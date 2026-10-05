#!/usr/bin/env python
"""Idle Pokemon in the towns: Pokemon that are simply there -- asleep in a yard, sitting by a door or on a bench,
loafing on the square, pottering round a townsperson -- from data/ambient.json `idle`, as the world pack
build/datapacks/cobblers_ambient_idle. The working Pokemon (tools/ambient.py) stay as they are.

The owner, 2026-10-03/04: "MORE AMBIENT POKEMON PER TOWN ... Not all of them need jobs. Some should just be there --
sleeping on a roof, sitting by a door, following a kid around. A town with one working Pokemon and six idle ones reads
better than seven all hauling things"; "ambient Pokemon per town at the cap the frame-rate test supports, with sleeping
ones that wake at 16 blocks"; "Buneary around the snow house".

The kinds, and what each rests on:

  sitter    still, by a door (facing out of it) or ON a plaza bench's seat (facing the way the bench faces)
  loafer    still, on the square (facing its middle), by a door or in a yard (facing away from its house)
            Both are held exactly as a working Pokemon is held (tools/ambient.py, EXP-046, measured): spawned
            `uncatchable no_ai` through a macro, claimed in the same function, PersistenceRequired, Invulnerable,
            Unbattleable; NoAI, so no gravity and no walking; the keeper puts it back on its spot (a tp) every keep.
            MEASURED (pose test 2026-10-03): no command or NBT gives a sitting or lying pose, so a "sitter" stands.
  sleeper   AI ON, with a custom behaviour list (`BehavioursAreCustom`, `Behaviours`) that is the exact list a Snorlax
            slept under in daylight on staging (2026-10-03, the session's `data merge`): Cobblemon's own
            cobblemon:pokemon_sleeps (find_resting_place, sleep, wake_up), no wander. Only species that can sleep in
            a lit town by day (rules.sleeps_by_day, read from the 1.8.0 jar: canSleep, a light range reaching 12+,
            times day or any) -- a night sleeper (light 0-4) never sleeps under a town's lanterns. It falls asleep
            and wakes on its own (drowsyChance / rouseChance per 20-tick sensor pass: a Snorlax dozes off in about a
            minute and sleeps about 18; a Slowpoke about 6 and 4). Held near home by the keeper: beyond
            sleeper_leash it is put back (a tp).
  follower  AI ON, cobblemon:wanders (proven live: dropping it stopped an Eevee wandering) plus cobblemon:stationary,
            Cobblemon's home walk (jar data/cobblemon/behaviours/stationary.json and molang/home_walk_task.molang:
            every 20 ticks, idle, no walk target, further than home_radius from home_x/y/z -> walk_to home), with the
            home written into `ScriptingConfig` as doubles (MoLangScriptingEntity.loadScriptingFromNBT reads
            ScriptingConfig through MoLangFunctions.readMoValueFromNBT: a DoubleTag becomes a number, a compound a
            struct). Its home is beside a townsperson (data/npc_seats.json) or a market stall's keeper where the town
            has one, so it potters round them. Following an NPC itself is NOT possible natively:
            cobblemon:pokemon_follows_owner's move_to_owner needs the Pokemon's OWNER, a player. Beyond
            follower_leash the keeper puts it back.

Waking at 16 blocks (the owner's rule). What Cobblemon does natively, read from the 1.8.0 jar: DrowsySensor (every 20
ticks) sets and clears the POKEMON_DROWSY memory from canSleep, the species' times, two vanilla memories and the
drowsy/rouse chances; WakeUpTask wakes a sleeping Pokemon once it is no longer drowsy. SleepDepth "normal" defines
shouldWake = a non-sneaking player inside a 16-block box round it -- but in 1.8.0 NOTHING CALLS shouldWake (the only
classes naming it are SleepDepth and its two implementations), so no player wakes a sleeper natively. So the keeper
does it: every wake_every ticks a sleeper tagged `cobblers.amb.dozer` with a player within wake_radius gets the awake
list (the same without cobblemon:pokemon_sleeps) and the tag `cobblers.amb.woken`; once no player is within
rest_radius it gets the sleeper list back. Writing `Behaviours` remakes the brain (PokemonEntity calls remakeBrain()
after an NBT load), which drops the sleeping memory; with AI on a sleep status runs out in seconds (measured
2026-10-03), and a sleep status alone shows no pose (measured). UNPROVEN: that the remake clears the pose at once in
game. Because any `data merge` remakes the brain, the keeper never merges a sleeper except to wake or settle it.

Where they stand: the town plan and the build model, never a world (CLAUDE.md). The ground is tools/ground.py
(rounded), a street's or the plaza's own paved y where the plan grades one. A spot is refused inside a building grown
by building_margin, on a lamp, under a dressing piece, a plaza piece (and its stall's keeper and customer cells), an
earthwork, a shrine, a working Pokemon's cells (grown), or near ground the water export changes; on a STREET (the
town plan's paved cells and data/placements.json's street polylines brushed at their width, or a planless town's
roads), on a walked route line, or on one of the square's walking lines (tools/plaza_centre.py's street mouths, door
aprons and desire lines); within one cell of ANY NPC the apply places (data/npc_seats.json, data/markets.json's
counters and stalls, and every npc and trainer item of tools/reapply.py's steps) -- so at least 2 from each; and on
any cell the BUILT town does not leave open: tools/npc_spot_sweep.py's replay (another agent's tool) of every fill,
setblock and `place template` every built pack runs (signposts, waystones, fences, porches, stalls, roofs) must
classify the feet cell `outside` (a bench seat: `pedestal` too), with no door in or orthogonally beside it, and a
still idler's body (the jar's hitbox x baseScale) clear of every solid cell. A door anchor whose own cell is refused
(the spot building_margin + 1 out from the door usually lands on the street the door faces) is not dropped: the nearest
open cell beside it is taken. So the build needs every other pack built first (reapply.py prepare runs it after them).
Unlike a worker, an idler may stand in a yard (a house lot outside its building). Groups of 1-3 (rules.group_sizes)
at spots at least group_gap apart: the frame-rate test found spread, not count, is what a client pays for.

Sleepers by day: canSleepAt compares the spot's light (PokemonEntity.canSleepAt, method_8317 in the 1.8.0 jar; which
light that is -- total brightness or the block's own emission -- is not settled here) with the species' range, so a day
sleeper is a species whose range holds BOTH open sky by day (15) and a block that emits nothing (0), with times day or
any: rules.sleeps_by_day.species filtered here, never by hand. A species in that table that fails either reading is
refused as a sleeper.

Followers stand only beside a placed NPC (rules.prefer.follower is ["npc"]): within follower_home_radius + 1 of it
(the disc it potters in touches the NPC) and at least 2 cells from it.

Two groups are not towns and are placed by their own place's plan, not the town model: the snow house's Buneary
(place_buneary) and, since 2026-10-05, Arrow Creeks Farm's livestock (tools/pokemon_farm.py idlers, group
"pokemon_farm"): stalled animals are loafers, grazing ones followers homed inside a fenced pen rather than beside an
NPC, and the wool flock's follower list adds cobblemon:pokemon_eats_grass (an idler's own `behaviours`, which the
claim writes in place of rules.behaviours.follower).

Not covered: a tree or a bush in a yard (the export's foliage: the replay has no trees), blocks a function writes by
relative coordinates (the replay skips them), NPCs spawned at runtime or by relative coordinates, anything a player
built. Roofs: NO roof sleepers -- a ridge of stairs is not a place to sleep.

Composed towns (data/ambient.json `composition`, the owner 2026-10-05: "fix it by composition"). A settlement with a
town file data/ambient_towns/<settlement>.json (or one in --towns-dir) is composed by it, and its idle.towns entry is
not read. Every Pokemon of the file is placed where the file says or the build fails naming the town, the record and
the rule; in the plan each carries `town`, `kind` (the keeper's: still / sleeper / follower), `role` (pet | placed |
situation; the workers are tools/ambient.py's plan) and `species`, and a situation's members `situation`:
  pets        `owner` an NPC the apply places in or near the town (data/npc_seats.json, data/markets.json, every npc
              and trainer of reapply.py's steps). follow: a follower homed in the ring round it (within
              follower_home_radius + 1, never next to it); wait: a still hold in the nearest open ring cell, facing it.
  placed      `spot` on `building` (a derived/towns/<settlement>_placement.json building id), resolved from that
              building's template as tools/place_town.py placed it (TownBuildings: the template file from
              data/placements.json, command_position, origin_y, rotation; checked to land on its recorded footprint):
                roof      the highest roof column nearest the middle (a top 3+ above the floor), on it
                gutter    the eave on `side` (default the side the door faces): the outermost roof column, nearest middle
                window    behind a glass block with open air outside and the building's air inside, at the lowest glass,
                          facing out (prefers the door's side); its height is capped at the glass run's
                step      out of the door to the first open cell, then one to the side (the door stays clear)
                porch     a covered floor cell with two open blocks over it within 2 of the door's side, open outward,
                          not in front of a door
                wall_top  on a wall or fence of the template standing a block or more above the floor
                under_cart never resolved: needs `at`
              or at an explicit `at` [x, y, z] (feet y) measured from the plan. roof, gutter and window need a species
              that fits (composition.spot_fit, the jar's hitbox x baseScale). Optional `side`, `facing`, `props`
              (blocks at offsets from the spot; the body must clear them), `allow`.
  situations  `at` [x, y, z] the anchor, feet y, which must be the plan's ground there (the settlement's own ground
              for the cavern and the sea decks, a street's or the square's paving, within 1) or the top of one of the
              town's buildings; members {species, count, pose, offsets [[dx, dy, dz]]} from it: still (NoAI hold),
              sleep (a day sleeper only), follow (homed on the anchor: the situation's home_radius / leash), wander_leashed
              (homed on its own spot, composition.poses.wander_leashed); props {block, at: [dx, dy, dz]} set by the
              town's t/<s>/props (run by R16C before the town settles) and taken out by t/<s>/cleanup.
Every placed Pokemon and situation member: its body clear of every building block of the town (and, in `build`, of the
built town); at ground level, not beside an NPC, not on a worker's cells, not near water the export changes, and not
on a street, walked route line or one of the square's walking lines unless the record's `allow` says "street" or
"walkway". Then, over the whole town with its workers: the count rules (tools/ambient.py composition_problems: band,
target, tally, working share), no two of one species within variety.same_species_group_radius outside one situation
(workers at their stations, blink spots and a carrier's two ends), and at most ceiling.in_view_max within
ceiling.in_view_radius of any standing point (the plan's street cells, the square, the street polylines; workers at
their start). NOT enforced here (the independent audit's): the pets/placed/situations shares, the variety rules across
towns.

  python tools/ambient_idle.py build [--source-root <root>] [--towns-dir <dir>]   # the pack and derived/ambient/idle_plan.json
  python tools/ambient_idle.py compose [--towns-dir <dir>] [--json <out>]         # the composed towns only, no built packs
  python tools/ambient_idle.py report                          # per-town counts and the keeper cost, from the plan
  python tools/ambient_idle.py verify --rcon --server-dir <server>

reapply.py prepare builds this pack in its own job (ambient_idle:build), after every pack it replays. The
re-application: reapply.py R16C settles each town (force-loads it, runs its keeper twice) and checks every idler with
verify.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import shutil
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402

DATA = ROOT / "data" / "ambient.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_ambient_idle"
PLAN = ROOT / "derived" / "ambient" / "idle_plan.json"
NS, FOLDER = "cobblers", "ambient_idle"
F = "%s:%s" % (NS, FOLDER)
OBJ = "cobblers_ambi"
TAG = "cobblers.amb"              # shared with the workers: each side's claim skips anything already tagged
IDLE = "cobblers.amb.idle"
DOZER = "cobblers.amb.dozer"      # a sleeper whose list has cobblemon:pokemon_sleeps
WOKEN = "cobblers.amb.woken"      # a sleeper kept awake while a player is near
KINDS = ("sitter", "loafer", "sleeper", "follower")     # what idle.towns may author
STILL = ("sitter", "loafer", "still")                   # held NoAI on their spot ("still": a composed town's)
IDLER_KINDS = KINDS + ("still",)
SPOTS = ("roof", "gutter", "window", "under_cart", "step", "wall_top", "porch")
POSES = {"still": "still", "sleep": "sleeper", "follow": "follower", "wander_leashed": "follower"}
PET_MODES = {"follow": "follower", "wait": "still"}
IID = re.compile(r"[a-z0-9_]+")
SPECIES_ID = re.compile(r"[a-z0-9_]+")
BLOCK = re.compile(r"[a-z0-9_.-]+:[a-z0-9_/.-]+(\[[a-z0-9_]+=[a-z0-9_]+(,[a-z0-9_]+=[a-z0-9_]+)*\])?")
AIRS = ("minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:structure_void")
YAW = {"south": 0.0, "west": 90.0, "north": 180.0, "east": 270.0}
NORMAL = {"south": (0, 1), "north": (0, -1), "east": (1, 0), "west": (-1, 0)}
BUNEARY_TOWN = "lopunny_house"
PACKS = ROOT / "build" / "datapacks"
NPC_CLEAR = 1                     # an idler is never within this many cells (Chebyshev) of an NPC: at least 2 from it
WALK_SOFT = ("street mouth", "door apron", "desire line", "street verge")   # the square's walking lines
SKIP_STEPS = False                # set while this build reads reapply.steps(): its own R16C steps need the plan it makes


class IdleError(SystemExit):
    pass


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def num(v):
    s = "%.2f" % v
    return s.rstrip("0").rstrip(".") if "." in s else s


def yaw_to(ax, az, bx, bz):
    """Minecraft yaw facing from (ax, az) towards (bx, bz): 0 south (+z), 90 west (-x)."""
    return (math.degrees(math.atan2(-(bx - ax), bz - az)) + 360.0) % 360.0


def h32(*parts):
    return zlib.crc32(":".join(str(p) for p in parts).encode())


def rect_cells(r, m=0):
    x0, z0, x1, z1 = r
    return {(x, z) for x in range(min(x0, x1) - m, max(x0, x1) + m + 1)
            for z in range(min(z0, z1) - m, max(z0, z1) + m + 1)}


def grow(cells, m):
    return {(x + dx, z + dz) for x, z in cells for dx in range(-m, m + 1) for dz in range(-m, m + 1)}


def day_sleepers(rules):
    """The species that sleep in a lit town by day under BOTH readings of canSleepAt's light: from the jar's table in
    rules.sleeps_by_day.species ("lo-hi times"), those whose range holds 0 and 15 and whose times are day or any."""
    out = set()
    for sp, v in rules["sleeps_by_day"]["species"].items():
        rng, _, times = v.partition(" ")
        lo, hi = (int(n) for n in rng.split("-"))
        if lo <= 0 and hi >= 15 and times.strip() in ("day", "any"):
            out.add(sp)
    return out


def street_cells(settlement, doc):
    """data/placements.json's street polylines for one settlement, brushed at width // 2 each side."""
    cells = set()
    pdata = (doc["settlements"].get(settlement) or {}).get("plan") or {}
    for st in pdata.get("streets") or []:
        half = int(st.get("width", 1)) // 2
        pts = st.get("polyline") or []
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            n = int(max(abs(bx - ax), abs(bz - az))) + 1
            for i in range(n + 1):
                cx, cz = round(ax + (bx - ax) * i / n), round(az + (bz - az) * i / n)
                cells |= {(cx + dx, cz + dz) for dx in range(-half, half + 1) for dz in range(-half, half + 1)}
    return cells


