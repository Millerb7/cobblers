#!/usr/bin/env python
"""Measure every planning cell: elevation, land fraction, slope, coast distance.

Output is derived data. Its `terrain` blocks use the field names of the
data/cells.json schema and carry the heightmap sha256 they were computed from,
so they can be copied into authored data without retyping numbers.

  python tools/cell_stats.py --source-root C:/Users/wnd/Documents

Water is split into sea, meaning water connected to the map edge, and inland
water, meaning enclosed lakes. "Distance to coast" is distance to the nearest
sea; distance to any water is reported separately.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import terrain as T
import landmarks as LM


# ---------------------------------------------------------------- rasters


def downsample(arr, factor, reduce="mean"):
    if factor == 1:
        return arr
    h, w = arr.shape
    h2, w2 = h // factor, w // factor
    v = arr[:h2 * factor, :w2 * factor].reshape(h2, factor, w2, factor)
    if reduce == "mean":
        return v.mean(axis=(1, 3))
    if reduce == "any":
        return v.any(axis=(1, 3))
    if reduce == "all":
        return v.all(axis=(1, 3))
    raise ValueError(reduce)


def _dilate4(m):
    out = m.copy()
    out[1:, :] |= m[:-1, :]
    out[:-1, :] |= m[1:, :]
    out[:, 1:] |= m[:, :-1]
    out[:, :-1] |= m[:, 1:]
    return out


def _dilate8(m):
    out = _dilate4(m)
    out[1:, 1:] |= m[:-1, :-1]
    out[1:, :-1] |= m[:-1, 1:]
    out[:-1, 1:] |= m[1:, :-1]
    out[:-1, :-1] |= m[1:, 1:]
    return out


def connected_to_edge(mask):
    """Cells of `mask` reachable from the map border through `mask` (4-connected).

    Iterative constrained dilation, so it needs only numpy.
    """
    reach = np.zeros_like(mask)
    reach[0, :] = mask[0, :]
    reach[-1, :] = mask[-1, :]
    reach[:, 0] = mask[:, 0]
    reach[:, -1] = mask[:, -1]
    while True:
        grown = _dilate4(reach) & mask
        if np.array_equal(grown, reach):
            return reach
        reach = grown


def distance_to(source, max_steps=None):
    """Octagonal distance in pixels from every cell to the nearest `source`.

    Alternates 4- and 8-neighbour growth, which approximates Euclidean
    distance within about 8%. Pure straight-line axis distances are exact.
    Cells never reached are +inf.
    """
    dist = np.full(source.shape, np.inf, dtype=np.float32)
    dist[source] = 0.0
    front = source.copy()
    step = 0
    while front.any() and (max_steps is None or step < max_steps):
        step += 1
        grown = _dilate8(front) if step % 2 == 0 else _dilate4(front)
        new = grown & ~np.isfinite(dist)
        if not new.any():
            break
        dist[new] = step
        front = front | new
    return dist


# ----------------------------------------------------------------- cells


def cell_grid(world, shape):
    g = world["grid"]
    if g.get("origin_x") is None or g.get("origin_z") is None:
        raise T.TerrainUnavailable("grid origin is unset; cells cannot be placed")
    size = int(g["cell_size"])
    rows, cols = int(g["rows"]), int(g["columns"])
    ox, oz = int(g["origin_x"]), int(g["origin_z"])
    if oz + rows * size > shape[0] or ox + cols * size > shape[1]:
        raise T.TerrainUnavailable("grid extends beyond the heightmap")
    for r in range(rows):
        for c in range(cols):
            z0, x0 = oz + r * size, ox + c * size
            yield (g["row_labels"][r] + g["column_labels"][c],
                   r, c, x0, z0, x0 + size - 1, z0 + size - 1)


def measure(heights, world, coast_factor, no_water=None):
    """no_water: full-resolution mask of ground that is below sea level but must
    never hold water (a landmark with water "never", such as the rift). It is
    counted as void, neither land nor water, and no distance is measured to it.
    """
    sea_level = T.sea_level(world)
    slope = T.slope_degrees(heights).astype(np.float32)
    land = heights > sea_level
    void = ~land & no_water if no_water is not None else np.zeros_like(land)
    water = ~land & ~void

    # coast distance on a coarser grid; a cell is 1024 blocks so 8-block
    # precision is ample, and it keeps the flood fill fast
    f = coast_factor
    water_c = downsample(water, f, "any") if f > 1 else water
    sea_c = connected_to_edge(water_c)
    lake_c = water_c & ~sea_c
    d_sea = distance_to(sea_c) * f
    d_water = distance_to(water_c) * f
    land_c = downsample(land, f, "all") if f > 1 else land

    sha = (world.get("heightmap") or {}).get("sha256")
    cells = []
    for cid, r, c, x0, z0, x1, z1 in cell_grid(world, heights.shape):
        h = heights[z0:z1 + 1, x0:x1 + 1]
        s = slope[z0:z1 + 1, x0:x1 + 1]
        lm = land[z0:z1 + 1, x0:x1 + 1]
        cz0, cz1, cx0, cx1 = z0 // f, (z1 + 1) // f, x0 // f, (x1 + 1) // f
        ds = d_sea[cz0:cz1, cx0:cx1]
        dw = d_water[cz0:cz1, cx0:cx1]
        lc = land_c[cz0:cz1, cx0:cx1]
        lk = lake_c[cz0:cz1, cx0:cx1]
        vm = void[z0:z1 + 1, x0:x1 + 1]

        land_frac = float(lm.mean())
        void_frac = float(vm.mean())
        entry = {
            "id": cid, "row": r, "column": c,
            "bounds": {"min_x": x0, "min_z": z0, "max_x": x1, "max_z": z1},
            "terrain": {
                "min_y": round(float(h.min()), 2),
                "max_y": round(float(h.max()), 2),
                "mean_y": round(float(h.mean()), 2),
                "land_fraction": round(land_frac, 4),
                "water_fraction": round(1.0 - land_frac - void_frac, 4),
                "void_fraction": round(void_frac, 4),
                "mean_slope": round(float(s.mean()), 3),
                "max_slope": round(float(s.max()), 3),
                "computed_from_sha256": sha,
            },
            "land": None,
            "coast": {
                "inland_water_fraction": round(float(lk.mean()), 4),
            },
        }
        if lm.any():
            hl, sl = h[lm], s[lm]
            entry["land"] = {
                "min_y": round(float(hl.min()), 2),
                "max_y": round(float(hl.max()), 2),
                "mean_y": round(float(hl.mean()), 2),
                "p90_y": round(float(np.percentile(hl, 90)), 2),
                "mean_slope": round(float(sl.mean()), 3),
                "p90_slope": round(float(np.percentile(sl, 90)), 3),
                "flat_fraction_under_5deg": round(float((sl < 5).mean()), 4),
            }
            dsl, dwl = ds[lc], dw[lc]
            finite = np.isfinite(dsl)
            if finite.any():
                entry["coast"].update({
                    "min_distance_to_sea": round(float(dsl[finite].min()), 1),
                    "mean_distance_to_sea": round(float(dsl[finite].mean()), 1),
                    "max_distance_to_sea": round(float(dsl[finite].max()), 1),
                })
            if np.isfinite(dwl).any():
                entry["coast"]["max_distance_to_any_water"] = round(
                    float(dwl[np.isfinite(dwl)].max()), 1)
        cells.append(entry)
    return cells, {
        "sea_fraction": round(float(sea_c.mean()), 4),
        "inland_water_fraction": round(float(lake_c.mean()), 4),
        "land_fraction": round(float(land.mean()), 4),
        "void_fraction": round(float(void.mean()), 4),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--coast-factor", type=int, default=8,
                   help="block size of the coast-distance grid (default 8)")
    p.add_argument("--landmarks", default=str(LM.DEFAULT_LANDMARKS),
                   help="landmarks whose water policy is honoured (default data/landmarks.json)")
    p.add_argument("--write-cells", default=None,
                   help="also write the terrain blocks into this cells file (data/cells.json), keeping authored fields")
    p.add_argument("--no-landmarks", action="store_true",
                   help="ignore landmarks: every enclosed hollow below sea level is water")
    a = p.parse_args(argv)
    landmarks = None
    if not a.no_landmarks:
        try:
            landmarks = LM.load(a.landmarks)
        except LM.LandmarkError as exc:
            raise SystemExit("landmarks: %s (pass --no-landmarks to measure without them)" % exc)
    try:
        heights, world = T.load_from_args(a)
    except T.TerrainUnavailable as exc:
        raise SystemExit("terrain unavailable: %s" % exc)
    no_water = LM.no_water_mask(landmarks, heights.shape) if landmarks else None
    try:
        cells, totals = measure(heights, world, a.coast_factor, no_water)
    except T.TerrainUnavailable as exc:
        raise SystemExit("terrain unavailable: %s" % exc)

    payload = {
        "schema": "cobblers.derived.cell_stats/1",
        "parameters": {"coast_factor": a.coast_factor,
                       "landmarks": None if a.no_landmarks else a.landmarks},
        "source": T.provenance(world, a.world),
        "notes": [
            "Slopes are in degrees. terrain.* covers the whole cell; land.* covers land only.",
            "Distance to sea is octagonal, within about 8% of Euclidean, at coast_factor-block resolution.",
            "Sea is water connected to the map edge; inland water is enclosed.",
            "Void is ground below sea level inside a landmark whose water policy is never.",
        ],
        "totals": totals,
        "cells": cells,
    }
    out = Path(a.out) if a.out else T.ROOT / "derived" / "cells" / "cell_stats.json"
    T.write_json(out, payload)
    print("%d cells -> %s" % (len(cells), out))
    if a.write_cells:
        write_cells(Path(a.write_cells), cells, world)
        print("terrain blocks written to %s" % a.write_cells)
    return 0


def write_cells(path, cells, world):
    """Write measured terrain into data/cells.json, keeping any authored fields already there."""
    import json
    import validate_data as V
    existing = {}
    doc = {"schema": "cobblers.cells/1", "status": "draft",
           "note": "One record per planning cell. terrain is measured by tools/cell_stats.py --write-cells and "
                   "re-checked by tools/validate_data.py; every other field is authored.",
           "cells": []}
    if path.is_file():
        old = json.loads(path.read_text(encoding="utf-8"))
        existing = {c["id"]: c for c in old.get("cells") or []}
        doc.update({k: v for k, v in old.items() if k != "cells"})
    digest = V.import_digest(world)
    for c in cells:
        rec = dict(existing.get(c["id"], {}))
        rec.update({"id": c["id"], "row": c["row"], "column": c["column"], "bounds": c["bounds"]})
        rec["terrain"] = dict(c["terrain"], computed_from_import=digest)
        doc["cells"].append(rec)
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
