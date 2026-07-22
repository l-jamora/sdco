"""Session-scoped fixtures for the SDCO test suite.

Reuses parsing/classification/reasoning helpers from
scripts/materialize_object_properties.py rather than reimplementing them --
pythonpath = ["scripts"] in pyproject.toml makes that a bare import.

Test individuals come from tests/fixtures/test_individuals.rdf, a small
hand-authored (Protege, RDF/XML) file -- not generated. See that file's
header for its shape.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from rdflib import RDF, Graph, URIRef

from materialize_object_properties import (
    classify_individuals,
    convert_to_owlxml,
    load_catalog,
    parse_any,
    run_hermit,
    stage_imports,
)

REPO = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO / "tests" / "fixtures" / "test_individuals.rdf"

CONDITION_REPORT = URIRef("https://l-jamora.github.io/m150-onto#ConditionReport")
SDCO_NS = "https://l-jamora.github.io/sdco#"

PLAIN_QUERY = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?cls ?prop ?val WHERE {
  ?cls owl:equivalentClass ?restr .
  ?restr a owl:Restriction ; owl:onProperty ?prop ; owl:hasValue ?val .
}
"""

INTERSECTION_QUERY = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?cls ?base ?prop ?val WHERE {
  ?cls owl:equivalentClass ?inter .
  ?inter owl:intersectionOf ?list .
  ?list rdf:rest*/rdf:first ?base .
  ?list rdf:rest*/rdf:first ?restr .
  ?restr a owl:Restriction ; owl:onProperty ?prop ; owl:hasValue ?val .
  FILTER (?base != ?restr)
}
"""


def get_defined_classes(graph: Graph) -> list[dict]:
    """One record per owl:equivalentClass definition: {cls, kind, base, prop, val}.
    kind is 'plain' (base=None) or 'intersection'. Single SPARQL pass -- callers
    should cache the result (see defined_classes fixture) rather than re-querying."""
    records = []
    for cls, prop, val in graph.query(PLAIN_QUERY):
        records.append({"cls": cls, "kind": "plain", "base": None, "prop": prop, "val": val})
    for cls, base, prop, val in graph.query(INTERSECTION_QUERY):
        records.append({"cls": cls, "kind": "intersection", "base": base, "prop": prop, "val": val})
    return records


def load_fixture_individuals() -> tuple[Graph, dict[URIRef, set[URIRef]]]:
    """Parses tests/fixtures/test_individuals.rdf, pulls off each individual's
    asserted damage-code rdf:type(s) (sdco# namespace only) as `expected`, and
    returns a graph with those types stripped so classify_individuals() has to
    re-derive them from the property values instead of finding them already
    there. Non-damage-code types (ConditionReport, Node, PipeSection,
    owl:NamedIndividual, ...) are left in the graph untouched."""
    raw = parse_any(FIXTURE_PATH)
    expected: dict[URIRef, set[URIRef]] = {}
    stripped = Graph()
    for prefix, ns in raw.namespaces():
        stripped.bind(prefix, ns)

    for s, p, o in raw:
        if p == RDF.type and str(o).startswith(SDCO_NS):
            expected.setdefault(s, set()).add(o)
        else:
            stripped.add((s, p, o))

    return stripped, expected


@pytest.fixture(scope="session")
def sdco_graph() -> Graph:
    return parse_any(REPO / "SDCO.rdf")


@pytest.fixture(scope="session")
def defined_classes(sdco_graph: Graph) -> list[dict]:
    return get_defined_classes(sdco_graph)


@pytest.fixture(scope="session")
def classified_graph(sdco_graph: Graph):
    """(graph, expected) -- sdco_graph plus the fixture individuals (types
    stripped), classified via the real classify_individuals(). Session-scoped:
    built once, asserted against by every classification test."""
    data, expected = load_fixture_individuals()
    g = Graph()
    for triple in sdco_graph:
        g.add(triple)
    for triple in data:
        g.add(triple)
    classify_individuals(g)
    return g, expected


@pytest.fixture(scope="session")
def reasoner_world(sdco_graph: Graph):
    """Loads SDCO + fixture individuals + m150-onto into owlready2/HermiT via
    the sibling repo, one shared run for every Tier 2 assertion. Skips cleanly
    if the sibling repo, owlready2, or a JDK isn't available. Yields
    (onto, expected) -- expected is the same fixture-derived mapping
    classified_graph uses, so test_reasoning can assert HermiT agrees with it."""
    m150_rdf = REPO.parent / "m150-onto" / "m150-onto.rdf"
    if not m150_rdf.exists():
        pytest.skip(f"sibling m150-onto repo not found at {m150_rdf}")
    if shutil.which("java") is None:
        pytest.skip("java not found on PATH")
    pytest.importorskip("owlready2")

    catalog_map = load_catalog(REPO / "catalog-v001.xml")
    tmp_dir = Path(tempfile.mkdtemp(prefix="sdco_test_reasoner_"))
    try:
        data, expected = load_fixture_individuals()
        fixture_ontology = URIRef("https://l-jamora.github.io/sdco/test_individuals")
        merged = Graph()
        for triple in sdco_graph:
            merged.add(triple)
        for triple in data:
            # Skip the fixture's own owl:Ontology declaration -- its
            # owl:imports (e.g. the materialized/test_individuals derived
            # file) aren't in catalog-v001.xml and would make owlready2 try
            # to fetch them over the network. sdco_graph already supplies
            # the real owl:imports (m150-onto) needed for reasoning.
            if triple[0] == fixture_ontology:
                continue
            merged.add(triple)
        merged_src = tmp_dir / "SDCO_with_fixture.ttl"
        merged.serialize(destination=str(merged_src), format="turtle")

        owl_path = tmp_dir / "SDCO.owl"
        source_graph = convert_to_owlxml(merged_src, owl_path)
        stage_imports(source_graph, catalog_map, tmp_dir, visited=set())
        onto = run_hermit(tmp_dir, owl_path.name)
        yield onto, expected
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
