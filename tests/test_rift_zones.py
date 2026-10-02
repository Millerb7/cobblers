"""The Rift's zone gatehouses (tools/rift_zones.py `build`): can a player actually WALK through one?

tools/rift_zones.py had no tests. This file is the first, written by the test author from the design
(docs/mechanics/RIFT_ZONES.md section 6 and data/rift_zones.json's own `gatehouse` block), not from the
generator's geometry: every column it reasons about is PARSED OUT OF THE EMITTED .mcfunction, because an
expectation derived from the code under test is not an expectation (CLAUDE.md, "Verify before claiming").

THE PROPERTY. A gatehouse is "a one-wide roofed walkway ... closed by a two-high barrier column directly
behind the guard" (data/rift_zones.json gatehouse.why). So the standable columns the shell emits must form ONE
piece a player can walk, from the knock box outside the guard to the exit box inside, broken in exactly one
place: the barrier. The flood fill is FOUR-CONNECTED, because a player cannot step diagonally between two
blocks that meet only at a corner when both orthogonal corners are solid -- and an eight-connected fill would
call every gatehouse in this repository connected and report nothing.

WHAT IS INERT, AND THEREFORE NOT ASSERTED HERE. `cobblers_rift_zones` is in tools/reapply.py's EXCLUDED, R9Z
places 6 of the 10 shells, z4 and z5 are held because `rift_crisis_resolved` has no setter on any branch, and
every guard is an armour-stand placeholder. Nothing here asserts the system is installed, enabled or reachable
in game, and a held zone is not a failure. `build` is allowed to exit 1 on its OWED dependencies; this file
does not treat that as a problem either.

HOW THE KNOWN DEFECT IS CARRIED. The recorded walkway break is a STRICT xfail keyed on the record itself
(RECORDED_BREAK below, read out of data/rift_zones.json measured_defects). Delete the record and the marks
vanish and these tests fail hard; fix the generator and leave the record and the strict xfail turns the pass
into a failure saying the record is stale. Defects this file found that the record does NOT cover are in
FOUND_HERE under the same discipline. Nothing here edits data/ or tools/.

NOT COVERED, and it needs a running server (the `boot-test` skill, then an experiment in experiments/):
  - that any of this lands: that the functions run, that the minecraft:location advancements over the knock,
    exit and zone boxes fire, that `tp` and `spawnpoint` put a player where the data says, that a ridden
    Cobblemon is carried by `execute on vehicle run tp` (data/rift_zones.json unproven);
  - that a player cannot sprint-jump, pearl or fly over a barrier, and cannot reach a knock box from INSIDE
    its zone and use it as a free pass (RIFT_ZONES.md section 6's guard experiment, unrun);
  - whether G2 READS as a gate now that it stands on open ground (unproven[6]): a judgement on built ground;
  - the cross-walls. This file tests the gatehouse shells only; the wall columns are `report`'s business.
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
GH = SPEC["gatehouse"]
AIR = "minecraft:air"
BARRIER = "minecraft:barrier"

# The record the strict xfails below quote, by id, out of data/rift_zones.json.
RECORDED_BREAK = "gatehouse_walkway_is_not_continuous"

# Defects THIS FILE found, 2026-10-01, that data/rift_zones.json measured_defects does not record. Strict
# xfail keyed (gate, property): the moment the generator or the data changes, each flips to a failure and must
# be removed along with the fix. Reported to the owner; nothing outside tests/ was touched.
FOUND_HERE = {
    ("z5", "places"):
        "z5's arrival is 14 blocks inside the guard's block and its exit box 16, because survey() anchors an "
        "inside-sited gate's places on zone_begins_at -- 11 blocks in for z5, the first column inside the "
        "8-grid boxes -- while cmd_build lays the shell from the guard's OWN block out to exit_in + 1 = 6. "
        "Both places therefore stand on open terrain past the end of the walkway, not on it. z5 is the only "
        "gate with zone_begins_in != 0. Found by tests/test_rift_zones.py.",
    # RETIRED 2026-10-01 by decision B12, not by a change here. The rim post's exit box column (3879, 3819)
    # was step t=5's own walkway centre, which step t=6's wall fill overwrote with obsidian -- the exit box
    # was inside a wall, not beside one. walkway_shell() now lays the walls as the COMPLEMENT of the walked
    # set, and a complement cannot contain a column of the thing it is the complement of, so the whole class
    # is gone rather than this one instance. The strict xfail turned into an XPASS on the first run after the
    # fix landed, which is the mark doing its job.
    ("z2_victory_road_descent", "places"):
        "the descent post's arrival and exit box are at y88 while the shell lays its walkway flat at the "
        "guard's own feet level y87 (ground_y 86 + 1): survey() takes each place's y from tools/ground.py at "
        "its own column and nothing reconciles that with the flat walkway. Found by tests/test_rift_zones.py.",
    ("z2_wilds_slip", "places"):
        "the wilds ranger's arrival is at y93 and its exit box at y97 while its walkway is flat at y95: the "
        "ground falls 2 and rises 2 across the nine columns and the places follow it, the walkway does not. "
        "Found by tests/test_rift_zones.py.",
}


def recorded_break():
    """The recorded walkway defect's reason, or None once it is no longer live.

    A defect stops being live either by leaving the file or by gaining a `fixed` field. The second is what
    this repository actually does -- a measured_defects entry is a RECORD and is kept after the fix, with
    `fixed` and `fixed_measured` saying what changed and what was re-measured -- so keying only on the id
    would hold these tests at xfail forever after the generator was repaired. B12 is exactly that case."""
    for d in SPEC.get("measured_defects", []):
        if d["id"] == RECORDED_BREAK and not d.get("fixed"):
            return "data/rift_zones.json measured_defects[%s]: %s." % (RECORDED_BREAK, d["what"].split(". ")[0])
    return None


# ------------------------------------------------------------------ the gates, from the data

def gates():
    """Every live gate as (name, guard id, record, arrive, turn_back, exit, knock, zone id, zone).

    Straight out of data/rift_zones.json through the tool's own gates_of(), which is the list `build` walks:
    a zone whose status starts SUPERSEDED emits nothing and is not a gate."""
    out = []
    for zid, z in sorted(SPEC["zones"].items(), key=lambda kv: kv[1]["order"]):
        if str(z.get("status") or "").startswith("SUPERSEDED") or not z.get("guard"):
            continue
        for g in RZ.gates_of(zid, z):
            out.append(tuple(g) + (zid, z))
    return out


GATES = gates()
NAMES = [g[0] for g in GATES]

# The two gates whose in/out axis is axis-aligned. data/rift_zones.json measured_defects calls them correct
# ("the two axis-aligned gates, z4 (5 of 8) and z5 (3 of 8), break ONLY at their barrier and are correct"),
# so they are not xfailed for the recorded break -- which is what makes these tests able to pass at all.
DIAGONAL = [g[0] for g in GATES
            if abs(g[2]["outward"][0]) not in (0.0, 1.0) or abs(g[2]["outward"][1]) not in (0.0, 1.0)]


# Where the RECORDED break shows up in a check other than the two it was recorded against. Still keyed on the
# record -- delete the record and these marks go with it -- but named gate by gate, because the symptom is not
# uniform: only G1's own block comes out of the fill as a piece of one.
RECORDED_SYMPTOMS = {
    ("z1", "knock"): "at G1 the guard's block (3100, 3270) is a piece of ONE: both diagonal shifts next to it "
                     "seal, so the knock box is standable and still not on the guard's side of anything.",
}


def param(code):
    """One pytest.param per live gate, strict-xfailed where a defect is on record for (gate, code)."""
    out = []
    for g in GATES:
        why = FOUND_HERE.get((g[0], code))
        if why is None and code in ("walkway", "barrier") and g[0] in DIAGONAL:
            why = recorded_break()
        if why is None and (g[0], code) in RECORDED_SYMPTOMS and recorded_break():
            why = "%s %s" % (recorded_break(), RECORDED_SYMPTOMS[(g[0], code)])
        marks = [pytest.mark.xfail(strict=True, reason=why)] if why else []
        out.append(pytest.param(g, marks=marks, id=g[0]))
    return out


# ------------------------------------------------------------------ reading the emitted function

def voxels(text):
    """{(x, y, z): block} from an emitted .mcfunction, commands applied IN ORDER so a later write wins.

    Parsed, never re-derived: this is the only thing this file knows about the shape of a shell. Handles the
    `execute ... run fill` form and the forceload lines tools/function_limits.py wraps round every function
    that writes blocks."""
    vox = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if " run " in line:
            line = line.split(" run ", 1)[1].strip()
        p = line.split()
        if p[0] == "fill" and len(p) >= 8:
            x0, y0, z0, x1, y1, z1 = (int(v) for v in p[1:7])
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        vox[(x, y, z)] = p[7]
        elif p[0] == "setblock" and len(p) >= 5:
            vox[(int(p[1]), int(p[2]), int(p[3]))] = p[4]
    return vox


def standable(vox, fy, open_blocks=()):
    """{(x, z)} a player can stand on with feet at fy: a solid floor at fy-1, fy and fy+1 both passable.

    `open_blocks` is what to treat as thin air; it is how the fill asks what the walkway would be with the
    barrier taken out. A voxel the function never writes is air, so anything outside the shell has no floor
    and is not standable -- the shell carves its own interior and that interior is all this measures."""
    def solid(c):
        b = vox.get(c)
        return b is not None and b != AIR and b not in open_blocks
    return {(x, z) for (x, y, z) in vox
            if y == fy - 1 and solid((x, y, z)) and not solid((x, fy, z)) and not solid((x, fy + 1, z))}


def pieces(cells):
    """The 4-CONNECTED components of a set of columns, largest first. 8-connectivity would hide the defect."""
    seen, out = set(), []
    for c in sorted(cells):
        if c in seen:
            continue
        q, piece = deque([c]), set()
        seen.add(c)
        while q:
            x, z = q.popleft()
            piece.add((x, z))
            for n in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                if n in cells and n not in seen:
                    seen.add(n)
                    q.append(n)
        out.append(piece)
    return sorted(out, key=lambda p: (-len(p), sorted(p)[0]))


# ------------------------------------------------------------------ building the pack

def _fake_ground(x, z):
    """A flat stand-in for tools/ground.py so the GATEHOUSES can be built without the out-of-repo heightmap.

    cmd_build reads ground only for the cross-wall columns; every gatehouse block comes from the guard's own
    `ground_y` in data/rift_zones.json. test_the_gatehouses_do_not_depend_on_the_heightmap_stub proves that
    byte for byte against a build on the real heightmap, which is what licenses this."""
    return 80


def _quiet_report(_a, quiet=False):
    """cmd_report's verdict without its heightmap comparisons: only used to keep the fast build off the
    out-of-repo heightmap. The report is `rift_zones.py report`'s own business, not this file's."""
    return 0


def build_pack(ground=None, module=None, report=None):
    """Run the real cmd_build into a throwaway directory; return {gate name: emitted text}.

    `module` lets a source-mutated copy of tools/rift_zones.py build instead, which is how the mutation
    proofs below show these tests bite the generator rather than agree with it."""
    M = module or RZ
    tmp = Path(tempfile.mkdtemp(prefix="rift_zones_test_"))
    saved = (M.PACKS, M.ground_of, M.cmd_report)
    M.PACKS = tmp
    if ground is not None:
        M.ground_of = lambda _root: ground
    if report is not None:
        M.cmd_report = report
    try:
        M.cmd_build(argparse.Namespace(source_root=os.environ.get("COBBLERS_SOURCE_ROOT")))
    finally:
        M.PACKS, M.ground_of, M.cmd_report = saved
    d = tmp / M.PACK / "data" / M.NS / "function" / M.FOLDER
    return {p.stem[len("gatehouse_"):]: p.read_text(encoding="utf-8")
            for p in d.glob("gatehouse_*.mcfunction")}


_CACHE = {}


def emitted(name):
    """The gatehouse function the real cmd_build writes for one gate, built once per session."""
    if "fast" not in _CACHE:
        _CACHE["fast"] = build_pack(ground=_fake_ground, report=_quiet_report)
    return _CACHE["fast"][name]


def axial(gate, c):
    """How far column `c` lies along the gate's inward axis from the guard's own block, in blocks."""
    q, out = gate[2]["block"], gate[2]["outward"]
    return (c[0] - q[0]) * -out[0] + (c[1] - q[1]) * -out[1]


# ------------------------------------------------------------------ the properties, as problem lists
#
# Each returns [] when a gatehouse is sound. The tests assert []; the mutation proofs assert a non-empty list
# for a named gate, which is what shows the check moves when the GENERATOR moves.

def walkway_problems(gate, text):
    """The walkway is one 4-connected piece once the barrier is open, and it spans the gate."""
    fy, knock, name = gate[6][1], gate[6], gate[0]
    cols = standable(voxels(text), fy, open_blocks=(BARRIER,))
    bad = []
    if not cols:
        return ["%s: no standable column at the walkway's own level y%d" % (name, fy)]
    ps = pieces(cols)
    if len(ps) != 1:
        bad.append("%s: with the barrier open the walkway is %d disconnected pieces, not one: %s"
                   % (name, len(ps), [sorted(p) for p in ps]))
    if not any(knock[0] <= c[0] <= knock[3] and knock[2] <= c[1] <= knock[5] for c in cols):
        bad.append("%s: no standable column inside the knock box %s" % (name, knock))
    if max(axial(gate, c) for c in cols) < GH["exit_in"]:
        bad.append("%s: the walkway stops short of exit_in = %d blocks inside the guard"
                   % (name, GH["exit_in"]))
    if min(axial(gate, c) for c in cols) > -GH["knock_out"] + 1:
        bad.append("%s: the walkway stops short of knock_out = %d blocks outside the guard"
                   % (name, GH["knock_out"]))
    return bad


def barrier_problems(gate, text):
    """The barrier is the only break: two pieces, the guard on the outer one, and one column of difference."""
    fy, name, q = gate[6][1], gate[0], tuple(gate[2]["block"])
    vox = voxels(text)
    closed = standable(vox, fy)
    opened = standable(vox, fy, open_blocks=(BARRIER,))
    bad = []
    ps = pieces(closed)
    if len(ps) != 2:
        bad.append("%s: the walkway breaks in %d place(s), not one (the barrier): %s"
                   % (name, len(ps), [sorted(p) for p in ps]))
    if not any(q in p for p in ps):
        bad.append("%s: the guard's own block %s is not standable" % (name, q))
    if len(opened) != len(closed) + 1:
        bad.append("%s: opening the barrier changes %d columns, not the one barrier column"
                   % (name, len(opened) - len(closed)))
    return bad


def place_problems(gate, text):
    """The arrival and the exit box are standable columns of the walkway, at the walkway's own level."""
    fy, name, arrive, ebox = gate[6][1], gate[0], gate[3], gate[5]
    cols = standable(voxels(text), fy)
    ac = (int(arrive[0] - 0.5), int(arrive[2] - 0.5))
    ec = (ebox[0], ebox[2])
    bad = []
    if ac not in cols:
        bad.append("%s: the arrival column %s is not a standable walkway column" % (name, ac))
    if ec not in cols:
        bad.append("%s: the exit box column %s is not a standable walkway column" % (name, ec))
    if int(arrive[1]) != fy:
        bad.append("%s: the arrival is at y%s, the walkway at y%d" % (name, arrive[1], fy))
    if ebox[1] != fy:
        bad.append("%s: the exit box starts at y%d, the walkway at y%d" % (name, ebox[1], fy))
    return bad


