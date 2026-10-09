#!/usr/bin/env python
"""The Frostpeak research camp: a small field camp at Frostpeak's south foot whose researchers study Articuno.

Generated from data/frostpeak_camp.json into the world-local datapack build/datapacks/cobblers_frostpeak_camp.

The adopted Articuno shrine (data/adopted_legendary_sites.json adopted_articuno_shrine, on the summit since 2026-10-02)
has no finder in the game. The camp is the natural way a player learns where to look: a telescope trained on the tower, a
theodolite on the summit's bearing, field notes on a board, and three researchers who point. Nothing here promises the
shrine's LumyMon altar works (EXP-048; the record's a_dead_altar_must_not_block rule): the dialogue only talks. It
sets no quest state but its own cursor, runs no command, gives nothing and gates nothing.

Every part is an existing, proven piece:

  the blocks      vanilla 1.21.1, seated the repository's way (tools/shrines.py): each piece on max(ground under its
                  footprint) + 1, a foundation down to the ground under any lower column, ground from tools/ground.py
                  (the canonical heightmap, rounded), never a world. Each column is cleared of plants, snow layers,
                  logs and leaves first. tools/function_limits.py force-loads what the function writes.
  the instruments block_display entities (the format tools/rift_skin.py uses) whose transformation points the tube
                  along the exact bearing and elevation to its target, which a block cannot. The shrine target is
                  the middle of the part of the tower's centre column visible over the false crest from the telescope;
                  the summit target is the false crest that hides the summit platform, on the summit's bearing.
                  Both are computed here from the heightmap.
  the researchers Cobblemon NPCs whose classes open a dialogue compiled by tools/compile_dialogue.py's Compiler from
                  a conversation built in memory (the ferry's pattern, tools/ferries.py): a hub page, one option per
                  topic, each topic a page that returns to the hub. The cursor fields are declared in
                  data/progression.json (quest.frostpeak_camp.<npc>_cursor). NPC classes load only at server start,
                  so this pack must be installed before boot, and the NPCs are placed over RCON by spawnnpcat
                  (tools/reapply.py's "npc" action), from npc_placements() below.

The functions, to run in order after the pack is installed and the server restarted:

  cobblers:frostpeak_camp/build         the blocks (force-loads its own chunks)
  cobblers:frostpeak_camp/instruments   kills this camp's display entities near the deck, then summons the two tubes

and then the three NPCs, placed by npc_placements(). tools/frostpeak_camp_audit.py checks the written pack
independently.

  python tools/frostpeak_camp.py build [--source-root R] [--out DIR]   write the pack and derived/frostpeak_camp/
  python tools/frostpeak_camp.py plan  [--source-root R]               print the numbers and the placements; writes nothing
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
import chunk_look as CL  # noqa: E402
import compile_dialogue as CD  # noqa: E402
import function_limits  # noqa: E402
from town_dressing import _runs, block_name, turn_state, turn_xz  # noqa: E402

DATA = ROOT / "data" / "frostpeak_camp.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_frostpeak_camp"
REPORT = ROOT / "derived" / "frostpeak_camp"
NS = "cobblers"
QUEST = "frostpeak_camp"
TAG = "cobblers_frostpeak_camp"
PIVOT_DY = 2.2          # the instrument's pivot above its deck's floor: just over a wall or fence post's top
TUBE_BACK = 0.3         # the share of the tube behind the pivot (the eyepiece end)
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class CampError(SystemExit):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load():
    return load_json(DATA)


# ------------------------------------------------------------------------------------------------------- the targets
def shrine_record():
    doc = load_json(ROOT / "data" / "adopted_legendary_sites.json")
    rec = next((s for s in doc["sites"] if s.get("id") == "adopted_articuno_shrine"), None)
    if rec is None:
        raise CampError("data/adopted_legendary_sites.json has no adopted_articuno_shrine: the camp has nothing to study")
    return rec


def summit_record():
    town = next((t for t in load_json(ROOT / "data" / "towns.json")["towns"] if t["id"] == "frostpeak_shrine"), None)
    if town is None:
        raise CampError("data/towns.json has no frostpeak_shrine: no summit platform to sight")
    return town


def bearing(dx, dz):
    """Compass bearing in degrees, clockwise from north (-z), 0..360."""
    return math.degrees(math.atan2(dx, -dz)) % 360


def clear_above(g, a, b, skip=3.0):
    """True when the straight line from a to b (x, y, z) passes above the top face of every ground block, ignoring the
    first `skip` blocks of horizontal distance (the camp's own bench under the instrument).

    Exact, by clipping the segment to each column's square (Liang-Barsky) over the segment's bounding box: the line is
    lowest at one end of the stretch it spends over a column, so a column blocks it when either end of that stretch is
    at or below the column's top face. A fixed-step walk misses the corners of columns it crosses; on 2026-10-02 the
    quarter-block walk this replaced called the summit tower visible from y369 where the crest still hides that layer."""
    (ax, ay, az), (bx, by, bz) = a, b
    dx, dy, dz = bx - ax, by - ay, bz - az
    d = math.hypot(dx, dz)

    def span(p0, dp, lo, hi):
        """The t interval in which p0 + t*dp lies in [lo, hi], or None."""
        if dp == 0:
            return (0.0, 1.0) if lo <= p0 <= hi else None
        t0, t1 = sorted(((lo - p0) / dp, (hi - p0) / dp))
        return t0, t1

    for cx in range(math.floor(min(ax, bx)), math.floor(max(ax, bx)) + 1):
        sx = span(ax, dx, cx, cx + 1)
        if sx is None or min(1.0, sx[1]) < max(0.0, sx[0]):
            continue
        # only the rows the segment can reach inside this column of x
        za, zb = sorted((az + dz * max(0.0, sx[0]), az + dz * min(1.0, sx[1])))
        for cz in range(math.floor(za), math.floor(zb) + 1):
            sz = span(az, dz, cz, cz + 1)
            if sz is None:
                continue
            t0, t1 = max(0.0, sx[0], sz[0]), min(1.0, sx[1], sz[1])
            if t1 <= t0 or (t0 + t1) / 2 * d < skip:
                continue
            if min(ay + dy * t0, ay + dy * t1) <= g(cx, cz) + 1:
                return False
    return True


def shrine_aim(g, pivot):
    """(aim point, lowest visible y, top y) on the tower's centre column, seen from pivot."""
    rec = shrine_record()
    cx, cz = rec["placement"]["centre"]
    seat, top = rec["placement"]["y"], rec["placement"]["top_y"]
    lo = next((y for y in range(seat, top + 1) if clear_above(g, pivot, (cx + 0.5, y + 0.5, cz + 0.5))), None)
    if lo is None:
        raise CampError("no part of the tower at (%d, %d) is visible from the telescope at %s" % (cx, cz, pivot))
    mid = (lo + top) // 2
    return (cx + 0.5, mid + 0.5, cz + 0.5), lo, top


def summit_aim(g, pivot):
    """(aim point on the crest, crest distance, summit centre, summit visible?) along the summit's bearing."""
    town = summit_record()
    sx, sz = town["centre"]["x"] + 0.5, town["centre"]["z"] + 0.5
    px, py, pz = pivot
    dx, dz = sx - px, sz - pz
    dist = math.hypot(dx, dz)
    best = None
    # a quarter-block step: at whole-block steps the line skips the corners of columns it crosses, and one of
    # them was the crest (the audit found the tube 0.06 degrees into it)
    for k in range(16, int(dist * 4)):
        i = k / 4
        t = i / dist
        x, z = px + dx * t, pz + dz * t
        top = g(math.floor(x), math.floor(z)) + 1
        ang = math.atan2(top - py, i)
        if best is None or ang > best[0]:
            best = (ang, x, top, z, i)
    ang, x, top, z, i = best
    sy = town["centre"]["ground_y"] + 1
    visible = clear_above(g, pivot, (sx, sy + 0.5, sz))
    return (x, top, z), i, (sx, sy, sz), visible


def quaternion(direction):
    """left_rotation [x, y, z, w] that turns the model's +z onto direction: pitch about X, then yaw about Y."""
    dx, dy, dz = direction
    h = math.hypot(dx, dz)
    a = math.atan2(dx, dz)              # +z onto the horizontal direction
    b = -math.atan2(dy, h)              # +z tipped up by the elevation
    cy, sy, cx, sx = math.cos(a / 2), math.sin(a / 2), math.cos(b / 2), math.sin(b / 2)
    return [cy * sx, sy * cx, -sy * sx, cy * cx]


def rotate(q, v):
    x, y, z, w = q
    m = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [sum(m[r][c] * v[c] for c in range(3)) for r in range(3)]


def f(v):
    return "%.4ff" % v


# -------------------------------------------------------------------------------------------------------- the pieces
class Piece:
    """Blocks as (local x, dy, local z, state); dy 0 is the floor (the block above the highest ground under it)."""

    def __init__(self, relief):
        self.blocks = []
        self.relief = relief
        self.npc_spots = {}

    def put(self, x, dy, z, state):
        self.blocks.append((x, dy, z, state))


def ridge_tent(spec, doc):
    """A ridge tent W wide and L long, its door at the local front (-z): a plank floor, canvas stepped up to a red
    ridge, a closed back, a gable over an open door. W and L odd."""
    w, l = spec["width"], spec["length"]
    if w % 2 == 0 or l % 2 == 0 or w < 5:
        raise CampError("%s: a tent's width and length are odd and the width at least 5" % spec["id"])
    r, s = w // 2, l // 2
    canvas, trim = doc["blocks"]["canvas"], doc["blocks"]["canvas_trim"]
    p = Piece(relief=2)
    inside = lambda x, dy: 1 <= dy <= r - abs(x)            # noqa: E731  the air under the canvas
    for z in range(-s, s + 1):
        for x in range(-r, r + 1):
            p.put(x, 0, z, "minecraft:spruce_planks")
            p.put(x, 1 + r - abs(x), z, trim if x == 0 else canvas)
            for dy in range(1, r - abs(x) + 1):
                if z == s:
                    p.put(x, dy, z, canvas)                 # the closed back
                elif z == -s and not (abs(x) <= 1 and dy <= 2):
                    p.put(x, dy, z, canvas)                 # the gable over the door
                else:
                    p.put(x, dy, z, "minecraft:air")
    fit = spec.get("fit_out")
    if fit == "mess":
        p.put(-(r - 1), 1, -(s - 2), "minecraft:barrel[facing=up]")
        p.put(-(r - 1), 1, -(s - 3), "minecraft:barrel[facing=east]")
        p.put(-(r - 1), 1, s - 2, "minecraft:smoker[facing=east,lit=false]")
        p.put(-(r - 1), 1, s - 1, "minecraft:barrel[facing=up]")
        for z in range(-(s - 3), s - 2):
            p.put(r - 1, 1, z, "minecraft:spruce_slab[type=top]")
        for z in (-2, 2):
            p.put(0, r, z, "minecraft:lantern[hanging=true]")
    elif fit == "bunk":
        for x in (-1, 1):
            for z in range(-(s - 2), s):
                p.put(x, 1, z, "minecraft:red_carpet")
        p.put(0, 1, s - 1, "minecraft:barrel[facing=up]")
        p.put(0, 2, s - 1, "minecraft:lantern[hanging=true]")
    elif fit is not None:
        raise CampError("%s: unknown fit_out %r" % (spec["id"], fit))
    return p


def deck(spec, doc):
    hx, hz = spec["half"]
    p = Piece(relief=2)
    for x in range(-hx, hx + 1):
        for z in range(-hz, hz + 1):
            p.put(x, 0, z, "minecraft:spruce_planks")
    if spec.get("rail") == "north":
        for x in range(-hx, hx + 1):
            sides = [s for s, ok in (("west", x > -hx), ("east", x < hx)) if ok]
            p.put(x, 1, -hz, "minecraft:spruce_fence[%s]" % ",".join("%s=true" % s for s in sides))
    return p


def fire_ring(spec, doc):
    p = Piece(relief=1)
    p.put(0, 0, 0, "minecraft:campfire[lit=true,signal_fire=false,facing=south]")
    for x in (-1, 0, 1):
        p.put(x, 0, -3, "minecraft:stripped_spruce_log[axis=x]")
        p.put(x, 0, 3, "minecraft:stripped_spruce_log[axis=x]")
    for z in (-1, 0, 1):
        p.put(-3, 0, z, "minecraft:stripped_spruce_log[axis=z]")
    return p


def supply_cache(spec, doc):
    p = Piece(relief=1)
    p.put(0, 0, 0, "minecraft:barrel[facing=up]")
    p.put(1, 0, 0, "minecraft:stripped_spruce_wood[axis=y]")
    p.put(1, 1, 0, "minecraft:barrel[facing=up]")
    p.put(2, 0, 0, "minecraft:stripped_spruce_wood[axis=y]")
    p.put(0, 0, 1, "minecraft:barrel[facing=south]")
    p.put(2, 0, 1, "minecraft:barrel[facing=up]")
    return p


def weather_mast(spec, doc):
    p = Piece(relief=1)
    for dy in range(0, 4):
        p.put(0, dy, 0, "minecraft:spruce_fence")
    p.put(0, 4, 0, "minecraft:lantern[hanging=false]")
    p.put(1, 0, 0, "minecraft:cauldron")
    return p


KINDS = {"ridge_tent": ridge_tent, "deck": deck, "fire_ring": fire_ring, "supply_cache": supply_cache,
         "weather_mast": weather_mast}
ON_DECK = ("instrument", "notes_board")


def wall_sign(facing, lines):
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
    return "minecraft:spruce_wall_sign[facing=%s]{front_text:{messages:[%s]}}" % (facing, q)


def seat(spec, piece, g):
    """[(x, y, z, state)] for a piece seated on the ground, and its floor."""
    ox, oz = spec["at"]
    facing = spec.get("facing", "north")
    last = {}
    for x, dy, z, s in piece.blocks:
        last[(x, dy, z)] = s
    world = []
    for (x, dy, z), s in last.items():
        tx, tz = turn_xz(x, z, facing)
        world.append((ox + tx, dy, oz + tz, turn_state(s, facing)))
    cols = sorted({(x, z) for x, _dy, z, _s in world})
    gr = {c: g(*c) for c in cols}
    relief = max(gr.values()) - min(gr.values())
    if relief > piece.relief:
        raise CampError("%s: the ground under it varies by %d blocks (allowed %d): move it" % (spec["id"], relief, piece.relief))
    floor = max(gr.values()) + 1
    return world, gr, floor


# ---------------------------------------------------------------------------------------------------------- the plan
def plan(doc, g):
    """Everything the pack is made from: blocks, instrument displays, sign texts, numbers, NPC spots."""
    site = doc["site"]
    sx0, sz0 = site["corner"]
    sx1, sz1 = sx0 + site["size"] - 1, sz0 + site["size"] - 1
    allowed = set(doc["blocks"]["ids"])
    foundation = doc["blocks"]["foundation"]
    pieces = {p["id"]: p for p in doc["pieces"]}
    blocks, floors, taken, who = {}, {}, {}, {}

    def add(pid, x, y, z, state, host=None):
        """One block of piece pid; a piece standing on a host (the deck) may share the host's columns, never a block."""
        if not (sx0 <= x <= sx1 and sz0 <= z <= sz1):
            raise CampError("%s: block at (%d, %d) is outside the site square" % (pid, x, z))
        owner = taken.get((x, z))
        if owner not in (None, pid, host):
            raise CampError("%s overlaps %s at (%d, %d)" % (pid, owner, x, z))
        if (x, y, z) in blocks and who[(x, y, z)] != pid:
            raise CampError("%s writes (%d, %d, %d), which %s already wrote" % (pid, x, y, z, who[(x, y, z)]))
        taken.setdefault((x, z), pid)
        name = block_name(state)
        if name != "minecraft:air" and name not in allowed:
            raise CampError("%s: %s is not in data/frostpeak_camp.json blocks.ids" % (pid, name))
        blocks[(x, y, z)] = state
        who[(x, y, z)] = pid

    owned = {}
    for spec in doc["pieces"]:
        if spec["kind"] in ON_DECK:
            continue
        if spec["kind"] not in KINDS:
            raise CampError("%s: unknown kind %r" % (spec["id"], spec["kind"]))
        piece = KINDS[spec["kind"]](spec, doc)
        world, gr, floor = seat(spec, piece, g)
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

    # the deck's furniture: piers, the board and its signs, on the deck's own floor
    numbers, displays, signs = {}, [], []
    for spec in doc["pieces"]:
        if spec["kind"] not in ON_DECK:
            continue
        host = spec["on"]
        if host not in floors:
            raise CampError("%s stands on %s, which is not a placed piece" % (spec["id"], host))
        x, z = spec["at"]
        if (x, z) not in owned[host]:
            raise CampError("%s at (%d, %d) is not on %s" % (spec["id"], x, z, host))
        fl = floors[host]
        if spec["kind"] == "instrument":
            pier = "minecraft:cobblestone_wall" if spec["target"] == "shrine" else "minecraft:spruce_fence"
            add(spec["id"], x, fl + 1, z, pier, host)
            pivot = (x + 0.5, fl + PIVOT_DY, z + 0.5)
            if spec["target"] == "shrine":
                aim, lo, top = shrine_aim(g, pivot)
                rec = shrine_record()
                cx, cz = rec["placement"]["centre"]
                numbers["shrine_bearing"] = "%03d" % round(bearing(cx + 0.5 - pivot[0], cz + 0.5 - pivot[2]))
                numbers["shrine_range"] = "%d" % (round(math.hypot(cx + 0.5 - pivot[0], cz + 0.5 - pivot[2]) / 10) * 10)
                numbers["shrine_top"] = "%d" % top
                numbers["crown_showing"] = "%d" % (top - lo + 1)
                numbers["climb"] = "%d" % (round((g(cx, cz) - g(x, z)) / 5) * 5)
                extra = {"visible_from_y": lo, "top_y": top}
            elif spec["target"] == "summit":
                aim, crest_d, summit, visible = summit_aim(g, pivot)
                if visible:
                    raise CampError("the summit platform is visible from the theodolite: the false-crest lines are wrong")
                numbers["summit_bearing"] = "%03d" % round(bearing(summit[0] - pivot[0], summit[2] - pivot[2]))
                numbers["summit_beyond"] = "%d" % (round((math.hypot(summit[0] - pivot[0], summit[2] - pivot[2]) - crest_d) / 10) * 10)
                extra = {"crest_distance": crest_d, "summit": list(summit), "summit_visible": visible}
            else:
                raise CampError("%s: unknown target %r" % (spec["id"], spec["target"]))
            d = [aim[0] - pivot[0], aim[1] - pivot[1], aim[2] - pivot[2]]
            n = math.sqrt(sum(c * c for c in d))
            d = [c / n for c in d]
            q = quaternion(d)
            tube = spec["tube"]
            w, ln = tube["width"], tube["length"]
            # the share of the tube behind the pivot, cut down when the tube is steep enough for its eyepiece end to
            # dip into the pier top (PIVOT_DY - 2 below the pivot): the summit tower (2026-10-02) is 40 degrees up
            elev = math.asin(d[1])
            back = TUBE_BACK
            if elev > 0:
                room = (PIVOT_DY - 2) - (w / 2) * math.cos(elev)
                back = min(back, max(0.0, room / (ln * math.sin(elev))) * 0.9)
            t = rotate(q, [-w / 2, -w / 2, -back * ln])
            cmd = ('summon minecraft:block_display %.2f %.2f %.2f {block_state:{Name:"%s"},'
                   'transformation:{left_rotation:[%s],right_rotation:[0f,0f,0f,1f],translation:[%s],scale:[%s]},'
                   'Tags:["%s","%s"]}' % (pivot[0], pivot[1], pivot[2], tube["block"], ",".join(f(v) for v in q),
                                          ",".join(f(v) for v in t), ",".join(f(v) for v in (w, w, ln)), TAG, spec["id"]))
            displays.append({"id": spec["id"], "pivot": list(pivot), "aim": list(aim), "direction": d,
                             "bearing": bearing(d[0], d[2]), "elevation": math.degrees(math.asin(d[1])),
                             "command": cmd, **extra})
        elif spec["kind"] == "notes_board":
            # two log posts, a two-by-two plank board between them, four wall signs on its south face
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
            raise CampError("the notes board has %d spots and %d signs" % (len(sg["spots"]), len(texts)))
        for (x, y, z), lines in zip(sg["spots"], texts):
            add(sg["id"] + "_signs", x, y, z, wall_sign("south", [fill(t, numbers) for t in lines]))

    npcs = []
    for r in doc["researchers"]:
        if "on" in r:
            x, z = r["at"]
            fl = floors[r["on"]]
        else:
            spec = pieces[r["in"]]
            lx, lz = turn_xz(*r["at_local"], spec.get("facing", "north"))
            x, z = spec["at"][0] + lx, spec["at"][1] + lz
            fl = floors[r["in"]]
        npcs.append({"id": r["id"], "at": [x, fl + 1, z], "conversation": "dlg_%s" % r["id"],
                     "npc_class": "%s:npc_%s" % (NS, r["id"])})
    return {"blocks": blocks, "who": who, "floors": floors, "displays": displays, "numbers": numbers, "npcs": npcs}


def fill(text, numbers):
    try:
        return text.format(**numbers)
    except KeyError as e:
        raise CampError("text %r names %s, which the plan does not compute" % (text, e))


# ---------------------------------------------------------------------------------------------------------- the talk
def conversation(r, numbers):
    """(conversation, quest) for one researcher, in memory, in data/dialogue.json's and data/quests.json's shape."""
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
            # talk, not a quest: every visit opens at the hub, whatever page the cursor was left on
            "entry_rules": [{"priority": 10, "when": {"kind": "always"}, "node": "hub"}],
            "nodes": nodes}
    quest = {"id": QUEST, "progression_field_refs": [field], "transitions": [], "rewards": []}
    return conv, quest


