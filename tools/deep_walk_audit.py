#!/usr/bin/env python
"""Walk the Windward Deep as a player would, through the blocks the packs actually write. Offline and independent.

tools/deep_city_audit.py checks each street level on its own and never the stair between two of them, which is how a
city whose stair towers could not be climbed passed it (docs/world-building/DEEP_STATUS.md section 6). This replays
the emitted functions, in the order tools/reapply.py runs them, over a world built from the canonical heightmap, and
walks it:

  the world    tools/ground.py's ground (rounded), rock at and under it, air over it, water up to the sea level in
               data/world.json; then every fill, setblock and `place template` of the packs in REPLAY, in their index
               order: the Rift skin (R1), the pit (R9B, its `replace #cobblers:rift_void` evaluated against the cells
               as they stand), Victory Road (R9C), the city (R9DC), the relic site (R9RU), the Habitat Blocks (R9E) and
               the signposts (R15). Every OTHER built pack that writes in the box is a problem until it is listed,
               because a list of what we replay is not the world (CLAUDE.md, "our list is not the world")
  the player   stands where two cells are clear over a floor; walks to a 4-neighbour at the same height; steps up one
               with a third cell clear over the cell he leaves (feet, head, and the head's rise as he climbs); drops up
               to three with his body's cells clear on the way down; jumps a one-wide gap, never more; never climbs a
               ladder or rides a lift (data/rift_deep.json's lifts are a second way; this is the walk). A wall sign,
               torch, plate, carpet or open-able door is no obstacle; an iron door is one unless an opener stands by
               it; a fence or wall also closes the cell above it. The HQ guard (an entity) occupies his two cells,
               and talking to him (within his reach, read from the relic pack's admit function) moves the player to
               the function's tp target
  the plan     derived/deep_city/plan.json (plan data, allowed): the towers, the Sink Gate, the spire's tiers and
               crown, the HQ. Nothing is imported from tools/deep_city.py or its helpers

What must hold, from the HQ's doorstep (data/relic_underground.json geometry.hq.guard.front_step):

  rings      every tread level of the pit (read from the pit pack's own air fills) has walked street on it
  towers     every stair tower climbs on its own, walked inside its footprint from its door to its upper street,
             except the towers whose plan records `headroom_blocked_by_lift`, which must NOT climb, and must be stopped
             by that lift; every pair of rings keeps a tower that climbs. A failed climb names the step and the block
             over it
  roofed     a sweep, not a list: every pair of stair treads one apart, anywhere in the box, where a step up between
             them is refused only for the third cell over the lower one. The roofed lift tower must be the only one
  sink gate  climbs from ring 0's street to the lip on its own, and the lip is walked
  arena      every tier's stand box and the crown deck are walked
  sign       the HQ door's wall sign is in none of the door's, the doorstep's or the guard's cells, hangs on a solid
             block, and the doorstep and the guard's seat are still places to stand
  lights     every way light data/relic_underground.json composition.way_lights declares is a floor the walk stands
             on (through the guard); no lantern hangs at head height over a floor the walk reaches

Not covered: anything a running server decides. Lifts, ladders, hatches, entity collision other than the guard's,
mob spawning, whether the guard admits (tools/relic_underground_audit.py checks his stages), slabs and stairs as
full blocks, the sculpted Rift where it differs from the heightmap and the skin does not write it, and
`data merge`/`execute` commands.

    python tools/deep_walk_audit.py [--source-root <root>] [--report derived/deep_walk/report.json]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

PACKS = ROOT / "build" / "datapacks"
PLAN = ROOT / "derived" / "deep_city" / "plan.json"
RELIC = ROOT / "data" / "relic_underground.json"
WORLD = ROOT / "data" / "world.json"
REPORT = ROOT / "derived" / "deep_walk" / "report.json"

# (reapply step, pack, function folder), in tools/reapply.py's order (tests/test_deep_walk_audit.py checks the order)
REPLAY = (("R1", "cobblers_rift", "rift"),
          ("R9B", "cobblers_deep", "deep"),
          ("R9C", "cobblers_vr_caves", "vr_caves"),
          ("R9DC", "cobblers_deep_city", "deep_city"),
          ("R9RU", "cobblers_relic_underground", "relic_underground"),
          ("R9E", "cobblers_habitats", "habitats"),
          ("R15", "cobblers_signs", "signs"))
# the box walked: the Deep's pit (tools/rift_deep.py model box 3341..3866, 2935..3509) and the relic site west of it,
# with a margin. Cells above Y1 are air, below Y0 rock
BOX = (3330, -32, 2925, 3875, 175, 3520)

AIR = "minecraft:air"
ROCK = "ground:rock"
WATER = "minecraft:water"
NUM = r"(-?\d+)"
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)(?: (replace|keep|hollow|outline|destroy|strict)(?: (\S+))?)?\s*$"
                  % ((NUM,) * 6))
SETB = re.compile(r"^setblock %s %s %s (.+?)\s*$" % ((NUM,) * 3))
SETB_MODE = re.compile(r"^(\S+) (replace|keep|destroy|strict)$")
PLACE = re.compile(r"^place template (\S+) %s %s %s(?: (none|clockwise_90|180|counterclockwise_90))?(?: (none|"
                   r"left_right|front_back))?(?: \S+)*\s*$" % ((NUM,) * 3))
TP = re.compile(r"^tp @s (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)(?: \S+ \S+)?$")
REACH = re.compile(r"^execute unless entity @s\[x=(-?\d+),y=(-?\d+),z=(-?\d+),distance=\.\.(\d+(?:\.\d+)?)\] "
                   r"run return fail$")
TALK = 3.0      # blocks: vanilla's entity interaction range, cell centre to the guard's seat


def base(state):
    return re.split(r"[\[{ ]", state, 1)[0]


# ------------------------------------------------------------------ what a block is to a walking player

PASS_EXACT = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:light", "minecraft:water",
              "minecraft:structure_void", "minecraft:ladder", "minecraft:vine", "minecraft:glow_lichen",
              "minecraft:redstone_wire", "minecraft:tripwire", "minecraft:cobweb", "minecraft:lever",
              "minecraft:short_grass", "minecraft:grass", "minecraft:tall_grass", "minecraft:fern",
              "minecraft:large_fern", "minecraft:dead_bush", "minecraft:snow", "minecraft:sculk_vein",
              "minecraft:hanging_roots", "minecraft:spore_blossom", "minecraft:pink_petals", "minecraft:seagrass",
              "minecraft:tall_seagrass", "minecraft:kelp", "minecraft:kelp_plant", "minecraft:sugar_cane",
              "minecraft:bubble_column", "minecraft:rail", "minecraft:nether_portal", "minecraft:fire", "minecraft:soul_fire"}
PASS_SUFFIX = ("_sign", "_banner", "torch", "_pressure_plate", "_button", "_carpet", "_rail",
               "_sapling", "_tulip", "_fungus", "_door", "_trapdoor", "_fence_gate", "_vines", "_plant",
               "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet", "oxeye_daisy", "cornflower",
               "lily_of_the_valley", "wither_rose", "torchflower", "red_mushroom", "brown_mushroom")
PASS_NOT = ("iron_door", "iron_trapdoor")          # an iron door or trapdoor needs an opener
TALL_SUFFIX = ("_fence", "_wall")                   # 1.5 high: the cell above is closed too
NOT_FLOOR_SUFFIX = ("lantern", "end_rod", "chain", "candle", "lightning_rod", "_head", "_skull", "flower_pot")
LIGHT_WORDS = ("lantern", "froglight", "glowstone", "shroomlight", "end_rod", "redstone_lamp")
OPENER_SUFFIX = ("_pressure_plate", "_button")


def kind(state):
    """(passable, floor, tall) for a block state: can a body stand in it, can a player stand on it, does it close the
    cell over it. Anything this does not know is solid, a floor, and not tall."""
    b = base(state)
    name = b.split(":", 1)[-1]
    if b in PASS_EXACT:
        return True, False, False
    if name in ("sea_lantern",):
        return False, True, False
    if name.endswith(PASS_NOT) or name in PASS_NOT:
        return False, True, False
    if name.endswith(PASS_SUFFIX):
        return True, False, False
    if name.endswith(TALL_SUFFIX) and not name.endswith(("_wall_sign", "_wall_torch", "_wall_banner", "_wall_head",
                                                         "_wall_skull", "_wall_fan", "_hanging_sign")):
        return False, False, True
    if name.endswith(NOT_FLOOR_SUFFIX) and "sea_lantern" not in name:
        return False, False, False
    return False, True, False


def is_light(state):
    n = base(state).split(":", 1)[-1]
    return any(w in n for w in LIGHT_WORDS)


def is_opener(state):
    n = base(state).split(":", 1)[-1]
    return n.endswith(OPENER_SUFFIX) or n == "lever"


# ------------------------------------------------------------------ the world, replayed

class World:
    """Block states over an inclusive box (x0, y0, z0, x1, y1, z1), stored [x, z, y] as palette indices."""

    def __init__(self, box):
        self.box = box
        x0, y0, z0, x1, y1, z1 = box
        self.NX, self.NY, self.NZ = x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1
        self.palette, self.pid = [], {}
        self.a = np.zeros((self.NX, self.NZ, self.NY), np.uint16)
        self.id(AIR)
        self.stats = {"writes": 0, "conditional_skipped": 0, "templates": 0}
        self.unparsed = []

    def id(self, state):
        i = self.pid.get(state)
        if i is None:
            i = len(self.palette)
            if i >= 65535:
                raise SystemExit("more than 65535 block states in the walk box")
            self.palette.append(state)
            self.pid[state] = i
        return i

    def lay_ground(self, ground_zx, sea_level=None):
        """ground_zx: (z, x) array of ground y over the box's columns. Rock at and under it, water to the sea."""
        x0, y0, z0 = self.box[:3]
        ys = np.arange(self.NY)[None, None, :] + y0
        g = ground_zx.T[:, :, None]
        rock = self.id(ROCK)
        self.a[ys <= g] = rock
        if sea_level is not None:
            self.a[(ys > g) & (ys <= sea_level)] = self.id(WATER)

    def _clip(self, x0, y0, z0, x1, y1, z1):
        bx0, by0, bz0, bx1, by1, bz1 = self.box
        lo = (max(x0, bx0), max(y0, by0), max(z0, bz0))
        hi = (min(x1, bx1), min(y1, by1), min(z1, bz1))
        if lo[0] > hi[0] or lo[1] > hi[1] or lo[2] > hi[2]:
            return None
        return (slice(lo[0] - bx0, hi[0] - bx0 + 1), slice(lo[2] - bz0, hi[2] - bz0 + 1),
                slice(lo[1] - by0, hi[1] - by0 + 1))

    def get(self, x, y, z):
        bx0, by0, bz0, bx1, by1, bz1 = self.box
        if not (bx0 <= x <= bx1 and bz0 <= z <= bz1):
            return None
        if y < by0:
            return ROCK
        if y > by1:
            return AIR
        return self.palette[int(self.a[x - bx0, z - bz0, y - by0])]

    def fill(self, x0, y0, z0, x1, y1, z1, state, mode=None, filt=None, tags=None):
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        z0, z1 = min(z0, z1), max(z0, z1)
        sl = self._clip(x0, y0, z0, x1, y1, z1)
        if sl is None:
            return
        self.stats["writes"] += 1
        i = self.id(state)
        sub = self.a[sl]
        if mode in (None, "replace", "destroy", "strict") and not filt:
            sub[...] = i
            return
        if mode == "replace":
            want = self._matcher(filt, tags)
            if want is None:
                self.stats["conditional_skipped"] += 1
                return
            lut = np.array([want(p) for p in self.palette], bool)
            sub[lut[sub]] = i
            return
        if mode == "keep":
            sub[sub == self.pid[AIR]] = i
            return
        if mode in ("hollow", "outline"):
            bx0, by0, bz0 = self.box[:3]
            xs = np.arange(sl[0].start, sl[0].stop) + bx0
            zs = np.arange(sl[1].start, sl[1].stop) + bz0
            ys = np.arange(sl[2].start, sl[2].stop) + by0
            edge = ((xs[:, None, None] == x0) | (xs[:, None, None] == x1) | (zs[None, :, None] == z0)
                    | (zs[None, :, None] == z1) | (ys[None, None, :] == y0) | (ys[None, None, :] == y1))
            sub[edge] = i
            if mode == "hollow":
                sub[~edge] = self.pid[AIR]
            return
        raise ValueError("fill mode %s" % mode)

    def _matcher(self, filt, tags):
        if filt.startswith("#"):
            vals = (tags or {}).get(filt[1:])
            if vals is None:
                return None
            return lambda p, v=set(vals): base(p) in v or (base(p) == ROCK and False)
        fb = base(filt)
        return lambda p: base(p) == fb

    def place_template(self, tpl, px, py, pz, rotation):
        """tpl: dict(size, palette [(name, props)], blocks [(x, y, z, state)]) as tools/structure_nbt.load gives;
        vanilla's StructureTemplate transform about the origin, no mirror."""
        self.stats["templates"] += 1
        rot = {None: 0, "none": 0, "clockwise_90": 1, "180": 2, "counterclockwise_90": 3}[rotation]
        names = []
        for name, props in tpl["palette"]:
            names.append(name + ("[%s]" % ",".join("%s=%s" % kv for kv in sorted(props.items())) if props else ""))
        for x, y, z, s in tpl["blocks"]:
            if rot == 0:
                wx, wz = px + x, pz + z
            elif rot == 1:
                wx, wz = px - z, pz + x
            elif rot == 2:
                wx, wz = px - x, pz - z
            else:
                wx, wz = px + z, pz - x
            if base(names[s]) == "minecraft:structure_void":
                continue
            self.fill(wx, py + y, wz, wx, py + y, wz, names[s])


