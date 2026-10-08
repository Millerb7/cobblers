#!/usr/bin/env python
"""Independent audit of the gym juniors: every seat in data/gym_junior_trainers.json (26 on 2026-10-06), their rosters and the pack that carries them.

WHY THIS EXISTS. `tools/gym_trainers.py check` proves each seat over `tools/gym_buildings.py build_one()`'s voxel
model and gym 2's replay of `place_donor.commands()` / `gym_interiors.gym2_commands()` -- the generators' own
models -- and with its own movement graph, sight sets and cuts. Its tests share that derivation. This audit shares
none of it (CLAUDE.md, "How to prove an audit is independent"):

  the blocks     the EMITTED function text: build/datapacks/cobblers_gym_buildings (gyms 1, 3-8),
                 cobblers_donor place_gym2_misty_gym_go + cobblers_gym_interiors (gym 2), replayed by a fill /
                 setblock interpreter written here; gym 2's `place template` resolved by reading misty.nbt out
                 of COBBLEVERSE-DP-v31.zip with an NBT reader written here. Nothing from tools/gym_buildings.py,
                 tools/place_donor.py, tools/gym_interiors.py or tools/gym_trainers.py is imported.
  the ground     tools/ground.py, rounded (the canonical heightmap; CLAUDE.md "Ground comes from the heightmap")
                 for the ring of columns round each lot and gym 2's terrain under the template. Inside a gym
                 1/3-8 lot, everything at or below the lot level the function does not write is the pad: solid.
  the leaders    the trainer_spawner block found IN the replayed blocks (cross-checked against
                 data/gym_buildings/*.json leader.spawner and data/gym_interiors.json measured), its type from
                 the leader's own team in data/trainers.json read through Cobblemon's species data in the jar,
                 its ace the max of that team, capped by data/trainers.json generation_contract.gym_ace_levels.
  the seats      what reaches the game: tools/route_trainers.py placements() -- the (id, seat, yaw) list
                 tools/reapply.py R17 summons -- and the emitted pack's cycle.mcfunction home line and mob file
                 forceBattleMaxDistance. data/gym_junior_trainers.json is read only for `gym` and to compare.
  the movement   a walk model written here (below), seeded at the gym's door side, not from any route the
                 records declare.

THE MOVEMENT MODEL (one model; stated so a reader can disagree with it).
  position    a cell whose feet and head cells are passable (air-like, water, ladder, scaffolding) with a floor
              under it (a solid or tall block, or scaffolding), or a feet cell that is water, ladder or
              scaffolding.
  walk        to a 4-neighbour at the same level, or up one (onto a solid block, with headroom over the player;
              never up onto a fence/wall top, which is 1.5 high), or off an edge: the player falls straight down
              the column to the first position. Falls of any height are allowed (no fall damage is modelled, which
              can only add routes).
  jump        across a gap at most ONE block wide (the stated model): 2 cells along an axis, landing level, one
              up, or any distance down; or 1 diagonal cell over a missing corner with both sides open. The flight
              cells (each gap column's feet, head and the cell above, and the cell over the jumper's head) must be
              passable. When NO arrival reaches the leader with gaps of one, the hall's own way needs a wider
              jump: the gap is widened to 2, then 3 (level or down only), the hall is judged at the narrowest gap
              that reaches its leader, and the report says so. (Gyms 3 and 4 need a gap of 2.)
  climb       up and down within ladder / vine / scaffolding columns, and down through scaffolding stood on.
  swim        up and down through water, and every walk move out of water.
  partial     slabs, stairs, trapdoors and furniture are full blocks (a bottom slab is a step of 0.5, which the
  blocks      model allows as a step of 1 anyway). Fences, walls, panes, bars and gates are TALL: solid,
              standable, never stepped up onto. Carpets, pressure plates, buttons, signs, banners, torches,
              lanterns, chains, flowers and grass are air; doors are air (they open); a waterlogged plant or coral
              is water. An unknown block name fails closed (a [blocks] problem).
  arrival     gyms 1, 3-8: every position on a ring of 3 columns round the lot at the heightmap ground, and every
              ground position inside the lot but outside the hall's footprint (the forecourt the door opens
              onto). Gym 2: the ring (no forecourt: the template box is the footprint); see D1 below.
  the leader  engaged from a position whose feet are within 3.0 of the leader's feet (spawner + 1) with a clear
              line from the player's eye (1.62) to the leader's chest (1.0).
  the junior  its two body cells are never walked through: a walk that touches the junior has passed it.

THE SIGHT. rctmod's ForceIntoBattleGoal fires within the mob file's forceBattleMaxDistance; the builder relays that
the distance test passes walls (docs/mechanics/GYM_INTERIORS.md section 3; NOT verified here). The goal's constant
pool names ProjectileUtil / EntityHitResult and lookAt fields (rctmod-fabric-1.21.1-0.19.0-beta.jar), which reads
as the PLAYER's look ray hitting the trainer -- so the trainer's own yaw probably does not gate the trigger (not
verified). Hence two tests:
  distance    "surely seen" = 3-D distance from the player's cell centre to the junior's feet <= sight - U, in any
              direction. U = 0.87 = sqrt(3 * 0.5^2): a player's feet are anywhere in the 1x1 cell and up to half a
              block lower on a slab, so the cell's far corner is U from its centre. A walk outside it FAILS
              [must_pass].
  facing      the same, and the cell's centre at least sqrt(2)/2 in front of the yaw's line (the whole cell in
              front; yaw 0 faces +z, 90 faces -x). A walk that passes within distance only beside or behind the
              junior is a WARNING [facing] (a failure with --strict-facing): the runtime evidence above says the
              yaw may not matter, and a pinned trainer's head turns.
  possibly    distance <= sight + U, any direction, through walls: used for what must NOT be caught.

CHECKS (codes; each problem is one line):
  seat        the seat is a dry position on solid footing with two open cells inside the hall's footprint,
              reachable; no two juniors share a body cell; none on another R17 trainer's seat or the leader's
              stand [seat]
  home        the emitted cycle.mcfunction sends the junior home to the seat R17 summons it at [home]
  sight       the mob file exists and forceBattleOnSight is true [sight]
  must_pass   with every position (and jump flight / fall cell) the junior surely sees removed, and its body
              cells, no arrival reaches the leader [must_pass]
  sight line  the must_pass cut again, counting only cells with a clear line from the player's eye to the junior
              (feet + 0.5, 1.0 or 1.5): rctmod-server.toml says trainer and player "look at each other", so a cut
              that holds only through a block is a WARNING [line_of_sight] (a failure with --strict-sight)
  softlock    with the junior's two body cells blocked, some arrival still reaches the leader [softlock]; and with
              EVERY junior's body cells blocked at once, as R17 summons them [softlock, the gym named]
  walled_in   with every junior standing, no position a player can reach has its only way back to an arrival
              through a junior's body (moves are one-way across a fall, so the way out is its own backward search;
              the hall's own one-way drops, there with nobody standing, are a note) [walled_in]
  leader      no position the junior possibly sees engages the leader [leader]; the spawner is found in the
              replayed blocks where the record says, and the leader's team tops out at the contract's ace
  order       ordering the juniors by the fewest moves before a player is surely in each one's sight (facing
              included), top levels never fall [order]
  roster      a Normal and a Challenge payload (`<id>_challenge` identity) in data/trainers.json, the same teams
              in the emitted pack's trainer files, both mob and dialog files and the advancement; every member at
              or below the leader's ace (the leader's own top level, capped by gym_ace_levels); Challenge top ==
              Normal top; every member's types (jar species data) include the leader's type (the majority type
              of the leader's own team) or the record's type_theme, and the theme is the leader's type; every move
              in the species' learnset; every heldItem a Cobblemon item; the skin in the rctmod jar [roster]
  other       no other R17 trainer seated inside a gym's lot [other_trainer]
  apart       positions surely in two juniors' sight (a note, not a failure)

D1 (gym 2's well, a KNOWN defect): gym 2 is walked as built on foot (reported as notes, never a failure), then
with data/gym_junior_trainers.json assume_closed sealed: on foot (a note: can a walker still reach Misty?) and with
every position open to the sky inside the lot added to the arrivals, because Misty's island floats. The checks
are judged on that last walk. Whether the 21 cells are still open as built is reported.

D3 (flight, information): for gyms 1 and 3-8 the walk is repeated with sky arrivals and the juniors a rider avoids
(and a walker does not) are named in a note.

WHAT THIS DOES NOT COVER: rctmod's real sight test (direction, walls, the 30-tick stare: D4); what other packs write
into the halls after the gym buildings (only other R17 trainers' seats are swept, not other packs' blocks); the
leader's own 16-block forced battle (D2); the junior actually summoned, facing its yaw, and battling. Those are an
experiment in a running server.

Run:  python tools/gym_trainers_audit.py [--gym gymN] [--strict-facing] [--build DIR] [--json out.json]
      exit 0 clean, 1 on a problem, 2 when an input is missing
"""
from __future__ import annotations

