#!/usr/bin/env python
"""Compile a campaign conversation (data/dialogue.json + data/quests.json + data/progression.json) into native Cobblemon 1.8 dialogue.

Output (build/datapacks/cobblers_dialogue, generated, not committed):
  data/cobblers/dialogues/<conversation id>.json   one page per node
  data/cobblers/npcs/<npc id>.json                 an NPC class whose interaction opens that dialogue
  data/cobblemon/callbacks/starter_chosen/...      only when a conversation offers the starter screen (see "starter")
  placement.txt                                    only with --place X Y Z: the spawnnpcat command for a test position (not
                                                   a decision). Not a function: NPC classes load only at server start and
                                                   functions are parsed first, so a function naming the class fails to load.

The runtime pieces, each proven on the disposable world before this compiler relied on it (EXP-022):
  state      q.player.data() + q.player.save_data(): per-player NBT in <world>/playermolangdata, strings and numbers.
             A quest field "quest.<quest>.<field>" is the key cobblers__quest__<quest>__<field>; booleans are 1/0, an
             unset key reads 0 (= false, or the initial node for the cursor).
  cursor     persisted before the next page is shown; the dialogue's initializationAction evaluates the entry rules
             and calls q.dialogue.set_page, so a reopened conversation lands on the stored node.
  items      q.run_command runs as the server (q.player.run_command would need the player to be an operator). Held-item
             checks run `execute as <uuid> if items entity @s weapon.mainhand <predicate> run tag @s add <tag>` and read
             q.player.has_tag; inside a dialogue action the command takes effect before the next statement.
             Consumption is `item replace ... with minecraft:air` under the same predicate, in the same action.
  rewards    grant_reward_once gives the verified contents and sets its claim field in one action, guarded by that field.

  scenes     two effects reach the scene runtime (tools/scenes_pack.py, data/scenes.json): sync_scene runs the scene's
             per-player beat for this player at once, so an actor moves on the click that moved its checkpoint rather
             than up to a second later; scene_function runs one of the scene's named functions as the player (a flash,
             a controlled encounter). Both are server-sourced commands like every other.
  flags      a condition {"kind": "flag", "flag": "<id>"} holds when the player has the progression flag's advancement
             (cobblers:flag/<id>, tools/progression_pack.py). Advancements are not in q.player.data(), so it is probed as
             the held items are: `execute as <uuid> if entity @s[advancements={...=true}] run tag @s add <tag>`, then
             q.player.has_tag, in the same action (first used by the ferry, tools/ferries.py, 2026-09-27).
  player_tag a condition {"kind": "player_tag", "tag": "<tag>"} holds when the player carries that scoreboard tag,
             read with q.player.has_tag like every probe here. Nothing in the dialogue sets it: another pack keeps it
             (the first, tools/lopunny_house.py: a player_tick_pre callback tags a player with a Lopunny in the party,
             the party read the water ladder proved, EXP-042). End to end it is experiments/EXP-052-lopunny-show.
  functions  an effect {"kind": "function", "function": "cobblers:<path>"} runs that function as and at the player, like
             scene_function but for a function a generated pack owns (the ferry's trips).
  battles    a conversation with "npc_battle": {"trainers": <data file>, "trainer": <id>, "skill": n} gives its NPC's
             class a `simple` party of that record's team (battle_class()), and a response action {"kind":
             "npc_battle"} closes the dialogue and starts the NPC's battle against the talking player, as Cobblemon's own
             dialogues/npc-example.json does. The result is read elsewhere, by a battle_victory callback (the finale's:
             tools/hq_tower.py). First used 2026-10-04 by Brann and Elara in the HQ tower; NOT yet run in game.
  starter    a response action {"kind": "open_starter_screen"} (its response's only action) runs Cobblemon's own
             `openstarterscreen <player>` for the talking player (Oak's first conversation, the owner's priority zero,
             2026-10-05). Read from OpenStarterScreenCommand.kt @1.8.0: permission level 2; a player who has already
             chosen gets nothing and the command returns 0; anyone else is unlocked, marked prompted, saved and sent
             the starter list, and it returns 1. The result goes to a score preset to -1 (so a command that never ran
             cannot read as 0); 0 tags the player STARTER_TAG and shows the response's `next`, anything else closes
             the dialogue so the screen stays up (the client's DialogueClosedHandler only closes a DialogueScreen).
             One starter per player is Cobblemon's own guarantee (chooseStarter refuses a second pick,
             docs/research/notes/starter-selection.md section 5); nothing here gives a Pokemon. A condition
             {"kind": "starter_chosen"} reads STARTER_TAG, which the pack's starter_chosen callback
             (CallbackHandler.kt @1.8.0: STARTER_CHOSEN -> cobblemon:starter_chosen, context `player`, the struct
             player_tick_pre's proven callbacks read) adds the moment a pick is made. NOT yet run in game.
  opened by  a conversation with "npc_id": null has no NPC class: a prop or an actor opens it (the scene runtime runs
             /opendialogue for the player who clicked), never an NPC's interaction.
  speakers   a conversation may name its speakers ("speakers": {"pip": "Pip", "narration": null}); a speaker mapped to
             null is narration and its page names no speaker. Without the map, the id is title-cased as before.
  initial    a condition on an enum field's declared initial value also matches the unset key (0), as the cursor's did.
  model      every class names "resourceIdentifier": NPC_RESOURCE. The client renders an NPC by the entity's synced
             resource identifier, which is the class's resourceIdentifier and, when the class gives none, THE CLASS ID
             (Cobblemon 1.8.0 NPCClasses reload: path "dummy" -> id). No client variation is named cobblers:<npc id>, so
             without the field every one of our NPCs fell to the green substitute doll (2026-10-02, Hollis).
             cobblemon:standard is Cobblemon's own variation (bedrock/npcs/variations/standard/0_standard_base.json):
             trainer.geo, textures/npcs/standard/trainer.png, poser standard. Checked by tools/npc_model_audit.py.

Only the constructs listed here are supported; anything else stops compilation rather than guessing.

  python tools/compile_dialogue.py dlg_route1_thirsty_stranger [--out DIR] [--place X Y Z]
  python tools/compile_dialogue.py --all [--out DIR]    every conversation that compiles; each refusal is listed with why
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_dialogue"
NS = "cobblers"
# The client variation every NPC class renders as (see "model" above). Shipped in the Cobblemon jar itself, so the
# fix is server-side data and no client needs a new pack.
NPC_RESOURCE = "cobblemon:standard"


class Unsupported(SystemExit):
    pass


def key(field):
    return "cobblers__" + field.replace(".", "__")


def lit(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        if not re.fullmatch(r"[A-Za-z0-9_.:\-]*", v):
            raise Unsupported("string value %r needs escaping the compiler does not do" % v)
        return "'%s'" % v
    raise Unsupported("value %r" % (v,))


def run(cmd_parts):
    """A server-sourced command whose text mixes literals and the player's uuid: ['execute as ', UUID, ' if ...']."""
    return "q.run_command(%s);" % " + ".join("q.player.uuid" if p is UUID else "'%s'" % p.replace("'", "\\'") for p in cmd_parts)


