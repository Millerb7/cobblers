#!/usr/bin/env python
"""The Haven Compact's story points (data/compact_points.json, data/compact_trainers.json): CP-04 the Records Run,
CP-12 the Crater Activation and CP-14 the Split Goes Public (docs/story/HAVEN_COMPACT_PASS.md section 3).

Every point is the design's M2: Cobblemon NPCs that talk and then fight. This tool turns the one authored file into
everything the existing runtime already reads, so nothing new runs in game except one battle_victory callback:

  the records   --write splices, from data/compact_points.json, one optional quest per point (data/quests.json), one
                conversation per NPC (data/dialogue.json), every field they use (data/progression.json quest_fields)
                and a presence probe per NPC (data/world_probes.json places.compact_*). Each NPC is a list of STATES,
                first match wins: an entry rule per state on THIS player's stage window and fields, the state's lines
                in order, and for a fighter's battle state a choice whose npc_battle (tools/compile_dialogue.py
                battle_action: singles, the level-cap refusal on over_cap_node) starts the NPC's battle. Without
                --write the same records are compared with data/ and any difference is reported as DRIFT.
  the pack      build writes build/datapacks/cobblers_compact: the battle_victory callback (the arena's in-game-proven
                shape, as tools/hq_tower.py fight_files) that runs a fighter's won function as the WINNING player
                when that fighter's NPC (matched by its fixed seat, radius RADIUS) is on the losing side, and one won
                function per fighter writing its `<who>_defeated` field into that player's data.
  the NPCs      npc_placements() is what reapply step R18CP spawns (each class compiled into cobblers_dialogue by
                tools/compile_dialogue.py, which gives a fighter's class its party from data/compact_trainers.json).
  check         the offline gate: seats on the heightmap (tools/ground.py, rounded) and off the road, the callback's
                radius clear of every other NPC we seat, teams under the next leader's ace, the species signature,
                each fighter's field, the crater flag's setter, no stage or badge written, and DRIFT.
  legality      every move, ability and species against a Cobblemon jar (--jar), written nowhere: its result is
                quoted in data/compact_trainers.json move_legality.
  verify        the world probe over RCON (needs the server lock): one cobblemon:npc at each seat, facing its yaw
                (tools/npc_seats.py verify, the same probe the settlement NPCs use).

What this does NOT cover (CLAUDE.md "Our list is not the world"): the seat sweep reads every coordinate in data/,
not the world, so a mod's or a donor's entity near a seat is not seen; the 'no heal between fights' of the design's
fallback is not enforced (nothing can tell a heal happened); two players fighting one NPC at once is unrun; the
dialogue route of npc_battle is NOT yet run in game (tools/compile_dialogue.py:43).

  python tools/compact_points.py [check] [--source-root R]
  python tools/compact_points.py write          splice the records into data/
  python tools/compact_points.py build          write the pack
  python tools/compact_points.py legality --jar <Cobblemon-fabric-1.8.0+1.21.1.jar>
  python tools/compact_points.py verify [--server-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

SPEC = ROOT / "data" / "compact_points.json"
TEAMS = ROOT / "data" / "compact_trainers.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_compact"
NS = "cobblers"
FOLDER = "compact"
CALLBACK = "data/cobblemon/callbacks/battle_victory/cobblers_compact.molang"
STAGE = "quest.main_worldshift_reveal.stage"
RADIUS = 1.5             # the callback's match on a fighter's seat (tools/hq_tower.py's finale fights use the same)
MIN_ROUTE = 5.0          # blocks from any walked route line (data/route_paths.json): nobody stands in the road (O2)
MIN_OTHER = 4.0          # blocks from any other coordinate data/ records: a seat is not stacked on someone else's
MIN_OWN = 2 * RADIUS + 1  # between two of our NPCs: neither falls inside the other's callback match
OVER_CAP = ("Not with that one in your party. It is past what your badges let you command. "
            "Put it in the PC and come back.")
PLACEHOLDER = ("Claude, 2026-10-11 (unit CP-CORE): functional stand-in lines for Codex to replace (the design's O10 "
               "default), written from docs/story/HAVEN_COMPACT_PASS.md section 3 and ARC.md rules 3-5.")
# the leader whose ace each point's teams stay under (the design's test list: 'every team's top level is under the
# next leader's ace'); read from data/trainers.json, never written here
NEXT_LEADER = {"gym3_town": "gym_03_surge", "gym7_town": "gym_07_blaine", "gym8_town": "gym_08_giovanni"}
VARGA_TOWER = ("hq_trainers.json", "hq_tower_trainer_07")
# Varga's lines' pre-evolutions, which have a wild home (only Excadrill of her four is homeless, as the design says);
# fixed by her tower team (Crobat, Gigalith, Drapion, Excadrill), so exempt from the species signature
SIGNATURE_EXEMPT = {"zubat", "golbat", "roggenrola", "boldore", "skorupi", "drilbur"}
OWN_FILES = {"compact_points.json", "compact_trainers.json"}


class CompactError(SystemExit):
    pass


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load():
    return _read(SPEC)


def teams():
    return {t["id"]: t for t in _read(TEAMS)["trainers"]}


def stages():
    prog = _read(ROOT / "data" / "progression.json")
    return next(f for f in prog["quest_fields"] if f["id"] == STAGE)["allowed_values"]


# ------------------------------------------------------------------------------------------------- names
def short(npc):
    """npc_compact_cp04_courier_1 -> courier_1: the speaker, the node prefix and the field stem."""
    m = re.fullmatch(r"npc_compact_cp\d\d_([a-z0-9_]+)", npc["id"])
    if not m:
        raise CompactError("NPC id %r is not npc_compact_cpNN_<who>" % npc["id"])
    return m.group(1)


def conv_id(npc):
    return "dlg_" + npc["id"][len("npc_"):]


def field(point, name):
    return "quest.%s.%s" % (point["quest"], name)


def defeated(point, npc):
    return field(point, "%s_defeated" % short(npc))


def cursor(point, npc):
    return field(point, "%s_cursor" % short(npc))


def yaw(npc):
    """Minecraft yaw facing from the seat to npc["faces"]: 0 faces +z, 90 faces -x."""
    (x, _y, z), (fx, fz) = npc["at"], npc["faces"]
    return int(round(math.degrees(math.atan2(-(fx - x), fz - z))))


def window(point):
    st = stages()
    return st[st.index(point["window"]):]


# ------------------------------------------------------------------------------------------------- conditions
def cond(point, npc, tok):
    if tok == "window":
        return {"kind": "progression_in", "field": STAGE, "values": window(point)}
    if tok == "defeated":
        return {"kind": "progression_equals", "field": defeated(point, npc), "value": True}
    if tok == "closed":
        c = point.get("closed_when")
        if not c:
            raise CompactError("%s: state reads 'closed' but the point has no closed_when" % npc["id"])
        return {"kind": "all", "conditions": [
            {"kind": "any", "conditions": [{"kind": "flag", "flag": f} for f in c["any_flag"]]}] + [
            {"kind": "progression_equals", "field": field(point, u), "value": False} for u in c["unless"]]}
    if tok.startswith("!"):
        return {"kind": "progression_equals", "field": field(point, tok[1:]), "value": False}
    return {"kind": "progression_equals", "field": field(point, tok), "value": True}


def when(point, npc, toks, extra=()):
    cs = [cond(point, npc, t) for t in toks] + list(extra)
    if not cs:
        return {"kind": "always"}
    return cs[0] if len(cs) == 1 else {"kind": "all", "conditions": cs}


# ------------------------------------------------------------------------------------------------- records
def conversation(point, npc, trainer_ids):
    who = short(npc)
    nodes, rules = [], []
    states = npc["states"]
    if states[-1]["when"]:
        raise CompactError("%s: the last state must have no conditions (it is the 'always' rule)" % npc["id"])
    fights = [s for s in states if s.get("fight")]
    if bool(fights) != bool(npc.get("fight")) or len(fights) > 1:
        raise CompactError("%s: a fighter has exactly one battle state, a talker none" % npc["id"])
    for i, st in enumerate(states):
        ids = ["%s_%s_%d" % (who, st["id"], k + 1) for k in range(len(st["lines"]))]
        choice = "%s_%s_choice" % (who, st["id"])
        for k, (nid, text) in enumerate(zip(ids, st["lines"])):
            last = k == len(ids) - 1
            node = {"id": nid, "kind": "line", "speaker": who, "text": text,
                    "next": ids[k + 1] if not last else (choice if st.get("fight") else nid)}
            if last and st.get("ack"):
                node["actions_after_acknowledge"] = [{"kind": "quest_transition", "transition": st["ack"]}]
            nodes.append(node)
        base = 10 * (i + 1)
        if st.get("fight"):
            f = st["fight"]
            over = "%s_over_cap" % who
            nodes.append({"id": choice, "kind": "choice", "speaker": who, "text": f["prompt"], "responses": [
                {"id": "r_fight", "text": f["yes"],
                 "actions": [{"kind": "npc_battle", "format": "singles", "over_cap_node": over}]},
                {"id": "r_not_yet", "text": f["no"], "actions": [{"kind": "close_dialogue"}]}]})
            nodes.append({"id": over, "kind": "line", "speaker": who, "text": OVER_CAP, "next": choice})
            rules.append({"priority": base, "when": when(point, npc, st["when"], [
                {"kind": "progression_equals", "field": cursor(point, npc), "value": choice}]), "node": choice,
                "why": "a player who left on the choice (a loss, a flee, 'not yet') is offered the battle again"})
        rule = {"priority": base + 5, "when": when(point, npc, st["when"]), "node": ids[0]}
        if st.get("actions"):
            rule["actions"] = [{"kind": "quest_transition", "transition": t} for t in st["actions"]]
        rule["why"] = "state %s" % st["id"]
        rules.append(rule)
    conv = {
        "id": conv_id(npc),
        "quest_id": point["quest"],
        "npc_id": npc["id"],
        "npc_name": npc["name"],
        "scope": "player",
        "generated_by": "tools/compact_points.py --write, from data/compact_points.json %s" % point["id"],
        "source": "docs/story/HAVEN_COMPACT_PASS.md section 3 %s; data/compact_points.json" % point["design"],
        "placeholder": PLACEHOLDER,
        "cursor": {"progression_field": cursor(point, npc), "initial_node": "%s_%s_1" % (who, states[-1]["id"]),
                   "persist": "after_each_node",
                   "restore": "on_every_interaction", "cursor_is": "next_unread_node"},
        "entry_rules": rules,
        "nodes": nodes,
        "speakers": {who: npc["name"]},
    }
    if npc.get("fight"):
        f = npc["fight"]
        if f["trainer"] not in trainer_ids:
            raise CompactError("%s: trainer %s is not in data/compact_trainers.json" % (npc["id"], f["trainer"]))
        conv["npc_battle"] = {"trainers": TEAMS.name, "trainer": f["trainer"], "skill": f["skill"]}
    return conv


def quest(point):
    fighters = [n for n in point["npcs"] if n.get("fight")]
    objectives = []
    for n in fighters:
        st = next(s for s in n["states"] if s.get("fight"))
        prior = [t for t in st["when"] if t != "window"]
        o = {"id": short(n), "complete_when": {"field": defeated(point, n), "equals": True},
             "text": "Beat %s." % n["name"]}
        if prior:
            o["active_when"] = {"field": field(point, prior[-1].lstrip("!")), "equals": not prior[-1].startswith("!")}
        objectives.append(o)
    transitions = []
    for t in point["transitions"]:
        tr = {"id": t["id"],
              "conditions": [{"kind": "progression_equals", "field": field(point, r.lstrip("!")),
                              "value": not r.startswith("!")} for r in t["requires"]],
              "effects": [{"kind": "set_progression", "field": field(point, s), "value": True} for s in t["sets"]]}
        if t.get("function"):
            tr["effects"].append({"kind": "function", "function": t["function"]})
        if t.get("why"):
            tr["why"] = t["why"]
        transitions.append(tr)
    return {
        "id": point["quest"],
        "source": "docs/story/HAVEN_COMPACT_PASS.md section 3 %s" % point["design"],
        "generated_by": "tools/compact_points.py --write, from data/compact_points.json %s" % point["id"],
        "scope": "player",
        "optional": True,
        "optional_why": "the design: 'No point gates a badge unless the owner says so (O3)'",
        "window": "THIS player's %s at %s or later (%s); the conversations' entry rules read it, the quest cannot "
                  "(a quest names only its own fields)" % (STAGE, point["window"], point["window_why"]),
        "serves": point["serves"],
        "progression_gate": [],
        "availability": {"conditions": [], "repeatable": False, "npc_remains_after_completion": True},
        "dialogue_ids": [conv_id(n) for n in point["npcs"]],
        "objectives": objectives,
        "transitions": transitions,
        "rewards": [],
        "battle_result_setter": "the cobblers_compact pack's battle_victory callback (tools/compact_points.py), as "
                                "the winning player: one won function per fighter writes its *_defeated field",
        "multiplayer": {"state": "per_player", "npcs": "shared static Cobblemon NPCs; each player meets them at "
                        "their own stage", "concurrent_players": "independent fields; whether two players may "
                        "battle one NPC at once is not known (EXP-091)"},
        "progression_field_refs": [f["id"] for f in fields(point)],
    }


def fields(point):
    out, seen = [], set()

    def add(fid, rec):
        if fid not in seen:
            seen.add(fid)
            out.append(rec)
    q = point["quest"]
    for n in point["npcs"]:
        add(cursor(point, n), {"id": cursor(point, n), "quest_id": q, "field": "%s_cursor" % short(n),
                               "type": "enum", "scope": "player", "initial": "%s_%s_1" % (short(n), n["states"][-1]["id"]),
                               "allowed_values": "node ids from %s" % conv_id(n)})
    for n in point["npcs"]:
        if n.get("fight"):
            add(defeated(point, n), {"id": defeated(point, n), "quest_id": q, "field": "%s_defeated" % short(n),
                                     "type": "boolean", "scope": "player", "initial": False,
                                     "set_by": "the cobblers_compact battle_victory callback (tools/compact_points.py)"})
    for t in point["transitions"]:
        for s in t["sets"]:
            add(field(point, s), {"id": field(point, s), "quest_id": q, "field": s, "type": "boolean",
                                  "scope": "player", "initial": False, "set_by": "transition %s" % t["id"]})
    return out


def probes(point):
    return [{"what": "%s (%s), after R18CP" % (n["name"], n["id"]),
             "entity": "@e[type=cobblemon:npc,x=%d,y=%d,z=%d,distance=..2]" % tuple(n["at"]),
             "count": 1, "hold": list(n["at"])} for n in point["npcs"]]


def records(spec=None):
    spec = spec or load()
    tids = set(teams())
    return {
        "dialogue": [conversation(p, n, tids) for p in spec["points"] for n in p["npcs"]],
        "quests": [quest(p) for p in spec["points"]],
        "fields": [f for p in spec["points"] for f in fields(p)],
        "probes": {"compact_%s" % p["id"].split("_", 1)[0]: probes(p) for p in spec["points"]},
    }


# ------------------------------------------------------------------------------------------------- splicing
def splice(path, key, owned, recs, write):
    """Replace this tool's run of records in the top-level array `key` (contiguous, wherever it stands), or append
    them at the array's end, without re-serialising anything else (these files are hand-formatted). Returns True when
    the file already holds exactly `recs`."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r'^  "%s": \[' % re.escape(key), text, re.M)
    if not m:
        raise CompactError("%s has no top-level array %r" % (path.name, key))
    dec = json.JSONDecoder()
    spans, i = [], m.end()
    while True:
        while text[i] in " \t\r\n,":
            i += 1
        if text[i] == "]":
            close = i
            break
        obj, j = dec.raw_decode(text, i)
        spans.append((i, j, obj))
        i = j
    mine = [k for k, (_, _, o) in enumerate(spans) if owned(o)]
    if mine and mine != list(range(mine[0], mine[0] + len(mine))):
        raise CompactError("%s: this tool's records are not one run (positions %s): put them together by hand"
                           % (path.name, mine))
    same = [spans[k][2] for k in mine] == json.loads(json.dumps(recs))
    body = ",\n".join("\n".join("    " + ln for ln in json.dumps(r, indent=2, ensure_ascii=False).split("\n"))
                      for r in recs)
    if mine:
        new = text[:spans[mine[0]][0]] + body.lstrip() + text[spans[mine[-1]][1]:]
    else:
        last = spans[-1][1]
        new = text[:last] + ",\n" + body + text[last:]
    if write and new != text:
        path.write_text(new, encoding="utf-8", newline="\n")
    return same


