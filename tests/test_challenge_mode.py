"""Challenge mode's rctmod data (tools/challenge_mode.py through tools/route_trainers.py) and the generator field it
needs (docs/story/generate_trainers.py). Builder's tests; the independent audit is docs/mechanics/OAK_AND_CHALLENGE.md
"What an audit must check". Validity only: nothing here proves rctmod honours the series, the swap or the spawner
(docs/research/RCT_PER_PLAYER_MODE.md section 7 is the in-game list)."""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import challenge_mode as CM  # noqa: E402
import route_trainers as RT  # noqa: E402

DATA = json.loads((ROOT / "data" / "challenge_mode.json").read_text(encoding="utf-8"))
TRAINERS = {t["id"]: t for t in json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))["trainers"]}
PROG = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
SFX = DATA["id_suffix"]
SERIES = DATA["series"]["id"]
OVER, _HELD = RT.overrides()
BOSSES = CM.boss_ids(OVER)
UPSTREAM = [u for _r, u, _c, _e in BOSSES]


@pytest.fixture(scope="module")
def files():
    return RT.files()


def _fn(files, name):
    return files["data/cobblers/function/%s.mcfunction" % name]


# Without it a player's mode choice names a series rctmod does not know (COMMANDS_ERRORS_UNKNOWN_SERIES), or the
# Challenge curve differs from the Normal one because the series file sets its own caps.
def test_the_series_file_exists_and_sets_no_cap(files):
    s = files["data/rctmod/series/%s.json" % SERIES]
    assert set(s) == {"title", "description", "difficulty"}
    assert "initialLevelCap" not in s and "relativeLevelCap" not in s
    assert s["difficulty"] == 7, "the card would rank the modes, which the owner asked not to do"


# Without it a leader, an Elite Four member or the Champion has no Challenge team, and a Challenge player meets
# nobody they can fight there.
def test_thirteen_bosses_each_get_a_challenge_id():
    assert len(BOSSES) == 13
    assert sorted(UPSTREAM) == sorted(DATA["bosses"])
    assert all(c == u + SFX for _r, u, c, _e in BOSSES)


@pytest.mark.parametrize("up", UPSTREAM)
def test_a_challenge_boss_carries_its_records_challenge_team_under_its_own_identity(files, up):
    rec, cid = next((r, c) for r, u, c, _e in BOSSES if u == up)
    team = files["data/rctmod/trainers/%s.json" % cid]
    want = rec["modes"]["challenge"]["rct"]
    assert team["team"] == want["team"] and team["team"]
    assert team["identity"] == rec["id"] + SFX != files["data/rctmod/trainers/%s.json" % up].get("identity", rec["rct"]["name"])
    assert team["battleFormat"] == want["battleFormat"]
    # the cap condition (RCT_PER_PLAYER_MODE.md section 3): the Challenge team tops out at the record's ace
    assert max(m["level"] for m in team["team"]) == rec["ace_level"]


@pytest.mark.parametrize("up", UPSTREAM)
def test_a_challenge_boss_is_in_the_challenge_series_and_its_chain_mirrors_kantos(files, up):
    cid = up + SFX
    mob = files["data/rctmod/mobs/trainers/single/%s.json" % cid]
    assert mob["series"] == [SERIES]
    req = DATA["bosses"][up]["upstream_required"]
    assert mob.get("requiredDefeats", []) == [[r + SFX] for r in req]
    for k, v in DATA["bosses"][up]["upstream_mob"].items():
        assert mob[k] == v
    assert "relativeLevelCap" not in mob
    assert files["data/rctmod/loot_table/trainers/single/%s.json" % cid] == {"pools": []}


def test_the_challenge_chain_is_one_line_through_all_thirteen():
    nxt = {}
    for up in UPSTREAM:
        for r in DATA["bosses"][up]["upstream_required"]:
            assert r not in nxt, "%s is required by two trainers" % r
            nxt[r] = up
    first = [u for u in UPSTREAM if not DATA["bosses"][u]["upstream_required"]]
    assert first == ["kanto_brock"]
    walk, at = [], first[0]
    while at:
        walk.append(at)
        at = nxt.get(at)
    assert walk[-1] == "kanto_champion_blue" and len(walk) == 13


# Without it a Normal player is battled by Challenge Brock in silence or the refusal is rctmod's default, and a
# Challenge leader says nothing before a battle.
@pytest.mark.parametrize("up", UPSTREAM)
def test_a_challenge_boss_speaks_every_refusal_and_its_battle_lines(files, up):
    d = files["data/rctmod/dialogs/trainers/single/%s.json" % (up + SFX)]
    refusals = json.loads((ROOT / "data" / "trainer_refusals.json").read_text(encoding="utf-8"))["lines"]
    for ctx, text in refusals.items():
        assert d[ctx] == [{"text": text}], ctx
    for ctx in ("on_battle_start", "on_battle_won", "on_battle_lost", "trainer_won", "trainer_lost", "on_cooldown"):
        assert d[ctx], ctx
    if "league" in up or "champion" in up:
        assert all("text" in x for x in d["on_battle_start"]), "the League's Challenge copy speaks our lines"
    else:
        lang = DATA["bosses"][up]["lang"]
        assert d["on_battle_start"][0] == {"translatable": "dialogs.rctmod.%s.on_battle_start.0" % lang}