UUID = object()


def ident(v):
    """A scene or function id, which becomes part of a function path."""
    if not isinstance(v, str) or not re.fullmatch(r"[a-z0-9_]+", v):
        raise Unsupported("id %r is not [a-z0-9_]+" % (v,))
    return v


def function_id(v):
    """A function in our own namespace, run by the `function` effect."""
    if not isinstance(v, str) or not re.fullmatch(r"%s:[a-z0-9_]+(/[a-z0-9_]+)*" % NS, v):
        raise Unsupported("function %r is not %s:<path> of [a-z0-9_/]" % (v, NS))
    return v
TX_SCORE = "cobblers_tx"
GIVE_FAILED = "cobblers_give_failed"
# the starter gate (see "starter" above): the tag a player carries once Cobblemon has given them their starter, the
# score openstarterscreen's result is stored in, and the callback that tags a pick as it is made
STARTER_TAG = "cobblers_starter_chosen"
STARTER_SCORE = "cobblers_starter"
STARTER_CALLBACK = "data/cobblemon/callbacks/starter_chosen/cobblers_starter_chosen.molang"


class Compiler:
    def __init__(self, conv, quest, fields):
        self.conv, self.quest, self.fields = conv, quest, fields
        self.nodes = {n["id"]: n for n in conv["nodes"]}
        self.transitions = {t["id"]: t for t in quest["transitions"]}
        self.rewards = {r["id"]: r for r in quest.get("rewards") or []}
        self.cursor = conv["cursor"]["progression_field"]
        self.initial = conv["cursor"]["initial_node"]

    # ---------------------------------------------------------------- conditions
    def field(self, fid):
        if fid not in self.fields:
            raise Unsupported("undeclared field %s" % fid)
        return "t.d.%s" % key(fid)

    def tag_for(self, slot, pred):
        return "cobblers_h_%s" % hashlib.sha256(("%s|%s" % (slot, pred)).encode()).hexdigest()[:10]

    def probe(self, slot, pred):
        tag = self.tag_for(slot, pred)
        return (run(["tag ", UUID, " remove %s" % tag]) +
                run(["execute as ", UUID, " if items entity @s %s %s run tag @s add %s" % (slot, pred, tag)]))

    def cond(self, c, probes):
        k = c["kind"]
        if k == "always":
            return "1"
        if k in ("all", "any"):
            parts = [self.cond(x, probes) for x in c["conditions"]]
            return "(%s)" % (" && " if k == "all" else " || ").join(parts)
        if k == "not":
            return "!(%s)" % self.cond(c["condition"], probes)
        if k == "progression_equals":
            f, v = self.field(c["field"]), c["value"]
            if v is False:
                return "(%s != 1)" % f
            if c["field"] == self.cursor and v == self.initial:
                return "(%s == %s || %s == 0)" % (f, lit(v), f)
            fdef = self.fields[c["field"]]
            if fdef.get("type") == "enum" and v == fdef.get("initial"):
                return "(%s == %s || %s == 0)" % (f, lit(v), f)
            return "(%s == %s)" % (f, lit(v))
        if k == "progression_in":
            return "(%s)" % " || ".join(self.cond({"kind": "progression_equals", "field": c["field"], "value": v}, probes) for v in c["values"])
        if k in ("held_item", "inventory_contains"):
            if c.get("hand", "main") != "main" or c.get("count", 1) != 1:
                raise Unsupported("held_item/inventory_contains supports the main hand and count 1 only")
            pred = c.get("item_predicate") or c["item"]
            slot = "weapon.mainhand" if k == "held_item" else "container.*"
            probes.setdefault((slot, pred), self.probe(slot, pred))
            return "q.player.has_tag('%s')" % self.tag_for(slot, pred)
        if k == "flag":
            # a progression flag is an advancement (tools/progression_pack.py), not player data: probed like an item
            sel = "@s[advancements={%s:flag/%s=true}]" % (NS, ident(c["flag"]))
            tag = self.tag_for("flag", sel)
            probes.setdefault(("flag", sel), run(["tag ", UUID, " remove %s" % tag]) +
                              run(["execute as ", UUID, " if entity %s run tag @s add %s" % (sel, tag)]))
            return "q.player.has_tag('%s')" % tag
        if k == "player_tag":
            # a tag another pack keeps on the player (the Lopunny house's party callback, tools/lopunny_house.py):
            # read directly, as every probe above reads the tag it set. No probe: this compiler sets nothing here
            tag = c.get("tag")
            if not isinstance(tag, str) or not re.fullmatch(r"[a-z0-9_.]+", tag):
                raise Unsupported("player_tag %r is not [a-z0-9_.]+" % (tag,))
            return "q.player.has_tag('%s')" % tag
        if k == "starter_chosen":
            # set by the starter_chosen callback, or by open_starter_screen when Cobblemon says the pick is made
            return "q.player.has_tag('%s')" % STARTER_TAG
        raise Unsupported("condition kind %s" % k)

    # ---------------------------------------------------------------- effects
    def effect(self, e):
        k = e["kind"]
        if k == "set_progression":
            return "%s = %s;" % (self.field(e["field"]), lit(e["value"]))
        if k == "consume_held_item":
            if e.get("count", 1) != 1 or e.get("hand", "main") != "main":
                raise Unsupported("consume_held_item supports one item from the main hand")
            pred = e.get("item_predicate") or e["item"]
            # ONE item, not the stack: `item replace ... with air` emptied the whole hand, so a player holding several
            # lost them all (found by the southern residents' independent audit, 2026-10-03). The hand check still
            # guards that the item is held; `clear ... 1` then takes exactly one matching item
            return run(["execute as ", UUID, " if items entity @s weapon.mainhand %s run clear @s %s 1" % (pred, pred)])
        if k == "give_item":
            return self.give(e["item"], e["count"])
        if k == "grant_reward_once":
            reward = self.rewards[e["reward"]]
            contents = reward.get("contents")
            if not contents:
                raise Unsupported("reward %s has no verified contents" % e["reward"])
            claim = self.field(e["claim_field"])
            gives = "".join(self.give(c["item"], c["count"]) for c in contents)
            # the claim is written only when every give reported success; otherwise the page that granted it retries
            return ("(%s != 1) ? { %s%s %s q.player.has_tag('%s') ? { v.cobblers_retry = 1; } : { %s = 1; }; };"
                    % (claim, run(["scoreboard objectives add %s dummy" % TX_SCORE]), run(["tag ", UUID, " remove %s" % GIVE_FAILED]),
                       gives, GIVE_FAILED, claim))
        if k == "sync_scene":
            return run(["execute as ", UUID, " at @s run function %s:scenes/%s/beat" % (NS, ident(e["scene"]))])
        if k == "scene_function":
            return run(["execute as ", UUID, " at @s run function %s:scenes/%s/fn/%s" % (NS, ident(e["scene"]), ident(e["function"]))])
        if k == "function":
            return run(["execute as ", UUID, " at @s run function %s" % function_id(e["function"])])
        raise Unsupported("effect kind %s" % k)

    def battle_action(self, a):
        """The response that starts this conversation's NPC's battle against the talking player. Cobblemon's own
        dialogues/npc-example.json (in the 1.8.0 jar) does exactly this from an option: `q.dialogue.close();` then
        `q.npc.start_battle(q.player, 'double');`. 'singles' is the format the arena probe ran in game on 2026-10-03
        (docs/research/notes/arena-per-player-opponents.md section 8), the only one allowed here. The NPC's class must
        carry a party (the conversation's npc_battle), or there is nothing to fight with."""
        if not self.conv.get("npc_battle"):
            raise Unsupported("an npc_battle response needs the conversation's npc_battle (the NPC's party)")
        if a.get("format", "singles") != "singles":
            raise Unsupported("npc_battle format %r: only 'singles' has been run in game" % a.get("format"))
        return "q.player.save_data(); q.dialogue.close(); q.npc.start_battle(q.player, 'singles');"

    def starter_action(self, r):
        """The response that offers the native starter screen (see "starter" in the module docstring). A player who
        has already chosen (the command returns 0) is tagged and shown the response's `next`; anyone else gets the
        screen and the dialogue closes."""
        nxt = r.get("next")
        if nxt not in self.nodes:
            raise Unsupported("response %s: open_starter_screen needs a next node for a player who has chosen" % r["id"])
        return (run(["scoreboard objectives add %s dummy" % STARTER_SCORE]) +
                run(["execute as ", UUID, " run scoreboard players set @s %s -1" % STARTER_SCORE]) +
                run(["execute as ", UUID, " store result score @s %s run openstarterscreen @s" % STARTER_SCORE]) +
                run(["execute as ", UUID, " if score @s %s matches 0 run tag @s add %s" % (STARTER_SCORE, STARTER_TAG)]) +
                " q.player.has_tag('%s') ? { %s } : { q.player.save_data(); q.dialogue.close(); };"
                % (STARTER_TAG, self.goto(nxt)))

    def give(self, item, count):
        """`give <uuid>` is refused (a uuid parses as an entity selector), so give runs as the player; its success
        count goes to a score, and a failure leaves a tag the Molang side reads in the same action."""
        # the objective must exist first: `store ... score` into a missing objective fails silently, and so would the
        # failure check (the first run lost a returned glass bottle that way)
        return (run(["scoreboard objectives add %s dummy" % TX_SCORE]) +
                run(["execute as ", UUID, " store success score @s %s run give @s %s %d" % (TX_SCORE, item, count)]) +
                run(["execute as ", UUID, " unless score @s %s matches 1 run tag @s add %s" % (TX_SCORE, GIVE_FAILED)]))

    def transition(self, tid):
        t = self.transitions[tid]
        probes = {}
        cond = " && ".join(self.cond(c, probes) for c in t["conditions"]) or "1"
        body = " ".join(self.effect(e) for e in t["effects"])
        return "%s (%s) ? { %s q.player.save_data(); };" % ("".join(probes.values()), cond, body)

    def cursor_target(self, tid):
        for e in self.transitions[tid]["effects"]:
            if e["kind"] == "set_progression" and e["field"] == self.cursor:
                return e["value"]
        return None

    # ---------------------------------------------------------------- pages
    def choice_probes(self, node_id):
        n = self.nodes.get(node_id)
        probes = {}
        if n and n["kind"] == "choice":
            for r in n["responses"]:
                if r.get("visible_when"):
                    self.cond(r["visible_when"], probes)
        return "".join(probes.values())

    def all_choice_probes(self):
        probes = {}
        for n in self.nodes.values():
            if n["kind"] == "choice":
                for r in n["responses"]:
                    if r.get("visible_when"):
                        self.cond(r["visible_when"], probes)
        return "".join(probes.values())

    def goto(self, target):
        """Persist the cursor at target, then show it (with the probes its options need), or close on a terminal repeat."""
        return "%s = %s; q.player.save_data(); %s q.dialogue.set_page(%s);" % (
            self.field(self.cursor), lit(target), self.choice_probes(target), lit(target))

    def speaker_name(self, sid):
        names = self.conv.get("speakers")
        if isinstance(names, dict) and sid in names:
            return names[sid]
        return sid.replace("_", " ").title()

    def page(self, n):
        speaker = n.get("speaker")
        page = {"id": n["id"], "lines": [n["text"]]}
        if speaker and self.speaker_name(speaker) is not None:
            page["speaker"] = speaker
        pre = "t.d = q.player.data(); "
        if n["kind"] == "line":
            acks = "".join(self.transition(a["transition"]) for a in n.get("actions_after_acknowledge") or [] if a["kind"] == "quest_transition")
            if any(a["kind"] != "quest_transition" for a in n.get("actions_after_acknowledge") or []):
                raise Unsupported("line %s: only quest_transition after acknowledge" % n["id"])
            if n["next"] == n["id"]:
                page["input"] = pre + acks + "%s = %s; q.player.save_data(); q.dialogue.close();" % (self.field(self.cursor), lit(n["id"]))
            else:
                if n["next"] not in self.nodes:
                    raise Unsupported("line %s: next %s is not a node" % (n["id"], n["next"]))
                if acks:
                    # a failed reward delivery keeps the cursor on this line and closes, so the next talk retries it
                    page["input"] = (pre + "v.cobblers_retry = 0; " + acks +
                                     "v.cobblers_retry == 1 ? { %s = %s; q.player.save_data(); q.dialogue.close(); } : { %s };"
                                     % (self.field(self.cursor), lit(n["id"]), self.goto(n["next"])))
                else:
                    page["input"] = pre + self.goto(n["next"])
            return page
        if n["kind"] != "choice":
            raise Unsupported("node kind %s" % n["kind"])
        options = []
        for r in n["responses"]:
            act, closes, tids, battle = pre, False, [], None
            if any(a["kind"] == "open_starter_screen" for a in r.get("actions") or []):
                if len(r.get("actions") or []) != 1:
                    raise Unsupported("response %s: open_starter_screen is a response's only action" % r["id"])
                opt = {"text": r["text"], "value": r["id"], "action": act + self.starter_action(r)}
                if r.get("visible_when"):
                    opt["isVisible"] = "t.d = q.player.data(); return %s;" % self.cond(r["visible_when"], {})
                options.append(opt)
                continue
            for a in r.get("actions") or []:
                if a["kind"] == "quest_transition":
                    act += self.transition(a["transition"])
                    tids.append(a["transition"])
                elif a["kind"] == "set_cursor":
                    act += "%s = %s; " % (self.field(self.cursor), lit(a["node"]))
                elif a["kind"] == "close_dialogue":
                    closes = True
                elif a["kind"] == "npc_battle":
                    battle = self.battle_action(a)
                else:
                    raise Unsupported("response action %s" % a["kind"])
            if battle is not None:
                if tids or closes or len(r.get("actions") or []) != 1:
                    raise Unsupported("response %s: npc_battle is a response's only action" % r["id"])
                act += battle
            elif closes:
                act += "q.player.save_data(); q.dialogue.close();"
            elif tids:
                nxt = r["next"]
                for tid in tids:
                    if self.cursor_target(tid) != nxt:
                        raise Unsupported("response %s: transition %s must set the cursor to %s" % (r["id"], tid, nxt))
                # success moved the cursor to next; a refused transition leaves it here, and the choice is shown again
                act += "q.player.save_data(); %s%s q.dialogue.set_page(%s);" % (self.choice_probes(nxt), self.choice_probes(n["id"]), self.field(self.cursor))
            else:
                act += self.goto(r["next"])
            opt = {"text": r["text"], "value": r["id"], "action": act}
            if r.get("visible_when"):
                # evaluated on its own, not after the page's actions: without reading the data here t.d is unset and
                # both of Pip's "Come with me." options showed (the owner, in game, 2026-09-24)
                opt["isVisible"] = "t.d = q.player.data(); return %s;" % self.cond(r["visible_when"], {})
            options.append(opt)
        page["input"] = {"type": "option", "vertical": True, "options": options}
        return page

    def entry(self):
        probes = {}
        parts = []
        for rule in sorted(self.conv["entry_rules"], key=lambda r: r["priority"]):
            cond = self.cond(rule["when"], probes)
            acts = "".join(self.transition(a["transition"]) for a in rule.get("actions") or [] if a["kind"] == "quest_transition")
            node = rule["node"]
            if node == "$cursor":
                c = self.field(self.cursor)
                target = "(%s == 0 ? %s : %s)" % (c, lit(self.initial), c)
            else:
                if node not in self.nodes:
                    raise Unsupported("entry node %s" % node)
                target = lit(node)
            parts.append("(v.cobblers_entry == 0 && %s) ? { t.d = q.player.data(); %s v.cobblers_entry = %s; };" % (cond, acts, target))
        return ("t.d = q.player.data(); %s%s v.cobblers_entry = 0; %s "
                "v.cobblers_entry == 0 ? { q.dialogue.close(); } : { q.dialogue.set_page(v.cobblers_entry); };"
                % ("".join(probes.values()), self.all_choice_probes(), " ".join(parts)))

    def dialogue(self):
        pages = [self.page(n) for n in self.conv["nodes"]]
        speakers = {n["speaker"]: {"name": self.speaker_name(n["speaker"])} for n in self.conv["nodes"]
                    if n.get("speaker") and self.speaker_name(n["speaker"]) is not None}
        return {"initializationAction": self.entry(), "speakers": speakers, "pages": pages}


