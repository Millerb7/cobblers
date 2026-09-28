#!/usr/bin/env python
"""Working Pokemon in the towns: each one doing the town's work where a player can watch it, from data/ambient.json,
as the world pack build/datapacks/cobblers_ambient.

The owner, 2026-09-28: "Every town gets Pokemon doing things a player can watch or interact with. Not decoration -
visible work that says what the place is." A worker is one shared Pokemon (not per player) with a job:

  carry   walks a route and back at walking pace, an item held over it on the way out (a block, a log, a sample) that
          it picks up at one end and sets down at the other, with the sound and the dust of it
  work    stands at its station facing the work (a stone pile, a target, a fumarole) and every few seconds hops to it:
          the particles and the sound of the work at the work
  blink   an Abra's job: every few seconds it teleports to its next spot (a lectern, a cart), portal particles and the
          sound at both ends

How one is held (EXP-046, staging cobblers-dryrun11, 2026-09-28): spawned by `spawnpokemonat ... uncatchable no_ai`
through a macro function (a spawn line parsed at server start does nothing until a /reload re-parses it: measured),
claimed in the same function (a Cobblemon Pokemon without PersistenceRequired is despawned within a
minute with no player near: measured), then tagged, `PersistenceRequired`, `Invulnerable` (it refused every damage
type `/damage` offers: generic, player_attack, mob_attack, arrow, in_fire) and `Unbattleable`, with Resistance V and
Regeneration. Effects do not survive a restart (measured), so the keeper re-applies them. NoAI means it never walks
off: every move it makes is this pack's `tp`. An interaction box stands on it: a click on the box says a line about
the work (`execute on target`), and a hit lands on the box, not on the Pokemon (a sword killed the Celebi, which
had no box: tools/sapling_celebi.py). It survived a chunk unload and a restart with its tags, flags, position and
carried item (measured); the loop's clock is a scoreboard and survived too.

The keeper (every 40 ticks, only where its chunk is loaded and a player is within keep_radius): exactly one worker,
one carried-item display, one interaction box (extras killed, a missing one made), the flags and effects asserted,
and the worker put back at its station if anything moved it. The step runs every tick, only while a player is within
active_radius, so an empty town costs nothing.

Where they stand: the ground is the heightmap (tools/ground.py, rounded), or a street's own paved y where the town
plan grades one; never a world (CLAUDE.md). Every cell a worker stands on, walks or blinks to is refused when it is
inside a building (grown by one), on a house or anchor lot, on a lamp, under a dressing piece or an earthwork's
blocks, or on or within 8 of a column the pending water export changes (derived/water_shape/changed.npy, when
present: the owner, 2026-09-28, nothing built that the export would invalidate). A route may not step more than one
block between neighbouring cells.

  python tools/ambient.py build [--source-root <root>]     # the pack, and derived/ambient/plan.json
  python tools/ambient.py verify --rcon --server-dir <server>   # a running staging server: one of each, flags held

The re-application: reapply.py R16C places each worker (force-loads its station, runs its place function) and checks
them with verify.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "ambient.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_ambient"
PLAN = ROOT / "derived" / "ambient" / "plan.json"
WATER_CHANGED = ROOT / "derived" / "water_shape" / "changed.npy"
NS, FOLDER = "cobblers", "ambient"
F = "%s:%s" % (NS, FOLDER)
OBJ = "cobblers_amb"
TAG = "cobblers.amb"
ID = re.compile(r"[a-z0-9_]+")
SPECIES = re.compile(r"[a-z0-9_]+")
ITEM = re.compile(r"minecraft:[a-z0-9_]+")
SOUND = re.compile(r"[a-z0-9_]+:[a-z0-9_.]+")
JOBS = ("carry", "work", "blink")


class AmbientError(SystemExit):
    pass


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def num(v):
    s = "%.2f" % v
    return s.rstrip("0").rstrip(".") if "." in s else s


def yaw_to(ax, az, bx, bz):
    """Minecraft yaw facing from (ax, az) towards (bx, bz): 0 south (+z), 90 west (-x)."""
    return (math.degrees(math.atan2(-(bx - ax), bz - az)) + 360.0) % 360.0


# ------------------------------------------------------------------------------------------------ ground and cells

class Site:
    """What a worker may stand on in one settlement, from the plan and the heightmap (never a world)."""

    def __init__(self, settlement, ground, doc, dressing, water, rules):
        import town_dressing as TD
        self.settlement = settlement
        self.ground = ground
        plan = TD.town_plan(settlement)
        self.street_y = {}
        for st in (plan.get("streets") or {}).values():
            for z, y, xa, xb in st.get("cells") or []:
                for x in range(xa, xb + 1):
                    self.street_y[(x, z)] = int(y)
        self.why = {}

        def mark(cells, why):
            for c in cells:
                self.why.setdefault(c, why)
        for lot in plan.get("lots") or []:
            mark(TD.rect_cells(lot["rect"]), "lot %s" % lot["id"])
        for an in plan.get("anchors") or []:
            mark(TD.rect_cells(an["rect"]), "anchor %s" % an["id"])
        for lamp in plan.get("lamps") or []:
            mark(TD.grow({(lamp["at"][0], lamp["at"][2])}, 1), "lamp")
        for bid, rect in TD.building_footprints(settlement, doc).items():
            mark(TD.rect_cells(rect, 1), "building %s" % bid)
        for q in doc["placements"]:
            if q.get("settlement") == settlement and q.get("kind") == "earthwork":
                mark(TD.command_columns(q.get("commands")), "earthwork %s" % q["id"])
        # the dressing's pieces, seated as the dressing seats them
        town = (dressing.get("towns") or {}).get(settlement)
        if town:
            mask = TD.Mask(settlement, doc, None)
            entries = ([dict(town["landmark"], id=town["landmark"].get("id", "landmark"))] if town.get("landmark") else []) \
                + list(town.get("pieces") or [])
            for e in entries:
                blocks, _floor = TD.place(e, settlement, ground, mask)
                mark({(b[0], b[2]) for b in blocks}, "dressing %s" % e["id"])
        self.water = water
        self.water_margin = int(rules["water_changed_margin"])

    def y(self, x, z):
        """The y a worker stands at over cell (x, z): one above the ground, or above the street's paving."""
        return (self.street_y[(x, z)] if (x, z) in self.street_y else self.ground(x, z)) + 1

    def blocked(self, x, z):
        if (x, z) in self.why:
            return self.why[(x, z)]
        if self.water is not None:
            m = self.water_margin
            if self.water[max(0, z - m):z + m + 1, max(0, x - m):x + m + 1].any():
                return "on or within %d of a column the water export changes" % m
        return None


