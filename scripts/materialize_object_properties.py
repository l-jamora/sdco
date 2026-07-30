"""Materialize literal object-property triples from an SDCO source ontology's
someValuesFrom restrictions.

SDCO ontologies model damage codes via owl:equivalentClass (matching literal
condition-report codes) plus rdfs:subClassOf restrictions using owl:someValuesFrom
on object properties. someValuesFrom is an existential restriction: HermiT correctly
classifies individuals into the right damage-code classes, but never invents a
concrete filler individual, so no literal triple like ":ind :hasPipeFabricDamage
:CrackFissure" is ever produced.

By default this script realizes each individual's named damage-code classes via a bounded
SPARQL forward-chaining pass (classify_individuals: every damage code's owl:equivalentClass
axiom is a plain hasValue restriction or a one-level intersection of one, so no DL reasoner
is actually needed to classify them). It then runs a SPARQL CONSTRUCT query that walks from
those named classes through the (already-asserted, untouched) someValuesFrom restrictions to
emit literal triples -- keeping only the most-specific filler per (individual, property) pair.
Output goes to a separate derived file; the source ontology file is never modified (checked
via hash before/after).

Pass --reason to use full HermiT DL realization (via owlready2) instead -- much slower
(minutes, driven by taxonomy expressivity rather than individual count), kept only as a
correctness oracle to validate the fast path against.

Use --source to pick which ontology file to materialize (e.g. SDCO.rdf or
SDCO-dwa-parsed.rdf). owl:imports in the source are resolved via the OASIS XML catalog
(catalog-v001.xml next to the source, or --catalog) so imported ontologies that live
outside this repo (e.g. m150-onto.rdf) can be found without a network fetch.
"""

import argparse
import hashlib
import shutil
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

REPO_ROOT = Path(__file__).resolve().parent.parent
SDCO = Namespace("https://l-jamora.github.io/sdco#")

# NOTE: does *not* require `?ind a owl:NamedIndividual` -- owlready2's RDF/XML
# export drops that explicit triple for individuals on round-trip, which made
# this query silently match nothing against the reasoner-exported graph. The
# type-walk below already anchors ?ind to real individuals (only they carry a
# damage-code rdf:type reachable to a Restriction).
CONSTRUCT_QUERY = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>

CONSTRUCT { ?ind ?prop ?filler . }
WHERE {
  ?ind rdf:type/rdfs:subClassOf* ?restr .
  ?restr a owl:Restriction ; owl:onProperty ?prop ; owl:someValuesFrom ?filler .

  FILTER NOT EXISTS {
    ?ind rdf:type/rdfs:subClassOf* ?restr2 .
    ?restr2 a owl:Restriction ; owl:onProperty ?prop ; owl:someValuesFrom ?filler2 .
    ?filler2 rdfs:subClassOf+ ?filler .
    FILTER (?filler2 != ?filler)
  }
}
"""

# Forward-chaining classification: replaces HermiT for the common case where
# every damage-code class is defined by owl:equivalentClass as either a plain
# hasValue restriction, or an intersection of a base code class with one more
# hasValue restriction. Both patterns are simple pattern matches -- no DL
# realization needed. Two passes: first *_SIMPLE (data property -> value),
# then *_INTERSECTION (relies on rdf:type from pass 1 already being in the
# graph).
CLASSIFY_SIMPLE_UPDATE = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>

INSERT { ?ind rdf:type ?cls . }
WHERE {
  ?cls owl:equivalentClass ?restr .
  ?restr a owl:Restriction ; owl:onProperty ?prop ; owl:hasValue ?val .
  ?ind ?prop ?val .
}
"""

CLASSIFY_INTERSECTION_UPDATE = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>

