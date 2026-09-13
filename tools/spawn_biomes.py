#!/usr/bin/env python
"""Enumerate the biomes and biome tags Cobblemon spawns are attached to, from the pack.

Reads the actual jars and datapacks of a server directory, never a remembered
list:

  vanilla   versions/<mc>/server-<mc>.jar (biome registry, vanilla biome tags)
  mods      mods/*.jar and their nested META-INF/jars/*.jar
  datapacks datapacks/*.zip and datapack folders; datapacks/extra/ only with
            --include-extra, because the server does not load it

Two scopes:

  default   spawn pools from the Cobblemon jar alone, resolved against every
            loaded tag: "what Cobblemon's default spawn files reference"
  pack      spawn pools after mods and datapacks override them by path, which
            is what the server actually runs

Every biome and tag referenced by a spawn condition or anticondition is
resolved to concrete biome IDs. When --regions is given, each reference is
checked against the biomes the region plan paints (plus its planned tag
overlays), and each spawn entry is checked for reachability: some planned
biome satisfies its condition biomes and none of its anticondition biomes.
Non-biome conditions (light, Y, structures, nearby blocks) are not evaluated.

  python tools/spawn_biomes.py --server-dir ../cobblers-server --regions data/regions.json \\
      --markdown docs/world-building/BIOME_COVERAGE_MATRIX.md
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPAWN_RE = re.compile(r"^data/([^/]+)/spawn_pool_world/(.+\.json)$")
TAG_RE = re.compile(r"^data/([^/]+)/tags/worldgen/biome/(.+)\.json$")
BIOME_RE = re.compile(r"^data/([^/]+)/worldgen/biome/(.+)\.json$")
DIMENSION_TAGS = (("overworld", "#minecraft:is_overworld"),
                  ("nether", "#minecraft:is_nether"),
                  ("end", "#minecraft:is_end"))


# ------------------------------------------------------------------ reading


class Pack:
    """A named source of data files: a jar, a zip or a folder."""

    def __init__(self, name, kind, files):
        self.name, self.kind, self.files = name, kind, files  # files: path -> bytes loader

    def read_json(self, path):
        raw = self.files[path]()
        # a handful of pack files carry a BOM or trailing commas; be strict on
        # everything else
        return json.loads(raw.decode("utf-8-sig"))


def _zip_files(zf, prefix_filter=("data/", "fabric.mod.json", "META-INF/jars/")):
    out = {}
    for n in zf.namelist():
        if n.endswith("/"):
            continue
        if n.startswith(prefix_filter):
            out[n] = (lambda zf=zf, n=n: zf.read(n))
    return out


def open_jar(path_or_bytes, name, kind, nested=True):
    """A jar and, recursively, the jars nested in META-INF/jars/."""
    zf = zipfile.ZipFile(path_or_bytes if not isinstance(path_or_bytes, bytes)
                         else io.BytesIO(path_or_bytes))
    files = _zip_files(zf)
    packs = [Pack(name, kind, {k: v for k, v in files.items() if not k.startswith("META-INF/jars/")})]
    if nested:
        for n in sorted(k for k in files if k.startswith("META-INF/jars/") and k.endswith(".jar")):
            packs += open_jar(files[n](), "%s!%s" % (name, n.rsplit("/", 1)[-1]), kind)
    return packs


def open_folder(path, name, kind):
    path = Path(path)
    files = {}
    for p in path.rglob("*"):
        if p.is_file():
            rel = p.relative_to(path).as_posix()
            if rel.startswith("data/"):
                files[rel] = (lambda p=p: p.read_bytes())
    return Pack(name, kind, files)


def mod_ids(packs):
    ids = set()
    for pk in packs:
        if "fabric.mod.json" in pk.files:
            try:
                ids.add(pk.read_json("fabric.mod.json")["id"])
            except (ValueError, KeyError):
                pass
    return ids


def discover(server_dir, include_extra=False):
    server_dir = Path(server_dir)
    vanilla = sorted((server_dir / "versions").glob("*/server-*.jar"))
    if not vanilla:
        raise SystemExit("no vanilla server jar under %s/versions/*/server-*.jar" % server_dir)
    packs = [p for p in open_jar(vanilla[-1], vanilla[-1].name, "vanilla", nested=False)]
    for jar in sorted((server_dir / "mods").glob("*.jar")):
        packs += open_jar(jar, jar.name, "mod")
    dp_dirs = [server_dir / "datapacks"]
    if include_extra:
        dp_dirs.append(server_dir / "datapacks" / "extra")
    for d in dp_dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir(), key=lambda p: p.name.lower()):
            if p.suffix == ".zip":
                zf = zipfile.ZipFile(p)
                packs.append(Pack(p.name, "datapack", _zip_files(zf, ("data/",))))
            elif p.is_dir() and (p / "pack.mcmeta").is_file():
                packs.append(open_folder(p, p.name, "datapack"))
    return packs


# ------------------------------------------------------------------ registry


def build_registry(packs):
    biomes = set()
    tags = {}            # "#ns:path" -> list of entries (dict id/required)
    tag_sources = defaultdict(list)
    for pk in packs:     # later packs override or extend earlier ones
        for path in pk.files:
            m = BIOME_RE.match(path)
            if m:
                biomes.add("%s:%s" % m.groups())
                continue
            m = TAG_RE.match(path)
            if m:
                key = "#%s:%s" % m.groups()
                doc = pk.read_json(path)
                vals = []
                for v in doc.get("values", []):
                    vals.append({"id": v, "required": True} if isinstance(v, str)
                                else {"id": v["id"], "required": v.get("required", True)})
                if doc.get("replace") or key not in tags:
                    tags[key] = vals
                else:
                    tags[key] = tags[key] + vals
                tag_sources[key].append(pk.name)
    return biomes, tags, tag_sources


def resolve(ref, biomes, tags, _seen=None):
    """Concrete loaded biome IDs a biome ID or #tag stands for."""
    if not ref.startswith("#"):
        return {ref} if ref in biomes else set()
    _seen = _seen or set()
    if ref in _seen:
        return set()
    _seen.add(ref)
    out = set()
    for v in tags.get(ref, []):
        out |= resolve(v["id"], biomes, tags, _seen)
    return out


