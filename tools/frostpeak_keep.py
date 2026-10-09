#!/usr/bin/env python
"""Wardenhold: a snow-covered winter keep on Frostpeak Strand's southern lip, built to be seen from Highwire.

Generated from data/frostpeak_keep.json into the world-local datapack build/datapacks/cobblers_frostpeak_keep.

The owner, 2026-10-09: "A SNOW-COVERED CASTLE at Frostpeak Strand, visible from Highwire. Measure the sightline before
siting it ... It should read as a landmark from Highwire first and a place second, so the silhouette matters more than
the interior." The site, the sightline numbers and the story are in docs/world-building/FROSTPEAK_KEEP.md; this file is
the building.

The shape, from the silhouette outwards (u east, v south, ry above the courtyard floor):

  curtain wall    49 x 41, three thick, walk at ry 10, merloned parapet to ry 12
  corner towers   four, 9 wide, hollow with three floors and a ladder, snow-block cone roofs to ry 40 (walls to ry 26)
  gatehouse       two towers flanking a five-wide arch in the north wall (the way in), cone roofs to ry 31
  postern         a three-wide door in the south wall, the way a walker from Highwire arrives
  the keep        19 x 19 on the courtyard's south half, three floors, a stair strip per floor, battlements at ry 30-32
  four turrets    on the keep's corners, solid, cone-roofed to ry 46
  the spire       11 wide from the keep roof, a ladder shaft, the beacon chamber (ry 47-54) with an open arcade, and a
                  snow-block cone to ry 68 with a finial: the tallest thing for 800 blocks, ry 71
  the plinth      the courtyard is the HIGHEST ground under the base rectangle, so nothing is cut; the lower ground is
                  filled with rock (a crag) and battered out at 0.8 per block to meet the hill

The materials answer the silhouette: dark masonry (deepslate and stone bricks) so the walls read against the sky, white
roofs (snow blocks) with blue-ice trim so they read against the dark, and the repository's one west wind
(data/frostpeak_summit.json wind) plasters packed ice on the west faces, its share rising with the height.

Nothing here is a spawn-condition block (the generator refuses one), nothing emits light (a ruin, dark by design:
STATE "Places are lit as towns" does not cover it), no chest or bed. The interior: the cold hall, the archive with the
Wardens' log (wall signs), the loft, the beacon chamber. The Pokemon that belong are Habitat Blocks
(data/habitat_blocks.json frostpeak_keep_*), placed by tools/habitat_blocks.py AFTER this pack (step order R9FK, R9E).

Ground comes from tools/ground.py (the canonical heightmap, rounded), never a world. The step for tools/reapply.py is
placement_steps(): hold the keep's chunks, run `cobblers:frostpeak_keep/build`, release.

  python tools/frostpeak_keep.py build [--source-root R] [--out DIR]   write the pack and derived/frostpeak_keep/
  python tools/frostpeak_keep.py plan  [--source-root R]               the numbers, the step and the probes
  python tools/frostpeak_keep.py probes [--source-root R]              write places.frostpeak_keep in data/world_probes.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "frostpeak_keep.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_frostpeak_keep"
REPORT = ROOT / "derived" / "frostpeak_keep"
NS = "cobblers"
FN = "frostpeak_keep"
AIR = "minecraft:air"
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()
# a test mutates these to prove the audit bites (CLAUDE.md: mutate the GENERATOR, never the record)
SPIRE_LIFT = 0          # added to the spire's chamber roof height
CLEAR_TOP_CUT = 0       # taken off the cleared volume's height


class KeepError(SystemExit):
    pass


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def unit(*key):
    h = hashlib.sha256("|".join(str(k) for k in key).encode()).hexdigest()
    return int(h[:12], 16) / float(16 ** 12)


def pick(table, u):
    acc = 0.0
    for value, share in table:
        acc += share
        if u < acc:
            return value
    return table[-1][0]


class Vox:
    """{(u, ry, v): state}: the later write wins. Specials (block entities) are kept apart."""

    def __init__(self):
        self.b = {}
        self.special = {}

    def put(self, u, y, v, s):
        self.b[(u, y, v)] = s
        self.special.pop((u, y, v), None)

    def box(self, u0, y0, v0, u1, y1, v1, s):
        for u in range(min(u0, u1), max(u0, u1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for v in range(min(v0, v1), max(v0, v1) + 1):
                    self.put(u, y, v, s)

    def air(self, u0, y0, v0, u1, y1, v1):
        self.box(u0, y0, v0, u1, y1, v1, AIR)

    def sign(self, u, y, v, facing, lines):
        q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
        self.b[(u, y, v)] = "minecraft:spruce_wall_sign[facing=%s,waterlogged=false]" % facing
        self.special[(u, y, v)] = "minecraft:spruce_wall_sign[facing=%s,waterlogged=false]{front_text:{messages:[%s]}}" % (facing, q)


def cells_sq(cu, cv, half, chamfer=True):
    for u in range(cu - half, cu + half + 1):
        for v in range(cv - half, cv + half + 1):
            if chamfer and half >= 3 and abs(u - cu) == half and abs(v - cv) == half:
                continue
            yield u, v


def wall_state(doc, u, y, v):
    return pick([tuple(e) for e in doc["palette"]["wall"]], unit("wall", u, y, v))


def pyramid(V, doc, cu, cv, y0, base_half, finial=True, trim_every=3):
    """A solid snow-block cone: halves base, base-1, base-1, base-2, ...; blue ice on the outer ring of every third layer."""
    pal = doc["palette"]
    halves = [base_half]
    h = base_half
    while h > 0:
        h -= 1
        halves += [h, h] if h > 0 else [0, 0]
    y = y0
    for i, half in enumerate(halves):
        for u, v in cells_sq(cu, cv, half, chamfer=False):
            ring = abs(u - cu) == half or abs(v - cv) == half
            V.put(u, y, v, pal["roof_trim"] if (ring and half > 0 and i % trim_every == 0) else pal["roof"])
        y += 1
    if finial:
        V.put(cu, y, cv, "minecraft:stone_brick_wall")
        V.put(cu, y + 1, cv, "minecraft:stone_brick_wall")
        V.put(cu, y + 2, cv, pal["rime"])
        return y + 2
    return y - 1


def hollow_tower(V, doc, cu, cv, half, top, floors, ladder_dir, roof_base, doors=(), slit_ys=(4, 14, 23), roof=True):
    """A tower of shell thickness two. doors: [(u, v, y0, y1)] cells carved through the shell. A ladder runs up the
    interior cell next to the +ladder_dir shell, floors have a one-block hole there."""
    cells = list(cells_sq(cu, cv, half))
    inner = {(u, v) for u, v in cells_sq(cu, cv, half - 2, chamfer=False)}
    for u, v in cells:
        for y in range(1, top + 1):
            V.put(u, y, v, AIR if (u, v) in inner else wall_state(doc, u, y, v))
    lu, lv = cu + ladder_dir[0] * (half - 2), cv + ladder_dir[1] * (half - 2)
    for fy in floors:
        for u, v in inner:
            if (u, v) != (lu, lv):
                V.put(u, fy, v, wall_state(doc, u, fy, v))
    face = {(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}[tuple(ladder_dir)]
    for y in range(1, top - 1):
        V.put(lu, y, lv, "minecraft:ladder[facing=%s]" % face)
    for sy in slit_ys:
        if sy < top:
            for (du, dv) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (du, dv) == tuple(ladder_dir):
                    continue
                for k in (half - 1, half):
                    V.put(cu + du * k, sy, cv + dv * k, AIR)
    for (u, v, y0, y1) in doors:
        for y in range(y0, y1 + 1):
            V.put(u, y, v, AIR)
    if roof:
        return pyramid(V, doc, cu, cv, top + 1, half + 1)
    return top


def solid_tower(V, doc, cu, cv, half, y0, top, roof_base):
    for u, v in cells_sq(cu, cv, half):
        for y in range(y0, top + 1):
            V.put(u, y, v, wall_state(doc, u, y, v))
    return pyramid(V, doc, cu, cv, top + 1, roof_base)


def building(doc):
    """The building above the courtyard floor, in (u, ry, v), plus the notes the later stages need."""
    d = doc["dims"]
    pal = doc["palette"]
    V = Vox()
    HU, HV, T = d["wall_hu"], d["wall_hv"], d["wall_thick"]
    notes = {}
    # ---- the courtyard floor, ry 0, inside the base rectangle (the plinth stage lays what is below)
    for u in range(-d["base_hu"], d["base_hu"] + 1):
        for v in range(-d["base_hv"], d["base_hv"] + 1):
            outside = abs(u) > HU or abs(v) > HV
            if outside:
                V.put(u, 0, v, pick([("minecraft:snow_block", 0.3), ("minecraft:stone", 0.3), ("minecraft:tuff", 0.2),
                                     ("minecraft:cobbled_deepslate", 0.2)], unit("terrace", u, v)))
            else:
                V.put(u, 0, v, pick([tuple(e) for e in pal["paving"]], unit("pave", u, v)))
    # ---- the curtain wall
    walk, par = d["wall_walk"], d["wall_parapet"]
    for u in range(-HU, HU + 1):
        for v in range(-HV, HV + 1):
            if abs(u) <= HU - T and abs(v) <= HV - T:
                continue
            for y in range(1, walk):
                V.put(u, y, v, wall_state(doc, u, y, v))
            V.put(u, walk, v, wall_state(doc, u, walk, v))
            outer = abs(u) == HU or abs(v) == HV
            if outer:
                V.put(u, walk + 1, v, wall_state(doc, u, walk + 1, v))
                merlon = (u % 2 == 0) if abs(v) == HV else (v % 2 == 0)
                if merlon:
                    V.put(u, par, v, wall_state(doc, u, par, v))
    # ---- the gate: a five-wide arch in the north wall, its portcullis raised
    for u in range(-2, 3):
        for v in range(-HV, -HV + T):
            for y in range(1, 5 if abs(u) == 2 else 6):
                V.put(u, y, v, AIR)
    for u in (-1, 0, 1):
        V.put(u, 5, -HV + 1, "minecraft:iron_bars")
    # ---- the postern: three wide, four high, in the south wall west of the keep's axis
    PU = -14
    for u in range(PU - 1, PU + 2):
        for v in range(HV - T + 1, HV + 1):
            for y in range(1, 5):
                V.put(u, y, v, AIR)
    notes["postern"] = (PU, HV)
    # ---- the four corner towers
    top = d["corner_wall"]
    ch = d["corner_half"]
    for su in (-1, 1):
        for sv in (-1, 1):
            cu, cv = su * (HU - 1), sv * (HV - 1)
            uf, vf = cu - su * ch, cv - sv * ch                # the faces toward the courtyard
            doors = [(uf, cv - sv * 2, 1, 2), (uf + su, cv - sv * 2, 1, 2),                      # ground door, courtyard side
                     (uf, cv, walk + 1, walk + 2), (uf + su, cv, walk + 1, walk + 2),            # the wall walk, one way
                     (cu, vf, walk + 1, walk + 2), (cu, vf + sv, walk + 1, walk + 2)]             # and the other
            notes["corner_tip_ry"] = hollow_tower(V, doc, cu, cv, ch, top, d["corner_floors"], (su, 0), ch + 1, doors)
    # ---- the gatehouse towers, astride the north wall
    gh = d["gate_towers_half"]
    for su in (-1, 1):
        cu, cv = su * 8, -HV + 1
        uf = cu - su * gh
        doors = [(uf, cv, walk + 1, walk + 2), (uf + su, cv, walk + 1, walk + 2),
                 (cu + su * gh, cv, walk + 1, walk + 2), (cu + su * (gh - 1), cv, walk + 1, walk + 2),
                 (cu, cv + gh, 1, 2), (cu, cv + gh - 1, 1, 2)]                                    # courtyard door, ground floor
        notes["gate_tip_ry"] = hollow_tower(V, doc, cu, cv, gh, d["gate_wall"], [10], (su, 0), gh + 1, doors, slit_ys=(4, 14))
    # ---- the keep
    kh, kc, kt, kf, kr = d["keep_half"], d["keep_cv"], d["keep_thick"], d["keep_floors"], d["keep_roof"]
    for u in range(-kh, kh + 1):
        for v in range(kc - kh, kc + kh + 1):
            core = abs(u) <= kh - kt and abs(v - kc) <= kh - kt
            for y in range(1, kr):
                V.put(u, y, v, AIR if core else wall_state(doc, u, y, v))
            V.put(u, kr, v, wall_state(doc, u, kr, v))
            edge = abs(u) == kh or abs(v - kc) == kh
            if edge:
                V.put(u, kr + 1, v, wall_state(doc, u, kr + 1, v))
                if (u + v) % 2 == 0:
                    V.put(u, kr + 2, v, wall_state(doc, u, kr + 2, v))
    ih = kh - kt
    # floors, with a stair strip per level (east, west, east), climbing south
    strips = {kf[0]: (ih - 1, ih), kf[1]: (-ih, -ih + 1), kr: (ih - 1, ih)}
    levels = [0, kf[0], kf[1], kr]
    run_v0 = kc - ih + 1
    for lvl, nxt in zip(levels, levels[1:]):
        h = nxt - lvl
        su0, su1 = strips[nxt]
        for u in range(-ih, ih + 1):
            for v in range(kc - ih, kc + ih + 1):
                # the floor above is cut only where a climber's head would meet it: the stair i has its head at lvl + 3 + i,
                # the floor is at lvl + h, so the last three stairs of a ten-block run (i = 7, 8, 9)
                in_strip = su0 <= u <= su1 and run_v0 + h - 3 <= v <= run_v0 + h - 1
                V.put(u, nxt, v, AIR if in_strip else wall_state(doc, u, nxt, v))
        for i in range(h):
            for u in range(su0, su1 + 1):
                V.put(u, lvl + 1 + i, run_v0 + i, "minecraft:stone_brick_stairs[facing=north,half=bottom,shape=straight]")
    # the keep's doors: north (the courtyard), three wide
    for u in (-1, 0, 1):
        for v in range(kc - kh, kc - kh + kt):
            for y in range(1, 4):
                V.put(u, y, v, AIR)
    for v in range(kc - kh, kc - kh + kt):
        V.put(0, 4, v, AIR)
    # slits on the other faces
    for sy in (5, 15, 25):
        for off in (-4, 4):
            for k in range(kt):
                for y in (sy, sy + 1):
                    V.put(off, y, kc - kh + k, AIR)
                    V.put(off, y, kc + kh - k, AIR)
                    V.put(-kh + k, y, kc + off, AIR)
                    V.put(kh - k, y, kc + off, AIR)
    # ---- the keep's turrets (solid), on its roof corners
    th = d["turret_half"]
    for su in (-1, 1):
        for sv in (-1, 1):
            notes["turret_tip_ry"] = solid_tower(V, doc, su * (kh - th), kc + sv * (kh - th), th, kr + 1, kr + 6, th + 1)
    # ---- the spire: centre (0, kc), hollow, a ladder, the beacon chamber and its cone
    sh = d["spire_half"]
    sf, swt = d["spire_floor"], d["spire_wall_top"]
    for u, v in cells_sq(0, kc, sh, chamfer=False):
        inner = abs(u) <= sh - 2 and abs(v - kc) <= sh - 2
        for y in range(kr + 1, sf):
            V.put(u, y, v, AIR if inner else wall_state(doc, u, y, v))
        for y in range(sf, swt + 1):
            V.put(u, y, v, AIR if (inner and y > sf) else wall_state(doc, u, y, v))
    lv = kc + sh - 2
    for y in range(kr + 1, sf + 1):
        V.put(0, y, lv, "minecraft:ladder[facing=north]")
    # the spire's door on its east face, from the pocket the third stair run opens into: the turrets (SE, NE) and the
    # spire close that strip's pocket off from the rest of the roof, so the door must face it
    for u in (sh, sh - 1):
        for y in (kr + 1, kr + 2):
            V.put(u, y, kc, AIR)
    # a lamp-less slit pair on each side of the shaft
    for sy in (kr + 8, kr + 13):
        for k in (sh - 1, sh):
            V.put(k, sy, kc, AIR)
            V.put(-k, sy, kc, AIR)
    # the beacon chamber's arcade: bars in the outer cell, air behind
    for y in range(sf + 2, sf + 6):
        for off in (-2, -1, 0, 1, 2):
            V.put(off, y, kc - sh, "minecraft:iron_bars")
            V.put(off, y, kc - sh + 1, AIR)
            V.put(off, y, kc + sh, "minecraft:iron_bars")
            V.put(off, y, kc + sh - 1, AIR)
            V.put(-sh, y, kc + off, "minecraft:iron_bars")
            V.put(-sh + 1, y, kc + off, AIR)
            V.put(sh, y, kc + off, "minecraft:iron_bars")
            V.put(sh - 1, y, kc + off, AIR)
    # the chamber's ceiling and cone
    for u, v in cells_sq(0, kc, sh, chamfer=False):
        V.put(u, swt + 1 + SPIRE_LIFT, v, wall_state(doc, u, swt + 1, v))
    spire_top = pyramid(V, doc, 0, kc, swt + 2 + SPIRE_LIFT, sh + 1)
    notes["spire_top_ry"] = spire_top
    notes["beacon"] = {"floor_ry": sf, "ladder": (0, lv), "nest": (-1, sf, kc + 1), "brazier": (0, sf + 1, kc)}
    # ---- the west wind's rime on the exposed west faces (the repository's one wind; data/frostpeak_summit.json wind)
    lo, hi = pal["rime_share"]
    top_ry = max(y for (_u, y, _v) in V.b)
    for (u, y, v), st in list(V.b.items()):
        if y < 3 or not st.split("[")[0].endswith("bricks") or (u - 1, y, v) in V.b:
            continue
        share = lo + (hi - lo) * min(1.0, y / float(top_ry))
        if unit("rime", u, y, v) < share:
            V.put(u, y, v, pal["rime"])
    # ---- the courtyard: a frozen well, and the hall furnishings
    for u in range(-13, -10):
        for v in range(-2, 1):
            if (u, v) != (-12, -1):
                V.put(u, 1, v, "minecraft:cobblestone")
    V.put(-12, 0, -1, pal["rime"])
    V.put(-12, 1, -1, pal["rime"])
    furnish(V, doc, d)
    return V, notes


def furnish(V, doc, d):
    """The three rooms: the cold hall (ry 1-9), the archive (ry 11-19) with the Wardens' log, the loft (ry 21-29)."""
    kc, kh, kt = d["keep_cv"], d["keep_half"], d["keep_thick"]
    ih = kh - kt
    n_in, s_in = kc - ih, kc + ih          # the interior's north and south rows
    # the hall: a long table with benches, a cold hearth in the west wall
    for u in range(-3, 4):
        V.put(u, 1, kc, "minecraft:spruce_fence")
        V.put(u, 2, kc, "minecraft:spruce_slab[type=top]")
        V.put(u, 1, kc - 2, "minecraft:spruce_stairs[facing=south,half=bottom]")
        V.put(u, 1, kc + 2, "minecraft:spruce_stairs[facing=north,half=bottom]")
    for v in range(kc - 1, kc + 2):
        V.put(-ih, 1, v, "minecraft:stone_bricks")
        V.put(-ih, 2, v, "minecraft:stone_bricks" if v != kc else "minecraft:campfire[lit=false,facing=east]")
        V.put(-ih, 3, v, "minecraft:stone_bricks")
    # the archive (ry 11-19): shelves on the north wall, a lectern and a barrel row; the log's signs above the shelves
    for u in range(-ih, ih + 1):
        if abs(u) <= 1:
            continue
        V.put(u, 11, n_in, "minecraft:bookshelf")
        V.put(u, 12, n_in, "minecraft:bookshelf")
    V.put(0, 11, n_in, "minecraft:lectern[facing=south,has_book=false,powered=false]")
    log = doc["log"]
    for i, entry in enumerate(log["entries"]):
        V.sign(entry["u"], 14, n_in, "south", entry["lines"])
    for u in (-ih + 1, ih - 1):
        V.put(u, 11, s_in, "minecraft:barrel[facing=up]")
    # the loft (ry 21-29): the lookout's desk at the south slit, the chart signs
    for u in range(-3, 4):
        V.put(u, 21, s_in - 1, "minecraft:spruce_slab[type=bottom]")
    V.put(-ih + 1, 21, s_in, "minecraft:barrel[facing=up]")
    V.put(ih - 1, 21, s_in, "minecraft:barrel[facing=up]")
    for i, entry in enumerate(log["loft"]):
        V.sign(entry["u"], 23, n_in, "south", entry["lines"])
    # the beacon chamber: the dead basin and the last entry
    sf = d["spire_floor"]
    V.put(0, sf + 1, kc, "minecraft:cauldron")
    last = log["last"]
    V.sign(last["u"], sf + 1, last["v"], last["facing"], last["lines"])


