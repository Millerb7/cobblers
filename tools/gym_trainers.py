#!/usr/bin/env python
"""The gym juniors: two to four trainers inside each of the eight gyms, seated so a player must pass them.

The owner, 2026-10-06: "Each gym should have its own trainers inside it, placed so a player must pass them, with
teams that fit the leader's type and the level band -- attrition before the leader, as the mainline does. Every
gym, both modes, audited against its own real geometry."

  python tools/gym_trainers.py propose --gym gym1     # the chokepoints and the seats that cover them
  python tools/gym_trainers.py check  [--gym gym1]    # prove every authored seat; writes derived/gym_trainers/

WHO OWNS WHAT. data/gym_junior_trainers.json is the STAND (seat, yaw, sight, skin, why) -- the same satellite shape
as data/vr_trainers.json, read by tools/route_trainers.py, which emits the rctmod files, the eye contact and the
rematch hold-off for every seat exactly as it does for the route trainers, and by tools/reapply.py R17, which
summons each one with `rctmod trainer summon_persistent`. data/trainers.json is the ROSTER, generated from
docs/story/TRAINER_RULES.json `gym_trainers` by docs/story/generate_trainers.py (Normal and Challenge payloads).
This tool decides nothing about teams; it proves seats.

THE GEOMETRY. Each hall is read from its own build, never from a world (the ground rule, tests/test_ground_rule.py):

  gyms 1, 3-8   tools/gym_buildings.py's own voxel model (build_one -> Emit.at), the same cells the function writes,
                over the lot's pad at its declared level
  gym 2         Misty's hall is the Cobbleverse donor `cobbleverse:misty`, placed whole at data/placements.json
                gym2_misty_gym: the template's own blocks from COBBLEVERSE-DP-v31.zip (read, never copied), then
                tools/place_donor.py's commands for that record (substitutions and the quay plinth), then
                tools/gym_interiors.py's healer sweep and gym 2 dig, replayed
  around them   tools/ground.py, rounded, for the ring of columns just outside the lot, where a player arrives

THE MOVEMENT MODEL (written here, for this tool; the independent audit must not reuse it). A position is a feet
cell with a passable head cell over it and something to stand on (a solid block or scaffolding under it), or a
feet cell that is water, a ladder or scaffolding. Two models over the same voxels:

  GENEROUS  for the cut proofs. Walk, step up one, fall ANY distance (fall damage ignored), climb, swim in all six
            directions, and sprint-jump to any position within REACH[dy] (centre to centre, horizontal) whose
            flight corridor is clear. Every partial block counts as a full one to stand on. Over-approximating the
            player is the safe side for "a player cannot get past": a cut that holds against a player who can do
            more than a real one holds against the real one.
  MODEST    for the softlock check, the opposite side: walk, step up one, fall, climb, swim, and only short jumps
            (MODEST_REACH). A seat must not be the only way through even for this player, so nobody is walled in
            by a trainer who, pinned at movement speed 0, is put back on its seat every ten ticks.

WHAT EACH SEAT MUST PROVE (check; each is a named code an audit can ask for):

  Two readings of a sight, because a position is a cell and the player's feet may be anywhere in it (SLACK 0.87):
  seen() is where a player IS within sight wherever they stand (centre within sight_distance - SLACK, in clear
  line of sight, which rctmod does not even require: its sight passes walls, docs/mechanics/GYM_INTERIORS.md
  section 3); sphere() is where a player MIGHT be (centre within sight_distance + SLACK, through walls).

  stand     the seat is a position on solid footing, dry, with two passable cells, inside the hall's own footprint
  softlock  with the junior's two body cells blocked -- and every jump or fall through them refused -- MODEST still
            reaches the leader from the street
  cut       with seen() blocked, and every jump or fall during which the player is surely in sight refused (so a
            sprint jump cannot fly over a junior), GENEROUS can no longer reach the leader from the street. That is
            "a player must pass them": every way to the leader enters the junior's sight
  leader    sphere() holds no position from which the leader can be engaged, so no junior fights a player at him
  street    sphere() holds no position outside the hall's footprint: no junior pulls a passer-by off the street
  apart     no position is in two juniors' seen(): no two juniors doing one junior's job (rctmod starts one battle at
            a time, so outer spheres touching is spacing, not a fault)
  order     the juniors' levels rise in the order a player first reaches their seen() (GENEROUS distance), and every
            level is below the leader's ace (the gym's cap, data/trainers.json generation_contract.gym_ace_levels)
  facing    the yaw is within 90 degrees of where a player first enters its sight

WHAT THIS DOES NOT PROVE, and the audit should not assume it does:
  - that eye contact fires. rctmod starts a forced battle only after player and trainer have stared at each other
    for forceBattleLookTicks (30, 1.5 s; experiments/EXP-034-scene-runtime). A player who looks away and keeps
    moving can cross a sight sphere. "Must pass" here is geometric: every route enters the sphere. Nothing gates
    the leader on a junior's defeat field, and none is added here (see GYM_TRAINERS.md, owner decisions).
  - that a player cannot build past. Every gym's no_build box is authored and not wired (each record says so), so
    a player in survival can pillar or bridge round any seat.
  - the real jump physics. REACH is a model; EXP-level truth needs a running game.

  NOT COVERED: anything in the world that this model does not build -- a town dressing, an entity, a later pass.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import zipfile
from collections import deque
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "gym_junior_trainers.json"
TRAINERS = ROOT / "data" / "trainers.json"
PLACEMENTS = ROOT / "data" / "placements.json"
INTERIORS = ROOT / "data" / "gym_interiors.json"
POLICY = ROOT / "data" / "spawn_block_policy.json"
REPORT = ROOT / "derived" / "gym_trainers"
SCHEMA = "cobblers.gym-junior-trainers/1"
GYMS = ("gym1", "gym2", "gym3", "gym4", "gym5", "gym6", "gym7", "gym8")
LEADERS = {"gym1": "gym_01_brock", "gym2": "gym_02_misty", "gym3": "gym_03_surge", "gym4": "gym_04_erika",
           "gym5": "gym_05_koga", "gym6": "gym_06_sabrina", "gym7": "gym_07_blaine", "gym8": "gym_08_giovanni"}

# The ground rule (tools/ground_rule.py): nothing here reads a world.
WORLD_READS = set()

# ------------------------------------------------------------------------------------------------ the model
# Horizontal reach of a jump, centre to centre, by the landing's height relative to the take-off. GENEROUS is
# deliberately more than vanilla (a sprint jump clears a four-block gap on the level, centre distance 5) so that a
# cut it cannot cross holds for any real player; MODEST is a jump nobody misses (a one-block gap, a two at most).
REACH = {1: 4.0, 0: 5.0, -1: 5.4, -2: 5.8}
REACH_DEEP = 6.5                 # three or more down
MODEST_REACH = {1: 2.0, 0: 3.0, -1: 3.2, -2: 3.6}
MODEST_REACH_DEEP = 3.6
MAX_DROP = 40                    # deepest fall followed (no gym is taller)
LEADER_REACH = 3.5               # a player this close to the leader's stand can engage him (survival entity reach 3)
EYE = 1.62
HALF_WIDTH = 0.29                # a player is 0.6 wide; a hair under, so grazing a face is not a collision

SOLID, OPEN, CLIMB, WATER, SCAF = 0, 1, 2, 3, 4
PASSABLE = (OPEN, CLIMB, WATER, SCAF)

# Every block name the eight halls hold, classified. A name not here fails closed: an unknown block could be the
# one a player walks through, and guessing it solid would invent a wall.
OPEN_NAMES = {
    "minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:light", "minecraft:short_grass",
    "minecraft:tall_grass", "minecraft:dandelion", "minecraft:poppy", "minecraft:cornflower",
    "minecraft:oxeye_daisy", "minecraft:chain", "minecraft:lantern", "minecraft:soul_lantern", "minecraft:torch",
    "minecraft:wall_torch", "minecraft:redstone_wire", "minecraft:rail",
    # thin collision: a player cannot really pass these, but GENEROUS is the safe side and the two below are props
    "pokeblocks:magikarp_fishbowl", "pokeblocks:pokedoll_shellder",
    # Cobblemon Battle Positions markers: flat floor markers
    "cobblemonbattlepositions:player_pokemon_position", "cobblemonbattlepositions:player_stand_position",
    "cobblemonbattlepositions:trainer_pokemon_position",
}
WATER_NAMES = {"minecraft:water", "minecraft:bubble_column", "minecraft:seagrass", "minecraft:tall_seagrass",
               "minecraft:kelp", "minecraft:kelp_plant", "minecraft:sea_pickle", "minecraft:fire_coral",
               "minecraft:tube_coral_fan"}
CLIMB_NAMES = {"minecraft:ladder", "minecraft:vine"}
SCAF_NAMES = {"minecraft:scaffolding"}
SOLID_NAMES = {
    # full or near-full collision: a player stands on it and cannot pass it
    "minecraft:acacia_planks", "minecraft:andesite", "minecraft:azalea_leaves", "minecraft:bamboo_planks",
    "minecraft:barrel", "minecraft:basalt", "minecraft:birch_planks", "minecraft:blast_furnace",
    "minecraft:bookshelf", "minecraft:brewing_stand", "minecraft:calcite", "minecraft:cauldron",
    "minecraft:cherry_log", "minecraft:cherry_planks", "minecraft:chest", "minecraft:chiseled_deepslate",
    "minecraft:chiseled_polished_blackstone", "minecraft:chiseled_quartz_block", "minecraft:chiseled_stone_bricks",
    "minecraft:chiseled_tuff", "minecraft:chiseled_tuff_bricks", "minecraft:coarse_dirt",
    "minecraft:cobbled_deepslate", "minecraft:cobblestone", "minecraft:cobblestone_wall", "minecraft:composter",
    "minecraft:copper_block", "minecraft:copper_grate", "minecraft:cut_copper", "minecraft:dark_oak_planks",
    "minecraft:deepslate", "minecraft:deepslate_bricks", "minecraft:deepslate_tiles", "minecraft:glass",
    "minecraft:glowstone", "minecraft:granite", "minecraft:grindstone", "minecraft:hay_block",
    "minecraft:iron_bars", "minecraft:lectern", "minecraft:mangrove_log", "minecraft:mangrove_planks",
    "minecraft:moss_block", "minecraft:mud", "minecraft:mud_brick_wall", "minecraft:mud_bricks",
    "minecraft:muddy_mangrove_roots", "minecraft:oak_fence", "minecraft:orange_terracotta", "minecraft:packed_mud",
    "minecraft:pearlescent_froglight", "minecraft:polished_andesite", "minecraft:polished_basalt",
    "minecraft:polished_blackstone", "minecraft:polished_blackstone_bricks", "minecraft:polished_deepslate",
    "minecraft:polished_diorite", "minecraft:polished_granite", "minecraft:polished_tuff", "minecraft:purpur_block",
    "minecraft:purpur_pillar", "minecraft:quartz_block", "minecraft:quartz_pillar", "minecraft:redstone_block",
    "minecraft:rooted_dirt", "minecraft:smoker", "minecraft:smooth_basalt", "minecraft:smooth_quartz",
    "minecraft:soul_sand", "minecraft:spruce_log", "minecraft:spruce_planks", "minecraft:stone",
    "minecraft:stone_bricks", "minecraft:stonecutter", "minecraft:stripped_acacia_log",
    "minecraft:stripped_cherry_log", "minecraft:stripped_mangrove_log", "minecraft:stripped_spruce_log",
    "minecraft:terracotta", "minecraft:tinted_glass", "minecraft:tuff", "minecraft:tuff_bricks",
    "minecraft:tuff_wall", "minecraft:verdant_froglight", "minecraft:waxed_copper_block",
    "minecraft:waxed_copper_grate", "minecraft:waxed_exposed_copper", "minecraft:waxed_weathered_copper",
    "minecraft:waxed_weathered_cut_copper", "rctmod:trainer_spawner",
    # Misty's donor and its dig
    "cobblefurnies:bonsai_plant", "cobblefurnies:light_blue_dark_stool", "cobblefurnies:light_blue_sofa",
    "cobblefurnies:light_blue_table", "cobblefurnies:statue_ancient", "cobblemon:blue_gilded_chest",
    "cobblemon:healing_machine", "cobblemon:relic_coin_sack", "cobblemon:water_stone_ore",
    "minecraft:black_concrete", "minecraft:decorated_pot", "minecraft:dirt", "minecraft:dirt_path",
    "minecraft:flowering_azalea_leaves", "minecraft:grass_block", "minecraft:light_blue_concrete",
    "minecraft:light_blue_stained_glass", "minecraft:light_blue_stained_glass_pane", "minecraft:oxidized_cut_copper",
    "minecraft:prismarine_brick_stairs", "minecraft:prismarine_bricks", "minecraft:prismarine",
    "minecraft:dark_prismarine", "minecraft:quartz_slab", "minecraft:quartz_stairs", "minecraft:sand",
    "minecraft:sea_lantern", "minecraft:smooth_quartz_stairs", "minecraft:smooth_stone",
    "minecraft:stone_brick_stairs", "minecraft:warped_planks", "minecraft:warped_stairs", "minecraft:white_concrete",
    "minecraft:dark_oak_slab", "minecraft:dark_oak_fence",
    "sophisticatedstorage:barrel", "moarconcrete:white_concrete_texture",
    "moarconcrete:black_concrete_texture", "moarconcrete:light_blue_concrete_texture",
}
PARTIAL_OPEN_SUFFIX = ("_carpet", "_pressure_plate", "_button", "_sign", "_banner")


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def classify(state, unknown=None):
    n = block_name(state)
    if n in OPEN_NAMES or n.endswith(PARTIAL_OPEN_SUFFIX):
        return OPEN
    if n in WATER_NAMES:
        return WATER
    if n in CLIMB_NAMES:
        return CLIMB
    if n in SCAF_NAMES:
        return SCAF
    if n in SOLID_NAMES or n.endswith(("_stairs", "_slab", "_wall", "_fence", "_concrete", "_glass_pane")):
        return SOLID
    if unknown is not None:
        unknown.add(n)
        return SOLID
    raise SystemExit("gym_trainers: block %r is not classified; add it to the movement model's tables" % n)


# ------------------------------------------------------------------------------------------------ the voxels
class Voxels:
    """A box of classified cells: (x0, y0, z0)-(x1, y1, z1) inclusive. Outside the box is solid, so nothing
    leaves the lot except back onto the ring a player arrived from."""

    def __init__(self, box, at):
        self.x0, self.y0, self.z0, self.x1, self.y1, self.z1 = box
        self.nx, self.ny, self.nz = self.x1 - self.x0 + 1, self.y1 - self.y0 + 1, self.z1 - self.z0 + 1
        self.c = bytearray(self.nx * self.ny * self.nz)
        self.unknown = set()
        for x in range(self.x0, self.x1 + 1):
            for z in range(self.z0, self.z1 + 1):
                for y in range(self.y0, self.y1 + 1):
                    self.c[self.i(x, y, z)] = classify(at(x, y, z), self.unknown)
        if self.unknown:
            raise SystemExit("gym_trainers: unclassified blocks %s; add them to the movement model's tables"
                             % sorted(self.unknown))

    def i(self, x, y, z):
        return ((x - self.x0) * self.nz + (z - self.z0)) * self.ny + (y - self.y0)

    def cls(self, x, y, z):
        if not (self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1 and self.z0 <= z <= self.z1):
            return SOLID if y <= self.y1 else OPEN
        return self.c[self.i(x, y, z)]

    def passable(self, x, y, z):
        return self.cls(x, y, z) != SOLID

    def standable(self, x, y, z):
        if not (self.x0 <= x <= self.x1 and self.y0 < y < self.y1 and self.z0 <= z <= self.z1):
            return False
        f = self.cls(x, y, z)
        if f == SOLID or self.cls(x, y + 1, z) == SOLID:
            return False
        if f in (CLIMB, WATER, SCAF):
            return True
        return self.cls(x, y - 1, z) in (SOLID, SCAF)

    def dry_footing(self, x, y, z):
        return self.standable(x, y, z) and self.cls(x, y, z) == OPEN and self.cls(x, y + 1, z) == OPEN \
            and self.cls(x, y - 1, z) == SOLID


# ------------------------------------------------------------------------------------------------ the halls
def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Hall:
    """One gym's voxels, its arrival ring, its leader and its footprint."""

    def __init__(self, gym, vox, ring, leader_stand, footprint, lot_rect, leader_id):
        self.gym, self.vox, self.ring = gym, vox, ring
        self.leader_stand, self.footprint, self.lot_rect, self.leader_id = leader_stand, footprint, lot_rect, leader_id