def densify(points, step):
    """Points every `step` blocks along a polyline of cell centres."""
    out = []
    for (ax, az), (bx, bz) in zip(points, points[1:]):
        a = (ax + 0.5, az + 0.5)
        b = (bx + 0.5, bz + 0.5)
        n = max(1, int(round(math.dist(a, b) / step)))
        for i in range(n):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    last = points[-1]
    out.append((last[0] + 0.5, last[1] + 0.5))
    return out


def cells_of(pts):
    seen, out = set(), []
    for x, z in pts:
        c = (int(math.floor(x)), int(math.floor(z)))
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


# ------------------------------------------------------------------------------------------------ the plan

def plan_worker(w, site, rules):
    wid = w["id"]
    if not ID.fullmatch(wid) or not SPECIES.fullmatch(w["species"]):
        raise AmbientError("ambient: bad id %r or species %r" % (wid, w.get("species")))
    if w["job"] not in JOBS:
        raise AmbientError("ambient/%s: job %r is not one of %s" % (wid, w["job"], JOBS))
    if not isinstance(w.get("interact"), str) or not w["interact"].strip():
        raise AmbientError("ambient/%s: every worker says something when clicked (interact)" % wid)
    level = int(w.get("level", rules["level"]))
    if not 1 <= level <= 100:
        raise AmbientError("ambient/%s: level %d" % (wid, level))

    def check(cells, what):
        for x, z in cells:
            why = site.blocked(x, z)
            if why:
                raise AmbientError("ambient/%s: %s cell (%d, %d) is not free: %s" % (wid, what, x, z, why))

    p = {"id": wid, "settlement": w["settlement"], "species": w["species"], "level": level, "job": w["job"],
         "interact": w["interact"], "box": w.get("box", rules["box"]), "clear": list(w.get("clear") or [])}
    for b in p["clear"]:
        if not ITEM.fullmatch(b):
            raise AmbientError("ambient/%s: clear %r" % (wid, b))
    if w["job"] == "carry":
        route = [tuple(c) for c in w["route"]]
        if len(route) < 2:
            raise AmbientError("ambient/%s: a carry route needs two points or more" % wid)
        pts = densify(route, float(rules["step_blocks"]))
        cells = cells_of(pts)
        check(cells, "route")
        ys = {c: site.y(*c) for c in cells}
        prev = None
        for c in cells:
            if prev is not None and abs(ys[c] - ys[prev]) > 1:
                raise AmbientError("ambient/%s: the route steps %d blocks between %s and %s"
                                   % (wid, abs(ys[c] - ys[prev]), prev, c))
            prev = c
        if not ITEM.fullmatch(w["carry"]):
            raise AmbientError("ambient/%s: carry %r" % (wid, w["carry"]))
        p.update(points=[(x, ys[(int(math.floor(x)), int(math.floor(z)))], z) for x, z in pts],
                 carry=w["carry"], pause=int(w.get("pause_ticks", rules["pause_ticks"])),
                 carry_height=float(w.get("carry_height", rules["carry_height"])),
                 pickup=w.get("pickup") or {}, drop=w.get("drop") or {})
        if p["pause"] < 1:
            raise AmbientError("ambient/%s: pause_ticks must be 1 or more (the load is picked up and set down in the pauses)" % wid)
        p["start"] = p["points"][0]
    elif w["job"] == "work":
        (x, z), (fx, fz) = w["at"], w["face"]
        check([(x, z)], "station")
        y = site.y(x, z)
        hx, hz = x + 0.5 + (fx - x) * 0.12, z + 0.5 + (fz - z) * 0.12
        if (math.floor(hx), math.floor(hz)) != (x, z) and site.blocked(math.floor(hx), math.floor(hz)):
            hx, hz = x + 0.5, z + 0.5                  # the hop's cell is not free (a lot, an anchor): it hops in place
        p["hop"] = (hx, hz)
        p.update(start=(x + 0.5, y, z + 0.5), yaw=yaw_to(x + 0.5, z + 0.5, fx + 0.5, fz + 0.5),
                 face=(fx + 0.5, site.y(fx, fz) if not site.blocked(fx, fz) else y, fz + 0.5),
                 every=int(w.get("every", rules["work_every"])), effect=w["effect"])
        if w.get("look_around"):
            lx, lz = w["look_around"]
            p["look_yaw"] = yaw_to(x + 0.5, z + 0.5, lx + 0.5, lz + 0.5)
    else:
        spots = []
        for s in w["spots"]:
            (x, z), (fx, fz) = s["at"], s["face"]
            check([(x, z)], "spot")
            spots.append((x + 0.5, site.y(x, z), z + 0.5, yaw_to(x + 0.5, z + 0.5, fx + 0.5, fz + 0.5)))
        if len(spots) < 2:
            raise AmbientError("ambient/%s: a blink job needs two spots or more" % wid)
        p.update(spots=spots, start=spots[0][:3], every=int(w.get("every", rules["blink_every"])))
    return p


