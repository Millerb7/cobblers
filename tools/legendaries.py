#!/usr/bin/env python
"""The authored legendary encounters and their chambers, from data/legendaries.json.

Ten encounters: the lake trio in air-chambered grottos (Mesprit, Azelf, Uxie), the four bespoke concepts
(the three Regis as one puzzle, Regigigas, Groudon, Lugia) and the wake of the sleeping Celebi. Only the
records whose `status` is "sited" are emitted; everything else is data with a named blocker, and this tool
refuses to write a block for it. That is the fail-closed half: a chamber that cannot be sited offline
cannot reach a world by accident.

WHAT A FUNCTION CAN AND CANNOT DO HERE
  - A Pokemon is summoned over RCON by tools/reapply.py (step R14L). `spawnpokemonat` inside a datapack
    function spawns nothing until a /reload (EXP-046 question 1), so the pack never spawns one. Same
    pattern as tools/sapling_celebi.py.
  - Cobblemon ignores Invulnerable and a sword killed the sleeping Celebi in three hits (EXP-023), so a
    dormant legendary is protected by BLOCKS, not by a flag: a barrier partition in a grotto, a stone plug
    in a sealed chamber. Once the gate opens the legendary is as killable as any placed Pokemon; that is a
    recorded open question in the data, not something this tool solves.
  - Ground comes from tools/ground.py (the canonical heightmap, rounded), never from a world.

THE CHAMBER, PARAMETRIC BY DESIGN
  A stone envelope is filled SOLID first and extends shell_margin beyond every carved block in all six
  directions; the void is then cut out of it. So "at least 4 blocks of rock round every void, no void
  connecting to the water but the passage" (WATER_BUILD_PLAN 4.5 audit 1) holds by construction and can be
  proved by arithmetic instead of by a dilation over a world.

    lake_grotto     mouth in the lake bed -> flooded shaft -> flooded passage -> a pool cut into the
                    chamber floor -> the air chamber, dry above the pool's surface -> a barrier partition
                    -> the alcove the legendary stands in. The mouth is open at every stage: the trio are
                    shown to everyone and only answer to a badge (WATER_BUILD_PLAN 4.2).
    sealed_chamber  a stone plug at the surface -> a dry ladder shaft -> a short adit -> the chamber. The
                    plug IS the gate and it never closes again, so nobody is sealed in.

  python tools/legendaries.py                     # -> build/datapacks/cobblers_legendaries
  python tools/legendaries.py --report            # the geometry of every record, nothing written
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data" / "legendaries.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_legendaries"
SCHEMA = "cobblers.legendaries/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
FILL_LIMIT = 32768

KINDS = ("lake_grotto", "sealed_chamber", "sapling_wake")
STATUSES = ("sited", "blocked", "gate_only")

# bearing -> (dx, dz). Cardinals only: every box stays axis aligned, so every write is a `fill`.
BEARINGS = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}

DORMANT = {"Unbattleable": "1b", "NoAI": "1b", "NoGravity": "1b", "PoseType": '"SLEEP"',
           "RecalculatePose": "0b", "HideLabel": "1b", "PersistenceRequired": "1b", "Silent": "1b"}
# Waking sets RecalculatePose back and lets Cobblemon choose the pose: PoseType is NOT set to another
# value, because EXP-023 proved only "SLEEP" and principle 7 forbids guessing the rest of the enum.
AWAKE = {"Unbattleable": "0b", "RecalculatePose": "1b", "HideLabel": "0b", "Silent": "0b"}


class LegendaryError(ValueError):
    pass


# ------------------------------------------------------------------ reading


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise LegendaryError("%s: schema must be %s" % (path, SCHEMA))
    seen = set()
    for r in doc.get("encounters") or []:
        rid = r.get("id")
        if not isinstance(rid, str) or not rid.replace("_", "").isalnum():
            raise LegendaryError("encounter id %r is not a valid id" % (rid,))
        if rid in seen:
            raise LegendaryError("encounter %r is declared twice" % rid)
        seen.add(rid)
        if r.get("kind") not in KINDS:
            raise LegendaryError("%s: kind must be one of %s" % (rid, ", ".join(KINDS)))
        if r.get("status") not in STATUSES:
            raise LegendaryError("%s: status must be one of %s" % (rid, ", ".join(STATUSES)))
        if r["status"] != "sited" and not (r.get("blocked_by") and r.get("blocked_why")):
            raise LegendaryError("%s: a record that is not sited names blocked_by and blocked_why" % rid)
        g = r.get("gate")
        if not isinstance(g, dict) or not isinstance(g.get("flags"), list) or not g["flags"]:
            raise LegendaryError("%s: gate.flags must be a non-empty list (no legendary is ungated)" % rid)
    if not seen:
        raise LegendaryError("%s: no encounters" % path)
    return doc


def emitted(doc):
    """The records this tool writes blocks and gate code for: sited only, never a blocked one."""
    return [r for r in doc["encounters"] if r["status"] == "sited"]


def gate_only(doc):
    """Records whose GATE is built but whose trigger is an open question: the wake of the Celebi. They get
    the badge check and the function that opens the shell, and nothing calls it, on purpose."""
    return [r for r in doc["encounters"] if r["status"] == "gate_only"]


# ------------------------------------------------------------------ geometry


def _anchor(rec):
    at = rec.get("mouth") if rec["kind"] == "lake_grotto" else rec.get("portal")
    if not (isinstance(at, list) and len(at) == 2):
        raise LegendaryError("%s: a sited record needs a [x, z] mouth (lake_grotto) or portal" % rec["id"])
    return int(at[0]), int(at[1])


def geometry(rec, doc, ground):
    """Every box of one sited chamber, as inclusive (x0, y0, z0, x1, y1, z1) tuples.

    Pure arithmetic on the record and the heightmap: no world is read, and the same function is what
    tools/legendaries_audit.py re-derives the plan from.
    """
    d = doc["defaults"]
    mx, mz = _anchor(rec)
    my = ground(mx, mz)
    bore = int(d["bore"])
    margin = int(d["shell_margin"])
    r = bore // 2
    ap, ch = rec["approach"], rec["chamber"]
    bearing = int(ap["bearing_deg"])
    if bearing not in BEARINGS:
        raise LegendaryError("%s: bearing_deg must be one of %s" % (rec["id"], sorted(BEARINGS)))
    dx, dz = BEARINGS[bearing]
    px, pz = -dz, dx  # the perpendicular
    lake = rec["kind"] == "lake_grotto"
    pool_depth = int(d["pool_depth"]) if lake else 0
    width, length, height = int(ch["width"]), int(ch["length"]), int(ch["height"])
    alcove = int(ch.get("alcove") or 0)
    if width % 2 == 0 or length % 2 == 0 or bore % 2 == 0:
        raise LegendaryError("%s: width, length and bore must be odd (they centre on the axis)" % rec["id"])
    if lake and pool_depth <= bore - 1:
        raise LegendaryError("%s: pool_depth must exceed bore - 1 or the passage meets the pool above its surface" % rec["id"])
    if alcove >= length:
        raise LegendaryError("%s: the alcove must be shorter than the chamber" % rec["id"])

    floor_y = my - int(ap["drop"])
    corr_y0 = floor_y - pool_depth if lake else floor_y + 1
    corr_y1 = corr_y0 + bore - 1
    passage = int(ap["passage"])

    def at(s, p, y0, y1):
        """A box s blocks along the axis and p blocks across it, from the anchor column."""
        return _box(mx + dx * s[0] + px * p[0], y0, mz + dz * s[0] + pz * p[0],
                    mx + dx * s[1] + px * p[1], y1, mz + dz * s[1] + pz * p[1])

    w2, cs0 = width // 2, r + passage + 1
    cs1 = cs0 + length - 1
    g = {}
    g["floor_y"], g["ceiling_y"], g["corr_y0"], g["mouth_y"] = floor_y, floor_y + height, corr_y0, my
    g["anchor"] = (mx, mz)
    g["axis"] = (dx, dz)
    # the chamber's walkable interior, the whole of it including the alcove
    g["chamber"] = at((cs0, cs1), (-w2, w2), floor_y + 1, floor_y + height)
    # the passage, and the shaft up to the bed (a grotto) or up to the plug (a sealed chamber)
    g["passage"] = at((r + 1, r + passage), (-r, r), corr_y0, corr_y1)
    plug_depth = int(rec.get("plug_depth") or 0)
    shaft_top = my if lake else my - plug_depth
    g["shaft"] = at((-r, r), (-r, r), corr_y0, shaft_top)
    if not lake:
        g["plug"] = at((-r, r), (-r, r), my - plug_depth + 1, my)
        # the ladder hugs the shaft wall behind the climber, so it faces along the axis, toward the adit
        g["ladder"] = at((-r, -r), (0, 0), corr_y0, shaft_top)
        g["ladder_facing"] = {(0, -1): "north", (1, 0): "east", (0, 1): "south", (-1, 0): "west"}[(dx, dz)]
    if lake:
        pw = (bore + 2) // 2
        g["pool"] = at((cs0, cs0 + bore + 1), (-pw, pw), corr_y0, floor_y)
    if alcove:
        g["door"] = at((cs1 - alcove, cs1 - alcove), (-w2, w2), floor_y + 1, floor_y + height)
        leg_s = cs1 - max(alcove // 2, 1)
    else:
        leg_s = cs1 - 2
    g["legendary"] = (mx + dx * leg_s, floor_y + 1, mz + dz * leg_s)
    g["pedestal"] = (mx + dx * leg_s, floor_y, mz + dz * leg_s)
    # the outer chamber: the zone a qualified player has to stand in. It stops at the partition.
    outer_end = (cs1 - alcove - 1) if alcove else cs1
    g["zone"] = at((cs0, outer_end), (-w2, w2), floor_y + 1, floor_y + height)

    voids = [g["chamber"], g["passage"], g["shaft"]] + ([g["pool"]] if lake else [])
    g["envelope"] = _grow(_hull(voids), margin)
    # the envelope must stop short of the surface; the shaft climbs the rest inside its own sleeve
    ex0, ey0, ez0, ex1, ey1, ez1 = g["envelope"]
    g["envelope"] = (ex0, ey0, ez0, ex1, min(ey1, floor_y + height + margin), ez1)
    env_top = g["envelope"][4]
    sx0, sz0 = mx - r - margin, mz - r - margin
    sx1, sz1 = mx + r + margin, mz + r + margin
    g["sleeve_footprint"] = (sx0, sz0, sx1, sz1)
    g["sleeve_top"] = int(ground.box(sx0, sz0, sx1, sz1).min()) - 1
    g["sleeve"] = (sx0, env_top + 1, sz0, sx1, g["sleeve_top"], sz1)
    g["env_footprint_min_ground"] = int(ground.box(ex0, ez0, ex1, ez1).min())
    g["bbox"] = _hull([g["envelope"], (sx0, env_top + 1, sz0, sx1, my, sz1)])
    g["lanterns"] = _lanterns(g["chamber"], alcove, (dx, dz), floor_y + height)
    return g


def _box(x0, y0, z0, x1, y1, z1):
    return (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1))


def _hull(boxes):
    xs0 = min(b[0] for b in boxes); ys0 = min(b[1] for b in boxes); zs0 = min(b[2] for b in boxes)
    xs1 = max(b[3] for b in boxes); ys1 = max(b[4] for b in boxes); zs1 = max(b[5] for b in boxes)
    return (xs0, ys0, zs0, xs1, ys1, zs1)


def _grow(b, m):
    return (b[0] - m, b[1] - m, b[2] - m, b[3] + m, b[4] + m, b[5] + m)


def volume(b):
    return (b[3] - b[0] + 1) * (b[4] - b[1] + 1) * (b[5] - b[2] + 1)


def _lanterns(chamber, alcove, axis, y):
    """Hanging lanterns under the chamber roof: the four quarters and the middle. Lanterns, never light
    blocks (docs/STATE.md, 'Places are lit as towns')."""
    x0, _y0, z0, x1, _y1, z1 = chamber
    xs = sorted({x0 + (x1 - x0) // 4, (x0 + x1) // 2, x1 - (x1 - x0) // 4})
    zs = sorted({z0 + (z1 - z0) // 4, (z0 + z1) // 2, z1 - (z1 - z0) // 4})
    return [(x, y, z) for x in xs for z in zs]


# ------------------------------------------------------------------ the pack


def _fill(box, block, extra=""):
    """One or more `fill` lines, split along the longest axis so none exceeds Minecraft's 32,768."""
    x0, y0, z0, x1, y1, z1 = box
    if volume(box) <= FILL_LIMIT:
        return ["fill %d %d %d %d %d %d %s%s" % (x0, y0, z0, x1, y1, z1, block, extra)]
    span = [(y1 - y0, 1), (x1 - x0, 0), (z1 - z0, 2)]
    span.sort(reverse=True)
    axis = span[0][1]
    lo, hi = box[axis], box[axis + 3]
    mid = (lo + hi) // 2
    a, b = list(box), list(box)
    a[axis + 3] = mid
    b[axis] = mid + 1
    return _fill(tuple(a), block, extra) + _fill(tuple(b), block, extra)