# ------------------------------------------------------------------------------------------------ the site and the world
SNOWABLE = ("stone_bricks", "cracked_stone_bricks", "deepslate_bricks", "cracked_deepslate_bricks", "tuff_bricks",
            "cobblestone", "gravel", "stone", "tuff", "cobbled_deepslate", "andesite")
STAIR = "minecraft:stone_brick_stairs[facing=north,half=bottom,shape=straight]"
NOT_PLACES = {"regions.json", "landmarks.json", "cells.json", "visibility.json", "frostpeak_keep.json"}


def strand_polygon():
    regs = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    sub = next(r for r in regs["subregions"] if r["id"] == "frostpeak_strand")
    return sub["polygons"][0]


def in_polygon(x, z, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % n]
        if (z0 > z) != (z1 > z):
            if x < x0 + (z - z0) * (x1 - x0) / (z1 - z0):
                inside = not inside
    return inside


def base_rect(doc):
    cx, cz = doc["site"]["centre"]
    d = doc["dims"]
    return cx - d["base_hu"], cz - d["base_hv"], cx + d["base_hu"], cz + d["base_hv"]


def siting(doc, g):
    """(pad, problems): the courtyard floor is the highest ground under the base rectangle; the rectangle lies wholly in
    the Strand's polygon, and no authored x/z of another place lies within `clear` blocks of it."""
    x0, z0, x1, z1 = base_rect(doc)
    pad = max(g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    bad = []
    poly = strand_polygon()
    outside = [(x, z) for x in range(x0, x1 + 1) for z in (z0, z1) if not in_polygon(x, z, poly)] \
        + [(x, z) for z in range(z0, z1 + 1) for x in (x0, x1) if not in_polygon(x, z, poly)]
    if outside:
        bad.append("%d base-rectangle edge columns lie outside frostpeak_strand's polygon, first %s" % (len(outside), outside[0]))
    import southern_residents as SR
    clear = doc["site"].get("clear_of_places", 100)
    # this keep's own records in other files (its two Habitat Blocks) are skipped by id, as the residents tools do
    mine = {"residents": [{"records": {"quest": "frostpeak_keep_hall_ward", "conversation": "frostpeak_keep_beacon_ward"}}]}
    pts = [p for p in SR.authored_points(mine, own_file=str(DATA)) if p[2] not in NOT_PLACES]
    near = min(((math.hypot(max(x0 - px, px - x1, 0), max(z0 - pz, pz - z1, 0)), px, pz, f) for px, pz, f in pts))
    if near[0] < clear:
        bad.append("%s authors (%s, %s), %.0f blocks from the base rectangle (needs %d)" % (near[3], near[1], near[2], near[0], clear))
    cb, _ = SR.corridor_check("frostpeak_keep", {(x, z) for x in range(x0, x1 + 1, 4) for z in range(z0, z1 + 1, 4)}, clear)
    bad += cb
    return pad, bad


def plan(doc, g):
    d = doc["dims"]
    pal = doc["palette"]
    cx, cz = doc["site"]["centre"]
    x0, z0, x1, z1 = base_rect(doc)
    pad, bad = siting(doc, g)
    if bad:
        raise KeepError("Wardenhold's site fails: " + "; ".join(bad))
    V, notes = building(doc)
    F, S = {}, {}
    for (u, ry, v), s in V.b.items():
        if s != AIR:
            F[(cx + u, pad + ry, cz + v)] = s
    for (u, ry, v), s in V.special.items():
        S[(cx + u, pad + ry, cz + v)] = s
    top_ry = max(k[1] for k, s in V.b.items() if s != AIR)
    for cell in habitat_cells(doc, pad).values():          # the Habitat Blocks' mimic floor, there before they are
        F[cell] = "minecraft:stone_bricks"
    base = [tuple(e) for e in pal["base"]]
    hu, hv, reach, bat = d["base_hu"], d["base_hv"], d["batter_reach"], d["batter"]
    plinth = 0
    edge_over = -99
    # ---- the plinth: rock under the rectangle, battered out to meet the hill; the gate ramp (u -2..2) is stairs down
    # the batter on the north axis, one block of fall per block of run (batter 1.0), replacing the batter's top block
    for x in range(cx - hu - reach, cx + hu + reach + 1):
        for z in range(cz - hv - reach, cz + hv + reach + 1):
            u, v = x - cx, z - cz
            du, dv = max(abs(u) - hu, 0), max(abs(v) - hv, 0)
            dist = math.hypot(du, dv)
            if dist > reach:
                continue
            gy = g(x, z)
            top = pad - 1 if dist == 0 else pad - math.ceil(dist * bat)
            if dist > reach - 1.5:
                edge_over = max(edge_over, top - gy)
            if top <= gy:
                continue
            if dist > 0:
                for y in range(top + 1, top + 7):
                    F.setdefault((x, y, z), AIR)
            for y in range(gy + 1, top + 1):
                depth = top - y
                if depth <= 1:
                    s = pick([("minecraft:snow_block", 0.35)] + [(b, w * 0.65) for b, w in base], unit("plinth", x, y, z))
                else:
                    s = "minecraft:stone"
                if (x, y, z) not in F:
                    F[(x, y, z)] = s
                plinth += 1
            if abs(u) <= 2 and v < -hv and bat == 1.0:
                F[(x, top, z)] = STAIR
    for u in range(-2, 3):
        F[(cx + u, pad, cz - hv)] = STAIR
    if edge_over > 1:
        raise KeepError("the plinth's batter ends %d blocks above the hill at its reach (%d): raise dims.batter_reach" % (edge_over, reach))
    # ---- the postern lane: a cutting south of the south wall, a flight of stairs up to the hill. The flat part is
    # gravel at the courtyard's level (standing pad + 1); step j of the flight is a stair block at pad + j, so its top
    # (standing pad + j + 1) meets the hill's own standing level (ground + 1) at the lane's far end.
    PU, _ = notes["postern"]
    lane_len = 16
    ends = [g(cx + PU + du, cz + hv + 1 + lane_len) for du in (-1, 0, 1)]
    rise = max(0, max(ends) - pad)
    if rise > lane_len - 3:
        raise KeepError("the postern lane would climb %d blocks in %d: lengthen it" % (rise, lane_len))
    lane_cells = set()
    for t in range(0, lane_len):
        z = cz + hv + 1 + t
        k = t - (lane_len - rise)
        for du in (-1, 0, 1):
            x = cx + PU + du
            gy = g(x, z)
            lane_cells.add((x, z))
            if k >= 0:
                y = pad + k + 1
                F[(x, y, z)] = STAIR
            else:
                y = pad
                F[(x, y, z)] = pick([("minecraft:gravel", 0.5), ("minecraft:cobblestone", 0.5)], unit("lane", x, z))
            for yy in range(gy + 1, y):
                F[(x, yy, z)] = "minecraft:stone"
            for yy in range(y + 1, max(gy, y) + 3):
                F[(x, yy, z)] = AIR
    # ---- snow: layers on the tops of the exposed masonry, deeper on a wall's lee (east) side
    colmax = {}
    for (x, y, z), s in F.items():
        if y >= pad and s != AIR and (x, z) not in lane_cells and ((x, z) not in colmax or y > colmax[(x, z)][0]):
            colmax[(x, z)] = (y, s)
    snow = {}
    for (x, z), (y, s) in colmax.items():
        if s.split("[")[0].replace("minecraft:", "") not in SNOWABLE:
            continue
        n = 1 + int(unit("snow", x, z) * 3)
        w = colmax.get((x - 1, z))
        if w and w[0] > y:
            n = min(5, n + 1 + (w[0] - y > 3))
        snow[(x, y + 1, z)] = "minecraft:snow[layers=%d]" % n
    for p, s in snow.items():
        F.setdefault(p, s)
    # ---- the cleared volume: the rectangle from the courtyard floor up, so no krummholz stands in the keep
    clear = (x0, pad + 1, z0, x1, pad + top_ry + 2 - CLEAR_TOP_CUT, z1)
    info = {"pad": pad, "top_ry": top_ry, "plinth_blocks": plinth, "clear": clear, "notes": notes, "lane_cells": len(lane_cells),
            "lane_rise": rise, "batter_edge_over": edge_over, "min_ground": min(g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))}
    return {"blocks": F, "special": S, "info": info}


