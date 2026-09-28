#!/usr/bin/env python
"""Offline audit of the southern Rift's mega site (build/datapacks/cobblers_gulch_mine against data/gulch_mine.json).

Independent of tools/gulch_mine.py's model: it rasterises the data itself, by the `geometry` the data file states
(the halls, tubes, road, rockfall band and zone polygon), takes the ground from the canonical heightmap
(tools/ground.py) and every expectation about other things from THEIR data (Victory Road's corridor in
data/routes.json, its caves in data/vr_caves.json, the sculpt's lip ring and gap in derived/rift_sculpt/plan.json,
data/towns.json, data/spawn_blocks.json), never from the generated output. The pack is then replayed and checked.

The plan (data only):
  cover       at least cover_min of rock over the shell of every hall column, on the heightmap
  surface     no carved cell within a block of its column's top outside the adit's portal
  victory     no column the build may write within Victory Road's corridor (its polyline, half its width, and a
              margin) or near its caves; no settlement footprint within the margin
  gap         the rockfall's band covers every ring point of the sculpt's gulch_mouth gap, and the rim beyond each end
              of the gap is a crag (the sculpt's raised lip); the wall's crest at each end stands no more than its jag
              below the crag there (measured on the heightmap, SOUTHERN_RIFT_MEGA.md 13: to the crag tops)
The output (replayed in index order):
  inside      every write in the grid and in a column the plan may write
  no stray    no air under the ground except in the halls, tubes and the earthworks' own clearing
  sealed      every cell next to the carved space, under its column's top and not carved, ends written solid
  blocks      no block named by a spawn condition, no fluid, no meteorid ore (they drop evolution stones)
  zone        the zone boxes (from the pack's advancement) run y-64 to 575; every write is inside them except the
              rockfall, the road and the lamp posts outside the gate; the knock box and the turn-back point are
              outside, the arrival and the exit box inside; every column of the gulch's basin (ground at or under
              basin_y) that a walker reaches from the square without crossing the rockfall or the zone's closing line
              is inside
  gate        the rockfall stands at least 3 over the lip's ground at every gap ring point, and reaches the crest line
              between the measured crag tops (less twice the jag) there, the plug its flat top; the knock teleports only a
              player holding the flag, the zone turns back only a player lacking it, the ward's box holds the plug with
              ward_margin to spare
  walk        on the replayed world: from the gate's arrival a walker reaches the square, both halls' floors, both
              faces' fronts, the Megas' anchors and the Cutters' counters; from the turn-back point, inside the grid, a
              walker does not reach the arrival (the rockfall closes the canyon)
  cove        each cove building (and a house's steps) inside the zone, off the square, the yard, the road, the
              cutting, the portal and the gate's wall; its ground within the data's limits (the heightmap); no two
              closer than the alley; the cutting a floor at its y with air over it; the walk above reaches every
              house's doorway from the gate's arrival
Not checked here: the farm dens' drop roll (no farm is in the data yet; SOUTHERN_RIFT_MEGA.md 13 holds them)
  faces       scenery (SOUTHERN_RIFT_MEGA.md 13): each face box written whole with exactly its crystals; no function
              outside the build's passes writes into a face box (the restore is retired, and its block tag gone); the
              tick wards each face every tick with the data's margin
  megas       one macro line spawns every Mega (EXP-046: no plain spawnpokemonat line anywhere); each den's spawn calls
              it with the species, the Mega aspect and the level at its anchor and claims the Mega in the same
              function (tags, PersistenceRequired); a mine anchor is a walkable floor cell of its hall; the leash walks
              it back to the same anchor at the data's radius; the keeper waits gm.resp from the respawn clock, with
              nobody within spawn_clear, and every line in the pack that writes a clock is one the design allows (load
              only when unset, the keeper's first sight of a gone Mega, a spawn)
  cutters     three villagers, NoAI and invulnerable, standing on the workshop's floor; every offer the data's raw
              stones and a diamond for one stone, unlimited, no experience, no price drift; the 60 stones each exactly
              once, none of the 32 left out
  limits      tools/function_limits.py finds nothing the server would refuse

Fails closed: no pack, an empty index, no sculpt plan, no zone advancement or no face is a failure, not a pass.

  python tools/gulch_mine_audit.py [--source-root DIR]      writes derived/gulch_mine/audit.json; exit 1 on any problem
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as GR            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "gulch_mine.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_gulch_mine"
FN = PACK / "data" / "cobblers" / "function" / "gulch_mine"
ADV = PACK / "data" / "cobblers" / "advancement" / "gulch_mine"
SCULPT = ROOT / "derived" / "rift_sculpt" / "plan.json"
OUT = ROOT / "derived" / "gulch_mine" / "audit.json"
SHELL = 2
MARGIN = 24                       # blocks kept from Victory Road's corridor edge and caves, and from any settlement
BASIN_Y = 120                     # the sculpt's basin: the Rift is the ground at or under y120 (docs/STATE.md, the Rift)
FLUIDS = ("minecraft:water", "minecraft:lava", "minecraft:flowing_water", "minecraft:flowing_lava")
AIRS = ("minecraft:air", "minecraft:cave_air", "minecraft:void_air")
PASSABLE = ("lantern", "door", "chain", "rail", "carpet")
CMD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")


def half_up(v):
    return int(math.floor(v + 0.5))


def h32(*vals):
    """The hash data/gulch_mine.json geometry names (the one tools/rift_mines.py states), written out again here."""
    a = 0x811C9DC5
    for v in vals:
        a = ((a ^ (int(v) & 0xFFFFFFFF)) * 0x01000193) & 0xFFFFFFFF
        a ^= a >> 15
        a = (a * 0x2C1B3C6D) & 0xFFFFFFFF
        a ^= a >> 12
    return a


# ------------------------------------------------------------------ the data, rasterised from its own words

def hall(h, seed):
    key = sum(ord(c) for c in h["id"])
    ph = [h32(seed, len(h["id"]), key, k) / 4294967296.0 * 2 * math.pi for k in range(3)]
    cx, cz = h["centre"]
    out = {}
    reach = int(math.ceil(h["radius"] * (1 + h["ragged"]) + 1))
    for x in range(cx - reach, cx + reach + 1):
        for z in range(cz - reach, cz + reach + 1):
            d = math.sqrt((x - cx) ** 2 + (z - cz) ** 2)
            th = math.atan2(z - cz, x - cx)
            n = 0.5 * math.sin(3 * th + ph[0]) + 0.3 * math.sin(5 * th + ph[1]) + 0.2 * math.sin(7 * th + ph[2])
            rt = h["radius"] * (1 + h["ragged"] * n) + 0.5
            if d <= rt:
                q = d / rt
                feet = h["feet"] + int(math.floor(h["bowl"] * q * q + 0.5))
                top = max(feet + 3, h["feet"] + int(math.floor(h["height"] * math.sqrt(max(0.0, 1 - q * q)) + 0.5)))
                out[(x, z)] = (feet, top)
    return out


def tube(path, r, height):
    cells = set()
    for a, b in zip(path, path[1:]):
        length = math.sqrt((b[0] - a[0]) ** 2 + (b[2] - a[2]) ** 2)
        n = int(math.ceil(4 * length)) + 1 if length > 0 else 1
        for s in range(n):
            f = 0.0 if n == 1 else s / (n - 1)
            px, py, pz = (half_up(a[q] + (b[q] - a[q]) * f) for q in range(3))
            for x in range(px - r, px + r + 1):
                for z in range(pz - r, pz + r + 1):
                    cells.update((x, y, z) for y in range(py, py + height))
    return cells


def road(rd):
    best = {}
    for a, b in zip(rd["path"], rd["path"][1:]):
        length = math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
        n = int(math.ceil(4 * length)) + 1 if length > 0 else 1
        for s in range(n):
            f = 0.0 if n == 1 else s / (n - 1)
            px, pz, py = (a[q] + (b[q] - a[q]) * f for q in range(3))
            for dx in range(-rd["half"], rd["half"] + 1):
                for dz in range(-rd["half"], rd["half"] + 1):
                    c = (half_up(px) + dx, half_up(pz) + dz)
                    dd = (c[0] - px) ** 2 + (c[1] - pz) ** 2
                    if c not in best or dd < best[c][0]:
                        best[c] = (dd, half_up(py))
    return {c: v[1] for c, v in best.items()}


def band(b):
    """{(x, z): j}: data geometry.band, each ring point moved d = -spread_out .. spread_in along its normal, the columns
    within 1 of each; a column keeps the claim with the least talus drop max(0, -d - core), the first among equals."""
    w = b["wall"]
    out, drop = {}, {}
    for j, x, z, nx, nz in b["points"]:
        for d in range(-w["spread_out"], w["spread_in"] + 1):
            dr = max(0, -d - w["core"])
            cx, cz = half_up(x + nx * d), half_up(z + nz * d)
            for a in (-1, 0, 1):
                for c in (-1, 0, 1):
                    k = (cx + a, cz + c)
                    if k not in out or dr < drop[k]:
                        out[k], drop[k] = j, dr
    return out


def inside_poly(poly, px, pz):
    c = False
    for i in range(len(poly)):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % len(poly)]
        if (z0 > pz) != (z1 > pz) and px < x0 + (pz - z0) * (x1 - x0) / (z1 - z0):
            c = not c
    return c


def crosses(p, q, a, b):
    """True when the step p -> q (column centres) crosses the segment a-b."""
    def orient(o, s, t):
        return (s[0] - o[0]) * (t[1] - o[1]) - (s[1] - o[1]) * (t[0] - o[0])
    d1, d2 = orient(a, b, p), orient(a, b, q)
    d3, d4 = orient(p, q, a), orient(p, q, b)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


# ------------------------------------------------------------------ the pack

def replay(names):
    final, files = {}, []
    for n in names:
        f = FN / (n + ".mcfunction")
        files.append(f)
        for ln in f.read_text(encoding="utf-8").splitlines():
            m = CMD.match(ln.strip())
            if not m:
                continue
            a = [int(v) for v in m.groups()[1:4]]
            b = [int(v) for v in m.groups()[4:7]] if m.group(5) else a
            for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                    for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
                        final[(x, y, z)] = m.group(8)
    return final, files


def adv(name):
    p = ADV / name
    if not p.is_file():
        raise SystemExit("no advancement %s: run `python tools/gulch_mine.py build` first" % p.relative_to(ROOT))
    return json.loads(p.read_text(encoding="utf-8"))


def boxes_of(doc):
    conds = doc["criteria"]["here"]["conditions"]["player"]
    terms = conds[0]["terms"] if conds and conds[0].get("condition") == "minecraft:any_of" else conds
    out = []
    for t in terms:
        p = t["predicate"]["location"]["position"]
        out.append(((p["x"]["min"], p["y"]["min"], p["z"]["min"]), (p["x"]["max"] - 1, p["y"]["max"] - 1, p["z"]["max"] - 1)))
    return out


def fn_text(name):
    p = FN / (name + ".mcfunction")
    return p.read_text(encoding="utf-8") if p.is_file() else ""


# ------------------------------------------------------------------ the audit

def audit(source_root=None):
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    ground = GR.Ground(source_root)
    probs, notes = [], {}
    seed = spec["seed"]
    (X0, X1), (Z0, Z1), (Y0, Y1) = spec["grid"]["x"], spec["grid"]["z"], spec["grid"]["y"]

    # ---- the data's own geometry
    halls = {h["id"]: hall(h, seed) for h in spec["mine"]["halls"]}
    env = set()
    for cols in halls.values():
        for (x, z), (feet, top) in cols.items():
            env.update((x, y, z) for y in range(feet, top + 1))
    for d in spec["mine"]["drifts"]:
        env |= tube(d["path"], d["r"], d["height"])
    faceset = set()
    for f in spec["mine"]["faces"]:
        x0, y0, z0, x1, y1, z1 = f["box"]
        faceset |= {(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)}
    if not faceset:
        probs.append("faces: the data has no face: nothing to audit")
    carved = env - faceset
    t = spec["town"]
    surface = {}
    sq = t["square"]
    for x in range(sq["rect"][0], sq["rect"][2] + 1):
        for z in range(sq["rect"][1], sq["rect"][3] + 1):
            surface[(x, z)] = (sq["surface_y"], sq["clear_above"])
    yd = t["yard"]
    for x in range(yd["rect"][0], yd["rect"][2] + 1):
        for z in range(yd["rect"][1], yd["rect"][3] + 1):
            surface.setdefault((x, z), (yd["surface_y"], yd["clear_above"]))
    rd = road(spec["gate"]["road"])
    for c, y in rd.items():
        surface.setdefault(c, (y, spec["gate"]["road"]["clear_above"]))
    cove = spec.get("cove") or {"paths": [], "buildings": [], "lamp_posts": []}
    path_cols = set()
    for p in cove["paths"]:
        for c, y in road(p).items():
            surface.setdefault(c, (y, p["clear_above"]))
            path_cols.add(c)
    bnd = band(spec["gate"]["band"])

    def top(x, z):
        return surface[(x, z)][0] if (x, z) in surface else ground(x, z)
    notes["carved cells (the audit's own)"] = len(carved)

    # ---- cover and surface
    cmin = spec["cover_min"]
    for hid, cols in halls.items():
        thin = [(x, z) for (x, z), (_f, tp) in cols.items() if top(x, z) - tp - SHELL < cmin]
        if thin:
            probs.append("cover: %s has %d columns with under %d of rock over its shell, e.g. %s" % (hid, len(thin), cmin, thin[:3]))
        notes["least rock over %s (shell included)" % hid] = min(top(x, z) - tp for (x, z), (_f, tp) in cols.items())
    pr = spec["mine"]["portal"]["open_rect"]
    breach = [c for c in carved if c[1] >= top(c[0], c[2]) - 1 and not (pr[0] <= c[0] <= pr[2] and pr[1] <= c[2] <= pr[3])]
    if breach:
        probs.append("surface: %d carved cells within a block of the top outside the portal, e.g. %s" % (len(breach), sorted(breach)[:3]))

    # ---- the columns the build may write
    cols = {(x + dx, z + dz) for x, _y, z in env | faceset for dx in range(-SHELL, SHELL + 1) for dz in range(-SHELL, SHELL + 1)}
    cols |= set(surface) | set(bnd)
    for x, z in t["lamp_posts"] + spec["gate"]["lamp_posts"]:
        cols.add((x, z))
    gr = spec["gate"]["grille"]
    cols |= {(gr["x"], z) for z in range(gr["z"][0] - 1, gr["z"][1] + 2)}
    # the cove town (data geometry.cove, in this file's words): a building's rect; a house's door is the middle of its
    # door side, and its steps the 3 columns across it at 1, 2 and 3 out; a lamp post its column
    out_dir = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
    houses = [b for b in cove["buildings"] if "door" in b]

    def rect_of(r):
        return {(x, z) for x in range(r[0], r[2] + 1) for z in range(r[1], r[3] + 1)}

    def door_of(b):
        x0, z0, x1, z1 = b["rect"]
        return {"north": ((x0 + x1) // 2, z0), "south": ((x0 + x1) // 2, z1), "west": (x0, (z0 + z1) // 2),
                "east": (x1, (z0 + z1) // 2)}[b["door"]]

    def steps_of(b):
        (dx, dz), (x, z) = out_dir[b["door"]], door_of(b)
        return {(x + dx * k + (s if dz else 0), z + dz * k + (s if dx else 0)) for k in (1, 2, 3) for s in (-1, 0, 1)}
    cove_cols = set()
    for b in cove["buildings"]:
        cove_cols |= rect_of(b["rect"]) | (steps_of(b) if "door" in b else set())
    cove_cols |= {tuple(p) for p in cove["lamp_posts"]}
    cols |= cove_cols | path_cols
    notes["columns the build may write"] = len(cols)
    notes["cove buildings (houses)"] = [len(cove["buildings"]), len(houses)]

    # ---- Victory Road and the settlements
    routes = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))["routes"]
    vr = next(r for r in routes if "victory" in r["id"])
    near_vr = []
    for p in vr["corridor"]["polyline"]:
        if not (X0 - 300 <= p["x"] <= X1 + 300 and Z0 - 300 <= p["z"] <= Z1 + 300):
            continue
        reach = p.get("corridor_width_blocks", vr["corridor"]["width_blocks"]) / 2 + MARGIN
        for x, z in cols:
            if (x - p["x"]) ** 2 + (z - p["z"]) ** 2 <= reach * reach:
                near_vr.append((x, z))
                break
    if near_vr:
        probs.append("victory: %d Victory Road corridor points have a build column within half the corridor and %d, e.g. %s"
                     % (len(near_vr), MARGIN, near_vr[:3]))
    pts = []

    def walk_pts(o):
        if isinstance(o, list) and len(o) in (2, 3) and all(isinstance(v, (int, float)) for v in o):
            pts.append((o[0], o[-1]))
        elif isinstance(o, dict):
            for v in o.values():
                walk_pts(v)
        elif isinstance(o, list):
            for v in o:
                walk_pts(v)
    walk_pts(json.loads((ROOT / "data" / "vr_caves.json").read_text(encoding="utf-8")))
    pts = [p for p in pts if 1000 < p[0] < 8000 and 1000 < p[1] < 8000]
    if pts:
        vx0, vx1 = min(p[0] for p in pts) - MARGIN, max(p[0] for p in pts) + MARGIN
        vz0, vz1 = min(p[1] for p in pts) - MARGIN, max(p[1] for p in pts) + MARGIN
        if any(vx0 <= x <= vx1 and vz0 <= z <= vz1 for x, z in cols):
            probs.append("victory: a build column lies inside Victory Road's caves' extent (x%d-%d z%d-%d)" % (vx0, vx1, vz0, vz1))
        notes["Victory Road caves' extent"] = [vx0, vx1, vz0, vz1]
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    for tw in towns:
        fp = tw.get("footprint") or {}
        if "min_x" not in fp:
            continue
        if any(fp["min_x"] - MARGIN <= x <= fp["max_x"] + MARGIN and fp["min_z"] - MARGIN <= z <= fp["max_z"] + MARGIN for x, z in cols):
            probs.append("settlement: a build column comes within %d of %s's footprint" % (MARGIN, tw["id"]))

    # ---- the gap
    if not SCULPT.is_file():
        raise SystemExit("no %s: the sculpt's plan (tools/rift_heightmap.py) is needed to check the gate" % SCULPT.relative_to(ROOT))
    sc = json.loads(SCULPT.read_text(encoding="utf-8"))
    ring, nrm = sc["ring"], sc["normals"]
    e = next(e for e in sc["entrances"] if e["id"] == spec["gate"]["band"]["entrance"])
    T = len(ring)
    missing = [(j, ring[(e["ring"] + j) % T]) for j in range(-e["gap"], e["gap"] + 1) if tuple(ring[(e["ring"] + j) % T]) not in bnd]
    if missing:
        probs.append("gap: %d ring points of the sculpt's %s gap are not under the rockfall, e.g. %s" % (len(missing), e["id"], missing[:3]))
    crag = {}
    for side in (-1, 1):
        for jj in range(e["gap"] + 1, e["gap"] + 4):
            k = (e["ring"] + side * jj) % T
            (x, z), (nx, nz) = ring[k], nrm[k]
            hi = max(ground(half_up(x + nx * d), half_up(z + nz * d)) for d in range(-16, 1))
            if hi < 135:
                probs.append("gap: the rim at ring point %d (%d, %d), beyond the gap, rises only to y%d" % (k, x, z, hi))
            if jj == e["gap"] + 1:
                crag[side] = hi
    notes["crag tops beyond the gap's ends (heightmap)"] = [crag.get(-1), crag.get(1)]
    # SOUTHERN_RIFT_MEGA.md 13: the wall fills the mouth to the crag tops. Measured here, not taken from the data: the
    # data's crest at each end may not stand more than its jag below the crag beside it
    wall = spec["gate"]["band"]["wall"]
    for side, ctop in zip((-1, 1), wall["top"]):
        if side in crag and ctop < crag[side] - wall["jag"]:
            probs.append("gap: the wall's crest at the %s end (y%d) stands below the crag there (y%d)"
                         % ("j-" if side < 0 else "j+", ctop, crag[side]))

    # ---- the output
    idx = FN / "index.txt"
    if not idx.is_file():
        raise SystemExit("no %s: run `python tools/gulch_mine.py build` first" % idx.relative_to(ROOT))
    names = [n for n in idx.read_text(encoding="utf-8").split("\n") if n.strip()]
    if not names:
        raise SystemExit("%s lists no function: nothing was generated" % idx.relative_to(ROOT))
    final, files = replay(names)
    notes["cells written"] = len(final)
    out_grid = [c for c in final if not (X0 <= c[0] <= X1 and Z0 <= c[2] <= Z1 and Y0 <= c[1] <= Y1)]
    if out_grid:
        probs.append("inside: %d writes outside the grid, e.g. %s" % (len(out_grid), out_grid[:3]))
    stray_cols = {(x, z) for x, _y, z in final} - cols
    if stray_cols:
        probs.append("inside: %d written columns the plan does not cover, e.g. %s" % (len(stray_cols), sorted(stray_cols)[:3]))
    stray = [c for c, b in final.items() if b in AIRS and c not in carved and c[1] <= top(c[0], c[2])]
    if stray:
        probs.append("no stray: %d air cells under the top that are not carved, e.g. %s" % (len(stray), sorted(stray)[:3]))
    ring6 = set()
    for x, y, z in carved:
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            q = (x + d[0], y + d[1], z + d[2])
            if q not in carved and q[1] <= top(q[0], q[2]):
                ring6.add(q)
    unsealed = [c for c in ring6 if final.get(c) is None or final[c] in AIRS or final[c].split("[")[0] in FLUIDS]
    if unsealed:
        probs.append("sealed: %d cells next to the carved space end unwritten, air or fluid, e.g. %s" % (len(unsealed), sorted(unsealed)[:3]))
    notes["cells sealing the carved space"] = len(ring6)
    sb = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]
    used = sorted({b.split("[")[0] for b in final.values()})
    bad = [b for b in used if b in sb or b in FLUIDS or (b.startswith("mega_showdown:mega_meteorid_") and b.endswith("_ore"))]
    if bad:
        probs.append("blocks: written blocks that decide spawns, are fluids or drop evolution stones: %s" % bad)
    notes["distinct blocks written"] = len(used)

    # ---- the zone
    zdoc = adv("zone.json")
    zb = boxes_of(zdoc)
    if not zb:
        probs.append("zone: the zone advancement has no box")
    zy = spec["zone"]["y"]
    if any(b[0][1] != zy[0] or b[1][1] != zy[1] for b in zb):
        probs.append("zone: a zone box does not run y%d to y%d" % tuple(zy))
    zcols = set()
    for (x0, _y0, z0), (x1, _y1, z1) in zb:
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                zcols.add((x, z))
    notes["zone boxes"] = len(zb)
    notes["zone columns"] = len(zcols)
    poly = spec["zone"]["polygon"]
    mism = [c for c in list(zcols)[:: max(1, len(zcols) // 4000)] if not inside_poly(poly, c[0] + 0.5, c[1] + 0.5)]
    if mism:
        probs.append("zone: %d sampled zone columns lie outside the data's polygon, e.g. %s" % (len(mism), mism[:3]))
    g = spec["gate"]
    allowed_out = set(bnd) | set(rd) | {tuple(p) for p in g["lamp_posts"]} | {(gr["x"], z) for z in range(gr["z"][0] - 1, gr["z"][1] + 2)}
    wrote_cols = {(x, z) for x, _y, z in final}
    outside = sorted(c for c in wrote_cols if c not in zcols and c not in allowed_out)
    if outside:
        probs.append("zone: %d written columns outside the zone that are not the rockfall, the road or the gate's lamps, e.g. %s"
                     % (len(outside), outside[:3]))
    k, ex = g["knock"], g["exit"]
    for x in range(k[0], k[3] + 1):
        for z in range(k[2], k[5] + 1):
            if (x, z) in zcols:
                probs.append("zone: knock box column (%d, %d) is in the zone" % (x, z))
    for x in range(ex[0], ex[3] + 1):
        for z in range(ex[2], ex[5] + 1):
            if (x, z) not in zcols:
                probs.append("zone: exit box column (%d, %d) is not in the zone" % (x, z))
    ax, ay, az = int(math.floor(g["arrive"][0])), g["arrive"][1], int(math.floor(g["arrive"][2]))
    tx, ty, tz = int(math.floor(g["turn_back"][0])), g["turn_back"][1], int(math.floor(g["turn_back"][2]))
    if (ax, az) not in zcols:
        probs.append("zone: the arrival is not in the zone")
    if (tx, tz) in zcols:
        probs.append("zone: the turn-back point is in the zone")
    if ex[0] <= ax <= ex[3] and ex[2] <= az <= ex[5]:
        probs.append("zone: the arrival is inside the exit box (a player would bounce straight back out)")
    # the gulch's basin, walked from the square, is all zone: a way in the zone does not cover is a hole in the gate.
    # The walk may not cross the zone's closing line, run on 40 blocks past each end into the walls so it cannot slip
    # round an end
    (pa, pb) = poly[-1], poly[0]
    ln = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
    ux, uz = (pb[0] - pa[0]) / ln, (pb[1] - pa[1]) / ln
    a, b = (pa[0] - ux * 40, pa[1] - uz * 40), (pb[0] + ux * 40, pb[1] + uz * 40)
    start = tuple(sq["centre"])
    seen, dq = {start}, deque([start])
    bx0, bx1 = min(p[0] for p in poly) - 60, max(p[0] for p in poly) + 60
    bz0, bz1 = min(p[1] for p in poly) - 60, max(p[1] for p in poly) + 60
    while dq:
        c = dq.popleft()
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (c[0] + d[0], c[1] + d[1])
            if q in seen or q in bnd or not (bx0 <= q[0] <= bx1 and bz0 <= q[1] <= bz1):
                continue
            if ground(*q) > BASIN_Y or crosses((c[0] + 0.5, c[1] + 0.5), (q[0] + 0.5, q[1] + 0.5), a, b):
                continue
            seen.add(q)
            dq.append(q)
    uncovered = sorted(c for c in seen if c not in zcols)
    notes["basin columns walked from the square"] = len(seen)
    if uncovered:
        probs.append("zone: %d basin columns reached from the square lie outside the zone, e.g. %s" % (len(uncovered), uncovered[:3]))

    # ---- the cove town (SOUTHERN_RIFT_MEGA.md 13): in the zone, on the cove's floor, off the ways and the square, apart
    if cove["buildings"]:
        t_ = spec["town"]
        keep_off = rect_of(t_["square"]["rect"]) | rect_of(t_["yard"]["rect"]) | set(rd) | path_cols \
            | rect_of([pr[0], pr[1], pr[2], pr[3]]) | set(bnd)
        for h in t_["houses"]:
            keep_off |= rect_of(h["rect"])
        rects = []
        for b in cove["buildings"]:
            rc = rect_of(b["rect"])
            reach_ = rc | (steps_of(b) if "door" in b else set())
            if reach_ - zcols:
                probs.append("cove: %s reaches %d columns outside the zone" % (b["id"], len(reach_ - zcols)))
            if reach_ & keep_off:
                probs.append("cove: %s stands on the square, the yard, a way, the portal or the gate" % b["id"])
            gs = [ground(*c) for c in rc]
            lim = cove["max_range"] if "door" in b else cove["max_range_open"]
            if max(gs) - min(gs) > lim or max(gs) > cove["max_ground"]:
                probs.append("cove: %s stands on ground y%d-%d (at most %d apart, at most y%d)"
                             % (b["id"], min(gs), max(gs), lim, cove["max_ground"]))
            rects.append((b["id"], b["rect"]))
        a0 = cove["alley"][0]
        for i in range(len(rects)):
            for k_ in range(i + 1, len(rects)):
                (ia, ra), (ib, rb) = rects[i], rects[k_]
                if ra[0] - a0 <= rb[2] and rb[0] - a0 <= ra[2] and ra[1] - a0 <= rb[3] and rb[1] - a0 <= ra[3]:
                    probs.append("cove: %s and %s stand closer than the alley (%d)" % (ia, ib, a0))
        # the cutting is a way, not a wall: level with its rasterised y along every column
        for c in path_cols:
            y = surface[c][0]
            if final.get((c[0], y, c[1]), "minecraft:air") in AIRS or final.get((c[0], y + 1, c[1])) not in AIRS + (None,):
                probs.append("cove: the cutting at %s is not a floor at y%d with air over it" % (c, y))
                break

    # ---- the gate's rockfall and advancements
    lowrise = []
    for j, x, z, _nx, _nz in g["band"]["points"]:
        c = (int(x), int(z))
        base = top(*c)
        if not all(final.get((c[0], y, c[1]), "").split("[")[0] not in ("",) + AIRS for y in range(base + 1, base + 4)):
            lowrise.append((j, c))
    if lowrise:
        probs.append("gate: the rockfall is under 3 high over %d ring points of the gap, e.g. %s" % (len(lowrise), lowrise[:3]))
    # every ring point of the gap stands under rock to the crest (the crest line between the measured crag tops, less
    # the jag); the plug's to its flat top
    js = [p[0] for p in g["band"]["points"]]
    lowwall = []
    for j, x, z, _nx, _nz in g["band"]["points"]:
        c = (half_up(x), half_up(z))
        jc = bnd.get(c, j)                     # the ring point whose claim the column keeps (geometry.band)
        if abs(jc) <= g["plug"]["half_j"]:
            want = g["plug"]["top_y"]
        else:
            lo, hi = crag.get(-1, 0), crag.get(1, 0)
            want = lo + (hi - lo) * (jc - min(js)) / float(max(js) - min(js)) - 2 * wall["jag"]
        if top(*c) >= want:
            continue
        if any(final.get((c[0], y, c[1]), "minecraft:air") in AIRS for y in range(top(*c) + 1, int(want) + 1)):
            lowwall.append((j, c))
    if lowwall:
        probs.append("gate: the wall does not reach the crest over %d ring points of the gap, e.g. %s" % (len(lowwall), lowwall[:3]))
    flag = spec["flag"]["advancement"]
    knock = fn_text("gate/knock")
    if not re.search(r"execute if entity @s\[advancements=\{%s=true\}\] run tp @s " % re.escape(flag), knock) \
            or re.search(r"^tp @s", knock, re.M):
        probs.append("gate: the knock does not put through only a player holding %s" % flag)
    zf = fn_text("gate/zone")
    if "advancements={%s=false}" % flag not in zf or "gate/turn_back" not in zf:
        probs.append("gate: the zone check does not turn back only a player lacking %s" % flag)
    ward = boxes_of(adv("gate_ward.json"))[0]
    wm = g["ward_margin"]
    pl = g["plug"]
    plug = [c for c, j in bnd.items() if abs(j) <= pl["half_j"]
            and not (c[0] > pl["max_x"] and pl["trim_z"][0] <= c[1] <= pl["trim_z"][1])]
    short = [c for c in plug if not (ward[0][0] + wm <= c[0] <= ward[1][0] - wm and ward[0][2] + wm <= c[1] <= ward[1][2] - wm)]
    if not plug or short:
        probs.append("gate: %d plug columns within %d of the ward's edge" % (len(short), wm))
    if not (ward[0][1] + wm <= min(top(*c) + 1 for c in plug) and pl["top_y"] <= ward[1][1] - wm):
        probs.append("gate: the ward's height does not hold the plug with %d to spare" % wm)
    if "mining_fatigue" not in fn_text("gate/ward"):
        probs.append("gate: the ward gives no Mining Fatigue")

    # ---- the walk, on the replayed world
    nx, nz, ny = X1 - X0 + 1, Z1 - Z0 + 1, Y1 - Y0 + 1
    gy = ground.box(X0, Z0, X1, Z1).T
    ys = np.arange(ny)[None, None, :] + Y0
    op = ys > gy[:, :, None]
    for (x, y, z), bk in final.items():
        if X0 <= x <= X1 and Z0 <= z <= Z1 and Y0 <= y <= Y1:
            op[x - X0, z - Z0, y - Y0] = bk in AIRS or any(p_ in bk for p_ in PASSABLE)
    stand = op & np.roll(op, -1, 2) & ~np.roll(op, 1, 2)
    stand[:, :, 0] = stand[:, :, -1] = False

    def walk(s):
        i0 = (s[0] - X0, s[2] - Z0, s[1] - Y0)
        if not (0 <= i0[0] < nx and 0 <= i0[1] < nz and 0 <= i0[2] < ny) or not stand[i0]:
            return set()
        seen_, dq_ = {i0}, deque([i0])
        while dq_:
            i, kk, j = dq_.popleft()
            for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a_, b_ = i + di, kk + dk
                if not (0 <= a_ < nx and 0 <= b_ < nz):
                    continue
                for dj in (0, 1, -1, -2, -3):
                    c_ = j + dj
                    if not (0 <= c_ < ny) or not stand[a_, b_, c_]:
                        continue
                    if dj == 1 and not (j + 2 < ny and op[i, kk, j + 2]):
                        continue
                    if dj < 0 and not all(op[a_, b_, c_ + q] for q in range(1, -dj + 2) if c_ + q < ny):
                        continue
                    if (a_, b_, c_) not in seen_:
                        seen_.add((a_, b_, c_))
                        dq_.append((a_, b_, c_))
                    break
        return seen_

    def floor_in(cols_, x, z):
        f = cols_.get((x, z))
        return None if f is None else f[0]
    reach_in = walk((ax, ay, az))
    notes["cells walked from the arrival"] = len(reach_in)
    targets = {"the square": (sq["centre"][0] + 4, sq["surface_y"] + 1, sq["centre"][1])}
    for h in spec["mine"]["halls"]:
        cx, cz = h["centre"]
        targets["%s's floor" % h["id"]] = (cx, floor_in(halls[h["id"]], cx, cz), cz)
    for f in spec["mine"]["faces"]:
        targets["%s's front" % f["id"]] = tuple(f["stand"])
    for bn in spec["cutters"]["benches"]:
        targets["the counter before %s" % bn["id"]] = tuple(bn["customer"])
    # every cove house's doorway, its floor the highest ground under its rect (the heightmap)
    for b in houses:
        x, z = door_of(b)
        targets["%s's doorway" % b["id"]] = (x, max(top(*c) for c in rect_of(b["rect"])) + 1, z)
    anchors = {}
    for s in spec["megas"]["slots"]:
        x, z = s["anchor"]
        hc = halls[s["hall"]]
        if (x, z) not in hc:
            probs.append("megas: %s's anchor (%d, %d) is outside its hall" % (s["id"], x, z))
            continue
        anchors[s["id"]] = (x, hc[(x, z)][0], z)
        targets["%s's anchor" % s["id"]] = anchors[s["id"]]
    for what, c in targets.items():
        if c[1] is None or (c[0] - X0, c[2] - Z0, c[1] - Y0) not in reach_in:
            probs.append("walk: %s %s is not reached from the gate's arrival" % (what, c))
    reach_out = walk((tx, ty, tz))
    notes["cells walked from the turn-back point"] = len(reach_out)
    if not reach_out:
        probs.append("walk: the turn-back point %s is not a place to stand" % ((tx, ty, tz),))
    if (ax - X0, az - Z0, ay - Y0) in reach_out:
        probs.append("walk: from the turn-back point a walker reaches the arrival: the rockfall does not close the canyon")

    # ---- the faces: scenery, written once by the build, warded for good (SOUTHERN_RIFT_MEGA.md 13)
    fbox = {}
    for f in spec["mine"]["faces"]:
        x0, y0, z0, x1, y1, z1 = f["box"]
        box = {(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)}
        fbox[f["id"]] = box
        written = [final.get(c) for c in box]
        if None in written:
            probs.append("faces: %s's box is not written whole" % f["id"])
        n0 = sum(1 for bk in written if bk and bk.startswith("mega_showdown:mega_stone_crystal"))
        if n0 != f["crystals"]:
            probs.append("faces: %s is built with %d crystals, the data says %d" % (f["id"], n0, f["crystals"]))
        if box & carved:
            probs.append("faces: %s's box is carved" % f["id"])
    # nothing outside the build's own passes writes a face: the restore cycle is retired
    idx_files = {FN / (n + ".mcfunction") for n in names}
    rewrites = []
    for p_ in sorted(FN.rglob("*.mcfunction")):
        if p_ in idx_files:
            continue
        for ln in p_.read_text(encoding="utf-8").splitlines():
            mm = re.search(r"\b(fill|setblock|clone) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))?", ln)
            if not mm:
                continue
            a = [int(v) for v in mm.groups()[1:4]]
            b = [int(v) for v in mm.groups()[4:7]] if mm.group(5) else a
            for fid, box in fbox.items():
                xs = [c[0] for c in box]; ys = [c[1] for c in box]; zs = [c[2] for c in box]
                if min(a[0], b[0]) <= max(xs) and max(a[0], b[0]) >= min(xs) and min(a[1], b[1]) <= max(ys) \
                        and max(a[1], b[1]) >= min(ys) and min(a[2], b[2]) <= max(zs) and max(a[2], b[2]) >= min(zs):
                    rewrites.append((p_.name, fid))
    if rewrites:
        probs.append("faces: functions outside the build write a face (the restore is retired): %s" % rewrites[:3])
    tick_text = fn_text("tick")
    wm = spec["faces"]["ward_margin"]
    for f in spec["mine"]["faces"]:
        x0, y0, z0, x1, y1, z1 = f["box"]
        want = ("execute as @a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d,gamemode=!creative,gamemode=!spectator] run effect give @s "
                "minecraft:mining_fatigue 3 3 true" % (x0 - wm, y0 - wm, z0 - wm, x1 - x0 + 2 * wm, y1 - y0 + 2 * wm, z1 - z0 + 2 * wm))
        if want not in tick_text.splitlines():
            probs.append("faces: %s is not warded every tick with margin %d" % (f["id"], wm))
    if (PACK / "data" / "cobblers" / "tags" / "block").is_dir():
        probs.append("faces: the retired restore's block tag is still in the pack")
    tick = json.loads((PACK / "data" / "minecraft" / "tags" / "function" / "tick.json").read_text(encoding="utf-8")) \
        if (PACK / "data" / "minecraft" / "tags" / "function" / "tick.json").is_file() else {"values": []}
    if "cobblers:gulch_mine/tick" not in tick["values"]:
        probs.append("faces: the pack's tick tag does not run the driver")

    # ---- the Megas: the mine's slots and the farms' dens, one keeper
    mg = spec["megas"]
    all_dens = [("mine", s) for s in mg["slots"]] + [(fa["id"], dn) for fa in spec.get("farms", []) for dn in fa["dens"]]
    sa = fn_text("megas/spawn_at").strip().splitlines()
    if sa != ["$spawnpokemonat $(x) $(y) $(z) $(species) $(aspect) uncatchable level=$(level)"]:
        probs.append("megas: megas/spawn_at is not the one macro line (EXP-046: a plain spawn line does nothing after a restart)")
    plain = [p_.name for p_ in FN.rglob("*.mcfunction")
             if any(ln.startswith("spawnpokemonat ") or " run spawnpokemonat " in ln for ln in p_.read_text(encoding="utf-8").splitlines())]
    if plain:
        probs.append("megas: a plain spawnpokemonat line (parsed at start, it spawns nothing until /reload): %s" % plain[:3])
    for site, s in all_dens:
        if site == "mine":
            if s["id"] not in anchors:
                continue
            x, y, z = anchors[s["id"]]
        else:
            x, y, z = s["anchor"]
        i = s["id"]
        sp = fn_text("megas/spawn_%s" % i)
        call = "function cobblers:gulch_mine/megas/spawn_at {x:%d,y:%d,z:%d,species:\"%s\",aspect:\"%s\",level:%d}" % (
            x, y, z, s["species"], s["aspect"], s["level"])
        if call not in sp.splitlines():
            probs.append("megas: %s's spawn is not `%s`" % (i, call))
        if "execute positioned %d %d %d as @e[type=cobblemon:pokemon,tag=!%s,distance=..2,limit=1,sort=nearest] run function " \
           "cobblers:gulch_mine/megas/bind_%s" % (x, y, z, mg["tag"], i) not in sp:
            probs.append("megas: %s is not claimed in the function that spawns it" % i)
        bind = fn_text("megas/bind_%s" % i)
        if "PersistenceRequired:1b" not in bind or ("tag @s add %s.%s" % (mg["tag"], i)) not in bind \
                or ("tag @s add %s" % mg["tag"]) not in bind.splitlines():
            probs.append("megas: %s is not tagged and kept from the despawner" % i)
        want = "positioned %d %d %d unless entity @s[distance=..%d] run tp @s %d %d %d" % (x, y, z, s["leash"], x, y, z)
        if want not in fn_text("leash_%s" % site):
            probs.append("megas: %s's leash is not `%s`" % (i, want))
        if site == "mine":
            i0 = (x - X0, z - Z0, y - Y0)
            if not stand[i0]:
                probs.append("megas: %s's anchor %s is not a floor cell to stand on" % (i, (x, y, z)))
        # the respawn clock: gm.gone is written only by load when unset, by the keeper when a Mega is seen (-1) or first
        # seen gone (the game time), and by the spawn (-1); the spawn waits gm.resp from it with nobody near
        keep = fn_text("megas/keep_%s" % i).splitlines()
        for need in ("execute if score #d gm.t < #%s gm.resp run return 0" % i,
                     "execute if entity @a[x=%d,y=%d,z=%d,distance=..%d] run return 0" % (x, y, z, mg["spawn_clear"]),
                     "execute if score #%s gm.gone matches -1 run function cobblers:gulch_mine/megas/gone_%s" % (i, i),
                     "execute unless loaded %d %d %d run return 0" % (x, y, z)):
            if need not in keep:
                probs.append("megas: %s's keeper lacks `%s`" % (i, need))
    allowed_gone = re.compile(r"^(execute unless score #(\w+) gm\.gone matches -2147483648\.\. run scoreboard players set #\2 gm\.gone 0"
                              r"|execute if score #n gm\.t matches 1\.\. run scoreboard players set #\w+ gm\.gone -1"
                              r"|scoreboard players operation #\w+ gm\.gone = #now gm\.t"
                              r"|scoreboard players set #\w+ gm\.gone -1"
                              r"|execute if score #\w+ gm\.gone matches -1 run function cobblers:gulch_mine/megas/gone_\w+"
                              r"|scoreboard players operation #d gm\.t -= #\w+ gm\.gone"
                              r"|scoreboard objectives add gm\.gone dummy)$")
    for p_ in sorted(FN.rglob("*.mcfunction")):
        rel = p_.relative_to(FN).as_posix()[:-len(".mcfunction")]
        for ln in p_.read_text(encoding="utf-8").splitlines():
            if "gm.gone" not in ln or ln.startswith("#"):
                continue
            if not allowed_gone.match(ln):
                probs.append("megas: %s moves a respawn clock in a way the design does not allow: `%s`" % (rel, ln))
            elif ln.startswith("scoreboard players set #") and ln.endswith("gm.gone -1") and not rel.startswith("megas/spawn_"):
                probs.append("megas: %s clears a respawn clock outside a spawn: `%s`" % (rel, ln))
            elif "= #now gm.t" in ln and not rel.startswith("megas/gone_"):
                probs.append("megas: %s starts a respawn clock outside the keeper's first sight of a gone Mega: `%s`" % (rel, ln))

    # ---- the Cutters
    cu = spec["cutters"]
    place = fn_text("cutters_place")
    sums = [ln for ln in place.splitlines() if ln.startswith("summon minecraft:villager ")]
    if len(sums) != len(cu["benches"]):
        probs.append("cutters: %d villagers summoned, %d benches" % (len(sums), len(cu["benches"])))
    sold = []
    off = cu["offer"]
    for ln in sums:
        for need in ("NoAI:1b", "Invulnerable:1b", "PersistenceRequired:1b", "level:5"):
            if need not in ln:
                probs.append("cutters: a villager lacks %s" % need)
        mm = re.match(r"summon minecraft:villager (-?[\d.]+) (-?\d+) (-?[\d.]+) ", ln)
        vx, vy, vz = int(math.floor(float(mm.group(1)))), int(mm.group(2)), int(math.floor(float(mm.group(3))))
        under = final.get((vx, vy - 1, vz), "")
        if not under or under in AIRS or final.get((vx, vy, vz), "minecraft:air") not in AIRS:
            probs.append("cutters: the villager at %s does not stand on a written floor in open air" % ((vx, vy, vz),))
        for r in re.findall(r"\{buy:\{id:\"([^\"]+)\",count:(\d+)\},buyB:\{id:\"([^\"]+)\",count:(\d+)\},sell:\{id:\"([^\"]+)\",count:(\d+)\},"
                            r"uses:(\d+),maxUses:(\d+),rewardExp:(\w+),xp:(\d+),priceMultiplier:([\d.]+)f,specialPrice:(-?\d+),demand:(-?\d+)\}", ln):
            buy, bc, buyb, bbc, sell, sc_, uses, mx, rexp, xp, pm, spr, dem = r
            if (buy, int(bc), buyb, int(bbc), int(sc_)) != (off["raw"], off["raw_count"], off["fee"], off["fee_count"], 1):
                probs.append("cutters: an offer for %s is not %d %s + %d %s -> 1" % (sell, off["raw_count"], off["raw"], off["fee_count"], off["fee"]))
            if int(mx) != off["max_uses"] or rexp != "0b" or int(xp) != 0 or float(pm) != 0.0 or int(spr) != 0 or int(dem) != 0 or int(uses) != 0:
                probs.append("cutters: the offer for %s is not unlimited, without experience and without price drift" % sell)
            sold.append(sell)
    want60 = [s for bn in cu["benches"] for s in bn["stones"]]
    if sorted(sold) != sorted(want60) or len(set(sold)) != len(sold):
        probs.append("cutters: %d offers for %d distinct stones; the data offers %d" % (len(sold), len(set(sold)), len(want60)))
    if set(sold) & set(cu["left_out"]):
        probs.append("cutters: left-out stones are offered: %s" % sorted(set(sold) & set(cu["left_out"])))
    notes["stones offered by the Cutters"] = len(set(sold))

    # ---- limits
    for f in sorted(FN.rglob("*.mcfunction")):
        for n, c, w in FL.check_file(f):
            probs.append("limits: %s line %d: %s" % (f.name, n, w))
    return probs, notes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root")
    a = p.parse_args(argv)
    probs, notes = audit(a.source_root)
    for k, v in notes.items():
        print("  %-48s %s" % (k, v))
    for pr in probs:
        print("PROBLEM:", pr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"problems": probs, "notes": notes}, indent=1) + "\n", encoding="utf-8")
    print("%s: %d problem(s)" % ("CLEAN" if not probs else "FAILED", len(probs)))
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
