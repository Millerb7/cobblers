#!/usr/bin/env python
"""The authored legendary encounters and their chambers, from data/legendaries.json.

Ten encounters: the lake trio in air-chambered grottos (Mesprit, Azelf, Uxie), the four bespoke concepts
(the three Regis as one puzzle, Regigigas, Groudon, Lugia) and the wake of the sleeping Celebi. Only the
records whose `status` is "sited" are emitted; everything else is data with a named blocker, and this tool
refuses to write a block for it. That is the fail-closed half: a chamber that cannot be sited offline
cannot reach a world by accident.

WHAT A FUNCTION CAN AND CANNOT DO HERE
  - A Pokemon is summoned by tools/reapply.py (step R14L), which runs each chamber's look-then-act chain
    (tools/chunk_look.py; 2026-10-12): the summon is a MACRO line in the chamber's function, because a plain
    `spawnpokemonat` in a function parsed at server start spawns nothing (EXP-046), and it fires only when the
    chunk's saved entities have arrived and no tagged legendary stands. So R14L is safe to re-run: it leaves an
    existing legendary alone and adds only a missing one, and it does not re-seal a chamber a player has opened
    (carve_once). Same pattern as tools/drowned_quarry.py.
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

A RECORD THAT MOVES (2026-10-12, Regigigas to the North Pine Isle) keeps its old chamber in `retired_sites`, each
entry the numbers that chamber was carved from (bore, shell_margin and pedestal_block frozen as they stood). For
each, files() emits a look-then-act cleanup that R14L runs BEFORE any summon: it refuses while a player stands in
a retired void (and the step reads the held count back, so the run stops), restores the voids to rock and the
sleeve and plug columns to the heightmap's terrain, clears the retired chamber's open score, and kills the record's
own legendary in the old chamber's box. The restore runs only while the old pedestal stands, so a second run
writes nothing; its ground is the heightmap (never a world) and its surface block is data, `terrain.surface`.

A retired site of kind `quake_cavern` (2026-10-21, Groudon's quake cavern, which the owner had undone and the old
chamber put back) is not a box chain: tools/groudon_cavern.py retire_functions emits its cleanup in the same shape
(look-then-act, refuse while a player stands in a void, read the held count back, restore only while the cavern is
there, kill the record's own legendary in the cavern's box), and this tool puts it in the pack and in R14L's order.

  python tools/legendaries.py                     # -> build/datapacks/cobblers_legendaries
  python tools/legendaries.py --report            # the geometry of every record, nothing written

A record's optional `cache` (2026-10-08) names a data/rewards.json cache whose container is the chamber's
pedestal; this tool only holds that record's coordinates to the geometry (cache_problems) and writes no item.
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
RETIRED_KINDS = ("sealed_chamber", "quake_cavern")   # a retired site's `kind`; absent means sealed_chamber
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
        _check_retired(r)
    if not seen:
        raise LegendaryError("%s: no encounters" % path)
    return doc


RETIRED_KEYS = ("id", "retired", "why", "portal", "approach", "chamber", "plug_depth", "bore", "shell_margin",
                "pedestal_block", "terrain")
# a retired quake cavern (2026-10-21): its geometry is data/groudon_cavern.json's model, frozen by the applied record's sha256
RETIRED_QUAKE_KEYS = ("id", "retired", "why", "portal", "cavern", "pedestal", "pedestal_block", "applied", "terrain")
TERRAIN_KEYS = ("surface", "under", "deep")


def _check_retired(rec):
    """A record's `retired_sites` (2026-10-12): the chambers it used to have, each frozen with the numbers it was
    carved from so tools/legendaries.py can undo it. Fail closed on anything the cleanup would have to guess."""
    seen = set()
    for s in rec.get("retired_sites") or []:
        sid = s.get("id")
        where = "%s retired site %r" % (rec["id"], sid)
        if not isinstance(sid, str) or not sid.replace("_", "").isalnum() or sid != sid.lower():
            raise LegendaryError("%s: the id must be a lowercase [a-z0-9_] name" % where)
        if sid in seen:
            raise LegendaryError("%s: declared twice" % where)
        seen.add(sid)
        if rec["kind"] != "sealed_chamber":
            raise LegendaryError("%s: only a sealed_chamber can have a retired site (a lake grotto's undoing is the "
                                 "water's, and nothing here writes it)" % where)
        kind = site_kind(s)
        if kind not in RETIRED_KINDS:
            raise LegendaryError("%s: kind must be one of %s" % (where, ", ".join(RETIRED_KINDS)))
        for k in (RETIRED_QUAKE_KEYS if kind == "quake_cavern" else RETIRED_KEYS):
            if k not in s:
                raise LegendaryError("%s: no %s; the cleanup would have to guess it" % (where, k))
        for k in TERRAIN_KEYS:
            if not isinstance(s["terrain"].get(k), str) or not s["terrain"][k].startswith("minecraft:"):
                raise LegendaryError("%s: terrain.%s must be a minecraft: block id" % (where, k))
        if not (isinstance(s["portal"], list) and len(s["portal"]) == 2):
            raise LegendaryError("%s: portal must be [x, z]" % where)
        if s["portal"] == rec.get("portal"):
            raise LegendaryError("%s: the retired portal is the record's live portal; nothing moved" % where)


def site_kind(site):
    """A retired site's kind: `sealed_chamber` (the default: every site before 2026-10-21) or `quake_cavern`."""
    return site.get("kind") or "sealed_chamber"


