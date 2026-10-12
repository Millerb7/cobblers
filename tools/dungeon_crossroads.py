#!/usr/bin/env python
"""Crossroads, looks and wings (dungeons pass 3, unit KIT3; DUNGEON_ROOMS.md 1b).

The owner, playing pass 2 (2026-10-10): "I see no diverging paths ... it didn't seem like I could go a different
direction ... the optional paths didn't feel immense." The Night Shift's fork left its host by two near-identical doors on
one wall and nothing signalled a choice.

Mechanism rung: datapack plus generator, inside the room kit (tools/dungeon_rooms.py). A look is blocks written by the
shell; a crossroads is a room kind; a wing is the kit's own `side` entry and a fork route marked optional. Nothing here
needs a scripting layer or a mod: the earlier rungs have no say over blocks in a custom dimension.

WHAT IT BUILDS
  * LOOKS. A fork route's `look` (a theme's `crossroads.looks.<id>`) restyles the door its first room is entered by, on
    BOTH sides, each room in its own wall column (the kit's rule: a room writes only inside its own box): the frame and
    lintel, light blocks set into a lit frame, the 3 x 3 approach's floor (`deck`), a one-deep wading trench over the
    approach's two inner rows for a `water` look (its bed one under the floor course, the stream's BED_UNDER), a window of
    the look's `window` block 2 wide and 2 high each side of the door (only where both rooms' walls meet there and no
    other door is near), and on the host's side a wall sign over the door with the route's `sign`.
  * CROSSROADS. A room kind (dress "light": no trunks or obstacles across the sightlines) with the anchor `hub`: where the
    chooser stands. Its checks: followed by a fork of 2-3 routes, each with a distinct look; no two exits on one wall
    closer than EXIT_GAP; from the hub's eye every exit's opening is in sight through the built grid.
  * WINGS. The checks only: a side entry of at most WING_MAX rooms, whose first room is not a box-only kind (it is
    entered through the host's side wall); a fork keeps one route that is not optional. The clock's exclusion of optional
    routes is tools/dungeon_clock.py clock_rooms.
  * PARKOUR, LONGER: sections at most PARKOUR_MAX_SECTIONS; `params.hard` (tools/dungeon_parkour.py reads it).

What it does NOT cover: whether a look reads as different in the game (the owner's look, unproven); a sign's text
rendering (the 1.21.1 block-entity form `front_text.messages` as JSON strings, read from the format, not run here).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_rooms as R  # noqa: E402
import dungeon_grid as G  # noqa: E402
from dungeon_rooms import fill, setb  # noqa: E402

MAX_ROUTES = 3
WING_MAX = 4
EXIT_GAP = 10            # two exits of one host on one wall: centre to centre at least this (frames, windows, a pier)
SIGN_LINE = 15
SIGN_LINES = 3
WINDOW_OFFS = (-4, -3, 3, 4)
PARKOUR_MAX_SECTIONS = 6
EYE = 1.62
FACING_INTO = {"west": "east", "east": "west", "north": "south", "south": "north"}   # a sign on a wall faces away from it


def looks_of(theme):
    return ((theme or {}).get("crossroads") or {}).get("looks") or {}


def _door_to(room, i, dir_):
    return next((x for x in room["doors"] if x["dir"] == dir_ and x["to"] == i), None)


def _along_range(room, side):
    return (room["iz0"], room["iz1"]) if side in ("east", "west") else (room["ix0"], room["ix1"])


def _inner(room, side, along, k=0):
    """The cell k in from `room`'s wall on `side` at `along` (x for a north/south wall, z for east/west)."""
    if side == "west":
        return (room["ix0"] + k, along)
    if side == "east":
        return (room["ix1"] - k, along)
    if side == "north":
        return (along, room["iz0"] + k)
    return (along, room["iz1"] - k)


def _windows(host, room, hd, din):
    """Along-wall positions for the windows of the door hd (host side) / din (route side): inside both rooms' walls,
    clear of every other door's opening and frames, both rooms open (an outline column, not rock) one cell in, with
    clear air at the window's two rows."""
    side, c, y = hd["side"], hd["c"], hd["y"]
    out = []
    for off in WINDOW_OFFS:
        p = c + off
        ok = True
        for rm, sd, own in ((host, side, hd), (room, R.OPP[side], din)):
            lo, hi = _along_range(rm, sd)
            if not lo <= p <= hi:
                ok = False
                break
            if any(x is not own and x["side"] == sd and abs(x["c"] - p) <= 2 for x in R.room_doors(rm)):
                ok = False
                break
            x, z = _inner(rm, sd, p)
            f = R.floor_xz(rm, x, z)
            if f is None or f > y + 1 or rm["ceil_y"] - 1 < y + 2:
                ok = False
                break
        if ok:
            out.append(p)
    return out