def load(data_dir):
    dialogue = json.loads((data_dir / "dialogue.json").read_text(encoding="utf-8"))
    quests = json.loads((data_dir / "quests.json").read_text(encoding="utf-8"))
    prog = json.loads((data_dir / "progression.json").read_text(encoding="utf-8"))
    return dialogue, {q["id"]: q for q in quests["quests"]}, {f["id"]: f for f in prog["quest_fields"]}


def check_fields(quest, fields):
    for fid in quest["progression_field_refs"]:
        if fid not in fields:
            raise Unsupported("undeclared field %s" % fid)
        if fields[fid]["scope"] != "player":
            raise Unsupported("world-scoped field %s" % fid)
        if fields[fid]["type"] == "integer":
            raise Unsupported("integer field %s (0 would be ambiguous with unset)" % fid)


def compile_conversation(conv, quests, fields, data_dir=None):
    """{relative path: content} for one conversation: its dialogue, and its NPC class when an NPC opens it."""
    quest = quests.get(conv["quest_id"])
    if quest is None:
        raise Unsupported("unknown quest %s" % conv["quest_id"])
    check_fields(quest, fields)
    c = Compiler(conv, quest, fields)
    files = {"data/%s/dialogues/%s.json" % (NS, conv["id"]): c.dialogue()}
    npc = conv.get("npc_id")
    if npc:
        first = next((n.get("speaker") for n in conv["nodes"] if n.get("speaker")), None)
        name = conv.get("npc_name") or (c.speaker_name(first) if first else None) or npc
        files["data/%s/npcs/%s.json" % (NS, npc)] = {
            "hitbox": "player", "names": [name], "resourceIdentifier": NPC_RESOURCE,
            "interaction": {"type": "dialogue", "dialogue": "%s:%s" % (NS, conv["id"])},
            "canDespawn": False, "isInvulnerable": True, "isMovable": False, "isLeashable": False,
            "allowProjectileHits": False,
        }
        if conv.get("npc_battle"):
            files["data/%s/npcs/%s.json" % (NS, npc)].update(battle_class(conv["npc_battle"], data_dir))
    elif conv.get("npc_battle"):
        raise Unsupported("npc_battle with no NPC: only an NPC has a party")
    return files


