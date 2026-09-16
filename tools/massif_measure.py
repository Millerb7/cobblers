#!/usr/bin/env python
"""Measure mountain and volcano profiles: summits, flank symmetry, clipped tops, crater bowls.

For each massif (a landmark outline or a sub-region), on a 4-block grid:
  summits     local maxima at least 20 blocks above everything within 160 blocks... ranked by height, with
              prominence (drop to the highest saddle toward a higher summit inside the massif)
  flanks      from the highest summit, 16 radial profiles: horizontal distance to fall 40 and 80 blocks, as mean
              grade; symmetry = steepest / gentlest of the 16
  clipped     columns at or above y200.5 (the import clamp), their area and connected patches
  bowls       for volcano cones: rim height (90th percentile of a ring) against the lowest point inside it

  python tools/massif_measure.py --source-root <root> --out derived/terrain/massifs.json
"""
from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import terrain as T

G = 4
MASSIFS = {
    "tri_peaks": {"landmark": "tri_peaks"},
    "mt_vessu": {"landmark": "mt_vessu"},
    "mt_clay": {"landmark": "mt_clay"},
    "frostpeak": {"subregion": "frostpeak"},
    "craters": {"landmark": "craters", "volcano": True},
}


def mask_for(spec, landmarks, regions, n):
    img = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(img)
    polys = []
    if "landmark" in spec:
        lm = next(l for l in landmarks["landmarks"] if l["id"] == spec["landmark"])
        polys = (lm.get("extent") or {}).get("polygons") or []
    else:
        s = next(s for s in regions["subregions"] if s["id"] == spec["subregion"])
        polys = s["polygons"]
    for ring in polys:
        d.polygon([(x / G, z / G) for x, z in ring], fill=1)
    return np.asarray(img) > 0


def summits(h4, mask, radius_cells=40, min_rise=20):
    zs, xs = np.nonzero(mask)
    out = []
    for z, x in zip(zs, xs):
        v = h4[z, x]
        z0, z1, x0, x1 = max(0, z - radius_cells), z + radius_cells + 1, max(0, x - radius_cells), x + radius_cells + 1
        win = h4[z0:z1, x0:x1]
        if v < win.max() - 1e-6:
            continue
        if v - np.percentile(win, 20) < min_rise:
            continue
        out.append((float(v), int(x), int(z)))
    # merge maxima of the same flat top
    out.sort(reverse=True)
    merged = []
    for v, x, z in out:
        if all(math.hypot(x - mx, z - mz) > 10 for _, mx, mz in merged):
            merged.append((v, x, z))
    return merged


def prominence(h4, mask, peak, higher):
    """Drop from the peak to the highest col on a path to any higher summit, by descending flood inside the mask."""
    if not higher:
        return None
    v0, px, pz = peak
    targets = {(x, z) for _, x, z in higher}
    lo, hi = 0.0, v0
    for _ in range(14):
        mid = (lo + hi) / 2
        seen = np.zeros(mask.shape, bool)
        q = deque([(pz, px)])
        seen[pz, px] = True
        found = False
        while q and not found:
            z, x = q.popleft()
            for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nz, nx = z + dz, x + dx
                if 0 <= nz < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[nz, nx] and not seen[nz, nx] and h4[nz, nx] >= mid:
                    if (nx, nz) in targets:
                        found = True
                        break
                    seen[nz, nx] = True
                    q.append((nz, nx))
        if found:
            lo = mid
        else:
            hi = mid
    return round(v0 - lo, 1)


def flanks(heights, x, z, drops=(40, 80), reach=900):
    rows = []
    t = np.arange(0, reach, 2, dtype=np.float32)
    top = float(heights[z, x])
    n = heights.shape[0]
    for k in range(16):
        ang = 2 * math.pi * k / 16
        dx, dz = math.sin(ang), -math.cos(ang)          # 0 = north (-z), clockwise
        xs = np.clip((x + dx * t).astype(int), 0, n - 1)
        zs = np.clip((z + dz * t).astype(int), 0, n - 1)
        prof = heights[zs, xs]
        row = {"bearing": int(k * 22.5)}
        for dr in drops:
            idx = np.nonzero(prof <= top - dr)[0]
            row["run_to_-%d" % dr] = int(t[idx[0]]) if len(idx) else None
        rows.append(row)
    g80 = [80.0 / r["run_to_-80"] for r in rows if r["run_to_-80"]]
    return rows, (round(max(g80) / min(g80), 2) if len(g80) >= 8 else None), (round(float(np.median(g80)), 3) if g80 else None)


