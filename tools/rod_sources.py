#!/usr/bin/env python
"""Every rod Cobblemon 1.8.0 registers, and every way a player gets it in this campaign.

  python tools/rod_sources.py            print each rod with its sources; exit 1 on a problem
  python tools/rod_sources.py --brief    only the rods that have a source other than crafting, and the verdict
  python tools/rod_sources.py --jar <path-to-Cobblemon-jar>
                                         also compare data/fishermen.json's rod universe with the jar's rod models and
                                         recipes (default: $COBBLERS_SERVER_ROOT/mods/Cobblemon-fabric-1.8.0+1.21.1.jar
                                         when it exists; the jar is only read)

THE OWNER (2026-10-12): "I need a check to make sure we have more fisherman NPCs handing out some rods throughout the
game; doesn't have to be every rod." Docs/STATE.md "Every Cobblemon item is obtainable without crafting" is the rule
behind it: crafting stays allowed, but a no-crafting run must be able to reach the rods that matter.

WHAT IT READS, and nothing derived from the table that makes the fishermen: data/quests.json (a reward whose contents
name a rod, the grant_reward_once that gives it, the transition's conditions), data/dialogue.json (the conversation of
that quest and its NPC), data/rewards.json, data/markets.json, data/direct_trades.json, data/traders.json, and every other
file in data/ for an exact "cobblemon:<rod>" string. data/fishermen.json is read only for the rod universe (48 ids, from the
jar) and the two floors this check enforces (check.min_npc_rods, check.min_waters).

A SOURCE, by kind:
  NPC     a quest reward of the rod, given by grant_reward_once in a transition, that a conversation with an npc_id runs, and
          that NPC is placed by a file (npc_seats.json, scenes.json, ...). Reported with the gate (the flag the transition
          requires) and whether the NPC is placed.
  find    a data/rewards.json cache or a loot table naming the rod.
  shop    an exact id in a stall, trader or direct trade.
  lent    the rod is handed out and taken back (the dungeon fishing room's Lent Rod): not a source.
  craft   every rod is a smithing-table recipe (jar): the Poke Rod smithing template, a vanilla fishing rod and the rod's
          ball. Reported with the ball, so a rod whose ball is itself unobtainable is visible.

PROBLEMS (exit 1): an exact cobblemon:*_rod id in data/ that is not in the universe (a typo), an NPC rod whose chain is broken
(no grant, no conversation, no NPC, NPC placed by nothing), a stronger rod (any but poke_rod) given with no badge flag in
the transition's conditions, fewer distinct NPC rods than check.min_npc_rods, fewer fishermen than check.min_waters.

NOT COVERED (CLAUDE.md "Our list is not the world"): a rod a mod or a donor template places in the world, a Cobblemon loot
table we did not override (chests in vanilla structures), and a rod somebody trades player to player. Whether the ball in a
rod changes what a rod catches is not researched (docs/STATE.md "Early fishing balance"). Nothing here was seen in game.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ROD_ID = re.compile(r"cobblemon:([a-z0-9_]+_rod)\b")
JAR_NAME = "Cobblemon-fabric-1.8.0+1.21.1.jar"
# a rod handed out and taken back: not a source. (file, dotted path) -> why
LENT = {("dungeon_extras2.json", "fishing.rod.id"): "the dungeon fishing room's Lent Rod, taken back at a run's end"}


def jload(rel):
    return json.loads((DATA / rel).read_text(encoding="utf-8"))


def universe():
    doc = jload("fishermen.json")
    return ["cobblemon:" + i for i in doc["rod_universe"]["ids"]], doc


def ball_of(rod_id):
    """The ball a rod's recipe takes: cobblemon:<name>_rod -> cobblemon:<name>_ball (the jar's 48 recipes all follow it)."""
    return rod_id[: -len("_rod")] + "_ball"


def walk(value, path=()):
    """Every (path, string) under a JSON value; a list index is part of the path."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from walk(v, path + (str(k),))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, path + (str(i),))
    elif isinstance(value, str):
        yield path, value


def jar_universe(jar):
    """({rod ids with an item model}, {rod ids with a recipe}) read from the jar; the smithing template is not a rod."""
    with zipfile.ZipFile(jar) as z:
        names = z.namelist()
    models = {re.search(r"models/item/([a-z0-9_]+_rod)\.json$", n).group(1) for n in names
              if re.search(r"assets/cobblemon/models/item/[a-z0-9_]+_rod\.json$", n)}
    recipes = {re.search(r"recipe/([a-z0-9_]+_rod)\.json$", n).group(1) for n in names
               if re.search(r"data/cobblemon/recipe/[a-z0-9_]+_rod\.json$", n)}
    return {"cobblemon:" + m for m in models}, {"cobblemon:" + r for r in recipes}


