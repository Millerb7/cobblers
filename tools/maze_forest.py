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
    # Played second cut: better, but the main path still read as one straight line -- its legs ran 110-150 blocks,
    # so inside an 8-wide corridor you looked down a long tunnel, and there were four decisions in 900 blocks. The
    # route is now BRAIDED: short obvious stretches, then a split into two comparable ordinary paths that rejoin.
    # Both sides of a braid are the same width and the same ground on purpose, so a split is a real choice rather than
    # a highway with a side road; neither is wrong, and each passes something the other does not.
    #
    #   entrance -> A  obvious
    #   A => B         braid 1: west past the bend, east past a spur to the fern glade
    #   B -> C -> D    obvious, a dead end off C
    #   D => E         braid 2: west through the sapling clearing, east past a dead end
    #   E -> F         obvious
    #   F => G         braid 3: north-west short and direct, north-east longer with a dead end
    #   G -> H -> exit obvious
    # NETWORK[0] is the entrance stretch: the flare narrows to its width.
    {"id": "entry", "kind": "entrance stretch", "tier": "obvious", "width": 8,
     "nodes": [(1468, 5052), (1460, 5010)]},
    {"id": "braid1_west", "kind": "braid", "tier": "ordinary", "width": 5,
     "nodes": [(1460, 5010), (1420, 4980), (1400, 4935), (1460, 4895)]},
    {"id": "braid1_east", "kind": "braid", "tier": "ordinary", "width": 5,
     "nodes": [(1460, 5010), (1500, 4975), (1515, 4930), (1460, 4895)]},
    {"id": "mid_1", "kind": "obvious stretch", "tier": "obvious", "width": 7,
     "nodes": [(1460, 4895), (1440, 4850), (1470, 4800)]},
    {"id": "braid2_west", "kind": "braid, through the sapling", "tier": "ordinary", "width": 5,
     "nodes": [(1470, 4800), (1410, 4770), (1385, 4700), (1380, 4648), (1420, 4590)]},
    {"id": "braid2_east", "kind": "braid", "tier": "ordinary", "width": 5,
     "nodes": [(1470, 4800), (1510, 4760), (1500, 4690), (1470, 4640), (1420, 4590)]},
    {"id": "mid_2", "kind": "obvious stretch", "tier": "obvious", "width": 7,
     "nodes": [(1420, 4590), (1470, 4550)]},
    {"id": "braid3_northwest", "kind": "braid", "tier": "ordinary", "width": 5,
     "nodes": [(1470, 4550), (1480, 4500), (1510, 4460), (1540, 4420)]},
    {"id": "braid3_northeast", "kind": "braid", "tier": "ordinary", "width": 5,
     "nodes": [(1470, 4550), (1540, 4540), (1580, 4490), (1540, 4420)]},
    {"id": "exit", "kind": "exit stretch", "tier": "obvious", "width": 8,
     "nodes": [(1540, 4420), (1560, 4370), (1572, 4300)]},
    # dead ends: short on purpose -- 70-75 blocks in and back out is about 35 seconds at 4.3 blocks a second
    {"id": "dead_c", "kind": "dead end", "tier": "quiet", "width": 3,
     "nodes": [(1440, 4850), (1390, 4838), (1370, 4825)]},
    {"id": "dead_braid2", "kind": "dead end", "tier": "quiet", "width": 3,
     "nodes": [(1500, 4690), (1550, 4700), (1570, 4712)]},
    {"id": "dead_braid3", "kind": "dead end", "tier": "quiet", "width": 3,
     "nodes": [(1580, 4490), (1630, 4482), (1650, 4478)]},
    {"id": "spur_mansion", "kind": "side path to the mansion", "tier": "ordinary", "width": 5,
     "nodes": [(1466, 5036), (1552, 5028), (1628, 5032)]},
    # hidden: each leaves the MIDDLE of a corridor segment, never a fork, so it is a thinner patch of trees you
    # decide to push into rather than one more visible way out
    {"id": "hidden_fern_glade", "kind": "hidden path", "tier": "hidden", "width": 2,
     "nodes": [(1508, 4952), (1560, 4945), (1600, 4940)]},
    {"id": "hidden_west_hollow", "kind": "hidden path", "tier": "hidden", "width": 2,
     "nodes": [(1398, 4735), (1320, 4770), (1260, 4800)]},
    {"id": "hidden_north_ring", "kind": "hidden path", "tier": "hidden", "width": 2,
     "nodes": [(1556, 4390), (1612, 4386), (1660, 4380)]},
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
    # small glades where the braids rejoin, so each decision has a room on the far side of it
    {"id": "braid1_join", "at": (1460, 4895), "r": 10, "kind": "glade"},
    {"id": "braid2_join", "at": (1420, 4590), "r": 11, "kind": "glade"},
    {"id": "braid3_join", "at": (1540, 4420), "r": 10, "kind": "glade"},
    {"id": "fern_glade", "at": (1600, 4940), "r": 9, "kind": "secret"},
    {"id": "west_hollow", "at": (1260, 4800), "r": 9, "kind": "secret"},
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


