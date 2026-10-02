#!/usr/bin/env python
"""The ten residents' offline audit: the emitted pack and the re-application steps, against the data and the heightmap.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/resident_encounters.py.
It reads data/resident_encounters.json (Codex's spec and the build block), the canonical heightmap (tools/ground.py),
the painted water (tools/water_mask.py) and the river corridors (data/rivers.json, its own test below), every other
site's data (towns, placements, route lines, Rift zones, elders, saplings, Habitat Blocks, progression flags,
trainers, data/blackout.json, the RCT level-cap config) and derives what it expects from them with its own code. The
only things taken from the generator are its OUTPUTS: the pack and the steps it hands tools/reapply.py, which are what
is being checked. tests/test_resident_encounters.py mutates the GENERATOR's code and leaves the data alone.

  spec       rules hold together (ten, the catch lists, respawn); the build's trigger and leash are the numbers in
             Codex's build_brief text; every status says built, never placed
  site       each anchor, measured: land is dry within 2 and has a sub-region; River Grip is in water with its feet on
             the surface; every anchor is off the route line by trigger + 16, outside every town footprint and
             placement by leash + 16, and outside every Rift zone box
  feet       every spawn, summon, bind, settle and leash names the anchor this audit derives
  writes     the dressing replayed: inside the record's bbox; never under the ground; never on a wet column (River
             Grip's in-water pieces wholly under the surface instead); never within 8 of a route line, 12 of an elder,
             sapling or Habitat Block, inside a town footprint, a placement or a Rift zone; nothing solid where the
             resident stands; every fill is a plant clear (air replace #minecraft:replaceable) at most 3 high
  keeper     per resident: kept only while its chunk is loaded; every kill spares tag=cobblers.guardian and names
             the resident; hold only on tag=!cobblers.guardian; the trigger, leash and settle radii are the record's;
             the spawn carries the level, uncatchable exactly for rules.permanently_uncatchable, and the presence
             gate's advancement exactly when the record has one; the respawn is rules' ticks
  blackout   nothing adds or removes cobblers.guardian or the blackout's exempt tag; no item is given, looted or summoned
  steps      one summon per ungated resident and none for a gated one, guarded on tag and species (never a bare
             distance), inside a forceload of the record's bbox; every dressing run inside its forceload
  catch      from data/trainers.json and the RCT config alone: each catchable resident's level is above every cap a
             player can hold before its gate and within the cap bound after it; Old Jaw is above the cap at its
             intended first meeting. A declared catch_gate_leak is reported, not failed

NOT checked, and it needs a running server: that the blocks land, that the summons and the macro spawn produce one
entity each, that NoAI merged on a live Pokemon holds and releases it, that a woken resident can be battled, how Fight
or Flight treats it, whether Cobblemon's own species drops fire on a knock-out, and every world probe in
docs/world-building/RESIDENT_ENCOUNTERS.md.

  python tools/resident_encounters_audit.py [--pack build/datapacks/cobblers_residents] [--source-root R]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_residents"
GUARDIAN = "cobblers.guardian"     # tools/blackout_pack.py recovery/bind: the tag every claim's guardian carries


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, check, msg):
        self.errors.append("%s: %s" % (check, msg))

    def note(self, msg):
        self.notes.append(msg)


def jload(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _code(text):
    return [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]


# ------------------------------------------------------------------ the world, from data


class World:
    def __init__(self, ground, centres):
        import water_mask as WM
        self.g = ground
        self.WM, self.bodies = WM, WM.bodies()
        rv = jload("rivers.json")
        self.river = []
        for c in rv.get("courses") or []:
            widths = (c.get("character") or {}).get("width") or [32]
            for p in c.get("graded_polyline") or []:
                if any(abs(p[0] - x) < 300 and abs(p[1] - z) < 300 for x, z in centres):
                    self.river.append((p[0], p[1], p[2], max(widths) / 2.0))
        self.routes = [(p[0], p[1]) for ps in jload("route_paths.json")["paths"].values() for p in ps]
        self.rgrid = {}
        for px, pz in self.routes:
            self.rgrid.setdefault((px // 32, pz // 32), []).append((px, pz))
        self.towns = [t["footprint"] for t in jload("towns.json")["towns"]
                      if (t.get("footprint") or {}).get("min_x") is not None]
        self.places = []
        for p in jload("placements.json")["placements"]:
            pos = p.get("position")
            if pos:
                s = p.get("size") or [8, 4, 8]
                self.places.append((pos["x"], pos["z"], pos["x"] + s[0] - 1, pos["z"] + s[2] - 1, p["id"]))
        self.rift = [(k, b) for k, z in jload("rift_zones.json")["zones"].items() for b in z.get("boxes") or []]
        trees = [(e["x"], e["z"], e["id"]) for e in jload("elder_trees.json")["elders"]]
        trees += [(s["x"], s["z"], s["id"]) for s in jload("themed_saplings.json")["saplings"] if s.get("x") is not None]
        trees += [(b["position"]["x"], b["position"]["z"], b.get("id")) for b in jload("habitat_blocks.json")["blocks"]
                  if b.get("position")]
        self.trees = [t for t in trees if any(abs(t[0] - x) < 200 and abs(t[1] - z) < 200 for x, z in centres)]
        self.subs = jload("regions.json")["subregions"]

    def level(self, x, z):
        lv = self.WM.level_at(x, z, self.g, self.bodies)[1]
        if lv is not None:
            return int(lv)
        gy = self.g(x, z)
        for px, pz, sy, half in self.river:
            if math.hypot(px - x, pz - z) <= half and gy < sy:
                return int(round(sy))
        return None

    def route_d(self, x, z, near=64):
        """The distance to the nearest walked route point; exact when it is under `near`, else at least `near`
        (the whole list is scanned only when near is None)."""
        if near is None:
            return min((math.hypot(px - x, pz - z) for px, pz in self.routes), default=1e9)
        r = near // 32 + 1
        pts = [p for i in range(x // 32 - r, x // 32 + r + 1) for j in range(z // 32 - r, z // 32 + r + 1)
               for p in self.rgrid.get((i, j), ())]
        d = min((math.hypot(px - x, pz - z) for px, pz in pts), default=1e9)
        return d if d < near else max(d, near)

    def in_town(self, x, z, m=0):
        return [f for f in self.towns if f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m]

    def in_place(self, x, z, m=0):
        return [p[4] for p in self.places if p[0] - m <= x <= p[2] + m and p[1] - m <= z <= p[3] + m]

    def in_rift(self, x, z):
        return [k for k, b in self.rift if b[0] <= x <= b[2] and b[1] <= z <= b[3]]

    def tree_d(self, x, z):
        return min(((math.hypot(t[0] - x, t[1] - z), t[2]) for t in self.trees), default=(1e9, None))

    def subregion(self, x, z):
        for s in self.subs:
            for poly in s.get("polygons") or []:
                inside, j = False, len(poly) - 1
                for i in range(len(poly)):
                    (xi, zi), (xj, zj) = poly[i], poly[j]
                    if (zi > z + 0.5) != (zj > z + 0.5) and x + 0.5 < (xj - xi) * (z + 0.5 - zi) / (zj - zi) + xi:
                        inside = not inside
                    j = i
                if inside:
                    return s["id"]
        return None


def expected_anchor(e, W):
    x, z = e["location"]["x"], e["location"]["z"]
    if e["build"].get("in_water"):
        lv = W.level(x, z)
        return None if lv is None else (x, lv + 1, z)
    return (x, W.g(x, z) + 1, z)


# ------------------------------------------------------------------ the checks


def check_spec(doc, rep):
    rules, enc = doc["rules"], doc["encounters"]
    if len(enc) != rules["count"] or len({e["id"] for e in enc}) != len(enc):
        rep.err("spec", "%d encounters (unique %d) against rules.count %d" % (len(enc), len({e["id"] for e in enc}), rules["count"]))
    ids = {e["id"] for e in enc}
    for k in ("uncatchable_at_intended_first_meeting", "permanently_uncatchable"):
        for i in rules[k]:
            if i not in ids:
                rep.err("spec", "rules.%s names %s, which is not an encounter" % (k, i))
    if not set(rules["permanently_uncatchable"]) <= set(rules["uncatchable_at_intended_first_meeting"]):
        rep.err("spec", "a permanently uncatchable resident must also be uncatchable at its first meeting")
    if "placed" in doc.get("status", "").replace("not_placed", ""):
        rep.err("spec", "the file status claims placement: %s" % doc["status"])
    for e in enc:
        m = re.search(r"trigger (\d+), leash (\d+)", e["build_brief"])
        bb = e["build"]
        if not m:
            rep.err("spec", "%s: no 'trigger N, leash M' in Codex's build_brief" % e["id"])
        elif (int(m.group(1)), int(m.group(2))) != (bb["trigger"], bb["leash"]):
            rep.err("spec", "%s: build trigger/leash %d/%d, Codex's brief %s/%s" % (e["id"], bb["trigger"], bb["leash"], m.group(1), m.group(2)))
        if e["status"] != "built_not_placed":
            rep.err("spec", "%s: status %s, expected built_not_placed (built, never claimed placed)" % (e["id"], e["status"]))
        if (e["catch_rule"] == "permanently_uncatchable") != (e["id"] in rules["permanently_uncatchable"]):
            rep.err("spec", "%s: catch_rule %s disagrees with rules.permanently_uncatchable" % (e["id"], e["catch_rule"]))


def check_site(doc, W, rep):
    for e in doc["encounters"]:
        bb, i = e["build"], e["id"]
        x, z = e["location"]["x"], e["location"]["z"]
        a = expected_anchor(e, W)
        if a is None:
            rep.err("site", "%s is built in water but (%d, %d) is dry" % (i, x, z))
            continue
        if list(a) != list(bb["anchor"]):
            rep.err("site", "%s: the heightmap gives the anchor %s, the record says %s" % (i, list(a), bb["anchor"]))
        if bb.get("in_water"):
            if not (W.g(x, z) < a[1] - 1):
                rep.err("site", "%s: the bed y%d is not under the water y%d" % (i, W.g(x, z), a[1] - 1))
        else:
            wet = [(dx, dz) for dx in range(-2, 3) for dz in range(-2, 3) if W.level(x + dx, z + dz) is not None]
            if wet:
                rep.err("site", "%s: water within 2 of the anchor at %s" % (i, wet[:3]))
            if W.subregion(x, z) is None:
                rep.err("site", "%s: (%d, %d) is in no sub-region" % (i, x, z))
        d = W.route_d(x, z, None)
        if d < bb["trigger"] + 16:
            rep.err("site", "%s: %.0f from a route line, inside trigger %d + 16" % (i, d, bb["trigger"]))
        if W.in_town(x, z, bb["leash"] + 16):
            rep.err("site", "%s: within leash + 16 of a town footprint" % i)
        if W.in_place(x, z, bb["leash"] + 16):
            rep.err("site", "%s: within leash + 16 of placement %s" % (i, W.in_place(x, z, bb["leash"] + 16)[:2]))
        if W.in_rift(x, z):
            rep.err("site", "%s: inside Rift zone %s" % (i, W.in_rift(x, z)))
        rep.note("%s: anchor %s, ground y%d, route %.0f, sub-region %s, nearest elder/sapling/Habitat Block: %s"
                 % (i, bb["anchor"], W.g(x, z), d, W.subregion(x, z),
                    "%.0f (%s)" % W.tree_d(x, z) if W.tree_d(x, z)[0] <= 200 else "none within 200"))


SET = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace)?$")
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (.+)$")
SOLID_OK = ("minecraft:air", "minecraft:cobweb", "minecraft:snow[", "minecraft:lantern")


def check_writes(doc, W, fns, rep):
    for e in doc["encounters"]:
        i, bb = e["id"], e["build"]
        ax, ay, az = bb["anchor"]
        text = fns.get("%s/dress" % i)
        if text is None:
            rep.err("writes", "%s has no dress function" % i)
            continue
        x0, z0, x1, z1 = bb["bbox"]
        bad = 0
        n = 0
        for line in _code(text):
            m, f = SET.match(line), FILL.match(line)
            if f:
                fx0, fy0, fz0, fx1, fy1, fz1 = (int(v) for v in f.groups()[:6])
                if f.group(7) != "air replace #minecraft:replaceable" or fy1 - fy0 > 2:
                    rep.err("writes", "%s: a fill that is not a plant clear of at most 3: %s" % (i, line[:100]))
                for cx in range(min(fx0, fx1), max(fx0, fx1) + 1):
                    for cz in range(min(fz0, fz1), max(fz0, fz1) + 1):
                        if not (x0 <= cx <= x1 and z0 <= cz <= z1):
                            rep.err("writes", "%s: a clear at (%d, %d) outside the bbox" % (i, cx, cz))
                        if min(fy0, fy1) <= W.g(cx, cz):
                            rep.err("writes", "%s: a clear reaches the ground at (%d, %d)" % (i, cx, cz))
                continue
            if not m:
                rep.err("writes", "%s: a dressing line that is neither setblock nor a plant clear: %s" % (i, line[:100]))
                continue
            n += 1
            x, y, z, block = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
            gy, lv = W.g(x, z), W.level(x, z)
            why = None
            if not (x0 <= x <= x1 and z0 <= z <= z1):
                why = "outside the bbox %s" % bb["bbox"]
            elif y < gy:
                why = "under the ground y%d" % gy
            elif lv is not None and not (bb.get("in_water") and gy < y < lv):
                why = "on a wet column (water y%d)%s" % (lv, "" if bb.get("in_water") else ", and this resident is a land one")
            elif lv is None and y - gy > 12:
                why = "%d above the ground" % (y - gy)
            elif W.route_d(x, z) < 8:
                why = "within 8 of a route line"
            elif W.tree_d(x, z)[0] < 12:
                why = "within 12 of %s" % W.tree_d(x, z)[1]
            elif W.in_town(x, z) or W.in_place(x, z) or W.in_rift(x, z):
                why = "inside a town, a placement or a Rift zone"
            elif any(k["box"][0] <= x <= k["box"][2] and k["box"][1] <= z <= k["box"][3] for k in bb.get("keep_out") or []):
                why = "inside a declared keep-out box (another site's template)"
            elif (max(abs(x - ax), abs(z - az)) <= 1 and ay <= y <= ay + 2 and y > gy and not block.startswith(SOLID_OK)):
                # above the column's own ground: a surface block swapped AT the ground adds nothing solid
                why = "solid where the resident stands"
            if why:
                bad += 1
                if bad <= 5:
                    rep.err("writes", "%s: %s at (%d, %d, %d) %s" % (i, block, x, y, z, why))
        if n == 0:
            # a resident whose ground belongs to a place built round it writes nothing itself, but only when that
            # place's own record names this resident back (integration, 2026-10-02: the Old Orchard and the Sleeper)
            owner = bb.get("dressing_by")
            back = None
            if owner and (ROOT / owner).exists():
                back = json.loads((ROOT / owner).read_text(encoding="utf-8")).get("resident", {}).get("id")
            if back != i:
                rep.err("writes", "%s: the dressing writes no block" % i)
        stand = "fill %d %d %d %d %d %d air replace #minecraft:replaceable" % (ax, ay, az, ax, ay + 1, az)
        if stand not in _code(text):
            rep.err("writes", "%s: no clear of its standing space at the anchor %s" % (i, bb["anchor"]))
        rep.note("%s: %d blocks written, %d off-plan" % (i, n, bad))


def check_keeper(doc, fns, rep):
    b, rules = doc["build"], doc["rules"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    flags = {f["id"] for f in jload("progression.json")["flags"]}
    keeper = _code(fns.get("keeper", ""))
    load = _code(fns.get("load", ""))
    if "scoreboard players set #resp %s %d" % (obj, rules["respawn_ticks_after_faint_death_or_catch"]) not in load:
        rep.err("keeper", "load does not set the respawn to rules' %d ticks" % rules["respawn_ticks_after_faint_death_or_catch"])
    if "%s:%s/load" % (ns, F) not in json.dumps(fns.get("__load_tag__", "")):
        rep.err("keeper", "the load tag does not run %s:%s/load" % (ns, F))
    for e in doc["encounters"]:
        i, bb = e["id"], e["build"]
        ax, ay, az = bb["anchor"]
        sx = "x=%.1f,y=%d,z=%.1f" % (ax + 0.5, ay, az + 0.5)
        at = "%.1f %d %.1f" % (ax + 0.5, ay, az + 0.5)
        P = "%s:%s/%s" % (ns, F, i)
        rtag = "%s.%s" % (b["tag"], i)
        if "execute if loaded %d %d %d run function %s/keep" % (ax, ay, az, P) not in keeper:
            rep.err("keeper", "%s: the keeper does not run its keep, guarded on its anchor's chunk" % i)
        keep, hold = _code(fns.get("%s/keep" % i, "")), _code(fns.get("%s/hold" % i, ""))
        if not any("as @e[type=cobblemon:pokemon,tag=%s,tag=!%s] run function %s/hold" % (rtag, GUARDIAN, P) in l for l in keep):
            rep.err("keeper", "%s: hold is not run only on its non-guardian residents" % i)
        if not any("tag=%s," % GUARDIAN in l and "Species:\"%s\"" % e["species"] in l and "distance=" in l for l in keep):
            rep.err("keeper", "%s: a guardian the blackout rebuilt (no resident tag) is not counted as present" % i)
        want = {"leash": "unless entity @s[%s,distance=..%d] run tp @s %s" % (sx, bb["leash"], at),
                "trigger": "if entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/wake" % (sx, bb["trigger"], P),
                "settle": "unless entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/settle"
                          % (sx, bb["leash"] + b["keeper"]["settle_margin"], P),
                "home": "run tp @s %s %s 0" % (at, bb["yaw"])}
        for k, v in want.items():
            if not any(v in l for l in hold):
                rep.err("keeper", "%s: hold lacks its %s (%s)" % (i, k, v))
        spawn = " ".join(_code(fns.get("%s/spawn" % i, "")))
        sp = e["species"].split(":", 1)[1]
        m = re.search(r'spawn_at \{x:"([-\d.]+)",y:(-?\d+),z:"([-\d.]+)",species:"([^"]+)",props:"([^"]*)"\}', spawn)
        if not m:
            rep.err("keeper", "%s: the spawn does not call the macro spawn_at" % i)
        else:
            if (float(m.group(1)), int(m.group(2)), float(m.group(3))) != (ax + 0.5, ay, az + 0.5) or m.group(4) != sp:
                rep.err("keeper", "%s: the spawn is %s at %s, expected %s at %s" % (i, m.group(4), m.groups()[:3], sp, at))
            props = m.group(5).split()
            if "level=%d" % e["level"] not in props:
                rep.err("keeper", "%s: the spawn lacks level=%d" % (i, e["level"]))
            if ("uncatchable" in props) != (i in rules["permanently_uncatchable"]):
                rep.err("keeper", "%s: uncatchable is %s, rules.permanently_uncatchable says %s"
                        % (i, "uncatchable" in props, i in rules["permanently_uncatchable"]))
        gate = bb.get("appears_after")
        adv = [l for l in keep if "advancements=" in l]
        if gate:
            if gate not in flags:
                rep.err("keeper", "%s: appears_after %s is not a flag in data/progression.json" % (i, gate))
            if not any("advancements={%s:flag/%s=true}" % (ns, gate) in l and "run return 0" in l for l in adv):
                rep.err("keeper", "%s: the spawn is not gated on %s" % (i, gate))
        elif adv:
            rep.err("keeper", "%s: the spawn carries a gate the record does not: %s" % (i, adv[0][:120]))
        if e["intended_stage"] == "pre_gym_1" and gate:
            rep.err("keeper", "%s: met before gym 1 by design but presence-gated on %s" % (i, gate))
        bind = _code(fns.get("%s/bind" % i, ""))
        if "data merge entity @s {NoAI:1b,PersistenceRequired:1b" not in " ".join(bind):
            rep.err("keeper", "%s: bind does not make it persistent and dormant" % i)
    # the kill rule, over the whole pack: no kill may reach a guardian, and every kill names one resident
    for name, text in fns.items():
        for l in _code(text):
            if re.search(r"\bkill\b", l):
                if "tag=!%s" % GUARDIAN not in l or not re.search(r"tag=%s\.\w+" % re.escape(b["tag"]), l):
                    rep.err("blackout", "%s: a kill that could reach a guardian or a non-resident: %s" % (name, l[:120]))


def check_blackout(doc, fns, rep):
    bo = jload("blackout.json")["claims"]
    ex = bo["exempt_tag"]
    if ex in (doc["build"]["tag"], doc["build"]["dormant_tag"]):
        rep.err("blackout", "the residents' tag is the blackout's exempt tag: residents would make no claim")
    for name, text in fns.items():
        for l in _code(text):
            if re.search(r"tag \S+ (add|remove) (%s|%s)\b" % (re.escape(GUARDIAN), re.escape(ex)), l):
                rep.err("blackout", "%s: touches the blackout's tags: %s" % (name, l[:120]))
            if re.match(r"(give|loot)\b", l) or "summon minecraft:item" in l or " run give " in l or " run loot " in l:
                rep.err("blackout", "%s: an item reward (rules.no_loot_drops): %s" % (name, l[:120]))
            if "fightorflight" in l.lower():
                rep.err("blackout", "%s: touches Fight or Flight (rules.aggression): %s" % (name, l[:120]))
    for i in ("wake", "settle", "bind"):
        for e in doc["encounters"]:
            if not fns.get("%s/%s" % (e["id"], i)):
                rep.err("keeper", "%s has no %s function" % (e["id"], i))


def check_steps(doc, steps, rep):
    b, k = doc["build"], doc["build"]["keeper"]
    held = []
    summons = {}
    dressed = set()
    for s in steps:
        if s[0] == "cmd" and s[1].startswith("forceload add "):
            held.append([int(v) for v in s[1].split()[2:6]])
        elif s[0] == "cmd" and s[1].startswith("forceload remove "):
            box = [int(v) for v in s[1].split()[2:6]]
            if box in held:
                held.remove(box)
        elif s[0] == "fn" and s[1].endswith("/dress"):
            dressed.add((s[1].split("/")[-2], tuple(map(tuple, held))))
        elif s[0] == "cmd" and "spawnpokemonat" in s[1]:
            m = re.search(r"tag=%s\.(\w+)" % re.escape(b["tag"]), s[1])
            summons.setdefault(m.group(1) if m else "?", []).append((s[1], [list(h) for h in held]))
    if held:
        rep.err("steps", "forceloads never released: %s" % held)
    for e in doc["encounters"]:
        i, bb = e["id"], e["build"]
        ax, ay, az = bb["anchor"]
        at = "%.1f %d %.1f" % (ax + 0.5, ay, az + 0.5)
        if not any(d[0] == i and list(bb["bbox"]) in [list(h) for h in d[1]] for d in dressed):
            rep.err("steps", "%s: its dressing does not run inside a forceload of its bbox %s" % (i, bb["bbox"]))
        got = summons.get(i, [])
        if bb.get("appears_after"):
            if got:
                rep.err("steps", "%s is presence-gated on %s but the re-application summons it" % (i, bb["appears_after"]))
            continue
        if len(got) != 1:
            rep.err("steps", "%s: %d summon steps, expected 1" % (i, len(got)))
            continue
        cmd, h = got[0]
        if list(bb["bbox"]) not in h:
            rep.err("steps", "%s: the summon is not inside the forceload of its bbox" % i)
        if "unless entity @e[type=cobblemon:pokemon,tag=%s.%s]" % (b["tag"], i) not in cmd:
            rep.err("steps", "%s: the summon guard does not key on its tag" % i)
        for guard in re.findall(r"unless entity (@e\[[^\]]*\])", cmd):
            if "distance=" in guard and "Species" not in guard:
                rep.err("steps", "%s: a guard keys on distance without the species (R14C's failure): %s" % (i, guard))
        if "spawnpokemonat %s %s " % (at, e["species"].split(":", 1)[1]) not in cmd + " ":
            rep.err("steps", "%s: the summon is not at %s" % (i, at))
        if "level=%d" % e["level"] not in cmd.split():
            rep.err("steps", "%s: the summon lacks level=%d" % (i, e["level"]))
        if ("uncatchable" in cmd.split()) != (i in doc["rules"]["permanently_uncatchable"]):
            rep.err("steps", "%s: the summon's uncatchable disagrees with rules" % i)


def _initial_cap():
    t = (ROOT / "modpack" / "config" / "rctmod-server.toml").read_text(encoding="utf-8")
    return int(re.search(r"^\s*initialLevelCap\s*=\s*(\d+)", t, re.M).group(1))


def check_catch(doc, rep):
    """The level-cap refusal as each resident's catch gate, from the trainers alone (upper bounds: a route trainer
    still owed lowers a player's cap further)."""
    tr = jload("trainers.json")
    aces = tr["generation_contract"]["gym_ace_levels"]
    ts = tr["trainers"] if isinstance(tr["trainers"], list) else list(tr["trainers"].values())
    top = {t["id"]: max(m["level"] for m in t.get("team") or [{"level": 0}]) for t in ts}
    e4 = max(top[k] for k in top if k.startswith("elite_"))
    champ = top["champion_blue"]
    before = {"gym%d_cleared" % (n + 1): aces[n] for n in range(8)}
    before["champion_cleared"] = champ
    after = {"gym%d_cleared" % (n + 1): (aces[n + 1] if n < 7 else e4) for n in range(8)}
    stage = {"pre_gym_1": max(_initial_cap(), aces[0])}
    rules = doc["rules"]
    for e in doc["encounters"]:
        i, L, g = e["id"], e["level"], e["gate"]
        if i in rules["permanently_uncatchable"]:
            continue
        if i in rules["uncatchable_at_intended_first_meeting"] and e["intended_stage"] in stage \
                and not L > stage[e["intended_stage"]]:
            rep.err("catch", "%s: level %d is catchable at its intended first meeting (cap %d)" % (i, L, stage[e["intended_stage"]]))
        if g is None:
            continue
        if not L > before[g]:
            if e["build"].get("catch_gate_leak"):
                rep.note("%s: DECLARED catch-gate leak: level %d <= the cap %d a player can hold before %s; presence-gated only"
                         % (i, L, before[g], g))
            else:
                rep.err("catch", "%s: level %d is within the cap %d a player can hold before %s" % (i, L, before[g], g))
        if g in after and L > after[g]:
            rep.err("catch", "%s: level %d is above every cap (%d) a player holds just after %s" % (i, L, after[g], g))


