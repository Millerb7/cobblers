#!/usr/bin/env python
"""An independent water, light and reach audit of the five places built on 2026-10-09: the Drowned Quarry, the Fungal
Isle's Glowcap Hollow pool, the Merian ice lodge's tarn, Gull Rock and Hummock Mere.

WHY IT IS INDEPENDENT. Each place's builder wrote its own audit; this one shares none of their derivation. It never
imports a place's geometry helpers (no Model, no plan, no profile function). It runs each place's GENERATOR to a
temporary directory, reads the .mcfunction files that come out, and replays every `fill`, `setblock` and `forceload`
in the order the re-application runs them (each generator's placement_steps) into its own block model:

  the world before the build   solid at and under round(heightmap) (tools/ground.py), water over a column that
                               tools/water_mask.py paints (a lake basin under its level_y, or the sea) from the ground
                               up to and including that level, air above. Its own vectorised even-odd raster of the
                               basins, cross-checked against water_mask.level_at by the tests.
  the build                    every command replayed; `replace <filter>` evaluated against the cell as it is at that
                               moment; a fill over 32,768 blocks refused as the server refuses it; a write into a chunk
                               no forceload holds at that moment refused and reported.

WHAT IT CHECKS, on the replayed result:

  containment   no water (a water block, or anything waterlogged) next to a cell water flows into (air, or a plant the
                flow washes out) across a side or downward, where either cell was written by the build: water written
                where it cannot be held, or an air pocket opened against water (a carve the lake drains into).
  light         no plain `minecraft:ice` at block light 11 or more. ASSUMED, not read from the jar: vanilla 1.21.1
                IceBlock.randomTick melts ice when block light > 11 - the ice's own light block, and ice's light block
                is 1. Light is propagated conservatively (every block not a known opaque full cube passes light, each
                step costs 1), so a pass is safe and a failure may be pessimistic.
  bounds        every write inside the place's declared box (data/<place>.json), and inside a forceloaded chunk.
  spawn         no block named by data/spawn_blocks.json unless a data/spawn_block_policy.json whitelist entry for that
                block is scoped to this place.
  reach         the walkable and swimmable routes the design promises, for a player 0.6 x 1.8 who steps or jumps up
                at most 1.25, falls at most 3 (any height into water), climbs out of water onto a surface at most one
                block above the top water block, and swims through water. Reachable from outside AND back: a node a
                player can reach and not leave is a softlock.
  swim          (the quarry) the 26-neighbour shortest swim from any breathing cell to the portal, the hall's door and the
                sump, timed at a sprint-swim of 5 blocks/s (docs/mechanics/WATER_MAP.md line 40) against vanilla's 15 s
                of air (line 27) and Surf's 45 s more (data/blackout.json water.surf_bonus_ticks 900).
  fatigue       (Gull Rock) the least surface-fatigue swim from wading water to a skerry a player can climb onto,
                with data/blackout.json `surface` (gain 4/tick where 3+ blocks deep, 1 shallower; first hit at
                collapse_ticks 1200) at 5 blocks/s (STATE "Surface exhaustion": "first hit at 15 s (about 75 blocks)").

WHAT IT DOES NOT COVER. Natural caves, overhangs, trees, grass and snow layers (the heightmap has none, so a removed
shell course is invisible here: the shell guards against cavities the heightmap cannot show); the real block material
of the surface (a `replace minecraft:mycelium` whose result is solid changes nothing it models; one whose result is
not solid is reported as unreplayable); anything another pack writes over the same ground; fluid physics beyond one
step of flow; whether ice freezes or the Lead stays open (biome temperature is not modelled); mobs, entities and
spawning; anything in a running game. Validity is not behaviour.

  python tools/new_places_water_audit.py                   # all five, a verdict line each and every problem
  python tools/new_places_water_audit.py --place rookery --json out.json
"""
from __future__ import annotations

import argparse
import contextlib
import heapq
import importlib
import io
import json
import math
import re
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

FILL_MAX = 32768                 # the server refuses a larger fill (vanilla `fill` limit, game rule default)
PLAYER_H = 1.8
JUMP = 1.25
FALL = 3.0
CLIMB_OUT = 2.0                  # a surface at most this far above the top water BLOCK's y (one block over the water)
SPRINT_SWIM = 5.0                # blocks/s: docs/mechanics/WATER_MAP.md line 40
AIR_NO_MOUNT = 15.0              # s: WATER_MAP.md line 27, vanilla's 300 ticks
MELT_ABOVE = 10                  # ASSUMED: ice melts at block light > 11 - 1 (ice's light block)

PLACES = ("drowned_quarry", "fungal_isle", "ice_lodge", "rookery", "hummock_mere")