def merge_boxes(cells):
    """[(x0, y0, z0, x1, y1, z1, state)]: a greedy cover of {(x, y, z): state} by boxes of one state."""
    by_state = {}
    for p, s in cells.items():
        by_state.setdefault(s, set()).add(p)
    out = []
    for s, pts in sorted(by_state.items()):
        left = set(pts)
        for (x, y, z) in sorted(pts, key=lambda p: (p[1], p[2], p[0])):
            if (x, y, z) not in left:
                continue
            xe = x
            while (xe + 1, y, z) in left:
                xe += 1
            ze = z
            while all((xx, y, ze + 1) in left for xx in range(x, xe + 1)):
                ze += 1
            ye = y
            while all((xx, ye + 1, zz) in left for xx in range(x, xe + 1) for zz in range(z, ze + 1)):
                ye += 1
            for xx in range(x, xe + 1):
                for yy in range(y, ye + 1):
                    for zz in range(z, ze + 1):
                        left.discard((xx, yy, zz))
            out.append((x, y, z, xe, ye, ze, s))
    return out


def commands(p):
    lines = ["# Generated by tools/frostpeak_keep.py from data/frostpeak_keep.json. Re-run to rebuild; do not edit.",
             "# Wardenhold: the snow-covered keep on Frostpeak Strand's southern lip. Run before the Habitat Blocks (R9FK, then R9E).",
             "# Writes no light, no spawn condition, no chest or bed; the only block entities are the log's wall signs."]
    cx0, cy0, cz0, cx1, cy1, cz1 = p["info"]["clear"]
    lines.append("fill %d %d %d %d %d %d minecraft:air" % (cx0, cy0, cz0, cx1, cy1, cz1))
    blocks = {k: v for k, v in p["blocks"].items() if k not in p["special"]}
    for (x0, y0, z0, x1, y1, z1, s) in merge_boxes(blocks):
        if (x0, y0, z0) == (x1, y1, z1):
            lines.append("setblock %d %d %d %s" % (x0, y0, z0, s))
        else:
            lines.append("fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, s))
    for (x, y, z), s in sorted(p["special"].items()):
        lines.append("setblock %d %d %d %s" % (x, y, z, s))
    lines = function_limits.ensure_loaded(lines)
    bad = function_limits.check_lines(lines, "%s/build" % FN)
    if bad:
        raise KeepError("the build has %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    return lines


def build(g):
    doc = load()
    p = plan(doc, g)
    files = {"pack.mcmeta": {"pack": {"pack_format": 48, "description":
                                      "Cobblers: Wardenhold, the snow-covered keep on Frostpeak Strand (generated by "
                                      "tools/frostpeak_keep.py from data/frostpeak_keep.json)"}},
             "data/%s/function/%s/build.mcfunction" % (NS, FN): commands(p)}
    return files, p


def hold_box(doc=None):
    doc = doc or load()
    x0, z0, x1, z1 = base_rect(doc)
    r = doc["dims"]["batter_reach"] + 6
    return x0 - r, z0 - r, x1 + r, z1 + r


def placement_steps():
    """[(kind, value)] for tools/reapply.py, step R9FK before R9E (the Habitat Blocks land in this pack's floors):
    hold the keep's chunks, build, release. Needs no heightmap: the box comes from the data file."""
    hold = "%d %d %d %d" % hold_box()
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (NS, FN)),
            ("cmd", "forceload remove " + hold)]