def layout_pass(doc, d, slot, rooms, items):
    """LAYOUT_FNS: every room's `optional` (a fork route marked so), and each route's look and sign on the door its first
    room is entered by, on both sides, with the windows both rooms will cut."""
    for i, it in enumerate(items):
        rooms[i]["optional"] = bool(it.get("optional"))
    for i, it in enumerate(items):
        if it.get("look") is None and it.get("sign") is None:
            continue
        room = rooms[i]
        din = next((x for x in room["doors"] if x["dir"] == "in"), None)
        if din is None:
            continue
        host = rooms[din["to"]]
        hd = _door_to(host, i, "out")
        if hd is None:
            continue
        for x in (hd, din):
            if it.get("look") is not None:
                x["look"] = it["look"]
        if it.get("sign") is not None:
            hd["sign"] = it["sign"]
        wins = _windows(host, room, hd, din) if it.get("look") is not None else []
        hd["windows"] = list(wins)
        din["windows"] = list(wins)


# ------------------------------------------------------------------------------------------------- the look's blocks


def _sign_lines(sign):
    if sign is None:
        return []
    return [sign] if isinstance(sign, str) else list(sign)


def sign_block(theme, side, lines):
    """A wall sign facing into the room from a wall on `side`, its front text the lines (1.21.1's block-entity form)."""
    base = (theme.get("crossroads") or {}).get("sign", "minecraft:oak_wall_sign")
    msgs = ["'%s'" % _json_str(t) for t in lines] + ["'\"\"'"] * (4 - len(lines))
    return "%s[facing=%s]{front_text:{messages:[%s]},is_waxed:1b}" % (base, FACING_INTO[side], ",".join(msgs))


def _json_str(t):
    return '"' + t.replace("\\", "\\\\").replace('"', '\\"').replace("'", "") + '"'


def look_ops(ctx):
    """POST_DRESS_FNS: the look of every door of this room that carries one (its own wall column and interior only)."""
    room, theme, grid = ctx.room, ctx.theme, ctx.grid
    looks = looks_of(theme)
    dark_kind = R.flags_of(room["kind"])["dark"]
    for door in R.room_doors(room):
        lk = looks.get(door.get("look")) if door.get("look") else None
        if lk is None and door.get("sign") is None:
            continue
        side, c, y = door["side"], door["c"], door["y"]
        w = R.wall_line(room, side)
        (x0, z0, x1, z1), frames, (lx0, lz0, lx1, lz1) = R._door_cols(room, door)
        if lk is not None:
            for fx, fz in frames:
                ctx.add(fill((fx, y, fz, fx, y + R.DOOR_H - 1, fz), lk["frame"]))
                if lk.get("lamp") and not dark_kind:
                    ctx.add(setb((fx, y + 2, fz), lk["lamp"]))
                    ctx.lights.append((fx, y + 2, fz))
            ctx.add(fill((lx0, y + R.DOOR_H, lz0, lx1, y + R.DOOR_H, lz1), lk["lintel"]))
            for p in door.get("windows") or []:
                if lk.get("window"):
                    a = (w, p) if side in ("east", "west") else (p, w)
                    for yy in (y + 1, y + 2):
                        if G.classify(grid.block_at(a[0], yy, a[1])) == G.SOLID:
                            ctx.add(setb((a[0], yy, a[1]), lk["window"]))
            _approach(ctx, door, lk)
        lines = _sign_lines(door.get("sign")) if door["dir"] == "out" else []
        if lines:
            sx, sz = _inner(room, side, c)
            if grid.inside(sx, y + R.DOOR_H, sz) and grid.block_at(sx, y + R.DOOR_H, sz) == "minecraft:air" \
                    and room["ceil_y"] - 1 >= y + R.DOOR_H:
                ctx.add(setb((sx, y + R.DOOR_H, sz), sign_block(theme, side, lines)))
                ctx.built.meta.setdefault("signs", []).append([sx, y + R.DOOR_H, sz, lines])


