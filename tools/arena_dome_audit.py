#!/usr/bin/env python
"""Heaven's Arena dome (tools/arena_dome.py, data/arena_dome.json), audited from the functions it EMITS. Independent.

Written by an agent that did not build the dome (CLAUDE.md principle 16). The built result is read by replaying the
emitted pack -- build/datapacks/cobblers_arena_dome, its index.txt order, every `fill` and `setblock` in command order
-- into a voxel map of its own. Nothing is imported from tools/arena_dome.py: not geometry(), footprint(), solid(),
contract_problems(), shape_problems() or city_problems(). Expectations come from:

  data/arena_dome.json      the declared numbers only: site centre and radius, drum wall/top, dome base/rise, cupola
                            top, tower box and door, passage, venue centres/half/top/steps and the runtime contract
  ARENA_SITE_NORTH.md       the measurement (constants below, each with its section): option A's centre, radius and
                            5,025 columns; the mouth plaza box; the west lift-bank-3 stair door; Victory Road's mouth;
                            "at least 6" of street; the paving owners that count as open floor
  tools/deep_city.py build  the city's plan and canvas (lots, towers, services, reserved and keep-clear boxes, the HQ
                            tower's top, every block the city writes): the neighbour, not the thing under test
  tools/rift_deep.py model  the pit's tread under every column, and the heightmap's rim round the pit (the lip)
  data/arena_fights.json    the ranks; data/spawn_blocks.json + data/spawn_block_policy.json: forbidden blocks

What must hold (check name: property):

  commands   the pack holds only fill, setblock, forceload and comments; index.txt lists every function file
  footprint  every written column is in the site's disc (r <= radius, the measurement's 5,025 columns) or the tower box
  height     highest write < the HQ tower's top (the city plan's hq.top) and > the lip (the commonest rounded heightmap
             height on the pit's rim); == the declared cupola top; nothing under the floor
  blocks     no water, lava, iron, minecraft:light, waterlogged=true, nor any spawn-condition block (data/spawn_blocks.json)
             that data/spawn_block_policy.json does not whitelist for the arena (it whitelists none)
  floor      every footprint column has a solid block written at floor_y
  drum       every column with wall[0] < r <= wall[1] is solid from floor_y+1 to drum.top, except the declared passage
             (passage x, inside the tower box), which is open to passage.to_y
  dome       every disc column's highest solid write is within 0.5 (rounding to a block) of the declared half-ellipsoid,
             base + rise * sqrt(1 - (r / wall[1])^2), the cupola's 3x3 excepted
  shell      a flood from the grand stage through every non-solid cell: with the door's declared opening closed it
             reaches nothing outside the written columns or above them; with it open it reaches entrance.outside; and
             every interior cell it reaches is WRITTEN (an unwritten one keeps whatever the world held)
  venues     each venue's (2*half-1)^2 floor at y=top is solid, 9 cells over it air (venue_why "at least 9 of headroom");
             every venue column and step row inside the drum's inner wall; venues disjoint
  contract   id/name/ranks/challenger_mark[x,y,z,yaw]/opponent_spot[x,y,z,yaw]/post[x,y,z] present; each point at a
             block centre, a solid block under the feet and two passable cells; mark and spot on the venue's clear
             floor at top+1, 8 apart, each yaw exactly facing the other (Minecraft yaw: 0 = +z, 90 = -x); the ranks
             across venues are data/arena_fights.json's, each exactly once
  site       data's centre and radius are the measurement's option A
  city       no written column on a city lot's columns, a lift-bank stair tower's footprint, a service box, a reserved or
             keep-clear box, the measured mouth plaza, or a column the pit's model does not put at floor_y; no written
             column nearer than 6 to anything the city builds (a write above the floor, or a non-paving owner) or to
             any lot's door or tower's door_out
  walk       a player (feet cell: a solid block under, two passable; step up 1 with head room, drop up to 3) on the
             pit's model + the city's canvas + this dome: reaches the dome's door from the west lift-bank-3 stair door
             and from Victory Road's mouth; reaches every venue's mark and spot from the door; still walks from the
             stair door to Victory Road's mouth (reported with and without the dome); and every floor-level lot door
             that is reachable without the dome is still reachable with it

Not covered (validity is not runtime behaviour, .claude/rules/testing.md): anything a running server decides -- that
R9AD really runs the functions, forceload limits, lighting levels and mob spawns inside the dome, the arena runtime's
use of the contract, a player's real hitbox and jump arc (the walk moves cell to cell), and the world under the floor
(the walk takes the pit from tools/rift_deep.py model(), not from tools/rift_deep.py's emitted carve). Approach aprons
are not in the city's plan (a count only): they are covered by the walk, not by a column check.

    python tools/arena_dome_audit.py [--source-root <root>] [--pack <dir>]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_arena_dome"
FOLDER = "arena_dome"

# ---- the measurement, docs/world-building/ARENA_SITE_NORTH.md (2026-10-03, commit b78b6f0)
SITE_A = ((3584, 3171), 40)              # section 4, option A: "(3584, 3171) ... 40 (81 across, 5,025 columns)"
DISC_COLUMNS = 5025                      # section 4, option A
MOUTH_PLAZA = (3528, 3064, 3592, 3124)   # sections 1 and 3: x3528-3592, z3064-3124 (x0, z0, x1, z1)
STAIR_DOOR = (3580, 3241)                # section 3: the west lift-bank-3 stair tower's door
VR_MOUTH = (3560, 1, 3064)               # section 3: Victory Road's mouth (feet)
MIN_STREET = 6                           # section 4: "at least 6" of street round option A
PAVING = {"plaza", "sidewalk", "fill_light"}   # "How it was measured": what the city lays flush on open floor
RELAYED_WALKS = {"core_to_vr_without": 222, "core_to_vr_with_A": 256}   # section 4, reported beside ours, not asserted

AIRS = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
NUM = r"(-?\d+)"
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)(?: (\S+))?\s*$" % ((NUM,) * 6))
SETB = re.compile(r"^setblock %s %s %s (\S+)(?: (\S+))?\s*$" % ((NUM,) * 3))


# ------------------------------------------------------------------ blocks, by this audit's own reading

def base_id(state):
    return state.split("[")[0].split("{")[0]


def passable(state):
    """A cell a player (and the flood) moves through. Doors, signs, buttons, plates, carpets, torches, ladders, vines
    and rails do not stop a player; everything else written does (glass, panes, chains and lanterns included)."""
    if state is None:
        return True
    b = base_id(state)
    if b in AIRS:
        return True
    name = b.split(":")[-1]
    if name.endswith("_trapdoor"):
        return "open=true" in state
    return name.endswith(("_door", "_sign", "_banner", "_button", "_pressure_plate", "_carpet", "torch", "rail")) \
        or name in ("ladder", "vine", "light")


def tall(state):
    """Collision higher than a block: not a floor a player stands on from a one-block step."""
    name = base_id(state).split(":")[-1]
    return name.endswith(("_fence", "_wall", "_fence_gate")) and not name.endswith("_sign")


# ------------------------------------------------------------------ the emitted pack, replayed

def replay_lines(lines, out, problems, where=""):
    """Apply `fill` and `setblock` lines in order to `out` {(x, y, z): state}; a later write replaces an earlier one."""
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or s.startswith("#") or s.startswith("forceload "):
            continue
        m = FILL.match(s)
        if m:
            x0, y0, z0, x1, y1, z1 = (int(m.group(i)) for i in range(1, 7))
            state, mode = m.group(7), m.group(8)
            if mode not in (None, "replace", "destroy"):
                problems.append(("commands", "%s:%d fill mode %s is not replayed: %s" % (where, n, mode, s)))
                continue
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        out[(x, y, z)] = state
            continue
        m = SETB.match(s)
        if m:
            mode = m.group(5)
            if mode not in (None, "replace", "destroy"):
                problems.append(("commands", "%s:%d setblock mode %s is not replayed: %s" % (where, n, mode, s)))
                continue
            out[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = m.group(4)
            continue
        problems.append(("commands", "%s:%d is not a block write: %s" % (where, n, s[:120])))
    return out


def replay_pack(pack_dir):
    """Every block the pack writes, in index.txt order. -> (writes, problems)."""
    problems = []
    fdir = Path(pack_dir) / "data" / "cobblers" / "function" / FOLDER
    idx = fdir / "index.txt"
    if not idx.is_file():
        return {}, [("commands", "no %s: the pack is not built (python tools/arena_dome.py build)" % idx)]
    order = [ln.strip() for ln in idx.read_text(encoding="utf-8").splitlines() if ln.strip()]
    files = {p.stem for p in fdir.glob("*.mcfunction")}
    for name in sorted(files - set(order)):
        problems.append(("commands", "%s.mcfunction is not in index.txt: R9AD would never run it" % name))
    out = {}
    for name in order:
        f = fdir / (name + ".mcfunction")
        if not f.is_file():
            problems.append(("commands", "index.txt names %s, which does not exist" % name))
            continue
        replay_lines(f.read_text(encoding="utf-8").splitlines(), out, problems, name)
    return out, problems


# ------------------------------------------------------------------ the flood (numpy dilation, no scipy)

def flood(open_, start):
    """Cells of the boolean grid `open_` 6-connected to `start` (an index tuple), by dilation to a fixed point."""
    seen = np.zeros_like(open_)
    if not open_[start]:
        return seen
    seen[start] = True
    while True:
        g = seen.copy()
        g[1:, :, :] |= seen[:-1, :, :]
        g[:-1, :, :] |= seen[1:, :, :]
        g[:, 1:, :] |= seen[:, :-1, :]
        g[:, :-1, :] |= seen[:, 1:, :]
        g[:, :, 1:] |= seen[:, :, :-1]
        g[:, :, :-1] |= seen[:, :, 1:]
        g &= open_
        if (g == seen).all():
            return seen
        seen = g


def shell_flood(W, start, door_cells):
    """Flood the dome's writes from `start`. A cell is outside when its column is unwritten or it is above its column's
    highest write. -> dict(escaped, reached_cells, unwritten_inside, reached(set of outside cells reached))."""
    cols = {}
    for (x, y, z) in W:
        cols[(x, z)] = max(cols.get((x, z), y), y)
    xs = [c[0] for c in cols]
    zs = [c[1] for c in cols]
    ys = [k[1] for k in W]
    X0, X1, Z0, Z1 = min(xs) - 1, max(xs) + 1, min(zs) - 1, max(zs) + 1
    Y0, Y1 = min(ys), max(ys) + 1
    shape = (X1 - X0 + 1, Y1 - Y0 + 1, Z1 - Z0 + 1)
    solid = np.zeros(shape, bool)
    written = np.zeros(shape, bool)
    for (x, y, z), b in W.items():
        written[x - X0, y - Y0, z - Z0] = True
        if not passable(b):
            solid[x - X0, y - Y0, z - Z0] = True
    for (x, y, z) in door_cells:
        if X0 <= x <= X1 and Y0 <= y <= Y1 and Z0 <= z <= Z1:
            solid[x - X0, y - Y0, z - Z0] = True
    top = np.full((shape[0], shape[2]), Y0 - 1, int)
    for (x, z), y in cols.items():
        top[x - X0, z - Z0] = y
    yy = np.arange(Y0, Y1 + 1)[None, :, None]
    outside = yy > top[:, None, :]
    s = (start[0] - X0, start[1] - Y0, start[2] - Z0)
    seen = flood(~solid, s)
    esc = seen & outside
    reached = {(int(i) + X0, int(j) + Y0, int(k) + Z0) for i, j, k in zip(*np.nonzero(esc))}
    unw = seen & ~outside & ~written
    return {"escaped": bool(esc.any()), "reached": reached, "cells": int(seen.sum()),
            "unwritten_inside": [(int(i) + X0, int(j) + Y0, int(k) + Z0) for i, j, k in zip(*np.nonzero(unw))]}


# ------------------------------------------------------------------ the walker

class Walk:
    """A player's feet cells over a code grid: 0 passable, 1 solid, 2 tall solid (fence, wall: not stood on)."""

    def __init__(self, code, origin):
        self.c = code
        self.o = origin            # (X0, Y0, Z0)
        self.n = code.shape
        self.b = bytes(np.ascontiguousarray(code, dtype=np.int8).tobytes())

    def at(self, x, y, z):
        X0, Y0, Z0 = self.o
        i, j, k = x - X0, y - Y0, z - Z0
        nx, ny, nz = self.n
        if not (0 <= i < nx and 0 <= k < nz) or j < 0:
            return 1               # walled in at the box's sides and floored under it: the walk never leaves the box
        return self.b[(i * ny + j) * nz + k] if j < ny else 0

    def stands(self, x, y, z):
        return self.at(x, y - 1, z) == 1 and self.at(x, y, z) == 0 and self.at(x, y + 1, z) == 0

    def moves(self, x, y, z):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if self.at(x, y + 2, z) == 0 and self.stands(nx, y + 1, nz):
                yield (nx, y + 1, nz)
            if self.stands(nx, y, nz):
                yield (nx, y, nz)
            for ny in (y - 1, y - 2, y - 3):
                if all(self.at(nx, yy, nz) == 0 for yy in range(ny, y + 2)) and self.stands(nx, ny, nz):
                    yield (nx, ny, nz)
                    break

    def distances(self, start):
        if not self.stands(*start):
            return {}
        d = {start: 0}
        q = deque([start])
        while q:
            c = q.popleft()
            for n in self.moves(*c):
                if n not in d:
                    d[n] = d[c] + 1
                    q.append(n)
        return d


