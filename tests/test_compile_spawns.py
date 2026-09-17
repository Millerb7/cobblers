"""tools/compile_spawns.py: the per-route species lists in data/spawns.json are authored, so the compiler must reproduce them.

Protects: a compiled route pool never contains a species outside its authored route_species_selection, and every
authored species is either compiled or reported as unreached. Also that output is deterministic.
Not covered: whether Cobblemon loads the files (runtime), or whether the box-to-sub-region sampling matches the one-off
compilation it replaced beyond the 15 boundary boxes documented in the tool.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_spawns as C  # noqa: E402


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def test_compiled_species_reproduce_the_authored_selection():
    spawns, routes = load("spawns.json"), load("routes.json")
    files, route_summaries, _ = C.build(spawns, routes)
    selection = spawns["route_species_selection"]
    assert {r["route_id"] for r in route_summaries} == set(selection)
    for summ in route_summaries:
        authored = set(selection[summ["route_id"]]["species"])
        compiled = {e["pokemon"] for e in json.loads(files["data/cobblers/spawn_pool_world/routes/%s.json" % summ["route_id"]])["spawns"]}
        assert compiled <= authored, (summ["route_id"], sorted(compiled - authored))
        assert compiled | set(summ["selected_species_not_reached"]) == authored, summ["route_id"]


def test_species_outside_the_selection_never_compile():
    spawns, routes = load("spawns.json"), load("routes.json")
    rid = routes["routes"][0]["id"]
    keep = sorted(spawns["route_species_selection"][rid]["species"])[:3]
    spawns["route_species_selection"][rid]["species"] = keep
    files, route_summaries, _ = C.build(spawns, routes)
    compiled = {e["pokemon"] for e in json.loads(files["data/cobblers/spawn_pool_world/routes/%s.json" % rid])["spawns"]}
    assert compiled <= set(keep)


def test_compilation_is_deterministic():
    spawns, routes = load("spawns.json"), load("routes.json")
    assert C.build(spawns, routes)[0] == C.build(spawns, routes)[0]
