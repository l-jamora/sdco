"""Restore owl:equivalentClass axioms deleted by commit 5c38450.

That commit ("Directly imports M150-Onto.rdf...") deleted, as collateral
damage while removing genuinely-duplicated old M150-Onto class/property
definitions, ~243 owl:equivalentClass axioms that link literal
hasConditionCode/hasCharacterization1/hasCharacterization2 values to SDCO's
damage-code classes (e.g. :BAK, :BAK1_Z). Those axioms are what let HermiT
classify a generic ConditionReport individual into a damage-code class in
the first place -- without them, scripts/materialize_object_properties.py
can never materialize anything.

This script surgically splices the missing owl:equivalentClass clause back
into each class that still exists in the current SDCO.rdf, using commit
e0a0242 (the last commit before the deletion) as the source. It does a
targeted text splice keyed on each class's "<subject> rdf:type owl:Class ;"
declaration line rather than a full rdflib round-trip, so the rest of the
~6500-line file's formatting/ordering is left untouched.

Usage: python scripts/restore_equivalentclass_axioms.py [--target FILE] [--dry-run]
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OLD_COMMIT = "e0a0242"

CLASS_LINE_RE = re.compile(r"^(:\S+|<[^>]+>) rdf:type owl:Class ;$", re.MULTILINE)


def get_old_text() -> str:
    result = subprocess.run(
        ["git", "show", f"{OLD_COMMIT}:SDCO.rdf"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8")


def find_class_lines(text: str) -> dict:
    """Map subject token -> (line_start, line_end) for each
    '<subject> rdf:type owl:Class ;' declaration. line_end is the offset
    right after the line's trailing newline."""
    out = {}
    for m in CLASS_LINE_RE.finditer(text):
        subject = m.group(1)
        line_end = m.end() + 1  # past the '\n'
        out.setdefault(subject, (m.start(), line_end))
    return out


def extract_equivalentclass_clause(text: str, after_offset: int) -> str | None:
    """If the text immediately following a class's 'rdf:type owl:Class ;'
    line starts with 'owl:equivalentClass [...]', return the verbatim
    clause text (from 'owl:equivalentClass' through the matching close
    bracket, inclusive). Returns None if no equivalentClass predicate is
    present there."""
    rest = text[after_offset:]
    stripped = rest.lstrip(" ")
    if not stripped.startswith("owl:equivalentClass"):
        return None

    leading_ws = len(rest) - len(stripped)
    start = after_offset + leading_ws
    bracket_start = text.index("[", start)
    if text[start:bracket_start].strip() != "owl:equivalentClass":
        return None

    depth = 0
    i = bracket_start
    while i < len(text):
        ch = text[i]
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    raise ValueError("unbalanced brackets while scanning owl:equivalentClass clause")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        default=str(REPO_ROOT / "SDCO.rdf"),
        help="File to restore axioms into (default: SDCO.rdf).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only, don't write the target file.")
    args = parser.parse_args()
    target_path = Path(args.target)

    old_text = get_old_text()
    current_text = target_path.read_text(encoding="utf-8")

    old_classes = find_class_lines(old_text)
    current_classes = find_class_lines(current_text)

    restored = []
    already_present = []
    missing_in_old = []
    unbalanced = []

    # Collect (insertion_offset, clause_text) pairs, applied back-to-front
    # so earlier offsets stay valid as we splice.
    insertions = []

    for subject, (_, cur_line_end) in current_classes.items():
        existing_clause = None
        try:
            existing_clause = extract_equivalentclass_clause(current_text, cur_line_end)
        except ValueError:
            pass
        if existing_clause is not None:
            already_present.append(subject)
            continue

        if subject not in old_classes:
            missing_in_old.append(subject)
            continue

        _, old_line_end = old_classes[subject]
        try:
            clause = extract_equivalentclass_clause(old_text, old_line_end)
        except ValueError:
            unbalanced.append(subject)
            continue

        if clause is None:
            missing_in_old.append(subject)
            continue

        insertions.append((cur_line_end, subject, clause))
        restored.append(subject)

    insertions.sort(key=lambda triple: triple[0], reverse=True)
    new_text = current_text
    for offset, subject, clause in insertions:
        # The clause's continuation lines are spliced in verbatim (their
        # original multi-line indentation from the old file already matches
        # the current file's convention, since class subject tokens are
        # unchanged). Only the first line's indentation was stripped by
        # extract_equivalentclass_clause() to detect the predicate -- restore
        # it here per the file's convention (subject token length + 1 space).
        indent = " " * (len(subject) + 1)
        new_text = new_text[:offset] + indent + clause + " ;\n" + new_text[offset:]

    print(f"[restore] classes with equivalentClass restored : {len(restored)}")
    print(f"[restore] classes already had equivalentClass    : {len(already_present)}")
    print(f"[restore] classes with no old equivalentClass    : {len(missing_in_old)}")
    if unbalanced:
        print(f"[restore] WARNING: unbalanced-bracket extraction skipped for: {unbalanced}", file=sys.stderr)

    if args.dry_run:
        print(f"[restore] --dry-run: not writing {target_path}")
        return 0

    if restored:
        target_path.write_text(new_text, encoding="utf-8")
        print(f"[restore] wrote {target_path}")
    else:
        print("[restore] nothing to do")

    return 0


if __name__ == "__main__":
    sys.exit(main())
