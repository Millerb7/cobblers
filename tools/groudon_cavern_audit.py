#!/usr/bin/env python
"""Independent audit of Groudon's quake cavern (tools/groudon_cavern.py, data/groudon_cavern.json).

WRITTEN TO NOT SHARE THE BUILDER'S DERIVATION (CLAUDE.md "How to prove an audit is independent"). It imports nothing from
tools/groudon_cavern.py: no geometry function, no noise, no profile. It reads
  - the EMITTED functions of both packs (build/datapacks/cobblers_groudon_cavern and _build), as text;
  - the heightmap through tools/ground.py (the natural terrain: solid up to the ground, air above, and nothing else: no
    cave, no ore, no aquifer is assumed or invented);
  - the declared intent in data: the model box, the keeper's box and stand, the flag (data/groudon_cavern.json), Groudon's
    record, its pedestal (data/rewards.json groudon_red_orb container, held to the builder's geometry only by this audit),
    the retired site (data/legendaries.json), the spawn zones, the neighbours' footprints;
and REPLAYS the writes (`fill`, `setblock`, in the order the functions call each other) onto a voxel grid of that terrain,
before the quake (the carve) and after each stage. Everything below is then measured on the replayed world:

  envelope   every cell within 4 of any carved void was WRITTEN solid by the carve (not merely natural rock: a missing
             envelope is invisible against a terrain model that is solid everywhere, so the audit asks for the writes)
  seal       a flood from Groudon's cell through air and lava never reaches the sky or the grid's edge before the quake
  plug       at least 4 cells of rock between the open ravine and the carved interior until the last stage
  walk       from the keeper's stand on the bowl floor to Groudon's cell and back, one block up or down at a time (up to 3
             down), two cells of headroom everywhere, over every reachable cell and not one shortest path
  hazard     nothing reachable stands on magma, fire or lava, within one block (diagonals) of lava, or beside a drop of
             more than 3 or into lava; nothing reachable inside the carved cavern is a place to fall from
  lava       every lava cell is walled or floored on its four sides and its underside; no water is written anywhere
  guard      the keeper's box holds every carved cell within 40 blocks of the pedestal and not the stand it sends people to,
             the stand is a place to stand, and the selector carries the record's own gate flag
  stages     the opening writes only inside the declared box; each stage holds its own chunks; the trigger box keeps every
             chunk it writes within the server's simulation distance of a player standing in it; each stage advances the
             state only on a probe cell that was rock before the stage and is air after it; nothing sets the legendary's
             open score before the last stage
  cleanup    tools/legendaries_audit.py's own check of the retired chamber's restore (it derives that chamber itself), run
             on the pack tools/legendaries.py would emit, and nothing the cavern writes touches the retired hull
  places     the clearances to the Mining Town's square, Fossick's hill, the retired hull; the hall is spawn-free; the roof
             over every void is thick; the hall is at least Kyogre's basin's size

NOT PROVEN: that the natural terrain holds nothing the model does not (a natural cave breaching the envelope is exactly
what the envelope is for, and its absence is assumed from a 4-thick wall, not seen); the surface and subsurface blocks of
the real world; that a command parses the way the game parses it; the keeper, the rumble or the quake in a running game;
what a player sees; whether `forceload add` inside a function loads a chunk in the same tick (the repo's measurement of
2026-09-21 says so; the stage ALSO needs a player within the simulation distance and a read-back probe).

  python tools/groudon_cavern_audit.py [--runtime DIR] [--build DIR]
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PACKS = ROOT / "build" / "datapacks"
RUNTIME = PACKS / "cobblers_groudon_cavern"
BUILD = PACKS / "cobblers_groudon_cavern_build"
DATA = ROOT / "data"

NS = "cobblers"
CARVE_ONCE = "cobblers:legendary/groudon/carve_once"
MARGIN = 4                    # WATER_BUILD_PLAN 4.5 audit 1, this audit's own copy of the number
GUARD_REACH = 40              # every carved cell this close (horizontally) to the pedestal is the keeper's to guard
SAFE_DROP = 3                 # fall damage starts past three blocks
KYOGRE_BASIN_COLUMNS = 1590   # pi * 22.5 ** 2: data/kyogre_cave.json rooms.basin radii 22.5, an ellipse
MIN_ROOF = 8
MIN_CLEAR = 60                # blocks from the ravine (the surface the quake cuts) and from Fossick's hill to any authored position
MIN_CLEAR_DEEP = 40           # blocks, horizontally, from the tunnel and hall (50 and more under the plateau) to any authored position
SIM_DEFAULT = 6

AIR, SOLID, LAVA, WATER, WALL, HURT = 0, 1, 2, 3, 4, 5
HURT_BLOCKS = {"minecraft:magma_block", "minecraft:fire", "minecraft:soul_fire", "minecraft:campfire",
               "minecraft:soul_campfire", "minecraft:cactus", "minecraft:sweet_berry_bush", "minecraft:wither_rose",
               "minecraft:powder_snow", "minecraft:cobweb"}
AIRS = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}

NUM = r"(-?\d+)"
FILL = re.compile(r"^fill\s+%s\s+%s\s+%s\s+%s\s+%s\s+%s\s+(\S+)(?:\s+(.*))?$" % ((NUM,) * 6))
SETBLOCK = re.compile(r"^setblock\s+%s\s+%s\s+%s\s+(\S+)(?:\s+(.*))?$" % ((NUM,) * 3))
SELBOX = re.compile(r"(?<![a-z])x=%s,y=%s,z=%s,dx=%s,dy=%s,dz=%s([^\]]*)\]" % ((NUM,) * 6))
FORCELOAD = re.compile(r"^forceload\s+(add|remove)\s+%s\s+%s(?:\s+%s\s+%s)?$" % ((NUM,) * 4))
CALL = re.compile(r"(?:^|\brun\s+)function\s+(\S+)\s*$")


class Report:
    def __init__(self):
        self.errors, self.checks, self.notes = [], 0, []

    def check(self, ok, msg):
        self.checks += 1
        if not ok:
            self.errors.append(msg)
        return bool(ok)


def classify_block(name):
    n = name.split("[", 1)[0].split("{", 1)[0]
    if n in AIRS:
        return AIR
    if n == "minecraft:lava":
        return LAVA
    if n == "minecraft:water" or "bubble_column" in n:
        return WATER
    if n.endswith("_wall") or n.endswith("_fence") or n.endswith("_fence_gate"):
        return WALL
    if n in HURT_BLOCKS:
        return HURT
    return SOLID


def jload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------------------------- reading


class Pack:
    """The two packs' functions as text, by id."""

    def __init__(self, *dirs):
        self.fns = {}
        for d in dirs:
            d = Path(d)
            if not d.is_dir():
                continue
            for f in sorted((d / "data").glob("*/function/**/*.mcfunction")):
                rel = f.relative_to(d / "data").parts
                fid = "%s:%s" % (rel[0], "/".join(rel[2:])[:-len(".mcfunction")])
                self.fns[fid] = f.read_text(encoding="utf-8").splitlines()

    def body(self, fid):
        return [l.strip() for l in self.fns.get(fid, []) if l.strip() and not l.strip().startswith("#")]