def ring_columns(rect):
    x0, z0, x1, z1 = rect
    out = []
    for x in range(x0 - 1, x1 + 2):
        out += [(x, z0 - 1), (x, z1 + 1)]
    for z in range(z0, z1 + 1):
        out += [(x0 - 1, z), (x1 + 1, z)]
    return out


def building_hall(gym, G):
    """Gyms 1 and 3-8: tools/gym_buildings.py's own model of the record it builds."""
    import gym_buildings as GB
    doc = load(ROOT / "data" / "gym_buildings" / ("%s.json" % gym))
    e, lot_rect, lot_level = GB.build_one(doc)
    lot_level = int(doc["site"]["lot_level"])
    x0, z0, x1, z1 = lot_rect
    ring = ring_columns(lot_rect)
    # the street meets the pad: a ring column below the pad is raised to it (the town prep blends its edges), a
    # hillside above it stays where tools/ground.py puts it
    ring_ground = {(x, z): max(G(x, z), lot_level) for x, z in ring}
    b = GB.norm(doc["bounds"])
    y0 = min(b[1], lot_level) - 3
    y1 = max([b[4]] + list(ring_ground.values())) + 4

    def at(x, y, z):
        if x0 <= x <= x1 and z0 <= z <= z1:
            return e.at(x, y, z)
        return "minecraft:stone" if y <= ring_ground[(x, z)] else "minecraft:air"

    vox = Voxels((x0 - 1, y0, z0 - 1, x1 + 1, y1, z1 + 1), at)
    sx, sy, sz = doc["leader"]["spawner"]
    f = doc["site"]["footprint"]
    starts = [(x, ring_ground[(x, z)] + 1, z) for x, z in ring]
    return Hall(gym, vox, starts, (sx, sy + 1, sz), tuple(f), tuple(lot_rect), doc["leader"]["id"])


