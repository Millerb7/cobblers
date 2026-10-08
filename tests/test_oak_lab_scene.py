"""Oak's lab scene and his League rules choice (the owner, 2026-10-06), through what the generators WRITE: the compiled
dialogue (tools/compile_dialogue.py) run on tools/oak_starter_audit.py's Molang interpreter, and the scene beat
(tools/scenes_pack.py). Builder's tests; the independent audit is docs/mechanics/OAK_AND_CHALLENGE.md "What an audit
must check". Validity, not behaviour: nobody has walked into the lab in game."""
from __future__ import annotations

import copy
import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402
import oak_starter_audit as OA  # noqa: E402
import scenes_pack as SP  # noqa: E402

DATA = ROOT / "data"
CONV = "dlg_main_pallet_oak"
MODE = "quest.main_worldshift_reveal.trainer_mode"
GREETED = "quest.main_worldshift_reveal.oak_greeted"
STAGE = "quest.main_worldshift_reveal.stage"
CM = json.loads((DATA / "challenge_mode.json").read_text(encoding="utf-8"))
SERIES, MODE_TAG = CM["series"]["id"], CM["mode"]["tag"]
FILES = CD.build(CONV, DATA)
DLG = FILES["data/cobblers/dialogues/%s.json" % CONV]
PAGES = {p["id"]: p for p in DLG["pages"]}
# The flag registry, read here rather than taken from the compiler: what a `function cobblers:flag/<id>/grant` call
# does is decided by tools/progression_pack.py, which writes that function (`advancement grant @s only
# cobblers:flag/<id>`) for a flag declared in data/progression.json whose set_by.kind is quest_transition, and for no
# other flag (tests/test_rift_crisis_resolved.py test_only_quest_transition_flags_get_a_grant_function).
FLAG_REGISTRY = {f["id"]: f for f in json.loads((DATA / "progression.json").read_text(encoding="utf-8"))["flags"]}


class Cmds:
    """The commands Oak's compiled scripts send, acting on one player; anything else fails the test."""

    P = r"(?:PLAYER-UUID|Player|@s)"
    flags = FLAG_REGISTRY

    def grant(self, w, fid):
        """A quest transition's `function` effect naming a flag's grant (compile_dialogue emits it as `execute as
        <player> at @s run function cobblers:flag/<id>/grant`). Judged on the registry, never on which line calls it:
        a flag that is undeclared, or is set by anything but a quest transition, has no grant function in the pack,
        and calling one is a failure. A held advancement granted again is a no-op (progression_pack's grant comment),
        so `granted` records every call and `flags` the state."""
        f = self.flags.get(fid)
        assert f is not None, "a grant of flag %r, which data/progression.json does not declare" % fid
        kind = (f.get("set_by") or {}).get("kind")
        assert kind == "quest_transition", (
            "a grant of flag %r, set by %r: tools/progression_pack.py writes flag/<id>/grant only for quest_transition"
            " flags, so this function does not exist" % (fid, kind))
        w["flags"].add(fid)
        w["granted"].append(fid)
        return 1

    def on_write(self, run, key, val):
        pass

    def command(self, w, cmd):
        cmd = cmd.strip()
        m = re.fullmatch(r"scoreboard objectives add (\S+) dummy", cmd)
        if m:
            w["objectives"].add(m.group(1))
            return 1
        m = re.fullmatch(r"tag %s (add|remove) (\S+)" % self.P, cmd)
        if m:
            (w["tags"].add if m.group(1) == "add" else w["tags"].discard)(m.group(2))
            return 1
        m = re.fullmatch(r"execute as %s (.*)" % self.P, cmd)
        assert m, "a command this model does not interpret: %r" % cmd
        return self.sub(w, m.group(1))

    def sub(self, w, rest):
        m = re.fullmatch(r"at @s (.*)", rest)
        if m:                                       # position only: nothing this model tracks depends on it
            return self.sub(w, m.group(1))
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
        raise AssertionError("an execute this model does not interpret: %r" % rest)

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
        m = re.fullmatch(r"rctmod player set series ([a-z0-9_]+) @s", cmd)
        if m:
            w["series"].append(m.group(1))           # every call: rctmod would wipe this player's progress
            return 1
        m = re.fullmatch(r"opendialogue cobblers:([a-z0-9_]+) @s", cmd)
        if m:
            w["opened"].append(m.group(1))
            return 1
        if cmd == "openstarterscreen @s":
            if w["chosen"]:
                return 0
            w["screen"] = True
            return 1
        m = re.fullmatch(r"function cobblers:flag/([a-z0-9_]+)/grant", cmd)
        if m:
            return self.grant(w, m.group(1))
        raise AssertionError("a command this model does not interpret: %r" % cmd)


