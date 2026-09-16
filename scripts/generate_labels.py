"""Derive an @en rdfs:label for every SDCO class from its name and axioms, and
append them to SDCO.rdf as one marker-delimited block at the end of the file.

SDCO declares ~1,164 classes and carries exactly one rdfs:label (on the
ontology node). Protege, SPARQL clients and third parties therefore see only
IRI local names like :BAB2_A. build_explainer.py already computes the display
text we need (humanize() / meaning_of()) and throws it away every build; this
script persists it.

Write policy: FILL GAPS, NEVER OVERWRITE. A class that already has an
rdfs:label anywhere in the file is left untouched. Regeneration is idempotent
because the generated block is stripped out *before* parsing, so a prior run's
labels are never mistaken for hand-authored ones.

The block is re-assertion-only Turtle (subjects restated in a later
statement), so no existing line of SDCO.rdf is edited -- do NOT round-trip the
file through rdflib.

Usage:
    python scripts/generate_labels.py --dry-run
    python scripts/generate_labels.py
"""

import argparse
import re
import sys
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph
from rdflib.collection import Collection
from rdflib.term import URIRef

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_explainer import humanize, local_name, meaning_of  # noqa: E402
from generate_node_codes import insert_before_footer  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SDCO_NS = "https://l-jamora.github.io/sdco#"

BEGIN_MARKER = "###  ---- BEGIN GENERATED LABELS (scripts/generate_labels.py -- do not hand-edit) ----"
END_MARKER = "###  ---- END GENERATED LABELS ----"
_BLOCK_RE = re.compile(
    r"\n*" + re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER) + r"\n*",
    re.DOTALL,
)

_SIMPLE_NAME_RE = re.compile(r"^[A-Z][A-Za-z]*$")
_CHAR_PROP_RE = re.compile(r"hasCharacterization(\d)$")


def strip_block(text: str) -> str:
    """Remove a previously generated label block; no-op if none present."""
    return _BLOCK_RE.sub("\n", text)


def _char_restriction(g: Graph, node):
    """(N, V) if node is a Restriction on m150#hasCharacterizationN with a
    hasValue filler, else None."""
    if (node, RDF.type, OWL.Restriction) not in g:
        return None
    prop = g.value(node, OWL.onProperty)
    val = g.value(node, OWL.hasValue)
    if prop is None or val is None:
        return None
    m = _CHAR_PROP_RE.search(str(prop))
    return (m.group(1), str(val)) if m else None


def compose(g: Graph, cls: URIRef) -> str:
    """Label for one class; first matching branch wins.

    1. equivalentClass -> plain Restriction on hasConditionCode/hasValue
       -> "{code}" or "{code} ({filler})".
    2. equivalentClass -> intersectionOf ( :Base [char restriction] )
       -> "{Base} char{N}={V}" or "... ({filler})".
    3. name is ^[A-Z][A-Za-z]*$  -> humanize(name).
    4. otherwise                 -> name verbatim (the :Schlauchliner_* family).

    {filler} is meaning_of() -- the humanized someValuesFrom filler(s) of the
    class's own direct rdfs:subClassOf restrictions; the parenthetical is
    omitted when it is None. {N}/{V}/{Base} are read from the axiom, never the
    name (e.g. :BDD_A is a char1 class with no digit in its name).
    """
    name = local_name(cls)

    for eq in g.objects(cls, OWL.equivalentClass):
        if (eq, RDF.type, OWL.Restriction) in g:
            prop = g.value(eq, OWL.onProperty)
            val = g.value(eq, OWL.hasValue)
            if prop is not None and str(prop).endswith("hasConditionCode") and val is not None:
                filler = meaning_of(g, cls)
                return f"{val} ({filler})" if filler else str(val)

        inter = g.value(eq, OWL.intersectionOf)
        if inter is not None:
            members = list(Collection(g, inter))
            base = next((m for m in members if isinstance(m, URIRef)), None)
            char = next((c for c in (_char_restriction(g, m) for m in members) if c), None)
            if base is not None and char is not None:
                core = f"{local_name(base)} char{char[0]}={char[1]}"
                filler = meaning_of(g, cls)
                return f"{core} ({filler})" if filler else core

    if _SIMPLE_NAME_RE.match(name):
        return humanize(name)
    return name


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_block(g: Graph) -> tuple[str, int, int]:
    classes = sorted(
        (s for s in g.subjects(RDF.type, OWL.Class)
         if isinstance(s, URIRef) and str(s).startswith(SDCO_NS)),
        key=local_name,
    )
    lines, skipped = [], 0
    for cls in classes:
        if g.value(cls, RDFS.label) is not None:
            skipped += 1
            continue
        lines.append(f':{local_name(cls)} rdfs:label "{_esc(compose(g, cls))}"@en .')
    block = BEGIN_MARKER + "\n" + "\n".join(lines) + "\n" + END_MARKER
    return block, len(lines), skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(REPO_ROOT / "SDCO.rdf"), help="Ontology file to update.")
    parser.add_argument("--dry-run", action="store_true", help="Print the block; write nothing.")
    args = parser.parse_args()

    source = Path(args.source)
    base_text = strip_block(source.read_text(encoding="utf-8"))

    g = Graph()
    g.parse(data=base_text, format="turtle")

    block, n_labeled, n_skipped = build_block(g)

    if args.dry_run:
        print(block)
        print(f"[dry-run] {n_labeled} label(s) to add, {n_skipped} class(es) already labeled")
        return 0

    source.write_text(base_text, encoding="utf-8", newline="\n")  # drop any prior block
    insert_before_footer(source, block)
    print(f"[done] wrote {n_labeled} label(s) to {source}; {n_skipped} class(es) already labeled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
