#!/usr/bin/env python
"""The dive and sky portals, and the pocket dimension they lead into, from data/portals.json.

Twelve portals: six under water, opened by the EXISTING `cobblers.dive` tag (granted by
`cobblers:water/grant_dive`, tools/blackout_pack.py), and six on summits east of x4000, opened by a NEW
`cobblers.sky` tag on the same tag-and-function pattern, granted once a player holds the
`cobblers:flag/gym4_cleared` advancement. The owner's content rule, verbatim: "1 in 6 meaningful, the rest a
chest or nothing" -- so each six is one `vault` and five small rooms.

THE RUNG (CLAUDE.md principle 6). Datapack plus functions/commands, and nothing above it:

  - Cobblemon native: no portal, no pocket space, no dimension feature. 1.8 adds party pools, party
    compositions, moveset builders and the Habitat Block; none of them moves a player.
  - a compatible addon / a Cobbleverse dependency: none of the pack's mods ships a portal to a custom
    dimension (base-pack/inventory).
  - configuration: there is no config key for a dimension or a portal in any of them.
  - datapack: a `dimension` and a `dimension_type` are plain datapack files, and EXP-047 proved one registers,
    loads with no new error, is writable and holds entities on this exact stack.
  - functions/commands: vanilla has no datapack-definable portal BLOCK, so the crossing itself is a command.
    It is a right-click on a `minecraft:interaction` entity, read by a
    `minecraft:player_interacted_with_entity` advancement whose reward runs the crossing function and then
    revokes itself -- the pattern tools/scenes_pack.py already uses for every clickable prop (EXP-034).

WHAT EXP-047 SETTLED AND THIS TOOL OBEYS

  - A selector with no positional constraint is NOT dimension-scoped: `execute in minecraft:overworld run kill
    @e[...]` destroyed an entity that was in the pocket dimension. So every selector here that must stay in one
    dimension carries a position (`execute in <dim> ... @a[x=..,dx=..]`), and the two global kills in the place
    functions are global ON PURPOSE, to clear a portal's own stale copies wherever they are.
  - Our per-tick systems reach the pocket dimension for free, blackout and the water ladder among them.
  - A pocket dimension's contents do NOT survive a re-export (they live inside the world folder), so every room
    is rebuilt by the re-application step; the rooms are flat and deterministic, so that is exact and cheap.
  - The crossing is a right-click, so the player is already dismounted: ADR-004's recall-on-crossing has nothing
    to recall and the water-fatigue collision cannot arise.

GROUND comes from tools/ground.py (the canonical heightmap, rounded), never from a world. A dive portal's
apron sits on the lake floor and the whole arch must stand under the body's authored `level_y`; a sky portal's
apron sits on its summit. A column lower than the apron is filled up to it with the apron block.

  python tools/portals.py build [--source-root <root>]   # -> build/datapacks/cobblers_portals
  python tools/portals.py report [--source-root <root>]  # every site's geometry and clearances; writes nothing

tools/portals_audit.py checks the written pack independently: it replays the functions into a voxel model and
holds it against its own reading of data/portals.json, the heightmap, the lake levels, the towns, the
placements and the legendary mouths. It is run by `prepare` and fails it.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402

DATA = ROOT / "data" / "portals.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_portals"
REPORT = ROOT / "derived" / "portals"
NS = "cobblers"
SCHEMA = "cobblers.portals/1"
PACK_FORMAT = 48  # Minecraft 1.21.1

# the compass direction a portal faces -> (forward dx, forward dz) and the player yaw that looks that way
FACINGS = {"north": ((0, -1), 180.0), "east": ((1, 0), -90.0), "south": ((0, 1), 0.0), "west": ((-1, 0), 90.0)}


class PortalError(ValueError):
    pass


# ----------------------------------------------------------------------------------------------- reading


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise PortalError("%s: schema must be %s" % (path, SCHEMA))
    seen, per_gate = set(), {}
    for p in doc.get("portals") or []:
        pid = p.get("id")
        if not isinstance(pid, str) or not pid.replace("_", "").isalnum() or pid != pid.lower():
            raise PortalError("portal id %r is not a lowercase [a-z0-9_] id" % (pid,))
        if pid in seen:
            raise PortalError("portal %r is declared twice" % pid)
        seen.add(pid)
        for k in ("name", "gate", "room", "meaningful", "at", "facing", "why", "story"):
            if k not in p:
                raise PortalError("portal %s: missing %r" % (pid, k))
        if p["story"] != "for Codex":
            raise PortalError("portal %s: its story is Codex's to write: \"story\": \"for Codex\"" % pid)
        if p["gate"] not in doc["gates"]:
            raise PortalError("portal %s: gate %r is not one of %s" % (pid, p["gate"], sorted(doc["gates"])))
        if p["room"] not in doc["rooms"]:
            raise PortalError("portal %s: room %r is not one of %s" % (pid, p["room"], sorted(doc["rooms"])))
        if p["facing"] not in FACINGS:
            raise PortalError("portal %s: facing %r is not a cardinal direction" % (pid, p["facing"]))
        if not (isinstance(p["at"], list) and len(p["at"]) == 2 and all(isinstance(v, int) for v in p["at"])):
            raise PortalError("portal %s: at must be [x, z] integers" % pid)
        if (p["room"] == "vault") != bool(p["meaningful"]):
            raise PortalError("portal %s: the meaningful one is the vault and the vault is the meaningful one" % pid)
        if bool(p.get("loot")) != bool(doc["rooms"][p["room"]]["chest"] or doc["rooms"][p["room"]]["pedestal"]):
            raise PortalError("portal %s: a %s room %s a loot table"
                              % (pid, p["room"], "needs" if p["room"] != "cell" else "must not have"))
        if p.get("loot") and p["loot"] not in doc["loot"]["tables"]:
            raise PortalError("portal %s: loot %r is not in loot.tables" % (pid, p["loot"]))
        if p["gate"] == "dive" and not p.get("water_body"):
            raise PortalError("portal %s: a dive portal names the water_body it stands in" % pid)
        per_gate.setdefault(p["gate"], []).append(p)
    if not per_gate:
        raise PortalError("data/portals.json lists no portal")
    n = doc["rules"]["meaningful_per"]
    for gate, group in sorted(per_gate.items()):
        if len(group) % n:
            raise PortalError("gate %s has %d portals: the owner's rule counts in %ds" % (gate, len(group), n))
        want, got = len(group) // n, sum(1 for p in group if p["meaningful"])
        if got != want:
            raise PortalError("gate %s: %d of %d meaningful, the rule is one in %d (%d)"
                              % (gate, got, len(group), n, want))
    return doc


def water_bodies(path=None):
    """{landmark id: (level_y, [polygons])} for every annotated body of water that has an authored level."""
    doc = json.loads((path or ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
    out = {}
    for l in doc["landmarks"]:
        lev = (l.get("water_body") or {}).get("level_y")
        polys = (l.get("extent") or {}).get("polygons") or []
        if lev is not None and polys:
            out[l["id"]] = (int(lev), polys)
    return out


def in_polygon(poly, x, z):
    n, c, j = len(poly), False, len(poly) - 1
    for i in range(n):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / float(zj - zi) + xi):
            c = not c
        j = i
    return c


# ------------------------------------------------------------------------------------------- the geometry
# A portal is a 5 by 5 apron with a 5-wide arch on it: two jambs, a 3 by 3 sheet, a lintel and two lamps.
# Local coordinates are (r, dy) with r along the arch (right of the facing) and dy above the apron.

ARCH_HEIGHT = 4          # the lintel/lamp course, apron + 4
APRON_HALF = 2
RESCUE_TICKS = 20        # the rescue sweep: it has to catch a falling player before the bedrock plane does
GATE_TICKS = 100         # the sky-tag sweep: nobody minds waiting five seconds for a tag


def unit(facing):
    (fx, fz), yaw = FACINGS[facing]
    return (fx, fz), (-fz, fx), yaw


def apron_columns(x, z):
    return [(x + dx, z + dz) for dx in range(-APRON_HALF, APRON_HALF + 1)
            for dz in range(-APRON_HALF, APRON_HALF + 1)]


def world_blocks(spec, doc, ground):
    """[(x, y, z, block)] for one portal's world side, plus the apron y and the two points it defines."""
    pal = doc["blocks"][spec["gate"]]
    x, z = spec["at"]
    (fx, fz), (rx, rz), yaw = unit(spec["facing"])
    cols = apron_columns(x, z)
    g = {c: ground(*c) for c in cols}
    relief = max(g.values()) - min(g.values())
    if relief > doc["rules"]["max_relief"]:
        raise PortalError("%s: the ground under its apron varies by %d blocks (the rule allows %d): move it"
                          % (spec["id"], relief, doc["rules"]["max_relief"]))
    ay = max(g.values())
    out = []
    for c in cols:                                        # the apron, and a footing under a lower column
        for y in range(g[c] + 1, ay):
            out.append((c[0], y, c[1], pal["apron"]))
        out.append((c[0], ay, c[1], pal["apron"]))
    def at(r, dy):
        return (x + rx * r, ay + dy, z + rz * r)
    for r in (-2, 2):                                     # the jambs
        for dy in (1, 2, 3):
            out.append(at(r, dy) + (pal["frame"],))
    for r in (-1, 0, 1):                                  # the sheet
        for dy in (1, 2, 3):
            out.append(at(r, dy) + (pal["sheet"],))
    for r in (-1, 0, 1):                                  # the lintel
        out.append(at(r, ARCH_HEIGHT) + (pal["frame"],))
    for r in (-2, 2):                                     # a lamp on each end of the lintel
        out.append(at(r, ARCH_HEIGHT) + (pal["lamp"],))
    click = (x + fx, ay + 1, z + fz)                      # the block the interaction entity fills
    stand = (x + 2 * fx, ay + 1, z + 2 * fz)              # where a returning player is put down
    return out, ay, click, stand, yaw


