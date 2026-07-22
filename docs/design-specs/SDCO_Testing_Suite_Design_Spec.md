# Design Spec: SDCO Ontology Test Suite

**Date:** 2026-07-16
**Repo:** `C:\Users\jluis\GitHub\ICOM\sdco` (local), branch `dev-classes_approach`
**Files added:** `pyproject.toml`, `requirements-dev.txt`, `tests/conftest.py`, `tests/synthetic.py`, `tests/test_structure.py`, `tests/test_classification.py`, `tests/test_reasoning.py`

Implements `docs/handover/plans/SDCO_Testing_Suite.md`. Read that plan first for the full rationale — this doc records what was actually built, the real ontology bugs it found on first run, and how to run/extend it. Read `CLAUDE.md` for repo-wide context (namespace state, modeling approach, materialization pipeline) before touching anything here.

> **Status note (2026-07-16):** Tier 1 (`pytest`, no args) has been run to completion; its findings are recorded in §4 and, in more detail, in `docs/handover/SDCO_Testing_Suite_Tier1_Findings.md`. **Tier 2 (`pytest -m reasoner`) has not been run to completion.** It was started and was still actively reasoning (confirmed via a live HermiT `java.exe` process) after ~25 minutes — reasoning over `SDCO.rdf` plus ~690 synthetic individuals is evidently much heavier than the 165s benchmark CLAUDE.md records for a smaller individual count — and was cancelled by request before finishing rather than left running unattended. Tier 2's code is written per the design in §3 below, but is **unverified**. Everything in this doc describing Tier 2 behavior is the intended design, not an observed result, until it's actually run to completion.

## 1. Problem this solves

`SDCO.rdf` had no tests. The only prior checks (`scripts/test_classify_individuals.py`, `scripts/test_generate_node_codes.py`) run against toy in-memory graphs and never load the real ontology, so they stay green even when `SDCO.rdf` itself breaks.

Two specific defects motivated this suite:

1. **`classify_individuals()`'s load-bearing assumption was asserted nowhere.** The forward-chaining classifier in `scripts/materialize_object_properties.py` is a hardcoded 2-pass algorithm, correct only because every `owl:equivalentClass` in `SDCO.rdf` is either a plain `hasValue` restriction or a one-level intersection of a base class with one more `hasValue` restriction. A future code shaped as a third pattern would silently under-classify, not error.
2. **The mixed-disjointness bug class had no permanent guard.** `scripts/obsolete/split_mixed_disjoint_classes.py` was a one-time fix for `owl:AllDisjointClasses` blocks that wrongly mixed characterization dimensions (a report can legitimately be both `BAB1_A` and `BAB2_A`). `scripts/generate_node_codes.py` adds codes from CSV, so the bug class can recur with no automated check to catch it.

Goal: catch ontology changes that make SDCO inconsistent, incoherent, or silently mis-classifying, before they land.

## 2. Approach

Two tiers, split by whether a DL reasoner is needed.

**Tier 1** (`tests/test_structure.py`, `tests/test_classification.py`) — rdflib only, no external deps beyond `pytest`, runs from a clean checkout in seconds-to-minutes. Structural invariants over `SDCO.rdf`, plus a synthetic round trip through the real `classify_individuals()` and `CONSTRUCT_QUERY`. This is where nearly all the value is, and it's the default (`pytest` with no args runs only this tier).

**Tier 2** (`tests/test_reasoning.py`) — opt-in via `@pytest.mark.reasoner`, minutes. HermiT via `owlready2`. Skips cleanly if `owlready2`, a JDK, or the sibling `m150-onto` repo (`../m150-onto`) is absent. One shared reasoner run backs three assertions (consistency, coherence, HermiT-agrees-with-fast-path); two additional negative tests each get their own fresh `owlready2.World()`, since an inconsistent ontology poisons every later reasoner call in the same process.

### Synthetic data, not copied fixtures

