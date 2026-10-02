#!/usr/bin/env python
"""The Ursaluna den's offline audit: the emitted pack replayed block by block against the plan, re-derived here.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/ursaluna_cave.py
for geometry. It reads data/ursaluna_cave.json, the canonical heightmap (tools/ground.py), data/regions.json,
data/spawns.json, data/habitat_blocks.json and data/dialogue.json, derives the cave it expects from them with its
own voxel predicate, then REPLAYS the generated carve function's fills into a block array and compares. The only
thing taken from the generator is its output (the pack, and the re-application steps it hands tools/reapply.py),
which is what is being checked. Mutating the generator's geometry or its wake (a chamber one block taller, a barrier
put back, a wake that leaves Unbattleable on, a shell that skips a layer) fails a named check here with data/ursaluna_cave.json untouched; the tests in
tests/test_ursaluna_cave.py do exactly that.

What is checked, each from the data and the heightmap, never from the pack:

  footprint   no write lands outside the planned box
  barrier     no line of the pack writes minecraft:barrier, anywhere (the owner, 2026-10-02: no wall)
  void        the air the carve leaves (with the lanterns standing in it) is exactly the passage and the hall the
              record describes
  cover       past the declared open mouth, every carved block has at least margin + 1 blocks of ground over it
  seal        past the open mouth, every block within margin of the cave is rock the carve wrote, the cave itself,
              or the hill's own ground (at or under its heightmap surface): no open air and no unwritten rock
              (a natural cavity) touches the cave anywhere but the mouth
  floor       every cave column whose floor is under the ground has the record's floor block, the den's under the
              den; no floor block is laid over air
  open        a flood fill through the cave's air from the mouth reaches the hall AND the bear: nothing stands between
  bear        the summon and the keeper put it where the record says; the model, scaled, fits in the den's air;
              the summon guard keys on the tag and the species, never on a bare distance (R14C's failure)
  wake        the trigger region, from the plan and the heightmap: a player can stand in it; every reachable block in
              it is in the HALL, never the passage or the mouth; every reachable block within reach + 1 of the bear's
              hitbox is in it (nobody touches the bear asleep); and no ground outside the cave is within it (nobody
              wakes it through the hill). The wake function is positioned at the bear's spot with the record's radius
              and no wider, merges the record's awake flags with Unbattleable 0b and no PoseType, and the keeper
              stands down on the awake score BEFORE it keeps; dress resets the score and load does not
  lanterns    each hangs in the cave from a solid block
  teddiursa   the Habitat Block and pool the record names exist; the block is ACTIVATED (style, no ReplaceSpawns, the
              record's group as max_spawns, at least 2 alive, TICK at chance 1) in the ground's top block outside
              every write; its spawn range reaches the mouth and stops short of the hall; and the pool is Teddiursa
              within the sub-region's band and below its evolution level
  watcher     the conversation exists and compiles, and the NPC stands one above the ground outside every write
  functions   every function passes tools/function_limits.py and is reached from the load tag or the steps

NOT checked, and it needs a running server (experiments/EXP-049-ursaluna-wake): that the fills land (chunk loading),
that the bear is twice normal size (scale_modifier applied after the intrinsic scale), that it sleeps, that the wake
fires, that Unbattleable 0b on a live entity lets a battle start, what a player sees, and that Teddiursa spawn round
the activated block.

  python tools/ursaluna_cave_audit.py [--pack build/datapacks/cobblers_ursaluna_cave] [--source-root R]
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
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_ursaluna_cave"
# Cobblemon 1.8.0 species data (data/cobblemon/species/generation2/teddiursa.json in the jar): Teddiursa evolves into
# Ursaring at level 30. A wild Teddiursa at 30 or above is older than its own evolution.
TEDDIURSA_EVOLVES_AT = 30
PLAYER_REACH = 3.0          # Minecraft 1.21 survival entity interaction range
EPS = 1e-6                  # the record's boundaries are inclusive to within this (a centre lands exactly on s = 0)
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace)?$")


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, check, msg):
        self.errors.append("%s: %s" % (check, msg))

    def note(self, msg):
        self.notes.append(msg)


# ------------------------------------------------------------------ the plan, derived here


class Plan:
    """The cave the record describes, in this file's own terms: angles, not the generator's unit vectors."""

    def __init__(self, rec, ground):
        self.rec, self.ground = rec, ground
        c = rec["cave"]
        self.m = int(c["margin"])
        self.mx, self.mz = rec["site"]["mouth"]
        self.floor = ground(self.mx, self.mz)
        self.theta = math.atan2(rec["site"]["axis"][1], rec["site"]["axis"][0])
        pa, ch = c["passage"], c["chamber"]
        far = max(pa["to"], ch["centre"] + ch["half_length"])
        side = max(pa["half_width"], ch["half_width"])
        r = int(math.ceil(math.hypot(far, side))) + self.m + 3
        self.x0, self.x1 = self.mx - r, self.mx + r
        self.z0, self.z1 = self.mz - r, self.mz + r
        self.y0 = self.floor - self.m - 2
        self.y1 = self.floor + 1 + max(pa["height"], ch["height"]) + self.m + 2
        xs = np.arange(self.x0, self.x1 + 1)
        zs = np.arange(self.z0, self.z1 + 1)
        dx = (xs + 0.5 - (self.mx + 0.5))[None, :]
        dz = (zs + 0.5 - (self.mz + 0.5))[:, None]
        cos, sin = math.cos(self.theta), math.sin(self.theta)
        self.s = dx * cos + dz * sin                       # along the axis, from the mouth's centre
        self.p = -dx * sin + dz * cos                      # across it
        self.g = ground.box(self.x0, self.z0, self.x1, self.z1)
        self.shape = (self.y1 - self.y0 + 1, self.z1 - self.z0 + 1, self.x1 - self.x0 + 1)
        void = np.zeros(self.shape, bool)
        for yi in range(self.shape[0]):
            h = (self.y0 + yi) + 0.5 - (self.floor + 1)
            if h <= 0:
                continue
            in_p = ((self.s >= pa["from"] - EPS) & (self.s <= pa["to"] + EPS)
                    & ((self.p / pa["half_width"]) ** 2 + (h / pa["height"]) ** 2 <= 1 + EPS))
            in_c = (((self.s - ch["centre"]) / ch["half_length"]) ** 2 + (self.p / ch["half_width"]) ** 2
                    + (h / ch["height"]) ** 2 <= 1 + EPS)
            void[yi] = in_p | in_c
        self.void = void
        den = c["den"]
        self.den0 = den["from"]
        # where the hall begins along the axis: the chamber ellipsoid's near tip, from the record's own numbers
        self.hall0 = ch["centre"] - ch["half_length"]

    def idx(self, x, y, z):
        return y - self.y0, z - self.z0, x - self.x0

    def inside(self, x, y, z):
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1 and self.z0 <= z <= self.z1

    def column(self, s, p):
        cos, sin = math.cos(self.theta), math.sin(self.theta)
        fx = self.mx + 0.5 + s * cos - p * sin
        fz = self.mz + 0.5 + s * sin + p * cos
        return int(math.floor(fx)), int(math.floor(fz))

    def bear(self):
        u = self.rec["ursaluna"]
        x, z = self.column(u["at_s"], u["at_p"])
        return x, self.floor + 1, z


# ------------------------------------------------------------------ the pack, replayed


def replay(plan, lines, rep):
    """{block name: id} and an int16 array of what the carve leaves: 0 untouched, else the palette id."""
    names = {}
    state = np.zeros(plan.shape, np.int16)

    def bid(name):
        return names.setdefault(name, len(names) + 1)

    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = FILL.match(line)
        if f:
            x0, y0, z0, x1, y1, z1 = (int(v) for v in f.groups()[:6])
            block, only = f.group(7), f.group(8)
            lo, hi = (min(x0, x1), min(y0, y1), min(z0, z1)), (max(x0, x1), max(y0, y1), max(z0, z1))
            if not (plan.inside(*lo) and plan.inside(*hi)):
                rep.err("footprint", "line %d writes %s..%s, outside the planned box x%d..%d y%d..%d z%d..%d"
                        % (n, lo, hi, plan.x0, plan.x1, plan.y0, plan.y1, plan.z0, plan.z1))
                continue
            a, b = plan.idx(*lo), plan.idx(*hi)
            sl = (slice(a[0], b[0] + 1), slice(a[1], b[1] + 1), slice(a[2], b[2] + 1))
            if only:
                region = state[sl]
                region[region == bid(only)] = bid(block)
            else:
                state[sl] = bid(block)
            continue
        sb = SETBLOCK.match(line)
        if sb:
            x, y, z = (int(v) for v in sb.groups()[:3])
            if not plan.inside(x, y, z):
                rep.err("footprint", "line %d sets (%d, %d, %d), outside the planned box" % (n, x, y, z))
                continue
            state[plan.idx(x, y, z)] = bid(sb.group(4))
            continue
        rep.err("carve", "line %d is neither a fill nor a setblock this audit can replay: %r" % (n, line[:80]))
    return names, state


# ------------------------------------------------------------------ the checks


def check_cave(rec, plan, names, state, rep):
    c = rec["cave"]
    b = c["blocks"]
    air = names.get("minecraft:air", -1)
    light = names.get(b["light"], -1)
    open_space = (state == air) | (state == light)
    extra = open_space & ~plan.void
    missing = plan.void & ~open_space
    if extra.any() or missing.any():
        rep.err("void", "the carve leaves %d open blocks the record does not describe and closes %d it does "
                "(e.g. %s)" % (int(extra.sum()), int(missing.sum()),
                               _first(plan, extra if extra.any() else missing)))
    Y = np.arange(plan.y0, plan.y1 + 1)[:, None, None]
    inner = (plan.s > c["open_mouth_until"])[None]
    thin = plan.void & inner & ((plan.g[None] - Y) < plan.m + 1)
    if thin.any():
        rep.err("cover", "%d carved blocks past the open mouth (s > %s) have under %d blocks of ground over them, "
                "e.g. %s" % (int(thin.sum()), c["open_mouth_until"], plan.m + 1, _first(plan, thin)))
    # the seal: what is within margin of an inner void block, outside the declared open mouth itself (the mouth is
    # open to the sky by design, so the cave a few blocks past it is near that open air through its own passage)
    near = _dilate(plan.void & inner, plan.m) & inner
    natural = state == 0
    terrain = Y <= plan.g[None]                                   # the hill's own solid ground, by the heightmap
    keep = Y > (plan.g[None] - int(c["keep_natural_top"]))        # the top band the shell must not write
    leak = near & natural & ~terrain
    if leak.any():
        rep.err("seal", "%d blocks of open air (above the heightmap ground) lie within %d of the cave past the "
                "mouth, e.g. %s" % (int(leak.sum()), plan.m, _first(plan, leak)))
    unsealed = near & natural & terrain & ~keep
    if unsealed.any():
        rep.err("seal", "%d blocks within %d of the cave are below the ground's top %d and were never written: a "
                "natural cavity there would open into the cave, e.g. %s"
                % (int(unsealed.sum()), plan.m, c["keep_natural_top"], _first(plan, unsealed)))
    wrote_top = (state != 0) & keep & ~plan.void & ~open_space
    wrote_top[plan.floor - plan.y0] = False      # the floor layer is checked on its own below
    if wrote_top.any():
        rep.err("surface", "%d blocks in the ground's top %d were rewritten (the shell must leave the hill's skin), "
                "e.g. %s" % (int(wrote_top.sum()), c["keep_natural_top"], _first(plan, wrote_top)))
    # the floor
    fi = plan.floor - plan.y0
    cols = plan.void.any(axis=0)
    under = plan.floor <= plan.g
    den_cols = plan.s >= plan.den0 - EPS
    want = np.where(den_cols, names.get(b["den_floor"], -2), names.get(b["floor"], -3))
    got = state[fi]
    bad = cols & under & (got != want)
    if bad.any():
        rep.err("floor", "%d cave columns under the ground lack their floor block at y%d, e.g. %s"
                % (int(bad.sum()), plan.floor, _first2(plan, bad, plan.floor)))
    floating = ~under & np.isin(got, [names.get(b["den_floor"], -2), names.get(b["floor"], -3)])
    if floating.any():
        rep.err("floor", "%d floor blocks laid where the ground is below the floor (over air), e.g. %s"
                % (int(floating.sum()), _first2(plan, floating, plan.floor)))
    # the lanterns
    for yi, zi, xi in zip(*np.nonzero(state == light)):
        above = yi + 1
        if above < plan.shape[0]:
            st = state[above, zi, xi]
            solid = (st not in (0, air, light)) or (st == 0 and plan.y0 + above <= plan.g[zi, xi])
        else:
            solid = False
        if not solid or not plan.void[yi, zi, xi]:
            rep.err("lanterns", "the lantern at %s does not hang from solid rock inside the cave"
                    % ((int(plan.x0 + xi), int(plan.y0 + yi), int(plan.z0 + zi)),))
    if int((state == light).sum()) != len(c["lanterns"]):
        rep.err("lanterns", "%d lanterns placed, the record lists %d" % (int((state == light).sum()), len(c["lanterns"])))


def check_bear(rec, plan, names, state, rep):
    u = rec["ursaluna"]
    air = names.get("minecraft:air", -1)
    bx, by, bz = plan.bear()
    k = float(u["scale_modifier"])
    w, h = (v * k for v in u["model"]["hitbox"])
    mw, mh, ml = (v * k for v in u["model"]["cube_bounds_blocks"])
    # the model, scaled, as a box along the axis centred on the bear: every block centre in it must be open air
    Y = np.arange(plan.y0, plan.y1 + 1)[:, None, None]
    ds = plan.s[None] - (u["at_s"])
    dp = plan.p[None] - (u["at_p"])
    dy = (Y + 0.5) - by
    body = (np.abs(ds) <= ml / 2) & (np.abs(dp) <= mw / 2) & (dy >= 0) & (dy <= mh)
    clash = body & (state != air)
    if clash.any():
        rep.err("bear", "the model at scale %s (%.1f long, %.1f wide, %.1f tall) meets %d blocks that are not air, "
                "e.g. %s" % (k, ml, mw, mh, int(clash.sum()), _first(plan, clash)))
    if state[plan.idx(bx, by - 1, bz)] == 0 or state[plan.idx(bx, by - 1, bz)] == air:
        rep.err("bear", "nothing solid under the bear at %s" % ((bx, by, bz),))
    # open: flood the cave's air from the mouth. There is no wall (the owner, 2026-10-02): the hall AND the bear are
    # reached, and what keeps a player from touching it asleep is the wake region, checked below
    start = plan.idx(plan.mx, plan.floor + 1, plan.mz)
    walk = state == air
    if not walk[start]:
        rep.err("open", "the mouth's floor block (%d, %d, %d) is not open air" % (plan.mx, plan.floor + 1, plan.mz))
        return
    seen = np.zeros_like(walk)
    seen[start] = True
    q = deque([start])
    while q:
        y, z, x = q.popleft()
        for a, b2, c2 in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (y + a, z + b2, x + c2)
            if 0 <= n[0] < walk.shape[0] and 0 <= n[1] < walk.shape[1] and 0 <= n[2] < walk.shape[2]                     and walk[n] and not seen[n]:
                seen[n] = True
                q.append(n)
    ch = rec["cave"]["chamber"]
    hx, hz = plan.column(ch["centre"] - ch["half_length"] / 2, 0)
    if not seen[plan.idx(hx, plan.floor + 1, hz)]:
        rep.err("open", "the hall (%d, %d) cannot be reached from the mouth" % (hx, hz))
    if not seen[plan.idx(bx, by, bz)]:
        rep.err("open", "the bear's own block %s cannot be reached from the mouth: something stands between"
                % ((bx, by, bz),))
    check_wake(rec, plan, names, state, seen, (w, h), rep)


def check_wake(rec, plan, names, state, seen, hitbox, rep):
    """The wake's trigger region, from the record's radius, the plan's bear spot and the heightmap.

    Minecraft's `distance` is measured from the execute position (the bear's spot) to a player's feet, so a player
    standing in block (x, y, z) is at (x + 0.5, y, z + 0.5)."""
    u = rec["ursaluna"]
    R = float(u["wake"]["radius"])
    air = names.get("minecraft:air", -1)
    light = names.get(rec["cave"]["blocks"]["light"], -1)
    w, h = hitbox
    bx, by, bz = plan.bear()
    cx, cy, cz = bx + 0.5, float(by), bz + 0.5
    ys, zs, xs = np.nonzero(seen)
    wx, wy, wz = xs + plan.x0, ys + plan.y0, zs + plan.z0
    dist = np.sqrt((wx + 0.5 - cx) ** 2 + (wy - cy) ** 2 + (wz + 0.5 - cz) ** 2)
    in_r = dist <= R
    # a player can stand there: the block under the feet is solid (written rock or floor, or the hill's own ground)
    below = state[ys - 1, zs, xs]
    stand = (ys > 0) & (((below != 0) & (below != air) & (below != light))
                        | ((below == 0) & (wy - 1 <= plan.g[zs, xs])))
    if not (in_r & stand).any():
        rep.err("wake", "no block a player can stand on is within %s of the bear's spot: the wake can never fire" % R)
    s_at = plan.s[zs, xs]
    early = in_r & (s_at < plan.hall0 - EPS)
    if early.any():
        i = int(np.nonzero(early)[0][0])
        rep.err("wake", "%d reachable blocks before the hall (s < %s) are within %s of the bear, e.g. %s: the bear "
                "would wake for a player still in the passage" % (int(early.sum()), plan.hall0, R,
                                                                 (int(wx[i]), int(wy[i]), int(wz[i]))))
    gx = np.maximum(np.abs(wx + 0.5 - cx) - w / 2 - 0.5, 0)
    gz = np.maximum(np.abs(wz + 0.5 - cz) - w / 2 - 0.5, 0)
    gy = np.maximum(np.maximum(by - (wy + 1), wy - (by + h)), 0)
    gap = np.sqrt(gx ** 2 + gy ** 2 + gz ** 2)
    touch = (gap < PLAYER_REACH + 1) & ~in_r
    if touch.any():
        rep.err("wake", "%d reachable blocks within reach + 1 of the bear's hitbox are outside the wake's %s: a player "
                "could hit the bear asleep" % (int(touch.sum()), R))
    # the hill: a player standing on the ground anywhere outside the cave must be farther than R
    if not (plan.x0 <= cx - R and cx + R <= plan.x1 + 1 and plan.z0 <= cz - R and cz + R <= plan.z1 + 1):
        rep.err("wake", "the planned box does not hold the wake's %s round %s, so the surface was not checked"
                % (R, (bx, by, bz)))
    else:
        X = np.arange(plan.x0, plan.x1 + 1)[None, :] + 0.5
        Z = np.arange(plan.z0, plan.z1 + 1)[:, None] + 0.5
        feet = plan.g + 1
        d = np.sqrt((X - cx) ** 2 + (feet - cy) ** 2 + (Z - cz) ** 2)
        fi = np.clip(feet - plan.y0, 0, plan.shape[0] - 1)
        in_cave = np.take_along_axis(plan.void, fi[None], axis=0)[0] & (feet <= plan.y1)
        topside = (d <= R) & ~in_cave
        if topside.any():
            zi, xi = (int(v[0]) for v in np.nonzero(topside))
            rep.err("wake", "%d ground columns outside the cave stand within %s of the bear, e.g. (%d, y%d, %d): a "
                    "player on the hill would wake it through the rock" % (int(topside.sum()), R, plan.x0 + xi,
                                                                          int(feet[zi, xi]), plan.z0 + zi))
        rep.note("wake %s: nearest ground outside the cave %.1f from the bear's spot"
                 % (R, float(d[~in_cave].min())))
    rep.note("bear at %s; %d reachable blocks inside the wake's %s, the nearest before the hall %.1f away; nearest "
             "reachable air %.1f from its hitbox"
             % ((bx, by, bz), int(in_r.sum()), R,
                float(dist[s_at < plan.hall0].min()) if (s_at < plan.hall0).any() else float("inf"),
                float(gap.min()) if len(gap) else float("inf")))


def check_functions(rec, plan, pack, steps, rep):
    ns, tag, u = rec["namespace"], rec["ursaluna"]["tag"], rec["ursaluna"]
    fdir = pack / "data" / ns / "function"
    fns = {p.relative_to(fdir).with_suffix("").as_posix(): p.read_text(encoding="utf-8")
           for p in fdir.rglob("*.mcfunction")}
    import function_limits
    for name, text in fns.items():
        for n, cmd, why in function_limits.check_lines(text.splitlines(), where=name):
            rep.err("functions", "%s:%d %s" % (name, n, why))
    bx, by, bz = plan.bear()
    at = "%.1f %d %.1f" % (bx + 0.5, by, bz + 0.5)
    species = 'nbt={Pokemon:{Species:"cobblemon:%s"}}' % u["species"]
    summons = [s[1] for s in steps if s[0] == "cmd" and "spawnpokemonat" in s[1]]
    if len(summons) != 1:
        rep.err("summon", "%d summon steps, expected 1" % len(summons))
    for cmd in summons:
        if "unless entity @e[tag=%s]" % tag not in cmd:
            rep.err("summon", "the guard does not key on the tag %s: %s" % (tag, cmd))
        for guard in re.findall(r"unless entity (@e\[[^\]]*\])", cmd):
            if "distance=" in guard and "tag=" not in guard and "Species" not in guard:
                rep.err("summon", "a guard keys on distance alone (R14C's failure): %s" % guard)
        if "spawnpokemonat %s %s " % (at, u["species"]) not in cmd:
            rep.err("summon", "the summon is not at the bear's spot %s: %s" % (at, cmd))
        for prop in ("level=%d" % int(u["level"]), "scale_modifier=%s" % u["scale_modifier"]):
            if prop not in cmd.split():
                rep.err("summon", "the summon lacks %s" % prop)
    fn_steps = [s[1] for s in steps if s[0] == "fn"]
    if fn_steps[:1] != ["%s:ursaluna_cave/carve" % ns]:
        rep.err("steps", "the first function step is not the carve: %s" % fn_steps)
    dn = fns.get("ursaluna_cave/dress_new", "")
    if species not in dn or "tag=!%s" % tag not in dn or ("positioned %s " % at) not in dn:
        rep.err("dress", "dress_new does not take only an undressed Ursaluna at the bear's spot")
    dress = fns.get("ursaluna_cave/dress", "")
    for key, v in u["nbt"].items():
        if "%s:%s" % (key, v) not in dress:
            rep.err("dress", "dress does not merge %s:%s" % (key, v))
    if "tp @s %s %s 0" % (at, u["yaw"]) not in dress:
        rep.err("dress", "dress does not put the bear at %s facing yaw %s" % (at, u["yaw"]))
    check_wake_functions(rec, plan, fns, rep)
    # the barrier: no line anywhere in the pack writes one (the owner, 2026-10-02: no wall)
    for name, text in sorted(fns.items()):
        hits = [n for n, line in enumerate(text.splitlines(), 1)
                if not line.lstrip().startswith("#") and "minecraft:barrier" in line]
        if hits:
            rep.err("barrier", "%s writes minecraft:barrier on %d line(s), first line %d" % (name, len(hits), hits[0]))
    # reachability: load tag -> load -> keeper -> near -> keep, wake_check -> wake -> cap_advice;
    # steps -> carve, dress_new -> dress
    tags = json.loads((pack / "data" / "minecraft" / "tags" / "function" / "load.json").read_text(encoding="utf-8"))
    reached = set()
    todo = [v.split(":", 1)[1] for v in tags["values"]] + [s.split(":", 1)[1] for s in fn_steps]
    while todo:
        f = todo.pop()
        if f in reached or f not in fns:
            continue
        reached.add(f)
        todo += re.findall(r"function %s:(\S+)" % ns, fns[f])
    for f in sorted(set(fns) - reached):
        rep.err("functions", "%s:%s is reached by nothing (not the load tag, the steps or another function)" % (ns, f))


def _code(text):
    return [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]


def check_wake_functions(rec, plan, fns, rep):
    """The wake as written, against the record and the plan's bear spot: the sleeping Celebi's shape
    (docs/mechanics/CELEBI_WAKE.md) - a state check on the keeper's loop, a keeper that stands down on the awake
    score before it keeps, the awake merge, the score set by the wake and reset only by dress."""
    ns, u = rec["namespace"], rec["ursaluna"]
    wk, kp, tag = u["wake"], u["keeper"], u["tag"]
    bx, by, bz = plan.bear()
    at = "%.1f %d %.1f" % (bx + 0.5, by, bz + 0.5)
    fq = lambda n: "%s:ursaluna_cave/%s" % (ns, n)          # noqa: E731
    load = _code(fns.get("ursaluna_cave/load", ""))
    objs = [m.group(1) for l in load for m in [re.match(r"scoreboard objectives add (\S+) dummy$", l)] if m]
    if len(objs) != 1:
        rep.err("wake", "load declares %d objectives, expected one" % len(objs))
        return
    obj, holder = objs[0], wk["awake_holder"]
    is_awake = "execute if score %s %s matches 1 run return 0" % (holder, obj)
    sets = lambda v: "scoreboard players set %s %s %d" % (holder, obj, v)   # noqa: E731
    if any(l.startswith("scoreboard players set %s " % holder) for l in load):
        rep.err("wake", "load resets the awake score: a restart would put a woken bear back to sleep")
    keeper = _code(fns.get("ursaluna_cave/keeper", ""))
    want = "execute positioned %s if entity @a[distance=..%d] run function %s" % (at, kp["player_radius"], fq("near"))
    if want not in keeper:
        rep.err("wake", "the keeper does not drive near from the bear's spot within %d" % kp["player_radius"])
    near = _code(fns.get("ursaluna_cave/near", ""))
    keep_at = near.index("function %s" % fq("keep")) if "function %s" % fq("keep") in near else None
    check_at = near.index("function %s" % fq("wake_check")) if "function %s" % fq("wake_check") in near else None
    if not near or near[0] != is_awake:
        rep.err("wake", "near does not stand down on the awake score first: a woken bear would be dragged home")
    if keep_at is None or check_at is None:
        rep.err("wake", "near does not run both keep and wake_check")
    # the trigger: positioned at the bear's spot, the record's radius exactly, no wider and no narrower
    wc = _code(fns.get("ursaluna_cave/wake_check", ""))
    sel = [m for l in wc for m in [re.match(r"execute positioned (\S+ \S+ \S+) as (@a\[[^\]]*(?:\{[^}]*\}[^\]]*)?\]) "
                                            r"run function (\S+)$", l)] if m]
    if len(sel) != 1:
        rep.err("wake", "wake_check has %d trigger lines, expected one" % len(sel))
    else:
        pos, s, target = sel[0].groups()
        r = re.search(r"distance=\.\.(\d+(?:\.\d+)?)[,\]]", s)
        if pos != at:
            rep.err("wake", "the trigger is positioned at %s, not the bear's spot %s" % (pos, at))
        if r is None or float(r.group(1)) != float(wk["radius"]):
            rep.err("wake", "the trigger's distance is %s, the record's radius is %s"
                    % (r.group(1) if r else "missing", wk["radius"]))
        if "gamemode=!spectator" not in s:
            rep.err("wake", "a spectator would wake the bear: %s" % s)
        for f in wk.get("gate_flags") or []:
            if "%s:flag/%s=true" % (ns, f) not in s:
                rep.err("wake", "the trigger does not carry the gate %s" % f)
        if target != fq("wake"):
            rep.err("wake", "the trigger runs %s, not %s" % (target, fq("wake")))
    wake = _code(fns.get("ursaluna_cave/wake", ""))
    merges = [m.group(1) for l in wake for m in [re.match(r"data merge entity @e\[tag=%s,limit=1\] \{(.*)\}$"
                                                         % re.escape(tag), l)] if m]
    if len(merges) != 1:
        rep.err("wake", "wake merges %d times onto the tagged bear, expected once" % len(merges))
    else:
        got = dict(kv.split(":", 1) for kv in merges[0].split(","))
        if got != {k: str(v) for k, v in wk["awake_nbt"].items()}:
            rep.err("wake", "wake merges %s, the record's awake flags are %s" % (got, wk["awake_nbt"]))
        if got.get("Unbattleable") != "0b":
            rep.err("wake", "wake leaves Unbattleable on: no battle could start, so there is no fight")
        if "PoseType" in got:
            rep.err("wake", "wake sets PoseType %s: only \"SLEEP\" is proven (EXP-023, principle 7)" % got["PoseType"])
        mi = next(i for i, l in enumerate(wake) if l.startswith("data merge entity"))
        if is_awake not in wake[:mi]:
            rep.err("wake", "wake does not return before the merge when the bear is already awake")
        if sets(1) not in wake[mi:]:
            rep.err("wake", "wake does not set the awake score after the merge: the keeper would not stand down")
    if sets(1) in _code(fns.get("ursaluna_cave/dress", "")) or sets(0) not in _code(fns.get("ursaluna_cave/dress", "")):
        rep.err("wake", "dress does not reset the awake score to 0 for the fresh, dormant bear")
    for name, text in fns.items():
        if name not in ("ursaluna_cave/wake", "ursaluna_cave/dress") and (sets(0) in _code(text) or sets(1) in _code(text)):
            rep.err("wake", "%s writes the awake score; only wake and dress may" % name)
    cap = _code(fns.get("ursaluna_cave/cap_advice", ""))
    if not any(l.startswith("$") and "rctmod player get level_cap @s" in l for l in cap):
        rep.err("wake", "cap_advice does not read the player's cap from a macro line")
    if not any("matches 1..%d " % (int(u["level"]) - 1) in l for l in cap):
        rep.err("wake", "cap_advice does not warn exactly the caps below the bear's level %d" % int(u["level"]))


def check_teddiursa(rec, plan, state, rep):
    t = rec["teddiursa"]
    hb = json.loads((DATA / "habitat_blocks.json").read_text(encoding="utf-8"))
    sp = json.loads((DATA / "spawns.json").read_text(encoding="utf-8"))
    blk = next((b for b in hb["blocks"] if b["id"] == t["block"]), None)
    hab = next((h for h in sp["habitats"] if h["id"] == t["habitat"]), None)
    if blk is None or hab is None:
        rep.err("teddiursa", "block %s in data/habitat_blocks.json: %s; habitat %s in data/spawns.json: %s"
                % (t["block"], blk is not None, t["habitat"], hab is not None))
        return
    # ACTIVATED (2026-10-02): a natural block only swaps what natural spawning picks within its range, and staging
    # measured 0 Pokemon within 32 of it. An activated one keeps its own group alive round itself.
    act = blk.get("activated") or {}
    if blk["pool"] != "cobblers:%s" % t["habitat"] or blk["style"] != "activated" or blk["replace_spawns"] is not False:
        rep.err("teddiursa", "the block is not an activated, non-replacing block on cobblers:%s" % t["habitat"])
    if "range_of_influence" in blk:
        rep.err("teddiursa", "an activated block carries a natural block's range_of_influence")
    if act.get("max_spawns") != t["group"] or not isinstance(t["group"], int) or t["group"] < 2:
        rep.err("teddiursa", "max_spawns %s is not the record's group %s of at least 2"
                % (act.get("max_spawns"), t["group"]))
    if act.get("trigger") != "TICK" or act.get("chance") != 1.0:
        rep.err("teddiursa", "the block does not refill on every tick at chance 1 (trigger %s, chance %s)"
                % (act.get("trigger"), act.get("chance")))
    if not 1 <= int(act.get("max_spawns_per_activation") or 0) <= int(act.get("max_spawns") or 0):
        rep.err("teddiursa", "max_spawns_per_activation %s is outside 1..max_spawns"
                % act.get("max_spawns_per_activation"))
    x, y, z = (blk["position"][k] for k in "xyz")
    if y != plan.ground(x, z):
        rep.err("teddiursa", "the block at %s is not in the ground's top block (heightmap y%d)" % ((x, y, z), plan.ground(x, z)))
    if plan.inside(x, y, z) and state[plan.idx(x, y, z)] != 0:
        rep.err("teddiursa", "the carve writes over the Habitat Block at %s" % ((x, y, z),))
    r = int(act.get("spawn_range") or 0)
    mouth = (plan.mx + 0.5, plan.floor + 1.5, plan.mz + 0.5)
    if math.dist((x + 0.5, y + 0.5, z + 0.5), mouth) > r:
        rep.err("teddiursa", "the spawn range %d does not reach the mouth (%.1f away)"
                % (r, math.dist((x + 0.5, y + 0.5, z + 0.5), mouth)))
    cx, cz = plan.column(plan.hall0, 0)
    dc = math.dist((x + 0.5, y + 0.5, z + 0.5), (cx + 0.5, plan.floor + 1.5, cz + 0.5))
    if dc <= r:
        rep.err("teddiursa", "the spawn range %d reaches the hall (%.1f away): the outskirts reach into the den" % (r, dc))
    # the band: the sub-region the mouth is in, by its polygons in data/regions.json
    sub = _subregion(plan.mx, plan.mz)
    band = next((s["level_band"] for s in sp["subregions"] if s["id"] == sub), None)
    ents = [e for e in sp["entries"] if e.get("scope") == t["habitat"] and e.get("mechanism") == "habitat_block"]
    if not ents or any(e["species"] != "teddiursa" for e in ents):
        rep.err("teddiursa", "the pool's entries are not Teddiursa alone: %s" % [e["species"] for e in ents])
    for e in ents:
        lo, hi = (int(v) for v in e["level"].split("-"))
        if band is None or lo < band["minimum"] or hi > band["maximum"]:
            rep.err("teddiursa", "levels %s are outside %s's band %s" % (e["level"], sub, band))
        if hi >= TEDDIURSA_EVOLVES_AT:
            rep.err("teddiursa", "levels %s reach %d, where Teddiursa evolves" % (e["level"], TEDDIURSA_EVOLVES_AT))
    rep.note("Teddiursa block %s activated, up to %s within %d, in %s (band %s); %.1f from the hall"
             % ((x, y, z), act.get("max_spawns"), r, sub, band, dc))


def check_watcher(rec, plan, state, rep):
    nx, ny, nz = rec["npc"]["at"]
    if ny != plan.ground(nx, nz) + 1:
        rep.err("watcher", "the NPC at %s does not stand one above the ground (y%d)" % ((nx, ny, nz), plan.ground(nx, nz)))
    if plan.inside(nx, ny, nz):
        i = plan.idx(nx, ny, nz)
        if state[:, i[1], i[2]].any():
            rep.err("watcher", "the carve writes in the NPC's column %s" % ((nx, nz),))
    dl = json.loads((DATA / "dialogue.json").read_text(encoding="utf-8"))
    conv = next((c for c in dl["conversations"] if c["id"] == rec["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        rep.err("watcher", "%s is not a conversation with an NPC" % rec["npc"]["conversation"])
        return
    import compile_dialogue as CD
    _d, quests, fields = CD.load(DATA)
    try:
        got = CD.compile_conversation(conv, quests, fields)
    except SystemExit as e:
        rep.err("watcher", "%s does not compile: %s" % (conv["id"], e))
        return
    if "data/cobblers/npcs/%s.json" % conv["npc_id"] not in got:
        rep.err("watcher", "%s compiles no NPC class" % conv["id"])


def _subregion(x, z):
    rg = json.loads((DATA / "regions.json").read_text(encoding="utf-8"))
    for s in rg["subregions"]:
        for poly in s.get("polygons") or []:
            pts = [(q["x"], q["z"]) if isinstance(q, dict) else (q[0], q[-1]) for q in poly]
            inside = False
            for i in range(len(pts)):
                (x1, z1), (x2, z2) = pts[i], pts[(i + 1) % len(pts)]
                if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
                    inside = not inside
            if inside:
                return s["id"]
    return None


def _dilate(mask, m):
    out = mask.copy()
    for axis in range(3):
        base = out.copy()
        for k in range(1, m + 1):
            out |= np.roll(base, k, axis) | np.roll(base, -k, axis)
    return out


def _first(plan, mask):
    y, z, x = (int(v[0]) for v in np.nonzero(mask))
    return (plan.x0 + x, plan.y0 + y, plan.z0 + z)


def _first2(plan, mask2, y):
    z, x = (int(v[0]) for v in np.nonzero(mask2))
    return (plan.x0 + x, y, plan.z0 + z)


# ------------------------------------------------------------------ entry points


def audit(rec, ground, pack, steps):
    rep = Report()
    plan = Plan(rec, ground)
    carve = pack / "data" / rec["namespace"] / "function" / "ursaluna_cave" / "carve.mcfunction"
    if not carve.is_file():
        rep.err("pack", "%s is missing: run tools/ursaluna_cave.py first" % carve)
        return rep
    names, state = replay(plan, carve.read_text(encoding="utf-8").splitlines(), rep)
    check_cave(rec, plan, names, state, rep)
    check_bear(rec, plan, names, state, rep)
    check_functions(rec, plan, pack, steps, rep)
    check_teddiursa(rec, plan, state, rep)
    check_watcher(rec, plan, state, rep)
    rep.note("planned void %d blocks; floor y%d; box x%d..%d z%d..%d"
             % (int(plan.void.sum()), plan.floor, plan.x0, plan.x1, plan.z0, plan.z1))
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    import ursaluna_cave          # for its OUTPUT only: the re-application steps it hands tools/reapply.py
    rec = json.loads((DATA / "ursaluna_cave.json").read_text(encoding="utf-8"))
    g = G.load(a.source_root)
    rep = audit(rec, g, Path(a.pack), ursaluna_cave.placement_steps(rec, g))
    for n in rep.notes:
        print("note: %s" % n)
    for e in rep.errors:
        print("PROBLEM %s" % e)
    print("ursaluna_cave_audit: %s" % ("clean" if not rep.errors else "%d problem(s)" % len(rep.errors)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
