#!/usr/bin/env python
"""Coldwater Station: a small research station on marsh country's east coast whose researchers study a sealed dive arch.

The owner, 2026-10-05: "make a research station at 6050 1843 ish looking for some other legendary (is kyogre
planned?) and have a ferry guy to take you to the snowy island across the water"; then: "for the kyogre research,
make them looking at a dive portal underwater, that will later tp the player to a kyogre cave". So the station studies
KYOGRE, through a dive arch on the sea floor 130 blocks off its deck. The arch is SEALED: it is built, clickable and
gated like every dive portal, and its destination is a stub that says the way is shut (data/coldwater_station.json
portal.hook says what attaches the cave later). It is a LEAD: talk, a telescope on the arch's buoy, a theodolite on
the Pine Isles boat, and field notes. It sets no state but each researcher's dialogue cursor, gives nothing and
promises nothing.

WHY THE ARCH IS NOT IN data/portals.json: tools/portals.py cannot hold an inactive portal. load() requires each
gate's portal count to be a multiple of six with one vault in each six (the owner's "1 in 6 meaningful"), rooms are
indexed per gate on that count, and every portal crosses into a built room. A seventh dive portal fails the first
rule, and a sealed one has no room. So the arch is built here with portals.py's own functions CALLED (world_blocks,
apron_columns, clearances, commands, summon, click_advancement) and its own data read (palette, rules, the dive
gate), and its siting is checked against portals.py's rules and the twelve portals.

Nothing here is new machinery. It is the Frostpeak research camp's pattern, with that camp's pieces CALLED, not
copied (tools/frostpeak_camp.py: the tent, deck, fire ring, supply cache and weather mast; seat(); the exact
line-of-sight walk clear_above(); the block_display quaternion; the wall sign), plus one piece of its own, a cabin.
The researchers' conversations are compiled in memory by tools/compile_dialogue.py's compile_conversation, as the
camp's are; their cursor fields are declared in data/progression.json. NPC classes load only at server start, so the
pack is installed before boot and the NPCs placed over RCON by tools/reapply.py's "npc" action (R18CW).

The ferry is NOT here. The station's jetty is a record in data/ferry_docks.json (tools/ferry_docks.py, R16H) and its
ferryman a dock in data/ferries.json on the line coldwater_crossing (tools/ferries.py, R17F). This tool reads that
dock to keep clear of it and the line to quote its fare and gate.

Every Y comes from tools/ground.py (the canonical heightmap, rounded), never a world. The builder's guards below
(rules in data/coldwater_station.json) fail the build; they are not an audit (data/coldwater_station.json
audit_checklist is the brief for the independent one).

  python tools/coldwater_station.py build [--source-root R] [--out DIR]   write the pack and derived/coldwater_station/
  python tools/coldwater_station.py plan  [--source-root R]               print the numbers and the probes; writes nothing

The functions, after the pack is installed and the server restarted (R18CW):
  cobblers:coldwater_station/build         the blocks (force-loads its own chunks)
  cobblers:coldwater_station/instruments   kills this station's display entities near the deck, summons the two tubes
  cobblers:coldwater_station/portal/build  the sealed arch, its buoy and its click box (force-loads its own chunks)
and then the three researchers from npc_placements(). A click on the arch runs portal/touch (the dive gate) and then
portal/destination, the stub.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import compile_dialogue as CD  # noqa: E402
import frostpeak_camp as FC  # noqa: E402
import function_limits  # noqa: E402
from town_dressing import block_name, turn_xz  # noqa: E402

DATA = ROOT / "data" / "coldwater_station.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_coldwater_station"
REPORT = ROOT / "derived" / "coldwater_station"
NS = "cobblers"
QUEST = "coldwater_station"
TAG = "cobblers_coldwater_station"
SCHEMA = "cobblers.coldwater_station/1"
SEA = 62
PIVOT_DY = FC.PIVOT_DY
TUBE_BACK = FC.TUBE_BACK
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class StationError(SystemExit):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load(path=DATA):
    doc = load_json(path)
    if doc.get("schema") != SCHEMA:
        raise StationError("%s: schema must be %s" % (path, SCHEMA))
    ids = [p["id"] for p in doc["pieces"]] + [r["id"] for r in doc["researchers"]]
    if len(ids) != len(set(ids)):
        raise StationError("piece and researcher ids must be unique")
    return doc


# --------------------------------------------------------------------------------------------- the ferry's records
def ferry_records(doc):
    """(line, near dock, far dock) from data/ferries.json, refused unless the line joins the two docks the file names."""
    fe = load_json(ROOT / "data" / "ferries.json")
    f = doc["ferry"]
    line = next((ln for ln in fe["lines"] if ln["id"] == f["line"]), None)
    if line is None:
        raise StationError("data/ferries.json has no line %s: the station's boat does not exist" % f["line"])
    if sorted(line["stops"]) != sorted([f["dock"], f["far_dock"]]):
        raise StationError("line %s stops at %s, not at %s and %s" % (f["line"], line["stops"], f["dock"], f["far_dock"]))
    docks = {d["id"]: d for d in fe["docks"]}
    return line, docks[f["dock"]], docks[f["far_dock"]]


def gate_says(line):
    gates = line.get("gates") or []
    return " and ".join(g["says"] for g in gates) if gates else "no badge"


# ------------------------------------------------------------------------------------------- the sealed dive arch
def portals_doc():
    import portals as P
    return P, P.load()


def arch(doc, g):
    """The sealed dive arch on the sea floor, by tools/portals.py's own geometry, palette and click trigger (CALLED):
    {blocks, apron_y, click, stand, yaw, buoy, lantern, columns}. Fail-closed on portals.py's rules for a dive
    portal (relief, submersion, water over the lintel, the clearances from towns, placements, legendary mouths and
    the twelve portals), on the sea's painted water (tools/water_mask.py claim, the body "sea"), and on the station's
    own rule that it lies inside the ferry lane data/sea_life.json excludes (see `protected_by_the_lane`)."""
    import water_mask as WM
    P, pdoc = portals_doc()
    spec = dict(doc["portal"]["site"], id=doc["portal"]["id"], gate="dive")
    if spec["id"] in {p["id"] for p in pdoc["portals"]}:
        raise StationError("%s is in data/portals.json: the arch would be built twice" % spec["id"])
    try:
        blocks, ay, click, stand, yaw = P.world_blocks(spec, pdoc, g)
    except P.PortalError as e:
        raise StationError(str(e))
    cols = P.apron_columns(*spec["at"])
    r = pdoc["rules"]
    probs = WM.claim("sea", cols, g, r["min_submersion"], label=spec["id"])
    sea = WM.sea_level()
    if ay + P.ARCH_HEIGHT > sea - r["min_water_above"]:
        probs.append("%s: its lintel tops out at y%d, %d under the sea's level y%d (min %d)"
                     % (spec["id"], ay + P.ARCH_HEIGHT, sea - ay - P.ARCH_HEIGHT, sea, r["min_water_above"]))
    sites = {q["id"]: {"at": q["at"], "gate": q["gate"]} for q in pdoc["portals"]}
    sites[spec["id"]] = {"at": spec["at"], "gate": "dive"}
    # only this arch's: the twelve were cleared by tools/portals.py itself (a pair is reported under the smaller id)
    probs += ["%s: %s" % (pid, why) for pid, why in P.clearances(pdoc, sites) if pid == spec["id"] or spec["id"] in why]
    probs += lane_problems(doc, cols + [(click[0], click[2])])
    if probs:
        raise StationError("the sealed arch is refused:\n  " + "\n  ".join(probs))
    x, z = spec["at"]
    buoy = (x, sea, z)                       # the deck rule (data/sea_town.json): a block AT the sea's level replaces
    lantern = (x, sea + 1, z)                # the top water layer; the lantern stands on it in the air
    pal = doc["portal"]["buoy"]
    blocks = list(blocks) + [buoy + (pal["float"],), lantern + (pal["light"],)]
    return {"blocks": blocks, "apron_y": ay, "click": click, "stand": stand, "yaw": yaw, "buoy": list(buoy),
            "lantern": list(lantern), "columns": cols, "spec": spec, "pdoc": pdoc}


def lane_problems(doc, cols):
    """The arch must lie inside the ferry lane tools/sea_life.py excludes from its writes (and tools/sea_floor.py
    with it), because neither knows this file: they exclude data/portals.json's portals, not this one. The lane is
    sea_life's own construction, re-derived here from the same data: the segment between the two landings'
    (x, z) of the line coldwater_crossing, ferry_lane_half_width_blocks either side. A margin of 4 is kept inside
    its edge for the raster's rounding."""
    line, near, far = ferry_records(doc)
    half = load_json(ROOT / "data" / "sea_life.json")["exclusions"]["ferry_lane_half_width_blocks"] - 4
    (ax, _ay, az), (bx, _by, bz) = near["landing"]["at"], far["landing"]["at"]
    L = math.hypot(bx - ax, bz - az)
    out = []
    for x, z in cols:
        t = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (z - az) * (bz - az)) / (L * L)))
        d = math.hypot(x - (ax + t * (bx - ax)), z - (az + t * (bz - az)))
        if d > half:
            out.append("(%d, %d) is %.1f from the %s ferry lane's centre line (max %d): tools/sea_life.py and "
                       "tools/sea_floor.py would write there" % (x, z, d, line["id"], half))
    return out