_CACHE = {}


def walked_lines():
    """{route id: [(x, z)]} data/route_paths.json, the walked route lines."""
    if "walked" not in _CACHE:
        d = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))
        _CACHE["walked"] = {k: [tuple(p[:2]) for p in v] for k, v in d["paths"].items()}
    return _CACHE["walked"]


def plaza_walkways(settlement, doc, ground):
    """{(x, z): why} the square's walking lines as tools/plaza_centre.py marks them for its pieces (street mouths, door
    aprons, desire lines, a street's verge over the square), for a settlement data/plaza_centres.json dresses."""
    import plaza_centre as PC
    if "plaza" not in _CACHE:
        _CACHE["plaza"] = (json.loads((ROOT / "data" / "plaza_centres.json").read_text(encoding="utf-8"))["towns"],
                           PC.refs_of())
    recs, refs = _CACHE["plaza"]
    if settlement not in recs:
        return {}
    town = PC.Town(settlement, dict(recs[settlement], _town=settlement), doc,
                   PC.ground_for(settlement, ground, doc, None), refs)
    out = {c: w for c, w in town.soft.items() if w.startswith(WALK_SOFT)}
    out.update({c: w for c, w in town.why.items() if w in ("street", "street verge") and c in set(PC.rect_cells(town.rect))})
    return out


class Built:
    """The towns as the apply builds them: tools/npc_spot_sweep.py's replay (another agent's tool) of every fill,
    setblock and `place template` in tools/reapply.py's step order, from the built packs, on the canonical heightmap,
    over boxes round the cells an idler could be given."""

    def __init__(self, packs, ground, cells, steps):
        import npc_spot_sweep as SW
        self.SW = SW
        tiles = {}
        for (x, z), ys in cells.items():
            k = (x >> 4, z >> 4)
            lo, hi = tiles.get(k, (10 ** 9, -10 ** 9))
            tiles[k] = (min(lo, min(ys)), max(hi, max(ys)))
        boxes = [(tx * 16 - 2, lo - SW.BOX_DOWN, tz * 16 - 2, tx * 16 + 17, hi + SW.BOX_UP, tz * 16 + 17)
                 for (tx, tz), (lo, hi) in sorted(tiles.items())]
        self.m = SW.Model(ground, boxes)
        self.lines = SW.replay(self.m, SW.Function(packs), SW.Templates(packs), steps)
        self.sizes = species_sizes()

    def refuses(self, x, y, z, species=None, seat=False):
        SW, m = self.SW, self.m
        fy = int(math.floor(y)) + (1 if seat else 0)
        cls, detail = SW.classify(m, x, fy, z)
        if seat and cls == "pedestal":
            cls = "outside"
        if cls != "outside":
            return "%s: %s" % (cls, detail)
        for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (-1, 0, 1):
                n = SW.short(m.at(x + dx, fy + dy, z + dz))
                if "_door" in n and "trapdoor" not in n:
                    return "in or beside a door"
        if species and self.sizes is not None:
            return self.body(x + 0.5, y, z + 0.5, self.sizes.get(species, (1.0, 2.0)), seat)
        return None

    def body(self, px, y, pz, size, skip_support=False):
        """Why a body of `size` (width, height) centred at (px, pz) with its feet at y meets a solid block of the built
        town, or None. skip_support: the cell its feet are sunk into (a seat, a slab) is not counted."""
        for c in body_cells(px, y, pz, size, skip_support):
            st = self.m.at(*c)
            if self.SW.solid(st):
                return "its body (%.1f x %.2f) meets %s at %s" % (size[0], size[1], self.SW.short(st), c)
        return None


def body_cells(px, y, pz, size, skip_support=False):
    """Every block cell a body of `size` (width, height) centred at (px, pz), feet at y, stands in: the jar's hitbox
    as Built.refuses reads it. skip_support leaves out the cell the feet are sunk into when y is not whole."""
    w, h = size
    hw = w / 2.0
    out = []
    for cx in range(math.floor(px - hw + 1e-6), math.floor(px + hw - 1e-6) + 1):
        for cz in range(math.floor(pz - hw + 1e-6), math.floor(pz + hw - 1e-6) + 1):
            for cy in range(math.floor(y), math.floor(y + h - 1e-6) + 1):
                if skip_support and cy == math.floor(y) and y != math.floor(y):
                    continue
                out.append((cx, cy, cz))
    return out


def species_sizes():
    """{species: (width, height)} the jar's hitbox x baseScale, or None with no Cobblemon jar here (the body check is
    then skipped and the build says so)."""
    import zipfile
    try:
        import battle_sim
        jar = battle_sim.find_jar()
    except (SystemExit, ImportError):
        return None
    out = {}
    with zipfile.ZipFile(jar) as z:
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                d = json.loads(z.read(n))
                hb = d.get("hitbox") or {"width": 1.0, "height": 1.0}
                s = float(d.get("baseScale", 1))
                out[n.rsplit("/", 1)[1][:-5]] = (float(hb["width"]) * s, float(hb["height"]) * s)
    return out


def load_steps(packs):
    """tools/reapply.py's steps over `packs`, with this pack's own R16C steps left out (they need the plan being made)."""
    import npc_spot_sweep as SW
    import ambient_idle as me
    me.SKIP_STEPS = True
    try:
        return SW.load_steps(packs)
    finally:
        me.SKIP_STEPS = False


# ------------------------------------------------------------------------------------------------ the site of a town