import argparse
import glob
import gzip
import io
import json
import math
import os
import re
import struct
import sys
import zipfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

SNAPSHOTS = "C:/Users/wnd/Documents/cobblers-local/server-snapshot-*"
GYMS = ("gym1", "gym2", "gym3", "gym4", "gym5", "gym6", "gym7", "gym8")
U = math.sqrt(3 * 0.25)          # a player's feet anywhere in the cell, up to a half block higher on a slab
FRONT = math.sqrt(2) / 2         # the cell's whole horizontal extent in front of the yaw's line
ENGAGE = 3.0                     # survival interaction reach
EYE = 1.62
RING = 3                         # heightmap columns round each lot


# ------------------------------------------------------------------------------------------------ inputs
def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def snapshots():
    return sorted(glob.glob(SNAPSHOTS), reverse=True)


def pack_dir(name, build=None):
    """The emitted pack: --build / COBBLERS_BUILD_DIR, this checkout's build/, then the newest server snapshot."""
    cands = []
    for b in (build, os.environ.get("COBBLERS_BUILD_DIR")):
        if b:
            cands.append(Path(b) / "datapacks" / name)
    cands.append(ROOT / "build" / "datapacks" / name)
    cands += [Path(s) / "datapacks" / name for s in snapshots()]
    for c in cands:
        if c.is_dir():
            return c
    return None


def donor_zip():
    cands = [os.environ.get("COBBLERS_DONOR_ZIP"), str(ROOT / "build" / "cobbleverse" / "COBBLEVERSE-DP-v31.zip")]
    cands += [s + "/datapacks/COBBLEVERSE-DP-v31.zip" for s in snapshots()]
    for c in cands:
        if c and Path(c).is_file():
            return c
    return None


def jar(prefix):
    dirs = [os.environ.get("COBBLERS_JAR_DIR")] + [s + "/mods" for s in snapshots()]
    for d in dirs:
        if d and Path(d).is_dir():
            hits = sorted(glob.glob(str(Path(d) / (prefix + "*.jar"))))
            if hits:
                return hits[-1]
    return None


def inputs_missing(build=None):
    """Names of the inputs this audit cannot run without (tests skip on them, the CLI fails on them)."""
    out = []
    for p in ("cobblers_gym_buildings", "cobblers_gym_interiors", "cobblers_donor", "cobblers_trainers"):
        if not pack_dir(p, build):
            out.append("pack " + p)
    if not donor_zip():
        out.append("COBBLEVERSE-DP-v31.zip")
    for j in ("Cobblemon-fabric", "rctmod-fabric"):
        if not jar(j):
            out.append("jar " + j)
    import terrain
    if not terrain.env_source_root():
        out.append("heightmap (COBBLERS_SOURCE_ROOT)")
    return out


# ------------------------------------------------------------------------------------------------ NBT
def _nbt(buf, t):
    """One tag payload of type t from the stream (Java NBT, big-endian)."""
    def rd(fmt):
        n = struct.calcsize(fmt)
        return struct.unpack(fmt, buf.read(n))[0]
    if t == 1:
        return rd(">b")
    if t == 2:
        return rd(">h")
    if t == 3:
        return rd(">i")
    if t == 4:
        return rd(">q")
    if t == 5:
        return rd(">f")
    if t == 6:
        return rd(">d")
    if t == 7:
        return buf.read(rd(">i"))
    if t == 8:
        return buf.read(rd(">H")).decode("utf-8")
    if t == 9:
        et, n = rd(">b"), rd(">i")
        return [_nbt(buf, et) for _ in range(n)]
    if t == 10:
        out = {}
        while True:
            ct = rd(">b")
            if ct == 0:
                return out
            name = buf.read(rd(">H")).decode("utf-8")
            out[name] = _nbt(buf, ct)
    if t == 11:
        return [rd(">i") for _ in range(rd(">i"))]
    if t == 12:
        return [rd(">q") for _ in range(rd(">i"))]
    raise ValueError("NBT tag type %d" % t)


def read_nbt(data):
    raw = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
    buf = io.BytesIO(raw)
    t = struct.unpack(">b", buf.read(1))[0]
    buf.read(struct.unpack(">H", buf.read(2))[0])
    return _nbt(buf, t)


def template(zpath, ident):
    """{(dx, dy, dz): state} for every block the template places (structure voids are absent), and its size."""
    ns, path = ident.split(":", 1)
    with zipfile.ZipFile(zpath) as z:
        root = read_nbt(z.read("data/%s/structure/%s.nbt" % (ns, path)))
    pal = []
    for p in root["palette"]:
        props = p.get("Properties") or {}
        pal.append(p["Name"] + ("[%s]" % ",".join("%s=%s" % kv for kv in sorted(props.items())) if props else ""))
    return {tuple(b["pos"]): pal[b["state"]] for b in root["blocks"]}, tuple(root["size"])


# ------------------------------------------------------------------------------------------------ the replay
def bare(state):
    return state.split("[", 1)[0].split("{", 1)[0]


class World:
    """Cells written by fill / setblock / place template over a base function."""

    def __init__(self, base):
        self.base, self.cells = base, {}

    def at(self, x, y, z):
        s = self.cells.get((x, y, z))
        return s if s is not None else self.base(x, y, z)

    def fill(self, a, b, state, mode=None, filt=None):
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        z0, z1 = sorted((a[2], b[2]))
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    edge = x in (x0, x1) or y in (y0, y1) or z in (z0, z1)
                    if mode == "replace" and filt is not None:
                        if bare(self.at(x, y, z)) != bare(filt):
                            continue
                    elif mode == "keep":
                        if bare(self.at(x, y, z)) not in ("minecraft:air", "minecraft:cave_air"):
                            continue
                    elif mode == "hollow" and not edge:
                        self.cells[(x, y, z)] = "minecraft:air"
                        continue
                    elif mode == "outline" and not edge:
                        continue
                    self.cells[(x, y, z)] = state

    def run(self, line, templates=None):
        """One command line. Returns the verb it understood, or None for one it skipped."""
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        p = line.split()
        if p[0] == "setblock":
            self.cells[(int(p[1]), int(p[2]), int(p[3]))] = p[4]
            return "setblock"
        if p[0] == "fill":
            st = p[7]
            mode = p[8] if len(p) > 8 else None
            filt = p[9] if len(p) > 9 else None
            self.fill(tuple(int(v) for v in p[1:4]), tuple(int(v) for v in p[4:7]), st, mode, filt)
            return "fill"
        if p[0] == "place" and p[1] == "template":
            rot = p[6] if len(p) > 6 else "none"
            mir = p[7] if len(p) > 7 else "none"
            integ = float(p[8]) if len(p) > 8 else 1.0
            if rot != "none" or mir != "none" or integ != 1.0:
                raise SystemExit("place template %s: rotation/mirror/integrity this audit does not model: %s"
                                 % (p[2], line))
            cells, _size = templates[p[2]]
            ox, oy, oz = int(p[3]), int(p[4]), int(p[5])
            for (dx, dy, dz), st in cells.items():
                self.cells[(ox + dx, oy + dy, oz + dz)] = st
            return "place"
        if p[0] in ("forceload", "schedule", "kill", "tp", "tellraw", "say", "data", "scoreboard", "execute",
                    "function", "summon", "gamerule", "title"):
            return None
        raise SystemExit("unknown command in a replayed function: %s" % line[:120])

    def run_file(self, path, templates=None):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            self.run(line, templates)


# ------------------------------------------------------------------------------------------------ blocks
AIR, SOLID, TALL, WATER, CLIMB, SCAF = "air", "solid", "tall", "water", "climb", "scaf"
PASSABLE = (AIR, WATER, CLIMB, SCAF)

AIR_NAMES = {
    "air", "cave_air", "void_air", "light", "structure_void", "torch", "wall_torch", "soul_torch", "soul_wall_torch",
    "redstone_torch", "redstone_wall_torch", "lantern", "soul_lantern", "chain", "rail", "powered_rail",
    "detector_rail", "activator_rail", "redstone_wire", "tripwire", "tripwire_hook", "lever", "short_grass",
    "grass", "tall_grass", "fern", "large_fern", "dead_bush", "dandelion", "poppy", "blue_orchid", "allium",
    "azure_bluet", "red_tulip", "orange_tulip", "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower",
    "lily_of_the_valley", "wither_rose", "sunflower", "lilac", "rose_bush", "peony", "torchflower",
    "pink_petals", "sugar_cane", "cobweb", "glow_lichen", "sculk_vein", "moss_carpet", "brown_mushroom",
    "red_mushroom", "crimson_roots", "warped_roots", "nether_sprouts", "hanging_roots", "spore_blossom",
    "cave_vines", "cave_vines_plant", "weeping_vines", "weeping_vines_plant", "twisting_vines",
    "twisting_vines_plant", "item_frame", "painting", "snow", "lily_pad", "end_rod", "candle", "sweet_berry_bush",
    "small_dripleaf", "pitcher_plant", "nether_portal", "fire", "soul_fire", "string", "ladder_air",
}
AIR_SUFFIX = ("_carpet", "_pressure_plate", "_button", "_sign", "_wall_sign", "_hanging_sign", "_wall_hanging_sign",
              "_banner", "_wall_banner", "_door", "_sapling", "_candle", "_coral_fan", "_coral_wall_fan", "_coral",
              "_tulip", "_head", "_wall_head", "_skull", "_wall_skull")