def _sel(rec, ns, met_false=False):
    """The advancement predicate a player must satisfy at this encounter's gate."""
    keys = ["%s:flag/%s=true" % (ns, f) for f in rec["gate"]["flags"]]
    keys += ["%s:legendary/%s/met=true" % (ns, m) for m in rec["gate"].get("requires_met") or []]
    if met_false:
        keys.append("%s:legendary/%s/met=false" % (ns, rec["id"]))
    return "advancements={%s}" % ",".join(keys)


def _zone_sel(box, extra):
    x0, y0, z0, x1, y1, z1 = box
    return "@a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d,%s]" % (x0, y0, z0, x1 - x0, y1 - y0, z1 - z0, extra)


def _nbt(d):
    return ",".join("%s:%s" % (k, v) for k, v in d.items())


def carve_lines(rec, doc, g):
    """The chamber, in the order that makes the seal true: solid first, then the void, then the water."""
    d = doc["defaults"]
    lake = rec["kind"] == "lake_grotto"
    out = ["# Generated by tools/legendaries.py from data/legendaries.json: %s" % rec["title"],
           "# chunks-loaded-by: tools/reapply.py R14L (forceload add over RCON before this runs)",
           "# the envelope is filled SOLID first and reaches %d blocks beyond every void: that is the seal"
           % int(d["shell_margin"])]
    out += _fill(g["envelope"], d["envelope_block"])
    out += _fill(g["sleeve"], d["envelope_block"])
    out += _fill(g["chamber"], "minecraft:air")
    if lake:
        out += _fill(g["pool"], "minecraft:water")
        out += _fill(g["passage"], "minecraft:water")
        out += _fill(g["shaft"], "minecraft:water")
    else:
        out += _fill(g["passage"], "minecraft:air")
        out += _fill(g["shaft"], "minecraft:air")
        out += _fill(g["ladder"], "minecraft:ladder[facing=%s]" % g["ladder_facing"])
    if "door" in g:
        out += _fill(g["door"], d["door_block"])
    px, py, pz = g["pedestal"]
    out.append("setblock %d %d %d %s" % (px, py, pz, d["pedestal_block"]))
    for x, y, z in g["lanterns"]:
        out.append("setblock %d %d %d %s replace" % (x, y, z, d["light"]))
    return out