# ------------------------------------------------------------------ spawns


SPECIES_RE = re.compile(r"[a-z0-9_\-]+")


def species_name(text):
    """The species id at the start of a Pokemon property string.

    'gamma form=x', 'pangoro held_item=cobblemon:fighting_gem' and odd
    whitespace all reduce to the leading id.
    """
    m = SPECIES_RE.match(str(text).strip().lower())
    return m.group(0) if m else None


def species_of(entry):
    names = []
    if entry.get("pokemon"):
        names.append(species_name(entry["pokemon"]))
    for h in entry.get("herdablePokemon") or []:
        p = h.get("pokemon") if isinstance(h, dict) else h
        if p:
            names.append(species_name(p))
    return [n for n in names if n]


def cobblemon_pack(packs):
    for pk in packs:
        if "fabric.mod.json" in pk.files:
            try:
                if pk.read_json("fabric.mod.json").get("id") == "cobblemon":
                    return pk
            except ValueError:
                continue
    raise SystemExit("the Cobblemon jar was not found in mods/")


def collect_entries(packs, scope, installed):
    if scope == "default":
        sources = [cobblemon_pack(packs)]
    else:
        sources = packs
    pools = {}
    for pk in sources:
        for path in pk.files:
            if SPAWN_RE.match(path):
                pools[path] = pk
    entries, skipped = [], defaultdict(int)
    for path, pk in sorted(pools.items()):
        doc = pk.read_json(path)
        if doc.get("enabled") is False:
            skipped["disabled_pool"] += 1
            continue
        need = set(doc.get("neededInstalledMods") or [])
        avoid = set(doc.get("neededUninstalledMods") or [])
        if not need <= installed or avoid & installed:
            skipped["mod_requirements_unmet"] += 1
            continue
        for s in doc.get("spawns") or []:
            cond = s.get("condition") or {}
            anti = s.get("anticondition") or {}
            entries.append({
                "pool": path, "pack": pk.name, "id": s.get("id"),
                "species": species_of(s), "bucket": s.get("bucket"),
                "type": s.get("type"),
                "biomes": list(cond.get("biomes") or []),
                "anti_biomes": list(anti.get("biomes") or []),
                "other_conditions": sorted(k for k in cond if k != "biomes"),
            })
    return entries, dict(skipped)


# ------------------------------------------------------------------ plan


def planned_biomes(regions_doc):
    """biome -> sorted region ids, plus the plan's tag overlays as {tag: [biomes]}.

    Reads the cobblers.regions/1 shapes: region biomes.bands, sea_biomes.shares,
    underground_biomes[{biome, regions}], tag_overlays[{tag, add_biomes}].
    A region whose biomes are deferred contributes nothing.
    """
    where = defaultdict(set)
    for r in regions_doc.get("regions") or []:
        b = r.get("biomes") or {}
        if b.get("deferred"):
            continue
        for band in b.get("bands") or []:
            where[band["biome"]].add(r["id"])
        for name in [b.get("primary")] + list(b.get("secondary") or []):
            if name:
                where[name].add(r["id"])
    for biome in ((regions_doc.get("sea_biomes") or {}).get("shares") or {}):
        where[biome].add("sea")
    for cave in regions_doc.get("underground_biomes") or []:
        for rid in cave.get("regions") or []:
            where[cave["biome"]].add(rid)
    overlays = defaultdict(list)
    for ov in regions_doc.get("tag_overlays") or []:
        overlays[ov["tag"]].extend(ov.get("add_biomes") or [])
    return {k: sorted(v) for k, v in where.items()}, dict(overlays)