def write_probes(recs, write):
    path = ROOT / "data" / "world_probes.json"
    doc = _read(path)
    same = all(doc["places"].get(k) == v for k, v in recs["probes"].items())
    if write and not same:
        doc["places"].update(recs["probes"])
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return same


def sync(write, spec=None):
    """[drift message] (empty when data/ already holds this tool's records); with write, makes it so."""
    spec = spec or load()
    recs = records(spec)
    convs = {c["id"] for c in recs["dialogue"]}
    qids = {q["id"] for q in recs["quests"]}
    fids = {f["id"] for f in recs["fields"]}
    drift = []
    for fname, key, owned, rs in (
            ("dialogue.json", "conversations", lambda o: o.get("id") in convs, recs["dialogue"]),
            ("quests.json", "quests", lambda o: o.get("id") in qids, recs["quests"]),
            ("progression.json", "quest_fields", lambda o: o.get("id") in fids, recs["fields"])):
        if not splice(ROOT / "data" / fname, key, owned, rs, write):
            drift.append("data/%s %s: this tool's %d records differ from data/compact_points.json" % (fname, key, len(rs)))
    if not write_probes(recs, write):
        drift.append("data/world_probes.json places.compact_*: differ from data/compact_points.json")
    return [] if write else drift


# ------------------------------------------------------------------------------------------------- the pack
def fight_list(spec=None):
    spec = spec or load()
    out = []
    for p in spec["points"]:
        for n in p["npcs"]:
            if n.get("fight"):
                out.append({"point": p, "npc": n, "trainer": n["fight"]["trainer"], "sets": defeated(p, n),
                            "function": "%s:%s/%s/won_%s" % (NS, FOLDER, p["id"].split("_", 1)[0], short(n)),
                            "won_say": n["fight"]["won_say"]})
    return out


