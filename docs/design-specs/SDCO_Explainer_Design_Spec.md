# Design Spec: SDCO Interactive Explainer

**Date:** 2026-07-30
**Repo:** `C:\Users\jluis\Repositories\ICOM\sdco`, branch `dev-classes_approach`
**Files:** `scripts/build_explainer.py`, `docs/explainer/template.html`, `docs/explainer/sdco_data.json` (generated), `docs/explainer/index.html` (generated)

Read `CLAUDE.md` for repo-wide context (namespace state, modeling approach, materialization pipeline) before touching this.

## 1. Problem this solves

SDCO's value proposition — raw DIN EN 13508-2 condition codes gain semantic meaning via `owl:equivalentClass` + `someValuesFrom` subsumption — is hard to see by reading `SDCO.rdf` directly. There was no artifact that let someone unfamiliar with OWL/SPARQL grasp what the ontology buys over the raw m150 data in a few minutes, backed by real numbers rather than a hand-written pitch that could drift from the ontology as it evolves.

Goal: a single self-contained HTML page, built from a real run over `SDCO.rdf` + the m150 example dataset, that walks a reader from "here's a raw code" to "here's what SPARQL over SDCO can answer that raw codes can't" — and stays correct automatically because every number on the page is measured, not typed.

## 2. Architecture: extract-then-inject, two-phase build

```
SDCO.rdf ─┐
m150-onto.rdf ─┼─► build_explainer.py ─► sdco_data.json ─┐
m150-onto-parsed-dwa.rdf ─┤                              ├─► index.html
derived/SDCO-dwa-parsed_materialized.rdf ─┘   template.html ─┘
```

**Phase 1 — extraction** (`scripts/build_explainer.py`, Python/rdflib). Loads four graphs read-only via `parse_any()` (reused from `materialize_object_properties.py` — same Turtle-vs-RDF/XML sniffing and `xsd:string` literal normalization the materialization pipeline already needed), merges them into one in-memory graph, and runs a series of `build_*()` functions that each answer one question against real data: every condition report and its properties, every one of the ~80 defined codes (used or not) with its taxonomy meaning, the `Observation`/`Reference` class trees pruned to what's actually populated, every pipe/node asset, and six hand-picked SPARQL example queries paired with a `withoutSdco` variant showing what the same question requires without the ontology. Output: `docs/explainer/sdco_data.json`.

**Phase 2 — injection.** The JSON is serialized compactly, `</` sequences escaped to `<\/` (a literal `</script>` inside the payload would terminate the enclosing `<script>` tag early), and spliced into `docs/explainer/template.html` in place of a literal placeholder token (`__SDCO_DATA__`), producing `docs/explainer/index.html`. `main()` raises if the placeholder is missing rather than silently writing a stale page.

**Why inject rather than fetch.** The explainer is meant to be published as a Claude Artifact, which runs under a CSP that blocks `fetch`/XHR to any URL, including a same-directory `sdco_data.json`. Inlining the data as a `<script type="application/json">` block sidesteps that entirely — `index.html` needs no network or filesystem access at render time, and also works over a plain `python -m http.server` for local viewing (not `file://` — browsers treat `file://` as a unique origin per load, which breaks the page in other ways).

**Why two files instead of one script emitting HTML directly.** `template.html` is static markup/CSS/JS that a human edits directly in a text editor with real HTML/JS syntax highlighting; `build_explainer.py` never constructs HTML strings. Re-running the build after only touching JS/CSS just re-splices the same JSON.

## 3. Data model (`sdco_data.json`)

Six top-level keys, one row of the page's job each:

- **`reports`** — every `m150:ConditionReport` individual: raw properties (`code`, `char1`, `char2`, material/dimension fields via `prop_key()` camelCasing), which asset/inspection it belongs to (joined via `m150:inspects` / `isChildOf`), and `sdco` — the materialized damage-code triples for that report (`{property, class}` pairs), read from `derived/SDCO-dwa-parsed_materialized.rdf` rather than re-deriving them, since materialization is already a solved, tested problem (`scripts/materialize_object_properties.py`).
- **`codes`** — all ~80 `equivalentClass`-defined codes, via `Q_CODE_CLASS` (walks `owl:equivalentClass`/`owl:Restriction`/`hasValue` on `hasConditionCode`), each annotated with usage `count` in this sample (0 is a valid, displayed value — a code absent from the sample dataset is not dropped from the page), its `family` (derived from the code's first two letters per DIN EN 13508-2's own convention — B/D = Pipe/Node, A/B/C/D = Fabric/Operation/Inventory/Other), and `meaning` — the humanized `someValuesFrom` filler(s) on the class's own direct `rdfs:subClassOf` restrictions (`meaning_of()`), e.g. `:BAB` → `"Fissure"`.
- **`taxonomy`** — two pruned trees for the page's tree/graph views: `observation` (walks `rdfs:subClassOf` descendants of `:Observation`, annotating each node with how many of *this sample's* reports fall under it) and `reference` (shallow by design — `Reference` → 8 families → present codes as leaves, since walking the full char1/char2 variant subtree would be hundreds of classes deep and add no explanatory value here).
- **`assets`** — every `PipeSection`/`Node` individual with its recorded properties and a computed `reportCount`.
- **`queries`** — six hand-picked SPARQL examples (fissures across pipe+node, damage orientation, structural-vs-inventory bucketing, root intrusions, manhole infiltration, "not damage at all"), each executed for real against the merged graph (not just displayed as a static string) and paired with a `withoutSdco` block showing the raw-code-only equivalent query and an explanation of what it can't express — the page's central argument, made concrete per example rather than asserted in prose.
- **`stats`** — triple counts per file, ontology axiom counts (`equivalentClass`, named classes, `someValuesFrom`, `AllDisjointClasses`, object properties), and derived counts (report/code/asset/inspection counts, materialized triple/subject counts, inspection date range) — the numbers the page's stat strip and prose reference by ID by templating them in at build time.

