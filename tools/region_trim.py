#!/usr/bin/env python
"""Report, and optionally remove, saved chunks outside a block rectangle.

Minecraft stores chunks in 32x32-chunk region files (region/, entities/ and
poi/ each use the same r.X.Z.mca layout). This walks one dimension's folder,
classifies every stored chunk as inside or outside the rectangle, and lists
structure starts found in the outside chunks, so a trim is auditable before
anything is deleted.

Dry run is the default. With --apply it requires --backup-dir, copies every
file it will change there first, then:
  - deletes region files that lie wholly outside the rectangle
  - for files that straddle the edge, clears the header entries of the
    outside chunks (their data becomes unreachable and the game treats them
    as never generated; the file is not compacted)

Distant Horizons keeps its own LOD database (data/DistantHorizons.sqlite)
which this does not touch; it must be purged or rebuilt separately.

  python tools/region_trim.py --world <offline-snapshot-world> \\
      --min-x -1024 --min-z -1024 --max-x 9215 --max-z 9215
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
from collections import Counter
from pathlib import Path

import nbt

REGION_RE = re.compile(r"^r\.(-?\d+)\.(-?\d+)\.mca$")
DIM_DIRS = {"overworld": "", "the_nether": "DIM-1", "the_end": "DIM1"}


# The ground rule (tools/ground_rule.py): the functions here that read a world, each only to check, never to
# decide a position: classifies and trims saved chunks outside the border; decides no position.
WORLD_READS = {'main', 'scan'}


def chunk_inside(cx, cz, b):
    """A chunk is inside if any of its blocks is inside the inclusive rectangle."""
    x0, z0 = cx * 16, cz * 16
    return not (x0 + 15 < b["min_x"] or x0 > b["max_x"] or z0 + 15 < b["min_z"] or z0 > b["max_z"])


def region_relation(rx, rz, b):
    x0, z0 = rx * 512, rz * 512
    x1, z1 = x0 + 511, z0 + 511
    if x1 < b["min_x"] or x0 > b["max_x"] or z1 < b["min_z"] or z0 > b["max_z"]:
        return "outside"
    if x0 >= b["min_x"] and x1 <= b["max_x"] and z0 >= b["min_z"] and z1 <= b["max_z"]:
        return "inside"
    return "straddles"


def present_chunks(path):
    data = Path(path).read_bytes()[:4096]
    out = []
    for idx in range(1024):
        if len(data) >= (idx + 1) * 4 and data[idx * 4:idx * 4 + 4] != b"\x00\x00\x00\x00":
            out.append((idx % 32, idx // 32))
    return out


def scan(dim_root, bounds, read_starts=True):
    report = {"folders": {}, "starts_outside": [], "chunks_outside": 0, "chunks_inside": 0}
    for folder in ("region", "entities", "poi"):
        d = dim_root / folder
        if not d.is_dir():
            continue
        files = []
        for p in sorted(d.iterdir()):
            m = REGION_RE.match(p.name)
            if not m:
                continue
            rx, rz = int(m.group(1)), int(m.group(2))
            rel = region_relation(rx, rz, bounds)
            chunks = present_chunks(p) if p.stat().st_size >= 8192 else []
            outside = [(lx, lz) for lx, lz in chunks if not chunk_inside(rx * 32 + lx, rz * 32 + lz, bounds)]
            files.append({"file": p.name, "relation": rel, "chunks": len(chunks), "outside_chunks": len(outside)})
            if folder == "region":
                report["chunks_outside"] += len(outside)
                report["chunks_inside"] += len(chunks) - len(outside)
                if read_starts and outside:
                    wanted = set(outside)
                    for lx, lz, ch in nbt.region_chunks(p):
                        if (lx, lz) not in wanted:
                            continue
                        for sid, v in ((ch.get("structures") or {}).get("starts") or {}).items():
                            if v.get("id") != "INVALID":
                                report["starts_outside"].append({
                                    "structure": sid, "x": (rx * 32 + lx) * 16 + 8, "z": (rz * 32 + lz) * 16 + 8,
                                    "file": p.name})
        report["folders"][folder] = files
    report["starts_outside_by_id"] = dict(Counter(s["structure"] for s in report["starts_outside"]).most_common())
    return report


def apply(dim_root, bounds, backup_dir, report):
    backup_dir = Path(backup_dir)
    actions = []
    for folder, files in report["folders"].items():
        for f in files:
            if not f["outside_chunks"]:
                continue
            src = dim_root / folder / f["file"]
            dst = backup_dir / folder / f["file"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if f["outside_chunks"] == f["chunks"]:
                src.unlink()
                actions.append({"file": "%s/%s" % (folder, f["file"]), "action": "deleted"})
                continue
            m = REGION_RE.match(f["file"])
            rx, rz = int(m.group(1)), int(m.group(2))
            data = bytearray(src.read_bytes())
            cleared = 0
            for idx in range(1024):
                lx, lz = idx % 32, idx // 32
                if data[idx * 4:idx * 4 + 4] != b"\x00\x00\x00\x00" and not chunk_inside(rx * 32 + lx, rz * 32 + lz, bounds):
                    data[idx * 4:idx * 4 + 4] = b"\x00\x00\x00\x00"
                    data[4096 + idx * 4:4096 + idx * 4 + 4] = struct.pack(">I", 0)
                    cleared += 1
            src.write_bytes(bytes(data))
            actions.append({"file": "%s/%s" % (folder, f["file"]), "action": "cleared %d chunks" % cleared})
    return actions


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--world", required=True, help="world folder (the one holding level.dat)")
    p.add_argument("--dimension", default="overworld",
                   help="overworld, the_nether, the_end, or a path under the world like dimensions/ns/name")
    p.add_argument("--min-x", type=int, required=True)
    p.add_argument("--min-z", type=int, required=True)
    p.add_argument("--max-x", type=int, required=True)
    p.add_argument("--max-z", type=int, required=True)
    p.add_argument("--apply", action="store_true", help="actually delete/clear outside chunks")
    p.add_argument("--backup-dir", default=None, help="required with --apply")
    p.add_argument("--no-starts", action="store_true", help="skip reading chunk data for structure starts")
    p.add_argument("--out", default=None, help="write the JSON report here")
    a = p.parse_args(argv)
    import runtime_guard
    world = runtime_guard.check(a.world, "trim")
    sub = DIM_DIRS.get(a.dimension, a.dimension)
    dim_root = world / sub if sub else world
    if not dim_root.is_dir():
        raise SystemExit("dimension folder not found: %s" % dim_root)
    if a.min_x > a.max_x or a.min_z > a.max_z:
        raise SystemExit("min must not exceed max")
    bounds = {"min_x": a.min_x, "min_z": a.min_z, "max_x": a.max_x, "max_z": a.max_z}
    if a.apply and not a.backup_dir:
        raise SystemExit("--apply needs --backup-dir; nothing was changed")
    if a.apply and Path(a.backup_dir).resolve().is_relative_to(dim_root.resolve()):
        raise SystemExit("--backup-dir must not be inside the dimension being trimmed")
    if a.apply and (world / "session.lock").exists():
        # the lock file persists after a clean stop; warn rather than refuse
        print("note: session.lock exists; make sure the server is stopped")

    report = scan(dim_root, bounds, not a.no_starts)
    report.update(world=str(world), dimension=a.dimension, bounds=bounds, applied=False)
    if a.apply:
        report["actions"] = apply(dim_root, bounds, a.backup_dir, report)
        report["applied"] = True
        report["backup_dir"] = str(a.backup_dir)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    rel = Counter(f["relation"] for f in report["folders"].get("region", []))
    print("%s %s: region files %s; chunks inside %d, outside %d; structure starts outside %d %s"
          % ("APPLIED" if a.apply else "DRY RUN", a.dimension, dict(rel), report["chunks_inside"],
             report["chunks_outside"], len(report["starts_outside"]), report["starts_outside_by_id"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