def analyse(packs, scope, regions_doc=None):
    installed = mod_ids(packs)
    biomes, tags, tag_sources = build_registry(packs)
    dims = {name: resolve(tag, biomes, tags) for name, tag in DIMENSION_TAGS}
    entries, skipped = collect_entries(packs, scope, installed)

    planned, overlays = planned_biomes(regions_doc) if regions_doc else ({}, {})
    tags_planned = {k: list(v) for k, v in tags.items()}
    for tag, bs in overlays.items():
        tags_planned[tag] = tags_planned.get(tag, []) + [{"id": b, "required": True} for b in bs]

    refs = defaultdict(lambda: {"condition_entries": 0, "anticondition_entries": 0,
                                "species": set(), "buckets": defaultdict(int)})
    for e in entries:
        for r in e["biomes"]:
            refs[r]["condition_entries"] += 1
            refs[r]["species"].update(e["species"])
            refs[r]["buckets"][e["bucket"]] += 1
        for r in e["anti_biomes"]:
            refs[r]["anticondition_entries"] += 1

    def dimension(members):
        found = [name for name, dm in dims.items() if members & dm]
        return found[0] if len(found) == 1 else ("mixed:" + "+".join(found) if found else "unresolved")

    ref_rows = []
    for ref, info in sorted(refs.items()):
        members = resolve(ref, biomes, tags)
        members_planned = resolve(ref, biomes, tags_planned)
        hits = sorted(b for b in members_planned if b in planned)
        via_overlay = sorted(set(hits) - members)
        ref_rows.append({
            "ref": ref, "kind": "tag" if ref.startswith("#") else "biome",
            "defined": ref in tags if ref.startswith("#") else ref in biomes,
            "condition_entries": info["condition_entries"],
            "anticondition_entries": info["anticondition_entries"],
            "species_count": len(info["species"]),
            "buckets": dict(info["buckets"]),
            "members": sorted(members),
            "dimension": dimension(members),
            "optional_unloaded": sorted(v["id"] for v in tags.get(ref, [])
                                        if not v["required"] and not v["id"].startswith("#")
                                        and v["id"] not in biomes),
            "covered": bool(hits) if regions_doc else None,
            "covered_by": [{"biome": b, "regions": planned[b]} for b in hits],
            "via_overlay": via_overlay,
        })

    # entry reachability and per-biome marginal value
    member_cache = {}

    def members_of(refs_, table):
        key = (tuple(refs_), id(table))
        if key not in member_cache:
            s = set()
            for r in refs_:
                s |= resolve(r, biomes, table)
            member_cache[key] = s
        return member_cache[key]

    plan_set = set(planned)
    reach, all_species, reach_species = 0, set(), set()
    per_biome_species = defaultdict(set)
    overworld_entries = 0
    for e in entries:
        # Base tags decide whether an entry can spawn in the overworld at all;
        # planned tags (with the plan's overlays) decide whether the plan
        # reaches it. An entry reachable only through an overlay counts in both.
        base_ok = ((members_of(e["biomes"], tags) if e["biomes"] else set(biomes))
                   - members_of(e["anti_biomes"], tags))
        plan_ok = ((members_of(e["biomes"], tags_planned) if e["biomes"] else set(biomes))
                   - members_of(e["anti_biomes"], tags_planned))
        if not ((base_ok | plan_ok) & dims["overworld"]):
            continue
        overworld_entries += 1
        all_species.update(e["species"])
        for b in plan_ok & dims["overworld"]:
            per_biome_species[b].update(e["species"])
        if plan_ok & plan_set:
            reach += 1
            reach_species.update(e["species"])

    biome_rows = []
    for b in sorted(dims["overworld"] | set(planned)):
        sp = per_biome_species.get(b, set())
        biome_rows.append({
            "biome": b, "loaded": b in biomes,
            "planned_regions": planned.get(b, []),
            "species_possible": len(sp),
            "species_only_here_if_unplanned": len(sp - reach_species) if b not in plan_set else 0,
            "unlocks_species": sorted(sp - reach_species) if b not in plan_set else [],
        })

    return {
        "schema": "cobblers.derived.spawn_biomes/1",
        "scope": scope,
        "sources": [{"name": pk.name, "kind": pk.kind,
                     "spawn_pools": sum(1 for p in pk.files if SPAWN_RE.match(p)),
                     "biome_tags": sum(1 for p in pk.files if TAG_RE.match(p)),
                     "biomes": sum(1 for p in pk.files if BIOME_RE.match(p))}
                    for pk in packs if any(SPAWN_RE.match(p) or TAG_RE.match(p) or BIOME_RE.match(p)
                                           for p in pk.files)],
        "skipped_pools": skipped,
        "spawn_entries": len(entries),
        "overworld_entries": overworld_entries,
        "biome_registry_size": len(biomes),
        "overworld_biomes": sorted(dims["overworld"]),
        "references": ref_rows,
        "biomes": biome_rows,
        "coverage": None if not regions_doc else {
            "planned_biomes": sorted(planned),
            "tag_overlays": overlays,
            "overworld_references": sum(1 for r in ref_rows if r["dimension"] == "overworld"),
            "overworld_references_covered": sum(1 for r in ref_rows
                                                if r["dimension"] == "overworld" and r["covered"]),
            "overworld_entries_reachable": reach,
            "overworld_species": len(all_species),
            "overworld_species_reachable": len(reach_species),
            "unreachable_species": sorted(all_species - reach_species),
        },
    }


