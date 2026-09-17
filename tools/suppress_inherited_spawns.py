#!/usr/bin/env python
"""Generate the bounded-suppression override pack: every inherited spawn file, re-emitted with the route boxes as anticonditions.

EXP-012 proved the native mechanism on single files: a spawn detail's "anticonditions" list (plural key; the singular
"anticondition" with an array aborts the whole reload) carrying coordinate boxes removes that detail inside the boxes
and nowhere else, and a file at the same resource path in a higher-priority pack replaces the inherited one. This tool
applies it to every inherited file:

  - read every data/<ns>/spawn_pool_world/**.json the server can load: mod jars (and datapacks nested in them),
    global datapacks (<server>/datapacks) and world datapacks (<world>/datapacks), in load order
  - per resource path take the effective file (the highest-priority source); skip our own cobblers_* packs and
    files already "enabled": false
  - add one coordinate anticondition per route box to every spawn detail, keeping any anticondition it already has
    (a singular "anticondition" object moves into the plural list)

Box sets (--boxes):
  raw     the 1,408 data/routes.json spawn_scope boxes as they are
  merged  the same union re-cut into fewer rectangles; with --grid 8 (the grid the boxes share) coverage is identical,
          with --grid 16/32/64 the union is snapped outward to that grid first (overshoot under one cell per edge)

  python tools/suppress_inherited_spawns.py --server <server dir> --world <disposable world dir> [--boxes merged --grid N] [--out DIR]

Output is generated build/ content (gitignored). It contains upstream spawn data (Cobblemon, COBBLEVERSE and addon
files re-emitted), so it must never be committed or redistributed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_suppress"
POOL = re.compile(r"(?:.*/)?data/([^/]+)/spawn_pool_world/(.+\.json)$")
GRID = 8


def route_boxes(routes):
    return [(b["min_x"], b["max_x"], b["min_z"], b["max_z"]) for r in routes["routes"] for b in r["spawn_scope"]["boxes"]]


def merge_boxes(boxes, grid=GRID):
    """Re-cut the union of inclusive boxes into rectangles: runs per row of grid cells, then equal runs stacked.

    A grid coarser than the boxes' own 8 blocks snaps the union outward (a cell is excluded if any box touches
    it), so the exclusion overshoots each box edge by less than one cell: fewer rectangles, a wider zone."""
    if grid % GRID:
        raise SystemExit("grid must be a multiple of %d" % GRID)
    cells = set()
    for x0, x1, z0, z1 in boxes:
        if x0 % GRID or (x1 + 1) % GRID or z0 % GRID or (z1 + 1) % GRID:
            raise SystemExit("box %s is not on the %d-block grid" % ((x0, x1, z0, z1), GRID))
        for cx in range(x0 // grid, x1 // grid + 1):
            for cz in range(z0 // grid, z1 // grid + 1):
                cells.add((cx, cz))
    rows = {}
    for cx, cz in cells:
        rows.setdefault(cz, []).append(cx)
    open_runs, done = {}, []
    for cz in sorted(rows):
        xs = sorted(rows[cz])
        runs, start = [], xs[0]
        for a, b in zip(xs, xs[1:] + [None]):
            if b != a + 1:
                runs.append((start, a))
                start = b
        nxt = {}
        for run in runs:
            if run in open_runs and open_runs[run][1] == cz - 1:
                nxt[run] = (open_runs[run][0], cz)
            else:
                nxt[run] = (cz, cz)
        for run, span in open_runs.items():
            if run not in nxt or nxt[run][0] != span[0]:
                done.append((run, span))
        open_runs = nxt
    done.extend(open_runs.items())
    out = [(r[0] * grid, (r[1] + 1) * grid - 1, s[0] * grid, (s[1] + 1) * grid - 1) for r, s in done]
    covered = {(cx, cz) for x0, x1, z0, z1 in out for cx in range(x0 // grid, (x1 + 1) // grid) for cz in range(z0 // grid, (z1 + 1) // grid)}
    if covered != cells or sum((x1 - x0 + 1) * (z1 - z0 + 1) for x0, x1, z0, z1 in out) != len(cells) * grid * grid:
        raise SystemExit("merged boxes do not reproduce the union exactly")
    return sorted(out)


def scan_zip(label, zf, sources):
    for n in zf.namelist():
        m = POOL.match(n)
        if m:
            # a jar's nested resource/data packs are separate packs; only top-level data/ is the mod's own pack
            sources.append((label if n.startswith("data/") else "%s!%s" % (label, n.split("data/")[0].rstrip("/")),
                            "%s:%s" % m.groups(), zf.read(n)))
        elif n.endswith(".zip"):
            try:
                scan_zip("%s!%s" % (label, n), zipfile.ZipFile(io.BytesIO(zf.read(n))), sources)
            except zipfile.BadZipFile:
                pass


def scan_pack_dir(label, root, sources):
    for f in sorted(root.rglob("*.json")):
        m = POOL.match(f.relative_to(root).as_posix())
        if m:
            sources.append((label, "%s:%s" % m.groups(), f.read_bytes()))


def collect(server, world):
    """(source, resource path, bytes) lowest priority first: mods, global datapacks, world datapacks."""
    sources = []
    for jar in sorted((server / "mods").glob("*.jar")):
        try:
            with zipfile.ZipFile(jar) as z:
                scan_zip("mod:" + jar.name, z, sources)
        except zipfile.BadZipFile:
            pass
    for label, d in (("global", server / "datapacks"), ("world", world / "datapacks")):
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.name.startswith("cobblers_"):
                continue
            if p.suffix == ".zip":
                scan_zip("%s:%s" % (label, p.name), zipfile.ZipFile(p), sources)
            elif p.is_dir():
                scan_pack_dir("%s:%s" % (label, p.name), p, sources)
    return sources


def suppress(doc, conds):
    n = 0
    for s in doc.get("spawns", []):
        existing = s.pop("anticonditions", None) or []
        single = s.pop("anticondition", None)
        if single:
            existing = existing + [single]
        s["anticonditions"] = existing + conds
        n += 1
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server", required=True, help="server directory holding mods/ and datapacks/")
    p.add_argument("--world", required=True, help="a DISPOSABLE world directory (its datapacks/ are read)")
    p.add_argument("--routes", default=str(ROOT / "data" / "routes.json"))
    p.add_argument("--boxes", choices=("raw", "merged"), default="merged")
    p.add_argument("--grid", type=int, default=16, help="merged only: snap the union outward to this grid (8 = exact; 16 is the EXP-012 choice)")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    if "cobblers-10240" in Path(a.world).as_posix():
        raise SystemExit("refusing to read the live world")
    boxes = route_boxes(json.loads(Path(a.routes).read_text(encoding="utf-8")))
    if a.boxes == "merged":
        boxes = merge_boxes(boxes, a.grid)
    conds = [{"minX": x0, "maxX": x1, "minZ": z0, "maxZ": z1} for x0, x1, z0, z1 in boxes]
    sources = collect(Path(a.server), Path(a.world))
    effective = {}
    for src, path, raw in sources:
        effective.setdefault(path, []).append(src)
        effective[path + "\0raw"] = raw
    out = Path(a.out)
    stats = {"box_set": a.boxes, "grid": a.grid if a.boxes == "merged" else None, "boxes": len(boxes), "source_files": len(sources), "paths": 0, "written": 0,
             "skipped_disabled": 0, "details": 0, "bytes": 0, "multi_source_paths": 0, "unparsed": []}
    for key in sorted(k for k in effective if "\0" not in k):
        stats["paths"] += 1
        if len(effective[key]) > 1:
            stats["multi_source_paths"] += 1
        try:
            doc = json.loads(effective[key + "\0raw"])
        except ValueError:
            stats["unparsed"].append(key)
            continue
        if doc.get("enabled", True) is False:
            stats["skipped_disabled"] += 1
            continue
        stats["details"] += suppress(doc, conds)
        ns, rel = key.split(":", 1)
        f = out / "data" / ns / "spawn_pool_world" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
        f.write_text(text, encoding="utf-8", newline="\n")
        stats["written"] += 1
        stats["bytes"] += len(text.encode("utf-8"))
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers bounded suppression of inherited spawns (generated, local only)"}}), encoding="utf-8")
    stats["routes_sha256"] = hashlib.sha256(Path(a.routes).read_bytes()).hexdigest()
    (out / "manifest.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
