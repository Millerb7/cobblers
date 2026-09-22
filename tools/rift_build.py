#!/usr/bin/env python
"""Build the Rift's wall, spires, cross-walls, gatehouses, floor light and biome from data (docs/mechanics/RIFT_ZONES.md).

Everything is decided from the canonical heightmap (tools/ground.py) and committed data: the outline
(data/landmarks.json rift.extent), the parameters (data/rift.json), Victory Road (data/routes.json) and the
settlements to keep clear of (data/placements.json). Nothing reads a world to decide (the ground rule).

  wall          on the outline, 2 thick, 16 above the ground: blackstone base, obsidian, crying obsidian sprinkled
  spires        every 32 blocks along the outline, 3x3 to y320, leaning and tapering, crying-obsidian bands, the top
                third purple glass; none within 60 blocks of a guard site
  rubble        within 40 blocks of G1-G3 the wall drops to 4-7 blocks (never gapped: still not walkable)
  gatehouses    G1-G3 on the outline, G4 in the wall behind the League: a one-wide walkway, roofed, a barrier
                directly behind the guard's cell, and a placeholder marker where the guard will stand
  cross-walls   rim to rim across the floor where zones meet (the throat, the south-east branch's mouth, behind
                the League), 16 above the higher rim
  floor light   crying obsidian set into the floor, one column in 80
  biome         cobblers:the_rift (a world datapack) painted with /fillbiome over every chunk the outline touches

  python tools/rift_build.py --source-root <root>                 plan, write the packs and derived/rift/plan.json
  python tools/rift_build.py verify --world <stopped world copy>  every planned block, read back; fails closed

Outputs: build/datapacks/cobblers_rift (server pack: cobblers:rift/blocks_<tile>, cobblers:rift/biome_<tile>, and
cobblers:rift/index listing them in order), build/datapacks/cobblers_rift_biome (world pack: the biome registry
entry), derived/rift/plan.json (what verify checks).

Staging only until the owner approves the live build. The biome ships without the spawn changes RIFT_ZONES section 7
requires, which is harmless only where no spawn pool is installed (the staging export).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import function_limits as FL  # noqa: E402

BUILD = ROOT / "build" / "datapacks"
PACK = BUILD / "cobblers_rift"
BIOME_PACK = BUILD / "cobblers_rift_biome"
PLAN = ROOT / "derived" / "rift" / "plan.json"
TILE = 128
PACK_FORMAT = 48
# verify reads a world to CHECK a result, never to decide one (CLAUDE.md, the ground rule; tools/ground_rule.py)
WORLD_READS = {"verify", "main"}


class RiftError(RuntimeError):
    pass


# ------------------------------------------------------------------ geometry


def point_in(x, z, poly):
    c = False
    for i in range(len(poly)):
        x1, z1 = poly[i]
        x2, z2 = poly[i - 1]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            c = not c
    return c


def inside_any(x, z, polys):
    return any(point_in(x, z, p) for p in polys)


def line_cells(a, b):
    (ax, az), (bx, bz) = a, b
    n = max(abs(bx - ax), abs(bz - az), 1)
    out = []
    for i in range(n + 1):
        c = (round(ax + (bx - ax) * i / n), round(az + (bz - az) * i / n))
        if not out or out[-1] != c:
            out.append(c)
    return out


def ring(poly, polys):
    """[(cell, outward normal)] along the polygon's edges, in order."""
    out = []
    for i in range(len(poly)):
        a, b = poly[i - 1], poly[i]
        dx, dz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dz) or 1.0
        nx, nz = dz / L, -dx / L
        mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if inside_any(mx + nx * 3, mz + nz * 3, polys):
            nx, nz = -nx, -nz
        for c in line_cells(a, b):
            if not out or out[-1][0] != c:
                out.append((c, (nx, nz)))
    return out


