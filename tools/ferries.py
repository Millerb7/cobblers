#!/usr/bin/env python
"""The ferry: ferrymen at docks, a compiled dialogue per dock, a fare in CobbleDollars, a fade and a teleport, per
player. Generated from data/ferries.json into the world-local datapack build/datapacks/cobblers_ferries.

The design is docs/mechanics/WATER_PROPOSAL.md section 4 (4.2 the mechanism, 4.3 the lines) with the owner's
decisions of 2026-09-27 (WATER_BUILD_PLAN.md section 13: "The ferry IS the gate for players without a water mount";
boats are shallows craft). Every part is an existing, proven piece, nothing new in the game:

  the ferryman   a Cobblemon NPC whose class opens a dialogue (tools/compile_dialogue.py, EXP-022), placed over RCON by
                 spawnnpcat after a restart, because NPC classes load only at server start (tools/reapply.py, step
                 R17F, the same "npc" action R9F and R17 use). The class and dialogue ship in this pack.
  the dialogue   one per dock, compiled by tools/compile_dialogue.py's Compiler from a conversation this tool builds in
                 memory: one page, one option per trip from this dock, a gated line's option visible only to a player
                 who meets its gates (flag conditions probed per player, compile_dialogue "flag"), and "Not today."
                 The menu holds no quest state: no cursor, no field, so nothing is added to data/progression.json.
  the trip       a function run as the player by the option (compile_dialogue "function"): refuse a second submit of
                 the same click (a per-player cooldown score), check every gate, read the balance (`cobbledollars query`
                 into a score, EXP-040), refuse with a message if it is short, charge through the macro the blackout
                 charge proved in game (`$cobbledollars remove @s $(amount)`, EXP-042 run 1), re-read the balance and
                 refuse the trip unless it fell by exactly the fare, then dismount, fade (blindness and a title) and
                 teleport to the far dock's landing. A free line has no CobbleDollars command at all.

Only lines whose every dock is built are emitted; the rest of the line set lives in the data, so each needs only its
docks. The audit is offline and fails closed (the implementer's audit; its tests belong to the test author):

  gates      every gate names a flag data/progression.json declares and tools/progression_pack.py plans, or a
             declared player boolean quest field; an emitted line with an unresolved gate fails
  docks      every built dock's ferryman and landing stand one above their ground (tools/ground.py, rounded, with the
             settlement's islet or decks laid over, never a world), on ground at or above the sea level (not water),
             in cells no authored earthwork writes, outside every building and keep-clear box, and apart from every
             other placed NPC (reapply's "npc" action counts NPCs within 2 blocks)
  swimming   every line declared a gate: each barrier crossing, walked shore to shore on the heightmap at the measured
             swim speed with data/blackout.json's surface-fatigue constants (tests/test_system_contracts.py C3's
             approach: a straight line, the water depth per block, the rest cells at either end trimmed; the fatigue
             stepped here from the constants, not from the generated function), knocks out an unaided and a trained
             swimmer; and the island's nearest other land (measured now, by dilation from its land) is the far side
             of a declared barrier no longer than that gap, so a new shorter crossing fails the audit. A line declared
             a leak keeps its barrier walk and must still leak as declared (so the declaration cannot go stale)
  the output every generated trip with a fare reads the balance before any charge, refuses when short before any
             charge, charges once, verifies the charge, and teleports only after it, to the landing the data names;
             a free trip has no CobbleDollars command; every gate is checked before the charge; every function passes
             tools/function_limits.py

  python tools/ferries.py build  [--source-root R] [--out DIR]   write the pack (no heightmap needed)
  python tools/ferries.py audit  [--source-root R]               the offline audit; exit 1 on any problem
  python tools/ferries.py measure X Z [--source-root R]          the nearest other land to the land at (X, Z)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import compile_dialogue as CD  # noqa: E402
import function_limits  # noqa: E402

DATA = ROOT / "data" / "ferries.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_ferries"
NS = "cobblers"
SCORE, COOLDOWN = "cobblers_ferry", "cobblers_ferry_cd"
STORAGE = "%s:ferries" % NS
ID = re.compile(r"[a-z0-9_]+")
GATE_KINDS = ("flag", "quest_field")
SWIM_KINDS = ("gate", "leak", "kindness", "unsited")
NPC_RADIUS = 2.5            # reapply's npc action counts cobblemon:npc within 2 blocks of the spot
SEARCH_MARGIN = 700         # blocks round an island searched for its nearest other land
# The ground rule (tools/ground_rule.py): nothing here reads a world; every position comes from tools/ground.py.
WORLD_READS: set = set()


class FerryError(SystemExit):
    pass


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def by_id(items):
    return {i["id"]: i for i in items}


def num(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ---------------------------------------------------------------------------------------------------------- the lines
def dock_built(d):
    return d.get("status") == "built" and isinstance(d.get("ferryman"), dict) and isinstance(d.get("landing"), dict)


def emitted_lines(doc):
    """The lines every one of whose docks is built: only these are generated."""
    docks = by_id(doc["docks"])
    return [ln for ln in doc["lines"] if all(s in docks and dock_built(docks[s]) for s in ln["stops"])]


def trips(line):
    """Every ordered pair of the line's stops: from each dock to each other one."""
    return [(a, b) for a in line["stops"] for b in line["stops"] if a != b]


def trip_fn(line, a, b):
    return "%s:ferries/%s/%s_to_%s" % (NS, line["id"], a, b)


def text(s, color="gray", italic=False):
    out = {"text": s, "color": color}
    if italic:
        out["italic"] = True
    return json.dumps(out, ensure_ascii=False)


def fill(template, **kw):
    for k, v in kw.items():
        template = template.replace("{%s}" % k, str(v))
    if re.search(r"\{[a-z_]+\}", template):
        raise FerryError("message %r names a placeholder this tool does not fill" % template)
    return template


def fare_text(doc, fare):
    m = doc["messages"]
    return m["free"] if fare == 0 else fill(m["fare"], fare=fare)


def dialogue_cond(gate):
    if gate["kind"] == "flag":
        return {"kind": "flag", "flag": gate["flag"]}
    if gate["kind"] == "quest_field":
        return {"kind": "progression_equals", "field": gate["field"], "value": gate.get("value", True)}
    raise FerryError("gate kind %r" % gate["kind"])