def _key(fid):
    return "cobblers__" + fid.replace(".", "__")


def pack_files(spec=None):
    """{relative path: text}: pack.mcmeta, the battle_victory callback and one won function per fighter."""
    out = {"pack.mcmeta": json.dumps({"pack": {"pack_format": 48, "description":
                                               "Cobblers: the Haven Compact's story fights (tools/compact_points.py)"}},
                                     indent=2) + "\n"}
    calls = []
    for f in fight_list(spec):
        x, y, z = f["npc"]["at"]
        sel = "@s[type=cobblemon:npc,x=%d.5,y=%d,z=%d.5,distance=..%s]" % (x, y, z, RADIUS)
        calls.append("      q.run_command('execute as ' + t.l.uuid + ' if entity %s as ' + t.w.player.uuid + "
                     "' run function %s');" % (sel, f["function"]))
        ns, path = f["function"].split(":", 1)
        out["data/%s/function/%s.mcfunction" % (ns, path)] = "\n".join([
            "# Generated by tools/compact_points.py: run by the cobblers_compact battle_victory callback as the player "
            "who beat %s (%s). Writes %s into THAT player's Cobblemon data, as tools/hq_tower.py's won functions do"
            % (f["npc"]["name"], f["trainer"], f["sets"]),
            'runmolang "t.d = q.player.data(); t.d.%s = 1; q.player.save_data();" @s' % _key(f["sets"]),
            "title @s actionbar %s" % json.dumps({"text": f["won_say"], "color": "gold"})]) + "\n"
    out[CALLBACK] = "\n".join(
        ["'Generated by tools/compact_points.py. The Compact story fights: a player who beat one of their NPCs runs "
         "its won function.';",
         "for_each(t.l, c.scriptable_losers, {",
         "  t.l.is_npc ? {",
         "    for_each(t.w, c.player_winners, {"]
        + calls + ["    });", "  };", "});", ""])
    return out


