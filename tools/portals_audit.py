#!/usr/bin/env python
"""Check the written portals pack against everything EXCEPT itself. Offline, fail-closed.

The rule this obeys (CLAUDE.md, "Verify before claiming"): an expectation derived from the artifact being
checked is not an expectation. So this tool never imports tools/portals.py and never reuses a number it wrote.
It reads the pack's FUNCTIONS as text, replays their fills, setblocks and summons into a voxel model, and then
holds that model against its own, separately written reading of:

  data/portals.json      the twelve portals, the gates, the room kinds, the rules and the loot
  tools/ground.py        the canonical heightmap, rounded -- the apron's y is recomputed here, not read back
  data/landmarks.json    each dive portal's water body: its `water_body.basin_polygons` and `level_y`, which
                         is where tools/paint_maps.py actually paints water. NOT the landmark's `extent`
                         polygons, which this tool used until F7: they are the place's label outline, they
                         enclose 219,737 dry columns at Lake Tilpey alone, and a portal in that gap passed.
                         This check is written separately from tools/water_mask.py on purpose, so the builder
                         and the audit are still two independent readings of the same rule
  data/towns.json        town footprints            } the clearances, recomputed
  data/placements.json   built places               }
  data/legendaries.json  the sited legendary mouths }
  data/spawn_blocks.json no block written in the WORLD may be a Cobblemon spawn condition
  build/datapacks/*      no other pack writes a block near a portal

  python tools/portals_audit.py [--source-root <root>] [--packs build/datapacks]

Exit 0 and "CLEAN" when every check passes; exit 1 and one line per problem otherwise.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

DATA = ROOT / "data" / "portals.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_portals"
NS = "cobblers"

FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: (\w+))?(?: (\S+))?\s*$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)\s*$")
SUMMON = re.compile(r"^summon (\S+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (\{.*\})\s*$")
TP = re.compile(r"^execute in (\S+) run tp @s (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)\s*$")
ANYWRITE = re.compile(r"(?:^|\brun )(?:fill|setblock|clone|place template \S+) (-?\d+) (-?\d+) (-?\d+)"
                      r"(?: (-?\d+) (-?\d+) (-?\d+))?")


def name_of(block):
    """`minecraft:chest[facing=north]{LootTable:"..."}` -> `minecraft:chest`."""
    return block.split("[")[0].split("{")[0]


def in_polygon(poly, x, z):
    n, c, j = len(poly), False, len(poly) - 1
    for i in range(n):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / float(zj - zi) + xi):
            c = not c
        j = i
    return c


def replay(lines):
    """{(x, y, z): block} and [(entity, x, y, z, nbt)], in order, as the server would leave them.

    `fill ... replace <filter>` is skipped: it clears whatever a world happens to hold, which a model of an
    empty world cannot express, and it never places a block."""
    blocks, entities = {}, []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = FILL.match(line)
        if m:
            x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
            if m.group(8) == "replace":
                continue
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        blocks[(x, y, z)] = m.group(7)
            continue
        m = SETBLOCK.match(line)
        if m:
            blocks[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = m.group(4)
            continue
        m = SUMMON.match(line)
        if m:
            entities.append((m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4)), m.group(5)))
    return blocks, entities


def read(path):
    return path.read_text(encoding="utf-8").splitlines()


def expected_apron_y(ground, x, z):
    """The apron's y, recomputed here: the highest rounded heightmap ground under the 5 by 5."""
    return max(ground(x + dx, z + dz) for dx in range(-2, 3) for dz in range(-2, 3))


