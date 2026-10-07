"""The gym juniors (tools/gym_trainers.py, data/gym_junior_trainers.json, TRAINER_RULES gym_trainers).

The builder's own tests; the independent audit is a separate job (docs/world-building/GYM_TRAINERS.md, "What an
audit must check"). Three layers:

  the model     a small synthetic hall, built here, where the right answer is known by construction: a cut that
                holds, a seat that walls the corridor (softlock), a seat that covers nothing (cut fails), a jump
                that would squeeze between two blocks meeting at a corner, a leader behind a wall
  the halls     the real proof for gym 3 (the smallest hall), mutated in the SEAT -- moved off its chokepoint, its
                sight shrunk -- so the check is shown to bite on the real geometry; and gym 2 with its recorded
                defect open and closed. Needs the heightmap (and for gym 2 the donor zip); a skip names it
  the rosters   counts, levels against the ace and the pass order, both modes, and -- with COBBLERS_JAR_DIR set --
                species, type theme and every move against the Cobblemon 1.8 jar's own learnsets

NOT covered: whether rctmod's eye contact fires (a runtime fact), and the other six halls' full proofs, which
`python tools/gym_trainers.py check` runs (about three minutes, too long for the suite).
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "docs" / "story"))
import gym_trainers as T  # noqa: E402

SEATS = json.loads((ROOT / "data" / "gym_junior_trainers.json").read_text(encoding="utf-8"))
RULES = json.loads((ROOT / "docs" / "story" / "TRAINER_RULES.json").read_text(encoding="utf-8"))
ROSTER = {r["id"]: r for r in json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))["trainers"]}
ACES = RULES["difficulty"]["gym_ace_levels"]
TYPES = {1: "rock", 2: "water", 3: "electric", 4: "grass", 5: "poison", 6: "psychic", 7: "fire", 8: "ground"}


# ------------------------------------------------------------------------------------------------ the model
def synthetic(seat_alcove=True):
    """A start room (x1-3), a one-wide corridor (z5, x4-12) with an alcove at (7, z4), and the leader's room (x13-16).
    Floor y0, headroom y1-3, roof y4. The leader stands at (15, 1, 5)."""
    open_cells = set()
    for x in range(1, 4):
        for z in range(1, 10):
            open_cells |= {(x, y, z) for y in (1, 2, 3)}
    for x in range(4, 13):
        open_cells |= {(x, y, 5) for y in (1, 2, 3)}
    if seat_alcove:
        open_cells |= {(7, y, 4) for y in (1, 2, 3)}
    for x in range(13, 17):
        for z in range(1, 10):
            open_cells |= {(x, y, z) for y in (1, 2, 3)}

    def at(x, y, z):
        return "minecraft:air" if (x, y, z) in open_cells else "minecraft:stone"

    vox = T.Voxels((0, 0, 0, 17, 5, 10), at)
    h = T.Hall("test", vox, [(2, 1, 5)], (15, 1, 5), (0, 0, 17, 10), (0, 0, 17, 10), "test_leader")
    h.closed = []
    return h


@pytest.fixture(scope="module")
def small():
    h = synthetic()
    return h, T.Graph(h, True), T.Graph(h, False)


def codes(problems):
    return {c for c, _m in problems}


def test_a_seat_in_the_alcove_beside_the_only_corridor_is_proved(small):
    h, gen, mod = small
    assert gen.reaches_leader() and mod.reaches_leader()
    assert T.check_seat(h, gen, mod, (7, 1, 4), 2.5) == []


def test_a_seat_standing_in_the_one_wide_corridor_is_a_softlock(small):
    h, gen, mod = small
    assert "softlock" in codes(T.check_seat(h, gen, mod, (7, 1, 5), 2.5))


def test_a_seat_in_the_start_room_covers_nothing_and_the_cut_fails(small):
    h, gen, mod = small
    assert "cut" in codes(T.check_seat(h, gen, mod, (2, 1, 2), 2.5))


def test_a_sight_too_short_to_reach_the_corridor_for_certain_fails_the_cut(small):
    h, gen, mod = small
    # the corridor cell (7,1,5) is 1.0 from the seat's centre; a player anywhere in it is within 1.0 + SLACK, so a
    # sight of 1.5 cannot be counted on to catch them there
    assert "cut" in codes(T.check_seat(h, gen, mod, (7, 1, 4), 1.5))


def test_a_jump_along_the_corridor_does_not_fly_over_the_sight(small):
    h, gen, _mod = small
    blk = T.sight_block(gen, (7, 1, 4), 2.5)
    # a five-block sprint jump from (5,1,5) to (10,1,5) lands outside the blocked positions, but passes one block
    # from the junior on the way; the move is refused, not allowed for landing clear
    a, b = gen.index[(5, 1, 5)], gen.index[(10, 1, 5)]
    assert b in gen.adj[a] and a not in blk.nodes and b not in blk.nodes
    assert not gen._ok(a, b, blk.edge)


def test_a_sight_that_reaches_the_leader_is_refused(small):
    h, gen, mod = small
    assert "leader" in codes(T.check_seat(h, gen, mod, (7, 1, 4), 4.5))


def test_a_sight_past_the_footprint_is_refused():
    h = synthetic()
    h.footprint = (5, 0, 17, 10)            # the start room is "street" now
    gen, mod = T.Graph(h, True), T.Graph(h, False)
    assert "street" in codes(T.check_seat(h, gen, mod, (5, 1, 5), 2.5))


def test_a_jump_cannot_squeeze_between_two_blocks_that_meet_at_a_corner():
    # two solid columns at (1,*,0) and (0,*,1) meet at a corner; a straight line from (0,1,0) to (1,1,1) passes
    # through the shared corner and nowhere else
    solid = {(1, 1, 0), (1, 2, 0), (0, 1, 1), (0, 2, 1)}

    def at(x, y, z):
        return "minecraft:stone" if y <= 0 or (x, y, z) in solid else "minecraft:air"

    v = T.Voxels((-3, -1, -3, 4, 5, 4), at)
    assert not T.corridor_clear(v, (-1, 1, -1), (2, 1, 2))
    assert T.corridor_clear(v, (-1, 1, 2), (2, 1, 2))      # the same length along a clear row


def test_a_position_behind_a_wall_does_not_engage_the_leader():
    # the leader's room z1-4 and a pocket z6-8 beyond a one-block wall at z5: (5,1,6) is 2 from the leader at
    # (5,1,4) in a straight line, through the wall
    open_cells = {(x, y, z) for x in range(1, 10) for z in list(range(1, 5)) + list(range(6, 9)) for y in (1, 2, 3)}

    def at(x, y, z):
        return "minecraft:air" if (x, y, z) in open_cells else "minecraft:stone"

    v = T.Voxels((0, 0, 0, 10, 5, 9), at)
    h = T.Hall("wall", v, [(1, 1, 1), (1, 1, 7)], (5, 1, 4), (0, 0, 10, 9), (0, 0, 10, 9), "x")
    gen = T.Graph(h, True)
    assert gen.index[(5, 1, 3)] in gen.goals
    assert gen.index[(5, 1, 6)] not in gen.goals
    assert not any(gen.nodes[k][2] >= 6 for k in gen.goals)


def test_an_unknown_block_fails_closed():
    with pytest.raises(SystemExit):
        T.classify("somemod:mystery_block")


# ------------------------------------------------------------------------------------------------ the halls
def _heightmap_or_skip():
    import ground
    try:
        return ground.load()
    except SystemExit as e:
        pytest.skip("canonical heightmap unavailable: %s" % e)
    except FileNotFoundError as e:
        pytest.skip("canonical heightmap unavailable: %s" % e)


@pytest.fixture(scope="module")
def g3():
    G = _heightmap_or_skip()
    h, gen, mod, arrival = T.built("gym3", G, SEATS)
    return G, h, gen, mod


def test_gym3_seats_are_proved_on_their_own_hall(g3):
    _G, h, gen, mod = g3
    for s in [s for s in SEATS["trainers"] if s["gym"] == "gym3"]:
        assert T.check_seat(h, gen, mod, tuple(s["seat"]), float(s["sight_distance"])) == [], s["id"]


def test_gym3_mutation_moving_a_seat_into_the_hall_corner_breaks_its_cut(g3):
    _G, h, gen, mod = g3
    s = [s for s in SEATS["trainers"] if s["id"] == "gym3_junior_01"][0]
    # the hall's north-west corner, by the door: on the floor, inside the footprint, nowhere near the tower stair
    corner = (1727, 175, 1394)
    assert h.vox.dry_footing(*corner)
    assert "cut" in codes(T.check_seat(h, gen, mod, corner, float(s["sight_distance"])))


def test_gym3_mutation_shrinking_a_seats_sight_breaks_its_cut(g3):
    _G, h, gen, mod = g3
    s = [s for s in SEATS["trainers"] if s["id"] == "gym3_junior_02"][0]
    assert "cut" in codes(T.check_seat(h, gen, mod, tuple(s["seat"]), 0.5))


def test_gym3_the_leader_is_reached_only_by_the_designed_climb(g3):
    _G, h, gen, _mod = g3
    chain = [gen.nodes[k] for k in gen.dominators()]
    # the record's stair (x1733) and cable ladder (x1749, z1410) are on every walk to Surge
    assert any(p[0] == 1733 and p[1] in range(176, 182) for p in chain)
    assert any(p[0] == 1749 and p[2] == 1410 for p in chain)


def test_gym3_full_check_is_clean(g3):
    G, _h, _gen, _mod = g3
    recs = ROSTER
    seats = [s for s in SEATS["trainers"] if s["gym"] == "gym3"]
    problems, row = T.check_gym("gym3", seats, recs, G)
    assert problems == []
    # the property, not a recorded order: every gym 3 seat is met, once, and no junior met later tops out lower
    order = row["juniors_in_pass_order"]
    assert sorted(order) == sorted(s["id"] for s in seats)
    tops = [max(m["level"] for m in recs[t]["team"]) for t in order]
    assert tops == sorted(tops), list(zip(order, tops))


def test_gym2_the_proof_needs_defect_d1_closed_and_says_so():
    if not T.donor_zip():
        pytest.skip("gym 2 needs COBBLEVERSE-DP-v31.zip (set COBBLERS_DONOR_ZIP)")
    G = _heightmap_or_skip()
    seats = [s for s in SEATS["trainers"] if s["gym"] == "gym2"]
    problems, row = T.check_gym("gym2", seats, ROSTER, G)
    assert problems == []
    assert row["arrival"] == "sky"
    assert row["assumed_closed"] and all(c["open_as_built"] for c in row["assumed_closed"])
    # while D1 is open a walker climbs the well into the hall past both juniors: the report must say so
    assert all(j["cut_holds_with_defects_open"] is False for j in row["juniors"])
    # as built, on foot, the only way to Misty is the well: nothing reaches her once its breakout is blocked
    h0 = T.hall("gym2", G)
    walk = T.Graph(h0, True, "walk")
    shaft = frozenset(walk.index[(1620, y, 2867)] for y in range(100, 133) if (1620, y, 2867) in walk.index)
    assert walk.reaches_leader() and not walk.reaches_leader(shaft)


# ------------------------------------------------------------------------------------------------ the rosters
# The owner's ask (relayed by the A2 brief, 2026-10-06, and data/gym_junior_trainers.json's note): at least three
# juniors a gym. A gym whose geometry cannot take three says so as DATA, in its own entry of the seat file:
#   "gyms": {"gymN": {"below_minimum": {"juniors": <its count>, "why": "<the geometry>", "evidence": "<the check>"}}}
MIN_JUNIORS = 3


def test_every_gym_has_at_least_three_juniors_or_declares_why_not():
    # Removing this lets a gym fall below the owner's minimum silently, or keep an exception it no longer needs.
    by = {}
    for s in SEATS["trainers"]:
        by[s["gym"]] = by.get(s["gym"], 0) + 1
    assert len({s["id"] for s in SEATS["trainers"]}) == len(SEATS["trainers"])
    faults = []
    for n in range(1, 9):
        gym = "gym%d" % n
        have = by.get(gym, 0)
        exc = (SEATS.get("gyms", {}).get(gym) or {}).get("below_minimum")
        if have < MIN_JUNIORS:
            if not exc:
                faults.append("%s has %d junior(s), below %d, and no gyms.%s.below_minimum record in "
                              "data/gym_junior_trainers.json" % (gym, have, MIN_JUNIORS, gym))
            elif exc.get("juniors") != have or not exc.get("why") or not exc.get("evidence"):
                faults.append("%s's below_minimum record %r does not declare its count %d with a why and evidence"
                              % (gym, exc, have))
        elif exc:
            faults.append("%s has %d juniors but still declares below_minimum: remove it" % (gym, have))
        if have < 1:
            faults.append("%s has no junior at all" % gym)
    assert faults == []


def test_every_seat_has_a_generated_roster_with_both_modes_below_the_ace():
    for s in SEATS["trainers"]:
        r = ROSTER[s["id"]]
        n = int(s["gym"][3:])
        assert r["class"] == "gym_trainer" and r["gym_order"] == n
        tops = {m: max(p["level"] for p in r["modes"][m]["team"]) for m in ("normal", "challenge")}
        assert tops["normal"] == tops["challenge"] < ACES[n - 1], s["id"]
        assert len(r["modes"]["challenge"]["team"]) == len(r["modes"]["normal"]["team"]) + 1
        assert r["rct"] == r["modes"]["normal"]["rct"]
        assert r["modes"]["challenge"]["rct"]["ai"]["data"] == RULES["ai_profiles"]["gym_challenge"]
        assert set(r["dialogue_text"]) == {"pre", "player_win", "player_loss"}
        assert eye_and_sight(s)


def eye_and_sight(s):
    return s["eye_contact"] is True and 2.0 <= s["sight_distance"] <= 5.0


def test_juniors_top_out_above_the_route_before_and_rise_in_seat_order():
    route_top = {}
    for r in ROSTER.values():
        if r.get("class") in ("route", "optional_route"):
            route_top[r["route_order"]] = max(route_top.get(r["route_order"], 0), max(m["level"] for m in r["team"]))
    for n in range(1, 9):
        tops = [max(m["level"] for m in ROSTER[s["id"]]["team"]) for s in SEATS["trainers"] if s["gym"] == "gym%d" % n]
        assert tops == sorted(tops), n
        assert min(tops) >= route_top[n] - 1, (n, tops, route_top[n])


def test_the_generator_refuses_a_junior_at_the_ace():
    import generate_trainers as GT
    rules = deepcopy(RULES)
    rules["gym_trainers"]["trainers"][0]["teams"]["normal"][-1]["level"] = ACES[0]
    with pytest.raises(ValueError, match="ace"):
        GT.build_gym_trainers(rules)


def test_the_generator_refuses_a_challenge_that_moves_the_cap():
    import generate_trainers as GT
    rules = deepcopy(RULES)
    rules["gym_trainers"]["trainers"][0]["teams"]["challenge"][-1]["level"] += 1
    with pytest.raises(ValueError, match="Challenge tops out"):
        GT.build_gym_trainers(rules)


def test_the_generated_records_are_current():
    import generate_trainers as GT
    built = GT.build_gym_trainers(RULES)
    assert [r["id"] for r in built] == [s["id"] for s in SEATS["trainers"]]
    for r in built:
        assert ROSTER[r["id"]] == r


def _jar():
    d = os.environ.get("COBBLERS_JAR_DIR")
    if not d:
        pytest.skip("set COBBLERS_JAR_DIR to the server's mods folder to check species, types and moves")
    hits = sorted(Path(d).glob("Cobblemon-fabric-1.8*.jar"))
    if not hits:
        pytest.skip("no Cobblemon 1.8 jar in COBBLERS_JAR_DIR")
    return hits[0]


def test_every_member_is_a_real_species_on_theme_with_learnable_moves():
    import battle_sim as B
    species, _moves, _chart = B.load_pack(_jar())
    for s in SEATS["trainers"]:
        n = int(s["gym"][3:])
        for mode in ("normal", "challenge"):
            for m in ROSTER[s["id"]]["modes"][mode]["team"]:
                sp = species.get(B.key(m["species"]))
                assert sp, (s["id"], m["species"])
                assert TYPES[n] in (sp.get("primaryType"), sp.get("secondaryType")), (s["id"], m["species"])
                learn = {e.split(":", 1)[1] for e in sp.get("moves", [])}
                assert set(m["moveset"]) <= learn, (s["id"], m["species"], sorted(set(m["moveset"]) - learn))


def test_every_skin_is_one_rctmod_ships():
    d = os.environ.get("COBBLERS_JAR_DIR")
    if not d:
        pytest.skip("set COBBLERS_JAR_DIR to check the skins against rctmod's jar")
    jars = sorted(Path(d).glob("rctmod-*.jar"))
    if not jars:
        pytest.skip("no rctmod jar in COBBLERS_JAR_DIR")
    names = set(zipfile.ZipFile(jars[0]).namelist())
    for s in SEATS["trainers"]:
        ns, path = s["skin"].split(":", 1)
        assert "assets/%s/%s" % (ns, path) in names, s["skin"]