Test individuals are **generated from the ontology's own `owl:equivalentClass` patterns** (`tests/synthetic.py`), not hand-written or copied from `SDCO-dwa-parsed.rdf`. That file turned out to hold only 6 bare stub individuals with no damage codes — the coded examples live in the imported `m150-onto-parsed-dwa.rdf` in the sibling repo, which isn't guaranteed to exist on a given checkout. Generating from the ontology's own axioms means the suite needs no external data, stays complete as codes are added, and runs from a clean checkout.

Values are **plain untyped `Literal`s** — this pins a real trap: rdflib literal equality is datatype-sensitive, so `owl:hasValue "BAB"` only joins against an individual's asserted value if both sides are plain literals. A typed literal (`"BAB"^^xsd:string`) silently fails to classify. `test_typed_literal_does_not_classify` asserts this is expected behavior, not a latent surprise.

### Namespace trap

`SDCO.rdf`'s `:` prefix and `@base` are `https://l-jamora.github.io/m150-onto#`, not a separate `sdco#` namespace (see CLAUDE.md's "Current namespace state" section). All tests use `M150 = Namespace("https://l-jamora.github.io/m150-onto#")` — never `sdco#`.

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

Session-scoped fixtures, reusing `parse_any`, `classify_individuals`, `convert_to_owlxml`, `load_catalog`, `run_hermit`, `stage_imports` from `scripts/materialize_object_properties.py` rather than reimplementing them.

- `sdco_graph` — `parse_any(REPO / "SDCO.rdf")`. No imports, no catalog.
- `defined_classes` — `synthetic.get_defined_classes(sdco_graph)`, one SPARQL pass parsing every `owl:equivalentClass` into `{cls, kind, base, prop, val}` records (`kind` is `"plain"` or `"intersection"`). Computed once per session; every structural test asserts against this list instead of re-querying.
- `synthetic_graph` — `(graph, expected)`. `sdco_graph` plus one synthesized individual per defined class, classified via the real `classify_individuals()`. Built once, asserted against by every classification test.
- `reasoner_world` — Tier 2 only. Merges `sdco_graph` + synthetic individuals into one temp file, converts to RDF/XML, stages `owl:imports` via the local catalog, and runs HermiT once. Yields `(onto, expected)`. `pytest.skip`s if the sibling `m150-onto` repo, a JDK, or `owlready2` is missing.

### `tests/synthetic.py`

`get_defined_classes(graph) -> list[dict]` and `synthesize(graph, defined=None) -> (Graph, dict[URIRef, set[URIRef]])`.

Per defined class, emits one `ConditionReport` individual carrying only the property/value pair(s) that satisfy its `owl:equivalentClass` definition: a plain code gets its one pair; an intersection gets its base's pair **plus** its own — so `classify_individuals()`'s real two-pass forward chainer (not a shortcut) is what derives both types, exercising the same mechanism production code relies on. `expected` maps each individual to the exact class-closure it must end up with (e.g. the individual built for `BAB1_A` must classify as both `:BAB1_A` and `:BAB` — asserted as `==`, not `⊇`, since an extra class means two codes share a definition signature, exactly the duplicate-code bug worth catching).

### `tests/test_structure.py` — Tier 1, 8 tests

No reasoner; reads `defined_classes`.

| Test | Guards |
|---|---|
| `test_equivalentclass_shape_is_exhaustive` | Every `owl:equivalentClass` in the file is plain-hasValue or one-level intersection — proven by partitioning **all** definitions and asserting the partition is total, not by hardcoding a count (346/52/294) that would churn on every legitimate code addition. |
| `test_two_passes_suffice` | No intersection's `base` is itself intersection-defined — the direct guard on `classify_individuals()`'s hardcoded 2-pass count. |
| `test_no_mixed_disjoint_groups` | For each `owl:AllDisjointClasses` group and inline `owl:disjointWith` pair, all members keyed on a `hasCharacterization*` property share the *same* one. Guards defect (2). Parsed via rdflib SPARQL, not text, since both block styles (`AllDisjointClasses` and inline) coexist. |
| `test_sibling_characterizations_are_pairwise_disjoint` | Positive counterpart (OOPS! P11, missing disjointness): within one `(base, characterization property)` family, every sibling pair must appear in *some* disjointness axiom. |
| `test_no_duplicate_definitions` | No two classes share a `(kind, base, prop, val)` signature. |
| `test_codes_are_plain_literals` | Every `owl:hasValue` in a code definition is an untyped `Literal` (no datatype, no language tag). |
| `test_no_dangling_object_property_references` | Every `owl:someValuesFrom` filler and `owl:onProperty` target used in a restriction is declared in-file as `owl:Class` / `owl:ObjectProperty`. Scoped to object properties only — datatype properties (`hasConditionCode` etc.) come from the m150-onto import and are never declared in `SDCO.rdf`. |
| `test_every_code_reaches_a_category` | Every defined class is `rdfs:subClassOf*` one of the 8 category roots (`PipeFabric/Inventory/Operation/Other`, `NodeFabric/Inventory/Operation/Other`). |