def battle_class(nb, data_dir=None):
    """The fields an NPC that also fights adds to its class (a conversation's npc_battle: {"trainers": <file in
    data/>, "trainer": <id>, "skill": 0-5}): a `simple` party of the trainer record's authored `team`, each member a
    properties string at its own level (tools/arena_runtime.py properties(), the form its exam classes use), and the
    rest of the shape of the arena probe class that battled in game on 2026-10-03 (docs/research/notes/
    arena-per-player-opponents.md sections 7-8): canChallenge false (a click opens the dialogue, never a battle), the
    battler and looks_at_players presets, autoHealParty (every challenge meets the full team). Every key is one
    NPCClass.kt @1.8.0 lists (same note, section 1)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from arena_runtime import properties
    src = (Path(data_dir) if data_dir else ROOT / "data") / nb["trainers"]
    recs = {t["id"]: t for t in json.loads(src.read_text(encoding="utf-8"))["trainers"]}
    rec = recs.get(nb["trainer"])
    if rec is None or not rec.get("team"):
        raise Unsupported("npc_battle: %s has no trainer %s with a team" % (nb["trainers"], nb["trainer"]))
    skill = nb.get("skill")
    if not isinstance(skill, int) or not 0 <= skill <= 5:
        raise Unsupported("npc_battle skill %r is not 0-5" % (skill,))
    return {"battleConfiguration": {"canChallenge": False}, "skill": skill, "autoHealParty": True,
            "ai": [{"type": "apply_behaviours", "presets": ["cobblemon:battler", "cobblemon:looks_at_players"]}],
            "party": {"type": "simple", "pokemon": [properties(m, m["level"]) for m in rec["team"]]}}


PACK_META = {"pack": {"pack_format": 48, "description": "Cobblers compiled dialogue (generated)"}}


def uses_starter_screen(conv):
    """True when a response of the conversation offers the native starter screen."""
    return any(a.get("kind") == "open_starter_screen" for n in conv["nodes"] if n.get("kind") == "choice"
               for r in n["responses"] for a in r.get("actions") or [])


def starter_callback():
    """The starter_chosen callback: tags the player the moment Cobblemon posts STARTER_CHOSEN for their pick, so the
    conversation that offered the screen knows on the next talk. Callbacks register only under the cobblemon
    namespace (docs/research/notes/level-cap-catch-block.md:27-32); `q.player.username` in a server-sourced command is
    the form tools/lopunny_house.py's player_tick_pre callback uses. Only a tag: harmless in any world it loads in."""
    return "q.run_command('tag ' + q.player.username + ' add %s');\n" % STARTER_TAG


