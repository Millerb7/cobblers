#!/usr/bin/env python
"""An independent audit of the eight gym arenas: the GENERATED functions replayed into a block model of its own.

  python tools/gym_arenas_audit.py [--gym gym2] [--pack build/datapacks/cobblers_gym_arenas] [--json out.json]

WHAT IT READS, AND WHAT IT DOES NOT. tools/gym_arenas.py builds an arena and checks it from the same in-memory
model. This audit shares none of that: it imports nothing from tools/gym_arenas.py and never reads the arena
records' geometry fields (entry, battle, floor_y, seat, parts). It reads, for each gym:

  - the emitted functions, in the order the apply runs them: the building as R16G leaves it
    (build/datapacks/cobblers_gym_buildings/.../<gym>.mcfunction) or, for Misty, the dig R16E leaves
    (cobblers_gym_interiors/.../gym2.mcfunction); then the arena (cobblers_gym_arenas/.../<gym>.mcfunction); then the
    seat move (<gym>_seat.mcfunction, its `execute if|unless block` conditions evaluated against this model, with no
    player near); then the Challenge spawner the trainers cycle sets (data/challenge_mode.json bosses.<id>.spawner.at).
    Every fill mode (replace with a filter, keep, hollow, outline, destroy) and setblock is replayed; any other
    command that would write a block fails closed.
  - the ground from tools/ground.py (the canonical heightmap, rounded), the lot from data/placements.json, the water
    from tools/bridges.py water() (sea, lakes, rivers), all unwritten ground taken as natural rock: a cave could be
    there, which is what a shell is for.
  - where the puzzle route ends from the BUILDING's data (data/gym_buildings/<gym>.json route: the step that ends
    beside the leader's hall spawner; Misty: data/gym_interiors.json gym2 route, the ledger gallery), never the
    arena record's entry.
  - the four Battle Positions blocks and the seat from the emitted blocks themselves; spawnHeightOffset from
    base-pack/cobbleverse/config/cobblemonbattlepositions.json.
  - the leaders' Pokemon from data/trainers.json (every `species` anywhere in the leader's record: team, rct, every
    mode, Challenge included), data/gym_trainers.json's ace and data/challenge_mode.json's boss record; their sizes
    from the server's own archives with zipfile (species `hitbox`, `baseScale`, the species_additions; the bedrock
    model in its bind pose, posed the way com.cobblemon...TexturedModel builds it: read with javap from the 1.8.0
    jar, see model_extent()), never through tools/pokemon_sizes.py or data/gym_arena_sizes.json. The table in
    docs/world-building/GYM_ARENAS.md is read only to compare against.

THE CHECKS, each derived:
  reach      a walk with a player's body (0.6 x 1.8; a step of 0.6 or a stair's half-block front without a jump;
             a jump of 1.25 with the headroom it needs; a fall of at most 3.0, the vanilla damage threshold, or any
             fall into water; swimming and climbing), from the route's end down to the challenger's stand (over the
             player stand block) and back up. A door is passable. Reported also without jumps, and with damaging falls
             when the strict walk fails.
  clearance  around each Pokemon block, no block with a collision shape within R of the block's centre, from the
             Pokemon's feet (block y + spawnHeightOffset) up to feet + H. R = the larger of the hitbox's half-diagonal
             and the bind-pose model's farthest corner, H = the larger of the hitbox height and the model's top, both
             times baseScale, over every member of the leader's team; the challenger's Pokemon is assumed as large
             (an assumption: a player's team is unbounded). MARGIN 0: Battle Positions puts the Pokemon at the
             block's centre (x + 0.5, z + 0.5) with its feet on the floor, and R is already the circle the model
             sweeps turning on the spot; animation is not measurable offline, and a margin guessed for it would be
             a tuned number.
  shell      every cell the arena leaves open (air, fluid, or a block with a partial shape) has six neighbours that
             are WRITTEN (by the arena, the building, the dig or the seat move) or, inside the building's own bounds,
             natural air. An unwritten neighbour at or under the natural top is rock that a cave could replace.
             Every arena write inside its record's `bounds` or a `through_building` box (the two declared fields).
  cover      over each column the arena writes (outside through_building), natural blocks between its highest
             write and the lowest thing above: at least 1 where that is a write or the lot's cut (exact), at least 1
             in the worst case where it is the heightmap, which ground.py says is one block LOW at 0.15% of columns
             (so round(h) - 1 - top >= 1).
  water      the water and lava the model holds, flowed (water 7 out, lava 3, down without limit, never into a door,
             ladder or waterloggable block, which flowing fluid does not enter) from every source: the world's water
             and every written fluid or waterlogged block. Settled world water does not flow into unwritten cells.
             No fluid may reach an arena cell the arena did not write as that fluid.
  hazards    no lava next to a cell a player's body can occupy; no walkable cell on magma; lava that could light a
             flammable block (vanilla LavaFluid.randomTick: a flammable block beside it with air over it, or air
             over the lava) is reported.
  light      block light from every written source, through every cell that is not an opaque full cube; no
             walkable cell inside the arena at block light 0 (vanilla monsters spawn only there since 1.18).

WHAT IT DOES NOT COVER: Battle Positions' search box and rctmod's sight line (the builder's check owns those); the
seat's spawner contract; runtime behavior of anything (that is an experiment in a running server).
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import os
import re
import sys
import zipfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PACKS = ROOT / "build" / "datapacks"
ARENA_PACK = PACKS / "cobblers_gym_arenas"
BUILDING_PACK = PACKS / "cobblers_gym_buildings"
INTERIOR_PACK = PACKS / "cobblers_gym_interiors"
SNAPSHOT = Path(os.environ.get("COBBLERS_SERVER_SNAPSHOT",
                               "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05"))
GYMS = ["gym%d" % i for i in range(1, 9)]
EPS = 1e-6

# the player (net.minecraft.world.entity.EntityType.PLAYER: 0.6 x 1.8), step height 0.6 (Player attribute
# generic.step_height), jump 0.42 initial velocity -> 1.2522 apex, fall damage = ceil(fallDistance - 3)
BODY = 1.8
STEP = 0.6
FACING = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
JUMP = 1.25
SAFE_FALL = 3.0


# =============================================================================================== block states
@functools.lru_cache(maxsize=None)
def parse_state(state):
    """(name, props) of a block state string; NBT dropped; the namespace made explicit."""
    s = state.split("{", 1)[0]
    props = {}
    if "[" in s:
        s, rest = s.split("[", 1)
        for kv in rest.rstrip("]").split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                props[k.strip()] = v.strip()
    if ":" not in s:
        s = "minecraft:" + s
    return s, tuple(sorted(props.items()))


def name_of(state):
    return parse_state(state)[0]


def prop(state, key, default=None):
    return dict(parse_state(state)[1]).get(key, default)


NAT = "natural:rock"          # unwritten ground: rock, or whatever a cave left
NAT_AIR = "minecraft:air"
NAT_WATER = "natural:water"   # the world's own water (sea, lake, river), settled
PAD = "natural:pad"           # the lot prep's fill under the pad, where the ground was lower than the lot

AIRS = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
NOCOLL = AIRS | {
    "minecraft:light", "minecraft:water", "minecraft:lava", NAT_WATER, "minecraft:redstone_wire",
    "minecraft:rail", "minecraft:powered_rail", "minecraft:detector_rail", "minecraft:activator_rail",
    "minecraft:torch", "minecraft:wall_torch", "minecraft:soul_torch", "minecraft:soul_wall_torch",
    "minecraft:redstone_torch", "minecraft:redstone_wall_torch", "minecraft:hanging_roots", "minecraft:cave_vines",
    "minecraft:cave_vines_plant", "minecraft:vine", "minecraft:glow_lichen", "minecraft:short_grass",
    "minecraft:grass", "minecraft:fern", "minecraft:tall_grass", "minecraft:large_fern", "minecraft:dead_bush",
    "minecraft:tripwire", "minecraft:ladder", "minecraft:fire", "minecraft:soul_fire", "minecraft:structure_void",
    "minecraft:sugar_cane", "minecraft:kelp", "minecraft:kelp_plant", "minecraft:seagrass", "minecraft:tall_seagrass",
    "minecraft:sculk_vein", "minecraft:spore_blossom", "minecraft:small_dripleaf", "minecraft:big_dripleaf_stem",
    "minecraft:twisting_vines", "minecraft:twisting_vines_plant", "minecraft:weeping_vines",
    "minecraft:weeping_vines_plant", "minecraft:pink_petals", "minecraft:nether_portal", "minecraft:scaffolding",
    "minecraft:dandelion", "minecraft:poppy", "minecraft:blue_orchid", "minecraft:allium", "minecraft:azure_bluet",
    "minecraft:oxeye_daisy", "minecraft:cornflower", "minecraft:lily_of_the_valley", "minecraft:wither_rose",
    "minecraft:sunflower", "minecraft:lilac", "minecraft:rose_bush", "minecraft:peony", "minecraft:torchflower",
    "minecraft:cobweb", "minecraft:sweet_berry_bush"}
# a door counts as passable (the brief); signs, banners, buttons, plates, saplings, tulips have no collision
NOCOLL_SUFFIX = ("_sign", "_banner", "_button", "_pressure_plate", "_sapling", "_tulip", "_door", "_coral",
                 "_coral_fan", "_mushroom")
CLIMB = {"minecraft:ladder", "minecraft:vine", "minecraft:cave_vines", "minecraft:cave_vines_plant",
         "minecraft:twisting_vines", "minecraft:twisting_vines_plant", "minecraft:weeping_vines",
         "minecraft:weeping_vines_plant", "minecraft:scaffolding"}
# flowing fluid never enters these (FlowingFluid.canHoldFluid: doors, signs, ladders; and a waterloggable block
# takes only a SOURCE, SimpleWaterloggedBlock.placeLiquid checks Fluids.WATER, so flowing water never waterlogs)
FLOW_STOP = {"minecraft:ladder", "minecraft:scaffolding", "minecraft:hanging_roots", "minecraft:glow_lichen",
             "minecraft:sculk_vein", "minecraft:light", "minecraft:rail", "minecraft:powered_rail",
             "minecraft:detector_rail", "minecraft:activator_rail"}
FLOW_STOP_SUFFIX = ("_door", "_sign", "_banner")
WOODS = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry", "bamboo", "pale_oak")
TRANSPARENT_FULL = ("glass", "_leaves", "_grate", "mangrove_roots", "ice", "slime_block", "honey_block", "beacon",
                    "barrier", "azalea", "cauldron", "spawner", "_bars", "lectern", "brewing_stand")


@functools.lru_cache(maxsize=None)
def shape(state):
    """The collision of one block, as (lo, hi, stair_facing): heights within the cell (hi may be 1.5 for a fence or
    a wall), the facing of a bottom stair (its high half), or None for no collision."""
    n, _p = parse_state(state)
    short = n.split(":", 1)[1]
    if n in NOCOLL or short.endswith(NOCOLL_SUFFIX):
        return None
    if n == NAT or n == PAD:
        return (0.0, 1.0, None)
    if short.endswith("_slab"):
        t = prop(state, "type", "bottom")
        return {"bottom": (0.0, 0.5, None), "top": (0.5, 1.0, None)}.get(t, (0.0, 1.0, None))
    if short.endswith("_stairs"):
        if prop(state, "half", "bottom") == "top":
            return (0.0, 1.0, None)
        return (0.0, 1.0, prop(state, "facing", "north"))
    if short.endswith("_fence") or short.endswith("_wall"):
        return (0.0, 1.5, None)
    if short.endswith("_fence_gate"):
        return None if prop(state, "open", "false") == "true" else (0.0, 1.5, None)
    if short.endswith("_trapdoor"):
        if prop(state, "open", "false") == "true":
            return None
        return (0.8125, 1.0, None) if prop(state, "half", "bottom") == "top" else (0.0, 0.1875, None)
    if short.endswith("carpet"):
        return (0.0, 0.0625, None)
    if short in ("lantern", "soul_lantern"):
        return (0.0625, 0.625, None) if prop(state, "hanging", "false") == "true" else (0.0, 0.5625, None)
    if short in ("flower_pot",) or short.startswith("potted_"):
        return (0.0, 0.375, None)
    if short in ("lectern", "brewing_stand"):
        return (0.0, 0.875, None)
    if short.endswith("campfire"):
        return (0.0, 0.4375, None)
    if short.endswith("candle"):
        return (0.0, 0.375, None)
    return (0.0, 1.0, None)


def collides(state):
    return shape(state) is not None


@functools.lru_cache(maxsize=None)
def opaque(state):
    """A full opaque cube stops block light; everything else lets it through (a partial shape, glass, roots)."""
    s = shape(state)
    if s is None or s[0] != 0.0 or s[1] != 1.0 or s[2] is not None:
        return False
    n = name_of(state)
    if n in (NAT, PAD):
        return True
    short = n.split(":", 1)[1]
    if short == "tinted_glass":
        return True
    if any(t in short for t in TRANSPARENT_FULL):
        return False
    if short in ("chain", "end_rod", "lightning_rod", "iron_bars") or short.endswith("_pane"):
        return False
    return True


def extra_opacity(state):
    n = name_of(state)
    if n in ("minecraft:water", NAT_WATER) or prop(state, "waterlogged") == "true":
        return 1
    if n.endswith("_leaves") or n.endswith("ice"):
        return 1
    return 0


EMIT = {"lantern": 15, "soul_lantern": 10, "torch": 14, "wall_torch": 14, "soul_torch": 10, "soul_wall_torch": 10,
        "redstone_torch": 7, "redstone_wall_torch": 7, "sea_lantern": 15, "glowstone": 15, "shroomlight": 15,
        "ochre_froglight": 15, "verdant_froglight": 15, "pearlescent_froglight": 15, "end_rod": 14,
        "jack_o_lantern": 15, "lava": 15, "magma_block": 3, "glow_lichen": 7, "beacon": 15, "conduit": 15,
        "crying_obsidian": 10, "enchanting_table": 7, "ender_chest": 7, "amethyst_cluster": 5,
        "large_amethyst_bud": 4, "medium_amethyst_bud": 2, "small_amethyst_bud": 1, "brewing_stand": 1,
        "sculk_catalyst": 6, "dragon_egg": 1, "respawn_anchor": 0, "light": 15}
EMIT_IF_LIT = {"redstone_lamp": 15, "campfire": 15, "soul_campfire": 10, "furnace": 13, "blast_furnace": 13,
               "smoker": 13, "copper_bulb": 15, "waxed_copper_bulb": 15}


@functools.lru_cache(maxsize=None)
def emission(state):
    n = name_of(state)
    short = n.split(":", 1)[1]
    if short in ("cave_vines", "cave_vines_plant"):
        return 14 if prop(state, "berries", "false") == "true" else 0
    if short == "light":
        return int(prop(state, "level", "15"))
    if short.endswith("candle"):
        return 3 * int(prop(state, "candles", "1")) if prop(state, "lit", "false") == "true" else 0
    if short in EMIT_IF_LIT:
        return EMIT_IF_LIT[short] if prop(state, "lit", "false" if short == "redstone_lamp" else "true") == "true" \
            else 0
    if n == NAT_WATER:
        return 0
    return EMIT.get(short, 0)


def is_water(state):
    n = name_of(state)
    return n in ("minecraft:water", NAT_WATER) or prop(state, "waterlogged") == "true" or \
        n in ("minecraft:bubble_column",)


def is_lava(state):
    return name_of(state) == "minecraft:lava"


def flow_passable(state):
    if collides(state):
        return False
    n = name_of(state)
    short = n.split(":", 1)[1]
    if n in FLOW_STOP or short.endswith(FLOW_STOP_SUFFIX):
        return False
    return True


def flammable(state):
    short = name_of(state).split(":", 1)[1]
    if short.startswith(("crimson", "warped")):
        return False
    if any(k in short for k in ("planks", "_log", "_wood", "_leaves", "wool", "bookshelf", "hay_block",
                                "scaffolding", "vine", "mosaic", "mangrove_roots", "azalea", "lectern", "beehive",
                                "bee_nest", "target", "dried_kelp", "tnt", "composter", "_carpet")):
        return True
    if short.startswith(WOODS) and short.endswith(("_stairs", "_slab", "_fence", "_fence_gate")):
        return True
    return False


# ================================================================================================ the world
class Nature:
    """What stands in a column before any function runs: rock up to the ground (tools/ground.py), the lot cut to its
    level, the world's water settled over its bed."""

    def __init__(self, G, lots, water_level):
        self.G = G
        self.lots = lots              # [(x0, z0, x1, z1, level or None)]
        self.water_level = water_level  # (x, z) -> level y or 0

    @functools.lru_cache(maxsize=None)
    def column(self, x, z):
        g = self.G(x, z)
        level = None
        for (x0, z0, x1, z1, lv) in self.lots:
            if x0 <= x <= x1 and z0 <= z <= z1 and lv is not None:
                level = int(lv)
        return g, level, self.water_level(x, z)

    def natural_top(self, x, z):
        """(y, exact): the highest natural block of the column, and whether it is exact (a cut) or the heightmap."""
        g, level, _w = self.column(x, z)
        if level is not None and g >= level - 1:
            return level - 1, True
        return g, False

    def __call__(self, x, y, z):
        g, level, wl = self.column(x, z)
        if level is not None:
            if y >= level:
                return NAT_AIR
            if y > g:
                return PAD
            return NAT
        if wl and g < y <= wl:
            return NAT_WATER
        if y <= g:
            return NAT
        return NAT_AIR


