#!/usr/bin/env python
"""The fishermen who hand out rods (data/fishermen.json): five NPCs at five waters, one rod each, once per player.

  python tools/fishermen.py check     the table against everything it names, and the shared files against the table; writes nothing
  python tools/fishermen.py write     seat every fisherman on the heightmap and splice the derived records into the shared files
  python tools/fishermen.py seats     print where each would stand now (the finder alone; writes nothing)

THE OWNER (2026-10-12): "I need a check to make sure we have more fisherman NPCs handing out some rods throughout the game;
doesn't have to be every rod." The check is tools/rod_sources.py; this is the content it counts.

WHAT `write` EMITS, each from data/fishermen.json alone (plus the heightmap, for the seats), spliced by id into:
  data/dialogue.json     one conversation per fisherman, after dlg_route1_first_cast_rack (the First Cast fisher's shape)
  data/quests.json       one optional quest each, before evt_route2_rollaway_geodude: the rod is a reward, given by
                         grant_reward_once (the give reports success, then the claim field is written, in one action)
  data/progression.json  quest.<q>.rod_claimed, .completed, .dialogue_cursor (player scope)
  data/npc_seats.json    each fisherman's stand; tools/reapply.py R17N places it (spawnnpcat + a turn to the seat's yaw)
Only those ids are touched in the shared files. A second `write` is a no-op.

THE GATE. Every rod but the Poke Rod is behind a badge: the conversation's entry rule turns a player without the flag away
with a line, and the giving transition also requires the flag, so a path that skips the entry rule still gives nothing.
The flag is gymN_cleared (data/progression.json flags): a series-independent badge count, not a leader's name.

WHERE A FISHERMAN STANDS: 2 to 4 blocks from a column the model holds under water, on ground at or above that water's surface
(a lake or the sea from data/landmarks.json basins and tools/water_mask.py; a river from the graded polyline of the named
course in data/rivers.json), at least 3.5 blocks from every walked route line, flat to one block in a 3x3, outside every
placement footprint and (unless the table drops it) every town footprint, 5 from any seated NPC or trainer and 3.5 from a
ferryman, scene or reward NPC and a trader clerk, and off the plan's streets, anchors and plaza where it falls inside a
settlement. GROUND comes from tools/ground.py (the canonical heightmap, rounded), never from a world.

NOT COVERED (CLAUDE.md "Our list is not the world"): whether the seat's feet and head are clear in a built world (a tree
or a template block the heightmap does not hold); that the water is in reach of a cast; that the painted river is as wide
as the polyline says. `python tools/npc_seats.py verify` probes the first on a server. Nothing here was seen in game.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compact_routes as CR  # noqa: E402  (Seater: the walked lines, the exclusions; splice_list; splice_quests)

DATA = ROOT / "data"
TABLE = DATA / "fishermen.json"
WHO = "data/fishermen.json (tools/fishermen.py write)"
DIALOGUE_AFTER = "dlg_route1_first_cast_rack"
QUEST_BEFORE = "evt_route2_rollaway_geodude"
FIELD_AFTER = "quest.evt_route1_first_cast.prop_cursor"
SEAT_AFTER = "npc_fossil_dig_foreman"
JAR = "Cobblemon-fabric-1.8.0+1.21.1.jar"
NPC_CLEAR = 3.5                # tools/markets.py NPC_CLEAR


def table():
    return json.loads(TABLE.read_text(encoding="utf-8"))


def quest_id(f):
    return "evt_fisher_" + f["slug"]


def conv_id(f):
    return "dlg_fisher_" + f["slug"]


def qfield(f, name):
    return "quest.%s.%s" % (quest_id(f), name)


def rod_item(f):
    return "cobblemon:" + f["rod"]


def rod_name(f):
    return f["rod"].replace("_", " ").title()


# ================================================================== the seat finder (the heightmap)

class FishSeater(CR.Seater):
    """CR.Seater (the walked lines, the placement and town exclusions, the other seats) with this table's own seats left
    out of "another seat", and the ground rule of a shore instead of a road: dry means level with or above the water."""

    def __init__(self, g=None):
        super().__init__(g)
        import water_mask as W
        self.W = W
        self.bodies = W.bodies()
        self.rivers = {c["id"]: c for c in json.loads((DATA / "rivers.json").read_text(encoding="utf-8"))["courses"]}
        self.pl = json.loads((DATA / "placements.json").read_text(encoding="utf-8"))
        self.towns = {t["id"]: t for t in json.loads((DATA / "towns.json").read_text(encoding="utf-8"))["towns"]}
        self.npcs = self._other_npcs()

    def _others(self):
        own = {f["id"] for f in table()["fishermen"]}
        out = []
        for f in ("route_trainers.json", "late_route_trainers.json", "vr_trainers.json", "mansion_guardians.json",
                  "hq_trainers.json", "gym_junior_trainers.json"):
            for t in CR.jload(f)["trainers"]:
                s = t.get("seat")
                if s and t.get("seated", True):
                    out.append((t["id"], s[0], s[2]))
        for s in CR.jload("npc_seats.json")["seats"]:
            if s["id"] not in own:
                out.append((s["id"], s["at"][0], s["at"][2]))
        return out

    def _other_npcs(self):
        """[(label, (x, y, z))]: ferrymen, scene and reward NPCs, trader clerks and every other seat (tools/markets.py
        other_npcs), less this table's own seats."""
        import markets as M
        traders = {t["id"]: t for t in CR.jload("traders.json")["traders"]}
        own = {"seat cobblers:" + f["id"] for f in table()["fishermen"]}
        return [(w, p) for w, p in M.other_npcs(None, traders) if w not in own]

    # -- water
    def level(self, x, z, water):
        """The water surface y over (x, z) for this table's kind of water, or None if the column is dry."""
        k = water["kind"]
        if k == "river":
            return self._river_level(x, z, water["course"])
        body, y = self.W.level_at(x, z, self.g, self.bodies)
        if k == "sea":
            return y if body == "sea" else None
        return y if body == water["body"] else None

    def _river_level(self, x, z, course, reach=30):
        best = None
        for (ax, az, sa, _fa), (bx, bz, sb, _fb) in _pairs(self.rivers[course]["graded_polyline"]):
            dx, dz = bx - ax, bz - az
            L = dx * dx + dz * dz
            t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L)) if L else 0.0
            d = math.hypot(ax + t * dx - x, az + t * dz - z)
            if d <= reach and (best is None or d < best[0]):
                best = (d, sa + (sb - sa) * t)
        if best is None:
            return None
        return best[1] if self.g(x, z) < best[1] - 0.5 else None

    # -- the plan of a settlement the seat falls inside
    def plan_conflict(self, x, z):
        for sid, st in self.pl["settlements"].items():
            plan = st.get("plan") or {}
            fp = (plan.get("footprint") or {}).get("rect")
            if not fp:
                t = self.towns.get(sid)
                f = (t or {}).get("footprint")
                fp = [f["min_x"], f["min_z"], f["max_x"], f["max_z"]] if f else None
            if not fp or not (fp[0] <= x <= fp[2] and fp[1] <= z <= fp[3]):
                continue
            for s in plan.get("streets") or []:
                half = (s.get("width") or 3) / 2.0
                for (ax, az), (bx, bz) in zip(s["polyline"], s["polyline"][1:]):
                    dx, dz = bx - ax, bz - az
                    L = dx * dx + dz * dz
                    t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L)) if L else 0.0
                    if math.hypot(ax + t * dx - x, az + t * dz - z) < half + 2.0:
                        return "%s street %s" % (sid, s["id"])
            for a in plan.get("anchors") or []:
                r = a.get("rect")
                if r and r[0] - 2 <= x <= r[2] + 2 and r[1] - 2 <= z <= r[3] + 2:
                    return "%s anchor %s" % (sid, a["id"])
            r = (plan.get("plaza") or {}).get("rect")
            if r and r[0] - 2 <= x <= r[2] + 2 and r[1] - 2 <= z <= r[3] + 2:
                return "%s plaza" % sid
        return None

    def find(self, f, rules):
        """The seat nearest f['near'] that passes every rule, or None."""
        water = f["water"]
        nx, nz = f["near"]
        R, drop = f["radius"], tuple(f.get("drop") or ())
        lo, hi = rules["water_distance"]
        cells = [(nx + dx, nz + dz) for dx in range(-R, R + 1) for dz in range(-R, R + 1) if dx * dx + dz * dz <= R * R]
        cells.sort(key=lambda c: (math.hypot(c[0] - nx, c[1] - nz), c))
        cache = {}

        def lv(x, z):
            if (x, z) not in cache:
                cache[(x, z)] = self.level(x, z, water)
            return cache[(x, z)]
        for x, z in cells:
            if self.route_dist(x, z) < rules["min_route"] or not self.apart_ok(x, z, rules["min_npc"]):
                continue
            if self.relief(x, z, 1) > 1 or self.excluded(x, z, drop) or self.plan_conflict(x, z):
                continue
            if lv(x, z) is not None:
                continue
            best = None
            for dz in range(-hi, hi + 1):
                for dx in range(-hi, hi + 1):
                    d = math.hypot(dx, dz)
                    if lo <= d <= hi and lv(x + dx, z + dz) is not None and (best is None or d < best[0]):
                        best = (d, x + dx, z + dz)
            if best is None:
                continue
            y = self.g(x, z)
            if y < lv(best[1], best[2]):
                continue
            if any(math.dist((x, y + 1, z), p) < NPC_CLEAR for _w, p in self.npcs):
                continue
            wx, wz = best[1], best[2]
            return {"at": [x, y + 1, z], "xz": (x, z),
                    "yaw": self.RE.yaw_to(wx - x, wz - z),
                    "ground": {"kind": "heightmap", "y": y, "source": "tools/ground.py, the canonical heightmap rounded"},
                    "faces": "the water at (%d, %d), %.1f blocks off" % (wx, wz, best[0]),
                    "water_surface_y": lv(wx, wz)}
        return None


