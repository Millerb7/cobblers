#!/usr/bin/env python
"""Compile data/underground_spawns.json into the wild spawns of the six dug systems (caves and mines).

Why it exists (the owner, 2026-10-22, "add pokemon to caves"): nothing spawned underground over most of the map.
tools/compile_spawns.py forces canSeeSky true on every land detail, and tools/suppress_inherited_spawns.py removes the
inherited details under every route and sub-region box at every height, so Cobblemon's own cave spawns went with them.

Output is its OWN pack, build/datapacks/cobblers_underground_spawns (a world pack in tools/reapply.py SPAWN_PACKS), not
more files in cobblers_spawns: the habitat, tiers, encounter and Nuzlocke audits read every file of that pack and grade
surface rosters. tools/suppress_inherited_spawns.py collect() skips every pack whose name starts with "cobblers_", so
the suppression's anticonditions are never added to these details (tests/test_underground_spawns.py checks it).

One file per system, data/cobblers/spawn_pool_world/underground/<system>.json (the path the Nether tables use). Every
detail is  {id, pokemon, type pokemon, spawnablePositionType grounded, bucket, level, weight, condition}, the shape
compile_spawns.build_nether writes, and its condition is the system's box (cut by keep_out, below) at the band's
minY..maxY with canSeeSky false and the overworld bound (compile_spawns.bind_dimension). Fields and their sources:
data/underground_spawns.json condition_fields.

keep_out: data/spawn_suppression.json spawn_free_zones and every data/towns.json footprint (padded 16) are cut out of
every box, at every height, with compile_spawns.subtract. A sweep over both files, not a list of ours. It does NOT cover
a placed structure that is not a town (the Route 1 mansion, trees): the world holds them and no footprint lists them.

  python tools/underground_spawns.py                 write the pack
  python tools/underground_spawns.py check           audit data and the written pack (jar checks run when the jar is on this machine)
  python tools/underground_spawns.py --out DIR       write somewhere else
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compile_spawns as CS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "underground_spawns.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_underground_spawns"
PACK = "cobblers_underground_spawns"
BANDS = ("shallow", "mid", "deep")
BUCKETS = ("common", "uncommon", "rare", "ultra-rare")
TOWN_PAD = 16
SUBDIR = "data/cobblers/spawn_pool_world/underground"
PACK_MCMETA = {"pack": {"pack_format": 48, "description": "Cobblers underground wild spawns (not runtime-proven)"}}


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def town_zones(towns_doc=None):
    """[(minX, maxX, minZ, maxZ)] of every town footprint padded TOWN_PAD."""
    if towns_doc is None:
        towns_doc = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))
    out = []
    for t in towns_doc["towns"]:
        f = t.get("footprint") or {}
        if "min_x" in f:
            out.append((f["min_x"] - TOWN_PAD, f["max_x"] + TOWN_PAD, f["min_z"] - TOWN_PAD, f["max_z"] + TOWN_PAD))
    return out


def keep_out():
    return list(CS.spawn_free_zones()) + town_zones()


def level_range(text):
    lo, _s, hi = str(text).partition("-")
    return int(lo), int(hi)


def system_parts(system, zones):
    """The system's box as (minX, maxX, minZ, maxZ) parts outside every keep-out zone."""
    x0, z0, x1, z1 = system["pool_box"]
    return CS.subtract((x0, x1, z0, z1), zones)


def system_details(system, zones):
    parts = system_parts(system, zones)
    out = []
    for band in BANDS:
        b = system["bands"][band]
        for n, (px0, px1, pz0, pz1) in enumerate(parts):
            for species, level, bucket, weight in b["entries"]:
                cond = {"minX": px0, "maxX": px1, "minY": b["minY"], "maxY": b["maxY"], "minZ": pz0, "maxZ": pz1,
                        "canSeeSky": False}
                CS.bind_dimension(cond)
                out.append({"id": "ug_%s_%s_b%02d_%s" % (system["id"], band, n, species), "pokemon": species,
                            "type": "pokemon", "spawnablePositionType": "grounded", "bucket": bucket, "level": level,
                            "weight": float(weight), "condition": cond})
    return out, parts


