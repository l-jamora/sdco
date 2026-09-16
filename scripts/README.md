# scripts/

Maintenance and materialization tooling for SDCO, categorized into subdirectories. Scripts import each other as bare same-directory modules (`sys.path.insert(0, str(Path(__file__).resolve().parent))`), so interdependent scripts live together in one directory — see each subdir's own dependency notes below before moving anything further.

## `ontology/`

Core scripts that read/write `SDCO.rdf` directly, plus their self-checks and input data. Interlinked: `generate_node_codes.py` and `build_explainer.py` import `materialize_object_properties.py`; `apply_comments.py` imports `generate_node_codes.py`; `generate_labels.py` imports both `build_explainer.py` and `generate_node_codes.py`.

- `materialize_object_properties.py` — realizes each individual's damage-code classes and emits literal `someValuesFrom` filler triples to `derived/*_materialized.rdf`/`.ttl`. Fast SPARQL forward-chaining path by default; `--reason` runs HermiT via `owlready2` as a correctness oracle. `pyproject.toml`'s `pythonpath = ["scripts/ontology"]` makes this a bare import for `tests/conftest.py`.
- `generate_node_codes.py` — generates OWL class axioms for Node damage/inventory/operation/other codes from `node_codes.csv` and inserts them into `SDCO.rdf`.
- `generate_labels.py` — derives an `@en` `rdfs:label` for every SDCO class from its name/axioms and appends gap-fill-only labels to `SDCO.rdf` as a regenerable marker-delimited block.
- `apply_comments.py` — splices reviewed `rdfs:comment` values from `observation_comments.csv` into `SDCO.rdf` by text-locating each class's declaration block (never an rdflib round-trip write, to avoid reformatting the file).
- `build_explainer.py` — extracts real data from `SDCO.rdf` + the m150 example dataset into `docs/explainer/sdco_data.json`, then builds `docs/explainer/index.html`.
- `node_codes.csv`, `observation_comments.csv`, `nodeclasses_wip.xlsx` — input data consumed by the generators above.
- `test_classify_individuals.py`, `test_generate_node_codes.py`, `test_apply_comments.py`, `test_generate_labels.py` — assert-based self-checks against toy in-memory graphs (no fixture files). Standalone `python scripts/ontology/test_*.py` runs, not collected by pytest (`testpaths = ["tests"]` in `pyproject.toml`).

## `benchmark/`

- `make_benchmark_dataset.py` — builds `benchmark/m150-onto-parsed-dwa-lite.rdf`, a lightweight copy of the m150-onto-parsed import (one `ConditionReport` per distinct `hasConditionCode`, plus a 2-hop object-property closure) for fast materialization iteration.

## `obsolete/`

One-time recovery scripts for fallout from the namespace-consolidation commit `5c38450`. Both confirmed via `--dry-run` to have zero remaining work against the current `SDCO.rdf` — kept for history, not part of the normal workflow. See `CLAUDE.md` for details.