def scan_rows(polys, z0, z1):
    """{z: [(x0, x1), ...]} inclusive spans inside any polygon (even-odd per polygon), for z0..z1."""
    rows = {}
    for z in range(z0, z1 + 1):
        zc = z + 0.5
        spans = []
        for poly in polys:
            xs = []
            for i in range(len(poly)):
                x1, y1 = poly[i]
                x2, y2 = poly[i - 1]
                if (y1 > zc) != (y2 > zc):
                    xs.append(x1 + (zc - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                spans.append((math.ceil(xs[j] - 0.5), math.floor(xs[j + 1] - 0.5)))
        if spans:
            rows[z] = spans
    return rows


def cardinal(nx, nz):
    return (1 if nx > 0 else -1, 0) if abs(nx) >= abs(nz) else (0, 1 if nz > 0 else -1)


def rim_ends(g, centre, axis_from, axis_to):
    """The two rim points of the floor's cross-section through `centre`, perpendicular to the axis: walking out each
    way until the ground has stopped rising for 12 blocks above y100."""
    ax, az = axis_to[0] - axis_from[0], axis_to[1] - axis_from[1]
    n = math.hypot(ax, az)
    px, pz = -az / n, ax / n
    ends = []
    for sgn in (-1, 1):
        best, since, last = -1, 0, None
        for t in range(0, 400):
            x, z = round(centre[0] + px * t * sgn), round(centre[1] + pz * t * sgn)
            h = g(x, z)
            if h > best:
                best, since, last = h, 0, (x, z)
            else:
                since += 1
            if since >= 12 and best > 100:
                break
        else:
            raise RiftError("no rim found from %s towards %d" % (centre, sgn))
        ends.append((last, best))
    return ends


# ------------------------------------------------------------------ the plan


class Plan:
    def __init__(self):
        self.cols = {}      # (x, z) -> {y: block}, last write wins
        self.summons = []   # (x, y, z, command)
        self.checks = []    # (x, y, z, [allowed blocks], what)
        self.counts = {}

    def put(self, x, y, z, block):
        self.cols.setdefault((x, z), {})[y] = block

    def column(self, x, z, y0, y1, block):
        for y in range(y0, y1 + 1):
            self.put(x, y, z, block)

    def count(self, what, n=1):
        self.counts[what] = self.counts.get(what, 0) + n


def load(source_root):
    import ground
    g = ground.load(source_root)
    rift = next(x for x in json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))["landmarks"]
                if x["id"] == "rift")
    spec = json.loads((ROOT / "data" / "rift.json").read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    routes = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))
    return g, rift["extent"]["polygons"], spec, placements, routes


def keep_clear(placements, polys, spec):
    """{name: rectangle} the Rift's blocks stay out of: every building of every settlement near the Rift (its placed
    box, tools/place_donor.py box, 4 blocks round), and the whole town of a settlement that data/rift.json lists as
    standing on the outline (tools/town_audit.py town_bounds), where the wall stops either side."""
    import place_donor
    import town_audit
    out = {}
    xs = [p[0] for poly in polys for p in poly]
    zs = [p[1] for poly in polys for p in poly]
    X0, X1, Z0, Z1 = min(xs) - 64, max(xs) + 64, min(zs) - 64, max(zs) + 64
    for q in placements["placements"]:
        if not q.get("position") or not q.get("size"):
            continue
        lo, hi = place_donor.box(q)
        if hi[0] < X0 or lo[0] > X1 or hi[2] < Z0 or lo[2] > Z1:
            continue
        out[q["id"]] = (lo[0] - 4, lo[2] - 4, hi[0] + 4, hi[2] + 4)
    for sid in spec.get("settlements_on_outline") or {}:
        out[sid] = town_audit.town_bounds(sid, placements)
    return out


def in_rects(x, z, rects):
    return next((s for s, (x0, z0, x1, z1) in rects.items() if x0 <= x <= x1 and z0 <= z <= z1), None)


def route_crossing(route, polys, near):
    pts = [(p["x"], p["z"]) if isinstance(p, dict) else (p[0], p[-1]) for p in route["corridor"]["polyline"]]
    best = None
    for a, b in zip(pts, pts[1:]):
        if inside_any(*a, polys) != inside_any(*b, polys):
            c = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
            d = math.hypot(c[0] - near[0], c[1] - near[1])
            if best is None or d < best[0]:
                best = (d, c)
    if best is None:
        raise RiftError("route %s never crosses the Rift's outline" % route["id"])
    return best[1]