def _pairs(pl):
    return list(zip(pl, pl[1:]))


def seat_all(tb, g=None):
    s = FishSeater(g)
    out = {}
    for f in tb["fishermen"]:
        r = s.find(f, tb["seat_rules"])
        if r is None:
            raise SystemExit("%s: no standable seat within %d blocks of %s on %s" % (f["id"], f["radius"], f["near"], f["water"]))
        s.taken.append((f["id"], r["xz"][0], r["xz"][1]))
        s.npcs.append(("seat cobblers:" + f["id"], tuple(r["at"])))
        out[f["id"]] = r
    return out


# ================================================================== the derived records

def eq(field, value):
    return {"kind": "progression_equals", "field": field, "value": value}


def derive(tb, seats):
    """{conversations, quests, fields, npc_seats}: every record this table owns in the shared files, in memory."""
    out = {"conversations": [], "quests": [], "fields": [], "npc_seats": []}
    for f in tb["fishermen"]:
        q, flag, L = quest_id(f), f["gate"]["flag"], f["lines"]
        claimed, done, cursor = qfield(f, "rod_claimed"), qfield(f, "completed"), qfield(f, "dialogue_cursor")
        out["fields"] += [
            {"id": claimed, "quest_id": q, "field": "rod_claimed", "type": "boolean", "scope": "player", "initial": False,
             "why": "grant_reward_once's claim for %s's %s (%s)" % (f["name"], rod_name(f), WHO)},
            {"id": done, "quest_id": q, "field": "completed", "type": "boolean", "scope": "player", "initial": False},
            {"id": cursor, "quest_id": q, "field": "dialogue_cursor", "type": "enum", "scope": "player",
             "initial": "fd_1", "allowed_values": "node ids from " + conv_id(f)},
        ]
        line = lambda i, sp, text, nxt, **kw: dict({"id": i, "kind": "line", "speaker": sp, "text": text, "next": nxt}, **kw)  # noqa: E731
        out["conversations"].append({
            "id": conv_id(f), "quest_id": q, "npc_id": f["id"], "source": WHO, "scope": "player",
            "cursor": {"progression_field": cursor, "initial_node": "fd_1", "persist": "after_each_node",
                       "restore": "on_every_interaction", "cursor_is": "next_unread_node"},
            "entry_rules": [
                {"priority": 10, "when": eq(done, True), "node": "fd_done"},
                {"priority": 20, "when": eq(claimed, True), "node": "fd_4"},
                {"priority": 25, "when": {"kind": "not", "condition": {"kind": "flag", "flag": flag}}, "node": "fd_wait"},
                {"priority": 40, "when": {"kind": "always"}, "node": "fd_1"},
            ],
            "nodes": [
                line("fd_1", "fisher", L["hello_1"], "fd_2"),
                line("fd_2", "fisher", L["hello_2"], "fd_3"),
                line("fd_3", "narration", L["offer"], "fd_4",
                     actions_after_acknowledge=[{"kind": "quest_transition", "transition": "give_rod"}]),
                line("fd_4", "fisher", L["thanks"], "fd_done",
                     actions_after_acknowledge=[{"kind": "quest_transition", "transition": "complete"}]),
                line("fd_done", "fisher", L["done"], "fd_done"),
                line("fd_wait", "fisher", L["wait"], "fd_wait"),
            ],
            "speakers": {"fisher": f["name"], "narration": None},
            "npc_name": f["name"],
            "placeholder": tb["placeholder"],
        })
        out["quests"].append({
            "id": q, "source": "%s: %s" % (WHO, f["where"]),
            "scope": "player", "optional": True, "progression_gate": [],
            "availability": {"conditions": [], "repeatable": False, "npc_remains_after_completion": True},
            "dialogue_ids": [conv_id(f)],
            "objectives": [{"id": "rod", "active_when": {"field": claimed, "equals": False},
                            "complete_when": {"field": claimed, "equals": True},
                            "text": "%s, %s, has %s %s for anyone with %s." % (
                                f["name"], f["where"], "an" if rod_name(f)[:1] in "AEIOU" else "a", rod_name(f),
                                f["gate"]["says"])}],
            "transitions": [
                {"id": "give_rod",
                 "conditions": [eq(claimed, False), {"kind": "flag", "flag": flag}],
                 "effects": [{"kind": "grant_reward_once", "reward": "reward_rod", "target": "triggering_player",
                              "claim_field": claimed, "idempotency_key": "%s:reward_rod:{player_uuid}" % q,
                              "receipt_commit": "atomic_with_item_delivery"}]},
                {"id": "complete", "conditions": [eq(claimed, True)],
                 "effects": [{"kind": "set_progression", "field": done, "value": True},
                             {"kind": "set_progression", "field": cursor, "value": "fd_done"}]},
            ],
            "rewards": [{"id": "reward_rod", "status": "item_id_verified (Cobblemon 1.8.0 jar)",
                         "contents": [{"item": rod_item(f), "count": 1,
                                       "verification": "%s: item model and recipe result in %s" % (rod_item(f), JAR)}],
                         "why": "one %s per player, once, behind %s (%s): data/fishermen.json. Crafting the same rod stays allowed "
                                "(smithing table: template, a rod, the ball); this is the natural source "
                                "(CLAUDE.md/STATE: every Cobblemon item is obtainable without crafting)."
                                % (rod_name(f), f["gate"]["says"], flag)}],
            "multiplayer": {"state": "per_player", "props": "none: one NPC",
                            "actors": "the Cobblemon NPC opens its own conversation for the player who clicked",
                            "concurrent_players": "independent fields; no player reads or writes another's"},
            "progression_field_refs": [claimed, done, cursor],
            "gate": {"flag": flag, "says": f["gate"]["says"],
                     "why": "a stronger rod than the Poke Rod is a reward for progress; both the conversation's entry rule and the give transition require it"},
            "proof_still_required": "the seat in a built world (feet and head clear, the water in reach of a cast: tools/npc_seats.py verify), "
                                    "and a player taking the rod once, then a second player taking theirs",
        })
        s = seats[f["id"]]
        out["npc_seats"].append({
            "id": f["id"], "conversation": conv_id(f), "at": s["at"], "yaw": s["yaw"], "ground": s["ground"],
            "faces": s["faces"],
            "why": "%s (data/fishermen.json): %s; %s" % (f["name"], f["where"], f["stage"])})
    return out