INSERT { ?ind rdf:type ?cls . }
WHERE {
  ?cls owl:equivalentClass ?inter .
  ?inter owl:intersectionOf ?list .
  ?list rdf:rest*/rdf:first ?base .
  ?list rdf:rest*/rdf:first ?restr .
  ?restr a owl:Restriction ; owl:onProperty ?prop ; owl:hasValue ?val .
  FILTER (?base != ?restr)
  ?ind rdf:type ?base .
  ?ind ?prop ?val .
}
"""


def classify_individuals(g: Graph) -> None:
    """Forward-chaining replacement for HermiT realization: adds rdf:type
    triples for every equivalentClass hasValue / intersection pattern,
    in-place. Bounded fixpoint (2 passes: simple then intersection, since
    intersection rules read the base type a simple rule just added)."""
    g.update(CLASSIFY_SIMPLE_UPDATE)
    g.update(CLASSIFY_INTERSECTION_UPDATE)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_any(path: Path) -> Graph:
    """Parse an ontology file whose serialization (turtle vs RDF/XML) may not match
    its .rdf extension -- some files in this project are Protege turtle exports
    saved with a .rdf extension, others are genuine RDF/XML."""
    g = Graph()
    try:
        g.parse(str(path), format="xml")
    except Exception:
        g = Graph()
        g.parse(str(path), format="turtle")
    # RDF 1.1: "x" and "x"^^xsd:string are the same term, but rdflib treats them as
    # distinct, so an xsd:string-typed hasConditionCode never joins against SDCO's
    # plain-literal owl:hasValue restrictions. Normalize on load.
    for s, p, o in list(g.triples((None, None, None))):
        if isinstance(o, Literal) and o.datatype == XSD.string:
            g.remove((s, p, o))
            g.add((s, p, Literal(str(o), lang=o.language)))
    return g


def convert_to_owlxml(src: Path, dst_owl: Path) -> Graph:
    g = parse_any(src)
    g.serialize(destination=str(dst_owl), format="xml")
    return g


def file_uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    path = unquote(parsed.path)
    if len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]  # strip leading slash before a Windows drive letter
    return Path(path)


def load_catalog(catalog_path: Path) -> dict:
    import xml.etree.ElementTree as ET

    if not catalog_path.exists():
        return {}
    ns = {"c": "urn:oasis:names:tc:entity:xmlns:xml:catalog"}
    root = ET.parse(catalog_path).getroot()
    mapping = {}
    for uri_el in root.findall("c:uri", ns):
        name, uri = uri_el.get("name"), uri_el.get("uri")
        if name and uri and name not in mapping:
            mapping[name] = file_uri_to_path(uri)
    return mapping


def stage_imports(graph: Graph, catalog_map: dict, tmp_dir: Path, visited: set) -> None:
    """Copy owl:imports targets into tmp_dir under a filename matching their IRI's
    last path segment, so owlready2's own import resolution finds them locally
    instead of trying to fetch them over the network. Recurses into each staged
    ontology's own imports."""
    for imp in graph.objects(None, OWL.imports):
        imp_iri = str(imp)
        if imp_iri in visited:
            continue
        visited.add(imp_iri)

        local_file = catalog_map.get(imp_iri)
        if not local_file or not local_file.exists():
            print(
                f"[warn] cannot resolve import <{imp_iri}> via catalog; "
                "owlready2 will try to fetch it over the network",
                file=sys.stderr,
            )
            continue

        basename = imp_iri.rstrip("/#").rsplit("/", 1)[-1]
        dst = tmp_dir / f"{basename}.owl"
        imp_graph = parse_any(local_file)
        imp_graph.serialize(destination=str(dst), format="xml")

        stage_imports(imp_graph, catalog_map, tmp_dir, visited)


def run_hermit(tmp_dir: Path, owl_filename: str):
    import owlready2

    owlready2.onto_path.append(str(tmp_dir))
    onto = owlready2.get_ontology(owl_filename).load()
    with onto:
        owlready2.sync_reasoner(infer_property_values=True)
    inconsistent = list(owlready2.default_world.inconsistent_classes())
    if inconsistent:
        raise RuntimeError(f"Ontology inconsistent after reasoning: {inconsistent}")
    return onto