def parse(line):
    """One command -> ("fill", args) / ("setblock", args) / ("place", args) / ("tp", ...) / None (not a block write) /
    ("unparsed", line) for a block write this cannot read (it fails closed)."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    m = FILL.match(s)
    if m:
        v = list(map(int, m.groups()[:6]))
        return ("fill", v + [m.group(7), m.group(8), m.group(9)])
    if s.startswith("fill "):
        return ("unparsed", s)
    m = SETB.match(s)
    if m:
        x, y, z = map(int, m.groups()[:3])
        rest = m.group(4)
        mm = SETB_MODE.match(rest)
        state, mode = (mm.group(1), mm.group(2)) if mm else (rest, None)
        return ("setblock", [x, y, z, state, mode])
    if s.startswith("setblock "):
        return ("unparsed", s)
    m = PLACE.match(s)
    if m:
        return ("place", [m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)])
    if s.startswith(("place ", "clone ")) or re.search(r" run (fill|setblock|clone|place) ", s):
        return ("unparsed", s)
    return None


def pack_functions(pack_dir, folder):
    """The pack's block functions in its index order, else every function in the folder, sorted."""
    fdir = Path(pack_dir) / "data" / "cobblers" / "function" / folder
    idx = fdir / "index.txt"
    if idx.is_file():
        return [fdir / (n.strip() + ".mcfunction") for n in idx.read_text(encoding="utf-8").split("\n") if n.strip()]
    return sorted(fdir.glob("*.mcfunction"))