def _approach(ctx, door, lk):
    """The approach's deck, and a wading trench over its two inner rows for a water look. Only for a door at the room's
    floor there (a landing keeps its own steps) and only on cells whose floor is the door's."""
    room, grid = ctx.room, ctx.grid
    side, c, y = door["side"], door["c"], door["y"]
    dx, dz = R.INWARD[side]
    x0, _y0, z0 = R.inner_cell(room, door)
    rows = {}
    for k in range(3):
        for wv in (-1, 0, 1):
            cell = (x0 + dx * k + (wv if dz else 0), z0 + dz * k + (wv if dx else 0))
            rows.setdefault(k, []).append(cell)
    flat = all(R.floor_xz(room, *cell) == y for cells in rows.values() for cell in cells)
    if not flat:
        return
    pick = set(R.pick_blocks(ctx.d))
    deck = lk.get("deck")
    for cells in rows.values():
        for (x, z) in cells:
            below = grid.block_at(x, y - 1, z)
            if deck and G.classify(below) == G.SOLID and G.base(below) not in pick:
                ctx.add(setb((x, y - 1, z), deck))
    if not lk.get("water") or room["pit"] or room["rise"]:
        return
    wet = rows[1] + rows[2]
    wset = set(wet)
    # contained: every side neighbour of a water cell at y - 1 is water or solid, and the cells above are open
    for (x, z) in wet:
        if G.classify(grid.block_at(x, y, z)) != G.PASS or G.classify(grid.block_at(x, y + 1, z)) != G.PASS:
            return
        for ax, az in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + ax, z + az)
            if n in wset:
                continue
            if not grid.inside(n[0], y - 1, n[1]) or G.classify(grid.block_at(n[0], y - 1, n[1])) != G.SOLID:
                return
    for (x, z) in wet:
        ctx.add(setb((x, y - 2, z), lk.get("bed", ctx.theme["hull"]["floor"])))
        ctx.add(setb((x, y - 1, z), "minecraft:water"))
    ctx.built.meta["extra_drop"] = max(ctx.built.meta.get("extra_drop", 0), 1)


# ------------------------------------------------------------------------------------------------- the kind


def hub_point(room):
    p = room.get("params") or {}
    fx, fz = (p.get("hub") or [0.5, 0.5])[:2]
    x = room["ix0"] + int(round((room["ix1"] - room["ix0"]) * float(fx)))
    z = room["iz0"] + int(round((room["iz1"] - room["iz0"]) * float(fz)))
    x = min(max(x, room["ix0"] + 2), room["ix1"] - 2)
    z = min(max(z, room["iz0"] + 2), room["iz1"] - 2)
    return [x, R.floor_at(room, x), z]


def kind_crossroads(doc, d, slot, room, theme):
    return {"anchors": {"hub": hub_point(room)},
            "functions": {"enter": ["title @s actionbar %s" % R.text("The way splits here.", "gray")]},
            "meta": {"crossroads": True}}


# ------------------------------------------------------------------------------------------------- checks


def _sign_problems(label, sign):
    lines = _sign_lines(sign)
    if not lines or len(lines) > SIGN_LINES:
        return ["%s: a sign is a string or 1..%d lines" % (label, SIGN_LINES)]
    bad = []
    for t in lines:
        if not isinstance(t, str) or not t or len(t) > SIGN_LINE or any(not (32 <= ord(ch) < 127) for ch in t) \
                or "'" in t or '"' in t or "\\" in t:
            bad.append("%s: sign line %r: 1..%d printable characters, no quotes or backslash" % (label, t, SIGN_LINE))
    return bad


def record_checks(doc, d, rd, theme):
    bad = []
    lab = d["id"]
    looks = looks_of(theme)
    top = rd["rooms"]
    for k, r in enumerate(top):
        kind = r.get("kind")
        if kind == "crossroads":
            nxt = top[k + 1] if k + 1 < len(top) else None
            if nxt is None or nxt.get("kind") != "fork":
                bad.append("%s room %s: a crossroads is a fork's host: the entry after it must be a fork" % (lab, r["id"]))
        if kind == "fork":
            routes = r.get("routes", [])
            host = top[k - 1] if k else None
            xr = host is not None and host.get("kind") == "crossroads"
            if len(routes) > MAX_ROUTES:
                bad.append("%s fork %s: %d routes; a fork splits at most %d ways" % (lab, r["id"], len(routes), MAX_ROUTES))
            if routes and all(rt.get("optional") for rt in routes):
                bad.append("%s fork %s: every route is optional; one must be the way on (the clock pays it)" % (lab, r["id"]))
            seen = {}
            for rt in routes:
                rid = "%s fork %s route %s" % (lab, r["id"], rt.get("id"))
                lk = rt.get("look")
                if lk is None:
                    if xr:
                        bad.append("%s: a route out of a crossroads needs a look (%s)" % (rid, ", ".join(sorted(looks))))
                elif lk not in looks:
                    bad.append("%s: look %r is not one of theme %s's (%s)" % (rid, lk, d.get("theme"), ", ".join(sorted(looks))))
                elif lk in seen:
                    bad.append("%s: look %r is also route %s's; the ways must look different" % (rid, lk, seen[lk]))
                else:
                    seen[lk] = rt.get("id")
                if rt.get("sign") is not None:
                    bad += _sign_problems(rid, rt["sign"])
                if "optional" in rt and not isinstance(rt["optional"], bool):
                    bad.append("%s: optional is true or false" % rid)
        if kind == "side":
            n = len(r.get("rooms") or [])
            if n > WING_MAX:
                bad.append("%s side %s: a wing is at most %d rooms (has %d)" % (lab, r["id"], WING_MAX, n))
            first = (r.get("rooms") or [{}])[0]
            if first.get("kind") in R.BOX_ONLY_KINDS:
                bad.append("%s side %s: its first room %s is a %s, entered west to east only; a wing is entered through the "
                           "host's side wall: put a connector first" % (lab, r["id"], first.get("id"), first.get("kind")))
    for r in R._walk_records(top):
        if r.get("kind") == "parkour":
            p = r.get("params") or {}
            s = p.get("sections")
            if s is not None and not (isinstance(s, int) and not isinstance(s, bool) and 2 <= s <= PARKOUR_MAX_SECTIONS):
                bad.append("%s room %s: parkour sections is 2..%d" % (lab, r["id"], PARKOUR_MAX_SECTIONS))
            if "hard" in p and not isinstance(p["hard"], bool):
                bad.append("%s room %s: parkour hard is true or false" % (lab, r["id"]))
        if r.get("kind") == "crossroads":
            hub = (r.get("params") or {}).get("hub")
            if hub is not None and not (isinstance(hub, list) and len(hub) == 2
                                        and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in hub)):
                bad.append("%s room %s: hub is [fx, fz], fractions 0..1" % (lab, r["id"]))
    return bad


