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

  python tools/ambient_idle.py build [--source-root <root>]   # the pack and derived/ambient/idle_plan.json
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
KINDS = ("sitter", "loafer", "sleeper", "follower")
STILL = ("sitter", "loafer")
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
            w, h = self.sizes.get(species, (1.0, 2.0))
            hw, px, pz = w / 2.0, x + 0.5, z + 0.5
            for cx in range(math.floor(px - hw + 1e-6), math.floor(px + hw - 1e-6) + 1):
                for cz in range(math.floor(pz - hw + 1e-6), math.floor(pz + hw - 1e-6) + 1):
                    for cy in range(math.floor(y), math.floor(y + h - 1e-6) + 1):
                        if seat and cy == fy - 1:
                            continue
                        st = m.at(cx, cy, cz)
                        if SW.solid(st):
                            return "its body (%.1f x %.2f) meets %s at %s" % (w, h, SW.short(st), (cx, cy, cz))
        return None


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
        for wid, cells in worker_cells.items():
            for g in grow(cells, 2):
                self.why.setdefault(g, "worker %s" % wid)
        self.water = water
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


def worker_cells():
    """{worker id: {(x, z)}} every cell a working Pokemon stands on, walks or blinks to, from its data (no plan needed)."""
    import ambient as A
    out = {}
    for w in A.load()["workers"]:
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


def plan(source_root=None, packs=None):
    import ground as G
    data = load()
    idle = data["idle"]
    rules = dict(idle["rules"], water_changed_margin=data["rules"]["water_changed_margin"])
    kinds_on = [k for k in rules["enabled_kinds"] if k in KINDS]
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    dressing = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
    g = G.Ground(source_root)
    import ambient as A
    water = None
    if A.WATER_CHANGED.is_file():
        import numpy as np
        water = np.load(A.WATER_CHANGED)
    # the built town: every pack's block writes replayed (the apply's own steps; this pack's are left out)
    steps = load_steps(packs or PACKS)
    wc, npcs, shrines = worker_cells(), npc_spots(steps), shrine_spots()
    n_workers = {}
    for w in data["workers"]:
        n_workers[w["settlement"]] = n_workers.get(w["settlement"], 0) + 1
    sites = {}
    for s, spec in idle["towns"].items():
        if s not in doc["settlements"]:
            raise IdleError("ambient_idle: %s has no settlement in data/placements.json" % s)
        for k in spec:
            if k not in KINDS and not k.endswith("why"):
                raise IdleError("ambient_idle/%s: unknown kind %r" % (s, k))
        sites[s] = TownSite(s, g, doc, dressing, water, rules, wc, npcs, shrines)
    cells = {}
    for site in sites.values():
        for c, ys in site.candidates().items():
            cells.setdefault(c, set()).update(ys)
    built = Built(packs or PACKS, g, cells, steps)
    towns, everyone, shortfalls = {}, [], []
    for s, spec in idle["towns"].items():
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
    worker_ids = {w["id"] for w in data["workers"]}
    if seen & worker_ids:
        raise IdleError("ambient_idle: ids shared with workers: %s" % sorted(seen & worker_ids))
    gates = {}
    for s, idlers in towns.items():
        if not idlers:
            continue
        cx = sum(i["at"][0] for i in idlers) / len(idlers)
        cz = sum(i["at"][2] for i in idlers) / len(idlers)
        cy = int(round(sum(i["at"][1] for i in idlers) / len(idlers)))
        r = max(math.dist((cx, cz), (i["at"][0], i["at"][2])) for i in idlers) + rules["keep_margin"]
        gates[s] = {"centre": [round(cx, 1), cy, round(cz, 1)], "radius": int(math.ceil(r))}
    return {"rules": rules, "kinds_on": kinds_on, "towns": towns, "gates": gates, "workers_per_town": n_workers,
            "water_changed_checked": water is not None, "replayed_lines": built.lines,
            "body_checked": built.sizes is not None}


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
                leash = rules["sleeper_leash"] if kind == "sleeper" else rules["follower_leash"]
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
                claim += ["data merge entity @s {NoAI:0b,%s,BehavioursAreCustom:1b,Behaviours:%s,"
                          "ScriptingConfig:{home_x:%sd,home_y:%sd,home_z:%sd,home_radius:%sd}}"
                          % (flags, snbt_list(i.get("behaviours") or beh["follower"]), num(x), num(y), num(z),
                             num(float(rules["follower_home_radius"])))]
            fn["i/%s/claim" % iid] = claim
        fn["t/%s/keep" % s] = keep
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


def report(pl):
    lines = []
    c = cost(pl)
    for s in sorted(pl["towns"]):
        idlers = pl["towns"][s]
        by = {k: sum(1 for i in idlers if i["kind"] == k) for k in KINDS}
        w = pl["workers_per_town"].get(s, 0)
        lines.append("%-15s idle %2d (%s) + working %d = %2d   keep %s lines/tick" % (
            s, len(idlers), ", ".join("%s %d" % (k, by[k]) for k in KINDS if by[k]), w, len(idlers) + w,
            c["towns"].get(s, {}).get("keep_lines_per_tick", 0)))
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
    for s, idlers in sorted(plan_doc()["towns"].items()):
        if not idlers:
            continue
        boxes = forceload_boxes(idlers)
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
    sub.add_parser("report")
    v = sub.add_parser("verify")
    v.add_argument("--rcon", action="store_true", required=True)
    v.add_argument("--server-dir", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        pl = plan(a.source_root)
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
