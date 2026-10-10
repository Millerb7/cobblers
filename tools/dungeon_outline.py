#!/usr/bin/env python
"""Room OUTLINES for the dungeon room kit (docs/mechanics/DUNGEON_ROOMS.md 1a): a room is no longer only a box.

An outline is a column mask over the room's bounding interior (ix0..ix1 x iz0..iz1) and a LIFT per open column (the
walking floor above the room's base floor; negative in a trench). tools/dungeon_rooms.py makes the RAW outline in
layout() (from the record, before the kind runs, so default anchors can be placed on it), and FINISHES it in
build_room() after the kind: every cell the kind or the route needs (doors, anchors, reserve boxes, the trail, the box
centre) is forced open and level, landings and stairs are forced to their lift, and only then is rock written, by
`replace air` fills, so a kind's own blocks are never removed.

Shapes: box, oval, l, t, gallery, cavern, split, ring (the table in DUNGEON_ROOMS.md 1a). Every generator is
deterministic from the rng it is given (dungeon_rooms.rng(d, room, "shape"), which a variant's seed re-rolls).
Nothing here decides whether a room can be walked: the walk check, the pit plug and the light check of
tools/dungeon_rooms.py run on the finished grid, and they are what proves it.
"""
from __future__ import annotations

import math

import numpy as np

SHAPES = ("box", "oval", "l", "t", "gallery", "cavern", "split", "ring")
SIDES = ("north", "south")


class Outline:
    """The open columns and their lift, in local indices i = x - ix0, j = z - iz0."""

    def __init__(self, room, shape="box", params=None):
        self.x0, self.x1, self.z0, self.z1 = room["ix0"], room["ix1"], room["iz0"], room["iz1"]
        self.nx, self.nz = self.x1 - self.x0 + 1, self.z1 - self.z0 + 1
        self.shape = shape
        self.params = dict(params or {})
        self.open_ = np.ones((self.nx, self.nz), dtype=bool)
        self.lift_ = np.zeros((self.nx, self.nz), dtype=np.int16)
        self.water = set()        # (x, z) cells whose feet level holds one block of water (a ring's pool)
        self.floors = list(room["floors"])
        self.finished = False

    # ---- queries (world coordinates) -------------------------------------------------------------------------
    def inside(self, x, z):
        return self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1

    def open(self, x, z):
        return self.inside(x, z) and bool(self.open_[x - self.x0, z - self.z0])

    def lift(self, x, z):
        return int(self.lift_[x - self.x0, z - self.z0]) if self.inside(x, z) else 0

    def base(self, x):
        return self.floors[min(max(x - self.x0, 0), len(self.floors) - 1)]

    def floor(self, x, z):
        """Feet level of the open column (x, z); None for rock or outside."""
        if not self.open(x, z):
            return None
        return self.base(x) + self.lift(x, z)

    def cells(self):
        ii, jj = np.nonzero(self.open_)
        return [(int(i) + self.x0, int(j) + self.z0) for i, j in zip(ii, jj)]

    def is_box(self):
        return bool(self.open_.all()) and not self.lift_.any()

    def sink(self):
        return max(0, -int(self.lift_.min())) if self.lift_.size else 0

    def summary(self):
        return {"shape": self.shape, "open": int(self.open_.sum()), "cells": int(self.open_.size),
                "lift_max": int(self.lift_.max()) if self.lift_.size else 0, "sink": self.sink()}

    def mirror_z(self):
        self.open_ = self.open_[:, ::-1].copy()
        self.lift_ = self.lift_[:, ::-1].copy()
        self.water = {(x, self.z0 + self.z1 - z) for x, z in self.water}


# ------------------------------------------------------------------------------------------------- generators


def _grid(o):
    i = np.arange(o.nx)[:, None].astype(float)
    j = np.arange(o.nz)[None, :].astype(float)
    return i, j


def shape_box(o, rg):
    pass


