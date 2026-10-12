#!/usr/bin/env python
"""Wardenhold's people and what drove them out: the burrow in Mt Vessu's face, Giratina in the ruined keep, the quest.

From data/frostpeak_keep_quest.json into the world-local pack build/datapacks/cobblers_frostpeak_keep_quest. The keep
itself, its ruin and the lair's ice are tools/frostpeak_keep.py (step R9FK); this pack is everything that lives:

  the burrow     the people who kept the keep, dug into Mt Vessu's west face at (1825, 736) (the owner, 2026-10-09):
                 a mouth through the talus, a timbered tunnel, a hall with a hearth, sleeping, stores and watch rooms.
                 The legendary chambers' order (tools/legendaries.py, tools/ursaluna_cave.py): a rock shell written
                 solid first, `margin` blocks round every room and never above the heightmap's ground, then the rooms
                 cut out of it, then floors, timber, furnishings, lanterns and the signs. Lit as towns are lit (lanterns,
                 never light blocks). Three residents (data/dialogue.json), placed by the re-application's npc action.
  Giratina       the owner, 2026-10-09: "move it to the castle in the north ... he just lives in the castle". A wild
                 Pokemon entity on the RESIDENTS' state machine, copied from tools/drowned_quarry.py keeper_files (itself
                 tools/resident_encounters.py's): dormant on its spot, awake for a player within trigger_radius,
                 settling back asleep when nobody is near, gone (beaten, caught, killed: one thing) on two loaded passes
                 in a row, back cooldown_ticks later with nobody within spawn_clear. Summoned by the re-application
                 through tools/chunk_look.py's look-then-act chain (N155), and by its keeper through a MACRO line
                 (a plain spawnpokemonat parsed at server start spawns nothing, EXP-046).
  the quest      three MoLang callbacks beside Cobblemon's own (EXP-042: a callback fires only from
                 data/cobblemon/callbacks/<event>/): battle_fainted credits EVERY player in the battle that beat it
                 (the gulch's and the Entei boss's c.players loop) with an advancement and the player tag the burrow's
                 dialogue reads; pokemon_captured records the one catch; poke_ball_capture_calculated is the Ursaluna
                 den's per-thrower gate: no catch before you have beaten it, and only one each.
  the old shrine the owner, 2026-10-09: "get rid of his sphere". shrine_takedown sets the retired Distortion shrine's
                 box (data/placements.json superseded_placements legendary_giratina_shrine) back to the heightmap's
                 ground and the water mask's water.

What this pack does NOT do: start a battle (no Cobblemon command for a wild battle), give the reward (the dialogue's
grant_reward_once does, data/rewards.json wardenhold_giratina), or touch a guardian (the blackout's tag, never held,
woken, settled or killed here; still counted as present).

Ground comes from tools/ground.py (the canonical heightmap, rounded), water from tools/water_mask.py; never a world.

  python tools/frostpeak_keep_quest.py build [--out DIR] [--source-root R]   write the pack
  python tools/frostpeak_keep_quest.py plan  [--source-root R]               the numbers and the steps
  python tools/frostpeak_keep_quest.py probes [--source-root R]              write places.frostpeak_keep_quest in data/world_probes.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "frostpeak_keep_quest.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_frostpeak_keep_quest"
SCHEMA = "cobblers.frostpeak_keep_quest/1"
PACK_FORMAT = 48          # Minecraft 1.21.1
OBJ = "cobblers.fkq"
PRESENT = -2147483648     # the return clock's "seen present" value; any other value is the game time it was first missed
FILL_MAX = 32768
CALLBACKS = "data/cobblemon/callbacks/%s/cobblers_frostpeak_keep_quest.molang"
WORLD_READS: set = set()
AIR = "minecraft:air"


class QuestError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise QuestError("%s: schema must be %s" % (path, SCHEMA))
    return doc


def unit(*key):
    h = hashlib.sha256("|".join(str(k) for k in key).encode()).hexdigest()
    return int(h[:12], 16) / float(16 ** 12)


def pick(table, u):
    acc = 0.0
    for value, share in table:
        acc += share
        if u < acc:
            return value
    return table[-1][0]


# ------------------------------------------------------------------------------------------------ the burrow
def rooms(doc):
    """{(x, y, z)} of the carved air and {(x, z): floor block} of the floors (the y is burrow.floor_y)."""
    b = doc["burrow"]
    fy = b["floor_y"]
    air, floor = set(), {}
    for r in b["rooms"]:
        x0, z0, x1, z1 = r["box"]
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                floor[(x, z)] = r["floor"]
                for y in range(fy + 1, fy + 1 + r["height"]):
                    air.add((x, y, z))
    return air, floor


def burrow_blocks(doc, g):
    """({(x, y, z): state} in write order, {(x, y, z): sign state with text}): the shell, then the rooms, then the rest."""
    b = doc["burrow"]
    fy = b["floor_y"]
    air, floor = rooms(doc)
    W, S = {}, {}
    m = b["shell"]["margin"]
    # 1. the shell: margin blocks round every carved cell (and under the floors), never above the column's own ground
    shell = set()
    for (x, y, z) in air:
        for dx in range(-m, m + 1):
            for dz in range(-m, m + 1):
                for dy in range(-m - 1, m + 1):
                    shell.add((x + dx, y + dy, z + dz))
    for (x, y, z) in sorted(shell):
        if (x, y, z) not in air and y <= g(x, z):
            W[(x, y, z)] = pick([tuple(e) for e in b["shell"]["block"]], unit("shell", x, y, z))
    # 2. the rooms, and their floors
    for c in air:
        W[c] = AIR
    for (x, z), s in floor.items():
        W[(x, fy, z)] = s
    # 3. timber sets in the tunnel: posts in the side walls, a beam in the roof
    t = b["timber"]
    mouth = next(r for r in b["rooms"] if r["id"] == "mouth")
    mz0, mz1 = mouth["box"][1], mouth["box"][3]
    top = fy + mouth["height"]
    for x in t["xs"]:
        for z in (mz0 - 1, mz1 + 1):
            for y in range(fy + 1, top + 1):
                W[(x, y, z)] = t["post"]
        for z in range(mz0 - 1, mz1 + 2):
            W[(x, top + 1, z)] = t["beam"]
    # 4. the hall: pillars, the hearth, benches, a table; the bedding, the stores, the watch room
    hall = next(r for r in b["rooms"] if r["id"] == "hall")
    for (x, z) in b["pillars"]:
        for y in range(fy + 1, fy + 1 + hall["height"]):
            W[(x, y, z)] = "minecraft:spruce_log[axis=y]"
    hx, hz = b["hearth"]
    W[(hx, fy + 1, hz)] = "minecraft:campfire[lit=true,facing=north,signal_fire=false,waterlogged=false]"
    for z in range(hz - 1, hz + 2):
        W[(hx - 3, fy + 1, z)] = "minecraft:spruce_stairs[facing=west,half=bottom,shape=straight]"
        W[(hx + 3, fy + 1, z)] = "minecraft:spruce_stairs[facing=east,half=bottom,shape=straight]"
    for x in range(hx - 1, hx + 2):
        W[(x, fy + 1, hall["box"][1] + 2)] = "minecraft:spruce_fence"
        W[(x, fy + 2, hall["box"][1] + 2)] = "minecraft:spruce_pressure_plate"
    for x in range(hx - 1, hx + 2):
        W[(x, fy + 1, hz + 5)] = "minecraft:brown_carpet"
        W[(x, fy + 1, hz + 6)] = "minecraft:brown_carpet"
    W[(hall["box"][2], fy + 1, hall["box"][1])] = "minecraft:crafting_table"
    sl = next(r for r in b["rooms"] if r["id"] == "sleeping")
    sx0, sz0, sx1, sz1 = sl["box"]
    for x in range(sx0 + 1, sx1, 3):
        for xx in (x, x + 1):
            if xx <= sx1:
                W[(xx, fy + 1, sz0)] = "minecraft:hay_block[axis=x]"
                W[(xx, fy + 2, sz0)] = "minecraft:brown_carpet"
    st = next(r for r in b["rooms"] if r["id"] == "stores")
    tx0, tz0, tx1, tz1 = st["box"]
    for x in range(tx0, tx1 + 1):
        if abs(x - (tx0 + tx1) // 2) <= 1:
            continue
        W[(x, fy + 1, tz1)] = "minecraft:barrel[facing=up,open=false]"
        if unit("stack", x) < 0.5:
            W[(x, fy + 2, tz1)] = "minecraft:barrel[facing=up,open=false]"
    W[(tx0, fy + 1, tz0 + 2)] = "minecraft:hay_block[axis=z]"
    W[(tx0, fy + 1, tz0 + 3)] = "minecraft:hay_block[axis=z]"
    W[(tx1, fy + 1, tz0 + 2)] = "minecraft:dried_kelp_block"
    W[(tx1, fy + 1, tz0 + 3)] = "minecraft:composter[level=0]"
    wa = next(r for r in b["rooms"] if r["id"] == "watch")
    W[(wa["box"][0] + 1, fy + 1, wa["box"][1])] = "minecraft:lectern[facing=south,has_book=false,powered=false]"
    # 5. the lanterns: hung under the roof, on the floors, on posts at the mouth (feet on the slope's own ground)
    lt = b["lanterns"]
    roof_of = {}
    for r in b["rooms"]:
        x0, z0, x1, z1 = r["box"]
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                roof_of[(x, z)] = fy + r["height"]
    for (x, z) in lt["hanging"]:
        W[(x, roof_of[(x, z)], z)] = "minecraft:lantern[hanging=true,waterlogged=false]"
    for (x, z) in lt["floor"]:
        W[(x, fy + 1, z)] = "minecraft:lantern[hanging=false,waterlogged=false]"
    for (x, z) in lt["posts"]:
        gy = g(x, z)
        W[(x, gy + 1, z)] = "minecraft:spruce_fence"
        W[(x, gy + 2, z)] = "minecraft:spruce_fence"
        W[(x, gy + 3, z)] = "minecraft:lantern[hanging=false,waterlogged=false]"
    # 6. the signs: wall signs, each hung on the rock (or timber) behind it, facing into the room
    sg = b["signs"]
    for s in [sg["mouth"]] + sg["watch"] + [sg["stores"]]:
        x, y, z = s["at"]
        q =",".join("'%s'" % json.dumps(tl).replace("'", "\\'") for tl in (list(s["lines"]) + ["", "", "", ""])[:4])
        W[(x, y, z)] = "minecraft:spruce_wall_sign[facing=%s,waterlogged=false]" % s["facing"]
        S[(x, y, z)] = "minecraft:spruce_wall_sign[facing=%s,waterlogged=false]{front_text:{messages:[%s]}}" % (s["facing"], q)
    return W, S


def resident_spots(doc):
    """[(id, conversation, (x, feet y, z), yaw)]: feet one above the burrow's floor."""
    fy = doc["burrow"]["floor_y"]
    return [(r["id"], r["conversation"], (r["at_xz"][0], fy + 1, r["at_xz"][1]), r["yaw"]) for r in doc["residents"]]