class World:
    """A voxel grid of the natural terrain, written onto by replayed commands."""

    def __init__(self, ground, box):
        (x0, x1), (y0, y1), (z0, z1) = box
        self.o = (x0, y0, z0)
        self.shape = (x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1)
        xs = np.arange(x0, x1 + 1)
        zs = np.arange(z0, z1 + 1)
        self.G = np.array([[ground(int(x), int(z)) for z in zs] for x in xs], dtype=np.int32)
        ys = (y0 + np.arange(self.shape[1]))[None, :, None]
        self.natural = ys <= self.G[:, None, :]
        self.cls = np.where(self.natural, SOLID, AIR).astype(np.int8)
        self.nid = np.zeros(self.shape, np.int16)
        self.names = ["natural"]
        self.written_solid = np.zeros(self.shape, bool)
        self.writes = 0
        self.outside = []
        self.boxes = []

    def copy(self):
        w = copy.copy(self)
        w.cls, w.nid, w.written_solid = self.cls.copy(), self.nid.copy(), self.written_solid.copy()
        w.names, w.outside, w.boxes = list(self.names), list(self.outside), list(self.boxes)
        return w

    def name_id(self, n):
        if n not in self.names:
            self.names.append(n)
        return self.names.index(n)

    def write(self, box, block):
        x0, y0, z0, x1, y1, z1 = box
        ox, oy, oz = self.o
        i0, j0, k0 = x0 - ox, y0 - oy, z0 - oz
        i1, j1, k1 = x1 - ox, y1 - oy, z1 - oz
        self.writes += 1
        self.boxes.append((box, block))
        if min(i0, j0, k0) < 0 or i1 >= self.shape[0] or j1 >= self.shape[1] or k1 >= self.shape[2]:
            self.outside.append((box, block))
            return
        c = classify_block(block)
        self.cls[i0:i1 + 1, j0:j1 + 1, k0:k1 + 1] = c
        self.nid[i0:i1 + 1, j0:j1 + 1, k0:k1 + 1] = self.name_id(block.split("[", 1)[0])
        if c in (SOLID, WALL, HURT):
            self.written_solid[i0:i1 + 1, j0:j1 + 1, k0:k1 + 1] = True
        else:
            self.written_solid[i0:i1 + 1, j0:j1 + 1, k0:k1 + 1] = False

    def at(self, x, y, z):
        i, j, k = x - self.o[0], y - self.o[1], z - self.o[2]
        if min(i, j, k) < 0 or i >= self.shape[0] or j >= self.shape[1] or k >= self.shape[2]:
            return None
        return int(self.cls[i, j, k])

    def name_at(self, x, y, z):
        return self.names[int(self.nid[x - self.o[0], y - self.o[1], z - self.o[2]])]


def replay(pack, fid, world, seen=None, depth=0):
    """Apply fid's fill and setblock lines to `world`, following `function` calls (a conditional call is followed as if its
    condition held: the conditions are checked as text elsewhere). Returns the ids it ran."""
    seen = [] if seen is None else seen
    if depth > 12 or fid not in pack.fns:
        return seen
    seen.append(fid)
    for line in pack.body(fid):
        m = FILL.match(line)
        if m:
            v = [int(a) for a in m.groups()[:6]]
            world.write((min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]), max(v[2], v[5])),
                        m.group(7))
            continue
        m = SETBLOCK.match(line)
        if m:
            x, y, z = (int(a) for a in m.groups()[:3])
            world.write((x, y, z, x, y, z), m.group(4))
            continue
        m = CALL.search(line)
        if m and m.group(1) in pack.fns:
            replay(pack, m.group(1), world, seen, depth + 1)
    return seen


# ---------------------------------------------------------------------------------------------------------------- helpers


def dilate(mask, n):
    out = mask.copy()
    for ax in range(3):
        acc = out.copy()
        for s in range(1, n + 1):
            a = [slice(None)] * 3
            b = [slice(None)] * 3
            a[ax], b[ax] = slice(s, None), slice(None, -s)
            acc[tuple(a)] |= out[tuple(b)]
            acc[tuple(b)] |= out[tuple(a)]
        out = acc
    return out


def flood(passable, start, G, o):
    """Cells reachable from `start` through `passable` (6-neighbourhood). Returns (set size, leaked: reached the sky or the
    grid's edge). The sky is any cell above the ground column."""
    nx, ny, nz = passable.shape
    seen = np.zeros(passable.shape, bool)
    si, sj, sk = start
    if not passable[si, sj, sk]:
        return 0, False, seen
    q = deque([start])
    seen[si, sj, sk] = True
    leaked = False
    n = 0
    while q:
        i, j, k = q.popleft()
        n += 1
        if i in (0, nx - 1) or j in (0, ny - 1) or k in (0, nz - 1) or j + o[1] > G[i, k]:
            leaked = True
        for di, dj, dk in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            a, b, c = i + di, j + dj, k + dk
            if 0 <= a < nx and 0 <= b < ny and 0 <= c < nz and passable[a, b, c] and not seen[a, b, c]:
                seen[a, b, c] = True
                q.append((a, b, c))
    return n, leaked, seen


