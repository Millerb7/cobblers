#!/usr/bin/env python
"""The Ursaluna den's offline audit: the emitted pack replayed block by block against the plan, re-derived here.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/ursaluna_cave.py
for geometry. It reads data/ursaluna_cave.json, the canonical heightmap (tools/ground.py), data/regions.json,
data/spawns.json, data/habitat_blocks.json and data/dialogue.json, derives the cave it expects from them with its
own voxel predicate, then REPLAYS the generated carve function's fills into a block array and compares. The only
thing taken from the generator is its output (the pack, and the re-application steps it hands tools/reapply.py),
which is what is being checked. Mutating the generator's geometry (a chamber one block taller, a curtain one block
thinner, a shell that skips a layer) fails a named check here with data/ursaluna_cave.json untouched; the tests in
tests/test_ursaluna_cave.py do exactly that.

What is checked, each from the data and the heightmap, never from the pack:

  footprint   no write lands outside the planned box
  void        the air the carve leaves (with the curtain and the lanterns standing in it) is exactly the passage and
              the hall the record describes
  cover       past the declared open mouth, every carved block has at least margin + 1 blocks of ground over it
  seal        past the open mouth, every block within margin of the cave is rock the carve wrote, the cave itself,
              or the hill's own ground (at or under its heightmap surface): no open air and no unwritten rock
              (a natural cavity) touches the cave anywhere but the mouth
  floor       every cave column whose floor is under the ground has the record's floor block, the den's under the
              den; no floor block is laid over air
  curtain     a flood fill through the cave's air from the mouth reaches the hall and never the bear, and no air a
              player can stand in is within reach + 1 of the bear's hitbox
  bear        the summon and the keeper put it where the record says; the model, scaled, fits in the den's air;
              the summon guard keys on the tag and the species, never on a bare distance (R14C's failure)
  lanterns    each hangs in the cave from a solid block
  teddiursa   the Habitat Block and pool the record names exist, the block sits in the ground's top block outside
              every write, its range reaches the mouth and stops short of the curtain, and the pool is Teddiursa
              within the sub-region's band and below its evolution level
  watcher     the conversation exists and compiles, and the NPC stands one above the ground outside every write
  functions   every function passes tools/function_limits.py and is reached from the load tag or the steps

NOT checked, and it needs a running server: that the fills land (chunk loading), that the bear is twice normal size
(scale_modifier applied after the intrinsic scale), that it sleeps, that the barrier stops a ball, what a player
sees, and that Teddiursa spawn in the Habitat Block's range.

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
        self.cur0, self.cur1 = den["curtain_from"], den["curtain_from"] + den["curtain_thickness"]

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
    curtain = names.get(b["curtain"], -1)
    light = names.get(b["light"], -1)
    open_space = (state == air) | (state == curtain) | (state == light)
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
    den_cols = plan.s >= plan.cur1 - EPS
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
            solid = (st not in (0, air, curtain, light)) or (st == 0 and plan.y0 + above <= plan.g[zi, xi])
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
    curtain = names.get(rec["cave"]["blocks"]["curtain"], -1)
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
    # the curtain: flood the cave's air from the mouth
    start = plan.idx(plan.mx, plan.floor + 1, plan.mz)
    walk = state == air
    if not walk[start]:
        rep.err("curtain", "the mouth's floor block (%d, %d, %d) is not open air" % (plan.mx, plan.floor + 1, plan.mz))
        return
    seen = np.zeros_like(walk)
    seen[start] = True
    q = deque([start])
    while q:
        y, z, x = q.popleft()
        for a, b2, c2 in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (y + a, z + b2, x + c2)
            if 0 <= n[0] < walk.shape[0] and 0 <= n[1] < walk.shape[1] and 0 <= n[2] < walk.shape[2] \
                    and walk[n] and not seen[n]:
                seen[n] = True
                q.append(n)
    ch = rec["cave"]["chamber"]
    hx, hz = plan.column(ch["centre"] - ch["half_length"] / 2, 0)
    if not seen[plan.idx(hx, plan.floor + 1, hz)]:
        rep.err("curtain", "the hall in front of the curtain (%d, %d) cannot be reached from the mouth" % (hx, hz))
    if seen[plan.idx(bx, by, bz)]:
        rep.err("curtain", "the bear's own block %s is reachable from the mouth through open air" % ((bx, by, bz),))
    # reach: from any reachable air block to the hitbox (axis aligned, w wide, h tall)
    ys, zs, xs = np.nonzero(seen)
    cx, cz = bx + 0.5, bz + 0.5
    wx, wy, wz = xs + plan.x0, ys + plan.y0, zs + plan.z0      # world coordinates of each reachable air block
    gx = np.maximum(np.abs(wx + 0.5 - cx) - w / 2 - 0.5, 0)
    gz = np.maximum(np.abs(wz + 0.5 - cz) - w / 2 - 0.5, 0)
    gy = np.maximum(np.maximum(by - (wy + 1), wy - (by + h)), 0)
    d = float(np.sqrt(gx ** 2 + gy ** 2 + gz ** 2).min()) if len(xs) else 1e9
    if d < PLAYER_REACH + 1:
        rep.err("curtain", "open air a player can reach is %.1f blocks from the bear's hitbox (reach %s + 1)"
                % (d, PLAYER_REACH))
    rep.note("bear at %s; nearest reachable air %.1f blocks from its hitbox; %d open blocks reachable"
             % ((bx, by, bz), d, int(seen.sum())))
    if not (state == curtain).any():
        rep.err("curtain", "no %s written at all" % rec["cave"]["blocks"]["curtain"])


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
    # reachability: load tag -> load -> keeper -> keep; steps -> carve, dress_new -> dress
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
    if blk["pool"] != "cobblers:%s" % t["habitat"] or blk["style"] != "natural" or blk["replace_spawns"] is not True:
        rep.err("teddiursa", "the block is not a natural ReplaceSpawns block on cobblers:%s" % t["habitat"])
    x, y, z = (blk["position"][k] for k in "xyz")
    if y != plan.ground(x, z):
        rep.err("teddiursa", "the block at %s is not in the ground's top block (heightmap y%d)" % ((x, y, z), plan.ground(x, z)))
    if plan.inside(x, y, z) and state[plan.idx(x, y, z)] != 0:
        rep.err("teddiursa", "the carve writes over the Habitat Block at %s" % ((x, y, z),))
    r = blk["range_of_influence"]
    mouth = (plan.mx + 0.5, plan.floor + 1.5, plan.mz + 0.5)
    if math.dist((x + 0.5, y + 0.5, z + 0.5), mouth) > r:
        rep.err("teddiursa", "the range %d does not reach the mouth (%.1f away)" % (r, math.dist((x, y, z), mouth)))
    cx, cz = plan.column(plan.cur0, 0)
    dc = math.dist((x + 0.5, y + 0.5, z + 0.5), (cx + 0.5, plan.floor + 1.5, cz + 0.5))
    if dc <= r:
        rep.err("teddiursa", "the range %d reaches the curtain (%.1f away): the outskirts reach into the hall" % (r, dc))
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
    rep.note("Teddiursa block %s range %d in %s (band %s); %.1f from the curtain" % ((x, y, z), r, sub, band, dc))


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