def donor_zip():
    env = os.environ.get("COBBLERS_DONOR_ZIP")
    cands = ([env] if env else []) + [str(ROOT / "build" / "cobbleverse" / "COBBLEVERSE-DP-v31.zip")] + \
        sorted(glob("C:/Users/wnd/Documents/cobblers-local/server-snapshot-*/datapacks/COBBLEVERSE-DP-v31.zip"),
               reverse=True)
    for c in cands:
        if c and Path(c).is_file():
            return c
    return None


def template_cells(zpath, template):
    """{(x, y, z): state} the template sets, template-relative. Unlisted cells are structure voids."""
    import nbt
    ns, path = template.split(":", 1)
    with zipfile.ZipFile(zpath) as z:
        _n, root = nbt.loads(z.read("data/%s/structure/%s.nbt" % (ns, path)))
    names = []
    for p in root["palette"]:
        props = p.get("Properties") or {}
        names.append(p["Name"] + ("[%s]" % ",".join("%s=%s" % kv for kv in sorted(props.items())) if props else ""))
    return {tuple(b["pos"]): names[b["state"]] for b in root["blocks"]}, tuple(root["size"])


class Replay:
    """fill / setblock over a dict of cells, for gym 2's donor commands and its dig."""

    def __init__(self, base):
        self.base, self.cells = base, {}

    def at(self, x, y, z):
        s = self.cells.get((x, y, z))
        return s if s is not None else self.base(x, y, z)

    def run(self, line):
        p = line.split()
        if not p or p[0].startswith("#") or p[0] in ("forceload", "place", "data", "say", "tellraw"):
            return
        if p[0] == "setblock":
            self.cells[(int(p[1]), int(p[2]), int(p[3]))] = p[4]
            return
        if p[0] != "fill":
            return
        x0, y0, z0, x1, y1, z1 = (int(v) for v in p[1:7])
        state, mode = p[7], (p[8] if len(p) > 8 else None)
        filt = p[9] if len(p) > 9 else None
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    if mode == "replace" and filt and block_name(self.at(x, y, z)) != block_name(filt):
                        continue
                    if mode == "keep" and block_name(self.at(x, y, z)) != "minecraft:air":
                        continue
                    if mode in ("hollow", "outline") and not (x in (x0, x1) or y in (y0, y1) or z in (z0, z1)):
                        if mode == "hollow":
                            self.cells[(x, y, z)] = "minecraft:air"
                        continue
                    self.cells[(x, y, z)] = state


