#!/usr/bin/env python
"""The old mine: a hill west of Route 1 at (1332, 4120) whose east face opens into a worked-out mineshaft and a cave.

The owner asked for it on 2026-09-24 to give the ground between Route 1 and the western woods a reason to walk to:
the route passes 262 blocks east (its nearest walked point is (1594, 4119)), and nothing else is recorded within 250
blocks. It is written like the mansion: an earthwork on a settlement of its own, `route1_old_mine`, in
data/placements.json, so the re-application builds it with the towns (R8) and tools/town_audit.py replays and checks
every block it writes.

  the hill      an irregular dome about 48 x 40 blocks and 16 high on the heightmap's ground (tools/ground.py, rounded,
                never a world's surface): grass where it is gentle, bare stone and andesite where it is steep, three
                spruces near the top and a few boulders on the flanks. Everything above the ground inside it and a
                margin round it is cleared first, so no painted tree is left sticking out of a slope
  the adit      a 3-wide, 4-high level cut into the east face at ground level, walked from a notch in the slope: a
                spruce portal, timber sets (fence posts and a plank cap) every four blocks, the old track's gravel bed
                and sleepers down the middle (the rails were taken up), lanterns under the caps
  the incline   stone stairs down eight blocks westward, the full width
  the cave      a dripstone chamber under the hill's west half, walled in stone, andesite and tuff with copper and
                calcite showing, a mud hollow at its west end, two old timber sets, the track bed's end at a buffer, and
                the mine's find (data/rewards.json r1_old_mine: a barrel, scenery; the reward is an advancement)

Lanterns are close enough that nothing walkable inside is at block light 0 (tools/light_plan.py checks places under a
roof); there are no hostile mobs in this pack (docs/STATE.md), so the light is for looks. No block here is a spawn
condition: no coal or iron ore, no rail and no water (rail draws rolycoly, carkol and coalossal, water bidoof,
bibarel and blastoise, coal and iron ore rolycoly, aron, aggron and alolan geodude: data/spawn_blocks.json); a Route 1
cave drawing any of them is a balance decision, not dressing. Nor cobweb, white or yellow carpet or bed.

  python tools/route1_old_mine.py --source-root <root>     # writes the settlement and its earthwork
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import ground as G

ROOT = Path(__file__).resolve().parent.parent
SID = "route1_old_mine"
CENTRE = (1332, 4120)
PEAK = (1329, 4118)                  # a little north-west of the centre, so the east face the adit enters is the long one
RX, RZ, HEIGHT = 24, 20, 16          # the dome's half-widths and its rise at the peak
CLEAR_MARGIN = 5                     # cleared of painted trees round the hill
Z_AXIS = 4120                        # the adit's centre line, running west from the portal
PORTAL_X = 1347                      # the portal's outer face; the notch runs east from it to the hill's foot
ADIT_END = 1334                      # the level's last cell; the incline starts west of it
DROP = 8                             # the incline's fall
CAVE = (1316, 4120)                  # the chamber's centre, under the hill's west half, clear of the incline
CAVE_R = (9.0, 8.0)                  # its half-widths, x and z
CAVE_H = 8                           # its height above its floor at the middle
SLEEPER = "minecraft:spruce_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]"
TRAIL = [(1357, 4120), (1366, 4121), (1374, 4123)]   # the carts' old way out of the notch, toward Route 1


def h32(*v):
    """A deterministic mix for materials and scatter."""
    x = 0
    for i, t in enumerate(v):
        x ^= (int(t) * (73856093, 19349663, 83492791, 2654435761)[i % 4]) & 0xFFFFFFFF
    x = (x ^ (x >> 13)) * 0x5BD1E995 & 0xFFFFFFFF
    return x ^ (x >> 15)


def rise(x, z):
    """The hill's height above the ground at (x, z): 0 outside it."""
    dx, dz = x - PEAK[0], z - PEAK[1]
    th = math.atan2(dz, dx)
    wobble = 1 + 0.10 * math.sin(3 * th + 1.3) + 0.06 * math.sin(5 * th + 0.4) + 0.04 * math.sin(8 * th + 2.1)
    d = math.hypot(dx / RX, dz / RZ) / wobble
    if d >= 1:
        return 0
    shoulder = 0.18 * max(0.0, 1 - math.hypot((x - 1320) / 9, (z - 4128) / 8))     # a second, lower top south-west
    return int(round(HEIGHT * ((1 + math.cos(math.pi * d)) / 2) ** 0.85 + HEIGHT * shoulder * (1 - d)))