def burrow_box(doc, g=None):
    W, _ = burrow_blocks(doc, g) if g is not None else (None, None)
    b = doc["burrow"]
    m = b["shell"]["margin"]
    xs = [r["box"][0] for r in b["rooms"]] + [r["box"][2] for r in b["rooms"]] + [p[0] for p in b["lanterns"]["posts"]]
    zs = [r["box"][1] for r in b["rooms"]] + [r["box"][3] for r in b["rooms"]] + [p[1] for p in b["lanterns"]["posts"]]
    return min(xs) - m - 2, min(zs) - m - 2, max(xs) + m + 2, max(zs) + m + 2


def checks(doc, g, W):
    """The builder's own refusals: a room over-covered by less than 3 blocks of the heightmap's ground, a block outside
    the record's palette, a wet column under the burrow."""
    bad = []
    air, _ = rooms(doc)
    mouth = next(r for r in doc["burrow"]["rooms"] if r["id"] == "mouth")
    inner = [(x, y, z) for (x, y, z) in air if x > mouth["box"][0] + 3]
    thin = [(x, y, z) for (x, y, z) in inner if g(x, z) - y < 3]
    if thin:
        bad.append("%d carved blocks have under 3 blocks of ground over them, first %s" % (len(thin), sorted(thin)[0]))
    names = {s.split("[")[0].split("{")[0] for s in W.values()}
    out = sorted(names - set(doc["blocks"]["ids"]))
    if out:
        bad.append("blocks outside data/frostpeak_keep_quest.json blocks.ids: %s" % out)
    return bad


