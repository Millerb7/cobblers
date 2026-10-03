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


def wall_held(z):
    """A zone that CAN grant its pass and is still held, because its wall would not let a passed player through:
    the zone names the measured defect (zones.<id>.needs_walls.defect) and that defect is still open. Read from the
    defect record, not from tools/rift_zones.py held_zones(). z5 since 2026-10-03, when rift_crisis_resolved's setter
    got its invoker (the relic hall's binder)."""
    rec = _record(HELD_WALLS)
    return (z.get("needs_walls") or {}).get("defect") == HELD_WALLS and rec is not None and not rec.get("fixed")


def built(z):
    """Whether R9Z builds this zone's wall, gatehouses and placeholders: it can grant its pass and no open defect
    holds it. A zone no passless player can reach is still BUILT (its blocks stay); it only ships no advancement."""
    return can_grant(z) and not wall_held(z)


def knock_touches_outside(z, knock):
    """This file's own reading of 'a passless player can step into the knock box from outside': some column of the
    box, or a 4-neighbour of one, lies in none of the zone's boxes. Written here, not imported from the generator."""
    cols = {(x, zz) for x in range(knock[0], knock[3] + 1) for zz in range(knock[2], knock[5] + 1)}
    ring = cols | {(x + dx, zz + dz) for (x, zz) in cols for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))}
    return any(not any(b[0] <= x <= b[2] and b[1] <= zz <= b[3] for b in z["boxes"]) for (x, zz) in ring)


def knocks_of(z):
    """Every knock box of a zone, read from the data: the zone's own, and each post's."""
    return [z["knock"]] + [po["knock"] for po in z.get("posts", [])]


def reachable(z):
    """Whether a passless player can reach at least one of this zone's guards without being turned back first."""
    return any(knock_touches_outside(z, k) for k in knocks_of(z))


def enforced(z):
    """Whether `build` ships this zone's advancements: it is built, and some guard of it can be walked up to by a
    player without the pass. Otherwise the zone check would turn everyone back with no way through (the owner,
    2026-10-03: the worse failure), so it fails open."""
    return built(z) and reachable(z)


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
def advancement_problems(adv, rule=lambda _zid, z: enforced(z)):
    """[] when every zone `rule(zid, zone)` says is enforced ships its zone check, knocks and exits, and every other zone ships
    no advancement at all."""
    names = {p.stem for p in adv.glob("*.json")}
    bad = []
    for zid, z in live_zones().items():
        mine = {n for n in names if n == "%s_zone" % zid or n.startswith("%s_" % zid)}
        if rule(zid, z):
            gates = [g[0] for g in RZ.gates_of(zid, z)]
            want = {"%s_zone" % zid} | {"%s_%s" % (g, k) for g in gates for k in ("knock", "exit")}
            if not want <= mine:
                bad.append("%s is enforced and is missing %s" % (zid, sorted(want - mine)))
        elif mine:
            bad.append("%s is not enforced (cannot grant, or no guard reachable) and still ships %s"
                       % (zid, sorted(mine)))
    return bad


def test_a_zone_that_cannot_grant_its_pass_has_no_advancement():
    _fn, adv = fast()
    assert advancement_problems(adv) == []


# ------------------------------------------------------------------ a zone nobody can knock at fails open

