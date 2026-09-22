#!/usr/bin/env python
"""Audit one dimension of a saved world against its border: coverage and structures.

After a pregen inside a world border, this answers three questions from the
region files alone (the server must be stopped):

  1. coverage - how many chunks inside the rectangle are saved, and at which
     generation status; anything short of "full" is not finished
  2. spill - how many chunks were saved outside the rectangle (view distance
     around players standing at the border, or generation before the border)
  3. structures - every structure start inside the rectangle, with its chunk
     position; checked against data/structures.json for that dimension, so
     the structures the campaign needs (by class) are listed as present or
     missing

  python tools/dimension_audit.py --world <offline-snapshot-world> \\
      --dimension the_nether --min-x -2048 --min-z -2048 --max-x 2047 --max-z 2047 \\
      --require-classes PROGRESSION,LEGENDARY --out derived/audit/nether.json

Exit status is 0 unless --fail-on-missing or --fail-on-incomplete is given and
the condition holds, so it can gate a procedure without being noisy by default.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import nbt
from region_trim import DIM_DIRS, REGION_RE, chunk_inside, region_relation

ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIMENSION = {"overworld": "overworld", "the_nether": "nether", "the_end": "end"}


# The ground rule (tools/ground_rule.py): the functions here that read a world, each only to check, never to
# decide a position: audits a pregenerated dimension's chunks; decides nothing.
WORLD_READS = {'audit', 'main'}


def status_name(value):
    return re.sub(r"^minecraft:", "", str(value or "unknown"))


def audit(dim_root, bounds):
    region = dim_root / "region"
    inside_status, outside = Counter(), 0
    starts = []
    for p in sorted(region.iterdir()) if region.is_dir() else []:
        m = REGION_RE.match(p.name)
        if not m or p.stat().st_size < 8192:
            continue
        rx, rz = int(m.group(1)), int(m.group(2))
        if region_relation(rx, rz, bounds) == "outside":
            # count without decoding: header entries only
            data = p.read_bytes()[:4096]
            outside += sum(1 for i in range(1024) if data[i * 4:i * 4 + 4] != b"\x00\x00\x00\x00")
            continue
        for lx, lz, ch in nbt.region_chunks(p):
            cx, cz = rx * 32 + lx, rz * 32 + lz
            if not chunk_inside(cx, cz, bounds):
                outside += 1
                continue
            inside_status[status_name(ch.get("Status"))] += 1
            for sid, v in ((ch.get("structures") or {}).get("starts") or {}).items():
                if v.get("id") != "INVALID":
                    starts.append({"structure": sid, "x": cx * 16 + 8, "z": cz * 16 + 8})
    cx0, cx1 = bounds["min_x"] // 16, bounds["max_x"] // 16
    cz0, cz1 = bounds["min_z"] // 16, bounds["max_z"] // 16
    expected = (cx1 - cx0 + 1) * (cz1 - cz0 + 1)
    saved = sum(inside_status.values())
    return {
        "chunks_expected_inside": expected,
        "chunks_saved_inside": saved,
        "chunks_full_inside": inside_status.get("full", 0),
        "coverage_full": round(inside_status.get("full", 0) / expected, 4) if expected else 0.0,
        "status_inside": dict(inside_status.most_common()),
        "chunks_saved_outside": outside,
        "starts": starts,
        "starts_by_id": dict(Counter(s["structure"] for s in starts).most_common()),
    }


def check_catalog(report, catalog, dimension, classes):
    want = CATALOG_DIMENSION.get(dimension, dimension)
    found = report["starts_by_id"]
    by_class = defaultdict(lambda: {"present": [], "missing": []})
    for s in catalog.get("structures") or []:
        if s.get("dimension") != want:
            continue
        key = "present" if s["id"] in found else "missing"
        by_class[s["cls"]][key].append(s["id"])
    unknown = sorted(sid for sid in found if sid not in {s["id"] for s in catalog.get("structures") or []})
    required_missing = sorted(sid for c in classes for sid in by_class.get(c, {}).get("missing", []))
    return {"by_class": {k: {"present": sorted(v["present"]), "missing": sorted(v["missing"])} for k, v in sorted(by_class.items())},
            "not_in_catalog": unknown, "required_classes": classes, "required_missing": required_missing}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--world", required=True, help="world folder (the one holding level.dat)")
    p.add_argument("--dimension", default="overworld",
                   help="overworld, the_nether, the_end, or a path under the world like dimensions/ns/name")
    p.add_argument("--min-x", type=int, required=True)
    p.add_argument("--min-z", type=int, required=True)
    p.add_argument("--max-x", type=int, required=True)
    p.add_argument("--max-z", type=int, required=True)
    p.add_argument("--structures", default=str(ROOT / "data" / "structures.json"), help="catalog to check against")
    p.add_argument("--require-classes", default="PROGRESSION,LEGENDARY",
                   help="comma-separated classes whose absence is reported as required_missing")
    p.add_argument("--fail-on-missing", action="store_true", help="exit 1 when a required structure is missing")
    p.add_argument("--fail-on-incomplete", action="store_true", help="exit 1 when coverage_full is below 1.0")
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)
    import runtime_guard
    world = runtime_guard.check(a.world, "read")
    sub = DIM_DIRS.get(a.dimension, a.dimension)
    dim_root = world / sub if sub else world
    if not dim_root.is_dir():
        raise SystemExit("dimension folder not found: %s" % dim_root)
    if a.min_x > a.max_x or a.min_z > a.max_z:
        raise SystemExit("min must not exceed max")
    bounds = {"min_x": a.min_x, "min_z": a.min_z, "max_x": a.max_x, "max_z": a.max_z}
    report = audit(dim_root, bounds)
    report.update(world=str(world), dimension=a.dimension, bounds=bounds)
    classes = [c.strip() for c in a.require_classes.split(",") if c.strip()]
    cat_path = Path(a.structures)
    if cat_path.is_file():
        report["catalog"] = check_catalog(report, json.loads(cat_path.read_text(encoding="utf-8")), a.dimension, classes)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    missing = (report.get("catalog") or {}).get("required_missing", [])
    print("%s: full %d/%d chunks (%.1f%%), %d saved outside; %d structure starts %s; required missing: %s"
          % (a.dimension, report["chunks_full_inside"], report["chunks_expected_inside"], 100 * report["coverage_full"],
             report["chunks_saved_outside"], len(report["starts"]), report["starts_by_id"], missing or "none"))
    if a.fail_on_missing and missing:
        return 1
    if a.fail_on_incomplete and report["coverage_full"] < 1.0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
