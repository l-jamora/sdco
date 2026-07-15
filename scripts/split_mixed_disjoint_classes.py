"""Split AllDisjointClasses blocks that wrongly mix independent
characterization dimensions.

Several damage-code families (e.g. BAF: hasCharacterization1-keyed :BAF1_A..Z
and hasCharacterization2-keyed :BAF2_A..Z) have a single owl:AllDisjointClasses
block listing *both* families as pairwise disjoint. hasCharacterization1
("nature of damage") and hasCharacterization2 ("cause of damage") are
independent dimensions -- a real condition report can legitimately be, e.g.,
both :BAF1_D and :BAF2_A at once. Treating them as mutually exclusive makes
the ontology inconsistent as soon as any individual is actually classified
into both (which scripts/restore_equivalentclass_axioms.py's restored axioms
now make possible). This is the same class of bug as the pre-existing
:BAB2_A hasDamageOrientation bug already fixed once (see
docs/Handover_Materialize_Object_Properties.md).

This script finds every owl:AllDisjointClasses block, groups its members by
the differentiating property used in their owl:equivalentClass restriction
(read from the class's own definition elsewhere in the file -- e.g.
hasCharacterization1 vs hasCharacterization2 vs hasConditionCode for
undifferentiated base codes), and if a block's members span more than one
such property, splits it into one block per property group. Members whose
differentiating property can't be determined are left in a block by
themselves (reported, not silently dropped).

Usage: python scripts/split_mixed_disjoint_classes.py [--target FILE] [--dry-run]
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DISJOINT_BLOCK_RE = re.compile(
    r"\[ rdf:type owl:AllDisjointClasses ;\n"
    r"  owl:members \( (?P<members>.*?)\n"
    r"              \)\n"
    r"\] \.\n",
    re.S,
)
ONPROPERTY_RE = re.compile(r"owl:onProperty <([^>]+)>")


def differentiating_property(text: str, subject: str) -> str | None:
    """The property used in `subject`'s owl:equivalentClass restriction --
    for intersectionOf patterns (refined _1_X/_2_X subclasses) this is the
    *second* onProperty in the clause (the base class's own onProperty comes
    first via its nested restriction); for simple patterns (base codes) it's
    the only onProperty."""
    for m in re.finditer(re.escape(subject) + r" rdf:type owl:Class ;\n", text):
        start = m.end()
        rest = text[start : start + 2000]
        if not rest.lstrip(" ").startswith("owl:equivalentClass"):
            continue
        props = ONPROPERTY_RE.findall(rest[: rest.index("] ;") + 3] if "] ;" in rest else rest)
        if not props:
            continue
        return props[-1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=str(REPO_ROOT / "SDCO.rdf"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    target_path = Path(args.target)

    text = target_path.read_text(encoding="utf-8")

    split_blocks = []  # (start, end, [ (property, [members]) ... ])
    unresolved = []

    for m in DISJOINT_BLOCK_RE.finditer(text):
        members = [tok.strip() for tok in m.group("members").split("\n")]
        members = [tok for tok in members if tok]

        groups: dict[str | None, list[str]] = {}
        for subject in members:
            prop = differentiating_property(text, subject)
            if prop is None:
                unresolved.append(subject)
            groups.setdefault(prop, []).append(subject)

        if len(groups) > 1:
            split_blocks.append((m.start(), m.end(), list(groups.values())))

    if unresolved:
        print(f"[split] WARNING: could not determine differentiating property for: {unresolved}", file=sys.stderr)

    print(f"[split] AllDisjointClasses blocks needing a split: {len(split_blocks)}")

    new_text = text
    for start, end, groups in sorted(split_blocks, key=lambda t: t[0], reverse=True):
        replacement_parts = []
        for group_members in groups:
            if len(group_members) < 2:
                continue  # a disjointness block of one member is meaningless; drop it
            members_text = ("\n" + " " * 16).join(group_members)
            replacement_parts.append(
                "[ rdf:type owl:AllDisjointClasses ;\n" f"  owl:members ( {members_text}\n" "              )\n" "] .\n"
            )
        replacement = "\n\n".join(replacement_parts) + "\n"
        new_text = new_text[:start] + replacement + new_text[end:]

    if args.dry_run:
        print(f"[split] --dry-run: not writing {target_path}")
        return 0

    if split_blocks:
        target_path.write_text(new_text, encoding="utf-8")
        print(f"[split] wrote {target_path}")
    else:
        print("[split] nothing to do")

    return 0


if __name__ == "__main__":
    sys.exit(main())