# ------------------------------------------------------------------ output


def markdown(result):
    lines = []
    cov = result["coverage"]
    lines.append("<!-- generated by tools/spawn_biomes.py; edit the tool or the plan, not this table -->")
    lines.append("")
    lines.append("Scope `%s`: %d spawn entries, %d whose biomes can occur in the overworld."
                 % (result["scope"], result["spawn_entries"], result["overworld_entries"]))
    if cov:
        lines.append("Planned surface: %d overworld references covered of %d; %d entries and %d of %d species reachable by biome."
                     % (cov["overworld_references_covered"], cov["overworld_references"],
                        cov["overworld_entries_reachable"], cov["overworld_species_reachable"],
                        cov["overworld_species"]))
    lines.append("")
    lines.append("| Reference | Entries | Anti | Species | Dimension | Loaded members | Covered by plan |")
    lines.append("|---|---:|---:|---:|---|---|---|")
    for r in sorted(result["references"], key=lambda r: (r["dimension"] != "overworld", -r["condition_entries"])):
        members = ", ".join(m.split(":", 1)[1] if m.startswith("minecraft:") else m for m in r["members"])
        if len(members) > 90:
            members = members[:87] + "..."
        if r["covered"] is None:
            cov_s = ""
        elif r["covered"]:
            cov_s = "; ".join("%s (%s)%s" % (c["biome"].replace("minecraft:", ""), ", ".join(c["regions"]),
                                             " overlay" if c["biome"] in r["via_overlay"] else "")
                              for c in r["covered_by"][:3])
            if len(r["covered_by"]) > 3:
                cov_s += "; +%d more" % (len(r["covered_by"]) - 3)
        else:
            cov_s = "**GAP**"
        lines.append("| `%s` | %d | %d | %d | %s | %s | %s |"
                     % (r["ref"], r["condition_entries"], r["anticondition_entries"],
                        r["species_count"], r["dimension"], members or "(none loaded)", cov_s))
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_DIR"),
                   help="server directory holding versions/, mods/, datapacks/ "
                        "(default $COBBLERS_SERVER_DIR)")
    p.add_argument("--scope", choices=("default", "pack"), default="pack")
    p.add_argument("--include-extra", action="store_true",
                   help="also load datapacks/extra (the server does not)")
    p.add_argument("--regions", default=None, help="region plan to check coverage against")
    p.add_argument("--out", default=None)
    p.add_argument("--markdown", default=None, help="also write the reference table here")
    a = p.parse_args(argv)
    if not a.server_dir:
        raise SystemExit("--server-dir or COBBLERS_SERVER_DIR is required")

    packs = discover(a.server_dir, a.include_extra)
    regions_doc = json.loads(Path(a.regions).read_text(encoding="utf-8")) if a.regions else None
    result = analyse(packs, a.scope, regions_doc)
    result["parameters"] = {"scope": a.scope, "include_extra": a.include_extra,
                            "regions": a.regions}
    out = Path(a.out) if a.out else ROOT / "derived" / "spawns" / ("spawn_biomes_%s.json" % a.scope)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    if a.markdown:
        Path(a.markdown).write_text(markdown(result), encoding="utf-8")
    ow = [r for r in result["references"] if r["dimension"] == "overworld"]
    print("%s scope: %d entries, %d references (%d overworld), %d loaded biomes"
          % (a.scope, result["spawn_entries"], len(result["references"]), len(ow),
             result["biome_registry_size"]))
    if result["coverage"]:
        c = result["coverage"]
        print("coverage: %d/%d overworld references, %d/%d species reachable by biome"
              % (c["overworld_references_covered"], c["overworld_references"],
                 c["overworld_species_reachable"], c["overworld_species"]))
    print("-> %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