# Without it a zone check ships for a zone whose every guard stands deep inside it: a player without the pass is
# turned back before reaching any guard, and nothing they can reach grants it -- no way through (the owner,
# 2026-10-03: the worse failure). Installed and run on staging 2026-10-02 for z1, whose G1 stands 141 blocks in.
# The zones this file's own column test calls unreachable are exactly the zones whose EVERY gate the defect record
# names, so the record, the geometry and the shipped pack cannot drift apart.
def test_a_zone_no_passless_player_can_reach_ships_no_advancement():
    rec = _record(TRAPPED)
    assert rec is not None and not rec.get("fixed"), "re-sited? then this pins nothing: update it with the record"
    trapped = set(rec["gates"])
    every_gate_trapped = {zid for zid, z in live_zones().items()
                          if all(g[0] in trapped for g in RZ.gates_of(zid, z))}
    unreachable = {zid for zid, z in live_zones().items() if not reachable(z)}
    assert unreachable == every_gate_trapped == {"z1"}, (unreachable, every_gate_trapped)
    # and the gates the record names, one by one, are the gates whose knock box is wholly inside the zone
    inside = {g[0] for zid, z in live_zones().items() for g in RZ.gates_of(zid, z)
              if not knock_touches_outside(z, g[6])}
    assert inside == trapped, sorted(inside)
    _fn, adv = fast()
    names = {p.stem for p in adv.glob("*.json")}
    assert not {n for n in names if n.startswith("z1_")}, sorted(names)
    # its blocks stay: R9Z still builds z1's wall and gatehouse, and the guard's placeholder is still placed
    fn, _adv = fast()
    index = [x for x in (fn / "index.txt").read_text(encoding="utf-8").split() if x]
    run, _held = r9z(index)
    assert {"gatehouse_z1", "wall_throat"} <= set(run), run
    assert any("\"z1\"" in ln for ln in _lines(fn, "guards_place"))


# Without this the test above could pass because the column test is wrong, not because the generator holds the
# zone: the GENERATOR's reachability hold is removed (data untouched) and the check must fail, naming z1.
def test_shipping_the_checks_of_an_unreachable_zone_fails():
    src = (ROOT / "tools" / "rift_zones.py").read_text(encoding="utf-8")
    old = "        enforced = enforced and zid not in unreachable"
    assert src.count(old) == 1
    mod = types.ModuleType("rift_zones_unreachable_shipped")
    mod.__file__ = str(ROOT / "tools" / "rift_zones.py")
    exec(compile(src.replace(old, "        enforced = enforced"), mod.__file__, "exec"), mod.__dict__)
    _fn, adv = build(module=mod)
    bad = advancement_problems(adv)
    assert bad and all(b.startswith("z1 ") for b in bad), bad
    assert (adv / "z1_zone.json").is_file() and (adv / "z1_knock.json").is_file()


# The same rule from a WALK, not from columns: over the heightmap, with every wall up, a zone ships its checks
# exactly when at least one of its gates can be walked up to by a passless player (passless_reaches_knock below).
@pytest.mark.slow
def test_the_zones_that_ship_checks_are_the_zones_a_passless_player_can_knock_at():
    (fn, adv), g = real()
    block = world_of(fn, everything(fn), g)
    walked = {}
    for zid, z in live_zones().items():
        gates = RZ.gates_of(zid, z)
        knocks = [x[6] for x in gates]
        walked[zid] = any(passless_reaches_knock(x, z, knocks, block) for x in gates)
    assert walked["z2"] and walked["z5"] and not walked["z1"], walked
    assert advancement_problems(adv, rule=lambda zid, z: built(z) and walked[zid]) == []


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
        if not built(z):
            assert "%s_zone" % zid in names, "the mutation did not bring back %s's zone check" % zid


# Without it the data's own switch drifts from the truth: a needs_* field left on a zone that can now grant
# keeps it shut for nothing, and one taken off a zone that cannot grant puts its walls up. A zone that can grant
# is still held while an OPEN defect names it (wall_held: z5's needs_walls on 2026-10-03, released the same day when
# the defect it named was fixed); a needs_walls left on a fixed defect fails here, which is the point.
def test_the_held_zones_are_exactly_the_zones_that_cannot_grant():
    held = set(RZ.held_zones(SPEC))
    cannot = {zid for zid, z in live_zones().items() if not built(z)}
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
        assert built(zones[owner[f]]), "R9Z runs %s, but %s cannot grant its pass" % (f, owner[f])
    for f in held:
        assert not built(zones[owner[f]]), "R9Z holds %s, but %s can grant its pass" % (f, owner[f])
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
        if built(z):
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


