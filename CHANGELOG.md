# Changelog

## [Unreleased]

### Docs

- Explainer: new fifth tab `Explore` / `Erkunden` (`#explore`, `#explore/<code>`) with a searchable code browser (definition, characterisation letters, class chain, matching m150-onto property and DWA XML element, IRIs), a sentence-shaped classifier ("Code X with characterisation 1 Y ...") that evaluates the two `equivalentClass` pattern shapes of `classify_individuals()` in JS and explains the match in plain words (letters valid only for other codes are flagged; no severity is shown because SDCO defines none), and a schematic inline-SVG sewer plan with nine synthetic example observations (station plus clock position, coloured by code family, keyboard accessible). New `build_explorer()` in `build_explainer.py` exports the data as `explorer` in `sdco_data.json` and asserts that the JS-mirror logic equals `classify_individuals()` for all presets and demo observations; the demo network and presets live in `scripts/ontology/explorer_demo.json` (synthetic, validated against `SDCO.rdf`). No external library is used.
- Explainer, linked-data graph: third switch "Haltung details" / "Haltungsdetails" fans out 10 whitelisted real triples of `Beispiel_PipeSection_1204013` (material, usage, sewer type, district, street, length, profile type/width/height, operational status) in a column left of the Haltung; code-list values are single nodes labelled with their `rdfs:label` in the page language. `hasYearOfConstruction` is whitelisted but absent from the sample data, so it is not shown.
- Explainer revamp (`docs/template.html`, `scripts/ontology/build_explainer.py`): the page now explains both m150-onto and SDCO in three tabs (Overview, m150-onto, SDCO; URL hash `#overview` / `#m150` / `#sdco`), with an EN/DE toggle, a white light-only theme and replayable animated scenes (XML to triples, graph, literal lifting into the taxonomy, reasoner classification and materialization, "all fissures" versus code lists, query explorer).
- `build_explainer.py` additionally extracts m150-onto statistics and one real condition report both as DWA-M 150 XML and as RDF (re-deriving its classification and materialization and asserting they match the materialized file), and asserts EN/DE i18n key parity at build time.
- New Overview scene "Linked data: two vocabularies, one graph": a draggable force-layout node-edge graph (hover, click for triples, pin/release, reset) of one pipe section, its inspection, reports, SDCO classes and materialized triples. Data from `build_linked_graph()` in `build_explainer.py`, bilingual.
- Explainer: new Overview scene "Why not just better XML software?" (argued prose plus an animated vendor-tools-versus-shared-layer schematic) and a fourth `Benefits` / `Mehrwert` tab (`#benefits`) with six replayable XML-today-versus-ontologies cards (queryability, reasoning, inference, consistency checking, integration, vendor/version independence), each tagged "demonstrated on this page" or "possible / future". New `build_benefits()` extraction with assertions; the consistency card is a real co-occurrence check (see next entry). The Overview contrast list shrank from six to three rows (query, inference and linked-records rows moved into the cards).
- Explainer, Benefits tab: the "Consistency checking" card now argues that DIN EN 13508-2 ties the allowed characterisation letters (`HZ014`/`HZ015`, `hasCharacterization1/2`) to the main code, which per-field checks do not express. New `build_consistency()` derives the allowed letters per code and dimension from the `equivalentClass` intersection patterns of `SDCO.rdf`, asserts that the letters of every dimension run without a gap (the one exception, `BCA` char1, is reported as unverified and left out), runs a SPARQL check after `classify_individuals()` on the 96 example reports (flags a letter that matches no subclass; a missing letter is never flagged, because SDCO does not encode which characterisations are mandatory) and asserts that one constructed `BAB` report with a letter valid only for other codes is flagged while a valid one is not. The card states that the XSD named in the example file is not in the m150-onto repository and makes no claim about what it enforces. The former disjointness example moved into the Integration card as one "possible / future" point.
- `docs/design-specs/SDCO_Explainer_Design_Spec.md` and `scripts/README.md` updated.

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
