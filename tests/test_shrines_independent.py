"""The wayside shrines (e24698c): data/shrines.json, tools/shrines.py, tools/shrines_audit.py and reapply step R16D.

Written by the test author, not by the session that built the shrines.

Three parts:
  1. The audit's claims, each proved on a synthetic root whose every value is hand-computed: a 256 by 256 heightmap at
     64.4 with one column line at 64.6 (rounded 65: a floor()-seated shrine is one block low there), a town, a house,
     a plan, a leg, an event site, painted water and trees, a pending water change, another pack's build, and a clean
     shrine function beside near misses of each. The clean one must pass (so the audit is not refusing everything),
     and each one-line breakage must be named (so it is not passing everything). The generator is poisoned in
     sys.modules while the audit runs, so the audit is shown to decide on its own.
  2. The real data, recomputed here from committed data, not from shrines.py's Clearance: the columns each shrine
     writes (they do not depend on the ground) against data/routes.json corridors, data/scenes.json event sites, the
     settlements' street polylines, every placed building whose size this checkout can read, data/towns.json (the
     sea town, the jungle ruins, the shrine's own town) and each other; the block list against data/spawn_blocks.json
     and the 1.21.1 jar; each function's force-loading, by a simulator of its own; R16D against the data.
  3. With the canonical heightmap (slow; SKIPS without COBBLERS_SOURCE_ROOT): every column's lowest block is one over
     round(h), none at or under the sea level. With the local-only inputs (derived/water_shape/changed.npy,
     build/paint, the built pack) the real water, trees and the full audit run; without them they SKIP.

A skip is not a pass. Not covered: whether a shrine reads as small and local, what Codex writes for it, anything in a
world (the functions have not run on staging), and the lots and street cells of derived/towns plans when absent.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import types
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import shrines as S  # noqa: E402  (the generator: used only to produce blocks and commands, never as the oracle)
import shrines_audit as SA  # noqa: E402

DATA = json.loads((ROOT / "data" / "shrines.json").read_text(encoding="utf-8"))
RULES = DATA["rules"]
ALLOWED = set(DATA["blocks"]["ids"])
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
TOWNS = {t["id"]: t["footprint"] for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
SHRINES = DATA["shrines"]
IDS = [s["id"] for s in SHRINES]


# ------------------------------------------------------------------------------------------------ small helpers
class Open:
    """A clearance that refuses nothing: the generator's own checks are not the oracle here."""

    def blocked(self, x, z):
        return None


def name(state):
    return re.split(r"[\[{]", state, 1)[0]


def box_distance(fp, x, z):
    return math.hypot(max(fp["min_x"] - x, 0, x - fp["max_x"]), max(fp["min_z"] - z, 0, z - fp["max_z"]))


def seg_distance(px, pz, a, b):
    (ax, az), (bx, bz) = a, b
    vx, vz = bx - ax, bz - az
    L2 = vx * vx + vz * vz
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * vx + (pz - az) * vz) / L2))
    return math.hypot(px - (ax + t * vx), pz - (az + t * vz))


def columns(spec):
    """The (x, z) a shrine writes. They do not depend on the ground (only the Y does), so a flat ground gives them."""
    blocks, _floor = S.place(spec, lambda x, z: 64, Open())
    return sorted({(x, z) for x, _y, z, _s in blocks})


def chequer(x, z):
    """Ground falling by one on every other column: every kind then gets a foundation course somewhere."""
    return 64 - ((x + z) % 2)