class TownSite:
    """What an idler may stand on in one settlement: tools/ambient.py's worker site, with the yards opened (a lot
    outside its building grown by building_margin) and the plaza pieces, townspeople, shrines and workers closed."""

    def __init__(self, settlement, ground, doc, dressing, water, rules, worker_cells, npcs, shrines):
        import ambient as A
        import town_dressing as TD
        self.settlement = settlement
        self.base = A.Site(settlement, ground, doc, dressing, water, {"water_changed_margin": rules["water_changed_margin"]})
        self.ground = ground
        self.why = {c: w for c, w in self.base.why.items() if not w.startswith(("lot ", "anchor "))}
        m = int(rules["building_margin"])
        self._m = m
        plan = TD.town_plan(settlement)
        self.lots = [tuple(l["rect"]) for l in plan.get("lots") or []]
        self.doors = []                                       # (building id, rect, facing)
        pp = ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)
        placed = json.loads(pp.read_text(encoding="utf-8")) if pp.is_file() else {"buildings": []}
        rects = {}
        for b in placed.get("buildings") or []:
            rects[b["id"]] = tuple(b["footprint"])
            if b.get("facing") in NORMAL:
                self.doors.append((b["id"], tuple(b["footprint"]), b["facing"]))
        for bid, r in TD.building_footprints(settlement, doc).items():
            rects.setdefault(bid, tuple(r))
        self.buildings = rects
        for bid, r in rects.items():
            for c in rect_cells(r, m):
                self.why.setdefault(c, "building %s" % bid)
        # the plaza: its pieces (benches are seats, not ground), its lights, its stalls' keepers and customers
        self.square, self.square_y, self.centrepiece, self.benches, self.keepers = None, None, None, [], []
        pc = ROOT / "derived" / "plaza_centres" / ("%s.json" % settlement)
        if pc.is_file():
            pz = json.loads(pc.read_text(encoding="utf-8"))
            self.square, self.square_y = tuple(pz["square"]["rect"]), int(pz["square"]["y"])
            if pz["square"].get("centrepiece"):
                self.centrepiece = (pz["square"]["centrepiece"][0], pz["square"]["centrepiece"][2])
            for p in pz["pieces"]:
                cols = {tuple(c) for c in p.get("columns") or []} | {(b[0], b[2]) for b in p.get("blocks") or []}
                for c in grow(cols, 1):
                    self.why.setdefault(c, "plaza %s" % p["id"])
                if p.get("keeper_at"):
                    k = (p["keeper_at"][0], p["keeper_at"][2])
                    self.keepers.append((p["id"], k))
                    for c in grow({k}, 1):
                        self.why.setdefault(c, "stall keeper %s" % p["id"])
                if p.get("customer"):
                    for c in grow({tuple(p["customer"])}, 1):
                        self.why.setdefault(c, "stall customer %s" % p["id"])
                if p["kind"] == "bench":
                    self.benches.append((p["id"], [tuple(c) for c in p["columns"]], int(p["floor_y"]), p["facing"]))
            for lx, _ly, lz in pz.get("lights") or []:
                for c in grow({(lx, lz)}, 1):
                    self.why.setdefault(c, "plaza light")
        elif plan.get("plaza"):
            self.square, self.square_y = tuple(plan["plaza"]["rect"]), int(plan["plaza"]["y"])
        # the town's box: its plan's footprint, plaza, lots and every building
        xs, zs = [], []
        for q in [plan.get("footprint"), self.square] + self.lots + list(rects.values()):
            if q:
                xs += [q[0], q[2]]
                zs += [q[1], q[3]]
        self.box = (min(xs) - 16, min(zs) - 16, max(xs) + 16, max(zs) + 16) if xs else None
        # streets: the plan's paved cells and data/placements.json's street polylines brushed at their width, or a
        # planless town's roads; the square's own cells are judged by its walking lines below
        streets = set(self.base.street_y) | street_cells(settlement, doc)
        if not plan:
            import plaza_centre as PC
            streets |= set(PC.road_cells(settlement, doc))
        for c in streets:
            if not self.on_square(*c):
                self.why.setdefault(c, "street")
        if self.box:
            for rid, pts in walked_lines().items():
                for x, z in pts:
                    if self.box[0] <= x <= self.box[2] and self.box[1] <= z <= self.box[3]:
                        self.why.setdefault((x, z), "walked route line %s" % rid)
        for c, w in plaza_walkways(settlement, doc, ground).items():
            self.why.setdefault(c, "the square's %s" % w)
        # every NPC the apply places, wherever its record says it belongs (a cell is a cell): never within NPC_CLEAR;
        # the town's own are the followers' anchors
        self.npcs = []
        self.npc_cells = {}
        for _pid, k in self.keepers:
            for g in grow({k}, NPC_CLEAR):
                self.npc_cells.setdefault(g, "stall keeper")
        if pc.is_file():
            for p in pz["pieces"]:
                if p.get("customer"):
                    self.npc_cells.setdefault((p["customer"][0], p["customer"][-1]), "stall customer %s" % p["id"])
        for nid, s, (x, _y, z) in npcs:
            fx, fz = float(x), float(z)
            c = (int(math.floor(fx)), int(math.floor(fz)))
            for g in grow({c}, NPC_CLEAR):
                self.why.setdefault(g, "townsperson %s" % nid)
                self.npc_cells.setdefault(g, "townsperson %s" % nid)
            if s == settlement or (self.box and self.box[0] <= fx <= self.box[2] and self.box[1] <= fz <= self.box[3]):
                self.npcs.append((nid, (fx, fz)))
        self.built = None                                   # a Built, set by plan() once every site is known
        for sid, c in shrines:
            for g in grow({c}, 4):
                self.why.setdefault(g, "shrine %s" % sid)
        self.worker_near = {}
        for wid, cells in worker_cells.items():
            for g in grow(cells, 2):
                self.why.setdefault(g, "worker %s" % wid)
                self.worker_near.setdefault(g, "worker %s" % wid)
        self.water = None if self.base.deck else water   # Pacifidlog's decks: see tools/ambient.py Site
        self.water_margin = int(rules["water_changed_margin"])

    def on_square(self, x, z):
        if not self.square:
            return False
        x0, z0, x1, z1 = self.square
        return min(x0, x1) <= x <= max(x0, x1) and min(z0, z1) <= z <= max(z0, z1)

    def y(self, x, z):
        """The y an idler stands at over cell (x, z): one above the plaza's paving, a street's, or the ground."""
        if self.on_square(x, z):
            return self.square_y + 1
        return self.base.y(x, z)

    def blocked(self, x, z):
        if (x, z) in self.why:
            return self.why[(x, z)]
        if self.water is not None:
            m = self.water_margin
            if self.water[max(0, z - m):z + m + 1, max(0, x - m):x + m + 1].any():
                return "on or within %d of a column the water export changes" % m
        return None

    def water_near(self, x, z):
        if self.water is not None:
            m = self.water_margin
            if self.water[max(0, z - m):z + m + 1, max(0, x - m):x + m + 1].any():
                return "on or within %d of a column the water export changes" % m
        return None

    def npc_close(self, x, z):
        """An NPC (or a stall's keeper or customer cell) on or beside (x, z): a bench seat is judged by this alone,
        since its cells are a plaza piece's."""
        return self.npc_cells.get((x, z))

    def refused(self, c, y, species, kind, seat=False):
        """Why the BUILT town refuses an idler of `species` standing at cell c with y (a seat's y ends .5), or None.
        Without a Built (a test building one town) nothing is refused here."""
        if self.built is None:
            return None
        return self.built.refuses(c[0], y, c[1], species if kind in STILL else None, seat)

    def candidates(self):
        """{(x, z): {feet y}} every cell place_town could try: the input to the replay's boxes."""
        out = {}
        an = self.anchors()
        for cat, lst in an.items():
            if cat == "bench":
                continue
            ring = NPC_RING if cat == "npc" else OFFSETS
            for _aid, (ax, az), _yaw in lst:
                for dx, dz in ring:
                    c = (ax + dx, az + dz)
                    if not self.blocked(*c):
                        out.setdefault(c, set()).add(self.y(*c))
        for _bid, seats, fy, _f in self.benches:
            for c in seats:
                out.setdefault(tuple(c), set()).add(fy + 1)
        return out

    # -------------------------------------------------------------------------------------------- the anchors
    def anchors(self):
        """{category: [(anchor id, (x, z), yaw or None)]}, each list in a stable scattered order."""
        out = {"bench": [], "door": [], "square": [], "yard": [], "npc": []}
        for bid, seats, _fy, facing in self.benches:
            out["bench"].append((bid, seats[len(seats) // 2], YAW[facing]))
        for bid, (x0, z0, x1, z1), facing in self.doors:
            nx, nz = NORMAL[facing]
            mx, mz = (x0 + x1) // 2, (z0 + z1) // 2
            ex = x1 if nx > 0 else x0 if nx < 0 else mx
            ez = z1 if nz > 0 else z0 if nz < 0 else mz
            out_by = int(self._m) + 1
            for side in (-2, 2):
                cx, cz = ex + nx * out_by + (-nz) * side, ez + nz * out_by + nx * side
                out["door"].append(("%s_%s" % (bid, "l" if side < 0 else "r"), (cx, cz), YAW[facing]))
        if self.square:
            x0, z0, x1, z1 = self.square
            cx, cz = self.centrepiece or ((x0 + x1) / 2.0, (z0 + z1) / 2.0)
            for x in range(min(x0, x1) + 1, max(x0, x1)):
                for z in range(min(z0, z1) + 1, max(z0, z1)):
                    edge = min(x - min(x0, x1), max(x0, x1) - x, z - min(z0, z1), max(z0, z1) - z)
                    if edge in (2, 3):
                        out["square"].append(("square", (x, z), yaw_to(x + .5, z + .5, cx + .5, cz + .5)))
        for lot in self.lots:
            x0, z0, x1, z1 = lot
            house = [r for r in self.buildings.values() if rect_cells(r) & rect_cells(lot)]
            hx = sum((r[0] + r[2]) / 2.0 for r in house) / len(house) if house else (x0 + x1) / 2.0
            hz = sum((r[1] + r[3]) / 2.0 for r in house) / len(house) if house else (z0 + z1) / 2.0
            for x in range(min(x0, x1) + 1, max(x0, x1)):
                for z in range(min(z0, z1) + 1, max(z0, z1)):
                    out["yard"].append(("yard", (x, z), yaw_to(hx, hz, x + .5, z + .5)))
        # a follower's anchor is an NPC the apply places: place_town seats it in the ring round it (NPC_CLEAR < d <=
        # reach). A plaza stall's keeper_at is where a keeper WOULD stand, not an NPC anything spawns: kept clear of,
        # never an anchor
        self.npc_at = {}
        for nid, (x, z) in self.npcs:
            self.npc_at[nid] = (x, z)
            out["npc"].append((nid, (int(math.floor(x)), int(math.floor(z))), None))
        for k in out:
            out[k].sort(key=lambda a: h32(self.settlement, k, a[1][0], a[1][1]))
        return out


OFFSETS = [(0, 0)] + sorted({(dx, dz) for dx in range(-3, 4) for dz in range(-3, 4) if (dx, dz) != (0, 0)},
                            key=lambda d: (abs(d[0]) + abs(d[1]), d))
# round an NPC: at least NPC_CLEAR + 1 cells off it (Chebyshev), nearest first; place_town keeps those within reach
NPC_RING = sorted({(dx, dz) for dx in range(-4, 5) for dz in range(-4, 5) if max(abs(dx), abs(dz)) > NPC_CLEAR},
                  key=lambda d: (math.hypot(*d), d))


def place_town(settlement, spec, site, rules, kinds_on):
    """[idler] for one town: each kind's species in groups of 1-3 at its preferred anchors, groups group_gap apart."""
    anchors = site.anchors()
    used_anchor, used_cells, out, short = [], set(), [], []
    cat_groups = {}
    cat_max = rules.get("max_groups") or {}
    sizes = itertools.cycle(rules["group_sizes"])
    gap, mgap = float(rules["group_gap"]), float(rules["member_gap"])
    n = 0
    for kind in ("sitter", "follower", "sleeper", "loafer"):
        if kind not in kinds_on:
            continue
        species = list(spec.get(kind) or [])
        if kind == "sleeper":
            day = day_sleepers(rules)
            bad = [s for s in species if s not in day]
            if bad:
                raise IdleError("ambient_idle/%s: %s may never sleep in a lit town by day under one of the two readings "
                                "of canSleepAt's light (rules.sleeps_by_day: open sky 15 and a block's own light 0 must "
                                "both be in range): %s" % (settlement, kind, bad))
        groups = []
        while species:
            k = next(sizes)
            groups.append(species[:k])
            species = species[k:]
        for grp in groups:
            placed = None
            for cat in rules["prefer"][kind]:
                if cat in cat_max and cat_groups.get(cat, 0) >= cat_max[cat]:
                    continue
                for aid, (ax, az), yaw in anchors[cat]:
                    if any(math.dist((ax, az), u) < gap for u in used_anchor):
                        continue
                    if cat == "bench":
                        seats = [b for b in site.benches if b[0] == aid][0]
                        cells = []
                        for c in seats[1]:
                            if c in used_cells:
                                continue
                            if site.npc_close(*c) or site.refused(c, seats[2] + 0.5, grp[len(cells)], kind, seat=True):
                                continue
                            cells.append(c)
                            if len(cells) == min(2, len(grp)):
                                break
                        if len(cells) < len(grp):
                            continue
                        placed = [(c, seats[2] + 0.5, YAW[seats[3]], cat, aid) for c in cells]
                        break
                    if cat == "npc":
                        # beside the NPC itself: within follower_home_radius + 1 of where it stands, never next to it
                        npc = site.npc_at[aid]
                        reach = float(rules["follower_home_radius"]) + 1
                        ring = [d for d in NPC_RING if math.dist((ax + d[0] + .5, az + d[1] + .5), npc) <= reach - 0.05]
                    elif cat == "door":
                        ring = OFFSETS        # the door spot itself is often the street: the nearest open cell beside it
                    elif site.blocked(ax, az):
                        continue
                    else:
                        ring = OFFSETS
                    ay = site.y(ax, az)
                    cells = []
                    for dx, dz in ring:
                        c = (ax + dx, az + dz)
                        if c in used_cells or site.blocked(*c) or abs(site.y(*c) - ay) > 1:
                            continue
                        if any(math.dist(c, p[0]) < mgap for p in cells):
                            continue
                        if site.refused(c, site.y(*c), grp[len(cells)], kind):
                            continue
                        if cat == "npc":
                            face = yaw_to(c[0] + .5, c[1] + .5, *site.npc_at[aid])
                        else:
                            face = yaw if yaw is not None else yaw_to(c[0] + .5, c[1] + .5, ax + .5, az + .5)
                        cells.append((c, float(site.y(*c)), face, cat, aid))
                        if len(cells) == len(grp):
                            break
                    if len(cells) == len(grp):
                        placed = cells
                        break
                if placed:
                    break
            if not placed:
                short.append((kind, grp))
                continue
            used_anchor.append(placed[0][0])
            cat_groups[placed[0][3]] = cat_groups.get(placed[0][3], 0) + 1
            for (c, y, face, cat, aid), sp in zip(placed, grp):
                used_cells.add(c)
                n += 1
                out.append({"id": "idle_%s_%02d" % (settlement, n), "town": settlement, "kind": kind, "species": sp,
                            "at": [c[0] + 0.5, y, c[1] + 0.5], "yaw": round(face, 1), "where": cat, "anchor": aid})
    return out, short


def place_buneary(bun, ground, rules, kinds_on):
    """The Buneary round the Lopunny superfan's house: spots in the house's local frame, checked against its own plan."""
    import lopunny_house as LH
    doc = LH.load()
    pl = LH.plan(doc, ground)
    cx, cz = doc["site"]["centre"]
    taken = set()
    for (x, y, z) in pl["blocks"]:
        if y >= ground(x, z) or (x, z) in taken:
            taken.add((x, z))
    blocked = grow(taken, 1)
    out = []
    for i, s in enumerate(bun["spots"], 1):
        if s["kind"] not in kinds_on:
            continue
        lx, lz = s["at_local"]
        x, z = cx + lx, cz + lz
        if (x, z) in blocked:
            raise IdleError("ambient_idle/buneary spot %d at (%d, %d) is on or beside the house's blocks" % (i, x, z))
        if s["kind"] == "sleeper" and bun["species"] not in rules["sleeps_by_day"]["species"] \
                and bun["species"] not in rules["sleeps_by_day"].get("night_only", {}):
            raise IdleError("ambient_idle/buneary: %s cannot sleep" % bun["species"])
        y = ground(x, z) + 1
        if s.get("face_local"):
            fx, fz = cx + s["face_local"][0], cz + s["face_local"][1]
            yaw = yaw_to(x + .5, z + .5, fx + .5, fz + .5)
        else:
            yaw = 0.0
        out.append({"id": "idle_buneary_%02d" % i, "town": BUNEARY_TOWN, "kind": s["kind"], "species": bun["species"],
                    "at": [x + 0.5, float(y), z + 0.5], "yaw": round(yaw, 1), "where": "snow_house", "anchor": "lopunny_house"})
    return out


def worker_cells(workers=None):
    """{worker id: {(x, z)}} every cell a working Pokemon stands on, walks or blinks to, from its data (no plan needed):
    `workers`, or data/ambient.json's with the default town files' in place of their towns'."""
    import ambient as A
    if workers is None:
        data = A.load()
        workers = A.workers_of(data, A.town_files(None, data))[0]
    out = {}
    for w in workers:
        if w["job"] == "carry":
            cells = set(A.cells_of(A.densify([tuple(c) for c in w["route"]], 0.5)))
        elif w["job"] == "work":
            cells = {tuple(w["at"]), tuple(w["face"])}
        else:
            cells = {tuple(s["at"]) for s in w["spots"]}
        out[w["id"]] = cells
    return out


def npc_spots(steps=None):
    """[(id, settlement or None, (x, y, z))] every NPC the apply places: data/npc_seats.json, data/markets.json's
    counters and stalls, and, given tools/reapply.py's steps, every npc and trainer item in them."""
    d = json.loads((ROOT / "data" / "npc_seats.json").read_text(encoding="utf-8"))
    out = [(s["id"], s.get("settlement"), tuple(s["at"])) for s in d["seats"] if s.get("at")]
    mk = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
    for r in (mk.get("counters") or []) + (mk.get("stalls") or []):
        if r.get("at"):
            out.append((r["id"], r.get("town"), tuple(r["at"])))
    for _sid, _d, items in steps or []:
        for it in items:
            if it[0] in ("npc", "trainer"):
                out.append((it[1][0], None, tuple(it[1][1])))
    return out


def shrine_spots():
    d = json.loads((ROOT / "data" / "shrines.json").read_text(encoding="utf-8"))
    return [(s["id"], tuple(s["at"])) for s in d.get("shrines") or [] if s.get("at")]


# ------------------------------------------------------------------------------------------------ composed towns

def facing_yaw(v, what):
    """A yaw from a facing: a cardinal (north/south/east/west) or degrees; None faces south."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) % 360.0
    if v in YAW:
        return YAW[v]
    raise IdleError("ambient_idle/%s: facing %r is neither a cardinal nor degrees" % (what, v))


def slab_bottom(state):
    return "_slab" in state and "type=bottom" in state


class TownBuildings:
    """A town's buildings as tools/place_town.py places them: where each template landed (derived/towns/<settlement>
    _placement.json: command_position, origin_y, rotation, footprint, floor_y, facing) and the template file
    data/placements.json names for it (kits/, hydrated), giving every block of the building in world coordinates.
    The plan and the template, never a world (CLAUDE.md). A placed Pokemon's spot is resolved from these blocks."""

    def __init__(self, settlement, doc):
        self.settlement = settlement
        pp = ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)
        self.recs = {b["id"]: b for b in (json.loads(pp.read_text(encoding="utf-8")).get("buildings") or [])} \
            if pp.is_file() else {}
        self.files = {q["id"]: q.get("file") for q in doc["placements"] if q.get("settlement") == settlement}
        self._blocks = {}
        self._solid = None
        self._all = None

    def record(self, bid):
        if bid not in self.recs:
            raise IdleError("ambient_idle/%s: no building %r in derived/towns/%s_placement.json (its buildings: %s)"
                            % (self.settlement, bid, self.settlement, ", ".join(sorted(self.recs)) or "none"))
        return self.recs[bid]

    def blocks(self, bid):
        """{(x, y, z): block state} every non-air block of the building as placed."""
        if bid in self._blocks:
            return self._blocks[bid]
        import nbt
        import place_town as PT
        rec = self.record(bid)
        if rec.get("ruin"):
            raise IdleError("ambient_idle/%s: building %s is placed from a ruined copy, whose blocks are not read here; "
                            "give the spot an explicit `at`" % (self.settlement, bid))
        f = self.files.get(bid)
        if not f or not (ROOT / f).is_file():
            raise IdleError("ambient_idle/%s: building %s's template file %r is not here (python tools/local_inputs.py "
                            "hydrate --store <store>); give the spot an explicit `at`" % (self.settlement, bid, f))
        _, t = nbt.load(ROOT / f)
        pal = t["palette"]
        px, _oy, pz = rec["command_position"]
        oy, rot = int(rec["origin_y"]), rec["rotation"]
        out = {}
        for b in t["blocks"]:
            p = pal[b["state"]]
            name = p["Name"]
            if name == "minecraft:jigsaw":
                # place_town writes each jigsaw's final state over it
                state = (b.get("nbt") or {}).get("final_state") or "minecraft:air"
            else:
                props = p.get("Properties") or {}
                state = name + ("[%s]" % ",".join("%s=%s" % kv for kv in sorted(props.items())) if props else "")
            if state.split("[")[0] in AIRS:
                continue
            tx, ty, tz = b["pos"]
            rx, rz = PT.rotate(tx, tz, rot)
            out[(px + rx, oy + ty, pz + rz)] = state
        fp = rec["footprint"]
        off = [c for c in out if not (fp[0] <= c[0] <= fp[2] and fp[1] <= c[2] <= fp[3])]
        if off:
            # an independent check of the reading: the template must land exactly on the footprint place_town recorded
            raise IdleError("ambient_idle/%s: building %s's template lands %d blocks outside its recorded footprint %s "
                            "(first %s): the placement record and the template disagree"
                            % (self.settlement, bid, len(off), fp, off[0]))
        self._blocks[bid] = out
        return out

    def every_block(self):
        """{(x, y, z): state} every non-air block of every building of the town whose template is readable here (a
        ruined copy or a missing file is left out: a spot on such a building needs an explicit `at`)."""
        if self._all is None:
            self._all = {}
            for bid in sorted(self.recs):
                if self.recs[bid].get("ruin") or not self.files.get(bid) or not (ROOT / self.files[bid]).is_file():
                    continue
                self._all.update(self.blocks(bid))
        return self._all

    def solid(self):
        """{(x, y, z): state} every solid block of every building of the town."""
        if self._solid is None:
            import npc_spot_sweep as SW
            self._solid = {c: st for c, st in self.every_block().items() if SW.solid(st)}
        return self._solid

    def tops(self, bid):
        """{(x, z): (y, state)} the highest solid block of each of the building's columns."""
        import npc_spot_sweep as SW
        out = {}
        for (x, y, z), st in self.blocks(bid).items():
            if SW.solid(st) and ((x, z) not in out or y > out[(x, z)][0]):
                out[(x, z)] = (y, st)
        return out

    def door(self, bid):
        """(x, z) the building's entrance column (place_town's entrance jigsaw or sidecar), in the world."""
        import place_town as PT
        rec = self.record(bid)
        info = PT.template_info(ROOT / self.files[bid])
        if info["entrance_pos"] is None:
            raise IdleError("ambient_idle/%s: building %s has no entrance; give the spot an explicit `at`" % (self.settlement, bid))
        px, _y, pz = rec["command_position"]
        rx, rz = PT.rotate(info["entrance_pos"][0], info["entrance_pos"][2], rec["rotation"])
        return px + rx, pz + rz

    # -------------------------------------------------------------------------------------------- the spots
    def spot(self, bid, spot, side, taken):
        """(x, y, z, yaw, detail): where a placed Pokemon goes on `spot` of building `bid` -- x, z the cell's centre,
        y its feet -- the first such place not in `taken` (cells (x, floor y, z)). Fails closed, naming the building,
        when the building has no such place."""
        import npc_spot_sweep as SW
        rec = self.record(bid)
        blocks = self.blocks(bid)
        x0, z0, x1, z1 = rec["footprint"]
        floor_y = int(rec["floor_y"])
        facing = side or rec.get("facing") or "south"
        if facing not in NORMAL:
            raise IdleError("ambient_idle/%s: side %r of building %s is not a cardinal" % (self.settlement, facing, bid))
        nx, nz = NORMAL[facing]
        cx, cz = (x0 + x1) / 2.0, (z0 + z1) / 2.0
        tops = self.tops(bid)

        def free(x, y, z):
            return (x, math.floor(y), z) not in taken

        def stand_on(y, st):
            return y + (0.5 if slab_bottom(st) else 1.0)

        def on_side(x, z):
            """How far (x, z) is in from the building's `facing` edge (0 on it)."""
            return {(1, 0): x1 - x, (-1, 0): x - x0, (0, 1): z1 - z, (0, -1): z - z0}[(nx, nz)]
        out = None
        if spot == "roof":
            roof = [(c, t) for c, t in tops.items() if t[0] >= floor_y + 3]
            if roof:
                hi = max(t[0] for _c, t in roof)
                for (x, z), (y, st) in sorted(roof, key=lambda q: (-q[1][0], math.dist(q[0], (cx, cz)), q[0])):
                    fy = stand_on(y, st)
                    if (x, math.ceil(fy), z) in blocks or not free(x, fy, z):
                        continue
                    out = (x, fy, z, YAW[facing], "ridge y%d of the roof's highest y%d" % (y, hi))
                    break
        elif spot == "gutter":
            # the eave on the building's `side` (default the side its door faces): the outermost roof column of each
            # line across that side, the one nearest the side's middle
            eave = {}
            for (x, z), (y, st) in tops.items():
                if y < floor_y + 3:
                    continue
                lat = z if nx else x
                d = on_side(x, z)
                if lat not in eave or d < eave[lat][0]:
                    eave[lat] = (d, (x, z), y, st)
            mid = cz if nx else cx
            for lat in sorted(eave, key=lambda q: (abs(q - mid), q)):
                _d, (x, z), y, st = eave[lat]
                fy = stand_on(y, st)
                if (x, math.ceil(fy), z) in blocks or not free(x, fy, z):
                    continue
                out = (x, fy, z, YAW[facing], "the %s eave at y%d" % (facing, y))
                break
        elif spot == "window":
            # a glass block with the open air outside it and the building's air inside: the Pokemon sits inside,
            # behind the glass, at the window's lowest glass block, looking out
            cands = []
            for (x, y, z), st in blocks.items():
                if "glass" not in st:
                    continue
                if (x, y - 1, z) in blocks and "glass" in blocks[(x, y - 1, z)]:
                    continue                                   # not the lowest glass of its run
                run = 1
                while (x, y + run, z) in blocks and "glass" in blocks[(x, y + run, z)]:
                    run += 1
                for (dx, dz), name in ((NORMAL[k], k) for k in ("south", "north", "east", "west")):
                    ox, oz, ix, iz = x + dx, z + dz, x - dx, z - dz
                    if any((ox, y + k, oz) in blocks for k in range(run)) or any((ix, y + k, iz) in blocks for k in range(run)):
                        continue
                    # outside: nothing of the building from the glass outward on that line; inside: a wall further in
                    k, outside = 1, True
                    while x0 <= x + dx * k <= x1 and z0 <= z + dz * k <= z1:
                        if (x + dx * k, y, z + dz * k) in blocks:
                            outside = False
                            break
                        k += 1
                    k, walled = 2, False
                    while x0 <= x - dx * k <= x1 and z0 <= z - dz * k <= z1:
                        if (x - dx * k, y, z - dz * k) in blocks:
                            walled = True
                            break
                        k += 1
                    if outside and walled:
                        cands.append(((0 if name == facing else 1), y, (ix, iz), run, name))
            for _pref, y, (ix, iz), run, name in sorted(cands, key=lambda q: (q[0], q[1], math.dist(q[2], (cx, cz)), q[2])):
                if not free(ix, y, iz):
                    continue
                out = (ix, float(y), iz, YAW[name], "behind a %s window, %d glass high" % (name, run), run)
                break
        elif spot == "step":
            # the doorstep: out of the door until the cell is open, then one to the side, so the door stays clear
            ex, ez = self.door(bid)
            k = 0
            while (ex + nx * k, floor_y + 1, ez + nz * k) in blocks and k < 6:
                k += 1
            sx, sz = ex + nx * k, ez + nz * k
            for lx, lz in ((-nz, nx), (nz, -nx)):
                x, z = sx + lx, sz + lz
                if (x, floor_y + 1, z) in blocks or (x, floor_y + 2, z) in blocks:
                    continue
                if "_door" in str(blocks.get((x - nx, floor_y + 1, z - nz), "")):
                    continue
                if free(x, floor_y + 1, z):
                    out = (x, float(floor_y + 1), z, YAW[facing], "beside the %s door at the step" % facing)
                    break
        elif spot == "porch":
            # a floor block of the building with two open blocks over it, a roof somewhere above, within two of the
            # door's side, open to the outside, and not in front of a door
            cands = []
            for (x, z), (ty, _st) in tops.items():
                if (x, floor_y, z) not in blocks or not SW.solid(blocks[(x, floor_y, z)]):
                    continue
                if (x, floor_y + 1, z) in blocks or (x, floor_y + 2, z) in blocks or ty <= floor_y + 2:
                    continue
                if on_side(x, z) > 2 or (x + nx, floor_y + 1, z + nz) in blocks:
                    continue
                if any("_door" in str(blocks.get((x + dx, floor_y + 1, z + dz), "")) for dx, dz in NORMAL.values()):
                    continue
                cands.append((x, z))
            for x, z in sorted(cands, key=lambda c: (math.dist(c, (cx, cz)), c)):
                if free(x, floor_y + 1, z):
                    out = (x, float(floor_y + 1), z, YAW[facing], "on the %s porch" % facing)
                    break
        elif spot == "wall_top":
            # a wall or fence standing at least a block above the floor (one at the floor's own layer is a kerb)
            walls = [((x, z), y) for (x, z), (y, st) in tops.items()
                     if SW.short(st).endswith(("_wall", "_fence", "_fence_gate")) and y >= floor_y + 1]
            for (x, z), y in sorted(walls, key=lambda q: (on_side(*q[0]), math.dist(q[0], (cx, cz)), q[0])):
                if (x, y + 1, z) in blocks or not free(x, y + 1, z):
                    continue
                out = (x, float(y + 1), z, YAW[facing], "on the wall top at y%d" % y)
                break
        else:
            raise IdleError("ambient_idle/%s: a %s spot is not resolved from a building: give it an explicit `at` "
                            "[x, y, z] (feet y) measured from the plan" % (self.settlement, spot))
        if out is None:
            raise IdleError("ambient_idle/%s: building %s has no free %s spot%s (resolved from its template as placed); "
                            "give the record an explicit `at` or choose another building"
                            % (self.settlement, bid, spot, " on its %s side" % side if side else ""))
        return out


def anchor_ground_ok(site, bld, x, y, z):
    """Is feet y at (x, z) the ground the plan gives there (the settlement's own ground, a street's or the square's
    paving, within one), or the top of one of the town's buildings?"""
    if abs(y - site.y(x, z)) <= 1:
        return True
    for bid in bld.recs:
        try:
            t = bld.tops(bid).get((x, z))
        except IdleError:
            continue
        if t and abs(y - (t[0] + 1)) <= 1:
            return True
    return False


STREETISH = ("street", "walked route line", "the square's")


def check_spot(s, what, x, y, z, species, site, bld, sizes, taken, allow=(), ground_checks=True):
    """Fail closed when a composed Pokemon at cell (x, z), feet y, would stand in a building's or the built town's
    blocks, on another's cell, or -- standing at ground level -- beside an NPC, on a worker's cells, near water the export
    changes, or (unless `allow` names it) on a street, a walked route line or one of the square's walking lines."""
    cell = (x, math.floor(y), z)
    if cell in taken:
        raise IdleError("ambient_idle/%s: %s stands in the cell of %s %s" % (s, what, taken[cell], cell))
    if sizes is not None:
        size = sizes[species]
        sunk = y != math.floor(y)
        for c in body_cells(x + 0.5, y, z + 0.5, size, sunk):
            if c in bld.solid():
                raise IdleError("ambient_idle/%s: %s (%s, %.1f x %.2f) at %s meets the building block %s at %s"
                                % (s, what, species, size[0], size[1], [x, y, z], bld.solid()[c], c))
        if site.built is not None:
            why = site.built.body(x + 0.5, y, z + 0.5, size, sunk)
            if why:
                raise IdleError("ambient_idle/%s: %s (%s) at %s: the built town refuses it: %s" % (s, what, species, [x, y, z], why))
    if ground_checks and abs(y - site.y(x, z)) <= 1:
        for why in (site.npc_close(x, z), site.worker_near.get((x, z)), site.water_near(x, z)):
            if why:
                raise IdleError("ambient_idle/%s: %s at %s: %s" % (s, what, [x, y, z], why))
        w = site.why.get((x, z)) or ""
        if w.startswith(STREETISH):
            kind = "street" if w.startswith(("street", "walked")) else "walkway"
            if kind not in allow:
                raise IdleError("ambient_idle/%s: %s at %s is on %s (allow it with \"allow\": [\"%s\"] on the record)"
                                % (s, what, [x, y, z], w, kind))


def compose_town(s, t, site, bld, rules, comp, sizes):
    """([idler], [prop]) for one composed town (data/ambient_towns/<s>.json): its situations at their authored anchors,
    its placed Pokemon on the spots of its buildings, its pets beside their NPCs. Every authored Pokemon is placed or
    the build fails naming the town, the record and the rule."""
    out, props, taken, ids = [], [], {}, set()
    poses = comp.get("poses") or {}
    fit = comp.get("spot_fit") or {}
    day = day_sleepers(rules)

    def iid_of(rid):
        if not isinstance(rid, str) or not IID.fullmatch(rid):
            raise IdleError("ambient_idle/%s: id %r is not [a-z0-9_]+" % (s, rid))
        iid = rid if rid.startswith(s + "_") else "%s_%s" % (s, rid)
        if iid in ids:
            raise IdleError("ambient_idle/%s: duplicate id %s" % (s, rid))
        ids.add(iid)
        return iid

    def species_ok(sp, what):
        if not isinstance(sp, str) or not SPECIES_ID.fullmatch(sp):
            raise IdleError("ambient_idle/%s: %s: species %r" % (s, what, sp))
        if sizes is not None and sp not in sizes:
            raise IdleError("ambient_idle/%s: %s: species %r is not in the Cobblemon jar" % (s, what, sp))

    def prop(block, x, y, z, owner):
        if not isinstance(block, str) or not BLOCK.fullmatch(block):
            raise IdleError("ambient_idle/%s: %s: prop block %r is not a block state" % (s, owner, block))
        if (x, y, z) in bld.every_block():
            raise IdleError("ambient_idle/%s: %s: the prop %s at %s would overwrite a building's %s"
                            % (s, owner, block, [x, y, z], bld.every_block()[(x, y, z)]))
        if site.built is not None:
            st = site.built.m.at(x, y, z)
            if site.built.SW.solid(st):
                raise IdleError("ambient_idle/%s: %s: the prop %s at %s would overwrite the built town's %s"
                                % (s, owner, block, [x, y, z], site.built.SW.short(st)))
        if any(p["at"] == [x, y, z] for p in props):
            raise IdleError("ambient_idle/%s: %s: two props at %s" % (s, owner, [x, y, z]))
        props.append({"at": [x, y, z], "block": block, "for": owner})

    def add(rec):
        out.append(rec)
        taken[(math.floor(rec["at"][0]), math.floor(rec["at"][1]), math.floor(rec["at"][2]))] = rec["id"]

    # the situations, at their authored anchors (members may share a species: that IS the situation)
    for sit in t["situations"]:
        sid = sit.get("id")
        what = "situation %s" % sid
        for f in ("id", "title", "story", "at", "members"):
            if not sit.get(f):
                raise IdleError("ambient_idle/%s: %s lacks %s" % (s, what, f))
        ax, ay, az = (int(math.floor(v)) for v in sit["at"])
        if not anchor_ground_ok(site, bld, ax, ay, az):
            raise IdleError("ambient_idle/%s: %s: its anchor %s is not the plan's ground there (feet y %d) nor a building's "
                            "top: an anchor's y is the feet y, measured from the plan" % (s, what, sit["at"], site.y(ax, az)))
        yaw0 = facing_yaw(sit.get("facing"), what)
        allow = tuple(sit.get("allow") or ())
        k = 0
        for m in sit["members"]:
            species_ok(m.get("species"), what)
            pose = m.get("pose")
            if pose not in POSES:
                raise IdleError("ambient_idle/%s: %s: pose %r is not one of %s" % (s, what, pose, sorted(POSES)))
            kind = POSES[pose]
            if kind == "sleeper" and m["species"] not in day:
                raise IdleError("ambient_idle/%s: %s: %s may never sleep in a lit town by day (rules.sleeps_by_day: open "
                                "sky 15 and a block's own light 0 must both be in range)" % (s, what, m["species"]))
            offs = m.get("offsets") or []
            if int(m.get("count", len(offs))) != len(offs) or not offs:
                raise IdleError("ambient_idle/%s: %s: %s count %s with %d offsets" % (s, what, m["species"], m.get("count"), len(offs)))
            for dx, dy, dz in offs:
                k += 1
                x, y, z = ax + int(dx), ay + int(dy), az + int(dz)
                iid = iid_of("%s_%d" % (sid, k))
                check_spot(s, "%s member %d (%s)" % (what, k, m["species"]), x, float(y), z, m["species"], site, bld,
                           sizes, taken, allow)
                rec = {"id": iid, "town": s, "kind": kind, "role": "situation", "situation": sid, "pose": pose,
                       "species": m["species"], "at": [x + 0.5, float(y), z + 0.5],
                       "yaw": round(facing_yaw(m["facing"], what) if "facing" in m else yaw0, 1),
                       "where": "situation", "anchor": sid}
                if pose == "follow":
                    rec["home"] = [ax + 0.5, float(ay), az + 0.5]
                    rec["home_radius"] = float(sit.get("home_radius", rules["follower_home_radius"]))
                    rec["leash"] = int(sit.get("leash", rules["follower_leash"]))
                elif pose == "wander_leashed":
                    wl = poses.get("wander_leashed") or {}
                    rec["home_radius"] = float(m.get("home_radius", wl.get("home_radius", 2)))
                    rec["leash"] = int(m.get("leash", wl.get("leash", 4)))
                add(rec)
        for p in sit.get("props") or []:
            dx, dy, dz = p["at"]
            prop(p.get("block"), ax + int(dx), ay + int(dy), az + int(dz), what)
    # the placed: on a spot of a building, resolved from its template as placed, or at an explicit `at`
    for r in t["placed"]:
        what = "placed %s" % r.get("id")
        species_ok(r.get("species"), what)
        if r.get("spot") not in SPOTS:
            raise IdleError("ambient_idle/%s: %s: spot %r is not one of %s" % (s, what, r.get("spot"), SPOTS))
        iid = iid_of(r.get("id"))
        run = None
        if r.get("at"):
            x, y, z = int(math.floor(r["at"][0])), float(r["at"][1]), int(math.floor(r["at"][2]))
            yaw, detail = facing_yaw(r.get("facing"), what), "at %s" % r["at"]
        elif r.get("building"):
            got = bld.spot(r["building"], r["spot"], r.get("side"), taken)
            x, y, z, yaw, detail = got[:5]
            run = got[5] if len(got) > 5 else None
            if r.get("facing") is not None:
                yaw = facing_yaw(r["facing"], what)
        else:
            raise IdleError("ambient_idle/%s: %s names neither a building nor an `at`" % (s, what))
        lim = fit.get(r["spot"])
        if lim:
            if sizes is None:
                raise IdleError("ambient_idle/%s: %s: a %s spot needs the species' size and there is no Cobblemon jar here"
                                % (s, what, r["spot"]))
            w, h = sizes[r["species"]]
            mh = float(lim.get("max_height", 99))
            if r["spot"] == "window" and run is not None:
                mh = min(mh, float(run))
            if w > float(lim.get("max_width", 99)) + 1e-9 or h > mh + 1e-9:
                raise IdleError("ambient_idle/%s: %s: %s (%.2f wide, %.2f high) does not fit a %s spot (at most %.2f wide, "
                                "%.2f high; composition.spot_fit)" % (s, what, r["species"], w, h, r["spot"],
                                                                      float(lim.get("max_width", 99)), mh))
        check_spot(s, "%s (%s)" % (what, r["species"]), x, y, z, r["species"], site, bld, sizes, taken,
                   tuple(r.get("allow") or ()))
        add({"id": iid, "town": s, "kind": "still", "role": "placed", "species": r["species"],
             "at": [x + 0.5, y, z + 0.5], "yaw": round(yaw, 1), "where": r["spot"],
             "anchor": r.get("building") or "at", "detail": detail})
        mine = {}
        for p in r.get("props") or []:
            dx, dy, dz = p["at"]
            c = (x + int(dx), int(math.floor(y)) + int(dy), z + int(dz))
            prop(p.get("block"), c[0], c[1], c[2], what)
            mine[c] = p["block"]
        if sizes is not None and mine:
            # under its own cart: the body must fit beneath what it is under (a situation's members may sit in theirs)
            import npc_spot_sweep as SW
            for c in body_cells(x + 0.5, y, z + 0.5, sizes[r["species"]], y != math.floor(y)):
                if c in mine and SW.solid(mine[c]):
                    raise IdleError("ambient_idle/%s: %s (%s, %.2f high) meets its own prop %s at %s"
                                    % (s, what, r["species"], sizes[r["species"]][1], mine[c], list(c)))
    # the pets: beside their NPC -- a follower homed in the ring round it, or a still hold facing it
    site.anchors()
    for r in t["pets"]:
        what = "pet %s" % r.get("id")
        species_ok(r.get("species"), what)
        kind = PET_MODES.get(r.get("mode"))
        if kind is None:
            raise IdleError("ambient_idle/%s: %s: mode %r is not one of %s" % (s, what, r.get("mode"), sorted(PET_MODES)))
        owner = r.get("owner")
        if owner not in site.npc_at:
            raise IdleError("ambient_idle/%s: %s: owner %r is not an NPC the apply places in this town (here: %s)"
                            % (s, what, owner, ", ".join(sorted(site.npc_at)) or "none"))
        iid = iid_of(r.get("id"))
        npc = site.npc_at[owner]
        ax, az = int(math.floor(npc[0])), int(math.floor(npc[1]))
        reach = float(rules["follower_home_radius"]) + 1 if kind == "follower" else 2.95
        ay = site.y(ax, az)
        got = None
        for dx, dz in NPC_RING:
            c = (ax + dx, az + dz)
            if math.dist((c[0] + .5, c[1] + .5), npc) > reach - 0.05:
                continue
            y = site.y(*c)
            if (c[0], y, c[1]) in taken or site.blocked(*c) or abs(y - ay) > 1:
                continue
            if site.refused(c, y, r["species"], kind):
                continue
            try:
                check_spot(s, what, c[0], float(y), c[1], r["species"], site, bld, sizes, taken)
            except IdleError:
                continue
            got = (c, y)
            break
        if got is None:
            raise IdleError("ambient_idle/%s: %s: no open cell beside %s (within %.1f of it, never next to it)" % (s, what, owner, reach))
        (x, z), y = got
        rec = {"id": iid, "town": s, "kind": kind, "role": "pet", "owner": owner, "mode": r["mode"], "species": r["species"],
               "at": [x + 0.5, float(y), z + 0.5], "yaw": round(yaw_to(x + .5, z + .5, *npc), 1), "where": "npc", "anchor": owner}
        add(rec)
    return out, props


def worker_points(workers, site, arules):
    """[(id, species, (x, y, z), is_start)] where a composed town's workers stand: a station, each blink spot, a
    carrier's two ends (start first), through tools/ambient.py's own planning on the town's ground."""
    import ambient as A
    out = []
    for w in workers:
        p = A.plan_worker(w, site.base, arules)
        if p["job"] == "carry":
            pts = [p["points"][0], p["points"][-1]]
        elif p["job"] == "blink":
            pts = [q[:3] for q in p["spots"]]
        else:
            pts = [p["start"]]
        for k, q in enumerate(pts):
            out.append((w["id"], w["species"], tuple(q), k == 0))
    return out


def walkable(site, doc):
    """[(x, y, z)] the standing points of a town: its plan's street cells, its square, and data/placements.json's
    street polylines, at the feet y the plan gives; a town with none, its buildings' surroundings every 2 blocks."""
    cells = set(site.base.street_y) | street_cells(site.settlement, doc)
    if site.square:
        x0, z0, x1, z1 = site.square
        cells |= {(x, z) for x in range(min(x0, x1), max(x0, x1) + 1) for z in range(min(z0, z1), max(z0, z1) + 1)}
    if not cells and site.box:
        x0, z0, x1, z1 = site.box
        cells = {(x, z) for x in range(x0, x1 + 1, 2) for z in range(z0, z1 + 1, 2) if not site.blocked(x, z)}
    return [(x + 0.5, float(site.y(x, z)), z + 0.5) for x, z in sorted(cells)]


def enforce(s, t, idlers, wpoints, site, doc, comp):
    """The placement rules of the composition, over every Pokemon of a composed town (workers included): the town's
    total in its size band, no two of one species within same_species_group_radius outside one situation, at most
    ceiling.in_view_max within ceiling.in_view_radius of any standing point. Returns the town's summary; fails closed
    naming the town and the rule."""
    import ambient as A
    import numpy as np
    bad = A.composition_problems(s, t, comp)
    total = len(idlers) + len({w[0] for w in wpoints})
    lo, hi = comp["scale"][t["size"]]
    if not lo <= total <= hi:
        bad.append("%s: %d Pokemon placed, outside the %s band %d-%d" % (s, total, t["size"], lo, hi))
    pts = [(i["species"], tuple(i["at"]), i.get("situation"), i["id"]) for i in idlers] + \
          [(sp, q, None, wid) for wid, sp, q, _st in wpoints]
    r = float(comp["variety"]["same_species_group_radius"])
    for a, b in itertools.combinations(pts, 2):
        if a[0] != b[0] or a[3] == b[3]:
            continue
        if a[2] is not None and a[2] == b[2]:
            continue                                     # one situation's members: that IS the situation
        d = math.dist(a[1], b[1])
        if d <= r:
            bad.append("%s: two %s within %.1f of each other outside a situation: %s at %s and %s at %s "
                       "(composition.variety.same_species_group_radius %g)"
                       % (s, a[0], d, a[3], [round(v, 1) for v in a[1]], b[3], [round(v, 1) for v in b[1]], r))
    mons = np.array([i["at"] for i in idlers] + [q for _w, _sp, q, st in wpoints if st], dtype=float).reshape(-1, 3)
    walk = np.array(walkable(site, doc), dtype=float).reshape(-1, 3)
    worst, at = 0, None
    if len(mons) and len(walk):
        R, cap = float(comp["ceiling"]["in_view_radius"]), int(comp["ceiling"]["in_view_max"])
        for k in range(0, len(walk), 2048):
            blk = walk[k:k + 2048]
            n = (np.linalg.norm(blk[:, None, :] - mons[None, :, :], axis=2) <= R).sum(axis=1)
            j = int(n.argmax())
            if n[j] > worst:
                worst, at = int(n[j]), blk[j].tolist()
        if worst > cap:
            bad.append("%s: %d Pokemon within %g of the standing point %s, over composition.ceiling.in_view_max %d"
                       % (s, worst, R, at, cap))
    if bad:
        raise IdleError("ambient_idle: the composition rules refuse:\n  " + "\n  ".join(bad))
    c = A.town_counts(t)
    return {"counts": c, "shares": {k: round(c[k] / c["total"], 2) for k in ("working", "pets", "placed", "situations")},
            "in_view_max": worst, "in_view_at": at, "walkable_points": len(walk),
            "unique_situations": [x["id"] for x in t["situations"] if x.get("unique")]}


def composed_sites(data, towns, g, doc, dressing, water, rules, wc, npcs, shrines, source_root):
    """{settlement: (TownSite, TownBuildings)} for every composed town, each on its own ground."""
    import ambient as A
    out = {}
    for s in sorted(towns):
        if s not in doc["settlements"]:
            raise IdleError("ambient_idle: %s has no settlement in data/placements.json" % s)
        out[s] = (TownSite(s, A.settlement_ground(s, g, doc, source_root), doc, dressing, water, rules, wc, npcs, shrines),
                  TownBuildings(s, doc))
    return out


def compose(source_root=None, towns_dir=None, towns=None, comp=None):
    """Every composed town planned and checked on the town plan, the templates and the settlement's ground, WITHOUT the
    replay of the built packs (so with no `reapply.py prepare` first): the townspeople are data/npc_seats.json's and
    data/markets.json's only, and nothing the built town adds (signposts, stalls, porches outside a template) is
    checked. For the town authors; `build` checks all of it. {settlement: {"idlers", "props", "summary"}}
    `towns` and `comp` (tests) stand in for the town files and data/ambient.json's composition."""
    import ground as G
    import ambient as A
    data = load()
    if comp is not None:
        data["composition"] = comp
    if towns is None:
        towns = A.town_files(towns_dir, data)
    rules = dict(data["idle"]["rules"], water_changed_margin=data["rules"]["water_changed_margin"])
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    dressing = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
    if ("ground", source_root) not in _CACHE:
        _CACHE[("ground", source_root)] = G.Ground(source_root)
    g = _CACHE[("ground", source_root)]
    water = np_load_water()
    workers, _sup = A.workers_of(data, towns)
    if "sizes" not in _CACHE:
        _CACHE["sizes"] = species_sizes()
    sizes = _CACHE["sizes"]
    # a town's site is the slow part (the dressing, the square's walking lines): kept for the process, keyed on
    # everything it is made from that a town file can change (the workers)
    key = ("sites", source_root, json.dumps(workers, sort_keys=True), tuple(sorted(towns)))
    if key not in _CACHE:
        _CACHE[key] = composed_sites(data, towns, g, doc, dressing, water, rules, worker_cells(workers), npc_spots(None),
                                     shrine_spots(), source_root)
    sites = _CACHE[key]
    out = {}
    for s, t in sorted(towns.items()):
        site, bld = sites[s]
        idlers, props = compose_town(s, t, site, bld, rules, data["composition"], sizes)
        wp = worker_points([w for w in workers if w["settlement"] == s], site, data["rules"])
        out[s] = {"idlers": idlers, "props": props,
                  "summary": enforce(s, t, idlers, wp, site, doc, data["composition"])}
    return out


def np_load_water():
    import ambient as A
    if A.WATER_CHANGED.is_file():
        import numpy as np
        return np.load(A.WATER_CHANGED)
    return None


def gates_of(towns, rules):
    """{town: {centre, radius}} the circle round a town's idlers inside which a player wakes its keeper."""
    gates = {}
    for s, idlers in towns.items():
        if not idlers:
            continue
        cx = sum(i["at"][0] for i in idlers) / len(idlers)
        cz = sum(i["at"][2] for i in idlers) / len(idlers)
        cy = int(round(sum(i["at"][1] for i in idlers) / len(idlers)))
        r = max(math.dist((cx, cz), (i["at"][0], i["at"][2])) for i in idlers) + rules["keep_margin"]
        gates[s] = {"centre": [round(cx, 1), cy, round(cz, 1)], "radius": int(math.ceil(r))}
    return gates


def plan(source_root=None, packs=None, towns_dir=None):
    import ground as G
    data = load()
    idle = data["idle"]
    rules = dict(idle["rules"], water_changed_margin=data["rules"]["water_changed_margin"])
    kinds_on = [k for k in rules["enabled_kinds"] if k in KINDS]
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    dressing = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
    g = G.Ground(source_root)
    import ambient as A
    water = np_load_water()
    # the composed towns (data/ambient.json composition): a town file replaces the town's idle.towns entry, and its
    # workers replace the town's data/ambient.json workers
    comp = data["composition"]
    composed = A.town_files(towns_dir, data)
    workers, _superseded = A.workers_of(data, composed)
    specs = {s: spec for s, spec in idle["towns"].items() if s not in composed}
    # the built town: every pack's block writes replayed (the apply's own steps; this pack's are left out)
    steps = load_steps(packs or PACKS)
    wc, npcs, shrines = worker_cells(workers), npc_spots(steps), shrine_spots()
    n_workers = {}
    for w in workers:
        n_workers[w["settlement"]] = n_workers.get(w["settlement"], 0) + 1
    sites = {}
    for s, spec in specs.items():
        if s not in doc["settlements"]:
            raise IdleError("ambient_idle: %s has no settlement in data/placements.json" % s)
        for k in spec:
            if k not in KINDS and not k.endswith("why"):
                raise IdleError("ambient_idle/%s: unknown kind %r" % (s, k))
        sites[s] = TownSite(s, g, doc, dressing, water, rules, wc, npcs, shrines)
    csites = composed_sites(data, composed, g, doc, dressing, water, rules, wc, npcs, shrines, source_root)
    sizes = species_sizes()
    cells = {}
    for site in sites.values():
        for c, ys in site.candidates().items():
            cells.setdefault(c, set()).update(ys)
    # a composed town's cells for the replay's boxes: a first pass without the built town, every pet's ring round
    # its NPC, every prop
    for s, (site, bld) in csites.items():
        idlers, props = compose_town(s, composed[s], site, bld, rules, comp, sizes)
        for i in idlers:
            cells.setdefault((math.floor(i["at"][0]), math.floor(i["at"][2])), set()).add(math.floor(i["at"][1]))
        for p in props:
            cells.setdefault((p["at"][0], p["at"][2]), set()).add(p["at"][1])
        for r in composed[s]["pets"]:
            if r.get("owner") in site.npc_at:
                ax, az = site.npc_at[r["owner"]]
                for dx, dz in NPC_RING:
                    c = (int(math.floor(ax)) + dx, int(math.floor(az)) + dz)
                    if not site.blocked(*c):
                        cells.setdefault(c, set()).add(site.y(*c))
    built = Built(packs or PACKS, g, cells, steps)
    towns, everyone, shortfalls, town_props, summaries = {}, [], [], {}, {}
    for s, (site, bld) in csites.items():
        site.built = built
        idlers, props = compose_town(s, composed[s], site, bld, rules, comp, sizes)
        wp = worker_points([w for w in workers if w["settlement"] == s], site, data["rules"])
        summaries[s] = enforce(s, composed[s], idlers, wp, site, doc, comp)
        towns[s] = idlers
        everyone += idlers
        if props:
            town_props[s] = props
    for s, spec in specs.items():
        site = sites[s]
        site.built = built
        idlers, short = place_town(s, spec, site, rules, kinds_on)
        if short:
            shortfalls.append("%s: no room for %s" % (s, short))
        total = len(idlers) + n_workers.get(s, 0)
        if total > rules["cap_per_town"]:
            raise IdleError("ambient_idle/%s: %d idle + %d working = %d, over the cap of %d"
                            % (s, len(idlers), n_workers.get(s, 0), total, rules["cap_per_town"]))
        towns[s] = idlers
        everyone += idlers
    if shortfalls:
        # every authored idler is placed or the build fails: a town quietly holding fewer than its data says is the
        # kind of success report CLAUDE.md forbids
        raise IdleError("ambient_idle: the site's anchors are used up or blocked (author fewer, or a smaller "
                        "group_gap):\n  " + "\n  ".join(shortfalls))
    towns[BUNEARY_TOWN] = place_buneary(idle["buneary"], g, rules, kinds_on)
    everyone += towns[BUNEARY_TOWN]
    # Arrow Creeks Farm's livestock (2026-10-05, data/pokemon_farm.json animals): one more group like the Buneary,
    # each spot checked by tools/pokemon_farm.py against the farm's own block plan (bodies clear, followers inside
    # their pens), never against a town plan, which the farm has none of
    import pokemon_farm as PF
    towns[PF.TOWN] = PF.idlers(g, rules, kinds_on)
    if len(towns[PF.TOWN]) > rules["cap_per_town"]:
        raise IdleError("ambient_idle/%s: %d animals, over the cap of %d" % (PF.TOWN, len(towns[PF.TOWN]), rules["cap_per_town"]))
    everyone += towns[PF.TOWN]
    seen = set()
    for i in everyone:
        if i["id"] in seen:
            raise IdleError("ambient_idle: duplicate id %s" % i["id"])
        seen.add(i["id"])
    worker_ids = {w["id"] for w in workers}
    if seen & worker_ids:
        raise IdleError("ambient_idle: ids shared with workers: %s" % sorted(seen & worker_ids))
    return {"rules": rules, "kinds_on": kinds_on, "towns": towns, "gates": gates_of(towns, rules), "workers_per_town": n_workers,
            "water_changed_checked": water is not None, "replayed_lines": built.lines,
            "body_checked": built.sizes is not None, "composed": summaries, "props": town_props}


# ------------------------------------------------------------------------------------------------ the functions

def snbt_list(ids):
    return "[%s]" % ",".join('"%s"' % b for b in ids)


def functions(pl):
    rules = pl["rules"]
    beh = rules["behaviours"]
    fn = {}
    fn["load"] = ["scoreboard objectives add %s dummy" % OBJ]
    fn["tick"] = ["# every tick: two clocks (the whole cost of this pack with nobody near: four lines)",
                  "scoreboard players add #clock %s 1" % OBJ,
                  "execute if score #clock %s matches %d.. run function %s/keep_all" % (OBJ, rules["keep_every"], F),
                  "scoreboard players add #wake %s 1" % OBJ,
                  "execute if score #wake %s matches %d.. run function %s/wakes" % (OBJ, rules["wake_every"], F)]
    # EXP-046: a spawn line parsed at server start does nothing until a /reload; a macro line is parsed when it runs
    fn["spawn_at"] = ["$spawnpokemonat $(x) $(y) $(z) $(species) level=$(level) uncatchable no_ai"]
    fn["wakes"] = [
        "scoreboard players set #wake %s 0" % OBJ,
        "# Cobblemon 1.8.0 wakes no sleeper for a player (SleepDepth.shouldWake is never called): this does, at %d"
        % rules["wake_radius"],
        "execute as @e[type=cobblemon:pokemon,tag=%s] at @s if entity @a[distance=..%d] run function %s/wake"
        % (DOZER, rules["wake_radius"], F),
        "execute as @e[type=cobblemon:pokemon,tag=%s] at @s unless entity @a[distance=..%d] run function %s/doze"
        % (WOKEN, rules["rest_radius"], F)]
    fn["wake"] = ["# the awake list (no cobblemon:pokemon_sleeps): the brain is remade, the sleep memory with it",
                  "data merge entity @s {BehavioursAreCustom:1b,Behaviours:%s}" % snbt_list(beh["awake"]),
                  "tag @s remove %s" % DOZER, "tag @s add %s" % WOKEN]
    fn["doze"] = ["# nobody near: the sleeper's own list back, so it can doze off again",
                  "data merge entity @s {BehavioursAreCustom:1b,Behaviours:%s}" % snbt_list(beh["sleeper"]),
                  "tag @s remove %s" % WOKEN, "tag @s add %s" % DOZER]
    keep_all = ["scoreboard players set #clock %s 0" % OBJ]
    for s, gate in sorted(pl["gates"].items()):
        cx, cy, cz = gate["centre"]
        keep_all.append("execute positioned %s %d %s if entity @a[distance=..%d] run function %s/t/%s/keep"
                        % (num(cx), cy, num(cz), gate["radius"], F, s))
    fn["keep_all"] = keep_all
    for s, idlers in sorted(pl["towns"].items()):
        if not idlers:
            continue
        keep = ["# %s: %d idle Pokemon, each exactly once and on its spot; run by keep_all only while a player is near,"
                " and by reapply.py R16C to settle the town" % (s, len(idlers))]
        for i in idlers:
            iid, kind = i["id"], i["kind"]
            t = "%s.%s" % (TAG, iid)
            sel = "@e[type=cobblemon:pokemon,tag=%s]" % t
            x, y, z = i["at"]
            keep += ["execute store result score #n %s if entity %s" % (OBJ, sel),
                     "execute if score #n %s matches 2.. positioned %s %s %s run kill @e[type=cobblemon:pokemon,tag=%s,limit=1,sort=furthest]"
                     % (OBJ, num(x), num(y), num(z), t),
                     "execute if score #n %s matches 0 if loaded %d %d %d run function %s/i/%s/spawn"
                     % (OBJ, math.floor(x), math.floor(y), math.floor(z), F, iid)]
            if kind in STILL:
                keep.append("execute as %s run tp @s %s %s %s %s 0" % (sel, num(x), num(y), num(z), num(i["yaw"])))
            else:
                # a composed town's follower names its own leash (a pet's, a situation's, a short wander_leashed one)
                leash = i.get("leash") or (rules["sleeper_leash"] if kind == "sleeper" else rules["follower_leash"])
                keep.append("execute as %s positioned %s %s %s unless entity @s[distance=..%d] run tp @s %s %s %s"
                            % (sel, num(x), num(y), num(z), leash, num(x), num(y), num(z)))
            fn["i/%s/spawn" % iid] = [
                "function %s/spawn_at {x:\"%s\",y:\"%s\",z:\"%s\",species:\"%s\",level:%d}"
                % (F, num(x), num(y), num(z), i["species"], rules["level"]),
                "execute positioned %s %s %s as @e[type=cobblemon:pokemon,tag=!%s,nbt={NoAI:1b},distance=..2,limit=1,sort=nearest] "
                "run function %s/i/%s/claim" % (num(x), num(y), num(z), TAG, F, iid)]
            claim = ["tag @s add %s" % TAG, "tag @s add %s" % IDLE, "tag @s add %s" % t]
            flags = 'PersistenceRequired:1b,Invulnerable:1b,Unbattleable:1b,DeathLootTable:"minecraft:empty"'
            if kind in STILL:
                claim += ["data merge entity @s {NoAI:1b,%s}" % flags,
                          "tp @s %s %s %s %s 0" % (num(x), num(y), num(z), num(i["yaw"]))]
            elif kind == "sleeper":
                claim += ["data merge entity @s {NoAI:0b,%s,BehavioursAreCustom:1b,Behaviours:%s}"
                          % (flags, snbt_list(beh["sleeper"])),
                          "tag @s add %s" % DOZER]
            else:
                # a follower's list is the rules' own, unless its group names a longer one (the farm's wool flock adds
                # cobblemon:pokemon_eats_grass, tools/pokemon_farm.py idlers)
                # its home is its spot, unless it names one (a situation's follow: the situation's anchor)
                hx, hy, hz = i.get("home") or (x, y, z)
                claim += ["data merge entity @s {NoAI:0b,%s,BehavioursAreCustom:1b,Behaviours:%s,"
                          "ScriptingConfig:{home_x:%sd,home_y:%sd,home_z:%sd,home_radius:%sd}}"
                          % (flags, snbt_list(i.get("behaviours") or beh["follower"]), num(hx), num(hy), num(hz),
                             num(float(i.get("home_radius") or rules["follower_home_radius"])))]
            fn["i/%s/claim" % iid] = claim
        fn["t/%s/keep" % s] = keep
    # a composed town's props (its situations' and placed Pokemon's blocks): set by reapply.py R16C before the town is
    # settled; its cleanup takes each one back out only while it is still the block it set, and the town's Pokemon
    # (each holds its own chunks, as a worker's tread does: run by R16C before the town's area is force-loaded)
    import function_limits
    for s, props in sorted((pl.get("props") or {}).items()):
        fn["t/%s/props" % s] = function_limits.ensure_loaded(
            ["# %s: %d props of its situations and placed Pokemon (data/ambient_towns/%s.json)" % (s, len(props), s)]
            + ["setblock %d %d %d %s" % (p["at"][0], p["at"][1], p["at"][2], p["block"]) for p in props])
    for s in sorted(set(pl.get("composed") or {}) | set(pl.get("props") or {})):
        fn["t/%s/cleanup" % s] = function_limits.ensure_loaded(
            ["# %s: the composed town taken out: its props (only where still the block set) and its Pokemon" % s]
            + ["execute if block %d %d %d %s run setblock %d %d %d minecraft:air"
               % (p["at"][0], p["at"][1], p["at"][2], p["block"], p["at"][0], p["at"][1], p["at"][2])
               for p in (pl.get("props") or {}).get(s, [])]
            + ["kill @e[type=cobblemon:pokemon,tag=%s.%s]" % (TAG, i["id"]) for i in pl["towns"].get(s, [])])
    return fn


def write(pl):
    import function_limits
    if OUT.exists():
        shutil.rmtree(OUT)
    base = OUT / "data" / NS / "function" / FOLDER
    base.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: idle Pokemon in the towns (tools/ambient_idle.py)"}}, indent=2) + "\n",
                                     encoding="utf-8")
    tags = OUT / "data" / "minecraft" / "tags" / "function"
    tags.mkdir(parents=True)
    (tags / "tick.json").write_text(json.dumps({"values": ["%s/tick" % F]}) + "\n", encoding="utf-8")
    (tags / "load.json").write_text(json.dumps({"values": ["%s/load" % F]}) + "\n", encoding="utf-8")
    fns = functions(pl)
    for name, cmds in fns.items():
        refused = function_limits.check_lines(cmds, name)
        if refused:
            raise IdleError("ambient_idle: %s: %d command(s) the server would refuse: %s" % (name, len(refused), refused[:3]))
        p = base / (name + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(cmds) + "\n", encoding="utf-8", newline="\n")
    ids = [i["id"] for s in sorted(pl["towns"]) for i in pl["towns"][s]]
    (base / "index.txt").write_text("\n".join(ids) + "\n", encoding="utf-8", newline="\n")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(pl, indent=1), encoding="utf-8")
    return fns


