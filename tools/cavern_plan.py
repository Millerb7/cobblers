#!/usr/bin/env python
"""The Displaced City cavern: plan and build functions (commands), for a human-composed town to stand in.

Reads data/towns.json displaced_city.underground (centre, 200 x 200, y32-72) and data/foliage.json cherry_vale, and
writes a datapack of numbered functions plus a plan report. Nothing runs until the functions are called.

  floor     graded, not flat, and not terraced: the top of a mountain a town once stood on, bottoming at y21, the
            deepest it can go without meeting lava. Benches whose radius wanders and whose surface tilts, an old
            road ridge climbing from the tunnel's arrival, and noise loud enough to survive rounding.
  ceiling   the rock itself, `rock_over_ceiling` blocks under the real ground and smoothed: y72 under the creek in
            the south-west, median y79, up to about y107 in the north-east. It is not lit, and a lantern's light
            dies 16 blocks up, so from the floor there is nothing up there to see. That is the point.
  light     from the ground, never the roof. Strings of chain run tree to tree with lanterns hung under them, and
            the tunnel's arrival has a lit apron. The wild floor is left at block light 0 deliberately: hostiles
            need exactly that, so the dark is an encounter area and the lit ground is the safe ground. The city's
            own lanterns come with the city, which is composed by hand.
  seal      water pockets in the rock (WorldPainter's underground water) inside the cavern and a 2-block shell are
            replaced with stone before anything is dug, so nothing floods.
  trees     cherry_vale's classes (cherry, birch, azalea) from the foliage object library, placed by spacing on a
            density field that thins on the benches and summit (the town's ground) and clears the arrival.
  tunnel    dug, not built: a bore that wanders in width, height and centre, walls left as cut rock, a rubble floor
            and rubble steps, alcoves where the diggers followed a seam, and a lantern every 8 blocks.
  biome     /fillbiome to minecraft:cherry_grove over the cavern volume, in its own function (not called by the others).

  python tools/cavern_plan.py --source-root <root> [--install <server>/datapacks]     # ground from the heightmap only
  then: /reload, /function cobblers:cavern/00_seal ... /function cobblers:cavern/50_tunnel (60_biome separately)
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import numpy as np

import terrain as T
from place_town import rotate, fill_boxes
from sculpt import unit_noise, smoothstep
import function_limits

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "kits" / "structures" / "foliage"
LATTICE = 10
ROCK_OVER_CEILING = 24
# The floor sits as deep as it can go for free. Lava is the limit, not bedrock: the exported world has 4,203 lava
# cells in 2,923 of the 40,000 columns, from y15 down. A floor bottoming at y21 keeps 6 blocks of rock over the
# highest of them, so no lava seal pass is needed; below y16 one would be.
BASE_Y = 21
LAVA_TOP = 15
# The ceiling is not a plane. It follows the rock, ROCK_OVER_CEILING under the real ground, smoothed so it reads as
# a cave roof rather than a copy of the surface. It is y72 only under the creek, and rises to about y107 in the
# north-east. CEIL_MAX is a backstop, above the y107 the survey found.
CEIL_MAX = 112
CEIL_SMOOTH = 9
MAX_GRADE = 0.25          # 1:4, the steepest a player walks up without jumping


def summit_floor(n, seed, arrival_local, base=BASE_Y):
    """Floor top y over an n x n cavern, centre at (n/2, n/2).

    The first cut of this floor was a smooth radial function rounded to integers, and it read from the air as rice
    paddies: a dead-level ring 14 blocks wide at the y46 bench, another 6 wide at y40, a flat cap inside r30, and
    only +/-0.8 of noise before np.rint, which rounds most of that away. Contour terraces, the same failure the
    surface had, and fixed the same way: vary the grade rather than smooth it.

      grade    a low-frequency field scales the fall, so the tread length (1/g) varies by sector instead of being
               one number for the whole dome
      benches  their radius wanders with angle (a 2/3/5-harmonic wobble, +/-13 blocks) and each one tilts across
               its width, so no contour closes on itself and no bench is level
      blends   10 blocks in and 10 out of a 20-block bench: there is no flat middle left to terrace
      noise    2.2 blocks peak at spacing 14 plus 1.1 at spacing 30, both above the 0.5 that rounding can erase
    """
    zz, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    u, v = xx - n / 2, zz - n / 2
    ang = np.arctan2(v, u)
    wob = 6.0 * np.cos(2 * ang + 0.7) + 4.5 * np.cos(3 * ang + 2.1) + 3.0 * np.cos(5 * ang + 4.3)
    r = np.hypot(u, v * 1.08) + wob
    grade = 0.75 + 0.5 * (0.5 + 0.5 * np.tanh(unit_noise(n, 48, seed + 11)))
    # the dome bottoms 4 above the clip floor: if it bottomed AT it, every column past r98 would clip to one value
    # and the outer margin would be a single 121-block-wide flat, which is the terrace the benches no longer are
    f = base + 4 + 20 * (1 - smoothstep(18, 98, r)) * grade           # the mountain top, falling unevenly
    for level, r0, r1, tilt in ((base + 13, 42, 62, 0.055), (base + 7, 68, 86, 0.040)):
        w = smoothstep(r0, r0 + 10, r) * (1 - smoothstep(r1 - 10, r1, r))
        bench = level + tilt * (u * math.cos(0.9) + v * math.sin(0.9))
        f = f * (1 - 0.8 * w) + bench * 0.8 * w                        # streets could run these, but they drain
    ax, az = arrival_local                                            # old road ridge from the arrival to the summit
    L = math.hypot(ax, az)
    t = np.clip((u * ax + v * az) / (L * L), 0, 1)
    d = np.hypot(u - t * ax, v - t * az)
    ramp = base + 4 + (1 - t) * 13
    f = np.where(d < 10, f * smoothstep(3, 10, d) + ramp * (1 - smoothstep(3, 10, d)), f)
    f = f + 2.2 * np.tanh(unit_noise(n, 14, seed)) + 1.1 * np.tanh(unit_noise(n, 30, seed + 5))
    # the upper clip has to sit above the natural peak (base+4+20*1.25 plus noise ~= base+29) or it caps the summit
    # into a flat plateau, which is the terrace the benches no longer are
    return np.clip(np.rint(f), base, base + 32).astype(int), r, d


def _smooth(a, passes):
    """Edge-padded box blur. np.roll would wrap the north edge onto the south and tilt the roof at the corners."""
    b = a.astype(float)
    for _ in range(passes):
        p = np.pad(b, 1, mode="edge")
        b = 0.4 * b + 0.15 * (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:])
    return b


def cave_roof(top, rock_over, ceil_max, passes):
    """Ceiling y per column: under the real rock, smoothed, and never violating the rock rule after smoothing.

    The first cut took the single lowest legal value (y72, set by the creek bed) and applied it to all 40,000
    columns, so the roof was a plane -- which is why it read as a lid. The legal cap is surface minus `rock_over`:
    y72 under the creek in the south-west, median y79, and up to y107 in the north-east. Following it gives a roof
    that climbs away from you instead of one you can measure at a glance.
    """
    cap = np.minimum(top - rock_over, ceil_max)
    return np.minimum(np.rint(_smooth(cap, passes)).astype(int), cap)


def poisson_positions(density, spacing, rng, tries=30):
    """Dart throwing on a density field (0..1 per cell), minimum spacing in blocks."""
    n = density.shape[0]
    cell = spacing / math.sqrt(2)
    gw = int(math.ceil(n / cell))
    grid = -np.ones((gw, gw), int)
    pts = []
    cand = rng.random((n * n * 3 // int(spacing * spacing), 2)) * n
    for x, z in cand:
        if rng.random() > density[int(z), int(x)]:
            continue
        gx, gz = int(x / cell), int(z / cell)
        ok = True
        for i in range(max(0, gx - 2), min(gw, gx + 3)):
            for j in range(max(0, gz - 2), min(gw, gz + 3)):
                k = grid[j, i]
                if k >= 0 and math.hypot(pts[k][0] - x, pts[k][1] - z) < spacing:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            grid[gz, gx] = len(pts)
            pts.append((x, z))
    return pts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--surface-world", default=None, help=argparse.SUPPRESS)
    p.add_argument("--install", default=None)
    p.add_argument("--seed", type=int, default=20260916)
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    towns = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}
    city = towns["displaced_city"]
    ug = city["underground"]
    cx, cz = ug["cavern_centre"]["x"], ug["cavern_centre"]["z"]
    n = ug["cavern_footprint_blocks"][0]
    x0, z0 = cx - n // 2, cz - n // 2
    x1, z1 = x0 + n - 1, z0 + n - 1
    y_lo, y_hi = ug["cavern_y"]
    rng = np.random.default_rng(a.seed)

    # ground above the cavern and along the tunnel: region files if given, else the heightmap (conservative floor)
    bx0, bz0, bx1, bz1 = min(x0, city["footprint"]["min_x"]) - 40, min(z0, city["footprint"]["min_z"]) - 120, x1 + 40, z1 + 40
    # Ground from the heightmap, never from a world. The cavern plan was the first tool to be bitten by
    # this: regenerated from a world the previous carve had already damaged, it followed the damage
    # instead of the terrain. And rounded, not floored: floor(h) is a block low across 48% of the map.
    if a.surface_world:
        raise SystemExit("--surface-world is gone: the cavern's ground comes from the heightmap (tools/ground.py), "
                         "never from a world, which holds the last carve")
    import ground as G
    ground = G.load(a.source_root) if a.source_root else G.load()
    basis = "heightmap %s, rounded (tools/ground.py)" % world["heightmap"]["sha256"][:12]
    top = np.array([[ground(x, z) for x in range(x0, x1 + 1)] for z in range(z0, z1 + 1)])

    # tunnel: mouth on the city's surface site facing the trough, around the creek's head, into the cavern's
    # north-west corner
    fp = city["footprint"]
    mouth = (fp["max_x"], (fp["min_z"] + fp["max_z"]) // 2 - 10)
    arrival = (x0 + 12, z0 + 10)
    # The run is not fixed. Dropping the floor to y21 put the arrival 13 blocks lower without moving the mouth, and
    # a fixed 339-block corridor then graded 0.292 -- over the 1:4 a player can walk. The corner is pushed north
    # until the path is long enough for MAX_GRADE, and the grade is asserted below rather than just reported.
    def route(back):
        c_ = (x0 + 12, z0 - back)
        return [mouth, (mouth[0] + 70, c_[1]), c_, arrival]

    def run_len(wps):
        return sum(math.hypot(b[0] - a_[0], b[1] - a_[1]) for a_, b in zip(wps, wps[1:]))
    floor, r_field, ridge_d = summit_floor(n, a.seed, (arrival[0] - cx, arrival[1] - cz))
    _drop = ground(*mouth) - int(floor[arrival[1] - z0, arrival[0] - x0])
    back = 50
    while back < 240 and _drop / max(run_len(route(back)), 1) > MAX_GRADE:
        back += 5
    waypoints = route(back)
    ceiling = cave_roof(top, ROCK_OVER_CEILING, CEIL_MAX, CEIL_SMOOTH)
    report = {"generator": "tools/cavern_plan.py", "ground_basis": basis, "cavern": [x0, z0, x1, z1],
              "floor_y": {"min": int(floor.min()), "median": float(np.median(floor)), "max": int(floor.max())},
              "ceiling_y": {"min": int(ceiling.min()), "median": float(np.median(ceiling)), "max": int(ceiling.max()),
                            "columns_below_72": int((ceiling < y_hi).sum())},
              "headroom": {"min": int((ceiling - 2 - floor).min()), "median": float(np.median(ceiling - 2 - floor))},
              "rock_over_ceiling_min": int((top - ceiling).min()), "surface_above": [int(top.min()), int(top.max())]}
    fn = {}

    # 00 seal water and lava pockets: the cavern plus a 2-block shell, over the range the NEW floor and roof
    # actually span. data/towns.json still says y32-72; the floor now bottoms at 22 and the roof reaches 110, and
    # sealing the old range would leave live water in the 8 blocks of new floor below it.
    # +10 over the roof, not +2: the rock above the north-east roof carries an aquifer at y113-117, and the roof
    # there is y110. Two blocks of margin leaves live water three blocks above a ceiling that has natural voids in
    # it, which is a flood path into the chamber.
    seal_lo = int(floor.min()) - 4
    # The top of the seal is PER COLUMN, and it is not negotiable. A single flat top of ceiling.max()+10 = y120
    # reaches above the ground (the surface over this footprint runs y96-135), and "fill stone replace water" does
    # not know the difference between a buried pocket and a river: it turned 900 columns of the Glacial Tear creek
    # into stone at y98-100. Stop 4 blocks under the real ground, every column.
    cmds = ["# seal underground water and lava, from y%d to 4 under the ground, per column" % seal_lo]
    # The whole rock column, not just 10 blocks over the roof. Stopping at ceiling+10 left pockets higher in the
    # rock, and natural voids let them drain into the chamber: 1,458 fluid cells inside it on the first rebuild.
    # `top` is the top SOLID block, so for a creek column it is the BED (y95-97), not the water surface (y98-100)
    # -- stopping 4 under it still leaves the Glacial Tear alone, which is what narrowing the seal was protecting.
    seal_top = top - 4
    for fluid in ("minecraft:water", "minecraft:lava"):
        for j in range(n):
            i = 0
            while i < n:
                t_ = int(seal_top[j, i])
                k = i
                while k + 1 < n and int(seal_top[j, k + 1]) == t_:
                    k += 1
                if t_ > seal_lo:
                    cmds.append("fill %d %d %d %d %d %d minecraft:stone replace %s"
                                % (x0 + i, seal_lo, z0 + j, x0 + k, t_, z0 + j, fluid))
                i = k + 1
    fn["00_seal"] = cmds
    report["seal_range"] = {"from": seal_lo, "to": "per column, min(ceiling+10, ground-4)",
                            "top_min": int(seal_top.min()), "top_max": int(seal_top.max())}

    # 05 reset what the previous cut of this cavern left behind. Its glowing false sky was sea lanterns behind
    # light blue glass at y71-72; where the new roof is higher those blocks fall inside the excavation and become
    # air, but under the creek the new roof IS y72, so the old sky would survive as the ceiling there. The old
    # invisible light lattice sat at old-floor+3 and has to go too, or the dark cavern is still lit.
    cmds = ["# undo the previous cut: the false sky, and the light lattice"]
    for old in ("minecraft:sea_lantern", "minecraft:light_blue_stained_glass"):
        for b in fill_boxes(x0, seal_lo, z0, x1, int(seal_top.max()), z1):
            cmds.append("fill %d %d %d %d %d %d minecraft:stone replace %s" % (b + (old,)))
    for b in fill_boxes(x0, seal_lo, z0, x1, int(seal_top.max()), z1):
        cmds.append("fill %d %d %d %d %d %d minecraft:air replace minecraft:light" % b)
    fn["05_reset"] = cmds

    # 10 excavate: air from floor+1 to ceiling-2 per column, in x runs of equal bounds
    cmds, dug = ["# excavate: air between the graded floor and the false sky"], 0
    for j in range(n):
        i = 0
        while i < n:
            lo, hi = floor[j, i] + 1, ceiling[j, i] - 2
            k = i
            while k + 1 < n and floor[j, k + 1] + 1 == lo and ceiling[j, k + 1] - 2 == hi:
                k += 1
            if hi >= lo:
                cmds.append("fill %d %d %d %d %d %d minecraft:air" % (x0 + i, lo, z0 + j, x0 + k, hi, z0 + j))
                dug += (k - i + 1) * (hi - lo + 1)
            i = k + 1
    fn["10_excavate"] = cmds
    report["excavated_blocks"] = dug

    # 15 cap the roof. The ceiling is natural rock the excavation stopped short of, and natural rock has holes in
    # it: 511 of 40,000 columns had a non-solid block exactly at the ceiling line, from voids in the stone between
    # y76 and y110. Left alone those are skylights, mob routes and, under the north-east aquifer, a leak. Four
    # blocks of stone are laid over every column whatever is there.
    cmds = ["# cap the roof: 4 solid blocks over every column, because natural rock has voids in it"]
    for j in range(n):
        i = 0
        while i < n:
            c_ = ceiling[j, i]
            k = i
            while k + 1 < n and ceiling[j, k + 1] == c_:
                k += 1
            xa, xb, z = x0 + i, x0 + k, z0 + j
            cmds.append("fill %d %d %d %d %d %d minecraft:stone replace #minecraft:air" % (xa, c_, z, xb, c_ + 3, z))
            cmds.append("fill %d %d %d %d %d %d minecraft:stone replace minecraft:water" % (xa, c_, z, xb, c_ + 3, z))
            i = k + 1
    fn["15_cap"] = cmds

    # 20 floor surface only. There is no ceiling surface any more: the roof is the natural rock the excavation
    # stopped 2 blocks short of. The glowing false sky it used to carry is what made the ceiling readable, and a
    # lantern's light (15, falling 1 a block) dies 16 blocks up, so an unlit roof at 30+ blocks renders black.
    cmds = ["# floor: grass on dirt. The ceiling is left as the rock it is, and unlit on purpose"]
    for j in range(n):
        i = 0
        while i < n:
            f_ = floor[j, i]
            k = i
            while k + 1 < n and floor[j, k + 1] == f_:
                k += 1
            xa, xb, z = x0 + i, x0 + k, z0 + j
            cmds += ["fill %d %d %d %d %d %d minecraft:dirt" % (xa, f_ - 3, z, xb, f_ - 1, z),
                     "fill %d %d %d %d %d %d minecraft:grass_block" % (xa, f_, z, xb, f_, z)]
            i = k + 1
    fn["20_surfaces"] = cmds

    # 30 trees: cherry_vale classes on a density field
    fol = json.loads((ROOT / "data" / "foliage.json").read_text(encoding="utf-8"))["types"]["cherry_vale"]
    lib = json.loads((LIBRARY / "library.json").read_text(encoding="utf-8"))["objects"]
    lib = list(lib.values()) if isinstance(lib, dict) else lib
    slope_local = np.hypot(*np.gradient(floor.astype(float)))
    town_ground = ((r_field < 30) | ((r_field > 44) & (r_field < 62)) | ((r_field > 70) & (r_field < 84)))
    clump = 0.5 + 0.5 * np.tanh(unit_noise(n, 24, a.seed + 7) * fol.get("clumping", 0.7))
    density = np.where(town_ground, 0.25, 1.0) * clump
    density[ridge_d < 10] = 0.0
    density[:14, :14] = 0.0
    density[(ceiling - floor) < 16] = 0.0                               # no crowns in the low ceiling under the creek
    weights = {c["group"]: c["core"] for c in fol["classes"]}
    spacing = {c["group"]: c["spacing"] for c in fol["classes"]}
    trees, cmds = [], ["# cherry vale trees from the foliage object library"]
    taken = np.zeros((n, n), bool)
    for group in sorted(weights, key=lambda g_: -weights[g_]):
        share = weights[group] / sum(weights.values())
        objs = [o for o in lib if o["group"] == group]
        if not objs:
            continue
        target_per_ha = fol["stems_per_ha"] * share
        pts = poisson_positions(np.clip(density * target_per_ha / fol["stems_per_ha"] * 3, 0, 1), spacing[group], rng)
        keep = int(round(target_per_ha * (n * n) / 10000 * float(density.mean())))
        rng.shuffle(pts)
        for x, z in pts[:keep]:
            xi, zi = int(x), int(z)
            if taken[max(0, zi - 3):zi + 4, max(0, xi - 3):xi + 4].any():
                continue
            o = objs[int(rng.integers(len(objs)))]
            rot = ["none", "clockwise_90", "180", "counterclockwise_90"][int(rng.integers(4))]
            ox, oy, oz = o["origin"]
            rx, rz = rotate(ox, oz, rot)
            wx, wz = x0 + xi, z0 + zi
            y = int(floor[zi, xi]) + 1
            if y + o["height"] > ceiling[zi, xi] - 3:
                continue
            cmds.append("place template cobblers:cavern/foliage/%s %d %d %d %s none 1.0 0" % (o["file"][:-4], wx - rx, y - oy, wz - rz, rot))
            taken[max(0, zi - 1):zi + 2, max(0, xi - 1):xi + 2] = True
            trees.append({"object": o["name"], "group": group, "at": [wx, y, wz], "rotation": rot,
                          "height": int(o["height"])})
    fn["30_trees"] = cmds
    report["trees"] = {"count": len(trees), "by_group": {g_: sum(1 for t in trees if t["group"] == g_) for g_ in weights}}

    # 40 light from the ground up, never from the roof. Strings of chain run tree to tree with lanterns hung
    # under them, and the tunnel's arrival gets a lit apron so the way in and out reads from anywhere on the floor.
    #
    # A string is a marker, not a lamp: a lantern is light 15 falling 1 a block, so one hung 14 above the floor
    # puts light 1 directly beneath it. That is the point -- points of light in the dark. The floor lighting comes
    # with the city, which is yours to compose; the wild floor is left at block light 0 on purpose, because
    # hostiles need exactly that, so the dark margins are an encounter area and the lit ground is the safe ground.
    cmds = ["# string lights tree to tree, and the apron at the tunnel arrival"]
    nodes = [(t["at"][0], t["at"][2], t["at"][1], t["height"]) for t in trees]
    degree = [0] * len(nodes)
    pairs, chains, lanterns = [], 0, 0
    order = sorted(range(len(nodes)), key=lambda i_: (nodes[i_][1], nodes[i_][0]))
    for i in order:
        if degree[i] >= 2:
            continue
        cand = sorted(((math.hypot(nodes[j][0] - nodes[i][0], nodes[j][1] - nodes[i][1]), j)
                       for j in range(len(nodes)) if j != i and degree[j] < 2
                       and 10 <= math.hypot(nodes[j][0] - nodes[i][0], nodes[j][1] - nodes[i][1]) <= 26
                       and tuple(sorted((i, j))) not in pairs))
        for d, j in cand[:2 - degree[i]]:
            pairs.append(tuple(sorted((i, j))))
            degree[i] += 1
            degree[j] += 1
    for i, j in pairs:
        ax, az, ay, ah = nodes[i]
        bx, bz, by, bh = nodes[j]
        hang = min(ay + int(ah * 0.75), by + int(bh * 0.75))
        L = int(round(math.hypot(bx - ax, bz - az)))
        axis = "x" if abs(bx - ax) >= abs(bz - az) else "z"
        seen = set()
        for s in range(L + 1):
            t_ = s / L
            x = int(round(ax + (bx - ax) * t_))
            z = int(round(az + (bz - az) * t_))
            y = int(round(hang - 2.0 * 4 * t_ * (1 - t_)))             # a shallow catenary, 2 blocks of sag
            if (x, y, z) in seen:
                continue
            seen.add((x, y, z))
            cmds.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:leaves" % (x, y, z, x, y, z))
            cmds.append("setblock %d %d %d minecraft:chain[axis=%s] keep" % (x, y, z, axis))
            chains += 1
            if s % 6 == 3:                                             # a lantern hung under every sixth link
                cmds.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:leaves" % (x, y - 1, z, x, y - 1, z))
                cmds.append("setblock %d %d %d minecraft:lantern[hanging=true] keep" % (x, y - 1, z))
                lanterns += 1
    ax_, az_ = arrival
    for k in range(16):                                                # the apron: lanterns on the ground at the way out
        aang = 2 * math.pi * k / 16
        px, pz = int(round(ax_ + 7 * math.cos(aang))), int(round(az_ + 7 * math.sin(aang)))
        if not (x0 <= px <= x1 and z0 <= pz <= z1):
            continue
        cmds.append("setblock %d %d %d minecraft:lantern[hanging=false] keep" % (px, floor[pz - z0, px - x0] + 1, pz))
        lanterns += 1
    fn["40_light"] = cmds
    report["light"] = {"strings": len(pairs), "chain_blocks": chains, "lanterns": lanterns,
                       "roof_lit": False, "wild_floor": "left at block light 0 on purpose"}

    # 50 tunnel: 5 wide, 5 tall, no steeper than 1:4, a stair at each step, lit every 20 blocks
    arr_y = int(floor[arrival[1] - z0, arrival[0] - x0])
    mouth_y = ground(*mouth)
    pts = []
    for (ax, az), (bx, bz) in zip(waypoints, waypoints[1:]):
        L = math.hypot(bx - ax, bz - az)
        for s in range(int(L)):
            pts.append((ax + (bx - ax) * s / L, az + (bz - az) * s / L))
    pts.append(waypoints[-1])
    total = len(pts) - 1
    drop = mouth_y - arr_y
    grade = drop / max(total, 1)
    cmds = ["# tunnel from the cave mouth (%d, %d, y%d) to the cavern (%d, %d, y%d): %d blocks, grade %.3f"
            % (mouth[0], mouth[1], mouth_y, arrival[0], arrival[1], arr_y, total, grade)]
    stations = []
    for s in range(len(pts)):
        x, z = pts[s]
        y = int(round(mouth_y - drop * s / max(total, 1)))
        j0 = min(len(pts) - 1, s + 1)
        dx, dz = pts[j0][0] - x, pts[j0][1] - z
        facing = ("east" if dx > 0 else "west") if abs(dx) >= abs(dz) else ("south" if dz > 0 else "north")
        stations.append((int(round(x)), y, int(round(z)), {"east": "west", "west": "east", "north": "south", "south": "north"}[facing]))
    # Dug, not built. The first cut was a 5x5 stone-brick corridor with a stair at every step, which reads as
    # masonry; this one varies its bore station by station, leaves the walls as the rock they were cut from, and
    # floors itself in rubble. Clear height never drops below 4 and the bore never below 2, so it stays walkable.
    #
    # 1: seal water around the corridor, 2: carve every station, 3: floor it, in that order, because a later
    # station's carve takes out an earlier station's floor if the floor is laid as it goes (it did, at every step)
    RUBBLE = ["minecraft:cobblestone", "minecraft:cobblestone", "minecraft:stone", "minecraft:gravel",
              "minecraft:andesite", "minecraft:coarse_dirt"]
    for xi, y, zi, _ in stations[::4]:
        cmds.append("fill %d %d %d %d %d %d minecraft:stone replace minecraft:water" % (xi - 5, y - 2, zi - 5, xi + 5, y + 8, zi + 5))
    trng = np.random.default_rng(a.seed + 91)                          # its own stream, so the bore does not shift
    bore = []                                                          # when the tree count changes
    for s, (xi, y, zi, _) in enumerate(stations):
        w = 2 + int(trng.integers(0, 2))                               # half-width 2 or 3: the bore wanders
        h = 4 + int(trng.integers(0, 3))                               # clear height 4 to 6
        ox, oz = int(trng.integers(-1, 2)), int(trng.integers(-1, 2))  # and so does its centre
        bore.append((w, h, ox, oz))
        cmds.append("fill %d %d %d %d %d %d minecraft:air" % (xi + ox - w, y + 1, zi + oz - w, xi + ox + w, y + h, zi + oz + w))
        if s % 17 == 5:                                                # an alcove where the diggers followed a seam
            ex, ez = (w + 3, w) if s % 34 == 5 else (w, w + 3)
            cmds.append("fill %d %d %d %d %d %d minecraft:air"
                        % (xi + ox - ex, y + 1, zi + oz - ez, xi + ox + ex, y + 3, zi + oz + ez))
    prev_y = None
    for s, (xi, y, zi, back) in enumerate(stations):
        w = bore[s][0] + 1
        ox, oz = bore[s][2], bore[s][3]
        cmds.append("fill %d %d %d %d %d %d %s replace #minecraft:replaceable"
                    % (xi + ox - w, y, zi + oz - w, xi + ox + w, y, zi + oz + w, RUBBLE[int(trng.integers(len(RUBBLE)))]))
        if prev_y is not None and y < prev_y:                           # a rubble step, not a cut stair
            cmds.append("fill %d %d %d %d %d %d %s replace #minecraft:replaceable"
                        % (xi + ox - w, y + 1, zi + oz - w, xi + ox + w, y + 1, zi + oz + w,
                           RUBBLE[int(trng.integers(len(RUBBLE)))]))
        prev_y = y
    # A lantern every 8 blocks, on the floor, not an invisible light block in the air: the light has to look like
    # something someone hung there. Measured at 20 on the first cut, 47 of 85 stations sat at block light 0, which
    # is exactly where monsters spawn, so 8 is the spacing and this check gets re-run after it is built.
    # Hung from the roof of the bore, not stood on the floor. A floor lantern was placed with `keep` at y+1, which
    # is exactly where the rubble step goes at every descending station -- so it failed to place almost everywhere
    # and 35 of 51 sampled stations sat at block light 0. The bore roof is rock at y+h+1, so a hanging lantern at
    # y+h always has support and always has air to occupy.
    # On a post at the side of the bore, every 6 stations. Two earlier attempts failed for opposite reasons: a
    # floor lantern at y+1 landed where the rubble step goes (35 of 51 stations dark), and a roof-hung one had no
    # roof to hang from along the 76-block open cut at the mouth (23 of 102 dark, all of them in the cut). A post
    # works in both: the wall stands on the rubble where y+1 is clear, and where the step already fills y+1 the
    # lantern simply sits on the step. Either way it has support and the light is 2 above the floor.
    for s in range(0, len(stations), 6):
        xi, y, zi, _ = stations[s]
        w_, h_, ox, oz = bore[s]
        px, pz = xi + ox + w_ - 1, zi + oz
        # unconditional, not `keep`: stations are 1 block apart and descend about 1 in 4, so a neighbour's rubble
        # step lands in this cell often enough that `keep` skipped 2 posts in every 10
        cmds.append("setblock %d %d %d minecraft:cobblestone_wall" % (px, y + 1, pz))
        cmds.append("setblock %d %d %d minecraft:lantern[hanging=false]" % (px, y + 2, pz))
    if grade > MAX_GRADE + 1e-6:
        raise SystemExit("tunnel grade %.3f exceeds %.2f over %d blocks: lengthen the run" % (grade, MAX_GRADE, total))
    cover = [(s, ground(stations[s][0], stations[s][2]) - (stations[s][1] + 5)) for s in range(3, len(stations) - 3)]
    fn["50_tunnel"] = cmds
    report["tunnel"] = {"mouth": [mouth[0], mouth_y, mouth[1]], "arrival": [arrival[0], arr_y, arrival[1]], "waypoints": waypoints,
                        "length_blocks": total, "drop": drop, "grade": round(grade, 3), "max_grade": MAX_GRADE,
                        "rock_cover_over_tunnel": {"min": int(min(c for _, c in cover)) if cover else None,
                                                   "median": float(np.median([c for _, c in cover])) if cover else None,
                                                   "open_cut_blocks_from_mouth": next((s_ for s_, c in cover if c >= 3), None),
                                                   "every_20": [[s_, int(c)] for s_, c in cover[::20]]}}

    # 70 drain. Sealing happens before digging, so anything that seeps in while the chamber is being carved is
    # still there afterwards: 91 cells spread over the whole floor, not one leak. With the shell sealed and the
    # roof capped nothing new arrives, so one pass of air-for-water at the end finishes it.
    cmds = ["# drain: clear anything that seeped in during the dig"]
    for j in range(n):
        i = 0
        while i < n:
            lo, hi = floor[j, i] + 1, ceiling[j, i] - 2
            k = i
            while k + 1 < n and floor[j, k + 1] + 1 == lo and ceiling[j, k + 1] - 2 == hi:
                k += 1
            if hi >= lo:
                cmds.append("fill %d %d %d %d %d %d minecraft:air replace minecraft:water" % (x0 + i, lo, z0 + j, x0 + k, hi, z0 + j))
            i = k + 1
    fn["70_drain"] = cmds

    # 60 biome (separate)
    cmds = ["# cherry grove biome over the cavern volume"]
    for b in fill_boxes(x0, y_lo, z0, x1, y_hi, z1, limit=32768):
        cmds.append("fillbiome %d %d %d %d %d %d minecraft:cherry_grove" % b)
    fn["60_biome"] = cmds

    # approach: nearest routed-leg point to the mouth, then a contour-following path
    legs = json.loads((ROOT / "derived" / "routes" / "critical_legs.json").read_text(encoding="utf-8"))["legs"]
    best = min(((math.hypot(q[0] - mouth[0], q[1] - mouth[1]), q, l) for l in legs for q in l["polyline"]), key=lambda t: t[0])
    report["approach"] = {"from_leg": "%s->%s" % (best[2]["from"], best[2]["to"]), "leg_point": best[1], "straight_blocks": round(best[0])}
    try:
        from route_path import route
        m = 60
        ax0, az0 = min(best[1][0], mouth[0]) - m, min(best[1][1], mouth[1]) - m
        ax1, az1 = max(best[1][0], mouth[0]) + m, max(best[1][1], mouth[1]) + m
        hh = heights[az0:az1, ax0:ax1]
        passable = (T.slope_degrees(hh) <= 30) & (hh > T.sea_level(world))
        path, cost = route(hh, passable, (int(best[1][0]) - ax0, int(best[1][1]) - az0), (mouth[0] - 2 - ax0, mouth[1] - az0), 8.0)
        if path:
            report["approach"]["path_every_16"] = [[x + ax0, z + az0] for x, z in path[::16]] + [[path[-1][0] + ax0, path[-1][1] + az0]]
            report["approach"]["length_blocks"] = len(path)
    except Exception as exc:                                         # the plan still stands without a trail
        report["approach"]["error"] = str(exc)

    out = Path(ROOT / "build" / "datapacks" / "cobblers_cavern")
    if out.exists():
        shutil.rmtree(out)
    for name, lines in fn.items():
        f = out / "data" / "cobblers" / "function" / "cavern" / (name + ".mcfunction")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("\n".join(function_limits.ensure_loaded(lines)) + "\n", encoding="utf-8")
    used = {t["object"] for t in trees}
    for o in lib:
        if o["name"] in used:
            dest = out / "data" / "cobblers" / "structure" / "cavern" / "foliage" / o["file"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(LIBRARY / o["file"], dest)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: Displaced City cavern (tools/cavern_plan.py)"}}, indent=2) + "\n", encoding="utf-8")
    report["functions"] = {k: len(v) for k, v in fn.items()}
    rep = ROOT / "derived" / "cavern" / "plan.json"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(dict(report, tree_positions=trees), indent=1, default=int), encoding="utf-8")
    np.savez_compressed(rep.with_suffix(".npz"), floor=floor, ceiling=ceiling, top=top)
    print(json.dumps(report, indent=1, default=int))
    if a.install:
        import runtime_guard
        dest = runtime_guard.check(a.install, "install into") / out.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(out, dest)
        print("installed", dest)


if __name__ == "__main__":
    main()
