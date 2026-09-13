#!/usr/bin/env python
"""Sample profiles perpendicular to a polyline and report valley shape.

Per-cell min/max/mean cannot tell a glacial trough from a stream valley. A
cross-section can: at each station along the axis this samples a transect at
right angles to it and measures

  floor_y        lowest ground on the transect (the thalweg)
  rims           highest ground either side of the thalweg
  depth          lower rim minus floor: how far the floor sits below the
                 surrounding surface it is cut into
  floor_width    width of the ground within floor_tolerance of the floor
  top_width      width below the lower rim, i.e. rim to rim
  level_width    width below a fixed Y such as sea level, when --level is set
  wall angles    mean slope of each wall between 20% and 80% of the depth
  b exponent     fit of (h - floor)/depth = (distance/half_width)^b over each
                 wall; b near 1 is a straight V wall, b near 2 a parabolic U

and classifies each profile as U, V, flat_floored, asymmetric or none. Every
threshold is a parameter and is recorded in the output.

The long profile of the floor is reported too. A glacial trough typically has
reversed (uphill) floor segments where a stream valley falls monotonically.

  python tools/cross_section.py --polyline 20,200;200,200 --width 60
  python tools/cross_section.py --source-root C:/Users/wnd/Documents \\
      --landmark glacier_corridor --axis trough
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

import terrain as T
import landmarks as LM

SHAPES = ("U", "V", "flat_floored", "asymmetric", "none")


def parse_polyline(s):
    pts = []
    for part in s.replace(" ", "").split(";"):
        if part:
            x, z = part.split(",")
            pts.append((float(x), float(z)))
    if len(pts) < 2:
        raise argparse.ArgumentTypeError("a polyline needs at least two X,Z points")
    return pts


def bilinear(heights, x, z):
    """Bilinear sample at fractional block coordinates, clamped to the map."""
    h, w = heights.shape
    x = np.clip(np.asarray(x, dtype=np.float64), 0, w - 1)
    z = np.clip(np.asarray(z, dtype=np.float64), 0, h - 1)
    x0 = np.minimum(np.floor(x).astype(np.int64), w - 2 if w > 1 else 0)
    z0 = np.minimum(np.floor(z).astype(np.int64), h - 2 if h > 1 else 0)
    fx, fz = x - x0, z - z0
    x1 = np.minimum(x0 + 1, w - 1)
    z1 = np.minimum(z0 + 1, h - 1)
    a = heights[z0, x0] * (1 - fx) + heights[z0, x1] * fx
    b = heights[z1, x0] * (1 - fx) + heights[z1, x1] * fx
    return a * (1 - fz) + b * fz


def stations(polyline, spacing):
    """Evenly spaced points along a polyline, with the local unit tangent.

    The tangent at a vertex is the segment the station lies on, so a sharp
    bend does not average two directions into one that fits neither.
    """
    pts = np.asarray(polyline, dtype=np.float64)
    seg = np.diff(pts, axis=0)
    seg_len = np.hypot(seg[:, 0], seg[:, 1])
    keep = seg_len > 0
    pts = np.vstack([pts[:1], pts[1:][keep]])
    seg, seg_len = seg[keep], seg_len[keep]
    total = float(seg_len.sum())
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    n = max(1, int(math.floor(total / spacing)))
    out = []
    for i in range(n + 1):
        d = min(i * spacing, total)
        k = min(int(np.searchsorted(cum, d, side="right")) - 1, len(seg) - 1)
        t = (d - cum[k]) / seg_len[k]
        p = pts[k] + t * seg[k]
        tan = seg[k] / seg_len[k]
        out.append((d, p, tan))
    return out, total


def _run_around(mask, i):
    """Inclusive [lo, hi] of the run of trues containing index i."""
    if not mask[i]:
        return i, i - 1
    lo = i
    while lo > 0 and mask[lo - 1]:
        lo -= 1
    hi = i
    while hi < len(mask) - 1 and mask[hi + 1]:
        hi += 1
    return lo, hi


def _wall_fit(offsets, prof, floor, depth, lo_frac, hi_frac):
    """Mean wall angle and power-law exponent for one wall.

    offsets are distances from the thalweg, increasing away from it, for the
    samples between the thalweg and that side's rim.
    """
    if depth <= 0 or len(offsets) < 3:
        return None, None
    rel = (prof - floor) / depth
    band = (rel >= lo_frac) & (rel <= hi_frac)
    angle = None
    if band.sum() >= 2:
        o, r = offsets[band], prof[band]
        run = float(o.max() - o.min())
        if run > 0:
            angle = math.degrees(math.atan(float(r.max() - r.min()) / run))
    b = None
    top = offsets[-1]
    fit = (rel > 0.05) & (rel < 0.95) & (offsets > 0)
    if top > 0 and fit.sum() >= 3:
        lx = np.log(offsets[fit] / top)
        ly = np.log(rel[fit])
        if np.ptp(lx) > 0:
            b = float(np.polyfit(lx, ly, 1)[0])
    return angle, b


def _rim(prof, i, direction, a, step=1.0):
    """Index of the wall top walking outward from the thalweg.

    The walk stops at whichever comes first:
      - the ground falls away by rim_drop past the highest point, so a hill
        beyond the far side of a shoulder is not mistaken for the valley wall;
      - the wall has climbed at least rim_flat_min_frac of the relief on that
        side (and at least min_depth), and the ground ahead flattens to under
        rim_flat_deg over rim_flat_run blocks: the break of slope at the top
        of the wall. Gently rising country beyond a steep wall is not wall,
        but a bench partway up a wall does not end it.
    A rise of less than rim_eps does not move the rim, so on a flat shoulder
    the rim is the nearest point of it.
    """
    floor = float(prof[i])
    best, best_i = floor, i
    run = max(1, int(round(a.rim_flat_run / step))) if a.rim_flat_deg is not None else 0
    flat_tan = math.tan(math.radians(a.rim_flat_deg)) if a.rim_flat_deg is not None else 0.0
    side = prof[:i + 1] if direction < 0 else prof[i:]
    min_climb = max(a.min_depth, a.rim_flat_min_frac * (float(side.max()) - floor))
    j = i + direction
    while 0 <= j < len(prof):
        h = float(prof[j])
        if h > best + a.rim_eps:
            best, best_i = h, j
        elif best - h > max(a.rim_drop, a.rim_drop_frac * (best - floor)):
            break
        if run and best - floor >= min_climb:
            k = j + direction * run
            n = j + direction
            # both the next sample and the run ahead must be flat, so the walk
            # does not stop one step short of the top of a steep wall
            if (0 <= k < len(prof) and (float(prof[k]) - h) / (run * step) < flat_tan
                    and (float(prof[n]) - h) / step < flat_tan):
                break
        j += direction
    return best_i


def analyse_profile(offsets, prof, a):
    """Measure and classify one transect. offsets run across the axis, left to right."""
    search = np.abs(offsets) <= (a.thalweg_window / 2.0 if a.thalweg_window else np.inf)
    i = int(np.flatnonzero(search)[np.argmin(prof[search])])
    floor = float(prof[i])
    step = float(offsets[1] - offsets[0]) if len(offsets) > 1 else 1.0
    li = _rim(prof, i, -1, a, step)
    ri = _rim(prof, i, 1, a, step)
    rim_l, rim_r = float(prof[li]), float(prof[ri])
    rim_low, rim_high = min(rim_l, rim_r), max(rim_l, rim_r)
    depth = rim_low - floor

    res = {
        "floor_y": round(floor, 2),
        "thalweg_offset": round(float(offsets[i]), 1),
        "rim_left": {"offset": round(float(offsets[li]), 1), "y": round(rim_l, 2)},
        "rim_right": {"offset": round(float(offsets[ri]), 1), "y": round(rim_r, 2)},
        "depth": round(depth, 2),
        "rim_difference": round(rim_high - rim_low, 2),
    }
    if a.level is not None:
        if floor < a.level:
            lo, hi = _run_around(prof < a.level, i)
            res["level_width"] = round((hi - lo + 1) * step, 1)
            res["level_run_clipped"] = bool(lo == 0 or hi == len(prof) - 1)
        else:
            res["level_width"] = 0.0
            res["level_run_clipped"] = False

    if depth < a.min_depth or li == i or ri == i:
        res.update(shape="none", floor_width=None, top_width=None,
                   wall_left_deg=None, wall_right_deg=None, b_left=None, b_right=None)
        return res

    tol = max(a.floor_tolerance, a.floor_tolerance_frac * depth)
    flo, fhi = _run_around(prof <= floor + tol, i)
    tlo, thi = _run_around(prof < rim_low, i)
    floor_width = (fhi - flo + 1) * step
    top_width = (thi - tlo + 1) * step

    # Each wall runs from the edge of the floor to its rim. Offsets are
    # measured from the floor edge, so a wide flat floor does not flatten b.
    lw_idx = np.arange(li, flo + 1)[::-1]
    rw_idx = np.arange(fhi, ri + 1)
    lw_off = np.abs(offsets[lw_idx] - offsets[flo])
    rw_off = np.abs(offsets[rw_idx] - offsets[fhi])
    ang_l, _ = _wall_fit(lw_off, prof[lw_idx], floor, depth, a.wall_low, a.wall_high)
    ang_r, _ = _wall_fit(rw_off, prof[rw_idx], floor, depth, a.wall_low, a.wall_high)

    # b over the whole half-profile from the thalweg, for U versus V
    hl_off = np.abs(offsets[np.arange(li, i + 1)[::-1]] - offsets[i])
    hr_off = np.abs(offsets[np.arange(i, ri + 1)] - offsets[i])
    _, bh_l = _wall_fit(hl_off, prof[np.arange(li, i + 1)[::-1]], floor, depth, 0, 1)
    _, bh_r = _wall_fit(hr_off, prof[np.arange(i, ri + 1)], floor, depth, 0, 1)
    bs = [b for b in (bh_l, bh_r) if b is not None]
    b_mean = sum(bs) / len(bs) if bs else None

    floor_frac = floor_width / top_width if top_width > 0 else 0.0
    angles = [x for x in (ang_l, ang_r) if x is not None]
    asym = False
    if rim_high - rim_low >= a.asym_rim_frac * (rim_high - floor):
        asym = True
    if len(angles) == 2:
        lo_a, hi_a = min(angles), max(angles)
        if hi_a - lo_a >= a.asym_angle_diff and hi_a >= a.asym_angle_ratio * max(lo_a, 1e-6):
            asym = True

    if floor_frac >= a.flat_floor_frac:
        base = "flat_floored"
    elif b_mean is not None and b_mean >= a.u_min_b:
        base = "U"
    else:
        base = "V"
    shape = "asymmetric" if asym else base

    res.update(
        shape=shape, base_shape=base, asymmetric=asym,
        floor_width=round(floor_width, 1), top_width=round(top_width, 1),
        floor_fraction=round(floor_frac, 3),
        wall_left_deg=None if ang_l is None else round(ang_l, 1),
        wall_right_deg=None if ang_r is None else round(ang_r, 1),
        b_left=None if bh_l is None else round(bh_l, 2),
        b_right=None if bh_r is None else round(bh_r, 2),
        b_mean=None if b_mean is None else round(b_mean, 2),
    )
    return res


def section(heights, polyline, a):
    sts, total = stations(polyline, a.spacing)
    half = a.width / 2.0
    offsets = np.arange(-half, half + 1e-9, a.sample_step)
    profiles = []
    for d, p, tan in sts:
        normal = np.array([-tan[1], tan[0]])  # left of the direction of travel
        xs = p[0] + normal[0] * offsets
        zs = p[1] + normal[1] * offsets
        prof = bilinear(heights, xs, zs)
        if a.smooth > 1:
            k = np.ones(a.smooth) / a.smooth
            prof = np.convolve(np.pad(prof, a.smooth // 2, mode="edge"), k, mode="valid")[:len(offsets)]
        r = analyse_profile(offsets, prof, a)
        tw = r["thalweg_offset"]
        for side in ("rim_left", "rim_right"):
            off = r[side]["offset"]
            r[side]["x"] = round(float(p[0] + normal[0] * off), 1)
            r[side]["z"] = round(float(p[1] + normal[1] * off), 1)
        r = {"distance": round(d, 1), "x": round(float(p[0]), 1), "z": round(float(p[1]), 1),
             "thalweg": {"x": round(float(p[0] + normal[0] * tw), 1),
                         "z": round(float(p[1] + normal[1] * tw), 1)}, **r}
        if a.keep_profiles:
            r["profile"] = [round(float(v), 2) for v in prof]
        profiles.append(r)
    return profiles, total


def summarise(profiles, level):
    def med(key):
        vals = [p[key] for p in profiles if p.get(key) is not None]
        return None if not vals else round(float(np.median(vals)), 2)

    def rng(key):
        vals = [p[key] for p in profiles if p.get(key) is not None]
        return None if not vals else [round(float(min(vals)), 2), round(float(max(vals)), 2)]

    counts = {s: 0 for s in SHAPES}
    for p in profiles:
        counts[p["shape"]] += 1
    walls = [w for p in profiles for w in (p.get("wall_left_deg"), p.get("wall_right_deg"))
             if w is not None]
    floors = [p["floor_y"] for p in profiles]
    rises = [b - a for a, b in zip(floors, floors[1:])]
    out = {
        "stations": len(profiles),
        "shape_counts": counts,
        "dominant_shape": max(counts, key=counts.get) if profiles else None,
        "floor_y": rng("floor_y"),
        "depth": {"median": med("depth"), "range": rng("depth")},
        "floor_width": {"median": med("floor_width"), "range": rng("floor_width")},
        "top_width": {"median": med("top_width"), "range": rng("top_width")},
        "wall_deg": {"median": None if not walls else round(float(np.median(walls)), 1),
                     "range": None if not walls else [round(min(walls), 1), round(max(walls), 1)]},
        "b_mean": {"median": med("b_mean"), "range": rng("b_mean")},
        "long_profile": {
            "start_floor_y": floors[0] if floors else None,
            "end_floor_y": floors[-1] if floors else None,
            "uphill_steps": sum(1 for r in rises if r > 0.5),
            "downhill_steps": sum(1 for r in rises if r < -0.5),
        },
    }
    if level is not None:
        lw = [p["level_width"] for p in profiles if "level_width" in p]
        out["level_width"] = {"level": level, "range": [min(lw), max(lw)] if lw else None,
                              "median": round(float(np.median(lw)), 1) if lw else None}
    return out


def build_parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--polyline", type=parse_polyline, metavar="X,Z;X,Z;...")
    src.add_argument("--landmark", help="landmark id in the landmarks file")
    p.add_argument("--landmarks", default=str(LM.DEFAULT_LANDMARKS))
    p.add_argument("--axis", default=None, help="axis id on the landmark (default: its first axis)")
    p.add_argument("--width", type=float, default=None,
                   help="full transect length across the axis, blocks (landmark default)")
    p.add_argument("--spacing", type=float, default=128.0, help="blocks between stations")
    p.add_argument("--sample-step", type=float, default=2.0, help="blocks between samples")
    p.add_argument("--smooth", type=int, default=1, help="moving-average window, samples")
    p.add_argument("--level", type=float, default=None,
                   help="also report the width below this Y, e.g. 62 for sea level")
    p.add_argument("--thalweg-window", type=float, default=None,
                   help="only look for the floor within this many blocks centred on the "
                        "axis (default: the middle half of the transect)")
    p.add_argument("--min-depth", type=float, default=6.0, help="shallower is shape none")
    p.add_argument("--rim-drop", type=float, default=3.0,
                   help="blocks the ground must fall past a high point to end the wall")
    p.add_argument("--rim-drop-frac", type=float, default=0.15,
                   help="or this fraction of the wall height, whichever is larger")
    p.add_argument("--rim-flat-deg", type=float, default=3.0,
                   help="the wall ends where the ground ahead flattens below this; "
                        "pass a negative value to disable")
    p.add_argument("--rim-flat-run", type=float, default=48.0,
                   help="blocks ahead over which --rim-flat-deg is measured")
    p.add_argument("--rim-flat-min-frac", type=float, default=0.5,
                   help="a flattening only ends the wall once this fraction of the "
                        "side's relief has been climbed, so benches do not")
    p.add_argument("--rim-eps", type=float, default=0.25,
                   help="rises smaller than this do not move the rim outward")
    p.add_argument("--floor-tolerance", type=float, default=2.0, help="blocks above floor")
    p.add_argument("--floor-tolerance-frac", type=float, default=0.1, help="fraction of depth")
    p.add_argument("--flat-floor-frac", type=float, default=0.4,
                   help="floor_width/top_width at or above this is flat_floored")
    p.add_argument("--u-min-b", type=float, default=1.5, help="b at or above this is U")
    p.add_argument("--wall-low", type=float, default=0.2, help="wall band lower fraction of depth")
    p.add_argument("--wall-high", type=float, default=0.8, help="wall band upper fraction")
    p.add_argument("--asym-rim-frac", type=float, default=0.5,
                   help="rim difference over the higher wall's height that marks asymmetry")
    p.add_argument("--asym-angle-diff", type=float, default=10.0, help="degrees")
    p.add_argument("--asym-angle-ratio", type=float, default=2.0)
    p.add_argument("--keep-profiles", action="store_true", help="include raw samples")
    p.add_argument("--id", default=None)
    return p


def params(**overrides):
    """The default analysis thresholds as a namespace, for library use and tests."""
    a = build_parser().parse_args(["--polyline", "0,0;1,0"])
    for k, v in overrides.items():
        setattr(a, k, v)
    return _normalise(a)


def _normalise(a):
    if a.rim_flat_deg is not None and a.rim_flat_deg < 0:
        a.rim_flat_deg = None
    return a


def main(argv=None):
    a = _normalise(build_parser().parse_args(argv))

    axis_meta = None
    if a.landmark:
        try:
            lms = LM.load(a.landmarks)
            lm = LM.get(lms, a.landmark)
            axis_meta = LM.axis(lm, a.axis)
        except LM.LandmarkError as exc:
            raise SystemExit("landmarks: %s" % exc)
        polyline = [tuple(pt) for pt in axis_meta["polyline"]]
        if a.width is None:
            a.width = float(axis_meta.get("section_width") or 0) or None
        name = a.id or "%s.%s" % (a.landmark, axis_meta["id"])
    else:
        polyline = a.polyline
        name = a.id or "section"
    if not a.width:
        raise SystemExit("--width is required when the axis does not define section_width")
    if a.thalweg_window is None:
        a.thalweg_window = a.width / 2.0

    try:
        heights, world = T.load_from_args(a)
    except T.TerrainUnavailable as exc:
        raise SystemExit("terrain unavailable: %s" % exc)

    profiles, total = section(heights, polyline, a)
    summary = summarise(profiles, a.level)
    params = {k: v for k, v in vars(a).items()
              if k not in ("world", "source_root", "heightmap", "out", "polyline")}
    payload = {
        "schema": "cobblers.derived.cross_section/1",
        "id": name,
        "parameters": params,
        "source": T.provenance(world, a.world),
        "landmark": a.landmark,
        "axis": axis_meta["id"] if axis_meta else None,
        "polyline": [[round(x, 1), round(z, 1)] for x, z in polyline],
        "length_blocks": round(total, 1),
        "summary": summary,
        "profiles": profiles,
    }
    out = Path(a.out) if a.out else T.ROOT / "derived" / "sections" / ("%s.json" % name)
    T.write_json(out, payload)
    s = summary
    print("%s: %d stations over %.0f blocks, shapes %s"
          % (name, s["stations"], total,
             ", ".join("%s %d" % (k, v) for k, v in s["shape_counts"].items() if v)))
    print("  floor y %s, depth median %s, floor width median %s, top width median %s, wall median %s deg"
          % (s["floor_y"], s["depth"]["median"], s["floor_width"]["median"],
             s["top_width"]["median"], s["wall_deg"]["median"]))
    print("-> %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
