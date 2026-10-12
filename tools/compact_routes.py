#!/usr/bin/env python
"""The Haven Compact's story points on the routes and in the towns (docs/story/HAVEN_COMPACT_PASS.md), from one table.

  python tools/compact_routes.py check     the table against everything it names; writes nothing
  python tools/compact_routes.py write     seat every actor on the heightmap and write every derived record
  python tools/compact_routes.py build     the battle_victory callback pack -> build/datapacks/cobblers_compact_routes

THE TABLE is data/compact_routes.json (the owner's 2026-10-11 brief: "more story points for them that a player would
go through ... especially some fun new battles"). This unit (CP-ROUTES) builds CP-01, 02, 03, 05, 06, 07, 08, 09, 10, 11
and 13. CP-04, CP-12 and CP-14 are unit CP-CORE's and are not here.

WHAT `write` EMITS, each from the table alone (plus the heightmap, for the seats):

  data/compact_route_trainers.json      the SEATED fighters (mechanism M1): record and seat together, the shape of
                                  data/hq_trainers.json, read by tools/route_trainers.py (the rctmod data, the defeat
                                  advancement, the cycle) and placed by tools/reapply.py R17 over RCON
  data/compact_route_npc_teams.json  the talk-then-fight NPCs' teams (mechanism M2): teams only, no seat, the shape of
                                  data/finale_trainers.json; tools/compile_dialogue.py's `npc_battle` reads the team
  data/dialogue.json              one conversation per NPC (spliced after dlg_viltri_north_bank)
  data/quests.json                one optional quest per point that has NPCs (spliced before evt_route3_nosepass_signs)
  data/progression.json           their cursor, defeat and choice fields (after quest.evt_viltri_north_bank.dialogue_cursor)
                                  and the seated fighters' quest.<id>.defeated
  data/npc_seats.json             the NPCs' stands (after npc_main_misty_relief_clerk); tools/reapply.py R17N places them

and `build` writes the pack that records an M2 win: a Cobblemon battle_victory callback that runs, as the winner, a
function that writes the NPC's defeat field into the player's own data (the shape tools/hq_tower.py fight_files proved).

Only those ids are touched in the shared files. A second `write` is a no-op.

WHAT IS NOT COVERED (CLAUDE.md "Our list is not the world"): this tool seats what the table lists. It does not know what a
donor template, a mod or an earlier pass already put in the same cells; whether a seat's feet are dry (painted water is not in
the heightmap) is a block read in the exported world, which the seat finder guards only by a minimum ground height.

GROUND comes from tools/ground.py (the canonical heightmap, rounded), never from a world.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data"
NS = "cobblers"
TABLE = DATA / "compact_routes.json"
TRAINERS_OUT = DATA / "compact_route_trainers.json"
NPC_TRAINERS_OUT = DATA / "compact_route_npc_teams.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_compact_routes"
FOLDER = "compact_routes"
CALLBACK = "data/cobblemon/callbacks/battle_victory/cobblers_compact_routes.molang"
STAGE = "quest.main_worldshift_reveal.stage"
WHO = "data/compact_routes.json (tools/compact_routes.py write)"
# where each kind of record is spliced, so a merge with a second author's records does not meet at one line
DIALOGUE_AFTER = "dlg_viltri_north_bank"
QUEST_BEFORE = "evt_route3_nosepass_signs"
FIELD_AFTER = "quest.evt_viltri_north_bank.dialogue_cursor"
SEAT_AFTER = "npc_main_misty_relief_clerk"
NPC_MIN_ROUTE = 3.5           # an immovable NPC this close to a walked line stands in the road (tests/test_npc_seats.py: 3)
TRAINER_MIN_ROUTE = 2.2
NPC_APART = 5.0
TRAINER_APART = 8.0
FLAT3, FLAT5 = 1, 2
SEA = 62


def jload(rel):
    return json.loads((DATA / rel).read_text(encoding="utf-8"))


def table():
    return json.loads(TABLE.read_text(encoding="utf-8"))


def stages():
    prog = jload("progression.json")
    return next(f for f in prog["quest_fields"] if f["id"] == STAGE)["allowed_values"]


def window(point):
    """Every stage from the point's own to the end of the story ('or later'), in the enum's order."""
    order = stages()
    if point.get("from_stage") is None:
        return None
    return order[order.index(point["from_stage"]):]


def all_actors(tb):
    return [(p, a) for p in tb["points"] for a in p["actors"]]


def short(actor):
    return actor["id"].replace("npc_compact_", "")


def conv_id(actor):
    return "dlg_compact_" + short(actor)


def key(field):
    return "cobblers__" + field.replace(".", "__")


def defeated_field(point, actor):
    """The field a win writes. A seated fighter's is rctmod's own (quest.<id>.defeated, tools/route_trainers.py); an NPC
    fighter's lives in its point's quest, named for its trainer record."""
    if actor["role"] == "seated":
        return "quest.%s.defeated" % actor["id"]
    return "quest.%s.%s_defeated" % (point["quest"], actor["trainer"])


def is_npc(actor):
    return actor["role"] != "seated"


def is_fighter(actor):
    return actor["role"] in ("seated", "fighter", "sider")


# ================================================================== seating (the heightmap)

class Seater:
    """Where each actor stands, measured on the canonical heightmap and the walked lines. Never on a world."""

    def __init__(self, g=None):
        import numpy as np
        import ground as G
        import late_route_trainers as LR
        import route_events as RE
        self.np = np
        self.LR = LR
        self.g = g or G.Ground()
        self.road = RE.Road()
        self.RE = RE
        self.pl = jload("placements.json")
        self.excl = LR.exclusions()
        self.placed = {}           # actor id -> (x, z)
        self.taken = [(i, x, z) for i, x, z in self._others()]
        segs = []
        for cells in self.road.paths.values():
            a = np.array(cells, dtype=float)
            segs.append(np.hstack([a[:-1], a[1:]]))
        self.segs = np.vstack(segs)

    # -- what else already stands somewhere
    def _others(self):
        out = []
        for f in ("route_trainers.json", "late_route_trainers.json", "vr_trainers.json", "mansion_guardians.json",
                  "hq_trainers.json", "gym_junior_trainers.json"):
            for t in jload(f)["trainers"]:
                s = t.get("seat")
                if s and t.get("seated", True):
                    out.append((t["id"], s[0], s[2]))
        own = {a["id"] for _p, a in all_actors(table())}      # this table's own earlier seats are not "another seat"
        for s in jload("npc_seats.json")["seats"]:
            if s["id"] not in own:
                out.append((s["id"], s["at"][0], s["at"][2]))
        return out

    # -- geometry
    def route_dist(self, x, z):
        np = self.np
        s = self.segs
        sel = s[(np.minimum(s[:, 0], s[:, 2]) - 12 <= x) & (np.maximum(s[:, 0], s[:, 2]) + 12 >= x)
                & (np.minimum(s[:, 1], s[:, 3]) - 12 <= z) & (np.maximum(s[:, 1], s[:, 3]) + 12 >= z)]
        if not len(sel):
            return 99.0
        ax, az, bx, bz = sel[:, 0], sel[:, 1], sel[:, 2], sel[:, 3]
        dx, dz = bx - ax, bz - az
        L = dx * dx + dz * dz
        t = np.where(L > 0, np.clip(((x - ax) * dx + (z - az) * dz) / np.where(L > 0, L, 1), 0, 1), 0)
        return float(np.min(np.hypot(ax + t * dx - x, az + t * dz - z)))

    def nearest_route_point(self, x, z):
        best = None
        for cells in self.road.paths.values():
            for px, pz in cells:
                if abs(px - x) <= 40 and abs(pz - z) <= 40:
                    d = math.hypot(px - x, pz - z)
                    if best is None or d < best[0]:
                        best = (d, px, pz)
        return best

    def relief(self, x, z, r):
        h = [self.g(x + dx, z + dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1)]
        return max(h) - min(h)

    def excluded(self, x, z, drop=()):
        for why, (x0, z0, x1, z1) in self.excl:
            if any(why.startswith(d) for d in drop):
                continue
            if x0 <= x <= x1 and z0 <= z <= z1:
                return why
        return None

    def apart_ok(self, x, z, need):
        for _i, tx, tz in self.taken:
            if math.hypot(tx - x, tz - z) < need:
                return False
        return True

    def ok(self, x, z, actor, spec, drop=()):
        """Why (x, z) cannot be this actor's seat, or None."""
        trainer = actor["role"] == "seated"
        d = self.route_dist(x, z)
        if d < (TRAINER_MIN_ROUTE if trainer else NPC_MIN_ROUTE):
            return "%.1f blocks from a walked line" % d
        if self.relief(x, z, 1) > FLAT3 or self.relief(x, z, 2) > FLAT5:
            return "not flat"
        if spec.get("min_ground") is not None and self.g(x, z) < spec["min_ground"]:
            return "ground y%d under the minimum %d" % (self.g(x, z), spec["min_ground"])
        if self.g(x, z) <= SEA + 1:
            return "ground y%d is at the water" % self.g(x, z)
        why = self.excluded(x, z, drop)
        if why:
            return why
        if not self.apart_ok(x, z, TRAINER_APART if trainer else NPC_APART):
            return "too near another seat"
        for m in spec.get("min_from") or []:
            if "point" in m and math.hypot(x - m["point"][0], z - m["point"][1]) < m["dist"]:
                return "within %s of %s" % (m["dist"], m["point"])
            if "box" in m:
                x0, z0, x1, z1 = m["box"]
                if x0 - m["dist"] <= x <= x1 + m["dist"] and z0 - m["dist"] <= z <= z1 + m["dist"]:
                    return "inside the box %s" % (m["box"],)
        return None

    # -- the kinds
    def seat(self, point, actor):
        spec = actor["seat"]
        kind = spec["kind"]
        fn = getattr(self, "seat_" + kind)
        res = fn(point, actor, spec)
        if res is None:
            raise SystemExit("%s: no standable seat for the %s anchor %s" % (actor["id"], kind, json.dumps(spec)[:200]))
        x, z = res["xz"]
        self.placed[actor["id"]] = (x, z)
        self.taken.append((actor["id"], x, z))
        return res

    def _heightmap(self, x, z, **extra):
        y = self.g(x, z)
        return dict({"xz": (x, z), "at": [x, y + 1, z], "ground": {"kind": "heightmap", "y": y,
                                                                    "source": "tools/ground.py, the canonical heightmap rounded"}},
                    **extra)

    def seat_route_shoulder(self, point, actor, spec):
        route = spec["route"]
        path = self.road.paths[route]
        if "fraction" in spec:
            i0 = int(spec["fraction"] * (len(path) - 1))
        else:
            i0 = self.road.nearest(route, spec["near"][0], spec["near"][1])[0]
        anchor_actor = spec.get("min_apart_from")
        for along in self.LR.ALONG:
            i = max(0, min(len(path) - 1, i0 + along))
            px, pz = path[i]
            _t, (nx, nz) = self.road.frame(route, i)
            road_y = self.g(px, pz)
            for off in spec["offsets"]:
                cands = []
                for s in (1, -1):
                    cx, cz = int(round(px + s * nx * off)), int(round(pz + s * nz * off))
                    cands.append((abs(self.g(cx, cz) - road_y), cx, cz, s))
                cands.sort()
                for _sc, cx, cz, s in cands:
                    if abs(self.g(cx, cz) - road_y) > 2:
                        continue
                    if self.ok(cx, cz, actor, spec) is not None:
                        continue
                    if anchor_actor:
                        d = math.hypot(cx - self.placed[anchor_actor][0], cz - self.placed[anchor_actor][1])
                        lo, hi = spec["apart"]
                        if not lo <= d <= hi:
                            continue
                    own = min(math.hypot(a - cx, b - cz) for a, b in path)
                    if own > 7.0:
                        continue
                    return self._heightmap(cx, cz, shoulder={"route": route, "path_index": i, "offset": off,
                                                                "along_path_cells": along,
                                                                "side": "right" if s > 0 else "left",
                                                                "road_ground": road_y,
                                                                "off_walked_line": round(self.route_dist(cx, cz), 1)})
        return None

    def seat_open(self, point, actor, spec):
        nx, nz = spec["near"]
        drop = ("ferry dock",)       # the dock is kept clear by the spec's own min_from instead
        cells = [(dx, dz) for dx in range(-spec["radius"], spec["radius"] + 1)
                 for dz in range(-spec["radius"], spec["radius"] + 1) if dx * dx + dz * dz <= spec["radius"] ** 2]
        cells.sort(key=lambda c: (c[0] ** 2 + c[1] ** 2, c))
        for dx, dz in cells:
            x, z = nx + dx, nz + dz
            if self.ok(x, z, actor, spec, drop=drop) is None:
                return self._heightmap(x, z, anchor={"near": [nx, nz], "moved_blocks": round(math.hypot(dx, dz), 1)})
        return None

    def seat_near_actor(self, point, actor, spec):
        ox, oz = self.placed[spec["actor"]]
        lo, hi = spec["distance"]
        cells = [(dx, dz) for dx in range(-hi, hi + 1) for dz in range(-hi, hi + 1) if lo <= math.hypot(dx, dz) <= hi]
        cells.sort(key=lambda c: (abs(math.hypot(*c) - (lo + hi) / 2.0), c))
        for dx, dz in cells:
            x, z = ox + dx, oz + dz
            if self.ok(x, z, actor, spec) is None:
                return self._heightmap(x, z, anchor={"beside": spec["actor"], "distance": round(math.hypot(dx, dz), 1)})
        return None

    def _settlement(self, sid):
        return self.pl["settlements"][sid]

    def plaza_point(self, sid, name):
        r = (self._settlement(sid).get("plan") or {})["plaza"]["rect"]
        cx, cz = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
        w = r[2] - r[0]
        return {"plaza_centre": (cx, cz), "plaza_centre_west": (cx - w // 4, cz), "plaza_centre_east": (cx + w // 4, cz),
                "plaza_edge_north": (cx, r[1] + 2)}[name]

    def seat_plaza(self, point, actor, spec):
        sid = spec["settlement"]
        plaza = (self._settlement(sid).get("plan") or {})["plaza"]
        r, py = plaza["rect"], plaza["y"]
        nx, nz = self.plaza_point(sid, spec["near"]) if isinstance(spec["near"], str) else spec["near"]
        anchors = [a["rect"] for a in (self._settlement(sid).get("plan") or {}).get("anchors") or [] if a.get("rect")]
        cells = [(x, z) for x in range(r[0] + 2, r[2] - 1) for z in range(r[1] + 2, r[3] - 1)]
        cells.sort(key=lambda c: (math.hypot(c[0] - nx, c[1] - nz), c))
        for x, z in cells:
            if any(a[0] - 2 <= x <= a[2] + 2 and a[1] - 2 <= z <= a[3] + 2 for a in anchors):
                continue
            if self.route_dist(x, z) < NPC_MIN_ROUTE:
                continue
            if not self.apart_ok(x, z, NPC_APART):
                continue
            return {"xz": (x, z), "at": [x, py + 1, z],
                    "ground": {"kind": "plaza", "y": py, "source": "data/placements.json %s plan.plaza" % sid},
                    "anchor": {"settlement": sid, "plaza_rect": r}, "settlement": sid}
        return None

    def seat_street_shoulder(self, point, actor, spec):
        sid = spec["settlement"]
        street = next(s for s in (self._settlement(sid).get("plan") or {})["streets"] if s["id"] == spec["street"])
        poly = street["polyline"]
        half = street.get("width", 3) / 2.0
        nx, nz = spec["near"]
        anchors = [a["rect"] for a in (self._settlement(sid).get("plan") or {}).get("anchors") or [] if a.get("rect")]

        def poly_dist(x, z):
            best = (1e9, None)
            for (ax, az), (bx, bz) in zip(poly, poly[1:]):
                dx, dz = bx - ax, bz - az
                L = dx * dx + dz * dz
                t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L)) if L else 0.0
                px, pz = ax + t * dx, az + t * dz
                d = math.hypot(px - x, pz - z)
                if d < best[0]:
                    best = (d, (px, pz))
            return best
        cells = [(nx + dx, nz + dz) for dx in range(-10, 11) for dz in range(-10, 11)]
        cells.sort(key=lambda c: (math.hypot(c[0] - nx, c[1] - nz), c))
        for x, z in cells:
            d, (px, _pz) = poly_dist(x, z)
            if not half + 2.0 <= d <= half + 5.0:
                continue
            if spec.get("side_of") == "west" and x >= px:
                continue
            if spec.get("side_of") == "east" and x <= px:
                continue
            if any(a[0] - 1 <= x <= a[2] + 1 and a[1] - 1 <= z <= a[3] + 1 for a in anchors):
                continue
            if self.ok(x, z, actor, spec, drop=("town " + sid, "ferry dock")) is None:
                return self._heightmap(x, z, settlement=sid,
                                       anchor={"street": spec["street"], "off_street": round(d, 1)})
        return None


