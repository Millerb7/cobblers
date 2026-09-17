#!/usr/bin/env python
"""Compile a campaign conversation (data/dialogue.json + data/quests.json + data/progression.json) into native Cobblemon 1.8 dialogue.

Output (build/datapacks/cobblers_dialogue, generated, not committed):
  data/cobblers/dialogues/<conversation id>.json   one page per node
  data/cobblers/npcs/<npc id>.json                 an NPC class whose interaction opens that dialogue
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

Only the constructs the thirsty stranger uses are supported; anything else stops compilation rather than guessing.

  python tools/compile_dialogue.py dlg_route1_thirsty_stranger [--out DIR] [--place X Y Z]
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
TX_SCORE = "cobblers_tx"
GIVE_FAILED = "cobblers_give_failed"


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
            return run(["execute as ", UUID, " if items entity @s weapon.mainhand %s run item replace entity @s weapon.mainhand with minecraft:air" % pred])
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
        raise Unsupported("effect kind %s" % k)

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

    def page(self, n):
        speaker = n.get("speaker")
        page = {"id": n["id"], "speaker": speaker, "lines": [n["text"]]}
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
            act, closes, tids = pre, False, []
            for a in r.get("actions") or []:
                if a["kind"] == "quest_transition":
                    act += self.transition(a["transition"])
                    tids.append(a["transition"])
                elif a["kind"] == "set_cursor":
                    act += "%s = %s; " % (self.field(self.cursor), lit(a["node"]))
                elif a["kind"] == "close_dialogue":
                    closes = True
                else:
                    raise Unsupported("response action %s" % a["kind"])
            if closes:
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
                opt["isVisible"] = self.cond(r["visible_when"], {})
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
        speakers = {n["speaker"]: {"name": n["speaker"].replace("_", " ").title()} for n in self.conv["nodes"] if n.get("speaker")}
        return {"initializationAction": self.entry(), "speakers": speakers, "pages": pages}


def build(conv_id, data_dir, place=None):
    dialogue = json.loads((data_dir / "dialogue.json").read_text(encoding="utf-8"))
    quests = json.loads((data_dir / "quests.json").read_text(encoding="utf-8"))
    prog = json.loads((data_dir / "progression.json").read_text(encoding="utf-8"))
    conv = next((c for c in dialogue["conversations"] if c["id"] == conv_id), None)
    if not conv:
        raise SystemExit("no conversation %s" % conv_id)
    quest = next(q for q in quests["quests"] if q["id"] == conv["quest_id"])
    fields = {f["id"]: f for f in prog["quest_fields"]}
    for fid in quest["progression_field_refs"]:
        if fields[fid]["scope"] != "player":
            raise Unsupported("world-scoped field %s" % fid)
        if fields[fid]["type"] == "integer":
            raise Unsupported("integer field %s (0 would be ambiguous with unset)" % fid)
    doc = Compiler(conv, quest, fields).dialogue()
    npc = conv["npc_id"]
    files = {
        "pack.mcmeta": {"pack": {"pack_format": 48, "description": "Cobblers compiled dialogue (generated)"}},
        "data/%s/dialogues/%s.json" % (NS, conv_id): doc,
        "data/%s/npcs/%s.json" % (NS, npc): {
            "hitbox": "player", "names": [conv["nodes"][0].get("speaker", npc).title()],
            "interaction": {"type": "dialogue", "dialogue": "%s:%s" % (NS, conv_id)},
            "canDespawn": False, "isInvulnerable": True, "isMovable": False, "isLeashable": False,
            "allowProjectileHits": False,
        },
    }
    if place:
        files["placement.txt"] = "spawnnpcat %d %d %d %s:%s\n" % (tuple(place) + (NS, npc))
    return files


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("conversation")
    p.add_argument("--data", default=str(ROOT / "data"))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--place", nargs=3, type=int, metavar=("X", "Y", "Z"), help="write the spawnnpcat command for a test position")
    a = p.parse_args(argv)
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
