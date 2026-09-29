"""Independent tests of the gym interiors, written by an agent that did not build them.

The incumbent's tests (tests/test_gym_interiors.py) and audit (tools/gym_interiors_audit.py) were written by the agent
that wrote tools/gym_interiors.py, and they take their expectations from data/gym_interiors.json, which is what the
generator read: they show the generator ran. These tests hold the emitted functions against things the generator does
not write: the gym's real lot and shell in data/placements.json, the ground in tools/ground.py (the heightmap, never
a world), the spawn-free zones, the block physics in tools/gym_interiors_independent.py (a movement model checked here
against hand-computed cases), and the design's own route.

Four kinds of test:

  the model      tiny synthetic worlds whose answer is worked out by hand (fall damage, jump reach, one-high holes,
                 bubble columns, water spread, shell boxes). A model that is wrong here is wrong everywhere.
  the content    the six real interiors, one property at a time. A property the content fails is listed in
                 KNOWN_DEFECTS with the finding (docs/world-building/GYM_INTERIORS_REVIEW.md) and the test xfails; when
                 the content is fixed the test FAILS until the entry is deleted, so a fix cannot go unnoticed and a
                 new defect cannot hide behind an old one.
  mutations      a copy of the emitted output is broken on purpose (moved 8 blocks, water deleted, a wall opened) and
                 the audit must say so. An audit that passes a mutated input is not an audit.
  the command    the CLI prints one verdict line and only problems.

NOT COVERED, by any of it: whether the blocks behave as modelled in a running game. Validity is not behaviour
(.claude/rules/testing.md). The movement model is a model: jump reach, swimming entry into a one-high hole, bubble
columns, fall damage into shallow water and the trainers' sight are rules from the game, not measurements of it. Each
needs a functional test in Minecraft (an experiment, not pytest). The trainers are not placed yet, so the guard checks
use the design's seats and a sight disc, not RCT's real trigger.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import gym_interiors_independent as A  # noqa: E402

GYMS = (1, 2, 3, 4, 5, 7)

# (gym, code) -> the finding. Each is a defect in the built content, seen by this audit and confirmed by hand; see
# docs/world-building/GYM_INTERIORS_REVIEW.md. Delete an entry when the content is fixed (the test tells you to).
KNOWN_DEFECTS = {
    (1, "step"): "F1 the chute back (c3_return) is one block too low: the cutting room's ceiling is y135, the chute floor's standing level is y135, so the head cell at x1824 y136 is rock and nobody can walk off it onto the straw",
    (1, "guard"): "F2 the dead-end walkway is a two-block sprint jump from the low ledge, so the pit, the yard hand, the ramp and the east ladders can be skipped",
    (4, "waypoint"): "F3 the drain cannot be entered: it is a one-high flooded hole entered from a dry mouth",
    (4, "crawl"): "F3 the drain cannot be entered: it is a one-high flooded hole entered from a dry mouth",
    (4, "leaves"): "F7 the azalea hedge is unpersistent leaves with no log near: it decays away, and it is the wall the first gardener guards",
    (4, "leak"): "F4 the cistern store and the drain's outfall are open-topped sources that spread across the floor",
    (7, "leak"): "F4 the geyser's two lowest water cells spread across the rack room floor",
    (5, "guard"): "F5 the false causeway stubs sit one block from the true one, so they can be hopped and the second tracker skipped",
    (2, "lantern"): "F6 lanterns hang one block below the ceiling or stand a block above the floor, in the air",
    (3, "lantern"): "F6 lanterns hang one block below the ceiling or stand a block above the floor, in the air",
    (4, "lantern"): "F6 lanterns hang one block below the ceiling or stand a block above the floor, in the air",
    (5, "lantern"): "F6 lanterns hang one block below the ceiling or stand a block above the floor, in the air",
    (7, "lantern"): "F6 lanterns hang one block below the ceiling or stand a block above the floor, in the air",
}


# ---------------------------------------------------------------------------------------------------- the fixtures
@pytest.fixture(scope="module")
def design():
    return json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def placements():
    return json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    try:
        return G.load()
    except BaseException as e:      # no heightmap on this machine: the site checks cannot run, and saying so is honest
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])


@pytest.fixture(scope="module")
def emitted(tmp_path_factory):
    """The functions tools/gym_interiors.py writes today, built into a scratch pack."""
    import gym_interiors as GI
    base = tmp_path_factory.mktemp("gym_interiors_pack")
    funcs = base / "data" / "cobblers" / "function" / "gym_interiors"
    mp = pytest.MonkeyPatch()
    mp.setattr(GI, "PACK", base)
    mp.setattr(GI, "FUNCS", funcs)
    mp.setattr(GI, "REPORT", base / "derived")
    try:
        GI.build(argparse.Namespace(out=None, source_root=None))
    finally:
        mp.undo()
    texts, healers = A.load_texts(funcs)
    return texts, healers, funcs


@pytest.fixture(scope="module")
def baseline(emitted, design, placements, ground):
    texts, healers, _ = emitted
    return A.run(texts, healers, design, placements, ground)


def run_only(n, text, emitted, design, placements, ground):
    texts, healers, _ = emitted
    t = dict(texts)
    t[n] = text
    rep, sites, worlds, extras = A.run(t, "", design, placements, ground, only={n})
    return rep


# --------------------------------------------------------------------------------------------- mutation helpers
COORD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)( (-?\d+) (-?\d+) (-?\d+))?( .*)$")


def shifted(text, dx=0, dy=0, dz=0):
    """The same commands, moved. Comments and forceloads are left alone."""
    out = []
    for line in text.splitlines():
        m = COORD.match(line)
        if not m:
            out.append(line)
            continue
        cmd = m.group(1)
        a = (int(m.group(2)) + dx, int(m.group(3)) + dy, int(m.group(4)) + dz)
        if m.group(5):
            b = (int(m.group(6)) + dx, int(m.group(7)) + dy, int(m.group(8)) + dz)
            out.append("%s %d %d %d %d %d %d%s" % (cmd, *a, *b, m.group(9)))
        else:
            out.append("%s %d %d %d%s" % (cmd, *a, m.group(9)))
    return "\n".join(out) + "\n"


def fills(text, needle):
    """Indexes of the fill lines whose block matches."""
    return [i for i, l in enumerate(text.splitlines()) if l.startswith("fill ") and needle in l]


def volume(line):
    v = [int(x) for x in line.split()[1:7]]
    return (abs(v[3] - v[0]) + 1) * (abs(v[4] - v[1]) + 1) * (abs(v[5] - v[2]) + 1)


def without(text, index):
    lines = text.splitlines()
    del lines[index]
    return "\n".join(lines) + "\n"


def replaced(text, index, new):
    lines = text.splitlines()
    lines[index] = new
    return "\n".join(lines) + "\n"


def appended(text, *lines):
    return text.rstrip("\n") + "\n" + "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- the content, one property at a time
def assert_clean(rep, gym, codes, what):
    """No problem of these codes for this gym, except the ones KNOWN_DEFECTS records (which xfail; fixed ones fail)."""
    present = {c for g, c, _ in rep.items if g == gym and c in codes}
    known = {c for (g, c) in KNOWN_DEFECTS if g == gym and c in codes}
    stale = known - present
    assert not stale, "gym%d no longer has %s: delete it from KNOWN_DEFECTS (%s)" % (gym, sorted(stale), what)
    fresh = present - known
    if fresh:
        detail = [t for g, c, t in rep.items if g == gym and c in fresh]
        pytest.fail("gym%d %s:\n  %s" % (gym, what, "\n  ".join(d[:400] for d in detail)))
    if present:
        pytest.xfail("; ".join(sorted({KNOWN_DEFECTS[(gym, c)] for c in present})))


@pytest.mark.parametrize("gym", GYMS)
def test_every_carve_stays_inside_the_gyms_own_lot_and_under_the_ground(baseline, gym):
    # breaks if: an interior is fitted to the wrong place and digs under a neighbour, a street or open sky
    assert_clean(baseline[0], gym, {"lot", "above_ground", "cover", "breach", "town"}, "site")


@pytest.mark.parametrize("gym", GYMS)
def test_the_hall_is_opened_by_exactly_one_column_ending_at_the_hall_floor(baseline, gym):
    # breaks if: the works open the hall in several places or the shaft ends below or above the standing level
    assert_clean(baseline[0], gym, {"shell_column", "shaft_top"}, "shell column")


@pytest.mark.parametrize("gym", GYMS)
def test_the_dig_lies_inside_its_spawn_free_zone(baseline, gym):
    # breaks if: a wild spawn can appear inside a gym's carved rooms (data/spawn_suppression.json)
    assert_clean(baseline[0], gym, {"spawn"}, "spawn zone")


@pytest.mark.parametrize("gym", GYMS)
def test_no_other_data_file_claims_the_columns_a_gym_digs(baseline, gym):
    # breaks if: a route, portal, scene or landmark is authored on top of a gym's works
    assert_clean(baseline[0], gym, {"gym_cells", "lot_lot", "data_claim"}, "overlap")


def test_every_placed_gym_shell_is_covered_by_the_healer_removal(baseline):
    # breaks if: a healing machine survives in a gym (the owner's 2026-09-29 call), for any of the eight
    assert "healer" not in baseline[0].codes()


@pytest.mark.parametrize("gym", GYMS)
def test_the_designed_route_can_be_walked_swum_and_climbed(baseline, gym):
    # breaks if: a waypoint the design promises is not a legal position, is unreachable, or a step between two is impossible
    assert_clean(baseline[0], gym, {"waypoint", "step", "crawl"}, "route")


@pytest.mark.parametrize("gym", GYMS)
def test_nobody_can_be_trapped_or_killed_by_a_fall(baseline, gym):
    # breaks if: a reachable position has no way back to the hall, or a fall costs more than the route may
    assert_clean(baseline[0], gym, {"trap", "fatal", "harsh", "landing"}, "traps and falls")


@pytest.mark.parametrize("gym", GYMS)
def test_no_room_can_be_skipped_and_no_guard_walked_round(baseline, gym):
    # breaks if: a wall between rooms is missing, or a guard's post can be bypassed by a jump or a decoy
    assert_clean(baseline[0], gym, {"room_join", "skip_room", "guard"}, "shortcuts")


@pytest.mark.parametrize("gym", GYMS)
def test_no_water_leaks_and_no_one_can_drown(baseline, gym):
    # breaks if: a source spreads out of its box, a submerged pocket has no way to air, or a breath cannot cover a swim
    assert_clean(baseline[0], gym, {"leak", "drown_trap", "drown"}, "water")


@pytest.mark.parametrize("gym", GYMS)
def test_ladders_have_walls_scaffolding_has_a_floor_and_lanterns_have_something_to_hold(baseline, gym):
    # breaks if: a block placed by /fill would fall or break on its first neighbour update
    assert_clean(baseline[0], gym, {"ladder", "scaffold", "lantern", "leaves", "palette"}, "supported blocks")


def test_every_problem_the_audit_raises_has_a_code(baseline):
    # breaks if: a new message is added to the audit without its code, so no test can ask for it
    assert "unknown" not in baseline[0].codes()


def test_blaines_leap_lands_in_six_blocks_of_water_and_costs_nothing(baseline):
    # breaks if: the pool under the open throat is shallower than the fall needs (the incumbent's own worry, checked independently)
    rep, sites, worlds, extras = baseline
    mv, adj, start = extras[7]
    landings = [(k, v) for k, v in mv.lands.items() if v[2] >= 17]
    assert landings, "no 17-block-or-longer fall was found in gym 7: the leap is not in the emitted blocks"
    w = worlds[7]
    for (a, b), (kind, depth, dist) in landings:
        assert kind == "water" and depth == 6, (a, b, kind, depth, dist)
        assert w.supports((b[0], 72, b[2])) and all(w.water((b[0], y, b[2])) for y in range(73, 79)), "the pool under %s is not six of water on a floor" % (b,)


def test_the_geyser_cannot_be_swum_down_so_the_leap_cannot_be_skipped(baseline):
    # breaks if: the rack room can be reached from the rim without the leap into the pool (the shortcut the incumbent found)
    rep, sites, worlds, extras = baseline
    mv, adj, start = extras[7]
    rack = (6175, 86, 5003)
    assert rack in adj
    # every route from the hall to the rack room passes through the pool
    seen, frontier = {start}, [start]
    pool = lambda c: 6165 <= c[0] <= 6170 and 73 <= c[1] <= 78 and 4999 <= c[2] <= 5003
    while frontier:
        c = frontier.pop()
        for d, how in adj[c]:
            if d not in seen and not pool(d):
                seen.add(d)
                frontier.append(d)
    assert rack not in seen


# ---------------------------------------------------------------------------------------------------- mutations
@pytest.mark.parametrize("gym", GYMS)
@pytest.mark.parametrize("axis", ("x", "z"))
def test_an_interior_moved_eight_blocks_is_caught(emitted, design, placements, ground, gym, axis):
    # breaks if: the audit compares with the artifact instead of the site, so a moved interior still passes
    texts, _, _ = emitted
    before = run_only(gym, texts[gym], emitted, design, placements, ground)
    moved = shifted(texts[gym], dx=8 if axis == "x" else 0, dz=8 if axis == "z" else 0)
    after = run_only(gym, moved, emitted, design, placements, ground)
    new = after.codes(gym) - before.codes(gym)
    assert new & {"lot", "shell_column", "cover", "breach", "spawn", "shaft_top", "above_ground", "town"}, (gym, axis, sorted(new))


@pytest.mark.parametrize("gym", GYMS)
def test_an_interior_raised_twelve_blocks_breaks_the_surface_and_is_caught(emitted, design, placements, ground, gym):
    # breaks if: cover is not measured against the heightmap
    texts, _, _ = emitted
    before = run_only(gym, texts[gym], emitted, design, placements, ground)
    after = run_only(gym, shifted(texts[gym], dy=12), emitted, design, placements, ground)
    assert (after.codes(gym) - before.codes(gym)) & {"cover", "breach", "above_ground", "shell_column", "shaft_top"}


def test_deleting_the_water_at_blaines_landing_is_caught(emitted, design, placements, ground):
    # breaks if: an eighteen-block fall can land on stone without the audit noticing
    texts, _, _ = emitted
    t = texts[7]
    water = [i for i in fills(t, "minecraft:water")]
    pool = max(water, key=lambda i: volume(t.splitlines()[i]))
    assert "6165 73 4999 6170 78 5003" in t.splitlines()[pool]
    before = run_only(7, t, emitted, design, placements, ground)
    after = run_only(7, without(t, pool), emitted, design, placements, ground)
    new = after.codes(7) - before.codes(7)
    # the pool was never carved: without the water fill the throat ends on rock at y78, so the fall is feet y96 to y79, 17 blocks
    assert "harsh" in new, sorted(after.codes(7))
    assert any("14" in text for g, c, text in after.items if c == "harsh"), "seventeen blocks onto stone cost fourteen"


def test_making_blaines_pool_one_block_deep_is_caught(emitted, design, placements, ground):
    # breaks if: shallow water under a long fall is accepted
    texts, _, _ = emitted
    t = texts[7]
    pool = max(fills(t, "minecraft:water"), key=lambda i: volume(t.splitlines()[i]))
    line = t.splitlines()[pool].split()
    line[2] = "78"     # y0 73 -> 78: one deep
    after = run_only(7, replaced(t, pool, " ".join(line)), emitted, design, placements, ground)
    assert "landing" in after.codes(7) or "harsh" in after.codes(7)


def test_opening_a_wall_between_the_cutting_floor_and_the_pit_is_caught(emitted, design, placements, ground):
    # breaks if: a room joined to another by a hole the design does not have goes unnoticed
    texts, _, _ = emitted
    before = run_only(1, texts[1], emitted, design, placements, ground)
    after = run_only(1, appended(texts[1], "fill 1815 131 3690 1816 133 3691 minecraft:air"), emitted, design, placements, ground)
    assert "room_join" in after.codes(1) and "room_join" not in before.codes(1)
    assert "skip_room" in after.codes(1)


def test_opening_a_wall_between_the_rim_and_the_galleries_is_caught(emitted, design, placements, ground):
    # breaks if: a drop from the rim gallery straight to the sample landing is not seen as a skipped puzzle
    texts, _, _ = emitted
    before = run_only(7, texts[7], emitted, design, placements, ground)
    # a shaft from the rim chamber's floor down onto the landing, beside the pool, through rock
    cut = "fill 6172 79 4997 6172 95 4997 minecraft:air"
    after = run_only(7, appended(texts[7], cut), emitted, design, placements, ground)
    new = after.codes(7) - before.codes(7)
    assert new & {"room_join", "skip_room"}, sorted(after.codes(7))


def test_making_the_geyser_an_ordinary_water_column_is_caught(emitted, design, placements, ground):
    # breaks if: a bubble column is treated as ordinary water, so swimming down it (the incumbent's shortcut) goes unseen
    texts, _, _ = emitted
    t = texts[7]
    idx = [i for i in fills(t, "minecraft:soul_sand")]
    assert len(idx) == 1
    before = run_only(7, t, emitted, design, placements, ground)
    after = run_only(7, replaced(t, idx[0], t.splitlines()[idx[0]].replace("soul_sand", "basalt")), emitted, design, placements, ground)
    new = after.codes(7) - before.codes(7)
    assert new & {"skip_room", "room_join"}, sorted(after.codes(7))


def test_removing_the_masons_ladder_traps_the_pit_and_is_caught(emitted, design, placements, ground):
    # breaks if: a pit with no way out is accepted
    texts, _, _ = emitted
    t = texts[1]
    idx = [i for i in fills(t, "ladder[facing=east]") if t.splitlines()[i].startswith("fill 1814 119 3692")]
    assert len(idx) == 1
    before = run_only(1, t, emitted, design, placements, ground)
    after = run_only(1, without(t, idx[0]), emitted, design, placements, ground)
    assert "trap" in after.codes(1) and "trap" not in before.codes(1)


def test_a_ladder_turned_to_face_the_open_air_is_caught(emitted, design, placements, ground):
    # breaks if: a ladder with nothing behind it (which pops off on its first update) is accepted
    texts, _, _ = emitted
    t = texts[1]
    idx = [i for i in fills(t, "ladder[facing=east]") if t.splitlines()[i].startswith("fill 1814 119 3692")]
    after = run_only(1, replaced(t, idx[0], t.splitlines()[idx[0]].replace("facing=east", "facing=west")), emitted, design, placements, ground)
    assert "ladder" in after.codes(1)


def test_a_shaft_that_stops_a_block_short_of_the_hall_floor_is_caught(emitted, design, placements, ground):
    # breaks if: the way into the works ends where a player cannot step off it
    texts, _, _ = emitted
    t = texts[1]
    assert t.count(" 1817 142 3685 ") == 2      # the healer's cell cleared, and the scaffolding that stands in it
    after = run_only(1, t.replace(" 1817 142 3685 ", " 1817 141 3685 "), emitted, design, placements, ground)
    assert "shell_column" in after.codes(1)


def test_flooding_the_drains_mouth_two_deep_makes_it_enterable(emitted, design, placements, ground):
    # breaks if: the one-high-hole rule is applied to every water cell instead of to holes entered from shallow water (a control)
    texts, _, _ = emitted
    before = run_only(4, texts[4], emitted, design, placements, ground)
    assert "waypoint" in before.codes(4) and "crawl" in before.codes(4)
    after = run_only(4, appended(texts[4], "fill 4310 99 1489 4310 100 1493 minecraft:water"), emitted, design, placements, ground)
    assert "waypoint" not in after.codes(4) and "crawl" not in after.codes(4), [t for g, c, t in after.items if c in ("waypoint", "crawl")]


def test_two_interiors_writing_the_same_cells_is_caught(emitted, design, placements, ground):
    # breaks if: cross-gym collisions are not compared at cell level
    texts, healers, _ = emitted
    t = dict(texts)
    t[2] = texts[1]
    rep, *_ = A.run(t, "", design, placements, ground, only={1, 2})
    assert "gym_cells" in rep.codes()


def test_a_data_file_naming_a_gyms_columns_is_caught(baseline):
    # breaks if: the search of the other data files matches nothing, so a scene or portal on a dig is invisible
    rep, sites, worlds, extras = baseline
    xs = [c[0] for c in worlds[3].cells]
    zs = [c[2] for c in worlds[3].cells]
    ys = [c[1] for c in worlds[3].cells]
    boxes = {3: (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))}
    hit = A.scan_claims({"scenes": [{"id": "s", "at": {"x": 1741, "y": 160, "z": 1410}}]}, boxes)
    assert hit and hit[0][0] == 3
    assert not A.scan_claims({"scenes": [{"at": {"x": 1741, "y": 400, "z": 1410}}]}, boxes), "a point far above the dig is not a claim on it"
    assert not A.scan_claims({"a": [0, 0, 9000, 9000]}, boxes), "a map-sized region is not a claim on one dig"


# ----------------------------------------------------------------------------- the model, in worlds worked by hand
class FakeSite:
    """A site with no shell and no ground: everything unwritten is open sky, so a test writes only what it needs."""
    n = 0
    hall_stand = 10 ** 6
    shell = (10 ** 6, 10 ** 6, 10 ** 6, 10 ** 6, 10 ** 6, 10 ** 6)

    def surface(self, x, z):
        return -1000

    def in_shell(self, x, y, z):
        return False


def world_of(*lines):
    ops, unknown = A.parse("\n".join(lines) + "\n")
    assert not unknown
    return A.World(FakeSite(), ops)


def test_fall_damage_is_distance_less_three_hay_takes_eighty_percent_and_water_takes_all():
    # breaks if: the damage model drifts from the game's (distance - 3, hay x0.2, water 2+ deep 0)
    lanes = []
    for lane, floor in enumerate(("minecraft:stone", "minecraft:hay_block", "water2", "water1")):
        z = 4 * lane
        lanes.append("fill 0 10 %d 0 10 %d minecraft:stone" % (z, z))              # the platform: feet stand at y11
        if floor.startswith("water"):
            lanes.append("fill 1 0 %d 1 0 %d minecraft:stone" % (z, z))
            lanes.append("fill 1 1 %d 1 %d %d minecraft:water" % (z, int(floor[-1]), z))
        else:
            lanes.append("fill 1 0 %d 1 0 %d %s" % (z, z, floor))
    mv = A.Moves(world_of(*lanes))
    land, dmg, kind, depth = mv.fall((0, 11, 0), (1, 11, 0))
    assert (land, kind, dmg) == ((1, 1, 0), "solid", 7.0)                          # feet y11 to y1: ten blocks, ten less three
    land, dmg, kind, depth = mv.fall((0, 11, 4), (1, 11, 4))
    assert kind == "hay" and abs(dmg - 1.4) < 1e-9                                 # the same ten onto hay
    land, dmg, kind, depth = mv.fall((0, 11, 8), (1, 11, 8))
    assert (kind, depth, dmg) == ("water", 2, 0)                                   # two of water negates it
    land, dmg, kind, depth = mv.fall((0, 11, 12), (1, 11, 12))
    assert (kind, depth, dmg) == ("water", 1, 7.0)                                 # one does not: the audit keeps a margin over the game


def test_a_jump_clears_a_gap_of_one_and_a_gap_of_two_only_with_a_run_up_and_never_three():
    # breaks if: jump reach is too generous (hiding real gaps) or too stingy (inventing traps). Rows are 10 apart so they never meet.
    w = world_of("fill 0 0 0 1 0 0 minecraft:stone", "fill 3 0 0 3 0 0 minecraft:stone",            # row 0: gap of one
                 "fill 0 0 10 0 0 10 minecraft:stone", "fill 3 0 10 3 0 10 minecraft:stone",       # row 10: gap of two, no run-up
                 "fill 0 0 20 3 0 20 minecraft:stone", "fill 6 0 20 6 0 20 minecraft:stone",       # row 20: gap of two, run-up
                 "fill 0 0 30 3 0 30 minecraft:stone", "fill 7 0 30 7 0 30 minecraft:stone",       # row 30: gap of three
                 "fill 0 0 40 0 0 40 minecraft:stone", "fill 1 0 40 1 1 40 minecraft:stone",       # row 40: a one-block step
                 "fill 0 0 50 0 0 50 minecraft:stone", "fill 1 0 50 1 2 50 minecraft:stone")       # row 50: a two-block wall
    mv = A.Moves(w)
    to = lambda n: {d for d, _ in mv.edges(n)}
    assert (3, 1, 0) in to((1, 1, 0))
    assert (3, 1, 10) not in to((0, 1, 10))
    assert (6, 1, 20) in to((3, 1, 20))
    assert (7, 1, 30) not in to((3, 1, 30))
    assert (1, 2, 40) in to((0, 1, 40))
    assert (1, 3, 50) not in to((0, 1, 50))


def test_a_one_high_flooded_hole_is_entered_only_from_water_two_deep():
    # breaks if: crawling into a hole from dry land, or from the surface, is allowed (the game refuses both)
    common = ["fill 0 0 0 8 0 2 minecraft:stone",
              "fill 4 1 1 8 1 1 minecraft:water", "fill 4 2 1 8 2 1 minecraft:stone",      # the hole: 1 high, roof over it
              "fill 4 1 0 8 2 0 minecraft:stone", "fill 4 1 2 8 2 2 minecraft:stone"]
    dry = A.Moves(world_of(*common))
    assert (8, 1, 1) not in dry.graph((1, 1, 1))
    assert ((3, 1, 1), (4, 1, 1)) in dry.refused
    shallow = A.Moves(world_of(*common, "fill 3 1 1 3 1 1 minecraft:water"))
    assert (8, 1, 1) not in shallow.graph((1, 1, 1))              # one deep at the mouth: the head is in air
    deep = A.Moves(world_of(*common, "fill 3 1 1 3 2 1 minecraft:water", "fill 3 1 0 3 3 0 minecraft:stone", "fill 3 1 2 3 3 2 minecraft:stone"))
    assert (8, 1, 1) in deep.graph((1, 1, 1))                     # two deep in front of it: swum in


def test_a_bubble_column_carries_up_and_will_not_let_you_down():
    # breaks if: the geyser can be swum down (the shortcut the incumbent found in the model)
    col = ["fill 0 0 0 2 0 2 minecraft:stone", "fill 1 0 1 1 0 1 minecraft:soul_sand", "fill 1 1 1 1 6 1 minecraft:water",
           "fill 0 1 0 0 6 2 minecraft:stone", "fill 2 1 0 2 6 2 minecraft:stone", "fill 1 1 0 1 6 0 minecraft:stone", "fill 1 1 2 1 6 2 minecraft:stone"]
    mv = A.Moves(world_of(*col))
    assert {(1, y, 1) for y in range(1, 7)} == mv.bubble
    assert (1, 5, 1) not in {d for d, _ in mv.edges((1, 6, 1))}          # no way down
    assert (1, 6, 1) in {d for d, _ in mv.edges((1, 5, 1))}              # up is fine
    plain = A.Moves(world_of(*[c.replace("soul_sand", "stone") for c in col]))
    assert (1, 5, 1) in {d for d, _ in plain.edges((1, 6, 1))}           # with stone under it, it is just water


def test_water_beside_air_is_a_leak_and_its_reach_is_seven_blocks_of_floor():
    # breaks if: an unsealed source is missed, or the spread is mis-sized (a source on flat floor wets 2*7*8 = 112 cells)
    rep = A.Report()
    leaky = world_of("fill -12 0 -12 12 0 12 minecraft:stone", "fill -12 1 -12 12 6 12 minecraft:air", "fill 0 1 0 0 1 0 minecraft:water")
    A.check_water(rep, FakeSite(), leaky, None)
    assert "leak" in rep.codes()
    assert len(A.flow_extent(leaky, [(0, 1, 0)])) == 112
    sealed = world_of("fill -3 0 -3 3 0 3 minecraft:stone", "fill -3 1 -3 3 6 3 minecraft:stone", "fill 0 1 0 0 1 0 minecraft:water")
    rep = A.Report()
    A.check_water(rep, FakeSite(), sealed, None)
    assert "leak" not in rep.codes()


def test_a_ladder_needs_a_solid_block_behind_it_and_lanterns_need_something_to_hold():
    # breaks if: the support rules for /fill'd blocks are wrong (ladder[facing=east] leans on the block to its west)
    rep = A.Report()
    ok = world_of("fill 0 0 0 0 5 0 minecraft:stone", "fill 1 1 0 1 4 0 minecraft:ladder[facing=east]", "fill 1 0 0 1 0 0 minecraft:stone",
                  "fill 1 6 0 1 6 0 minecraft:stone", "fill 1 5 0 1 5 0 minecraft:lantern[hanging=true]")
    A.check_water(rep, FakeSite(), ok, None)
    assert not rep.codes(), rep.problems
    bad = world_of("fill 1 1 0 1 4 0 minecraft:ladder[facing=east]", "fill 1 0 0 1 0 0 minecraft:stone", "fill 3 3 3 3 3 3 minecraft:lantern[hanging=true]")
    rep = A.Report()
    A.check_water(rep, FakeSite(), bad, None)
    assert {"ladder", "lantern"} <= rep.codes()
    rep = A.Report()
    A.check_water(rep, FakeSite(), world_of("fill 0 0 0 0 0 0 minecraft:azalea_leaves"), None)
    assert "leaves" in rep.codes()
    rep = A.Report()
    A.check_water(rep, FakeSite(), world_of("fill 0 0 0 0 0 0 minecraft:azalea_leaves[persistent=true]"), None)
    assert "leaves" not in rep.codes()


def test_a_shell_box_follows_the_rotation_of_a_size_about_its_corner():
    # breaks if: the four rotations are mixed up, which moves every check by up to a whole building
    rec = {"position": {"x": 100, "y": 50, "z": 200}, "size": [10, 5, 20]}
    assert A.shell_box(dict(rec, rotation="none")) == (100, 50, 200, 109, 54, 219)
    assert A.shell_box(dict(rec, rotation="180")) == (91, 50, 181, 100, 54, 200)
    assert A.shell_box(dict(rec, rotation="clockwise_90")) == (81, 50, 200, 100, 54, 209)
    assert A.shell_box(dict(rec, rotation="counterclockwise_90")) == (100, 50, 191, 119, 54, 200)


def test_the_shell_formula_agrees_with_the_placement_tools_for_every_placed_gym(placements):
    # breaks if: this audit's derivation and tools/place_donor.py drift apart (one of them is then wrong)
    import place_donor
    n = 0
    for r in placements["placements"]:
        if isinstance(r, dict) and r.get("pack_template") and r.get("kind") in ("gym", "donor") and re.match(r"gym[1-8]_", r.get("id", "")):
            (x0, y0, z0), (x1, y1, z1) = place_donor.box(r)
            assert A.shell_box(r) == (x0, y0, z0, x1, y1, z1), r["id"]
            n += 1
    assert n == 8


def test_the_rotation_of_an_offset_agrees_with_the_town_placement_tool():
    # breaks if: the healer cell is worked out differently here and in tools/place_town.py (one of them is then wrong)
    import place_town
    for rot in ("none", "180", "clockwise_90", "counterclockwise_90"):
        for off in ((21, 5), (6, 12), (0, 3), (26, 8)):
            assert A.rotate_offset(off[0], off[1], rot) == tuple(place_town.rotate(off[0], off[1], rot)), (rot, off)
    assert A.rotate_offset(3, 5, "clockwise_90") == (-5, 3)      # by hand: x,z -> -z,x


def test_the_design_route_has_a_one_way_door_on_every_built_gym(design):
    # breaks if: `outbound` finds no turning point, so the skipped-room check silently looks at nothing
    for g in design["gyms"]:
        if g.get("built"):
            out = A.outbound(g)
            assert 3 <= len(out) < len(g["route"]), g["id"]


# ---------------------------------------------------------------------------------------------------- the command
def test_the_command_prints_one_verdict_line_and_only_problems(emitted):
    # breaks if: the audit lists what passed, or exits 0 while it has problems
    _, _, funcs = emitted
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gym_interiors_independent.py"), "--functions", str(funcs)],
                       capture_output=True, text=True, timeout=120)
    lines = r.stdout.strip().splitlines()
    if r.returncode not in (0, 1):
        pytest.skip("the audit could not run here: " + r.stdout[-200:] + r.stderr[-200:])
    assert lines[-1].startswith("gym interiors (independent): ")
    body = lines[:-1]
    assert all(re.match(r"gym\d+ [A-Z]+: ", l) or l.startswith("s HEALER") or l.startswith("gyms") for l in body), body[:3]
    assert (r.returncode == 1) == bool(body)


def test_the_command_refuses_an_empty_functions_folder(tmp_path):
    # breaks if: a missing build is reported as a clean audit
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gym_interiors_independent.py"), "--functions", str(tmp_path)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "run python tools/gym_interiors.py build first" in r.stdout