class World:
    def __init__(self, nature):
        self.nature = nature
        self.cells = {}
        self.layer = {}

    def get(self, x, y, z):
        s = self.cells.get((x, y, z))
        return s if s is not None else self.nature(x, y, z)

    def set(self, c, state, layer):
        self.cells[c] = state
        self.layer[c] = layer

    def written(self, c):
        return c in self.cells


class Unsupported(SystemExit):
    pass


def matches(state, pred):
    if pred.startswith("#"):
        raise Unsupported("block tag predicates are not modelled: %s" % pred)
    pn, pp = parse_state(pred)
    sn, sp = parse_state(state)
    if sn == NAT_WATER:
        sn = "minecraft:water"
    if pn != sn:
        return False
    sd = dict(sp)
    return all(sd.get(k) == v for k, v in pp)


IGNORED = ("forceload", "tellraw", "scoreboard", "schedule", "say", "function", "kill", "tp", "summon", "data",
           "gamerule", "playsound", "title", "particle", "effect", "tag", "return")


def apply_line(world, line, layer, log):
    w = line.split()
    if not w or w[0].startswith("#"):
        return
    cmd = w[0]
    if cmd == "fill":
        x0, y0, z0, x1, y1, z1 = (int(v) for v in w[1:7])
        state = w[7]
        mode = w[8] if len(w) > 8 else "replace"
        filt = w[9] if len(w) > 9 and mode == "replace" else None
        if mode not in ("replace", "destroy", "keep", "hollow", "outline"):
            raise Unsupported("fill mode %r: %s" % (mode, line))
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        za, zb = sorted((z0, z1))
        for x in range(xa, xb + 1):
            for y in range(ya, yb + 1):
                for z in range(za, zb + 1):
                    edge = x in (xa, xb) or y in (ya, yb) or z in (za, zb)
                    if mode in ("replace", "destroy"):
                        if filt and not matches(world.get(x, y, z), filt):
                            continue
                        world.set((x, y, z), state, layer)
                    elif mode == "keep":
                        if name_of(world.get(x, y, z)) in AIRS:
                            world.set((x, y, z), state, layer)
                    elif mode == "hollow":
                        world.set((x, y, z), state if edge else "minecraft:air", layer)
                    elif mode == "outline" and edge:
                        world.set((x, y, z), state, layer)
        log["fill"] = log.get("fill", 0) + 1
    elif cmd == "setblock":
        x, y, z = (int(v) for v in w[1:4])
        state = w[4]
        mode = w[5] if len(w) > 5 else "replace"
        if mode == "keep" and name_of(world.get(x, y, z)) not in AIRS:
            return
        world.set((x, y, z), state, layer)
        log["setblock"] = log.get("setblock", 0) + 1
    elif cmd == "execute":
        ok, i = True, 1
        while i < len(w):
            t = w[i]
            if t in ("if", "unless"):
                kind = w[i + 1]
                if kind == "block":
                    x, y, z = (int(v) for v in w[i + 2:i + 5])
                    res = matches(world.get(x, y, z), w[i + 5])
                    i += 6
                elif kind == "entity":
                    res = False   # nobody is near: the apply's own guard, and the state the audit models
                    i += 3
                else:
                    raise Unsupported("execute %s %s: %s" % (t, kind, line))
                ok = ok and (res if t == "if" else not res)
            elif t == "positioned":
                i += 3 if w[i + 1] == "as" else 4
            elif t in ("as", "at", "in"):
                i += 2
            elif t == "run":
                if ok:
                    apply_line(world, " ".join(w[i + 1:]), layer, log)
                log["execute"] = log.get("execute", 0) + 1
                return
            else:
                raise Unsupported("execute subcommand %r: %s" % (t, line))
        raise Unsupported("execute without run: %s" % line)
    elif cmd in IGNORED:
        return
    else:
        raise Unsupported("a command the audit cannot replay: %s" % line)


