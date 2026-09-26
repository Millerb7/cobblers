#!/usr/bin/env python
"""Rasterise the region plan into WorldPainter paint maps (tools/worldpainter/paint.js).

Reads data/regions.json (sub-region polygons and their paint presets), data/landmarks.json
(water bodies and carved channels) and the heightmap, and writes 8-bit PNGs aligned with the
heightmap (pixel = block) plus manifest.json:

  biomes.png      WorldPainter biome id per column (sea biomes by depth and latitude)
  terrain.png     terrain code per column (see TERRAIN_CODES)
  objects_*.png   one map per foliage object group, 15 where one object of the group stands (tools/foliage.py)
  canopy.npz      planned canopy top on 4-block cells, for sightline checks (tools/landmark_trees.py)
  plants_*.png    one bit map per plant set
  frost.png       snow cover
  water_*.png     raised water for lakes above sea level, cropped to each basin

  python tools/paint_maps.py --source-root C:/Users/wnd/Documents --out build/paint

This is a preview paint: rough by design. Everything it decides comes from the presets in
data/regions.json and the forest types in data/foliage.json, so a repaint is an edit there and a rerun.

Trees are custom objects (kits/structures/foliage, tools/foliage_objects.py) at positions tools/foliage.py
computes. The "allowed" mask records where a trunk may stand: land, off the shore, out of lake basins, river
beds and banks, and dry ravine floors.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import terrain as T

ROOT = Path(__file__).resolve().parent.parent
N = 8192

# WorldPainter 2.27.1 biome ids (org.pepsoft.worldpainter.biomeschemes.Minecraft1_21Biomes, first occurrence)
WP_BIOMES = {
    "minecraft:ocean": 0, "minecraft:plains": 1, "minecraft:desert": 2, "minecraft:windswept_hills": 3, "minecraft:forest": 4,
    "minecraft:taiga": 5, "minecraft:swamp": 6, "minecraft:river": 7, "minecraft:frozen_ocean": 10, "minecraft:frozen_river": 11,
    "minecraft:snowy_plains": 12, "minecraft:mushroom_fields": 14, "minecraft:beach": 16, "minecraft:jungle": 21,
    "minecraft:sparse_jungle": 23, "minecraft:deep_ocean": 24, "minecraft:stony_shore": 25, "minecraft:snowy_beach": 26,
    "minecraft:birch_forest": 27, "minecraft:dark_forest": 29, "minecraft:snowy_taiga": 30, "minecraft:old_growth_pine_taiga": 32,
    "minecraft:windswept_forest": 34, "minecraft:savanna": 35, "minecraft:savanna_plateau": 36, "minecraft:badlands": 37,
    "minecraft:wooded_badlands": 38, "minecraft:warm_ocean": 44, "minecraft:lukewarm_ocean": 45, "minecraft:cold_ocean": 46,
    "minecraft:deep_lukewarm_ocean": 48, "minecraft:deep_cold_ocean": 49, "minecraft:deep_frozen_ocean": 50,
    "minecraft:sunflower_plains": 129, "minecraft:windswept_gravelly_hills": 131, "minecraft:flower_forest": 132,
    "minecraft:ice_spikes": 140, "minecraft:old_growth_birch_forest": 155, "minecraft:old_growth_spruce_taiga": 160,
    "minecraft:windswept_savanna": 163, "minecraft:eroded_badlands": 165, "minecraft:bamboo_jungle": 168,
    "minecraft:dripstone_caves": 174, "minecraft:lush_caves": 175, "minecraft:cherry_grove": 246, "minecraft:mangrove_swamp": 247,
    "minecraft:deep_dark": 248, "minecraft:frozen_peaks": 249, "minecraft:grove": 250, "minecraft:jagged_peaks": 251,
    "minecraft:meadow": 252, "minecraft:snowy_slopes": 253, "minecraft:stony_peaks": 254,
}
TERRAIN_CODES = {"GRASS": 1, "SAND": 2, "DESERT": 3, "RED_SAND": 4, "MESA": 5, "ROCK": 6, "STONE_MIX": 7, "GRAVEL": 8,
                 "SNOW": 9, "DEEP_SNOW": 10, "PODZOL": 11, "MUD": 12, "MYCELIUM": 13, "BASALT": 14, "BLACKSTONE": 15,
                 "BEACHES": 16, "PERMADIRT": 17, "MAGMA": 18, "CLAY": 19, "MOSS": 20, "RED_DESERT": 21, "BARE_GRASS": 22,
                 "SANDSTONE": 23}
# one mask, 1 where a trunk may stand; the painting steps below clear it where nothing may grow
TREE_LAYERS = ("allowed",)
# Plant names are WorldPainter's (org.pepsoft.worldpainter.layers.plants.Plants). "Short Grass" is avoided:
# WorldPainter 2.27.1 writes it as minecraft:grass, the pre-1.20.3 name. Minecraft upgrades it on chunk load (the
# chunks carry DataVersion 2860), but Distant Horizons reads region files raw and warns, so the sets stay clear of it.
# Two-block plants (Tall Grass, Large Fern, Peony, Lilac) are the eye-level wall: a player's eye is at 1.62, so a
# one-block plant is under it and a two-block plant is in it. Measured on the exported world, Pallet meadows had a
# tall plant in 1 column in 4.1 -- a 4.1-block sightline, the view a player walks out of the hometown into. The target
# is 1 in 8 (an 8-block sightline), so the open-ground sets below carry half the tall weight they did, and the
# difference goes to ferns and flowers, which are one block tall. Halving works whether WorldPainter treats
# occurrence as a share of the layer or as an absolute chance: either way the tall count halves.
# Forest-floor sets are left as they were; the forests measured 1 in 11 to 1 in 20 already.
PLANT_SETS = {
    "grassland": {"Tall Grass": 6, "Fern": 6, "Dandelion": 2, "Poppy": 1, "Oxeye Daisy": 1},
    "meadow_flowers": {"Tall Grass": 3, "Oxeye Daisy": 4, "Cornflower": 4, "Azure Bluet": 3, "Allium": 1, "Dandelion": 2, "Poppy": 2},
    "blossom": {"Pink Tulip": 6, "Peony": 1, "Lilac": 2, "Tall Grass": 2, "White Tulip": 3},
    "shrub": {"Sweet Berry Bush": 5, "Azalea": 4, "Flowering Azalea": 2, "Large Fern": 2, "Tall Grass": 3, "Dead Shrub": 1, "Fern": 4},
    "fern_floor": {"Fern": 8, "Large Fern": 4, "Tall Grass": 2, "Sweet Berry Bush": 1},
    "dry_scrub": {"Dead Shrub": 7, "Tall Grass": 1},
    "swamp_floor": {"Blue Orchid": 3, "Fern": 5, "Tall Grass": 2, "Brown Mushroom": 1},
    "mushrooms": {"Red Mushroom": 1, "Brown Mushroom": 1},
    # forest understory (data/foliage.json types), by how deep inside the forest a column is
    "forest_floor_sparse": {"Fern": 3, "Large Fern": 1, "Brown Mushroom": 1},
    "berry_fern": {"Fern": 5, "Sweet Berry Bush": 3, "Large Fern": 2},
    "moss_mushroom": {"Moss Carpet": 6, "Brown Mushroom": 2, "Red Mushroom": 1},
    "lily_valley": {"Lily of the Valley": 3, "Fern": 2, "Tall Grass": 3},
    "petals": {"Pink Petals": 5, "Tall Grass": 2},
    "jungle_floor": {"Fern": 4, "Large Fern": 3, "Tall Grass": 2},
    # New sets are named to sort after every earlier one: a preset's plant noise is salted by the set's sorted
    # position (main, "salt = 307 + ..."), so a name sorting earlier would reshuffle every plant on the map.
    # bamboo groves in the jungle isles' understory (data/foliage.json overlay jungle_bamboo): vanilla bamboo decides
    # no loaded spawn condition (data/spawn_blocks.json), and no bamboo_jungle biome is painted
    "understory_bamboo": {"Bamboo": 6, "Fern": 3, "Large Fern": 2},
    # the Long Isle's desert island (docs/world-building/LONG_ISLE.md): dead shrubs and the odd cactus on the sand
    "xeric_scrub": {"Dead Shrub": 6, "Cactus": 2},
}
# how WorldPainter renders each object group (tools/worldpainter/paint.js); groups not listed get the defaults:
# random rotation, trunks extended down to uneven ground
OBJECT_SETTINGS = {
    "fallen_log_conifer": {"extend_foundation": False},
    "fallen_log_broadleaf": {"extend_foundation": False},
    "leaf_litter": {"extend_foundation": False},
    "bush_broadleaf": {"extend_foundation": False},
    "bush_conifer": {"extend_foundation": False},
    "jungle_bush": {"extend_foundation": False},
}
ZONES = {"core": (0.66, 1.01), "mid": (0.33, 0.66), "edge": (-0.01, 0.33)}


def value_noise(scale, seed, octaves=2):
    """Smooth noise in [0, 1] over the full map, from bicubic-upsampled random grids."""
    rng = np.random.default_rng(seed)
    out = np.zeros((N, N), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        s = max(4, int(scale / (2 ** o)))
        g = rng.random((N // s + 2, N // s + 2)).astype(np.float32)
        img = Image.fromarray(g, mode="F").resize(((N // s + 2) * s, (N // s + 2) * s), Image.BICUBIC)
        out += amp * np.asarray(img)[:N, :N]
        total += amp
        amp *= 0.5
    out /= total
    lo, hi = np.percentile(out[::16, ::16], [1, 99])
    return np.clip((out - np.float32(lo)) / np.float32(hi - lo), 0, 1).astype(np.float32)


def rasterise_subregions(subs):
    """uint8 index map, 0 = none. Larger sub-regions first; gaps filled from neighbours."""
    img = Image.new("L", (N, N), 0)
    d = ImageDraw.Draw(img)
    order = sorted(range(len(subs)), key=lambda i: -subs[i]["measured"]["area_km2"])
    for i in order:
        for ring in subs[i]["polygons"]:
            if len(ring) >= 3:
                d.polygon([tuple(p) for p in ring], fill=i + 1)
    return np.asarray(img).copy()


def fill_gaps(idx, land):
    from PIL import ImageFilter
    for _ in range(12):
        gaps = land & (idx == 0)
        if not gaps.any():
            break
        grown = np.asarray(Image.fromarray(idx).filter(ImageFilter.MaxFilter(5)))
        idx = np.where(gaps, grown, idx)
    return idx


RIVER_BANK = 2       # blocks of bank material beyond the water's edge
COLD_BIOMES = ("minecraft:snowy_taiga", "minecraft:snowy_plains", "minecraft:grove", "minecraft:snowy_slopes",
               "minecraft:frozen_peaks", "minecraft:jagged_peaks", "minecraft:ice_spikes", "minecraft:snowy_beach")


def paint_rivers(rivers_path, heights, biome, terr, trees, plants, frost, out):
    """Fill every cut river course with water at its stored surface (the whole block below it), paint its bed
    by reach, sand or gravel banks, the river biome (frozen river among cold biomes), and clear trees, plants
    and frost off the water: moving water does not freeze, and an iced-over river would stop being a barrier.

    Writes one level map per course: 8-bit crop, value = water level y, 0 = none. Only the stations of the
    heightmap that was cut are filled, so a plan whose cut does not match the imported heightmap refuses."""
    import grade_rivers as G

    doc = json.loads(Path(rivers_path).read_text(encoding="utf-8"))
    cut = doc.get("cut") or {}
    world = T.load_world(ROOT / "data" / "world.json")
    # the imported heightmap is the cut itself, or a sculpt of it (world.json heightmap.sculpted_from), which keeps
    # river channels unchanged
    hm = world["heightmap"]
    cut_of_import = (hm.get("sculpted_from") or {}).get("sha256") or hm["sha256"]
    if (cut.get("output") or {}).get("sha256") != cut_of_import:
        raise SystemExit("rivers.json cut output %s is not the imported heightmap's river cut %s; rerun the cut (and "
                         "the sculpt) and import it" % ((cut.get("output") or {}).get("sha256"), cut_of_import))
    cold = [WP_BIOMES[b] for b in COLD_BIOMES]
    manifest = []
    for c in doc["courses"]:
        if c["id"] not in cut.get("courses_cut", []):
            continue
        pts, chain = G.densify_chained(c["graded_polyline"])
        reach_of = [G.at_chainage(c["reaches"], ch) for ch in chain]
        pad = max(r["width"] for r in c["reaches"]) // 2 + RIVER_BANK + 2
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        x0, x1 = max(0, int(min(xs)) - pad), min(N, int(max(xs)) + pad + 1)
        z0, z1 = max(0, int(min(zs)) - pad), min(N, int(max(zs)) + pad + 1)
        best = np.full((z1 - z0, x1 - x0), np.inf, np.float32)
        level = np.zeros((z1 - z0, x1 - x0), np.uint8)
        bedmap = np.zeros((z1 - z0, x1 - x0), np.uint8)
        bank = np.zeros((z1 - z0, x1 - x0), bool)
        for (x, z, surface, _floor), r in zip(pts, reach_of):
            if r["water_body"]:
                continue
            hw = r["width"] / 2.0
            rr = int(math.ceil(hw)) + RIVER_BANK + 1
            ax0, ax1 = max(x0, int(x) - rr), min(x1, int(x) + rr + 2)
            az0, az1 = max(z0, int(z) - rr), min(z1, int(z) + rr + 2)
            zz, xx = np.mgrid[az0:az1, ax0:ax1]
            dist = np.hypot(xx - x, zz - z).astype(np.float32)
            sub = (slice(az0 - z0, az1 - z0), slice(ax0 - x0, ax1 - x0))
            wet = (dist <= hw) & (dist < best[sub])
            best[sub] = np.where(wet, dist, best[sub])
            level[sub] = np.where(wet, int(math.floor(surface + 0.01)), level[sub])   # 76.999 interpolated is 77
            bedmap[sub] = np.where(wet, TERRAIN_CODES[r["bed"]], bedmap[sub])
            bank[sub] |= (dist > hw) & (dist <= hw + RIVER_BANK)
            if r["bed"] == "GRAVEL":
                bedmap[sub] = np.where((dist > hw) & (dist <= hw + RIVER_BANK) & (bedmap[sub] == 0),
                                       TERRAIN_CODES["GRAVEL"], bedmap[sub])
        h = heights[z0:z1, x0:x1]
        water = (level > 0) & (h < level)
        level = np.where(water, level, 0).astype(np.uint8)
        region = (slice(z0, z1), slice(x0, x1))
        bed_or_bank = (level > 0) | bank
        codes = np.where(bedmap > 0, bedmap, TERRAIN_CODES["SAND"]).astype(np.uint8)
        t = terr[region]
        t[bed_or_bank] = codes[bed_or_bank]
        b = biome[region]
        is_cold = np.isin(b, cold)
        b[bed_or_bank] = np.where(is_cold[bed_or_bank], WP_BIOMES["minecraft:frozen_river"], WP_BIOMES["minecraft:river"])
        for k in trees:
            trees[k][region][bed_or_bank] = 0
        for k in plants:
            plants[k][region][level > 0] = False
        frost[region][level > 0] = False
        name = "river_%s.png" % c["id"]
        Image.fromarray(level).save(out / name)
        cols = int((level > 0).sum())
        manifest.append({"name": c["id"], "levels": name, "x": x0, "z": z0, "columns": cols,
                         "min_level": int(level[level > 0].min()) if cols else None,
                         "max_level": int(level.max()) if cols else None})
    return manifest


def settlement_clearance(towns_path, margin):
    """True inside every settlement footprint plus margin blocks."""
    mask = np.zeros((N, N), bool)
    if not towns_path or not Path(towns_path).exists():
        return mask
    doc = json.loads(Path(towns_path).read_text(encoding="utf-8"))
    for t in doc.get("towns") or []:
        if t.get("kind") == "landmark_tree":
            continue            # its glade (data/foliage.json glade_radius) is the clearance
        fp = t.get("footprint") or {}
        if all(k in fp and fp[k] is not None for k in ("min_x", "min_z", "max_x", "max_z")):
            x0, z0 = max(0, int(fp["min_x"]) - margin), max(0, int(fp["min_z"]) - margin)
            x1, z1 = min(N, int(fp["max_x"]) + margin + 1), min(N, int(fp["max_z"]) + margin + 1)
            mask[z0:z1, x0:x1] = True
    return mask


def route_lanes(routes_path, clearance):
    """True within clearance blocks of every route's stored centreline (data/routes.json corridor.polyline). Foliage
    overlays keep their ground contact (prop roots, knees, tangles) off it, so a dense overlay never walls a route."""
    if not routes_path or not Path(routes_path).exists():
        raise SystemExit("foliage overlays keep %d blocks off the routes, but the routes file %r is absent"
                         % (clearance, routes_path))
    doc = json.loads(Path(routes_path).read_text(encoding="utf-8"))
    img = Image.new("L", (N, N), 0)
    d = ImageDraw.Draw(img)
    for r in doc.get("routes") or []:
        pts = [(float(p["x"]), float(p["z"])) for p in ((r.get("corridor") or {}).get("polyline") or [])]
        if len(pts) >= 2:
            d.line(pts, fill=1, width=2 * clearance + 1, joint="curve")
        for x, z in pts:
            d.ellipse((x - clearance, z - clearance, x + clearance, z + clearance), fill=1)
    return np.asarray(img).astype(bool)


def paint_foliage(a, out, heights, slope, idx, subs, presets, biome, terr, plants, speck, nz, allowed, lake_depth, water, land):
    import foliage as F
    doc = json.loads(Path(a.foliage).read_text(encoding="utf-8"))
    library = json.loads(Path(a.library).read_text(encoding="utf-8"))
    lib_dir = Path(a.library).parent
    excl = settlement_clearance(a.towns, doc["density_model"]["settlement_clearance_blocks"])
    # water clearance at block scale: no ground contact within water_clearance_blocks of any water
    from PIL import ImageFilter
    c = int(doc["density_model"]["water_clearance_blocks"])
    near_water = np.asarray(Image.fromarray(water.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * c + 1))) > 0
    allowed = allowed & ~near_water
    layers, lane = F.overlay_layers(doc)
    paths = route_lanes(getattr(a, "routes", None), lane) if layers and lane > 0 else None
    res = F.place(doc, library, subs, presets, idx, heights, slope, allowed, lake_depth, water, excl, a.seed, paths=paths)
    G = F.G

    def up(grid):
        return np.repeat(np.repeat(grid, G, axis=0), G, axis=1)

    # forest types, then overlays (floor and understory only: an overlay never paints a biome)
    covers = [(doc["types"][t], res["fields"][t]) for t in res["type_ids"]]
    covers += [(next(lay for lay in layers if lay["id"] == oid), res["overlay_fields"][oid])
               for oid in res.get("overlay_ids", [])]
    for spec, f in covers:
        z0, z1, x0, x1 = f["box"]
        bz0, bz1, bx0, bx1 = z0 * G, min(N, z1 * G), x0 * G, min(N, x1 * G)
        view = (slice(bz0, bz1), slice(bx0, bx1))
        hh, ww = bz1 - bz0, bx1 - bx0
        mask = up(f["mask"])[:hh, :ww] & land[view] & ~water[view]
        inside = up(f["inside"])[:hh, :ww]
        core = up(f["core"])[:hh, :ww]
        if spec.get("biome"):
            biome[view][mask] = WP_BIOMES[spec["biome"]]
        fl = spec.get("floor")
        if fl:
            tv = terr[view]
            sel = inside & (core >= fl["threshold"]) & np.isin(tv, [TERRAIN_CODES[k] for k in ("GRASS", "BARE_GRASS", "PODZOL")])
            pick = nz(24, 601)[view]
            lo = 0.0
            for i_, (name, share) in enumerate(fl["mix"]):
                last = i_ == len(fl["mix"]) - 1
                s = sel & (pick >= lo) & ((pick <= 1.0) if last else (pick < lo + share))
                tv[s] = TERRAIN_CODES[name]
                lo += share
        sp = speck[view]
        for zone, zspec in (spec.get("understory") or {}).items():
            zlo, zhi = ZONES[zone]
            zm = inside & (core > zlo) & (core <= zhi) & land[view] & ~water[view]
            if zspec.get("clear"):
                for k in plants:
                    plants[k][view][zm] = False
            plants[zspec["set"]][view][zm & (sp < zspec["coverage"])] = True

    by_group = {r["group"]: [] for r in library["objects"]}
    for r in library["objects"]:
        by_group[r["group"]].append(r)
    debris_offset = {}
    for spec in doc["types"].values():
        for db in spec.get("debris") or []:
            if db.get("vertical_offset"):
                debris_offset[db["group"]] = db["vertical_offset"]
    manifest = []
    for g, pts in sorted(res["positions"].items()):
        if not pts:
            continue
        if g not in by_group:
            raise SystemExit("foliage group %s has no objects in %s" % (g, a.library))
        m = np.zeros((N, N), np.uint8)
        arr = np.array(pts)
        m[arr[:, 1], arr[:, 0]] = 15
        name = "objects_%s.png" % g
        Image.fromarray(m).save(out / name)
        settings = OBJECT_SETTINGS.get(g, {})
        objs = [{"file": str((lib_dir / r["file"]).resolve()), "frequency": 1,
                 "offset": [-r["origin"][0], -r["origin"][2], -r["origin"][1]],
                 "extend_foundation": settings.get("extend_foundation", True),
                 "vertical_offset": debris_offset.get(g, 0)} for r in by_group[g]]
        manifest.append({"layer": g, "map": name, "count": len(pts), "objects": objs})
    np.savez_compressed(out / "canopy.npz", canopy=res["canopy"], grid_blocks=G)
    stats = {"types": res["stats"], "objects": {e["layer"]: e["count"] for e in manifest},
             "total_objects": int(sum(e["count"] for e in manifest))}
    if res.get("overlay_stats"):
        stats["overlays"] = res["overlay_stats"]
    if res.get("by_subregion"):
        stats["by_subregion"] = res["by_subregion"]
    return manifest, stats


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--regions", default=str(ROOT / "data" / "regions.json"))
    p.add_argument("--landmarks", default=str(ROOT / "data" / "landmarks.json"))
    p.add_argument("--seed", type=int, default=20260914, help="noise seed, so repaints are repeatable")
    p.add_argument("--rivers", default=str(ROOT / "data" / "rivers.json"),
                   help="graded rivers (tools/grade_rivers.py); '' to paint none")
    p.add_argument("--foliage", default=str(ROOT / "data" / "foliage.json"), help="forest types; '' to place no trees")
    p.add_argument("--library", default=str(ROOT / "kits" / "structures" / "foliage" / "library.json"))
    p.add_argument("--towns", default=str(ROOT / "data" / "towns.json"), help="settlement footprints kept clear of trees")
    p.add_argument("--routes", default=str(ROOT / "data" / "routes.json"),
                   help="route centrelines foliage overlays keep clear of (data/foliage.json overlays.path_clearance_blocks)")
    p.add_argument("--coast-class", default=str(ROOT / "build" / "sculpt" / "coast_class.png"),
                   help="coast classes from tools/sculpt.py apply; '' for the uniform beach rule")
    a = p.parse_args(argv)
    out = Path(a.out) if a.out else ROOT / "build" / "paint"
    out.mkdir(parents=True, exist_ok=True)

    heights, world = T.load_from_args(a)
    sea_level = T.sea_level(world)
    regions = json.loads(Path(a.regions).read_text(encoding="utf-8"))
    landmarks = json.loads(Path(a.landmarks).read_text(encoding="utf-8"))
    presets = regions["paint_presets"]
    subs = regions["subregions"]
    for s in subs:
        if s["paint"]["preset"] not in presets:
            raise SystemExit("sub-region %s uses unknown preset %s" % (s["id"], s["paint"]["preset"]))

    slope = T.slope_degrees(heights).astype(np.float32)
    land = heights >= sea_level
    idx = fill_gaps(rasterise_subregions(subs), land)
    print("sub-regions rasterised; unassigned land %.3f%%" % (100.0 * (land & (idx == 0)).mean()))

    noise = {}

    def nz(scale, salt):
        key = (scale, salt)
        if key not in noise:
            noise[key] = value_noise(scale, a.seed + salt)
        return noise[key]

    biome = np.full((N, N), 255, np.uint8)
    terr = np.zeros((N, N), np.uint8)
    trees = {k: np.ones((N, N), np.uint8) for k in TREE_LAYERS}
    plants = {k: np.zeros((N, N), bool) for k in PLANT_SETS}
    frost = np.zeros((N, N), bool)
    rng = np.random.default_rng(a.seed)
    speck = rng.random((N, N), dtype=np.float32)
    jitter = (nz(48, 7) - 0.5) * 16.0     # blocks of wobble on elevation bands, so lines are not contours

    for i, s in enumerate(subs, start=1):
        m = idx == i
        if not m.any():
            continue
        pr = dict(presets[s["paint"]["preset"]], **(s["paint"].get("override") or {}))
        h = heights[m] + jitter[m]
        # biome
        if "biome_bands" in pr:
            b = np.full(h.shape, WP_BIOMES[pr["biome_bands"][-1][1]], np.uint8)
            for top, name in reversed(pr["biome_bands"][:-1]):
                b[h < top] = WP_BIOMES[name]
            biome[m] = b
        else:
            biome[m] = WP_BIOMES[pr["biome"]]
        # terrain
        t = np.full(h.shape, TERRAIN_CODES[pr.get("terrain", "GRASS")], np.uint8)
        for patch in pr.get("patches") or []:
            sel = nz(patch.get("scale", 64), 11 + TERRAIN_CODES[patch["terrain"]])[m] < patch["coverage"]
            t[sel] = TERRAIN_CODES[patch["terrain"]]
        for lo, name in pr.get("terrain_above") or []:
            t[h >= lo] = TERRAIN_CODES[name]
        for hi_, name in pr.get("terrain_below") or []:
            t[h < hi_] = TERRAIN_CODES[name]
        # scree: loose rock on the band of slope just below where the ground turns to bare rock
        sc = pr.get("scree")
        if sc:
            sm_ = slope[m]
            sel = (sm_ >= sc["slope_deg"][0]) & (sm_ < sc["slope_deg"][1]) & (nz(24, 29)[m] < sc.get("coverage", 0.7))
            t[sel] = TERRAIN_CODES[sc["terrain"]]
        steep = pr.get("rock_slope_deg", 38)
        if steep:
            t[slope[m] >= steep] = TERRAIN_CODES[pr.get("rock", "STONE_MIX")]
        terr[m] = t
        # trees: none on cliffs or above the treeline; where they stand is tools/foliage.py's decision
        blocked = slope[m] > 40
        if pr.get("treeline_y") is not None:
            blocked |= (heights[m] + jitter[m]) > pr["treeline_y"]
        for k in trees:
            layer = trees[k]
            layer[m] = np.where(blocked, 0, layer[m])
        # plants
        for pl in pr.get("plants") or []:
            salt = 307 + sorted(PLANT_SETS).index(pl["set"])
            cov = pl["coverage"] * (0.35 + 1.3 * nz(pl.get("scale", 64), salt)[m])
            sel = speck[m] < cov
            cur = plants[pl["set"]]
            cur[m] = cur[m] | sel
        # frost
        if pr.get("frost"):
            frost[m] = True
        elif pr.get("frost_above_y") is not None:
            frost[m] = h >= pr["frost_above_y"]

    # sea biomes by depth and latitude, beaches on the shore
    sea = ~land
    zz = np.arange(N, dtype=np.float32)[:, None] + (nz(512, 9) - 0.5) * 600
    deep = heights < 34
    sea_biome = np.where(zz < 1800, np.where(deep, 50, 10), np.where(zz < 3800, np.where(deep, 49, 46),
                         np.where(zz < 6200, np.where(deep, 24, 0), np.where(deep, 48, 44)))).astype(np.uint8)
    biome[sea] = sea_biome[sea]
    shore = land & (heights < sea_level + 3) & (slope < 20)
    cold = np.isin(biome, [WP_BIOMES[b] for b in ("minecraft:snowy_taiga", "minecraft:snowy_plains", "minecraft:grove",
                                                   "minecraft:snowy_slopes", "minecraft:frozen_peaks", "minecraft:jagged_peaks")])
    # sea columns carry ocean biomes, so a cold coast's shallows follow the land: cold within about 96 blocks of
    # cold land (a graded beach shelf reaches 7 deep some 70-80 blocks out)
    cg = cold[::8, ::8].copy()
    for _ in range(12):
        g2 = cg.copy()
        g2[1:, :] |= cg[:-1, :]; g2[:-1, :] |= cg[1:, :]; g2[:, 1:] |= cg[:, :-1]; g2[:, :-1] |= cg[:, 1:]
        cg = g2
    cold_near = np.repeat(np.repeat(cg, 8, 0), 8, 1)[:cold.shape[0], :cold.shape[1]]
    cold = cold | (sea & cold_near)
    arid = np.isin(terr, [TERRAIN_CODES[k] for k in ("DESERT", "RED_DESERT", "MESA", "RED_SAND", "SAND",
                                                   "SANDSTONE")])
    coast_class = None
    if a.coast_class and Path(a.coast_class).exists():
        coast_class = np.asarray(Image.open(a.coast_class))
        record = Path(a.coast_class).with_suffix(".json")
        if record.exists():
            made_for = json.loads(record.read_text(encoding="utf-8")).get("heightmap_sha256")
            # A coast map built for the heightmap the imported one was RESCALED from is still correct. The rescale
            # (tools/rescale.py) is the identity at or below y145 -- measured, 0 of 62,789,211 columns there change
            # integer elevation -- and every coast class lives a few blocks either side of sea level, far below it.
            # Anything else is genuinely stale and still refused.
            parent = (world["heightmap"].get("rescaled_from") or {}).get("sha256")
            if made_for != world["heightmap"]["sha256"] and made_for != parent:
                raise SystemExit("coast class map %s was made for heightmap %s, not the imported %s: re-run sculpt.py apply"
                                 % (a.coast_class, str(made_for)[:12], world["heightmap"]["sha256"][:12]))
        if coast_class.shape != (N, N):
            raise SystemExit("coast class map %s is %s, not %dx%d" % (a.coast_class, coast_class.shape, N, N))
    if coast_class is None:
        terr[shore & ~cold & ~arid] = TERRAIN_CODES["BEACHES"]
        terr[shore & cold] = TERRAIN_CODES["GRAVEL"]
    else:
        # shore materials by coast class (tools/sculpt.py): the grade was fixed first, so sand only lies where a
        # beach has width; codes 1 beach, 2 estuary, 3 grassy shore, 4 rocky, 5 cliff, 0 outside the coastal band
        def paint(cls, sel, name, cold_name=None):
            s = (coast_class == cls) & sel
            if cold_name:
                terr[s & cold] = TERRAIN_CODES[cold_name]
                s = s & ~cold
            terr[s] = TERRAIN_CODES[name]
        shallow = sea & (heights >= sea_level - 7)
        pn = nz(32, 41)
        paint(1, land & (heights < sea_level + 5.5) & (slope < 16), "BEACHES", "GRAVEL")
        paint(1, shallow, "SAND", "GRAVEL")
        paint(2, land & (heights < sea_level + 3) & (slope < 10) & (pn >= 0.3), "MUD")
        paint(2, land & (heights < sea_level + 3) & (slope < 10) & (pn < 0.3), "CLAY")
        paint(2, sea & (heights >= sea_level - 4), "MUD")
        paint(3, land & (heights < sea_level + 1.2) & (slope < 12), "GRAVEL")
        paint(3, shallow, "GRAVEL")
        paint(4, land & (heights < sea_level + 7) & (pn >= 0.35), "STONE_MIX")
        paint(4, land & (heights < sea_level + 7) & (pn < 0.35), "GRAVEL")
        paint(4, sea & (heights >= sea_level - 9), "GRAVEL")
        paint(5, land & (heights < sea_level + 4) & (slope < 30), "GRAVEL")
        paint(5, sea & (heights >= sea_level - 12), "STONE_MIX")
        outside = coast_class == 0
        terr[shore & outside & ~cold & ~arid] = TERRAIN_CODES["BEACHES"]
        terr[shore & outside & cold] = TERRAIN_CODES["GRAVEL"]
        shore = shore | (land & np.isin(coast_class, [1, 2]) & (heights < sea_level + 5.5) & (slope < 16))
    # polygons are simplified, so they overhang the coast: nothing grows or freezes on the sea
    for k in trees:
        trees[k][shore | sea] = 0
    for k in plants:
        plants[k][sea] = False
    frost[sea] = False

    # lakes above sea level: raise water inside each basin; beds and banks become sand, gravel or clay
    manifest_water = []
    lake_depth = np.zeros((N, N), np.float32)
    for lm in landmarks["landmarks"]:
        wb = lm.get("water_body")
        if not wb:
            continue
        level = wb["level_y"]
        bimg = Image.new("L", (N, N), 0)
        dd = ImageDraw.Draw(bimg)
        for ring in wb["basin_polygons"]:
            dd.polygon([tuple(q) for q in ring], fill=1)
        basin = np.asarray(bimg).astype(bool)
        wet = basin & (heights < level)
        if not wet.any():
            continue
        zs, xs = np.nonzero(basin)
        x0, x1, z0, z1 = int(xs.min()), int(xs.max()) + 1, int(zs.min()), int(zs.max()) + 1
        name = "water_%s.png" % lm["id"]
        Image.fromarray(basin[z0:z1, x0:x1].astype(np.uint8)).save(out / name)
        manifest_water.append({"name": lm["id"], "level": int(level), "x": x0, "z": z0, "mask": name})
        bed = np.where(nz(40, 17) > 0.5, TERRAIN_CODES["GRAVEL"], TERRAIN_CODES["CLAY"]).astype(np.uint8)
        terr[wet] = bed[wet]
        lake_depth[wet] = np.maximum(lake_depth[wet], level - heights[wet])
        bank = basin & ~wet & (heights < level + 2)
        terr[bank] = TERRAIN_CODES["SAND"]
        for k in trees:
            trees[k][basin & (heights < level + 2)] = 0
        for k in plants:
            plants[k][wet] = False
        frost[wet] = False

    # dry ravines (carves that cannot hold a river): gravel floors, no trees on the floor
    cimg = Image.new("L", (N, N), 0)
    cd = ImageDraw.Draw(cimg)
    for lm in landmarks["landmarks"]:
        if lm.get("kind") != "ravine":
            continue
        for ax in lm.get("axes") or []:
            cd.line([tuple(q) for q in ax["polyline"]], fill=1, width=10)
    creek = np.asarray(cimg).astype(bool) & land
    terr[creek] = TERRAIN_CODES["GRAVEL"]
    for k in trees:
        trees[k][creek] = 0

    # graded rivers: water at each station's stored surface, bed material by reach, banks, river biome
    manifest_rivers = paint_rivers(a.rivers, heights, biome, terr, trees, plants, frost, out) if a.rivers else []

    # forests: exact object positions, floor, understory and biome by forest type
    manifest_objects, foliage_stats = [], {}
    if a.foliage:
        water = sea | (lake_depth > 0)
        for w in manifest_rivers:
            lv = np.asarray(Image.open(out / w["levels"])).astype(np.float32)
            h_, w_ = lv.shape
            sub = heights[w["z"]:w["z"] + h_, w["x"]:w["x"] + w_]
            water[w["z"]:w["z"] + h_, w["x"]:w["x"] + w_] |= (lv > 0) & (lv > sub)
        manifest_objects, foliage_stats = paint_foliage(a, out, heights, slope, idx, subs, presets, biome, terr,
                                                        plants, speck, nz, trees["allowed"] > 0, lake_depth, water, land)

    Image.fromarray(biome).save(out / "biomes.png")
    Image.fromarray(terr).save(out / "terrain.png")
    for k, v in plants.items():
        Image.fromarray(v.astype(np.uint8)).save(out / ("plants_%s.png" % k))
    Image.fromarray(frost.astype(np.uint8)).save(out / "frost.png")
    manifest = {
        "biomes": "biomes.png", "terrain": "terrain.png",
        "terrain_codes": {str(v): k for k, v in TERRAIN_CODES.items()},
        "objects": manifest_objects,
        "plants": [{"name": "cobblers_%s" % k, "map": "plants_%s.png" % k, "plants": PLANT_SETS[k]} for k in PLANT_SETS if plants[k].any()],
        "frost": "frost.png", "water": manifest_water + manifest_rivers,
        "source": {"regions": str(a.regions), "landmarks": str(a.landmarks), "heightmap_sha256": world["heightmap"]["sha256"], "seed": a.seed},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    used = sorted({name for name, bid in WP_BIOMES.items() if (biome == bid).any()})
    stats = {"biomes_used": used,
             "tree_allowed_pct": round(100.0 * (trees["allowed"] > 0).mean(), 2),
             "foliage": foliage_stats,
             "frost_pct": round(100.0 * frost.mean(), 2), "lakes": [w["name"] for w in manifest_water],
             "rivers": {w["name"]: {"water_columns": w["columns"], "levels": [w["min_level"], w["max_level"]]}
                        for w in manifest_rivers}}
    (out / "stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
