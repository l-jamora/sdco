# Design Spec: CSV-Driven Node Damage-Code Generator

**Date:** 2026-07-16
**Repo:** `C:\Users\jluis\GitHub\ICOM\sdco` (local), branch `dev-classes_approach`
**Files added:** `node_codes.csv`, `scripts/generate_node_codes.py`, `scripts/test_generate_node_codes.py`

This document specifies the CSV-driven tool built to add the remaining DIN EN 13508-2 **Node** damage/inventory/operation/other codes to `SDCO.rdf`, and the reasoning behind its design. Read `CLAUDE.md` first for repo-wide context (namespace state, modeling approach, materialization pipeline) — this doc only covers the new generator.

## 1. Problem this solves

`SDCO.rdf` models each DIN EN 13508-2 code as an OWL class:

- `owl:equivalentClass` matches the literal condition-report code (`hasConditionCode` `hasValue` `"<code>"`).
- `rdfs:subClassOf` restrictions use `owl:someValuesFrom` (not `owl:hasValue`) on a characteristic object property to place the code in the taxonomy.
- Characterization-letter subclasses add one more `hasValue` restriction (on `hasCharacterization1`/`hasCharacterization2`) via `owl:intersectionOf`.

Before this work, the **Pipe** side of the taxonomy (`PipeFabric`, `PipeInventory`, `PipeOperation`, `PipeOther`) was fully populated (~119 classes). The **Node** side was almost entirely empty: `NodeFabric` had only 3 codes (`DAA`, `DAB`, `DAC` + their characterization subclasses), and `NodeInventory`, `NodeOperation`, `NodeOther` had **zero** subclasses.

Hand-authoring the remaining Node codes in Turtle is repetitive and precision-sensitive — the axiom shape must match exactly, or `scripts/materialize_object_properties.py`'s forward-chaining classifier (`classify_individuals()`) silently stops recognizing new codes (it pattern-matches specifically on plain-`hasValue` and one-level-`intersectionOf` `equivalentClass` shapes). The generator lets new codes be authored as CSV rows instead, guaranteeing shape-correctness by construction.

## 2. Axiom shapes reproduced (verified against existing `SDCO.rdf` content)

**Single-characterization-dimension code** (`DAA`, under `NodeFabric`, `SDCO.rdf:4265`):

```turtle
###  https://l-jamora.github.io/m150-onto#DAA
:DAA rdf:type owl:Class ;
     owl:equivalentClass [ rdf:type owl:Restriction ;
                           owl:onProperty :hasConditionCode ;
                           owl:hasValue "DAA"
                         ] ;
     rdfs:subClassOf :NodeFabric ,
                     [ rdf:type owl:Restriction ;
                       owl:onProperty :hasNodeFabricDamage ;
                       owl:someValuesFrom :Deformation
                     ] .

###  https://l-jamora.github.io/m150-onto#DAA_A
:DAA_A rdf:type owl:Class ;
       owl:equivalentClass [ owl:intersectionOf ( :DAA
                                                  [ rdf:type owl:Restriction ;
                                                    owl:onProperty :hasCharacterization1 ;
                                                    owl:hasValue "A"
                                                  ]
                                                ) ;
                             rdf:type owl:Class
                           ] ;
       rdfs:subClassOf :DAA ,
                       [ rdf:type owl:Restriction ;
                         owl:onProperty :hasNodeFabricDamage ;
                         owl:someValuesFrom :GeneralDeformation
                       ] .
```

**Two-characterization-dimension code** (`DAB`, `SDCO.rdf:4314`) — the two dimensions are **separate, flat sibling sets**, never a joint/combined class, and each dimension can use a **different** object property:

```turtle
###  https://l-jamora.github.io/m150-onto#DAB1_A   (char1 sibling — naming: <code>1_<letter>)
:DAB1_A rdf:type owl:Class ;
        owl:equivalentClass [ owl:intersectionOf ( :DAB
                                                   [ rdf:type owl:Restriction ;
                                                     owl:onProperty :hasCharacterization1 ;
                                                     owl:hasValue "A"
                                                   ]
                                                 ) ;
                              rdf:type owl:Class
                            ] ;
        rdfs:subClassOf :DAB ,
                        [ rdf:type owl:Restriction ;
                          owl:onProperty :hasNodeFabricDamage ;
                          owl:someValuesFrom :SurfaceCrackFissure
                        ] .

###  https://l-jamora.github.io/m150-onto#DAB2_A   (char2 sibling — naming: <code>2_<letter>, different property)
:DAB2_A rdf:type owl:Class ;
        owl:equivalentClass [ owl:intersectionOf ( :DAB
                                                   [ rdf:type owl:Restriction ;
                                                     owl:onProperty :hasCharacterization2 ;
                                                     owl:hasValue "A"
                                                   ]
                                                 ) ;
                              rdf:type owl:Class
                            ] ;
        rdfs:subClassOf :DAB ,
                        [ rdf:type owl:Restriction ;
                          owl:onProperty :hasDamageOrientation ;
                          owl:someValuesFrom :Vertical
                        ] .
```

**Naming rule**: single-dimension codes name letter-subclasses `<Code>_<Letter>` (e.g. `DAA_A`); two-dimension codes name them `<Code>1_<Letter>` / `<Code>2_<Letter>` (e.g. `DAB1_A`, `DAB2_A`). The generator does **not** derive this naming — the CSV author supplies `class_name` directly.

**Disjointness** (explicitly requested: "set disjoint with other damage codes in the same level"), reproduced from the existing Pipe-side pattern:

```turtle
[ rdf:type owl:AllDisjointClasses ;
  owl:members ( :A :B :C )
] .
```

**Object properties already available**: `hasNodeFabricDamage`, `hasNodeInventoryFeature`, `hasNodeFeature`, and the shared (non-Node/Pipe-prefixed) `hasDamageOrientation`. **`hasNodeOperationDamage` did not exist** prior to this work — no property linked `NodeOperation` codes to anything. It is auto-declared by the generator (see §4) the first time it's referenced, mirroring the existing `hasPipeOperationDamage` declaration exactly:

```turtle
###  https://l-jamora.github.io/m150-onto#hasPipeOperationDamage
:hasPipeOperationDamage rdf:type owl:ObjectProperty ;
                        rdfs:subPropertyOf :hasPipeDamage ;
                        rdf:type owl:AsymmetricProperty ,
                                 owl:IrreflexiveProperty .
```

`hasConditionCode`, `hasCharacterization1`, `hasCharacterization2` are all `owl:DatatypeProperty`, `rdfs:range xsd:string`, imported from m150-onto — never redeclared by the generator.

## 3. `node_codes.csv` schema

Flat CSV, one row per class. Header:

```
class_name,category,parent_code,characterization_dim,char_value,object_property,filler_class,comment
```

`row_type` was dropped: a row is a "base" row (top-level code under a Node
container) if `parent_code` is blank, or a "char" row (characterization-letter
subclass of a `base` code) if it's filled in — derivable, so not worth typing.

`apply_defaults()` (called before validation) also fills in two fields when
left blank, verified against every existing Pipe-side class so the defaults
never guess at something the doc's earlier scope boundary (§5, object
properties) said must never be guessed:

- **`object_property`** — a base row defaults from its `category` via
  `CATEGORY_OBJECT_PROPERTY` (`NodeFabric`→`hasNodeFabricDamage`,
  `NodeInventory`→`hasNodeInventoryFeature`, `NodeOperation`→`hasNodeOperationDamage`,
  `NodeOther`→`hasNodeFeature` — this 1:1 category↔property mapping is 100%
  consistent across every existing Pipe-side base class). A char row instead
  carries forward the property from an earlier row in the same
  `(parent_code, characterization_dim)` group — also verified 100% consistent
  within a group (e.g. all of `BAB1_A/B/C` share `hasPipeFabricDamage`) — so
  only the first row of a group needs it spelled out; repeats can leave it
  blank. This carry-forward is deliberately **not** extended to guess a
  group's first row from the category default, because that's sometimes wrong
  (`BAA_A`/`BAA_B` use `hasDamageOrientation`, not `BAA`'s own
  `hasPipeFabricDamage`) — getting this field wrong is the one silent-failure
  case §5 already flags as a hard-validation risk, so it's never defaulted
  without a same-group precedent to copy from.