def conversation(doc, dock, lines):
    """(conversation, quest) for one dock's ferryman, in memory, in data/dialogue.json's and data/quests.json's shape,
    so tools/compile_dialogue.py compiles them as it compiles every other conversation."""
    docks = by_id(doc["docks"])
    m = doc["messages"]
    qid = "ferry_%s" % dock["id"]
    responses, transitions, refs = [], [], []
    for ln in lines:
        for a, b in trips(ln):
            if a != dock["id"]:
                continue
            tid = "go_%s_%s" % (ln["id"], b)
            conds = [dialogue_cond(g) for g in ln.get("gates") or []]
            refs += [g["field"] for g in ln.get("gates") or [] if g["kind"] == "quest_field"]
            transitions.append({"id": tid, "conditions": conds,
                                "effects": [{"kind": "function", "function": trip_fn(ln, a, b)}]})
            r = {"id": "r_%s_%s" % (ln["id"], b),
                 "text": fill(m["option"], destination=docks[b]["name"], line=ln["name"], fare=fare_text(doc, ln["fare"])),
                 "actions": [{"kind": "quest_transition", "transition": tid}, {"kind": "close_dialogue"}]}
            if conds:
                r["visible_when"] = conds[0] if len(conds) == 1 else {"kind": "all", "conditions": conds}
            responses.append(r)
    responses.append({"id": "r_leave", "text": m["leave"], "actions": [{"kind": "close_dialogue"}]})
    conv = {"id": "dlg_ferry_%s" % dock["id"], "quest_id": qid, "npc_id": "npc_ferry_%s" % dock["id"],
            "npc_name": dock["ferryman"]["name"], "scope": "player", "speakers": {"ferryman": dock["ferryman"]["name"]},
            # a menu, not a conversation with a place in it: no cursor, no quest field
            "cursor": {"progression_field": None, "initial_node": "menu"},
            "entry_rules": [{"priority": 10, "when": {"kind": "always"}, "node": "menu"}],
            "nodes": [{"id": "menu", "kind": "choice", "speaker": "ferryman", "text": dock["ferryman"]["greeting"],
                       "responses": responses}]}
    quest = {"id": qid, "progression_field_refs": sorted(set(refs)), "transitions": transitions, "rewards": []}
    return conv, quest


def gate_check(doc, line, gate, dest):
    """The command that refuses the trip, as the player, when this gate is not met; None for a gate only the dialogue
    can check (a quest field lives in Cobblemon player data, which a function cannot read in line)."""
    if gate["kind"] != "flag":
        return None
    msg = fill(doc["messages"]["gated"], line=line["name"], destination=dest["name"], requirement=gate["says"])
    return "execute unless entity @s[advancements={%s:flag/%s=true}] run return run tellraw @s %s" % (
        NS, gate["flag"], text(msg, "gold"))


def trip_lines(doc, line, a, b):
    docks = by_id(doc["docks"])
    src, dest = docks[a], docks[b]
    m, t = doc["messages"], doc["trip"]
    fare = int(line["fare"])
    lx, ly, lz = dest["landing"]["at"]
    yaw = dest["landing"].get("yaw", 0)
    out = ["# Generated by tools/ferries.py from data/ferries.json: %s, %s to %s (as and at the player, from the "
           "ferryman's dialogue)" % (line["name"], src["name"], dest["name"]),
           "# a second submit of the same click, or a trip straight after one, does nothing",
           "execute store result score #now %s run time query gametime" % SCORE,
           "execute if score @s %s > #now %s run return 0" % (COOLDOWN, SCORE)]
    for g in line.get("gates") or []:
        c = gate_check(doc, line, g, dest)
        if c:
            out.append(c)
    if fare > 0:
        before, _, after = m["short"].partition("{balance}")
        before = fill(before, line=line["name"], destination=dest["name"], fare=fare)
        after = fill(after, line=line["name"], destination=dest["name"], fare=fare)
        refuse = json.dumps([{"text": "", "color": "gold"}, {"text": before},
                             {"score": {"name": "@s", "objective": SCORE}}, {"text": after}], ensure_ascii=False)
        failed = fill(m["charge_failed"], line=line["name"], destination=dest["name"], fare=fare)
        out += ["# the fare, $%d: read the balance first (EXP-040), refuse if it is short, nothing taken" % fare,
                "execute store result score @s %s run cobbledollars query @s" % SCORE,
                "execute unless score @s %s matches %d.. run return run tellraw @s %s" % (SCORE, fare, refuse),
                "# from here the click is spent: a second one inside the cooldown is refused above",
                "scoreboard players operation @s %s = #now %s" % (COOLDOWN, SCORE),
                "scoreboard players add @s %s %d" % (COOLDOWN, int(t["cooldown_ticks"])),
                "data modify storage %s charge.amount set value %d" % (STORAGE, fare),
                "function %s:ferries/charge with storage %s charge" % (NS, STORAGE),
                "# the charge must have taken exactly the fare, or there is no trip",
                "execute store result score #after %s run cobbledollars query @s" % SCORE,
                "scoreboard players operation #want %s = @s %s" % (SCORE, SCORE),
                "scoreboard players remove #want %s %d" % (SCORE, fare),
                "execute unless score #after %s = #want %s run return run tellraw @s %s" % (SCORE, SCORE, text(failed, "red"))]
    else:
        out += ["# a free line: no fare, nothing read or taken",
                "scoreboard players operation @s %s = #now %s" % (COOLDOWN, SCORE),
                "scoreboard players add @s %s %d" % (COOLDOWN, int(t["cooldown_ticks"]))]
    fade = t["fade"]
    out += ["# off whatever is ridden (a boat, a Pokemon), and anything riding the player, so nothing is dragged along",
            "ride @s dismount",
            "execute on passengers run ride @s dismount",
            "effect give @s minecraft:blindness %d 0 true" % int(fade["blindness_seconds"]),
            "title @s times %d %d %d" % tuple(fade["title_ticks"]),
            "title @s subtitle %s" % text(fill(m["arrive_subtitle"], line=line["name"], destination=dest["name"]), "gray", True),
            "title @s title %s" % text(fill(m["arrive_title"], line=line["name"], destination=dest["name"]), "white"),
            "playsound %s player @s ~ ~ ~ 1 1" % t["sound"],
            "tp @s %s %d %s %s 0" % (num(lx + 0.5), ly, num(lz + 0.5), num(yaw))]
    if fare > 0:
        out.append("tellraw @s %s" % text(fill(m["paid"], line=line["name"], destination=dest["name"], fare=fare)))
    return out


