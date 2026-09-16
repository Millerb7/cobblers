#!/usr/bin/env python
"""Raise the mountains without moving anything anyone has built.

The world runs y10..y200 on a straight line from the heightmap, so the tallest peak is y201 while the world tree
reaches y535 -- five times its height. The fix is not a new straight line: that rescales every elevation, moves the
coast, regrades every river, and (measured) lifts Foothill Woods to y161 and the tree top to y580 against a y575
ceiling. Instead the line stays and the CURVE goes into the image: identity below the threshold, gain above it.

    g(y) = 1 + (G-1) * smoothstep((y-T)/W)      the vertical gain, C1 at both ends of the blend
    y'   = y + (G-1) * W * (s^3 - s^4/2)        its integral, s = clamp((y-T)/W, 0, 1)
    y'   = y + (G-1)*W/2 + (G-1)*(y - T - W)    above the blend, where the gain is flat at G

T is not a free choice. Everything authored sits below y145: the highest elder tree is y144.4, the highest water
anywhere y127.0, the cavern surface y134.7, the grove y114.9-118.1, and the ridge that governs the sightline from
Pallet to the world tree y139.0. y145 is also the p90 of land elevation. Six independent constraints inside six
blocks, so it is the map saying where authored ground ends, not a guess.

WorldPainter imports on a straight line, so the curve lives in the image and the import line is re-fitted to the
new range. That round trip is 16-bit, and it is NOT free: a plain nearest-value quantisation moved 48,568 land
columns below the threshold by a whole block, because a column sitting 0.002 under an integer gets pushed across
it. So the quantiser here is floor-preserving -- of the two image levels bracketing the target it takes the one
that keeps the column's integer elevation, and only then the nearer one. Low ground comes out bit for bit.

  python tools/rescale.py --source-root <root> [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path

import numpy as np
from PIL import Image

import terrain as T_

ROOT = Path(__file__).resolve().parent.parent
THRESHOLD = 145.0
BLEND = 55.0
GAIN = 5.0
FULL = 65535.0
BAND = 512                      # rows at a time: the full map in float64 is 536 MB an array
COARSE = 16                     # the landform base is measured at 16-block cells, then smoothed and resampled
BASE_PASSES = 4


def landform_base(y, coarse=COARSE, passes=BASE_PASSES):
    """The broad shape of the land, with local relief taken out.

    The gain must be applied to the LANDFORM, not to every column. Applying it per column multiplies local relief
    too: measured, the largest adjacent step went from 22.8 blocks to 96.8, with 218 steps over 40 -- sheer
    one-column walls rather than mountains. Smoothing at 16-block cells and resampling gives a base that follows
    massifs and ignores cliffs, so the displacement is nearly equal either side of a crag and the crag keeps its
    own size.
    """
    n = y.shape[0]
    small = y.reshape(n // coarse, coarse, n // coarse, coarse).mean(axis=(1, 3))
    for _ in range(passes):
        q = np.pad(small, 1, mode="edge")
        small = 0.36 * small + 0.16 * (q[:-2, 1:-1] + q[2:, 1:-1] + q[1:-1, :-2] + q[1:-1, 2:])
    img = Image.fromarray(small.astype(np.float32), mode="F").resize((n, n), Image.BILINEAR)
    return np.asarray(img, dtype=np.float32)


def gain_curve(y, t=THRESHOLD, w=BLEND, g=GAIN):
    """Elevation in -> elevation out. Identity at or below t."""
    s = np.clip((y - t) / w, 0.0, 1.0)
    out = y + (g - 1.0) * w * (s ** 3 - s ** 4 / 2.0)
    over = y > t + w
    out = np.where(over, y + (g - 1.0) * w / 2.0 + (g - 1.0) * (y - t - w), out)
    return np.where(y <= t, y, out)


def y_of_h(h, imp, high_out):
    return imp["low_out"] + np.minimum((h / FULL - imp["low_in"]) / (imp["high_in"] - imp["low_in"]), 1.0) \
        * (high_out - imp["low_out"])


def h_of_y(y, imp, high_out):
    return (imp["low_in"] + (y - imp["low_out"]) / (high_out - imp["low_out"])
            * (imp["high_in"] - imp["low_in"])) * FULL


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T_.add_common_args(p)
    p.add_argument("--apply", action="store_true", help="write the new heightmap")
    a = p.parse_args(argv)
    heights, world = T_.load_from_args(a)
    imp = world["import"]
    y_old_all = heights.astype(np.float32)
    base_all = landform_base(y_old_all)
    print("landform base: min %.1f max %.1f (vs terrain max %.1f)" % (base_all.min(), base_all.max(), y_old_all.max()))

    peak_new = float((y_old_all + np.where(y_old_all > THRESHOLD, 1.0, 0.0) *
                      (gain_curve(base_all.astype(np.float64)) - base_all)).max())
    high_out = float(math.ceil(peak_new))
    land_all = y_old_all > imp["water_level"]
    print("land %d of %d columns (%.1f%%); peak y%.2f -> y%.2f; new import line high_out %d (was %d)"
          % (land_all.sum(), y_old_all.size, 100 * land_all.mean(), y_old_all.max(), peak_new,
             high_out, imp["high_out"]))
    for probe in (62, 100, 117.7, 139, 145, 150, 160, 170, 180, 190, 200):
        print("   y%-6.1f -> y%.2f" % (probe, float(gain_curve(np.array([float(probe)]))[0])))

    n = y_old_all.shape[0]
    out = np.zeros_like(y_old_all, dtype=np.uint16)
    moved_low = moved_low_land = 0
    worst_err = 0.0
    examples = []
    for r0 in range(0, n, BAND):
        yo = y_old_all[r0:r0 + BAND].astype(np.float64)
        bo = base_all[r0:r0 + BAND].astype(np.float64)
        # displacement comes from the smoothed landform; the gate is the column's own elevation, so a column at
        # or below the threshold moves exactly zero no matter what the massif around it is doing
        gate = np.clip((yo - THRESHOLD) / BLEND, 0.0, 1.0)
        gate = gate * gate * (3.0 - 2.0 * gate)
        yn = yo + gate * (gain_curve(bo) - bo)
        h = np.clip(h_of_y(yn, imp, high_out), 0.0, FULL)
        lo = np.floor(h)
        hi = np.minimum(lo + 1.0, FULL)
        y_lo, y_hi = y_of_h(lo, imp, high_out), y_of_h(hi, imp, high_out)
        # nearest by default
        pick_hi = np.abs(y_hi - yn) < np.abs(y_lo - yn)
        # but below the threshold, integer elevation must not move
        low = yo <= THRESHOLD
        keep = np.floor(yo)
        lo_ok, hi_ok = np.floor(y_lo) == keep, np.floor(y_hi) == keep
        pick_hi = np.where(low & lo_ok & ~hi_ok, False, pick_hi)
        pick_hi = np.where(low & hi_ok & ~lo_ok, True, pick_hi)
        chosen = np.where(pick_hi, hi, lo)
        y_rt = np.where(pick_hi, y_hi, y_lo)
        out[r0:r0 + BAND] = chosen.astype(np.uint16)
        worst_err = max(worst_err, float(np.abs(y_rt - yn).max()))
        bad = low & (np.floor(y_rt) != keep)
        moved_low += int(bad.sum())
        land = yo > imp["water_level"]
        moved_low_land += int((bad & land).sum())
        if bad.any() and len(examples) < 3:
            zz, xx = np.where(bad)
            examples.append((int(xx[0]), int(r0 + zz[0]), float(yo[zz[0], xx[0]]), float(y_rt[zz[0], xx[0]])))

    print("\nround-trip error: max %.5f blocks" % worst_err)
    print("columns at or below y%.0f whose INTEGER elevation changes: %d (land: %d)"
          % (THRESHOLD, moved_low, moved_low_land))
    for x, z, yo_, yr in examples:
        print("   (%d, %d): y%.4f -> y%.4f" % (x, z, yo_, yr))
    if moved_low == 0:
        print("   LOW GROUND IS BIT FOR BIT")

    y_check = y_of_h(out.astype(np.float64), imp, high_out)
    print("\nresulting elevation: min %.2f p50 %.2f p90 %.2f max %.2f"
          % (y_check.min(), np.percentile(y_check, 50), np.percentile(y_check[land_all], 90), y_check.max()))

    if not a.apply:
        print("\n(dry run -- pass --apply to write the heightmap)")
        return
    root = Path(a.source_root or world["source_root"])
    out_path = root / "land_8k_16_rescaled_b145.png"
    Image.fromarray(out, mode="I;16").save(out_path)
    print("\nwrote %s\n  sha256 %s\n  %d bytes"
          % (out_path, hashlib.sha256(out_path.read_bytes()).hexdigest(), out_path.stat().st_size))
    print("  import line: low_in %.9f high_in %.9f low_out %.6f high_out %d"
          % (imp["low_in"], imp["high_in"], imp["low_out"], high_out))


if __name__ == "__main__":
    main()