def misty_hall(G):
    """Gym 2: the donor template as placed, the donor's own commands, then the healer sweep and the dig."""
    import place_donor
    import gym_interiors as GI
    placements = load(PLACEMENTS)
    recs = {p["id"]: p for p in placements["placements"] if isinstance(p, dict) and p.get("id")}
    rec = recs["gym2_misty_gym"]
    if rec.get("rotation", "none") != "none" or rec.get("mirror", "none") != "none":
        raise SystemExit("gym2_misty_gym is rotated or mirrored; this model places it unturned only")
    zp = donor_zip()
    if not zp:
        raise SystemExit("gym 2 needs the donor template: set COBBLERS_DONOR_ZIP to COBBLEVERSE-DP-v31.zip")
    cells, size = template_cells(zp, rec["pack_template"])
    px, py, pz = (rec["position"][k] for k in "xyz")
    (lx, ly, lz), (hx, hy, hz) = place_donor.box(rec)

    def ground(x, y, z):
        return "minecraft:stone" if y <= G(x, z) else "minecraft:air"

    def placed(x, y, z):
        s = cells.get((x - px, y - py, z - pz))
        return s if s is not None else ground(x, y, z)

    r = Replay(placed)
    subs = load(POLICY)["substitutions"]
    for line in place_donor.commands(rec, subs):
        r.run(line)
    doc = load(INTERIORS)
    healers, _rows = GI.healer_commands(doc, recs)
    for line in healers.ops:
        r.run(line)
    gym = [g for g in doc["gyms"] if g["id"] == "gym2"][0]
    for line in GI.gym2_commands(gym, recs).ops:
        r.run(line)
    margin = 3
    rect = (lx - margin, lz - margin, hx + margin, hz + margin)
    ring = ring_columns(rect)
    y0 = min(min(gym["dig"][1], ly), min(G(x, z) for x, z in ring)) - 3
    y1 = hy + 4
    vox = Voxels((rect[0] - 1, y0, rect[1] - 1, rect[2] + 1, y1, rect[3] + 1), r.at)
    spawner = list(GI.to_world(rec, doc["measured"]["misty_relative"]["trainer_spawner"]))
    starts = [(x, G(x, z) + 1, z) for x, z in ring]
    return Hall("gym2", vox, starts, (spawner[0], spawner[1] + 1, spawner[2]), (lx, lz, hx, hz), rect,
                "kanto_misty")


def hall(gym, G=None, closures=()):
    """The gym's Hall. `closures` are [(defect id, [[x, y, z], ...])]: cells a recorded defect leaves open that the
    proof is run with closed, each one named in the report -- never silently."""
    import ground as ground_mod
    G = G or ground_mod.load()
    h = misty_hall(G) if gym == "gym2" else building_hall(gym, G)
    h.closed = []
    for did, cells in closures:
        for c in cells:
            x, y, z = c
            was = h.vox.cls(x, y, z)
            if (h.vox.x0 <= x <= h.vox.x1 and h.vox.y0 <= y <= h.vox.y1 and h.vox.z0 <= z <= h.vox.z1):
                h.vox.c[h.vox.i(x, y, z)] = SOLID
            h.closed.append((did, (x, y, z), was != SOLID))
    return h


def sky_positions(v):
    """Every position open to the sky: where a rider on a flying mount can set down (Cobblemon 1.8 riding)."""
    out = []
    for x in range(v.x0, v.x1 + 1):
        for z in range(v.z0, v.z1 + 1):
            for y in range(v.y1 - 1, v.y0, -1):
                if not v.passable(x, y + 1, z):
                    break
                if v.standable(x, y, z):
                    out.append((x, y, z))
                    if v.cls(x, y, z) not in (WATER, CLIMB, SCAF):
                        break
    return out


# ------------------------------------------------------------------------------------------------ the graph
def offsets(reach, deep):
    """[(dx, dz, dy)] jump landings in reach, excluding plain neighbours, nearest first."""
    out = []
    r = int(math.ceil(max(max(reach.values()), deep)))
    for dx in range(-r, r + 1):
        for dz in range(-r, r + 1):
            d = math.hypot(dx, dz)
            if d < 1.5:
                continue
            for dy in range(1, -8, -1):
                lim = reach.get(dy, deep if dy < -2 else None)
                if lim is not None and d <= lim:
                    out.append((dx, dz, dy))
    return sorted(out, key=lambda o: (math.hypot(o[0], o[1]), -o[2]))


