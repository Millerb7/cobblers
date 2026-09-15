#!/usr/bin/env python
"""EXP-017 Task A: expected density of every modded ore, computed from the placed/configured
feature JSON inside the jars the server loads.

  python ore_model.py <mods dir> <out.json> [--sim 200000]

Model (vanilla 1.21.1 placement, checked against the intermediary bytecode of
OreFeature class_3122, ScatteredOreFeature class_5875 and TrapezoidHeightProvider class_6342):
  attempts per chunk      = count x (1/rarity chance)          (count, rarity_filter modifiers)
  attempt height pdf p(y) = uniform(min..max) or trapezoid(min..max, plateau 0) = min + U[0,m] + U[0,l],
                            l = (max-min)//2, m = (max-min) - l   (sum of two integer uniforms)
  blocks per attempt B    = minecraft:ore  -> Monte-Carlo of OreFeature with every target cell being host
                            minecraft:scattered_ore -> E[nextInt(size+1)] = size/2 (all cells host)
  expected ore per chunk per y  E(y) = attempts x B x p(y)
  per 1,000 host blocks at y    D(y) = 1000 x E(y) / 256
Assumptions: every cell of the vein is the target host (discard_chance_on_air_exposure is 0 for all of
them, so air only matters by not being host); a vein centred at y spreads its blocks over ~y-2..y+1,
ignored for band averages; the biome modifier passes (all attempts inside a tagged biome); in the
overworld the host is deepslate below y=0 and stone from y=0 (the WorldPainter export's split; vanilla
blends 0..8). For stone-only or deepslate-only targets, attempts landing in the other rock place nothing.
"""
import json
import math
import random
import sys
import zipfile
from pathlib import Path

import numpy as np

MODS = Path(sys.argv[1])
OUT = Path(sys.argv[2])
NSIM = int(sys.argv[sys.argv.index("--sim") + 1]) if "--sim" in sys.argv else 200000

JARS = {
    "cobblemon": "Cobblemon-fabric-1.8.0+1.21.1.jar",
    "lumymon": "LumyMon-0.6.6.jar",
    "legendarymonuments": "LegendaryMonuments-Cobbleverse.jar",
}

# Biome attachment, read from code (javap of CobblemonOrePlacedFeatures / CobblemonPlacedFeatures,
# LumyMon ModOreGeneration, LegendaryMonuments ModOreGeneration; intermediary names resolved with
# yarn 1.21.1+build.3). Cobblemon's tags are data: data/cobblemon/tags/worldgen/biome/has_ore/*.
LUMY_BIOMES = {
    "dragon_ore_placed": ["minecraft:deep_dark"],
    "electron_ore_placed": ["minecraft:desert"],
    "ice_ore_placed": ["minecraft:ice_spikes", "minecraft:frozen_ocean", "minecraft:frozen_peaks"],
    "rock_ore_placed": ["minecraft:badlands", "minecraft:eroded_badlands", "minecraft:wooded_badlands"],
    "steel_ore_placed": ["minecraft:dripstone_caves"],
}


def read(jar, path):
    with zipfile.ZipFile(MODS / JARS[jar]) as z:
        return json.loads(z.read(path))


def anchor(a, dim):
    bottom, top = (-64, 319) if dim == "overworld" else (0, 255)
    if "absolute" in a:
        return a["absolute"]
    if "above_bottom" in a:
        return bottom + a["above_bottom"]
    if "below_top" in a:
        return top - a["below_top"]
    raise ValueError(a)