def audit(a):
    import ground as G
    bad = []
    doc = json.loads(DATA.read_text(encoding="utf-8"))
    if not PACK.is_dir():
        return ["the pack is not built: run `python tools/portals.py build` first (%s)" % PACK]
    g = G.Ground(a.source_root)
    rules, pocket = doc["rules"], doc["pocket"]
    fy, dim = pocket["floor_y"], pocket["dimension"]
    marks = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))["landmarks"]
    # (level_y, basin polygons): the basin is the painted water, the extent is only the label outline (F7)
    bodies = {l["id"]: ((l.get("water_body") or {}).get("level_y"),
                        (l.get("water_body") or {}).get("basin_polygons") or [])
              for l in marks}
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    places = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
    legend = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))["encounters"]
    spawn_blocks = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])

    fdir = PACK / "data" / NS / "function" / "portals"
    adir = PACK / "data" / NS / "advancement" / "portals"
    ldir = PACK / "data" / NS / "loot_table" / "portals"
    world_cols, rooms, per_gate = {}, {}, Counter()

    # ---- the dimension itself ------------------------------------------------------------------------
    half = dim.split(":")[1]
    dt = PACK / "data" / NS / "dimension_type" / ("%s.json" % half)
    dd = PACK / "data" / NS / "dimension" / ("%s.json" % half)
    for f in (dt, dd):
        if not f.is_file():
            bad.append("missing %s" % f.relative_to(PACK))
    if dt.is_file() and dd.is_file():
        t = json.loads(dt.read_text(encoding="utf-8"))
        d = json.loads(dd.read_text(encoding="utf-8"))
        gen = pocket["generator"]
        if d.get("type") != pocket["dimension_type"]:
            bad.append("the dimension's type is %r, not %r" % (d.get("type"), pocket["dimension_type"]))
        if t.get("min_y") != gen["min_y"] or t.get("height") != gen["height"]:
            bad.append("dimension_type min_y/height %s/%s, data says %s/%s"
                       % (t.get("min_y"), t.get("height"), gen["min_y"], gen["height"]))
        if t.get("has_skylight") != gen["has_skylight"] or t.get("fixed_time") != gen["fixed_time"]:
            bad.append("dimension_type skylight/fixed_time disagree with data/portals.json")
        if t.get("bed_works") or t.get("respawn_anchor_works"):
            bad.append("a bed or a respawn anchor works in the pocket dimension: a player could set spawn there")
        s = (d.get("generator") or {}).get("settings") or {}
        if s.get("biome") != gen["biome"] or s.get("layers") != gen["layers"]:
            bad.append("the flat generator's biome or layers disagree with data/portals.json")
        if s.get("features") or s.get("lakes"):
            bad.append("the flat generator has features or lakes on")
        if fy <= gen["min_y"] + 2:
            bad.append("the room floor y%d is on top of the generated layer: nothing to fall onto" % fy)

    # ---- every portal --------------------------------------------------------------------------------
    for index, spec in enumerate(doc["portals"], start=1):
        pid, gate, kind = spec["id"], spec["gate"], doc["rooms"][spec["room"]]
        pal, gt = doc["blocks"][gate], doc["gates"][gate]
        per_gate[gate] += 1
        x, z = spec["at"]

        wf, rf = fdir / "world" / ("%s.mcfunction" % pid), fdir / "pocket" / ("%s.mcfunction" % pid)
        ef, lf = fdir / "enter" / ("%s.mcfunction" % pid), fdir / "leave" / ("%s.mcfunction" % pid)
        missing = [f for f in (wf, rf, ef, lf) if not f.is_file()]
        if missing:
            bad += ["%s: missing %s" % (pid, f.name) for f in missing]
            continue

        # -- the world side --------------------------------------------------------------------------
        wb, went = replay(read(wf))
        ay = expected_apron_y(g, x, z)
        cols = [(x + dx, z + dz) for dx in range(-2, 3) for dz in range(-2, 3)]
        relief = max(g(*c) for c in cols) - min(g(*c) for c in cols)
        if relief > rules["max_relief"]:
            bad.append("%s: %d blocks of relief under the apron (max %d)" % (pid, relief, rules["max_relief"]))
        for c in cols:
            if wb.get((c[0], ay, c[1])) != pal["apron"]:
                bad.append("%s: no apron at %s y%d (found %r)" % (pid, c, ay, wb.get((c[0], ay, c[1]))))
                break
            for y in range(g(*c) + 1, ay):
                if wb.get((c[0], y, c[1])) != pal["apron"]:
                    bad.append("%s: the footing under %s is open at y%d" % (pid, c, y))
                    break
        above = Counter(name_of(b) for (bx, by, bz), b in wb.items() if by > ay)
        # built by addition, not as a dict literal: a palette may give two roles the same block
        # (the owner's 2026-09-29 skins do), and duplicate keys in a literal silently keep the last
        want = Counter()
        want[name_of(pal["frame"])] += 9
        want[name_of(pal["sheet"])] += 9
        want[name_of(pal["lamp"])] += 2
        if above != want:
            bad.append("%s: the arch above the apron is %s, expected %s" % (pid, dict(above), dict(want)))
        for b in set(name_of(v) for v in wb.values()):
            if b in spawn_blocks:
                bad.append("%s writes %s in the world, which is a Cobblemon spawn condition (data/spawn_blocks.json)"
                           % (pid, b))
        world_cols[pid] = (min(c[0] for c in cols) - 1, min(c[1] for c in cols) - 1,
                           max(c[0] for c in cols) + 1, max(c[1] for c in cols) + 1)
        clicks = [e for e in went if e[0] == "minecraft:interaction"]
        if len(clicks) != 1 or "cobblers_portal_%s" % pid not in clicks[0][4]:
            bad.append("%s: its world function does not summon exactly one interaction tagged for it" % pid)
        elif not any("kill @e[type=minecraft:interaction,tag=cobblers_portal_%s]" % pid in l for l in read(wf)):
            bad.append("%s: its world function summons without killing a stale copy first" % pid)
        elif abs(clicks[0][2] - (ay + 1)) > 0.01:
            bad.append("%s: the click box stands at y%.1f, not on the apron at y%d" % (pid, clicks[0][2], ay + 1))

        # -- the gate and the water ------------------------------------------------------------------
        if gate == "sky" and x < rules["sky_min_x"]:
            bad.append("%s: a sky portal at x%d is west of the x%d line the owner set" % (pid, x, rules["sky_min_x"]))
        if gate == "dive":
            lev, polys = bodies.get(spec.get("water_body"), (None, []))
            if lev is None:
                bad.append("%s: water body %r has no authored level_y" % (pid, spec.get("water_body")))
            elif not polys:
                bad.append("%s: water body %r has no basin_polygons, so no water is painted in it at all"
                           % (pid, spec.get("water_body")))
            else:
                # every apron column, not just the centre: an apron half outside the basin is half dry
                outside = [c for c in cols if not any(in_polygon(p, c[0], c[1]) for p in polys)]
                if outside:
                    bad.append("%s: %d of its %d apron columns are outside %s's basin_polygons, where "
                               "tools/paint_maps.py paints no water; first %s"
                               % (pid, len(outside), len(cols), spec["water_body"], outside[0]))
                top = max(by for (_bx, by, _bz) in wb)
                if top > lev - rules["min_water_above"]:
                    bad.append("%s: its top block is y%d, only %d under the water at y%d (min %d)"
                               % (pid, top, lev - top, lev, rules["min_water_above"]))
                for c in cols:
                    if g(*c) > lev - rules["min_submersion"]:
                        bad.append("%s: the apron column %s is only %d under the water (min %d)"
                                   % (pid, c, lev - g(*c), rules["min_submersion"]))
                        break

        # -- the clearances --------------------------------------------------------------------------
        for t in towns:
            fp = t.get("footprint") or {}
            if not fp:
                continue
            d = math.hypot(max(fp["min_x"] - x, 0, x - fp["max_x"]), max(fp["min_z"] - z, 0, z - fp["max_z"]))
            if d < rules["min_from_town_footprint"][gate]:
                bad.append("%s: %.0f from %s's footprint (min %d)"
                           % (pid, d, t["id"], rules["min_from_town_footprint"][gate]))
        for q in places:
            pos = q.get("position") or {}
            if "x" in pos:
                d = math.hypot(pos["x"] - x, pos["z"] - z)
                if d < rules["min_from_placement"][gate]:
                    bad.append("%s: %.0f from the placement %s (min %d)"
                               % (pid, d, q["id"], rules["min_from_placement"][gate]))
        for e in legend:
            if e.get("mouth"):
                d = math.hypot(e["mouth"][0] - x, e["mouth"][1] - z)
                if d < rules["min_from_legendary_mouth"]:
                    bad.append("%s: %.0f from %s's mouth (min %d)"
                               % (pid, d, e["id"], rules["min_from_legendary_mouth"]))
        for other in doc["portals"]:
            if other["id"] <= pid:
                continue
            d = math.hypot(other["at"][0] - x, other["at"][1] - z)
            if d < rules["min_between_portals"]:
                bad.append("%s: %.0f from %s (min %d)" % (pid, d, other["id"], rules["min_between_portals"]))

        # -- the room --------------------------------------------------------------------------------
        band = pocket["bands"][gate]
        seq = [q["id"] for q in doc["portals"] if q["gate"] == gate].index(pid)
        cx, cz = pocket["origin_x"] + seq * pocket["spacing"], band
        rb, rent = replay(read(rf))
        h = kind["half"]
        rooms[pid] = (cx - h - 1, fy - 1, cz - h - 1, cx + h + 1, fy + kind["height"], cz + h + 1)
        if gate == "dive":
            for bx in range(cx - h - 1, cx + h + 2):       # a sealed shell: every boundary cell solid
                for by in range(fy - 1, fy + kind["height"] + 1):
                    for bz in range(cz - h - 1, cz + h + 2):
                        edge = (bx in (cx - h - 1, cx + h + 1) or bz in (cz - h - 1, cz + h + 1)
                                or by in (fy - 1, fy + kind["height"]))
                        got = rb.get((bx, by, bz))
                        if edge and (got is None or name_of(got) == "minecraft:air"):
                            bad.append("%s: its room leaks at (%d, %d, %d)" % (pid, bx, by, bz))
                            break
                    else:
                        continue
                    break
                else:
                    continue
                break
        else:
            for bx in range(cx - h - 1, cx + h + 2):       # a floor everywhere and a parapet two courses high
                for bz in range(cz - h - 1, cz + h + 2):
                    if rb.get((bx, fy - 1, bz)) is None:
                        bad.append("%s: its platform has a hole at (%d, %d)" % (pid, bx, bz))
                        break
                    rim = bx in (cx - h - 1, cx + h + 1) or bz in (cz - h - 1, cz + h + 1)
                    if rim and (rb.get((bx, fy, bz)) is None or rb.get((bx, fy + 1, bz)) is None):
                        bad.append("%s: its parapet is under two courses at (%d, %d)" % (pid, bx, bz))
                        break
                else:
                    continue
                break
        chests = [p for p, b in rb.items() if name_of(b) == "minecraft:chest"]
        if len(chests) != (1 if kind["chest"] else 0):
            bad.append("%s: %d chest(s) in a %s room" % (pid, len(chests), spec["room"]))
        for p, b in rb.items():
            if name_of(b) == "minecraft:chest" and 'LootTable:"%s:portals/%s"' % (NS, pid) not in b:
                bad.append("%s: its chest carries no loot table of its own" % pid)
        rtags = [e for e in rent if "cobblers_return_%s" % pid in e[4]]
        if len(rtags) != 1:
            bad.append("%s: its room does not summon exactly one return box" % pid)
        claims = [e for e in rent if "cobblers_claim_%s" % pid in e[4]]
        if len(claims) != (1 if kind["pedestal"] else 0):
            bad.append("%s: %d claim box(es) in a %s room" % (pid, len(claims), spec["room"]))

        # -- the crossing and the way back -----------------------------------------------------------
        enter = read(ef)
        tps = [TP.match(l.strip()) for l in enter]
        tps = [m for m in tps if m]
        if len(tps) != 1:
            bad.append("%s: its enter function does not teleport exactly once" % pid)
        else:
            d, tx, ty, tz = tps[0].group(1), float(tps[0].group(2)), float(tps[0].group(3)), float(tps[0].group(4))
            if d != dim:
                bad.append("%s: it crosses into %r, not %r" % (pid, d, dim))
            if not (cx - h < tx < cx + h + 1 and cz - h < tz < cz + h + 1 and ty == fy):
                bad.append("%s: it lands at (%.1f, %.1f, %.1f), outside its own room at (%d, %d)"
                           % (pid, tx, ty, tz, cx, cz))
            if rb.get((int(math.floor(tx)), int(ty), int(math.floor(tz)))) not in (None, "minecraft:air"):
                bad.append("%s: it lands inside a block it wrote" % pid)
        if not any(("execute unless entity @s[tag=%s] run return 0" % gt["tag"]) == l.strip() for l in enter):
            bad.append("%s: its enter function has no %s gate that stops the crossing" % (pid, gt["tag"]))
        if not any("scoreboard players set @s cobblers.portal %d" % index == l.strip() for l in enter):
            bad.append("%s: its enter function does not record portal %d for the rescue" % (pid, index))
        for other in doc["gates"]:
            if other != gate and any("cobblers.%s" % other in l for l in enter):
                bad.append("%s: its enter function names the %s gate as well as its own" % (pid, other))
        if not any(l.strip().startswith("advancement revoke @s only %s:portals/enter/%s" % (NS, pid)) for l in enter):
            bad.append("%s: its enter function never re-arms its click advancement: one crossing per player, ever" % pid)

        leave = read(lf)
        ltps = [m for m in (TP.match(l.strip()) for l in leave) if m]
        if len(ltps) != 1 or ltps[0].group(1) != "minecraft:overworld":
            bad.append("%s: its leave function does not teleport once into the overworld" % pid)
        else:
            lx, ly, lz = (float(ltps[0].group(i)) for i in (2, 3, 4))
            if abs(ly - (ay + 1)) > 0.01:
                bad.append("%s: it puts the player down at y%.1f, not on its apron at y%d" % (pid, ly, ay + 1))
            if not (x - 2.5 <= lx <= x + 3.5 and z - 2.5 <= lz <= z + 3.5):
                bad.append("%s: it puts the player down at (%.1f, %.1f), off its own apron" % (pid, lx, lz))
            if wb.get((int(math.floor(lx)), int(ly), int(math.floor(lz)))) is not None:
                bad.append("%s: it puts the player down inside the arch it built" % pid)
        if any(doc["gates"][q]["tag"] in l for q in doc["gates"] for l in leave):
            bad.append("%s: the way back is gated. It must never be" % pid)

        # -- the advancements and the loot ------------------------------------------------------------
        for what, tag in (("enter", "cobblers_portal_%s" % pid), ("leave", "cobblers_return_%s" % pid)):
            f = adir / what / ("%s.json" % pid)
            if not f.is_file():
                bad.append("%s: no %s advancement" % (pid, what))
                continue
            adv = json.loads(f.read_text(encoding="utf-8"))
            crit = ((adv.get("criteria") or {}).get("click") or {})
            if crit.get("trigger") != "minecraft:player_interacted_with_entity":
                bad.append("%s: the %s advancement is not a click trigger" % (pid, what))
            if tag not in json.dumps(crit):
                bad.append("%s: the %s advancement listens for the wrong tag" % (pid, what))
            if (adv.get("rewards") or {}).get("function") != "%s:portals/%s/%s" % (NS, what, pid):
                bad.append("%s: the %s advancement rewards the wrong function" % (pid, what))
        if kind["pedestal"]:
            cf = fdir / "claim" / ("%s.mcfunction" % pid)
            ca = adir / "claim" / ("%s.json" % pid)
            if not cf.is_file() or not ca.is_file():
                bad.append("%s: the meaningful room has no once-per-player claim" % pid)
            elif any("advancement revoke" in l for l in read(cf)):
                bad.append("%s: its claim re-arms itself, so the reward is not once per player" % pid)
        if spec.get("loot"):
            lt = ldir / ("%s.json" % pid)
            if not lt.is_file():
                bad.append("%s: no loot table" % pid)
            else:
                got = json.loads(lt.read_text(encoding="utf-8"))
                names = [e["name"] for p in got["pools"] for e in p["entries"]]
                if names != [i["item"] for i in doc["loot"]["tables"][spec["loot"]]]:
                    bad.append("%s: its loot table is not the one data/portals.json names" % pid)

    # ---- the owner's rule, the rescue, the drivers ---------------------------------------------------
    n = rules["meaningful_per"]
    for gate, count in sorted(per_gate.items()):
        want = count // n
        got = sum(1 for p in doc["portals"] if p["gate"] == gate and p["meaningful"])
        if count % n or got != want:
            bad.append("gate %s: %d meaningful of %d, the owner's rule is one in %d" % (gate, got, count, n))
    rescue = read(fdir / "rescue.mcfunction") if (fdir / "rescue.mcfunction").is_file() else []
    for index, spec in enumerate(doc["portals"], start=1):
        want = ("execute if score @s cobblers.portal matches %d run function %s:portals/leave/%s"
                % (index, NS, spec["id"]))
        if not any(want == l.strip() for l in rescue):
            bad.append("the rescue does not put portal %d's travellers back at %s" % (index, spec["id"]))
    if not any("unless score @s cobblers.portal matches 1.." in l for l in rescue):
        bad.append("the rescue has no fallback for a player who never crossed a portal")
    load = read(fdir / "load.mcfunction") if (fdir / "load.mcfunction").is_file() else []
    if not any("scoreboard objectives add cobblers.portal dummy" == l.strip() for l in load):
        bad.append("the load function never creates the cobblers.portal objective")
    for driver in ("tick", "gate"):
        if not any("schedule function %s:portals/%s" % (NS, driver) in l for l in load):
            bad.append("the load function never starts %s" % driver)
        f = fdir / ("%s.mcfunction" % driver)
        if not f.is_file() or not any("schedule function %s:portals/%s" % (NS, driver) in l for l in read(f)):
            bad.append("%s does not reschedule itself: it would run once and stop" % driver)
    tick = read(fdir / "tick.mcfunction") if (fdir / "tick.mcfunction").is_file() else []
    if not any(("execute in %s as @a[x=" % dim) in l for l in tick):
        bad.append("the rescue sweep is not anchored in the pocket dimension by an absolute box (EXP-047)")
    gatef = read(fdir / "gate.mcfunction") if (fdir / "gate.mcfunction").is_file() else []
    sky = doc["gates"]["sky"]
    if not any(sky["advancement"] in l and sky["tag"] in l for l in gatef):
        bad.append("the sky tag is not granted off %s" % sky["advancement"])
    for f in PACK.rglob("*.mcfunction"):
        for line in read(f):
            if line.strip().startswith("#"):
                continue
            if "grant_dive" in line or "tag @s add cobblers.dive" in line:
                bad.append("%s touches the dive gate. cobblers.dive is blackout_pack's and this pack only reads it"
                           % f.name)
    tagf = PACK / "data" / "minecraft" / "tags" / "function" / "load.json"
    if not tagf.is_file() or "%s:portals/load" % NS not in tagf.read_text(encoding="utf-8"):
        bad.append("the pack is not in the minecraft:load tag, so nothing ever starts it")

    # ---- the rooms do not overlap, and nothing else in the build is near a portal --------------------
    ids = sorted(rooms)
    for i, p in enumerate(ids):
        for q in ids[i + 1:]:
            a1, b1 = rooms[p], rooms[q]
            if all(a1[k] <= b1[k + 3] and b1[k] <= a1[k + 3] for k in range(3)):
                bad.append("the rooms of %s and %s overlap" % (p, q))
    packs = Path(a.packs)
    if not packs.is_dir():
        bad.append("no %s: the cross-pack check cannot run" % packs)
    else:
        boxes = list(world_cols.items())
        gx0 = min(b[0] for _p, b in boxes) if boxes else 0
        gx1 = max(b[2] for _p, b in boxes) if boxes else 0
        gz0 = min(b[1] for _p, b in boxes) if boxes else 0
        gz1 = max(b[3] for _p, b in boxes) if boxes else 0
        for f in packs.rglob("*.mcfunction"):
            if PACK in f.parents:
                continue
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                m = ANYWRITE.search(line)
                if not m:
                    continue
                v = [int(q) for q in m.groups() if q is not None]
                x0, z0 = v[0], v[2]
                x1, z1 = (v[3], v[5]) if len(v) == 6 else (x0, z0)
                if max(x0, x1) < gx0 or min(x0, x1) > gx1 or max(z0, z1) < gz0 or min(z0, z1) > gz1:
                    continue
                for pid, (bx0, bz0, bx1, bz1) in boxes:
                    if min(x0, x1) <= bx1 and max(x0, x1) >= bx0 and min(z0, z1) <= bz1 and max(z0, z1) >= bz0:
                        bad.append("%s writes into %s's columns (%s)" % (f.name, pid, line.strip()[:60]))
    return bad


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=env_source_root())
    p.add_argument("--packs", default=str(ROOT / "build" / "datapacks"))
    a = p.parse_args(argv)
    bad = audit(a)
    if bad:
        print("PROBLEM: %d" % len(bad))
        for b in bad[:60]:
            print("  " + b)
        return 1
    print("portals audit CLEAN: %d portals, the pocket dimension, the gates and the rescue"
          % len(json.loads(DATA.read_text(encoding="utf-8"))["portals"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