def build(conv_id, data_dir, place=None):
    dialogue, quests, fields = load(data_dir)
    conv = next((c for c in dialogue["conversations"] if c["id"] == conv_id), None)
    if not conv:
        raise SystemExit("no conversation %s" % conv_id)
    files = {"pack.mcmeta": PACK_META}
    files.update(compile_conversation(conv, quests, fields, data_dir))
    if uses_starter_screen(conv):
        files[STARTER_CALLBACK] = starter_callback()
    if place:
        if not conv.get("npc_id"):
            raise SystemExit("%s has no NPC: a prop or an actor opens it" % conv_id)
        files["placement.txt"] = "spawnnpcat %d %d %d %s:%s\n" % (tuple(place) + (NS, conv["npc_id"]))
    return files


def build_all(data_dir):
    """(files, compiled ids, {refused id: why}) for every conversation in the data."""
    dialogue, quests, fields = load(data_dir)
    files, done, refused = {"pack.mcmeta": PACK_META}, [], {}
    for conv in dialogue["conversations"]:
        try:
            got = compile_conversation(conv, quests, fields, data_dir)
        except Unsupported as e:
            refused[conv["id"]] = str(e)
            continue
        clash = [k for k in got if k in files]
        if clash:
            raise SystemExit("%s writes %s, which another conversation already wrote" % (conv["id"], clash))
        files.update(got)
        done.append(conv["id"])
        if uses_starter_screen(conv):
            files[STARTER_CALLBACK] = starter_callback()
    return files, done, refused


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("conversation", nargs="?")
    p.add_argument("--all", action="store_true", help="every conversation that compiles, into one pack")
    p.add_argument("--data", default=str(ROOT / "data"))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--place", nargs=3, type=int, metavar=("X", "Y", "Z"), help="write the spawnnpcat command for a test position")
    a = p.parse_args(argv)
    if a.all == bool(a.conversation):
        p.error("name one conversation, or pass --all")
    if a.all:
        files, done, refused = build_all(Path(a.data))
        print("compiled %d conversations" % len(done))
        for cid, why in sorted(refused.items()):
            print("  refused %s: %s" % (cid, why))
    else:
        files = build(a.conversation, Path(a.data), a.place)
    out = Path(a.out)
    for rel, content in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        f.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %d files to %s" % (len(files), out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
