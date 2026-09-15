#!/usr/bin/env python
"""Build the spawn-tag overlay datapack from data/regions.json spawn_tag_overlays.

Cobblemon spawns on biome tags. Some tags (e.g. #cobblemon:is_volcanic, #cobblemon:is_thermal) list only biomes
from mods this pack does not load, so no biome carries them and their spawns never happen. An overlay appends
vanilla biomes the region plan paints for that identity (tags merge with "replace": false).

A vanilla biome is global, so a tag on it applies wherever that biome is painted. --check-paint measures, from the
paint maps, what share of each overlay biome's columns lie inside the overlay's regions, and fails below
--min-share, so an overlay cannot quietly leak an identity onto the rest of the map.

  python tools/spawn_tag_pack.py --out build/datapacks/cobblers_spawn_tags --check-paint build/paint/biomes.png
  python tools/spawn_tag_pack.py --install <server>/datapacks
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK_FORMAT = 48          # Minecraft 1.21.1 data packs
PACK_NAME = "cobblers_spawn_tags"


def tag_files(overlays):
    """{relative path: document} for every overlay tag."""
    out = {}
    for ov in overlays:
        ns, name = ov["tag"].split(":", 1)
        values = list(ov["biomes"]) + [{"id": b, "required": False} for b in ov.get("optional_biomes") or []]
        rel = "data/%s/tags/worldgen/biome/%s.json" % (ns, name)
        if rel in out:
            raise SystemExit("spawn_tag_overlays lists %s twice; merge the entries" % ov["tag"])
        out[rel] = {"replace": False, "values": values}
    return out


def build(regions_doc, out_dir: Path):
    overlays = regions_doc.get("spawn_tag_overlays") or []
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "data").mkdir(parents=True)
    (out_dir / "pack.mcmeta").write_text(json.dumps({"pack": {
        "pack_format": PACK_FORMAT,
        "description": "Cobblers: spawn tags for region identities no loaded biome carries (generated from data/regions.json)"}},
        indent=2) + "\n", encoding="utf-8")
    files = tag_files(overlays)
    for rel, doc in files.items():
        p = out_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return files


def check_paint(regions_doc, biomes_png: Path, min_share: float):
    import numpy as np
    from PIL import Image, ImageDraw
    import paint_maps as PM

    Image.MAX_IMAGE_PIXELS = None
    b = np.asarray(Image.open(biomes_png))
    n = b.shape[0]
    rows = []
    for ov in regions_doc.get("spawn_tag_overlays") or []:
        im = Image.new("L", (b.shape[1], n), 0)
        d = ImageDraw.Draw(im)
        for g in regions_doc["regions"]:
            if g["id"] in ov["regions"]:
                for ring in g["polygons"]:
                    d.polygon([tuple(p) for p in ring], fill=1)
        inside = np.asarray(im) > 0
        for biome in ov["biomes"]:
            bid = PM.WP_BIOMES.get(biome)
            if bid is None:
                rows.append({"tag": ov["tag"], "biome": biome, "painted_columns": 0, "inside_share": None,
                             "ok": False, "note": "not a paintable biome"})
                continue
            m = b == bid
            total = int(m.sum())
            share = float((m & inside).sum()) / total if total else None
            rows.append({"tag": ov["tag"], "biome": biome, "painted_columns": total,
                         "inside_share": round(share, 4) if share is not None else None,
                         "ok": share is not None and share >= min_share})
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--regions", default=str(ROOT / "data" / "regions.json"))
    p.add_argument("--out", default=str(ROOT / "build" / "datapacks" / PACK_NAME))
    p.add_argument("--check-paint", default=None, help="biomes.png from tools/paint_maps.py")
    p.add_argument("--min-share", type=float, default=0.95)
    p.add_argument("--install", default=None, help="copy the built pack into this datapacks folder")
    a = p.parse_args(argv)
    doc = json.loads(Path(a.regions).read_text(encoding="utf-8"))
    out = Path(a.out)
    files = build(doc, out)
    print("built %s: %s" % (out, ", ".join(sorted(files))))
    rc = 0
    if a.check_paint:
        rows = check_paint(doc, Path(a.check_paint), a.min_share)
        for r in rows:
            print("  %-24s %-26s painted %9s  inside its regions %s  %s" % (
                r["tag"], r["biome"], r["painted_columns"], r["inside_share"], "ok" if r["ok"] else "LEAKS"))
        if not all(r["ok"] for r in rows):
            rc = 1
    if a.install:
        dest = Path(a.install) / PACK_NAME
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(out, dest)
        print("installed", dest)
    return rc


if __name__ == "__main__":
    sys.exit(main())
