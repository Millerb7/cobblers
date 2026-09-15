#!/usr/bin/env python
"""Read and edit a Minecraft level.dat without losing tag types, and never print the seed.

tools/nbt.py is a reader that flattens tags to Python values. level.dat edits
need the exact tag types back (a Byte must stay a Byte), so this module keeps
every tag as (type, value) and writes the file back byte-compatible.

  python tools/level_dat.py summary <level.dat>
  python tools/level_dat.py seed-match <a/level.dat> <b/level.dat>
  python tools/level_dat.py carry --from <old/level.dat> --to <new/level.dat> \\
      --keys DataPacks,GameRules,Difficulty,DifficultyLocked,GameType,allowCommands

The seed is only ever shown as a sha256 of its decimal text, so a report can
prove two worlds share a seed without publishing it. `carry` writes a backup
beside the target (level.dat.carry-backup) before changing anything.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import struct
import sys
from pathlib import Path

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY = range(13)


# ------------------------------------------------------------------ codec

def _read_string(buf):
    (n,) = struct.unpack(">H", buf.read(2))
    return buf.read(n).decode("utf-8", "surrogatepass")


def _read_payload(buf, t):
    if t == BYTE:
        return struct.unpack(">b", buf.read(1))[0]
    if t == SHORT:
        return struct.unpack(">h", buf.read(2))[0]
    if t == INT:
        return struct.unpack(">i", buf.read(4))[0]
    if t == LONG:
        return struct.unpack(">q", buf.read(8))[0]
    if t == FLOAT:
        return struct.unpack(">f", buf.read(4))[0]
    if t == DOUBLE:
        return struct.unpack(">d", buf.read(8))[0]
    if t == BYTE_ARRAY:
        (n,) = struct.unpack(">i", buf.read(4))
        return buf.read(n)
    if t == STRING:
        return _read_string(buf)
    if t == LIST:
        et = buf.read(1)[0]
        (n,) = struct.unpack(">i", buf.read(4))
        return (et, [_read_payload(buf, et) for _ in range(n)])
    if t == COMPOUND:
        out = {}
        while True:
            ct = buf.read(1)[0]
            if ct == END:
                return out
            name = _read_string(buf)
            out[name] = (ct, _read_payload(buf, ct))
    if t == INT_ARRAY:
        (n,) = struct.unpack(">i", buf.read(4))
        return list(struct.unpack(">%di" % n, buf.read(4 * n)))
    if t == LONG_ARRAY:
        (n,) = struct.unpack(">i", buf.read(4))
        return list(struct.unpack(">%dq" % n, buf.read(8 * n)))
    raise ValueError("unknown tag type %d" % t)


def _write_string(out, s):
    b = s.encode("utf-8", "surrogatepass")
    out.write(struct.pack(">H", len(b)))
    out.write(b)


def _write_payload(out, t, v):
    if t == BYTE:
        out.write(struct.pack(">b", v))
    elif t == SHORT:
        out.write(struct.pack(">h", v))
    elif t == INT:
        out.write(struct.pack(">i", v))
    elif t == LONG:
        out.write(struct.pack(">q", v))
    elif t == FLOAT:
        out.write(struct.pack(">f", v))
    elif t == DOUBLE:
        out.write(struct.pack(">d", v))
    elif t == BYTE_ARRAY:
        out.write(struct.pack(">i", len(v)))
        out.write(v)
    elif t == STRING:
        _write_string(out, v)
    elif t == LIST:
        et, items = v
        out.write(bytes([et if items else (et or END)]))
        out.write(struct.pack(">i", len(items)))
        for item in items:
            _write_payload(out, et, item)
    elif t == COMPOUND:
        for name, (ct, cv) in v.items():
            out.write(bytes([ct]))
            _write_string(out, name)
            _write_payload(out, ct, cv)
        out.write(bytes([END]))
    elif t == INT_ARRAY:
        out.write(struct.pack(">i", len(v)))
        out.write(struct.pack(">%di" % len(v), *v))
    elif t == LONG_ARRAY:
        out.write(struct.pack(">i", len(v)))
        out.write(struct.pack(">%dq" % len(v), *v))
    else:
        raise ValueError("unknown tag type %d" % t)


def loads(data):
    """-> (root_name, root_compound) with typed children."""
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    buf = io.BytesIO(data)
    t = buf.read(1)[0]
    if t != COMPOUND:
        raise ValueError("root tag is not a compound")
    name = _read_string(buf)
    return name, _read_payload(buf, COMPOUND)


def dumps(name, compound):
    out = io.BytesIO()
    out.write(bytes([COMPOUND]))
    _write_string(out, name)
    _write_payload(out, COMPOUND, compound)
    return gzip.compress(out.getvalue(), mtime=0)


def load(path):
    return loads(Path(path).read_bytes())


def plain(node):
    """Typed node -> plain Python, for display."""
    t, v = node
    if t == COMPOUND:
        return {k: plain(c) for k, c in v.items()}
    if t == LIST:
        et, items = v
        return [plain((et, i)) for i in items]
    if t == BYTE_ARRAY:
        return "<%d bytes>" % len(v)
    return v


# ------------------------------------------------------------ level.dat views

def data_of(root):
    t, v = root["Data"]
    return v


def seed_of(data):
    wgs = data.get("WorldGenSettings")
    if wgs and "seed" in wgs[1]:
        return int(wgs[1]["seed"][1])
    if "RandomSeed" in data:
        return int(data["RandomSeed"][1])
    return None


def seed_digest(seed):
    return None if seed is None else hashlib.sha256(str(seed).encode("ascii")).hexdigest()


def summary(path):
    _, root = load(path)
    d = data_of(root)
    wgs = plain(d["WorldGenSettings"]) if "WorldGenSettings" in d else {}
    dims = {k: (v.get("generator") or {}).get("type") for k, v in (wgs.get("dimensions") or {}).items()}
    datapacks = plain(d["DataPacks"]) if "DataPacks" in d else None
    return {
        "level_name": plain(d.get("LevelName", (STRING, None))),
        "data_version": plain(d.get("DataVersion", (INT, None))),
        "seed_sha256": seed_digest(seed_of(d)),
        "generate_features": wgs.get("generate_features"),
        "dimension_generators": dims,
        "spawn": [plain(d[k]) if k in d else None for k in ("SpawnX", "SpawnY", "SpawnZ")],
        "border": {k: plain(d[k]) for k in ("BorderCenterX", "BorderCenterZ", "BorderSize", "BorderSizeLerpTarget", "BorderSizeLerpTime") if k in d},
        "game_type": plain(d["GameType"]) if "GameType" in d else None,
        "difficulty": plain(d["Difficulty"]) if "Difficulty" in d else None,
        "datapacks": datapacks,
        "game_rules_count": len(d["GameRules"][1]) if "GameRules" in d else 0,
    }


def carry(src, dst, keys, backup=True):
    """Copy top-level Data keys from src level.dat into dst level.dat."""
    _, sroot = load(src)
    dname, droot = load(dst)
    sd, dd = data_of(sroot), data_of(droot)
    copied, missing = [], []
    for k in keys:
        if k in sd:
            dd[k] = sd[k]
            copied.append(k)
        else:
            missing.append(k)
    if backup:
        shutil.copy2(dst, str(dst) + ".carry-backup")
    Path(dst).write_bytes(dumps(dname, droot))
    return copied, missing


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary")
    s.add_argument("level_dat")
    m = sub.add_parser("seed-match")
    m.add_argument("a")
    m.add_argument("b")
    c = sub.add_parser("carry")
    c.add_argument("--from", dest="src", required=True)
    c.add_argument("--to", dest="dst", required=True)
    c.add_argument("--keys", required=True)
    c.add_argument("--no-backup", action="store_true")
    a = p.parse_args(argv)
    if a.cmd == "summary":
        print(json.dumps(summary(a.level_dat), indent=1))
        return 0
    if a.cmd == "seed-match":
        sa, sb = seed_of(data_of(load(a.a)[1])), seed_of(data_of(load(a.b)[1]))
        same = sa is not None and sa == sb
        print(json.dumps({"match": same, "a_seed_sha256": seed_digest(sa), "b_seed_sha256": seed_digest(sb)}, indent=1))
        return 0 if same else 1
    if a.cmd == "carry":
        copied, missing = carry(a.src, a.dst, [k.strip() for k in a.keys.split(",") if k.strip()], not a.no_backup)
        print(json.dumps({"copied": copied, "missing_in_source": missing}, indent=1))
        return 0 if not missing else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