# Without it a Challenge Champion never opens the League's own doors: they key on upstream's defeat advancement,
# which upstream grants only for the Normal id.
@pytest.mark.parametrize("up", UPSTREAM)
def test_a_challenge_win_grants_upstreams_own_defeat_advancement(files, up):
    cid = up + SFX
    adv = files["data/cobblers/advancement/trainer/%s.json" % cid]
    assert adv["criteria"]["won"] == {"trigger": "rctmod:defeat_count", "conditions": {"trainer_ids": [cid], "count": 1}}
    fn = _fn(files, "trainers/won/%s" % cid)
    assert "advancement grant @s only %s" % DATA["bosses"][up]["advancement"] in fn
    assert re.fullmatch(r"cobbleverse:trainer/kanto/defeat_[a-z_]+", DATA["bosses"][up]["advancement"])


# Without it a Challenge leader's win sets no badge, so a Challenge player can never progress.
def test_every_kanto_badge_flag_lists_the_challenge_id_beside_the_normal_one():
    seen = set()
    for f in PROG["flags"]:
        ids = ((f.get("set_by") or {}).get("trainer_ids") or {}).get("kanto") or []
        for t in ids:
            if t in DATA["bosses"]:
                assert t + SFX in ids, (f["id"], ids)
                seen.add(t)
    assert len(seen) == 9, "eight gyms and the Champion carry a flag: %s" % sorted(seen)


# Without it a gym has one leader for both modes, or the second leader is spawned on a plinth, into a wall, or
# not at all. A boss in data/challenge_mode.json single_leader.rollout stands as ONE leader instead (the owner,
# 2026-10-07); its swap and retire function are tests/test_one_leader_swap.py's.
@pytest.mark.parametrize("up", [u for u in UPSTREAM if u not in CM.rollout()])
def test_each_challenge_boss_has_a_second_spawner_set_while_a_player_is_near(files, up):
    cid = up + SFX
    x, y, z = DATA["bosses"][up]["spawner"]["at"]
    place = _fn(files, "trainers/challenge/place_%s" % cid)
    body = [l for l in place if not l.startswith("#")]
    assert body == ["setblock %d %d %d minecraft:redstone_block" % (x, y - 1, z),
                    'setblock %d %d %d rctmod:trainer_spawner{TrainerIds:["%s"]}' % (x, y, z, cid)]
    cyc = _fn(files, "trainers/challenge/cycle")
    line = [l for l in cyc if l.endswith("run function cobblers:trainers/challenge/place_%s" % cid)]
    assert len(line) == 1
    assert line[0].startswith("execute if entity @a[x=%d,y=%d,z=%d,distance=..%d] if loaded %d %d %d unless block "
                              "%d %d %d rctmod:trainer_spawner if block %d %d %d minecraft:air if block %d %d %d "
                              "minecraft:air" % (x, y, z, CM.NEAR, x, y, z, x, y, z, x, y + 1, z, x, y + 2, z))


def test_the_challenge_cycle_runs_on_the_trainers_clock_before_the_cycle_resets_it(files):
    tick = _fn(files, "trainers/tick")
    calls = [l.rsplit(" ", 1)[-1] for l in tick if " run function " in l]
    assert calls.index("cobblers:trainers/challenge/cycle") < calls.index("cobblers:trainers/cycle")
    assert not any("_challenge" in l for l in _fn(files, "trainers/cycle")), "Challenge lines leaked into the cycle"


# The spawner cell, checked against the gym building's own model with the shared floor rule (tools/npc_spot_sweep.py
# spawner_problem): set into the floor, flush on four sides, room for the leader over it. Gym 2 and the League are
# templates nothing in the repository models; their cells were measured from the template and are NOT re-checked.
def _gym_models():
    import gym_buildings as GB
    out = {}
    for _p, d in GB.records():
        e, _r, _l = GB.build_one(d)
        out[d["leader"]["id"]] = (d, e)
    return out


