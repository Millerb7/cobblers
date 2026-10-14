"""tools/player_waystone.py and Oak's gift: a player's own waystone, once, with every other way to make one closed
(data/player_waystone.json; the owner, 2026-10-09).

Builder's tests (written with the generator); the independent audit is another agent's. The gift is run through the
compiled dialogue on tests/test_oak_lab_scene.py's command model (tools/oak_starter_audit.py's Molang interpreter),
not read off the data. The closed list is checked against the Waystones jar when the server snapshot is present; those
checks SKIP without it, and a skip is not a pass.

What none of this covers: that the server skips a recipe file holding only `fabric:load_conditions` (read from Fabric
API's source for tools/key_ball.py, never run), that the give lands in a real inventory, that breaking a placed
waystone drops the item (the loot table is read from the jar, not run), and what another player sees at a waystone
placed by the first. Marked in data/player_waystone.json and in docs/STATE.md.
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
sys.path.insert(0, str(ROOT / "tests"))

import player_waystone as PW  # noqa: E402
import test_oak_lab_scene as T  # noqa: E402

DOC = PW.load()
GIFT = DOC["gift"]
CLAIM = GIFT["claim_field"]
CARD = ("rctmod:trainer_card", 1)                       # Oak's second gift (ECONOMY_V2 E9, 2026-10-13)
CARD_CLAIM = "quest.main_worldshift_reveal.trainer_card_claimed"
JAR = PW.find_jar()
NEED_JAR = pytest.mark.skipif(JAR is None, reason="the server snapshot's Waystones jar is not on this machine")
CFG = ROOT / "base-pack" / "cobbleverse" / "config" / "waystones-common.toml"


# ---------------------------------------------------------------------------------------------------- the closed list
@NEED_JAR
def test_the_closed_list_is_exactly_what_the_jar_ships():
    # Without it a waystone, sharestone, portstone or warp item the jar ships stays craftable and a player can make a
    # second waystone, or fast travel, past Oak's one.
    assert PW.problems(DOC, JAR) == []
    rec, adv = PW.jar_ids(JAR)
    assert rec == set(DOC["recipe_off"]["recipes"]) and adv == set(DOC["recipe_off"]["advancements"])
    assert len(rec) == 54


@NEED_JAR
def test_every_item_a_player_could_place_or_warp_with_is_a_closed_recipe_result():
    # Read from the jar's recipes, not from our list: every result of a closed recipe, and nothing the jar can make
    # that is not closed.
    import zipfile
    z = zipfile.ZipFile(JAR)
    results = set()
    for n in z.namelist():
        if re.fullmatch(r"data/[^/]+/recipe/.+\.json", n) and z.read(n).strip():
            r = json.loads(z.read(n).decode("utf-8-sig"))["result"]
            results.add(r if isinstance(r, str) else r.get("id"))
    closed = {("waystones:" + p.split("/")[-1][:-5]) for p in PW.closed(DOC) if "/recipe/" in p}
    made_by_closed = set()
    for rid in DOC["recipe_off"]["recipes"]:
        r = json.loads(z.read("data/waystones/recipe/%s.json" % rid.split(":")[1]).decode("utf-8-sig"))["result"]
        made_by_closed.add(r if isinstance(r, str) else r["id"])
    assert results == made_by_closed
    for must in ("waystone", "mossy_waystone", "sandy_waystone", "warp_plate", "warp_stone", "warp_scroll",
                 "return_scroll", "portal_scroll", "twinbound_feather", "epitaph", "red_sharestone", "red_portstone"):
        assert "waystones:" + must in results, must
    assert closed == set(DOC["recipe_off"]["recipes"])


def test_the_pack_holds_only_load_conditions_that_never_pass_and_no_function_or_loot_table():
    # Without it a closed file could carry a result and re-open the recipe, or the pack could override the mod's loot
    # table and lose the pickup on break.
    files = PW.build(DOC, JAR)
    body = json.loads(next(v for k, v in files.items() if "/recipe/waystone.json" in k))
    assert body == {"fabric:load_conditions": [PW.NEVER]}
    assert len(files) == 1 + 2 * 54
    for path, text in files.items():
        if path == "pack.mcmeta":
            continue
        assert re.fullmatch(r"data/waystones/(recipe|advancement/recipes)/[a-z_/]+\.json", path), path
        assert json.loads(text) == {"fabric:load_conditions": [PW.NEVER]}, path
    assert not any("loot" in p or "function" in p or "tags" in p for p in files)


def test_the_gifts_own_recipe_must_be_closed():
    bad = copy.deepcopy(DOC)
    bad["recipe_off"]["recipes"].remove("waystones:waystone")
    assert any("would stay craftable" in p for p in PW.problems(bad))


def test_a_condition_that_can_pass_is_refused():
    bad = copy.deepcopy(DOC)
    bad["recipe_off"]["condition"] = {"condition": "fabric:true"}
    assert PW.problems(bad)


@NEED_JAR
def test_a_recipe_the_jar_ships_and_the_list_misses_is_found():
    bad = copy.deepcopy(DOC)
    bad["recipe_off"]["recipes"].remove("waystones:warp_stone")
    assert any("warp_stone" in p for p in PW.problems(bad, JAR))


def test_the_gift_records_agree_and_a_broken_one_is_found():
    assert PW.problems(DOC) == []
    quests = json.loads((ROOT / "data" / "quests.json").read_text(encoding="utf-8"))["quests"]
    q = next(x for x in quests if x["id"] == GIFT["quest"])
    t = next(x for x in q["transitions"] if x["id"] == GIFT["transition"])
    g = next(e for e in t["effects"] if e["kind"] == "grant_reward_once")
    assert g["reward"] == "reward_" + GIFT["reward"] and g["claim_field"] == CLAIM
    assert g["idempotency_key"].endswith("{player_uuid}")
    bad = copy.deepcopy(DOC)
    bad["gift"]["reward"] = "oak_something_else"
    assert PW.problems(bad)


# ----------------------------------------------------------------------------------------------- Oak gives it, once
def sent_off():
    """A player who has taken the starter and is about to answer the League rules: the world and the answers."""
    return T.started(), T.STANDARD


def test_a_new_player_is_given_exactly_one_waystone_in_the_send_off_talk():
    # Without it the gift is on a line nobody reaches, or is given on every talk.
    w, answers = sent_off()
    shown, _ = T.talk(w, answers)
    assert shown.index("oak_waystone_002") == shown.index("oak_birds") + 2
    # ECONOMY_V2 E9 (2026-10-13): Oak then gives the trainer card in the same talk, straight after the waystone
    assert shown[shown.index("oak_waystone_002") + 1:shown.index("oak_waystone_002") + 3] == ["oak_card_001", "oak_card_002"]
    assert w["gave"] == [(GIFT["item"], GIFT["count"]), CARD]
    assert T.field(w, CLAIM) == 1 and T.field(w, CARD_CLAIM) == 1
    assert T.field(w, T.STAGE) == "oak_sendoff"
    for _ in range(4):
        T.talk(w)
    assert w["gave"] == [(GIFT["item"], GIFT["count"]), CARD], "a later talk gave another"


def test_a_player_who_has_not_chosen_a_starter_is_given_nothing():
    w = T.fresh()
    for _ in range(3):
        T.talk(w)
    assert w["gave"] == [] and T.field(w, CLAIM) == 0


def test_a_failed_give_writes_no_claim_so_the_next_talk_retries():
    # The compiler writes the claim only when every give reported success (tools/compile_dialogue.py grant_reward_once)
    class Refusing(T.Cmds):
        def leaf(self, w, cmd):
            if cmd.startswith("give @s "):
                return None
            return super().leaf(w, cmd)

    w, answers = sent_off()
    T.talk(w, answers, cmds=Refusing())
    assert w["gave"] == [] and T.field(w, CLAIM) == 0
    T.talk(w)                                  # the same player, a working give: the next talk finishes the grant
    assert (GIFT["item"], GIFT["count"]) in w["gave"] and T.field(w, CLAIM) == 1


def _old_player(cursor, stage):
    """A player Oak sent off before the gift shipped: the starter chosen, the rules recorded, no claim."""
    w, answers = sent_off()
    T.talk(w, answers)
    w["gave"].clear()
    w["data"][T.CD.key(CLAIM)] = 0.0
    w["data"][T.CD.key("quest.main_worldshift_reveal.pallet_oak_cursor")] = cursor
    w["data"][T.CD.key(T.STAGE)] = stage
    return w


def test_a_player_sent_off_before_it_shipped_is_offered_it_once_on_their_next_talk():
    w = _old_player("oak_repeat_before_mismatch", "oak_sendoff")
    shown, _ = T.talk(w)
    assert shown[:2] == ["oak_waystone_001", "oak_waystone_002"], shown
    assert w["gave"] == [(GIFT["item"], GIFT["count"])] and T.field(w, CLAIM) == 1
    shown, _ = T.talk(w)
    assert "oak_waystone_001" not in shown and len(w["gave"]) == 1


def test_a_player_past_the_boundary_is_offered_it_in_one_line_and_goes_back_to_their_own_repeat():
    w = _old_player("oak_repeat_after_mismatch", "oak_admitted")
    shown, _ = T.talk(w)
    assert shown == ["oak_waystone_late", "oak_repeat_after_mismatch"], shown
    assert w["gave"] == [(GIFT["item"], GIFT["count"])]
    shown, _ = T.talk(w)
    assert shown == ["oak_repeat_after_mismatch"] and len(w["gave"]) == 1


def _no_card_player(cursor, stage):
    """A player Oak sent off before the card shipped: the waystone claimed, the card not."""
    w = _old_player(cursor, stage)
    w["data"][T.CD.key(CLAIM)] = 1.0
    w["data"][T.CD.key(CARD_CLAIM)] = 0.0
    return w


def test_a_player_without_the_card_is_given_it_once_before_and_after_the_boundary():
    # ECONOMY_V2 E9: without the two entry rules (priorities 8 and 9) a player Oak already sent off never gets the card
    for cursor, stage, node in (("oak_repeat_before_mismatch", "oak_sendoff", "oak_card_late_before"),
                                ("oak_repeat_after_mismatch", "oak_admitted", "oak_card_late")):
        w = _no_card_player(cursor, stage)
        shown, _ = T.talk(w)
        assert shown[0] == node and w["gave"] == [CARD] and T.field(w, CARD_CLAIM) == 1, (node, shown, w["gave"])
        T.talk(w)
        assert w["gave"] == [CARD], "a second talk gave another card"


def test_a_failed_card_give_writes_no_claim_so_the_next_talk_retries():
    class Refusing(T.Cmds):
        def leaf(self, w, cmd):
            if cmd.startswith("give @s "):
                return None
            return super().leaf(w, cmd)

    w = _no_card_player("oak_repeat_before_mismatch", "oak_sendoff")
    T.talk(w, cmds=Refusing())
    assert w["gave"] == [] and T.field(w, CARD_CLAIM) == 0
    T.talk(w)
    assert w["gave"] == [CARD] and T.field(w, CARD_CLAIM) == 1


# ------------------------------------------------------------------------------------ the config this rests on
def _toml(key):
    m = re.search(r"^\s*%s\s*=\s*(.+?)\s*$" % re.escape(key), CFG.read_text(encoding="utf-8"), re.M)
    assert m, key
    return m.group(1)


def test_the_config_facts_data_player_waystone_json_states_are_the_files():
    # Without it the report on cost, visibility and restriction goes stale the day the config changes.
    assert _toml("enableCosts") == "false" and _toml("enableCooldowns") == "false"
    assert _toml("restrictedWaystones").replace(" ", "") == '["PLAYER"]'
    assert _toml("defaultVisibility") == '"ACTIVATION"'
    assert _toml("allowedVisibilities").replace(" ", "") == "[]"
    assert _toml("inventoryButton") == '""'


def test_no_overlay_of_the_waystones_config_exists_so_the_base_packs_is_what_runs():
    for d in ("modpack/config", "server/config"):
        assert not list((ROOT / d).rglob("waystones*.toml")), d


# ------------------------------------------------------------------------------------------------- the registration
def test_the_pack_is_registered_world_local_with_a_reason():
    import reapply
    assert "cobblers_player_waystone" in reapply.SERVER_PACKS
    assert "cobblers_player_waystone" in reapply.WORLD_LOCAL
    assert reapply.EXCLUDED["cobblers_player_waystone"].startswith("load-time only")