def mine(tb):
    ids = {"conversations": set(), "quests": set(), "fields": set(), "npc_seats": set()}
    d = derive(tb, {f["id"]: {"at": [0, 0, 0], "yaw": 0, "ground": {}, "faces": ""} for f in tb["fishermen"]})
    for k in ids:
        ids[k] = {r["id"] for r in d[k]}
    return ids


# ================================================================== write and check

def write_all(tb, seats):
    d, ids = derive(tb, seats), mine(tb)
    changed = []
    if CR.splice_list("dialogue.json", "conversations", ids["conversations"], d["conversations"], DIALOGUE_AFTER):
        changed.append("dialogue.json")
    if CR.splice_list("progression.json", "quest_fields", ids["fields"], d["fields"], FIELD_AFTER):
        changed.append("progression.json")
    if CR.splice_list("npc_seats.json", "seats", ids["npc_seats"], d["npc_seats"], SEAT_AFTER):
        changed.append("npc_seats.json")
    if CR.splice_quests(ids["quests"], d["quests"], before=QUEST_BEFORE):
        changed.append("quests.json")
    return changed


def stored_seats(tb):
    have = {s["id"]: s for s in CR.jload("npc_seats.json")["seats"]}
    return {f["id"]: {"at": have[f["id"]]["at"], "yaw": have[f["id"]]["yaw"], "ground": have[f["id"]]["ground"],
                      "faces": have[f["id"]]["faces"]} for f in tb["fishermen"]}


