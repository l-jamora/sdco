# SDCO — Agent Context

## Project Overview

SDCO (Sewer Damage Classification Ontology) is an OWL ontology that formalizes the **DIN EN 13508-2** standard — the European coding system for visual inspection of drains/sewers (damage codes, characterizations, inventory/observation codes; ~80 codes total). See `docs/DIN EN 13508-2 ENGLISH.pdf` for the source standard.

SDCO complements **[m150-onto](../m150-onto)** (`C:\Users\jluis\Repositories\ICOM\m150-onto`), a sibling ontology modeling the DWA M150 data-exchange format (pipe sections, nodes, inspection/condition reports as OWL individuals). Where m150-onto stores condition-report data as literal codes (`hasConditionCode "BAB"`), SDCO gives those codes semantic meaning as a damage-code class taxonomy (`:BAB` ⊑ `Fissure`, etc.) and imports m150-onto (`owl:imports` in `SDCO.rdf`, resolved locally via `catalog-v001.xml` pointing at `m150-onto.rdf`). Read `m150-onto/CLAUDE.md` before touching anything that crosses the two ontologies.

Full design narrative, competency questions, and SPARQL/SHACL examples: `docs/Sewer Damage Classification Ontology SDCO.md`.

## Key files

- `SDCO.rdf` — the ontology, repo root. **Turtle syntax despite the `.rdf` extension** — reasoning tools (owlready2/HermiT) need RDF/XML, so convert via `rdflib` first (see scripts).
- `SDCO-dwa-parsed.rdf` — SDCO merged with m150-onto-parsed example/test data (from m150-onto's ontoparser output).
- `catalog-v001.xml` — OASIS XML catalog resolving `owl:imports <https://l-jamora.github.io/m150-onto>` to the local `m150-onto/m150-onto.rdf` file, so imports work offline.
- `derived/` — generated output only (materialized triples, catalog copy for that context). Never hand-edit; regenerate via scripts.
- `docs/` — design doc, DIN EN 13508-2 PDFs, refactor/handover writeups. Read before large structural changes — several past decisions (punning removal, materialization approach) are recorded there with rationale, not just in commit messages.
- `scripts/` — one-off/repeatable maintenance scripts (Python, `rdflib`/`owlready2`), described below.

## Namespace state (fixed and committed)

`SDCO.rdf`'s `:` prefix and `@base` are `https://l-jamora.github.io/sdco#` — native SDCO terms (`:BAB`, `:PipeFabric`, `:hasPipeFabricDamage`, `:Fissure`, `:CrackFissure`, etc.) live there; `m150-onto`-defined terms (`ConditionReport`, `hasConditionCode`, `hasCharacterization1/2`, etc., referenced via the `m150-onto:` prefix) stay in `https://l-jamora.github.io/m150-onto#`. This is the two-prefix layout `docs/` describes.

History: commit `5c38450` ("Directly imports M150-Onto.rdf, as defined in catalog-v001.xml") had collapsed SDCO's own `:` prefix onto the m150-onto namespace and, as collateral damage, deleted ~243 `owl:equivalentClass` axioms. Both were fixed and committed: the axioms were restored (`scripts/obsolete/restore_equivalentclass_axioms.py`, now a no-op kept for history) and the namespace was moved back to `sdco#` in commits `d772723`/`d1afe80`. Currently 504 `owl:equivalentClass` definitions total — roughly doubled from the earlier 243 once the Node-side (D-family) codes were added in full. When writing new SPARQL against `SDCO.rdf`, use `sdco#` for damage-code/taxonomy terms and `m150-onto#` for data-exchange-format terms — check `SDCO.rdf`'s actual `@prefix`/`@base` lines if in doubt, since this has flipped before.

## Modeling approach (branch: `dev-classes_approach`)

Damage codes are modeled as **OWL classes**, not individuals:
- `owl:equivalentClass` matches literal condition-report codes (e.g. `:BAB` ≡ `hasConditionCode value "BAB"`).
- `rdfs:subClassOf` restrictions use `owl:someValuesFrom` (not `owl:hasValue`) on characteristic object properties (`hasPipeFabricDamage`, `hasDamageOrientation`, etc.) to link damage-code classes into their taxonomy (e.g. `CrackFissure ⊑ Fissure`).

This is the result of a **punning removal refactor**, fully executed (`docs/stale/Punning_Refactor_Plan.md` — plan complete, kept for history): originally every taxonomy term was punned (both `owl:Class` and `owl:NamedIndividual`) to fill `owl:hasValue` restrictions. That was replaced with `someValuesFrom` so subsumption reasoning works automatically without punning — trade-off: `someValuesFrom` is existential, so HermiT classifies individuals into the right damage classes but never materializes a literal, queryable triple (`:ind :hasPipeFabricDamage :CrackFissure`) for the filler.

A sibling branch `dev-instances_approach` (remote-only, individuals-only, no class taxonomy) was considered and rejected for this repo — it avoids the materialization gap but loses automatic subsumption. **Don't suggest switching back to it without raising that trade-off explicitly** — it was already decided once.

## Materialization: turning existential restrictions into literal triples

`scripts/materialize_object_properties.py` solves the gap above: realizes each individual's damage-code classes, then a SPARQL CONSTRUCT query walks from those realized classes through the untouched `someValuesFrom` restrictions to emit literal triples (most-specific filler only) to `derived/*_materialized.rdf`/`.ttl`. The source file is never modified (hash-checked). Supports `--source` to pick `SDCO.rdf` or `SDCO-dwa-parsed.rdf`, and `--catalog` to resolve `owl:imports` locally.

```bash
python scripts/materialize_object_properties.py --source SDCO-dwa-parsed.rdf
```

**Default path (fast, seconds):** `classify_individuals()` forward-chains the `equivalentClass` patterns directly with SPARQL UPDATE — every damage code is defined as either a plain `hasValue` restriction or an intersection of a base code class with one more `hasValue` restriction, so full DL realization was never actually needed for this taxonomy shape. Full run on `SDCO-dwa-parsed.rdf` (~1,128 individuals across the m150-onto imports): ~10s, 104 triples.

**`--reason` flag (slow, minutes+):** runs the original HermiT path via `owlready2` (`sync_reasoner(infer_property_values=True)`) instead, kept only as a correctness oracle — verified byte-for-byte identical output against the fast path on the benchmark dataset. HermiT reasoning time is driven by the *taxonomy's* DL expressivity (501 `someValuesFrom` restrictions, 1,228 defined classes, disjointness axioms), not individual count — it took 165s even on the 23-report lite benchmark, vs 10s total for the fast path on the full ~1,128-individual dataset.

**Bug fixed in this pass:** the CONSTRUCT query used to require `?ind a owl:NamedIndividual`, but `owlready2`'s RDF/XML export drops that explicit triple on round-trip — so every prior `--reason` run silently matched zero individuals (`derived/*_materialized.rdf` were empty stubs before this fix, regardless of dataset). The query no longer requires that clause; the type-walk already anchors `?ind` to real individuals.

Reuse the CONSTRUCT query for any new object property or damage code rather than writing new SWRL or hand-walking inferred types — it already generalizes across all object properties and the full subclass hierarchy. If a future damage-code class needs an `equivalentClass` pattern beyond plain-hasValue / one-level-intersection, extend `classify_individuals()`'s two SPARQL UPDATE queries rather than reintroducing HermiT as the default.

### Benchmark dataset

`benchmark/` holds a lightweight copy of the m150-onto-parsed import for fast iteration: `scripts/make_benchmark_dataset.py` picks one `ConditionReport` per distinct `hasConditionCode` (23 reports vs 452 individuals in the full parsed file) plus a 2-hop object-property closure, and `benchmark/catalog-lite.xml` points `owl:imports <https://l-jamora.github.io/m150-onto-parsed>` at it instead of the full file.

```bash
python scripts/make_benchmark_dataset.py   # regenerate benchmark/m150-onto-parsed-dwa-lite.rdf
python scripts/materialize_object_properties.py --source SDCO-dwa-parsed.rdf --catalog benchmark/catalog-lite.xml
```

## Other scripts

- `scripts/make_benchmark_dataset.py` — regenerates `benchmark/m150-onto-parsed-dwa-lite.rdf` (see above).
- `scripts/test_classify_individuals.py` — assert-based self-check for `classify_individuals()`'s two forward-chaining rules (simple + intersection `equivalentClass` patterns) against a toy graph. Run after touching that function.
- `scripts/generate_labels.py` — derives an `@en` `rdfs:label` for every SDCO class from its name and axioms (condition-code / intersection / CamelCase / verbatim branches) and appends them to `SDCO.rdf` as one regenerable marker-delimited block (`---- BEGIN/END GENERATED LABELS ----`) at the end of the file. Fills gaps only — never overwrites a label that already exists anywhere in the file — and is idempotent (strips its own prior block before re-parsing). `--dry-run` prints the block. `scripts/test_generate_labels.py` is its assert-based self-check; `tests/test_structure.py::test_every_sdco_class_has_a_label` keeps the gap closed.

### `scripts/obsolete/`

One-time recovery scripts for fallout from the namespace-consolidation commit (`5c38450`) above. Both confirmed via `--dry-run` to have zero remaining work against the current `SDCO.rdf` — their fixes are already baked into the file. Kept for history/docstring context, not part of the normal workflow.

- `restore_equivalentclass_axioms.py` — restored `owl:equivalentClass` axioms accidentally deleted by commit `5c38450`, splicing them back from commit `e0a0242` by text-matching each class's declaration line.
- `split_mixed_disjoint_classes.py` — fixed `owl:AllDisjointClasses` blocks that wrongly mixed independent characterization dimensions (e.g. `hasCharacterization1`-keyed and `hasCharacterization2`-keyed code families listed as mutually disjoint, when a real report can legitimately be both). Same bug class as the `BAB2_A`/`hasDamageOrientation` fix documented in `docs/stale/Handover_Materialize_Object_Properties.md`.

## Test suite

`tests/` (pytest) checks `SDCO.rdf` itself, not just the Python scripts. Full rationale, file-by-file design, and findings: `docs/design-specs/SDCO_Testing_Suite_Design_Spec.md` — read it before touching `tests/`.

- **Tier 1** (`tests/test_structure.py`, `tests/test_classification.py`, default `pytest`, ~1-2s): rdflib-only structural invariants over `SDCO.rdf`, plus a fixture round trip through `classify_individuals()`/`CONSTRUCT_QUERY`.
- **Tier 2** (`tests/test_reasoning.py`, opt-in via `pytest -m reasoner`, ~10s): HermiT via `owlready2`, needs a JDK and the sibling `m150-onto` repo. Both tiers currently pass. Two real ontology defects the suite once surfaced (design spec §4b) — `:BBC`'s `equivalentClass` wrongly reading literal `"BBB"`, and the `BCA1_*` family having no disjointness axioms — were fixed in commit `ab9ec6d`.
- Test individuals live in `tests/fixtures/test_individuals.rdf` — hand-authored (Protégé-shaped RDF/XML), not generated. Each individual's expected damage-code `rdf:type`(s) must be derived from HermiT (`python scripts/materialize_object_properties.py --source tests/fixtures/test_individuals.rdf --catalog tests/fixtures/catalog-v001.xml --reason`), **never** by hand-guessing or by copying `classify_individuals()`'s own output back in — that would make the test circular.

## Working with the ontology

- **Prototyping**: Protégé, HermiT/Pellet reasoner.
- **Python tooling**: `rdflib` (Turtle parsing, SPARQL CONSTRUCT) + `owlready2` (HermiT reasoning). Java (`jdk-23`+) must be on PATH for HermiT via owlready2.
- Loading via owlready2 on Windows: pass a bare filename with the directory added to `owlready2.onto_path` — `file:///C:/...` IRIs fail with `OSError: Invalid argument`.
- After any reasoning run, check `default_world.inconsistent_classes()` is empty before trusting results.
- Branch discipline: structural ontology work happens on `dev-classes_approach`, not `main`/`dev-sdco` (both currently behind, untouched by the punning/materialization work). Check with the user before merging or pushing — timing has not been decided.
