#!/usr/bin/env python
"""Re-export the canonical heightmap with WorldPainter, carrying the old world's seed and settings.

  python tools/reexport.py --old-world <offline-snapshot-world> \\
      --out-dir <staging-dir> --name <new-world-name> \\
      --world-file C:/Users/wnd/Documents/cobblers-10240.world

Reads the mapping, margin, border and spawn from data/world.json, the seed
from the old world's level.dat, and runs tools/worldpainter/export_world.js
through wpscript. The seed travels only in the child process environment and
is never printed or logged. After the export it copies the old level.dat's
DataPacks selection and game settings into the new level.dat, and checks the
seeds match by digest.

Nothing is deleted. The new world folder must not already exist.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import level_dat as L
import terrain as T

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "worldpainter" / "export_world.js"
# WorldGenSettings is carried whole: WorldPainter writes its own default overworld preset (large biomes on the
# authoring machine) and per-dimension generator seeds, while the old world's settings are the ones the
# Nether, End and structure audits were computed against.
CARRY_KEYS = ["WorldGenSettings", "DataPacks", "GameRules", "Difficulty", "DifficultyLocked", "GameType",
              "allowCommands", "hardcore"]


def wp_levels(world):
    """The import line as WorldPainter levels: integer world levels, fractional image levels."""
    imp = world["import"]
    depth = world["heightmap"].get("bit_depth", 16)
    full = float((1 << depth) - 1)
    lo_in, hi_in = imp["low_in"] * full, imp["high_in"] * full
    lo_out, hi_out = float(imp["low_out"]), float(imp["high_out"])
    slope = (hi_out - lo_out) / (hi_in - lo_in)
    world_low = int(lo_out // 1)           # whole number at or below low_out
    world_high = int(round(hi_out))
    image_low = lo_in - (lo_out - world_low) / slope
    image_high = lo_in + (world_high - lo_out) / slope
    return {"image-low": image_low, "image-high": image_high, "world-low": world_low, "world-high": world_high}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--world", default=str(T.DEFAULT_WORLD))
    p.add_argument("--source-root", default=None)
    p.add_argument("--old-world", required=True, help="world folder whose level.dat supplies seed and settings")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--world-file", required=True)
    p.add_argument("--wpscript", default=r"C:\Program Files\WorldPainter\wpscript.exe")
    p.add_argument("--log", default=None)
    p.add_argument("--paint", default=None, help="manifest.json from tools/paint_maps.py; paints biomes, terrain, vegetation and lakes")
    a = p.parse_args(argv)
    import runtime_guard
    runtime_guard.check(a.old_world, "read"), runtime_guard.check(a.out_dir, "export into")

    world = T.load_world(a.world)
    heightmap = T.resolve_heightmap(world, Path(a.world), a.source_root)  # checks sha256
    exp = world["export"]
    target = Path(a.out_dir) / a.name
    if target.exists():
        raise SystemExit("refusing to overwrite existing %s" % target)
    old_dat = Path(a.old_world) / "level.dat"
    seed = L.seed_of(L.data_of(L.load(old_dat)[1]))
    if seed is None:
        raise SystemExit("no seed in %s" % old_dat)

    levels = wp_levels(world)
    args = [a.wpscript, str(SCRIPT),
            "--heightmap=%s" % heightmap, "--name=%s" % a.name, "--out=%s" % a.out_dir,
            "--world-file=%s" % a.world_file,
            "--image-low=%r" % levels["image-low"], "--image-high=%r" % levels["image-high"],
            "--world-low=%d" % levels["world-low"], "--world-high=%d" % levels["world-high"],
            "--water=%d" % world["import"]["water_level"],
            "--margin=%d" % exp["export_margin_blocks"],
            "--spawn-x=%d" % exp["spawn"][0], "--spawn-z=%d" % exp["spawn"][1],
            "--border-centre=%d" % exp["border"]["centre"], "--border-size=%d" % exp["border"]["size"]]
    if a.paint:
        args += ["--paint=%s" % Path(a.paint).resolve(), "--paint-script=%s" % (ROOT / "tools" / "worldpainter" / "paint.js")]
    print("levels:", json.dumps(levels))
    env = dict(os.environ, COBBLERS_WP_SEED=str(seed))
    proc = subprocess.run(args, env=env, capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    if str(seed) in output:
        output = output.replace(str(seed), "<seed>")
    if a.log:
        Path(a.log).write_text(output, encoding="utf-8")
    print(output)
    if proc.returncode != 0 or not (target / "level.dat").is_file():
        raise SystemExit("wpscript failed (exit %d)" % proc.returncode)

    copied, missing = L.carry(old_dat, target / "level.dat", CARRY_KEYS)
    new_seed = L.seed_of(L.data_of(L.load(target / "level.dat")[1]))
    report = {"world": str(target), "carried": copied, "missing_in_old": missing,
              "seed_match": new_seed == seed, "seed_sha256": L.seed_digest(new_seed),
              "summary": L.summary(target / "level.dat")}
    print(json.dumps(report, indent=1))
    return 0 if report["seed_match"] else 1


if __name__ == "__main__":
    sys.exit(main())
