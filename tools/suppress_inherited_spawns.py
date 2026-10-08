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
  - add one coordinate anticondition per box to every spawn detail, keeping any anticondition it already has
    (a singular "anticondition" object moves into the plural list)
  - add ONE more anticondition to every detail, {"dimensions": ["minecraft:the_nether"]} (NETHER_ANTICONDITION): it is
    satisfied anywhere in the Nether and nowhere else, so every inherited spawn is gone from the Nether and the
    overworld keeps exactly the suppression it had (the owner, 2026-10-08, approving docs/mechanics/NETHER_ENCOUNTERS.md
    Q3 "replace, not layer"; our own Nether tables are compiled pools in cobblers_spawns, which this tool never reads)
  - first, drop every detail (and herd member) of a species data/spawn_suppression.json removed_species lists, in
    every dimension and outside every box; a file left with no detail is re-emitted as the inherited file with
    "enabled": false (EXP-012 V4/V5). The list is the 22 paradoxes (the owner, 2026-10-08: paradoxes are dungeon
    content, never wild). Fails closed if the server's Cobblemon jar labels a paradox the list lacks, and, after
    writing, if any inherited path the server loads is still enabled and names a listed species (verify_removed_species)

The boxes stay plain minX/maxX/minZ/maxZ with no dimension. Bound to the overworld (review N153's first fix) they
grew the pack from 240.8 MB to 418.8 MB (relayed from that unit's measurement), and with every inherited Nether spawn
removed by the one Nether anticondition the binding has nothing left to protect there. In the End the plain boxes
still remove inherited spawns at the overworld boxes' x/z; the End is unreachable by decision
(docs/world-building/DIMENSIONS_AND_BORDERS.md) and nothing is authored there.

With --subregions the box set is the route corridors plus every sub-region polygon from data/regions.json, plus every
marine band box data/spawns.json marine_zones defines (tools/compile_spawns.py marine_bands). Without it,
only the corridors are suppressed, so the 43 million blocks the sub-region rosters cover keep their inherited spawns
and our rosters merely add to them: the regions read as vanilla with sprinkles.

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

import subregion_boxes

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_suppress"
POOL = re.compile(r"(?:.*/)?data/([^/]+)/spawn_pool_world/(.+\.json)$")
GRID = 8
# Cobblemon 1.8.0 SpawningCondition "dimensions" (docs/research/notes/spawn-dimension-condition-1.8.0.md): an
# anticondition naming only the Nether is satisfied at every Nether position and at no other, so it removes the detail
# in the Nether and changes nothing anywhere else. One per detail, not one per box.
NETHER = "minecraft:the_nether"
NETHER_ANTICONDITION = {"dimensions": [NETHER]}


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
            # our own packs are never inherited: cobblers_spawns holds the compiled pools, the Nether's
            # (spawn_pool_world/nether/) among them, so skipping it here is what keeps the Nether anticondition off
            # them (contract C19, tests/test_suppress_inherited_spawns.py test_our_compiled_pools_are_never_re_emitted)
            if p.name.startswith("cobblers_"):
                continue
            if p.suffix == ".zip":
                scan_zip("%s:%s" % (label, p.name), zipfile.ZipFile(p), sources)
            elif p.is_dir():
                scan_pack_dir("%s:%s" % (label, p.name), p, sources)
    return sources


def box_anticondition(box):
    """One suppression anticondition: the box, with no dimension (EXP-012's shape). It also matches the Nether and the
    End at the same x/z; in the Nether that is moot, because NETHER_ANTICONDITION already removes every inherited
    detail there (see the module docstring for why the per-box overworld binding of review N153 was reverted)."""
    x0, x1, z0, z1 = box
    return {"minX": x0, "maxX": x1, "minZ": z0, "maxZ": z1}


def suppress(doc, conds, nether=True):
    """Append the box anticonditions, then (nether) the one Nether anticondition, to every detail. Returns the count."""
    n = 0
    for s in doc.get("spawns", []):
        existing = s.pop("anticonditions", None) or []
        single = s.pop("anticondition", None)
        if single:
            existing = existing + [single]
        s["anticonditions"] = existing + conds + ([dict(NETHER_ANTICONDITION, dimensions=[NETHER])] if nether else [])
        n += 1
    return n


def species_token(pokemon):
    """The species of a detail's "pokemon" property string: its first word, lower case, any namespace dropped
    ("fearow held_item=cobblemon:flying_gem alpha=true" -> "fearow", "cobblemon:fluttermane" -> "fluttermane")."""
    words = str(pokemon or "").split()
    return words[0].lower().rsplit(":", 1)[-1] if words else ""


def remove_species(doc, removed):
    """Drop every detail of a removed species from doc (a herd loses those members, and the herd itself when none is
    left). Returns the number of details and herd members dropped."""
    n = 0
    keep = []
    for s in doc.get("spawns", []):
        if species_token(s.get("pokemon")) in removed:
            n += 1
            continue
        herd = s.get("herdablePokemon")
        if isinstance(herd, list):
            members = [h for h in herd if species_token(h.get("pokemon")) not in removed]
            n += len(herd) - len(members)
            if not members:
                continue
            s["herdablePokemon"] = members
        keep.append(s)
    if "spawns" in doc:
        doc["spawns"] = keep
    return n


def removed_species(path):
    """The species data/spawn_suppression.json removed_species lists (normalised as species_token does)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return {species_token(s) for s in doc["removed_species"]["species"]}


def jar_paradoxes(server):
    """The species the Cobblemon jar on this server labels "paradox", or None when no Cobblemon jar is there."""
    jars = sorted((Path(server) / "mods").glob("Cobblemon-fabric-*.jar"))
    if not jars:
        return None
    found = set()
    with zipfile.ZipFile(jars[0]) as z:
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                d = json.loads(z.read(n))
                if "paradox" in (d.get("labels") or []):
                    found.add(species_token(str(d.get("name", "")).replace(" ", "").replace("-", "")))
    return found


def _names_species(text, removed):
    """Removed species named as a "pokemon" value anywhere in a spawn file's raw text. Deliberately a text scan and
    not remove_species's walk, so a detail shape the walk does not know (a new herd key, a nested list) still shows."""
    hits = set()
    for m in re.finditer(r'"pokemon"\s*:\s*"([^"]*)"', text):
        sp = species_token(m.group(1))
        if sp in removed:
            hits.add(sp)
    return hits


def verify_removed_species(effective, out, removed):
    """Fail closed unless no inherited spawn file the server loads still names a removed species while enabled.

    For every inherited resource path: if its effective source names one, the pack must override that path with a file
    that is "enabled": false or names none. Every file the pack writes is scanned the same way. Returns the problems."""
    problems = []
    for key in sorted(k for k in effective if "\0" not in k):
        src = _names_species(effective[key + "\0raw"].decode("utf-8", "replace"), removed)
        ns, rel = key.split(":", 1)
        f = Path(out) / "data" / ns / "spawn_pool_world" / rel
        if not f.is_file():
            if src:
                problems.append("%s names %s and the pack does not override it" % (key, sorted(src)))
            continue
        text = f.read_text(encoding="utf-8")
        try:
            enabled = json.loads(text).get("enabled", True) is not False
        except ValueError:
            problems.append("%s: the pack's override does not parse" % key)
            continue
        left = _names_species(text, removed)
        if enabled and left:
            problems.append("%s: the pack's override is enabled and still names %s" % (key, sorted(left)))
    return problems


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server", required=True, help="server directory holding mods/ and datapacks/")
    p.add_argument("--world", required=True, help="a DISPOSABLE world directory (its datapacks/ are read)")
    p.add_argument("--routes", default=str(ROOT / "data" / "routes.json"))
    p.add_argument("--regions", default=str(ROOT / "data" / "regions.json"))
    p.add_argument("--spawns", default=str(ROOT / "data" / "spawns.json"),
                   help="read for its marine_zones, whose band boxes are suppressed with --subregions")
    p.add_argument("--waterways", default=str(ROOT / "data" / "waterways.json"))
    p.add_argument("--subregions", action="store_true",
                   help="suppress inside every sub-region polygon too, not only the route corridors: without this, "
                        "the 43 million blocks the sub-region rosters cover keep their inherited spawns and our "
                        "rosters only add to them")
    p.add_argument("--subregion-grid", type=int, default=32,
                   help="grid the sub-region polygons are rasterised on (must match tools/compile_spawns.py --grid)")
    p.add_argument("--boxes", choices=("raw", "merged"), default="merged")
    p.add_argument("--grid", type=int, default=16, help="merged only: snap the union outward to this grid (8 = exact; 16 is the EXP-012 choice)")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--suppression", default=str(ROOT / "data" / "spawn_suppression.json"),
                   help="read for removed_species: species no inherited pool may spawn anywhere")
    p.add_argument("--no-nether", action="store_true",
                   help="leave the inherited Nether spawns alone (the pack as it was before 2026-10-08); for "
                        "measurement and comparison only, never for an install")
    a = p.parse_args(argv)
    if "cobblers-10240" in Path(a.world).as_posix():
        raise SystemExit("refusing to read the live world")
    boxes = route_boxes(json.loads(Path(a.routes).read_text(encoding="utf-8")))
    route_box_count = len(boxes)
    import compile_spawns
    marine_box_count = 0
    if a.subregions:
        regions = json.loads(Path(a.regions).read_text(encoding="utf-8"))
        for sub in regions["subregions"]:
            boxes.extend(subregion_boxes.boxes_for(sub["polygons"], a.subregion_grid))
        # the marine bands (data/spawns.json marine_zones) are authored rosters too: without them the pack's own sea
        # spawns stay live over the band and swamp it (2026-09-26, the Windward Sea: Cobblemon's Magikarp herd at
        # weight 59.4, Wishiwashi's at 100 and Relicanth's at 1000 in the common bucket, against our 24s)
        spawns_doc = json.loads(Path(a.spawns).read_text(encoding="utf-8"))
        water = []
        if Path(a.waterways).is_file():
            import waterways as waterways_mod
            for w in json.loads(Path(a.waterways).read_text(encoding="utf-8"))["waterways"]:
                for _, _, bs in waterways_mod.boxes_by_segment(w["polyline"], w["half_width"], compile_spawns.WATERWAY_GRID):
                    water.extend(bs)
        marine = [b for bs in compile_spawns.marine_bands(spawns_doc, regions, json.loads(Path(a.routes).read_text(encoding="utf-8")),
                                                          water).values() for b in bs]
        marine_box_count = len(marine)
        boxes.extend(marine)
    # a spawn-free zone is suppressed whatever covers it: our compiled pools stay out of it too, so nothing spawns there
    boxes.extend(compile_spawns.spawn_free_zones())
    if a.boxes == "merged":
        boxes = merge_boxes(boxes, a.grid)
    conds = [box_anticondition(b) for b in boxes]
    removed = removed_species(a.suppression)
    labelled = jar_paradoxes(a.server)
    if labelled is not None and labelled - removed:
        raise SystemExit("the Cobblemon jar labels %s paradox and %s removed_species does not list it: a wild paradox "
                         "would stay live (the owner, 2026-10-08)" % (sorted(labelled - removed), a.suppression))
    sources = collect(Path(a.server), Path(a.world))
    effective = {}
    for src, path, raw in sources:
        effective.setdefault(path, []).append(src)
        effective[path + "\0raw"] = raw
    out = Path(a.out)
    stats = {"box_set": a.boxes, "grid": a.grid if a.boxes == "merged" else None, "boxes": len(boxes),
             "route_boxes": route_box_count, "subregions": bool(a.subregions), "marine_boxes": marine_box_count,
             "subregion_grid": a.subregion_grid if a.subregions else None, "source_files": len(sources), "paths": 0, "written": 0,
             "skipped_disabled": 0, "details": 0, "bytes": 0, "multi_source_paths": 0, "unparsed": [],
             "nether_suppressed": not a.no_nether, "removed_species": len(removed),
             "paradox_label_check": "no Cobblemon jar on this server" if labelled is None else len(labelled),
             "removed_species_details": 0, "disabled_paths": []}
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
        dropped = remove_species(doc, removed)
        stats["removed_species_details"] += dropped
        if dropped and not doc.get("spawns"):
            # every detail was a removed species: disable the inherited file at its path, the shape EXP-012 proved
            # (V4 a jar file, V5 a COBBLEVERSE-DP file), instead of re-emitting it suppressed
            doc = json.loads(effective[key + "\0raw"])
            doc["enabled"] = False
            stats["disabled_paths"].append(key)
        else:
            stats["details"] += suppress(doc, conds, nether=not a.no_nether)
        ns, rel = key.split(":", 1)
        f = out / "data" / ns / "spawn_pool_world" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
        f.write_text(text, encoding="utf-8", newline="\n")
        stats["written"] += 1
        stats["bytes"] += len(text.encode("utf-8"))
    # fail closed BEFORE pack.mcmeta and the manifest, so a failed run leaves no pack that reads as generated
    problems = verify_removed_species(effective, out, removed)
    if problems:
        (out / "pack.mcmeta").unlink(missing_ok=True)
        raise SystemExit("a removed species is still a live inherited spawn (%d): %s" % (len(problems), "; ".join(problems[:10])))
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers bounded suppression of inherited spawns (generated, local only)"}}), encoding="utf-8")
    stats["routes_sha256"] = hashlib.sha256(Path(a.routes).read_bytes()).hexdigest()
    (out / "manifest.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
