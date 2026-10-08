#!/usr/bin/env python
"""Generate the Entei boss pack from data/entei_boss.json: one repeatable legendary, each player their own copy.

docs/mechanics/NETHER_DUNGEON_SCOPE.md option B, built as the first slice of option A. The owner's decisions of
2026-10-10 are recorded in data/entei_boss.json `decision`.

THE LOOP. A player crafts an Ember Sigil from Nether materials (a datapack recipe) and eats it anywhere in the
Nether. A minecraft:consume_item advancement runs `enter` as them: past the Champion, outside the lockout, with a
free slot, standing in the Nether -> their Nether block is stored and they are teleported into their own slot, a
sealed room in cobblers:pocket. Anything else -> the sigil is given back with the reason. The keeper spawns their
Entei once per run: catchable (props.catch) until they hold cobblers:entei_boss/caught, uncatchable (props.farm)
after. A catch grants the advancement (pokemon_captured); a farm-mode faint in battle rolls one item from the drop
table into their inventory (battle_fainted). Losing blacks them out through the existing blackout, with no item claim
(the Entei carries data/blackout.json claims.exempt_tag). The arch in the room takes them back to their Nether block.

Patterns reused, each cited where it is used:
  tools/hoopa_cradle.py   the per-player owned legendary: the owner number on the entity, the macro spawn (EXP-046),
                          the bind by species selector, the leash, the pokemon_captured callback and its advancement
  tools/gulch_mine.py     the battle_fainted callback shape and the Mining Fatigue ward
  tools/portals.py        the pocket room's arch, its click advancement (EXP-034) and the block commands
  tools/blackout_pack.py  the macro teleport from stored scores (blackout/checkpoint/tp) and the exempt tag

What it emits (namespace cobblers, folder entei_boss/):
  load            objectives, free slots, the keeper's schedule
  keeper          every period_ticks: tend each owned slot; sweep the band for anyone not in their own slot
  slot/s<k>/...   tend, free, appear, bind, roll, caught, faint_catch: one set per slot, so no macro picks a slot
  enter           the sigil's checks, the store and the teleport
  refund          the sigil back, with the reason
  check, eject    the band sweep's test, and the way out (also the arch's)
  leave           the arch: frees the clicker's slot, then eject
  fainted, caught as the player, from the two callbacks
  place, rooms/*  the rooms, built by tools/reapply.py step R16Q
and an advancement for the sigil, one for the arch, one for the catch; a recipe; a loot table; two MoLang callbacks.

  python tools/entei_boss.py                 # write build/datapacks/cobblers_entei_boss
  python tools/entei_boss.py --out <dir>

Ownership: the output is generated and lives in build/ (gitignored); data/entei_boss.json is the source. What the
pack does NOT cover is data/entei_boss.json does_not_cover.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402
import portals  # noqa: E402  (the room's block commands, its interaction summon and the click advancement)

DATA = ROOT / "data" / "entei_boss.json"
PORTALS = ROOT / "data" / "portals.json"
BLACKOUT = ROOT / "data" / "blackout.json"
WORLD = ROOT / "data" / "world.json"
BANK_OUT = ROOT / "modpack" / "config" / "cobbledollars" / "bank.json"
BANK_DATA = ROOT / "data" / "bank.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_entei_boss"
SCHEMA = "cobblers.entei_boss/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
CALLBACKS = "data/cobblemon/callbacks/%s/cobblers_entei_boss.molang"
STORE = "cobblers:entei_boss"
SIGIL_ADV = "entei_boss/sigil"
EXIT_ADV = "entei_boss/exit"
OBJ_RE = re.compile(r"^[a-z0-9_.]{1,16}$")


class EnteiError(ValueError):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise EnteiError("%s: schema must be %s" % (path, SCHEMA))
    return doc


def _j(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------- geometry


def slot_centre(doc, k):
    """Slot k (1-based): its centre column."""
    p = doc["pocket"]
    return p["origin"][0] + (k - 1) * p["spacing"], p["origin"][1]


def slot_geometry(doc, k):
    """{centre, spot, arrive, click, box} for slot k. The arch is tools/portals.py room_blocks' arch: against the
    low-z wall at cz - half, its click one block in front, the arrival three in front, facing south (yaw 0)."""
    cx, cz = slot_centre(doc, k)
    r, fy = doc["room"], doc["pocket"]["floor_y"]
    half, height = r["half"], r["height"]
    az = cz - half
    return {
        "centre": (cx, cz),
        "spot": (cx, fy, cz + r["spot_dz"]),
        "arch_z": az,
        "click": (cx, fy, az + 1),
        "arrive": (cx, fy, az + 3),
        # the presence box: the interior and its decorative walls, floor to ceiling
        "box": (cx - half - 1, fy - 1, cz - half - 1, 2 * half + 2, height + 1, 2 * half + 2),
    }


def band_box(doc, margin=64):
    """(x, y, z, dx, dy, dz) over every slot with a margin, the whole height of the dimension."""
    n, half = doc["pocket"]["slots"], doc["room"]["half"]
    xs = [slot_centre(doc, k)[0] for k in range(1, n + 1)]
    zs = [slot_centre(doc, k)[1] for k in range(1, n + 1)]
    x0, z0 = min(xs) - half - margin, min(zs) - half - margin
    x1, z1 = max(xs) + half + margin, max(zs) + half + margin
    return (x0, 0, z0, x1 - x0, 255, z1 - z0)


def room_blocks(doc, k):
    """[(x, y, z, block)] for slot k's room: bedrock outside, one decorative course inside it, air within, four
    lights, the arch. Later entries win (tools/portals.py commands)."""
    g = slot_geometry(doc, k)
    cx, cz = g["centre"]
    r, pal, fy = doc["room"], doc["room"]["palette"], doc["pocket"]["floor_y"]
    half, height = r["half"], r["height"]
    out = []
    for x in range(cx - half - 2, cx + half + 3):
        for y in range(fy - 2, fy + height + 2):
            for z in range(cz - half - 2, cz + half + 3):
                dx, dz = abs(x - cx), abs(z - cz)
                outer = dx == half + 2 or dz == half + 2 or y in (fy - 2, fy + height + 1)
                if outer:
                    b = pal["outer"]
                elif y == fy - 1:
                    b = pal["floor"]
                elif y == fy + height:
                    b = pal["ceiling"]
                elif dx == half + 1 or dz == half + 1:
                    b = pal["wall"]
                else:
                    b = "minecraft:air"
                out.append((x, y, z, b))
    for dx in (-half + 2, half - 2):
        for dz in (-half + 2, half - 2):
            out.append((cx + dx, fy + height, cz + dz, pal["light"]))
    az = g["arch_z"]
    for rr in (-2, 2):
        for dy in (0, 1, 2):
            out.append((cx + rr, fy + dy, az, pal["frame"]))
    for rr in (-1, 0, 1):
        for dy in (0, 1, 2):
            out.append((cx + rr, fy + dy, az, pal["sheet"]))
    for rr in range(-2, 3):
        out.append((cx + rr, fy + 3, az, pal["frame"]))
    return out


# ------------------------------------------------------------------------------------------------- checks


def bank_items():
    """Every item id the CobbleDollars bank buys: the generated file (base list plus ours) and data/bank.json buys."""
    ids = set()
    if BANK_OUT.is_file():
        for e in (_j(BANK_OUT).get("bank") or []):
            if isinstance(e, dict) and e.get("item"):
                ids.add(e["item"])
    for e in (_j(BANK_DATA).get("buys") or []):
        if isinstance(e, dict) and e.get("item"):
            ids.add(e["item"])
    return ids


def problems(doc, portals_doc=None, blackout=None, world=None, bank=None):
    """[problem] in the record, held against the pocket the portals define, the border, the overworld map, the
    blackout's exempt tag and the bank's buy list."""
    portals_doc = portals_doc if portals_doc is not None else _j(PORTALS)
    blackout = blackout if blackout is not None else _j(BLACKOUT)
    world = world if world is not None else _j(WORLD)
    bank = bank if bank is not None else bank_items()
    bad = []
    p, r = doc["pocket"], doc["room"]
    pp = portals_doc["pocket"]
    if p["dimension"] != pp["dimension"]:
        bad.append("pocket.dimension %s is not data/portals.json's %s" % (p["dimension"], pp["dimension"]))
    if p["floor_y"] != pp["floor_y"]:
        bad.append("pocket.floor_y %d differs from data/portals.json's %d" % (p["floor_y"], pp["floor_y"]))
    gen = pp["generator"]
    if not (gen["min_y"] < p["floor_y"] - 2 and p["floor_y"] + r["height"] + 1 < gen["min_y"] + gen["height"]):
        bad.append("the room does not fit the dimension's height")
    if p["slots"] < 1 or p["spacing"] < 2 * (r["half"] + 3):
        bad.append("slots %d / spacing %d: rooms would touch" % (p["slots"], p["spacing"]))
    # the portals' rescue sweeps everyone below their floor inside its box (tools/portals.py files): stay out of it
    rz0 = min(pp["bands"].values()) - pp["rescue_margin"]
    rz1 = max(pp["bands"].values()) + pp["rescue_margin"]
    bx, _by, bz, bdx, _bdy, bdz = band_box(doc)
    if not (bz + bdz < rz0 or bz > rz1):
        bad.append("the band's z %d..%d meets the portals' rescue box z %d..%d" % (bz, bz + bdz, rz0, rz1))
    lo, hi = p["border"]
    m = p["border_margin"]
    if bx < lo + m or bz < lo + m or bx + bdx > hi - m or bz + bdz > hi - m:
        bad.append("the band %s leaves the world border %d..%d less %d" % ((bx, bz, bx + bdx, bz + bdz), lo, hi, m))
    wb = world["bounds"]
    inside_map = not (bx + bdx < wb["min_x"] or bx > wb["max_x"] or bz + bdz < wb["min_z"] or bz > wb["max_z"])
    if inside_map:
        bad.append("the band overlaps the overworld map's bounds: an overworld checkpoint could share its coordinates")
    if not 1 <= r["leash"] < r["half"]:
        bad.append("leash %d: must be at least 1 and inside the room's half-width %d" % (r["leash"], r["half"]))
    if not 0 < r["spot_dz"] < r["half"]:
        bad.append("spot_dz %d is outside the room" % r["spot_dz"])
    # the boss
    lvl = int(doc["level"])
    if not 1 <= lvl <= 100:
        bad.append("level %d" % lvl)
    for phase in ("catch", "farm"):
        props = doc["props"][phase]
        found = re.findall(r"(?:^| )level=(\d+)", props)
        if found != [str(lvl)]:
            bad.append("props.%s must carry level=%d exactly once (found %s)" % (phase, lvl, found))
        if re.search(r"(?:^| )alpha=", props):
            bad.append("props.%s carries alpha: Cobblemon re-levels an alpha above the party (research note)" % phase)
    if "uncatchable" in doc["props"]["catch"].split():
        bad.append("props.catch is uncatchable: the first clear would never be catchable")
    if "uncatchable" not in doc["props"]["farm"].split():
        bad.append("props.farm is catchable: a player could catch a second Entei every run")
    if doc["gate_flag"] != "cobblers:flag/champion_cleared" and lvl > 60:
        bad.append("level %d with a gate before the Champion: above the 60 cap the catch block refuses every ball" % lvl)
    # the drops: items, not bankable, no plates, no money
    for e in doc["drops"]["entries"]:
        it = e["item"]
        if it in bank:
            bad.append("drop %s is on the bank's buy list: a drop would launder into money" % it)
        if it.endswith("_plate") or "plate" in it.split(":", 1)[-1]:
            bad.append("drop %s is a plate: no Arceus plates (the owner)" % it)
        if it.startswith("cobbledollars:"):
            bad.append("drop %s is money" % it)
        if int(e["weight"]) < 1 or int(e["count"]) < 1:
            bad.append("drop %s weight/count" % it)
    # the key's materials and the key itself
    if doc["key"]["item"] in {i["item"] for i in doc["key"]["recipe"]["ingredients"]}:
        bad.append("the sigil's base item is one of its own ingredients")
    if sum(i["count"] for i in doc["key"]["recipe"]["ingredients"]) > 9:
        bad.append("the recipe needs more than 9 items: it does not fit a crafting grid")
    if "minecraft:custom_data" not in doc["key"]["components"] or "minecraft:food" not in doc["key"]["components"]:
        bad.append("the sigil needs custom_data (to be told apart) and food (to be eaten)")
    # the blackout exemption is read, never copied
    if not (blackout.get("claims") or {}).get("exempt_tag"):
        bad.append("data/blackout.json has no claims.exempt_tag to put on the Entei")
    for name in doc["objectives"].values():
        if not OBJ_RE.match(name):
            bad.append("objective %r" % name)
    if len(set(doc["objectives"].values())) != len(doc["objectives"]):
        bad.append("two objectives share a name")
    k = doc["keeper"]
    if k["period_ticks"] < 1 or k["arrive_delay_ticks"] < k["period_ticks"]:
        bad.append("keeper period %d / arrive delay %d" % (k["period_ticks"], k["arrive_delay_ticks"]))
    if doc["lockout"]["ticks"] < 0:
        bad.append("lockout")
    return bad


# ------------------------------------------------------------------------------------------------- the sigil


def snbt(v):
    """A component value as SNBT for a `give` (the same value the recipe carries as JSON)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return "%sf" % repr(v)
    if isinstance(v, str):
        return "'%s'" % v.replace("\\", "\\\\").replace("'", "\\'") if '"' in v else '"%s"' % v
    if isinstance(v, list):
        return "[%s]" % ",".join(snbt(x) for x in v)
    if isinstance(v, dict):
        return "{%s}" % ",".join("%s:%s" % (k, snbt(x)) for k, x in v.items())
    raise EnteiError("component value %r" % (v,))