- **`class_name`** on char rows — derived as `<parent><dim>_<value>` if the
  code uses both characterization dimensions, or `<parent>_<value>` if it only
  ever uses one, checked against both the current CSV batch and any
  already-declared `<parent>1_*`/`<parent>2_*` siblings already in the
  ontology (covers a dimension added in an earlier run). This *is* the naming
  rule the original version of this doc said the generator would never derive
  — reversed on request, since it was the single biggest source of repetitive
  typing in practice. An explicit `class_name` in the CSV still always wins.

| Column | Required for | Meaning |
|---|---|---|
| `class_name` | `base` rows; optional on `char` rows (auto-derived, see above) | Full class name including any letter/dimension suffix, e.g. `DEA`, `DEA_A`, `DEB1_A`, `DEB2_C`. |
| `category` | `base` rows | One of `NodeFabric` / `NodeInventory` / `NodeOperation` / `NodeOther`. |
| `parent_code` | `char` rows | The base code's `class_name` this row characterizes. Blank ⇒ this is a `base` row. |
| `characterization_dim` | `char` rows | `1` or `2` — selects `hasCharacterization1`/`hasCharacterization2`. |
| `char_value` | `char` rows | The letter value for the `hasValue` restriction, e.g. `"A"`. |
| `object_property` | optional (see defaulting above) | Local name (no prefix) of the object property for the `someValuesFrom` restriction, e.g. `hasNodeFabricDamage`. |
| `filler_class` | all rows | Local name used as the `someValuesFrom` target, e.g. `Deformation`. May not exist yet in the ontology — see §5. |
| `comment` | optional | Free text emitted as `rdfs:comment`. |

Blank lines and any row whose first cell starts with `#` are skipped by the parser — this lets TODO/example rows live in the CSV as inline documentation without being treated as data.

The shipped `node_codes.csv` contains:
1. **5 round-trip proof rows** — the existing `DAA`, `DAA_A`, `DAB`, `DAB1_A`, `DAB2_A` data. Running the generator against these produces **no new class triples** (idempotent skip, §5) but still exercises disjoint-group computation (folds `DAA`+`DAB` into one `NodeFabric` group, since both are present as `base` rows).
2. **2 TODO example rows** (`DEA`, `DEA_A`) for a first `NodeOperation` code, deliberately chosen to exercise the `hasNodeOperationDamage` auto-declare path. Meant to be replaced with real data.

## 4. `scripts/generate_node_codes.py`

Pure `rdflib` (read-only graph parsing for validation lookups) + stdlib `csv` + string templating for output. No `owlready2`/Java — this is TBox authoring, not reasoning.

**CLI:**
```
python scripts/generate_node_codes.py [--csv node_codes.csv] [--source SDCO.rdf] [--dry-run]
```

**Control flow** (strict order, no partial writes):

```
parse SDCO.rdf (parse_any: try RDF/XML, fall back to Turtle)
  -> read_rows(csv)                (skip blank/# rows)
  -> validate(rows, graph)         (collect ALL errors; abort with no file touched if any)
  -> warn_missing_fillers(...)     (non-fatal)
  -> build_output(rows, graph)     (string of new Turtle blocks)
  -> --dry-run: print and exit
     else: insert_before_footer(source, text) and write
```