def build(doc):
    """{relative path in the pack: content (list of lines, or a JSON object)} and the NPCs to place."""
    files = {"pack.mcmeta": {"pack": {"pack_format": 48, "description": "Cobblers ferry (generated by tools/ferries.py)"}},
             "data/minecraft/tags/function/load.json": {"values": ["%s:ferries/load" % NS]}}
    fn = lambda rel: "data/%s/function/ferries/%s.mcfunction" % (NS, rel)
    files[fn("load")] = ["# the ferry's scores: the balance read, and each player's cooldown after a click",
                         "scoreboard objectives add %s dummy" % SCORE, "scoreboard objectives add %s dummy" % COOLDOWN]
    lines = emitted_lines(doc)
    # the blackout charge's macro, proven in game (EXP-042 run 1: $725 to $652). Emitted only when a built line
    # actually charges a fare: with the Sound ferry retired on 2026-09-29 the one paid line went with it, the
    # remaining built line is free, and an unreferenced function fails prepare's orphan gate. Generating it anyway
    # would be dead code that the gate is right to refuse.
    if any(int(t.get("fare") or 0) > 0 for ln in lines for t in (ln.get("trips") or [ln])):
        files[fn("charge")] = ["$cobbledollars remove @s $(amount)"]
    docks = by_id(doc["docks"])
    npcs = []
    for ln in lines:
        for a, b in trips(ln):
            files[fn("%s/%s_to_%s" % (ln["id"], a, b))] = trip_lines(doc, ln, a, b)
    serving = {}
    for ln in lines:
        for s in ln["stops"]:
            serving.setdefault(s, []).append(ln)
    # the fields data/progression.json declares, NOT an empty dict. It was {} until 2026-09-30, which made every
    # `quest_field` gate impossible: the compiler refuses an undeclared field, so any line gated on a quest would
    # fail the whole pack with "undeclared field <id>" no matter what progression.json said. Nothing had hit it
    # because no gated line was emitted until the ferry docks made four charters live. static_problems() below
    # already reads the same list the same way.
    fields = {f["id"]: f for f in json.loads(
        (ROOT / "data" / "progression.json").read_text(encoding="utf-8")).get("quest_fields") or []}
    for d in sorted(serving):
        conv, quest = conversation(doc, docks[d], serving[d])
        got = CD.compile_conversation(conv, {quest["id"]: quest}, fields)
        clash = [k for k in got if k in files]
        if clash:
            raise FerryError("%s writes %s twice" % (d, clash))
        files.update(got)
        x, y, z = docks[d]["ferryman"]["at"]
        npcs.append((conv["id"], (x, y, z), "%s:%s" % (NS, conv["npc_id"])))
    return files, npcs