# ------------------------------------------------------------------ the instrument itself

# Without this the fill could silently stop measuring what it claims to. An 8-connected fill, or one that
# treats the barrier as air, calls every gatehouse in this repository fine and reports nothing at all.
def test_the_fill_is_four_connected_so_a_sealed_diagonal_is_a_break():
    sealed = "\n".join([            # two walkway blocks meeting only at a corner, both corners solid
        "fill 0 9 0 0 9 0 minecraft:obsidian", "fill 1 9 1 1 9 1 minecraft:obsidian",
        "setblock 1 10 0 minecraft:obsidian", "setblock 0 10 1 minecraft:obsidian"])
    cells = standable(voxels(sealed), 10)
    assert cells == {(0, 0), (1, 1)}
    assert len(pieces(cells)) == 2, "a corner-only diagonal must count as a break, not a step"
    assert len(pieces(standable(voxels("fill 0 9 0 1 9 0 minecraft:obsidian"), 10))) == 1


# Without this a block written over a walkway column by a later command would still read as standable and the
# fill would walk through obsidian. Command order is the whole reason the barrier shows up at all: cmd_build
# fills the walkway centre with air first and the barrier over it afterwards.
def test_a_later_command_wins_so_a_walled_over_walkway_column_is_not_standable():
    vox = voxels("\n".join(["fill 0 9 0 0 9 0 minecraft:obsidian",
                            "fill 0 10 0 0 11 0 minecraft:air",
                            "fill 0 10 0 0 11 0 minecraft:barrier"]))
    assert standable(vox, 10) == set()
    assert standable(vox, 10, open_blocks=(BARRIER,)) == {(0, 0)}


