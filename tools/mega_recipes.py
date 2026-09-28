#!/usr/bin/env python
"""Mega Showdown's stone recipes raised to the Cutters' count of raw mega stones (docs/world-building/SOUTHERN_RIFT_MEGA.md
decision 5A; section 13 sets the count to 2).

Every Mega Stone recipe in Mega Showdown 1.0.2 (81) and ZAMegas 1.7.7 (11) is a shaped craft with one raw
`mega_showdown:mega_stone` in the middle of a 3 x 3 pattern whose four corners are empty (read from the jars,
2026-09-27). This writes each recipe back at its own path with the raw stone's key also in the first RAW_COUNT - 1
empty cells in reading order (at 2: the top left corner), so a crafted stone takes as many raw stones as the Cutters'
trade (data/gulch_mine.json cutters.offer.raw_count). Everything else in the recipe is the jar's own.

The recipes are the jar's content, and Mega Showdown's licence (MEGA SHOWDOWN LICENSE v2.1) is not MIT-style: nothing
here is committed. The pack is generated at `tools/reapply.py prepare` from the jar the server runs, into
build/datapacks/cobblers_mega_recipes (gitignored), and installed world-local. The jar must match the SHA-1
modpack/manifest/overlay.json pins, or nothing is written.

It also checks data/gulch_mine.json: every stone a Cutter offers, and every stone it lists as left out, is a stone in
the jars, the two lists do not meet, and together they are every stone.

  python tools/mega_recipes.py --server-dir <server>        reads <server>/mods (the jars only; nothing else)
  python tools/mega_recipes.py --jar-dir <folder with the two jars>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "datapacks" / "cobblers_mega_recipes"
OVERLAY = ROOT / "modpack" / "manifest" / "overlay.json"
GULCH = ROOT / "data" / "gulch_mine.json"
JARS = (("cobblemon_mega_showdown", "mega_showdown"), ("zamega", "zamega"))
RAW = "mega_showdown:mega_stone"
# the price is data (SOUTHERN_RIFT_MEGA.md 13: 2 raw stones a keyed stone, 4 before the owner's redesign): crafting
# takes what the Cutters' trade takes
RAW_COUNT = json.loads(GULCH.read_text(encoding="utf-8"))["cutters"]["offer"]["raw_count"]


class RecipeError(Exception):
    pass


def pins():
    """{namespace: (file name, sha1)} for the two jars, from the overlay manifest."""
    doc = json.loads(OVERLAY.read_text(encoding="utf-8"))
    rows = doc if isinstance(doc, list) else next(v for v in doc.values() if isinstance(v, list) and v and isinstance(v[0], dict) and "to_file" in v[0])
    out = {}
    for r in rows:
        f = r.get("to_file") or ""
        if f.startswith("mega_showdown-fabric-"):
            out["mega_showdown"] = (f, r.get("sha1"))
        elif f.startswith("zamega-fabric-"):
            out["zamega"] = (f, r.get("sha1"))
    missing = {"mega_showdown", "zamega"} - set(out)
    if missing:
        raise RecipeError("modpack/manifest/overlay.json pins no jar for %s" % sorted(missing))
    return out


def open_jars(folder):
    """{namespace: ZipFile}, each checked against its pinned SHA-1."""
    out = {}
    for ns, (name, sha1) in pins().items():
        p = Path(folder) / name
        if not p.is_file():
            raise RecipeError("no %s in %s" % (name, folder))
        have = hashlib.sha1(p.read_bytes()).hexdigest()
        if sha1 and have != sha1:
            raise RecipeError("%s is %s, overlay.json pins %s: not the jar the pack runs" % (name, have, sha1))
        out[ns] = zipfile.ZipFile(p)
    return out


def stones(jars):
    """{"ns:stone": (recipe path, recipe dict)} for every Mega Stone: a mega definition with a recipe at the same name."""
    out = {}
    for ns, z in jars.items():
        names = set(z.namelist())
        for n in sorted(names):
            pre = "data/%s/mega_showdown/mega/" % ns
            if not (n.startswith(pre) and n.endswith(".json")):
                continue
            stone = n[len(pre):-5]
            rp = "data/%s/recipe/%s.json" % (ns, stone)
            if rp not in names:
                raise RecipeError("%s:%s has a mega definition and no recipe" % (ns, stone))
            out["%s:%s" % (ns, stone)] = (rp, json.loads(z.read(rp), strict=False))
    return out


def raised(recipe, sid):
    """The recipe with the raw stone's key in the first three empty cells as well (RAW_COUNT in all)."""
    if recipe.get("type") != "minecraft:crafting_shaped":
        raise RecipeError("%s: not a shaped recipe (%s)" % (sid, recipe.get("type")))
    keys = [k for k, v in recipe["key"].items() if (v.get("item") if isinstance(v, dict) else None) == RAW]
    if len(keys) != 1:
        raise RecipeError("%s: %d keys name the raw stone, expected 1" % (sid, len(keys)))
    k = keys[0]
    rows = [list(r.ljust(3)) for r in recipe["pattern"]]
    if len(rows) != 3 or any(len(r) != 3 for r in rows):
        raise RecipeError("%s: the pattern is not 3 x 3" % sid)
    have = sum(r.count(k) for r in rows)
    if have != 1:
        raise RecipeError("%s: the pattern holds %d raw stones, expected 1" % (sid, have))
    empty = [(i, j) for i in range(3) for j in range(3) if rows[i][j] == " "]
    if len(empty) < RAW_COUNT - 1:
        raise RecipeError("%s: only %d empty cells" % (sid, len(empty)))
    for i, j in empty[:RAW_COUNT - 1]:
        rows[i][j] = k
    out = dict(recipe)
    out["pattern"] = ["".join(r) for r in rows]
    return out


