"""Build a lightweight benchmark copy of m150-onto-parsed-dwa.rdf for fast
materialization benchmarking.

Picks one ConditionReport individual per distinct hasConditionCode value (so the
damage-code taxonomy is still fully exercised), then follows object-property links
outward a couple hops (isChildOf -> InspectionReport -> inspects/hasInspector/... )
so no dangling references are left. Writes benchmark/m150-onto-parsed-dwa-lite.rdf.

Run: python scripts/make_benchmark_dataset.py
"""

from pathlib import Path

from rdflib import RDF, Graph, Namespace, URIRef

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT.parent / "m150-onto" / "m150-onto-parsed-dwa.rdf"
OUTPUT = REPO_ROOT / "benchmark" / "m150-onto-parsed-dwa-lite.rdf"
M150 = Namespace("https://l-jamora.github.io/m150-onto#")
CLOSURE_HOPS = 2


def pick_seed_individuals(g: Graph) -> set:
    seen_codes = set()
    seeds = set()
    for ind in g.subjects(RDF.type, M150.ConditionReport):
        code = g.value(ind, M150.hasConditionCode)
        if code is None or str(code) in seen_codes:
            continue
        seen_codes.add(str(code))
        seeds.add(ind)
    return seeds


def expand_closure(g: Graph, seeds: set, hops: int) -> set:
    included = set(seeds)
    frontier = set(seeds)
    for _ in range(hops):
        next_frontier = set()
        for s in frontier:
            for _, o in g.predicate_objects(s):
                if isinstance(o, URIRef) and o not in included:
                    included.add(o)
                    next_frontier.add(o)
        frontier = next_frontier
    return included


def main() -> int:
    g = Graph()
    g.parse(SOURCE.as_uri(), format="xml")

    seeds = pick_seed_individuals(g)
    included = expand_closure(g, seeds, CLOSURE_HOPS)

    out = Graph()
    for prefix, ns in g.namespaces():
        out.bind(prefix, ns)
    for s, p, o in g:
        if s == URIRef("https://l-jamora.github.io/m150-onto-parsed") or s in included:
            out.add((s, p, o))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.serialize(destination=str(OUTPUT), format="xml")
    n_reports = len(list(out.subjects(RDF.type, M150.ConditionReport)))
    print(f"[done] wrote {len(out)} triples ({n_reports} ConditionReports, {len(included)} individuals) to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
