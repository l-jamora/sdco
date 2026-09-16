# Design Spec: SDCO Ontology Test Suite

**Date:** 2026-07-16 (updated 2026-07-22: synthetic data generation replaced with a manual fixture; updated again 2026-07-22: fixture given real HermiT-verified expected data, both tiers run to completion, several test-suite bugs fixed)
**Repo:** `C:\Users\jluis\GitHub\ICOM\sdco` (local), branch `dev-classes_approach`
**Files added:** `pyproject.toml`, `requirements-dev.txt`, `tests/conftest.py`, `tests/fixtures/test_individuals.rdf`, `tests/test_structure.py`, `tests/test_classification.py`, `tests/test_reasoning.py`

Read `CLAUDE.md` for repo-wide context (namespace state, modeling approach, materialization pipeline) before touching anything here.

> **Status note (2026-07-22):** Both tiers have been run to completion and are green except for the two real ontology defects in §4b, which are deliberately left unfixed. Tier 1: 13/13 pass.
>
> **Update (commit `ab9ec6d`):** both §4b defects were subsequently fixed. As of that commit both tiers pass in full (18/18). Tier 2 (`pytest -m reasoner`): 5/5 pass in ~10s on this machine — the ~25-minute reasoning time once feared for Tier 2 was a property of the old ~690-individual synthetic dataset (since deleted), not of the current 4-individual hand-authored fixture; against the fixture, HermiT is dominated by the taxonomy's expressivity, matching CLAUDE.md's ~165s benchmark order of magnitude, not the 25+ minute figure from the synthetic-data era.

## 1. Problem this solves

`SDCO.rdf` had no tests. The only prior checks (`scripts/test_classify_individuals.py`, `scripts/test_generate_node_codes.py`) run against toy in-memory graphs and never load the real ontology, so they stay green even when `SDCO.rdf` itself breaks.

Two specific defects motivated this suite:

1. **`classify_individuals()`'s load-bearing assumption was asserted nowhere.** The forward-chaining classifier in `scripts/materialize_object_properties.py` is a hardcoded 2-pass algorithm, correct only because every `owl:equivalentClass` in `SDCO.rdf` is either a plain `hasValue` restriction or a one-level intersection of a base class with one more `hasValue` restriction. A future code shaped as a third pattern would silently under-classify, not error.
2. **The mixed-disjointness bug class had no permanent guard.** `scripts/obsolete/split_mixed_disjoint_classes.py` was a one-time fix for `owl:AllDisjointClasses` blocks that wrongly mixed characterization dimensions (a report can legitimately be both `BAB1_A` and `BAB2_A`). `scripts/generate_node_codes.py` adds codes from CSV, so the bug class can recur with no automated check to catch it.

Goal: catch ontology changes that make SDCO inconsistent, incoherent, or silently mis-classifying, before they land.

## 2. Approach

Two tiers, split by whether a DL reasoner is needed.

**Tier 1** (`tests/test_structure.py`, `tests/test_classification.py`) — rdflib only, no external deps beyond `pytest`, runs from a clean checkout in seconds-to-minutes. Structural invariants over `SDCO.rdf`, plus a fixture round trip through the real `classify_individuals()` and `CONSTRUCT_QUERY`. This is where nearly all the value is, and it's the default (`pytest` with no args runs only this tier).

**Tier 2** (`tests/test_reasoning.py`) — opt-in via `@pytest.mark.reasoner`, minutes. HermiT via `owlready2`. Skips cleanly if `owlready2`, a JDK, or the sibling `m150-onto` repo (`../m150-onto`) is absent. One shared reasoner run backs three assertions (consistency, coherence, HermiT-agrees-with-fast-path); two additional negative tests each get their own fresh `owlready2.World()`, since an inconsistent ontology poisons every later reasoner call in the same process.

### Manual fixture, not synthesized data