def faces_target(sea, actor, plan_of):
    """((x, z), the words) of the one point the actor faces, so the seat's `faces` names exactly one (x, z)."""
    spec = actor["seat"]["faces"]
    x, z = sea.placed[actor["id"]]
    if spec == "route":
        d, px, pz = sea.nearest_route_point(x, z)
        return (px, pz), "the walked line at (%d, %d), %.1f blocks off" % (px, pz, d)
    if isinstance(spec, dict) and "actor" in spec:
        tx, tz = sea.placed[spec["actor"]]
        return (tx, tz), "%s at (%d, %d)" % (spec["actor"], tx, tz)
    if spec == "plaza_centre":
        sid = actor["seat"]["settlement"]
        tx, tz = sea.plaza_point(sid, "plaza_centre")
        return (tx, tz), "the middle of the plaza at (%d, %d)" % (tx, tz)
    tx, tz = spec
    return (tx, tz), "the point (%d, %d)" % (tx, tz)


def seat_all(tb, g=None):
    """{actor id: seat dict with yaw and faces}, in table order, measured now."""
    sea = Seater(g)
    out = {}
    pending = []
    for p, a in all_actors(tb):
        # an actor that is placed relative to another waits for it; facing waits for everyone
        res = sea.seat(p, a)
        out[a["id"]] = res
        pending.append((p, a))
    for p, a in pending:
        (tx, tz), words = faces_target(sea, a, None)
        x, z = sea.placed[a["id"]]
        out[a["id"]]["yaw"] = sea.RE.yaw_to(tx - x, tz - z)
        out[a["id"]]["faces"] = words
    return out