def arch_functions(doc, a):
    """{function name: lines} for the arch, the touch and the destination stub; {advancement path: json}."""
    import portals as P
    pdoc = a["pdoc"]
    pid = doc["portal"]["id"]
    tag = "cobblers_kyogre_arch"
    dive = pdoc["gates"]["dive"]
    hook = doc["portal"]["hook"]
    world = ["# Generated by tools/coldwater_station.py from data/coldwater_station.json. Re-run to rebuild; do not edit.",
             "# %s: the sealed dive arch on the sea floor the station watches, tools/portals.py's own geometry and" % pid,
             "# palette, and the station's buoy over it. Its click box is the portals' trigger; the crossing is not built."]
    world += P.commands(a["blocks"])
    world += ["# the click box, one block in front of the sheet. The kill is global on purpose, as tools/portals.py's: a",
              "# stale copy of this arch's box is removed wherever it is",
              "kill @e[type=minecraft:interaction,tag=%s]" % tag,
              P.summon(a["click"], tag, "%s_%s" % (tag, pid), 3.0, 3.0)]
    touch = ["# the touch, as the player who clicked the arch. Re-armed first, so it fires again (tools/portals.py enter/*).",
             "advancement revoke @s only %s:coldwater_station/portal_touch" % NS,
             "execute as @e[type=minecraft:interaction,tag=%s,distance=..8] run data remove entity @s interaction" % tag,
             "# the dive gate, as every dive portal's: data/portals.json gates.dive",
             "execute unless entity @s[tag=%s] run tellraw @s %s" % (dive["tag"], P.text(dive["locked_message"], "gray")),
             "execute unless entity @s[tag=%s] run return 0" % dive["tag"],
             "function %s" % hook["destination_function"]]
    stub = ["# THE HOOK (data/coldwater_station.json portal.hook). The Kyogre cave does not exist. When it does, this",
            "# function's body becomes the crossing (tools/portals.py enter/* is the pattern: set the return score, tp in",
            "# the destination dimension) and its own gate. Today it only says the way is shut. It changes no state.",
            "tellraw @s %s" % P.text(hook["sealed_message"], "dark_aqua")]
    adv = P.click_advancement(tag, "%s:coldwater_station/portal/touch" % NS)
    return ({"portal/build": function_limits.ensure_loaded(world), "portal/touch": touch, "portal/destination": stub},
            {"data/%s/advancement/coldwater_station/portal_touch.json" % NS: adv})


