#!/usr/bin/env python
"""The independent audit of the Merian Ice Lodge pack (tools/ice_lodge.py, data/ice_lodge.json).

It imports nothing from the builder. It replays the written function (every `fill` and `setblock`, in order, with its
own parser) into a voxel map, and checks that map against the RECORD and the heightmap, re-deriving every expectation
itself: the tarn's mask from the lobes' ellipses, the water column under every ice cell, the holes, the Lead's open
water, the shelters, the walk between them, the lights and the melting rule, the lodge's rooms.

The checks, by error prefix:

  pack      the files the pack must have and none it must not; the conversation and the class; no other function
  limits    every write inside a chunk a forceload in the function added earlier; no fill over 32,768 blocks
  ground    every written column is on the cirque floor of the record (the heightmap, rounded)
  clear     no write outside the record's site bounds or inside a keep-clear box
  palette   every block named is in the record's blocks.ids; no spawn-condition block except water, which the policy
            allows by an entry whose scope names ice_lodge
  tarn      each tarn column (an ellipse union) has bed, water to y106, then ice, packed ice, blue ice, planks or a cut
  water     no water cell touches air beside it or open ground below the floor; the water is contained
  lead      the Lead's columns are air over water, and its open-water core (5 by 5 neighbourhood all open) is at least
            the record's size
  holes     each station's hole is air over water, with its stool on ice
  shelters  five by five on the ice, a hole in the middle, a door, a roof, a lantern over the hole
  walk      from the lodge's door to every shelter, the Lead, every station and the cirque path, over blocks a player
            can stand on and through cells a player can pass
  light     (a) plain ice never within reach of a light that would melt it; (b) every floor cell of the lodge and the
            shelters at block light 8 or more (the level monsters cannot spawn at), propagated here, walls opaque
  lodge     the floor, the door pair, the hearth, the bunks (the kept one a different colour), the tackle, the board
  keeper    two air blocks over a floor at her spot; the pack's class and dialogue; the step list
  probes    every probe in data/world_probes.json ice_lodge is true of the replay

  python tools/ice_lodge_audit.py [--pack DIR] [--source-root R]

NOT covered, and it needs a running server: that the fills land, that ice stays where a lantern is not, that the
open-water treasure check holds at the Lead, that water spawns anything, that the keeper renders and talks.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

REC_PATH = ROOT / "data" / "ice_lodge.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_ice_lodge"
FN = "data/cobblers/function/ice_lodge/build.mcfunction"
FILL_LIMIT = 32768
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()

ICE_ALL = ("minecraft:ice", "minecraft:packed_ice", "minecraft:blue_ice")
LIGHTS = {"minecraft:lantern": 15, "minecraft:soul_lantern": 10, "minecraft:campfire": 15}
# opaque to light and to feet: everything not named in PASS is a wall to the light, which can only under-light
LIGHT_PASS = {"minecraft:air", "minecraft:cave_air", "minecraft:glass_pane", "minecraft:spruce_fence", "minecraft:lantern",
              "minecraft:soul_lantern", "minecraft:chain", "minecraft:brown_carpet", "minecraft:campfire",
              "minecraft:spruce_wall_sign", "minecraft:spruce_sign", "minecraft:cauldron", "minecraft:red_bed",
              "minecraft:blue_bed", "minecraft:spruce_pressure_plate", "minecraft:water"}
# a player passes through these (the rest block a body): air, carpet, doors, wall signs, a bottom slab, the walk planks
BODY_FREE = {"minecraft:air", "minecraft:cave_air", "minecraft:brown_carpet", "minecraft:spruce_door",
             "minecraft:spruce_wall_sign", "minecraft:spruce_sign", "minecraft:spruce_slab", "minecraft:spruce_pressure_plate"}
FLOOR_OK = {"minecraft:spruce_planks", "minecraft:ice", "minecraft:packed_ice", "minecraft:blue_ice", "minecraft:cobblestone"}


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, check, msg):
        self.errors.append("%s: %s" % (check, msg))


def base(state):
    return state.split("[")[0].split("{")[0]


def props(state):
    m = re.match(r"[^\[{]*\[([^\]]*)\]", state)
    return dict(kv.split("=", 1) for kv in m.group(1).split(",")) if m else {}


def matches(want, have):
    if have is None:
        return base(want) in ("minecraft:air", "air")
    if base(want) != base(have):
        return False
    hp = props(have)
    return all(hp.get(k) == v for k, v in props(want).items())


# --------------------------------------------------------------------------------------------------- the replay
def replay(lines, rep):
    """({(x, y, z): state}, loaded chunk set at each write checked, clears) from the function's commands."""
    world, clears = {}, []
    loaded = set()
    for n, raw in enumerate(lines, 1):
        l = raw.strip()
        if not l or l.startswith("#"):
            continue
        t = l.split(None, 7)
        if t[0] == "forceload" and t[1] == "add":
            x0, z0, x1, z1 = (int(v) for v in t[2:6])
            for cx in range(min(x0, x1) >> 4, (max(x0, x1) >> 4) + 1):
                for cz in range(min(z0, z1) >> 4, (max(z0, z1) >> 4) + 1):
                    loaded.add((cx, cz))
        elif t[0] == "forceload" and t[1] == "remove":
            x0, z0, x1, z1 = (int(v) for v in t[2:6])
            for cx in range(min(x0, x1) >> 4, (max(x0, x1) >> 4) + 1):
                for cz in range(min(z0, z1) >> 4, (max(z0, z1) >> 4) + 1):
                    loaded.discard((cx, cz))
        elif t[0] == "setblock":
            x, y, z = (int(v) for v in t[1:4])
            state = l.split(None, 4)[4]
            if (x >> 4, z >> 4) not in loaded:
                rep.err("limits", "line %d writes (%d, %d, %d) in a chunk not force-loaded before it" % (n, x, y, z))
            world[(x, y, z)] = state
        elif t[0] == "fill":
            x0, y0, z0, x1, y1, z1 = (int(v) for v in t[1:7])
            rest = l.split(None, 7)[7]
            vol = (abs(x1 - x0) + 1) * (abs(y1 - y0) + 1) * (abs(z1 - z0) + 1)
            if vol > FILL_LIMIT:
                rep.err("limits", "line %d fills %d blocks (limit %d)" % (n, vol, FILL_LIMIT))
            if " replace " in " " + rest:
                clears.append(((min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1)), rest))
                continue
            for cx in range(min(x0, x1) >> 4, (max(x0, x1) >> 4) + 1):
                for cz in range(min(z0, z1) >> 4, (max(z0, z1) >> 4) + 1):
                    if (cx, cz) not in loaded:
                        rep.err("limits", "line %d fills in chunk (%d, %d), not force-loaded before it" % (n, cx, cz))
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        world[(x, y, z)] = rest
        else:
            rep.err("pack", "line %d: command %r is not one this pack may run" % (n, t[0]))
    return world, clears