def _celebi_wake(rec, doc, ns):
    """The wake of the sleeping Celebi: the gate, and the function that takes the barrier shell off.

    CALLED BY cobblers:celebi/wake (tools/sapling_celebi.py), which watches for the trigger on the Celebi
    keeper's own loop: a player past this gate, within wake.radius of the branch, holding wake.item
    (data/sapling_celebi.json, docs/mechanics/CELEBI_WAKE.md). EXP-023's candidate, a
    `minecraft:item_used_on_block` advancement, was dropped: an advancement fires once per player for ever
    and cannot test another advancement, so a player who tried the item before the gate opened would have
    burned it, and the barrier shell seals every face of the branch block so it cannot be used on at all.

    The badge check lives INSIDE `open`, not in the caller, so the trigger cannot skip it. `open` also sets
    the Celebi pack's awake score, which is what stands its keeper down: without that the keeper teleports
    the woken Celebi back onto its branch every 40 ticks, through the battle the wake exists to give.
    """
    import sapling_celebi
    sc = sapling_celebi.load()
    x0, y0, z0, x1, y1, z1 = sapling_celebi.shell_box(sc)
    cx, cy, cz = (int(v // 1) for v in sc["position"])
    rid = rec["id"]
    flags = ",".join("%s:flag/%s=true" % (ns, f) for f in rec["gate"]["flags"])
    return {
        "legendary/%s/open" % rid: [
            "# Generated by tools/legendaries.py. RUN AS THE WAKING PLAYER, by cobblers:celebi/wake.",
            "# chunks-loaded-by: the waking player, who stands within %d blocks of this write"
            % int(sc["wake"]["radius"]),
            "execute unless entity @s[advancements={%s}] run return 0" % flags,
            "execute if %s run return 0" % sapling_celebi.awake_if(1),
            "advancement grant @s only %s:legendary/%s/met" % (ns, rid),
            "fill %d %d %d %d %d %d minecraft:air replace minecraft:barrier" % (x0, y0, z0, x1, y1, z1),
            "data merge entity @e[tag=%s,limit=1] {%s}" % (sapling_celebi.TAG, _nbt(AWAKE)),
            "# the Celebi keeper (tools/sapling_celebi.py) stands down on this score. Without it, celebi/keep",
            "# teleports the woken Celebi back onto its branch every %d ticks while a player is within %d blocks."
            % (sc["keeper"]["period_ticks"], sc["keeper"]["player_radius"]),
            sapling_celebi.awake_set(1),
            "tellraw @a[distance=..48] %s" % json.dumps(
                {"text": "The Celebi opens its eyes.", "color": "green", "italic": True}, ensure_ascii=False),
            "playsound minecraft:block.beacon.activate master @a[distance=..48] %d %d %d 1 1.6" % (cx, cy, cz)],
    }


def files(doc, ground):
    ns = doc["namespace"]
    obj = doc["objective"]
    period = int(doc["period_ticks"])
    recs = emitted(doc)
    fn, adv = {}, {}
    # every encounter gets its `met` advancement, blocked ones included: a selector that names an advancement
    # the server does not know is a command error, and Regigigas's gate names all three golems, one of which
    # (registeel) has no chamber yet. The advancement exists and is simply never granted.
    for rec in doc["encounters"]:
        adv["legendary/%s/met" % rec["id"]] = {"criteria": {"granted": {"trigger": "minecraft:impossible"}},
                                               "requirements": [["granted"]]}
    tick = ["# Generated by tools/legendaries.py: one proximity line per emitted encounter, every %dt." % period,
            "# The Celebi keeper's shape (tools/sapling_celebi.py): nothing else runs until somebody is near."]
    load = ["scoreboard objectives add %s dummy" % obj]
    for rec in recs:
        rid = rec["id"]
        tag = doc["tag_prefix"] + rid
        g = geometry(rec, doc, ground)
        lake = rec["kind"] == "lake_grotto"
        lx, ly, lz = g["legendary"]
        at = "%.1f %d %.1f" % (lx + 0.5, ly, lz + 0.5)
        if lake:
            # driven from the CHAMBER's centre, not the mouth: open/close write the partition, so whoever
            # trips the driver has to be close enough to be holding those chunks loaded themselves
            cx0, cy0, cz0, cx1, cy1, cz1 = g["chamber"]
            drive_x, drive_y, drive_z = (cx0 + cx1) // 2, (cy0 + cy1) // 2, (cz0 + cz1) // 2
            reach = 48
        else:
            # driven from the portal, where the only block write (the plug) is; the chamber below is the
            # same column, so `met` reaches it without a second driver
            drive_x, drive_y, drive_z = (g["anchor"][0], g["mouth_y"], g["anchor"][1])
            reach = int(rec["approach"]["drop"]) + 48
        load.append("scoreboard players add #%s %s 0" % (rid, obj))
        tick.append("execute positioned %d %d %d if entity @a[distance=..%d] run function %s:legendary/%s/near"
                    % (drive_x, drive_y, drive_z, reach, ns, rid))

        near = ["# %s. The gate is the advancement predicate on every line that can open this chamber." % rec["title"]]
        gate_zone = g["zone"] if lake else _grow(_box(g["anchor"][0], g["mouth_y"], g["anchor"][1],
                                                      g["anchor"][0], g["mouth_y"] + 2, g["anchor"][1]), 2)
        near.append("execute if entity %s unless score #%s %s matches 1 run function %s:legendary/%s/open"
                    % (_zone_sel(gate_zone, _sel(rec, ns)), rid, obj, ns, rid))
        if lake:
            near.append("execute unless entity %s unless score #%s %s matches 0 run function %s:legendary/%s/close"
                        % (_zone_sel(gate_zone, _sel(rec, ns)), rid, obj, ns, rid))
        near.append("execute as %s run function %s:legendary/%s/met"
                    % (_zone_sel(g["zone"], _sel(rec, ns, met_false=True)), ns, rid))
        near.append("execute if score #%s %s matches 0 run function %s:legendary/%s/keep" % (rid, obj, ns, rid))

        open_ = ["# chunks-loaded-by: the player who trips it. cobblers:legendary/%s/near only calls this when a"
                 " qualified player stands within %d blocks of this write, inside their own simulation radius"
                 % (rid, reach),
                 "scoreboard players set #%s %s 1" % (rid, obj)]
        if lake:
            open_ += _fill(g["door"], "minecraft:air", " replace %s" % doc["defaults"]["door_block"])
        else:
            open_ += _fill(g["plug"], "minecraft:air")
        open_ += ["data merge entity @e[tag=%s,limit=1] {%s}" % (tag, _nbt(AWAKE)),
                  "playsound minecraft:block.beacon.activate master @a[distance=..48] %d %d %d 1 0.6"
                  % (lx, ly, lz),
                  "tellraw @a[distance=..48] %s" % json.dumps(
                      {"text": rec["title"].split(",")[0] + " stirs.", "color": "aqua", "italic": True},
                      ensure_ascii=False)]
        fn["legendary/%s/open" % rid] = open_

        if lake:
            fn["legendary/%s/close" % rid] = (
                ["# chunks-loaded-by: the player who trips it: near only runs while somebody is within %d blocks"
                 % reach,
                 "scoreboard players set #%s %s 0" % (rid, obj)]
                + _fill(g["door"], doc["defaults"]["door_block"], " replace minecraft:air")
                + ["data merge entity @e[tag=%s,limit=1] {%s}" % (tag, _nbt(DORMANT))])

        fn["legendary/%s/dress" % rid] = ["data merge entity @s {%s}" % _nbt(DORMANT),
                                          "tag @s add %s" % tag,
                                          "tp @s %s 0 0" % at]
        fn["legendary/%s/dress_new" % rid] = [
            "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..3,limit=1,sort=nearest] "
            "run function %s:legendary/%s/dress" % (at, tag, ns, rid)]
        fn["legendary/%s/keep" % rid] = [
            "# only while the chamber is shut: never drag a Pokemon out of a battle in progress",
            "execute store result score #%s_n %s if entity @e[tag=%s]" % (rid, obj, tag),
            "execute if score #%s_n %s matches 2.. run kill @e[tag=%s,limit=1,sort=random]" % (rid, obj, tag),
            "execute as @e[tag=%s] run function %s:legendary/%s/dress" % (tag, ns, rid)]
        fn["legendary/%s/met" % rid] = [
            "# runs as the qualifying player, once: the advancement is the per-player record",
            "advancement grant @s only %s:legendary/%s/met" % (ns, rid),
            "tellraw @s %s" % json.dumps({"text": "You have found %s." % rec["title"].split(",")[0],
                                          "color": "gold"}, ensure_ascii=False)]
        fn["legendary/%s/near" % rid] = near
        fn["legendary/%s/carve" % rid] = carve_lines(rec, doc, g)

    for rec in gate_only(doc):
        rid = rec["id"]
        fn |= _celebi_wake(rec, doc, ns)

    tick.append("schedule function %s:legendary/tick %dt replace" % (ns, period))
    for rec in gate_only(doc):
        # Named here on purpose, in a comment, so tools/reapply.py's uncovered() check sees that nothing
        # driving it is a decision rather than a pack function silently lost. The gate lives inside the
        # function itself, so whichever trigger is chosen later cannot skip it.
        tick.append("# %s:legendary/%s/open is not driven from here: it has no chamber and no proximity driver. "
                    "Its trigger lives with the entity it wakes (cobblers:celebi/wake, tools/sapling_celebi.py, "
                    "on that pack's own 40-tick loop)." % (ns, rec["id"]))
    load.append("schedule function %s:legendary/tick %dt replace" % (ns, period))
    fn["legendary/tick"] = tick
    fn["legendary/load"] = load

    out = {"data/%s/function/%s.mcfunction" % (ns, n): "\n".join(v) + "\n" for n, v in fn.items()}
    out |= {"data/%s/advancement/%s.json" % (ns, n): json.dumps(v, indent=2) + "\n" for n, v in adv.items()}
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:legendary/load" % ns]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT,
                                              "description": "Cobblers: the authored legendary encounters "
                                                             "(tools/legendaries.py)"}}, indent=2) + "\n"
    return out