def sigil_give(doc):
    key = doc["key"]
    return "%s[%s]" % (key["item"], ",".join("%s=%s" % (k, snbt(v)) for k, v in key["components"].items()))


def recipe(doc):
    key = doc["key"]
    ings = []
    for i in key["recipe"]["ingredients"]:
        ings += [{"item": i["item"]}] * int(i["count"])
    return {"type": "minecraft:crafting_shapeless", "category": "misc", "ingredients": ings,
            "result": {"id": key["item"], "count": 1, "components": key["components"]}}


def sigil_advancement(doc, fn):
    """minecraft:consume_item on the sigil, matched by its custom_data (tools/research_station.py _item_json's
    shape). No dimension condition: the function decides, so a sigil eaten in the wrong place is refunded."""
    key = doc["key"]
    return {"criteria": {"eat": {"trigger": "minecraft:consume_item", "conditions": {
                "item": {"items": key["item"],
                         "components": {"minecraft:custom_data": key["components"]["minecraft:custom_data"]}}}}},
            "requirements": [["eat"]], "rewards": {"function": fn}}


def loot_table(doc):
    return {"pools": [{"rolls": int(doc["drops"]["rolls"]), "entries": [
        {"type": "minecraft:item", "name": e["item"], "weight": int(e["weight"]),
         "functions": [{"function": "minecraft:set_count", "count": int(e["count"])}]}
        for e in doc["drops"]["entries"]]}]}


