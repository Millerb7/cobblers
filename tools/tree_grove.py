#!/usr/bin/env python
"""Grow the grove a tree town will inhabit: giant trees sized and spaced for building between. No platforms,
bridges or buildings: those are composition.

A habitat giant is built for a town, not for a skyline:
  trunk      5x5 with buttress roots, bare to FLOOR_Y so paths and stairs can wind up it
  floor tier 6-8 near-level limbs at FLOOR_Y..FLOOR_Y+4 reaching LIMB_REACH: what platforms rest on
  room       trunk only from the floor tier to CROWN_BASE: about 10 blocks of clear height for buildings
  crown      a broad canopy from CROWN_BASE to the top, radius CROWN_R, so the town is roofed and shaded

Layout: trunks on a ring around a central clearing plus an outer ring, each moved within MOVE blocks to the flattest
dry 5x5 ground, spaced so crowns just touch and limb tips leave a gap to bridge.

  python tools/tree_grove.py --source-root <root> [--site x,z --id name] [--all-shortlisted]
  writes kits/structures/prefabs/trees/tree_town/giant_<species>_<a|b|c>.nbt (+ .json), derived/sites/tree_grove_<id>.json,
  and a placement function in build/grove/ (not run)
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
from pathlib import Path

import numpy as np

import terrain as T
import structure_nbt as S
from landmark_trees import _ball, _leaves, _limb, _log, _rng, _roots

ROOT = Path(__file__).resolve().parent.parent
FLOOR_Y, ROOM, CROWN_R, LIMB_REACH = 16, 10, 14, 12
SPACING = 36
MOVE = 8
SPECIES = {"foothill_mixed": "oak", "birch_shore": "birch", "riparian_woods": "oak", "birch_plateau": "birch",
           "drowned_swamp": "mangrove", "broken_oakwood": "dark_oak"}


def habitat_giant(kind, variant):
    rng = _rng("habitat_giant_%s_%s" % (kind, variant))
    b = S.Builder()
    log_kind = {"birch": "birch", "mangrove": "mangrove", "dark_oak": "dark_oak"}.get(kind, "oak")
    top = FLOOR_Y + ROOM + 4 + int(rng.integers(0, 5))
    for y in range(-2, top - 2):
        for x in range(5):
            for z in range(5):
                if (x in (0, 4) and z in (0, 4)) and y > 6:
                    continue
                b.set(x, y, z, *_log(log_kind))
    _roots(b, 2, 2, 8, 8, log_kind, rng, top=4)
    n_limbs = int(rng.integers(6, 9))
    for k in range(n_limbs):
        ang = 2 * math.pi * k / n_limbs + rng.uniform(-0.2, 0.2)
        reach = LIMB_REACH * rng.uniform(0.85, 1.05)
        y0 = FLOOR_Y + rng.uniform(0, 2)
        tip = (2 + math.cos(ang) * reach, y0 + rng.uniform(1, 3), 2 + math.sin(ang) * reach)
        _limb(b, (2, y0, 2), tip, 1.5, log_kind)                     # near-level: platforms rest on these
    crown_base = FLOOR_Y + 4 + ROOM
    for k in range(5):                                               # upper limbs into the crown
        ang = 2 * math.pi * k / 5 + rng.uniform(-0.3, 0.3)
        tip = (2 + math.cos(ang) * CROWN_R * 0.7, crown_base + rng.uniform(4, 8), 2 + math.sin(ang) * CROWN_R * 0.7)
        _limb(b, (2, crown_base - 2, 2), tip, 1.0, log_kind)
        _ball(b, *tip, rng.uniform(5, 6.5), rng.uniform(3, 4), rng.uniform(5, 6.5), _leaves(log_kind), rng)
    _ball(b, 2, crown_base + 9, 2, CROWN_R, 6, CROWN_R, _leaves(log_kind), rng, ragged=0.2)
    return b, {"floor_tier_y": [FLOOR_Y, FLOOR_Y + 4], "room_clear_y": [FLOOR_Y + 5, crown_base - 1],
               "crown_y": [crown_base, crown_base + 15], "crown_radius": CROWN_R, "limb_reach": LIMB_REACH, "trunk": [5, 5]}


def write_prefab(kind, variant, b, dims):
    name = "giant_%s_%s" % (kind, variant)
    d = ROOT / "kits" / "structures" / "prefabs" / "trees" / "tree_town"
    d.mkdir(parents=True, exist_ok=True)
    data, shift = b.to_bytes()
    (d / (name + ".nbt")).write_bytes(data)
    lo, hi = b.bounds()
    side = {"schema": "cobblers.prefab/1", "template_id": "cobblers:kits/trees/tree_town/%s" % name, "kind": "trees",
            "set": "tree_town", "name": name, "author": "tools/tree_grove.py",
            "source": {"file": "generated", "imported": datetime.date.today().isoformat(), "size": (hi - lo + 1).tolist(),
                       "blocks": len(b.blocks)},
            "entrance": None, "grade_layer": None, "trunk_origin": [int(shift[0]), int(shift[1]), int(shift[2])],
            "habitat": dims, "notes": "trunk base at template (trunk_origin); the 5x5 trunk spans +0..+4 in x and z from it"}
    (d / (name + ".json")).write_text(json.dumps(side, indent=1) + "\n", encoding="utf-8")
    return side


def grove(heights, water, site, rng):
    cx, cz = site
    rings = [(0, 0)] if False else []
    for k in range(6):
        ang = 2 * math.pi * k / 6
        rings.append((cx + SPACING * math.cos(ang), cz + SPACING * math.sin(ang)))
    for k in range(4):
        ang = 2 * math.pi * (k + 0.5) / 4
        rings.append((cx + SPACING * 1.9 * math.cos(ang), cz + SPACING * 1.9 * math.sin(ang)))
    trees = []
    for x, z in rings:
        best = None
        for dx in range(-MOVE, MOVE + 1, 2):
            for dz in range(-MOVE, MOVE + 1, 2):
                tx, tz = int(round(x + dx)), int(round(z + dz))
                pad = heights[tz - 3:tz + 8, tx - 3:tx + 8]
                if water[tz - 12:tz + 17, tx - 12:tx + 17].any():
                    continue
                relief = float(pad.max() - pad.min())
                if best is None or relief < best[0]:
                    best = (relief, tx, tz)
        if best is None or best[0] > 4:
            continue
        if any(math.hypot(best[1] - t["x"], best[2] - t["z"]) < SPACING * 0.8 for t in trees):
            continue
        trees.append({"x": best[1], "z": best[2], "ground_y": int(math.floor(float(heights[best[2] + 2, best[1] + 2]))),
                      "pad_relief": round(best[0], 1)})
    gaps = []
    for i, t in enumerate(trees):
        d = min((math.hypot(t["x"] - u["x"], t["z"] - u["z"]) for j, u in enumerate(trees) if j != i), default=None)
        gaps.append(d)
    return trees, gaps


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--site", default=None)
    p.add_argument("--id", default=None)
    p.add_argument("--all-shortlisted", action="store_true")
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    from PIL import Image
    man = json.loads((ROOT / "build" / "paint" / "manifest.json").read_text(encoding="utf-8"))
    water = heights <= T.sea_level(world)
    for w in man["water"]:
        key = "levels" if "levels" in w else "mask"
        m = np.asarray(Image.open(ROOT / "build" / "paint" / w[key])) > 0
        water[w["z"]:w["z"] + m.shape[0], w["x"]:w["x"] + m.shape[1]] |= m
    sites = []
    if a.site:
        x, z = [int(v) for v in a.site.split(",")]
        sites.append({"id": a.id or "site_%d_%d" % (x, z), "x": x, "z": z, "forest": None})
    if a.all_shortlisted:
        short = json.loads((ROOT / "derived" / "sites" / "tree_town.json").read_text(encoding="utf-8"))["shortlist"]
        sites += [{"id": s["subregion"], "x": s["x"], "z": s["z"], "forest": s["forest"]} for s in short]
    written = {}
    out = []
    for s in sites:
        kind = SPECIES.get(s["forest"], "oak")
        rng = np.random.default_rng(abs(hash(s["id"])) % (2 ** 32))
        variants = []
        for v in "abc":
            key = (kind, v)
            if key not in written:
                b, dims = habitat_giant(kind, v)
                written[key] = write_prefab(kind, v, b, dims)
            variants.append(written[key])
        trees, gaps = grove(heights, water, (s["x"], s["z"]), rng)
        cmds = ["# grove for a tree town at %s (%d, %d): giants only, nothing built (tools/tree_grove.py)" % (s["id"], s["x"], s["z"])]
        for i, t in enumerate(trees):
            side = variants[i % 3]
            ox, oy, oz = side["trunk_origin"]
            rot = ["none", "clockwise_90", "180", "counterclockwise_90"][int(rng.integers(4))]
            from place_town import rotate
            rx, rz = rotate(ox, oz, rot)
            t.update({"object": side["template_id"], "rotation": rot})
            cmds.append("forceload add %d %d" % (t["x"], t["z"]))
            cmds.append("place template %s %d %d %d %s none 1.0 0" % (side["template_id"], t["x"] - rx, t["ground_y"] + 1 - oy, t["z"] - rz, rot))
            cmds.append("forceload remove %d %d" % (t["x"], t["z"]))
        rep = {"site": s, "species": kind, "giants": trees, "nearest_neighbour_blocks": [round(g, 1) if g else None for g in gaps],
               "limb_tip_gap_blocks": [round(g - 2 * LIMB_REACH - 5, 1) if g else None for g in gaps],
               "crown_overlap_blocks": [round(2 * CROWN_R - g, 1) if g else None for g in gaps],
               "habitat": variants[0]["habitat"]}
        path = ROOT / "derived" / "sites" / ("tree_grove_%s.json" % s["id"])
        path.write_text(json.dumps(rep, indent=1), encoding="utf-8")
        fn = ROOT / "build" / "grove" / ("grove_%s.mcfunction" % s["id"])
        fn.parent.mkdir(parents=True, exist_ok=True)
        fn.write_text("\n".join(cmds) + "\n", encoding="utf-8")
        out.append({"id": s["id"], "species": kind, "giants": len(trees), "nearest_neighbour": [min(g for g in gaps if g), max(g for g in gaps if g)] if trees else None,
                    "pad_relief_max": max(t["pad_relief"] for t in trees) if trees else None})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
