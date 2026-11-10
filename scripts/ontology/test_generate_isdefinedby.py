"""Self-check for generate_isdefinedby.py: main-code and characterization
paths read from axioms (not names), din_clause fallback for non-code
classes, derivation from referring code classes (table learned from the
clauses), unknown-clause-class guard, classes with neither skipped, existing
annotations kept, block-strip idempotency -- against a tiny in-memory graph.

Run: python scripts/ontology/test_generate_isdefinedby.py
"""

from rdflib import OWL, RDF, RDFS, BNode, Graph, Literal, Namespace
from rdflib.collection import Collection

from generate_isdefinedby import BEGIN_MARKER, build_block, code_path, strip_block

S = Namespace("https://l-jamora.github.io/sdco#")
M = Namespace("https://l-jamora.github.io/m150-onto#")


def _code(g, cls, code):
    b = BNode()
    g.add((b, RDF.type, OWL.Restriction))
    g.add((b, OWL.onProperty, M.hasConditionCode))
    g.add((b, OWL.hasValue, Literal(code)))
    g.add((cls, RDF.type, OWL.Class))
    g.add((cls, OWL.equivalentClass, b))


def _char(g, cls, base, n, v):
    r, inter, lst = BNode(), BNode(), BNode()
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, M[f"hasCharacterization{n}"]))
    g.add((r, OWL.hasValue, Literal(v)))
    Collection(g, lst, [base, r])
    g.add((inter, OWL.intersectionOf, lst))
    g.add((cls, RDF.type, OWL.Class))
    g.add((cls, OWL.equivalentClass, inter))


def main():
    g = Graph()
    _code(g, S.BAB, "BAB")
    _char(g, S.Oddly_Named, S.BAB, 2, "A")  # path must come from axioms, not the name
    _code(g, S.BAC, "BAC")
    g.add((S.BAC, RDFS.isDefinedBy, Literal("hand-written")))
    g.add((S.CrackFissure, RDF.type, OWL.Class))  # filler class: takes the din_clause
    g.add((S.Vertical, RDF.type, OWL.Class))  # neither code nor clause: no annotation
    r = BNode()  # Oddly_Named (BAB char2 A) points at :Longitudinal -> derived
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, S.hasDamageOrientation))
    g.add((r, OWL.someValuesFrom, S.Longitudinal))
    g.add((S.Oddly_Named, RDFS.subClassOf, r))
    g.add((S.Longitudinal, RDF.type, OWL.Class))

    assert code_path(g, S.BAB) == "main code BAB"
    assert code_path(g, S.Oddly_Named) == "main code BAB, characterization 2 = A"
    assert code_path(g, S.CrackFissure) is None

    clauses = {"CrackFissure": "Table 4, BAB char1 (B)", "BAB": "ignored: axiom wins"}
    block, added, skipped = build_block(g, clauses)
    assert (added, skipped) == (4, 1), (added, skipped)
    assert ':Longitudinal rdfs:isDefinedBy "DIN EN 13508-2, Table 4, BAB char2 (A)" .' in block
    assert ':BAB rdfs:isDefinedBy "DIN EN 13508-2, main code BAB" .' in block
    assert ':CrackFissure rdfs:isDefinedBy "DIN EN 13508-2, Table 4, BAB char1 (B)" .' in block
    assert ':Oddly_Named rdfs:isDefinedBy "DIN EN 13508-2, main code BAB, characterization 2 = A" .' in block
    assert "Vertical" not in block and ":BAC " not in block

    try:
        build_block(g, {"Typo": "Table 4"})
        raise AssertionError("unknown class in din_clause rows must raise")
    except ValueError:
        pass

    text = "head\n\n\n" + block + "\n\n\nfooter\n"
    assert BEGIN_MARKER not in strip_block(text)
    assert strip_block(strip_block(text)) == strip_block(text)
    print("ok")


if __name__ == "__main__":
    main()