def npc_placements(doc):
    """[(conversation id, (x, y, z), npc class)] for tools/reapply.py's "npc" action, from the committed data alone."""
    docks = by_id(doc["docks"])
    stops = sorted({s for ln in emitted_lines(doc) for s in ln["stops"]})
    return [("dlg_ferry_%s" % s, tuple(docks[s]["ferryman"]["at"]), "%s:npc_ferry_%s" % (NS, s)) for s in stops]


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(content) + "\n" if isinstance(content, list) else json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        f.write_text(body, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------------------------------------- the audit
def static_problems(doc, progression, planned_flags):
    out = []
    docks = {}
    for d in doc.get("docks") or []:
        if not ID.fullmatch(d.get("id") or ""):
            out.append("dock id %r" % d.get("id"))
            continue
        if d["id"] in docks:
            out.append("dock %s: declared twice" % d["id"])
        docks[d["id"]] = d
        if d.get("status") not in ("built", "planned", "retired"):
            out.append("dock %s: status must be built, planned or retired" % d["id"])
        # `retired` exists because the design already anticipated it: STATE records that "the Sound ferry retires
        # when [the Pacifidlog re-site] is applied". Applying the water shape drowned the old Sound docks, and the
        # tool had no word for a dock that was built and is now gone, which forced a choice between lying ("planned")
        # and failing the audit for ever. A retired dock is never built and never ground-checked; its `retired_why`
        # says what replaced it.
        if d.get("status") == "retired" and not d.get("retired_why"):
            out.append("dock %s: a retired dock needs retired_why" % d["id"])
        if d.get("status") == "built":
            for part in ("ferryman", "landing"):
                p = d.get(part)
                if not (isinstance(p, dict) and isinstance(p.get("at"), list) and len(p["at"]) == 3
                        and all(type(v) is int for v in p["at"])):
                    out.append("dock %s: a built dock needs %s.at [x, y, z] integers" % (d["id"], part))
            fm = d.get("ferryman") or {}
            if not (isinstance(fm.get("name"), str) and fm["name"] and isinstance(fm.get("greeting"), str) and fm["greeting"]):
                out.append("dock %s: the ferryman needs a name and a greeting" % d["id"])
            if not d.get("why"):
                out.append("dock %s: no why" % d["id"])
    fields = {f["id"]: f for f in progression.get("quest_fields") or []}
    declared_flags = {f["id"] for f in progression.get("flags") or []}
    emitted = {ln["id"] for ln in emitted_lines(doc)} if not out else set()
    seen = set()
    for ln in doc.get("lines") or []:
        lid = ln.get("id") or ""
        if not ID.fullmatch(lid) or lid in seen:
            out.append("line id %r (missing, malformed or repeated)" % lid)
            continue
        seen.add(lid)
        for k in ("name", "why", "fare_why", "gate_why"):
            if not ln.get(k):
                out.append("line %s: no %s" % (lid, k))
        if not (isinstance(ln.get("fare"), int) and not isinstance(ln["fare"], bool) and ln["fare"] >= 0):
            out.append("line %s: fare must be a whole number of CobbleDollars, 0 or more" % lid)
        stops = ln.get("stops") or []
        if len(stops) < 2 or len(set(stops)) != len(stops):
            out.append("line %s: needs two or more different stops" % lid)
        for s in stops:
            if s not in docks:
                out.append("line %s: stop %s is not a dock" % (lid, s))
        for g in ln.get("gates") or []:
            kind = g.get("kind")
            if kind not in GATE_KINDS:
                out.append("line %s: gate kind %r" % (lid, kind))
                continue
            if kind == "flag":
                if g.get("flag") not in declared_flags:
                    out.append("line %s: gate flag %r is not declared in data/progression.json flags" % (lid, g.get("flag")))
                elif g["flag"] not in planned_flags:
                    out.append("line %s: gate flag %r is not planned by tools/progression_pack.py (no advancement)" % (lid, g["flag"]))
                if not g.get("says"):
                    out.append("line %s: gate %s has no refusal wording (says)" % (lid, g.get("flag")))
            else:
                f = fields.get(g.get("field"))
                ok = f is not None and f.get("scope") == "player" and f.get("type") == "boolean"
                if not ok and lid in emitted:
                    out.append("line %s: gate %s is not a declared player boolean quest field, and the line is built"
                               % (lid, g.get("field") or g.get("quest")))
                if not ok and lid not in emitted and not g.get("blocked_by"):
                    out.append("line %s: gate %s has no declared field and no blocked_by saying why"
                               % (lid, g.get("field") or g.get("quest")))
        sw = ln.get("swim") or {}
        if sw.get("declared") not in SWIM_KINDS:
            out.append("line %s: swim.declared must be one of %s" % (lid, ", ".join(SWIM_KINDS)))
        if sw.get("declared") in ("gate", "leak") and not sw.get("barriers"):
            out.append("line %s: declared %s with no barrier crossing to walk" % (lid, sw.get("declared")))
        if sw.get("declared") == "gate" and not sw.get("island"):
            out.append("line %s: declared a gate with no island seed (a point on the land it serves)" % lid)
        if sw.get("declared") == "leak" and not sw.get("leaks"):
            out.append("line %s: declared a leak with no leak crossing" % lid)
        if sw.get("declared") == "unsited" and lid in emitted:
            out.append("line %s: built, but its crossing is unsited" % lid)
        if not sw.get("why"):
            out.append("line %s: swim has no why" % lid)
    return out


class Occupancy:
    """Every block an authored earthwork in data/placements.json writes, and every building rectangle, for asking
    whether a cell is free. Parsed from the commands (setblock, fill), which are the placements' own data."""
    SET = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)")
    FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)")

    def __init__(self, placements):
        self.sets, self.fills, self.rects = {}, [], []
        for q in placements.get("placements") or []:
            for c in q.get("commands") or []:
                m = self.SET.match(c)
                if m:
                    self.sets[tuple(int(v) for v in m.groups()[:3])] = (q["id"], m.group(4))
                    continue
                m = self.FILL.match(c)
                if m:
                    a = [int(v) for v in m.groups()[:6]]
                    self.fills.append((min(a[0], a[3]), min(a[1], a[4]), min(a[2], a[5]),
                                       max(a[0], a[3]), max(a[1], a[4]), max(a[2], a[5]), q["id"], m.group(7)))
        for sid, s in (placements.get("settlements") or {}).items():
            for an in ((s.get("plan") or {}).get("anchors") or []):
                if isinstance(an.get("rect"), list) and len(an["rect"]) == 4:
                    self.rects.append((tuple(an["rect"]), "%s %s" % (sid, an.get("id"))))
            ws = (s.get("plan") or {}).get("waystone") or {}
            if isinstance(ws.get("position"), list) and len(ws["position"]) >= 2:
                wx, wz = ws["position"][0], ws["position"][-1]
                self.rects.append(((wx, wz, wx, wz), "%s waystone" % sid))

    def writer(self, x, y, z):
        """(placement id, block) written at the cell, or None. Air written by a clear is still a write."""
        if (x, y, z) in self.sets:
            return self.sets[(x, y, z)]
        for x0, y0, z0, x1, y1, z1, pid, b in self.fills:
            if x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1:
                return pid, b
        return None

    def building(self, x, z):
        for (x0, z0, x1, z1), what in self.rects:
            if min(x0, x1) <= x <= max(x0, x1) and min(z0, z1) <= z <= max(z0, z1):
                return what
        return None


def other_npcs():
    """[(what, (x, y, z))] of every other NPC the re-application places: scene NPCs and reward NPCs."""
    import reapply
    return [("npc %s" % c, p) for c, p, _ in reapply.scene_npcs() + reapply.npcs()]


def ground_for(settlement, cache, source_root=None):
    import ground as G
    if settlement not in cache:
        base = cache.get(None)
        if base is None:
            base = cache[None] = G.Ground(source_root)
        cache[settlement] = base if settlement is None else G.for_settlement(settlement, base=G.Ground(source_root))
    return cache[settlement]


def dock_problems(doc, placements, gcache, source_root=None, sea=62):
    out, report = [], []
    occ = Occupancy(placements)
    others = other_npcs()
    spots = []
    for d in doc["docks"]:
        if not dock_built(d):
            continue
        g = ground_for(d.get("settlement"), gcache, source_root)
        for part in ("ferryman", "landing"):
            x, y, z = d[part]["at"]
            gy = g(x, z)
            where = "dock %s %s at (%d, %d, %d)" % (d["id"], part, x, y, z)
            if gy < sea:
                out.append("%s: the ground there is y%d, under the sea level y%d: it is water" % (where, gy, sea))
            if y != gy + 1:
                out.append("%s: stands at y%d, but its ground is y%d, so it must stand at y%d" % (where, y, gy, gy + 1))
            for dy in (0, 1):
                w = occ.writer(x, y + dy, z)
                # air written there (a deck's headroom cleared) keeps the cell free; any block fills it
                if w and w[1].split("[")[0] not in ("minecraft:air", "minecraft:cave_air"):
                    out.append("%s: %s writes %s into the cell at y%d" % (where, w[0], w[1], y + dy))
            b = occ.building(x, z)
            if b:
                out.append("%s: inside %s" % (where, b))
            for x0, z0, x1, z1 in d.get("keep_clear") or []:
                if x0 <= x <= x1 and z0 <= z <= z1:
                    out.append("%s: inside the dock's own keep-clear box %s" % (where, [x0, z0, x1, z1]))
            report.append("%s: ground y%d (%s), cell free" % (where, gy, d.get("settlement") or "heightmap"))
        spots.append((d["id"], tuple(d["ferryman"]["at"])))
        if math.dist(d["ferryman"]["at"], d["landing"]["at"]) < 2:
            out.append("dock %s: its landing is within 2 blocks of its ferryman: an arrival lands in the NPC" % d["id"])
    for i, (a, p) in enumerate(spots):
        for what, q in others + [("ferryman %s" % b, s) for b, s in spots[i + 1:]]:
            if math.dist(p, q) < NPC_RADIUS + 0.5:
                out.append("ferryman %s at %s is %.1f blocks from %s at %s: reapply's npc count would see both"
                           % (a, p, math.dist(p, q), what, q))
    return out, report