def plan(source_root=None):
    import ground as G
    data = load()
    rules = data["rules"]
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    dressing = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
    g = G.Ground(source_root)
    water = None
    if WATER_CHANGED.is_file():
        import numpy as np
        water = np.load(WATER_CHANGED)
    sites, out, seen = {}, [], set()
    for w in data["workers"]:
        if w["id"] in seen:
            raise AmbientError("ambient: duplicate worker %s" % w["id"])
        seen.add(w["id"])
        s = w["settlement"]
        if s not in doc["settlements"]:
            raise AmbientError("ambient/%s: settlement %r has no plan" % (w["id"], s))
        if s not in sites:
            sites[s] = Site(s, g, doc, dressing, water, rules)
        out.append(plan_worker(w, sites[s], rules))
    # the owner's per-town limit (data/ambient.json rules.per_town): carriers, and stationary workers (work and blink)
    cap = rules["per_town"]
    for s in sorted({w["settlement"] for w in out}):
        n_carry = sum(1 for w in out if w["settlement"] == s and w["job"] == "carry")
        n_still = sum(1 for w in out if w["settlement"] == s and w["job"] != "carry")
        if n_carry > cap["carriers"] or n_still > cap["stationary"]:
            raise AmbientError("ambient: %s has %d carriers and %d stationary workers; the limit is %d and %d"
                               % (s, n_carry, n_still, cap["carriers"], cap["stationary"]))
    return {"rules": rules, "workers": out, "water_changed_checked": water is not None}


# ------------------------------------------------------------------------------------------------ the functions