def corridor_clear(v, a, b):
    """The jump's flight: every column the player's body (HALF_WIDTH either side of the straight line from a to b)
    sweeps is passable at the higher of the two feet levels and the head over it, and the take-off has jump room
    over the head. The body's width is what stops a jump squeezing between two blocks that meet at a corner."""
    if not v.passable(a[0], a[1] + 2, a[2]):
        return False
    h = max(a[1], b[1])
    n = int(math.ceil(math.hypot(b[0] - a[0], b[2] - a[2]) * 10))
    seen = set()
    for k in range(1, n):
        t = k / n
        px, pz = a[0] + 0.5 + (b[0] - a[0]) * t, a[2] + 0.5 + (b[2] - a[2]) * t
        for cx in {int(math.floor(px - HALF_WIDTH)), int(math.floor(px + HALF_WIDTH))}:
            for cz in {int(math.floor(pz - HALF_WIDTH)), int(math.floor(pz + HALF_WIDTH))}:
                if (cx, cz) in seen:
                    continue
                seen.add((cx, cz))
                for y in (h, h + 1):
                    if not v.passable(cx, y, cz):
                        return False
    for y in range(b[1], h + 2):
        if not v.passable(b[0], y, b[2]):
            return False
    return True


def fall_from(v, x, y, z):
    """Where a player who steps into the open cell (x, y, z) comes to rest, or None."""
    for d in range(MAX_DROP):
        yy = y - d
        if not v.passable(x, yy, z) or not v.passable(x, yy + 1, z):
            return None
        if v.standable(x, yy, z):
            return (x, yy, z)
    return None


DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Graph:
    """Positions and moves in one model over a Hall's voxels."""

    def __init__(self, h, generous=True, arrival="walk"):
        v = self.v = h.vox
        self.h = h
        reach, deep = (REACH, REACH_DEEP) if generous else (MODEST_REACH, MODEST_REACH_DEEP)
        self.nodes = [(x, y, z) for x in range(v.x0, v.x1 + 1) for z in range(v.z0, v.z1 + 1)
                      for y in range(v.y0 + 1, v.y1) if v.standable(x, y, z)]
        self.index = {p: k for k, p in enumerate(self.nodes)}
        jumps = offsets(reach, deep)
        adj = [[] for _ in self.nodes]
        long_moves = set()
        for k, (x, y, z) in enumerate(self.nodes):
            out = set()
            c = v.cls(x, y, z)
            for dx, dz in DIRS:
                q = (x + dx, y, z + dz)
                if q in self.index:
                    out.add(q)
                elif v.passable(*q) and v.passable(q[0], y + 1, q[2]):
                    r = fall_from(v, *q)
                    if r:
                        out.add(r)
                up = (x + dx, y + 1, z + dz)
                if up in self.index and (v.passable(x, y + 2, z) or c in (WATER, CLIMB, SCAF)):
                    out.add(up)
            if c in (CLIMB, WATER, SCAF) or v.cls(x, y - 1, z) == SCAF:
                for dy in (1, -1):
                    q = (x, y + dy, z)
                    if q in self.index:
                        out.add(q)
                    elif dy == -1 and v.passable(*q):
                        r = fall_from(v, *q)
                        if r:
                            out.add(r)
            if c == OPEN and v.cls(x, y - 1, z) == SOLID:
                for dx, dz, dy in jumps:
                    q = (x + dx, y + dy, z + dz)
                    if q in self.index and q not in out and corridor_clear(v, (x, y, z), q):
                        out.add(q)
            out.discard((x, y, z))
            adj[k] = [self.index[q] for q in out]
            for q in out:
                if not ((q[0], q[2]) == (x, z) or (abs(q[0] - x) + abs(q[2] - z) == 1 and q[1] == y)):
                    long_moves.add((k, self.index[q]))       # a jump, or a fall down a neighbouring column
        self.adj = adj
        self.long = long_moves
        arrive = list(h.ring) + (sky_positions(v) if arrival == "sky" else [])
        self.arrival = arrival
        self.starts = sorted({self.index[s] for s in arrive if s in self.index})
        lx, ly, lz = h.leader_stand
        # a player engages the leader by interacting with him: within reach AND in clear line of sight, so a wall
        # between them is not an engagement (rctmod's sight-forced battle is a separate matter: GYM_TRAINERS.md D2)
        self.goals = {k for k, (x, y, z) in enumerate(self.nodes)
                      if math.dist((x, y, z), (lx, ly, lz)) <= LEADER_REACH and los(v, (x, y, z), (lx, ly, lz))}
        if not self.starts:
            raise SystemExit("%s: no position on the arrival ring" % h.gym)

    def _split(self, blocked):
        if isinstance(blocked, Block):
            return blocked.nodes, blocked.edge
        return blocked, None

    def _ok(self, k, j, edge):
        """A move is refused by a Block's edge rule only when it is a jump or a fall: a step between neighbouring
        positions never leaves those two cells, so blocking the positions already covers it."""
        return edge is None or (k, j) not in self.long or not edge(self.nodes[k], self.nodes[j])

    def reach(self, blocked=frozenset()):
        """Distances (BFS, in moves) from the street to every position, never entering `blocked` (a set of
        positions, or a Block, which also refuses the jumps and falls that pass through what it blocks)."""
        nodes, edge = self._split(blocked)
        dist = {}
        q = deque()
        for s in self.starts:
            if s not in nodes:
                dist[s] = 0
                q.append(s)
        while q:
            k = q.popleft()
            for j in self.adj[k]:
                if j not in dist and j not in nodes and self._ok(k, j, edge):
                    dist[j] = dist[k] + 1
                    q.append(j)
        return dist

    def reaches_leader(self, blocked=frozenset()):
        d = self.reach(blocked)
        return any(g in d for g in self.goals)

    def path(self, blocked=frozenset()):
        """One shortest walk street -> leader, as node indices, or None."""
        nodes, edge = self._split(blocked)
        prev = {}
        q = deque()
        for s in self.starts:
            if s not in nodes:
                prev[s] = None
                q.append(s)
        while q:
            k = q.popleft()
            if k in self.goals:
                out = []
                while k is not None:
                    out.append(k)
                    k = prev[k]
                return out[::-1]
            for j in self.adj[k]:
                if j not in prev and j not in nodes and self._ok(k, j, edge):
                    prev[j] = k
                    q.append(j)
        return None

    def dominators(self):
        """Positions every walk street -> leader passes through, in walk order (Cooper-Harvey-Kennedy over the
        reachable graph with a super-source before the ring and a super-sink after the leader's positions)."""
        n = len(self.nodes)
        S, T = n, n + 1
        succ = {S: list(self.starts)}
        for k in range(n):
            succ[k] = list(self.adj[k]) + ([T] if k in self.goals else [])
        succ[T] = []
        order, seen, stack = [], {S}, [(S, iter(succ[S]))]
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                order.append(node)
                stack.pop()
            elif nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, iter(succ[nxt])))
        if T not in seen:
            return []
        rpo = order[::-1]
        pos = {v_: i for i, v_ in enumerate(rpo)}
        preds = {v_: [] for v_ in rpo}
        for u in rpo:
            for w in succ[u]:
                if w in preds:
                    preds[w].append(u)
        idom = {S: S}

        def inter(a, b):
            while a != b:
                while pos[a] > pos[b]:
                    a = idom[a]
                while pos[b] > pos[a]:
                    b = idom[b]
            return a
        changed = True
        while changed:
            changed = False
            for v_ in rpo[1:]:
                ps = [p for p in preds[v_] if p in idom]
                if not ps:
                    continue
                new = ps[0]
                for p in ps[1:]:
                    new = inter(p, new)
                if idom.get(v_) != new:
                    idom[v_] = new
                    changed = True
        chain, d = [], idom[T]
        while d != S:
            chain.append(d)
            d = idom[d]
        return chain[::-1]


