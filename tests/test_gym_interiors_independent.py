"""Independent tests of the gym interiors, written by an agent that did not build them.

NARROWED 2026-09-29, and by a different agent again. The owner's redesign (docs/world-building/GYM_BUILDINGS_BRIEF.md)
replaced the works under gyms 1, 3, 4, 5 and 7 with authored buildings; those records are `built: false` and
tools/gym_interiors.py no longer emits them. **Misty's gym 2 is still built and keeps its coverage here** - the suite
now parametrises on tools/gym_interiors_independent.GYM_NUMBERS, which reads the `built` flags, so nothing is asserted
about content that no longer exists and nothing silently stops being checked when a gym comes back.

The mutations that could only be made against a demolished interior (Blaine's pool, Brock's masons' ladder, the rim
wall, the geyser's soul sand, Erika's drain, two interiors colliding) were NOT deleted: every one of them is carried
across to tests/test_gym_buildings_independent.py against tools/gym_buildings_independent.py, which audits what
replaced them. The synthetic model tests below are unchanged and are the shared physics both audits rest on.

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

GYMS = A.GYM_NUMBERS

# (gym, code) -> the finding. Each is a defect in the built content, seen by this audit and confirmed by hand; see
# docs/world-building/GYM_INTERIORS_REVIEW.md. Delete an entry when the content is fixed (the test tells you to).
# The entries for gyms 1, 3, 4, 5 and 7 went with those interiors when they were demolished.
KNOWN_DEFECTS = {
    (2, "lantern"): "F6 lanterns hang one block below the ceiling or stand a block above the floor, in the air",
}


def test_the_suite_audits_every_interior_that_is_still_built():
    # breaks if: an interior comes back (or the last one goes) and the parametrised tests silently stop covering it
    built = {g["id"] for g in json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))["gyms"]
             if g.get("built")}
    assert {"gym%d" % n for n in GYMS} == built and built, built


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
    from terrain import TerrainUnavailable
    try:
        return G.load()
    except TerrainUnavailable as e:
        # See the same fixture in test_gym_buildings_independent.py: the one error that means "no heightmap
        # on this machine". It was `except BaseException`, which hid every other fault behind a skip.
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


@pytest.mark.parametrize("gym", GYMS)
def test_a_shaft_that_stops_a_block_short_of_the_hall_floor_is_caught(emitted, design, placements, ground, baseline, gym):
    # breaks if: the way into the works ends where a player cannot step off it
    texts, _, _ = emitted
    site = baseline[1][gym]
    top, stand = baseline[2][gym].hall_col, site.hall_stand
    assert top is not None, "gym%d has no column into the shell to move" % gym
    needle, lower = " %d %d %d " % (top[0], stand, top[1]), " %d %d %d " % (top[0], stand - 1, top[1])
    t = texts[gym]
    assert needle in t, "gym%d's shaft top %s is not written literally; this mutation cannot be made" % (gym, needle)
    after = run_only(gym, t.replace(needle, lower), emitted, design, placements, ground)
    assert "shell_column" in after.codes(gym)


@pytest.mark.parametrize("gym", GYMS)
def test_a_data_file_naming_a_gyms_columns_is_caught(baseline, gym):
    # breaks if: the search of the other data files matches nothing, so a scene or portal on a dig is invisible
    rep, sites, worlds, extras = baseline
    cells = worlds[gym].cells
    xs, ys, zs = [c[0] for c in cells], [c[1] for c in cells], [c[2] for c in cells]
    box = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))
    boxes = {gym: box}
    mid = {"x": (box[0] + box[3]) // 2, "y": (box[1] + box[4]) // 2, "z": (box[2] + box[5]) // 2}
    hit = A.scan_claims({"scenes": [dict(id="s", at=mid)]}, boxes)
    assert hit and hit[0][0] == gym
    far = dict(mid, y=400)
    assert not A.scan_claims({"scenes": [{"at": far}]}, boxes), "a point far above the dig is not a claim on it"
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