def pack_tags(pack_dir):
    out = {}
    for f in (Path(pack_dir) / "data").glob("*/tags/block/*.json"):
        ns = f.parent.parent.parent.name
        out["%s:%s" % (ns, f.stem)] = [v for v in json.loads(f.read_text(encoding="utf-8")).get("values", [])
                                       if isinstance(v, str)]
    return out


def find_template(tid, packs_dir, kits=ROOT / "kits" / "structures"):
    ns, path = tid.split(":", 1)
    for p in sorted(Path(packs_dir).iterdir()) if Path(packs_dir).is_dir() else []:
        f = p / "data" / ns / "structure" / (path + ".nbt")
        if f.is_file():
            return f
    f = kits / "campaign" / (path + ".nbt")
    return f if f.is_file() else None


def replay(world, packs, problems, load_template=None, packs_dir=PACKS, on_line=None):
    """packs: [(step, pack dir, folder)]. Applies every block write in order; a pack's pit columns are collected by
    on_line(step, op) if given. Unreadable block writes and unplaceable templates are problems. Block tags are the
    union over every pack (a datapack tag merges across the packs that define it)."""
    tags = {}
    dirs = [Path(p) for _s, p, _f in packs]
    dirs += [p for p in sorted(Path(packs_dir).iterdir()) if p.is_dir()] if Path(packs_dir).is_dir() else []
    for d in dirs:
        for k, v in pack_tags(d).items():
            tags.setdefault(k, [])
            tags[k] += [x for x in v if x not in tags[k]]
    for step, pdir, folder in packs:
        pdir = Path(pdir)
        if not pdir.is_dir():
            problems.append(("replay", "%s: no built pack %s" % (step, pdir.name)))
            continue
        fns = pack_functions(pdir, folder)
        if not fns:
            problems.append(("replay", "%s: %s has no block functions in %s" % (step, pdir.name, folder)))
        for f in fns:
            if not f.is_file():
                problems.append(("replay", "%s: %s's index names %s, which is missing" % (step, pdir.name, f.name)))
                continue
            for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
                op = parse(ln)
                if op is None:
                    continue
                k, v = op
                if k == "unparsed":
                    world.unparsed.append("%s %s: %s" % (step, f.name, v[:160]))
                    continue
                if on_line is not None:
                    on_line(step, op)
                if k == "fill":
                    world.fill(*v[:6], v[6], v[7], v[8], tags)
                elif k == "setblock":
                    x, y, z, state, mode = v
                    world.fill(x, y, z, x, y, z, state, "keep" if mode == "keep" else None, None, tags)
                elif k == "place":
                    tid, px, py, pz, rot = v
                    f_ = find_template(tid, packs_dir)
                    if f_ is None or load_template is None:
                        problems.append(("replay", "%s: cannot place template %s (no .nbt found)" % (step, tid)))
                        continue
                    world.place_template(load_template(f_), px, py, pz, rot)
    for u in world.unparsed[:5]:
        problems.append(("replay", "a block write this audit cannot read: %s" % u))
    if len(world.unparsed) > 5:
        problems.append(("replay", "%d more unreadable block writes" % (len(world.unparsed) - 5)))