def gatehouse(plan, g, name, P, N, spec, above_to=None):
    """A gatehouse centred on P, walkway along N (N points to the outside, where players arrive)."""
    gh = spec["gatehouse"]
    T = (-N[1], N[0])
    half_l, half_w = gh["length"] // 2, gh["width"] // 2
    g0 = g(*P)
    cells = set()
    for a in range(-half_l, half_l + 1):
        for c in range(-half_w, half_w + 1):
            x, z = P[0] + a * N[0] + c * T[0], P[1] + a * N[1] + c * T[1]
            cells.add((x, z))
            lo = min(g(x, z), g0) - 2
            plan.column(x, z, lo, g0 + gh["height"] - 1, gh["block"])
            plan.put(x, g0 + gh["height"], z, gh["roof"])
            if above_to:
                plan.column(x, z, g0 + gh["height"] + 1, above_to, spec["wall"]["block"])
        # the walkway: floor at g0, open for two blocks, the roof over it
        x, z = P[0] + a * N[0], P[1] + a * N[1]
        plan.put(x, g0, z, gh["block"])
        plan.column(x, z, g0 + 1, g0 + gh["height"] - 1, "minecraft:air")
        plan.put(x, g0 + 3, z, gh["roof"])
        plan.checks.append((x, g0 + 1, z, ["minecraft:air", "minecraft:barrier"], "%s walkway" % name))
        plan.checks.append((x, g0 + 3, z, [gh["roof"]], "%s roof over the walkway" % name))
    # the barrier directly behind the guard's cell (guard at +1, towards the outside)
    for y in (g0 + 1, g0 + 2):
        plan.put(P[0], y, P[1], gh["barrier"])
        plan.checks.append((P[0], y, P[1], [gh["barrier"]], "%s barrier" % name))
    gx, gz = P[0] + N[0], P[1] + N[1]
    plan.summons.append((gx, g0 + 1, gz, 'summon minecraft:armor_stand %d %d %d {CustomName:\'"%s guard (placeholder)"\','
                         'CustomNameVisible:1b,NoGravity:1b,Invulnerable:1b,Tags:["cobblers_rift_guard"]}'
                         % (gx, g0 + 1, gz, name)))
    # approaches: 3 wide, 12 long each side, cleared to 4 high and floored where the ground falls away
    for a in list(range(half_l + 1, half_l + 13)) + list(range(-half_l - 12, -half_l)):
        for c in (-1, 0, 1):
            x, z = P[0] + a * N[0] + c * T[0], P[1] + a * N[1] + c * T[1]
            h = g(x, z)
            if h < g0:
                plan.column(x, z, h + 1, g0, "minecraft:polished_blackstone")
            plan.column(x, z, g0 + 1, g0 + 4, "minecraft:air")
    plan.count("gatehouses")
    return cells, g0


def spire(plan, g, rng, cell, sp):
    x0, z0 = cell
    base = g(x0, z0) + 1
    top = sp["top_y"]
    H = top - base
    if H < 40:
        return
    dx = dz = 0
    step = sp["lean"]["step_blocks"]
    mx = sp["lean"]["max_offset"]
    for y in range(base, top + 1):
        k = y - base
        if k and k % step == 0:
            dx = max(-mx, min(mx, dx + rng.choice((-1, 0, 1))))
            dz = max(-mx, min(mx, dz + rng.choice((-1, 0, 1))))
        f = k / H
        if f < sp["shape"]["full_3x3_to"]:
            shape = [(i, j) for i in (-1, 0, 1) for j in (-1, 0, 1)]
        elif f < sp["shape"]["plus_to"]:
            shape = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]
        else:
            shape = [(0, 0)]
        if f >= sp["glass"]["from_fraction"]:
            blk = sp["glass"]["block"]
        elif k % sp["band"]["every"] == 0:
            blk = sp["band"]["block"]
        else:
            blk = sp["block"]
        for i, j in shape:
            plan.put(x0 + dx + i, y, z0 + dz + j, blk)
    plan.checks.append((x0 + dx, top, z0 + dz, [sp["glass"]["block"]], "spire top"))
    plan.checks.append((x0, base + 2, z0, [sp["block"], sp["band"]["block"]], "spire foot"))
    plan.count("spires")


