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
from place_town import rotate
import function_limits

ROOT = Path(__file__).resolve().parent.parent
FLOOR_Y, ROOM, CROWN_R, LIMB_REACH = 16, 10, 14, 12
SPACING = 36
MOVE = 8
# Bigger trees for the same town. `giant` is what the grove is built from and is never regenerated: its prefabs are
# already standing in the world. `elder` and `world` are additions, built by big_tree below.
#
# They are meant to read as the same thing at two ages. An elder is a world tree's sapling -- it takes the species
# of the wood it lands in, which is why there are seven of them, and it has the same trunk-and-storeys shape at a
# fifth of the size. There is one grown world tree, at Foothill Woods, and nothing else on the map is its scale.
#
#   storeys   limb tiers a town can floor over, `gap` apart; `room` is the clear trunk above the last one
#   crown     stacked solid balls from crown_base, (rise, radius, half-depth). Fine up to about radius 20; a solid
#             ellipsoid grows as r^2*h, so a radius-45 one is 135,000 leaves on its own
#   clusters  the world tree's canopy instead: (rise, ring radius, count, ball radius) rings of balls hung off
#             branches, which gets a 46-block crown for a third of the blocks and looks like foliage, not a dome
# The world tree is 418 blocks tall and needs the raised build limit (modpack/datapacks/cobblers_height, y575). At
# Foothill Woods, ground y116, its crown sits y456-534. Two numbers are not free choices: the first limb storey is
# at +56 so it clears every giant crown below it (those top out at ground+45), and the roots reach only 26 even
# though the tree could carry 60 -- the nearest giant trunk is 34.7 blocks away and roots at 60 would plough
# straight through its base.
TIERS = {
    "elder": {"floor": 20, "gap": 18, "storeys": 2, "room": 14, "trunk_r": 3, "reach": 17, "limb_r": 2.0,
              "limbs": (7, 10), "root_r": 13, "root_n": 10, "root_top": 6,
              "crown": [(12, 19, 8), (20, 12, 5)]},
    # A world tree's sapling, at the centre of Route 1's forest. The same shape language as the parent -- rounded
    # tapering trunk, hung cluster canopy -- at a tenth the size, and a little stockier (1:8 against the parent's
    # 1:12), which is how young trees read. One of them, alone, near Pallet: out of place on purpose.
    "sapling": {"floor": 16, "gap": 0, "storeys": 1, "room": 8, "trunk_r": 2, "reach": 11, "limb_r": 1.4,
                "limbs": (5, 7), "root_r": 8, "root_n": 8, "root_top": 3,
                "core": (6, 8, 5), "clusters": [(1, 12, 6, 6), (7, 7, 4, 5)]},
    "world": {"floor": 56, "gap": 38, "storeys": 8, "room": 14, "trunk_r": 17, "reach": 58, "limb_r": 5.0,
              "limbs": (9, 12), "root_r": 26, "root_n": 32, "root_top": 20,
              "core": (32, 38, 23),
              "clusters": [(4, 78, 13, 23), (26, 70, 15, 21), (48, 55, 13, 19), (66, 30, 9, 15)]},
}
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