**As of 2026-07-22, test individuals are hand-authored in Protégé, not generated.** The original design (`tests/synthetic.py`, since deleted) generated one individual per `owl:equivalentClass` definition straight from the ontology's own axioms, for exhaustive coverage with no external data file. That traded away something the maintainer wants back: authoring test individuals directly in Protégé, the same tool used to edit `SDCO.rdf` itself. The suite now reads a small hand-picked fixture instead: `tests/fixtures/test_individuals.rdf`.

The fixture asserts, per individual, both its property values (`hasConditionCode`, `hasCharacterization*`, ...) **and** its expected damage-code `rdf:type`(s) — since nothing else can supply an unambiguous expectation for a hand-picked individual (unlike the generated approach, where the expected type came for free from whichever axiom produced the individual). `tests/conftest.py`'s `load_fixture_individuals()` strips those asserted types back off before classification (keeping everything else — `:ConditionReport`, `:Node`, `:PipeSection`, `:InspectionReport`, `owl:NamedIndividual`, ...) and holds the stripped types aside as `expected`, so `classify_individuals()`/HermiT still have to re-derive them from the property values rather than finding them already there.

**Where the expected `rdf:type`s come from — HermiT, never the code under test.** Hand-guessing the expected types, or (worse) computing them by running `classify_individuals()` and copying its output back into the fixture, would make the classification tests circular — they'd just confirm the code agrees with itself. The expected types in `tests/fixtures/test_individuals.rdf` were instead produced by running `scripts/materialize_object_properties.py --source tests/fixtures/test_individuals.rdf --catalog tests/fixtures/catalog-v001.xml --reason`, an independent DL reasoner (HermiT via `owlready2`), and reading each individual's inferred type closure (`ind.INDIRECT_is_a`), intersected with the equivalentClass-defined damage-code universe (excluding ancestor taxonomy classes like `PipeFabric`/`Defect`/`Observation`/`Reference`, which are a separate concern already covered by `test_structure.py::test_every_code_reaches_a_category`). Materialized-property fillers (e.g. `hasPipeFabricDamage → :Fissure`) were cross-checked directly against `SDCO.rdf`'s own `someValuesFrom` axioms, not against `CONSTRUCT_QUERY`'s output. **Follow this same workflow — HermiT first, fixture second — when adding new fixture individuals**; never seed expected types from `classify_individuals()`'s own output.

This trades exhaustive coverage (every defined class, ~243 today) for maintainer control: coverage is now whatever's in the fixture file, edited directly. Add more individuals to `tests/fixtures/test_individuals.rdf` (in Protégé or by hand, matching its RDF/XML shape), then re-derive their expected types via `--reason` as above, to extend coverage; no Python changes needed unless a new *kind* of assertion is wanted.

Values are **plain untyped `Literal`s** — this pins a real trap: rdflib literal equality is datatype-sensitive, so `owl:hasValue "BAB"` only joins against an individual's asserted value if both sides are plain literals. A typed literal (`"BAB"^^xsd:string`) silently fails to classify. `test_typed_literal_does_not_classify` asserts this is expected behavior, not a latent surprise (this one test still builds its individual inline in Python, since it's a negative case that must never classify — there's nothing to hand-author).

### Namespace trap (historical — now fixed both in `SDCO.rdf` and in the tests)

As of commits `d772723`/`d1afe80`, `SDCO.rdf`'s `:` prefix and `@base` are `https://l-jamora.github.io/sdco#` again — native SDCO terms (`BAB`, `PipeFabric`, `hasPipeFabricDamage`, `Fissure`, ...) live there, while `m150-onto`-defined terms (`ConditionReport`, `hasConditionCode`, `hasCharacterization1/2`, ...) stay in `https://l-jamora.github.io/m150-onto#`. See CLAUDE.md's namespace section for the full history.

`test_classification.py` and `test_structure.py` were still hardcoding `m150-onto#` for SDCO-native terms (`M150.BAB`, `M150.PipeFabric`, `M150.hasPipeFabricDamage`, `M150.Fissure`, category roots, ...) when this was written against the pre-fix namespace layout — a straightforward miss once the ontology's namespace moved out from under the tests. Both files now declare `SDCO = Namespace("https://l-jamora.github.io/sdco#")` alongside `M150` and use whichever is correct per term. This was the single largest source of failures found when the suite was actually run against current `SDCO.rdf` (see §4a).

