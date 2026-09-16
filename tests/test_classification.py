"""Tier 1 behavioral tests against the fixture round trip through the real
classify_individuals() and CONSTRUCT_QUERY -- no reasoner, seconds.
"""

from rdflib import RDF, XSD, Graph, Literal, Namespace

from materialize_object_properties import CONSTRUCT_QUERY, classify_individuals

M150 = Namespace("https://l-jamora.github.io/m150-onto#")
SDCO = Namespace("https://l-jamora.github.io/sdco#")


def test_every_code_classifies(classified_graph):
    g, expected = classified_graph
    failures = []
    for ind, expected_types in expected.items():
        actual_types = {t for t in g.objects(ind, RDF.type) if str(t).startswith(str(SDCO))}
        if actual_types != expected_types:
            failures.append((ind, expected_types, actual_types))
    assert not failures, f"classification mismatches (showing up to 10): {failures[:10]}"


def test_materialization_nonempty_and_correct(classified_graph):
    g, expected = classified_graph
    triples = list(g.query(CONSTRUCT_QUERY))
    assert len(triples) > 0, "CONSTRUCT_QUERY produced zero triples"

    bab_ind = next(ind for ind, types in expected.items() if types == {SDCO.BAB})
    assert (bab_ind, SDCO.hasPipeFabricDamage, SDCO.Fissure) in triples


def test_most_specific_filler_only(classified_graph):
    g, expected = classified_graph
    triples = list(g.query(CONSTRUCT_QUERY))

    bab1a_ind = next(ind for ind, types in expected.items() if types == {SDCO.BAB1_A, SDCO.BAB})
    fillers = {o for s, p, o in triples if s == bab1a_ind and p == SDCO.hasPipeFabricDamage}
    assert fillers == {SDCO.SurfaceCrackFissure}, (
        f"expected only the most-specific filler, got {fillers}"
    )


def test_typed_literal_does_not_classify(sdco_graph):
    g = Graph()
    for t in sdco_graph:
        g.add(t)
    ind = M150.synthetic_typed_literal_test
    g.add((ind, M150.hasConditionCode, Literal("BAB", datatype=XSD.string)))

    classify_individuals(g)

    assert (ind, RDF.type, SDCO.BAB) not in g


def test_classify_individuals_is_idempotent(classified_graph):
    g, _ = classified_graph
    before = len(g)
    classify_individuals(g)
    after = len(g)

    assert after == before, f"second classify_individuals() pass added {after - before} triples"
