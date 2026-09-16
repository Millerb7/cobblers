#!/usr/bin/env python
"""Route 1's forest: a maze made of negative space.

The maze is not walls and it is not height. The trees are packed tight enough that you cannot see through them, and
a branching network of clear corridors is cut through the pack. The gap IS the path -- nothing is paved.

What makes it a maze is the branching, not the density: forks lead genuinely different ways, one loop rejoins, two
spurs dead-end, and at a fork you cannot tell which way is better. It is small on purpose. A first forest should be
briefly disorienting, not a labyrinth, and the world-tree sapling at its centre gives you something to orient by.

The barrier is line of sight, not collision. Trunks are ordinary single-block oak and birch; a player who squeezes
between two of them has found a shortcut, which is how Viridian Forest works too.

  python tools/maze_forest.py --source-root <root> [--apply]
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import numpy as np

import terrain as T
from place_town import rotate

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "kits" / "structures" / "foliage"
TILE = 200                               # 200x200 is 169 chunks, under forceload's 256-chunk limit
BOX = (1180, 4300, 1820, 5060)          # x0, z0, x1, z1
SAPLING = (1380, 4628)
MAZE_SPACING = 2.0                       # in the maze band: 1,427 stems/ha, a 7.0-block sightline
OUTER_SPACING = 6.0                      # beyond it, ordinary woodland so the maze has an edge
MAZE_BAND = 80                           # how far the dense pack reaches from the corridor network.
# 80 because the main path's zigzag legs are about 110 blocks apart, so 80 either side packs the gap between them
# solid -- you cannot cut the corner. Wider only adds trees: the sightline inside the band is 6.3 at 80 and 6.7 at
# 150, but the tree count goes 41,124 to 57,428.
CLEARING_R = 20                          # open ground around the sapling
EDGE_FEATHER = 3                         # blocks over which density ramps back up at a corridor edge
SEED = 20260916
SURFACE_WORLD = "C:/Users/wnd/Documents/github/cobblers-server/cobblers-10240"

# The network. Every corridor is a polyline of nodes plus a width; the gap is the path, so width is what the
# player walks. `kind` is only for the report.
# Paths are not all the same, on purpose. Some should feel obvious and some should not, so width, ground and light
# all say how much a path wants to be found:
#   obvious   the through route: 8 wide, trodden ground, lanterns at every fork. You can always get back to it.
#   ordinary  the loop and the mansion spur: 5 wide, lightly worn ground, no light
#   quiet     the dead ends: 3 wide, grass underfoot. Nothing says go here, which is what makes them a choice.
#   hidden    squeeze paths to secret glades: 2 wide, no ground change, no light, and they leave the corridors
#             where the pack is thickest, so you find one by pushing into the trees, not by following anything.
# Played first-cut feedback: corridors read too narrow and too alike, the south entrance was a gap between two
# birches behind tall grass, and there was nowhere to discover.
NETWORK = [
    {"id": "main", "kind": "through route", "tier": "obvious", "width": 8,
     "nodes": [(1468, 5052), (1436, 4944), (1504, 4856), (1396, 4768), (1380, 4648),
               (1472, 4556), (1540, 4444), (1572, 4300)]},
    {"id": "loop_east", "kind": "loop, rejoins main", "tier": "ordinary", "width": 5,
     "nodes": [(1504, 4856), (1616, 4812), (1664, 4688), (1600, 4592), (1472, 4556)]},
    # dead ends are short on purpose: a wrong turn has to cost seconds. At 4.3 blocks a second, 70-80 blocks in and
    # back out is about 35 seconds. The first cut ran 175 and 169, which was 80 seconds of being punished.
    {"id": "spur_west", "kind": "dead end", "tier": "quiet", "width": 3,
     "nodes": [(1436, 4944), (1388, 4922), (1368, 4908)]},
    {"id": "spur_northwest", "kind": "dead end", "tier": "quiet", "width": 3,
     "nodes": [(1396, 4768), (1348, 4750), (1330, 4728)]},
    {"id": "spur_mansion", "kind": "side path to the mansion", "tier": "ordinary", "width": 5,
     "nodes": [(1468, 5036), (1552, 5028), (1628, 5032)]},
    # hidden: each leaves the MIDDLE of a corridor segment, not a fork -- start one at a fork and it is just a
    # fourth visible way out. From mid-segment it is a slightly thinner patch of trees you have to decide to push into.
    {"id": "hidden_fern_glade", "kind": "hidden path", "tier": "hidden", "width": 2,
     "nodes": [(1470, 4900), (1540, 4918), (1590, 4940)]},
    {"id": "hidden_west_hollow", "kind": "hidden path", "tier": "hidden", "width": 2,
     "nodes": [(1388, 4708), (1320, 4776), (1260, 4840)]},
    {"id": "hidden_north_ring", "kind": "hidden path", "tier": "hidden", "width": 2,
     "nodes": [(1556, 4372), (1612, 4376), (1660, 4380)]},
]
MANSION = (1630, 5034)
MANSION_CLEARING_R = 22

# The south entrance is a flared mouth, 16 wide, narrowing to the 8-wide main path over 40 blocks, with lantern posts
# either side. The first cut entered through a 6-wide gap that read as a gap between two trees.
ENTRANCE = {"mouth": (1468, 5058), "into": (1466, 5018), "mouth_width": 16}

# Openings: the sapling clearing is the centre you orient by; glades are small rooms off the corridors;
# the secret glades are where the hidden paths end.
CLEARINGS = [
    {"id": "sapling", "at": SAPLING, "r": 20, "kind": "centre"},
    {"id": "mansion", "at": MANSION, "r": MANSION_CLEARING_R, "kind": "set piece"},
    {"id": "loop_glade", "at": (1664, 4688), "r": 12, "kind": "glade"},
    {"id": "bend_glade", "at": (1436, 4944), "r": 10, "kind": "glade"},
    {"id": "north_glade", "at": (1540, 4444), "r": 11, "kind": "glade"},
    {"id": "fern_glade", "at": (1590, 4940), "r": 9, "kind": "secret"},
    {"id": "west_hollow", "at": (1260, 4840), "r": 9, "kind": "secret"},
    {"id": "north_ring", "at": (1660, 4380), "r": 8, "kind": "secret"},
]
GROUND = {                                   # what the ground says, by tier (weights of a per-column mix)
    "obvious": {"minecraft:coarse_dirt": 40, "minecraft:dirt_path": 30, "minecraft:podzol": 15, None: 15},
    "ordinary": {"minecraft:coarse_dirt": 25, "minecraft:podzol": 20, None: 55},
    "quiet": {None: 100},
    "hidden": {None: 100},
}


def polyline_distance(shape, box, nodes):
    """Distance in blocks from every cell to a polyline."""
    x0, z0 = box[0], box[1]
    zz, xx = np.mgrid[0:shape[0], 0:shape[1]].astype(np.float32)
    wx, wz = xx + x0, zz + z0
    best = np.full(shape, 1e9, np.float32)
    for (ax, az), (bx, bz) in zip(nodes, nodes[1:]):
        vx, vz = bx - ax, bz - az
        L2 = float(vx * vx + vz * vz) or 1.0
        t = np.clip(((wx - ax) * vx + (wz - az) * vz) / L2, 0.0, 1.0)
        best = np.minimum(best, np.hypot(wx - (ax + vx * t), wz - (az + vz * t)))
    return best


def build_fields(box, seed=SEED):
    x0, z0, x1, z1 = box
    shape = (z1 - z0 + 1, x1 - x0 + 1)
    corridor = np.zeros(shape, np.float32)          # 1 inside a corridor, ramping to 0 at EDGE_FEATHER out
    for c in NETWORK:
        d = polyline_distance(shape, box, c["nodes"])
        half = c["width"] / 2.0
        corridor = np.maximum(corridor, np.clip((half + EDGE_FEATHER - d) / EDGE_FEATHER, 0.0, 1.0))
    for cl in CLEARINGS:
        d = polyline_distance(shape, box, [cl["at"], cl["at"]])
        corridor = np.maximum(corridor, np.clip((cl["r"] + EDGE_FEATHER - d) / EDGE_FEATHER, 0.0, 1.0))
    # the entrance: a mouth that narrows from mouth_width to the main path's width over its length
    (mx, mz), (ix, iz) = ENTRANCE["mouth"], ENTRANCE["into"]
    zz, xx = np.mgrid[0:shape[0], 0:shape[1]].astype(np.float32)
    wx, wz = xx + x0, zz + z0
    vx, vz = ix - mx, iz - mz
    L2 = float(vx * vx + vz * vz)
    t = np.clip(((wx - mx) * vx + (wz - mz) * vz) / L2, 0.0, 1.0)
    d = np.hypot(wx - (mx + vx * t), wz - (mz + vz * t))
    half = (ENTRANCE["mouth_width"] + (NETWORK[0]["width"] - ENTRANCE["mouth_width"]) * t) / 2.0
    corridor = np.maximum(corridor, np.clip((half + EDGE_FEATHER - d) / EDGE_FEATHER, 0.0, 1.0))
    # how far each cell is from the network, so the dense pack can be bounded and the maze has an edge
    near = np.full(shape, 1e9, np.float32)
    for c in NETWORK:
        near = np.minimum(near, polyline_distance(shape, box, c["nodes"]))
    band = np.clip((MAZE_BAND + 40 - near) / 40.0, 0.0, 1.0)     # 1 inside the band, fading over 40 blocks
    return 1.0 - corridor, band                      # density: 1 in the pack, 0 on the path


def poisson(density, spacing, rng, box):
    """Dart throwing at `spacing`, weighted by density."""
    h, w = density.shape
    cell = spacing / math.sqrt(2)
    gw, gh = int(math.ceil(w / cell)), int(math.ceil(h / cell))
    grid = -np.ones((gh, gw), int)
    pts = []
    tries = int(w * h / (spacing * spacing) * 6)
    cand = np.column_stack((rng.random(tries) * w, rng.random(tries) * h))
    for x, z in cand:
        ix, iz = int(x), int(z)
        if density[iz, ix] <= 0.02 or rng.random() > density[iz, ix]:
            continue
        gx, gz = int(x / cell), int(z / cell)
        ok = True
        for a in range(max(0, gz - 2), min(gh, gz + 3)):
            for b in range(max(0, gx - 2), min(gw, gx + 3)):
                j = grid[a, b]
                if j >= 0 and math.hypot(pts[j][0] - x, pts[j][1] - z) < spacing:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            grid[gz, gx] = len(pts)
            pts.append((x, z))
    return [(int(box[0] + x), int(box[1] + z)) for x, z in pts]


def sightline(stems, area_blocks, mean_eye_width):
    """The published metric: 1 / (stems per block * eye width)."""
    per_block = stems / area_blocks
    return 1.0 / (per_block * mean_eye_width) if per_block and mean_eye_width else None


def ascii_map(density, box, cols=96):
    x0, z0, x1, z1 = box
    h, w = density.shape
    rows = int(cols * h / w / 2)
    out = []
    for r in range(rows):
        line = ""
        for c in range(cols):
            zs, ze = int(r * h / rows), int((r + 1) * h / rows)
            xs, xe = int(c * w / cols), int((c + 1) * w / cols)
            v = density[zs:ze, xs:xe].mean()
            line += "#" if v > 0.85 else ("+" if v > 0.5 else ("." if v > 0.15 else " "))
        out.append(line)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--surface-world", default=None)
    p.add_argument("--install", default=None)
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    x0, z0, x1, z1 = BOX
    rng = np.random.default_rng(SEED)

    density, band = build_fields(BOX)
    lib = json.loads((ROOT / "kits/structures/foliage/library.json").read_text(encoding="utf-8"))["objects"]
    lib = list(lib.values()) if isinstance(lib, dict) else lib
    # the maze body: single-block trunks only, so the barrier is sight and not collision
    body = [o for o in lib if o["group"] in ("oak", "birch", "fancy_oak", "tall_birch") and o.get("eye_width", 1) <= 1.0]
    big = [o for o in lib if o["group"] in ("fancy_oak", "tall_birch") and o["height"] >= 12]
    print("body objects: %d (heights %d..%d, all eye_width 1.0)"
          % (len(body), min(o["height"] for o in body), max(o["height"] for o in body)))
    print("big-tree objects: %d (heights %d..%d)" % (len(big), min(o["height"] for o in big), max(o["height"] for o in big)))

    # Two regimes. Dart throwing only reaches about 57% of grid packing, so a 3.5 min-distance gives 468 stems/ha
    # and a 21-block sightline -- barely tighter than the spruce thicket, which is not a maze. 2.0 gets there.
    maze_field = density * band
    outer_field = density * (1.0 - band)
    maze = poisson(maze_field, MAZE_SPACING, rng, BOX)
    outer = poisson(outer_field, OUTER_SPACING, np.random.default_rng(SEED + 3), BOX)
    maze_area, outer_area = float(maze_field.sum()), float(outer_field.sum())
    mean_eye = float(np.mean([o.get("eye_width", 1.0) for o in body]))
    s = sightline(len(maze), maze_area, mean_eye)
    s_out = sightline(len(outer), outer_area, mean_eye)
    print("\nmaze band  : %6d trunks over %5.2f ha, %5.0f stems/ha -> sightline %5.1f blocks"
          % (len(maze), maze_area / 1e4, len(maze) / (maze_area / 1e4), s))
    print("outer wood : %6d trunks over %5.2f ha, %5.0f stems/ha -> sightline %5.1f blocks"
          % (len(outer), outer_area / 1e4, len(outer) / (outer_area / 1e4), s_out))
    print("reference  : spruce thicket 129 stems/ha -> 26 blocks; foothill mixed 55 -> 88")
    stems = maze + outer

    corridor_area = float((1.0 - density).sum())
    print("corridors: %.2f ha open of a %.2f ha box (%.1f%%)"
          % (corridor_area / 1e4, density.size / 1e4, 100 * corridor_area / density.size))

    print("\nnetwork:")
    total_len = 0.0
    for c in NETWORK:
        L = sum(math.hypot(b[0] - a_[0], b[1] - a_[1]) for a_, b in zip(c["nodes"], c["nodes"][1:]))
        total_len += L
        print("   %-19s %-9s %-26s %d wide, %4.0f blocks  %s -> %s"
              % (c["id"], c["tier"], c["kind"], c["width"], L, c["nodes"][0], c["nodes"][-1]))
    print("   total corridor length %.0f blocks" % total_len)
    print("\n   entrance: %d-wide mouth at %s narrowing to %d over %.0f blocks"
          % (ENTRANCE["mouth_width"], ENTRANCE["mouth"], NETWORK[0]["width"],
             math.hypot(ENTRANCE["into"][0] - ENTRANCE["mouth"][0], ENTRANCE["into"][1] - ENTRANCE["mouth"][1])))
    print("   openings:")
    for cl in CLEARINGS:
        print("      %-12s %-9s at %s radius %d" % (cl["id"], cl["kind"], cl["at"], cl["r"]))

    # forks: nodes shared by more than one corridor
    from collections import Counter
    ends = Counter()
    for c in NETWORK:
        for nd in c["nodes"]:
            ends[nd] += 1
    forks = [k for k, v in ends.items() if v > 1]
    print("\n   forks (a node two corridors share): %d" % len(forks))
    for f in sorted(forks):
        who = [c["id"] for c in NETWORK if f in c["nodes"]]
        print("      %s  %s" % (f, " + ".join(who)))
    dead = [c for c in NETWORK if c["kind"] == "dead end"]
    print("   dead ends: %d  %s" % (len(dead), [c["nodes"][-1] for c in dead]))
    loops = [c for c in NETWORK if "loop" in c["kind"]]
    print("   loops: %d  %s" % (len(loops), [(c["nodes"][0], c["nodes"][-1]) for c in loops]))

    # big trees, scattered through the pack, well clear of the corridors
    bigpts = []
    for x, z in poisson(np.where(density > 0.9, 1.0, 0.0), 78.0, np.random.default_rng(SEED + 5), BOX):
        bigpts.append((x, z))
    print("\n   big trees scattered through the pack: %d (spacing 78)" % len(bigpts))

    print("\n   sapling clearing: %s radius %d   mansion: %s radius %d, %.0f blocks off the main path"
          % (SAPLING, CLEARING_R, MANSION, MANSION_CLEARING_R,
             min(math.hypot(MANSION[0] - n[0], MANSION[1] - n[1]) for n in NETWORK[0]["nodes"])))

    print("\nplan (# pack, + edge, . thin, space = corridor); north is up, the route enters bottom-centre:")
    for line in ascii_map(density, BOX):
        print("   |" + line + "|")

    rep = {"box": BOX, "maze_spacing": MAZE_SPACING, "outer_spacing": OUTER_SPACING, "maze_band": MAZE_BAND,
           "maze_trunks": len(maze), "outer_trunks": len(outer), "stems": len(stems),
           "maze_sightline_blocks": s, "outer_sightline_blocks": s_out, "mean_eye_width": mean_eye,
           "corridor_open_ha": corridor_area / 1e4, "network": NETWORK,
           "forks": [list(f) for f in sorted(forks)],
           "dead_ends": [list(c["nodes"][-1]) for c in dead],
           "loops": [[list(c["nodes"][0]), list(c["nodes"][-1])] for c in loops],
           "sapling": list(SAPLING), "mansion": list(MANSION), "big_trees": len(bigpts)}

    # Seat every trunk on the world's own ground and write the placement in TILES. A 200x200 tile is 169 chunks,
    # under the 256 a single forceload box accepts -- a limit whose failure shows only in the command's reply, and
    # which silently swallowed two earlier town-prep runs.
    import world_heights as WH
    ground, _, _ = WH.extract(a.surface_world or SURFACE_WORLD, BOX)
    rng2 = np.random.default_rng(SEED + 11)
    tiles, placed = {}, 0
    for pts, pool in ((maze, body), (outer, body), (bigpts, big)):
        for (wx, wz) in pts:
            o = pool[int(rng2.integers(len(pool)))]
            rot = ("none", "clockwise_90", "180", "counterclockwise_90")[int(rng2.integers(4))]
            ox, oy, oz = o["origin"]
            rx, rz = rotate(ox, oz, rot)
            gy = int(ground[wz - BOX[1], wx - BOX[0]])
            key = ((wx - BOX[0]) // TILE, (wz - BOX[1]) // TILE)
            tiles.setdefault(key, []).append(
                "place template cobblers:route1/foliage/%s %d %d %d %s none 1.0 0"
                % (o["file"][:-4], wx - rx, gy + 1 - oy, wz - rz, rot))
            placed += 1
    print("\nplacement: %d objects over %d tiles of %d blocks" % (placed, len(tiles), TILE))

    out = ROOT / "build" / "datapacks" / "cobblers_route1"
    if out.exists():
        shutil.rmtree(out)
    used = set()
    for key, cmds in sorted(tiles.items()):
        f = out / "data" / "cobblers" / "function" / "route1" / ("tile_%d_%d.mcfunction" % key)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("\n".join(["# Route 1 forest tile %d %d" % key] + cmds) + "\n", encoding="utf-8")
        for c in cmds:
            used.add(c.split()[2].rsplit("/", 1)[-1] + ".nbt")
    for o in lib:
        if o["file"] in used:
            dest = out / "data" / "cobblers" / "structure" / "route1" / "foliage" / o["file"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(LIBRARY / o["file"], dest)
    (out / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "Cobblers: the Route 1 maze forest (tools/maze_forest.py)"}},
        indent=2) + "\n", encoding="utf-8")
    print("wrote %s (%d tile functions, %d distinct objects)" % (out.relative_to(ROOT), len(tiles), len(used)))
    rep["tiles"] = {"%d_%d" % k: len(v) for k, v in sorted(tiles.items())}
    rep["objects_placed"] = placed

    (ROOT / "derived" / "sites").mkdir(parents=True, exist_ok=True)
    (ROOT / "derived" / "sites" / "route1_forest.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("wrote derived/sites/route1_forest.json")
    if a.install:
        dest = Path(a.install) / out.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(out, dest)
        print("installed %s" % dest)


if __name__ == "__main__":
    main()