def emitted(doc):
    """The records this tool writes blocks and gate code for: sited only, never a blocked one."""
    return [r for r in doc["encounters"] if r["status"] == "sited"]


def retired(doc):
    """[(record, site)] for every retired chamber site of every record, in file order."""
    return [(r, s) for r in doc["encounters"] for s in (r.get("retired_sites") or [])]


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


# ------------------------------------------------------------------ a retired chamber (2026-10-12)

RETIRE_HELD = "cobblers_leg_retire_held"   # worn by a player standing in a retired void: the restore refused


def retired_geometry(rec, site, doc, ground):
    """geometry() over a retired site's frozen numbers (bore and shell_margin as they stood when it was carved)."""
    pseudo = {"id": rec["id"], "kind": "sealed_chamber", "portal": site["portal"], "approach": site["approach"],
              "chamber": site["chamber"], "plug_depth": site["plug_depth"]}
    pdoc = {"defaults": dict(doc["defaults"], bore=site["bore"], shell_margin=site["shell_margin"])}
    return geometry(pseudo, pdoc, ground)


def retire_parts(rec, site, doc):
    """(chain base, restore function, score holder, chain's new tag) of one retired site's cleanup."""
    base = "%s:legendary/%s/retire_%s" % (doc["namespace"], rec["id"], site["id"])
    return base, base + "_restore", "legret_%s_%s" % (rec["id"], site["id"]), doc["tag_prefix"] + rec["id"] + ".retire"


def _vol(box):
    x0, y0, z0, x1, y1, z1 = box
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (x0, y0, z0, x1 - x0, y1 - y0, z1 - z0)


def retire_rects(cols):
    """{(x, z): key} -> [(x0, x1, z0, z1, key)]: runs of equal key along x, rows of equal runs merged over z."""
    rows = {}
    for (x, z), k in sorted(cols.items(), key=lambda c: (c[0][1], c[0][0])):
        runs = rows.setdefault(z, [])
        if runs and runs[-1][1] == x - 1 and runs[-1][2] == k:
            runs[-1][1] = x
        else:
            runs.append([x, x, k])
    out, zs = [], sorted(rows)
    i = 0
    while i < len(zs):
        j = i
        while j + 1 < len(zs) and zs[j + 1] == zs[j] + 1 and rows[zs[j + 1]] == rows[zs[i]]:
            j += 1
        for x0, x1, k in rows[zs[i]]:
            out.append((x0, x1, zs[i], zs[j], k))
        i = j + 1
    return out


