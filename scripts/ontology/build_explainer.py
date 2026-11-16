"""Extract real data from the SDCO ontology and its DWA-M 150 example dataset
into docs/sdco_data.json, then inlines it into the self-contained HTML
explainer page docs/index.html. Every number on that page is measured here --
nothing hand-typed.

Read-only on all ontology files. Reuses parse_any() from
materialize_object_properties.py (same directory, importable directly since
python adds a script's own directory to sys.path[0]) rather than
reimplementing RDF/XML-vs-turtle sniffing or the xsd:string literal
normalization that join between m150 data and SDCO relies on.

    python scripts/ontology/build_explainer.py
"""

import argparse
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef

sys.path.insert(0, str(Path(__file__).resolve().parent))
from materialize_object_properties import CONSTRUCT_QUERY, classify_individuals, parse_any  # noqa: E402

# Token in docs/template.html replaced by the extracted JSON at build time.
PLACEHOLDER = "__SDCO_DATA__"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
M150_REPO = REPO_ROOT.parent / "m150-onto"

S = Namespace("https://l-jamora.github.io/sdco#")
M = Namespace("https://l-jamora.github.io/m150-onto#")

FAMILY_FIRST = {"B": "Pipe", "D": "Node"}
FAMILY_SECOND = {"A": "Fabric", "B": "Operation", "C": "Inventory", "D": "Other"}
FAMILY_NAMES = [
    "PipeFabric", "PipeOperation", "PipeInventory", "PipeOther",
    "NodeFabric", "NodeOperation", "NodeInventory", "NodeOther",
]

DESIGNATION_PROPS = {"hasPipeSectionTopNodeDesignation", "hasPipeSectionBottomNodeDesignation"}
PIPE_PROPS = [
    "hasMaterial", "hasPipeSectionProfileHeight", "hasPipeSectionProfileWidth",
    "hasPipeSectionLength", "hasPipeSectionPipeLength", "hasStreetName",
    "hasPipeSectionTopNodeDesignation", "hasPipeSectionBottomNodeDesignation",
    "hasDesignation",
]
NODE_PROPS = [
    "hasMaterial", "hasNodeManholeLength", "hasNodeManholeWidth", "hasDepth",
    "hasStreetName", "hasDesignation",
]

Q_CODE_CLASS = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?cls ?code WHERE {
  ?cls owl:equivalentClass ?restr .
  ?restr a owl:Restriction ; owl:onProperty m150:hasConditionCode ; owl:hasValue ?code .
}
"""


def local_name(uri) -> str:
    s = str(uri)
    return s.rsplit("#", 1)[-1] if "#" in s else s.rsplit("/", 1)[-1]


def humanize(name: str) -> str:
    """CrackFissure -> 'Crack Fissure'."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name)


def prop_key(local: str) -> str:
    """hasLongText -> longText; label -> label."""
    if local.startswith("has"):
        local = local[3:]
    return local[0].lower() + local[1:] if local else local


def simplify_value(g: Graph, val):
    """URIRef -> its rdfs:label if present, else local name. Literal -> python value
    (ISO string for dates). Used uniformly for report props, asset props, and
    query result rows."""
    if isinstance(val, URIRef):
        labels = sorted(g.objects(val, RDFS.label), key=lambda l: (getattr(l, "language", None) != "en", str(l)))
        return str(labels[0]) if labels else local_name(val)
    if hasattr(val, "toPython"):
        try:
            v = val.toPython()
        except Exception:
            return str(val)
        if hasattr(v, "isoformat"):
            return v.isoformat()
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        return str(v)
    return str(val)


def family_of(code: str) -> str:
    return FAMILY_FIRST.get(code[0], "?") + FAMILY_SECOND.get(code[1], "?")


def meaning_of(g: Graph, cls: URIRef):
    """Humanized someValuesFrom filler(s) from the code class's own direct
    rdfs:subClassOf restrictions (not its char1/char2 intersection subclasses) --
    e.g. :BAB -> 'Fissure'. None if the class carries no such restriction."""
    fillers = []
    for restr in g.objects(cls, RDFS.subClassOf):
        if (restr, RDF.type, OWL.Restriction) in g:
            filler = g.value(restr, OWL.someValuesFrom)
            if filler is not None:
                fillers.append(str(g.value(filler, RDFS.label) or humanize(local_name(filler))))
    return "; ".join(fillers) if fillers else None


def build_inspections(merged: Graph) -> dict:
    out = {}
    for insp, _, asset in merged.triples((None, M.inspects, None)):
        date_lit = merged.value(insp, M.hasInspectionDateTime)
        date_str = simplify_value(merged, date_lit) if date_lit is not None else None
        asset_type = None
        for t in merged.objects(asset, RDF.type):
            if local_name(t) in ("PipeSection", "Node"):
                asset_type = local_name(t)
                break
        out[local_name(insp)] = {
            "assetId": local_name(asset),
            "assetType": asset_type,
            "date": date_str,
        }
    return out


def build_reports(merged: Graph, m150_data: Graph, materialized_graph: Graph, inspections: dict) -> list:
    reports = []
    for report_uri in sorted(m150_data.subjects(RDF.type, M.ConditionReport), key=str):
        props = {}
        child_of = None
        for p, o in sorted(merged.predicate_objects(report_uri), key=lambda t: (str(t[0]), str(t[1]))):
            if p == RDF.type or str(p).startswith(str(S)):
                continue  # SDCO-namespace triples come from materialized_graph -> "sdco" below
            lname = local_name(p)
            if lname == "isChildOf":
                child_of = o
                continue
            key = prop_key(lname)
            val = simplify_value(merged, o)
            if key in props:
                existing = props[key]
                props[key] = existing + [val] if isinstance(existing, list) else [existing, val]
            else:
                props[key] = val

        rec = {"id": local_name(report_uri)}
        rec["code"] = props.pop("conditionCode", None)
        rec["char1"] = props.pop("characterization1", None)
        rec["char2"] = props.pop("characterization2", None)
        rec.update(props)

        insp_id = local_name(child_of) if child_of is not None else None
        insp = inspections.get(insp_id, {})
        rec["assetId"] = insp.get("assetId")
        rec["assetType"] = insp.get("assetType")
        rec["inspectionId"] = insp_id
        rec["inspectionDate"] = insp.get("date")

        rec["sdco"] = sorted(
            ({"property": local_name(p), "class": local_name(o)} for p, o in materialized_graph.predicate_objects(report_uri)),
            key=lambda e: (e["property"], e["class"]),
        )
        reports.append(rec)
    return reports


def build_codes(merged: Graph, reports: list) -> list:
    """Every code the ontology defines (~80, one equivalentClass per DIN EN
    13508-2 code), not just the ones the sample dataset happens to use --
    count is 0 for codes absent from this dataset rather than the code being
    dropped outright."""
    counts = Counter(r["code"] for r in reports)
    code_to_class = {str(code_lit): cls for cls, code_lit in merged.query(Q_CODE_CLASS)}
    codes = []
    for code, cls in sorted(code_to_class.items()):
        count = counts.get(code, 0)
        # :BDC carries three comments (description + one per characterisation);
        # value() picked one at random, silently dropping the other two.
        comment = "\n\n".join(sorted(
            (str(c) for c in merged.objects(cls, RDFS.comment)),
            key=lambda c: (c.startswith("Characterisation"), c),
        )) or None
        codes.append({
            "code": code,
            "count": count,
            "sdcoClass": local_name(cls),
            "comment": comment,
            "family": family_of(code),
            "meaning": meaning_of(merged, cls),
        })
    codes.sort(key=lambda c: (-c["count"], c["code"]))
    return codes


def build_class_edges(g: Graph):
    """child -> set(named parents) and its reverse, from rdfs:subClassOf triples
    with a named (URIRef) object -- skips the blank-node someValuesFrom
    restrictions, which aren't part of the plain class tree."""
    edges = defaultdict(set)
    for child, _, parent in g.triples((None, RDFS.subClassOf, None)):
        if isinstance(child, URIRef) and isinstance(parent, URIRef):
            edges[child].add(parent)
    desc = defaultdict(set)
    for child, parents in edges.items():
        for parent in parents:
            desc[parent].add(child)
    return edges, desc


