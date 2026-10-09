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
that the barrier cannot be jumped or pearled. The zone check's LOGIC is covered since 2026-10-04 (qualify on entry,
at the end of this file, also written by the implementer at the caller's request): a small interpreter runs the
emitted functions against a modelled player. Whether the server agrees with that interpreter is not covered.
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
    assert any("\"z1\"" in ln for ln in _lines(fn, "guards_act"))


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
# Since 2026-10-08 (N155) the summon waits for a look that sees a guard stand in EVERY guard's chunk, or blind,
# read by tools/chunk_look_audit.py with the guards' positions taken from the data here.
def test_one_placeholder_per_built_gate_and_the_old_ones_go():
    import chunk_look_audit as CA
    fn, _adv = fast()
    pack = fn.parents[3]
    sites = [tuple(g[2]["block"]) for zid, z in live_zones().items() if built(z) for g in RZ.gates_of(zid, z)]
    assert CA.problems(pack, "cobblers:rift_zones/guards", "cobblers_rift_guard", "R9Z guards", sites=sites) == []
    fn, _adv = fast()
    for p in fn.glob("gatehouse_*.mcfunction"):
        assert "summon" not in p.read_text(encoding="utf-8"), p.stem
    want = {}
    for zid, z in live_zones().items():
        if built(z):
            for g in RZ.gates_of(zid, z):
                want[g[0]] = (g[2]["block"][0], g[2]["ground_y"] + 1, g[2]["block"][1])
    placed = {}
    for ln in _lines(fn, "guards_act"):
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
    assert any(ln.startswith("schedule function cobblers:rift_zones/guards_look") for ln in _lines(fn, "guards"))
    assert any(ln.startswith("schedule function cobblers:rift_zones/guards_done") for ln in _lines(fn, "guards_act"))
    assert RZ.guard_count(SPEC) == len(want)


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
    gatehouse, to there. Read from the data, not from the generator.

    EXCEPT where the record declares its own `axis` (G5): there the surveyed line is the traced mask's nearest
    edge, 90 degrees off the way through, and the player arrives along the declared axis (north up
    entrance_to_e4, axis.why). Starting on the surveyed line there put both walks' ends beside the gatehouse,
    east and west of league_gate, and no walk came from the south at all (qa review of a450a05, 2026-10-03)."""
    if gd.get("axis"):
        return gd["axis"]["outward"]
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


# ------------------------------------------------------------------ qualify on entry
#
# docs/world-building/CRITICAL_PATH_WALK_2.md item 1: Victory Road's fights 8-10 lie inside z5's boxes, 40 blocks
# under G5, and the zone check tested only the score a knock box sets, so a player holding rift_crisis_resolved
# who walked the caves north was teleported to the turn-back. These tests RUN the emitted advancement and
# functions with their own small interpreter (this file's, not the generator's): the location advancement's
# boxes decide whether the zone check fires, and the .mcfunction text decides what it does to the player.

def _selector_args(sel):
    """'@s[a=1,advancements={x=true,y=true}]' -> [('a', '1'), ('advancements', '{x=true,y=true}')]."""
    assert sel.startswith("@s"), sel
    if sel == "@s":
        return []
    body, out, cur, depth = sel[3:-1], [], "", 0
    for ch in body:
        depth += ch == "{"
        depth -= ch == "}"
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [tuple(a.split("=", 1)) for a in out if a]


def _matches(player, sel):
    """This file's reading of a selector on @s: gamemode, advancements and a dx/dy/dz volume."""
    args = dict()
    for k, v in _selector_args(sel):
        if k == "gamemode":
            if v.startswith("!") and player["gamemode"] == v[1:]:
                return False
            if not v.startswith("!") and player["gamemode"] != v:
                return False
        elif k == "advancements":
            for term in v.strip("{}").split(","):
                a, want = term.split("=")
                if (a in player["advancements"]) != (want == "true"):
                    return False
        else:
            args[k] = int(v)
    if "x" in args:
        x, y, z = player["pos"]
        for c, p in (("x", x), ("y", y), ("z", z)):
            if not args[c] <= p < args[c] + args["d" + c] + 1:
                return False
    return True


def _run(fn_dir, line, player, depth=0):
    """Run one command line against `player`. Only the commands the zone functions use are understood; anything
    else raises, so a new command cannot be silently skipped."""
    assert depth < 8
    t = line.split()
    if t[0] == "execute":
        i = 1
        while i < len(t):
            if t[i] in ("if", "unless"):
                want = t[i] == "if"
                if t[i + 1] == "entity":
                    ok, i = _matches(player, t[i + 2]), i + 3
                elif t[i + 1] == "score":
                    assert t[i + 2] == "@s" and t[i + 4] == "matches" and t[i + 5] == "1..", t
                    ok, i = player["scores"].get(t[i + 3], None) is not None and player["scores"][t[i + 3]] >= 1, i + 6
                else:
                    raise AssertionError("unknown execute test: %s" % line)
                if ok != want:
                    return
            elif t[i] == "on" and t[i + 1] == "vehicle":
                return   # the test player rides nothing
            elif t[i] == "run":
                return _run(fn_dir, " ".join(t[i + 1:]), player, depth + 1)
            else:
                raise AssertionError("unknown execute part: %s" % line)
        return
    if t[0] == "function":
        ns, path = t[1].split(":", 1)
        assert path.startswith(RZ.FOLDER + "/"), t[1]
        for ln in _lines(fn_dir, path[len(RZ.FOLDER) + 1:]):
            _run(fn_dir, ln, player, depth + 1)
    elif t[0] == "scoreboard" and t[1:3] == ["players", "set"] and t[3] == "@s":
        player["scores"][t[4]] = int(t[5])
    elif t[0] == "tp" and t[1] == "@s":
        player["pos"] = (float(t[2]), float(t[3]), float(t[4]))
        player["turned_back"] = True
    elif t[0] in ("title", "tellraw", "spawnpoint", "advancement"):
        pass
    else:
        raise AssertionError("unknown command: %s" % line)