def held_violations(lines):
    """[(line, why)] for a block write into a chunk not force-loaded at that point, and chunks left held at the end.
    A simulator of its own (not tools/function_limits.py)."""
    held, bad = set(), []

    def chunks(x0, z0, x1, z1):
        return {(cx, cz) for cx in range(min(x0, x1) // 16, max(x0, x1) // 16 + 1)
                for cz in range(min(z0, z1) // 16, max(z0, z1) // 16 + 1)}
    for raw in lines:
        s = raw.strip()
        m = re.match(r"forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$", s)
        if m:
            c = chunks(*(int(v) for v in m.groups()[1:]))
            held = held | c if m.group(1) == "add" else held - c
            continue
        m = re.match(r"setblock (-?\d+) -?\d+ (-?\d+) ", s)
        if m:
            need = chunks(int(m.group(1)), int(m.group(2)), int(m.group(1)), int(m.group(2)))
        else:
            m = re.match(r"fill (-?\d+) -?\d+ (-?\d+) (-?\d+) -?\d+ (-?\d+) ", s)
            if not m:
                continue
            need = chunks(*(int(v) for v in m.groups()))
        if not need <= held:
            bad.append((s, "writes into unheld chunk(s) %s" % sorted(need - held)[:3]))
    if held:
        bad.append(("(end)", "chunks still force-loaded: %s" % sorted(held)[:3]))
    return bad


# ================================================================================ 1. the audit, on a synthetic root
N = 256
SHRINE_AT = (100, 100)
# the clean function's solid writes: a 3 by 3 base one over round(h) (x 101 stands on 65, the rest on 64), a second
# course and a cap on the centre, a candle on a corner
CLEAN = (["# fixture shrine s1", "forceload add 96 96 111 111",
          "fill 99 65 99 101 70 101 minecraft:air replace #minecraft:replaceable"]
         + ["setblock %d %d %d minecraft:cobblestone" % (x, 66 if x == 101 else 65, z)
            for x in (99, 100, 101) for z in (99, 100, 101)]
         + ["setblock 100 66 100 minecraft:stone", "setblock 100 67 100 minecraft:chiseled_stone_bricks",
            "setblock 99 66 99 minecraft:candle[candles=1,lit=true]", "forceload remove 96 96 111 111"])


def base_fixture():
    heights = np.full((N, N), 64.4, dtype=np.float32)
    heights[:, 101] = 64.6                                   # round 65, floor 64
    fx = {
        "heights": heights,
        "shrines": {"schema": "cobblers.shrines/1", "rules": dict(RULES),
                    "blocks": {"ids": ["minecraft:cobblestone", "minecraft:stone", "minecraft:chiseled_stone_bricks",
                                       "minecraft:candle", "minecraft:poppy"]},
                    "shrines": [{"id": "s1", "name": "fixture (working name)", "settlement": "town_a", "kind": "cairn",
                                 "at": list(SHRINE_AT), "facing": "north", "why": "fixture", "story": "for Codex",
                                 "palette": {}}]},
        "spawn": {"blocks": {"minecraft:poppy": ["a spawn entry"]}},
        "towns": {"towns": [
            {"id": "town_a", "footprint": {"min_x": 110, "max_x": 150, "min_z": 90, "max_z": 130}},
            {"id": "sea_town", "footprint": {"min_x": 200, "max_x": 250, "min_z": 200, "max_z": 250}},
            {"id": "jungle_ruins", "footprint": {"min_x": 0, "max_x": 10, "min_z": 240, "max_z": 250}}]},
        # near misses: the house 3 east (the audit keeps 2), the data street at z 106 width 3 (cells 105-107)
        "placements": {"settlements": {"town_a": {"plan": {"streets": [
            {"id": "st", "polyline": [[104, 106], [150, 106]], "width": 3}]}}},
            "placements": [{"id": "house_1", "settlement": "town_a", "kind": "house",
                            "position": {"x": 104, "z": 99}, "size": [3, 4, 3], "rotation": "none"}]},
        # the plan: a lot and a street's cells beside the shrine, not under it
        "plan": {"lots": [{"id": "L1", "rect": [103, 95, 105, 97]}],
                 "streets": {"s_plan": {"cells": [[104, 64, 90, 110]]}}},
        "critical": {"legs": [{"polyline": [[0, 10], [250, 10]]}]},
        # the corridor 4 south of the shrine's last row (the margin is 3)
        "routes": {"routes": [{"id": "r1", "corridor": {"polyline": [{"x": 0, "z": 105}, {"x": 250, "z": 105}]}}]},
        "scenes": {"scenes": [{"id": "ev1", "area": {"from": [103, 60, 90], "to": [108, 70, 95]}}]},
        "water": [(10, 20, 10, 20)],                            # painted water, far
        "trees": [(106, 100)],                                 # 5 east of x 101: outside tree_reach 4
        "changed": [(110, 100)],                               # 9 east of x 101: outside the 8
        "other": ["setblock 104 65 100 minecraft:stone"],      # 3 east of x 101: the audit keeps 2
        "function": list(CLEAN),
        "index": ["s1"],
        "write_critical": True,
        "write_changed": True,
    }
    return fx


class FakeGround:
    def __init__(self, heights):
        self.heights = heights
        self.world = {"vertical": {"sea_level": 50}}
        self.ox = self.oz = 0

    def __call__(self, x, z):
        return int(np.round(self.heights[int(z), int(x)]))


def write_root(root, fx):
    from PIL import Image

    def dump(rel, obj):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj), encoding="utf-8")
    dump("data/shrines.json", fx["shrines"])
    dump("data/spawn_blocks.json", fx["spawn"])
    dump("data/towns.json", fx["towns"])
    dump("data/placements.json", fx["placements"])
    dump("data/routes.json", fx["routes"])
    dump("data/scenes.json", fx["scenes"])
    dump("derived/towns/town_a_plan.json", fx["plan"])
    if fx["write_critical"]:
        dump("derived/routes/critical_legs.json", fx["critical"])
    water = np.zeros((N, N), dtype=np.uint8)
    for x0, x1, z0, z1 in fx["water"]:
        water[z0:z1 + 1, x0:x1 + 1] = 255
    trees = np.zeros((N, N), dtype=np.uint8)
    for x, z in fx["trees"]:
        trees[z, x] = 255
    (root / "build" / "paint").mkdir(parents=True, exist_ok=True)
    Image.fromarray(water).save(root / "build" / "paint" / "water.png")
    Image.fromarray(trees).save(root / "build" / "paint" / "trees.png")
    dump("build/paint/manifest.json", {"water": [{"x": 0, "z": 0, "mask": "water.png"}],
                                       "objects": [{"map": "trees.png"}]})
    if fx["write_changed"]:
        ch = np.zeros((N, N), dtype=bool)
        for x, z in fx["changed"]:
            ch[z, x] = True
        (root / "derived" / "water_shape").mkdir(parents=True, exist_ok=True)
        np.save(root / "derived" / "water_shape" / "changed.npy", ch)
    other = root / "build" / "datapacks" / "other_pack" / "data" / "x" / "function"
    other.mkdir(parents=True, exist_ok=True)
    (other / "f.mcfunction").write_text("\n".join(fx["other"]) + "\n", encoding="utf-8")
    pack = root / "build" / "datapacks" / "cobblers_shrines"
    fdir = pack / "data" / "cobblers" / "function" / "shrines"
    fdir.mkdir(parents=True, exist_ok=True)
    if fx["function"] is not None:
        (fdir / "s1.mcfunction").write_text("\n".join(fx["function"]) + ("\n" if fx["function"] else ""),
                                            encoding="utf-8")
    (fdir / "index.txt").write_text("\n".join(fx["index"]) + "\n", encoding="utf-8")
    return pack


@pytest.fixture
def run_audit(tmp_path, monkeypatch):
    """(problems, writes) of tools/shrines_audit.py over the fixture, the generator made unimportable."""
    import ground as G
    import town_character as TC
    import town_dressing_audit as TA

    def go(fx):
        root = tmp_path / ("root%d" % go.n)
        go.n += 1
        pack = write_root(root, fx)
        with monkeypatch.context() as m:
            poison = types.ModuleType("shrines")
            poison.__getattr__ = lambda n: (_ for _ in ()).throw(AssertionError("the audit used the generator: " + n))
            m.setitem(sys.modules, "shrines", poison)
            m.setattr(SA, "ROOT", root)
            m.setattr(TA, "ROOT", root)
            m.setattr(G, "Ground", lambda source_root=None, world_path=None: FakeGround(fx["heights"]))
            m.setattr(TC, "default_pack_dir", lambda: None)
            m.setattr(TC, "default_vanilla_jar", lambda: None)
            m.setattr(SA, "vanilla_blocks", lambda: set(fx["shrines"]["blocks"]["ids"]) | {"minecraft:diamond_block"})
            return SA.audit(pack, None)
    go.n = 0
    return go


def test_the_audit_passes_a_clean_shrine_beside_near_misses_of_everything_it_checks(run_audit):
    # Without it an audit that refuses everything (or measures a margin wrong by one) would look like a working one.
    problems, total = run_audit(base_fixture())
    assert problems == []
    assert total == 9 + 3 + 3 * 3 * 6                         # 12 solid writes and the 54 of the clearing fill


def _swap(fx, old, new):
    fx["function"] = [new if line == old else line for line in fx["function"]]
    assert new in fx["function"], "the fixture has no line %r" % old


def _floating(fx):
    _swap(fx, "setblock 99 65 99 minecraft:cobblestone", "setblock 99 66 99 minecraft:cobblestone")


def _buried(fx):
    _swap(fx, "setblock 99 65 99 minecraft:cobblestone", "setblock 99 64 99 minecraft:cobblestone")


def _seated_by_floor(fx):
    # x 101's ground is 64.6: round() says 65 and the column starts at 66; floor() would start it at 65
    for z in (99, 100, 101):
        _swap(fx, "setblock 101 66 %d minecraft:cobblestone" % z, "setblock 101 65 %d minecraft:cobblestone" % z)


def _plan_street(fx):
    fx["plan"]["streets"]["s_plan"]["cells"].append([100, 64, 95, 99])


def _data_street(fx):
    fx["placements"]["settlements"]["town_a"]["plan"]["streets"].append(
        {"id": "st2", "polyline": [[90, 99], [99, 99]], "width": 1})


def _lot(fx):
    fx["plan"]["lots"].append({"id": "L2", "rect": [101, 101, 103, 103]})


def _building(fx):
    fx["placements"]["placements"][0]["position"] = {"x": 103, "z": 99}      # 2 east of x 101


def _event_site(fx):
    fx["scenes"]["scenes"].append({"id": "ev2", "area": {"from": [101, 60, 101], "to": [102, 70, 102]}})


def _route_leg(fx):
    fx["routes"]["routes"][0]["corridor"]["polyline"] = [{"x": 0, "z": 103}, {"x": 250, "z": 103}]   # 2 from z 101


def _critical_leg(fx):
    fx["critical"]["legs"].append({"polyline": [[100, 0], [100, 98]]})       # ends 1 north of the shrine


def _no_critical(fx):
    fx["write_critical"] = False


def _spawn_block(fx):
    _swap(fx, "setblock 99 66 99 minecraft:candle[candles=1,lit=true]", "setblock 99 66 99 minecraft:poppy")


def _unlisted(fx):
    _swap(fx, "setblock 100 67 100 minecraft:chiseled_stone_bricks", "setblock 100 67 100 minecraft:diamond_block")


def _sea_town(fx):
    fx["towns"]["towns"][1]["footprint"] = {"min_x": 140, "max_x": 170, "min_z": 140, "max_z": 170}   # 55 away


def _jungle_ruins(fx):
    fx["towns"]["towns"][2]["footprint"] = {"min_x": 40, "max_x": 60, "min_z": 60, "max_z": 80}


def _far_from_town(fx):
    fx["shrines"]["rules"]["max_from_town"] = 5                                # the town is 9 away


def _water_export(fx):
    fx["changed"].append((106, 100))                                          # 5 east of x 101


def _no_water_export(fx):
    fx["write_changed"] = False


def _painted_water(fx):
    fx["water"].append((100, 100, 100, 100))


def _under_sea(fx):
    fx["heights"][100, 100] = 49.0


def _tree(fx):
    fx["trees"].append((104, 101))                                            # 3 east of x 101


def _other_build(fx):
    fx["other"].append("fill 102 60 96 103 70 97 minecraft:stone")            # 1 east and 2 north: a box's corner


def _empty(fx):
    fx["function"] = []


def _missing(fx):
    fx["function"] = None


def _index(fx):
    fx["index"] = ["s1", "s2"]


def _unloaded(fx):
    fx["function"] = [l for l in fx["function"] if not l.startswith("forceload")]


def _too_many(fx):
    fx["function"] = fx["function"][:-1] + ["setblock 100 %d 100 minecraft:stone" % y for y in range(68, 118)] \
        + fx["function"][-1:]


# (case, the breakage, a phrase the audit's problem must hold). Each row is a claim of the audit's docstring; without
# its row the audit could stop catching that one and every other test here would stay green.
CASES = [
    ("floating", _floating, "floats"),
    ("buried", _buried, "buried"),
    ("seated_by_floor_not_round", _seated_by_floor, "buried"),
    ("plan_street_cells", _plan_street, "writes on street s_plan"),
    ("data_street_polyline", _data_street, "street (data polyline)"),
    ("lot", _lot, "writes on lot L2"),
    ("building_within_2", _building, "within 2 of building house_1"),
    ("event_site", _event_site, "event site ev2"),
    ("routes_json_leg", _route_leg, "from a routed leg"),
    ("critical_leg", _critical_leg, "from a routed leg"),
    ("critical_legs_missing", _no_critical, "critical legs cannot be checked"),
    ("spawn_block", _spawn_block, "is a spawn condition"),
    ("unlisted_block", _unlisted, "minecraft:diamond_block at 100 67 100 is not in data/shrines.json blocks"),
    ("sea_town", _sea_town, "writes within 64 of sea_town"),
    ("jungle_ruins", _jungle_ruins, "writes within 64 of jungle_ruins"),
    ("too_far_from_its_town", _far_from_town, "from town_a's footprint, over 5"),
    ("water_export", _water_export, "the water export changes"),
    ("water_export_missing", _no_water_export, "pending water export cannot be checked"),
    ("painted_water", _painted_water, "is painted water"),
    ("under_sea_level", _under_sea, "under the sea level"),
    ("painted_tree", _tree, "painted tree or object"),
    ("other_pack_build", _other_build, "another pack's build"),
    ("empty_function", _empty, "the shrines write nothing"),
    ("missing_function", _missing, "no function"),
    ("index_mismatch", _index, "does not list exactly"),
    ("unloaded_chunks", _unloaded, "would refuse"),
    ("too_many_blocks", _too_many, "writes 62 blocks"),
]


@pytest.mark.parametrize("case,breakage,phrase", CASES, ids=[c[0] for c in CASES])
def test_the_audit_names_each_breakage_it_claims_to_catch(run_audit, case, breakage, phrase):
    # Without it the audit's docstring is a claim, not a check: each row is one breakage of an otherwise clean root.
    fx = base_fixture()
    breakage(fx)
    problems, _total = run_audit(fx)
    assert any(phrase in p for p in problems), "%s: not caught; problems were %s" % (case, problems)


def test_an_empty_shrine_function_is_a_failure_with_nothing_counted(run_audit):
    # Without it the CLI could print CLEAN over a pack whose function exists and writes nothing.
    fx = base_fixture()
    _empty(fx)
    problems, total = run_audit(fx)
    assert total == 0
    assert any("writes 0 blocks" in p for p in problems)


def test_the_audit_does_not_read_the_generator_or_its_report():
    # Without it the audit could agree with shrines.py by reading its Clearance or derived/shrines/report.json,
    # which is the generator grading itself.
    src = (ROOT / "tools" / "shrines_audit.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+shrines\b", src, re.M)
    assert "report.json" not in src and '"shrines" / "report' not in src


# ============================================================================== generator behaviour, synthetic ground
def test_a_shrine_on_a_one_block_step_stands_on_the_high_side_with_a_foundation_on_the_low():
    # Without it a shrine on sloping ground floats over its low columns or is buried in its high ones.
    spec = {"id": "t", "kind": "cairn", "at": [100, 100], "facing": "north", "palette": {}}
    ground = {x: 64 for x in (99, 100)}
    ground[101] = 65
    blocks, floor = S.place(spec, lambda x, z: ground[x], Open())
    assert floor == 66
    low = {}
    for x, y, z, _s in blocks:
        low[(x, z)] = min(low.get((x, z), y), y)
    assert low == {(x, z): ground[x] + 1 for x in (99, 100, 101) for z in (99, 100, 101)}
    # the foundation on the low side is the kind's default, cobblestone, one block at y65
    found = sorted((x, z) for x, y, z, s in blocks if y == 65)
    assert found == [(x, z) for x in (99, 100) for z in (99, 100, 101)]
    assert {s for x, y, z, s in blocks if y == 65} == {"minecraft:cobblestone"}


def test_a_shrine_on_ground_varying_by_two_is_refused():
    # Without it a shrine could be seated with a two-block foundation wall on one side, which the kinds do not allow.
    spec = {"id": "t", "kind": "cairn", "at": [100, 100], "facing": "north", "palette": {}}
    with pytest.raises(SystemExit, match="varies by 2"):
        S.place(spec, lambda x, z: 66 if x == 101 else 64, Open())


def test_a_shrine_over_a_refused_cell_is_not_built_and_the_reason_is_named():
    # Without it the generator's clearance would be advisory: a shrine on a street would be written anyway.
    class Street:
        def blocked(self, x, z):
            return "street s1" if (x, z) == (101, 99) else None
    spec = {"id": "t", "kind": "cairn", "at": [100, 100], "facing": "north", "palette": {}}
    with pytest.raises(SystemExit, match=r"\(101, 99\) is not free: street s1"):
        S.place(spec, lambda x, z: 64, Street())


# ============================================================================================ 2. the real data
def test_every_shrine_leaves_its_story_to_codex_and_adds_no_field_of_its_own():
    # Without it a shrine could carry an invented dedication or legend that is Codex's to write.
    fields = set(DATA["fields"])
    for s in SHRINES:
        assert s.get("story") == "for Codex", s["id"]
        assert s["name"].endswith("(working name)"), s["id"]
        assert set(s) <= fields, "%s: fields beyond data/shrines.json `fields`: %s" % (s["id"], set(s) - fields)


def test_the_brief_excludes_the_sea_town_and_the_jungle_ruins_and_no_shrine_stands_there():
    # Without it a shrine could be put at the floating sea town or the unkept ruins, which the brief keeps bare.
    assert {"sea_town", "jungle_ruins"} <= set(RULES["excluded_settlements"])
    for s in SHRINES:
        assert s["settlement"] not in ("sea_town", "jungle_ruins"), s["id"]
        for ex in ("sea_town", "jungle_ruins"):
            d = min(box_distance(TOWNS[ex], x, z) for x, z in columns(s))
            assert d > RULES["excluded_margin"], "%s is %.0f from %s" % (s["id"], d, ex)


def test_every_shrine_stands_on_the_approach_of_its_own_town():
    # Without it a shrine could drift away from the town whose approach it is for.
    for s in SHRINES:
        d = min(box_distance(TOWNS[s["settlement"]], x, z) for x, z in columns(s))
        assert d <= RULES["max_from_town"], "%s is %.0f from %s" % (s["id"], d, s["settlement"])


def test_no_two_shrines_share_a_column():
    # Without it one shrine's function would overwrite another's.
    seen = {}
    for s in SHRINES:
        for c in columns(s):
            assert c not in seen, "%s and %s share %s" % (s["id"], seen.get(c), c)
            seen[c] = s["id"]


def test_the_shrine_block_list_holds_no_spawn_condition():
    # Without it a shrine could decide what spawns on the road beside it.
    assert not ALLOWED & SPAWN, sorted(ALLOWED & SPAWN)


@pytest.mark.parametrize("sid", IDS)
def test_every_block_a_shrine_writes_is_listed_and_none_is_a_spawn_condition(sid):
    # Without it a palette default or a foundation block outside the list (or a spawn block) reaches the world.
    spec = next(s for s in SHRINES if s["id"] == sid)
    blocks, _floor = S.place(spec, chequer, Open())
    names = {name(st) for _x, _y, _z, st in blocks}
    assert names <= ALLOWED, sorted(names - ALLOWED)
    assert not names & SPAWN, sorted(names & SPAWN)
    assert 5 <= len(blocks) <= 60, len(blocks)


def _jar():
    try:
        import town_character as TC
        jar = TC.default_vanilla_jar()
    except Exception:  # noqa: BLE001
        return None
    return zipfile.ZipFile(jar) if jar and Path(jar).is_file() else None


@pytest.mark.skipif(_jar() is None, reason="NOT_EXECUTED: no Minecraft 1.21.1 client jar")
def test_every_listed_shrine_block_is_a_minecraft_1_21_1_block():
    # Without it a mistyped id would be dropped by the server with nothing written.
    names = set(_jar().namelist())
    missing = [b for b in ALLOWED if "assets/minecraft/blockstates/%s.json" % b.split(":")[1] not in names]
    assert not missing, missing


@pytest.mark.parametrize("sid", IDS)
def test_every_shrine_function_holds_the_chunks_it_writes_for_its_whole_run(sid):
    # Without it a shrine whose columns straddle a chunk edge is written into an unloaded chunk, which does nothing
    # and says nothing.
    spec = next(s for s in SHRINES if s["id"] == sid)
    blocks, floor = S.place(spec, chequer, Open())
    lines = function_limits.ensure_loaded(S.commands_for(spec, blocks, floor))
    assert not held_violations(lines), held_violations(lines)[:3]


def test_a_shrine_across_a_chunk_corner_holds_all_four_chunks():
    # Without it the check above would pass on shrines that happen to sit inside one chunk.
    spec = {"id": "t", "name": "t", "kind": "roofed_altar", "at": [16, 16], "facing": "north", "palette": {}}
    blocks, floor = S.place(spec, lambda x, z: 64, Open())
    assert {(x // 16, z // 16) for x, _y, z, _s in blocks} == {(0, 0), (0, 1), (1, 0), (1, 1)}
    lines = function_limits.ensure_loaded(S.commands_for(spec, blocks, floor))
    assert not held_violations(lines)
    bare = [l for l in lines if not l.startswith("forceload")]
    assert held_violations(bare), "the simulator did not notice a function holding nothing"


def test_no_shrine_is_within_the_leg_margin_of_a_routes_json_corridor():
    # Without it a shrine could stand on or against the road a player walks.
    legs = [[(q["x"], q["z"]) for q in (r.get("corridor") or {}).get("polyline") or []]
            for r in json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))["routes"]]
    crit = ROOT / "derived" / "routes" / "critical_legs.json"
    if crit.is_file():
        legs += [[tuple(p) for p in leg.get("polyline") or []] for leg in json.loads(crit.read_text())["legs"]]
    for s in SHRINES:
        d, where = min((seg_distance(x, z, a, b), (x, z)) for x, z in columns(s)
                       for leg in legs for a, b in zip(leg, leg[1:]))
        assert d > RULES["leg_margin"], "%s: %s is %.1f from a leg" % (s["id"], where, d)


def test_no_shrine_is_on_or_beside_a_route_event_site():
    # Without it a shrine could stand in an event's staging area (Route 2's cart site sits just north of Brock's town).
    m = RULES["point_margin"]
    for sc in json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))["scenes"]:
        if not sc.get("area"):
            continue
        a, b = sc["area"]["from"], sc["area"]["to"]
        x0, x1, z0, z1 = min(a[0], b[0]) - m, max(a[0], b[0]) + m, min(a[2], b[2]) - m, max(a[2], b[2]) + m
        for s in SHRINES:
            hit = [c for c in columns(s) if x0 <= c[0] <= x1 and z0 <= c[1] <= z1]
            assert not hit, "%s is on or within %d of event site %s at %s" % (s["id"], m, sc["id"], hit[0])


