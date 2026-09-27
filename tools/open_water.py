#!/usr/bin/env python
"""The open sea, by distance from land, from the canonical heightmap: the zones surface exhaustion reads.

A 16-block cell is land if any column in it is at or above sea level. The sea is every cell below it that is
connected to the world border (so inland lakes, whose basins dip under sea level but are ringed by land, are not
sea). Each sea cell gets a band by its Chebyshev distance from the nearest land cell:

  shallows   under `shallow_blocks` (96): free swimming
  open       under `deep_blocks` (256): exhaustion builds
  deep       beyond: exhaustion builds twice as fast

The bands are merged into rectangles (row runs, then stacked runs) so a datapack can test a player against a few
hundred boxes. Positions come from the heightmap (tools/ground.py), never from a world; the 1024-block margin
outside the heightmap is sea by construction (docs/STATE.md 'World facts').

  python tools/open_water.py            # print the band areas and box counts
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

CELL = 16
WORLD_MIN, WORLD_MAX = -1024, 9215          # the playable limits inside the 10,240-block border
SEA_LEVEL = 62


def cells(ground=None):
    """(land mask, sea mask, x0 of cell 0) on the CELL grid over the playable world."""
    import ground as G
    g = ground or G.load()
    n = (WORLD_MAX - WORLD_MIN + 1) // CELL
    land = np.zeros((n, n), dtype=bool)                   # [cz, cx]
    h = np.round(g.heights)
    hz, hx = h.shape
    # the heightmap's own cells (origin 0, 0): max ground per cell
    k = (hz // CELL, hx // CELL)
    cellmax = h[:k[0] * CELL, :k[1] * CELL].reshape(k[0], CELL, k[1], CELL).max(axis=(1, 3))
    off = (g.oz - WORLD_MIN) // CELL, (g.ox - WORLD_MIN) // CELL
    land[off[0]:off[0] + k[0], off[1]:off[1] + k[1]] = cellmax >= SEA_LEVEL
    below = ~land
    # the sea: below sea level and connected to the border (4-connected flood fill)
    sea = np.zeros_like(below)
    stack = [(z, x) for z in range(n) for x in (0, n - 1) if below[z, x]] + \
            [(z, x) for x in range(n) for z in (0, n - 1) if below[z, x]]
    for z, x in stack:
        sea[z, x] = True
    while stack:
        z, x = stack.pop()
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = z + dz, x + dx
            if 0 <= a < n and 0 <= b < n and below[a, b] and not sea[a, b]:
                sea[a, b] = True
                stack.append((a, b))
    return land, sea


def dilate(mask, r):
    """Chebyshev dilation by r cells (separable max over rows, then columns)."""
    out = mask.copy()
    for axis in (0, 1):
        acc = out.copy()
        for s in range(1, r + 1):
            acc |= np.roll(out, s, axis=axis) & _valid(out.shape, s, axis, +1)
            acc |= np.roll(out, -s, axis=axis) & _valid(out.shape, s, axis, -1)
        out = acc
    return out


def _valid(shape, s, axis, sign):
    v = np.ones(shape, dtype=bool)
    if axis == 0:
        if sign > 0:
            v[:s, :] = False
        else:
            v[-s:, :] = False
    else:
        if sign > 0:
            v[:, :s] = False
        else:
            v[:, -s:] = False
    return v


def bands(shallow_blocks=96, deep_blocks=256, ground=None):
    """{"open": mask, "deep": mask} over the cell grid."""
    land, sea = cells(ground)
    near = dilate(land, shallow_blocks // CELL)
    mid = dilate(land, deep_blocks // CELL)
    return {"open": sea & mid & ~near, "deep": sea & ~mid}


def rectangles(mask):
    """Greedy merge of a cell mask into [x0, z0, x1, z1] block boxes (inclusive)."""
    n = mask.shape[0]
    runs = {}                                           # (x0, x1) -> list of rows, stacked while contiguous
    boxes = []
    open_runs = {}
    for z in range(n):
        row, x = mask[z], 0
        current = set()
        while x < n:
            if row[x]:
                x0 = x
                while x < n and row[x]:
                    x += 1
                current.add((x0, x - 1))
            else:
                x += 1
        for key in list(open_runs):
            if key not in current:
                z0 = open_runs.pop(key)
                boxes.append((key[0], z0, key[1], z - 1))
        for key in current:
            open_runs.setdefault(key, z)
    for key, z0 in open_runs.items():
        boxes.append((key[0], z0, key[1], n - 1))
    return sorted([[WORLD_MIN + a * CELL, WORLD_MIN + b * CELL, WORLD_MIN + (c + 1) * CELL - 1, WORLD_MIN + (d + 1) * CELL - 1]
                   for a, b, c, d in boxes])


def zones(shallow_blocks=96, deep_blocks=256, ground=None):
    b = bands(shallow_blocks, deep_blocks, ground)
    return {k: rectangles(v) for k, v in b.items()}


def main():
    z = zones()
    for k, v in z.items():
        area = sum((x1 - x0 + 1) * (z1 - z0 + 1) for x0, z0, x1, z1 in v)
        print("%-5s %4d boxes, %.1f km2" % (k, len(v), area / 1e6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