def path_dressing(ground, box, seed=SEED):
    """Ground, cleared plants and lanterns that say which paths want to be found. Commands keyed by tile.

    obvious and ordinary paths are cleared of two-block plants at eye height and given worn ground; quiet and hidden
    paths are left exactly as the forest grew them, which is the point. Lanterns go at every fork on the through
    route and either side of the south entrance, on posts placed unconditionally -- the tunnel taught that `keep`
    silently skips a cell something else already occupies.
    """
    x0, z0, x1, z1 = box
    shape = (z1 - z0 + 1, x1 - x0 + 1)
    rank = {"hidden": 0, "quiet": 1, "ordinary": 2, "obvious": 3}
    best = np.full(shape, -1, np.int8)                # the most obvious tier covering each cell
    for c in NETWORK:
        d = polyline_distance(shape, box, c["nodes"])
        inside = d <= c["width"] / 2.0
        best = np.where(inside & (rank[c["tier"]] > best), rank[c["tier"]], best)
    # the entrance flare counts as obvious
    (mx, mz), (ix, iz) = ENTRANCE["mouth"], ENTRANCE["into"]
    zz, xx = np.mgrid[0:shape[0], 0:shape[1]].astype(np.float32)
    wx, wz = xx + x0, zz + z0
    vx, vz = ix - mx, iz - mz
    t = np.clip(((wx - mx) * vx + (wz - mz) * vz) / float(vx * vx + vz * vz), 0.0, 1.0)
    dd = np.hypot(wx - (mx + vx * t), wz - (mz + vz * t))
    half = (ENTRANCE["mouth_width"] + (NETWORK[0]["width"] - ENTRANCE["mouth_width"]) * t) / 2.0
    best = np.where(dd <= half, rank["obvious"], best)

    inv = {v: k for k, v in rank.items()}
    rng = np.random.default_rng(seed + 29)
    roll = rng.random(shape)
    tiles = {}
    counts = {"cleared": 0, "ground": 0, "lanterns": 0}

    def put(wxv, wzv, cmd):
        key = ((wxv - x0) // TILE, (wzv - z0) // TILE)
        tiles.setdefault(key, []).append(cmd)

    zs, xs = np.where(best >= rank["ordinary"])
    for zi, xi in zip(zs, xs):
        wxv, wzv = int(x0 + xi), int(z0 + zi)
        gy = int(ground[zi, xi])
        tier = inv[int(best[zi, xi])]
        # clear eye height: two-block plants are the wall; this also takes short plants off a worn path
        put(wxv, wzv, "fill %d %d %d %d %d %d minecraft:air replace #minecraft:replaceable"
            % (wxv, gy + 1, wzv, wxv, gy + 2, wzv))
        counts["cleared"] += 1
        acc, r = 0.0, roll[zi, xi] * 100
        for block, w in GROUND[tier].items():
            acc += w
            if r < acc:
                if block:
                    put(wxv, wzv, "setblock %d %d %d %s" % (wxv, gy, wzv, block))
                    counts["ground"] += 1
                break

    def post(px, pz):
        gy = int(ground[pz - z0, px - x0])
        put(px, pz, "setblock %d %d %d minecraft:oak_fence" % (px, gy + 1, pz))
        put(px, pz, "setblock %d %d %d minecraft:lantern[hanging=false]" % (px, gy + 2, pz))
        counts["lanterns"] += 1

    # A post at every fork -- a node two or more visible corridors share -- just off the edge of the most obvious
    # corridor through it. Both perpendicular sides are tried and the post goes on whichever is further from every
    # corridor, so it marks the fork without landing in the mouth of a branch. The network is braided, so there is no
    # single "main" polyline to hang these off any more.
    visible = [c for c in NETWORK if c["tier"] != "hidden"]
    from collections import Counter
    uses = Counter(n for c in visible for n in c["nodes"])
    rank_of = {"obvious": 3, "ordinary": 2, "quiet": 1}
    for node, k in sorted(uses.items()):
        if k < 2:
            continue
        host = max((c for c in visible if node in c["nodes"]), key=lambda c: (rank_of[c["tier"]], c["width"]))
        i = host["nodes"].index(node)
        a_ = host["nodes"][max(0, i - 1)]
        b_ = host["nodes"][min(len(host["nodes"]) - 1, i + 1)]
        tx, tz = b_[0] - a_[0], b_[1] - a_[1]
        L = math.hypot(tx, tz) or 1.0
        nx, nz = -tz / L, tx / L
        off = host["width"] / 2.0 + 1.5
        best_pt, best_clear = None, -1.0
        for sgn in (1, -1):
            px = int(round(node[0] + sgn * nx * off))
            pz = int(round(node[1] + sgn * nz * off))
            if not (x0 <= px <= x1 and z0 <= pz <= z1):
                continue
            clear = min(polyline_distance((1, 1), (px, pz, px, pz), c["nodes"])[0, 0] - c["width"] / 2.0
                        for c in visible)
            if clear > best_clear:
                best_pt, best_clear = (px, pz), clear
        if best_pt:
            post(*best_pt)
    half_mouth = ENTRANCE["mouth_width"] / 2.0 + 1.5
    post(int(round(mx - half_mouth)), mz)
    post(int(round(mx + half_mouth)), mz)
    return tiles, counts


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
    loops = [c for c in NETWORK if "loop" in c["kind"] or c["kind"].startswith("braid")]
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
    # The centrepiece: one world-tree sapling in the sapling clearing, trunk centred on SAPLING. It had been sized
    # but never placed -- the clearing stood empty -- so the forest now places its own. The prefab comes from
    # tools/tree_grove.py (tier "sapling") through the kits datapack, which must be installed first.
    side = json.loads((ROOT / "kits/structures/prefabs/trees/tree_town/sapling_oak_a.json").read_text(encoding="utf-8"))
    sox, soy, soz = side["trunk_origin"]
    c = side["habitat"]["trunk"][0] // 2
    sgy = int(ground[SAPLING[1] - BOX[1], SAPLING[0] - BOX[0]])
    sx, sz = SAPLING[0] - c - sox, SAPLING[1] - c - soz            # rotation none: builder (c, c) lands on SAPLING
    skey = ((SAPLING[0] - BOX[0]) // TILE, (SAPLING[1] - BOX[1]) // TILE)
    tiles.setdefault(skey, []).append("place template %s %d %d %d none none 1.0 0"
                                      % (side["template_id"], sx, sgy + 1 - soy, sz))
    rep["sapling_placed"] = {"at": list(SAPLING), "ground_y": sgy, "height": side["habitat"]["height"],
                             "top_y": sgy + 1 + side["habitat"]["height"]}
    print("sapling: %s at %s, ground y%d, top y%d"
          % (side["template_id"], SAPLING, sgy, sgy + 1 + side["habitat"]["height"]))

    # path dressing runs after the trees in each tile, so a tree cannot land on a lantern post
    dress, dcounts = path_dressing(ground, BOX)
    for key, cmds in dress.items():
        tiles.setdefault(key, []).extend(cmds)
    print("path dressing: %d columns cleared at eye height, %d given worn ground, %d lantern posts"
          % (dcounts["cleared"], dcounts["ground"], dcounts["lanterns"]))

    out = ROOT / "build" / "datapacks" / "cobblers_route1"
    if out.exists():
        shutil.rmtree(out)
    used = set()
    for key, cmds in sorted(tiles.items()):
        f = out / "data" / "cobblers" / "function" / "route1" / ("tile_%d_%d.mcfunction" % key)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("\n".join(["# Route 1 forest tile %d %d" % key] + cmds) + "\n", encoding="utf-8")
        for c in cmds:
            if c.startswith("place template"):        # dressing commands share the tile but are not objects
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
