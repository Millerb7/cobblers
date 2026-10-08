"""tools/hoopa_cradle.py and data/hoopa_cradle.json: one catchable Hoopa per player after the Rift release.

Written by the builder of the pack (the legendaries sweep, 2026-10-06), so these are the builder's own checks, not an
independent audit; docs/world-building/LEGENDARY_SWEEP.md "What an audit must check" lists what a second reader owes.

The independent sides, none of them the record:
  the cradle     data/relic_underground.json geometry.cradle (centre, floor, radius) and geometry.release.at (the binder)
  the release    data/quests.json unlock_league_after_rift_resolution's FIRST effect, and data/dialogue.json
                 dlg_main_relic_hall_release, the one node that runs it
  the decision   level 60 and 'once per player, back until caught' (docs/STATE.md, the owner, 2026-10-06), stated here

Mutations change the GENERATOR (monkeypatched functions) or a copy of the record in memory; no file is written.
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
import hoopa_cradle as H  # noqa: E402

DOC = H.load()
RELIC = json.loads((ROOT / "data" / "relic_underground.json").read_text(encoding="utf-8"))
QUESTS = json.loads((ROOT / "data" / "quests.json").read_text(encoding="utf-8"))
DIALOGUE = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
CRADLE = RELIC["geometry"]["cradle"]
BINDER = RELIC["geometry"]["release"]["at"]
OWNER_LEVEL = 60          # the owner's default, 2026-10-06 (docs/STATE.md): the cap after gym 8
FLAG = "cobblers:flag/rift_crisis_resolved"


def fns(doc=DOC):
    return H.functions(doc)


def cmds(lines):
    return [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def test_the_committed_record_has_no_problems():
    assert H.problems(DOC) == []


# Without it the Hoopa could stand anywhere: the keeper's position is read back out of the generated text and held to
# the cradle's own centre and floor, which this file takes from data/relic_underground.json, not from the record.
def test_the_keeper_and_the_spawn_stand_on_the_cradles_centre():
    want = (CRADLE["centre"][0] + 0.5, CRADLE["floor_y"] + 1, CRADLE["centre"][1] + 0.5)
    f = fns()
    keeper = " ".join(cmds(f["keeper"]))
    for m in re.finditer(r"positioned ([\d.]+) (\d+) ([\d.]+)", keeper):
        assert (float(m.group(1)), int(m.group(2)), float(m.group(3))) == want
    m = re.search(r'x:"([\d.]+)",y:(\d+),z:"([\d.]+)"', " ".join(cmds(f["appear"])))
    assert m and (float(m.group(1)), int(m.group(2)), float(m.group(3))) == want


def test_a_spot_off_the_cradle_is_refused():
    d = copy.deepcopy(DOC)
    d["spot"] = [d["spot"][0] + 3, d["spot"][1], d["spot"][2]]
    assert any("not the cradle's centre" in p for p in H.problems(d))
    d = copy.deepcopy(DOC)
    d["spot"] = [d["spot"][0], d["spot"][1] + 1, d["spot"][2]]
    assert any("floor" in p for p in H.problems(d))


# Without it the release could run while its player stands outside the keeper's reach and nothing would appear.
def test_the_binders_stand_is_inside_the_keepers_reach():
    sx, _, sz = DOC["spot"]
    assert ((BINDER[0] - sx) ** 2 + (BINDER[2] - sz) ** 2) ** 0.5 <= DOC["keeper"]["near_radius"]
    d = copy.deepcopy(DOC)
    d["keeper"]["near_radius"] = 6
    assert any("binder" in p for p in H.problems(d))


# THE WIRING. The keeper must key on exactly what the release grants, and the release must be reachable only through
# the one dialogue node. Read from the quest and the dialogue, not from the record.
def test_the_flag_the_keeper_reads_is_the_release_transitions_first_grant():
    tr = next(t for q in QUESTS["quests"] for t in q.get("transitions") or []
              if t["id"] == "unlock_league_after_rift_resolution")
    assert tr["effects"][0] == {"kind": "function", "function": FLAG + "/grant"}
    assert DOC["gate_flag"] == FLAG
    keeper = " ".join(cmds(fns()["keeper"]))
    assert "advancements={%s=true,%s=false}" % (FLAG, DOC["caught_advancement"]) in keeper


def test_the_release_node_is_the_one_that_runs_the_transition():
    runs = []
    for c in DIALOGUE["conversations"]:
        for n in c["nodes"]:
            for a in (n.get("actions_after_acknowledge") or []) + [a for r in n.get("responses") or []
                                                                   for a in r.get("actions") or []]:
                if a.get("kind") == "quest_transition" and a.get("transition") == "unlock_league_after_rift_resolution":
                    runs.append((c["id"], n["id"]))
    assert runs == [("dlg_main_relic_hall_release", "release_001")]


def test_a_transition_whose_first_effect_moved_is_refused():
    q = copy.deepcopy(QUESTS)
    for qq in q["quests"]:
        for t in qq.get("transitions") or []:
            if t["id"] == "unlock_league_after_rift_resolution":
                t["effects"].insert(0, {"kind": "set_progression", "field": "x", "value": 1})
    assert any("first effect" in p for p in H.problems(DOC, quests=q))


# Without it the Hoopa would not be the owner's: species, level 60, wild (not a player's sent-out one), through the
# macro that EXP-046 proved is the only form a function can spawn with.
def test_appear_spawns_a_level_60_hoopa_through_the_macro():
    f = fns()
    assert DOC["level"] == OWNER_LEVEL
    assert cmds(f["spawn_at"]) == ["$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
    appear = " ".join(cmds(f["appear"]))
    assert 'species:"hoopa"' in appear and 'props:"level=60"' in appear
    assert 'Species:"cobblemon:hoopa",PokemonOriginalTrainerType:"NONE"' in appear
    assert "scoreboard players set @s hp.had 1" in appear


def test_bind_owns_tags_and_keeps_the_hoopa():
    b = cmds(fns()["bind"])
    assert "tag @s add cobblers.hoopa" in b
    assert "scoreboard players operation @s hp.own = #me hp.id" in b
    assert "data merge entity @s {PersistenceRequired:1b}" in b


# ONCE PER PLAYER, BACK UNTIL CAUGHT: modelled as a tiny state machine over the generated `tend` lines, so a change to
# the clock or to the 'never had one' branch shows here.
def _tend(player, hoopas, now, doc=DOC):
    """Run `tend` for one player in a model. player: {id, had, gone}; hoopas: [owner ids]. Returns True if it spawned."""
    lines = cmds(fns(doc)["tend"])
    resp = doc["keeper"]["respawn_after_ticks"]
    if player.get("id") is None:
        player["id"] = 7
    have = player["id"] in hoopas
    assert any("if score #have hp.t matches 1 run return 0" in ln for ln in lines)
    if have:
        player.pop("gone", None)
        return False
    if player.get("had") != 1:
        player["had"] = 1
        return True
    player.setdefault("gone", now)
    if now - player["gone"] <= resp - 1:
        return False
    player["had"] = 1
    player.pop("gone", None)
    return True


def test_the_clock_lines_say_what_the_model_assumes():
    lines = cmds(fns()["tend"])
    resp = DOC["keeper"]["respawn_after_ticks"]
    assert "execute if score #d hp.t matches ..%d run return 0" % (resp - 1) in lines
    assert any(ln.startswith("execute unless score @s hp.had matches 1 run return run function") for ln in lines)
    assert lines[-1] == "function cobblers:hoopa_cradle/appear"


def test_first_visit_spawns_and_a_lost_hoopa_returns_only_after_the_clock():
    p = {}
    assert _tend(p, [], 0)                       # the release: appears at once
    assert not _tend(p, [p["id"]], 20)           # present: nothing
    assert not _tend(p, [], 40)                  # fainted: the clock starts
    assert not _tend(p, [], 40 + DOC["keeper"]["respawn_after_ticks"] - 20)
    assert _tend(p, [], 40 + DOC["keeper"]["respawn_after_ticks"])


# Without it any thrower could hold another player's Hoopa, or a player who has caught theirs could take a second.
def test_the_ball_check_holds_only_for_an_eligible_owner():
    bc = " ".join(cmds(fns()["ball_check"]))
    elig = "advancements={%s=true,%s=false}" % (FLAG, DOC["caught_advancement"])
    assert "if entity @s[%s] as @e[type=cobblemon:pokemon,tag=cobblers.hoopa_hit,limit=1] if score @s hp.own = #thr hp.id" % elig in bc
    assert "execute if score #ok hp.t matches 0 run tag @s add cobblers.hoopa_refuse" in bc
    cb = H.callbacks(DOC)[H.CALLBACKS % "poke_ball_capture_calculated"]
    # the refusal is the only path to set_shakes(0), and the tag is added before and removed after the check
    assert cb.index("add_tag('cobblers.hoopa_hit')") < cb.index("ball_check") < cb.index("remove_tag('cobblers.hoopa_hit')")
    assert cb.count("q.set_shakes(0)") == 1
    assert cb.index("has_tag('cobblers.hoopa_refuse')") < cb.index("q.set_shakes(0)")


def test_only_a_hoopa_caught_near_the_cradle_counts():
    cb = H.callbacks(DOC)[H.CALLBACKS % "pokemon_captured"]
    assert "t.id == 'cobblemon:hoopa'" in cb
    x, y, z = DOC["spot"]
    assert "@s[x=%d,y=%d,z=%d,distance=..%d]" % (x, y, z, DOC["catch"]["catch_radius"]) in cb
    caught = cmds(fns()["caught"])
    assert "advancement grant @s only %s" % DOC["caught_advancement"] in caught


def test_the_pack_writes_one_load_tag_and_the_caught_advancement(tmp_path):
    files = H.build(DOC)
    assert json.loads(files["data/minecraft/tags/function/load.json"]) == {"values": ["cobblers:hoopa_cradle/load"]}
    adv = json.loads(files["data/cobblers/advancement/hoopa_cradle/caught.json"])
    assert adv["criteria"]["granted"]["trigger"] == "minecraft:impossible"
    H.write(files, tmp_path / "p")
    assert (tmp_path / "p" / "pack.mcmeta").is_file()


# MUTATE THE GENERATOR: drop the caught=false half of the keeper's gate and the wiring test must go red.
def test_a_generator_that_forgets_the_caught_gate_is_caught(monkeypatch):
    real = H.functions

    def broken(doc):
        out = real(doc)
        out["keeper"] = [ln.replace(",%s=false" % doc["caught_advancement"], "") for ln in out["keeper"]]
        return out
    monkeypatch.setattr(H, "functions", broken)
    with pytest.raises(AssertionError):
        test_the_flag_the_keeper_reads_is_the_release_transitions_first_grant()


def test_a_generator_that_moves_the_spawn_is_caught(monkeypatch):
    monkeypatch.setattr(H, "_xyz", lambda doc: "%.1f %d %.1f" % (doc["spot"][0] + 1.5, doc["spot"][1], doc["spot"][2] + 0.5))
    with pytest.raises(AssertionError):
        test_the_keeper_and_the_spawn_stand_on_the_cradles_centre()