def walk_world(M, ccv_v, W, box):
    """The code grid over `box` (x0, z0, x1, z1, y0, y1): the pit's model, then the city's canvas, then `W` on top."""
    x0, z0, x1, z1, y0, y1 = box
    mask, T, H = M["mask"], M["tread_y"], M["H"]
    MX0, MZ0 = M["box"][0], M["box"][1]
    nx, ny, nz = x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1
    ground = np.full((nx, nz), 999, int)
    for i in range(nx):
        for k in range(nz):
            a, b = z0 + k - MZ0, x0 + i - MX0
            if 0 <= a < mask.shape[0] and 0 <= b < mask.shape[1]:
                ground[i, k] = int(T[a, b]) if mask[a, b] else int(round(float(H[a, b])))
    yy = np.arange(y0, y1 + 1)[None, :, None]
    code = (yy <= ground[:, None, :]).astype(np.int8)
    for src in (ccv_v, W):
        for (x, y, z), b in src.items():
            if x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1:
                code[x - x0, y - y0, z - z0] = 0 if passable(b) else (2 if tall(b) else 1)
    return Walk(code, (x0, y0, z0))


# ------------------------------------------------------------------ the checks

def load():
    spec = json.loads((DATA / "arena_dome.json").read_text(encoding="utf-8"))
    fights = json.loads((DATA / "arena_fights.json").read_text(encoding="utf-8"))
    spawn = set(json.loads((DATA / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    policy = json.loads((DATA / "spawn_block_policy.json").read_text(encoding="utf-8"))
    white = {b for w in policy.get("whitelist") or [] if "arena" in (w.get("scope") or "").lower() for b in w["blocks"]}
    forbidden = (spawn - white) | {s["from"] for s in policy.get("substitutions") or []}
    return spec, fights, forbidden


def disc(spec):
    (cx, cz), R = spec["site"]["centre"], spec["site"]["radius"]
    return {(x, z) for x in range(cx - R, cx + R + 1) for z in range(cz - R, cz + R + 1)
            if math.hypot(x - cx, z - cz) <= R}


def tower_cols(spec):
    x0, z0, x1, z1 = spec["tower"]["box"]
    return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


def shape_audit(W, spec, fights, forbidden):
    """Every check that needs only the replayed writes and the data. -> (problems [(check, message)], stats)."""
    P = []
    st = {}
    (cx, cz), R = spec["site"]["centre"], spec["site"]["radius"]
    fy = spec["site"]["floor_y"]
    if not W:
        return [("commands", "the pack writes nothing")], st
    D = disc(spec)
    TW = tower_cols(spec)
    FP = D | TW
    cols = {}
    for (x, y, z) in W:
        cols.setdefault((x, z), []).append(y)
    st["blocks"] = len(W)
    st["columns"] = len(cols)

    # site: the data is the measurement's option A
    if (tuple(spec["site"]["centre"]), R) != SITE_A:
        P.append(("site", "data site %s r%s is not ARENA_SITE_NORTH.md option A %s" % (spec["site"]["centre"], R, SITE_A)))
    if len(D) != DISC_COLUMNS:
        P.append(("site", "the disc r<=%s holds %d columns, the measurement %d" % (R, len(D), DISC_COLUMNS)))

    # footprint
    stray = sorted(set(cols) - FP)
    if stray:
        P.append(("footprint", "%d written columns outside the disc and the tower box, e.g. %s" % (len(stray), stray[:3])))

    # height
    ymax = max(y for (_x, y, _z) in W)
    ymin = min(y for (_x, y, _z) in W)
    st["top"] = ymax
    if ymin < fy:
        P.append(("height", "a write at y%d, under the floor y%d" % (ymin, fy)))
    cu_top = spec["dome"]["cupola"]["top"]
    if ymax != cu_top:
        P.append(("height", "the highest write is y%d, the declared cupola top y%d" % (ymax, cu_top)))

    # blocks
    bad = Counter()
    for b in W.values():
        bid = base_id(b)
        if bid in ("minecraft:water", "minecraft:lava", "minecraft:light") or "iron" in bid \
                or "waterlogged=true" in b or bid in forbidden:
            bad[b] += 1
    for b, n in sorted(bad.items()):
        P.append(("blocks", "%s written %d times" % (b, n)))

    def solid_at(x, y, z):
        b = W.get((x, y, z))
        return b is not None and not passable(b)

    def open_at(x, y, z):
        return passable(W.get((x, y, z)))

    # floor
    nofloor = sorted(c for c in FP if not solid_at(c[0], fy, c[1]))
    if nofloor:
        P.append(("floor", "%d footprint columns have no solid floor written at y%d, e.g. %s" % (len(nofloor), fy, nofloor[:3])))

    # drum
    Ri, Ro = spec["drum"]["wall"]
    dtop = spec["drum"]["top"]
    pa = spec["tower"]["passage"]
    tx0, tz0, tx1, tz1 = spec["tower"]["box"]
    holes, shut = [], []
    for (x, z) in D:
        r = math.hypot(x - cx, z - cz)
        if not (Ri < r <= Ro):
            continue
        in_pass = pa["x"][0] <= x <= pa["x"][1] and tz0 <= z <= tz1
        for y in range(fy + 1, dtop + 1):
            if in_pass and y <= pa["to_y"]:
                if not open_at(x, y, z):
                    shut.append((x, y, z))
            elif not solid_at(x, y, z):
                holes.append((x, y, z))
    if holes:
        P.append(("drum", "%d cells of the drum wall (%s < r <= %s, y%d-%d) are not solid, e.g. %s"
                  % (len(holes), Ri, Ro, fy + 1, dtop, sorted(holes)[:3])))
    if shut:
        P.append(("drum", "the passage is shut at %d cells, e.g. %s" % (len(shut), sorted(shut)[:3])))

    # dome surface
    base, rise = spec["dome"]["base"], spec["dome"]["rise"]
    off = []
    for (x, z) in D:
        if abs(x - cx) <= 1 and abs(z - cz) <= 1:
            continue
        r = math.hypot(x - cx, z - cz)
        want = base + rise * math.sqrt(max(0.0, 1 - (r / Ro) ** 2))
        ss = [y for y in cols.get((x, z), []) if solid_at(x, y, z)]
        got = max(ss) if ss else None
        if got is None or abs(got - want) > 0.5 + 1e-9:
            off.append(((x, z), got, round(want, 2)))
    if off:
        P.append(("dome", "%d columns' outer surface is off the half-ellipsoid (r%s, rise %s), e.g. %s"
                  % (len(off), Ro, rise, off[:3])))
    st["crown"] = max((y for y in cols.get((cx, cz), []) if solid_at(cx, y, cz)), default=None)

    # venues and the contract
    vcols = {}
    seen_ranks = []
    for v in spec["venues"]:
        vid = v.get("id")
        for k in ("id", "name", "ranks", "challenger_mark", "opponent_spot", "post", "centre", "half", "top", "steps"):
            if k not in v:
                P.append(("contract", "%s has no %s" % (vid, k)))
        if any(k not in v for k in ("centre", "half", "top", "steps", "challenger_mark", "opponent_spot", "post")):
            continue
        (vx, vz), h, top, steps = v["centre"], v["half"], v["top"], v["steps"]
        mine = {(vx + dx, vz + dz) for dx in range(-h, h + 1) for dz in range(-h, h + 1)}
        mine |= {(x, vz + h + k) for k in range(1, steps + 1) for x in range(vx - 3, vx + 4)}
        out = sorted(c for c in mine if math.hypot(c[0] - cx, c[1] - cz) > Ri)
        if out:
            P.append(("venues", "%s reaches past the drum's inner wall r%s at %s" % (vid, Ri, out[:3])))
        for oid, oc in vcols.items():
            if mine & oc:
                P.append(("venues", "%s and %s overlap" % (vid, oid)))
        vcols[vid] = mine
        nofl, low = [], []
        for dx in range(-(h - 1), h):
            for dz in range(-(h - 1), h):
                x, z = vx + dx, vz + dz
                if not solid_at(x, top, z):
                    nofl.append((x, top, z))
                for y in range(top + 1, top + 10):
                    if W.get((x, y, z)) is None or base_id(W[(x, y, z)]) not in AIRS:
                        low.append((x, y, z, W.get((x, y, z))))
        if nofl:
            P.append(("venues", "%s: %d cells of its %dx%d floor at y%d are not solid, e.g. %s"
                      % (vid, len(nofl), 2 * h - 1, 2 * h - 1, top, nofl[:3])))
        if low:
            P.append(("venues", "%s: %d cells of its 9 headroom are not written air, e.g. %s" % (vid, len(low), low[:3])))
        m, s, p = v["challenger_mark"], v["opponent_spot"], v["post"]
        if len(m) != 4 or len(s) != 4 or len(p) != 3:
            P.append(("contract", "%s: mark/spot need [x, y, z, yaw], post [x, y, z]" % vid))
            continue
        for pt, what in ((m, "challenger_mark"), (s, "opponent_spot"), (p, "post")):
            x, y, z = math.floor(pt[0]), int(pt[1]), math.floor(pt[2])
            if pt[0] != x + 0.5 or pt[2] != z + 0.5 or pt[1] != y:
                P.append(("contract", "%s %s %s is not at a block centre on a whole y" % (vid, what, pt[:3])))
            if not solid_at(x, y - 1, z):
                P.append(("contract", "%s %s %s stands on %s" % (vid, what, pt[:3], W.get((x, y - 1, z)))))
            for yy in (y, y + 1):
                if not open_at(x, yy, z):
                    P.append(("contract", "%s %s %s is shut at y%d by %s" % (vid, what, pt[:3], yy, W.get((x, yy, z)))))
            if what != "post" and not (abs(x - vx) <= h - 1 and abs(z - vz) <= h - 1 and y == top + 1):
                P.append(("contract", "%s %s %s is not on the venue's clear floor at y%d" % (vid, what, pt[:3], top + 1)))
        d = math.hypot(m[0] - s[0], m[2] - s[2])
        if abs(d - 8) > 1e-9:
            P.append(("contract", "%s: the spot is %.2f from the mark, not 8" % (vid, d)))
        for a, b, what in ((m, s, "mark"), (s, m, "spot")):
            want = math.degrees(math.atan2(-(b[0] - a[0]), b[2] - a[2])) % 360
            if abs(((a[3] - want) + 180) % 360 - 180) > 1e-9:
                P.append(("contract", "%s: the %s's yaw %s does not face the other (want %s)" % (vid, what, a[3], want)))
        if (p[0], p[2]) in ((m[0], m[2]), (s[0], s[2])):
            P.append(("contract", "%s: the post stands on the mark or the spot" % vid))
        seen_ranks += list(v.get("ranks") or [])
    ids = [v.get("id") for v in spec["venues"]]
    if len(set(ids)) != len(ids):
        P.append(("contract", "venue ids repeat: %s" % ids))
    want_ranks = sorted(r["rank"] for r in fights["ranks"])
    if sorted(seen_ranks) != want_ranks:
        P.append(("contract", "the venues carry ranks %s; data/arena_fights.json has %s, each once"
                  % (sorted(seen_ranks), want_ranks)))

    # shell: flood from the grand stage (the venue nearest the centre), the door shut, then open
    stage = min(spec["venues"], key=lambda v: math.hypot(v["centre"][0] - cx, v["centre"][1] - cz))
    sm = stage["challenger_mark"]
    start = (math.floor(sm[0]), int(sm[1]), math.floor(sm[2]))
    dr = spec["tower"]["door"]
    door_cells = [(x, y, dr["z"]) for x in range(dr["x"][0], dr["x"][1] + 1) for y in range(fy + 1, dr["to_y"] + 1)]
    shut_f = shell_flood(W, start, door_cells)
    open_f = shell_flood(W, start, [])
    st["interior_cells"] = shut_f["cells"]
    if shut_f["escaped"]:
        P.append(("shell", "with the door shut the inside still reaches %d outside cells, e.g. %s"
                  % (len(shut_f["reached"]), sorted(shut_f["reached"])[:3])))
    if shut_f["unwritten_inside"]:
        P.append(("shell", "%d cells inside the shell are never written (the world keeps what it held), e.g. %s"
                  % (len(shut_f["unwritten_inside"]), shut_f["unwritten_inside"][:3])))
    outside = tuple(spec["entrance"]["outside"])
    if outside not in open_f["reached"]:
        P.append(("shell", "with the door open the inside does not reach the door's outside %s" % (outside,)))
    door = tuple(spec["entrance"]["door"])
    if door not in door_cells:
        P.append(("shell", "entrance.door %s is not in the tower's declared door opening" % (door,)))
    return P, st


def city_state(source_root):
    """The neighbour: the city's canvas and plan (tools/deep_city.py build, nothing emitted, about 10 s) and the pit's
    ring model (tools/rift_deep.py model)."""
    import deep_city as DC
    import rift_deep as RD
    ccv, plan, _services, _cspec = DC.build(source_root, None)
    return {"v": {k: b for k, (b, _ph) in ccv.v.items()}, "owner": dict(ccv.owner), "plan": plan,
            "model": RD.model(source_root)}


def lip(M):
    """The pit's lip: the commonest rounded heightmap height on the columns just outside the pit's mask."""
    mask = M["mask"]
    pad = np.pad(mask, 1)
    nb = pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
    rim = (~mask) & nb
    vals = np.round(M["H"][rim]).astype(int)
    c = Counter(vals.tolist())
    return c.most_common(1)[0][0], int(vals.max())


def city_audit(W, spec, city):
    """Every check against the neighbour: the city's plan and canvas and the pit's model. -> (problems, stats)."""
    P = []
    st = {}
    plan, M, cv, owner = city["plan"], city["model"], city["v"], city["owner"]
    fy = spec["site"]["floor_y"]
    cols = {(x, z) for (x, _y, z) in W}
    if not cols:
        return [("city", "the pack writes nothing")], st
    ymax = max(y for (_x, y, _z) in W)

    # height against the neighbours
    hq_top = plan["hq"]["top"]
    lp, lmax = lip(M)
    st.update(hq_top=hq_top, lip=lp, rim_max=lmax)
    if not ymax < hq_top:
        P.append(("height", "the dome's top y%d is not under the HQ tower's y%d" % (ymax, hq_top)))
    if not ymax > lp:
        P.append(("height", "the dome's top y%d does not clear the lip y%d" % (ymax, lp)))

    # the pit's model: floor_y under every written column
    T, mask = M["tread_y"], M["mask"]
    MX0, MZ0 = M["box"][0], M["box"][1]
    offf = []
    for (x, z) in cols:
        a, b = z - MZ0, x - MX0
        if not (0 <= a < mask.shape[0] and 0 <= b < mask.shape[1] and mask[a, b] and int(T[a, b]) == fy):
            offf.append((x, z))
    if offf:
        P.append(("city", "%d written columns are not the pit's y%d floor, e.g. %s" % (len(offf), fy, sorted(offf)[:3])))

    # what the city stands on each column: lots by owner; anything above the floor or not paving is built
    lot_ids = {l_["id"] for l_ in plan["lots"]}
    lot_cols, built = set(), set()
    for (x, y, z) in cv:
        o = owner.get((x, y, z))
        if o in lot_ids:
            lot_cols.add((x, z))
        if y > fy or o not in PAVING:
            built.add((x, z))
    boxes = []
    for t in plan["towers"]:
        (a0, b0), (a1, b1) = t["footprint"]
        boxes.append(("tower at door %s" % (t["door"],), (a0, b0, a1, b1)))
    for s in plan.get("services") or []:
        b = s["box"]
        boxes.append(("service %s" % s["id"], (b[0], b[2], b[3], b[5])))
    for r in plan.get("reserved") or []:
        b = r["box"]
        boxes.append(("reserved %s" % r["id"], (b[0], b[2], b[3], b[5])))
    for k, b in (plan.get("keep_clear") or {}).items():
        boxes.append(("keep-clear %s" % k, (b[0], b[2], b[3], b[5])))
    boxes.append(("the measured mouth plaza", MOUTH_PLAZA))
    hb = plan["hq"]["tower"]
    boxes.append(("the HQ tower", tuple(hb)))
    on_lot = sorted(cols & lot_cols)
    if on_lot:
        P.append(("city", "%d written columns on city lots, e.g. %s" % (len(on_lot), on_lot[:3])))
    on_built = sorted(cols & built)
    if on_built:
        P.append(("city", "%d written columns where the city builds more than floor paving, e.g. %s"
                  % (len(on_built), on_built[:3])))
    for name, (a0, b0, a1, b1) in boxes:
        hit = sorted(c for c in cols if a0 <= c[0] <= a1 and b0 <= c[1] <= b1)
        if hit:
            P.append(("city", "%d written columns inside %s, e.g. %s" % (len(hit), name, hit[:3])))

    # the street left: every written column to anything the city builds, and to every door
    # (from the written set's edge columns: a point outside the set is nearest to one of them; one inside is flagged
    # above)
    edge = np.array([(x, z) for (x, z) in cols
                     if any((x + dx, z + dz) not in cols for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))], float)

    def nearest(points):
        if not points:
            return (1e9, None, None)
        pts = np.array(points, float)
        d = np.hypot(edge[:, None, 0] - pts[None, :, 0], edge[:, None, 1] - pts[None, :, 1])
        i, j = np.unravel_index(int(d.argmin()), d.shape)
        return (float(d[i, j]), tuple(int(v) for v in edge[i]), tuple(int(v) for v in pts[j]))

    xs = [c[0] for c in cols]
    zs = [c[1] for c in cols]
    bx0, bx1, bz0, bz1 = min(xs) - 15, max(xs) + 15, min(zs) - 15, max(zs) + 15
    near_built = [c for c in built if bx0 <= c[0] <= bx1 and bz0 <= c[1] <= bz1]
    nb = nearest(near_built)
    st["street"] = (round(nb[0], 1), nb[2])
    if nb[0] < MIN_STREET:
        P.append(("city", "a write at %s is %.1f from the city's %s, under the measured %d" % (nb[1], nb[0], nb[2], MIN_STREET)))
    doors = [tuple(l_["door"]) for l_ in plan["lots"] if l_.get("door")]
    doors += [tuple(t["door_out"]) for t in plan["towers"]]
    doors.append(tuple(plan["sink_gate"]["door_out"]))
    nd = nearest(doors)
    st["door_street"] = (round(nd[0], 1), nd[2])
    if nd[0] < MIN_STREET:
        P.append(("city", "a write at %s is %.1f from the door %s, under the measured %d" % (nd[1], nd[0], nd[2], MIN_STREET)))

    # the walk
    stair = [t for t in plan["towers"] if tuple(t["door"]) == STAIR_DOOR]
    if not stair:
        P.append(("walk", "no lift-bank stair tower in the city's plan has its door at %s" % (STAIR_DOOR,)))
        return P, st
    t = stair[0]
    s_feet = (STAIR_DOOR[0], t["from"] + 1, STAIR_DOOR[1])
    box = (min(xs + [VR_MOUTH[0], STAIR_DOOR[0]]) - 90, min(zs + [VR_MOUTH[2]]) - 30,
           max(xs + [STAIR_DOOR[0]]) + 100, max(zs + [STAIR_DOOR[1]]) + 30, fy - 2, fy + 24)
    with_d = walk_world(M, cv, W, box)
    without = walk_world(M, cv, {}, box)
    dw = with_d.distances(s_feet)
    dn = without.distances(s_feet)
    if not dw:
        P.append(("walk", "the stair door's feet cell %s is not stood on" % (s_feet,)))
        return P, st
    door = tuple(spec["entrance"]["door"])
    st["stair_to_door"] = dw.get(door)
    if door not in dw:
        P.append(("walk", "the dome's door %s is not reached on foot from the stair door %s" % (door, s_feet)))
    st["core_to_vr_with"] = dw.get(VR_MOUTH)
    st["core_to_vr_without"] = dn.get(VR_MOUTH)
    if VR_MOUTH not in dw:
        P.append(("walk", "the walk from the stair door %s to Victory Road's mouth %s is cut" % (s_feet, VR_MOUTH)))
    dv = with_d.distances(VR_MOUTH)
    st["vr_to_door"] = dv.get(door)
    if door not in dv:
        P.append(("walk", "the dome's door %s is not reached from Victory Road's mouth %s" % (door, VR_MOUTH)))
    dd = with_d.distances(door)
    for v in spec["venues"]:
        for k in ("challenger_mark", "opponent_spot"):
            p = v[k]
            c = (math.floor(p[0]), int(p[1]), math.floor(p[2]))
            if c not in dd:
                P.append(("walk", "%s's %s %s is not reached from the door" % (v["id"], k, c)))
    lost, kept, checked = [], 0, 0
    for l_ in plan["lots"]:
        if not l_.get("door") or l_.get("level") != fy:
            continue
        c = (l_["door"][0], fy + 1, l_["door"][1])
        if c in dn:
            checked += 1
            if c in dw:
                kept += 1
            else:
                lost.append(l_["id"])
    st["floor_doors"] = (kept, checked)
    if lost:
        P.append(("walk", "%d floor-level lot doors reached before the dome are cut off by it: %s" % (len(lost), lost)))
    return P, st


def audit(pack=PACK, source_root=None, city=None):
    spec, fights, forbidden = load()
    W, P = replay_pack(pack)
    sp, st = shape_audit(W, spec, fights, forbidden)
    P += sp
    if city is None and source_root:
        city = city_state(source_root)
    if city is not None and W:
        cp, cst = city_audit(W, spec, city)
        P += cp
        st.update(cst)
    elif city is None:
        P.append(("city", "no source root: the city, lip and walk checks did not run"))
    return P, st


CHECKS = ("commands", "site", "footprint", "height", "blocks", "floor", "drum", "dome", "shell", "venues", "contract",
          "city", "walk")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root")
    ap.add_argument("--pack", default=str(PACK))
    a = ap.parse_args(argv)
    from terrain import env_source_root
    src = a.source_root or env_source_root()
    P, st = audit(Path(a.pack), src)
    by = Counter(k for k, _m in P)
    for k in CHECKS:
        print("  %-9s %s" % (k, "PROBLEMS %d" % by[k] if by[k] else "ok"))
    for k, m in P[:30]:
        print("PROBLEM [%s] %s" % (k, m))
    print("  stats: %s" % json.dumps(st, default=str))
    print("  relayed (ARENA_SITE_NORTH.md section 4, 2D walk): core to Victory Road %d without a dome, %d with A"
          % (RELAYED_WALKS["core_to_vr_without"], RELAYED_WALKS["core_to_vr_with_A"]))
    if P:
        print("arena_dome_audit: FAILED, %d problems" % len(P))
        return 1
    print("arena_dome_audit: ok, %d blocks replayed" % st.get("blocks", 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