def build(out=OUT, spec=None):
    files = pack_files(spec)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return files


def npc_placements(spec=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for reapply step R18CP's npc action."""
    spec = spec or load()
    return [(conv_id(n), tuple(n["at"]), "%s:%s" % (NS, n["id"]), yaw(n)) for p in spec["points"] for n in p["npcs"]]


# ------------------------------------------------------------------------------------------------- the checks
def _seg(px, pz, a, b):
    (ax, az), (bx, bz) = a, b
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L))
    return math.hypot(px - ax - t * dx, pz - az - t * dz)


def other_points():
    """[(x, z, where)] for every [x, y, z] triple and every {x, z} object in data/*.json except this unit's own files
    and its own probes: the sweep a seat must stand clear of (it reads data, not the world)."""
    out = []

    def walk(v, where):
        if isinstance(v, list):
            if len(v) == 3 and all(isinstance(a, int) and not isinstance(a, bool) for a in v):
                x, y, z = v
                if 0 < x < 8192 and -64 < y < 330 and 0 < z < 8192:
                    out.append((x, z, where))
                return
            for c in v:
                walk(c, where)
        elif isinstance(v, dict):
            if isinstance(v.get("x"), (int, float)) and isinstance(v.get("z"), (int, float)) \
                    and not isinstance(v.get("x"), bool):
                out.append((v["x"], v["z"], where))
            for k, c in v.items():
                walk(c, where)
    for f in sorted((ROOT / "data").glob("*.json")):
        if f.name in OWN_FILES or f.name == "route_paths.json":
            continue
        try:
            d = _read(f)
        except (ValueError, OSError):
            continue
        if f.name == "world_probes.json":
            d = {k: v for k, v in d.get("places", {}).items() if not k.startswith("compact_")}
        walk(d, f.name)
    return out


