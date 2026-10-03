#!/usr/bin/env python
"""Heaven's Arena (schema 2, layout "halls"), audited from what tools/deep_city.py writes. Offline and independent.

Written by an agent that did not build the arena. Every expectation is derived HERE from data/deep_city.json `arena`
and data/arena_trainers.json; nothing is imported from tools/deep_city.py except build() (the artifact under test:
its canvas, every block the city writes, after every later pass and drop) and env_source_root(). arena_geometry,
build_arena_halls, arena_plan_halls, frame, ring_cells and the plan's tier records are never read for an
expectation. The plan supplies two numbers only, the drum's centre and its lobby floor, and both are cross-checked:
the centre against every seat in data/arena_trainers.json, the lobby against the canvas.

The player is tools/deep_walk_audit.py's Walker (a separate auditor's tool, its block kinds and its moves), over a
world made of the canvas inside the drum. The gate is modelled here, from the record's own entity box, with
Minecraft's selector semantics: an `@a[x,y,z,dx,dy,dz]` box spans [x, x+dx+1) on each axis and selects a player
whose hitbox (0.6 wide, 1.8 tall, centred in his cell) overlaps it, strictly.

What must hold:

  drum      every block of the drum (r < radius + 0.5, lobby floor to crown + 3) is WRITTEN: a world applied before
            2026-10-03 holds schema 1's core and annular decks there, and a block the build leaves out keeps them
  shell     every course's wall stands at the radius data/deep_city.json taper gives it (a setback at a tier floor
            narrows the courses ABOVE it), only the lobby's axis doors open in it, and outside a narrowed course
            the drum is air but for the setback's balustrade
  floors    every tier's floor covers the drum out to the band under it, the setback's ledge included
  halls     each tier's whole air volume, floor + 1 to the next floor - 1, is air except the ring, its four corner
            posts, the stair bay and the benches; the lobby is air but for the bay; the crown's three courses are
            air but for its balustrade and its beacon
  ring      11x11 (stage.size) of walkable floor one step over the floor at centre + stage.centre, the cells round
            it at ring height clear
  benches   only outside the ring's corner clearance (1.5), never on the four axis aisles or within one of the
            bay, stepped (an outer bench never lower than an inner one), as many rows per tier as fit between that
            clearance and the hall's wall, capped at `benches`
  seats     each seat is its tier's floor + 2 (on the ring), on the ring at centre + stage.centre + stage.stand,
            3x3 ring under it, 3x3x3 clear over it, its yaw facing stage.mark and its `faces` naming that mark
  exits     one opening per tier in the bay's 7x7 wall ring, at floor + 1 and + 2
  gates     each tier's box is exactly the shaft's 5x5 interior from floor + 3 to the next floor - 1 (the crown for
            tier 7); the landing is a floor cell with two clear over it, beside that tier's exit, outside every box
            and outside the bay, its yaw pointing at the ring
  walks     with the gates ignored the lobby reaches the crown, every exit, landing and mark; from every exit the
            tier's mark is reached without entering the stair (no bench closes it); with the gates on, a player
            holding the first k tiers' tags reaches tier k+1's mark and nothing above that tier's box, and a player
            holding none, put on any tier's landing, walks down to the lobby
  cycle     tools/route_trainers.py files()' cycle holds exactly one title and one tp per tier, on the record's box
            and the record's landing, for players without that tier's tag

Not covered: anything a running server decides -- whether the cycle runs at the rate it says, a player's real
position inside a cell (the walk centres him), knockback, an rctmod battle, the trainers' tp-home, whether the tag
is held when it should be, and whether the emitted functions place the canvas faithfully (_compress is not
re-read here: tests/test_deep_city.py and tools/deep_walk_audit.py read the commands). Slabs and stairs are full
blocks to the Walker.

    python tools/arena_audit.py [--source-root <root>]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

CITY = ROOT / "data" / "deep_city.json"
TRAINERS = ROOT / "data" / "arena_trainers.json"

AIRS = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
BAY = 7                 # data/deep_city.json bay_why: "the 7x7 stair" -- a 1-thick wall round a 5x5 shaft
AISLE = 1               # benches_why: "four aisles on the axes" -- |dx| <= 1 or |dz| <= 1 is never a bench
CORNER_CLEAR = 1.5      # benches_why: "kept 1.5 clear of the ring's corners"
BAY_CLEAR = 1           # benches_why: "nothing within one of the bay"
PLAYER_H, PLAYER_W = 1.8, 0.6
CHECKS = ("drum", "shell", "floors", "halls", "ring", "benches", "seats", "exits", "gates", "walks", "cycle")


def base(b):
    return re.split(r"[\[{ ]", b, 1)[0]


def is_air(b):
    return b is not None and base(b) in AIRS


def load():
    ar = json.loads(CITY.read_text(encoding="utf-8"))["arena"]
    tr = json.loads(TRAINERS.read_text(encoding="utf-8"))["trainers"]
    return ar, sorted(tr, key=lambda t: t["tier"])


# ------------------------------------------------------------------ the arena as the data describes it

def shell_radius(ar, y):
    """The drum's radius for the course at y. taper [[ty, r], ...]: a setback AT a tier floor ty, so every course
    above ty is r (taper_why: "the drum narrows only ABOVE the lip"); the floor ty itself still reaches the band
    below ("each setback's floor runs out to the band below as a lit ledge")."""
    r = int(ar["radius"])
    for ty, tr in sorted((int(a), int(b)) for a, b in ar["taper"]):
        if y > ty:
            r = tr
    return r


def expect(ar, trainers, centre, lobby):
    """Everything the audit compares with the canvas, from the two data files and the drum's centre and lobby."""
    cx, cz = centre
    tiers = [int(t) for t in ar["tiers"]]
    crown = int(ar["crown"])
    nexts = tiers[1:] + [crown]
    scx, scz = (int(v) for v in ar["stage"]["centre"])
    half = int(ar["stage"]["size"]) // 2
    stand = [int(v) for v in ar["stage"]["stand"]]
    mark = [int(v) for v in ar["stage"]["mark"]]
    bx, bz = (int(v) for v in ar["bay"]["centre"])
    bh = BAY // 2
    ring_c = (cx + scx, cz + scz)
    corner_r = math.hypot(abs(scx) + half, abs(scz) + half)       # the ring's farthest corner from the drum's axis
    E = {"centre": (cx, cz), "lobby": lobby, "rad": int(ar["radius"]), "tiers": tiers, "crown": crown,
         "nexts": nexts, "half": half, "ring_c": ring_c, "corner_r": corner_r,
         "bay": (cx + bx, cz + bz), "bay_half": bh, "benches": int(ar["benches"]), "tier": {}}
    for n, (y, nxt) in enumerate(zip(tiers, nexts), 1):
        hall = shell_radius(ar, y + 1) - 0.5                       # a column is in the hall when r < hall
        # bench rows: one block wide each, from the hall's wall inward, while the row's inner edge stays the
        # corner clearance off the ring
        rows = 0
        while rows < E["benches"] and hall - (rows + 1) >= corner_r + CORNER_CLEAR:
            rows += 1
        E["tier"][n] = {
            "y": y, "next": nxt, "hall": hall, "rows": rows,
            "stand": (ring_c[0] + stand[0], y + 2, ring_c[1] + stand[1]),
            "mark": (ring_c[0] + mark[0], y + 2, ring_c[1] + mark[1]),
            # the shaft's 5x5 interior, from the first height a player on the floor (feet y + 1, 1.8 tall) does
            # not reach, to the next floor: [x, y, z, dx, dy, dz] with the box spanning [x, x + dx + 1)
            "box": [cx + bx - (bh - 1), y + 3, cz + bz - (bh - 1), 2 * (bh - 1), nxt - (y + 3) - 1, 2 * (bh - 1)],
        }
    return E


