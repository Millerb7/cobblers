#!/usr/bin/env python
"""Offline audit of the Seaward Drift, its strip mine, its gatehouses and Driftmouth Isle with its lighthouse
(tools/sea_drift.py, data/sea_drift.json).

Independent of tools/sea_drift.py: nothing is imported from it and nothing is taken from its plan. The pack it wrote
(build/datapacks/cobblers_sea_drift, every function in index order) is REPLAYED over a world made only from the canonical
heightmap (tools/ground.py, rounded: solid to the ground, painted water over it to the sea level or a lake's level, air
above), and the result is checked against rules the data and the other files state:

  water     every cell the pack opens (left non-solid where the heightmap world had rock or water) keeps at least
            cover + 1 Chebyshev from any water left in the replayed world, cover being the data's three parts summed
            here (shell_r + export_tolerance + natural_seabed); no write is a fluid; the measured minimum is reported
  sealed    every opened cell under the heightmap world's surface touches only opened cells, blocks the pack wrote, or
            open air: never an unwritten natural block (a cave, the export's gravel) and never water
  route     the data's route is two ends on one axis (the owner, 2026-10-02: "a straight shot to the island")
  walk      a player can walk from the line's stop in Foothill Gate to both of its doors, down the road and up the climb
            into the keeper's hall, out of its south door, up the tower's stair to the lantern room, and to both
            barrels, on full blocks and stairs, never climbing a whole block without a stair (a rail is not a stair)
  light     block light flooded from every light source the pack writes (lanterns and glowstone, at their cited 15)
            reaches 1 or more at every floor cell under a roof: no cell a hostile could spawn on is at light 0 (there
            are none in this pack, docs/STATE.md; the rule holds anyway)
  gatehouse Foothill Gate and the keeper's hall: every wall cell solid but the data's doors and the road's own opening
            (over a rail of the line, within the tube's half-width and height), the roof whole, a sign naming the
            place, the line's stop inside with its buffer in the wall
  lighthouse the tower's walls whole to the lantern room, the room glazed with the data's glazing, a lamp in it of a
            light-emitting block this audit knows (and no spawn condition, by `blocks`), lit, with nothing but glass
            between it and the open air on all four sides, at least 10 over the isle's crown
  blocks    no written block is named by a spawn condition (data/spawn_blocks.json); every ore is one the data lists
            (or its deepslate variant) and stands in the strip mine's own area (north of the drift, within the
            branches' reach of the junction)
  ores      every branch the data's numbers give (first_branch_z, branch_every, corridor_to_z) exposes an ore, and the
            far half of the branches exposes more gold and lapis than the near half
  isle      Driftmouth Isle has dry ground and a shingle tide line; its record's ground_y is the replayed ground at its
            centre and its heightmap_seabed_y the heightmap's; the road surfaces only inside the keeper's hall
  habitats  every data/habitat_blocks.json record of the isle's sits on its mimic block in the replayed world, rock on
            all six sides, water within its spawn box (and the sea's surface for the upper ones); its pool exists in
            data/spawns.json, has none of the three species the owner named (Magikarp, Goldeen, Barraskewda), and
            every species in it is placed by an existing spawnable position
  rewards   both caches' containers are barrels in the replayed world and their trigger boxes hold a walkable place
  rails     the rail line, read from the replayed blocks: every rail joins its neighbours by its shape's ends into ONE
            line (a connected graph, no junction, no loop) whose two ends are the route's two ends, on Foothill Gate's
            floor and the keeper's hall's, every rail on it, standing on a solid block; no rail turns
  straight  every rail of that line on the axis through its two ends, each one column further along than the last
  power     every powered rail written powered has a lever (switched on, sealed in rock) or other source beside it or
            under its bed; none written unpowered can be reached by power; no activator rail can be powered by a
            source or a passing cart
  stops     each end is an unpowered powered rail with a solid buffer beyond it, a button that powers it, no detector
            beside it, and a walkable place at it
  boost     every climbing rail powered; no run of unpowered rails longer than data rail_line physics allows (the
            cited full-speed run over the margin)
  limits    tools/function_limits.py finds nothing the server would refuse

Fails closed: no pack, an empty index, an unknown command, no lantern or no habitat record is a failure.

  python tools/sea_drift_audit.py [--source-root DIR] [--pack DIR]   writes derived/sea_drift/audit.json; exit 1 on any
                                                                      problem
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402
import terrain as T            # noqa: E402
import water_mask as WM        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "sea_drift.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_sea_drift"
OUT = ROOT / "derived" / "sea_drift" / "audit.json"
NOT_WANTED = ("magikarp", "goldeen", "barraskewda")       # the owner, 2026-10-02 brief: the species every lake has
NUM = r"(-?\d+)"
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)(?: replace (\S+))?$" % ((NUM,) * 6))
SET = re.compile(r"^setblock %s %s %s (\S+?(?:\{.*\})?)$" % ((NUM,) * 3))      # a sign's text has spaces
NATURAL, WATER, OPEN = "natural", "water", "open-air"


class AuditError(Exception):
    pass


def bid(b):
    return b.split("[")[0].split("{")[0]


def passable(b):
    """A body can stand in it: air, a rail, a button. Not a lantern (it has a hitbox), a fence, a barrel or a stair."""
    i = bid(b)
    return (i in ("minecraft:air", "minecraft:cave_air", OPEN) or i.endswith("rail") or i.endswith("_button")
            or i.endswith("_wall_sign"))


def transparent(b):
    """Block light passes: air, rails, lanterns, fences, stairs (half open), signs, glass; not full blocks or fluids."""
    i = bid(b)
    return (passable(b) or i.endswith("lantern") or i.endswith("_fence") or i.endswith("_stairs")
            or i in ("minecraft:glass", "minecraft:glass_pane"))


# the block light each light source emits (minecraft.wiki: Light, "Light-emitting blocks"); a lamp the pack writes that
# is not one of these is no lamp
LIGHTS = {"minecraft:lantern": 15, "minecraft:glowstone": 15, "minecraft:sea_lantern": 15, "minecraft:shroomlight": 15,
          "minecraft:ochre_froglight": 15, "minecraft:verdant_froglight": 15, "minecraft:pearlescent_froglight": 15}


def solid_floor(b):
    """A full block a body can stand on (not air, water, a rail, a lantern, a fence or a stair)."""
    return not transparent(b) and b != WATER


class World:
    """The heightmap world with the pack's writes over it."""

    def __init__(self, g, sea):
        self.g, self.sea = g, sea
        self.w = {}
        self.built = set()        # cells the pack wrote solid at some point (then perhaps opened again)
        self.cols = {}
        self.lakes = [(b["level_y"], b["basin"], _bbox(b["basin"])) for b in WM.bodies().values() if b["basin"]]

    def level(self, x, z):
        k = (x, z)
        if k not in self.cols:
            gy = self.g(x, z)
            lv = None
            for lev, basin, (x0, z0, x1, z1) in self.lakes:
                if x0 <= x <= x1 and z0 <= z <= z1 and gy < lev and WM.in_polygons(basin, x, z):
                    lv = max(lv or -1, int(lev))
            if lv is None and gy < self.sea:
                lv = self.sea
            self.cols[k] = (gy, lv)
        return self.cols[k]

    def base(self, x, y, z):
        gy, lv = self.level(x, z)
        if y <= gy:
            return NATURAL
        if lv is not None and y <= lv:
            return WATER
        return OPEN

    def at(self, x, y, z):
        return self.w.get((x, y, z)) or self.base(x, y, z)

    def water_ys(self, x, z):
        gy, lv = self.level(x, z)
        if lv is None:
            return []
        return [y for y in range(gy + 1, lv + 1) if (x, y, z) not in self.w]


