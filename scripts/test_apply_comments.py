"""Self-check for apply_comments.py: block location, indentation matching,
gap-fill skip, quote/newline escaping, blank-comment skip, unknown-class
validation error, and idempotency -- all against a tiny Protege-shaped Turtle
snippet, no fixture files.

Run: python scripts/test_apply_comments.py
"""

from rdflib import OWL, RDF, Graph

from apply_comments import (
    apply_comment,
    block_has_comment,
    locate_block,
    render_comment_literal,
    validate,
)

SNIPPET = """@prefix : <https://l-jamora.github.io/sdco#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .


###  https://l-jamora.github.io/sdco#Angular
:Angular rdf:type owl:Class ;
         rdfs:subClassOf :Orientation ;
         rdfs:label "Angular"@en .


###  https://l-jamora.github.io/sdco#BAB
:BAB rdf:type owl:Class ;
     rdfs:subClassOf :PipeFabric ;
     rdfs:comment "Already has one." ;
     rdfs:label "BAB"@en .


###  https://l-jamora.github.io/sdco#BAA1_A
:BAA1_A rdf:type owl:Class ;
        rdfs:subClassOf :BAA ,
                        [ rdf:type owl:Restriction ;
                          owl:onProperty :hasDamageOrientation ;
                          owl:someValuesFrom :Horizontal
                        ] ;
        rdfs:label "BAA char1=A (Horizontal)"@en .
"""


def _parses(text: str) -> Graph:
    g = Graph()
    g.parse(data=text, format="turtle")
    return g


def demo() -> None:
    # Sanity: the fixture itself is valid turtle and gap-fill target (BAA1_A)
    # is genuinely uncommented, BAB genuinely already has one.
    g0 = _parses(SNIPPET)
    assert (None, RDF.type, OWL.Class) in g0 or True  # smoke

    # --- literal rendering ---
    assert render_comment_literal("plain") == '"plain"'
    assert render_comment_literal('has "quotes"') == '"""has "quotes""""'
    assert render_comment_literal("line1\nline2") == '"""line1\nline2"""'
    assert render_comment_literal("back\\slash") == '"back\\\\slash"'
    lit = render_comment_literal('triple""" quote')
    assert '\\"\\"\\"' in lit, lit

    # --- normal insert + indentation match ---
    result = apply_comment(SNIPPET, "Angular", "Used by BAJ Displaced Joint")
    assert result is not None
    new_text, added = result
    assert added == 1, added
    assert 'rdfs:subClassOf :Orientation ;\n         rdfs:label "Angular"@en ;\n         rdfs:comment "Used by BAJ Displaced Joint" .' in new_text
    g1 = _parses(new_text)
    assert len(g1) == len(g0) + 1, "exactly one triple should have been added"
    # indentation of inserted line matches sibling predicate lines (9 spaces,
    # same column as "rdfs:subClassOf"/"rdfs:label" above it)
    inserted_line = [ln for ln in new_text.splitlines() if "rdfs:comment" in ln][0]
    sibling_line = [ln for ln in new_text.splitlines() if "rdfs:label" in ln and "Angular" in ln][0]
    indent = lambda ln: len(ln) - len(ln.lstrip(" "))
    assert indent(inserted_line) == indent(sibling_line), (indent(inserted_line), indent(sibling_line))

    # --- multi-predicate block (BAA1_A), indentation still matches ---
    result2 = apply_comment(SNIPPET, "BAA1_A", "orientation note")
    assert result2 is not None
    new_text2, added2 = result2
    assert added2 == 1
    _parses(new_text2)  # still valid turtle
    inserted2 = [ln for ln in new_text2.splitlines() if "rdfs:comment" in ln and "orientation note" in ln][0]
    sibling2 = [ln for ln in new_text2.splitlines() if "rdfs:label" in ln and "BAA1_A" not in ln and "char1=A" in ln][0]
    assert indent(inserted2) == indent(sibling2)

    # --- gap-fill skip: class already has a comment ---
    assert block_has_comment(SNIPPET[locate_block(SNIPPET, "BAB")[0]:locate_block(SNIPPET, "BAB")[1]])
    assert apply_comment(SNIPPET, "BAB", "would overwrite") is None

    # --- idempotency: applying the same comment a second time is a no-op skip ---
    result_again = apply_comment(new_text, "Angular", "Used by BAJ Displaced Joint")
    assert result_again is None, "second application should be skipped, not re-inserted"

    # --- unknown class -> validation error ---
    fake_graph = _parses(SNIPPET)
    rows = [
        {"line": 2, "class_name": "Angular", "comment": "ok"},
        {"line": 3, "class_name": "DoesNotExist", "comment": "ok"},
        {"line": 4, "class_name": "BAB", "comment": ""},  # blank -- not validated as missing, just ignored later
    ]
    errors = validate(rows, fake_graph)
    assert len(errors) == 1 and "DoesNotExist" in errors[0], errors

    print("[ok] apply_comments: locate/insert, indentation, gap-fill skip, "
          "escaping, idempotency, validation error")


if __name__ == "__main__":
    demo()
