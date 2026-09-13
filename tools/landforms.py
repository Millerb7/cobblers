#!/usr/bin/env python
"""Separate the terrain into bodies and candidate landform classes.

Produces the measurements region design needs, never the regions themselves:

  - land bodies: the mainland and each island, with area, bounds, elevation
  - water bodies: the open sea and each enclosed inland water body, with its
    floor elevation, so a flooded basin is not mistaken for a dry valley
  - peaks: summits above a threshold, clustered, with local prominence
  - a candidate landform class per pixel, from explicit elevation and slope
    rules whose thresholds are all parameters

These are candidates. Where a region boundary goes is an authored decision
recorded in data/regions.json.

  python tools/landforms.py --source-root C:/Users/wnd/Documents
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import terrain as T
import cell_stats as C
import landmarks as LM

CLASSES = [
    # id, name, RGB for the preview
    (0, "sea", (38, 70, 130)),
    (1, "inland_water", (60, 120, 180)),
    (2, "shore", (214, 200, 150)),
    (3, "lowland_flat", (120, 170, 80)),
    (4, "lowland_rolling", (100, 145, 70)),
    (5, "upland_flat", (160, 160, 90)),
    (6, "upland_rolling", (140, 125, 80)),
    (7, "steep", (120, 95, 80)),
    (8, "montane", (130, 120, 115)),
    (9, "alpine", (240, 240, 245)),
    (10, "void_floor", (120, 40, 160)),
]


def label_components(mask):
    """4-connected component labels via min-label propagation with pointer jumping.

    Returns an int32 array where 0 is background and components are 1..n,
    renumbered by descending area.
    """
    h, w = mask.shape
    idx = np.arange(1, h * w + 1, dtype=np.int64).reshape(h, w)
    lab = np.where(mask, idx, 0)
    big = np.iinfo(np.int64).max
    while True:
        cur = np.where(mask, lab, big)
        m = cur.copy()
        m[1:, :] = np.minimum(m[1:, :], cur[:-1, :])
        m[:-1, :] = np.minimum(m[:-1, :], cur[1:, :])
        m[:, 1:] = np.minimum(m[:, 1:], cur[:, :-1])
        m[:, :-1] = np.minimum(m[:, :-1], cur[:, 1:])
        new = np.where(mask, m, 0)
        # pointer jumping: follow each label to the label its root carries
        flat = new.ravel()
        for _ in range(4):
            fg = flat > 0
            jumped = flat.copy()
            jumped[fg] = flat[flat[fg] - 1]
            flat = np.where(fg, np.minimum(flat, jumped), 0)
        new = flat.reshape(h, w)
        if np.array_equal(new, lab):
            break
        lab = new
    ids, inv, counts = np.unique(lab, return_inverse=True, return_counts=True)
    order = [i for i in np.argsort(-counts) if ids[i] != 0]
    remap = np.zeros(ids.size, dtype=np.int32)
    for rank, i in enumerate(order, start=1):
        remap[i] = rank
    return remap[inv].reshape(h, w)


def body_summary(labels, heights_c, factor, kind):
    out = []
    n = int(labels.max())
    zz, xx = np.indices(labels.shape)
    for k in range(1, n + 1):
        m = labels == k
        area_px = int(m.sum())
        ys, xs = zz[m], xx[m]
        hv = heights_c[m]
        out.append({
            "id": "%s_%d" % (kind, k),
            "area_blocks2": area_px * factor * factor,
            "bounds": {
                "min_x": int(xs.min()) * factor, "min_z": int(ys.min()) * factor,
                "max_x": (int(xs.max()) + 1) * factor - 1,
                "max_z": (int(ys.max()) + 1) * factor - 1,
            },
            "centroid": {"x": round(float(xs.mean()) * factor + factor / 2, 1),
                         "z": round(float(ys.mean()) * factor + factor / 2, 1)},
            "y": {"min": round(float(hv.min()), 2), "mean": round(float(hv.mean()), 2),
                  "max": round(float(hv.max()), 2)},
        })
    return out


def find_peaks(heights_c, factor, min_y, window, cluster_radius):
    """Local maxima above min_y within a square window, clustered by distance."""
    h, w = heights_c.shape
    r = window // 2
    pad = np.pad(heights_c, r, mode="edge")
    local_max = heights_c.copy()
    # separable running max
    tmp = np.full_like(pad, -np.inf)
    for d in range(-r, r + 1):
        tmp[:, r:-r or None] = np.maximum(tmp[:, r:-r or None],
                                          np.roll(pad, d, axis=1)[:, r:-r or None])
    runmax = np.full((h, w), -np.inf, dtype=heights_c.dtype)
    for d in range(-r, r + 1):
        runmax = np.maximum(runmax, np.roll(tmp, d, axis=0)[r:-r or None, r:-r or None])
    is_peak = (heights_c >= runmax) & (heights_c >= min_y)
    zs, xs = np.nonzero(is_peak)
    cand = sorted(zip(heights_c[zs, xs], xs, zs), reverse=True)

    peaks = []
    for y, x, z in cand:
        bx, bz = int(x) * factor + factor // 2, int(z) * factor + factor // 2
        if any((bx - p["x"]) ** 2 + (bz - p["z"]) ** 2 < cluster_radius ** 2 for p in peaks):
            continue
        # local relief: summit minus the lowest ground in a surrounding ring
        z0, z1 = max(0, z - 3 * r), min(h, z + 3 * r + 1)
        x0, x1 = max(0, x - 3 * r), min(w, x + 3 * r + 1)
        ring_min = float(heights_c[z0:z1, x0:x1].min())
        peaks.append({"x": bx, "z": bz, "y": round(float(y), 2),
                      "local_relief": round(float(y) - ring_min, 2)})
    return peaks


def classify(heights_c, slope_c, sea_c, lake_c, d_sea, sea_level, a, void_c=None):
    cls = np.zeros(heights_c.shape, dtype=np.uint8)
    void_c = np.zeros_like(sea_c) if void_c is None else void_c
    land = ~(sea_c | lake_c | void_c)
    y, s = heights_c, slope_c
    shore = land & (d_sea <= a.shore_distance) & (y < sea_level + a.shore_rise)
    alpine = land & (y >= a.treeline)
    steep = land & ~alpine & (s >= a.steep_slope)
    montane = land & ~alpine & ~steep & (y >= a.montane_y)
    upland = land & ~alpine & ~steep & ~montane & (y >= a.upland_y)
    lowland = land & ~alpine & ~steep & ~montane & ~upland
    flat = s < a.flat_slope

    cls[sea_c] = 0
    cls[lake_c] = 1
    cls[lowland & ~flat] = 4
    cls[lowland & flat] = 3
    cls[upland & ~flat] = 6
    cls[upland & flat] = 5
    cls[montane] = 8
    cls[steep] = 7
    cls[alpine] = 9
    cls[shore] = 2
    cls[void_c] = 10
    return cls


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--factor", type=int, default=8, help="analysis block size (default 8)")
    p.add_argument("--treeline", type=float, default=165.0, help="alpine above this Y")
    p.add_argument("--montane-y", type=float, default=145.0)
    p.add_argument("--upland-y", type=float, default=115.0)
    p.add_argument("--steep-slope", type=float, default=25.0, help="degrees")
    p.add_argument("--flat-slope", type=float, default=5.0, help="degrees")
    p.add_argument("--shore-distance", type=float, default=48.0, help="blocks from sea")
    p.add_argument("--shore-rise", type=float, default=8.0, help="blocks above sea level")
    p.add_argument("--peak-min-y", type=float, default=165.0)
    p.add_argument("--peak-window", type=int, default=9, help="pixels at --factor")
    p.add_argument("--peak-cluster", type=float, default=300.0, help="blocks")
    p.add_argument("--min-body", type=int, default=64 * 64, help="ignore bodies smaller than this many blocks2")
    p.add_argument("--landmarks", default=str(LM.DEFAULT_LANDMARKS),
                   help="landmarks whose water policy is honoured (default data/landmarks.json)")
    p.add_argument("--no-landmarks", action="store_true",
                   help="ignore landmarks: every enclosed hollow below sea level is water")
    a = p.parse_args(argv)
    landmarks = None
    if not a.no_landmarks:
        try:
            landmarks = LM.load(a.landmarks)
        except LM.LandmarkError as exc:
            raise SystemExit("landmarks: %s (pass --no-landmarks to classify without them)" % exc)

    try:
        heights, world = T.load_from_args(a)
    except T.TerrainUnavailable as exc:
        raise SystemExit("terrain unavailable: %s" % exc)

    f = a.factor
    sea_level = T.sea_level(world)
    hc = C.downsample(heights.astype(np.float32), f, "mean")
    sc = C.downsample(T.slope_degrees(heights).astype(np.float32), f, "mean")
    below_c = C.downsample(heights <= sea_level, f, "any")
    # Ground inside a water:"never" landmark is not a water body even below sea
    # level. It is its own class, so nothing downstream reads the rift as a lake.
    no_water_c = (LM.no_water_mask(landmarks, hc.shape, factor=f) if landmarks
                  else np.zeros(hc.shape, dtype=bool))
    void_c = below_c & no_water_c
    water_c = below_c & ~no_water_c
    land_c = ~below_c
    sea_c = C.connected_to_edge(water_c)
    lake_c = water_c & ~sea_c
    d_sea = C.distance_to(sea_c) * f

    land_lab = label_components(land_c)
    lake_lab = label_components(lake_c)
    lands = [b for b in body_summary(land_lab, hc, f, "land") if b["area_blocks2"] >= a.min_body]
    lakes = [b for b in body_summary(lake_lab, hc, f, "inland_water") if b["area_blocks2"] >= a.min_body]
    if lands:
        lands[0]["role"] = "mainland"
        for b in lands[1:]:
            b["role"] = "island"

    peaks = find_peaks(hc, f, a.peak_min_y, a.peak_window, a.peak_cluster)
    cls = classify(hc, sc, sea_c, lake_c, d_sea, sea_level, a, void_c)

    outdir = Path(a.out) if a.out else T.ROOT / "derived" / "landforms"
    outdir.mkdir(parents=True, exist_ok=True)
    np.save(outdir / "classes.npy", cls)
    np.save(outdir / "land_labels.npy", land_lab)
    np.save(outdir / "heights_c.npy", hc)
    palette = np.array([c[2] for c in CLASSES], dtype=np.uint8)
    Image.fromarray(palette[cls]).save(outdir / "classes.png")

    counts = {name: round(float((cls == cid).mean()), 4) for cid, name, _ in CLASSES}
    payload = {
        "schema": "cobblers.derived.landforms/1",
        "parameters": {k: v for k, v in vars(a).items()
                       if k not in ("world", "source_root", "heightmap", "out", "landmarks",
                                    "no_landmarks")},
        "landmarks": None if a.no_landmarks else a.landmarks,
        "void_fraction": round(float(void_c.mean()), 4),
        "source": T.provenance(world, a.world),
        "resolution_blocks": f,
        "class_ids": {name: cid for cid, name, _ in CLASSES},
        "class_fractions": counts,
        "land_bodies": lands,
        "inland_water_bodies": lakes,
        "peaks": peaks,
    }
    T.write_json(outdir / "landforms.json", payload)
    print("%d land bodies (%d islands), %d inland water bodies, %d peaks -> %s"
          % (len(lands), max(0, len(lands) - 1), len(lakes), len(peaks), outdir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