def test_no_shrine_is_on_a_planned_street():
    # Without it a shrine could be written across a street a town's plan paves.
    for st, rec in PLACEMENTS["settlements"].items():
        for street in (rec.get("plan") or {}).get("streets") or []:
            pts = [tuple(p) for p in street.get("polyline") or []]
            half = int(street.get("width", 1)) // 2
            for s in SHRINES:
                for x, z in columns(s):
                    d = min((seg_distance(x, z, a, b) for a, b in zip(pts, pts[1:])), default=1e9)
                    assert d > half + 1, "%s: %s is %.1f from %s's street %s" % (s["id"], (x, z), d, st,
                                                                                  street.get("id"))


def _placed_rects():
    """[(id, (x0, z0, x1, z1))] of every placed building whose size this checkout can read, and the ids it cannot."""
    import nbt
    rects, unknown = [], []
    for q in PLACEMENTS["placements"]:
        if q.get("kind") == "earthwork" or not q.get("position"):
            continue
        size = q.get("size")
        if not size and q.get("file") and (ROOT / q["file"]).is_file():
            size = nbt.load(ROOT / q["file"])[1]["size"]
        if not size:
            unknown.append(q)
            continue
        w, d = (size[2], size[0]) if (q.get("rotation") or "none") in ("clockwise_90", "counterclockwise_90") \
            else (size[0], size[2])
        x0, z0 = q["position"]["x"], q["position"]["z"]
        rects.append((q["id"], (x0, z0, x0 + w - 1, z0 + d - 1)))
    return rects, unknown