def landing_aim(far):
    x, y, z = far["ferryman"]["at"]
    return (x + 0.5, y + 1.6, z + 0.5)


# ------------------------------------------------------------------------------------------------- the cabin piece
def cabin(spec, doc):
    """A plank hut W x L (odd, at least 5), its open door at the local front (-z): log corners, plank walls three
    high, a pane window in each side and the back, a stripped-wood rim and a plank roof with a slab cap."""
    w, l = spec["width"], spec["length"]
    if w % 2 == 0 or l % 2 == 0 or w < 5 or l < 5:
        raise StationError("%s: a cabin's width and length are odd and at least 5" % spec["id"])
    r, s = w // 2, l // 2
    p = FC.Piece(relief=2)
    for x in range(-r, r + 1):
        for z in range(-s, s + 1):
            p.put(x, 0, z, "minecraft:spruce_planks")
            edge_x, edge_z = abs(x) == r, abs(z) == s
            for dy in (1, 2, 3):
                if edge_x and edge_z:
                    p.put(x, dy, z, "minecraft:spruce_log[axis=y]")
                elif edge_x or edge_z:
                    if z == -s and x == 0 and dy <= 2:
                        p.put(x, dy, z, "minecraft:air")                       # the door
                    elif dy == 2 and edge_x and z == 0:
                        p.put(x, dy, z, "minecraft:glass_pane[north=true,south=true]")
                    elif dy == 2 and z == s and x == 0:
                        p.put(x, dy, z, "minecraft:glass_pane[east=true,west=true]")
                    else:
                        p.put(x, dy, z, "minecraft:spruce_planks")
                else:
                    p.put(x, dy, z, "minecraft:air")
            p.put(x, 4, z, "minecraft:stripped_spruce_wood[axis=y]" if (edge_x or edge_z) else "minecraft:spruce_planks")
            if abs(x) < r and abs(z) < s:
                p.put(x, 5, z, "minecraft:spruce_slab[type=bottom]")
    fit = spec.get("fit_out")
    if fit == "lab":
        p.put(-(r - 1), 1, -(s - 1), "minecraft:packed_ice")
        p.put(-(r - 1), 1, -(s - 2), "minecraft:blue_ice")
        p.put(-(r - 1), 2, -(s - 1), "minecraft:packed_ice")
        p.put(-(r - 1), 1, s - 1, "minecraft:bookshelf")
        p.put(-(r - 2), 1, s - 1, "minecraft:bookshelf")
        p.put(r - 1, 1, s - 1, "minecraft:cartography_table")
        p.put(r - 1, 1, s - 2, "minecraft:lectern[facing=west]")
        p.put(r - 1, 1, -(s - 1), "minecraft:barrel[facing=up]")
        p.put(0, 3, 1, "minecraft:lantern[hanging=true]")
    elif fit is not None:
        raise StationError("%s: unknown fit_out %r" % (spec["id"], fit))
    return p