## 3. Files

### `pyproject.toml` (repo root)

Pytest config only — no `[project]` table, nothing to package.

```toml
[tool.pytest.ini_options]
pythonpath = ["scripts"]
testpaths = ["tests"]
markers = ["reasoner: needs owlready2 + JDK + sibling m150-onto repo (slow, minutes)"]
addopts = "-m 'not reasoner'"
```

`pythonpath = ["scripts"]` makes `from materialize_object_properties import ...` a bare import. `testpaths = ["tests"]` keeps pytest from collecting `scripts/test_*.py` — those two stay standalone `python scripts/test_*.py` self-checks, untouched. `addopts` makes Tier 2 opt-in.

### `requirements-dev.txt`

`pytest` and `owlready2` (Tier 2 only). Both were already present on this machine's `python` (user site-packages), so no install step was actually needed here — a clean checkout will need `pip install -r requirements-dev.txt`.

### `tests/conftest.py`

Session-scoped fixtures, reusing `parse_any`, `classify_individuals`, `convert_to_owlxml`, `load_catalog`, `run_hermit`, `stage_imports` from `scripts/materialize_object_properties.py` rather than reimplementing them. Also defines `get_defined_classes()` (moved here from the deleted `tests/synthetic.py` — still needed by the structural tests) and `load_fixture_individuals()`.

- `sdco_graph` — `parse_any(REPO / "SDCO.rdf")`. No imports, no catalog.
- `defined_classes` — `get_defined_classes(sdco_graph)`, one SPARQL pass parsing every `owl:equivalentClass` into `{cls, kind, base, prop, val}` records (`kind` is `"plain"` or `"intersection"`). Computed once per session; every structural test asserts against this list instead of re-querying.
- `classified_graph` — `(graph, expected)`. `sdco_graph` plus the fixture individuals from `tests/fixtures/test_individuals.rdf` (expected `sdco#`-namespace types stripped, everything else — `ConditionReport`, `Node`, `PipeSection`, `InspectionReport`, `owl:NamedIndividual` — left in place), classified via the real `classify_individuals()`. Built once, asserted against by every classification test. `load_fixture_individuals()` only strips types whose IRI starts with the `sdco#` namespace (`SDCO_NS` in `conftest.py`) — it used to strip *every* non-`ConditionReport` `rdf:type`, which silently deleted the fixture's basic `m150-onto` entity types (`Node`, `PipeSection`, `InspectionReport`) from the graph classification ran against. Fixed 2026-07-22.
- `reasoner_world` — Tier 2 only. Merges `sdco_graph` + fixture individuals into one temp file, converts to RDF/XML, stages `owl:imports` via the local catalog, and runs HermiT once. Yields `(onto, expected)`. `pytest.skip`s if the sibling `m150-onto` repo, a JDK, or `owlready2` is missing. It drops the fixture's own `owl:Ontology` declaration when merging — that declaration's `owl:imports` (pointing at the derived `materialized/test_individuals` file) isn't in the repo-root `catalog-v001.xml`, and without dropping it owlready2 tried to fetch it over the network and failed. Fixed 2026-07-22.

### `tests/fixtures/test_individuals.rdf`

Hand-authored (Protégé or by hand, matching Protégé's RDF/XML serialization) — not generated. Four `ConditionReport` individuals today, each with its expected `sdco#` `rdf:type`(s) asserted directly in the file (see the fixture's inline comments) and verified via HermiT, not via `classify_individuals()` (see the "manual fixture" section above for the workflow):

| Individual | `hasConditionCode` / characterizations | Expected types | Exercises |
|---|---|---|---|
| `0_ConditionReport1_1` | `BAB`, char1=`B`, char2=`A` | `{BAB, BAB1_B, BAB2_A}` | multiple simultaneous intersection matches |
| `0_ConditionReport1_2` | `BBA`, char1=`C` | `{BBA, BBA_C}` | a different base+intersection family |
| `0_ConditionReport1_3` | `BAB` only | `{BAB}` | plain-code-only match, filler `hasPipeFabricDamage → Fissure` |
| `0_ConditionReport1_4` | `BAB`, char1=`A` | `{BAB, BAB1_A}` | most-specific-filler rule, filler `hasPipeFabricDamage → SurfaceCrackFissure` (not the less-specific `Fissure`) |