### `tests/test_classification.py` — Tier 1, 5 tests

Against `synthetic_graph`.

| Test | Guards |
|---|---|
| `test_every_code_classifies` | Every synthesized individual carries exactly its expected type closure — the behavioral complement to the structural shape guard. |
| `test_materialization_nonempty_and_correct` | `CONSTRUCT_QUERY` produces `> 0` triples (the historical `?ind a owl:NamedIndividual` bug produced silent empty stubs — this would have caught it), and a `hasConditionCode "BAB"` individual materializes `hasPipeFabricDamage → :Fissure`. |
| `test_most_specific_filler_only` | An individual matching both a base and a characterization code (`BAB` and `BAB1_A`) materializes only the char code's filler (`:SurfaceCrackFissure`), not both. |
| `test_typed_literal_does_not_classify` | Negative: `hasConditionCode "BAB"^^xsd:string` classifies as nothing. Pins the datatype-sensitivity trap as intended behavior. |
| `test_classify_individuals_is_idempotent` | Running `classify_individuals()` twice adds nothing the second time — relevant because `SDCO-dwa-parsed.rdf` imports its own materialized output, a cycle that feeds prior output back in on re-runs. |

### `tests/test_reasoning.py` — Tier 2, `@pytest.mark.reasoner`, 5 tests

**Unverified — see the status note above.** Written and believed correct, not yet run to completion.

Three off the shared `reasoner_world` fixture:

- `test_ontology_is_consistent` — the fixture's own `sync_reasoner()` call would have raised `OwlReadyInconsistentOntologyError` and failed the fixture before any test body ran; reaching the assertion is the check.
- `test_ontology_is_coherent` — `owlready2.default_world.inconsistent_classes()` is empty. Separate from consistency: an unsatisfiable class leaves the ontology consistent while it simply has no individuals.
- `test_hermit_agrees_with_fast_path` — realizes the synthetic individuals under HermiT and asserts the inferred type closure matches `classify_individuals()`'s output exactly, **restricted to the equivalentClass-defined universe** (HermiT also infers the full `rdfs:subClassOf*` ancestor chain — `PipeFabric`, `Reference`, etc. — which the fast path never touches, so an unrestricted comparison could never agree even when correct). This turns HermiT into a standing oracle for the fast path, which CLAUDE.md says was previously verified byte-for-byte only once, by hand.

Plus two negative tests, each in a fresh `owlready2.World()`:

- `test_inline_disjoint_pair_is_inconsistent` — an individual typed into both members of an inline `owl:disjointWith` pair must raise `OwlReadyInconsistentOntologyError`.
- `test_all_disjoint_classes_group_member_is_inconsistent` — same, for two members of an `AllDisjointClasses` group.

These prove the disjointness axioms actually bite the reasoner, not just that they parse.

## 4. Findings from the first run

Per the plan: **a first-run structural failure is a real finding about the ontology, not a reason to relax the assertion.** Tier 1 (the only tier actually run — see status note above) found two genuine bugs, confirmed by hand against `SDCO.rdf`. Summarized here; full writeup with reproduction steps in `docs/handover/SDCO_Testing_Suite_Tier1_Findings.md`.

