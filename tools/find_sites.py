#!/usr/bin/env python
"""Find buildable sites: flat areas above sea level, ranked.

Produces candidates. A human picks. Nothing here decides where a town goes.

  python tools/find_sites.py --world tests/fixtures/terrain/world.json \
      --min-size 16 --max-slope 5 --top 10
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import terrain as T


def buildable_mask(heights, world, max_slope_deg, above_sea, max_y=None):
    slope = T.slope_degrees(heights)
    sea = T.sea_level(world)
    mask = (slope <= max_slope_deg) & (heights >= sea + above_sea)
    if max_y is not None:
        # Ground clipped at the height ceiling is flat by accident, not by
        # design, and would otherwise rank above every real site.
        mask &= heights <= max_y
    return mask, slope


def run_lengths(m, axis):
    """Length of the run of trues ending at each cell, along one axis.

    Vectorised cumsum-with-reset, so it scales to an 8192-square map.
    """
    cs = np.cumsum(m, axis=axis, dtype=np.int32)
    reset = np.where(m, 0, cs)
    reset = np.maximum.accumulate(reset, axis=axis)
    return cs - reset


def largest_squares(mask, start_row=0, dp=None):
    """Size of the largest all-true square whose bottom-right is (z, x).

    Uses dp[z,x] = min(dp[z-1,x-1] + 1, up[z,x], left[z,x]). Unlike the
    textbook recurrence this has no dependence on dp[z,x-1], so each row is a
    single vectorised operation and only the row loop remains in Python.
    """
    m = mask.astype(np.int32)
    up = run_lengths(m, 0)
    left = run_lengths(m, 1)
    if dp is None:
        dp = np.zeros(mask.shape, dtype=np.int32)
    width = mask.shape[1]
    for z in range(start_row, mask.shape[0]):
        # A missing diagonal predecessor (top row, left column) counts as a
        # square of side 0, so the term is 0 + 1 = 1, never 0.
        diag = np.ones(width, dtype=np.int32)
        if z > 0:
            diag[1:] = dp[z - 1, :-1] + 1
        dp[z] = np.minimum(np.minimum(diag, up[z]), left[z])
    return dp


def extract_sites(mask, heights, slope, min_size, top, bbox=None):
    """Greedy, largest first, never overlapping.

    Take the largest square, mark it unbuildable, and recompute only the rows
    it can affect. Ties break row-major, so the result is deterministic.
    """
    work = mask.copy()
    dp = largest_squares(work)
    sites = []
    while len(sites) < top:
        flat = int(np.argmax(dp))
        z1, x1 = divmod(flat, dp.shape[1])
        size = int(dp[z1, x1])
        if size < min_size:
            break
        x0, z0 = x1 - size + 1, z1 - size + 1
        work[z0:z1 + 1, x0:x1 + 1] = False
        dp = largest_squares(work, start_row=z0, dp=dp)
        patch_h = heights[z0:z1 + 1, x0:x1 + 1]
        patch_s = slope[z0:z1 + 1, x0:x1 + 1]
        off_x, off_z = (bbox[0], bbox[1]) if bbox else (0, 0)
        sites.append({
            "rank": len(sites) + 1,
            "size": size,
            "min_x": x0 + off_x, "min_z": z0 + off_z,
            "max_x": x1 + off_x, "max_z": z1 + off_z,
            "center": {"x": (x0 + x1) // 2 + off_x, "z": (z0 + z1) // 2 + off_z},
            "height": {
                "min": round(float(patch_h.min()), 2),
                "max": round(float(patch_h.max()), 2),
                "mean": round(float(patch_h.mean()), 2),
                "range": round(float(patch_h.max() - patch_h.min()), 2),
            },
            "slope_degrees": {
                "mean": round(float(patch_s.mean()), 3),
                "max": round(float(patch_s.max()), 3),
            },
        })
        if len(sites) >= top:
            break
    return sites


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--min-size", type=int, default=16, help="minimum square side in blocks")
    p.add_argument("--max-slope", type=float, default=5.0, help="max slope in degrees")
    p.add_argument("--above-sea", type=float, default=1.0,
                   help="minimum height above sea level in blocks")
    p.add_argument("--max-y", type=float, default=None,
                   help="exclude ground above this height, e.g. summits clipped at the ceiling")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--bbox", default=None, metavar="X0,Z0,X1,Z1",
                   help="restrict the search to this block box (inclusive)")
    a = p.parse_args(argv)

    try:
        heights, world = T.load_from_args(a)
    except T.TerrainUnavailable as exc:
        raise SystemExit("terrain unavailable: %s" % exc)

    bbox = None
    if a.bbox:
        x0, z0, x1, z1 = (int(v) for v in a.bbox.split(","))
        bbox = (x0, z0, x1, z1)
        heights = heights[z0:z1 + 1, x0:x1 + 1]

    mask, slope = buildable_mask(heights, world, a.max_slope, a.above_sea, a.max_y)
    sites = extract_sites(mask, heights, slope, a.min_size, a.top, bbox)

    payload = {
        "schema": "cobblers.derived.sites/1",
        "parameters": {
            "min_size": a.min_size, "max_slope_degrees": a.max_slope, "max_y": a.max_y,
            "above_sea": a.above_sea, "top": a.top, "bbox": a.bbox,
        },
        "source": T.provenance(world, a.world),
        "buildable_fraction": round(float(mask.mean()), 4),
        "site_count": len(sites),
        "sites": sites,
    }
    out = Path(a.out) if a.out else T.ROOT / "derived" / "sites" / "sites.json"
    T.write_json(out, payload)
    print("%d site(s), buildable %.1f%% of the searched area -> %s"
          % (len(sites), 100 * mask.mean(), out))
    for s in sites[:10]:
        print("  #%-2d %3d x %-3d at (%4d, %4d)  y %.0f-%.0f  slope max %.2f deg"
              % (s["rank"], s["size"], s["size"], s["center"]["x"], s["center"]["z"],
                 s["height"]["min"], s["height"]["max"], s["slope_degrees"]["max"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