def terrain_lines(cols, ground, terrain):
    """fill lines putting every column of `cols` ({(x, z): (lo, hi)}) back to terrain over its y range: `deep` to three
    under the ground, `under` to one under, `surface` at the ground, air above, up to hi. The ground is the heightmap's,
    rounded (never a world). tools/rift_zones.py restore_lines' rule, which tools/gym_demolish.py shares in spirit."""
    keyed = {c: (ground(c[0], c[1]), lo, hi) for c, (lo, hi) in cols.items()}
    out = []
    for x0, x1, z0, z1, (gy, lo, hi) in retire_rects(keyed):
        def band(a, b, block):
            if a <= b:
                out.append("fill %d %d %d %d %d %d %s" % (x0, a, z0, x1, b, z1, block))
        band(lo, min(gy - 3, hi), terrain["deep"])
        band(max(lo, gy - 2), min(gy - 1, hi), terrain["under"])
        band(max(lo, gy), min(gy, hi), terrain["surface"])
        band(max(lo, gy + 1), hi, "minecraft:air")
    return out


def retire_restore_lines(rec, site, doc, ground):
    """The retired chamber, put back: the open score cleared (the new chamber is unopened), every carved void back
    to rock, every column the sleeve and plug wrote back to terrain from the heightmap, the pedestal last (the
    probe that gates all of it, so an interrupted run is run again)."""
    g = retired_geometry(rec, site, doc, ground)
    t = site["terrain"]
    mx, mz = g["anchor"]
    my = g["mouth_y"]
    r = int(site["bore"]) // 2
    out = ["# Generated by tools/legendaries.py from data/legendaries.json: %s, retired site %s (%s)."
           % (rec["title"], site["id"], site["retired"]),
           "# chunks-loaded-by: %s (its forceload holds the retired site's whole hull)" % retire_parts(rec, site, doc)[0],
           "# Run only while the pedestal still stands (or, taken by a player, its cell, the cell over it and the passage's",
           "# floor all read air), so a second run writes nothing; the pedestal is also the LAST write, so a",
           "# run that stopped half way is run again. The retired chamber's open score is cleared first: the live",
           "# chamber elsewhere is unopened, and carve_once skips a chamber whose score is 1.",
           "scoreboard players set #%s %s 0" % (rec["id"], doc["objective"])]
    for name in ("chamber", "passage", "shaft"):
        out += _fill(g[name], t["deep"])
    cols = {}
    env_top = g["envelope"][4]
    sx0, sz0, sx1, sz1 = g["sleeve_footprint"]
    for x in range(sx0, sx1 + 1):
        for z in range(sz0, sz1 + 1):
            plug = abs(x - mx) <= r and abs(z - mz) <= r
            lo, hi = env_top + 1, (max(g["sleeve_top"], my) if plug else g["sleeve_top"])
            if lo <= hi:
                cols[(x, z)] = (lo, hi)
    out += ["# the sleeve and the plug: every column back to the heightmap's terrain (%s at the ground)" % t["surface"]]
    out += terrain_lines(cols, ground, t)
    px, py, pz = g["pedestal"]
    out.append("setblock %d %d %d %s" % (px, py, pz, t["deep"]))
    return out


