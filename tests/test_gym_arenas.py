"""The builder's tests for tools/gym_arenas.py and tools/pokemon_sizes.py (an independent audit is another agent's).

What breaks if these go: an arena that leaks into rock, a Pokemon block out of Battle Positions' search, a seat the
build function overwrites on a re-run, a leader's seat that one consumer reads from the hall and another from the
arena, and a size table that no longer matches the teams it was measured for.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import gym_arenas as GA  # noqa: E402


@pytest.fixture(scope="module")
def G():
    import ground
    return ground.load()


@pytest.fixture(scope="module")
def built(G):
    out = {}
    for _p, doc in GA.records():
        out[doc["id"]] = (doc,) + GA.build(doc, G)
    return out


def problems_of(doc, G):
    return GA.build(doc, G)[2]


# ------------------------------------------------------------------------------------------------- the records
def test_every_record_passes_its_own_checks(built):
    # breaks if: an authored arena fails a design rule and would still be emitted
    assert built, "no data/gym_arenas record"
    for gid, (_doc, _a, _ops, problems, _facts) in built.items():
        assert problems == [], (gid, problems)


def test_one_file_per_gym_named_by_its_id():
    for p, doc in GA.records():
        assert p.stem == doc["id"] == doc["gym"]
        assert (ROOT / "data" / "gym_interiors.json").exists()


def test_brock_battle_is_found_from_every_start_cell(built):
    # breaks if: a cell a battle starts from cannot find both Pokemon blocks (the set is then invalid)
    _doc, _a, _ops, _p, facts = built["gym1"]
    assert facts["battle_start_cells"] > 100
    for k in ("trainer_pokemon", "player_pokemon", "trainer_stand"):
        got, total = facts["markers_found_from"][k].split(" of ")
        assert got == total, (k, facts["markers_found_from"])


def test_brock_is_measured_to_onix(built):
    _doc, _a, _ops, _p, facts = built["gym1"]
    assert facts["size"]["clear_radius_species"] == "onix" and facts["size"]["clear_radius"] > 10
    assert facts["dais_height"] == 3 and facts["approach"] > 17


# ------------------------------------------------------------------------------------------- mutations: do the checks bite?
def _mutated(doc, f):
    d = copy.deepcopy(doc)
    f(d)
    return d


def test_a_pokemon_block_moved_toward_the_stage_is_refused(built, G):
    doc = built["gym1"][0]
    d = _mutated(doc, lambda d: d["battle"].__setitem__("trainer_pokemon", [1826, 121, 3670]))
    assert any("clear radius" in p for p in problems_of(d, G))


def test_the_challengers_block_beyond_the_search_is_refused(built, G):
    doc = built["gym1"][0]
    d = _mutated(doc, lambda d: d["battle"].__setitem__("player_pokemon", [1826, 121, 3690]))
    assert any("player_pokemon is out of Battle Positions' search" in p for p in problems_of(d, G))


def test_a_missing_shell_face_is_a_leak(built, G):
    doc = built["gym1"][0]

    def cut(d):
        d["parts"][0] = {"op": "carve", "box": [1810, 122, 3660, 1842, 136, 3703]}
    assert any("touch unwritten ground" in p for p in problems_of(_mutated(doc, cut), G))


def test_a_climbable_or_low_dais_is_refused(built, G):
    doc = built["gym1"][0]
    d = _mutated(doc, lambda d: d.__setitem__("floor_y", 124))
    assert any("the dais is 1 over the floor" in p for p in problems_of(d, G))


def test_cover_is_the_generator_not_the_record(built, G, monkeypatch):
    # a generator mutation: the same record against a stricter COVER must fail, so the slack is real, not tuned
    monkeypatch.setattr(GA, "COVER", GA.COVER + 1)
    assert any("natural blocks over the arena" in p for p in problems_of(built["gym1"][0], G))


def test_a_stair_with_no_headroom_cuts_the_descent(built, G, monkeypatch):
    # a generator mutation: headroom 1 leaves no room to walk the stair, and the floor is cut off
    doc = built["gym1"][0]
    real = GA.newel_stair

    def low(a, part):
        return real(a, dict(part, headroom=1))
    monkeypatch.setattr(GA, "newel_stair", low)
    assert any("cannot be reached on foot" in p for p in problems_of(doc, G))


# ------------------------------------------------------------------------------------------------- the seat
def test_the_build_function_never_writes_the_seat(built):
    # breaks if: a re-run of the arena erases the spawner the move set (the leader would be left with none)
    for gid, (doc, _a, ops, _p, _f) in built.items():
        sx, sy, sz = doc["leader"]["seat"]
        for cell in ((sx, sy, sz), (sx, sy - 1, sz)):
            for line in ops:
                m = re.match(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) ", line)
                if m:
                    b = [int(v) for v in m.groups()]
                    assert not GA.inside(cell, b), (gid, cell, line)
                m = re.match(r"setblock (-?\d+) (-?\d+) (-?\d+) ", line)
                if m:
                    assert tuple(int(v) for v in m.groups()) != cell, (gid, line)


def test_the_move_restores_the_old_cell_only_once_the_new_spawner_stands():
    doc = GA.records("gym1")[0][1]
    lines = [l for l in GA.seat_lines(doc, GA.reach()) if not l.startswith("#")]
    old = "if block 1832 155 3696 rctmod:trainer_spawner"
    restore = [l for l in lines if l.endswith("minecraft:polished_andesite") or l.endswith("minecraft:stone_bricks")]
    assert len(restore) == 2
    for l in restore:
        assert old in l and "if block 1826 125 3662 rctmod:trainer_spawner" in l and "distance=..17]" in l
    sets = [l for l in lines if "run setblock 1826 125 3662 rctmod:trainer_spawner" in l]
    assert len(sets) == 2 and all('TrainerIds:["kanto_brock"]' in l for l in sets)


def test_one_source_of_the_seat_reaches_every_consumer():
    # breaks if: the swap, the rematch hold-off, the world audit and the map disagree about where Brock stands
    import challenge_mode as CM
    seat = tuple(GA.records("gym1")[0][1]["leader"]["seat"])
    s = GA.leader_seats()["kanto_brock"]
    assert s["seat"] == seat and s["old_seat"] == (1832, 155, 3696)
    entry = CM.doc()["bosses"]["kanto_brock"]
    assert CM.normal_seat("kanto_brock", entry) == seat
    import route_trainers
    lines = "\n".join(route_trainers.leader_cycle_lines())
    assert "x=%d.5,y=%d,z=%d.5,distance=..24,nbt={TrainerId:\"kanto_brock\"}" % seat in lines
    assert "x=1832.5,y=155,z=3696.5" not in lines
    import trainer_world_audit
    assert [s for s in trainer_world_audit.spawners() if s[0] == "gym1"][0][2] == seat
    import nuzlocke_map
    g = nuzlocke_map.gyms()[1]
    assert (g["x"], g["z"]) == (seat[0], seat[2])


def test_a_leader_outside_the_rollout_needs_its_challenge_spawner_moved(built, G, monkeypatch):
    # breaks if: an arena for one of the seven is accepted while its second spawner stays in the hall
    cm = GA.load(ROOT / "data" / "challenge_mode.json")
    cm["single_leader"]["rollout"] = []
    real = GA.load
    monkeypatch.setattr(GA, "load", lambda p: cm if str(p).endswith("challenge_mode.json") else real(p))
    assert any("Challenge spawner" in p for p in problems_of(built["gym1"][0], G))


# ------------------------------------------------------------------------------------------------- the pack
def test_the_pack_builds_and_every_function_passes_the_limits(tmp_path, G):
    import function_limits
    out = tmp_path / "cobblers_gym_arenas"
    done = GA.build_pack(out, GA.records(), G)
    funcs = out / "data" / "cobblers" / "function" / "gym_arenas"
    assert done and (funcs / "verify.mcfunction").exists()
    for gid in done:
        for name in (gid, gid + "_seat", gid + "_old_leader", gid + "_old_leader_look", gid + "_old_leader_done"):
            p = funcs / ("%s.mcfunction" % name)
            assert p.exists(), name
            lines = p.read_text(encoding="utf-8").splitlines()
            assert function_limits.check_lines(lines, name) == [], name
    kills = (funcs / "gym1_old_leader_look.mcfunction").read_text(encoding="utf-8")
    assert 'TrainerId:"kanto_brock",InBattle:0b' in kills and 'TrainerId:"kanto_brock_challenge",InBattle:0b' in kills


def test_reapply_runs_the_arenas_after_the_buildings_and_before_the_retire(monkeypatch):
    import reapply
    # steps() lists some packs from their built index; this worktree has no build/, and the order is what is tested
    monkeypatch.setattr(reapply, "indexed", lambda *a, **k: [])
    assert "cobblers_gym_arenas" in reapply.WORLD_LOCAL
    try:
        steps = reapply.steps()
    except SystemExit as e:
        # other packs' own placement steps read their built index (relic_underground's, among others): without a
        # build/ the order is read from the source, where steps() appends them in run order
        if "prepare" not in str(e):
            raise
        src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
        pos = [src.index('("%s", "' % sid) for sid in ("R16E", "R16F", "R16G", "R16GA", "R17L")]
        assert pos == sorted(pos), pos
        acts = GA.steps()
        assert acts[-1] == ("check", "gym_arenas") and ("fn", "cobblers:gym_arenas/gym1_seat") in acts
        return
    ids = [s[0] for s in steps]
    assert "R16GA" in ids and ids.index("R16G") < ids.index("R16GA") < ids.index("R17L")
    assert ids.index("R16E") < ids.index("R16GA") and ids.index("R16F") < ids.index("R16GA")
    items = [s for s in steps if s[0] == "R16GA"][0][2]
    assert ("check", "gym_arenas") in [tuple(i) for i in items]


def test_presence_probes_are_in_world_probes():
    wp = GA.load(ROOT / "data" / "world_probes.json")["places"]
    for k, v in GA.presence_probes().items():
        assert wp.get(k) == v, k


# ------------------------------------------------------------------------------------------------- the sizes
def test_the_size_table_matches_the_teams_it_was_measured_for():
    # breaks if: a leader's team changes and data/gym_arena_sizes.json is not regenerated (an arena sized to an old team)
    import pokemon_sizes as PS
    sizes = GA.load(ROOT / "data" / "gym_arena_sizes.json")
    teams = PS.leader_teams()
    assert set(sizes["leaders"]) == set(teams)
    for lid, L in teams.items():
        got = {m["species"] for m in sizes["leaders"][lid]["members"]}
        assert got == set(L["members"]), (lid, got ^ set(L["members"]))
        for m in sizes["leaders"][lid]["members"]:
            assert m["clear_radius"] >= m["design_width"] / 2 ** 0.5 - 1e-6
            assert m["width_from"] and m["height_from"]


def test_no_leader_can_be_scaled_by_the_baby_ramp():
    import pokemon_sizes as PS
    sizes = GA.load(ROOT / "data" / "gym_arena_sizes.json")
    PS.check_levels(sizes)


# ------------------------------------------------------------------------------------------------- the survey
def test_the_survey_covers_eight_gyms_and_finds_mistys_standing_well():
    s = GA.load(ROOT / "data" / "gym_arenas" / "survey.json")
    assert s["cover"] == GA.COVER
    assert [g["gym"] for g in s["gyms"]] == ["gym%d" % i for i in range(1, 9)]
    g2 = s["gyms"][1]
    assert any(c["path"].endswith(".dig") and c["state"] == "carved and standing" for c in g2["carved_in_data"])
    for g in s["gyms"]:
        assert g["envelopes"]["lot"]["shell_top_max"] <= g["lot_level"] - 1 - GA.COVER if g["lot_level"] else True
