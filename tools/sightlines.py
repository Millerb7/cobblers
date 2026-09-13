#!/usr/bin/env python
"""Raycast from a viewpoint to named landmarks and report what is visible.

Walks the straight line between observer and target, comparing the terrain
height under each sample against the height of the line at that point. The
first sample where terrain rises above the line is the blocker.

  python tools/sightlines.py --world tests/fixtures/terrain/world.json \
      --from 60,130 --eye 2 --target crest:112,130 --target far_base:180,130
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

import terrain as T


def parse_point(s):
    x, z = s.split(",")
    return int(x), int(z)


def parse_target(s):
    if ":" not in s:
        raise argparse.ArgumentTypeError("target must be NAME:X,Z")
    name, pos = s.split(":", 1)
    x, z = pos.split(",")
    return {"name": name, "x": int(x), "z": int(z)}


def sample_height(heights, x, z):
    h, w = heights.shape
    xi = min(max(int(round(x)), 0), w - 1)
    zi = min(max(int(round(z)), 0), h - 1)
    return float(heights[zi, xi])


def cast(heights, observer, eye, target, target_height, step=0.5, margin=1.0):
    """margin: blocks at each end excluded from occlusion.

    Without it, a target standing on the highest ground grazes its own summit
    and reports itself as the blocker.
    """
    ox, oz = observer
    tx, tz = target["x"], target["z"]
    oy = sample_height(heights, ox, oz) + eye
    ty = sample_height(heights, tx, tz) + target_height
    dist = math.hypot(tx - ox, tz - oz)
    if dist == 0:
        return {"visible": True, "distance": 0.0, "blocked_at": None,
                "min_clearance": None}

    n = max(2, int(dist / step))
    worst = None
    blocked_at = None
    for i in range(1, n):
        f = i / n
        along = dist * f
        if along <= margin or (dist - along) <= margin:
            continue
        x = ox + (tx - ox) * f
        z = oz + (tz - oz) * f
        line_y = oy + (ty - oy) * f
        ground = sample_height(heights, x, z)
        clearance = line_y - ground
        if worst is None or clearance < worst["clearance"]:
            worst = {"clearance": clearance, "x": x, "z": z,
                     "ground": ground, "line_y": line_y, "fraction": f}
        if clearance < 0 and blocked_at is None:
            blocked_at = {"x": round(x, 1), "z": round(z, 1),
                          "ground_y": round(ground, 2),
                          "line_y": round(line_y, 2),
                          "distance": round(dist * f, 1)}
    return {
        "visible": blocked_at is None,
        "distance": round(dist, 2),
        "observer_y": round(oy, 2),
        "target_y": round(ty, 2),
        "blocked_at": blocked_at,
        "min_clearance": round(worst["clearance"], 3) if worst else None,
        "min_clearance_at": {"x": round(worst["x"], 1), "z": round(worst["z"], 1)}
        if worst else None,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--from", dest="observer", required=True, metavar="X,Z")
    p.add_argument("--eye", type=float, default=2.0, help="observer eye height in blocks")
    p.add_argument("--target", action="append", type=parse_target, default=[],
                   metavar="NAME:X,Z", help="repeatable")
    p.add_argument("--target-height", type=float, default=0.0,
                   help="height above ground of the thing being looked at")
    p.add_argument("--step", type=float, default=0.5, help="sample spacing in blocks")
    p.add_argument("--margin", type=float, default=1.0,
                   help="blocks excluded at each end, so a target does not occlude itself")
    p.add_argument("--id", default="sightlines")
    a = p.parse_args(argv)

    if not a.target:
        raise SystemExit("at least one --target NAME:X,Z is required")

    try:
        heights, world = T.load_from_args(a)
    except T.TerrainUnavailable as exc:
        raise SystemExit("terrain unavailable: %s" % exc)

    observer = parse_point(a.observer)
    results = []
    for t in a.target:
        r = cast(heights, observer, a.eye, t, a.target_height, a.step, a.margin)
        r["name"] = t["name"]
        r["target"] = {"x": t["x"], "z": t["z"]}
        results.append(r)

    payload = {
        "schema": "cobblers.derived.sightlines/1",
        "id": a.id,
        "parameters": {
            "from": list(observer), "eye": a.eye,
            "target_height": a.target_height, "step": a.step, "margin": a.margin,
        },
        "source": T.provenance(world, a.world),
        "visible_count": sum(1 for r in results if r["visible"]),
        "results": results,
    }
    out = Path(a.out) if a.out else T.ROOT / "derived" / "sightlines" / ("%s.json" % a.id)
    T.write_json(out, payload)
    for r in results:
        if r["visible"]:
            print("  VISIBLE  %-14s %6.1f blocks, clearance %.2f"
                  % (r["name"], r["distance"], r["min_clearance"]))
        else:
            b = r["blocked_at"]
            print("  BLOCKED  %-14s %6.1f blocks, by ground y=%.1f at (%.0f, %.0f)"
                  % (r["name"], r["distance"], b["ground_y"], b["x"], b["z"]))
    print("-> %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
