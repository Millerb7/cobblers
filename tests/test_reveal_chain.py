"""The mainline reveal, beat by beat, played through the COMPILED dialogue (tools/compile_dialogue.py --all).

The owner (2026-10-05): "Wire all ten beats -- Pallet, the eight gyms, the League. Whatever Oak's quest does, do that
for each." Oak's chain is: an NPC seated where the beat happens (data/npc_seats.json, placed by tools/reapply.py R17N),
a conversation that opens on the right stage, and transitions that move the stage. This file checks that chain for
every beat by running the compiled Molang a click would run, not the data it was compiled from:

  the walk     tools/oak_starter_audit.py's Molang interpreter (parse, Run) runs each compiled dialogue's
               initializationAction, then each shown page's input or a chosen option's action; the commands those
               scripts send (tags, scores, the advancement probe the `flag` condition compiles to, openstarterscreen)
               are interpreted by Commands below. A command it does not know fails the test, so a new construct is
               never walked past silently.
  the badges   a badge is the progression flag's advancement plus its reward's carry (tools/progression_pack.py
               flag/<id>/granted -> flag/<id>/carry, a runmolang run here by the same interpreter).

Expectations come from the design, not from the compiler: the beat -> speaker table is ARC.md's (who tells each beat,
written out below), the completion stages and badges are data/quests.json beats[], the towns are where ARC.md puts
each beat. Not covered, and it needs a running server: that Cobblemon evaluates these scripts as this interpreter
does (EXP-022 proved the store; the advancement probe is the ferry's), and that the NPCs stand where their seats say
(tools/npc_seats.py verify).

Generator mutations run 2026-10-05 (tools/compile_dialogue.py edited, data untouched, then restored):
  transition() drops every effect on the main stage        20 failed (every beat, the hand-off, the League)
  the `flag` probe names cobblers:flag/<id>x               7 failed: test_a_badge_alone_opens_its_next_teller
                                                           [*-won_before_the_carry]
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

import compile_dialogue as CD  # noqa: E402
import oak_starter_audit as OA  # noqa: E402
import progression_pack as PP  # noqa: E402

DATA = ROOT / "data"


def _json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


QUEST = next(q for q in _json("quests.json")["quests"] if q["id"] == "main_worldshift_reveal")
FIELDS = {f["id"]: f for f in _json("progression.json")["quest_fields"]}
SEATS = {s["id"]: s for s in _json("npc_seats.json")["seats"]}
CONVS = {c["id"]: c for c in _json("dialogue.json")["conversations"]}
STAGE = "quest.main_worldshift_reveal.stage"
SKEY = CD.key(STAGE)
FILES, DONE, REFUSED = CD.build_all(DATA)
PACK = PP.files(PP.plan(PP.load(DATA / "progression.json"), placements=_json("placements.json")))
BEATS = {b["id"]: b for b in QUEST["beats"]}

# ARC.md: who tells each beat and where. The Rift surveyor is the hand-off into the Rift crisis (the finale's own
# conversations take it from rift_crisis_pending); the League steward closes the story after the finale.
TELLERS = {
    "pallet": (["dlg_main_pallet_oak", "dlg_main_pallet_mina", "dlg_main_pallet_oak", "dlg_main_pallet_maren"], "hometown"),
    "brock": (["dlg_main_brock_witness"], "gym1_town"),
    "misty": (["dlg_main_misty_relief_clerk"], "gym2_town"),
    "surge": (["dlg_main_surge_signal_clerk"], "gym3_town"),
    "erika": (["dlg_main_erika_survey_archivist"], "gym4_town"),
    "koga": (["dlg_main_koga_marsh_tracker"], "gym5_town"),
    "sabrina": (["dlg_main_sabrina_pattern"], "gym6_town"),
    "blaine": (["dlg_main_blaine_crater_analyst"], "gym7_town"),
    "giovanni": (["dlg_main_giovanni_watch"], "gym8_town"),
    "league": (["dlg_main_league_steward"], "league"),
}
HANDOFF = "dlg_main_rift_surveyor"          # giovanni_reveal_complete -> rift_crisis_pending
FINALE_READS = "rift_crisis_pending"        # the stage the finale's conversations open on
FINALE_GIVES = "rift_released"              # the stage the finale sets (unlock_league_after_rift_resolution)
ORDER = sorted(BEATS, key=lambda b: BEATS[b]["order"])


# ------------------------------------------------------------------------------------------------ the runtime
class Commands:
    """The server commands the compiled scripts send, as they act on one player."""

    PLAYER = r"(?:PLAYER-UUID|Player|@s)"

    def on_write(self, run, key, val):
        pass

    def command(self, w, cmd):
        cmd = cmd.strip()
        m = re.fullmatch(r"scoreboard objectives add (\S+) dummy", cmd)
        if m:
            w["objectives"].add(m.group(1))
            return 1
        m = re.fullmatch(r"tag %s (add|remove) (\S+)" % self.PLAYER, cmd)
        if m:
            (w["tags"].add if m.group(1) == "add" else w["tags"].discard)(m.group(2))
            return 1
        m = re.fullmatch(r"execute as %s (.*)" % self.PLAYER, cmd)
        if m:
            return self.sub(w, m.group(1))
        raise AssertionError("a command the walk does not model: %r" % cmd)

    def sub(self, w, rest):
        m = re.fullmatch(r"at @s (.*)", rest)
        if m:
            return self.sub(w, m.group(1))
        m = re.fullmatch(r"run function (\S+)", rest)
        if m:
            w["functions"].append(m.group(1))
            return 1
        m = re.fullmatch(r"run (.*)", rest)
        if m:
            return self.leaf(w, m.group(1))
        m = re.fullmatch(r"if entity @s\[advancements=\{cobblers:flag/([a-z0-9_]+)=true\}\] (.*)", rest)
        if m:
            return self.sub(w, m.group(2)) if m.group(1) in w["flags"] else None
        m = re.fullmatch(r"if score @s (\S+) matches (-?\d+) (.*)", rest)
        if m:
            return self.sub(w, m.group(3)) if w["scores"].get(m.group(1)) == int(m.group(2)) else None
        m = re.fullmatch(r"store result score @s (\S+) (.*)", rest)
        if m:
            r = self.sub(w, m.group(2))
            if r is not None and m.group(1) in w["objectives"]:
                w["scores"][m.group(1)] = r
            return r
        raise AssertionError("an execute the walk does not model: %r" % rest)

    def leaf(self, w, cmd):
        m = re.fullmatch(r"tag @s (add|remove) (\S+)", cmd)
        if m:
            (w["tags"].add if m.group(1) == "add" else w["tags"].discard)(m.group(2))
            return 1
        m = re.fullmatch(r"scoreboard players set @s (\S+) (-?\d+)", cmd)
        if m:
            if m.group(1) not in w["objectives"]:
                return None
            w["scores"][m.group(1)] = int(m.group(2))
            return 1
        if cmd == "openstarterscreen @s":
            # OpenStarterScreenCommand.kt @1.8.0 as tools/compile_dialogue.py relays it: 0 for a player who has chosen
            if w["chosen"]:
                return 0
            w["screen"] = True
            return 1
        raise AssertionError("a command the walk does not model: %r" % cmd)


CMDS = Commands()


def fresh():
    return {"data": {}, "tags": set(), "flags": set(), "scores": {}, "objectives": set(), "chosen": False,
            "screen": False, "functions": []}


def stage(w):
    v = w["data"].get(SKEY, 0.0)
    return FIELDS[STAGE]["initial"] if v == 0.0 else v


def dialogue(cid):
    return FILES["data/cobblers/dialogues/%s.json" % cid]


def talk(w, cid, answers=None):
    """One click on the NPC that opens `cid`, read to the end. `answers` {page: option value}; otherwise the first
    visible option. Returns the pages shown."""
    dlg = dialogue(cid)
    pages = {p["id"]: p for p in dlg["pages"]}
    r = OA.Run(w, CMDS)
    r.exec(dlg["initializationAction"])
    page, v, shown = (None if r.closed else r.page), r.v, []
    while page is not None:
        assert len(shown) < 64, "%s: no end after %s" % (cid, shown[-8:])
        assert page in pages, "%s sets page %r, which it does not have" % (cid, page)
        shown.append(page)
        inp = pages[page].get("input")
        if isinstance(inp, str):
            action = inp
        else:
            opts = [o for o in inp["options"]
                    if not o.get("isVisible") or OA.Run(w, CMDS, {}).truth(OA.Run(w, CMDS, {}).exec(o["isVisible"]))]
            want = (answers or {}).get(page)
            o = next(o for o in opts if want is None or o["value"] == want)
            action = o["action"]
        rr = OA.Run(w, CMDS, v)
        rr.exec(action)
        page = None if rr.closed else rr.page
    return shown


def pick_starter(w):
    """The player picks on Cobblemon's screen: the pack's starter_chosen callback runs."""
    assert w["screen"], "no starter screen was opened"
    w["chosen"] = True
    OA.Run(w, CMDS).exec(FILES[CD.STARTER_CALLBACK])


def win(w, flag, carry=True):
    """The leader's first win: the flag's advancement, then its reward (which runs the badge's carry). carry=False is
    a player who won before the carry shipped: the advancement only."""
    w["flags"].add(flag)
    for line in [] if not carry else PACK["data/cobblers/function/flag/%s/granted.mcfunction" % flag].splitlines():
        m = re.fullmatch(r"function cobblers:flag/([a-z0-9_]+)/carry", line)
        if m:
            text = PACK["data/cobblers/function/flag/%s/carry.mcfunction" % m.group(1)]
            (molang,) = [re.fullmatch(r'runmolang "(.*)" @s', l).group(1) for l in text.splitlines()
                         if l.strip() and not l.startswith("#")]
            OA.Run(w, CMDS).exec(molang)


def gym_of(beat):
    """The badge a beat's leader gives (beats[].world_change_flag); the League's is the Champion's."""
    return BEATS[beat].get("world_change_flag")


# ------------------------------------------------------------------------------------------------ the walk
def walk():
    """A fresh player plays the story in order: {beat: the player just before its teller is first spoken to}."""
    w, before = fresh(), {}
    before["pallet"] = copy.deepcopy(w)
    talk(w, "dlg_main_pallet_oak", {"oak_offer_002": "oak_offer_choose"})
    pick_starter(w)
    for cid in TELLERS["pallet"][0]:
        talk(w, cid)
    prev = "pallet"
    for beat in ORDER[1:-1]:
        flag = BEATS[beat].get("requires_existing_flag")
        if flag:
            win(w, flag)
        before[beat] = copy.deepcopy(w)
        for cid in TELLERS[beat][0]:
            talk(w, cid)
        prev = beat
    win(w, gym_of(prev))
    before["handoff"] = copy.deepcopy(w)
    talk(w, HANDOFF)
    before["finale"] = copy.deepcopy(w)
    return before, w


BEFORE, AFTER = walk()


def test_every_teller_conversation_compiles():
    want = {c for cids, _ in TELLERS.values() for c in cids} | {HANDOFF}
    assert not want & set(REFUSED), {c: REFUSED[c] for c in want & set(REFUSED)}
    assert want <= set(DONE)


@pytest.mark.parametrize("cid", sorted({c for cids, _ in TELLERS.values() for c in cids} | {HANDOFF}))
def test_every_teller_is_seated_with_a_class_that_opens_its_conversation(cid):
    npc = CONVS[cid]["npc_id"]
    assert npc in SEATS, "%s (%s) has no seat in data/npc_seats.json" % (npc, cid)
    assert SEATS[npc]["conversation"] == cid
    cls = FILES.get("data/cobblers/npcs/%s.json" % npc)
    assert cls, "no compiled NPC class %s" % npc
    assert cls["interaction"] == {"type": "dialogue", "dialogue": "cobblers:%s" % cid}


@pytest.mark.parametrize("beat", ORDER)
def test_each_teller_stands_in_its_beats_town(beat):
    cids, town = TELLERS[beat]
    for cid in cids:
        assert SEATS[CONVS[cid]["npc_id"]].get("settlement") == town, (cid, SEATS[CONVS[cid]["npc_id"]].get("settlement"))


def test_the_rift_handoff_stands_at_the_victory_road_trailhead():
    """No settlement: the surveyor's seat is within 20 blocks of Victory Road's trailhead gate G2 (3548, 5322),
    data/rift_zones.json's own record of it."""
    zones = json.dumps(_json("rift_zones.json"))
    assert "3548" in zones and "5322" in zones, "G2's trailhead (3548, 5322) is no longer in data/rift_zones.json"
    x, _y, z = SEATS[CONVS[HANDOFF]["npc_id"]]["at"]
    assert ((x - 3548) ** 2 + (z - 5322) ** 2) ** 0.5 <= 20


def test_a_fresh_player_gets_the_starter_from_oak_before_the_story_moves():
    w = fresh()
    talk(w, "dlg_main_pallet_oak", {"oak_offer_002": "oak_offer_choose"})
    assert w["screen"] and stage(w) == "not_started"


def test_the_walk_reaches_the_rift_crisis():
    assert stage(AFTER) == FINALE_READS


@pytest.mark.parametrize("beat", ORDER[:-1])
def test_each_beat_moves_the_stage_from_the_one_before_to_its_own(beat):
    w = copy.deepcopy(BEFORE[beat])
    i = ORDER.index(beat)
    was = "not_started" if i == 0 else BEATS[ORDER[i - 1]]["completion_stage"]
    assert stage(w) == was, "before %s the stage is %s, not %s" % (beat, stage(w), was)
    if beat == "pallet":
        # Oak's offer first: the story never moves for a player Cobblemon has not given a starter
        talk(w, "dlg_main_pallet_oak", {"oak_offer_002": "oak_offer_choose"})
        pick_starter(w)
        assert stage(w) == was
    for cid in TELLERS[beat][0]:
        talk(w, cid)
    assert stage(w) == BEATS[beat]["completion_stage"]


@pytest.mark.parametrize("beat", ORDER[2:-1])
def test_a_teller_spoken_to_out_of_turn_does_not_move_the_stage(beat):
    """Two beats back, no badge for this one: the teller says its locked line and the stage stays."""
    i = ORDER.index(beat)
    w = copy.deepcopy(BEFORE[ORDER[i - 1]])
    was = stage(w)
    shown = talk(w, TELLERS[beat][0][0])
    assert stage(w) == was
    assert shown and shown[0].endswith("_locked"), shown


@pytest.mark.parametrize("carry", [True, False], ids=["reward_carried", "won_before_the_carry"])
@pytest.mark.parametrize("beat", [b for b in ORDER[:-1] if BEATS[b].get("requires_existing_flag")])
def test_a_badge_alone_opens_its_next_teller(beat, carry):
    """A player who skipped every conversation but holds the badges up to this beat's own requirement hears it --
    whether the badge's reward carried the stage, or the badge was won before the carry existed and only the
    teller's own badge probe (the compiled `flag` condition) can carry it."""
    w = fresh()
    talk(w, "dlg_main_pallet_oak", {"oak_offer_002": "oak_offer_choose"})
    pick_starter(w)
    for b in ORDER[1:ORDER.index(beat)]:
        win(w, gym_of(b), carry)
    for cid in TELLERS[beat][0]:
        talk(w, cid)
    assert stage(w) == BEATS[beat]["completion_stage"]


def test_the_rift_surveyor_hands_the_player_to_the_finale():
    w = copy.deepcopy(BEFORE["handoff"])
    assert stage(w) == BEATS["giovanni"]["completion_stage"]
    talk(w, HANDOFF)
    assert stage(w) == FINALE_READS


def test_the_league_stays_shut_until_the_finale_releases_hoopa():
    w = copy.deepcopy(BEFORE["finale"])
    win(w, gym_of("league") or "champion_cleared")
    shown = talk(w, "dlg_main_league_steward")
    assert shown == ["league_locked"] and stage(w) == FINALE_READS


def test_the_league_recognises_the_player_once_the_finale_has_released_hoopa():
    """The finale's unlock_league_after_rift_resolution sets the stage and the steward's cursor; modelled here as its
    data says (it is the finale's to prove), then the steward is played compiled."""
    w = copy.deepcopy(BEFORE["finale"])
    t = next(t for t in QUEST["transitions"] if t["id"] == "unlock_league_after_rift_resolution")
    for e in t["effects"]:
        if e["kind"] == "set_progression":
            w["data"][CD.key(e["field"])] = e["value"]
    assert stage(w) == FINALE_GIVES
    talk(w, "dlg_main_league_steward")
    assert stage(w) == BEATS["league"]["completion_stage"]
