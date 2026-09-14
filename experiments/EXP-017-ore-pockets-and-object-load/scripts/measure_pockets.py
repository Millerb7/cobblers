#!/usr/bin/env python
"""EXP-017 Task A: measure Underground Pockets exports (read-only).

  python measure_pockets.py <tools dir> <out.json> [--rows LO HI] <world dir> [<world dir> ...]

The worlds are the 256x256 flat (y=100) worlds written by pockets_sweep.js / pockets_verify.js. The
stand-in ore is every block whose namespace is not "minecraft:" (vanilla ores placed by WorldPainter's
default Resources layer are ignored). Only rows LO..HI are measured (default -63..94: above bedrock and
below the 5-block top layer, i.e. every cell there is underground).

Per world:
  permille       ore cells per 1,000 cells in the measured rows (pockets overwrite any host block,
                 so "cells" = host rock volume)
  row_permille   the same per y (list, LO first) - shows the 4-block aliasing of the noise lattice
  blobs          6-connected components of ore cells inside the measured rows
  blob_size_*    blocks per blob: mean / median / p90 / max and a histogram (sizes >= 50 pooled)
  blobs_per_1000 blobs per 1,000 cells
Needs numpy; uses scipy.ndimage.label when available, else a numpy union-find.
"""
import json
import sys
from pathlib import Path

import numpy as np

args = sys.argv[1:]
tools, out = args[0], Path(args[1])
rest = args[2:]
LO, HI = -63, 94
if rest and rest[0] == "--rows":
    LO, HI = int(rest[1]), int(rest[2])
    rest = rest[3:]
sys.path.insert(0, tools)
import nbt  # noqa: E402
from world_heights import unpack_states  # noqa: E402

Y0, NY = -64, 384


def load(world):
    index = {"minecraft:air": 0}
    grid = np.zeros((NY, 256, 256), dtype=np.int16)  # [y, z, x]; missing sections stay air
    for mca in sorted((Path(world) / "region").glob("*.mca")):
        for _, _, ch in nbt.region_chunks(mca):
            cx, cz = ch["xPos"], ch["zPos"]
            if not (0 <= cx < 16 and 0 <= cz < 16):
                continue
            for sec in ch.get("sections", []):
                bs = sec.get("block_states")
                if not bs:
                    continue
                pal = [p["Name"] for p in bs["palette"]]
                ids = np.array([index.setdefault(n, len(index)) for n in pal], dtype=np.int16)
                sy = sec["Y"] * 16 - Y0
                if sy < 0 or sy + 16 > NY:
                    continue
                idx = unpack_states(bs.get("data"), len(pal)).reshape(16, 16, 16)
                grid[sy:sy + 16, cz * 16:cz * 16 + 16, cx * 16:cx * 16 + 16] = ids[idx]
    return grid, list(index)


def label(mask):
    try:
        from scipy import ndimage
        return ndimage.label(mask)
    except ImportError:
        pass
    shape = mask.shape
    flat = mask.ravel()
    idx = np.flatnonzero(flat)
    parent = np.arange(flat.size, dtype=np.int64)

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root

    sy, sz, sx = shape
    coords = np.stack(np.unravel_index(idx, shape), axis=1)
    for axis, step in ((2, 1), (1, sx), (0, sx * sz)):
        ok = coords[:, axis] < shape[axis] - 1
        a = idx[ok]
        b = a + step
        both = flat[b]
        for i, j in zip(a[both], b[both]):
            ri, rj = find(int(i)), find(int(j))
            if ri != rj:
                parent[rj] = ri
    roots = np.array([find(int(i)) for i in idx], dtype=np.int64)
    _, lab_ids = np.unique(roots, return_inverse=True)
    lab = np.zeros(flat.size, dtype=np.int32)
    lab[idx] = lab_ids + 1
    return lab.reshape(shape), int(lab_ids.max() + 1) if idx.size else 0


def summarise(ore):
    """ore: bool array [rows, 256, 256] -> density and blob statistics."""
    cells = ore.size
    lab, n = label(ore)
    sizes = np.bincount(lab.ravel())[1:] if n else np.array([], dtype=np.int64)
    return {
        "cells": int(cells),
        "ore": int(ore.sum()),
        "permille": round(1000.0 * ore.sum() / cells, 4),
        "row_permille": [round(1000.0 * r.sum() / r.size, 3) for r in ore],
        "blobs": int(n),
        "blobs_per_1000": round(1000.0 * n / cells, 5),
        "blob_size_mean": round(float(sizes.mean()), 3) if n else None,
        "blob_size_median": float(np.median(sizes)) if n else None,
        "blob_size_p90": float(np.percentile(sizes, 90)) if n else None,
        "blob_size_max": int(sizes.max()) if n else None,
        "blob_size_hist": {str(k): int(v) for k, v in zip(*np.unique(np.minimum(sizes, 50), return_counts=True))} if n else {},
    }


if __name__ == "__main__":
    results = []
    for world in rest:
        grid, names = load(world)
        sub = grid[LO - Y0:HI - Y0 + 1]
        ore_ids = [i for i, nm in enumerate(names) if not nm.startswith("minecraft:")]
        res = {"world": Path(world).name, "rows": [LO, HI], "ore_names": [names[i] for i in ore_ids],
               "air_cells_in_rows": int((sub == 0).sum())}
        res.update(summarise(np.isin(sub, ore_ids)))
        results.append(res)
        print(json.dumps({k: v for k, v in res.items() if k not in ("row_permille", "blob_size_hist")}))
    out.write_text(json.dumps(results), encoding="utf8")