def jload(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def surf_air():
    """Seconds a Surf-trained player holds under water: the bonus then vanilla's 15 (data/blackout.json, WATER_MAP 28)."""
    return jload("data/blackout.json")["water"]["surf_bonus_ticks"] / 20.0 + AIR_NO_MOUNT


# ------------------------------------------------------------------------------------------------ block properties

_STATE = re.compile(r"([#a-z0-9_.:/-]+)(\[[^\]]*\])?")
REPLACEABLE = {"air", "cave_air", "void_air", "water", "lava", "short_grass", "fern", "dead_bush", "seagrass",
               "tall_seagrass", "fire", "soul_fire", "snow", "vine", "glow_lichen", "light", "tall_grass", "large_fern",
               "structure_void", "bubble_column", "warped_roots", "nether_sprouts", "crimson_roots", "hanging_roots"}
AIRS = {"air", "cave_air", "void_air", "base:air"}
# no collision AND water flows into them, washing them out
WASHABLE = {"short_grass", "tall_grass", "fern", "large_fern", "dead_bush", "vine", "red_mushroom", "brown_mushroom",
            "torch", "wall_torch", "redstone_torch", "redstone_wall_torch", "snow", "dandelion", "poppy", "blue_orchid",
            "allium", "azure_bluet", "oxeye_daisy", "cornflower", "lily_of_the_valley", "sweet_berry_bush", "glow_lichen",
            "hanging_roots", "nether_sprouts", "crimson_roots", "warped_roots", "fire", "light", "structure_void"}
WATERY = {"water", "kelp", "kelp_plant", "seagrass", "tall_seagrass", "bubble_column", "base:water"}
OPAQUE_NAMES = {"stone", "cobblestone", "mossy_cobblestone", "andesite", "diorite", "granite", "tuff", "calcite", "dirt",
                "coarse_dirt", "rooted_dirt", "mud", "packed_mud", "gravel", "sand", "red_sand", "podzol", "mycelium",
                "grass_block", "packed_ice", "blue_ice", "mushroom_stem", "barrel", "loom", "fletching_table", "smoker",
                "furnace", "blast_furnace", "bookshelf", "verdant_froglight", "pearlescent_froglight",
                "ochre_froglight", "shroomlight", "glowstone", "sea_lantern", "deepslate", "clay", "crafting_table",
                "jack_o_lantern", "pumpkin", "melon", "base:terrain"}
OPAQUE_SUFFIX = ("_planks", "_log", "_wood", "_bricks", "_terracotta", "_concrete", "_ore", "_hyphae",
                 "mushroom_block", "hay_block", "snow_block", "bone_block", "dried_kelp_block", "moss_block", "_wool")
EMIT = {"lantern": 15, "soul_lantern": 10, "campfire": 15, "soul_campfire": 10, "verdant_froglight": 15,
        "pearlescent_froglight": 15, "ochre_froglight": 15, "shroomlight": 15, "glowstone": 15, "sea_lantern": 15,
        "torch": 14, "wall_torch": 14, "jack_o_lantern": 15, "redstone_torch": 7, "end_rod": 14, "lava": 15,
        "beacon": 15, "conduit": 15, "lava_cauldron": 15, "glow_berries": 14}


def parse_state(s):
    m = _STATE.match(s)
    if not m:
        return s, {}
    bid = m.group(1)
    props = {}
    if m.group(2):
        for kv in m.group(2)[1:-1].split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                props[k.strip()] = v.strip()
    if ":" not in bid:
        bid = "minecraft:" + bid
    return bid, props


def short(bid):
    return bid if bid.startswith("base:") else bid.split(":", 1)[1]


class Props:
    __slots__ = ("water", "open", "top", "opaque", "emit", "air")


_PROPS = {}


def props(state):
    """(water-bearing, water flows into it, collision top in blocks (0 none), opaque to light, light emitted, is air)."""
    p = _PROPS.get(state)
    if p is not None:
        return p
    bid, pr = parse_state(state)
    n = short(bid)
    p = Props()
    p.air = n in AIRS
    p.water = n in WATERY or pr.get("waterlogged") == "true"
    p.open = (p.air or n in WASHABLE) and not p.water
    passable = p.air or n in WASHABLE or n in WATERY or n.endswith("_sign") or n.endswith("_door") \
        or n.endswith("pressure_plate") or n.endswith("_button") or n in ("rail", "ladder", "cobweb", "lever") \
        or n.endswith("_banner")
    if passable:
        top = 0.0
    elif n.endswith("_slab"):
        top = 0.5 if pr.get("type", "bottom") == "bottom" else 1.0
    elif n.endswith("_carpet"):
        top = 0.0625
    elif n.endswith("_fence") or n.endswith("_fence_gate") or (n.endswith("_wall") and not n.endswith("wall_sign")):
        top = 1.5
    elif n.endswith("_bed"):
        top = 0.5625
    elif n in ("campfire", "soul_campfire"):
        top = 0.4375
    elif n in ("lantern", "soul_lantern"):
        top = 0.625
    elif n.endswith("_trapdoor"):
        top = 0.1875
    elif n in ("mud", "soul_sand"):
        top = 0.875
    elif n == "lily_pad":
        top = 0.09375
    else:
        top = 1.0
    p.top = top
    p.opaque = n in OPAQUE_NAMES or (n.endswith(OPAQUE_SUFFIX) and not n.endswith(("_wall", "_slab", "_stairs")))
    lit = pr.get("lit", "true") != "false"
    p.emit = EMIT.get(n, 0) if lit else 0
    _PROPS[state] = p
    return p


def tag_match(state, tag):
    n = short(parse_state(state)[0])
    n = {"base:air": "air", "base:water": "water"}.get(n, n)
    if tag == "#minecraft:replaceable":
        return n in REPLACEABLE
    if tag == "#minecraft:logs":
        return n != "mushroom_stem" and n.endswith(("_log", "_wood", "_stem", "_hyphae"))
    if tag == "#minecraft:leaves":
        return n.endswith("_leaves")
    raise ValueError("unknown tag %s" % tag)


def state_match(state, filt):
    if filt.startswith("#"):
        return tag_match(state, filt)
    fid, fp = parse_state(filt)
    sid, sp = parse_state(state)
    return sid == fid and all(sp.get(k) == v for k, v in fp.items())


def split_block(rest):
    """(block state with its NBT, the remaining words) from the text after a command's coordinates."""
    i, depth, q = 0, 0, None
    while i < len(rest):
        c = rest[i]
        if q:
            if c == "\\":
                i += 1
            elif c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == " " and depth == 0:
            break
        i += 1
    return rest[:i], rest[i:].split()


# ------------------------------------------------------------------------------------------------ the world before


def even_odd(polys, X, Z):
    """tools/water_mask.in_polygons over a grid: each ring's parity, OR across rings."""
    out = np.zeros(X.shape, bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        for poly in polys:
            c = np.zeros(X.shape, bool)
            n = len(poly)
            j = n - 1
            for i in range(n):
                xi, zi = poly[i]
                xj, zj = poly[j]
                if zi != zj:
                    c ^= ((zi > Z) != (zj > Z)) & (X < (xj - xi) * (Z - zi) / float(zj - zi) + xi)
                j = i
            out |= c
    return out


class Base:
    """The world as the export left it: ground from tools/ground.py, painted water from tools/water_mask.py."""

    def __init__(self, g):
        import water_mask as WM
        self.g, self.WM = g, WM
        self.bodies = WM.bodies()
        self.sea = WM.sea_level()
        self.cols = {}

    def prime(self, x0, z0, x1, z1):
        G = self.g.box(x0, z0, x1, z1)
        X, Z = np.meshgrid(np.arange(x0, x1 + 1), np.arange(z0, z1 + 1))
        lev = np.full(G.shape, -10 ** 6)
        for b in self.bodies.values():
            if not b["basin"]:
                continue
            pts = [q for r in b["basin"] for q in r]
            if max(p[0] for p in pts) < x0 or min(p[0] for p in pts) > x1 or \
                    max(p[1] for p in pts) < z0 or min(p[1] for p in pts) > z1:
                continue
            wet = even_odd(b["basin"], X, Z) & (G < b["level_y"])
            lev = np.where(wet & (b["level_y"] > lev), b["level_y"], lev)
        lev = np.where((lev == -10 ** 6) & (G < self.sea), self.sea, lev)
        for zi in range(G.shape[0]):
            for xi in range(G.shape[1]):
                L = int(lev[zi, xi])
                self.cols[(x0 + xi, z0 + zi)] = (int(G[zi, xi]), L if L > -10 ** 6 else None)

    def col(self, x, z):
        c = self.cols.get((x, z))
        if c is None:
            _b, L = self.WM.level_at(x, z, self.g, self.bodies, self.sea)
            c = self.cols[(x, z)] = (self.g(x, z), L)
        return c

    def state(self, x, y, z):
        gy, L = self.col(x, z)
        if y <= gy:
            return "base:terrain"
        if L is not None and y <= L:
            return "base:water"
        return "base:air"


# ------------------------------------------------------------------------------------------------ the replay


class Replay:
    """Every block write of a pack's functions, in order, over a Base. `roi` (x0, y0, z0, x1, y1, z1) clips what is
    stored; commands are still checked whole."""

    def __init__(self, base, roi=None):
        self.base, self.roi = base, roi
        self.w, self.src = {}, {}
        self.loaded = set()
        self.cmds = []           # (function, kind, box, block)
        self.problems = []

    def get(self, x, y, z):
        s = self.w.get((x, y, z))
        return s if s is not None else self.base.state(x, y, z)

    def _problem(self, kind, msg):
        self.problems.append((kind, msg))

    def run_steps(self, steps, pack):
        for st in steps:
            if st[0] == "cmd":
                self.command(st[1], "<step>", pack)
            elif st[0] == "fn":
                self.function(st[1], pack)

    def function(self, ref, pack, depth=0):
        if depth > 16:
            self._problem("replay", "function nesting over 16 at %s" % ref)
            return
        ns, path = ref.split(":", 1)
        f = Path(pack) / "data" / ns / "function" / (path + ".mcfunction")
        if not f.exists():
            self._problem("replay", "%s: no such function in the generated pack" % ref)
            return
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("$"):
                self.command(line, path, pack, depth)

    def command(self, line, fn, pack, depth=0):
        w = line.split(" ")
        head = w[0]
        if head == "forceload" and len(w) >= 2 and w[1] in ("add", "remove"):
            if w[1] == "remove" and len(w) >= 3 and w[2] == "all":
                self.loaded.clear()
                return
            nums = [int(float(v)) for v in w[2:6]]
            if len(nums) == 2:
                nums += nums
            x0, z0, x1, z1 = nums
            ch = {(cx, cz) for cx in range(min(x0, x1) >> 4, (max(x0, x1) >> 4) + 1)
                  for cz in range(min(z0, z1) >> 4, (max(z0, z1) >> 4) + 1)}
            if w[1] == "add":
                self.loaded |= ch
            else:
                self.loaded -= ch
        elif head == "function" and len(w) == 2:
            self.function(w[1], pack, depth + 1)
        elif head == "fill":
            self.fill(line, fn)
        elif head == "setblock":
            self.setblock(line, fn)
        elif head == "execute" and re.search(r" run (fill|setblock|clone|place) ", line):
            self._problem("replay", "%s: a conditional block write is not replayed: %s" % (fn, line[:120]))
        elif head in ("clone", "place"):
            self._problem("replay", "%s: %s is not replayed: %s" % (fn, head, line[:120]))

    def _held(self, box, fn, line):
        x0, _y0, z0, x1, _y1, z1 = box
        for cx in range(x0 >> 4, (x1 >> 4) + 1):
            for cz in range(z0 >> 4, (z1 >> 4) + 1):
                if (cx, cz) not in self.loaded:
                    self._problem("hold", "%s: writes into chunk (%d, %d), which no forceload holds when it runs: %s"
                                  % (fn, cx, cz, line[:100]))
                    return False
        return True

    def _clip(self, box):
        if self.roi is None:
            return box
        a = tuple(max(box[i], self.roi[i]) for i in range(3)) + tuple(min(box[i + 3], self.roi[i + 3]) for i in range(3))
        return a if all(a[i] <= a[i + 3] for i in range(3)) else None

    def fill(self, line, fn):
        w = line.split(" ", 7)
        c = [int(v) for v in w[1:7]]
        box = (min(c[0], c[3]), min(c[1], c[4]), min(c[2], c[5]), max(c[0], c[3]), max(c[1], c[4]), max(c[2], c[5]))
        block, more = split_block(w[7])
        mode = more[0] if more else "replace"
        filt = more[1] if mode == "replace" and len(more) > 1 else None
        vol = (box[3] - box[0] + 1) * (box[4] - box[1] + 1) * (box[5] - box[2] + 1)
        self.cmds.append((fn, "fill", box, block))
        if vol > FILL_MAX:
            self._problem("fill", "%s: a fill of %d blocks, over %d: the server refuses it: %s" % (fn, vol, FILL_MAX, line[:100]))
            return
        if not self._held(box, fn, line):
            return
        if mode not in ("replace", "destroy", "keep"):
            self._problem("replay", "%s: fill mode %s is not replayed" % (fn, mode))
            return
        cb = self._clip(box)
        if cb is None:
            return
        solid_result = props(block).top >= 1.0 and not props(block).water
        for y in range(cb[1], cb[4] + 1):
            for z in range(cb[2], cb[5] + 1):
                for x in range(cb[0], cb[3] + 1):
                    if mode == "keep" and not props(self.get(x, y, z)).air:
                        continue
                    if filt is not None:
                        cur = self.get(x, y, z)
                        if cur == "base:terrain" and not filt.startswith("#") and not solid_result:
                            self._problem("replay", "%s: `replace %s` with %s at (%d, %d, %d) depends on the natural "
                                                    "surface's material, which no heightmap holds" % (fn, filt, block, x, y, z))
                            continue
                        if not state_match(cur, filt):
                            continue
                    self.w[(x, y, z)] = block
                    self.src[(x, y, z)] = fn

    def setblock(self, line, fn):
        w = line.split(" ", 4)
        x, y, z = (int(v) for v in w[1:4])
        block, more = split_block(w[4])
        mode = more[0] if more else "replace"
        box = (x, y, z, x, y, z)
        self.cmds.append((fn, "setblock", box, block))
        if not self._held(box, fn, line):
            return
        if self._clip(box) is None:
            return
        if mode == "keep" and not props(self.get(x, y, z)).air:
            return
        self.w[(x, y, z)] = block
        self.src[(x, y, z)] = fn


# ------------------------------------------------------------------------------------------------ generation


@contextlib.contextmanager
def _quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def _write_pack(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, v in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(v, (list, tuple)):
            text = "\n".join(v) + "\n"
        elif isinstance(v, dict):
            text = json.dumps(v, indent=2) + "\n"
        else:
            text = v
        f.write_text(text, encoding="utf-8", newline="\n")
    return out


def generate(place, out, g, check=True):
    """(steps, pack directory): the place's generator run to `out`, and the re-application's order for it."""
    mod = importlib.import_module(place)
    with _quiet():
        if place == "drowned_quarry":
            doc = mod.load()
            files = mod.files(doc, g)
            steps = mod.placement_steps(doc, g)
        elif place == "fungal_isle":
            doc = mod.load()
            pl = mod.plan(doc, g)
            files, _pl = mod.files(pl=pl, check=check)
            steps = mod.placement_steps(pl=pl)
        elif place == "ice_lodge":
            doc = mod.load()
            files, _pl, _meta = mod.files(doc, g)
            steps = mod.placement_steps(doc, g)
        elif place == "rookery":
            doc = mod.load()
            files, _m = mod.files(doc, g, check=check)
            steps = mod.placement_steps(doc, g)
        elif place == "hummock_mere":
            doc = mod.load()
            files, _b = mod.files(doc, g, check=check)
            steps = mod.placement_steps(doc, g)
        else:
            raise ValueError(place)
    return [s for s in steps if s[0] in ("cmd", "fn")], _write_pack(files, out)


# ------------------------------------------------------------------------------------------------ the checks


SIDES_DOWN = ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0))
SIDES_UP = ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0))