WATER_NAMES = {"water", "bubble_column", "seagrass", "tall_seagrass", "kelp", "kelp_plant"}
CLIMB_NAMES = {"ladder", "vine"}
TALL_SUFFIX = ("_fence", "_fence_gate", "_pane", "_wall")
TALL_NAMES = {"iron_bars", "glass_pane"}
SOLID_SUFFIX = (
    "_planks", "_log", "_wood", "_stem", "_hyphae", "_bricks", "_stairs", "_slab", "_block", "_concrete",
    "_concrete_powder", "_terracotta", "_ore", "_glass", "_wool", "_leaves", "_trapdoor", "_tiles", "_bed",
    "_shulker_box", "_lamp", "_texture", "_stone", "_sandstone", "_deepslate", "_basalt", "_copper", "_pillar",
    "_ice", "_nylium", "_froglight", "_cauldron", "_anvil", "_table", "_chest", "_mosaic", "_quartz", "_prismarine",
    "_coral_block", "_mud", "_rock", "_shelf", "_cabinet", "_crate", "_counter", "_drawer", "_chair", "_bench",
    "_desk", "_sofa", "_couch", "_stool", "_lectern", "_barrel", "_box", "_cupboard", "_wardrobe", "_nightstand",
    "_grate",
)
SOLID_NAMES = {
    "stone", "granite", "diorite", "andesite", "deepslate", "cobblestone", "dirt", "coarse_dirt", "rooted_dirt",
    "grass_block", "podzol", "mycelium", "dirt_path", "farmland", "mud", "clay", "sand", "red_sand", "gravel",
    "sandstone", "red_sandstone", "calcite", "tuff", "dripstone_block", "obsidian", "crying_obsidian", "bedrock",
    "netherrack", "basalt", "blackstone", "glowstone", "sea_lantern", "prismarine", "dark_prismarine",
    "bookshelf", "chiseled_bookshelf", "chest", "trapped_chest", "barrel", "lectern", "crafting_table", "furnace",
    "blast_furnace", "smoker", "anvil", "chipped_anvil", "damaged_anvil", "grindstone", "stonecutter", "loom",
    "cartography_table", "fletching_table", "smithing_table", "composter", "cauldron", "water_cauldron",
    "brewing_stand", "enchanting_table", "jukebox", "note_block", "beehive", "bee_nest", "hopper", "dispenser",
    "dropper", "observer", "piston", "sticky_piston", "target", "tnt", "glass", "tinted_glass", "ice", "packed_ice",
    "blue_ice", "snow_block", "pumpkin", "carved_pumpkin", "jack_o_lantern", "melon", "hay_block", "sponge",
    "wet_sponge", "magma_block", "soul_sand", "soul_soil", "bone_block", "scaffolding_solid", "flower_pot",
    "decorated_pot", "campfire", "soul_campfire", "bell", "spawner", "trial_spawner", "vault", "copper_grate",
    "iron_door", "moss_block", "terracotta", "quartz_block", "smooth_stone", "smooth_quartz", "smooth_sandstone",
    "smooth_red_sandstone", "purpur_block", "end_stone", "amethyst_block", "budding_amethyst", "reinforced_deepslate",
    "lodestone", "respawn_anchor", "conduit", "beacon", "cobweb_solid", "dried_kelp_block", "honeycomb_block",
    "slime_block", "honey_block", "packed_mud", "muddy_mangrove_roots", "mangrove_roots", "cobbled_deepslate",
    "polished_deepslate", "chiseled_deepslate", "cracked_deepslate_tiles", "polished_tuff", "chiseled_tuff",
    "iron_block", "gold_block", "diamond_block", "emerald_block", "lapis_block", "redstone_block", "coal_block",
    "copper_block", "raw_iron_block", "raw_copper_block", "raw_gold_block", "netherite_block", "ancient_debris",
    "nether_wart_block", "warped_wart_block", "shroomlight", "crimson_nylium", "warped_nylium", "mossy_cobblestone",
    "infested_stone", "suspicious_sand", "suspicious_gravel", "big_dripleaf", "pointed_dripstone", "lantern_solid",
    "barrier", "command_block", "structure_block", "jigsaw", "sculk", "sculk_sensor", "sculk_catalyst",
    "sculk_shrieker", "calibrated_sculk_sensor", "crafter", "heavy_core", "dragon_egg", "cake", "daylight_detector",
    "comparator", "repeater", "end_portal_frame", "lightning_rod", "armor_stand", "chorus_plant", "chorus_flower",
    "cactus", "bamboo", "sniffer_egg", "turtle_egg", "frogspawn", "sea_pickle", "brown_mushroom_block",
    "red_mushroom_block", "mushroom_stem", "cut_sandstone", "cut_red_sandstone", "chiseled_sandstone",
    "chiseled_red_sandstone", "chiseled_quartz_block", "quartz_pillar", "quartz_bricks", "purpur_pillar",
    "gilded_blackstone", "chiseled_polished_blackstone", "cracked_polished_blackstone_bricks", "polished_basalt",
    "smooth_basalt", "polished_granite", "polished_diorite", "polished_andesite", "polished_blackstone",
    "chiseled_stone_bricks", "cut_copper", "exposed_copper", "weathered_copper", "oxidized_copper", "waxed_cut_copper",
}
# mod blocks seen in the halls, each checked by hand against its model's collision (all full or furniture-tall)
SOLID_MODDED_NS = {"moarconcrete", "rechiseled", "cobblemon", "rctmod", "handcrafted", "beautify", "cozy_home",
                   "cobblefurnies", "carvedwood", "pokeblocks", "vanillabackport", "mega_showdown",
                   "legendarymonuments", "lumymon", "waystones", "comforts",
                   # gym 2's three battle-position markers sit in the floor UNDER a stair or a block (y130-131),
                   # so whatever their collision they are never stood in; the storage barrel is a full block
                   "cobblemonbattlepositions", "sophisticatedstorage"}


class UnknownBlock(Exception):
    pass


def classify(state):
    k = _classify(state)
    # a waterlogged plant or coral is water to a swimmer; a waterlogged stair or slab is still a block
    if k == AIR and "waterlogged=true" in state:
        return WATER
    return k


def _classify(state):
    name = bare(state)
    ns, _, path = name.partition(":") if ":" in name else ("minecraft", "", name)
    if ns != "minecraft" and path.endswith(("_carpet", "_pressure_plate", "_button")):
        return AIR
    if ns == "minecraft":
        if path == "scaffolding":
            return SCAF
        if path in WATER_NAMES:
            return WATER
        if path in CLIMB_NAMES:
            return CLIMB
        if path in TALL_NAMES or (path.endswith(TALL_SUFFIX) and not path.endswith(("_wall_torch", "_wall_sign",
                                                                                    "_wall_banner", "_wall_head",
                                                                                    "_wall_skull",
                                                                                    "_wall_hanging_sign",
                                                                                    "_coral_wall_fan"))):
            return TALL
        if path in AIR_NAMES or path.endswith(AIR_SUFFIX):
            if path.endswith("_door") and path == "iron_door":
                return SOLID
            return AIR
        if path in SOLID_NAMES or path.endswith(SOLID_SUFFIX):
            return SOLID
        raise UnknownBlock(name)
    if ns == "cobblemon" and path.endswith(("_sapling", "_flower", "_mint", "_seeds")):
        return AIR
    if ns in SOLID_MODDED_NS:
        return SOLID
    raise UnknownBlock(name)


# ------------------------------------------------------------------------------------------------ the halls
class Hall:
    """The voxels of one gym, its arrival positions, its leader and its footprint."""

    def __init__(self, gym, world, box, lot, footprint, spawner, arrival, sky=False):
        self.gym, self.world, self.lot, self.footprint = gym, world, lot, footprint
        self.x0, self.y0, self.z0, self.x1, self.y1, self.z1 = box
        self.spawner = spawner
        self.leader = (spawner[0], spawner[1] + 1, spawner[2]) if spawner else None
        self.arrival_rule, self.sky = arrival, sky
        self.override = {}
        self._cls = {}
        self.unknown = set()

    def cls(self, x, y, z):
        c = (x, y, z)
        o = self.override.get(c)
        if o is not None:
            return o
        if not (self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1) or y > self.y1:
            return AIR if y > self.y1 else SOLID
        if y < self.y0:
            return SOLID
        k = self._cls.get(c)
        if k is None:
            st = self.world.at(x, y, z)
            try:
                k = classify(st)
            except UnknownBlock as e:
                self.unknown.add(str(e))
                k = SOLID
            self._cls[c] = k
        return k

    def inside(self, x, z, rect):
        return rect[0] <= x <= rect[2] and rect[1] <= z <= rect[3]