def find_jar(arg):
    if arg:
        return Path(arg)
    root = os.environ.get("COBBLERS_SERVER_ROOT")
    if root:
        p = Path(root) / "mods" / JAR_NAME
        if p.exists():
            return p
    return None


def other_files_naming(*needles, skip=()):
    """The data files (not the ones in skip) in which any of the exact strings appears as a JSON string value."""
    out = []
    for f in sorted(DATA.glob("*.json")):
        if f.name in skip:
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if any(s in needles for _p, s in walk(doc)):
            out.append(f.name)
    return out


def npc_sources(rods):
    """[{rod, quest, reward, npc, conversation, gate flags, placed_by, problems}] for every quest reward that names a rod."""
    quests = jload("quests.json")["quests"]
    convs = {c["id"]: c for c in jload("dialogue.json")["conversations"]}
    by_quest = {}
    for c in convs.values():
        by_quest.setdefault(c["quest_id"], []).append(c)
    out = []
    for q in quests:
        for rw in q.get("rewards") or []:
            for item in (rw.get("contents") or []):
                rod = item.get("item")
                if rod not in rods:
                    continue
                rec = {"rod": rod, "quest": q["id"], "reward": rw["id"], "npc": None, "conversation": None,
                       "gates": [], "placed_by": [], "problems": []}
                gives = [t for t in q.get("transitions") or []
                         if any(e.get("kind") == "grant_reward_once" and e.get("reward") == rw["id"]
                                for e in t.get("effects") or [])]
                if not gives:
                    rec["problems"].append("%s: reward %s is never given by a grant_reward_once transition" % (q["id"], rw["id"]))
                for t in gives:
                    for c in t.get("conditions") or []:
                        if c.get("kind") == "flag":
                            rec["gates"].append(c["flag"])
                for c in by_quest.get(q["id"], []):
                    if c.get("npc_id"):
                        rec["npc"], rec["conversation"] = c["npc_id"], c["id"]
                        runs = [a.get("transition") for n in c["nodes"] for a in n.get("actions_after_acknowledge") or []
                                if a.get("kind") == "quest_transition"]
                        if not any(t["id"] in runs for t in gives):
                            rec["problems"].append("%s: no node of %s runs the giving transition" % (q["id"], c["id"]))
                        # a rule that stops a player below the gate before the give is the conversation's own gate
                        rec["entry_gate"] = sorted({r["when"].get("condition", {}).get("flag")
                                                    for r in c.get("entry_rules") or []
                                                    if r["when"].get("kind") == "not"
                                                    and r["when"].get("condition", {}).get("kind") == "flag"})
                if rec["npc"] is None:
                    rec["problems"].append("%s: no conversation with an npc_id runs this quest" % q["id"])
                else:
                    rec["placed_by"] = other_files_naming(rec["npc"], rec["conversation"],
                                                          skip=("dialogue.json", "quests.json", "progression.json",
                                                                "fishermen.json"))   # the table that makes them places nothing
                    if not rec["placed_by"]:
                        rec["problems"].append("%s: NPC %s / %s is placed by no file in data/" % (q["id"], rec["npc"], rec["conversation"]))
                out.append(rec)
    return out


def exact_hits(rods, universe_ids):
    """[(rod id, file, dotted path)] for every data file string that is exactly cobblemon:<x>_rod, and [(string, file)] for
    ids of that shape the universe does not know."""
    hits, unknown = [], []
    for f in sorted(DATA.glob("*.json")):
        if f.name in ("fishermen.json",):
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for path, s in walk(doc):
            for m in ROD_ID.finditer(s):
                rid = "cobblemon:" + m.group(1)
                if rid not in universe_ids:
                    unknown.append((rid, f.name))
                if s == rid:
                    hits.append((rid, f.name, ".".join(path)))
    return hits, unknown