# ------------------------------------------------------------------------------------------------ sight
def los_points(v, a, b, skip=()):
    """Clear line of sight between two points (floats): no solid cell on the segment but the ones in `skip`."""
    n = max(2, int(math.dist(a, b) * 5))
    for k in range(1, n):
        t = k / n
        c = (int(math.floor(a[0] + (b[0] - a[0]) * t)), int(math.floor(a[1] + (b[1] - a[1]) * t)),
             int(math.floor(a[2] + (b[2] - a[2]) * t)))
        if c in skip:
            continue
        if v.cls(*c) == SOLID:
            return False
    return True


def los(v, a, b):
    """Clear line of sight eye to eye between two positions."""
    return los_points(v, (a[0] + 0.5, a[1] + EYE, a[2] + 0.5), (b[0] + 0.5, b[1] + EYE, b[2] + 0.5),
                      skip=((a[0], a[1] + 1, a[2]), (b[0], b[1] + 1, b[2])))


# Where a player is, against where the graph says. A position is a cell; the player's feet are anywhere in its
# column's footprint (0.71 from the centre, horizontally) and up to half a block above its floor (a slab, a stair).
SLACK = 0.87


def sphere(g, seat, d):
    """Every position from which a player MIGHT be within d of the seat, through walls: the most rctmod's sight
    check can reach. Used where over-counting is the safe side (the leader, street and apart checks)."""
    sx, sy, sz = seat
    r = int(math.ceil(d + SLACK))
    out = set()
    for x in range(sx - r, sx + r + 1):
        for y in range(sy - r, sy + r + 1):
            for z in range(sz - r, sz + r + 1):
                k = g.index.get((x, y, z))
                if k is not None and math.dist((x, y, z), seat) <= d + SLACK:
                    out.add(k)
    return out


def seen(g, seat, d):
    """Every position at which a player IS within d of the seat wherever in it they stand, in clear line of sight:
    the least rctmod's sight check reaches. Used where under-counting is the safe side (the cut)."""
    sx, sy, sz = seat
    r = int(math.ceil(d))
    out = set()
    for x in range(sx - r, sx + r + 1):
        for y in range(sy - r, sy + r + 1):
            for z in range(sz - r, sz + r + 1):
                k = g.index.get((x, y, z))
                if k is not None and math.dist((x, y, z), seat) <= d - SLACK and los(g.v, seat, (x, y, z)):
                    out.add(k)
    return out


class Block:
    """Positions a walk may not enter, and a rule refusing the jumps and falls that pass through what is blocked
    on the way between two positions that are not."""

    def __init__(self, nodes, edge=None):
        self.nodes, self.edge = frozenset(nodes), edge


def sight_block(g, seat, d):
    """The cut's block: the positions surely in sight, and every jump or fall during which the player is surely
    within d of the seat in clear line of sight at some moment."""
    v = g.v
    sx, sy, sz = seat
    eye = (sx + 0.5, sy + EYE, sz + 0.5)

    def surely(px, pz, h_lo, h_hi, side):
        hd = math.hypot(px - eye[0], pz - eye[2]) + side
        vd = max(abs(h_lo - sy), abs(h_hi - sy))
        if math.hypot(hd, vd) > d:
            return False
        return all(los_points(v, eye, (px, h + EYE, pz), skip=((sx, sy + 1, sz),)) for h in (h_lo, h_hi))

    def edge(a, b):
        if math.hypot(b[0] - a[0], b[2] - a[2]) >= 1.5:          # a jump: anywhere on the line, any height of the arc
            lo, hi = min(a[1], b[1]), max(a[1], b[1]) + 1.25
            n = int(math.ceil(math.hypot(b[0] - a[0], b[2] - a[2]) * 4))
            for k in range(1, n):
                t = k / n
                if surely(a[0] + 0.5 + (b[0] - a[0]) * t, a[2] + 0.5 + (b[2] - a[2]) * t, lo, hi, 0.3):
                    return True
            return False
        # a step up (over the take-off, then onto the next column) or a fall (down the next column): each height
        # in the column is passed at some moment, somewhere in the column's footprint
        cols = [((a[0], a[2]), range(a[1], max(a[1], b[1]) + 1)),
                ((b[0], b[2]), range(min(a[1], b[1]), max(a[1], b[1]) + 1))]
        return any(surely(cx + 0.5, cz + 0.5, h, h, 0.71) for (cx, cz), hs in cols for h in hs)

    return Block(seen(g, seat, d), edge)


def body(g, seat):
    x, y, z = seat
    return {g.index[p] for p in ((x, y, z), (x, y + 1, z)) if p in g.index}


