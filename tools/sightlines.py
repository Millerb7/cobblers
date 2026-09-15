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
import landmarks as LM


def parse_point(s):
    """X,Z, or @LANDMARK[.ANCHOR] to be resolved against the landmarks file."""
    if s.startswith("@"):
        return s
    x, z = s.split(",")
    return int(x), int(z)


def parse_target(s):
    """NAME:X,Z | NAME:@LANDMARK[.ANCHOR] | @LANDMARK[.ANCHOR] | @LANDMARK* (whole extent)."""
    if s.startswith("@") and s.endswith("*"):
        return {"name": s[1:-1] + " (extent)", "extent": s[1:-1]}
    if s.startswith("@"):
        return {"name": s[1:], "ref": s}
    if ":" not in s:
        raise argparse.ArgumentTypeError("target must be NAME:X,Z, @LANDMARK[.ANCHOR] or @LANDMARK*")
    name, pos = s.split(":", 1)
    if pos.startswith("@"):
        return {"name": name, "ref": pos}
    x, z = pos.split(",")
    return {"name": name, "x": int(x), "z": int(z)}


def resolve_refs(observer, targets, landmarks_path):
    """Replace @landmark references with coordinates; attach extents for @landmark*."""
    if not (isinstance(observer, str) or any("ref" in t or "extent" in t for t in targets)):
        return observer, targets
    try:
        doc = LM.load(landmarks_path)
        if isinstance(observer, str):
            observer = LM.point(doc, observer[1:])
        for t in targets:
            if "ref" in t:
                t["x"], t["z"] = LM.point(doc, t["ref"][1:])
            elif "extent" in t:
                t["landmark"] = LM.get(doc, t["extent"])
                if not (t["landmark"].get("extent") or {}).get("polygons"):
                    raise LM.LandmarkError("landmark %s has no extent to sample" % t["extent"])
    except LM.LandmarkError as exc:
        raise SystemExit("landmarks: %s" % exc)
    return observer, targets


