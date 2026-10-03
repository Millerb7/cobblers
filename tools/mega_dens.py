#!/usr/bin/env python
"""The seven open-air Mega dens made visible, from data/mega_dens.json: a lair you can see from the air round each den
anchor in data/gulch_mine.json farms[].dens[].

The owner, 2026-10-02: "Den dressing rather than a taller trigger box. I want to see something from the air and go down
to it, not trigger a spawn by flying near." Until now a den wrote no block at all. Each den here is, roughly 24-30
blocks across:

  the scrape     a disc of churned ground (coarse dirt, rooted dirt, gravel, the species' own ground) with a ragged edge,
                 written AT each column's ground surface, never above it
  the ring       shoved boulders standing just outside it, broken where the trampled approach comes in
  the approach   a three-wide track of path and churned dirt from the scrape's edge toward the nearest critical path
  the carcass    a spine and ribs of bone and a skull, and loose bones over the scrape
  the sign       the species' own mark at `feature_at`: Aggron's spoil heap of torn ore and scrap, Pinsir's woodpile of
                 felled and split trunks, Manectric's fused strike and its black streaks, Houndoom's ash and char and
                 bone heap, Abomasnow's frost patch and ice spires, Tyranitar's crater and split boulders, Garchomp's
                 burrow
  the pad        every column within anchor_pad.clear_radius of the anchor levelled to the anchor's ground with one block,
                 and the head_room over it written AIR: the keeper spawns the Mega AT the anchor, never inside a block

Dark by design (data/mega_dens.json lighting): no light source is written. Ground from tools/ground.py (the canonical
heightmap, rounded), never a world. Every block is refused unless it is in blocks.ids and inside the den's write_box.

  python tools/mega_dens.py build [--source-root R] [--out DIR]   write the pack
  python tools/mega_dens.py plan  [--source-root R]               print the numbers and the steps; writes nothing
  python tools/mega_dens.py probes [--source-root R]              print the World probes (docs/world-building/MEGA_DENS.md)

The re-application: placement_steps() is step R9MD (tools/reapply.py), after R9S and before R9E.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "mega_dens.json"
GULCH = ROOT / "data" / "gulch_mine.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_mega_dens"
SCHEMA = "cobblers.mega-dens/1"
NS = "cobblers"
FN = "mega_dens"
PACK_FORMAT = 48  # Minecraft 1.21.1
AIR = "minecraft:air"
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class DenError(SystemExit):
    pass


def load(path=DATA, gulch=GULCH):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise DenError("%s: schema must be %s" % (path, SCHEMA))
    if doc.get("lighting") != "dark":
        raise DenError("the dens are dark by design: lighting must be 'dark'")
    gm = json.loads(Path(gulch).read_text(encoding="utf-8"))
    dens = {d["id"]: (f, d) for f in gm["farms"] for d in f["dens"]}
    for rec in doc["dens"]:
        if rec["den"] not in dens:
            raise DenError("%s is not a den in data/gulch_mine.json farms[].dens[]" % rec["den"])
        if dens[rec["den"]][1]["species"] != rec["species"]:
            raise DenError("%s: the gulch's den is a %s, not a %s" % (rec["den"], dens[rec["den"]][1]["species"],
                                                                    rec["species"]))
    return doc, dens


def _base(state):
    return state.split("[")[0].split("{")[0]


def _pick(rng, weights):
    keys = sorted(weights)
    total = sum(weights[k] for k in keys)
    v = rng.random() * total
    for k in keys:
        v -= weights[k]
        if v < 0:
            return k
    return keys[-1]


# ------------------------------------------------------------------------------------------------------------ the den
class Den:
    """One den's writes, {(x, y, z): state}, and each column's current top (the ground, then what stands on it)."""

    def __init__(self, doc, rec, gden, g, index):
        self.doc, self.rec, self.g = doc, rec, g
        self.species = rec["species"]
        self.ax, self.ay, self.az = gden["anchor"]
        self.G0 = self.ay - 1
        pad = doc["anchor_pad"]
        self.clear, self.head = pad["clear_radius"], pad["head_room"]
        self.L = doc["layout"]
        self.box = rec["write_box"]
        self.allowed = set(doc["blocks"]["ids"])
        self.rng = random.Random(doc["seed"] * 101 + index)
        self.w, self.top, self.reserved = {}, {}, set()
        tx, tz = rec["approach_toward"]
        self.theta = math.atan2(tz - self.az, tx - self.ax)
        self.fx, self.fz = rec["feature_at"]
        self.feature_cells = set()

    # --- primitives
    def ground(self, x, z):
        return int(round(self.g(x, z)))

    def gtop(self, x, z):
        if (x, z) not in self.top:
            self.top[(x, z)] = self.ground(x, z)
        return self.top[(x, z)]

    def r(self, x, z):
        return math.hypot(x - self.ax, z - self.az)

    def inside(self, x, z, margin=0):
        b = self.box
        return b[0] + margin <= x <= b[3] - margin and b[2] + margin <= z <= b[5] - margin

    def put(self, x, y, z, state):
        if _base(state) not in self.allowed:
            raise DenError("%s is not in data/mega_dens.json blocks.ids" % _base(state))
        b = self.box
        if not (b[0] <= x <= b[3] and b[1] <= y <= b[4] and b[2] <= z <= b[5]):
            raise DenError("%s: (%d, %d, %d) is outside its write_box %s" % (self.species, x, y, z, b))
        self.w[(x, y, z)] = state

    def surface(self, x, z, state):
        self.put(x, self.gtop(x, z), z, state)

    def stack(self, x, z, state, n=1):
        for _ in range(n):
            y = self.gtop(x, z) + 1
            self.put(x, y, z, state)
            self.top[(x, z)] = y

    def lower(self, x, z, newtop, floor):
        for y in range(newtop + 1, self.gtop(x, z) + 1):
            self.put(x, y, z, AIR)
        self.put(x, newtop, z, floor)
        self.top[(x, z)] = newtop

    def can_stand(self, x, z, bare=True):
        """Something may stand here: clear of the anchor, off the track and the dug sign, inside the box, and (unless
        it is meant to rest on another part of the same thing) on the column's own ground, not on top of something."""
        return (self.r(x, z) > self.L["object_clear"] and (x, z) not in self.reserved and self.inside(x, z, 1)
                and (not bare or self.gtop(x, z) <= self.ground(x, z)))

    def angle_off(self, a):
        d = (a - self.theta + math.pi) % (2 * math.pi) - math.pi
        return abs(d)

    # --- the parts every den has
    def scrape(self):
        R, rag = self.L["scrape_radius"], self.L["scrape_ragged"]
        p1, p2 = self.rng.uniform(0, 6.28), self.rng.uniform(0, 6.28)
        self.edge = lambda a: R + rag * (0.5 * math.sin(3 * a + p1) + 0.5 * math.sin(5 * a + p2))
        n = R + rag + 1
        for x in range(self.ax - n, self.ax + n + 1):
            for z in range(self.az - n, self.az + n + 1):
                a = math.atan2(z - self.az, x - self.ax)
                if self.r(x, z) <= self.edge(a):
                    self.surface(x, z, _pick(self.rng, self.rec["scrape"]))

    def approach(self):
        w = self.L["approach_width"] // 2
        c, s = math.cos(self.theta), math.sin(self.theta)
        t = float(self.L["approach_from"])
        cols = []
        while t <= self.L["approach_to"]:
            for off in range(-w, w + 1):
                col = (int(round(self.ax + t * c - off * s)), int(round(self.az + t * s + off * c)))
                if col not in cols and self.inside(*col, 1):
                    cols.append(col)
            t += 0.5
        for col in cols:
            self.surface(col[0], col[1], _pick(self.rng, self.rec["path"]))
            self.reserved.add(col)

    def boulders(self):
        L = self.L
        n = L["boulders"]
        tyr = self.species == "tyranitar"
        for i in range(n):
            a = 2 * math.pi * i / n + self.theta + self.rng.uniform(-0.2, 0.2)
            if self.angle_off(a) < math.radians(L["ring_gap_degrees"]) / 2:
                continue
            rr = self.rng.uniform(*L["ring_radius"])
            br = self.rng.uniform(*L["boulder_radius"]) + (0.6 if tyr else 0)
            hb = self.rng.randint(*L["boulder_height"]) + (1 if tyr else 0)
            cx, cz = self.ax + rr * math.cos(a), self.az + rr * math.sin(a)
            split = self.rng.uniform(0, math.pi)
            k = int(math.ceil(br)) + 1
            for x in range(int(cx) - k, int(cx) + k + 2):
                for z in range(int(cz) - k, int(cz) + k + 2):
                    d = math.hypot(x - cx, z - cz)
                    if d > br or not self.can_stand(x, z):
                        continue
                    if tyr and abs((x - cx) * math.cos(split) + (z - cz) * math.sin(split)) < 0.5:
                        continue            # smashed through: the crack between the two halves
                    h = max(1, int(round(hb * (1 - (d / (br + 0.8)) ** 2))))
                    for _ in range(h):
                        self.stack(x, z, self.rng.choice(self.rec["boulder"]))
                    if self.species == "abomasnow":
                        self.stack(x, z, "minecraft:snow[layers=%d]" % self.rng.randint(1, 3))
            if tyr:                         # the pieces knocked off it
                for _ in range(4):
                    fa = self.rng.uniform(0, 2 * math.pi)
                    fd = br + self.rng.uniform(1.0, 2.5)
                    x, z = int(round(cx + fd * math.cos(fa))), int(round(cz + fd * math.sin(fa)))
                    if self.can_stand(x, z):
                        self.stack(x, z, self.rng.choice(["minecraft:cobblestone", "minecraft:gravel"]))

    def carcass(self):
        a = self.theta + math.radians(100)
        px = int(round(self.ax + self.L["carcass_at"] * math.cos(a)))
        pz = int(round(self.az + self.L["carcass_at"] * math.sin(a)))
        # the spine runs along the dominant tangent axis
        along_x = abs(math.sin(a)) >= abs(math.cos(a))
        axis = "x" if along_x else "z"
        step = (1, 0) if along_x else (0, 1)
        side = (0, 1) if along_x else (1, 0)
        for i in range(-2, 3):
            x, z = px + i * step[0], pz + i * step[1]
            if self.can_stand(x, z):
                self.stack(x, z, "minecraft:bone_block[axis=%s]" % axis)
        for i in (-1, 0, 1):
            for sgn in (-1, 1):
                x, z = px + i * step[0] + sgn * side[0], pz + i * step[1] + sgn * side[1]
                if self.can_stand(x, z):
                    self.stack(x, z, "minecraft:bone_block[axis=y]", 2 if i == 0 else 1)
        x, z = px + 2 * step[0], pz + 2 * step[1]
        if self.can_stand(x, z):
            self.stack(x, z, "minecraft:skeleton_skull[rotation=%d]" % self.rng.randint(0, 15))
        for _ in range(self.L["bones_scattered"]):
            for _try in range(12):
                ba = self.rng.uniform(0, 2 * math.pi)
                bd = self.rng.uniform(5, self.L["scrape_radius"] - 1)
                x, z = int(round(self.ax + bd * math.cos(ba))), int(round(self.az + bd * math.sin(ba)))
                if self.can_stand(x, z) and self.gtop(x, z) == self.ground(x, z):
                    self.stack(x, z, "minecraft:bone_block[axis=%s]" % self.rng.choice("xz"))
                    break

    def pad(self):
        """Last: the anchor's columns levelled to its ground with one block, the head room over them air, nothing else
        within clear_radius."""
        for x in range(self.ax - self.clear, self.ax + self.clear + 1):
            for z in range(self.az - self.clear, self.az + self.clear + 1):
                if self.r(x, z) > self.clear:
                    continue
                for k in [k for k in self.w if k[0] == x and k[2] == z]:
                    del self.w[k]
                self.put(x, self.G0, z, self.rec["pad"])
                for y in range(self.G0 + 1, self.G0 + self.head + 1):
                    self.put(x, y, z, AIR)
                self.top[(x, z)] = self.G0

    # --- the signs
    def trunk(self, x0, z0, axis, length, log, split_log=None, end=None):
        dx, dz = (1, 0) if axis == "x" else (0, 1)
        sx, sz = (0, 1) if axis == "x" else (1, 0)
        for i in range(length):
            x, z = x0 + i * dx, z0 + i * dz
            if self.can_stand(x, z):
                self.stack(x, z, end if (end and i == length - 1) else "%s[axis=%s]" % (log, axis))
            if split_log and self.can_stand(x + sx, z + sz):
                self.stack(x + sx, z + sz, "%s[axis=%s]" % (split_log, axis))

    def spot(self, rmin, rmax, avoid_approach=0.6):
        for _ in range(40):
            a = self.rng.uniform(0, 2 * math.pi)
            if self.angle_off(a) < avoid_approach:
                continue
            d = self.rng.uniform(rmin, rmax)
            x, z = int(round(self.ax + d * math.cos(a))), int(round(self.az + d * math.sin(a)))
            if self.can_stand(x, z):
                return x, z
        return None

    def spoil_heap(self):
        F = (self.fx, self.fz)
        ore = {"minecraft:raw_iron_block": 3, "minecraft:raw_copper_block": 2, "minecraft:gravel": 2,
               "minecraft:cobbled_deepslate": 1}
        for x in range(F[0] - 5, F[0] + 6):
            for z in range(F[1] - 5, F[1] + 6):
                d = math.hypot(x - F[0], z - F[1])
                if d > 4.3 or not self.can_stand(x, z):
                    continue
                h = max(1, int(round(3 * (1 - (d / 4.6) ** 2))))
                for _ in range(h - 1):
                    self.stack(x, z, self.rng.choice(["minecraft:tuff", "minecraft:cobbled_deepslate"]))
                self.stack(x, z, _pick(self.rng, ore))
                self.feature_cells.add((x, z))
        bars = [c for c in sorted(self.feature_cells) if math.hypot(c[0] - F[0], c[1] - F[1]) <= 2.5]
        self.rng.shuffle(bars)
        for x, z in bars[:4]:
            self.stack(x, z, "minecraft:iron_bars", 2)
        for kind, n, lo, hi in (("chain", 3, 5.0, 6.5), ("anvil", 2, 5.0, 7.0)):
            placed = 0
            for _try in range(40):
                if placed == n:
                    break
                a = self.rng.uniform(0, 2 * math.pi)
                d = self.rng.uniform(lo, hi)
                x, z = int(round(F[0] + d * math.cos(a))), int(round(F[1] + d * math.sin(a)))
                if not self.can_stand(x, z) or (x, z) in self.feature_cells:
                    continue
                if kind == "chain":
                    self.stack(x, z, "minecraft:chain[axis=%s,waterlogged=false]" % self.rng.choice("xz"))
                else:
                    self.stack(x, z, "minecraft:damaged_anvil[facing=%s]" % self.rng.choice(
                        ["north", "east", "south", "west"]))
                self.feature_cells.add((x, z))
                placed += 1

    def woodpile(self):
        F = (self.fx, self.fz)
        for row in (-1, 0, 1):
            for i in range(-2, 3):
                x, z = F[0] + i, F[1] + row
                if self.can_stand(x, z):
                    self.stack(x, z, "minecraft:%s[axis=x]" % ("stripped_oak_log" if row == 0 else "oak_log"))
                    self.feature_cells.add((x, z))
        for row in (-1, 0, 1):
            for i in range(-2, 3):
                x, z = F[0] + row, F[1] + i
                if self.can_stand(x, z, bare=False):
                    self.stack(x, z, "minecraft:%s[axis=z]" % ("stripped_oak_log" if row == 0 else "oak_log"))
                    self.feature_cells.add((x, z))
        for _ in range(6):
            s = self.spot(5, 12)
            if s:
                split = self.rng.random() < 0.7
                self.trunk(s[0], s[1], self.rng.choice("xz"), self.rng.randint(5, 7), "minecraft:oak_log",
                           "minecraft:stripped_oak_log" if split else None)
        for _ in range(4):
            s = self.spot(6, 14)
            if s:
                self.stack(s[0], s[1], "minecraft:oak_log[axis=y]", self.rng.randint(1, 2))
                self.stack(s[0], s[1], "minecraft:stripped_oak_log[axis=y]")

    def strike(self):
        F = (self.fx, self.fz)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                x, z = F[0] + dx, F[1] + dz
                if (x, z) not in self.reserved and self.r(x, z) > self.clear:
                    self.surface(x, z, "minecraft:obsidian")
                    self.feature_cells.add((x, z))

        def streak(x, z, a, n, fork):
            ends = []
            for i in range(n):
                a += self.rng.uniform(-0.45, 0.45)
                x, z = x + math.cos(a), z + math.sin(a)
                c = (int(round(x)), int(round(z)))
                if not self.inside(c[0], c[1], 2):
                    break
                if c not in self.reserved and self.r(*c) > self.clear and c not in self.feature_cells:
                    self.surface(c[0], c[1], "minecraft:blackstone" if self.rng.random() < 0.7
                                 else "minecraft:basalt[axis=y]")
                if fork and i == n // 2 and self.rng.random() < 0.6:
                    ends += streak(x, z, a + self.rng.choice((-0.9, 0.9)), self.rng.randint(3, 5), False)
            ends.append((int(round(x)), int(round(z))))
            return ends

        ends = []
        for i in range(7):
            ends += streak(F[0], F[1], 2 * math.pi * i / 7 + self.rng.uniform(-0.3, 0.3), self.rng.randint(7, 12), True)
        for dx, dz in ((2, 2), (-2, 2), (2, -2), (-2, -2)):
            ends.append((F[0] + dx, F[1] + dz))
        for x, z in ends:
            if self.can_stand(x, z):
                self.stack(x, z, "minecraft:glass", self.rng.randint(1, 2))

    def bone_pile(self):
        F = (self.fx, self.fz)
        for x in range(F[0] - 3, F[0] + 4):
            for z in range(F[1] - 3, F[1] + 4):
                d = math.hypot(x - F[0], z - F[1])
                if d <= 2.6 and self.can_stand(x, z):
                    self.stack(x, z, "minecraft:bone_block[axis=%s]" % self.rng.choice("xyz"), 2 if d <= 1.2 else 1)
                    self.feature_cells.add((x, z))
        cells = sorted(c for c in self.feature_cells if math.hypot(c[0] - F[0], c[1] - F[1]) <= 1.5)
        self.rng.shuffle(cells)
        for x, z in cells[:3]:
            self.stack(x, z, "minecraft:skeleton_skull[rotation=%d]" % self.rng.randint(0, 15))
        for _ in range(4):
            s = self.spot(5, 12)
            if s:
                self.trunk(s[0], s[1], self.rng.choice("xz"), self.rng.randint(4, 6), "minecraft:dark_oak_log",
                           end="minecraft:coal_block")
        for _ in range(3):
            s = self.spot(6, 13)
            if s:
                self.stack(s[0], s[1], "minecraft:dark_oak_log[axis=y]", self.rng.randint(1, 2))
                self.stack(s[0], s[1], "minecraft:coal_block")

    def frost(self):
        # the frost reaches past the scrape
        n = self.L["scrape_radius"] + self.L["scrape_ragged"] + 4
        for x in range(self.ax - n, self.ax + n + 1):
            for z in range(self.az - n, self.az + n + 1):
                a = math.atan2(z - self.az, x - self.ax)
                d = self.r(x, z)
                if self.edge(a) < d <= self.edge(a) + 3 and (x, z) not in self.reserved and self.rng.random() < 0.55:
                    self.surface(x, z, "minecraft:snow_block")
        F = (self.fx, self.fz)
        for dx, dz in ((0, 0), (1, 0), (0, 1), (1, 1)):
            x, z = F[0] + dx, F[1] + dz
            if self.can_stand(x, z):
                self.stack(x, z, "minecraft:packed_ice", 3 if (dx, dz) == (0, 0) else 2)
                self.feature_cells.add((x, z))
        if self.can_stand(*F, bare=False):
            self.stack(F[0], F[1], "minecraft:packed_ice")
            self.stack(F[0], F[1], "minecraft:blue_ice", 2)
        for _ in range(6):
            s = self.spot(6, 12)
            if s:
                h = self.rng.randint(3, 5)
                self.stack(s[0], s[1], "minecraft:packed_ice", h - 1)
                self.stack(s[0], s[1], "minecraft:blue_ice")
                self.feature_cells.add(s)

    def frost_late(self):
        """Snow lying on the snow, wherever nothing stands."""
        for (x, z), t in sorted(self.top.items()):
            if t != self.ground(x, z) or not self.can_stand(x, z):
                continue
            if self.w.get((x, t, z)) == "minecraft:snow_block" and self.rng.random() < 0.6:
                self.stack(x, z, "minecraft:snow[layers=%d]" % self.rng.randint(1, 3))

    def crater(self):
        F = (self.fx, self.fz)
        Gf = self.ground(*F)
        R = self.rec["dig"]["radius"]
        depth = self.rec["dig"]["depth"]
        floor = {"minecraft:gravel": 3, "minecraft:andesite": 2, "minecraft:coarse_dirt": 1}
        for x in range(F[0] - R - 2, F[0] + R + 3):
            for z in range(F[1] - R - 2, F[1] + R + 3):
                d = math.hypot(x - F[0], z - F[1])
                if d > R or (x, z) in self.reserved or self.r(x, z) <= self.clear:
                    continue
                dep = depth if d <= R / 2 else (1 if d <= R * 0.8 else 0)
                newtop = Gf - dep
                if newtop < self.gtop(x, z):
                    self.lower(x, z, newtop, _pick(self.rng, floor))
                else:
                    self.surface(x, z, _pick(self.rng, floor))
                self.feature_cells.add((x, z))
        self.reserved |= self.feature_cells
        rim = {"minecraft:cobblestone": 2, "minecraft:andesite": 2, "minecraft:gravel": 1}
        for x in range(F[0] - R - 2, F[0] + R + 3):
            for z in range(F[1] - R - 2, F[1] + R + 3):
                d = math.hypot(x - F[0], z - F[1])
                if R < d <= R + 1.6 and self.can_stand(x, z) and self.rng.random() < 0.75:
                    self.stack(x, z, _pick(self.rng, rim))

    def burrow(self):
        F = (self.fx, self.fz)
        Gb = self.ground(*F)
        dx, dz = self.ax - F[0], self.az - F[1]
        if abs(dx) >= abs(dz):
            sx, sz, facing = (1 if dx > 0 else -1), 0, ("east" if dx > 0 else "west")
        else:
            sx, sz, facing = 0, (1 if dz > 0 else -1), ("south" if dz > 0 else "north")
        for ox in range(-2, 3):
            for oz in range(-2, 3):
                x, z = F[0] + ox, F[1] + oz
                if max(abs(ox), abs(oz)) <= 1:
                    self.lower(x, z, Gb - 2, "minecraft:smooth_sandstone")
                else:                          # the lining under the rim, then the rim's own ground
                    for y in range(Gb - 2, self.gtop(x, z)):
                        self.put(x, y, z, "minecraft:sandstone")
                    self.surface(x, z, "minecraft:smooth_sandstone")
                self.feature_cells.add((x, z))
        x, z = F[0] + sx, F[1] + sz
        self.put(x, Gb - 1, z, "minecraft:sandstone_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]"
                 % facing)
        self.top[(x, z)] = Gb - 1
        self.reserved |= self.feature_cells
        for ox in range(-3, 4):
            for oz in range(-3, 4):
                x, z = F[0] + ox, F[1] + oz
                ring = max(abs(ox), abs(oz))
                if ring == 2 and ox * sx + oz * sz != 2:
                    self.reserved.discard((x, z))
                    if self.can_stand(x, z):
                        self.stack(x, z, "minecraft:smooth_sandstone")
                        if abs(ox) == 2 and abs(oz) == 2:
                            self.stack(x, z, "minecraft:sandstone")
                    self.reserved.add((x, z))
                elif ring == 3 and self.can_stand(x, z) and self.rng.random() < 0.5:
                    self.stack(x, z, "minecraft:sandstone")

    def build(self):
        self.scrape()
        self.approach()
        feature = getattr(self, self.rec["feature"])
        feature()
        self.boulders()
        self.carcass()
        if self.species == "abomasnow":
            self.frost_late()
        self.pad()
        return self