def height_pdf(h, dim):
    lo, hi = anchor(h["min_inclusive"], dim), anchor(h["max_inclusive"], dim)
    ys = np.arange(lo, hi + 1)
    if h["type"] == "minecraft:uniform":
        return ys, np.full(len(ys), 1.0 / len(ys)), lo, hi
    if h["type"] == "minecraft:trapezoid":
        plateau = h.get("plateau", 0)
        k = hi - lo
        if plateau >= k:
            return ys, np.full(len(ys), 1.0 / len(ys)), lo, hi
        l = (k - plateau) // 2
        m = k - l
        a = np.full(m + 1, 1.0 / (m + 1))
        b = np.full(l + 1, 1.0 / (l + 1))
        p = np.convolve(a, b)
        return ys, p, lo, hi
    raise ValueError(h["type"])


# ---- OreFeature Monte-Carlo (minecraft:ore) -------------------------------------------------
def ore_vein(size, rnd, x=0, y=0, z=0):
    """Cells placed by one OreFeature attempt at (x, y, z) when every cell is host. Mirrors
    OreFeature.place + doPlace (1.21.1): endpoints, per-step spheres, contained-sphere pruning,
    and the (c+0.5-centre)/r < 1 cell test with a BitSet against duplicates."""
    f = rnd.random() * math.pi
    g = size / 8.0
    d0 = x + math.sin(f) * g
    d1 = x - math.sin(f) * g
    e0 = z + math.cos(f) * g
    e1 = z - math.cos(f) * g
    h0 = y + rnd.randrange(3) - 2
    h1 = y + rnd.randrange(3) - 2
    spheres = []
    for k in range(size):
        t = k / size
        cx = d0 + t * (d1 - d0)
        cy = h0 + t * (h1 - h0)
        cz = e0 + t * (e1 - e0)
        hh = rnd.random() * size / 16.0
        r = ((math.sin(math.pi * t) + 1.0) * hh + 1.0) / 2.0
        spheres.append([cx, cy, cz, r])
    for i in range(size - 1):
        if spheres[i][3] <= 0:
            continue
        for j in range(i + 1, size):
            if spheres[j][3] <= 0:
                continue
            dx, dy, dz = (spheres[i][n] - spheres[j][n] for n in range(3))
            dr = spheres[i][3] - spheres[j][3]
            if dr * dr > dx * dx + dy * dy + dz * dz:
                if dr > 0:
                    spheres[j][3] = -1.0
                else:
                    spheres[i][3] = -1.0
    cells = set()
    for cx, cy, cz, r in spheres:
        if r < 0:
            continue
        for bx in range(math.floor(cx - r), math.floor(cx + r) + 1):
            ux = (bx + 0.5 - cx) / r
            if ux * ux >= 1:
                continue
            for by in range(math.floor(cy - r), math.floor(cy + r) + 1):
                uy = (by + 0.5 - cy) / r
                if ux * ux + uy * uy >= 1:
                    continue
                for bz in range(math.floor(cz - r), math.floor(cz + r) + 1):
                    uz = (bz + 0.5 - cz) / r
                    if ux * ux + uy * uy + uz * uz < 1:
                        cells.add((bx, by, bz))
    return cells


def components(cells):
    cells = set(cells)
    sizes = []
    while cells:
        stack = [cells.pop()]
        n = 0
        while stack:
            cx, cy, cz = stack.pop()
            n += 1
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q = (cx + d[0], cy + d[1], cz + d[2])
                if q in cells:
                    cells.remove(q)
                    stack.append(q)
        sizes.append(n)
    return sizes


def simulate(size, n):
    rnd = random.Random(17 + size)
    counts, comp = [], []
    for _ in range(n):
        c = ore_vein(size, rnd)
        counts.append(len(c))
        comp += components(c)
    counts = np.array(counts)
    return {
        "attempts": n,
        "blocks_per_attempt_mean": round(float(counts.mean()), 4),
        "blocks_per_attempt_hist": {str(k): int(v) for k, v in zip(*np.unique(counts, return_counts=True))},
        "blocks_per_attempt_max": int(counts.max()),
        "blob_size_mean_6conn": round(float(np.mean(comp)), 3) if comp else 0.0,
        "blob_size_hist_6conn": {str(k): int(v) for k, v in zip(*np.unique(comp, return_counts=True))},
        "blobs_per_attempt_6conn": round(len(comp) / n, 4),
    }