def test_no_shrine_is_within_the_building_margin_of_a_placed_building():
    # Without it a shrine could stand against a house wall or in a doorway a town rebuild clears.
    m = RULES["building_margin"]
    rects, _unknown = _placed_rects()
    for s in SHRINES:
        for bid, (x0, z0, x1, z1) in rects:
            hit = [c for c in columns(s) if x0 - m <= c[0] <= x1 + m and z0 - m <= c[1] <= z1 + m]
            assert not hit, "%s is within %d of %s at %s" % (s["id"], m, bid, hit[0])


def test_buildings_near_a_shrine_have_a_size_this_checkout_can_read():
    # Without it the check above silently skips the houses nearest a shrine (their templates are local only).
    _rects, unknown = _placed_rects()
    near = sorted({q["id"] for q in unknown for s in SHRINES
                   if math.hypot(q["position"]["x"] - s["at"][0], q["position"]["z"] - s["at"][1]) < 80})
    if near:
        pytest.skip("NOT_EXECUTED: %d building(s) within 80 of a shrine have no readable template here: %s"
                    % (len(near), ", ".join(near[:8])))


def test_r16d_runs_every_shrine_of_the_data_in_order_after_the_dressing_and_the_working_pokemon(monkeypatch):
    # Without it a shrine added to the data is built but never re-applied, and the export erases it.
    import ambient
    import reapply
    # the other steps' local-only inputs (built packs' indexes, the working Pokemon's plan) are not what is tested
    monkeypatch.setattr(reapply, "indexed", lambda pack, folder: [])
    monkeypatch.setattr(ambient, "placement_steps", lambda *a, **k: [])
    try:
        steps = reapply.steps()
    except SystemExit as e:
        pytest.skip("NOT_EXECUTED: reapply.steps() needs a local-only input here: %s" % e)
    ids = [sid for sid, _t, _a in steps]
    assert ids.count("R16D") == 1
    (acts,) = [a for sid, _t, a in steps if sid == "R16D"]
    assert acts == [("fn", "cobblers:shrines/%s" % i) for i in IDS]
    assert ids.index("R16B") < ids.index("R16D") and ids.index("R16C") < ids.index("R16D")


