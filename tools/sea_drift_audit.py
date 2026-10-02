#!/usr/bin/env python
"""Offline audit of the Seaward Drift, its strip mine and Driftmouth Isle (tools/sea_drift.py, data/sea_drift.json).

Independent of tools/sea_drift.py: nothing is imported from it and nothing is taken from its plan. The pack it wrote
(build/datapacks/cobblers_sea_drift, every function in index order) is REPLAYED over a world made only from the canonical
heightmap (tools/ground.py, rounded: solid to the ground, painted water over it to the sea level or a lake's level, air
above), and the result is checked against rules the data and the other files state:

  water     every cell the pack opens (left non-solid where the heightmap world had rock or water) keeps at least
            cover + 1 Chebyshev from any water left in the replayed world, cover being the data's three parts summed
            here (shell_r + export_tolerance + natural_seabed); no write is a fluid; the measured minimum is reported
  sealed    every opened cell under the heightmap world's surface touches only opened cells, blocks the pack wrote, or
            open air: never an unwritten natural block (a cave, the export's gravel) and never water
  route     every route vertex of the data has an opened cell in its column (the drift follows the data's legs)
  walk      a player can walk from the cut's head on the plateau to outside the headhouse's door, and to both barrels,
            on full blocks and stairs, never climbing a whole block without a stair (a rail is not a stair)
  light     block light flooded from every lantern the pack writes reaches 1 or more at every floor cell under a roof:
            no cell a hostile could spawn on is at light 0 (there are none in this pack, docs/STATE.md; the rule holds
            anyway)
  blocks    no written block is named by a spawn condition (data/spawn_blocks.json); every ore is one the data lists
            (or its deepslate variant) and stands in the strip mine's own area (north of the drift, within the
            branches' reach of the junction)
  ores      every branch the data's numbers give (first_branch_z, branch_every, corridor_to_z) exposes an ore, and the
            far half of the branches exposes more gold and lapis than the near half
  isle      Driftmouth Isle has dry ground and a shingle tide line; its record's ground_y is the replayed ground at its
            centre and its heightmap_seabed_y the heightmap's; the stairwell surfaces inside the headhouse box
  habitats  every data/habitat_blocks.json record of the isle's sits on its mimic block in the replayed world, rock on
            all six sides, water within its spawn box (and the sea's surface for the upper ones); its pool exists in
            data/spawns.json, has none of the three species the owner named (Magikarp, Goldeen, Barraskewda), and
            every species in it is placed by an existing spawnable position
  rewards   both caches' containers are barrels in the replayed world and their trigger boxes hold a walkable place
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
SET = re.compile(r"^setblock %s %s %s (\S+)(?: replace)?$" % ((NUM,) * 3))
NATURAL, WATER, OPEN = "natural", "water", "open-air"


class AuditError(Exception):
    pass


def bid(b):
    return b.split("[")[0].split("{")[0]


def passable(b):
    """A body can stand in it: air, a rail. Not a lantern (it has a hitbox), a fence, a barrel or a stair."""
    i = bid(b)
    return i in ("minecraft:air", "minecraft:cave_air", OPEN) or i.endswith("rail")


def transparent(b):
    """Block light passes: air, rails, lanterns, fences, stairs (half open), not full blocks or fluids."""
    i = bid(b)
    return passable(b) or i.endswith("lantern") or i.endswith("_fence") or i.endswith("_stairs")


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

    # -- route (the first vertex is the cut's head, on the surface: the walk starts there)
    for vx, vz in spec["route"]["vertices"][1:]:
        if not any((vx, y, vz) in opened for y in range(-64, 320)):
            P.append("route: no opened cell in the column of vertex (%d, %d)" % (vx, vz))

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
    x0, z0, x1, z1 = isl["headhouse"]["box"]
    door = (x0 - 1, isl["pad_y"] + 1, isl["stairwell"]["spine_z"])
    if door not in seen:
        P.append("walk: outside the headhouse door %s is not reached from the cut's head %s" % (door, start))

    # -- light (flooded from every lantern the pack writes)
    lanterns = [p for p, b in W.w.items() if bid(b) == "minecraft:lantern"]
    if not lanterns:
        P.append("light: the pack writes no lantern")
    light = {p: 15 for p in lanterns}
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
    bad = sorted({bid(b) for b in W.w.values() if bid(b) in cond})
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
                if not (x0 <= x <= x1 and z0 <= z <= z1):           # the house's walls are not the ground
                    crown = t if crown is None else max(crown, t)
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
        P.append("isle: the stairwell does not surface inside the headhouse box")

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