**Validation rules** (`validate()`):
- Duplicate `class_name` across rows → error.
- `row_type` must be `base` or `char`.
- `base` rows: `category` must be one of the 4 known Node containers.
- `char` rows: `characterization_dim` must be `1` or `2`; `char_value` non-empty.
- `char` rows: `parent_code` must resolve to either an earlier `base` row in the same CSV, or an existing `owl:Class` in the graph that is `rdfs:subClassOf` one of the 4 Node containers. Unresolvable → error (typo protection).
- `object_property`: must already be declared as `owl:ObjectProperty` in the graph, **or** match the regex `^has(Node|Pipe)(Fabric|Operation)Damage$` (see §4.1). Anything else → hard error naming the property and pointing at an existing analogous declaration to copy.
- `filler_class`: only required to be *non-empty* — existence in the graph is checked separately as a **warning**, never a validation failure (see §5).

### 4.1 Object-property auto-declaration

Only properties matching `has(Node|Pipe)(Fabric|Operation)Damage` are eligible for auto-declaration if not already present in the graph. This is deliberately narrow — bounded by an exact regex, not a general naming heuristic — because it covers the one concrete, known gap (`hasNodeOperationDamage`) by mirroring an existing sibling declaration exactly:

```python
AUTO_DECLARE_PATTERN = re.compile(r"^has(Node|Pipe)(Fabric|Operation)Damage$")
```

When triggered, it emits (family = `Node` or `Pipe`, extracted from the match):

```turtle
###  https://l-jamora.github.io/m150-onto#<prop_name>
:<prop_name> rdf:type owl:ObjectProperty , owl:AsymmetricProperty , owl:IrreflexiveProperty ;
    rdfs:subPropertyOf :has<family>Damage .
```

Any object property name that doesn't already exist and doesn't match this pattern is a **hard validation failure** — the script never guesses an arbitrary property's semantics.

### 4.2 Idempotent re-runs and disjoint grouping

If a CSV row's `class_name` already exists as an `owl:Class` in the graph, its class body is **skipped** (not re-declared, not duplicated) — but it still counts toward disjoint-group membership. This is also the deliberate mechanism for folding *pre-existing* codes into a new disjointness block alongside brand-new siblings: to include e.g. `DAA`/`DAB`/`DAC` in a disjoint group with new `NodeFabric` codes, just add rows for them too (their class axioms will simply be skipped).

Disjoint groups are computed purely from rows present in the CSV being processed (no whole-graph sibling query):
- `base` rows are grouped by `category`.
- `char` rows are grouped by `(parent_code, characterization_dim)`.

Only groups with **2 or more members** produce an `owl:AllDisjointClasses` block; singleton groups are skipped (a disjointness axiom over one class is meaningless).

### 4.3 Output placement

New Turtle is generated as a plain string (never via `graph.serialize()` on the whole merged graph — that would reorder/reformat the entire hand-authored file and produce an unreviewable diff). It is spliced in **immediately before** the file's trailing footer comment:

```
###  Generated by the OWL API (version 4.5.29.2024-05-13T12:11:03Z) https://github.com/owlcs/owlapi
```

confirmed to be the literal last line of `SDCO.rdf`. If that exact marker isn't found (e.g. the file gets re-exported from Protégé in a different shape later), `insert_before_footer()` falls back to a plain append and prints a `[warn]` — a non-fatal, self-announcing degradation rather than a silent assumption failure.

`SDCO.rdf` is git-tracked, so the intended review loop is: run the script, inspect `git diff`, and `git checkout -- SDCO.rdf` to abort if anything looks wrong. No separate staging file is used.

## 5. Deliberate scope boundaries