# Without this the forceload wrapper would be read as a block write, or an `execute ... run fill` would be
# skipped with its fill inside it, and every count below would be about the wrong blocks.
def test_the_parser_ignores_forceload_and_reads_through_an_execute_prefix():
    text = "\n".join(["forceload add 0 0 15 15", "# a comment",
                      "execute positioned 0 0 0 run fill 0 9 0 0 9 0 minecraft:stone",
                      "forceload remove 0 0 15 15"])
    assert voxels(text) == {(0, 9, 0): "minecraft:stone"}


# ------------------------------------------------------------------ the walkway

# THE TEST. Without it a gatehouse ships as a wall with a hole: every sideways shift of cmd_build's walkway
# seals its own diagonal, so a player who walks up to the gate cannot walk out of it again. Passing the gate
# works anyway, because passing is a teleport; leaving on foot is not, and that is what breaks.
@pytest.mark.parametrize("gate", param("walkway"))
def test_every_gatehouse_walkway_is_one_walkable_piece_once_the_barrier_is_open(gate):
    assert walkway_problems(gate, emitted(gate[0])) == []


# Without it a walkway with TWO breaks passes as readily as one with none. The design has exactly one thing
# that stops a player -- the two-high barrier column directly behind the guard -- and a second break is a
# gate nobody can use, while a missing one is a gate that stops nobody.
@pytest.mark.parametrize("gate", param("barrier"))
def test_the_barrier_is_the_only_break_in_every_gatehouse_walkway(gate):
    assert barrier_problems(gate, emitted(gate[0])) == []