1. **`:BBC`'s `owl:hasValue` restriction reads `"BBB"` instead of `"BBC"`** (`SDCO.rdf:2094-2098`, copy-paste from `:BBB` at line 2013). This makes `:BBC` a literal duplicate of `:BBB` — any report coded `BBB` also (wrongly) classifies as `BBC`, and vice versa. Caught by `test_no_duplicate_definitions` directly, and manifests behaviorally in `test_every_code_classifies`.
2. **The entire `BCA1_*` family has zero disjointness axioms.** `BCA1_A, _B, _C, _D, _E, _G, _Z` (7 classes, `SDCO.rdf:2677-2780`) appear in no `owl:disjointWith` and no `owl:AllDisjointClasses` block anywhere in the file — unlike every sibling family (e.g. `BAB1_A/_B/_C` is properly grouped). A report could be classified as both `BCA1_A` and `BCA1_B` simultaneously with nothing to flag it. Caught by `test_sibling_characterizations_are_pairwise_disjoint`.

**Neither fix is applied by this suite** — building the tests was the scoped task; fixing `SDCO.rdf` is a separate, small follow-up (retype one literal; add one `AllDisjointClasses` block) left for a deliberate decision on this branch.

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

Tier 1 takes roughly 2-3 minutes on this machine — dominated by `rdfs:subClassOf*` SPARQL property-path queries over ~1,283 classes in rdflib's pure-Python engine (`test_every_code_reaches_a_category` runs 8 of these), not by anything being wrong.

Tier 2 has **not** been timed to completion. A run was started and cancelled after ~25 minutes while still actively reasoning (confirmed via a live HermiT `java.exe` process, not a hang) — reasoning over `SDCO.rdf` plus ~690 synthetic individuals combines a higher individual count and higher taxonomy expressivity than either case CLAUDE.md separately benchmarks for `--reason`, so 165s is not a reliable estimate here. Budget considerably more than that, and expect to run it deliberately (e.g. in the background) rather than inline.

### Reading a failure

- A **Tier 1 structural failure** (`test_structure.py`) means `SDCO.rdf` itself violates an invariant — fix the ontology, not the test. See §4 for the two known ones as of this writing.
- A **Tier 1 classification failure** (`test_classification.py`) means either the ontology or `classify_individuals()`/`CONSTRUCT_QUERY` in `scripts/materialize_object_properties.py` disagree with each other — check which side is wrong before editing either.
- A **Tier 2 failure** means HermiT disagrees with the fast path, or the ontology is actually inconsistent/incoherent under full DL semantics even though the fast-path forward chainer didn't notice (the fast path only pattern-matches `equivalentClass`; it has no notion of disjointness or consistency at all). This is what should happen per the design — Tier 2 is unverified (see status note), so treat the first real run as a shakedown, not just a check of `SDCO.rdf`.

### Extending the suite when adding new codes

New codes added via `scripts/generate_node_codes.py` (or by hand) are covered automatically — the synthetic individuals and expected classifications in §3 are generated from whatever `owl:equivalentClass` axioms exist in `SDCO.rdf` at test time, not hardcoded to today's 346. No test file needs editing to add coverage for a new code; only a new code that uses a *third* `equivalentClass` shape (see §1, defect 1) or introduces a *new* pattern of disjointness bug would need a new assertion, not new fixture data.

### Verifying `SDCO.rdf` is never mutated

The suite only ever copies triples into new in-memory `Graph()` objects or temp files; `SDCO.rdf` on disk is read-only to every test. Spot-check after a run:

```bash
git status --short SDCO.rdf   # should be empty
```

## 7. Out of scope

Matches the plan's scoping exactly:

- No tests for the Python scripts themselves — `scripts/test_classify_individuals.py` and `scripts/test_generate_node_codes.py` stay as they are.
- No SHACL, no ROBOT, no OOPS! integration, no CI workflow — no `.github/` exists today, and adding one means solving the hardcoded-catalog-absolute-path portability problem (`catalog-v001.xml` and `benchmark/catalog-lite.xml` both hardcode `C:/Users/jluis/...`) first.
- No hierarchy golden-file snapshot — the structural partition tests catch the same class of regression without per-code-addition churn.
- Fixing the two ontology bugs found in §4 — flagged, not fixed, by design.
