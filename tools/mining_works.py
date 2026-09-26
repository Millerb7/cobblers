#!/usr/bin/env python
"""The Craters' mining town, dressed as a working mine: the owner, 2026-09-25, "mine rails, ore piles, tons of theatrics".

Everything follows the town's own plan (data/placements.json mining_town: the ore road in from the west, the pithead
yard, the mine spur climbing to the barred adit):

  the track     rails down the middle of the mine spur from the adit's mouth, then west along the ore road to the
                pithead yard: the carts' way out of the mountain. On the paving the town plan grades (its street
                cells), off it on the heightmap's ground, never on a world's
  the headframe over a capped shaft in the middle of the yard: basalt legs, a deepslate crown, a chain hanging down
                the shaft, the shaft under an iron grate
  ore piles     one in each corner of the yard: coal, iron, copper, and spoil
  the slag heap east of the adit, and the adit's smoke: two campfires either side of its mouth

Rails and coal and iron ore decide spawns (Rolycoly, Carkol and Coalossal; Aron and Aggron), and the owner wants that
here (data/spawn_block_policy.json records it). Nothing is written where another of the town's builds stands: the
buildings' footprints, the other earthworks' cells, the lamp posts.

  python tools/mining_works.py --source-root <root>     # writes the earthwork mining_town_works
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
from pathlib import Path

import ground as G

ROOT = Path(__file__).resolve().parent.parent
SID = "mining_town"
RID = "mining_town_works"
PORTAL_MOUTH = (6735, 5808)          # just outside the adit's face (mining_portal builds z5809 and in)
HEADFRAME = (6620, 5699)             # the middle of the pithead yard
PILES = {                            # corner of the yard -> (centre, palette)
    "coal": ((6604, 5692), ["minecraft:coal_ore", "minecraft:deepslate_coal_ore", "minecraft:coal_block",
                            "minecraft:cobbled_deepslate"]),
    "iron": ((6636, 5692), ["minecraft:iron_ore", "minecraft:deepslate_iron_ore", "minecraft:raw_iron_block",
                            "minecraft:cobblestone"]),
    "copper": ((6604, 5707), ["minecraft:copper_ore", "minecraft:raw_copper_block", "minecraft:deepslate_copper_ore",
                              "minecraft:tuff"]),
    "spoil": ((6636, 5707), ["minecraft:cobbled_deepslate", "minecraft:tuff", "minecraft:andesite", "minecraft:cobblestone"]),
}
SLAG = (6748, 5798)
PILE_R = (3.0, 2.4)


def h32(*v):
    x = 0
    for i, t in enumerate(v):
        x ^= (int(t) * (73856093, 19349663, 83492791, 2654435761)[i % 4]) & 0xFFFFFFFF
    x = (x ^ (x >> 13)) * 0x5BD1E995 & 0xFFFFFFFF
    return x ^ (x >> 15)


def line(a, b):
    n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    return [(round(a[0] + (b[0] - a[0]) * i / n), round(a[1] + (b[1] - a[1]) * i / n)) for i in range(n + 1)]


def paved(plan):
    """{(x, z): y} of the town plan's graded paving: street cells and the yard."""
    out = {}
    for st in plan["streets"].values():
        for z, y, x0, x1 in st["cells"]:
            for x in range(x0, x1 + 1):
                out[(x, z)] = y
    x0, z0, x1, z1 = plan["plaza"]["rect"]
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            out[(x, z)] = plan["plaza"]["y"]
    return out


def occupied(doc, report):
    """Columns another mining-town build writes: building footprints and the other earthworks' cells."""
    cols = set()
    for b in report.get("buildings") or []:
        x0, z0, x1, z1 = b["footprint"]
        cols |= {(x, z) for x in range(x0 - 1, x1 + 2) for z in range(z0 - 1, z1 + 2)}
    for q in doc["placements"]:
        if q.get("settlement") != SID or q.get("kind") != "earthwork" or q["id"] == RID:
            continue
        for c in q.get("commands") or []:
            m = re.match(r"(?:fill|setblock) (-?\d+) -?\d+ (-?\d+)(?: (-?\d+) -?\d+ (-?\d+))?", c)
            if m:
                xa, za = int(m.group(1)), int(m.group(2))
                xb, zb = (int(m.group(3)), int(m.group(4))) if m.group(3) else (xa, za)
                cols |= {(x, z) for x in range(min(xa, xb), max(xa, xb) + 1) for z in range(min(za, zb), max(za, zb) + 1)}
    return cols


