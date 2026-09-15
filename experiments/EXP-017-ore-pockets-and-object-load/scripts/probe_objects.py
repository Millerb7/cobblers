#!/usr/bin/env python
"""EXP-017 Task B: snapshot the Cobblemon blocks and block entities of a saved world (read-only).

  python probe_objects.py <world dir> <tools dir> <out.json> [--x0 0 --z0 0 --x1 255 --z1 255]

Writes JSON with:
  chunks        count, DataVersion histogram, Status histogram
  blocks        per cobblemon:* block name: count and every position (x, y, z) with its properties
  block_entities every block entity: id, pos, the block at pos, and its data (bytes -> length)
Run it once on the WorldPainter export (before load) and once on the saved world after the
server stopped; compare_objects.py diffs the two.
"""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

world, tools, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, tools)
import nbt  # noqa: E402

args = sys.argv[4:]
opt = {args[i].lstrip("-"): int(args[i + 1]) for i in range(0, len(args), 2)}
X0, Z0, X1, Z1 = opt.get("x0", 0), opt.get("z0", 0), opt.get("x1", 255), opt.get("z1", 255)


def unpack(data: bytes, bits: int, count: int):
    longs = [int.from_bytes(data[i:i + 8], "big") for i in range(0, len(data), 8)]
    per, mask, res = 64 // bits, (1 << bits) - 1, []
    for lg in longs:
        for k in range(per):
            res.append((lg >> (k * bits)) & mask)
            if len(res) == count:
                return res
    return res


def plain(v):
    if isinstance(v, bytes):
        return "<%d bytes>" % len(v)
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [plain(x) for x in v]
    return v


dv, status = Counter(), Counter()
blocks = defaultdict(list)
block_at = {}
bes = []
nchunks = 0
for mca in sorted((world / "region").glob("*.mca")):
    for _, _, ch in nbt.region_chunks(mca):
        cx, cz = ch["xPos"], ch["zPos"]
        if not (X0 // 16 <= cx <= X1 // 16 and Z0 // 16 <= cz <= Z1 // 16):
            continue
        nchunks += 1
        dv[ch.get("DataVersion")] += 1
        status[str(ch.get("Status"))] += 1
        for sec in ch.get("sections", []):
            bs = sec.get("block_states")
            if not bs:
                continue
            pal = bs["palette"]
            names = [p["Name"] for p in pal]
            if not any(n.startswith("cobblemon:") for n in names):
                continue
            idx = unpack(bs["data"], max(4, math.ceil(math.log2(len(pal)))), 4096) if len(pal) > 1 else [0] * 4096
            for i, pi in enumerate(idx):
                p = pal[pi]
                if not p["Name"].startswith("cobblemon:"):
                    continue
                pos = (cx * 16 + (i & 15), sec["Y"] * 16 + (i >> 8), cz * 16 + ((i >> 4) & 15))
                blocks[p["Name"]].append([*pos, p.get("Properties", {})])
                block_at[pos] = p
        for be in ch.get("block_entities", []):
            pos = (be["x"], be["y"], be["z"])
            b = block_at.get(pos)
            bes.append({"id": be.get("id"), "pos": list(pos), "block": (b or {}).get("Name"),
                        "data": plain({k: v for k, v in be.items() if k not in ("x", "y", "z", "id")})})

res = {
    "world": str(world),
    "chunks": nchunks,
    "data_version": {str(k): v for k, v in dv.items()},
    "status": dict(status),
    "blocks": {k: {"count": len(v), "positions": v} for k, v in sorted(blocks.items())},
    "block_entity_counts": dict(Counter(b["id"] for b in bes)),
    "block_entities": bes,
}
out.write_text(json.dumps(res), encoding="utf8")
print(json.dumps({k: res[k] for k in ("chunks", "data_version", "status", "block_entity_counts")}),
      {k: v["count"] for k, v in res["blocks"].items()})