# ---- swimming: the plan's and C3's walk, with the fatigue stepped from data/blackout.json's constants
def line_cells(a, b):
    (x0, z0), (x1, z1) = a, b
    n = int(max(abs(x1 - x0), abs(z1 - z0)))
    out = []
    for i in range(n + 1):
        c = (int(round(x0 + (x1 - x0) * i / n)), int(round(z0 + (z1 - z0) * i / n)))
        if not out or out[-1] != c:
            out.append(c)
    return out, math.dist(a, b) / max(1, len(out) - 1)


def crossing(g, a, b, sea):
    """(depths from the first to the last swimming cell, step, {end: dry}) on the straight line a -> b."""
    cells, step = line_cells(a, b)
    depth = [sea - g(x, z) for x, z in cells]
    wet = [i for i, d in enumerate(depth) if d > 1]
    if not wet:
        return [], step, {"from": True, "to": True}
    return depth[wet[0]:wet[-1] + 1], step, {"from": depth[0] <= 1, "to": depth[-1] <= 1}


def swim(depths, step, trained, surf, speed):
    """The blocks at which the fatigue hits land for a swimmer crossing the depths at `speed` blocks per second, as
    blackout_pack.py's surface/tick steps it every sample_ticks: land or one block of water (wading) recovers; two
    blocks builds gain_shallow, deep_water_blocks or more gain_deep, halved (integer) for a trained swimmer; past
    collapse_ticks one hit every pulse_ticks, the first on the sample collapse is reached."""
    per = surf["sample_ticks"]
    g_shallow, g_deep = surf["gain_shallow_per_tick"] * per, surf["gain_deep_per_tick"] * per
    rec, col, pulse, cap = surf["recover_per_tick"] * per, surf["collapse_ticks"], surf["pulse_ticks"], surf["cap_ticks"]
    fat, fpt, pos, hits, total = 0, pulse, 0.0, [], len(depths) * step
    while pos < total:
        pos += speed * per / 20.0
        d = depths[min(len(depths) - 1, int(pos / step))]
        if d <= 1:
            fat = max(0, fat - rec)
            if fat < col:
                fpt = pulse
            continue
        gain = g_deep if d >= surf["deep_water_blocks"] else g_shallow
        if trained:
            gain //= 2
        if fat < col:
            fpt = pulse
        fat = min(fat + gain, cap)
        if fat >= col:
            fpt += per
            if fpt >= pulse:
                fpt = 0
                hits.append(round(pos))
    return hits


def outcome(hits):
    return "no hit" if not hits else ("hit" if len(hits) < 2 else "knocked out")


def longest_swim(depths, step):
    run, best = 0, 0
    for d in depths:
        run = 0 if d <= 1 else run + 1
        best = max(best, run)
    return best * step


class Land:
    """Land-or-wade components on the heightmap (ground at the sea level - 1 or above: land, or one block of water,
    where a player stands with the head out), bounded to a box, found by flood fill from a seed."""

    def __init__(self, g, sea, box):
        import numpy as np
        self.np, self.box = np, box
        x0, z0, x1, z1 = box
        h = g.heights[z0 - g.oz:z1 - g.oz + 1, x0 - g.ox:x1 - g.ox + 1]
        self.walk = np.round(h).astype(int) >= sea - 1

    def cell(self, x, z):
        return z - self.box[1], x - self.box[0]

    def component(self, x, z, stop_at=None):
        """The component holding (x, z), as a mask; with stop_at, True as soon as that cell is reached instead."""
        np = self.np
        seen = np.zeros_like(self.walk)
        s = self.cell(x, z)
        if not (0 <= s[0] < seen.shape[0] and 0 <= s[1] < seen.shape[1]) or not self.walk[s]:
            return None if stop_at is None else False
        want = self.cell(*stop_at) if stop_at else None
        # a flood over each row's runs of land, not cell by cell (a cell-by-cell walk was 30 of the audit's 47 s): two
        # runs in neighbouring rows are 4-connected exactly when their columns overlap
        rows, starts, ends = self.runs()
        first = np.searchsorted(rows, np.arange(seen.shape[0] + 1)).tolist()      # each row's first run
        run_of = lambda r, c: first[r] + int(np.searchsorted(ends[first[r]:first[r + 1]], c, "right"))
        start = run_of(*s)
        got = {start}
        q = deque([start])
        while q:
            i = q.popleft()
            r = int(rows[i])
            for r2 in (r - 1, r + 1):
                if 0 <= r2 < seen.shape[0]:
                    lo, hi = first[r2], first[r2 + 1]
                    for j in range(lo + int(np.searchsorted(ends[lo:hi], starts[i], "right")),
                                   lo + int(np.searchsorted(starts[lo:hi], ends[i], "left"))):
                        if j not in got:
                            got.add(j)
                            q.append(j)
        if want is not None:
            a, b = want
            return bool(0 <= a < seen.shape[0] and 0 <= b < seen.shape[1] and self.walk[a, b] and run_of(a, b) in got)
        for i in got:
            seen[rows[i], starts[i]:ends[i]] = True
        return seen

    def runs(self):
        """(row, start, end) arrays of every run of walkable cells, row by row, ends exclusive; computed once."""
        if getattr(self, "_runs", None) is None:
            np = self.np
            edge = np.diff(np.pad(self.walk.astype(np.int8), ((0, 0), (1, 1))), axis=1)
            rows, starts = np.nonzero(edge == 1)
            _r, ends = np.nonzero(edge == -1)
            self._runs = (rows, starts, ends)
        return self._runs

    def touches_edge(self, mask, lo=0, hi=8191):
        """Whether the land reaches an edge of the box that is not the heightmap's own edge (x/z 0..8191, the
        authoring landmass: data/world.json), so it may continue outside the box."""
        x0, z0, x1, z1 = self.box
        return bool((z0 > lo and mask[0].any()) or (z1 < hi and mask[-1].any())
                    or (x0 > lo and mask[:, 0].any()) or (x1 < hi and mask[:, -1].any()))

    def nearest_other(self, mask, limit=SEARCH_MARGIN):
        """(gap, (x, z) on other land, (x, z) on the mask's land) for the nearest land not in the mask, by dilation
        (4- and 8-connected in turn, as the plan's appendix) and then the exact distance among the first hits and
        those within 9% more steps (the dilation's octagon is within 8% of a circle); None past `limit`."""
        np = self.np
        other = self.walk & ~mask
        front, hits, first = mask.copy(), [], None
        shore = mask & ~(np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1))
        sz, sx = np.nonzero(shore)
        for step in range(1, limit + 1):
            grown = front.copy()
            grown[1:, :] |= front[:-1, :]
            grown[:-1, :] |= front[1:, :]
            grown[:, 1:] |= front[:, :-1]
            grown[:, :-1] |= front[:, 1:]
            if step % 2 == 0:
                grown[1:, 1:] |= front[:-1, :-1]
                grown[:-1, :-1] |= front[1:, 1:]
                grown[1:, :-1] |= front[:-1, 1:]
                grown[:-1, 1:] |= front[1:, :-1]
            new = grown & other & ~front
            if new.any():
                zs, xs = np.nonzero(new)
                hits += list(zip(zs.tolist(), xs.tolist()))
                if first is None:
                    first = step
            front = grown
            if first is not None and step >= first * 1.09 + 2:
                break
        if not hits:
            return None
        best = None
        for hz, hx in hits[:4000]:
            d2 = (sz - hz) ** 2 + (sx - hx) ** 2
            k = int(np.argmin(d2))
            if best is None or d2[k] < best[0]:
                best = (int(d2[k]), (hx + self.box[0], hz + self.box[1]), (int(sx[k]) + self.box[0], int(sz[k]) + self.box[1]))
        return math.sqrt(best[0]), best[1], best[2]


