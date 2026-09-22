#!/usr/bin/env python
"""Copy whole chunks from one saved world into another: terrain (region/), entities (entities/) and points of
interest (poi/).

Used after a re-export to carry work built in the live world (a settlement, say) into the freshly exported
world, so a terrain or paint change elsewhere does not cost the build. The chunks are copied byte for byte
(compressed payload and timestamp), so lighting, heightmaps and block entities travel with them. Both worlds
must be closed (server stopped).

The destination region files are rewritten sector by sector; every chunk outside the box keeps its bytes.

  python tools/transplant_chunks.py --from <old world> --to <new world> --blocks 1376 4976 1567 5391 [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import struct
import time
from pathlib import Path

SECTOR = 4096
DIRS = ("region", "entities", "poi")


# The ground rule (tools/ground_rule.py): the functions here that read a world, each only to check, never to
# decide a position: copies chunks between disposable worlds; decides no position.
WORLD_READS = {'main', 'transplant', 'write_region'}


def read_region(path):
    """{index: (timestamp, raw chunk record incl. 4-byte length and compression byte)}"""
    out = {}
    if not path.exists():
        return out
    data = path.read_bytes()
    if len(data) < 2 * SECTOR:
        return out
    for i in range(1024):
        off = struct.unpack(">I", b"\x00" + data[i * 4:i * 4 + 3])[0]
        count = data[i * 4 + 3]
        if off == 0 or count == 0:
            continue
        ts = struct.unpack(">I", data[SECTOR + i * 4:SECTOR + i * 4 + 4])[0]
        start = off * SECTOR
        length = struct.unpack(">I", data[start:start + 4])[0]
        out[i] = (ts, data[start:start + 4 + length])
    return out


def write_region(path, chunks):
    header = bytearray(2 * SECTOR)
    body = bytearray()
    sector = 2
    for i in sorted(chunks):
        ts, record = chunks[i]
        n = (len(record) + SECTOR - 1) // SECTOR
        header[i * 4:i * 4 + 4] = struct.pack(">I", sector)[1:] + bytes([n])
        header[SECTOR + i * 4:SECTOR + i * 4 + 4] = struct.pack(">I", ts)
        body += record + b"\x00" * (n * SECTOR - len(record))
        sector += n
    tmp = path.with_suffix(".mca.tmp")
    tmp.write_bytes(bytes(header) + bytes(body))
    tmp.replace(path)


def transplant(src, dst, box, dry_run=False):
    x0, z0, x1, z1 = box
    cx0, cz0, cx1, cz1 = x0 >> 4, z0 >> 4, x1 >> 4, z1 >> 4
    report = {"chunks": (cx1 - cx0 + 1) * (cz1 - cz0 + 1), "copied": {}, "missing_in_source": {}}
    for sub in DIRS:
        by_region = {}
        for cx in range(cx0, cx1 + 1):
            for cz in range(cz0, cz1 + 1):
                by_region.setdefault((cx >> 5, cz >> 5), []).append(((cx & 31) + (cz & 31) * 32))
        copied = missing = 0
        for (rx, rz), idxs in sorted(by_region.items()):
            name = "r.%d.%d.mca" % (rx, rz)
            s = read_region(Path(src) / sub / name)
            dpath = Path(dst) / sub / name
            d = read_region(dpath)
            changed = False
            for i in idxs:
                if i in s:
                    d[i] = s[i]
                    copied += 1
                    changed = True
                elif i in d:
                    del d[i]                  # the source has no chunk here (e.g. no entities): leave none
                    missing += 1
                    changed = True
                else:
                    missing += 1
            if changed and not dry_run:
                dpath.parent.mkdir(parents=True, exist_ok=True)
                write_region(dpath, d)
        report["copied"][sub] = copied
        report["missing_in_source"][sub] = missing
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--from", dest="src", required=True)
    p.add_argument("--to", dest="dst", required=True)
    p.add_argument("--blocks", nargs=4, type=int, required=True, metavar=("MIN_X", "MIN_Z", "MAX_X", "MAX_Z"))
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    import runtime_guard
    runtime_guard.check(a.src, "read"), runtime_guard.check(a.dst, "write")
    t = time.time()
    rep = transplant(a.src, a.dst, a.blocks, a.dry_run)
    rep["seconds"] = round(time.time() - t, 1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
