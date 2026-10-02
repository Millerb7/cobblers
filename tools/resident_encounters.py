#!/usr/bin/env python
"""The ten named residents of data/resident_encounters.json: their dressing, their keeper and their re-application.

Codex authored ten memorable non-legendary residents in sparse parts of the map (PR #107, `rules` is the spec). This
tool builds all ten into one pack, cobblers_residents, on patterns the repository already runs:

  the dressing   per resident, the blocks its build_brief names (drag marks, a wreck, snapped poles, a migration
                 scar, a failed orchard...), from small primitives in the record's `build.dressing`, every block seated
                 on the canonical heightmap's rounded ground (tools/ground.py), never on a world. Surface work replaces
                 the ground's TOP block only (the height never changes); nothing is written under the ground, and no
                 land primitive writes on a wet column (tools/water_mask.py's lakes and sea, and the river corridors of
                 data/rivers.json).
  the resident   a wild Pokemon entity, the Ursaluna den's and the gulch Megas' way:
                   - spawned by a MACRO (`residents/spawn_at`): `spawnpokemonat` written plainly in a function spawns
                     nothing when parsed at server start (EXP-046); a macro line is parsed when it runs
                   - re-applied over RCON by R18R for the residents that need no gate (placement_steps below), guarded on
                     its TAG and its SPECIES, never a bare distance (THE SUMMON GUARD, tools/ursaluna_cave.py)
                   - kept by a 40-tick loop (`residents/keeper`) with the gulch's respawn clock: the game time it was
                     first seen gone on two passes in a row, written only by the keeper; it comes back respawn ticks
                     later (rules.respawn_ticks_after_faint_death_or_catch), with a player near and none close
                   - DORMANT (NoAI, on its spot, facing its yaw) until a player comes within its trigger; then awake,
                     leashed to its anchor, and settled back asleep when everyone has gone
  the blackout   a resident that beats a player becomes that claim's guardian (data/resident_encounters.json
                 build.blackout_decision). From then on this pack only COUNTS it: every hold, wake, settle and kill
                 selector carries tag=!cobblers.guardian. Nothing here ever adds cobblers.gm (the blackout's exempt tag).

What this pack does NOT do: start a battle (Cobblemon 1.8.0 has no command for a wild battle), change Fight or Flight
(rules.aggression: its config is global), drop or give anything (rules.no_loot_drops), or name the Pokemon in game.

  python tools/resident_encounters.py                # -> build/datapacks/cobblers_residents
  python tools/resident_encounters.py --report       # the sites as measured, the writes, the steps; nothing written
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data" / "resident_encounters.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_residents"
SCHEMA = "cobblers.resident-encounters/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
PRESENT = -2147483648   # the respawn clock's "seen present" value; any other value is the game time it was first missed
KINDS = ("strip", "post", "log", "blocks", "tree")


class ResidentError(ValueError):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ResidentError("%s: schema must be %s" % (path, SCHEMA))
    rules, b = doc["rules"], doc["build"]
    enc = doc["encounters"]
    if len(enc) != rules["count"]:
        raise ResidentError("rules.count is %d but %d encounters are authored" % (rules["count"], len(enc)))
    for e in enc:
        bb = e.get("build")
        if not bb:
            raise ResidentError("%s has no build block" % e["id"])
        if not (0 < bb["trigger"] < bb["leash"]):
            raise ResidentError("%s: the trigger must be inside the leash" % e["id"])
        perm = e["id"] in rules["permanently_uncatchable"]
        if perm != (e["catch_rule"] == "permanently_uncatchable"):
            raise ResidentError("%s: catch_rule disagrees with rules.permanently_uncatchable" % e["id"])
        for p in bb["dressing"]:
            if p["kind"] not in KINDS:
                raise ResidentError("%s: unknown dressing kind %s" % (e["id"], p["kind"]))
    if b["keeper"]["spawn_clear"] >= b["keeper"]["spawn_radius"]:
        raise ResidentError("spawn_clear must be inside spawn_radius, or nothing ever spawns")
    return doc


def species(e):
    return e["species"].split(":", 1)[1]


def species_sel(e):
    return 'nbt={Pokemon:{Species:"%s"}}' % e["species"]


# ------------------------------------------------------------------ water and ground


class Wet:
    """(x, z) -> True where water stands: tools/water_mask.py (lakes, tarns, marsh, sea) and the river corridors."""

    def __init__(self, ground, near):
        import water_mask as WM
        self.WM, self.g = WM, ground
        self.bodies = WM.bodies()
        rv = json.loads((ROOT / "data" / "rivers.json").read_text(encoding="utf-8"))
        self.river = []
        for c in rv.get("courses") or []:
            w = max((c.get("character") or {}).get("width") or [32])
            for p in c.get("graded_polyline") or []:
                if any(math.hypot(p[0] - x, p[1] - z) < 400 for x, z in near):
                    self.river.append((p[0], p[1], p[2], w / 2.0 + 1))
        self.cache = {}

    def level(self, x, z):
        """The water surface y over (x, z), or None where dry."""
        k = (x, z)
        if k not in self.cache:
            lv = self.WM.level_at(x, z, self.g, self.bodies)[1]
            if lv is None:
                gy = self.g(x, z)
                for px, pz, sy, half in self.river:
                    if abs(px - x) <= half and abs(pz - z) <= half and math.hypot(px - x, pz - z) <= half and gy < sy:
                        lv = int(round(sy))
                        break
            self.cache[k] = lv
        return self.cache[k]

    def __call__(self, x, z):
        return self.level(x, z) is not None


def anchor(e, ground, wet=None):
    """(x, feet y, z): feet one above the rounded ground; in water, one above the water's surface block."""
    x, z = e["location"]["x"], e["location"]["z"]
    if e["build"].get("in_water"):
        lv = (wet or Wet(ground, [(x, z)])).level(x, z)
        if lv is None:
            raise ResidentError("%s is built in water but (%d, %d) is dry" % (e["id"], x, z))
        return x, int(lv) + 1, z
    return x, ground(x, z) + 1, z