# ------------------------------------------------------------------------------------------------ cost, steps, verify

def cost(pl):
    """Command lines per tick, from the functions as written: always (nobody near), and per occupied town."""
    rules = pl["rules"]
    fns = functions(pl)

    def run(name):                       # the command lines a function runs: its comments cost nothing
        return len([l for l in fns[name] if l.strip() and not l.lstrip().startswith("#")])
    always = run("tick") + run("keep_all") / rules["keep_every"] + run("wakes") / rules["wake_every"]
    per = {}
    for s, idlers in pl["towns"].items():
        if idlers:
            lines = run("t/%s/keep" % s)
            ai = sum(1 for i in idlers if i["kind"] not in STILL)
            per[s] = {"idle": len(idlers), "ai_on": ai, "keep_lines_per_tick": round(lines / rules["keep_every"], 2)}
    return {"always_lines_per_tick": round(always, 2), "towns": per}


def composed_line(sm):
    c = sm["counts"]
    return ("composed: working %d, pets %d, placed %d, situations %d = %d (shares %s); at most %d in view (of %d standing "
            "points); unique: %s" % (c["working"], c["pets"], c["placed"], c["situations"], c["total"],
                                     " ".join("%s %.2f" % kv for kv in sm["shares"].items()), sm["in_view_max"],
                                     sm["walkable_points"], ", ".join(sm["unique_situations"]) or "NONE"))