def export_and_reload(onto, dst_owl: Path) -> Graph:
    onto.save(file=str(dst_owl), format="rdfxml")
    g = Graph()
    g.parse(str(dst_owl), format="xml")
    return g


def build_merged_graph(source: Path, catalog_map: dict) -> Graph:
    """Parse source plus every owl:imports target (recursively, via the
    catalog) into one merged rdflib Graph -- the input classify_individuals
    and the CONSTRUCT query need, without invoking owlready2/HermiT at all."""
    merged = parse_any(source)
    visited: set = set()

    def recurse(g: Graph) -> None:
        for imp in list(g.objects(None, OWL.imports)):
            imp_iri = str(imp)
            if imp_iri in visited:
                continue
            visited.add(imp_iri)
            local_file = catalog_map.get(imp_iri)
            if not local_file or not local_file.exists():
                print(
                    f"[warn] cannot resolve import <{imp_iri}> via catalog; skipping",
                    file=sys.stderr,
                )
                continue
            imp_graph = parse_any(local_file)
            for t in imp_graph:
                merged.add(t)
            recurse(imp_graph)

    recurse(merged)
    return merged


def named_types_persisted(source_graph: Graph, reasoned_graph: Graph) -> bool:
    """True if HermiT's inferred rdf:type triples for named individuals survived
    the owlready2 export/reload round-trip: checks generically for any inferred
    rdf:type triple (on a named individual) that wasn't already asserted in the
    source."""
    asserted = {(s, o) for s, _, o in source_graph.triples((None, RDF.type, None)) if isinstance(o, URIRef)}
    reasoned = {(s, o) for s, _, o in reasoned_graph.triples((None, RDF.type, None)) if isinstance(o, URIRef)}
    return len(reasoned - asserted) > 0


def build_fallback_graph(onto, src: Path) -> Graph:
    import owlready2

    g = parse_any(src)

    for ind in onto.individuals():
        ind_uri = URIRef(ind.iri)
        for t in ind.INDIRECT_is_a:
            if isinstance(t, owlready2.Restriction):
                continue
            if isinstance(t, owlready2.ThingClass):
                g.add((ind_uri, RDF.type, URIRef(t.iri)))
    return g


def warn_functional_property_conflicts(triples, source_graph: Graph) -> None:
    functional_props = {s for s in source_graph.subjects(RDF.type, OWL.FunctionalProperty)}

    by_ind_prop = {}
    for s, p, o in triples:
        if p in functional_props:
            by_ind_prop.setdefault((s, p), set()).add(o)

    for (ind, prop), fillers in by_ind_prop.items():
        if len(fillers) > 1:
            print(
                f"[warn] functional property {prop} has multiple fillers for {ind}: "
                f"{sorted(str(f) for f in fillers)}",
                file=sys.stderr,
            )