# Without it the six gatehouses drift apart one at a time. The recorded defect was UNIFORM across all of them,
# so "they are all alike" is the property that says a fix reached every gate and not only the one looked at.
@pytest.mark.xfail(recorded_break() is not None, strict=True, reason=recorded_break() or "")
def test_the_seven_gatehouses_break_in_the_same_number_of_places_as_each_other():
    counts = {g[0]: len(pieces(standable(voxels(emitted(g[0])), g[6][1]))) for g in GATES}
    assert len(set(counts.values())) == 1, "the gatehouses are not alike: %s" % counts


# Without it the way out sits off the walkway, or inside one of its own walls, and nothing says so: the design
# puts the arrival and the exit box ON the walkway, and a place that is not standable at the walkway's own
# level is a place a player reaches by falling into it, or not at all.
@pytest.mark.parametrize("gate", param("places"))
def test_every_gates_arrival_and_exit_box_sit_on_the_walkway_the_shell_builds(gate):
    assert place_problems(gate, emitted(gate[0])) == []


# Without it a knock box ends up somewhere no player can stand, and nothing ever calls qualify: the knock box
# is the ONE thing that runs a zone's qualify (data/rift_zones.json gatehouse.knock_why), and before it
# existed the walls simply sealed the Rift.
@pytest.mark.parametrize("gate", param("knock"))
def test_every_knock_box_has_a_standable_column_on_the_guards_side_of_the_barrier(gate):
    fy, knock, q = gate[6][1], gate[6], tuple(gate[2]["block"])
    cols = standable(voxels(emitted(gate[0])), fy)
    inside = {c for c in cols if knock[0] <= c[0] <= knock[3] and knock[2] <= c[1] <= knock[5]}
    assert inside, "%s: no standable column in the knock box %s at y%d" % (gate[0], knock, fy)
    outer = next(p for p in pieces(cols) if q in p)
    assert inside & outer, ("%s: the knock box %s is standable but not on the guard's own side of the barrier"
                            % (gate[0], knock))
    assert knock[1] == fy and knock[4] - knock[1] == 1, (
        "%s: the knock box must be a player's two-block height at the walkway's own level" % gate[0])