def homeless_species():
    """The species docs/story/ENCOUNTER_GAPS.md lists with no authored home, as Cobblemon ids."""
    text = (ROOT / "docs" / "story" / "ENCOUNTER_GAPS.md").read_text(encoding="utf-8")
    out = set()
    for line in text.splitlines():
        m = re.match(r"- \*\*Generation \d \(\d+\):\*\* (.*)", line)
        if m:
            out |= {re.sub(r"[^a-z0-9]", "", n.lower()) for n in m.group(1).split(",")}
    return out


def check(ground=None, spec=None):
    """Problems, as strings; [] when clean. `ground` is a tools/ground.py Ground, or None to skip the heightmap."""
    import numpy as np
    spec = spec or load()
    probs = []
    T = teams()
    data = ROOT / "data"
    pl = _read(data / "placements.json")
    paths = _read(data / "route_paths.json")["paths"]
    rp = np.array([(x, z) for v in paths.values() for x, z in v], dtype=float)
    others = other_points()
    roster = {t["id"]: t for t in _read(data / "trainers.json")["trainers"]}
    ours = [(p, n) for p in spec["points"] for n in p["npcs"]]
    ids = [n["id"] for _, n in ours]
    if len(ids) != len(set(ids)):
        probs.append("an NPC id is used twice")
    homeless = homeless_species()
    for p, n in ours:
        x, y, z = n["at"]
        g = n["ground"]
        if y != g + 1:
            probs.append("%s: stands at y%d, its ground is y%d (a seat is ground + 1)" % (n["id"], y, g))
        if ground is not None and ground(x, z) != g:
            probs.append("%s: the heightmap's ground at (%d, %d) is y%d, the seat says y%d" % (n["id"], x, z, ground(x, z), g))
        if ground is not None:
            box = ground.box(x - 1, z - 1, x + 1, z + 1)
            if int(box.max()) - int(box.min()) > 1:
                probs.append("%s: the 3x3 round its seat is not level within one block" % n["id"])
        d = float(np.min(np.hypot(rp[:, 0] - x, rp[:, 1] - z)))
        if d < MIN_ROUTE:
            probs.append("%s: %.1f blocks from a walked route line (minimum %s)" % (n["id"], d, MIN_ROUTE))
        plan = (pl["settlements"].get(p["settlement"]) or {}).get("plan") or {}
        lots = set((plan.get("house_lots") or {}).get("along") or [])
        size = (plan.get("house_lots") or {}).get("size") or [0, 0]
        setback = (plan.get("house_lots") or {}).get("setback") or 0
        for s in plan.get("streets") or []:
            clear = s["width"] / 2 + 1.5 + (setback + max(size) + 2 if s["id"] in lots else 0)
            if any(_seg(x, z, a, b) < clear for a, b in zip(s["polyline"], s["polyline"][1:])):
                probs.append("%s: inside %s's %s or its lot band" % (n["id"], p["settlement"], s["id"]))
        for a in plan.get("anchors") or []:
            r = a.get("rect")
            if r and r[0] - 2 <= x <= r[2] + 2 and r[1] - 2 <= z <= r[3] + 2:
                probs.append("%s: on %s's anchor %s" % (n["id"], p["settlement"], a.get("id")))
        r = (plan.get("plaza") or {}).get("rect")
        if r and r[0] <= x <= r[2] and r[1] <= z <= r[3]:
            probs.append("%s: on %s's plaza, whose paved y is not the heightmap's" % (n["id"], p["settlement"]))
        near = [w for ox, oz, w in others if math.hypot(ox - x, oz - z) < MIN_OTHER]
        if near:
            probs.append("%s: within %s blocks of a coordinate %s records" % (n["id"], MIN_OTHER, near[0]))
        for q, m in ours:
            if m["id"] < n["id"] and math.hypot(m["at"][0] - x, m["at"][2] - z) < MIN_OWN:
                probs.append("%s and %s: %.1f apart, inside the callback's match" % (m["id"], n["id"],
                                                                                  math.hypot(m["at"][0] - x, m["at"][2] - z)))
        if not isinstance(n.get("faces"), list) or len(n["faces"]) != 2:
            probs.append("%s: faces is not an [x, z]" % n["id"])
        # the states: fields they read and transitions they run exist
        tids = {t["id"] for t in p["transitions"]}
        sets = {s for t in p["transitions"] for s in t["sets"]} | {
            "%s_defeated" % short(m) for m in p["npcs"] if m.get("fight")}
        for u in (p.get("closed_when") or {}).get("unless") or []:
            if u not in sets:
                probs.append("%s: closed_when reads %s, which nothing in the point sets" % (p["id"], u))
        for st in n["states"]:
            for t in st.get("actions") or []:
                if t not in tids:
                    probs.append("%s state %s: runs unknown transition %s" % (n["id"], st["id"], t))
            if st.get("ack") and st["ack"] not in tids:
                probs.append("%s state %s: acknowledges unknown transition %s" % (n["id"], st["id"], st["ack"]))
            for tok in st["when"]:
                if tok in ("window", "defeated", "closed"):
                    continue
                if tok.lstrip("!") not in sets:
                    probs.append("%s state %s: reads %s, which nothing in the point sets" % (n["id"], st["id"], tok))
        f = n.get("fight")
        if f:
            rec = T.get(f["trainer"])
            if rec is None or not rec.get("team"):
                probs.append("%s: no team %s in data/compact_trainers.json" % (n["id"], f["trainer"]))
                continue
            if rec.get("sets") != [defeated(p, n)]:
                probs.append("%s: %s sets %s, the NPC's field is %s" % (n["id"], f["trainer"], rec.get("sets"), defeated(p, n)))
            if rec.get("point") != p["id"]:
                probs.append("%s: %s names point %s" % (n["id"], f["trainer"], rec.get("point")))
            lead = roster.get(NEXT_LEADER.get(p["settlement"], ""))
            if lead is None:
                probs.append("%s: no next leader for %s" % (n["id"], p["settlement"]))
            else:
                ace = max(m["level"] for m in lead["team"])
                top = max(m["level"] for m in rec["team"])
                if top >= ace:
                    probs.append("%s: top level %d is not under %s's ace %d" % (f["trainer"], top, lead["id"], ace))
            for m in rec["team"]:
                if m["species"] not in homeless and m["species"] not in SIGNATURE_EXEMPT:
                    probs.append("%s: %s has a wild home (not on docs/story/ENCOUNTER_GAPS.md's lists)" % (f["trainer"], m["species"]))
            if not 0 <= f.get("skill", -1) <= 5:
                probs.append("%s: skill %r is not 0-5" % (n["id"], f.get("skill")))
    # every team is fought by exactly one NPC
    fought = [n["fight"]["trainer"] for _, n in ours if n.get("fight")]
    for tid in T:
        if fought.count(tid) != 1:
            probs.append("%s: fought by %d NPCs, not 1" % (tid, fought.count(tid)))
    # Varga rises, and stays under her tower team
    tower = {t["id"]: t for t in _read(data / VARGA_TOWER[0])["trainers"]}[VARGA_TOWER[1]]
    tower_low = min(m["level"] for m in tower["rct"]["team"])
    vs = sorted((tid for tid in T if tid.startswith("compact_varga_")), key=lambda s: int(s.rsplit("_", 1)[1]))
    tops = [max(m["level"] for m in T[v]["team"]) for v in vs]
    if tops != sorted(tops) or len(set(tops)) != len(tops) or (tops and tops[-1] >= tower_low):
        probs.append("Varga's tops %s must rise and stay under her tower team's %d" % (tops, tower_low))
    # nothing here writes a stage or grants a flag other than the one the point declares
    prog = _read(data / "progression.json")
    flags = {fl["id"]: fl for fl in prog["flags"]}
    for p in spec["points"]:
        for t in p["transitions"]:
            fn = t.get("function")
            if fn:
                mm = re.fullmatch(r"cobblers:flag/([a-z0-9_]+)/grant", fn)
                fl = flags.get(mm.group(1)) if mm else None
                sb = (fl or {}).get("set_by") or {}
                if not fl or sb.get("quest") != p["quest"] or sb.get("transition") != t["id"]:
                    probs.append("%s %s: runs %s, but data/progression.json does not name it the setter" % (p["id"], t["id"], fn))
            for s in t["sets"]:
                if field(p, s) == STAGE:
                    probs.append("%s: writes the main stage" % t["id"])
    fl = flags.get("crater_operation_stopped") or {}
    if (fl.get("set_by") or {}).get("quest") != "evt_compact_crater":
        probs.append("crater_operation_stopped: its declared setter is not CP-12 (evt_compact_crater)")
    return probs


