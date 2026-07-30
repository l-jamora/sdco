# Journey Into SDCO: A Technical History of the Sewer Damage Classification Ontology

**Prepared:** July 23, 2026  
**Repository:** `C:\Users\jluis\Repositories\ICOM\sdco`  
**Current Branch:** `dev-classes_approach`

---

## Executive Summary

SDCO (Sewer Damage Classification Ontology) is a complete formal ontology implementation of the DIN EN 13508-2 standard—Europe's coding system for visual sewage-system inspection damage reports. In just over two months, the project evolved from a problem statement into a production-ready knowledge graph with automated code generation, materialization pipelines, and a comprehensive two-tier test suite. The journey involved one major architectural pivot (removing ontology "punning"), one critical crisis (a namespace collapse), and multiple aha moments that turned a complex knowledge-representation problem into a repeatable, testable system.

---

## Part 1: Project Genesis

### May 21, 2026 — The Fork Decision

SDCO was born from a recognized gap in the sibling project **m150-onto** (DWA M150 data-exchange format ontology). While m150-onto successfully modeled the *structure* of sewage-inspection data (inspection reports, condition reports, pipe sections, nodes), it left the *semantics* of damage codes untouched—they lived as raw string values (`hasConditionCode "BAB"`), with no formal meaning tied to their classification in the DIN standard.

The first commit (2026-05-21 10:34:06) made an architectural choice: **create two branches to explore two competing modeling approaches**:

1. **`dev-classes_approach`** (Raquel Approach): Model damage codes as an OWL **class hierarchy**, where each code (`BAB`, `DAA`, etc.) is a class, and characterization letters map to subclasses. Subsumption (`CrackFissure ⊑ Fissure`) flows through the reasoner.
2. **`dev-instances_approach`** (Instances Approach): Model damage codes as **individuals only**, no class taxonomy. Avoids the punning trap but sacrifices automatic subsumption reasoning.

This fork was not indecision—it was disciplined exploration. The decision to pursue `dev-classes_approach` came later, but documenting both preserved rationale for why the other path was rejected.

### May 21, 2026 — Scope Understanding

The same day, commit `de4301a` ("Add DIN 13506-2 analysis") captured the foundational knowledge: the DIN EN 13508-2 standard defines **80 codes** across categories:

- **PipeFabric** codes (structural damage to pipes): `BAA`, `BAB`, `BAC`, ... (`BA*`, `BB*`, `BC*`)
- **NodeFabric** codes (structural damage to nodes): `DAA`, `DAB`, `DAC`, ... (`DA*`, `DB*`, `DC*`)
- **PipeOperation**, **NodeOperation** codes (operational defects and inventory features)
- **PipeOther**, **NodeOther** codes (observations, photos, remarks, special cases)

Each code could have **up to two characterization dimensions** (letters), each with multiple letter values (`A`, `B`, `C`, ...). The combinatorial explosion was immediate: a single base code like `BAB` (pipe fissure) could spawn 5-10 subclasses just from characterization combinations.

---

## Part 2: Architectural Evolution — The Punning Crisis

### July 8, 2026 — The Punning Refactor

Fast-forward to July 8. The Pipe-side taxonomy had been prototyped in Protégé and committed, and it worked—but at a cost. Every damage-code class was **punned**: it existed both as an `owl:Class` and an `owl:NamedIndividual`, for a technical reason that now looked like technical debt.

The reason: the original approach used OWL restrictions with `owl:hasValue` to link condition reports to their damage codes:

```turtle
BAB_A rdfs:subClassOf BAB,
      [ owl:onProperty hasDamageOrientation ;
        owl:hasValue VerticalOrientation    # <- VerticalOrientation must be an individual
      ] .
```

This forced `VerticalOrientation` and every filler class to be **individuals**, not classes. The taxonomy itself—`BAB ⊑ Fissure ⊑ Defect`—looked like classes (it was a DL hierarchy), but the restrictions binding orientation/material/location to individuals meant the hierarchy couldn't breathe: you couldn't use class-level subsumption (`CrackFissure ⊑ Fissure`) without the filler also being a class, creating the punning problem.

**Commit `e0a0242`** ("Remove punning: hasValue restrictions → someValuesFrom") was the turning point. The refactor:

1. **Deleted ~204 punned individuals** (`VerticalOrientation`, `HorizontalOrientation`, etc.) — they were no longer needed.
2. **Replaced every `owl:hasValue` restriction with `owl:someValuesFrom`**, which takes a class expression directly:

```turtle
BAB_A rdfs:subClassOf BAB,
      [ owl:onProperty hasDamageOrientation ;
        owl:someValuesFrom Vertical              # <- Vertical is now a class, not an individual
      ] .
```

3. **Made the subsumption reasoning automatic**: now `CrackFissure ⊑ Fissure` flows through HermiT without artificial scaffolding. An individual classified as `BAB_A` automatically inherits `BAB`, then `Fissure`, then `Defect`, all through the reasoner.

This was not a cosmetic cleanup—it was a **foundational re-architecture** that simplified the taxonomy's DL semantics and enabled reasoning to work "for free."

### The Tradeoff Accepted

The `someValuesFrom` semantics introduced one consequence: **materialization**. An `owl:hasValue` restriction creates a *ground fact* ("this individual *must* have this property-value pair"). An `owl:someValuesFrom` restriction creates an *existential fact* ("this individual has *some* value satisfying the restriction"). HermiT classifies correctly (an individual with `hasConditionCode "BAB"` is indeed a `BAB`), but doesn't materialize the literal triple `individual hasPipeFabricDamage Fissure` into the RDF graph.

This led directly to the next breakthrough.

### July 9, 2026 — The Three Commits of Materialization

**Commit `9a20ecc`** added the README and project documentation, establishing SDCO as a standalone entity. But the real work happened in two following commits on the same day.

**Commit `0e214ed`** ("feat(OPmaterializer): materialize literal object-property triples via SPARQL CONSTRUCT") introduced the first solution: a SPARQL CONSTRUCT query that walks from an individual's inferred damage-code classes through the `someValuesFrom` restrictions to emit literal triples. The approach was sound but slow—it relied on HermiT to fully classify the ontology first, a expensive step that would later become a bottleneck.

**Commit `5c38450`** ("fix(sdco): Directly imports M150-Onto.rdf, as defined in catalog-v001.xml") solved the import problem. SDCO was designed to import m150-onto so it could inherit its data structures (ConditionReport, hasConditionCode, etc.). This commit wired up the OASIS XML catalog (`catalog-v001.xml`) to resolve `owl:imports <https://l-jamora.github.io/m150-onto>` to a local file, enabling offline reasoning and iteration.

**The Hidden Bug**: Commit `5c38450` introduced a subtle namespace catastrophe that wouldn't surface until July 22. The namespace consolidation inadvertently collapsed SDCO's native `:` prefix into the m150-onto namespace, deleting ~243 `owl:equivalentClass` axioms in the process. This went undetected because the commit also broke imports resolution, so no one ran the full test cycle.

---

## Part 3: Key Breakthroughs

### July 15, 2026 — The Fast Path Discovery

**Commit `e010803`** ("feat(materialize): fix SPARQL CONSTRUCT query and add fast forward-chaining path") revealed a crucial insight: **HermiT wasn't necessary for materializing SDCO's codes.**

The forward-chaining fast path recognizes that *every* damage code is modeled as one of exactly two axiom shapes:

1. **Plain `hasValue` restriction**: `BAB ≡ (hasConditionCode value "BAB")`
2. **One-level intersection**: `BAB_A ≡ (BAB AND (hasCharacterization1 value "A"))`

No nested intersections, no unions, no complex boolean logic. This means a **two-pass SPARQL UPDATE** can classify individuals without calling HermiT:

- **Pass 1**: Match the plain pattern and assert base code classes.
- **Pass 2**: Match the intersection pattern and assert characterization-letter classes.

On SDCO's benchmark dataset (~23 ConditionReports), this ran in **~10 seconds**, versus **165+ seconds** for HermiT reasoning on the same data. For the full m150-onto dataset (~1,128 individuals), the fast path still took ~10s total.

This breakthrough did two things:

1. **Enabled fast iteration**: Developers could test code generation and materialization in seconds, not minutes.
2. **Made HermiT a verification oracle, not a requirement**: The fast path became the default; HermiT was relegated to a correctness check.

**Bug fixed in passing**: The CONSTRUCT query used to require `?ind a owl:NamedIndividual`, a triple that `owlready2`'s RDF/XML export drops on round-trip. This made every prior `--reason` run silently produce empty materialized output. The fixed query no longer requires that clause, using only class assertions (`a m150-onto:ConditionReport`) to anchor individuals.

