"""Apply human/AI-reviewed rdfs:comment values from a CSV into SDCO.rdf.

scripts/observation_comments.csv (written by a separate review pass, not this
script) carries one row per class under review:

    class_name,label,parent,existing_comment,din_clause,comment

Only class_name and comment are consumed here -- label/parent/existing_comment/
din_clause are human review aids and are ignored. A row with a blank comment
is skipped silently (the reviewer chose not to add one).

TEXT SPLICE, never an rdflib round-trip write: SDCO.rdf is a hand-formatted
Protege turtle export, and re-serializing it through rdflib would reformat the
whole file. Instead this script locates each class's declaration block
(":ClassName rdf:type owl:Class ;" ... the top-level "." that ends the Turtle
statement, found by tracking bracket depth and string-literal state so nested
"."s in blank nodes/strings don't confuse it) and inserts an rdfs:comment
predicate immediately before that terminating period, indented to match the
block's existing sibling predicate lines. See :BAB and :Angular in SDCO.rdf
for the target shape -- a plain string literal, no @en tag (unlike
rdfs:label), using a triple-quoted literal only when the comment contains a
quote or a newline.

Write policy: FILL GAPS, NEVER OVERWRITE. A class that already carries an
rdfs:comment anywhere in its block is left untouched and reported as skipped.

Validation runs fully before anything is written: every class_name must exist
as an owl:Class in SDCO.rdf, and all errors are collected and printed together
-- the file is left untouched if any are found. After writing, the file is
re-parsed with rdflib to confirm it still parses, the triple count must have
grown by exactly the number of comments applied, and the line count must have
grown by exactly the number of inserted lines (i.e. no line was deleted);
any failure restores the original text and aborts.

Usage:
    python scripts/apply_comments.py --csv scripts/observation_comments.csv --dry-run
    python scripts/apply_comments.py --csv scripts/observation_comments.csv
"""