def containment(rp, only=None):
    """[((x, y, z) water, (x, y, z) open)] where water would flow out, at least one side written by the build."""
    out = set()
    for (x, y, z), s in rp.w.items():
        if only and rp.src[(x, y, z)] not in only:
            continue
        p = props(s)
        if p.water:
            for dx, dy, dz in SIDES_DOWN:
                n = (x + dx, y + dy, z + dz)
                if props(rp.get(*n)).open:
                    out.add(((x, y, z), n))
        elif p.open:
            for dx, dy, dz in SIDES_UP:
                n = (x + dx, y + dy, z + dz)
                if props(rp.get(*n)).water:
                    out.add((n, (x, y, z)))
    return sorted(out)


def light_at_ice(rp, only=None):
    """([(ice cell, block light)] for every written plain ice cell over MELT_ABOVE, the brightest plain ice), light
    propagated conservatively."""
    ice = [c for c, s in rp.w.items() if parse_state(s)[0] == "minecraft:ice" and (not only or rp.src[c] in only)]
    if not ice:
        return [], 0
    srcs = [(c, props(s).emit) for c, s in rp.w.items() if props(s).emit]
    level = {}
    for c, e in srcs:
        if level.get(c, 0) >= e:
            continue
        level[c] = e
        frontier = [c]
        L = e
        while frontier and L > 1:
            L -= 1
            nxt = []
            for (x, y, z) in frontier:
                for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                    n = (x + dx, y + dy, z + dz)
                    if level.get(n, 0) >= L or props(rp.get(*n)).opaque:
                        continue
                    level[n] = L
                    nxt.append(n)
            frontier = nxt
    return sorted((c, level[c]) for c in ice if level.get(c, 0) > MELT_ABOVE), max(level.get(c, 0) for c in ice)