def load_pack(pack, ns, folder):
    fdir = pack / "data" / ns / "function" / folder
    fns = {p.relative_to(fdir).with_suffix("").as_posix(): p.read_text(encoding="utf-8") for p in fdir.rglob("*.mcfunction")}
    tag = pack / "data" / "minecraft" / "tags" / "function" / "load.json"
    fns["__load_tag__"] = tag.read_text(encoding="utf-8") if tag.is_file() else ""
    return fns


def audit(doc, ground, pack, steps):
    rep = Report()
    b = doc["build"]
    fdir = Path(pack) / "data" / b["namespace"] / "function" / b["folder"]
    if not fdir.is_dir():
        rep.err("pack", "%s is missing: run tools/resident_encounters.py first" % fdir)
        return rep
    fns = load_pack(Path(pack), b["namespace"], b["folder"])
    W = World(ground, [(e["location"]["x"], e["location"]["z"]) for e in doc["encounters"]])
    import function_limits
    for name, text in fns.items():
        if name.startswith("__"):
            continue
        for n, cmd, why in function_limits.check_lines(text.splitlines(), where=name):
            rep.err("functions", "%s:%d %s" % (name, n, why))
    check_spec(doc, rep)
    check_site(doc, W, rep)
    check_writes(doc, W, fns, rep)
    check_keeper(doc, fns, rep)
    check_blackout(doc, fns, rep)
    check_steps(doc, steps, rep)
    check_catch(doc, rep)
    # reachability: load tag -> load -> keeper -> keep -> hold/spawn -> ...; steps -> dress, bind_new
    reached, todo = set(), ["load"] + [s[1].split(":", 1)[1].split("/", 1)[1] for s in steps if s[0] == "fn"]
    while todo:
        f = todo.pop()
        if f in reached or f not in fns:
            continue
        reached.add(f)
        todo += re.findall(r"function %s:%s/(\S+)" % (b["namespace"], b["folder"]), fns[f])
    for f in sorted(set(fns) - reached - {"__load_tag__"}):
        rep.err("functions", "%s is reached by nothing" % f)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    import resident_encounters   # for its OUTPUT only: the re-application steps it hands tools/reapply.py
    doc = jload("resident_encounters.json")
    g = G.load(a.source_root)
    rep = audit(doc, g, Path(a.pack), resident_encounters.placement_steps(resident_encounters.load(), g))
    for n in rep.notes:
        print("note: %s" % n)
    for e in rep.errors:
        print("PROBLEM %s" % e)
    print("resident_encounters_audit: %s" % ("clean" if not rep.errors else "%d problem(s)" % len(rep.errors)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
