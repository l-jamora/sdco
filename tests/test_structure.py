"""Tier 1 structural invariants over SDCO.rdf -- no reasoner, seconds.

Guards the two defects in docs/handover/plans/SDCO_Testing_Suite.md:
(1) classify_individuals()'s hardcoded 2-pass assumption that every
    owl:equivalentClass is plain-hasValue or one-level intersection.
(2) owl:AllDisjointClasses / owl:disjointWith groups mixing characterization
    dimensions (a report can legitimately be both char1 "A" and char2 "A").
"""

from rdflib import OWL, RDF, RDFS, Namespace, URIRef

M150 = Namespace("https://l-jamora.github.io/m150-onto#")
SDCO = Namespace("https://l-jamora.github.io/sdco#")

CATEGORY_ROOTS = [
    SDCO.PipeFabric,
    SDCO.PipeInventory,
    SDCO.PipeOperation,
    SDCO.PipeOther,
    SDCO.NodeFabric,
    SDCO.NodeInventory,
    SDCO.NodeOperation,
    SDCO.NodeOther,
]

ALL_EQUIVALENT_CLASS_QUERY = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?cls ?def WHERE { ?cls owl:equivalentClass ?def . }
"""

PLAIN_DEF_QUERY = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?cls ?def WHERE {
  ?cls owl:equivalentClass ?def .
  ?def a owl:Restriction ; owl:onProperty ?p ; owl:hasValue ?v .
}
"""

INTERSECTION_DEF_QUERY = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?cls ?def WHERE {
  ?cls owl:equivalentClass ?def .
  ?def owl:intersectionOf ?list .
  ?list rdf:rest*/rdf:first ?base .
  ?list rdf:rest*/rdf:first ?restr .
  ?restr a owl:Restriction ; owl:onProperty ?p ; owl:hasValue ?v .
  FILTER (?base != ?restr)
}
"""

ALL_DISJOINT_GROUPS_QUERY = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?grp ?member WHERE {
  ?grp a owl:AllDisjointClasses ;
       owl:members/rdf:rest*/rdf:first ?member .
}
"""

DISJOINT_WITH_QUERY = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?a ?b WHERE { ?a owl:disjointWith ?b . }
"""

SOME_VALUES_FROM_QUERY = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?prop ?filler WHERE {
  ?restr owl:onProperty ?prop ; owl:someValuesFrom ?filler .
}
"""


def disjoint_groups(sdco_graph):
    """List of member-sets: one per AllDisjointClasses block, plus one 2-member
    set per inline owl:disjointWith pair."""
    groups: dict = {}
    for grp, member in sdco_graph.query(ALL_DISJOINT_GROUPS_QUERY):
        groups.setdefault(grp, set()).add(member)
    result = list(groups.values())
    for a, b in sdco_graph.query(DISJOINT_WITH_QUERY):
        result.append({a, b})
    return result


def characterization_props(defined_classes):
    """cls -> its hasCharacterization* property, for intersection-defined
    classes keyed on one. Plain-defined base codes have none."""
    props = {}
    for rec in defined_classes:
        if rec["kind"] == "intersection" and str(rec["prop"]).startswith(str(M150.hasCharacterization)):
            props[rec["cls"]] = rec["prop"]
    return props


def test_equivalentclass_shape_is_exhaustive(sdco_graph):
    all_defs = set(sdco_graph.query(ALL_EQUIVALENT_CLASS_QUERY))
    plain_defs = set(sdco_graph.query(PLAIN_DEF_QUERY))
    intersection_defs = set(sdco_graph.query(INTERSECTION_DEF_QUERY))

    assert plain_defs & intersection_defs == set(), "a definition matched both shapes"
    assert all_defs == plain_defs | intersection_defs, (
        f"equivalentClass definitions outside plain/one-level-intersection shape: "
        f"{all_defs - (plain_defs | intersection_defs)}"
    )