def box_cells(b):
    x0, z0, x1, z1 = b
    return [(x, z) for x in range(min(x0, x1), max(x0, x1) + 1) for z in range(min(z0, z1), max(z0, z1) + 1)]


def mask_of(rec):
    out = set()
    for lobe in rec["tarn"]["lobes"]:
        (cx, cz), rx, rz = lobe["c"], lobe["rx"], lobe["rz"]
        out |= {(x, z) for x in range(cx - rx - 1, cx + rx + 2) for z in range(cz - rz - 1, cz + rz + 2)
                if ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2 <= 1.0}
    return out


class World:
    """The replayed blocks over the heightmap: a column nothing wrote is natural ground up to g and air above it."""

    def __init__(self, written, g, level):
        self.w, self.g, self.level = written, g, level

    def at(self, x, y, z):
        s = self.w.get((x, y, z))
        if s is not None:
            return s
        return "minecraft:stone" if y <= self.g(x, z) else "minecraft:air"


# ------------------------------------------------------------------------------------------------------- audit
def audit(rec, g, pack_dir=PACK, steps=None, npcs=None):
    rep = Report()
    pack = Path(pack_dir)
    fn = pack / FN
    level = rec["site"]["level"]
    sy = rec["tarn"]["surface_y"]
    wt = rec["tarn"]["water_top_y"]
    # ---- pack
    if not (pack / "pack.mcmeta").is_file() or not fn.is_file():
        rep.err("pack", "no pack.mcmeta or no %s under %s" % (FN, pack))
        return rep
    others = sorted(p.relative_to(pack).as_posix() for p in pack.glob("data/*/function/**/*.mcfunction")
                    if p.relative_to(pack).as_posix() != FN)
    if others:
        rep.err("pack", "more than one function: %s (every function must be run by a step or called)" % others[:3])
    kid = rec["keeper"]["id"]
    for rel in ("data/cobblers/npcs/npc_%s.json" % kid, "data/cobblers/dialogues/dlg_%s.json" % kid):
        if not (pack / rel).is_file():
            rep.err("pack", "missing %s" % rel)
    written, clears = replay(fn.read_text(encoding="utf-8").splitlines(), rep)
    W = World(written, g, level)
    if not written:
        rep.err("pack", "the function writes nothing")
        return rep
    rep.notes.append("%d blocks replayed" % len(written))

    # ---- ground / clear / palette
    cols = {(x, z) for (x, y, z) in written}
    off = sorted(c for c in cols if g(*c) != level)
    if off:
        rep.err("ground", "%d written column(s) are not on y%d (heightmap %s); first %s"
                % (len(off), level, sorted({g(*c) for c in off}), off[:3]))
    bx0, bz0, bx1, bz1 = rec["site"]["bounds"]
    out = sorted(c for c in cols if not (bx0 <= c[0] <= bx1 and bz0 <= c[1] <= bz1))
    if out:
        rep.err("clear", "%d column(s) outside the site bounds; first %s" % (len(out), out[:3]))
    for kc in rec["site"]["keep_clear"]:
        x0, z0, x1, z1 = kc["box"]
        hit = sorted(c for c in cols if x0 <= c[0] <= x1 and z0 <= c[1] <= z1)
        if hit:
            rep.err("clear", "writes %s inside %s" % (hit[:3], kc["id"]))
    for (x0, y0, z0, x1, y1, z1), what in clears:
        if not (bx0 <= x0 and x1 <= bx1 and bz0 <= z0 and z1 <= bz1):
            rep.err("clear", "a clearing fill (%d..%d, %d..%d) leaves the site bounds" % (x0, x1, z0, z1))
        if "#minecraft:replaceable" not in what:
            rep.err("clear", "a clearing fill that is not limited to #minecraft:replaceable: %s" % what)
    allowed = set(rec["blocks"]["ids"])
    names = {base(s) for s in written.values()}
    extra = sorted(names - allowed)
    if extra:
        rep.err("palette", "blocks outside the record's blocks.ids: %s" % extra)
    sb = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    pol = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    ok = {b for w in pol["whitelist"] if "ice_lodge" in (w.get("scope") or "") for b in w["blocks"]}
    if ok - {"minecraft:water"}:
        rep.err("palette", "the policy allows %s for ice_lodge, more than water" % sorted(ok - {"minecraft:water"}))
    bad = sorted((names & sb) - ok)
    if bad:
        rep.err("palette", "spawn-condition block(s) %s with no policy entry scoped to ice_lodge" % bad)

    # ---- the special column sets, derived from the record
    mask = mask_of(rec)
    lead_cells = set(box_cells(rec["lead"]["box"]))
    holes = {tuple(s["hole"]) for s in rec["stations"]}
    n = rec["shelter"]["size"] // 2
    shelter_centres = [tuple(s["c"]) for s in rec["shelters"]]
    cuts = lead_cells | holes | set(shelter_centres)

    # ---- tarn
    ice_ok = set(ICE_ALL) | {"minecraft:spruce_planks"}
    bad_cols = []
    depths = []
    for (x, z) in sorted(mask):
        top = base(W.at(x, sy, z))
        if (x, z) in cuts:
            if top != "minecraft:air":
                bad_cols.append((x, z, "a cut that is %s" % top))
                continue
        elif top not in ice_ok:
            bad_cols.append((x, z, "surface %s" % top))
            continue
        d = 0
        y = wt
        while base(W.at(x, y, z)) == "minecraft:water":
            d += 1
            y -= 1
        if d < 2 or d > 5:
            bad_cols.append((x, z, "water %d deep" % d))
        elif base(W.at(x, y, z)) != base(rec["tarn"]["bed"]):
            bad_cols.append((x, z, "bed %s" % W.at(x, y, z)))
        else:
            depths.append(d)
        if base(W.at(x, sy + 1, z)) not in ("minecraft:air", "minecraft:spruce_fence", "minecraft:spruce_slab", "minecraft:barrel",
                                            "minecraft:cauldron", "minecraft:stripped_spruce_log", "minecraft:spruce_wall_sign") \
                and (x, z) not in cuts:
            pass
    if bad_cols:
        rep.err("tarn", "%d tarn column(s) wrong; first %s" % (len(bad_cols), bad_cols[:3]))
    if depths and (min(depths), max(depths)) != (2, 5):
        rep.err("tarn", "depths run %d..%d, the record says 2..5" % (min(depths), max(depths)))
    stray = sorted((x, y, z) for (x, y, z), s in written.items() if base(s) == "minecraft:water" and (x, z) not in mask)
    if stray:
        rep.err("tarn", "%d water block(s) outside the tarn's ellipses; first %s" % (len(stray), stray[:3]))
    plain = sum(1 for (x, y, z), s in written.items() if y == sy and base(s) == "minecraft:ice")
    if plain < 0.5 * len(mask):
        rep.err("tarn", "only %d plain-ice columns of %d: the tarn would read as frost, not ice" % (plain, len(mask)))

    # ---- water contained
    leaks = []
    for (x, y, z), s in written.items():
        if base(s) != "minecraft:water":
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = base(W.at(x + dx, y, z + dz))
            if nb in ("minecraft:air", "minecraft:cave_air"):
                leaks.append((x, y, z, "air beside"))
        if base(W.at(x, y - 1, z)) in ("minecraft:air", "minecraft:cave_air"):
            leaks.append((x, y, z, "air below"))
        if y == wt and (x, z) not in cuts and base(W.at(x, y + 1, z)) == "minecraft:air":
            leaks.append((x, y, z, "open to air, and not a hole"))
    if leaks:
        rep.err("water", "%d water block(s) are not contained; first %s" % (len(leaks), leaks[:3]))

    # ---- the Lead
    core = 0
    for (x, z) in lead_cells:
        if base(W.at(x, sy, z)) != "minecraft:air" or base(W.at(x, sy + 1, z)) != "minecraft:air":
            rep.err("lead", "column (%d, %d) is not open air over the water" % (x, z))
            break
        if all(base(W.at(x + a, sy, z + b)) == "minecraft:air" and base(W.at(x + a, wt, z + b)) == "minecraft:water"
               and base(W.at(x + a, wt - 1, z + b)) == "minecraft:water" and base(W.at(x + a, wt - 2, z + b)) == "minecraft:water"
               for a in range(-2, 3) for b in range(-2, 3)):
            core += 1
    lx0, lz0, lx1, lz1 = rec["lead"]["box"]
    want_core = max(0, (lx1 - lx0 + 1) - 4) * max(0, (lz1 - lz0 + 1) - 4)
    if core < want_core:
        rep.err("lead", "open-water core is %d columns, the Lead's box allows %d (no 5 by 5 open neighbourhood where it should be)"
                % (core, want_core))
    gap = [tuple(c) for c in rec["lead"]["gap"]]
    ring = [(x, z) for x in range(lx0 - 1, lx1 + 2) for z in range(lz0 - 1, lz1 + 2) if not (lx0 <= x <= lx1 and lz0 <= z <= lz1)]
    for c in ring:
        have = base(W.at(c[0], sy + 1, c[1]))
        if c in gap:
            if have == "minecraft:spruce_fence" or base(W.at(c[0], sy, c[1])) != "minecraft:spruce_planks":
                rep.err("lead", "the gap cell %s should be planks without a fence" % (c,))
        elif have != "minecraft:spruce_fence":
            rep.err("lead", "ring cell %s has %s, not a fence" % (c, have))
            break

    # ---- holes
    for s in rec["stations"]:
        hx, hz = s["hole"]
        if base(W.at(hx, sy, hz)) != "minecraft:air" or base(W.at(hx, wt, hz)) != "minecraft:water":
            rep.err("holes", "%s: the hole at (%d, %d) is not air over water" % (s["id"], hx, hz))
        kx, kz = s["stool"]
        if base(W.at(kx, sy + 1, kz)) != "minecraft:spruce_slab" or base(W.at(kx, sy, kz)) not in ICE_ALL:
            rep.err("holes", "%s: no stool slab on ice at (%d, %d)" % (s["id"], kx, kz))

    # ---- shelters
    fr = rec["shelter"]["frost_radius"]
    for s in rec["shelters"]:
        cx, cz = s["c"]
        if any((cx + a, cz + b) not in mask for a in range(-n, n + 1) for b in range(-n, n + 1)):
            rep.err("shelters", "%s: not wholly on the ice" % s["id"])
        if base(W.at(cx, sy, cz)) != "minecraft:air" or base(W.at(cx, wt, cz)) != "minecraft:water":
            rep.err("shelters", "%s: no hole in the middle of its floor" % s["id"])
        if base(W.at(cx, sy + 3, cz)) != "minecraft:lantern" or "hanging=true" not in W.at(cx, sy + 3, cz):
            rep.err("shelters", "%s: no lantern hanging over the hole" % s["id"])
        if base(W.at(cx, sy + 4, cz)) != "minecraft:spruce_planks":
            rep.err("shelters", "%s: no roof over the hole" % s["id"])
        dx, dz = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}[s["door"]]
        dcell = (cx + dx * n, cz + dz * n)
        if base(W.at(dcell[0], sy + 1, dcell[1])) != "minecraft:spruce_door":
            rep.err("shelters", "%s: no door at %s" % (s["id"], dcell))
        walls = [(cx + a, cz + b) for a in range(-n, n + 1) for b in range(-n, n + 1) if max(abs(a), abs(b)) == n and (cx + a, cz + b) != dcell]
        if any(base(W.at(c[0], sy + 1, c[1])) in ("minecraft:air",) for c in walls):
            rep.err("shelters", "%s: a wall course has a gap" % s["id"])
        for a in range(-fr, fr + 1):
            for b in range(-fr, fr + 1):
                if abs(a) + abs(b) <= fr and (cx + a, cz + b) in mask and base(W.at(cx + a, sy, cz + b)) == "minecraft:ice":
                    rep.err("shelters", "%s: plain ice at (%d, %d) inside the frost diamond" % (s["id"], cx + a, cz + b))
                    break

    # ---- the walk
    walkable = walk_graph(W, rec, level)
    start = (rec["lodge"]["door"]["cells"][0][0], rec["lodge"]["door"]["cells"][0][1] - 1)
    targets = {"the cirque path's foot": (2813, 1042), "the keeper": tuple(rec["keeper"]["at"])}
    for s in rec["shelters"]:
        cx, cz = s["c"]
        dx, dz = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}[s["door"]]
        targets["%s's floor" % s["id"]] = (cx + dx * (n - 1), cz + dz * (n - 1))
    targets["the Lead's gap"] = tuple(gap[len(gap) // 2])
    seen = flood(walkable, start)
    if start not in walkable:
        rep.err("walk", "the lodge's door has nothing to stand on just inside, at %s" % (start,))
    for name, c in targets.items():
        if c not in seen:
            rep.err("walk", "%s at %s cannot be reached on foot from the lodge's door" % (name, c))
    for s in rec["stations"]:
        hx, hz = s["hole"]
        if not any((hx + a, hz + b) in seen for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            rep.err("walk", "%s: no reachable cell beside the hole at (%d, %d)" % (s["id"], hx, hz))

    # ---- light
    ices = [(x, y, z) for (x, y, z), s in written.items() if base(s) == "minecraft:ice"]
    lim = rec["tarn"]["light_rule"]["melts_above_block_light"] - rec["tarn"]["light_rule"]["margin"]
    for (x, y, z), s in written.items():
        lv = LIGHTS.get(base(s))
        if lv is None or lv <= lim or (base(s) == "minecraft:campfire" and "lit=false" in s):
            continue
        d = min((abs(x - a) + abs(y - b) + abs(z - c) for a, b, c in ices), default=99)
        if d < lv - lim:
            rep.err("light", "%s at %s is %d from plain ice, a level-%d light needs %d" % (base(s), (x, y, z), d, lv, lv - lim))
    lit = light_map(W, written, rec)
    L = rec["lodge"]
    f = L["floor_y"]
    x0, z0, x1, z1 = L["box"]
    rooms = {"lodge": [(x, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)]}
    for s in rec["shelters"]:
        cx, cz = s["c"]
        rooms[s["id"]] = [(cx + a, cz + b) for a in range(-n + 1, n) for b in range(-n + 1, n) if (a, b) != (0, 0)]
    for name, cells in rooms.items():
        dark = []
        for (x, z) in cells:
            fl = base(W.at(x, f, z))
            if fl in FLOOR_OK and base(W.at(x, f + 1, z)) in BODY_FREE | {"minecraft:brown_carpet"}:
                if lit.get((x, f + 1, z), 0) < 8:
                    dark.append((x, z, lit.get((x, f + 1, z), 0)))
        if dark:
            rep.err("light", "%s: %d floor cell(s) below block light 8 (a monster can spawn); first %s" % (name, len(dark), dark[:3]))

    # ---- the lodge
    for c in L["door"]["cells"]:
        if base(W.at(c[0], f + 1, c[1])) != "minecraft:spruce_door" or base(W.at(c[0], f + 2, c[1])) != "minecraft:spruce_door":
            rep.err("lodge", "no two-high door at %s" % (c,))
    hx, hz = L["hearth"]["campfire"]
    if not matches("minecraft:campfire[lit=true]", W.at(hx, f + 1, hz)):
        rep.err("lodge", "no lit campfire at the hearth %s" % ((hx, hz),))
    if base(W.at(hx, f, hz)) != "minecraft:cobblestone":
        rep.err("lodge", "the hearth stands on %s, not stone" % W.at(hx, f, hz))
    for b in L["bunks"]:
        a, c = b["head"]
        if not matches(b["bed"] + "[part=head]", W.at(a, f + 1, c)) or not matches(b["bed"] + "[part=foot]", W.at(a, f + 1, c + 1)):
            rep.err("lodge", "%s: the bed is not whole at %s" % (b["id"], (a, c)))
    if len({b["bed"] for b in L["bunks"]}) < 2:
        rep.err("lodge", "the kept bunk is not told apart from the others by colour")
    for t in L["tackle"]:
        if not matches(t["block"], W.at(t["at"][0], f + 1, t["at"][1])):
            rep.err("lodge", "no %s at %s" % (t["block"], t["at"]))
    signs = [W.at(L["board"]["sign_x"], L["board"]["y"][0], z) for z in L["board"]["z"]]
    if any(base(s) != "minecraft:spruce_wall_sign" for s in signs):
        rep.err("lodge", "the catch board is missing a sign")
    for (x, z) in L["lanterns"]:
        if base(W.at(x, f + 2, z)) != "minecraft:lantern" or base(W.at(x, f + 1, z)) != "minecraft:spruce_fence":
            rep.err("lodge", "no lantern on a post at %s" % ((x, z),))
    for r in rec["racks"]:
        if base(W.at(r["x0"] + 3, f + 4, r["z"])) != "minecraft:stripped_spruce_log" or base(W.at(r["x0"] + 1, f + 2, r["z"])) != "minecraft:dried_kelp_block":
            rep.err("lodge", "%s: beam or hanging bundle missing" % r["id"])
    sm0, sm1 = L["smoke_hole"]
    open_roof = []
    for x in range(x0, x1 + 1):
        for z in range(z0 + 1, z1):
            capped = any(base(W.at(x, y, z)) not in ("minecraft:air", "minecraft:cave_air") for y in range(f + 5, f + 11))
            hole = sm0 <= x <= sm1 and z == L["ridge_z"]
            if capped == hole:
                open_roof.append((x, z, "open" if hole is False else "capped"))
    if open_roof:
        rep.err("lodge", "the roof is open where it should be closed or closed over the smoke hole: %s" % open_roof[:3])

    # ---- keeper
    kx, kz = rec["keeper"]["at"]
    if base(W.at(kx, f, kz)) not in FLOOR_OK or base(W.at(kx, f + 1, kz)) != "minecraft:air" or base(W.at(kx, f + 2, kz)) != "minecraft:air":
        rep.err("keeper", "(%d, %d) is not a floor with two blocks of air over it" % (kx, kz))
    if not (x0 < kx < x1 and z0 < kz < z1):
        rep.err("keeper", "the keeper is not inside the lodge")
    if steps is not None:
        hold = "%d %d %d %d" % tuple(rec["site"]["hold"])
        want = [("cmd", "forceload add " + hold), ("fn", "cobblers:ice_lodge/build"), ("cmd", "forceload remove " + hold)]
        have = [s for s in steps if s[0] in ("cmd", "fn")]
        if have != want:
            rep.err("keeper", "the step list is %s, expected %s" % (have, want))
        nps = [s[1] for s in steps if s[0] == "npc"]
        if nps != [("dlg_%s" % kid, (kx, f + 1, kz), "cobblers:npc_%s" % kid, rec["keeper"]["yaw"])]:
            rep.err("keeper", "the step list's NPC is %s" % nps)
        order = [s[0] for s in steps]
        if order.index("fn") > order.index("npc"):
            rep.err("keeper", "the keeper is placed before the blocks")

    # ---- probes
    wp = ROOT / "data" / "world_probes.json"
    rows = json.loads(wp.read_text(encoding="utf-8"))["places"].get("ice_lodge")
    if not rows:
        rep.err("probes", "data/world_probes.json has no ice_lodge probes")
    else:
        for r in rows:
            if "block" in r:
                x, y, z, want = r["block"]
                if not matches(want, written.get((x, y, z))) == r.get("expect", True):
                    rep.err("probes", "%r says %s at %s but the replay has %s" % (r["what"], want, (x, y, z), written.get((x, y, z))))
        if not any("entity" in r for r in rows):
            rep.err("probes", "no probe for the keeper")
        if len([r for r in rows if "block" in r]) < 20:
            rep.err("probes", "fewer than 20 block probes")
    return rep


# ----------------------------------------------------------------------------------------------- walking and light
def walk_graph(W, rec, level):
    f = level
    x0, z0, x1, z1 = 2700, 1042, 2830, 1110
    ok = set()
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            floor = base(W.at(x, f, z))
            if floor == "minecraft:stone" or floor in FLOOR_OK:
                pass
            else:
                continue
            b1, b2 = base(W.at(x, f + 1, z)), base(W.at(x, f + 2, z))
            if b1 in BODY_FREE and b2 in BODY_FREE:
                ok.add((x, z))
    return ok


def flood(ok, start):
    if start not in ok:
        return set()
    seen, q = {start}, deque([start])
    while q:
        x, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, z + dz)
            if n in ok and n not in seen:
                seen.add(n)
                q.append(n)
    return seen


def light_map(W, written, rec):
    """Block light from every light in the function, 1 lost per block, through anything in LIGHT_PASS and nothing else
    (unwritten air is air; unwritten ground and every other block is a wall). Returns {(x, y, z): level}."""
    lit = {}
    q = deque()
    for (x, y, z), s in written.items():
        lv = LIGHTS.get(base(s))
        if lv and not (base(s) == "minecraft:campfire" and "lit=false" in s):
            lit[(x, y, z)] = lv
            q.append((x, y, z))
    while q:
        c = q.popleft()
        lv = lit[c]
        if lv <= 1:
            continue
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (c[0] + d[0], c[1] + d[1], c[2] + d[2])
            if lit.get(n, 0) >= lv - 1:
                continue
            if base(W.at(*n)) not in LIGHT_PASS:
                continue
            lit[n] = lv - 1
            q.append(n)
    return lit


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rec = json.loads(REC_PATH.read_text(encoding="utf-8"))
    g = G.load(a.source_root)
    rep = audit(rec, g, a.pack)
    # the registration, from reapply.py's text (the audit does not import the builder or the step list)
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    if '"cobblers_ice_lodge"' not in src or '("R18IL"' not in src or 'add("ice_lodge:build"' not in src:
        rep.err("pack", "tools/reapply.py does not register cobblers_ice_lodge, R18IL and the build job")
    for n in rep.notes:
        print(n)
    for e in rep.errors:
        print("PROBLEM", e)
    print("ice_lodge audit: %d problem(s)" % len(rep.errors))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