def make_ancestors_fn(edges: dict):
    cache = {}

    def ancestors(cls):
        if cls in cache:
            return cache[cls]
        cache[cls] = set()  # cycle guard
        acc = set()
        for parent in edges.get(cls, ()):
            acc.add(parent)
            acc |= ancestors(parent)
        cache[cls] = acc
        return acc

    return ancestors


def build_report_ancestor_sets(reports: list, ancestors) -> dict:
    out = {}
    for r in reports:
        classes = {S[e["class"]] for e in r["sdco"]}
        aset = set()
        for cls in classes:
            aset.add(cls)
            aset |= ancestors(cls)
        out[r["id"]] = aset
    return out


def build_observation_tree(desc: dict, report_ancestor_sets: dict) -> dict:
    def count(node):
        return sum(1 for aset in report_ancestor_sets.values() if node in aset)

    def rec(node, path):
        if node in path:  # cycle guard, shouldn't trigger on a real class tree
            return {"name": local_name(node), "children": [], "reportCount": count(node)}
        children = sorted(desc.get(node, ()), key=lambda u: local_name(u))
        return {
            "name": local_name(node),
            "children": [rec(c, path | {node}) for c in children],
            "reportCount": count(node),
        }

    return rec(S.Observation, frozenset())


def build_reference_tree(codes: list) -> dict:
    """Shallow by design: Reference -> 8 families -> present codes as leaves,
    reportCount derived from each code's letter-key family rather than walking
    the full char1/char2 variant subtree (hundreds of classes deep)."""
    children = []
    for fam in FAMILY_NAMES:
        fam_codes = [c for c in codes if c["family"] == fam]
        children.append({
            "name": fam,
            "children": [{"name": c["code"], "children": [], "reportCount": c["count"]} for c in fam_codes],
            "reportCount": sum(c["count"] for c in fam_codes),
        })
    return {"name": "Reference", "children": children, "reportCount": sum(c["count"] for c in codes)}


def build_assets(merged: Graph, m150_data: Graph, reports: list) -> list:
    assets = []
    for type_name, cls, prop_list in (("PipeSection", M.PipeSection, PIPE_PROPS), ("Node", M.Node, NODE_PROPS)):
        for a in sorted(m150_data.subjects(RDF.type, cls), key=str):
            rec = {"id": local_name(a), "type": type_name}
            for p_local in prop_list:
                val = merged.value(a, M[p_local])
                if val is None:
                    continue
                key = prop_key(p_local)
                rec[key] = local_name(val) if p_local in DESIGNATION_PROPS else simplify_value(merged, val)
            rec["reportCount"] = sum(1 for r in reports if r["assetId"] == rec["id"])
            assets.append(rec)
    return assets


def run_query(g: Graph, sparql: str, cols: list) -> list:
    rows = []
    for row in g.query(sparql):
        rows.append({
            c: (local_name(row[i]) if isinstance(row[i], URIRef) else simplify_value(g, row[i]))
               if row[i] is not None else None
            for i, c in enumerate(cols)
        })
    rows.sort(key=lambda r: [(v is not None, str(v)) for v in r.values()])
    return rows


def build_queries(merged: Graph, reports: list) -> list:
    reports_by_id = {r["id"]: r for r in reports}
    queries = []

    # q1 -- fissures (pipe + node), via the taxonomy dimension shared by both codes
    q1_sparql = """
PREFIX sdco: <https://l-jamora.github.io/sdco#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?report ?code ?cls WHERE {
  ?report m150:hasConditionCode ?code .
  { ?report sdco:hasPipeFabricDamage ?cls } UNION { ?report sdco:hasNodeFabricDamage ?cls }
  ?cls rdfs:subClassOf* sdco:Fissure .
}
""".strip()
    rows1 = run_query(merged, q1_sparql, ["report", "code", "cls"])
    for row in rows1:
        row["asset"] = reports_by_id.get(row["report"], {}).get("assetId")
        row["class"] = row.pop("cls")
    q1_without_sparql = """
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?report ?code WHERE {
  ?report m150:hasConditionCode ?code .
  FILTER(?code IN ("BAB", "DAB"))
}
""".strip()
    run_query(merged, q1_without_sparql, ["report", "code"])  # executed for honesty, not stored twice
    queries.append({
        "id": "q1",
        "question": "Show me every fissure in the network",
        "sparql": q1_sparql,
        "results": rows1,
        "resultCount": len(rows1),
        "withoutSdco": {
            "explanation": (
                "BAB (pipe fissure) and DAB (node fissure) are the same underlying defect but share no "
                "common substring or numeric relationship in the raw condition code -- a code-only query "
                "has no way to know they should be grouped together without a human already knowing "
                "DIN EN 13508-2's code table by heart."
            ),
            "sparql": q1_without_sparql,
        },
    })

    # q2 -- orientation. Strongest example: no equivalent raw-code query exists at all.
    q2_sparql = """
PREFIX sdco: <https://l-jamora.github.io/sdco#>
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?report ?code ?orientation WHERE {
  ?report m150:hasConditionCode ?code ;
          sdco:hasDamageOrientation ?orientation .
}
""".strip()
    rows2 = run_query(merged, q2_sparql, ["report", "code", "orientation"])
    for row in rows2:
        row["asset"] = reports_by_id.get(row["report"], {}).get("assetId")
    vertical = [r for r in rows2 if r["orientation"] == "Vertical"]
    longitudinal = [r for r in rows2 if r["orientation"] == "Longitudinal"]
    queries.append({
        "id": "q2",
        "question": "Which damages run vertically?",
        "sparql": q2_sparql,
        "results": vertical,
        "resultCount": len(vertical),
        "contrast": {"orientation": "Longitudinal", "count": len(longitudinal)},
        "withoutSdco": {
            "explanation": (
                "Orientation is buried in hasCharacterization2, whose value's meaning is entirely "
                "code-dependent (the same letter means a different thing for a different code) -- there "
                "is no equivalent query over the raw m150 data alone."
            ),
            "sparql": None,
        },
    })

    # q3 -- structural defect vs operational defect vs inventory note vs other observation
    q3_sparql = """
PREFIX sdco: <https://l-jamora.github.io/sdco#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?report ?code ?cls ?bucket WHERE {
  ?report m150:hasConditionCode ?code .
  VALUES ?prop { sdco:hasPipeFabricDamage sdco:hasNodeFabricDamage sdco:hasPipeOperationDamage sdco:hasNodeOperationDamage sdco:hasPipeInventoryFeature sdco:hasNodeInventoryFeature sdco:hasPipeFeature sdco:hasNodeFeature sdco:hasDamageOrientation sdco:hasDamageCause sdco:hasTerminationReason sdco:hasConnectionDischargeDirection }
  ?report ?prop ?cls .
  VALUES ?bucket { sdco:StructuralDefect sdco:OperationalDefect sdco:Inventory sdco:OtherObservation }
  ?cls rdfs:subClassOf* ?bucket .
}
""".strip()
    rows3 = run_query(merged, q3_sparql, ["report", "code", "cls", "bucket"])
    bucket_reports = defaultdict(set)
    for row in rows3:
        bucket_reports[row["bucket"]].add(row["report"])
    q3_results = [{"bucket": b, "reportCount": len(reps)} for b, reps in sorted(bucket_reports.items())]
    q3_without_sparql = """
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?report ?code WHERE {
  ?report m150:hasConditionCode ?code .
  FILTER(REGEX(?code, "^.A"))
}
""".strip()
    run_query(merged, q3_without_sparql, ["report", "code"])
    queries.append({
        "id": "q3",
        "question": "Which observations are structural defects, and which are just inventory notes?",
        "sparql": q3_sparql,
        "results": q3_results,
        "resultCount": len(rows3),
        "withoutSdco": {
            "explanation": (
                "The split roughly correlates with the condition code's 2nd letter (A=Fabric, B=Operation, "
                "C=Inventory, D=Other) by DIN EN 13508-2 convention, but that convention lives in the "
                "standard's documentation, not in the triple store -- nothing in the raw m150 data marks a "
                "code as 'structural' vs 'just inventory'; a raw-code query has to hardcode the letter "
                "convention by hand, per code family, with no way to verify it against the data itself."
            ),
            "sparql": q3_without_sparql,
        },
    })

    # q4 -- root intrusions
    q4_sparql = """
PREFIX sdco: <https://l-jamora.github.io/sdco#>
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?report ?code WHERE {
  ?report m150:hasConditionCode ?code ;
          sdco:hasPipeOperationDamage sdco:ComplexMassRoots .
}
""".strip()
    rows4 = run_query(merged, q4_sparql, ["report", "code"])
    for row in rows4:
        row["asset"] = reports_by_id.get(row["report"], {}).get("assetId")
        row["class"] = "ComplexMassRoots"
    q4_without_sparql = """
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?report WHERE {
  ?report m150:hasConditionCode "BBA" ;
          m150:hasCharacterization1 "C" .
}
""".strip()
    rows4b = run_query(merged, q4_without_sparql, ["report"])
    if len(rows4b) != len(rows4):
        print(f"[warn] q4: sdco query found {len(rows4)} rows but code+char1 query found {len(rows4b)}", file=sys.stderr)
    queries.append({
        "id": "q4",
        "question": "Where are the root intrusions?",
        "sparql": q4_sparql,
        "results": rows4,
        "resultCount": len(rows4),
        "withoutSdco": {
            "explanation": "Needs code BBA AND hasCharacterization1 = 'C' -- two fields, not one.",
            "sparql": q4_without_sparql,
        },
    })

    # q5 -- manhole infiltration
    q5_sparql = """
PREFIX sdco: <https://l-jamora.github.io/sdco#>
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?report ?code ?cls WHERE {
  ?report m150:hasConditionCode ?code ;
          sdco:hasNodeOperationDamage ?cls .
  FILTER(?cls IN (sdco:WallInfiltration, sdco:SweatingInfiltration))
}
""".strip()
    rows5 = run_query(merged, q5_sparql, ["report", "code", "cls"])
    for row in rows5:
        row["asset"] = reports_by_id.get(row["report"], {}).get("assetId")
        row["class"] = row.pop("cls")
    queries.append({
        "id": "q5",
        "question": "Which manholes show infiltration?",
        "sparql": q5_sparql,
        "results": rows5,
        "resultCount": len(rows5),
        "withoutSdco": {
            "explanation": (
                "Both rows come from the same raw code (DBF); SweatingInfiltration vs WallInfiltration is "
                "determined by whether the differentiating characterization is char1 or char2 and which "
                "literal value it holds -- not discoverable from the code string alone."
            ),
            "sparql": None,
        },
    })

    # q6 -- not damage at all (inventory notes / other observations)
    q6_sparql = """
PREFIX sdco: <https://l-jamora.github.io/sdco#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?report ?code ?cls WHERE {
  ?report m150:hasConditionCode ?code .
  VALUES ?prop { sdco:hasPipeFabricDamage sdco:hasNodeFabricDamage sdco:hasPipeOperationDamage sdco:hasNodeOperationDamage sdco:hasPipeInventoryFeature sdco:hasNodeInventoryFeature sdco:hasPipeFeature sdco:hasNodeFeature sdco:hasDamageOrientation sdco:hasDamageCause sdco:hasTerminationReason sdco:hasConnectionDischargeDirection }
  ?report ?prop ?cls .
  VALUES ?bucket { sdco:Inventory sdco:OtherObservation }
  ?cls rdfs:subClassOf* ?bucket .
}
""".strip()
    rows6 = run_query(merged, q6_sparql, ["report", "code", "cls"])
    distinct6 = sorted({r["report"] for r in rows6})
    q6_results = [{"report": rid, "code": reports_by_id[rid]["code"], "asset": reports_by_id[rid].get("assetId")} for rid in distinct6]
    q6_without_sparql = """
PREFIX m150: <https://l-jamora.github.io/m150-onto#>
SELECT ?report ?code WHERE {
  ?report m150:hasConditionCode ?code .
  FILTER(?code IN ("DDB", "BDC"))
}
""".strip()
    run_query(merged, q6_without_sparql, ["report", "code"])
    queries.append({
        "id": "q6",
        "question": "Which reports aren't damage at all?",
        "sparql": q6_sparql,
        "results": q6_results,
        "resultCount": len(q6_results),
        "withoutSdco": {
            "explanation": (
                "No single field marks a report as 'not damage' -- an analyst has to already know and "
                "enumerate every non-damage code by hand (e.g. DDB for general remarks, BDC for inspection "
                "termination, and every inventory-feature code besides), with no way to check the list is "
                "complete."
            ),
            "sparql": q6_without_sparql,
        },
    })

    return queries