def habitat_cells(doc, pad):
    """The two Habitat Block positions this keep reserves: the hall's and the beacon chamber's (the floor cells under
    them are written by this pack, as the blocks' mimic)."""
    cx, cz = doc["site"]["centre"]
    d = doc["dims"]
    kc = d["keep_cv"]
    return {"hall": (cx + 3, pad, cz + kc - 4), "beacon": (cx - 1, pad + d["spire_floor"], cz + kc + 1)}


def probes(p, doc):
    out = []
    b = p["blocks"]
    pad = p["info"]["pad"]

    def first(pred, what, key=lambda k: k):
        for (x, y, z), blk in sorted(b.items(), key=lambda kv: key(kv[0])):
            if pred(blk):
                out.append({"what": what, "block": [x, y, z, blk.split("{")[0]], "expect": True})
                return

    top = max(((x, y, z) for (x, y, z), v in b.items() if v == doc["palette"]["rime"]), key=lambda k: (k[1], k))
    out.append({"what": "the spire's finial ice, the highest block", "block": list(top) + [doc["palette"]["rime"]], "expect": True})
    first(lambda v: v == doc["palette"]["roof"], "a snow-block cone roof", key=lambda k: (-k[1], k))
    first(lambda v: v == doc["palette"]["roof_trim"], "blue-ice roof trim")
    first(lambda v: v.startswith("minecraft:ladder"), "the spire's ladder", key=lambda k: (-k[1], k))
    first(lambda v: v == "minecraft:iron_bars", "the portcullis or the arcade's bars")
    first(lambda v: v.startswith("minecraft:stone_brick_stairs"), "a stair of the gate ramp or the keep", key=lambda k: (k[1], k))
    for k, s in sorted(p["special"].items())[:1]:
        out.append({"what": "a sign of the Wardens' log", "block": list(k) + [s.split("{")[0]], "expect": True})
    # the two Habitat Block cells are NOT probed here: once R9E places them they are cobblemon:habitat_block, and
    # tools/habitat_blocks.py verify owns them
    return out


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(content) + "\n" if isinstance(content, list) else json.dumps(content, indent=2) + "\n"
        f.write_text(body, encoding="utf-8", newline="\n")