def shape_oval(o, rg):
    f = float(o.params.get("fill", 1.0))
    i, j = _grid(o)
    cx, cz = (o.nx - 1) / 2.0, (o.nz - 1) / 2.0
    rx, rz = max(2.0, f * o.nx / 2.0), max(2.0, f * o.nz / 2.0)
    o.open_ = ((i - cx) / rx) ** 2 + ((j - cz) / rz) ** 2 <= 1.0


def shape_l(o, rg):
    corner = o.params.get("corner", "ne")
    fx, fz = o.params.get("cut", [0.5, 0.5])
    ci, cj = int(round(o.nx * fx)), int(round(o.nz * fz))
    i, j = _grid(o)
    east = "e" in corner
    north = "n" in corner
    cut_i = (i >= o.nx - ci) if east else (i < ci)
    cut_j = (j < cj) if north else (j >= o.nz - cj)
    o.open_ = ~(cut_i & cut_j)


def shape_t(o, rg):
    bar = o.params.get("bar", "north")
    stem = float(o.params.get("stem", 0.4))
    bw = max(5, int(round(o.nz * float(o.params.get("bar_frac", 0.45)))))
    i, j = _grid(o)
    in_bar = (j < bw) if bar == "north" else (j >= o.nz - bw)
    half = max(2.5, o.nx * stem / 2.0)
    in_stem = np.abs(i - (o.nx - 1) / 2.0) <= half
    o.open_ = in_bar | (in_stem & np.ones_like(j, dtype=bool))


def shape_gallery(o, rg):
    band = float(o.params.get("band", 0.55))
    waves = float(o.params.get("waves", 1.5))
    phase = rg.uniform(0, 2 * math.pi)
    i, j = _grid(o)
    half = max(3.0, o.nz * band / 2.0)
    amp = max(0.0, (o.nz - 2 * half) / 2.0 - 0.5)
    zc = (o.nz - 1) / 2.0 + amp * np.sin(2 * math.pi * waves * i / max(1, o.nx - 1) + phase)
    o.open_ = np.abs(j - zc) <= half


def _blobs(o, rg, n, rmin, rmax):
    """A field that is high near n random disc centres (a cheap, smooth value noise)."""
    i, j = _grid(o)
    f = np.zeros((o.nx, o.nz))
    for _ in range(n):
        ci, cj = rg.uniform(0, o.nx - 1), rg.uniform(0, o.nz - 1)
        r = rg.uniform(rmin, rmax)
        f += np.exp(-((i - ci) ** 2 + (j - cj) ** 2) / (2 * r * r))
    return f


def _smooth(mask, passes=2):
    """Cellular automaton: a cell is open when 5 or more of its 3 x 3 are open (ragged edges, no single specks)."""
    m = mask.copy()
    for _ in range(passes):
        p = np.pad(m, 1, constant_values=False).astype(np.int8)
        s = sum(p[1 + a:p.shape[0] - 1 + a, 1 + b:p.shape[1] - 1 + b] for a in (-1, 0, 1) for b in (-1, 0, 1))
        m = s >= 5
    return m