def big_tree(kind, variant, tier):
    """An `elder` or `world` tree: the same habitat idea as habitat_giant, scaled up and given more limb storeys.

    habitat_giant is deliberately not routed through here. Its prefabs are already standing in the world, and
    regenerating them with different geometry would leave the placed trees and the files disagreeing.
    """
    t = TIERS[tier]
    rng = _rng("habitat_%s_%s_%s" % (tier, kind, variant))
    b = S.Builder()
    log_kind = {"birch": "birch", "mangrove": "mangrove", "dark_oak": "dark_oak", "spruce": "spruce",
                "cherry": "cherry", "jungle": "jungle", "acacia": "acacia"}.get(kind, "oak")
    R = t["trunk_r"]
    c = R                                                             # trunk spans 0..2R in x and z
    storeys = [t["floor"] + i * t["gap"] for i in range(t["storeys"])]
    crown_base = storeys[-1] + 4 + t["room"]
    for y in range(-2, crown_base + 3):                               # trunk, tapering above the first storey
        span = max(crown_base - storeys[0], 1)
        f = 1.0 if y <= storeys[0] else 1 - 0.45 * min(1.0, (y - storeys[0]) / span)
        rr = R * f
        for dx in range(-R, R + 1):
            for dz in range(-R, R + 1):
                if dx * dx + dz * dz > rr * rr + rr:                  # rounded, not a square column
                    continue
                b.set(c + dx, y, c + dz, *_log(log_kind))
    _roots(b, c, c, t["root_r"], t["root_n"], log_kind, rng, top=t["root_top"])
    tiers_out = []
    for si, sy in enumerate(storeys):                                 # near-level limbs: what a storey rests on
        n_limbs = int(rng.integers(*t["limbs"]))
        twist = rng.uniform(0, math.pi)
        for k in range(n_limbs):
            ang = 2 * math.pi * k / n_limbs + twist + rng.uniform(-0.15, 0.15)
            reach = t["reach"] * rng.uniform(0.82, 1.05) * (1 - 0.12 * si)
            y0 = sy + rng.uniform(0, 2)
            tip = (c + math.cos(ang) * reach, y0 + rng.uniform(1, 3), c + math.sin(ang) * reach)
            _limb(b, (c, y0, c), tip, t["limb_r"], log_kind)
        tiers_out.append([int(sy), int(sy) + 4])
    if "clusters" in t:                                               # the world tree: a canopy of hung masses
        cr, ch, cd = t["core"]
        _ball(b, c, crown_base + cr, c, ch, cd, ch, _leaves(log_kind), rng, ragged=0.2)
        top = crown_base + cr + cd
        for rise, ring, count, brad in t["clusters"]:
            for k in range(count):
                ang = 2 * math.pi * k / count + rng.uniform(-0.22, 0.22) + rise * 0.11
                rr = ring * rng.uniform(0.86, 1.06)
                bx, bz = c + math.cos(ang) * rr, c + math.sin(ang) * rr
                by = crown_base + rise + rng.uniform(-3, 3)
                _limb(b, (c, crown_base - 8, c), (bx, by - brad * 0.4, bz), t["limb_r"] * 0.55, log_kind)
                rx, rz = brad * rng.uniform(0.88, 1.12), brad * rng.uniform(0.88, 1.12)
                _ball(b, bx, by, bz, rx, brad * 0.62, rz, _leaves(log_kind), rng, ragged=0.26)
                top = max(top, int(by + brad * 0.62))
    else:
        for k in range(t["limbs"][0]):                                # upper limbs carrying the crown
            ang = 2 * math.pi * k / t["limbs"][0] + rng.uniform(-0.3, 0.3)
            r0 = t["crown"][0][1] * 0.7
            tip = (c + math.cos(ang) * r0, crown_base + rng.uniform(4, 9), c + math.sin(ang) * r0)
            _limb(b, (c, crown_base - 3, c), tip, t["limb_r"] * 0.6, log_kind)
            _ball(b, *tip, rng.uniform(6, 8), rng.uniform(4, 5), rng.uniform(6, 8), _leaves(log_kind), rng)
        for rise, rad, half in t["crown"]:                            # stacked canopy
            _ball(b, c, crown_base + rise, c, rad, half, rad, _leaves(log_kind), rng, ragged=0.22)
        top = crown_base + t["crown"][-1][0] + t["crown"][-1][2]
    return b, {"tier": tier, "floor_tier_y": tiers_out, "room_clear_y": [storeys[-1] + 5, crown_base - 1],
               "crown_y": [crown_base, int(top)], "crown_radius": (t["clusters"][0][1] if "clusters" in t else t["crown"][0][1]),
               "limb_reach": t["reach"],
               "trunk": [2 * R + 1, 2 * R + 1], "height": int(top)}


def write_prefab(kind, variant, b, dims, tier="giant"):
    name = "giant_%s_%s" % (kind, variant) if tier == "giant" else "%s_%s_%s" % (tier, kind, variant)
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
            "tier": tier, "habitat": dims,
            "notes": "trunk base at template (trunk_origin); the %dx%d trunk spans +0..+%d in x and z from it"
                     % (dims["trunk"][0], dims["trunk"][1], dims["trunk"][0] - 1)}
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


def footprint(px, pz, sx, sz, rot):
    """World box a template covers when placed at (px, pz) with `rot`.

    `place template` rotates about the placement position, so for 180 and the two 90s the template extends in the
    NEGATIVE direction. Taking min(px, px + sx) assumed it never did, which left the forceload box covering a
    corner of the tree instead of the tree -- the exact "That position is not loaded" failure the forceload exists
    to prevent.
    """
    corners = [rotate(dx, dz, rot) for dx in (0, sx) for dz in (0, sz)]
    xs = [px + c[0] for c in corners]
    zs = [pz + c[1] for c in corners]
    return min(xs), min(zs), max(xs), max(zs)