def gym_record(gym):
    return load(ROOT / "data" / "gym_buildings" / ("%s.json" % gym))


def building_hall(gym, G, build=None):
    """Gyms 1, 3-8: the lot's pad, the emitted gym function and the healer sweep, replayed."""
    rec = gym_record(gym)
    lot = tuple(rec["site"]["lot_rect"])
    level = int(rec["site"]["lot_level"])
    ring = {}
    for x in range(lot[0] - RING, lot[2] + RING + 1):
        for z in range(lot[1] - RING, lot[3] + RING + 1):
            if not (lot[0] <= x <= lot[2] and lot[1] <= z <= lot[3]):
                ring[(x, z)] = G(x, z)

    def base(x, y, z):
        if lot[0] <= x <= lot[2] and lot[1] <= z <= lot[3]:
            return "minecraft:stone" if y <= level else "minecraft:air"
        return "minecraft:stone" if y <= ring.get((x, z), level) else "minecraft:air"

    w = World(base)
    fdir = pack_dir("cobblers_gym_buildings", build) / "data" / "cobblers" / "function" / "gym_buildings"
    w.run_file(fdir / ("%s.mcfunction" % gym))
    idir = pack_dir("cobblers_gym_interiors", build) / "data" / "cobblers" / "function" / "gym_interiors"
    w.run_file(idir / "healers.mcfunction")
    inlot = [c for c in w.cells if lot[0] <= c[0] <= lot[2] and lot[1] <= c[2] <= lot[3]]
    stray = sorted(c for c in w.cells if not (lot[0] <= c[0] <= lot[2] and lot[1] <= c[2] <= lot[3]))
    top = max([c[1] for c in inlot] + list(ring.values())) + 4
    bot = min([c[1] for c in inlot] + [level] + list(ring.values())) - 3
    box = (lot[0] - RING, bot, lot[1] - RING, lot[2] + RING, top, lot[3] + RING)
    spawners = [c for c in inlot if bare(w.cells[c]) == "rctmod:trainer_spawner"]
    h = Hall(gym, w, box, lot, tuple(rec["site"]["footprint"]), None, "foot")
    h.level, h.ring, h.declared_spawner = level, ring, tuple(rec["leader"]["spawner"])
    h.spawners = spawners
    h.stray = stray
    h.spawner = h.declared_spawner if h.declared_spawner in spawners else (spawners[0] if spawners else None)
    if h.spawner:
        h.leader = (h.spawner[0], h.spawner[1] + 1, h.spawner[2])
    return h


def misty_hall(G, build=None):
    """Gym 2: the donor function (place template + substitutions + plinth), the healer sweep, the gym 2 dig."""
    ddir = pack_dir("cobblers_donor", build) / "data" / "cobblers" / "function" / "structures"
    go = (ddir / "place_gym2_misty_gym_go.mcfunction").read_text(encoding="utf-8")
    m = re.search(r"^place template (\S+) (-?\d+) (-?\d+) (-?\d+)", go, re.M)
    ident, px, py, pz = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
    cells, size = template(donor_zip(), ident)
    sx, sy, sz = size
    lot = (px, pz, px + sx - 1, pz + sz - 1)
    ring = {}
    for x in range(lot[0] - RING, lot[2] + RING + 1):
        for z in range(lot[1] - RING, lot[3] + RING + 1):
            ring[(x, z)] = G(x, z)

    def base(x, y, z):
        return "minecraft:stone" if y <= ring.get((x, z), -999) else "minecraft:air"

    w = World(base)
    w.run_file(ddir / "place_gym2_misty_gym_go.mcfunction", {ident: (cells, size)})
    idir = pack_dir("cobblers_gym_interiors", build) / "data" / "cobblers" / "function" / "gym_interiors"
    w.run_file(idir / "healers.mcfunction")
    w.run_file(idir / "gym2.mcfunction")
    inlot = [c for c in w.cells if lot[0] <= c[0] <= lot[2] and lot[1] <= c[2] <= lot[3]]
    top = py + sy + 4
    bot = min([c[1] for c in inlot] + list(ring.values())) - 3
    box = (lot[0] - RING, bot, lot[1] - RING, lot[2] + RING, top, lot[3] + RING)
    spawners = [c for c in inlot if bare(w.cells[c]) == "rctmod:trainer_spawner"]
    rel = load(ROOT / "data" / "gym_interiors.json")["measured"]["misty_relative"]["trainer_spawner"]
    h = Hall("gym2", w, box, lot, lot, None, "foot+sky", sky=True)
    h.level, h.ring = None, ring
    h.declared_spawner = (px + rel[0], py + rel[1], pz + rel[2])
    h.spawners, h.stray = spawners, []
    h.spawner = h.declared_spawner if h.declared_spawner in spawners else (spawners[0] if spawners else None)
    if h.spawner:
        h.leader = (h.spawner[0], h.spawner[1] + 1, h.spawner[2])
    h.template_origin = (px, py, pz)
    return h


def hall(gym, G, build=None):
    return misty_hall(G, build) if gym == "gym2" else building_hall(gym, G, build)


# ------------------------------------------------------------------------------------------------ movement
def passable(h, x, y, z):
    return h.cls(x, y, z) in PASSABLE


def is_pos(h, x, y, z):
    f = h.cls(x, y, z)
    if f not in PASSABLE or not passable(h, x, y + 1, z):
        return False
    if f in (WATER, CLIMB, SCAF):
        return True
    return h.cls(x, y - 1, z) in (SOLID, TALL, SCAF)


def land(h, x, y, z, limit=80):
    """Falling from feet cell (x, y, z) (passable): the first position at or below it, and the cells passed."""
    passed = []
    for yy in range(y, max(h.y0, y - limit) - 1, -1):
        if not passable(h, x, yy, z):
            return None, passed
        if is_pos(h, x, yy, z):
            return (x, yy, z), passed
        passed.append((x, yy, z))
    return None, passed


DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def moves(h, p, gap=1):
    """[(q, swept)]: every move out of position p, with the cells the body passes through on the way (other than
    q's own feet and head)."""
    x, y, z = p
    here = h.cls(x, y, z)
    out = []
    head2 = passable(h, x, y + 2, z)
    # climb and swim vertically
    if here in (CLIMB, SCAF, WATER):
        if is_pos(h, x, y + 1, z):
            out.append(((x, y + 1, z), ()))
        if passable(h, x, y - 1, z) and is_pos(h, x, y - 1, z):
            out.append(((x, y - 1, z), ()))
    if here == AIR and h.cls(x, y - 1, z) in (SCAF,) and is_pos(h, x, y - 1, z):
        out.append(((x, y - 1, z), ()))       # down through the scaffolding stood on (sneak)
    for dx, dz in DIRS:
        nx, nz = x + dx, z + dz
        if is_pos(h, nx, y, nz):
            out.append(((nx, y, nz), ()))
        elif passable(h, nx, y, nz) and passable(h, nx, y + 1, nz):
            q, passed = land(h, nx, y - 1, nz)
            if q:
                out.append((q, tuple([(nx, y, nz)] + passed)))
        # step up one: onto a solid (never a tall) block, with headroom over the player for the hop
        if head2 and h.cls(nx, y, nz) == SOLID and is_pos(h, nx, y + 1, nz):
            out.append(((nx, y + 1, nz), ((x, y + 2, z),)))
        # a jump over a gap up to `gap` wide (a gap of one may land a block higher; a wider one level or lower)
        if not head2:
            continue
        sweep = [(x, y + 2, z)]
        for k in range(1, gap + 1):
            mx, mz = x + k * dx, z + k * dz
            mid = [(mx, y, mz), (mx, y + 1, mz), (mx, y + 2, mz)]
            if not all(passable(h, *c) for c in mid) or is_pos(h, mx, y, mz):
                break
            sweep += mid
            fx, fz = x + (k + 1) * dx, z + (k + 1) * dz
            sw = tuple(sweep)
            if is_pos(h, fx, y, fz):
                out.append(((fx, y, fz), sw))
            elif k == 1 and h.cls(fx, y, fz) == SOLID and is_pos(h, fx, y + 1, fz):
                out.append(((fx, y + 1, fz), sw))
            elif passable(h, fx, y, fz) and passable(h, fx, y + 1, fz):
                q, passed = land(h, fx, y - 1, fz)
                if q:
                    out.append((q, sw + ((fx, y, fz),) + tuple(passed)))
    # a diagonal hop over a missing corner: both sides open for the body
    for dx in (1, -1):
        for dz in (1, -1):
            a, b, f = (x + dx, z), (x, z + dz), (x + dx, z + dz)
            side = [(a[0], y, a[1]), (a[0], y + 1, a[1]), (b[0], y, b[1]), (b[0], y + 1, b[1])]
            if not all(passable(h, *c) for c in side):
                continue
            if is_pos(h, f[0], y, f[1]):
                out.append(((f[0], y, f[1]), tuple(side)))
            elif passable(h, f[0], y, f[1]) and passable(h, f[0], y + 1, f[1]):
                q, passed = land(h, f[0], y - 1, f[1])
                if q:
                    out.append((q, tuple(side) + ((f[0], y, f[1]),) + tuple(passed)))
    return out


