#!/usr/bin/env python
"""Elder trees: a few emergent giants in every wood, one tier below the five hand-sited landmarks.

The landmark trees are ceremonies. Each one was placed for what it is seen from, given its own glade, and there
are five of them on 60 km2. This is the other half of the same idea at a tenth of the ceremony: 2 to 4 elders in
each forested sub-region, so that a wood has something older than its canopy somewhere inside it, and none of
them pretends to be the tree of the map.

An elder (the `elder` tier in tools/tree_grove.py) is 81 blocks tall on a 7x7 trunk, crown radius 19, about 20k
blocks: roughly twice a mega spruce and half a landmark. The foliage types it stands in carry 30-190 stems per
hectare and top out around 20-50 blocks, so an elder clears its own canopy by 30-plus and reads as emergent from
outside the wood. That only works if the ground holds it, so every site is measured:

  pad       9x9 (the 7x7 trunk plus a block of margin), relief at most 2.0 blocks, measured on the heightmap's
            ground, rounded (tools/ground.py), never on a world, which holds whatever was built into it last. The
            trunk is a solid column: on a sloped seat it either floats on the low side or buries its first storey
  dry       no water within 24 blocks of the trunk centre. The root flare reaches 13 and the crown 19; a trunk
            on a bank looks placed, a trunk in a pond looks like a mistake
  spacing   220 blocks between elders and from the landmark tree sites, and clear of every landmark's declared
            glade_radius + 80. Two emergents in one sightline cancel each other out
  path      at least 60 blocks from a routed leg centreline - crown radius 19 plus limb reach 17 is 36, so 60
            keeps the canopy off the path entirely - and at least 120 from any town centre, but within 600 of
            some leg, which is about a minute off-route: findable by curiosity, not by a marker
  inside    48 blocks inside both the sub-region polygon and its measured bounds, so a wood's elders are in the
            wood and not on the seam with its neighbour

Counts scale with area at roughly one per 0.35 km2 and clamp to [2, 4]: the smallest included wood is 0.28 km2
(wedge_north) and the largest 1.94 (foothill_woods), which without the clamp would be 1 and 6.

Sites are picked by farthest-point sampling over a 16-block grid of cells that pass everything, then nudged up
to 8 blocks onto the flattest pad that still passes. Rotation per tree comes from a seeded RNG so the same
three prefabs per species do not read as three prefabs.

  python tools/elder_trees.py --source-root <root>
  writes kits/structures/prefabs/trees/tree_town/elder_<species>_<a|b|c>.nbt (+ .json),
  derived/sites/elder_trees.json and build/elders/elders.mcfunction (not run)
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import terrain as T
from landmark_trees import _rng
from place_town import rotate
from tree_grove import TIERS, big_tree, write_prefab
import function_limits

ROOT = Path(__file__).resolve().parent.parent
TIER = "elder"
GRID = 16                    # coarse search step; the pad is 9 wide, so 16 samples every distinct seat once
NUDGE, NUDGE_STEP = 8, 2     # refinement box around a chosen cell
PAD = 4                      # half-width of the 9x9 pad: trunk 7x7 (-3..+3) plus a block of margin
PAD_RELIEF = 2.0
DRY = 24                     # no water within this of the trunk centre
SPACING = 220                # between elders, and from a landmark tree site
GLADE_CLEAR = 80             # extra margin outside a landmark's own glade_radius
OFF_TOWN, OFF_LEG, NEAR_LEG = 120, 60, 600
INSET = 48
PER_KM2, MIN_N, MAX_N = 1 / 0.35, 2, 4
ROTATIONS = ("none", "clockwise_90", "180", "counterclockwise_90")

# Foliage types that are woodland rather than scatter. Everything else in data/foliage.json is either named for
# what it is not (scatter, scrub, heath, lone, snags) or plants under 25 stems per hectare, which is a tree every
# 20 blocks or sparser: an 81-block emergent over that is a monument in a field, not the oldest tree in a wood.
NOT_WOODLAND = {"treeline_scatter", "krummholz", "heath_scrub", "open_lone", "savanna_lone", "badlands_scrub",
                "rift_scatter", "scorched_snags", "islet_trees", "snag_fen", "spruce_heath", "oak_parkland"}
MIN_STEMS = 25
# Log kind per foliage type, read off the type's own `classes` in data/foliage.json (what it actually plants).
# acacia is unused: every acacia type (savanna_lone, scorched_snags) is scatter and excluded.
SPECIES = {
    "old_growth_spruce": "spruce",   # ancient_spruce / mega_spruce
    "spruce_thicket": "spruce",
    "coastal_spruce": "spruce",
    "snow_pine": "spruce",           # pine is a spruce log in Minecraft terms
    "birch_plateau": "birch",        # tall_birch / birch over fancy_oak
    "birch_shore": "birch",
    "foothill_mixed": "oak",         # fancy_oak leads, oak and birch under it
    "riparian_woods": "oak",
    "lakeside_copses": "oak",
    "broken_oakwood": "dark_oak",    # matches tree_grove.SPECIES
    "dark_wood": "dark_oak",
    "mossy_broadleaf": "dark_oak",   # fancy_oak and dark_oak over moss
    "drowned_swamp": "mangrove",     # swamp_oak
    "cherry_vale": "cherry",
    "emergent_jungle": "jungle",     # mega_jungle: the type is named for this tree
    "jungle_edge": "jungle",
}


def seg_distance(px, pz, a, ab, ab2):
    """Distance from a point to the nearest of a precomputed set of segments (all legs concatenated)."""
    t = np.clip(((px - a[:, 0]) * ab[:, 0] + (pz - a[:, 1]) * ab[:, 1]) / ab2, 0, 1)
    q = a + ab * t[:, None]
    return float(np.min(np.hypot(q[:, 0] - px, q[:, 1] - pz)))


def footprint(px, pz, sx, sz, rot):
    """World x/z box a template occupies. Rotation moves the far corner, so this is not simply px..px+sx."""
    pts = [rotate(dx, dz, rot) for dx in (0, sx - 1) for dz in (0, sz - 1)]
    xs = [px + q[0] for q in pts]
    zs = [pz + q[1] for q in pts]
    return min(xs), min(zs), max(xs), max(zs)


def foliage_of(sub, foliage):
    """Assigned type first, the terrain preset's default second: `assign` covers 12 of 62 sub-regions."""
    if sub["id"] in foliage["assign"]:
        return foliage["assign"][sub["id"]]["type"]
    return foliage["preset_defaults"].get((sub.get("paint") or {}).get("preset"))


