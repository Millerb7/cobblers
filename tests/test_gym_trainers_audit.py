"""tools/gym_trainers_audit.py: the independent audit of the gym juniors (every seat in data/gym_junior_trainers.json).

Two halves. The first runs the audit's own movement, sight and replay code over SYNTHETIC halls whose answers can
be worked out by hand, so the model is tested on more than the one set of real halls. The second runs the audit
over the real emitted packs, the donor template, the heightmap and the jars (skipped when a checkout lacks them),
and proves its independence by MUTATING THE GENERATORS -- tools/route_trainers.py's placements() (what R17
summons) and docs/story/generate_trainers.py's build_gym_trainers() -- never the authored records.

Not covered (an experiment, not pytest): rctmod's real sight test and eye contact, a junior actually summoned at its
seat and facing its yaw, the hold-off, a walk of each hall counting the fights before the leader, and what other
packs write into the halls after the gym buildings.
"""
import gzip
import importlib
import io
import math
import struct
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import gym_trainers_audit as A  # noqa: E402


# ------------------------------------------------------------------------------------------------ synthetic halls
def flat_hall(cmds, box=(0, 60, 0, 30, 80, 30), floor=63):
    """A hall over stone up to `floor`, with the commands replayed on it; lot and footprint are the whole box."""
    def base(x, y, z):
        return "minecraft:stone" if y <= floor else "minecraft:air"

    w = A.World(base)
    for c in cmds:
        w.run(c)
    x0, y0, z0, x1, y1, z1 = box
    h = A.Hall("test", w, box, (x0, z0, x1, z1), (x0, z0, x1, z1), (25, floor, 25), "foot")
    h.level, h.ring = floor, {}
    return h


def corridor(width=1, bypass=False):
    """A walled corridor along +z at x 10.., floor y63, from z 2 to z 28; optionally a parallel corridor at x 14 that
    rejoins at both ends (a way round whatever stands in the first)."""
    cmds = ["fill 5 64 0 20 66 30 minecraft:stone",            # solid rock over the floor
            "fill 10 64 2 %d 65 28 minecraft:air" % (9 + width)]
    if bypass:
        cmds += ["fill 14 64 2 14 65 28 minecraft:air",
                 "fill 10 64 2 14 65 3 minecraft:air",
                 "fill 10 64 27 14 65 28 minecraft:air"]
    return cmds


def test_a_step_of_one_is_climbed_and_a_step_of_two_is_not():
    # Removing this lets a model that climbs walls (or cannot climb stairs) through: every cut it proves is wrong.
    h = flat_hall(["setblock 5 64 5 minecraft:stone", "fill 8 64 5 8 65 5 minecraft:stone"])
    nxt = {q for q, _s in A.moves(h, (4, 64, 5))}
    assert (5, 65, 5) in nxt
    nxt = {q for q, _s in A.moves(h, (7, 64, 5))}
    assert (8, 66, 5) not in nxt and (8, 65, 5) not in nxt


def test_a_gap_of_one_is_jumped_a_gap_of_two_only_when_allowed():
    # Removing this lets the jump table drift: the stated model is "no jumping over gaps wider than one".
    h = flat_hall(["fill 0 63 10 30 63 10 minecraft:air", "fill 0 60 10 30 62 10 minecraft:air",
                   "fill 0 60 20 30 63 21 minecraft:air"])
    assert (5, 64, 11) in {q for q, _s in A.moves(h, (5, 64, 9), gap=1)}
    assert (5, 64, 22) not in {q for q, _s in A.moves(h, (5, 64, 19), gap=1)}
    assert (5, 64, 22) in {q for q, _s in A.moves(h, (5, 64, 19), gap=2)}


def test_a_fall_lands_on_the_first_floor_below_and_records_the_cells_passed():
    # Removing this lets a fall skip a floor, or pass through a junior's sight without the cut noticing.
    h = flat_hall(["fill 0 64 0 4 70 4 minecraft:stone"])
    falls = {q: s for q, s in A.moves(h, (4, 71, 2)) if q[1] == 64}
    assert (5, 64, 2) in falls
    assert (5, 70, 2) in falls[(5, 64, 2)] and (5, 65, 2) in falls[(5, 64, 2)]


