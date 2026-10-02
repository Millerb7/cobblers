"""What R9Z puts in the world: can a player walk through every gatehouse it builds, and does it build nothing
nobody can pass?

WRITTEN BY THE IMPLEMENTER (minecraft-systems-dev, 2026-10-02) at the caller's request, which is against
CLAUDE.md principle 16's preference: a separate reviewer should read these against the data before trusting
them. They are kept independent of the generator where it matters: the walk reads only the EMITTED
.mcfunction text and the canonical heightmap, with its own movement model, and the "can this zone grant"
test reads data/progression.json and the zone's pass, never tools/rift_zones.py held_zones().

THE MOVEMENT MODEL (a player's, not the builder's): feet in two passable blocks over a solid one; a step to a
4-neighbour level, one block up only with a third block of air over the column jumped from, or down by up to
three. Terrain is solid up to round(heightmap) and air above it; every emitted fill/setblock overrides it, in
the order R9Z runs them.

NOT COVERED: anything that needs a server -- that the advancements fire, that `tp` lands where the data says,
that the barrier cannot be jumped or pearled. Nor the zone check itself, which is location only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import types
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rift_zones as RZ  # noqa: E402

SPEC = json.loads((ROOT / "data" / "rift_zones.json").read_text(encoding="utf-8"))
PROGRESSION = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
GH = SPEC["gatehouse"]
PASSABLE = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
HELD_WALLS = "held_walls_do_not_meet_their_gatehouses"


def live_zones():
    return {zid: z for zid, z in SPEC["zones"].items()
            if not str(z.get("status", "")).startswith("SUPERSEDED") and z.get("guard")}


def can_grant(z):
    """Whether the SERVER can give this zone's pass, from the data and nothing the generator decides: the pass
    is a set of `cobblers:flag/<id>` advancements and every one of those ids is a flag data/progression.json
    declares (tools/progression_pack.py writes an advancement for each). A caught-count pass has no server-side
    reader at all."""
    p = z["pass"]
    if p["kind"] not in ("badges", "flag") or not p.get("advancements"):
        return False
    # a flag the server can grant is declared AND, where its setter names who invokes it (`set_by.invoked_by`, a
    # quest-transition setter), something does: rift_crisis_resolved is declared with its transition since 2026-10-02
    # but nothing invokes it yet, which tools/rift_zones.py's report already counts as owed (the same rule here)
    grantable = {f["id"] for f in PROGRESSION["flags"]
                 if not ("invoked_by" in (f.get("set_by") or {}) and not f["set_by"]["invoked_by"])}
    return all(a.startswith("cobblers:flag/") and a[len("cobblers:flag/"):] in grantable for a in p["advancements"])


def _quiet_report(_a, quiet=False):
    return 0


def build(module=None, real_ground=False):
    """Run cmd_build into a throwaway directory; return (function dir, advancement dir)."""
    M = module or RZ
    tmp = Path(tempfile.mkdtemp(prefix="rift_zones_apply_"))
    saved = (M.PACKS, M.ground_of, M.cmd_report)
    M.PACKS = tmp
    M.cmd_report = _quiet_report
    if not real_ground:
        M.ground_of = lambda _root: (lambda x, z: 80)
    try:
        M.cmd_build(argparse.Namespace(source_root=os.environ.get("COBBLERS_SOURCE_ROOT")))
    finally:
        M.PACKS, M.ground_of, M.cmd_report = saved
    base = tmp / M.PACK / "data" / M.NS
    return base / "function" / M.FOLDER, base / "advancement" / M.FOLDER


_FAST = {}


def fast():
    if "b" not in _FAST:
        _FAST["b"] = build()
    return _FAST["b"]


def r9z(index):
    import reapply
    return reapply.rift_zone_steps(index, SPEC)


# ------------------------------------------------------------------ nothing nobody can pass

# Without it the zone check of a zone nobody can be granted ships in the pack, and the pack acts on its own the
# moment it is installed: on 2026-10-02 that was z5, the League's precinct, turning back every survival player
# (data/rift_zones.json measured_defects[held_zone_checks_shut_the_league]).
def test_a_zone_that_cannot_grant_its_pass_has_no_advancement():
    _fn, adv = fast()
    names = {p.stem for p in adv.glob("*.json")}
    for zid, z in live_zones().items():
        mine = {n for n in names if n == "%s_zone" % zid or n.startswith("%s_" % zid)}
        if can_grant(z):
            gates = [g[0] for g in RZ.gates_of(zid, z)]
            want = {"%s_zone" % zid} | {"%s_%s" % (g, k) for g in gates for k in ("knock", "exit")}
            assert want <= mine, "%s can grant its pass and is missing %s" % (zid, sorted(want - mine))
        else:
            assert not mine, "%s cannot grant its pass and still ships %s" % (zid, sorted(mine))


# Without this the test above could pass because nothing ships, not because a held zone is skipped: the
# GENERATOR's hold is removed, the data untouched, and the held zones' advancements must come back.
def test_removing_the_hold_from_build_ships_the_held_zones_checks_again():
    src = (ROOT / "tools" / "rift_zones.py").read_text(encoding="utf-8")
    old = "        enforced = zid not in held"
    assert src.count(old) == 1
    mod = types.ModuleType("rift_zones_unheld")
    mod.__file__ = str(ROOT / "tools" / "rift_zones.py")
    exec(compile(src.replace(old, "        enforced = True"), mod.__file__, "exec"), mod.__dict__)
    _fn, adv = build(module=mod)
    names = {p.stem for p in adv.glob("*.json")}
    for zid, z in live_zones().items():
        if not can_grant(z):
            assert "%s_zone" % zid in names, "the mutation did not bring back %s's zone check" % zid


# Without it the data's own switch drifts from the truth: a needs_* field left on a zone that can now grant
# keeps it shut for nothing, and one taken off a zone that cannot grant puts its walls up. When Codex declares
# rift_crisis_resolved this fails until z5's needs_progression goes, which is the point.
def test_the_held_zones_are_exactly_the_zones_that_cannot_grant():
    held = set(RZ.held_zones(SPEC))
    cannot = {zid for zid, z in live_zones().items() if not can_grant(z)}
    assert held == cannot, "held %s, cannot grant %s" % (sorted(held), sorted(cannot))


# Without it R9Z runs a wall or a gatehouse of a zone whose pass nothing grants: a wall nobody can pass.
def test_r9z_runs_no_wall_and_no_gatehouse_of_a_zone_that_cannot_grant():
    fn, _adv = fast()
    index = [x for x in (fn / "index.txt").read_text(encoding="utf-8").split() if x]
    run, held = r9z(index)
    assert sorted(run + held) == sorted(index)
    zones = live_zones()
    owner = {}
    for zid, z in zones.items():
        for g in RZ.gates_of(zid, z):
            owner["gatehouse_%s" % g[0]] = zid
        if z.get("wall"):
            owner["wall_%s" % z["wall"]] = zid
    for f in run:
        assert can_grant(zones[owner[f]]), "R9Z runs %s, but %s cannot grant its pass" % (f, owner[f])
    for f in held:
        assert not can_grant(zones[owner[f]]), "R9Z holds %s, but %s can grant its pass" % (f, owner[f])
    assert run, "R9Z runs nothing at all"


def _lines(fn, name):
    return [ln for ln in (fn / (name + ".mcfunction")).read_text(encoding="utf-8").splitlines()
            if ln and not ln.startswith("#")]


# Without it a re-run of R9Z stacks a second placeholder on every guard, and the descent post keeps G2's old
# one under its old tag. One fresh stand per gate R9Z builds, on the guard's own feet, none for a held gate,
# none from a gatehouse function (a kill in the tick of the forceload cannot see saved entities), and the
# clean-up a later tick kills every OTHER guard stand on that block, but only once the fresh one is there.
def test_one_placeholder_per_built_gate_and_the_old_ones_go():
    fn, _adv = fast()
    for p in fn.glob("gatehouse_*.mcfunction"):
        assert "summon" not in p.read_text(encoding="utf-8"), p.stem
    want = {}
    for zid, z in live_zones().items():
        if can_grant(z):
            for g in RZ.gates_of(zid, z):
                want[g[0]] = (g[2]["block"][0], g[2]["ground_y"] + 1, g[2]["block"][1])
    placed = {}
    for ln in _lines(fn, "guards_place"):
        if ln.startswith("summon minecraft:armor_stand"):
            x, y, z = (int(v) for v in ln.split()[2:5])
            tags = ln.split("Tags:[", 1)[1].split("]", 1)[0].replace('"', "").split(",")
            gate = [t for t in tags if t in want]
            assert len(gate) == 1 and "cobblers_rift_guard" in tags and "cobblers_rift_guard_new" in tags, ln
            placed[gate[0]] = (x, y, z)
    assert placed == want
    done = _lines(fn, "guards_done")
    for name, (x, y, z) in want.items():
        box = "x=%d,y=%d,z=%d,dx=0,dy=1,dz=0" % (x, y, z)
        hits = [ln for ln in done if ln.startswith("execute if entity") and box in ln]
        assert len(hits) == 1, name
        cond, kill = hits[0].split(" run ", 1)
        assert "tag=cobblers_rift_guard_new" in cond and "tag=!cobblers_rift_guard_new" in kill, hits[0]
    assert any(ln.startswith("schedule function cobblers:rift_zones/guards_place") for ln in _lines(fn, "guards"))
    assert any(ln.startswith("schedule function cobblers:rift_zones/guards_done") for ln in _lines(fn, "guards_place"))


# ------------------------------------------------------------------ the walk, over the heightmap

def world_of(fn_dir, names, g):
    over = {}
    for n in names:
        over.update(RZ.simulate_function((fn_dir / (n + ".mcfunction")).read_text(encoding="utf-8").splitlines()))

    def block(x, y, z):
        b = over.get((x, y, z))
        if b is not None:
            return b
        return "terrain" if y <= g(x, z) else "minecraft:air"
    return block


def walker(block):
    def stand(x, y, z):
        return block(x, y, z) in PASSABLE and block(x, y + 1, z) in PASSABLE and block(x, y - 1, z) not in PASSABLE

    def feet(x, z, near):
        for d in range(0, 24):
            for y in (near + d, near - d):
                if stand(x, y, z):
                    return (x, y, z)
        return None

    def reach(start, centre, r=28):
        seen, q = {start}, deque([start])
        while q:
            x, y, z = q.popleft()
            for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                if abs(nx - centre[0]) > r or abs(nz - centre[1]) > r:
                    continue
                for ny in (y + 1, y, y - 1, y - 2, y - 3):
                    if (nx, ny, nz) in seen:
                        continue
                    if ny == y + 1 and block(x, y + 2, z) not in PASSABLE:
                        continue
                    if stand(nx, ny, nz):
                        seen.add((nx, ny, nz))
                        q.append((nx, ny, nz))
                        break
        return seen
    return feet, reach


def walk_problems(gate, block):
    """[] when a player can: walk from the approach outside into the knock box and back out again; walk from
    the arrival into the zone; walk from the zone into the exit box. Start points are on the gate's own axis,
    walkway_in + 6 blocks inside and knock_out + 6 outside, at the heightmap's ground there."""
    name, _gid, gd, arr, _tb, eb, knock = gate
    q, ow, fy = gd["block"], gd["outward"], gd["ground_y"] + 1
    feet, reach = walker(block)

    def on_axis(t):
        return (int(round(q[0] - ow[0] * t)), int(round(q[1] - ow[1] * t)))
    o, i = on_axis(-(GH["knock_out"] + 6)), on_axis(GH["walkway_in"] + 6)
    out_c, in_c = feet(o[0], o[1], fy), feet(i[0], i[1], fy)
    bad = []
    if out_c is None or in_c is None:
        return ["%s: no standable start point outside %s or inside %s" % (name, o, i)]
    in_knock = [c for c in reach(out_c, q) if knock[0] <= c[0] <= knock[3] and knock[2] <= c[2] <= knock[5]
                and c[1] == knock[1]]
    if not in_knock:
        bad.append("%s: from outside at %s no player reaches the knock box %s" % (name, out_c, knock))
    elif out_c not in reach(in_knock[0], q):
        bad.append("%s: a player at the knock box %s cannot walk back out to %s" % (name, in_knock[0], out_c))
    a = (int(arr[0] - 0.5), int(arr[1]), int(arr[2] - 0.5))
    if in_c not in reach(a, q):
        bad.append("%s: from the arrival %s no player walks into the zone at %s" % (name, a, in_c))
    if not any((c[0], c[2]) == (eb[0], eb[2]) and c[1] == eb[1] for c in reach(in_c, q)):
        bad.append("%s: from the zone at %s no player reaches the exit box %s" % (name, in_c, eb[:3]))
    return bad