# ------------------------------------------------------------------ the re-application


def placement_steps(doc, ground=None):
    """tools/reapply.py R14L: hold the chunks, carve, summon over RCON, dress, shut the gate, release."""
    import ground as G
    ground = ground or G.load()
    steps = []
    ns = doc["namespace"]
    for rec in emitted(doc):
        rid = rec["id"]
        tag = doc["tag_prefix"] + rid
        g = geometry(rec, doc, ground)
        x0, _y0, z0, x1, _y1, z1 = g["bbox"]
        lx, ly, lz = g["legendary"]
        at = "%.1f %d %.1f" % (lx + 0.5, ly, lz + 0.5)
        steps += [("cmd", "forceload add %d %d %d %d" % (x0, z0, x1, z1)), ("wait", 3),
                  ("fn", "%s:legendary/%s/carve" % (ns, rid)),
                  ("cmd", "execute unless entity @e[tag=%s] positioned %s unless entity "
                          "@e[type=cobblemon:pokemon,distance=..3] run spawnpokemonat %s %s level=%d no_ai"
                   % (tag, at, at, rec["species"], int(rec["level"]))),
                  ("wait", 1),
                  ("fn", "%s:legendary/%s/dress_new" % (ns, rid))]
        if rec["kind"] == "lake_grotto":
            steps.append(("fn", "%s:legendary/%s/close" % (ns, rid)))
        steps.append(("cmd", "forceload remove %d %d %d %d" % (x0, z0, x1, z1)))
    return steps