# ------------------------------------------------------------------------------------------------- functions


def _fn(doc, name):
    return "%s:%s/%s" % ("cobblers", "entei_boss", name)


def _sel_box(box, extra=""):
    x, y, z, dx, dy, dz = box
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d%s" % (x, y, z, dx, dy, dz, ("," + extra) if extra else "")


def _species_sel(doc):
    # tools/hoopa_cradle.py _species_sel: a wild one of the species
    return 'nbt={Pokemon:{Species:"%s",PokemonOriginalTrainerType:"NONE"}}' % doc["species"]["id"]


def functions(doc, blackout=None):
    blackout = blackout if blackout is not None else _j(BLACKOUT)
    o, m, k, t = doc["objectives"], doc["message"], doc["keeper"], doc["tags"]
    ID, OWN, SLOT, RUN, LAST, CLR, RUNS = o["id"], o["own"], o["slot"], o["run"], o["last"], o["clears"], o["runs"]
    MODE, SP, ROLL, AT, RX, RY, RZ, W = (o["mode"], o["spawned"], o["rolled"], o["at"], o["rx"], o["ry"], o["rz"],
                                         o["work"])
    dim = doc["pocket"]["dimension"]
    n = doc["pocket"]["slots"]
    exempt = blackout["claims"]["exempt_tag"]
    caught_adv = doc["catch"]["advancement"]
    gate = doc["gate_flag"]
    head = "# Generated by tools/entei_boss.py from data/entei_boss.json; never edit (build/ is regenerated)."

    def say(key, colour, tail=None):
        parts = [{"text": m[key], "color": colour, "italic": True}]
        if tail:
            parts.append(tail)
        body = parts[0] if len(parts) == 1 else [""] + parts
        return "tellraw @s %s" % json.dumps(body, ensure_ascii=False)

    out = {}
    out["load"] = [head] + ["scoreboard objectives add %s dummy" % v for v in o.values()] + [
        "# a slot is free at 0; an unset score would match nothing, so each starts at 0"] + [
        "execute unless score #s%d %s matches -2147483648.. run scoreboard players set #s%d %s 0" % (i, OWN, i, OWN)
        for i in range(1, n + 1)] + [
        "execute unless score #runs %s matches 1.. run scoreboard players set #runs %s 0" % (RUN, RUN),
        "scoreboard players set #100 %s 100" % W,
        "scoreboard players set #1200 %s 1200" % W,
        "schedule function %s %dt replace" % (_fn(doc, "keeper"), k["period_ticks"])]
    bb = band_box(doc)
    out["keeper"] = [
        head,
        "# Every %d ticks. Each owned slot is tended; then every player in the band who is not standing in their" % k["period_ticks"],
        "# own slot is sent out. Selectors that must stay in %s carry a position (EXP-047 result 4)." % dim,
        "execute store result score #now %s run time query gametime" % W] + [
        "execute if score #s%d %s matches 1.. run function %s" % (i, OWN, _fn(doc, "slot/s%d/tend" % i))
        for i in range(1, n + 1)] + [
        "execute in %s as @a[%s] at @s run function %s" % (dim, _sel_box(bb, "gamemode=!spectator"), _fn(doc, "check")),
        "schedule function %s %dt replace" % (_fn(doc, "keeper"), k["period_ticks"])]

    out["check"] = [
        head,
        "# As a player in the band, in %s (the keeper's selector put us there). Valid only standing in the slot" % dim,
        "# their run owns. @s box tests are coordinate-only, which is safe here because the dimension is known.",
        "scoreboard players set #ok %s 0" % W] + [
        "execute if score @s %s matches %d if score @s %s = #s%d %s if entity @s[%s] run scoreboard players set #ok %s 1"
        % (SLOT, i, ID, i, OWN, _sel_box(slot_geometry(doc, i)["box"]), W) for i in range(1, n + 1)] + [
        "execute if score #ok %s matches 0 run function %s" % (W, _fn(doc, "eject"))]

    fb = blackout["pallet"]["position"]
    out["eject"] = [
        head,
        "# As a player leaving (the arch, or the sweep): the run is over for them. Back to the Nether block they ate",
        "# the sigil in, as the blackout returns a player (tools/blackout_pack.py blackout/checkpoint/tp), then onto",
        "# that block's centre by a relative step, which is right for negative coordinates too.",
        "scoreboard players set @s %s 0" % SLOT,
        "execute unless score @s %s matches -2147483648.. run return run execute in minecraft:overworld run tp @s %d %d %d"
        % (RX, fb[0], fb[1], fb[2]),
        "execute store result storage %s go.x int 1 run scoreboard players get @s %s" % (STORE, RX),
        "execute store result storage %s go.y int 1 run scoreboard players get @s %s" % (STORE, RY),
        "execute store result storage %s go.z int 1 run scoreboard players get @s %s" % (STORE, RZ),
        "function %s with storage %s go" % (_fn(doc, "go"), STORE),
        "execute at @s run tp @s ~0.5 ~ ~0.5",
        say("out", "gold")]
    out["go"] = ["$execute in minecraft:the_nether run tp @s $(x) $(y) $(z)"]

    out["leave"] = [
        head,
        "# The arch, clicked (the proven click trigger, tools/portals.py click_advancement, EXP-034). Never gated:",
        "# whatever else is true, a player can always leave. The slot is freed while its owner still stands in it,",
        "# so its Entei is killed with its chunk loaded.",
        "advancement revoke @s only cobblers:%s" % EXIT_ADV,
        "execute as @e[type=minecraft:interaction,tag=%s,distance=..8] run data remove entity @s interaction" % t["exit"]] + [
        "execute if score @s %s matches %d if score @s %s = #s%d %s run function %s"
        % (SLOT, i, ID, i, OWN, _fn(doc, "slot/s%d/free" % i)) for i in range(1, n + 1)] + [
        "function %s" % _fn(doc, "eject")]

    # ---- the sigil ------------------------------------------------------------------------------------------
    lock = doc["lockout"]["ticks"]
    enter = [
        head,
        "# As the player who has just eaten an Ember Sigil, at them (minecraft:consume_item). #why: 0 go, 1 not in",
        "# the Nether, 2 already in a run, 3 before the Champion, 4 lockout, 5 every slot busy.",
        "advancement revoke @s only cobblers:%s" % SIGIL_ADV,
        "execute unless score @s %s matches 1.. run scoreboard players add #next %s 1" % (ID, ID),
        "execute unless score @s %s matches 1.. run scoreboard players operation @s %s = #next %s" % (ID, ID, ID),
        "scoreboard players operation #me %s = @s %s" % (W, ID),
        "execute store result score #now %s run time query gametime" % W,
        "scoreboard players set #why %s 0" % W,
        "# 1: the Nether, tested with a positional player selector in that dimension (a bare @s is not dimension-checked)",
        "scoreboard players set #nether %s 0" % W,
        "execute in minecraft:the_nether positioned as @s as @a[distance=..0.5] if score @s %s = #me %s run "
        "scoreboard players set #nether %s 1" % (ID, W, W),
        "execute if score #nether %s matches 0 run scoreboard players set #why %s 1" % (W, W)]
    enter += ["execute if score #why %s matches 0 if score @s %s matches %d if score @s %s = #s%d %s run "
              "scoreboard players set #why %s 2" % (W, SLOT, i, ID, i, OWN, W) for i in range(1, n + 1)]
    enter += [
        "execute if score #why %s matches 0 unless entity @s[advancements={%s=true}] run scoreboard players set #why %s 3"
        % (W, gate, W),
        "scoreboard players operation #d %s = #now %s" % (W, W),
        "scoreboard players operation #d %s -= @s %s" % (W, LAST),
        "execute if score #why %s matches 0 if score @s %s matches -2147483648.. if score #d %s matches ..%d run "
        "scoreboard players set #why %s 4" % (W, LAST, W, lock - 1, W),
        "scoreboard players set #pick %s 0" % W]
    enter += ["execute if score #pick %s matches 0 if score #s%d %s matches 0 run scoreboard players set #pick %s %d"
              % (W, i, OWN, W, i) for i in range(1, n + 1)]
    enter += [
        "execute if score #why %s matches 0 if score #pick %s matches 0 run scoreboard players set #why %s 5" % (W, W, W),
        "execute unless score #why %s matches 0 run return run function %s" % (W, _fn(doc, "refund")),
        "# go: the lockout starts now (counted from entry: data/entei_boss.json lockout.why)",
        "scoreboard players operation @s %s = #now %s" % (LAST, W),
        "scoreboard players add @s %s 1" % RUNS,
        "# where they stand, to come back to: x and z floored, y rounded up (a slab top is 0.5 above its block)",
        "execute store result score @s %s run data get entity @s Pos[0]" % RX,
        "execute store result score @s %s run data get entity @s Pos[2]" % RZ,
        "execute store result score @s %s run data get entity @s Pos[1] 100" % RY,
        "scoreboard players add @s %s 99" % RY,
        "scoreboard players operation @s %s /= #100 %s" % (RY, W),
        "scoreboard players add #runs %s 1" % RUN,
        "scoreboard players operation @s %s = #pick %s" % (SLOT, W)]
    for i in range(1, n + 1):
        ax, ay, az = slot_geometry(doc, i)["arrive"]
        enter += ["execute if score #pick %s matches %d run function %s" % (W, i, _fn(doc, "slot/s%d/open" % i))]
        out["slot/s%d/open" % i] = [
            head,
            "# As the player taking slot %d: the slot is theirs for this run, and they cross into it." % i,
            "scoreboard players operation #s%d %s = @s %s" % (i, OWN, ID),
            "scoreboard players operation #s%d %s = #runs %s" % (i, RUN, RUN),
            "scoreboard players operation #s%d %s = #now %s" % (i, AT, W),
            "scoreboard players set #s%d %s 0" % (i, SP),
            "scoreboard players set #s%d %s 0" % (i, ROLL),
            "scoreboard players set #s%d %s 0" % (i, MODE),
            say("enter", "gold"),
            "execute in %s run tp @s %.1f %d %.1f 0 0" % (dim, ax + 0.5, ay, az + 0.5)]
    out["enter"] = enter
    give = "give @s %s 1" % sigil_give(doc)
    lock_tail = {"score": {"name": "#rem", "objective": W}, "color": "gold"}
    out["refund"] = [
        head,
        "# As a player whose sigil opened nothing: it comes back, with the reason (#why, set by enter).",
        give,
        "execute if score #why %s matches 1 run %s" % (W, say("refund_dimension", "gray")),
        "execute if score #why %s matches 2 run %s" % (W, say("refund_run", "gray")),
        "execute if score #why %s matches 3 run %s" % (W, say("refund_gate", "gray")),
        "scoreboard players set #rem %s %d" % (W, lock),
        "scoreboard players operation #rem %s -= #d %s" % (W, W),
        "scoreboard players add #rem %s 1199" % W,
        "scoreboard players operation #rem %s /= #1200 %s" % (W, W),
        "execute if score #why %s matches 4 run %s" % (W, say("refund_lockout", "gray", lock_tail)),
        "execute if score #why %s matches 5 run %s" % (W, say("refund_busy", "gray"))]

    # ---- the slots ------------------------------------------------------------------------------------------
    leash = doc["room"]["leash"]
    for i in range(1, n + 1):
        g = slot_geometry(doc, i)
        sx, sy, sz = g["spot"]
        at = "%.1f %d %.1f" % (sx + 0.5, sy, sz + 0.5)
        box = _sel_box(g["box"])
        stag = "%s.s%d" % (t["boss"], i)
        S = "#s%d" % i
        out["slot/s%d/tend" % i] = [
            head,
            "# Slot %d, owned. Is its owner standing in it?" % i,
            "scoreboard players set #here %s 0" % W,
            "execute in %s as @a[%s] if score @s %s = %s %s run scoreboard players set #here %s 1" % (dim, box, ID, S, OWN, W),
            "execute if score #here %s matches 0 run return run function %s" % (W, _fn(doc, "slot/s%d/free" % i)),
            "# the ward (the gulch's: Mining Fatigue to a player at the faces, data/gulch_mine.json faces.why)",
            "execute in %s as @a[%s,gamemode=!creative,gamemode=!spectator] run effect give @s minecraft:mining_fatigue 3 %d true"
            % (dim, box, k["ward_amplifier"]),
            "# an Entei with this slot's tag but another run's number is stale (its run ended while its chunk was unloaded)",
            "execute as @e[type=cobblemon:pokemon,tag=%s] unless score @s %s = %s %s run kill @s" % (stag, RUN, S, RUN),
            "# once per run, after the arrival delay",
            "scoreboard players operation #d %s = #now %s" % (W, W),
            "scoreboard players operation #d %s -= %s %s" % (W, S, AT),
            "execute if score %s %s matches 0 if score #d %s matches %d.. run function %s"
            % (S, SP, W, k["arrive_delay_ticks"], _fn(doc, "slot/s%d/appear" % i)),
            "# the leash",
            "execute in %s positioned %s as @e[type=cobblemon:pokemon,tag=%s,distance=..64] unless entity @s[distance=..%d] run tp @s %s"
            % (dim, at, stag, leash, at)]
        out["slot/s%d/free" % i] = [
            head,
            "# Slot %d's run is over (its owner left, by the arch, a blackout, a death or a logout)." % i,
            "kill @e[type=cobblemon:pokemon,tag=%s]" % stag,
            "scoreboard players operation #me %s = %s %s" % (W, S, OWN),
            "# an owner who is online elsewhere has no run any more; an offline one is caught by check when they return",
            "execute as @a if score @s %s = #me %s run scoreboard players set @s %s 0" % (ID, W, SLOT),
            "scoreboard players set %s %s 0" % (S, OWN),
            "scoreboard players set %s %s 0" % (S, SP),
            "scoreboard players set %s %s 0" % (S, ROLL),
            "scoreboard players set %s %s 0" % (S, MODE)]
        out["slot/s%d/appear" % i] = [
            head,
            "# Slot %d: the owner's Entei, catchable until they have caught one (data/entei_boss.json catch.rule)." % i,
            "scoreboard players set %s %s 1" % (S, SP),
            "scoreboard players set %s %s 1" % (S, MODE),
            "execute in %s as @a[%s] if score @s %s = %s %s if entity @s[advancements={%s=true}] run scoreboard players set %s %s 2"
            % (dim, box, ID, S, OWN, caught_adv, S, MODE),
            "execute if score %s %s matches 1 in %s run function %s {x:\"%.1f\",y:%d,z:\"%.1f\",props:\"%s %s\"}"
            % (S, MODE, dim, _fn(doc, "spawn_at"), sx + 0.5, sy, sz + 0.5, doc["species"]["id"].split(":", 1)[1],
               doc["props"]["catch"]),
            "execute if score %s %s matches 2 in %s run function %s {x:\"%.1f\",y:%d,z:\"%.1f\",props:\"%s %s\"}"
            % (S, MODE, dim, _fn(doc, "spawn_at"), sx + 0.5, sy, sz + 0.5, doc["species"]["id"].split(":", 1)[1],
               doc["props"]["farm"]),
            "execute in %s positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..3,%s,limit=1,sort=nearest] run function %s"
            % (dim, at, t["boss"], _species_sel(doc), _fn(doc, "slot/s%d/bind" % i)),
            "execute in %s as @a[%s] if score @s %s = %s %s run %s" % (dim, box, ID, S, OWN, say("appear", "red"))]
        out["slot/s%d/bind" % i] = [
            head,
            "# As slot %d's new Entei: ours by tag, this run's number, its owner's number, kept from the despawner" % i,
            "# (tools/hoopa_cradle.py bind), and the blackout's exempt tag: a loss to it makes no item claim",
            "# (data/blackout.json claims.exempt_why; the gulch Megas carry it the same way)",
            "tag @s add %s" % t["boss"],
            "tag @s add %s" % stag,
            "tag @s add %s" % exempt,
            "scoreboard players operation @s %s = %s %s" % (RUN, S, RUN),
            "scoreboard players operation @s %s = %s %s" % (OWN, S, OWN),
            "data merge entity @s {PersistenceRequired:1b}"]
        out["slot/s%d/settle" % i] = [
            head,
            "# As slot %d's owner, standing in it, when their Entei has fainted in a battle (from fainted)." % i,
            "# nothing unless this run spawned its Entei (mode 1 catch, 2 farm) and is not yet settled",
            "execute unless score %s %s matches 1..2 run return 0" % (S, MODE),
            "execute unless score %s %s matches 0 run return 0" % (S, ROLL),
            "scoreboard players set %s %s 1" % (S, ROLL),
            "execute if score %s %s matches 1 run return run %s" % (S, MODE, say("faint_catch", "gray")),
            "scoreboard players add @s %s 1" % CLR,
            "loot give @s loot %s" % doc["drops"]["loot_table"],
            say("drop", "gold")]
        out["slot/s%d/caught" % i] = [
            head,
            "# As slot %d's owner, standing in it, who has just caught an Entei (from caught): theirs to keep." % i,
            "execute unless score %s %s matches 1 run return 0" % (S, MODE),
            "execute unless score %s %s matches 0 run return 0" % (S, ROLL),
            "scoreboard players set %s %s 1" % (S, ROLL),
            "scoreboard players add @s %s 1" % CLR,
            "execute unless entity @s[advancements={%s=true}] run %s" % (caught_adv, say("caught", "gold")),
            "advancement grant @s only %s" % caught_adv]
    out["spawn_at"] = [
        "# a macro, so the mod's command is parsed when it runs (EXP-046, .claude/rules/datapacks.md); run with",
        "# `execute in` the pocket dimension, so the spawn lands there",
        "$spawnpokemonat $(x) $(y) $(z) $(props)"]

    def from_callback(name, target):
        lines = [head,
                 "# As the first player in the battle, from the %s callback. Only a player standing in the slot their" % name,
                 "# run owns counts, tested with a positional selector in %s (dimension-safe)." % dim,
                 "scoreboard players operation #me %s = @s %s" % (W, ID)]
        for i in range(1, n + 1):
            lines.append("execute in %s as @a[%s] if score @s %s = #me %s if score @s %s = #s%d %s if score @s %s matches %d "
                         "run function %s" % (dim, _sel_box(slot_geometry(doc, i)["box"]), ID, W, ID, i, OWN, SLOT, i,
                                              _fn(doc, "slot/s%d/%s" % (i, target))))
        return lines
    out["fainted"] = from_callback("battle_fainted", "settle")
    out["caught"] = from_callback("pokemon_captured", "caught")

    out["place"] = [
        head,
        "# tools/reapply.py step R16Q. The rooms live in the world folder, so a re-export loses them (EXP-047",
        "# result 6); they are flat and deterministic, so this rebuilds them exactly. The dimension is cobblers_portals'",
        "# and registers only at a boot: a first install restarts before this runs.",
        "execute in %s run function %s" % (dim, _fn(doc, "rooms/build"))]
    out["rooms/build"] = ["# runs with %s as its execution dimension (place carries it in)." % dim] + [
        "function %s" % _fn(doc, "rooms/s%d" % i) for i in range(1, n + 1)]
    return out