# ------------------------------------------------------------------ the walk

class Walker:
    """The world as a player meets it: flat arrays over [x, z, y] with a two-column border that is never a place."""

    def __init__(self, world, obstacles=(), ghost_lights=False):
        self.w = world
        x0, y0, z0 = world.box[:3]
        self.x0, self.y0, self.z0 = x0, y0, z0
        NX, NZ, NY = world.NX, world.NZ, world.NY
        self.NX, self.NZ, self.NY = NX, NZ, NY
        lut = [kind(p) for p in world.palette]
        pl = np.array([k[0] for k in lut], bool)
        fl = np.array([k[1] for k in lut], bool)
        tl = np.array([k[2] for k in lut], bool)
        if ghost_lights:
            for i, p in enumerate(world.palette):
                if is_light(p) and not fl[i]:
                    pl[i] = True
        P = pl[world.a]
        F = fl[world.a]
        T = tl[world.a]
        P[:, :, 1:] &= ~T[:, :, :-1]
        # an iron door is passable when an opener stands beside either half (tools/relic_underground_audit.py's rule)
        for i, p in enumerate(world.palette):
            if base(p) == "minecraft:iron_door" and "half=lower" in p:
                for xi, zi, yi in zip(*np.nonzero(world.a == i)):
                    x, y, z = int(xi) + x0, int(yi) + y0, int(zi) + z0
                    if self.openers((x, y, z)):
                        P[xi, zi, yi] = True
                        if yi + 1 < NY:
                            P[xi, zi, yi + 1] = True
        for (x, y, z) in obstacles:
            if self.inside(x, y, z):
                P[x - x0, z - z0, y - y0] = False
        S = P.copy()
        S[:, :, :-1] &= P[:, :, 1:]
        S[:, :, 1:] &= F[:, :, :-1]
        S[:, :, 0] = False
        S[:, :, -3:] = False
        for arr in (S,):
            arr[:2], arr[-2:], arr[:, :2], arr[:, -2:] = False, False, False, False
        self.P = P.ravel().tobytes()
        self.S = S.ravel().tobytes()
        self.F = F.ravel().tobytes()

    def inside(self, x, y, z):
        return 0 <= x - self.x0 < self.NX and 0 <= z - self.z0 < self.NZ and 0 <= y - self.y0 < self.NY

    def idx(self, x, y, z):
        return ((x - self.x0) * self.NZ + (z - self.z0)) * self.NY + (y - self.y0)

    def xyz(self, i):
        c, yi = divmod(i, self.NY)
        xi, zi = divmod(c, self.NZ)
        return xi + self.x0, yi + self.y0, zi + self.z0

    def openers(self, lower):
        x, y, z = lower
        return [(x + dx, y + dy, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) for dy in (0, 1)
                if (dx, dz) != (0, 0) and is_opener(self.w.get(x + dx, y + dy, z + dz) or AIR)]

    def stand(self, x, y, z):
        return self.inside(x, y, z) and bool(self.S[self.idx(x, y, z)])

    def passable(self, x, y, z):
        return (not self.inside(x, y, z)) or bool(self.P[self.idx(x, y, z)])

    def walk(self, starts, edges=None, columns=None, jumps=True):
        """starts: [(x, y, z)] feet cells. edges: {feet idx: target idx} (a guard's tp). columns: a set of column
        indices (idx // NY) the walk may not leave. -> bytearray, 1 at every feet cell reached."""
        P, S, NY = self.P, self.S, self.NY
        DX, DZ = self.NZ * NY, NY
        seen = bytearray(len(S))
        q = deque()
        for c in starts:
            if self.stand(*c):
                i = self.idx(*c)
                seen[i] = 1
                q.append(i)
        edges = edges or {}

        def ok(n):
            return not seen[n] and (columns is None or n // NY in columns)
        while q:
            i = q.popleft()
            nxt = []
            for d in (DX, -DX, DZ, -DZ):
                n = i + d
                if S[n]:
                    nxt.append(n)
                if S[n + 1] and P[i + 2]:
                    nxt.append(n + 1)
                if P[n] and P[n + 1]:
                    for k in (1, 2, 3):
                        m = n - k
                        if not P[m]:
                            break
                        if S[m]:
                            nxt.append(m)
                            break
                    if jumps and not S[n] and P[n + 2] and P[i + 2]:
                        n2 = n + d
                        if 0 <= n2 < len(S):
                            if S[n2] and P[n2 + 2]:
                                nxt.append(n2)
                            elif S[n2 - 1] and P[n2 + 1] and P[n2 + 2]:
                                nxt.append(n2 - 1)
            t = edges.get(i)
            if t is not None:
                nxt.append(t)
            for n in nxt:
                if ok(n):
                    seen[n] = 1
                    q.append(n)
        return seen

    def reached(self, seen):
        """[(x, y, z)] of every feet cell reached."""
        a = np.frombuffer(bytes(seen), np.uint8).reshape(self.NX, self.NZ, self.NY)
        xi, zi, yi = np.nonzero(a)
        return list(zip((xi + self.x0).tolist(), (yi + self.y0).tolist(), (zi + self.z0).tolist()))

    def blocked_climbs(self, seen, columns=None):
        """[(from feet, to feet, blocker cell)]: a reached place next to a place one up that is NOT reached, and the
        step up is refused only for the third cell over the place he leaves."""
        P, S, NY = self.P, self.S, self.NY
        DX, DZ = self.NZ * NY, NY
        out = []
        for i in (j for j, v in enumerate(seen) if v) if columns is None else \
                (c * NY + y for c in columns for y in range(NY) if seen[c * NY + y]):
            for d in (DX, -DX, DZ, -DZ):
                n = i + d + 1
                if S[n] and not seen[n] and not P[i + 2] and (columns is None or n // NY in columns):
                    out.append((self.xyz(i), self.xyz(n), self.xyz(i + 2)))
        return out

    def roofed_steps(self, columns=None):
        """A sweep over every place standing on a stair: [(lower feet, upper feet, blocker)] where the next stair up is
        a place but the step to it is refused only for the third cell over the lower one."""
        P, S, NY = self.P, self.S, self.NY
        DX, DZ = self.NZ * NY, NY
        stair = np.array(["_stairs" in base(p) for p in self.w.palette], bool)[self.w.a].ravel()
        cand = np.nonzero(np.frombuffer(self.S, np.uint8).astype(bool) & np.roll(stair, 1))[0]
        out = []
        for i in cand.tolist():
            if columns is not None and i // NY not in columns:
                continue
            if P[i + 2]:
                continue
            for d in (DX, -DX, DZ, -DZ):
                n = i + d + 1
                if 0 <= n < len(S) and S[n] and stair[n - 1]:
                    out.append((self.xyz(i), self.xyz(n), self.xyz(i + 2)))
        return out

    def columns_in(self, x0, z0, x1, z1):
        return {(x - self.x0) * self.NZ + (z - self.z0) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
                if 0 <= x - self.x0 < self.NX and 0 <= z - self.z0 < self.NZ}


# ------------------------------------------------------------------ the checks

def guard_edge(relic_spec, relic_pack):
    """(seat, reach, target) of the HQ guard from the relic pack's admit function, or a problem string."""
    g = relic_spec["geometry"]["hq"]["guard"]
    fname = g["admit"]["function"].split(":", 1)[-1]
    f = Path(relic_pack) / "data" / "cobblers" / "function" / (fname + ".mcfunction")
    if not f.is_file():
        return None, "the relic pack has no admit function %s" % f.name
    cmds = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    tps = [TP.match(c) for c in cmds if TP.match(c)]
    reach = [REACH.match(c) for c in cmds if REACH.match(c)]
    if len(tps) != 1 or len(reach) != 1:
        return None, "%s has %d tp and %d reach tests, not one of each" % (f.name, len(tps), len(reach))
    seat = tuple(int(v) for v in reach[0].groups()[:3])
    to = tuple(int(math.floor(float(v))) for v in tps[0].groups())
    return (seat, min(TALK, float(reach[0].group(4))), to), None


def stand_at(world, c):
    """Two clear cells over a floor, read straight from the blocks (no walk)."""
    x, y, z = c
    return (kind(world.get(x, y, z) or AIR)[0] and kind(world.get(x, y + 1, z) or AIR)[0]
            and kind(world.get(x, y - 1, z) or ROCK)[1] and not kind(world.get(x, y - 1, z) or ROCK)[2])


def sign_problems(world, door, step, seat):
    """([wall sign cells within 3 of the door], [problems]): every such sign is off the door's two cells, the doorstep's
    two and the guard's two, and hangs on a block a player could stand on; the doorstep and the seat stay places."""
    out = []
    signs = [(x, y, z) for x in range(door[0] - 3, door[0] + 4) for y in range(door[1] - 1, door[1] + 4)
             for z in range(door[2] - 3, door[2] + 4) if "_wall_sign" in base(world.get(x, y, z) or AIR)]
    keep = {door, (door[0], door[1] + 1, door[2]), step, (step[0], step[1] + 1, step[2]), seat,
            (seat[0], seat[1] + 1, seat[2])}
    if not signs:
        out.append("no wall sign within 3 of the HQ door %s" % (door,))
    for s in signs:
        if s in keep:
            out.append("the HQ sign at %s is in a cell the door, the doorstep or the guard uses" % (s,))
        m = re.search(r"facing=(\w+)", world.get(*s))
        dx, dz = {"north": (0, 1), "south": (0, -1), "east": (-1, 0), "west": (1, 0)}[m.group(1)] if m else (0, 0)
        held = world.get(s[0] + dx, s[1], s[2] + dz)
        if not m or not kind(held or AIR)[1]:
            out.append("the HQ sign at %s hangs on %s, not a solid block" % (s, held))
    if not stand_at(world, step):
        out.append("the HQ doorstep %s is not a place to stand" % (step,))
    if not stand_at(world, seat):
        out.append("the guard's seat %s is not a place to stand" % (seat,))
    return signs, out


def lights_at_head_height(world, walker, seen):
    """[(x, y, z, block)]: a light that is not a floor (a lantern, an end rod) hanging in the head cell over a floor,
    where the feet cell under it is open and next to a place the walk reached: it stops a walker under it."""
    hung = []
    for i, p in enumerate(world.palette):
        if not is_light(p) or kind(p)[1]:
            continue
        for xi, zi, yi in zip(*np.nonzero(world.a == i)):
            x, y, z = int(xi) + world.box[0], int(yi) + world.box[1], int(zi) + world.box[2]
            f = (x, y - 1, z)
            if not walker.passable(*f) or not kind(world.get(x, y - 2, z) or ROCK)[1]:
                continue
            if any(walker.inside(f[0] + dx, f[1] + dy, f[2] + dz) and seen[walker.idx(f[0] + dx, f[1] + dy, f[2] + dz)]
                   for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)) for dy in (-1, 0, 1)):
                hung.append((x, y, z, base(p)))
    return hung