def room_centre(doc, spec, index):
    p = doc["pocket"]
    return p["origin_x"] + index * p["spacing"], p["bands"][spec["gate"]]


def room_blocks(doc, spec, cx, cz):
    """[(x, y, z, block)] for one room in the pocket dimension, its arrival point and its click block.

    A dive room is a sealed shell; a sky room is an open platform with a parapet two courses high, so it reads
    as an island under the dimension's own sky. Both carry the same arch back."""
    kind = doc["rooms"][spec["room"]]
    pal = doc["blocks"][spec["gate"]]
    half, height, fy = kind["half"], kind["height"], doc["pocket"]["floor_y"]
    out = []
    if spec["gate"] == "dive":
        for x in range(cx - half - 1, cx + half + 2):     # a sealed box: shell solid, interior air
            for y in range(fy - 1, fy + height + 1):
                for z in range(cz - half - 1, cz + half + 2):
                    edge = (x in (cx - half - 1, cx + half + 1) or z in (cz - half - 1, cz + half + 1)
                            or y in (fy - 1, fy + height))
                    out.append((x, y, z, pal["shell"] if edge else "minecraft:air"))
        for dx in (-half + 1, half - 1):                  # four lights in the ceiling
            for dz in (-half + 1, half - 1):
                out.append((cx + dx, fy + height - 1, cz + dz, pal["light"]))
    else:
        for x in range(cx - half - 1, cx + half + 2):     # the platform
            for z in range(cz - half - 1, cz + half + 2):
                out.append((x, fy - 1, z, pal["floor"]))
        for x in range(cx - half - 1, cx + half + 2):     # a parapet two courses high all round
            for z in range(cz - half - 1, cz + half + 2):
                if x in (cx - half - 1, cx + half + 1) or z in (cz - half - 1, cz + half + 1):
                    for dy in (0, 1):
                        out.append((x, fy + dy, z, pal["shell"]))
        for dx in (-half - 1, half + 1):                  # a lantern on each corner of the parapet
            for dz in (-half - 1, half + 1):
                out.append((cx + dx, fy + 2, cz + dz, "minecraft:lantern[hanging=false]"))
    az = cz - half                                        # the arch back, against the low-z side
    for r in (-2, 2):
        for dy in (0, 1, 2):
            out.append((cx + r, fy + dy, az, pal["frame"]))
    for r in (-1, 0, 1):
        for dy in (0, 1, 2):
            out.append((cx + r, fy + dy, az, pal["sheet"]))
    for r in (-2, -1, 0, 1, 2):
        out.append((cx + r, fy + 3, az, pal["frame"]))
    click = (cx, fy, az + 1)                              # the return interaction, one block in front
    arrive = (cx, fy, az + 3)                             # where a crossing player is put down
    if kind["chest"]:
        out.append((cx, fy, cz + half, "minecraft:chest[facing=north]"))
    if kind["pedestal"]:
        out.append((cx, fy, cz + half - 1, pal["pedestal"]))
        out.append((cx, fy + 1, cz + half - 1, pal["light"]))
    return out, arrive, click


