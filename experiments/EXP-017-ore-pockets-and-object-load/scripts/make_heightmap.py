#!/usr/bin/env python
"""EXP-017: write heightmap100.png (256x256 8-bit grey, value 100 -> flat terrain at y=100).

  python make_heightmap.py <dir>
"""
import struct
import sys
import zlib
from pathlib import Path

W = H = 256
raw = b"".join(b"\x00" + bytes([100]) * W for _ in range(H))


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 0, 0, 0, 0))
png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
out = Path(sys.argv[1]) / "heightmap100.png"
out.write_bytes(png)
print("wrote", out)