def report(pl):
    lines = []
    c = cost(pl)
    for s in sorted(pl["towns"]):
        idlers = pl["towns"][s]
        by = {k: sum(1 for i in idlers if i["kind"] == k) for k in IDLER_KINDS}
        w = pl["workers_per_town"].get(s, 0)
        lines.append("%-15s idle %2d (%s) + working %d = %2d   keep %s lines/tick" % (
            s, len(idlers), ", ".join("%s %d" % (k, by[k]) for k in IDLER_KINDS if by[k]), w, len(idlers) + w,
            c["towns"].get(s, {}).get("keep_lines_per_tick", 0)))
        if s in (pl.get("composed") or {}):
            lines.append("    " + composed_line(pl["composed"][s]))
    lines.append("always (nobody near): %s lines/tick" % c["always_lines_per_tick"])
    return lines


def plan_doc():
    if not PLAN.is_file():
        raise IdleError("no %s: run python tools/ambient_idle.py build" % PLAN)
    return json.loads(PLAN.read_text(encoding="utf-8"))


def forceload_boxes(idlers, pad=2, tile=240):
    xs = [int(math.floor(i["at"][0])) for i in idlers]
    zs = [int(math.floor(i["at"][2])) for i in idlers]
    x0, x1, z0, z1 = min(xs) - pad, max(xs) + pad, min(zs) - pad, max(zs) + pad
    out = []
    for bx in range(x0, x1 + 1, tile):
        for bz in range(z0, z1 + 1, tile):
            out.append((bx, bz, min(bx + tile - 1, x1), min(bz + tile - 1, z1)))
    return out