# ------------------------------------------------------------------------------------------------ the old shrine
def shrine_record(doc):
    pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    pid = doc["shrine_takedown"]["placement"]
    if any(p.get("id") == pid for p in pl["placements"]):
        raise QuestError("%s is still in data/placements.json placements: retire it before taking it down" % pid)
    return next(r for r in pl["superseded_placements"]["records"] if r.get("id") == pid)


def shrine_box(doc):
    import place_donor
    (x0, y0, z0), (x1, y1, z1) = place_donor.box(shrine_record(doc))
    return x0, y0, z0, x1, y1, z1


def slabs(x0, y0, z0, x1, y1, z1):
    per = max(1, FILL_MAX // ((x1 - x0 + 1) * (z1 - z0 + 1)))
    y = y0
    while y <= y1:
        yield x0, y, z0, x1, min(y1, y + per - 1), z1
        y += per


def shrine_lines(doc, g, wet=None):
    """The takedown: the box to air, every column rock to its rounded ground (the top block `surface`), then water up
    to the mask's level where it says water stands. Returns (lines, report)."""
    import resident_encounters as RE
    x0, y0, z0, x1, y1, z1 = shrine_box(doc)
    surface = doc["shrine_takedown"]["surface"]
    wet = wet or RE.Wet(g, [((x0 + x1) // 2, (z0 + z1) // 2)])
    lines = ["# the box to air (the template's dome, altar, anchor, glass, distortion blocks and its ten light blocks)"]
    lines += ["fill %d %d %d %d %d %d minecraft:air" % s for s in slabs(x0, y0, z0, x1, y1, z1)]
    lines.append("# each column back to the heightmap's ground, rounded (tools/ground.py), the slab's sunk layers included")
    rows = {}
    wet_cols = []
    for z in range(z0, z1 + 1):
        for x in range(x0, x1 + 1):
            gy = g(x, z)
            rows.setdefault((z, min(gy, y1)), []).append(x)
            lv = wet.level(x, z)
            if lv is not None and lv > gy:
                wet_cols.append((x, z, gy, int(lv)))
    for (z, gy), xs in sorted(rows.items()):
        xs.sort()
        run = [xs[0]]
        for x in xs[1:] + [None]:
            if x is not None and x == run[-1] + 1:
                run.append(x)
                continue
            if gy - 1 >= y0:
                lines.append("fill %d %d %d %d %d %d minecraft:stone" % (run[0], y0, z, run[-1], gy - 1, z))
            if gy >= y0:
                lines.append("fill %d %d %d %d %d %d %s" % (run[0], gy, z, run[-1], gy, z, surface))
            run = [x] if x is not None else []
    if wet_cols:
        lines.append("# the water mask's water over its own ground")
        lines += ["fill %d %d %d %d %d %d minecraft:water" % (x, gy + 1, z, x, min(lv, y1), z) for x, z, gy, lv in wet_cols]
    return lines, {"box": [x0, y0, z0, x1, y1, z1], "columns": (x1 - x0 + 1) * (z1 - z0 + 1), "wet_columns": len(wet_cols),
                   "ground": [min(g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)),
                              max(g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))]}


# ------------------------------------------------------------------------------------------------ Giratina
def keep_pad(g):
    import frostpeak_keep as K
    pad, bad = K.siting(K.load(), g)
    if bad:
        raise QuestError("Wardenhold's site fails: %s" % bad)
    return pad


def spot(g):
    import frostpeak_keep as K
    return K.giratina_spot(K.load(), keep_pad(g))


def _sel_xyz(p):
    return "x=%.1f,y=%d,z=%.1f" % (p[0], p[1], p[2])


def _at(p):
    return "%.1f %d %.1f" % (p[0], p[1], p[2])


def _sp(doc):
    return 'nbt={Pokemon:{Species:"cobblemon:%s"}}' % doc["giratina"]["species"]


def _nbt(d):
    return "{%s}" % ",".join("%s:%s" % kv for kv in d.items())


def _text(msg, color):
    return json.dumps({"text": msg, "color": color, "italic": color == "gold"}, ensure_ascii=False)


def giratina_files(doc, p):
    """tools/drowned_quarry.py keeper_files, line for line, plus the quest's credit, the catch gate and the tag sync."""
    ns, fo = doc["namespace"], doc["folder"]
    m = doc["giratina"]
    k = m["keeper"]
    qu = doc["quest"]
    T, D, G = m["tag"], m["dormant_tag"], m["guardian_tag"]
    sx, at, yaw = _sel_xyz(p), _at(p), m["yaw"]
    P = "%s:%s/giratina" % (ns, fo)
    x, y, z = p
    near = "@s[%s,distance=..%d]" % (sx, m["fight_radius"])
    fn = {}
    fn["load"] = ["# Generated by tools/frostpeak_keep_quest.py from data/frostpeak_keep_quest.json",
                  "scoreboard objectives add %s dummy" % OBJ,
                  "# the return clock is set here only when it was never set: a restart never moves it",
                  "execute unless score #gone %s matches -2147483648.. run scoreboard players set #gone %s %d" % (OBJ, OBJ, PRESENT),
                  "scoreboard players set #resp %s %d" % (OBJ, k["cooldown_ticks"]),
                  "schedule function %s/keeper %dt replace" % (P, k["period_ticks"])]
    fn["keeper"] = ["# the keeper's loop: the quest tag kept in step with its advancement (anyone, anywhere), then",
                    "# Giratina, only while its lair's chunk is loaded (nobody has to be near for the return clock)",
                    "execute as @a[tag=!%s,advancements={%s=true}] run tag @s add %s" % (qu["beaten_tag"], qu["defeated_advancement"], qu["beaten_tag"]),
                    "execute store result score #now %s run time query gametime" % OBJ,
                    "execute if loaded %d %d %d run function %s/keep" % (math.floor(x), y, math.floor(z), P),
                    "schedule function %s/keeper %dt replace" % (P, k["period_ticks"])]
    fn["keep"] = [
        "# Present: ours by tag (a guardian keeps our tag), or a guardian the blackout REBUILT, which does not, found by its",
        "# tag and species near the lair. Never a bare distance (THE SUMMON GUARD, R14C's failure).",
        "execute store result score #n %s if entity @e[type=cobblemon:pokemon,tag=%s]" % (OBJ, T),
        "execute if score #n %s matches 0 if entity @e[type=cobblemon:pokemon,tag=%s,%s,distance=..%d,%s] run "
        "scoreboard players set #n %s 1" % (OBJ, G, sx, k["guardian_search_radius"], _sp(doc), OBJ),
        "# a duplicate (a spawn that raced a slow entity load): the furthest one goes, and NEVER a guardian",
        "execute if score #n %s matches 2.. run kill @e[type=cobblemon:pokemon,tag=%s,tag=!%s,%s,limit=1,sort=furthest]"
        % (OBJ, T, G, sx),
        "execute if score #n %s matches 1.. run scoreboard players set #abs %s 0" % (OBJ, OBJ),
        "execute if score #n %s matches 1.. run scoreboard players set #gone %s %d" % (OBJ, OBJ, PRESENT),
        "# hold it: home, wake, settle. A guardian is the blackout's and is never held here",
        "execute if score #n %s matches 1.. as @e[type=cobblemon:pokemon,tag=%s,tag=!%s] run function %s/hold" % (OBJ, T, G, P),
        "execute if score #n %s matches 1.. run return 0" % OBJ,
        "# absent on %d loaded passes in a row (entities load a moment after their chunk) before it counts as gone"
        % k["absent_passes"],
        "scoreboard players add #abs %s 1" % OBJ,
        "execute if score #abs %s matches ..%d run return 0" % (OBJ, k["absent_passes"] - 1),
        "# first seen gone (beaten, caught or killed: all one thing here): the clock starts now. Only this line moves it",
        "execute if score #gone %s matches %d run scoreboard players operation #gone %s = #now %s" % (OBJ, PRESENT, OBJ, OBJ),
        "scoreboard players operation #d %s = #now %s" % (OBJ, OBJ),
        "scoreboard players operation #d %s -= #gone %s" % (OBJ, OBJ),
        "execute if score #d %s < #resp %s run return 0" % (OBJ, OBJ),
        "# never conjured in front of anyone, and only for a player to meet it",
        "execute if entity @a[%s,distance=..%d] run return 0" % (sx, k["spawn_clear"]),
        "execute unless entity @a[%s,distance=..%d,gamemode=!spectator] run return 0" % (sx, k["spawn_radius"]),
        "function %s/spawn" % P]
    fn["hold"] = [
        "# as Giratina (never a guardian). DORMANT: held on its spot, facing its yaw; it wakes for a player within %d."
        % m["trigger_radius"],
        "execute if entity @s[tag=%s] unless entity @s[%s,distance=..%s] run tp @s %s %s 0" % (D, sx, k["home_tolerance"], at, yaw),
        "execute if entity @s[tag=%s] if entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/wake"
        % (D, sx, m["trigger_radius"], P),
        "# AWAKE: it lies down again on its spot when nobody is within %d (a fight fled is not won)" % k["settle_radius"],
        "execute if entity @s[tag=!%s] unless entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/settle"
        % (D, sx, k["settle_radius"], P)]
    fn["wake"] = ["# as Giratina: the trigger, a STATE CHECK on the keeper's own loop, never an advancement (CELEBI_WAKE.md 1)",
                  "tag @s remove %s" % D,
                  "data merge entity @s %s" % _nbt(m["awake_nbt"]),
                  "tellraw @a[%s,distance=..48] %s" % (sx, _text(m["message"], "gold")),
                  "playsound %s hostile @a[%s,distance=..48] %s 2 0.6" % (m["sound"], sx, at)]
    fn["settle"] = ["# as Giratina: everyone has gone, so it goes back to its spot and sleeps",
                    "tp @s %s %s 0" % (at, yaw),
                    "data merge entity @s %s" % _nbt(m["dormant_nbt"]),
                    "tag @s add %s" % D]
    props = " ".join(["level=%d" % m["level"], "scale_modifier=%s" % m["scale_modifier"]] + list(m["spawn_properties"]))
    fn["spawn_at"] = ["$spawnpokemonat $(x) $(y) $(z) %s %s" % (m["species"], props)]
    fn["spawn"] = ["# a wild Giratina through the macro (EXP-046), then bound at once",
                   "function %s/spawn_at {x:\"%.1f\",y:%d,z:\"%.1f\"}" % (P, x, y, z),
                   "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..3,%s,limit=1,sort=nearest] run function %s/bind"
                   % (at, T, _sp(doc), P)]
    fn["bind"] = ["# as the new Giratina: tagged, kept from the despawner (PersistenceRequired, EXP-041), dormant on its spot",
                  "tag @s add %s" % T, "tag @s add %s" % D,
                  "data merge entity @s %s" % _nbt(m["dormant_nbt"]),
                  "tp @s %s %s 0" % (at, yaw),
                  "scoreboard players set #gone %s %d" % (OBJ, PRESENT),
                  "scoreboard players set #abs %s 0" % OBJ]
    c = m["catch"]
    fn["fainted"] = ["# as and at each player of a battle in which a wild Giratina fainted (the battle_fainted callback): the",
                     "# quest's credit, for a player at the lair (the only wild Giratina in the world lives there)",
                     "execute unless entity %s run return 0" % near,
                     "advancement grant @s only %s" % qu["defeated_advancement"],
                     "tag @s add %s" % qu["beaten_tag"],
                     "tellraw @s %s" % _text("Giratina sinks into the ice and is gone. The burrow on Mt Vessu will want to hear.", "aqua")]
    fn["caught"] = ["# as and at the player who caught a Giratina (the pokemon_captured callback): their one catch",
                    "execute unless entity %s run return 0" % near,
                    "advancement grant @s only %s" % qu["caught_advancement"]]
    F = qu["free_tag"]
    fn["catch_check"] = [
        "# as and at the thrower, from the poke_ball_capture_calculated callback: %s on the thrower = it breaks free" % F,
        "tag @s remove %s" % F,
        "# asleep: no ball takes it, and the ball wakes it",
        "execute if entity @e[tag=%s,tag=%s,%s,distance=..%d] run tag @s add %s" % (T, D, sx, m["fight_radius"], F),
        "execute if entity @s[tag=%s] run tellraw @s %s" % (F, _text(c["asleep_message"], "red")),
        "execute if entity @s[tag=%s] as @e[tag=%s,tag=%s,%s,distance=..%d] run return run function %s/wake"
        % (F, T, D, sx, m["fight_radius"], P),
        "# awake: only a thrower who has beaten it, and only once",
        "execute unless entity @s[advancements={%s=true}] run tellraw @s %s" % (qu["defeated_advancement"], _text(c["not_beaten_message"], "red")),
        "execute unless entity @s[advancements={%s=true}] run return run tag @s add %s" % (qu["defeated_advancement"], F),
        "execute if entity @s[advancements={%s=true}] run tellraw @s %s" % (qu["caught_advancement"], _text(c["caught_message"], "red")),
        "execute if entity @s[advancements={%s=true}] run tag @s add %s" % (qu["caught_advancement"], F)]
    return fn


def callback_files(doc):
    """The three MoLang callbacks (no apostrophe in a comment string: MoLang strings are single-quoted)."""
    ns, fo = doc["namespace"], doc["folder"]
    sp = "cobblemon:%s" % doc["giratina"]["species"]
    T = doc["giratina"]["tag"]
    F = doc["quest"]["free_tag"]
    fn = lambda n: "%s:%s/giratina/%s" % (ns, fo, n)   # noqa: E731
    return {
        # tools/entei_boss.py callbacks: c.pokemon.actor.is_wild, c.pokemon.pokemon, c.players, .player.uuid; EVERY player
        CALLBACKS % "battle_fainted": "\n".join([
            "'Generated by tools/frostpeak_keep_quest.py. A wild Giratina fainting in battle: every player in the battle';",
            "'who stands at Wardenhold is credited with the burrow quest (frostpeak_keep_quest/giratina/fainted).';",
            "c.pokemon.actor.is_wild ? {",
            "  t.pk = c.pokemon.pokemon;",
            "  t.pk.species.identifier == '%s' ? {" % sp,
            "    for_each(t.a, c.players, {",
            "      q.run_command('execute as ' + t.a.player.uuid + ' at @s run function %s');" % fn("fainted"),
            "    });",
            "  };",
            "};", ""]),
        # tools/hoopa_cradle.py and tools/entei_boss.py: q.pokemon.species.identifier, q.player.uuid
        CALLBACKS % "pokemon_captured": "\n".join([
            "'Generated by tools/frostpeak_keep_quest.py. A Giratina caught at Wardenhold: the catcher has had their one.';",
            "t.id = q.pokemon.species.identifier;",
            "t.id == '%s' ? {" % sp,
            "  q.run_command('execute as ' + q.player.uuid + ' at @s run function %s');" % fn("caught"),
            "};", ""]),
        # tools/ursaluna_cave.py: the tag handshake through the thrower
        CALLBACKS % "poke_ball_capture_calculated": "\n".join([
            "'Generated by tools/frostpeak_keep_quest.py. A ball at Wardenhold s Giratina: asleep, it breaks free and wakes';",
            "'it; awake, it breaks free unless the thrower has beaten it and has not caught one before.';",
            "t.pk = q.pokemon;",
            "t.th = q.thrower;",
            "t.pk.has_tag('%s') ? {" % T,
            "  t.th.is_player ? {",
            "    q.run_command('execute as ' + t.th.uuid + ' at @s run function %s');" % fn("catch_check"),
            "    t.th.has_tag('%s') ? {" % F,
            "      q.set_shakes(0);",
            "      t.th.remove_tag('%s');" % F,
            "    };",
            "  };",
            "};", ""]),
    }


def chain_files(doc, p):
    """The look-then-act chain the re-application starts (tools/chunk_look.py), tools/drowned_quarry.py chain_files'."""
    import chunk_look as CL
    ns, fo = doc["namespace"], doc["folder"]
    base, holder, new = chain_names(doc)
    scope = "type=cobblemon:pokemon,tag=%s" % doc["giratina"]["tag"]
    x, _y, z = p
    box = (int(x) - 24, int(z) - 24, int(x) + 24, int(z) + 24)
    act = ["# the summon, once a look has seen this box's saved entities (or blind after %d ticks: a first run)" % CL.BLIND_TICKS,
           "execute unless entity @e[%s] run function %s:%s/giratina/spawn_new" % (scope, ns, fo)]
    fns = CL.chain(base, box, ["@e[%s]" % scope], act, [scope], new, scope, holder, note="tools/frostpeak_keep_quest.py")
    out = {ref.split(":", 1)[1].split("/", 1)[1]: lines for ref, lines in fns.items()}
    out["giratina/spawn_new"] = ["# as the act: the summon, then the new Giratina marked for the chain's de-duplication",
                                 "function %s:%s/giratina/spawn" % (ns, fo),
                                 "execute positioned %s as @e[%s,distance=..3,limit=1,sort=nearest] run tag @s add %s"
                                 % (_at(p), scope, new)]
    return out, box


def chain_names(doc):
    ns, fo = doc["namespace"], doc["folder"]
    return "%s:%s/place" % (ns, fo), "fk_giratina", doc["giratina"]["tag"] + ".new"


def impossible():
    return {"criteria": {"granted": {"trigger": "minecraft:impossible"}}, "requirements": [["granted"]]}


# ------------------------------------------------------------------------------------------------ the pack
def merge_boxes(cells):
    by_state = {}
    for p_, s in cells.items():
        by_state.setdefault(s, set()).add(p_)
    out = []
    for s, pts in sorted(by_state.items()):
        left = set(pts)
        for (x, y, z) in sorted(pts, key=lambda q: (q[1], q[2], q[0])):
            if (x, y, z) not in left:
                continue
            xe = x
            while (xe + 1, y, z) in left:
                xe += 1
            ze = z
            while all((xx, y, ze + 1) in left for xx in range(x, xe + 1)):
                ze += 1
            ye = y
            while all((xx, ye + 1, zz) in left for xx in range(x, xe + 1) for zz in range(z, ze + 1)):
                ye += 1
            for xx in range(x, xe + 1):
                for yy in range(y, ye + 1):
                    for zz in range(z, ze + 1):
                        left.discard((xx, yy, zz))
            out.append((x, y, z, xe, ye, ze, s))
    return out


def burrow_lines(doc, g):
    W, S = burrow_blocks(doc, g)
    bad = checks(doc, g, W)
    if bad:
        raise QuestError("the burrow fails: " + "; ".join(bad))
    lines = ["# Generated by tools/frostpeak_keep_quest.py from data/frostpeak_keep_quest.json: the burrow in Mt Vessu's face.",
             "# chunks-loaded-by: R18FK (forceload add %d %d %d %d before this runs)" % burrow_box(doc)]
    # the shell first (solid rock), then the air, then everything else: three passes so a later write wins
    shell = {k: v for k, v in W.items() if v.split("[")[0] in ("minecraft:stone", "minecraft:tuff", "minecraft:andesite")}
    air = {k: v for k, v in W.items() if v == AIR}
    rest = {k: v for k, v in W.items() if k not in shell and k not in air and k not in S}
    for part in (shell, air, rest):
        for (x0, y0, z0, x1, y1, z1, s) in merge_boxes(part):
            lines.append("setblock %d %d %d %s" % (x0, y0, z0, s) if (x0, y0, z0) == (x1, y1, z1)
                         else "fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, s))
    for (x, y, z), s in sorted(S.items()):
        lines.append("setblock %d %d %d %s" % (x, y, z, s))
    return lines


def files(doc, g):
    ns, fo = doc["namespace"], doc["folder"]
    p = spot(g)
    fn = {"burrow/build": burrow_lines(doc, g)}
    sl, _rep = shrine_lines(doc, g)
    fn["shrine_takedown"] = ["# Generated by tools/frostpeak_keep_quest.py: the retired Distortion shrine taken down (the owner, 2026-10-09)",
                             "# chunks-loaded-by: R18FK (forceload add over the box before this runs)"] + sl
    fn.update({"giratina/" + k: v for k, v in giratina_files(doc, p).items()})
    chain, _box = chain_files(doc, p)
    fn.update(chain)
    out = {}
    for n, lines in fn.items():
        if not n.startswith("giratina/spawn_at"):
            bad = function_limits.check_lines(lines, "%s/%s" % (fo, n))
            if bad:
                raise QuestError("%s/%s has %d command(s) the server would refuse: %s" % (fo, n, len(bad), bad[:2]))
        out["data/%s/function/%s/%s.mcfunction" % (ns, fo, n)] = "\n".join(lines) + "\n"
    out.update(callback_files(doc))
    qu = doc["quest"]
    for adv in (qu["defeated_advancement"], qu["caught_advancement"]):
        ans, path = adv.split(":", 1)
        out["data/%s/advancement/%s.json" % (ans, path)] = json.dumps(impossible(), indent=2) + "\n"
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/giratina/load" % (ns, fo)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: Wardenhold's burrow, its Giratina and the quest (tools/frostpeak_keep_quest.py)"}},
                                    indent=2) + "\n"
    return out