def audit(world, plan, relic_spec, pit, relic_pack=None):
    """world: a replayed World. plan: derived/deep_city/plan.json. pit: {(x, z): tread y} from the pit pack's air.
    -> (problems [(kind, msg)], stats)."""
    problems, st = [], {}

    def bad(k, m):
        problems.append((k, m))
    hq = relic_spec["geometry"]["hq"]
    door = tuple(hq["front_door"]["at"])
    step = tuple(hq["guard"]["front_step"])
    seat = tuple(hq["guard"]["at"])
    lift_block = base(json.loads((ROOT / "data" / "rift_deep.json").read_text(encoding="utf-8"))["lifts"]["block"])

    # the sign at the HQ door: a wall sign near the door, off every cell the door, the doorstep and the guard use
    st["hq_signs"], msgs = sign_problems(world, door, step, seat)
    for m in msgs:
        bad("sign", m)

    # the walk, with the guard standing in his two cells and his admit as an edge
    walker = Walker(world, obstacles=[seat, (seat[0], seat[1] + 1, seat[2])])
    edges = {}
    ge, gp = guard_edge(relic_spec, relic_pack) if relic_pack else (None, "no relic pack given")
    if gp:
        bad("guard", gp)
    else:
        (sx, sy, sz), reach, to = ge
        if walker.stand(*to):
            t = walker.idx(*to)
            r = int(math.ceil(reach)) + 1
            for x in range(sx - r, sx + r + 1):
                for y in range(sy - r, sy + r + 1):
                    for z in range(sz - r, sz + r + 1):
                        if math.dist((x + 0.5, y, z + 0.5), (sx + 0.5, sy, sz + 0.5)) <= reach and walker.inside(x, y, z):
                            edges[walker.idx(x, y, z)] = t
        else:
            bad("guard", "the guard's tp target %s is not a place to stand" % (to,))
    seen = walker.walk([step], edges)
    cells = walker.reached(seen)
    st["walked"] = len(cells)

    # the rings
    levels = sorted(set(pit.values()))
    st["rings"] = {}
    for lv in levels:
        cols = [c for c, t in pit.items() if t == lv]
        street = sum(1 for (x, z) in cols if walker.stand(x, lv + 1, z))
        got = sum(1 for (x, z) in cols if seen[walker.idx(x, lv + 1, z)]) if cols else 0
        st["rings"][lv] = (got, street)
        if not got:
            bad("rings", "the ring at y%d (feet y%d) is not walked to: 0 of its %d street places" % (lv, lv + 1, street))

    # the towers, each on its own
    st["towers"] = {}
    climbs = {}
    for t in plan.get("towers", []):
        (fx, fz), (tx, tz) = t["footprint"]
        cols = walker.columns_in(min(fx, tx) - 2, min(fz, tz) - 2, max(fx, tx) + 2, max(fz, tz) + 2)
        ox, oz = t["door_out"]
        ok, why, blk = _climb(walker, (ox, t["from"] + 1, oz), t["to"] + 1, cols, t["from"])
        key = tuple(t["door"])
        climbs[key] = (t["boundary"], ok)
        st["towers"][str(key)] = "climbs" if ok else why
        lift = t.get("headroom_blocked_by_lift")
        if lift is None and not ok:
            bad("towers", "the stair tower at door %s (y%d to y%d) cannot be climbed: %s" % (key, t["from"], t["to"], why))
        if lift is not None:
            ul = t.get("upper_lift") or []
            if ok:
                bad("towers", "the tower at door %s climbs, but the plan says its roof stays on for a lift at %s"
                    % (key, lift))
            elif blk is None or [blk[0], blk[2]] != list(lift[:2]) or base(world.get(*blk) or AIR) != lift_block \
                    or (ul and list(blk) != list(ul)):
                bad("towers", "the tower at door %s is stopped, but not by its lift %s (a %s): %s"
                    % (key, lift, lift_block, why))
        if not seen[walker.idx(ox, t["from"] + 1, oz)]:
            bad("towers", "the tower at door %s is not walked to: its doorstep %s is not reached from the HQ"
                % (key, (ox, t["from"] + 1, oz)))
    for b in sorted({v[0] for v in climbs.values()}):
        if not any(ok for (bb, ok) in climbs.values() if bb == b):
            bad("towers", "no tower between the rings of boundary %d climbs" % b)

    # the Sink Gate, on its own, then the lip
    sg = plan.get("sink_gate")
    if sg:
        xs = [sg["door"][0], sg["door_out"][0], sg["exit"][0]] + [c[0] for c in sg.get("roof_open_over", [])]
        zs = [sg["door"][1], sg["door_out"][1], sg["exit"][1]] + [c[1] for c in sg.get("roof_open_over", [])]
        cols = walker.columns_in(min(xs) - 4, min(zs) - 4, max(xs) + 4, max(zs) + 4)
        ok, why, _b = _climb(walker, (sg["door_out"][0], sg["from"] + 1, sg["door_out"][1]), sg["to"] + 1, cols, sg["from"],
                         at_least=True)
        st["sink_gate"] = "climbs" if ok else why
        if not ok:
            bad("lip", "the Sink Gate (door %s) cannot be climbed from y%d to the lip: %s" % (sg["door"], sg["from"], why))
        ex, ez = sg["exit"]
        if not any(seen[walker.idx(ex, y, ez)] for y in range(sg["to"] - 2, sg["to"] + 6) if walker.inside(ex, y, ez)):
            bad("lip", "the Sink Gate's exit column %s is not walked to" % ((ex, ez),))
    top = max(levels) if levels else 66
    lip = [c for c in cells if (c[0], c[2]) not in pit and c[1] > top + 1]
    st["lip"] = len(lip)
    if not lip:
        bad("lip", "no place on the lip (outside the pit, over y%d) is walked to" % (top + 1))

    # the arena: every tier's stand box and the crown deck
    ar = plan.get("arena") or {}
    st["tiers"] = {}
    for tr in ar.get("tiers", []):
        x0, y0, z0, x1, _y1, z1 = tr["clear"]
        got = any(seen[walker.idx(x, y0, z)] for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
        st["tiers"][tr["tier"]] = got
        if not got:
            bad("arena", "tier %d (y%d): its stand %s is not walked to" % (tr["tier"], tr["y"], tr["stand"]))
    if ar:
        cx, cz = ar["centre"]
        R, crown = ar["radius"], ar["crown"]
        deck = [c for c in cells if c[1] == crown + 1 and math.hypot(c[0] - cx, c[2] - cz) <= R]
        st["crown"] = len(deck)
        if not deck:
            spire = walker.columns_in(cx - R - 1, cz - R - 1, cx + R + 1, cz + R + 1)
            stuck = sorted(walker.blocked_climbs(seen, spire), key=lambda b: -b[0][1])
            bad("arena", "the crown deck (feet y%d) is not walked to%s" % (crown + 1, (
                "; the climb stops on %s: stepping up to %s needs air at %s, which is %s"
                % (stuck[0][0], stuck[0][1], stuck[0][2], world.get(*stuck[0][2]))) if stuck else ""))

    # the roofed-step sweep: only the towers the plan says a lift keeps roofed may have one
    roofed = walker.roofed_steps()
    allowed = {tuple(t["headroom_blocked_by_lift"]) for t in plan.get("towers", []) if t.get("headroom_blocked_by_lift")}
    allowed_cols = set()
    for t in plan.get("towers", []):
        if t.get("headroom_blocked_by_lift"):
            (fx, fz), (tx, tz) = t["footprint"]
            allowed_cols |= {(x, z) for x in range(min(fx, tx), max(fx, tx) + 1) for z in range(min(fz, tz), max(fz, tz) + 1)}
    stray = [r for r in roofed if (r[0][0], r[0][2]) not in allowed_cols or (r[2][0], r[2][2]) not in allowed
             or base(world.get(*r[2]) or AIR) != lift_block]
    st["roofed_steps"] = [list(map(list, r)) for r in roofed]
    for r in stray[:5]:
        bad("roofed", "a roofed step: from the stair at %s up to %s the third cell %s is %s"
            % (r[0], r[1], r[2], world.get(*r[2])))
    if len(stray) > 5:
        bad("roofed", "%d more roofed steps" % (len(stray) - 5))
    st["roofed_allowed"] = sorted(allowed)

    # the lights: the way lights are walked floors; no lantern hangs at head height over a walked floor
    wl = relic_spec.get("composition", {}).get("way_lights")
    if wl:
        found, lost = 0, []
        pa, ga = relic_spec["geometry"]["passage"], relic_spec["geometry"]["gallery"]
        rows = [[(x, z) for z in wl["passage"]["z"]] for x in range(wl["passage"]["from_x"], pa["stops_at_x"] - 1,
                                                                   -wl["passage"]["every"])]
        rows += [[(x, z) for x in wl["gallery"]["x"]] for z in range(wl["gallery"]["from_z"], ga["z"][0] - 1,
                                                                    -wl["gallery"]["every"])]
        st["way_light_cells"] = []
        for row in rows:
            hits = [(x, y, z) for (x, z) in row for y in range(-10, 40) if base(world.get(x, y, z) or AIR) == wl["block"]]
            if len(hits) != 1:
                lost.append((row, len(hits)))
                continue
            found += 1
            x, y, z = hits[0]
            st["way_light_cells"].append(hits[0])
            if not seen[walker.idx(x, y + 1, z)]:
                bad("lights", "the way light at %s is not a floor the walk stands on (over it: %s, %s)"
                    % (hits[0], world.get(x, y + 1, z), world.get(x, y + 2, z)))
        st["way_lights"] = found
        for row, n in lost:
            bad("lights", "the way light row %s holds %d %s, not one" % (row, n, wl["block"]))
    hung = []
    for i, p in enumerate(world.palette):
        if not is_light(p) or kind(p)[1]:
            continue
        for xi, zi, yi in zip(*np.nonzero(world.a == i)):
            x, y, z = int(xi) + world.box[0], int(yi) + world.box[1], int(zi) + world.box[2]
            f = (x, y - 1, z)
            if not walker.passable(*f) or not kind(world.get(x, y - 2, z) or ROCK)[1]:
                continue
            near = any(seen[walker.idx(f[0] + dx, f[1] + dy, f[2] + dz)] for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       for dy in (-1, 0, 1) if walker.inside(f[0] + dx, f[1] + dy, f[2] + dz))
            if near:
                hung.append((x, y, z, base(p)))
    st["lanterns_at_head_height"] = hung
    for h in hung[:5]:
        bad("lights", "a %s hangs at head height at %s over a floor the walk reaches" % (h[3], h[:3]))
    if len(hung) > 5:
        bad("lights", "%d more lights at head height" % (len(hung) - 5))
    return problems, st


def _climb(walker, start, top_feet, cols, g, at_least=False):
    """(ok, why, blocker): does a walk from `start`, kept to `cols`, reach a place with feet at top_feet (or above,
    at_least)? If not, the highest step up refused for headroom alone names the step and the cell over it."""
    if not walker.stand(*start):
        return False, "its doorstep %s is not a place to stand (%s / %s over %s)" % (
            start, walker.w.get(*start), walker.w.get(start[0], start[1] + 1, start[2]),
            walker.w.get(start[0], start[1] - 1, start[2])), None
    seen = walker.walk([start], columns=cols)
    for c in cols:
        for y in range(walker.NY):
            if seen[c * walker.NY + y]:
                fy = y + walker.y0
                if fy == top_feet or (at_least and fy >= top_feet):
                    return True, "", None
    stuck = sorted(walker.blocked_climbs(seen, cols), key=lambda b: (-b[0][1], b))
    hi = max((walker.xyz(c * walker.NY + y)[1] for c in cols for y in range(walker.NY) if seen[c * walker.NY + y]),
             default=None)
    if stuck:
        a, b, blk = stuck[0]
        return False, ("the climb stops on step %d (feet %s): stepping up to %s needs air at %s, which is %s"
                       % (a[1] - 1 - g, a, b, blk, walker.w.get(*blk))), blk
    return False, "the climb gets no higher than feet y%s and no step up is refused for headroom alone" % hi, None


# ------------------------------------------------------------------ inputs

def pit_of(on_lines):
    """{(x, z): tread y} from the pit pack's single-column unconditional air fills (tools/rift_deep.py 'open it to the
    sky': fill x ty+1 z x top z minecraft:air)."""
    pit = {}
    for k, v in on_lines:
        if k == "fill" and v[0] == v[3] and v[2] == v[5] and base(v[6]) == AIR and v[7] is None:
            pit[(v[0], v[2])] = min(v[1], v[4]) - 1
    return pit


def other_writers(box, replayed, packs_dir=PACKS):
    """{pack: cells-ish count} for every built pack NOT replayed that writes a block inside the box."""
    x0, y0, z0, x1, y1, z1 = box
    out = {}
    for p in sorted(Path(packs_dir).iterdir()) if Path(packs_dir).is_dir() else []:
        if not p.is_dir() or p.name in replayed:
            continue
        n = 0
        for f in (p / "data").rglob("*.mcfunction") if (p / "data").is_dir() else []:
            for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if not ln.startswith(("fill ", "setblock ")):
                    continue
                op = parse(ln)
                if not op or op[0] not in ("fill", "setblock"):
                    continue
                v = op[1]
                xa, ya, za = v[0], v[1], v[2]
                xb, yb, zb = (v[3], v[4], v[5]) if op[0] == "fill" else (xa, ya, za)
                if max(xa, xb) < x0 or min(xa, xb) > x1 or max(za, zb) < z0 or min(za, zb) > z1 \
                        or max(ya, yb) < y0 or min(ya, yb) > y1:
                    continue
                n += 1
        if n:
            out[p.name] = n
    return out


def build_world(source_root, packs_dir=PACKS, overrides=None, box=BOX):
    """-> (world, pit, problems). overrides: {pack name: pack dir} (the mutation tests build a city elsewhere)."""
    import ground as G
    import structure_nbt as SN
    g = G.load(source_root)
    sea = json.loads(WORLD.read_text(encoding="utf-8"))["vertical"]["sea_level"]
    w = World(box)
    x0, y0, z0, x1, y1, z1 = box
    w.lay_ground(g.box(x0, z0, x1, z1), sea)
    problems = []
    lines = []
    packs = [(s, (overrides or {}).get(p, Path(packs_dir) / p), f) for s, p, f in REPLAY]
    replay(w, packs, problems, SN.load, packs_dir,
           on_line=lambda step, op: lines.append(op) if step == "R9B" else None)
    pit = pit_of(lines)
    if not pit:
        problems.append(("replay", "the pit pack writes no column of air: no rings to walk"))
    return w, pit, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root", default=env_source_root())
    ap.add_argument("--packs", default=str(PACKS))
    ap.add_argument("--plan", default=str(PLAN))
    ap.add_argument("--city-pack", help="replay this cobblers_deep_city instead of the one in --packs")
    ap.add_argument("--report", default=str(REPORT))
    a = ap.parse_args(argv)
    if not a.source_root:
        ap.error("needs --source-root or COBBLERS_SOURCE_ROOT: the ground comes from the heightmap")
    plan_p = Path(a.plan)
    if not plan_p.is_file():
        raise SystemExit("no %s: run `python tools/deep_city.py build` first" % plan_p)
    plan = json.loads(plan_p.read_text(encoding="utf-8"))
    relic = json.loads(RELIC.read_text(encoding="utf-8"))
    over = {"cobblers_deep_city": Path(a.city_pack)} if a.city_pack else None
    world, pit, problems = build_world(a.source_root, Path(a.packs), over)
    others = other_writers(BOX, {p for _s, p, _f in REPLAY}, Path(a.packs))
    for k, n in sorted(others.items()):
        problems.append(("replay", "%s writes %d blocks in the walk's box and is not replayed (add it to REPLAY in "
                                   "reapply order)" % (k, n)))
    relic_pack = (over or {}).get("cobblers_relic_underground", Path(a.packs) / "cobblers_relic_underground")
    p2, st = audit(world, plan, relic, pit, relic_pack)
    problems += p2
    rep = Path(a.report)
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps({"problems": problems, "stats": st, "replay": world.stats}, indent=1, default=str),
                   encoding="utf-8")
    print("replayed %d writes (%d conditional skipped, %d templates); walked %d places from the HQ doorstep"
          % (world.stats["writes"], world.stats["conditional_skipped"], world.stats["templates"], st.get("walked", 0)))
    print("rings (walked / street places): %s" % ", ".join("y%d %d/%d" % (k, v[0], v[1])
                                                          for k, v in sorted(st.get("rings", {}).items())))
    print("towers: %s" % "; ".join("%s %s" % (k, v if v == "climbs" else "STOPPED") for k, v in st.get("towers", {}).items()))
    print("sink gate: %s; lip places %d; tiers %s; crown places %d" % (
        "climbs" if st.get("sink_gate") == "climbs" else "STOPPED", st.get("lip", 0),
        "".join("1" if v else "0" for _k, v in sorted(st.get("tiers", {}).items())), st.get("crown", 0)))
    print("roofed steps found %d (allowed under a lift: %s); way lights %s; lights at head height %d"
          % (len(st.get("roofed_steps", [])), st.get("roofed_allowed"), st.get("way_lights"),
             len(st.get("lanterns_at_head_height", []))))
    kinds = {}
    for k, msg in problems:
        kinds.setdefault(k, []).append(msg)
    for k in ("replay", "sign", "guard", "rings", "towers", "roofed", "lip", "arena", "lights"):
        got = kinds.get(k, [])
        print("%-7s %s" % (k, "clean" if not got else "%d PROBLEM(S): %s" % (len(got), "; ".join(got[:3]))))
    print("deep walk audit: %s (detail: %s)" % ("CLEAN" if not problems else "%d PROBLEMS" % len(problems), rep))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
