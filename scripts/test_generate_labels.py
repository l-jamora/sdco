"""Self-check for generate_labels.py: the four compose() branches, the
mangling guard, block-strip idempotency, and the fill-gaps-never-overwrite
skip -- all against a tiny in-memory graph, no fixture files.

Run: python scripts/test_generate_labels.py
"""

from rdflib import OWL, RDF, RDFS, BNode, Graph, Literal, Namespace
from rdflib.collection import Collection

from generate_labels import BEGIN_MARKER, build_block, compose, strip_block

S = Namespace("https://l-jamora.github.io/sdco#")
M = Namespace("https://l-jamora.github.io/m150-onto#")


def _restriction(g, prop, *, has_value=None, some_values_from=None):
    b = BNode()
    g.add((b, RDF.type, OWL.Restriction))
    g.add((b, OWL.onProperty, prop))
    if has_value is not None:
        g.add((b, OWL.hasValue, Literal(has_value)))
    if some_values_from is not None:
        g.add((b, OWL.someValuesFrom, some_values_from))
    return b


def _fixture() -> Graph:
    g = Graph()

    # Branch 1: plain hasConditionCode restriction, with a someValuesFrom filler.
    g.add((S.BAB, RDF.type, OWL.Class))
    g.add((S.BAB, OWL.equivalentClass,
           _restriction(g, M.hasConditionCode, has_value="BAB")))
    g.add((S.BAB, RDFS.subClassOf,
           _restriction(g, S.hasPipeFabricDamage, some_values_from=S.Fissure)))

    # Branch 1 with no filler -> bare code.
    g.add((S.BXX, RDF.type, OWL.Class))
    g.add((S.BXX, OWL.equivalentClass,
           _restriction(g, M.hasConditionCode, has_value="BXX")))

    # Branch 2: intersectionOf ( :BAB [char2=A] ), filler :Longitudinal.
    inter = BNode()
    lst = BNode()
    Collection(g, lst, [S.BAB, _restriction(g, M.hasCharacterization2, has_value="A")])
    g.add((inter, RDF.type, OWL.Class))
    g.add((inter, OWL.intersectionOf, lst))
    g.add((S.BAB2_A, RDF.type, OWL.Class))
    g.add((S.BAB2_A, OWL.equivalentClass, inter))
    g.add((S.BAB2_A, RDFS.subClassOf,
           _restriction(g, S.hasDamageOrientation, some_values_from=S.Longitudinal)))

    # Branch 2 for a char1 class whose name carries no digit (:BDD_A style).
    inter2 = BNode()
    lst2 = BNode()
    Collection(g, lst2, [S.BDD, _restriction(g, M.hasCharacterization1, has_value="A")])
    g.add((inter2, RDF.type, OWL.Class))
    g.add((inter2, OWL.intersectionOf, lst2))
    g.add((S.BDD_A, RDF.type, OWL.Class))
    g.add((S.BDD_A, OWL.equivalentClass, inter2))

    # Branch 3: CamelCase taxonomy term.
    g.add((S.CrackFissure, RDF.type, OWL.Class))
    g.add((S.CrackFissure, RDFS.subClassOf, S.Fissure))

    # Branch 4: underscore name -> verbatim.
    g.add((S.Schlauchliner_BAA_A, RDF.type, OWL.Class))
    g.add((S.Schlauchliner_BAA_A, RDFS.subClassOf, S.Schlauchliner))

    # Already labeled -> must be skipped by build_block.
    g.add((S.Deformation, RDF.type, OWL.Class))
    g.add((S.Deformation, RDFS.label, Literal("hand authored", lang="en")))

    return g


def demo() -> None:
    g = _fixture()

    assert compose(g, S.BAB) == "BAB (Fissure)", compose(g, S.BAB)
    assert compose(g, S.BXX) == "BXX", compose(g, S.BXX)
    assert compose(g, S.BAB2_A) == "BAB char2=A (Longitudinal)", compose(g, S.BAB2_A)
    assert compose(g, S.BDD_A) == "BDD char1=A", compose(g, S.BDD_A)
    assert compose(g, S.CrackFissure) == "Crack Fissure", compose(g, S.CrackFissure)
    assert compose(g, S.Schlauchliner_BAA_A) == "Schlauchliner_BAA_A", compose(g, S.Schlauchliner_BAA_A)

    # Mangling guard: names that humanize() would wreck never reach branch 3.
    assert not compose(g, S.BAB).startswith("B A B"), "3-letter code was mangled by humanize()"
    assert "_ " not in compose(g, S.Schlauchliner_BAA_A), "underscore name was mangled"

    block, n_labeled, n_skipped = build_block(g)
    assert n_skipped == 1, n_skipped
    assert n_labeled == 6, n_labeled
    assert ":Deformation " not in block, "already-labeled class leaked into the block"
    # Sorted by local name.
    names = [ln.split(" ", 1)[0] for ln in block.splitlines()[1:-1]]
    assert names == sorted(names), names

    # The generate cycle (strip old block, splice fresh one before the footer)
    # is idempotent: running it twice yields byte-identical text.
    base = "@prefix : <x> .\n\nbody line\n\n\n### footer\n"

    def splice(text: str, blk: str) -> str:
        idx = text.rfind("### footer")
        return text[:idx].rstrip("\n") + "\n\n\n" + blk + "\n\n\n" + text[idx:]

    once = splice(strip_block(base), block)
    twice = splice(strip_block(once), block)
    assert once == twice, "generate cycle is not idempotent"
    assert BEGIN_MARKER not in strip_block(once), "strip left the marker behind"

    print("[ok] generate_labels: 4 branches, mangling guard, skip, strip idempotency")


if __name__ == "__main__":
    demo()