class Graph:
    """Every position reachable from the arrival set, with its moves."""

    def __init__(self, h, arrivals, gap=1):
        self.h, self.arrivals = h, list(dict.fromkeys(arrivals))
        self.adj = {}
        todo = deque(self.arrivals)
        seen = set(self.arrivals)
        while todo:
            p = todo.popleft()
            ms = moves(h, p, gap)
            self.adj[p] = ms
            for q, _s in ms:
                if q not in seen and h.x0 <= q[0] <= h.x1 and h.z0 <= q[2] <= h.z1:
                    seen.add(q)
                    todo.append(q)

    def bfs(self, ok_pos=None, ok_move=None, goal=None):
        """Distances from the arrival set over the positions ok_pos admits and the moves ok_move admits. Stops at
        the first goal position if one is given; returns (dist, parent, goal reached or None)."""
        dist, parent = {}, {}
        todo = deque()
        for a in self.arrivals:
            if a in self.adj and (ok_pos is None or ok_pos(a)):
                dist[a] = 0
                parent[a] = None
                todo.append(a)
        while todo:
            p = todo.popleft()
            if goal is not None and p in goal:
                return dist, parent, p
            for q, sw in self.adj.get(p, ()):
                if q in dist or q not in self.adj:
                    continue
                if ok_pos is not None and not ok_pos(q):
                    continue
                if ok_move is not None and not ok_move(sw):
                    continue
                dist[q] = dist[p] + 1
                parent[q] = p
                todo.append(q)
        return dist, parent, None


MAX_GAP = 3


def leavers(g, ok_pos=None, ok_move=None):
    """Every position from which some arrival is reached over the positions ok_pos admits and the moves ok_move
    admits: the way back out. Moves are not symmetric (a fall is one way), so this is its own search, backward over
    the graph's moves, not the forward reach reversed."""
    rev = {}
    for p, ms in g.adj.items():
        for q, sw in ms:
            if q in g.adj:
                rev.setdefault(q, []).append((p, sw))
    out = set()
    todo = deque()
    for a in g.arrivals:
        if a in g.adj and (ok_pos is None or ok_pos(a)) and a not in out:
            out.add(a)
            todo.append(a)
    while todo:
        q = todo.popleft()
        for p, sw in rev.get(q, ()):
            if p in out or (ok_pos is not None and not ok_pos(p)) or (ok_move is not None and not ok_move(sw)):
                continue
            out.add(p)
            todo.append(p)
    return out


def walk(h, arr):
    """The graph at the narrowest jump that reaches the leader: gaps of 1 first (the stated model), wider only when
    the hall's own way to its leader needs one. Returns (graph, engage set, gap)."""
    for gap in range(1, MAX_GAP + 1):
        g = Graph(h, arr, gap)
        goal = engage_set(h, g)
        if goal:
            return g, goal, gap
    return g, goal, MAX_GAP


def path_to(parent, p):
    out = []
    while p is not None:
        out.append(p)
        p = parent[p]
    return out[::-1]


def arrivals(h, sky=False):
    """Ring positions at the heightmap ground, ground positions in the lot outside the footprint, and (sky) every
    position open to the sky inside the lot."""
    out = []
    fp = h.footprint
    for (x, z), g in h.ring.items():
        if fp[0] <= x <= fp[2] and fp[1] <= z <= fp[3]:
            continue
        for y in (g + 1, g + 2, g):
            if is_pos(h, x, y, z):
                out.append((x, y, z))
                break
    if h.level is not None:
        for x in range(h.lot[0], h.lot[2] + 1):
            for z in range(h.lot[1], h.lot[3] + 1):
                if fp[0] <= x <= fp[2] and fp[1] <= z <= fp[3]:
                    continue
                for y in range(h.level - 1, h.level + 3):
                    if is_pos(h, x, y, z):
                        out.append((x, y, z))
    out = [p for p in out if h.x0 <= p[0] <= h.x1 and h.z0 <= p[2] <= h.z1]
    if sky:
        out += sky_positions(h)
    return out


def sky_positions(h):
    out = []
    for x in range(h.lot[0], h.lot[2] + 1):
        for z in range(h.lot[1], h.lot[3] + 1):
            for y in range(h.y1 - 1, h.y0, -1):
                if not passable(h, x, y + 1, z):
                    break
                if is_pos(h, x, y, z):
                    out.append((x, y, z))
                    if h.cls(x, y, z) == AIR:
                        break
    return out


# ------------------------------------------------------------------------------------------------ sight
def feet(c):
    return (c[0] + 0.5, c[1], c[2] + 0.5)


def facing(yaw):
    r = math.radians(yaw)
    return (-math.sin(r), math.cos(r))


def dist3(a, b):
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(a, b)))


def surely_seen(seat, yaw, d, c, cone=True):
    s, p = feet(seat), feet(c)
    if dist3(s, p) > d - U:
        return False
    if not cone:
        return True
    fx, fz = facing(yaw)
    return (p[0] - s[0]) * fx + (p[2] - s[2]) * fz >= FRONT


def possibly_seen(seat, d, c):
    return dist3(feet(seat), feet(c)) <= d + U


def solid_at(h, x, y, z):
    return h.cls(math.floor(x), math.floor(y), math.floor(z)) in (SOLID, TALL)


def clear_line(h, a, b, step=0.1):
    n = max(1, int(dist3(a, b) / step))
    ca, cb = tuple(math.floor(v) for v in a), tuple(math.floor(v) for v in b)
    for i in range(1, n):
        t = i / n
        pt = tuple(a[k] + (b[k] - a[k]) * t for k in range(3))
        cell = tuple(math.floor(v) for v in pt)
        if cell in (ca, cb):
            continue
        if solid_at(h, *pt):
            return False
    return True


def engage_set(h, g):
    lf = feet(h.leader)
    chest = (lf[0], lf[1] + 1.0, lf[2])
    out = set()
    for p in g.adj:
        pf = feet(p)
        if dist3(pf, lf) <= ENGAGE and clear_line(h, (pf[0], pf[1] + EYE, pf[2]), chest):
            out.add(p)
    return out


# ------------------------------------------------------------------------------------------------ the seats
def junior_gyms():
    """{junior id: gym} -- the only thing taken from data/gym_junior_trainers.json besides the D1 cells."""
    return {t["id"]: t["gym"] for t in load(ROOT / "data" / "gym_junior_trainers.json")["trainers"]}


def seats(placements=None, build=None):
    """{id: {gym, seat, yaw, sight, ...}}: the juniors as R17 summons them (route_trainers.placements()) with the
    sight the emitted mob file gives rctmod."""
    if placements is None:
        import route_trainers
        placements = route_trainers.placements()
    gyms = junior_gyms()
    declared = {t["id"]: t.get("sight_distance")
                for t in load(ROOT / "data" / "gym_junior_trainers.json")["trainers"]}
    mobs = pack_dir("cobblers_trainers", build) / "data" / "rctmod" / "mobs" / "trainers" / "single"
    out = {}
    for tid, seat, yaw in placements:
        if tid not in gyms:
            continue
        mf = mobs / ("%s.json" % tid)
        mob = load(mf) if mf.is_file() else None
        out[tid] = {"gym": gyms[tid], "seat": tuple(int(v) for v in seat), "yaw": float(yaw),
                    "sight": float(mob["forceBattleMaxDistance"]) if mob else None, "mob": mob,
                    "declared_sight": declared.get(tid)}
    return out


def other_trainer_seats(placements=None):
    if placements is None:
        import route_trainers
        placements = route_trainers.placements()
    gyms = junior_gyms()
    return [(tid, tuple(seat)) for tid, seat, _y in placements if tid not in gyms]


