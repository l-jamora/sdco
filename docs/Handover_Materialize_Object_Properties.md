# Handover: Materializing Concrete Object-Property Triples

**Date:** 2026-07-08
**Repo:** `c:\Users\jluis\GitHub\ICOM\sdco` (local), `l-jamora/sdco` (remote)
**Branch:** `dev-classes_approach` (local, 1 commit ahead of `origin/dev-classes_approach`, **not pushed**)
**Latest commit:** `e0a0242` "Remove punning: hasValue restrictions -> someValuesFrom"

This file exists so a new Claude Code session can pick up this work without re-deriving everything above. Read this whole file before doing anything else — most of the diagnostic legwork is already done and documented below with evidence, not just claims.

## How we got here

1. `docs/Punning_Refactor_Plan.md` (in this repo) laid out a plan to remove OWL punning from SDCO — every taxonomy leaf term (e.g. `:CrackFissure`) was declared as both `owl:Class` and `owl:NamedIndividual` so it could fill `owl:hasValue` restrictions. That plan was fully executed on `dev-classes_approach`:
   - 248 `owl:hasValue :Class` restrictions → `owl:someValuesFrom :Class` (across `hasPipeFabricDamage`, `hasPipeOperationDamage`, `hasDamageOrientation`, `hasPipeInventoryFeature`, `hasPipeFeature`, `hasWater`, `hasTerminationReason`, `hasNodeFabricDamage`, `hasStartNodeType`, `hasFinishNodeType`, `hasDamageCause`, `hasObstructionReason`, `hasLocation`, `hasVerticalCurvatureDirection`, `hasHorizontalCurvatureDirection`).
   - 204 punned `owl:NamedIndividual` declarations deleted. (7 remaining `NamedIndividual` declarations in the file — `0_ConditionReport_001_1`, `0_ConditionReport_002_1`, `0_InspectionReport_001`, `0_InspectionReport_002`, `0_Node001`, `0_PipeSection001`, `:HighCost` — are genuine example-data individuals, not punning artifacts. Leave them alone.)
   - Fixed one pre-existing data bug HermiT caught after the conversion: `:BAB2_A` pointed `hasDamageOrientation someValuesFrom :SurfaceCrackFissure` (wrong — clashes with the property's `:Orientation` range since `SurfaceCrackFissure ⊑ Fissure`, not `⊑ Orientation`). Fixed to `:Longitudinal`, matching sibling codes `BAK2_A`/`BAL2_A`/`BAM_A` and the docs.
   - Docs updated: `docs/Sewer Damage Classification Ontology SDCO.md` (Limitations section, Step 4 section).
   - Verified consistent with HermiT (via `owlready2`): **zero inconsistent classes**.
   - Not yet pushed or merged — that decision is still open (user hasn't asked for it yet).

2. While discussing how to load new XML-derived condition-report data into the ontology, the user asked why Protégé's reasoner wasn't inferring **object properties** for example individuals. That's the live problem this handover is about.

## The open problem (precisely stated)

The ontology models each DIN 13508-2 damage code as a class defined via `owl:equivalentClass` matching literal condition-report codes, e.g. (`SDCO.rdf:493`):

```turtle
:BAB rdf:type owl:Class ;
     owl:equivalentClass [ owl:onProperty <https://l-jamora.github.io/m150-onto#hasConditionCode> ;
                            owl:hasValue "BAB" ] ;
     rdfs:subClassOf :PipeFabric ,
                     [ owl:onProperty :hasPipeFabricDamage ;
                       owl:someValuesFrom :Fissure ] .
```

and further-refined subclasses like `:BAB1_B` (`SDCO.rdf:528`) and `:BAB2_B` (`SDCO.rdf:580`) add `hasCharacterization1`/`hasCharacterization2` literal matches and narrower `someValuesFrom` restrictions (e.g. `hasPipeFabricDamage some CrackFissure`, `hasDamageOrientation some Circumferential`).

There's an example individual at `SDCO.rdf:7648`:

```turtle
:0_ConditionReport_001_1 rdf:type owl:NamedIndividual, m150-onto:Condition ;
    m150-onto:hasCharacterization1 "B" ;
    m150-onto:hasCharacterization2 "B" ;
    m150-onto:hasConditionCode "BAB" ;
    ... (other literal data properties)
```

**I ran HermiT directly on this individual (owlready2, see commands below) and confirmed:**

- Its **inferred Types** correctly include `:BAB`, `:BAB1_B`, `:BAB2_B`, and the anonymous restriction classes `hasPipeFabricDamage some Fissure`, `hasPipeFabricDamage some CrackFissure`, `hasDamageOrientation some Circumferential`. So classification (literal code → damage-code class) works perfectly.
- Its **object property assertions** (the actual triples/edges you'd see in Protégé's "Property assertions" panel, or query over with plain SPARQL) contain **nothing** for `hasPipeFabricDamage` or `hasDamageOrientation` — only the pre-asserted `isChildOf`.

**Why:** `owl:someValuesFrom` is an existential restriction. Under the Open World Assumption, `:BAB1_B ⊑ (hasPipeFabricDamage some CrackFissure)` only requires that *some* filler of type `CrackFissure` exists for every `BAB1_B` instance — it does not require, and DL reasoners will not invent, a concrete named individual to serve as that filler. So HermiT is behaving correctly; it's just that `someValuesFrom` fundamentally cannot produce a literal, queryable triple. This is the same design tension the ontology's own docs flag in the "Step 4: Ontology Coding" section — an earlier SWRL + intermediary-mapping-individuals approach was abandoned as "laborious... doppelt-gemoppelt" (doubly redundant) in favor of the pure-OWL `equivalentClass` approach, which is exactly what's now blocking triple materialization.

**What the user actually needs:** a real, literal triple such as `:0_ConditionReport_001_1 :hasPipeFabricDamage :CrackFissure .` that a plain SPARQL query (no OWL reasoner in the query path) can retrieve.

## Directions to evaluate (not decided — this is the next session's job)

Laid out neutrally; each has a real tradeoff and none has been chosen yet:

1. **SWRL rules that assert the edge directly**, e.g. `BAB1_B(?x) -> hasPipeFabricDamage(?x, :CrackFissure)`. Note `:CrackFissure` here is used as an individual constant in the rule head — this is functionally punning again (needs `:CrackFissure` usable as both class and rule-head constant), so it may partially undo the point of the just-finished refactor. Would need one rule per leaf `_X` subclass (~248 of them) — mechanical to generate from the existing `someValuesFrom` restrictions via script, but reintroduces the individual-per-term problem, just scoped to SWRL instead of the TBox.
2. **Post-hoc materialization step**: run the reasoner once (HermiT/Pellet, as already scripted below), then walk each individual's *inferred types*, and for every anonymous class expression `P some C` in that list, emit a literal triple `ind P C` back into the graph (or a separate "materialized" graph) via a script. This is an ETL/batch step, not a live OWL mechanism — keeps the TBox clean (no reintroduced punning) and produces exactly the queryable triples wanted. Straightforward to build on the `owlready2` HermiT pipeline already working (see below) — would need a bit of care picking which anonymous-class inferences to materialize (there can be multiple `P some C` for different C along a subsumption chain, e.g. both `hasPipeFabricDamage some Fissure` and `hasPipeFabricDamage some CrackFissure` — probably want only the most specific).
3. **SPARQL CONSTRUCT/INSERT over the reasoner-backed graph**: same idea as #2 but implemented as a SPARQL query run against a reasoning-capable triple store (GraphDB, Stardog, even Protégé's DL query) instead of a Python script.
4. **Query-time reasoning**: don't materialize anything; instead require that all downstream consumers query through an OWL-aware endpoint (DL query / a reasoner-backed SPARQL endpoint) rather than plain RDF SPARQL. Avoids storing derived data at all, but changes the tooling requirement for anyone querying the ontology later (can't just load `SDCO.rdf` into a plain triple store and SPARQL it).

Option 2 is probably the pragmatic middle ground (keeps the TBox punning-free, doesn't reintroduce SWRL complexity, produces literal triples) but this needs to be talked through with the user, not assumed.

## Environment / tooling already confirmed working

- Python 3.11.9, `rdflib` 7.1.4, `owlready2` all installed and working.
- Java 23 (`jdk-23`) installed and on PATH — needed for HermiT via owlready2.
- `SDCO.rdf` is Turtle syntax despite the `.rdf` extension. `owlready2`/HermiT need RDF/XML, so convert first via `rdflib`.

Working reasoner pipeline (validated, reuse this):

```python
# 1. Convert Turtle -> RDF/XML (owlready2 can't load Turtle directly)
from rdflib import Graph
g = Graph()
g.parse('SDCO.rdf', format='turtle')
g.serialize(destination=r'C:\Users\jluis\AppData\Local\Temp\sdco_rdfxml.owl', format='xml')
```

```python
# 2. Load into owlready2 and run HermiT
import owlready2
owlready2.onto_path.append(r"C:\Users\jluis\AppData\Local\Temp")
from owlready2 import get_ontology, sync_reasoner, default_world

onto = get_ontology("sdco_rdfxml.owl").load()
with onto:
    sync_reasoner(infer_property_values=True)  # infer_property_values_of= is NOT a valid kwarg in this owlready2 version

# Consistency check:
print(list(default_world.inconsistent_classes()))  # [] means consistent

# Inspect one individual:
ind = onto.search_one(iri="*0_ConditionReport_001_1")
for t in ind.INDIRECT_is_a: print(t)          # inferred Types (this DOES show P some C)
for prop in onto.object_properties():          # inferred object property VALUES (this does NOT show P some C fillers)
    if prop[ind]: print(prop, prop[ind])
```

Note: passing `file:///C:/...` IRIs directly to `get_ontology(...).load()` fails on Windows with `OSError: Invalid argument` — instead append the directory to `owlready2.onto_path` and load by filename only, as above.

## Key file locations

- `SDCO.rdf` — the ontology, repo root, ~8565 lines, Turtle syntax.
  - Prefix `:` = `http://www.semanticweb.org/jluis/ontologies/sdco#`
  - Prefix `m150-onto:` = `https://l-jamora.github.io/m150-onto#` (external ontology, condition-report/data properties live here — `hasCharacterization1/2`, `hasConditionCode`, etc.)
  - Damage-code class pattern: `SDCO.rdf:493` (`:BAB`), `:528` (`:BAB1_B`), `:580` (`:BAB2_B`) — good representative examples.
  - Example data individuals: `SDCO.rdf:7648` onward (`#Individuals` section).
- `docs/Sewer Damage Classification Ontology SDCO.md` — main design-narrative doc. Step 4 (~line 250-270) covers the SWRL-vs-pure-OWL history relevant to this problem. Limitations section (~line 454-471) covers the punning resolution.
- `docs/Punning_Refactor_Plan.md` — the (now-executed) plan for the punning removal. Useful for understanding *why* `someValuesFrom` was chosen over `hasValue`, which is the direct cause of the current materialization gap.

## Git state to be aware of

- Local `dev-classes_approach` is **1 commit ahead** of `origin/dev-classes_approach` (commit `e0a0242`) — not pushed.
- `dev-instances_approach` (remote only, `origin/dev-instances_approach`) is the individuals-only alternative that was considered and rejected during the punning refactor — kept on the remote as documented history, not deleted. It might be worth a second look now: it models everything through individuals rather than classes, which sidesteps this exact materialization problem (individuals-based facts are literal triples by construction) at the cost of losing automatic class-subsumption reasoning. Worth reconsidering in light of this new problem, but that trade was already discussed once with the user and they picked the classes approach for the subsumption benefit — don't just switch back without discussing why.
- Nothing has been merged into `main` or `dev-sdco`. `main` and `dev-sdco` are both at `de4301a` ("Add DIN 13506-2 analysis"), untouched by any of this work.
- User has not yet decided whether/when to push or merge `dev-classes_approach`.

## What the user wants next

Direct quote: "I need a literal queryable triple." They want to continue in a fresh session "to save on context and credits," with the new session doing "the majority of the thinking" — i.e., don't just mechanically implement option 2 above; actually think through the tradeoffs with the user first, the way this session did for the BAB2_A bug and the dev-instances_approach question (see `AskUserQuestion` usage pattern in this repo's recent history if available, or just: ask before committing to an approach that changes the ontology's modeling strategy).