# Without it a guard is sited in mid-air or inside its own shell, and the NPC Codex writes there has nothing
# to stand on.
@pytest.mark.parametrize("gate", GATES, ids=NAMES)
def test_every_guard_stands_on_a_standable_column_of_its_own_gatehouse(gate):
    fy, q = gate[6][1], tuple(gate[2]["block"])
    assert q in standable(voxels(emitted(gate[0])), fy), (
        "%s: the guard's block %s is not standable at y%d" % (gate[0], q, fy))
    assert gate[2]["ground_y"] + 1 == fy, (
        "%s: the guard's feet level y%d is not its ground_y %d + 1" % (gate[0], fy, gate[2]["ground_y"]))


# Without it the roof over the walkway can be left off and a player jumps the guard instead of asking it
# (data/rift_zones.json gatehouse.why: "roofed at y+2 so nothing jumps the guard").
@pytest.mark.parametrize("gate", GATES, ids=NAMES)
def test_every_standable_walkway_column_is_roofed_at_the_designs_height(gate):
    fy = gate[6][1]
    vox = voxels(emitted(gate[0]))
    roof = fy + GH["roof_at"]
    open_cols = [c for c in standable(vox, fy)
                 if vox.get((c[0], roof, c[1])) in (None, AIR)]
    assert not open_cols, "%s: %d standable walkway column(s) have no roof at y%d: %s" % (
        gate[0], len(open_cols), roof, sorted(open_cols))