# --------------------------------------------------------------------------------------------------------- the pack
def commands(blocks):
    cmds = ["# Generated by tools/frostpeak_camp.py from data/frostpeak_camp.json. Re-run to rebuild; do not edit.",
            "# The Frostpeak research camp's blocks. Run before cobblers:frostpeak_camp/instruments."]
    span = {}
    for (x, y, z) in blocks:
        lo, hi = span.get((x, z), (y, y))
        span[(x, z)] = (min(lo, y), max(hi, y))
    # each column cleared over its own span only (from the block under its lowest write, which is the ground or the
    # floor's own level, to above its highest), in runs along a row that share a span
    by_span = {}
    for c, s in span.items():
        by_span.setdefault(s, []).append(c)
    for (lo, hi), cols in sorted(by_span.items()):
        for x0, x1, z in _runs(cols):
            cmds.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:replaceable" % (x0, lo - 1, z, x1, hi + 1, z))
            for tag in ("#minecraft:logs", "#minecraft:leaves"):
                cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, lo, z, x1, hi + 2, z, tag))
    for (x, y, z), s in sorted(blocks.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2])):
        cmds.append("setblock %d %d %d %s" % (x, y, z, s))
    return cmds


INSTRUMENTS_FN = "%s:frostpeak_camp/instruments" % NS
INSTRUMENTS_HOLDER = "frostpeak_instruments"     # tools/reapply.py R18F reads the count back from this holder


