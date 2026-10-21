#!/usr/bin/env python
"""A built hill with a timbered adit in one face: the Route 1 old mine's (tools/route1_old_mine.py, 2026-09-24), shared.

The owner, 2026-10-20, of the Fossick Deep Galleries' free-standing frame on the flat: "make fossick like route 1". The
Route 1 old mine is not cut into a natural slope: it BUILDS a hill on flat ground and digs its adit into that. This
module is that hill and that adit, lifted out of tools/route1_old_mine.py so a second mine is built by the same code
rather than a copy (tools/fossick_adit.py). tools/route1_old_mine.py builds exactly what it built before through it
(its recorded earthwork, data/placements.json route1_old_mine_hill, is byte for byte the same).

  Hill          an irregular dome over the heightmap's ground (tools/ground.py, rounded, never a world's surface):
                `rise` is the Route 1 hill's profile about any peak, mirrored in x when the adit runs east
  site          everything above the ground in and round the hill cleared first, so no painted tree is left sticking
                out of a slope
  hill_body     stone, then two of the palette's under layer, then its skin; bare rock where the slope is steep
  adit          the notch open to the sky, a 3-wide 4-high level, the spruce portal, timber sets (fence posts and a
                plank cap) every four blocks with a lantern under each, the old track's sleepers, and the incline:
                cobblestone stairs down `drop` blocks into the hill, the full width, a lantern every four stairs
  outside       the spoil heap by the portal, a lamp post in the notch, trees on the top, boulders on the flanks

Every function appends Minecraft commands to a list in the order tools/route1_old_mine.py has always written them.
"""
from __future__ import annotations

import math

SLEEPER = "minecraft:spruce_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]"


def h32(*v):
    """A deterministic mix for materials and scatter."""
    x = 0
    for i, t in enumerate(v):
        x ^= (int(t) * (73856093, 19349663, 83492791, 2654435761)[i % 4]) & 0xFFFFFFFF
    x = (x ^ (x >> 13)) * 0x5BD1E995 & 0xFFFFFFFF
    return x ^ (x >> 15)


def rock(x, y, z):
    k = h32(x, y, z, 7) % 20
    return ("minecraft:andesite" if k < 5 else "minecraft:tuff" if k < 7 else "minecraft:cobblestone" if k < 8
            else "minecraft:stone")


def wall(x, y, z):
    """A cave wall: rock, and now and then copper the miners left and a calcite vein. No coal or iron ore: both decide
    spawns (#minecraft:coal_ores draws rolycoly and carkol, #minecraft:iron_ores aron, aggron and alolan geodude,
    data/spawn_blocks.json), and a cave drawing them is a balance decision, not dressing."""
    k = h32(x, y, z, 11) % 60
    if k < 3:
        return "minecraft:copper_ore"
    if k == 3:
        return "minecraft:dripstone_block"      # not gravel: a wall cell may be a ceiling, and gravel falls (staging)
    if k == 4:
        return "minecraft:calcite"
    return rock(x, y, z)


def _fill(c):
    return lambda a, b, blk: c.append("fill %d %d %d %d %d %d %s" % (a[0], a[1], a[2], b[0], b[1], b[2], blk))


def _sb(c):
    return lambda x, y, z, blk: c.append("setblock %d %d %d %s" % (x, y, z, blk))


class Hill:
    """The Route 1 hill's profile about `peak`: half-widths rx, rz and `height` at the peak, a wobbled outline, and a
    lower second top (the shoulder) offset (-9, +10) from the peak with half-widths 9 and 8. `mirror` reflects the
    whole shape in x about the peak, so a hill whose adit runs east has the face Route 1's runs west into."""

    def __init__(self, peak, rx, rz, height, mirror=False):
        self.peak, self.rx, self.rz, self.height, self.mirror = tuple(peak), rx, rz, height, mirror
        sx = peak[0] + 9 if mirror else peak[0] - 9
        self.shoulder = (sx, peak[1] + 10)

    def rise(self, x, z):
        """The hill's height above the ground at (x, z): 0 outside it."""
        dx, dz = x - self.peak[0], z - self.peak[1]
        if self.mirror:
            dx = -dx
        th = math.atan2(dz, dx)
        wobble = 1 + 0.10 * math.sin(3 * th + 1.3) + 0.06 * math.sin(5 * th + 0.4) + 0.04 * math.sin(8 * th + 2.1)
        d = math.hypot(dx / self.rx, dz / self.rz) / wobble
        if d >= 1:
            return 0
        shoulder = 0.18 * max(0.0, 1 - math.hypot((x - self.shoulder[0]) / 9, (z - self.shoulder[1]) / 8))
        return int(round(self.height * ((1 + math.cos(math.pi * d)) / 2) ** 0.85 + self.height * shoulder * (1 - d)))

    def plan(self, g, margin):
        """(top, clear): the hill's surface height per column it raises, and the columns to clear (the hill grown by
        `margin`)."""
        top = {}
        for x in range(self.peak[0] - self.rx - 8, self.peak[0] + self.rx + 9):
            for z in range(self.peak[1] - self.rz - 8, self.peak[1] + self.rz + 9):
                r = self.rise(x, z)
                if r > 0:
                    top[(x, z)] = g(x, z) + r
        clear = set()
        for (x, z) in top:
            for dx in range(-margin, margin + 1):
                for dz in range(-margin, margin + 1):
                    clear.add((x + dx, z + dz))
        return top, clear


