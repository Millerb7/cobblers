#!/usr/bin/env python
"""The independent land audit of the places and event chains built 2026-10-09: Wardenhold (frostpeak_keep), Crownbreaker
(tri_peaks_nest), the Undertow (buried_dune), the Sundown Watch (sunset_watch), Route 4's thaw road (route4_events) and
Route 5's Bellwether (route5_events); Gull Rock (rookery) only for its resident's clock and level.

It reads what the game would read: the GENERATED functions (each generator run in-process into memory, or an already
built pack directory) replayed over the canonical heightmap (tools/ground.py, rounded), and the data records the runtime
reads (data/scenes.json, quests.json, dialogue.json, progression.json, rewards.json, spawns.json, habitat_blocks.json).
It never calls a builder's checker, siting helper, measurement, sightline or walk; every number a builder reported is
RELAYED here (RELAYED below, with its source) and recomputed with this file's own code. Where they disagree the
measurement is reported and the relayed figure is not used.

Checks (group: codes)
  ground     G1-G6   claimed ground and pad heights against the heightmap; claimed distances to routes, towns, places
  sightline  S1-S2   Wardenhold's spire from Highwire's ten street points (own rays); Crownbreaker's tooth from Highwire
  walks      W1      every walk a design promises, reachable AND returnable for a player (0.6 x 1.8: one column; step
                     or jump up 1 with headroom, fall at most 3, ladders climbable; water is not walked)
  residents  R1-R3   each named Pokemon's generated level against the RCT cap ladder (tools/legendaries_audit.rct_caps,
                     computed from data/trainers.json and the RCT config), the catch gate each design claims, respawn ticks
  chains     E1-E6   every flag a scene, conversation or quest reads is declared in data/progression.json; transitions
                     and reward ids resolve; every reward item is in a jar; counter value against markets income_basis;
                     no progression item
  city       C1      Route 4's walked line against the Displaced City (STATE "at least 250" vs ROUTE4_EVENTS "14.1")
  bounds     B1-B7   every write in a chunk force-loaded when it runs; inside the record's declared box; palette and
                     spawn-condition blocks; Wardenhold emits no light; fill volume; nothing in a route's walking space

  python tools/new_places_land_audit.py                       every group; exit 1 on a problem
  python tools/new_places_land_audit.py --only walks,bounds   some groups
  python tools/new_places_land_audit.py --packs build/datapacks   audit built packs instead of generating them

What it does NOT cover (validity is not behaviour, .claude/rules/testing.md): anything in a running server; trees,
snow, donor templates, towns and every other pack's blocks (the world model is the heightmap plus these packs only, so
a walk that passes here can still meet a tree or a wall another pack builds, and the Displaced City's own gate is not in
the model); diagonal moves and sprint-jumps (the walk model is conservative: it can only miss a route, never invent
one); Distant Horizons LODs, fog, render distance; whether a Habitat Block, a scene or a reward actually runs.
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import re
import sys
import tempfile
import zipfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np  # noqa: E402

DATA = ROOT / "data"
UNITS = ("frostpeak_keep", "tri_peaks_nest", "buried_dune", "sunset_watch", "route4_events", "route5_events")
GROUPS = ("ground", "sightline", "walks", "residents", "chains", "city", "bounds")
JAR_DIR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods")
COBBLEMON_JAR = JAR_DIR / "Cobblemon-fabric-1.8.0+1.21.1.jar"
# the Minecraft 1.21.1 client jar (the tm_gate's source of vanilla ids): vanilla item ids are looked up here
VANILLA_JARS = (Path("C:/Users/wnd/AppData/Roaming/ModrinthApp/meta/versions/1.21.1-0.19.5/1.21.1-0.19.5.jar"),)

# ------------------------------------------------------------------------------------------------ relayed numbers
# Every figure a builder reported, with where it was reported. Nothing below is used as an expectation for a world
# property; each is compared with this file's own measurement and a mismatch is a problem.
RELAYED = {
    "frostpeak_keep": {"source": "docs/world-building/FROSTPEAK_KEEP.md", "centre": (1548, 636), "pad": 127,
                       "top": 198, "streets": (757, 815), "base_rect": (1520, 612, 1576, 660)},
    "tri_peaks_nest": {"source": "docs/world-building/TRI_PEAKS_NEST.md", "anchor": (1478, 254, 1062), "ground": 253,
                       "tip": (1474, 263, 1053), "town_to_tip": 416, "town_to_crown": 416, "route_point": 406,
                       "habitat": ("ursaluna_den_outskirts_ward", 363)},
    "buried_dune": {"source": "docs/world-building/UNDERTOW_BASIN.md, data/buried_dune.json measured",
                    "centre": (7282, 5592), "ground": 99, "route_point": 1299},
    "sunset_watch": {"source": "docs/world-building/SUNSET_WATCH.md", "centre": (1072, 7492), "pad": 137,
                     "terrace": (1054, 7481, 1085, 7503), "terrace_ground": (134, 137), "landing": (2575, 6899),
                     "landing_to_centre": 1616, "waymark": (2576, 6916), "waymark_ground": 63,
                     "dusk_tower": ((1156, 7216), 288.5), "clear_radius": 150},
    "route4_events": {"source": "docs/world-building/ROUTE4_EVENTS.md",
                      "sites": {"headwall_camp": ((2500, 1278), 162, 18, 1089),
                                "steam_hollow": ((3110, 1500), 107, 39, 1903),
                                "strayed_load": ((3262, 1450), 115, 104, None)},
                      "gate_off_line": 235, "city_centre": (3366, 1755), "city_centre_off_line": 14.1},
    "route5_events": {"source": "docs/world-building/ROUTE5_EVENTS.md",
                      # scene: (road-to-person or prop, relayed distance(s)), nearest seat
                      "sites": {"route5_empty_fold": (16, 151), "route5_cairn_bells": ((48, 59), 77),
                                "route5_lee_hut": (35, 65), "route5_winter_fold": (42, 155)}},
    "route_value": {"source": "orchestrator brief, ROUTE5_EVENTS.md / ROUTE4_EVENTS.md Economy",
                    "route5_events": (1500, 2400), "route4_events": (0, 0)},
    "city": {"source": "docs/STATE.md 'Leg 4 waypoint' (at least 250) vs ROUTE4_EVENTS.md (14.1)",
             "state_min": 250, "route4_doc": 14.1},
    "respawn": {"source": "orchestrator brief", "rookery": 144000, "tri_peaks_nest": 72000, "buried_dune": 72000},
}

# Highwire's ten street points (FROSTPEAK_KEEP.md: the belvedere and a 3 x 3 grid on gym3_town's footprint)
STREETS = [(1700, 1382)] + [(x, z) for z in (1386, 1410, 1434) for x in (1664, 1688, 1712)]
EYE = 1.62
SEA = json.loads((DATA / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]


def jload(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class Problem(str):
    pass


# ================================================================================================ the packs
def _read_dir(d):
    return {p.relative_to(d).as_posix(): p.read_text(encoding="utf-8") for p in Path(d).rglob("*") if p.is_file()}


def generate(unit, g):
    """{pack-relative path: text}: the unit's generator run in-process, the bytes its pack would hold. A test that
    mutates a generator patches the module before this runs; nothing here reads a builder's checker."""
    if unit == "frostpeak_keep":
        import frostpeak_keep as M
        files, _ = M.build(g)
        return {k: ("\n".join(v) + "\n" if isinstance(v, list) else json.dumps(v)) for k, v in files.items()}
    if unit == "tri_peaks_nest":
        import tri_peaks_nest as M
        return dict(M.files(M.load(), g))
    if unit in ("buried_dune", "rookery", "sunset_watch"):
        M = __import__(unit)
        w, _ = M.files(M.load(), g)
        return dict(w)
    if unit in ("route4_events", "route5_events"):
        M = __import__(unit)
        sites = M.build(g, M.Road4(), M.load_spec()) if unit == "route4_events" else M.build(g, M.Road5())
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "pack"
            M.write_pack(sites, out=out)
            return _read_dir(out)
    raise KeyError(unit)


def built(unit, packs_dir):
    d = Path(packs_dir) / ("cobblers_" + unit)
    if not d.is_dir():
        raise SystemExit("%s: no built pack at %s" % (unit, d))
    return _read_dir(d)


def run_order(unit, files):
    """The functions the re-application step runs, in order (tools/reapply.py R9FK/R9TP/R9BD/R9SW/R12R4/R12R5)."""
    base = "data/cobblers/function/%s/" % unit
    if unit in ("route4_events", "route5_events"):
        names = [n for n in files[base + "index.txt"].split() if n]
        return [base + n + ".mcfunction" for n in names]
    if unit == "tri_peaks_nest":
        return [base + "crownbreaker/dress.mcfunction"]
    return [base + "build.mcfunction"]