def fill_runs(blocks, origin, comment, limit=30000):
    """A Builder's blocks as run-length `fill` commands along x, split into functions.

    The world tree is 1.26 million blocks. That is too many for one `place template`: the structure loads its whole
    block list into memory and places it in a single tick, and the NBT alone runs to several megabytes. The cavern
    moved 1.94 million blocks as function fills without trouble, so this does the same. Runs are split at `limit`
    because maxCommandChainLength is 65536 by default and a function over it simply stops partway.
    """
    ox, oy, oz = origin
    runs = {}
    for (x, y, z), st in blocks.items():
        runs.setdefault((y, z, st), []).append(x)
    cmds = []
    for (y, z, st), xs in sorted(runs.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        name, props = st
        spec = name + ("[%s]" % ",".join("%s=%s" % kv for kv in sorted(props)) if props else "")
        xs.sort()
        i = 0
        while i < len(xs):
            j = i
            while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
                j += 1
            cmds.append("fill %d %d %d %d %d %d %s" % (ox + xs[i], oy + y, oz + z, ox + xs[j], oy + y, oz + z, spec))
            i = j + 1
    parts = [cmds[i:i + limit] for i in range(0, len(cmds), limit)]
    return [["# %s (part %d of %d)" % (comment, k + 1, len(parts))] + p for k, p in enumerate(parts)]


def _pad(ground, x, z, half, x0, z0):
    """Relief over a (2*half+1) square of real world ground, centred on (x, z). None if it runs off the extract."""
    a, b_ = z - half - z0, x - half - x0
    if a < 0 or b_ < 0 or a + 2 * half + 1 > ground.shape[0] or b_ + 2 * half + 1 > ground.shape[1]:
        return None
    pad = ground[a:a + 2 * half + 1, b_:b_ + 2 * half + 1].astype(float)
    return float(pad.max() - pad.min())


def augment(site_id, source_root=None, want_elders=4):
    """Add the world tree and a ring of elders to a grove that is already standing.

    The giants keep their positions: they are in the world. Clearances are horizontal only where the canopies
    share height. A giant's crown is ground+30..45 and an elder's is ground+56..81, so they never meet; what has
    to clear is trunk against limb tip. The world tree's first limb storey is ground+24 reaching 24, so it passes
    over a giant's clear trunk (its own crown starts at +30) as long as the trunks are well apart.
    """
    rep = json.loads((ROOT / "derived" / "sites" / ("tree_grove_%s.json" % site_id)).read_text(encoding="utf-8"))
    # a giant's record stores the trunk's MIN CORNER, not its centre: the 5x5 trunk spans +0..+4 from it. Spacing
    # and pad relief have to be measured centre to centre, or a 13-wide world tree is judged 6 blocks off where it
    # will stand, and is seated on the ground under its corner. The trees added here store the centre.
    giants = [dict(g, x=g["x"] + 2, z=g["z"] + 2) for g in rep["giants"]]
    cx, cz = rep["site"]["x"], rep["site"]["z"]
    # ground and water from the heightmap and the painted water model, never the world: augment runs over
    # a grove that is already standing, so the world's ground here is the last grove's roots and trunks
    import ground as G
    from elder_trees import painted_water
    box = (cx - 140, cz - 140, cx + 140, cz + 140)
    g_src = G.load(source_root)
    ground = g_src.box(*box)
    x0, z0 = box[0], box[1]
    wet_full = painted_water(g_src.heights, g_src.world)
    wet = wet_full[z0 - g_src.oz:box[3] - g_src.oz + 1, x0 - g_src.ox:box[2] - g_src.ox + 1]

    def dry(x, z, r):
        a, b_ = z - r - z0, x - r - x0
        if a < 0 or b_ < 0 or a + 2 * r + 1 > wet.shape[0] or b_ + 2 * r + 1 > wet.shape[1]:
            return False
        return not wet[a:a + 2 * r + 1, b_:b_ + 2 * r + 1].any()

    def gy(x, z):
        return int(ground[z - z0, x - x0])

    # the world tree: the flattest dry 15x15 near the grove's empty centre that keeps 28 blocks off every giant
    best = None
    for dz in range(-24, 25, 2):
        for dx in range(-24, 25, 2):
            x, z = cx + dx, cz + dz
            near = min(math.hypot(x - t["x"], z - t["z"]) for t in giants)
            if near < 28 or not dry(x, z, 30):
                continue
            r = _pad(ground, x, z, 7, x0, z0)
            if r is None or r > 2.0:
                continue
            score = near - 2 * r                                   # far from the giants, and level
            if best is None or score > best[0]:
                best = (score, x, z, r, near)
    world_tree = None
    if best is not None:
        _, x, z, r, near = best
        world_tree = {"x": x, "z": z, "ground_y": gy(x, z), "pad_relief": round(r, 1),
                      "nearest_giant": round(near, 1), "tier": "world"}

    # elders on two rings outside the giants, taking the ones that are level, dry and clear
    placed = [(t["x"], t["z"], 14) for t in giants]
    if world_tree:
        placed.append((world_tree["x"], world_tree["z"], 26))
    elders = []
    cands = []
    for radius in (56, 74):
        for k in range(12):
            ang = 2 * math.pi * k / 12 + (0.26 if radius == 74 else 0)
            cands.append((cx + radius * math.cos(ang), cz + radius * math.sin(ang)))
    for fx, fz in cands:
        if len(elders) >= want_elders:
            break
        best = None
        for dz in range(-10, 11, 2):
            for dx in range(-10, 11, 2):
                x, z = int(round(fx + dx)), int(round(fz + dz))
                if any(math.hypot(x - px, z - pz) < 30 for px, pz, _ in placed):
                    continue
                if any(math.hypot(x - e["x"], z - e["z"]) < 44 for e in elders):
                    continue
                if not dry(x, z, 22):
                    continue
                r = _pad(ground, x, z, 4, x0, z0)
                if r is None or r > 2.5:
                    continue
                if best is None or r < best[0]:
                    best = (r, x, z)
        if best is not None:
            r, x, z = best
            elders.append({"x": x, "z": z, "ground_y": gy(x, z), "pad_relief": round(r, 1), "tier": "elder"})
    return rep, world_tree, elders


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--site", default=None)
    p.add_argument("--id", default=None)
    p.add_argument("--augment", default=None, help="grove id: add the world tree and elders to a grove already placed")
    p.add_argument("--elders", type=int, default=4)
    p.add_argument("--all-shortlisted", action="store_true")
    p.add_argument("--surface-world", default=None, help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    if a.surface_world:
        raise SystemExit("--surface-world is gone: trunks are seated on the heightmap's ground (tools/ground.py), "
                         "never on a world, which holds the last grove")
    if a.augment:
        rep, wt, elders = augment(a.augment, a.source_root, a.elders)
        kind = SPECIES.get(rep["site"].get("forest"), "oak")
        from place_town import rotate
        rng = _rng("augment_" + a.augment)
        cmds = ["# %s: the world tree and elders added to the standing grove (tools/tree_grove.py --augment)" % a.augment]
        out = []
        # the world tree is deliberately NOT placed here. At 1.26M blocks it is past what `place template` can
        # carry, so tools/world_tree.py emits it as fill functions; writing it as a prefab too put a stale
        # 198-block tree inside the real one, and clearing that cost 61,678 commands.
        if wt:
            wt.update({"object": "cobblers:worldtree/* (fill functions, tools/world_tree.py)", "rotation": "none"})
        for t in elders:
            tier = t["tier"]
            variant = "a" if tier == "world" else "abc"[len(out) % 3]
            b, dims = big_tree(kind, variant, tier)
            side = write_prefab(kind, variant, b, dims, tier)
            ox, oy, oz = side["trunk_origin"]
            rot = "none" if tier == "world" else ["none", "clockwise_90", "180", "counterclockwise_90"][int(rng.integers(4))]
            rx, rz = rotate(ox, oz, rot)
            sx, sy, sz = side["source"]["size"]
            # t["x"], t["z"] is the trunk centre; builder (a, b) lands at (origin + rotate(a, b, rot)), so the
            # origin has to be pulled back by the rotated half-trunk for the centre to land where it was sited
            c = dims["trunk"][0] // 2
            cdx, cdz = rotate(c, c, rot)
            px, pz = t["x"] - cdx - rx, t["z"] - cdz - rz
            lo_x, lo_z, hi_x, hi_z = footprint(px, pz, sx, sz, rot)
            t.update({"object": side["template_id"], "rotation": rot, "height": dims["height"], "position": "trunk centre",
                      "crown_radius": dims["crown_radius"], "trunk": dims["trunk"], "top_y": t["ground_y"] + dims["height"]})
            cmds.append("forceload add %d %d %d %d" % (lo_x - 8, lo_z - 8, hi_x + 8, hi_z + 8))
            cmds.append("place template %s %d %d %d %s none 1.0 0" % (side["template_id"], px, t["ground_y"] + 1 - oy, pz, rot))
            # a skirt so the trunk meets the ground on the low side of a pad that is not perfectly level
            cmds.append("fill %d %d %d %d %d %d minecraft:grass_block replace #minecraft:air"
                        % (t["x"] - c - 1, t["ground_y"], t["z"] - c - 1, t["x"] + c + 1, t["ground_y"], t["z"] + c + 1))
            cmds.append("forceload remove %d %d %d %d" % (lo_x - 8, lo_z - 8, hi_x + 8, hi_z + 8))
            out.append(t)
        rep["world_tree"], rep["elders"] = wt, elders
        (ROOT / "derived" / "sites" / ("tree_grove_%s.json" % a.augment)).write_text(json.dumps(rep, indent=1), encoding="utf-8")
        fn = ROOT / "build" / "grove" / ("grove_%s_augment.mcfunction" % a.augment)
        fn.parent.mkdir(parents=True, exist_ok=True)
        fn.write_text("\n".join(function_limits.ensure_loaded(cmds)) + "\n", encoding="utf-8")
        print(json.dumps({"site": a.augment, "species": kind, "added": out,
                          "giants_kept": len(rep["giants"]), "function": str(fn.relative_to(ROOT))}, indent=1))
        return
    heights, world = T.load_from_args(a)
    from PIL import Image
    man = json.loads((ROOT / "build" / "paint" / "manifest.json").read_text(encoding="utf-8"))
    water = heights <= T.sea_level(world)
    for w in man["water"]:
        key = "levels" if "levels" in w else "mask"
        m = np.asarray(Image.open(ROOT / "build" / "paint" / w[key])) > 0
        water[w["z"]:w["z"] + m.shape[0], w["x"]:w["x"] + m.shape[1]] |= m
    import ground as G
    ground_of = G.load(a.source_root)
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
        rng = _rng("grove_" + s["id"])
        variants = []
        for v in "abc":
            key = (kind, v)
            if key not in written:
                b, dims = habitat_giant(kind, v)
                written[key] = write_prefab(kind, v, b, dims)
            variants.append(written[key])
        trees, gaps = grove(heights, water, (s["x"], s["z"]), rng)
        # seat each trunk on the heightmap's ground, rounded (tools/ground.py): the ground a fresh export has
        for t in trees:
            t["heightmap_ground_y"] = t["ground_y"]
            t["ground_y"] = ground_of(t["x"] + 2, t["z"] + 2)
        cmds = ["# grove for a tree town at %s (%d, %d): giants only, nothing built (tools/tree_grove.py)" % (s["id"], s["x"], s["z"])]
        for i, t in enumerate(trees):
            side = variants[i % 3]
            ox, oy, oz = side["trunk_origin"]
            rot = ["none", "clockwise_90", "180", "counterclockwise_90"][int(rng.integers(4))]
            from place_town import rotate
            rx, rz = rotate(ox, oz, rot)
            t.update({"object": side["template_id"], "rotation": rot})
            sx, sy, sz = side["source"]["size"]
            px, pz = t["x"] - rx, t["z"] - rz
            lo_x, lo_z, hi_x, hi_z = footprint(px, pz, sx, sz, rot)
            cmds.append("forceload add %d %d %d %d" % (lo_x - 8, lo_z - 8, hi_x + 8, hi_z + 8))
            cmds.append("place template %s %d %d %d %s none 1.0 0" % (side["template_id"], px, t["ground_y"] + 1 - oy, pz, rot))
            cmds.append("forceload remove %d %d %d %d" % (lo_x - 8, lo_z - 8, hi_x + 8, hi_z + 8))
        rep = {"site": s, "species": kind, "giants": trees, "nearest_neighbour_blocks": [round(g, 1) if g else None for g in gaps],
               "limb_tip_gap_blocks": [round(g - 2 * LIMB_REACH - 5, 1) if g else None for g in gaps],
               "crown_overlap_blocks": [round(2 * CROWN_R - g, 1) if g else None for g in gaps],
               "habitat": variants[0]["habitat"]}
        path = ROOT / "derived" / "sites" / ("tree_grove_%s.json" % s["id"])
        path.write_text(json.dumps(rep, indent=1), encoding="utf-8")
        fn = ROOT / "build" / "grove" / ("grove_%s.mcfunction" % s["id"])
        fn.parent.mkdir(parents=True, exist_ok=True)
        fn.write_text("\n".join(function_limits.ensure_loaded(cmds)) + "\n", encoding="utf-8")
        out.append({"id": s["id"], "species": kind, "giants": len(trees), "nearest_neighbour": [min(g for g in gaps if g), max(g for g in gaps if g)] if trees else None,
                    "pad_relief_max": max(t["pad_relief"] for t in trees) if trees else None})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