def extent_samples(lm, heights, spacing=64.0, top=40):
    """Points that stand for 'any part of this landmark': its outline, densified
    to spacing, plus its highest ground, at least spacing apart.

    A flat-topped summit hides its own centre from anyone below it; its edge is
    what an observer actually sees, so the outline is sampled, not the anchor.
    """
    pts = []
    for poly in lm["extent"]["polygons"]:
        ring = poly + poly[:1]
        for (x0, z0), (x1, z1) in zip(ring, ring[1:]):
            n = max(1, int(math.hypot(x1 - x0, z1 - z0) // spacing))
            for i in range(n):
                pts.append((x0 + (x1 - x0) * i / n, z0 + (z1 - z0) * i / n))
    f = 8
    m = LM.mask(lm, (heights.shape[0] // f, heights.shape[1] // f), factor=f)
    zs, xs = np.nonzero(m)
    if len(zs):
        hz = heights[zs * f + f // 2, xs * f + f // 2]
        chosen = []
        for k in np.argsort(-hz):
            x, z = float(xs[k] * f + f // 2), float(zs[k] * f + f // 2)
            if all((x - cx) ** 2 + (z - cz) ** 2 >= spacing ** 2 for cx, cz in chosen):
                chosen.append((x, z))
                if len(chosen) >= top:
                    break
        pts += chosen
    h, w = heights.shape
    return [(min(max(x, 0), w - 1), min(max(z, 0), h - 1)) for x, z in pts]

def sample_height(heights, x, z):
    h, w = heights.shape
    xi = min(max(int(round(x)), 0), w - 1)
    zi = min(max(int(round(z)), 0), h - 1)
    return float(heights[zi, xi])


def cast(heights, observer, eye, target, target_height, step=0.5, margin=1.0):
    """margin: blocks at each end excluded from occlusion.

    Without it, a target standing on the highest ground grazes its own summit
    and reports itself as the blocker. Samples are taken every step blocks and
    compared against the nearest heightmap block.
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
    f = np.arange(1, n) / n
    along = dist * f
    keep = (along > margin) & ((dist - along) > margin)
    f = f[keep]
    if f.size == 0:
        return {"visible": True, "distance": round(dist, 2), "observer_y": round(oy, 2),
                "target_y": round(ty, 2), "blocked_at": None, "min_clearance": None,
                "min_clearance_at": None}
    x = ox + (tx - ox) * f
    z = oz + (tz - oz) * f
    line_y = oy + (ty - oy) * f
    hh, ww = heights.shape
    xi = np.clip(np.rint(x).astype(np.int64), 0, ww - 1)
    zi = np.clip(np.rint(z).astype(np.int64), 0, hh - 1)
    ground = heights[zi, xi].astype(np.float64)
    clearance = line_y - ground
    w = int(np.argmin(clearance))
    below = np.flatnonzero(clearance < 0)
    blocked_at = None
    if below.size:
        i = int(below[0])
        blocked_at = {"x": round(float(x[i]), 1), "z": round(float(z[i]), 1),
                      "ground_y": round(float(ground[i]), 2),
                      "line_y": round(float(line_y[i]), 2),
                      "distance": round(float(dist * f[i]), 1)}
    return {
        "visible": blocked_at is None,
        "distance": round(dist, 2),
        "observer_y": round(oy, 2),
        "target_y": round(ty, 2),
        "blocked_at": blocked_at,
        "min_clearance": round(float(clearance[w]), 3),
        "min_clearance_at": {"x": round(float(x[w]), 1), "z": round(float(z[w]), 1)},
    }


def cast_extent(heights, observer, eye, target, target_height, step, margin):
    """Any part of a landmark visible? Casts to every extent sample."""
    pts = extent_samples(target["landmark"], heights)
    hits = []
    for x, z in pts:
        r = cast(heights, observer, eye, {"x": x, "z": z}, target_height, step, margin)
        hits.append((r, x, z))
    vis = [(r, x, z) for r, x, z in hits if r["visible"]]
    best = min(vis, key=lambda t: t[0]["distance"]) if vis else max(
        hits, key=lambda t: t[0]["min_clearance"] if t[0]["min_clearance"] is not None else -1e9)
    r, x, z = best
    return {
        "visible": bool(vis),
        "samples": len(hits),
        "visible_samples": len(vis),
        "visible_fraction": round(len(vis) / len(hits), 3) if hits else 0.0,
        "distance": r["distance"],
        "observer_y": r.get("observer_y"),
        "target_y": r.get("target_y"),
        "blocked_at": None if vis else r["blocked_at"],
        "min_clearance": r["min_clearance"],
        "min_clearance_at": r.get("min_clearance_at"),
        "nearest_visible_point" if vis else "least_blocked_point": {"x": round(x, 1), "z": round(z, 1)},
    }

def run_set(heights, observer, eye, targets, target_height, step, margin):
    results = []
    for t in targets:
        if "extent" in t:
            r = cast_extent(heights, observer, eye, t, target_height, step, margin)
            r["name"] = t["name"]
            r["target"] = {"landmark": t["extent"], "mode": "extent"}
        else:
            r = cast(heights, observer, eye, t, target_height, step, margin)
            r["name"] = t["name"]
            r["target"] = {"x": t["x"], "z": t["z"]}
            if "ref" in t:
                r["target"]["landmark"] = t["ref"][1:]
        results.append(r)
    return results


def print_results(label, results):
    print(label)
    for r in results:
        extra = (" (%d of %d outline and summit points)" % (r["visible_samples"], r["samples"])
                 if "samples" in r else "")
        if r["visible"]:
            print("  VISIBLE  %-28s %7.1f blocks, clearance %.2f%s"
                  % (r["name"], r["distance"], r["min_clearance"], extra))
        else:
            b = r["blocked_at"]
            print("  BLOCKED  %-28s %7.1f blocks, by ground y=%.1f at (%.0f, %.0f)%s"
                  % (r["name"], r["distance"], b["ground_y"], b["x"], b["z"], extra))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from", dest="observer", metavar="X,Z|@LANDMARK.ANCHOR")
    src.add_argument("--plan", help="JSON file of sightline sets: "
                                    '{"sets": [{"id", "from", "targets", "eye"?, "target_height"?}]}')
    p.add_argument("--landmarks", default=str(LM.DEFAULT_LANDMARKS))
    p.add_argument("--eye", type=float, default=2.0, help="observer eye height in blocks")
    p.add_argument("--target", action="append", type=parse_target, default=[],
                   metavar="NAME:X,Z|@LANDMARK.ANCHOR", help="repeatable")
    p.add_argument("--target-height", type=float, default=0.0,
                   help="height above ground of the thing being looked at")
    p.add_argument("--step", type=float, default=0.5, help="sample spacing in blocks")
    p.add_argument("--margin", type=float, default=1.0,
                   help="blocks excluded at each end, so a target does not occlude itself")
    p.add_argument("--id", default="sightlines")
    a = p.parse_args(argv)

    if a.plan:
        plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
        sets = []
        for s in plan.get("sets") or []:
            targets = [parse_target(t) for t in s["targets"]]
            observer, targets = resolve_refs(parse_point(s["from"]), targets, a.landmarks)
            sets.append(dict(s, observer=observer, parsed=targets))
        if not sets:
            raise SystemExit("the plan holds no sets")
    else:
        if not a.target:
            raise SystemExit("at least one --target is required")
        observer, targets = resolve_refs(parse_point(a.observer), a.target, a.landmarks)
        sets = [{"id": a.id, "from": a.observer, "observer": observer, "parsed": targets}]

    try:
        heights, world = T.load_from_args(a)
    except T.TerrainUnavailable as exc:
        raise SystemExit("terrain unavailable: %s" % exc)

    out_sets = []
    for s in sets:
        eye = float(s.get("eye", a.eye))
        th = float(s.get("target_height", a.target_height))
        results = run_set(heights, s["observer"], eye, s["parsed"], th, a.step, a.margin)
        out_sets.append({
            "id": s["id"],
            "note": s.get("note"),
            "parameters": {"from": list(s["observer"]), "from_ref": s["from"] if str(s["from"]).startswith("@") else None,
                           "eye": eye, "target_height": th, "step": a.step, "margin": a.margin},
            "visible_count": sum(1 for r in results if r["visible"]),
            "results": results,
        })
        print_results("%s from %s" % (s["id"], s["from"]), results)

    source = T.provenance(world, a.world)
    if a.plan:
        payload = {"schema": "cobblers.derived.sightlines/1", "id": Path(a.plan).stem,
                   "plan": str(a.plan), "source": source, "sets": out_sets}
        name = Path(a.plan).stem
    else:
        only = out_sets[0]
        payload = {"schema": "cobblers.derived.sightlines/1", "id": a.id,
                   "parameters": only["parameters"], "source": source,
                   "visible_count": only["visible_count"], "results": only["results"]}
        name = a.id
    out = Path(a.out) if a.out else T.ROOT / "derived" / "sightlines" / ("%s.json" % name)
    T.write_json(out, payload)
    print("-> %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