def test_yaw_zero_faces_south_and_the_half_plane_excludes_the_side():
    # Removing this lets a sign error in the yaw convention turn every junior round without a test noticing.
    seat = (10, 64, 10)
    assert A.surely_seen(seat, 0, 3.0, (10, 64, 11))           # yaw 0 faces +z
    assert not A.surely_seen(seat, 0, 3.0, (10, 64, 9))        # behind
    assert not A.surely_seen(seat, 0, 3.0, (11, 64, 10))       # beside
    assert A.surely_seen(seat, 90, 3.0, (9, 64, 10))           # yaw 90 faces -x
    assert A.surely_seen(seat, 0, 3.0, (11, 64, 10), cone=False)
    # the uncertainty is a cell's centre-to-corner half a block up, and it shrinks the sure sight
    assert math.isclose(A.U, math.sqrt(0.75))
    assert not A.surely_seen(seat, 0, 3.0, (10, 64, 13))       # 3.0 > 3.0 - U


def test_must_pass_holds_in_a_one_wide_corridor_and_fails_with_a_bypass():
    # Removing this lets the cut pass a junior that a parallel corridor walks round.
    for bypass, avoidable in ((False, False), (True, True)):
        h = flat_hall(corridor(bypass=bypass))
        g = A.Graph(h, [(10, 64, 2)])
        goal = {(10, 64, 28)}
        j = {"t": {"seat": (10, 64, 15), "yaw": 180, "sight": 3.0}}
        r = A.junior_walks(h, g, j, goal)["t"]
        assert bool(r["evade"][False]) is avoidable


def test_a_junior_in_a_one_wide_corridor_is_a_softlock_and_in_a_two_wide_one_is_not():
    # Removing this lets a junior wall the only way to its leader.
    for width, walled in ((1, True), (2, False)):
        h = flat_hall(corridor(width=width))
        g = A.Graph(h, [(10, 64, 2)])
        j = {"t": {"seat": (10, 64, 15), "yaw": 180, "sight": 3.0}}
        assert A.junior_walks(h, g, j, {(10, 64, 28)})["t"]["softlock_free"] is (not walled)


def test_two_juniors_side_by_side_wall_a_two_wide_lane_that_each_alone_leaves_open():
    # Removing this lets two juniors that each pass the one-at-a-time softlock check stand shoulder to shoulder
    # across a two-wide lane and lock the player out (R17 summons them all at once).
    h = flat_hall(corridor(width=2))
    g = A.Graph(h, [(10, 64, 2)])
    goal = {(10, 64, 28)}
    js = {"a": {"seat": (10, 64, 15), "yaw": 180, "sight": 3.0}, "b": {"seat": (11, 64, 15), "yaw": 180, "sight": 3.0}}
    walks = A.junior_walks(h, g, js, goal)
    assert walks["a"]["softlock_free"] and walks["b"]["softlock_free"]
    assert A.standing_together(g, goal, [(10, 64, 15)])["reaches_leader"] is True
    assert A.standing_together(g, goal, [(10, 64, 15), (11, 64, 15)])["reaches_leader"] is False


def test_a_junior_behind_a_wall_holds_the_cut_by_distance_but_not_by_line_of_sight():
    # Removing this lets a junior "guard" a corridor through a solid wall: rctmod's trigger is a mutual stare
    # (rctmod-server.toml forceBattleLookTicks: "look at each other"), so a wall between them may mean no battle.
    for window, blind in ((False, True), (True, False)):
        cmds = corridor(width=1) + ["fill 12 64 15 12 65 15 minecraft:air"]        # the junior's own pocket at x12
        if window:
            cmds.append("fill 11 64 15 11 65 15 minecraft:air")                     # x11 opened between them
        h = flat_hall(cmds)
        g = A.Graph(h, [(10, 64, 2)])
        r = A.junior_walks(h, g, {"t": {"seat": (12, 64, 15), "yaw": 90, "sight": 3.0}}, {(10, 64, 28)})["t"]
        assert r["evade"][False] is None                     # 2.0 from (10, 64, 15): surely within 3.0 - U
        assert bool(r["evade"]["los"]) is blind