# ================================================================== the derived records

def rct_of(tb, actor):
    return {"name": {"literal": actor["name"]},
            "battleRules": {"maxItemUses": 0, "healPlayers": False, "adjustPlayerLevels": False,
                            "adjustNPCLevels": False},
            "ai": {"type": "rct", "data": dict(tb["ai_presets"][actor["ai"]])},
            "bag": [],
            "team": json.loads(json.dumps(actor["team"]))}


def trainers_doc(tb, seats):
    """data/compact_route_trainers.json: the seated fighters, record and seat together (the shape of data/hq_trainers.json)."""
    out = []
    for p, a in all_actors(tb):
        if a["role"] != "seated":
            continue
        s = seats[a["id"]]
        e = {"id": a["id"], "display_name": a["name"], "point": p["id"],
             "seat": s["at"], "yaw": s["yaw"], "faces": s["faces"],
             "skin": tb["skins"][a["skin"]], "eye_contact": bool(a.get("eye_contact"))}
        if a.get("eye_contact"):
            e["sight_distance"] = a.get("sight_distance", 6.0)
        e["ground"] = s["ground"]
        for k in ("shoulder", "anchor"):
            if k in s:
                e[k] = s[k]
        e["why"] = a["why"]
        e["team"] = json.loads(json.dumps(a["team"]))
        e["dialogue_text"] = dict(a["lines"])
        e["rct"] = rct_of(tb, a)
        out.append(e)
    return {
        "schema": "cobblers.compact_route_trainers/1",
        "status": "seated %s from the heightmap and the walked lines; placed in no world yet" % tb["status"][:10],
        "generated_by": "python tools/compact_routes.py write, from data/compact_routes.json (the table owns the teams, lines and anchors; the heightmap owns the seat)",
        "consumed_by": "tools/route_trainers.py (the team, the mob, the lines, the defeat advancement and the cycle) and tools/reapply.py R17 (the summon)",
        "design": "docs/story/HAVEN_COMPACT_PASS.md",
        "ground": "tools/ground.py, the canonical heightmap rounded. No world save was read to decide any position",
        "not_verified": "seat dryness (painted water is not in the heightmap) and anything a donor template or a mod put in the same cells are block reads in the exported world",
        "trainers": out,
    }