def spawn_blocks(rp, token, only=None):
    names = set(jload("data/spawn_blocks.json")["blocks"])
    allowed = set()
    for w in jload("data/spawn_block_policy.json")["whitelist"]:
        scope = (w.get("scope") or "") + " " + (w.get("why") or "")
        if token in scope:
            allowed |= set(w["blocks"])
    bad = {}
    for c, s in rp.w.items():
        if only and rp.src[c] not in only:
            continue
        b = parse_state(s)[0]
        if b in names and b not in allowed:
            bad.setdefault(b, c)
    return sorted(bad.items())


def outside(rp, box3, only=None):
    """Commands whose box leaves (x0, y0, z0, x1, y1, z1); None bounds are open."""
    out = []
    for fn, kind, b, block in rp.cmds:
        if only and fn not in only:
            continue
        for i in range(3):
            lo, hi = box3[i], box3[i + 3]
            if (lo is not None and b[i] < lo) or (hi is not None and b[i + 3] > hi):
                out.append((fn, b, block))
                break
    return out


# ------------------------------------------------------------------------------------------------ the player


def ncol(n):
    """(x, z) of a node: ("s", x, z, S) stands on a surface, ("w", x, y, z) swims in a water cell."""
    return (n[1], n[2]) if n[0] == "s" else (n[1], n[3])


class Nav:
    """Stand and swim nodes over a box of the replayed world, with every move a player can make between them."""

    def __init__(self, rp, box, swim=True, wade_only=False):
        self.rp, self.swim, self.wade_only = rp, swim, wade_only
        x0, y0, z0, x1, y1, z1 = box
        self.box = box
        ny, nz, nx = y1 - y0 + 1, z1 - z0 + 1, x1 - x0 + 1
        self.top = np.zeros((ny, nz, nx), np.float32)
        self.wat = np.zeros((ny, nz, nx), bool)
        for zi in range(nz):
            for xi in range(nx):
                x, z = x0 + xi, z0 + zi
                for yi in range(ny):
                    p = props(rp.get(x, y0 + yi, z))
                    self.top[yi, zi, xi] = p.top
                    self.wat[yi, zi, xi] = p.water
        self.stands = {}
        self.water = {}
        for zi in range(nz):
            for xi in range(nx):
                x, z = x0 + xi, z0 + zi
                st = []
                for yi in range(ny - 3):
                    t = self.top[yi, zi, xi]
                    if t > 0:
                        S = y0 + yi + float(t)
                        if self.free(x, z, S, S + PLAYER_H) and not (wade_only and self.submerged(x, z, S)):
                            st.append(S)
                self.stands[(x, z)] = st
                self.water[(x, z)] = [y0 + yi for yi in range(ny) if self.wat[yi, zi, xi] and self.top[yi, zi, xi] == 0]
        self.nodes, self.adj = self._graph()

    def _i(self, x, y, z):
        x0, y0, z0, x1, y1, z1 = self.box
        if not (x0 <= x <= x1 and z0 <= z <= z1 and y0 <= y <= y1):
            return None
        return y - y0, z - z0, x - x0

    def free(self, x, z, a, b):
        for yy in range(int(math.floor(a)) - 1, int(math.ceil(b)) + 1):
            i = self._i(x, yy, z)
            if i is None:
                continue
            t = self.top[i]
            if t > 0 and yy < b - 1e-6 and yy + t > a + 1e-6:
                return False
        return True

    def is_water(self, x, y, z):
        i = self._i(x, y, z)
        return bool(self.wat[i]) if i is not None else False

    def submerged(self, x, z, S):
        return self.is_water(x, int(math.floor(S + 1.62)), z)

    def _graph(self):
        nodes = []
        for (x, z), st in self.stands.items():
            nodes += [("s", x, z, S) for S in st]
        if self.swim:
            for (x, z), ws in self.water.items():
                nodes += [("w", x, y, z) for y in ws]
        adj = {n: [] for n in nodes}
        for n in nodes:
            adj[n] = list(self._moves(n))
        return nodes, adj

    def _moves(self, n):
        D4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
        if n[0] == "s":
            _k, x, z, S = n
            for dx, dz in D4:
                c = (x + dx, z + dz)
                for S2 in self.stands.get(c, ()):
                    if S2 - S > JUMP + 1e-6:
                        continue
                    if S - S2 > FALL and not self.is_water(c[0], int(math.floor(S2)), c[1]):
                        continue
                    if not self.free(c[0], c[1], S2, max(S, S2) + PLAYER_H):
                        continue
                    if S2 > S and not self.free(x, z, S, S2 + PLAYER_H):
                        continue
                    yield ("s", c[0], c[1], S2)
                if self.swim:
                    below = [y for y in self.water.get(c, ()) if y < S + 1 and self.free(c[0], c[1], y, max(S, y) + PLAYER_H)]
                    if below:
                        yield ("w", c[0], max(below), c[1])
            if self.swim:
                fy = int(math.floor(S + 1e-6))
                if fy in self.water.get((x, z), ()):
                    yield ("w", x, fy, z)
        else:
            _k, x, y, z = n
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                if y + dy in self.water.get((x + dx, z + dz), ()) and (x + dx, z + dz) in self.water:
                    yield ("w", x + dx, y + dy, z + dz)
            for dx, dz in D4 + ((0, 0),):
                c = (x + dx, z + dz)
                for S2 in self.stands.get(c, ()):
                    if S2 <= y + CLIMB_OUT + 1e-6 and self.free(c[0], c[1], S2, S2 + PLAYER_H) \
                            and self.free(x, z, y, max(y + 1, S2 + PLAYER_H)):
                        yield ("s", c[0], c[1], S2)

    def reach(self, sources):
        seen = set(s for s in sources if s in self.adj)
        stack = list(seen)
        while stack:
            n = stack.pop()
            for m in self.adj[n]:
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        return seen

    def back(self, sources):
        """Every node from which some source is reachable."""
        radj = {}
        for n, ms in self.adj.items():
            for m in ms:
                radj.setdefault(m, []).append(n)
        seen = set(s for s in sources if s in self.adj)
        stack = list(seen)
        while stack:
            n = stack.pop()
            for m in radj.get(n, ()):
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        return seen

    def rim(self, pred=None, width=1):
        x0, _y0, z0, x1, _y1, z1 = self.box
        out = []
        for n in self.nodes:
            if n[0] != "s":
                continue
            x, z = n[1], n[2]
            if (x - x0 < width or x1 - x < width or z - z0 < width or z1 - z < width) and (pred is None or pred(x, z)):
                out.append(n)
        return out