def instrument_functions(displays, tag=TAG, base=INSTRUMENTS_FN, holder=INSTRUMENTS_HOLDER,
                         note="tools/frostpeak_camp.py"):
    """{function id: lines}: the instrument tubes, block_display entities pointed at their targets, re-summoned (an
    export erases entities) through tools/chunk_look.py's look-then-act chain. The old one-tick shape (forceload, kill,
    summon) killed nothing where the chunk's saved displays had not arrived yet, and a re-run doubled every tube (N155,
    measured for the stall merchants on staging 2026-10-08). The chain kills this site's own displays near the deck only
    once one is seen there (or blind on a first run), summons each tube once with a `<tag>_new` tag, and 100 ticks later
    kills any copy without it and counts what stands into #<holder>. Shared with tools/coldwater_station.py."""
    xs = [d["pivot"][0] for d in displays]
    zs = [d["pivot"][2] for d in displays]
    cx, cy, cz = sum(xs) / len(xs), displays[0]["pivot"][1], sum(zs) / len(zs)
    box = (math.floor(min(xs)), math.floor(min(zs)), math.floor(max(xs)), math.floor(max(zs)))
    scope = "type=minecraft:block_display,tag=%s,x=%.1f,y=%.1f,z=%.1f,distance=..24" % (tag, cx, cy, cz)
    new = tag + "_new"
    act = ["# %d tubes: this site's old displays near the deck, then one of each" % len(displays),
           "kill @e[%s]" % scope]
    for d in displays:
        cmd = d["command"]
        if not cmd.endswith('"]}'):
            raise CampError("%s: its summon does not end in its Tags list, so it cannot carry %s" % (d["id"], new))
        act.append("# %s: bearing %.2f, elevation %.2f, aimed at (%.1f, %.1f, %.1f)" % (
            d["id"], d["bearing"], d["elevation"], d["aim"][0], d["aim"][1], d["aim"][2]))
        act.append(cmd[:-2] + ',"%s"]}' % new)
    return CL.chain(base, box, ["@e[%s]" % scope], act, [scope], new, scope, holder, note=note)


