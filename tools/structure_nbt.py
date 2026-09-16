#!/usr/bin/env python
"""Structure templates (.nbt): read, write, and capture from a saved world.

tools/nbt.py reads NBT but drops tag types, so it cannot write. Structure templates have a fixed
schema, so this module writes them with explicit types:

  {DataVersion: int, size: [int x3], palette: [{Name: str, Properties: {str: str}}],
   blocks: [{pos: [int x3], state: int}], entities: []}

capture() reads a box of blocks out of a world's region files (the server must have flushed with
`save-all flush`), which is how vanilla features placed with `/place feature` become objects:
a powered structure block in SAVE mode does not write a file on 1.21.1 (tried 2026-09-14).

  python tools/structure_nbt.py info kits/structures/foliage/spruce_01.nbt
"""
from __future__ import annotations

import argparse
import gzip
import io
import struct
from pathlib import Path

import numpy as np

import nbt

DATA_VERSION = 3955            # Minecraft 1.21.1
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY = range(13)


# ------------------------------------------------------------------ writing

def _str(out, s):
    b = s.encode("utf-8")
    out.write(struct.pack(">H", len(b)))
    out.write(b)


def _named(out, tag, name):
    out.write(struct.pack(">b", tag))
    _str(out, name)


def _compound_of_strings(out, d):
    for k in sorted(d):
        _named(out, STRING, k)
        _str(out, str(d[k]))
    out.write(b"\x00")


def dumps(size, palette, blocks, data_version=DATA_VERSION):
    """Gzipped structure template bytes. palette: [(name, {prop: value})]; blocks: [(x, y, z, state)]."""
    out = io.BytesIO()
    _named(out, COMPOUND, "")
    _named(out, INT, "DataVersion")
    out.write(struct.pack(">i", data_version))
    _named(out, LIST, "size")
    out.write(struct.pack(">bi", INT, 3))
    out.write(struct.pack(">3i", *size))
    _named(out, LIST, "palette")
    out.write(struct.pack(">bi", COMPOUND, len(palette)))
    for name, props in palette:
        _named(out, STRING, "Name")
        _str(out, name)
        if props:
            _named(out, COMPOUND, "Properties")
            _compound_of_strings(out, props)
        out.write(b"\x00")
    _named(out, LIST, "blocks")
    out.write(struct.pack(">bi", COMPOUND, len(blocks)))
    for x, y, z, state in blocks:
        _named(out, LIST, "pos")
        out.write(struct.pack(">bi", INT, 3))
        out.write(struct.pack(">3i", x, y, z))
        _named(out, INT, "state")
        out.write(struct.pack(">i", state))
        out.write(b"\x00")
    _named(out, LIST, "entities")
    out.write(struct.pack(">bi", COMPOUND, 0))
    out.write(b"\x00")
    # a fixed gzip mtime so identical content gives identical bytes
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(out.getvalue())
    return buf.getvalue()


class Builder:
    """Accumulate blocks by coordinate (later writes win), then write a trimmed template."""

    def __init__(self):
        self.blocks = {}

    def set(self, x, y, z, name, props=None):
        self.blocks[(int(x), int(y), int(z))] = (name, tuple(sorted((props or {}).items())))

    def setdefault(self, x, y, z, name, props=None):
        """Set only where nothing is yet: leaves never overwrite a trunk."""
        key = (int(x), int(y), int(z))
        if key not in self.blocks:
            self.blocks[key] = (name, tuple(sorted((props or {}).items())))

    def get(self, x, y, z):
        v = self.blocks.get((int(x), int(y), int(z)))
        return v[0] if v else None

    def bounds(self):
        k = np.array(list(self.blocks))
        return k.min(axis=0), k.max(axis=0)

    def to_bytes(self, origin=None):
        """Shift so the minimum corner is 0,0,0 and write. Returns (bytes, shift) where shift is added to
        builder coordinates to get template coordinates."""
        lo, hi = self.bounds()
        shift = -lo
        size = (hi - lo + 1).tolist()
        palette, index, blocks = [], {}, []
        for (x, y, z), state in sorted(self.blocks.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
            if state[0] in AIR:
                continue
            if state not in index:
                index[state] = len(palette)
                palette.append((state[0], dict(state[1])))
            blocks.append((x + shift[0], y + shift[1], z + shift[2], index[state]))
        return dumps(size, palette, blocks), shift.tolist()


# ------------------------------------------------------------------ reading

def load(path):
    """-> dict(size, palette [(name, props)], blocks [(x, y, z, state)])."""
    _, doc = nbt.load(path)
    palette = [(p.get("Name"), dict(p.get("Properties") or {})) for p in doc.get("palette") or []]
    blocks = [(b["pos"][0], b["pos"][1], b["pos"][2], b["state"]) for b in doc.get("blocks") or []]
    return {"size": list(doc.get("size")), "palette": palette, "blocks": blocks,
            "data_version": doc.get("DataVersion")}


def describe(t):
    names = {}
    for _, _, _, s in t["blocks"]:
        n = t["palette"][s][0]
        names[n] = names.get(n, 0) + 1
    logs = [(x, y, z) for x, y, z, s in t["blocks"] if t["palette"][s][0].endswith(("_log", "_wood"))]
    base = [(x, z) for x, y, z in logs if y == min((p[1] for p in logs), default=0)]
    return {"size": t["size"], "blocks": len(t["blocks"]), "materials": names,
            "trunk_base": sorted(base)}


# ------------------------------------------------------------------ capture from a world

def _section_states(sec):
    from world_heights import unpack_states
    bs = sec.get("block_states") or {}
    pal = bs.get("palette") or []
    if not pal:
        return None, None
    idx = unpack_states(bs.get("data"), len(pal)).reshape(16, 16, 16)  # [y, z, x]
    return pal, idx


def capture(world_dir, lo, hi):
    """Builder with every non-air block in the inclusive box lo..hi (x, y, z), in world coordinates."""
    b = Builder()
    region = Path(world_dir) / "region"
    need = {}
    for cx in range(lo[0] >> 4, (hi[0] >> 4) + 1):
        for cz in range(lo[2] >> 4, (hi[2] >> 4) + 1):
            need.setdefault((cx >> 5, cz >> 5), set()).add((cx & 31, cz & 31))
    for (rx, rz), chunks in need.items():
        path = region / ("r.%d.%d.mca" % (rx, rz))
        for lx, lz, ch in nbt.region_chunks(path, wanted=chunks):
            x0, z0 = (rx * 32 + lx) * 16, (rz * 32 + lz) * 16
            for sec in ch.get("sections") or []:
                y0 = int(sec.get("Y", 0)) * 16
                if y0 + 15 < lo[1] or y0 > hi[1]:
                    continue
                pal, idx = _section_states(sec)
                if pal is None:
                    continue
                for pi, p in enumerate(pal):
                    if p.get("Name") in AIR:
                        continue
                    ys, zs, xs = np.nonzero(idx == pi)
                    for y, z, x in zip(ys + y0, zs + z0, xs + x0):
                        if lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1] and lo[2] <= z <= hi[2]:
                            b.set(x, y, z, p["Name"], p.get("Properties"))
    return b


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("info")
    i.add_argument("path")
    a = p.parse_args(argv)
    if a.cmd == "info":
        import json
        print(json.dumps(describe(load(a.path)), indent=1))


if __name__ == "__main__":
    main()
