#!/usr/bin/env python
"""RESOURCES: piles of ore by band (pass 2, unit RESOURCES2, 2026-10-10).

The owner, playing pass 2 on staging: "The resource rooms should have piles of ore, based on location in game as well:
early game don't give them great stuff, but late in game a mega stone or two, diamonds, maybe a netherite." And: ore in
the dungeon's walls counts as a resource too. Mechanism rung: **datapack plus generator** (CLAUDE.md principle 6): a
dress op, merged room hooks and two loot tables are enough; no mod, scripting layer or companion process.

WHAT A `resources` ROOM HOLDS NOW (data/dungeon_resources.json is the table; docs/mechanics/DUNGEON_ROOMS.md section 10):
  * the SEAM (tools/dungeon_kinds.py kind_resources): the 24-block face the greed ladder counts, its mix per band now
    authored in the table (`seam`), equal to tools/economy_sim.py's assumption;
  * HEAPS: free-standing mounds of the theme's rubble on the room's real outline, 2-3 high, stepped by one block so a
    player can climb them, their TOP cell of every column a candidate for ore (the crest of the tallest heaps takes the
    rare ores);
  * VEINS: ore in the rock of a shaped room's walls (a cavern, an L, a broken hall): the exposed layer of rock only,
    every other neighbour of the cell solid, so breaking one opens a pocket in the room and nothing else;
  * the CACHE (band 5 and 6): a chest at a heap's foot with a loot table holding the raw Mega Showdown stone.
  The room's GEOMETRY never changes with the band: the same heaps and veins every run. The slot's reset (as the entrant,
  `dg.band`) sets which candidate cells are ore and which ore, the rest of them rubble, and puts the cache back for the
  band that holds one. The shell writes band 1's.

WHY EACH CHOICE IS THE LOWEST RUNG: the pick (an adventure-mode can_break list) already breaks only the blocks the room
names (R2, EXP-074), the seam already refills at reset and counts blocks gone by `unless block`; the cache is the
vault's chest and loot table (tools/dungeon_puzzles.py). All this module adds is more cells and a table.

WHAT THE PICK MAY BREAK (R.pick_blocks gains `pick_extra`): the seam's blocks and every ore of the table for this theme's
family, nothing else. tools/dungeon_rooms.py walk_problems counts the cells in the built grid and expects exactly the
seam, the cracked faces and `meta.breakable_extra` (the band-1 ore cells this module wrote). The rift pick stays an iron
pickaxe: every ore of the table is mined by an iron tool, and the two things that are not (ancient debris needs a diamond
tool, vanilla tag minecraft:needs_diamond_tool, ASSUMED; the Mega stone's crystal likewise, read from the Mega Showdown jar)
are FOUND in the cache chest, not mined.

THE BUDGET (`budget()`, run by tests/test_dungeon_resources.py): per band, for the shortest of the dungeons, the bank
value of the seam and the piles is at most `dollar_factor` x the gathering tier open at that band's badges x the run's
required hours; every rare ore at most `item_rate_factor` x the bank's rate x those hours; the cache's raw stones at most
the farm's rate x those hours.

UNPROVEN IN GAME: that a chest placed with a LootTable gives its stone when opened in adventure mode in the pocket (the
vault's own assumption); the mining times;
that stepped heaps climb as the walk check says.

  python tools/dungeon_resources.py            # the table, the budget verdicts, the room plans; exit 1 on a problem
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_grid as G  # noqa: E402
import dungeon_rooms as R  # noqa: E402
from dungeon_rooms import fill, setb  # noqa: E402

DATA_PATH = ROOT / "data" / "dungeon_resources.json"
OBJ = "dg.rs"
BANDS = (1, 2, 3, 4, 5, 6)
FACE = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
YAW = {"south": 0, "west": 90, "east": -90, "north": 180}       # a stand cell looking at the chest: the direction it faces
RARE_ORDER = ("diamond", "emerald", "gold")       # the crest takes these first: dearest first
OPPOSITE = {"north": "south", "south": "north", "west": "east", "east": "west"}
GREED_CALL = True       # a pile or vein block gone calls greed/take once, as a seam block does (data may override: calls_greed)

_DATA = {}


class ResError(ValueError):
    pass


def data(path=DATA_PATH):
    key = str(path)
    if key not in _DATA:
        _DATA[key] = json.loads(Path(path).read_text(encoding="utf-8"))
    return _DATA[key]


# ------------------------------------------------------------------------------------------------- the table


def resources():
    return data()["resources"]


def avg_drop(res):
    lo, hi = resources()[res]["drop"]
    return (lo + hi) / 2.0


def table_row(band):
    """{resource: blocks} the heaps and veins hold at `band`."""
    out = {}
    for res, e in data()["table"].items():
        if e["min_band"] <= band <= e["max_band"]:
            n = int(e["counts"].get(str(band), 0))
            if n:
                out[res] = n
    return out


def seam_row(band):
    return {k: int(v) for k, v in data()["seam"][str(band)].items()}


def row_total(row):
    return sum(row.values())


def table_resources():
    return [r for r in resources() if any(r in table_row(b) or r in seam_row(b) for b in BANDS)]


def theme_cfg(d):
    return data()["themes"].get(d.get("theme"))


def family_block(cfg, res):
    return resources()[res]["blocks"][cfg["family"]]


def seam_counts(row, n):
    """`row` (a mix summing to 24) scaled to n blocks by largest remainder; deterministic."""
    tot = row_total(row)
    if n == tot:
        return dict(row)
    raw = {k: v * n / tot for k, v in row.items()}
    out = {k: int(math.floor(v)) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: (-(raw[k] - out[k]), k))[: n - sum(out.values())]:
        out[k] += 1
    return out


def seam_uses_table(theme_id):
    cfg = data()["themes"].get(theme_id)
    return bool(cfg) and cfg.get("seam", "table") == "table"


def seam_face(theme_id, band, n):
    """The block of each of the seam's n cells at `band`, from the authored mix; the same cell order as the old round robin
    (j * 5 mod n) so a face reads mixed, not in bands of one ore."""
    cfg = data()["themes"][theme_id]
    counts = seam_counts(seam_row(band), n)
    expanded = [k for k in sorted(counts) for _ in range(counts[k])]
    return [family_block(cfg, expanded[(j * 5) % n]) for j in range(n)]


def pile_blocks(d):
    """Every ore block this theme's piles can hold, in table order (the pick's list gains them)."""
    cfg = theme_cfg(d)
    if cfg is None:
        return []
    out = []
    for res in resources():
        if any(res in table_row(b) for b in BANDS):
            blk = family_block(cfg, res)
            if blk not in out:
                out.append(blk)
    return out


def has_resources_rooms(d):
    return R.has_rooms(d) and any(r["kind"] == "resources" for r in R.all_records(d))


def pick_extra(d, themes=None):
    """The blocks beyond the seam and the secrets that this dungeon's rift pick may break (R.pick_blocks calls this)."""
    return pile_blocks(d) if has_resources_rooms(d) else []