def patches(mask):
    seen = np.zeros(mask.shape, bool)
    sizes = []
    for z, x in zip(*np.nonzero(mask)):
        if seen[z, x]:
            continue
        q = deque([(z, x)])
        seen[z, x] = True
        c = 0
        while q:
            a, b = q.popleft()
            c += 1
            for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                na, nb = a + da, b + db
                if 0 <= na < mask.shape[0] and 0 <= nb < mask.shape[1] and mask[na, nb] and not seen[na, nb]:
                    seen[na, nb] = True
                    q.append((na, nb))
        sizes.append(c)
    return sorted(sizes, reverse=True)


def bowl(heights, x, z, rim_radius):
    n = heights.shape[0]
    yy, xx = np.mgrid[-rim_radius - 8:rim_radius + 9, -rim_radius - 8:rim_radius + 9]
    d = np.hypot(xx, yy)
    zs, xs = np.clip(z + yy, 0, n - 1), np.clip(x + xx, 0, n - 1)
    win = heights[zs, xs]
    ring = win[(d >= rim_radius - 4) & (d <= rim_radius + 4)]
    inner = win[d < rim_radius - 4]
    rim = float(np.percentile(ring, 90))
    return {"rim_y": round(rim, 1), "floor_y": round(float(inner.min()), 1), "depth": round(rim - float(inner.min()), 1)}


def measure(heights, landmarks, regions):
    n = heights.shape[0]
    h4 = heights[::G, ::G]
    out = {}
    for name, spec in MASSIFS.items():
        m = mask_for(spec, landmarks, regions, n // G)
        tops = summits(h4, m, radius_cells=25 if spec.get("volcano") else 40, min_rise=15)
        rows = []
        for i, (v, x, z) in enumerate(tops[:6]):
            rows.append({"x": x * G, "z": z * G, "y": round(v, 1),
                         "prominence": prominence(h4, m, (v, x, z), [t for t in tops[:i] if t[0] > v])})
        hx, hz = rows[0]["x"], rows[0]["z"]
        fl, sym, med = flanks(heights, hx, hz)
        clip = (heights >= 200.5)
        mfull = np.repeat(np.repeat(m, G, 0), G, 1)[:n, :n]
        cm = clip & mfull
        entry = {"summits": rows, "highest": rows[0], "flank_grade_80_median": med, "flank_symmetry_steep_over_gentle": sym,
                 "flanks": fl, "clipped_columns": int(cm.sum()),
                 "clipped_patches_4block": patches(cm[::G, ::G])[:8]}
        if spec.get("volcano"):
            entry["cones"] = []
            for r in rows[:4]:
                best = None
                for rad in (12, 20, 28, 36, 48):
                    b = bowl(heights, r["x"], r["z"], rad)
                    if best is None or b["depth"] > best["depth"]:
                        best = dict(b, rim_radius=rad)
                entry["cones"].append({"x": r["x"], "z": r["z"], "top_y": r["y"], **best})
        out[name] = entry
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    landmarks = json.loads((T.ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
    regions = json.loads((T.ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    res = measure(heights, landmarks, regions)
    out = a.out or str(T.ROOT / "derived" / "terrain" / "massifs.json")
    T.write_json(out, {"generator": "tools/massif_measure.py", "provenance": T.provenance(world, Path(a.world)), "massifs": res})
    for k, v in res.items():
        print(k, "summits", [(s["x"], s["z"], s["y"], s["prominence"]) for s in v["summits"]],
              "flank grade", v["flank_grade_80_median"], "symmetry", v["flank_symmetry_steep_over_gentle"],
              "clipped", v["clipped_columns"], v["clipped_patches_4block"][:4], v.get("cones"))


if __name__ == "__main__":
    main()