BANDS = {"deepslate_-63_-1": (-63, -1), "stone_0_63": (0, 63), "stone_64_127": (64, 127),
         "stone_128_191": (128, 191), "stone_192_255": (192, 255), "stone_0_191": (0, 191)}


def feature_rows():
    rows = []
    cob = "data/cobblemon/worldgen/"
    stones = ["dawn", "dusk", "fire", "ice", "leaf", "moon", "shiny", "sun", "thunder", "water"]
    for s in stones:
        cfg = read("cobblemon", cob + "configured_feature/ore/%s_stone.json" % s)
        for part in ("lower", "upper", "lower_rare", "upper_rare"):
            pf = "%s_stone_%s" % (s, part)
            tier = "rare" if part.endswith("rare") else "normal"
            rows.append(dict(ore="cobblemon:%s_stone" % s, placed="cobblemon:ore/" + pf, tier=tier,
                             placed_json=read("cobblemon", cob + "placed_feature/ore/%s.json" % pf), configured=cfg,
                             dim="overworld", biome="#cobblemon:has_ore/ore_%s_stone_%s" % (s, tier)))
    rows.append(dict(ore="cobblemon:moon_stone (dripstone)", placed="cobblemon:ore/moon_stone_dripstone", tier="dripstone",
                     placed_json=read("cobblemon", cob + "placed_feature/ore/moon_stone_dripstone.json"),
                     configured=read("cobblemon", cob + "configured_feature/ore/dripstone_moon_stone.json"),
                     dim="overworld", biome="#cobblemon:has_ore/ore_moon_stone_dripstone"))
    rows.append(dict(ore="cobblemon:fire_stone (nether)", placed="cobblemon:ore/fire_stone_nether", tier="nether",
                     placed_json=read("cobblemon", cob + "placed_feature/ore/fire_stone_nether.json"),
                     configured=read("cobblemon", cob + "configured_feature/ore/nether_fire_stone.json"),
                     dim="nether", biome="#cobblemon:has_ore/ore_fire_stone_nether"))
    rows.append(dict(ore="cobblemon:type_gems", placed="cobblemon:type_gems", tier="special",
                     placed_json=read("cobblemon", cob + "placed_feature/type_gems.json"),
                     configured=read("cobblemon", cob + "configured_feature/type_gems.json"),
                     dim="overworld", biome="#minecraft:is_overworld"))
    for name in LUMY_BIOMES:
        pj = read("lumymon", "data/lumymon/worldgen/placed_feature/%s.json" % name)
        cj = read("lumymon", "data/lumymon/worldgen/configured_feature/%s.json" % pj["feature"].split(":")[1])
        rows.append(dict(ore=pj["feature"], placed="lumymon:" + name, tier="single", placed_json=pj, configured=cj,
                         dim="overworld", biome=LUMY_BIOMES[name]))
    for name in ("galar_particle_ore_placed", "deepslate_galar_particle_ore_placed"):
        pj = read("legendarymonuments", "data/legendarymonuments/worldgen/placed_feature/%s.json" % name)
        cj = read("legendarymonuments", "data/legendarymonuments/worldgen/configured_feature/%s.json" % pj["feature"].split(":")[1])
        rows.append(dict(ore=pj["feature"], placed="legendarymonuments:" + name, tier="single", placed_json=pj,
                         configured=cj, dim="overworld", biome="BiomeSelectors.foundInOverworld() (code)"))
    return rows


