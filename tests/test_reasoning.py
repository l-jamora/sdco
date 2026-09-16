"""Tier 2: HermiT via owlready2. Opt-in (`pytest -m reasoner`), minutes.

Three assertions off one shared reasoner run (reasoner_world), plus exactly two
negative tests -- each needs its own poisoned World(), so each gets a fresh one
rather than reusing the shared session fixture (an inconsistent ontology
poisons every later reasoner call in the same process).
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from rdflib import RDF, Namespace, URIRef

from materialize_object_properties import (
    convert_to_owlxml,
    load_catalog,
    parse_any,
    stage_imports,
)

pytestmark = pytest.mark.reasoner

REPO = Path(__file__).resolve().parent.parent
M150 = Namespace("https://l-jamora.github.io/m150-onto#")


def onto_defined_type_closure(onto_iri: str, defined_universe: set) -> set:
    """HermiT's inferred named-class closure for one individual, restricted to
    the equivalentClass-defined damage-code universe -- HermiT also infers every
    ancestor via plain rdfs:subClassOf (PipeFabric, Reference, ...), which the
    fast-path classify_individuals() never touches, so comparing on the raw sets
    would never agree even when correct."""
    import owlready2

    entity = owlready2.default_world[onto_iri]
    assert entity is not None, f"fixture individual not found in reasoner world: {onto_iri}"

    types = set()
    for c in entity.INDIRECT_is_a:
        if isinstance(c, owlready2.Restriction):
            continue
        if isinstance(c, owlready2.ThingClass):
            types.add(URIRef(c.iri))
    return types & defined_universe


def test_ontology_is_consistent(reasoner_world):
    # reasoner_world's fixture setup already called sync_reasoner(); an
    # inconsistent ontology raises OwlReadyInconsistentOntologyError there,
    # failing the fixture before any test body runs. Reaching this line is
    # itself the assertion.
    onto, _ = reasoner_world
    assert onto is not None


def test_ontology_is_coherent(reasoner_world):
    import owlready2

    inconsistent = list(owlready2.default_world.inconsistent_classes())
    assert inconsistent == [], f"unsatisfiable classes: {inconsistent}"


def test_hermit_agrees_with_fast_path(reasoner_world):
    onto, expected = reasoner_world
    defined_universe = set().union(*expected.values())

    mismatches = []
    for ind_uri, expected_types in expected.items():
        actual_types = onto_defined_type_closure(str(ind_uri), defined_universe)
        if actual_types != expected_types:
            mismatches.append((ind_uri, expected_types, actual_types))

    assert not mismatches, f"HermiT vs fast-path mismatches (showing up to 10): {mismatches[:10]}"


def _assert_poisoned_pair_is_inconsistent(a: URIRef, b: URIRef, tag: str) -> None:
    """Assert individual typed into both a and b in a fresh World makes the
    ontology inconsistent."""
    import owlready2

    catalog_map = load_catalog(REPO / "catalog-v001.xml")
    graph = parse_any(REPO / "SDCO.rdf")
    graph.add((M150.poison_ind, RDF.type, a))
    graph.add((M150.poison_ind, RDF.type, b))

    tmp_dir = Path(tempfile.mkdtemp(prefix=f"sdco_test_reasoner_{tag}_"))
    try:
        src = tmp_dir / "poisoned.ttl"
        graph.serialize(destination=str(src), format="turtle")
        owl_path = tmp_dir / "poisoned.owl"
        source_graph = convert_to_owlxml(src, owl_path)
        stage_imports(source_graph, catalog_map, tmp_dir, visited=set())

        world = owlready2.World()
        owlready2.onto_path.append(str(tmp_dir))
        onto = world.get_ontology(owl_path.name).load()
        with pytest.raises(owlready2.OwlReadyInconsistentOntologyError):
            with onto:
                owlready2.sync_reasoner(world, infer_property_values=True)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_inline_disjoint_pair_is_inconsistent(sdco_graph):
    a, b = next(iter(sdco_graph.query(
        "PREFIX owl: <http://www.w3.org/2002/07/owl#> "
        "SELECT ?a ?b WHERE { ?a owl:disjointWith ?b . } LIMIT 1"
    )))
    _assert_poisoned_pair_is_inconsistent(a, b, "neg1")


def test_all_disjoint_classes_group_member_is_inconsistent(sdco_graph):
    group = next(iter(sdco_graph.query(
        "PREFIX owl: <http://www.w3.org/2002/07/owl#> "
        "SELECT ?grp WHERE { ?grp a owl:AllDisjointClasses . } LIMIT 1"
    )))[0]
    members = [
        row[0] for row in sdco_graph.query(
            "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
            "PREFIX owl: <http://www.w3.org/2002/07/owl#> "
            f"SELECT ?m WHERE {{ {group.n3()} owl:members/rdf:rest*/rdf:first ?m . }}"
        )
    ]
    _assert_poisoned_pair_is_inconsistent(members[0], members[1], "neg2")