def _ground():
    if not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("COBBLERS_SOURCE_ROOT is not set: the heightmap is outside the repo")
    import ground as GD
    try:
        return GD.load(os.environ["COBBLERS_SOURCE_ROOT"])
    except Exception as e:  # noqa: BLE001 -- only the heightmap's absence is a skip
        if type(e).__name__ != "TerrainUnavailable":
            raise
        pytest.skip("the heightmap is not readable here")


def gates_r9z_runs(fn):
    index = [x for x in (fn / "index.txt").read_text(encoding="utf-8").split() if x]
    run, _held = r9z(index)
    gates = [g for zid, z in live_zones().items() for g in RZ.gates_of(zid, z) if "gatehouse_%s" % g[0] in run]
    return run, gates


_REAL = {}


def real():
    if "b" not in _REAL:
        _REAL["g"] = _ground()
        _REAL["b"] = build(real_ground=True)
    return _REAL["b"], _REAL["g"]


# THE TEST. Without it a gatehouse ships that the shell checks call sound and a player still cannot walk
# through, because the walkway's mouths open onto ground a block or five away from its floor
# (measured_defects[gatehouse_mouths_do_not_meet_the_ground]); or a wall R9Z runs crosses a walkway's
# approach. Everything R9Z runs, in its order, over the heightmap.
@pytest.mark.slow
def test_every_gatehouse_r9z_builds_can_be_walked_through():
    (fn, _adv), g = real()
    run, gates = gates_r9z_runs(fn)
    assert len(gates) == 5, "R9Z's gatehouses changed: %s" % [x[0] for x in gates]
    block = world_of(fn, run, g)
    problems = [p for gate in gates for p in walk_problems(gate, block)]
    assert problems == [], "\n".join(problems)


