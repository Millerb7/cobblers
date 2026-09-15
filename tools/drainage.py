#!/usr/bin/env python
"""Drainage on a coarse height grid: priority flood, D8 flow directions, accumulation.

Priority flood (Barnes et al. 2014, with an epsilon so flats drain) starts from open sea and
fills every closed basin to its spill, so every land cell drains to the sea. D8 then sends each
cell to its steepest lower neighbour on the filled surface, and accumulation counts the cells
upstream of each cell. Multiply by the cell area for catchment.

Used by tools/grade_rivers.py to size river channels from the ground they drain.
"""
from __future__ import annotations

import heapq

import numpy as np

NB = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))
EPS = 1e-4


def priority_flood(height, open_sea, sea_level):
    """Filled surface and the order cells were settled in (lowest drain first)."""
    h, w = height.shape
    filled = np.array(height, dtype=np.float64)
    filled[open_sea] = np.maximum(filled[open_sea], sea_level)
    closed = open_sea.copy()
    border = np.zeros_like(open_sea)
    border[1:, :] |= open_sea[:-1, :]
    border[:-1, :] |= open_sea[1:, :]
    border[:, 1:] |= open_sea[:, :-1]
    border[:, :-1] |= open_sea[:, 1:]
    # only the sea is an outlet; the map edge is one only when there is no sea at all, so a land hollow on the
    # edge fills and drains like any other (d8 treats beyond the edge as a wall)
    seeds = border & ~open_sea
    if not open_sea.any():
        seeds = np.zeros_like(open_sea)
        seeds[0, :] = seeds[-1, :] = seeds[:, 0] = seeds[:, -1] = True
    pq = []
    fl = filled.ravel().tolist()
    for i in np.flatnonzero(seeds):
        fl[i] = max(fl[i], sea_level)
        pq.append((fl[i], int(i)))
    closed_l = (closed | seeds).ravel().tolist()
    heapq.heapify(pq)
    order = []
    while pq:
        v, i = heapq.heappop(pq)
        order.append(i)
        z, x = divmod(i, w)
        for dz, dx in NB:
            nz, nx = z + dz, x + dx
            if 0 <= nz < h and 0 <= nx < w:
                j = nz * w + nx
                if not closed_l[j]:
                    closed_l[j] = True
                    if fl[j] <= v:
                        fl[j] = v + EPS
                    heapq.heappush(pq, (fl[j], j))
    return np.array(fl).reshape(h, w), order


def d8(filled, open_sea):
    """Index into NB of each cell's steepest downhill neighbour; -1 for sea and sinks."""
    h, w = filled.shape
    pad = np.pad(filled, 1, constant_values=np.inf)
    best = np.zeros((h, w))
    dirs = np.full((h, w), -1, np.int8)
    for k, (dz, dx) in enumerate(NB):
        nb = pad[1 + dz:h + 1 + dz, 1 + dx:w + 1 + dx]
        drop = (filled - nb) / (1.4142135623730951 if dz and dx else 1.0)
        upd = drop > best
        best[upd] = drop[upd]
        dirs[upd] = k
    dirs[open_sea] = -1
    return dirs


def accumulation(dirs, order):
    """Cells draining through each cell, itself included. order: cells from priority_flood."""
    h, w = dirs.shape
    acc = np.ones(h * w)
    dl = dirs.ravel()
    offs = [dz * w + dx for dz, dx in NB]
    for i in reversed(order):
        k = dl[i]
        if k >= 0:
            acc[i + offs[k]] += acc[i]
    return acc.reshape(h, w)


def receiver(dirs, z, x):
    k = int(dirs[z, x])
    if k < 0:
        return None
    dz, dx = NB[k]
    return z + dz, x + dx