def particle(effect, x, y, z):
    """A particle command from a worker's effect: a block's dust or a named particle."""
    if effect.get("block"):
        if not ITEM.fullmatch(effect["block"]):
            raise AmbientError("ambient: particle block %r" % effect["block"])
        name = 'minecraft:block{block_state:{Name:"%s"}}' % effect["block"]
    else:
        name = effect["particle"]
        if not re.fullmatch(r"minecraft:[a-z_]+", name):
            raise AmbientError("ambient: particle %r" % name)
    sp = effect.get("spread", 0.25)
    return "particle %s %s %s %s %s %s %s %s %d" % (name, num(x), num(y), num(z), num(sp), num(sp), num(sp),
                                                   num(effect.get("speed", 0)), int(effect.get("count", 10)))


def sound(name, x, y, z, rules, pitch=1.0):
    if not SOUND.fullmatch(name):
        raise AmbientError("ambient: sound %r" % name)
    # the selector carries the position: a tick function runs at the world spawn, where `distance` would measure from
    # (the test author, 2026-09-28: no player heard a worker)
    return "playsound %s neutral @a[x=%s,y=%s,z=%s,distance=..%d] %s %s %s %s %s" % (
        name, num(x), num(y), num(z), rules["hear_radius"], num(x), num(y), num(z), num(rules["volume"]), num(pitch))