def plan(doc, dens, g):
    out = []
    for i, rec in enumerate(doc["dens"]):
        _farm, gden = dens[rec["den"]]
        out.append(Den(doc, rec, gden, g, i).build())
    return out


def most_visible(d):
    """The sign's own column, at its top: the heap, the pile, the spire, the strike, the crater's or burrow's floor."""
    return d.fx, d.gtop(d.fx, d.fz), d.fz


def max_rise(d):
    return max(y - d.ground(x, z) for (x, y, z), s in d.w.items() if s != AIR)


# ---------------------------------------------------------------------------------------------------------- the pack
def _runs(blocks):
    """setblock and fill lines for {(x, y, z): state}, one fill per run of one state along x, bottom up, so a gravity
    block or a snow layer is always written after what it rests on."""
    out = []
    keys = sorted(blocks, key=lambda k: (k[1], k[2], k[0]))
    i = 0
    while i < len(keys):
        x, y, z = keys[i]
        st = blocks[keys[i]]
        j = i
        while j + 1 < len(keys) and keys[j + 1] == (keys[j][0] + 1, y, z) and blocks[keys[j + 1]] == st:
            j += 1
        if j == i:
            out.append("setblock %d %d %d %s" % (x, y, z, st))
        else:
            out.append("fill %d %d %d %d %d %d %s" % (x, y, z, keys[j][0], y, z, st))
        i = j + 1
    return out