def classify(subs, foliage):
    """-> (included rows, excluded rows). One decision per sub-region, each with the number behind it."""
    inc, exc = [], []
    for sub in sorted(subs, key=lambda s: s["id"]):
        ftype = foliage_of(sub, foliage)
        stems = float((foliage["types"].get(ftype) or {}).get("stems_per_ha", 0)) if ftype else 0.0
        km2 = float(sub["measured"]["area_km2"])
        row = {"id": sub["id"], "foliage": ftype, "stems_per_ha": stems, "area_km2": km2}
        if not ftype:
            row["why"] = "preset %r has no foliage type" % (sub.get("paint") or {}).get("preset")
            exc.append(row)
        elif ftype in NOT_WOODLAND:
            row["why"] = "%s is scatter/scrub, not woodland" % ftype
            exc.append(row)
        elif stems < MIN_STEMS:
            row["why"] = "%s carries %.3g stems/ha, under %d" % (ftype, stems, MIN_STEMS)
            exc.append(row)
        else:
            row["species"] = SPECIES[ftype]
            row["want"] = int(min(MAX_N, max(MIN_N, round(km2 * PER_KM2))))
            inc.append(row)
    return inc, exc


def region_mask(sub, x0, z0, w, h):
    """The sub-region's own polygons rasterised at 1 block per cell inside the extract window."""
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    for ring in sub["polygons"]:
        d.polygon([(x - x0, z - z0) for x, z in ring], fill=1)
    return np.asarray(img).astype(bool)


def painted_water(heights, world):
    """Sea plus every painted lake and river course (build/paint), as tools/tree_grove.py builds it."""
    man = json.loads((ROOT / "build" / "paint" / "manifest.json").read_text(encoding="utf-8"))
    wet = heights <= T.sea_level(world)
    for w in man["water"]:
        key = "levels" if "levels" in w else "mask"
        m = np.asarray(Image.open(ROOT / "build" / "paint" / w[key])) > 0
        wet[w["z"]:w["z"] + m.shape[0], w["x"]:w["x"] + m.shape[1]] |= m
    return wet


