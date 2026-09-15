#!/usr/bin/env python
"""Minimal read-only NBT and Anvil region reader, standard library only.

Enough to inspect level.dat, structure templates (.nbt) and chunk data in
.mca region files. It does not write NBT.

  python tools/nbt.py path/to/level.dat            # print the tree, depth-limited
"""
from __future__ import annotations

import gzip
import io
import struct
import zlib
from pathlib import Path

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY = range(13)


class _Reader:
    def __init__(self, data: bytes):
        self.b = data
        self.i = 0

    def take(self, n):
        v = self.b[self.i:self.i + n]
        if len(v) != n:
            raise ValueError("truncated NBT")
        self.i += n
        return v

    def unpack(self, fmt):
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, self.take(size))[0]

    def string(self):
        n = self.unpack(">H")
        return self.take(n).decode("utf-8", "replace")

    def payload(self, tag):
        if tag == BYTE:
            return self.unpack(">b")
        if tag == SHORT:
            return self.unpack(">h")
        if tag == INT:
            return self.unpack(">i")
        if tag == LONG:
            return self.unpack(">q")
        if tag == FLOAT:
            return self.unpack(">f")
        if tag == DOUBLE:
            return self.unpack(">d")
        if tag == BYTE_ARRAY:
            n = self.unpack(">i")
            return self.take(n)
        if tag == STRING:
            return self.string()
        if tag == LIST:
            inner = self.unpack(">b")
            n = self.unpack(">i")
            return [self.payload(inner) for _ in range(max(n, 0))]
        if tag == COMPOUND:
            out = {}
            while True:
                t = self.unpack(">b")
                if t == END:
                    return out
                name = self.string()
                out[name] = self.payload(t)
        if tag == INT_ARRAY:
            n = self.unpack(">i")
            return list(struct.unpack(">%di" % n, self.take(4 * n)))
        if tag == LONG_ARRAY:
            n = self.unpack(">i")
            # long arrays (block states, heightmaps) are skipped as raw bytes
            return self.take(8 * n)
        raise ValueError("unknown NBT tag %d" % tag)


def loads(data: bytes):
    """Parse an NBT document. Accepts gzip, zlib or raw bytes. Returns (name, compound)."""
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    elif data[:1] == b"\x78":
        try:
            data = zlib.decompress(data)
        except zlib.error:
            pass
    r = _Reader(data)
    tag = r.unpack(">b")
    if tag != COMPOUND:
        raise ValueError("NBT root is not a compound")
    name = r.string()
    return name, r.payload(COMPOUND)


def load(path):
    return loads(Path(path).read_bytes())


def region_chunks(path):
    """Yield (chunk_x_in_region, chunk_z_in_region, compound) for every chunk in a .mca file."""
    data = Path(path).read_bytes()
    if len(data) < 8192:
        return
    for idx in range(1024):
        off = struct.unpack(">I", b"\x00" + data[idx * 4:idx * 4 + 3])[0]
        if off == 0:
            continue
        start = off * 4096
        length = struct.unpack(">I", data[start:start + 4])[0]
        comp = data[start + 4]
        body = data[start + 5:start + 4 + length]
        if comp == 2:
            raw = zlib.decompress(body)
        elif comp == 1:
            raw = gzip.decompress(body)
        elif comp == 3:
            raw = body
        else:
            continue  # external or unknown compression
        _, chunk = loads(raw) if raw[:1] != b"\x0a" else ("", _Reader(raw[3 + struct.unpack(">H", raw[1:3])[0]:]).payload(COMPOUND))
        yield idx % 32, idx // 32, chunk


def dump(obj, depth=4, indent=0, out=None):
    out = out if out is not None else io.StringIO()
    pad = "  " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and depth > 0:
                out.write("%s%s:\n" % (pad, k))
                dump(v, depth - 1, indent + 1, out)
            elif isinstance(v, (dict, list)):
                out.write("%s%s: <%s of %d>\n" % (pad, k, type(v).__name__, len(v)))
            elif isinstance(v, bytes):
                out.write("%s%s: <%d bytes>\n" % (pad, k, len(v)))
            else:
                out.write("%s%s: %r\n" % (pad, k, v))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:20]):
            if isinstance(v, (dict, list)) and depth > 0:
                out.write("%s[%d]:\n" % (pad, i))
                dump(v, depth - 1, indent + 1, out)
            else:
                out.write("%s[%d]: %r\n" % (pad, i, v if not isinstance(v, bytes) else "<bytes>"))
        if len(obj) > 20:
            out.write("%s... %d more\n" % (pad, len(obj) - 20))
    return out


if __name__ == "__main__":
    import sys
    name, root = load(sys.argv[1])
    print(dump(root, depth=int(sys.argv[2]) if len(sys.argv) > 2 else 4).getvalue())