def build_lines(d):
    out = ["# Generated by tools/mega_dens.py from data/mega_dens.json. Re-run to rebuild; do not edit.",
           "# The %s den (%s) round the anchor %d %d %d: %s." % (d.species, d.rec["den"], d.ax, d.ay, d.az, d.rec["sign"]),
           "# Dark by design: no light source. The anchor's pad and its head room are written last."]
    out += _runs(d.w)
    return out


def files(doc, dens, g):
    ds = plan(doc, dens, g)
    out = {"pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                               "Cobblers: the seven open-air Mega dens, dressed (tools/mega_dens.py)"}},
                                     indent=2) + "\n"}
    for d in ds:
        lines = function_limits.ensure_loaded(build_lines(d))
        bad = function_limits.check_lines(lines, d.species)
        if bad:
            raise DenError("%s: %d command(s) the server would refuse: %s" % (d.species, len(bad), bad[:3]))
        out["data/%s/function/%s/%s.mcfunction" % (NS, FN, d.species)] = "\n".join(lines) + "\n"
    return out, ds


def placement_steps(doc=None, dens=None, g=None):
    """For tools/reapply.py, step R9MD (after R9S, before R9E): per den, hold its write box, build, release."""
    import ground as G
    if doc is None:
        doc, dens = load()
    g = g or G.load()
    steps = []
    for rec in doc["dens"]:
        b = rec["write_box"]
        hold = "%d %d %d %d" % (b[0], b[2], b[3], b[5])
        steps += [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/%s" % (NS, FN, rec["species"])),
                  ("cmd", "forceload remove " + hold)]
    return steps


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def report(ds):
    lines = []
    for d in ds:
        xs = [k[0] for k in d.w]
        ys = [k[1] for k in d.w]
        zs = [k[2] for k in d.w]
        mv = most_visible(d)
        lines.append("%-9s anchor (%d, %d, %d) ground y%d: %d blocks (air %d), x%d..%d y%d..%d z%d..%d; most visible "
                     "(%d, %d, %d); tallest %d over its ground" % (d.species, d.ax, d.ay, d.az, d.G0, len(d.w),
                                       sum(1 for s in d.w.values() if s == AIR), min(xs), max(xs), min(ys), max(ys),
                                       min(zs), max(zs), mv[0], mv[1], mv[2], max_rise(d)))
    return lines


