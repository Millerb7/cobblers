"""The Rift's zone gatehouses (tools/rift_zones.py `build`): is each one an open way with a guard beside it?

REWRITTEN 2026-10-12. The owner, after playing: "It shouldn't be a one-block corridor to squeeze through; it should just
be a guard that stops you if you can't enter." The gatehouse used to be a walled, roofed corridor with a barrier across
it (the first version of this file measured that walkway for continuity once the barrier was open). It is now an open
passage at least data/rift_zones.json gatehouse.min_width = 5 wide with nothing over it lower than min_clear = 4, a guard
on a pad beside it, and the zone's own LINE box doing the stopping.

HOW IT IS MEASURED. tools/gatehouse_audit.py parses the EMITTED .mcfunction text and shares no code with
tools/rift_zones.py (it carries its own reading of the passage's rows and lanes, its own movement model and its own
description of the retired shell). This file builds the real pack, hands the audit the texts, and proves each check bites
by mutating the GENERATOR with the data untouched (CLAUDE.md, "How to prove an audit is independent"): a mutation that
only edited data would move the expectation and the output together and prove nothing.

TWO GROUNDS. FLAT puts terrain level with each gate's floor: the plain case. PLATEAU stands the ground six blocks
above each gate's floor everywhere: the passage must be CUT through it and held open, which is the only way a width or a
clearance can be measured at all (on flat ground a narrow passage is still surrounded by walkable terrain), and it is
the shape of the old shell's fault, a tunnel of natural ground over a roofed corridor.

NOT COVERED, and it needs a running server (the `boot-test` skill, then an experiment in experiments/): that the
functions run and the line's minecraft:location advancement fires, that `tp` and `spawnpoint` put a player where the
data says, that a ridden Cobblemon is carried by `execute on vehicle run tp`, and whether any of it READS as a gate on
built ground -- a judgement a player makes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import gatehouse_audit as GA  # noqa: E402
import rift_zones as RZ  # noqa: E402

SPEC = json.loads((ROOT / "data" / "rift_zones.json").read_text(encoding="utf-8"))
GH = SPEC["gatehouse"]


# ------------------------------------------------------------------ the gates, from the data

def gates():
    """Every live gate as (name, guard id, record, arrive, turn_back, exit, knock, zone id, zone): the tool's own
    gates_of(), which is the list `build` walks; a zone whose status starts SUPERSEDED emits nothing."""
    out = []
    for zid, z in sorted(SPEC["zones"].items(), key=lambda kv: kv[1]["order"]):
        if str(z.get("status") or "").startswith("SUPERSEDED") or not z.get("guard"):
            continue
        for g in RZ.gates_of(zid, z):
            out.append(tuple(g) + (zid, z))
    return out


GATES = gates()
NAMES = [g[0] for g in GATES]
PLACES = [(tuple(g[2]["block"]), g[2]["ground_y"]) for g in GATES]


def _nearest_floor(x, z):
    return min(PLACES, key=lambda p: max(abs(p[0][0] - x), abs(p[0][1] - z)))[1]


def flat_ground(x, z):
    """Terrain level with the nearest gate's own ground: the plain case."""
    return _nearest_floor(x, z)


def plateau_ground(x, z):
    """Terrain six above the nearest gate's ground everywhere: the passage has to be cut through it."""
    return _nearest_floor(x, z) + 6


# ------------------------------------------------------------------ building the pack

def _quiet_report(_a, quiet=False):
    """cmd_report's verdict without its heightmap comparisons: only used to keep the fast build off the out-of-repo
    heightmap. The report is `rift_zones.py report`'s own business, not this file's."""
    return 0