- **Filler classes are not validated for existence**, only warned about. The user's own stated workflow is to create `someValuesFrom` target classes (e.g. `Deformation`, `TapRoot`) by hand, sometimes *while* filling out the CSV — referencing a not-yet-declared class via `someValuesFrom` is syntactically valid RDF/OWL (an untyped URI until the class declaration is added), so this is a warning, not a blocker.
- **Object properties are stricter** than filler classes: a typo'd or invented property name that doesn't match the known auto-declare pattern is a hard failure, because getting the property wrong silently breaks the taxonomy's semantics (wrong dimension, wrong domain) in a way a human is unlikely to notice from the generated Turtle alone.
- **No whole-graph disjoint-sibling discovery.** The generator never queries "what other classes already exist under this category/parent" to auto-expand disjoint groups — grouping is CSV-scoped only, by design (see §4.2 for how to opt existing codes in).
- **Naming-convention logic is limited to char-row `class_name` derivation** (§3) — the one place retyping was the biggest burden. It never extends to `base` rows (real code letters like `DEA` come from the DIN standard, not a pattern) or to guessing `object_property` for a char group's first row (§3 explains why that stays a hard requirement).
- **Cascading validation errors are not suppressed.** If a `base` row fails validation, dependent `char` rows referencing it as `parent_code` will also report their own "unresolvable parent" error. This is accepted as harmless noise (all errors print together, so the root cause is visible) rather than adding suppression logic for a cosmetic nicety.
- **No duplicate-`hasValue`-string detection.** Two different `class_name`s accidentally using the same literal code string (e.g. a copy/paste typo) is not checked — OWL doesn't care, and it's a presentation-layer risk only. Left out per YAGNI; revisit only if it actually bites someone.

## 6. `scripts/test_generate_node_codes.py`

Assert-based `demo()`, no test framework, in-memory graph and row dicts only (matches this repo's existing `test_classify_individuals.py` convention). Twelve behaviors verified:

1. Base-row triple shape (`hasConditionCode` value, category superclass, `someValuesFrom` restriction).
2. Char-row `intersectionOf` shape (parent + `hasCharacterization1`).
3. Char-2 uses a distinct object property correctly (doesn't leak char-1's property).
4. Undeclared, non-matching `object_property` → hard validation failure.
5. `hasNodeOperationDamage`-style auto-declare path: validation passes, and the emitted property block has the correct `subPropertyOf`.
6. Unresolvable `parent_code` → hard validation failure.
7. Disjoint block emitted only for groups of 2+ members; singleton groups produce none.
8. Idempotent skip: a `class_name` already in the graph produces no class body, but is still folded into its disjoint group alongside a new sibling.
9. Footer-insertion lands new text before the marker, not after (verified against a temp file).
10. `apply_defaults`: base row `object_property` defaults from category.
11. `apply_defaults`: single-dim code derives `class_name` without a digit; a char group's first row does not get a guessed `object_property`.
12. `apply_defaults`: two-dim code derives `class_name` with a digit; a group's 2nd+ row carries forward `object_property` without leaking across dimensions.

Run: `python scripts/test_generate_node_codes.py` → `[ok] generate_node_codes: 12 behaviors verified`.

## 7. Verification performed

1. `python scripts/test_generate_node_codes.py` — all 9 assertions pass.
2. `python scripts/generate_node_codes.py --dry-run` against the real `SDCO.rdf` + shipped `node_codes.csv` — confirmed: the 5 existing DAA/DAB rows produced no class output (idempotency), `hasNodeOperationDamage` was auto-declared once, `DEA`/`DEA_A` were generated with the correct shapes, and one `AllDisjointClasses` block was emitted for `{DAA, DAB}` under `NodeFabric`.
3. A real (non-dry-run) write against a **throwaway copy** of `SDCO.rdf` (never the tracked file) was parsed afterward with `rdflib` (`format="turtle"`) — succeeded, 6557 triples, new content confirmed positioned immediately before the footer line. The throwaway copy was deleted; the tracked `SDCO.rdf` was not modified by this verification pass.

## 8. Next steps for the user

1. Replace the `DEA`/`DEA_A` TODO rows in `node_codes.csv` with real `NodeOperation` (and `NodeInventory`/`NodeOther`/remaining `NodeFabric`) codes from `docs/DIN EN 13508-2 ENGLISH.pdf`.
2. Create any referenced `filler_class` targets that don't exist yet (the script will list them as `[warn]`s).
3. Run with `--dry-run` first, review the printed Turtle, then run for real and check `git diff` before committing.
4. Once new Node codes exist, `scripts/materialize_object_properties.py` should pick them up automatically for materialization — no changes needed there, since the generator reproduces the exact `equivalentClass` shapes `classify_individuals()` already pattern-matches on.