def apply_file(world, path, layer):
    log = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "~" in line and not line.startswith("#"):
            raise Unsupported("relative coordinates are not modelled: %s" % line)
        apply_line(world, line, layer, log)
    return log


def function_writes(path):
    """Every cell one function's plain fills and setblocks touch (execute-guarded writes excluded), as a set."""
    out = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        w = line.split()
        if not w or w[0].startswith("#"):
            continue
        if w[0] == "fill":
            x0, y0, z0, x1, y1, z1 = (int(v) for v in w[1:7])
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        out.add((x, y, z))
        elif w[0] == "setblock":
            out.add(tuple(int(v) for v in w[1:4]))
    return out


# ============================================================================================ the inputs
def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def norm(b):
    x0, y0, z0, x1, y1, z1 = b
    return (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1))


def inside(c, b):
    return b[0] <= c[0] <= b[3] and b[1] <= c[1] <= b[4] and b[2] <= c[2] <= b[5]


def site(gym, building_pack=None, interior_pack=None):
    """The gym's own data, independent of the arena record: leader id, the building (or dig) box, where the puzzle
    route ends, the lot."""
    bp = ROOT / "data" / "gym_buildings" / ("%s.json" % gym)
    placements = load(ROOT / "data" / "placements.json")["settlements"]
    if bp.exists():
        b = load(bp)
        spawner = tuple(b["leader"]["spawner"])
        ends = [tuple(st["to"]) for st in b.get("route") or [] if st.get("to")]
        end = min(ends, key=lambda t: (t[0] - spawner[0]) ** 2 + (t[1] - spawner[1]) ** 2 + (t[2] - spawner[2]) ** 2)
        starts = [tuple(st["from"]) for st in b.get("route") or [] if st.get("from")]
        lots = [(a["rect"][0], a["rect"][1], a["rect"][2], a["rect"][3], a.get("level"))
                for a in placements[b["settlement"]]["plan"].get("anchors") or [] if a.get("role") == "gym"]
        return {"leader": b["leader"]["id"], "host_box": norm(b["bounds"]), "host_fn": Path(building_pack or BUILDING_PACK) / "data" /
                "cobblers" / "function" / "gym_buildings" / ("%s.mcfunction" % gym), "host": "building",
                "route_end": end, "route_start": starts[0] if starts else None, "hall_spawner": spawner,
                "lots": lots, "host_allows_natural_air": True}
    i = [g for g in load(ROOT / "data" / "gym_interiors.json")["gyms"] if g["id"] == gym][0]
    gallery = [st["at"] for st in i["route"] if st.get("room") == "r3_gallery"]
    lots = [(a["rect"][0], a["rect"][1], a["rect"][2], a["rect"][3], a.get("level"))
            for a in placements[i["settlement"]]["plan"].get("anchors") or [] if "gym" in (a.get("role") or "")]
    return {"leader": i["leader"]["id"], "host_box": norm(i["dig"]), "host_fn": Path(interior_pack or INTERIOR_PACK) / "data" / "cobblers" /
            "function" / "gym_interiors" / ("%s.mcfunction" % gym), "host": "dig",
            "template_box": norm(i["shell"]["expect_box"]),
            "route_end": tuple(gallery[0]), "route_start": None, "hall_spawner": tuple(i["leader"]["expect_spawner_at"]),
            "lots": lots, "host_allows_natural_air": False}


def declared(gym):
    """The two declared fields an arena's writes are held to: bounds and through_building. Nothing else of the
    record is read."""
    d = load(ROOT / "data" / "gym_arenas" / ("%s.json" % gym))
    return norm(d["bounds"]), [norm(t["box"]) for t in d.get("through_building") or []], d


def challenge_spawner(leader):
    b = load(ROOT / "data" / "challenge_mode.json")["bosses"].get(leader) or {}
    at = (b.get("spawner") or {}).get("at")
    return tuple(at) if at else None


def spawn_height_offset():
    return float(load(ROOT / "base-pack" / "cobbleverse" / "config" / "cobblemonbattlepositions.json")
                 ["spawnHeightOffset"])


# ================================================================================================= sizes
def team_species(leader):
    """Every species a leader can send out, over every tier: data/trainers.json (the record whose rct id or
    gym_trainers mapping is the leader), data/gym_trainers.json's ace, data/challenge_mode.json's boss record."""
    gt = load(ROOT / "data" / "gym_trainers.json")["trainers"]
    ours = {t["id"] for t in gt if t.get("upstream_trainer_id") == leader}
    found = {}

    def collect(o, where):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("species", "ace_species") and isinstance(v, str):
                    found.setdefault(v, set()).add(where)
                else:
                    collect(v, where)
        elif isinstance(o, list):
            for v in o:
                collect(v, where)

    for t in load(ROOT / "data" / "trainers.json")["trainers"]:
        if t.get("id") in ours:
            collect(t, "data/trainers.json %s" % t["id"])
    for t in gt:
        if t["id"] in ours:
            collect(t.get("ace") or {}, "data/gym_trainers.json %s ace" % t["id"])
    collect(load(ROOT / "data" / "challenge_mode.json")["bosses"].get(leader) or {},
            "data/challenge_mode.json bosses.%s" % leader)
    out = {}
    for s, w in found.items():
        toks = s.replace("cobblemon:", "").split()
        out.setdefault(toks[0].lower(), {"aspects": set(), "where": set()})
        out[toks[0].lower()]["aspects"] |= set(toks[1:])
        out[toks[0].lower()]["where"] |= w
    return out