CMDS = Cmds()


def fresh(**kw):
    w = {"data": {}, "tags": set(), "flags": set(), "scores": {}, "objectives": set(), "chosen": False,
         "screen": False, "series": [], "opened": [], "granted": []}
    w.update(kw)
    return w


def talk(w, answers=None, dlg=None, cmds=None):
    """One talk with Oak, read to the end; `answers` {page: option value, or a list taken in turn (the last repeats)},
    else the first visible option. `dlg` and `cmds` default to the real compiled dialogue and the model above."""
    dlg, cmds = dlg or DLG, cmds or CMDS
    pages = {p["id"]: p for p in dlg["pages"]}
    answers = {k: list(v) if isinstance(v, list) else [v] for k, v in (answers or {}).items()}
    r = OA.Run(w, cmds)
    r.exec(dlg["initializationAction"])
    page, v, shown, offered = (None if r.closed else r.page), r.v, [], {}
    while page is not None:
        assert len(shown) < 64, shown[-8:]
        shown.append(page)
        inp = pages[page].get("input")
        if isinstance(inp, str):
            action = inp
        else:
            opts = [o for o in inp["options"]
                    if not o.get("isVisible") or OA.Run(w, cmds, {}).truth(OA.Run(w, cmds, {}).exec(o["isVisible"]))]
            offered[page] = [o["value"] for o in opts]
            queue = answers.get(page)
            want = (queue.pop(0) if len(queue) > 1 else queue[0]) if queue else None
            action = next(o for o in opts if want is None or o["value"] == want)["action"]
        rr = OA.Run(w, cmds, v)
        rr.exec(action)
        page = None if rr.closed else rr.page
    return shown, offered


def pick(w):
    assert w["screen"]
    w["chosen"] = True
    OA.Run(w, CMDS).exec(FILES[CD.STARTER_CALLBACK])


def field(w, fid):
    return w["data"].get(CD.key(fid), 0.0)


def started(answers_mode=None):
    """A fresh player who took the offer and picked on Cobblemon's screen."""
    w = fresh()
    talk(w, {"oak_offer_002": "oak_offer_choose"})
    pick(w)
    return w


# ------------------------------------------------------------------------------------------------ the mode choice
# Without it the choice is offered before the starter (so a player without a partner decides how hard their gyms are
# blind) or after the send-off (when the story has already moved).
def test_the_rules_come_after_the_starter_and_before_the_send_off():
    w = started()
    shown, offered = talk(w, {"oak_mode_005": "oak_mode_pick_full", "oak_mode_confirm_full": "oak_mode_record_full"})
    assert shown[:5] == ["oak_mode_001", "oak_mode_002", "oak_mode_003", "oak_mode_004", "oak_mode_005"]
    assert shown.index("oak_mode_recorded_challenge") < shown.index("oak_003")
    assert field(w, STAGE) == "oak_sendoff"


def test_full_team_puts_the_player_in_the_challenge_series_once_and_tags_them():
    w = started()
    talk(w, {"oak_mode_005": "oak_mode_pick_full", "oak_mode_confirm_full": "oak_mode_record_full"})
    assert w["series"] == [SERIES]
    assert MODE_TAG in w["tags"]
    assert field(w, MODE) == "challenge"
    # every later talk, whatever is answered, never runs the series command again (each call wipes rctmod progress)
    for _ in range(4):
        talk(w)
    assert w["series"] == [SERIES]


def test_standard_runs_no_rctmod_command():
    w = started()
    shown, _ = talk(w, {"oak_mode_005": "oak_mode_pick_standard", "oak_mode_confirm_standard": "oak_mode_record_standard"})
    assert "oak_mode_recorded_normal" in shown
    assert w["series"] == [] and MODE_TAG not in w["tags"] and field(w, MODE) == "normal"


def test_let_me_think_closes_and_the_next_talk_explains_again():
    w = started()
    shown, _ = talk(w, {"oak_mode_005": "oak_mode_think"})
    assert shown[-1] == "oak_mode_005" and field(w, MODE) in (0.0, "unset") and w["series"] == []
    assert field(w, STAGE) in (0.0, "not_started")
    shown, _ = talk(w)
    assert shown[0] == "oak_mode_001"