# Without it a defect could be carried here on a non-strict xfail, or on a reason that traces to nothing: a
# non-strict xfail stays green after the fix lands, which is how a stale defect record survives for months.
def test_every_defect_this_file_carries_is_a_strict_xfail_that_traces_to_a_record():
    seen = 0
    for code in ("walkway", "barrier", "places", "knock"):
        for p in param(code):
            for m in getattr(p, "marks", ()):
                if m.name != "xfail":
                    continue
                seen += 1
                assert m.kwargs.get("strict") is True, (code, p.id)
                why = m.kwargs.get("reason") or ""
                assert RECORDED_BREAK in why or "Found by tests/test_rift_zones.py" in why, (code, p.id, why)
    # The marks keyed to the RECORD exist only while the record is live: once it carries `fixed`, both the
    # per-gate walkway marks and the symptom marks must be gone, and a stale count here would hide that.
    expected = len(FOUND_HERE) + (2 * len(DIAGONAL) + len(RECORDED_SYMPTOMS) if recorded_break() else 0)
    assert seen == expected, (
        "the defects carried here changed: %d marks, expected %d (recorded break is %s)"
        % (seen, expected, "live" if recorded_break() else "fixed"))


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


# ------------------------------------------------------------------ mutating the generator

def mutant(old, new):
    """A copy of tools/rift_zones.py with one line of source changed, imported as its own module.

    MUTATE THE GENERATOR, NOT THE RECORD (CLAUDE.md): data/rift_zones.json is untouched by both proofs below
    and the only thing that moves is the code that lays the shell. A mutation test that only ever edits data
    proves nothing, because the data is what both sides read."""
    src = (ROOT / "tools" / "rift_zones.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, "the line to mutate is not in tools/rift_zones.py exactly once: %r" % old
    mod = types.ModuleType("rift_zones_mutant")
    mod.__file__ = str(ROOT / "tools" / "rift_zones.py")
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


# The two lines of walkway_shell() that B12 replaced the per-step perpendicular pair with. The old target,
# `px, pz = (0, 1) if abs(dx) > abs(dz) else (1, 0)`, is the line the fix DELETED, so both proofs below were
# re-pointed here by the integrating session -- the mutations still change the GENERATOR and still leave
# data/rift_zones.json untouched, which is the property that matters.
# B12 deleted the perpendicular pair AND reordered cmd_build to emit the walkway's air AFTER the walls, so
# a mutation that merely walls over the walkway is now carved back out by the air pass and proves nothing.
# Both proofs therefore target walkway_path(), which decides the SHAPE the air is laid over.
CORNER_JOIN = "            path.append((ax + sx, az) if abs(dx) >= abs(dz) else (ax, az + sz))"
PATH_RETURN = """                            % (block, x, z))
    return path"""
SOUND = [g for g in GATES if g[0] not in DIAGONAL]


# Without this the walkway test could be one that always fails, for reasons of its own, and would prove
# nothing when the fix lands. Swapping cmd_build's perpendicular -- the GENERATOR, with the data untouched --
# makes the two gatehouses that are sound today wall over their own walkway, and the fill says so by name.
def test_dropping_the_corner_join_reopens_the_defect_b12_fixed():
    bent = [g for g in GATES if g[0] in DIAGONAL]
    assert len(bent) == 5, "the diagonal gates changed: %s" % DIAGONAL
    for g in GATES:
        assert walkway_problems(g, emitted(g[0])) == [], "%s does not pass today: nothing to mutate" % g[0]
    texts = build_pack(ground=_fake_ground, module=mutant(
        CORNER_JOIN, "            pass"), report=_quiet_report)
    for g in bent:
        assert walkway_problems(g, texts[g[0]]), (
            "%s: without the corner-joining column the walkway steps diagonally and a player cannot walk it, "
            "yet the fill called it sound; the fill is not measuring the generator's geometry" % g[0])
    for g in SOUND:
        assert walkway_problems(g, texts[g[0]]) == [], (
            "%s is axis-aligned and has no diagonal step, so this mutation must not touch it" % g[0])


# Without this the barrier test could be passing because the walkway is narrow rather than because the barrier
# closes it. Widening the shell by one column each side -- again the GENERATOR, not the data -- leaves a
# walkway three wide, where a player walks straight round the barrier; the barrier check must catch that, and
# the connectivity check must NOT, because a three-wide walkway is still connected. This pins which is which.
def test_widening_the_shell_in_cmd_build_lets_a_player_walk_round_the_barrier():
    texts = build_pack(ground=_fake_ground, module=mutant(
        PATH_RETURN, """                            % (block, x, z))
    return path + [(x + 1, z) for (x, z) in path] + [(x, z + 1) for (x, z) in path]"""), report=_quiet_report)
    for g in SOUND:
        assert barrier_problems(g, texts[g[0]]), (
            "%s: a three-wide walkway still reads as closed by its barrier" % g[0])
        assert walkway_problems(g, texts[g[0]]) == [], (
            "%s: a three-wide walkway is wrong, but it is still one connected piece; the connectivity check "
            "must not be the thing that rejects it" % g[0])


# ------------------------------------------------------------------ with the heightmap

def _source_root():
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT is not set: the heightmap is outside the repo")
    return root


# Without it every test above is about a build the real tool never makes. This is what licenses _fake_ground:
# if a gatehouse ever starts reading the heightmap, the two builds diverge and the fast tests stop being true.
@pytest.mark.slow
def test_the_gatehouses_do_not_depend_on_the_heightmap_stub():
    _source_root()
    real = build_pack()
    assert sorted(real) == sorted(NAMES)
    for name, text in real.items():
        assert text == emitted(name), "%s: the real build and the stubbed build differ" % name


# Without it a guard's ground_y is whatever was typed and its shell floats or buries: the ground a placement
# stands on comes from tools/ground.py, rounded, and never from a world (CLAUDE.md).
@pytest.mark.slow
@pytest.mark.parametrize("gate", GATES, ids=NAMES)
def test_every_guards_ground_is_the_heightmaps_ground(gate):
    import ground as GD
    g = GD.load(_source_root())
    q = gate[2]["block"]
    assert gate[2]["ground_y"] == g(q[0], q[1]), (
        "%s: ground_y %d, heightmap y%d at %s" % (gate[0], gate[2]["ground_y"], g(q[0], q[1]), q))


# Without it the arrival, turn-back and exit box drift off the ground they were surveyed on, and a player is
# teleported into rock or one block above the floor.
@pytest.mark.slow
@pytest.mark.parametrize("gate", GATES, ids=NAMES)
def test_every_gates_places_stand_one_block_above_the_heightmap(gate):
    import ground as GD
    g = GD.load(_source_root())
    arrive, tb, ebox = gate[3], gate[4], gate[5]
    for what, (x, y, z) in (("arrival", (arrive[0] - 0.5, arrive[1], arrive[2] - 0.5)),
                            ("turn-back", (tb[0] - 0.5, tb[1], tb[2] - 0.5)),
                            ("exit box", (ebox[0], ebox[1], ebox[2]))):
        assert int(y) == g(int(x), int(z)) + 1, (
            "%s: the %s is at y%s, the heightmap's ground at (%d, %d) is y%d"
            % (gate[0], what, y, int(x), int(z), g(int(x), int(z))))