def swim_distances(rp, box, targets):
    """{target name: blocks} of the shortest 26-neighbour swim through passable water from any breathing cell (water
    with an open cell above it) to any cell of each target set, inside `box`."""
    x0, y0, z0, x1, y1, z1 = box
    water = set()
    for y in range(y0, y1 + 1):
        for z in range(z0, z1 + 1):
            for x in range(x0, x1 + 1):
                p = props(rp.get(x, y, z))
                if p.water and p.top == 0:
                    water.add((x, y, z))
    breath = [c for c in water if (c[0], c[1] + 1, c[2]) not in water and props(rp.get(c[0], c[1] + 1, c[2])).top == 0]
    steps = [(dx, dy, dz, math.sqrt(dx * dx + dy * dy + dz * dz))
             for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1) if dx or dy or dz]
    dist = {c: 0.0 for c in breath}
    pq = [(0.0, c) for c in breath]
    heapq.heapify(pq)
    while pq:
        d, c = heapq.heappop(pq)
        if d > dist.get(c, 1e18):
            continue
        x, y, z = c
        for dx, dy, dz, w in steps:
            n = (x + dx, y + dy, z + dz)
            if n not in water:
                continue
            if (dx and dy) or (dx and dz) or (dy and dz):          # no corner cutting through rock
                if any((x + a, y + b, z + e) not in water for a in {0, dx} for b in {0, dy} for e in {0, dz}):
                    continue
            nd = d + w
            if nd < dist.get(n, 1e18):
                dist[n] = nd
                heapq.heappush(pq, (nd, n))
    out = {}
    for name, cells in targets.items():
        ds = [dist[c] for c in cells if c in dist]
        out[name] = round(min(ds), 1) if ds else None
    return out, breath


# ------------------------------------------------------------------------------------------------ the places


class Result:
    def __init__(self, place):
        self.place = place
        self.problems = []      # (check, message)
        self.measured = {}

    def add(self, check, msg):
        self.problems.append((check, msg))

    def checks(self):
        return sorted({c for c, _m in self.problems})


def _common(res, rp, token, bounds, only=None, ice=False):
    for kind, msg in rp.problems:
        res.add(kind, msg)
    leaks = containment(rp, only)
    res.measured["leaks"] = len(leaks)
    pockets = [c for c, s in rp.w.items() if (not only or rp.src[c] in only) and props(s).open
               and rp.base.state(*c) == "base:water"]
    res.measured["water_cells_made_open"] = len(pockets)
    for c in sorted(pockets)[:6]:
        res.add("pocket", "the build opens %s, a cell the painted water fills (%s): the water there drains or a pocket "
                          "is left under it" % (c, rp.get(*c)))
    for wc, oc in leaks[:12]:
        res.add("containment", "water at %s flows into %s (%s next to %s)" % (wc, oc, rp.get(*wc), rp.get(*oc)))
    if bounds is not None:
        out = outside(rp, bounds, only)
        res.measured["outside_bounds"] = len(out)
        for fn, b, block in out[:6]:
            res.add("bounds", "%s writes %s over %s, outside the declared box %s" % (fn, block[:40], b, bounds))
    for b, c in spawn_blocks(rp, token, only):
        res.add("spawn", "%s at %s is a spawn condition (data/spawn_blocks.json) with no whitelist entry scoped to %s"
                % (b, c, token))
    if ice:
        hot, top = light_at_ice(rp, only)
        res.measured["ice_over_light"] = len(hot)
        res.measured["brightest_plain_ice"] = top
        for c, L in hot[:8]:
            res.add("light", "plain ice at %s has block light %d (melts above %d, ASSUMED vanilla rule)" % (c, L, MELT_ABOVE))


def _wbox(rp, only=None, pad=2):
    cs = [c for c in rp.w if not only or rp.src[c] in only]
    xs, ys, zs = [c[0] for c in cs], [c[1] for c in cs], [c[2] for c in cs]
    return min(xs) - pad, min(ys) - pad, min(zs) - pad, max(xs) + pad, max(ys) + pad, max(zs) + pad


def node_pos(n):
    """The player's position (feet) at a node: standing on a surface, or swimming in a water cell's middle."""
    return (n[1] + 0.5, n[3], n[2] + 0.5) if n[0] == "s" else (n[1] + 0.5, n[2] + 0.5, n[3] + 0.5)


def _wake(res, rp, anchor, trigger, sea, swim=True, wade_only=False, starts=None):
    """Nearest reachable-and-returnable player position to a resident's wake point, against its trigger radius."""
    ax, ay, az = anchor
    R = int(trigger) * 2
    box = (ax - R, sea - 8, az - R, ax + R, ay + 8, az + R)
    nav = Nav(rp, box, swim=swim, wade_only=wade_only)
    src = starts(nav) if starts else [n for n in nav.nodes if ncol(n)[0] in (box[0], box[3]) or ncol(n)[1] in (box[2], box[5])]
    ok = nav.reach(src) & nav.back(src)
    point = (ax + 0.5, ay, az + 0.5)
    best = min(((math.dist(node_pos(n), point), n) for n in ok), default=(None, None))
    res.measured["wake_nearest"] = [None if best[0] is None else round(best[0], 1), best[1], trigger]
    if best[0] is None or best[0] > trigger:
        res.add("wake", "no position a player can walk, climb or swim to and leave is within the wake trigger %d of %s: "
                        "the nearest is %s blocks, at %s" % (trigger, tuple(point), best[0] and round(best[0], 1),
                                                               best[1] and tuple(round(v, 1) for v in node_pos(best[1]))))


