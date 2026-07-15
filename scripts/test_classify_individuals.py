"""Self-check for classify_individuals()'s forward-chaining rules: one simple
hasValue pattern, one intersection pattern, run against a tiny toy graph.

Run: python scripts/test_classify_individuals.py
"""

from rdflib import RDF, Graph, Literal, Namespace, OWL, URIRef

from materialize_object_properties import classify_individuals

EX = Namespace("http://example.org/ex#")


def demo() -> None:
    g = Graph()
    g.bind("ex", EX)

    # Simple: Code ≡ hasConditionCode value "BAB"
    restr = URIRef("http://example.org/ex#restr1")
    g.add((EX.Code, OWL.equivalentClass, restr))
    g.add((restr, RDF.type, OWL.Restriction))
    g.add((restr, OWL.onProperty, EX.hasConditionCode))
    g.add((restr, OWL.hasValue, Literal("BAB")))
    g.add((EX.ind1, EX.hasConditionCode, Literal("BAB")))

    # Intersection: SubCode ≡ (Code AND hasCharacterization1 value "A")
    restr2 = URIRef("http://example.org/ex#restr2")
    inter = URIRef("http://example.org/ex#inter")
    lst1 = URIRef("http://example.org/ex#lst1")
    lst2 = URIRef("http://example.org/ex#lst2")
    g.add((EX.SubCode, OWL.equivalentClass, inter))
    g.add((inter, OWL.intersectionOf, lst1))
    g.add((lst1, RDF.first, EX.Code))
    g.add((lst1, RDF.rest, lst2))
    g.add((lst2, RDF.first, restr2))
    g.add((lst2, RDF.rest, RDF.nil))
    g.add((restr2, RDF.type, OWL.Restriction))
    g.add((restr2, OWL.onProperty, EX.hasCharacterization1))
    g.add((restr2, OWL.hasValue, Literal("A")))
    g.add((EX.ind1, EX.hasCharacterization1, Literal("A")))

    # ind2 matches the simple rule only (no hasCharacterization1)
    g.add((EX.ind2, EX.hasConditionCode, Literal("BAB")))

    classify_individuals(g)

    assert (EX.ind1, RDF.type, EX.Code) in g, "simple rule failed"
    assert (EX.ind1, RDF.type, EX.SubCode) in g, "intersection rule failed"
    assert (EX.ind2, RDF.type, EX.Code) in g, "simple rule failed for ind2"
    assert (EX.ind2, RDF.type, EX.SubCode) not in g, "ind2 must not match intersection rule"

    print("[ok] classify_individuals: simple + intersection rules verified")


if __name__ == "__main__":
    demo()