def functions(pl):
    rules = pl["rules"]
    fn = {}
    tick = ["# every tick: the steps of the workers a player is near (cobblers_amb #<id>_on, set by the keepers)",
            "scoreboard players add #clock %s 1" % OBJ,
            "execute if score #clock %s matches %d.. run function %s/keep_all" % (OBJ, rules["keep_every"], F),
            "execute as @e[type=minecraft:interaction,tag=%s.i] if data entity @s interaction run function %s/click" % (TAG, F),
            "execute as @e[type=minecraft:interaction,tag=%s.i] if data entity @s attack run data remove entity @s attack" % TAG]
    keep_all = ["scoreboard players set #clock %s 0" % OBJ]
    click = ["# a player clicked a worker's box: the worker's line, to them, then forget the click"]
    fn["load"] = ["scoreboard objectives add %s dummy" % OBJ]
    # EXP-046: `spawnpokemonat` written in a function spawns nothing when the function was parsed at server start, and
    # works once a /reload has parsed it again (measured twice on staging, 2026-09-28). A macro line is parsed when it
    # runs, so the keeper works after a plain restart with no /reload
    fn["spawn_at"] = ["$spawnpokemonat $(x) $(y) $(z) $(species) level=$(level) uncatchable no_ai"]
    for w in pl["workers"]:
        wid = w["id"]
        t = "%s.%s" % (TAG, wid)
        tc, ti = "%s.c.%s" % (TAG, wid), "%s.i.%s" % (TAG, wid)
        sx, sy, sz = w["start"]
        on = "#%s_on" % wid
        clk = "#%s_t" % wid
        tick.append("execute if score %s %s matches 1 run function %s/w/%s/step" % (on, OBJ, F, wid))
        keep_all.append("execute if loaded %d %d %d run function %s/w/%s/keep" % (math.floor(sx), sy, math.floor(sz), F, wid))
        # the keeper resets the step flag only where it runs: a chunk that unloaded with the flag on would step for ever
        keep_all.append("execute unless loaded %d %d %d run scoreboard players set %s %s 0" % (math.floor(sx), sy, math.floor(sz), on, OBJ))
        click.append("execute if entity @s[tag=%s] run function %s/w/%s/click" % (ti, F, wid))
        near = "@a[x=%s,y=%s,z=%s,distance=..%%d]" % (num(sx), sy, num(sz))
        w_sel = "@e[type=cobblemon:pokemon,tag=%s]" % t
        w1 = "@e[type=cobblemon:pokemon,tag=%s,limit=1]" % t
        box_w, box_h = w["box"]
        # the keeper
        keep = ["# %s (%s, %s): exactly one, held, protected, at work; only while a player is within %d"
                % (wid, w["settlement"], w["species"], rules["keep_radius"]),
                "scoreboard players set %s %s 0" % (on, OBJ),
                "execute unless entity %s run return 0" % (near % rules["keep_radius"]),
                "function %s/w/%s/hold" % (F, wid),
                "execute if entity %s run scoreboard players set %s %s 1" % (near % rules["active_radius"], on, OBJ)]
        fn["w/%s/keep" % wid] = keep
        hold = ["execute store result score #n %s if entity %s" % (OBJ, w_sel),
                "# a second one (a spawn that raced a slow entity load): the one furthest from the station goes",
                "execute if score #n %s matches 2.. positioned %s %s %s run kill @e[type=cobblemon:pokemon,tag=%s,limit=1,sort=furthest]"
                % (OBJ, num(sx), sy, num(sz), t),
                "execute if score #n %s matches 0 run function %s/w/%s/spawn" % (OBJ, F, wid),
                "execute as %s run data merge entity @s {NoAI:1b,Invulnerable:1b,Unbattleable:1b,PersistenceRequired:1b}" % w_sel,
                "execute as %s run effect give @s minecraft:resistance infinite 4 true" % w_sel,
                "execute as %s run effect give @s minecraft:regeneration infinite 4 true" % w_sel,
                "execute store result score #n %s if entity @e[type=minecraft:interaction,tag=%s]" % (OBJ, ti),
                "execute if score #n %s matches 2.. run kill @e[type=minecraft:interaction,tag=%s,limit=1]" % (OBJ, ti),
                "execute if score #n %s matches 0 at %s run summon minecraft:interaction ~ ~ ~ "
                "{width:%sf,height:%sf,response:1b,Tags:[\"%s.i\",\"%s\"]}" % (OBJ, w1, num(box_w), num(box_h), TAG, ti)]
        if w["job"] == "carry":
            hold += ["execute store result score #n %s if entity @e[type=minecraft:item_display,tag=%s]" % (OBJ, tc),
                     "execute if score #n %s matches 2.. run kill @e[type=minecraft:item_display,tag=%s,limit=1]" % (OBJ, tc),
                     "execute if score #n %s matches 0 at %s run summon minecraft:item_display ~ ~%s ~ {Tags:[\"%s.c\",\"%s\"],"
                     "teleport_duration:2,item:{id:\"%s\",count:1},transformation:{left_rotation:[0f,0f,0f,1f],"
                     "right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[0.55f,0.55f,0.55f]}}"
                     % (OBJ, w1, num(w["carry_height"]), TAG, tc, w["carry"]),
                     "# a new display starts empty (an item_display cannot be summoned holding air): the load shows at the pickup",
                     "execute if score #n %s matches 0 run item replace entity @e[type=minecraft:item_display,tag=%s] contents with minecraft:air"
                     % (OBJ, tc)]
        else:
            # a station worker stands where it works: anything that moved it (a push, a stray tp) is undone here
            yaw = w.get("yaw", 0.0)
            if w["job"] == "work":
                hold.append("execute as %s run tp @s %s %s %s %s 0" % (w_sel, num(sx), sy, num(sz), num(yaw)))
            hold.append("execute as @e[type=minecraft:interaction,tag=%s] at %s run tp @s ~ ~ ~" % (ti, w1))
        fn["w/%s/hold" % wid] = hold
        fn["w/%s/spawn" % wid] = [
            "# EXP-046: through the macro (a spawn line parsed at boot does nothing until a /reload), and claimed at once",
            "# (unclaimed, the despawner takes it within a minute)",
            "function %s/spawn_at {x:\"%s\",y:%d,z:\"%s\",species:\"%s\",level:%d}" % (F, num(sx), sy, num(sz), w["species"], w["level"]),
            "execute positioned %s %s %s as @e[type=cobblemon:pokemon,tag=!%s,nbt={NoAI:1b},distance=..2,limit=1,sort=nearest] "
            "run function %s/w/%s/claim" % (num(sx), sy, num(sz), TAG, F, wid),
            "scoreboard players set %s %s 0" % (clk, OBJ)]
        fn["w/%s/claim" % wid] = [
            "tag @s add %s" % TAG, "tag @s add %s" % t,
            "data merge entity @s {PersistenceRequired:1b,Invulnerable:1b,Unbattleable:1b,DeathLootTable:\"minecraft:empty\"}"]
        # the re-application: the station's chunk loaded by the driver first, then placed whether or not anyone is near.
        # A worker with `clear` treads its track first: the export paints snow over the heightmap's ground (Northlight:
        # deep enough to hide a Timburr standing in it, the owner, 2026-09-28), so those blocks are taken out of every
        # cell it stands on and the one above, and it walks on the ground its y was measured from
        # (its own function, holding its own chunks: run by R16C before the station is force-loaded, because a
        # `forceload remove` is not counted and would release the station the driver holds)
        if w["clear"]:
            import function_limits
            clear = []
            for bname in w["clear"]:
                for (cx, cy, cz) in stand_cells(w):
                    clear.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (cx, cy, cz, cx, cy + 1, cz, bname))
            fn["w/%s/tread" % wid] = function_limits.ensure_loaded(clear)
        fn["w/%s/place" % wid] = ["function %s/w/%s/hold" % (F, wid)]
        lines = w["interact"].replace("\\", "\\\\").replace('"', '\\"')
        fn["w/%s/click" % wid] = [
            "execute on target run tellraw @s {\"text\":\"%s\",\"color\":\"gray\",\"italic\":true}" % lines,
            "execute at %s run particle minecraft:heart ~ ~%s ~ 0.3 0.2 0.3 0 3" % (w1, num(box_h)),
            "data remove entity @s interaction"]
        fn["w/%s/step" % wid] = step(w, rules, w_sel, tc, ti, fn)
        if w["job"] == "carry":
            fn["load"].append("function %s/w/%s/route" % (F, wid))
    fn["tick"] = tick
    fn["keep_all"] = keep_all
    fn["click"] = click
    return fn