def one_way_drop_hall():
    """A one-wide corridor (x10, feet y64) from the arrival at z2 to z14, then a two-block drop (z15-28, feet y62) to
    the leader at z28: the drop cannot be climbed back. The way back is a return lane: east at z20 to x12, two steps
    up (z19, z18) to y64, north along x12 to z5, west through x11 into the corridor. Worked by hand: everything past
    the drop gets back only along the x12 lane."""
    return flat_hall([
        "fill 5 61 0 20 70 30 minecraft:stone",
        "fill 10 64 2 10 65 14 minecraft:air",        # the upper corridor (floor y63)
        "fill 10 62 15 10 65 28 minecraft:air",       # the drop and the lower corridor (floor y61)
        "fill 11 62 20 12 65 20 minecraft:air",       # east at z20
        "fill 12 63 19 12 66 19 minecraft:air",       # step one (floor y62)
        "fill 12 64 18 12 66 18 minecraft:air",       # step two (floor y63)
        "fill 12 64 5 12 65 17 minecraft:air",        # the return lane
        "fill 11 64 5 11 65 5 minecraft:air",         # back into the corridor
    ])


def test_a_junior_in_the_only_way_back_from_a_drop_walls_the_player_in():
    # Removing this lets a junior stand in the one lane back out of a part of a hall a player drops into: the way in
    # still works (the softlock check passes) and the player cannot leave.
    h = one_way_drop_hall()
    g = A.Graph(h, [(10, 64, 2)])
    goal = {(10, 62, 28)}
    assert (10, 62, 15) in g.adj and (10, 64, 14) not in {q for q, _s in A.moves(h, (10, 62, 15))}
    free = A.standing_together(g, goal, [])
    assert free["reaches_leader"] and free["walled_in"] == [] and free["one_way"] == 0
    lane = A.standing_together(g, goal, [(12, 64, 10)])
    assert lane["reaches_leader"] is True
    assert (10, 62, 28) in lane["walled_in"] and (10, 62, 15) in lane["walled_in"]
    assert (10, 64, 2) not in lane["walled_in"]
    # the same junior on the corridor's own side, before the drop, walls nothing in: its seat is not on the way back
    side = A.standing_together(g, goal, [(10, 64, 3)])
    assert side["walled_in"] == [] and side["reaches_leader"] is False


def test_a_drop_with_no_way_back_at_all_is_the_halls_not_a_juniors():
    # Removing this lets a hall's own one-way drop be charged to a junior standing elsewhere (or hidden).
    h = flat_hall([                                   # one_way_drop_hall() without its return lane
        "fill 5 61 0 20 70 30 minecraft:stone",
        "fill 10 64 2 10 65 14 minecraft:air",
        "fill 10 62 15 10 65 28 minecraft:air",
    ])
    g = A.Graph(h, [(10, 64, 2)])
    st = A.standing_together(g, {(10, 62, 28)}, [(10, 64, 3)])
    # with the junior at z3 nothing past it is reached, so nothing is charged to it; with nobody standing the 14
    # cells z15-28 of the lower corridor are the hall's own trap
    assert st["walled_in"] == []
    assert A.standing_together(g, {(10, 62, 28)}, [])["one_way"] == 14


def test_fill_modes_replace_hollow_and_keep_replay_as_minecraft_does():
    # Removing this lets the replay misread a substitution or a hollow shell, and every hall built on it.
    w = A.World(lambda x, y, z: "minecraft:air")
    w.run("fill 0 0 0 2 2 2 minecraft:stone hollow")
    assert A.bare(w.at(1, 1, 1)) == "minecraft:air" and A.bare(w.at(0, 1, 1)) == "minecraft:stone"
    w.run("fill 0 0 0 2 2 2 minecraft:dirt replace minecraft:stone")
    assert A.bare(w.at(0, 0, 0)) == "minecraft:dirt" and A.bare(w.at(1, 1, 1)) == "minecraft:air"
    w.run("fill 0 0 0 2 2 2 minecraft:glass keep")
    assert A.bare(w.at(1, 1, 1)) == "minecraft:glass" and A.bare(w.at(0, 0, 0)) == "minecraft:dirt"