def gone_pedestal_probe(g):
    """[(x, y, z)] three cells of a retired chamber that read air only once it was carved and its pedestal taken away: the
    pedestal's own cell, the legendary's cell over it, and the passage's middle column at its floor level."""
    px, py, pz = g["pedestal"]
    p = g["passage"]
    return [(px, py, pz), (px, py + 1, pz), ((p[0] + p[3]) // 2, p[1], (p[2] + p[5]) // 2)]


def retire_functions(rec, site, doc, ground):
    """{'ns:path': lines} of one retired site's cleanup: a look-then-act chain (tools/chunk_look.py) that, once its
    hull shows its saved entities (or blind after the chain's limit), refuses if a player stands in a void, else
    restores the chamber (only while its pedestal stands) and kills the record's own legendary standing in it.

    The kill is the chamber's own and nothing else: type cobblemon:pokemon, the record's tag, and the retired
    chamber's box. The live chamber's legendary carries the same tag and stands elsewhere, outside that box.
    The chain counts the players it held (RETIRE_HELD); the step reads 0 back, so a refusal stops the run.

    A retired QUAKE CAVERN (2026-10-21) is tools/groudon_cavern.py's: the same shape over its own model."""
    if site_kind(site) == "quake_cavern":
        import groudon_cavern
        return groudon_cavern.retire_functions(rec, site, doc, ground)
    import chunk_look as CL
    g = retired_geometry(rec, site, doc, ground)
    base, restore, holder, new_tag = retire_parts(rec, site, doc)
    tag = doc["tag_prefix"] + rec["id"]
    scope = "type=cobblemon:pokemon,tag=%s,%s" % (tag, _vol(_grow(g["chamber"], 2)))
    # the three voids a player could stand in, each its own box (one hull would take in the surface over the chamber
    # on ground that stands lower than the plug); the shaft's box ends at the plug's top, the surface block
    shaft = g["shaft"]
    voids = [g["chamber"], g["passage"], (shaft[0], shaft[1], shaft[2], shaft[3], g["mouth_y"], shaft[5])]
    held = "@a[tag=%s]" % RETIRE_HELD
    px, py, pz = g["pedestal"]
    bb = g["bbox"]
    act = ["# the cleanup of %s's retired site %s (tools/legendaries.py retire_functions)" % (rec["id"], site["id"]),
           "# a player standing in a void is held, and nothing below is done while anyone is: the step reads the held count",
           "tag @a remove %s" % RETIRE_HELD]
    act += ["tag @a[%s] add %s" % (_vol(v), RETIRE_HELD) for v in voids]
    # the restore runs while the old pedestal stands; and ALSO when a player opened the old chamber and took the pedestal
    # away (review 2026-10-21): then the pedestal's cell, the old legendary's cell over it and the passage's floor-level
    # cell all read air, three cells that natural rock (a world that never had the chamber) does not hollow together.
    # Without it the old open score stays 1 and the live chamber's carve_once (which skips an opened chamber) never runs.
    # The restore puts rock in all three, so neither line fires twice.
    pp = gone_pedestal_probe(g)
    act += ["execute unless entity %s if block %d %d %d %s run function %s"
            % (held, px, py, pz, site["pedestal_block"], restore),
            "execute unless entity %s %s run function %s"
            % (held, " ".join("if block %d %d %d minecraft:air" % c for c in pp), restore),
            "execute unless entity %s run kill @e[%s]" % (held, scope)]
    fns = CL.chain(base, (bb[0], bb[2], bb[3], bb[5]), ["@e[%s]" % scope], act, [scope], new_tag,
                   "tag=%s" % RETIRE_HELD, holder, note="tools/legendaries.py")
    fns[restore] = retire_restore_lines(rec, site, doc, ground)
    return fns


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
            # never shut anyone in: the partition stays open while ANY player is in the chamber or the doorway
            # (play test 2026-10-05, review 87: the approach box alone let Azelf's gate close on a player inside)
            inside = _grow(_hull([g["chamber"], g["door"]]), 1)
            near.append("execute unless entity %s unless entity %s unless score #%s %s matches 0 run function %s:legendary/%s/close"
                        % (_zone_sel(gate_zone, _sel(rec, ns)), _zone_sel(inside, "gamemode=!spectator"), rid, obj, ns, rid))
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
        # R14L is safe to re-run (2026-10-12): the summon is the act of a look-then-act chain (tools/chunk_look.py,
        # N155), so it fires only once the legendary's chunk has shown its saved entities (or blind, a first run),
        # and only when no tagged one stands. A macro line summons it (EXP-046: a plain spawnpokemonat in a function
        # parsed at server start spawns nothing). The carve is skipped once the gate has opened.
        base, holder, box, scope, new_tag = chain_parts(rec, doc, g)
        sx, sy, sz = ("%.1f" % (lx + 0.5), int(ly), "%.1f" % (lz + 0.5))
        fn["legendary/%s/spawn_at" % rid] = [
            "$spawnpokemonat $(x) $(y) $(z) %s level=%d no_ai" % (rec["species"], int(rec["level"]))]
        spawn_new = [
            "# the chain's act, only when no tagged %s stands: summon it unless some Pokemon already stands at the spot"
            " (an interrupted summon, which dress_new takes), dress it, mark it for the chain's de-duplication" % rec["species"],
            "execute positioned %s unless entity @e[type=cobblemon:pokemon,distance=..3] run function %s:legendary/%s/spawn_at "
            "{x:\"%s\",y:%d,z:\"%s\"}" % (at, ns, rid, sx, sy, sz),
            "function %s:legendary/%s/dress_new" % (ns, rid)]
        # (a lake grotto's door is shut by the carve itself, and dress merges DORMANT: the old step's `close` is not
        # needed here, and it would write the door outside the chain's small held box)
        spawn_new.append("execute positioned %s as @e[%s,distance=..3,limit=1,sort=nearest] run tag @s add %s"
                         % (at, scope, new_tag))
        fn["legendary/%s/spawn_new" % rid] = spawn_new
        fn["legendary/%s/carve_once" % rid] = [
            "# a re-run must not re-seal a chamber a player has opened: carve only while the gate is shut (the score is"
            " 1 once the plug is out, or the door is open)",
            "execute unless score #%s %s matches 1 run function %s:legendary/%s/carve" % (rid, obj, ns, rid)]
        from chunk_look import chain as _chain
        act = ["# the summon, once a look has seen this chunk's saved entities (or blind after the limit: a first run)",
               "execute unless entity @e[%s] run function %s:legendary/%s/spawn_new" % (scope, ns, rid)]
        for ref, lines in _chain(base, box, ["@e[%s]" % scope], act, [scope], new_tag, scope, holder,
                                 note="tools/legendaries.py").items():
            fn[ref.split(":", 1)[1]] = lines
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

    # a record that MOVED leaves its old chamber behind in any world it was built in: the cleanup (R14L runs it first)
    for rec, site in retired(doc):
        for ref, lines in retire_functions(rec, site, doc, ground).items():
            fn[ref.split(":", 1)[1]] = lines

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


# ------------------------------------------------------------------ the chamber's cache (data/rewards.json)


REWARDS = ROOT / "data" / "rewards.json"


def cache_problems(doc, ground, rewards=None):
    """A sited record with `cache` names a data/rewards.json cache whose container is a block THIS tool writes
    (2026-10-08: `pedestal`, the setblock under the legendary). The reward itself is ADR-002's advancement
    (tools/rewards_pack.py); nothing in this pack gives an item. This holds the hand-written coordinates in that
    record to the chamber's geometry, so a moved portal, drop or chamber cannot leave the find in rock: the
    container must be the pedestal block at the pedestal, and the trigger box must hold the pedestal's column
    and stand inside the chamber's footprint, from the pedestal's y up into the chamber."""
    recs = [r for r in emitted(doc) if r.get("cache")]
    if not recs:
        return []
    rewards = rewards if rewards is not None else json.loads(REWARDS.read_text(encoding="utf-8"))
    by_id = {r.get("id"): r for r in rewards.get("rewards") or []}
    bad = []
    for rec in recs:
        c = rec["cache"]
        rid = c.get("reward")
        if c.get("container") != "pedestal":
            bad.append("%s: cache.container must be 'pedestal' (the one container this tool writes)" % rec["id"])
            continue
        r = by_id.get(rid)
        if r is None or r.get("kind") != "cache":
            bad.append("%s: cache.reward %r is not a cache in data/rewards.json" % (rec["id"], rid))
            continue
        g = geometry(rec, doc, ground)
        px, py, pz = g["pedestal"]
        ct = r.get("container") or {}
        if list(ct.get("at") or []) != [px, py, pz]:
            bad.append("%s: %s's container is at %s; the pedestal is at %s"
                       % (rec["id"], rid, ct.get("at"), [px, py, pz]))
        if ct.get("block") != doc["defaults"]["pedestal_block"]:
            bad.append("%s: %s's container block %s is not the pedestal block %s"
                       % (rec["id"], rid, ct.get("block"), doc["defaults"]["pedestal_block"]))
        t = r.get("trigger") or {}
        lo, hi = t.get("min") or [0, 0, 0], t.get("max") or [0, 0, 0]
        cx0, cy0, cz0, cx1, cy1, cz1 = g["chamber"]
        if not (lo[0] <= px <= hi[0] and lo[2] <= pz <= hi[2]):
            bad.append("%s: %s's trigger %s..%s does not hold the pedestal's column" % (rec["id"], rid, lo, hi))
        if not (cx0 <= lo[0] and hi[0] <= cx1 and cz0 <= lo[2] and hi[2] <= cz1 and lo[1] == py
                and py < hi[1] <= cy1):
            bad.append("%s: %s's trigger %s..%s leaves the chamber %s (from the pedestal's y%d up)"
                       % (rec["id"], rid, lo, hi, g["chamber"], py))
        if not r.get("requires_flags"):
            bad.append("%s: %s has no requires_flags; a legendary's item is gated (docs/mechanics/ITEM_ROUTES.md "
                       "section 1)" % (rec["id"], rid))
    return bad


# ------------------------------------------------------------------ the re-application


def chain_parts(rec, doc, g):
    """(base, holder, box, scope, new tag) of one legendary's look-then-act chain (tools/chunk_look.py)."""
    lx, _ly, lz = g["legendary"]
    tag = doc["tag_prefix"] + rec["id"]
    return ("%s:legendary/%s/place" % (doc["namespace"], rec["id"]), "legendary_%s" % rec["id"],
            (lx - 4, lz - 4, lx + 4, lz + 4), "type=cobblemon:pokemon,tag=%s" % tag, tag + ".new")


def placement_steps(doc, ground=None):
    """tools/reapply.py R14L, safe to re-run: per chamber, hold the chunks, carve (not once the gate has opened),
    release, then the look-then-act chain that summons the legendary only if none stands, and its count read back.

    The chain holds and releases its own chunks, so the step's hold is released BEFORE it (a forceload is per
    chunk, not counted). A re-run therefore leaves an existing legendary alone and adds only a missing one.

    FIRST, the cleanup of every retired chamber site (retire_functions): a chain per site that restores the old
    chamber and kills the record's own legendary standing in it, read back as 0 players held. It runs before any
    summon so the old legendary is gone before the live one is added, and it is safe to run twice."""
    import chunk_look as CL
    import ground as G
    ground = ground or G.load()
    steps = []
    ns = doc["namespace"]
    for rec, site in retired(doc):
        base, _restore, holder, _new = retire_parts(rec, site, doc)
        steps += CL.steps(base, holder, 0, "%s's retired site %s (players held in it)" % (rec["id"], site["id"]))
    for rec in emitted(doc):
        rid = rec["id"]
        g = geometry(rec, doc, ground)
        x0, _y0, z0, x1, _y1, z1 = g["bbox"]
        base, holder, _box, _scope, _new = chain_parts(rec, doc, g)
        steps += [("cmd", "forceload add %d %d %d %d" % (x0, z0, x1, z1)), ("wait", 3),
                  ("fn", "%s:legendary/%s/carve_once" % (ns, rid)),
                  ("cmd", "forceload remove %d %d %d %d" % (x0, z0, x1, z1))]
        steps += CL.steps(base, holder, 1, "%s's legendary" % rid)
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
        for rec, site in retired(doc):
            if site_kind(site) == "quake_cavern":
                print("%-12s RETIRED %-14s lip %s  cavern %s  (%s; python tools/groudon_cavern.py report)"
                      % (rec["id"], site["id"], site["portal"], site["cavern"], site["retired"]))
                continue
            g = retired_geometry(rec, site, doc, g_)
            print("%-12s RETIRED %-14s anchor %s ground y%d  floor y%d  hull %s  (%s)"
                  % (rec["id"], site["id"], g["anchor"], g["mouth_y"], g["floor_y"], g["bbox"], site["retired"]))
        return 0

    out = Path(a.out)
    written = files(doc, g_)
    import function_limits
    bad = []
    for rel, text in written.items():
        if rel.endswith(".mcfunction"):
            bad += ["%s:%d %s: %s" % (rel, n, cmd, why)
                    for n, cmd, why in function_limits.check_lines(text.splitlines(), where=rel)]
    bad += cache_problems(doc, g_)
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
