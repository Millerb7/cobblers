#!/usr/bin/env python
"""The room kinds and the theme dressing ops tools/dungeon_rooms.py ships (docs/mechanics/DUNGEON_ROOMS.md).

Kinds built here, with their own geometry and runtime: entry_room, exit_room, boss_arena, drift, stairs, maze,
parkour, resources, dark_room, collapse_bridge, safe_room. A kind is registered with dungeon_rooms.register(); wave 2
registers its own in its own modules (dungeon_fights, dungeon_puzzles) the same way and never edits this file.

Every kind is deterministic: its randomness comes from dungeon_rooms.rng(d, room, salt), which depends on the dungeon
and room ids and not on the slot, so the four slots of a dungeon are the same dungeon.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_rooms as R  # noqa: E402
from dungeon_rooms import fill, setb, rng  # noqa: E402

DIRS = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
OPPOSITE = {"north": "south", "south": "north", "west": "east", "east": "west"}


def pick(rg, items):
    """One block from a string or a [{"block", "w"}] list."""
    if isinstance(items, str):
        return items
    tot = sum(i.get("w", 1) for i in items)
    r = rg.uniform(0, tot)
    for i in items:
        r -= i.get("w", 1)
        if r <= 0:
            return i["block"]
    return items[-1]["block"]


LOADED = "# chunks-loaded-by: the member standing in the room (its chunks are loaded)"


def U(doc):
    c = doc["engine"]["clock"]
    return c["units_per_tick"] * 20


# ------------------------------------------------------------------------------------------------- connectors


def kind_drift(doc, d, slot, room, theme):
    return {}


# ------------------------------------------------------------------------------------------------- entry, exit, arena


def _rip(room, theme, wall_x, zc, y):
    f, o = theme["rip"]["frame"], theme["rip"]["opening"]
    return [fill((wall_x, y, zc - 2, wall_x, y + 3, zc + 2), f), fill((wall_x, y, zc - 1, wall_x, y + 2, zc + 1), o)]


def kind_entry(doc, d, slot, room, theme):
    fy = room["floor_in"]
    z = room["z_in"]
    return {"blocks": _rip(room, theme, room["xa"], z, fy),
            "anchors": {"arrive": [room["xa"] + 3, fy, z, -90], "back": [room["xa"] + 1, fy, z],
                        "threshold": [room["xb"] - 1, fy, room["z_out"], -90]}}


def kind_exit(doc, d, slot, room, theme):
    fy = room["floor_in"]
    z = room["z_in"]
    return {"blocks": _rip(room, theme, room["xb"], z, fy),
            "anchors": {"far": [room["xb"] - 1, fy, z, 90]}}


def kind_arena(doc, d, slot, room, theme):
    fy = room["floor_in"]
    zc = (room["iz0"] + room["iz1"]) // 2
    sx = room["xa"] + (2 * (room["xb"] - room["xa"])) // 3
    return {"anchors": {"spot": [sx, fy, zc, 90], "arena": [room["ix0"], fy, room["iz0"], room["ix1"], fy + room["height"] - 2, room["iz1"]],
                        "center": [sx - 4, fy, zc]}}


# ------------------------------------------------------------------------------------------------- maze


def _maze_tree(nx, nz, start, rg, loops):
    """A spanning tree over an nx x nz grid by randomised depth-first search: {(i, j): {(i2, j2)}}."""
    adj = {(i, j): set() for i in range(nx) for j in range(nz)}
    seen = {start}
    stack = [start]
    while stack:
        i, j = stack[-1]
        nbrs = [(i + a, j + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= i + a < nx and 0 <= j + b < nz and (i + a, j + b) not in seen]
        if not nbrs:
            stack.pop()
            continue
        n = rg.choice(nbrs)
        seen.add(n)
        adj[(i, j)].add(n)
        adj[n].add((i, j))
        stack.append(n)
    for _ in range(loops):
        i, j = rg.randrange(nx), rg.randrange(nz)
        a, b = rg.choice(((1, 0), (0, 1)))
        if 0 <= i + a < nx and 0 <= j + b < nz:
            adj[(i, j)].add((i + a, j + b))
            adj[(i + a, j + b)].add((i, j))
    return adj


def kind_maze(doc, d, slot, room, theme):
    m = theme["maze"]
    p = room["params"]
    rg = rng(d, room, "maze:%s" % p.get("seed", ""))
    nx = (room["ix1"] - room["ix0"]) // 4
    nz = (room["iz1"] - room["iz0"]) // 4
    fy = room["floor_in"]
    H = int(p.get("wall_height", m.get("height", 4)))
    j_in = (room["z_in"] - 2 - room["iz0"]) // 4
    j_out = (room["z_out"] - 2 - room["iz0"]) // 4
    adj = _maze_tree(nx, nz, (0, j_in), rg, int(p.get("loops", 0)))
    ix0, iz0 = room["ix0"], room["iz0"]
    ops = []
    wall = m["wall"]
    ops.append(fill((ix0, fy, iz0, room["ix1"], fy + H - 1, room["iz1"]), pick(rg, wall) if isinstance(wall, str) else wall[0]["block"]))
    if not isinstance(wall, str) and len(wall) > 1:
        # a second and third wall block in thin horizontal bands, so the hedge or the rubble is not one flat block
        for k, e in enumerate(wall[1:], 1):
            y = fy + (k * 2) % H
            ops.append(fill((ix0, y, iz0, room["ix1"], y, room["iz1"]), e["block"]))
    if m.get("top"):
        ops.append(fill((ix0, fy + H - 1, iz0, room["ix1"], fy + H - 1, room["iz1"]), m["top"]))
    if m.get("post"):
        for i in range(nx + 1):
            for j in range(nz + 1):
                ops.append(fill((ix0 + 4 * i, fy, iz0 + 4 * j, ix0 + 4 * i, fy + H - 1, iz0 + 4 * j), m["post"]))
    dead = []
    for (i, j), ns in adj.items():
        cx, cz = ix0 + 4 * i + 1, iz0 + 4 * j + 1
        ops.append(fill((cx, fy, cz, cx + 2, fy + H - 1, cz + 2), "minecraft:air"))
        if (i, j) not in ((0, j_in), (nx - 1, j_out)) and len(ns) == 1:
            dead.append([cx + 1, fy, cz + 1])
        for (i2, j2) in ns:
            if (i2, j2) > (i, j):
                if i2 > i:
                    ops.append(fill((cx + 3, fy, cz, cx + 3, fy + H - 1, cz + 2), "minecraft:air"))
                else:
                    ops.append(fill((cx, fy, cz + 3, cx + 2, fy + H - 1, cz + 3), "minecraft:air"))
    ops.append(fill((ix0, fy, room["z_in"] - 1, ix0, fy + H - 1, room["z_in"] + 1), "minecraft:air"))
    ops.append(fill((room["ix1"], fy, room["z_out"] - 1, room["ix1"], fy + H - 1, room["z_out"] + 1), "minecraft:air"))
    ci, cj = nx // 2, nz // 2
    return {"blocks": ops,
            "anchors": {"center": [ix0 + 4 * ci + 2, fy, iz0 + 4 * cj + 2], "dead_ends": dead,
                        "entry": [ix0 + 2, fy, room["z_in"], -90], "exit": [room["ix1"] - 2, fy, room["z_out"], -90]},
            "meta": {"cells": [nx, nz], "dead_end_count": len(dead)}}


def check_maze(doc, d, slot):
    bad = []
    for r in R.layout(doc, d, slot):
        if r["kind"] == "maze":
            if (r["z_out"] - r["z_in"]) % 4:
                bad.append("%s room %s: a maze's exit_dz must be a multiple of 4 (its rows are 4 apart)" % (d["id"], r["id"]))
            rows = (r["iz1"] - r["iz0"]) // 4
            for z in (r["z_in"], r["z_out"]):
                j = (z - 2 - r["iz0"]) // 4
                if not (0 <= j < rows) or (z - 2 - r["iz0"]) % 4:
                    bad.append("%s room %s: a door at z %d is not on a maze row" % (d["id"], r["id"], z))
            if r["height"] < int(r["params"].get("wall_height", 4)) + 2:
                bad.append("%s room %s: a maze needs its height 2 over the wall height" % (d["id"], r["id"]))
    return bad


# ------------------------------------------------------------------------------------------------- parkour


def _sections(L_int, nsec):
    """Ledge x offsets (6 long each) and the free lengths between them."""
    free_total = L_int - 6 * (nsec + 1)
    each = free_total // nsec
    gaps = [each + (1 if k < free_total - each * nsec else 0) for k in range(nsec)]
    return gaps


def _platform_run(free, rg):
    """Platform starts and gaps filling `free` cells between two ledges: 3-wide platforms, gaps of 1 or 2."""
    ms = [m for m in range(1, free) if m + 1 <= free - 3 * m <= 2 * (m + 1)]
    if not ms:
        return None
    m = ms[len(ms) // 2]
    extra = free - 3 * m - (m + 1)
    gaps = [1] * (m + 1)
    for k in rg.sample(range(m + 1), extra):
        gaps[k] = 2
    return m, gaps


def kind_parkour(doc, d, slot, room, theme):
    t = theme["parkour"]
    p = room["params"]
    rg = rng(d, room, "parkour")
    fy = room["floor_in"]
    y_lo = room["y_lo"]
    ix0, ix1, iz0, iz1 = room["ix0"], room["ix1"], room["iz0"], room["iz1"]
    L = ix1 - ix0 + 1
    nsec = int(p.get("sections", max(1, (L - 12) // 30)))
    gaps = _sections(L, nsec)
    zl = [round(room["z_in"] + (room["z_out"] - room["z_in"]) * s / nsec) for s in range(nsec + 1)]
    ops = [fill((ix0, y_lo - 1, iz0, ix1, y_lo - 1, iz1), t["catch_floor"])]
    platforms, ledges, ck = [], [], []

    def ledge(x0, zc_):
        z0, z1 = zc_ - 3, zc_ + 3
        ops.append(fill((x0, y_lo, z0, x0 + 5, fy - 2, z1), t["pillar"]))
        ops.append(fill((x0, fy - 1, z0, x0 + 5, fy - 1, z1), t["ledge"]))
        ops.append(fill((x0 + 1, fy - 1, z0 + 1, x0 + 4, fy - 1, z1 - 1), t["ledge_top"]))
        ledges.append((x0, x0 + 5, z0, z1))
        ck.append([x0 + 3, fy, zc_, -90])

    x = ix0
    ledge(x, zl[0])
    zc = zl[0]
    off = 0
    for s, free in enumerate(gaps):
        run = _platform_run(free, rg)
        if run is None:
            raise R.RoomError("%s room %s: no way to place platforms across a gap of %d" % (d["id"], room["id"], free))
        m, gp = run
        cx = x + 6
        for k in range(m):
            cx += gp[k]
            dy = rg.choice((0, 0, 1, -1))
            if abs(off + dy) > 1:
                dy = 0
            off += dy
            target = zl[s] + (zl[s + 1] - zl[s]) * (k + 1) / (m + 1)
            zn = round(target) + rg.choice((-2, -1, 0, 1, 2))
            zn = min(max(zn, zc - 2), zc + 2)
            zc = min(max(zn, iz0 + 3), iz1 - 3)
            top = fy + off
            ops.append(fill((cx, y_lo, zc, cx, top - 2, zc), t["pillar"]))
            ops.append(fill((cx, top - 1, zc - 1, cx + 2, top - 1, zc + 1), t["platform"]))
            platforms.append([cx + 1, top, zc])
            cx += 3
        x = x + 6 + free
        ledge(x, zl[s + 1])
        zc = zl[s + 1]
    # cracked lamps across the entry ledge's west edge: the no-deploy box's edge (3.4)
    ops.append(fill((ix0, fy - 1, room["z_in"] - 3, ix0, fy - 1, room["z_in"] + 3), theme["lamp"]))
    # catch floor lights, flush, so nothing walkable is dark
    lights = []
    for lx in range(ix0 + 4, ix1, 8):
        for lz in range(iz0 + 4, iz1, 8):
            ops.append(setb((lx, y_lo - 1, lz), theme["hull"]["light"]))
            lights.append((lx, y_lo - 1, lz))
    pen = int(doc["engine"]["clock"]["fall_penalty_s"]) * U(doc)
    catch = [ix0, y_lo, iz0, ix1, y_lo + 1, iz1]
    ck_boxes = [[a, fy, z0, b, fy + 2, z1] for (a, b, z0, z1) in ledges]
    tick = [LOADED, "effect give @s minecraft:resistance 2 4 true"]
    for i, bx in enumerate(ck_boxes):
        tick.append("execute if entity @s[%s] run scoreboard players set @s dg.ck %d" % (R.sel_box(bx), i))
    tick.append("execute if entity @s[%s] run function %s" % (R.sel_box(catch), R.room_fn(d, room, slot, "fall")))
    fall = [R.HEAD, LOADED, "# a fall onto the catch floor: back to the last ledge stood on, the clock charged, no damage (F1: resistance)",
            "scoreboard players remove @s dg.clock %d" % pen,
            "effect give @s minecraft:resistance 3 4 true"]
    for i, c in enumerate(ck):
        fall.append("execute if score @s dg.ck matches %d run tp @s %d.5 %d %d.5 %d 0" % (i, c[0], c[1], c[2], c[3]))
    fall += ["playsound minecraft:entity.player.hurt master @s ~ ~ ~ 0.6 1",
             "title @s actionbar %s" % R.text(theme["messages"]["fall"].replace("{s}", str(doc["engine"]["clock"]["fall_penalty_s"])), "red")]
    return {"blocks": ops,
            "anchors": {"checkpoints": ck, "platforms": platforms, "catch": catch, "center": ck[len(ck) // 2]},
            "lights": lights,
            "functions": {"fall": fall, "enter": ["scoreboard players set @s dg.ck 0"], "tick": tick},
            "meta": {"light_ref_y": fy, "extra_drop": 0, "ledges": ledges, "platform_count": len(platforms)}}


def check_parkour(doc, d, slot):
    bad = []
    for r in R.layout(doc, d, slot):
        if r["kind"] == "parkour" and r["height"] < 7:
            bad.append("%s room %s: a parkour needs a height of at least 7 (jumps, 3 clear above each)" % (d["id"], r["id"]))
        if r["kind"] == "parkour" and r["rise"]:
            bad.append("%s room %s: a parkour is level" % (d["id"], r["id"]))
    return bad


# ------------------------------------------------------------------------------------------------- collapse bridge


def kind_bridge(doc, d, slot, room, theme):
    t = theme["bridge"]
    fy = room["floor_in"]
    y_lo = room["y_lo"]
    ix0, ix1, iz0, iz1 = room["ix0"], room["ix1"], room["iz0"], room["iz1"]
    z = room["z_in"]
    lag = int(room["params"].get("lag", 6))
    ledge_w = int(room["params"].get("ledge", 5))
    ops = []
    west = (ix0, ix0 + ledge_w - 1)
    east = (ix1 - ledge_w + 1, ix1)
    for a, b in (west, east):
        ops.append(fill((a, y_lo, z - 4, b, fy - 2, z + 4), t["support"]))
        ops.append(fill((a, fy - 1, z - 4, b, fy - 1, z + 4), t["ledge"]))
    sx0, sx1 = west[1] + 1, east[0] - 1
    segs = []
    x = sx0
    while x <= sx1:
        segs.append((x, min(x + 2, sx1)))
        x += 3
    span = [sx0, fy - 1, z - 3, sx1, fy, z + 3]
    ops.append(fill((sx0, fy - 1, z - 2, sx1, fy - 1, z + 2), t["span"]))
    ops.append(fill((sx0, fy - 1, z - 3, sx1, fy - 1, z - 3), t["span_edge"]))
    ops.append(fill((sx0, fy - 1, z + 3, sx1, fy - 1, z + 3), t["span_edge"]))
    ops.append(fill((sx0, fy, z - 3, sx1, fy, z - 3), t["rail"]))
    ops.append(fill((sx0, fy, z + 3, sx1, fy, z + 3), t["rail"]))
    for lx in range(sx0 + 3, sx1 - 1, 8):
        for lz in (z - 3, z + 3):
            ops.append(setb((lx, fy + 1, lz), t["post"]))
    lights = []
    for lx in range(ix0 + 4, ix1, 8):
        for lz in range(iz0 + 4, iz1, 8):
            ops.append(setb((lx, y_lo - 1, lz), theme["hull"]["light"]))
            lights.append((lx, y_lo - 1, lz))
    pen = int(doc["engine"]["clock"]["fall_penalty_s"]) * U(doc)
    catch = [ix0, y_lo, iz0, ix1, y_lo + 1, iz1]
    ck = [[west[0] + 2, fy, z, -90], [east[1] - 2, fy, z, 90]]
    wbox = [west[0], fy, z - 4, west[1], fy + 2, z + 4]
    ebox = [east[0], fy, z - 4, east[1], fy + 2, z + 4]
    restore = [R.HEAD, LOADED, "# the span whole again (the member stands on a ledge, or the slot is reset)"]
    restore += [R.op_line(op) for op in (fill((sx0, fy - 1, z - 2, sx1, fy - 1, z + 2), t["span"]),
                                         fill((sx0, fy - 1, z - 3, sx1, fy - 1, z - 3), t["span_edge"]),
                                         fill((sx0, fy - 1, z + 3, sx1, fy - 1, z + 3), t["span_edge"]),
                                         fill((sx0, fy, z - 3, sx1, fy, z - 3), t["rail"]),
                                         fill((sx0, fy, z + 3, sx1, fy, z + 3), t["rail"]))]
    restore += ["tag @s remove %s" % R.TAG_CBE, "tag @s remove %s" % R.TAG_CBW]
    tick = [LOADED, "effect give @s minecraft:resistance 2 4 true",
            "execute store result score @s dg.x run data get entity @s Pos[0]",
            "execute if entity @s[%s] run scoreboard players set @s dg.ck 0" % R.sel_box(wbox),
            "execute if entity @s[%s] run scoreboard players set @s dg.ck 1" % R.sel_box(ebox),
            "execute if entity @s[%s,tag=%s] run function %s" % (R.sel_box(wbox), R.TAG_CBE, R.room_fn(d, room, slot, "restore")),
            "execute if entity @s[%s,tag=%s] run function %s" % (R.sel_box(wbox), R.TAG_CBW, R.room_fn(d, room, slot, "restore")),
            "execute if entity @s[%s,tag=%s] run function %s" % (R.sel_box(ebox), R.TAG_CBE, R.room_fn(d, room, slot, "restore")),
            "execute if entity @s[%s,tag=%s] run function %s" % (R.sel_box(ebox), R.TAG_CBW, R.room_fn(d, room, slot, "restore")),
            "execute unless entity @s[tag=%s] unless entity @s[tag=%s] if entity @s[x=%d,y=%d,z=%d,dx=1,dy=2,dz=6] run tag @s add %s"
            % (R.TAG_CBE, R.TAG_CBW, sx0, fy, z - 3, R.TAG_CBE),
            "execute unless entity @s[tag=%s] unless entity @s[tag=%s] if entity @s[x=%d,y=%d,z=%d,dx=1,dy=2,dz=6] run tag @s add %s"
            % (R.TAG_CBE, R.TAG_CBW, sx1 - 1, fy, z - 3, R.TAG_CBW)]
    for a, b in segs:
        cells = fill((a, fy - 1, z - 3, b, fy, z + 3), "minecraft:air")
        tick.append("execute if entity @s[tag=%s] if score @s dg.x matches %d.. run %s" % (R.TAG_CBE, b + lag, R.op_line(cells)))
        tick.append("execute if entity @s[tag=%s] if score @s dg.x matches ..%d run %s" % (R.TAG_CBW, a - lag, R.op_line(cells)))
    tick.append("execute if entity @s[%s] run function %s" % (R.sel_box(catch), R.room_fn(d, room, slot, "fall")))
    fall = [R.HEAD, LOADED, "# a fall: back to the ledge last stood on, the clock charged, no damage (F1: resistance)",
            "scoreboard players remove @s dg.clock %d" % pen,
            "effect give @s minecraft:resistance 3 4 true"]
    for i, c in enumerate(ck):
        fall.append("execute if score @s dg.ck matches %d run tp @s %d.5 %d %d.5 %d 0" % (i, c[0], c[1], c[2], c[3]))
    fall += ["playsound minecraft:entity.player.hurt master @s ~ ~ ~ 0.6 1",
             "title @s actionbar %s" % R.text(theme["messages"]["fall"].replace("{s}", str(doc["engine"]["clock"]["fall_penalty_s"])), "red")]
    return {"blocks": ops, "lights": lights,
            "anchors": {"span": span, "checkpoints": ck, "catch": catch, "center": [(sx0 + sx1) // 2, fy, z]},
            "functions": {"enter": ["scoreboard players set @s dg.ck 0", "tag @s remove %s" % R.TAG_CBE, "tag @s remove %s" % R.TAG_CBW],
                          "tick": tick, "fall": fall, "restore": restore[1:],
                          "reset": [R.op_line(op) for op in (fill((sx0, fy - 1, z - 2, sx1, fy - 1, z + 2), t["span"]),
                                                             fill((sx0, fy - 1, z - 3, sx1, fy - 1, z - 3), t["span_edge"]),
                                                             fill((sx0, fy - 1, z + 3, sx1, fy - 1, z + 3), t["span_edge"]),
                                                             fill((sx0, fy, z - 3, sx1, fy, z - 3), t["rail"]),
                                                             fill((sx0, fy, z + 3, sx1, fy, z + 3), t["rail"]))]},
            "meta": {"light_ref_y": fy, "segments": len(segs)}}


def check_bridge(doc, d, slot):
    bad = []
    for r in R.layout(doc, d, slot):
        if r["kind"] == "collapse_bridge":
            if r["z_out"] != r["z_in"]:
                bad.append("%s room %s: a collapse bridge is straight (no exit_dz)" % (d["id"], r["id"]))
            if r["height"] < 7:
                bad.append("%s room %s: a collapse bridge needs a height of at least 7" % (d["id"], r["id"]))
            if r["length"] < 30:
                bad.append("%s room %s: a collapse bridge is at least 30 long" % (d["id"], r["id"]))
            if r["width"] < 9:
                bad.append("%s room %s: a collapse bridge is at least 9 wide" % (d["id"], r["id"]))
    return bad


# ------------------------------------------------------------------------------------------------- resources


def seam_cells(room):
    p = room["params"]
    n = int(p.get("seam_blocks", 24))
    w = int(p.get("face_w", 8))
    rows = -(-n // w)
    cx = (room["ix0"] + room["ix1"]) // 2
    x0 = cx - w // 2
    z = room["iz0"] + 2
    fy = room["floor_in"]
    return [(x0 + i, fy + j, z) for j in range(rows) for i in range(w)][:n], (x0, fy, room["iz0"], x0 + w - 1, fy + rows - 1, z)


def seam_block_for(theme, band, j, n):
    avail = [e["block"] for e in theme["seam"]["blocks"] if e["min_band"] <= band]
    return avail[((j * 5) % n) % len(avail)]


def kind_resources(doc, d, slot, room, theme):
    t = theme["seam"]
    cells, slab = seam_cells(room)
    n = len(cells)
    ops = [fill(slab, t["slab"])]
    fy = room["floor_in"]
    bands = [b["band"] for b in doc["engine"]["bands"]]
    reset = ["# the seam's face: band 1's blocks first, then each higher band's difference (the entrant's band is frozen)"]
    h = R.state_holder(slot, room)
    first = {}
    for j, (x, y, z) in enumerate(cells):
        first[j] = seam_block_for(theme, bands[0], j, n)
        reset.append("setblock %d %d %d %s" % (x, y, z, first[j]))
    for b in bands[1:]:
        for j, (x, y, z) in enumerate(cells):
            blk = seam_block_for(theme, b, j, n)
            if blk != seam_block_for(theme, b - 1, j, n):
                reset.append("execute if score @s dg.band matches %d.. run setblock %d %d %d %s" % (b, x, y, z, blk))
    reset += ["scoreboard players set %sm%d dg.rs 1" % (h, j) for j in range(n)]
    tick = []
    for j, (x, y, z) in enumerate(cells):
        hj = "%sm%d" % (h, j)
        tick += ["execute if score %s dg.rs matches 1 if block %d %d %d minecraft:air run scoreboard players set %s dg.rs 2" % (hj, x, y, z, hj),
                 "execute if score %s dg.rs matches 2 run function %s" % (hj, R.F("greed/take")),
                 "execute if score %s dg.rs matches 2 run scoreboard players set %s dg.rs 3" % (hj, hj)]
    # the face is written once by the shell too, with band 1's blocks, so a bare shell is not a hole in the wall
    for j, (x, y, z) in enumerate(cells):
        ops.append(setb((x, y, z), first[j]))
    cx = (slab[0] + slab[3]) // 2
    return {"blocks": ops,
            "anchors": {"seam": [list(c) for c in cells], "seam_box": list(slab), "stand_at": [cx, fy, room["iz0"] + 3, 180]},
            "functions": {"reset": reset, "tick": tick},
            "reserve": [(slab[0] - 1, fy, slab[2], slab[3] + 1, fy, slab[5] + 3)],
            "meta": {"seam_cells": n}}


# ------------------------------------------------------------------------------------------------- dark room


def kind_dark(doc, d, slot, room, theme):
    rg = rng(d, room, "dark")
    fy = room["floor_in"]
    p = room["params"]
    n = int(p.get("candles", 3))
    xs = [room["ix0"] + int((room["ix1"] - room["ix0"]) * (k + 1) / (n + 1)) for k in range(n)]
    ops, spots = [], []
    for x in xs:
        z = room["z_in"] + rg.choice((-2, 2))
        z = min(max(z, room["iz0"] + 1), room["iz1"] - 1)
        ops.append(setb((x, fy, z), "minecraft:candle[candles=4,lit=true]"))
        spots.append([x, fy, z])
    torches = int(p.get("torches", 3))
    floors = theme["dark"]["place_on"]
    give = ('give @s minecraft:torch[minecraft:can_place_on={predicates:[{blocks:[%s]}]}] %d'
            % (",".join('"%s"' % b for b in floors), torches)) if torches else None
    box = R.sel_box(room["box"])
    reset = ["execute in %s run fill %d %d %d %d %d %d minecraft:air replace minecraft:torch" % ((doc["engine"]["pocket"]["dimension"],) + tuple(room["box"])),
             "execute in %s run fill %d %d %d %d %d %d minecraft:air replace minecraft:wall_torch" % ((doc["engine"]["pocket"]["dimension"],) + tuple(room["box"]))]
    enter = ["title @s actionbar %s" % R.text(theme["messages"]["dark"], "dark_gray")]
    if give:
        enter.append(give)
    return {"blocks": ops, "anchors": {"candles": spots}, "functions": {"enter": enter, "reset": reset},
            "meta": {"torches": torches, "assumed": "can_place_on on a torch in adventure mode is UNPROVEN (the shape is R2's can_break)"}}


# ------------------------------------------------------------------------------------------------- safe room


def kind_safe(doc, d, slot, room, theme):
    s = theme["safe"]
    fy = room["floor_in"]
    zc = (room["iz0"] + room["iz1"]) // 2
    cx = (room["ix0"] + room["ix1"]) // 2
    ops = []
    ops.append(fill((cx - 4, fy, zc - 2, cx + 4, fy, zc + 2), s["rug"]))
    hz = room["iz0"] + 1
    ops.append(fill((cx - 2, fy, hz + 1, cx + 2, fy, hz + 1), s["counter"]))
    ops.append(fill((cx - 2, fy + 1, hz + 1, cx + 2, fy + 1, hz + 1), s["counter_top"]))
    for k, bx in enumerate((cx - 5, cx + 5)):
        face = "east" if k == 0 else "west"
        ops.append(setb((bx, fy, zc), "%s[facing=%s,half=bottom]" % (s["bench"], face)))
        ops.append(setb((bx, fy, zc - 1), "%s[facing=%s,half=bottom]" % (s["bench"], face)))
        ops.append(setb((bx, fy, zc + 1), "%s[facing=%s,half=bottom]" % (s["bench"], face)))
    lights = []
    for bx in (room["ix0"] + 2, room["ix1"] - 2):
        for bz in (room["iz0"] + 1, room["iz1"] - 1):
            ops.append(setb((bx, fy, bz), s["post"]))
            ops.append(setb((bx, fy + 1, bz), s["lantern"]))
            lights.append((bx, fy + 1, bz))
    return {"blocks": ops, "lights": lights, "reserve": [(cx - 6, fy, hz - 1, cx + 6, fy, zc + 3)],
            "anchors": {"healer": [cx, fy, hz, 0], "rest": [cx, fy, zc + 3, 180], "center": [cx, fy, zc + 3]}}


# ------------------------------------------------------------------------------------------------- dressing ops


def _cells(ctx):
    return ctx.standable_cells()


def _air_col(ctx, x, y0, y1, z):
    return all(ctx.air(x, y, z) for y in range(y0, y1 + 1))


def dress_base_course(ctx, spec):
    r = ctx.room
    y = r["y_lo"] if spec.get("where", "bottom") == "bottom" else r["ceil_y"] - 1
    if r["rise"]:
        return
    for zw in (r["za"], r["zb"]):
        ctx.add(fill((r["ix0"], y, zw, r["ix1"], y, zw), spec["block"]))


def dress_pillars(ctx, spec):
    r = ctx.room
    every = int(spec.get("every", 6))
    rg = ctx.rng
    for k, x in enumerate(range(r["ix0"] + 3, r["ix1"] - 2, every)):
        for zw in (r["za"], r["zb"]):
            top = r["ceil_y"] - 1
            if rg.random() < spec.get("broken_p", 0):
                top -= rg.randint(1, max(1, r["height"] - 3))
            ctx.add(fill((x, r["y_lo"], zw, x, top, zw), spec["block"]))
            if spec.get("cap") and top == r["ceil_y"] - 1:
                ctx.add(fill((x, top, zw, x, top, zw), spec["cap"]))


def dress_timber(ctx, spec):
    r = ctx.room
    if r["rise"] or r["pit"]:
        return
    every = int(spec.get("every", 8))
    fy = r["floor_in"]
    zc = (r["iz0"] + r["iz1"]) // 2
    for x in range(r["ix0"] + 3, r["ix1"] - 2, every):
        ok = all(ctx.air(x, y, z) for z in (r["iz0"], r["iz1"]) for y in range(fy, r["ceil_y"] - 1)) and not any(
            (x, z) in ctx.keep or (x, z) in ctx.trail for z in (r["iz0"], r["iz1"]))
        if not ok:
            continue
        for z in (r["iz0"], r["iz1"]):
            ctx.add(fill((x, fy, z, x, r["ceil_y"] - 2, z), spec["post"]))
        ctx.add(fill((x, r["ceil_y"] - 1, r["iz0"], x, r["ceil_y"] - 1, r["iz1"]), spec["beam"]))
        if spec.get("lantern") and r["ceil_y"] - 3 >= fy + 3 and all(ctx.air(x, y, zc) for y in (r["ceil_y"] - 2, r["ceil_y"] - 3)):
            ctx.add(setb((x, r["ceil_y"] - 2, zc), "minecraft:chain"))
            ctx.add(setb((x, r["ceil_y"] - 3, zc), "minecraft:lantern[hanging=true]"))
            ctx.lights.append((x, r["ceil_y"] - 3, zc))


def dress_streak(ctx, spec):
    r = ctx.room
    rg = ctx.rng
    wall = ctx.theme["hull"]["wall"]
    fy = r["floor_in"]
    for _ in range(int(spec.get("count", 4))):
        zw = rg.choice((r["za"], r["zb"]))
        ln = rg.randint(*spec.get("len", [3, 7]))
        x0 = rg.randint(r["ix0"] + 2, max(r["ix0"] + 2, r["ix1"] - ln - 1))
        y = rg.randint(r["y_lo"] + 1, max(r["y_lo"] + 1, r["y_lo"] + 3))
        ctx.add(fill((x0, y, zw, x0 + ln - 1, y + rg.randint(0, 1), zw), pick(rg, spec["blocks"]), "replace " + R.G.base(wall)))


def dress_floor_strip(ctx, spec):
    r = ctx.room
    if r["rise"] or r["pit"]:
        return
    fy = r["floor_in"]
    y = fy - 1
    zs = {}
    for x in range(r["ix0"], r["ix1"] + 1):
        t = (x - r["ix0"]) / max(1, r["ix1"] - r["ix0"])
        zs[x] = round(r["z_in"] + (r["z_out"] - r["z_in"]) * min(1, max(0, (t - 0.25) / 0.5)))
    every = int(spec.get("every", 3))
    for x in range(r["ix0"] + 1, r["ix1"], every):
        ctx.add(fill((x, y, zs[x] - 1, x, y, zs[x] + 1), spec["sleeper"], "replace " + R.G.base(ctx.theme["hull"]["floor"])))
    x = r["ix0"]
    while x <= r["ix1"]:
        e = x
        while e + 1 <= r["ix1"] and zs[e + 1] == zs[x]:
            e += 1
        for dz in (-1, 1):
            ctx.add(fill((x, y, zs[x] + dz, e, y, zs[x] + dz), spec["rail"], "replace " + R.G.base(ctx.theme["hull"]["floor"])))
        x = e + 1


def dress_floor_patches(ctx, spec):
    r = ctx.room
    if r["rise"] or r["pit"]:
        return
    rg = ctx.rng
    area = (r["ix1"] - r["ix0"] + 1) * (r["iz1"] - r["iz0"] + 1)
    n = int(area * spec.get("per100", 4) / 100)
    y = r["floor_in"] - 1
    base = "replace " + R.G.base(ctx.theme["hull"]["floor"])
    for _ in range(n):
        w, h = rg.randint(*spec.get("size", [2, 4])), rg.randint(*spec.get("size", [2, 4]))
        x0 = rg.randint(r["ix0"] + 3, max(r["ix0"] + 3, r["ix1"] - w - 2))
        z0 = rg.randint(r["iz0"], max(r["iz0"], r["iz1"] - h))
        ctx.add(fill((x0, y, z0, x0 + w - 1, y, z0 + h - 1), pick(rg, spec["blocks"]), base))


def dress_ground_cover(ctx, spec):
    rg = ctx.rng
    r = ctx.room
    used = set()
    cells = _cells(ctx)
    rg.shuffle(cells)
    for (x, y, z) in cells:
        if (x, z) in ctx.keep or abs(x - r["ix0"]) < 2 or abs(x - r["ix1"]) < 2 or (x, z) in used or not ctx.air(x, y, z):
            continue
        below = R.G.base(ctx.grid.block_at(x, y - 1, z))
        roll = rg.random()
        acc = 0.0
        for pl in spec["plants"]:
            acc += pl["p"]
            if roll >= acc:
                continue
            if pl.get("on") and below not in pl["on"]:
                break
            if pl.get("solid") and ctx.reserved(x, z):
                break
            if pl.get("double"):
                if not ctx.air(x, y + 1, z) or y + 1 > r["ceil_y"] - 4:
                    break
                ctx.add(setb((x, y, z), pl["double"]["lower"]))
                ctx.add(setb((x, y + 1, z), pl["double"]["upper"]))
            else:
                ctx.add(setb((x, y, z), pl["block"]))
            used.add((x, z))
            break


def _free(ctx, x, z):
    return not ctx.reserved(x, z)


def dress_trunks(ctx, spec):
    r = ctx.room
    rg = ctx.rng
    cells = [c for c in _cells(ctx) if _free(ctx, c[0], c[2]) and r["ix0"] + 2 <= c[0] <= r["ix1"] - 2]
    rg.shuffle(cells)
    want = int(len(cells) * spec.get("density", 0.08))
    gap = int(spec.get("min_gap", 2))
    placed = []
    top = r["ceil_y"] - 1
    for (x, y, z) in cells:
        if len(placed) >= want:
            break
        thick = 2 if rg.random() < spec.get("thick_p", 0.25) else 1
        foot = [(x + a, z + b) for a in range(thick) for b in range(thick)]
        if any(not _free(ctx, fx, fz) or fx > r["ix1"] - 2 or fz > r["iz1"] for fx, fz in foot):
            continue
        if any(max(abs(x - px), abs(z - pz)) < gap + thick for px, pz, pt in placed):
            continue
        if not all(_air_col(ctx, fx, y, top, fz) for fx, fz in foot):
            continue
        ctx.add(fill((x, y, z, x + thick - 1, top, z + thick - 1), spec["block"]))
        placed.append((x, z, thick))
        if rg.random() < spec.get("vines_p", 0.5):
            side = rg.choice(list(DIRS))
            dx, dz = DIRS[side]
            if dx:
                vx, vz = (x + thick if dx > 0 else x - 1), z + rg.randrange(thick)
            else:
                vx, vz = x + rg.randrange(thick), (z + thick if dz > 0 else z - 1)
            face = OPPOSITE[side]
            ln = rg.randint(*spec.get("vine_len", [3, 9]))
            y1 = top - rg.randint(0, 2)
            for yy in range(y1, max(y1 - ln, y - 1), -1):
                if not ctx.air(vx, yy, vz) or not _free(ctx, vx, vz):
                    break
                ctx.add(setb((vx, yy, vz), "minecraft:vine[%s=true]" % face))


def dress_canopy(ctx, spec):
    r = ctx.room
    if r["height"] < 6:
        return
    rg = ctx.rng
    leaf = spec["leaf"]
    top = r["ceil_y"] - 1
    layers = int(spec.get("layers", 2))
    box = (r["ix0"], 0, r["iz0"], r["ix1"], 0, r["iz1"])
    for k in range(layers):
        y = top - k
        ctx.add(fill((box[0], y, box[2], box[3], y, box[5]), leaf, "keep"))
    if layers >= 2:
        for x in range(r["ix0"], r["ix1"] + 1):
            for z in range(r["iz0"], r["iz1"] + 1):
                if rg.random() < spec.get("hole_p", 0.1) and ctx.grid.block_at(x, top - 1, z) == leaf:
                    ctx.add(setb((x, top - 1, z), "minecraft:air"))
    for x in range(r["ix0"] + 1, r["ix1"]):
        for z in range(r["iz0"], r["iz1"] + 1):
            if spec.get("light") and rg.random() < spec.get("light_p", 0.03) and ctx.grid.block_at(x, top, z) == leaf:
                ctx.add(setb((x, top, z), spec["light"]))
                ctx.lights.append((x, top, z))
    for x in range(r["ix0"] + 2, r["ix1"] - 1):
        for z in range(r["iz0"], r["iz1"] + 1):
            if rg.random() < spec.get("curtain_p", 0.03) and _free(ctx, x, z):
                ln = rg.randint(*spec.get("curtain_len", [2, 3]))
                low = top - layers - ln + 1
                if low <= r["floor_in"] + 4:
                    continue
                if not all(ctx.air(x, y, z) or ctx.grid.block_at(x, y, z) == leaf for y in range(low, top - layers + 1)):
                    continue
                ctx.add(fill((x, low, z, x, top - layers, z), leaf))
                if z + 1 <= r["iz1"] and _free(ctx, x, z + 1):
                    for y in range(low, top - layers + 1):
                        if ctx.air(x, y, z + 1):
                            ctx.add(setb((x, y, z + 1), "minecraft:vine[north=true]"))
                    for y in range(low - 1, low - 1 - rg.randint(1, 4), -1):
                        if y > r["floor_in"] + 1 and ctx.air(x, y, z + 1):
                            ctx.add(setb((x, y, z + 1), "minecraft:vine[north=true]"))


def dress_wall_vines(ctx, spec):
    r = ctx.room
    rg = ctx.rng
    for z_in, face in ((r["iz0"], "north"), (r["iz1"], "south")):
        for x in range(r["ix0"] + 2, r["ix1"] - 1):
            if rg.random() >= spec.get("p", 0.1):
                continue
            blk = pick(rg, spec["blocks"])
            y1 = r["ceil_y"] - rg.randint(3, 5)
            if "lichen" in blk:
                y = rg.randint(r["floor_in"] + 1, y1)
                if ctx.air(x, y, z_in):
                    ctx.add(setb((x, y, z_in), "%s[%s=true]" % (blk, face)))
                continue
            ln = rg.randint(*spec.get("len", [2, 6]))
            for y in range(y1, y1 - ln, -1):
                if y <= r["floor_in"] or not ctx.air(x, y, z_in):
                    break
                ctx.add(setb((x, y, z_in), "%s[%s=true]" % (blk, face)))


def _water_ok(ctx, x, y, z):
    g = ctx.grid
    return (g.inside(x, y - 1, z) and R.G.classify(g.block_at(x, y - 1, z)) == R.G.SOLID and ctx.air(x, y, z)
            and R.G.classify(g.block_at(x, y, z)) == R.G.PASS and (x, z) not in ctx.keep)


def dress_stream(ctx, spec):
    r = ctx.room
    if r["rise"] or r["pit"]:
        return
    rg = ctx.rng
    fy = r["floor_in"]
    y = fy - 1
    bed = spec.get("bed", ctx.theme["hull"]["floor"])
    water = set()
    n = int(spec.get("count", 1))
    xs = []
    for _ in range(n):
        for _try in range(20):
            xc = rg.randint(r["ix0"] + 5, max(r["ix0"] + 5, r["ix1"] - 5))
            if all(abs(xc - o) >= 8 for o in xs):
                xs.append(xc)
                break
    for xc in xs:
        w = rg.randint(*spec.get("width", [2, 3]))
        x = xc
        for z in range(r["iz0"], r["iz1"] + 1):
            if rg.random() < 0.25:
                x += rg.choice((-1, 1))
            x = min(max(x, r["ix0"] + 3), r["ix1"] - 3 - w)
            for xx in range(x, x + w):
                water.add((xx, z))
    for _ in range(int(spec.get("pools", 0))):
        pw, ph = rg.randint(*spec.get("pool_size", [4, 7])), rg.randint(*spec.get("pool_size", [4, 7]))
        px = rg.randint(r["ix0"] + 4, max(r["ix0"] + 4, r["ix1"] - pw - 4))
        pz = rg.randint(r["iz0"] + 1, max(r["iz0"] + 1, r["iz1"] - ph - 1))
        for xx in range(px, px + pw):
            for zz in range(pz, pz + ph):
                if (xx - px) in (0, pw - 1) and (zz - pz) in (0, ph - 1):
                    continue
                water.add((xx, zz))
    cells = sorted(c for c in water if _water_ok(ctx, c[0], fy, c[1]))
    for (x, z) in cells:
        ctx.add(setb((x, y - 1, z), bed))
        ctx.add(setb((x, y, z), "minecraft:water"))
    ctx.built.meta["extra_drop"] = max(ctx.built.meta.get("extra_drop", 0), 1)
    got = set(cells)
    for (x, z) in cells:
        roll = rg.random()
        acc = 0.0
        for pl in spec.get("plants", []):
            acc += pl["p"]
            if roll < acc:
                ctx.add(setb((x, y, z), pl["block"]))
                if "sea_pickle" in pl["block"]:
                    ctx.lights.append((x, y, z))
                break


def dress_columns(ctx, spec):
    r = ctx.room
    rg = ctx.rng
    cells = [c for c in _cells(ctx) if _free(ctx, c[0], c[2]) and r["ix0"] + 2 <= c[0] <= r["ix1"] - 2]
    rg.shuffle(cells)
    area = len(cells)
    want = int(area * spec.get("density", 0.02))
    placed = []
    top = r["ceil_y"] - 1
    for (x, y, z) in cells:
        if len(placed) >= want:
            break
        if any(max(abs(x - px), abs(z - pz)) < 4 for px, pz in placed) or not _air_col(ctx, x, y, top, z):
            continue
        t = 2 if rg.random() < spec.get("thick_p", 0.3) else 1
        if t == 2 and not all(_free(ctx, x + a, z + b) and _air_col(ctx, x + a, y, top, z + b) for a in (0, 1) for b in (0, 1)):
            t = 1
        h = top if rg.random() >= spec.get("broken_p", 0.5) else y + rg.randint(1, max(1, r["height"] - 3))
        ctx.add(fill((x, y, z, x + t - 1, min(h, top), z + t - 1), spec["block"]))
        placed.append((x, z))
        if spec.get("cap") and h >= top:
            ctx.add(fill((x, top, z, x + t - 1, top, z + t - 1), spec["cap"]))
        elif rg.random() < spec.get("fallen_p", 0.5):
            ln = rg.randint(3, 5)
            fx = x + t + rg.randint(0, 2)
            if all(ctx.air(fx + k, y, z) and _free(ctx, fx + k, z) for k in range(ln)) and fx + ln < r["ix1"] - 2:
                ctx.add(fill((fx, y, z, fx + ln - 1, y, z), spec["block"]))


def dress_piles(ctx, spec):
    r = ctx.room
    rg = ctx.rng
    cells = [c for c in _cells(ctx) if _free(ctx, c[0], c[2]) and r["ix0"] + 3 <= c[0] <= r["ix1"] - 4]
    rg.shuffle(cells)
    want = int(len(cells) * spec.get("density", 0.015))
    n = 0
    for (x, y, z) in cells:
        if n >= want:
            break
        w, h = rg.randint(2, 3), 2
        if not all(ctx.air(x + a, y, z + b) and _free(ctx, x + a, z + b) for a in range(w) for b in range(h)):
            continue
        ctx.add(fill((x, y, z, x + w - 1, y, z + h - 1), pick(rg, spec["blocks"])))
        n += 1


# ------------------------------------------------------------------------------------------------- registration


def dress_glow_vines(ctx, spec):
    """Glow berries hanging from the canopy to a few blocks over the floor (DG-JUNGLE, 2026-10-09): the light a TALL room
    needs, since the hull's ceiling lattice cannot reach a floor more than about 12 below it (lattice_spacing). Only in
    rooms whose clear height over their lowest floor is at least `min_height`; a lattice `every` apart, each column
    moved up to two cells off a trunk or column or an anchor's keep, from the first air under the leaves down to
    `clear` blocks over the floor, so the player walks under every tip. Cave vines have no collision (dungeon_grid
    PASSABLE). Each lit cell (berries=true) is a light of 14, not 15, so the spacing is reckoned at 14."""
    r = ctx.room
    clear = int(spec.get("clear", 4))
    lowest = min(r["floors"]) if not r["pit"] else min(r["floor_in"], r["floor_out"])
    if r["ceil_y"] - lowest < int(spec.get("min_height", 11)):
        return
    every = int(spec.get("every", 7))
    tip, body = spec["tip"], spec["body"]
    unlit = spec.get("body_unlit", body)
    top = r["ceil_y"] - 1
    for x0 in R._spread(r["ix0"] + 1, r["ix1"] - 1, every):
        for z0 in R._spread(r["iz0"] + 1, r["iz1"] - 1, every):
            for dx, dz in sorted(((a, b) for a in range(-2, 3) for b in range(-2, 3)), key=lambda t: abs(t[0]) + abs(t[1])):
                x, z = x0 + dx, z0 + dz
                if not (r["ix0"] <= x <= r["ix1"] and r["iz0"] <= z <= r["iz1"]) or (x, z) in ctx.keep:
                    continue
                y_tip = R.floor_at(r, x) + clear
                y = top
                while y > y_tip and not ctx.air(x, y, z):
                    y -= 1
                if y <= y_tip or ctx.air(x, y + 1, z):
                    continue        # no leaf, log or ceiling to hang from, or nothing to hang
                if not _air_col(ctx, x, y_tip, y, z):
                    continue
                for k, yy in enumerate(range(y, y_tip - 1, -1)):
                    lit = yy == y_tip or k % 2 == 0
                    ctx.add(setb((x, yy, z), tip if yy == y_tip else (body if lit else unlit)))
                    if lit:
                        ctx.lights.append((x, yy, z))
                break


R.register("drift", kind_drift, dress="full", rise=True, connector=True)
R.register("stairs", kind_drift, dress="light", rise=True, connector=True)
R.register("entry_room", kind_entry, dress="light")
R.register("exit_room", kind_exit, dress="light")
R.register("boss_arena", kind_arena, dress="light")
R.register("maze", kind_maze, dress="light", length_snap=(4, 3), width_snap=(4, 1))
R.register("parkour", kind_parkour, dress="none", pit=6, no_deploy=True, jumps=True)
R.register("collapse_bridge", kind_bridge, dress="none", pit=6)
R.register("resources", kind_resources, dress="light")
R.register("dark_room", kind_dark, dress="full", dark=True)
R.register("safe_room", kind_safe, dress="light")

R.register_dress("base_course", dress_base_course, "light")
R.register_dress("pillars", dress_pillars, "light")
R.register_dress("timber", dress_timber, "light")
R.register_dress("streak", dress_streak, "light")
R.register_dress("floor_strip", dress_floor_strip, "light")
R.register_dress("floor_patches", dress_floor_patches, "light")
R.register_dress("ground_cover", dress_ground_cover, "light")
R.register_dress("trunks", dress_trunks, "full")
R.register_dress("canopy", dress_canopy, "light")
R.register_dress("wall_vines", dress_wall_vines, "light")
R.register_dress("stream", dress_stream, "light")
R.register_dress("columns", dress_columns, "full")
R.register_dress("piles", dress_piles, "full")
R.register_dress("glow_vines", dress_glow_vines, "light")

R.EXTRA_CHECKS.extend([check_maze, check_parkour, check_bridge])