def rock(x, y, z):
    k = h32(x, y, z, 7) % 20
    return ("minecraft:andesite" if k < 5 else "minecraft:tuff" if k < 7 else "minecraft:cobblestone" if k < 8
            else "minecraft:stone")


def wall(x, y, z):
    """A cave wall: rock, and now and then copper the miners left and a calcite vein. No coal or iron ore: both decide
    spawns (#minecraft:coal_ores draws rolycoly and carkol, #minecraft:iron_ores aron, aggron and alolan geodude,
    data/spawn_blocks.json), and a Route 1 cave drawing them is a balance decision, not dressing."""
    k = h32(x, y, z, 11) % 60
    if k < 3:
        return "minecraft:copper_ore"
    if k == 3:
        return "minecraft:dripstone_block"      # not gravel: a wall cell may be a ceiling, and gravel falls (staging)
    if k == 4:
        return "minecraft:calcite"
    return rock(x, y, z)


def plan(g):
    """(top, cols): the hill's surface height per column it raises, and the columns to clear."""
    top = {}
    for x in range(PEAK[0] - RX - 8, PEAK[0] + RX + 9):
        for z in range(PEAK[1] - RZ - 8, PEAK[1] + RZ + 9):
            r = rise(x, z)
            if r > 0:
                top[(x, z)] = g(x, z) + r
    clear = set()
    for (x, z) in top:
        for dx in range(-CLEAR_MARGIN, CLEAR_MARGIN + 1):
            for dz in range(-CLEAR_MARGIN, CLEAR_MARGIN + 1):
                clear.add((x + dx, z + dz))
    return top, clear


