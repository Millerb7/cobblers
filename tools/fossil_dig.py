#!/usr/bin/env python
"""The Scorchbone Dig on the scorched plateau's west mesa, from data/fossil_dig.json: a bone bed cut down in three
stepped trenches, the crew's camp on its west lip, and the fossil seams in the trench walls that silt back up.

The owner, 2026-10-06: "build a fossil dig at about (4183, 5623), its kind of empty". The obtainability sweep
(docs/research/OBTAINABILITY_SWEEP_2026-10-05.md, P0) found 14 of 15 Cobblemon fossils with no supply in this
pre-generated world: Cobblemon 1.8.0 puts them in archaeology loot tables (cobblemon:fossils/...) that only its own
worldgen structures carry. Nothing here is new machinery; every piece is an existing one:

  the dig       vanilla 1.21.1 blocks seated on tools/ground.py (the canonical heightmap, rounded), never a world. The
                upper level is cut one block below the lowest ground under it, each inner level two below the one round
                it. Every column of a level is dug to air from its floor up to its ground; the riser between two levels
                is written solid in two-block terracotta bands (fixed by absolute y) from the lower floor up, two deep;
                the outer wall gets a one-block skin of the same bands. A skeleton lies on the bed's floor.
  the seams     12 suspicious_gravel blocks in four faces, each at the foot of a riser (one above the lower floor),
                each with a LootTable naming one of Cobblemon's 15 rare fossil tables (one fossil, nothing else). The
                build arms them; the restore re-arms them.
  the restore   tools/mines.py's, the same shape: every `every_ticks` the pack looks for a player inside the dig's
                approach box; only then each face is checked, and restored when `period_ticks` have passed since its
                last restore, the four corners of its box are loaded, and no player and no Pokemon stands in its box
                grown by one. The restore writes only over #cobblers:fossil_dig_rearm (air, cave air, plain gravel):
                the face's wall cells back to their band, then each seam back to suspicious gravel with a fossil table
                picked by `random value 0..14`. An unbrushed seam is not touched and keeps its fossil.
  the camp      two ridge tents (white wool, open ends, a barrel and a hanging lantern inside), two sieves with spoil
                heaps and a wash tub, a sorting table, a finds board of wall signs facing the pit, an entrance sign and
                lanterns on fence posts. No light blocks, no chest, no bed, no water.
  the foreman   NOT in this pack: a conversation in data/dialogue.json (dlg_fossil_dig_foreman), seated by
                data/npc_seats.json (R17N, the Arrow Creeks farmer's way); seat_problems() checks that seat is the
                spot this plan leaves open, and the build fails if it is not.

The palette guard is tools/wayside_kit.py load_record: the record's blocks.ids may hold no spawn condition from
data/spawn_blocks.json that no data/spawn_block_policy.json entry scoped to fossil_dig allows, no chest and no bed,
and the plan refuses any block outside blocks.ids.

  python tools/fossil_dig.py build  [--source-root R] [--out DIR]   write the pack (fails on a siting problem)
  python tools/fossil_dig.py report [--source-root R]               numbers, coordinates, siting, steps; writes nothing

The re-application (tools/reapply.py, not edited here): placement_steps() is one step (proposed R9FD; it writes no
Habitat Block, so its order against R9E does not matter); the foreman needs no step of his own (R17N). The pack
also runs on its own (its load and tick tags): it must be installed with the other world packs.
The independent audit is someone else's: docs/world-building/FOSSIL_DIG.md says what it must check.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wayside_kit as K  # noqa: E402

DATA = ROOT / "data" / "fossil_dig.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_fossil_dig"
SCHEMA = "cobblers.fossil-dig/1"
PLACE = "fossil_dig"
NS = "cobblers"
FN = "fossil_dig"
F = "%s:%s" % (NS, FN)
AIR = "minecraft:air"
CLEAR_MARGIN = 3
CLEAR_OVER = 4
GRAVITY = {"minecraft:gravel", "minecraft:suspicious_gravel", "minecraft:sand", "minecraft:red_sand",
           "minecraft:suspicious_sand"}
SIDES = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class DigError(SystemExit):
    pass


def load(path=DATA):
    doc = K.load_record(path, SCHEMA, PLACE)
    lv = doc["pit"]["levels"]
    if [l["id"] for l in lv] != ["upper", "middle", "bed"]:
        raise DigError("pit.levels must be upper, middle, bed")
    for outer, inner in zip(lv, lv[1:]):
        ox0, oz0, ox1, oz1 = outer["rect"]
        ix0, iz0, ix1, iz1 = inner["rect"]
        if not (ox0 < ix0 and oz0 < iz0 and ix1 < ox1 and iz1 < oz1):
            raise DigError("level %s must lie strictly inside %s" % (inner["id"], outer["id"]))
        if inner["step"] < 2:
            raise DigError("level %s: a step under 2 leaves no wall below the upper floor for a seam" % inner["id"])
    tabs = doc["fossils"]["tables"]
    if len({t["item"] for t in tabs}) != 15 or len({t["loot_table"] for t in tabs}) != 15:
        raise DigError("fossils.tables must name 15 distinct fossils and 15 distinct tables")
    if not all(t["loot_table"].startswith("cobblemon:fossils/") for t in tabs):
        raise DigError("every fossil table must be one of Cobblemon's cobblemon:fossils/ tables")
    if doc["fossils"]["seam_block"] not in doc["blocks"]["ids"]:
        raise DigError("the seam block is not in blocks.ids")
    rs = doc["restore"]
    if rs["period_ticks"] < 12000:
        raise DigError("restore.period_ticks under 12,000 (600 s) is faster than the stone faces' own minimum")
    if any(b == doc["fossils"]["seam_block"] for b in rs["rearm"]):
        raise DigError("the rearm tag must not hold the seam block: an unbrushed seam would lose its fossil")
    if len({f["id"] for f in doc["faces"]}) != len(doc["faces"]):
        raise DigError("face ids must be unique")
    return doc


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan(K.Plan):
    """K.Plan with a collision guard: a block may replace air or a floor it was told it may, never another block."""

    def __init__(self, doc):
        super().__init__(doc["blocks"]["ids"], PLACE)
        self.floor_cells = set()

    def put(self, x, y, z, state, over_floor=False):
        cur = self.solid.get((x, y, z))
        if cur is not None and cur != AIR and cur != state and not (over_floor and (x, y, z) in self.floor_cells):
            raise DigError("(%d, %d, %d): %s would overwrite %s" % (x, y, z, state, cur))
        super().put(x, y, z, state)

    def hang(self, x, y, z, state):
        if self.solid.get((x, y, z), AIR) != AIR or (x, y, z) in self.hung:
            raise DigError("(%d, %d, %d): %s hangs where a block already is" % (x, y, z, state))
        super().hang(x, y, z, state)


def _in(rect, lx, lz):
    x0, z0, x1, z1 = rect
    return x0 <= lx <= x1 and z0 <= lz <= z1


def _cheb(rect, lx, lz):
    """Chebyshev distance from a cell outside `rect` to it (0 inside)."""
    x0, z0, x1, z1 = rect
    return max(x0 - lx, 0, lx - x1, z0 - lz, 0, lz - z1)


def strata(doc, y):
    s = doc["pit"]["strata"]
    return s[(y // doc["pit"]["strata_band"]) % len(s)]


def sign_text(lines):
    return ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])


def standing_sign(rotation, lines):
    return "minecraft:spruce_sign[rotation=%d,waterlogged=false]{front_text:{messages:[%s]}}" % (rotation, sign_text(lines))


def seam_state(doc, loot_table):
    return '%s{LootTable:"%s"}' % (doc["fossils"]["seam_block"], loot_table)


def plan(doc, g):
    """Everything the build writes, the seams, the faces' restore sets and the NPC's spot."""
    cx, cz = doc["site"]["centre"]
    p = Plan(doc)
    lv = {l["id"]: l for l in doc["pit"]["levels"]}
    order = [l["id"] for l in doc["pit"]["levels"]]
    R = {k: lv[k]["rect"] for k in order}
    ux0, uz0, ux1, uz1 = R["upper"]
    low = min(g(cx + a, cz + b) for a in range(ux0, ux1 + 1) for b in range(uz0, uz1 + 1))
    floors = {"upper": low - lv["upper"]["depth_below_lowest_ground"]}
    for a, b in zip(order, order[1:]):
        floors[b] = floors[a] - lv[b]["step"]
    rd = doc["pit"]["riser_depth"]
    fl = doc["pit"]["floor"]

    def level_of(lx, lz):
        out = None
        for k in order:
            if _in(R[k], lx, lz):
                out = k
        return out

    # 1. the outer skin: a ring outer_skin_depth wide round the upper level, from its floor up to the ground
    sk = doc["pit"]["outer_skin_depth"]
    for a in range(ux0 - sk, ux1 + sk + 1):
        for b in range(uz0 - sk, uz1 + sk + 1):
            if _in(R["upper"], a, b):
                continue
            x, z = cx + a, cz + b
            for y in range(floors["upper"], g(x, z) + 1):
                p.put(x, y, z, strata(doc, y))
    # 2. each level: its floor, the air over it up to the ground, the riser round the next level in
    for i, k in enumerate(order):
        inner = order[i + 1] if i + 1 < len(order) else None
        x0, z0, x1, z1 = R[k]
        for a in range(x0, x1 + 1):
            for b in range(z0, z1 + 1):
                if inner and _in(R[inner], a, b):
                    continue
                x, z = cx + a, cz + b
                F0 = floors[k]
                if inner is None:
                    p.put(x, F0 - 1, z, strata(doc, F0 - 1))
                if inner and _cheb(R[inner], a, b) <= rd:
                    for y in range(floors[inner], F0):
                        p.put(x, y, z, strata(doc, y))
                p.put(x, F0, z, K.pick(x, F0, z, fl))
                p.floor_cells.add((x, F0, z))
                for y in range(F0 + 1, max(g(x, z), F0) + 1):
                    p.put(x, y, z, AIR)
    # 3. the stairs: one run per level on its west side at stairs.lz, from the floor up to the level round it (the rim
    # for the upper level), ascending west
    st = doc["pit"]["stairs"]
    lz = st["lz"]
    for i, k in enumerate(order):
        x0 = R[k][0]
        top = g(cx + x0 - 1, cz + lz) if i == 0 else floors[order[i - 1]]
        h = top - floors[k]
        for j in range(1, h + 1):
            x, y, z = cx + x0 + (h - j), floors[k] + j, cz + lz
            for yy in range(floors[k] + 1, y):
                p.put(x, yy, z, strata(doc, yy))
            p.put(x, y, z, K.stair(st["kind"], "west"))
    # 4. the bone bed
    bb = doc["bone_bed"]
    F3 = floors["bed"]
    for a in range(bb["spine"]["lx"][0], bb["spine"]["lx"][1] + 1):
        p.put(cx + a, F3 + 1, cz + bb["spine"]["lz"], "minecraft:bone_block[axis=x]")
    for a in bb["ribs"]["lx"]:
        for b in bb["ribs"]["lz"]:
            p.put(cx + a, F3 + 1, cz + b, "minecraft:bone_block[axis=z]")
    for a, b, dy in bb["skull"]:
        p.put(cx + a, F3 + dy, cz + b, "minecraft:bone_block[axis=y]")
    for a, b in bb["tail_flush"]:
        p.put(cx + a, F3, cz + b, "minecraft:bone_block[axis=x]", over_floor=True)
    F2 = floors["middle"]
    stair_cols = {(k[0], k[2]) for k, s in p.solid.items() if s.startswith("minecraft:spruce_stairs")}
    for a in range(R["middle"][0], R["middle"][2] + 1):
        for b in range(R["middle"][1], R["middle"][3] + 1):
            x, z = cx + a, cz + b
            if _in(R["bed"], a, b) or (x, z) in stair_cols:
                continue
            if K.pick(x, F2, z, [True] + [False] * 8):
                p.put(x, F2, z, "minecraft:bone_block[axis=y]", over_floor=True)
    # 5. the seams and each face's restore set
    tabs = doc["fossils"]["tables"]
    faces = []
    n = 0
    for f in doc["faces"]:
        lower = f["level"]
        outer = order[order.index(lower) - 1]
        dx, dz = SIDES[f["side"]]
        y = floors[lower] + 1
        if y >= floors[outer]:
            raise DigError("face %s: its seams would stand at or over the %s floor" % (f["id"], outer))
        seams, support, backing, between = [], [], [], []
        for a, b in f["cells"]:
            if level_of(a, b) != outer or level_of(a - dx, b - dz) != lower:
                raise DigError("face %s: (%d, %d) is not a %s-level cell with the %s level on its %s side"
                               % (f["id"], a, b, outer, lower, f["side"]))
            x, z = cx + a, cz + b
            if p.solid.get((x, y, z)) != strata(doc, y):
                raise DigError("face %s: (%d, %d, %d) is not riser wall in the plan" % (f["id"], x, y, z))
            tb = tabs[n % len(tabs)]
            n += 1
            p._chk(seam_state(doc, tb["loot_table"]))
            p.solid[(x, y, z)] = seam_state(doc, tb["loot_table"])   # replaces the riser's band, on purpose
            seams.append({"at": (x, y, z), "built_with": tb["loot_table"]})
            support.append((x, y - 1, z))
            backing.append((x + dx, y, z + dz))
        cs = [(cx + a, cz + b) for a, b in f["cells"]]
        if dx == 0:
            zz = cs[0][1]
            if any(c[1] != zz for c in cs):
                raise DigError("face %s: a %s face's seams must share one z" % (f["id"], f["side"]))
            span = [(x, y, zz) for x in range(min(c[0] for c in cs), max(c[0] for c in cs) + 1)]
        else:
            xx = cs[0][0]
            if any(c[0] != xx for c in cs):
                raise DigError("face %s: a %s face's seams must share one x" % (f["id"], f["side"]))
            span = [(xx, y, z) for z in range(min(c[1] for c in cs), max(c[1] for c in cs) + 1)]
        seam_at = {s["at"] for s in seams}
        between = [c for c in span if c not in seam_at]
        wall = {}
        for c in support + backing + between:
            st_ = p.solid.get(c)
            if st_ != strata(doc, c[1]):
                raise DigError("face %s: restore cell %s is %s in the plan, not its band" % (f["id"], c, st_))
            wall[c] = st_
        cells = list(seam_at) + list(wall)
        xs, ys, zs = zip(*cells)
        faces.append({"face": f, "seams": seams, "wall": wall,
                      "bounds": (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))})
    # 6. lanterns on posts
    for post in doc["lanterns"]["posts"]:
        a, b = post["at"]
        x, z = cx + a, cz + b
        base = g(x, z) if post["on"] == "ground" else floors[post["on"]]
        for y in (base + 1, base + 2):
            p.put(x, y, z, K.fence("spruce"))
        p.hang(x, base + 3, z, K.lantern(False))
    # 7. the camp
    camp = doc["camp"]
    for t in camp["tents"]:
        x0, z0, x1, z1 = t["rect"]
        cols = [(cx + a, cz + b) for a in range(x0, x1 + 1) for b in range(z0, z1 + 1)]
        Gt = max(g(x, z) for x, z in cols)
        for x, z in cols:
            for y in range(g(x, z) + 1, Gt + 1):
                p.put(x, y, z, "minecraft:coarse_dirt")
        cv = camp["tent_canvas"]
        mid = (x0 + x1) // 2
        for b in range(z0, z1 + 1):
            z = cz + b
            p.put(cx + x0, Gt + 1, z, cv)
            p.put(cx + x1, Gt + 1, z, cv)
            p.put(cx + x0 + 1, Gt + 2, z, cv)
            p.put(cx + x1 - 1, Gt + 2, z, cv)
            p.put(cx + mid, Gt + 3, z, cv)
        p.put(cx + x0 + 1, Gt + 1, cz + z1 - 1, "minecraft:barrel[facing=up,open=false]")
        p.hang(cx + mid, Gt + 2, cz + (z0 + z1) // 2, K.lantern(True))

    def on_ground(a, b, state):
        x, z = cx + a, cz + b
        p.put(x, g(x, z) + 1, z, state)

    for a, b in camp["sieves"]:
        on_ground(a, b, "minecraft:scaffolding[bottom=false,distance=0,waterlogged=false]")
    for a, b in camp["spoil"]:
        on_ground(a, b, "minecraft:gravel")
    on_ground(*camp["tub"], "minecraft:cauldron")
    tab = camp["sorting_table"]
    Gs = max(g(cx + a, cz + b) for a, b in tab)
    for a, b in tab:
        p.put(cx + a, Gs + 1, cz + b, "minecraft:spruce_slab[type=top,waterlogged=false]")
    p.put(cx + tab[0][0], Gs + 2, cz + tab[0][1], "minecraft:decorated_pot[cracked=false,facing=east,waterlogged=false]")
    p.put(cx + tab[-1][0], Gs + 2, cz + tab[-1][1], "minecraft:skeleton_skull[rotation=4]")
    fb = camp["finds_board"]
    bcols = [(cx + fb["x"], cz + b) for b in range(fb["lz"][0], fb["lz"][1] + 1)]
    Gb = max(g(x, z) for x, z in bcols)
    for x, z in bcols:
        for y in range(g(x, z) + 1, Gb + 1):
            p.put(x, y, z, "minecraft:coarse_dirt")
        for y in (Gb + 1, Gb + 2):
            p.put(x, y, z, "minecraft:spruce_planks")
    sx = cx + fb["x"] + 1
    board = doc["signs"]["board"]
    for i, (x, z) in enumerate(bcols[:3]):
        p.hang(sx, Gb + 2, z, K.wall_sign("spruce", fb["faces"], board[i]))
    p.hang(sx, Gb + 1, bcols[1][1], K.wall_sign("spruce", fb["faces"], board[3]))
    ea, eb = camp["entrance_sign"]
    ex, ez = cx + ea, cz + eb
    p.hang(ex, g(ex, ez) + 1, ez, standing_sign(4, doc["signs"]["entrance"]))
    # 8. the foreman's spot
    na, nb = doc["npc"]["at_local"]
    nx, nz = cx + na, cz + nb
    npc = (nx, g(nx, nz) + 1, nz)
    blocks = p.blocks()
    if any(blocks.get((nx, npc[1] + d, nz), AIR) != AIR for d in (0, 1)):
        raise DigError("the foreman's spot %s is not two blocks of air" % (npc,))
    xs, ys, zs = zip(*blocks)
    return {"plan": p, "floors": floors, "lowest_ground": low, "faces": faces, "npc": npc, "blocks": blocks,
            "bounds": {"min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]}}


# ---------------------------------------------------------------------------------------------------------- the pack
def clear_box(pl, g):
    b = pl["bounds"]
    x0, z0 = b["min"][0] - CLEAR_MARGIN, b["min"][2] - CLEAR_MARGIN
    x1, z1 = b["max"][0] + CLEAR_MARGIN, b["max"][2] + CLEAR_MARGIN
    lo = min(g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    return (x0, lo + 1, z0, x1, b["max"][1] + CLEAR_OVER, z1)


def build_lines(doc, pl, g):
    p = pl["plan"]
    x0, y0, z0, x1, y1, z1 = clear_box(pl, g)
    out = ["# Generated by tools/fossil_dig.py from data/fossil_dig.json. Re-run to rebuild; do not edit.",
           "# The Scorchbone Dig: the stepped bone bed, its seams, the crew's camp, the lanterns.",
           "# 1. clear the plants, cacti and any tree over everything this writes, above the lowest ground"]
    for tag in ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable", "minecraft:cactus", "minecraft:dead_bush"):
        out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the cut, from the top down: the mesa's red sand falls if the block under it goes first")
    out += K.runs({k: s for k, s in p.solid.items() if s == AIR}, top_down=True)
    out.append("# 3. the walls, floors, stairs, bones and camp, bottom up (each seam armed with a fixed fossil)")
    out += K.runs({k: s for k, s in p.solid.items() if s != AIR})
    out.append("# 4. what hangs on it or stands on it, from the top: lanterns, signs")
    out += K.runs(p.hung, top_down=True)
    out.append("# 5. the restore may start: each face's clock staggered from now by its offset")
    out += ["scoreboard objectives add fd.t dummy", "scoreboard objectives add fd.last dummy",
            "execute store result score #now fd.t run time query gametime"]
    period = doc["restore"]["period_ticks"]
    for f in pl["faces"]:
        fid = f["face"]["id"]
        out += ["scoreboard players operation #%s fd.last = #now fd.t" % fid,
                "scoreboard players remove #%s fd.last %d" % (fid, period - int(f["face"]["offset_ticks"]))]
    out.append("scoreboard players set #built fd.t 1")
    return out


def _vol(b, grow=0):
    x0, y0, z0, x1, y1, z1 = b
    x0, y0, z0, x1, y1, z1 = x0 - grow, y0 - grow, z0 - grow, x1 + grow, y1 + grow, z1 + grow
    return (x0, y0, z0, x1, y1, z1), "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (x0, y0, z0, x1 - x0, y1 - y0, z1 - z0)


def approach_box(doc, pl):
    rs = doc["restore"]
    bs = [f["bounds"] for f in pl["faces"]]
    m = rs["approach_margin"]
    return (min(b[0] for b in bs) - m, min(b[1] for b in bs) - rs["approach_down"], min(b[2] for b in bs) - m,
            max(b[3] for b in bs) + m, max(b[4] for b in bs) + rs["approach_up"], max(b[5] for b in bs) + m)


def driver_files(doc, pl):
    rs = doc["restore"]
    tag = "#%s:%s" % (NS, rs["rearm_tag"])
    tabs = doc["fossils"]["tables"]
    fn = {}
    load_ = ["# the dig's restore state (tools/fossil_dig.py): scores live in the world's scoreboard, so a restore that",
             "# has happened is not repeated after a restart; the build sets each face's clock and #built",
             "scoreboard objectives add fd.t dummy", "scoreboard objectives add fd.last dummy",
             "scoreboard players set #period fd.t %d" % rs["period_ticks"]]
    for f in pl["faces"]:
        fid = f["face"]["id"]
        load_.append("execute unless score #%s fd.last matches -2147483648.. run scoreboard players set #%s fd.last 0"
                     % (fid, fid))
    fn["load"] = load_
    fn["tick"] = ["# one counter a tick; every %d ticks the work, which runs only where a player is near" % rs["every_ticks"],
                  "scoreboard players add #clock fd.t 1",
                  "execute if score #clock fd.t matches %d.. run function %s/drive" % (rs["every_ticks"], F)]
    _b, av = _vol(approach_box(doc, pl))
    fn["drive"] = ["scoreboard players set #clock fd.t 0",
                   "# nothing is restored before the build has run (it sets #built)",
                   "execute unless score #built fd.t matches 1 run return 0",
                   "execute store result score #now fd.t run time query gametime",
                   "execute if entity @a[%s] run function %s/site" % (av, F)]
    fn["site"] = ["# a player is within the dig's approach box: check each face"] + \
        ["function %s/faces/check_%s" % (F, f["face"]["id"]) for f in pl["faces"]]
    for f in pl["faces"]:
        fid = f["face"]["id"]
        (gx0, gy0, gz0, gx1, gy1, gz1), vol = _vol(f["bounds"], 1)
        fn["faces/check_%s" % fid] = [
            "# restore on approach: the period has passed, the face's four corners are loaded, and nobody and no",
            "# Pokemon stands in it or one block round it",
            "scoreboard players operation #d fd.t = #now fd.t",
            "scoreboard players operation #d fd.t -= #%s fd.last" % fid,
            "execute if score #d fd.t < #period fd.t run return 0",
            "execute unless loaded %d %d %d run return 0" % (gx0, gy0, gz0),
            "execute unless loaded %d %d %d run return 0" % (gx1, gy0, gz0),
            "execute unless loaded %d %d %d run return 0" % (gx0, gy0, gz1),
            "execute unless loaded %d %d %d run return 0" % (gx1, gy0, gz1),
            "execute if entity @a[%s] run return 0" % vol,
            "execute if entity @e[type=cobblemon:pokemon,%s] run return 0" % vol,
            "function %s/faces/restore_%s" % (F, fid)]
        restore = ["# chunks-loaded-by: %s/faces/check_%s (execute if loaded, the face's four corners)" % (F, fid),
                   "# the wall first (support under each seam, the cell behind it, the face between), only over %s" % tag]
        for (x, y, z), st in sorted(f["wall"].items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
            restore.append("fill %d %d %d %d %d %d %s replace %s" % (x, y, z, x, y, z, st, tag))
        restore.append("# then each seam, if it was brushed out or dug away")
        for k, s in enumerate(f["seams"]):
            restore.append("function %s/faces/seam_%s_%d" % (F, fid, k))
        restore.append("scoreboard players operation #%s fd.last = #now fd.t" % fid)
        fn["faces/restore_%s" % fid] = restore
        for k, s in enumerate(f["seams"]):
            x, y, z = s["at"]
            body = ["# chunks-loaded-by: %s/faces/check_%s (execute if loaded, the face's four corners)" % (F, fid),
                    "# an unbrushed seam keeps its fossil; a brushed one (gravel) or a dug one (air) is re-armed",
                    "execute unless block %d %d %d %s run return 0" % (x, y, z, tag),
                    "execute store result score #v fd.t run random value 0..%d" % (len(tabs) - 1)]
            for i, t in enumerate(tabs):
                body.append("execute if score #v fd.t matches %d run setblock %d %d %d %s"
                            % (i, x, y, z, seam_state(doc, t["loot_table"])))
            fn["faces/seam_%s_%d" % (fid, k)] = body
    return fn


def files(doc, g):
    import function_limits
    pl = plan(doc, g)
    out = {"pack.mcmeta": json.dumps({"pack": {"pack_format": K.PACK_FORMAT, "description":
                                               "Cobblers: the Scorchbone Dig on the scorched plateau (tools/fossil_dig.py)"}},
                                     indent=2) + "\n"}
    build = function_limits.ensure_loaded(build_lines(doc, pl, g))
    funcs = {"build": build}
    funcs.update(driver_files(doc, pl))
    for name, body in funcs.items():
        bad = function_limits.check_lines(body, name)
        if bad:
            raise DigError("function %s: %d command(s) the server would refuse: %s" % (name, len(bad), bad[:3]))
        out["data/%s/function/%s/%s.mcfunction" % (NS, FN, name)] = "\n".join(body) + "\n"
    out["data/%s/tags/block/%s.json" % (NS, doc["restore"]["rearm_tag"])] = \
        json.dumps({"values": doc["restore"]["rearm"]}, indent=2) + "\n"
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s/load" % F]}, indent=2) + "\n"
    out["data/minecraft/tags/function/tick.json"] = json.dumps({"values": ["%s/tick" % F]}, indent=2) + "\n"
    return out, pl


# ---------------------------------------------------------------------------------------------------------- siting
def _rect_dist(rect, x, z):
    x0, z0, x1, z1 = rect
    return math.hypot(max(x0 - x, 0, x - x1), max(z0 - z, 0, z - z1))


def _rects_overlap(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def siting(doc, pl, g):
    """(problems, nearest): the clear box (which holds every write) against the rules in site.keep_clear."""
    import southern_residents as SR
    kc = doc["site"]["keep_clear"]
    x0, _y0, z0, x1, _y1, z1 = clear_box(pl, g)
    rect = (x0, z0, x1, z1)
    probs, near = [], {}
    paths = K.route_paths()
    dp = min((_rect_dist(rect, x, z), name) for name, pts in paths.items() for x, z in pts)
    near["route_path"] = dp
    if dp[0] < kc["path_clearance"]:
        probs.append("%.0f blocks from route path %s (needs %d)" % (dp[0], dp[1], kc["path_clearance"]))
    # our own records in the shared files are skipped by id, as southern_residents skips its own: the foreman's seat
    own = {"residents": [{"records": {"conversation": "npc_%s_foreman" % PLACE}}]}
    pts = [pt for pt in SR.authored_points(own, own_file=str(DATA)) if pt[2] not in kc["excluded_files"]]
    da = min((_rect_dist(rect, a, b), f, (a, b)) for a, b, f in pts)
    near["authored"] = da
    if da[0] < kc["authored_clearance"]:
        probs.append("%.0f blocks from %s authored in data/%s (needs %d)" % (da[0], da[2], da[1], kc["authored_clearance"]))
    cols = {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    cp, cb = SR.corridor_check(PLACE, cols, kc["authored_clearance"])
    near["corridor"] = cb[:1] + cb[2:]
    probs += cp
    for k in kc["keep_out_boxes"]:
        if _rects_overlap(rect, k["box"]):
            probs.append("inside the keep-out box %s (%s)" % (k["box"], k["why"]))
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    m = kc["authored_clearance"]
    for t in towns:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if _rects_overlap(rect, (f["min_x"] - m, f["min_z"] - m, f["max_x"] + m, f["max_z"] + m)):
            probs.append("within %d of town %s's footprint" % (m, t["id"]))
    rz = json.loads((ROOT / "data" / "rift_zones.json").read_text(encoding="utf-8"))["zones"]
    for k, zone in rz.items():
        for bx in zone.get("boxes") or []:
            if _rects_overlap(rect, bx[:4]):
                probs.append("inside Rift zone %s" % k)
    hb = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
    dh = []
    for b in hb:
        if b.get("style") != "activated":
            continue
        d = _rect_dist(rect, b["position"]["x"], b["position"]["z"])
        dh.append((d, b["id"]))
        if d <= b["activated"]["spawn_range"]:
            probs.append("Habitat Block %s's spawn range reaches the dig (%.0f)" % (b["id"], d))
    near["habitat_block"] = min(dh) if dh else None
    return probs, near


# ---------------------------------------------------------------------------------------------------------- reapply
def hold_box(pl, g):
    x0, _y0, z0, x1, _y1, z1 = clear_box(pl, g)
    return (x0, z0, x1, z1)


def placement_steps(doc=None, g=None):
    """For tools/reapply.py (proposed R9FD): hold the chunks, build, release (R9DU's shape)."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    return K.placement_steps(hold_box(plan(doc, g), g), FN)


def seat_problems(doc, pl):
    """The foreman is seated by data/npc_seats.json (R17N, the Arrow Creeks farmer's way), not by a step of this
    tool: [] when that seat is this plan's spot, names this conversation and records the ground under it."""
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    conv = next((c for c in dl["conversations"] if c["id"] == doc["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        return ["%s is not a conversation with an NPC in data/dialogue.json" % doc["npc"]["conversation"]]
    seats = json.loads((ROOT / "data" / "npc_seats.json").read_text(encoding="utf-8"))["seats"]
    seat = next((s for s in seats if s["id"] == conv["npc_id"]), None)
    if seat is None:
        return ["%s has no seat in data/npc_seats.json" % conv["npc_id"]]
    probs = []
    if tuple(seat["at"]) != tuple(pl["npc"]):
        probs.append("%s is seated at %s; the plan leaves %s open" % (conv["npc_id"], seat["at"], pl["npc"]))
    if seat["conversation"] != conv["id"] or seat["ground"]["y"] != pl["npc"][1] - 1:
        probs.append("%s: the seat's conversation or recorded ground disagrees with the plan" % conv["npc_id"])
    return probs


def report(doc, pl, g):
    b = pl["blocks"]
    probs, near = siting(doc, pl, g)
    probs = probs + seat_problems(doc, pl)
    lines = ["site %s: lowest ground under the upper level y%d; floors %s"
             % (doc["site"]["centre"], pl["lowest_ground"], json.dumps(pl["floors"])),
             "blocks written: %d (air %d); bounds %s; clear box %s"
             % (len(b), sum(1 for s in b.values() if s == AIR), json.dumps(pl["bounds"]), clear_box(pl, g)),
             "foreman stands at %s" % (pl["npc"],),
             "approach box %s" % (approach_box(doc, pl),)]
    for f in pl["faces"]:
        lines.append("face %s (offset %d): seams %s; box %s; %d wall cells"
                     % (f["face"]["id"], f["face"]["offset_ticks"], [s["at"] for s in f["seams"]], f["bounds"], len(f["wall"])))
    lines.append("siting and seat: %s; nearest %s" % ("clear" if not probs else "PROBLEMS " + "; ".join(probs),
                                              json.dumps(near, default=str)))
    lines.append("steps: %s" % json.dumps([list(s) for s in K.placement_steps(hold_box(pl, g), FN)]))
    return lines, probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "report"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, pl = files(doc, g)
    lines, probs = report(doc, pl, g)
    if a.cmd == "report":
        print("\n".join(lines))
        return 1 if probs else 0
    if probs:
        raise DigError("fossil_dig: siting problems, nothing written: %s" % "; ".join(probs))
    K.write(out_files, a.out)
    n = sum(1 for l in out_files["data/%s/function/%s/build.mcfunction" % (NS, FN)].splitlines()
            if l and not l.startswith("#"))
    print("fossil_dig: %d files -> %s (build: %d commands)" % (len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