# ------------------------------------------------------------------ CLI


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print each record's geometry and write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g_ = G.load(a.source_root)
    recs = emitted(doc)
    if a.report:
        for rec in doc["encounters"]:
            if rec["status"] != "sited":
                print("%-12s %-14s BLOCKED on %s" % (rec["id"], rec["kind"], rec["blocked_by"]))
                continue
            g = geometry(rec, doc, g_)
            print("%-12s %-14s anchor %s ground y%d  floor y%d  ceiling y%d  envelope %s vol %d  "
                  "clearance %d  sleeve top y%d (mouth %+d)"
                  % (rec["id"], rec["kind"], g["anchor"], g["mouth_y"], g["floor_y"], g["ceiling_y"],
                     g["envelope"], volume(g["envelope"]),
                     g["env_footprint_min_ground"] - g["envelope"][4], g["sleeve_top"],
                     g["mouth_y"] - g["sleeve_top"] - 1))
        return 0

    out = Path(a.out)
    written = files(doc, g_)
    import function_limits
    bad = []
    for rel, text in written.items():
        if rel.endswith(".mcfunction"):
            bad += ["%s:%d %s: %s" % (rel, n, cmd, why)
                    for n, cmd, why in function_limits.check_lines(text.splitlines(), where=rel)]
    for m in bad:
        print("ERROR %s" % m)
    if bad:
        return 1
    if out.exists():
        shutil.rmtree(out)
    for rel, text in written.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    blocked = [r["id"] for r in doc["encounters"] if r["status"] != "sited"]
    print("legendaries: %d chambers emitted (%s) -> %s" % (len(recs), ", ".join(r["id"] for r in recs), out))
    print("             %d NOT emitted, each with a named blocker: %s" % (len(blocked), ", ".join(blocked)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
