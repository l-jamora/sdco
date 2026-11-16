"""Add an rdfs:isDefinedBy annotation to every SDCO code class, tracing it to
the DIN EN 13508-2 main code (and characterization) it formalizes, and append
them to SDCO.rdf as one marker-delimited block before the OWL API footer.

The value is read from the class's own equivalentClass axiom, never its name:
    :BAB    -> "DIN EN 13508-2, main code BAB"
    :BAB2_A -> "DIN EN 13508-2, main code BAB, characterization 2 = A"
Observation classes (the fillers, e.g. :CrackFissure) have no such axiom;
they take the reviewed din_clause column of observation_comments.csv instead:
    :ArchShapedConnectingPipeline -> "DIN EN 13508-2, Table 12, DCG char1 (E)"
Remaining classes are traced through the code classes whose someValuesFrom
restrictions point at them, in the same notation:
    :Circumferential -> "DIN EN 13508-2, Table 4, BAB char2 (C); Table 10, DAB char2 (C)"
Table numbers come from the din_clause column itself (per main code; a code it
never mentions falls back to its two-letter prefix only if that prefix maps to
exactly one table there, else the table is left out). Classes with none of the
three (SDCO's own groupings, e.g. :Cause) get nothing.

shortcut: code classes themselves trace to the code, not the table number.

Write policy and idempotency as in generate_labels.py: fill gaps, never
overwrite; the prior block is stripped before parsing. Do NOT round-trip
SDCO.rdf through rdflib.

Usage:
    python scripts/authoring/generate_isdefinedby.py --dry-run
    python scripts/authoring/generate_isdefinedby.py
"""

import argparse
import csv
import re
import sys
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph
from rdflib.collection import Collection
from rdflib.term import URIRef

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from build_explainer import local_name  # noqa: E402
from generate_labels import SDCO_NS, _char_restriction, _esc  # noqa: E402
from generate_node_codes import insert_before_footer  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STANDARD = "DIN EN 13508-2"

BEGIN_MARKER = "###  ---- BEGIN GENERATED ISDEFINEDBY (scripts/generate_isdefinedby.py -- do not hand-edit) ----"
END_MARKER = "###  ---- END GENERATED ISDEFINEDBY ----"
_BLOCK_RE = re.compile(
    r"\n*" + re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER) + r"\n*",
    re.DOTALL,
)


def strip_block(text: str) -> str:
    """Remove a previously generated block; no-op if none present."""
    return _BLOCK_RE.sub("\n", text)


def code_parts(g: Graph, cls: URIRef) -> tuple[str, list[tuple[str, str]]] | None:
    """(main code, [(N, V), ...]) from equivalentClass, or None."""
    for eq in g.objects(cls, OWL.equivalentClass):
        prop = g.value(eq, OWL.onProperty)
        val = g.value(eq, OWL.hasValue)
        if prop is not None and str(prop).endswith("hasConditionCode") and val is not None:
            return str(val), []

        inter = g.value(eq, OWL.intersectionOf)
        if inter is not None:
            members = list(Collection(g, inter))
            base = next((m for m in members if isinstance(m, URIRef)), None)
            char = next((c for c in (_char_restriction(g, m) for m in members) if c), None)
            parts = code_parts(g, base) if base is not None else None
            if parts and char:
                return parts[0], parts[1] + [char]
    return None


def code_path(g: Graph, cls: URIRef) -> str | None:
    """'main code X[, characterization N = V ...]', or None."""
    parts = code_parts(g, cls)
    if parts is None:
        return None
    return ", ".join([f"main code {parts[0]}"] + [f"characterization {n} = {v}" for n, v in parts[1]])


