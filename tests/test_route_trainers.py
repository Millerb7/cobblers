"""tools/route_trainers.py: the Route 1-3 trainers as Radical Cobblemon Trainers data (build/datapacks/cobblers_trainers).

Written by the test author, not by the session that wrote the tool.

What is asserted, on the real data (data/trainers.json, data/route_trainers.json, data/progression.json): the seat
file names exactly the thirteen route_01_/route_02_/route_03_ trainers; each trainer file carries only keys rctapi
0.16's TrainerModel (name, ai, bag, team) or rctmod (battleRules) reads; each mob never spawns naturally, is beaten
once, and wears one of rctmod's own single-trainer textures; exactly route_01_trainer_01 forces a battle on sight;
the dialog keys carry the record's own three lines, one line per key; the defeat advancement fires on rctmod's
defeat_count for that trainer id alone at count 1; and the won function writes only the declared per-player fields
(the trainer's own defeated field, plus the north-bank quest's for the shore angler).

The Gastly mansion's five guardians, which the same tool generates from data/mansion_guardians.json, are asserted in
tests/test_mansion_guardians.py.

Not covered, and it needs a running server: that rctmod reads these files (mob keys, dialog keys, textureResource)
the way the names suggest; that defeat_count fires for the winner and never on a loss or forfeit (EXP-027 covers the
gym form); that `rctmod trainer summon_persistent` places the trainer at its seat (reapply.py R17).
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import route_trainers as RT  # noqa: E402

TRAINERS = {r["id"]: r for r in json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))["trainers"]}
SEATS = json.loads((ROOT / "data" / "route_trainers.json").read_text(encoding="utf-8"))["trainers"]
FIELDS = {f["id"] for f in json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))["quest_fields"]}
ROUTE_IDS = sorted(t for t in TRAINERS if re.match(r"route_0[123]_", t))
ALLOWED_TRAINER_KEYS = {"name", "ai", "bag", "team", "battleRules"}


@pytest.fixture(scope="module")
def files():
    return RT.files()


def ids():
    return [s["id"] for s in SEATS]


# Without it a Route 1-3 trainer in data/trainers.json is never generated or placed, or a seat names a trainer from
# another route.
def test_the_seats_are_exactly_the_thirteen_route_1_to_3_trainers():
    assert len(ROUTE_IDS) == 13
    assert sorted(ids()) == ROUTE_IDS
    assert len(set(ids())) == len(ids())


# Without it a key rctapi does not read (battleFormat, identity) is shipped and silently ignored, or a typo drops a
# team or bag without a word.
@pytest.mark.parametrize("tid", ROUTE_IDS)
def test_trainer_files_carry_only_keys_rctapi_or_rctmod_read(files, tid):
    doc = files["data/rctmod/trainers/%s.json" % tid]
    assert set(doc) <= ALLOWED_TRAINER_KEYS, set(doc) - ALLOWED_TRAINER_KEYS
    assert doc["team"] == TRAINERS[tid]["rct"]["team"] and doc["team"]
    assert doc["name"] == TRAINERS[tid]["rct"]["name"]


# Without it a route trainer spawns naturally all over the world, can be farmed for repeat wins, or wears a texture
# a client does not have.
@pytest.mark.parametrize("tid", ROUTE_IDS)
def test_mobs_never_spawn_are_beaten_once_and_wear_an_rctmod_texture(files, tid):
    mob = files["data/rctmod/mobs/trainers/single/%s.json" % tid]
    assert mob["spawnWeightFactor"] == 0
    assert mob["maxTrainerDefeats"] == 1
    assert re.fullmatch(r"rctmod:textures/trainers/single/[a-z0-9_]+\.png", mob["textureResource"]), mob["textureResource"]


# Without it the eye-contact lesson is lost (Route 1's first trainer does not stop the player), or every trainer
# forces a battle and the routes become a gauntlet nobody designed.
def test_exactly_the_first_route_1_trainer_forces_a_battle_on_sight(files):
    forced = sorted(t for t in ROUTE_IDS if files["data/rctmod/mobs/trainers/single/%s.json" % t].get("forceBattleOnSight"))
    assert forced == ["route_01_trainer_01"]
    # the route trainer keeps the open-air reach; only the mansion's guardians are shortened (sight_distance)
    assert files["data/rctmod/mobs/trainers/single/route_01_trainer_01.json"]["forceBattleMaxDistance"] == 8.0


# Without it the trainer says the losing line when the player wins, or a line from another record.
@pytest.mark.parametrize("tid", ROUTE_IDS)
def test_dialog_keys_carry_the_records_own_lines(files, tid):
    d = files["data/rctmod/dialogs/trainers/single/%s.json" % tid]
    text = TRAINERS[tid]["dialogue_text"]
    want = {"on_battle_start": text["pre"],
            "on_battle_lost": text["player_win"], "trainer_lost": text["player_win"],
            "on_battle_won": text["player_loss"], "trainer_won": text["player_loss"],
            # said while on cooldown, including the cycle's cooldown for a player who has beaten it
            "on_cooldown": "Let me catch my breath."}
    assert set(d) == set(want)
    for k, line in want.items():
        assert d[k] == [{"text": line}], k


# Without it the defeat field is set by another trainer's win, or by a count the first win does not reach (the same
# form tests/test_progression_pack.py pins for the badge flags).
@pytest.mark.parametrize("tid", ROUTE_IDS)
def test_the_defeat_advancement_is_defeat_count_for_this_trainer_at_count_1(files, tid):
    adv = files["data/cobblers/advancement/trainer/%s.json" % tid]
    assert list(adv["criteria"]) == ["won"]
    crit = adv["criteria"]["won"]
    assert crit["trigger"] == "rctmod:defeat_count"
    assert crit["conditions"] == {"trainer_ids": [tid], "count": 1}
    assert adv["rewards"]["function"] == "cobblers:trainers/won/%s" % tid
    assert "data/cobblers/function/trainers/won/%s.mcfunction" % tid in files


def _key(field):
    return "cobblers__" + field.replace(".", "__")


# Without it the won function writes a field no quest declares (state nobody reads), or someone else's field, or
# forgets to save; the north-bank angler must also mark its quest's trainer_defeated.
@pytest.mark.parametrize("tid", ROUTE_IDS)
def test_the_won_function_sets_only_the_declared_defeat_fields(files, tid):
    lines = files["data/cobblers/function/trainers/won/%s.mcfunction" % tid]
    mol = [l for l in lines if l.startswith("runmolang ")]
    assert len(mol) == 1
    body = re.fullmatch(r'runmolang "(.*)" @s', mol[0]).group(1)
    assigned = set(re.findall(r"t\.d\.([A-Za-z0-9_]+)\s*=", body))
    want = ["quest.%s.defeated" % tid]
    if tid == "route_02_shore_trainer_01":
        want.append("quest.evt_viltri_north_bank.trainer_defeated")
    assert all(f in FIELDS for f in want), [f for f in want if f not in FIELDS]
    assert assigned == {_key(f) for f in want}
    assert body.startswith("t.d = q.player.data();") and body.endswith("q.player.save_data();")
    # the winner is tagged at once (the trainer cycle refreshes that tag from the field); nothing else writes state
    assert [l for l in lines if l.startswith("tag ")] == ["tag @s add cobblers_beat_%s" % tid]
    assert not [l for l in lines if l.split(" ", 1)[0] in ("scoreboard", "data", "advancement", "function")]