KINDS = dict(FC.KINDS, cabin=cabin)
ON_DECK = FC.ON_DECK


# ------------------------------------------------------------------------------------------------------ the guards
def keep_out(doc):
    """The ferry dock's keep-clear boxes and its ferryman's and landing's columns, grown by rules.dock_clearance."""
    _line, near, _far = ferry_records(doc)
    m = doc["rules"]["dock_clearance"]
    boxes = [[b[0] - m, b[1] - m, b[2] + m, b[3] + m] for b in near.get("keep_clear") or []]
    for part in ("ferryman", "landing"):
        x, _y, z = near[part]["at"]
        boxes.append([x - m, z - m, x + m, z + m])
    return boxes


def siting(doc, cols, g):
    """Problems, as strings, for every column the station writes."""
    import numpy as np
    import southern_residents as SR
    probs = []
    wet = sorted((x, z) for x, z in cols if g(x, z) < SEA)
    if wet:
        probs.append("%d written column(s) stand in the sea (ground under y%d); first %s" % (len(wet), SEA, wet[:3]))
    for x0, z0, x1, z1 in keep_out(doc):
        hit = sorted((x, z) for x, z in cols if x0 <= x <= x1 and z0 <= z <= z1)
        if hit:
            probs.append("writes %s, within %d of the station jetty or its ferryman/landing"
                         % (hit[:3], doc["rules"]["dock_clearance"]))
    # the station's own jetty (its record in data/ferries.json and in data/ferry_docks.json) and its line are skipped
    # BY ID, through the residents' own-records hook (tools/southern_residents.py owned_ids reads records.*)
    own = {"residents": [{"records": {"quest": doc["ferry"]["dock"], "conversation": doc["ferry"]["line"]}}]}
    # data/regions.json's points are polygon vertices and measured bounds: boundaries, not things anyone placed
    pts = [pt for pt in SR.authored_points(own, own_file=DATA) if pt[2] != "regions.json"]
    P = np.array([(a, b) for a, b, _f in pts], float)
    C = np.array(sorted(cols), float)
    d = np.hypot(P[None, :, 0] - C[:, None, 0], P[None, :, 1] - C[:, None, 1])
    i, j = np.unravel_index(np.argmin(d), d.shape)
    m = doc["rules"]["authored_clearance"]
    if d[i, j] < m:
        probs.append("(%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                     % (C[i][0], C[i][1], d[i, j], pts[j][2], m))
    cprobs, _best = SR.corridor_check("coldwater_station", cols, m)
    probs += cprobs
    for t in load_json(ROOT / "data" / "towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            probs.append("within %d of town %s's footprint" % (m, t["id"]))
    for k, zone in load_json(ROOT / "data" / "rift_zones.json")["zones"].items():
        if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for bx in zone.get("boxes") or [] for x, z in cols):
            probs.append("inside Rift zone %s" % k)
    for zn in load_json(ROOT / "data" / "spawn_suppression.json").get("spawn_free_zones") or []:
        b = zn.get("box") or zn.get("bounds")
        if isinstance(b, list) and len(b) == 4 and any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for x, z in cols):
            probs.append("inside spawn-free zone %s" % zn.get("id"))
    return probs