def compile_all(spec=None):
    """[(conversation id, refusal)]: compile every generated conversation with tools/compile_dialogue.py against the
    data in data/ (run after write)."""
    import compile_dialogue as CD
    bad = []
    for c in records(spec)["dialogue"]:
        try:
            CD.build(c["id"], ROOT / "data")
        except SystemExit as e:
            bad.append((c["id"], str(e)))
    return bad


def legality(jar, spec=None):
    """[problem] for every species, move and ability in data/compact_trainers.json against the jar's species files.
    A move counts when the species or a pre-evolution learns it by level-up at or below the member's level, or by TM,
    egg or tutor."""
    z = zipfile.ZipFile(jar)
    idx = {n.rsplit("/", 1)[1][:-5]: n for n in z.namelist()
           if n.startswith("data/cobblemon/species/") and n.endswith(".json")}
    probs = []
    for tid, t in teams().items():
        for m in t["team"]:
            sp = m["species"]
            if sp not in idx:
                probs.append("%s: no species %s" % (tid, sp))
                continue
            chain, name = [], sp
            while name:
                d = json.loads(z.read(idx[name]))
                chain.append(d)
                pre = d.get("preEvolution")
                name = re.sub(r"[^a-z0-9]", "", pre.split()[0].lower()) if pre else None
                if name and name not in idx:
                    break
            if chain[0].get("implemented") is not True:
                probs.append("%s: %s is not implemented" % (tid, sp))
            learn = set()
            for d in chain:
                for mv in d.get("moves") or []:
                    k, v = mv.split(":", 1)
                    if not k.isdigit() or int(k) <= m["level"]:
                        learn.add(v)
            for mv in m["moveset"]:
                if mv not in learn:
                    probs.append("%s: %s L%d cannot learn %s" % (tid, sp, m["level"], mv))
            abil = {a.split(":", 1)[-1] for a in chain[0].get("abilities") or []}
            if m.get("ability") and m["ability"] not in abil:
                probs.append("%s: %s has no ability %s (%s)" % (tid, sp, m["ability"], sorted(abil)))
    return probs