def probes(ds):
    """The World probes for docs/world-building/MEGA_DENS.md: RCON block checks a session holding the server runs after
    R9MD, each expected to answer `Test passed`. They check the world matches this build; they prove nothing about the
    build itself (that is tools/mega_dens_audit.py's job)."""
    out = []
    for d in ds:
        st = lambda k: _base(d.w[k])                                       # noqa: E731
        out.append("### %s (`%s`), anchor (%d, %d, %d)" % (d.species.capitalize(), d.rec["den"], d.ax, d.ay, d.az))
        out.append("")
        rows = [((d.ax, d.G0, d.az), st((d.ax, d.G0, d.az)), "the pad under the anchor"),
                ((d.ax, d.ay, d.az), AIR, "the anchor itself is open"),
                ((d.ax, d.ay + d.head - 1, d.az), AIR, "the top of the head room"),
                ((d.ax + d.clear, d.ay + 1, d.az), AIR, "the edge of the spawn cylinder")]
        top = (d.fx, d.gtop(d.fx, d.fz), d.fz)
        rows.append((top, st(top), "the sign's own column, at its top (%s)" % d.rec["feature"]))
        if d.rec.get("dig"):
            k = (d.fx, d.ground(d.fx, d.fz), d.fz)
            rows.append((k, AIR, "the %s is open where the ground was" % d.rec["feature"]))
        path = sorted(k for k, s in d.w.items() if _base(s) == "minecraft:dirt_path")
        if path:
            rows.append((path[len(path) // 2], "minecraft:dirt_path", "the trampled approach"))
        ring = [k for k, s in d.w.items() if s != AIR and _base(s) in d.rec["boulder"]
                and d.r(k[0], k[2]) >= d.L["ring_radius"][0] - 2 and k[1] > d.ground(k[0], k[2])]
        if ring:
            k = max(ring, key=lambda k: (k[1] - d.ground(k[0], k[2]), k))
            rows.append((k, st(k), "the top of the tallest ring boulder"))
        skull = sorted(k for k, s in d.w.items() if _base(s) == "minecraft:skeleton_skull")
        if skull:
            rows.append((skull[0], "minecraft:skeleton_skull", "a skull"))
        for (x, y, z), b, what in rows:
            out.append("- `execute if block %d %d %d %s` -> `Test passed` (%s)" % (x, y, z, b, what))
        out.append("- `execute positioned %d %d %d if entity @e[type=cobblemon:pokemon,distance=..32]` -> `Test passed` "
                   "while the gulch's keeper holds this den's Mega (cobblers_gulch_mine, not this pack)" % (d.ax, d.ay, d.az))
        out.append("")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "plan", "probes"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    doc, dens = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, ds = files(doc, dens, g)
    if a.cmd == "plan":
        print("\n".join(report(ds)))
        print("steps (R9MD): %d" % len(placement_steps(doc, dens, g)))
        return 0
    if a.cmd == "probes":
        print("\n".join(probes(ds)))
        return 0
    write(out_files, a.out)
    n = sum(1 for rel, t in out_files.items() if rel.endswith(".mcfunction") for l in t.splitlines()
            if l and not l.startswith("#"))
    print("mega_dens: %d files -> %s (%d commands)" % (len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