# ------------------------------------------------------------------------------------------- the commands


def runs(cells):
    """[(x0, x1, y, z)] runs of equal y and z along x, for the fills."""
    out, cur = [], None
    for x, y, z in sorted(cells, key=lambda c: (c[1], c[2], c[0])):
        if cur and cur[2] == y and cur[3] == z and x == cur[1] + 1:
            cur[1] = x
            continue
        cur = [x, x, y, z]
        out.append(cur)
    return [tuple(c) for c in out]


def commands(blocks):
    """fills where a block repeats along x, setblocks otherwise. Later entries win, as in a world."""
    last = {}
    for x, y, z, b in blocks:
        last[(x, y, z)] = b
    by_block = {}
    for (x, y, z), b in last.items():
        by_block.setdefault(b, []).append((x, y, z))
    out = []
    for b in sorted(by_block):
        for x0, x1, y, z in runs(by_block[b]):
            if x1 > x0:
                out.append(("fill %d %d %d %d %d %d %s" % (x0, y, z, x1, y, z, b), y, x0))
            else:
                out.append(("setblock %d %d %d %s" % (x0, y, z, b), y, x0))
    # lowest first, so a course never lands on air that a later course fills
    return [c for c, _y, _x in sorted(out, key=lambda c: (c[1], c[2], c[0]))]