def main():
    sims = {}
    out_rows = []
    for r in feature_rows():
        pj, cj = r["placed_json"], r["configured"]
        count, rarity, height = 1, 1, None
        for m in pj["placement"]:
            if m["type"] == "minecraft:count":
                count *= m["count"]
            elif m["type"] == "minecraft:rarity_filter":
                rarity = m["chance"]
            elif m["type"] == "minecraft:height_range":
                height = m["height"]
        ftype = cj["type"]
        cfg = cj["config"]
        targets = [{"state": t["state"]["Name"],
                    "rule": t["target"]["predicate_type"],
                    "match": t["target"].get("tag") or t["target"].get("block")} for t in cfg.get("targets", [])]
        entry = {k: r[k] for k in ("ore", "placed", "tier", "dim", "biome")}
        entry.update(feature_type=ftype, size=cfg.get("size"), discard_chance_on_air_exposure=cfg.get("discard_chance_on_air_exposure"),
                     targets=targets, count=count, rarity_chance=rarity, height=height)
        if ftype == "minecraft:ore":
            key = cfg["size"]
            if key not in sims:
                sims[key] = simulate(key, NSIM)
            B = sims[key]["blocks_per_attempt_mean"]
        elif ftype == "minecraft:scattered_ore":
            B = cfg["size"] / 2.0
        else:
            B = None
        entry["blocks_per_attempt"] = B
        attempts = count / rarity
        entry["attempts_per_chunk"] = attempts
        if B is not None and height is not None:
            ys, p, lo, hi = height_pdf(height, r["dim"])
            entry["y_range"] = [lo, hi]
            dens = 1000.0 * attempts * B * p / 256.0  # per 1,000 host blocks at y
            entry["peak_permille_host"] = round(float(dens.max()), 5)
            entry["peak_y"] = int(ys[int(dens.argmax())])
            entry["mean_permille_host_over_range"] = round(float(dens.mean()), 5)
            entry["ore_blocks_per_chunk_total"] = round(attempts * B, 4)
            stone_only = all(t["match"] in ("minecraft:stone_ore_replaceables",) for t in targets)
            deep_only = all(t["match"] in ("minecraft:deepslate_ore_replaceables",) for t in targets)
            bands = {}
            for bname, (a, b) in BANDS.items():
                if r["dim"] != "overworld":
                    continue
                sel = (ys >= a) & (ys <= b)
                n = b - a + 1
                v = float(dens[sel].sum()) / n
                if stone_only and b < 0 or deep_only and a >= 0:
                    v = 0.0
                bands[bname] = round(v, 5)
            entry["band_mean_permille_host"] = bands
            entry["density_by_y"] = {str(int(y)): round(float(d), 6) for y, d in zip(ys, dens)}
        out_rows.append(entry)

    # combine per ore + tier (e.g. normal = lower + upper) band means
    combined = {}
    for e in out_rows:
        if "band_mean_permille_host" not in e or not e["band_mean_permille_host"]:
            continue
        key = "%s|%s" % (e["ore"], e["tier"])
        c = combined.setdefault(key, {"features": [], "bands": {b: 0.0 for b in BANDS}, "y_profile": {}})
        c["features"].append(e["placed"])
        for b, v in e["band_mean_permille_host"].items():
            c["bands"][b] = round(c["bands"][b] + v, 5)
    OUT.write_text(json.dumps({"model": __doc__, "ore_feature_simulation": sims, "features": out_rows,
                               "combined_by_ore_and_tier": combined}, indent=1), encoding="utf8")
    for e in out_rows:
        print("%-45s %-9s %-22s n=%-5s cnt=%-4s rar=1/%-2s B=%-6s y=%-12s peak=%-8s mean=%-8s %s" % (
            e["placed"], e["tier"], e["feature_type"].split(":")[1], e["size"], e["count"], e["rarity_chance"],
            e["blocks_per_attempt"], e.get("y_range"), e.get("peak_permille_host"), e.get("mean_permille_host_over_range"),
            e.get("band_mean_permille_host", "")))
    print(json.dumps(sims, indent=1)[:2000])
    for k, v in combined.items():
        print(k, v["bands"])


if __name__ == "__main__":
    main()