def npc_trainers_doc(tb):
    """data/compact_route_npc_teams.json: the talk-then-fight NPCs' teams (the shape of data/finale_trainers.json)."""
    out = []
    for p, a in all_actors(tb):
        if a["role"] not in ("fighter", "sider"):
            continue
        out.append({"id": a["trainer"], "display_name": a["name"], "point": p["id"], "npc": a["id"],
                    "conversation": conv_id(a), "sets": [defeated_field(p, a)],
                    "skill": a["skill"],
                    "team_note": a.get("team_note", ""),
                    "team": json.loads(json.dumps(a["team"])),
                    "fights_as": "the Cobblemon NPC %s: its class's party is `team` (tools/compile_dialogue.py battle_class), "
                                 "started from %s's choice, recorded by the cobblers_compact_routes battle_victory callback"
                                 % (a["id"], conv_id(a))})
    return {
        "schema": "cobblers.compact-npc-trainers/1",
        "status": "generated; teams are PLACEHOLDERS for trainer-balance-designer",
        "generated_by": "python tools/compact_routes.py write, from data/compact_routes.json",
        "note": "Teams only. No seat: the NPCs stand where data/npc_seats.json says. No rctmod record: these fight as Cobblemon NPCs.",
        "trainers": out,
    }


def eq(field, value):
    return {"kind": "progression_equals", "field": field, "value": value}