def summon(pos, tag_all, tag_one, width, height):
    x, y, z = pos
    return ('summon minecraft:interaction %.1f %d %.1f {width:%.1ff,height:%.1ff,response:1b,Tags:["%s","%s"]}'
            % (x + 0.5, y, z + 0.5, width, height, tag_all, tag_one))


def text(msg, colour):
    return json.dumps({"text": msg, "color": colour})


def click_advancement(tag, fn):
    """The proven click trigger (tools/scenes_pack.py, EXP-034): a right-click on one tagged interaction."""
    return {"criteria": {"click": {"trigger": "minecraft:player_interacted_with_entity", "conditions": {
                "entity": [{"condition": "minecraft:entity_properties", "entity": "this",
                            "predicate": {"type": "minecraft:interaction", "nbt": '{Tags:["%s"]}' % tag}}]}}},
            "rewards": {"function": fn}}


def loot_table(items):
    return {"pools": [{"rolls": 1, "entries": [{"type": "minecraft:item", "name": i["item"], "functions": [
                {"function": "minecraft:set_count", "count": i["count"]}]}]} for i in items]}


# ------------------------------------------------------------------------------------------------- checks


def clearances(doc, sites):
    """[(portal id, problem)] for every clearance rule in data/portals.json rules."""
    r = doc["rules"]
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    places = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
    legend = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))["encounters"]
    mouths = [(e["id"], e["mouth"]) for e in legend if e.get("mouth")]
    bad = []
    for pid, s in sites.items():
        x, z = s["at"]
        gate = s["gate"]
        if gate == "sky" and x < r["sky_min_x"]:
            bad.append((pid, "a sky portal at x%d is west of the x%d line" % (x, r["sky_min_x"])))
        for t in towns:
            fp = t.get("footprint") or {}
            if not fp:
                continue
            d = math.hypot(max(fp["min_x"] - x, 0, x - fp["max_x"]), max(fp["min_z"] - z, 0, z - fp["max_z"]))
            if d < r["min_from_town_footprint"][gate]:
                bad.append((pid, "%.0f from %s's footprint (min %d)" % (d, t["id"], r["min_from_town_footprint"][gate])))
        for q in places:
            pos = q.get("position") or {}
            if "x" not in pos:
                continue
            d = math.hypot(pos["x"] - x, pos["z"] - z)
            if d < r["min_from_placement"][gate]:
                bad.append((pid, "%.0f from the placement %s (min %d)" % (d, q["id"], r["min_from_placement"][gate])))
        for lid, m in mouths:
            d = math.hypot(m[0] - x, m[1] - z)
            if d < r["min_from_legendary_mouth"]:
                bad.append((pid, "%.0f from %s's mouth (min %d)" % (d, lid, r["min_from_legendary_mouth"])))
        for qid, q in sites.items():
            if qid <= pid:
                continue
            d = math.hypot(q["at"][0] - x, q["at"][1] - z)
            if d < r["min_between_portals"]:
                bad.append((pid, "%.0f from %s (min %d)" % (d, qid, r["min_between_portals"])))
    return bad