def test_an_unknown_block_fails_closed_and_waterlogged_plants_are_water():
    # Removing this lets an unclassified block silently become air (a hole) or solid (a wall).
    with pytest.raises(A.UnknownBlock):
        A.classify("somemod:mystery_thing")
    assert A.classify("minecraft:seagrass") == A.WATER
    assert A.classify("minecraft:tube_coral_fan[waterlogged=true]") == A.WATER
    assert A.classify("minecraft:oak_fence") == A.TALL
    assert A.classify("minecraft:stone_brick_stairs[waterlogged=true]") == A.SOLID
    assert A.classify("cobblefurnies:light_blue_poke_wool_carpet") == A.AIR


def _nbt_string(s):
    b = s.encode()
    return struct.pack(">H", len(b)) + b


def test_the_nbt_reader_reads_a_hand_built_structure():
    # Removing this lets the gym 2 template be misread, and Misty's hall with it.
    def tag(t, name, payload):
        return struct.pack(">b", t) + _nbt_string(name) + payload

    def ints(vals):
        return struct.pack(">bi", 3, len(vals)) + b"".join(struct.pack(">i", v) for v in vals)

    palette = struct.pack(">bi", 10, 1) + tag(8, "Name", _nbt_string("minecraft:stone")) + b"\x00"
    block = tag(9, "pos", ints([1, 2, 3])) + tag(3, "state", struct.pack(">i", 0)) + b"\x00"
    root = tag(10, "", tag(9, "size", ints([4, 5, 6])) + tag(9, "palette", palette)
               + tag(9, "blocks", struct.pack(">bi", 10, 1) + block) + b"\x00")
    d = A.read_nbt(gzip.compress(root))
    assert d["size"] == [4, 5, 6]
    assert d["palette"][0]["Name"] == "minecraft:stone"
    assert d["blocks"][0]["pos"] == [1, 2, 3]


# ------------------------------------------------------------------------------------------------ the real halls
MISSING = A.inputs_missing()
real = pytest.mark.skipif(bool(MISSING), reason="needs %s" % ", ".join(MISSING))


@pytest.fixture(scope="module")
def G():
    import ground
    return ground.load()


@pytest.fixture(scope="module")
def report(G):
    return A.audit(G=G)


def problems_of(rep, who, codes=None):
    return [p for p in rep["problems"] if p[1] == who and (codes is None or p[0] in codes)]


JUNIORS = sorted(A.load(ROOT / "data" / "gym_junior_trainers.json")["trainers"], key=lambda t: t["id"])
IDS = [t["id"] for t in JUNIORS]
# defects this audit found on 2026-10-06, each recorded in the hand-back. Strict by hand (pytest.xfail() is never
# strict): a known defect that is gone FAILS, naming the entry to remove. gym7_junior_03's softlock was fixed by
# moving its seat one block north to (6179, 120, 4991), gym3_junior_01's must-pass by moving it one block east to
# (1732, 175, 1424). Both moves were found by this audit and re-proved by tools/gym_trainers.py check.
# Found 2026-10-06 (A2 audit): the Archive Reader's cut holds only through a block -- a walk from (6195, 98, 3332)
# passes within 3.5 of her only where no clear line joins the player's eye to her (closest 2.45 at (6198, 99,
# 3326)). A warning in the CLI (runtime sight through walls is unverified), recorded here so it cannot widen.
KNOWN = {
    ("line_of_sight", "gym6_junior_01"): "the Archive Reader's cut holds only if rctmod's sight passes walls",
}


@real
def test_every_leader_spawner_is_built_where_its_record_says(report):
    # Removing this lets a hall move its leader without a record (or this audit's walk target) following.
    assert [p for p in report["problems"] if p[0] in ("leader", "blocks")] == []


@real
@pytest.mark.parametrize("tid", IDS)
def test_each_junior_stands_dry_inside_its_hall_and_alone(report, tid):
    # Removing this lets a junior be summoned into a wall, over a drop, onto another trainer or outside its hall.
    assert problems_of(report, tid, {"seat", "home", "sight"}) == []