# "Let me think" on the confirmation closes rather than looping back inside the talk: a page cycle inside one talk is
# what tools/oak_starter_audit.py's explorer cannot finish (every option path, exponentially, to its 64-page guard).
def test_let_me_think_on_the_confirmation_writes_nothing_and_starts_over():
    w = started()
    shown, _ = talk(w, {"oak_mode_005": "oak_mode_pick_full", "oak_mode_confirm_full": "oak_mode_back_full"})
    assert shown[-1] == "oak_mode_confirm_full" and field(w, MODE) in (0.0, "unset") and w["series"] == []
    assert talk(w)[0][0] == "oak_mode_001"


def test_no_page_cycle_inside_one_talk():
    conv = next(c for c in json.loads((DATA / "dialogue.json").read_text(encoding="utf-8"))["conversations"]
                if c["id"] == CONV)
    edges = {}
    for n in conv["nodes"]:
        if n["kind"] == "line":
            if n["next"] != n["id"]:
                edges.setdefault(n["id"], set()).add(n["next"])
        else:
            for r in n["responses"]:
                closes = any(a["kind"] in ("close_dialogue", "open_starter_screen") for a in r.get("actions") or [])
                if r.get("next") and not closes:
                    edges.setdefault(n["id"], set()).add(r["next"])
    state = {}

    def visit(u, path):
        state[u] = 1
        for v in edges.get(u, ()):
            assert state.get(v) != 1, "a cycle inside one talk: %s" % (path + [v])
            if v not in state:
                visit(v, path + [v])
        state[u] = 2
    for n in edges:
        if n not in state:
            visit(n, [n])


# Without it a player who already beat Brock is offered Full-Team, and the series command wipes their progress: the
# cap falls back to 20 and every leader refuses their party (RCT_PER_PLAYER_MODE.md section 1, consequences).
def test_full_team_is_not_offered_to_a_badge_holder_and_cannot_be_recorded_by_one():
    w = started()
    w["flags"].add("gym1_cleared")
    _shown, offered = talk(w, {"oak_mode_005": "oak_mode_think"})
    assert "oak_mode_pick_full" not in offered["oak_mode_005"]
    # and the transition itself refuses, should the page be reached anyway
    tr = next(o for o in PAGES["oak_mode_confirm_full"]["input"]["options"] if o["value"] == "oak_mode_record_full")
    OA.Run(w, CMDS, {}).exec("t.d = q.player.data(); " + tr["action"].split("t.d = q.player.data(); ", 1)[1])
    assert w["series"] == [] and field(w, MODE) in (0.0, "unset")


def test_a_player_whose_mode_is_recorded_never_sees_the_choice():
    w = started()
    talk(w, {"oak_mode_005": "oak_mode_pick_standard", "oak_mode_confirm_standard": "oak_mode_record_standard"})
    for cur in ["oak_mode_001", "oak_mode_005", "oak_mode_confirm_full", "oak_offer_001"]:
        v = copy.deepcopy(w)
        v["data"][CD.key("quest.main_worldshift_reveal.pallet_oak_cursor")] = cur
        shown, _ = talk(v)
        assert not [p for p in shown if p.startswith("oak_mode_0") or p.startswith("oak_mode_confirm")], (cur, shown)


# The owner: "the difference explained without the words easy and hard".
def test_oaks_rules_never_say_easy_or_hard():
    conv = next(c for c in json.loads((DATA / "dialogue.json").read_text(encoding="utf-8"))["conversations"]
                if c["id"] == CONV)
    text = " ".join([n["text"] for n in conv["nodes"] if n["id"].startswith("oak_mode")] +
                    [r["text"] for n in conv["nodes"] if n["id"].startswith("oak_mode") for r in n.get("responses", [])])
    assert not re.search(r"\b(easy|easier|easiest|hard|harder|hardest|difficult|difficulty)\b", text, re.I), text
    assert "Standard rules" in text and "Full-Team rules" in text


def test_the_compiler_refuses_a_series_command_without_its_lock():
    dialogue, quests, fields = CD.load(DATA)
    q = copy.deepcopy(quests["main_worldshift_reveal"])
    t = next(t for t in q["transitions"] if t["id"] == "record_trainer_mode_challenge")
    t["conditions"] = [c for c in t["conditions"] if c.get("field") != MODE]
    conv = next(c for c in dialogue["conversations"] if c["id"] == CONV)
    with pytest.raises(SystemExit):
        CD.compile_conversation(conv, dict(quests, main_worldshift_reveal=q), fields, DATA)