def water_check(doc, spec, site, bodies):
    """[problem] for a dive portal that is not properly drowned."""
    body = spec["water_body"]
    if body not in bodies:
        return ["%s: no water body %r with an authored level_y in data/landmarks.json" % (spec["id"], body)]
    level, polys = bodies[body]
    out = []
    x, z = spec["at"]
    if not any(in_polygon(p, x, z) for p in polys):
        out.append("%s: (%d, %d) is outside %s's outline" % (spec["id"], x, z, body))
    top = site["apron_y"] + ARCH_HEIGHT
    if top > level - doc["rules"]["min_water_above"]:
        out.append("%s: its lintel tops out at y%d, %d under %s's level y%d (min %d)"
                   % (spec["id"], top, level - top, body, level, doc["rules"]["min_water_above"]))
    for c, gy in site["ground"].items():
        if gy > level - doc["rules"]["min_submersion"]:
            out.append("%s: the apron column %s is at y%d, %d under %s's level y%d (min %d)"
                       % (spec["id"], c, gy, level - gy, body, level, doc["rules"]["min_submersion"]))
            break
    site["level_y"] = level
    return out


# -------------------------------------------------------------------------------------------- the emitter


def sites(doc, ground):
    """{portal id: everything the emitter and the report need}, fail-closed on any rule."""
    out, problems, bodies = {}, [], water_bodies()
    for i, spec in enumerate(doc["portals"]):
        blocks, ay, click, stand, yaw = world_blocks(spec, doc, ground)
        cx, cz = room_centre(doc, spec, i % (len(doc["portals"]) // len(doc["gates"])))
        rb, arrive, rclick = room_blocks(doc, spec, cx, cz)
        s = {"id": spec["id"], "gate": spec["gate"], "room": spec["room"], "at": spec["at"],
             "facing": spec["facing"], "meaningful": spec["meaningful"], "index": i + 1,
             "apron_y": ay, "ground": {c: ground(*c) for c in apron_columns(*spec["at"])},
             "world_blocks": blocks, "click": click, "stand": stand, "yaw": yaw,
             "room_centre": [cx, cz], "room_blocks": rb, "arrive": arrive, "room_click": rclick,
             "loot": spec.get("loot")}
        if spec["gate"] == "dive":
            problems += water_check(doc, spec, s, bodies)
        out[spec["id"]] = s
    problems += ["%s: %s" % (pid, why) for pid, why in clearances(doc, out)]
    if problems:
        raise PortalError("data/portals.json: " + "; ".join(problems))
    return out


def files(doc, S):
    """{path in the pack: text}."""
    out, fn = {}, {}
    p = doc["pocket"]
    dim, half_ns = p["dimension"], p["dimension"].split(":")[1]
    gen = p["generator"]
    out["data/%s/dimension_type/%s.json" % (NS, half_ns)] = json.dumps({
        "ultrawarm": False, "natural": True, "piglin_safe": True, "respawn_anchor_works": False,
        "bed_works": False, "has_raids": False, "has_skylight": gen["has_skylight"], "has_ceiling": False,
        "coordinate_scale": 1.0, "ambient_light": 0.0, "logical_height": gen["height"],
        "effects": "minecraft:overworld", "infiniburn": "#minecraft:infiniburn_overworld",
        "min_y": gen["min_y"], "height": gen["height"], "monster_spawn_light_level": 0,
        "monster_spawn_block_light_limit": 0, "fixed_time": gen["fixed_time"]}, indent=2) + "\n"
    out["data/%s/dimension/%s.json" % (NS, half_ns)] = json.dumps({
        "type": p["dimension_type"],
        "generator": {"type": "minecraft:flat", "settings": {
            "biome": gen["biome"], "lakes": False, "features": False,
            "layers": gen["layers"], "structure_overrides": []}}}, indent=2) + "\n"

    # ---- the gate, the sweep and the rescue ------------------------------------------------------------
    sky = doc["gates"]["sky"]
    fn["portals/load"] = ["# Generated by tools/portals.py from data/portals.json. Re-run to rebuild.",
                          "scoreboard objectives add cobblers.portal dummy",
                          "schedule function %s:portals/tick %dt replace" % (NS, RESCUE_TICKS),
                          "schedule function %s:portals/gate %dt replace" % (NS, GATE_TICKS)]
    fn["portals/grant_sky"] = [
        "# the sky gate, on the pattern of cobblers:water/grant_dive (tools/blackout_pack.py): a tag on the",
        "# player, granted once by a function. Nothing revokes it.",
        "tag @s add %s" % sky["tag"],
        "tellraw @s %s" % text(sky["granted_message"], "aqua")]
    lo = [min(s["room_centre"][0] for s in S.values()) - p["rescue_margin"], gen["min_y"],
          min(s["room_centre"][1] for s in S.values()) - p["rescue_margin"]]
    hi = [max(s["room_centre"][0] for s in S.values()) + p["rescue_margin"], p["floor_y"] - 2,
          max(s["room_centre"][1] for s in S.values()) + p["rescue_margin"]]
    fn["portals/gate"] = [
        "# the sky gate, swept every %d ticks. A per-player selector, so it needs no dimension constraint;" % GATE_TICKS,
        "# it is retroactive (a player who cleared gym 4 before this pack existed is tagged on the next sweep)",
        "# and it reaches a late joiner the moment they clear gym 4.",
        "execute as @a[advancements={%s=true},tag=!%s] run function %s:portals/grant_sky"
        % (sky["advancement"], sky["tag"], NS),
        "schedule function %s:portals/gate %dt replace" % (NS, GATE_TICKS)]
    fn["portals/tick"] = [
        "# the rescue, every %d ticks. EXP-047 proved a selector with no positional constraint is NOT" % RESCUE_TICKS,
        "# dimension-scoped here, so this one carries an absolute box and `execute in` names the dimension.",
        "# Anybody in the pocket dimension below the room floors has fallen out of a room, or logged in where a",
        "# room no longer stands (a re-export wipes the dimension's blocks): put them back where they came in.",
        "# %dt, not longer: the drop from a room's floor to the bedrock plane is %d blocks and a fall that far" % (
            RESCUE_TICKS, p["floor_y"] - gen["min_y"]),
        "# kills, so the sweep has to catch them on the way down.",
        "execute in %s as @a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d] run function %s:portals/rescue"
        % (dim, lo[0], lo[1], lo[2], hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], NS),
        "schedule function %s:portals/tick %dt replace" % (NS, RESCUE_TICKS)]
    order = sorted(S.values(), key=lambda s: s["index"])
    rescue = ["# runs as a stranded player. cobblers.portal is the portal they last crossed; each leave function",
              "# puts them back at its own world-side arch, so no per-player coordinate is ever stored."]
    for s in order:
        rescue.append("execute if score @s cobblers.portal matches %d run function %s:portals/leave/%s"
                      % (s["index"], NS, s["id"]))
    fallback = next(s for s in order if s["gate"] == "sky")
    rescue += ["# never crossed a portal and yet is in there: put them on dry land at %s" % fallback["id"],
               "execute unless score @s cobblers.portal matches 1.. run function %s:portals/leave/%s"
               % (NS, fallback["id"])]
    fn["portals/rescue"] = rescue
    fn["portals/place"] = [
        "# the world-side arches are their own functions (tools/reapply.py step R16P); this builds the rooms.",
        "# `execute in` carries the dimension into the function, so every command inside it -- the forceloads",
        "# included -- acts in the pocket dimension.",
        "execute in %s run function %s:portals/pocket/build" % (dim, NS)]
    fn["portals/pocket/build"] = ["# runs with the pocket dimension as its execution dimension."] + \
        ["function %s:portals/pocket/%s" % (NS, s["id"]) for s in order]

    # ---- one world function, one room function, one crossing and one return for each portal ------------
    for s in order:
        gate = doc["gates"][s["gate"]]
        cols = apron_columns(*s["at"])
        ys = [b[1] for b in s["world_blocks"]]
        world = ["# %s (%s): the world side of the arch." % (s["id"], s["gate"])]
        if s["gate"] == "sky":
            for x0, x1, y, z in runs([(c[0], 0, c[1]) for c in cols]):
                world.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:replaceable"
                             % (x0, s["apron_y"] + 1, z, x1, max(ys) + 2, z))
                for tag in ("#minecraft:logs", "#minecraft:leaves"):
                    world.append("fill %d %d %d %d %d %d minecraft:air replace %s"
                                 % (x0, s["apron_y"] + 1, z, x1, max(ys) + 3, z, tag))
        world += commands(s["world_blocks"])
        world += ["# the click box, one block in front of the sheet. The kill is global on purpose: a stale copy",
                  "# of THIS portal is to be removed wherever it is, the pocket dimension included (EXP-047).",
                  "kill @e[type=minecraft:interaction,tag=cobblers_portal_%s]" % s["id"],
                  summon(s["click"], "cobblers_portal", "cobblers_portal_%s" % s["id"], 3.0, 3.0)]
        out["data/%s/function/portals/world/%s.mcfunction" % (NS, s["id"])] = \
            "\n".join(function_limits.ensure_loaded(world)) + "\n"

        room = ["# %s: its room in %s. Called by portals/pocket/build, which carries the dimension in." % (s["id"], dim)]
        room += commands(s["room_blocks"])
        room += ["kill @e[type=minecraft:interaction,tag=cobblers_return_%s]" % s["id"],
                 summon(s["room_click"], "cobblers_return", "cobblers_return_%s" % s["id"], 3.0, 3.0)]
        if doc["rooms"][s["room"]]["pedestal"]:
            cx, cz = s["room_centre"]
            ped = (cx, p["floor_y"] + 1, cz + doc["rooms"][s["room"]]["half"] - 1)
            room += ["kill @e[type=minecraft:interaction,tag=cobblers_claim_%s]" % s["id"],
                     summon(ped, "cobblers_claim", "cobblers_claim_%s" % s["id"], 1.6, 1.6)]
        out["data/%s/function/portals/pocket/%s.mcfunction" % (NS, s["id"])] = \
            "\n".join(function_limits.ensure_loaded(room)) + "\n"

        ax, ay, az = s["arrive"]
        out["data/%s/function/portals/enter/%s.mcfunction" % (NS, s["id"])] = "\n".join([
            "# the crossing, as the player who clicked. The advancement is re-armed first, so it fires again.",
            "advancement revoke @s only %s:portals/enter/%s" % (NS, s["id"]),
            "execute as @e[type=minecraft:interaction,tag=cobblers_portal_%s,distance=..8] run data remove entity @s interaction"
            % s["id"],
            "execute unless entity @s[tag=%s] run tellraw @s %s" % (gate["tag"], text(gate["locked_message"], "gray")),
            "execute unless entity @s[tag=%s] run return 0" % gate["tag"],
            "scoreboard players set @s cobblers.portal %d" % s["index"],
            "execute in %s run tp @s %.1f %d %.1f 0 0" % (dim, ax + 0.5, ay, az + 0.5)]) + "\n"
        sx, sy, sz = s["stand"]
        out["data/%s/function/portals/leave/%s.mcfunction" % (NS, s["id"])] = "\n".join([
            "# the way back, never gated: whatever else is true, a player can always leave.",
            "advancement revoke @s only %s:portals/leave/%s" % (NS, s["id"]),
            "execute as @e[type=minecraft:interaction,tag=cobblers_return_%s,distance=..8] run data remove entity @s interaction"
            % s["id"],
            "execute in minecraft:overworld run tp @s %.1f %d %.1f %.1f 0"
            % (sx + 0.5, sy, sz + 0.5, s["yaw"])]) + "\n"
        out["data/%s/advancement/portals/enter/%s.json" % (NS, s["id"])] = json.dumps(
            click_advancement("cobblers_portal_%s" % s["id"], "%s:portals/enter/%s" % (NS, s["id"])), indent=2) + "\n"
        out["data/%s/advancement/portals/leave/%s.json" % (NS, s["id"])] = json.dumps(
            click_advancement("cobblers_return_%s" % s["id"], "%s:portals/leave/%s" % (NS, s["id"])), indent=2) + "\n"

        if s["loot"] and doc["rooms"][s["room"]]["chest"]:
            out["data/%s/loot_table/portals/%s.json" % (NS, s["id"])] = \
                json.dumps(loot_table(doc["loot"]["tables"][s["loot"]]), indent=2) + "\n"
        if s["loot"] and doc["rooms"][s["room"]]["pedestal"]:
            out["data/%s/loot_table/portals/%s.json" % (NS, s["id"])] = \
                json.dumps(loot_table(doc["loot"]["tables"][s["loot"]]), indent=2) + "\n"
            out["data/%s/function/portals/claim/%s.mcfunction" % (NS, s["id"])] = "\n".join([
                "# ONCE PER PLAYER: the advancement is never revoked, so a second click does nothing. That is what",
                "# makes the meaningful room work for a party -- a chest would go to whoever opened it first.",
                "execute as @e[type=minecraft:interaction,tag=cobblers_claim_%s,distance=..8] run data remove entity @s interaction"
                % s["id"],
                "loot give @s loot %s:portals/%s" % (NS, s["id"]),
                "tellraw @s %s" % text("You take what was left here for you.", "gold")]) + "\n"
            out["data/%s/advancement/portals/claim/%s.json" % (NS, s["id"])] = json.dumps(
                click_advancement("cobblers_claim_%s" % s["id"], "%s:portals/claim/%s" % (NS, s["id"])), indent=2) + "\n"

    for name, lines in fn.items():
        out["data/%s/function/%s.mcfunction" % (NS, name)] = "\n".join(lines) + "\n"
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:portals/load" % NS]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                     "Cobblers: dive and sky portals, and the pocket dimension (tools/portals.py)"}},
                                    indent=2) + "\n"
    return out