def within(field, values):
    return {"kind": "progression_in", "field": field, "values": list(values)}


def allof(*c):
    c = [x for x in c if x is not None]
    return c[0] if len(c) == 1 else {"kind": "all", "conditions": c}


def line(i, speaker, text, nxt, **extra):
    n = {"id": i, "kind": "line", "speaker": speaker, "text": text, "next": nxt}
    n.update(extra)
    return n


def chain(prefix, speaker, texts, last_next, loop=False):
    nodes = []
    for k, t in enumerate(texts, 1):
        nid = "%s_%03d" % (prefix, k)
        nxt = ("%s_%03d" % (prefix, k + 1)) if k < len(texts) else (nid if loop else last_next)
        nodes.append(line(nid, speaker, t, nxt))
    return nodes


def quest_field(point, name):
    return "quest.%s.%s" % (point["quest"], name)


def conversation(tb, point, actor, W):
    """One NPC's conversation. The entry rules read the player's own stage window and, for a fighter, its defeat field."""
    s, sp, evt = short(actor), actor["speaker"], point["quest"]
    cur = quest_field(point, s + "_cursor")
    win = within(STAGE, W)
    nodes, rules = [], []
    role = actor["role"]
    before = line(s + "_before", sp, actor["before"], s + "_before")
    nodes.append(before)
    after_ids = []

    def add_after(texts):
        ch = chain(s + "_after", sp, texts, None, loop=True)
        nodes.extend(ch)
        after_ids.extend(n["id"] for n in ch)

    note = {}
    if role == "talker":
        nodes += chain(s, sp, actor["lines"], s + "_repeat")
        nodes.append(line(s + "_repeat", sp, actor["repeat"], s + "_repeat"))
        if actor.get("after_requires"):
            add_after(actor["after_lines"])
            f = actor["after_requires"]
            rules.append({"priority": 4, "when": allof(win, eq(f, True), within(cur, after_ids)), "node": "$cursor"})
            rules.append({"priority": 5, "when": allof(win, eq(f, True)), "node": s + "_after_001",
                          "why": "the field that changes what this character says is %s" % f})
        rules.append({"priority": 10, "when": allof(win, eq(cur, s + "_before")), "node": s + "_001",
                      "why": "first time in the window: the account opens"})
        rules.append({"priority": 20, "when": {"kind": "always"}, "node": "$cursor"})
    else:
        done = quest_field(point, actor["trainer"] + "_defeated")
        choice = s + "_choice"
        speakers_narr = "narration"
        add_after(actor["after"])
        rules.append({"priority": 4, "when": allof(win, eq(done, True), within(cur, after_ids)), "node": "$cursor"})
        rules.append({"priority": 5, "when": allof(win, eq(done, True)), "node": s + "_after_001",
                      "why": "this player beat %s (the cobblers_compact_routes callback set %s)" % (actor["name"], done)})
        fight_node = s + "_001"
        if role == "sider":
            other = next(x for x in point["actors"] if x["id"] == actor["other"])
            sw = quest_field(point, "sided_with")
            odone = quest_field(point, other["trainer"] + "_defeated")
            side_choice = s + "_side_choice"
            rules.append({"priority": 6, "when": allof(win, eq(sw, other["side"]), eq(cur, choice)), "node": choice})
            rules.append({"priority": 7, "when": allof(win, eq(sw, other["side"])), "node": s + "_fight_001",
                          "why": "the player stands with %s, so this one tests them" % other["name"]})
            rules.append({"priority": 8, "when": allof(win, eq(sw, actor["side"]), eq(odone, True)),
                          "node": s + "_sided_after"})
            rules.append({"priority": 9, "when": allof(win, eq(sw, actor["side"])), "node": "$cursor"})
            rules.append({"priority": 10, "when": allof(win, eq(cur, side_choice)), "node": side_choice})
            nodes += chain(s, sp, actor["intro"], side_choice)
            nodes.append({"id": side_choice, "kind": "choice", "speaker": sp, "text": actor["side_ask"], "responses": [
                {"id": "r_side", "text": actor["side_yes"], "next": s + "_side_thanks",
                 "actions": [{"kind": "quest_transition", "transition": "side_" + actor["side"]}]},
                {"id": "r_hear", "text": actor["side_no"], "actions": [{"kind": "close_dialogue"}]}]})
            nodes.append(line(s + "_side_thanks", sp, actor["side_thanks"], s + "_side_repeat"))
            nodes.append(line(s + "_side_repeat", sp, actor["side_thanks"], s + "_side_repeat"))
            nodes.append(line(s + "_sided_after", sp, actor["sided_after"], s + "_sided_after"))
            nodes += chain(s + "_fight", sp, actor["fight_intro"], choice)
            note["transition"] = (actor["side"], s)
        else:
            for k, rq in enumerate(actor.get("requires") or []):
                bid = "%s_blocked_%d" % (s, k + 1)
                rules.append({"priority": 6 + k, "when": allof(win, eq(rq["field"], False)), "node": bid,
                              "why": "refused until %s" % rq["field"]})
                nodes.append(line(bid, sp, rq["blocked"], bid))
            rules.append({"priority": 10, "when": allof(win, eq(cur, choice)), "node": choice})
            nodes += chain(s, sp, actor["intro"], choice)
        rules.append({"priority": 12 if role == "fighter" else 14, "when": win, "node": fight_node})
        nodes.append({"id": choice, "kind": "choice", "speaker": speakers_narr, "text": actor["ask"], "responses": [
            {"id": "r_fight", "text": actor["fight"],
             "actions": [{"kind": "npc_battle", "format": "singles", "over_cap_node": s + "_over_cap"}]},
            {"id": "r_decline", "text": actor["decline"], "actions": [{"kind": "close_dialogue"}]}]})
        nodes.append(line(s + "_over_cap", sp, actor["over_cap"], choice,
                          placeholder="Claude, 2026-10-11 (unit CP-ROUTES): a functional refusal line for Codex to replace. "
                                      "Shown instead of the battle when the party's highest level is over the player's RCT "
                                      "level cap (tools/levelcap_pack.py battle_check, read by tools/compile_dialogue.py)"))
    if role != "talker":                       # a talker's priority-20 'always' -> $cursor is its catch-all
        rules.append({"priority": 30, "when": {"kind": "always"}, "node": s + "_before"})
    rules.sort(key=lambda r: r["priority"])
    conv = {
        "id": conv_id(actor), "quest_id": evt, "npc_id": actor["id"], "npc_name": actor["name"],
        "source": "%s %s %s: %s" % (WHO, point["id"], point["slug"], point["serves"]),
        "scope": "player",
        "cursor": {"progression_field": cur, "initial_node": s + "_before", "persist": "after_each_node",
                   "restore": "on_every_interaction", "cursor_is": "next_unread_node"},
        "entry_rules": rules,
        "nodes": nodes,
        "speakers": {sp: actor["name"], "narration": None},
        "placeholder": actor.get("placeholder", "lines are stand-ins for Codex"),
    }
    if not any(n.get("speaker") == "narration" for n in nodes):
        del conv["speakers"]["narration"]
    if role in ("fighter", "sider"):
        conv["npc_battle"] = {"trainers": "compact_route_npc_teams.json", "trainer": actor["trainer"], "skill": actor["skill"]}
    return conv, note