def stand_cells(w):
    """Every (x, y, z) block a worker stands in: its route's cells, its spots, or its station."""
    if w["job"] == "carry":
        pts = [(math.floor(x), y, math.floor(z)) for x, y, z in w["points"]]
    elif w["job"] == "blink":
        pts = [(math.floor(x), y, math.floor(z)) for x, y, z, _yaw in w["spots"]]
    else:
        x, y, z = w["start"]
        pts = [(math.floor(x), y, math.floor(z))]
    seen, out = set(), []
    for c in pts:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


STORE = "%s:ambient" % NS


def step(w, rules, w_sel, tc, ti, fn=None):
    """The per-tick clock and the moves of one worker's job. A carrier's route is not one line per point (a carrier
    cost 0.41 ms a tick that way, measured on staging 2026-09-28, most of it failed score tests): the route is data in
    storage, and each tick one macro looks up the point for the clock. `fn` receives the helper functions."""
    clk = "#%s_t" % w["id"]
    out = ["scoreboard players add %s %s 1" % (clk, OBJ)]
    move = []                                   # (tick, [commands])
    walk = []                                   # the carrier's two dispatch lines, after the wrap
    if w["job"] == "carry":
        pts, pause = w["points"], w["pause"]
        n = len(pts)

        def heading(seq_pts):
            # each point faces along its own leg (the next point; the last keeps the leg it arrived on)
            out, last = [], 0.0
            for i, (x, _y, z) in enumerate(seq_pts):
                if i + 1 < len(seq_pts):
                    nx, _ny, nz = seq_pts[i + 1]
                    if (nx, nz) != (x, z):
                        last = yaw_to(x, z, nx, nz)
                out.append(last)
            return out
        back = list(reversed(pts))
        period = 2 * (pause + n)
        wid = w["id"]

        def entries(seq_pts):
            return "[%s]" % ",".join('{x:"%s",y:"%s",z:"%s",h:"%s",r:"%s"}' % (num(x), y, num(z), num(y + w["carry_height"]), num(yaw))
                                     for (x, y, z), yaw in zip(seq_pts, heading(seq_pts)))
        fn["w/%s/route" % wid] = ["data modify storage %s p.%s set value {out:%s,back:%s}" % (STORE, wid, entries(pts), entries(back))]
        fn["w/%s/tp" % wid] = ["$tp %s $(x) $(y) $(z) $(r) 0" % w_sel,
                               "$tp @e[type=minecraft:interaction,tag=%s] $(x) $(y) $(z)" % ti,
                               "$tp @e[type=minecraft:item_display,tag=%s] $(x) $(h) $(z) $(r) 0" % tc]
        for leg, start in (("out", pause), ("back", 2 * pause + n)):
            fn["w/%s/walk_%s" % (wid, leg)] = [
                "scoreboard players operation #i %s = %s %s" % (OBJ, clk, OBJ),
                "scoreboard players remove #i %s %d" % (OBJ, start),
                "execute store result storage %s arg.i int 1 run scoreboard players get #i %s" % (STORE, OBJ),
                "function %s/w/%s/go_%s with storage %s arg" % (F, wid, leg, STORE)]
            fn["w/%s/go_%s" % (wid, leg)] = ["$function %s/w/%s/tp with storage %s p.%s.%s[$(i)]" % (F, wid, STORE, wid, leg)]
            walk.append("execute if score %s %s matches %d..%d run function %s/w/%s/walk_%s"
                        % (clk, OBJ, start, start + n - 1, F, wid, leg))
        ax, ay, az = pts[0]
        bx, by, bz = pts[-1]
        up = pause - min(6, pause)                # in the pause before the walk out, never wrapped onto the walk back
        down = pause + n + min(4, pause - 1)      # in the pause at the far end, before the walk back starts
        move.append((up, ["item replace entity @e[type=minecraft:item_display,tag=%s] contents with %s" % (tc, w["carry"])]
                     + ([sound(w["pickup"]["sound"], ax, ay, az, rules)] if w["pickup"].get("sound") else [])))
        move.append((down, ["item replace entity @e[type=minecraft:item_display,tag=%s] contents with minecraft:air" % tc]
                     + ([sound(w["drop"]["sound"], bx, by, bz, rules)] if w["drop"].get("sound") else [])
                     + ([particle(w["drop"], bx, by + 0.3, bz)] if (w["drop"].get("block") or w["drop"].get("particle")) else [])))
    elif w["job"] == "work":
        x, y, z = w["start"]
        fx, fy, fz = w["face"]
        e = w["effect"]
        period = w["every"]
        yaw = w["yaw"]
        # a hop towards the work, the strike, and back
        hx, hz = w.get("hop", (x + (fx - x) * 0.12, z + (fz - z) * 0.12))
        move.append((1, ["execute as %s run tp @s %s %s %s %s 0" % (w_sel, num(hx), num(y + 0.35), num(hz), num(yaw))]))
        strike = [particle(e, fx, fy + e.get("dy", 0.6), fz)]
        if e.get("sound"):
            strike.append(sound(e["sound"], fx, fy, fz, rules, e.get("pitch", 1.0)))
        move.append((3, ["execute as %s run tp @s %s %s %s %s 0" % (w_sel, num(x), y, num(z), num(yaw))] + strike))
        if w.get("look_yaw") is not None:
            period *= 4                           # three strikes, then a look round, then back to it
            move.append((1 + w["every"], ["execute as %s run tp @s %s %s %s %s 0" % (w_sel, num(hx), num(y + 0.35), num(hz), num(yaw))]))
            move.append((3 + w["every"], ["execute as %s run tp @s %s %s %s %s 0" % (w_sel, num(x), y, num(z), num(yaw))] + strike))
            move.append((1 + 2 * w["every"], ["execute as %s run tp @s %s %s %s %s 0" % (w_sel, num(hx), num(y + 0.35), num(hz), num(yaw))]))
            move.append((3 + 2 * w["every"], ["execute as %s run tp @s %s %s %s %s 0" % (w_sel, num(x), y, num(z), num(yaw))] + strike))
            move.append((3 * w["every"], ["execute as %s run tp @s %s %s %s %s 0" % (w_sel, num(x), y, num(z), num(w["look_yaw"]))]))
    else:
        spots = w["spots"]
        period = w["every"] * len(spots)
        for k, (x, y, z, yaw) in enumerate(spots):
            px, py, pz, _ = spots[k - 1]
            tk = k * w["every"] + 1
            move.append((tk, ["particle minecraft:portal %s %s %s 0.3 0.6 0.3 0.4 30" % (num(px), num(py + 0.6), num(pz)),
                              "execute as %s run tp @s %s %s %s %s 0" % (w_sel, num(x), y, num(z), num(yaw)),
                              "execute as @e[type=minecraft:interaction,tag=%s] run tp @s %s %s %s" % (ti, num(x), y, num(z)),
                              "particle minecraft:reverse_portal %s %s %s 0.3 0.6 0.3 0.05 30" % (num(x), num(y + 0.6), num(z)),
                              sound("minecraft:entity.enderman.teleport", x, y, z, rules, 1.6)]))
    out.append("execute if score %s %s matches %d.. run scoreboard players set %s %s 0" % (clk, OBJ, period, clk, OBJ))
    out += walk
    for tk, cmds in sorted(move, key=lambda m: m[0]):
        for c in cmds:
            out.append("execute if score %s %s matches %d run %s" % (clk, OBJ, tk % period, c))
    return out


