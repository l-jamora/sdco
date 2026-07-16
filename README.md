# SDCO — Sewer Damage Classification Ontology

An OWL ontology formalizing **DIN EN 13508-2**, the European coding system for visual inspection of drains/sewers (damage, characterization, inventory/observation codes — ~80 codes total). Source standard: `docs/DIN EN 13508-2 ENGLISH.pdf`.

SDCO complements [m150-onto](../m150-onto), a sibling ontology modeling the DWA M150 data-exchange format (pipe sections, nodes, inspection/condition reports as OWL individuals). Where m150-onto stores condition-report data as literal codes (`hasConditionCode "BAB"`), SDCO gives those codes semantic meaning as a damage-code class taxonomy (`:BAB` ⊑ `Fissure`, etc.) via `owl:imports`, resolved locally through `catalog-v001.xml`.

Full design narrative, competency questions, and SPARQL/SHACL examples: `docs/Sewer Damage Classification Ontology SDCO.md`.

## Repository layout

- `SDCO.rdf` — the ontology (Turtle syntax despite the `.rdf` extension).
- `SDCO-dwa-parsed.rdf` — SDCO merged with m150-onto-parsed example/test data.
- `catalog-v001.xml` — OASIS XML catalog resolving `owl:imports` to the local m150-onto file.
- `derived/` — generated output only (materialized triples). Never hand-edit; regenerate via scripts.
- `benchmark/` — lightweight dataset for fast iteration on materialization.
- `docs/` — design docs, the DIN EN 13508-2 standard, refactor/handover writeups.
- `scripts/` — maintenance and materialization scripts (`scripts/obsolete/` holds one-time recovery scripts kept for history).

## Modeling approach

Damage codes are modeled as **OWL classes** (branch `dev-classes_approach`), not individuals: `owl:equivalentClass` matches literal condition-report codes, and `rdfs:subClassOf` restrictions use `owl:someValuesFrom` to place damage-code classes into their taxonomy. This lets HermiT-style subsumption reasoning work automatically without punning.

## Materialization

`someValuesFrom` restrictions are existential, so reasoning alone never yields a literal, queryable triple for the filler. `scripts/materialize_object_properties.py` closes that gap, producing `derived/*_materialized.rdf`/`.ttl`:

```bash
python scripts/materialize_object_properties.py --source SDCO-dwa-parsed.rdf
```

By default it forward-chains the `equivalentClass` patterns directly (seconds). Pass `--reason` to instead run the original HermiT path via `owlready2` as a correctness oracle (minutes+).

See `CLAUDE.md` for full agent-facing context, including current namespace state, working notes, and script details.