def point_fields(point):
    """The quest.<evt>.* fields of a point with NPCs, and the quest.<tid>.defeated of its seated fighters."""
    out = []
    evt = point.get("quest")
    for a in point["actors"]:
        if a["role"] == "seated":
            tid = a["id"]
            out.append({"id": "quest.%s.defeated" % tid, "quest_id": tid, "field": "defeated", "type": "boolean",
                        "scope": "player", "initial": False,
                        "why": "%s %s (%s), set by its rctmod defeat_count advancement (tools/route_trainers.py); "
                               "data/compact_route_trainers.json" % (point["id"], point["title"], a["name"])})
            continue
        s = short(a)
        out.append({"id": "quest.%s.%s_cursor" % (evt, s), "quest_id": evt, "field": s + "_cursor", "type": "enum",
                    "scope": "player", "initial": s + "_before", "allowed_values": "node ids from " + conv_id(a)})
        if is_fighter(a):
            out.append({"id": "quest.%s.%s_defeated" % (evt, a["trainer"]), "quest_id": evt,
                        "field": a["trainer"] + "_defeated", "type": "boolean", "scope": "player", "initial": False,
                        "why": "%s: this player beat %s, set by the cobblers_compact_routes battle_victory callback "
                               "(tools/compact_routes.py build)" % (point["id"], a["name"])})
    for x in point.get("extra_fields") or []:
        out.append({"id": "quest.%s.%s" % (evt, x["field"]), "quest_id": evt, "field": x["field"], "type": x["type"],
                    "scope": "player", "initial": x["initial"], "allowed_values": x["allowed_values"],
                    "why": "%s: the player's choice at %s" % (point["id"], point["title"])})
    return out


def quest_of(tb, point, notes):
    evt = point["quest"]
    refs = [f["id"] for f in point_fields(point) if f["quest_id"] == evt]
    objectives, transitions = [], []
    for a in point["actors"]:
        if not is_npc(a):
            continue
        s = short(a)
        if is_fighter(a):
            d = quest_field(point, a["trainer"] + "_defeated")
            objectives.append({"id": "beat_" + s, "active_when": {"field": d, "equals": False},
                               "complete_when": {"field": d, "equals": True}, "text": "Beat %s." % a["name"]})
        else:
            c = quest_field(point, s + "_cursor")
            objectives.append({"id": "hear_" + s, "active_when": {"field": c, "equals": s + "_before"},
                               "complete_when": {"field": c, "equals": s + "_repeat"},
                               "text": "Hear what %s has to say." % a["name"]})
        side = notes.get(a["id"], {}).get("transition")
        if side:
            sw = quest_field(point, "sided_with")
            transitions.append({"id": "side_" + side[0], "conditions": [eq(sw, "none")],
                                "effects": [{"kind": "set_progression", "field": sw, "value": side[0]},
                                            {"kind": "set_progression", "field": quest_field(point, side[1] + "_cursor"),
                                             "value": side[1] + "_side_thanks"}]})
    return {
        "id": evt, "source": "%s %s %s: %s" % (WHO, point["id"], point["slug"], point["serves"]),
        "scope": "player", "optional": True, "progression_gate": [],
        "availability": {"conditions": [], "repeatable": False, "npc_remains_after_completion": True},
        "dialogue_ids": [conv_id(a) for a in point["actors"] if is_npc(a)],
        "objectives": objectives, "transitions": transitions,
        "multiplayer": {"state": "per_player", "props": "none: a conversation per NPC",
                        "actors": "Cobblemon NPCs open their own conversation for the player who clicked",
                        "concurrent_players": "independent fields; no player reads or writes another's"},
        "progression_field_refs": refs,
        "stage_window": "from %s to the end of the story (data/progression.json quest.main_worldshift_reveal.stage); "
                        "no gate on any badge" % point["from_stage"],
        "defeat_setter": "only the cobblers_compact_routes battle_victory callback (tools/compact_routes.py build)",
    }