# ---------------------------------------------------------------------------
# m150-onto side: the same condition report as DWA-M 150 XML and as RDF
# ---------------------------------------------------------------------------

XML_EXAMPLE = "DWA M 150 Beispiel 04_2010 Typ B .xml"
MAPPING_CSV = Path("ontoparser") / "mapping_DWA-to-m150onto.csv"
FEATURED_CODE = "BAB"  # first report with this code that has exactly one XML counterpart
XSD = "http://www.w3.org/2001/XMLSchema#"
TRIPLE_ORDER = [
    "type", "label", "hasConditionCode", "hasCharacterization1", "hasCharacterization2",
    "hasQuantification1", "hasLinearDamage", "hasPipeSectionConditionStation", "hasPositionFrom",
    "hasPositionTo", "hasVideoCounterReading", "hasImageName", "hasLongText", "isChildOf",
]


def load_mapping(path: Path) -> dict:
    """DWA element code -> m150-onto property local name (object or data property)."""
    out = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) >= 3 and (row[1] or row[2]):
                out[row[0]] = row[1] or row[2]
    return out


def fmt_object(o) -> dict:
    if isinstance(o, URIRef):
        return {"kind": "iri", "text": "m150:" + local_name(o)}
    dt = getattr(o, "datatype", None)
    return {"kind": "lit", "text": str(o), "datatype": ("xsd:" + str(dt).replace(XSD, "")) if dt else None}


def restriction_text(g: Graph, node) -> str:
    """Compact Manchester-style text of an owl:Restriction (hasValue / someValuesFrom)."""
    prop = local_name(g.value(node, OWL.onProperty))
    if (node, OWL.hasValue, None) in g:
        return f'{prop} value "{g.value(node, OWL.hasValue)}"'
    return f"{prop} some {local_name(g.value(node, OWL.someValuesFrom))}"


def class_axioms(g: Graph, cls: URIRef) -> dict:
    """The real equivalentClass / subClassOf restriction text of a class, for display."""
    equiv = []
    for node in g.objects(cls, OWL.equivalentClass):
        if (node, OWL.intersectionOf, None) in g:
            parts = []
            lst = g.value(node, OWL.intersectionOf)
            for item in g.items(lst):
                parts.append(local_name(item) if isinstance(item, URIRef) else restriction_text(g, item))
            equiv.append(" and ".join(parts))
        else:
            equiv.append(restriction_text(g, node))
    subs = [restriction_text(g, o) for o in g.objects(cls, RDFS.subClassOf) if (o, RDF.type, OWL.Restriction) in g]
    named = [local_name(o) for o in g.objects(cls, RDFS.subClassOf) if isinstance(o, URIRef)]
    label = g.value(cls, RDFS.label)
    return {"name": local_name(cls), "label": str(label) if label else None,
            "equivalentTo": equiv, "subClassOf": subs, "namedSupers": sorted(named)}


def shortest_chain(edges: dict, start: URIRef, goal: URIRef):
    """BFS over named rdfs:subClassOf edges: start -> ... -> goal (None if unreachable)."""
    prev, queue = {start: None}, [start]
    for node in queue:
        if node == goal:
            chain = []
            while node is not None:
                chain.append(node)
                node = prev[node]
            return chain
        for parent in sorted(edges.get(node, ()), key=str):
            if parent not in prev:
                prev[parent] = node
                queue.append(parent)
    return None