def _quarry_shell(res, rp, g, doc, bounds):
    """The record's construction claim (geometry.margin_why): every cell within `margin` (any axis, a cube) of a
    flooded cell past the portal is rock THE PACK WROTE, except the top `keep_natural_top` blocks of a column, which it
    never writes. The heightmap cannot show a cave; this proves the shell that guards against one was written."""
    G = doc["geometry"]
    m, keep, px = int(G["margin"]), int(G["keep_natural_top"]), int(G["road"]["portal_x"])
    x0, y0, z0, x1, _y1, z1 = bounds
    y1 = G["floor_y"] + max(G["hall"]["height"], G["road"]["height"]) + m + 1
    ny, nz, nx = y1 - y0 + 1, z1 - z0 + 1, x1 - x0 + 1
    wet = np.zeros((ny, nz, nx), bool)
    rock = np.zeros((ny, nz, nx), bool)
    for (x, y, z), s in rp.w.items():
        if x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1:
            p = props(s)
            if p.water:
                wet[y - y0, z - z0, x - x0] = True
            elif p.top >= 1.0:
                rock[y - y0, z - z0, x - x0] = True
    core = wet.copy()
    core[:, :, :max(0, px + 1 - x0)] = False
    need = core.copy()
    for axis in range(3):
        acc = need.copy()
        for k in range(1, m + 1):
            sl_a, sl_b = [slice(None)] * 3, [slice(None)] * 3
            sl_a[axis], sl_b[axis] = slice(k, None), slice(None, -k)
            acc[tuple(sl_a)] |= need[tuple(sl_b)]
            acc[tuple(sl_b)] |= need[tuple(sl_a)]
        need = acc
    Gd = g.box(x0, z0, x1, z1)
    Y = np.arange(y0, y1 + 1)[:, None, None]
    natural_top = Y > (Gd[None] - keep)
    bad = need & ~wet & ~rock & ~natural_top
    res.measured["shell_cells_required"] = int((need & ~wet & ~natural_top).sum())
    res.measured["shell_cells_missing"] = int(bad.sum())
    for yi, zi, xi in list(zip(*np.nonzero(bad)))[:6]:
        c = (int(xi) + x0, int(yi) + y0, int(zi) + z0)
        res.add("shell", "%s is within %d of a flooded cell past the portal and the pack wrote no rock there (%s)"
                % (c, m, rp.get(*c)))


def audit_quarry(g, base, pack, steps):
    res = Result("drowned_quarry")
    doc = jload("data/drowned_quarry.json")
    G = doc["geometry"]
    m, fl = G["margin"], G["floor_y"]
    rd, hall, pit = G["road"], G["hall"], G["pit"]
    hw = rd["half_width"]
    pts = rd["points"]
    xs = [p[0] for p in pts] + list(hall["x"]) + [pit["centre"][0] - pit["radius"], pit["centre"][0] + pit["radius"]]
    zs = [p[1] for p in pts] + list(hall["z"]) + [pit["centre"][1] - pit["radius"], pit["centre"][1] + pit["radius"]]
    bounds = (min(xs) - hw - m, fl - pit["depth"] - m, min(zs) - hw - m, max(xs) + hw + m, None, max(zs) + hw + m)
    base.prime(bounds[0] - 4, bounds[2] - 4, bounds[3] + 4, bounds[5] + 4)
    rp = Replay(base)
    rp.run_steps(steps, pack)
    _common(res, rp, "drowned_quarry", bounds)
    lake = max(base.col(x, z)[1] or -999 for x in range(bounds[0], bounds[0] + 40) for z in range(pts[0][1] - 3, pts[0][1] + 4))
    box = (bounds[0] - 2, bounds[1], bounds[2] - 2, bounds[3] + 2, lake + 1, bounds[5] + 2)
    px = rd["portal_x"]
    z0 = pts[0][1]
    zl = pts[-1][1]
    targets = {
        "portal": [(px, y, z) for y in range(fl + 1, fl + rd["height"] + 1) for z in range(z0 - hw, z0 + hw + 1)],
        "hall_door": [(hall["x"][0], y, z) for y in range(fl + 1, fl + rd["height"] + 1) for z in range(zl - hw, zl + hw + 1)],
        "sump": [tuple(int(math.floor(v)) for v in doc["monster"]["spot"])],
    }
    sx, sy_, sz = doc["monster"]["spot"]
    tr = doc["monster"]["trigger_radius"]
    targets["wake"] = [(x, y, z) for x in range(int(sx) - tr, int(sx) + tr + 1) for z in range(int(sz) - tr, int(sz) + tr + 1)
                       for y in range(int(sy_) - tr, int(sy_) + tr + 1)
                       if math.dist((x + 0.5, y + 0.5, z + 0.5), (sx, sy_, sz)) <= tr]
    _quarry_shell(res, rp, g, doc, bounds)
    d, breath = swim_distances(rp, box, targets)
    res.measured["swim_blocks"] = d
    res.measured["builder_relayed"] = {"portal": 24, "hall_door": 137, "sump": 180}
    inside = [c for c in breath if c[0] > px and c[1] <= fl + hall["height"]]
    res.measured["breathing_cells_past_portal"] = len(inside)
    for c in inside[:5]:
        res.add("swim", "a breathing cell (water under an open cell) inside the working at %s: there is air to rest in" % (c,))
    surf = surf_air()
    for name in targets:
        if d[name] is None:
            res.add("swim", "the %s is not reachable by swimming from any breathing cell" % name)
    if None not in d.values():
        t = {k: v / SPRINT_SWIM for k, v in d.items()}
        res.measured["swim_seconds"] = {k: round(v, 1) for k, v in t.items()}
        if not 2 * t["portal"] < AIR_NO_MOUNT:
            res.add("swim", "no mount cannot touch the portal and return: %.1f s there and back > %.0f s" % (2 * t["portal"], AIR_NO_MOUNT))
        if not t["hall_door"] > AIR_NO_MOUNT:
            res.add("swim", "no mount reaches the hall door one way in %.1f s, inside %.0f s of air: the gate is open"
                    % (t["hall_door"], AIR_NO_MOUNT))
        if not 2 * t["hall_door"] <= surf:
            res.add("swim", "Surf cannot reach the hall door and return: %.1f s > %.0f s" % (2 * t["hall_door"], surf))
        if not 2 * t["sump"] > surf:
            res.add("swim", "Surf reaches the sump and returns in %.1f s inside %.0f s: Dive is not the gate" % (2 * t["sump"], surf))
    return res, rp