def write(pl):
    import function_limits
    if OUT.exists():
        shutil.rmtree(OUT)
    base = OUT / "data" / NS / "function" / FOLDER
    base.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: working Pokemon in the towns (tools/ambient.py)"}}, indent=2) + "\n",
                                     encoding="utf-8")
    tags = OUT / "data" / "minecraft" / "tags" / "function"
    tags.mkdir(parents=True)
    (tags / "tick.json").write_text(json.dumps({"values": ["%s/tick" % F]}) + "\n", encoding="utf-8")
    (tags / "load.json").write_text(json.dumps({"values": ["%s/load" % F]}) + "\n", encoding="utf-8")
    fns = functions(pl)
    for name, cmds in fns.items():
        refused = function_limits.check_lines(cmds, name)
        if refused:
            raise AmbientError("ambient: %s: %d command(s) the server would refuse: %s" % (name, len(refused), refused[:3]))
        p = base / (name + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(cmds) + "\n", encoding="utf-8", newline="\n")
    (base / "index.txt").write_text("\n".join(w["id"] for w in pl["workers"]) + "\n", encoding="utf-8", newline="\n")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(pl, indent=1), encoding="utf-8")
    return fns


def placement_steps():
    """reapply.py R16C: for each worker, its track trodden (if it has one), its station's chunk loaded, the worker
    placed, the chunk let go."""
    out = []
    for w in plan_workers():
        x, z = int(math.floor(w["start"][0])), int(math.floor(w["start"][2]))
        if w.get("clear"):
            out.append(("fn", "%s/w/%s/tread" % (F, w["id"])))
        out += [("cmd", "forceload add %d %d" % (x, z)), ("wait", 3), ("fn", "%s/w/%s/place" % (F, w["id"])), ("wait", 2),
                ("fn", "%s/w/%s/place" % (F, w["id"])), ("cmd", "forceload remove %d %d" % (x, z))]
    return out