@real
@pytest.mark.parametrize("tid", IDS)
def test_every_walk_to_the_leader_passes_within_each_juniors_sight(report, tid):
    # Removing this lets a junior stand where a player walks round it (attrition before the leader is the point).
    found = problems_of(report, tid, {"must_pass"})
    if ("must_pass", tid) in KNOWN:
        assert found, "fixed: remove ('must_pass', %r) from KNOWN" % tid
        pytest.xfail(KNOWN[("must_pass", tid)])
    assert found == []


@real
@pytest.mark.parametrize("tid", IDS)
def test_no_junior_walls_the_only_way_to_its_leader(report, tid):
    # Removing this lets a junior pinned at speed 0 lock a player out of the gym.
    found = problems_of(report, tid, {"softlock"})
    if ("softlock", tid) in KNOWN:
        assert found, "fixed: remove ('softlock', %r) from KNOWN" % tid
        pytest.xfail(KNOWN[("softlock", tid)])
    assert found == []


@real
@pytest.mark.parametrize("tid", IDS)
def test_every_walk_to_the_leader_passes_in_each_juniors_line_of_sight(report, tid):
    # Removing this lets a junior guard its lane only through a wall, which a mutual-stare trigger may never fire.
    found = [w for w in report["warnings"] if w[1] == tid and w[0] == "line_of_sight"]
    if ("line_of_sight", tid) in KNOWN:
        assert found, "fixed: remove ('line_of_sight', %r) from KNOWN" % tid
        pytest.xfail(KNOWN[("line_of_sight", tid)])
    assert found == []


@real
def test_no_gym_is_walled_by_its_juniors_standing_together(report):
    # Removing this lets juniors that each leave a lane open fill every lane together, or shut the only way back
    # out of a part of a hall a player drops into.
    together = [p for p in report["problems"] if p[0] in ("softlock", "walled_in") and p[1] in A.GYMS]
    assert together == []
    for gym, r in report["gyms"].items():
        assert r["info"].get("walled_in_by_juniors") == 0, gym


@real
@pytest.mark.parametrize("tid", IDS)
def test_each_juniors_rosters_fit_the_leader_and_reach_the_pack(report, tid):
    # Removing this lets a junior out-level its leader, leave the type, lose its Challenge identity or its files.
    assert problems_of(report, tid, {"roster", "leader"}) == []


@real
def test_levels_rise_in_the_order_a_player_meets_the_juniors(report):
    # Removing this lets a later junior be easier than an earlier one, which the order of the walk contradicts.
    assert [p for p in report["problems"] if p[0] == "order"] == []
    for gym, r in report["gyms"].items():
        assert len(r["info"]["order"]) == len(r["juniors"]), gym


@real
def test_no_other_trainer_is_seated_inside_a_gym(report):
    # Removing this lets a route or scene trainer stand inside a hall where no junior proof accounted for it.
    assert [p for p in report["problems"] if p[0] == "other_trainer"] == []


@real
def test_gym2_d1_is_still_open_as_built_and_the_proof_says_so(report):
    # Removing this lets D1 be fixed (or worsen) without the assume_closed cells in the seat file being revisited.
    r = report["gyms"]["gym2"]
    assert "D1: 21 of the 21 assume_closed cells are open as built" in r["notes"]
    assert r["info"]["as_built_on_foot_reaches_leader"] is True
    assert r["info"]["sealed_on_foot_reaches_leader"] is False


# ------------------------------------------------------------------------------------------------ mutation proofs
def mutated(path, old, new, name):
    """The module at `path` with one edit to its CODE (the authored data is untouched)."""
    src = Path(path).read_text(encoding="utf-8")
    assert src.count(old) == 1, "mutation anchor moved in %s" % path
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    saved = sys.modules.get(name)
    sys.modules[name] = mod
    try:
        exec(compile(src.replace(old, new), str(path), "exec"), mod.__dict__)
    finally:
        if saved is not None:
            sys.modules[name] = saved
        else:
            del sys.modules[name]
    return mod


PLACEMENTS = 'return [(s["id"], tuple(s["seat"]), s["yaw"]) for s in seats]'