def audit_fungal(g, base, pack, steps):
    res = Result("fungal_isle")
    doc = jload("data/fungal_isle.json")
    gl = [x for x in doc["glades"] if x["id"] == "glowcap_hollow"][0]
    cx, cz = gl["centre"]
    R = gl["radius"]
    rim = gl["pieces"]["bowl"]["rim_radius"]
    yc = g(cx, cz)
    roi = (cx - R - 8, yc - 40, cz - R - 8, cx + R + 8, yc + 60, cz + R + 8)
    base.prime(roi[0] - 2, roi[2] - 2, roi[3] + 2, roi[5] + 2)
    rp = Replay(base, roi)
    rp.run_steps(steps, pack)
    only = {"fungal_isle/glowcap_hollow"}
    bounds = (cx - R, None, cz - R, cx + R, None, cz + R)
    _common(res, rp, "fungal_isle", bounds, only)
    others = [c for c in rp.w if rp.src[c] not in only and math.hypot(c[0] - cx, c[2] - cz) <= rim + 2]
    res.measured["other_functions_inside_the_bowl"] = len(others)
    pool = [c for c, s in rp.w.items() if rp.src[c] in only and props(s).water]
    res.measured["pool_water"] = len(pool)
    if not pool:
        res.add("reach", "the hollow writes no water")
        return res, rp
    leaks_all = containment(rp)
    near = [l for l in leaks_all if math.hypot(l[0][0] - cx, l[0][2] - cz) <= R and l not in containment(rp, only)]
    for wc, oc in near[:6]:
        res.add("containment", "another function opens the pool: water %s into %s" % (wc, oc))
    wb = _wbox(rp, only, pad=4)
    box = (cx - R - 3, min(c[1] for c in pool) - 3, cz - R - 3, cx + R + 3, wb[4], cz + R + 3)
    nav = Nav(rp, box)
    out_src = nav.rim()
    fwd = nav.reach(out_src)
    bk = nav.back(out_src)
    pool_cols = {(c[0], c[2]) for c in pool}
    edge = [n for n in nav.nodes if n[0] == "s" and (n[1], n[2]) not in pool_cols and any(
        (n[1] + a, n[2] + b) in pool_cols for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    res.measured["pool_edge_reachable"] = sum(1 for n in edge if n in fwd and n in bk)
    if not any(n in fwd and n in bk for n in edge):
        res.add("reach", "no place beside the pool is reachable from outside the glade and back")
    must = [n for n in nav.nodes if math.hypot(ncol(n)[0] - cx, ncol(n)[1] - cz) <= rim and
            (n in fwd or (n[0] == "w" and ncol(n) in pool_cols) or n in edge)]
    trapped = [n for n in must if n not in bk]
    res.measured["bowl_nodes"] = len(must)
    res.measured["bowl_trapped"] = len(trapped)
    for n in trapped[:8]:
        res.add("reach", "a player at %s inside the bowl cannot get back out of the glade" % (n,))
    return res, rp


def audit_lodge(g, base, pack, steps):
    res = Result("ice_lodge")
    doc = jload("data/ice_lodge.json")
    b0 = doc["site"]["bounds"]
    hold = doc["site"]["hold"]
    base.prime(hold[0] - 6, hold[1] - 6, hold[2] + 6, hold[3] + 6)
    rp = Replay(base)
    rp.run_steps(steps, pack)
    _common(res, rp, "ice_lodge", (b0[0], None, b0[1], b0[2], None, b0[3]), ice=True)
    sy = doc["tarn"]["surface_y"]
    box = (hold[0], sy - 8, hold[1], hold[2], sy + 14, hold[3])
    nav = Nav(rp, box)
    src = nav.rim(width=2)
    fwd = nav.reach(src)
    bk = nav.back(src)
    ok = fwd & bk

    def at(x, z):
        return [n for n in nav.nodes if n[0] == "s" and n[1] == x and n[2] == z]

    want = {"the keeper's floor %s" % doc["keeper"]["at"]: [tuple(doc["keeper"]["at"])]}
    for w in doc["walks"]["list"]:
        x0, z0, x1, z1 = w["box"]
        want["walk %s" % w["id"]] = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    for s in doc["stations"]:
        want["station %s stool side" % s["id"]] = [(s["hole"][0] + a, s["hole"][1] + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    n = doc["shelter"]["size"] // 2
    for s in doc["shelters"]:
        cx, cz = s["c"]
        want["inside %s" % s["id"]] = [(cx + a, cz + b) for a in range(-n + 1, n) for b in range(-n + 1, n) if (a, b) != (0, 0)]
    for name, cols in want.items():
        if not any(m in ok for c in cols for m in at(*c)):
            res.add("reach", "%s: no cell of it is reachable from the cirque and back" % name)
    # a boardwalk is walkable along ALL of it, not at one end
    sy1 = sy + 1
    for w in doc["walks"]["list"]:
        x0, z0, x1, z1 = w["box"]
        miss = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if ("s", x, z, float(sy1)) not in ok]
        for c in miss[:3]:
            res.add("reach", "walk %s: the plank at %s is not a surface a player reaches from the cirque and back" % (w["id"], c))
    # every water cell a player can fall into through a hole or the Lead must lead back out
    holes = [tuple(s["hole"]) for s in doc["stations"]] + [tuple(s["c"]) for s in doc["shelters"]]
    lx0, lz0, lx1, lz1 = doc["lead"]["box"]
    holes += [(x, z) for x in range(lx0, lx1 + 1) for z in range(lz0, lz1 + 1)]
    wet = [m for m in nav.nodes if m[0] == "w" and (m[1], m[3]) in set(holes)]
    stuck = [m for m in wet if m not in bk]
    res.measured["hole_and_lead_water"] = len(wet)
    res.measured["hole_water_trapped"] = len(stuck)
    for m in stuck[:6]:
        res.add("reach", "a player in the water at %s (a hole or the Lead) cannot climb back out" % ((m[1], m[2], m[3]),))
    trapped = [m for m in fwd if m not in bk]
    res.measured["trapped"] = len(trapped)
    for m in trapped[:6]:
        res.add("reach", "reachable and not returnable: %s" % (m,))
    return res, rp


def audit_rookery(g, base, pack, steps):
    res = Result("rookery")
    doc = jload("data/rookery.json")
    r = doc["residents"][0]
    bb = r["bbox"]
    cx, cz = r["site"]["centre"]
    sk = doc["skerries"]
    base.prime(bb[0] - 6, bb[1] - 6, bb[2] + 6, bb[3] + 6)
    rp = Replay(base)
    rp.run_steps(steps, pack)
    _common(res, rp, "rookery", (bb[0], None, bb[1], bb[2], None, bb[3]))
    sea = base.col(cx, cz)[1]
    # the skerries: where the record puts them; each must be a rock a swimmer can climb onto and leave
    climbable = {}
    for k in range(int(sk["count"])):
        bear = math.radians(sk["first_bearing"] + sk["step_deg"] * k)
        sx, sz = cx + int(round(sk["ring_radius"] * math.sin(bear))), cz - int(round(sk["ring_radius"] * math.cos(bear)))
        rr = int(math.ceil(sk["radius"])) + 9
        box = (sx - rr, sea - 6, sz - rr, sx + rr, sea + int(sk["top_over_sea"]) + 6, sz + rr)
        nav = Nav(rp, box)
        src = [m for m in nav.nodes if m[0] == "w" and m[2] == sea and
               (m[1] in (box[0], box[3]) or m[3] in (box[2], box[5]))]
        fwd, bk = nav.reach(src), nav.back(src)
        rock = [m for m in nav.nodes if m[0] == "s" and m[3] > sea + 1 and parse_state(rp.get(m[1], int(m[3]) - 1, m[2]))[0] != "minecraft:hay_block"
                and (m[1], int(m[3]) - 1, m[2]) in rp.w]
        top = max((m[3] for m in rock if m in fwd and m in bk), default=None)
        res.measured["skerry%d_highest_stand" % k] = top
        if top is None:
            res.add("reach", "skerry %d near (%d, %d): no rock a swimmer can climb onto and leave" % (k, sx, sz))
        climbable[k] = [(m[1], m[2]) for m in nav.nodes if m[0] == "s" and m in fwd and m in bk and (m[1], int(m[3]) - 1, m[2]) in rp.w]
    # the Gullmother: her keeper wakes her for a player within `trigger` of the anchor (resident_encounters' hold,
    # `@a[x=..,y=..,z=..,distance=..trigger]`, the player's feet). Can a swimmer or climber get that close?
    pk = r["pokemon"]
    _wake(res, rp, pk["anchor"], pk["trigger"], sea, swim=True)
    # the swim from the shore, on the surface: fatigue by data/blackout.json `surface`
    sf = jload("data/blackout.json")["surface"]
    W = 260
    x0, z0, x1, z1 = bb[0] - W, bb[1] - W, bb[2] + W, bb[3] + W
    base.prime(x0, z0, x1, z1)
    tpb = 20.0 / SPRINT_SWIM
    written_cols = {(c[0], c[2]) for c in rp.w}

    def depth(x, z):
        gy, L = base.col(x, z)
        return 0 if L is None else L - gy

    goal = set()
    for k, cols in climbable.items():
        for (x, z) in cols:
            for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + a, z + b) not in written_cols and depth(x + a, z + b) >= 1:
                    goal.add((x + a, z + b))
    dist = {}
    pq = []
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if (x, z) not in written_cols and depth(x, z) == 1:
                dist[(x, z)] = 0.0
                pq.append((0.0, (x, z)))
    heapq.heapify(pq)
    best = None
    while pq:
        d, c = heapq.heappop(pq)
        if d > dist.get(c, 1e18):
            continue
        if c in goal:
            best = (d, c)
            break
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                n = (c[0] + a, c[1] + b)
                if (a or b) and x0 <= n[0] <= x1 and z0 <= n[1] <= z1 and n not in written_cols and depth(*n) >= 2:
                    rate = sf["gain_deep_per_tick"] if depth(*n) >= sf["deep_water_blocks"] else sf["gain_shallow_per_tick"]
                    nd = d + math.hypot(a, b) * tpb * rate
                    if nd < dist.get(n, 1e18):
                        dist[n] = nd
                        heapq.heappush(pq, (nd, n))
    if best is None:
        res.add("fatigue", "no skerry is reachable by a surface swim from wading water within %d blocks" % W)
    else:
        res.measured["shore_swim_fatigue_ticks"] = round(best[0])
        res.measured["shore_swim_reaches"] = best[1]
        if best[0] >= sf["collapse_ticks"]:
            res.add("fatigue", "the shortest swim from wading water to a climbable skerry builds %d fatigue ticks, at or "
                               "over the first hit (%d): not a short swim for an untrained player" % (best[0], sf["collapse_ticks"]))
    return res, rp


def audit_hummock(g, base, pack, steps):
    res = Result("hummock_mere")
    doc = jload("data/hummock_mere.json")
    r = doc["residents"][0]
    bb, wb = r["bbox"], doc["waysign"]["bbox"]
    base.prime(bb[0] - 8, bb[1] - 8, bb[2] + 12, bb[3] + 8)
    base.prime(wb[0] - 2, wb[1] - 2, wb[2] + 2, wb[3] + 2)
    rp = Replay(base)
    rp.run_steps(steps, pack)
    main = {"hummock_mere/hummock_mere/build"} | {k for k in {src for src in rp.src.values()} if k.endswith("hummock_mere/build")}
    _common(res, rp, "hummock_mere", (bb[0], None, bb[1], bb[2], None, bb[3]), only=main)
    _wsr = Result("w")
    _common(_wsr, rp, "hummock_mere", (wb[0], None, wb[1], wb[2], None, wb[3]),
            only={k for k in set(rp.src.values()) if k.endswith("hummock_waysign/build")})
    for c, m in _wsr.problems:
        res.add(c, "the waysign: " + m)
    cx, cz = r["site"]["centre"]
    L = r["site"]["water_level"]
    box = (bb[0] - 4, L - 5, bb[1] - 4, bb[2] + 10, L + 14, bb[3] + 4)
    nav = Nav(rp, box, swim=False, wade_only=True)
    spit = nav.rim(pred=lambda x, z: base.col(x, z)[1] is None, width=2)
    res.measured["spit_starts"] = len(spit)
    fwd, bk = nav.reach(spit), nav.back(spit)
    mound = [n for n in nav.nodes if n[0] == "s" and math.hypot(n[1] - cx, n[2] - cz) <= 2.5 and n[3] > L + 1]
    res.measured["mound_crest_nodes"] = len(mound)
    if not any(n in fwd and n in bk for n in mound):
        res.add("reach", "the Hummock's crest (within 2.5 of (%d, %d)) is not reachable by wading from the dry spit and back"
                % (cx, cz))
    trapped = [n for n in fwd if n not in bk]
    res.measured["trapped"] = len(trapped)
    for n in trapped[:6]:
        res.add("reach", "reachable by wading and not returnable: %s" % (n,))
    pk = r["pokemon"]
    ax, ay, az = pk["anchor"]
    best = min(((math.dist(node_pos(n), (ax + 0.5, ay, az + 0.5)), n) for n in fwd & bk), default=(None, None))
    res.measured["wake_nearest"] = [None if best[0] is None else round(best[0], 1), best[1], pk["trigger"]]
    if best[0] is None or best[0] > pk["trigger"]:
        res.add("wake", "no wading position is within the Hummock's wake trigger %d of %s" % (pk["trigger"], pk["anchor"]))
    return res, rp


AUDITS = {"drowned_quarry": audit_quarry, "fungal_isle": audit_fungal, "ice_lodge": audit_lodge,
          "rookery": audit_rookery, "hummock_mere": audit_hummock}


def audit(place, g=None, base=None, pack=None, steps=None, check=True):
    """Result for one place: generate (unless a pack and steps are given), replay, check."""
    import ground as G
    g = g or G.load()
    base = base or Base(g)
    if pack is None:
        tmp = Path(tempfile.mkdtemp(prefix="npwa_"))
        try:
            steps, pack = generate(place, tmp / place, g, check=check)
            return AUDITS[place](g, base, pack, steps)[0]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return AUDITS[place](g, base, pack, steps)[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--place", choices=PLACES, action="append")
    ap.add_argument("--json", help="write every measurement and problem here")
    a = ap.parse_args(argv)
    import ground as G
    g = G.load()
    base = Base(g)
    out, bad = {}, 0
    for p in a.place or PLACES:
        r = audit(p, g, base)
        out[p] = {"problems": r.problems, "measured": r.measured}
        bad += len(r.problems)
        print("%-15s %s  %s" % (p, "PASS" if not r.problems else "FAIL %d" % len(r.problems),
                                json.dumps(r.measured, default=str)[:400]))
        for c, m in r.problems:
            print("  PROBLEM [%s] %s" % (c, m))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