def build_output_graph(triples, source: Path, output_iri: str, reasoner_used: str) -> Graph:
    out = Graph()
    out.bind("", SDCO)
    out.bind("owl", OWL)

    output_node = URIRef(output_iri)
    out.add((output_node, RDF.type, OWL.Ontology))
    out.add((output_node, OWL.imports, URIRef("https://l-jamora.github.io/sdco")))
    out.add((output_node, RDFS.label, Literal("SDCO materialized object-property triples (DERIVED)")))
    out.add(
        (
            output_node,
            RDFS.comment,
            Literal(
                f"Auto-generated by scripts/materialize_object_properties.py via {reasoner_used} "
                "+ SPARQL CONSTRUCT. DO NOT HAND-EDIT -- regenerate with: "
                f"python scripts/materialize_object_properties.py --source {source.name}. "
                f"Source: {source.name}."
            ),
        )
    )

    for s, p, o in triples:
        out.add((s, p, o))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=str(REPO_ROOT / "SDCO.rdf"),
        help="Ontology file to materialize (e.g. SDCO.rdf or SDCO-dwa-parsed.rdf).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path. Defaults to derived/<source stem>_materialized.rdf",
    )
    parser.add_argument(
        "--format",
        choices=["xml", "turtle"],
        default="xml",
        help="Output serialization (default: xml / RDF-XML).",
    )
    parser.add_argument(
        "--catalog",
        default=None,
        help="OASIS XML catalog used to resolve owl:imports. Defaults to "
        "catalog-v001.xml next to --source.",
    )
    parser.add_argument("--tmp-dir", default=None)
    parser.add_argument("--keep-tmp", action="store_true")
    parser.add_argument("--force-fallback", action="store_true")
    parser.add_argument(
        "--reason",
        action="store_true",
        help="Use full HermiT DL realization instead of the default forward-chaining "
        "classifier. Much slower; kept as a correctness oracle to validate the fast path.",
    )
    args = parser.parse_args()

    source = Path(args.source)
    ext = "rdf" if args.format == "xml" else "ttl"
    output = Path(args.output) if args.output else REPO_ROOT / "derived" / f"{source.stem}_materialized.{ext}"
    output.parent.mkdir(parents=True, exist_ok=True)

    catalog_path = Path(args.catalog) if args.catalog else source.parent / "catalog-v001.xml"
    catalog_map = load_catalog(catalog_path)

    hash_before = sha256_of(source)

    tmp_dir = Path(args.tmp_dir) if args.tmp_dir else Path(tempfile.mkdtemp(prefix="sdco_materialize_"))
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.reason:
            t0 = time.perf_counter()
            owl_path = tmp_dir / f"{source.stem}.owl"
            source_graph = convert_to_owlxml(source, owl_path)
            stage_imports(source_graph, catalog_map, tmp_dir, visited=set())
            print(f"[phase] convert+stage: {time.perf_counter() - t0:.1f}s")

            t0 = time.perf_counter()
            onto = run_hermit(tmp_dir, owl_path.name)
            print(f"[phase] HermiT reason: {time.perf_counter() - t0:.1f}s")

            t0 = time.perf_counter()
            reasoned_owl_path = tmp_dir / "reasoned.owl"
            reasoned_graph = export_and_reload(onto, reasoned_owl_path)
            print(f"[phase] export+reload: {time.perf_counter() - t0:.1f}s")

            use_fallback = args.force_fallback or not named_types_persisted(source_graph, reasoned_graph)
            if use_fallback:
                print("[verify] path B (fallback: Python-synthesized named-class rdf:type triples)")
                work_graph = build_fallback_graph(onto, source)
            else:
                print("[verify] path A (reasoner-exported graph)")
                work_graph = reasoned_graph
        else:
            t0 = time.perf_counter()
            work_graph = build_merged_graph(source, catalog_map)
            classify_individuals(work_graph)
            print(f"[phase] classify: {time.perf_counter() - t0:.1f}s")
            source_graph = work_graph

        t0 = time.perf_counter()
        result = work_graph.query(CONSTRUCT_QUERY)
        triples = sorted(result, key=lambda t: (str(t[0]), str(t[1]), str(t[2])))
        print(f"[phase] construct: {time.perf_counter() - t0:.1f}s")

        warn_functional_property_conflicts(triples, source_graph)

        reasoner_used = "HermiT (owlready2)" if args.reason else "forward-chaining classify_individuals()"
        output_iri = f"https://l-jamora.github.io/sdco/materialized/{source.stem}"
        out = build_output_graph(triples, source, output_iri, reasoner_used)
        out.serialize(destination=str(output), format=args.format)

        print(f"[done] wrote {len(triples)} triples to {output}")
    finally:
        if not args.keep_tmp:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    hash_after = sha256_of(source)
    if hash_after != hash_before:
        raise RuntimeError(f"{source} was modified by this script -- this must never happen")

    return 0


if __name__ == "__main__":
    sys.exit(main())