def npc_seat_of(point, actor, seat):
    e = {"id": actor["id"], "conversation": conv_id(actor)}
    if seat.get("settlement"):
        e["settlement"] = seat["settlement"]
    e["at"] = seat["at"]
    e["yaw"] = seat["yaw"]
    e["ground"] = seat["ground"]
    e["faces"] = seat["faces"]
    e["why"] = "%s %s (data/compact_routes.json): %s" % (point["id"], point["title"], point["where"])
    return e


def derive(tb, seats):
    """Every derived record, in memory: {file: ...}. `seats` is {actor id: seat dict}."""
    out = {"conversations": [], "quests": [], "fields": [], "npc_seats": [], "trainers": trainers_doc(tb, seats),
           "npc_trainers": npc_trainers_doc(tb)}
    for p in tb["points"]:
        W = window(p)
        notes = {}
        for a in p["actors"]:
            if is_npc(a):
                c, n = conversation(tb, p, a, W)
                out["conversations"].append(c)
                notes[a["id"]] = n
                out["npc_seats"].append(npc_seat_of(p, a, seats[a["id"]]))
        out["fields"] += point_fields(p)
        if p.get("quest"):
            out["quests"].append(quest_of(tb, p, notes))
    return out


def mine(tb):
    """The ids this table owns in each shared file."""
    d = derive(tb, _blank_seats(tb))
    return {"conversations": {c["id"] for c in d["conversations"]}, "quests": {q["id"] for q in d["quests"]},
            "fields": {f["id"] for f in d["fields"]}, "npc_seats": {s["id"] for s in d["npc_seats"]}}


def _blank_seats(tb):
    return {a["id"]: {"at": [0, 0, 0], "yaw": 0, "faces": "", "ground": {}} for _p, a in all_actors(tb)}


# ================================================================== splicing into the shared files

def dump(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def splice_list(rel, key, ids, new, after_id):
    """Replace this table's records (by id) in data/<rel>'s `key` list: removed wherever they are, inserted after `after_id`."""
    p = DATA / rel
    doc = json.loads(p.read_text(encoding="utf-8"))
    lst = [r for r in doc[key] if r.get("id") not in ids]
    at = next((i for i, r in enumerate(lst) if r.get("id") == after_id), None)
    if at is None:
        raise SystemExit("%s has no %s to splice after" % (rel, after_id))
    doc[key] = lst[:at + 1] + new + lst[at + 1:]
    text = dump(doc)
    if text != p.read_text(encoding="utf-8"):
        p.write_text(text, encoding="utf-8", newline="\n")
        return True
    return False


def splice_quests(ids, new, before=None):
    """data/quests.json is hand-formatted (it does not round-trip through json.dumps), so records are spliced as text:
    the old blocks of this table's ids out, the new ones in before QUEST_BEFORE (or `before`, which tools/fishermen.py
    names so that two tables splicing into the same file never meet at one line)."""
    p = DATA / "quests.json"
    text = p.read_text(encoding="utf-8")
    lines = text.split("\n")
    starts = [i for i, l in enumerate(lines) if l == "    {" and lines[i + 1].startswith('      "id": "')]
    ids_at = {i: lines[i + 1].split('"')[3] for i in starts}
    end_of_array = next(i for i in range(len(lines) - 1, -1, -1) if lines[i] == "  ]")
    bounds = {s: (starts[k + 1] if k + 1 < len(starts) else end_of_array) for k, s in enumerate(starts)}
    drop = set()
    for s in starts:
        if ids_at[s] in ids:
            drop.update(range(s, bounds[s]))
    kept = [l for i, l in enumerate(lines) if i not in drop]
    starts2 = [i for i, l in enumerate(kept) if l == "    {" and kept[i + 1].startswith('      "id": "')]
    at = next(i for i in starts2 if kept[i + 1].split('"')[3] == (before or QUEST_BEFORE))
    block = []
    for q in new:
        body = json.dumps(q, indent=2, ensure_ascii=False).split("\n")
        block += ["    " + b for b in body]
        block[-1] += ","
    out = "\n".join(kept[:at] + block + kept[at:])
    json.loads(out)                              # never write a file that does not parse
    if out != text:
        p.write_text(out, encoding="utf-8", newline="\n")
        return True
    return False


def write_all(tb, seats):
    d = derive(tb, seats)
    ids = mine(tb)
    changed = []
    for rel, doc in (("compact_route_trainers.json", d["trainers"]), ("compact_route_npc_teams.json", d["npc_trainers"])):
        text = dump(doc)
        p = DATA / rel
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            p.write_text(text, encoding="utf-8", newline="\n")
            changed.append(rel)
    if splice_list("dialogue.json", "conversations", ids["conversations"], d["conversations"], DIALOGUE_AFTER):
        changed.append("dialogue.json")
    if splice_list("progression.json", "quest_fields", ids["fields"], d["fields"], FIELD_AFTER):
        changed.append("progression.json")
    if splice_list("npc_seats.json", "seats", ids["npc_seats"], d["npc_seats"], SEAT_AFTER):
        changed.append("npc_seats.json")
    if splice_quests(ids["quests"], d["quests"]):
        changed.append("quests.json")
    return changed


# ================================================================== the pack

def fight_list(tb):
    """[(point, actor, (x, y, z))] for every NPC fighter, the stand read from data/npc_seats.json (not re-measured)."""
    stands = {s["id"]: s["at"] for s in jload("npc_seats.json")["seats"]}
    return [(p, a, stands[a["id"]]) for p, a in all_actors(tb) if a["role"] in ("fighter", "sider")]


def pack_files(tb):
    """{relative path: text}: one function per NPC fighter and the callback that runs it for the winner. The callback is
    the shape tools/hq_tower.py fight_files proved: for each NPC on the losing side and each PLAYER on the winning side, a
    server-sourced `execute as <npc uuid> if entity @s[...]` picks the fight's NPC by its fixed spot, then `as <player
    uuid>` runs the function as that winner. A loss, a flee and every other NPC battle in the world match nothing."""
    out, calls = {}, []
    for p, a, (x, y, z) in fight_list(tb):
        fid = defeated_field(p, a)
        name = "won_" + a["trainer"]
        sel = "@s[type=cobblemon:npc,x=%d.5,y=%d,z=%d.5,distance=..1.5]" % (x, y, z)
        calls.append("      q.run_command('execute as ' + t.l.uuid + ' if entity %s as ' + t.w.player.uuid + "
                     "' run function %s:%s/%s');" % (sel, NS, FOLDER, name))
        mol = "t.d = q.player.data(); t.d.%s = 1; q.player.save_data();" % key(fid)
        out["data/%s/function/%s/%s.mcfunction" % (NS, FOLDER, name)] = "\n".join([
            "# Generated by tools/compact_routes.py: run by the battle_victory callback as the player who beat %s "
            "(%s %s). Writes %s into THAT player's Cobblemon data, as tools/route_trainers.py's won functions do"
            % (a["name"], p["id"], p["slug"], fid),
            'runmolang "%s" @s' % mol]) + "\n"
    out[CALLBACK] = "\n".join(
        ["'Generated by tools/compact_routes.py. The Compact story points: a player who beat one of its NPC fighters runs its won function.';",
         "for_each(t.l, c.scriptable_losers, {",
         "  t.l.is_npc ? {",
         "    for_each(t.w, c.player_winners, {"]
        + calls + ["    });", "  };", "});", ""])
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": 48, "description":
                                              "Cobblers: the Haven Compact story points' fight results (tools/compact_routes.py)"}},
                                    indent=2) + "\n"
    return out


