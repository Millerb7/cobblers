#!/usr/bin/env python
"""Prefab kit: bring builds made in Axiom (or saved with a structure block) into kits/structures/prefabs as
structure templates the placer can use, check them, and pack them into a datapack.

  import   a Sponge schematic (.schem, version 2 or 3: what Axiom's "Export Schematic..." and WorldEdit write) or a
           structure .nbt  ->  kits/structures/prefabs/<kind>/<set>/<name>.nbt plus <name>.json (the sidecar:
           source, size, entrance, ground layer, block namespaces)
  index    validate every prefab: loads, sidecar present and consistent, name convention, entrance inside the box,
           block namespaces loaded by the server (with --server-dir)
  pack     build build/datapacks/cobblers_kits with every prefab at data/cobblers/structure/kits/<kind>/<set>/<name>.nbt,
           so it places as cobblers:kits/<kind>/<set>/<name>; --install copies it into a server's datapacks folder

  python tools/kit.py import kits/structures/incoming/house.schem --kind buildings --set viltri --name cottage_a \\
      --entrance 4,1,0 --facing north --author you [--no-air]
  python tools/kit.py index [--server-dir <server-dir, under the lock>]
  python tools/kit.py pack [--install <server-dir>/datapacks, under the lock]

Entrance: the block in front of the door at ground level, in the build's own coordinates (0,0,0 is the minimum
corner of the export). Its y is the ground layer: tools/place_town.py puts that layer at the ground in front of
the door, the same rule it applies to a donor's entrance jigsaw.
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import json
import re
import shutil
from pathlib import Path

import level_dat as L

ROOT = Path(__file__).resolve().parent.parent
PREFABS = ROOT / "kits" / "structures" / "prefabs"
KINDS = ("buildings", "services", "gyms", "landmarks", "props", "bridges", "trees", "paths")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")
FACINGS = ("north", "south", "east", "west")
AIR = ("minecraft:air", "minecraft:cave_air", "minecraft:void_air")
DATA_VERSION_1_21_1 = 3955


def read_varints(data, count):
    out, i, n = [], 0, len(data)
    while len(out) < count and i < n:
        value, shift = 0, 0
        while True:
            b = data[i]
            i += 1
            value |= (b & 0x7F) << shift
            if not b & 0x80:
                break
            shift += 7
        out.append(value)
    if len(out) != count:
        raise SystemExit("block data holds %d entries, expected %d" % (len(out), count))
    return out


def parse_state(s):
    m = re.match(r"^([^\[]+)(?:\[(.*)\])?$", s)
    name, props = m.group(1), m.group(2)
    if ":" not in name:
        name = "minecraft:" + name
    p = {}
    if props:
        for kv in props.split(","):
            k, v = kv.split("=", 1)
            p[k.strip()] = v.strip()
    return name, p


def val(node, default=None):
    return node[1] if node is not None else default


def sponge_to_structure(root, keep_air=True):
    """Typed Sponge schematic compound -> typed structure template compound, plus a summary."""
    if "Schematic" in root and root["Schematic"][0] == L.COMPOUND:        # version 3 wraps everything
        root = root["Schematic"][1]
    version = val(root.get("Version"))
    if version not in (2, 3):
        raise SystemExit("unsupported Sponge schematic version %r (expected 2 or 3)" % version)
    w, h, ln = val(root["Width"]), val(root["Height"]), val(root["Length"])
    w, h, ln = w & 0xFFFF, h & 0xFFFF, ln & 0xFFFF                      # stored as shorts
    if version == 3:
        blocks = root["Blocks"][1]
        palette, data, bes = blocks["Palette"][1], blocks["Data"][1], val(blocks.get("BlockEntities"), (L.COMPOUND, []))
    else:
        palette, data, bes = root["Palette"][1], root["BlockData"][1], val(root.get("BlockEntities"), (L.COMPOUND, []))
    index_to_state = {v[1]: k for k, v in palette.items()}
    ids = read_varints(data, w * h * ln)
    pal, pal_idx = [], {}
    def state_index(s):
        if s not in pal_idx:
            name, props = parse_state(s)
            comp = {"Name": (L.STRING, name)}
            if props:
                comp["Properties"] = (L.COMPOUND, {k: (L.STRING, v) for k, v in props.items()})
            pal_idx[s] = len(pal)
            pal.append(comp)
        return pal_idx[s]
    be_at = {}
    for be in bes[1]:
        pos = val(be["Pos"])
        bid = val(be.get("Id"))
        if version == 3:
            nbt = dict(val(be.get("Data"), {}))
        else:
            nbt = {k: v for k, v in be.items() if k not in ("Pos", "Id")}
        if bid:
            nbt["id"] = (L.STRING, bid)
        be_at[tuple(pos)] = nbt
    out_blocks, namespaces, air = [], {}, 0
    for i, sid in enumerate(ids):
        s = index_to_state[sid]
        x, z, y = i % w, (i // w) % ln, i // (w * ln)
        name = parse_state(s)[0]
        if name in AIR:
            air += 1
            if not keep_air:
                continue
        namespaces[name.split(":")[0]] = namespaces.get(name.split(":")[0], 0) + 1
        comp = {"pos": (L.LIST, (L.INT, [x, y, z])), "state": (L.INT, state_index(s))}
        if (x, y, z) in be_at:
            comp["nbt"] = (L.COMPOUND, be_at[(x, y, z)])
        out_blocks.append(comp)
    entities = []
    ents = val(root.get("Entities"), (L.COMPOUND, []))
    for e in ents[1]:
        pos = val(e["Pos"])
        nbt = dict(val(e.get("Data"), {})) if version == 3 else {k: v for k, v in e.items() if k not in ("Pos", "Id")}
        if val(e.get("Id")):
            nbt["id"] = (L.STRING, val(e["Id"]))
        entities.append({"pos": (L.LIST, (L.DOUBLE, list(pos))), "blockPos": (L.LIST, (L.INT, [int(p // 1) for p in pos])),
                         "nbt": (L.COMPOUND, nbt)})
    dv = val(root.get("DataVersion"), DATA_VERSION_1_21_1)
    struct = {"DataVersion": (L.INT, dv), "size": (L.LIST, (L.INT, [w, h, ln])),
              "palette": (L.LIST, (L.COMPOUND, pal)), "blocks": (L.LIST, (L.COMPOUND, out_blocks)),
              "entities": (L.LIST, (L.COMPOUND, entities))}
    summary = {"format": "sponge_v%d" % version, "data_version": dv, "size": [w, h, ln], "blocks": len(out_blocks),
               "air_in_box": air, "air_kept": keep_air, "block_entities": len(be_at), "entities": len(entities),
               "namespaces": dict(sorted(namespaces.items()))}
    return struct, summary


def structure_summary(root):
    pal = [val(p["Name"]) for p in root["palette"][1][1]]
    blocks = root["blocks"][1][1]
    ns = {}
    for b in blocks:
        n = pal[val(b["state"])].split(":")[0]
        ns[n] = ns.get(n, 0) + 1
    return {"format": "structure", "data_version": val(root.get("DataVersion")), "size": val(root["size"])[1],
            "blocks": len(blocks), "block_entities": sum(1 for b in blocks if "nbt" in b),
            "entities": len(val(root.get("entities"), (L.COMPOUND, []))[1]), "namespaces": dict(sorted(ns.items()))}


def prefab_paths(kind, set_, name):
    d = PREFABS / kind / set_
    return d / (name + ".nbt"), d / (name + ".json")


def cmd_import(a):
    for label, v in (("kind", a.kind), ("set", a.set), ("name", a.name)):
        if label == "kind" and v not in KINDS:
            raise SystemExit("--kind must be one of %s" % ", ".join(KINDS))
        if not NAME_RE.match(v):
            raise SystemExit("--%s %r: lowercase letters, digits and underscores, starting with a letter or digit" % (label, v))
    src = Path(a.file)
    raw = src.read_bytes()
    name, root = L.loads(raw)
    if src.suffix.lower() in (".schem", ".schematic"):
        struct, summary = sponge_to_structure(root, keep_air=not a.no_air)
    elif src.suffix.lower() == ".nbt":
        struct, summary = root, structure_summary(root)
    else:
        raise SystemExit("import takes .schem, .schematic or .nbt")
    size = summary["size"]
    entrance = None
    if a.entrance:
        ex, ey, ez = [int(v) for v in a.entrance.split(",")]
        if not (0 <= ex < size[0] and 0 <= ey < size[1] and 0 <= ez < size[2]):
            raise SystemExit("entrance %s is outside the %s box" % (a.entrance, size))
        if a.facing not in FACINGS:
            raise SystemExit("--facing must be one of %s" % ", ".join(FACINGS))
        entrance = {"pos": [ex, ey, ez], "facing": a.facing}
    elif a.kind in ("buildings", "services", "gyms"):
        raise SystemExit("a %s prefab needs --entrance x,y,z and --facing: the placer seats it by its door" % a.kind)
    nbt_path, side_path = prefab_paths(a.kind, a.set, a.name)
    if nbt_path.exists() and not a.replace:
        raise SystemExit("%s exists; pass --replace to overwrite it" % nbt_path.relative_to(ROOT))
    nbt_path.parent.mkdir(parents=True, exist_ok=True)
    nbt_path.write_bytes(L.dumps("", struct))
    side = {"schema": "cobblers.prefab/1", "template_id": "cobblers:kits/%s/%s/%s" % (a.kind, a.set, a.name),
            "kind": a.kind, "set": a.set, "name": a.name, "author": a.author,
            "source": {"file": src.name, "imported": datetime.date.today().isoformat(), **summary},
            "entrance": entrance, "grade_layer": entrance["pos"][1] if entrance else None, "notes": a.notes}
    side_path.write_text(json.dumps(side, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(side, indent=1))


def iter_prefabs():
    for nbt_path in sorted(PREFABS.glob("*/*/*.nbt")):
        yield nbt_path, nbt_path.with_suffix(".json")


def cmd_index(a):
    loaded = None
    if a.server_dir:
        import zipfile
        loaded = {"minecraft"}
        import runtime_guard
        for jar in (runtime_guard.check(a.server_dir, "read the server directory") / "mods").glob("*.jar"):
            try:
                with zipfile.ZipFile(jar) as z:
                    names = {n.split("/")[1] for n in z.namelist() if n.startswith(("assets/", "data/")) and n.count("/") >= 2}
                    loaded |= names
            except zipfile.BadZipFile:
                continue
    rows, errors = [], []
    for nbt_path, side_path in iter_prefabs():
        rel = nbt_path.relative_to(ROOT).as_posix()
        kind, set_, name = nbt_path.parts[-3], nbt_path.parts[-2], nbt_path.stem
        if kind not in KINDS or not NAME_RE.match(set_) or not NAME_RE.match(name):
            errors.append("%s: path does not follow <kind>/<set>/<name>.nbt" % rel)
        try:
            _, root = L.loads(nbt_path.read_bytes())
            summ = structure_summary(root)
        except Exception as exc:                      # a broken file is a finding, not a crash
            errors.append("%s: does not load (%s)" % (rel, exc))
            continue
        if not side_path.exists():
            errors.append("%s: no sidecar .json" % rel)
            continue
        side = json.loads(side_path.read_text(encoding="utf-8"))
        if side.get("template_id") != "cobblers:kits/%s/%s/%s" % (kind, set_, name):
            errors.append("%s: sidecar template_id %r does not match its path" % (rel, side.get("template_id")))
        ent = side.get("entrance")
        if kind in ("buildings", "services", "gyms") and not ent:
            errors.append("%s: no entrance in the sidecar" % rel)
        if ent and not all(0 <= ent["pos"][i] < summ["size"][i] for i in range(3)):
            errors.append("%s: entrance %s outside size %s" % (rel, ent["pos"], summ["size"]))
        missing = sorted(set(summ["namespaces"]) - loaded) if loaded is not None else []
        if missing:
            errors.append("%s: blocks from namespaces the server does not load: %s" % (rel, ", ".join(missing)))
        rows.append({"prefab": rel, **summ, "entrance": ent})
    print(json.dumps({"prefabs": rows, "errors": errors}, indent=1))
    raise SystemExit(1 if errors else 0)


def cmd_pack(a):
    out = Path(a.out or ROOT / "build" / "datapacks" / "cobblers_kits")
    if out.exists():
        shutil.rmtree(out)
    n = 0
    for nbt_path, _ in iter_prefabs():
        kind, set_ = nbt_path.parts[-3], nbt_path.parts[-2]
        dest = out / "data" / "cobblers" / "structure" / "kits" / kind / set_ / nbt_path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(nbt_path, dest)
        n += 1
    out.mkdir(parents=True, exist_ok=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: prefab kit (tools/kit.py pack)"}}, indent=2) + "\n", encoding="utf-8")
    print("packed %d prefabs into %s" % (n, out))
    if a.install:
        import runtime_guard
        dest = runtime_guard.check(a.install, "install into") / out.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(out, dest)
        print("installed", dest)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("import")
    s.add_argument("file")
    s.add_argument("--kind", required=True)
    s.add_argument("--set", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--entrance", default=None, help="x,y,z of the ground block in front of the door, build coordinates")
    s.add_argument("--facing", default=None, help="which way the door faces: north, south, east, west")
    s.add_argument("--author", default=None)
    s.add_argument("--notes", default=None)
    s.add_argument("--no-air", action="store_true", help="drop air so placement leaves existing terrain in empty cells")
    s.add_argument("--replace", action="store_true")
    s = sub.add_parser("index")
    s.add_argument("--server-dir", default=None)
    s = sub.add_parser("pack")
    s.add_argument("--out", default=None)
    s.add_argument("--install", default=None)
    a = p.parse_args(argv)
    {"import": cmd_import, "index": cmd_index, "pack": cmd_pack}[a.cmd](a)


if __name__ == "__main__":
    main()