# ------------------------------------------------------------------ the dressing


def _h32(x, z, salt):
    return ((x * 73856093) ^ (z * 19349663) ^ (salt * 83492791)) & 0xFFFFFFFF


def _pick(palette, x, z, salt):
    total = sum(w for _b, w in palette)
    r = _h32(x, z, salt) % total
    for b, w in palette:
        if r < w:
            return b
        r -= w
    return palette[-1][0]


def _seg_cols(a, b, half):
    """Integer (dx, dz) offsets whose centre lies within half + 0.5 of the segment a-b."""
    (ax, az), (bx, bz) = a, b
    vx, vz = bx - ax, bz - az
    L2 = vx * vx + vz * vz
    r = half + 0.5
    out = []
    for dx in range(int(math.floor(min(ax, bx) - r)), int(math.ceil(max(ax, bx) + r)) + 1):
        for dz in range(int(math.floor(min(az, bz) - r)), int(math.ceil(max(az, bz) + r)) + 1):
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((dx - ax) * vx + (dz - az) * vz) / L2))
            if math.hypot(dx - (ax + t * vx), dz - (az + t * vz)) <= r:
                out.append((dx, dz))
    return out


def _axis(block, axis):
    return block if "[" in block else "%s[axis=%s]" % (block, axis)


def dressing(e, ground, wet):
    """[(x, y, z, block, primitive name)] block writes, and [(x, y0, z, y1, name)] plant clears, for one resident."""
    ax, az = e["location"]["x"], e["location"]["z"]
    sets, clears = [], []
    for i, p in enumerate(e["build"]["dressing"]):
        k, name, water = p["kind"], p.get("name", p["kind"]), bool(p.get("in_water"))

        def ok(x, z):
            return wet(x, z) == water
        if k == "strip":
            for dx, dz in _seg_cols(p["from"], p["to"], p["half_width"]):
                x, z = ax + dx, az + dz
                if not ok(x, z):
                    continue
                gy = ground(x, z)
                sets.append((x, gy, z, _pick(p["surface"], x, z, i + 1), name))
                if p.get("clear"):
                    clears.append((x, gy + 1, z, gy + int(p["clear"]), name))
        elif k == "post":
            x, z = ax + p["at"][0], az + p["at"][1]
            if not ok(x, z):
                continue
            gy = ground(x, z)
            for j, b in enumerate(p["blocks"]):
                sets.append((x, gy + 1 + j, z, b, name))
        elif k == "log":
            ddx, ddz = (1, 0) if p["dir"] == "x" else (0, 1)
            for j in range(int(p["length"])):
                x, z = ax + p["from"][0] + ddx * j, az + p["from"][1] + ddz * j
                if ok(x, z):
                    sets.append((x, ground(x, z) + 1, z, _axis(p["block"], p["dir"]), name))
        elif k == "blocks":
            # each block on its OWN column's ground: an object seated on one base level buries its uphill side
            # (the audit's first run found the wreck's planks a block under the beach)
            bx, bz = ax + p["at"][0], az + p["at"][1]
            for ddx, dy, ddz, b in p["blocks"]:
                x, z = bx + ddx, bz + ddz
                if ok(x, z):
                    sets.append((x, ground(x, z) + dy, z, b, name))
        elif k == "tree":
            bx, bz = ax + p["at"][0], az + p["at"][1]
            if not ok(bx, bz):
                continue
            base = ground(bx, bz)
            ux, uz = p["lean"]
            trunk = []
            for j in range(int(p["height"])):
                trunk.append((bx + int(round(j * ux * 0.35)), base + 1 + j, bz + int(round(j * uz * 0.35))))
            for x, y, z in trunk:
                sets.append((x, y, z, p["log"], name))
            tx, ty, tz = trunk[-1]
            r = int(p["radius"])
            ts = set(trunk)
            for dx in range(-r, r + 1):
                for dy in range(-1, r + 1):
                    for dz in range(-r, r + 1):
                        if math.sqrt(dx * dx + dy * dy + dz * dz) <= r + 0.2 and (tx + dx, ty + dy, tz + dz) not in ts:
                            sets.append((tx + dx, ty + dy, tz + dz, p["leaves"], name))
    # one block per position: the last primitive wins (a post on a strip's column stands on the strip's surface)
    last = {}
    for s in sets:
        last[(s[0], s[1], s[2])] = s
    return list(last.values()), clears


