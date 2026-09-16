#!/usr/bin/env python
"""Check a heightmap file for silent corruption before anything uses it.

Checks, each reported and failed on:
  decode       the PNG decodes to a single-channel 16-bit array of the expected size
  sha256       matches the expected hash, when one is given
  range        raw values inside 0..65535 with under 0.5% of columns at either rail (a clipped or
               mis-scaled file piles values on a rail)
  precision    under 5% of values are multiples of 257 (an 8-bit image scaled up to 16 bits)
  tears        adjacent-column jumps over 24 blocks, compared with the predecessor: a torn tile, shifted row or
               swapped byte order shows as many new jumps
  duplicates   no run of 8+ identical consecutive rows or columns over land that the predecessor did not have
  predecessor  columns changed, largest change, and changes outside an allowed box list

  python tools/heightmap_check.py FILE [--sha SHA] [--predecessor FILE] [--allow X0,Z0,X1,Z1 ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

import terrain as T

Image.MAX_IMAGE_PIXELS = None


def load_raw(path, size):
    img = Image.open(path)
    img.load()
    a = np.array(img)
    if a.ndim != 2:
        raise ValueError("%s has %d channels" % (path, a.shape[2] if a.ndim == 3 else -1))
    if a.dtype not in (np.uint16, np.int32, np.uint32):
        raise ValueError("%s decodes as %s, not 16-bit" % (path, a.dtype))
    if a.shape != (size, size):
        raise ValueError("%s is %s, not %dx%d" % (path, a.shape, size, size))
    if a.max() > 65535 or a.min() < 0:
        raise ValueError("%s has values outside 16 bits" % path)
    return a.astype(np.int32)


def dup_runs(a, land, axis, run=8):
    d = np.all(np.diff(a, axis=axis) == 0, axis=1 - axis) & np.any(land, axis=1 - axis)[1:]
    best = cur = 0
    for v in d:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best + 1 if best else 0


def tears(h):
    return int((np.abs(np.diff(h, axis=1)) > 24).sum() + (np.abs(np.diff(h, axis=0)) > 24).sum())


def check(path, world, sha=None, predecessor=None, allow=()):
    size = int((world.get("grid") or {}).get("size") or (world.get("heightmap") or {}).get("width") or 8192)
    rep, fails = {"file": str(path)}, []
    raw = load_raw(path, size)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    rep["sha256"] = digest
    if sha and digest != sha:
        fails.append("sha256 %s is not the expected %s" % (digest[:12], sha[:12]))
    rep["raw_min"], rep["raw_max"] = int(raw.min()), int(raw.max())
    rails = float(((raw == 0) | (raw == 65535)).mean())
    rep["rail_share"] = round(rails, 5)
    if rails > 0.005:
        fails.append("%.2f%% of columns sit on a rail" % (rails * 100))
    m257 = float((raw % 257 == 0).mean())
    rep["multiple_of_257_share"] = round(m257, 4)
    if m257 > 0.05:
        fails.append("%.1f%% of values are multiples of 257 (8-bit data)" % (m257 * 100))
    h = T.sample_to_height(raw, world).astype(np.float32)
    land = h > T.sea_level(world)
    rep["tears"] = tears(h)
    rep["duplicate_row_run"] = dup_runs(raw, land, 0)
    rep["duplicate_col_run"] = dup_runs(raw.T, land.T, 0)
    if predecessor:
        praw = load_raw(predecessor, size)
        ph = T.sample_to_height(praw, world).astype(np.float32)
        ptears = tears(ph)
        rep["predecessor"] = {"file": str(predecessor), "tears": ptears}
        if rep["tears"] > ptears * 1.5 + 1000:
            fails.append("tears %d against the predecessor's %d" % (rep["tears"], ptears))
        pl = ph > T.sea_level(world)
        for k, p_run in (("duplicate_row_run", dup_runs(praw, pl, 0)), ("duplicate_col_run", dup_runs(praw.T, pl.T, 0))):
            if rep[k] >= 8 and rep[k] > p_run:
                fails.append("%s %d (predecessor %d)" % (k, rep[k], p_run))
        d = h - ph
        changed = raw != praw
        rep["predecessor"].update({"columns_changed": int(changed.sum()), "changed_half_block": int((np.abs(d) >= 0.5).sum()),
                                   "max_raise": round(float(d.max()), 2), "max_lower": round(float(d.min()), 2)})
        if allow:
            inside = np.zeros_like(changed)
            for x0, z0, x1, z1 in allow:
                inside[max(0, z0):z1 + 1, max(0, x0):x1 + 1] = True
            out = changed & ~inside
            rep["predecessor"]["changed_outside_allowed"] = int(out.sum())
            if out.any():
                zs, xs = np.nonzero(out)
                fails.append("%d columns changed outside the allowed boxes, e.g. (%d, %d)" % (out.sum(), xs[0], zs[0]))
    rep["ok"] = not fails
    rep["failures"] = fails
    return rep


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("file")
    p.add_argument("--world", default=str(T.ROOT / "data" / "world.json"))
    p.add_argument("--sha", default=None)
    p.add_argument("--predecessor", default=None)
    p.add_argument("--allow", nargs="*", default=[], help="X0,Z0,X1,Z1 boxes where changes are expected")
    a = p.parse_args(argv)
    world = T.load_world(a.world)
    allow = [tuple(int(v) for v in s.split(",")) for s in a.allow]
    rep = check(a.file, world, a.sha, a.predecessor, allow)
    print(json.dumps(rep, indent=1))
    raise SystemExit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