# ------------------------------------------------------------------------------------------------------- the plan
def plan(doc, g):
    """Everything the pack is made from: blocks, instrument displays, sign texts, numbers, NPC spots."""
    site = doc["site"]
    sx0, sz0 = site["corner"]
    sx1, sz1 = sx0 + site["size"] - 1, sz0 + site["size"] - 1
    allowed = set(doc["blocks"]["ids"])
    spawn = set(load_json(ROOT / "data" / "spawn_blocks.json")["blocks"])
    bad = sorted(allowed & spawn)
    if bad:
        raise StationError("blocks.ids names spawn-condition blocks %s (data/spawn_blocks.json)" % bad)
    foundation = doc["blocks"]["foundation"]
    pieces = {p["id"]: p for p in doc["pieces"]}
    blocks, floors, taken, who = {}, {}, {}, {}

    def add(pid, x, y, z, state, host=None):
        if not (sx0 <= x <= sx1 and sz0 <= z <= sz1):
            raise StationError("%s: block at (%d, %d) is outside the site square" % (pid, x, z))
        owner = taken.get((x, z))
        if owner not in (None, pid, host):
            raise StationError("%s overlaps %s at (%d, %d)" % (pid, owner, x, z))
        if (x, y, z) in blocks and who[(x, y, z)] != pid:
            raise StationError("%s writes (%d, %d, %d), which %s already wrote" % (pid, x, y, z, who[(x, y, z)]))
        taken.setdefault((x, z), pid)
        name = block_name(state)
        if name != "minecraft:air" and name not in allowed:
            raise StationError("%s: %s is not in data/coldwater_station.json blocks.ids" % (pid, name))
        if y <= g(x, z) and name != "minecraft:air":
            raise StationError("%s: (%d, %d, %d) is at or under the ground y%d" % (pid, x, y, z, g(x, z)))
        blocks[(x, y, z)] = state
        who[(x, y, z)] = pid

    owned = {}
    for spec in doc["pieces"]:
        if spec["kind"] in ON_DECK:
            continue
        if spec["kind"] not in KINDS:
            raise StationError("%s: unknown kind %r" % (spec["id"], spec["kind"]))
        piece = KINDS[spec["kind"]](spec, doc)
        try:
            world, gr, floor = FC.seat(spec, piece, g)
        except FC.CampError as e:
            raise StationError(str(e))
        floors[spec["id"]] = floor
        low = {}
        for x, dy, z, _s in world:
            low[(x, z)] = min(low.get((x, z), dy), dy)
        for (x, z), dy0 in low.items():
            for y in range(gr[(x, z)] + 1, floor + dy0):
                add(spec["id"], x, y, z, foundation)
        for x, dy, z, s in world:
            add(spec["id"], x, floor + dy, z, s)
        owned[spec["id"]] = {(x, z) for x, _dy, z, _s in world}

    line, _near, far = ferry_records(doc)
    the_arch = arch(doc, g)
    named = sorted({block_name(b[3]) for b in the_arch["blocks"]} & spawn)
    if named:
        raise StationError("the arch writes spawn-condition blocks %s (data/spawn_blocks.json)" % named)
    numbers = {"fare": "%d" % line["fare"], "gate": gate_says(line)}
    displays, signs = [], []
    for spec in doc["pieces"]:
        if spec["kind"] not in ON_DECK:
            continue
        host = spec["on"]
        if host not in floors:
            raise StationError("%s stands on %s, which is not a placed piece" % (spec["id"], host))
        x, z = spec["at"]
        if (x, z) not in owned[host]:
            raise StationError("%s at (%d, %d) is not on %s" % (spec["id"], x, z, host))
        fl = floors[host]
        if spec["kind"] == "instrument":
            pier = "minecraft:cobblestone_wall" if spec["target"] == "arch_buoy" else "minecraft:spruce_fence"
            add(spec["id"], x, fl + 1, z, pier, host)
            pivot = (x + 0.5, fl + PIVOT_DY, z + 0.5)
            if spec["target"] == "arch_buoy":
                bx, by, bz = the_arch["lantern"]
                aim = (bx + 0.5, by + 0.5, bz + 0.5)
                if not FC.clear_above(g, pivot, aim):
                    raise StationError("the arch's buoy lantern at %s is hidden from the telescope at %s"
                                       % (the_arch["lantern"], pivot))
                numbers["arch_bearing"] = "%03d" % round(FC.bearing(aim[0] - pivot[0], aim[2] - pivot[2]))
                numbers["arch_range"] = "%d" % (round(math.hypot(aim[0] - pivot[0], aim[2] - pivot[2]) / 10) * 10)
                numbers["arch_depth"] = "%d" % (SEA - the_arch["apron_y"])
                extra = {"buoy": the_arch["buoy"], "apron_y": the_arch["apron_y"]}
            elif spec["target"] == "landing":
                aim = landing_aim(far)
                numbers["landing_bearing"] = "%03d" % round(FC.bearing(aim[0] - pivot[0], aim[2] - pivot[2]))
                numbers["landing_range"] = "%d" % (round(math.hypot(aim[0] - pivot[0], aim[2] - pivot[2]) / 10) * 10)
                extra = {"landing": list(far["ferryman"]["at"])}
            else:
                raise StationError("%s: unknown target %r" % (spec["id"], spec["target"]))
            d = [aim[0] - pivot[0], aim[1] - pivot[1], aim[2] - pivot[2]]
            n = math.sqrt(sum(c * c for c in d))
            d = [c / n for c in d]
            q = FC.quaternion(d)
            tube = spec["tube"]
            w, ln = tube["width"], tube["length"]
            elev = math.asin(d[1])
            back = TUBE_BACK
            if elev > 0:
                room = (PIVOT_DY - 2) - (w / 2) * math.cos(elev)
                back = min(back, max(0.0, room / (ln * math.sin(elev))) * 0.9)
            t = FC.rotate(q, [-w / 2, -w / 2, -back * ln])
            cmd = ('summon minecraft:block_display %.2f %.2f %.2f {block_state:{Name:"%s"},'
                   'transformation:{left_rotation:[%s],right_rotation:[0f,0f,0f,1f],translation:[%s],scale:[%s]},'
                   'Tags:["%s","%s"]}' % (pivot[0], pivot[1], pivot[2], tube["block"], ",".join(FC.f(v) for v in q),
                                          ",".join(FC.f(v) for v in t), ",".join(FC.f(v) for v in (w, w, ln)), TAG, spec["id"]))
            displays.append({"id": spec["id"], "pivot": list(pivot), "aim": list(aim), "direction": d,
                             "bearing": FC.bearing(d[0], d[2]), "elevation": math.degrees(math.asin(d[1])),
                             "command": cmd, **extra})
        elif spec["kind"] == "notes_board":
            for dx in (-2, 1):
                add(spec["id"], x + dx, fl + 1, z, "minecraft:spruce_log[axis=y]", host)
                add(spec["id"], x + dx, fl + 2, z, "minecraft:spruce_log[axis=y]", host)
            for dx in (-1, 0):
                add(spec["id"], x + dx, fl + 1, z, "minecraft:spruce_planks", host)
                add(spec["id"], x + dx, fl + 2, z, "minecraft:spruce_planks", host)
            signs.append({"id": spec["id"], "spots": [(x - 1, fl + 2, z + 1), (x, fl + 2, z + 1),
                                                      (x - 1, fl + 1, z + 1), (x, fl + 1, z + 1)]})

    for sg in signs:
        texts = doc["notes_board"]["signs"]
        if len(texts) != len(sg["spots"]):
            raise StationError("the notes board has %d spots and %d signs" % (len(sg["spots"]), len(texts)))
        for (x, y, z), lines in zip(sg["spots"], texts):
            add(sg["id"] + "_signs", x, y, z, FC.wall_sign("south", [fill(t, numbers) for t in lines]))

    npcs = []
    for r in doc["researchers"]:
        if "on" in r:
            x, z = r["at"]
            host = r["on"]
        else:
            spec = pieces[r["in"]]
            lx, lz = turn_xz(*r["at_local"], spec.get("facing", "north"))
            x, z = spec["at"][0] + lx, spec["at"][1] + lz
            host = r["in"]
        fl = floors[host]
        if (x, z) not in owned[host]:
            raise StationError("%s at (%d, %d) is not on %s" % (r["id"], x, z, host))
        for dy in (1, 2):
            s = blocks.get((x, fl + dy, z))
            if s is not None and block_name(s) != "minecraft:air":
                raise StationError("%s at (%d, %d): %s fills its body at y%d" % (r["id"], x, z, block_name(s), fl + dy))
        npcs.append({"id": r["id"], "at": [x, fl + 1, z], "conversation": "dlg_%s" % r["id"],
                     "npc_class": "%s:npc_%s" % (NS, r["id"])})

    cols = {(x, z) for (x, _y, z) in blocks}
    probs = siting(doc, cols, g)
    if probs:
        raise StationError("the station's siting rules refuse the build:\n  " + "\n  ".join(probs))
    return {"blocks": blocks, "who": who, "floors": floors, "displays": displays, "numbers": numbers, "npcs": npcs,
            "arch": the_arch}