`conftest.py`'s `load_fixture_individuals()` splits the `sdco#`-namespace types back out as `expected` before classification runs. Extend this file directly to add coverage — no Python changes needed — but re-derive new individuals' expected types via HermiT (`--reason`), never by hand-guessing or by running `classify_individuals()` and copying its output.

### `tests/test_structure.py` — Tier 1, 8 tests

No reasoner; reads `defined_classes`.

| Test | Guards |
|---|---|
| `test_equivalentclass_shape_is_exhaustive` | Every `owl:equivalentClass` in the file is plain-hasValue or one-level intersection — proven by partitioning **all** definitions and asserting the partition is total, not by hardcoding a count (243 today) that would churn on every legitimate code addition. |
| `test_two_passes_suffice` | No intersection's `base` is itself intersection-defined — the direct guard on `classify_individuals()`'s hardcoded 2-pass count. |
| `test_no_mixed_disjoint_groups` | For each `owl:AllDisjointClasses` group and inline `owl:disjointWith` pair, all members keyed on a `hasCharacterization*` property share the *same* one. Guards defect (2). Parsed via rdflib SPARQL, not text, since both block styles (`AllDisjointClasses` and inline) coexist. |
| `test_sibling_characterizations_are_pairwise_disjoint` | Positive counterpart (OOPS! P11, missing disjointness): within one `(base, characterization property)` family, every sibling pair must appear in *some* disjointness axiom. |
| `test_no_duplicate_definitions` | No two classes share a `(kind, base, prop, val)` signature. |
| `test_codes_are_plain_literals` | Every `owl:hasValue` in a code definition is an untyped `Literal` (no datatype, no language tag). |
| `test_no_dangling_object_property_references` | Every `owl:someValuesFrom` filler and `owl:onProperty` target used in a restriction is declared in-file as `owl:Class` / `owl:ObjectProperty`. Scoped to object properties only — datatype properties (`hasConditionCode` etc.) come from the m150-onto import and are never declared in `SDCO.rdf`. |
| `test_every_code_reaches_a_category` | Every defined class is `rdfs:subClassOf*` one of the 8 category roots (`PipeFabric/Inventory/Operation/Other`, `NodeFabric/Inventory/Operation/Other`). |

### `tests/test_classification.py` — Tier 1, 5 tests

Against `classified_graph`.

| Test | Guards |
|---|---|
| `test_every_code_classifies` | Every fixture individual carries exactly its expected `sdco#`-namespace type closure — the behavioral complement to the structural shape guard. Compares `actual_types` filtered to the `sdco#` namespace against `expected`, not filtered to "everything except `M150.ConditionReport`" — the latter used to leave `owl:NamedIndividual` in `actual_types` with nothing on the `expected` side to match it, an always-red comparison. Fixed 2026-07-22. |
| `test_materialization_nonempty_and_correct` | `CONSTRUCT_QUERY` produces `> 0` triples (the historical `?ind a owl:NamedIndividual` bug produced silent empty stubs — this would have caught it), and the fixture's plain-`BAB` individual (`0_ConditionReport1_3`) materializes `hasPipeFabricDamage → :Fissure`. |
| `test_most_specific_filler_only` | The fixture individual matching both a base and a characterization code (`0_ConditionReport1_4`: `BAB` and `BAB1_A`) materializes only the char code's filler (`:SurfaceCrackFissure`), not both. |
| `test_typed_literal_does_not_classify` | Negative: `hasConditionCode "BAB"^^xsd:string` classifies as nothing. Pins the datatype-sensitivity trap as intended behavior. Built inline, not from the fixture. |
| `test_classify_individuals_is_idempotent` | Running `classify_individuals()` twice adds nothing the second time — relevant because `SDCO-dwa-parsed.rdf` imports its own materialized output, a cycle that feeds prior output back in on re-runs. |