def instrument_count(doc):
    """The displays the chain must leave standing: one per authored instrument."""
    return sum(1 for p in doc["pieces"] if p.get("kind") == "instrument")


def build(doc, g):
    p = plan(doc, g)
    fn = lambda rel: "data/%s/function/frostpeak_camp/%s.mcfunction" % (NS, rel)   # noqa: E731
    files = {"pack.mcmeta": {"pack": {"pack_format": 48, "description":
                                      "Cobblers: the Frostpeak research camp (generated by tools/frostpeak_camp.py)"}}}
    files[fn("build")] = function_limits.ensure_loaded(commands(p["blocks"]))
    files.update(CL.files(instrument_functions(p["displays"])))
    for rel in ("build", "instruments", "instruments_look", "instruments_act", "instruments_done"):
        bad = function_limits.check_lines(files[fn(rel)], rel)
        if bad:
            raise CampError("%s: %d command(s) the server would refuse: %s" % (rel, len(bad), bad[:3]))
    fields = {fd["id"]: fd for fd in load_json(ROOT / "data" / "progression.json")["quest_fields"]}
    for r in doc["researchers"]:
        conv, quest = conversation(r, p["numbers"])
        got = CD.compile_conversation(conv, {quest["id"]: quest}, fields)
        clash = [k for k in got if k in files]
        if clash:
            raise CampError("%s writes %s twice" % (r["id"], clash))
        files.update(got)
    files["steps.txt"] = ["# Run in this order, after the pack is installed and the server restarted (NPC classes load at boot):",
                          "function %s:frostpeak_camp/build" % NS, "function %s:frostpeak_camp/instruments" % NS] + [
                         "spawnnpcat %d %d %d %s" % (tuple(n["at"]) + (n["npc_class"],)) for n in p["npcs"]]
    return files, p


