# SDCO — Agent Context

## Project Overview

SDCO (Sewer Damage Classification Ontology) is an OWL ontology that formalizes the **DIN EN 13508-2** standard — the European coding system for visual inspection of drains/sewers (damage codes, characterizations, inventory/observation codes; ~80 codes total). See `docs/DIN EN 13508-2 ENGLISH.pdf` for the source standard.

SDCO complements **[m150-onto](../m150-onto)** (`C:\Users\jluis\GitHub\ICOM\m150-onto`), a sibling ontology modeling the DWA M150 data-exchange format (pipe sections, nodes, inspection/condition reports as OWL individuals). Where m150-onto stores condition-report data as literal codes (`hasConditionCode "BAB"`), SDCO gives those codes semantic meaning as a damage-code class taxonomy (`:BAB` ⊑ `Fissure`, etc.) and imports m150-onto (`owl:imports` in `SDCO.rdf`, resolved locally via `catalog-v001.xml` pointing at `m150-onto.rdf`). Read `m150-onto/CLAUDE.md` before touching anything that crosses the two ontologies.

Full design narrative, competency questions, and SPARQL/SHACL examples: `docs/Sewer Damage Classification Ontology SDCO.md`.

## Key files

- `SDCO.rdf` — the ontology, repo root. **Turtle syntax despite the `.rdf` extension** — reasoning tools (owlready2/HermiT) need RDF/XML, so convert via `rdflib` first (see scripts).
- `SDCO-dwa-parsed.rdf` — SDCO merged with m150-onto-parsed example/test data (from m150-onto's ontoparser output).
- `catalog-v001.xml` — OASIS XML catalog resolving `owl:imports <https://l-jamora.github.io/m150-onto>` to the local `m150-onto/m150-onto.rdf` file, so imports work offline.
- `derived/` — generated output only (materialized triples, catalog copy for that context). Never hand-edit; regenerate via scripts.
- `docs/` — design doc, DIN EN 13508-2 PDFs, refactor/handover writeups. Read before large structural changes — several past decisions (punning removal, materialization approach) are recorded there with rationale, not just in commit messages.
- `scripts/` — one-off/repeatable maintenance scripts (Python, `rdflib`/`owlready2`), described below.

## ⚠️ Current namespace state (uncommitted, mid-refactor)

As of the current working tree, `SDCO.rdf` binds its default `:` prefix to the **m150-onto namespace** (`https://l-jamora.github.io/m150-onto#`), and native SDCO terms (`:BAB`, `:CrackFissure`, etc.) are declared under that same prefix rather than a separate `sdco:` namespace. This is a side effect of commit `5c38450` ("Directly imports M150-Onto.rdf, as defined in catalog-v001.xml"), which also deleted ~243 `owl:equivalentClass` axioms as collateral damage — since restored (see `scripts/obsolete/restore_equivalentclass_axioms.py` docstring for the full story; the axioms are back in `SDCO.rdf`, so that script is now a no-op kept for history). `docs/` still describes the older two-prefix layout (`:` = sdco#, `m150-onto:` = m150-onto#) — treat the docs' prefix examples as conceptually correct but not textually current. Check `SDCO.rdf`'s actual `@prefix`/`@base` lines before writing new SPARQL against it.

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

**`--reason` flag (slow, minutes+):** runs the original HermiT path via `owlready2` (`sync_reasoner(infer_property_values=True)`) instead, kept only as a correctness oracle — verified byte-for-byte identical output against the fast path on the benchmark dataset. HermiT reasoning time is driven by the *taxonomy's* DL expressivity (248 `someValuesFrom` restrictions, 243 defined classes, disjointness axioms), not individual count — it took 165s even on the 23-report lite benchmark, vs 10s total for the fast path on the full ~1,128-individual dataset.

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

### `scripts/obsolete/`

One-time recovery scripts for fallout from the namespace-consolidation commit (`5c38450`) above. Both confirmed via `--dry-run` to have zero remaining work against the current `SDCO.rdf` — their fixes are already baked into the file. Kept for history/docstring context, not part of the normal workflow.

- `restore_equivalentclass_axioms.py` — restored `owl:equivalentClass` axioms accidentally deleted by commit `5c38450`, splicing them back from commit `e0a0242` by text-matching each class's declaration line.
- `split_mixed_disjoint_classes.py` — fixed `owl:AllDisjointClasses` blocks that wrongly mixed independent characterization dimensions (e.g. `hasCharacterization1`-keyed and `hasCharacterization2`-keyed code families listed as mutually disjoint, when a real report can legitimately be both). Same bug class as the `BAB2_A`/`hasDamageOrientation` fix documented in `docs/stale/Handover_Materialize_Object_Properties.md`.

## Working with the ontology

- **Prototyping**: Protégé, HermiT/Pellet reasoner.
- **Python tooling**: `rdflib` (Turtle parsing, SPARQL CONSTRUCT) + `owlready2` (HermiT reasoning). Java (`jdk-23`+) must be on PATH for HermiT via owlready2.
- Loading via owlready2 on Windows: pass a bare filename with the directory added to `owlready2.onto_path` — `file:///C:/...` IRIs fail with `OSError: Invalid argument`.
- After any reasoning run, check `default_world.inconsistent_classes()` is empty before trusting results.
- Branch discipline: structural ontology work happens on `dev-classes_approach`, not `main`/`dev-sdco` (both currently behind, untouched by the punning/materialization work). Check with the user before merging or pushing — timing has not been decided.