def build(source_root):
    g, polys, spec, placements, routes = load(source_root)
    plan = Plan()
    clear = keep_clear(placements, polys, spec)
    wall = spec["wall"]
    rng = random.Random(spec["spires"]["seed"])

    # guard sites on the outline
    rings = [ring(p, polys) for p in polys]
    all_ring = [(c, n) for r in rings for c, n in r]
    sites = {}
    for name, s in spec["guard_sites"].items():
        if s["on"] != "outline":
            continue
        near = tuple(s["near"])
        if s.get("where_route_crosses"):
            route = next(r for r in routes["routes"] if r["id"] == s["where_route_crosses"])
            near = route_crossing(route, polys, near)
        c, n = min(all_ring, key=lambda cn: math.hypot(cn[0][0] - near[0], cn[0][1] - near[1]))
        sites[name] = (c, cardinal(*n))

    gate_cells = set()
    for name, (c, N) in sites.items():
        cells, _ = gatehouse(plan, g, name, c, N, spec)
        gate_cells |= cells

    # the wall on the outline, and rubble near the outline's guard sites
    rub = spec["rubble"]
    skipped = {}
    walled = set()
    for r in rings:
        for (x, z), (nx, nz) in r:
            ox, oz = cardinal(nx, nz)
            for cx, cz in ((x, z), (x + ox, z + oz)):
                if (cx, cz) in walled or (cx, cz) in gate_cells:
                    continue
                s = in_rects(cx, cz, clear)
                if s:
                    skipped[s] = skipped.get(s, 0) + 1
                    continue
                walled.add((cx, cz))
                h = g(cx, cz)
                near_site = min((math.hypot(cx - p[0], cz - p[1]) for p, _ in sites.values()), default=1e9)
                if near_site <= rub["radius"]:
                    top = h + rng.randint(*rub["height"])
                    plan.column(cx, cz, h + 1, top, rng.choice([wall["block"], wall["base_block"]]))
                    plan.count("rubble columns")
                    if rng.randrange(rub["scatter_one_in"]) == 0:
                        sx, sz = cx + ox * rng.randint(2, 5), cz + oz * rng.randint(2, 5)
                        plan.put(sx, g(sx, sz) + 1, sz, wall["base_block"])
                    continue
                top = h + wall["height_above_ground"]
                plan.column(cx, cz, h + 1, h + wall["base_height"], wall["base_block"])
                plan.column(cx, cz, h + wall["base_height"] + 1, top, wall["block"])
                for y in range(h + 1, top + 1):
                    if rng.randrange(wall["sprinkle"]["one_in"]) == 0:
                        plan.put(cx, y, cz, wall["sprinkle"]["block"])
                plan.checks.append((cx, top, cz, [wall["block"], wall["sprinkle"]["block"]], "wall top"))
                plan.checks.append((cx, h + 1, cz, [wall["base_block"], wall["sprinkle"]["block"]], "wall base"))
                plan.count("wall columns")

    # spires every N blocks along each ring, none near a guard site or a settlement
    sp = spec["spires"]
    for r in rings:
        for i in range(0, len(r), sp["every_blocks"]):
            (x, z), _ = r[i]
            if min((math.hypot(x - p[0], z - p[1]) for p, _ in sites.values()), default=1e9) < rub["no_spires_within"]:
                continue
            if in_rects(x, z, clear):
                continue
            spire(plan, g, rng, (x, z), sp)

    # cross-walls, rim to rim; G4 in the one behind the League
    import place_donor
    league = next(p for p in placements["placements"] if p.get("id") == "league_building")
    llo, lhi = place_donor.box(league)
    for name, cw in spec["cross_walls"].items():
        (e1, r1), (e2, r2) = rim_ends(g, tuple(cw["centre"]), cw["axis_from"], cw["axis_to"])
        top = max(r1, r2) + spec["cross_wall_height_above_rim"]
        ax, az = cw["axis_to"][0] - cw["axis_from"][0], cw["axis_to"][1] - cw["axis_from"][1]
        A = cardinal(ax, az)
        cells = line_cells(e1, e2)
        if cw.get("clear_of") == "league":
            gap = min(max(llo[0] - x, 0, x - lhi[0]) + max(llo[2] - z, 0, z - lhi[2]) for x, z in cells)
            if gap < cw["clearance"]:
                raise RiftError("cross-wall %s comes within %d blocks of the League (needs %d)"
                                % (name, gap, cw["clearance"]))
        gate = None
        for s_name, s in spec["guard_sites"].items():
            if s["on"] == "cross_wall" and s["cross_wall"] == name:
                mid = len(cells) // 2
                span = cells[mid - 40: mid + 41]
                P = min(span, key=lambda c: (g(*c), abs(cells.index(c) - mid)))
                N = {"south": (0, 1), "north": (0, -1), "east": (1, 0), "west": (-1, 0)}[s["outside"]]
                gc, _ = gatehouse(plan, g, s_name, P, N, spec, above_to=top)
                gate = gc
        n = 0
        for x, z in cells:
            for cx, cz in ((x, z), (x + A[0], z + A[1])):
                if gate and (cx, cz) in gate:
                    continue
                h = g(cx, cz)
                plan.column(cx, cz, h + 1, top, wall["block"])
                n += 1
                if n % 7 == 0:
                    plan.checks.append((cx, top, cz, [wall["block"]], "cross-wall %s top" % name))
        plan.count("cross-wall %s columns" % name, n)
        plan.count("cross-wall %s top y" % name, top)

    # floor light, never in a town (it would take a paved street or plaza cell)
    import town_audit
    towns = {}
    for sid, s in placements["settlements"].items():
        c = s.get("centre")
        if c and (inside_any(c[0], c[1], polys) or sid in (spec.get("settlements_on_outline") or {})):
            towns[sid] = town_audit.town_bounds(sid, placements)
    fl = spec["floor_light"]
    frng = random.Random(fl["seed"])
    xs = [p[0] for poly in polys for p in poly]
    zs = [p[1] for poly in polys for p in poly]
    rows = scan_rows(polys, min(zs), max(zs))
    chunks = set()
    for z, spans in rows.items():
        for x0, x1 in spans:
            for cx in range(x0 >> 4, (x1 >> 4) + 1):
                chunks.add((cx, z >> 4))
            hs = g.box(x0, z, x1, z)[0]
            for i, h in enumerate(hs):
                x = x0 + i
                if h < fl["floor_below_y"] and frng.randrange(fl["one_in"]) == 0 and not in_rects(x, z, clear) \
                        and not in_rects(x, z, towns) and (x, z) not in walled:
                    plan.put(x, int(h), z, fl["block"])
                    plan.checks.append((x, int(h), z, [fl["block"]], "floor light"))
                    plan.count("floor lights")
    plan.biome_chunks = sorted(chunks)
    plan.count("biome chunks", len(chunks))
    plan.skipped = skipped
    plan.sites = {k: [list(c), list(n)] for k, (c, n) in sites.items()}
    return plan, spec