def stand_clears(a, ground):
    """The standing space: plants off the anchor's 3x3, from each column's own ground + 1 (never into the ground) up
    to the resident's feet + 1."""
    out = []
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            x, z = a[0] + dx, a[2] + dz
            y0 = max(ground(x, z) + 1, a[1])
            if y0 <= a[1] + 1:
                out.append((x, y0, z, a[1] + 1, "standing space"))
    return out


def bbox(sets, clears, at):
    xs = [s[0] for s in sets] + [c[0] for c in clears] + [at[0]]
    zs = [s[2] for s in sets] + [c[2] for c in clears] + [at[2]]
    return [min(xs), min(zs), max(xs), max(zs)]


def site(e, ground, wet):
    """(anchor, block writes, plant clears, the record's bbox), refusing a record whose measured anchor or bbox no
    longer matches what the heightmap gives (the record is what other builders check their collisions against)."""
    a = anchor(e, ground, wet)
    sets, clears = dressing(e, ground, wet)
    clears = clears + stand_clears(a, ground)
    box = bbox(sets, clears, a)
    bb = e["build"]
    if list(a) != list(bb.get("anchor") or []):
        raise ResidentError("%s: the heightmap puts the anchor at %s, the record says %s" % (e["id"], list(a), bb.get("anchor")))
    rb = bb.get("bbox") or []
    if len(rb) != 4 or not (rb[0] <= box[0] and rb[1] <= box[1] and box[2] <= rb[2] and box[3] <= rb[3]):
        raise ResidentError("%s: the dressing's box %s is not inside the record's bbox %s" % (e["id"], box, rb))
    return a, sets, clears, rb


# ------------------------------------------------------------------ the pack


def _at(a):
    return "%.1f %d %.1f" % (a[0] + 0.5, a[1], a[2] + 0.5)


def _sel_xyz(a):
    return "x=%.1f,y=%d,z=%.1f" % (a[0] + 0.5, a[1], a[2] + 0.5)


def _nbt(d):
    return "{%s}" % ",".join("%s:%s" % kv for kv in d.items())


def dormant_nbt(e):
    d = {"NoAI": "1b", "PersistenceRequired": "1b"}
    d.update(e["build"].get("dormant_extra") or {})
    return d


def awake_nbt(e):
    d = {"NoAI": "0b"}
    for k in (e["build"].get("dormant_extra") or {}):
        d[k] = "0b"
    return d


def spawn_props(doc, e):
    props = ["level=%d" % int(e["level"])]
    if e["id"] in doc["rules"]["permanently_uncatchable"]:
        props.append("uncatchable")
    return props


def gate_sel(doc, e):
    g = e["build"].get("appears_after")
    return ",advancements={%s:flag/%s=true}" % (doc["build"]["namespace"], g) if g else ""


