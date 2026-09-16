#!/usr/bin/env python
"""The Displaced City cavern: plan and build functions (commands), for a human-composed town to stand in.

Reads data/towns.json displaced_city.underground (centre, 200 x 200, y32-72) and data/foliage.json cherry_vale, and
writes a datapack of numbered functions plus a plan report. Nothing runs until the functions are called.

  floor     graded, not flat: the top of a mountain a town once stood on. A rounded summit (about y52), two benches
            where streets could have run (y46 and y40), an old road ridge climbing from the tunnel's arrival to the
            summit, low relief on everything; the walls fall to about y34.
  ceiling   y72, lowered column by column so at least `rock_over_ceiling` blocks of natural rock stay between the
            ceiling and the ground above (the creek's bed included). The ceiling is a glowing false sky: sea lanterns
            behind light blue stained glass.
  light     light blocks (invisible, no collision) in a diamond lattice 10 blocks apart at floor+3: every point one
            block above a sapling reads at least 9 (cherry saplings grow at 9+), every spawn position at least 1
            (overworld monsters spawn only at block light 0). Measured in a sealed test chamber on the server.
  seal      water pockets in the rock (WorldPainter's underground water) inside the cavern and a 2-block shell are
            replaced with stone before anything is dug, so nothing floods.
  trees     cherry_vale's classes (cherry, birch, azalea) from the foliage object library, placed by spacing on a
            density field that thins on the benches and summit (the town's ground) and clears the arrival.
  tunnel    from a cave mouth on the trough flank down to the cavern at no more than 1:4, 5 wide and 5 tall, a stair
            at every step, lit so nothing spawns in it; and the approach trail from the nearest routed leg.
  biome     /fillbiome to minecraft:cherry_grove over the cavern volume, in its own function (not called by the others).

  python tools/cavern_plan.py --source-root <root> [--surface-world <stopped world>] [--install <server>/datapacks]
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

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "kits" / "structures" / "foliage"
LATTICE = 10
ROCK_OVER_CEILING = 24


def summit_floor(n, seed, arrival_local):
    """Floor top y over an n x n cavern, centre at (n/2, n/2)."""
    zz, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    u, v = xx - n / 2, zz - n / 2
    r = np.hypot(u, v * 1.08)
    f = 34 + 18 * (1 - smoothstep(22, 96, r))                         # the mountain top
    for level, r0, r1 in ((46, 44, 62), (40, 70, 84)):                 # benches a town's streets could follow
        w = smoothstep(r0, r0 + 4, r) * (1 - smoothstep(r1 - 4, r1, r))
        f = f * (1 - 0.85 * w) + level * 0.85 * w
    f = np.where(r < 30, np.maximum(f, 50 + 2 * (1 - smoothstep(0, 28, r))), f)   # a low crown on the summit plateau
    ax, az = arrival_local                                            # old road ridge from the arrival to the summit
    L = math.hypot(ax, az)
    t = np.clip((u * ax + v * az) / (L * L), 0, 1)
    d = np.hypot(u - t * ax, v - t * az)
    ramp = 38 + (1 - t) * 12
    f = np.where(d < 9, np.maximum(f * smoothstep(3, 9, d) + ramp * (1 - smoothstep(3, 9, d)), 0), f)
    f = f + 0.8 * np.tanh(unit_noise(n, 16, seed))
    return np.clip(np.rint(f), 33, 60).astype(int), r, d


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
    p.add_argument("--surface-world", default=None, help="stopped world: ground above the cavern read from region files")
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
    if a.surface_world:
        import world_heights
        g, _, _ = world_heights.extract(a.surface_world, (bx0, bz0, bx1, bz1))
        ground = lambda x, z: int(g[z - bz0, x - bx0])
        basis = "region files of %s" % a.surface_world
    else:
        ground = lambda x, z: int(math.floor(float(heights[z, x])))
        basis = "heightmap %s, floor(h): run again with --surface-world on the exported world before building" % world["heightmap"]["sha256"][:12]
    top = np.array([[ground(x, z) for x in range(x0, x1 + 1)] for z in range(z0, z1 + 1)])

    # tunnel: mouth on the city's surface site facing the trough, around the creek's head, into the cavern's
    # north-west corner
    fp = city["footprint"]
    mouth = (fp["max_x"], (fp["min_z"] + fp["max_z"]) // 2 - 10)
    arrival = (x0 + 12, z0 + 10)
    corner = (x0 + 12, z0 - 50)
    waypoints = [mouth, (mouth[0] + 70, corner[1]), corner, arrival]
    floor, r_field, ridge_d = summit_floor(n, a.seed, (arrival[0] - cx, arrival[1] - cz))
    ceiling = np.minimum(y_hi, top - ROCK_OVER_CEILING)
    report = {"generator": "tools/cavern_plan.py", "ground_basis": basis, "cavern": [x0, z0, x1, z1],
              "floor_y": {"min": int(floor.min()), "median": float(np.median(floor)), "max": int(floor.max())},
              "ceiling_y": {"min": int(ceiling.min()), "median": float(np.median(ceiling)), "max": int(ceiling.max()),
                            "columns_below_72": int((ceiling < y_hi).sum())},
              "headroom": {"min": int((ceiling - 2 - floor).min()), "median": float(np.median(ceiling - 2 - floor))},
              "rock_over_ceiling_min": int((top - ceiling).min()), "surface_above": [int(top.min()), int(top.max())]}
    fn = {}

    # 00 seal water pockets: cavern plus a 2-block shell, y_lo-2 .. y_hi+2
    cmds = ["# seal underground water around the cavern (tools/cavern_plan.py)"]
    for b in fill_boxes(x0 - 2, y_lo - 2, z0 - 2, x1 + 2, y_hi + 2, z1 + 2):
        cmds.append("fill %d %d %d %d %d %d minecraft:stone replace minecraft:water" % b)
    fn["00_seal"] = cmds

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

    # 20 floor and ceiling surfaces
    cmds = ["# floor: grass on dirt; ceiling: light blue glass under sea lanterns"]
    for j in range(n):
        i = 0
        while i < n:
            f_, c_ = floor[j, i], ceiling[j, i]
            k = i
            while k + 1 < n and floor[j, k + 1] == f_ and ceiling[j, k + 1] == c_:
                k += 1
            xa, xb, z = x0 + i, x0 + k, z0 + j
            cmds += ["fill %d %d %d %d %d %d minecraft:dirt" % (xa, f_ - 3, z, xb, f_ - 1, z),
                     "fill %d %d %d %d %d %d minecraft:grass_block" % (xa, f_, z, xb, f_, z),
                     "fill %d %d %d %d %d %d minecraft:light_blue_stained_glass" % (xa, c_ - 1, z, xb, c_ - 1, z),
                     "fill %d %d %d %d %d %d minecraft:sea_lantern" % (xa, c_, z, xb, c_, z)]
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
            trees.append({"object": o["name"], "group": group, "at": [wx, y, wz], "rotation": rot})
    fn["30_trees"] = cmds
    report["trees"] = {"count": len(trees), "by_group": {g_: sum(1 for t in trees if t["group"] == g_) for g_ in weights}}

    # 40 light lattice at floor+3, only into air (trees may occupy a point; the check afterwards finds dark spots)
    cmds, lights = ["# light lattice: diamond, 10 apart, floor+3, invisible"], 0
    for j in range(0, n):
        for i in range(0, n):
            if (i % LATTICE == 0 and j % LATTICE == 0) or (i % LATTICE == LATTICE // 2 and j % LATTICE == LATTICE // 2):
                cmds.append("setblock %d %d %d minecraft:light[level=15] keep" % (x0 + i, floor[j, i] + 3, z0 + j))
                lights += 1
    fn["40_light"] = cmds
    report["light_blocks"] = lights

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
    # 1: seal water around the corridor, 2: carve every station's air, 3: lay floor and stairs, so a later
    # station's carve cannot take out an earlier station's floor
    for xi, y, zi, _ in stations[::4]:
        cmds.append("fill %d %d %d %d %d %d minecraft:stone replace minecraft:water" % (xi - 4, y - 2, zi - 4, xi + 4, y + 7, zi + 4))
    for xi, y, zi, _ in stations:
        cmds.append("fill %d %d %d %d %d %d minecraft:air" % (xi - 2, y + 1, zi - 2, xi + 2, y + 5, zi + 2))
    prev_y = None
    for xi, y, zi, back in stations:
        cmds.append("fill %d %d %d %d %d %d minecraft:stone_bricks replace #minecraft:replaceable" % (xi - 2, y, zi - 2, xi + 2, y, zi + 2))
        if prev_y is not None and y < prev_y:
            cmds.append("fill %d %d %d %d %d %d minecraft:stone_brick_stairs[facing=%s] replace #minecraft:replaceable" % (xi - 2, y + 1, zi - 2, xi + 2, y + 1, zi + 2, back))
        prev_y = y
    # a light every 8 blocks: the floor descends, so the distance from a light to the floor grows faster than the
    # horizontal step. Measured at 20: 47 of 85 stations sat at block light 0, where monsters spawn
    for s in range(0, len(stations), 8):
        xi, y, zi, _ = stations[s]
        cmds.append("setblock %d %d %d minecraft:light[level=15] keep" % (xi, y + 3, zi))
    cover = [(s, ground(stations[s][0], stations[s][2]) - (stations[s][1] + 5)) for s in range(3, len(stations) - 3)]
    fn["50_tunnel"] = cmds
    report["tunnel"] = {"mouth": [mouth[0], mouth_y, mouth[1]], "arrival": [arrival[0], arr_y, arrival[1]], "waypoints": waypoints,
                        "length_blocks": total, "drop": drop, "grade": round(grade, 3), "max_grade": 0.25,
                        "rock_cover_over_tunnel": {"min": int(min(c for _, c in cover)) if cover else None,
                                                   "median": float(np.median([c for _, c in cover])) if cover else None,
                                                   "open_cut_blocks_from_mouth": next((s_ for s_, c in cover if c >= 3), None),
                                                   "every_20": [[s_, int(c)] for s_, c in cover[::20]]}}

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
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
        dest = Path(a.install) / out.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(out, dest)
        print("installed", dest)


if __name__ == "__main__":
    main()
