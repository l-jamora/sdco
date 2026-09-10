"""Self-check for generate_node_codes.py: rendering shapes, validation
failures, the auto-declare path, disjoint grouping, idempotent skipping, and
footer-insertion -- run against tiny in-memory graphs/rows, no fixture files.

Run: python scripts/test_generate_node_codes.py
"""

import tempfile
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph

from generate_node_codes import (
    FOOTER_MARKER,
    NODE,
    apply_defaults,
    build_output,
    group_disjoints,
    insert_before_footer,
    render_base_class,
    render_char_class,
    validate,
)


def _row(**kwargs) -> dict:
    base = {
        "class_name": "",
        "category": "",
        "parent_code": "",
        "characterization_dim": "",
        "char_value": "",
        "object_property": "",
        "filler_class": "",
        "comment": "",
    }
    base.update(kwargs)
    return base


def build_graph() -> Graph:
    g = Graph()
    for cat in ("NodeFabric", "NodeInventory", "NodeOperation", "NodeOther"):
        g.add((NODE[cat], RDF.type, OWL.Class))
    g.add((NODE.hasNodeFabricDamage, RDF.type, OWL.ObjectProperty))
    g.add((NODE.hasDamageOrientation, RDF.type, OWL.ObjectProperty))
    # pre-existing base class: exercises idempotent skip + parent resolution via graph
    g.add((NODE.DAB, RDF.type, OWL.Class))
    g.add((NODE.DAB, RDFS.subClassOf, NODE.NodeFabric))
    return g