@real
def test_moving_a_seat_in_route_trainers_fails_the_walk(G):
    # Removing this loses the proof that the walk checks the seat R17 summons, not a copy of the builder's answer.
    rt = mutated(ROOT / "tools" / "route_trainers.py", PLACEMENTS,
                 'return [(s["id"], (s["seat"][0] + (3 if s["id"] == "gym5_junior_03" else 0),) + '
                 'tuple(s["seat"][1:]), s["yaw"]) for s in seats]', "route_trainers_mutant")
    rep = A.audit(("gym5",), placements=rt.placements(), G=G)
    assert problems_of(rep, "gym5_junior_03", {"must_pass"}), rep["problems"]


@real
def test_turning_the_juniors_round_in_route_trainers_fails_the_facing(G):
    # Removing this loses the proof that the facing check reads the yaw R17 summons with.
    rt = mutated(ROOT / "tools" / "route_trainers.py", PLACEMENTS,
                 'return [(s["id"], tuple(s["seat"]), s["yaw"] + 180) for s in seats]', "route_trainers_mutant")
    clean = A.audit(("gym6",), G=G, strict_facing=True)
    assert problems_of(clean, "gym6_junior_01", {"facing"}) == []
    rep = A.audit(("gym6",), placements=rt.placements(), G=G, strict_facing=True)
    assert problems_of(rep, "gym6_junior_01", {"facing"}), rep["problems"]


@real
def test_two_juniors_moved_side_by_side_across_gym7s_stair_fail_together_and_not_alone(G):
    # Removing this loses the proof, on a real hall, that the juniors are judged standing at once: the Rim
    # Researcher moved (in route_trainers' placements, the generator of what R17 summons) beside the Stair Stoker
    # fills the stair's other lane, and only the all-at-once check sees it.
    rt = mutated(ROOT / "tools" / "route_trainers.py", PLACEMENTS,
                 'return [(s["id"], (6179, 116, 4987) if s["id"] == "gym7_junior_02" else tuple(s["seat"]), s["yaw"]) '
                 'for s in seats]', "route_trainers_mutant")
    rep = A.audit(("gym7",), placements=rt.placements(), G=G)
    assert problems_of(rep, "gym7", {"softlock"}), rep["problems"]
    assert problems_of(rep, "gym7_junior_02", {"softlock"}) == [] and problems_of(rep, "gym7_junior_04",
                                                                                  {"softlock"}) == []


@real
def test_undoing_the_stair_stokers_facing_correction_fails_the_facing(G):
    # Removing this loses the proof that the new gym 7 seat's yaw (135, corrected from 180) is what keeps the climb
    # past him in front of him.
    rt = mutated(ROOT / "tools" / "route_trainers.py", PLACEMENTS,
                 'return [(s["id"], tuple(s["seat"]), 180 if s["id"] == "gym7_junior_04" else s["yaw"]) '
                 'for s in seats]', "route_trainers_mutant")
    clean = A.audit(("gym7",), G=G, strict_facing=True)
    assert problems_of(clean, "gym7_junior_04", {"facing"}) == []
    rep = A.audit(("gym7",), placements=rt.placements(), G=G, strict_facing=True)
    assert problems_of(rep, "gym7_junior_04", {"facing"}), rep["problems"]


@real
def test_raising_a_team_in_the_trainer_generator_fails_the_roster(G):
    # Removing this loses the proof that the ace check reads what the generator emits, not what the rules say.
    gen = mutated(ROOT / "docs" / "story" / "generate_trainers.py",
                  'modes[mode_name] = {"team": deepcopy(slot["teams"][mode_name]),',
                  'modes[mode_name] = {"team": [dict(m, level=m["level"] + 6) for m in slot["teams"][mode_name]],',
                  "generate_trainers_mutant")
    roster = gen.build_gym_trainers(gen.load_json(gen.RULES_PATH))
    rep = A.audit(("gym1",), roster=roster, G=G)
    over = [p for p in problems_of(rep, "gym1_junior_01", {"roster"}) if "over the leader's ace" in p[2]]
    assert over, rep["problems"]
