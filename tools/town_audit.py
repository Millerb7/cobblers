#!/usr/bin/env python
"""After a town is built: does the world hold what the plan says, and does any block in it decide spawns?

Two checks on the result, never on the commands, because a function swallows its commands' output:

  plan       roads present where the plan puts them and paved with the planned block at the planned level,
             nothing standing on them, every lamp lit, every building standing (95% of its template's blocks
             where the template puts them) and no ground inside its rooms. See plan_audit().
  spawns     the block policy, below.


The policy check in tools/validate_data.py reads templates. This reads the world, which is the only
thing that catches what a template does not say: a jigsaw that resolved into a substituted block, a
donor placed by resource id whose substitution fills were refused, a path laid in the wrong material,
or anything a later hand-edit put there. Misty's gym kept 958 blocks of vanilla concrete through a
clean template check, because the fills that should have replaced them were over the /fill limit and
the server refused them in silence.

A block is a problem here when it is named by a Cobblemon spawn condition (data/spawn_blocks.json),
is not whitelisted in data/spawn_block_policy.json, and is the `from` side of a substitution that was
supposed to have removed it. Whitelisted blocks are reported as a count, not an error: a town is
allowed beds and flowers, and seeing how many is useful.

  python tools/town_audit.py gym1_town --world <stopped world copy>
  python tools/town_audit.py --all --world <stopped world copy>

Ownership: read-only. It never writes to the world and never touches the live save.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def policy_sets(policy, triggers):
    """(blocks that must not appear, blocks that are allowed on purpose)."""
    substituted_from = {s["from"] for s in policy.get("substitutions") or [] if isinstance(s, dict)}
    allowed = set()
    for w in policy.get("whitelist") or []:
        allowed |= set(w.get("blocks") or [])
    return substituted_from, allowed


def town_bounds(settlement, placements, margin=8):
    """The ground a town occupies: every placement, street and plaza it records."""
    s = placements["settlements"][settlement]
    plan = s.get("plan") or {}
    xs, zs = [], []
    for q in placements["placements"]:
        if q.get("settlement") != settlement or not q.get("position"):
            continue
        pos = q["position"]
        size = q.get("size") or [24, 0, 24]
        xs += [pos["x"], pos["x"] + size[0]]
        zs += [pos["z"], pos["z"] + size[2]]
    for street in plan.get("streets") or []:
        for x, z in street.get("polyline") or []:
            xs.append(x)
            zs.append(z)
    for r in s.get("roads") or []:
        for x, z in r.get("polyline") or []:
            xs.append(x)
            zs.append(z)
    pz = plan.get("plaza")
    if pz and (pz.get("rect") or pz.get("box")):
        rect = pz.get("rect") or pz["box"]
        xs += [rect[0], rect[2]]
        zs += [rect[1], rect[3]]
    if not xs:
        raise SystemExit("%s: nothing placed and no streets, so there is nothing to audit" % settlement)
    return min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin


def town_y_range(settlement, placements, pad_below=4, pad_above=8):
    """The vertical slice the town occupies.

    Scanning the whole column reads the ore and lava the world generated under the town, which is not
    the town's doing and drowns the finding that is. The slice runs from a little under the lowest
    floor to a little over the tallest roof.
    """
    floors, tops = [], []
    rep = ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)
    if rep.is_file():
        for b in json.loads(rep.read_text(encoding="utf-8")).get("buildings") or []:
            if b.get("floor_y") is not None:
                floors.append(b["floor_y"])
                tops.append(b["floor_y"] + 24)
    for q in placements["placements"]:
        if q.get("settlement") != settlement:
            continue
        y = (q.get("position") or {}).get("y")
        if y is not None:
            floors.append(y)
            tops.append(y + (q.get("size") or [0, 24, 0])[1])
    plan = (placements["settlements"][settlement].get("plan") or {})
    for a in plan.get("anchors") or []:
        for v in (a.get("ground_range") or []):
            floors.append(int(v))
            tops.append(int(v) + 24)
    if (plan.get("plaza") or {}).get("y") is not None:
        floors.append(plan["plaza"]["y"])
        tops.append(plan["plaza"]["y"] + 8)
    if not floors:
        return -64, 200
    return min(floors) - pad_below, max(tops) + pad_above


def audit(settlement, world, y_range=None, server_dir=None):
    import structure_nbt as SN
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    blocks_doc = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))
    triggers = set(blocks_doc.get("blocks") or blocks_doc)
    must_not, allowed = policy_sets(policy, triggers)

    x0, z0, x1, z1 = town_bounds(settlement, placements)
    y_range = y_range or town_y_range(settlement, placements)
    cap = SN.capture(world, (x0, y_range[0], z0), (x1, y_range[1], z1))

    # A block inside a footprint we placed is ours and has to answer for itself. One outside is the
    # site: the coal and iron under a town are the world's, not the builder's, and reporting them as
    # findings buries the ones that matter.
    # the boxes are three-dimensional on purpose: a building's footprint in plan also covers the
    # ground under it, and the coal seam a town happens to stand on is not something the builder put
    # there. Each box runs from its floor to its roof, with a couple of blocks of foundation below.
    floors = {}
    rep = ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)
    if rep.is_file():
        for b in json.loads(rep.read_text(encoding="utf-8")).get("buildings") or []:
            if b.get("floor_y") is not None:
                floors[b["id"]] = b["floor_y"]
    ours = []
    for q in placements["placements"]:
        if q.get("settlement") != settlement or not q.get("position"):
            continue
        pos, size = q["position"], q.get("size") or [28, 24, 28]
        base = pos.get("y", floors.get(q["id"]))
        if base is None:
            base = y_range[0] + 4
        # from the floor up, not from the foundations down: the ore behind a foundation course is
        # the ground the town was built on, and the builder did not choose it
        ours.append((pos["x"], pos["x"] + size[0] - 1, base, base + size[1] - 1,
                     pos["z"], pos["z"] + size[2] - 1))

    # where a placement's template is known, "ours" is exactly what it writes. A house record has no size, and the
    # 28-block box it defaulted to took in 4,408 blocks of the Tableland plateau's own red sand as if we had put it
    # there. A placement whose template cannot be read here (a donor without --server-dir) keeps its box.
    known, written = set(), set()
    for bid, solid, rooms, _ in expected_buildings(settlement, placements, server_dir):
        if solid is not None:
            known.add(bid)
            written |= set(solid) | set(rooms)
    mine = [q for q in placements["placements"] if q.get("settlement") == settlement and q.get("position")]
    boxed = [box for q, box in zip(mine, ours) if q["id"] not in known]

    def placed(x, y, z):
        if (x, y, z) in written:
            return True
        return any(a <= x <= b and c <= y <= d and e <= z <= f for a, b, c, d, e, f in boxed)

    inside, outside = Counter(), Counter()
    for (x, y, z), v in cap.blocks.items():
        name = v[0]
        if name in triggers:
            (inside if placed(x, y, z) else outside)[name] += 1
    unsubstituted = {b: n for b, n in inside.items() if b in must_not}
    unlisted = {b: n for b, n in inside.items() if b not in allowed and b not in must_not}
    listed = {b: n for b, n in inside.items() if b in allowed}
    return {"settlement": settlement, "bounds": [x0, z0, x1, z1], "y_range": list(y_range),
            "blocks_read": len(cap.blocks), "placed_footprints": len(ours),
            "unsubstituted": dict(sorted(unsubstituted.items())),
            "not_in_policy": dict(sorted(unlisted.items())),
            "whitelisted_present": dict(sorted(listed.items())),
            "in_the_ground_around_it": dict(sorted(outside.items()))}


# ----------------------------------------------------------------------------- the plan against the world
#
# A generated function reports nothing: a refused /fill, a street laid a block off, a house that never landed all
# look like success from the outside. So the town is checked by its result. The plan (derived/towns/<town>_plan.json,
# written by tools/town_plan.py) says which cell of which street is paved with what at which height and where each
# lamp is; the placement report (derived/towns/<town>_placement.json, written by tools/place_town.py) says which
# template landed where and turned which way. Each is compared with the blocks the world holds.

STANDING = 0.95        # a building stands when this share of its template's blocks is where the template puts them
NATURAL_GROUND = {"minecraft:dirt", "minecraft:grass_block", "minecraft:coarse_dirt", "minecraft:podzol",
                  "minecraft:rooted_dirt", "minecraft:stone", "minecraft:andesite", "minecraft:diorite",
                  "minecraft:granite", "minecraft:deepslate", "minecraft:tuff", "minecraft:gravel", "minecraft:sand",
                  "minecraft:red_sand", "minecraft:clay", "minecraft:mud", "minecraft:water", "minecraft:lava"}
PASSABLE_SUFFIXES = ("_carpet", "_pressure_plate", "_button", "torch", "_sapling", "_flower", "grass", "fern",
                     "_petals", "leaf_litter", "snow", "_rail", "rail", "_sign")
NOT_A_BLOCK = {"minecraft:air", "minecraft:cave_air", "minecraft:structure_void"}


def _rotate(x, z, rot):
    return {"none": (x, z), "clockwise_90": (-z, x), "180": (-x, -z), "counterclockwise_90": (z, -x)}[rot]


def expected_paving(plan):
    """{(x, z): (y, block, what)} in the order the prep function writes them: streets, then the plaza, then lamps.
    A later write wins, as it does in the world."""
    out = {}
    for sid, st in (plan.get("streets") or {}).items():
        for z, y, x0, x1 in st.get("cells") or []:
            for x in range(x0, x1 + 1):
                out[(x, z)] = (y, st["surface"], sid)
    pz = plan.get("plaza")
    if pz:
        x0, z0, x1, z1 = pz["rect"]
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                out[(x, z)] = (pz["y"], pz["surface"], "plaza")
    return out


def _command_columns(lines):
    """Every (x, z) a list of fill and setblock commands writes."""
    import re
    out = set()
    for l in lines:
        m = re.match(r"(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))?", l.strip())
        if not m:
            continue
        x0, z0 = int(m.group(2)), int(m.group(4))
        x1, z1 = (int(m.group(5)), int(m.group(7))) if m.group(5) else (x0, z0)
        out |= {(x, z) for x in range(min(x0, x1), max(x0, x1) + 1) for z in range(min(z0, z1), max(z0, z1) + 1)}
    return out


def expected_buildings(settlement, placements, server_dir=None):
    """[(id, {(x, y, z): block name}, {(x, y, z) of the template's rooms: air}, note)] for every building the town
    records: houses and services from the placement report and their local templates, donors from the installed
    pack (when a server directory is given)."""
    import nbt
    rep_path = ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)
    rep = json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.is_file() else {"buildings": []}
    by_id = {q["id"]: q for q in placements["placements"] if q.get("settlement") == settlement}
    out = []

    def expand(bid, doc, origin, rot, grade):
        pal = doc["palette"]
        solid, rooms = {}, {}
        ox, oy, oz = origin
        for b in doc["blocks"]:
            tx, ty, tz = b["pos"]
            p = pal[b["state"]]
            name = p["Name"]
            if name == "minecraft:jigsaw":
                name = (b.get("nbt") or {}).get("final_state") or "minecraft:air"
                name = name.split("[")[0].split("{")[0]
            if name.startswith("waystones:") or name == "minecraft:structure_void":
                continue
            rx, rz = _rotate(tx, tz, rot)
            pos = (ox + rx, oy + ty, oz + rz)
            if name in ("minecraft:air", "minecraft:cave_air"):
                if ty > grade:
                    rooms[pos] = name
            else:
                solid[pos] = name
        out.append((bid, solid, rooms, None))

    for b in rep.get("buildings") or []:
        q = by_id.get(b["id"])
        if not q or not q.get("file"):
            continue
        # the template the server was given: a stripped or dried copy when place_town rewrote it
        placed = b.get("template_placed") or q["template"]
        src = ROOT / q["file"]
        if placed != q["template"]:
            ns, rel = placed.split(":", 1)
            src = ROOT / "build" / "datapacks" / "cobblers_towns" / "data" / ns / "structure" / (rel + ".nbt")
        _, doc = nbt.load(src)
        expand(b["id"], doc, tuple(b["command_position"]), b["rotation"], b["grade_layer"])
    for q in by_id.values():
        if q.get("kind") == "earthwork":
            # the authored commands, replayed: what they write is what should stand
            import build_audit
            import function_limits
            cols = {(x, z) for (x, z) in _command_columns(q.get("commands") or [])}
            col = build_audit.replay(q.get("commands") or [], sorted(cols))
            solid = {(x, y, z): b for (x, z), ys in col.items() for y, b in ys.items() if b not in ("minecraft:air",)}
            out.append((q["id"], solid, {}, None))
            continue
        if q.get("file") or not q.get("pack_template") or q.get("kind") == "vendor":
            continue
        if not server_dir:
            out.append((q["id"], None, None, "a pack donor: pass --server-dir to read its template from the installed pack"))
            continue
        import place_donor
        _, doc = place_donor.load_template(server_dir, q["pack_template"])
        pos = q["position"]
        # a donor whose ground layer is not its lowest (a bca building stands on two to five layers of its own
        # terrain) records it, so the air below that layer is not read as rooms with ground in them
        expand(q["id"], doc, (pos["x"], pos["y"], pos["z"]), q.get("rotation", "none"), int(q.get("grade_layer", 0)))
        # the record's own substitutions and removals are what should stand, not the template's blocks
        own = {s["from"]: s["to"] for s in place_donor.own_substitutions(q)}
        own.update({b: "minecraft:air" for b in q.get("remove_blocks") or []})
        if own:
            bid, solid, rooms, note = out.pop()
            for p, n in list(solid.items()):
                if n in own:
                    if own[n] == "minecraft:air":
                        del solid[p]
                    else:
                        solid[p] = own[n]
            out.append((bid, solid, rooms, note))
    return out


def town_functions(settlement):
    """The functions that build a place, in the order the re-application runs them: its prep, its town function, its
    after-donor function (when it has one)."""
    fdir = ROOT / "build" / "datapacks" / "cobblers_towns" / "data" / "cobblers" / "function" / "towns"
    out = [ROOT / "build" / "town_prep" / ("prep_%s.mcfunction" % settlement), fdir / ("%s.mcfunction" % settlement)]
    late = fdir / ("%s_after_donors.mcfunction" % settlement)
    return out + ([late] if late.is_file() else [])


_WRITE = None


def stray_paving_writes(settlement, plan, placements):
    """([(file, line)], problem or None): every write in the place's own functions of a block the plan paves with, at a
    column the plan does not pave. Deterministic, cell by cell against the plan's road and plaza cells, with a
    building's footprint (and a block round it), an anchor the plan paves on purpose and an authored earthwork's
    columns allowed. It replaces a density heuristic that compared the ring round the plaza with the landscape
    further out and gave up ("not checkable") wherever the landscape was the plaza's own stone (Codex review,
    2026-09-21). Stray paving in a world can only come from these functions, so checking them is checking for it."""
    import re
    global _WRITE
    _WRITE = _WRITE or re.compile(r"(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")
    paving = expected_paving(plan)
    if not paving:
        return [], "the plan paves no cell: nothing to check the town's paving against"
    surfaces = {v[1] for v in paving.values()}
    allowed = set(paving)
    for a in plan.get("anchors") or []:
        if a.get("surface"):
            x0, z0, x1, z1 = a["rect"]
            allowed |= {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    for q in placements["placements"]:
        if q.get("settlement") == settlement and q.get("kind") == "earthwork":
            allowed |= _command_columns(q.get("commands") or [])
    rep_path = ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)
    if rep_path.is_file():
        for b in json.loads(rep_path.read_text(encoding="utf-8")).get("buildings") or []:
            x0, z0, x1, z1 = b["footprint"]
            allowed |= {(x, z) for x in range(x0 - 1, x1 + 2) for z in range(z0 - 1, z1 + 2)}
    stray = []
    for f in town_functions(settlement):
        if not f.is_file():
            return [], "%s is missing: the town's functions were not generated, so its paving cannot be checked" % f.name
        for line in f.read_text(encoding="utf-8").splitlines():
            m = _WRITE.match(line.strip())
            if not m or m.group(8).split("[")[0].split("{")[0] not in surfaces:
                continue
            x0, z0 = int(m.group(2)), int(m.group(4))
            x1, z1 = (int(m.group(5)), int(m.group(7))) if m.group(5) else (x0, z0)
            if any((x, z) not in allowed for x in range(min(x0, x1), max(x0, x1) + 1)
                   for z in range(min(z0, z1), max(z0, z1) + 1)):
                stray.append((f.name, line.strip()))
    return stray, None


def expected_building_ids(settlement, placements):
    """The buildings the data says the place has: every house, service, donor and earthwork record (not vendors)."""
    return {q["id"] for q in placements["placements"]
            if q.get("settlement") == settlement and q.get("kind") != "vendor"
            and (q.get("file") or q.get("pack_template") or q.get("kind") == "earthwork")}


def plan_audit(settlement, world, server_dir=None):
    """Roads where the plan puts them, paved with the right block; lamps lit at their spots; every building
    standing and none of them buried. Returns a result dict with a "problems" list of sentences."""
    import structure_nbt as SN
    plan_path = ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)
    if not plan_path.is_file():
        # fail closed: a place with no plan has nothing checked, which is not a pass
        msg = "no plan: %s has not been run through tools/town_plan.py" % settlement
        return {"skipped": msg, "problems": [msg], "not_checkable": []}
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    # grass under a block turns to dirt by itself, and farmland dries back to dirt: Brock's animal pen had lost 21
    # grass blocks that way over a few hours, which is not the building failing to stand
    same = {"minecraft:grass_block": {"minecraft:dirt"}, "minecraft:farmland": {"minecraft:dirt"},
            # a dirt path with a block on it reverts to dirt (Sabrina's two large farms, 24 blocks)
            "minecraft:dirt_path": {"minecraft:dirt"}}
    for s in policy.get("substitutions") or []:
        same.setdefault(s["from"], set()).add(s["to"])
        same.setdefault(s["to"], set()).add(s["from"])
    paving = expected_paving(plan)
    lamps = [tuple(L["at"]) for L in plan.get("lamps") or []]
    lamp_block = plan.get("lamp_block")
    buildings = expected_buildings(settlement, placements, server_dir)
    if not any(st.get("cells") for st in (plan.get("streets") or {}).values()):
        msg = "the plan predates recorded street cells; re-run tools/town_plan.py"
        return {"skipped": msg, "problems": [msg], "not_checkable": []}

    xs = [k[0] for k in paving] + [p[0] for _, s, r, _ in buildings if s for p in list(s) + list(r)]
    zs = [k[1] for k in paving] + [p[2] for _, s, r, _ in buildings if s for p in list(s) + list(r)]
    ys = [v[0] for v in paving.values()] + [p[1] for _, s, r, _ in buildings if s for p in list(s) + list(r)]
    if plan.get("plaza"):                        # the ring the stray-paving check reads
        r = plan["plaza"]["rect"]
        xs += [r[0] - 40, r[2] + 40]
        zs += [r[1] - 40, r[3] + 40]
        ys += [plan["plaza"]["y"] - 3, plan["plaza"]["y"] + 3]
    cap = SN.capture(world, (min(xs), min(ys) - 2, min(zs)), (max(xs), max(ys) + 3, max(zs)))
    at = lambda x, y, z: cap.blocks.get((x, y, z), ("minecraft:air",))[0]
    problems = []
    unchecked = []                                       # checks that could not run here, said so rather than passed

    # roads and the plaza
    lamp_cells = {(x, z) for x, _, z in lamps}
    # A cell an authored earthwork covers is where that earthwork was meant to stand: the summit cairn on the
    # Displaced City's square, a stair's foot. It is checked as part of the earthwork, not as road. Only the
    # columns an earthwork writes at or above the paving level count; one that only digs below does not hide a cell.
    earth_ids = {q["id"] for q in placements["placements"] if q.get("settlement") == settlement and q.get("kind") == "earthwork"}
    covered = {}
    for bid, solid, _, _ in buildings:
        if bid in earth_ids and solid:
            for (x, y, z) in solid:
                covered[(x, z)] = max(covered.get((x, z), y), y)
    exempt = {c for c, (y, _, _) in paving.items() if any(covered.get(c, -10 ** 6) >= y + d for d in (0, 1))}
    roads = {}
    for (x, z), (y, block, what) in paving.items():
        if (x, z) in lamp_cells or (x, z) in exempt:
            continue
        r = roads.setdefault(what, {"cells": 0, "paved": 0, "off_level": 0, "wrong": Counter(), "blocked_above": Counter()})
        r["cells"] += 1
        got = at(x, y, z)
        if got == block or got in same.get(block, ()):
            r["paved"] += 1
        elif block in (at(x, y - 1, z), at(x, y + 1, z)):
            r["off_level"] += 1
        else:
            r["wrong"][got] += 1
        above = at(x, y + 1, z)
        if above not in NOT_A_BLOCK and above != block and not above.endswith(PASSABLE_SUFFIXES) \
                and not above.startswith("waystones:"):
            r["blocked_above"][above] += 1
    for what, r in sorted(roads.items()):
        bad = r["cells"] - r["paved"]
        if bad:
            problems.append("%s: %d of %d cells not paved as planned (%d a block off level; found instead: %s)"
                            % (what, bad, r["cells"], r["off_level"],
                               ", ".join("%s %d" % (k.split(":")[-1], n) for k, n in r["wrong"].most_common(4)) or "-"))
        if r["blocked_above"]:
            problems.append("%s: %d cells have a block standing on the road (%s)"
                            % (what, sum(r["blocked_above"].values()),
                               ", ".join("%s %d" % (k.split(":")[-1], n) for k, n in r["blocked_above"].most_common(4))))

    # paving where the plan puts none, cell by cell: every write of a planned paving block in the place's own
    # functions must land on a planned road or plaza cell (or a building, a paved anchor, an earthwork). The world
    # side (each planned cell paved) is checked above; stray paving can only come from these writes.
    stray, why_not = stray_paving_writes(settlement, plan, placements)
    if why_not:
        problems.append("paving: %s" % why_not)
    elif stray:
        problems.append("paving outside the plan: %d writes of a paving block land off the plan's road cells (first: %s)"
                        % (len(stray), "; ".join("%s: %s" % s for s in stray[:3])))
    if not roads or not sum(r["cells"] for r in roads.values()):
        problems.append("roads: no planned road cell was checked")
    # every building the data records is checked, or the audit says which were not
    checked = {r["id"] for r in [{"id": b[0]} for b in buildings if b[1] is not None]}
    missing = sorted(expected_building_ids(settlement, placements) - checked)
    if missing:
        problems.append("buildings the data records but the audit did not check: %s" % ", ".join(missing[:8]))

    # lamps
    dark =[(x, y - 1, z, at(x, y - 1, z)) for x, y, z in lamps if at(x, y - 1, z) != lamp_block]
    if lamps and dark:
        problems.append("lamps: %d of %d spots are not lit with %s (first: %s)"
                        % (len(dark), len(lamps), lamp_block, "; ".join("%d %d %d holds %s" % d for d in dark[:3])))

    # buildings
    rows = []
    for bid, solid, rooms, note in buildings:
        if solid is None:
            rows.append({"id": bid, "skipped": note})
            continue
        present = sum(1 for p, n in solid.items() if at(*p) == n or at(*p) in same.get(n, ()))
        buried = Counter(at(*p) for p in rooms if at(*p) in NATURAL_GROUND)
        share = present / max(1, len(solid))
        rows.append({"id": bid, "template_blocks": len(solid), "present": present, "share": round(share, 4),
                     "ground_in_rooms": dict(buried)})
        if share < STANDING:
            problems.append("%s: only %d of %d template blocks are in place (%.1f%%); it is not standing as placed"
                            % (bid, present, len(solid), 100 * share))
        if buried:
            problems.append("%s: ground inside its rooms (%s)" % (bid, ", ".join("%s %d" % (k.split(":")[-1], n)
                                                                               for k, n in buried.most_common(4))))
    return {"roads": {k: dict(v, wrong=dict(v["wrong"]), blocked_above=dict(v["blocked_above"])) for k, v in roads.items()},
            "lamps": {"spots": len(lamps), "lit": len(lamps) - len(dark), "block": lamp_block},
            "buildings": rows, "problems": problems, "not_checkable": unchecked}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("settlement", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--world", required=True, help="a STOPPED world copy; never the live save")
    p.add_argument("--server-dir", default=None, help="the server whose packs hold donor templates, so donor "
                   "buildings are checked too; without it they are reported as not checked")
    p.add_argument("--json", action="store_true", dest="as_json")
    a = p.parse_args(argv)
    if "cobblers-10240" in Path(a.world).as_posix():
        raise SystemExit("refusing to read the live world")
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    names = sorted(placements["settlements"]) if a.all else [a.settlement]
    if not names or names == [None]:
        raise SystemExit("name a settlement or pass --all")
    bad = 0
    out = []
    for name in names:
        try:
            res = audit(name, a.world, server_dir=a.server_dir)
        except SystemExit as exc:
            # fail closed: a place the audit could not read is not clean
            print("%-12s NOT AUDITED: %s" % (name, exc))
            bad += 1
            continue
        res["plan"] = plan_audit(name, a.world, a.server_dir)
        out.append(res)
        problems = len(res["unsubstituted"]) + len(res["not_in_policy"])
        # a check that could not run blocks a clean result as surely as one that failed
        bad += problems + len(res["plan"]["problems"]) + len(res["plan"].get("not_checkable") or [])
        if a.as_json:
            continue
        pl = res["plan"]
        if pl.get("skipped"):
            print("   plan against world: SKIPPED, %s" % pl["skipped"])
        else:
            for what, r in sorted(pl["roads"].items()):
                print("   %-14s %4d of %4d cells paved as planned" % (what, r["paved"], r["cells"]))
            print("   lamps          %4d of %4d lit (%s)" % (pl["lamps"]["lit"], pl["lamps"]["spots"], pl["lamps"]["block"]))
            for row in pl["buildings"]:
                if row.get("skipped"):
                    print("   %-22s not checked: %s" % (row["id"], row["skipped"]))
                else:
                    print("   %-22s %5d of %5d template blocks in place (%.1f%%)%s"
                          % (row["id"], row["present"], row["template_blocks"], 100 * row["share"],
                             "  GROUND IN ROOMS %s" % row["ground_in_rooms"] if row["ground_in_rooms"] else ""))
            for msg in pl["problems"]:
                print("   PLAN MISMATCH  %s" % msg)
            for msg in pl.get("not_checkable") or []:
                print("   NOT CHECKABLE  %s" % msg)
        print("%-12s %s blocks read in %s, y %d to %d"
              % (name, format(res["blocks_read"], ","), res["bounds"], res["y_range"][0], res["y_range"][1]))
        for b, n in res["unsubstituted"].items():
            print("   UNSUBSTITUTED %-44s %d  (a substitution was supposed to remove this)" % (b, n))
        for b, n in res["not_in_policy"].items():
            print("   NOT IN POLICY %-44s %d  (decides spawns and nothing says it may)" % (b, n))
        if res["whitelisted_present"]:
            print("   allowed on purpose: %s"
                  % ", ".join("%s %d" % (b.split(":")[-1], n) for b, n in res["whitelisted_present"].items()))
        if res["in_the_ground_around_it"]:
            top = sorted(res["in_the_ground_around_it"].items(), key=lambda kv: -kv[1])[:5]
            print("   in the ground around it, not ours: %s"
                  % ", ".join("%s %d" % (b.split(":")[-1], n) for b, n in top))
        if not problems:
            print("   spawn blocks clean: nothing inside a footprint we placed decides a spawn without saying so")
        if not pl.get("skipped") and not pl["problems"] and not pl.get("not_checkable"):
            print("   plan clean: every road cell, lamp and building is where the plan puts it")
    if a.as_json:
        print(json.dumps(out, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