def npc_placements(doc=None, g=None):
    """[(conversation id, (x, y, z), npc class)] for tools/reapply.py's "npc" action."""
    import ground as G
    doc = doc or load()
    g = g or G.Ground()
    return [(n["conversation"], tuple(n["at"]), n["npc_class"]) for n in plan(doc, g)["npcs"]]


def instrument_steps(doc=None):
    """tools/reapply.py R18F's instrument actions: start the chain, wait for all of it, read the count back. Run after
    the step has RELEASED its own forceload: the chain holds and releases its own, and a forceload is per chunk."""
    doc = doc or load()
    return CL.steps(INSTRUMENTS_FN, INSTRUMENTS_HOLDER, instrument_count(doc), "the Frostpeak camp's instrument tubes")


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in files.items():
        f_ = out / rel
        f_.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(content) + "\n" if isinstance(content, list) else json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        f_.write_text(body, encoding="utf-8", newline="\n")


def report(p):
    """The probes the integrating session checks in game, and the numbers."""
    blocks, who = p["blocks"], p["who"]
    top = {}
    for pos, s in blocks.items():
        if block_name(s) == "minecraft:air":
            continue
        pid = who[pos]
        if pid not in top or (pos[1], pos[0], pos[2]) > (top[pid][1], top[pid][0], top[pid][2]):
            top[pid] = pos
    # one probe per piece: its highest block (the first thing an incomplete build loses)
    probes = [{"piece": pid, "at": list(pos), "block": block_name(blocks[pos]),
               "check": "execute if block %d %d %d %s" % (pos + (block_name(blocks[pos]),))}
              for pid, pos in sorted(top.items())]
    return {"numbers": p["numbers"], "floors": p["floors"], "npcs": p["npcs"],
            "displays": [{k: v for k, v in d.items() if k != "command"} for d in p["displays"]],
            "blocks": len(blocks), "probes": probes}


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
    rep = report(p)
    if a.action == "plan":
        print(json.dumps(rep, indent=1))
        return 0
    write(files, a.out)
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "report.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print("wrote %d files to %s (%d blocks, %d displays, %d NPCs)" % (len(files), a.out, len(p["blocks"]),
                                                                       len(p["displays"]), len(p["npcs"])))
    for k, v in sorted(p["numbers"].items()):
        print("  %s = %s" % (k, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
