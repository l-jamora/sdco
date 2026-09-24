# Changelog

## [0.1.2] - 2026-09-24

### Ontology

- Fixed `:BAF2_E` (pipe surface damage, cause "Not Evident"): its restriction used `hasPipeFabricDamage` instead of `hasDamageCause`, unlike its siblings `BAF2_A–D/Z` and the node twin `DAF2_E`.
- Fixed `:DBH2_A/B/C/Z` (node vermin location): their restrictions used `hasNodeOperationDamage` instead of `hasLocation`, unlike the pipe twins `BBH2_*`.
- Added `rdfs:range :Defect` to `:hasDamage` (inherited by all six pipe/node damage sub-properties). Since `Defect` is disjoint with `Cause`/`Location`, a non-damage value on a damage property now makes the class unsatisfiable, so the reasoner catches this defect class.
- `owl:versionIRI`/`owl:versionInfo` bumped to `0.1.2` (0.1.1 had left them at `0.1.0`).

### Tests

- New Tier 1 test `test_sibling_characterizations_share_one_property`: every sibling in a characterization family must use the same object property. Fails on the pre-fix `BAF2_E`; the `DBH2_*` case is caught by the new range via Tier 2's `test_ontology_is_coherent`.

### Docs

- `docs/design-specs/SDCO_Testing_Suite_Design_Spec.md`: new test documented, §4c on the two defects and both guards, Tier 1 test count corrected.
- `CLAUDE.md`: refreshed stale numbers (materialization output 141 triples / ~16 s, 509 `someValuesFrom` restrictions, 839 named classes — the old 1,228 had counted anonymous intersection classes too).
- `scripts/README.md`: fixed explainer output paths (`docs/index.html`, `docs/sdco_data.json`).
- Explainer (`docs/index.html`, `docs/sdco_data.json`) rebuilt against the current ontology. It had been stale since before the 0.1.0 fixes (still showed `Slit` instead of `Silt`, the old `BBE` Obstacle meaning and old counts); now in sync.

## [0.1.1] - 2026-09-17

### Ontology

- Added an `rdfs:comment` to the `Reference` superclass in `SDCO.rdf` explaining its role, with a concrete example (`DAB`/`DAB2_A`).

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