def _fires(adv_dir, name, pos):
    """Whether a minecraft:location advancement's boxes contain `pos`, read from the emitted JSON."""
    doc = json.loads((adv_dir / (name + ".json")).read_text(encoding="utf-8"))
    conds = doc["criteria"]["here"]["conditions"]["player"]
    terms = conds[0]["terms"] if conds[0]["condition"] == "minecraft:any_of" else conds

    def inside(term):
        p = term["predicate"]["location"]["position"]
        return all(p[c]["min"] <= v < p[c]["max"] for c, v in zip("xyz", pos))
    return any(inside(term) for term in terms)


def _enter(fn_dir, adv_dir, zid, pos, advancements):
    """A survival player with no pass score stands at `pos`; the zone's location advancement must fire there and
    its reward runs (twice: the advancement is revoked and fires again while the player stays)."""
    assert _fires(adv_dir, "%s_zone" % zid, pos), "%s's zone check does not fire at %s" % (zid, pos)
    player = {"pos": pos, "gamemode": "survival", "advancements": set(advancements), "scores": {},
              "turned_back": False}
    for _ in range(2):
        _run(fn_dir, "function %s:%s/%s/zone" % (RZ.NS, RZ.FOLDER, zid), player)
        if player["turned_back"]:
            break
    return player


def _testable_enforced():
    return sorted(zid for zid, z in live_zones().items()
                  if enforced(z) and z["pass"]["kind"] in ("badges", "flag") and z["pass"].get("advancements"))


def _far_point(zid, z):
    """A point inside one of the zone's boxes, at least 32 blocks from every knock box, from the data."""
    knocks = knocks_of(z)
    for b in z["boxes"]:
        cx, cz = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
        if all(abs(cx - (k[0] + k[3]) / 2) > 32 or abs(cz - (k[2] + k[5]) / 2) > 32 for k in knocks):
            return (cx + 0.5, 40.0, cz + 0.5)
    raise AssertionError("%s has no box 32 blocks from a knock" % zid)


def test_the_zones_with_a_server_testable_pass_are_enforced_today():
    # the tests below are vacuous if no zone qualifies; z5 is the one the walk found
    assert "z5" in _testable_enforced(), _testable_enforced()


def _vr_seat(index):
    """Victory Road's stand `index` as a feet position, from data/vr_trainers.json (hand-authored, not this tool's)."""
    vr = json.loads((ROOT / "data" / "vr_trainers.json").read_text(encoding="utf-8"))
    s = next(t["seat"] for t in vr["trainers"] if t["stand_index"] == index)
    return (s[0] + 0.5, float(s[1]), s[2] + 0.5)


def _admit_point(zid, z):
    """Where a pass holder walks in and is admitted: anywhere away from a knock, except in a zone whose pass is
    earned only inside it (z5, pass.admit_within, 2026-10-08), where it is Victory Road's eighth stand, the first
    fight inside z5 and in the cave it is earned in."""
    return _vr_seat(8) if z["pass"].get("admit_within") else _far_point(zid, z)


@pytest.mark.parametrize("zid", _testable_enforced())
def test_a_player_holding_the_pass_who_enters_away_from_any_knock_is_not_turned_back(zid):
    z = live_zones()[zid]
    fn, adv = fast()
    pos = _admit_point(zid, z)
    for k in knocks_of(z):
        assert not _matches({"pos": pos, "gamemode": "survival", "advancements": set()},
                            "@s[%s]" % RZ.sel_box(k))
    player = _enter(fn, adv, zid, pos, z["pass"]["advancements"])
    assert not player["turned_back"], "%s turned back a qualified player at %s" % (zid, pos)
    assert player["pos"] == pos, "the admit teleported the player"
    assert player["scores"].get(SPEC["pass"]["objective_prefix"] + zid) == 1


@pytest.mark.parametrize("zid", _testable_enforced())
def test_a_player_without_the_pass_is_still_turned_back(zid):
    z = live_zones()[zid]
    fn, adv = fast()
    pos = _far_point(zid, z)
    tx, ty, tz, _yaw = z["turn_back"]
    advs = z["pass"]["advancements"]
    # none of it, and (for a multi-advancement pass) all but the last: both are passless
    for held in ([], advs[:-1]) if len(advs) > 1 else ([],):
        player = _enter(fn, adv, zid, pos, held)
        assert player["turned_back"], "%s let a player holding only %s stay at %s" % (zid, held, pos)
        assert player["pos"] == (tx, float(int(ty)), tz)
        assert SPEC["pass"]["objective_prefix"] + zid not in player["scores"]