def table_lookup(clauses: dict[str, str]):
    """main code -> table number, learned from the reviewed din_clause strings."""
    by_code: dict[str, set[str]] = {}
    for clause in clauses.values():
        for part in clause.split(";"):
            table = re.search(r"Table (\d+)", part)
            for code in re.findall(r"\b([BD][A-D][A-Z])\b", part):
                if table:
                    by_code.setdefault(code, set()).add(table.group(1))
    by_prefix: dict[str, set[str]] = {}
    for code, tables in by_code.items():
        by_prefix.setdefault(code[:2], set()).update(tables)

    def table_of(code: str) -> str | None:
        for found in (by_code.get(code), by_prefix.get(code[:2])):
            if found:
                return next(iter(found)) if len(found) == 1 else None
        return None

    return table_of


def derived_clause(g: Graph, cls: URIRef, table_of) -> str | None:
    """'Table T, CODE[ charN (V)]; ...' for every code class whose direct
    someValuesFrom restriction points at cls, or None."""
    refs = set()
    for restriction in g.subjects(OWL.someValuesFrom, cls):
        for code_cls in g.subjects(RDFS.subClassOf, restriction):
            parts = code_parts(g, code_cls) if isinstance(code_cls, URIRef) else None
            if parts:
                refs.add((parts[0], tuple(parts[1])))
    if not refs:
        return None

    def fmt(ref):
        code, chars = ref
        text = " ".join([code] + [f"char{n} ({v})" for n, v in chars])
        table = table_of(code)
        return f"Table {table}, {text}" if table else text

    def key(ref):
        table = table_of(ref[0])
        return (int(table) if table else 999, ref[0], ref[1])

    return "; ".join(fmt(r) for r in sorted(refs, key=key))


def read_clauses(csv_path: Path) -> dict[str, str]:
    """class_name -> din_clause for the rows that carry one."""
    with csv_path.open(encoding="utf-8", newline="") as f:
        return {r["class_name"]: r["din_clause"].strip() for r in csv.DictReader(f) if r["din_clause"].strip()}


def build_block(g: Graph, clauses: dict[str, str] | None = None) -> tuple[str, int, int]:
    clauses = clauses or {}
    unknown = sorted(set(clauses) - {local_name(s) for s in g.subjects(RDF.type, OWL.Class)})
    if unknown:
        raise ValueError(f"din_clause rows name classes not in the ontology: {unknown}")
    table_of = table_lookup(clauses)
    classes = sorted(
        (s for s in g.subjects(RDF.type, OWL.Class)
         if isinstance(s, URIRef) and str(s).startswith(SDCO_NS)),
        key=local_name,
    )
    lines, skipped = [], 0
    for cls in classes:
        path = code_path(g, cls) or clauses.get(local_name(cls)) or derived_clause(g, cls, table_of)
        if path is None:
            continue
        if g.value(cls, RDFS.isDefinedBy) is not None:
            skipped += 1
            continue
        lines.append(f':{local_name(cls)} rdfs:isDefinedBy "{_esc(f"{STANDARD}, {path}")}" .')
    block = BEGIN_MARKER + "\n" + "\n".join(lines) + "\n" + END_MARKER
    return block, len(lines), skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(REPO_ROOT / "SDCO.rdf"), help="Ontology file to update.")
    parser.add_argument("--csv", default=str(REPO_ROOT / "scripts" / "authoring" / "observation_comments.csv"),
                        help="Inventory whose din_clause column traces Observation classes.")
    parser.add_argument("--dry-run", action="store_true", help="Print the block; write nothing.")
    args = parser.parse_args()

    source = Path(args.source)
    base_text = strip_block(source.read_text(encoding="utf-8"))

    g = Graph()
    g.parse(data=base_text, format="turtle")

    block, n_added, n_skipped = build_block(g, read_clauses(Path(args.csv)))

    if args.dry_run:
        print(block)
        print(f"[dry-run] {n_added} annotation(s) to add, {n_skipped} class(es) already annotated")
        return 0

    source.write_text(base_text, encoding="utf-8", newline="\n")  # drop any prior block
    insert_before_footer(source, block)
    print(f"[done] wrote {n_added} annotation(s) to {source}; {n_skipped} class(es) already annotated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