def plan_workers():
    if not PLAN.is_file():
        raise AmbientError("no %s: run python tools/ambient.py build" % PLAN)
    return json.loads(PLAN.read_text(encoding="utf-8"))["workers"]


def plan_positions():
    """[(id, x, y, z)] of each worker's start, from the last build's plan."""
    return [(w["id"], w["start"][0], w["start"][1], w["start"][2]) for w in plan_workers()]


def verify(rc):
    """Over RCON on a running server: each worker exactly once, with its flags, and its box. [problems]"""
    import time
    bad = []
    for wid, x, y, z in plan_positions():
        rc("forceload add %d %d" % (math.floor(x), math.floor(z)))
        got = ""
        for _ in range(10):
            got = rc("execute if entity @e[type=cobblemon:pokemon,tag=%s.%s]" % (TAG, wid))
            if "count: 1" in got:
                break
            time.sleep(1)
        if "count: 1" not in got:
            bad.append("%s: expected one worker, got %r" % (wid, got))
        else:
            for key in ("PersistenceRequired", "Invulnerable", "Unbattleable", "NoAI"):
                r = rc("data get entity @e[type=cobblemon:pokemon,tag=%s.%s,limit=1] %s" % (TAG, wid, key))
                if "1b" not in r:
                    bad.append("%s: %s is %r" % (wid, key, r))
            if "count: 1" not in rc("execute if entity @e[type=minecraft:interaction,tag=%s.i.%s]" % (TAG, wid)):
                bad.append("%s: no interaction box" % wid)
        rc("forceload remove %d %d" % (math.floor(x), math.floor(z)))
        print("   %-28s %s" % (wid, "ok" if not any(b.startswith(wid + ":") for b in bad) else "PROBLEM"), flush=True)
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    v = sub.add_parser("verify")
    v.add_argument("--rcon", action="store_true", required=True)
    v.add_argument("--server-dir", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        pl = plan(a.source_root)
        fns = write(pl)
        for w in pl["workers"]:
            extra = len(w["points"]) if w["job"] == "carry" else len(w.get("spots") or [1])
            print("%-28s %-12s %-8s %-6s %s" % (w["id"], w["settlement"], w["species"], w["job"],
                                                "%d points" % extra if w["job"] == "carry" else ""))
        print("wrote %s: %d workers, %d functions%s" % (OUT, len(pl["workers"]), len(fns),
                                                        "" if pl["water_changed_checked"] else
                                                        " (WARNING: no derived/water_shape/changed.npy; the water rule was not checked)"))
        return 0
    import reapply
    bad = verify(reapply.Rcon(a.server_dir))
    for m in bad:
        print("PROBLEM", m)
    print("%d problems" % len(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