def step_holds(unit, g):
    """Boxes the re-application step force-loads around its function (tools/reapply.py runs exactly this list)."""
    if unit in ("route4_events", "route5_events"):
        return []                       # R12R4/R12R5 hold nothing: each function force-loads its own box
    M = __import__(unit)
    steps = M.placement_steps() if unit == "frostpeak_keep" else M.placement_steps(None, g)
    out = []
    for kind, v in steps:
        if kind == "cmd" and v.startswith("forceload add "):
            out.append(tuple(int(t) for t in v.split()[2:6]))
    return out


# ================================================================================================ blocks
AIR, GROUND, WATER = "minecraft:air", "#ground", "minecraft:water"
PASS, SOLID, TALL, LADDER, FLUID = "pass", "solid", "tall", "ladder", "fluid"
NOCOLLIDE = {
    "air", "cave_air", "void_air", "light", "short_grass", "tall_grass", "fern", "large_fern", "dead_bush", "pink_petals",
    "vine", "glow_lichen", "tripwire", "tripwire_hook", "lever", "rail", "powered_rail", "detector_rail", "activator_rail",
    "redstone_wire", "sweet_berry_bush", "cobweb", "string", "sugar_cane", "torch", "wall_torch", "soul_torch",
    "soul_wall_torch", "redstone_torch", "redstone_wall_torch", "structure_void", "hanging_roots", "spore_blossom",
    "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet", "red_tulip", "orange_tulip", "white_tulip", "pink_tulip",
    "oxeye_daisy", "cornflower", "lily_of_the_valley", "wither_rose", "torchflower", "sunflower", "lilac", "rose_bush",
    "peony", "pitcher_plant", "wheat", "carrots", "potatoes", "beetroots", "seagrass", "tall_seagrass", "nether_sprouts",
    "crimson_roots", "warped_roots", "moss_carpet", "brown_mushroom", "red_mushroom"}
NOCOLLIDE_SUFFIX = ("_sign", "_banner", "_carpet", "_button", "_pressure_plate", "_sapling", "_fence_gate", "_coral_fan")
REPLACEABLE = {"air", "cave_air", "void_air", "water", "lava", "short_grass", "tall_grass", "fern", "large_fern", "dead_bush",
               "snow", "vine", "glow_lichen", "light", "seagrass", "tall_seagrass", "hanging_roots", "fire", "structure_void",
               "crimson_roots", "warped_roots", "nether_sprouts", "bubble_column"}
TAGS = {
    "#minecraft:logs": lambda b: b.endswith(("_log", "_wood", "_stem", "_hyphae")),
    "#minecraft:leaves": lambda b: b.endswith("_leaves"),
    "#minecraft:saplings": lambda b: b.endswith("_sapling") or b in ("azalea", "flowering_azalea", "mangrove_propagule"),
    "#minecraft:flowers": lambda b: b in NOCOLLIDE and b not in ("air", "short_grass", "tall_grass", "fern", "large_fern",
                                                                 "dead_bush", "vine", "light") or b.endswith("_leaves") and b.startswith(("cherry", "flowering")),
    "#minecraft:replaceable": lambda b: b in REPLACEABLE,
}
LIGHT_EMITTERS = ("lantern", "torch", "glowstone", "sea_lantern", "shroomlight", "jack_o_lantern", "light", "end_rod",
                  "beacon", "magma_block", "lava", "glow_lichen", "froglight", "conduit", "respawn_anchor", "crying_obsidian",
                  "amethyst_cluster", "redstone_lamp", "candle", "campfire")


def bid(state):
    s = state.split("[")[0].split("{")[0].strip()
    return s if ":" in s or s.startswith("#") else "minecraft:" + s


def props(state):
    m = re.match(r"^[^\[{]*\[([^\]]*)\]", state)
    return dict(kv.split("=", 1) for kv in m.group(1).split(",") if "=" in kv) if m else {}


def short(b):
    return b.split(":", 1)[1] if b.startswith("minecraft:") else b


@functools.lru_cache(maxsize=None)
def kind(state):
    if state == GROUND:
        return SOLID
    b = bid(state)
    if not b.startswith("minecraft:"):
        return SOLID
    s = short(b)
    if s in ("water", "lava", "bubble_column"):
        return FLUID
    if s in ("ladder", "scaffolding"):
        return LADDER
    if s == "snow":
        return PASS if int(props(state).get("layers", "1")) <= 5 else SOLID
    if s in NOCOLLIDE or s.endswith(NOCOLLIDE_SUFFIX):
        return PASS
    if s.endswith("_door") and s != "iron_door" or s.endswith("_trapdoor") and s != "iron_trapdoor":
        return PASS                 # a player opens it
    if s.endswith("_fence") or s.endswith("_wall"):
        return TALL                 # 1.5 high: neither stepped onto nor jumped over
    return SOLID


def emits_light(state):
    s = short(bid(state))
    if s in ("campfire", "soul_campfire") or s.endswith("candle") or s == "redstone_lamp":
        return props(state).get("lit", "true" if "campfire" in s else "false") == "true"
    return any(s == e or s.endswith("_" + e) or s.startswith(e) for e in LIGHT_EMITTERS if e not in ("campfire", "candle",
                                                                                                    "redstone_lamp"))


# ================================================================================================ the world model
class World:
    """The heightmap (rounded) as solid ground, the sea above sub-sea ground, and every block our commands write."""

    def __init__(self, g):
        self.g = g
        self.o = {}
        self.cols = {}
        self._gy = {}
        self._ys = {}

    def gy(self, x, z):
        k = (x, z)
        v = self._gy.get(k)
        if v is None:
            v = self._gy[k] = int(self.g(x, z))
        return v

    def base(self, x, y, z):
        gy = self.gy(x, z)
        if y <= gy:
            return GROUND
        if y <= SEA:
            return WATER
        return AIR

    def get(self, x, y, z):
        v = self.o.get((x, y, z))
        return v if v is not None else self.base(x, y, z)

    def put(self, x, y, z, s):
        self.o[(x, y, z)] = s
        self.cols.setdefault((x, z), set()).add(y)
        self._ys.pop((x, z), None)

    # --- the player
    def k(self, x, y, z):
        return kind(self.get(x, y, z))

    def passable(self, x, y, z):
        return self.k(x, y, z) in (PASS, LADDER)

    def standable(self, x, y, z):
        if not (self.passable(x, y, z) and self.passable(x, y + 1, z)):
            return False
        return self.k(x, y - 1, z) == SOLID or self.k(x, y, z) == LADDER

    def stand_ys(self, x, z):
        """Feet heights a player can stand at in this column (cached: call only once every write is in)."""
        k = (x, z)
        v = self._ys.get(k)
        if v is not None:
            return v
        gy = self.gy(x, z)
        ys = self.cols.get(k)
        if not ys:
            v = (gy + 1,) if gy + 1 > SEA and self.standable(x, gy + 1, z) else ()
        else:
            lo, hi = min(min(ys), gy) - 1, max(max(ys), gy) + 3
            v = tuple(y for y in range(lo, hi + 1) if self.standable(x, y, z))
        self._ys[k] = v
        return v

    def legal(self, ax, ay, az, bx, by, bz):
        d = by - ay
        if d == 1:
            return self.passable(ax, ay + 2, az)
        if d == 0:
            return True
        if -3 <= d < 0:
            return all(self.passable(bx, y, bz) for y in range(by, ay + 2))
        return False

    def succ(self, s, box):
        x, y, z = s
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (box[0] <= nx <= box[2] and box[1] <= nz <= box[3]):
                continue
            for ny in self.stand_ys(nx, nz):
                if y - 3 <= ny <= y + 1 and self.legal(x, y, z, nx, ny, nz):
                    yield (nx, ny, nz)
        if self.k(x, y, z) == LADDER and self.standable(x, y + 1, z) and self.passable(x, y + 2, z):
            yield (x, y + 1, z)
        if self.k(x, y - 1, z) == LADDER:
            yield (x, y - 1, z)

    def pred(self, s, box):
        x, y, z = s
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (box[0] <= nx <= box[2] and box[1] <= nz <= box[3]):
                continue
            for ny in self.stand_ys(nx, nz):
                if y - 1 <= ny <= y + 3 and self.legal(nx, ny, nz, x, y, z):
                    yield (nx, ny, nz)
        if self.k(x, y - 1, z) == LADDER and self.standable(x, y - 1, z) and self.passable(x, y + 1, z):
            yield (x, y - 1, z)
        if self.k(x, y, z) == LADDER and self.standable(x, y + 1, z):
            yield (x, y + 1, z)

    def bfs(self, starts, box, back=False):
        step = self.pred if back else self.succ
        seen = set(starts)
        q = deque(starts)
        while q:
            s = q.popleft()
            for n in step(s, box):
                if n not in seen:
                    seen.add(n)
                    q.append(n)
        return seen


FILL_RE = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (.+)$")
SET_RE = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (.+)$")
FL_RE = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+))?$")
WRITERS = re.compile(r"^(clone|place|fill|setblock)\b|\brun (clone|place|fill|setblock)\b")