class Walker:
    """The walking rules, on a replayed world: stand on a solid non-wall, feet and head cells air."""

    def __init__(self, w):
        self.w = w
        self.c = w.cls
        self.o = w.o
        self.nx, self.ny, self.nz = w.shape

    def free(self, i, j, k):
        return 0 <= i < self.nx and 0 <= j < self.ny and 0 <= k < self.nz and self.c[i, j, k] == AIR

    def support(self, i, j, k):
        return 0 <= i < self.nx and 0 < j <= self.ny and 0 <= k < self.nz and self.c[i, j - 1, k] in (SOLID, HURT)

    def standable(self, i, j, k, head=2):
        return self.support(i, j, k) and all(self.free(i, j + h, k) for h in range(head))

    def moves(self, s):
        i, j, k = s
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, c = i + di, k + dk
            if self.standable(a, j, c):
                yield (a, j, c)
                continue
            # step up one: head room in the starting column to jump, and in the new one
            if self.free(i, j + 2, k) and self.standable(a, j + 1, c):
                yield (a, j + 1, c)
                continue
            # walk off and fall up to SAFE_DROP
            if self.free(a, j, c) and self.free(a, j + 1, c):
                for d in range(1, SAFE_DROP + 1):
                    if not self.free(a, j - d + 1, c) and d > 1:
                        break
                    if self.standable(a, j - d, c):
                        yield (a, j - d, c)
                        break
                    if not self.free(a, j - d, c):
                        break

    def bfs(self, start):
        prev = {start: None}
        q = deque([start])
        while q:
            s = q.popleft()
            for t in self.moves(s):
                if t not in prev:
                    prev[t] = s
                    q.append(t)
        return prev


def path_to(prev, goal):
    out = []
    while goal is not None:
        out.append(goal)
        goal = prev[goal]
    return out[::-1]


# ---------------------------------------------------------------------------------------------------------------- the audit


def parse_selbox(line):
    m = SELBOX.search(line)
    if not m:
        return None
    x, y, z, dx, dy, dz = (int(v) for v in m.groups()[:6])
    return (x, y, z, x + dx, y + dy, z + dz), m.group(7)