def start_heading(gd):
    """The heading the walks' START POINTS are measured along: the gate's SURVEYED outward (data/rift_zones.json
    <gate>.surveyed_outward -- the road's walked line on a route gate, the traced mask's axis otherwise), not
    the built one.

    Since 2026-10-03 the gatehouse is six wide on a cardinal axis (gatehouse.axis_why), snapped up to 34
    degrees off the surveyed line. A start point on the SNAPPED axis lands wherever that axis happens to go:
    at G2, twelve blocks in, on the cliff the Victory Road cut runs past (ground y126 at (3548, 5310) beside the
    road's y111 at (3552, 5311)); at the wilds slip, eight out, on a bump that can be jumped down from and not
    climbed. On the surveyed line they are the places they were before the snap -- on the road, on the ground
    the gate was sited to join -- which is what this walk asks about: can a player get from there, through the
    gatehouse, to there. Read from the data, not from the generator."""
    return gd.get("surveyed_outward") or gd["outward"]


def walk_problems(gate, block):
    """[] when a player can: walk from the approach outside into the knock box and back out again; walk from
    the arrival into the zone; walk from the zone into the exit box. Start points are on the gate's surveyed
    line (start_heading), walkway_in + 6 blocks inside and knock_out + 6 outside, at the heightmap's ground there."""
    name, _gid, gd, arr, _tb, eb, knock = gate
    q, ow, fy = gd["block"], start_heading(gd), gd["ground_y"] + 1
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
    bad += straight_on_problems(gate, block)
    return bad


def straight_on_problems(gate, block):
    """[] when, at each end, a player walking straight on off the last approach column steps onto ground.

    Added 2026-10-03 (data/rift_zones.json measured_defects[held_walls_do_not_meet_their_gatehouses]): G5's
    inner approach ended one column short of a column of league_gate, so a passed player walking out of the
    walkway walked into obsidian. The flood fill above still called G5 sound, because a player can sidestep
    onto the ground beside it; a doorway whose way out is a sidestep round a wall is the defect all the same.
    Since 2026-10-03 the walkway is six wide and each side's approach is one run per lane
    (data/rift_zones.json gatehouse.width_why): every lane is checked. The heading is the record's own outward
    (out of the outer mouth) or its reverse (out of the inner one), read from the data; the step is the movement
    model's: up one with headroom, or down by up to three."""
    name, _gid, gd, *_ = gate
    ow = gd["outward"]
    bad = []

    def ok(x, y, z):
        return block(x, y, z) in PASSABLE and block(x, y + 1, z) in PASSABLE and block(x, y - 1, z) not in PASSABLE
    for side, (hx, hz) in (("outer", (ow[0], ow[1])), ("inner", (-ow[0], -ow[1]))):
        runs = gd["approach"][side]
        if len(runs) != GH["walkway"] or not all(runs):
            bad.append("%s: the %s approach has %d lane run(s), %d of them empty; one per lane (%d) is what says "
                       "where each lane's mouth is" % (name, side, len(runs), sum(1 for r in runs if not r),
                                                        GH["walkway"]))
            continue
        for lane, run in enumerate(runs):
            lx, lz, ly = run[-1][0], run[-1][1], run[-1][2]
            sx, sz = lx + hx, lz + hz
            steps = [y for y in (ly, ly - 1, ly - 2, ly - 3) if ok(sx, y, sz)]
            if ok(sx, ly + 1, sz) and block(lx, ly + 2, lz) in PASSABLE:
                steps.append(ly + 1)
            if not steps:
                bad.append("%s: walking straight on off the %s approach, lane %d, at (%d, %d, %d), the column "
                           "(%d, %d) is not ground a player can step onto: %s"
                           % (name, side, lane, lx, ly, lz, sx, sz,
                              [block(sx, y, sz) for y in range(ly - 1, ly + 3)]))
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
    # six since 2026-10-03: z5 released (its flag is set by the relic hall's binder and its wall meets G5); z4 held
    assert len(gates) == 6, "R9Z's gatehouses changed: %s" % [x[0] for x in gates]
    block = world_of(fn, run, g)
    problems = [p for gate in gates for p in walk_problems(gate, block)]
    assert problems == [], "\n".join(problems)


def _record(rid):
    return next((d for d in SPEC["measured_defects"] if d["id"] == rid), None)


def all_gates():
    return [x for zid, z in live_zones().items() for x in RZ.gates_of(zid, z)]