def _outward(x, y, z, dx, dz):
    """The cell one further out from the drum's axis, along the axis a door at (dx, dz) from the centre is on."""
    if abs(dx) >= abs(dz):
        return x + (1 if dx > 0 else -1), y, z
    return x, y, z + (1 if dz > 0 else -1)


def in_box(box, feet):
    """Whether a player standing in cell `feet` (centred, 0.6 x 1.8) is selected by an entity box."""
    x, y, z, dx, dy, dz = box
    fx, fy, fz = feet
    lo = (fx + 0.5 - PLAYER_W / 2, fy, fz + 0.5 - PLAYER_W / 2)
    hi = (fx + 0.5 + PLAYER_W / 2, fy + PLAYER_H, fz + 0.5 + PLAYER_W / 2)
    blo, bhi = (x, y, z), (x + dx + 1, y + dy + 1, z + dz + 1)
    return all(lo[k] < bhi[k] and hi[k] > blo[k] for k in range(3))


# ------------------------------------------------------------------ the walk

def make_walker(get, E):
    import deep_walk_audit as W
    cx, cz = E["centre"]
    R = E["rad"] + 4
    g0 = E["lobby"]
    box = (cx - R, g0 - 2, cz - R, cx + R, E["crown"] + 6, cz + R)
    world = W.World(box)
    rock = world.id(W.ROCK)
    for x in range(box[0], box[3] + 1):
        for z in range(box[2], box[5] + 1):
            for y in range(box[1], box[4] + 1):
                b = get(x, y, z)
                if b is None:
                    if y <= g0:
                        world.a[x - box[0], z - box[2], y - box[1]] = rock
                    continue
                world.a[x - box[0], z - box[2], y - box[1]] = world.id(b)
    wk = W.Walker(world)
    drum = wk.columns_in(cx - E["rad"], cz - E["rad"], cx + E["rad"], cz + E["rad"])
    drum = {c for c in drum if math.hypot(c // wk.NZ + wk.x0 - cx, c % wk.NZ + wk.z0 - cz) < E["rad"] + 0.5}
    return wk, drum


def neighbours(wk, i):
    """tools/deep_walk_audit.py Walker.walk's moves from feet cell i: level, one up, a drop of up to three, a one-wide
    jump. Repeated here only because a gate needs to stop the walk at a cell, which walk() has no way to say."""
    P, S, NY = wk.P, wk.S, wk.NY
    out = []
    for d in (wk.NZ * NY, -wk.NZ * NY, NY, -NY):
        n = i + d
        if S[n]:
            out.append(n)
        if S[n + 1] and P[i + 2]:
            out.append(n + 1)
        if P[n] and P[n + 1]:
            for k in (1, 2, 3):
                m = n - k
                if not P[m]:
                    break
                if S[m]:
                    out.append(m)
                    break
            if not S[n] and P[n + 2] and P[i + 2]:
                n2 = n + d
                if 0 <= n2 < len(S):
                    if S[n2] and P[n2 + 2]:
                        out.append(n2)
                    elif S[n2 - 1] and P[n2 + 1] and P[n2 + 2]:
                        out.append(n2 - 1)
    return out


def gated_walk(wk, starts, columns, gates):
    """gates: [(box, landing feet)] that apply to this player. A cell inside a box is reached and then turned back:
    its only move is to the landing. -> (set of feet cells reached, set of boxes that fired)."""
    seen, fired, q = set(), set(), deque()
    for c in starts:
        if wk.stand(*c):
            i = wk.idx(*c)
            seen.add(i)
            q.append(i)
    while q:
        i = q.popleft()
        here = wk.xyz(i)
        hit = next((k for k, (box, _l) in enumerate(gates) if in_box(box, here)), None)
        if hit is not None:
            fired.add(hit)
            nxt = [wk.idx(*gates[hit][1])]
        else:
            nxt = neighbours(wk, i)
        for n in nxt:
            if n not in seen and n // wk.NY in columns:
                seen.add(n)
                q.append(n)
    return {wk.xyz(i) for i in seen}, fired


# ------------------------------------------------------------------ the audit

def audit(get, ar, trainers, centre, lobby, cycle=None, bridge_y=None):
    """get(x, y, z) -> the block the build writes there, or None where it writes nothing. -> (problems, stats);
    problems are (check, message). bridge_y: data/deep_city.json spire.bridge_y unless given."""
    import deep_walk_audit as W
    if bridge_y is None:
        bridge_y = int(json.loads(CITY.read_text(encoding="utf-8"))["spire"]["bridge_y"])
    problems = []
    stats = {}

    def bad(k, m):
        problems.append((k, m))

    E = expect(ar, trainers, centre, lobby)
    cx, cz = E["centre"]
    rad, tiers, crown, half = E["rad"], E["tiers"], E["crown"], E["half"]
    rcx, rcz = E["ring_c"]
    bxc, bzc = E["bay"]
    bh = E["bay_half"]
    g0 = lobby

    def solid_floor(b):
        return b is not None and not W.kind(b)[0] and W.kind(b)[1]

    def in_bay(x, z, pad=0):
        return abs(x - bxc) <= bh + pad and abs(z - bzc) <= bh + pad

    def in_ring(x, z):
        return abs(x - rcx) <= half and abs(z - rcz) <= half

    cols = [(cx + dx, cz + dz, math.hypot(dx, dz)) for dx in range(-rad - 1, rad + 2) for dz in range(-rad - 1, rad + 2)
            if math.hypot(dx, dz) < rad + 0.5]
    deck = set(tiers) | {crown}

    # the seats name the centre: centre + stage.centre + stage.stand, at the seat's own tier
    for t in trainers:
        n = t["tier"]
        want = E["tier"][n]["stand"]
        if tuple(t["seat"]) != want:
            bad("seats", "%s seat %s is not its tier's stand %s (centre %s + stage %s + stand %s, floor y%d + 2)"
                % (t["id"], t["seat"], list(want), list(centre), ar["stage"]["centre"], ar["stage"]["stand"],
                   E["tier"][n]["y"]))
    if sorted(t["tier"] for t in trainers) != list(range(1, len(tiers) + 1)):
        bad("seats", "the record's tiers %s are not one per tier 1..%d" % ([t["tier"] for t in trainers], len(tiers)))

    # ---- drum: every block written
    # (the lobby floor itself is the pit's: R9B's tread-light grid stands in it and the city leaves those cells
    # unwritten on purpose; a schema 1 floor block surviving there is a floor either way -- see `floors`)
    unwritten = [(x, y, z) for x, z, _r in cols for y in range(g0 + 1, crown + 4) if get(x, y, z) is None]
    stats["drum_blocks"] = len(cols) * (crown + 3 - g0)
    if unwritten:
        bad("drum", "%d block(s) of the drum are never written, so whatever stands there (schema 1) survives: %s"
            % (len(unwritten), unwritten[:4]))

    # ---- shell and setbacks
    rails = {ty + 1: shell_radius(ar, ty) for ty, _r in ar["taper"]}
    rails[crown + 1] = shell_radius(ar, crown)
    for y in range(g0 + 1, crown + 4):
        if y in deck:
            continue
        sr = shell_radius(ar, y)
        for x, z, r in cols:
            b = get(x, y, z)
            dx, dz = x - cx, z - cz
            if y <= crown and sr - 0.5 <= r < sr + 0.5:
                # the lobby's doors, and tier 1's where a y15 bridge comes in (benches_why: the aisles "are also
                # where the y15 bridges come in"): on an axis, three wide, and a bridge's deck outside it
                door = min(abs(dx), abs(dz)) <= 1 and (y <= g0 + 4 or (
                    bridge_y < y <= bridge_y + 3 and solid_floor(get(*_outward(x, bridge_y, z, dx, dz)))))
                if not door and (b is None or W.kind(b)[0]):
                    bad("shell", "the wall at r=%.1f (course radius %d) is open at %s: %s" % (r, sr, (x, y, z), b))
            elif r >= sr + 0.5 or y > crown:
                rail = y in rails and rails[y] - 0.5 <= r < rails[y] + 0.5
                beacon = y > crown and (dx, dz) == (0, 0)
                if not rail and not beacon and not is_air(b):
                    bad("shell", "outside the course's radius %d at %s (r=%.1f) stands %s" % (sr, (x, y, z), r, b))

    # ---- floors
    for y in sorted(deck) + [g0]:
        reach = shell_radius(ar, y) if y != g0 else rad
        for x, z, r in cols:
            if r >= reach + 0.5 or (abs(x - bxc) < bh and abs(z - bzc) < bh):
                continue                                              # the shaft's interior is the stair's
            if y == g0 and get(x, y, z) is None:
                continue                                              # the pit's own floor (its light grid)
            if not solid_floor(get(x, y, z)):
                bad("floors", "the floor at y%d has no floor at %s (r=%.1f, reaching %d): %s"
                    % (y, (x, z), r, reach, get(x, y, z)))

    # ---- halls: everything a tier's air volume holds
    heights = {}
    for n, T in E["tier"].items():
        y = T["y"]
        for x, z, r in cols:
            if in_bay(x, z):
                continue
            for yy in range(y + 1, T["next"]):
                if r >= shell_radius(ar, yy) - 0.5:
                    continue                                          # the wall, checked above
                b = get(x, yy, z)
                if is_air(b) or b is None:
                    continue
                dx, dz = x - cx, z - cz
                ok = False
                if in_ring(x, z) and yy == y + 1:
                    ok = True
                elif abs(x - rcx) == half and abs(z - rcz) == half and yy in (y + 2, y + 3):
                    ok = True                                         # a corner post and its lantern
                elif (yy <= y + E["benches"] and min(abs(dx), abs(dz)) > AISLE and not in_bay(x, z, BAY_CLEAR)
                      and r >= E["corner_r"] + CORNER_CLEAR):
                    ok = True
                    heights[(n, x, z)] = max(heights.get((n, x, z), 0), yy - y)
                if not ok:
                    bad("halls", "tier %d's hall holds %s at %s (r=%.1f): not ring, post, bay or bench"
                        % (n, b, (x, yy, z), r))
    for x, z, r in cols:                                              # the lobby
        if in_bay(x, z):
            continue
        for yy in range(g0 + 1, tiers[0]):
            if r < rad - 0.5 and not is_air(get(x, yy, z)) and get(x, yy, z) is not None:
                bad("halls", "the lobby holds %s at %s" % (get(x, yy, z), (x, yy, z)))

    # ---- ring
    for n, T in E["tier"].items():
        y = T["y"]
        for dx in range(-half - 1, half + 2):
            for dz in range(-half - 1, half + 2):
                x, z = rcx + dx, rcz + dz
                edge = max(abs(dx), abs(dz))
                if edge <= half:
                    if not solid_floor(get(x, y + 1, z)) or not solid_floor(get(x, y, z)):
                        bad("ring", "tier %d's ring is not one step over the floor at %s: %s on %s"
                            % (n, (x, y + 1, z), get(x, y + 1, z), get(x, y, z)))
                    post = abs(dx) == half and abs(dz) == half
                    if not post and not is_air(get(x, y + 2, z)):
                        bad("ring", "tier %d's ring is covered at %s: %s" % (n, (x, y + 2, z), get(x, y + 2, z)))
                elif math.hypot(x - cx, z - cz) < T["hall"] and not is_air(get(x, y + 1, z)):
                    # in the hall; a cell of the drum's wall diagonal to a corner (tier 7) is the wall, checked above
                    bad("ring", "tier %d's ring is not %dx%d: %s at %s beside it"
                        % (n, 2 * half + 1, 2 * half + 1, get(x, y + 1, z), (x, y + 1, z)))

    # ---- benches
    for n, T in E["tier"].items():
        mine = {(x, z): h for (k, x, z), h in heights.items() if k == n}
        got_rows = max(mine.values(), default=0)
        if got_rows != T["rows"]:
            bad("benches", "tier %d has %d bench row(s); the hall (r<%.1f) fits %d outside the ring's clearance"
                % (n, got_rows, T["hall"], T["rows"]))
        for (x, z), h in mine.items():
            r = math.hypot(x - cx, z - cz)
            for (x2, z2), h2 in mine.items():
                if math.hypot(x2 - cx, z2 - cz) > r + 1 and h2 < h and abs(x2 - x) + abs(z2 - z) <= 2:
                    bad("benches", "tier %d's bench at %s (h%d) is higher than the one outside it at %s (h%d)"
                        % (n, (x, z), h, (x2, z2), h2))
    stats["bench_rows"] = {n: max([h for (k, _x, _z), h in heights.items() if k == n], default=0) for n in E["tier"]}

    # ---- seats
    for t in trainers:
        T = E["tier"][t["tier"]]
        y = T["y"]
        sx, _sy, sz = T["stand"]
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if not (in_ring(sx + dx, sz + dz) and solid_floor(get(sx + dx, y + 1, sz + dz))):
                    bad("seats", "%s: no ring under %s" % (t["id"], (sx + dx, y + 1, sz + dz)))
                for yy in (y + 2, y + 3, y + 4):
                    if not is_air(get(sx + dx, yy, sz + dz)):
                        bad("seats", "%s: not clear at %s: %s" % (t["id"], (sx + dx, yy, sz + dz),
                                                                  get(sx + dx, yy, sz + dz)))
        mx, my, mz = T["mark"]
        want = round(math.degrees(math.atan2(-(mx - sx), mz - sz)))
        if (t["yaw"] - want + 180) % 360 - 180 != 0:
            bad("seats", "%s faces yaw %s, the mark %s is at yaw %d" % (t["id"], t["yaw"], [mx, my, mz], want))
        named = re.findall(r"\[(-?\d+), (-?\d+), (-?\d+)\]", t.get("faces") or "")
        if [tuple(int(v) for v in m) for m in named] != [(mx, my, mz)]:
            bad("seats", "%s's `faces` names %s, not the mark %s" % (t["id"], named, [mx, my, mz]))

    # ---- exits: openings in the bay's wall ring at each tier
    perim = [(bxc + i, bzc + j) for i in range(-bh, bh + 1) for j in range(-bh, bh + 1) if max(abs(i), abs(j)) == bh]
    exits = {}
    for n, T in E["tier"].items():
        y = T["y"]
        found = [(x, y + 1, z) for x, z in perim if is_air(get(x, y + 1, z)) and is_air(get(x, y + 2, z))
                 and solid_floor(get(x, y, z))]
        if len(found) != 1:
            bad("exits", "tier %d's stair bay has %d opening(s) at y%d, not one: %s" % (n, len(found), y + 1, found))
        if found:
            exits[n] = found[0]
    stats["exits"] = {n: list(e) for n, e in exits.items()}
    # and nothing else opens the shaft between the lobby and the crown: a gate box is "the shaft" only while the
    # bay's wall closes it
    door = [(x, g0 + 1, z) for x, z in perim if is_air(get(x, g0 + 1, z)) and is_air(get(x, g0 + 2, z))]
    if len(door) != 1:
        bad("exits", "the stair bay has %d door(s) onto the lobby, not one: %s" % (len(door), door))
    allowed = {(x, yy, z) for x, y1, z in list(exits.values()) + door for yy in (y1, y1 + 1)}
    leaks = [(x, yy, z) for x, z in perim for yy in range(g0 + 1, crown)
             if (x, yy, z) not in allowed and (get(x, yy, z) is None or W.kind(get(x, yy, z))[0])]
    if leaks:
        bad("exits", "the stair bay's wall is open at %d cell(s) that are no exit: %s" % (len(leaks), leaks[:4]))

    # ---- gates: the record's box and landing against the shaft and the floor
    for t in trainers:
        n = t["tier"]
        T = E["tier"][n]
        g = t.get("gate")
        if not g:
            bad("gates", "%s has no gate" % t["id"])
            continue
        if list(g["box"]) != T["box"]:
            bad("gates", "%s's box %s is not the shaft's interior from y%d to the next floor y%d - 1: %s"
                % (t["id"], g["box"], T["y"] + 3, T["next"], T["box"]))
        want_to = "tier %d" % (n + 1) if n < len(tiers) else "the crown"
        if g.get("to") != want_to:
            bad("gates", "%s's gate leads to %r, not %r" % (t["id"], g.get("to"), want_to))
        lx, ly, lz, lyaw = g["landing"]
        feet = (math.floor(lx), int(ly), math.floor(lz))
        if (lx % 1, lz % 1) != (0.5, 0.5):
            bad("gates", "%s's landing %s is not a cell's centre" % (t["id"], g["landing"]))
        if feet[1] != T["y"] + 1:
            bad("gates", "%s's landing y%s is not on tier %d's floor (y%d + 1)" % (t["id"], ly, n, T["y"]))
        if not (solid_floor(get(feet[0], feet[1] - 1, feet[2])) and is_air(get(*feet))
                and is_air(get(feet[0], feet[1] + 1, feet[2]))):
            bad("gates", "%s's landing %s is not a floor with two clear over it" % (t["id"], list(feet)))
        if in_bay(feet[0], feet[2]):
            bad("gates", "%s's landing %s is inside the stair bay" % (t["id"], list(feet)))
        for t2 in trainers:
            if t2.get("gate") and in_box(t2["gate"]["box"], feet):
                bad("gates", "%s's landing %s is inside %s's box: the tp would fire again"
                    % (t["id"], list(feet), t2["id"]))
        if n in exits and abs(exits[n][0] - feet[0]) + abs(exits[n][2] - feet[2]) != 1:
            bad("gates", "%s's landing %s is not beside the tier's exit %s" % (t["id"], list(feet), list(exits[n])))
        # the landing's yaw is a ray that crosses the ring
        vx, vz = -math.sin(math.radians(lyaw)), math.cos(math.radians(lyaw))
        if not any(in_ring(math.floor(lx + vx * s), math.floor(lz + vz * s)) for s in range(1, 40)):
            bad("gates", "%s's landing yaw %s does not look at the ring" % (t["id"], lyaw))

    # ---- walks
    wk, drum = make_walker(get, E)
    shaft = wk.columns_in(bxc - bh + 1, bzc - bh + 1, bxc + bh - 1, bzc + bh - 1)
    start = (cx, g0 + 1, cz)
    if not wk.stand(*start):
        bad("walks", "the lobby at %s is not a place to stand" % (start,))
    free, _f = gated_walk(wk, [start], drum, [])
    stats["walk_open"] = len(free)
    if not any(p[1] == crown + 1 for p in free):
        top = max((p[1] for p in free), default=None)
        bad("walks", "with the gates ignored the lobby never reaches the crown (y%d): the highest feet are y%s"
            % (crown + 1, top))
    for n, T in E["tier"].items():
        for what, c in (("exit", exits.get(n)), ("mark", T["mark"]), ("stand", T["stand"])):
            if c and tuple(c) not in free:
                bad("walks", "with the gates ignored tier %d's %s %s is not reached from the lobby" % (n, what, c))
        if n in exits:
            floor_only = gated_walk(wk, [exits[n]], drum - shaft, [])[0]
            rec = next((t for t in trainers if t["tier"] == n and t.get("gate")), None)
            if rec:
                lx, ly, lz, _yaw = rec["gate"]["landing"]
                if (math.floor(lx), int(ly), math.floor(lz)) not in floor_only:
                    bad("walks", "tier %d's landing %s is not reached from its exit %s on the floor"
                        % (n, rec["gate"]["landing"], exits[n]))
            if T["mark"] not in floor_only:
                bad("walks", "on tier %d nothing reaches the mark %s from the exit %s without the stair: a bench "
                    "or the ring closes it" % (n, T["mark"], exits[n]))
    gates = []
    for t in trainers:
        if t.get("gate"):
            lx, ly, lz, _y = t["gate"]["landing"]
            gates.append((t["gate"]["box"], (math.floor(lx), int(ly), math.floor(lz))))
    for k in range(len(trainers) + 1):
        on = gates[k:]                                                # tags held for tiers 1..k
        seen, fired = gated_walk(wk, [start], drum, on)
        stats.setdefault("climb_top", {})[k] = max(p[1] for p in seen) if seen else None
        if k < len(trainers):
            T = E["tier"][k + 1]
            if T["mark"] not in seen:
                bad("walks", "holding tiers 1..%d, the climb never reaches tier %d's mark %s" % (k, k + 1, T["mark"]))
            above = [p for p in seen if p[1] > T["next"]]
            if above:
                bad("walks", "holding tiers 1..%d, the climb passes tier %d's gate: %s reached"
                    % (k, k + 1, sorted(above, key=lambda p: -p[1])[0]))
            if 0 not in fired:
                bad("walks", "holding tiers 1..%d, tier %d's gate never fires on the climb" % (k, k + 1))
        elif not any(p[1] == crown + 1 for p in seen):
            bad("walks", "holding every tier, the crown is not reached")
    for n, (box, landing) in enumerate(gates, 1):
        seen, fired = gated_walk(wk, [landing], drum, gates)
        stats.setdefault("descent_gates_fired", {})[n] = sorted(f + 1 for f in fired)
        if not any(p[1] == g0 + 1 for p in seen):
            bad("walks", "a player holding no tier, put on tier %d's landing %s, never walks down to the lobby"
                % (n, landing))

    # ---- the cycle
    if cycle is not None:
        sel = re.compile(r"^(title|tp) @a\[x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+),tag=!(\S+?),"
                         r"gamemode=!creative,gamemode=!spectator\] (.*)$")
        got = {}
        for line in cycle:
            m = sel.match(line)
            if m:
                got.setdefault(m.group(8), []).append((m.group(1), [int(v) for v in m.groups()[1:7]], m.group(9)))
        want_tags = {"cobblers_beat_%s" % t["id"]: t for t in trainers}
        for tag in sorted(set(got) - set(want_tags)):
            bad("cycle", "a gate line for %s, which is no arena tier" % tag)
        for tag, t in want_tags.items():
            lines = got.get(tag, [])
            kinds = sorted(k for k, _b, _r in lines)
            if kinds != ["title", "tp"]:
                bad("cycle", "%s: %s gate line(s), not one title and one tp" % (t["id"], kinds))
            for k, box, rest in lines:
                if box != list(t["gate"]["box"]) or box != E["tier"][t["tier"]]["box"]:
                    bad("cycle", "%s's %s box %s is not the record's %s" % (t["id"], k, box, t["gate"]["box"]))
                if k == "tp":
                    lx, ly, lz, lyaw = t["gate"]["landing"]
                    parts = rest.split()
                    if [float(v) for v in parts[:4]] != [float(lx), float(ly), float(lz), float(lyaw)]:
                        bad("cycle", "%s's tp goes to %s, not the record's landing %s"
                            % (t["id"], parts[:4], t["gate"]["landing"]))
    return problems, stats


def build_canvas(source_root):
    """The artifact: tools/deep_city.py's own canvas, after every pass of its build. -> (get, centre, lobby)."""
    import deep_city as DC
    cv, plan, _services, _spec = DC.build(source_root, None)
    return cv.get, tuple(plan["spire"]["centre"]), int(plan["arena"]["lobby"])


def cycle_lines():
    import route_trainers as RT
    fs = RT.files()
    return next(v for k, v in fs.items() if k.endswith("trainers/cycle.mcfunction"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root", default=env_source_root())
    a = ap.parse_args(argv)
    if not a.source_root:
        ap.error("needs --source-root or COBBLERS_SOURCE_ROOT: the city is built from the heightmap")
    ar, trainers = load()
    if ar.get("layout") != "halls":
        print("Heaven's Arena audit: layout is %r, not halls; nothing to audit" % ar.get("layout"))
        return 1
    get, centre, lobby = build_canvas(a.source_root)
    problems, stats = audit(get, ar, trainers, centre, lobby, cycle_lines())
    print("centre %s lobby y%d; drum blocks %d; bench rows %s; open walk %d cells"
          % (list(centre), lobby, stats["drum_blocks"], stats["bench_rows"], stats.get("walk_open", 0)))
    kinds = {}
    for k, m in problems:
        kinds.setdefault(k, []).append(m)
    for k in CHECKS:
        got = kinds.get(k, [])
        print("%-8s %s" % (k, "clean" if not got else "%d PROBLEM(S): %s" % (len(got), "; ".join(got[:3]))))
    print("Heaven's Arena audit: %s" % ("CLEAN" if not problems else "%d PROBLEMS" % len(problems)))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