def check_cutters(all_stones):
    g = json.loads(GULCH.read_text(encoding="utf-8"))["cutters"]
    offered = [s for b in g["benches"] for s in b["stones"]]
    left = g["left_out"]
    probs = []
    for s in offered + left:
        if s not in all_stones:
            probs.append("%s is not a Mega Stone in the pinned jars" % s)
    if len(set(offered)) != len(offered):
        probs.append("a Cutter stone is offered twice")
    if set(offered) & set(left):
        probs.append("offered and left out at once: %s" % sorted(set(offered) & set(left)))
    if set(offered) | set(left) != set(all_stones):
        probs.append("neither offered nor left out: %s" % sorted(set(all_stones) - set(offered) - set(left)))
    return probs, len(offered), len(left)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--server-dir", help="the server; only <server>/mods/<the two pinned jars> is read")
    g.add_argument("--jar-dir", help="a folder holding the two pinned jars")
    a = p.parse_args(argv)
    folder = Path(a.server_dir) / "mods" if a.server_dir else Path(a.jar_dir)
    try:
        jars = open_jars(folder)
        found = stones(jars)
        out = {sid: (rp, raised(r, sid)) for sid, (rp, r) in found.items()}
        probs, n_off, n_left = check_cutters(found)
    except RecipeError as e:
        raise SystemExit("mega_recipes: %s: nothing written" % e)
    if probs:
        for pr in probs:
            print("PROBLEM:", pr)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: Mega Stone recipes at %d raw stones (tools/mega_recipes.py; generated "
                                     "from the local jars, not redistributable)" % RAW_COUNT}}, indent=2) + "\n", encoding="utf-8")
    for sid, (rp, r) in sorted(out.items()):
        f = OUT / rp
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")
    print("wrote %s: %d recipes at %d raw stones (%d Mega Showdown, %d ZAMegas); the Cutters offer %d, leave out %d"
          % (OUT.relative_to(ROOT), len(out), RAW_COUNT, sum(1 for s in out if s.startswith("mega_showdown:")),
             sum(1 for s in out if s.startswith("zamega:")), n_off, n_left))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
