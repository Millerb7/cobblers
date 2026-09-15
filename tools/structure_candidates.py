#!/usr/bin/env python
"""List where random-spread structure sets may start inside a rectangle, from the world seed.

Minecraft's random_spread placement divides the world into cells of
`spacing` chunks and picks one candidate chunk per cell from the seed and the
set's salt. A structure can only start in a candidate chunk; whether it
actually starts there also depends on the biome and terrain checks, which
this does not model. So the output is an upper bound: the attempts a border
contains. Pregen plus tools/dimension_audit.py gives the real answer.

The arithmetic follows Minecraft 1.21.1 (RandomSpreadStructurePlacement and
the java.util.Random LCG behind WorldgenRandom):

  cell      = floorDiv(chunk, spacing)
  seed'     = cellX * 341873128712 + cellZ * 132897987541 + worldSeed + salt
  offset    = nextInt(spacing - separation)           (linear)
            = (nextInt(n) + nextInt(n)) / 2            (triangular)
  frequency < 1 filters candidates with a second random keyed on the chunk

Concentric-ring sets (strongholds) and Repurposed Structures'
advanced_random_spread are reported as not modelled.

  python tools/structure_candidates.py --server-dir ../cobblers-server \\
      --level-dat ../cobblers-server/erosion-land-8k/level.dat --dimension end \\
      --min-x -4096 --min-z -4096 --max-x 4095 --max-z 4095 --classes PROGRESSION,LEGENDARY

The world seed is read from level.dat at run time and never written out.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MULT = 0x5DEECE66D
MASK = (1 << 48) - 1


class JavaRandom:
    """java.util.Random, enough of it for worldgen placement."""

    def __init__(self, seed):
        self.state = (seed ^ MULT) & MASK

    def next_bits(self, bits):
        self.state = (self.state * MULT + 0xB) & MASK
        r = self.state >> (48 - bits)
        if bits == 32 and r >= 1 << 31:
            r -= 1 << 32
        return r

    def next_int(self, bound=None):
        if bound is None:
            return self.next_bits(32)
        if bound <= 0:
            raise ValueError("bound must be positive")
        if bound & -bound == bound:
            return (bound * self.next_bits(31)) >> 31
        while True:
            u = self.next_bits(31)
            r = u % bound
            if u - r + (bound - 1) < 1 << 31:
                return r

    def next_float(self):
        return self.next_bits(24) / float(1 << 24)


def large_feature_with_salt(world_seed, a, b, salt):
    return JavaRandom(a * 341873128712 + b * 132897987541 + world_seed + salt)


def candidate_chunk(world_seed, cell_x, cell_z, spacing, separation, salt, spread="linear"):
    rnd = large_feature_with_salt(world_seed, cell_x, cell_z, salt)
    n = spacing - separation
    if spread == "triangular":
        ox = (rnd.next_int(n) + rnd.next_int(n)) // 2
        oz = (rnd.next_int(n) + rnd.next_int(n)) // 2
    else:
        ox = rnd.next_int(n)
        oz = rnd.next_int(n)
    return cell_x * spacing + ox, cell_z * spacing + oz


def passes_frequency(world_seed, salt, cx, cz, frequency):
    """The 'default' frequency reduction method (probability_reducer)."""
    if frequency >= 1.0:
        return True
    return large_feature_with_salt(world_seed, salt, cx, cz).next_float() < frequency


def candidates(world_seed, placement, bounds):
    spacing, separation = placement["spacing"], placement["separation"]
    salt = placement["salt"]
    spread = placement.get("spread_type", "linear")
    freq = placement.get("frequency", 1.0)
    method = placement.get("frequency_reduction_method", "default")
    c0x, c1x = bounds["min_x"] // 16, bounds["max_x"] // 16
    c0z, c1z = bounds["min_z"] // 16, bounds["max_z"] // 16
    out, filtered = [], 0
    for gx in range(c0x // spacing, c1x // spacing + 1):
        for gz in range(c0z // spacing, c1z // spacing + 1):
            cx, cz = candidate_chunk(world_seed, gx, gz, spacing, separation, salt, spread)
            if not (c0x <= cx <= c1x and c0z <= cz <= c1z):
                continue
            if freq < 1.0 and method == "default" and not passes_frequency(world_seed, salt, cx, cz, freq):
                filtered += 1
                continue
            out.append({"chunk": [cx, cz], "block": [cx * 16 + 8, cz * 16 + 8]})
    return out, filtered, (freq < 1.0 and method != "default")


def read_seed(level_dat):
    import nbt
    _, level = nbt.load(level_dat)
    data = level["Data"]
    wg = data.get("WorldGenSettings") or {}
    seed = wg.get("seed", data.get("RandomSeed"))
    if seed is None:
        raise SystemExit("no seed in %s" % level_dat)
    return int(seed)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server-dir", required=True)
    p.add_argument("--level-dat", required=True)
    p.add_argument("--dimension", default="overworld", help="overworld, nether or end (as in data/structures.json)")
    p.add_argument("--min-x", type=int, required=True)
    p.add_argument("--min-z", type=int, required=True)
    p.add_argument("--max-x", type=int, required=True)
    p.add_argument("--max-z", type=int, required=True)
    p.add_argument("--structures", default=str(ROOT / "data" / "structures.json"))
    p.add_argument("--classes", default=None, help="only sets holding a structure of these classes")
    p.add_argument("--only", default=None, help="comma-separated structure ids")
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)

    import spawn_biomes as SB
    import structure_inventory as SI

    catalog = json.loads(Path(a.structures).read_text(encoding="utf-8"))
    wanted = {}
    classes = set(a.classes.split(",")) if a.classes else None
    only = set(a.only.split(",")) if a.only else None
    for s in catalog["structures"]:
        if s["dimension"] != a.dimension:
            continue
        if classes and s["cls"] not in classes:
            continue
        if only and s["id"] not in only:
            continue
        wanted[s["id"]] = s["cls"]

    ix = SI.Index(SB.discover(a.server_dir))
    seed = read_seed(a.level_dat)
    bounds = {"min_x": a.min_x, "min_z": a.min_z, "max_x": a.max_x, "max_z": a.max_z}
    sets = []
    for key in sorted(ix.sets):
        doc = ix.json(ix.sets, key) or {}
        members = [m["structure"] for m in doc.get("structures") or []]
        hit = [m for m in members if m in wanted]
        if not hit:
            continue
        pl = doc.get("placement") or {}
        ptype = pl.get("type")
        if ptype and ":" not in ptype:
            ptype = "minecraft:" + ptype
        row ={"set": key, "structures": hit, "classes": sorted({wanted[m] for m in hit}), "set_size": len(members),
               "placement": ptype, "spacing": pl.get("spacing"), "separation": pl.get("separation")}
        if ptype == "minecraft:random_spread":
            cands, filtered, unmodelled_freq = candidates(seed, pl, bounds)
            row.update(candidates=cands, candidate_count=len(cands), removed_by_frequency=filtered,
                       frequency=pl.get("frequency", 1.0))
            if unmodelled_freq:
                row["note"] = "frequency reduction method %s not modelled" % pl.get("frequency_reduction_method")
            if pl.get("exclusion_zone"):
                row["note"] = (row.get("note", "") + " exclusion_zone not modelled").strip()
        else:
            row["note"] = "placement type not modelled"
        sets.append(row)
    result = {"schema": "cobblers.derived.structure_candidates/1", "dimension": a.dimension, "bounds": bounds,
              "caveat": "candidate chunks are attempts; biome and terrain checks decide which become starts",
              "sets": sets}
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    for r in sets:
        print("%-45s %-28s spacing %-4s sep %-4s candidates %s %s" % (
            r["set"], ",".join(r["classes"]), r["spacing"], r["separation"], r.get("candidate_count", "-"), r.get("note", "")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