def pick(row, sub, ground, wet, inside, x0, z0, chosen, fixed, segs, towns, glades, relax):
    """Farthest-point sampling over the passing cells of one sub-region, then a nudge onto the flattest pad.

    `chosen` is every elder placed so far (all regions), `fixed` the landmark tree sites: the 220-block rule is
    global, so a wood next to a landmark gets fewer usable cells than one in the middle of nowhere.
    """
    b = sub["measured"]["bounds"]
    a, ab, ab2 = segs

    def test(x, z):
        """-> (relief, ground_y, dleg) if the cell passes every rule, else None."""
        if not (b["min_x"] + INSET <= x <= b["max_x"] - INSET and b["min_z"] + INSET <= z <= b["max_z"] - INSET):
            return None
        lx, lz = x - x0, z - z0
        if not inside[lz - INSET:lz + INSET + 1, lx - INSET:lx + INSET + 1].all():
            return None                                       # 48 blocks inside the polygon, not just its box
        if wet[lz - DRY:lz + DRY + 1, lx - DRY:lx + DRY + 1].any():
            return None
        pad = ground[lz - PAD:lz + PAD + 1, lx - PAD:lx + PAD + 1]
        if pad.min() <= -30000:                               # a column the export never wrote
            return None
        relief = float(pad.max() - pad.min())
        if relief > PAD_RELIEF:
            return None
        if any(math.hypot(tx - x, tz - z) < OFF_TOWN for tx, tz in towns):
            return None
        for gx, gz, gr in glades:
            if math.hypot(gx - x, gz - z) < gr + GLADE_CLEAR:
                return None
        if any(math.hypot(px - x, pz - z) < SPACING for px, pz in fixed):
            return None
        dleg = seg_distance(x, z, a, ab, ab2)
        if dleg < OFF_LEG or (dleg > NEAR_LEG and not relax["far_from_legs"]):
            return None
        return relief, int(ground[lz, lx]), dleg

    def sweep():
        out = []
        for z in range(b["min_z"] + INSET, b["max_z"] - INSET + 1, GRID):
            for x in range(b["min_x"] + INSET, b["max_x"] - INSET + 1, GRID):
                r = test(x, z)
                if r is not None:
                    out.append((x, z) + r)
        return out

    cands = sweep()
    if not cands:
        relax["far_from_legs"] = True                          # maybe this wood simply has no leg within 600
        cands = sweep()
        if not cands:
            relax["far_from_legs"] = False                     # it was something else; do not claim a relaxation

    out = []
    free = [c for c in cands if all(math.hypot(c[0] - p[0], c[1] - p[1]) >= SPACING for p in chosen)]
    while len(out) < row["want"] and free:
        ref = chosen + fixed + [(s["x"], s["z"]) for s in out]
        # farthest-point: take the cell with the largest distance to anything already standing
        best = max(free, key=lambda c: min((math.hypot(c[0] - p[0], c[1] - p[1]) for p in ref), default=1e9))
        # nudge onto the flattest pad within NUDGE that still passes everything, including the new neighbours
        seat = (best[2], best[0], best[1], best[3], best[4])
        for dz in range(-NUDGE, NUDGE + 1, NUDGE_STEP):
            for dx in range(-NUDGE, NUDGE + 1, NUDGE_STEP):
                r = test(best[0] + dx, best[1] + dz)
                if r is None or r[0] >= seat[0]:
                    continue
                if any(math.hypot(best[0] + dx - s["x"], best[1] + dz - s["z"]) < SPACING for s in out):
                    continue
                seat = (r[0], best[0] + dx, best[1] + dz, r[1], r[2])
        out.append({"x": seat[1], "z": seat[2], "ground_y": seat[3], "pad_relief": round(seat[0], 1),
                    "distance_to_nearest_leg": round(seat[4])})
        free = [c for c in free if math.hypot(c[0] - seat[1], c[1] - seat[2]) >= SPACING]
    return out, len(cands)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--surface-world", default=None, help=argparse.SUPPRESS)
    p.add_argument("--function", default=str(ROOT / "build" / "elders" / "elders.mcfunction"))
    a = p.parse_args(argv)
    if a.surface_world:
        # This tool used to require a world, on the grounds that pads were measured on the ground the
        # world has rather than the heightmap. The canonical heightmap carries the pads now
        # (land_8k_16_rescaled_b145_pads.png), and round(h) matches a fresh export at 99.85% of columns
        # (tools/ground.py), so the world is no longer needed and is no longer safe: it holds what was
        # built into it last.
        raise SystemExit("--surface-world is gone: trunks are seated on the heightmap's ground (tools/ground.py)")
    heights, world = T.load_from_args(a)
    n = heights.shape[0]
    import ground as G
    ground_of = G.load(a.source_root) if a.source_root else G.load()

    subs = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["subregions"]
    foliage = json.loads((ROOT / "data" / "foliage.json").read_text(encoding="utf-8"))
    towns_doc = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    legs = json.loads((ROOT / "derived" / "routes" / "critical_legs.json").read_text(encoding="utf-8"))["legs"]
    towns = [(t["centre"]["x"], t["centre"]["z"]) for t in towns_doc if (t.get("centre") or {}).get("x") is not None]
    glades = [(t["site"][0], t["site"][1], t["glade_radius"]) for t in foliage["landmark_trees"]]
    fixed = [(g[0], g[1]) for g in glades]
    pts = np.concatenate([np.asarray(l["polyline"], float) for l in legs])
    breaks = np.cumsum([len(l["polyline"]) for l in legs])[:-1]      # do not join the end of one leg to the next
    keep = np.ones(len(pts) - 1, bool)
    keep[breaks - 1] = False
    seg_a, seg_b = pts[:-1][keep], pts[1:][keep]
    segs = (seg_a, seg_b - seg_a, np.maximum(((seg_b - seg_a) ** 2).sum(1), 1e-9))

    included, excluded = classify(subs, foliage)
    sea_wet = painted_water(heights, world)
    by_id = {s["id"]: s for s in subs}

    written, regions, chosen, notes = {}, [], [], []
    for row in included:
        sub = by_id[row["id"]]
        b = sub["measured"]["bounds"]
        m = DRY + PAD + NUDGE + 8                                    # window margin for every box test above
        x0, z0 = b["min_x"] - m, b["min_z"] - m
        x1, z1 = b["max_x"] + m, b["max_z"] + m
        cx0, cz0 = max(0, x0), max(0, z0)
        cx1, cz1 = min(n - 1, x1), min(n - 1, z1)
        ground = np.full((z1 - z0 + 1, x1 - x0 + 1), -64, dtype=int)
        ground[cz0 - z0:cz1 - z0 + 1, cx0 - x0:cx1 - x0 + 1] = ground_of.box(cx0, cz0, cx1, cz1)
        h, w = ground.shape
        # water from the painted water model only: the world's own water was read here too, and the world
        # holds whatever fluid a later build or a fluid clear put into it
        wet = np.zeros((h, w), bool)
        px0, pz0 = max(0, x0), max(0, z0)
        px1, pz1 = min(n, x1 + 1), min(n, z1 + 1)
        if px1 > px0 and pz1 > pz0:
            wet[pz0 - z0:pz1 - z0, px0 - x0:px1 - x0] |= sea_wet[pz0:pz1, px0:px1]
        inside = region_mask(sub, x0, z0, w, h)
        relax = {"far_from_legs": False}
        sites, n_cand = pick(row, sub, ground, wet, inside, x0, z0, chosen, fixed, segs, towns, glades, relax)
        if relax["far_from_legs"]:
            notes.append("%s: no cell within %d blocks of a routed leg; the near-leg rule was dropped for it"
                         % (row["id"], NEAR_LEG))
        if len(sites) < row["want"]:
            notes.append("%s: wanted %d, %d cells passed, placed %d (spacing %d is the binding rule)"
                         % (row["id"], row["want"], n_cand, len(sites), SPACING))
        kind = row["species"]
        variants = []
        for v in "abc":
            if (kind, v) not in written:
                bld, dims = big_tree(kind, v, TIER)
                written[(kind, v)] = write_prefab(kind, v, bld, dims, TIER)
            variants.append(written[(kind, v)])
        rng = _rng("elder_trees_%s" % row["id"])                     # seeded on the id: the same map every run
        for i, s in enumerate(sites):
            side = variants[i % 3]
            s["object"] = side["template_id"]
            s["rotation"] = ROTATIONS[int(rng.integers(4))]
            s["variant"] = side["name"][-1]
            chosen.append((s["x"], s["z"]))
        regions.append({"id": row["id"], "foliage": row["foliage"], "species": kind, "area_km2": row["area_km2"],
                        "stems_per_ha": row["stems_per_ha"], "wanted": row["want"], "placed": len(sites),
                        "passing_cells": n_cand, "relaxed": [k for k, v in relax.items() if v], "sites": sites})

    all_sites = [s for r in regions for s in r["sites"]]
    for s in all_sites:                       # nearest other elder or landmark tree, over the finished set
        others = [q for q in chosen + fixed if q != (s["x"], s["z"])]
        s["nearest_other"] = round(min(math.hypot(q[0] - s["x"], q[1] - s["z"]) for q in others))

    # placement: seat the trunk base one above the ground, forceload the whole rotated footprint, put it back
    R = TIERS[TIER]["trunk_r"]
    cmds = ["# elder trees: %d emergent giants over %d forested sub-regions (tools/elder_trees.py)"
            % (sum(len(r["sites"]) for r in regions), len(regions)),
            "# run once, on a server with no players near these columns; each tree is ~20k blocks"]
    for r in regions:
        cmds.append("# %s (%s, %s)" % (r["id"], r["foliage"], r["species"]))
        for s in r["sites"]:
            side = written[(r["species"], s["variant"])]
            ox, oy, oz = side["trunk_origin"]
            sx, _, sz = side["source"]["size"]
            qx, qz = rotate(ox + R, oz + R, s["rotation"])           # the trunk centre, wherever rotation put it
            px, pz = s["x"] - qx, s["z"] - qz
            lo_x, lo_z, hi_x, hi_z = footprint(px, pz, sx, sz, s["rotation"])
            cmds.append("forceload add %d %d %d %d" % (lo_x - 8, lo_z - 8, hi_x + 8, hi_z + 8))
            cmds.append("place template %s %d %d %d %s none 1.0 0"
                        % (side["template_id"], px, s["ground_y"] + 1 - oy, pz, s["rotation"]))
            cmds.append("forceload remove %d %d %d %d" % (lo_x - 8, lo_z - 8, hi_x + 8, hi_z + 8))

    fn = Path(a.function)
    fn.parent.mkdir(parents=True, exist_ok=True)
    fn.write_text("\n".join(function_limits.ensure_loaded(cmds)) + "\n", encoding="utf-8")
    spacings = [s["nearest_other"] for s in all_sites]
    doc = {"generator": "tools/elder_trees.py", "provenance": T.provenance(world, Path(a.world)),
           "ground_from": "heightmap, rounded (tools/ground.py)", "tier": TIER, "habitat": next(iter(written.values()))["habitat"],
           "rules": {"pad_blocks": 2 * PAD + 1, "pad_relief_max": PAD_RELIEF, "dry_radius": DRY,
                     "spacing": SPACING, "glade_clear": GLADE_CLEAR, "off_town": OFF_TOWN, "off_leg": OFF_LEG,
                     "near_leg": NEAR_LEG, "region_inset": INSET, "grid": GRID, "per_km2": round(PER_KM2, 3)},
           "species_by_foliage": SPECIES, "notes": notes,
           "excluded": excluded, "regions": regions, "function": str(fn.relative_to(ROOT))}
    T.write_json(a.out or str(ROOT / "derived" / "sites" / "elder_trees.json"), doc)
    print(json.dumps({"trees": len(all_sites), "regions": len(regions),
                      "per_region": {r["id"]: r["placed"] for r in regions},
                      "min_spacing_blocks": min(spacings) if spacings else None,
                      "max_pad_relief": max(s["pad_relief"] for s in all_sites) if all_sites else None,
                      "prefabs": sorted(v["name"] for v in written.values()),
                      "notes": notes, "function": str(fn.relative_to(ROOT))}, indent=1))


if __name__ == "__main__":
    main()