def walk_both(g, sea, c, surf, speed):
    depths, step, dry = crossing(g, tuple(c["from"]), tuple(c["to"]), sea)
    return {"depths": depths, "step": step, "dry": dry, "swim": longest_swim(depths, step),
            "unaided": outcome(swim(depths, step, False, surf, speed)) if depths else "no hit",
            "trained": outcome(swim(depths, step, True, surf, speed)) if depths else "no hit"}


def swim_problems(doc, g, sea, surf, contracts=None, structure=True):
    """Every declared gate and leak, walked; each gate's island checked for a shorter way over."""
    out, report = [], []
    speed = float(doc["swim_model"]["speed_blocks_per_second"])
    c3 = {c["id"]: c for c in ((contracts or {}).get("C3") or {}).get("crossings") or []}
    for ln in doc["lines"]:
        sw = ln["swim"]
        kind = sw["declared"]
        # a retired line is not walked: its water no longer exists as declared (the Pacifidlog re-site drowned the
        # Sound crossing, and the water shape removed the Jungle Isle entirely). `retired_why` says what replaced it,
        # and the line is kept rather than deleted so the history of the crossing survives.
        if ln.get("status") == "retired":
            report.append("%-24s RETIRED: %s" % (ln["id"], str(ln.get("retired_why"))[:100]))
            continue
        if kind in ("kindness", "unsited"):
            report.append("%-24s %s: %s" % (ln["id"], kind, sw["why"][:90]))
            continue
        for c in sw.get("barriers") or []:
            if c.get("c3"):
                ref = c3.get(c["c3"])
                if ref is None:
                    out.append("line %s barrier %s: names C3 crossing %s, which data/system_contracts.json does not hold"
                               % (ln["id"], c["id"], c["c3"]))
                elif list(ref["from"]) != list(c["from"]) or list(ref["to"]) != list(c["to"]):
                    out.append("line %s barrier %s: its ends differ from C3's %s (%s -> %s): the two have drifted"
                               % (ln["id"], c["id"], c["c3"], ref["from"], ref["to"]))
            r = walk_both(g, sea, c, surf, speed)
            report.append("%-24s barrier %-22s length %4.0f, swim %4.0f: unaided %s, trained %s"
                          % (ln["id"], c["id"], math.dist(c["from"], c["to"]), r["swim"], r["unaided"], r["trained"]))
            if not r["depths"]:
                out.append("line %s barrier %s: no swimming on it at all" % (ln["id"], c["id"]))
                continue
            for end in c.get("dry_ends", ["from", "to"]):
                if not r["dry"][end]:
                    out.append("line %s barrier %s: its %s end is not land or wading water: re-measure it" % (ln["id"], c["id"], end))
            for who in ("unaided", "trained"):
                if r[who] != "knocked out":
                    out.append("line %s barrier %s: %s swimmer is not knocked out (%s): the %s is no gate here"
                               % (ln["id"], c["id"], {"unaided": "an unaided", "trained": "a trained"}[who], r[who], ln["name"]))
        for c in sw.get("leaks") or []:
            r = walk_both(g, sea, c, surf, speed)
            report.append("%-24s leak    %-22s length %4.0f, swim %4.0f: unaided %s, trained %s (declared a leak)"
                          % (ln["id"], c["id"], math.dist(c["from"], c["to"]), r["swim"], r["unaided"], r["trained"]))
            if r["unaided"] == "knocked out" and r["trained"] == "knocked out":
                out.append("line %s leak %s: no longer swimmable by anyone: the declaration is stale, declare the line "
                           "a gate" % (ln["id"], c["id"]))
            reach = c.get("reaches")
            if reach:
                x0, z0 = max(0, min(c["to"][0], reach[0]) - 400), max(0, min(c["to"][1], reach[1]) - 400)
                x1, z1 = min(8191, max(c["to"][0], reach[0]) + 400), min(8191, max(c["to"][1], reach[1]) + 400)
                if not Land(g, sea, (x0, z0, x1, z1)).component(c["to"][0], c["to"][1], stop_at=tuple(reach)):
                    out.append("line %s leak %s: its far end no longer walks to %s: the declaration is stale"
                               % (ln["id"], c["id"], reach))
                else:
                    report.append("%-24s leak    %-22s walks on land, wading and decks from %s to %s"
                                  % (ln["id"], c["id"], c["to"], reach))
        for c in sw.get("hops") or []:
            r = walk_both(g, sea, c, surf, speed)
            report.append("%-24s hop     %-22s length %4.0f, swim %4.0f: unaided %s, trained %s (inside the barriers)"
                          % (ln["id"], c["id"], math.dist(c["from"], c["to"]), r["swim"], r["unaided"], r["trained"]))
        if kind == "gate" and structure:
            out += island_problems(ln, g, sea, report)
    return out, report