def build_m150(m150_root: Path, sdco_graph: Graph, m150_data: Graph, m150_tbox: Graph,
               materialized_graph: Graph, reports: list, codes: list) -> dict:
    """Stats about m150-onto + the featured record shown both as XML and as RDF,
    and the classification trace of that record through SDCO."""
    xml_path = m150_root / "xml" / XML_EXAMPLE
    tree = ET.parse(xml_path)  # honours the XML declaration's ISO-8859-1
    root = tree.getroot()
    parent = {c: p for p in root.iter() for c in p}
    mapping = load_mapping(m150_root / MAPPING_CSV)

    # --- find the featured record: same URI key the ontoparser builds ---
    featured_uri = None
    candidates = sorted((r for r in m150_data.subjects(RDF.type, M.ConditionReport)
                         if local_name(r).endswith("_" + FEATURED_CODE)), key=str)
    wanted = {local_name(c): c for c in candidates}
    hz_match = {}
    for el in root.iter():
        if el.tag not in ("HZ", "KZ"):
            continue
        asset = parent[parent[el]]  # HZ -> HI -> HG (pipe) ; KZ -> KI -> KG (node)
        asset_id = (asset.findtext("HG001") or asset.findtext("KG001") or "").strip()
        station = (el.findtext(el.tag + "001") or "").strip().replace(",", "_").replace(".", "_")
        code = (el.findtext(el.tag + "002") or "").strip()
        key = f"Beispiel_Condition_{asset_id}_{station}_{code}"
        if key in wanted:
            hz_match.setdefault(key, []).append((el, asset_id))
    unique = [k for k in sorted(wanted) if len(hz_match.get(k, [])) == 1]
    assert unique, "no featured report with exactly one XML counterpart"
    key = unique[0]
    featured_uri = wanted[key]
    el, asset_id = hz_match[key][0]

    # --- XML rows and the triple each one became ---
    triples = {}
    for p, o in m150_data.predicate_objects(featured_uri):
        if p == RDF.type:
            if o == M.ConditionReport:
                triples["type"] = {"p": "a", "o": fmt_object(o)}
            continue
        triples[local_name(p) if p != RDFS.label else "label"] = {"p": "m150:" + local_name(p) if p != RDFS.label else "rdfs:label", "o": fmt_object(o)}
    xml_rows, used = [], set()
    for child in el:
        val = (child.text or "").strip()
        if not val:
            continue
        prop = mapping.get(child.tag)
        assert prop in triples, f"{child.tag} -> {prop} not found among the RDF triples of {key}"
        used.add(prop)
        xml_rows.append({"tag": child.tag, "value": val, "prop": prop})
    for k in triples:
        if k not in used:
            triples[k]["parserAdded"] = True
    ordered = sorted(triples, key=lambda k: TRIPLE_ORDER.index(k) if k in TRIPLE_ORDER else 99)

    feat_report = next(r for r in reports if r["id"] == local_name(featured_uri))
    code_str = feat_report["code"]

    # --- classification trace: assert literals -> forward chain -> materialize (cross-checked) ---
    g = Graph()
    for t in sdco_graph:
        g.add(t)
    for p, o in m150_data.predicate_objects(featured_uri):
        g.add((featured_uri, p, o))
    before = set(g.objects(featured_uri, RDF.type))
    classify_individuals(g)
    inferred = [t for t in g.objects(featured_uri, RDF.type) if t not in before and isinstance(t, URIRef)]
    constructed = sorted((local_name(p), local_name(o)) for _, p, o in g.query(CONSTRUCT_QUERY) if _ == featured_uri)
    expected = sorted((e["property"], e["class"]) for e in feat_report["sdco"])
    assert constructed == expected, f"re-derived materialization {constructed} != materialized file {expected}"

    edges, _ = build_class_edges(sdco_graph)
    ancestors = make_ancestors_fn(edges)
    inferred_info = []
    for t in sorted(inferred, key=lambda c: (len(ancestors(c)), str(c))):
        ax = class_axioms(sdco_graph, t)
        if (S[ax["name"]], None, None) not in sdco_graph:
            continue
        inferred_info.append(ax)
    chains = []
    for prop, cls in constructed:
        chain = shortest_chain(edges, S[cls], S.Observation) or [S[cls]]
        chains.append({"property": prop, "class": cls, "chain": [local_name(c) for c in chain]})

    # --- m150-onto statistics ---
    all_elems = list(root.iter())
    stats = {
        "classes": len([s for s in m150_tbox.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)]),
        "objectProperties": len([s for s in m150_tbox.subjects(RDF.type, OWL.ObjectProperty) if isinstance(s, URIRef)]),
        "dataProperties": len([s for s in m150_tbox.subjects(RDF.type, OWL.DatatypeProperty) if isinstance(s, URIRef)]),
        "namedIndividuals": len({s for s in m150_tbox.subjects(RDF.type, OWL.NamedIndividual) if isinstance(s, URIRef)}),
        "xmlBytes": xml_path.stat().st_size,
        "xmlElements": len(all_elems),
        "xmlDistinctTags": len({e.tag for e in all_elems}),
        "xmlConditionBlocks": sum(1 for e in all_elems if e.tag in ("HZ", "KZ")),
        "mappedDwaElements": len(mapping),
        "parsedIndividuals": len({s for s in m150_data.subjects() if isinstance(s, URIRef)}),
    }
    # The XML has more condition blocks than the RDF has report individuals (108 vs 96 here): the
    # page therefore only cites the individual count, not the block count.
    assert stats["xmlConditionBlocks"] >= len(reports), "fewer XML condition blocks than ConditionReport individuals"

    # fissure comparison: how many (code, char1, char2) combinations would a code-only query have to enumerate
    fissure_classes = sorted({local_name(c) for c in sdco_graph.transitive_subjects(RDFS.subClassOf, S.Fissure)} - {"Fissure"})
    return {
        "stats": stats,
        "featured": {
            "reportId": local_name(featured_uri),
            "code": code_str,
            "assetId": asset_id,
            "xmlPath": f"{el.tag[0]}G > {el.tag[0]}I > {el.tag}",
            "xmlRows": xml_rows,
            "triples": [{"key": k, **triples[k]} for k in ordered],
            "inferred": inferred_info,
            "materialized": chains,
            "fissureSubclasses": fissure_classes,
        },
    }


def build_fissure_comparison(queries: list, reports: list, subclasses: list) -> dict:
    """q1 re-cut for the 'all fissures' animation: how many hits per raw code / per
    (code, char1, char2) combination a code-only query would have to enumerate,
    versus the single subsumption query."""
    by_id = {r["id"]: r for r in reports}
    q1 = next(q for q in queries if q["id"] == "q1")
    combos = Counter()
    per_code = Counter()
    for row in q1["results"]:
        r = by_id[row["report"]]
        combos[(r["code"], r["char1"], r["char2"], row["class"])] += 1
        per_code[r["code"]] += 1
    return {
        "total": q1["resultCount"],
        "perCode": [{"code": c, "count": n} for c, n in sorted(per_code.items())],
        "combos": [{"code": c, "char1": a, "char2": b, "class": k, "count": n}
                   for (c, a, b, k), n in sorted(combos.items())],
        "subclassCount": len(subclasses),
    }


CHAR_PROPS = {"char1": M.hasCharacterization1, "char2": M.hasCharacterization2}

Q_CHAR_SUBCLASSES = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?cls ?base ?prop ?val WHERE {
  ?cls owl:equivalentClass ?inter . ?inter owl:intersectionOf ?list .
  ?list rdf:rest*/rdf:first ?base . ?list rdf:rest*/rdf:first ?restr .
  ?restr a owl:Restriction ; owl:onProperty ?prop ; owl:hasValue ?val .
  FILTER (isIRI(?base))
}
"""

# A report violates a dimension when its code class has characterisation subclasses on that property, the
# report carries a letter there, and (after classify_individuals) it landed in none of those subclasses.
# VALUES lists come from Q_CHAR_SUBCLASSES (a path-based FILTER NOT EXISTS over the whole graph took minutes).
Q_CHAR_VIOLATIONS = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?r ?base ?val WHERE {
  VALUES ?base { %s }
  ?r <%s> ?val . ?r rdf:type ?base .
  FILTER (STR(?val) != "")
  FILTER NOT EXISTS { VALUES ?sub { %s } ?r rdf:type ?sub . }
}
"""