def summary(p, doc):
    counts = {}
    for v in p["blocks"].values():
        k = v.split("[")[0].split("{")[0]
        counts[k] = counts.get(k, 0) + 1
    return {"info": p["info"], "habitat_cells": {k: list(v) for k, v in habitat_cells(doc, p["info"]["pad"]).items()},
            "blocks": dict(sorted(counts.items())), "probes": probes(p, doc)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("build", "plan", "probes"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    g = G.Ground(a.source_root)
    doc = load()
    if a.action == "probes":
        wp = ROOT / "data" / "world_probes.json"
        d = json.loads(wp.read_text(encoding="utf-8"))
        d["places"]["frostpeak_keep"] = probes(plan(doc, g), doc)
        wp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("wrote %d probes under places.frostpeak_keep in data/world_probes.json" % len(d["places"]["frostpeak_keep"]))
        return 0
    if a.action == "plan":
        p = plan(doc, g)
        s = summary(p, doc)
        s["steps"] = placement_steps()
        print(json.dumps(s, indent=1, default=list))
        return 0
    files, p = build(g)
    write(files, a.out)
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "report.json").write_text(json.dumps(summary(p, doc), indent=1, default=list) + "\n", encoding="utf-8")
    n = len(files["data/%s/function/%s/build.mcfunction" % (NS, FN)])
    print("wrote %s (%d lines in %s:%s/build; pad y%d, top y%d, %d plinth blocks, %d signs)"
          % (a.out, n, NS, FN, p["info"]["pad"], p["info"]["pad"] + p["info"]["top_ry"], p["info"]["plinth_blocks"], len(p["special"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
