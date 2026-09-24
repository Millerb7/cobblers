"""tools/rewards_pack.py and data/rewards.json: Victory Road's finds as per-player advancement grants (ADR-002).

Written by the test author, not by the session that wrote the tool or the data.

What is asserted: problems() refuses each malformed record the pack could otherwise be built from; the committed
data/rewards.json has none of them; the advancement's location criterion takes in the whole trigger box, in the
overworld, and runs cobblers:reward/<id>; the function gives exactly the listed contents and speaks only to @s; and
write() emits one advancement and one function per cache and nothing for an npc_grant.

Not covered, and it needs a boot or a functional test:
  - that Minecraft 1.21.1 loads the advancement and the function at all (the JSON shape is asserted, not parsed
    by the game);
  - that a player standing in the box is granted the advancement once, and a second player separately (ADR-002's
    two-player grant is unproven);
  - that the item ids and the TM component exist in the installed jars (jar_problems needs --server-dir and the
    coordination lock, and is not run here);
  - that the barrel really stands at container.at in a built world (tools/vr_regions.py checks its model).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rewards_pack as R  # noqa: E402

DOC = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
CACHES = [r for r in DOC["rewards"] if r.get("kind") == "cache"]


def cache(rid="vr_test", **over):
    r = {"id": rid, "kind": "cache", "place": "a test room",
         "trigger": {"min": [10, 20, 30], "max": [14, 23, 34]},
         "container": {"block": "minecraft:barrel", "at": [12, 20, 32]},
         "contents": [{"item": "cobblemon:water_stone", "count": 1, "verification": "a path in a jar"},
                      {"item": "cobblemon:technical_machine", "count": 2,
                       "components": "[cobblemon:tm_move={move:\"overheat\"}]", "verification": "another path"}],
         "message": "You found it."}
    r.update(over)
    return r


def grant(rid="vr_grant", **over):
    r = {"id": rid, "kind": "npc_grant", "npc_at": [1, 2, 3], "quest": "evt_test",
         "contents": [{"item": "obc:bottle_cap_gold", "count": 1, "verification": "a path in a jar"}]}
    r.update(over)
    return r


def probs(*records):
    return R.problems({"rewards": list(records)})


# ------------------------------------------------------------------ problems(): what the pack refuses

# Without it a well-formed record could be reported as broken, and every refusal test below would pass vacuously.
def test_a_well_formed_cache_and_npc_grant_have_no_problems():
    assert probs(cache(), grant()) == []


# Without it two records share cobblers:reward/<id>: the second one's files silently overwrite the first's.
def test_a_duplicate_id_is_refused():
    assert any("duplicate" in p for p in probs(cache("vr_same"), grant("vr_same")))


# Without it an id the game cannot use as a resource path (upper case, a dash, a space, none) reaches write().
@pytest.mark.parametrize("rid", ["VR_Upper", "vr-dash", "vr space", "", None, 7])
def test_an_id_that_is_not_a_resource_path_is_refused(rid):
    r = cache()
    r["id"] = rid
    assert any("bad id" in p for p in probs(r))


# Without it `give @s <item> 0` (or no count) is written: a find that gives nothing, or a function the game rejects.
@pytest.mark.parametrize("count", ["missing", 0, -3, "1", 1.5, None])
def test_an_item_without_a_positive_whole_count_is_refused(count):
    r = cache()
    if count == "missing":
        del r["contents"][0]["count"]
    else:
        r["contents"][0]["count"] = count
    assert any("positive count" in p for p in probs(r))


# Without it an item id nobody proved exists in a jar is shipped; the game drops a give of an unknown item.
@pytest.mark.parametrize("verification", ["missing", "", "   ", None])
def test_an_item_without_a_verification_string_is_refused(verification):
    r = cache()
    if verification == "missing":
        del r["contents"][1]["verification"]
    else:
        r["contents"][1]["verification"] = verification
    assert any("no verification" in p for p in probs(r)), \
        "verification=%r was accepted as proof that the item exists" % (verification,)


# Without it a cache with no trigger box crashes advancement(), or one with min > max is a box no player can stand in.
@pytest.mark.parametrize("trigger", [
    None,
    {},
    {"min": [10, 20, 30]},
    {"max": [14, 23, 34]},
    {"min": [10, 20], "max": [14, 23, 34]},
    {"min": [15, 20, 30], "max": [14, 23, 34]},        # x
    {"min": [10, 24, 30], "max": [14, 23, 34]},        # y
    {"min": [10, 20, 35], "max": [14, 23, 34]},        # z
], ids=["absent", "empty", "no_max", "no_min", "short_min", "x_inverted", "y_inverted", "z_inverted"])
def test_a_cache_without_a_valid_trigger_box_is_refused(trigger):
    r = cache()
    if trigger is None:
        del r["trigger"]
    else:
        r["trigger"] = trigger
    assert any("trigger" in p for p in probs(r))


# Without it the barrel can be built somewhere a player never enters the box: they open it, find it empty, and the
# advancement that holds the reward never fires.
@pytest.mark.parametrize("at", [[8, 20, 32], [16, 20, 32], [12, 18, 32], [12, 25, 32], [12, 20, 28], [12, 20, 36]])
def test_a_container_not_beside_its_trigger_box_is_refused(at):
    assert any("not beside" in p for p in probs(cache(container={"block": "minecraft:barrel", "at": at})))


# Without it the one-block allowance round the box is lost, and a barrel against the box's wall is refused.
@pytest.mark.parametrize("at", [[9, 20, 32], [15, 20, 32], [12, 19, 32], [12, 24, 32], [12, 20, 29], [12, 20, 35],
                                [10, 20, 30], [14, 23, 34]])
def test_a_container_inside_or_touching_its_trigger_box_is_accepted(at):
    assert probs(cache(container={"block": "minecraft:barrel", "at": at})) == []


# Without it the reward arrives in silence: the player is never told what they were given.
@pytest.mark.parametrize("message", ["missing", "", "  ", None])
def test_a_cache_without_a_message_is_refused(message):
    r = cache()
    if message == "missing":
        del r["message"]
    else:
        r["message"] = message
    assert any("no message" in p for p in probs(r)), "message=%r was accepted" % (message,)


# Without it an npc_grant is recorded that no quest gives: the find exists on paper and nowhere in the game.
@pytest.mark.parametrize("quest", ["missing", "", None])
def test_an_npc_grant_without_a_quest_is_refused(quest):
    r = grant()
    if quest == "missing":
        del r["quest"]
    else:
        r["quest"] = quest
    assert any("names its quest" in p for p in probs(r))


# Without it a typo in kind makes a record neither built nor granted, silently.
def test_an_unknown_kind_is_refused():
    assert any("kind" in p for p in probs(cache(kind="chest")))


# Without it a record with nothing in it builds a find that gives nothing.
def test_a_record_with_no_contents_is_refused():
    assert any("no contents" in p for p in probs(cache(contents=[])))


# Without it a bad file still produces a pack: main must stop before write() and leave no output behind.
def test_main_writes_nothing_when_the_data_has_a_problem(tmp_path):
    data = tmp_path / "rewards.json"
    data.write_text(json.dumps({"rewards": [cache(), cache()]}), encoding="utf-8")
    out = tmp_path / "out"
    assert R.main(["--data", str(data), "--out", str(out)]) == 1
    assert not out.exists()


# ------------------------------------------------------------------ the committed data

# Without it the committed file can carry any of the faults above and still be built by hand with write().
def test_the_committed_rewards_file_has_no_problems():
    assert R.problems(DOC) == []


# Without it a committed record can lack what its kind is used for: every cache its trigger, container and message,
# every npc_grant its quest and where the NPC stands (tools/reapply.py npcs() reads npc_at).
def test_every_committed_record_carries_the_fields_its_kind_needs():
    bad = []
    for r in DOC["rewards"]:
        need = ("trigger", "container", "message") if r["kind"] == "cache" else ("quest", "npc_at")
        bad += ["%s: %s" % (r["id"], k) for k in need if not r.get(k)]
    assert bad == []


# ------------------------------------------------------------------ advancement()

CASES = [cache()] + CACHES


# Without it a player standing on the last row of the box (x = max, feet at max + 0.7) is outside the predicate
# and never earns the find; or the check could fire at the same coordinates in another dimension.
@pytest.mark.parametrize("r", CASES, ids=lambda r: r["id"])
def test_the_advancement_takes_in_the_whole_trigger_box_in_the_overworld(r):
    a = R.advancement(r)
    (crit,) = a["criteria"].values()
    assert crit["trigger"] == "minecraft:location"
    (cond,) = crit["conditions"]["player"]
    assert cond["condition"] == "minecraft:entity_properties" and cond["entity"] == "this"
    loc = cond["predicate"]["location"]
    assert loc["dimension"] == "minecraft:overworld"
    lo, hi = r["trigger"]["min"], r["trigger"]["max"]
    for k, axis in enumerate("xyz"):
        assert loc["position"][axis] == {"min": lo[k], "max": hi[k] + 1}, axis


# Without it the advancement fires and runs nothing, or another find's function.
@pytest.mark.parametrize("r", CASES, ids=lambda r: r["id"])
def test_the_advancement_runs_the_reward_function_of_its_own_id(r):
    assert R.advancement(r)["rewards"] == {"function": "cobblers:reward/%s" % r["id"]}


# ------------------------------------------------------------------ function()

def _commands(lines):
    return [ln for ln in lines if ln.strip() and not ln.startswith("#")]


# Without it a component (the TM's move) or a count is dropped, and the player gets the wrong thing.
@pytest.mark.parametrize("r", CASES, ids=lambda r: r["id"])
def test_the_function_gives_every_item_with_its_components_and_count(r):
    gives = [ln for ln in _commands(R.function(r)) if ln.startswith("give ")]
    want = ["give @s %s%s %d" % (c["item"], c.get("components", ""), c["count"]) for c in r["contents"]]
    assert gives == want


# Without it the find is handed to, or announced to, everyone on the server instead of the one who earned it.
@pytest.mark.parametrize("r", CASES, ids=lambda r: r["id"])
def test_the_function_gives_and_speaks_only_to_the_earning_player(r):
    cmds = _commands(R.function(r))
    assert cmds, "no commands"
    for ln in cmds:
        verb, target = ln.split(" ", 2)[:2]
        assert verb in ("give", "tellraw"), ln
        assert target == "@s", ln
    tell = [ln for ln in cmds if ln.startswith("tellraw ")]
    assert len(tell) == 1
    assert json.loads(tell[0].split(" ", 2)[2])["text"] == r["message"]


# ------------------------------------------------------------------ write()

# Without it an npc_grant would also be given by an advancement (twice over), or a cache would have no function.
def test_write_emits_one_advancement_and_one_function_per_cache_and_nothing_for_a_grant(tmp_path):
    doc = {"rewards": [cache("vr_one"), grant("vr_given"), cache("vr_two")]}
    out = tmp_path / "cobblers_rewards"
    assert R.write(doc, out) == 2
    adv = sorted(p.name for p in (out / "data" / "cobblers" / "advancement" / "reward").iterdir())
    fn = sorted(p.name for p in (out / "data" / "cobblers" / "function" / "reward").iterdir())
    assert adv == ["vr_one.json", "vr_two.json"]
    assert fn == ["vr_one.mcfunction", "vr_two.mcfunction"]
    every = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert every == sorted(["pack.mcmeta"] + ["data/cobblers/advancement/reward/" + a for a in adv]
                           + ["data/cobblers/function/reward/" + f for f in fn])
    assert json.loads((out / "data/cobblers/advancement/reward/vr_one.json").read_text(encoding="utf-8")) \
        == R.advancement(doc["rewards"][0])
    body = (out / "data/cobblers/function/reward/vr_two.mcfunction").read_text(encoding="utf-8").splitlines()
    assert body == R.function(doc["rewards"][2])
    assert json.loads((out / "pack.mcmeta").read_text(encoding="utf-8"))["pack"]["pack_format"] == 48


# Without it a record removed from data/rewards.json keeps its advancement in the pack from the last build.
def test_write_replaces_a_previous_build_rather_than_adding_to_it(tmp_path):
    out = tmp_path / "cobblers_rewards"
    R.write({"rewards": [cache("vr_old")]}, out)
    R.write({"rewards": [cache("vr_new")]}, out)
    names = {p.stem for p in out.rglob("*") if p.is_file() and p.name != "pack.mcmeta"}
    assert names == {"vr_new"}


# Without it the committed caches are not all built, or the committed npc_grant leaks into the pack.
def test_the_committed_file_writes_one_pair_per_cache_and_none_for_its_grant(tmp_path):
    out = tmp_path / "cobblers_rewards"
    caches = sorted(r["id"] for r in CACHES)
    assert R.write(DOC, out) == len(caches)
    got = sorted(p.stem for p in (out / "data/cobblers/advancement/reward").iterdir())
    assert got == caches == sorted(p.stem for p in (out / "data/cobblers/function/reward").iterdir())