class Archives:
    """The server's archives, read with zipfile: every mod jar and every world datapack in the snapshot."""

    def __init__(self, snap=SNAPSHOT):
        self.snap = Path(snap)
        self.mods = sorted((self.snap / "mods").glob("*.jar"))
        self.packs = sorted(p for p in (self.snap / "datapacks").glob("*.zip"))
        self._index = None

    def index(self):
        if self._index is None:
            idx = []
            for kind, paths in (("mod", self.mods), ("datapack", self.packs)):
                for p in paths:
                    try:
                        z = zipfile.ZipFile(p)
                    except zipfile.BadZipFile:
                        continue
                    names = [n for n in z.namelist() if n.endswith(".json") and (
                        "/species/" in n or "/species_additions/" in n or "/bedrock/pokemon/resolvers/" in n
                        or "/bedrock/pokemon/models/" in n or "/bedrock/models/" in n)]
                    if names:
                        idx.append((kind, p, z, names))
            self._index = idx
        return self._index

    def read(self, z, n):
        return json.loads(z.read(n).decode("utf-8-sig"))


def species_size(arch, sp):
    """(width, height, baseScale, sources) over every candidate file: a world datapack's species file overrides a
    mod's at the same path; between two mods the loader's order is not fixed, so every candidate counts, and the
    largest is the design figure. Additions apply on top."""
    files, adds = [], []
    for kind, p, z, names in arch.index():
        for n in names:
            if "/species/" in n and n.endswith("/%s.json" % sp):
                files.append((kind, p.name, n, arch.read(z, n)))
            elif "/species_additions/" in n:
                d = arch.read(z, n)
                tgt = str(d.get("target", "")).split(":")[-1]
                if tgt == sp:
                    adds.append((kind, p.name, n, d))
    if any(k == "datapack" for k, *_ in files):
        files = [f for f in files if f[0] == "datapack"]
    if not files:
        return None
    # a species file with no hitbox takes Species.<init>'s 1 x 1, with no baseScale 1.0. Every addition applies
    # over the file, each overriding only the fields it sets; their mutual order is not known, so every order is
    # a candidate and the largest product is the design figure
    import itertools
    srcs, cands = [], []
    for _kind, an, n, d in files:
        srcs.append("%s %s hitbox %s baseScale %s" % (an, n, d.get("hitbox"), d.get("baseScale")))
    sets = [d for _k, _a, _n, d in adds if d.get("hitbox") or d.get("baseScale") is not None]
    for _kind, an, n, d in adds:
        if d.get("hitbox") or d.get("baseScale") is not None:
            srcs.append("%s %s (addition) hitbox %s baseScale %s" % (an, n, d.get("hitbox"), d.get("baseScale")))
    for _kind, _an, _n, d in files:
        for order in itertools.permutations(sets):
            hb = d.get("hitbox") or {"width": 1.0, "height": 1.0}
            sc = 1.0 if d.get("baseScale") is None else float(d["baseScale"])
            for a in order:
                hb = a.get("hitbox") or hb
                sc = float(a["baseScale"]) if a.get("baseScale") is not None else sc
            cands.append((float(hb["width"]) * sc, float(hb["height"]) * sc, sc))
    return {"width": max(c[0] for c in cands), "height": max(c[1] for c in cands),
            "scale": max(c[2] for c in cands), "sources": srcs}


