#!/usr/bin/env python
"""Which blocks a Cobblemon spawn can be conditioned on, and which templates contain them.

A donor building's roof can decide what spawns in a town: the Cobbleverse datapack spawns Varoom and Revavroom on
any of the 16 concrete colours, in every overworld biome. This tool reads the spawn data the server actually loads
(Cobblemon and every mod jar, plus the enabled datapacks), resolves the block tags those conditions use, and writes
the block list to data/spawn_blocks.json. `audit` then reports which structure templates contain those blocks.

  blocks      scan and write data/spawn_blocks.json (blocks -> the spawns that name them)
  audit       scan kits/structures for templates containing any of them
  substitute  rewrite templates with data/spawn_block_policy.json substitutions, in the palette and in
              every jigsaw final_state, recording sha256 before and after

  python tools/spawn_blocks.py blocks --server-dir <server-dir, under the lock>
  python tools/spawn_blocks.py audit [--server-dir <server-dir, under the lock>]
  python tools/spawn_blocks.py substitute [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import nbt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "spawn_blocks.json"
FIELDS = ("neededBaseBlocks", "neededNearbyBlocks")
# tags a block-tag scan cannot resolve: fluid tags, and convention tags whose vanilla equivalent is the same set
ALIAS = {"#minecraft:water": ["minecraft:water", "minecraft:bubble_column"], "#c:sand": ["#minecraft:sand"],
         "#c:redstone_ores": ["#minecraft:redstone_ores"]}


def read_sources(server_dir):
    """-> list of (label, open(path) -> bytes, namelist). Mod jars, enabled datapack zips and folders."""
    import runtime_guard
    server = runtime_guard.check(server_dir, "read the server directory")
    out = []

    def add_zip(label, z):
        out.append((label, z.read, z.namelist()))
        for n in z.namelist():                              # one level of nested jars: fabric api modules, the
            if n.endswith(".jar") and (n.startswith("META-INF/jars/") or n.startswith("META-INF/versions/")):
                try:                                        # bundled vanilla server, addon libraries
                    inner = zipfile.ZipFile(io.BytesIO(z.read(n)))
                except (zipfile.BadZipFile, KeyError):
                    continue
                out.append(("%s!%s" % (label, n.split("/")[-1]), inner.read, inner.namelist()))
    vanilla = server / "server.jar"
    if vanilla.exists():                                    # vanilla tags (#minecraft:sand and the rest) live here
        add_zip(vanilla.name, zipfile.ZipFile(vanilla))
    for jar in sorted((server / "mods").glob("*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except zipfile.BadZipFile:
            continue
        add_zip(jar.name, z)
    dp = server / "datapacks"
    for p in sorted(dp.iterdir()) if dp.exists() else []:
        if p.name == "extra":
            continue                                        # not loaded by the server
        if p.suffix == ".zip":
            try:
                z = zipfile.ZipFile(p)
            except zipfile.BadZipFile:
                continue
            out.append((p.name, z.read, z.namelist()))
        elif p.is_dir():
            names = [q.relative_to(p).as_posix() for q in p.rglob("*") if q.is_file()]
            out.append((p.name, lambda n, base=p: (base / n).read_bytes(), names))
    return out


def loaded_namespaces(sources):
    """Namespaces the server can actually place: minecraft plus every loaded mod id and datapack namespace."""
    ns = {"minecraft", "c"}
    for label, read, names in sources:
        if "fabric.mod.json" in names:
            try:
                ns.add(json.loads(read("fabric.mod.json"))["id"])
            except Exception:
                pass
        for n in names:
            if n.startswith(("data/", "assets/")) and n.count("/") >= 2:
                ns.add(n.split("/")[1])
    return ns


def collect(sources):
    spawns, tags = defaultdict(list), {}
    for label, read, names in sources:
        for n in names:
            if n.startswith("data/") and "/tags/block" in n and n.endswith(".json"):
                parts = n.split("/")
                ns, path = parts[1], "/".join(parts[4:])[:-5]
                try:
                    tags.setdefault("#%s:%s" % (ns, path), []).extend(json.loads(read(n)).get("values", []))
                except Exception:
                    continue
            if "spawn_pool_world" in n and n.endswith(".json"):
                try:
                    doc = json.loads(read(n))
                except Exception:
                    continue
                for s in doc.get("spawns", []):
                    for field in FIELDS:
                        for cond_name in ("condition", "anticondition"):
                            for b in ((s.get(cond_name) or {}).get(field) or []):
                                spawns[b].append({"pokemon": s.get("pokemon"), "bucket": s.get("bucket"), "field": field,
                                                  "condition": cond_name, "biomes": (s.get(cond_name) or {}).get("biomes"),
                                                  "source": label})
    return spawns, tags


def resolve(entry, tags, seen=None):
    seen = seen or set()
    if not entry.startswith("#"):
        return {entry if ":" in entry else "minecraft:" + entry}
    if entry in seen:
        return set()
    seen.add(entry)
    out = set()
    for v in tags.get(entry, []) or ALIAS.get(entry, []):
        v = v["id"] if isinstance(v, dict) else v
        out |= resolve(v, tags, seen)
    return out


def cmd_blocks(a):
    sources = read_sources(a.server_dir)
    spawns, tags = collect(sources)
    ns_loaded = loaded_namespaces(sources)
    blocks = defaultdict(list)
    unresolved, skipped = [], set()
    for entry, uses in spawns.items():
        got = resolve(entry, tags)
        if not got:
            unresolved.append(entry)
        for b in got:
            if b.split(":")[0] not in ns_loaded:            # a tag may name blocks of mods this pack does not have
                skipped.add(b)
                continue
            for u in uses:
                blocks[b].append(dict(u, via=entry if entry.startswith("#") else None))
    doc = {"schema": "cobblers.spawn-blocks/1", "generated": datetime.date.today().isoformat(),
           "generator": "tools/spawn_blocks.py blocks",
           "scope": {"server_dir": str(Path(a.server_dir).resolve()), "mod_jars": sum(1 for s in sources if s[0].endswith(".jar")),
                     "datapacks": sum(1 for s in sources if not s[0].endswith(".jar")), "fields": list(FIELDS)},
           "note": ("Every block a loaded spawn condition names, directly or through a tag. A template that contains one "
                    "decides encounters wherever it is placed, so tools/validate_data.py fails on a placed template "
                    "containing one unless data/placements.json whitelists it."),
           "entries_scanned": sum(len(v) for v in spawns.values()), "unresolved_tags": sorted(unresolved),
           "blocks_from_absent_mods": len(skipped), "loaded_namespaces": len(ns_loaded),
           "blocks": {b: sorted({(u["pokemon"] or "herd") + ("" if u["condition"] == "condition" else " (anticondition)")
                                 + " [" + (u["via"] or "direct") + ", " + u["field"] + ", " + u["source"] + "]" for u in uses})
                      for b, uses in sorted(blocks.items())}}
    OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"blocks": len(doc["blocks"]), "blocks_from_absent_mods": len(skipped),
                      "unresolved_tags": doc["unresolved_tags"], "out": str(OUT)}, indent=1))


def template_blocks(path):
    """Every block a placed template puts in the world, by name.

    That includes what its jigsaws turn into: a jigsaw's final_state is not in the palette, and
    tools/place_town.py resolves it when it places the template. Counting the palette alone made the
    CobbleTowns Marts look clean while their shop counters still became light blue concrete.
    """
    _, doc = nbt.load(path)
    pal = [p.get("Name") for p in doc.get("palette") or []]
    used = defaultdict(int)
    for b in doc.get("blocks") or []:
        used[pal[b["state"]]] += 1
        final = (b.get("nbt") or {}).get("final_state")
        if isinstance(final, str):
            used[final.split("[")[0]] += 1
    return used


def cmd_audit(a):
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    trigger = set(doc["blocks"])
    rows, total = [], 0
    for p in sorted((ROOT / "kits" / "structures").rglob("*.nbt")):
        total += 1
        used = template_blocks(p)
        hits = {b: n for b, n in used.items() if b in trigger}
        if hits:
            rows.append({"template": p.relative_to(ROOT).as_posix(), "blocks": dict(sorted(hits.items(), key=lambda kv: -kv[1])),
                         "spawns": sorted({s for b in hits for s in doc["blocks"][b]})})
    print(json.dumps({"templates_scanned": total, "templates_with_spawn_blocks": len(rows), "findings": rows}, indent=1))
    raise SystemExit(0)


POLICY = ROOT / "data" / "spawn_block_policy.json"


def cmd_substitute(a):
    """Swap blocks in the templates themselves, type-preserving, and record what changed in the policy file."""
    import gzip
    import hashlib
    import level_dat as L
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    swap = {e["from"]: e["to"] for e in policy["substitutions"]}
    applied = []
    for path in sorted((ROOT / "kits" / "structures").rglob("*.nbt")):
        used = template_blocks(path)
        hits = {b: n for b, n in used.items() if b in swap}
        if not hits:
            continue
        raw = path.read_bytes()
        name, root = L.loads(raw)
        if gzip.decompress(L.dumps(name, root)) != gzip.decompress(raw):
            raise SystemExit("%s does not round-trip through the NBT writer; refusing to rewrite it" % path)
        changed = 0
        for entry in root["palette"][1][1]:
            nm = L.plain(entry["Name"])
            if nm in swap:
                entry["Name"] = (L.STRING, swap[nm])
                changed += 1
        # A jigsaw block carries the block it becomes in its own nbt, not in the palette. Swapping
        # only the palette leaves the substituted block behind in every jigsaw's final_state, and
        # tools/place_town.py resolves those when it places the template: found on 2026-09-20 in the
        # CobbleTowns Marts, whose shop-counter jigsaws turn into light blue concrete.
        jigsaws = 0
        for block in root["blocks"][1][1]:
            nbt_tag = block.get("nbt")
            if not nbt_tag:
                continue
            fields = nbt_tag[1] if isinstance(nbt_tag, tuple) else nbt_tag
            final = fields.get("final_state") if hasattr(fields, "get") else None
            if final is None:
                continue
            text = L.plain(final)
            base = text.split("[")[0]
            if base in swap:
                fields["final_state"] = (L.STRING, text.replace(base, swap[base], 1))
                jigsaws += 1
        before = hashlib.sha256(raw).hexdigest()
        out = L.dumps(name, root)
        after = hashlib.sha256(out).hexdigest()
        row = {"template": path.relative_to(ROOT).as_posix(), "palette_entries_changed": changed,
               "jigsaw_final_states_changed": jigsaws,
               "blocks": {b: {"count": n, "to": swap[b]} for b, n in sorted(hits.items())},
               "sha256_before": before, "sha256_after": after}
        applied.append(row)
        if not a.dry_run:
            path.write_bytes(out)
    if not a.dry_run:
        policy["applied"] = {"date": datetime.date.today().isoformat(), "by": "tools/spawn_blocks.py substitute",
                             "templates": applied}
        POLICY.write_text(json.dumps(policy, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"templates": len(applied), "dry_run": bool(a.dry_run), "detail": applied}, indent=1))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("blocks")
    s.add_argument("--server-dir", required=True)
    s = sub.add_parser("audit")
    s.add_argument("--server-dir", default=None)
    s = sub.add_parser("substitute")
    s.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    {"blocks": cmd_blocks, "audit": cmd_audit, "substitute": cmd_substitute}[a.cmd](a)


if __name__ == "__main__":
    main()