def placement_steps():
    """reapply.py R16C: each town's idlers settled -- its area force-loaded, its keeper run twice (a chunk's saved
    entities load a moment after its blocks; the keeper removes a second), the area let go. None while this build
    reads the steps (SKIP_STEPS): they write no block, and they need the plan the build is making."""
    if SKIP_STEPS:
        return []
    out = []
    pl = plan_doc()
    for s, idlers in sorted(pl["towns"].items()):
        if not idlers:
            continue
        boxes = forceload_boxes(idlers)
        if (pl.get("props") or {}).get(s):
            # a composed town's props first (the function holds its own chunks), then the town settled
            out.append(("fn", "%s/t/%s/props" % (F, s)))
        out += [("cmd", "forceload add %d %d %d %d" % b) for b in boxes]
        out += [("wait", 3), ("fn", "%s/t/%s/keep" % (F, s)), ("wait", 2), ("fn", "%s/t/%s/keep" % (F, s))]
        out += [("cmd", "forceload remove %d %d %d %d" % b) for b in boxes]
    return out


def verify(rc):
    """Over RCON on a running server: each idler exactly once, NoAI as its kind needs. [problems]"""
    import time
    bad = []
    for s, idlers in sorted(plan_doc()["towns"].items()):
        if not idlers:
            continue
        boxes = forceload_boxes(idlers)
        for b in boxes:
            rc("forceload add %d %d %d %d" % b)
        time.sleep(3)
        for i in idlers:
            t = "%s.%s" % (TAG, i["id"])
            got = rc("execute if entity @e[type=cobblemon:pokemon,tag=%s]" % t)
            if "count: 1" not in got:
                bad.append("%s: expected one, got %r" % (i["id"], got))
                continue
            r = rc("data get entity @e[type=cobblemon:pokemon,tag=%s,limit=1] NoAI" % t)
            want = "1b" if i["kind"] in STILL else "0b"
            # a mob saves NoAI only while it is true: with AI on the tag is absent (staging, 2026-10-04: every
            # follower and sleeper read "Found no elements matching NoAI" with its custom behaviours set)
            if want not in r and not (want == "0b" and "Found no elements" in r):
                bad.append("%s (%s): NoAI is %r, wanted %s" % (i["id"], i["kind"], r, want))
        for b in boxes:
            rc("forceload remove %d %d %d %d" % b)
        print("   %-16s %d idle  %s" % (s, len(idlers), "ok" if not any(m.startswith("idle_%s" % s) for m in bad)
                                       else "PROBLEM"), flush=True)
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--source-root", default=env_source_root())
    b.add_argument("--towns-dir", default=None, help="the composed town files (default data/ambient_towns)")
    c = sub.add_parser("compose", help="plan and check the composed towns only, without the built packs")
    c.add_argument("--source-root", default=env_source_root())
    c.add_argument("--towns-dir", default=None, help="the composed town files (default data/ambient_towns)")
    c.add_argument("--json", default=None, help="write the composed idlers, props and summaries here")
    sub.add_parser("report")
    v = sub.add_parser("verify")
    v.add_argument("--rcon", action="store_true", required=True)
    v.add_argument("--server-dir", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "compose":
        got = compose(a.source_root, a.towns_dir)
        if not got:
            print("no town files in %s" % (a.towns_dir or "data/ambient_towns"))
            return 1
        for s, v in got.items():
            print("%-15s %s; props %d" % (s, composed_line(v["summary"]), len(v["props"])))
        if a.json:
            Path(a.json).write_text(json.dumps(got, indent=1), encoding="utf-8")
        print("composed %d towns, every rule held. NOT checked here: the built packs' blocks (signposts, stalls, "
              "anything not in a building template) and the townspeople reapply.py's steps place; `build` checks both"
              % len(got))
        return 0
    if a.cmd == "build":
        pl = plan(a.source_root, towns_dir=a.towns_dir)
        fns = write(pl)
        for line in report(pl):
            print(line)
        n = sum(len(v) for v in pl["towns"].values())
        print("wrote %s: %d idle Pokemon in %d places, %d functions; %d block-writing lines of every pack replayed%s%s" % (
            OUT, n, sum(1 for v in pl["towns"].values() if v), len(fns), pl["replayed_lines"],
            "" if pl["water_changed_checked"] else " (WARNING: no derived/water_shape/changed.npy; the water rule was not checked)",
            "" if pl["body_checked"] else " (WARNING: no Cobblemon jar here; the still idlers' bodies were not checked)"))
        return 0
    if a.cmd == "report":
        for line in report(plan_doc()):
            print(line)
        return 0
    import reapply
    bad = verify(reapply.Rcon(a.server_dir))
    for m in bad:
        print("PROBLEM", m)
    print("%d problems" % len(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