def chest_data(doc, S):
    """The chests carry their loot table, so a re-applied room refills. Folded into the room functions."""
    for s in S.values():
        if s["loot"] and doc["rooms"][s["room"]]["chest"]:
            yield s


def build(a):
    import ground as G
    doc = load()
    g = G.Ground(a.source_root)
    S = sites(doc, g)
    # the chest carries its loot table: rewrite the plain chest block now that the table's name is known
    for s in S.values():
        if doc["rooms"][s["room"]]["chest"]:
            s["room_blocks"] = [(x, y, z, b if b != "minecraft:chest[facing=north]" else
                                 'minecraft:chest[facing=north]{LootTable:"%s:portals/%s"}' % (NS, s["id"]))
                                for x, y, z, b in s["room_blocks"]]
    out = files(doc, S)
    for path, body in sorted(out.items()):
        if path.endswith(".mcfunction"):
            refused = function_limits.check_lines(body.splitlines(), path)
            if refused:
                raise PortalError("%s: %d command(s) the server would refuse: %s" % (path, len(refused), refused[:3]))
    if PACK.exists():
        shutil.rmtree(PACK)
    for path, body in sorted(out.items()):
        f = PACK / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    REPORT.mkdir(parents=True, exist_ok=True)
    rec = {"portals": [{"id": s["id"], "gate": s["gate"], "room": s["room"], "meaningful": s["meaningful"],
                        "index": s["index"], "at": s["at"], "facing": s["facing"], "apron_y": s["apron_y"],
                        "level_y": s.get("level_y"), "click": list(s["click"]), "stand": list(s["stand"]),
                        "room_centre": s["room_centre"], "arrive": list(s["arrive"]),
                        "world_blocks": len(s["world_blocks"]), "room_blocks": len(s["room_blocks"])}
                       for s in sorted(S.values(), key=lambda q: q["index"])]}
    (REPORT / "report.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    for s in rec["portals"]:
        print("%-26s %-4s %-5s at %5d %5d apron y%-3d  room %5d %4d  %4d + %4d blocks%s"
              % (s["id"], s["gate"], s["room"], s["at"][0], s["at"][1], s["apron_y"], s["room_centre"][0],
                 s["room_centre"][1], s["world_blocks"], s["room_blocks"], "  MEANINGFUL" if s["meaningful"] else ""))
    print("wrote", PACK)
    return 0


def report(a):
    import ground as G
    doc = load()
    S = sites(doc, G.Ground(a.source_root))
    for s in sorted(S.values(), key=lambda q: q["index"]):
        print("%-26s %-4s %-5s at %5d %5d facing %-5s apron y%-3d level %s  click %s  stand %s  room %s arrive %s"
              % (s["id"], s["gate"], s["room"], s["at"][0], s["at"][1], s["facing"], s["apron_y"],
                 s.get("level_y", "-"), s["click"], s["stand"], s["room_centre"], s["arrive"]))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("build", "report"):
        q = sub.add_parser(name)
        q.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    a = p.parse_args(argv)
    return {"build": build, "report": report}[a.cmd](a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