# ------------------------------------------------------------------------------------------------ the rosters
class Species:
    """Cobblemon's own species, items and rctmod's skins, read from the jars."""

    def __init__(self):
        self.types, self.moves = {}, {}
        with zipfile.ZipFile(jar("Cobblemon-fabric")) as z:
            for n in z.namelist():
                if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                    d = json.loads(z.read(n))
                    name = Path(n).stem
                    t = [d.get("primaryType"), d.get("secondaryType")]
                    self.types[name] = {x.lower() for x in t if x}
                    self.moves[name] = {m.split(":", 1)[1] for m in d.get("moves", []) if ":" in m}
            lang = json.loads(z.read("assets/cobblemon/lang/en_us.json"))
        self.items = {k.split(".", 2)[2] for k in lang if k.startswith("item.cobblemon.")}
        with zipfile.ZipFile(jar("rctmod-fabric")) as z:
            self.skins = {n for n in z.namelist() if n.startswith("assets/rctmod/textures/")}


def leader_type(rec, sp):
    """The type most of the leader's team carries, and whether a strict majority does."""
    count = {}
    team = rec.get("team") or []
    for m in team:
        for t in sp.types.get(m["species"], ()):
            count[t] = count.get(t, 0) + 1
    if not count:
        return None, False
    best = max(sorted(count), key=lambda t: count[t])
    return best, count[best] * 2 > len(team)


def leaders(doc, sp):
    """{gymN: {id, type, ace, cap}}: each leader's own record, its team's type and its top level."""
    caps = doc["generation_contract"]["gym_ace_levels"]
    out = {}
    for r in doc["trainers"]:
        m = re.match(r"gym_0(\d)_", r.get("id", ""))
        if not m or r.get("class") != "gym_leader":
            continue
        n = int(m.group(1))
        tops = [max(x["level"] for x in r["team"])] if r.get("team") else []
        for mode in (r.get("modes") or {}).values():
            if mode.get("team"):
                tops.append(max(x["level"] for x in mode["team"]))
        t, majority = leader_type(r, sp)
        cap = caps[n - 1]
        out["gym%d" % n] = {"id": r["id"], "type": t, "majority": majority, "cap": cap,
                            "top": min(tops) if tops else None,
                            "ace": min([cap] + ([min(tops)] if tops else []))}
    return out


def roster_problems(tid, rec, gym, lead, sp, pack, mob):
    """Every roster fault of one junior, as (code, detail)."""
    out = []
    if rec is None:
        return [("roster", "no record in data/trainers.json")]
    modes = rec.get("modes") or {}
    teams = {m: (modes.get(m) or {}).get("team") for m in ("normal", "challenge")}
    for m in ("normal", "challenge"):
        if not teams[m]:
            out.append(("roster", "no %s team" % m))
    if out:
        return out
    ident = {m: ((modes[m].get("rct") or {}).get("identity")) for m in ("normal", "challenge")}
    if ident["normal"] != tid:
        out.append(("roster", "Normal identity %r, not %r" % (ident["normal"], tid)))
    if ident["challenge"] != tid + "_challenge":
        out.append(("roster", "Challenge identity %r, not %r" % (ident["challenge"], tid + "_challenge")))
    ace = lead["ace"]
    theme = (rec.get("type_theme") or "").lower()
    for m in ("normal", "challenge"):
        for p in teams[m]:
            if p["level"] > ace:
                out.append(("roster", "%s %s L%d is over the leader's ace %d" % (m, p["species"], p["level"], ace)))
            ts = sp.types.get(p["species"])
            if ts is None:
                out.append(("roster", "%s %s: no such species in the Cobblemon jar" % (m, p["species"])))
                continue
            if lead["type"] not in ts and theme not in ts:
                out.append(("roster", "%s %s is %s: neither the leader's %s nor the stated theme %r"
                            % (m, p["species"], "/".join(sorted(ts)), lead["type"], theme)))
            bad = [mv for mv in p.get("moveset", []) if mv not in sp.moves.get(p["species"], ())]
            if bad:
                out.append(("roster", "%s %s cannot learn %s" % (m, p["species"], bad)))
            if p.get("heldItem") and p["heldItem"].split(":")[-1] not in sp.items:
                out.append(("roster", "%s %s holds %r, not a Cobblemon item" % (m, p["species"], p["heldItem"])))
    tops = {m: max(p["level"] for p in teams[m]) for m in teams}
    if tops["normal"] != tops["challenge"]:
        out.append(("roster", "Challenge tops out at %d, Normal at %d" % (tops["challenge"], tops["normal"])))
    # the emitted pack carries both, as the roster says
    tdir = pack / "data" / "rctmod" / "trainers"
    for m, ident_ in (("normal", tid), ("challenge", tid + "_challenge")):
        f = tdir / ("%s.json" % ident_)
        if not f.is_file():
            out.append(("roster", "the pack has no trainer file %s.json" % ident_))
            continue
        got = [(p["species"], p["level"], tuple(p.get("moveset", [])), p.get("heldItem")) for p in load(f)["team"]]
        want = [(p["species"], p["level"], tuple(p.get("moveset", [])), p.get("heldItem")) for p in teams[m]]
        if got != want:
            out.append(("roster", "the pack's %s.json team differs from data/trainers.json %s" % (ident_, m)))
        for sub in ("mobs/trainers/single", "dialogs/trainers/single"):
            if not (pack / "data" / "rctmod" / sub / ("%s.json" % ident_)).is_file():
                out.append(("roster", "the pack has no %s/%s.json" % (sub, ident_)))
    if not (pack / "data" / "cobblers" / "advancement" / "trainer" / ("%s.json" % tid)).is_file():
        out.append(("roster", "the pack has no advancement trainer/%s.json" % tid))
    if mob:
        tex = mob.get("textureResource", "")
        if tex and "assets/rctmod/" + tex.split(":", 1)[-1] not in sp.skins:
            out.append(("roster", "skin %s is not in the rctmod jar" % tex))
    return out


def tops(rec):
    return max(p["level"] for p in rec["modes"]["normal"]["team"])


# ------------------------------------------------------------------------------------------------ the audit
def homes(pack):
    """{id: (x, y, z)} from the emitted cycle.mcfunction's send-home lines."""
    out = {}
    f = pack / "data" / "cobblers" / "function" / "trainers" / "cycle.mcfunction"
    pat = re.compile(r'nbt=\{TrainerId:"([^"]+)",InBattle:0b\}\] positioned (\S+) (\S+) (\S+) .* run tp @s')
    for line in f.read_text(encoding="utf-8").splitlines():
        m = pat.search(line)
        if m:
            out.setdefault(m.group(1), []).append(tuple(float(v) for v in m.groups()[1:]))
    return out


def junior_walks(h, g, juniors, goal):
    """Per junior: must_pass (the walk that avoids its sight, or None), softlock (True if still reachable), first
    (moves before a player is surely in its sight)."""
    dist, _p, _r = g.bfs()
    out = {}
    for tid, j in juniors.items():
        seat, yaw, d = j["seat"], j["yaw"], j["sight"]
        seen = {p for p in g.adj if surely_seen(seat, yaw, d, p)}
        first = min((dist[p] for p in seen if p in dist), default=None)
        evade = {}
        # the junior's own two cells are never walked through: a walk that touches the junior has passed it
        body = {seat, (seat[0], seat[1] + 1, seat[2])}
        for cone in (True, False):
            sn = seen if cone else {p for p in g.adj if surely_seen(seat, yaw, d, p, cone=False)}

            def ok_pos(q, sn=sn, body=body):
                return q not in sn and q not in body and (q[0], q[1] + 1, q[2]) not in body

            def ok_move(sw, seat=seat, yaw=yaw, d=d, cone=cone, body=body):
                return not body.intersection(sw) and not any(surely_seen(seat, yaw, d, c, cone) for c in sw)

            _d, parent, hit = g.bfs(ok_pos, ok_move, goal)
            evade[cone] = None
            if hit:
                path = path_to(parent, hit)
                near = min(path, key=lambda p: dist3(feet(p), feet(seat)))
                evade[cone] = {"from": path[0], "to": hit, "closest": near,
                               "closest_distance": round(dist3(feet(near), feet(seat)), 2), "moves": len(path) - 1}

        # line of sight: the same cut in any direction, counting only cells with a clear line from the player's eye
        # to some part of the junior (feet + 0.5, 1.0, 1.5). If rctmod's trigger is the player's look ray hitting the
        # trainer (the jar's ProjectileUtil / EntityHitResult, see THE SIGHT), a cell behind a wall never fires.
        los_cache = {}

        def los_seen(c, seat=seat, d=d):
            if c not in los_cache:
                sf = feet(seat)
                cf = feet(c)
                eye = (cf[0], cf[1] + EYE, cf[2])
                los_cache[c] = surely_seen(seat, 0, d, c, cone=False) and any(
                    clear_line(h, eye, (sf[0], sf[1] + k, sf[2])) for k in (0.5, 1.0, 1.5))
            return los_cache[c]

        def ok_pos3(q, body=body):
            return not los_seen(q) and q not in body and (q[0], q[1] + 1, q[2]) not in body

        def ok_move3(sw, body=body):
            return not body.intersection(sw) and not any(los_seen(c) for c in sw)

        _d3, parent3, hit3 = g.bfs(ok_pos3, ok_move3, goal)
        evade["los"] = None
        if hit3:
            path = path_to(parent3, hit3)
            near = min(path, key=lambda p: dist3(feet(p), feet(seat)))
            evade["los"] = {"from": path[0], "to": hit3, "closest": near,
                            "closest_distance": round(dist3(feet(near), feet(seat)), 2), "moves": len(path) - 1}

        def ok_pos2(q, body=body):
            return q not in body and (q[0], q[1] + 1, q[2]) not in body

        def ok_move2(sw, body=body):
            return not body.intersection(sw)

        _d, _p2, hit2 = g.bfs(ok_pos2, ok_move2, goal)
        out[tid] = {"evade": evade, "softlock_free": hit2 is not None, "first": first,
                    "seen_positions": len(seen)}
    return out