def _held_record():
    return next((d for d in SPEC["measured_defects"] if d["id"] == HELD_WALLS and not d.get("fixed")), None)


# Without it a held zone's needs_* field can be removed while its wall still seals its own gatehouse, and the
# release puts up a wall nobody can pass. Strict xfail keyed on the record: fix the siting and it XPASSes, and
# the record must then say `fixed`.
@pytest.mark.slow
@pytest.mark.xfail(_held_record() is not None, strict=True,
                   reason="data/rift_zones.json measured_defects[%s]" % HELD_WALLS)
def test_a_held_zones_gatehouse_can_be_walked_through_with_its_wall_up():
    (fn, _adv), g = real()
    index = [x for x in (fn / "index.txt").read_text(encoding="utf-8").split() if x]
    run, held = r9z(index)
    assert held, "nothing is held: this test's premise is gone, retire it with the record"
    block = world_of(fn, run + held, g)
    gates = [x for zid, z in live_zones().items() if zid in RZ.held_zones(SPEC) for x in RZ.gates_of(zid, z)]
    problems = [p for gate in gates for p in walk_problems(gate, block)]
    assert problems == [], "\n".join(problems)


# Without this the walk could pass for reasons of its own. Dropping the approach from the GENERATOR -- data
# untouched (CLAUDE.md, "mutate the generator, not the record") -- must break the gates whose mouths do not meet
# the ground, by name, and leave the ones whose mouths do.
@pytest.mark.slow
def test_dropping_the_approach_from_build_breaks_the_gates_that_need_it():
    src = (ROOT / "tools" / "rift_zones.py").read_text(encoding="utf-8")
    old = '            ap = [c for side in ("outer", "inner") for c in gd["approach"][side]]'
    assert src.count(old) == 1
    mod = types.ModuleType("rift_zones_no_approach")
    mod.__file__ = str(ROOT / "tools" / "rift_zones.py")
    exec(compile(src.replace(old, "            ap = []"), mod.__file__, "exec"), mod.__dict__)
    (fn, _adv), g = real()
    mfn, _madv = build(module=mod, real_ground=True)
    run, gates = gates_r9z_runs(fn)
    block = world_of(mfn, run, g)
    broken = {gate[0] for gate in gates if walk_problems(gate, block)}
    assert {"z2_victory_road_descent", "z2_wilds_slip"} <= broken, broken
    assert not broken & {"z1", "z2"}, "z1 and z2 meet their ground without an approach: %s" % broken