def fill(text, numbers):
    try:
        return text.format(**numbers)
    except KeyError as e:
        raise StationError("text %r names %s, which the plan does not compute" % (text, e))


# ------------------------------------------------------------------------------------------------------ the talk
def conversation(r, numbers):
    """(conversation, quest) for one researcher, in data/dialogue.json's and data/quests.json's shape (the camp's)."""
    field = "quest.%s.%s_cursor" % (QUEST, r["id"].split("_")[-1])
    sp = r["id"]
    responses = [{"id": "r_%s" % t["id"], "text": t["ask"], "next": t["id"]} for t in r["topics"]]
    responses.append({"id": "r_leave", "text": r["leave"], "actions": [{"kind": "close_dialogue"}]})
    nodes = [{"id": "hub", "kind": "choice", "speaker": sp, "text": fill(r["greeting"], numbers), "responses": responses}]
    nodes += [{"id": t["id"], "kind": "line", "speaker": sp, "text": fill(t["says"], numbers), "next": "hub"}
              for t in r["topics"]]
    conv = {"id": "dlg_%s" % r["id"], "quest_id": QUEST, "npc_id": "npc_%s" % r["id"], "npc_name": r["name"],
            "scope": "player", "speakers": {sp: r["name"]},
            "cursor": {"progression_field": field, "initial_node": "hub"},
            "entry_rules": [{"priority": 10, "when": {"kind": "always"}, "node": "hub"}],
            "nodes": nodes}
    quest = {"id": QUEST, "progression_field_refs": [field], "transitions": [], "rewards": []}
    return conv, quest