# ------------------------------------------------------------------ writing


def runs(col):
    """[(y0, y1, block)] vertical runs of one column."""
    out = []
    for y in sorted(col):
        b = col[y]
        if out and out[-1][2] == b and out[-1][1] == y - 1:
            out[-1][1] = y
        else:
            out.append([y, y, b])
    return out


def functions(plan, spec):
    tiles = {}
    for (x, z), col in plan.cols.items():
        t = (x // TILE, z // TILE)
        for y0, y1, b in runs(col):
            tiles.setdefault(t, []).append(
                "setblock %d %d %d %s" % (x, y0, z, b) if y0 == y1 else "fill %d %d %d %d %d %d %s" % (x, y0, z, x, y1, z, b))
    for x, y, z, cmd in plan.summons:
        tiles.setdefault((x // TILE, z // TILE), []).append(cmd)
    out = {}
    order = []
    for (tx, tz) in sorted(tiles):
        name = "blocks_%d_%d" % (tx, tz)
        lines = FL.ensure_loaded(["# Generated by tools/rift_build.py: the Rift's blocks in tile %d %d" % (tx, tz)]
                                 + tiles[(tx, tz)])
        problems = FL.check_lines(lines, name)
        if problems:
            raise RiftError("function %s would be refused: %s" % (name, problems[:3]))
        out[name] = lines
        order.append(name)
    btiles = {}
    for cx, cz in plan.biome_chunks:
        btiles.setdefault((cx // 8, cz // 8), []).append((cx, cz))
    y0, y1 = spec["biome"]["y"]
    for (tx, tz), chs in sorted(btiles.items()):
        name = "biome_%d_%d" % (tx, tz)
        x0, z0 = tx * 128, tz * 128
        lines = ["# Generated by tools/rift_build.py: cobblers:the_rift over the Rift's chunks in tile %d %d" % (tx, tz),
                 "forceload add %d %d %d %d" % (x0, z0, x0 + 127, z0 + 127)]
        for cx, cz in sorted(chs):
            for ya, yb in ((y0, y0 + 127), (y0 + 128, y1)):
                lines.append("fillbiome %d %d %d %d %d %d %s" % (cx * 16, ya, cz * 16, cx * 16 + 15, yb, cz * 16 + 15,
                                                                 spec["biome"]["id"]))
        lines.append("forceload remove %d %d %d %d" % (x0, z0, x0 + 127, z0 + 127))
        out[name] = lines
        order.append(name)
    return out, order


def biome_json(spec):
    b = spec["biome"]
    return {"has_precipitation": b["has_precipitation"], "temperature": b["temperature"], "downfall": b["downfall"],
            "effects": b["effects"], "spawners": {}, "spawn_costs": {}, "carvers": {}, "features": []}


def write(plan, spec):
    fns, order = functions(plan, spec)
    for d in (PACK, BIOME_PACK):
        if d.exists():
            shutil.rmtree(d)
    fdir = PACK / "data" / "cobblers" / "function" / "rift"
    fdir.mkdir(parents=True)
    (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": PACK_FORMAT,
                                      "description": "Cobblers: the Rift's wall, spires, gatehouses and biome paint (tools/rift_build.py)"}}) + "\n",
                                      encoding="utf-8")
    for name, lines in fns.items():
        (fdir / (name + ".mcfunction")).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (fdir / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8", newline="\n")
    ns, path = spec["biome"]["id"].split(":")
    bdir = BIOME_PACK / "data" / ns / "worldgen" / "biome"
    bdir.mkdir(parents=True)
    (bdir / (path + ".json")).write_text(json.dumps(biome_json(spec), indent=2) + "\n", encoding="utf-8")
    (BIOME_PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": PACK_FORMAT,
                                            "description": "Cobblers: the Rift biome registry entry (tools/rift_build.py)"}}) + "\n",
                                            encoding="utf-8")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps({"counts": plan.counts, "skipped_for_settlements": plan.skipped, "sites": plan.sites,
                                "checks": plan.checks, "functions": order,
                                "commands": sum(len(v) for v in fns.values())}, indent=0), encoding="utf-8")
    return fns, order