def test_victory_roads_last_fights_are_inside_z5_and_open_to_a_player_who_released_hoopa():
    # Since 2026-10-08 (pass.admit_within) the flag admits only in the cave ground at z5's south edge, which the
    # eighth stand is in; a player who walked up from there holds the score at the ninth and tenth.
    obj = SPEC["pass"]["objective_prefix"] + "z5"
    fn, adv = fast()
    z5 = live_zones()["z5"]
    flag = z5["pass"]["advancements"]
    for index in (8, 9, 10):
        pos = _vr_seat(index)
        assert _fires(adv, "z5_zone", pos), "stand %s is no longer inside z5: re-read the walk's item 1" % (pos,)
        walked_up = _enter(fn, adv, "z5", pos, flag) if index == 8 else None
        if walked_up is None:
            player = {"pos": pos, "gamemode": "survival", "advancements": set(flag), "scores": {obj: 1},
                      "turned_back": False}
            _run(fn, "function %s:%s/z5/zone" % (RZ.NS, RZ.FOLDER), player)
            walked_up = player
        assert not walked_up["turned_back"], pos
        assert _enter(fn, adv, "z5", pos, [])["turned_back"], pos


def test_a_flag_holder_over_the_precinct_who_never_walked_the_caves_is_turned_back():
    # the closure (docs/world-building/CRITICAL_PATH_WALK_2.md item 3): on the surface or in the sky over z5, the flag
    # alone is not a pass; only the score earned in the caves is
    z5 = live_zones()["z5"]
    fn, adv = fast()
    x, _y, zz = _far_point("z5", z5)
    for y in (90.0, 140.0):
        player = _enter(fn, adv, "z5", (x, y, zz), z5["pass"]["advancements"])
        assert player["turned_back"], "z5 let a flag holder stay at %s without the score" % ((x, y, zz),)


# Without it the interpreter above could pass for reasons of its own. Dropping qualify on entry from the GENERATOR --
# data untouched (CLAUDE.md, "mutate the generator, not the record") -- must bring the walk's blocker back.
def test_dropping_qualify_on_entry_from_build_turns_a_qualified_player_back_in_victory_roads_caves():
    src = (ROOT / "tools" / "rift_zones.py").read_text(encoding="utf-8")
    old = "FOLDER, zid)] + entry + ["
    assert src.count(old) == 1
    mod = types.ModuleType("rift_zones_no_entry")
    mod.__file__ = str(ROOT / "tools" / "rift_zones.py")
    exec(compile(src.replace(old, "FOLDER, zid)] + ["), mod.__file__, "exec"), mod.__dict__)
    mfn, madv = build(module=mod)
    # the eighth stand: the one the unmutated build admits a flag holder at (the test above)
    assert _enter(mfn, madv, "z5", _vr_seat(8), live_zones()["z5"]["pass"]["advancements"])["turned_back"]


def test_a_player_at_the_knock_is_still_answered_by_the_guard():
    # the knock is kept, as a door: a player who earned z5's score in the caves is granted and arrives on the
    # walkway; since 2026-10-08 (pass.knock_needs_score) the flag alone is refused there, which was the surface skip
    z5 = live_zones()["z5"]
    obj = SPEC["pass"]["objective_prefix"] + "z5"
    fn, _adv = fast()
    k = z5["knock"]
    at_k = (k[0] + 0.5, float(k[1]), k[2] + 0.5)
    flag_only = {"pos": at_k, "gamemode": "survival", "advancements": set(z5["pass"]["advancements"]), "scores": {},
                 "turned_back": False}
    _run(fn, "function %s:%s/z5/knock" % (RZ.NS, RZ.FOLDER), flag_only)
    assert flag_only["pos"] == at_k and obj not in flag_only["scores"], "G5 let in a flag holder who never walked the caves"
    player = dict(flag_only, scores={obj: 1}, pos=at_k)
    _run(fn, "function %s:%s/z5/knock" % (RZ.NS, RZ.FOLDER), player)
    ax, ay, az, _ = z5["arrive"]
    assert player["pos"] == (ax, float(int(ay)), az)
    assert player["scores"][obj] == 1
    passless = dict(player, advancements=set(), scores={}, pos=(k[0] + 0.5, float(k[1]), k[2] + 0.5))
    _run(fn, "function %s:%s/z5/knock" % (RZ.NS, RZ.FOLDER), passless)
    assert passless["scores"] == {} and passless["pos"] == (k[0] + 0.5, float(k[1]), k[2] + 0.5)
    # and the zone check leaves a passless player standing in the knock box to be answered
    passless["turned_back"] = False
    _run(fn, "function %s:%s/z5/zone" % (RZ.NS, RZ.FOLDER), passless)
    assert not passless["turned_back"]