def _bbox(polys):
    pts = [p for poly in polys for p in poly]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def replay(pack, world):
    fn = pack / "data" / "cobblers" / "function" / "sea_drift"
    idx = fn / "index.txt"
    if not idx.is_file():
        raise AuditError("no %s" % idx)
    names = [l.strip() for l in idx.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not names:
        raise AuditError("the pack's index is empty")
    for n in names:
        for ln in (fn / (n + ".mcfunction")).read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or ln.startswith("forceload "):
                continue
            mt = FILL.match(ln)
            if mt:
                x0, y0, z0, x1, y1, z1 = (int(v) for v in mt.groups()[:6])
                b, flt = mt.group(7), mt.group(8)
                if flt:
                    raise AuditError("%s: a filtered fill is not modelled: %s" % (n, ln))
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        for y in range(min(y0, y1), max(y0, y1) + 1):
                            world.w[(x, y, z)] = b
                            if not transparent(b):
                                world.built.add((x, y, z))
                continue
            mt = SET.match(ln)
            if mt:
                x, y, z = (int(v) for v in mt.groups()[:3])
                world.w[(x, y, z)] = mt.group(4)
                if not transparent(mt.group(4)):
                    world.built.add((x, y, z))
                continue
            raise AuditError("%s: a command the audit does not model: %s" % (n, ln[:80]))
    return names


N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def audit(source_root=None, pack=PACK, spec=None):
    spec = spec or json.loads(SPEC.read_text(encoding="utf-8"))
    g = G.load(source_root)
    sea = int(T.sea_level(g.world))
    W = World(g, sea)
    names = replay(Path(pack), W)
    P = []
    res = {"functions": len(names), "writes": len(W.w)}

    # -- opened cells: written non-solid where the heightmap world had rock or water, or where the pack itself had
    #    built (the isle's rock the stairwell climbs through)
    opened = set()
    for (x, y, z), b in W.w.items():
        if transparent(b) and (W.base(x, y, z) in (NATURAL, WATER) or (x, y, z) in W.built):
            opened.add((x, y, z))
        if bid(b) in ("minecraft:water", "minecraft:lava", "minecraft:flowing_water"):
            P.append("blocks: a fluid written at (%d, %d, %d)" % (x, y, z))
    res["opened"] = len(opened)
    if not opened:
        P.append("the pack opens nothing")

    # -- water
    cover = int(spec["shell_r"]) + int(spec["cover"]["export_tolerance"]) + int(spec["cover"]["natural_seabed"])
    res["cover_required"] = cover
    span = {}
    for (x, y, z) in opened:
        lo, hi = span.get((x, z), (y, y))
        span[(x, z)] = (min(lo, y), max(hi, y))
    wys = {}
    least = None
    for (x, z), (lo, hi) in span.items():
        for a in range(-cover, cover + 1):
            for c in range(-cover, cover + 1):
                k = (x + a, z + c)
                if k not in wys:
                    wys[k] = W.water_ys(*k)
                for wy in wys[k]:
                    d = max(abs(a), abs(c), 0 if lo <= wy <= hi else min(abs(wy - lo), abs(wy - hi)))
                    if least is None or d - 1 < least[0]:
                        least = (d - 1, (x, z), wy)
    res["cover_min_measured"] = least[0] if least else None
    if least and least[0] < cover:
        P.append("water: %d solid blocks between the opening at column (%d, %d) and water at y%d, under %d"
                 % (least[0], least[1][0], least[1][1], least[2], cover))

    # -- sealed
    leaks = []
    for (x, y, z) in opened:
        for a, b_, c in N6:
            q = (x + a, y + b_, z + c)
            if q in opened or q in W.w:
                continue
            base = W.base(*q)
            if base != OPEN:
                leaks.append((q, base))
    res["leaks"] = len(leaks)
    for q, base in leaks[:5]:
        P.append("sealed: (%d, %d, %d) is unwritten %s beside an opened cell" % (q + (base,)))

    # -- route: two ends on one axis (the owner: "a straight shot to the island"); the line's own straightness is read
    #    from the rails below
    vs = spec["route"]["vertices"]
    if len(vs) != 2 or (vs[0][0] != vs[1][0] and vs[0][1] != vs[1][1]):
        P.append("route: the data's route %s is not two ends on one axis" % (vs,))

    # -- walk: a standing place is a full block's top (one height) or a stair (its low half and its high half, so a
    #    run of stairs is walked half a block at a time); a move may change height by half a block at most
    def node_h(x, y, z):
        b = W.at(x, y, z)
        if bid(b).endswith("_stairs"):
            return (y + 0.5, y + 1.0) if passable(W.at(x, y + 1, z)) and passable(W.at(x, y + 2, z)) else None
        if passable(b) and passable(W.at(x, y + 1, z)) and solid_floor(W.at(x, y - 1, z)):
            return (float(y),)
        return None

    def step_ok(ha, hb):
        return min(abs(a - b) for a in ha for b in hb) <= 0.5

    def ours(x, y, z):
        return (x, y, z) in W.w or (x, y - 1, z) in W.w

    vx, vz = spec["route"]["vertices"][0]
    start = (vx, g(vx, vz) + 1, vz)
    seen = {}
    if node_h(*start) is not None:
        seen[start] = node_h(*start)
    dq = deque(seen)
    while dq:
        x, y, z = dq.popleft()
        h = seen[(x, y, z)]
        for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (-1, 0, 1):
                q = (x + a, y + dy, z + c)
                if q in seen or not ours(*q):
                    continue
                hq = node_h(*q)
                if hq is not None and step_ok(hq, h):
                    seen[q] = hq
                    dq.append(q)
    res["walk_nodes"] = len(seen)
    isl = spec["island"]
    lh = isl["lighthouse"]
    x0, z0, x1, z1 = lh["hall"]["box"]
    gh = spec["gatehouse"]
    goals = [("the keeper's hall's south door", (lh["hall"]["door_x"][0], isl["pad_y"] + 1, z1))]
    goals += [("Foothill Gate's %s door" % side, (gh["doors_x"][0], gh["floor_y"] + 1, zz))
              for side, zz in (("north", gh["box"][1]), ("south", gh["box"][3]))]
    tx0, tz0, tx1, tz1 = lh["tower"]["box"]
    fl = lh["tower"]["lantern_room_feet"]
    room = [(x, fl, z) for x in range(tx0 + 1, tx1) for z in range(tz0 + 1, tz1)]
    for what, p in goals:
        if p not in seen:
            P.append("walk: %s %s is not reached from the line's stop in the gatehouse %s" % (what, p, start))
    if not any(p in seen for p in room):
        P.append("walk: the lighthouse's lantern room (feet y%d) is not reached up the tower's stair" % fl)

    # -- light (flooded from every light source the pack writes)
    lanterns = [p for p, b in W.w.items() if bid(b) in LIGHTS]
    if not lanterns:
        P.append("light: the pack writes no lantern")
    light = {p: LIGHTS[bid(W.w[p])] for p in lanterns}
    frontier = list(lanterns)
    for lv in range(14, 0, -1):
        nxt = []
        for (x, y, z) in frontier:
            for a, b_, c in N6:
                q = (x + a, y + b_, z + c)
                if light.get(q, 0) >= lv or not transparent(W.at(*q)):
                    continue
                light[q] = lv
                nxt.append(q)
        frontier = nxt
    dark = []
    for (x, y, z), h in seen.items():
        if len(h) != 1:
            continue
        roofed = any(not transparent(W.at(x, yy, z)) for yy in range(y + 2, y + 40))
        if roofed and light.get((x, y, z), 0) < 1:
            dark.append((x, y, z))
    res["dark_floor_cells"] = len(dark)
    res["floor_cells_checked"] = sum(1 for h in seen.values() if len(h) == 1)
    for d in dark[:5]:
        P.append("light: the floor cell (%d, %d, %d) is under a roof at block light 0" % d)

    # -- blocks
    cond = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]
    if not cond:
        P.append("blocks: data/spawn_blocks.json lists nothing: the check cannot run")
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))["whitelist"]
    scoped = {b for w in policy if "sea_drift" in (w.get("scope") or "") for b in w["blocks"]}
    res["whitelisted_here"] = sorted(scoped)
    bad = sorted({bid(b) for b in W.w.values() if bid(b) in cond and bid(b) not in scoped})
    for b in bad:
        P.append("blocks: %s is a spawn condition (%s)" % (b, ", ".join(sorted({c.split(" [")[0] for c in cond[b]}))[:80]))
    sm = spec["strip_mine"]
    o = sm["ores"]
    allowed = set(o["near"]) | set(o["far"])
    allowed |= {o["deep_variant"] % a.split(":")[1] for a in list(allowed)}
    zr = spec["route"]["vertices"][0][1]
    reach_x = sm["drift_r"] + sm["branch_length"] + 2
    ores = {}
    for (x, y, z), b in W.w.items():
        i = bid(b)
        if not i.endswith("_ore"):
            continue
        if i not in allowed:
            P.append("blocks: %s at (%d, %d, %d) is not an ore the data lists" % (i, x, y, z))
        if not (abs(x - sm["junction_x"]) <= reach_x and sm["corridor_to_z"] - 2 * sm["chamber"]["r"] - 3 <= z
                < zr - spec["tube"]["r"]):
            P.append("blocks: an ore at (%d, %d, %d) is outside the strip mine's area" % (x, y, z))
        ores[(x, y, z)] = i
    res["ores"] = len(ores)

    # -- ores per branch (rows from the data's own numbers)
    rows = []
    zb = sm["first_branch_z"]
    while zb - sm["corridor_to_z"] >= 2:
        rows.append(zb)
        zb -= sm["branch_every"]
    exposed = {}
    for (x, y, z), i in ores.items():
        if any((x + a, y + b_, z + c) in opened for a, b_, c in N6):
            exposed[(x, y, z)] = i
    per = []
    for zb in rows:
        for sgn in (1, -1):
            n = sum(1 for (x, y, z) in exposed if abs(z - zb) <= 1 and (x - sm["junction_x"]) * sgn > sm["drift_r"])
            per.append(n)
            if n == 0:
                P.append("ores: the %s branch at z%d exposes no ore" % ("east" if sgn > 0 else "west", zb))
    res["exposed_per_branch"] = per
    half = (rows[0] + rows[-1]) / 2.0 if rows else 0
    rich = lambda i: "gold" in i or "lapis" in i      # noqa: E731
    near = sum(1 for (x, y, z), i in exposed.items() if rich(i) and z > half)
    far = sum(1 for (x, y, z), i in exposed.items() if rich(i) and z <= half)
    res["gold_lapis_exposed_near_far"] = [near, far]
    if not far > near:
        P.append("ores: the far half exposes %d gold and lapis, not more than the near half's %d" % (far, near))

    # -- isle
    c = isl["centre"]

    def built_ground(x, z):
        """The top of the solid column the pack raised over the seabed, read upward from the heightmap's ground."""
        y = g(x, z) + 1
        if (x, y, z) not in W.w:
            return None
        while W.at(x, y, z) not in (OPEN, WATER) and not transparent(W.at(x, y, z)):
            y += 1
        return y - 1

    top = built_ground(c["x"], c["z"])
    res["isle_centre_ground_y"] = top
    if top != c["ground_y"]:
        P.append("isle: the record's centre ground_y %s is not the replayed ground y%s" % (c["ground_y"], top))
    if g(c["x"], c["z"]) != c["heightmap_seabed_y"]:
        P.append("isle: heightmap_seabed_y %s is not the heightmap's y%d" % (c["heightmap_seabed_y"], g(c["x"], c["z"])))
    R = isl["radius"] + isl["skirt"]
    dry, shingle, crown = 0, 0, None
    for x in range(c["x"] - R, c["x"] + R + 1):
        for z in range(c["z"] - R, c["z"] + R + 1):
            t = built_ground(x, z)
            if t is None:
                continue
            if t > sea:
                dry += 1
                if not any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for b in (lh["hall"]["box"], lh["tower"]["box"])):
                    crown = t if crown is None else max(crown, t)      # the lighthouse's walls are not the ground
            if abs(t - sea) <= 2 and bid(W.at(x, t, z)) == isl["beach"]:
                shingle += 1
    res["isle_crown_y"] = crown
    res["isle_dry_columns"], res["isle_shingle_columns"] = dry, shingle
    if dry == 0:
        P.append("isle: no dry ground")
    if shingle == 0:
        P.append("isle: no %s at the tide line" % isl["beach"])
    surf = [(x, y, z) for (x, y, z) in opened if y == isl["pad_y"] and abs(x - c["x"]) <= R and abs(z - c["z"]) <= R]
    if not surf or not all(x0 < x < x1 and z0 < z < z1 for (x, y, z) in surf):
        P.append("isle: the road does not surface inside the keeper's hall %s" % (lh["hall"]["box"],))

    # -- the buildings: both gatehouses whole and named, the lighthouse's tower whole and its lamp lit and seen
    P += buildings(W, spec, res, light, crown)

    # -- habitats
    hdoc = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))
    sdoc = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    pool = "cobblers:%s" % spec["waters"]["pool"]
    habs = [b for b in hdoc["blocks"] if b.get("pool") == pool]
    res["habitat_blocks"] = len(habs)
    if not habs:
        P.append("habitats: data/habitat_blocks.json has no block of %s" % pool)
    for b in habs:
        p = b["position"]
        x, y, z = p["x"], p["y"], p["z"]
        if bid(W.at(x, y, z)) != bid(b.get("mimic", "")):
            P.append("habitats: %s stands on %s, not its mimic %s" % (b["id"], W.at(x, y, z), b.get("mimic")))
        for a, b_, cc in N6:
            q = W.at(x + a, y + b_, z + cc)
            if transparent(q) or q == WATER:
                P.append("habitats: %s is not sealed in rock (%s beside it)" % (b["id"], q))
                break
        rr = b["activated"]["spawn_range"]
        wet = surface = 0
        for xx in range(x - rr, x + rr + 1, 2):
            for zz in range(z - rr, z + rr + 1, 2):
                ys = [wy for wy in W.water_ys(xx, zz) if y - rr <= wy <= y + rr]
                wet += len(ys)
                if ys and max(ys) == sea and W.at(xx, sea + 1, zz) == OPEN:
                    surface += 1
        if wet == 0:
            P.append("habitats: %s has no water in its spawn box" % b["id"])
        if b["id"].endswith("_high") and surface == 0:
            P.append("habitats: %s does not reach the sea's surface" % b["id"])
    hab = next((h for h in sdoc["habitats"] if "cobblers:%s" % h["id"] == pool), None)
    if hab is None:
        P.append("habitats: no pool %s in data/spawns.json" % pool)
    ents = [e for e in sdoc["entries"] if e.get("scope") == spec["waters"]["pool"]]
    live = [e for e in ents if e.get("ambient") and e.get("weight", 0) > 0]
    res["pool_species"] = sorted(e["species"] for e in live)
    if not live:
        P.append("habitats: the pool spawns nothing")
    for e in ents:
        if e["species"] in NOT_WANTED:
            P.append("habitats: %s is one of the species the owner is tired of" % e["species"])
        others = [o_ for o_ in sdoc["entries"] if o_.get("scope") != spec["waters"]["pool"]
                  and o_.get("species") == e["species"] and o_.get("spawnable_position")]
        if not others:
            # No other table carries it (the encounter rebuild of 2026-10-02 dropped Binacle, Clauncher and Dragonair
            # from all of them). Judge it against Cobblemon's own spawn files instead: the position must be one
            # Cobblemon itself uses for this species. The RAW counts, not position_types.choose() - that is the
            # generator's rule, and an audit sharing it would agree with the generator by construction.
            import position_types
            jar = position_types.default_jar()
            if jar is None:
                P.append("habitats: %s is in no other table and COBBLERS_SERVER_ROOT is unset: cannot judge its "
                         "position" % e["species"])
            elif not position_types.upstream_positions(jar).get(e["species"], {}).get(e.get("spawnable_position")):
                P.append("habitats: %s's position %r is not one Cobblemon's own spawn files use for it"
                         % (e["species"], e.get("spawnable_position")))
            continue
        if e.get("spawnable_position") != others[0]["spawnable_position"]:
            P.append("habitats: %s's position %r is not the one data/spawns.json already gives it"
                     % (e["species"], e.get("spawnable_position")))

    # -- rewards
    rdoc = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
    for key in ("strips", "isle"):
        rid = spec["caches"][key]["reward"]
        r = next((r for r in rdoc["rewards"] if r["id"] == rid), None)
        if r is None:
            P.append("rewards: no record %s" % rid)
            continue
        at = tuple(r["container"]["at"])
        if bid(W.at(*at)) != "minecraft:barrel":
            P.append("rewards: %s's container at %s is %s, not a barrel" % (rid, at, W.at(*at)))
        lo, hi = r["trigger"]["min"], r["trigger"]["max"]
        if not any(all(lo[i] <= q[i] <= hi[i] for i in range(3)) for q in seen):
            P.append("rewards: no walkable place reached from the cut lies in %s's trigger box" % rid)

    # -- the rail line
    P += rail_line(W, spec, seen, res)

    # -- limits
    probs = []
    fn = Path(pack) / "data" / "cobblers" / "function" / "sea_drift"
    for n in names:
        lines = (fn / (n + ".mcfunction")).read_text(encoding="utf-8").splitlines()
        probs += FL.check_lines(lines, n)
    for pr in probs[:5]:
        P.append("limits: %s" % (pr,))
    res["problems"] = P
    return res


