#!/usr/bin/env python
"""Measure contour terracing across the whole landmass: why the land reads as concentric rings from the air.

A smooth slope of grade g becomes a 1-block step every 1/g blocks once it is written as blocks. Steps read as
rings when that spacing is regular over a wide area. Measures per heightmap:

  regimes         share of land by regional grade (sigma 24): flat under 1:12, ring-forming 1:12 to 1:1.5,
                  steep over 1:1.5
  treads          block treads on the quantised surface (floor(h)), read along sampled rows and columns and
                  corrected to the fall line: histogram and percentiles
  tread_cv        coefficient of variation of consecutive treads in 64-block windows with 6+ treads; a
                  regular ring field is near the quantisation floor, about 0.15
  terrace_index   the earlier source-side index (1-block slope departing from the 9-block slope, relative to
                  that slope, 32-block windows with most ground gentle); near 0 means the source is smooth
  perturbation    rho = |grad(fine, sigma 2.5) - grad(regional, sigma 24)| / |grad(regional)| on ring-forming
                  ground. Contours run as parallel rings when rho is near 0, wander above about 0.3, and break
                  into patches where rho passes 1 (the slope locally reverses)
  shoreline       coast_measure profiles: flats (4 blocks of rise over 80+ blocks) and cliffs (4 blocks of
                  rise within 4)

  python tools/terrace_measure.py --source-root <root> [--heightmap FILE --label NAME] [--no-coast]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

import terrain as T
from coast_measure import measure as coast_profiles
from coast_measure import smooth

Image.MAX_IMAGE_PIXELS = None
TREAD_BINS = [1, 1.5, 2, 3, 4, 6, 8, 12, 24, 1e9]
CV_BINS = [0, 0.1, 0.15, 0.2, 0.3, 0.4, 0.6, 1e9]
RHO_BINS = [0, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 1e9]
TI_BINS = [0, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 1e9]


def hist(vals, bins, weights=None):
    c, _ = np.histogram(vals, bins=bins, weights=weights)
    tot = max(float(c.sum()), 1.0)
    return {("%g-%g" % (bins[i], bins[i + 1])).replace("-1e+09", "+"): round(float(c[i]) / tot, 4) for i in range(len(c))}


def treads(h, land, ux, uz, step=8, window=64):
    """Treads on floor(h) along every step-th row and column. Returns (tread, window key) arrays."""
    q = np.floor(h).astype(np.int16)
    n = h.shape[0]
    out_t, out_k = [], []
    for axis in (1, 0):
        for i in range(0, n, step):
            line = q[i, :] if axis == 1 else q[:, i]
            lm = land[i, :] if axis == 1 else land[:, i]
            u = np.abs(ux[i, :] if axis == 1 else uz[:, i])
            d = np.diff(line.astype(np.int32))
            pos = np.nonzero(d != 0)[0]
            if len(pos) < 2:
                continue
            sgn = np.sign(d[pos])
            ok = (sgn[1:] == sgn[:-1]) & (np.abs(d[pos[1:]]) == 1) & (np.abs(d[pos[:-1]]) == 1)
            run = (pos[1:] - pos[:-1]).astype(np.float32)
            mid = (pos[1:] + pos[:-1]) // 2
            ok &= lm[mid] & lm[pos[1:]] & lm[pos[:-1]+1]
            t = run * np.maximum(u[mid], 0.05)          # axis run to fall-line tread
            ok &= (u[mid] > 0.3)                          # skip lines nearly along the contour
            if axis == 1:
                key = (i // window) * 100000 + mid // window
            else:
                key = (mid // window) * 100000 + i // window
            out_t.append(t[ok]); out_k.append(key[ok])
    return np.concatenate(out_t), np.concatenate(out_k)


def window_cv(t, k, min_count=6):
    uk, inv = np.unique(k, return_inverse=True)
    cnt = np.bincount(inv)
    s1 = np.bincount(inv, t)
    s2 = np.bincount(inv, t * t)
    mean = s1 / np.maximum(cnt, 1)
    var = np.maximum(s2 / np.maximum(cnt, 1) - mean ** 2, 0)
    good = cnt >= min_count
    return np.sqrt(var[good]) / np.maximum(mean[good], 1e-6), mean[good]


def run(h, world, regions=None, coast=True):
    sea = T.sea_level(world)
    n = h.shape[0]
    land = h > sea
    rep = {"land_columns": int(land.sum())}

    reg = smooth(h, 24)
    gz, gx = np.gradient(reg)
    greg = np.hypot(gx, gz)
    del reg
    ux, uz = gx / np.maximum(greg, 1e-6), gz / np.maximum(greg, 1e-6)
    ring = land & (greg >= 1 / 12) & (greg <= 1 / 1.5)
    rep["regimes"] = {"flat_under_1_12": round(float((land & (greg < 1 / 12)).sum() / land.sum()), 4),
                      "ring_1_12_to_1_1.5": round(float(ring.sum() / land.sum()), 4),
                      "steep_over_1_1.5": round(float((land & (greg > 1 / 1.5)).sum() / land.sum()), 4)}

    fine = smooth(h, 2.5)
    fz, fx = np.gradient(fine)
    del fine
    rho = np.hypot(fx - gx, fz - gz) / np.maximum(greg, 1e-6)
    r = rho[ring]
    rep["perturbation"] = {"columns": int(r.size), "p10": round(float(np.percentile(r, 10)), 3),
                           "median": round(float(np.median(r)), 3), "p90": round(float(np.percentile(r, 90)), 3),
                           "share_over_0.3": round(float((r > 0.3).mean()), 4),
                           "share_over_1": round(float((r > 1).mean()), 4), "histogram": hist(r, RHO_BINS)}
    del rho, r, fx, fz, gx, gz

    t, k = treads(h, land & ring, ux, uz)
    rep["treads"] = {"count": int(t.size), "p10": round(float(np.percentile(t, 10)), 2),
                     "median": round(float(np.median(t)), 2), "p90": round(float(np.percentile(t, 90)), 2),
                     "histogram": hist(t, TREAD_BINS)}
    cv, mean = window_cv(t, k)
    rep["tread_cv"] = {"windows": int(cv.size), "p10": round(float(np.percentile(cv, 10)), 3),
                       "median": round(float(np.median(cv)), 3), "p90": round(float(np.percentile(cv, 90)), 3),
                       "share_under_0.2": round(float((cv < 0.2).mean()), 4), "histogram": hist(cv, CV_BINS)}
    del ux, uz

    # the earlier source-side terrace index, unchanged
    sm9 = smooth(h, 4)
    gz9, gx9 = np.gradient(sm9)
    g9 = np.hypot(gx9, gz9)
    del sm9
    u9x, u9z = gx9 / np.maximum(g9, 1e-6), gz9 / np.maximum(g9, 1e-6)
    gz1, gx1 = np.gradient(h)
    dev = np.abs(gx1 * u9x + gz1 * u9z - g9)
    del gz1, gx1, u9x, u9z, gx9, gz9
    W = 32
    kk = n // W

    def pool(a):
        return a[: kk * W, : kk * W].reshape(kk, W, kk, W).mean(axis=(1, 3))
    gentle = ((g9 > 0.04) & (g9 < 0.45) & land).astype(np.float32)
    ti = pool(dev * gentle) / np.maximum(pool(g9 * gentle), 1e-6)
    valid = pool(gentle) > 0.5
    v = ti[valid]
    rep["terrace_index"] = {"windows": int(v.size), "p50": round(float(np.percentile(v, 50)), 3),
                            "p90": round(float(np.percentile(v, 90)), 3), "p99": round(float(np.percentile(v, 99)), 3),
                            "histogram": hist(v, TI_BINS)}
    del dev, g9, gentle

    if regions is not None:
        from sculpt import region_index
        idx, subs = region_index(n, regions, 8)
        big = idx.repeat(8, 0).repeat(8, 1)[:n, :n]
        par = {}
        for i, s in enumerate(subs, start=1):
            par.setdefault(s["parent"], []).append(i)
        by = {}
        # rho per region recomputed cheaply on a 4-block subsample
        rho4 = None
        for pid, ids in sorted(par.items()):
            m = np.isin(big[::4, ::4], ids) & ring[::4, ::4]
            if m.sum() < 500:
                continue
            by[pid] = {"ring_share_of_land": round(float(m.sum() / max(1, (np.isin(big[::4, ::4], ids) & land[::4, ::4]).sum())), 3),
                       "median_regional_grade": round(float(np.median(greg[::4, ::4][m])), 3)}
        rep["by_region"] = by

    if coast:
        rows, _ = coast_profiles(h, sea)
        g = np.array([r["grade_0_4"] for r in rows if r["grade_0_4"] is not None])
        rep["shoreline"] = {"profiles": int(g.size),
                            "flat_share_grade_under_1_20": round(float((g <= 1 / 20).mean()), 4),
                            "beach_share_1_8_or_flatter": round(float((g <= 1 / 8).mean()), 4),
                            "cliff_share_1_1_or_steeper": round(float((g >= 1).mean()), 4),
                            "steeper_than_1_1.5": round(float((g >= 1 / 1.5).mean()), 4),
                            "median_run_per_rise": round(float(np.median(1 / g)), 2)}
    return rep


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--heightmap-file", default=None, help="measure this file instead of world.json's (not hash-checked)")
    p.add_argument("--label", default=None)
    p.add_argument("--no-coast", action="store_true")
    p.add_argument("--regions", default=str(T.ROOT / "data" / "regions.json"))
    a = p.parse_args(argv)
    world = T.load_world(Path(a.world))
    if a.heightmap_file:
        path = Path(a.heightmap_file)
        h = T.read_heights(path, world).astype(np.float32)
    else:
        h, world = T.load_from_args(a)
        path = None
    sha = hashlib.sha256(path.read_bytes()).hexdigest() if path else world["heightmap"]["sha256"]
    regions = json.loads(Path(a.regions).read_text(encoding="utf-8"))
    rep = {"generator": "tools/terrace_measure.py", "heightmap_sha256": sha, "label": a.label, **run(h, world, regions, not a.no_coast)}
    out = a.out or str(T.ROOT / "derived" / "terrace" / ("%s.json" % (a.label or sha[:12])))
    T.write_json(out, rep)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
