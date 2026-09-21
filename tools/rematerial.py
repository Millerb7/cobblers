#!/usr/bin/env python
"""Re-material a structure template: the same building in the materials of the place it stands.

CobbleTowns has four town Centres and three Marts, and all seven are in use. A Centre is one building everywhere
(the red roof is what says Centre), so the towns after them get that building in their own stone, trim and
planting. data/rematerial.json holds every derived template: its base, the block-for-block map, and why. The map
swaps like for like (stairs for stairs, slab for slab, a tall plant for a tall plant), so every block keeps
properties it actually has; the tool refuses a map whose source block is not in the base, which would be a typo.

  python tools/rematerial.py            # write every template data/rematerial.json lists

Ownership: generated from committed MIT bases into kits/structures/campaign/f4/services/towns/; each output is
recorded in kits/PROVENANCE.json.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import level_dat as L  # noqa: E402

MANIFEST = ROOT / "data" / "rematerial.json"


def rematerial(src, dest, mapping):
    """Write dest: src with every palette entry named in mapping renamed. -> {from: palette entries changed}."""
    raw = Path(src).read_bytes()
    name, root = L.loads(raw)
    if gzip.decompress(L.dumps(name, root)) != gzip.decompress(raw):
        raise SystemExit("%s does not round-trip through the NBT writer; refusing to rewrite it" % src)
    pal = root["palette"][1][1]
    present = {L.plain(e["Name"]) for e in pal}
    unknown = sorted(set(mapping) - present)
    if unknown:
        raise SystemExit("%s: the map names blocks the base does not contain: %s" % (src, ", ".join(unknown)))
    changed = {}
    for e in pal:
        nm = L.plain(e["Name"])
        if nm in mapping:
            e["Name"] = (L.STRING, mapping[nm])
            changed[nm] = changed.get(nm, 0) + 1
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_bytes(L.dumps(name, root))
    return changed


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest", default=str(MANIFEST))
    a = p.parse_args(argv)
    doc = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    maps = doc["maps"]
    for t in doc["templates"]:
        mapping = {}
        for m in t["maps"]:
            mapping.update(maps[m])
        base = ROOT / t["base"]
        # only the entries this base holds: a shared map lists blocks for Centres and Marts both
        _, root = L.loads(base.read_bytes())
        present = {L.plain(e["Name"]) for e in root["palette"][1][1]}
        mapping = {k: v for k, v in mapping.items() if k in present}
        changed = rematerial(base, ROOT / t["out"], mapping)
        print("%-58s %2d blocks re-materialed" % (t["out"], len(changed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