import argparse
import csv
import re
import sys
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_node_codes import NODE, parse_any  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def read_rows(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, raw in enumerate(reader, start=2):  # +2: header is line 1
            rows.append(
                {
                    "line": i,
                    "class_name": (raw.get("class_name") or "").strip(),
                    "comment": (raw.get("comment") or "").strip(),
                }
            )
    return rows


def _class_exists(graph: Graph, name: str) -> bool:
    return (NODE[name], RDF.type, OWL.Class) in graph


def validate(rows: list[dict], graph: Graph) -> list[str]:
    errors = []
    for r in rows:
        name = r["class_name"]
        if not name:
            errors.append(f"row {r['line']}: missing class_name")
        elif not _class_exists(graph, name):
            errors.append(f"row {r['line']} ({name}): class ':{name}' not found in the ontology")
    return errors


def render_comment_literal(comment: str) -> str:
    """Plain-string literal (no @en), matching the 47 rdfs:comment values
    already in SDCO.rdf. Triple-quoted when the comment contains a quote or a
    newline; backslashes are always escaped."""
    escaped = comment.replace("\\", "\\\\")
    if '"' in comment or "\n" in comment:
        escaped = escaped.replace('"""', '\\"\\"\\"')
        return f'"""{escaped}"""'
    return f'"{escaped}"'


def _find_block_end(text: str, start: int) -> int:
    """Index just past the top-level '.' that terminates the Turtle statement
    beginning at `start`, tracking bracket depth ([]/()) and string-literal
    state so nested '.'s (in blank nodes or comment text) don't match."""
    i, n = start, len(text)
    depth = 0
    state = "normal"  # normal | single | triple
    while i < n:
        c = text[i]
        if state == "normal":
            if text.startswith('"""', i):
                state, i = "triple", i + 3
                continue
            if c == '"':
                state, i = "single", i + 1
                continue
            if c in "[(":
                depth += 1
            elif c in "])":
                depth -= 1
            elif c == "." and depth == 0:
                return i + 1
            i += 1
        elif state == "triple":
            if text.startswith('"""', i):
                state, i = "normal", i + 3
                continue
            i += 1
        else:  # single
            if c == "\\":
                i += 2
                continue
            if c == '"':
                state, i = "normal", i + 1
                continue
            i += 1
    raise ValueError("unterminated Turtle statement")


def _mask_strings(s: str) -> str:
    """Replace string-literal contents with 'x' (same length) so predicate
    keys can be searched for without matching text that merely looks like
    them inside a literal."""
    out = []
    i, n = 0, len(s)
    state = "normal"
    while i < n:
        c = s[i]
        if state == "normal":
            if s.startswith('"""', i):
                out.append('"""')
                state, i = "triple", i + 3
                continue
            if c == '"':
                out.append('"')
                state, i = "single", i + 1
                continue
            out.append(c)
            i += 1
        elif state == "triple":
            if s.startswith('"""', i):
                out.append('"""')
                state, i = "normal", i + 3
                continue
            out.append("x" if c != "\n" else "\n")
            i += 1
        else:  # single
            if c == "\\":
                out.append("xx")
                i += 2
                continue
            if c == '"':
                out.append('"')
                state, i = "normal", i + 1
                continue
            out.append("x")
            i += 1
    return "".join(out)


def locate_block(text: str, class_name: str) -> tuple[int, int]:
    """(start, end) indices of the class's full declaration statement, start
    at ':ClassName rdf:type owl:Class' and end just past the top-level '.'.
    Raises ValueError if not found, or found more than once (ambiguous)."""
    pattern = re.compile(r"^:" + re.escape(class_name) + r"\s+rdf:type\s+owl:Class\b", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        raise ValueError(f"could not locate declaration for ':{class_name}' in source text")
    if len(matches) > 1:
        raise ValueError(f"':{class_name}' declaration appears {len(matches)} times in source text -- ambiguous")
    start = matches[0].start()
    end = _find_block_end(text, start)
    return start, end


def block_has_comment(block_text: str) -> bool:
    return "rdfs:comment" in _mask_strings(block_text)


def block_indent(block_text: str) -> str:
    """Leading whitespace of the block's second line -- the column its
    sibling predicate lines are aligned to."""
    lines = block_text.splitlines()
    if len(lines) < 2:
        # No second predicate line to align to (not expected in SDCO.rdf,
        # every class carries at least rdfs:label) -- fall back to aligning
        # just past ":ClassName ".
        return " " * (len(lines[0].split(" rdf:type", 1)[0]) + 1)
    second = lines[1]
    return second[: len(second) - len(second.lstrip(" "))]


def apply_comment(text: str, class_name: str, comment: str) -> tuple[str, int] | None:
    """Insert `comment` as an rdfs:comment predicate into class_name's block.
    Returns (new_text, lines_inserted), or None if the class already has a
    comment (gap-fill only -- caller should count this as skipped)."""
    start, end = locate_block(text, class_name)
    block = text[start:end]
    if block_has_comment(block):
        return None

    indent = block_indent(block)
    # block ends with the statement's terminating '.'; strip back to the
    # last non-whitespace char before it (the end of the prior predicate's
    # object) so we can turn that line's trailing " ." into " ;\n<comment>".
    j = len(block) - 2
    while j >= 0 and block[j].isspace():
        j -= 1
    literal = render_comment_literal(comment)
    insertion = " ;\n" + indent + "rdfs:comment " + literal + " ."
    new_block = block[: j + 1] + insertion
    new_text = text[:start] + new_block + text[end:]
    return new_text, insertion.count("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", default=str(REPO_ROOT / "scripts" / "observation_comments.csv"), help="CSV of reviewed comments to apply.")
    parser.add_argument("--source", default=str(REPO_ROOT / "SDCO.rdf"), help="Ontology file to update.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print what would change; write nothing.")
    args = parser.parse_args()

    source = Path(args.source)
    csv_path = Path(args.csv)

    graph = parse_any(source)
    rows = read_rows(csv_path)

    errors = validate(rows, graph)
    if errors:
        print(f"[error] {len(errors)} validation error(s) -- nothing written:")
        for e in errors:
            print(f"  - {e}")
        return 1

    to_apply = [r for r in rows if r["comment"]]
    n_blank = len(rows) - len(to_apply)

    original_text = source.read_text(encoding="utf-8")
    text = original_text
    n_applied = 0
    n_already = 0
    lines_inserted = 0

    for r in to_apply:
        result = apply_comment(text, r["class_name"], r["comment"])
        if result is None:
            n_already += 1
            print(f"[skip] :{r['class_name']} already has an rdfs:comment -- left untouched")
            continue
        text, added = result
        n_applied += 1
        lines_inserted += added
        verb = "[dry-run] would apply" if args.dry_run else "[apply]"
        print(f"{verb} :{r['class_name']}")

    print(
        f"[summary] applied={n_applied} skipped-already-commented={n_already} "
        f"skipped-blank={n_blank} (of {len(rows)} row(s))"
    )

    if args.dry_run or n_applied == 0:
        if not args.dry_run and n_applied == 0:
            print("[done] nothing to write.")
        else:
            print("[dry-run] nothing written.")
        return 0

    triples_before = len(graph)
    lines_before = len(original_text.splitlines())

    source.write_text(text, encoding="utf-8", newline="\n")

    try:
        check_graph = Graph()
        check_graph.parse(str(source), format="turtle")
        lines_after = len(text.splitlines())
        assert lines_after - lines_before == lines_inserted, (
            f"line count grew by {lines_after - lines_before}, expected {lines_inserted}"
        )
        assert len(check_graph) - triples_before == n_applied, (
            f"triple count grew by {len(check_graph) - triples_before}, expected {n_applied}"
        )
    except Exception as exc:
        source.write_text(original_text, encoding="utf-8", newline="\n")
        print(f"[error] post-write safety check failed, reverted {source}: {exc}")
        return 1

    print(f"[done] wrote {n_applied} comment(s) to {source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
