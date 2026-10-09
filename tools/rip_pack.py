#!/usr/bin/env python
"""rip_pack.py - build the CLIENT resource pack that gives the dungeon rip its animated oval.

  python tools/rip_pack.py build   [--out build/client/cobblers-rip.zip]
  python tools/rip_pack.py install --instance DIR [--zip build/client/cobblers-rip.zip]

The rip (tools/dungeon.py R16DR) is an `item_display` of a vanilla item carrying a `custom_model_data`. This pack
turns that one item+value into a flat oval quad with an animated texture. It adds no mod and no datapack, is never
installed on the dedicated server, and holds only what tools/rip_art.py draws, so nothing in it is anyone's art.

WHAT IS IN IT (every path and rule below was read from the 1.21.1 client jar, `pack_version.resource` 34, or from
a pack already in this repository's runtime, 2026-10-09; none is from memory alone):

  pack.mcmeta                                        pack_format 34 (the jar's version.json), the same value tools/client_model_fix.py writes
  assets/minecraft/models/item/<item>.json           the carrier item's own model, as the jar ships it
                                                     (parent minecraft:item/generated, layer0 minecraft:item/<item>) PLUS
                                                     "overrides": [{"predicate": {"custom_model_data": N}, "model": ...}].
                                                     The 1.21.1 override mechanism, the one Cobblemon's own rods use for
                                                     their 'cast' predicate (assets/cobblemon/models/item/*_rod.json).
                                                     (1.21.2+ replaced it with assets/<ns>/items/; 1.21.1 has no such folder)
  assets/cobblers/models/item/dungeon_rip.json       two zero-thickness quads (a north face and a south face, so the oval
                                                     shows from both sides), the way the jar's block/cross.json draws a plane
  assets/cobblers/textures/item/dungeon_rip.png      frames stacked top to bottom, each W x H
  assets/cobblers/textures/item/dungeon_rip.png.mcmeta
                                                     {"animation": {"width", "height", "frametime", "interpolate"}}: the jar's
                                                     animation metadata reads frametime, frames, width, height, interpolate

HOW A PLAYER GETS IT. The zip is built on demand (it is never committed: build/ is disposable and a PNG is not
embedded in the .mrpack, tools/client_pack.py refuses an image), and handed over like the model-fix pack
(docs/decisions/ADR-006): `python tools/rip_pack.py build`, then each player copies build/client/cobblers-rip.zip into their
instance's resourcepacks/ and enables it, or runs `install --instance <their instance>`, which does the same and
puts it last in options.txt's resourcePacks (last = highest priority, as client_model_fix.install does). Without it a
player sees the carrier item (a big flat amethyst shard) where the oval stands.

NOT COVERED. Whether the oval looks right in game (only a client can say); that no other pack overrides the same
item model above ours (ours is listed last by `install`); full-bright is the display entity's own `brightness`
NBT, not a property of the model.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rip_art  # noqa: E402

DATA = ROOT / "data" / "dungeons.json"
PACK_FORMAT = 34          # Minecraft 1.21.1 resource packs (the client jar's version.json pack_version.resource)
PACK_NAME = "cobblers-rip.zip"
ZIP_DATE = (2026, 1, 1, 0, 0, 0)


def art_spec(doc):
    return doc["engine"]["rip_art"]


def _item_path(item):
    ns, name = item.split(":", 1)
    return "assets/%s/models/item/%s.json" % (ns, name)


def _res_path(res, kind, ext):
    ns, name = res.split(":", 1)
    return "assets/%s/%s/%s.%s" % (ns, kind, name, ext)


def carrier_model(spec):
    """The carrier item's model: the jar's own (generated, layer0) plus one override for our custom_model_data."""
    ns, name = spec["item"].split(":", 1)
    return {"parent": "minecraft:item/generated",
            "textures": {"layer0": "%s:item/%s" % (ns, name)},
            "overrides": [{"predicate": {"custom_model_data": spec["custom_model_data"]}, "model": spec["model"]}]}


def oval_model(spec):
    face = {"uv": [0, 0, 16, 16], "texture": "#0"}
    return {"textures": {"0": spec["texture"], "particle": spec["texture"]},
            "elements": [{"from": [0, 0, 8], "to": [16, 16, 8], "shade": False,
                          "faces": {"north": dict(face), "south": dict(face)}}]}


def mcmeta(spec):
    return {"animation": {"width": spec["frame"]["width"], "height": spec["frame"]["height"],
                          "frametime": spec["frametime_ticks"], "interpolate": bool(spec["interpolate"])}}


def files(doc):
    spec = art_spec(doc)
    w, h = spec["frame"]["width"], spec["frame"]["height"]
    png = rip_art.strip_png(w, h, spec["frames"])
    j = lambda o: (json.dumps(o, indent=2) + "\n").encode("utf-8")  # noqa: E731
    return {
        "pack.mcmeta": j({"pack": {"pack_format": PACK_FORMAT,
                                   "description": "Cobblers: the dungeon rip's animated oval (client only)"}}),
        _item_path(spec["item"]): j(carrier_model(spec)),
        _res_path(spec["model"], "models", "json"): j(oval_model(spec)),
        _res_path(spec["texture"], "textures", "png"): png,
        _res_path(spec["texture"], "textures", "png") + ".mcmeta": j(mcmeta(spec)),
    }


def write_zip(out, entries):
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, entries[name])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", type=Path, default=ROOT / "build" / "client" / PACK_NAME)
    i = sub.add_parser("install")
    i.add_argument("--instance", required=True, type=Path)
    i.add_argument("--zip", type=Path, default=ROOT / "build" / "client" / PACK_NAME)
    a = p.parse_args(argv)
    if a.cmd == "build":
        entries = files(json.loads(DATA.read_text(encoding="utf-8")))
        write_zip(a.out, entries)
        print("%s: %d files, %d bytes" % (a.out, len(entries), a.out.stat().st_size))
        return 0
    import client_model_fix as cmf   # its install() copies the zip and puts it last in options.txt (with a backup)
    packs = cmf.install(a.instance, a.zip)
    print("installed; top of the pack list:", packs[-3:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