def route1_skin(x, z, steep):
    """The Route 1 hill's skin: grass where it is gentle, coarse dirt and gravel where it steepens, now and then podzol."""
    k = h32(x, z, 3) % 14
    return ("minecraft:coarse_dirt" if steep == 2 and k < 5 else "minecraft:gravel" if steep == 2 and k < 7
            else "minecraft:podzol" if k == 0 else "minecraft:grass_block[snowy=false]")


ROUTE1_PALETTE = {"skin": route1_skin, "under": "minecraft:dirt", "steep": rock}


def site(c, g, clear):
    """Every painted tree and plant above the ground over `clear`, in runs of equal ground along x."""
    fill = _fill(c)
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


def hill_body(c, g, top, palette=ROUTE1_PALETTE):
    """The hill: stone, then two of the palette's under layer, then its skin; the palette's bare rock where steep."""
    fill, sb = _fill(c), _sb(c)
    for (x, z), t in sorted(top.items()):
        base = g(x, z)
        near = [top.get((x + a, z + b), g(x + a, z + b)) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        steep = max(abs(t - n) for n in near)
        if t - 3 > base:
            fill((x, base + 1, z), (x, t - 3, z), "minecraft:stone")
        if steep >= 3:
            for y in range(max(base + 1, t - 2), t + 1):
                sb(x, y, z, palette["steep"](x, y, z))
            continue
        if t - 1 > base:
            fill((x, max(base + 1, t - 2), z), (x, t - 1, z), palette["under"])
        sb(x, t, z, palette["skin"](x, z, steep))


class Adit:
    """An adit's line: the portal's outer face `portal_x`, the level's last cell `adit_end`, the centre line `z_axis`, the
    incline's `drop`, and `sense` -1 when the adit runs west into the hill (Route 1) or +1 when it runs east."""

    def __init__(self, portal_x, adit_end, z_axis, drop, sense):
        if sense not in (-1, 1) or (adit_end - portal_x) * sense < 1:
            raise SystemExit("an adit runs from its portal into the hill: portal %d, level end %d, sense %r"
                             % (portal_x, adit_end, sense))
        self.portal_x, self.adit_end, self.z_axis, self.drop, self.sense = portal_x, adit_end, z_axis, drop, sense

    def feet(self, g):
        """The level's feet: one over the ground just outside the portal."""
        return g(self.portal_x - self.sense, self.z_axis) + 1

    def level(self):
        """(lo, hi): the level's x range, inside the portal to its last cell."""
        return tuple(sorted((self.adit_end, self.portal_x + self.sense)))

    def stair(self, i, feet):
        """(x, y) of stair i (1 .. drop): the incline's i-th row and its stair block."""
        return self.adit_end + self.sense * i, feet - i


def adit(c, g, top, a):
    """The notch, the level, the portal, the timber sets, the sleepers and the incline, in Route 1's order. Returns the
    level's feet."""
    fill, sb = _fill(c), _sb(c)
    s, P, E, Z = a.sense, a.portal_x, a.adit_end, a.z_axis
    feet = a.feet(g)
    xs = [x for (x, z) in top if z == Z]
    foot = max(xs) + 1 if s == -1 else min(xs) - 1                                   # the hill's outer foot on the line
    for x in range(P, foot - s, -s):                                                # the notch, open to the sky
        fill((x, feet, Z - 2), (x, feet + 20, Z + 2), "minecraft:air")
        for z in range(Z - 2, Z + 3):                                               # its floor: earth, never loose
            if g(x, z) + 1 <= feet - 2:                                             # gravel over lower ground
                fill((x, g(x, z) + 1, z), (x, feet - 2, z), "minecraft:dirt")
            sb(x, feet - 1, z, "minecraft:coarse_dirt")
    lo, hi = a.level()
    fill((lo, feet, Z - 1), (hi, feet + 3, Z + 1), "minecraft:air")
    fill((lo, feet - 1, Z - 1), (hi, feet - 1, Z + 1), "minecraft:gravel")
    fill((lo, feet + 4, Z - 1), (hi, feet + 4, Z + 1), "minecraft:stone")                       # a roof, always
    for x in range(lo, hi + 1):
        for z in (Z - 2, Z + 2):
            fill((x, feet - 1, z), (x, feet + 4, z), rock(x, feet, z))                           # the level's walls
    # the portal: spruce posts and a beam, in the face
    for z in (Z - 2, Z + 2):
        fill((P, feet, z), (P, feet + 3, z), "minecraft:spruce_log[axis=y]")
    fill((P, feet + 4, Z - 2), (P, feet + 4, Z + 2), "minecraft:spruce_log[axis=z]")
    fill((P - s, feet + 4, Z - 2), (P - s, feet + 4, Z + 2), "minecraft:spruce_slab[type=bottom]")
    # timber sets every four blocks, a lantern under each cap
    for x in range(P + s, E + s, 4 * s):
        for z in (Z - 1, Z + 1):
            fill((x, feet, z), (x, feet + 2, z), "minecraft:spruce_fence")
        fill((x, feet + 3, Z - 1), (x, feet + 3, Z + 1), "minecraft:spruce_planks")
        sb(x, feet + 2, Z, "minecraft:lantern[hanging=true]")
    # the old track: its rails taken up, its sleepers left on the bed, from outside the portal to the incline
    for x in range(E, P - 4 * s, -2 * s):
        sb(x, feet, Z, SLEEPER)
    # ---- the incline: stairs down into the hill, the full width, facing out
    facing = "east" if s == -1 else "west"
    for i in range(1, a.drop + 1):
        x, y = a.stair(i, feet)
        fill((x, y, Z - 1), (x, y + 4, Z + 1), "minecraft:air")
        fill((x, y + 5, Z - 2), (x, y + 5, Z + 2), "minecraft:stone")
        for z in (Z - 2, Z + 2):
            fill((x, y - 1, z), (x, y + 5, z), rock(x, y, z))
        fill((x, y - 1, Z - 1), (x, y - 1, Z + 1), "minecraft:stone")
        for z in (Z - 1, Z, Z + 1):
            sb(x, y, z, "minecraft:cobblestone_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]" % facing)
        if i % 4 == 0:
            sb(x, y + 3, Z, "minecraft:lantern[hanging=true]")
            sb(x, y + 4, Z, "minecraft:spruce_planks")
    return feet


def lamp_post(a, feet):
    """(x, y, z) of the notch's lamp: three out from the portal, on the line's far side, on a fence post."""
    return (a.portal_x - 3 * a.sense, feet + 1, a.z_axis + 2)


def outside(c, g, top, a, feet, spoil, trees, boulders, boulder_blocks=("minecraft:mossy_cobblestone", "minecraft:andesite"),
            spoil_blocks=("minecraft:gravel", "minecraft:cobblestone")):
    """The spoil heap by the portal (`spoil` columns), the notch's lamp post, `trees` ((x, z, trunk height): spruces on
    the top) and `boulders` ((x, z): three-block boulders on the flanks)."""
    fill, sb = _fill(c), _sb(c)
    for (x, z) in spoil:
        base = top.get((x, z), g(x, z))
        sb(x, base + 1, z, spoil_blocks[0] if h32(x, z) % 3 else spoil_blocks[1])
    lx, ly, lz = lamp_post(a, feet)
    sb(lx, ly - 1, lz, "minecraft:spruce_fence")                                     # a lamp post in the notch
    sb(lx, ly, lz, "minecraft:lantern[hanging=false]")
    for tx, tz, th in trees:
        t = top[(tx, tz)]
        fill((tx, t + 1, tz), (tx, t + th, tz), "minecraft:spruce_log[axis=y]")
        for k in range(3):
            r = 2 - k // 2
            y = t + th - 3 + 2 * k
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if (dx, dz) != (0, 0) and abs(dx) + abs(dz) <= r + (1 if k == 0 else 0):
                        sb(tx + dx, y, tz + dz, "minecraft:spruce_leaves[distance=1,persistent=true,waterlogged=false]")
        sb(tx, t + th + 1, tz, "minecraft:spruce_leaves[distance=1,persistent=true,waterlogged=false]")
    for bx, bz in boulders:
        t = top.get((bx, bz), g(bx, bz))
        for dx, dz, e in ((0, 0, 1), (1, 0, 1), (0, 1, 1), (0, 0, 2)):
            sb(bx + dx, t + e, bz + dz, boulder_blocks[0] if h32(bx, bz, dx, dz) % 2 else boulder_blocks[1])