def split_state(rest):
    """'<state> [mode [filter]]' -> (state, mode, filter). A state with NBT keeps everything."""
    if "{" in rest:
        return rest, "replace", None
    t = rest.split()
    st = t[0]
    mode = t[1] if len(t) > 1 else "replace"
    flt = t[2] if len(t) > 2 else None
    return st, mode, flt


def chunks(x0, z0, x1, z1):
    return {(cx, cz) for cx in range(min(x0, x1) >> 4, (max(x0, x1) >> 4) + 1)
            for cz in range(min(z0, z1) >> 4, (max(z0, z1) >> 4) + 1)}


def matcher(flt):
    if flt is None:
        return None
    if flt.startswith("#"):
        f = TAGS.get(flt)
        if f is None:
            raise ValueError("unknown tag filter %s" % flt)
        return lambda st: st != GROUND and f(short(bid(st)))
    want = bid(flt)
    return lambda st: st != GROUND and bid(st) == want


class Replay:
    """Every block command of a unit's functions replayed in run order over a World."""

    def __init__(self, unit, files, world, holds):
        self.unit, self.world = unit, world
        self.volumes = []               # (fn, line, x0, y0, z0, x1, y1, z1, state) of every write command
        self.states = set()             # every state a command may place
        self.unloaded, self.unparsed, self.too_big = [], [], []
        for fn in run_order(unit, files):
            loaded = set()
            for h in holds:
                loaded |= chunks(*h)
            for n, raw in enumerate(files[fn].splitlines(), 1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                m = FL_RE.match(line)
                if m:
                    a = [int(v) for v in m.groups()[1:] if v is not None]
                    c = chunks(a[0], a[1], a[2], a[3]) if len(a) == 4 else chunks(a[0], a[1], a[0], a[1])
                    loaded = (loaded | c) if m.group(1) == "add" else (loaded - c)
                    continue
                m = SET_RE.match(line)
                if m:
                    x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    rest = m.group(4)
                    mode = "replace"
                    if "{" not in rest and rest.split()[-1] in ("replace", "keep", "destroy") and len(rest.split()) > 1:
                        rest, mode = rest.rsplit(" ", 1)
                    self._write(fn, n, loaded, x, y, z, x, y, z, rest, mode, None)
                    continue
                m = FILL_RE.match(line)
                if m:
                    c = [int(v) for v in m.groups()[:6]]
                    st, mode, flt = split_state(m.group(7))
                    self._write(fn, n, loaded, *c, st, mode, flt)
                    continue
                if WRITERS.search(line) or "~" in line.split(" run ")[-1] and line.startswith(("setblock", "fill")):
                    self.unparsed.append("%s:%d %s" % (fn, n, line[:120]))

    def _write(self, fn, n, loaded, x0, y0, z0, x1, y1, z1, st, mode, flt):
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        z0, z1 = min(z0, z1), max(z0, z1)
        w = self.world
        if ":" not in st.split("[")[0].split("{")[0]:
            st = "minecraft:" + st          # 'air' and 'minecraft:air' are the same block
        self.volumes.append((fn, n, x0, y0, z0, x1, y1, z1, st))
        self.states.add(st)
        vol = (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1)
        if vol > 32768:
            self.too_big.append("%s:%d fills %d blocks (the limit is 32768)" % (fn, n, vol))
        if not chunks(x0, z0, x1, z1) <= loaded:
            self.unloaded.append("%s:%d writes x%d..%d z%d..%d outside every force-loaded chunk" % (fn, n, x0, x1, z0, z1))
        test = matcher(flt) if mode == "replace" else None
        if mode == "keep":
            test = lambda s: kind(s) != SOLID and bid(s) in (AIR, "minecraft:cave_air")  # noqa: E731
        if test is not None and not any(test(s) for s in (AIR, WATER)):
            # the base world (air, water, ground) never matches: only blocks we wrote can be replaced
            for x in range(x0, x1 + 1):
                for z in range(z0, z1 + 1):
                    for y in sorted(w.cols.get((x, z), ())):
                        if y0 <= y <= y1 and test(w.o[(x, y, z)]):
                            w.put(x, y, z, st)
            return
        hollow = mode in ("hollow", "outline")
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                for y in range(y0, y1 + 1):
                    edge = x in (x0, x1) or y in (y0, y1) or z in (z0, z1)
                    if hollow and not edge:
                        if mode == "hollow":
                            w.put(x, y, z, AIR)
                        continue
                    if test is None or test(w.get(x, y, z)):
                        w.put(x, y, z, st)


# ================================================================================================ the run
class Audit:
    def __init__(self, g=None, packs=None, units=UNITS):
        if g is None:
            import ground as G
            g = G.load()
        self.g = g
        self.packs = packs
        self.units = units
        self.problems = []
        self.notes = []
        self._replay = {}

    def files(self, unit):
        return built(unit, self.packs) if self.packs else generate(unit, self.g)

    def replay(self, unit):
        r = self._replay.get(unit)
        if r is None:
            files = self.files(unit)
            r = Replay(unit, files, World(self.g), step_holds(unit, self.g))
            r.files = files
            self._replay[unit] = r
        return r

    def bad(self, code, unit, msg):
        self.problems.append(Problem("%s %s: %s" % (code, unit, msg)))

    def note(self, code, unit, msg):
        self.notes.append("%s %s: %s" % (code, unit, msg))

    def run(self, groups=GROUPS):
        for grp in groups:
            getattr(self, "check_" + grp)()
        return self.problems


# ------------------------------------------------------------------------------------------------ geometry helpers
def paths():
    return {k: [tuple(p) for p in v] for k, v in jload("route_paths.json")["paths"].items()}


def walked(path):
    d, acc = [0.0], 0.0
    for a, b in zip(path, path[1:]):
        acc += math.hypot(b[0] - a[0], b[1] - a[1])
        d.append(acc)
    return d


def nearest(points, x, z):
    best = min(range(len(points)), key=lambda i: (points[i][0] - x) ** 2 + (points[i][1] - z) ** 2)
    return best, math.hypot(points[best][0] - x, points[best][1] - z)


def nearest_any(x, z):
    out = (None, None, 1e18)
    for k, v in paths().items():
        i, d = nearest(v, x, z)
        if d < out[2]:
            out = (k, v[i], d)
    return out


def in_poly(x, z, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, z1 = ring[i]
        x2, z2 = ring[(i + 1) % n]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            inside = not inside
    return inside


def subregion(sid):
    for s in jload("regions.json")["subregions"]:
        if s["id"] == sid:
            return s
    raise KeyError(sid)


def towns():
    return {t["id"]: t for t in jload("towns.json")["towns"]}


def box_dist(x, z, b):
    dx = max(b[0] - x, 0, x - b[2])
    dz = max(b[1] - z, 0, z - b[3])
    return math.hypot(dx, dz)


def close(measured, relayed, tol=0.5):
    return abs(measured - relayed) <= tol


# ------------------------------------------------------------------------------------------------ rays
def ray(g, eye, tgt, step=0.5):
    """(clear, margin): the straight segment from eye to tgt against the top surface (round(h) + 1) of every ground
    column it crosses, the eye's own column skipped. margin = the least height of the segment over that surface."""
    ex, ey, ez = eye
    tx, ty, tz = tgt
    dist = math.hypot(tx - ex, tz - ez)
    n = max(2, int(dist / step))
    t = np.arange(1, n) / n
    px, pz, py = ex + (tx - ex) * t, ez + (tz - ez) * t, ey + (ty - ey) * t
    ix, iz = np.floor(px).astype(int), np.floor(pz).astype(int)
    keep = ~((ix == math.floor(ex)) & (iz == math.floor(ez))) & ~((ix == math.floor(tx)) & (iz == math.floor(tz)))
    top = np.round(g.heights[iz - g.oz, ix - g.ox]).astype(float) + 1.0
    m = (py - top)[keep]
    margin = float(m.min()) if m.size else float("inf")
    return margin > 0, margin


def eye_at(g, x, z):
    return (x + 0.5, int(g(x, z)) + 1 + EYE, z + 0.5)


# ================================================================================================ ground
def _check_ground(self):
    g = self.g
    P = paths()
    T = towns()
    if "frostpeak_keep" in self.units:
        R = RELAYED["frostpeak_keep"]
        x0, z0, x1, z1 = R["base_rect"]
        top = int(g.box(x0, z0, x1, z1).max())
        if top != R["pad"]:
            self.bad("G1", "frostpeak_keep", "the highest ground under the base rectangle is y%d; the relayed pad is y%d" % (top, R["pad"]))
        r = self.replay("frostpeak_keep")
        w = r.world
        hall = [b for b in jload("habitat_blocks.json")["blocks"] if b["id"] == "frostpeak_keep_hall_ward"][0]["position"]
        hx, hy, hz = hall["x"], hall["y"], hall["z"]
        if w.k(hx, hy, hz) != SOLID or not w.standable(hx, hy + 1, hz):
            self.bad("G1", "frostpeak_keep", "the hall's Habitat Block cell (%d, %d, %d) is not a floor block with room to stand "
                     "(is %s, above %s)" % (hx, hy, hz, w.get(hx, hy, hz), w.get(hx, hy + 1, hz)))
        if hy != top:
            self.bad("G1", "frostpeak_keep", "the hall's Habitat Block is at y%d, the courtyard pad (highest ground) is y%d" % (hy, top))
        ymax = max(y for (x, y, z), s in w.o.items() if s != AIR)
        if ymax != R["top"]:
            self.bad("G1", "frostpeak_keep", "the generated keep tops out at y%d; relayed y%d" % (ymax, R["top"]))
        cx, cz = R["centre"]
        ds = [math.hypot(sx - cx, sz - cz) for sx, sz in STREETS]
        if not (close(min(ds), R["streets"][0], 1) and close(max(ds), R["streets"][1], 1)):
            self.bad("G2", "frostpeak_keep", "street distances %.0f-%.0f, relayed %d-%d" % (min(ds), max(ds), *R["streets"]))
        rings = subregion("frostpeak_strand")["polygons"]
        edge = [(x, z0) for x in range(x0, x1 + 1)] + [(x, z1) for x in range(x0, x1 + 1)] + \
               [(x0, z) for z in range(z0, z1 + 1)] + [(x1, z) for z in range(z0, z1 + 1)]
        out = [p for p in edge if not any(in_poly(p[0] + 0.5, p[1] + 0.5, ring) for ring in rings)]
        if out:
            self.bad("G2", "frostpeak_keep", "%d edge columns of the base rectangle lie outside frostpeak_strand, e.g. %s" % (len(out), out[:3]))
        k, pt, d = nearest_any(cx, cz)
        self.note("G2", "frostpeak_keep", "nearest route path point %s on %s, %.0f blocks" % (pt, k, d))
    if "tri_peaks_nest" in self.units:
        R = RELAYED["tri_peaks_nest"]
        ax, ay, az = R["anchor"]
        if g(ax, az) != R["ground"] or g(ax, az) + 1 != ay:
            self.bad("G3", "tri_peaks_nest", "ground at the crown (%d, %d) is y%d; relayed y%d, feet y%d" % (ax, az, g(ax, az), R["ground"], ay))
        r = self.replay("tri_peaks_nest")
        spawn = r.files["data/cobblers/function/tri_peaks_nest/crownbreaker/spawn.mcfunction"]
        m = re.search(r'x:"([\d.]+)",y:(\d+),z:"([\d.]+)"', spawn)
        sx, sy, sz = float(m.group(1)), int(m.group(2)), float(m.group(3))
        if not r.world.standable(int(sx), sy, int(sz)) or int(r.world.gy(int(sx), int(sz))) + 1 != sy:
            self.bad("G3", "tri_peaks_nest", "the generated spawn point (%s, %d, %s) is not feet on the crown's ground" % (sx, sy, sz))
        hx, hz = T["gym3_town"]["centre"]["x"], T["gym3_town"]["centre"]["z"]
        d_crown = math.hypot(ax - hx, az - hz)
        tx, ty, tz = R["tip"]
        d_tip = math.hypot(tx - hx, tz - hz)
        if not close(d_crown, R["town_to_crown"]):
            self.bad("G3", "tri_peaks_nest", "Highwire's centre to the crown is %.1f blocks; data/tri_peaks_nest.json "
                     "measured.town_to_crown_blocks_straight relays %d (that is the tallest tooth's tip, %.1f)" % (d_crown, R["town_to_crown"], d_tip))
        k, pt, d = nearest_any(ax, az)
        if not close(d, R["route_point"]):
            self.bad("G3", "tri_peaks_nest", "nearest route path point %s is %.1f; relayed %d" % (pt, d, R["route_point"]))
        hb = [b for b in jload("habitat_blocks.json")["blocks"] if b["id"] == R["habitat"][0]][0]["position"]
        dh = math.hypot(hb["x"] - ax, hb["z"] - az)
        if not close(dh, R["habitat"][1], 1):
            self.bad("G3", "tri_peaks_nest", "%s is %.1f from the crown; relayed %d" % (R["habitat"][0], dh, R["habitat"][1]))
    if "buried_dune" in self.units:
        R = RELAYED["buried_dune"]
        cx, cz = R["centre"]
        if g(cx, cz) != R["ground"]:
            self.bad("G4", "buried_dune", "ground at the centre is y%d; relayed y%d" % (g(cx, cz), R["ground"]))
        k, pt, d = nearest_any(cx, cz)
        if not close(d, R["route_point"], 1):
            self.bad("G4", "buried_dune", "nearest route path point is %.0f; relayed %d" % (d, R["route_point"]))
        r = self.replay("buried_dune")
        low = sorted({(x, z) for (fn, n, x0, y0, z0, x1, y1, z1, st) in r.volumes for x in (x0, x1) for z in (z0, z1)
                      if r.world.gy(x, z) < 66})
        if low:
            self.bad("G4", "buried_dune", "%d written corner columns stand on ground under y66 (rules.min_ground), e.g. %s" % (len(low), low[:3]))
    if "sunset_watch" in self.units:
        R = RELAYED["sunset_watch"]
        x0, z0, x1, z1 = R["terrace"]
        b = g.box(x0, z0, x1, z1)
        if (int(b.min()), int(b.max())) != R["terrace_ground"] or int(b.max()) != R["pad"]:
            self.bad("G5", "sunset_watch", "terrace ground y%d-%d; relayed y%d-%d, pad y%d" % (b.min(), b.max(), *R["terrace_ground"], R["pad"]))
        w = self.replay("sunset_watch").world
        cx, cz = R["centre"]
        if w.k(cx, R["pad"], cz) != SOLID:
            self.bad("G5", "sunset_watch", "the terrace centre (%d, %d, %d) is not paved: %s" % (cx, R["pad"], cz, w.get(cx, R["pad"], cz)))
        wx, wz = R["waymark"]
        if g(wx, wz) != R["waymark_ground"]:
            self.bad("G5", "sunset_watch", "ground at the waymark is y%d; relayed y%d" % (g(wx, wz), R["waymark_ground"]))
        lx, lz = R["landing"]
        if not close(math.hypot(lx - cx, lz - cz), R["landing_to_centre"], 1):
            self.bad("G5", "sunset_watch", "landing to centre %.0f; relayed %d" % (math.hypot(lx - cx, lz - cz), R["landing_to_centre"]))
        (dx, dz), dd = R["dusk_tower"]
        if not close(math.hypot(dx - cx, dz - cz), dd):
            self.bad("G5", "sunset_watch", "the Dusk tower is %.1f off; relayed %.1f" % (math.hypot(dx - cx, dz - cz), dd))
        k, pt, d = nearest_any(cx, cz)
        near_t = [(tid, round(box_dist(cx, cz, (t["footprint"]["min_x"], t["footprint"]["min_z"], t["footprint"]["max_x"], t["footprint"]["max_z"]))))
                  for tid, t in T.items() if "footprint" in t]
        near_t = [t for t in near_t if t[1] < R["clear_radius"]]
        if d < R["clear_radius"] or near_t:
            self.bad("G5", "sunset_watch", "within %d blocks: route point %.0f, towns %s" % (R["clear_radius"], d, near_t))
    if "route4_events" in self.units:
        R = RELAYED["route4_events"]
        p4 = P["route_04_surge_to_erika"]
        wk = walked(p4)
        for sid, ((x, z), gy, off, wlk) in R["sites"].items():
            i, d = nearest(p4, x, z)
            if g(x, z) != gy:
                self.bad("G6", "route4_events", "%s ground y%d; relayed y%d" % (sid, g(x, z), gy))
            if not close(d, off, 1):
                self.bad("G6", "route4_events", "%s is %.1f off the walked line; relayed %d" % (sid, d, off))
            if wlk is not None and not close(wk[i], wlk, 15):
                self.bad("G6", "route4_events", "%s's nearest cell is at walked %.0f; relayed %d" % (sid, wk[i], wlk))
        gate = jload("route4_events.json")["sites"]["thaw_gate"]["gate"]
        i, d = nearest(p4, *gate)
        if not close(d, R["gate_off_line"], 1):
            self.bad("G6", "route4_events", "the gate (%d, %d) is %.1f off the walked line; relayed %d" % (*gate, d, R["gate_off_line"]))
    if "route5_events" in self.units:
        R = RELAYED["route5_events"]
        p5 = P["route_05_erika_to_koga"]
        sc = {s["id"]: s for s in jload("scenes.json")["scenes"]}
        seats = [t["seat"] for t in jload("late_route_trainers.json")["trainers"]]
        r = self.replay("route5_events")
        for sid, (road, seat) in R["sites"].items():
            s = sc[sid]
            pts = [n["at"] for n in s.get("npcs", [])] or [p["at"] for p in s.get("props", [])]
            ds = sorted(nearest(p5, p[0], p[2])[1] for p in pts)
            want = road if isinstance(road, tuple) else (road, road)
            if not (close(ds[0], want[0], 1) and close(ds[-1], want[1], 1)):
                self.bad("G6", "route5_events", "%s: road to its person or props %.0f-%.0f; relayed %s" % (sid, ds[0], ds[-1], road))
            vols = [v for v in r.volumes if v[0].endswith("/%s.mcfunction" % sid)]
            bx0, bz0 = min(v[2] for v in vols), min(v[4] for v in vols)
            bx1, bz1 = max(v[5] for v in vols), max(v[7] for v in vols)
            c = ((bx0 + bx1) / 2, (bz0 + bz1) / 2)
            ds = min(math.hypot(st[0] - c[0], st[2] - c[1]) for st in seats)
            if not close(ds, seat, 1):
                self.bad("G6", "route5_events", "%s: built box centre to the nearest seat %.0f; relayed %d" % (sid, ds, seat))


# ================================================================================================ sightlines
def keep_features(w, pad):
    """The finial (the highest block), the arcade (iron bars in the beacon chamber band) and the spire's axis column."""
    solid = [(x, y, z) for (x, y, z), s in w.o.items() if s != AIR and y > pad]
    top = max(solid, key=lambda p: p[1])
    arcade = [(x, y, z) for (x, y, z), s in w.o.items() if bid(s) == "minecraft:iron_bars" and pad + 46 <= y <= pad + 55]
    return solid, top, arcade


def silhouette(g, eye, solid, centre):
    """Share of the keep's outline, binned 1 block across the line of sight by 1 block high, whose nearest block has a
    clear ray from the eye. This file's own definition; the builder's 'fraction' is relayed, not reused."""
    ex, _, ez = eye
    dx, dz = centre[0] - ex, centre[1] - ez
    L = math.hypot(dx, dz)
    px, pz = -dz / L, dx / L
    cells = {}
    for (x, y, z) in solid:
        lat = math.floor((x + 0.5 - ex) * px + (z + 0.5 - ez) * pz)
        d = (x + 0.5 - ex) ** 2 + (z + 0.5 - ez) ** 2
        k = (lat, y)
        if k not in cells or d < cells[k][0]:
            cells[k] = (d, (x + 0.5, y + 0.5, z + 0.5))
    vis = sum(1 for _, t in cells.values() if ray(g, eye, t, step=1.0)[0])
    return vis / len(cells)


def _check_sightline(self):
    g = self.g
    if "frostpeak_keep" in self.units:
        R = RELAYED["frostpeak_keep"]
        w = self.replay("frostpeak_keep").world
        pad = int(g.box(*R["base_rect"]).max())
        solid, top, arcade = keep_features(w, pad)
        fin = (top[0] + 0.5, top[1] + 0.5, top[2] + 0.5)
        eyes = [eye_at(g, x, z) for x, z in STREETS]
        fin_ok = [ray(g, e, fin)[0] for e in eyes]
        if not all(fin_ok):
            self.bad("S1", "frostpeak_keep", "the finial %s is hidden from %d of 10 street points: %s" % (
                top, fin_ok.count(False), [STREETS[i] for i, v in enumerate(fin_ok) if not v]))
        if not arcade:
            self.bad("S1", "frostpeak_keep", "no iron-bar arcade in the beacon band y%d-%d" % (pad + 46, pad + 55))
        else:
            arc_ok = [any(ray(g, e, (x + 0.5, y + 0.5, z + 0.5))[0] for x, y, z in arcade) for e in eyes]
            if arc_ok.count(True) < 9:
                self.bad("S1", "frostpeak_keep", "the arcade is seen from %d of 10 street points (claimed at least 9)" % arc_ok.count(True))
        axis = [y for y in range(pad + 1, top[1] + 1) if ray(g, eyes[0], (top[0] + 0.5, y + 0.5, top[2] + 0.5))[0]]
        if len(axis) < 30:
            self.bad("S1", "frostpeak_keep", "%d blocks of the spire's axis are seen from the belvedere (claimed at least 30)" % len(axis))
        sil = [silhouette(g, e, solid, R["centre"]) for e in eyes]
        self.note("S1", "frostpeak_keep", "finial %s seen from %d/10; axis seen %d blocks from the belvedere; silhouette "
                  "(this file's definition) mean %.2f, min %.2f, max %.2f (relayed mean 0.28)" % (
                      top, fin_ok.count(True), len(axis), sum(sil) / len(sil), min(sil), max(sil)))
        self.measured_silhouette = sil
    if "tri_peaks_nest" in self.units:
        R = RELAYED["tri_peaks_nest"]
        w = self.replay("tri_peaks_nest").world
        tip = max(((x, y, z) for (x, y, z), s in w.o.items() if s != AIR and kind(s) == SOLID), key=lambda p: p[1])
        if tip != R["tip"]:
            self.bad("S2", "tri_peaks_nest", "the tallest generated tooth tip is %s; relayed %s" % (tip, R["tip"]))
        t = towns()["gym3_town"]["centre"]
        ok, margin = ray(g, eye_at(g, t["x"], t["z"]), (tip[0] + 0.5, tip[1] + 1.0, tip[2] + 0.5))
        if not ok:
            self.bad("S2", "tri_peaks_nest", "the tooth tip %s is hidden from Highwire's centre (margin %.1f)" % (tip, margin))
        self.note("S2", "tri_peaks_nest", "tip %s from Highwire's centre: clear=%s, margin %.1f (relayed 2.3)" % (tip, ok, margin))


# ================================================================================================ walks
def _start_states(w, x, z, r=6):
    for d in range(r + 1):
        for dx in range(-d, d + 1):
            for dz in (-d, d) if abs(dx) != d else range(-d, d + 1):
                ys = w.stand_ys(x + dx, z + dz)
                if ys:
                    gy = w.gy(x + dx, z + dz)
                    return [(x + dx, min(ys, key=lambda y: abs(y - gy - 1)), z + dz)]
    return []


def walk(w, name, start_xz, targets, margin=40):
    """[(target name, reached, returnable)]. targets: [(name, (x0, y0, z0, x1, y1, z1) feet box, predicate or None)]."""
    st = _start_states(w, *start_xz)
    if not st:
        return [(t[0], False, False, "no dry start near %s" % (start_xz,)) for t in targets]
    xs = [start_xz[0]] + [t[1][0] for t in targets] + [t[1][3] for t in targets]
    zs = [start_xz[1]] + [t[1][2] for t in targets] + [t[1][5] for t in targets]
    box = (min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin)
    fwd = w.bfs(st, box)
    back = w.bfs(st, box, back=True)
    out = []
    for tname, (x0, y0, z0, x1, y1, z1), pred in targets:
        cand = [s for s in fwd if x0 <= s[0] <= x1 and y0 <= s[1] <= y1 and z0 <= s[2] <= z1 and (pred is None or pred(s))]
        ret = [s for s in cand if s in back]
        out.append((tname, bool(cand), bool(ret), "%d cells reached, %d returnable" % (len(cand), len(ret))))
    return out


def near(x, y, z, r, dy=2):
    """Feet within r blocks (horizontal, column centres) of (x, z), and within dy of y."""
    return ((math.floor(x - r), math.floor(y - dy), math.floor(z - r), math.floor(x + r), math.floor(y + dy), math.floor(z + r)),
            lambda s: math.hypot(s[0] + 0.5 - x, s[2] + 0.5 - z) <= r)


def scene_targets(sid):
    s = [x for x in jload("scenes.json")["scenes"] if x["id"] == sid][0]
    t = []
    for n in s.get("npcs", []):
        x, y, z = n["at"]
        b, p = near(x + 0.5, y, z + 0.5, 2.5)
        t.append(("%s npc %s" % (sid, n["conversation"]), b, p))
    for pr in s.get("props", []):
        x, y, z = pr["at"]
        b, p = near(x, y, z, 3.0)
        t.append(("%s prop %s" % (sid, pr["id"]), b, p))
    for a in s.get("actors", []):
        for pl in a["place"]:
            m = s["markers"][pl["marker"]]["at"]
            b, p = near(m[0] + 0.5, m[1], m[2] + 0.5, 3.0)
            t.append(("%s actor %s at %s" % (sid, a["id"], pl["marker"]), b, p))
    for zn in s.get("zones", []):
        f, to = zn["from"], zn["to"]
        t.append(("%s zone %s" % (sid, zn["id"]), (f[0], f[1], f[2], to[0], to[1], to[2]), None))
    return t


def cache_target(rid):
    r = [x for x in jload("rewards.json")["rewards"] if x["id"] == rid][0]
    a, b = r["trigger"]["min"], r["trigger"]["max"]
    return ("cache %s" % rid, (a[0], a[1], a[2], b[0], b[1], b[2]), None)


def walk_plan(unit):
    """[(walk name, start (x, z), [target])]: every walk the unit's design promises."""
    if unit == "frostpeak_keep":
        hb = {b["id"]: b["position"] for b in jload("habitat_blocks.json")["blocks"]}
        h, bcn = hb["frostpeak_keep_hall_ward"], hb["frostpeak_keep_beacon_ward"]
        d = jload("frostpeak_keep.json")["dims"]
        cx, cz = jload("frostpeak_keep.json")["site"]["centre"]
        pad = h["y"]                     # the hall's block is set in the courtyard-level floor (G1 holds it there)
        kx0, kx1 = cx - d["keep_half"], cx + d["keep_half"]
        kz0, kz1 = cz + d["keep_cv"] - d["keep_half"], cz + d["keep_cv"] + d["keep_half"]
        floors = [("the archive (keep floor ry %d)" % d["keep_floors"][0], d["keep_floors"][0]),
                  ("the loft (keep floor ry %d)" % d["keep_floors"][1], d["keep_floors"][1]),
                  ("the roof pocket (ry %d)" % d["keep_roof"], d["keep_roof"])]
        tg = [("the hall (Habitat Block)",) + near(h["x"] + 0.5, h["y"] + 1, h["z"] + 0.5, 2.5)] + \
             [(n, (kx0, pad + ry + 1, kz0, kx1, pad + ry + 1, kz1), None) for n, ry in floors] + \
             [("the beacon chamber, up the ladder (Froslass' block)",) + near(bcn["x"] + 0.5, bcn["y"] + 1, bcn["z"] + 0.5, 4.0, 1)]
        return [("north approach", (cx, cz - 80), tg), ("south hill", (cx, cz + 80), tg),
                ("Highwire's belvedere", STREETS[0], tg[:1])]
    if unit == "tri_peaks_nest":
        x, y, z = RELAYED["tri_peaks_nest"]["anchor"]
        return [("Highwire's gate", (1688, 1412), [("the crown",) + near(x + 0.5, y, z + 0.5, 2.5, 1)])]
    if unit == "buried_dune":
        d = jload("buried_dune.json")
        cx, cz = d["site"]["centre"]
        bed = (cx + 0.5, 85, cz + 0.5)
        trig = d["pokemon"]["trigger"]
        box = (cx - trig, 85 - trig, cz - trig, cx + trig, 85 + trig, cz + trig)
        pred = lambda s: math.dist((s[0] + 0.5, s[1], s[2] + 0.5), bed) <= trig  # noqa: E731
        sea = [t for t in d["trails"] if t["id"] == "sea"][0]["waypoints"][0]
        north = [t for t in d["trails"] if t["id"] == "north"][0]["waypoints"][0]
        tg = [("the bowl's floor, within the wake radius", box, pred)]
        return [("the strand (sea trail's foot)", tuple(sea), tg), ("the north shelf", tuple(north), tg)]
    if unit == "sunset_watch":
        d = jload("sunset_watch.json")
        cx, cz = d["site"]["centre"]
        kx, kz = cx + d["npc"]["at"][0], cz + d["npc"]["at"][1]
        y = RELAYED["sunset_watch"]["pad"] + 1
        tg = [("the keeper",) + near(kx + 0.5, y, kz + 0.5, 2.5), cache_target(d["find"]["reward"]),
              ("the dial plinth",) + near(cx - 4 + 0.5, y, cz + 0.5, 3.0)]
        return [("the approach's east end", (cx + 40, cz), tg), ("the stair run's foot", (cx - 19 - 8, cz), tg)]
    if unit == "route4_events":
        p4 = paths()["route_04_surge_to_erika"]
        out = []
        for sid in ("route4_headwall_camp", "route4_steam_hollow", "route4_summit_road", "route4_thaw_gate"):
            tg = scene_targets(sid)
            if sid == "route4_steam_hollow":
                tg.append(cache_target("r4_strayed_load"))
            # the walk starts on the walked line, at its cell nearest the scene's first target
            b = tg[0][1]
            i, _ = nearest(p4, (b[0] + b[3]) / 2, (b[2] + b[5]) / 2)
            out.append(("%s from the walked line" % sid, p4[i], tg))
        return out
    if unit == "route5_events":
        p5 = paths()["route_05_erika_to_koga"]
        out = []
        for sid in ("route5_empty_fold", "route5_cairn_bells", "route5_lee_hut", "route5_winter_fold"):
            tg = scene_targets(sid)
            if sid == "route5_cairn_bells":
                tg.append(cache_target("r5_shepherds_tin"))
            b = tg[0][1]
            i, _ = nearest(p5, (b[0] + b[3]) / 2, (b[2] + b[5]) / 2)
            out.append(("%s from the road" % sid, p5[i], tg))
        return out
    return []


def _check_walks(self):
    self.walk_results = {}
    for unit in self.units:
        w = self.replay(unit).world
        for name, start, tg in walk_plan(unit):
            res = walk(w, name, start, tg, margin=40 if unit != "frostpeak_keep" or "belvedere" not in name else 60)
            self.walk_results[(unit, name)] = res
            self.note("W1", unit, "from %s %s: %s" % (name, start, "; ".join(
                "%s %s" % (t, "ok" if a and b else ("one-way" if a else "NO")) for t, a, b, _ in res)))
            for tname, reached, ret, why in res:
                if not reached:
                    self.bad("W1", unit, "from %s %s: %s is not reachable (%s)" % (name, start, tname, why))
                elif not ret:
                    self.bad("W1", unit, "from %s %s: %s is reachable but there is no way back (%s)" % (name, start, tname, why))


# ================================================================================================ residents
def caps():
    import legendaries_audit as L
    return L.rct_caps()


def prev_gate(gate):
    n = int(re.match(r"gym(\d)_cleared", gate).group(1))
    return None if n == 1 else "gym%d_cleared" % (n - 1)


def generated_level(files, unit, rid):
    for k, v in files.items():
        if k.endswith("/%s/spawn.mcfunction" % rid):
            m = re.search(r'props:"level=(\d+)', v)
            return int(m.group(1))
    raise KeyError("%s: no generated spawn for %s" % (unit, rid))


def generated_respawn(files, unit):
    for k, v in files.items():
        if k.endswith("/load.mcfunction"):
            m = re.search(r"^scoreboard players set #resp \S+ (\d+)$", v, re.M)
            if m:
                return int(m.group(1))
    raise KeyError("%s: no #resp in a generated load function" % unit)


def _check_residents(self):
    C = caps()
    self.note("R1", "ladder", "RCT caps (tools/legendaries_audit.rct_caps, from data/trainers.json + the RCT config): %s" % C)
    named = []
    if "tri_peaks_nest" in self.units:
        e = jload("tri_peaks_nest.json")["encounters"][0]
        named.append(("tri_peaks_nest", e["id"], e["gate"], self.replay("tri_peaks_nest").files))
    if "buried_dune" in self.units:
        p = jload("buried_dune.json")["pokemon"]
        named.append(("buried_dune", p["id"], p["gate"], self.replay("buried_dune").files))
    for unit, rid, gate, files in named:
        lv = generated_level(files, unit, rid)
        before, at = C[prev_gate(gate)], C[gate]
        if not lv > before:
            self.bad("R1", unit, "%s is L%d, catchable at the cap %d before %s (claimed: not before the gate)" % (rid, lv, before, gate))
        if not lv <= at:
            self.bad("R1", unit, "%s is L%d, over the cap %d %s gives (claimed: catchable at the gate)" % (rid, lv, at, gate))
        want = RELAYED["respawn"][unit]
        got = generated_respawn(files, unit)
        if got != want:
            self.bad("R3", unit, "generated respawn %d ticks; the design says %d" % (got, want))
    # Gull Rock: its clock (two hours) and its level against its own ceiling rule (tier 7's next cap)
    rk = jload("rookery.json")
    files = generate("rookery", self.g) if not self.packs else built("rookery", self.packs)
    got = generated_respawn(files, "rookery")
    if got != RELAYED["respawn"]["rookery"]:
        self.bad("R3", "rookery", "Gull Rock's generated respawn is %d ticks; the design says %d" % (got, RELAYED["respawn"]["rookery"]))
    pk = rk["residents"][0]["pokemon"]
    lv = generated_level(files, "rookery", rk["residents"][0]["id"]) if any(
        k.endswith("/%s/spawn.mcfunction" % rk["residents"][0]["id"]) for k in files) else pk["level"]
    nc = jload("encounter_design.json")["rules"]["hearts"]["next_cap"]["7"]
    if lv > nc:
        self.bad("R1", "rookery", "the Gullmother is L%d over its ceiling %d" % (lv, nc))
    # Habitat residents: levels from the pool data/spawns.json compiles (the runtime pool is compiled from it)
    hab = {h["id"]: h for h in jload("spawns.json")["habitats"]}
    tiers = jload("encounter_design.json")["rules"]["tiers"]
    nxt = jload("encounter_design.json")["rules"]["hearts"]["next_cap"]

    def lv_range(entry):
        a, b = (int(v) for v in str(entry["level"]).split("-"))
        return a, b
    if "frostpeak_keep" in self.units:
        band = tiers["5"]["band"]
        for e in hab["frostpeak_keep_hall"]["entries"]:
            a, b = lv_range(e)
            if a < band[0] or b > band[1]:
                self.bad("R2", "frostpeak_keep", "hall %s %d-%d is outside the Strand's band %s" % (e["pokemon"], a, b, band))
        for e in hab["frostpeak_keep_beacon"]["entries"]:
            a, b = lv_range(e)
            if not (a > band[1] and b < nxt["5"]):
                self.bad("R2", "frostpeak_keep", "beacon %s %d-%d is not above the band %s and under the next cap %d" % (e["pokemon"], a, b, band, nxt["5"]))
            if not b <= C["gym5_cleared"]:
                self.bad("R2", "frostpeak_keep", "beacon %s tops at %d, over the cap after gym 5 (%d)" % (e["pokemon"], b, C["gym5_cleared"]))
    if "sunset_watch" in self.units:
        cap5 = tiers["5"]["cap"]
        if cap5 != C["gym4_cleared"]:
            self.bad("R2", "sunset_watch", "tier 5's cap %d is not the RCT cap after gym 4 (%d)" % (cap5, C["gym4_cleared"]))
        for e in hab["sunset_watch_dusk"]["entries"] + hab["sunset_watch_day"]["entries"]:
            a, b = lv_range(e)
            if e["pokemon"] == "drakloak":
                if (a - cap5, b - cap5) != (5, 8) or not b > nxt["5"]:
                    self.bad("R2", "sunset_watch", "Drakloak %d-%d is not 5-8 over the tier-5 cap %d and above the next %d at its top" % (a, b, cap5, nxt["5"]))
            elif b > cap5:
                self.bad("R2", "sunset_watch", "%s %d-%d tops over the leg's cap %d (claimed catchable on the leg)" % (e["pokemon"], a, b, cap5))


# ================================================================================================ chains
QUESTS = {"route4_events": "evt_route4_thaw_road", "route5_events": "evt_route5_bellwether"}
PROGRESSION_ITEM = re.compile(r"^(tmcraft:tm_|.*:tr_)|(_candy|rare_candy|bottle_cap|ability_capsule|ability_patch|_mint|"
                              r"lucky_egg|key_stone|mega_bracelet|linking_cord|exp_share)|"
                              r"^cobblemon:(fire|water|thunder|leaf|moon|sun|shiny|dusk|dawn|ice)_stone$|^mega_showdown:")


def _walk_values(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key and isinstance(v, str):
                yield v
            yield from _walk_values(v, key)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_values(v, key)


@functools.lru_cache(maxsize=None)
def jar_names(path):
    with zipfile.ZipFile(path) as z:
        return frozenset(z.namelist())


def item_in_jars(item):
    ns, name = item.split(":", 1)
    rel = "assets/%s/models/item/%s.json" % (ns, name)
    jars = list(VANILLA_JARS) if ns == "minecraft" else ([COBBLEMON_JAR] if ns == "cobblemon" else sorted(JAR_DIR.glob("*.jar")))
    jars = [j for j in jars if j.is_file()]
    if not jars:
        return None
    return any(rel in jar_names(str(j)) for j in jars)


def prices():
    m = jload("markets.json")
    P = {}
    for grp in ("counters", "stalls"):
        for c in m[grp]:
            for k in ("stock", "held_stock"):
                for ln in c.get(k) or []:
                    if ln.get("item") and ln.get("price") is not None:
                        u = ln["price"] / max(1, ln.get("count", 1))
                        P[ln["item"]] = min(P.get(ln["item"], 1e18), u)
    return P


def _check_chains(self):
    prog = {f["id"] for f in jload("progression.json")["quest_fields"]}
    quests = {q["id"]: q for q in jload("quests.json")["quests"]}
    convs = jload("dialogue.json")["conversations"]
    scenes = jload("scenes.json")["scenes"]
    rewards = {r["id"]: r for r in jload("rewards.json")["rewards"]}
    P = prices()
    bank = {b["item"] for b in jload("bank.json")["buys"]}
    income = jload("markets.json")["income_basis"]["leg_by_badge"]
    items = {}
    for unit, qid in QUESTS.items():
        if unit not in self.units:
            continue
        q = quests.get(qid)
        if q is None:
            self.bad("E1", unit, "quest %s is not in data/quests.json" % qid)
            continue
        recs = [q] + [c for c in convs if c.get("quest_id") == qid] + [s for s in scenes if s.get("quest_id") == qid]
        refs = set()
        for r in recs:
            for key in ("field", "progression_field", "claim_field"):
                refs |= set(_walk_values(r, key))
        local = set()
        for t in q.get("transitions", []):
            for c in t.get("when", []) if isinstance(t.get("when"), list) else []:
                local.add(c.lstrip("!").split("=")[0])
            for d in t.get("do", []) if isinstance(t.get("do"), list) else []:
                if d.startswith("set:"):
                    local.add(d[4:].split("=")[0])
        for o in q.get("objectives", []):
            for key in ("active", "complete"):
                if isinstance(o.get(key), str):
                    local.add(o[key].lstrip("!"))
        refs |= {"quest.%s.%s" % (qid, f) for f in local if f}
        self.note("E1", unit, "%d flag references over %d records (quest, conversations, scenes)" % (len(refs), len(recs)))
        missing = sorted(f for f in refs if f.startswith("quest.") and f not in prog)
        if missing:
            self.bad("E1", unit, "%d flag(s) read or set but not declared in data/progression.json: %s" % (len(missing), missing[:8]))
        tnames = {t["id"] for t in q.get("transitions", [])}
        used = set(_walk_values(recs[1:], "transition"))
        for s in recs:
            for z in s.get("zones", []) if isinstance(s.get("zones"), list) else []:
                used |= set(z.get("transitions", []))
        if used - tnames:
            self.bad("E2", unit, "transitions named but not in %s: %s" % (qid, sorted(used - tnames)))
        rnames = {r["id"] for r in q.get("rewards", [])} if isinstance(q.get("rewards"), list) else set((q.get("rewards") or {}).keys())
        granted = set(_walk_values(q, "reward"))
        if granted - rnames:
            self.bad("E2", unit, "rewards granted but not defined on %s: %s" % (qid, sorted(granted - rnames)))
        bundles = []
        qr = q.get("rewards")
        for r in (qr if isinstance(qr, list) else [dict(v, id=k) for k, v in (qr or {}).items()]):
            cont = [(c["item"], c["count"]) if isinstance(c, dict) else (c[0], c[1]) for c in r.get("contents", [])]
            bundles.append((r["id"], cont))
        items[unit] = bundles
    caches = {"route4_events": ["r4_strayed_load"], "route5_events": ["r5_shepherds_tin"], "sunset_watch": ["sunset_watch_lamp_store"]}
    for unit, ids in caches.items():
        if unit not in self.units:
            continue
        for rid in ids:
            if rid not in rewards:
                self.bad("E2", unit, "cache %s is not in data/rewards.json" % rid)
                continue
            items.setdefault(unit, []).append((rid, [(c["item"], c["count"]) for c in rewards[rid]["contents"]]))
    for unit, bundles in items.items():
        for rid, cont in bundles:
            for it, n in cont:
                ok = item_in_jars(it)
                if ok is False:
                    self.bad("E3", unit, "%s gives %s, which no jar's item models carry" % (rid, it))
                elif ok is None:
                    self.note("E3", unit, "%s: %s not checked (its jar is not on this machine)" % (rid, it))
                if PROGRESSION_ITEM.search(it):
                    self.bad("E5", unit, "%s gives %s, a progression item, with no gate" % (rid, it))
                if it in bank:
                    self.bad("E4", unit, "%s gives %s, which the Bank buys: an income source" % (rid, it))
    # value: counter prices of what a player can take, the least and the most a single player gets
    self.chain_value = {}
    for unit, leg in (("route5_events", "5"), ("route4_events", "4")):
        if unit not in items:
            continue
        val = {rid: sum(P.get(it, 0) * n for it, n in cont) for rid, cont in items[unit]}
        unpriced = sorted({it for _, cont in items[unit] for it, _ in cont if it not in P})
        if unit == "route5_events":
            lo = val["reward_oil"] + val["reward_plain"] + val["r5_shepherds_tin"]
            hi = val["reward_salve"] + val["reward_full"] + val["r5_shepherds_tin"]
        else:
            lo = hi = sum(val.values())
        cash = sum(1 for _, cont in items[unit] for it, _ in cont if it in bank or it.startswith("cobbledollars:"))
        self.chain_value[unit] = (lo, hi, income[leg], unpriced, cash)
        rl = RELAYED["route_value"][unit]
        self.note("E4", unit, "counter value %d-%d against leg %s's trainer income %d (%.1f%%-%.1f%%); not on any counter: "
                  "%s; items that convert to money: %d" % (lo, hi, leg, income[leg], 100.0 * lo / income[leg],
                                                           100.0 * hi / income[leg], unpriced, cash))
        # the two relayed figures are in different units: Route 5's is counter value, Route 4's is cash (money made)
        got = (round(lo), round(hi)) if rl[1] else (cash, cash)
        if got != rl:
            self.bad("E4", unit, "%s of the chain's rewards is %d-%d; relayed %d-%d" % (
                "counter value" if rl[1] else "cash", got[0], got[1], *rl))


# ================================================================================================ the Displaced City
def _check_city(self):
    if "route4_events" not in self.units:
        return
    p4 = paths()["route_04_surge_to_erika"]
    dc = towns()["displaced_city"]
    fp = dc["footprint"]
    cav = dc["underground"]["cavern_centre"]
    n = dc["underground"]["cavern_footprint_blocks"][0]
    cbox = (cav["x"] - n // 2, cav["z"] - n // 2, cav["x"] - n // 2 + n - 1, cav["z"] - n // 2 + n - 1)
    town_box = (fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"])
    d_town_c = nearest(p4, dc["centre"]["x"], dc["centre"]["z"])[1]
    d_town_box = min(box_dist(x, z, town_box) for x, z in p4)
    d_cav_c = nearest(p4, cav["x"], cav["z"])[1]
    over = sum(1 for x, z in p4 if cbox[0] <= x <= cbox[2] and cbox[1] <= z <= cbox[3])
    rel = RELAYED["route4_events"]["city_centre"]
    d_rel = nearest(p4, *rel)[1]
    self.city = {"town_centre": d_town_c, "town_footprint": d_town_box, "cavern_centre": d_cav_c,
                 "path_cells_over_cavern": over, "route4_doc_point": d_rel}
    self.note("C1", "route4_events", "walked line to: the town's centre (%d, %d) %.1f, its footprint %.1f; the cavern's "
              "centre (%d, %d) %.1f; %d path cells over the cavern box %s; ROUTE4_EVENTS' point %s %.1f" % (
                  dc["centre"]["x"], dc["centre"]["z"], d_town_c, d_town_box, cav["x"], cav["z"], d_cav_c, over, cbox, rel, d_rel))
    if d_town_box < RELAYED["city"]["state_min"]:
        self.bad("C1", "route4_events", "the walked line passes %.0f from the Displaced City's surface footprint; STATE "
                 "says at least %d" % (d_town_box, RELAYED["city"]["state_min"]))
    if d_cav_c < RELAYED["city"]["state_min"]:
        self.bad("C1", "route4_events", "the walked line passes %.1f blocks from the Displaced City cavern's centre (%d, %d) "
                 "and crosses %d cells over its box: STATE's 'at least 250 off the critical path' holds for the surface town "
                 "(%.0f), not for the city underground" % (d_cav_c, cav["x"], cav["z"], over, d_town_box))


# ================================================================================================ bounds
# The whitelist scopes in data/spawn_block_policy.json that name a KIND of place rather than a place (read 2026-10-09).
# Every other entry is a named place, gym, template or tool, and allows its blocks there only; an entry added later is
# read as a named place until it is listed here, so a new general scope fails closed rather than open.
GENERAL_SCOPES = ("overworld placements only", "overworld and the cherry-grove cavern", "service buildings",
                  "gardens and orchards", "foliage objects, gardens and landmark trees", "farm and animal-pen lots")


def _check_bounds(self):
    sb = set(jload("spawn_blocks.json")["blocks"])
    pol = jload("spawn_block_policy.json")["whitelist"]
    route_cells = set()
    for v in paths().values():
        route_cells |= set(v)
    for unit in self.units:
        r = self.replay(unit)
        for m in r.unloaded[:5]:
            self.bad("B1", unit, m)
        if len(r.unloaded) > 5:
            self.bad("B1", unit, "... and %d more writes outside force-loaded chunks" % (len(r.unloaded) - 5))
        for m in r.too_big + r.unparsed:
            self.bad("B6", unit, m)
        rec = jload(unit + ".json") if (DATA / (unit + ".json")).is_file() else {}
        boxes = []
        if unit == "tri_peaks_nest":
            boxes = [tuple(e["build"]["bbox"]) for e in rec["encounters"]]
        if unit == "sunset_watch":
            boxes = [tuple(b["min"]) + tuple(b["max"]) for b in rec["site"]["bounding_boxes"]
                     if b["id"] in ("sunset_watch_all", "sunset_watch_landing_box")]
        if boxes:
            out = [v for v in r.volumes if not any(b[0] <= v[2] and v[5] <= b[2] and b[1] <= v[4] and v[7] <= b[3] for b in boxes)]
            if out:
                self.bad("B2", unit, "%d write(s) outside the record's declared boxes %s, e.g. %s:%d x%d..%d z%d..%d" % (
                    len(out), boxes, out[0][0].rsplit("/", 1)[-1], out[0][1], out[0][2], out[0][5], out[0][4], out[0][7]))
        ids = set(rec.get("blocks", {}).get("ids", [])) if isinstance(rec.get("blocks"), dict) else set()
        placed = {bid(s) for s in r.states}
        self.note("B0", unit, "%d write commands, %d cells set, %d block ids, spawn conditions written: %s; holds %s" % (
            len(r.volumes), len(r.world.o), len(placed), sorted(placed & sb), step_holds(unit, self.g)))
        if ids:
            extra = sorted(placed - ids)
            if extra:
                self.bad("B3", unit, "writes block(s) its record does not declare (blocks.ids): %s" % extra)
        for b in sorted(placed & sb):
            entries = [e for e in pol if b in e["blocks"]]
            mine = [e for e in entries if unit in e.get("scope", "") or "cobblers_" + unit in e.get("scope", "")]
            general = [e for e in entries if e not in mine and e.get("scope", "").startswith(GENERAL_SCOPES)]
            other = [e for e in entries if e not in mine and e not in general]
            if not entries:
                self.bad("B4", unit, "writes %s, a spawn condition (data/spawn_blocks.json) no whitelist entry in "
                         "data/spawn_block_policy.json allows" % b)
            elif not mine and not general:
                self.bad("B4", unit, "writes %s; data/spawn_block_policy.json allows it only for %s" % (
                    b, [e["scope"][:60] for e in other]))
            elif not mine:
                self.note("B4", unit, "%s is allowed by a general scope: %s" % (b, [e["scope"][:70] for e in general]))
        if unit == "frostpeak_keep":
            lit = sorted({s for s in r.states if emits_light(s)})
            if lit:
                self.bad("B5", unit, "the keep is dark by design and writes light: %s" % lit[:5])
        # a flight of stairs is climbed toward its facing (the vanilla model's tall half is on the facing side, read from
        # assets/minecraft/models/block/stairs.json and the blockstate's y rotation): a stair whose next step up lies the
        # other way is set backwards, and every step of it is a jump
        w = r.world
        dirs = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
        back = []
        for (x, y, z), s in w.o.items():
            if not bid(s).endswith("_stairs") or props(s).get("half", "bottom") != "bottom":
                continue
            f = props(s).get("facing")
            for name, (dx, dz) in dirs.items():
                nxt = w.o.get((x + dx, y + 1, z + dz), "")
                if bid(nxt).endswith("_stairs") and props(nxt).get("half", "bottom") == "bottom" and f != name and \
                        f == {"north": "south", "south": "north", "east": "west", "west": "east"}[name]:
                    back.append((x, y, z, f, name))
        if back:
            self.bad("B8", unit, "%d stair(s) face away from the flight they belong to (climbed by jumping), e.g. %s" % (
                len(back), sorted(back)[:3]))
        # nothing solid in a route's walking space (feet and head over the path's ground)
        hits = []
        for (x, y, z), s in w.o.items():
            if (x, z) in route_cells and kind(s) in (SOLID, TALL) and y in (w.gy(x, z) + 1, w.gy(x, z) + 2):
                hits.append((x, y, z, bid(s)))
        if hits:
            self.bad("B7", unit, "%d solid block(s) in a route path's walking space, e.g. %s" % (len(hits), sorted(hits)[:3]))


Audit.check_ground = _check_ground
Audit.check_sightline = _check_sightline
Audit.check_walks = _check_walks
Audit.check_residents = _check_residents
Audit.check_chains = _check_chains
Audit.check_city = _check_city
Audit.check_bounds = _check_bounds


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default=",".join(GROUPS))
    ap.add_argument("--units", default=",".join(UNITS))
    ap.add_argument("--packs", default=None, help="audit built packs in this directory instead of generating them")
    ap.add_argument("--source-root", default=None)
    a = ap.parse_args(argv)
    import ground as G
    au = Audit(G.load(a.source_root), a.packs, tuple(u for u in a.units.split(",") if u))
    probs = au.run(tuple(x for x in a.only.split(",") if x))
    for n in au.notes:
        print("note", n)
    for p in probs:
        print("PROBLEM", p)
    print("new_places_land_audit: %d problem(s) over %s (%s)" % (len(probs), ",".join(au.units), a.only))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