@pytest.mark.parametrize("up", [u for u in UPSTREAM if DATA["bosses"][u]["spawner"]["measured_by"] == "gym_buildings"])
def test_a_gym_buildings_challenge_spawner_is_set_into_its_floor(up):
    import gym_buildings as GB
    import npc_spot_sweep as SW
    models = _gym_models()
    d, e = models[up]
    q = tuple(DATA["bosses"][up]["spawner"]["at"])
    assert list(q) != list(d["leader"]["spawner"])
    lo, hi = GB.norm(d["bounds"])[:3], GB.norm(d["bounds"])[3:]
    assert all(lo[i] <= q[i] <= hi[i] for i in range(3)), "outside the gym building"
    assert e.solid(*q), "the cell is not floor: %s" % e.at(*q)
    extra = {q: "rctmod:trainer_spawner", (q[0], q[1] - 1, q[2]): "minecraft:redstone_block"}
    why = SW.spawner_problem(lambda a, b, c: extra.get((a, b, c), e.at(a, b, c)), q)
    assert why is None, why
    lx, ly, lz = d["leader"]["spawner"]
    assert 2 <= abs(q[0] - lx) + abs(q[2] - lz) <= 5 and q[1] == ly


# ------------------------------------------------------------------------------------------------ routes
SEATED = [s for s in RT.load()[1] if s["id"] in TRAINERS and CM.has_challenge(TRAINERS[s["id"]])]


def test_every_seated_trainer_with_a_challenge_team_gets_a_challenge_copy(files):
    # 51 route seats, plus the gym juniors (data/gym_junior_trainers.json, 2026-10-06): each gets a Challenge copy too
    import json as _json
    juniors = _json.loads((ROOT / "data" / "gym_junior_trainers.json").read_text(encoding="utf-8"))
    n_jr = len(juniors.get("trainers") or juniors.get("seats") or juniors.get("juniors") or [])
    assert n_jr > 0 and len(SEATED) == 51 + n_jr, (len(SEATED), n_jr)
    for s in SEATED:
        cid = s["id"] + SFX
        assert files["data/rctmod/trainers/%s.json" % cid]["team"] == TRAINERS[s["id"]]["modes"]["challenge"]["rct"]["team"]
        mob = files["data/rctmod/mobs/trainers/single/%s.json" % cid]
        normal = files["data/rctmod/mobs/trainers/single/%s.json" % s["id"]]
        assert mob["series"] == [SERIES] and normal["series"] == [], "the Normal seat stays seriesless"
        assert {k: v for k, v in mob.items() if k != "series"} == {k: v for k, v in normal.items() if k != "series"}
        assert mob["optional"] is True and mob["requiredDefeats"] == [], "a route copy must never move a cap"
        assert files["data/rctmod/dialogs/trainers/single/%s.json" % cid] == \
            files["data/rctmod/dialogs/trainers/single/%s.json" % s["id"]]


def test_no_seat_without_a_challenge_team_gets_a_copy(files):
    have = {s["id"] for s in SEATED}
    for s in RT.load()[1]:
        if s["id"] not in have:
            assert "data/rctmod/trainers/%s.json" % (s["id"] + SFX) not in files, s["id"]


def test_the_swap_follows_the_nearest_player_and_never_a_battle(files):
    cyc = _fn(files, "trainers/challenge/cycle")
    tag = DATA["mode"]["tag"]
    for s in SEATED:
        tid, cid = s["id"], s["id"] + SFX
        to_c = [l for l in cyc if 'nbt={TrainerId:"%s",InBattle:0b}] at @s as @p[' % tid in l
                and l.endswith('{TrainerId:"%s"}' % cid)]
        back = [l for l in cyc if 'nbt={TrainerId:"%s",InBattle:0b}]' % cid in l and l.endswith('{TrainerId:"%s"}' % tid)]
        assert len(to_c) == 1 and "if entity @s[tag=%s]" % tag in to_c[0]
        assert len(back) == 2
        assert any("unless entity @s[tag=%s]" % tag in l for l in back)
        assert any("unless entity @a[distance=.." in l for l in back)


# ------------------------------------------------------------------------------------------------ generator
def test_the_trainer_generator_is_current():
    r = subprocess.run([sys.executable, str(ROOT / "docs" / "story" / "generate_trainers.py"), "--check-active"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_every_challenge_payload_has_its_own_identity():
    for t in TRAINERS.values():
        if t.get("modes"):
            assert t["modes"]["challenge"]["rct"]["identity"] == t["id"] + SFX
            assert t["modes"]["normal"]["rct"]["identity"] == t["rct"]["identity"] == t["id"]


def test_challenge_rct_refuses_a_team_that_would_move_the_cap():
    rec = copy.deepcopy(TRAINERS["gym_01_brock"])
    rec["modes"]["challenge"]["rct"]["team"][0]["level"] = rec["ace_level"] + 3
    with pytest.raises(SystemExit):
        CM.challenge_rct(rec)


def test_a_boss_entry_for_a_trainer_nobody_overrides_fails(monkeypatch):
    d = copy.deepcopy(DATA)
    d["bosses"]["kanto_nobody"] = d["bosses"]["kanto_brock"]
    monkeypatch.setattr(CM, "doc", lambda: d)
    with pytest.raises(SystemExit):
        CM.boss_ids(OVER)
