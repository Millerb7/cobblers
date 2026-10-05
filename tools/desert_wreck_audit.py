#!/usr/bin/env python
"""Independent audit of the Brass Petrel's BUILT pack (build/datapacks/cobblers_desert_wreck) against the heightmap.

Written by an agent that built none of it (CLAUDE.md principle 16). It never imports tools/desert_wreck.py. Every
expectation comes from:

  - the canonical heightmap through tools/ground.py, rounded (or any callable g(x, z) a test hands in);
  - data/desert_wreck.json's DECLARED numbers (x, bow_z, length, half_beam, tapers, stern_show, depth, hold, hatch_at,
    bulkhead, cabin, breach_half, pool.blocks, residents, find, bounds, blocks.ids/spawn_conditions);
  - the hull's narrowing 0,0,0,0,1,1,2,3, as docs/world-building/DESERT_WRECK.md's table declares it (the data file's
    prose says "0 for 3 rows, 1 for 2, 2, then 3", seven rows for an eight-row hull: a recorded disagreement);
  - the shared files: data/route_paths.json, data/habitat_blocks.json, data/encounter_design.json (rules.hearts),
    data/spawn_blocks.json, data/spawn_block_policy.json, data/rewards.json, data/spawns.json, data/world.json, and every
    other data file's boxes and points (another place's footprint);
  - the Cobblemon 1.8.0 jar (species files, item models and the en_us lang file).

What is read from the pack is only what the server would execute: the setblock / fill / forceload lines of
build.mcfunction and the castellan spawn function's coordinates. A world model is built from them: a written cell is its
written state; an unwritten cell is ground at or under round(h), water from there up to the sea level where the ground
is under it, air elsewhere.

The checks (each error names its check):
  seating   D = max(ground under the transom row) + stern_show, K = D - depth; every hull column's ground over K and
            at or over the sea; the first three bow rows' ground at or over D + 1 (buried); the stern's ground at or
            under D - stern_show (standing).
  shape     every hull cell (from the declared tapers and narrowing) is written; shell cells are shell planks or the
            wale except the declared breach; the deck, floor and interior hold what they should; nothing under the keel.
  sea       nothing written where the ground is under 61; no air or sand where it is under 62; no written air beside
            unwritten water.
  palette   every block in blocks.ids; the lantern the only light source; no water, waterlogging, bubble-column base,
            chest or bed. light: an independent block-light flood leaves no written air inside the hull or cabin at 0.
  spawn     the written spawn-condition blocks (data/spawn_blocks.json) equal blocks.spawn_conditions and are covered
            by the data/spawn_block_policy.json entry scoped to desert_wreck.
  support   every lantern, sign, ladder, carpet, coral sprig/fan and banner on something; no sand or anvil over air; no
            natural ground over written air; no component of written blocks out of touch with the ground.
  footprint every written block inside data/desert_wreck.json bounds, the bounds tight, none in another place's
            box, none within rules.hearts.clear_of_path_blocks of a route path; every write force-loaded; fills under
            the limit; the clearing names plants only (no water, never #minecraft:replaceable).
  walk      a two-high walk, steps of at most one, ladders climbable, from the sand at (x, ground+1, z_transom+1) reaches
            the berth, the cargo hold, the deck (from the hold through the hatch, never leaving the hull) and the cache.
  wards     the two natural ReplaceSpawns blocks: where the data says, not in a written block, dry, inside the bounds,
            and no sphere overlapping another natural or activated block's (3D).
  castellan anchor dry, sea within 3, not built on, the spawn at ground + 1; at least clear_of_path_blocks from every
            route path; leash clear of every activated block's spawn range (tests/test_resident_siting.py's rule) and of
            other places' natural blocks; level within next_cap of the pool's tier; species in the jar.
  cache     the container a written barrel inside the cabin; the trigger box round it and holding a reachable stand;
            every item in the jar.
  pool      every species of the strand's pool in the jar, a regional form present as a form of its species.

NOT covered (it needs a running server): that the fills land, that the dune's material lies as the heightmap says, that
the wards redirect spawns, that the keeper wakes Castellan, that the cache pays, that mobs do or do not spawn.

    python tools/desert_wreck_audit.py [--pack DIR] [--jar JAR] [--source-root DIR] [-v]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import sys
import zipfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_PACK = ROOT / "build" / "datapacks" / "cobblers_desert_wreck"
JAR_CANDIDATES = [Path(r"C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")]

NARROWING = (0, 0, 0, 0, 1, 1, 2, 3)   # docs/world-building/DESERT_WRECK.md: "narrowing downward 0,0,0,0,1,1,2,3"
FILL_LIMIT = 32768                       # vanilla 1.21.1 commandModificationBlockLimit default

SHELL_IDS = {"minecraft:dark_oak_planks", "minecraft:spruce_planks", "minecraft:stripped_dark_oak_log"}
# vanilla 1.21.1 blocks that emit light (by name; lit variants of furnaces/lamps are states, matched by the stems)
EMITTER = re.compile(r"(torch|lantern|candle|froglight|campfire|redstone_lamp|glowstone|shroomlight|^minecraft:light$|"
                     r"sea_pickle|end_rod|magma|lava|fire$|beacon|conduit|amethyst_cluster|amethyst_bud|glow_lichen|"
                     r"crying_obsidian|respawn_anchor|jack_o_lantern|sculk_catalyst|sculk_sensor|brewing_stand|"
                     r"enchanting_table|ender_chest|furnace|smoker)")
FORBIDDEN = re.compile(r"(water|bubble_column|soul_sand|soul_soil|magma|kelp|seagrass|^minecraft:chest$|trapped_chest|_bed$)")
# what a player's body passes through (a trapdoor is the hatch: the player opens it)
PASS = re.compile(r"^minecraft:(air|cave_air|ladder|.*_wall_sign|.*_sign|.*_carpet|.*_trapdoor|.*_banner|dead_.*_coral_fan|"
                  r"dead_.*_coral_wall_fan|dead_(brain|tube|horn|fire|bubble)_coral|short_grass|dead_bush)$")
# what a player cannot stand ON (no top to step onto within one block)
NOT_FLOOR = re.compile(r"^minecraft:(lantern|chain|.*_fence|.*_wall)$")
# full cubes: what stops block light
OPAQUE = re.compile(r"^minecraft:(.*_planks|stripped_.*_log|.*_log|sand|barrel|raw_copper_block|cartography_table|"
                    r"dead_.*_coral_block|bone_block|calcite)$")
FACING = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0)}
CLEARABLE = {"minecraft:dead_bush", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern",
             "minecraft:large_fern", "minecraft:cactus", "minecraft:sugar_cane", "#minecraft:logs", "#minecraft:leaves"}
NOT_PLACES = {"desert_wreck.json", "regions.json", "cells.json", "world.json", "route_paths.json", "id_authorship.json",
              "spawns.json", "spawn_blocks.json", "spawn_block_policy.json", "encounter_design.json"}
OWN_IDS = re.compile(r"^(habitat\.)?desert_wreck")


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def base(state):
    return re.match(r"[#a-z0-9_:./-]+", state).group(0)


def props(state):
    m = re.match(r"[a-z0-9_:./-]+\[([^\]]*)\]", state)
    if not m:
        return {}
    return dict(kv.split("=", 1) for kv in m.group(1).split(",") if "=" in kv)


class Report:
    def __init__(self):
        self.errors, self.notes, self.checks = [], [], set()

    def err(self, check, msg):
        self.checks.add(check)
        self.errors.append("%s: %s" % (check, msg))

    def note(self, check, msg):
        self.checks.add(check)
        self.notes.append("%s: %s" % (check, msg))

    def ran(self, check):
        self.checks.add(check)

    def failed(self, check):
        return [e for e in self.errors if e.startswith(check + ":")]


# ------------------------------------------------------------------------------------------------- reading the pack
def parse_build(text):
    """(blocks {(x,y,z): state}, order {(x,y,z): line index}, clears [(box, target)], unloaded [(line, text)],
    oversized [text])."""
    blocks, order, clears, unloaded, oversized = {}, {}, [], [], []
    loaded = set()
    for i, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        t = line.split(" ")
        if t[0] == "forceload":
            nums = [int(v) for v in t[2:6]] if len(t) >= 6 else [int(t[2]), int(t[3]), int(t[2]), int(t[3])]
            cs = {(cx, cz) for cx in range(min(nums[0], nums[2]) >> 4, (max(nums[0], nums[2]) >> 4) + 1)
                  for cz in range(min(nums[1], nums[3]) >> 4, (max(nums[1], nums[3]) >> 4) + 1)}
            if t[1] == "add":
                loaded |= cs
            else:
                loaded -= cs
            continue
        if t[0] == "fill":
            x0, y0, z0, x1, y1, z1 = (int(v) for v in t[1:7])
            x0, x1, y0, y1, z0, z1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)
            vol = (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1)
            if vol > FILL_LIMIT:
                oversized.append(line)
            need = {(cx, cz) for cx in range(x0 >> 4, (x1 >> 4) + 1) for cz in range(z0 >> 4, (z1 >> 4) + 1)}
            if not need <= loaded:
                unloaded.append((i, line))
            rest = " ".join(t[7:])
            if " replace " in " " + rest + " " and t[8:9] and t[8] == "replace":
                clears.append(((x0, y0, z0, x1, y1, z1), t[7], " ".join(t[9:])))
                continue
            st = rest
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    for z in range(z0, z1 + 1):
                        blocks[(x, y, z)] = st
                        order[(x, y, z)] = i
            continue
        if t[0] == "setblock":
            x, y, z = int(t[1]), int(t[2]), int(t[3])
            if (x >> 4, z >> 4) not in loaded:
                unloaded.append((i, line))
            blocks[(x, y, z)] = line.split(" ", 4)[4]
            order[(x, y, z)] = i
    return blocks, order, clears, unloaded, oversized


def read_pack(pack):
    pack = Path(pack)
    fdir = pack / "data" / "cobblers" / "function" / "desert_wreck"
    build = (fdir / "build.mcfunction").read_text(encoding="utf-8")
    spawn = fdir / "castellan" / "spawn.mcfunction"
    return build, (spawn.read_text(encoding="utf-8") if spawn.is_file() else "")


# ------------------------------------------------------------------------------------------------- the world model
class World:
    def __init__(self, blocks, g, sea):
        self.b, self.g, self.sea = blocks, g, sea
        self._gc = {}

    def ground(self, x, z):
        k = (x, z)
        if k not in self._gc:
            self._gc[k] = int(self.g(x, z))
        return self._gc[k]

    def state(self, x, y, z):
        """the written state, else 'ground', 'water' or 'air'."""
        s = self.b.get((x, y, z))
        if s is not None:
            return s
        gy = self.ground(x, z)
        if y <= gy:
            return "ground"
        if gy < self.sea and y <= self.sea:
            return "water"
        return "air"

    def passable(self, x, y, z):
        s = self.state(x, y, z)
        if s == "air":
            return True
        if s in ("ground", "water"):
            return False
        return bool(PASS.match(base(s)))

    def floor(self, x, y, z):
        s = self.state(x, y, z)
        if s == "ground":
            return True
        if s in ("air", "water"):
            return False
        b = base(s)
        return not PASS.match(b) and not NOT_FLOOR.match(b)

    def solid(self, x, y, z):
        """non-air, non-water: something a hung block can be attached to."""
        s = self.state(x, y, z)
        if s in ("air", "water"):
            return False
        return s == "ground" or base(s) not in ("minecraft:air", "minecraft:cave_air")

    def opaque(self, x, y, z):
        s = self.state(x, y, z)
        if s == "ground":
            return True
        if s in ("air", "water"):
            return False
        return bool(OPAQUE.match(base(s)))

    def ladder(self, x, y, z):
        s = self.b.get((x, y, z))
        return s is not None and base(s) == "minecraft:ladder"


# ------------------------------------------------------------------------------------------------- the declared hull
class Hull:
    """The hull's geometry from data/desert_wreck.json's numbers and the declared narrowing, on ground g."""

    def __init__(self, doc, g):
        w = doc["wreck"]
        self.w = w
        self.W, self.Z0, self.L = w["x"], w["bow_z"], w["length"]
        bt, st, hb = w["bow_taper"], w["stern_taper"], w["half_beam"]
        self.hw0 = [bt[lz] if lz < len(bt) else st[lz - (self.L - len(st))] if lz >= self.L - len(st) else hb
                    for lz in range(self.L)]
        if w["depth"] != len(NARROWING) - 1:
            raise SystemExit("desert_wreck_audit: depth %d but the declared narrowing has %d rows"
                             % (w["depth"], len(NARROWING)))
        tz = self.Z0 + self.L - 1
        h = self.hw0[-1]
        self.transom = [(self.W + lx, tz) for lx in range(-h, h + 1)]
        self.D = max(int(g(x, z)) for x, z in self.transom) + w["stern_show"]
        self.K = self.D - w["depth"]
        self.F = self.D - w["hold"]["floor_below_deck"]
        self.cells = {}
        for lz in range(self.L):
            for y in range(self.K, self.D + 1):
                hw = self.hw(lz, y)
                for lx in range(-hw, hw + 1):
                    self.cells[(self.W + lx, y, self.Z0 + lz)] = None
        for (x, y, z) in self.cells:
            out = [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1), (x, y - 1, z)]
            if y == self.K or any(c not in self.cells for c in out):
                self.cells[(x, y, z)] = "shell"
            elif y == self.D:
                self.cells[(x, y, z)] = "deck"
            elif y == self.F:
                self.cells[(x, y, z)] = "floor"
            else:
                self.cells[(x, y, z)] = "interior"

    def hw(self, lz, y):
        return self.hw0[lz] - NARROWING[self.D - y]

    def in_footprint(self, x, z):
        lz = z - self.Z0
        return 0 <= lz < self.L and abs(x - self.W) <= self.hw0[lz]

    def lz(self, k):
        return self.Z0 + k


# ------------------------------------------------------------------------------------------------- checks
def check_seating(doc, g, H, rep):
    rep.ran("seating")
    for lz in range(H.L):
        for lx in range(-H.hw0[lz], H.hw0[lz] + 1):
            x, z = H.W + lx, H.Z0 + lz
            gy = int(g(x, z))
            if gy <= H.K or gy < 62:
                rep.err("seating", "hull column (%d, %d): ground y%d is not over the keel y%d and dry" % (x, z, gy, H.K))
    for lz in range(3):
        for lx in range(-H.hw0[lz], H.hw0[lz] + 1):
            gy = int(g(H.W + lx, H.Z0 + lz))
            if gy < H.D + 1:
                rep.err("seating", "bow row z%d x%d: ground y%d is under D+1 = y%d: the bow is not buried"
                        % (H.Z0 + lz, H.W + lx, gy, H.D + 1))
    for x, z in H.transom:
        if int(g(x, z)) > H.D - H.w["stern_show"]:
            rep.err("seating", "transom (%d, %d): ground over D - stern_show" % (x, z))
    rep.note("seating", "D = y%d, K = y%d, hold floor y%d (from the heightmap and the declared numbers)" % (H.D, H.K, H.F))


def check_shape(doc, H, blocks, rep):
    rep.ran("shape")
    w = doc["wreck"]
    b = doc["blocks"]
    tz = H.Z0 + H.L - 1
    bulk_z = H.Z0 + w["bulkhead"]
    hatch = (H.W, H.D, H.Z0 + w["hatch_at"])
    masts = {H.Z0 + m["at"] for m in w["masts"].values()}
    spill_end = H.Z0 + w["hold"]["spill_slope_to"]
    missing, bad = [], []
    for c, kind in H.cells.items():
        x, y, z = c
        s = blocks.get(c)
        if s is None:
            missing.append(c)
            continue
        bs = base(s)
        if kind == "shell":
            breach = z == tz and abs(x - H.W) <= w["breach_half"] and H.F < y < H.D
            if breach:
                # the breach's opening (air, its sand sill) or the transom round it; the walk proves it is open
                if bs not in SHELL_IDS | {"minecraft:air", "minecraft:sand"}:
                    bad.append((c, bs, "breach"))
            elif bs not in SHELL_IDS:
                bad.append((c, bs, "shell"))
        elif kind == "deck":
            if bs == b["deck"]:
                continue
            if bs == "minecraft:air":
                continue           # a deck hole: held by check_support (ground under D, aft of the spill)
            if c == hatch and bs.endswith("_trapdoor"):
                continue
            if x == H.W and z in masts and bs == "minecraft:stripped_spruce_log":
                continue
            bad.append((c, bs, "deck"))
        elif kind == "floor":
            if bs not in (b["floor"], b["mast"]):
                bad.append((c, bs, "floor"))
        else:
            if bs in ("minecraft:dark_oak_planks", "minecraft:birch_planks", "minecraft:stripped_dark_oak_log"):
                bad.append((c, bs, "interior"))
            elif bs == "minecraft:spruce_planks" and z != bulk_z:
                bad.append((c, bs, "interior"))
    if missing:
        rep.err("shape", "%d hull cell(s) not written (natural ground left inside the hull), e.g. %s"
                % (len(missing), sorted(missing)[:4]))
    if bad:
        rep.err("shape", "%d hull cell(s) hold the wrong block, e.g. %s" % (len(bad), bad[:4]))
    under = [(x, H.K - 1, z) for (x, y, z) in H.cells if y == H.K and (x, H.K - 1, z) in blocks]
    if under:
        rep.err("shape", "%d block(s) written under the keel y%d, e.g. %s" % (len(under), H.K, under[:3]))
    holes = [(x, z) for (x, y, z), k in H.cells.items() if k == "deck" and blocks.get((x, y, z)) == "minecraft:air"]
    for x, z in holes:
        if z <= spill_end:
            rep.err("shape", "deck hole (%d, %d) over the sand spill (z <= %d)" % (x, z, spill_end))
    rep.note("shape", "%d hull cells, %d deck holes" % (len(H.cells), len(holes)))
    return holes


def check_sea(W, rep):
    rep.ran("sea")
    for (x, y, z), s in W.b.items():
        gy = W.ground(x, z)
        bs = base(s)
        if gy < W.sea - 1:
            rep.err("sea", "(%d, %d, %d) %s written where the ground is y%d (under %d)" % (x, y, z, bs, gy, W.sea - 1))
        elif gy < W.sea and bs in ("minecraft:air", "minecraft:sand"):
            rep.err("sea", "(%d, %d, %d) %s written in a sea column (ground y%d)" % (x, y, z, bs, gy))
        if bs in ("minecraft:air", "minecraft:cave_air") and y <= W.sea:
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0)):
                if (x + dx, y + dy, z + dz) not in W.b and W.state(x + dx, y + dy, z + dz) == "water":
                    rep.err("sea", "written air (%d, %d, %d) beside the sea: water flows in" % (x, y, z))
                    break


def check_palette(doc, blocks, rep):
    rep.ran("palette")
    allowed = set(doc["blocks"]["ids"])
    seen = {}
    for c, s in blocks.items():
        seen.setdefault(base(s), c)
        if props(s).get("waterlogged") == "true":
            rep.err("palette", "%s at %s is waterlogged" % (base(s), c))
    for bs, c in sorted(seen.items()):
        if bs not in allowed:
            rep.err("palette", "%s at %s is not in blocks.ids" % (bs, c))
        if EMITTER.search(bs) and bs != "minecraft:lantern":
            rep.err("palette", "%s at %s emits light (only the lantern may)" % (bs, c))
        if FORBIDDEN.search(bs):
            rep.err("palette", "%s at %s is forbidden (water, bubble column, chest or bed)" % (bs, c))
    return set(seen)


def check_spawn_conditions(doc, written_ids, spawn_blocks, policy, rep):
    rep.ran("spawn")
    cond = set(spawn_blocks["blocks"]) & written_ids
    declared = set(doc["blocks"]["spawn_conditions"])
    if cond != declared:
        rep.err("spawn", "written spawn-condition blocks %s; declared %s" % (sorted(cond), sorted(declared)))
    entries = [e for e in policy["whitelist"] if "desert_wreck" in e.get("scope", "")]
    if not entries:
        rep.err("spawn", "no data/spawn_block_policy.json whitelist entry is scoped to desert_wreck")
        return
    covered = set().union(*(set(e["blocks"]) for e in entries))
    if cond - covered:
        rep.err("spawn", "written spawn-condition blocks not whitelisted for desert_wreck: %s" % sorted(cond - covered))


def check_light(W, H, doc, holes, rep):
    rep.ran("light")
    srcs = [c for c, s in W.b.items() if base(s) == "minecraft:lantern"]
    if not srcs:
        rep.err("light", "no lantern written")
    level = {}
    q = deque()
    for c in srcs:
        level[c] = 15
        q.append(c)
    xs = [c[0] for c in W.b]
    zs = [c[2] for c in W.b]
    box = (min(xs) - 2, max(xs) + 2, min(zs) - 2, max(zs) + 2)
    while q:
        x, y, z = q.popleft()
        lv = level[(x, y, z)] - 1
        if lv <= 0:
            continue
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (x + dx, y + dy, z + dz)
            if not (box[0] <= n[0] <= box[1] and box[2] <= n[2] <= box[3]):
                continue
            if level.get(n, 0) >= lv or W.opaque(*n):
                continue
            level[n] = lv
            q.append(n)
    cab = doc["wreck"]["cabin"]
    inner = [c for c, k in H.cells.items() if k in ("interior",)]
    for lz in range(cab["from"], H.L):
        z = H.Z0 + lz
        for lx in range(-H.hw0[lz] + 1, H.hw0[lz]):
            for y in range(H.D + 1, H.D + cab["height"] + 1):
                inner.append((H.W + lx, y, z))
    holeset = {(x, H.D, z) for x, z in holes}
    dark = [c for c in inner if c not in holeset and W.b.get(c) in ("minecraft:air",) and level.get(c, 0) == 0]
    if dark:
        rep.err("light", "%d written air cell(s) inside the wreck at block light 0, e.g. %s" % (len(dark), sorted(dark)[:5]))
    return level


def _supporter(W, c):
    """the cell a hung block hangs from or stands on, or None when the block needs none."""
    x, y, z = c
    s = W.b[c]
    bs, p = base(s), props(s)
    if bs == "minecraft:lantern":
        return (x, y + 1, z) if p.get("hanging") == "true" else (x, y - 1, z)
    if bs.endswith("_wall_sign") or bs == "minecraft:ladder" or bs.endswith("_wall_fan"):
        dx, dy, dz = FACING[p.get("facing", "north")]
        return (x - dx, y - dy, z - dz)
    if (bs.endswith("_carpet") or bs.endswith("_banner") or bs.endswith("_coral_fan") or bs.endswith("_sign")
            or re.match(r"minecraft:dead_(brain|tube|horn|fire|bubble)_coral$", bs)):
        return (x, y - 1, z)
    return None


def check_support(W, H, holes, rep):
    rep.ran("support")
    for c, s in W.b.items():
        bs = base(s)
        sup = _supporter(W, c)
        if sup is not None:
            ok = W.solid(*sup)
            if bs == "minecraft:lantern" and props(s).get("hanging") != "true":
                ok = W.floor(*sup) or bool(NOT_FLOOR.match(base(W.state(*sup))) and W.state(*sup) != "ground")
            if not ok:
                rep.err("support", "%s at %s has nothing at %s (%s)" % (bs, c, sup, W.state(*sup)))
        if bs in ("minecraft:sand", "minecraft:chipped_anvil", "minecraft:anvil", "minecraft:damaged_anvil"):
            below = W.state(c[0], c[1] - 1, c[2])
            if below in ("air", "water") or below == "minecraft:air":
                rep.err("support", "%s at %s over %s: it falls" % (bs, c, below))
        if bs in ("minecraft:air", "minecraft:cave_air"):
            up = (c[0], c[1] + 1, c[2])
            if up not in W.b and W.state(*up) == "ground":
                rep.err("support", "natural ground at %s over written air %s: it falls in" % (up, c))
    for x, z in holes:
        if W.ground(x, z) >= H.D:
            rep.err("support", "deck hole (%d, %d) where the ground y%d is at or over the deck y%d"
                    % (x, z, W.ground(x, z), H.D))
    # every component of written non-air blocks touches the ground
    solid = {c for c, s in W.b.items() if base(s) not in ("minecraft:air", "minecraft:cave_air")}
    seen = set()
    floating = []
    for c0 in solid:
        if c0 in seen:
            continue
        comp, q, grounded = [], [c0], False
        seen.add(c0)
        while q:
            c = q.pop()
            comp.append(c)
            x, y, z = c
            if y - 1 <= W.ground(x, z) and (x, y - 1, z) not in W.b:
                grounded = True
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n = (x + dx, y + dy, z + dz)
                if n in solid and n not in seen:
                    seen.add(n)
                    q.append(n)
                elif n not in W.b and W.state(*n) == "ground":
                    grounded = True
        if not grounded:
            floating.append(sorted(comp)[:3])
    if floating:
        rep.err("support", "%d component(s) of written blocks touch no ground, e.g. %s" % (len(floating), floating[:3]))


def _boxes_and_points(o, path=""):
    if isinstance(o, dict):
        if isinstance(o.get("id"), str) and OWN_IDS.match(o["id"]):
            return
        if isinstance(o.get("min"), list) and isinstance(o.get("max"), list) and len(o["min"]) in (2, 3):
            a, b = o["min"], o["max"]
            if len(a) == 3:
                yield "box", path, (a[0], a[2], b[0], b[2])
            else:
                yield "box", path, (a[0], a[1], b[0], b[1])
        if isinstance(o.get("x"), (int, float)) and isinstance(o.get("z"), (int, float)) and not isinstance(o["x"], bool):
            yield "point", path, (o["x"], o["z"], o["x"], o["z"])
        for k, v in o.items():
            yield from _boxes_and_points(v, path + "/" + str(k))
    elif isinstance(o, list):
        nums = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in o)
        if nums and len(o) == 4 and o[0] <= o[2] and o[1] <= o[3]:
            yield "box", path, tuple(o)
        elif nums and len(o) == 6 and o[0] <= o[3] and o[2] <= o[5]:
            yield "box", path, (o[0], o[2], o[3], o[5])
        elif nums and len(o) in (2, 3):
            yield "point", path, (o[0], o[-1], o[0], o[-1])
        elif not nums:
            for i, v in enumerate(o):
                yield from _boxes_and_points(v, "%s[%d]" % (path, i))


def check_footprint(doc, blocks, clears, unloaded, oversized, data, rep, tight=True):
    """tight: the recorded bounds must EQUAL the written span. They were measured on the canonical heightmap, so a
    test on other ground passes tight=False and keeps only the containment."""
    rep.ran("footprint")
    bx = doc["bounds"]

    def inside(c, k):
        lo, hi = bx[k]["min"], bx[k]["max"]
        return all(lo[i] <= c[i] <= hi[i] for i in range(3))

    out = [c for c in blocks if not inside(c, "wreck") and not inside(c, "strand")]
    if out:
        rep.err("footprint", "%d written block(s) outside the declared bounds, e.g. %s" % (len(out), sorted(out)[:4]))
    for k in ("wreck", "strand"):
        mine = [c for c in blocks if inside(c, k) and (k == "strand" or not inside(c, "strand"))]
        if not mine:
            rep.err("footprint", "no written block in bounds.%s" % k)
            continue
        got = ([min(c[i] for c in mine) for i in range(3)], [max(c[i] for c in mine) for i in range(3)])
        if tight and got != (bx[k]["min"], bx[k]["max"]):
            rep.err("footprint", "bounds.%s is %s-%s; the written blocks span %s-%s"
                    % (k, bx[k]["min"], bx[k]["max"], got[0], got[1]))
    for (box, st, target) in clears:
        if st != "minecraft:air" or target not in CLEARABLE:
            rep.err("footprint", "clearing fill writes %s over %s (only plants may be cleared; never water or "
                    "#minecraft:replaceable)" % (st, target))
    if unloaded:
        rep.err("footprint", "%d write(s) outside a force-loaded chunk, e.g. line %d: %s"
                % (len(unloaded), unloaded[0][0], unloaded[0][1][:80]))
    if oversized:
        rep.err("footprint", "%d fill(s) over %d blocks: %s" % (len(oversized), FILL_LIMIT, oversized[0][:80]))
    # another place's box or point
    xs = [c[0] for c in blocks] + [b[0] for b, _s, _t in clears] + [b[3] for b, _s, _t in clears]
    zs = [c[2] for c in blocks] + [b[2] for b, _s, _t in clears] + [b[5] for b, _s, _t in clears]
    fx0, fx1, fz0, fz1 = min(xs), max(xs), min(zs), max(zs)
    cols = {(c[0], c[2]) for c in blocks}
    for f in sorted(glob.glob(str(Path(data) / "*.json"))):
        name = Path(f).name
        if name in NOT_PLACES:
            continue
        try:
            d = load_json(f)
        except ValueError:
            continue
        for kind, path, (a0, b0, a1, b1) in _boxes_and_points(d):
            if a1 < fx0 or a0 > fx1 or b1 < fz0 or b0 > fz1:
                continue
            if kind == "point" and (a0, b0) not in cols:
                rep.note("footprint", "%s%s %s lies inside the clearing box but on no written column" % (name, path, (a0, b0)))
                continue
            hit = [c for c in cols if a0 <= c[0] <= a1 and b0 <= c[1] <= b1]
            if hit:
                rep.err("footprint", "%s%s %s %s holds %d written column(s), e.g. %s"
                        % (name, path, kind, (a0, b0, a1, b1), len(hit), sorted(hit)[:2]))
            else:
                rep.note("footprint", "%s%s %s overlaps the clearing box only" % (name, path, (a0, b0, a1, b1)))
    # route paths
    clear = load_json(Path(data) / "encounter_design.json")["rules"]["hearts"]["clear_of_path_blocks"]
    pts = [p for pl in load_json(Path(data) / "route_paths.json")["paths"].values() for p in pl]
    # the distance to the written columns' bounding rectangle is a lower bound; only when it is under the rule are
    # the columns themselves measured
    near = min(math.hypot(max(fx0 - px, 0, px - fx1), max(fz0 - pz, 0, pz - fz1)) for px, pz in pts)
    if near < clear:
        near = min(math.hypot(px - x, pz - z) for px, pz in pts
                   if math.hypot(max(fx0 - px, 0, px - fx1), max(fz0 - pz, 0, pz - fz1)) < clear for x, z in cols)
    if near < clear:
        rep.err("footprint", "a written block is %.0f blocks from a route path (rule: %d)" % (near, clear))
    rep.note("footprint", "nearest route path %.0f blocks from a written column" % near)


def walk(W, start, domain, keep=None):
    """{feet cell} reachable from start: two-high, steps of at most one, ladders climbable. keep(x, z) limits it."""
    x0, x1, y0, y1, z0, z1 = domain

    def ok(x, y, z):
        if not (x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1):
            return False
        if keep is not None and not keep(x, z):
            return False
        if not (W.passable(x, y, z) and W.passable(x, y + 1, z)):
            return False
        return W.floor(x, y - 1, z) or W.ladder(x, y, z) or W.ladder(x, y - 1, z)

    if not ok(*start):
        return set()
    seen = {start}
    q = deque([start])
    while q:
        x, y, z = q.popleft()
        nxt = []
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            nxt.append((nx, y, nz))
            if W.passable(x, y + 2, z):
                nxt.append((nx, y + 1, nz))
            if W.passable(nx, y + 1, nz):
                nxt.append((nx, y - 1, nz))
        if W.ladder(x, y, z):
            nxt.append((x, y + 1, z))
        if W.ladder(x, y - 1, z):
            nxt.append((x, y - 1, z))
        for n in nxt:
            if n not in seen and ok(*n):
                seen.add(n)
                q.append(n)
    return seen


def check_walk(doc, W, H, reward, rep):
    rep.ran("walk")
    w = doc["wreck"]
    sx, sz = H.W, H.Z0 + H.L
    start = (sx, W.ground(sx, sz) + 1, sz)
    domain = (H.W - 50, H.W + 50, H.K - 6, H.D + 25, H.Z0 - 15, H.Z0 + H.L + 60)
    reach = walk(W, start, domain)
    if not reach:
        rep.err("walk", "the start %s on the sand behind the transom is not a two-high stand" % (start,))
        return set()
    bulk = H.Z0 + w["bulkhead"]
    spill = H.Z0 + w["hold"]["spill_slope_to"]
    berth = [c for c in reach if c[1] == H.F + 1 and bulk < c[2] < H.Z0 + H.L - 1 and H.in_footprint(c[0], c[2])]
    hold = [c for c in reach if c[1] == H.F + 1 and spill < c[2] < bulk and H.in_footprint(c[0], c[2])]
    if not berth:
        rep.err("walk", "the berth (feet y%d, z%d-%d) is not reached from %s" % (H.F + 1, bulk + 1, H.Z0 + H.L - 2, start))
    if not hold:
        rep.err("walk", "the cargo hold (feet y%d, z%d-%d) is not reached from %s" % (H.F + 1, spill + 1, bulk - 1, start))
    else:
        cab = H.Z0 + w["cabin"]["from"]
        inner = walk(W, min(hold), domain, keep=H.in_footprint)
        deck = [c for c in inner if c[1] == H.D + 1 and c[2] < cab]
        if not deck:
            rep.err("walk", "the deck (feet y%d) is not reached from the hold without leaving the hull: no way up "
                    "through the hatch at (%d, %d, %d)" % (H.D + 1, H.W, H.D, H.Z0 + w["hatch_at"]))
    if reward:
        lo, hi = reward["trigger"]["min"], reward["trigger"]["max"]
        inbox = [c for c in reach if all(lo[i] <= c[i] <= hi[i] for i in range(3))]
        if not inbox:
            rep.err("walk", "no reachable stand inside the cache's trigger box %s-%s" % (lo, hi))
    rep.note("walk", "%d reachable stands from %s; berth %d, hold %d" % (len(reach), start, len(berth), len(hold)))
    return reach


def _blocks_of(data):
    return load_json(Path(data) / "habitat_blocks.json")["blocks"]


def _range(b):
    if b.get("style") == "activated":
        return (b.get("activated") or {}).get("spawn_range")
    return b.get("range_of_influence")


def check_wards(doc, W, H, data, rep):
    rep.ran("wards")
    habs = _blocks_of(data)
    by = {b["id"]: b for b in habs}
    cx, cz = doc["site"]["centre"]
    pool = "cobblers:%s" % doc["pool"]["id"]
    spawns = load_json(Path(data) / "spawns.json")
    if not any(h.get("id") == doc["pool"]["id"] for h in spawns.get("habitats", [])):
        rep.err("wards", "pool %s is not a habitat in data/spawns.json" % doc["pool"]["id"])
    mine = []
    for spec in doc["pool"]["blocks"]:
        rec = by.get(spec["id"])
        if rec is None:
            rep.err("wards", "%s is not in data/habitat_blocks.json" % spec["id"])
            continue
        if "at" in spec:
            x, z = cx + spec["at"][0], cz + spec["at"][1]
            y = W.ground(x, z) - spec["below_ground"]
        else:
            x, z = H.W, H.Z0 + spec["lz"]
            y = H.K - spec["below_keel"]
        p = rec["position"]
        if (p["x"], p["y"], p["z"]) != (x, y, z):
            rep.err("wards", "%s is at %s; the data's geometry puts it at %s" % (spec["id"], (p["x"], p["y"], p["z"]), (x, y, z)))
        if rec.get("style") != "natural" or rec.get("replace_spawns") is not True:
            rep.err("wards", "%s is not a natural ReplaceSpawns block" % spec["id"])
        if rec.get("range_of_influence") != spec["range"]:
            rep.err("wards", "%s range %s, declared %s" % (spec["id"], rec.get("range_of_influence"), spec["range"]))
        if rec.get("pool") != pool:
            rep.err("wards", "%s pool %s, expected %s" % (spec["id"], rec.get("pool"), pool))
        c = (p["x"], p["y"], p["z"])
        if c in W.b:
            rep.err("wards", "%s at %s is in a written block (%s)" % (spec["id"], c, base(W.b[c])))
        if W.ground(p["x"], p["z"]) < W.sea:
            rep.err("wards", "%s at %s is in the sea (ground y%d)" % (spec["id"], c, W.ground(p["x"], p["z"])))
        lo, hi = doc["bounds"]["wreck"]["min"], doc["bounds"]["wreck"]["max"]
        if not (lo[0] <= p["x"] <= hi[0] and lo[2] <= p["z"] <= hi[2]):
            rep.err("wards", "%s at %s is outside the place's bounds" % (spec["id"], c))
        r = rec.get("range_of_influence") or 0
        wet = sum(1 for dx in range(-r, r + 1) for dz in range(-r, r + 1)
                  if dx * dx + dz * dz <= r * r and W.ground(p["x"] + dx, p["z"] + dz) < W.sea)
        rep.note("wards", "%s at %s: %d column(s) of its range are sea" % (spec["id"], c, wet))
        mine.append(rec)
    for a in mine:
        pa = a["position"]
        for o in habs:
            if o["id"] == a["id"] or _range(o) is None:
                continue
            po = o["position"]
            d = math.dist((pa["x"], pa["y"], pa["z"]), (po["x"], po["y"], po["z"]))
            if d < _range(a) + _range(o):
                rep.err("wards", "%s overlaps %s (%s): %.1f apart, ranges %d + %d"
                        % (a["id"], o["id"], o.get("style"), d, _range(a), _range(o)))


def check_castellan(doc, W, spawn_text, data, jar, rep):
    rep.ran("castellan")
    cx, cz = doc["site"]["centre"]
    design = load_json(Path(data) / "encounter_design.json")["rules"]["hearts"]
    pts = [p for pl in load_json(Path(data) / "route_paths.json")["paths"].values() for p in pl]
    habs = _blocks_of(data)
    own = {s["id"] for s in doc["pool"]["blocks"]}
    for r in doc["residents"]:
        pk = r["pokemon"]
        x, z = cx + pk["at"][0], cz + pk["at"][1]
        gy = W.ground(x, z)
        if gy < W.sea:
            rep.err("castellan", "%s's anchor (%d, %d) is in the sea (ground y%d)" % (pk["id"], x, z, gy))
        wet = [(x + dx, z + dz) for dx in range(-3, 4) for dz in range(-3, 4)
               if dx * dx + dz * dz <= 9 and W.ground(x + dx, z + dz) < W.sea]
        if not wet:
            rep.err("castellan", "%s's anchor (%d, %d): no sea within 3" % (pk["id"], x, z))
        for y in (gy + 1, gy + 2):
            if (x, y, z) in W.b:
                rep.err("castellan", "%s's anchor (%d, %d, %d) is built on (%s)" % (pk["id"], x, y, z, base(W.b[(x, y, z)])))
        want = '{x:"%.1f",y:%d,z:"%.1f"' % (x + 0.5, gy + 1, z + 0.5)
        if want not in spawn_text:
            rep.err("castellan", "the spawn function does not summon at %s (ground + 1)" % want)
        d = min(math.hypot(px - x, pz - z) for px, pz in pts)
        if d < design["clear_of_path_blocks"]:
            rep.err("castellan", "%s is %.0f blocks from a route path (rule %d)" % (pk["id"], d, design["clear_of_path_blocks"]))
        leash = pk["leash"]
        for b in habs:
            dd = math.hypot(b["position"]["x"] - x, b["position"]["z"] - z)
            if b.get("style") == "activated" and dd < b["activated"]["spawn_range"] + leash:
                rep.err("castellan", "%s's leash %d overlaps activated %s's spawns (%.0f apart, needs %d)"
                        % (pk["id"], leash, b["id"], dd, b["activated"]["spawn_range"] + leash))
            elif b.get("style") == "natural" and b["id"] not in own and dd < (b.get("range_of_influence") or 0) + leash:
                rep.err("castellan", "%s's leash %d overlaps another place's natural %s (%.0f apart)" % (pk["id"], leash, b["id"], dd))
            elif b["id"] in own and dd < (b.get("range_of_influence") or 0) + leash:
                rep.note("castellan", "%s's leash reaches its own ward %s (%.0f apart): its own pool, by design"
                         % (pk["id"], b["id"], dd))
        cap = design["next_cap"][str(doc["pool"]["tier"])]
        if pk["level"] > cap:
            rep.err("castellan", "%s L%d over tier %s's ceiling %d" % (pk["id"], pk["level"], doc["pool"]["tier"], cap))
        if jar is not None and not jar.species(pk["species"].split(":", 1)[1]):
            rep.err("castellan", "%s is not a species in the jar" % pk["species"])


def check_cache(doc, W, H, reward, jar, rep):
    rep.ran("cache")
    if reward is None:
        rep.err("cache", "data/rewards.json has no reward %s" % doc["find"]["reward"])
        return
    c = tuple(reward["container"]["at"])
    if base(W.b.get(c, "minecraft:air")) != "minecraft:barrel":
        rep.err("cache", "the container %s is %s, not a written barrel" % (c, W.b.get(c)))
    cab = doc["wreck"]["cabin"]
    lz = c[2] - H.Z0
    if not (cab["from"] <= lz < H.L and abs(c[0] - H.W) < H.hw0[lz] and H.D + 1 <= c[1] <= H.D + cab["height"]):
        rep.err("cache", "the container %s is not inside the cabin (z%d-%d, y%d-%d)"
                % (c, H.Z0 + cab["from"], H.Z0 + H.L - 1, H.D + 1, H.D + cab["height"]))
    lo, hi = reward["trigger"]["min"], reward["trigger"]["max"]
    if not all(lo[i] <= c[i] <= hi[i] for i in range(3)):
        rep.err("cache", "the trigger box %s-%s does not hold the container %s" % (lo, hi, c))
    items = [i["item"] for i in reward["contents"]]
    if sorted(items) != sorted(i for i, _n in doc["find"]["contents"]):
        rep.err("cache", "data/rewards.json pays %s; data/desert_wreck.json find says %s" % (items, doc["find"]["contents"]))
    if jar is not None:
        for it in items:
            if not jar.item(it):
                rep.err("cache", "%s is not an item in the Cobblemon 1.8.0 jar" % it)


def check_pool(doc, data, jar, rep):
    rep.ran("pool")
    if jar is None:
        rep.note("pool", "no jar: species not checked")
        return
    for e in doc["pool"]["entries"]:
        name = e[0]
        sp, _, form = name.partition(" ")
        if not jar.species(sp, form):
            rep.err("pool", "%s is not in the jar" % name)


class Jar:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.names = set(self.z.namelist())
        self.lang = json.loads(self.z.read("assets/cobblemon/lang/en_us.json"))
        self.sp = {}
        for n in self.names:
            m = re.match(r"data/cobblemon/species/[^/]+/([a-z0-9_]+)\.json$", n)
            if m:
                self.sp[m.group(1)] = n

    def item(self, iid):
        ns, _, p = iid.partition(":")
        return ("assets/%s/models/item/%s.json" % (ns, p) in self.names
                and ("item.%s.%s" % (ns, p) in self.lang or "block.%s.%s" % (ns, p) in self.lang))

    def species(self, name, form=""):
        n = self.sp.get(name)
        if n is None:
            return False
        if not form:
            return True
        d = json.loads(self.z.read(n))
        return any(form in [a.lower() for a in (f.get("aspects") or [])] for f in d.get("forms") or [])


def audit(doc, pack, g, data=DATA, jar=None, tight_bounds=True):
    rep = Report()
    build_text, spawn_text = read_pack(pack)
    blocks, order, clears, unloaded, oversized = parse_build(build_text)
    sea = int((load_json(Path(data) / "world.json").get("vertical") or {}).get("sea_level", 62))
    W = World(blocks, g, sea)
    H = Hull(doc, g)
    rewards = load_json(Path(data) / "rewards.json")["rewards"]
    reward = next((r for r in rewards if r.get("id") == doc["find"]["reward"]), None)
    check_seating(doc, g, H, rep)
    holes = check_shape(doc, H, blocks, rep)
    check_sea(W, rep)
    ids = check_palette(doc, blocks, rep)
    check_spawn_conditions(doc, ids, load_json(Path(data) / "spawn_blocks.json"),
                           load_json(Path(data) / "spawn_block_policy.json"), rep)
    check_light(W, H, doc, holes, rep)
    check_support(W, H, holes, rep)
    check_footprint(doc, blocks, clears, unloaded, oversized, data, rep, tight_bounds)
    check_walk(doc, W, H, reward, rep)
    check_wards(doc, W, H, data, rep)
    check_castellan(doc, W, spawn_text, data, jar, rep)
    check_cache(doc, W, H, reward, jar, rep)
    check_pool(doc, data, jar, rep)
    rep.note("blocks", "%d cells written, %d clearing fills" % (len(blocks), len(clears)))
    return rep


def find_jar():
    for p in JAR_CANDIDATES:
        if p.is_file():
            return p
    hits = sorted(Path(r"C:/Users/wnd/Documents").rglob("Cobblemon-fabric-1.8.0*.jar"))
    return hits[0] if hits else None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Independent audit of the Brass Petrel's built pack.")
    ap.add_argument("--pack", default=str(DEFAULT_PACK))
    ap.add_argument("--data", default=str(DATA / "desert_wreck.json"))
    ap.add_argument("--jar", default=None)
    ap.add_argument("--source-root")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as G
    if not (Path(a.pack) / "data").is_dir():
        print("desert_wreck_audit: no pack at %s: run python tools/desert_wreck.py build first" % a.pack)
        return 2
    jp = Path(a.jar) if a.jar else find_jar()
    jar = Jar(jp) if jp and jp.is_file() else None
    rep = audit(load_json(a.data), a.pack, G.load(a.source_root), DATA, jar)
    if jar is None:
        rep.notes.append("jar: no Cobblemon 1.8.0 jar found: species and items NOT checked")
    for e in rep.errors:
        print("PROBLEM " + e)
    if a.verbose:
        for n in rep.notes:
            print("note " + n)
    print("desert_wreck_audit: %d problem(s) over %d checks (%s)%s" % (
        len(rep.errors), len(rep.checks), ", ".join(sorted(rep.checks)), "" if jar else "; jar NOT checked"))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