def build_consistency(sdco_graph: Graph, m150_data: Graph, featured_code: str) -> dict:
    """Co-occurrence check: a report whose main code has characterisation subclasses (per dimension) but whose
    letter is not one of them is classified into the base code class and into none of its subclasses.
    SDCO does not encode which characterisations are mandatory, so a missing value is never flagged; only a
    present letter that matches no subclass is."""
    allowed = defaultdict(lambda: defaultdict(set))
    sub_iris = defaultdict(set)  # property -> subclass IRIs
    base_iris = defaultdict(set)
    for cls, base, prop, val in sdco_graph.query(Q_CHAR_SUBCLASSES):
        allowed[local_name(base)][local_name(prop)].add(str(val))
        sub_iris[prop].add(cls)
        base_iris[prop].add(base)
    assert allowed, "no characterisation subclasses found in SDCO.rdf"
    inv = {local_name(v): k for k, v in CHAR_PROPS.items()}
    assert set(inv) >= {local_name(p) for d in allowed.values() for p in d}, "unexpected restriction property in intersections"

    # Completeness invariant: letters other than the special X/Z (other) must run A, B, C, ... without a gap.
    # A gap means the subclass set may be incomplete (or the standard skips a letter); such a dimension is
    # reported and left out of the check so it cannot cause a false positive.
    unverified = []
    for code in sorted(allowed):
        for prop, vals in sorted(allowed[code].items()):
            plain = sorted(v for v in vals if len(v) == 1 and v not in "XZ")
            if plain != [chr(65 + i) for i in range(len(plain))]:
                unverified.append({"code": code, "dim": inv[prop], "letters": sorted(vals)})
    skip = {(u["code"], local_name(CHAR_PROPS[u["dim"]])) for u in unverified}
    assert len(unverified) <= 3, f"too many dimensions with gaps in their letters: {unverified}"

    def violations(g: Graph) -> list:
        out = []
        for dim, prop in CHAR_PROPS.items():
            q = Q_CHAR_VIOLATIONS % (" ".join(f"<{x}>" for x in sorted(base_iris[prop])), prop,
                                     " ".join(f"<{x}>" for x in sorted(sub_iris[prop])))
            for r, base, val in g.query(q):
                if (local_name(base), local_name(prop)) in skip:
                    continue
                out.append({"report": local_name(r), "code": local_name(base), "dim": dim, "value": str(val)})
        return sorted(out, key=lambda v: (v["report"], v["dim"]))

    g = Graph()
    for t in sdco_graph:
        g.add(t)
    for t in m150_data:
        g.add(t)
    classify_individuals(g)
    reports = sorted(g.subjects(RDF.type, M.ConditionReport), key=str)
    assert len(reports) == 96, f"expected 96 reports, got {len(reports)}"
    covered = {r for r in reports for p in CHAR_PROPS.values()
               if str(g.value(r, p) or "").strip() and any(
                   local_name(p) in allowed.get(local_name(t), {}) and (local_name(t), local_name(p)) not in skip
                   for t in g.objects(r, RDF.type))}
    found = violations(g)

    # constructed counter-example: one BAB-like report with a letter valid for other codes but not for this one
    code = featured_code
    assert code in allowed and "hasCharacterization1" in allowed[code], f"{code} has no characterisation-1 subclasses"
    ok1 = allowed[code]["hasCharacterization1"]
    elsewhere = sorted({v for c, d in allowed.items() if c != code for v in d.get("hasCharacterization1", ()) if len(v) == 1 and v != "Z"} - ok1)
    assert elsewhere, "no letter that is valid elsewhere but not for the featured code"
    bad = elsewhere[0]
    ex = URIRef("urn:example:constructed-report")
    for val, expect in ((bad, True), (sorted(ok1)[0], False)):  # the second one is a control, not shown
        cg = Graph()
        for t in sdco_graph:
            cg.add(t)
        cg.add((ex, RDF.type, M.ConditionReport))
        cg.add((ex, M.hasConditionCode, Literal(code)))
        cg.add((ex, M.hasCharacterization1, Literal(val)))
        classify_individuals(cg)
        flagged = violations(cg)
        assert bool(flagged) == expect, f"constructed {code}/{val}: flagged={flagged}, expected {expect}"
        if expect:
            types = sorted(local_name(t) for t in cg.objects(ex, RDF.type) if str(t).startswith(str(S)))
    assert types == [code], f"constructed report should be typed only {code}, got {types}"

    dims = sum(len(d) for d in allowed.values())
    # Which schema does the example file name, and is it in the m150-onto repo? (It is not: nothing is claimed about it.)
    xml_head = next(M150_REPO.glob("xml/DWA M 150 Beispiel 04_2010 Typ B*.xml")).read_bytes()[:600].decode("latin-1")
    xsd = re.search(r'noNamespaceSchemaLocation="([^"]+)"', xml_head).group(1)
    assert not list(M150_REPO.rglob("*.xsd")), "an .xsd now exists in m150-onto: read it and state what it constrains for HZ014/HZ015"
    return {
        "xsd": xsd,
        "code": code,
        "allowed": {d: sorted(allowed[code][local_name(p)]) for d, p in CHAR_PROPS.items() if local_name(p) in allowed[code]},
        "fieldLetters": {d: sorted({v for c in allowed.values() for v in c.get(local_name(p), ())}) for d, p in CHAR_PROPS.items()},
        "coverage": {"codes": len(allowed), "dimensions": dims,
                     "unverified": unverified},
        "sample": {"reports": len(reports), "checked": len(covered), "violations": len({h["report"] for h in found}), "hits": found,
                   "byLetter": [{"code": c, "dim": d, "value": v, "n": n} for (c, d, v), n in sorted(Counter((h["code"], h["dim"], h["value"]) for h in found).items())]},
        "counter": {"code": code, "dim": "char1", "value": bad, "allowed": sorted(ok1), "classes": types},
    }


def build_benefits(sdco_graph: Graph, m150_data: Graph, m150: dict, codes: list, linked_graph: dict, materialized_triples: int,
                   materialized_subjects: int) -> dict:
    """Facts for the 'Benefits' tab and the 'why not better XML software' scene. Everything is read from
    already extracted data or from SDCO.rdf / tests/, then sanity-asserted."""
    F, FI = m150["featured"], m150["fissure"]
    onto = next(sdco_graph.subjects(RDF.type, OWL.Ontology))
    version = str(sdco_graph.value(onto, OWL.versionInfo))
    imports = sorted(str(o) for o in sdco_graph.objects(onto, OWL.imports))
    version_iri = str(sdco_graph.value(onto, OWL.versionIRI))
    assert version and imports and version_iri.endswith(version), "SDCO.rdf: versionInfo / versionIRI / owl:imports inconsistent"

    # vendor-tool scene: real codes with their SDCO meaning; the per-tool 'copies' drawn from them are schematic
    used = [c for c in codes if c["count"] > 0 and c["meaning"]]
    pick = [next(c for c in used if c["code"] == F["code"])] + [c for c in used if c["code"] != F["code"]][:3]
    assert len(pick) == 4 and len({c["code"] for c in pick}) == 4, "vendor scene needs 4 distinct coded rows"
    vendor_rows = [{"code": c["code"], "meaning": c["meaning"]} for c in pick]

    # integration (future): the real disjointness group containing the featured report's orientation class
    a = next(m["class"] for m in F["materialized"] if m["property"] == "hasDamageOrientation")
    b = "Circumferential"
    group = None
    for grp in sdco_graph.subjects(RDF.type, OWL.AllDisjointClasses):
        members = [local_name(x) for x in sdco_graph.items(sdco_graph.value(grp, OWL.members))]
        if a in members and b in members:
            group = members
    assert group, f"no AllDisjointClasses group containing {a} and {b}"

    consistency = build_consistency(sdco_graph, m150_data, F["code"])

    ns = {n["id"]: n["ns"] for n in linked_graph["nodes"]}
    cross = sum(1 for e in linked_graph["edges"] if not e.get("detail") and ns.get(e["source"]) == "m150" and ns.get(e["target"]) == "sdco")
    assert cross >= 1, "linked graph has no m150 -> SDCO edge"
    assert FI["total"] >= 1 and FI["subclassCount"] >= 2 and len(FI["perCode"]) >= 2
    assert F["materialized"] and materialized_triples > len(F["materialized"])
    return {
        "version": version, "versionIri": version_iri, "imports": imports,
        "vendorRows": vendor_rows,
        "query": {"hits": FI["total"], "codes": [c["code"] for c in FI["perCode"]], "subclasses": FI["subclassCount"]},
        "inference": {"report": F["reportId"], "asserted": sum(1 for t in F["triples"] if not t.get("parserAdded")),
                      "materialized": F["materialized"][0], "forReport": len(F["materialized"]),
                      "total": materialized_triples, "subjects": materialized_subjects},
        "consistency": consistency,
        "integration": {"crossEdges": cross, "nodes": len([n for n in linked_graph["nodes"] if not n.get("detail")]),
                        "disjoint": {"a": a, "b": b, "group": group}},
    }