def everything(fn):
    """Every wall and gatehouse function, built by R9Z today or held, in R9Z's order."""
    index = [x for x in (fn / "index.txt").read_text(encoding="utf-8").split() if x]
    run, held = r9z(index)
    assert sorted(run + held) == sorted(index)
    return run + held


# Without it a held zone's needs_* field can be removed while its wall still seals its own gatehouse, and the
# release puts up a wall nobody can pass (measured_defects[held_walls_do_not_meet_their_gatehouses], fixed
# 2026-10-03 by moving G4 three blocks into behind_league and opening one column of league_gate at G5's inner
# mouth). EVERY gatehouse the data defines, built or held, with EVERY wall up: a held zone is released by
# deleting one field, and nothing else re-checks its geometry when that happens.
@pytest.mark.slow
def test_every_gatehouse_built_or_held_can_be_walked_through_with_every_wall_up():
    rec = _record(HELD_WALLS)
    assert rec is not None and rec.get("fixed"), "the record of the fix is gone or says unfixed"
    (fn, _adv), g = real()
    gates = all_gates()
    assert len(gates) == 7, "the data's gatehouses changed: %s" % [x[0] for x in gates]
    block = world_of(fn, everything(fn), g)
    problems = [p for gate in gates for p in walk_problems(gate, block)]
    assert problems == [], "\n".join(problems)