# ------------------------------------------------------------------------------------------------- geometry


def _rubble(rg, cfg):
    blocks = cfg["rubble"]
    total = sum(w for _b, w in blocks)
    t = rg.random() * total
    for b, w in blocks:
        t -= w
        if t <= 0:
            return b
    return blocks[-1][0]


def heap_profile(H):
    """[(dx, dz, h)]: a stepped dome, height H at the centre and one less per block out (euclid, floored): neighbours differ by at most one."""
    out = []
    for dx in range(-H, H + 1):
        for dz in range(-H, H + 1):
            h = H - int(math.floor(math.hypot(dx, dz)))
            if h >= 1:
                out.append((dx, dz, h))
    return out


def _solid_floor(ctx, x, y, z):
    return ctx.grid.inside(x, y - 1, z) and G.classify(ctx.grid.block_at(x, y - 1, z)) == G.SOLID


COVER = {"minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern", "minecraft:large_fern", "minecraft:moss_carpet",
         "minecraft:glow_lichen", "minecraft:poppy", "minecraft:dandelion", "minecraft:blue_orchid", "minecraft:azure_bluet",
         "minecraft:red_tulip", "minecraft:oxeye_daisy", "minecraft:lily_of_the_valley", "minecraft:pink_petals",
         "minecraft:brown_mushroom", "minecraft:red_mushroom", "minecraft:small_dripleaf", "minecraft:vine"}
# what a heap may be built over (the jungle's ground cover): plants with no function, cleared above the heap


def _clear(ctx, x, y, z):
    b = G.base(ctx.grid.block_at(x, y, z))
    return b in G.AIR or b in COVER