EXPLORER_DEMO = Path(__file__).resolve().parent / "explorer_demo.json"


def classify_mirror(codes: dict, code: str, c1: str = "", c2: str = "") -> list:
    """The two documented pattern shapes of classify_individuals() on the exported table: the plain code class,
    plus its characterisation subclass for each dimension whose letter matches exactly (hasValue)."""
    if code not in codes:
        return []
    out = [codes[code]["cls"]]
    for dim, letter in (("char1", c1), ("char2", c2)):
        out += [o["cls"] for o in codes[code]["dims"].get(dim, {}).get("options", []) if letter and o["value"] == letter]
    return out


def build_explorer(sdco_graph: Graph, m150_tbox: Graph, codes: list, edges: dict) -> dict:
    """Code browser, classifier and demo plan data, all read from SDCO.rdf (+ m150-onto labels)."""
    mapping = load_mapping(M150_REPO / MAPPING_CSV)
    xml_of = defaultdict(list)
    for el, prop in mapping.items():
        xml_of[prop].append(el)
    obs_root = S.Observation

    def mlabel(prop: str) -> dict:
        lab = m150_tbox.value(M[prop], RDFS.label)
        return {"prop": prop, "iri": str(M[prop]), "label": str(lab) if lab else None, "xml": sorted(xml_of.get(prop, []))}

    def filler_info(cls: URIRef):
        """First someValuesFrom filler of the class's own restrictions: label, and chain Observation -> filler."""
        for r in sdco_graph.objects(cls, RDFS.subClassOf):
            if (r, RDF.type, OWL.Restriction) in sdco_graph and (r, OWL.someValuesFrom, None) in sdco_graph:
                f = sdco_graph.value(r, OWL.someValuesFrom)
                ch = shortest_chain(edges, f, obs_root) or [f]
                lab = sdco_graph.value(f, RDFS.label)
                return {"name": local_name(f), "label": str(lab) if lab else humanize(local_name(f)),
                        "chain": [str(sdco_graph.value(c, RDFS.label) or humanize(local_name(c))) for c in ch]}
        return None

    # characterisation subclasses: exactly the (base code class) AND (one hasValue) shape
    dim_of = {local_name(v): k for k, v in CHAR_PROPS.items()}
    opts = defaultdict(lambda: defaultdict(list))
    for cls, base, prop, val in sdco_graph.query(Q_CHAR_SUBCLASSES):
        ax = class_axioms(sdco_graph, cls)
        opts[local_name(base)][dim_of[local_name(prop)]].append({
            "value": str(val), "cls": local_name(cls), "label": ax["label"], "iri": str(cls),
            "equivalentTo": ax["equivalentTo"][0], "implied": ax["subClassOf"], "filler": filler_info(cls)})
    out = {}
    for c in codes:
        cls = S[c["sdcoClass"]]
        ax = class_axioms(sdco_graph, cls)
        comment = c["comment"] or ""
        note = {}
        for k, lab in (("char1", "Char1"), ("char2", "Char2"), ("quantification", "Quantification")):
            m = re.search(rf"^{lab}:\s*(.+)$", comment, re.M)
            if m:
                note[k] = m.group(1).strip()
        dims = {}
        for dim, prop in CHAR_PROPS.items():
            o = sorted(opts[c["code"]].get(dim, []), key=lambda x: x["value"])
            if o:
                dims[dim] = {"m150": mlabel(local_name(prop)), "options": o, "note": note.get(dim)}
        out[c["code"]] = {
            "cls": c["sdcoClass"], "iri": str(cls), "label": ax["label"], "family": c["family"], "count": c["count"],
            "meaning": c["meaning"], "comment": comment or None, "quantification": note.get("quantification"),
            "equivalentTo": ax["equivalentTo"][0], "implied": ax["subClassOf"], "supers": ax["namedSupers"],
            "filler": filler_info(cls), "m150": mlabel("hasConditionCode"), "dims": dims}
    for code, d in out.items():  # the matching logic assumes the documented pattern shapes only
        assert d["equivalentTo"] == f'hasConditionCode value "{code}"', f"{code}: unexpected equivalentClass {d['equivalentTo']}"
        for dim, dd in d["dims"].items():
            for o in dd["options"]:
                assert o["equivalentTo"] == f'{d["cls"]} and hasCharacterization{dim[-1]} value "{o["value"]}"', f"{o['cls']}: unexpected pattern {o['equivalentTo']}"

    def name_of(code, c1="", c2=""):
        d = out[code]
        fills = [o["filler"]["label"] for dim, l in (("char1", c1), ("char2", c2)) for o in d["dims"].get(dim, {}).get("options", [])
                 if l and o["value"] == l and o["filler"]]
        return (d["meaning"] or code) + (": " + ", ".join(fills) if fills else "")

    demo = json.loads(EXPLORER_DEMO.read_text(encoding="utf-8"))
    mh = {m["id"]: m for m in demo["manholes"]}
    pipes = {p["id"]: p for p in demo["pipes"]}
    for p in pipes.values():
        a, b = mh[p["from"]], mh[p["to"]]
        p["length"] = round(((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** .5, 1)
    seen = set()
    for item in demo["presets"] + demo["observations"]:
        assert item["code"] in out, f"demo code {item['code']} not in SDCO"
        c1, c2 = item.get("char1", ""), item.get("char2", "")
        valid = all(l == "" or any(o["value"] == l for o in out[item["code"]]["dims"].get(dim, {}).get("options", []))
                    for dim, l in (("char1", c1), ("char2", c2)))
        assert valid != bool(item.get("expectFlag")), f"{item['id']}: letter validity unexpected"
        item["name"] = name_of(item["code"], c1, c2)
        item["classes"] = classify_mirror(out, item["code"], c1, c2)
        if item["id"].startswith("O"):
            assert item["id"] not in seen
            seen.add(item["id"])
            if "pipe" in item:
                assert item["station"] <= pipes[item["pipe"]]["length"], f"{item['id']} station beyond pipe length"
            else:
                assert item["manhole"] in mh
            assert 1 <= item["clock"] <= 12
    # cross-check the mirror against the real forward-chaining classifier
    g = Graph()
    for t in sdco_graph:
        g.add(t)
    inds = {}
    for i, item in enumerate(demo["presets"] + demo["observations"]):
        r = URIRef(f"urn:example:explorer-{i}")
        inds[r] = item
        g.add((r, RDF.type, M.ConditionReport))
        g.add((r, M.hasConditionCode, Literal(item["code"])))
        for k, p in (("char1", M.hasCharacterization1), ("char2", M.hasCharacterization2)):
            if item.get(k):
                g.add((r, p, Literal(item[k])))
    classify_individuals(g)
    known = {d["cls"] for d in out.values()} | {o["cls"] for d in out.values() for dd in d["dims"].values() for o in dd["options"]}
    for r, item in inds.items():
        real = sorted(local_name(t) for t in g.objects(r, RDF.type) if local_name(t) in known)
        assert real == sorted(item["classes"]), f"{item['id']}: mirror {item['classes']} != classify_individuals {real}"
    return {"codes": out, "families": FAMILY_NAMES, "demo": demo}


def check_i18n(template: str, query_ids: list) -> int:
    """Key parity between the two languages, and every key the page uses must exist."""
    m = re.search(r'<script type="application/json" id="i18n">(.*?)</script>', template, re.S)
    assert m, "template has no i18n dictionary block"
    d = json.loads(m.group(1))
    en, de = set(d["en"]), set(d["de"])
    assert en == de, f"i18n key mismatch: only EN {sorted(en - de)}, only DE {sorted(de - en)}"
    used = set(re.findall(r'data-i(?:-html|-ph)?="([^"]+)"', template))
    used |= set(re.findall(r"\bt\('([^']+)'[,)]", template))
    used |= {f"q.{i}.{f}" for i in query_ids for f in ("question", "why")}
    missing = sorted(k for k in used if k not in en)
    assert not missing, f"i18n keys used but undefined: {missing}"
    return len(en)


def build_linked_graph(sdco_graph: Graph, m150_data: Graph, m150_tbox: Graph, materialized_graph: Graph,
                       reports: list, inspections: dict, max_depth: int = 1, max_reports: int = 5) -> dict:
    """Node-edge subgraph for the 'linked data' scene: the pipe section whose reports cover
    the most distinct codes -> its inspection -> one report per distinct code (first max_reports) -> code literal,
    SDCO code class (rdf:type from classify_individuals), materialized object-property fillers
    and their rdfs:subClassOf chain (max_depth steps up). Every edge is a real triple."""
    by_asset = defaultdict(list)
    for r in reports:
        if r["assetType"] == "PipeSection":
            by_asset[r["assetId"]].append(r)
    asset_id = max(sorted(by_asset), key=lambda a: len({r["code"] for r in by_asset[a]}))
    first = {}
    for r in sorted(by_asset[asset_id], key=lambda r: r["id"]):
        first.setdefault(r["code"], r)
    # Prefer a fissure report (filler under sdco:Fissure) so the scene shows the chain up to :Fissure.
    edges_sc, _ = build_class_edges(sdco_graph)
    by_name = {local_name(u): u for u in m150_data.subjects(RDF.type, M.ConditionReport)}

    def climbs_to_fissure(c):
        todo, seen = [c], set()
        while todo:
            x = todo.pop()
            if x == S.Fissure:
                return True
            if x not in seen:
                seen.add(x)
                todo += edges_sc.get(x, ())
        return False

    fissure = next((r for r in sorted(by_asset[asset_id], key=lambda r: r["id"])
                    if any(climbs_to_fissure(o) for p, o in materialized_graph.predicate_objects(by_name[r["id"]])
                           if isinstance(o, URIRef) and str(p).startswith(str(S)))), None)
    assert fissure, "no fissure report in the chosen pipe section"
    first.pop(fissure["code"], None)
    picked = ([fissure] + list(first.values()))[:max_reports]  # readability cap

    g = Graph()
    for t in sdco_graph:
        g.add(t)
    uris = {r["id"]: by_name[r["id"]] for r in picked}
    for r in picked:
        for p, o in m150_data.predicate_objects(uris[r["id"]]):
            g.add((uris[r["id"]], p, o))
    classify_individuals(g)

    nodes, edges = {}, []

    def node(nid, label, ns, kind, iri):
        nodes.setdefault(nid, {"id": nid, "label": label, "ns": ns, "kind": kind, "iri": iri})

    def edge(a, b, label):
        edges.append({"source": a, "target": b, "label": label})

    asset_uri = next(a for a in m150_data.subjects(RDF.type, M.PipeSection) if local_name(a) == asset_id)
    node(asset_id, "Haltung " + asset_id.rsplit("_", 1)[-1], "m150", "individual", str(asset_uri))
    insp_id = picked[0]["inspectionId"]
    insp_uri = next(i for i in m150_data.subjects(M.inspects, asset_uri) if local_name(i) == insp_id)
    node(insp_id, "Inspection " + (inspections[insp_id]["date"] or "")[:10], "m150", "individual", str(insp_uri))
    edge(insp_id, asset_id, "m150:inspects")
    # Optional "inspection details" fan: real triples of the inspection individual (whitelist; nothing invented).
    # Objects get their rdfs:label as a literal one hop further out.
    for pname in ("hasInspectionDateTime", "hasInspector", "hasCompany", "hasSiteManagement", "hasClient",
                  "hasCameraSystemUsed"):
        for o in m150_data.objects(insp_uri, M[pname]):
            if isinstance(o, Literal):
                lid = "lit:insp:" + pname
                node(lid, f'"{str(o)}"', "m150", "literal", "")
                edge(insp_id, lid, "m150:" + pname)
            else:
                node(local_name(o), local_name(o).replace("Beispiel_", "", 1), "m150", "individual", str(o))
                edge(insp_id, local_name(o), "m150:" + pname)
                for lab in m150_data.objects(o, RDFS.label):
                    node("lit:" + local_name(o), f'"{lab}"', "m150", "literal", "")
                    edge(local_name(o), "lit:" + local_name(o), "rdfs:label")
    detail_ids = set(nodes) - {asset_id, insp_id}
    for nid in detail_ids:
        nodes[nid]["detail"] = True
    # Optional "Haltung details" fan: whitelisted real triples of the pipe section. Code-list individuals become one
    # node labelled by their rdfs:label in both languages (the page picks one); IRI stays in the side panel.
    # hasYearOfConstruction is whitelisted but absent from the sample data, so it only appears if present.
    def bilabels(u):
        by = {}
        for gr in (m150_data, m150_tbox):
            for lab in gr.objects(u, RDFS.label):
                by.setdefault(lab.language or "", str(lab))
        if not by:
            return None
        plain = by.get("") or next(iter(by.values()))
        return {"de": by.get("de", plain), "en": by.get("en", plain)}

    hal_ids = set()
    for pname in ("hasMaterial", "hasSewerUsage", "hasSewerType", "hasDistrictName", "hasStreetName",
                  "hasYearOfConstruction", "hasPipeSectionLength", "hasPipeSectionProfileType",
                  "hasPipeSectionProfileWidth", "hasPipeSectionProfileHeight", "hasOperationalStatus"):
        for o in m150_data.objects(asset_uri, M[pname]):
            if isinstance(o, Literal):
                nid = "lit:hal:" + pname
                node(nid, f'"{str(o)}"', "m150", "literal", "")
            else:
                nid = local_name(o)
                labs = bilabels(o)
                assert labs, f"{nid} has no rdfs:label"
                node(nid, labs["en"], "m150", "individual", str(o))
                nodes[nid]["labels"] = labs
            hal_ids.add(nid)
            edge(asset_id, nid, "m150:" + pname)
    for nid in hal_ids:
        nodes[nid]["detail"] = nodes[nid]["hd"] = True
    detail_ids |= hal_ids
    for r in picked:
        ru = uris[r["id"]]
        rid = r["id"]
        node(rid, "Report " + r["code"], "m150", "individual", str(ru))
        edge(rid, insp_id, "m150:isChildOf")
        lit = "lit:" + r["code"]
        node(lit, f'"{r["code"]}"', "m150", "literal", "")
        edge(rid, lit, "m150:hasConditionCode")
        for c in sorted(g.objects(ru, RDF.type), key=str):
            if isinstance(c, URIRef) and str(c).startswith(str(S)):
                node(local_name(c), ":" + local_name(c), "sdco", "class", str(c))
                edge(rid, local_name(c), "rdf:type")
        for p, o in sorted(materialized_graph.predicate_objects(ru), key=lambda t: (str(t[0]), str(t[1]))):
            if not str(p).startswith(str(S)):
                continue
            cur = o
            node(local_name(o), ":" + local_name(o), "sdco", "class", str(o))
            edge(rid, local_name(o), "sdco:" + local_name(p))
            steps = max_depth
            if climbs_to_fissure(o):  # let the fissure path reach :Fissure, nothing else gets longer
                steps = 8
            for _ in range(steps):
                parents = sorted(edges_sc.get(cur, ()), key=str)
                if not parents:
                    break
                par = next((x for x in parents if climbs_to_fissure(x)), parents[0]) if steps > max_depth else parents[0]
                node(local_name(par), ":" + local_name(par), "sdco", "class", str(par))
                edge(local_name(cur), local_name(par), "rdfs:subClassOf")
                cur = par
                if steps > max_depth and cur == S.Fissure:
                    break
    seen, uniq = set(), []
    for e in edges:
        k = (e["source"], e["target"], e["label"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    for e in uniq:
        if e["source"] in detail_ids or e["target"] in detail_ids:
            e["detail"] = True
            if e["source"] == asset_id and e["target"] in hal_ids:
                e["hd"] = True
    assert len(detail_ids - hal_ids) >= 4, "inspection details fan is nearly empty"
    hal_labels = {nodes[i].get("labels", {}).get("en", nodes[i]["label"]) for i in hal_ids}
    assert len(hal_ids) >= 5 and {"Concrete", "Ortsmitte"} <= hal_labels, f"Haltung details fan incomplete: {sorted(hal_labels)}"
    out = {"asset": asset_id, "nodes": list(nodes.values()), "edges": uniq}
    ids = set(nodes)
    assert 20 <= len(nodes) <= 90, f"linked graph has {len(nodes)} nodes, expected 20-60"
    assert uniq and all(e["source"] in ids and e["target"] in ids for e in uniq), "dangling edge in linked graph"
    assert "Fissure" in ids, "linked graph must show the chain up to sdco:Fissure"
    assert {n["ns"] for n in nodes.values()} >= {"m150", "sdco"}, "linked graph must cross the namespace boundary"
    return out


def build_stats(sdco_graph, m150_data, m150_tbox, materialized_graph, reports, codes, assets,
                 inspections, materialized_triples, materialized_subjects) -> dict:
    dates = sorted(i["date"] for i in inspections.values() if i["date"])
    return {
        "tripleCounts": {
            "SDCO.rdf": len(sdco_graph),
            "m150-onto-parsed-dwa.rdf": len(m150_data),
            "m150-onto.rdf": len(m150_tbox),
            "SDCO-dwa-parsed_materialized.rdf": len(materialized_graph),
        },
        "axioms": {
            "equivalentClass": len(list(sdco_graph.subjects(OWL.equivalentClass, None))),
            "namedClasses": len([s for s in sdco_graph.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)]),
            "someValuesFrom": len(list(sdco_graph.subjects(OWL.someValuesFrom, None))),
            "allDisjointClasses": len(list(sdco_graph.subjects(RDF.type, OWL.AllDisjointClasses))),
            "objectProperties": len([s for s in sdco_graph.subjects(RDF.type, OWL.ObjectProperty) if isinstance(s, URIRef)]),
        },
        "reportCount": len(reports),
        "codeCount": sum(1 for c in codes if c["count"] > 0),
        "totalCodeCount": len(codes),
        "pipeSectionCount": sum(1 for a in assets if a["type"] == "PipeSection"),
        "nodeCount": sum(1 for a in assets if a["type"] == "Node"),
        "inspectionCount": len(inspections),
        "materializedTripleCount": materialized_triples,
        "materializedSubjectCount": materialized_subjects,
        "inspectionDateRange": {"min": dates[0] if dates else None, "max": dates[-1] if dates else None},
    }


def inject(output: dict, out_path: Path) -> int:
    # Inject the data into the page template -> a single self-contained index.html.
    # A published artifact runs under a CSP that blocks fetching a separate .json,
    # so the data has to be inlined rather than loaded.
    template_path = out_path.parent / "template.html"
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
        payload = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
        # `</script>` inside a <script> block would end it early; escape defensively.
        payload = payload.replace("</", "<\\/")
        n_keys = check_i18n(template, [q["id"] for q in output["queries"]])
        print(f"[ok] i18n: {n_keys} keys in both languages")
        if PLACEHOLDER not in template:
            raise SystemExit(f"{template_path.name} is missing the {PLACEHOLDER} placeholder")
        page_path = out_path.parent / "index.html"
        page_path.write_text(template.replace(PLACEHOLDER, payload), encoding="utf-8")
        print(f"[done] wrote {page_path} ({page_path.stat().st_size} bytes)")
    else:
        print(f"[skip] no {template_path.name}; wrote data only")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdco", default=str(REPO_ROOT / "SDCO.rdf"))
    parser.add_argument("--m150-data", default=str(M150_REPO / "m150-onto-parsed-dwa.rdf"))
    parser.add_argument("--m150-tbox", default=str(M150_REPO / "m150-onto.rdf"))
    parser.add_argument("--materialized", default=str(REPO_ROOT / "derived" / "SDCO-dwa-parsed_materialized.rdf"))
    parser.add_argument("--output", default=str(REPO_ROOT / "docs" / "sdco_data.json"))
    parser.add_argument("--template-only", action="store_true",
                        help="skip extraction (slow); re-inject the existing --output JSON into the template")
    args = parser.parse_args()
    if args.template_only:
        out_path = Path(args.output)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        return inject(data, out_path)

    sdco_graph = parse_any(Path(args.sdco))
    m150_data = parse_any(Path(args.m150_data))
    m150_tbox = parse_any(Path(args.m150_tbox))
    materialized_graph = parse_any(Path(args.materialized))

    merged = Graph()
    for g in (sdco_graph, m150_data, m150_tbox, materialized_graph):
        for t in g:
            merged.add(t)

    inspections = build_inspections(merged)
    reports = build_reports(merged, m150_data, materialized_graph, inspections)
    codes = build_codes(merged, reports)

    edges, desc = build_class_edges(merged)
    ancestors = make_ancestors_fn(edges)
    report_ancestor_sets = build_report_ancestor_sets(reports, ancestors)
    observation_tree = build_observation_tree(desc, report_ancestor_sets)
    reference_tree = build_reference_tree(codes)

    assets = build_assets(merged, m150_data, reports)
    queries = build_queries(merged, reports)

    materialized_triples = sum(1 for _, p, _ in materialized_graph if str(p).startswith(str(S)))
    materialized_subjects = len({s for s, p, _ in materialized_graph if str(p).startswith(str(S))})

    stats = build_stats(sdco_graph, m150_data, m150_tbox, materialized_graph, reports, codes, assets,
                         inspections, materialized_triples, materialized_subjects)

    assert len(reports) == 96, f"expected 96 reports, got {len(reports)}"
    used_codes = sum(1 for c in codes if c["count"] > 0)
    assert used_codes == 23, f"expected 23 used codes, got {used_codes}"
    assert len(codes) == 80, f"expected 80 codes defined in the ontology, got {len(codes)}"
    assert materialized_triples == 141, f"expected 141 materialized triples, got {materialized_triples}"
    for q in queries:
        assert q["resultCount"] >= 1, f"query {q['id']} returned zero rows"

    m150 = build_m150(M150_REPO, sdco_graph, m150_data, m150_tbox, materialized_graph, reports, codes)
    m150["fissure"] = build_fissure_comparison(queries, reports, m150["featured"]["fissureSubclasses"])

    linked_graph = build_linked_graph(sdco_graph, m150_data, m150_tbox, materialized_graph, reports, inspections)

    benefits = build_benefits(sdco_graph, m150_data, m150, codes, linked_graph, materialized_triples, materialized_subjects)

    explorer = build_explorer(sdco_graph, m150_tbox, codes, edges)

    output = {
        "explorer": explorer,
        "m150": m150,
        "benefits": benefits,
        "linkedGraph": linked_graph,
        "reports": reports,
        "codes": codes,
        "taxonomy": {"observation": observation_tree, "reference": reference_tree},
        "assets": assets,
        "queries": queries,
        "stats": stats,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[done] wrote {out_path} ({out_path.stat().st_size} bytes)")
    print(f"reports={len(reports)} codes={len(codes)} assets={len(assets)} inspections={len(inspections)}")
    print(f"materialized: {materialized_triples} triples, {materialized_subjects} distinct subjects")
    print("queries: " + ", ".join(f"{q['id']}={q['resultCount']}" for q in queries))
    print(f"inspection date range: {stats['inspectionDateRange']}")

    return inject(output, out_path)


if __name__ == "__main__":
    sys.exit(main())