def build(tb, out=OUT):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    files = pack_files(tb)
    for rel, text in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return files


# ================================================================== check and main

def stored_seats(tb):
    """The seats as `write` stored them (no heightmap needed), shaped like seat_all's."""
    npc = {s["id"]: s for s in jload("npc_seats.json")["seats"]}
    tr = {t["id"]: t for t in jload("compact_route_trainers.json")["trainers"]}
    out = {}
    for _p, a in all_actors(tb):
        if a["role"] == "seated":
            t = tr[a["id"]]
            out[a["id"]] = {k: t[k] for k in ("yaw", "faces", "ground", "shoulder", "anchor") if k in t}
            out[a["id"]]["at"] = t["seat"]
        else:
            s = npc[a["id"]]
            out[a["id"]] = {"at": s["at"], "yaw": s["yaw"], "faces": s["faces"], "ground": s["ground"]}
            if "settlement" in s:
                out[a["id"]]["settlement"] = s["settlement"]
    return out


def check(tb):
    """Problems, as strings: the shared files against what the table derives (drift), the table against what it names."""
    probs = []
    try:
        seats = stored_seats(tb)
    except (KeyError, FileNotFoundError):
        return ["the derived records are missing: run `python tools/compact_routes.py write`"]
    d = derive(tb, seats)
    ids = mine(tb)
    have = {
        "conversations": {c["id"]: c for c in jload("dialogue.json")["conversations"]},
        "quest_fields": {c["id"]: c for c in jload("progression.json")["quest_fields"]},
        "seats": {c["id"]: c for c in jload("npc_seats.json")["seats"]},
        "quests": {c["id"]: c for c in jload("quests.json")["quests"]},
    }
    for c in d["conversations"]:
        if have["conversations"].get(c["id"]) != c:
            probs.append("data/dialogue.json: %s differs from the table (run write)" % c["id"])
    for f in d["fields"]:
        if have["quest_fields"].get(f["id"]) != f:
            probs.append("data/progression.json: %s differs from the table (run write)" % f["id"])
    for s in d["npc_seats"]:
        if have["seats"].get(s["id"]) != s:
            probs.append("data/npc_seats.json: %s differs from the table (run write)" % s["id"])
    for q in d["quests"]:
        if have["quests"].get(q["id"]) != q:
            probs.append("data/quests.json: %s differs from the table (run write)" % q["id"])
    for rel, doc in (("compact_route_trainers.json", d["trainers"]), ("compact_route_npc_teams.json", d["npc_trainers"])):
        if jload(rel) != doc:
            probs.append("data/%s differs from the table (run write)" % rel)
    del ids
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("check", "write", "build"))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    tb = table()
    if a.action == "write":
        seats = seat_all(tb)
        changed = write_all(tb, seats)
        print("seated %d actors; wrote: %s" % (len(seats), ", ".join(changed) or "nothing (already current)"))
        for p, act in all_actors(tb):
            s = seats[act["id"]]
            print("  %-28s %-6s at %-18s yaw %4d  %s" % (act["id"], p["id"], s["at"], s["yaw"], s["faces"]))
        return 0
    if a.action == "build":
        files = build(tb, a.out)
        print("wrote %d files to %s" % (len(files), a.out))
        return 0
    probs = check(tb)
    print("compact routes: %s" % ("clean" if not probs else "%d problem(s)" % len(probs)))
    for m in probs:
        print("  PROBLEM " + m)
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