def gather(jar=None):
    ids, doc = universe()
    rods = set(ids)
    probs = []
    jar = find_jar(jar)
    jar_note = "jar not read (set COBBLERS_SERVER_ROOT or pass --jar)"
    if jar is not None and jar.exists():
        models, recipes = jar_universe(jar)
        if models != rods or recipes != rods:
            probs.append("data/fishermen.json rod_universe differs from the jar: models-only %s, recipes-only %s, "
                         "table-only %s" % (sorted(models - rods), sorted(recipes - rods), sorted(rods - models)))
        jar_note = "universe checked against %s (%d models, %d recipes)" % (jar.name, len(models), len(recipes))
    npcs = npc_sources(rods)
    hits, unknown = exact_hits(rods, rods)
    for rid, f in unknown:
        probs.append("%s names %s, which is not a rod Cobblemon 1.8.0 registers" % (f, rid))
    table = {}
    for rid in ids:
        table[rid] = {"npc": [], "find": [], "shop": [], "lent": [], "craft": "smithing: Poke Rod template + minecraft:fishing_rod + " + ball_of(rid)}
    for n in npcs:
        table[n["rod"]]["npc"].append(n)
        probs += n["problems"]
        if n["rod"] != "cobblemon:poke_rod" and not n["gates"]:
            probs.append("%s gives %s with no badge flag in its transition's conditions: a stronger rod needs a gate" % (n["quest"], n["rod"]))
        if n["rod"] != "cobblemon:poke_rod" and n["npc"] and not n.get("entry_gate"):
            probs.append("%s: %s opens with no entry rule that turns a player below the gate away before the offer" % (n["quest"], n["conversation"]))
    for rid, f, path in hits:
        if f == "quests.json":
            continue                               # counted above, as an NPC reward with its chain
        lent = next((w for (lf, lp), w in LENT.items() if f == lf and path.endswith(lp)), None)
        if lent:
            table[rid]["lent"].append("%s (%s)" % (f, lent))
        elif f == "rewards.json":
            table[rid]["find"].append("%s %s" % (f, path))
        elif f in ("markets.json", "direct_trades.json", "traders.json"):
            table[rid]["shop"].append("%s %s" % (f, path))
        else:
            table[rid]["find"].append("%s %s" % (f, path))
    n_rods = {n["rod"] for n in npcs if not n["problems"]}
    n_men = {n["npc"] for n in npcs if not n["problems"]}
    chk = doc["check"]
    if len(n_rods) < chk["min_npc_rods"]:
        probs.append("only %d distinct rods are handed out by an NPC (%s), the floor is %d (data/fishermen.json check.min_npc_rods)"
                     % (len(n_rods), ", ".join(sorted(r.split(":")[1] for r in n_rods)) or "none", chk["min_npc_rods"]))
    if len(n_men) < chk["min_waters"]:
        probs.append("only %d NPCs hand out a rod, the floor is %d (check.min_waters)" % (len(n_men), chk["min_waters"]))
    table_men = {f["id"] for f in doc["fishermen"]}
    for missing in sorted(table_men - n_men):
        probs.append("data/fishermen.json lists %s but no resolved NPC rod chain in data/ belongs to it (run tools/fishermen.py write)" % missing)
    return {"table": table, "problems": probs, "jar_note": jar_note, "ids": ids, "npcs": npcs}


def render(g, brief=False):
    lines = []
    for rid in g["ids"]:
        t = g["table"][rid]
        has = t["npc"] or t["find"] or t["shop"]
        if brief and not has:
            continue
        parts = []
        for n in t["npc"]:
            gate = "/".join(n["gates"]) or "ungated"
            parts.append("NPC %s (%s, %s; placed by %s)" % (n["npc"], n["quest"], gate, ", ".join(n["placed_by"]) or "NOTHING"))
        parts += ["find " + s for s in t["find"]]
        parts += ["shop " + s for s in t["shop"]]
        parts += ["lent " + s for s in t["lent"]]
        if not brief:
            parts.append("craft: " + t["craft"].split(": ", 1)[1])
        lines.append("%-26s %s" % (rid.split(":")[1], "; ".join(parts)))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jar")
    ap.add_argument("--brief", action="store_true")
    a = ap.parse_args(argv)
    g = gather(a.jar)
    for l in render(g, a.brief):
        print(l)
    n_rods = {n["rod"] for n in g["npcs"] if not n["problems"]}
    print("%d rods registered; %d handed out by %d NPC(s); %s" % (
        len(g["ids"]), len(n_rods), len({n["npc"] for n in g["npcs"] if not n["problems"]}), g["jar_note"]))
    for p in g["problems"]:
        print("  PROBLEM " + p)
    print("rod sources: %s" % ("clean" if not g["problems"] else "%d problem(s)" % len(g["problems"])))
    return 1 if g["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
