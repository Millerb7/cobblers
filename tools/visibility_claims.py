#!/usr/bin/env python
"""Measure every visibility claim in data/visibility.json, the way off-path distances are measured.

A claim says one thing can (or cannot) be seen from somewhere. It records where the claim is stated (recorded_in),
what observes (observers), what is looked at (target), over bare terrain or the planned canopy (surface), and what
was measured last time (measured). tools/validate_data.py re-measures each claim and fails when the count drifts, when a
claim measures false, or when a claim's fragility flag does not match the rule. This tool writes the measurements.

Casts use tools/sightlines.py. Landmark-tree targets use tools/landmark_trees.py's own visibility (eye 1.6, crown top
less 3, the tree's glade lowered) so the claims agree with the tree survey; every other target uses eye 1.62, a
1-block step and 3 blocks excluded at each end.

Observers:  leg (a "from->to" leg of data/routes.json, spacing), route (route_id, spacing, optional
            near_water_crossings_blocks), point (at), points (points), town_centre (town), footprint_grid (town, step),
            footprint_edges (town, sides, step), ring (radius, n; around the target tree)
Targets:    landmark_tree (id), town (id, height_above_ground), point (at, height_above_ground, optional end_margin),
            absolute (at, y), landmark_extent (landmark), course (course, within_blocks, count "targets" or
            "observers"), array_mast (the Route 3 Nosepass sightline margin; tools/nosepass_sightline.py)

  python tools/visibility_claims.py --source-root <root>            # report measured against recorded
  python tools/visibility_claims.py --source-root <root> --write    # rewrite measured and fragile
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import landmark_trees as L  # noqa: E402
import sightlines as SL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EYE, STEP, END_MARGIN = 1.62, 1.0, 3.0
FRAGILE_MAX_SEEN = 10          # a positive claim seen from this few points, or
FRAGILE_MAX_SHARE = 0.05       # this small a share, is fragile: one foliage or terrain change can break it
FRAGILE_MIN_MARGIN = 2.0       # a sightline margin under this many blocks is fragile


class Inputs:
    def __init__(self, data_dir, heights, world, canopy_path):
        d = Path(data_dir)
        self.heights, self.world = heights, world
        self.routes = json.loads((d / "routes.json").read_text(encoding="utf-8"))
        self.towns = {t["id"]: t for t in json.loads((d / "towns.json").read_text(encoding="utf-8"))["towns"]}
        self.landmarks = {l["id"]: l for l in json.loads((d / "landmarks.json").read_text(encoding="utf-8"))["landmarks"]}
        self.foliage = json.loads((d / "foliage.json").read_text(encoding="utf-8"))
        self.rivers = json.loads((d / "rivers.json").read_text(encoding="utf-8"))
        lib = json.loads((d.parent / "kits" / "structures" / "foliage" / "library.json").read_text(encoding="utf-8"))
        self.tree_heights = {r["name"]: r["height"] for r in lib["objects"]}
        self.canopy_path = Path(canopy_path) if canopy_path else None
        self.canopy_sha256 = None
        self._surface = None
        if self.canopy_path and self.canopy_path.exists():
            self.canopy_sha256 = hashlib.sha256(self.canopy_path.read_bytes()).hexdigest()

    def surface(self, kind):
        if kind == "terrain":
            return None
        if self._surface is None:
            if self.canopy_sha256 is None:
                raise FileNotFoundError("the planned canopy %s is absent" % self.canopy_path)
            self._surface = L._surface(self.heights, str(self.canopy_path))
        return self._surface


def _route(inp, route_id):
    return next(r for r in inp.routes["routes"] if r["id"] == route_id)


def _sample(polyline, spacing):
    """(x, z, along) every `spacing` blocks along a polyline, as landmark_trees.leg_points samples it."""
    p = np.array([[q["x"], q["z"]] for q in polyline], float)
    seg = np.hypot(*np.diff(p, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    out = []
    for d in np.arange(0, cum[-1], spacing):
        i = min(np.searchsorted(cum, d, side="right") - 1, len(seg) - 1)
        t = (d - cum[i]) / max(seg[i], 1e-6)
        out.append((float(p[i, 0] + (p[i + 1, 0] - p[i, 0]) * t), float(p[i, 1] + (p[i + 1, 1] - p[i, 1]) * t), float(d)))
    return out


def observers(spec, inp, target_site=None):
    k = spec["type"]
    if k == "leg":
        a, b = spec["leg"].split("->")
        r = next(r for r in inp.routes["routes"] if r["from_town"] == a and r["to_town"] == b)
        return [(x, z) for x, z, _ in _sample(r["corridor"]["polyline"], spec.get("spacing", 48))]
    if k == "route":
        r = _route(inp, spec["route_id"])
        pts = _sample(r["corridor"]["polyline"], spec.get("spacing", 16))
        near = spec.get("near_water_crossings_blocks")
        if near is not None:
            spans = [(w["start"]["at_distance_blocks"] - near, w["end"]["at_distance_blocks"] + near) for w in r["water_crossings"]]
            pts = [p for p in pts if any(lo <= p[2] <= hi for lo, hi in spans)]
        return [(x, z) for x, z, _ in pts]
    if k == "point":
        return [tuple(spec["at"])]
    if k == "points":
        return [tuple(p) for p in spec["points"]]
    if k == "town_centre":
        c = inp.towns[spec["town"]]["centre"]
        return [(c["x"], c["z"])]
    if k in ("footprint_grid", "footprint_edges"):
        fp = inp.towns[spec["town"]]["footprint"]
        step = spec.get("step", 5)
        if k == "footprint_grid":
            return [(x, z) for x in range(fp["min_x"], fp["max_x"] + 1, step) for z in range(fp["min_z"], fp["max_z"] + 1, step)]
        pts = []
        for side in spec["sides"]:
            if side in ("east", "west"):
                x = fp["max_x"] if side == "east" else fp["min_x"]
                pts += [(x, z) for z in range(fp["min_z"], fp["max_z"] + 1, step)]
            else:
                z = fp["min_z"] if side == "north" else fp["max_z"]
                pts += [(x, z) for x in range(fp["min_x"], fp["max_x"] + 1, step)]
        return pts
    if k == "ring":
        x, z = target_site
        n = spec.get("n", 24)
        return [(x + math.cos(2 * math.pi * i / n) * spec["radius"], z + math.sin(2 * math.pi * i / n) * spec["radius"]) for i in range(n)]
    raise ValueError("unknown observer type %r" % k)


def _cast(inp, o, at, height, surface, end_margin=END_MARGIN):
    return SL.cast(inp.heights, o, EYE, {"x": at[0], "z": at[1]}, height, step=STEP, margin=end_margin, surface=surface)["visible"]


def measure(claim, inp):
    """{"seen": n, "of": N, "unit": ...} or, for array_mast, {"margin_blocks": m}."""
    t, surface_kind = claim["target"], claim.get("surface", "terrain")
    k = t["type"]
    if k == "array_mast":
        import nosepass_sightline as N
        arr = inp.landmarks["surge_signal_array"]
        ss = arr["site"]["nosepass_view"]["canopy_clear"]["sign_site"]
        regions = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
        lib = json.loads((ROOT / "kits" / "structures" / "foliage" / "library.json").read_text(encoding="utf-8"))
        model = N.model_canopy(inp.heights, regions, inp.foliage, lib)
        ax, az = arr["anchor"]["x"], arr["anchor"]["z"]
        top = float(inp.heights[az, ax]) + arr["site"]["mast_blocks"]
        x, z = ss["at"]
        m = N.margins(inp.heights, model, None, None, x, z, ax, az, top, float(ss["clearing"]["along_sightline_blocks"]))
        return {"margin_blocks": round(m["model_margin"], 1)}
    surf = inp.surface(surface_kind)
    if k == "landmark_tree":
        spec = next(s for s in inp.foliage["landmark_trees"] if s["id"] == t["id"])
        x, z = spec["site"]
        g = int(spec.get("glade_radius", 24))
        pts = observers(claim["observers"], inp, (x, z))
        base = inp.heights if surf is None else surf
        s = base.copy() if surf is None else surf
        win = (slice(max(0, z - g), z + g + 1), slice(max(0, x - g), x + g + 1))
        saved = s[win].copy()
        s[win] = inp.heights[win]
        try:
            v = L.visibility(inp.heights, s, (x, z), inp.tree_heights[spec["object"]], pts)
        finally:
            s[win] = saved
        return {"seen": v["visible"], "of": v["observers"], "unit": "observer points"}
    pts = observers(claim["observers"], inp)
    if k in ("town", "point", "absolute"):
        if k == "town":
            c = inp.towns[t["id"]]["centre"]
            at, h = (c["x"], c["z"]), t["height_above_ground"]
        elif k == "point":
            at, h = tuple(t["at"]), t["height_above_ground"]
        else:
            at = tuple(t["at"])
            h = t["y"] - float(inp.heights[at[1], at[0]])
        em = t.get("end_margin", END_MARGIN)
        seen = sum(_cast(inp, o, at, h, surf, em) for o in pts)
        return {"seen": seen, "of": len(pts), "unit": "observer points"}
    if k == "landmark_extent":
        lm = inp.landmarks[t["landmark"]]
        assert len(pts) == 1, "landmark_extent claims take one observer"
        r = SL.cast_extent(inp.heights, pts[0], EYE, {"landmark": lm}, 0.5, 2.0, END_MARGIN)
        return {"seen": r["visible_samples"], "of": r["samples"], "unit": "target samples"}
    if k == "course":
        course = next(c for c in inp.rivers["courses"] if c["id"] == t["course"])
        within = t["within_blocks"]
        if t.get("count", "targets") == "targets":
            assert len(pts) == 1, "a course claim counting targets takes one observer"
            o = pts[0]
            targets = [q for q in course["graded_polyline"] if math.hypot(q[0] - o[0], q[1] - o[1]) <= within]
            seen = sum(_cast(inp, o, (q[0], q[1]), 1.0, surf) for q in targets)
            return {"seen": seen, "of": len(targets), "unit": "target samples"}
        seen = 0
        for o in pts:
            if any(math.hypot(q[0] - o[0], q[1] - o[1]) <= within and _cast(inp, o, (q[0], q[1]), 1.0, surf)
                   for q in course["graded_polyline"]):
                seen += 1
        return {"seen": seen, "of": len(pts), "unit": "observer points"}
    raise ValueError("unknown target type %r" % k)


def is_fragile(claim, m):
    """The fragility rule: a positive claim that holds on few points or a small share, or a thin sightline margin."""
    if "margin_blocks" in m:
        return m["margin_blocks"] < FRAGILE_MIN_MARGIN
    if claim["expect"] != "visible":
        return False
    return m["seen"] <= FRAGILE_MAX_SEEN or (m["of"] and m["seen"] / m["of"] < FRAGILE_MAX_SHARE)


def holds(claim, m):
    if "margin_blocks" in m:
        return m["margin_blocks"] > 0
    return m["seen"] > 0 if claim["expect"] == "visible" else m["seen"] == 0


def main(argv=None):
    import terrain as T
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--data", default=str(ROOT / "data"))
    p.add_argument("--canopy", default=str(ROOT / "build" / "paint" / "canopy.npz"))
    p.add_argument("--only", nargs="*", help="claim ids")
    p.add_argument("--write", action="store_true")
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    path = Path(a.data) / "visibility.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    inp = Inputs(a.data, heights, world, a.canopy)
    print("canopy sha256 %s (recorded %s)" % (inp.canopy_sha256, doc["canopy"]["sha256"]))
    changed = 0
    for c in doc["claims"]:
        if a.only and c["id"] not in a.only:
            continue
        m = measure(c, inp)
        fr = bool(is_fragile(c, m))
        flag = "" if holds(c, m) else "  FALSE"
        if c.get("measured") != m or c.get("fragile") != fr:
            changed += 1
            print("%-44s %s -> %s fragile %s%s" % (c["id"], json.dumps(c.get("measured")), json.dumps(m), fr, flag))
            c["measured"], c["fragile"] = m, fr
        else:
            print("%-44s unchanged %s fragile %s%s" % (c["id"], json.dumps(m), fr, flag))
    if a.write:
        doc["canopy"]["sha256"] = inp.canopy_sha256
        doc["heightmap_sha256"] = world["heightmap"]["sha256"]
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("wrote %s (%d changed)" % (path, changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