### `tests/test_reasoning.py` — Tier 2, `@pytest.mark.reasoner`, 5 tests

**Verified 2026-07-22 — 5/5 pass, ~10s total** against the current 4-individual fixture. Two bugs were found and fixed getting here, both in the test code, not the ontology:

- `owlready2.sync_reasoner(infer_property_values=True, world=world)` — the installed `owlready2` 0.51 takes the target world/ontology as a positional argument (`x=None, infer_property_values=False, ...`), not a `world=` keyword; raised `TypeError: sync_reasoner_hermit() got an unexpected keyword argument 'world'`. Fixed to `sync_reasoner(world, infer_property_values=True)`.
- `_assert_poisoned_pair_is_inconsistent`'s helpers embedded a blank node (the `owl:AllDisjointClasses`/pair-lookup result) into a second SPARQL query as `f"<{group}>"` — wrapping a blank node's opaque ID in angle brackets produces a syntactically valid but meaningless IRI, so the query silently matched zero members (`IndexError: list index out of range` downstream). Fixed to `group.n3()`, which emits correct `_:` blank-node syntax (or `<...>` for URIRefs) automatically.

Three off the shared `reasoner_world` fixture:

- `test_ontology_is_consistent` — the fixture's own `sync_reasoner()` call would have raised `OwlReadyInconsistentOntologyError` and failed the fixture before any test body ran; reaching the assertion is the check.
- `test_ontology_is_coherent` — `owlready2.default_world.inconsistent_classes()` is empty. Separate from consistency: an unsatisfiable class leaves the ontology consistent while it simply has no individuals.
- `test_hermit_agrees_with_fast_path` — realizes the fixture individuals under HermiT and asserts the inferred type closure matches `classify_individuals()`'s output exactly, **restricted to the equivalentClass-defined universe** (HermiT also infers the full `rdfs:subClassOf*` ancestor chain — `PipeFabric`, `Reference`, etc. — which the fast path never touches, so an unrestricted comparison could never agree even when correct). This turns HermiT into a standing oracle for the fast path, which CLAUDE.md says was previously verified byte-for-byte only once, by hand.

Plus two negative tests, each in a fresh `owlready2.World()`:

- `test_inline_disjoint_pair_is_inconsistent` — an individual typed into both members of an inline `owl:disjointWith` pair must raise `OwlReadyInconsistentOntologyError`.
- `test_all_disjoint_classes_group_member_is_inconsistent` — same, for two members of an `AllDisjointClasses` group.

These prove the disjointness axioms actually bite the reasoner, not just that they parse.

## 4. Findings

### 4a. Test-suite bugs (found and fixed, 2026-07-22)

Once the suite was actually run against current `SDCO.rdf` (rather than designed against a since-superseded namespace layout), it failed almost everywhere — not because of ontology defects, but because the suite itself had drifted from the ontology and from its own fixture. All fixed in place; none of these required touching `SDCO.rdf`:

1. **Stale `m150-onto#` namespace for SDCO-native terms**, in both `test_classification.py` and `test_structure.py` (`M150.BAB`, `M150.PipeFabric`, `M150.hasPipeFabricDamage`, `M150.Fissure`, the 8 `CATEGORY_ROOTS`, ...) — written against the namespace layout CLAUDE.md used to describe as "current, uncommitted, mid-refactor," which was committed and flipped back to `sdco#` in the meantime. See the "Namespace trap" section above.
2. **`conftest.py`'s `load_fixture_individuals()` over-stripped**: it pulled *every* non-`ConditionReport` `rdf:type` triple off the fixture individuals into `expected`, including basic `m150-onto` entity types (`Node`, `PipeSection`, `InspectionReport`) and `owl:NamedIndividual` — not just `sdco#` damage-code classifications. This silently deleted real type information from the graph being classified and made `expected` contain noise no test could meaningfully check. Fixed to only strip `sdco#`-namespace types.
3. **`test_every_code_classifies`'s `actual_types` filter** excluded only `M150.ConditionReport`, so `owl:NamedIndividual` stayed in `actual_types` with nothing on the `expected` side to match it — an always-red comparison once (2) stopped erroneously absorbing `owl:NamedIndividual` into `expected` too. Fixed to filter `actual_types` to the `sdco#` namespace, matching what `expected` now actually contains.
4. **The fixture had no expected classifications at all** — `test_individuals.rdf` asserted property values but never the resulting `sdco#` `rdf:type`(s), so `expected` was empty and three classification tests had nothing to check (two failed with `StopIteration` looking for individuals that didn't exist). Fixed by adding two more individuals (`0_ConditionReport1_3`, `_4`) and asserting all four individuals' expected types, verified via HermiT (`--reason`) — see the "manual fixture" section above for why HermiT and not `classify_individuals()` itself.
5. **`reasoner_world`'s merged graph carried the fixture's own `owl:Ontology`/`owl:imports` triples**, including an import (`.../sdco/materialized/test_individuals`) absent from the repo-root `catalog-v001.xml`; owlready2 tried to fetch it over the network and failed. Fixed by dropping triples about the fixture's Ontology node before merging.
6. **`owlready2.sync_reasoner(..., world=world)`** — a keyword the installed `owlready2` 0.51 doesn't accept (it's positional). Fixed to `sync_reasoner(world, infer_property_values=True)`.
7. **Blank node embedded as `f"<{group}>"` in a second SPARQL query** (`test_reasoning.py`'s poisoned-pair helpers) — produces a syntactically valid but semantically meaningless IRI instead of blank-node syntax, so the follow-up query silently matched zero rows. Fixed to `group.n3()`.

### 4b. Real ontology defects (found, since fixed in commit `ab9ec6d`)

Two genuine `SDCO.rdf` bugs, confirmed by hand, survived after all of §4a's fixes — at the time of writing these were what was actually still red (`pytest -m ""`: 16/18 pass):

1. **`:BBC`'s `owl:hasValue` restriction reads `"BBB"` instead of `"BBC"`** (`SDCO.rdf`, copy-paste from `:BBB`). This makes `:BBC` a literal duplicate of `:BBB` — any report coded `BBB` also (wrongly) classifies as `BBC`, and vice versa. Caught by `test_no_duplicate_definitions`.
2. **The entire `BCA1_*` family has zero disjointness axioms.** `BCA1_A, _B, _C, _D, _E, _G, _Z` appear in no `owl:disjointWith` and no `owl:AllDisjointClasses` block anywhere in the file — unlike every sibling family (e.g. `BAB1_A/_B/_C` is properly grouped). A report could be classified as both `BCA1_A` and `BCA1_B` simultaneously with nothing to flag it. Caught by `test_sibling_characterizations_are_pairwise_disjoint`.

**Neither fix was applied by this suite at the time** — deliberately left for a separate decision on this branch (retype one literal; add one `AllDisjointClasses` block). Both were subsequently fixed in commit `ab9ec6d` (`:BBC` retyped to `"BBC"`; an `owl:AllDisjointClasses` block added for the `BCA1_*` family) — `pytest -m ""` now passes 18/18. This section is kept as a historical record of what the test suite surfaced; see the design spec's git history for the fix itself.

## 5. Mutation-proof (guard verification)

Per the plan, "a test that never fails is decoration." Each guard was proven capable of failing by mutating an in-memory copy (never the real `SDCO.rdf`) and confirming red:

| Mutation | Result |
|---|---|
| Chained intersection (a class's `equivalentClass` base is itself intersection-defined) | `test_two_passes_suffice` → **red** |
| `equivalentClass` to an `owl:unionOf` (a genuine third shape, matching neither plain nor one-level-intersection) | `test_equivalentclass_shape_is_exhaustive` → **red** |
| Cross `owl:disjointWith` between a char1-keyed and a char2-keyed sibling (`BAB1_A owl:disjointWith BAB2_A`) | `test_no_mixed_disjoint_groups` → **red** |
| Retype `:BAA`'s `hasValue` literal to `"BAA"^^xsd:string` | `test_codes_are_plain_literals` → **red** |
| Delete `:BAA`'s `someValuesFrom` restriction | `test_materialization_nonempty_and_correct` → **red** |

Note the first row: a chained-intersection base does **not** trip the shape-exhaustiveness test — by design, that's `test_two_passes_suffice`'s job. The shape test only fails for a structurally different `equivalentClass` pattern (e.g. `unionOf`), which needed its own mutation to demonstrate.

## 6. How to use this suite

### Setup (once per checkout)

```bash
pip install -r requirements-dev.txt
```

Tier 2 additionally needs a JDK on `PATH` and the sibling `m150-onto` repo checked out at `../m150-onto` relative to this repo (i.e. `C:\Users\jluis\GitHub\ICOM\m150-onto`). Both are already satisfied on this machine.

### Running

```bash
pytest                      # Tier 1 only (default) — structure + classification, no reasoner
pytest -m reasoner          # Tier 2 only — HermiT, several minutes
pytest -m "" -q             # both tiers in one run (overrides the default addopts filter)
python scripts/test_classify_individuals.py   # existing standalone self-checks, untouched
python scripts/test_generate_node_codes.py
```

Tier 1 runs in ~1-2 seconds on this machine (13 tests, all rdflib in-memory SPARQL over `SDCO.rdf` alone — no reasoner, no imports resolved).

Tier 2 (5 tests) runs in ~10 seconds on this machine against the current 4-individual fixture, HermiT included. The ~25-minute figure once recorded here was specific to the old, since-deleted synthetic dataset (~690 generated individuals) — irrelevant now that the fixture is 4 hand-authored individuals; don't use it to budget future Tier 2 runs.

### Reading a failure

- A **Tier 1 structural failure** (`test_structure.py`) means `SDCO.rdf` itself violates an invariant — fix the ontology, not the test. See §4b for the two now-fixed ones found this way historically.
- A **Tier 1 classification failure** (`test_classification.py`) means either the ontology, `classify_individuals()`/`CONSTRUCT_QUERY` in `scripts/materialize_object_properties.py`, or the fixture's HermiT-derived expected types disagree with each other — check which side is wrong before editing any of them.
- A **Tier 2 failure** means HermiT disagrees with the fast path, or the ontology is actually inconsistent/incoherent under full DL semantics even though the fast-path forward chainer didn't notice (the fast path only pattern-matches `equivalentClass`; it has no notion of disjointness or consistency at all).

### Extending the suite when adding new codes

The structural tests (`test_structure.py`) still cover new codes automatically — they assert against `defined_classes`, parsed fresh from whatever `owl:equivalentClass` axioms exist in `SDCO.rdf` at test time. **The classification/materialization tests (`test_classification.py`, `test_reasoning.py`) do not** — since 2026-07-22 they only see whatever individuals are hand-authored in `tests/fixtures/test_individuals.rdf`. A new code is only *behaviorally* exercised if someone adds an individual for it to that file (in Protégé or by hand); the structural tests will catch shape/disjointness defects in it either way.

### Verifying `SDCO.rdf` is never mutated

The suite only ever copies triples into new in-memory `Graph()` objects or temp files; `SDCO.rdf` on disk is read-only to every test. Spot-check after a run:

```bash
git status --short SDCO.rdf   # should be empty
```

## 7. Out of scope

- No tests for the Python scripts themselves — `scripts/test_classify_individuals.py` and `scripts/test_generate_node_codes.py` stay as they are.
- No SHACL, no ROBOT, no OOPS! integration, no CI workflow — no `.github/` exists today, and adding one means solving the hardcoded-catalog-absolute-path portability problem (`catalog-v001.xml` and `benchmark/catalog-lite.xml` both hardcode `C:/Users/jluis/...`) first.
- No hierarchy golden-file snapshot — the structural partition tests catch the same class of regression without per-code-addition churn.
- Fixing the two ontology bugs found in §4b — flagged, not fixed, by design at the time; both were subsequently fixed in commit `ab9ec6d` (see §4b).