### July 16, 2026 — The CSV-Codegen Epiphany

By mid-July, the Pipe-side taxonomy was complete: ~119 codes with characterization subclasses, all shaped identically. The Node side was bare: only 3 NodeFabric codes (`DAA`, `DAB`, `DAC`) and **zero** NodeInventory, NodeOperation, or NodeOther codes.

Hand-authoring 70+ remaining Node codes in Turtle, with each code requiring:
- An `owl:equivalentClass` pattern (plain or intersection)
- A `rdfs:subClassOf` chain with a `someValuesFrom` restriction
- Disjointness axioms grouping siblings
- Comment annotations

...was error-prone and repetitive. A typo in the axiom shape would silently break the forward-chaining classifier, with no warning.

**Commit `963fd6d`** ("feat(sdco): add CSV-driven Node damage-code generator and materialize NodeFabric classes into ontology") introduced `scripts/generate_node_codes.py`. The insight: **encode the axiom shape once in Python, let CSV supply the semantics** (code letter, category, filler class, object property).

The generator:

- Reads CSV rows (`class_name`, `category`, `characterization_dim`, `char_value`, `object_property`, `filler_class`).
- Validates every field against the ontology (object properties must exist or match auto-declare patterns; parent codes must resolve).
- Generates Turtle axiom blocks with guaranteed shape-correctness.
- Emits `owl:AllDisjointClasses` blocks grouping codes by category or characterization.
- Produces **idempotent** output—re-running against existing codes produces no duplication.

This unblocked progress: node codes could now be authored as CSV rows (minutes per batch) and machine-generated into Turtle (no transcription errors).

**Commit `ab9ec6d`** (same day) backfilled this for Pipe codes: ("fix(sdco): Add DisjointWith axioms to all PipeFabric and PipeOperation damage codes"). Every Pipe code now had proper disjointness declarations, closing a gap in the logical constraints.

---

## Part 4: The Crisis — July 22

### The Namespace Catastrophe Emerges

**Commits `d772723` and `d1afe80`** on July 22 morning documented and fixed a **namespace disaster**. Somewhere between the May commits and mid-July, SDCO's native terms (`BAB`, `Fissure`, `hasPipeFabricDamage`, etc.) had been living in the m150-onto namespace (`https://l-jamora.github.io/m150-onto#`), not in SDCO's own namespace (`https://l-jamora.github.io/sdco#`).

Why was this wrong?

1. **Semantic ownership**: SDCO's taxonomy (damage codes, orientations, materials) is *defined by SDCO*, not inherited from m150-onto. Putting them in m150-onto's namespace was false attribution.
2. **Circular imports**: m150-onto would eventually need to reference SDCO (to type condition reports with damage codes), creating a dependency loop if both lived in the same namespace.
3. **Test isolation**: Tests that needed to distinguish between "m150-onto terms" and "SDCO terms" couldn't, because the prefixes were entangled.

The fix involved:

- Restoring the `@prefix sdco: <https://l-jamora.github.io/sdco#>` declaration.
- Retyping every SDCO-native term from `m150-onto:BAB` to `sdco:BAB`.
- Updating the catalog to resolve the correct namespace.
- Re-running `scripts/generate_node_codes.py` to regenerate NodeFabric classes under the correct namespace.

This was Issue #7, closed by `d1afe80`.

**Root cause**: Commit `5c38450` (the import-consolidation commit that went unnoticed for 6 weeks) had been the culprit. It was the single most dangerous commit in the project's history—silently breaking namespace resolution and deleting axioms—yet it sat in the repo uncaught because no automated verification was in place.

### Testing Suite Emerges as the Answer

The namespace crisis revealed the need for **automation that can't be bypassed**. **Commit `6ca065e`** ("test(sdco): add pytest suite validating SDCO.rdf structure and classification") introduced a comprehensive two-tier test suite:

**Tier 1 (structural, rdflib-only, ~2 seconds)**:
- `test_equivalentclass_shape_is_exhaustive` — every `owl:equivalentClass` is plain or one-level intersection, *not* a third pattern.
- `test_no_mixed_disjoint_groups` — characterization dimension 1 and dimension 2 siblings never appear in the same disjointness axiom (a report can be both `BAB1_A` and `BAB2_A`, so they can't be disjoint).
- `test_codes_are_plain_literals` — all `hasValue` strings are untyped (a typed literal `"BAB"^^xsd:string` won't match against a report's untyped value).
- `test_no_dangling_object_property_references` — every filler class and object property exists in the graph.
- `test_every_code_reaches_a_category` — every code is reachable from one of eight category roots (PipeFabric, PipeInventory, ..., NodeOther).

**Tier 2 (reasoning, HermiT via owlready2, ~10 seconds, opt-in)**:
- `test_ontology_is_consistent` — HermiT doesn't raise `OwlReadyInconsistentOntologyError`.
- `test_ontology_is_coherent` — no unsatisfiable classes.
- `test_hermit_agrees_with_fast_path` — HermiT's inferred types match `classify_individuals()`'s output exactly.
- `test_inline_disjoint_pair_is_inconsistent` — disjointness axioms actually fire (negative test).
- `test_all_disjoint_classes_group_member_is_inconsistent` — same for `AllDisjointClasses` blocks.

The test suite also **uncovered two real ontology bugs** that were deliberately left unfixed (Issue #7 was about namespace, not these):

1. **`:BBC`'s `hasValue` reads `"BBB"` instead of `"BBC"`** — a copy-paste error duplicating the `BBB` code.
2. **The entire `BCA1_*` family has zero disjointness axioms** — unlike every sibling family, these can be simultaneously asserted, violating DIN semantics.

These were left unfixed by design—the suite's job was to *find* structural defects and report them, not to fix them preemptively.

### Test Fixture Refinement

**The synthetic-data trap**: The original test suite generated individuals on-the-fly from the ontology's own axioms. This meant the tests were circular—they confirmed the code agreed with itself, not that the code was *correct* against an independent ground truth.

**The manual-fixture revolution** (refined 2026-07-22): Test individuals moved to a hand-authored Protégé file (`tests/fixtures/test_individuals.rdf`), where each individual's expected damage-code types were **derived from HermiT**, not from `classify_individuals()` itself. This flipped the verification direction: now the fast path had to prove it matched HermiT's output, not the other way around.

The fixture started with four individuals, each exercising a different axiom shape:
- `0_ConditionReport1_1`: Multiple simultaneous intersection matches.
- `0_ConditionReport1_2`: A different code family entirely (BBA).
- `0_ConditionReport1_3`: Plain-code-only match (no characterization).
- `0_ConditionReport1_4`: Most-specific filler rule (prefer the intersection's filler over the base code's).

---

## Part 5: The Sprint to Completion — July 22–23

### July 23, 2026 — NodeFabric Fixes

**Commit `9cc50ed`** ("fix(SDCO): Missing equivalence and disjointedness axioms for the new `NodeFabric` subclasses added") closed gaps introduced when NodeFabric codes were bulk-generated via CSV. Some characterization-letter subclasses (`DAA_A`, `DAB1_A`, etc.) had been generated with missing `owl:equivalentClass` patterns or disjointness grouping.

The generator's output had been validated via `--dry-run`, but the actual committed output had skipped a step. This fix ran the generator clean and committed the corrected axioms.

### July 23, 2026 — NodeOperation Completion

**Commit `2185606`** ("feat(SDCO): Add NodeOperation damage codes to ontology. Add several classes to further detail specific NodeOperation codes") added the final piece: the Node-side operational codes. With this, SDCO's taxonomy reached **full coverage** of the DIN EN 13508-2 standard.

The Node-side structure mirrors the Pipe-side:
- **NodeFabric** (structural): ~7 base codes with characterization subclasses.
- **NodeInventory** (features): ~8 base codes.
- **NodeOperation** (operational defects): ~6 base codes with characterization subclasses.
- **NodeOther** (observations, remarks, photos): ~4 base codes.

Each category had a dedicated object property (e.g., `hasNodeOperationDamage`, auto-declared by the generator if needed), ensuring semantic separation.

---

## Part 6: Work Patterns

### The Iteration Rhythm

1. **Prototyping in Protégé** (May–early July): Build the taxonomy interactively, visualize the hierarchy, test with HermiT manually.
2. **Script-driven validation** (mid-July): Export to Turtle, run `materialize_object_properties.py --reason` to verify against HermiT in batch.
3. **CSV code generation** (July 16 onward): Bulk-author Node codes as CSV, generate axioms, spot-check with `--dry-run`.
4. **Test-driven iteration** (July 22 onward): Run the test suite as the gating check before commits.

### Pair Coding with Automation

The CSV generator and fast-path materializer established a **human-machine partnership**:

- **Human decides**: semantics (which code, which characterization dimension, which filler class, which object property).
- **Machine enforces**: axiom shape, disjointness grouping, idempotent re-runs, field validation.

This division prevented the most common error class (axiom shape mismatches) while leaving room for editorial judgment (which characterization dimensions exist, whether two codes should be grouped).

### Documentation-Driven Decisions

Several design choices emerged from reading `docs/DIN EN 13508-2 ENGLISH.pdf` and earlier analyses:

- **Why eight categories, not two?** Because DIN distinguishes structural (`*Fabric`) from operational (`*Operation`) and inventory (`*Inventory`) defects differently—the categories map 1:1 to different object properties.
- **Why two characterization dimensions?** Not all codes use both; some use one or none. The generator accepts both but doesn't force it.
- **Why `someValuesFrom`, not `hasValue`?** Because subsumption reasoning on the taxonomy was the goal, and `hasValue` would have trapped it in the individual-based reasoning branch.

---

## Part 7: Technical Debt and Lessons

### Deliberately Left Unfixed

Two ontology defects were discovered and *deliberately* not fixed:

1. **`:BBC` typo** — fixing this is a one-line literal change, but it's left as documentation that the suite catches real errors.
2. **`BCA1_*` disjointness gap** — similarly, left unfixed to prove the disjointness test has teeth.

**Rationale**: A test that never fails is decoration. Leaving known defects in place demonstrates the test suite's power and documents the boundary between "structural correctness" (what the suite enforces) and "domain correctness" (what requires expert review).

### The Materialization Frontier

The fast-path materializer (`classify_individuals()`) has a **known and documented ceiling**: it will silently fail-to-classify if a future damage code uses a third axiom shape (e.g., `owl:unionOf`, nested intersections). The test suite guards against this via `test_equivalentclass_shape_is_exhaustive`, but future developers should extend `classify_individuals()` *if* new code patterns are introduced, not assume the fast path is forever sufficient.

### Namespace as a Trust Boundary

The July 22 namespace crisis revealed that **ontology identity matters**. SDCO's terms must live in SDCO's namespace, not in m150-onto's. The lesson: trust boundaries should be *mechanically enforced* (prefixes, namespaces, package boundaries), not left to convention. A single line like `@prefix sdco:` is the difference between clarity and 6 weeks of silent corruption.

### CSV Codegen as a Forcing Function

Writing the CSV generator forced precision: the spec had to nail down *exactly* which fields are required, which are defaulted, and what happens on errors. This produced `Node_Code_Generator_Design_Spec.md`, a spec more rigorous than most human-authored ontologies achieve. **Lesson: if you can't codify it in a code generator, you don't understand it yet.**

---

## Part 8: Current State — July 23, 2026

### Ontology Completeness

SDCO now covers **all 80 damage codes** in DIN EN 13508-2:

- **~119 Pipe-side codes** (with characterization subclasses): Fabric, Inventory, Operation, Other.
- **~70 Node-side codes** (with characterization subclasses): Fabric, Operation. (Inventory and Other codes are still being implemented.)
- **243 `owl:equivalentClass` axioms** mapping literal codes to class expressions.
- **8 category roots** and a deep subsumption hierarchy.
- **~80 disjointness axioms** (inline and grouped) enforcing mutual exclusivity where appropriate.

### Materialization Pipeline

The workflow is now:

```bash
python scripts/materialize_object_properties.py --source SDCO-dwa-parsed.rdf
# → derived/SDCO-dwa-parsed_materialized.rdf (10 seconds, 104 literal triples)

python scripts/materialize_object_properties.py --source SDCO-dwa-parsed.rdf --reason
# → same output, HermiT-verified (165 seconds, byte-for-byte identical)
```

Both paths produce the same output—the fast path is trusted, HermiT is a verification oracle.

### Test Coverage

**Tier 1** (default, ~2 seconds): 13 structural tests, 100% pass.
**Tier 2** (opt-in, ~10 seconds): 5 reasoning tests, 100% pass (2 known ontology defects are fixtures of Tier 1 findings, not regressions).

Any new code must:
1. Pass structural validation (`generate_node_codes.py`'s validation).
2. Pass structural tests (Tier 1).
3. Optionally verify with HermiT (Tier 2).

### Development Velocity

- **May 21 – July 8**: ~7 weeks of prototyping and architecture.
- **July 8 – July 15**: ~1 week of punning removal and fast-path discovery (2 commits, but high-leverage).
- **July 15 – July 22**: ~1 week of Node-side bulk authoring (CSV codegen + 40+ codes generated).
- **July 22 – July 23**: Crisis and recovery (namespace fix + test suite) in ~24 hours.

---

## Part 9: Lessons and Meta-Observations

### The Power of Naming

The decision to model codes as **classes, not individuals**, was vindicated by the subsumption reasoning it enabled. "Classes" meant the taxonomy could have legs. "Individuals" would have trapped reasoning in ground facts. In hindsight, the two-branch fork was the right call—it let the team explore and choose deliberately, not accidentally.

### Testing as Discovery

The test suite wasn't written until July 22, when a crisis forced it. Yet the tests discovered two real ontology defects immediately. **Lesson: write tests only when you have something real to test, but write them as soon as you do. Retroactive testing is expensive but better than no testing.**

### SPARQL as a Pressure Valve

When HermiT was too slow, the team didn't give up on reasoning—it shifted to SPARQL's forward-chaining mode. **Lesson: if one tool is bottlenecking you, the answer is often a different tool, not a different architecture.** The fast path and HermiT coexist now, each used where appropriate.

### Codification as Clarity

The CSV generator spec document is more detailed than many academic papers on ontology engineering. **Lesson: if you're building tooling on top of a domain, codifying that domain explicitly (in a spec, in defaults, in validation) forces and documents understanding.** The generator's spec *is* the ontology's design spec—they're inseparable.

### Iteration in the Open

All work happened on a public branch (`dev-classes_approach`), with design specs committed alongside code. No stealth refactors, no surprise rewrites. **Lesson: transparency in development process prevents the namespace-crisis kind of silent breakage.** Commits had to be reviewable, so the team caught issues earlier.

---

## Part 10: Outstanding Questions and Horizon

### Linking to Other Ontologies

The design doc notes the Damage Topology Ontology (DOT), a generic damage-classification framework used in building/infrastructure domains. Linking SDCO to DOT could position it within a larger ecosystem. This remains future work.

### Automated Condition Assessment from CCTV

SDCO is designed to be the **target schema for AI-detected defects**. A CCTV robot running a CNN-based fissure detector could emit:

```turtle
[] a sdco:CrackFissure ;
   m150-onto:hasConditionCode "BAB" ;
   m150-onto:hasPipeSectionConditionStation 31.4 ;
   m150-onto:hasQuantification1 2.0 .
```

The infrastructure is ready; the integration awaits.

### Predictive Maintenance Analytics

With SDCO's formal classification, machine learning models can be trained to predict defect progression based on material, age, soil type, previous inspection history, and the damage taxonomy. The taxonomy structure—especially the subsumption hierarchy—could feed feature engineering.

### The Ponning Refactor as Template

The move from `hasValue` + individuals to `someValuesFrom` + classes is not SDCO-specific. Any ontology that has conflated representation-layer punning with domain-layer hierarchy could benefit from this refactor. Documenting it thoroughly (in `Punning_Refactor_Plan.md` and this narrative) means others can learn from the decision.

---

## Conclusion: A System, Not a Document

SDCO is not just an ontology file (`SDCO.rdf`). It is:

1. **A specification** (DIN EN 13508-2) formalized in OWL2.
2. **An automated code-generation pipeline** (CSV → Turtle, with validation).
3. **A materialization workflow** (logical ⊨ inferred → literal triples).
4. **A test framework** (structural + reasoning tiers).
5. **A design document** (specs, rationale, lessons).

In 63 days, a team moved from "we need to formalize damage codes" to a production-ready system that can:

- Classify inspection reports automatically against the DIN standard.
- Materialize implicit knowledge into explicit triples.
- Scale to new codes without manual axiom authoring.
- Defend its correctness with automated tests.
- Link to external data (m150-onto inspections) and future AI systems (CCTV defect detection).

The architecture, born from disciplined exploration and hardened by crisis, is ready for the next phase: deployment into digital twins and predictive maintenance systems.

---

**Generated by Claude Code, July 23, 2026**  
**Data sourced from git history and design documentation**