def resident_files(doc, e, a, sets, clears, box):
    b, k = doc["build"], doc["build"]["keeper"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    i, bb = e["id"], e["build"]
    tag, rtag, dtag, gtag = b["tag"], "%s.%s" % (b["tag"], i), b["dormant_tag"], b["guardian_tag"]
    P = "%s:%s/%s" % (ns, F, i)
    at, sx = _at(a), _sel_xyz(a)
    yaw = bb["yaw"]
    msg = json.dumps({"text": bb["message"], "color": "gold", "italic": True}, ensure_ascii=False)
    gone, abs_ = "#%s.gone" % i, "#%s.abs" % i
    fn = {}
    dress = ["# Generated by tools/resident_encounters.py from data/resident_encounters.json: %s's dressing" % e["name"],
             "# chunks-loaded-by: the re-application R18R (forceload add %d %d %d %d over RCON before this runs)" % tuple(box),
             "# 1. the plants off the surface work and the standing space (only #minecraft:replaceable: grass, ferns,",
             "#    snow layers, vines), each column from its own ground + 1"]
    dress += ["fill %d %d %d %d %d %d air replace #minecraft:replaceable" % (x, y0, z, x, y1, z) for x, y0, z, y1, _n in clears]
    dress.append("# 2. the blocks, each on the rounded heightmap ground of its own column")
    dress += ["setblock %d %d %d %s replace" % (x, y, z, s) for x, y, z, s, _n in sorted(sets, key=lambda t: (t[1], t[0], t[2]))]
    fn["%s/dress" % i] = dress
    keep = [
        "# %s (%s, level %d): kept on the keeper's loop while its anchor's chunk is loaded." % (e["name"], e["species"], e["level"]),
        "# Present: ours by tag (a guardian keeps our tag), or a guardian the blackout REBUILT, which does not, found by",
        "# its tag and species near the anchor. Never a bare distance (THE SUMMON GUARD).",
        "execute store result score #n %s if entity @e[type=cobblemon:pokemon,tag=%s]" % (obj, rtag),
        "execute if score #n %s matches 0 if entity @e[type=cobblemon:pokemon,tag=%s,%s,distance=..%d,%s] run "
        "scoreboard players set #n %s 1" % (obj, gtag, sx, bb["leash"] + k["guardian_search_margin"], species_sel(e), obj),
        "# a duplicate (a spawn that raced a slow entity load): the furthest one goes, and NEVER a guardian",
        "execute if score #n %s matches 2.. run kill @e[type=cobblemon:pokemon,tag=%s,tag=!%s,%s,limit=1,sort=furthest]"
        % (obj, rtag, gtag, sx),
        "execute if score #n %s matches 1.. run scoreboard players set %s %s 0" % (obj, abs_, obj),
        "execute if score #n %s matches 1.. run scoreboard players set %s %s %d" % (obj, gone, obj, PRESENT),
        "# hold it: leash, wake, settle - a guardian is the blackout's and is never held here",
        "execute if score #n %s matches 1.. as @e[type=cobblemon:pokemon,tag=%s,tag=!%s] run function %s/hold" % (obj, rtag, gtag, P),
        "execute if score #n %s matches 1.. run return 0" % obj,
        "# absent on two passes in a row (entities load a moment after their chunk) before it counts as gone",
        "scoreboard players add %s %s 1" % (abs_, obj),
        "execute if score %s %s matches ..1 run return 0" % (abs_, obj),
        "# first seen gone: the respawn clock starts now. Only this line moves it",
        "execute if score %s %s matches %d run scoreboard players operation %s %s = #now %s" % (gone, obj, PRESENT, gone, obj, obj),
        "scoreboard players operation #d %s = #now %s" % (obj, obj),
        "scoreboard players operation #d %s -= %s %s" % (obj, gone, obj),
        "execute if score #d %s < #resp %s run return 0" % (obj, obj),
        "# never conjured in front of anyone",
        "execute if entity @a[%s,distance=..%d] run return 0" % (sx, k["spawn_clear"]),
        "# a player near to meet it%s" % (", holding %s (its presence gate)" % bb["appears_after"] if bb.get("appears_after") else ""),
        "execute unless entity @a[%s,distance=..%d,gamemode=!spectator%s] run return 0" % (sx, k["spawn_radius"], gate_sel(doc, e)),
        "function %s/spawn" % P]
    fn["%s/keep" % i] = keep
    fn["%s/hold" % i] = [
        "# as the resident (never a guardian): the leash, from its anchor",
        "execute unless entity @s[%s,distance=..%d] run tp @s %s" % (sx, bb["leash"], at),
        "# DORMANT: held on its spot, facing its yaw; it wakes for the first player within its trigger",
        "execute if entity @s[tag=%s] unless entity @s[%s,distance=..%s] run tp @s %s %s 0" % (dtag, sx, k["home_tolerance"], at, yaw),
        "execute if entity @s[tag=%s] if entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/wake"
        % (dtag, sx, bb["trigger"], P),
        "# AWAKE: settles back onto its spot asleep when nobody is within leash + %d" % k["settle_margin"],
        "execute if entity @s[tag=!%s] unless entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/settle"
        % (dtag, sx, bb["leash"] + k["settle_margin"], P)]
    fn["%s/wake" % i] = [
        "# as the resident: its trigger (rules.aggression: a bounded local trigger; Fight or Flight is never changed)",
        "tag @s remove %s" % dtag,
        "data merge entity @s %s" % _nbt(awake_nbt(e)),
        "tellraw @a[%s,distance=..48] %s" % (sx, msg),
        "playsound %s hostile @a[%s,distance=..48] %s 2 0.8" % (bb["sound"], sx, at)]
    fn["%s/settle" % i] = [
        "# as the resident: everyone has gone, so it goes back to its spot and sleeps",
        "tp @s %s %s 0" % (at, yaw),
        "data merge entity @s %s" % _nbt(dormant_nbt(e)),
        "tag @s add %s" % dtag]
    fn["%s/spawn" % i] = [
        "# a wild %s through the macro (EXP-046), then bound at once" % e["name"],
        "function %s:%s/spawn_at {x:\"%.1f\",y:%d,z:\"%.1f\",species:\"%s\",props:\"%s\"}"
        % (ns, F, a[0] + 0.5, a[1], a[2] + 0.5, species(e), " ".join(spawn_props(doc, e))),
        "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..2,%s,limit=1,sort=nearest] run function %s/bind"
        % (at, tag, species_sel(e), P)]
    fn["%s/bind" % i] = [
        "# as the new resident: tagged, kept from the despawner (PersistenceRequired, EXP-041), dormant on its spot",
        "tag @s add %s" % tag, "tag @s add %s" % rtag, "tag @s add %s" % dtag,
        "data merge entity @s %s" % _nbt(dormant_nbt(e)),
        "tp @s %s %s 0" % (at, yaw),
        "scoreboard players set %s %s %d" % (gone, obj, PRESENT),
        "scoreboard players set %s %s 0" % (abs_, obj)]
    if not bb.get("appears_after"):
        # only an ungated resident is summoned by R18R; a gated one appears through its keeper alone
        fn["%s/bind_new" % i] = [
            "# run by R18R just after its RCON summon: the nearest undressed %s at the anchor" % e["name"],
            "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..4,%s,limit=1,sort=nearest] run function %s/bind"
            % (at, tag, species_sel(e), P)]
    return fn


def files(doc, ground, wet=None):
    b, k, rules = doc["build"], doc["build"]["keeper"], doc["rules"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    enc = doc["encounters"]
    wet = wet or Wet(ground, [(e["location"]["x"], e["location"]["z"]) for e in enc])
    fn = {"spawn_at": ["# a macro, so the mod's command is parsed when it runs (EXP-046, .claude/rules/datapacks.md)",
                       "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]}
    load = ["# the residents' keeper state (tools/resident_encounters.py). Scores survive a restart in the world's scoreboard;",
            "# a clock that has never been set starts READY (respawn ticks already elapsed), so a fresh world fills at once",
            "scoreboard objectives add %s dummy" % obj,
            "scoreboard players set #resp %s %d" % (obj, int(rules["respawn_ticks_after_faint_death_or_catch"])),
            "execute store result score #ready %s run time query gametime" % obj,
            "scoreboard players operation #ready %s -= #resp %s" % (obj, obj)]
    keeper = ["execute store result score #now %s run time query gametime" % obj]
    for e in enc:
        a, sets, clears, box = site(e, ground, wet)
        i = e["id"]
        load += ["execute unless score #%s.gone %s matches -2147483648.. run scoreboard players operation #%s.gone %s = #ready %s"
                 % (i, obj, i, obj, obj),
                 "execute unless score #%s.abs %s matches -2147483648.. run scoreboard players set #%s.abs %s 0" % (i, obj, i, obj)]
        keeper.append("execute if loaded %d %d %d run function %s:%s/%s/keep" % (a[0], a[1], a[2], ns, F, i))
        fn.update(resident_files(doc, e, a, sets, clears, box))
    load.append("schedule function %s:%s/keeper %dt replace" % (ns, F, k["period_ticks"]))
    keeper.append("schedule function %s:%s/keeper %dt replace" % (ns, F, k["period_ticks"]))
    fn["load"] = load
    fn["keeper"] = keeper
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, F, n): "\n".join(v) + "\n" for n, v in fn.items()}
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, F)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT,
                                              "description": "Cobblers: the ten named residents "
                                                             "(tools/resident_encounters.py)"}}, indent=2) + "\n"
    return out


