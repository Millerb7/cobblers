#!/usr/bin/env python
"""Forest placement: density fields and exact object positions from data/foliage.json.

Called by tools/paint_maps.py. Works on a 4-block grid for fields and on blocks for positions.

For each forest type, over the sub-regions assigned to it:
  edge      distance to the type's own boundary (octagonal distance on the grid), plus ragged noise, ramped to
            full density at edge_width; the ragged value also moves the boundary itself
  glades    low-frequency noise removes glade_share of the area, soft-edged
  clumping  medium-frequency noise gathers stems into groves
  slope     thins from slope_lo to slope_hi degrees
  treeline  thins over the 24 blocks below the sub-region's treeline_y
  water     none within water_clearance blocks; water_boost types gain density near water
  density   D = scale * edge * glades * clumping * slope * treeline * water, stems per block = stems_per_ha * D / 1e4

Positions: a Bernoulli draw per grid cell at that expected count, jittered inside the cell, then a class drawn by
its core/edge (or low/high elevation) weights. Candidates are accepted biggest spacing first; every stem keeps
(spacing_a + spacing_b) / 2 from every other stem, across types. Lone trees are drawn in open ground beyond a
forest's edge; debris (boulders, logs, snags, litter) is drawn separately and only keeps clear of trunks.

The object that WorldPainter places at a position is a random variant of the position's group, so the canopy
grid uses each group's mean height and crown radius.

Overlays (data/foliage.json "overlays"): extra stems and debris laid over named sub-regions after every forest type
and its debris are placed, each from its own random stream (seed and the overlay id). They only fill gaps: they keep
the same pairwise spacing from every stem already standing and clear of debris, landmark glades, settlements, water
and, when overlays.path_clearance_blocks is set, of the route polylines. Because they run last and draw from their
own streams, the forest types place exactly what they placed without them, so an overlay's effect is local to its
sub-regions. An overlay's density is its edge ramp times optional patch noise (the top `share` of the noise inside
it), a near-water term and slope, scaled per sub-region. Overlays never paint a biome: spawn pools key on it.
"""
from __future__ import annotations

import math
import zlib

import numpy as np
from PIL import Image

G = 4                      # grid blocks