# ------------------------------------------------------------------ the rail line
#
# Read from the replayed blocks alone: which rails there are, the shape each was written with, and every lever and
# button. Nothing is taken from tools/sea_drift.py's own list of the line. The rules are vanilla's for 1.21.1, cited
# in data/sea_drift.json rail_line physics (the Minecraft Wiki), and the World methods they rest on:
#   a rail's two ends are its shape's two directions, the uphill end one block up; two rails join where an end of
#   one is an end of the other at the same height
#   a lever or button weakly powers its six neighbours and strongly powers the block it hangs on; a solid block that
#   is strongly powered powers the six cells round it (World.isReceivingRedstonePower takes only STRONG power from a
#   solid neighbour); a powered rail passes power to the powered rails it joins, up to 8 away; an activator rail
#   likewise to activator rails; a detector rail powers its neighbours and the block under it while a cart is on it

def sign_text(b):
    """The text on a sign block's front, joined, or None if it is not a sign."""
    if not bid(b).endswith("_sign") or "{" not in b:
        return None
    return " ".join(re.findall(r"'\"((?:[^\"\\\\]|\\\\.)*)\"'", b))


def buildings(W, spec, res, light, crown):
    """Foothill Gate and the keeper's hall: every wall cell solid but the data's doors and the road's own opening, a roof,
    a sign naming the place, and the line's stop inside with its buffer in the wall. Driftmouth Light's tower: its walls
    whole to the lantern room, the room glazed, a lamp in it of an allowed light-emitting block, lit, with clear glass
    between it and the sea on all four sides and standing over the isle's crown."""
    P = []
    r, H = spec["tube"]["r"], spec["tube"]["height"]
    rails = {p: b for p, b in W.w.items() if bid(b) in RAIL_IDS}
    by_col = {}
    for (x, y, z) in rails:
        by_col[(x, z)] = y
    isl = spec["island"]
    lh = isl["lighthouse"]
    gh = spec["gatehouse"]
    (vx, vz), (wx, wz) = spec["route"]["vertices"][:2]
    axis_z = vz == wz

    def road_open(x, y, z):
        """A wall cell the road passes through: over a rail of the line, within the tube's half-width and height."""
        for o in range(-r, r + 1):
            k = (x, z - o) if axis_z else (x - o, z)
            if k in by_col and (k[1] == vz if axis_z else k[0] == vx) and by_col[k] <= y < by_col[k] + H:
                return True
        return False

    tdoor = tuple(lh["tower"]["door"])
    halls = [("Foothill Gate", gh["display_name"], gh["box"], gh["floor_y"], gh["wall_height"],
              {(x, z) for x in range(gh["doors_x"][0], gh["doors_x"][1] + 1) for z in (gh["box"][1], gh["box"][3])},
              (vx, gh["floor_y"] + 1, vz)),
             ("the keeper's hall", lh["display_name"], lh["hall"]["box"], isl["pad_y"], lh["hall"]["wall_height"],
              {(x, lh["hall"]["box"][3]) for x in range(lh["hall"]["door_x"][0], lh["hall"]["door_x"][1] + 1)} | {tdoor},
              (wx, isl["pad_y"] + 1, wz))]
    found = []
    for what, name, (x0, z0, x1, z1), fy, wh, doors, stop in halls:
        holes = []
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if not (x in (x0, x1) or z in (z0, z1)):
                    continue
                for y in range(fy + 1, fy + wh + 1):
                    b = W.at(x, y, z)
                    if not transparent(b) and b not in (OPEN, WATER):
                        continue
                    if ((x, z) in doors and y <= fy + 3) or road_open(x, y, z):
                        continue
                    holes.append((x, y, z))
        roof = [(x, fy + wh + 1, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
                if transparent(W.at(x, fy + wh + 1, z)) or W.at(x, fy + wh + 1, z) in (OPEN, WATER)]
        signs = [sign_text(b) for (x, y, z), b in W.w.items() if x0 - 1 <= x <= x1 + 1 and z0 - 1 <= z <= z1 + 1
                 and fy < y <= fy + wh + 1 and sign_text(b) is not None]
        named = [t for t in signs if name.lower() in t.lower()]
        found.append({"building": what, "wall_holes": len(holes), "roof_holes": len(roof), "signs": len(signs),
                      "named": len(named)})
        for h in holes[:3]:
            P.append("gatehouse: %s's wall is open at %s (no door and not the road)" % (what, h))
        if roof:
            P.append("gatehouse: %s's roof is open at %d cells, the first %s" % (what, len(roof), roof[0]))
        if not named:
            P.append("gatehouse: no sign on %s names %s" % (what, name))
        if not (x0 < stop[0] < x1 and z0 < stop[2] < z1) or bid(W.at(*stop)) != "minecraft:powered_rail":
            P.append("gatehouse: the line's stop %s is not a rail inside %s" % (stop, what))
        beyond = [(x, stop[1], z) for x, z in ((stop[0] + 1, stop[2]), (stop[0] - 1, stop[2]), (stop[0], stop[2] + 1),
                                                (stop[0], stop[2] - 1)) if x in (x0, x1) or z in (z0, z1)]
        if not beyond or not all(solid_floor(W.at(*q)) for q in beyond):
            P.append("gatehouse: the stop %s in %s is not against its wall (the buffer)" % (stop, what))
    res["buildings"] = found
    # -- the tower
    tb = lh["tower"]
    tx0, tz0, tx1, tz1 = tb["box"]
    fl, pad = tb["lantern_room_feet"], isl["pad_y"]
    holes = [(x, y, z) for x in range(tx0, tx1 + 1) for z in range(tz0, tz1 + 1) if x in (tx0, tx1) or z in (tz0, tz1)
             for y in range(pad + 1, fl) if not ((x, z) == tdoor and y <= pad + 2)
             and (transparent(W.at(x, y, z)) or W.at(x, y, z) in (OPEN, WATER))]
    for h in holes[:3]:
        P.append("lighthouse: the tower's wall is open at %s" % (h,))
    glazing = [(x, y, z) for x in range(tx0, tx1 + 1) for z in range(tz0, tz1 + 1)
               if (x in (tx0, tx1)) != (z in (tz0, tz1)) for y in range(fl, fl + 3)]
    unglazed = [p for p in glazing if bid(W.at(*p)) != bid(tb["glazing"]) or not transparent(W.at(*p))]
    if unglazed:
        P.append("lighthouse: the lantern room is not glazed at %d cells, the first %s" % (len(unglazed), unglazed[0]))
    lamps = [(p, b) for p, b in W.w.items() if tx0 < p[0] < tx1 and tz0 < p[2] < tz1 and fl <= p[1] < fl + 3
             and bid(b) in LIGHTS]
    res["lamp"] = [list(p) for p, _b in lamps]
    if not lamps:
        P.append("lighthouse: no light-emitting block in the lantern room (%s are the ones this audit knows)" % sorted(LIGHTS))
    for p, b in lamps:
        if bid(b) != bid(tb["lamp"]):
            P.append("lighthouse: the lamp at %s is %s, not the data's %s" % (p, bid(b), tb["lamp"]))
        if light.get(p, 0) < 15:
            P.append("lighthouse: the lamp at %s is not lit" % (p,))
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x, z = p[0] + dx, p[2] + dz
            while tx0 <= x <= tx1 and tz0 <= z <= tz1:
                if not transparent(W.at(x, p[1], z)):
                    P.append("lighthouse: the lamp at %s is hidden from the %s by %s at (%d, %d, %d)"
                             % (p, {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}[(dx, dz)],
                                W.at(x, p[1], z), x, p[1], z))
                    break
                x, z = x + dx, z + dz
        if crown is not None and p[1] < crown + 10:
            P.append("lighthouse: the lamp at y%d stands less than 10 over the isle's crown y%d" % (p[1], crown))
    res["tower_wall_holes"] = len(holes)
    return P


RAIL_IDS = ("minecraft:rail", "minecraft:powered_rail", "minecraft:detector_rail", "minecraft:activator_rail")
DIR = {"east": (1, 0), "west": (-1, 0), "south": (0, 1), "north": (0, -1)}
STRAIGHT = {"east_west": ("east", "west"), "north_south": ("north", "south")}


def props(b):
    if "[" not in b:
        return {}
    return dict(kv.split("=", 1) for kv in b[b.index("[") + 1:b.rindex("]")].split(",") if "=" in kv)


def rail_ends(x, y, z, shape):
    """The two ends of a rail at (x, y, z) as (2x + dx, height, 2z + dz), or None for a shape that is not a rail's."""
    if shape in STRAIGHT:
        ds = [(DIR[a], 0) for a in STRAIGHT[shape]]
    elif shape.startswith("ascending_") and shape[10:] in DIR:
        d = DIR[shape[10:]]
        ds = [(d, 1), ((-d[0], -d[1]), 0)]
    elif shape.count("_") == 1 and all(p in DIR for p in shape.split("_")):
        a, b = shape.split("_")
        if (DIR[a][0] == 0) == (DIR[b][0] == 0):
            return None
        ds = [(DIR[a], 0), (DIR[b], 0)]
    else:
        return None
    return [(2 * x + d[0], y + h, 2 * z + d[1]) for d, h in ds]


def attached(p, b):
    """The block a lever or button hangs on."""
    pr = props(b)
    x, y, z = p
    if pr.get("face") == "ceiling":
        return (x, y + 1, z)
    if pr.get("face") == "floor":
        return (x, y - 1, z)
    d = DIR.get(pr.get("facing"), (0, 0))
    return (x - d[0], y, z - d[1])


def rail_line(W, spec, seen, res):
    P = []
    rl = spec["rail_line"]
    ph = rl["physics"]
    rails = {p: b for p, b in W.w.items() if bid(b) in RAIL_IDS}
    res["rails"] = len(rails)
    if not rails:
        return ["rails: the pack writes no rail"]
    # -- shapes, support and the ends graph
    ends, key = {}, {}
    for p, b in rails.items():
        shape = props(b).get("shape", "")
        e = rail_ends(*p, shape)
        curve = e is not None and shape not in STRAIGHT and not shape.startswith("ascending_")
        if e is None:
            P.append("rails: %s at %s has no rail shape %r" % (bid(b), p, shape))
            continue
        if curve:
            P.append("rails: %s at %s turns (%s): the line is straight, end to end" % (bid(b), p, shape))
        if not solid_floor(W.at(p[0], p[1] - 1, p[2])):
            P.append("rails: the rail at %s stands on %s" % (p, W.at(p[0], p[1] - 1, p[2])))
        ends[p] = e
        for k in e:
            key.setdefault(k, []).append(p)
    nbr = {p: [] for p in ends}
    for k, ps in key.items():
        if len(ps) > 2:
            P.append("rails: %d rails meet at one end %s (a junction)" % (len(ps), ps))
        for a in ps:
            nbr[a] += [q for q in ps if q != a]
    tips = sorted(p for p in nbr if len(nbr[p]) < 2)
    res["rail_line_ends"] = [list(t) for t in tips]
    if len(tips) != 2:
        for t in tips[:6]:
            P.append("rails: the line ends or breaks at %s (%s)" % (t, rails[t]))
        if len(tips) != 2:
            P.append("rails: %d loose ends, not the line's two stops" % len(tips))
    # -- the two stops are where the data says: the route's two ends, one on Foothill Gate's floor and one on the keeper's
    #    hall's
    (vx, vz), (wx, wz) = spec["route"]["vertices"][:2]
    isl = spec["island"]
    gh = spec["gatehouse"]
    mouth = [t for t in tips if (t[0], t[2]) == (vx, vz) and t[1] == gh["floor_y"] + 1]
    house = [t for t in tips if (t[0], t[2]) == (wx, wz) and t[1] == isl["pad_y"] + 1]
    if len(mouth) != 1 or len(house) != 1:
        P.append("rails: the line's ends %s are not the route's two ends, on Foothill Gate's floor (y%d) and the keeper's "
                 "hall's (y%d)" % (tips, gh["floor_y"] + 1, isl["pad_y"] + 1))
        return P
    # -- one line: from the mouth's stop to the headhouse's, every rail on it once
    path, prev, cur = [mouth[0]], None, mouth[0]
    while True:
        nx = [q for q in nbr[cur] if q != prev]
        if not nx:
            break
        prev, cur = cur, nx[0]
        if cur in path:
            P.append("rails: the line loops at %s" % (cur,))
            break
        path.append(cur)
    res["rail_line_length"] = len(path)
    if path[-1] != house[0]:
        P.append("rails: the line from the mouth's stop %s ends at %s, not at the headhouse's stop %s"
                 % (mouth[0], path[-1], house[0]))
    if len(path) != len(rails):
        P.append("rails: %d rails are written and %d are on the line from stop to stop" % (len(rails), len(path)))
    # -- straight: every rail of the line on the axis through its two ends, one column further along at each step
    axis = 2 if vz == wz else 0                         # the coordinate that stays the same
    off = [p for p in path if p[axis] != (vz if axis == 2 else vx)]
    jumps = [(a, b) for a, b in zip(path, path[1:]) if abs(b[2 - axis] - a[2 - axis]) != 1]
    res["rail_line_off_axis"] = len(off)
    if off:
        P.append("straight: %d rails of the line leave its axis (%s %d), the first at %s"
                 % (len(off), "z" if axis == 2 else "x", vz if axis == 2 else vx, off[0]))
    if jumps:
        P.append("straight: the line does not advance one column a rail between %s and %s" % jumps[0])
    # -- power: every lever and button the pack writes
    sources, buttons, levers = set(), {}, []
    for p, b in W.w.items():
        i = bid(b)
        if i == "minecraft:lever" or i.endswith("_button"):
            att = attached(p, b)
            if not solid_floor(W.at(*att)):
                P.append("power: the %s at %s hangs on %s" % (i, p, W.at(*att)))
            reach = {(p[0] + a, p[1] + b_, p[2] + c) for a, b_, c in N6}
            if solid_floor(W.at(*att)):
                reach |= {(att[0] + a, att[1] + b_, att[2] + c) for a, b_, c in N6}
            if i.endswith("_button") and props(b).get("powered") != "true":
                buttons[p] = reach
            elif props(b).get("powered") == "true":
                sources |= reach
            if i == "minecraft:lever":
                levers.append(p)
                if any(transparent(W.at(p[0] + a, p[1] + b_, p[2] + c)) or W.at(p[0] + a, p[1] + b_, p[2] + c) == WATER
                       for a, b_, c in N6):
                    P.append("power: the lever at %s is not sealed in rock (a player could see it and switch it off)" % (p,))
        elif i in ("minecraft:redstone_block", "minecraft:redstone_torch"):
            sources |= {(p[0] + a, p[1] + b_, p[2] + c) for a, b_, c in N6}
    res["rail_levers"] = len(levers)

    def chain(kind, seeds):
        """Rails of one kind reached from seeds through joined rails of that kind, up to 8 away."""
        got, front = set(seeds), list(seeds)
        for _ in range(int(ph["propagation"])):
            front = [q for p in front for q in nbr.get(p, []) if bid(rails[q]) == kind and q not in got]
            got |= set(front)
        return got

    pr_ = [p for p in path if bid(rails[p]) == "minecraft:powered_rail"]
    direct = {p for p in pr_ if p in sources}
    live = chain("minecraft:powered_rail", direct)
    for p in pr_:
        on = props(rails[p]).get("powered") == "true"
        if on and p not in direct:
            P.append("power: the powered rail at %s is written powered and has no power source beside it or under it" % (p,))
        if not on and p in live:
            P.append("power: the powered rail at %s is written unpowered and power reaches it: it would switch on" % (p,))
    detectors = [p for p in path if bid(rails[p]) == "minecraft:detector_rail"]
    cart = {(p[0] + a, p[1] + b_, p[2] + c) for p in detectors for a, b_, c in N6}
    cart |= {(p[0] + a, p[1] - 1 + b_, p[2] + c) for p in detectors for a, b_, c in N6}
    acts = [p for p in path if bid(rails[p]) == "minecraft:activator_rail"]
    for p in chain("minecraft:activator_rail", [q for q in acts if q in sources or q in cart]):
        P.append("power: the activator rail at %s can be powered (by a source or a passing cart): it would throw the "
                 "rider out" % (p,))
    # -- the stops: unpowered powered rail, a solid buffer beyond its free end, a button, a place to get on
    stops = []
    for t in (mouth[0], house[0]):
        b = rails[t]
        st = {"rail": list(t)}
        if bid(b) != "minecraft:powered_rail" or props(b).get("powered") != "false" or t in live:
            P.append("stops: the stop at %s is %s: an unpowered powered rail brakes a cart to a stop" % (t, b))
        free = [k for k in ends[t] if len(key[k]) == 1]
        if len(free) == 1:
            k = free[0]
            beyond = ((k[0] + (k[0] - 2 * t[0])) // 2, t[1], (k[2] + (k[2] - 2 * t[2])) // 2)
            st["buffer"] = list(beyond)
            if not solid_floor(W.at(*beyond)):
                P.append("stops: beyond the stop at %s is %s, not a solid block to stop at and launch from"
                         % (t, W.at(*beyond)))
        if not any(t in reach for reach in buttons.values()):
            P.append("stops: no button powers the stop at %s" % (t,))
        if t in cart:
            P.append("stops: a detector rail beside the stop at %s would power it under an arriving cart" % (t,))
        if not (t in seen or any((t[0] + a, t[1] + dy, t[2] + c) in seen for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1))
                                 for dy in (-1, 0, 1))):
            P.append("stops: no walkable place reached from the cut lies at the stop %s" % (t,))
        stops.append(st)
    res["rail_stops"] = stops
    # -- boost: every climb powered; on the flat, no more unpowered rails between powered ones than the cited full-speed
    #    run allows with the data's margin
    limit = min(ph["occupied_subsequent_max"]) // int(ph["margin"])
    res["boost_limit"] = limit
    run, worst = 0, (0, None)
    for p in path:
        b = rails[p]
        boosted = bid(b) == "minecraft:powered_rail" and p in direct
        if props(b).get("shape", "").startswith("ascending_") and not boosted:
            P.append("boost: the climb at %s is %s, not a powered rail with power" % (p, b))
        run = 0 if boosted else run + 1
        if run > worst[0]:
            worst = (run, p)
    res["max_unboosted_run"] = worst[0]
    if worst[0] > limit:
        P.append("boost: %d rails without a powered one, ending at %s, over the %d that %s rails at full speed / margin "
                 "%s allow" % (worst[0], worst[1], limit, min(ph["occupied_subsequent_max"]), ph["margin"]))
    res["rail_kinds"] = {k: sum(1 for p in path if bid(rails[p]) == k) for k in RAIL_IDS}
    res["rail_boosted"] = len(direct)
    return P


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=None)
    p.add_argument("--pack", default=str(PACK))
    a = p.parse_args(argv)
    try:
        res = audit(a.source_root, Path(a.pack))
    except AuditError as e:
        print("AUDIT FAILED: %s" % e)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, indent=1) + "\n")
    brief = {k: v for k, v in res.items() if k not in ("problems", "exposed_per_branch")}
    print(json.dumps(brief))
    for pr in res["problems"][:20]:
        print("PROBLEM %s" % pr)
    print("%d problems -> %s" % (len(res["problems"]), OUT.relative_to(ROOT)))
    return 1 if res["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