def body_block(g, seat):
    """The softlock check's block: the junior's two cells, which no walk, jump or fall can pass through."""
    sx, sy, sz = seat
    cells = {(sx, sy, sz), (sx, sy + 1, sz)}

    def edge(a, b):
        if math.hypot(b[0] - a[0], b[2] - a[2]) < 1.5:
            col = (b[0], b[2]) == (sx, sz) or (a[0], a[2]) == (sx, sz)
            return col and min(a[1], b[1]) <= sy + 1 and max(a[1], b[1]) + 1 >= sy
        h = max(a[1], b[1])
        n = int(math.ceil(math.hypot(b[0] - a[0], b[2] - a[2]) * 10))
        for k in range(1, n):
            t = k / n
            px, pz = a[0] + 0.5 + (b[0] - a[0]) * t, a[2] + 0.5 + (b[2] - a[2]) * t
            for cx in {int(math.floor(px - HALF_WIDTH)), int(math.floor(px + HALF_WIDTH))}:
                for cz in {int(math.floor(pz - HALF_WIDTH)), int(math.floor(pz + HALF_WIDTH))}:
                    if (cx, h, cz) in cells or (cx, h + 1, cz) in cells:
                        return True
        return False

    return Block(body(g, seat), edge)


def yaw_towards(seat, target):
    dx, dz = target[0] - seat[0], target[2] - seat[2]
    return int(round(math.degrees(math.atan2(-dx, dz))))


# ------------------------------------------------------------------------------------------------ checks
def in_rect(p, rect):
    return rect[0] <= p[0] <= rect[2] and rect[1] <= p[2] <= rect[3]