def demo() -> None:
    g = build_graph()

    # 1. base-row triple shape
    base_row = _row(
        class_name="DEA", category="NodeOperation",
        object_property="hasNodeOperationDamage", filler_class="Roots",
    )
    out = render_base_class(base_row)
    assert 'owl:hasValue "DEA"' in out, "base row missing hasConditionCode value"
    assert "owl:onProperty :hasNodeOperationDamage" in out, "base row missing object property"
    assert "owl:someValuesFrom :Roots" in out, "base row missing filler class"
    assert "rdfs:subClassOf :NodeOperation" in out, "base row missing category superclass"

    # 2. char-row intersectionOf shape (dim 1)
    char_row_1 = _row(
        class_name="DEA_A", parent_code="DEA",
        characterization_dim="1", char_value="A",
        object_property="hasNodeOperationDamage", filler_class="TapRoot",
    )
    out1 = render_char_class(char_row_1)
    assert "owl:intersectionOf ( :DEA" in out1, "char row missing parent intersection"
    # hasCharacterization1/2 are m150-onto terms; SDCO.rdf declares no m150-onto:
    # prefix, so the generator (and the committed D-family classes) use the full IRI.
    assert (
        "owl:onProperty <https://l-jamora.github.io/m150-onto#hasCharacterization1>" in out1
    ), "char row missing hasCharacterization1"
    assert 'owl:hasValue "A"' in out1, "char row missing char_value"
    assert "owl:someValuesFrom :TapRoot" in out1, "char row missing filler class"

    # 3. char-2 uses a different property correctly
    char_row_2 = _row(
        class_name="DEA2_A", parent_code="DEA",
        characterization_dim="2", char_value="A",
        object_property="hasDamageOrientation", filler_class="Vertical",
    )
    out2 = render_char_class(char_row_2)
    assert (
        "owl:onProperty <https://l-jamora.github.io/m150-onto#hasCharacterization2>" in out2
    ), "char2 row missing hasCharacterization2"
    assert "owl:someValuesFrom :Vertical" in out2, "char2 row missing its own filler class"
    assert "hasNodeOperationDamage" not in out2, "char2 row must not leak char1's object property"

    # 4. missing/undeclared object_property -> hard validation failure
    bogus_rows = [_row(
        class_name="DXX", category="NodeOther",
        object_property="hasBogusThing", filler_class="Something",
    )]
    errors = validate(bogus_rows, g)
    assert any("hasBogusThing" in e for e in errors), "undeclared, non-matching property should fail validation"

    # 5. auto-declare path for hasNodeOperationDamage (not in graph, matches pattern)
    auto_rows = [base_row]
    assert validate(auto_rows, g) == [], "auto-declarable property should pass validation"
    out5 = build_output(auto_rows, g)
    assert "hasNodeOperationDamage rdf:type owl:ObjectProperty" in out5, "auto-declare block missing"
    assert "rdfs:subPropertyOf :hasNodeDamage" in out5, "auto-declare should subProperty hasNodeDamage"

    # 6. unresolvable parent_code -> hard validation failure
    orphan_rows = [_row(
        class_name="ZZZ_A", parent_code="NoSuchParent",
        characterization_dim="1", char_value="A",
        object_property="hasNodeFabricDamage", filler_class="Foo",
    )]
    errors6 = validate(orphan_rows, g)
    assert any("NoSuchParent" in e for e in errors6), "unresolvable parent_code should fail validation"

    # 7. disjoint block only for 2+ members
    pair_rows = [
        _row(class_name="DFA", category="NodeOther",
             object_property="hasNodeFabricDamage", filler_class="Foo"),
        _row(class_name="DFB", category="NodeOther",
             object_property="hasNodeFabricDamage", filler_class="Bar"),
    ]
    groups = group_disjoints(pair_rows)
    assert any(set(m) == {"DFA", "DFB"} for m in groups), "2-member category should form a disjoint group"

    singleton_rows = [_row(class_name="DFC", category="NodeInventory",
                            object_property="hasNodeFabricDamage", filler_class="Foo")]
    assert group_disjoints(singleton_rows) == [], "singleton category should not form a disjoint group"

    # 8. idempotent skip-if-exists, still counted for disjoint grouping
    idempotent_rows = [
        _row(class_name="DAB", category="NodeFabric",
             object_property="hasNodeFabricDamage", filler_class="Fissure"),
        _row(class_name="DAG", category="NodeFabric",
             object_property="hasNodeFabricDamage", filler_class="SomethingElse"),
    ]
    out8 = build_output(idempotent_rows, g)
    assert ":DAB rdf:type owl:Class ;" not in out8, "pre-existing class must not be re-declared"
    assert ":DAG rdf:type owl:Class ;" in out8, "new sibling class must be declared"
    assert "AllDisjointClasses" in out8 and ":DAB" in out8 and ":DAG" in out8, (
        "pre-existing class must still be folded into the disjoint group"
    )

    # 9. footer insertion lands new text before the marker, not after
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".rdf", delete=False, encoding="utf-8")
    tmp.write(f"existing content\n\n\n{FOOTER_MARKER}\n")
    tmp.close()
    tmp_path = Path(tmp.name)
    try:
        insert_before_footer(tmp_path, "NEW BLOCK HERE")
        result = tmp_path.read_text(encoding="utf-8")
        assert result.index("NEW BLOCK HERE") < result.index(FOOTER_MARKER), (
            "new content must be inserted before the footer marker"
        )
    finally:
        tmp_path.unlink()

    # 10. apply_defaults: base row object_property defaults from category
    d1 = [_row(class_name="DGA", category="NodeInventory", filler_class="Foo")]
    apply_defaults(d1, g)
    assert d1[0]["object_property"] == "hasNodeInventoryFeature", (
        "base row object_property should default from category"
    )

    # 11. apply_defaults: single-dim code -> class_name derived without a digit,
    # and its object_property (first/only row in the group) is NOT guessed
    d2 = [
        _row(category="NodeFabric", class_name="DGB", filler_class="Foo"),
        _row(parent_code="DGB", characterization_dim="1", char_value="A", filler_class="Bar"),
    ]
    apply_defaults(d2, g)
    assert d2[1]["class_name"] == "DGB_A", "single-dim char row should derive name without a digit"
    assert d2[1]["object_property"] == "", (
        "first row of a char group must not silently inherit a guessed property"
    )

    # 12. apply_defaults: two-dim code -> class_name derived WITH a digit, and
    # a 2nd row in the same group carries forward the 1st row's object_property
    d3 = [
        _row(category="NodeFabric", class_name="DGC", filler_class="Foo"),
        _row(parent_code="DGC", characterization_dim="1", char_value="A",
             object_property="hasNodeFabricDamage", filler_class="Bar"),
        _row(parent_code="DGC", characterization_dim="1", char_value="B", filler_class="Baz"),
        _row(parent_code="DGC", characterization_dim="2", char_value="A",
             object_property="hasDamageOrientation", filler_class="Qux"),
    ]
    apply_defaults(d3, g)
    assert d3[1]["class_name"] == "DGC1_A", "two-dim char row should derive name with its dim digit"
    assert d3[2]["class_name"] == "DGC1_B", "2nd row of a group should also get its dim digit"
    assert d3[2]["object_property"] == "hasNodeFabricDamage", (
        "2nd+ row of a char group should carry forward the group's object_property"
    )
    assert d3[3]["class_name"] == "DGC2_A", "dim-2 row should derive name with digit 2"
    assert d3[3]["object_property"] == "hasDamageOrientation", (
        "dim-2 group must not leak dim-1's carried-forward property"
    )

    print("[ok] generate_node_codes: 12 behaviors verified")


if __name__ == "__main__":
    demo()
