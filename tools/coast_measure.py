#!/usr/bin/env python
"""Measure the coast: grade, shelf and terracing along profiles normal to the shoreline.

The shoreline is the edge of open sea (sea-level water connected to the map edge). Sample points are one
shoreline column per SPACING x SPACING cell. At each, the seaward normal comes from the smoothed height
gradient, and a profile is read along it from OFFSHORE blocks out to INLAND blocks in (bilinear, 1-block steps).

Per profile:
  run_to_+N     horizontal blocks from the shoreline to N blocks above sea level (N = 2, 4, 8, 16)
  grade_0_4     rise per horizontal block over the first 4 blocks of rise (1/12 is a beach, 1/2 a bank, 1 a cliff)
  depth_at_-N   horizontal blocks from the shoreline to N blocks below sea level (N = 3, 8, 15)
  steps         terraces in the first 16 blocks of rise: treads (8+ blocks with under 0.06 rise per block)
                each followed by a riser (0.6+ blocks within 3), while the mean grade there is gentle enough that
                a smooth slope would show no treads
  flat_share    share of that stretch that is tread

  python tools/coast_measure.py --source-root <root> --out derived/coast/profiles.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import terrain as T

SPACING = 32
OFFSHORE = 250
INLAND = 300


def open_sea(heights, sea):
    wet = (heights < sea).astype(np.uint8) * 255
    img = Image.fromarray(np.pad(wet, 1, constant_values=255)).copy()      # an array-backed image does not flood fill
    ImageDraw.floodfill(img, (0, 0), 128)
    return (np.array(img) == 128)[1:-1, 1:-1]


def box1d(a, r, axis):
    a = np.moveaxis(a, axis, 0)
    p = np.concatenate([np.repeat(a[:1], r + 1, axis=0), a, np.repeat(a[-1:], r, axis=0)], axis=0)
    c = np.cumsum(p, axis=0, dtype=np.float64)
    out = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
    return np.moveaxis(out.astype(np.float32), 0, axis)


def smooth(h, radius=6):
    """Approximate Gaussian: three separable box passes (sigma about radius)."""
    r = max(1, int(round(radius * 0.8)))
    out = h.astype(np.float32)
    for _ in range(3):
        out = box1d(box1d(out, r, 0), r, 1)
    return out


def bilinear(h, xs, zs):
    nz, nx = h.shape
    x0 = np.clip(np.floor(xs).astype(int), 0, nx - 2)
    z0 = np.clip(np.floor(zs).astype(int), 0, nz - 2)
    fx, fz = np.clip(xs - x0, 0, 1), np.clip(zs - z0, 0, 1)
    return (h[z0, x0] * (1 - fx) * (1 - fz) + h[z0, x0 + 1] * fx * (1 - fz)
            + h[z0 + 1, x0] * (1 - fx) * fz + h[z0 + 1, x0 + 1] * fx * fz)


def shoreline_samples(sea_mask, spacing=SPACING):
    land = ~sea_mask
    edge = land.copy()
    edge[1:-1, 1:-1] = land[1:-1, 1:-1] & (sea_mask[:-2, 1:-1] | sea_mask[2:, 1:-1] | sea_mask[1:-1, :-2] | sea_mask[1:-1, 2:])
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = False
    zs, xs = np.nonzero(edge)
    cell = {}
    for x, z in zip(xs, zs):
        cell.setdefault((x // spacing, z // spacing), (x, z))
    return sorted(cell.values(), key=lambda p: (p[1], p[0]))


def profile_metrics(prof, sea):
    """prof[i] is the height at signed distance i - OFFSHORE (positive inland)."""
    d = np.arange(len(prof)) - OFFSHORE
    inland = prof[OFFSHORE:]
    out = {}
    for n in (2, 4, 8, 16):
        idx = np.nonzero(inland >= sea + n)[0]
        out["run_to_+%d" % n] = int(idx[0]) if len(idx) else None
    r4 = out["run_to_+4"]
    out["grade_0_4"] = round(4.0 / max(r4, 1), 3) if r4 is not None else None
    off = prof[:OFFSHORE + 1][::-1]
    for n in (3, 8, 15):
        idx = np.nonzero(off <= sea - n)[0]
        out["depth_at_-%d" % n] = int(idx[0]) if len(idx) else None
    # terraces within the first 16 blocks of rise
    r16 = out["run_to_+16"] or len(inland) - 1
    seg = inland[:r16 + 1]
    steps, tread_len = 0, 0
    if len(seg) > 12:
        rise = np.diff(seg)
        i = 0
        while i < len(rise):
            j = i
            while j < len(rise) and rise[j] < 0.06:
                j += 1
            if j - i >= 8 and j < len(rise):
                riser = seg[min(j + 3, len(seg) - 1)] - seg[j]
                if riser >= 0.6:
                    steps += 1
                    tread_len += j - i
            i = max(j, i + 1)
        mean_grade = 16.0 / max(r16, 1)
        out["steps"] = steps if mean_grade < 0.5 else 0
        out["flat_share"] = round(tread_len / max(len(rise), 1), 2) if mean_grade < 0.5 else 0.0
    else:
        out["steps"], out["flat_share"] = 0, 0.0
    return out


def measure(heights, sea, regions_doc=None, spacing=SPACING):
    sea_mask = open_sea(heights, sea)
    sm = smooth(heights, 6)
    gz, gx = np.gradient(sm)
    pts = shoreline_samples(sea_mask, spacing)
    sub_lookup = None
    if regions_doc:
        n = heights.shape[0]
        img = Image.new("I", (n, n), 0)
        d = ImageDraw.Draw(img)
        subs = regions_doc["subregions"]
        for i, s in enumerate(subs, start=1):
            for ring in s["polygons"]:
                d.polygon([tuple(q) for q in ring], fill=i)
        sub_idx = np.asarray(img)
        # coastal columns often fall just outside simplified polygons: take the nearest sub-region within 64 blocks
        sub_lookup = (sub_idx, subs)
    rows = []
    t = np.arange(-OFFSHORE, INLAND + 1, dtype=np.float32)
    for x, z in pts:
        nx, nz = float(gx[z, x]), float(gz[z, x])
        L = math.hypot(nx, nz)
        if L < 1e-4:
            continue
        nx, nz = nx / L, nz / L                   # uphill = inland
        prof = bilinear(heights, x + nx * t, z + nz * t)
        m = profile_metrics(prof, sea)
        seaward = (math.degrees(math.atan2(-nx, nz)) + 360) % 360      # compass bearing of the seaward normal, 0 = north(-z)
        row = {"x": int(x), "z": int(z), "faces": round((180 + math.degrees(math.atan2(nx, -nz))) % 360), **m}
        if sub_lookup:
            sub_idx, subs = sub_lookup
            win = sub_idx[max(0, z - 64):z + 65, max(0, x - 64):x + 65]
            vals = win[win > 0]
            if len(vals):
                s = subs[int(np.bincount(vals).argmax()) - 1]
                row["subregion"], row["region"] = s["id"], s["parent"]
        rows.append(row)
    return rows, sea_mask


def summarise(rows):
    def pct(vals, q):
        v = [x for x in vals if x is not None]
        return round(float(np.percentile(v, q)), 3) if v else None
    by_region = {}
    for r in rows:
        by_region.setdefault(r.get("region") or "?", []).append(r)
    out = {}
    for reg, rs in sorted(by_region.items()):
        g = [r["grade_0_4"] for r in rs]
        out[reg] = {"samples": len(rs),
                    "grade_0_4": {"p10": pct(g, 10), "median": pct(g, 50), "p90": pct(g, 90)},
                    "beach_width_share": round(sum(1 for x in g if x is not None and x <= 1 / 8) / len(rs), 2),
                    "cliff_share": round(sum(1 for x in g if x is not None and x >= 0.5) / len(rs), 2),
                    "terraced_share": round(sum(1 for r in rs if r["steps"] >= 2) / len(rs), 2),
                    "shelf_to_-3_median": pct([r["depth_at_-3"] for r in rs], 50),
                    "shelf_to_-8_median": pct([r["depth_at_-8"] for r in rs], 50)}
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--regions", default=str(T.ROOT / "data" / "regions.json"))
    p.add_argument("--spacing", type=int, default=SPACING)
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    sea = T.sea_level(world)
    regions = json.loads(Path(a.regions).read_text(encoding="utf-8"))
    rows, _ = measure(heights, sea, regions, a.spacing)
    g = [r["grade_0_4"] for r in rows if r["grade_0_4"] is not None]
    doc = {"generator": "tools/coast_measure.py", "provenance": T.provenance(world, Path(a.world)),
           "spacing_blocks": a.spacing, "samples": len(rows),
           "overall": {"grade_0_4_median": round(float(np.median(g)), 3),
                       "beach_grade_share": round(float(np.mean([x <= 1 / 8 for x in g])), 3),
                       "steeper_than_1_in_2_share": round(float(np.mean([x >= 0.5 for x in g])), 3),
                       "terraced_share": round(float(np.mean([r["steps"] >= 2 for r in rows])), 3)},
           "by_region": summarise(rows), "profiles": rows}
    out = a.out or str(T.ROOT / "derived" / "coast" / "profiles.json")
    T.write_json(out, doc)
    print(json.dumps({k: doc[k] for k in ("samples", "overall", "by_region")}, indent=1))


if __name__ == "__main__":
    main()