def check(tb):
    """Problems, as strings: the table against what it names, the shared files against what the table derives."""
    probs = []
    ids = {"cobblemon:" + i for i in tb["rod_universe"]["ids"]}
    flags = {x["id"] for x in CR.jload("progression.json")["flags"]}
    seen_rod, seen_id = set(), set()
    for f in tb["fishermen"]:
        if rod_item(f) not in ids:
            probs.append("%s: %s is not in the rod universe" % (f["id"], rod_item(f)))
        if f["rod"] == "poke_rod":
            probs.append("%s: the Poke Rod is First Cast's, a fisherman here hands out a better one" % f["id"])
        if f["rod"] in seen_rod:
            probs.append("%s: %s is already another fisherman's rod" % (f["id"], f["rod"]))
        seen_rod.add(f["rod"])
        if f["id"] in seen_id:
            probs.append("%s: listed twice" % f["id"])
        seen_id.add(f["id"])
        if f["gate"]["flag"] not in flags:
            probs.append("%s: gate flag %s is not a progression flag" % (f["id"], f["gate"]["flag"]))
        for k in ("hello_1", "hello_2", "offer", "thanks", "done", "wait"):
            if not f["lines"].get(k):
                probs.append("%s: no %s line" % (f["id"], k))
    try:
        seats = stored_seats(tb)
    except KeyError:
        return probs + ["the derived records are missing: run `python tools/fishermen.py write`"]
    d = derive(tb, seats)
    have = {
        "conversations": {c["id"]: c for c in CR.jload("dialogue.json")["conversations"]},
        "fields": {c["id"]: c for c in CR.jload("progression.json")["quest_fields"]},
        "npc_seats": {c["id"]: c for c in CR.jload("npc_seats.json")["seats"]},
        "quests": {c["id"]: c for c in CR.jload("quests.json")["quests"]},
    }
    where = {"conversations": "dialogue.json", "fields": "progression.json", "npc_seats": "npc_seats.json", "quests": "quests.json"}
    for k, recs in d.items():
        for r in recs:
            if have[k].get(r["id"]) != r:
                probs.append("data/%s: %s differs from the table (run write)" % (where[k], r["id"]))
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("check", "write", "seats"))
    a = ap.parse_args(argv)
    tb = table()
    if a.action == "check":
        probs = check(tb)
        print("%d fishermen: %s" % (len(tb["fishermen"]), "clean" if not probs else "%d problem(s)" % len(probs)))
        for p in probs:
            print("  PROBLEM " + p)
        return 1 if probs else 0
    seats = seat_all(tb)
    if a.action == "write":
        changed = write_all(tb, seats)
        print("seated %d fishermen; wrote: %s" % (len(seats), ", ".join(changed) or "nothing (already current)"))
    for f in tb["fishermen"]:
        s = seats[f["id"]]
        print("%-30s %-10s at %s yaw %4d ground y%d  %s" % (f["id"], f["rod"], s["at"], s["yaw"], s["ground"]["y"], s["faces"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