def rot(rx, ry, rz):
    """The bind-pose rotation of a bone or cube, in the geometry file's own frame (y up). TexturedModel (javap
    -c, Cobblemon 1.8.0) builds each part as PartPose.offsetAndRotation(pivot - parentPivot with y negated,
    toRadians(rx), toRadians(ry), toRadians(rz)) and each box with y negated, so the part lives in F = diag(1,-1,1)
    of the file's frame; ModelPart turns it by rotationZYX(z, y, x) = Rz Ry Rx. Conjugated back by F that is
    Rz(-rz) Ry(ry) Rx(-rx). A root bone (no parent) gets PartPose.offset(0, 0, 0): no rotation."""
    def m(a, axis):
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        if axis == "x":
            return ((1, 0, 0), (0, c, -s), (0, s, c))
        if axis == "y":
            return ((c, 0, s), (0, 1, 0), (-s, 0, c))
        return ((c, -s, 0), (s, c, 0), (0, 0, 1))

    def mul(A, B):
        return tuple(tuple(sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    return mul(mul(m(-rz, "z"), m(ry, "y")), m(-rx, "x"))


def apply_m(M, v):
    return tuple(sum(M[i][k] * v[k] for k in range(3)) for i in range(3))


def model_extent(geo):
    """(radius, top) of a bedrock geometry in its bind pose, in model units (1/16 block): the farthest any cube
    corner lies from the vertical axis through the origin, and the highest corner. Positions follow TexturedModel:
    a root bone's cubes sit at origin - rootPivot; a child's at (pivot - parentPivot) + R (point - pivot), up the
    chain; a rotated cube is a sub-part about its own pivot."""
    g = geo["minecraft:geometry"][0] if "minecraft:geometry" in geo else geo
    bones = {b["name"]: b for b in g.get("bones") or []}

    def up(name, v):
        b = bones[name]
        par = b.get("parent")
        if not par or par not in bones:
            return v
        p, pp = b.get("pivot") or [0, 0, 0], bones[par].get("pivot") or [0, 0, 0]
        r = b.get("rotation")
        v2 = apply_m(rot(*r), v) if r else v
        return up(par, tuple(p[i] - pp[i] + v2[i] for i in range(3)))

    rad, top = 0.0, -1e9
    for name, b in bones.items():
        bp = b.get("pivot") or [0, 0, 0]
        for c in b.get("cubes") or []:
            o, s = c.get("origin"), c.get("size")
            if not o or not s:
                continue
            inf = float(c.get("inflate") or 0)
            lo = [o[i] - inf for i in range(3)]
            hi = [o[i] + s[i] + inf for i in range(3)]
            for cx in (lo[0], hi[0]):
                for cy in (lo[1], hi[1]):
                    for cz in (lo[2], hi[2]):
                        q = (cx, cy, cz)
                        if c.get("rotation"):
                            cp = c.get("pivot") or bp
                            w = apply_m(rot(*c["rotation"]), tuple(q[i] - cp[i] for i in range(3)))
                            v = tuple(cp[i] - bp[i] + w[i] for i in range(3))
                        else:
                            v = tuple(q[i] - bp[i] for i in range(3))
                        if b.get("parent") and b["parent"] in bones:
                            pos = up(name, v)
                            # up() returns the point in the root bone's frame: relative to the root pivot
                        else:
                            pos = v
                        # absolute model coordinates: add the root's pivot back (the root sits at its own pivot in
                        # the geometry; its offset(0,0,0) puts that pivot at the entity origin, so for the radius
                        # the root-relative position is the one that counts)
                        rad = max(rad, math.hypot(pos[0], pos[2]))
                        root = name
                        while bones[root].get("parent") in bones:
                            root = bones[root]["parent"]
                        top = max(top, pos[1] + (bones[root].get("pivot") or [0, 0, 0])[1])
    return rad, top


def species_model(arch, sp):
    """(radius, top, source) in model units of the base form's model (resolver variation with no aspects), the
    largest over every server archive that resolves the species; None if no server archive carries one."""
    models = set()
    for _k, p, z, names in arch.index():
        for n in names:
            if "/bedrock/pokemon/resolvers/" not in n:
                continue
            try:
                d = arch.read(z, n)
            except ValueError:
                continue
            if str(d.get("species", "")).split(":")[-1] != sp:
                continue
            for v in d.get("variations") or []:
                if not v.get("aspects") and v.get("model"):
                    models.add(v["model"].split(":")[-1])
    best = None
    for m in models:
        fname = "/%s.json" % m
        for _k, p, z, names in arch.index():
            for n in names:
                if "/models/" in n and n.endswith(fname):
                    r, t = model_extent(arch.read(z, n))
                    if best is None or r > best[0]:
                        best = (r, t, "%s %s" % (p.name, n))
    return best


def leader_size(arch, leader):
    """The clear radius and height, measured, over every member of every tier."""
    team = team_species(leader)
    rows = {}
    for sp, info in sorted(team.items()):
        hs = species_size(arch, sp)
        if hs is None:
            rows[sp] = {"missing": True, "aspects": sorted(info["aspects"])}
            continue
        md = species_model(arch, sp)
        s = hs["scale"]
        mr = md[0] / 16.0 * s if md else None
        mt = md[1] / 16.0 * s if md else None
        rows[sp] = {"width": hs["width"], "height": hs["height"], "scale": s,
                    "half_diagonal": hs["width"] / math.sqrt(2.0),
                    "model_radius": mr, "model_top": mt, "model": md[2] if md else None,
                    "aspects": sorted(info["aspects"]), "sources": hs["sources"]}
    ok = {k: v for k, v in rows.items() if not v.get("missing")}
    R = max((max(v["half_diagonal"], v["model_radius"] or 0.0), k) for k, v in ok.items())
    H = max((max(v["height"], v["model_top"] or 0.0), k) for k, v in ok.items())
    W = max((v["width"], k) for k, v in ok.items())
    return {"members": rows, "radius": R[0], "radius_species": R[1], "height": H[0], "height_species": H[1],
            "width": W[0], "width_species": W[1]}


def doc_table():
    """GYM_ARENAS.md's size table, to compare: {gym: {widest, tallest, radius, height, members}}."""
    out = {}
    text = (ROOT / "docs" / "world-building" / "GYM_ARENAS.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(r"\|\s*(\d)\s*\|[^|]+\|\s*(\w+) ([\d.]+)\s*\|\s*(\w+) ([\d.]+)\s*\|[^|]+\|\s*(\w+) ([\d.]+)\s*\|"
                     r"\s*(\w+) ([\d.]+)\s*\|\s*([^|]+)\|", line)
        if m:
            out["gym" + m.group(1)] = {"widest": (m.group(2), float(m.group(3))),
                                       "tallest": (m.group(4), float(m.group(5))),
                                       "radius": (m.group(6), float(m.group(7))),
                                       "height": (m.group(8), float(m.group(9))),
                                       "members": sorted(s.strip() for s in m.group(10).split(","))}
    return out


# ================================================================================================= the walk
class Walker:
    """A player's body in the block model. Nodes are (x, z, h): feet height h, a multiple of 1/16."""

    def __init__(self, world, box, fall=SAFE_FALL, jump=True, body=None):
        self.W = world
        self.box = box   # (x0, y0, z0, x1, y1, z1)
        self.fall = fall
        self.jump = jump
        self.body = body or BODY   # 1.5 crouching (Pose.CROUCHING's dimensions)
        self._sh = {}

    def sh(self, x, y, z):
        k = (x, y, z)
        v = self._sh.get(k)
        if v is None:
            st = self.W.get(x, y, z)
            v = (shape(st), is_water(st) and not collides(st), name_of(st) in CLIMB, is_lava(st))
            self._sh[k] = v
        return v

    def clear(self, x, z, a, b):
        """No collision (and no lava) in the column between heights a and b."""
        for y in range(int(math.floor(a)) - 1, int(math.floor(b - EPS)) + 1):
            s, _w, _c, lava = self.sh(x, y, z)
            if lava and y + 1 > a + EPS and y < b - EPS:
                return False
            if s is None:
                continue
            lo, hi = y + s[0], y + s[1]
            if lo < b - EPS and hi > a + EPS:
                return False
        return True

    def support(self, x, z, h):
        """The block a player standing at h stands on, or None."""
        for y in (int(math.floor(h - EPS)), int(math.floor(h - EPS)) - 1):
            s, _w, _c, _l = self.sh(x, y, z)
            if s is not None and abs(y + s[1] - h) < EPS:
                return (x, y, z)
        return None

    def floating(self, x, z, h):
        """Held up without a block: in water or on a climbable (feet cell)."""
        y = int(math.floor(h + EPS))
        _s, w, c, _l = self.sh(x, y, z)
        return w or c

    def valid(self, x, z, h):
        return self.clear(x, z, h, h + self.body) and (self.support(x, z, h) is not None or self.floating(x, z, h))

    def inbox(self, x, z, h):
        b = self.box
        return b[0] <= x <= b[3] and b[2] <= z <= b[5] and b[1] <= h <= b[4] + 1

    def supports_in(self, x, z, lo, hi):
        out = []
        for y in range(int(math.floor(lo)) - 2, int(math.floor(hi)) + 1):
            s, _w, _c, _l = self.sh(x, y, z)
            if s is not None and lo - EPS <= y + s[1] <= hi + EPS:
                out.append((y + s[1], (x, y, z), s))
        return out

    def settle(self, x, y, z):
        """The node a player at feet cell (x, y, z) stands at: the highest valid height from y + 0.5 down 3."""
        for h16 in range(int((y + 0.5) * 16), int((y - 3) * 16) - 1, -1):
            h = h16 / 16.0
            if self.valid(x, z, h):
                return (x, z, h)
        return None

    def side_top(self, cell, d):
        """The top of a support's half that faces direction d: a bottom stair's low half (+0.5) on the side away
        from its facing, its high half (+1) toward it or along it; any other block its top."""
        s = self.sh(*cell)[0]
        if s[2] is not None and FACING[s[2]] == (-d[0], -d[1]):
            return cell[1] + 0.5
        return cell[1] + s[1]

    def col_clear(self, x, z, base, lo, hi):
        """No collision (and no lava) in column (x, z) overlapping [lo, hi), counting only the cells over `base`
        (the support's own cell, whose shape the straddle height already accounts for) when there is one."""
        start = base + 1 if base is not None else int(math.floor(lo)) - 1
        for y in range(start, int(math.floor(hi - EPS)) + 1):
            s, _w, _c, lava = self.sh(x, y, z)
            if lava and y + 1 > lo + EPS and y < hi - EPS:
                return False
            if s is not None and y + s[0] < hi - EPS and y + s[1] > lo + EPS:
                return False
        return True

    def moves(self, n):
        """One step from node n. Between two columns the body passes the boundary at the STRADDLE height: the
        higher of the two halves under it (a stair's low half on its low side), so a flight of stairs is two
        half-block steps a tread and the head clears what hangs over the boundary only if it clears it from there."""
        x, z, h = n
        out = []
        yfeet = int(math.floor(h + EPS))
        _s, wet, climb, _l = self.sh(x, yfeet, z)
        sa = self.support(x, z, h)
        surface_swim = wet and not self.sh(x, yfeet + 1, z)[1]
        if wet or climb:
            if self.valid(x, z, h + 1):
                out.append(((x, z, h + 1), "climb"))
            if self.valid(x, z, h - 1):
                out.append(((x, z, h - 1), "climb"))
        lift = JUMP if self.jump else STEP
        if surface_swim:
            lift = max(lift, (yfeet + 2) - h)   # a swimmer climbs onto a bank one over the surface cell
        elif climb:
            lift = max(lift, 1.0)               # off the top of a ladder
        floating = sa is None
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            tA = self.side_top(sa, (dx, dz)) if sa else h
            # what is under the body in the next column, from the highest it could step or jump to down to the
            # first thing a walk off the edge lands on (nothing under that is reached by walking)
            cands = []
            for y in range(int(math.floor(h + max(lift, 1.0) + EPS)), int(math.floor(h)) - 65, -1):
                s2, w2, c2, l2 = self.sh(nx, y, nz)
                if l2:
                    break
                if s2 is not None:
                    top = y + s2[1]
                    cands.append((top, (nx, y, nz)))
                    if top <= h + EPS:
                        break
                elif w2 or c2:
                    cands.append((float(y), None))
                    if y <= h + EPS:
                        break
            for h2, sb in cands:
                if not self.valid(nx, nz, h2):
                    continue
                tB = self.side_top(sb, (-dx, -dz)) if sb else h2
                ht = max(tA, tB)
                rise1, rise2 = ht - h, h2 - ht
                walk = rise1 <= STEP + EPS and rise2 <= STEP + EPS
                jumped = False
                if not walk:
                    if h2 - h > lift + EPS or (not self.jump and not floating and h2 - h > STEP + EPS):
                        continue
                    jumped = True
                fall = ht - h2
                if sb is not None and fall > self.fall + EPS:
                    continue
                # over its own column the head rises to the higher of where it stands and the straddle (and, in a
                # jump, the height it lands at); over the next column only to the straddle or the landing
                head_a = max(h, ht, h2 if jumped else h) + self.body
                head_b = max(ht, h2) + self.body
                if not self.col_clear(x, z, sa[1] if sa else None, min(h, ht), head_a):
                    continue
                if not self.col_clear(nx, nz, sb[1] if sb else None, min(h2, ht), head_b):
                    continue
                out.append(((nx, nz, h2), "jump" if jumped else ("fall" if fall > EPS else "walk")))
        return out

    def reach(self, start, stop=None):
        seen, q = {start}, deque([start])
        while q:
            n = q.popleft()
            if stop is not None and n == stop:
                break
            for m, _how in self.moves(n):
                if m not in seen and self.inbox(*m):
                    seen.add(m)
                    q.append(m)
        return seen


def blocked_at(upright, crouch, start):
    """Where an upright walk stops that a crouching one passes: the first crouch-only moves out of the upright
    set, with what stands in the way."""
    if start is None:
        return ""
    seen = upright.reach(start)
    out = []
    for n in sorted(seen):
        for m, _how in crouch.moves(n):
            if m in seen or not crouch.inbox(*m):
                continue
            x, z, h = m
            stops = []
            # what an upright head meets and a crouching one passes: collision between 1.5 and 1.8 over the
            # lower of the two heights, in either column
            base = min(h, n[2])
            for (cx, cz) in ((x, z), (n[0], n[1])):
                for y in range(int(math.floor(base + 1.5)) - 1, int(math.floor(max(h, n[2]) + BODY)) + 1):
                    st = upright.W.get(cx, y, cz)
                    if collides(st):
                        lo, hi, _f = shape(st)
                        if y + lo < max(h, n[2]) + BODY - EPS and y + hi > base + 1.5 - 0.5:
                            stops.append(((cx, y, cz), st))
            out.append((m, stops))
    if not out:
        return ""
    return "; upright stops at %d step(s), first into %s past %s" % (
        len(out), [out[0][0][0], out[0][0][2], out[0][0][1]], [[list(c), st] for c, st in out[0][1]][:2])


# ================================================================================================= fluids, light
def flow(world, box, sources, reach):
    """Every cell a fluid from `sources` reaches: down without limit, sideways `reach` from where it lands; settled
    world water never moves into an unwritten cell."""
    best = {}
    q = deque()
    for c in sources:
        best[c] = 0
        q.append(c)

    def ok(c):
        return box[0] <= c[0] <= box[3] and box[1] <= c[1] <= box[4] and box[2] <= c[2] <= box[5]

    while q:
        c = q.popleft()
        d = best[c]
        x, y, z = c
        src_nat = not world.written(c)
        below = (x, y - 1, z)
        targets = []
        if ok(below) and (flow_passable(world.get(*below)) or best.get(below) is not None):
            targets.append((below, 0))
        if d < reach:
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                targets.append(((x + dx, y, z + dz), d + 1))
        for t, nd in targets:
            if not ok(t):
                continue
            st = world.get(*t)
            if is_water(st) or is_lava(st):
                if t not in best:
                    best[t] = 0
                    q.append(t)
                continue
            if not flow_passable(st):
                continue
            if src_nat and not world.written(t):
                continue
            if best.get(t, 99) > nd:
                best[t] = nd
                q.append(t)
    return set(best)


def block_light(world, box):
    lit, q = {}, deque()
    for c, st in world.cells.items():
        if not inside(c, box):
            continue
        e = emission(st)
        if e:
            lit[c] = max(lit.get(c, 0), e)
            q.append(c)
    while q:
        c = q.popleft()
        v = lit[c]
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (c[0] + d[0], c[1] + d[1], c[2] + d[2])
            if not inside(n, box):
                continue
            st = world.get(*n)
            if opaque(st):
                continue
            nv = v - 1 - extra_opacity(st)
            if nv > lit.get(n, 0):
                lit[n] = nv
                q.append(n)
    return lit


# ================================================================================================= one gym
def assemble(gym, pack=ARENA_PACK, G=None, water_fn=None, hosts=(None, None)):
    """The world as the apply leaves it for one gym: nature, the host (building or dig), the arena, the seat move,
    the Challenge spawner."""
    import ground as ground_mod
    G = G or ground_mod.load()
    s = site(gym, *hosts)
    bounds, through, _rec = declared(gym)
    if water_fn is None:
        water_fn = water_levels(G, bounds, s["host_box"])
    world = World(Nature(G, s["lots"], water_fn))
    funcs = Path(pack) / "data" / "cobblers" / "function" / "gym_arenas"
    if s["host"] == "dig":
        # the donor template is not in the repository; the one cell of it the seat move reads is its spawner, which
        # data/gym_interiors.json records as measured (expect_spawner_at), standing on a redstone block
        hx, hy, hz = s["hall_spawner"]
        world.set((hx, hy - 1, hz), "minecraft:redstone_block", "template")
        world.set((hx, hy, hz), 'rctmod:trainer_spawner{TrainerIds:["%s"]}' % s["leader"], "template")
    logs = {"host": apply_file(world, s["host_fn"], s["host"])}
    host_cells = set(world.cells)
    logs["arena"] = apply_file(world, funcs / ("%s.mcfunction" % gym), "arena")
    arena_writes = function_writes(funcs / ("%s.mcfunction" % gym))
    logs["seat"] = apply_file(world, funcs / ("%s_seat.mcfunction" % gym), "seat")
    cs = challenge_spawner(s["leader"])
    if cs and inside(cs, bounds):
        world.set(cs, 'rctmod:trainer_spawner{TrainerIds:["%s_challenge"]}' % s["leader"], "cycle")
    return world, s, bounds, through, arena_writes, host_cells, logs


def water_levels(G, bounds, host):
    """(x, z) -> water level over a window round the arena and its host, from tools/bridges.py water()."""
    import bridges
    x0 = min(bounds[0], host[0]) - 24
    z0 = min(bounds[2], host[2]) - 24
    x1 = max(bounds[3], host[3]) + 24
    z1 = max(bounds[5], host[5]) + 24
    level, wet, _definite = bridges.water(G.heights, G.world, (x0, z0, x1, z1))

    def f(x, z):
        if x0 <= x <= x1 and z0 <= z <= z1 and wet[z - z0, x - x0]:
            return int(level[z - z0, x - x0])
        return 0
    f.window = (x0, z0, x1, z1)
    f.wet = int(wet.sum())
    return f


def markers(world, bounds):
    out = {}
    for c, st in world.cells.items():
        n = name_of(st)
        if n.startswith("cobblemonbattlepositions:"):
            out.setdefault(n.split(":")[1], []).append(c)
    return out


def audit_gym(gym, pack=ARENA_PACK, G=None, arch=None, size=None, hosts=(None, None)):
    import ground as ground_mod
    G = G or ground_mod.load()
    world, s, bounds, through, arena_writes, host_cells, logs = assemble(gym, pack, G, hosts=hosts)
    problems, facts = [], {"gym": gym, "leader": s["leader"], "logs": logs}
    region = [bounds, s["host_box"]] + through
    box = (min(b[0] for b in region) - 2, min(b[1] for b in region) - 3, min(b[2] for b in region) - 2,
           max(b[3] for b in region) + 2, max(b[4] for b in region) + 3, max(b[5] for b in region) + 2)

    # ---- the blocks the battle reads
    mk = markers(world, bounds)
    for k in ("trainer_pokemon_position", "player_pokemon_position", "trainer_stand_position",
              "player_stand_position"):
        if len(mk.get(k, [])) != 1:
            problems.append("marker %s: %d in the model (exactly one)" % (k, len(mk.get(k, []))))
    seats = [c for c, st in world.cells.items() if name_of(st) == "rctmod:trainer_spawner"
             and s["leader"] in st and "_challenge" not in st and inside(c, bounds)]
    if len(seats) != 1:
        problems.append("leader spawner in the arena: %d (exactly one after the seat move)" % len(seats))
    old = s["hall_spawner"]
    if name_of(world.get(*old)) == "rctmod:trainer_spawner":
        problems.append("the hall spawner %s is still standing after the seat move" % (list(old),))
    if problems:
        facts["problems"] = problems
        return facts
    off = spawn_height_offset()
    TP, PP = mk["trainer_pokemon_position"][0], mk["player_pokemon_position"][0]
    PS = mk["player_stand_position"][0]
    seat = seats[0]

    # ---- bounds
    stray = sorted(c for c in arena_writes if not inside(c, bounds) and not any(inside(c, t) for t in through))
    facts["arena_cells_written"] = len(arena_writes)
    if stray:
        problems.append("BOUNDS: %d arena write(s) outside bounds and every through_building box, first %s"
                        % (len(stray), list(stray[0])))
    seat_writes = [c for c, l in world.layer.items() if l == "seat"]
    stray_seat = [c for c in seat_writes if not inside(c, bounds) and not inside(c, s["host_box"])
                  and not (s.get("template_box") and inside(c, s["template_box"]))]
    if stray_seat:
        problems.append("BOUNDS: the seat move writes %d cell(s) outside the arena and its host, first %s"
                        % (len(stray_seat), list(stray_seat[0])))

    # ---- shell
    leaks, sky = [], []
    for c in arena_writes:
        st = world.get(*c)
        if shape(st) == (0.0, 1.0, None):
            continue   # a full cube (glass included): neither a cave nor a fluid passes it
        x, y, z = c
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (x + d[0], y + d[1], z + d[2])
            if world.written(n):
                continue
            nat = world.nature(*n)
            if nat in (NAT, PAD):
                leaks.append((c, n))
            elif s["host_allows_natural_air"] and inside(n, s["host_box"]):
                continue
            else:
                sky.append((c, n, nat))
    facts["shell_leaks"] = len(leaks)
    facts["shell_leak_pairs"] = [[list(a_), list(b_)] for a_, b_ in sorted(leaks)[:60]]
    if leaks:
        problems.append("SHELL: %d open arena cell(s) beside unwritten rock (a cave can open there), first %s beside %s"
                        % (len(leaks), list(leaks[0][0]), list(leaks[0][1])))
    if sky:
        problems.append("SHELL: %d open arena cell(s) beside the world's own %s outside the host, first %s beside %s"
                        % (len(sky), sky[0][2], list(sky[0][0]), list(sky[0][1])))

    # ---- cover
    tops = {}
    for c in arena_writes:
        if any(inside(c, t) for t in through):
            continue
        tops[(c[0], c[2])] = max(tops.get((c[0], c[2]), -999), c[1])
    host_low = {}
    for c in host_cells:
        k = (c[0], c[2])
        host_low.setdefault(k, []).append(c[1])
    worst = None
    bare = []
    for (x, z), yt in tops.items():
        nt, exact = world.nature.natural_top(x, z)
        above = [y for y in host_low.get((x, z), []) if y > yt]
        if above and min(above) - 1 <= nt:
            nt, exact = min(above) - 1, True
        natural = nt - yt if exact else (nt - 1) - yt   # cells between, worst case
        if worst is None or natural < worst[0]:
            worst = (natural, (x, yt, z), nt, exact)
        if natural < 1:
            bare.append((x, yt, z, nt, exact))
    facts["cover_min"] = worst[0] if worst else None
    facts["cover_min_at"] = list(worst[1]) if worst else None
    if bare:
        b0 = bare[0]
        problems.append("COVER: %d column(s) with no natural block over the arena in the worst case, first (%d, %d, %d)"
                        " under a natural top at y%d (%s)" % (len(bare), b0[0], b0[1], b0[2], b0[3],
                                                              "exact" if b0[4] else "heightmap, may be one low"))

    # ---- reach, both ways
    start = None
    w_strict = Walker(world, box)
    rx, ry, rz = s["route_end"]
    start = w_strict.settle(rx, ry, rz)
    stand = (PS[0], PS[2], PS[1] + off)
    facts["route_end"] = list(s["route_end"])
    facts["challenger_stand"] = [PS[0], PS[1] + off, PS[2]]
    if start is None:
        problems.append("REACH: the route's end %s is not a cell a player can stand in" % (list(s["route_end"]),))
        down = set()
    else:
        down = w_strict.reach(start)
    if not w_strict.valid(*stand):
        problems.append("REACH: the challenger's stand %s is not a cell a player can stand in" % facts["challenger_stand"])
    facts["reach_down"] = stand in down
    up = w_strict.reach(stand) if w_strict.valid(*stand) else set()
    facts["reach_up"] = start in up if start else False
    crouch = Walker(world, box, body=1.5)
    if not facts["reach_down"]:
        w_dmg = Walker(world, box, fall=1e9)
        facts["reach_down_with_damage"] = start is not None and stand in w_dmg.reach(start)
        facts["reach_down_crouching"] = start is not None and stand in crouch.reach(start)
        problems.append("REACH: the challenger's stand %s is not reached walking upright from the route's end %s "
                        "without fall damage (with damage: %s; crouching: %s)%s"
                        % (facts["challenger_stand"], list(s["route_end"]), facts["reach_down_with_damage"],
                           facts["reach_down_crouching"], blocked_at(w_strict, crouch, start)))
    if not facts["reach_up"]:
        facts["reach_up_crouching"] = start is not None and start in crouch.reach(stand)
        problems.append("REACH: from the challenger's stand %s a player walking upright cannot get back to the "
                        "route's end %s (crouching: %s)" % (facts["challenger_stand"], list(s["route_end"]),
                                                            facts["reach_up_crouching"]))
    if start is not None and facts["reach_down"] and facts["reach_up"]:
        # the generator's own stairs promise a walk both ways WITHOUT a jump (tools/gym_arenas.py newel_stair: "every
        # step is then a stair's half-block front or level, never a full block's +1"). Held to the arena's part of
        # the way: from the challenger's stand, without jumping, back onto a floor the host (building or dig) wrote
        nj = Walker(world, box, jump=False)
        nj_set = nj.reach(stand)
        facts["reach_up_without_jump"] = start in nj_set
        host_floor = [n for n in nj_set if w_strict.support(*n) is not None
                      and w_strict.support(*n) in host_cells and w_strict.support(*n) not in arena_writes]
        facts["host_floor_without_jump"] = len(host_floor)
        if not host_floor:
            jumps = []
            for n in sorted(nj_set):
                for m, how in w_strict.moves(n):
                    if how == "jump" and m not in nj_set:
                        jumps.append((n, m))
            problems.append("STAIR: going up, no way off the arena's own descent onto the host's floor without a "
                            "jump; %d jump(s) at the edge, first %s" % (
                                len(jumps), ["%s -> %s" % (list(a), list(b)) for a, b in jumps[:2]]))
    leader_stand = (seat[0], seat[2], seat[1] + 1.0)
    facts["leader_stand_reachable"] = leader_stand in down
    if leader_stand in down:
        problems.append("REACH: a player can walk onto the leader's own stand %s" % [seat[0], seat[1] + 1, seat[2]])

    walk = down | up
    standing = [n for n in walk if w_strict.support(*n) is not None]

    def arena_cell(n):
        # a cell the arena made: its feet cell or the block under it written by the arena, inside its declared
        # boxes (the open sky beside a through_building box is the world's, lit by the sky)
        feet = (n[0], int(math.floor(n[2] + EPS)), n[1])
        sup = w_strict.support(*n)
        if not (inside(feet, bounds) or any(inside(feet, t) for t in through)):
            return False
        return feet in arena_writes or (sup is not None and sup in arena_writes)
    in_arena = [n for n in standing if arena_cell(n)]
    facts["walkable_cells"] = len(walk)
    facts["walkable_in_arena"] = len(in_arena)

    # ---- clearance
    size = size or leader_size(arch or Archives(), s["leader"])
    R, H = size["radius"], size["height"]
    facts["size"] = {"radius": round(R, 3), "radius_species": size["radius_species"], "height": round(H, 3),
                     "height_species": size["height_species"], "width": round(size["width"], 3),
                     "width_species": size["width_species"]}
    for label, M in (("trainer_pokemon", TP), ("player_pokemon", PP)):
        cx, cz = M[0] + 0.5, M[2] + 0.5
        feet = M[1] + off
        sup = world.get(M[0], int(math.floor(feet - EPS)), M[2])
        sh = shape(sup)
        if sh is None or abs(int(math.floor(feet - EPS)) + sh[1] - feet) > EPS:
            problems.append("CLEARANCE: %s at %s: nothing for its Pokemon to stand on at y%.1f (%s)"
                            % (label, list(M), feet, sup))
        hits, nearest = [], None
        ylo, yhi = int(math.floor(feet + EPS)), int(math.ceil(feet + H - EPS)) - 1
        for x in range(int(math.floor(cx - R)) - 4, int(math.ceil(cx + R)) + 4):
            for z in range(int(math.floor(cz - R)) - 4, int(math.ceil(cz + R)) + 4):
                ddx = max(x - cx, 0.0, cx - (x + 1))
                ddz = max(z - cz, 0.0, cz - (z + 1))
                d = math.hypot(ddx, ddz)
                for y in range(ylo, yhi + 1):
                    st = world.get(x, y, z)
                    sh = shape(st)
                    if sh is None:
                        continue
                    if y == ylo and sh[1] <= 0.0625 + EPS:
                        continue   # a carpet on the floor
                    if nearest is None or d < nearest[0]:
                        nearest = (d, (x, y, z), st)
                    if d < R - EPS:
                        hits.append(((x, y, z), round(d, 2), st))
                    break
        facts["%s_clear_slack" % label] = round(nearest[0] - R, 2) if nearest else None
        facts["%s_nearest" % label] = [list(nearest[1]), nearest[2]] if nearest else None
        if hits:
            hits.sort(key=lambda h: h[1])
            problems.append("CLEARANCE: %s %s: %d column(s) with a block within R %.2f (%s) up to y%d, nearest %s "
                            "at %.2f (%s)" % (label, list(M), len(hits), R, size["radius_species"], yhi,
                                              list(hits[0][0]), hits[0][1], hits[0][2]))
    gap = math.hypot(TP[0] - PP[0], TP[2] - PP[2])
    facts["pokemon_gap"] = round(gap, 2)
    if gap <= size["width"] + EPS:
        problems.append("CLEARANCE: the two Pokemon blocks are %.2f apart, inside the widest hitbox %.2f"
                        % (gap, size["width"]))

    # ---- fluids
    fbox = (box[0] - 8, box[1] - 4, box[2] - 8, box[3] + 8, box[4] + 4, box[5] + 8)
    wsrc, lsrc = [], []
    for x in range(fbox[0], fbox[3] + 1):
        for z in range(fbox[2], fbox[5] + 1):
            if world.nature.water_level(x, z):
                g = world.nature.column(x, z)[0]
                for y in range(g, world.nature.water_level(x, z) + 1):
                    if not world.written((x, y, z)) and world.nature(x, y, z) == NAT_WATER:
                        wsrc.append((x, y, z))
    for c, st in world.cells.items():
        if not inside(c, fbox):
            continue
        if is_water(st):
            wsrc.append(c)
        if is_lava(st):
            lsrc.append(c)
    wet = flow(world, fbox, wsrc, 7)
    hot = flow(world, fbox, lsrc, 3)
    arena_fluid = {c for c in arena_writes if is_water(world.get(*c))}
    arena_lava = {c for c in arena_writes if is_lava(world.get(*c))}
    in_ar = lambda c: inside(c, bounds) or any(inside(c, t) for t in through)
    flooded = sorted(c for c in wet if in_ar(c) and c not in arena_fluid)
    facts["water_sources"] = len(wsrc)
    facts["world_water_columns_near"] = getattr(world.nature.water_level, "wet", None)
    if flooded:
        problems.append("WATER: %d arena cell(s) a flow reaches that the arena did not write as water, first %s"
                        % (len(flooded), list(flooded[0])))
    spilled = sorted(c for c in hot if c not in arena_lava and in_ar(c))
    if spilled:
        problems.append("LAVA: %d cell(s) the arena's lava flows into, first %s" % (len(spilled), list(spilled[0])))
    facts["lava_cells"] = len(hot)

    # ---- hazards on the walk
    body = set()
    for (x, z, h) in walk:
        y0 = int(math.floor(h + EPS))
        for y in range(y0, int(math.floor(h + BODY - EPS)) + 1):
            body.add((x, y, z))
    exposed = []
    for c in hot:
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            if (c[0] + d[0], c[1] + d[1], c[2] + d[2]) in body:
                exposed.append(c)
                break
    if exposed:
        problems.append("HAZARD: %d lava cell(s) beside a cell a player's body occupies, first %s"
                        % (len(exposed), list(exposed[0])))
    hot_floor = []
    for n in standing:
        sup = w_strict.support(*n)
        if sup and name_of(world.get(*sup)) in ("minecraft:magma_block", "minecraft:campfire",
                                                 "minecraft:soul_campfire"):
            hot_floor.append(sup)
    if hot_floor:
        problems.append("HAZARD: %d walkable cell(s) on magma or a campfire, first %s"
                        % (len(hot_floor), list(hot_floor[0])))
    fire = []
    for c in hot:
        x, y, z = c
        if name_of(world.get(x, y + 1, z)) in AIRS:
            fire.append((c, "air over the lava"))
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                n = (x + dx, y, z + dz)
                if flammable(world.get(*n)) and name_of(world.get(x + dx, y + 1, z + dz)) in AIRS:
                    fire.append((c, "flammable %s at %s with air over it" % (name_of(world.get(*n)), list(n))))
    if fire:
        problems.append("HAZARD: lava that can start a fire: %d case(s), first %s: %s"
                        % (len(fire), list(fire[0][0]), fire[0][1]))
    facts["fire_cases"] = len(fire)

    # ---- light
    lbox = (box[0] - 15, box[1] - 15, box[2] - 15, box[3] + 15, box[4] + 15, box[5] + 15)
    lit = block_light(world, lbox)
    levels = []
    dark, spawnable = [], []
    for n in in_arena:
        c = (n[0], int(math.floor(n[2] + EPS)), n[1])
        v = lit.get(c, 0)
        levels.append(v)
        if v < 1:
            dark.append(c)
            # vanilla NaturalSpawner (ON_GROUND): the block under must have a sturdy top face; a bottom stair, a
            # bottom slab, a fence or a carpet's cell does not. A full cube, a top slab, an upside-down stair does.
            sup = w_strict.support(*n)
            sst = world.get(*sup) if sup else None
            ssh = shape(sst) if sst else None
            if ssh is not None and ssh[1] == 1.0 and ssh[2] is None and abs(n[2] - (sup[1] + 1)) < EPS:
                spawnable.append(c)
    levels.sort()
    facts["light"] = {"cells": len(levels), "min": levels[0] if levels else None,
                      "median": levels[len(levels) // 2] if levels else None, "dark": len(dark),
                      "dark_cells": [list(c) for c in sorted(dark)[:40]],
                      "dark_spawnable": [list(c) for c in sorted(spawnable)]}
    if spawnable:
        problems.append("LIGHT: %d walkable arena cell(s) at block light 0 on a sturdy top face (a monster can spawn "
                        "there), first %s; %d dark in all" % (len(spawnable), list(sorted(spawnable)[0]), len(dark)))
    lamps = [c for c, st in world.cells.items() if name_of(st) == "minecraft:redstone_lamp" and in_ar(c)]
    facts["redstone_lamps_in_arena"] = len(lamps)
    # a light source with an opaque block on all six sides lights nothing but its own cell
    buried = []
    for c in sorted(arena_writes):
        st = world.get(*c)
        if emission(st) and all(opaque(world.get(c[0] + d[0], c[1] + d[1], c[2] + d[2])) for d in (
                (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))):
            buried.append(list(c))
    facts["buried_lights"] = buried
    facts["problems"] = problems
    return facts


def compare_sizes(arch, gyms):
    """Each leader's measured size against GYM_ARENAS.md's table; a disagreement is a finding."""
    table = doc_table()
    out = {}
    for g in gyms:
        s = site(g)
        size = leader_size(arch, s["leader"])
        row = table.get(g)
        diffs = []
        if row is None:
            diffs.append("no row in GYM_ARENAS.md")
        else:
            members = sorted(size["members"])
            if members != row["members"]:
                diffs.append("members %s, the table %s" % (members, row["members"]))
            for key, mine, msp in (("widest", size["width"], size["width_species"]),
                                   ("radius", size["radius"], size["radius_species"]),
                                   ("height", size["height"], size["height_species"])):
                sp, val = row[key]
                # the table prints two decimals: anything past its rounding (0.005) is a disagreement
                if sp != msp or abs(val - mine) > 0.0051:
                    diffs.append("%s: measured %s %.2f, the table %s %.2f" % (key, msp, mine, sp, val))
            th = max(v["height"] for v in size["members"].values() if not v.get("missing"))
            tsp = [k for k, v in size["members"].items() if not v.get("missing") and v["height"] == th][0]
            if row["tallest"][0] != tsp or abs(row["tallest"][1] - th) > 0.01:
                diffs.append("tallest hitbox: measured %s %.2f, the table %s %.2f" % (tsp, th, *row["tallest"]))
        aspects = {k: v["aspects"] for k, v in size["members"].items() if v.get("aspects")}
        if aspects:
            diffs.append("members name aspects or forms: %s" % aspects)
        missing = [k for k, v in size["members"].items() if v.get("missing")]
        if missing:
            diffs.append("no species file in any server archive: %s" % missing)
        out[g] = {"size": size, "diffs": diffs}
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--gym", default=None)
    p.add_argument("--pack", default=str(ARENA_PACK))
    p.add_argument("--json", default=None, help="write every fact here; print only verdicts")
    a = p.parse_args(argv)
    import ground as ground_mod
    G = ground_mod.load()
    arch = Archives()
    gyms = [a.gym] if a.gym else GYMS
    sizes = compare_sizes(arch, gyms)
    report, rc = {}, 0
    for g in gyms:
        f = audit_gym(g, a.pack, G, arch, sizes[g]["size"])
        f["size_vs_doc"] = sizes[g]["diffs"]
        report[g] = f
        sz = f.get("size") or {}
        print("%s %s: down %s up %s (no jump %s); R %.2f %s H %.2f %s; slack T %s P %s; cover %s; light %s; lava %s"
              % (g, f["leader"], f.get("reach_down"), f.get("reach_up"), f.get("reach_up_without_jump"),
                 sz.get("radius", 0), sz.get("radius_species"), sz.get("height", 0), sz.get("height_species"),
                 f.get("trainer_pokemon_clear_slack"), f.get("player_pokemon_clear_slack"), f.get("cover_min"),
                 (f.get("light") or {}).get("min"), f.get("lava_cells")))
        for d in sizes[g]["diffs"]:
            print("   SIZE", d)
        for b in f["problems"]:
            print("   PROBLEM", b)
        rc = rc or (1 if f["problems"] else 0)
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1, default=lambda o: sorted(o) if isinstance(o, set)
                                           else str(o)) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