def build(g):
    c = ["# the old mine: a hill with a mineshaft in its east face and a cave under it (tools/route1_old_mine.py)"]
    fill = lambda a, b, blk: c.append("fill %d %d %d %d %d %d %s" % (a[0], a[1], a[2], b[0], b[1], b[2], blk))
    sb = lambda x, y, z, blk: c.append("setblock %d %d %d %s" % (x, y, z, blk))
    top, clear = plan(g)
    # ---- the site: every painted tree and plant above the ground in and round the hill
    for z in sorted({z for _, z in clear}):
        xs = sorted(x for x, zz in clear if zz == z)
        run = [xs[0]]
        for x in xs[1:] + [None]:
            if x is not None and x == run[-1] + 1 and g(x, z) == g(run[0], z):
                run.append(x)
                continue
            fill((run[0], g(run[0], z) + 1, z), (run[-1], g(run[0], z) + 30, z), "minecraft:air")
            if x is not None:
                run = [x]
    # ---- the hill: stone, then two of dirt, then its skin; bare rock where the slope is steep
    for (x, z), t in sorted(top.items()):
        base = g(x, z)
        near = [top.get((x + a, z + b), g(x + a, z + b)) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        steep = max(abs(t - n) for n in near)
        if t - 3 > base:
            fill((x, base + 1, z), (x, t - 3, z), "minecraft:stone")
        if steep >= 3:
            for y in range(max(base + 1, t - 2), t + 1):
                sb(x, y, z, rock(x, y, z))
            continue
        if t - 1 > base:
            fill((x, max(base + 1, t - 2), z), (x, t - 1, z), "minecraft:dirt")
        k = h32(x, z, 3) % 14
        skin = ("minecraft:coarse_dirt" if steep == 2 and k < 5 else "minecraft:gravel" if steep == 2 and k < 7
                else "minecraft:podzol" if k == 0 else "minecraft:grass_block[snowy=false]")
        sb(x, t, z, skin)
    # ---- the cave: a stone shell, then the chamber hollowed out of it, walls dressed afterwards
    floor = g(PORTAL_X + 1, Z_AXIS) - DROP              # the chamber's floor block; feet stand at floor + 1
    cells = set()
    for x in range(int(CAVE[0] - CAVE_R[0]) - 1, int(CAVE[0] + CAVE_R[0]) + 2):
        for z in range(int(CAVE[1] - CAVE_R[1]) - 1, int(CAVE[1] + CAVE_R[1]) + 2):
            th = math.atan2(z - CAVE[1], x - CAVE[0])
            d = math.hypot((x - CAVE[0]) / CAVE_R[0], (z - CAVE[1]) / CAVE_R[1]) / (1 + 0.12 * math.sin(4 * th + 0.7))
            if d >= 1:
                continue
            ceil = floor + 1 + int(round(CAVE_H * math.sqrt(1 - d * d)))
            for y in range(floor + 1, max(floor + 3, ceil) + 1):
                cells.add((x, y, z))
    shell = set()
    for (x, y, z) in cells:
        for a in (-2, -1, 0, 1, 2):
            for b in (-2, -1, 0, 1, 2):
                for e in (-1, 0, 1, 2):
                    q = (x + a, y + e, z + b)
                    if q not in cells:
                        shell.add(q)
    for (x, z) in sorted({(x, z) for x, _, z in shell | cells}):
        ys = [y for (xx, y, zz) in shell | cells if xx == x and zz == z]
        roof = top.get((x, z), g(x, z)) - 3                  # never into the hill's skin or the ground's
        lo, hi = min(ys), min(max(ys), roof)
        if hi >= lo:
            fill((x, lo, z), (x, hi, z), "minecraft:stone")
    for (x, y, z) in sorted(shell):
        if any((x + a, y + e, z + b) in cells for a, e, b in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))):
            if y <= top.get((x, z), g(x, z)) - 3:
                sb(x, y, z, wall(x, y, z))
    for (x, z) in sorted({(x, z) for x, _, z in cells}):                            # hollowed a column at a time
        ys = [y for (xx, y, zz) in cells if xx == x and zz == z]
        fill((x, min(ys), z), (x, max(ys), z), "minecraft:air")
    # ---- the notch and the adit: cut from the hill's foot west into the face, at ground level
    feet = g(PORTAL_X + 1, Z_AXIS) + 1
    east_foot = max(x for (x, z) in top if z == Z_AXIS) + 1
    for x in range(PORTAL_X, east_foot + 1):                                        # the notch, open to the sky
        fill((x, feet, Z_AXIS - 2), (x, feet + 20, Z_AXIS + 2), "minecraft:air")
        for z in range(Z_AXIS - 2, Z_AXIS + 3):                                     # its floor: earth, never loose
            if g(x, z) + 1 <= feet - 2:                                             # gravel over lower ground
                fill((x, g(x, z) + 1, z), (x, feet - 2, z), "minecraft:dirt")
            sb(x, feet - 1, z, "minecraft:coarse_dirt")
    fill((ADIT_END, feet, Z_AXIS - 1), (PORTAL_X - 1, feet + 3, Z_AXIS + 1), "minecraft:air")
    fill((ADIT_END, feet - 1, Z_AXIS - 1), (PORTAL_X - 1, feet - 1, Z_AXIS + 1), "minecraft:gravel")
    fill((ADIT_END, feet + 4, Z_AXIS - 1), (PORTAL_X - 1, feet + 4, Z_AXIS + 1), "minecraft:stone")   # a roof, always
    for x in range(ADIT_END, PORTAL_X):
        for z in (Z_AXIS - 2, Z_AXIS + 2):
            fill((x, feet - 1, z), (x, feet + 4, z), rock(x, feet, z))                                 # the level's walls
    # the portal: spruce posts and a beam, in the face
    for z in (Z_AXIS - 2, Z_AXIS + 2):
        fill((PORTAL_X, feet, z), (PORTAL_X, feet + 3, z), "minecraft:spruce_log[axis=y]")
    fill((PORTAL_X, feet + 4, Z_AXIS - 2), (PORTAL_X, feet + 4, Z_AXIS + 2), "minecraft:spruce_log[axis=z]")
    fill((PORTAL_X + 1, feet + 4, Z_AXIS - 2), (PORTAL_X + 1, feet + 4, Z_AXIS + 2), "minecraft:spruce_slab[type=bottom]")
    # timber sets every four blocks, a lantern under each cap
    for x in range(PORTAL_X - 1, ADIT_END - 1, -4):
        for z in (Z_AXIS - 1, Z_AXIS + 1):
            fill((x, feet, z), (x, feet + 2, z), "minecraft:spruce_fence")
        fill((x, feet + 3, Z_AXIS - 1), (x, feet + 3, Z_AXIS + 1), "minecraft:spruce_planks")
        sb(x, feet + 2, Z_AXIS, "minecraft:lantern[hanging=true]")
    # the old track: its rails taken up, its sleepers left on the bed, from outside the portal to the incline
    for x in range(ADIT_END, PORTAL_X + 4, 2):
        sb(x, feet, Z_AXIS, SLEEPER)
    # ---- the incline: stairs down westward, the full width
    for i in range(1, DROP + 1):
        x, y = ADIT_END - i, feet - i
        fill((x, y, Z_AXIS - 1), (x, y + 4, Z_AXIS + 1), "minecraft:air")
        fill((x, y + 5, Z_AXIS - 2), (x, y + 5, Z_AXIS + 2), "minecraft:stone")
        for z in (Z_AXIS - 2, Z_AXIS + 2):
            fill((x, y - 1, z), (x, y + 5, z), rock(x, y, z))
        fill((x, y - 1, Z_AXIS - 1), (x, y - 1, Z_AXIS + 1), "minecraft:stone")
        for z in (Z_AXIS - 1, Z_AXIS, Z_AXIS + 1):
            sb(x, y, z, "minecraft:cobblestone_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]")
        if i % 4 == 0:
            sb(x, y + 3, Z_AXIS, "minecraft:lantern[hanging=true]")
            sb(x, y + 4, Z_AXIS, "minecraft:spruce_planks")
    # the incline's foot opens into the chamber: clear the two cells between it and the cave's edge
    bottom = feet - DROP
    for x in range(ADIT_END - DROP - 3, ADIT_END - DROP):
        fill((x, bottom, Z_AXIS - 1), (x, bottom + 3, Z_AXIS + 1), "minecraft:air")
        fill((x, bottom - 1, Z_AXIS - 1), (x, bottom - 1, Z_AXIS + 1), "minecraft:stone")
    # ---- the chamber's dressing
    cx, cz = CAVE
    fill((cx - 7, floor, cz - 1), (ADIT_END - DROP - 1, floor, cz + 1), "minecraft:gravel")            # the old track bed
    for x in range(cx - 6, ADIT_END - DROP, 2):
        sb(x, floor + 1, cz, SLEEPER)
    sb(cx - 7, floor + 1, cz, "minecraft:barrel[facing=east,open=false]")                               # the buffer
    for px in (cx + 3, cx - 3):                                                                          # two old sets
        for z in (cz - 2, cz + 2):
            fill((px, floor + 1, z), (px, floor + 3, z), "minecraft:spruce_fence")
        fill((px, floor + 4, cz - 2), (px, floor + 4, cz + 2), "minecraft:spruce_planks")
        sb(px, floor + 3, cz, "minecraft:lantern[hanging=true]")
    for x, z in ((cx - 5, cz + 4), (cx + 5, cz - 4), (cx - 1, cz - 5), (cx + 1, cz + 5)):                # floor lanterns
        sb(x, floor + 1, z, "minecraft:lantern[hanging=false]")
    for x in range(cx - 8, cx - 5):                                                         # where water pooled once
        for z in range(cz - 3, cz):
            if (x, floor + 1, z) in cells:
                sb(x, floor, z, "minecraft:mud")
    hanging = []
    for i, (x, z) in enumerate(((cx + 4, cz + 4), (cx - 2, cz - 3), (cx + 6, cz + 1), (cx - 4, cz + 3), (cx + 1, cz - 2))):
        col = [y for (xx, y, zz) in cells if xx == x and zz == z]
        if not col:
            continue
        ceil = max(col)
        sb(x, ceil + 1, z, "minecraft:dripstone_block")
        sb(x, ceil, z, "minecraft:pointed_dripstone[thickness=tip,vertical_direction=down,waterlogged=false]")
        hanging.append((x, ceil, z))
        if i % 2 == 0 and ceil - floor > 5 and (x + 1, floor + 1, z) in cells:
            sb(x + 1, floor, z, "minecraft:dripstone_block")
            sb(x + 1, floor + 1, z, "minecraft:pointed_dripstone[thickness=tip,vertical_direction=up,waterlogged=false]")
    # the find, at the chamber's far west end (data/rewards.json r1_old_mine): an empty barrel, scenery
    fx, fy, fz = find_spot(g)
    sb(fx, fy, fz, "minecraft:barrel[facing=up,open=false]")
    sb(fx + 1, fy, fz, "minecraft:lantern[hanging=false]")
    # ---- outside: the spoil heap by the portal, three spruces near the top, boulders
    for (x, z) in ((1350, 4124), (1351, 4124), (1352, 4125), (1350, 4125), (1351, 4125), (1351, 4126), (1353, 4124)):
        base = top.get((x, z), g(x, z))
        sb(x, base + 1, z, "minecraft:gravel" if h32(x, z) % 3 else "minecraft:cobblestone")
    sb(PORTAL_X + 3, feet, Z_AXIS + 2, "minecraft:spruce_fence")                    # a lamp post in the notch
    sb(PORTAL_X + 3, feet + 1, Z_AXIS + 2, "minecraft:lantern[hanging=false]")
    for tx, tz, th in ((1327, 4115, 7), (1331, 4121, 6), (1323, 4126, 8)):
        t = top[(tx, tz)]
        fill((tx, t + 1, tz), (tx, t + th, tz), "minecraft:spruce_log[axis=y]")
        for k in range(3):
            r = 2 - k // 2
            y = t + th - 3 + 2 * k
            for a in range(-r, r + 1):
                for b in range(-r, r + 1):
                    if (a, b) != (0, 0) and abs(a) + abs(b) <= r + (1 if k == 0 else 0):
                        sb(tx + a, y, tz + b, "minecraft:spruce_leaves[distance=1,persistent=true,waterlogged=false]")
        sb(tx, t + th + 1, tz, "minecraft:spruce_leaves[distance=1,persistent=true,waterlogged=false]")
    for bx, bz in ((1314, 4112), (1344, 4106), (1338, 4133), (1318, 4131)):
        t = top.get((bx, bz), g(bx, bz))
        for a, b, e in ((0, 0, 1), (1, 0, 1), (0, 1, 1), (0, 0, 2)):
            sb(bx + a, t + e, bz + b, "minecraft:mossy_cobblestone" if h32(bx, bz, a, b) % 2 else "minecraft:andesite")
    # first of all, a rebuild takes down the last build's stalactites. The site clear removes the block each hangs
    # from, which schedules it to fall a tick later; by then this function has put a new one in the same place, and a
    # stalactite's scheduled tick drops it without looking at its support again. Removing a stalactite itself
    # schedules nothing. Every second rebuild lost one on staging (2026-09-24) until this ran first
    # The portal's lamp stands on a fence the site clear also removes, and it dropped as an item on every rebuild
    c[1:1] = ["setblock %d %d %d minecraft:air" % p for p in hanging + [(PORTAL_X + 3, feet + 1, Z_AXIS + 2)]]
    return c