def test_a_built_shrine_pack_counts_as_covered_only_through_r16d(tmp_path, monkeypatch):
    # Without it the fail-closed check could pass a shrine pack no step runs.
    import reapply
    fdir = tmp_path / "cobblers_shrines" / "data" / "cobblers" / "function" / "shrines"
    fdir.mkdir(parents=True)
    (fdir / "a.mcfunction").write_text("setblock 0 0 0 minecraft:stone\n", encoding="utf-8")
    monkeypatch.setattr(reapply, "PACKS", tmp_path)
    assert "cobblers_shrines" not in reapply.EXCLUDED
    assert reapply.uncovered([("R16D", "t", [("fn", "cobblers:shrines/a")])]) == []
    assert reapply.uncovered([("R16B", "t", [("fn", "cobblers:town_dressing/x")])])


# ====================================================================== 3. the heightmap and the local-only inputs
def _ground():
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("NOT_EXECUTED: COBBLERS_SOURCE_ROOT is not set: the canonical heightmap is outside the repo")
    import terrain as T
    heights, world = T.load(ROOT / "data" / "world.json", root)
    return heights, world


@pytest.fixture(scope="module")
def canonical():
    return _ground()


@pytest.mark.slow
def test_every_shrine_column_starts_one_block_over_rounded_heightmap_ground(canonical):
    # Without it a shrine floats over the export's ground or is buried in it (floor() is a block low at half the map).
    heights, world = canonical
    ox, oz = world["grid"]["origin_x"], world["grid"]["origin_z"]
    sea = float((world.get("vertical") or {}).get("sea_level", 62))

    def g(x, z):
        return int(np.round(float(heights[z - oz, x - ox])))
    for s in SHRINES:
        blocks, _floor = S.place(s, g, Open())
        low = {}
        for x, y, z, _st in blocks:
            low[(x, z)] = min(low.get((x, z), y), y)
        wrong = {c: (y, g(*c)) for c, y in low.items() if y != g(*c) + 1}
        assert not wrong, "%s: column: (lowest block, ground) %s" % (s["id"], wrong)
        wet = [c for c in low if heights[c[1] - oz, c[0] - ox] <= sea]
        assert not wet, "%s: at or under the sea level at %s" % (s["id"], wet)


