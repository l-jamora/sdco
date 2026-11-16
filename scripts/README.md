# scripts/

Two directories, split by job. Scripts import siblings as bare modules (`sys.path.insert(0, ...)`); `pyproject.toml` puts both directories on pytest's `pythonpath`. Run them through the repo-root `Makefile` where a target exists.

## `pipeline/` — turn a parsed M150 file into derived output

- `materialize_object_properties.py` — `make materialize [DATA=<parsed file>]`. Merges `SDCO.rdf`, `../m150-onto/m150-onto.rdf` (via the root `catalog-v001.xml`) and the parsed data file, realizes each individual's damage-code classes and emits literal `someValuesFrom` filler triples to `derived/<data stem>_materialized.rdf`. Fast SPARQL forward-chaining by default; `--reason` runs HermiT via `owlready2` as a correctness oracle. SDCO.rdf and the data file are hash-checked.
- `build_explainer.py` — `make explainer`. Extracts real data from `SDCO.rdf`, the m150 example dataset and the materialized file into `docs/sdco_data.json`, then builds the bilingual (EN/DE) `docs/index.html` from `docs/template.html`; many internal assertions, `--template-only` skips extraction.
- `explorer_demo.json` — synthetic demo sewer plan and classifier presets for the Explore tab, validated against `SDCO.rdf` by `build_explainer.py`.

## `authoring/` — scripts that edit `SDCO.rdf`

They import `pipeline/` modules (`parse_any`, `build_explainer` helpers) and each other: `apply_comments.py` imports `generate_node_codes.py`; `generate_labels.py` imports `build_explainer.py` and `generate_node_codes.py`; `generate_isdefinedby.py` imports all of those.

- `generate_node_codes.py` — generates OWL class axioms for Node damage/inventory/operation/other codes from `node_codes.csv` and inserts them into `SDCO.rdf`.
- `generate_labels.py` — derives an `@en` `rdfs:label` for every class and appends gap-fill-only labels as a regenerable marker-delimited block.
- `generate_isdefinedby.py` — adds `rdfs:isDefinedBy` tracing classes to DIN EN 13508-2 (code classes from their axioms, Observation classes from `observation_comments.csv` or the code classes pointing at them). `make regen` runs labels then isDefinedBy.
- `apply_comments.py` — splices reviewed `rdfs:comment` values from `observation_comments.csv` into `SDCO.rdf` by text-locating each class's declaration block (no rdflib round-trip write).
- `node_codes.csv`, `observation_comments.csv`, `nodeclasses_wip.xlsx` — input data.

The assert-based self-checks for these scripts live in `tests/` (`test_classify_individuals.py`, `test_generate_*.py`, `test_apply_comments.py`) and run under `make test`.