def verify(rc, spec=None):
    import npc_seats
    spec = spec or load()
    doc = {"seats": [{"id": n["id"], "at": n["at"], "yaw": yaw(n)} for p in spec["points"] for n in p["npcs"]]}
    return npc_seats.verify(rc, doc=doc, classes={})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", nargs="?", default="check", choices=("check", "write", "build", "legality", "verify"))
    ap.add_argument("--source-root", default=None)
    ap.add_argument("--jar", default=None)
    ap.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_ROOT"))
    a = ap.parse_args(argv)
    if a.action == "write":
        sync(True)
        print("wrote the records of %d points into data/ (dialogue, quests, progression, world_probes)" % len(load()["points"]))
        return 0
    if a.action == "build":
        files = build()
        print("wrote %d files to %s" % (len(files), OUT))
        return 0
    if a.action == "legality":
        if not a.jar:
            raise CompactError("legality needs --jar <Cobblemon jar>")
        probs = legality(a.jar)
        n = sum(len(t["team"]) for t in teams().values())
        print("%d members of %d teams: %s" % (n, len(teams()), "every move, ability and species legal" if not probs
                                               else "%d problem(s)" % len(probs)))
        for p in probs:
            print("  PROBLEM " + p)
        return 1 if probs else 0
    if a.action == "verify":
        import reapply
        res = verify(reapply.Rcon(a.server_dir))
        for sid, verdict, detail in res:
            print("%-4s %-40s %s" % (verdict, sid, detail))
        fails = [r for r in res if r[1] != "ok"]
        print("%d of %d Compact NPCs verified in the world" % (len(res) - len(fails), len(res)))
        return 1 if fails else 0
    import ground as G
    try:
        g = G.load(a.source_root)
    except (SystemExit, OSError, FileNotFoundError) as e:
        print("heightmap unreadable (%s): the ground checks are skipped" % e)
        g = None
    probs = check(g) + ["DRIFT " + d for d in sync(False)]
    probs += ["%s does not compile: %s" % c for c in compile_all()]
    spec = load()
    print("%d points, %d NPCs, %d fights: %s" % (len(spec["points"]), sum(len(p["npcs"]) for p in spec["points"]),
                                                len(fight_list(spec)), "clean" if not probs else "%d problem(s)" % len(probs)))
    for p in probs:
        print("  PROBLEM " + p)
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