def shape_cavern(o, rg):
    area = o.nx * o.nz
    # the body: a band along the room (where the trail runs) widened by blobs, so the walls are ragged, not straight
    i, j = _grid(o)
    zc = (o.nz - 1) / 2.0
    body = np.exp(-((j - zc) ** 2) / (2 * (0.30 * o.nz) ** 2))
    f = body + 0.9 * _blobs(o, rg, max(4, area // 90), 2.5, max(3.0, min(o.nx, o.nz) / 4.0))
    thr = np.quantile(f, 1.0 - float(o.params.get("open_frac", 0.72)))
    m = _smooth(f >= thr, 2)
    # alcoves: small round bays pushed into the rock at the edge of the open body
    for _ in range(int(o.params.get("alcoves", 4))):
        ci = rg.randint(3, max(3, o.nx - 4))
        side = rg.choice((0, 1))
        cj = rg.randint(1, max(1, o.nz // 5)) if side == 0 else rg.randint(min(o.nz - 2, o.nz - 1 - o.nz // 5), o.nz - 2)
        r = rg.uniform(1.6, 2.6)
        m |= ((i - ci) ** 2 + (j - cj) ** 2) <= r * r
    # rock pillars: small closed discs standing in the open floor, away from the edges
    n_p = int(round(area * float(o.params.get("pillars", 1.2)) / 100.0))
    for _ in range(n_p):
        ci, cj = rg.randint(3, max(3, o.nx - 4)), rg.randint(3, max(3, o.nz - 4))
        r = rg.choice((0.8, 1.2, 1.6))
        m &= ~(((i - ci) ** 2 + (j - cj) ** 2) <= r * r)
    o.open_ = m
    # an uneven floor: low humps of +1 (and +2 inside them when rough is 2), never a step of more than one
    rough = int(o.params.get("rough", 1))
    if rough > 0:
        h = _blobs(o, rg, max(2, area // 160), 2.0, 4.0)
        t1 = np.quantile(h, 0.78)
        lift = (h >= t1).astype(np.int16)
        if rough >= 2:
            t2 = np.quantile(h, 0.93)
            inner = _shrink(h >= t1) & (h >= t2)
            lift += inner.astype(np.int16)
        o.lift_ = lift


def _shrink(mask):
    p = np.pad(mask, 1, constant_values=False)
    out = mask.copy()
    for a, b in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        out &= p[1 + a:p.shape[0] - 1 + a, 1 + b:p.shape[1] - 1 + b]
    return out


def shape_split(o, rg):
    level = int(o.params.get("level", 4))
    depth = int(o.params.get("depth", 2))
    side = o.params.get("side", "north")
    frac = float(o.params.get("frac", 0.35))
    tw = max(3, int(round(o.nz * frac)))
    lift = np.zeros((o.nx, o.nz), dtype=np.int16)
    # the terrace: rows next to the chosen long wall; the trench: the two rows below its edge
    if side == "north":
        t_rows = range(0, tw)
        d_rows = range(tw, min(o.nz, tw + 2))
        step_dir = 1
        edge = tw - 1
    else:
        t_rows = range(o.nz - tw, o.nz)
        d_rows = range(max(0, o.nz - tw - 2), o.nz - tw)
        step_dir = -1
        edge = o.nz - tw
    for j in t_rows:
        lift[:, j] = level
    a, b = 6, o.nx - 7
    for i in range(o.nx):
        if a <= i <= b:
            dd = min(depth, i - a + 1, b - i + 1)        # the trench ramps down from each end: walkable in and out
            for j in d_rows:
                lift[i, j] = -dd
    # the stairs up to the terrace: 3 wide at the west end (before the trench), one block a step, out from its edge
    for i in range(2, 5):
        for k in range(1, level):
            j = edge + step_dir * k
            if 0 <= j < o.nz:
                lift[i, j] = level - k
    o.lift_ = lift


def shape_ring(o, rg):
    feature = o.params.get("feature", "rock")
    i, j = _grid(o)
    cx, cz = (o.nx - 1) / 2.0, (o.nz - 1) / 2.0
    R = max(3.5, float(o.params.get("radius", 0.3)) * min(o.nx, o.nz))
    d = np.sqrt((i - cx) ** 2 + (j - cz) ** 2)
    band = (d >= R) & (d <= R + 1.6)
    gaps = (np.abs(i - cx) <= 1.5) | (np.abs(j - cz) <= 1.5)       # four ways in, on the axes
    if feature == "rock":
        o.open_ = ~(band & ~gaps)
    elif feature == "columns":
        ang = np.arctan2(j - cz, i - cx)
        slots = np.abs(((ang / (2 * math.pi) * 12) % 1.0) - 0.5) > 0.32
        o.open_ = ~(band & ~gaps & slots)
    else:   # pool: a ring of one-deep water to wade, the plaza in the middle dry
        lift = np.zeros((o.nx, o.nz), dtype=np.int16)
        lift[band & ~gaps] = -1
        o.lift_ = lift
        ii, jj = np.nonzero(band & ~gaps)
        o.water = {(int(a) + o.x0, int(b) + o.z0) for a, b in zip(ii, jj)}


GENERATORS = {"box": shape_box, "oval": shape_oval, "l": shape_l, "t": shape_t, "gallery": shape_gallery,
              "cavern": shape_cavern, "split": shape_split, "ring": shape_ring}


def shape_sink(shape, params):
    """How far below the base floor the shape cuts (known before the outline is made: layout needs it for y_lo)."""
    params = params or {}
    if shape == "split":
        return int(params.get("depth", 2))
    if shape == "ring" and params.get("feature") == "pool":
        return 1
    return 0


def shape_lift_max(shape, params):
    params = params or {}
    if shape == "split":
        return int(params.get("level", 4))
    if shape == "cavern":
        return max(0, int(params.get("rough", 1)))
    return 0


def make(room, shape, params, rg, mirror=False):
    o = Outline(room, shape, params)
    if shape not in GENERATORS:
        raise ValueError("unknown shape %r" % shape)
    GENERATORS[shape](o, rg)
    if mirror:
        o.mirror_z()
    return o


# ------------------------------------------------------------------------------------------------- finishing


def finish(o, keep, forced):
    """keep: (x, z) cells forced open at lift 0 (doors' approach, anchors, reserve, trail, the centre). forced:
    {(x, z): lift} for landings and stairs, which win over everything. Water under a forced or kept cell is dropped."""
    for (x, z) in keep:
        if o.inside(x, z):
            o.open_[x - o.x0, z - o.z0] = True
            o.lift_[x - o.x0, z - o.z0] = 0
            o.water.discard((x, z))
    for (x, z), h in forced.items():
        if o.inside(x, z):
            o.open_[x - o.x0, z - o.z0] = True
            o.lift_[x - o.x0, z - o.z0] = h
            o.water.discard((x, z))
    # a pool cell must sit in a trench (lift -1) to hold one block of water at the feet
    o.water = {(x, z) for (x, z) in o.water if o.open(x, z) and o.lift(x, z) == -1}
    o.finished = True


def ops(o, room, theme, fill):
    """The blocks the finished outline writes: rock (the hull's wall) in closed columns from the base floor to the
    ceiling, raised floor (the hull's floor) under lifted columns, air down into trenches, water in a pool. Every rock
    and raised-floor fill is `replace minecraft:air`: a kind's block is never overwritten. Runs are merged along z."""
    wall, floor_b = theme["hull"]["wall"], theme["hull"]["floor"]
    ceil = room["ceil_y"]
    out = []
    for i in range(o.nx):
        x = o.x0 + i
        base = o.base(x)
        j = 0
        while j < o.nz:
            op_ = o.open_[i, j]
            h = int(o.lift_[i, j])
            e = j
            while e + 1 < o.nz and o.open_[i, e + 1] == op_ and int(o.lift_[i, e + 1]) == h:
                e += 1
            z0, z1 = o.z0 + j, o.z0 + e
            if not op_:
                out.append(fill((x, base, z0, x, ceil - 1, z1), wall, "replace minecraft:air"))
            elif h > 0:
                out.append(fill((x, base, z0, x, base + h - 1, z1), floor_b, "replace minecraft:air"))
            elif h < 0:
                out.append(fill((x, base + h, z0, x, base - 1, z1), "minecraft:air"))
            j = e + 1
    for (x, z) in sorted(o.water):
        out.append(("set", (x, o.base(x) - 1, z), "minecraft:water"))
    return out