# ------------------------------------------------------------------------------------------------ the bird hint
# Test author, unit WAY review (2026-10-08): `oak_birds` is the sapling hint (birds nest in the great trees), placed
# after the send-off so every player who leaves Pallet hears it. Checked through the compiled dialogue.
STANDARD = {"oak_mode_005": "oak_mode_pick_standard", "oak_mode_confirm_standard": "oak_mode_record_standard"}


# Without it a re-wire of the send-off can orphan the hint (a dead node) with every other test still green.
def test_the_bird_hint_follows_the_send_off_in_the_same_talk():
    w = started()
    shown, _ = talk(w, STANDARD)
    assert shown[shown.index("oak_003") + 1] == "oak_birds", shown
    assert field(w, STAGE) == "oak_sendoff"


# Without it the hint could become the repeat line (heard on every talk) or loop inside one talk.
def test_the_bird_hint_is_heard_once_and_later_talks_give_the_repeat_line():
    w = started()
    heard = talk(w, STANDARD)[0]
    for _ in range(4):
        heard += talk(w)[0]
    assert heard.count("oak_birds") == 1, heard
    assert talk(w)[0] == ["oak_repeat_before_mismatch"]


# ------------------------------------------------------------------------------------------------ a flag grant
# The model's grant rule, exercised through what the compiler EMITS for a `function` effect on the send-off. The flag
# is synthetic (added to a copy of the registry), so these say nothing about any authored flag: they prove the model
# judges a grant by the registry, not by which line makes it. Without them the rule above could accept any function.
def _sendoff_granting(flag):
    dialogue, quests, fields = CD.load(DATA)
    q = copy.deepcopy(quests["main_worldshift_reveal"])
    t = next(t for t in q["transitions"] if t["id"] == "record_oak_sendoff")
    t["effects"].insert(0, {"kind": "function", "function": "cobblers:flag/%s/grant" % flag})
    conv = next(c for c in dialogue["conversations"] if c["id"] == CONV)
    return CD.compile_conversation(conv, dict(quests, main_worldshift_reveal=q), fields, DATA)[
        "data/cobblers/dialogues/%s.json" % CONV]


class _Registry(Cmds):
    def __init__(self, extra):
        self.flags = dict(FLAG_REGISTRY, **extra)


PROBE = {"id": "probe_sendoff", "set_by": {"kind": "quest_transition", "quest": "main_worldshift_reveal",
                                           "transition": "record_oak_sendoff"}}


def test_a_send_off_granting_a_quest_transition_flag_holds_it_once():
    cmds, dlg = _Registry({PROBE["id"]: PROBE}), _sendoff_granting(PROBE["id"])
    w = fresh()
    talk(w, {"oak_offer_002": "oak_offer_choose"}, dlg, cmds)
    pick(w)
    talk(w, STANDARD, dlg, cmds)
    assert PROBE["id"] in w["flags"] and field(w, STAGE) == "oak_sendoff"
    for _ in range(3):
        talk(w, None, dlg, cmds)
    assert w["granted"].count(PROBE["id"]) == 1     # the transition's stage guard: never run twice


@pytest.mark.parametrize("flag,why", [("probe_undeclared", "does not declare"), ("gym1_cleared", "quest_transition")])
def test_a_grant_the_progression_pack_does_not_write_fails(flag, why):
    assert flag == "probe_undeclared" or FLAG_REGISTRY[flag]["set_by"]["kind"] != "quest_transition"
    dlg = _sendoff_granting(flag)
    w = fresh()
    talk(w, {"oak_offer_002": "oak_offer_choose"}, dlg)
    pick(w)
    with pytest.raises(AssertionError, match=why):
        talk(w, STANDARD, dlg)


# ------------------------------------------------------------------------------------------------ the scene
SCENES ={s["id"]: s for s in json.loads((DATA / "scenes.json").read_text(encoding="utf-8"))["scenes"]}
SCENE = SCENES["oak_lab"]
SEATS = {s["id"]: s for s in json.loads((DATA / "npc_seats.json").read_text(encoding="utf-8"))["seats"]}
LAB = ROOT / "kits" / "structures" / "campaign" / "f4" / "pallet" / "rare_structures" / "lab.nbt"
ORIGIN = (1487, 117, 5309)        # data/placements.json hometown_oaks_lab, floor y117 (data/npc_seats.json)


def _beat():
    files, _s = SP.build(DATA)
    return files