def room_function(doc, i):
    g = slot_geometry(doc, i)
    t = doc["tags"]
    lines = ["# slot %d's room in %s. Called by rooms/build, which carries the dimension in." % (i, doc["pocket"]["dimension"])]
    lines += portals.commands(room_blocks(doc, i))
    lines += ["kill @e[type=minecraft:interaction,tag=%s_s%d]" % (t["exit"], i),
              portals.summon(g["click"], t["exit"], "%s_s%d" % (t["exit"], i), 3.0, 3.0)]
    return function_limits.ensure_loaded(lines)


def callbacks(doc):
    """The two MoLang callbacks. No apostrophe inside a comment string: MoLang strings are single-quoted."""
    sp = doc["species"]["id"]
    return {
        # tools/gulch_mine.py callback_files: c.pokemon.actor.is_wild, c.pokemon.pokemon, c.players, .player.uuid
        CALLBACKS % "battle_fainted": "\n".join([
            "'Generated by tools/entei_boss.py from data/entei_boss.json. A wild Entei fainting in battle: the first';",
            "'player in the battle settles their slot run, if they stand in the slot their run owns.';",
            "c.pokemon.actor.is_wild ? {",
            "  t.pk = c.pokemon.pokemon;",
            "  t.pk.species.identifier == '%s' ? {" % sp,
            "    t.done = 0;",
            "    for_each(t.a, c.players, {",
            "      t.done == 0 ? {",
            "        q.run_command('execute as ' + t.a.player.uuid + ' at @s run function %s');" % _fn(doc, "fainted"),
            "        t.done = 1;",
            "      };",
            "    });",
            "  };",
            "};", ""]),
        # tools/hoopa_cradle.py callbacks: q.pokemon.species.identifier, q.player.uuid
        CALLBACKS % "pokemon_captured": "\n".join([
            "'Generated by tools/entei_boss.py from data/entei_boss.json. An Entei caught by a player standing in the';",
            "'slot their run owns: the catch that ends the catchable phase. An Entei caught anywhere else counts for nothing.';",
            "t.id = q.pokemon.species.identifier;",
            "t.id == '%s' ? {" % sp,
            "  q.run_command('execute as ' + q.player.uuid + ' at @s run function %s');" % _fn(doc, "caught"),
            "};", ""]),
    }