def build(doc, zones=None):
    """{relative path: text} for the pack, and a per-system summary."""
    zones = keep_out() if zones is None else zones
    files = {"pack.mcmeta": CS.dumps(PACK_MCMETA)}
    summary = []
    for s in doc["systems"]:
        details, parts = system_details(s, zones)
        ids = [d["id"] for d in details]
        if len(set(ids)) != len(ids):
            raise SystemExit("%s: spawn ids are used more than once" % s["id"])
        pool = {"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [], "spawns": details}
        files["%s/%s.json" % (SUBDIR, s["id"])] = CS.dumps(pool)
        summary.append({"system": s["id"], "kind": s["kind"], "box_parts": len(parts), "details": len(details),
                        "species": sorted({d["pokemon"] for d in details})})
    return files, summary


def write(doc, out):
    files, summary = build(doc)
    out = Path(out)
    wanted = {(out / rel).resolve() for rel in files}
    for old in out.glob("data/*/spawn_pool_world/**/*.json"):
        if old.resolve() not in wanted:
            old.unlink()
    for rel, text in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    manifest = {"generator": "tools/underground_spawns.py",
                "inputs": {"data/underground_spawns.json": hashlib.sha256(DATA.read_bytes()).hexdigest()},
                "files": {rel: hashlib.sha256(t.encode("utf-8")).hexdigest() for rel, t in sorted(files.items())},
                "systems": summary}
    (out / "manifest.json").write_text(CS.dumps(manifest), encoding="utf-8", newline="\n")
    return files, summary


# ---------------------------------------------------------------------------------------------------- the audit

def jar_species():
    """({species id: [(result species, minLevel)]}, jar name) or (None, reason). Reads the Cobblemon 1.8 jar's species files."""
    try:
        import battle_sim
        jar = battle_sim.find_jar()
    except Exception as exc:                      # no jar on this machine
        return None, str(exc)
    evo = {}
    with zipfile.ZipFile(jar) as z:
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                d = json.loads(z.read(n))
                rows = []
                for e in d.get("evolutions") or []:
                    for r in e.get("requirements") or []:
                        if r.get("variant") == "level" and "minLevel" in r:
                            rows.append((str(e.get("result", "")).split()[0].lower(), int(r["minLevel"])))
                evo[Path(n).stem.lower()] = rows
    return evo, Path(jar).name


def forbidden_species():
    d = json.loads((ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))
    return set(d["removed_species"]["species"]) | set(d["managed_species"]["species"])


def overlaps(a, b):
    """Inclusive (x0, x1, z0, z1) boxes."""
    return not (a[1] < b[0] or a[0] > b[1] or a[3] < b[2] or a[2] > b[3])


def audit(doc, pack):
    """Problems (a list of strings) from the authored table and the written pack. Reads the pack from disk."""
    problems = []
    pack = Path(pack)
    zones = keep_out()
    evo, jar = jar_species()
    pre = {}
    if evo:
        for s, rows in evo.items():
            for res, lvl in rows:
                pre[res] = max(pre.get(res, 0), lvl)
    banned = forbidden_species()
    seen = set()
    for s in doc["systems"]:
        sid = s["id"]
        seen.add(sid)
        x0, z0, x1, z1 = s["pool_box"]
        f = pack / SUBDIR / ("%s.json" % sid)
        if not f.is_file():
            problems.append("%s: no pool file %s" % (sid, f))
            continue
        details = json.loads(f.read_text(encoding="utf-8"))["spawns"]
        ids = [d["id"] for d in details]
        if len(set(ids)) != len(ids):
            problems.append("%s: repeated spawn ids" % sid)
        prev_min = None
        for band in BANDS:
            b = (s.get("bands") or {}).get(band)
            if not b or not b.get("entries"):
                problems.append("%s: no %s pool" % (sid, band))
                continue
            if not any(e[2] == "common" for e in b["entries"]):
                problems.append("%s %s: no common entry" % (sid, band))
            if not any(e[2] in ("rare", "ultra-rare") for e in b["entries"]) and band == "deep":
                problems.append("%s deep: no rare pick" % sid)
            if b["minY"] > b["maxY"]:
                problems.append("%s %s: minY over maxY" % (sid, band))
            # the bands tile the depth range: each one starts right under the one above it
            if prev_min is not None and b["maxY"] != prev_min - 1:
                problems.append("%s %s: maxY %d is not one under the band above (minY %d)" % (sid, band, b["maxY"], prev_min))
            prev_min = b["minY"]
            mine = [d for d in details if d["id"].startswith("ug_%s_%s_" % (sid, band))]
            if len(mine) < len(b["entries"]):
                problems.append("%s %s: pool file has %d details for %d entries" % (sid, band, len(mine), len(b["entries"])))
            for sp, lv, bucket, w in b["entries"]:
                lo, hi = level_range(lv)
                if bucket not in BUCKETS or w <= 0:
                    problems.append("%s %s %s: bad bucket or weight" % (sid, band, sp))
                if not (1 <= lo <= hi <= s["cap"]):
                    problems.append("%s %s %s: level %s outside 1..cap %d" % (sid, band, sp, lv, s["cap"]))
                if sp in banned:
                    problems.append("%s %s %s: a removed or managed species" % (sid, band, sp))
                if evo is not None:
                    if sp not in evo:
                        problems.append("%s %s %s: not a species in %s" % (sid, band, sp, jar))
                    elif lo < pre.get(sp, 0):
                        problems.append("%s %s %s: level %d is under the level %d its pre-evolution needs" % (sid, band, sp, lo, pre[sp]))
            for d in mine:
                c = d["condition"]
                if c.get("canSeeSky") is not False:
                    problems.append("%s: %s is not canSeeSky false" % (sid, d["id"]))
                if c.get("dimensions") != ["minecraft:overworld"]:
                    problems.append("%s: %s is not bound to the overworld" % (sid, d["id"]))
                if (c.get("minY"), c.get("maxY")) != (b["minY"], b["maxY"]):
                    problems.append("%s: %s y range is not its band's" % (sid, d["id"]))
                box = (c["minX"], c["maxX"], c["minZ"], c["maxZ"])
                if box[0] < x0 or box[1] > x1 or box[2] < z0 or box[3] > z1:
                    problems.append("%s: %s reaches outside the system box" % (sid, d["id"]))
                if any(overlaps(box, z) for z in zones):
                    problems.append("%s: %s overlaps a town or spawn-free zone" % (sid, d["id"]))
                if "anticonditions" in d or "anticondition" in d:
                    problems.append("%s: %s carries an anticondition" % (sid, d["id"]))
    extra = sorted(p.stem for p in (pack / SUBDIR).glob("*.json") if p.stem not in seen) if (pack / SUBDIR).is_dir() else []
    if extra:
        problems.append("pool files no system names: %s" % extra)
    if evo is None:
        print("jar checks NOT run: %s" % jar)
    return problems


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", nargs="?", default="build", choices=("build", "check"))
    p.add_argument("--data", default=str(DATA))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    doc = load(a.data)
    if a.command == "check":
        problems = audit(doc, a.out)
        for q in problems:
            print("PROBLEM", q)
        print("underground spawns audit: %d problem(s)" % len(problems))
        return 1 if problems else 0
    files, summary = write(doc, a.out)
    for q in summary:
        print("  %s (%s): %d box parts, %d details, %d species" % (q["system"], q["kind"], q["box_parts"], q["details"], len(q["species"])))
    print("wrote %d files to %s" % (len(files) + 1, a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