def test_the_scene_area_holds_the_spawn_the_lab_and_oak():
    oak = SEATS["npc_main_pallet_oak"]["at"]
    assert SP.inside(oak, SCENE["area"])
    assert SP.inside([1461, 118, 5306], SCENE["area"]), "the world spawn (cobblers_towns towns/hometown setworldspawn)"
    z = SCENE["zones"][0]
    assert z["transitions"] == ["greet_in_lab"]


def test_walking_into_the_lab_opens_oaks_conversation_once():
    files = _beat()
    beat = files["data/cobblers/function/scenes/oak_lab/beat.mcfunction"]
    zone = [l for l in beat if "opendialogue" in l]
    assert len(zone) == 1
    m = re.fullmatch(r'execute if entity @s\[[^\]]+\] run runmolang "(.*)" @s', zone[0])
    mol = m.group(1)
    w = fresh()
    for _ in range(3):                          # three cycles standing in the lab
        OA.Run(w, CMDS).exec(mol)
    assert w["opened"] == [CONV]
    # a player already sent off is never greeted
    w2 = fresh()
    w2["data"][CD.key(STAGE)] = "oak_sendoff"
    OA.Run(w2, CMDS).exec(mol)
    assert w2["opened"] == []


def test_the_six_starters_stand_until_the_player_has_chosen():
    want = {"cosmog", "kubfu", "typenull", "poipole", "meltan", "larvesta"}
    assert {a["species"] for a in SCENE["actors"]} == want == OA.STARTERS
    for a in SCENE["actors"]:
        assert a["place"] == [{"when": {"kind": "not", "condition": {"kind": "starter_chosen"}}, "marker": "starter_" + a["id"]}]
        assert a["conversation"] == "dlg_main_pallet_lab_starter"


@pytest.mark.skipif(not LAB.is_file(), reason="kits not hydrated (python tools/local_inputs.py hydrate)")
def test_every_starter_marker_is_standable_in_the_lab_template():
    import nbt
    _, doc = nbt.loads(LAB.read_bytes())
    pal = doc.get("palette") if doc.get("palette") is not None else doc["palettes"][0]
    names = [p.get("Name") for p in pal]
    cells = {tuple(int(v) for v in b["pos"]): names[b["state"]] for b in doc["blocks"]}
    air = lambda c: cells.get(c, "minecraft:air") in ("minecraft:air", "minecraft:cave_air")
    for name, mk in SCENE["markers"].items():
        x, y, z = mk["at"]
        for ox, oz in mk["slots"]:
            # the copy stands at the block centre plus its slot (tools/scenes_pack.py actor): the block it is in
            lx = math.floor(x + 0.5 + ox) - ORIGIN[0]
            ly = y - ORIGIN[1]
            lz = math.floor(z + 0.5 + oz) - ORIGIN[2]
            assert air((lx, ly, lz)) and air((lx, ly + 1, lz)), (name, (lx, ly, lz), cells.get((lx, ly, lz)))
            assert not air((lx, ly - 1, lz)), (name, "nothing under", (lx, ly - 1, lz))


def test_no_two_starters_share_a_block_and_every_stand_is_on_the_heightmap_floor():
    # Without it a seventh (or a moved sixth) stand can put two copies in one block, and the player clicks the wrong
    # starter; or a stand can float or sink against the lab floor the heightmap and the template agree on (y117).
    import ground
    owner = {}
    try:
        g = ground.load()
    except (OSError, SystemExit) as e:
        pytest.skip("canonical heightmap unavailable: %s" % e)
    stands = {n: m for n, m in SCENE["markers"].items() if n.startswith("starter_")}
    assert set(stands) == {"starter_" + s for s in OA.STARTERS}
    for name, mk in stands.items():
        x, y, z = mk["at"]
        # the floor under every stand is the ground (tools/ground.py, rounded), not a world read
        assert y - 1 == ORIGIN[1] == round(g(x, z)), (name, y, round(g(x, z)))
        for ox, oz in mk["slots"]:
            # tools/scenes_pack.py: the copy stands at the block centre plus its slot
            cell = (math.floor(x + 0.5 + ox), math.floor(z + 0.5 + oz))
            assert owner.setdefault(cell, name) == name, (cell, owner[cell], name)


def test_the_hint_shows_only_to_a_player_without_a_starter():
    e = SCENE["effects"][0]
    assert e["kind"] == "actionbar" and e["when"] == {"kind": "not", "condition": {"kind": "starter_chosen"}}
    files = _beat()
    assert files["data/cobblers/function/scenes/oak_lab/fx/oak_is_waiting.mcfunction"][-1].startswith("title @s actionbar ")