def sight(grid, eye, target, skip):
    """True if the segment eye -> target crosses no SOLID cell of the grid other than those in `skip`."""
    (ax, ay, az), (bx, by, bz) = eye, target
    n = int(math.ceil(max(abs(bx - ax), abs(by - ay), abs(bz - az)) * 8)) + 1
    cls = grid.cls()
    x0, y0, z0 = grid.box[:3]
    for k in range(n + 1):
        t = k / float(n)
        c = (int(math.floor(ax + (bx - ax) * t)), int(math.floor(ay + (by - ay) * t)), int(math.floor(az + (bz - az) * t)))
        if c in skip or not grid.inside(*c):
            continue
        if cls[c[0] - x0, c[1] - y0, c[2] - z0] == G.SOLID:
            return False
    return True


def exit_target(room, door):
    """The centre of a door's opening in this room's own wall column, at mid height."""
    w = R.wall_line(room, door["side"])
    if door["side"] in ("east", "west"):
        return (w + 0.5, door["y"] + 1.5, door["c"] + 0.5), {(w, door["y"] + h, door["c"] + dc) for h in range(R.DOOR_H) for dc in (-1, 0, 1)}
    return (door["c"] + 0.5, door["y"] + 1.5, w + 0.5), {(door["c"] + dc, door["y"] + h, w) for h in range(R.DOOR_H) for dc in (-1, 0, 1)}


def geometry_checks(doc, d, slot):
    bad = []
    for b in R.slot_build(doc, d, slot):
        room = b.room
        if room["kind"] != "crossroads":
            continue
        lab = "%s room %s" % (d["id"], room["id"])
        exits = [x for x in R.room_doors(room) if x["dir"] == "out" and not x.get("shortcut")]
        for i, a in enumerate(exits):
            for e in exits[i + 1:]:
                if a["side"] == e["side"] and abs(a["c"] - e["c"]) < EXIT_GAP:
                    bad.append("%s: two exits on its %s wall %d apart (at least %d: the ways must not look like one)"
                               % (lab, a["side"], abs(a["c"] - e["c"]), EXIT_GAP))
        hub = b.anchors.get("hub")
        if not hub:
            bad.append("%s: no hub anchor" % lab)
            continue
        hx, hy, hz = hub[:3]
        eye = (hx + 0.5, hy + EYE, hz + 0.5)
        for door in exits:
            tgt, skip = exit_target(room, door)
            if not sight(b.grid, eye, tgt, skip):
                bad.append("%s: the exit on its %s wall at %d cannot be seen from the hub (%d, %d, %d)"
                           % (lab, door["side"], door["c"], hx, hy, hz))
    return bad


def problems_kit3(doc, d, slot):
    theme = R.theme_for(d)
    rd = R.resolve(doc, d, slot)
    bad = record_checks(doc, d, rd, theme)
    if bad:
        return bad
    return geometry_checks(doc, d, slot)


R.register("crossroads", kind_crossroads, dress="light")
R.LAYOUT_FNS.append(layout_pass)
R.POST_DRESS_FNS.append(look_ops)
R.EXTRA_CHECKS.append(problems_kit3)