def test_no_shrine_is_within_8_of_a_column_the_pending_water_export_changes():
    # Without it a shrine could stand where the water export will put water or cut the bank away.
    p = ROOT / "derived" / "water_shape" / "changed.npy"
    if not p.is_file():
        pytest.skip("NOT_EXECUTED: no derived/water_shape/changed.npy here (python tools/water_shape.py)")
    changed = np.load(p, mmap_mode="r")
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    ox, oz = world["grid"]["origin_x"], world["grid"]["origin_z"]
    w = RULES["water_change_margin"]
    for s in SHRINES:
        for x, z in columns(s):
            win = np.asarray(changed[z - oz - w:z - oz + w + 1, x - ox - w:x - ox + w + 1])
            assert not win.any(), "%s: %s is within %d (square) of a changed column" % (s["id"], (x, z), w)


@pytest.mark.slow
def test_the_built_shrine_pack_passes_the_audit():
    # Without it a built pack that drifted from the data (or a data change never rebuilt) would go to the server.
    if not (SA.PACK / "data" / "cobblers" / "function" / "shrines" / "index.txt").is_file():
        pytest.skip("NOT_EXECUTED: no built build/datapacks/cobblers_shrines here (python tools/shrines.py build)")
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("NOT_EXECUTED: COBBLERS_SOURCE_ROOT is not set")
    problems, total = SA.audit(SA.PACK, root)
    assert total and not problems, problems[:10]