def plan_heaps(ctx, cfg, target, rg):
    """Place heaps until the candidate cells reach `target` or the room has no more space. A heap whose footprint meets a
    wall is clipped by it and becomes a bank against the wall (at least 60% of its cells must stand). Returns (heaps, cands,
    foot): the heaps, their ore candidates and every column a heap occupies."""
    r = ctx.room
    geo = data()["geometry"]
    hmin, hmax = cfg["heaps"]["height"]
    head, pad = int(geo["headroom"]), int(geo["pad"])
    cols = [(x, z) for x in range(r["ix0"], r["ix1"] + 1) for z in range(r["iz0"], r["iz1"] + 1) if ctx.open(x, z)]
    rg.shuffle(cols)
    near = [c for c in cols if any(not ctx.open(c[0] + a, c[1] + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    nearset = set(near)
    far = [c for c in cols if c not in nearset]
    order = []
    while near or far:          # banks and free heaps alternate, so a room has both
        if near:
            order.append(near.pop())
        if far:
            order.append(far.pop())
    heaps, cands, foot, taken = [], [], set(), set()
    top = r["ceil_y"] - 2
    for (cx, cz) in order:
        if len(heaps) >= cfg["heaps"]["max"]:
            break
        if len(cands) >= target and len(heaps) >= cfg["heaps"]["min"]:
            break
        f0 = ctx.floor(cx, cz)
        if f0 is None:
            continue
        H = rg.randint(hmin, hmax)
        prof = heap_profile(H)
        ok = True
        cells = []
        for dx, dz, h in prof:
            x, z = cx + dx, cz + dz
            if not ctx.open(x, z):
                continue            # the wall clips the heap: a bank
            f = ctx.floor(x, z)
            if f is None or abs(f - f0) > 1 or ctx.reserved(x, z) or (x, z) in taken or not _solid_floor(ctx, x, f, z) \
                    or (x, f, z) not in ctx.res_reach:
                ok = False
                break
            if f + h + head - 1 > top or not all(_clear(ctx, x, y, z) for y in range(f, f + h + head)):
                ok = False
                break
            cells.append((x, z, f, h))
        if not ok or len(cells) < 0.6 * len(prof):
            continue
        hp = {"centre": (cx, cz), "H": H, "floor": f0, "cells": []}
        for x, z, f, h in cells:
            blk = _rubble(rg, cfg)
            ctx.add(fill((x, f, z, x, f + h - 1, z), blk))
            ctx.add(fill((x, f + h, z, x, f + h + head - 1, z), "minecraft:air"))
            hp["cells"].append((x, z, f, h))
            foot.add((x, z))
            cands.append({"pos": (x, f + h - 1, z), "host": blk, "kind": "heap",
                          "prom": (h - 1) * 2.0 + (1.0 if (x, z) == (cx, cz) else 0.0) + rg.random() * 0.5})
            for a in range(-pad, pad + 1):
                for b2 in range(-pad, pad + 1):
                    taken.add((x + a, z + b2))
        heaps.append(hp)
    return heaps, cands, foot


def backed(ctx, x, y, z, dx, dz, wall):
    """May the rock cell (x, y, z), exposed to the air cell (x - dx, z - dz), hold ore? Only the room's own rock: inside the
    interior box, the exposed layer, the five other neighbours solid and inside the grid (so breaking it opens a pocket in
    this room and not the hull, a chamber, a door or the void)."""
    r = ctx.room
    if not (r["ix0"] <= x <= r["ix1"] and r["iz0"] <= z <= r["iz1"]):
        return False
    if y < r["y_lo"] or y > r["ceil_y"] - 3:
        return False
    g = ctx.grid
    if not g.inside(x, y, z) or G.base(g.block_at(x, y, z)) != wall:
        return False
    if not ctx.air(x - dx, y, z - dz):
        return False
    for a, b, c in ((dx, 0, dz), (0, 1, 0), (0, -1, 0), (dz, 0, dx), (-dz, 0, -dx)):
        nx, ny, nz = x + a, y + b, z + c
        if not g.inside(nx, ny, nz) or G.classify(g.block_at(nx, ny, nz)) != G.SOLID:
            return False
    return True


def plan_veins(ctx, cfg, cap, rg, foot):
    """Ore cells in the rock of a shaped room's walls: runs of up to `vein_max_run` along a wall, one or two rows."""
    if not cfg.get("veins"):
        return []
    o = ctx.room.get("outline")
    if o is None or o.is_box():
        return []
    wall = G.base(ctx.theme["hull"]["wall"])
    run_max = int(data()["geometry"]["vein_max_run"])
    faces = ctx.walls()
    rg.shuffle(faces)
    used, out = set(), []
    for (x, y, z, face) in faces:
        if len(out) >= cap:
            break
        dx, dz = FACE[face]
        along = (1, 0) if dz else (0, 1)
        row = y + rg.randint(0, 1)
        run = []
        # grow the run along the face from the seed, both ways, while the rock stays legal
        seq = [0]
        for k in range(1, run_max):
            seq.append(k if (k % 2) else -k)
        for k in seq:
            ox, oz = x + along[0] * k, z + along[1] * k
            rx, rz = ox + dx, oz + dz
            if (rx, row, rz) in used or ctx.reserved(rx, rz) or (rx, rz) in foot:
                continue
            if not ctx.open(ox, oz) or ctx.floor(ox, oz) is None or abs(ctx.floor(ox, oz) - y) > 0 or (ox, y, oz) not in ctx.res_reach:
                continue
            if backed(ctx, rx, row, rz, dx, dz, wall):
                run.append((rx, row, rz))
        for c in run[:max(0, cap - len(out))]:
            used.add(c)
            out.append({"pos": c, "host": ctx.grid.block_at(*c), "kind": "vein", "prom": 0.0})
    return out


def plan_cache(ctx, heaps, foot, rg):
    """A chest at the foot of the biggest heap: (chest cell, facing, stand cell). The stand cell is open, level, free."""
    if not heaps:
        return None
    big = max(heaps, key=lambda h: (h["H"], len(h["cells"])))
    cx, cz = big["centre"]
    ring = [(cx + a, cz + b) for a in range(-big["H"] - 2, big["H"] + 3) for b in range(-big["H"] - 2, big["H"] + 3)]
    ring.sort(key=lambda p: (abs(p[0] - cx) + abs(p[1] - cz), p))
    for (x, z) in ring:
        if (x, z) in foot or not ctx.open(x, z) or ctx.reserved(x, z):
            continue
        f = ctx.floor(x, z)
        if f is None or not _solid_floor(ctx, x, f, z) or not all(ctx.air(x, y, z) for y in range(f, f + 3)) \
                or (x, f, z) not in ctx.res_reach:
            continue
        for facing, (dx, dz) in sorted(FACE.items()):
            sx, sz = x + dx, z + dz
            if (sx, sz) in foot or not ctx.open(sx, sz) or ctx.floor(sx, sz) != f or (sx, f, sz) not in ctx.res_reach:
                continue
            if not all(ctx.air(sx, y, sz) for y in range(f, f + 3)):
                continue
            # not in the way of the kit's anchors: the stand cell may be on the trail, the chest may not
            return {"chest": (x, f, z), "facing": facing, "stand": (sx, f, sz)}
    return None


# ------------------------------------------------------------------------------------------------- the dress op


def assign(cands, row, rg):
    """{pos: resource} for one band: the rare ores on the crests (highest `prom`, heaps first), the bulk at random."""
    rare = sorted([k for k, n in row.items() if resources()[k]["rare"] for _ in range(n)], key=lambda k: (RARE_ORDER.index(k), k))
    order = sorted(cands, key=lambda c: (-c["prom"], c["pos"]))
    out = {}
    crest = [c for c in order if c["kind"] == "heap"]
    for res, c in zip(rare, crest):
        out[c["pos"]] = res
    bulk = [k for k, n in sorted(row.items()) if not resources()[k]["rare"] for _ in range(n)]
    rg.shuffle(bulk)
    rest = [c for c in order if c["pos"] not in out]
    rg.shuffle(rest)
    for res, c in zip(bulk, rest):
        out[c["pos"]] = res
    if len(out) != row_total(row):
        raise ResError("only %d of %d ores found a cell (%d candidates)" % (len(out), row_total(row), len(cands)))
    return out


def rg_for(d, room, salt):
    return R.rng(d, room, salt)


def cache_items(band):
    """[(key, item, count)] the cache chest holds at `band` (nothing under the cache's min_band)."""
    c = data()["cache"]
    if band < int(c["min_band"]):
        return []
    return [(k, e["item"], int(e["count_by_band"][str(band)])) for k, e in c["items"].items() if str(band) in e["count_by_band"]]


def cache_count(band):
    """How many different stacks the cache holds at `band`: 0 means no chest at that band."""
    return len(cache_items(band))


def cache_table_id(band):
    return "cobblers:%s/b%d" % (data()["cache"]["loot_dir"], band)


def holder(slot, room, tag):
    return R.state_holder(slot, room) + tag


def dress_deposits(ctx, spec):
    r, b, d = ctx.room, ctx.built, ctx.d
    if r["kind"] != "resources":
        return
    cfg = theme_cfg(d)
    if cfg is None:
        return
    geo = data()["geometry"]
    need = max(row_total(table_row(band)) for band in BANDS)
    target = int(math.ceil(need * float(geo["capacity_factor"])))
    rg = R.rng(d, r, "deposits")
    # where a player can stand (the walk check's own rules), so no ore or chest is placed in a pocket nobody reaches
    g = ctx.grid
    x0, y0, z0 = g.box[:3]
    sx0, sy0, sz0 = R.room_start(r)
    ctx.res_reach = {(a + x0, b2 + y0, c + z0) for (a, b2, c) in G.walk(g, [g.local(sx0, sy0, sz0)], jumps=False, cls=g.cls())}
    heaps, cands, foot = plan_heaps(ctx, cfg, target, rg)
    veins = plan_veins(ctx, cfg, max(target // 2, target - len(cands)), rg, foot)
    cands += veins
    if len(cands) < need:
        raise R.RoomError("%s room %s: its heaps and veins give %d ore cells and the table needs %d at its richest band (the "
                          "room is too small or too crowded)" % (d["id"], r["id"], len(cands), need))
    cache = plan_cache(ctx, heaps, foot, rg) if any(cache_count(band) for band in BANDS) else None
    if cache is None and any(cache_count(band) for band in BANDS):
        raise R.RoomError("%s room %s: no site for the cache chest" % (d["id"], r["id"]))
    cands.sort(key=lambda c: (c["pos"][0], c["pos"][1], c["pos"][2]))
    by_band = {}
    for band in BANDS:
        by_band[band] = assign(cands, table_row(band), R.rng(d, r, "deposits:band%d" % band))
    # the ground the heaps and the cache take is kept from later dressing
    for hp in heaps:
        for (x, z, _f, _h) in hp["cells"]:
            for a in range(-1, 2):
                for c in range(-1, 2):
                    ctx.keep.add((x + a, z + c))
    if cache is not None:
        for a in range(-1, 2):
            for c in range(-1, 2):
                ctx.keep.add((cache["chest"][0] + a, cache["chest"][2] + c))
                ctx.keep.add((cache["stand"][0] + a, cache["stand"][2] + c))
    fam = cfg["family"]

    def block_at_band(c, band):
        res = by_band[band].get(c["pos"])
        return resources()[res]["blocks"][fam] if res else c["host"]

    # the shell: band 1's ore (the rest is rubble already)
    n1 = 0
    for c in cands:
        blk = block_at_band(c, 1)
        if blk != c["host"]:
            n1 += 1
            ctx.add(setb(c["pos"], blk))
    # the room's hooks
    reset = ["# the piles (RESOURCES2): every candidate cell back to its rubble or ore, band 1's first, then each higher band's difference"]
    for c in cands:
        reset.append("setblock %d %d %d %s" % (*c["pos"], block_at_band(c, 1)))
    for band in BANDS[1:]:
        for c in cands:
            blk = block_at_band(c, band)
            if blk != block_at_band(c, band - 1):
                reset.append("execute if score @s dg.band matches %d.. run setblock %d %d %d %s" % (band, *c["pos"], blk))
    for j, c in enumerate(cands):
        reset.append("scoreboard players set %s %s 0" % (holder(ctx.slot, r, "o%d" % j), OBJ))
    for band in BANDS:
        for j, c in enumerate(cands):
            if c["pos"] in by_band[band]:
                reset.append("execute if score @s dg.band matches %d run scoreboard players set %s %s 1"
                             % (band, holder(ctx.slot, r, "o%d" % j), OBJ))
    tick = []
    call = bool(data().get("calls_greed", GREED_CALL))
    for j, c in enumerate(cands):
        hj = holder(ctx.slot, r, "o%d" % j)
        x, y, z = c["pos"]
        tick.append("execute if score %s %s matches 1 if block %d %d %d minecraft:air run scoreboard players set %s %s 2" % (hj, OBJ, x, y, z, hj, OBJ))
        if call:
            tick.append("execute if score %s %s matches 2 run function %s" % (hj, OBJ, R.F("greed/take")))
        tick.append("execute if score %s %s matches 2 run scoreboard players set %s %s 3" % (hj, OBJ, hj, OBJ))
    meta = {"cands": [{"pos": list(c["pos"]), "host": c["host"], "kind": c["kind"]} for c in cands],
            "by_band": {str(band): {"%d,%d,%d" % c["pos"]: by_band[band].get(c["pos"]) for c in cands if c["pos"] in by_band[band]}
                        for band in BANDS},
            "heaps": [{"centre": list(h["centre"]), "H": h["H"], "cells": len(h["cells"])} for h in heaps],
            "foot": sorted(list(p) for p in foot), "veins": len(veins), "band1_ore": n1}
    if cache is not None:
        x, y, z = cache["chest"]
        sx, sy, sz = cache["stand"]
        hk = holder(ctx.slot, r, "k")
        reset.append("# the cache: from air, with the entrant's band's loot table (a setblock onto the same chest state fails and loads nothing)")
        reset.append("setblock %d %d %d minecraft:air" % (x, y, z))
        for band in BANDS:
            if cache_count(band):
                reset.append("execute if score @s dg.band matches %d run setblock %d %d %d %s[facing=%s]{LootTable:\"%s\"}"
                             % (band, x, y, z, data()["cache"]["container"], cache["facing"], cache_table_id(band)))
        reset.append("scoreboard players set %s %s 0" % (hk, OBJ))
        reset.append("execute if score @s dg.band matches %d.. run scoreboard players set %s %s 1"
                     % (int(data()["cache"]["min_band"]), hk, OBJ))
        tick.append("execute if score %s %s matches 1 unless data block %d %d %d LootTable run scoreboard players set %s %s 2" % (hk, OBJ, x, y, z, hk, OBJ))
        if call:
            tick.append("execute if score %s %s matches 2 run function %s" % (hk, OBJ, R.F("greed/take")))
        tick.append("execute if score %s %s matches 2 run scoreboard players set %s %s 3" % (hk, OBJ, hk, OBJ))
        b.anchors["cache"] = [[sx, sy, sz, YAW[OPPOSITE[cache["facing"]]]]]
        meta["cache"] = {"chest": [x, y, z], "facing": cache["facing"], "stand": [sx, sy, sz], "holder": hk}
    b.functions["tick"] = b.functions.get("tick", []) + tick
    b.functions["reset"] = b.functions.get("reset", []) + reset
    b.meta["deposits"] = meta
    b.meta["breakable_extra"] = n1


# ------------------------------------------------------------------------------------------------- the pack


def loot_table(band):
    pools = []
    for _k, item, n in cache_items(band):
        pools.append({"rolls": 1, "entries": [{"type": "minecraft:item", "name": item,
                                               "functions": [{"function": "minecraft:set_count", "count": n}]}]})
    return {"type": "minecraft:chest", "pools": pools}


def pack_files(doc):
    """{path: text}: the cache's loot table for each band that holds one, when any rooms dungeon has a resources room."""
    import dungeon as DG
    if not any(has_resources_rooms(d) and theme_cfg(d) is not None for d in DG.dungeons(doc)):
        return {}
    out = {}
    for band in BANDS:
        if cache_count(band):
            tid = cache_table_id(band).split(":", 1)[1]
            out["data/cobblers/loot_table/%s.json" % tid] = json.dumps(loot_table(band), indent=2) + "\n"
    return out


# ------------------------------------------------------------------------------------------------- the budget


def required_hours(doc):
    """{band: hours} of the shortest rooms dungeon: its clock for the band over the slack factor."""
    slack = float(doc["engine"]["clock"]["slack_factor"])
    out = {}
    for band in BANDS:
        hs = []
        for d in doc["dungeons"]:
            if not R.has_rooms(d):
                continue
            c = (d.get("clock_s_by_band") or {}).get(str(band))
            if c:
                hs.append(c / slack / 3600.0)
        if hs:
            out[band] = min(hs)
    return out


def band_badges(doc, band):
    """The fewest badges a band's lowest cap implies (tools/economy_sim.py CAP_BY_BADGES)."""
    import economy_sim as E
    lo = [b for b in doc["engine"]["bands"] if b["band"] == band][0]["caps"][0]
    return max(k for k, v in E.CAP_BY_BADGES.items() if v <= lo)


def budget(doc=None):
    """[(band, verdict, detail)] where verdict is "ok" or "OVER". See the module docstring for the three rules."""
    import dungeon as DG
    import economy_sim as E
    doc = doc if doc is not None else DG.load()
    w = E.World(E.load_docs())
    cfg = data()["budget"]
    hours = required_hours(doc)
    out = []
    for band in BANDS:
        h = hours.get(band)
        if h is None:
            continue
        badges = band_badges(doc, band)
        tier = max(v for n, v in w.tier_hour.items() if w.tier_opens_badges[n] <= badges)
        limit = cfg["dollar_factor"] * tier * h
        blocks = {}
        for src in (seam_row(band), table_row(band)):
            for k, n in src.items():
                blocks[k] = blocks.get(k, 0) + n
        dollars = 0.0
        for k, n in blocks.items():
            item = resources()[k]["item"]
            dollars += n * avg_drop(k) * w.price.get(item, 0)
        for k, item, n in cache_items(band):
            pi = data()["cache"]["items"][k].get("price_item")
            dollars += n * (w.price.get(pi, 0) if pi else 0)
        out.append((band, "ok" if dollars <= limit + 1e-9 else "OVER",
                    "value $%.0f of $%.0f (tier $%.0f/h x %.3f h x %.2f; %d badges)" % (dollars, limit, tier, h, cfg["dollar_factor"], badges)))
        for k, n in sorted(blocks.items()):
            e = resources()[k]
            item = e["item"]
            rate = w.rate.get(item)
            if not e["rare"] or not rate:
                continue
            cap = int(math.floor(cfg["item_rate_factor"] * rate * h))
            items = n * avg_drop(k)
            out.append((band, "ok" if items <= cap else "OVER",
                        "%s: %d blocks (%.0f items) of at most %d (%.1f x bank rate %.0f/h x %.3f h)"
                        % (k, n, items, cap, cfg["item_rate_factor"], rate, h)))
        for k, item, n in cache_items(band):
            pi = data()["cache"]["items"][k].get("price_item")
            if k == "mega":
                cap = int(math.floor(cfg["farm_raw_per_hour"] * h))
                out.append((band, "ok" if n <= cap else "OVER",
                            "cache: %d raw mega stone(s) of at most %d (farm %.1f/h x %.3f h)" % (n, cap, cfg["farm_raw_per_hour"], h)))
            elif pi and w.rate.get(pi):
                # the cache's item plus the same item in the ore (none of the table's ores drops it today): one budget
                cap = int(math.floor(cfg["item_rate_factor"] * w.rate[pi] * h))
                out.append((band, "ok" if n <= cap else "OVER",
                            "cache: %d %s of at most %d (%.1f x bank rate %.0f/h x %.3f h)" % (n, item, cap, cfg["item_rate_factor"], w.rate[pi], h)))
    return out


def items_yielded():
    """Every item a pile, a vein, the seam or the cache can yield: [(item, source)], for the greed value table."""
    out = []
    for res in table_resources():
        e = resources()[res]
        out.append((e["item"], "ore %s (drop %d-%d a block)" % (res, e["drop"][0], e["drop"][1])))
    c = data()["cache"]
    for k, e in c["items"].items():
        out.append((e["item"], "cache chest (%s), %s" % (k, ", ".join("band %s: %d" % (b, n) for b, n in sorted(e["count_by_band"].items())))))
    return out


# ------------------------------------------------------------------------------------------------- checks


def check_data(doc=None):
    """The table's own consistency, independent of any room."""
    bad = []
    D = data()
    res = D["resources"]
    for k, e in D["table"].items():
        if k not in res:
            bad.append("table row %s is not a resource" % k)
            continue
        if not (1 <= e["min_band"] <= e["max_band"] <= 6):
            bad.append("table row %s: bands %s..%s" % (k, e["min_band"], e["max_band"]))
        if not e.get("why"):
            bad.append("table row %s has no why" % k)
        for b, n in e["counts"].items():
            if not (e["min_band"] <= int(b) <= e["max_band"]) or int(n) < 1:
                bad.append("table row %s: count %s at band %s is outside min_band..max_band or not positive" % (k, n, b))
        for b in range(e["min_band"], e["max_band"] + 1):
            if str(b) not in e["counts"]:
                bad.append("table row %s has no count at band %d (min_band..max_band is a promise)" % (k, b))
    for b in BANDS:
        if row_total(seam_row(b)) != 24:
            bad.append("seam band %d sums to %d, not 24" % (b, row_total(seam_row(b))))
        for k in seam_row(b):
            if k not in res:
                bad.append("seam band %d: %s is not a resource" % (b, k))
    return bad


def problems(doc, d, slot):
    """Per room problems the kit's walk check cannot see (it counts breakable cells; this proves they cannot leak)."""
    if not has_resources_rooms(d) or theme_cfg(d) is None:
        return []
    bad = []
    for b in R.slot_build(doc, d, slot):
        r = b.room
        if r["kind"] != "resources":
            continue
        meta = b.meta.get("deposits")
        lab = "%s room %s" % (d["id"], r["id"])
        if meta is None:
            bad.append("%s: it is a resources room and has no deposits (the theme's dress list lacks the `deposits` op)" % lab)
            continue
        bad += leak_problems(lab, b)
    return bad


def leak_problems(lab, b):
    """Break EVERY ore cell of EVERY band (and the whole seam) in a copy of the grid: nothing may become reachable from the
    room's air that was not (the hull, a chamber, another room, the void), and no ore cell touches the room's box edge."""
    import numpy as np
    r = b.room
    g = b.grid
    meta = b.meta["deposits"]
    cells = [tuple(c["pos"]) for c in meta["cands"]] + [tuple(c[:3]) for c in b.anchors.get("seam", [])]
    bad = []
    for (x, y, z) in cells:
        if not (r["ix0"] <= x <= r["ix1"] and r["iz0"] <= z <= r["iz1"] and r["y_lo"] <= y <= r["ceil_y"] - 2):
            bad.append("%s: a pile cell (%d, %d, %d) is outside the room's interior" % (lab, x, y, z))
    if bad:
        return bad[:3]
    cls0 = g.cls()
    passable0 = (cls0 == G.PASS) | (cls0 == G.WATER)
    g2 = G.Grid(g.box)
    g2.a, g2.pal, g2.idx, g2.codes = g.a.copy(), list(g.pal), dict(g.idx), list(g.codes)
    for (x, y, z) in cells:
        g2.apply(("set", (x, y, z), "minecraft:air"))
    cls1 = g2.cls()
    passable1 = (cls1 == G.PASS) | (cls1 == G.WATER)
    sx, sy, sz = R.room_start(r)
    start = g.local(sx, sy, sz)

    def flood(p):
        seen = np.zeros(p.shape, dtype=bool)
        stack = [start]
        seen[start] = True
        while stack:
            cx, cy, cz = stack.pop()
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                nx, ny, nz = cx + dx, cy + dy, cz + dz
                if 0 <= nx < p.shape[0] and 0 <= ny < p.shape[1] and 0 <= nz < p.shape[2] and p[nx, ny, nz] and not seen[nx, ny, nz]:
                    seen[nx, ny, nz] = True
                    stack.append((nx, ny, nz))
        return seen

    before, after = flood(passable0), flood(passable1)
    gone = np.zeros(after.shape, dtype=bool)
    for (x, y, z) in cells:
        gone[g.local(x, y, z)] = True
    new = after & ~before & ~gone
    # every cell broken must itself be reached from the room's air (a pocket), and nothing else opens
    if new.any():
        ix, iy, iz = [int(v) for v in np.argwhere(new)[0]]
        x0, y0, z0 = g.box[:3]
        bad.append("%s: breaking the piles opens %d cells that were closed, the first at (%d, %d, %d): a hole out of the room"
                   % (lab, int(new.sum()), ix + x0, iy + y0, iz + z0))
    return bad


def register():
    if __name__ != "dungeon_resources":
        return       # a mutant copy exec'd by a test must not take the dress op over
    R.register_dress("deposits", dress_deposits, "light")
    if dress_deposits not in R.PICK_EXTRA_FNS:
        R.PICK_EXTRA_FNS.append(pick_extra)
    if problems not in R.EXTRA_CHECKS:
        R.EXTRA_CHECKS.append(problems)


register()


def report(doc):
    out = ["# resources: the table, per band (blocks of ore in the heaps and veins; the seam is 24 more)"]
    for band in BANDS:
        row = table_row(band)
        out.append("band %d: %s%s" % (band, ", ".join("%s %d" % (k, n) for k, n in row.items()) or "-",
                                       "  + cache " + ", ".join("%d %s" % (n, i.split(":")[1]) for _k, i, n in cache_items(band)) if cache_count(band) else ""))
    out.append("# budget")
    for band, verdict, detail in budget(doc):
        out.append("%s band %d: %s" % (verdict.upper() if verdict != "ok" else "ok", band, detail))
    out.append("# items a pile or cache can yield")
    for item, src in items_yielded():
        out.append("  %s  (%s)" % (item, src))
    return out


def main(argv=None):
    import dungeon as DG
    doc = DG.load()
    lines = report(doc)
    bad = check_data(doc) + [x for x in lines if x.startswith("OVER")]
    print("\n".join(lines))
    for x in bad:
        print("PROBLEM:", x)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