# ------------------------------------------------------------------------------------------------------ the pack
def commands(blocks):
    body = FC.commands(blocks)
    return ["# Generated by tools/coldwater_station.py from data/coldwater_station.json. Re-run to rebuild; do not edit.",
            "# Coldwater Station's blocks. Run before cobblers:coldwater_station/instruments."] + body[2:]


def instrument_commands(displays):
    xs = [d["pivot"][0] for d in displays]
    zs = [d["pivot"][2] for d in displays]
    cx, cy, cz = sum(xs) / len(xs), displays[0]["pivot"][1], sum(zs) / len(zs)
    x0, x1 = math.floor(min(xs)), math.floor(max(xs))
    z0, z1 = math.floor(min(zs)), math.floor(max(zs))
    out = ["# Generated by tools/coldwater_station.py from data/coldwater_station.json. Re-run to rebuild; do not edit.",
           "# The instrument tubes: block_display entities pointed at their targets. An export erases entities, so this",
           "# re-summons them after removing this station's own displays near the deck (expect %d)." % len(displays),
           "forceload add %d %d %d %d" % (x0, z0, x1, z1),
           "kill @e[type=minecraft:block_display,tag=%s,x=%.1f,y=%.1f,z=%.1f,distance=..24]" % (TAG, cx, cy, cz)]
    for d in displays:
        out.append("# %s: bearing %.2f, elevation %.2f, aimed at (%.1f, %.1f, %.1f)" % (
            d["id"], d["bearing"], d["elevation"], d["aim"][0], d["aim"][1], d["aim"][2]))
        out.append(d["command"])
    out.append("forceload remove %d %d %d %d" % (x0, z0, x1, z1))
    return out


