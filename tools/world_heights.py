#!/usr/bin/env python
"""Read the surface of a saved world back from its region files, and compare it with the heightmap.

Terrain tools measure the heightmap. This measures the world the game will
load, so an export can be checked against what the heightmap predicted.

  extract   decode every chunk in a rectangle and write, per column:
              ground  Y of the highest block that is not air, water or a
                      non-solid plant (the terrain surface or seabed)
              water   Y of the highest water block above ground, or -32768
            plus which chunks are missing, chunk statuses, and the names of
            the blocks found on top of the ground
  compare   load the heightmap through tools/terrain.py (the world.json
            mapping) and report drift: land elevation, seabed depth, clipped
            summits, the margin, and anything outside the expected canvas

  python tools/world_heights.py extract --world <offline-snapshot-world> \\
      --min-x -1280 --min-z -1280 --max-x 9471 --max-z 9471 --out derived/world/heights.npz
  python tools/world_heights.py compare --heights derived/world/heights.npz --out derived/world/drift.json

Reads only; the server must be stopped so region files are consistent.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import nbt

ROOT = Path(__file__).resolve().parent.parent
REGION_RE = re.compile(r"^r\.(-?\d+)\.(-?\d+)\.mca$")
NONE = -32768
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
WATER = {"minecraft:water", "minecraft:bubble_column"}
# blocks that sit on the ground without being it
COVER = {
    "minecraft:snow", "minecraft:short_grass", "minecraft:grass", "minecraft:tall_grass", "minecraft:fern",
    "minecraft:large_fern", "minecraft:dead_bush", "minecraft:sugar_cane", "minecraft:seagrass",
    "minecraft:tall_seagrass", "minecraft:kelp", "minecraft:kelp_plant", "minecraft:lily_pad",
    "minecraft:dandelion", "minecraft:poppy", "minecraft:cornflower", "minecraft:oxeye_daisy",
    "minecraft:azure_bluet", "minecraft:allium", "minecraft:blue_orchid", "minecraft:lilac",
    "minecraft:rose_bush", "minecraft:peony", "minecraft:sunflower", "minecraft:vine", "minecraft:cactus",
    "minecraft:sweet_berry_bush", "minecraft:brown_mushroom", "minecraft:red_mushroom",
    "minecraft:azalea", "minecraft:flowering_azalea", "minecraft:pink_petals", "minecraft:bamboo",
    "minecraft:mangrove_roots", "minecraft:mushroom_stem", "minecraft:brown_mushroom_block",
    "minecraft:red_mushroom_block", "minecraft:cocoa", "minecraft:pink_tulip", "minecraft:white_tulip",
    "minecraft:red_tulip", "minecraft:orange_tulip",
    # forest understory and small foliage objects (data/foliage.json, kits/structures/foliage)
    "minecraft:lily_of_the_valley", "minecraft:moss_carpet", "minecraft:leaf_litter", "minecraft:bush",
    "minecraft:firefly_bush", "minecraft:wildflowers", "minecraft:vine",
}
# painted worlds carry trees: their trunks and canopy are not the ground surface
COVER_SUFFIXES = ("_leaves", "_log", "_wood")


def is_cover(name):
    return name in COVER or name.endswith(COVER_SUFFIXES)


def unpack_states(raw, palette_len, count=4096):
    """Anvil 1.16+ packed block-state indices (no spanning between longs)."""
    bits = max(4, int(np.ceil(np.log2(palette_len)))) if palette_len > 1 else 0
    if bits == 0 or not raw:
        return np.zeros(count, dtype=np.int32)
    longs = np.frombuffer(raw, dtype=">u8").astype(np.uint64)
    per_long = 64 // bits
    i = np.arange(count, dtype=np.uint64)
    word = longs[(i // np.uint64(per_long)).astype(np.int64)]
    shift = (i % np.uint64(per_long)) * np.uint64(bits)
    return ((word >> shift) & np.uint64((1 << bits) - 1)).astype(np.int32)


def chunk_columns(chunk):
    """-> ground (16,16) int16, water (16,16) int16, status. Ground skips cover: plants, snow layers and trees."""
    ground = np.full((16, 16), NONE, np.int16)
    water = np.full((16, 16), NONE, np.int16)
    names = Counter()
    sections = chunk.get("sections") or chunk.get("Sections") or []
    for sec in sorted(sections, key=lambda s: -int(s.get("Y", 0))):
        bs = sec.get("block_states")
        if not bs:
            continue
        palette = [p.get("Name", "") for p in bs.get("palette") or []]
        if not palette or (len(palette) == 1 and palette[0] in AIR):
            continue
        idx = unpack_states(bs.get("data"), len(palette)).reshape(16, 16, 16)  # [y, z, x]
        is_ground = np.array([n not in AIR and n not in WATER and not is_cover(n) for n in palette])
        is_water = np.array([n in WATER for n in palette])
        base = int(sec.get("Y", 0)) * 16
        g = is_ground[idx]
        w = is_water[idx]
        ys = np.arange(16).reshape(16, 1, 1)
        g_top = np.where(g.any(axis=0), (np.where(g, ys, -1)).max(axis=0) + base, NONE)
        w_top = np.where(w.any(axis=0), (np.where(w, ys, -1)).max(axis=0) + base, NONE)
        water = np.where((water == NONE) & (w_top != NONE), w_top, water).astype(np.int16)
        newly = (ground == NONE) & (g_top != NONE)
        if newly.any():
            ground = np.where(newly, g_top, ground).astype(np.int16)
        if (ground != NONE).all():
            break
    # water only counts above the ground
    water = np.where(water > ground, water, NONE).astype(np.int16)
    status = str(chunk.get("Status", "?")).replace("minecraft:", "")
    return ground, water, status


def _region_job(args):
    path, rx, rz, bounds = args
    x0, z0 = rx * 512, rz * 512
    g = np.full((512, 512), NONE, np.int16)
    w = np.full((512, 512), NONE, np.int16)
    present = np.zeros((32, 32), bool)
    statuses = Counter()
    outside = 0
    for lx, lz, ch in nbt.region_chunks(path):
        cx0, cz0 = x0 + lx * 16, z0 + lz * 16
        inside = not (cx0 + 15 < bounds[0] or cx0 > bounds[2] or cz0 + 15 < bounds[1] or cz0 > bounds[3])
        if not inside:
            outside += 1
            continue
        ground, water, status = chunk_columns(ch)
        g[lz * 16:lz * 16 + 16, lx * 16:lx * 16 + 16] = ground
        w[lz * 16:lz * 16 + 16, lx * 16:lx * 16 + 16] = water
        present[lz, lx] = True
        statuses[status] += 1
    return rx, rz, g, w, present, dict(statuses), outside


def extract(world_dir, bounds, workers=None):
    import runtime_guard
    region = runtime_guard.check(world_dir, "read") / "region"
    minx, minz, maxx, maxz = bounds
    W, H = maxx - minx + 1, maxz - minz + 1
    ground = np.full((H, W), NONE, np.int16)
    water = np.full((H, W), NONE, np.int16)
    chunks_expected = ((maxx >> 4) - (minx >> 4) + 1) * ((maxz >> 4) - (minz >> 4) + 1)
    jobs, outside_files = [], []
    for p in sorted(region.iterdir()):
        m = REGION_RE.match(p.name)
        if not m or p.stat().st_size < 8192:
            continue
        rx, rz = int(m.group(1)), int(m.group(2))
        if rx * 512 + 511 < minx or rx * 512 > maxx or rz * 512 + 511 < minz or rz * 512 > maxz:
            outside_files.append(p.name)
            continue
        jobs.append((str(p), rx, rz, bounds))
    statuses, present_chunks, outside_chunks = Counter(), 0, 0
    with ProcessPoolExecutor(max_workers=workers or os.cpu_count()) as ex:
        for rx, rz, g, w, present, st, outside in ex.map(_region_job, jobs, chunksize=1):
            x0, z0 = rx * 512, rz * 512
            sx0, sz0 = max(x0, minx), max(z0, minz)
            sx1, sz1 = min(x0 + 511, maxx), min(z0 + 511, maxz)
            if sx0 <= sx1 and sz0 <= sz1:
                ground[sz0 - minz:sz1 - minz + 1, sx0 - minx:sx1 - minx + 1] = g[sz0 - z0:sz1 - z0 + 1, sx0 - x0:sx1 - x0 + 1]
                water[sz0 - minz:sz1 - minz + 1, sx0 - minx:sx1 - minx + 1] = w[sz0 - z0:sz1 - z0 + 1, sx0 - x0:sx1 - x0 + 1]
            statuses.update(st)
            present_chunks += int(present.sum())
            outside_chunks += outside
    meta = {"world": str(world_dir), "bounds": {"min_x": minx, "min_z": minz, "max_x": maxx, "max_z": maxz},
            "chunks_expected": chunks_expected, "chunks_present": present_chunks,
            "chunks_saved_outside_bounds": outside_chunks, "region_files_outside_bounds": outside_files,
            "status": dict(statuses), "columns_without_ground": int((ground == NONE).sum())}
    return ground, water, meta


def _stats(a):
    a = np.asarray(a, dtype=np.float64)
    if a.size == 0:
        return None
    q = np.percentile(a, [5, 25, 50, 75, 95])
    return {"n": int(a.size), "min": float(a.min()), "p5": float(q[0]), "p25": float(q[1]), "median": float(q[2]),
            "p75": float(q[3]), "p95": float(q[4]), "max": float(a.max()), "mean": round(float(a.mean()), 3)}


def compare(heights_npz, world_path=None, source_root=None, landmarks=True):
    import terrain as T
    z = np.load(heights_npz, allow_pickle=False)
    ground, water = z["ground"], z["water"]
    meta = json.loads(str(z["meta"]))
    b = meta["bounds"]
    pred, world = T.load(world_path, source_root)
    sea = T.sea_level(world)
    H, W = pred.shape
    ox, oz = -b["min_x"], -b["min_z"]            # landmass origin inside the extracted arrays
    g = ground[oz:oz + H, ox:ox + W].astype(np.float64)
    wt = water[oz:oz + H, ox:ox + W]
    imp = world["import"]
    prev = imp.get("previous") or {}

    report = {"heights": str(heights_npz), "extract": meta, "import": {k: imp[k] for k in ("low_in", "high_in", "low_out", "high_out")}}
    missing = g <= NONE
    report["landmass_columns_missing"] = int(missing.sum())

    # How WorldPainter turns a float height into a block: compare three rules
    diff_round = g - np.floor(pred + 0.5)
    diff_floor = g - np.floor(pred)
    rule = "round" if (diff_round == 0).mean() >= (diff_floor == 0).mean() else "floor"
    expected = np.floor(pred + 0.5) if rule == "round" else np.floor(pred)
    d = (g - expected)[~missing]
    report["integer_rule"] = {"best_match": rule, "exact_round": round(float((diff_round == 0).mean()), 6),
                              "exact_floor": round(float((diff_floor == 0).mean()), 6)}
    land = (pred >= sea) & ~missing
    seam = (pred < sea) & ~missing
    dl = (g - expected)[land]
    report["land"] = {
        "columns": int(land.sum()),
        "exact": round(float((dl == 0).mean()), 6), "within_1": round(float((np.abs(dl) <= 1).mean()), 6),
        "max_abs_drift": float(np.abs(dl).max()) if dl.size else 0.0,
        "drift_histogram": {str(int(k)): int(v) for k, v in zip(*np.unique(np.clip(dl, -5, 5), return_counts=True))},
    }
    if prev:
        # land under the previous import line, for "did land move"
        depth = world["heightmap"].get("bit_depth", 16)
        full = float((1 << depth) - 1)
        lo_in, hi_in, lo_out, hi_out = (float(imp[k]) for k in ("low_in", "high_in", "low_out", "high_out"))
        frac = (pred - lo_out) / (hi_out - lo_out) * (hi_in - lo_in) + lo_in
        old = np.clip(prev["low_out"] + (frac - prev["low_in"]) / (prev["high_in"] - prev["low_in"]) * (prev["high_out"] - prev["low_out"]),
                      prev["low_out"], prev["high_out"])
        old_block = np.floor(old + 0.5) if rule == "round" else np.floor(old)
        above = (old > prev["low_out"] + 0.5) & ~missing
        do = (g - old_block)[above]
        report["land_vs_previous_mapping"] = {
            "columns_above_previous_floor": int(above.sum()),
            "exact": round(float((do == 0).mean()), 6), "within_1": round(float((np.abs(do) <= 1).mean()), 6),
            "max_abs_drift": float(np.abs(do).max()) if do.size else 0.0,
            "float_difference_max": float(np.abs(old - pred)[above].max()) if above.any() else 0.0,
        }
    seabed_export = g[seam]
    seabed_pred = pred[seam]
    report["seabed"] = {
        "columns": int(seam.sum()),
        "export": _stats(seabed_export), "heightmap": _stats(seabed_pred),
        "export_share_at_or_below_y20": round(float((seabed_export <= 20).mean()), 4),
        "export_share_at_or_below_y30": round(float((seabed_export <= 30).mean()), 4),
        "heightmap_share_at_or_below_y20": round(float((seabed_pred <= 20).mean()), 4),
        "drift": {"exact": round(float((g - expected)[seam].__eq__(0).mean()), 6),
                  "max_abs": float(np.abs((g - expected)[seam]).max()) if seam.any() else 0.0},
        "water_to_sea_level": round(float((wt[seam] == int(sea) - 1).mean() + (wt[seam] == int(sea)).mean()), 4),
        "water_top_values": {str(int(k)): int(v) for k, v in zip(*np.unique(wt[seam], return_counts=True))},
    }
    hi = float(imp["high_out"])
    land_all = pred >= sea
    report["clipped_summits"] = {
        "ceiling_y": hi,
        "heightmap_land_share_at_ceiling": round(float((pred[land_all] >= hi).mean()), 6),
        "heightmap_all_share_at_ceiling": round(float((pred >= hi).mean()), 6),
        "export_land_share_at_ceiling": round(float((g[land_all & ~missing] >= hi).mean()), 6),
        "export_columns_above_ceiling": int((g > hi).sum()),
    }
    # margin: everything extracted outside the landmass box
    outer = np.ones(ground.shape, bool)
    outer[oz:oz + H, ox:ox + W] = False
    mg = ground[outer]
    report["margin"] = {"columns": int(outer.sum()), "missing": int((mg <= NONE).sum()),
                        "ground": _stats(mg[mg > NONE]),
                        "water_top_values": {str(int(k)): int(v) for k, v in zip(*np.unique(water[outer], return_counts=True))}}
    # water on land below sea level (inland basins, the rift) and dry sea
    report["water_classification"] = {
        "heightmap_below_sea_level_columns": int((pred < sea).sum()),
        "export_columns_with_water": int((wt > NONE).sum()),
        "below_sea_level_without_water": int(((pred < sea) & (wt <= NONE) & ~missing).sum()),
        "above_sea_level_with_water": int(((pred >= sea) & (wt > NONE)).sum()),
    }
    lm_path = ROOT / "data" / "landmarks.json"
    if landmarks and lm_path.is_file():
        doc = json.loads(lm_path.read_text(encoding="utf-8"))
        report["water_never_landmarks"] = [l["id"] for l in doc.get("landmarks") or [] if l.get("water") == "never"]
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--world", required=True, help="world folder holding region/")
    e.add_argument("--min-x", type=int, required=True)
    e.add_argument("--min-z", type=int, required=True)
    e.add_argument("--max-x", type=int, required=True)
    e.add_argument("--max-z", type=int, required=True)
    e.add_argument("--workers", type=int, default=None)
    e.add_argument("--out", required=True)
    c = sub.add_parser("compare")
    c.add_argument("--heights", required=True)
    c.add_argument("--world-config", default=None)
    c.add_argument("--source-root", default=None)
    c.add_argument("--out", required=True)
    a = p.parse_args(argv)
    if a.cmd == "extract":
        ground, water, meta = extract(a.world, (a.min_x, a.min_z, a.max_x, a.max_z), a.workers)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(a.out, ground=ground, water=water, meta=np.array(json.dumps(meta)))
        print(json.dumps(meta, indent=1))
        return 0
    rep = compare(a.heights, a.world_config, a.source_root)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("integer_rule", "land", "seabed", "clipped_summits") if k in rep}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
