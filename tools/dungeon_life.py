#!/usr/bin/env python
"""LIFE: what lives in a dungeon room, and what it tells (pass 2, unit LIFE, 2026-10-10).

The owner, playing the first full-length dungeons: "It feels arbitrarily long right now. A lot of the sequences are
good, we just need more life in each room." This module is that, in three layers, each per THEME (data/dungeon_themes.json
key `life`) and each a dress op of the room kit (tools/dungeon_rooms.py register_dress), so it builds into every slot
with the shell and needs nothing the kit does not already give a kind. Mechanism rung: datapack plus generator; nothing
needed a mod or a scripting layer.

  1. AMBIENT POKEMON (`life` op, last in a theme's dress list). Wild Pokemon that live in the room: spawned on the
     member's first pass into it, wandering, NOT a fight and NOT a clear condition. They are spawned by the
     `spawnpokemonat` MACRO and bound at once, exactly as the fight rooms' wild Pokemon are (tools/dungeon_fights.py:
     the macro, then the nearest unclaimed Pokemon within 2.5 blocks of the spot gets the claim; a plain `summon
     cobblemon:pokemon` is refused, .claude/rules/datapacks.md). The claim (`life/s<g>/bind`) is the fight rooms' own:
     the sweep's keep tag, the slot's tag, the blackout's exempt tag, the run id, PersistenceRequired; plus `dg.lf` and
     the room's index in `dg.rs` (an entity holds it, as the fight Pokemon hold the run id). They are `uncatchable`
     (D8: catches only after the Champion; a catchable ambient Pokemon would be a held catch, DUNGEON_CATCHES.md, an
     owner decision), below the band's LOWER cap, and an evolution line is chosen by band (stage 0 at bands 1-2 ...).
     Two variants per room are generated and one is chosen by the member's run id (an even run, an odd run), so a second run meets other animals.
     Cleanup: the room's reset discards its own; the slot's free and tend discard everything tagged `dg.s<g>` (the same
     lines tools/dungeon_fights.py patch_functions writes, written again here so a slot with no wild room is covered);
     a member entering room i discards the life of rooms i-3 and earlier (a 26-room run would otherwise carry 50
     wandering Pokemon). Rooms that already have wild Pokemon, trainers or a drop (nest, habitat, miniboss, stand,
     gauntlet, boss, parkour, bridge, set pieces, the entry and exit) get none: ambient life must never be mistaken for
     the room's fight.
  2. SET DRESSING THAT TELLS WHAT HAPPENED (`life_scenes` op, after `stream` in a theme's dress list and before the
     obstacle ops, so they work round it: the footprint and a one-block margin go into `ctx.trail`, which they respect). A scene is a small ASCII
     map of cells, each a stack of ROLES (bedroll, crate, lamp, rubble, beam, bone, skull, candle, note ...) the theme
     resolves to blocks: a camp with a cold fire pit, a cave-in with a fallen beam and bones, a nest of bones, a shrine
     with candles, a fallen log, a stack of crates, a waxed sign (a note). Rotated and mirrored by the room's rng,
     seated on standable cells off the trail/reserve/keep cells (`DressCtx.reserved`) and on flat enough ground, and a
     scene is accepted ONLY IF the walk check's own BFS still reaches every cell and every point anchor it reached before
     (a scene that would cut a room is dropped, not built).
  3. SOUND, PARTICLES, LIGHT. `life` also writes the room's `tick` (each keeper pass the member is in the room): a
     sound at a scene or the far side of the room now and then, a particle puff at a scene; and CANDLES: a scene's
     candle is placed UNLIT in the shell and set lit when the member enters (the light only ever goes UP: no light is
     taken from a room), restored by the room's reset. A dark_room keeps its darkness: no lamp, no candle.

Interface (what tools/dungeon.py build() calls): `functions(doc)` -> {name: lines} (the table `life/load` and, per slot,
the walker go/pick/loop/mon/at and the claim bind), `load_entries(doc)` (the table's function id for load.json),
`patch_functions(doc, fns)` (free and tend discard), `problems(doc, d, slot)` (registered in R.EXTRA_CHECKS), `report(doc)`.
THE ANIMALS ARE DATA: a spawn and a claim per animal per band per variant in each room's `enter` was 11,664 commands and put
the keeper's static chain at 90,136 against 29,332 (limit 65,536); the table is in command storage and a room's `enter` is
two lines (docs/mechanics/DUNGEON_LIFE.md 2.1). A built room carries `meta["life"]`. Hook order: the life lines are PREPENDED to the room's `enter`,
`tick` and `reset` (a kind's tick often starts with `return 0` on its own state, which would swallow lines after it).

UNPROVEN IN GAME (docs/mechanics/DUNGEON_LIFE.md): that the macro-spawned, bound Pokemon wander inside the room and
stay inside a loaded box (the nest's tp-back is not used here), that `uncatchable` Pokemon accept a player's battle
request (a player may fight one; nothing in the run depends on it), the entity-score read `scores={dg.rs=..N}` on a
Pokemon, a candle's `lit` set by setblock, a waxed sign's SNBT, and the sounds' loudness.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_grid as G  # noqa: E402
import dungeon_rooms as R  # noqa: E402
from dungeon_rooms import setb  # noqa: E402

STORE = "cobblers:dungeons"          # command storage: life.s<g>.r<i>v<v>b<band> (the table), life.arg, life.cur
TAG_LIFE = "dg.lf"
OBJ_ROOM = "dg.rs"                 # on a life Pokemon: the index of its room (the prune reads it)
VARIANTS = 2                       # animals rolled per run: this many precomputed sets per room
PRUNE_BEHIND = 3                   # entering room i discards the life of rooms i - PRUNE_BEHIND and earlier
BIND_RADIUS = 2.5                  # the spawned Pokemon is the nearest unclaimed one this close to its spot
DOOR_CLEAR = 10                    # spawn this far (horizontally) from the door the member comes in by, where the room allows
SPECIES = re.compile(r"[a-z0-9_-]+")
KINDS_NO_AMBIENT = {"entry_room", "exit_room", "boss_arena", "nest", "habitat", "miniboss", "stand", "gauntlet", "ambush",
                    "parkour", "collapse_bridge", "setpiece"}
KINDS_NO_SCENES = {"entry_room", "exit_room", "boss_arena", "parkour", "collapse_bridge", "setpiece"}
SCENE_ATTEMPTS = 70
MARGIN = (-1, 0, 1)                     # cells kept clear of trunks and cover round a scene (it is in ctx.trail)
LIGHT_ROLES = ("lamp", "candle")   # roles that give light: skipped in a dark room
MAX_DY_LOW, TALL_ROOM = 1, 8       # scene stacks reach dy 1 in a room up to 8 high, dy 0 in a taller one
NOTE_LINE_MAX = 15                # a sign line is 15 characters of the default font before it clips

# ------------------------------------------------------------------------------------------------- scene shapes
#
# rows are z (north to south), columns are x. A legend value is the stack at that cell: [(dy, role), ...]; dy -1 REPLACES
# the floor tile under the cell, dy 0 is the cell the player would stand in, dy 1+ stacks above it. `.` is untouched.
# A role the theme does not give is skipped (a theme can leave the beam or the skull out). `{axis}` in a block is
# x or z by the rotation; `{rot}` a random skull/sign rotation 0..15; `{note}` the sign's text.

SCENES = {
    "camp": {"rows": ["bb.sss", "bb.sFs", "CL...."],
             "legend": {"b": [(0, "bedroll")], "s": [(0, "ring")], "F": [(-1, "scorch")], "C": [(0, "crate")],
                        "L": [(0, "crate"), (1, "lamp")]},
             "why": "a camp: a bedroll, a barrel with a lantern, a cold fire pit with its stones round it (open on one side)"},
    "cave_in": {"rows": [".rrrr..", "orRRRrk", "rRRTRBB", "orRRRr.", ".rrrr.."],
                "legend": {"r": [(0, "rubble")], "R": [(0, "rubble"), (1, "rubble")],
                           "T": [(0, "rubble"), (1, "rubble"), (2, "rubble")], "B": [(0, "beam")],
                           "o": [(0, "bone")], "k": [(0, "skull")]},
                "why": "a heap of what came down, a beam laid across it and bones at its foot"},
    "bones": {"rows": [".o.b.", "bBBBo", ".BkB.", "ob.bo"],
              "legend": {"o": [(0, "bone")], "b": [(0, "bone")], "B": [(-1, "nest"), (0, "bone"), (1, "bone")],
                         "k": [(-1, "nest"), (0, "bone"), (1, "skull")]},
              "why": "a nest of bones: something large slept here, and ate"},
    "crates": {"rows": ["CCc.", "cC.C"],
               "legend": {"C": [(0, "crate")], "c": [(0, "crate"), (1, "crate")]},
               "why": "a stack of crates against a wall"},
    "idol": {"rows": ["c.c", ".P.", "c.c"],
             "legend": {"P": [(0, "plinth"), (1, "pillar"), (2, "pillar"), (3, "cap")], "c": [(0, "candle")]},
             "why": "a small shrine: a pillar on a plinth, four candles (they catch when the member walks in)"},
    "fallen": {"rows": ["LLLLL", "m.m.m"],
               "legend": {"L": [(0, "log")], "m": [(0, "cover")]},
               "why": "a fallen log (or column) with moss over it"},
    "note": {"rows": ["N"],
             "legend": {"N": [(0, "note")]},
             "why": "a waxed sign standing in the floor: a line or two of what somebody left"},
}
# footprints this big are not placed in a LIGHT-dressed room (a connector's walls are close)
SMALL_SCENES = {"crates", "note", "bones", "idol", "fallen"}


# ------------------------------------------------------------------------------------------------- helpers


def cfg_of(theme):
    return theme.get("life") or {}


def kind_ok(spec, kind):
    if kind in spec.get("not_kinds", []):
        return False
    return "kinds" not in spec or kind in spec["kinds"]


def pick(rg, entries):
    """One block of a role: a string, or a weighted list [{"block", "w"}]."""
    if isinstance(entries, str):
        return entries
    total = sum(e.get("w", 1) for e in entries)
    roll = rg.random() * total
    acc = 0.0
    for e in entries:
        acc += e.get("w", 1)
        if roll < acc:
            return e["block"]
    return entries[-1]["block"]


def weighted_unique(rg, specs, n):
    pool = list(specs)
    out = []
    while pool and len(out) < n:
        total = sum(s.get("weight", s.get("w", 1)) for s in pool)
        roll = rg.random() * total
        acc = 0.0
        for s in pool:
            acc += s.get("weight", s.get("w", 1))
            if roll < acc:
                out.append(s)
                pool.remove(s)
                break
    return out


def rotate(cells, r, mirror):
    """cells {(dx, dz): stack} rotated r quarter turns (and mirrored in x first), shifted so the minimum is 0."""
    out = {}
    for (dx, dz), v in cells.items():
        if mirror:
            dx = -dx
        for _ in range(r):
            dx, dz = -dz, dx
        out[(dx, dz)] = v
    mx = min(k[0] for k in out)
    mz = min(k[1] for k in out)
    return {(k[0] - mx, k[1] - mz): v for k, v in out.items()}


def scene_cells(name):
    sc = SCENES[name]
    out = {}
    for dz, row in enumerate(sc["rows"]):
        for dx, ch in enumerate(row):
            if ch in sc["legend"]:
                out[(dx, dz)] = sc["legend"][ch]
    return out


def sign_block(base, rot, lines):
    msgs = ",".join("'%s'" % json.dumps({"text": t}, ensure_ascii=False) for t in (list(lines) + [""] * 4)[:4])
    return "%s[rotation=%d]{is_waxed:1b,front_text:{messages:[%s]}}" % (base, rot, msgs)


def stage_of(band, n):
    """The evolution stage of a line n long at a band (1..6): stage 0 first, the last stage at the top bands."""
    return min(n - 1, ((band - 1) * n) // 6)


def level_of(doc, band_entry, off):
    lo = min(band_entry["caps"])
    lv = max(1, lo - off)
    if band_entry["band"] == 6:
        lv = max(lv, doc["engine"]["stands"]["band6_levels"][0])
    return lv


def feet_ok(block):
    """A feet or head cell a scene may overwrite: air or a plant-like block, never a control or a light."""
    if G.classify(block) != G.PASS:
        return False
    return not re.search(r"lever|button|plate|torch|candle|sign|lantern|light$", G.base(block))


# ------------------------------------------------------------------------------------------------- the walk

def starts_of(ctx):
    room = ctx.room
    pts = []
    if hasattr(R, "room_start"):
        pts.append(tuple(R.room_start(room)))
    for name in ("door_in_at", "door_out_at"):
        a = ctx.built.anchors.get(name)
        if a:
            pts.append((int(a[0]), int(a[1]), int(a[2])))
    return [ctx.grid.local(*p) for p in pts if ctx.grid.inside(*p)]


def reach_of(ctx):
    fl = R.flags_of(ctx.room["kind"])
    return G.walk(ctx.grid, starts_of(ctx), jumps=fl["jumps"])


def anchor_cells(ctx):
    out = []
    for name, v in ctx.built.anchors.items():
        if name in R.BOX_ANCHORS or name in R.NO_STAND:
            continue
        for p in R._point_list(v):
            out.append((name, int(p[0]), int(p[1]), int(p[2])))
    return out


def anchors_ok(ctx, reach):
    g = ctx.grid
    out = set()
    for name, x, y, z in anchor_cells(ctx):
        if any(g.inside(x, y - k, z) and g.local(x, y - k, z) in reach for k in (0, 1, 2)):
            out.add((name, x, y, z))
    return out


def snapshot(grid):
    return grid.a.copy(), list(grid.pal), dict(grid.idx), list(grid.codes)


def restore(grid, snap):
    grid.a, grid.pal, grid.idx, grid.codes = snap[0], snap[1], snap[2], snap[3]


# ------------------------------------------------------------------------------------------------- scenes


def floor_light_zone(ctx):
    """The cells round the floor-light lattice of a TALL room (tools/dungeon_rooms.py floor_lights: a theme with
    hull.tall_lights lights a room too tall for its ceiling from light blocks set into the floor course, each moved to
    the nearest open cell within 2). A scene on those cells takes the light away: the walk check then finds standable
    cells at light 0. The lattice is recomputed here from the kit's own helpers; if the kit changes it, the walk check
    names the rooms, as it did on 2026-10-10 (3 rooms before this zone)."""
    t = ctx.theme["hull"]
    tall = t.get("tall_lights")
    room = ctx.room
    if not tall or not hasattr(R, "_spread"):
        return set()
    ref_y = ctx.built.meta.get("light_ref_y", min(room["floor_in"], room["floor_out"]))
    pen = t.get("light_penalty", 0)
    if not 15 - t["min_light"] - (room["ceil_y"] - ref_y) - pen < tall.get("under", 3):
        return set()
    step = int(max(3, min(tall.get("every", t["light_every"]), 15 - t["min_light"] - 1 - pen)))
    xs = R._spread(room["ix0"], room["ix1"], step)
    zs = R._spread(room["iz0"], room["iz1"], step)
    return {(x + a, z + b) for x in xs for z in zs for a in (-2, -1, 0, 1, 2) for b in (-2, -1, 0, 1, 2)}


def role_block(rg, roles, role, rot_axis):
    ent = roles.get(role)
    if ent is None:
        return None
    b = pick(rg, ent)
    return b.replace("{axis}", rot_axis).replace("{rot}", str(rg.randint(0, 15)))


def dress_life_scenes(ctx, spec):
    room, theme = ctx.room, ctx.theme
    cfg = cfg_of(theme).get("scenes")
    kind = room["kind"]
    if not cfg or kind in KINDS_NO_SCENES or ctx.level < 1:
        ctx.built.meta.setdefault("life", {})["scenes"] = []
        return
    light_only = ctx.level < R.LEVELS["full"]
    rg = ctx.rng
    listed = [s for s in cfg["list"] if kind_ok(s, kind) and s["scene"] in SCENES
              and not (light_only and s["scene"] not in SMALL_SCENES)]
    life = ctx.built.meta.setdefault("life", {})
    life["scenes"] = []
    if not listed:
        return
    area = (room["ix1"] - room["ix0"] + 1) * (room["iz1"] - room["iz0"] + 1)
    want = min(int(cfg.get("max", 3)), max(1, round(area / float(cfg.get("area_per", 900)))))
    if light_only:
        want = 1
    cells = ctx.standable_cells()
    by_col = {}
    for x, y, z in cells:
        by_col.setdefault((x, z), []).append(y)
    reach0 = reach_of(ctx)
    anc0 = anchors_ok(ctx, reach0)
    chosen_names = []
    for _ in range(want):
        spec_ = weighted_unique(rg, [s for s in listed if s["scene"] not in chosen_names or s.get("repeat")], 1)
        if not spec_:
            break
        sc = spec_[0]
        placed = _place(ctx, sc, cells, by_col, rg, reach0, anc0, light_only)
        if placed:
            life["scenes"].append(placed)
            chosen_names.append(sc["scene"])
            reach0 = reach_of(ctx)
            anc0 = anchors_ok(ctx, reach0)
            cells = ctx.standable_cells()
            by_col = {}
            for x, y, z in cells:
                by_col.setdefault((x, z), []).append(y)


def _place(ctx, sc, cells, by_col, rg, reach0, anc0, light_only):
    room, theme = ctx.room, ctx.theme
    name = sc["scene"]
    roles = sc["roles"]
    dark = R.flags_of(room["kind"])["dark"]
    # a stack is cut at MAX_DY: the light check counts every standable cell, the top of a 3-high heap included, and a tall
    # room is lit from its floor; a scene is a spread of single layers there and at most two high in a low room
    max_dy = MAX_DY_LOW if room["height"] <= TALL_ROOM else 0
    base = {k: [(dy, r) for dy, r in st if dy <= max_dy] for k, st in scene_cells(name).items()}
    base = {k: st for k, st in base.items() if st}
    notes = cfg_of(theme).get("notes") or []
    if name == "note" and not notes:
        return None
    g = ctx.grid
    zone = floor_light_zone(ctx)
    for attempt in range(SCENE_ATTEMPTS):
        x0, y0, z0 = rg.choice(cells)
        rot, mirror = rg.randint(0, 3), rg.random() < 0.5
        shape = rotate(base, rot, mirror)
        axis = "x" if rot % 2 == 0 else "z"
        foot = {}
        ok = True
        for (dx, dz), stack in shape.items():
            c = (x0 + dx, z0 + dz)
            ys = by_col.get(c)
            if not ys or ctx.reserved(*c) or c in zone:
                ok = False
                break
            y = min(ys, key=lambda v: abs(v - y0))
            if abs(y - y0) > 1:
                ok = False
                break
            top = max(dy for dy, _r in stack)
            if not all(feet_ok(g.block_at(c[0], y + k, c[1])) for k in range(0, max(top, 0) + 2)):
                ok = False
                break
            foot[c] = y
        if not ok:
            continue
        # no two scenes touch (the margin of an earlier one is in ctx.keep already, so reserved() covered it)
        # a scene sits against a wall: one footprint cell has a solid neighbour column outside the footprint
        hug = any(g.inside(c[0] + a, y, c[1] + b) and (c[0] + a, c[1] + b) not in foot
                  and G.classify(g.block_at(c[0] + a, y, c[1] + b)) == G.SOLID
                  for c, y in foot.items() for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if (light_only or sc.get("hug")) and not hug:
            continue
        if not hug and attempt < SCENE_ATTEMPTS // 2:
            continue
        rgs = R.rng(ctx.d, room, "life:scene:%s:%d" % (name, (x0 - room["ix0"]) * 1000 + (z0 - room["iz0"])))
        ops, candles, notes_used = [], [], None
        for (dx, dz), stack in shape.items():
            c = (x0 + dx, z0 + dz)
            y = foot[c]
            for dy, role in stack:
                if dark and role in LIGHT_ROLES:
                    continue
                blk = role_block(rgs, roles, role, axis)
                if blk is None:
                    continue
                if role == "note":
                    notes_used = rgs.choice(notes)
                    blk = sign_block(blk.split("[")[0], rgs.randint(0, 15), notes_used)
                if role == "candle":
                    candles.append([c[0], y + dy, c[1], blk, blk.replace("lit=false", "lit=true")])
                ops.append(setb((c[0], y + dy, c[1]), blk))
        if not ops:
            return None
        snap = snapshot(g)
        for op in ops:
            g.apply(op)
        reach1 = reach_of(ctx)
        lost = [k for k in reach0 if k not in reach1 and (k[0] + g.box[0], k[2] + g.box[2]) not in foot]
        anc1 = anchors_ok(ctx, reach1)
        if lost or not anc0 <= anc1:
            restore(g, snap)
            continue
        ctx.built.ops.extend(ops)
        for c in foot:
            for a in MARGIN:
                for b in MARGIN:
                    ctx.trail.add((c[0] + a, c[1] + b))     # NOT ctx.keep: the glow vines skip keep cells and would leave the scene dark
        return {"scene": name, "at": [x0, foot[(x0, z0)] if (x0, z0) in foot else y0, z0],
                "cells": sorted([c[0], c[1]] for c in foot), "candles": candles, "note": notes_used,
                "blocks": len(ops)}
    return None


# ------------------------------------------------------------------------------------------------- ambient Pokemon


def spots_of(ctx, reach):
    """Standable, reachable, dry cells of the room, off its doors: [(x, y, z)]."""
    g = ctx.grid
    room = ctx.room
    din = ctx.built.anchors.get("door_in_at")
    out = []
    for x, y, z in ctx.standable_cells():
        if g.local(x, y, z) not in reach:
            continue
        b = g.block_at(x, y, z)
        if G.classify(b) == G.WATER or not feet_ok(b):
            continue
        out.append((x, y, z))
    if din:
        far = [c for c in out if (c[0] - din[0]) ** 2 + (c[2] - din[2]) ** 2 >= DOOR_CLEAR ** 2]
        if len(far) >= 6:
            out = far
    return out


def _spread(rg, cells, n, mode, near=None):
    if not cells:
        return []
    pool = list(cells)
    if near:
        close = [c for c in pool if (c[0] - near[0]) ** 2 + (c[2] - near[2]) ** 2 <= 25]
        pool = close or pool
    first = rg.choice(pool)
    picked = [first]
    for _ in range(n - 1):
        best = None
        for _t in range(60):
            c = rg.choice(pool)
            d2 = min((c[0] - p[0]) ** 2 + (c[2] - p[2]) ** 2 for p in picked)
            if mode == "cluster":
                if 2 <= d2 <= 16:
                    best = c
                    break
            elif d2 >= 25:
                best = c
                break
        if best is None:
            best = rg.choice(pool)
            if any(best == p for p in picked):
                continue
        picked.append(best)
    return picked


def plan_ambient(ctx, cfg, reach):
    room = ctx.room
    kind = room["kind"]
    if kind in KINDS_NO_AMBIENT or ctx.level < 1:
        return []
    amb = cfg.get("ambient") or {}
    groups = [g for g in amb.get("groups", []) if kind_ok(g, kind)]
    if not groups:
        return []
    doc = ctx.doc
    bands = doc["engine"]["bands"]
    spots = spots_of(ctx, reach)
    if len(spots) < 4:
        return []
    off_trail = [c for c in spots if (c[0], c[2]) not in ctx.trail]
    variants = []
    for v in range(VARIANTS):
        rg = R.rng(ctx.d, room, "life:ambient:%d" % v)
        n_groups = rg.randint(*amb.get("per_room", [1, 2]))
        mons = []
        for gp in weighted_unique(rg, groups, n_groups):
            line = rg.choice(gp["lines"])
            n = rg.randint(*gp["count"])
            pool = off_trail if (len(off_trail) >= 4 and not gp.get("on_trail")) else spots
            near = None
            if gp.get("near"):
                a = ctx.built.anchors.get(gp["near"])
                if a:
                    near = a if isinstance(a[0], (int, float)) else a[0]
            for (x, y, z) in _spread(rg, pool, n, gp.get("mode", "scatter"), near):
                off = rg.randint(*gp.get("below", [4, 9]))
                by_band = {}
                for b in bands:
                    sp = line[stage_of(b["band"], len(line))]
                    lv = level_of(doc, b, off)
                    props = "level=%d uncatchable" % lv + (" no_ai" if gp.get("sleep") else "")
                    by_band[b["band"]] = {"species": sp, "level": lv, "props": props}
                mons.append({"group": gp["id"], "pos": [x, y, z], "yaw": rg.choice((0, 90, 180, -90)), "bands": by_band})
        variants.append(mons)
    return variants


def pos_of_scene_or_center(ctx, rg):
    pts = []
    for s in ctx.built.meta.get("life", {}).get("scenes", []):
        pts.append(tuple(s["at"]))
    c = ctx.built.anchors.get("center")
    if c:
        pts.append((int(c[0]), int(c[1]), int(c[2])))
    return rg.choice(pts) if pts else None


def ambience_lines(ctx, cfg):
    """The tick's sound and particle lines for this room, at a scene or the room's centre. A sound fires on the member's
    own clock digits (dg.s1 = a digit, dg.s10 inside a range), so it needs no `random` (a room's own rolls stay its own):
    once a minute-sixth, a digit chosen per room and entry, on as many sixths of a minute as `every` seconds asks for
    (every 10 s = all six, 20 s = three, 60 s = one). A particle puff runs every pass while the member is within 24."""
    import dungeon as DG
    room = ctx.room
    kind = room["kind"]
    rg = R.rng(ctx.d, room, "life:ambience")
    lines = []
    for k, e in enumerate(cfg.get("ambience", [])):
        if not kind_ok(e, kind):
            continue
        p = pos_of_scene_or_center(ctx, rg)
        if p is None:
            continue
        x, y, z = p
        if e.get("sound"):
            width = max(1, min(6, round(60.0 / float(e.get("every", 10)))))
            digit = (room["i"] * 3 + k * 7) % 10
            lo = (room["i"] + k) % (7 - width)
            lines.append("execute if score @s %s matches %d if score @s %s matches %d..%d run playsound %s ambient @s %.1f %d %.1f %s %s"
                         % (DG.OBJ["s1"], digit, DG.OBJ["s10"], lo, lo + width - 1, e["sound"], x + 0.5, y, z + 0.5,
                            e.get("vol", 0.8), e.get("pitch", 1)))
        if e.get("particle"):
            d = e.get("delta", [1, 0.5, 1])
            lines.append("execute positioned %.1f %d %.1f if entity @s[distance=..24] run particle %s ~ ~%s ~ %s %s %s %s %d"
                         % (x + 0.5, y, z + 0.5, e["particle"], e.get("lift", 0.5), d[0], d[1], d[2], e.get("speed", 0.01),
                            int(e.get("count", 3))))
    return lines


def dress_life(ctx, spec):
    room, theme = ctx.room, ctx.theme
    cfg = cfg_of(theme)
    life = ctx.built.meta.setdefault("life", {})
    life.setdefault("scenes", [])
    if not cfg or ctx.level < 1:
        return
    kind = room["kind"]
    d, slot = ctx.d, ctx.slot
    g, i = slot["g"], room["i"]
    reach = reach_of(ctx)
    variants = plan_ambient(ctx, cfg, reach)
    life["variants"] = variants
    life["room"] = i
    dim = ctx.doc["engine"]["pocket"]["dimension"]
    enter, reset, tick = [], [], []
    enter.append("# life (tools/dungeon_life.py): the room's animals, the candles, the older rooms' animals gone")
    if i - PRUNE_BEHIND >= 0:
        enter.append("execute in %s as @e[type=cobblemon:pokemon,tag=dg.s%d,tag=%s,scores={%s=..%d}] run runmolang \"q.entity.discard;\""
                     % (dim, g, TAG_LIFE, OBJ_ROOM, i - PRUNE_BEHIND))
    if variants and any(variants):
        # the animals are DATA, not commands: the table is in storage (functions(): life/load), keyed r<room>v<variant>b<band>,
        # and one shared walker spawns what the key holds. A line per animal per band per variant per slot here would
        # be 11,664 commands and put the keeper's chain (static count, dungeon_independent_audit) over 65,536 with nothing
        # left for anyone else (measured 2026-10-10: 29,332 without, 90,136 with).
        enter.append("data modify storage %s life.arg set value %s" % (STORE, macro(room=str(i))))
        enter.append("function %s" % R.F("life/s%d/go" % g))
        reset.append("execute as @e[type=cobblemon:pokemon,tag=dg.s%d,tag=%s,scores={%s=%d}] run runmolang \"q.entity.discard;\""
                     % (g, TAG_LIFE, OBJ_ROOM, i))
    flame = cfg.get("candle_flame", "small_flame")
    sound = cfg.get("candle_sound", "item.flintandsteel.use")
    for sc in life["scenes"]:
        for cx, cy, cz, unlit, lit in sc["candles"]:
            enter.append("setblock %d %d %d %s" % (cx, cy, cz, lit))
            enter.append("particle %s %.1f %.1f %.1f 0.15 0.15 0.15 0.01 6" % (flame, cx + 0.5, cy + 0.4, cz + 0.5))
            reset.append("setblock %d %d %d %s" % (cx, cy, cz, unlit))
        if sc["candles"]:
            cx, cy, cz = sc["candles"][0][:3]
            enter.append("playsound %s ambient @s %.1f %d %.1f 0.7 1" % (sound, cx + 0.5, cy, cz + 0.5))
    tick += ambience_lines(ctx, cfg)
    life["lines"] = {"enter": len(enter), "tick": len(tick), "reset": len(reset)}
    f = ctx.built.functions
    if len(enter) > 1:
        f["enter"] = enter + f.get("enter", [])
    if tick:
        f["tick"] = tick + f.get("tick", [])
    if reset:
        f["reset"] = reset + f.get("reset", [])


def macro(**kw):
    return "{" + ",".join('%s:"%s"' % (k, v) for k, v in kw.items()) + "}"


# ------------------------------------------------------------------------------------------------- the pack


def life_rooms(doc):
    """[(dungeon, slot, built)] for every built room with ambient Pokemon."""
    import dungeon as DG
    out = []
    for slot in DG.slots(doc):
        d = slot["dungeon"]
        if not R.has_rooms(d):
            continue
        for b in R.slot_build(doc, d, slot):
            if (b.meta.get("life") or {}).get("variants") and any(b.meta["life"]["variants"]):
                out.append((d, slot, b))
    return out


def table_lines(doc):
    """The ambient Pokemon as DATA: one `data modify storage` line per (slot, room, variant, band), a list of the macro
    arguments of each animal. Keyed life.s<g>.r<room>v<variant>b<band>."""
    out = []
    bands = [b["band"] for b in doc["engine"]["bands"]]
    for _d, slot, b in life_rooms(doc):
        g, i = slot["g"], b.room["i"]
        for v, mons in enumerate(b.meta["life"]["variants"]):
            for bn in bands:
                recs = []
                for m in mons:
                    x, y, z = m["pos"]
                    e = m["bands"][bn]
                    recs.append(macro(x="%.1f" % (x + 0.5), y=str(y), z="%.1f" % (z + 0.5), species=e["species"],
                                      props=e["props"], room=str(i)))
                out.append("data modify storage %s life.s%d.r%dv%db%d set value [%s]" % (STORE, g, i, v, bn, ",".join(recs)))
    return out


def functions(doc):
    """{function name under cobblers:dungeons/: lines}: the table (life/load) and, per slot with life, the walker that
    spawns what a room's key holds (go, pick, loop, one) and the claim (bind)."""
    import dungeon as DG
    out = {}
    slots = sorted({s["g"] for _d, s, _b in life_rooms(doc)})
    if not slots:
        return out
    out["life/load"] = [DG.HEAD, "# The ambient Pokemon of every room, as data (tools/dungeon_life.py table_lines). Runs at every load, so a",
                        "# changed table ships with the pack and needs no re-apply step.",
                        "data modify storage %s life set value {}" % STORE,
                        "scoreboard players set #lf2 %s %d" % (DG.OBJ["t"], VARIANTS)] + table_lines(doc)
    exempt = DG.blackout_terms()["exempt"]
    keep = doc["engine"]["sweep"]["keep_tag"]
    dim = doc["engine"]["pocket"]["dimension"]
    band, run, TMP = DG.OBJ["band"], DG.OBJ["run"], DG.OBJ["t"]
    for g in slots:
        out["life/s%d/go" % g] = [
            DG.HEAD, "# As the member, a room of slot %d entered (life.arg.room is set by the room): which animals this run and band." % g,
            "# the band, and the variant from the member's run id (no `random`: a run alternates, and a room's own `random` rolls stay its own)",
            "scoreboard players operation #lf %s = @s %s" % (TMP, run),
            "scoreboard players operation #lf %s %%= #lf2 %s" % (TMP, TMP),
            "execute store result storage %s life.arg.b int 1 run scoreboard players get @s %s" % (STORE, band),
            "execute store result storage %s life.arg.v int 1 run scoreboard players get #lf %s" % (STORE, TMP),
            "function %s with storage %s life.arg" % (R.F("life/s%d/pick" % g), STORE),
            "function %s" % R.F("life/s%d/loop" % g)]
        out["life/s%d/pick" % g] = [
            DG.HEAD, "# (macro: room, v, b) the room's list for this variant and band, into life.cur",
            "$data modify storage %s life.cur set from storage %s life.s%d.r$(room)v$(v)b$(b)" % (STORE, STORE, g)]
        out["life/s%d/loop" % g] = [
            DG.HEAD, "# Spawn life.cur's animals one by one (each removed after its spawn); an empty list ends it",
            "execute unless data storage %s life.cur[0] run return 0" % STORE,
            "execute in %s run function %s with storage %s life.cur[0]" % (dim, R.F("life/s%d/mon" % g), STORE),
            "data remove storage %s life.cur[0]" % STORE,
            "function %s" % R.F("life/s%d/loop" % g)]
        out["life/s%d/mon" % g] = [
            DG.HEAD, "# (macro: x, y, z, species, props, room) in the pocket: the spawn through the macro helper `at`, and in the SAME function",
            "# the claim of the nearest unclaimed Pokemon within %g blocks of the spot, as the fight rooms do (V15: the exempt tag is" % BIND_RADIUS,
            "# added in the function that spawns, not a pass later)",
            "$function %s {x:\"$(x)\",y:\"$(y)\",z:\"$(z)\",species:\"$(species)\",props:\"$(props)\"}" % R.F("life/s%d/at" % g),
            "$execute positioned $(x) $(y) $(z) as @e[type=cobblemon:pokemon,tag=!%s,distance=..%g,sort=nearest,limit=1] run function %s {room:\"$(room)\"}"
            % (keep, BIND_RADIUS, R.F("life/s%d/bind" % g))]
        out["life/s%d/at" % g] = [
            DG.HEAD, "# (macro: x, y, z, species, props) the MACRO spawn (EXP-046: a plain `spawnpokemonat` parsed at boot does nothing)",
            "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
        out["life/s%d/bind" % g] = [
            DG.HEAD, "# As an ambient Pokemon a room of slot %d has just spawned (tools/dungeon_life.py): kept from the recall sweep, the" % g,
            "# slot's, the blackout's exempt tag (a dungeon Pokemon claims nothing: DUNGEONS.md 2.5), this run's, kept from the",
            "# despawner (EXP-041), and the room it lives in (dg.rs on the entity; the prune reads it)",
            "tag @s add %s" % keep, "tag @s add dg.s%d" % g, "tag @s add %s" % exempt, "tag @s add %s" % TAG_LIFE,
            "scoreboard players operation @s %s = #s%d %s" % (DG.OBJ["run"], g, DG.OBJ["run"]),
            "data merge entity @s {PersistenceRequired:1b}",
            "$scoreboard players set @s %s $(room)" % OBJ_ROOM]
    return out


def load_entries(doc):
    """Function ids appended to load.json after the engine's and the fights': the table."""
    return [R.F("life/load")] if life_rooms(doc) else []


def discard_lines(doc, g):
    """The slot's free and tend lines (the same text tools/dungeon_fights.py patch_functions writes)."""
    import dungeon as DG
    dim = doc["engine"]["pocket"]["dimension"]
    free = "execute in %s as @e[type=cobblemon:pokemon,tag=dg.s%d] run runmolang \"q.entity.discard;\"" % (dim, g)
    tend = ("execute in %s as @e[type=cobblemon:pokemon,tag=dg.s%d] unless score @s %s = #s%d %s run runmolang "
            "\"q.entity.discard;\"" % (dim, g, DG.OBJ["run"], g, DG.OBJ["run"]))
    return free, tend


def patch_functions(doc, fns):
    for g in sorted({s["g"] for _d, s, _b in life_rooms(doc)}):
        free, tend = discard_lines(doc, g)
        for name, line in (("slot/s%d/free" % g, free), ("slot/s%d/tend" % g, tend)):
            if line not in fns[name]:
                fns[name].append(line)


# ------------------------------------------------------------------------------------------------- the checks


def problems(doc, d, slot):
    """Life that cannot be right: a Pokemon spot that is not reachable or not standable, a level over the band's lower cap,
    a catchable one, an unknown species format, a scene candle that is not in the shell."""
    bad = []
    cfg_ok = True
    for b in R.slot_build(doc, d, slot):
        life = b.meta.get("life")
        if not life:
            continue
        r = b.room
        lab = "%s room %s (%s) life" % (d["id"], r["id"], r["kind"])
        g = b.grid
        fl = R.flags_of(r["kind"])
        start = g.local(*R.room_start(r))
        reach = G.walk(g, [start], jumps=fl["jumps"]) if hasattr(G, "walk") else set()
        for v, mons in enumerate(life.get("variants") or []):
            for m in mons:
                x, y, z = m["pos"]
                if not any(g.inside(x, y - k, z) and g.local(x, y - k, z) in reach for k in (0, 1)):
                    bad.append("%s: variant %d spot %s is not reachable from the door in" % (lab, v, m["pos"]))
                if G.classify(g.block_at(x, y, z)) == G.WATER:
                    bad.append("%s: variant %d spot %s is in water" % (lab, v, m["pos"]))
                if r["kind"] in KINDS_NO_AMBIENT:
                    bad.append("%s: ambient Pokemon in a %s room" % (lab, r["kind"]))
                for bn, e in m["bands"].items():
                    band = next(x_ for x_ in doc["engine"]["bands"] if x_["band"] == bn)
                    if not SPECIES.fullmatch(e["species"]):
                        bad.append("%s: species %r is not a lowercase species id" % (lab, e["species"]))
                    if e["level"] > min(band["caps"]) and bn != 6:
                        bad.append("%s: a %s at level %d over band %d's lower cap %d" % (lab, e["species"], e["level"], bn, min(band["caps"])))
                    if "uncatchable" not in e["props"].split():
                        bad.append("%s: an ambient %s is catchable (D8)" % (lab, e["species"]))
        for sc in life.get("scenes") or []:
            for cx, cy, cz, unlit, lit in sc["candles"]:
                if not g.inside(cx, cy, cz) or G.base(g.block_at(cx, cy, cz)) != G.base(unlit):
                    bad.append("%s: candle (%d, %d, %d) is not in the shell" % (lab, cx, cy, cz))
    return bad


def report(doc):
    import dungeon as DG
    lines = []
    for slot in DG.slots(doc):
        d = slot["dungeon"]
        if slot["k"] != 1 or not R.has_rooms(d):
            continue
        rooms = scn = mons = cand = 0
        for b in R.slot_build(doc, d, slot):
            life = b.meta.get("life") or {}
            v = life.get("variants") or []
            if any(v):
                rooms += 1
                mons += max(len(x) for x in v)
            scn += len(life.get("scenes") or [])
            cand += sum(len(s["candles"]) for s in life.get("scenes") or [])
        lines.append("%s: %d of %d rooms have animals (%d animal spots in a room's largest set, summed), %d scenes, %d candles"
                     % (d["id"], rooms, len(d["rooms"]), mons, scn, cand))
    return lines


def register():
    if __name__ != "dungeon_life":
        return       # a mutant copy exec'd by a test must not take the dress ops over
    R.register_dress("life_scenes", dress_life_scenes, "light")
    R.register_dress("life", dress_life, "light")
    if problems not in R.EXTRA_CHECKS:
        R.EXTRA_CHECKS.append(problems)


register()


def main(argv=None):
    import dungeon as DG
    doc = DG.load()
    print("\n".join(report(doc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