def impossible():
    return {"criteria": {"granted": {"trigger": "minecraft:impossible"}}, "requirements": [["granted"]]}


def build(doc, **kw):
    bad = problems(doc, **kw)
    if bad:
        raise EnteiError("data/entei_boss.json: " + "; ".join(bad))
    files = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Entei boss, one per player in cobblers:pocket (tools/entei_boss.py)"}},
                                  indent=2) + "\n",
        "data/minecraft/tags/function/load.json": json.dumps({"values": [_fn(doc, "load")]}, indent=2) + "\n",
    }
    adv_ns, adv_path = doc["catch"]["advancement"].split(":", 1)
    files["data/%s/advancement/%s.json" % (adv_ns, adv_path)] = json.dumps(impossible(), indent=2) + "\n"
    files["data/cobblers/advancement/%s.json" % SIGIL_ADV] = json.dumps(
        sigil_advancement(doc, _fn(doc, "enter")), indent=2) + "\n"
    files["data/cobblers/advancement/%s.json" % EXIT_ADV] = json.dumps(
        portals.click_advancement(doc["tags"]["exit"], _fn(doc, "leave")), indent=2) + "\n"
    rid_ns, rid_path = doc["key"]["recipe"]["id"].split(":", 1)
    files["data/%s/recipe/%s.json" % (rid_ns, rid_path)] = json.dumps(recipe(doc), indent=2) + "\n"
    lt_ns, lt_path = doc["drops"]["loot_table"].split(":", 1)
    files["data/%s/loot_table/%s.json" % (lt_ns, lt_path)] = json.dumps(loot_table(doc), indent=2) + "\n"
    fns = functions(doc, kw.get("blackout"))
    for i in range(1, doc["pocket"]["slots"] + 1):
        fns["rooms/s%d" % i] = room_function(doc, i)
    for name, lines in fns.items():
        rel = "data/cobblers/function/entei_boss/%s.mcfunction" % name
        refused = function_limits.check_lines(lines, rel)
        if refused:
            for ln, cmd, why in refused:
                print("REFUSED %s line %d: %s\n   %s" % (rel, ln, why, cmd))
            raise SystemExit("%s: %d command(s) the server would refuse; nothing written" % (rel, len(refused)))
        files[rel] = "\n".join(lines) + "\n"
    files.update(callbacks(doc))
    return files


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default=str(DATA))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    files = build(load(a.data))
    write(files, a.out)
    print("cobblers_entei_boss: %d files -> %s" % (len(files), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
