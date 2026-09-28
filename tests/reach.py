"""Whether a player standing just outside a ward can reach a guarded block: shared by tests/test_gulch_mine.py and
contract C6 in tests/test_system_contracts.py, which asked the same question in pure Python (147 s and 131 s).

The formula is theirs, vectorised: for every feet position on the lattice of the ward's position ranges, one step
outside each face, the eyes are `eye` above the feet, and a block (a unit cube at its min corner) is reached when the
eyes are within `reach` of the nearest point of the cube. The squares are summed x, y, z in that order and rooted, as
math.sqrt(sum(...)) did, so the distances are the same doubles.
"""
from __future__ import annotations

import itertools

import numpy as np


def reach_from_outside(pos, blocks, eye, reach, chunk=512):
    """[(distance, feet)] for every feet position just outside the ward (`pos`: {"x"|"y"|"z": {"min", "max"}}) whose
    eyes are within `reach` of any of `blocks` (min corners)."""
    b = np.asarray(sorted(blocks), dtype=np.float64)
    if not len(b):
        return []
    lattice = {a: [pos[a]["min"] + k for k in range(int(pos[a]["max"] - pos[a]["min"]) + 1)] for a in "xyz"}
    feet = []
    for a in "xyz":
        for out in (pos[a]["min"] - 1e-3, pos[a]["max"] + 1e-3):
            feet.extend(itertools.product(*[lattice[c] if c != a else [out] for c in "xyz"]))
    hits = []
    for i in range(0, len(feet), chunk):
        part = feet[i:i + chunk]
        e = np.asarray(part, dtype=np.float64)
        e[:, 1] += eye
        e = e[:, None, :]                                     # (feet, 1, 3) against (blocks, 3)
        gap = np.maximum(np.maximum(b[None] - e, 0.0), e - (b[None] + 1))
        d = np.sqrt(gap[..., 0] ** 2 + gap[..., 1] ** 2 + gap[..., 2] ** 2).min(axis=1)
        hits.extend((float(dd), p) for dd, p in zip(d, part) if dd <= reach)
    return hits
