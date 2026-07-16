# SDCO: Removing Punning — Refactor Plan

## Background

SDCO currently declares a punned individual for every taxonomy leaf/branch term (e.g. `:CrackFissure` is both `owl:Class` and `owl:NamedIndividual`) so that it can be used as the filler of an `owl:hasValue` restriction. This was flagged in the docs as "not recommended" ([`Sewer Damage Classification Ontology SDCO.md:468`](Sewer%20Damage%20Classification%20Ontology%20SDCO.md#L468)), and the repo already created `dev-classes_approach` / `dev-instances_approach` to resolve it.

**Chosen direction:** `dev-classes_approach`. Replace every `owl:hasValue :Term` restriction with `owl:someValuesFrom :Term`, then delete the punned individual declarations. `someValuesFrom` takes a class expression, so no individual is needed, and subsumption (`CrackFissure ⊑ Fissure`) now flows through the reasoner automatically instead of being invisible to it.

## Scope

This pattern is **not limited to damage codes** — every characteristic property in the ontology uses it. Confirmed by scanning `SDCO.rdf`:

| Property | `owl:hasValue` restriction count |
|---|---|
| `hasPipeFabricDamage` | 76 |
| `hasPipeOperationDamage` | 40 |
| `hasDamageOrientation` | 26 |
| `hasPipeInventoryFeature` | 22 |
| `hasPipeFeature` | 14 |
| `hasWater` | 13 |
| `hasTerminationReason` | 13 |
| `hasNodeFabricDamage` | 11 |
| `hasStartNodeType` | 8 |
| `hasFinishNodeType` | 8 |
| `hasDamageCause` | 5 |
| `hasObstructionReason` | 4 |
| `hasLocation` | 4 |
| `hasVerticalCurvatureDirection` | 2 |
| `hasHorizontalCurvatureDirection` | 2 |
| **Total** | **~491 restriction blocks** |

There are **~211 punned `owl:NamedIndividual` declarations** (one per taxonomy term: `CrackFissure`, `Left`, `Right`, `InPipeline`, `Junction`, `Deformation`, `TapRoot`, …), each following the pattern:

```turtle
:Left rdf:type owl:NamedIndividual ,
               :Left .
```

Every filler checked (`Left`, `Right`, `Connection`, `Junction`, `InPipeline`, `CrackFissure`, …) is also declared as a real class with a `rdfs:subClassOf` parent in its taxonomy — so the fix applies uniformly, there's no leaf term that's "just" an individual with no class counterpart.

**Not affected:** restrictions like `owl:onProperty <...hasCharacterization1> ; owl:hasValue "A"` — these use string literals via the `m150-onto` data property, not punned classes. Leave these alone.

**Also unaffected:** the `owl:AllDisjointClasses` blocks (e.g. `CrackFissure`/`FractureFissure`/`SurfaceCrackFissure`) — these already operate purely on the class IRIs and stay valid once the punned individuals are gone. No `owl:AllDifferent`/`owl:differentFrom` individual-level axioms exist to clean up.

## The transformation

**Before:**
```turtle
###  http://www.semanticweb.org/jluis/ontologies/sdco#DAB1_B
:DAB1_B rdf:type owl:Class ;
        owl:equivalentClass [ owl:intersectionOf ( :DAB
                                                   [ rdf:type owl:Restriction ;
                                                     owl:onProperty <https://l-jamora.github.io/m150-onto#hasCharacterization1> ;
                                                     owl:hasValue "B"
                                                   ]
                                                 ) ;
                              rdf:type owl:Class
                            ] ;
        rdfs:subClassOf :DAB ,
                        [ rdf:type owl:Restriction ;
                          owl:onProperty :hasNodeFabricDamage ;
                          owl:hasValue :CrackFissure
                        ] .
```

**After:**
```turtle
###  http://www.semanticweb.org/jluis/ontologies/sdco#DAB1_B
:DAB1_B rdf:type owl:Class ;
        owl:equivalentClass [ owl:intersectionOf ( :DAB
                                                   [ rdf:type owl:Restriction ;
                                                     owl:onProperty <https://l-jamora.github.io/m150-onto#hasCharacterization1> ;
                                                     owl:hasValue "B"
                                                   ]
                                                 ) ;
                              rdf:type owl:Class
                            ] ;
        rdfs:subClassOf :DAB ,
                        [ rdf:type owl:Restriction ;
                          owl:onProperty :hasNodeFabricDamage ;
                          owl:someValuesFrom :CrackFissure
                        ] .
```

Only `owl:hasValue :X` → `owl:someValuesFrom :X` changes. Everything else in the restriction is untouched.

Then, remove the now-unused punned individual:
```turtle
###  http://www.semanticweb.org/jluis/ontologies/sdco#CrackFissure
:CrackFissure rdf:type owl:NamedIndividual ,
                       :CrackFissure .
```
This whole block is deleted (repeat for all ~211).

### More examples across different properties

`hasLocation` ([`SDCO.rdf:2782-2786`](../SDCO.rdf#L2782-L2786)):
```turtle
# before
[ rdf:type owl:Restriction ;
  owl:onProperty :hasLocation ;
  owl:hasValue :InPipeline
]
# after
[ rdf:type owl:Restriction ;
  owl:onProperty :hasLocation ;
  owl:someValuesFrom :InPipeline
]
```

`hasHorizontalCurvatureDirection` ([`SDCO.rdf:3179-3182`](../SDCO.rdf#L3179-L3182)):
```turtle
# before
[ rdf:type owl:Restriction ;
  owl:onProperty :hasHorizontalCurvatureDirection ;
  owl:hasValue :Left
]
# after
[ rdf:type owl:Restriction ;
  owl:onProperty :hasHorizontalCurvatureDirection ;
  owl:someValuesFrom :Left
]
```

`hasDamageOrientation` ([`SDCO.rdf:469-470`](../SDCO.rdf#L469-L470)) — note this property is `Functional`/`Asymmetric`/`Irreflexive`; those characteristics are unaffected by switching `hasValue`→`someValuesFrom`:
```turtle
# before
[ rdf:type owl:Restriction ;
  owl:onProperty :hasDamageOrientation ;
  owl:hasValue :Vertical
]
# after
[ rdf:type owl:Restriction ;
  owl:onProperty :hasDamageOrientation ;
  owl:someValuesFrom :Vertical
]
```

### What you gain

Today, `:CrackFissure` (individual) and `:Fissure` (class) have **no logical relationship** — a reasoner cannot tell that a report classified under `DAB1_B` is "about a Fissure." After the change, because `CrackFissure rdfs:subClassOf Fissure` is a real class axiom and the restriction is `hasNodeFabricDamage some CrackFissure`, a reasoner can automatically infer:
```
DAB1_B ⊑ (hasNodeFabricDamage some Fissure)
```
for every ancestor in the `Fissure` hierarchy, with no extra axioms needed.

## To-do list

- [ ] **Branch**: do this work on `dev-classes_approach` (already exists for this purpose), not `main`/`dev-sdco`.
- [ ] **Write a conversion script** rather than hand-editing — ~491 restriction blocks across ~9,000 lines is too large/repetitive to safely edit by hand. Options:
  - `rdflib` (Python): parse the Turtle graph, for every triple `?r owl:hasValue ?v` where `?r rdf:type owl:Restriction` and `?v` is also `rdf:type owl:Class`, replace predicate `owl:hasValue` with `owl:someValuesFrom`.
  - Simple regex pass also works here since the pattern is syntactically uniform (`owl:hasValue :Xxx` inside a Restriction block) — but validate against the data-property cases (`owl:hasValue "A"`) so only object-value (colon-prefixed, non-quoted) fillers are touched.
- [ ] **Convert all 491 `owl:hasValue` → `owl:someValuesFrom`** restrictions for the 14 properties listed above.
- [ ] **Delete the ~211 punned `owl:NamedIndividual` declarations** (the `:Term rdf:type owl:NamedIndividual, :Term .` blocks) — confirm each has zero remaining `owl:hasValue` references first.
- [ ] **Leave untouched**: `hasCharacterization1`/`hasCharacterization2`/`hasConditionCode` literal-valued restrictions (`owl:hasValue "A"`, `"BAB"`, etc.) and the existing `owl:AllDisjointClasses` blocks.
- [ ] **Reload in Protégé and run a reasoner** (HermiT or Pellet): check the ontology is still consistent, and spot-check that e.g. `DAB1_B` now classifies as a subclass of `hasNodeFabricDamage some Fissure`.
- [ ] **Spot-check functional/asymmetric/irreflexive properties** (`hasDamageOrientation`, `hasCondition`, `hasCurvatureDirection` subproperties) still behave as expected post-reasoning.
- [ ] **Update the docs**: revise the "Limitations" bullet in [`Sewer Damage Classification Ontology SDCO.md`](Sewer%20Damage%20Classification%20Ontology%20SDCO.md#L468) to describe the resolution instead of flagging punning as an open problem; note in "Step 4: Ontology Coding" that the mass-imported `hasValue` restrictions were converted to `someValuesFrom`.
- [ ] **Decide what happens to `dev-instances_approach`**: either drop it or keep it as a documented alternative (individuals-only, no class hierarchy) that was considered and not used, so future readers understand why.
- [ ] **Merge** `dev-classes_approach` back once verified, closing out the punning issue mentioned in commit `e4f7d2a`.