def lamp_cols(plan):
    return {(l["at"][0], l["at"][2]) for l in plan.get("lamps") or [] if isinstance(l, dict) and l.get("at")}


def build(g, plan, doc, report):
    c = ["# the Craters' mining town as a working mine (tools/mining_works.py)"]
    sb = lambda x, y, z, blk: c.append("setblock %d %d %d %s" % (x, y, z, blk))
    fill = lambda a, b, blk: c.append("fill %d %d %d %d %d %d %s" % (a + b + (blk,)))
    pave = paved(plan)
    # the lamps are glowstone set flush in the paving (plan paving.lamp), so the track runs over them; the piles and the
    # heap keep off them
    busy = occupied(doc, report)
    lamps = lamp_cols(plan)
    floor = lambda x, z: pave.get((x, z), g(x, z))
    streets = doc["settlements"][SID]["plan"]["streets"]
    spur = next(s["polyline"] for s in streets if s["id"] == "mine_spur")
    road = next(s["polyline"] for s in streets if s["id"] == "ore_road")
    # ---- the track: from the adit's mouth down the spur, then west along the ore road to the yard's east edge
    pts = line(PORTAL_MOUTH, tuple(spur[-1]))
    for a, b in zip(spur[::-1], spur[::-1][1:]):
        pts += line(tuple(a), tuple(b))[1:]
    x_yard = plan["plaza"]["rect"][2] + 2
    for a, b in zip(road[::-1], road[::-1][1:]):
        for p in line(tuple(a), tuple(b))[1:]:
            if p[0] >= x_yard:
                pts.append(p)
    # rails join only along x or z: a diagonal step becomes two, the corner taken on whichever side is free
    four = [pts[0]]
    for p in pts[1:]:
        q = four[-1]
        if p[0] != q[0] and p[1] != q[1]:
            a, b = (p[0], q[1]), (q[0], p[1])
            four.append(a if a not in busy else b)
        four.append(p)
    seen, track, skipped = set(), [], []
    for p in four:
        if p in seen:
            continue
        seen.add(p)
        (skipped if p in busy else track).append(p)
    if skipped:
        raise SystemExit("the track crosses %d cells another build owns, e.g. %s: move the track or that build"
                         % (len(skipped), skipped[:5]))
    for x, z in track:
        y = floor(x, z)
        if (x, z) not in pave:
            sb(x, y, z, "minecraft:gravel")                     # ballast where the track leaves the paving
        fill((x, y + 1, z), (x, y + 3, z), "minecraft:air")
        sb(x, y + 1, z, "minecraft:rail")                        # laid in order, so each joins the last
    # ---- the headframe over the shaft, in the middle of the yard
    hx, hz = HEADFRAME
    yy = plan["plaza"]["y"]
    fill((hx - 1, yy - 7, hz - 1), (hx + 1, yy - 1, hz + 1), "minecraft:air")                   # the shaft
    for x in (hx - 2, hx + 2):
        fill((x, yy - 7, hz - 2), (x, yy - 1, hz + 2), "minecraft:cobbled_deepslate")            # its lining
    for z in (hz - 2, hz + 2):
        fill((hx - 1, yy - 7, z), (hx + 1, yy - 1, z), "minecraft:cobbled_deepslate")
    fill((hx - 1, yy - 8, hz - 1), (hx + 1, yy - 8, hz + 1), "minecraft:cobbled_deepslate")      # its floor
    fill((hx - 1, yy, hz - 1), (hx + 1, yy, hz + 1), "minecraft:iron_trapdoor[facing=north,half=top,open=false]")
    for dx, dz in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
        fill((hx + dx, yy + 1, hz + dz), (hx + dx, yy + 11, hz + dz), "minecraft:polished_basalt[axis=y]")
    for y in (yy + 6, yy + 12):
        fill((hx - 2, y, hz - 2), (hx + 2, y, hz - 2), "minecraft:deepslate_brick_slab[type=bottom]")
        fill((hx - 2, y, hz + 2), (hx + 2, y, hz + 2), "minecraft:deepslate_brick_slab[type=bottom]")
        fill((hx - 2, y, hz - 1), (hx - 2, y, hz + 1), "minecraft:deepslate_brick_slab[type=bottom]")
        fill((hx + 2, y, hz - 1), (hx + 2, y, hz + 1), "minecraft:deepslate_brick_slab[type=bottom]")
    fill((hx - 1, yy + 12, hz), (hx + 1, yy + 12, hz), "minecraft:polished_basalt[axis=x]")      # the sheave's beam
    # the chain hangs from the beam to the grate and on down the shaft under it; the grate stays shut everywhere, so
    # nobody falls into a pit they cannot climb out of
    fill((hx, yy + 1, hz), (hx, yy + 11, hz), "minecraft:chain[axis=y]")
    fill((hx, yy - 6, hz), (hx, yy - 1, hz), "minecraft:chain[axis=y]")
    for dx, dz in ((-2, -2), (2, 2)):
        sb(hx + dx, yy + 12, hz + dz, "minecraft:lantern[hanging=false]")
    # ---- ore piles, a corner of the yard each
    for name, ((px, pz), pal) in sorted(PILES.items()):
        for x in range(int(px - PILE_R[0]) - 1, int(px + PILE_R[0]) + 2):
            for z in range(int(pz - PILE_R[1]) - 1, int(pz + PILE_R[1]) + 2):
                d = math.hypot((x - px) / PILE_R[0], (z - pz) / PILE_R[1])
                h = int(round(3.2 * (1 - d) + (h32(x, z, 3) % 3 - 1) * 0.4))
                if d >= 1 or h <= 0 or (x, z) in busy or (x, z) in lamps:
                    continue
                for k in range(h):
                    sb(x, yy + 1 + k, z, pal[h32(x, z, k, len(name)) % len(pal)])
    # ---- the slag heap east of the adit, on the heightmap's ground
    sx, sz = SLAG
    for x in range(sx - 5, sx + 6):
        for z in range(sz - 4, sz + 5):
            d = math.hypot((x - sx) / 5.0, (z - sz) / 4.0)
            if d >= 1 or (x, z) in busy or (x, z) in lamps:
                continue
            gy = g(x, z)
            h = int(round(4.5 * (1 - d))) + h32(x, z, 9) % 2
            for k in range(h):
                sb(x, gy + 1 + k, z, ("minecraft:basalt[axis=y]", "minecraft:blackstone", "minecraft:tuff",
                                      "minecraft:cobbled_deepslate")[h32(x, z, k, 5) % 4])
    # ---- smoke at the adit's mouth
    for x in (PORTAL_MOUTH[0] - 4, PORTAL_MOUTH[0] + 4):
        z = PORTAL_MOUTH[1]
        if (x, z) not in busy:
            sb(x, floor(x, z) + 1, z, "minecraft:campfire[lit=true,signal_fire=false,facing=south,waterlogged=false]")
    return c, len(track)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    a = p.parse_args(argv)
    g = G.Ground(a.source_root)
    plan = json.loads((ROOT / "derived" / "towns" / ("%s_plan.json" % SID)).read_text(encoding="utf-8"))
    report = json.loads((ROOT / "derived" / "towns" / ("%s_placement.json" % SID)).read_text(encoding="utf-8"))
    path = ROOT / "data" / "placements.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    cmds, n_track = build(g, plan, doc, report)
    rec = {"id": RID, "settlement": SID, "kind": "earthwork", "cell": "F7", "status": "planned", "after": "donors",
           "chosen_because": "the owner, 2026-09-25: the Craters' mining town needs mine rails, ore piles and theatrics, "
                             "and its fauna should be mining Pokemon; see tools/mining_works.py",
           "commands": cmds}
    at = next((i for i, q in enumerate(doc["placements"]) if q["id"] == RID), None)
    if at is None:
        doc["placements"].append(rec)
    else:
        doc["placements"][at] = rec
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote %s: %d commands, %d rails" % (RID, len(cmds), n_track))


if __name__ == "__main__":
    main()
