# Changelog

## [0.1.0] - 2026-09-16

First release. Everything below happened on `dev-classes_approach`, merged into `main` for this tag.

### Ontology

- Full DIN EN 13508-2 damage-code class taxonomy (pipe fabric, pipe operation, inventory, and node-side D-family codes), modeled with `owl:equivalentClass` matching literal condition-report codes and `someValuesFrom` restrictions linking classes into their hierarchy.
- Removed punning (classes that were also individuals) in favor of the `someValuesFrom` approach, so subsumption reasoning works without punned terms.
- Node-side codes (NodeFabric, NodeOperation, NodeInventory, NodeOther) added with full class hierarchies, characterizations, and disjointness axioms.
- `rdfs:label` generated for every SDCO class; `rdfs:comment` added to 164 Observation classes documenting DIN-grounded semantics.
- Namespace fixed to `https://l-jamora.github.io/sdco#` for native SDCO terms, `m150-onto#` for imported data-exchange terms.
- Several defect fixes: `:BBC` equivalentClass literal, `BCA1_*` missing disjointness, `:BBE` main code pointing at the wrong Obstacle class, `:InspectionComplete` char2 A/C ambiguity, `Slit`→`Silt` spelling correction, BCB point-repair characterization wiring.

### Tooling

- `scripts/materialize_object_properties.py`: turns existential `someValuesFrom` restrictions into literal, queryable triples. Fast SPARQL forward-chaining path by default; `--reason` (HermiT via owlready2) kept as a correctness oracle.
- `scripts/generate_labels.py`, `scripts/generate_node_codes.py`, `scripts/apply_comments.py`, `scripts/build_explainer.py`, `scripts/make_benchmark_dataset.py`.
- Interactive HTML explainer (`docs/index.html`) built from live ontology + materialized data.

### Tests

- `tests/test_structure.py`, `tests/test_classification.py` — Tier 1, rdflib-only structural checks (~2s).
- `tests/test_reasoning.py` — Tier 2, opt-in HermiT reasoning checks (`pytest -m reasoner`), needs a JDK and the sibling `m150-onto` repo.

### Docs

- `docs/design-specs/` — design specs and refactor/handover writeups (punning removal, testing suite, node code generator, explainer).