def standing_together(g, goal, seat_list):
    """Every junior's two body cells blocked AT ONCE (R17 summons them all; the per-junior softlock check blocks one
    at a time, which two juniors side by side in a two-wide lane both pass): whether an arrival still reaches the
    leader, the positions a player can then reach whose only way back to an arrival runs through a body
    (`walled_in`), and how many reachable positions have no way back even with nobody standing (`one_way`: the
    hall's own drops, not the juniors')."""
    body = set()
    for s in seat_list:
        body |= {tuple(s), (s[0], s[1] + 1, s[2])}

    def ok_pos(q):
        return q not in body and (q[0], q[1] + 1, q[2]) not in body

    def ok_move(sw):
        return not body.intersection(sw)

    _d, _p, hit = g.bfs(ok_pos, ok_move, goal)
    inside, _pp, _r = g.bfs(ok_pos, ok_move)
    out_free = leavers(g)
    out_all = leavers(g, ok_pos, ok_move)
    return {"reaches_leader": hit is not None,
            "walled_in": sorted(p for p in inside if p in out_free and p not in out_all),
            "one_way": sum(1 for p in inside if p not in out_free)}


def audit_gym(gym, juniors, recs, lead, sp, G, pack, home, others, build=None, strict_facing=False,
              strict_sight=False):
    """{'problems': [(code, id, detail)], 'notes': [...], 'info': {...}} for one gym."""
    h = hall(gym, G, build)
    probs, notes, info, warns = [], [], {}, []
    if h.unknown:
        probs.append(("blocks", gym, "unclassified block names: %s" % sorted(h.unknown)))
    if not h.spawner:
        probs.append(("leader", gym, "no rctmod:trainer_spawner in the replayed blocks"))
        return {"problems": probs, "warnings": warns, "notes": notes, "info": info}
    if h.spawner != h.declared_spawner:
        probs.append(("leader", gym, "spawner built at %s, the record says %s" % (h.spawner, h.declared_spawner)))
    sealed, gap = [], None
    if gym == "gym2":
        doc = load(ROOT / "data" / "gym_junior_trainers.json")
        for c in doc["gyms"]["gym2"].get("assume_closed", []):
            sealed += [tuple(x) for x in c["cells"]]
        open_now = [c for c in sealed if h.cls(*c) in PASSABLE]
        notes.append("D1: %d of the %d assume_closed cells are open as built" % (len(open_now), len(sealed)))
        # as built, on foot: what a walker finds
        g0, goal0, gap0 = walk(h, arrivals(h, sky=False))
        info["as_built_on_foot_reaches_leader"] = bool(goal0)
        if goal0:
            notes.append("D1: as built, a walker on foot reaches Misty (jumps over gaps up to %d)" % gap0)
            w0 = junior_walks(h, g0, juniors, goal0)
            for tid, r in sorted(w0.items()):
                e = r["evade"][False] or r["evade"][True]
                if e:
                    notes.append("D1 (known, not failed alone): as built, a walker from %s reaches Misty at %s "
                                 "in %d moves without being surely in %s's sight%s (closest %.2f at %s)"
                                 % (e["from"], e["to"], e["moves"], tid,
                                    "" if r["evade"][False] else " in front of it", e["closest_distance"],
                                    e["closest"]))
        else:
            notes.append("D1: as built, no walker on foot reaches Misty")
        for c in sealed:
            h.override[c] = SOLID
        _g1, goal1, _gap1 = walk(h, arrivals(h, sky=False))
        info["sealed_on_foot_reaches_leader"] = bool(goal1)
        notes.append("D1 sealed: a walker on foot %s Misty; the juniors are proved for a player who lands from the "
                     "sky (the island floats)" % ("still reaches" if goal1 else "cannot reach"))
        g, goal, gap = walk(h, arrivals(h, sky=True))
        info["arrival"] = "D1 sealed; ring, lot ground and every position open to the sky"
    else:
        g, goal, gap = walk(h, arrivals(h))
        info["arrival"] = "ring and forecourt, on foot"
    info["positions"], info["arrivals"], info["engage"], info["gap"] = len(g.adj), len(g.arrivals), len(goal), gap
    if not goal:
        probs.append(("leader", gym, "no arrival reaches a position that engages the leader at %s, even with "
                      "jumps over gaps of %d" % (h.leader, MAX_GAP)))
        return {"problems": probs, "warnings": warns, "notes": notes, "info": info}
    if gap > 1:
        notes.append("the leader is reached only with a jump over a gap of %d (the stated model allows 1); every "
                     "check below lets the player make such jumps" % gap)
    # seats
    bodies = {}
    for tid, j in juniors.items():
        s = j["seat"]
        bodies[tid] = {s, (s[0], s[1] + 1, s[2])}
    for tid, j in sorted(juniors.items()):
        s = j["seat"]
        x, y, z = s
        if j["sight"] is None:
            probs.append(("sight", tid, "no mob file in the pack"))
            continue
        if j["mob"].get("forceBattleOnSight") is not True:
            probs.append(("sight", tid, "forceBattleOnSight is not true"))
        if not (h.cls(x, y, z) == AIR and h.cls(x, y + 1, z) in (AIR,) and h.cls(x, y - 1, z) in (SOLID, TALL)):
            probs.append(("seat", tid, "at %s: feet %s (%s), head %s, floor %s -- not a dry stand on a floor"
                          % (s, h.cls(x, y, z), bare(h.world.at(x, y, z)), h.cls(x, y + 1, z), h.cls(x, y - 1, z))))
        fp = h.footprint
        if not (fp[0] <= x <= fp[2] and fp[1] <= z <= fp[3]):
            probs.append(("seat", tid, "at %s, outside the hall's footprint %s" % (s, fp)))
        if s not in g.adj:
            probs.append(("seat", tid, "at %s, a position no arrival reaches" % (s,)))
        for other, b in bodies.items():
            if other != tid and (bodies[tid] & b or dist3(feet(s), feet(juniors[other]["seat"])) < 1.0):
                probs.append(("seat", tid, "at %s shares a body cell with %s" % (s, other)))
        if dist3(feet(s), feet(h.leader)) < 1.5 or s == h.spawner:
            probs.append(("seat", tid, "at %s, on the leader's stand %s" % (s, h.leader)))
        for oid, os_ in others:
            if dist3(feet(s), feet(os_)) < 1.0:
                probs.append(("seat", tid, "at %s, on %s's seat %s" % (s, oid, os_)))
        hs = home.get(tid, [])
        want = (x + 0.5, float(y), z + 0.5)
        if hs != [want]:
            probs.append(("home", tid, "cycle.mcfunction sends it home to %s; R17 summons it at %s, once" % (hs, want)))
        if j.get("declared_sight") is not None and j["declared_sight"] != j["sight"]:
            probs.append(("sight", tid, "the mob file's forceBattleMaxDistance %s is not the seat's sight_distance %s"
                          % (j["sight"], j["declared_sight"])))
        if any(possibly_seen(s, j["sight"], p) for p in goal):
            near = min(goal, key=lambda p: dist3(feet(p), feet(s)))
            probs.append(("leader", tid, "its sight (%.1f + %.2f) reaches %s, a position that engages the leader"
                          % (j["sight"], U, near)))
    # the trainers of other systems standing in this hall
    lot = h.lot
    for oid, os_ in others:
        if lot[0] <= os_[0] <= lot[2] and lot[1] <= os_[2] <= lot[3]:
            probs.append(("other_trainer", oid, "seated at %s inside %s's lot" % (os_, gym)))
    walks = junior_walks(h, g, {t: j for t, j in juniors.items() if j["sight"] is not None}, goal)
    for tid, r in sorted(walks.items()):
        if r["evade"][False]:
            e = r["evade"][False]
            probs.append(("must_pass", tid, "a walk from %s reaches the leader at %s in %d moves without coming "
                          "within its sight distance in any direction (closest %.2f at %s)"
                          % (e["from"], e["to"], e["moves"], e["closest_distance"], e["closest"])))
        elif r["evade"][True]:
            e = r["evade"][True]
            (probs if strict_facing else warns).append(("facing", tid, "yaw %g: a walk from %s reaches the leader at %s in %d moves passing "
                          "within its sight distance only behind or beside it (closest %.2f at %s)"
                          % (juniors[tid]["yaw"], e["from"], e["to"], e["moves"], e["closest_distance"],
                             e["closest"])))
        if not r["evade"][False] and r["evade"].get("los"):
            e = r["evade"]["los"]
            (probs if strict_sight else warns).append((
                "line_of_sight", tid, "a walk from %s reaches the leader at %s in %d moves passing within its sight "
                "distance only behind a block (no clear line from the player's eye to it; closest %.2f at %s): the cut "
                "holds only if rctmod's sight passes walls" % (e["from"], e["to"], e["moves"], e["closest_distance"],
                                                               e["closest"])))
        if not r["softlock_free"]:
            probs.append(("softlock", tid, "with its two body cells at %s blocked, no arrival reaches the leader"
                          % (juniors[tid]["seat"],)))
    # every junior stands at once (R17 summons them all): the hall is judged with ALL their bodies in place, once for
    # the way in and once for the way back out
    if walks:
        st = standing_together(g, goal, [juniors[t]["seat"] for t in walks])
        if not st["reaches_leader"]:
            probs.append(("softlock", gym, "with all %d juniors standing at once no arrival reaches the leader"
                          % len(walks)))
        trapped = st["walled_in"]
        info["walled_in_by_juniors"] = len(trapped)
        if trapped:
            who = min(walks, key=lambda t: min(dist3(feet(p), feet(juniors[t]["seat"])) for p in trapped))
            probs.append(("walled_in", gym, "%d position(s) a player reaches with every junior standing have a way "
                          "back to an arrival only through a junior's body (e.g. %s, nearest %s at %s)"
                          % (len(trapped), trapped[0], who, juniors[who]["seat"])))
        hall_traps = st["one_way"]
        info["one_way_without_juniors"] = hall_traps
        if hall_traps:
            notes.append("way back (information): %d reachable position(s) have no way back to an arrival in the walk "
                         "model even with no junior standing (the hall's own one-way drops; not the juniors')"
                         % hall_traps)
    if gym != "gym2":
        # D3 (information): a rider on a flying mount setting down anywhere open to the sky inside the lot
        gs = Graph(h, arrivals(h, sky=True), gap)
        ws = junior_walks(h, gs, {t: j for t, j in juniors.items() if j["sight"] is not None}, engage_set(h, gs))
        fly = sorted(t for t, r in ws.items() if r["evade"][False] and not walks[t]["evade"][False])
        info["flight_avoids"] = fly
        notes.append("flight (D3, information): a rider setting down open to the sky avoids %s"
                     % (", ".join(fly) if fly else "no junior"))
    # order: the order a player first comes surely into each one's sight
    order = sorted(walks, key=lambda t: (walks[t]["first"] if walks[t]["first"] is not None else 10 ** 9, t))
    info["order"] = [(t, walks[t]["first"], tops(recs[t]) if recs.get(t) else None) for t in order]
    last = None
    for t in order:
        if not recs.get(t) or walks[t]["first"] is None:
            continue
        top = tops(recs[t])
        if last and top < last[1]:
            probs.append(("order", t, "tops out at L%d, met at move %s after %s (L%d, move %s)"
                          % (top, walks[t]["first"], last[0], last[1], walks[last[0]]["first"])))
        last = (t, top)
    # apart (information): positions surely in two juniors' sight
    both = []
    ids = sorted(walks)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ja, jb = juniors[a], juniors[b]
            n = sum(1 for p in g.adj if surely_seen(ja["seat"], ja["yaw"], ja["sight"], p)
                    and surely_seen(jb["seat"], jb["yaw"], jb["sight"], p))
            if n:
                both.append((a, b, n))
    if both:
        notes.append("apart: positions surely in two juniors' sight: %s" % both)
    info["walks"] = {t: {"first": r["first"], "seen_positions": r["seen_positions"]} for t, r in walks.items()}
    return {"problems": probs, "warnings": warns, "notes": notes, "info": info}