# ------------------------------------------------------------------ verify


def verify(world):
    """Every planned check, read back from a stopped world copy. Fails closed: no plan, or a plan with no checks of
    any kind the build makes, fails."""
    import build_audit
    if not PLAN.is_file():
        print("FAIL: no derived/rift/plan.json: run the build first")
        return 1
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    checks = p["checks"]
    kinds = {c[4].split(" ")[0] for c in checks}
    need = {"wall", "spire", "floor", "G1", "G2", "G3", "G4", "cross-wall"}
    if not checks or not need <= kinds:
        print("FAIL: the plan checks %s, not everything the build makes (%s)" % (sorted(kinds), sorted(need - kinds)))
        return 1
    W = build_audit.World(world)
    by, bad = {}, {}
    for x, y, z, allowed, what in checks:
        key = what.split(" guard")[0]
        ok = W.block(x, y, z) in allowed
        by.setdefault(key, [0, 0])[0 if ok else 1] += 1
        if not ok:
            bad.setdefault(key, []).append((x, y, z, W.block(x, y, z)))
    for k in sorted(by):
        good, wrong = by[k]
        print("%-32s %6d of %6d as planned%s" % (k, good, good + wrong,
                                                ("   e.g. %s" % bad[k][:2]) if wrong else ""))
    total = sum(b for _, b in by.values())
    print("rift: %s" % ("clean" if total == 0 else "%d MISMATCHES" % total))
    return 0 if total == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "verify"))
    ap.add_argument("--source-root")
    ap.add_argument("--world")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        if not a.world:
            ap.error("verify needs --world <stopped world copy>")
        return verify(a.world)
    plan, spec = build(a.source_root)
    fns, order = write(plan, spec)
    print("rift: %d functions, %d commands; %s" % (len(order), sum(len(v) for v in fns.values()),
                                                  ", ".join("%s %d" % kv for kv in sorted(plan.counts.items()))))
    print("placed blocks: %d" % sum(1 for col in plan.cols.values() for b in col.values() if b != "minecraft:air"))
    if plan.skipped:
        print("wall left out inside settlements: %s" % plan.skipped)
    print("guard sites:", {k: v[0] for k, v in plan.sites.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