def noise(n, scale_blocks, seed, octaves=2):
    """Smooth noise in [0, 1] on an n x n grid of G-block cells."""
    rng = np.random.default_rng(seed)
    out = np.zeros((n, n), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        s = max(2, int(scale_blocks / G / (2 ** o)))
        k = n // s + 2
        g = rng.random((k, k)).astype(np.float32)
        img = Image.fromarray(g, mode="F").resize((k * s, k * s), Image.BICUBIC)
        out += amp * np.asarray(img)[:n, :n]
        total += amp
        amp *= 0.5
    out /= total
    lo, hi = np.percentile(out[::4, ::4], [1, 99])
    return np.clip((out - lo) / max(hi - lo, 1e-6), 0, 1).astype(np.float32)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / np.maximum(np.asarray(e1, np.float32) - e0, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def inside_distance(mask, max_cells):
    """Cells from each True cell to the nearest False cell (octagonal metric), capped."""
    d = np.zeros(mask.shape, np.float32)
    cur = mask.copy()
    for k in range(max_cells):
        if not cur.any():
            break
        e = cur.copy()
        e[1:, :] &= cur[:-1, :]
        e[:-1, :] &= cur[1:, :]
        e[:, 1:] &= cur[:, :-1]
        e[:, :-1] &= cur[:, 1:]
        if k % 2 == 1:
            e[1:, 1:] &= cur[:-1, :-1]
            e[:-1, :-1] &= cur[1:, 1:]
            e[1:, :-1] &= cur[:-1, 1:]
            e[:-1, 1:] &= cur[1:, :-1]
        d += cur
        cur = e
    return d


def local_mean(a, radius_cells):
    """Box mean with an integral image."""
    p = np.pad(a.astype(np.float64), radius_cells + 1, mode="edge")
    c = p.cumsum(0).cumsum(1)
    r = radius_cells
    zi0 = np.arange(a.shape[0]) + 1
    xi0 = np.arange(a.shape[1]) + 1
    zi1, xi1 = zi0 + 2 * r, xi0 + 2 * r
    s = c[zi1[:, None], xi1[None, :]] - c[zi0[:, None] - 1, xi1[None, :]] - c[zi1[:, None], xi0[None, :] - 1] + c[zi0[:, None] - 1, xi0[None, :] - 1]
    return (s / ((2 * r + 1) ** 2)).astype(np.float32)


class Spacing:
    """Grid hash of accepted stems: (x, z, spacing)."""

    def __init__(self, cell=8):
        self.cell = cell
        self.cells = {}

    def ok(self, x, z, sp, reach):
        c = self.cell
        cx, cz = int(x) // c, int(z) // c
        r = int(math.ceil(reach / c))
        for ix in range(cx - r, cx + r + 1):
            for iz in range(cz - r, cz + r + 1):
                for (px, pz, psp) in self.cells.get((ix, iz), ()):
                    need = (sp + psp) / 2
                    if (px - x) ** 2 + (pz - z) ** 2 < need * need:
                        return False
        return True

    def add(self, x, z, sp):
        self.cells.setdefault((int(x) // self.cell, int(z) // self.cell), []).append((x, z, sp))


def group_stats(library):
    out = {}
    for r in library["objects"]:
        g = out.setdefault(r["group"], {"heights": [], "crowns": [], "eye": [], "ground_radius": 0})
        g["heights"].append(r["height"])
        g["crowns"].append(r["crown_radius"])
        g["eye"].append(r.get("eye_width", 1))
        g["ground_radius"] = max(g["ground_radius"], r.get("ground_radius", 0))
    return {k: {"height": float(np.mean(v["heights"])), "crown": float(np.mean(v["crowns"])),
                "eye_width": float(np.mean(v["eye"])), "ground_radius": v["ground_radius"]} for k, v in out.items()}


def type_masks(doc, subs, presets, idx4):
    """type id -> (bool grid of its sub-regions, density scale grid, treeline grid)."""
    n = idx4.shape[0]
    by_type = {}
    for i, s in enumerate(subs, start=1):
        a = doc.get("assign", {}).get(s["id"])
        t = a["type"] if a else doc["preset_defaults"].get(s["paint"]["preset"])
        if not t:
            continue
        if t not in doc["types"]:
            raise SystemExit("foliage type %s for %s is not defined" % (t, s["id"]))
        m, scale, tl = by_type.setdefault(t, (np.zeros((n, n), bool), np.ones((n, n), np.float32),
                                              np.full((n, n), 10000, np.float32)))
        sel = idx4 == i
        m |= sel
        scale[sel] = float((a or {}).get("density_scale", 1.0))
        pr = dict(presets[s["paint"]["preset"]], **(s["paint"].get("override") or {}))
        if pr.get("treeline_y") is not None:
            tl[sel] = float(pr["treeline_y"])
    return by_type


OVERLAY_REQUIRED = ("id", "subregions", "stems_per_ha", "classes")


def overlay_layers(doc):
    """(layers, path_clearance_blocks) from data/foliage.json "overlays"; ([], 0) when there are none. Fails closed on
    a malformed layer, since tools/validate_data.py does not check overlays."""
    ov = doc.get("overlays")
    if not ov:
        return [], 0
    layers = ov.get("layers") or []
    seen = set()
    for lay in layers:
        missing = [k for k in OVERLAY_REQUIRED if k not in lay]
        if missing:
            raise SystemExit("foliage overlay %s needs %s" % (lay.get("id"), ", ".join(missing)))
        if lay["id"] in seen:
            raise SystemExit("foliage overlay %s is listed twice" % lay["id"])
        seen.add(lay["id"])
        if "biome" in lay:
            raise SystemExit("foliage overlay %s sets a biome; overlays never change biomes (spawn pools key on "
                             "biome)" % lay["id"])
        if not isinstance(lay["subregions"], dict) or not lay["subregions"]:
            raise SystemExit("foliage overlay %s: subregions must map sub-region ids to a density scale" % lay["id"])
        if not lay["classes"]:
            raise SystemExit("foliage overlay %s has no classes" % lay["id"])
        pt = lay.get("patches")
        if pt is not None and not (0 < pt.get("share", 0) <= 1 and pt.get("scale", 0) > 0):
            raise SystemExit("foliage overlay %s: patches need a scale and a share in (0, 1]" % lay["id"])
        for db in lay.get("debris") or []:
            if db.get("zone") not in ("any", "core"):
                raise SystemExit("foliage overlay %s: debris zone %r is not any or core" % (lay["id"], db.get("zone")))
    return layers, int(ov.get("path_clearance_blocks", 0))


def type_boxes(types, n, margin):
    out = {}
    for t, (m, _, _) in types.items():
        zs, xs = np.nonzero(m)
        if len(zs) == 0:
            continue
        out[t] = (max(0, zs.min() - margin), min(n, zs.max() + margin + 1), max(0, xs.min() - margin), min(n, xs.max() + margin + 1))
    return out


def place(doc, library, subs, presets, idx, heights, slope, allowed, lake_depth, water, exclusions, seed, paths=None):
    """Return positions {group: [(x, z)]}, per-type fields (crops at G blocks with their box), canopy, stats, and for
    overlays their fields, stats and a per-sub-region tally before and after them.

    paths: optional block mask of route lanes that overlay ground contact keeps clear of (forest types ignore it)."""
    N = heights.shape[0]
    n = N // G
    h4 = heights[::G, ::G].astype(np.float32)
    s4 = slope[::G, ::G].astype(np.float32)
    idx4 = idx[::G, ::G]
    water4 = water[::G, ::G]
    gstats = group_stats(library)
    dm = doc["density_model"]
    rng = np.random.default_rng(seed)
    types = type_masks(doc, subs, presets, idx4)
    type_ids = sorted(types)

    reach_max = max([doc["types"][t].get("edge_width", 0) + doc["types"][t].get("ragged", 0) for t in type_ids]
                    + [(doc["types"][t].get("lone") or {}).get("reach", 0) for t in type_ids] + [0])
    boxes = type_boxes(types, n, int(reach_max / G) + 4)
    type_ids = [t for t in type_ids if t in boxes]
    wd = inside_distance(~water4, 64) * G          # blocks to water, capped at 256
    forest_type = np.full((n, n), -1, np.int16)
    fields = {}
    for ti, t in enumerate(type_ids):
        spec = doc["types"][t]
        z0, z1, x0, x1 = boxes[t]
        m = types[t][0][z0:z1, x0:x1]
        scale = types[t][1][z0:z1, x0:x1]
        tl = types[t][2][z0:z1, x0:x1]
        hn, wn = m.shape
        salt = 1000 + ti * 17
        ragged = spec.get("ragged", 0)
        ew = spec.get("edge_width", 0)

        def crop_noise(scale_blocks, s):
            return noise(n, scale_blocks, s)[z0:z1, x0:x1]

        if ew > 0:
            e = inside_distance(m, int((ew + ragged) / G) + 2) * G
            e = e + ragged * (crop_noise(dm["noise"]["ragged_scale"], seed + salt) - 0.5) * 2
            c = np.clip(e / ew, 0, 1) ** 0.8
            inside = m & (e > 0)
        else:
            c = m.astype(np.float32)
            inside = m.copy()
        d = c.copy()
        gs = spec.get("glade_share", 0)
        if gs > 0:
            d *= smoothstep(gs - 0.04, gs + 0.06, crop_noise(dm["noise"]["glade_scale"], seed + salt + 1))
        k = spec.get("clumping", 0)
        if k > 0:
            d *= (1 - k) + k * smoothstep(0.45, 0.75, crop_noise(dm["noise"]["clump_scale"], seed + salt + 2)) * 2.2
        d *= 1 - smoothstep(spec.get("slope_lo", 20), spec.get("slope_hi", 34), s4[z0:z1, x0:x1])
        d *= 1 - smoothstep(tl - 24, tl, h4[z0:z1, x0:x1])
        wdc = wd[z0:z1, x0:x1]
        wb = spec.get("water_boost")
        if wb:
            d *= 1 + (wb["factor"] - 1) * np.exp(-wdc / wb["reach"])
        d[wdc < dm["water_clearance_blocks"]] = 0
        d *= scale
        d[~inside] = 0
        fields[t] = {"box": (z0, z1, x0, x1), "mask": m, "inside": inside, "core": (c * inside).astype(np.float32),
                     "density": np.clip(d, 0, 1.5).astype(np.float32)}
        forest_type[z0:z1, x0:x1][inside] = ti

    spacing = Spacing()
    positions = {}
    counts = {t: {} for t in type_ids}
    core_counts = {t: {} for t in type_ids}
    canopy = np.zeros((n, n), np.float32)

    def stamp(x, z, group):
        gsd = gstats.get(group)
        if not gsd:
            return
        top = float(heights[int(z), int(x)]) + gsd["height"]
        r = max(1, int(round(gsd["crown"] / G)))
        cx, cz = int(x) // G, int(z) // G
        a0, a1, b0, b1 = max(0, cz - r), min(n, cz + r + 1), max(0, cx - r), min(n, cx + r + 1)
        canopy[a0:a1, b0:b1] = np.maximum(canopy[a0:a1, b0:b1], top)

    def trunk_ok(x, z, group, max_slope):
        # every column the object's ground contact can cover, under any of WorldPainter's four rotations:
        # the square of ground_radius around the origin (a 2x2 trunk has radius 1, so its 3x3 is checked)
        r = int(gstats.get(group, {}).get("ground_radius", 0))
        if x - r < 0 or z - r < 0 or x + r >= N or z + r >= N:
            return False
        win = (slice(z - r, z + r + 1), slice(x - r, x + r + 1))
        if exclusions[win].any() or not allowed[win].all():
            return False
        return slope[z, x] <= max_slope

    glades = []
    skipped = []
    for lt in doc.get("landmark_trees") or []:
        x, z = lt["site"]
        if not (0 <= x < N and 0 <= z < N):
            skipped.append(lt["id"])
            continue
        glades.append((x, z, lt.get("glade_radius", 24)))
        positions.setdefault(lt["object"], []).append((x, z))
        stamp(x, z, lt["object"])

    def clear_of_glades(x, z):
        return all((x - gx) ** 2 + (z - gz) ** 2 >= r * r for gx, gz, r in glades)

    max_sp = max([c["spacing"] for t in type_ids for c in doc["types"][t]["classes"]] + [3])

    def draw(box, lam, weights_fn, sp_of, groups, gen=None):
        # gen: an overlay's own stream; the forest types all draw from rng, in the same order as before overlays
        r_ = rng if gen is None else gen
        z0, z1, x0, x1 = box
        zs, xs = np.nonzero(r_.random(lam.shape, dtype=np.float32) < lam * G * G)
        if len(zs) == 0:
            return []
        wts = weights_fn(zs, xs)
        tot = wts.sum(axis=1)
        keep = tot > 0
        zs, xs, wts, tot = zs[keep], xs[keep], wts[keep], tot[keep]
        bx = (xs + x0) * G + r_.integers(0, G, len(xs))
        bz = (zs + z0) * G + r_.integers(0, G, len(zs))
        u = r_.random(len(bx)) * tot
        choice = np.minimum((np.cumsum(wts, axis=1) < u[:, None]).sum(axis=1), len(groups) - 1)
        order = np.lexsort((r_.random(len(bx)), -np.array([sp_of[g] for g in groups])[choice]))
        return [(int(bx[i]), int(bz[i]), groups[choice[i]]) for i in order]

    open_ids = [i for i, tt in enumerate(type_ids) if doc["types"][tt].get("open")]
    for ti, t in enumerate(type_ids):
        spec = doc["types"][t]
        f = fields[t]
        z0, z1, x0, x1 = f["box"]
        classes = spec["classes"]
        groups = [c["group"] for c in classes]
        sp_of = {c["group"]: c["spacing"] for c in classes}
        lam = spec["stems_per_ha"] / 1e4 * f["density"]
        if "elevation_sort" in spec:
            es = spec["elevation_sort"]
            hc = h4[z0:z1, x0:x1]
            rel = (hc - local_mean(hc, int(es["radius"] / G))) / es["span"]
            hi = np.clip(0.5 + rel / 2, 0, 1)

            def weights(zs, xs, hi=hi, classes=classes):
                v = hi[zs, xs]
                return np.stack([c.get("low", 0) * (1 - v) + c.get("high", 0) * v for c in classes], axis=-1)
        else:
            def weights(zs, xs, cc=f["core"], classes=classes):
                v = cc[zs, xs]
                return np.stack([c.get("core", 1) * v + c.get("edge", 1) * (1 - v) for c in classes], axis=-1)
        for x, z, g in draw(f["box"], lam, weights, sp_of, groups):
            sp = sp_of[g]
            if not trunk_ok(x, z, g, spec.get("slope_hi", 34)):
                continue
            if not clear_of_glades(x, z) or not spacing.ok(x, z, sp, (sp + max_sp) / 2 + 1):
                continue
            spacing.add(x, z, sp)
            positions.setdefault(g, []).append((x, z))
            counts[t][g] = counts[t].get(g, 0) + 1
            if f["core"][z // G - z0, x // G - x0] >= 0.9:
                core_counts[t][g] = core_counts[t].get(g, 0) + 1
            stamp(x, z, g)
        lone = spec.get("lone")
        if lone and not spec.get("open"):
            ft = forest_type[z0:z1, x0:x1]
            open_ground = (ft < 0) | np.isin(ft, open_ids)
            dout = inside_distance(~f["inside"], int(lone["reach"] / G) + 1) * G
            band = open_ground & (dout > 0) & (dout <= lone["reach"])
            lam_l = np.where(band, lone["per_ha"] / 1e4 * (1 - dout / lone["reach"]) ** 2, 0).astype(np.float32)
            lg = lone["groups"]
            spl = {g: sp_of.get(g, 6) for g in lg}
            for x, z, g in draw(f["box"], lam_l, lambda zs, xs, k=len(lg): np.ones((len(zs), k), np.float32), spl, lg):
                if not trunk_ok(x, z, g, spec.get("slope_lo", 20)) or not clear_of_glades(x, z) \
                        or not spacing.ok(x, z, spl[g], (spl[g] + max_sp) / 2 + 1):
                    continue
                spacing.add(x, z, spl[g])
                positions.setdefault(g, []).append((x, z))
                counts[t]["lone:" + g] = counts[t].get("lone:" + g, 0) + 1
                stamp(x, z, g)

    debris_spacing = Spacing()
    for ti, t in enumerate(type_ids):
        spec = doc["types"][t]
        f = fields[t]
        for db in spec.get("debris") or []:
            zone = f["core"] if db.get("zone") == "core" else f["inside"].astype(np.float32)
            lam = (db["per_ha"] / 1e4 * zone).astype(np.float32)
            g = db["group"]
            for x, z, _ in draw(f["box"], lam, lambda zs, xs: np.ones((len(zs), 1), np.float32), {g: 3}, [g]):
                if not trunk_ok(x, z, g, db.get("max_slope", 20)):
                    continue
                if not clear_of_glades(x, z) or not spacing.ok(x, z, 2.5, (2.5 + max_sp) / 2 + 1) \
                        or not debris_spacing.ok(x, z, 3, 4):
                    continue
                debris_spacing.add(x, z, 3)
                positions.setdefault(g, []).append((x, z))
                counts[t][g] = counts[t].get(g, 0) + 1

    # ---------------------------------------------------------------- overlays: after everything above, own streams
    n_before = {g: len(p) for g, p in positions.items()}
    layers, _ = overlay_layers(doc)
    overlay_ids, overlay_fields, overlay_counts = [], {}, {}
    sub_index = {s["id"]: i for i, s in enumerate(subs, start=1)}
    ov_max_sp = max([c["spacing"] for lay in layers for c in lay["classes"]] + [max_sp])

    def clear_of_paths(x, z, group):
        if paths is None:
            return True
        r = int(gstats.get(group, {}).get("ground_radius", 0))
        return not paths[max(0, z - r):z + r + 1, max(0, x - r):x + r + 1].any()

    for lay in layers:
        oid = lay["id"]
        for g in [c["group"] for c in lay["classes"]] + [db["group"] for db in lay.get("debris") or []]:
            if g not in gstats:
                raise SystemExit("foliage overlay %s uses object group %s, which the library does not have" % (oid, g))
        scale4 = np.zeros((n, n), np.float32)
        for sid, sc in lay["subregions"].items():
            if sid not in sub_index:
                raise SystemExit("foliage overlay %s names sub-region %s, which is not in data/regions.json" % (oid, sid))
            scale4[idx4 == sub_index[sid]] = float(sc)
        m_full = scale4 > 0
        overlay_counts[oid] = {}
        if not m_full.any():
            continue
        ew, ragged = lay.get("edge_width", 0), lay.get("ragged", 0)
        zs_, xs_ = np.nonzero(m_full)
        margin = int((ew + ragged) / G) + 4
        box = (max(0, zs_.min() - margin), min(n, zs_.max() + margin + 1),
               max(0, xs_.min() - margin), min(n, xs_.max() + margin + 1))
        z0, z1, x0, x1 = box
        m = m_full[z0:z1, x0:x1]
        salt = 5000 + zlib.crc32(oid.encode("utf-8")) % 100000
        orng = np.random.default_rng([int(seed), zlib.crc32(oid.encode("utf-8"))])

        def crop_noise(scale_blocks, s, z0=z0, z1=z1, x0=x0, x1=x1):
            return noise(n, scale_blocks, s)[z0:z1, x0:x1]

        if ew > 0:
            e = inside_distance(m, int((ew + ragged) / G) + 2) * G
            e = e + ragged * (crop_noise(dm["noise"]["ragged_scale"], seed + salt) - 0.5) * 2
            c = np.clip(e / ew, 0, 1) ** 0.8
            inside = m & (e > 0)
        else:
            c = m.astype(np.float32)
            inside = m.copy()
        d = c.astype(np.float32)
        pt = lay.get("patches")
        if pt:
            pn = crop_noise(pt["scale"], seed + salt + 1)
            vals = pn[inside]
            thr = float(np.quantile(vals, 1 - pt["share"])) if vals.size else 1.0
            soft = float(pt.get("soft", 0.05))
            d = d * smoothstep(thr - soft, thr + soft, pn)
        wdc = wd[z0:z1, x0:x1]
        nw = lay.get("near_water")
        if nw:
            d = d * (nw["floor"] + (1 - nw["floor"]) * np.exp(-wdc / nw["reach"]))
        d = d * (1 - smoothstep(lay.get("slope_lo", 20), lay.get("slope_hi", 34), s4[z0:z1, x0:x1]))
        d[wdc < dm["water_clearance_blocks"]] = 0
        d = d * scale4[z0:z1, x0:x1]
        d[~inside] = 0
        core = np.clip(d, 0, 1).astype(np.float32)
        overlay_fields[oid] = {"box": box, "mask": m, "inside": inside, "core": core,
                               "density": np.clip(d, 0, 1.5).astype(np.float32)}
        overlay_ids.append(oid)
        oc = overlay_counts[oid]

        classes = lay["classes"]
        groups = [c_["group"] for c_ in classes]
        sp_of = {c_["group"]: c_["spacing"] for c_ in classes}
        lam = lay["stems_per_ha"] / 1e4 * d

        def weights(zs, xs, cc=core, classes=classes):
            v = cc[zs, xs]
            return np.stack([c_.get("core", 1) * v + c_.get("edge", 1) * (1 - v) for c_ in classes], axis=-1)

        for x, z, g in draw(box, lam, weights, sp_of, groups, gen=orng):
            sp = sp_of[g]
            if not trunk_ok(x, z, g, lay.get("slope_hi", 34)) or not clear_of_paths(x, z, g):
                continue
            if not clear_of_glades(x, z) or not spacing.ok(x, z, sp, (sp + ov_max_sp) / 2 + 1) \
                    or not debris_spacing.ok(x, z, sp, (sp + 3) / 2 + 1):
                continue
            spacing.add(x, z, sp)
            positions.setdefault(g, []).append((x, z))
            oc[g] = oc.get(g, 0) + 1
            stamp(x, z, g)
        for db in lay.get("debris") or []:
            zone = core if db.get("zone") == "core" else inside.astype(np.float32)
            lam_d = (db["per_ha"] / 1e4 * zone).astype(np.float32)
            g = db["group"]
            for x, z, _ in draw(box, lam_d, lambda zs, xs: np.ones((len(zs), 1), np.float32), {g: 3}, [g], gen=orng):
                if not trunk_ok(x, z, g, db.get("max_slope", 20)) or not clear_of_paths(x, z, g):
                    continue
                if not clear_of_glades(x, z) or not spacing.ok(x, z, 2.5, (2.5 + ov_max_sp) / 2 + 1) \
                        or not debris_spacing.ok(x, z, 3, 4):
                    continue
                debris_spacing.add(x, z, 3)
                positions.setdefault(g, []).append((x, z))
                oc[g] = oc.get(g, 0) + 1

    # which groups are trees (for the tallies): every class and lone group of a type or an overlay
    tree_groups = {c["group"] for t in doc["types"].values() for c in t["classes"]}
    tree_groups |= {g for t in doc["types"].values() for g in (t.get("lone") or {}).get("groups", [])}
    tree_groups |= {c["group"] for lay in layers for c in lay["classes"]}

    def split(g, pts):
        """(point, placed before the overlays?) for every point of a group."""
        nb = n_before.get(g, 0)
        return ((p, j < nb) for j, p in enumerate(pts))

    overlay_stats = {}
    for lay in layers:
        oid = lay["id"]
        if oid not in overlay_fields:
            overlay_stats[oid] = {"area_ha": 0.0, "by_group": {}}
            continue
        f = overlay_fields[oid]
        z0, z1, x0, x1 = f["box"]
        inside, core = f["inside"], f["core"]
        dense = inside & (core >= 0.5)
        area_ha = float(inside.sum()) * G * G / 1e4
        dense_ha = float(dense.sum()) * G * G / 1e4
        added = sum(v for g, v in overlay_counts[oid].items() if g in {c["group"] for c in lay["classes"]})
        # every tree standing in the overlay's area and in its dense part, before and after the overlays, and the
        # mean free sightline at eye height in the dense part (1 / sum of stems per block x eye width)
        tally = {"area_before": 0, "area_after": 0, "dense_before": 0, "dense_after": 0}
        block = {"before": 0.0, "after": 0.0}
        for g, pts in positions.items():
            if g not in tree_groups or g not in gstats:
                continue
            for (x, z), before in split(g, pts):
                cz, cx = z // G - z0, x // G - x0
                if not (0 <= cz < z1 - z0 and 0 <= cx < x1 - x0) or not inside[cz, cx]:
                    continue
                tally["area_after"] += 1
                tally["area_before"] += before
                if dense[cz, cx]:
                    tally["dense_after"] += 1
                    tally["dense_before"] += before
                    block["after"] += gstats[g]["eye_width"]
                    block["before"] += gstats[g]["eye_width"] if before else 0

        def per_ha(v, ha):
            return round(v / ha, 1) if ha else None

        def sightline(b_):
            return round(dense_ha * 1e4 / b_) if b_ else None

        overlay_stats[oid] = {
            "area_ha": round(area_ha, 1), "stems_added": added, "target_stems_per_ha": lay["stems_per_ha"],
            "trees_per_ha_before": per_ha(tally["area_before"], area_ha), "trees_per_ha": per_ha(tally["area_after"], area_ha),
            "dense_area_ha": round(dense_ha, 1),
            "dense_trees_per_ha_before": per_ha(tally["dense_before"], dense_ha),
            "dense_trees_per_ha": per_ha(tally["dense_after"], dense_ha),
            "dense_eye_level_sightline_blocks_before": sightline(block["before"]),
            "dense_eye_level_sightline_blocks": sightline(block["after"]),
            "by_group": dict(sorted(overlay_counts[oid].items()))}

    # per sub-region: trees and other objects (debris, landmarks) before and after the overlays, on dry 4-block cells
    dry4 = ~water4
    by_subregion = {}
    for i, s in enumerate(subs, start=1):
        by_subregion[s["id"]] = {"dry_area_ha": round(float(((idx4 == i) & dry4).sum()) * G * G / 1e4, 1),
                                 "trees_before": 0, "trees": 0, "other_before": 0, "other": 0}
    for g, pts in positions.items():
        kind = "trees" if g in tree_groups else "other"
        for (x, z), before in split(g, pts):
            i = int(idx4[z // G, x // G])
            if i <= 0 or i > len(subs):
                continue
            e = by_subregion[subs[i - 1]["id"]]
            e[kind] += 1
            e[kind + "_before"] += before
    for e in by_subregion.values():
        a_ = e["dry_area_ha"]
        e["trees_per_ha_before"] = round(e["trees_before"] / a_, 1) if a_ else None
        e["trees_per_ha"] = round(e["trees"] / a_, 1) if a_ else None

    stats = {}
    for t in type_ids:
        area_ha = float(fields[t]["inside"].sum()) * G * G / 1e4
        class_groups = {c["group"] for c in doc["types"][t]["classes"]}
        trees = sum(v for k, v in counts[t].items() if k in class_groups)
        core_ha = float((fields[t]["core"] >= 0.9).sum()) * G * G / 1e4
        core_stems = sum(core_counts[t].values())
        # mean free sightline at eye height in the core: 1 / sum(stems per block * eye width)
        blocking = sum(c / (core_ha * 1e4) * gstats[g]["eye_width"] for g, c in core_counts[t].items()) if core_ha else 0
        stats[t] = {"area_ha": round(area_ha, 1), "stems": trees, "stems_per_ha": round(trees / area_ha, 1) if area_ha else None,
                    "core_area_ha": round(core_ha, 1), "core_stems_per_ha": round(core_stems / core_ha, 1) if core_ha else None,
                    "core_eye_level_sightline_blocks": round(1 / blocking) if blocking else None,
                    "target_core_stems_per_ha": doc["types"][t]["stems_per_ha"], "by_group": dict(sorted(counts[t].items()))}
    if skipped:
        stats["_landmark_trees_outside_map"] = skipped
    return {"positions": positions, "fields": fields, "type_ids": type_ids, "canopy": canopy, "stats": stats,
            "overlay_ids": overlay_ids, "overlay_fields": overlay_fields, "overlay_stats": overlay_stats,
            "by_subregion": by_subregion}