def audit(gyms=GYMS, placements=None, roster=None, build=None, G=None, strict_facing=False, strict_sight=False):
    """The whole audit. `placements` replaces route_trainers.placements() and `roster` the gym_trainer records of
    data/trainers.json -- the two hooks the generator-mutation tests use."""
    import ground as ground_mod
    G = G or ground_mod.load()
    sp = Species()
    doc = load(ROOT / "data" / "trainers.json")
    lead = leaders(doc, sp)
    if roster is None:
        roster = [r for r in doc["trainers"] if r.get("class") == "gym_trainer"]
    recs = {r["id"]: r for r in roster}
    pack = pack_dir("cobblers_trainers", build)
    js = seats(placements, build)
    home = homes(pack)
    others = other_trainer_seats(placements)
    gyms_of = junior_gyms()
    report = {"U": U, "gyms": {}}
    missing = [t for t in gyms_of if t not in js]
    top_probs = [("seat", t, "in data/gym_junior_trainers.json but not in route_trainers.placements() (R17 never "
                  "summons it)") for t in missing]
    top_probs += [("roster", t, "a gym_trainer record with no seat") for t in recs if t not in gyms_of]
    for gym in gyms:
        L = lead.get(gym)
        juniors = {t: j for t, j in js.items() if j["gym"] == gym}
        probs = []
        if L is None:
            probs.append(("leader", gym, "no gym_leader record in data/trainers.json"))
        elif not L["majority"]:
            probs.append(("leader", gym, "the leader's team has no majority type (best %s)" % L["type"]))
        if L and L["top"] is not None and L["top"] != L["cap"]:
            probs.append(("leader", gym, "the leader's team tops out at %s, the contract's ace is %d"
                          % (L["top"], L["cap"])))
        for tid, j in juniors.items():
            for code, detail in roster_problems(tid, recs.get(tid), gym, L, sp, pack, j["mob"]):
                probs.append((code, tid, detail))
            if recs.get(tid) and (recs[tid].get("type_theme") or "").lower() != (L or {}).get("type"):
                probs.append(("roster", tid, "stated theme %r differs from the leader's type %s"
                              % (recs[tid].get("type_theme"), (L or {}).get("type"))))
        r = audit_gym(gym, juniors, recs, L, sp, G, pack, home, others, build, strict_facing, strict_sight)
        r["problems"] = probs + r["problems"]
        r["leader"] = L
        r["juniors"] = sorted(juniors)
        report["gyms"][gym] = r
    report["problems"] = top_probs + [p for g in report["gyms"].values() for p in g["problems"]]
    report["warnings"] = [w for g in report["gyms"].values() for w in g["warnings"]]
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gym", action="append", choices=GYMS)
    ap.add_argument("--build", help="a build directory holding datapacks/ (default: this checkout's build/, then "
                                    "the newest server snapshot)")
    ap.add_argument("--strict-facing", action="store_true",
                    help="fail, rather than warn, on a junior passed only beside or behind it")
    ap.add_argument("--strict-sight", action="store_true",
                    help="fail, rather than warn, on a junior passed only with a block between it and the player")
    ap.add_argument("--json", default=str(ROOT / "derived" / "gym_trainers_audit" / "report.json"))
    a = ap.parse_args(argv)
    miss = inputs_missing(a.build)
    if miss:
        print("gym_trainers_audit: cannot run, missing: %s" % ", ".join(miss))
        return 2
    rep = audit(tuple(a.gym or GYMS), build=a.build, strict_facing=a.strict_facing, strict_sight=a.strict_sight)
    out = Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, default=list) + "\n", encoding="utf-8")
    for gym, r in rep["gyms"].items():
        L = r.get("leader") or {}
        order = r["info"].get("order") or []
        print("%s (%s, ace %s): %d junior(s), %d problem(s), %d warning(s)%s" % (
            gym, L.get("type"), L.get("ace"), len(r["juniors"]), len(r["problems"]), len(r["warnings"]),
            "; met in order " + " < ".join("%s@%s L%s" % o for o in order) if order else ""))
        for n in r["notes"]:
            print("  note: " + n)
    for code, who, detail in rep["warnings"]:
        print("WARN [%s] %s: %s" % (code, who, detail))
    for code, who, detail in rep["problems"]:
        print("PROBLEM [%s] %s: %s" % (code, who, detail))
    print("gym_trainers_audit: %d problem(s), %d warning(s) over %d gym(s); report %s"
          % (len(rep["problems"]), len(rep["warnings"]), len(rep["gyms"]), out))
    return 1 if rep["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
