#!/usr/bin/env python
"""Generate the size-outlier datapack from data/sizes.json.

The ambient layer of size variance is Cobblemon's own: pokemonIntrinsicSizeMin/Max in the config,
rolled uniformly on every spawn. This pack is the second layer, the rare individual worth telling
someone about, and it needs no mod: Cobblemon 1.8 already carries Pokemon.ScaleModifier, syncs it
with its own ScaleModifierUpdatePacket, and accepts a write to it through /data.

What it emits:

  size/sweep      every wild Pokemon that carries no marker yet is rolled, then the sweep reschedules
  size/roll       writes the marker, rolls 1..<per>, and dispatches to a tier
  size/<tier>     picks one of the tier's scales and writes it

The marker is Pokemon.PersistentData.cobblers_sized, which lives on the Pokemon and not the entity,
so it goes into the ball with a captured one and the roll never repeats. Anything with
Pokemon.PokemonOwnerId is skipped, so a player's Pokemon is never resized when it is sent out.

  python tools/size_outliers.py                      # write build/datapacks/cobblers_sizes
  python tools/size_outliers.py --out <dir>

Ownership: the output is generated and lives in build/ (gitignored); data/sizes.json is the source.
This tool makes no decision about rates or scales.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_sizes"
NS = "cobblers"
MARKER = "Pokemon.PersistentData.cobblers_sized"
SCORE = "cobblers_size"
PACK_MCMETA = {"pack": {"pack_format": 48,
                        "description": "Cobblers rare size outliers (generated; see data/sizes.json)"}}

# how many open blocks a tier needs above the Pokemon, from data/sizes.json. A collision box scales
# with ScaleModifier (measured 2026-09-20: Gyarados 4.0 high at its normal size, 5.0 at scale 2.0),
# so an upward roll in a low space would make something that cannot fit where it stands.
AIR = "#minecraft:air"


def functions(doc):
    per = doc["roll"]["per"]
    interval = doc["sweep"]["interval_ticks"]
    out = {}

    sweep = [
        "# every wild Pokemon that has not been rolled yet; anything already marked is skipped here,",
        "# so the work per pass is proportional to what has just spawned.",
        "execute as @e[type=cobblemon:pokemon] unless data entity @s %s unless data entity @s Pokemon.PokemonOwnerId run function %s:size/roll" % (MARKER, NS),
        "schedule function %s:size/sweep %dt replace" % (NS, interval),
    ]
    out["size/sweep"] = sweep

    roll = [
        "# the marker goes on first: a Pokemon is rolled once, whatever the outcome.",
        "data modify entity @s %s set value 1b" % MARKER,
        "execute store result score @s %s run random value 1..%d" % (SCORE, per),
    ]
    for tier in doc["tiers"]:
        lo, hi = tier["window"]
        roll.append("execute if score @s %s matches %d..%d run function %s:size/%s"
                    % (SCORE, lo, hi, NS, tier["id"]))
    roll.append("scoreboard players reset @s %s" % SCORE)
    out["size/roll"] = roll

    for tier in doc["tiers"]:
        scales = tier["scales"]
        lines = ["# %s: %s" % (tier["id"], tier["rate"])]
        if tier.get("note"):
            lines.append("# %s" % tier["note"])
        guard = ""
        headroom = int(tier.get("headroom_blocks") or 0)
        if headroom:
            lines.append("# only where it has room to stand: %d open blocks above it." % headroom)
            guard = "".join(" if block ~ ~%d ~ %s" % (n, AIR) for n in range(1, headroom + 1))
        lines.append("execute store result score @s %s run random value 1..%d" % (SCORE, len(scales)))
        for n, scale in enumerate(scales, start=1):
            lines.append("execute if score @s %s matches %d%s run data modify entity @s Pokemon.ScaleModifier set value %sf"
                         % (SCORE, n, guard, scale))
        out["size/%s" % tier["id"]] = lines

    out["size/start"] = [
        "scoreboard objectives add %s dummy" % SCORE,
        "schedule function %s:size/sweep %dt replace" % (NS, interval),
    ]
    return out


def build(doc):
    files = {"pack.mcmeta": json.dumps(PACK_MCMETA, indent=2) + "\n",
             "data/minecraft/tags/function/load.json": json.dumps(
                 {"values": ["%s:size/start" % NS]}, indent=2) + "\n"}
    for name, lines in functions(doc).items():
        files["data/%s/function/%s.mcfunction" % (NS, name)] = "\n".join(lines) + "\n"
    return files


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sizes", default=str(ROOT / "data" / "sizes.json"))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    doc = json.loads(Path(a.sizes).read_text(encoding="utf-8"))
    files = build(doc)
    out = Path(a.out)
    for rel, text in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    total = sum(t["window"][1] - t["window"][0] + 1 for t in doc["tiers"])
    print("wrote %d files to %s: %d tiers, %d of %d rolls are an outlier (1 in %.0f)"
          % (len(files), out, len(doc["tiers"]), total, doc["roll"]["per"], doc["roll"]["per"] / total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