# ------------------------------------------------------------------ the re-application


def summon_command(doc, e, a):
    b, k = doc["build"], doc["build"]["keeper"]
    at = _at(a)
    return ("execute unless entity @e[type=cobblemon:pokemon,tag=%s.%s] positioned %s "
            "unless entity @e[type=cobblemon:pokemon,tag=%s,distance=..%d,%s] "
            "unless entity @e[type=cobblemon:pokemon,distance=..4,%s] run spawnpokemonat %s %s %s"
            % (b["tag"], e["id"], at, b["guardian_tag"], e["build"]["leash"] + k["guardian_search_margin"],
               species_sel(e), species_sel(e), at, species(e), " ".join(spawn_props(doc, e))))


def placement_steps(doc=None, ground=None):
    """For tools/reapply.py R18R: per resident, hold its box, dress it, and - only where it has no presence gate -
    summon it over RCON and bind it; then release. A gated resident is left to its keeper, which spawns it the first
    time a player holding the gate comes near (build.appears_after_rule)."""
    import ground as G
    doc = doc or load()
    ground = ground or G.load()
    enc = doc["encounters"]
    wet = Wet(ground, [(e["location"]["x"], e["location"]["z"]) for e in enc])
    b = doc["build"]
    steps = []
    for e in enc:
        a, sets, clears, box = site(e, ground, wet)
        hold = "%d %d %d %d" % tuple(box)
        P = "%s:%s/%s" % (b["namespace"], b["folder"], e["id"])
        steps += [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s/dress" % P)]
        if not e["build"].get("appears_after"):
            steps += [("cmd", summon_command(doc, e, a)), ("wait", 1), ("fn", "%s/bind_new" % P)]
        steps.append(("cmd", "forceload remove " + hold))
    return steps


# ------------------------------------------------------------------ CLI


def report(doc, ground):
    enc = doc["encounters"]
    wet = Wet(ground, [(e["location"]["x"], e["location"]["z"]) for e in enc])
    lines = []
    for e in enc:
        a, sets, clears, box = site(e, ground, wet)
        bb = e["build"]
        lines.append("%-16s %-22s L%-2d anchor %s ground y%d feet y%d yaw %s trigger %d leash %d appears_after %s; "
                     "%d blocks, %d clears, bbox %s"
                     % (e["id"], e["species"], e["level"], (a[0], a[1], a[2]), ground(a[0], a[2]), a[1], bb["yaw"],
                        bb["trigger"], bb["leash"], bb.get("appears_after"), len(sets), len(clears), box))
    steps = placement_steps(doc, ground)
    lines.append("steps: %d (%d summons)" % (len(steps), sum(1 for s in steps if s[0] == "cmd" and "spawnpokemonat" in s[1])))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the sites, the writes and the steps; write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.report:
        print("\n".join(report(doc, g)))
        return 0
    written = files(doc, g)
    import function_limits
    bad = []
    for rel, text in written.items():
        if rel.endswith(".mcfunction"):
            bad += ["%s:%d %s: %s" % (rel, n, cmd, why)
                    for n, cmd, why in function_limits.check_lines(text.splitlines(), where=rel)]
    for msg in bad:
        print("ERROR %s" % msg)
    if bad:
        return 1
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in written.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    n = sum(1 for rel, t in written.items() if rel.endswith("/dress.mcfunction")
            for l in t.splitlines() if l and not l.startswith("#"))
    print("resident_encounters: %d files -> %s (dressing: %d commands, %d residents)" % (len(written), out, n,
                                                                                     len(doc["encounters"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