# ------------------------------------------------------------------------------------------------ the re-application
def npc_placements(doc=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for tools/reapply.py's "npc" action, from the committed data."""
    doc = doc or load()
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    convs = {c["id"]: c for c in dl["conversations"]}
    out = []
    for rid, conv, at, yaw in resident_spots(doc):
        c = convs.get(conv)
        if c is None or not c.get("npc_id"):
            raise QuestError("%s is not a conversation with an NPC in data/dialogue.json" % conv)
        out.append((conv, at, "%s:%s" % (doc["namespace"], c["npc_id"]), yaw))
    return out


def placement_steps(doc=None, ground=None):
    """For tools/reapply.py R18FK (after the restart that loads cobblers_dialogue's NPC classes, and after R9FK built
    the keep): take the old shrine down, dig the burrow, summon Giratina through the look-then-act chain, then the
    three residents. Each block step holds its own chunks and releases them before the chain (a forceload is per chunk,
    not counted)."""
    import chunk_look as CL
    import ground as G
    doc = doc or load()
    ground = ground or G.load()
    ns, fo = doc["namespace"], doc["folder"]
    sx0, _sy0, sz0, sx1, _sy1, sz1 = shrine_box(doc)
    shrine = "%d %d %d %d" % (sx0, sz0, sx1, sz1)
    burrow = "%d %d %d %d" % burrow_box(doc)
    base, holder, _new = chain_names(doc)
    return ([("cmd", "forceload add " + shrine), ("wait", 3), ("fn", "%s:%s/shrine_takedown" % (ns, fo)),
             ("cmd", "forceload remove " + shrine),
             ("cmd", "forceload add " + burrow), ("wait", 3), ("fn", "%s:%s/burrow/build" % (ns, fo)),
             ("cmd", "forceload remove " + burrow)]
            + CL.steps(base, holder, 1, "Wardenhold's Giratina")
            + [("npc", n) for n in npc_placements(doc)])


def probes(doc, g):
    """[probe] in data/world_probes.json's shape: the burrow's blocks, the old shrine's ground, Giratina."""
    W, S = burrow_blocks(doc, g)
    b = doc["burrow"]
    fy = b["floor_y"]
    rows = []

    def blk(what, x, y, z):
        rows.append({"what": what, "block": [x, y, z, W[(x, y, z)].split("{")[0]], "expect": True})
    hx, hz = b["hearth"]
    blk("the burrow's hearth (a lit campfire)", hx, fy + 1, hz)
    blk("a pillar of the hall", b["pillars"][0][0], fy + 2, b["pillars"][0][1])
    blk("the tunnel's first timber beam (the portal in the face)", b["timber"]["xs"][0], fy + 4, 736)
    blk("the hall's floor (packed mud)", hx + 2, fy, hz + 2)
    blk("the stores' barrels", 1844, fy + 1, 751)
    x, y, z = b["lanterns"]["hanging"][2][0], None, b["lanterns"]["hanging"][2][1]
    y = next(yy for yy in range(fy, fy + 8) if W.get((x, yy, z), "").startswith("minecraft:lantern"))
    blk("a hung lantern in the hall", x, y, z)
    k = sorted(S)[0]
    rows.append({"what": "a sign of the burrow", "block": list(k) + [S[k].split("{")[0]], "expect": True})
    x0, y0, z0, x1, y1, z1 = shrine_box(doc)
    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
    rows.append({"what": "the old Distortion shrine's altar cell, now air (the shrine is taken down)",
                 "block": [x0 + 23, y0 + 12, z0 + 20, "minecraft:air"], "expect": True})
    rows.append({"what": "the old shrine's ground at its middle, rock again at the heightmap's height",
                 "block": [cx, g(cx, cz), cz, doc["shrine_takedown"]["surface"]], "expect": True})
    sp = spot(g)
    rows.append({"what": "Giratina in Wardenhold's yard (one tagged %s; absent while its return clock runs)" % doc["giratina"]["tag"],
                 "hold": [math.floor(sp[0]), sp[1], math.floor(sp[2])],
                 "entity": "@e[type=cobblemon:pokemon,tag=%s]" % doc["giratina"]["tag"], "count": 1})
    return rows


def write(files_, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files_.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("build", "plan", "probes"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    g = G.load(a.source_root)
    doc = load()
    if a.action == "probes":
        wp = ROOT / "data" / "world_probes.json"
        d = json.loads(wp.read_text(encoding="utf-8"))
        d["places"]["frostpeak_keep_quest"] = probes(doc, g)
        wp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("wrote %d probes under places.frostpeak_keep_quest in data/world_probes.json" % len(d["places"]["frostpeak_keep_quest"]))
        return 0
    if a.action == "plan":
        _l, rep = shrine_lines(doc, g)
        print(json.dumps({"giratina_spot": spot(g), "burrow_box": burrow_box(doc), "shrine": rep,
                          "residents": resident_spots(doc), "steps": placement_steps(doc, g)}, indent=1, default=list))
        return 0
    fs = files(doc, g)
    write(fs, a.out)
    n = sum(len(t.splitlines()) for r, t in fs.items() if r.endswith(".mcfunction"))
    print("frostpeak_keep_quest: %d files -> %s (%d function lines; Giratina at %s)" % (len(fs), a.out, n, spot(g)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