**Self-check, not a test file.** `main()` asserts five invariants inline before writing output (96 reports, 23 used codes, 80 total defined codes, 141 materialized triples, every example query returns ≥1 row) — a `python -m pytest`-free guard that a change to the sample dataset, the ontology, or the extraction logic doesn't silently produce a page with a wrong number on it. These are exact counts pinned to the current benchmark dataset, not tolerances — deliberately brittle, so any drift is loud rather than silently absorbed. Note these will need updating if the sample dataset or ontology code count changes (see `CLAUDE.md`'s "504 equivalentClass definitions" — the explainer's own count of "codes" is a different, narrower query scoped to `hasConditionCode`-keyed definitions only, so the two numbers don't have to match and shouldn't be conflated).

## 4. Page structure (`template.html`)

Static HTML/CSS plus one IIFE of vanilla JS (no framework, no build step, no dependency — the whole page including the 500+ line script is one file) that reads the injected `D = JSON.parse(...)` object and renders into empty containers by ID. Section by section, top to bottom:

1. **Hero** — one report shown in full, with `‹`/`›` arrow buttons and left/right arrow keys (`goTo()`) to page through every *used* code in the sample, each transition re-rendering the raw code, its report row, and its plain-English "meaning" derived from the taxonomy.
2. **Stat strip** — headline numbers from `stats`, e.g. total codes defined vs. used in this sample.
3. **Problem statement** — "the meaning lives in a PDF" framing, with a couple of hand-picked code/meaning pairs (`pairCards`) as concrete illustration.
4. **Reference grid** — full code table (`refGrid`), one row per family, columns for each code kind, filterable to used-only vs. all-defined via a checkbox (`showUnused`) that toggles a CSS class rather than re-rendering.
5. **Taxonomy tree** — collapsible indented tree over `taxonomy.observation`/`.reference`.
6. **Taxonomy graph** — the same hierarchy as a node-link SVG diagram (custom layout, no d3/graphviz dependency), collapsed by default past a depth threshold (`markInitialCollapse`) so the initial render isn't overwhelming.
7. **"The bridge is one sentence"** — the equivalentClass + someValuesFrom pitch in prose, now that the reader has seen the taxonomy.
8. **Query bar** — one button per `queries` entry; clicking renders that query's SPARQL, its live result rows (`renderRowsTable`/`renderDistribution`), and its `withoutSdco` contrast — the page's payoff section.
9. **Claims / limits** — plain statement of what the ontology buys (three words) and what it doesn't do yet, notably that the ontology itself carries almost no `rdfs:label`/`rdfs:comment` and every plain-English gloss on the page was hand-written for the page, not sourced from ontology annotations — an honest scope boundary, not a claim that the ontology is self-documenting.
10. **Colophon** — build provenance (file sizes, triple counts) injected from `stats`.

Every `<section class="band">` follows the same shape: a `rail` div (a short vertical label) and a content block populated by one `put()`/`txt()` call reading from `D`. New sections should follow this pattern rather than introducing a second rendering convention.

## 5. Build & run

```bash
python scripts/build_explainer.py
```

Regenerates both `docs/explainer/sdco_data.json` and `docs/explainer/index.html` from whatever `SDCO.rdf`/`derived/SDCO-dwa-parsed_materialized.rdf` currently contain — re-run after any ontology or materialization change that should be reflected on the page. Optional flags (`--sdco`, `--m150-data`, `--m150-tbox`, `--materialized`, `--output`) let it point at the benchmark dataset instead of the full one, matching the `--source`/`--catalog` flag pattern already used by `materialize_object_properties.py`.

Serve, don't open directly:

```bash
cd docs/explainer
python -m http.server 8000
```

`file://` is a non-starter — browsers treat each `file://` load as its own unique security origin, which breaks the page (documented in README.md's Explainer section, which this spec expands on).

## 6. Known rough edges (as of 2026-07-30)

- `build_explainer.py`'s own run can be slow enough to time out under a 2-minute default shell timeout on this machine (observed empirically across the session; root cause not yet isolated — likely HermiT-adjacent I/O from `parse_any()` on the larger m150-onto files, not the extraction logic itself). Run it with a longer timeout or in the background rather than assuming a hang means failure.
- The ontology carries almost no `rdfs:label`/`rdfs:comment` (see §4, item 9) — every human-readable gloss on the page (`meaning_of()`'s output aside) was hand-authored against the page's own needs, not pulled from ontology annotations. If `SDCO.rdf` gains real annotations later, the honest thing is to prefer them over the hand-written prose, not layer both.
- The reference-tree simplification (§3, `build_reference_tree`) is deliberate and shallow; don't extend it to the full char1/char2 subtree without reconsidering whether the graph view can still render usefully at that depth.
