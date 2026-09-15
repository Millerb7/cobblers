#!/usr/bin/env python
"""Local terrain sculpting: coasts by class, massif asymmetry and summits, volcano cones.

Reads the river-cut heightmap (data/rivers.json cut output) and data/sculpt.json, and writes a derived 16-bit
heightmap that world.json imports. Every brush is local and feathered; columns no brush touches are written
back with their original 16-bit value, and protected sites keep their original terrain.

  plan    classify the coast and report what each brush would change: derived/sculpt/report.json and
          coast_classes.json, previews; no heightmap
  apply   also write <source root>/land_8k_16_sculpted.png and build/sculpt/coast_class.png (paint) with its
          coast_class.json record of the heightmap it belongs to

Coast. Shoreline samples (one per 32 x 32 cell) are classified from aspect (exposure to the prevailing wind
times open-water fetch), coastline shape (land share within 256 blocks), hardness (region and relief) and river
mouths. Each class has a profile along the signed distance to the shoreline d (positive inland): a beach or
estuary lays a berm and a graded strand up to a low top and a gently shelving floor out to sea; a grassy shore
cuts the first rise back to 1:5-1:7; a rocky shore steepens and roughens the bank and deepens the water; a
cliff lifts a face with talus at its foot and deep water. Grades vary along the coast by noise. A zero-mean
micro-relief breaks the uniform block staircase. Class profiles are blended by distance-weighted class shares,
so stretches meet without seams.

Massifs. The upper massif shifts toward its steep face along a tapered weight (features move by up to
shift_blocks; the steep flank compresses and the other stretches), clipped summit plateaus are rebuilt as
ridged domes with one designated highest point, and strata give cliff bands on steep ground and benches on
gentle ground.

Volcano. The cones shift away from the prevailing wind, then each gets its own form: stratovolcano with a
breached crater, lava dome with spines, cinder cone, caldera.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import terrain as T
from coast_measure import open_sea, shoreline_samples, smooth
from foliage import inside_distance, noise as grid_noise


def bilinear(h, xs, zs):
    """Bilinear sample of a rectangular array; coordinates clamp to its own edges per axis."""
    nz, nx = h.shape
    x0 = np.clip(np.floor(xs).astype(np.int64), 0, nx - 2)
    z0 = np.clip(np.floor(zs).astype(np.int64), 0, nz - 2)
    fx = np.clip(xs - x0, 0, 1)
    fz = np.clip(zs - z0, 0, 1)
    return (h[z0, x0] * (1 - fx) * (1 - fz) + h[z0, x0 + 1] * fx * (1 - fz)
            + h[z0 + 1, x0] * (1 - fx) * fz + h[z0 + 1, x0 + 1] * fx * fz)

ROOT = Path(__file__).resolve().parent.parent
CLASSES = ("beach", "estuary", "shore", "rocky", "cliff")
CLASS_CODE = {c: i + 1 for i, c in enumerate(CLASSES)}


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ io

def y_to_raw(y, world):
    imp = world["import"]
    full = float((1 << (world["heightmap"].get("bit_depth") or 16)) - 1)
    frac = imp["low_in"] + (y - imp["low_out"]) / (imp["high_out"] - imp["low_out"]) * (imp["high_in"] - imp["low_in"])
    return np.clip(np.rint(frac * full), 0, full).astype(np.uint16)


def up(grid, factor, shape):
    """Bilinear upsample of a coarse grid whose cell i covers blocks [i*f, (i+1)*f)."""
    n0, n1 = grid.shape
    zs = (np.arange(shape[0]) + 0.5) / factor - 0.5
    xs = (np.arange(shape[1]) + 0.5) / factor - 0.5
    z0 = np.clip(np.floor(zs).astype(int), 0, n0 - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, n1 - 1)
    z1, x1 = np.minimum(z0 + 1, n0 - 1), np.minimum(x0 + 1, n1 - 1)
    fz, fx = np.clip(zs - z0, 0, 1)[:, None], np.clip(xs - x0, 0, 1)[None, :]
    g = grid.astype(np.float32)
    return ((g[z0][:, x0] * (1 - fx) + g[z0][:, x1] * fx) * (1 - fz) + (g[z1][:, x0] * (1 - fx) + g[z1][:, x1] * fx) * fz)


# ------------------------------------------------------------------ protection

def protection(n, towns_doc, foliage_doc, rivers_doc, landmarks_doc, cfg, grid=4, shape="rect"):
    """Blocks outside the nearest protected site, on a grid (0 inside), capped at the terrain feather.

    shape "rect": settlement footprints as drawn plus margin (coasts). "circle": the circle inscribed in each
    footprint plus margin (mountains), so a kept site reads as a knoll or shelf, not a square mesa."""
    m = n // grid
    img = Image.new("L", (m, m), 0)
    d = ImageDraw.Draw(img)
    p = cfg["protect"]
    pad_sites = {pd["site"] for pd in cfg.get("pads") or []}
    for t in towns_doc.get("towns") or []:
        fp = t.get("footprint") or {}
        if not all(fp.get(k) is not None for k in ("min_x", "min_z", "max_x", "max_z")) or t.get("id") in pad_sites:
            continue
        mg = p["landmark_tree_margin_blocks"] if t.get("kind") == "landmark_tree" else p["settlement_margin_blocks"]
        if shape == "circle":
            cx, cz = (fp["min_x"] + fp["max_x"]) / 2, (fp["min_z"] + fp["max_z"]) / 2
            r = min(fp["max_x"] - fp["min_x"], fp["max_z"] - fp["min_z"]) / 2 + mg
            d.ellipse([(cx - r) / grid, (cz - r) / grid, (cx + r) / grid, (cz + r) / grid], fill=255)
        else:
            d.rectangle([(fp["min_x"] - mg) / grid, (fp["min_z"] - mg) / grid, (fp["max_x"] + mg) / grid, (fp["max_z"] + mg) / grid], fill=255)
    for rc in p.get("rectangles") or []:
        d.rectangle([rc["min_x"] / grid, rc["min_z"] / grid, rc["max_x"] / grid, rc["max_z"] / grid], fill=255)
    cut = set((rivers_doc.get("cut") or {}).get("courses_cut") or [])
    for c in rivers_doc.get("courses") or []:
        if c["id"] not in cut or not c.get("graded_polyline"):
            continue
        w = max((c.get("character") or {}).get("width") or [8]) / 2 + p["river_margin_blocks"]
        pts = [(q[0] / grid, q[1] / grid) for q in c["graded_polyline"]]
        d.line(pts, fill=255, width=max(1, int(2 * w / grid)))
        for x, z in pts:
            r = w / grid
            d.ellipse([x - r, z - r, x + r, z + r], fill=255)
    for lm in landmarks_doc.get("landmarks") or []:
        wb = lm.get("water_body")
        if not wb:
            continue
        for ring in wb.get("basin_polygons") or []:
            d.polygon([(x / grid, z / grid) for x, z in ring], fill=255, outline=255)
    base = np.asarray(img) > 0
    # lake_margin_blocks (at least one cell) grows every protected feature, not only lake basins: settlements,
    # glades and rivers get their own margin plus this one. Square footprints are protected by their inscribed
    # circle, whose corners this growth covers (the real footprints changed by at most 0.22 blocks).
    lake_grow = int(p["lake_margin_blocks"] / grid)
    grown = base.copy()
    for _ in range(max(1, lake_grow)):
        g2 = grown.copy()
        g2[1:, :] |= grown[:-1, :]; g2[:-1, :] |= grown[1:, :]; g2[:, 1:] |= grown[:, :-1]; g2[:, :-1] |= grown[:, 1:]
        grown = g2
    cap = max(p["feather_blocks"], p["terrain_feather_blocks"])
    return (inside_distance(~grown, int(cap / grid) + 2) * grid).astype(np.float32)


# ------------------------------------------------------------------ coast classification

def region_index(n, regions_doc, grid=8):
    m = n // grid
    img = Image.new("I", (m, m), 0)
    d = ImageDraw.Draw(img)
    subs = regions_doc["subregions"]
    for i, s in enumerate(subs, start=1):
        for ring in s["polygons"]:
            d.polygon([(x / grid, z / grid) for x, z in ring], fill=i)
    return np.asarray(img), subs


def classify_coast(heights, sea, sea_mask, regions_doc, rivers_doc, cfg):
    c = cfg["coast"]
    n = heights.shape[0]
    pts = shoreline_samples(sea_mask, c["spacing_blocks"])
    sm = smooth(heights, 6)
    gz, gx = np.gradient(sm)
    # land share on a 16-block grid, averaged over the concavity radius
    g16 = 16
    land16 = (~sea_mask)[: n // g16 * g16, : n // g16 * g16].reshape(n // g16, g16, n // g16, g16).mean(axis=(1, 3)).astype(np.float32)
    r = int(c["concavity_radius_blocks"] / g16)
    p = np.pad(land16, r, mode="edge").cumsum(0).cumsum(1)
    k = 2 * r + 1
    share16 = (p[k:, k:] - p[:-k, k:] - p[k:, :-k] + p[:-k, :-k]) / (k * k)
    share16 = np.pad(share16, ((0, land16.shape[0] - share16.shape[0]), (0, land16.shape[1] - share16.shape[1])), mode="edge")
    sea16 = land16 < 0.5
    ridx, subs = region_index(n, regions_doc, 8)
    mouths = [(cc["end_at"]["x"], cc["end_at"]["z"]) for cc in rivers_doc.get("courses") or []
              if cc.get("valid") and cc.get("ends_in") == "open_sea" and cc.get("end_at")
              and cc["id"] in set((rivers_doc.get("cut") or {}).get("courses_cut") or [])]
    wind = math.radians(cfg["prevailing_wind_from_deg"])
    rows = []
    for x, z in pts:
        nx, nz = float(gx[z, x]), float(gz[z, x])
        L = math.hypot(nx, nz)
        if L < 1e-4:
            continue
        nx, nz = nx / L, nz / L                              # inland unit vector
        sx, sz = -nx, -nz                                    # seaward
        faces = (math.degrees(math.atan2(sx, -sz)) + 360) % 360
        # fetch along the seaward normal
        fetch = c["fetch_cap_blocks"]
        for t in range(48, int(c["fetch_cap_blocks"]), 32):
            px, pz = int(x + sx * t), int(z + sz * t)
            if not (0 <= px < n and 0 <= pz < n):
                break
            if not sea16[pz // g16, px // g16]:
                fetch = t
                break
        exposure = max(0.0, math.cos(math.radians(faces) - wind)) * min(1.0, fetch / 2000.0)
        share = float(share16[min(z // g16, share16.shape[0] - 1), min(x // g16, share16.shape[1] - 1)])
        # hinterland relief above the uniform coastal ramp (which reaches about y100 by 150 blocks in everywhere):
        # the 90th percentile of height 200-500 blocks inland, less 100
        cx_, cz_ = int(x + nx * 350), int(z + nz * 350)
        win = heights[max(0, cz_ - 150):max(0, cz_ + 150):8, max(0, cx_ - 150):max(0, cx_ + 150):8]
        relief = max(0.0, float(np.percentile(win, 90)) - 100.0) if win.size else 0.0
        vals = ridx[max(0, z // 8 - 8):z // 8 + 9, max(0, x // 8 - 8):x // 8 + 9]
        vals = vals[vals > 0]
        region = subs[int(np.bincount(vals).argmax()) - 1]["parent"] if len(vals) else None
        hard = region in c["hard_regions"]
        soft = region in c["soft_regions"]
        mouth = min((math.hypot(mx - x, mz - z) for mx, mz in mouths), default=1e9)
        if mouth <= c["estuary_mouth_radius_blocks"]:
            cls = "estuary"
        elif (share < 0.40 and (exposure > 0.5 or relief > 50)) or (hard and relief > 55):
            cls = "cliff"
        elif hard or (not soft and ((exposure > 0.55 and share <= 0.55) or relief > 45)) or (soft and exposure > 0.7):
            cls = "rocky"
        elif share > 0.55 or (soft and (share > 0.48 or exposure < 0.25)) or (exposure < 0.1 and relief < 15 and share > 0.45):
            cls = "beach"
        else:
            cls = "shore"
        rows.append({"x": int(x), "z": int(z), "faces": round(faces), "exposure": round(exposure, 2), "fetch": int(fetch),
                     "land_share": round(share, 2), "relief": round(relief, 1), "region": region,
                     "river_mouth_blocks": round(mouth) if mouth < 1e8 else None, "raw_class": cls})
    # smooth classes along the coast: weighted majority within the radius (estuaries keep priority)
    R = c["class_smoothing_radius_blocks"]
    P = np.array([[r["x"], r["z"]] for r in rows], float)
    for i, r in enumerate(rows):
        if r["raw_class"] == "estuary":
            r["class"] = "estuary"
            continue
        dd = np.hypot(P[:, 0] - r["x"], P[:, 1] - r["z"])
        near = np.nonzero(dd <= R)[0]
        votes = {}
        for j in near:
            cj = rows[j]["raw_class"]
            if cj == "estuary":
                continue
            votes[cj] = votes.get(cj, 0) + (1 - dd[j] / (R + 1))
        r["class"] = max(votes, key=votes.get) if votes else r["raw_class"]
    return rows


def class_weights(rows, n, grid=8, sigma_blocks=110):
    m = n // grid
    W = np.zeros((len(CLASSES), m, m), np.float32)
    for r in rows:
        W[CLASSES.index(r["class"]), min(r["z"] // grid, m - 1), min(r["x"] // grid, m - 1)] += 1
    rr = max(1, int(sigma_blocks / grid / 1.7))
    for i in range(len(CLASSES)):
        a = W[i]
        for _ in range(3):
            a = _box(a, rr)
        W[i] = a
    tot = W.sum(axis=0)
    W /= np.maximum(tot, 1e-9)
    return W, tot


def _box(a, r):
    from coast_measure import box1d
    return box1d(box1d(a, r, 0), r, 1)


# ------------------------------------------------------------------ coast profiles

def profile_beachlike(h0, d, sea, spec, n1, n2, n3, n4):
    g = spec["grade"][0] + (spec["grade"][1] - spec["grade"][0]) * n1
    E = spec["berm_blocks"][0] + (spec["berm_blocks"][1] - spec["berm_blocks"][0]) * n2
    H = spec["top_above_sea"][0] + (spec["top_above_sea"][1] - spec["top_above_sea"][0]) * n4
    B = spec["back_blocks"][0] + (spec["back_blocks"][1] - spec["back_blocks"][0]) * (1 - n4)
    gs = spec["shelf_grade"][0] + (spec["shelf_grade"][1] - spec["shelf_grade"][0]) * n3
    Ds = spec["shelf_depth"][0] + (spec["shelf_depth"][1] - spec["shelf_depth"][0]) * n3
    toe = 0.35
    L = sea + toe + (d + E) / g
    dtop = (H - toe) * g - E
    new = h0.copy()
    core = (d >= -E) & (d <= dtop)
    new = np.where(core, np.where(d < 0, np.maximum(h0, L), L), new)
    back = d > dtop
    t = smoothstep(dtop, dtop + B, d)
    new = np.where(back, np.minimum(h0, L) * (1 - t) + h0 * t, new)          # keep climbing at the strand grade, ease into the old slope
    # underwater shelf: fill only
    dx = -(d + E)
    under = dx > 0
    edge = (Ds + toe) * gs
    U = np.where(dx <= edge, sea + toe - dx / gs, sea - Ds - (dx - edge) / 3.0)
    new = np.where(under, np.maximum(h0, U), new)
    return new


def profile_shore(h0, d, sea, spec, n1, n2, n3, n4):
    g = spec["grade"][0] + (spec["grade"][1] - spec["grade"][0]) * n1
    H = spec["top_above_sea"][0] + (spec["top_above_sea"][1] - spec["top_above_sea"][0]) * n4
    B = spec["back_blocks"][0] + (spec["back_blocks"][1] - spec["back_blocks"][0]) * (1 - n4)
    gs = spec["shelf_grade"][0] + (spec["shelf_grade"][1] - spec["shelf_grade"][0]) * n3
    Ds = spec["shelf_depth"][0] + (spec["shelf_depth"][1] - spec["shelf_depth"][0]) * n3
    L = sea + 0.5 + np.maximum(d, 0) / g
    dtop = (H - 0.5) * g
    new = h0.copy()
    core = (d >= 0) & (d <= dtop)
    new = np.where(core, np.minimum(h0, L), new)
    t = smoothstep(dtop, dtop + B, d)
    back = d > dtop
    new = np.where(back, np.minimum(h0, L) * (1 - t) + h0 * t, new)          # keep climbing at the strand grade, ease into the old slope
    dx = -d
    under = dx > 0
    edge = Ds * gs
    U = np.where(dx <= edge, sea - dx / gs, sea - Ds - (dx - edge) / 3.0)
    new = np.where(under, np.maximum(h0, U), new)
    return new


def profile_rocky(h0, d, sea, spec, rug):
    L = np.minimum(sea + np.maximum(d, 0) / spec["bank_grade"], sea + spec["bank_top_above_sea"])
    t = smoothstep(spec["bank_top_above_sea"] * spec["bank_grade"], spec["bank_top_above_sea"] * spec["bank_grade"] + spec["back_blocks"], d)
    land = d >= 0
    new = np.where(land, np.maximum(h0, L) * (1 - t) + h0 * t, h0)
    under = ~land
    U = np.maximum(sea - (-d) / spec["drop_grade"], sea - spec["drop_depth"])
    new = np.where(under, np.minimum(h0, U), new)
    band = smoothstep(-24, -6, d) * (1 - smoothstep(30, 70, d))
    return new + (rug - 0.5) * 2 * spec["rugged"] * band


def profile_cliff(h0, d, sea, spec, relief, n2, rug, n4):
    # cliffs come and go along the coast: where the gate noise is low the face sinks into a rocky bank
    gate = smoothstep(0.3, 0.6, n4)
    C = np.clip(spec["relief_share"] * relief, spec["height"][0], spec["height"][1]) * (0.85 + 0.3 * n2) * (0.3 + 0.7 * gate)
    f0, f1 = spec["face_blocks"]
    P = sea + C * smoothstep(f0, f1, d)
    w = 1 - smoothstep(spec["back_blocks"][0], spec["back_blocks"][1], d)
    land = d >= 0
    new = np.where(land, np.maximum(h0, P) * w + h0 * (1 - w), h0)
    new = np.where((d < f0) & (d > -spec["talus_blocks"]), np.minimum(new, sea - 1.5 + 3.0 * rug * (1 - np.abs(d + spec["talus_blocks"] / 2) / (spec["talus_blocks"] / 2 + 1))), new)
    under = d <= -spec["talus_blocks"]
    U = np.maximum(sea - 3 - (-d - spec["talus_blocks"]) * spec["drop_grade"], sea - spec["drop_depth"])
    new = np.where(under, np.minimum(h0, U), new)
    return new


# ------------------------------------------------------------------ massifs and volcano

def polygon_mask(n, regions_doc, sub_ids, grid):
    m = n // grid
    img = Image.new("L", (m, m), 0)
    d = ImageDraw.Draw(img)
    for s in regions_doc["subregions"]:
        if s["id"] in sub_ids:
            for ring in s["polygons"]:
                d.polygon([(x / grid, z / grid) for x, z in ring], fill=1)
    return np.asarray(img) > 0


def shift_toward(h, weight, bearing_deg, blocks):
    """new(p) = h(p - u * blocks * weight(p)), u pointing toward bearing (0 = north = -z)."""
    b = math.radians(bearing_deg)
    ux, uz = math.sin(b), -math.cos(b)
    zz, xx = np.mgrid[0:h.shape[0], 0:h.shape[1]].astype(np.float32)
    return bilinear(h, xx - ux * blocks * weight, zz - uz * blocks * weight)


def sculpt_massif(h, spec, box, regions_doc, n, seed):
    x0, z0, x1, z1 = box
    crop = h[z0:z1, x0:x1].astype(np.float32)
    g = 4
    mask = polygon_mask(n, regions_doc, spec["subregions"], g)[z0 // g:z1 // g, x0 // g:x1 // g]
    din = inside_distance(mask, int(spec["shift_taper_blocks"] / g) + 2) * g
    wgrid = smoothstep(0, spec["shift_taper_blocks"], din)
    # the weight follows smoothed height: a per-column height would shift neighbours by different amounts
    w = up(wgrid, g, crop.shape) * smoothstep(spec["shift_from_y"], spec["shift_from_y"] + 40, smooth(crop, 12))
    region_w = up(smoothstep(0, 80, din), g, crop.shape)          # summits and strata stay inside the massif
    new = shift_toward(crop, w.astype(np.float32), spec["steep_faces_deg"], spec["shift_blocks"])
    # clipped summit plateaus: a smooth ridged lowering inside them, deepest where the ridge noise is low (saddles),
    # nothing at the designated highest point, fading out across the plateau edge
    s = spec["summits"]
    plateau = (new >= 199.0).astype(np.float32)
    pm = smooth(plateau, 24)                                        # smooth plateau indicator, about 0.5 at the edge
    rn = up(_ridged_rect(mask.shape, s["ridge_scale_blocks"], seed + 11), g, crop.shape)
    M = np.clip(rn ** 1.3 * s["secondary_cap"], 0, s["secondary_cap"])
    hx, hz = s["highest"]
    zz, xx = np.mgrid[z0:z1, x0:x1]
    M = np.maximum(M, np.exp(-((xx - hx) ** 2 + (zz - hz) ** 2) / (2 * 70.0 ** 2)))
    lowering = s["rise"] * (1 - M) * smoothstep(0.15, 0.85, pm) * region_w
    new = new - lowering
    # the designated highest point: a summit rising to y200, raising only ground already high on the massif
    pr = s.get("peak_radius", 120)
    dist = np.hypot(xx - hx, zz - hz)
    peak = 200.0 - 26.0 * (dist / pr) ** 1.6
    new = np.where((dist < pr) & (new > 175), np.maximum(new, peak), new)
    # subsidiary summits stand clearly below it: height above y180 is compressed away from the highest point
    comp = smoothstep(150, 300, dist) * region_w * s.get("subsidiary_compression", 0.4)
    new = np.where(new > 180, new - (new - 180) * comp, new)
    # strata: cliff bands on steep ground, benches on gentle ground, applied to smoothed height as an offset
    st = spec["strata"]
    base_sm = smooth(new, 6)
    gz, gx = np.gradient(base_sm)
    slope = np.degrees(np.arctan(np.hypot(gx, gz)))
    wn = up(_rect_noise(mask.shape, 90, seed + 21), g, crop.shape)
    bn = up(_rect_noise(mask.shape, 300, seed + 22), g, crop.shape)
    # strata run from from_y up to just below the summits, which keep their designed heights
    above = smoothstep(st["from_y"], st["from_y"] + 15, new) * (1 - smoothstep(180, 190, base_sm)) * region_w

    def terrace(hh, band):
        # the contour is warped by up to 14 blocks so bands wander and break rather than ring the summit;
        # risers take the upper half of each band, so a bench is a shelf, not a step
        q = (hh + (wn - 0.5) * 28) / band
        f = q - np.floor(q)
        return (np.floor(q) + smoothstep(0.45, 1.0, f)) * band - (wn - 0.5) * 28

    cb = st["cliff_band"][0] + (st["cliff_band"][1] - st["cliff_band"][0]) * bn
    bb = st["bench_band"][0] + (st["bench_band"][1] - st["bench_band"][0]) * bn
    # patches: strata show in about half the steep ground and a third of the gentle ground, never as full rings
    pn = up(_rect_noise(mask.shape, 220, seed + 23), g, crop.shape)
    pn2 = up(_rect_noise(mask.shape, 260, seed + 24), g, crop.shape)
    cliff_w = (smoothstep(st["cliff_slope_deg"] - 4, st["cliff_slope_deg"] + 4, slope) * st["cliff_strength"] * above
               * smoothstep(0.4, 0.6, pn))
    bench_w = (smoothstep(st["bench_slope_deg"][0] - 3, st["bench_slope_deg"][0] + 3, slope)
               * (1 - smoothstep(st["bench_slope_deg"][1] - 3, st["bench_slope_deg"][1] + 3, slope)) * st["bench_strength"] * above
               * smoothstep(0.55, 0.75, pn2))
    new = new + (terrace(base_sm, cb) - base_sm) * cliff_w + (terrace(base_sm, bb) - base_sm) * bench_w
    out = h.copy()
    out[z0:z1, x0:x1] = new
    return out


def _rect_noise(shape, scale_blocks, seed):
    m = max(shape)
    return grid_noise(m, scale_blocks, seed)[: shape[0], : shape[1]]


def _ridged_rect(shape, scale_blocks, seed):
    return 1 - np.abs(2 * _rect_noise(shape, scale_blocks, seed) - 1)


def sculpt_volcano(h, vcfg, box, n, seed):
    x0, z0, x1, z1 = box
    crop = h[z0:z1, x0:x1].astype(np.float32)
    zz, xx = np.mgrid[z0:z1, x0:x1].astype(np.float32)
    # shift each cone's upper part away from the wind (toward the steep face)
    w = np.zeros_like(crop)
    for c in vcfg["cones"]:
        cx, cz = c["centre"]
        r = np.hypot(xx - cx, zz - cz)
        w = np.maximum(w, 1 - smoothstep(60, vcfg["shift_taper_blocks"] + 60, r))
    w *= smoothstep(vcfg["shift_from_y"], vcfg["shift_from_y"] + 30, crop)
    new = shift_toward(crop, w, vcfg["steep_faces_deg"], vcfg["shift_blocks"])
    b = math.radians(vcfg["steep_faces_deg"])
    sx, sz = math.sin(b) * vcfg["shift_blocks"], -math.cos(b) * vcfg["shift_blocks"]
    rng = np.random.default_rng(seed)

    reach = {"stratovolcano": "flank_to_radius", "lava_dome": "dome_radius", "cinder_cone": "radius", "caldera": "flank_to_radius"}
    extra = {"stratovolcano": 70, "lava_dome": 45, "cinder_cone": 120, "caldera": 40}
    for c in vcfg["cones"]:
        cx, cz = c["centre"][0], c["centre"][1]
        if c["form"] != "caldera":
            cx, cz = cx + sx, cz + sz          # the cone's top moved with the shift
        r = np.hypot(xx - cx, zz - cz)
        ang = np.degrees(np.arctan2(xx - cx, -(zz - cz))) % 360
        before_cone = new
        r_out = c[reach[c["form"]]] + extra[c["form"]]
        if c["form"] == "stratovolcano":
            R, rim, F = c["crater_radius"], c["rim_y"], c["flank_to_radius"]
            flank = rim - c["flank_drop"] * np.clip((r - R - c["rim_width"]) / (F - R - c["rim_width"]), 0, 1) ** 1.3
            t = np.where(r <= R, c["crater_floor_y"] + (rim - c["crater_floor_y"]) * (r / R) ** 3, flank)
            new = np.minimum(new, t)
            da = np.abs((ang - c["breach_bearing_deg"] + 180) % 360 - 180)
            wb = 1 - smoothstep(c["breach_half_angle_deg"] * 0.4, c["breach_half_angle_deg"], da)
            wb = wb * smoothstep(R * 0.5, R, r) * (1 - smoothstep(F * 0.75, F, r))
            breach = c["breach_floor_y"] - c["breach_grade"] * np.maximum(r - R, 0)
            new = new - np.maximum(new - breach, 0) * wb
        elif c["form"] == "lava_dome":
            R = c["dome_radius"]
            t = np.where(r <= R, c["dome_top_y"] - c["dome_drop"] * (r / R) ** 2, c["dome_top_y"] - c["dome_drop"] - 0.3 * (r - R))
            new = np.minimum(new, t)
            crng = np.random.default_rng(c.get("spine_seed", 7))
            for _ in range(c["spines"]):
                a = crng.uniform(0, 2 * math.pi)
                rr = crng.uniform(8, c["dome_radius"] * 0.45)
                px, pz = cx + math.cos(a) * rr, cz + math.sin(a) * rr
                dd = np.hypot(xx - px, zz - pz)
                spine = 200.0 - dd * (6.0 / c["spine_radius"])
                new = np.where(dd <= c["spine_radius"] * 1.5, np.maximum(new, spine), new)
        elif c["form"] == "cinder_cone":
            t = c["top_y"] - c["slope"] * r
            t = np.where(r <= c["crater_radius"], c["crater_floor_y"] + (c["top_y"] - c["crater_floor_y"]) * (r / c["crater_radius"]) ** 2, t)
            wcc = c["strength"] * (1 - smoothstep(c["radius"] * 0.8, c["radius"], r))
            wcc = np.where(r <= c["crater_radius"], 1.0, wcc)
            # anything standing above the cone surface (the old clipped spur) is cut down to it, never below the plain
            capped = np.minimum(new, np.maximum(t, c["plain_y"]))
            new = np.where(r <= c["crater_radius"], np.minimum(capped, t), capped * (1 - wcc) + np.maximum(t, capped) * wcc)
        elif c["form"] == "caldera":
            ph = rng.uniform(0, 2 * math.pi, 3)
            a_ = np.radians(ang)
            rim_n = (np.sin(2 * a_ + ph[0]) + 0.6 * np.sin(3 * a_ + ph[1]) + 0.35 * np.sin(5 * a_ + ph[2])) / 1.95
            rim_y = c["rim_y"] + c["rim_noise"] * rim_n
            floor = c["floor_y"]
            wall = floor + (rim_y - floor) * smoothstep(c["floor_radius"], c["wall_to_radius"], r) ** 0.8
            rim = rim_y
            flank = rim_y - c["flank_grade"] * (r - c["rim_to_radius"])
            t = np.where(r <= c["floor_radius"], floor, np.where(r <= c["wall_to_radius"], wall, np.where(r <= c["rim_to_radius"], rim, flank)))
            inner = r <= c["wall_to_radius"]
            ring = (r > c["wall_to_radius"]) & (r <= c["flank_to_radius"])
            fade = 1 - smoothstep(c["flank_to_radius"] - 50, c["flank_to_radius"], r)
            new = np.where(inner, t, np.where(ring, np.maximum(new, t) * fade + new * (1 - fade), new))
        # every form stays inside its own reach
        wr = 1 - smoothstep(r_out * 0.8, r_out, r)
        new = before_cone * (1 - wr) + new * wr
    out = h.copy()
    out[z0:z1, x0:x1] = np.clip(new, 10, 200)
    return out


# ------------------------------------------------------------------ hillside relief

def unit_noise(n, spacing, seed):
    """Zero-mean, unit-variance smooth noise on n x n blocks: a random grid every `spacing` blocks, bicubic."""
    rng = np.random.default_rng(seed)
    k = n // spacing + 4
    g = rng.standard_normal((k, k)).astype(np.float32)
    img = Image.fromarray(g, mode="F").resize((k * spacing, k * spacing), Image.BICUBIC)
    off = int(rng.integers(0, spacing))
    a = np.asarray(img)[off:off + n, off:off + n].astype(np.float32)
    return (a - a.mean()) / max(float(a.std()), 1e-6)


def sculpt_relief(h, rcfg, sea, seed, report=None, keep=None):
    """Break the regular contour rings of smooth hillsides without smoothing them.

    A slope of grade g quantises to a 1-block step every 1/g blocks; over a smooth ramp those steps run as parallel
    rings. Relief of amplitude A across the slope at wavelength L moves each contour by A/g and tilts the local
    grade by about 2*pi*A/L, so the ratio rho = (2*pi*A/L)/g sets whether contours wander (rho ~0.3) or break into
    spurs and gullies (rho near 1). Amplitude is proportional to the regional grade (A = k*g, capped), so flats
    stay flat and every grade gets the same rho. The noise is averaged along the fall line, so features run
    downhill like spurs and gullies rather than as knobs.
    """
    n = h.shape[0]
    sm = smooth(h, rcfg["regional_sigma_blocks"])
    gz, gx = np.gradient(sm)
    del sm
    g = np.hypot(gx, gz).astype(np.float32)
    ux = (gx / np.maximum(g, 1e-6)).astype(np.float32)
    uz = (gz / np.maximum(g, 1e-6)).astype(np.float32)
    del gx, gz
    base = np.zeros((n, n), np.float32)
    for i, o in enumerate(rcfg["octaves"]):
        base += o["weight"] * unit_noise(n, o["spacing_blocks"], seed + i)
    # average along the fall line (line integral convolution), in tiles
    L, taps = rcfg["fall_line_stretch_blocks"], rcfg["fall_line_taps"]
    ts = np.linspace(-L, L, taps).astype(np.float32)
    ani = np.zeros_like(base)
    T_, P = 1024, int(L) + 2
    for tz in range(0, n, T_):
        for tx in range(0, n, T_):
            z0, z1, x0, x1 = tz, min(n, tz + T_), tx, min(n, tx + T_)
            pz0, px0 = max(0, z0 - P), max(0, x0 - P)
            crop = base[pz0:min(n, z1 + P), px0:min(n, x1 + P)]
            zz, xx = np.mgrid[z0:z1, x0:x1].astype(np.float32)
            u, w = ux[z0:z1, x0:x1], uz[z0:z1, x0:x1]
            acc = np.zeros(zz.shape, np.float32)
            for t in ts:
                acc += bilinear(crop, xx + t * u - px0, zz + t * w - pz0)
            ani[z0:z1, x0:x1] = acc / taps
    # normalise by the same average taken along one fixed direction over a fixed window: a statistic of the noise
    # alone, so a terrain edit in one place changes the relief only where the fall line moved
    w0 = min(n, 1024)
    zz, xx = np.mgrid[0:w0, 0:w0].astype(np.float32)
    ref = sum(bilinear(base[:w0 + P, :w0 + P], xx + t + P, zz) for t in ts) / taps if n > w0 + P else ani
    del base
    ani = ani / max(float(ref.std()), 1e-6)
    c = rcfg["noise_soft_clip_sigma"]
    ani = c * np.tanh(ani / c)                      # no tails: the largest change stays near c * max amplitude
    lo, hi = rcfg["low_fade_above_sea"]
    s0, s1 = rcfg["steep_fade_grade"]
    fade = smoothstep(sea + lo, sea + hi, h) * (1 - smoothstep(s0, s1, g))
    amp = np.minimum(rcfg["amplitude_per_grade"] * g, rcfg["max_amplitude_blocks"]) * fade
    if keep is not None:
        amp = amp * keep                            # 0 inside protected footprints, basins, channels
    delta = amp * ani
    if report is not None:
        report.update({"columns_changed_half_block": int((np.abs(delta) >= 0.5).sum()),
                       "max_raise": round(float(delta.max()), 2), "max_lower": round(float(delta.min()), 2),
                       "p99_abs": round(float(np.percentile(np.abs(delta[::4, ::4]), 99)), 2)})
    return np.clip(h + delta, 10, 200).astype(np.float32)


# ------------------------------------------------------------------ main pipeline

def run(heights, world, cfg, regions, rivers, towns, foliage_doc, landmarks, seed=20260915, preview_dir=None):
    n = heights.shape[0]
    sea = T.sea_level(world)
    h0 = heights.astype(np.float32)
    new = h0.copy()
    report = {"coast": {}, "massifs": {}, "volcano": {}}

    # coast
    sea_mask = open_sea(h0, sea)
    rows = classify_coast(h0, sea, sea_mask, regions, rivers, cfg)
    W, tot = class_weights(rows, n)
    g2 = 2
    s2 = sea_mask[::g2, ::g2]
    cap = int(cfg["coast"]["band_blocks"] / g2) + 4
    dl = inside_distance(~s2, cap)
    ds = inside_distance(s2, cap)
    d2 = (dl - ds).astype(np.float32) * g2
    d2 = smooth(d2, 2)
    n16 = grid_noise(n // 8, 400, seed + 1)
    n16b = grid_noise(n // 8, 400, seed + 2)
    n16c = grid_noise(n // 8, 400, seed + 3)
    n16d = grid_noise(n // 8, 300, seed + 6)
    micro = grid_noise(n // 4, cfg["coast"]["micro_relief_scale_blocks"], seed + 4)
    rug = grid_noise(n // 4, 16, seed + 5)
    relief8 = np.zeros((n // 8, n // 8), np.float32)
    for r in rows:
        relief8[min(r["z"] // 8, relief8.shape[0] - 1), min(r["x"] // 8, relief8.shape[1] - 1)] = max(r["relief"], 1)
    rel_s = _box(_box(_box(relief8, 6), 6), 6) / np.maximum(_box(_box(_box((relief8 > 0).astype(np.float32), 6), 6), 6), 1e-6)
    class_map = np.zeros((n, n), np.uint8)
    T_ = 1024
    band = cfg["coast"]["band_blocks"]
    spec = cfg["coast"]["classes"]
    changed_coast = 0
    for tz in range(0, n, T_):
        for tx in range(0, n, T_):
            zs, xs = slice(tz, min(n, tz + T_)), slice(tx, min(n, tx + T_))
            shape = (zs.stop - zs.start, xs.stop - xs.start)

            def upc(grid, f):
                z0c, x0c = tz // f, tx // f
                sub = grid[max(0, z0c - 1):z0c + shape[0] // f + 2, max(0, x0c - 1):x0c + shape[1] // f + 2]
                off_z, off_x = (z0c - max(0, z0c - 1)) * f, (x0c - max(0, x0c - 1)) * f
                u = up(sub, f, (sub.shape[0] * f, sub.shape[1] * f))
                return u[off_z:off_z + shape[0], off_x:off_x + shape[1]]

            d = upc(d2, g2)
            if np.abs(d).min() > band:
                continue
            hh = h0[zs, xs]
            wts = [upc(W[i], 8) for i in range(len(CLASSES))]
            coverage = upc(np.minimum(tot, 1.0), 8)
            n1, n2, n3, n4 = upc(n16, 8), upc(n16b, 8), upc(n16c, 8), upc(n16d, 8)
            mic, rg = upc(micro, 4), upc(rug, 4)
            rel = upc(rel_s, 8)
            outs = {
                "beach": profile_beachlike(hh, d, sea, spec["beach"], n1, n2, n3, n4),
                "estuary": profile_beachlike(hh, d, sea, spec["estuary"], n1, n2, n3, n4),
                "shore": profile_shore(hh, d, sea, spec["shore"], n1, n2, n3, n4),
                "rocky": profile_rocky(hh, d, sea, spec["rocky"], rg),
                "cliff": profile_cliff(hh, d, sea, spec["cliff"], rel, n2, rg, n4),
            }
            wsum = np.maximum(sum(wts), 1e-6)
            blended = sum(outs[c] * wts[i] for i, c in enumerate(CLASSES)) / wsum
            amp = sum(spec[c]["micro_relief"] * wts[i] for i, c in enumerate(CLASSES)) / wsum
            land_band = smoothstep(3, 12, d) * (1 - smoothstep(150, 200, d))
            blended = blended + (mic - 0.5) * 2 * amp * land_band
            wband = (1 - smoothstep(band - 50, band, np.abs(d))) * smoothstep(0.0005, 0.005, coverage)
            res = hh * (1 - wband) + blended * wband
            new[zs, xs] = res
            cls = np.argmax(np.stack(wts), axis=0).astype(np.uint8) + 1
            class_map[zs, xs] = np.where((wband > 0.5) & (np.abs(d) < 120), cls, 0)
            changed_coast += int((np.abs(res - hh) >= 0.5).sum())
    report["coast"]["samples"] = len(rows)
    report["coast"]["classes"] = {c: sum(1 for r in rows if r["class"] == c) for c in CLASSES}
    report["coast"]["columns_changed_half_block"] = changed_coast

    # massifs
    for m in cfg["massifs"]:
        mask = polygon_mask(n, regions, m["subregions"], 4)
        zs_, xs_ = np.nonzero(mask)
        pad = m["shift_taper_blocks"] + 200
        box = (max(0, xs_.min() * 4 - pad), max(0, zs_.min() * 4 - pad), min(n, xs_.max() * 4 + pad), min(n, zs_.max() * 4 + pad))
        box = tuple(int(v - v % 4) for v in box)
        prev = new[box[1]:box[3], box[0]:box[2]].copy()
        new = sculpt_massif(new, m, box, regions, n, seed + 100)
        diff = new[box[1]:box[3], box[0]:box[2]] - prev
        report["massifs"][m["id"]] = {"box": box, "columns_changed_half_block": int((np.abs(diff) >= 0.5).sum()),
                                      "max_raise": round(float(diff.max()), 1), "max_lower": round(float(diff.min()), 1)}
    # volcano
    v = cfg["volcano"]
    cs = np.array([c["centre"] for c in v["cones"]])
    pad = v["shift_taper_blocks"] + 320
    box = (int(max(0, cs[:, 0].min() - pad)), int(max(0, cs[:, 1].min() - pad)), int(min(n, cs[:, 0].max() + pad)), int(min(n, cs[:, 1].max() + pad)))
    prev = new[box[1]:box[3], box[0]:box[2]].copy()
    new = sculpt_volcano(new, v, box, n, seed + 200)
    diff = new[box[1]:box[3], box[0]:box[2]] - prev
    report["volcano"] = {"box": box, "columns_changed_half_block": int((np.abs(diff) >= 0.5).sum()),
                         "max_raise": round(float(diff.max()), 1), "max_lower": round(float(diff.min()), 1)}

    # hillside relief: after every shaping brush, before pads and protection
    if cfg.get("relief"):
        report["relief"] = {}
        # relief is a few blocks at most, so protected sites are kept as drawn rectangles (no mesa to fear) and the
        # footprints, basins and channels stay bit-identical
        pr = protection(n, towns, foliage_doc, rivers, landmarks, cfg, 4, "rect")
        keep = up(smoothstep(0, cfg["relief"]["protect_feather_blocks"], pr), 4, (n, n))
        keep[up((pr <= 0).astype(np.float32), 4, (n, n)) > 0] = 0
        new = sculpt_relief(new, cfg["relief"], sea, seed + 300, report["relief"], keep)
        del keep, pr

    # pads: deliberately flat sites are pressed to their level with a soft edge, after the terrain brushes
    by_id = {tw["id"]: tw for tw in towns.get("towns") or []}
    report["pads"] = {}
    for pd in cfg.get("pads") or []:
        tw = by_id[pd["site"]]
        cx, cz = tw["centre"]["x"], tw["centre"]["z"]
        R, F = pd["radius"], pd["feather"]
        x0, x1, z0, z1 = max(0, cx - R - F), min(n, cx + R + F + 1), max(0, cz - R - F), min(n, cz + R + F + 1)
        zz, xx = np.mgrid[z0:z1, x0:x1]
        wpad = 1 - smoothstep(R, R + F, np.hypot(xx - cx, zz - cz))
        before = new[z0:z1, x0:x1].copy()
        new[z0:z1, x0:x1] = before * (1 - wpad) + pd["y"] * wpad
        report["pads"][pd["site"]] = {"flat_columns": int((wpad > 0.999).sum()), "max_change": round(float(np.abs(new[z0:z1, x0:x1] - before).max()), 1)}
    # protection last: protected sites keep the original terrain. Coastal brushes feather out over feather_blocks;
    # massif and volcano brushes, which move terrain by tens of blocks, over terrain_feather_blocks.
    # circles, not rectangles: a rectangle's feather leaves a square mesa on a sloping coast
    prot_circ = protection(n, towns, foliage_doc, rivers, landmarks, cfg, 4, "circle")
    terrain_zone = np.zeros((n // 4, n // 4), bool)
    for bx in [r["box"] for r in report["massifs"].values()] + [report["volcano"]["box"]]:
        terrain_zone[bx[1] // 4:bx[3] // 4, bx[0] // 4:bx[2] // 4] = True
    fc, ft = cfg["protect"]["feather_blocks"], cfg["protect"]["terrain_feather_blocks"]
    prot = prot_circ
    feather = np.where(terrain_zone, ft, fc).astype(np.float32)
    pgrid = smoothstep(0, 1, np.clip(1 - prot / feather, 0, 1))
    pgrid = _box(_box(pgrid, 2), 2)                     # the grid distance is stepped; smooth it before upsampling
    protected = 0
    for tz in range(0, n, 1024):
        z0c = tz // 4
        sub = pgrid[max(0, z0c - 1):z0c + 258]
        u = up(sub, 4, (sub.shape[0] * 4, n))
        off = (z0c - max(0, z0c - 1)) * 4
        rows_ = slice(tz, min(n, tz + 1024))
        pw = u[off:off + (rows_.stop - rows_.start), :n]
        new[rows_] = new[rows_] * (1 - pw) + h0[rows_] * pw
        protected += int((pw > 0.99).sum())
    new = np.clip(new, float(world["import"]["low_out"]), float(world["import"]["high_out"]))
    report["protected_columns"] = protected
    return new, rows, class_map, report


def hillshade(h, x0, z0, x1, z1, step=1):
    a = h[z0:z1:step, x0:x1:step].astype(np.float32)
    gz, gx = np.gradient(a, step)
    az, alt = math.radians(315), math.radians(40)
    slope = np.arctan(np.hypot(gx, gz) * 1.5)
    aspect = np.arctan2(-gx, gz)
    sh = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    img = np.clip(sh * 255, 0, 255).astype(np.uint8)
    water = a < 62
    rgb = np.stack([img, img, img], -1)
    rgb[water] = (rgb[water] * np.array([0.45, 0.6, 0.95])).astype(np.uint8)
    return rgb


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "apply"):
        s = sub.add_parser(name)
        T.add_common_args(s)
        s.add_argument("--config", default=str(ROOT / "data" / "sculpt.json"))
        s.add_argument("--from-heightmap", default=None, help="input heightmap (default: data/rivers.json cut output)")
        s.add_argument("--out-name", default="land_8k_16_sculpted.png")
        s.add_argument("--out-dir", default=None)
        s.add_argument("--previews", nargs="*", default=[], help="x0,z0,x1,z1 boxes to render before/after hillshades")
    a = p.parse_args(argv)
    world_path = Path(a.world)
    world = T.load_world(world_path)
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    regions = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    rivers = json.loads((ROOT / "data" / "rivers.json").read_text(encoding="utf-8"))
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))
    foliage_doc = json.loads((ROOT / "data" / "foliage.json").read_text(encoding="utf-8"))
    landmarks = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
    import os
    cut_out = rivers["cut"]["output"]
    root = Path(a.source_root or os.environ.get("COBBLERS_SOURCE_ROOT") or ".")
    src_path = Path(a.from_heightmap) if a.from_heightmap else root / cut_out["path"]
    raw = np.array(Image.open(src_path))
    sha = hashlib.sha256(src_path.read_bytes()).hexdigest()
    if sha != cut_out["sha256"]:
        raise SystemExit("input %s sha256 %s is not the river cut recorded in rivers.json (%s)" % (src_path, sha[:12], cut_out["sha256"][:12]))
    heights = T.sample_to_height(raw, world).astype(np.float32)
    new, rows, class_map, report = run(heights, world, cfg, regions, rivers, towns, foliage_doc, landmarks)
    new_raw = y_to_raw(new, world)
    # bit-identical where nothing changed by at least one raw step's worth
    delta = new - heights
    touched = np.abs(delta) > 1e-3
    out_raw = np.where(touched, new_raw, raw).astype(np.uint16)
    report["columns_touched"] = int(touched.sum())
    report["columns_changed_half_block"] = int((np.abs(delta) >= 0.5).sum())
    report["raised_volume_blocks"] = int(np.clip(delta, 0, None).sum())
    report["lowered_volume_blocks"] = int(np.clip(-delta, 0, None).sum())
    report["clipped_columns_before"] = int((heights >= 199.9).sum())
    report["clipped_columns_after"] = int((new >= 199.9).sum())
    report["coast_class_share"] = {c: round(sum(1 for r in rows if r["class"] == c) / max(len(rows), 1), 3) for c in CLASSES}
    out_dir = Path(a.out_dir) if a.out_dir else src_path.parent
    build = ROOT / "build" / "sculpt"
    build.mkdir(parents=True, exist_ok=True)
    for spec in a.previews:
        x0, z0, x1, z1 = [int(v) for v in spec.split(",")]
        step = max(1, (x1 - x0) // 1400)
        before = hillshade(heights, x0, z0, x1, z1, step)
        after = hillshade(new, x0, z0, x1, z1, step)
        Image.fromarray(np.concatenate([before, after], axis=1)).save(build / ("preview_%d_%d_%d_%d.png" % (x0, z0, x1, z1)))
    derived = ROOT / "derived" / "sculpt"
    derived.mkdir(parents=True, exist_ok=True)
    (derived / "coast_classes.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    if a.cmd == "apply":
        out = out_dir / a.out_name
        Image.fromarray(out_raw).save(out)
        report["output"] = {"path": a.out_name, "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
        Image.fromarray(class_map).save(build / "coast_class.png")
        (build / "coast_class.json").write_text(json.dumps({"heightmap_sha256": report["output"]["sha256"]}), encoding="utf-8")
        report["class_codes"] = CLASS_CODE
    report["input"] = {"path": cut_out["path"], "sha256": sha}
    (derived / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