def gates_in_a_wall(fn):
    """The gates whose emitted gatehouse touches a column of their own zone's emitted wall: those are the
    gates the wall is meant to close on, so the barrier must be the only way past. Read off the two emitted
    functions; which wall is the zone's comes from the data. G1 stands 141 blocks inside z1, nowhere near the
    throat wall, and z2 has no wall, so their gatehouses touch none."""
    out = []
    for gate in all_gates():
        zid = gate[0].split("_")[0]
        w = SPEC["zones"][zid].get("wall")
        if not w:
            continue
        wall = {(x, z) for (x, _y, z) in RZ.simulate_function(
            (fn / ("wall_%s.mcfunction" % w)).read_text(encoding="utf-8").splitlines())}
        house = {(x, z) for (x, _y, z) in RZ.simulate_function(
            (fn / ("gatehouse_%s.mcfunction" % gate[0])).read_text(encoding="utf-8").splitlines())}
        if any((x + dx, z + dz) in wall for (x, z) in house for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            out.append(gate)
    return out


def bypassed(gate, block):
    """True when, barrier shut, a player outside walks round to inside within 28 of the guard."""
    _n, _gid, gd, *_ = gate
    q, ow, fy = gd["block"], start_heading(gd), gd["ground_y"] + 1
    feet, reach = walker(block)
    o = (int(round(q[0] + ow[0] * (GH["knock_out"] + 6))), int(round(q[1] + ow[1] * (GH["knock_out"] + 6))))
    i = (int(round(q[0] - ow[0] * (GH["walkway_in"] + 6))), int(round(q[1] - ow[1] * (GH["walkway_in"] + 6))))
    return feet(i[0], i[1], fy) in reach(feet(o[0], o[1], fy), q)


# Without it a wall re-cut to meet its gatehouse could open a way round the barrier, and the walk above would
# pass happily, because it asks only whether a player CAN get through. Opening league_gate's column at G5's inner
# mouth is exactly such a re-cut.
@pytest.mark.slow
def test_the_barrier_is_the_only_way_past_a_gatehouse_in_a_wall():
    (fn, _adv), g = real()
    walled = gates_in_a_wall(fn)
    assert {x[0] for x in walled} == {"z4", "z5"}, [x[0] for x in walled]
    block = world_of(fn, everything(fn), g)
    assert [x[0] for x in walled if bypassed(x, block)] == []


def _mutated_build(old, new, label):
    src = (ROOT / "tools" / "rift_zones.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, "the line to mutate is not in tools/rift_zones.py exactly once: %r" % old
    mod = types.ModuleType(label)
    mod.__file__ = str(ROOT / "tools" / "rift_zones.py")
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return build(module=mod, real_ground=True)


# Without this the bypass check could pass for reasons of its own. Dropping the gatehouse's side walls from the
# GENERATOR (walkway_shell returns nothing; data untouched) must open a way round G4.
#
# G4 ONLY since 2026-10-03, measured, and the reason is geometry rather than a weaker check: the six-wide G5
# runs north-south (zones.z5.guard.axis) and league_gate crosses it AT the barrier row, its diagonal meeting the
# barrier's two end lanes -- (3570, 2678) against (3571, 2679) at the west end, corner to corner, and (3577, 2679)
# beside (3576, 2679) at the east -- so with no side walls at all the cross-wall and the barrier still close G5.
# At G4 behind_league crosses the walkway's two OUTER rows, outside the barrier, and only the side walls stop a
# player stepping sideways off the guard's row. The proof that the bypass check bites at G5 is the next test.
@pytest.mark.slow
def test_dropping_the_shell_from_build_opens_a_way_round_the_gate_its_wall_does_not_close():
    (fn, _adv), g = real()
    mfn, _madv = _mutated_build("    return sorted(walls, key=lambda p: (p[1], p[0]))", "    return []",
                                "rift_zones_no_shell")
    block = world_of(mfn, everything(fn), g)
    assert {x[0] for x in gates_in_a_wall(fn) if bypassed(x, block)} == {"z4"}


# Without this the bypass check could pass at G5 for reasons of its own. Narrowing the barrier to the guard's own
# lane in the GENERATOR (gate_places; data untouched) leaves five lanes of walkway running past it, and the
# bypass check must find the way round at BOTH walled gates.
@pytest.mark.slow
def test_narrowing_the_barrier_to_one_lane_opens_a_way_round_both_walled_gates():
    (fn, _adv), g = real()
    mfn, _madv = _mutated_build('            "barrier": rows[1],', '            "barrier": [rows[1][zero]],',
                                "rift_zones_narrow_barrier")
    block = world_of(mfn, everything(fn), g)
    assert {x[0] for x in gates_in_a_wall(fn) if bypassed(x, block)} == {"z4", "z5"}


# Without it the straight-on check could pass for reasons of its own: building from the PRE-FIX approach -- G5's
# inner run without the league_gate column, the generator's own wall-awareness undone -- must break G5 by name.
@pytest.mark.slow
def test_an_approach_that_stops_short_of_the_wall_fails_straight_on():
    # RE-POINTED 2026-10-03. The pre-fix case this was written for -- G5's inner run stopping one column short of
    # league_gate at (3581, 2680) -- no longer exists: the six-wide G5 runs north-south (zones.z5.guard.axis) and
    # crosses the wall at its barrier row, so no approach of it meets a wall column. The proof keeps its shape:
    # put ONE wall column straight on past the end of one lane's inner run (the wall as it would stand had the
    # generator's wall-awareness not opened it) and the straight-on check must name G5.
    (fn, _adv), g = real()
    z5 = json.loads(json.dumps(SPEC["zones"]["z5"]))
    gate = RZ.gates_of("z5", z5)[0]
    ow = z5["guard"]["outward"]
    run = z5["guard"]["approach"]["inner"][0]
    wx, wz = run[-1][0] - ow[0], run[-1][1] - ow[1]
    over = {}
    for n in everything(fn):
        over.update(RZ.simulate_function((fn / (n + ".mcfunction")).read_text(encoding="utf-8").splitlines()))
    for y in range(g(wx, wz) + 1, g(wx, wz) + 1 + SPEC["wall"]["rise_over_floor"]):
        over[(wx, y, wz)] = "minecraft:obsidian"

    def block(x, y, z):
        b = over.get((x, y, z))
        return b if b is not None else ("terrain" if y <= g(x, z) else "minecraft:air")
    assert straight_on_problems(gate, block), "a wall column straight on from G5's inner mouth went unseen"
    assert walk_problems(gate, block) != []


# mouth_cut is what put the wall column into the approach. Unit-level, flat ground, a wall two columns out.
def test_mouth_cut_carries_the_run_through_its_own_wall():
    flat = lambda x, z: 80  # noqa: E731
    wall = frozenset({(12, 0), (13, 0)})
    assert RZ.mouth_cut((9, 0), (10, 0), 81, flat, "t") == [[11, 0, 81, None]]
    assert RZ.mouth_cut((9, 0), (10, 0), 81, flat, "t", wall) == [[11, 0, 81, None], [12, 0, 81, None],
                                                                   [13, 0, 81, None]]


TRAPPED = "gates_stand_deep_inside_their_own_zone"


def passless_reaches_knock(gate, z, knocks, block):
    """True when a player WITHOUT the pass walks from outside to the knock box and never stands in the zone's
    boxes outside a knock box -- where the zone check would turn them back before the guard could answer."""
    _n, _gid, gd, _a, _t, _e, knock = gate
    q, ow, fy = gd["block"], start_heading(gd), gd["ground_y"] + 1
    feet, reach = walker(block)

    def turned_back(x, zz):
        return (any(b[0] <= x <= b[2] and b[1] <= zz <= b[3] for b in z["boxes"])
                and not any(k[0] <= x <= k[3] and k[2] <= zz <= k[5] for k in knocks))
    o = (int(round(q[0] + ow[0] * (GH["knock_out"] + 6))), int(round(q[1] + ow[1] * (GH["knock_out"] + 6))))
    start = feet(o[0], o[1], fy)
    if start is None or turned_back(start[0], start[2]):
        return False
    ok = {c for c in reach(start, q) if not turned_back(c[0], c[2])}
    seen, dq = {start}, deque([start])
    while dq:
        x, y, zz = dq.popleft()
        if knock[0] <= x <= knock[3] and knock[2] <= zz <= knock[5] and y == knock[1]:
            return True
        for nx, nz in ((x + 1, zz), (x - 1, zz), (x, zz + 1), (x, zz - 1)):
            for ny in (y + 1, y, y - 1, y - 2, y - 3):
                if (nx, ny, nz) in ok and (nx, ny, nz) not in seen:
                    seen.add((nx, ny, nz))
                    dq.append((nx, ny, nz))
    return False


# Without it a gatehouse can walk perfectly and still be one nobody without the pass ever reaches, because the
# zone's own boxes surround it and the zone check turns them back first. G2 moved to the trailhead on 2026-10-01
# for exactly this; G1 and the three z2 posts still stand 62-153 blocks inside their zones. Strict xfail keyed
# on the record, which names the gates that fail: re-site them and it XPASSes.
@pytest.mark.slow
@pytest.mark.xfail(bool(_record(TRAPPED)) and not (_record(TRAPPED) or {}).get("fixed"), strict=True,
                   reason="data/rift_zones.json measured_defects[%s]" % TRAPPED)
def test_a_player_without_the_pass_can_walk_up_to_every_guard():
    (fn, _adv), g = real()
    block = world_of(fn, everything(fn), g)
    bad = []
    for zid, z in live_zones().items():
        gates = RZ.gates_of(zid, z)
        knocks = [x[6] for x in gates]
        bad += [x[0] for x in gates if not passless_reaches_knock(x, z, knocks, block)]
    assert bad == [], bad


# The record names exactly the gates that fail today, so a new one cannot join the xfail silently.
@pytest.mark.slow
def test_the_trapped_gates_record_names_exactly_the_gates_that_fail():
    rec = _record(TRAPPED)
    assert rec is not None
    if rec.get("fixed"):
        return
    (fn, _adv), g = real()
    block = world_of(fn, everything(fn), g)
    bad = set()
    for zid, z in live_zones().items():
        gates = RZ.gates_of(zid, z)
        knocks = [x[6] for x in gates]
        bad |= {x[0] for x in gates if not passless_reaches_knock(x, z, knocks, block)}
    assert bad == set(rec["gates"]), sorted(bad)


# Without this the walk could pass for reasons of its own. Dropping the approach from the GENERATOR -- data
# untouched (CLAUDE.md, "mutate the generator, not the record") -- must break the gates whose mouths do not meet
# the ground, by name, and leave the ones whose mouths do.
@pytest.mark.slow
def test_dropping_the_approach_from_build_breaks_the_gates_that_need_it():
    src = (ROOT / "tools" / "rift_zones.py").read_text(encoding="utf-8")
    old = '            ap = approach_columns(gd)'
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