def island_problems(ln, g, sea, report):
    """The island group (the seed's land and every hop's far side) must not be land-connected to any barrier's near
    side, and its nearest other land must be a barrier's near side, reached by that barrier in no more than the gap."""
    sw = ln["swim"]
    pts = [tuple(sw["island"])] + [tuple(h["from"]) for h in sw.get("hops") or []]
    pts += [tuple(h["to"]) for h in sw.get("hops") or []] + [tuple(b["to"]) for b in sw["barriers"]]

    def group_in(box):
        land = Land(g, sea, box)
        group = land.component(*sw["island"])
        if group is None:
            return land, None, "line %s: its island seed %s is not on land" % (ln["id"], sw["island"])
        for h in sw.get("hops") or []:
            m = land.component(*h["from"])
            if m is None:
                return land, None, "line %s hop %s: its near end %s is not on land" % (ln["id"], h["id"], h["from"])
            group = group | m
        return land, group, None

    # the heightmap is the authoring landmass, x/z 0..8191 (data/world.json). Grow the box until the island group's
    # land lies inside it, then search round the land's own extent
    clip = lambda x0, z0, x1, z1: (max(0, x0), max(0, z0), min(8191, x1), min(8191, z1))
    xs, zs = [p[0] for p in pts], [p[1] for p in pts]
    margin = 2 * SEARCH_MARGIN
    while True:
        box = clip(min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin)
        land, group, err = group_in(box)
        if err:
            return [err]
        if not land.touches_edge(group) or box == (0, 0, 8191, 8191):
            break
        margin *= 2
    gz, gx = land.np.nonzero(group)
    box = clip(int(gx.min()) + box[0] - SEARCH_MARGIN - 8, int(gz.min()) + box[1] - SEARCH_MARGIN - 8,
               int(gx.max()) + box[0] + SEARCH_MARGIN + 8, int(gz.max()) + box[1] + SEARCH_MARGIN + 8)
    land, group, err = group_in(box)
    if err:
        return [err]
    out = []
    for p in [tuple(b["to"]) for b in sw["barriers"]] + [tuple(h["to"]) for h in sw.get("hops") or []]:
        z, x = land.cell(*p)
        if not group[z, x]:
            out.append("line %s: the crossing end %s is not on the island group's land" % (ln["id"], p))
    for b in sw["barriers"]:
        z, x = land.cell(*b["from"])
        if group[z, x]:
            out.append("line %s barrier %s: its near end %s is on the island's own land: no water to cross"
                       % (ln["id"], b["id"], b["from"]))
    edge = land.touches_edge(group)
    near = land.nearest_other(group)
    if near is None:
        out.append("line %s: no other land within %d blocks of the island group: nothing to measure the gate from"
                   % (ln["id"], SEARCH_MARGIN))
        return out
    gap, there, here = near
    report.append("%-24s island  nearest other land %s from %s, %.0f blocks%s"
                  % (ln["id"], there, here, gap, " (the island's land reaches the search box's edge)" if edge else ""))
    if edge:
        out.append("line %s: the island group's land reaches the edge of the search box %s: it may join other land"
                   % (ln["id"], box))
    ok = []
    for b in sw["barriers"]:
        if math.dist(b["from"], b["to"]) <= gap * 1.1 + 8 and land.component(there[0], there[1], stop_at=tuple(b["from"])):
            ok.append(b["id"])
    if not ok:
        out.append("line %s: the island's nearest other land is %s, %.0f blocks from %s, and no declared barrier "
                   "starts on that land and is that short: walk that crossing and declare it (a barrier, or a hop "
                   "whose island is itself behind a barrier)" % (ln["id"], there, gap, here))
    return out