def build_pack(ground, module=None):
    """Run the real cmd_build into a throwaway directory; return {function name: emitted text}.

    `module` lets a source-mutated copy of tools/rift_zones.py build instead, which is how the mutation proofs below
    show these tests bite the generator rather than agree with it."""
    M = module or RZ
    tmp = Path(tempfile.mkdtemp(prefix="rift_zones_test_"))
    saved = (M.PACKS, M.ground_of, M.cmd_report)
    M.PACKS = tmp
    M.ground_of = lambda _root: ground
    M.cmd_report = _quiet_report
    try:
        M.cmd_build(argparse.Namespace(source_root=os.environ.get("COBBLERS_SOURCE_ROOT")))
    finally:
        M.PACKS, M.ground_of, M.cmd_report = saved
    d = tmp / M.PACK / "data" / M.NS / "function" / M.FOLDER
    return {p.stem: p.read_text(encoding="utf-8") for p in d.glob("*.mcfunction")}


_CACHE = {}


def built(kind):
    if kind not in _CACHE:
        _CACHE[kind] = build_pack(flat_ground if kind == "flat" else plateau_ground)
    return _CACHE[kind]


def audited(texts, ground):
    return GA.audit(texts, SPEC, ground)


def mutant(old, new):
    """A copy of tools/rift_zones.py with one line of source changed, imported as its own module.

    MUTATE THE GENERATOR, NOT THE RECORD (CLAUDE.md): data/rift_zones.json is untouched by every proof below and the
    only thing that moves is the code that lays the gatehouse."""
    src = (ROOT / "tools" / "rift_zones.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, "the line to mutate is not in tools/rift_zones.py exactly once: %r" % old
    mod = types.ModuleType("rift_zones_mutant")
    mod.__file__ = str(ROOT / "tools" / "rift_zones.py")
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


# ------------------------------------------------------------------ the data's own promises

# Without it the owner's floor ("at least 5 blocks wide") can be edited away in the data and every check that reads
# the number follows it down.
def test_the_data_keeps_the_owners_floor_of_five_wide_and_four_clear():
    assert GH["min_width"] == 5 and GH["min_clear"] == 4
    assert GH["walkway"] >= 5, "the passage is %d wide" % GH["walkway"]
    assert GH["clear_above"] + 1 >= 4 and GH["arch_at"] >= 4 and GH["post_height"] == GH["arch_at"]


# Without it the audit could be run on an empty pack and report no problem.
def test_the_pack_holds_a_gatehouse_function_for_every_gate_and_a_guard_summon_for_every_built_one():
    texts = built("flat")
    for name in NAMES:
        assert "gatehouse_%s" % name in texts, name
    stands = GA.guard_stands(texts["guards_act"])
    held = GA.held(SPEC)
    assert set(stands) == {n for n in NAMES if n.split("_")[0] not in held}, sorted(stands)


# ------------------------------------------------------------------ the audit on the real build

# THE TEST. Without it a gatehouse ships that a player cannot walk through, or squeezes through, or finds roofed,
# or finds the retired shell still standing round it, or finds the guard in the way.
@pytest.mark.parametrize("kind,ground", [("flat", flat_ground), ("plateau", plateau_ground)])
def test_every_gatehouse_is_an_open_passage_with_the_guard_beside_it(kind, ground):
    assert audited(built(kind), ground) == []


# Without it a barrier, or any of the retired shell's materials, can be written back into a gatehouse function and
# only the audit's world model would notice. This reads the TEXT: the retired shell is gone from the generator.
@pytest.mark.parametrize("name", NAMES)
def test_no_gatehouse_function_writes_a_barrier_or_obsidian(name):
    text = built("flat")["gatehouse_%s" % name]
    for banned in ("minecraft:barrier", "minecraft:obsidian", "minecraft:crying_obsidian"):
        assert banned not in text, "%s writes %s" % (name, banned)


# Without it a light block (the owner: lanterns on posts, NEVER light blocks) can be used as dressing.
@pytest.mark.parametrize("name", NAMES)
def test_the_dressing_never_uses_a_light_block(name):
    text = built("flat")["gatehouse_%s" % name]
    assert "minecraft:light" not in text
    assert "minecraft:lantern" in text


# Without it the guard can be seated close to another NPC: reapply's npc action counts cobblemon:npc within 2 blocks
# and the site rules keep 3.5 (tools/markets.py NPC_CLEAR), so a guard 2 blocks from a clerk is a guard that
# answers for both.
def test_every_guard_stands_clear_of_every_other_npc():
    import markets
    assert markets.NPC_CLEAR == GA.NPC_CLEAR
    seats = [(s["at"][0], s["at"][2]) for s in json.loads((ROOT / "data" / "npc_seats.json")
                                                          .read_text(encoding="utf-8"))["seats"]]
    stands = GA.guard_stands(built("flat")["guards_act"])
    assert stands
    pts = [(n, v[0], v[2]) for n, v in stands.items()]
    for n, x, z in pts:
        for sx, sz in seats:
            assert ((x - sx) ** 2 + (z - sz) ** 2) ** 0.5 >= markets.NPC_CLEAR, (n, (x, z), (sx, sz))
        for n2, x2, z2 in pts:
            if n2 != n:
                assert ((x - x2) ** 2 + (z - z2) ** 2) ** 0.5 >= markets.NPC_CLEAR, (n, n2)


# ------------------------------------------------------------------ mutating the generator
#
# Each proof: the unmutated generator passes the audit on that ground (so a failure is the mutation's, not the audit's),
# then ONE line of tools/rift_zones.py changes, the data stays as it is, and the audit must name the fault for EVERY gate.

LANES_LINE = "    return list(range(-((w - 1) // 2), w // 2 + 1))"
ARCH_LINE = '            arch_y = fy + gh["arch_at"]'
PAD_LINE = '    pad_k = lo if gh["guard_side"] < 0 else hi'
DEMOLISH_LINE = "            gl += restore_lines(dem, g, terr)"
AIR_LINE = "                air.setdefault(max(top_air, g(*c)), []).append(c)"


def _bites(line, new, ground, needle, only=None):
    base = audited(built("flat" if ground is flat_ground else "plateau"), ground)
    assert base == [], "the unmutated build does not pass, so there is nothing to mutate: %s" % base[:2]
    texts = build_pack(ground, module=mutant(line, new))
    bad = audited(texts, ground)
    for name in (only or NAMES):
        mine = [b for b in bad if b.startswith(name + " ") or b.startswith(name + ":")]
        assert any(needle in b for b in mine), (
            "%s: the mutation went unseen by the audit (wanted %r among %s)" % (name, needle, mine[:3] or "no problem"))


# Without it "narrower than the passage width" is a check nobody has seen fail. The generator is made to lay four lanes
# for a gatehouse the data says is six wide; on ground that must be cut, every row of every gate is under 5.
def test_a_passage_narrower_than_five_fails_the_audit():
    _bites(LANES_LINE, "    return list(range(-((w - 1) // 2), w // 2 - 1))", plateau_ground, "under gatehouse.min_width")


# Without it "an overhang under four blocks" is a check nobody has seen fail. The generator puts the beam three above
# the floor; the audit must find a block within four of the floor in the passage.
def test_a_beam_lower_than_four_blocks_fails_the_audit():
    _bites(ARCH_LINE, "            arch_y = fy + 3", flat_ground, "within 4 of the floor")


# Without it "a roof or a natural tunnel over the way" is a check nobody has seen fail. The generator clears only two
# blocks of air over the floor and no longer cuts higher ground open; on the plateau the ground above stays, which is the
# old shell's tunnel.
def test_a_tunnel_of_natural_ground_over_the_passage_fails_the_audit():
    _bites(AIR_LINE, "                air.setdefault(fy + 1, []).append(c)", plateau_ground, "within 4 of the floor")


# Without it "the guard stands in the walk line" is a check nobody has seen fail. The generator seats the guard in the
# guard's own lane (lane 0) instead of beside the passage.
def test_a_guard_standing_in_the_walk_line_fails_the_audit():
    _bites(PAD_LINE, "    pad_k = 0", flat_ground, "IN the walk line", only=[n for n in NAMES if n != "z4"])


# Without it "the retired shell is gone" is a check nobody has seen fail. The generator skips the demolition; the walls,
# frame and barrier of the 2026-10-03 shell, which the world holds today, are left standing.
def test_a_build_that_leaves_the_retired_shell_standing_fails_the_audit():
    _bites(DEMOLISH_LINE, "            pass", flat_ground, "retired shell are still standing")


# ------------------------------------------------------------------ the turn-back

# Without it a turned-back player is teleported INTO the zone that just turned them back and is turned back
# again, from where they were put: the turn-back must lie outside every box of the zone it defends.
@pytest.mark.parametrize("gate", GATES, ids=NAMES)
def test_every_turn_back_point_is_outside_the_zone_it_defends(gate):
    tb, z = gate[4], gate[8]
    c = (int(tb[0] - 0.5), int(tb[2] - 0.5))
    inside = [b for b in z["boxes"] if b[0] <= c[0] <= b[2] and b[1] <= c[1] <= b[3]]
    assert not inside, ("%s: the turn-back %s is inside its own zone's box %s, so the player is turned back "
                        "from where they were just put" % (gate[0], c, inside[0]))


# Without it an outside-sited gate's turn-back can be flung across the Rift instead of put back at the door it
# just failed. G2 stands on Victory Road at the trailhead and its turn-back belongs turn_back_out = 8 blocks
# back down the road, at the gatehouse's own door, where the player can try again.
def test_an_outside_sited_gates_turn_back_is_at_its_own_door():
    outside = [g for g in GATES if g[2]["side"] == "outside"]
    assert [g[0] for g in outside] == ["z2"], (
        "the set of outside-sited gates changed: %s" % [g[0] for g in outside])
    for g in outside:
        tb, q = g[4], g[2]["block"]
        d = max(abs(int(tb[0] - 0.5) - q[0]), abs(int(tb[2] - 0.5) - q[1]))
        assert d <= GH["turn_back_out"], (
            "%s: the turn-back is %d blocks from the guard's block, past turn_back_out %d"
            % (g[0], d, GH["turn_back_out"]))


# ------------------------------------------------------------------ with the heightmap

def _source_root():
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT is not set: the heightmap is outside the repo")
    return root


# Without it every test above is about a terrain the real tool never builds on. The same audit, the real build, the
# canonical heightmap's ground.
@pytest.mark.slow
def test_the_audit_passes_on_the_real_build_over_the_real_heightmap():
    import ground as GD
    g = GD.load(_source_root())
    assert audited(build_pack(g), g) == []


# Without it a guard's ground_y is whatever was typed and its pad floats or buries: the ground a placement stands on
# comes from tools/ground.py, rounded, and never from a world (CLAUDE.md).
@pytest.mark.slow
@pytest.mark.parametrize("gate", GATES, ids=NAMES)
def test_every_guards_ground_is_the_heightmaps_ground(gate):
    import ground as GD
    g = GD.load(_source_root())
    q = gate[2]["block"]
    assert gate[2]["ground_y"] == g(q[0], q[1]), (
        "%s: ground_y %d, heightmap y%d at %s" % (gate[0], gate[2]["ground_y"], g(q[0], q[1]), q))


# Without it a player is teleported into rock or one block above the floor. The arrival stands ON the passage, which is
# laid flat at the guard's feet level, so it is checked against the heightmap at the GUARD'S block; the turn-back stands
# outside, on terrain the gatehouse never touches, so it keeps its own column.
@pytest.mark.slow
@pytest.mark.parametrize("gate", GATES, ids=NAMES)
def test_every_gates_places_stand_on_the_floor_a_player_actually_stands_on(gate):
    import ground as GD
    g = GD.load(_source_root())
    bx, bz = gate[2]["block"][0], gate[2]["block"][1]
    floor = g(bx, bz) + 1
    arrive, tb = gate[3], gate[4]
    assert int(arrive[1]) == floor, (
        "%s: the arrival is at y%s, but the passage it stands on is laid flat at the guard's feet level y%d "
        "(heightmap y%d at the guard's block (%d, %d))" % (gate[0], arrive[1], floor, floor - 1, bx, bz))
    x, y, z = tb[0] - 0.5, tb[1], tb[2] - 0.5
    assert int(y) == g(int(x), int(z)) + 1, (
        "%s: the turn-back is at y%s, the heightmap's ground at its own column (%d, %d) is y%d"
        % (gate[0], y, int(x), int(z), g(int(x), int(z))))
