"""Extract real data from the SDCO ontology and its DWA-M 150 example dataset
into docs/explainer/sdco_data.json, for a later phase to inject into a
self-contained HTML explainer page. Every number on that page is measured
here -- nothing hand-typed.

Read-only on all ontology files. Reuses parse_any() from
materialize_object_properties.py (same directory, importable directly since
python adds a script's own directory to sys.path[0]) rather than
reimplementing RDF/XML-vs-turtle sniffing or the xsd:string literal
normalization that join between m150 data and SDCO relies on.

    python scripts/build_explainer.py
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef

sys.path.insert(0, str(Path(__file__).resolve().parent))
from materialize_object_properties import parse_any  # noqa: E402

# Token in docs/explainer/template.html replaced by the extracted JSON at build time.
PLACEHOLDER = "__SDCO_DATA__"

REPO_ROOT = Path(__file__).resolve().parent.parent
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
        label = g.value(val, RDFS.label)
        return str(label) if label is not None else local_name(val)
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
        for p, o in merged.predicate_objects(report_uri):
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
        comment = merged.value(cls, RDFS.comment)
        codes.append({
            "code": code,
            "count": count,
            "sdcoClass": local_name(cls),
            "comment": str(comment) if comment is not None else None,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdco", default=str(REPO_ROOT / "SDCO.rdf"))
    parser.add_argument("--m150-data", default=str(M150_REPO / "m150-onto-parsed-dwa.rdf"))
    parser.add_argument("--m150-tbox", default=str(M150_REPO / "m150-onto.rdf"))
    parser.add_argument("--materialized", default=str(REPO_ROOT / "derived" / "SDCO-dwa-parsed_materialized.rdf"))
    parser.add_argument("--output", default=str(REPO_ROOT / "docs" / "explainer" / "sdco_data.json"))
    args = parser.parse_args()

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

    output = {
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

    # Inject the data into the page template -> a single self-contained index.html.
    # A published artifact runs under a CSP that blocks fetching a separate .json,
    # so the data has to be inlined rather than loaded.
    template_path = out_path.parent / "template.html"
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
        payload = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
        # `</script>` inside a <script> block would end it early; escape defensively.
        payload = payload.replace("</", "<\\/")
        if PLACEHOLDER not in template:
            raise SystemExit(f"{template_path.name} is missing the {PLACEHOLDER} placeholder")
        page_path = out_path.parent / "index.html"
        page_path.write_text(template.replace(PLACEHOLDER, payload), encoding="utf-8")
        print(f"[done] wrote {page_path} ({page_path.stat().st_size} bytes)")
    else:
        print(f"[skip] no {template_path.name}; wrote data only")

    return 0


if __name__ == "__main__":
    sys.exit(main())