def build(doc, g):
    p = plan(doc, g)
    fn = lambda rel: "data/%s/function/coldwater_station/%s.mcfunction" % (NS, rel)   # noqa: E731
    files = {"pack.mcmeta": {"pack": {"pack_format": 48, "description":
                                      "Cobblers: Coldwater Station (generated by tools/coldwater_station.py)"}}}
    files[fn("build")] = function_limits.ensure_loaded(commands(p["blocks"]))
    files[fn("instruments")] = instrument_commands(p["displays"])
    afns, aadv = arch_functions(doc, p["arch"])
    for rel, lines in afns.items():
        files[fn(rel)] = lines
    files.update(aadv)
    for rel in ("build", "instruments", "portal/build", "portal/touch", "portal/destination"):
        bad = function_limits.check_lines(files[fn(rel)], rel)
        if bad:
            raise StationError("%s: %d command(s) the server would refuse: %s" % (rel, len(bad), bad[:3]))
    fields = {fd["id"]: fd for fd in load_json(ROOT / "data" / "progression.json")["quest_fields"]}
    for r in doc["researchers"]:
        conv, quest = conversation(r, p["numbers"])
        got = CD.compile_conversation(conv, {quest["id"]: quest}, fields)
        clash = [k for k in got if k in files]
        if clash:
            raise StationError("%s writes %s twice" % (r["id"], clash))
        files.update(got)
    files["steps.txt"] = ["# Run in this order, after the pack is installed and the server restarted (NPC classes load at boot):",
                          "function %s:coldwater_station/build" % NS, "function %s:coldwater_station/instruments" % NS,
                          "function %s:coldwater_station/portal/build" % NS] + [
                         "spawnnpcat %d %d %d %s" % (tuple(n["at"]) + (n["npc_class"],)) for n in p["npcs"]]
    return files, p


def forceload_box(doc=None):
    doc = doc or load()
    x0, z0 = doc["site"]["corner"]
    n = doc["site"]["size"]
    return x0 - 8, z0 - 8, x0 + n + 7, z0 + n + 7


def npc_placements(doc=None, g=None):
    """[(conversation id, (x, y, z), npc class)] for tools/reapply.py's "npc" action."""
    import ground as G
    doc = doc or load()
    g = g or G.Ground()
    return [(n["conversation"], tuple(n["at"]), n["npc_class"]) for n in plan(doc, g)["npcs"]]


def placement_steps(doc=None, g=None):
    """R18CW's actions: the blocks and instruments held in a forceload, then the three researchers."""
    doc = doc or load()
    box = "%d %d %d %d" % forceload_box(doc)
    return ([("cmd", "forceload add " + box), ("wait", 3),
             ("fn", "%s:coldwater_station/build" % NS), ("fn", "%s:coldwater_station/instruments" % NS),
             ("cmd", "forceload remove " + box),
             # the sealed arch: its function force-loads its own chunks (tools/function_limits.py ensure_loaded)
             ("fn", "%s:coldwater_station/portal/build" % NS)]
            + [("npc", n) for n in npc_placements(doc, g)])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("build", "plan"))
    ap.add_argument("--source-root")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args(argv)
    import ground as G
    g = G.Ground(a.source_root)
    doc = load()
    files, p = build(doc, g)
    rep = FC.report(p)
    a_ = p["arch"]
    top = max(a_["blocks"], key=lambda b: (b[1], b[0], b[2]))
    rep["arch"] = {"id": a_["spec"]["id"], "at": a_["spec"]["at"], "facing": a_["spec"]["facing"],
                   "apron_y": a_["apron_y"], "click": list(a_["click"]), "buoy": a_["buoy"],
                   "probes": ["execute if block %d %d %d %s" % (top[0], top[1], top[2], block_name(top[3])),
                              "execute if block %d %d %d %s" % (a_["spec"]["at"][0], a_["apron_y"], a_["spec"]["at"][1],
                                                                block_name(a_["pdoc"]["blocks"]["dive"]["apron"])),
                              "execute if entity @e[type=minecraft:interaction,tag=cobblers_kyogre_arch]"]}
    if a.action == "plan":
        print(json.dumps(rep, indent=1))
        return 0
    FC.write(files, a.out)
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "report.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print("wrote %d files to %s (%d blocks, %d displays, %d NPCs)" % (len(files), a.out, len(p["blocks"]),
                                                                       len(p["displays"]), len(p["npcs"])))
    for k, v in sorted(p["numbers"].items()):
        print("  %s = %s" % (k, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
