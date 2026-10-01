"""Independent tests of the five authored gym buildings, written by an agent that built none of them.

Five agents wrote data/gym_buildings/gym{1,3,4,5,7}.json, one each, and none of them was allowed to write a test
(CLAUDE.md principle 16). tools/gym_buildings.py fail-closes on its own record - the block allow-list, `bounds`,
block support, the spawner, the chest - and every one of those expectations comes out of the record the generator
read, so a clean build proves the generator ran and nothing else. These tests hold the EMITTED command text against
things the generator does not write:

  the site      data/placements.json: the gym lot rect and its `level` from the town plan, the town's other
                placements, anchors and streets
  the ground    tools/ground.py, rounded - the heightmap, never a world save
  the rules     data/gym_interiors.json `rules`: max_fall 12, max_submerged_run 14
  the zones     data/spawn_suppression.json
  Misty         data/gym_interiors.json gym2, the one interior still built, which nothing may touch
  the physics   the movement model in tools/gym_buildings_independent.py, checked here against synthetic worlds
                whose answer is worked out by hand

Four kinds of test:

  the model      tiny worlds with hand-computed answers: fall damage, the sprint-jump reach table, a run-off into
                 open air, bubble columns, water spread, block support. A model that is wrong here is wrong
                 everywhere, and the reach table is the one number the whole "can this stage be skipped" question
                 turns on.
  the content    the five real buildings, one property at a time. A property the content fails is listed in
                 KNOWN_DEFECTS with the finding (docs/world-building/GYM_BUILDINGS_REVIEW.md) and the test xfails;
                 when the content is fixed the test FAILS until the entry is deleted, so a fix cannot go unnoticed
                 and a new defect cannot hide behind an old one.
  mutations      a copy of the emitted output is broken on purpose - a building moved eight blocks, the water under
                 Blaine's leap deleted, a wall opened into a gated room, a ladder removed, a ladder turned round,
                 the geyser's soul sand swapped for stone, the pool made one deep, two buildings on the same cells -
                 and the audit must say so. An audit that passes a mutated input is not an audit.
  the command    the CLI prints one verdict line and only problems, and refuses an empty folder.

NOT COVERED, by any of it: whether the blocks behave in a running game as they are modelled here. Validity is not
behaviour (.claude/rules/testing.md). The sprint-jump reach table, the lift of a soul-sand bubble column, fall
damage in shallow water, whether a lantern really pops and whether an rctmod:trainer_spawner really spawns its
leader are rules of the game taken from outside, not measurements of it. Each needs a functional test inside
Minecraft - an experiment recorded in experiments/, not pytest. Nor does anything here say the buildings look
right, or that the demolition in tools/gym_demolish.py really clears what they stand on.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import gym_buildings_independent as A  # noqa: E402

# Every record that exists on disk, not a list written down here. A hardcoded five is how gyms 6 and 8 went
# unaudited for a day: tools/gym_buildings_independent.py has always globbed the folder, so the audit covered
# them while these tests did not look, and the one test that compares the two is what caught it.
GYMS = tuple(sorted(A.load_records(ROOT)))

# (gym, code) -> the finding. Each is a defect in the built content, seen by this audit and confirmed by hand
# against the emitted text; see docs/world-building/GYM_BUILDINGS_REVIEW.md. Delete an entry when the content is
# fixed - the test tells you to.
KNOWN_DEFECTS = {
    # Empty on 2026-09-29: every entry D1-D8 was fixed by the integrating session and the tests said so,
    # one failure per repair, which is what this table is for. What was fixed, in the records under
    # data/gym_buildings/ and not in this audit: Brock's and Koga's ladder courses re-cut as ladder and
    # not as air (the same defect twice, written by two builders independently); Brock's decoy hop
    # declared; Erika's and Brock's and Koga's and Blaine's waypoints moved off block cells onto the
    # cells a player stands in; a landing bale at the foot of Koga's reed stair and his top course
    # narrowed to one bundle so the drying loft cannot be hopped past; the west gap opened in Blaine's
    # deck rail; Blaine's crating floor widened one west; and a drowned adit under Blaine's casing, which
    # is the only way a sealed bubble column can be entered at all. The two spawn-box breaches were fixed
    # earlier the same day in data/spawn_suppression.json.
    #
    # Add an entry here when THIS audit sees a defect that is not going to be fixed at once; never to
    # silence one that is.
}


MUTABLE = ("fill", "setblock")
COORD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)( (-?\d+) (-?\d+) (-?\d+))?( .*)$")


# ---------------------------------------------------------------------------------------------------- the fixtures
@pytest.fixture(scope="module")
def records():
    return A.load_records(ROOT)


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
        # The one error that means "this machine has no heightmap", raised by terrain.load for a missing
        # COBBLERS_SOURCE_ROOT and for a root that does not hold the image. This was `except BaseException`,
        # which also caught KeyboardInterrupt and SystemExit and would have turned any bug inside
        # ground.load() into a silent skip of every site check. The heightmap IS present here, so the skip
        # was never why these passed -- test_no_swallowed_crashes named this line and was right.
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])


@pytest.fixture(scope="module")
def emitted(tmp_path_factory, records):
    """The functions tools/gym_buildings.py writes today, built into a scratch pack."""
    import gym_buildings as GB
    base = tmp_path_factory.mktemp("gym_buildings_pack")
    funcs = base / "data" / "cobblers" / "function" / "gym_buildings"
    mp = pytest.MonkeyPatch()
    mp.setattr(GB, "PACK", base)
    mp.setattr(GB, "FUNCS", funcs)
    mp.setattr(GB, "REPORT", base / "derived")
    try:
        GB.main(["build"])
    finally:
        mp.undo()
    return A.load_texts(funcs, sorted(records)), funcs


@pytest.fixture(scope="module")
def baseline(emitted, records, placements, ground):
    texts, _ = emitted
    return A.run(texts, records, placements, ground)


def run_one(gid, text, emitted, records, placements, ground):
    texts, _ = emitted
    t = dict(texts)
    t[gid] = text
    rep, _s, _w, _e = A.run(t, records, placements, ground, only={gid})
    return rep


# --------------------------------------------------------------------------------------------- mutation helpers
def shifted(text, dx=0, dy=0, dz=0):
    """The same commands, moved. Comments and forceloads are left alone."""
    out = []
    for line in text.splitlines():
        m = COORD.match(line)
        if not m:
            out.append(line)
            continue
        a = (int(m.group(2)) + dx, int(m.group(3)) + dy, int(m.group(4)) + dz)
        if m.group(5):
            b = (int(m.group(6)) + dx, int(m.group(7)) + dy, int(m.group(8)) + dz)
            out.append("%s %d %d %d %d %d %d%s" % (m.group(1), a[0], a[1], a[2], b[0], b[1], b[2], m.group(9)))
        else:
            out.append("%s %d %d %d%s" % (m.group(1), a[0], a[1], a[2], m.group(9)))
    return "\n".join(out) + "\n"


def line_index(text, needle):
    hits = [i for i, l in enumerate(text.splitlines()) if needle in l]
    assert len(hits) == 1, "expected exactly one line holding %r, found %d" % (needle, len(hits))
    return hits[0]


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


# ----------------------------------------------------------------- the content, one property at a time
def assert_clean(rep, gid, codes, what):
    """No problem of these codes for this gym, except the ones KNOWN_DEFECTS records (which xfail; fixed ones fail)."""
    present = {c for g, c, _ in rep.items if g == gid and c in codes}
    known = {c for (g, c) in KNOWN_DEFECTS if g == gid and c in codes}
    stale = known - present
    assert not stale, "%s no longer has %s: delete it from KNOWN_DEFECTS (%s)" % (gid, sorted(stale), what)
    fresh = present - known
    if fresh:
        detail = [t for g, c, t in rep.items if g == gid and c in fresh]
        pytest.fail("%s %s:\n  %s" % (gid, what, "\n  ".join(d[:400] for d in detail)))
    if present:
        pytest.xfail("; ".join(sorted({KNOWN_DEFECTS[(gid, c)] for c in present})))


@pytest.mark.parametrize("gid", GYMS)
def test_every_building_stands_inside_its_own_gym_lot_on_its_pad(baseline, gid):
    # breaks if: a building is fitted to the wrong place, spills onto a street, or floats over the levelled pad
    assert_clean(baseline[0], gid, {"lot", "float", "breach", "palette", "missing", "unmodelled"}, "site")


@pytest.mark.parametrize("gid", GYMS)
def test_no_building_stands_on_another_placement_an_anchor_or_a_street(baseline, gid):
    # breaks if: the town plan moved under a gym and the building now sits on a neighbour's lot or on the road
    assert_clean(baseline[0], gid, {"town"}, "the town round it")


@pytest.mark.parametrize("gid", GYMS)
def test_every_building_lies_inside_its_spawn_free_box(baseline, gid):
    # breaks if: part of a gym can spawn wild Pokemon, which the spawn-free zones exist to stop
    assert_clean(baseline[0], gid, {"spawn"}, "spawn suppression")


@pytest.mark.parametrize("gid", GYMS)
def test_nothing_else_claims_the_columns_a_building_occupies(baseline, gid):
    # breaks if: a scene, portal, route or landmark is authored inside a gym building, or two gyms collide
    assert_clean(baseline[0], gid, {"gym_cells", "misty", "data_claim"}, "overlap")


@pytest.mark.parametrize("gid", GYMS)
def test_the_leader_can_be_reached_on_foot_from_the_lot(baseline, gid):
    # breaks if: the gym cannot be finished - the badge is unwinnable because the spawner cannot be walked to
    assert_clean(baseline[0], gid, {"unreachable", "chest"}, "the leader")


@pytest.mark.parametrize("gid", GYMS)
def test_the_designed_route_can_be_walked_climbed_and_swum(baseline, gid):
    # breaks if: a step the design promises is not a legal position, is unreachable, or does not lead to the next
    assert_clean(baseline[0], gid, {"waypoint", "step"}, "the route")


@pytest.mark.parametrize("gid", GYMS)
def test_nobody_is_trapped_and_no_fall_costs_more_than_the_rules_allow(baseline, gid):
    # breaks if: a player can be sealed in, killed by a fall, or hurt past data/gym_interiors.json rules.max_fall
    assert_clean(baseline[0], gid, {"trap", "trap_later", "fatal", "harsh", "declared_fall"}, "traps and falls")


@pytest.mark.parametrize("gid", GYMS)
def test_no_stage_can_be_skipped_and_no_gap_can_be_sprint_jumped(baseline, gid):
    # breaks if: a puzzle stage is optional, or a gap meant to gate it is four blocks or less
    assert_clean(baseline[0], gid, {"skip", "gap", "bubble"}, "shortcuts")


@pytest.mark.parametrize("gid", GYMS)
def test_no_fluid_leaks_and_nobody_drowns(baseline, gid):
    # breaks if: a water or lava source spreads out of its box, or a swim is longer than one breath
    assert_clean(baseline[0], gid, {"leak", "lava", "landing", "drown", "drown_trap"}, "water and lava")


@pytest.mark.parametrize("gid", GYMS)
def test_every_block_has_what_holds_it_up(baseline, gid):
    # breaks if: a block /fill placed would pop on its first neighbour update (31 lanterns did, in the works this replaced)
    assert_clean(baseline[0], gid, {"ladder", "lantern", "chain", "falling", "leaves"}, "supported blocks")


def test_the_audit_says_something_about_every_building_that_exists(baseline, records):
    # breaks if: a new data/gym_buildings/*.json is added and the audit silently never looks at it
    assert set(baseline[1]) == set(records) == set(GYMS), (sorted(baseline[1]), sorted(records))


# ------------------------------------------------------------- the data, against sources the generator does not own
def test_every_record_agrees_with_the_town_plan_about_its_lot(records, placements):
    # breaks if: a town plan is re-cut and a gym building is left fitted to a lot that no longer exists
    for gid, rec in records.items():
        site = A.Site(gid, rec["settlement"], placements, lambda x, z: 0)
        assert list(site.lot) == list(rec["site"]["lot_rect"]), gid
        assert site.level == rec["site"]["lot_level"], gid


def test_every_record_stands_on_a_lot_the_prep_really_levels(records, placements):
    # breaks if: a building takes its ground from a `level` the town plan does not declare, so the pad is imaginary
    for gid, rec in records.items():
        site = A.Site(gid, rec["settlement"], placements, lambda x, z: 0)
        assert isinstance(site.level, int), gid
        kind = ((rec["site"].get("ground") or {}).get("kind")) or "lot_level"
        assert kind in ("lot_level", "heightmap"), (gid, kind)


def test_every_building_is_an_interior_that_was_superseded(records):
    # breaks if: a building is written for a gym whose works are still standing, or Misty's gym 2 is touched.
    # Renamed from test_the_five_buildings_...: the count belongs in the data, not in the name of the check,
    # and the old name was the whole reason this went red when gyms 6 and 8 were added.
    #
    # It went red for a real reason and it was right to: data/gym_buildings/ held gym6 and gym8 while
    # data/gym_interiors.json still recorded both as NOT superseded. gym6's why_not was an owner gate --
    # Sabrina's gym not built until EXP-034 has run, being the only per-player puzzle -- and EXP-034 is
    # still unrun. The owner confirmed both buildings on 2026-10-01: the Hall of Lenses carries no
    # per-player state, so the machinery the gate protected against is not in it, and gym8's "as gym2" was
    # stale (Giovanni's was a donor shell, not Misty's carved interior). gym_interiors.json records both
    # decisions. The data was changed to match a decision, never to turn this check green.
    doc = json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))
    superseded = {g["id"] for g in doc["gyms"] if g.get("superseded_by")}
    assert set(records) == superseded, (sorted(records), sorted(superseded))
    assert [g["id"] for g in doc["gyms"] if g.get("built")] == ["gym2"]


def test_exactly_one_spawner_per_building_names_its_own_leader_and_no_healer_is_written(baseline):
    # breaks if: a gym has no leader, two leaders, or a healing machine (the owner removed healers from all eight)
    for gid, world in baseline[2].items():
        spawners = [(c, s) for c, s in world.cells.items() if A.block_name(s) == "rctmod:trainer_spawner"]
        assert len(spawners) == 1, (gid, spawners)
        (x, y, z), state = spawners[0]
        leader = json.loads((ROOT / "data" / "gym_buildings" / ("%s.json" % gid)).read_text(encoding="utf-8"))["leader"]
        assert leader["id"] in state and list(leader["spawner"]) == [x, y, z], (gid, state)
        assert A.block_name(world.state((x, y - 1, z))) == "minecraft:redstone_block", gid
        assert not [c for c, s in world.cells.items() if A.block_name(s) == "cobblemon:healing_machine"], gid


def test_no_building_writes_a_block_from_a_namespace_the_modpack_does_not_carry(baseline):
    # breaks if: a block from a mod that is not installed is written, and /fill silently does nothing
    for gid, world in baseline[2].items():
        got = {A.block_name(s).split(":")[0] for s in world.cells.values()}
        assert got <= A.KNOWN_NAMESPACES, (gid, sorted(got - A.KNOWN_NAMESPACES))


# ---------------------------------------------------------------------------------------------------- mutations
@pytest.mark.parametrize("gid", GYMS)
@pytest.mark.parametrize("axis", ("x", "z"))
def test_a_building_moved_eight_blocks_is_caught(emitted, records, placements, ground, gid, axis):
    # breaks if: the audit compares with the record instead of the site, so a building off its lot still passes
    texts, _ = emitted
    before = run_one(gid, texts[gid], emitted, records, placements, ground)
    moved = shifted(texts[gid], dx=8 if axis == "x" else 0, dz=8 if axis == "z" else 0)
    after = run_one(gid, moved, emitted, records, placements, ground)
    new = after.codes(gid) - before.codes(gid)
    assert new & {"lot", "spawn", "town", "float", "breach"}, (gid, axis, sorted(new))


@pytest.mark.parametrize("gid", GYMS)
def test_a_building_raised_eight_blocks_off_its_pad_is_caught(emitted, records, placements, ground, gid):
    # breaks if: ground is not taken from the town plan's `level`, so a building hanging in the air passes
    texts, _ = emitted
    before = run_one(gid, texts[gid], emitted, records, placements, ground)
    after = run_one(gid, shifted(texts[gid], dy=8), emitted, records, placements, ground)
    assert (after.codes(gid) - before.codes(gid)) & {"float", "lot", "unreachable", "breach"}, sorted(after.codes(gid))


def test_deleting_the_water_under_blaines_leap_is_caught(emitted, records, placements, ground):
    # breaks if: a fourteen-block fall can land on stone without the audit noticing
    texts, _ = emitted
    t = texts["gym7"]
    i = line_index(t, "fill 6167 104 4992 6173 106 4998 minecraft:water")
    before = run_one("gym7", t, emitted, records, placements, ground)
    after = run_one("gym7", without(t, i), emitted, records, placements, ground)
    new = after.codes("gym7") - before.codes("gym7")
    assert new & {"declared_fall", "harsh", "fatal"}, sorted(after.codes("gym7"))


def test_the_depth_of_blaines_basin_is_measured_not_assumed(emitted, records, placements, ground):
    # breaks if: the audit stops measuring how deep the water under a declared fall actually is.
    # This test used to assert that a ONE-deep basin was a finding, on MIN_LANDING_WATER = 2. That margin had no
    # rule behind it - a single water block takes the whole of a fall in vanilla - and it failed every building
    # whose floor is a one-deep flood, Koga's Reed House among them. The margin went on 2026-09-29; what has to
    # stay is that the depth is read out of the blocks and reported, because a landing with NO water is still a
    # finding (test_deleting_the_water_under_blaines_leap_is_caught) and that check needs the same measurement.
    texts, _ = emitted
    t = texts["gym7"]
    i = line_index(t, "fill 6167 104 4992 6173 106 4998 minecraft:water")
    before = run_one("gym7", t, emitted, records, placements, ground)
    assert any("the_leap" in n and "water 3 deep" in n for n in before.notes),         [n for n in before.notes if "the_leap" in n]
    shallow = t.splitlines()[i].replace("6167 104 4992", "6167 106 4992")
    after = run_one("gym7", replaced(t, i, shallow), emitted, records, placements, ground)
    assert any("the_leap" in n and "water 1 deep" in n for n in after.notes),         [n for n in after.notes if "the_leap" in n]


def test_opening_a_wall_into_erikas_court_lets_the_canopy_be_skipped_and_is_caught(emitted, records, placements, ground):
    # breaks if: a hole straight into the leader's room does not register as a skipped stage
    texts, _ = emitted
    t = texts["gym4"]
    before = run_one("gym4", t, emitted, records, placements, ground)
    assert "skip" not in before.codes("gym4")
    # a tunnel at the beds' own level, from the colonnade's floor straight through the court's south wall
    cut = "fill 4308 111 1484 4308 112 1500 minecraft:air"
    after = run_one("gym4", appended(t, cut), emitted, records, placements, ground)
    assert "skip" in after.codes("gym4"), sorted(after.codes("gym4"))


def test_removing_the_ladder_out_of_erikas_court_makes_it_a_trap_and_is_caught(emitted, records, placements, ground):
    # breaks if: a room with no way out is accepted (Erika's court is entered by a nine-block drop)
    texts, _ = emitted
    t = texts["gym4"]
    i = line_index(t, "fill 4303 111 1484 4303 120 1484 minecraft:ladder[facing=north]")
    before = run_one("gym4", t, emitted, records, placements, ground)
    after = run_one("gym4", without(t, i), emitted, records, placements, ground)
    assert "trap" in after.codes("gym4") and "trap" not in before.codes("gym4"), sorted(after.codes("gym4"))


def test_a_ladder_turned_to_face_the_open_air_is_caught(emitted, records, placements, ground):
    # breaks if: a ladder with nothing behind it (which pops off on its first update) is accepted
    texts, _ = emitted
    t = texts["gym4"]
    i = line_index(t, "fill 4303 111 1484 4303 120 1484 minecraft:ladder[facing=north]")
    turned = t.splitlines()[i].replace("facing=north", "facing=south")
    after = run_one("gym4", replaced(t, i, turned), emitted, records, placements, ground)
    assert "ladder" in after.codes("gym4"), sorted(after.codes("gym4"))


def test_the_geyser_is_a_one_way_lift_and_an_ordinary_water_column_would_not_be(emitted, records, placements, ground):
    # breaks if: a bubble column is modelled as ordinary water, so swimming down it into Blaine's vault - the
    # shortcut the record itself asks the audit to rule out - goes unseen
    texts, _ = emitted
    t = texts["gym7"]
    site = A.Site("gym7", records["gym7"]["settlement"], placements, ground)
    # the foot is reached by the drowned adit under the casing (D8's fix), so no mutation is needed to give the
    # column a foot; `opened` below cuts the casing at the vault's own level instead, to prove the leak that is
    # the whole reason the adit goes underneath it
    opened = appended(t, "fill 6178 107 4997 6178 108 4997 minecraft:air")
    head, foot = (6179, 119, 4997), (6179, 104, 4997)

    column = [(6179, y, 4997) for y in range(foot[1], head[1] + 1)]

    def can_swim_down(text):
        """Is there a move from any cell of the shaft to the cell below it, inside the shaft? That, and not
        general reachability, is what 'the column cannot be descended' means."""
        ops, unknown = A.parse(text, "gym7")
        assert not unknown
        world = A.World(site, ops)
        mv = A.Moves(world, A.graph_box(site, world))
        return any((c[0], c[1] - 1, c[2]) in {d for d, _ in mv.edges(c)} for c in column[1:])

    assert not can_swim_down(opened), "the soul-sand column let a player descend into the vault"
    i = line_index(opened, "setblock 6179 103 4997 minecraft:soul_sand")
    plain = replaced(opened, i, opened.splitlines()[i].replace("soul_sand", "polished_blackstone"))
    assert can_swim_down(plain), "with plain water under it the column is not a one-way lift, and the model missed it"
    # and the leak check sees what opening the casing costs: the column is watertight only while it is sealed
    after = run_one("gym7", opened, emitted, records, placements, ground)
    assert "leak" in after.codes("gym7"), sorted(after.codes("gym7"))


def test_two_buildings_writing_the_same_cells_is_caught(emitted, records, placements, ground):
    # breaks if: cross-building collisions are not compared at cell level
    texts, _ = emitted
    t = dict(texts)
    t["gym3"] = texts["gym1"]
    rep, _s, _w, _e = A.run(t, records, placements, ground, only={"gym1", "gym3"})
    assert "gym_cells" in rep.codes() or "lot" in rep.codes("gym3")


def test_a_building_written_into_mistys_dig_is_caught(emitted, records, placements, ground):
    # breaks if: the one interior still built can be overwritten by a new gym building without anybody noticing
    texts, _ = emitted
    misty = json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))["gyms"]
    dig = [g for g in misty if g["id"] == "gym2"][0]["dig"]
    t = dict(texts)
    t["gym1"] = appended(texts["gym1"], "fill %d %d %d %d %d %d minecraft:stone"
                         % (dig[0], dig[1], dig[2], dig[0] + 1, dig[1] + 1, dig[2] + 1))
    rep, _s, _w, _e = A.run(t, records, placements, ground, only={"gym1"})
    assert "misty" in rep.codes("gym1"), sorted(rep.codes("gym1"))


def test_a_data_file_naming_a_buildings_columns_is_caught(baseline):
    # breaks if: the scan of the other data files matches nothing, so a scene or portal inside a gym is invisible
    world = baseline[2]["gym1"]
    box = world.extent
    boxes = {"gym1": box}
    mid = {"x": (box[0] + box[3]) // 2, "y": (box[1] + box[4]) // 2, "z": (box[2] + box[5]) // 2}
    hit = A.scan_claims({"scenes": [dict(id="s", at=mid)]}, boxes)
    assert hit and hit[0][0] == "gym1"
    assert not A.scan_claims({"scenes": [{"at": dict(mid, y=400)}]}, boxes), "a point far above is not a claim"
    assert not A.scan_claims({"a": [0, 0, 9000, 9000]}, boxes), "a map-sized region is not a claim on one gym"


# ----------------------------------------------------------------------------- the model, in worlds worked by hand
class FakeSite:
    """A site with no lot and no pad: everything unwritten is open sky, so a test writes only what it needs."""
    id = "fake"
    lot = (-10 ** 6, -10 ** 6, 10 ** 6, 10 ** 6)
    level = -1000

    def in_lot(self, x, z):
        return True

    def surface(self, x, z):
        return -1000


def world_of(*lines):
    ops, unknown = A.parse("\n".join(lines) + "\n")
    assert not unknown, unknown
    return A.World(FakeSite(), ops)


def test_fall_damage_is_distance_less_three_hay_takes_eighty_percent_and_water_takes_all():
    # breaks if: the damage model drifts from the game's (distance - 3, hay x0.2, any depth of water 0)
    lanes = []
    for lane, floor in enumerate(("minecraft:stone", "minecraft:hay_block", "water2", "water1")):
        z = 4 * lane
        lanes.append("fill 0 10 %d 0 10 %d minecraft:stone" % (z, z))      # the platform: feet stand at y11
        if floor.startswith("water"):
            lanes.append("fill 1 0 %d 1 0 %d minecraft:stone" % (z, z))
            lanes.append("fill 1 1 %d 1 %d %d minecraft:water" % (z, int(floor[-1]), z))
        else:
            lanes.append("fill 1 0 %d 1 0 %d %s" % (z, z, floor))
    mv = A.Moves(world_of(*lanes))
    assert mv.fall((0, 11, 0), (1, 11, 0)) == ((1, 1, 0), 7.0, "solid", 0)     # feet y11 to y1: ten, less three
    land, dmg, kind, _d = mv.fall((0, 11, 4), (1, 11, 4))
    assert kind == "hay" and abs(dmg - 1.4) < 1e-9                              # the same ten onto hay
    assert mv.fall((0, 11, 8), (1, 11, 8))[1:] == (0, "water", 2)               # two of water negates it
    assert mv.fall((0, 11, 12), (1, 11, 12))[1:] == (0, "water", 1)             # and so does ONE: the game's rule,
    # not a margin. This line read (7.0, "water", 1) until 2026-09-29, on MIN_LANDING_WATER = 2. In vanilla a
    # single water block takes the whole of a fall of any height - the water-bucket save rests on it - and the
    # margin failed every building whose floor is a one-deep flood. It is the audit's one unverified rule of the
    # game: the in-game check is a seven-block fall into one block of water.


def test_a_sprint_jump_clears_four_blocks_level_five_down_one_three_up_one_and_never_more():
    # breaks if: jump reach drifts. This is the number the whole "can a stage be skipped" question turns on:
    # docs/world-building/GYM_BUILDINGS.md binds every building to "no gap of four blocks or less".
    def row(z, gap, dy, run_up=4):
        # a take-off strip `run_up` long ending at x0, then `gap` empty columns, then the landing block
        # the take-off floor is y0 (feet y1); the landing floor for a rise of `dy` is y(dy) (feet y(1+dy))
        return ["fill %d 0 %d 0 0 %d minecraft:stone" % (-run_up, z, z),
                "fill %d %d %d %d %d %d minecraft:stone" % (gap + 1, dy, z, gap + 1, dy, z)]

    cases = {  # (gap, dy) -> can a player cross it
        (1, 0): True, (4, 0): True, (5, 0): False,
        (5, -1): True, (6, -1): False,
        (3, 1): True, (4, 1): False,
    }
    lines = []
    for i, (gap, dy) in enumerate(sorted(cases)):
        lines += row(i * 20, gap, dy)
    w = world_of(*lines)
    mv = A.Moves(w)
    for i, (gap, dy) in enumerate(sorted(cases)):
        z = i * 20
        dests = {d for d, _ in mv.edges((0, 1, z))}
        got = (gap + 1, 1 + dy, z) in dests
        assert got == cases[(gap, dy)], "gap %d, dy %+d: crossed=%s, expected %s" % (gap, dy, got, cases[(gap, dy)])


def test_a_gap_of_more_than_one_needs_a_run_up_behind_the_take_off():
    # breaks if: a standing player on a one-block perch is credited with a sprint jump, inventing shortcuts
    long_run = world_of("fill -4 0 0 0 0 0 minecraft:stone", "fill 4 0 0 4 0 0 minecraft:stone")
    assert (4, 1, 0) in {d for d, _ in A.Moves(long_run).edges((0, 1, 0))}
    perch = world_of("fill 0 0 0 0 0 0 minecraft:stone", "fill 4 0 0 4 0 0 minecraft:stone")
    assert (4, 1, 0) not in {d for d, _ in A.Moves(perch).edges((0, 1, 0))}


def test_a_run_off_into_open_air_lands_where_the_fall_model_says_and_never_past_water():
    # breaks if: a leap off a ledge is credited with reaching the bottom of a shaft it would splash into on the way
    # (which is how a sealed water column was briefly read as an entrance)
    w = world_of("fill -4 20 0 0 20 0 minecraft:stone",                    # the ledge: feet stand at y21
                 "fill 3 0 0 3 0 0 minecraft:stone",                       # the shaft's floor, twenty-one down
                 "fill 3 1 0 3 10 0 minecraft:water")                      # ten of water standing in it
    mv = A.Moves(w)
    dests = {d for d, _ in mv.edges((0, 21, 0))}
    assert (3, 10, 0) in dests, sorted(d for d in dests if d[0] == 3)      # the surface of the water, not the floor
    assert (3, 1, 0) not in dests


def test_a_bubble_column_carries_up_and_will_not_let_you_down():
    # breaks if: a soul-sand column is treated as ordinary water, so Blaine's vault becomes reachable without the leap
    col = ["fill 0 0 0 2 0 2 minecraft:stone", "fill 1 0 1 1 0 1 minecraft:soul_sand",
           "fill 1 1 1 1 6 1 minecraft:water",
           "fill 0 1 0 0 6 2 minecraft:stone", "fill 2 1 0 2 6 2 minecraft:stone",
           "fill 1 1 0 1 6 0 minecraft:stone", "fill 1 1 2 1 6 2 minecraft:stone"]
    mv = A.Moves(world_of(*col))
    assert {(1, y, 1) for y in range(1, 7)} == mv.bubble
    assert (1, 5, 1) not in {d for d, _ in mv.edges((1, 6, 1))}            # no way down
    assert (1, 6, 1) in {d for d, _ in mv.edges((1, 5, 1))}                # up is fine
    plain = A.Moves(world_of(*[c.replace("soul_sand", "stone") for c in col]))
    assert (1, 5, 1) in {d for d, _ in plain.edges((1, 6, 1))}             # with stone under it, it is just water


def test_a_one_high_flooded_hole_is_entered_only_from_water_deep_enough_to_swim_in():
    # breaks if: crawling into a one-high hole from dry land is allowed (the game refuses it; Erika's drain was
    # rejected for exactly this in the works these buildings replaced)
    common = ["fill 0 0 0 8 0 2 minecraft:stone",
              "fill 4 1 1 8 1 1 minecraft:water", "fill 4 2 1 8 2 1 minecraft:stone",
              "fill 4 1 0 8 2 0 minecraft:stone", "fill 4 1 2 8 2 2 minecraft:stone"]
    dry = A.Moves(world_of(*common))
    assert (8, 1, 1) not in dry.graph([(1, 1, 1)])
    deep = A.Moves(world_of(*common, "fill 3 1 1 3 2 1 minecraft:water",
                            "fill 3 1 0 3 3 0 minecraft:stone", "fill 3 1 2 3 3 2 minecraft:stone"))
    assert (8, 1, 1) in deep.graph([(1, 1, 1)])


def test_water_beside_air_is_a_leak_and_its_reach_is_seven_blocks_of_floor():
    # breaks if: an unsealed source is missed, or the spread is mis-sized (a source on flat floor wets 2*7*8 = 112)
    rep = A.Report()
    leaky = world_of("fill -12 0 -12 12 0 12 minecraft:stone", "fill -12 1 -12 12 6 12 minecraft:air",
                     "fill 0 1 0 0 1 0 minecraft:water")
    A.check_water(rep, "g", leaky, None, set())
    assert "leak" in rep.codes()
    assert len(A.flow_extent(leaky, [(0, 1, 0)])) == 112
    sealed = world_of("fill -3 0 -3 3 0 3 minecraft:stone", "fill -3 1 -3 3 6 3 minecraft:stone",
                      "fill 0 1 0 0 1 0 minecraft:water")
    rep = A.Report()
    A.check_water(rep, "g", sealed, None, set())
    assert "leak" not in rep.codes()
    rep = A.Report()
    lava = world_of("fill -12 0 -12 12 0 12 minecraft:stone", "fill -12 1 -12 12 6 12 minecraft:air",
                    "fill 0 1 0 0 1 0 minecraft:lava")
    A.check_water(rep, "g", lava, None, set())
    assert "lava" in rep.codes()


def test_a_ladder_needs_a_wall_behind_it_and_lanterns_and_chains_need_something_to_hold():
    # breaks if: the support rules are wrong (ladder[facing=east] leans on the block to its WEST). 31 lanterns
    # stood in mid air across the works these buildings replaced and nothing reported it.
    rep = A.Report()
    ok = world_of("fill 0 0 0 0 5 0 minecraft:stone", "fill 1 1 0 1 4 0 minecraft:ladder[facing=east]",
                  "fill 1 0 0 1 0 0 minecraft:stone", "fill 1 6 0 1 6 0 minecraft:stone",
                  "fill 1 5 0 1 5 0 minecraft:lantern[hanging=true]")
    A.check_blocks(rep, "g", ok)
    assert not rep.codes(), rep.problems
    rep = A.Report()
    bad = world_of("fill 1 1 0 1 4 0 minecraft:ladder[facing=east]", "fill 1 0 0 1 0 0 minecraft:stone",
                   "fill 3 3 3 3 3 3 minecraft:lantern[hanging=true]", "fill 5 5 5 5 5 5 minecraft:chain",
                   "fill 7 7 7 7 7 7 minecraft:azalea_leaves")
    A.check_blocks(rep, "g", bad)
    assert {"ladder", "lantern", "chain", "leaves"} <= rep.codes(), sorted(rep.codes())
    rep = A.Report()
    A.check_blocks(rep, "g", world_of("fill 0 0 0 0 0 0 minecraft:azalea_leaves[persistent=true]"))
    assert "leaves" not in rep.codes()


def test_the_seed_ring_is_the_lot_perimeter_at_pad_level_and_never_the_door_the_record_declares(baseline):
    # breaks if: the audit starts the player where the building says its door is, so a building with no door passes
    for gid, site in baseline[1].items():
        world = baseline[2][gid]
        st = A.seeds(site, world)
        assert st, gid
        x0, z0, x1, z1 = site.lot
        for (x, y, z) in st:
            assert y == site.level + 1, (gid, x, y, z)
            assert x in (x0, x1) or z in (z0, z1), (gid, x, y, z)


def test_the_ground_comes_from_the_town_plan_and_the_heightmap_and_never_from_a_world():
    # breaks if: the audit starts reading a world save to decide where the ground is (CLAUDE.md's ground rule)
    src = (ROOT / "tools" / "gym_buildings_independent.py").read_text(encoding="utf-8")
    assert "WORLD_READS = set()" in src
    for forbidden in (".mca", "level.dat", "session.lock", "cobblers-10240", "nbtlib", "amulet"):
        assert forbidden not in src.lower(), forbidden
    assert "import ground" in src and "site.surface" in src


# ---------------------------------------------------------------------------------------------------- the command
def test_the_command_prints_one_verdict_line_and_only_problems(emitted):
    # breaks if: the audit lists what passed, or exits 0 while it has problems
    _, funcs = emitted
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gym_buildings_independent.py"), "--functions", str(funcs)],
                       capture_output=True, text=True, timeout=600)
    if r.returncode not in (0, 1):
        pytest.skip("the audit could not run here: " + r.stdout[-200:] + r.stderr[-200:])
    lines = r.stdout.strip().splitlines()
    assert lines[-1].startswith("gym buildings (independent): ")
    body = lines[:-1]
    assert all(re.match(r"gym\d+ [A-Z]+: ", l) for l in body), body[:3]
    assert (r.returncode == 1) == bool(body)


def test_the_command_refuses_an_empty_functions_folder(tmp_path):
    # breaks if: a missing build is reported as a clean audit
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gym_buildings_independent.py"), "--functions", str(tmp_path)],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 2 and "run python tools/gym_buildings.py build first" in r.stdout
