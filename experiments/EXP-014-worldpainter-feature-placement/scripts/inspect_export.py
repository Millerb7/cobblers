#!/usr/bin/env python
"""EXP-014 inspector: decode an exported 1.20.5+ Java world and report modded content.

  python inspect_export.py <world dir> <tools dir containing nbt.py> [prefix ...]

Reports, as JSON on stdout, for every block whose name starts with one of the prefixes
(default "cobblemon:"): count, min/max y, count west (x<128) / east (x>=128), and the
biome at each block; plus every block entity (id, the block actually at its position,
its data keys) and a few vanilla control counts. Read-only.
"""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

world = Path(sys.argv[1])
sys.path.insert(0, sys.argv[2])
import nbt  # noqa: E402

PREFIXES = tuple(sys.argv[3:]) or ("cobblemon:",)
CONTROL = ("minecraft:coal_ore", "minecraft:iron_ore", "minecraft:deepslate_iron_ore", "minecraft:jigsaw",
           "minecraft:stone", "minecraft:deepslate", "minecraft:grass_block")


def unpack(data: bytes, bits: int, count: int):
    longs = [int.from_bytes(data[i:i + 8], "big") for i in range(0, len(data), 8)]
    per = 64 // bits
    mask = (1 << bits) - 1
    out = []
    for lg in longs:
        for k in range(per):
            out.append((lg >> (k * bits)) & mask)
            if len(out) == count:
                return out
    return out


def section_blocks(sec):
    bs = sec.get("block_states")
    if not bs:
        return None, None
    pal = bs["palette"]
    if len(pal) == 1 or "data" not in bs:
        return pal, None
    bits = max(4, math.ceil(math.log2(len(pal))))
    return pal, unpack(bs["data"], bits, 4096)


def section_biomes(sec):
    b = sec.get("biomes")
    if not b:
        return None, None
    pal = b["palette"]
    if len(pal) == 1 or "data" not in b:
        return pal, None
    bits = math.ceil(math.log2(len(pal)))
    return pal, unpack(b["data"], bits, 64)


stats = defaultdict(lambda: {"count": 0, "min_y": None, "max_y": None, "west_x_lt_128": 0, "east_x_ge_128": 0,
                             "biomes": Counter()})
control = Counter()
block_at = {}
block_entities = []
biome_columns = Counter()
chunks = 0
for mca in sorted((world / "region").glob("*.mca")):
    for _, _, chunk in nbt.region_chunks(mca):
        chunks += 1
        cx, cz = chunk["xPos"], chunk["zPos"]
        for sec in chunk.get("sections", []):
            pal, idx = section_blocks(sec)
            if pal is None:
                continue
            sy = sec["Y"]
            names = [p["Name"] for p in pal]
            if not any(n.startswith(PREFIXES) or n in CONTROL for n in names):
                continue
            bpal, bidx = section_biomes(sec)
            for i in range(4096):
                n = names[idx[i]] if idx is not None else names[0]
                if not (n.startswith(PREFIXES) or n in CONTROL):
                    continue
                x = cx * 16 + (i & 15)
                z = cz * 16 + ((i >> 4) & 15)
                y = sy * 16 + (i >> 8)
                if n in CONTROL:
                    control[n] += 1
                    continue
                s = stats[n]
                s["count"] += 1
                s["min_y"] = y if s["min_y"] is None else min(s["min_y"], y)
                s["max_y"] = y if s["max_y"] is None else max(s["max_y"], y)
                s["west_x_lt_128" if x < 128 else "east_x_ge_128"] += 1
                if bpal is not None:
                    bi = bidx[((((i >> 8) >> 2) * 4 + ((i >> 4) & 15) // 4) * 4 + (i & 15) // 4)] if bidx else 0
                    s["biomes"][bpal[bi]] += 1
                full = pal[idx[i]] if idx is not None else pal[0]
                block_at[(x, y, z)] = full
        for be in chunk.get("block_entities", []):
            pos = (be["x"], be["y"], be["z"])
            blk = block_at.get(pos)
            block_entities.append({"id": be.get("id"), "pos": list(pos),
                                   "block_at_pos": blk["Name"] if blk else "(not a tracked block)",
                                   "keys": sorted(k for k in be if k not in ("x", "y", "z", "id", "keepPacked"))})

be_summary = defaultdict(lambda: {"count": 0, "on_matching_block": 0, "keys": None, "blocks": Counter()})
for be in block_entities:
    e = be_summary[be["id"]]
    e["count"] += 1
    e["blocks"][be["block_at_pos"]] += 1
    if be["block_at_pos"] != "(not a tracked block)":
        e["on_matching_block"] += 1
    e["keys"] = e["keys"] or be["keys"]

out = {
    "world": str(world),
    "chunks": chunks,
    "blocks": {k: {**v, "biomes": dict(v["biomes"])} for k, v in sorted(stats.items())},
    "control_counts": dict(control),
    "block_entities": {k: {**v, "blocks": dict(v["blocks"])} for k, v in sorted(be_summary.items(), key=lambda kv: str(kv[0]))},
    "block_entity_samples": block_entities[:3],
}
print(json.dumps(out, indent=2))
