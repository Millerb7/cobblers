#!/usr/bin/env python
"""Stop worldgen placing gym copies, League copies and legendary altars in the Nether and the End.

data/dimension_overrides.json is the source. It lists the upstream structure_sets that can place, in a Nether or
End biome, a structure carrying an rctmod trainer spawner, a command-block summon or a legendary encounter, and
says for each whether it is SUPPRESSED, KEPT (a recorded decision) or NOT COVERED (in an optional pack this world
never enabled). The pack overrides each suppressed set at its own namespace path with the same structures and
placement plus "frequency": 0.0, so worldgen never picks a start for it. The structure definitions are not
touched, and our own copies are pasted with `place template`, which never reads a structure_set.

  python tools/dimension_overrides.py                    # build build/datapacks/cobblers_dimension_overrides
  python tools/dimension_overrides.py build --out <dir>
  python tools/dimension_overrides.py audit --roots <mods dir> <datapacks dir> [--pack <built pack>]
  python tools/dimension_overrides.py count              # expected candidate starts per set (method in --help)

THE AUDIT IS INDEPENDENT OF THE DATA FILE. It scans the upstream jars and datapacks it is given (zips, jars and
folder packs, nested jars included), resolves every structure's biomes through the biome tags those packs ship
(plus vanilla's #minecraft:is_nether and #minecraft:is_end), and calls a structure dangerous when it can start in a
Nether or End biome AND either one of its templates (the template at its own path, and every element of its start
pool) holds `rctmod:trainer_spawner` or `command_block`, or data/adopted_legendary_sites.json's catalogue names it
as a legendary's template. Every dangerous structure's set must then be suppressed in the BUILT pack with the
upstream structures and placement, or declared kept, or declared not covered with every source optional.

What this does NOT cover:
  - the overworld: it needs nothing, since the export writes every chunk and worldgen places no structure there;
  - structures pieced together deeper than the start pool (a jigsaw's later pools are not opened);
  - Legendary Monuments' own Distortion World, and any other modded dimension;
  - chunks generated before the pack is installed: they keep whatever they placed;
  - anything placed by a feature rather than a structure (the Ruinous stakes, for one).

Ownership: the output is generated and lives in build/ (gitignored); data/dimension_overrides.json is the source.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "dimension_overrides.json"
CATALOGUE = ROOT / "data" / "adopted_legendary_sites.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_dimension_overrides"
PACK = "cobblers_dimension_overrides"
PACK_FORMAT = 48
FREQUENCY = 0.0

# vanilla 1.21.1's dimension biome tags (data/minecraft/tags/worldgen/biome/is_nether.json and is_end.json in the
# Minecraft jar, which is not in the scanned folders); packs may add to them and the scan merges what they add
NETHER = frozenset({"minecraft:nether_wastes", "minecraft:soul_sand_valley", "minecraft:crimson_forest",
                    "minecraft:warped_forest", "minecraft:basalt_deltas"})
END = frozenset({"minecraft:the_end", "minecraft:end_highlands", "minecraft:end_midlands",
                 "minecraft:small_end_islands", "minecraft:end_barrens"})
VANILLA_TAGS = {"minecraft:is_nether": NETHER, "minecraft:is_end": END}
MARKERS = (b"rctmod:trainer_spawner", b"command_block")
JSON_RX = re.compile(r"^data/([^/]+)/(worldgen/structure_set|worldgen/structure|worldgen/template_pool|"
                     r"tags/worldgen/biome)/(.+)\.json$")
NBT_RX = re.compile(r"^data/([^/]+)/structures?/(.+)\.nbt$")


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _rid(s):
    return s if ":" in s else "minecraft:" + s


def set_path(set_id):
    ns, path = set_id.split(":", 1)
    return Path("data") / ns / "worldgen" / "structure_set" / (path + ".json")


def override_json(entry):
    """The file that replaces one upstream structure_set: its structures and placement, never placing."""
    placement = dict(entry["placement"])
    placement["frequency"] = FREQUENCY
    return {"structures": [dict(s) for s in entry["structures"]], "placement": placement}


def files(data=None):
    data = data or load()
    out = {"pack.mcmeta": {"pack": {"pack_format": PACK_FORMAT,
                                    "description": "Cobblers: no gym, League or legendary copies in the Nether "
                                                   "or the End (data/dimension_overrides.json)"}}}
    for e in data["suppress"]:
        out[set_path(e["structure_set"]).as_posix()] = override_json(e)
    return out


def build(out=DEFAULT_OUT, data=None):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    written = files(data)
    for rel, obj in written.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    return sorted(written)


# ------------------------------------------------------------------ the independent scan

class Scan:
    def __init__(self):
        self.sets = {}        # id -> [(source, data)]
        self.structures = {}  # id -> [(source, data)]
        self.pools = {}       # id -> data
        self.tags = {}        # id -> set of entries
        self.nbt = {}         # id -> set of markers found

    def add_json(self, source, name, raw):
        m = JSON_RX.match(name)
        if not m:
            return
        ns, kind, path = m.groups()
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except ValueError:
            return
        if kind == "tags/worldgen/biome":
            vals = set()
            for v in data.get("values", []):
                vals.add(v.get("id") if isinstance(v, dict) else v)
            self.tags.setdefault(ns + ":" + path, set()).update(vals)
            return
        rid = ns + ":" + path
        if kind == "worldgen/structure_set":
            self.sets.setdefault(rid, []).append((source, data))
        elif kind == "worldgen/structure":
            self.structures.setdefault(rid, []).append((source, data))
        else:
            self.pools[rid] = data

    def add_nbt(self, name, raw):
        m = NBT_RX.match(name)
        if not m:
            return
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
        found = {k.decode() for k in MARKERS if k in raw}
        self.nbt.setdefault(m.group(1) + ":" + m.group(2), set()).update(found)

    def add_zip(self, z, source):
        for n in z.namelist():
            if n.endswith((".jar", ".zip")):
                try:
                    self.add_zip(zipfile.ZipFile(io.BytesIO(z.read(n))), source + "!" + n)
                except zipfile.BadZipFile:
                    pass
            elif n.endswith(".json"):
                self.add_json(source, n, z.read(n))
            elif n.endswith(".nbt"):
                self.add_nbt(n, z.read(n))

    def add_root(self, root):
        root = Path(root)
        paths = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for p in paths:
            source = p.name if root.is_file() else p.relative_to(root).as_posix()
            if PACK in source:
                continue                               # our own override, installed: never upstream

            if p.suffix in (".jar", ".zip"):
                try:
                    self.add_zip(zipfile.ZipFile(p), source)
                except zipfile.BadZipFile:
                    pass
                continue
            rel = p.relative_to(root).as_posix() if not root.is_file() else p.name
            i = rel.find("data/")
            if i < 0 or (i > 0 and rel[i - 1] != "/"):
                continue
            if p.suffix == ".json":
                self.add_json(rel[:i].rstrip("/") or root.name, rel[i:], p.read_bytes())
            elif p.suffix == ".nbt":
                self.add_nbt(rel[i:], p.read_bytes())

    def biomes(self, entry, seen=()):
        out = set()
        if isinstance(entry, list):
            for e in entry:
                out |= self.biomes(e, seen)
        elif isinstance(entry, str):
            if entry.startswith("#"):
                t = _rid(entry[1:])
                if t not in seen:
                    for v in self.tags.get(t, set()) | set(VANILLA_TAGS.get(t, ())):
                        if isinstance(v, str):
                            out |= self.biomes(v, seen + (t,))
            else:
                out.add(_rid(entry))
        return out

    def templates(self, sid, data):
        out = {sid}
        pool = self.pools.get(_rid(data.get("start_pool", "")) if data.get("start_pool") else "", {})
        for el in pool.get("elements", []):
            loc = (el.get("element") or {}).get("location")
            if isinstance(loc, str):
                out.add(_rid(loc))
        return out


def scan(roots):
    s = Scan()
    for r in roots:
        s.add_root(r)
    return s


def legendary_templates(path=CATALOGUE):
    cat = json.loads(Path(path).read_text(encoding="utf-8"))["catalogue_2026_10_06"]["templates"]
    return {c["template"]: c["legendary"] for c in cat if c.get("legendary")}


def optional(source, names):
    return any(n in source for n in names) or "extra/" in source.replace("\\", "/")


def dangers(s, legendaries):
    """{structure id: (dimensions, reasons)} for every structure that can start in a Nether or End biome and
    carries a trainer spawner, a command block, or a catalogued legendary."""
    out = {}
    for sid, defs in s.structures.items():
        data = defs[-1][1]
        b = s.biomes(data.get("biomes", []))
        dims = (["the_nether"] if b & NETHER else []) + (["the_end"] if b & END else [])
        if not dims:
            continue
        reasons = sorted({m for t in s.templates(sid, data) for m in s.nbt.get(t, ())})
        if sid in legendaries:
            reasons.append("legendary: " + legendaries[sid])
        if reasons:
            out[sid] = (dims, reasons)
    return out


def audit(roots, pack=DEFAULT_OUT, data=None, legendaries=None):
    data = data or load()
    legendaries = legendaries if legendaries is not None else legendary_templates()
    s = scan(roots)
    opt = data.get("optional_packs", [])
    problems = []
    declared = {}
    for kind in ("suppress", "kept", "not_covered"):
        for e in data.get(kind, []):
            if e["structure_set"] in declared:
                problems.append("%s: declared twice (%s and %s)" % (e["structure_set"], declared[e["structure_set"]], kind))
            declared[e["structure_set"]] = kind
    found = dangers(s, legendaries)
    for sid, (dims, reasons) in sorted(found.items()):
        homes = sorted(k for k, v in s.sets.items() if any(x.get("structure") == sid for x in v[-1][1].get("structures", [])))
        if not homes:
            continue                                   # in no set: worldgen never places it
        for set_id in homes:
            kind = declared.get(set_id)
            if kind is None:
                problems.append("%s (set %s) can start in %s and carries %s: neither suppressed, kept nor declared "
                                "not covered" % (sid, set_id, "/".join(dims), ", ".join(reasons)))
            elif kind == "not_covered" and not all(optional(src, opt) for src, _ in s.sets[set_id]):
                problems.append("%s: declared not covered, but it ships in a pack this world always loads (%s)"
                                % (set_id, ", ".join(src for src, _ in s.sets[set_id])))
    built = Path(pack)
    if not (built / "pack.mcmeta").is_file():
        problems.append("%s: not built (no pack.mcmeta)" % built)
    for e in data.get("suppress", []):
        set_id = e["structure_set"]
        ups = [(src, d) for src, d in s.sets.get(set_id, []) if not optional(src, opt)]
        if not ups:
            problems.append("%s: suppressed, but no pack this world always loads defines it" % set_id)
            continue
        for st in ups[-1][1].get("structures", []):
            if not any(not optional(src, opt) for src, _ in s.structures.get(st["structure"], [])):
                problems.append("%s: names %s, which only an optional pack defines (an unbound reference fails "
                                "the registry load)" % (set_id, st["structure"]))
        f = built / set_path(set_id)
        if not f.is_file():
            problems.append("%s: no override in the built pack (%s)" % (set_id, f))
            continue
        got = json.loads(f.read_text(encoding="utf-8"))
        # the literal 0.0, never the generator's FREQUENCY: an expectation shared with the builder proves nothing
        for src, up in ups:                            # every copy scanned must agree with what we override
            expect = {"structures": up.get("structures", []),
                      "placement": dict(up.get("placement", {}), frequency=0.0)}
            if got != expect:
                problems.append("%s: the built override is not %s's set with frequency 0.0:\n    built    %s\n"
                                "    upstream %s" % (set_id, src, json.dumps(got, sort_keys=True),
                                                     json.dumps(expect, sort_keys=True)))
    return problems, found


# ------------------------------------------------------------------ the count

def _axis_offsets(k, spread):
    """Probability of each offset 0..k-1 inside a region (vanilla RandomSpreadType: linear nextInt(k), triangular
    (nextInt(k) + nextInt(k)) / 2)."""
    if spread == "triangular":
        p = [0.0] * k
        for a in range(k):
            for b in range(k):
                p[(a + b) // 2] += 1.0 / (k * k)
        return p
    return [1.0 / k] * k


def expected_candidates(placement, lo, hi, exclude_radius=0):
    """Expected number of candidate start chunks a random_spread set has inside the block window lo..hi (both axes),
    over every possible seed. Exact for the placement grid; it counts attempts, not structures: each becomes a
    start only if the biome at it is one the structure takes, which this cannot know without the generator."""
    sp, sep = placement["spacing"], placement["separation"]
    off = _axis_offsets(sp - sep, placement.get("spread_type", "linear"))
    clo, chi = lo // 16, hi // 16
    regions = range(clo // sp - 1, chi // sp + 2)
    axis = {}
    for i in regions:
        axis[i] = [(i * sp + o, p) for o, p in enumerate(off) if clo <= i * sp + o <= chi]
    if not exclude_radius:
        s = sum(p for i in regions for _c, p in axis[i])
        return s * s
    r2 = (exclude_radius / 16.0) ** 2
    total = 0.0
    for i in regions:
        for j in regions:
            for cx, px in axis[i]:
                for cz, pz in axis[j]:
                    if (cx + 0.5) ** 2 + (cz + 0.5) ** 2 >= r2:
                        total += px * pz
    return total


def counts(data=None):
    data = data or load()
    w = data["count_windows"]
    rows = []
    for kind in ("suppress", "kept"):
        for e in data[kind]:
            if e["dimension"] == "the_nether":
                a = expected_candidates(e["placement"], w["the_nether_unscaled"]["min"], w["the_nether_unscaled"]["max"])
                b = expected_candidates(e["placement"], w["the_nether_centre_over_8"]["min"],
                                        w["the_nether_centre_over_8"]["max"])
            else:
                a = b = expected_candidates(e["placement"], w["the_end"]["min"], w["the_end"]["max"],
                                            w["the_end"]["exclude_radius"])
            rows.append((kind, e["structure_set"], e["dimension"], a, b))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(DEFAULT_OUT))
    au = sub.add_parser("audit")
    au.add_argument("--roots", nargs="+", required=True, help="mods and datapacks folders, or single jars/zips")
    au.add_argument("--pack", default=str(DEFAULT_OUT))
    sub.add_parser("count")
    a = ap.parse_args(argv)
    if a.cmd in (None, "build"):
        out = getattr(a, "out", str(DEFAULT_OUT))
        written = build(out)
        print("built %s: %d structure_set overrides" % (out, len(written) - 1))
        return 0
    if a.cmd == "count":
        print("set | dimension | expected candidates (Nether: unscaled window ; centre/8 window)")
        for kind, sid, dim, x, y in counts():
            print("%-8s %-38s %-10s %7.1f ; %7.1f" % (kind, sid, dim, x, y))
        return 0
    problems, found = audit(a.roots, a.pack)
    print("dimension_overrides audit: %d dangerous structures found in the Nether/End, %d problems"
          % (len(found), len(problems)))
    for sid, (dims, reasons) in sorted(found.items()):
        print("  found %s [%s] %s" % (sid, "/".join(dims), ", ".join(reasons)))
    for p in problems:
        print("PROBLEM " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