# ---- the generated output, against the data
def output_problems(doc, files):
    out = []
    docks = by_id(doc["docks"])
    fn = lambda rel: "data/%s/function/ferries/%s.mcfunction" % (NS, rel)
    lines = emitted_lines(doc)
    if not lines:
        out.append("no line has all its docks built: the pack would place no ferryman")
    for ln in lines:
        for a, b in trips(ln):
            path = fn("%s/%s_to_%s" % (ln["id"], a, b))
            body = files.get(path)
            if body is None:
                out.append("%s: no trip function" % path)
                continue
            cmds = [c for c in body if c and not c.startswith("#")]
            where = lambda pred: [i for i, c in enumerate(cmds) if pred(c)]
            query = where(lambda c: "cobbledollars query" in c)
            charge = where(lambda c: c.startswith("function %s:ferries/charge" % NS))
            refuse = where(lambda c: c.startswith("execute unless score @s %s matches" % SCORE))
            tp = where(lambda c: c.startswith("tp @s "))
            gates = where(lambda c: "advancements={" in c)
            cd_set = where(lambda c: c.startswith("scoreboard players operation @s %s" % COOLDOWN))
            cd_check = where(lambda c: c.startswith("execute if score @s %s > #now" % COOLDOWN))
            dismount = where(lambda c: c == "ride @s dismount")
            want = [g for g in ln.get("gates") or [] if g["kind"] == "flag"]
            if len(gates) != len(want):
                out.append("%s: %d gate checks for %d flag gates" % (path, len(gates), len(want)))
            if len(tp) != 1:
                out.append("%s: %d teleports, not 1" % (path, len(tp)))
                continue
            x, y, z = docks[b]["landing"]["at"]
            if cmds[tp[0]].split()[2:5] != [num(x + 0.5), str(y), num(z + 0.5)]:
                out.append("%s: teleports to %s, not the landing of %s %s" % (path, cmds[tp[0]], b, [x, y, z]))
            if not (cd_check and cd_check[0] < min(gates + query + charge + tp)):
                out.append("%s: the cooldown is not checked before everything else" % path)
            if not (dismount and dismount[0] < tp[0]):
                out.append("%s: no dismount before the teleport" % path)
            if ln["fare"] == 0:
                if query or charge or any("cobbledollars" in c for c in cmds):
                    out.append("%s: a free line touches CobbleDollars" % path)
                continue
            if len(charge) != 1:
                out.append("%s: %d charges, not 1" % (path, len(charge)))
                continue
            if len(query) != 2 or not (query[0] < refuse[0] < charge[0] < query[1] < tp[0] if refuse else False):
                out.append("%s: not read, refuse-if-short, charge, re-read, then travel (reads %s, refusal %s, charge %s, tp %s)"
                           % (path, query, refuse, charge, tp))
            if refuse and cmds[refuse[0]].split()[6] != "%d.." % ln["fare"]:
                out.append("%s: refuses below %s, not the fare %d" % (path, cmds[refuse[0]].split()[6], ln["fare"]))
            amount = [c for c in cmds if c.startswith("data modify storage %s charge.amount set value" % STORAGE)]
            if amount != ["data modify storage %s charge.amount set value %d" % (STORAGE, ln["fare"])]:
                out.append("%s: charges %s, not the fare %d" % (path, amount, ln["fare"]))
            if gates and max(gates) > charge[0]:
                out.append("%s: a gate is checked after the charge" % path)
            if not (cd_set and cd_set[0] < charge[0]):
                out.append("%s: the cooldown is not set before the charge (a second submit could pay twice)" % path)
            verify = where(lambda c: c.startswith("execute unless score #after %s = #want" % SCORE))
            if not (verify and query[1] < verify[0] < tp[0]):
                out.append("%s: the charge is not verified before the teleport" % path)
    # the charge macro is only generated when a built line actually charges a fare (the generator does the same),
    # so its absence is correct when every built line is free -- as it is since the Sound ferry retired. When it is
    # there it must still be the blackout's proven form, and when a paid trip exists it must be there.
    charge = files.get(fn("charge"))
    paid = any(any(c.startswith("function %s:ferries/charge" % NS) for c in v)
               for k, v in files.items() if k.endswith(".mcfunction") and k != fn("charge"))
    if paid and charge is None:
        out.append("a trip charges a fare but the charge macro was not generated")
    elif charge is not None and charge != ["$cobbledollars remove @s $(amount)"]:
        out.append("the charge macro is %r, not the blackout's proven form" % charge)
    for rel, body in files.items():
        if rel.endswith(".mcfunction"):
            refused = function_limits.check_lines(body, rel)
            if refused:
                out.append("%s: %d command(s) the server would refuse" % (rel, len(refused)))
    # every built dock's dialogue offers exactly its trips, gated options hidden from those who do not qualify
    for d in {s for ln in lines for s in ln["stops"]}:
        dlg = files.get("data/%s/dialogues/dlg_ferry_%s.json" % (NS, d))
        npc = files.get("data/%s/npcs/npc_ferry_%s.json" % (NS, d))
        if dlg is None or npc is None:
            out.append("dock %s: no compiled dialogue or NPC class" % d)
            continue
        opts = dlg["pages"][0]["input"]["options"]
        want = {("%s_to_%s" % (a, b), ln["id"], bool(ln.get("gates"))) for ln in lines for a, b in trips(ln) if a == d}
        got = set()
        for o in opts:
            m = re.search(r"function %s:ferries/([a-z0-9_]+)/([a-z0-9_]+)'" % NS, o["action"])
            if m:
                got.add((m.group(2), m.group(1), "isVisible" in o))
        if got != want:
            out.append("dock %s: its dialogue offers %s, the data %s" % (d, sorted(got), sorted(want)))
    return out


def audit(doc, source_root=None, contracts=None, structure=True):
    import progression_pack as PP
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    planned = {f["id"] for f in PP.plan(prog, placements=placements)["flags"]}
    problems = static_problems(doc, prog, planned)
    report = []
    if problems:
        return problems, report
    files, _ = build(doc)
    problems += output_problems(doc, files)
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    sea = int(world["vertical"]["sea_level"])
    gcache = {}
    p, r = dock_problems(doc, placements, gcache, source_root, sea)
    problems += p
    report += r
    blackout = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))
    import ground as G
    g = G.for_settlement("relic_island", base=G.for_settlement("sea_town", base=G.Ground(source_root)))
    contracts = contracts if contracts is not None else json.loads((ROOT / "data" / "system_contracts.json").read_text(encoding="utf-8"))
    p, r = swim_problems(doc, g, sea, blackout["surface"], {c["id"]: c for c in contracts.get("contracts") or []}, structure)
    return problems + p, report + r


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default=str(DATA))
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(DEFAULT_OUT))
    b.add_argument("--source-root", help="unused: the build needs no heightmap (accepted so prepare passes it alike)")
    a = sub.add_parser("audit")
    a.add_argument("--source-root")
    m = sub.add_parser("measure")
    m.add_argument("x", type=int)
    m.add_argument("z", type=int)
    m.add_argument("--source-root")
    args = p.parse_args(argv)
    doc = load(args.data) if args.cmd != "measure" else None
    if args.cmd == "build":
        files, npcs = build(doc)
        write(files, args.out)
        lines = emitted_lines(doc)
        print("wrote %d files to %s: %d lines built of %d (%s), %d ferrymen"
              % (len(files), args.out, len(lines), len(doc["lines"]), ", ".join(ln["id"] for ln in lines), len(npcs)))
        return 0
    if args.cmd == "measure":
        import ground as G
        g = G.for_settlement("relic_island", base=G.for_settlement("sea_town", base=G.Ground(args.source_root)))
        box = (max(0, args.x - 2 * SEARCH_MARGIN), max(0, args.z - 2 * SEARCH_MARGIN),
               min(8191, args.x + 2 * SEARCH_MARGIN), min(8191, args.z + 2 * SEARCH_MARGIN))
        land = Land(g, 62, box)
        mask = land.component(args.x, args.z)
        if mask is None:
            print("(%d, %d) is not land or wading water" % (args.x, args.z))
            return 1
        print("land cells %d%s; nearest other land: %s" % (int(mask.sum()), " (reaches the box edge)" if land.touches_edge(mask) else "",
                                                           land.nearest_other(mask)))
        return 0
    problems, report = audit(doc, args.source_root)
    for line in report:
        print(line)
    for pr in problems:
        print("PROBLEM", pr)
    print("ferry audit: %d problems" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