def find_spot(g):
    """The find's barrel: the chamber's west end, on its floor."""
    floor = g(PORTAL_X + 1, Z_AXIS) - DROP
    return (int(CAVE[0] - CAVE_R[0]) + 2, floor + 1, CAVE[1] + 2)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    a = p.parse_args(argv)
    g = G.Ground(a.source_root)
    top, clear = plan(g)
    xs, zs = [x for x, _ in clear], [z for _, z in clear]
    path = ROOT / "data" / "placements.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["settlements"][SID] = {
        "centre": list(CENTRE), "status": "authored 2026-09-24 and built on staging; not in the live world",
        "plan": {
            "reading": "West of Route 1, across open ground, a hill rises on its own with three spruces on its top. Its "
                       "east face has been cut: a notch in the slope, a spruce portal, and an old track bed running into "
                       "the dark, its rails long taken up. The level goes in at ground height under timber sets, then "
                       "stairs drop into a cave under the hill, dripstone overhead, copper still in the walls, a mud "
                       "hollow where water once stood, and a barrel the miners left.",
            "entries": [{"from": "Route 1, 262 blocks east (nearest walked point (1594, 4119)), across open ground",
                         "at": list(TRAIL[-1]), "street": "trail"}],
            "exits": [],
            "footprint": {"rect": [min(xs), min(zs), max(TRAIL[-1][0], max(xs)), max(zs)],
                          "why": "the hill, the margin cleared round it and the trail out of the notch"},
            "streets": [{"id": "trail", "polyline": [list(p) for p in TRAIL], "width": 2,
                         "surface": "minecraft:coarse_dirt", "max_grade": 0.15,
                         "why": "the carts' old way out, worn into the ground: it says the notch is a way in"}],
            "anchors": [{"id": "hill", "role": "landmark", "template": None,
                         "rect": [min(x for x, _ in top), min(z for _, z in top), max(x for x, _ in top), max(z for _, z in top)],
                         "facing": "east", "why": "the hill and its mine (earthwork route1_old_mine_hill)"}],
            "house_lots": {"along": [], "why": "no houses"},
            "paving": {"main": "minecraft:coarse_dirt", "lamp": "none", "why": "a worn trail, unlit; the portal has its lamp"},
            "no_services": "a landmark off a route, not a town",
        },
    }
    rec = {"id": "route1_old_mine_hill", "settlement": SID, "kind": "earthwork", "cell": "E2",
           "status": "planned", "chosen_because": "the owner, 2026-09-24: a hill that turns into a mineshaft cave at "
           "(1332, 130, 4120), to give that ground some life; see tools/route1_old_mine.py",
           "commands": build(g)}
    at = next((i for i, q in enumerate(doc["placements"]) if q["id"] == rec["id"]), None)
    if at is None:
        doc["placements"].append(rec)
    else:
        doc["placements"][at] = rec
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote %s: %d commands; hill %d columns, peak y%d; the find at %s" % (
        SID, len(rec["commands"]), len(top), max(top.values()), find_spot(g)))


if __name__ == "__main__":
    main()