def check_seat(h, gen, mod, seat, d, mod_baseline=None):
    """[(code, message)] for one seat at sight distance d. Empty is a proof."""
    bad = []
    v = h.vox
    if tuple(seat) not in gen.index or not v.dry_footing(*seat):
        bad.append(("stand", "%s is not a dry position on solid footing" % (list(seat),)))
        return bad
    if not in_rect(seat, h.footprint):
        bad.append(("stand", "%s is outside the hall's footprint %s" % (list(seat), list(h.footprint))))
    if (mod_baseline if mod_baseline is not None else mod.reaches_leader()):
        if not mod.reaches_leader(body_block(mod, seat)):
            bad.append(("softlock", "with the junior standing at %s the MODEST player can no longer reach the "
                                    "leader: the seat is the way through" % (list(seat),)))
    else:
        if not gen.reaches_leader(body_block(gen, seat)):
            bad.append(("softlock", "with the junior standing at %s even the GENEROUS player cannot reach the "
                                    "leader" % (list(seat),)))
    s = sight_block(gen, seat, d)
    if gen.reaches_leader(s):
        p = gen.path(s)
        bad.append(("cut", "a walk reaches the leader without entering the junior's sight (%s, d %.1f), e.g. via %s"
                           % (list(seat), d, [list(gen.nodes[k]) for k in p[::max(1, len(p) // 6)]])))
    full = sphere(gen, seat, d)
    if full & gen.goals:
        bad.append(("leader", "the sight sphere reaches %d position(s) from which the leader is engaged"
                              % len(full & gen.goals)))
    out = [gen.nodes[k] for k in full if not in_rect(gen.nodes[k], h.footprint)]
    if out:
        bad.append(("street", "the sight sphere reaches %d position(s) outside the hall's footprint, e.g. %s"
                              % (len(out), list(out[0]))))
    return bad


RADII = (2.5, 3.0, 3.5, 4.0, 4.5, 5.0)


def candidates(h, gen, mod, radii=RADII):
    """Every seat near the shortest walk whose sight cuts the leader off, at the smallest sight distance that does,
    and that passes every other per-seat check: [(first-reached moves, d, seat)]. A cut must touch every walk, the
    shortest among them, so only seats within the largest radius of that walk are tried."""
    v = h.vox
    path = gen.path()
    if not path:
        return []
    dist = gen.reach()
    base = mod.reaches_leader()
    r = radii[-1]
    near = set()
    for k in path:
        px, py, pz = gen.nodes[k]
        R = int(math.ceil(r))
        for x in range(px - R, px + R + 1):
            for z in range(pz - R, pz + R + 1):
                for y in range(py - R, py + R + 1):
                    s = (x, y, z)
                    if s in gen.index and math.dist(s, (px, py, pz)) <= r and v.dry_footing(*s) \
                            and in_rect(s, h.footprint):
                        near.add(s)
    found = []
    for s in sorted(near):
        if gen.reaches_leader(sight_block(gen, s, r)):
            continue                                   # not even the widest sight cuts it
        d = next(d for d in radii if not gen.reaches_leader(sight_block(gen, s, d)))
        if check_seat(h, gen, mod, s, d, base):
            continue
        reached = [dist[k] for k in seen(gen, s, d) if k in dist]
        found.append((min(reached), d, s))
    return sorted(found)


# ------------------------------------------------------------------------------------------------ the record
def records():
    doc = load(DATA)
    if doc.get("schema") != SCHEMA:
        raise SystemExit("data/gym_junior_trainers.json: schema %r, expected %r" % (doc.get("schema"), SCHEMA))
    return doc


def roster():
    return {r["id"]: r for r in load(TRAINERS)["trainers"]}


def gym_config(gym, doc=None):
    """(arrival, closures) the record declares for one gym: how a player arrives for the proof, and which recorded
    defects the proof runs with closed."""
    if doc is None:
        doc = records() if DATA.exists() else {"gyms": {}}
    g = (doc.get("gyms") or {}).get(gym) or {}
    return g.get("arrival", "walk"), [(c["defect"], c["cells"]) for c in g.get("assume_closed") or []]


def built(gym, G, doc=None):
    arrival, closures = gym_config(gym, doc)
    h = hall(gym, G, closures)
    return h, Graph(h, True, arrival), Graph(h, False, arrival), arrival


def check_gym(gym, seats, recs, G=None, verbose=False):
    """(problems, report row) for one gym's authored seats."""
    h, gen, mod, arrival = built(gym, G)
    problems = []
    if not gen.reaches_leader():
        problems.append((gym, "-", "unreachable", "the GENEROUS player cannot reach the leader at all"))
    base = mod.reaches_leader()
    rows = []
    spheres = {}
    first = gen.reach()
    for s in seats:
        seat = tuple(s["seat"])
        for code, msg in check_seat(h, gen, mod, seat, float(s["sight_distance"]), base):
            problems.append((gym, s["id"], code, msg))
        # apart: no position where two juniors would BOTH surely force a fight. rctmod starts one battle at a time,
        # so an overlap of the outer spheres is spacing, not a fault; an overlap of the cores is two juniors doing
        # one junior's job
        spheres[s["id"]] = seen(gen, seat, float(s["sight_distance"]))
        sight = [k for k in seen(gen, seat, float(s["sight_distance"])) if k in first]
        entry = min(sight, key=lambda k: (first[k], gen.nodes[k])) if sight else None
        r = recs.get(s["id"])
        top = max(m["level"] for m in r["team"]) if r else None
        rows.append({"id": s["id"], "seat": list(seat), "yaw": s.get("yaw"), "sight_distance": s["sight_distance"],
                     "first_reached_moves": first[entry] if entry is not None else None,
                     "first_seen_at": list(gen.nodes[entry]) if entry is not None else None,
                     "yaw_to_first_seen": yaw_towards(seat, gen.nodes[entry]) if entry is not None else None,
                     "top_level": top})
        if s.get("yaw") is not None and entry is not None:
            off = abs((s["yaw"] - yaw_towards(seat, gen.nodes[entry]) + 180) % 360 - 180)
            if off > 90:
                problems.append((gym, s["id"], "facing", "yaw %s faces away from where a player first enters its "
                                 "sight (%s, yaw %d)" % (s["yaw"], list(gen.nodes[entry]),
                                                         yaw_towards(seat, gen.nodes[entry]))))
        if r is None:
            problems.append((gym, s["id"], "roster", "data/trainers.json has no record"))
    # information, never a pass/fail: what a rider on a flying mount does to each cut (Cobblemon 1.8 riding sets a
    # player down anywhere open to the sky), and what each cut is worth while the recorded defects stay open
    sky = gen if arrival == "sky" else Graph(h, True, "sky")
    open_gen = None
    if h.closed:
        h0 = hall(gym, G)
        open_gen = Graph(h0, True, arrival)
    for row, s in zip(rows, seats):
        seat, d = tuple(s["seat"]), float(s["sight_distance"])
        row["cut_holds_for_a_flyer"] = not sky.reaches_leader(sight_block(sky, seat, d))
        if open_gen is not None:
            row["cut_holds_with_defects_open"] = not open_gen.reaches_leader(sight_block(open_gen, seat, d))
    ids = list(spheres)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            both = spheres[ids[i]] & spheres[ids[j]]
            if both:
                problems.append((gym, ids[i], "apart", "%d position(s) surely inside both %s's and %s's sight"
                                 % (len(both), ids[i], ids[j])))
    ace = max(m["level"] for m in recs[LEADERS[gym]]["team"])
    order = sorted(rows, key=lambda r: (r["first_reached_moves"] if r["first_reached_moves"] is not None else 1e9))
    last = 0
    for r in order:
        if r["top_level"] is None:
            continue
        if r["top_level"] >= ace:
            problems.append((gym, r["id"], "order", "tops out at %d, not below the leader's ace %d"
                             % (r["top_level"], ace)))
        if r["top_level"] < last:
            problems.append((gym, r["id"], "order", "tops out at %d but is reached after a junior topping at %d"
                             % (r["top_level"], last)))
        last = max(last, r["top_level"])
    return problems, {"gym": gym, "arrival": arrival,
                      "assumed_closed": [{"defect": d_, "cell": list(c_), "open_as_built": o_}
                                         for d_, c_, o_ in h.closed],
                      "leader": h.leader_id, "leader_stand": list(h.leader_stand), "leader_ace": ace,
                      "footprint": list(h.footprint), "positions_generous": len(gen.nodes),
                      "positions_modest": len(mod.nodes), "modest_reaches_leader": base,
                      "juniors_in_pass_order": [r["id"] for r in order], "juniors": rows}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("propose")
    q.add_argument("--gym", required=True, choices=GYMS)
    q.add_argument("--per", type=int, default=3, help="candidate seats printed per chokepoint")
    c = sub.add_parser("check")
    c.add_argument("--gym", default=None, choices=GYMS)
    a = p.parse_args(argv)
    import ground as ground_mod
    G = ground_mod.load()

    if a.cmd == "propose":
        h, gen, mod, arrival = built(a.gym, G)
        print("%s (arrival %s, closed %s): %d generous positions, %d modest; generous reaches the leader: %s; "
              "modest: %s" % (a.gym, arrival, sorted({c[0] for c in h.closed}), len(gen.nodes), len(mod.nodes),
                              gen.reaches_leader(), mod.reaches_leader()))
        chain = [k for k in gen.dominators() if k not in gen.goals and k not in gen.starts]
        print("single-cell chokepoints: %s" % [list(gen.nodes[k]) for k in chain])
        path = gen.path()
        print("shortest generous walk (%d moves): %s" % (len(path) - 1, [list(gen.nodes[k]) for k in path]))
        cands = candidates(h, gen, mod)
        print("%d proven seats (first reached at, sight, seat, yaw to the leader):" % len(cands))
        by = {}
        for m, d, s in cands:
            by.setdefault(m, []).append((d, s))
        for m in sorted(by):
            best = sorted(by[m])[:a.per]
            print("  %3d moves: %s" % (m, "; ".join("%s d%.1f" % (list(s), d) for d, s in best)))
        return 0

    doc = records()
    recs = roster()
    gyms = [a.gym] if a.gym else list(GYMS)
    problems, report = [], []
    for gym in gyms:
        seats = [s for s in doc["trainers"] if s["gym"] == gym]
        if not seats:
            problems.append((gym, "-", "count", "no junior seated"))
            continue
        pr, row = check_gym(gym, seats, recs, G)
        problems += pr
        report.append(row)
        print("%s: %d junior(s), %s" % (gym, len(seats), "proved" if not pr else "%d problem(s)" % len(pr)))
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / ("report%s.json" % ("_" + a.gym if a.gym else ""))).write_text(
        json.dumps({"gyms": report, "problems": [list(x) for x in problems]}, indent=1) + "\n", encoding="utf-8")
    for x in problems:
        print("PROBLEM %s %s [%s] %s" % x)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