def test_two_passes_suffice(defined_classes):
    intersection_defined = {rec["cls"] for rec in defined_classes if rec["kind"] == "intersection"}
    offenders = [
        rec["cls"] for rec in defined_classes
        if rec["kind"] == "intersection" and rec["base"] in intersection_defined
    ]
    assert not offenders, f"intersection classes whose base is itself intersection-defined: {offenders}"


def test_no_mixed_disjoint_groups(sdco_graph, defined_classes):
    char_prop = characterization_props(defined_classes)
    offenders = []
    for group in disjoint_groups(sdco_graph):
        props = {char_prop[m] for m in group if m in char_prop}
        if len(props) > 1:
            offenders.append((group, props))
    assert not offenders, f"disjoint groups mixing characterization dimensions: {offenders}"


def test_sibling_characterizations_are_pairwise_disjoint(sdco_graph, defined_classes):
    """Positive counterpart: within one (base, characterization property) family,
    every pair of sibling codes must be disjoint somewhere in the file."""
    disjoint_pairs = set()
    for group in disjoint_groups(sdco_graph):
        members = list(group)
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                disjoint_pairs.add(frozenset((a, b)))

    families: dict = {}
    for rec in defined_classes:
        if rec["kind"] == "intersection" and str(rec["prop"]).startswith(str(M150.hasCharacterization)):
            families.setdefault((rec["base"], rec["prop"]), set()).add(rec["cls"])

    missing = []
    for (base, prop), members in families.items():
        members = list(members)
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                if frozenset((a, b)) not in disjoint_pairs:
                    missing.append((base, prop, a, b))
    assert not missing, f"sibling characterization classes missing a disjointness axiom: {missing}"


def test_no_duplicate_definitions(defined_classes):
    seen: dict = {}
    dupes = []
    for rec in defined_classes:
        sig = (rec["kind"], rec["base"], rec["prop"], rec["val"])
        if sig in seen and seen[sig] != rec["cls"]:
            dupes.append((sig, seen[sig], rec["cls"]))
        seen.setdefault(sig, rec["cls"])
    assert not dupes, f"two classes share the same defining (base, prop, val) signature: {dupes}"


def test_codes_are_plain_literals(defined_classes):
    offenders = [
        rec["cls"] for rec in defined_classes
        if rec["val"].datatype is not None or rec["val"].language is not None
    ]
    assert not offenders, f"code definitions using a non-plain literal: {offenders}"


def test_no_dangling_object_property_references(sdco_graph):
    declared_object_props = set(sdco_graph.subjects(RDF.type, OWL.ObjectProperty))
    declared_classes = set(sdco_graph.subjects(RDF.type, OWL.Class))

    missing_props = set()
    missing_fillers = set()
    for prop, filler in sdco_graph.query(SOME_VALUES_FROM_QUERY):
        if prop not in declared_object_props:
            missing_props.add(prop)
        if filler not in declared_classes:
            missing_fillers.add(filler)

    assert not missing_props, f"someValuesFrom onProperty not declared as owl:ObjectProperty in-file: {missing_props}"
    assert not missing_fillers, f"someValuesFrom filler not declared as owl:Class in-file: {missing_fillers}"


def test_every_code_reaches_a_category(sdco_graph, defined_classes):
    defined = {rec["cls"] for rec in defined_classes}
    reachable = set()
    for root in CATEGORY_ROOTS:
        q = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?cls WHERE {{ ?cls rdfs:subClassOf* <{root}> . }}
        """
        reachable |= {row[0] for row in sdco_graph.query(q)}

    orphans = defined - reachable
    assert not orphans, f"defined classes with no path to a category root: {orphans}"


def test_every_sdco_class_has_a_label(sdco_graph):
    missing = sorted(
        str(s) for s in sdco_graph.subjects(RDF.type, OWL.Class)
        if isinstance(s, URIRef)
        and str(s).startswith(str(SDCO))
        and sdco_graph.value(s, RDFS.label) is None
    )
    assert not missing, f"SDCO classes with no rdfs:label ({len(missing)}): {missing[:10]}"