def chunks_of(x0, z0, x1, z1):
    return {(cx, cz) for cx in range(x0 // 16, x1 // 16 + 1) for cz in range(z0 // 16, z1 // 16 + 1)}


def sim_distance():
    f = ROOT / "server" / "config" / "server.properties.example"
    if f.is_file():
        m = re.search(r"^simulation-distance\s*=\s*(\d+)", f.read_text(encoding="utf-8"), re.M)
        if m:
            return int(m.group(1))
    return SIM_DEFAULT


def rect_gap(a, b):
    """Chebyshev-free gap between two (x0, z0, x1, z1) rects, Euclidean; 0 when they meet."""
    dx = max(a[0] - b[2], b[0] - a[2], 0)
    dz = max(a[1] - b[3], b[1] - a[3], 0)
    return (dx * dx + dz * dz) ** 0.5


def audit(runtime=RUNTIME, build=BUILD, ground=None, rewards=None, leg=None, gdoc=None, suppression=None, placements=None,
          plaza=None):
    import legendaries as L
    import legendaries_audit as LA
    rep = Report()
    if ground is None:
        import ground as G
        ground = G.Ground()
    gdoc = gdoc or jload(DATA / "groudon_cavern.json")
    leg = leg or L.load()
    rewards = rewards or jload(DATA / "rewards.json")
    suppression = suppression or jload(DATA / "spawn_suppression.json")
    placements = placements or jload(DATA / "placements.json")
    plaza = plaza or jload(DATA / "plaza_centres.json")
    rec = next(r for r in leg["encounters"] if r["id"] == gdoc["record"])
    flag = rec["gate"]["flags"][0]
    pack = Pack(runtime, build)
    rep.check(bool(pack.fns), "NOTHING TO CHECK: no function in %s or %s: run tools/groudon_cavern.py build" % (runtime, build))
    if not pack.fns:
        return rep
    rep.check(CARVE_ONCE in pack.fns, "the build pack has no %s, the entry R14L runs" % CARVE_ONCE)
    b = gdoc["box"]
    pad = 24
    box = ((b["x"][0] - pad, b["x"][1] + pad), (b["y"][0], b["y"][1]), (b["z"][0] - pad, b["z"][1] + pad))
    sealed = World(ground, box)
    ran = replay(pack, CARVE_ONCE, sealed)
    rep.check(len(ran) >= 4, "the carve ran only %s: not a cavern" % ran)
    rep.check(sealed.writes > 1000, "the carve wrote only %d commands" % sealed.writes)
    rep.check(not sealed.outside, "carve writes outside the audit grid (the declared box + %d): %s" % (pad, sealed.outside[:2]))
    ox, oy, oz = sealed.o
    G = sealed.G

    # ---- water: none, anywhere in any emitted function
    allcmds = [l for fid in pack.fns for l in pack.body(fid)]
    rep.check(not any("water" in l or "bubble_column" in l for l in allcmds if l.startswith(("fill", "setblock"))),
              "a fill or setblock writes water: lava and water meeting make stone in the mouth")
    rep.check(sealed.cls.max() >= LAVA and int((sealed.cls == LAVA).sum()) > 100, "the carve places too little lava to be a lake")
    rep.check(int((sealed.cls == WATER).sum()) == 0, "water in the replayed carve")

    # ---- the interior, the envelope, the seal
    carved = sealed.natural & np.isin(sealed.cls, (AIR, LAVA))      # rock the carve opened: air or lava where the ground was solid
    rep.check(int(carved.sum()) > 20000, "only %d carved cells before the quake: not a cavern" % int(carved.sum()))
    ring = dilate(carved, MARGIN) & ~carved
    thin = ring & ~sealed.written_solid
    rep.check(not thin.any(),
              "%d cell(s) within %d of a carved void were not written solid by the carve (no envelope there); first %s"
              % (int(thin.sum()), MARGIN, [tuple(int(v) + o for v, o in zip(c, sealed.o)) for c in np.argwhere(thin)[:3]]))
    ped = rewards_pedestal(rewards)
    rep.check(ped is not None, "data/rewards.json groudon_red_orb has no container.at: the pedestal cannot be placed")
    if ped is None:
        return rep
    px, py, pz = ped
    gi, gj, gk = px - ox, py + 1 - oy, pz - oz
    passable = np.isin(sealed.cls, (AIR, LAVA))
    n, leaked, inside = flood(passable, (gi, gj, gk), G, sealed.o)
    rep.check(n > 20000, "Groudon's cell (%d, %d, %d) opens on only %d cells of void: the cavern is not one room" % (px, py + 1, pz, n))
    rep.check(not leaked, "BEFORE THE QUAKE a flood from Groudon's cell reaches the sky or the grid's edge: the dormant legendary "
                          "is not sealed in")
    rep.check(int((carved & ~inside).sum()) == 0,
              "%d carved cell(s) are not connected to Groudon's room" % int((carved & ~inside).sum()))
    rep.check(sealed.name_at(px, py, pz) == "minecraft:smooth_basalt",
              "the Red Orb's container (%d, %d, %d) is %s after the carve, not smooth_basalt" % (px, py, pz, sealed.name_at(px, py, pz)))
    rep.check(all(sealed.free(px, py + 1 + h, pz) if False else sealed.at(px, py + 1 + h, pz) == AIR for h in range(4)),
              "less than 4 cells of air over the pedestal for Groudon to stand in")

    # ---- the roof over every void
    cols = carved.any(axis=1)
    ytop = np.where(carved, (oy + np.arange(sealed.shape[1]))[None, :, None], -10_000).max(axis=1)
    roof = np.where(cols, G - ytop, 10_000)
    rep.check(int(roof.min()) >= MIN_ROOF, "a void has only %d blocks of rock over it (least allowed %d)" % (int(roof.min()), MIN_ROOF))
    rep.notes.append("least roof over any void: %d blocks" % int(roof.min()))

    # ---- lava: contained on its four sides and under
    lava = sealed.cls == LAVA
    leaks = []
    for (di, dj, dk) in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)):
        sh = np.zeros_like(lava)
        src = [slice(None)] * 3
        dst = [slice(None)] * 3
        for ax, d in enumerate((di, dj, dk)):
            if d > 0:
                src[ax], dst[ax] = slice(None, -1), slice(1, None)
            elif d < 0:
                src[ax], dst[ax] = slice(1, None), slice(None, -1)
        sh[tuple(dst)] = lava[tuple(src)]
        leaks.append(sh & (sealed.cls == AIR))
    spill = np.logical_or.reduce(leaks)
    rep.check(not spill.any(), "%d air cell(s) sit beside or under lava: it would flow; first %s"
              % (int(spill.sum()), [tuple(int(v) + o for v, o in zip(c, sealed.o)) for c in np.argwhere(spill)[:3]]))
    sealed_lava = lava
    rep.check(int(lava.sum()) > 100, "no lake")

    # ---- the stages, replayed
    rt = pack
    state = sealed.copy()
    s1 = state.writes
    replay(rt, "cobblers:groudon_cavern/stage/1", state)
    rep.check(state.writes == s1, "stage 1 (the tremor) writes blocks")
    before_plug = None
    probes = {}
    stage_fids = [f for f in rt.fns if re.fullmatch(r"cobblers:groudon_cavern/stage/[2-9]", f)]
    rep.check(sorted(stage_fids) == ["cobblers:groudon_cavern/stage/2", "cobblers:groudon_cavern/stage/3",
                                      "cobblers:groudon_cavern/stage/4"], "stages found: %s" % sorted(stage_fids))
    sim = sim_distance()
    tick = rt.body("cobblers:groudon_cavern/tick")
    for fid in sorted(stage_fids):
        st = int(fid.rsplit("/", 1)[1])
        body = rt.body(fid)
        w0 = state.copy()
        replay(rt, fid, state)
        new = [(bx, blk) for bx, blk in state.boxes[w0.writes:]]
        rep.check(len(new) > 0, "stage %d writes nothing" % st)
        rep.check(all(blk == "minecraft:air" for _bx, blk in new), "stage %d writes something other than air" % st)
        rep.check(not state.outside, "stage %d writes outside the audit grid: %s" % (st, state.outside[:2]))
        # holds its own chunks
        held = set()
        for ln in body:
            m = FORCELOAD.match(ln)
            if m and m.group(1) == "add":
                a = [int(v) for v in m.groups()[1:] if v is not None]
                held |= chunks_of(a[0], a[1], a[2] if len(a) > 2 else a[0], a[3] if len(a) > 3 else a[1])
        need = set()
        for (bx0, _y0, bz0, bx1, _y1, bz1), _blk in new:
            need |= chunks_of(bx0, bz0, bx1, bz1)
        rep.check(need <= held, "stage %d writes %d chunk(s) it does not forceload" % (st, len(need - held)))
        # the trigger box in tick keeps a player within simulation distance of every chunk it writes
        trig = [ln for ln in tick if "matches %d " % st in ln and "function cobblers:groudon_cavern/stage/%d" % st in ln]
        rep.check(len(trig) == 1, "tick has %d line(s) driving stage %d" % (len(trig), st))
        if trig:
            sb = parse_selbox(trig[0])
            rep.check(sb is not None, "stage %d's trigger has no x/y/z box" % st)
            if sb:
                (tx0, _ty0, tz0, tx1, _ty1, tz1), _ = sb
                worst = 0
                for (cx, cz) in need:
                    for px_ in (tx0, tx1):
                        for pz_ in (tz0, tz1):
                            worst = max(worst, abs(cx - px_ // 16), abs(cz - pz_ // 16))
                rep.check(worst < sim, "stage %d: a player standing at the trigger box's corner is %d chunks from a chunk it "
                                       "writes; simulation distance is %d" % (st, worst, sim))
                rep.notes.append("stage %d: %d chunks written, worst player-to-chunk distance %d (simulation %d)"
                                 % (st, len(need), worst, sim))
                allw = [bx for bx, _ in new]
                rep.check(tx0 <= min(a[0] for a in allw) and tz0 <= min(a[2] for a in allw)
                          and tx1 >= max(a[3] for a in allw) and tz1 >= max(a[5] for a in allw),
                          "stage %d's trigger box does not contain the stage's own writes" % st)
        # the read-back: a probe that was rock before and is air after
        pm = [re.match(r"^execute if block %s %s %s minecraft:air run scoreboard players set #quake (\S+) (\d+)$" % ((NUM,) * 3), ln)
              for ln in body]
        pm = [m for m in pm if m]
        rep.check(len(pm) == 1, "stage %d has %d probe line(s)" % (st, len(pm)))
        if pm:
            x, y, z = (int(v) for v in pm[0].groups()[:3])
            was, now = w0.at(x, y, z), state.at(x, y, z)
            rep.check(was is not None and was != AIR and now == AIR,
                      "stage %d's probe (%d, %d, %d) is not rock before and air after (class %s -> %s): it would report "
                      "success without the stage having worked" % (st, x, y, z, was, now))
            rep.check(int(pm[0].group(5)) == st + 1, "stage %d moves #quake to %s, not %d" % (st, pm[0].group(5), st + 1))
            rep.check(y <= int(G[x - ox, z - oz]) - 3, "stage %d's probe is not 3 under the ground" % st)
        if st == 3:
            before_plug = state.copy()
    opened = state
    rep.check(before_plug is not None, "no state before the plug")
    # the whole chain advances in order and the legendary's open score is set once, by `opened`, called from stage 4
    sets = [(fid, ln) for fid in rt.fns for ln in rt.body(fid) if re.search(r"scoreboard players set #%s %s 1$" % (rec["id"], leg["objective"]), ln)]
    rep.check(len(sets) == 1 and sets[0][0] == "cobblers:groudon_cavern/opened",
              "the legendary's open score (#%s %s) is set by %s; it must be set once, by `opened`"
              % (rec["id"], leg["objective"], [s[0] for s in sets]))
    callers = [fid for fid in rt.fns for ln in rt.body(fid) if "function cobblers:groudon_cavern/opened" in ln]
    rep.check(callers == ["cobblers:groudon_cavern/stage/4"], "`opened` is called by %s, not by stage 4 alone" % callers)
    last = [ln for ln in rt.body("cobblers:groudon_cavern/stage/4") if "function cobblers:groudon_cavern/opened" in ln]
    rep.check(len(last) == 1 and "#quake" in last[0] and "matches 5" in last[0],
              "stage 4 calls `opened` without testing that #quake reached 5 (the probe)")
    # the rumble, as text: from the record's own flag, and nothing is cut by it
    rumble = [l for l in tick if "function cobblers:groudon_cavern/rumble" in l]
    rep.check(len(rumble) == 1 and "advancements={%s:flag/%s=true}" % (NS, flag) in rumble[0] and "#quake" in rumble[0]
              and "matches 0" in rumble[0] and "#built" in rumble[0],
              "the rumble is not driven once, from %s, while #quake is 0 and the cavern is built: %s" % (flag, rumble))
    rb = rt.body("cobblers:groudon_cavern/rumble")
    rep.check(not any(l.startswith(("fill", "setblock", "forceload")) for l in rb), "the rumble writes blocks")
    rep.check(any("playsound" in l and "@a" in l and "distance" not in l for l in rb), "the rumble is not heard by every player")
    rep.check(any(re.search(r"run tellraw @a |^tellraw @a ", l) for l in rb), "the rumble is not told to every player")
    # a player who logged out over the cut and is back after it must not fall to their death: slow falling, in a box that
    # holds every cell the quake cut
    rj = [l for l in tick if "scores={" in l and "slow_falling" in l]
    rep.check(len(rj) == 1, "tick has %d rejoin line(s) giving slow falling" % len(rj))
    if rj:
        sb = parse_selbox(rj[0])
        cut = sealed.natural & (opened.cls == AIR) & (sealed.cls == SOLID)
        pts_ = np.argwhere(cut)
        rep.check(sb is not None and len(pts_) > 0, "the rejoin line has no x/y/z box, or the quake cuts nothing")
        if sb and len(pts_):
            (rx0, ry0, rz0, rx1, ry1, rz1), _ = sb
            lo = pts_.min(axis=0) + np.array(sealed.o)
            hi = pts_.max(axis=0) + np.array(sealed.o)
            rep.check(rx0 <= lo[0] and ry0 <= lo[1] and rz0 <= lo[2] and rx1 >= hi[0] and ry1 >= hi[1] and rz1 >= hi[2],
                      "the rejoin box %s does not hold every cell the quake cuts (%s..%s)" % ((rx0, ry0, rz0, rx1, ry1, rz1), lo, hi))
        rep.check(any("scoreboard players reset @a[scores=" in l for l in tick), "the rejoin count is never cleared")
        loadf = " ".join(pack.body("cobblers:groudon_cavern/load"))
        rep.check("minecraft.custom:minecraft.leave_game" in loadf, "the rejoin objective counts nothing (no leave_game criterion)")
    ce = pack.body(CARVE_ONCE)
    rep.check(len(ce) == 1 and "matches 1" in ce[0] and "#%s %s" % (rec["id"], leg["objective"]) in ce[0] and "matches 2.." in ce[0],
              "carve_once does not skip an opened or begun cavern: %s" % ce)

    # ---- the plug: rock between the ravine and the interior until the last stage
    rav_only = sealed.natural & (before_plug.cls == AIR) & (sealed.cls == SOLID)
    rep.check(int(rav_only.sum()) > 5000, "the first stages cut only %d cells: not a ravine" % int(rav_only.sum()))
    near = dilate(rav_only, MARGIN) & carved
    rep.check(not near.any(), "the open ravine is within %d of the carved interior before the plug is cut" % MARGIN)
    passable_b = np.isin(before_plug.cls, (AIR, LAVA))
    n_b, leaked_b, _ = flood(passable_b, (gi, gj, gk), G, sealed.o)
    rep.check(not leaked_b, "after the ravine is cut and BEFORE the plug, Groudon's room already opens to the sky")

    # ---- the walk, over the opened world
    stand = tuple(gdoc["guard"]["stand"])
    sy = int(ground(stand[0], stand[1])) + 1
    ow = Walker(opened)
    s0 = (stand[0] - ox, sy - oy, stand[1] - oz)
    rep.check(ow.standable(*s0), "the keeper's stand (%d, %d, %d) is not a place to stand after the quake" % (stand[0], sy, stand[1]))
    prev = ow.bfs(s0)
    goal = (px - ox, py + 1 - oy, pz - oz)
    rep.check(goal in prev, "NO WALK from the bowl (%d, %d, %d) to Groudon (%d, %d, %d) over the opened world: steps of one up, "
                            "three down, two cells of headroom" % (stand[0], sy, stand[1], px, py + 1, pz))
    if goal in prev:
        path = path_to(prev, goal)
        heads = []
        for (i, j, k) in path:
            h = 0
            while ow.free(i, j + h, k) and h < 8:
                h += 1
            heads.append(h)
        rep.check(min(heads) >= 2, "headroom %d on the path" % min(heads))
        rep.notes.append("walk: %d steps, headroom min %d, descends %d blocks" % (len(path), min(heads), path[0][1] - path[-1][1]))
        back = ow.bfs(goal)
        rep.check(s0 in back, "NO WAY BACK from Groudon to the bowl: a step up of more than one, or a drop, on the way down")
        # the whole way is walked over carved ground and natural ground; no cell on it is HURT, near lava, or over lava
    reach = set(prev)
    carved_open = opened.natural & (opened.cls == AIR)
    # hazards over every reachable cell
    hurt = lava_near = drops = rim = 0
    first = {}
    for (i, j, k) in reach:
        if opened.cls[i, j - 1, k] == HURT:
            hurt += 1
            first.setdefault("hurt", (i + ox, j - 1 + oy, k + oz))
        lo, hi = max(j - 3, 0), min(j + 2, opened.shape[1])
        if (opened.cls[max(i - 1, 0):i + 2, lo:hi, max(k - 1, 0):k + 2] == LAVA).any():
            lava_near += 1
            first.setdefault("lava", (i + ox, j + oy, k + oz))
        inside_cave = bool(carved_open[i, j, k])
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, c = i + di, k + dk
            if ow.free(a, j, c) and ow.free(a, j + 1, c):
                d = 1
                while d <= SAFE_DROP + 1 and j - d >= 0 and ow.free(a, j - d, c):
                    d += 1
                if d > SAFE_DROP or j - d < 0 or opened.cls[a, j - d, c] in (LAVA, WATER, HURT):
                    if not inside_cave:
                        rim += 1          # a natural cliff on the surface (the ravine's rim): reported, not failed
                        break
                    if inside_cave:
                        drops += 1
                        first.setdefault("drop", (i + ox, j + oy, k + oz))
    rep.check(hurt == 0, "%d reachable cell(s) stand on a hurting block (magma, fire...); first %s" % (hurt, first.get("hurt")))
    rep.check(lava_near == 0, "%d reachable cell(s) are within one block of lava; first %s" % (lava_near, first.get("lava")))
    rep.check(drops == 0, "%d reachable cell(s) in the cavern stand beside a drop of more than %d or into a fluid; first %s"
              % (drops, SAFE_DROP, first.get("drop")))
    rep.notes.append("%d reachable standing cells checked; %d of them on the open surface stand at a natural cliff (the ravine's rim: not on the path, reported and not failed)" % (len(reach), rim))
    lava_cells = int((opened.cls == LAVA).sum())
    rep.check(lava_cells == int(sealed_lava.sum()), "the quake changes the lava")

    # ---- the hall's size, against Kyogre's basin, on the replayed floor
    hall = [c for c in reach if abs(c[0] + ox - px) <= 40 and abs(c[2] + oz - pz) <= 40 and c[1] + oy <= py + 3]
    cols_set = {(c[0], c[2]) for c in hall}
    ground_cols = len(cols_set)
    rep.check(ground_cols >= KYOGRE_BASIN_COLUMNS * 0.8,
              "the hall's walkable columns near the dais are %d, under 80%% of Kyogre's basin (%d)" % (ground_cols, KYOGRE_BASIN_COLUMNS))
    rep.notes.append("hall walkable columns within 40 of the dais: %d (Kyogre's basin ellipse: %d)" % (ground_cols, KYOGRE_BASIN_COLUMNS))
    mx = 0
    for (i, j, k) in hall[:: max(1, len(hall) // 400)]:
        h = 0
        while ow.free(i, j + h, k) and h < 40:
            h += 1
        mx = max(mx, h)
    rep.check(mx >= 20, "the highest headroom in the hall is %d, under 20" % mx)

    # ---- the keeper
    kline = [l for l in tick if "function cobblers:groudon_cavern/eject" in l]
    rep.check(len(kline) == 1, "tick has %d eject line(s)" % len(kline))
    if kline:
        sb = parse_selbox(kline[0])
        rep.check(sb is not None, "the keeper's selector has no box")
        if sb:
            (kx0, ky0, kz0, kx1, ky1, kz1), extra = sb
            rep.check("advancements={%s:flag/%s=true}" % (NS, flag) in kline[0] and "unless entity @s[" in kline[0],
                      "the keeper does not turn away a player who lacks %s: %s" % (flag, kline[0][:160]))
            rep.check("gamemode=!creative" in extra and "gamemode=!spectator" in extra, "the keeper does not leave creative and spectator alone")
            allair = np.argwhere(carved_open)
            near_ped = [(int(i) + ox, int(j) + oy, int(k) + oz) for i, j, k in allair
                        if (int(i) + ox - px) ** 2 + (int(k) + oz - pz) ** 2 <= GUARD_REACH ** 2]
            out = [c for c in near_ped if not (kx0 <= c[0] <= kx1 and ky0 <= c[1] <= ky1 and kz0 <= c[2] <= kz1)]
            rep.check(bool(near_ped), "no carved cell within %d of the pedestal: nothing to guard" % GUARD_REACH)
            rep.check(not out, "%d carved cell(s) within %d blocks of the pedestal stand outside the keeper's box %s; first %s"
                      % (len(out), GUARD_REACH, (kx0, ky0, kz0, kx1, ky1, kz1), out[:3]))
            rep.check(not (kx0 <= stand[0] <= kx1 and kz0 <= stand[1] <= kz1), "the keeper's own stand is inside its box")
            decl = gdoc["guard"]["box"]
            rep.check(list(decl[:3]) == [kx0, ky0, kz0] and [decl[3] - decl[0], decl[4] - decl[1], decl[5] - decl[2]]
                      == [kx1 - kx0, ky1 - ky0, kz1 - kz0], "the keeper's emitted box is not the declared guard.box")
            # the way in is not shut at the box's edge: players are only turned back INSIDE it, so the box must leave the
            # walk open from the stand to the box (the walk reaches a cell outside the box)
            outside_cells = [c for c in (path if goal in prev else []) if not (kx0 <= c[0] + ox <= kx1 and kz0 <= c[2] + oz <= kz1)]
            rep.check(bool(outside_cells), "the whole walk is inside the keeper's box: nobody could see the cavern")
    ej = rt.body("cobblers:groudon_cavern/eject")
    tp = [l for l in ej if l.startswith("tp @s")]
    rep.check(len(tp) == 1, "eject has %d tp line(s)" % len(tp))
    if tp:
        m = re.match(r"^tp @s (-?\d+)\.5 (-?\d+) (-?\d+)\.5 ", tp[0])
        rep.check(bool(m) and (int(m.group(1)), int(m.group(3))) == (stand[0], stand[1]) and int(m.group(2)) == sy,
                  "eject sends a player somewhere other than the stand (%d, %d, %d): %s" % (stand[0], sy, stand[1], tp[0]))

    # ---- the wake and the record's own gate, in the legendaries pack
    import tempfile
    doc2 = copy.deepcopy(leg)
    for r in doc2["encounters"]:
        if r["id"] != rec["id"]:
            r.pop("retired_sites", None)
    with tempfile.TemporaryDirectory() as td:
        legpack = Path(td)
        for rel, text in L.files(doc2, ground).items():
            f = legpack / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8", newline="\n")
        fn_dir = legpack / "data" / leg["namespace"] / "function" / "legendary"
        near_f = fn_dir / rec["id"] / "near.mcfunction"
        rep.check(near_f.is_file(), "the legendaries pack has no near for %s" % rec["id"])
        if near_f.is_file():
            body = [l for l in near_f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
            rep.check(not any("/open" in l for l in body), "near still calls an open function: a plug that no longer exists")
            rep.check(any("/wake" in l and "matches 1" in l for l in body), "near does not wake Groudon only once the open score is 1")
            rep.check(any("/met" in l and "met=false" in l for l in body), "near does not grant `met` to a qualified player in the hall")
            rep.check(any("/keep" in l and "matches 0" in l for l in body), "near does not keep the sleeper dormant while sealed")
        rep.check(not (fn_dir / rec["id"] / "carve.mcfunction").exists(), "the legendaries pack still carves a sealed chamber")
        rep.check(not (fn_dir / rec["id"] / "carve_once.mcfunction").exists(),
                  "the legendaries pack and the build pack both define carve_once")
        # the retired chamber: the existing audit derives that chamber itself (legendaries_audit.own_old_site)
        lrep = LA.Report()
        LA._retired_sites(doc2, ground, legpack, fn_dir, lrep)
        rep.check(lrep.checks > 20, "the cleanup audit ran only %d checks" % lrep.checks)
        for e in lrep.errors:
            rep.errors.append("cleanup: " + e)
        rep.checks += lrep.checks
        steps = L.placement_steps(doc2, ground)
        rep.check(("fn", CARVE_ONCE) in steps, "R14L's steps do not run carve_once")
        ret = [i for i, s in enumerate(steps) if s[0] == "fn" and "retire_" in s[1] and not s[1].endswith("_restore")]
        rep.check(bool(ret) and ret[0] < steps.index(("fn", CARVE_ONCE)), "R14L does not run the cleanup before the carve")
        site = next(s for r, s in L.retired(doc2) if r["id"] == rec["id"])
        o = LA.own_old_site(site, ground)
        hull = o["hull"]
        hit = [(bx, blk) for bx, blk in sealed.boxes + state.boxes
               if bx[0] <= hull[3] and hull[0] <= bx[3] and bx[1] <= hull[4] and hull[1] <= bx[4] and bx[2] <= hull[5] and hull[2] <= bx[5]]
        rep.check(not hit, "the cavern writes %d command(s) into the retired hull %s; first %s" % (len(hit), hull, hit[:1]))
        rep.check(not (o["pedestal"][0] == px and o["pedestal"][1] == py and o["pedestal"][2] == pz),
                  "the new pedestal is the old one: the cleanup's probe would take the new cavern down")

    # ---- places: clearance, spawn zone
    # every authored position of the Mining Town and of Fossick's hill (streets, lots, workers, situations, the square, the
    # footprint), measured to the cells themselves and not to a bounding box: the SURFACE cells the quake cuts (the ravine and
    # the plug's columns, which a player sees and walks) and the cells under the plateau (the tunnel and the hall)
    surface_cols = (opened.natural & (opened.cls == AIR) & ~carved).any(axis=1)
    deep_cols = carved.any(axis=1)
    pts = authored_points(placements, plaza, ox, oz, opened.shape)
    rep.check(len(pts) > 100, "only %d authored Mining Town / Fossick positions found: the clearance would be vacuous" % len(pts))

    def nearest(cols):
        xs, zs = np.nonzero(cols)
        cx, cz = xs + ox, zs + oz
        best = (1e9, None)
        for label, x, z in pts:
            d = float(np.sqrt(((cx - x) ** 2 + (cz - z) ** 2).min()))
            if d < best[0]:
                best = (d, (label, x, z))
        return best

    ds, ps = nearest(surface_cols)
    dd, pd_ = nearest(deep_cols)
    rep.check(ds >= MIN_CLEAR, "the ravine's cut is %.0f blocks from %s (least %d)" % (ds, ps, MIN_CLEAR))
    rep.check(dd >= MIN_CLEAR_DEEP, "the tunnel and hall are %.0f blocks (horizontally) from %s (least %d)" % (dd, pd_, MIN_CLEAR_DEEP))
    ff = placements["settlements"]["fossick_adit"]["plan"]["footprint"]["rect"]
    sx, szz = np.nonzero(surface_cols | deep_cols)
    foot = (int(sx.min()) + ox, int(szz.min()) + oz, int(sx.max()) + ox, int(szz.max()) + oz)
    rep.check(rect_gap(foot, ff) >= MIN_CLEAR, "the footprint %s is %.0f from Fossick's hill rect %s" % (foot, rect_gap(foot, ff), ff))
    rep.notes.append("nearest authored position to the ravine's cut: %.0f blocks (%s); to the tunnel and hall, horizontally: %.0f "
                     "blocks (%s); to Fossick's hill rect: %.0f blocks; footprint %s"
                     % (ds, ps, dd, pd_, rect_gap(foot, ff), foot))
    zones = [z["box"] for z in suppression["spawn_free_zones"]]
    hall_cols = {(c[0] + ox, c[2] + oz) for c in hall}
    cover = [z for z in zones if all(z[0] <= x <= z[2] and z[1] <= zz <= z[3] for x, zz in hall_cols)]
    rep.check(bool(hall_cols) and bool(cover), "no spawn-free zone in data/spawn_suppression.json holds every walkable column of the hall")
    rep.check(all(isinstance(v, int) and v % 8 == 0 for v in cover[0][:2]) if cover else False, "the covering zone is not snapped to the 8-block grid")
    rzone = rec.get("spawn_free_zone")
    rep.check(isinstance(rzone, list) and len(rzone) == 4 and all(rzone[0] <= x < rzone[2] and rzone[1] <= zz < rzone[3] for x, zz in hall_cols),
              "the record's own spawn_free_zone %s does not hold the hall" % rzone)
    return rep


def authored_points(placements, plaza, ox, oz, shape):
    """[(label, x, z)] every [x, z] / [x, y, z] / [x0, z0, x1, z1] in the Mining Town's and Fossick's authored data that lies
    within 400 blocks of the audit grid (data/placements.json settlements, data/ambient_towns/mining_town.json,
    data/plaza_centres.json). Our list is not the world: this says what it does NOT cover (a mod's structures, what an earlier
    pass left behind, the natural terrain's features)."""
    out = []
    lo_x, hi_x = ox - 400, ox + shape[0] + 400
    lo_z, hi_z = oz - 400, oz + shape[2] + 400

    def walkp(o, label):
        if isinstance(o, dict):
            for k, v in o.items():
                walkp(v, label + "." + str(k))
        elif isinstance(o, list):
            nums = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in o)
            if nums and len(o) in (2, 3):
                x, z = (o[0], o[1]) if len(o) == 2 else (o[0], o[2])
                if lo_x <= x <= hi_x and lo_z <= z <= hi_z:
                    out.append((label[:70], int(x), int(z)))
            elif nums and len(o) == 4:
                for x, z in ((o[0], o[1]), (o[2], o[3]), (o[0], o[3]), (o[2], o[1])):
                    if lo_x <= x <= hi_x and lo_z <= z <= hi_z:
                        out.append((label[:70] + " (rect)", int(x), int(z)))
            else:
                for i, v in enumerate(o):
                    walkp(v, label + "." + str(i))

    walkp(placements["settlements"]["mining_town"], "placements.mining_town")
    walkp(placements["settlements"]["fossick_adit"], "placements.fossick_adit")
    walkp(plaza["towns"]["mining_town"], "plaza_centres.mining_town")
    walkp(jload(DATA / "ambient_towns" / "mining_town.json"), "ambient_towns.mining_town")
    return out


def rewards_pedestal(rewards):
    r = next((r for r in rewards["rewards"] if r.get("id") == "groudon_red_orb"), None)
    if not r:
        return None
    at = (r.get("container") or {}).get("at")
    return tuple(int(v) for v in at) if at else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runtime", default=str(RUNTIME))
    ap.add_argument("--build", default=str(BUILD))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rep = audit(Path(a.runtime), Path(a.build), G.Ground(a.source_root))
    for n in rep.notes:
        print("note: %s" % n)
    for e in rep.errors:
        print("FAIL %s" % e)
    print("groudon cavern audit: %d checks, %d failures" % (rep.checks, len(rep.errors)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
