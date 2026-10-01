#!/usr/bin/env python
"""The ferry docks: the blocks that make a planned stop in data/ferries.json a real place on the water.

  python tools/ferry_docks.py report [--dock <id>] [--source-root <root>]
  python tools/ferry_docks.py build  [--out build/datapacks/cobblers_ferry_docks] [--source-root <root>]

WHY THIS EXISTS. data/ferries.json carries ten lines and sixteen docks, and on 2026-09-30 only one line could
run: `relic_row`, because only its two docks were built. Everything else - the Sunset strait, the Northlight
packet, the Tilpey launch, the postgame charters - was a charter on paper with no landing at one or both ends.
A dock is what makes a line real.

WHERE A DOCK SITS. Never from a world save (CLAUDE.md's ground rule; tests/test_ground_rule.py). Each record in
data/ferry_docks.json names the dock's `near` point (which data/ferries.json already carried, with its
`near_basis`) and the cardinal direction `out` it faces. From those two numbers and the canonical heightmap
(tools/ground.py, rounded) this tool derives the SHORE COLUMN by one rule, the same for every dock:

    the column nearest `near` that is dry (ground >= the water level), whose whole `width`-wide strip has at
    least `min_reach` water columns (ground < the water level) straight outward along `out`, and which has at
    least `min_dry` dry columns straight back landward; ties broken by distance, then z, then x.

The record also declares the shore column it was authored against. `report` derives it again from the heightmap
and REFUSES if the two disagree: if the heightmap moves under a dock, the dock fails rather than hanging in the
air. That is the point of writing the derivation down twice.

WATER LEVELS. The sea is data/world.json `vertical.sea_level` (62). Lake Tilpey is y77, measured plan data from
data/legendaries.json (Uxie's grotto mouth: "18 below the water level y77"); a lake record must name its source
and the tool refuses a level with no source.

THE DECK HEIGHT. deck_y = water level + 2, which is what every dock and pier already built here stands at:
`first_cast`'s jetty (tools/route_events.py, deck 64), `sunset_pier_south` and `sunset_pier_west`
(data/placements.json, planks at y64) - all sea level 62 plus 2. The sea town's rafts are a different thing: a
floating deck replacing the top water layer at y62 (tools/sea_town.py). A jetty is not a raft, so this tool
follows the jetties.

WHAT IT REFUSES, and why here rather than in an audit (the audit and the tests are another agent's -
CLAUDE.md principle 16 - and must replay the emitted text independently):

  shore          the derived shore column must equal the declared one (above)
  deck height    deck_y must be the water level + 2, the level read from data, never from this tool's output
  over water     every deck cell past the root must stand over water on the heightmap, and the head must have
                 at least `min_head_depth` blocks of it: a deck that does not meet the water is not a dock
  landward       the root must stand on dry ground, and the walk from the root inland must stay dry for
                 `min_dry` columns with no step over one block: a dock nobody can reach from land is not a dock
  placements     no cell may fall inside another placement's write extent (data/placements.json), nor inside a
                 spawn-free zone (data/spawn_suppression.json)
  spawn blocks   no block written may be a spawn condition (data/spawn_blocks.json, contract C4: a block a
                 spawn condition names decides encounters wherever it is placed)
  the ferrymen   data/ferries.json's own ferryman and landing for the dock must stand at ground + 1 on dry
                 ground, outside the dock's blocks, and at least 2 blocks apart (the same rule tools/ferries.py
                 applies at R17F; checked here so a bad edit fails at the cheap gate)
  commands       tools/function_limits.py: fills under the /fill limit, every write inside a forced chunk

THE RE-APPLY. This tool emits `cobblers:ferry_docks/<id>`; nothing in tools/reapply.py runs it yet. See
docs/world-building/FERRY_DOCKS.md for the step this needs and where it belongs in the order.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import ground as ground_mod  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_ferry_docks"
FUNCS = PACK / "data" / "cobblers" / "function" / "ferry_docks"
REPORT = ROOT / "derived" / "ferry_docks"
DOCKS = ROOT / "data" / "ferry_docks.json"
FERRIES = ROOT / "data" / "ferries.json"
WORLD = ROOT / "data" / "world.json"
PLACEMENTS = ROOT / "data" / "placements.json"
SUPPRESSION = ROOT / "data" / "spawn_suppression.json"
SPAWN_BLOCKS = ROOT / "data" / "spawn_blocks.json"
SCHEMA = "cobblers.ferry-docks/1"

# The ground rule (tests/test_ground_rule.py): nothing here reads a world at all.
WORLD_READS = set()

DIR = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}
# Minecraft yaw: 0 faces south (+z), 90 west (-x), 180 north (-z), -90 east (+x).
YAW = {"south": 0, "west": 90, "north": 180, "east": -90}

PLANK = "minecraft:spruce_planks"
GRAIN = "minecraft:stripped_spruce_wood"
PILE = "minecraft:spruce_log[axis=y]"
FENCE = "minecraft:spruce_fence"
LANTERN = "minecraft:lantern[hanging=false]"
STAIR = "minecraft:spruce_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]"
AIR = "minecraft:air"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


# ------------------------------------------------------------------------------------------------- the model
class Emit:
    """The blocks one dock writes, in order, as /setblock and /fill lines, with the cells kept for checking."""

    def __init__(self, dock_id, note):
        self.id = dock_id
        self.ops = ["# %s" % note]
        self.cells = {}

    def comment(self, text):
        self.ops.append("# %s" % text)

    def set(self, x, y, z, state):
        self.ops.append("setblock %d %d %d %s" % (x, y, z, state))
        self.cells[(x, y, z)] = state

    def fill(self, x0, y0, z0, x1, y1, z1, state):
        a = (min(x0, x1), min(y0, y1), min(z0, z1))
        b = (max(x0, x1), max(y0, y1), max(z0, z1))
        self.ops.append("fill %d %d %d %d %d %d %s" % (a[0], a[1], a[2], b[0], b[1], b[2], state))
        for x in range(a[0], b[0] + 1):
            for y in range(a[1], b[1] + 1):
                for z in range(a[2], b[2] + 1):
                    self.cells[(x, y, z)] = state

    def solid_cells(self):
        return {p: s for p, s in self.cells.items() if block_name(s) not in ("minecraft:air", "minecraft:cave_air")}

    def rect(self):
        if not self.cells:
            return None
        xs = [p[0] for p in self.cells]
        zs = [p[2] for p in self.cells]
        return [min(xs), min(zs), max(xs), max(zs)]


# ------------------------------------------------------------------------------------------------ the siting
def water_level(rec, world):
    w = rec["water"]
    if w["kind"] == "sea":
        return int(world["vertical"]["sea_level"]), "data/world.json vertical.sea_level"
    if w["kind"] == "lake":
        if not w.get("level_source"):
            raise SystemExit("%s: a lake water level needs level_source naming the measured plan data it "
                             "comes from" % rec["id"])
        # F7's shape, one level down (found by the F7 agent, 2026-09-30): this used to RETURN the record's own
        # `level`, so a dock's claim about water was tested against a number it supplied itself. The three
        # Tilpey docks happened to be right because lake_tilpey's authored level_y is also 77 - luck, not
        # construction. The landmark is the single definition now; `level` is kept as the record's reading and
        # asserted against it, so a disagreement is a loud error instead of a silent dry dock.
        import water_mask as WM
        body = w.get("body")
        if not body:
            raise SystemExit("%s: a lake dock needs water.body naming the landmark whose painted water it "
                             "stands in (one of %s)" % (rec["id"], ", ".join(sorted(WM.bodies()))))
        known = WM.bodies()
        if body not in known:
            raise SystemExit("%s: water.body %r is not a landmark with an authored water body (have: %s)"
                             % (rec["id"], body, ", ".join(sorted(known))))
        lvl = int(known[body]["level_y"])
        if int(w["level"]) != lvl:
            raise SystemExit("%s: water.level is %d but %s's authored level_y is %d. The landmark is the "
                             "definition; fix the record or the landmark, do not let them disagree"
                             % (rec["id"], int(w["level"]), body, lvl))
        return lvl, "data/landmarks.json %s water_body.level_y (the record's own reading agrees)" % body
    raise SystemExit("%s: water.kind %r is not sea or lake" % (rec["id"], w["kind"]))


def shore_column(g, near, out, level, radius, min_reach, min_dry, width=3):
    """THE RULE, written once: the dry column nearest `near` whose whole deck strip has water straight out and
    land straight back."""
    dx, dz = DIR[out]
    px, pz = lateral(out)
    half = (int(width) - 1) // 2
    offs = range(-half, half + 1)
    nx, nz = near
    best = None
    for x in range(nx - radius, nx + radius + 1):
        for z in range(nz - radius, nz + radius + 1):
            if g(x, z) < level:
                continue
            if not all(g(x + dx * i + px * k, z + dz * i + pz * k) < level
                       for i in range(1, min_reach + 1) for k in offs):
                continue
            if not all(g(x - dx * i, z - dz * i) >= level for i in range(0, min_dry + 1)):
                continue
            key = (round(math.hypot(x - nx, z - nz), 6), z, x)
            if best is None or key < best[0]:
                best = (key, (x, z))
    return best[1] if best else None


def axis_of(out):
    """(along, across) unit vectors for a dock facing `out`."""
    dx, dz = DIR[out]
    return (dx, dz), (dz, dx) if dx == 0 else (0, 1)


def lateral(out):
    return (1, 0) if DIR[out][0] == 0 else (0, 1)


def geometry(rec, g, level):
    """Every column of the dock, derived from the shore column: {root, deck, apron, rect, ...}."""
    out = rec["out"]
    (ax, az) = DIR[out]
    (px, pz) = lateral(out)
    sx, sz = rec["shore"]["at"]
    half = (int(rec.get("width", 3)) - 1) // 2
    length = int(rec.get("length", 0))

    def col(i, k):
        return (sx + ax * i + px * k, sz + az * i + pz * k)

    offs = range(-half, half + 1)
    deck = [col(i, k) for i in range(1, length + 1) for k in offs]
    step = [col(i, k) for i in (-1, 0) for k in offs]
    stairs = [col(-2, k) for k in offs]
    apron_half = (int(rec.get("apron_width", 5)) - 1) // 2
    apron = [col(i, k) for i in range(-int(rec.get("apron", 4)) - 2, -2) for k in range(-apron_half, apron_half + 1)]
    cells = deck + step + stairs + apron
    xs = [c[0] for c in cells] or [sx]
    zs = [c[1] for c in cells] or [sz]
    return {
        "out": out, "shore": (sx, sz), "along": (ax, az), "across": (px, pz), "half": half,
        "length": length, "deck": deck, "step": step, "stairs": stairs, "apron": apron,
        "deck_y": level + 2, "col": col, "offs": list(offs),
        "rect": [min(xs), min(zs), max(xs), max(zs)],
        "head": col(length, 0) if length else (sx, sz),
    }


# -------------------------------------------------------------------------------------------------- building
def build_dock(rec, g, level):
    geo = geometry(rec, g, level)
    deck_y = geo["deck_y"]
    e = Emit(rec["id"], "%s: %s (tools/ferry_docks.py)" % (rec["id"], rec["name"]))
    e.comment(rec["why"])
    ax, az = geo["along"]
    px, pz = geo["across"]
    sx, sz = geo["shore"]
    col = geo["col"]

    # the apron: a boarded forecourt laid AT the ground, so the heightmap ground under the ferryman is unchanged
    if geo["apron"]:
        e.comment("the forecourt, boarded flush with the ground: it does not lift the ground under the ferryman")
        for x, z in geo["apron"]:
            if g(x, z) >= level:
                e.set(x, g(x, z), z, PLANK)

    # headroom over everything that is walked, before anything is built into it
    e.comment("headroom over the deck and the steps")
    lo = col(-2, -geo["half"])
    hi = col(geo["length"], geo["half"])
    e.fill(lo[0], deck_y + 1, lo[1], hi[0], deck_y + 3, hi[1], AIR)

    # the landward steps: a stair, then two solid courses to the deck (first_cast's "step up")
    e.comment("the step up from the shore")
    for x, z in geo["stairs"]:
        if deck_y - 1 > g(x, z):
            e.set(x, deck_y - 1, z, STAIR % geo["out"])
    for x, z in geo["step"]:
        e.fill(x, g(x, z) + 1, z, x, deck_y, z, PLANK)

    # the deck, over the water
    e.comment("the deck, %d columns out over the water at y%d" % (geo["length"], deck_y))
    for i in range(1, geo["length"] + 1):
        for k in geo["offs"]:
            x, z = col(i, k)
            e.set(x, deck_y, z, PLANK if (x + z) % 4 else "%s[axis=%s]" % (GRAIN, "x" if ax else "z"))
        if i % 4 == 0:
            for k in (-geo["half"], geo["half"]):
                x, z = col(i, k)
                if g(x, z) + 1 <= deck_y - 1:
                    e.fill(x, g(x, z) + 1, z, x, deck_y - 1, z, PILE)
                e.set(x, deck_y + 1, z, FENCE)

    # the head: two mooring posts with lanterns on them
    e.comment("the head: mooring posts and their lanterns")
    for k in (-geo["half"], geo["half"]):
        x, z = col(geo["length"], k)
        e.set(x, deck_y + 1, z, FENCE)
        e.set(x, deck_y + 2, z, LANTERN)
    return e, geo


def build_quay(rec, g, level):
    """A quay head: a boarded forecourt at the ground beside a pier another tool already built, with bollards.
    No deck of its own - the pier IS the deck, and this tool does not rebuild another tool's blocks. Its rect is
    AUTHORED, not derived, because it has to keep out of the pier's own cells in data/placements.json."""
    geo = geometry(rec, g, level)
    x0, z0, x1, z1 = rec["apron_rect"]
    geo["apron"] = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    geo["length"] = 0
    e = Emit(rec["id"], "%s: %s (tools/ferry_docks.py)" % (rec["id"], rec["name"]))
    e.comment(rec["why"])
    e.comment("the quay head beside %s: boards at the ground, bollards, lanterns. The pier is the deck"
              % rec["host"]["placement"])
    for x, z in geo["apron"]:
        if g(x, z) >= level:
            e.set(x, g(x, z), z, PLANK)
    for x, z in rec["bollards"]:
        e.set(x, g(x, z) + 1, z, FENCE)
        e.set(x, g(x, z) + 2, z, LANTERN)
    geo["rect"] = e.rect()
    geo["head"] = tuple(rec["shore"]["at"])
    return e, geo


def build_one(rec, g, level):
    kind = rec["structure"]
    if kind == "jetty":
        return build_dock(rec, g, level)
    if kind == "quay_head":
        return build_quay(rec, g, level)
    if kind == "host":
        e = Emit(rec["id"], "%s: built by %s; this tool writes no block" % (rec["id"], rec["host"]["built_by"]))
        return e, {"deck_y": level + 2, "length": 0, "apron": [], "deck": [], "rect": None,
                   "head": tuple(rec["near"]), "along": DIR[rec["out"]], "shore": tuple(rec["near"])}
    raise SystemExit("%s: structure %r is not jetty, quay_head or host" % (rec["id"], kind))


# -------------------------------------------------------------------------------------------------- refusals
class Occupancy:
    """The columns data/placements.json writes a block into, by placement id.

    A bounding rect is not enough: `sunset_west_lights` is lanterns scattered over a whole town, and its rect
    swallows every street between them. So the rect is only a prefilter, and a candidate's commands are expanded
    into real columns before anything is called an overlap."""

    NUM = re.compile(r"(-?\d+) (-?\d+) (-?\d+)")

    def __init__(self, doc):
        self.rects = []
        self.cmds = {}
        for p in doc["placements"]:
            xs, zs = [], []
            cmds = [c for c in (p.get("commands") or []) if not c.lstrip().startswith("#")]
            for c in cmds:
                for m in self.NUM.finditer(c):
                    x, _y, z = (int(v) for v in m.groups())
                    xs.append(x)
                    zs.append(z)
            if xs:
                self.rects.append((p["id"], min(xs), min(zs), max(xs), max(zs)))
                self.cmds[p["id"]] = cmds
        self.ids = {p["id"] for p in doc["placements"]}

    def columns(self, pid):
        """Every (x, z) the placement writes a block other than air into."""
        out = set()
        for c in self.cmds.get(pid, []):
            parts = c.split()
            if parts[0] == "setblock" and len(parts) >= 5:
                if block_name(parts[4]) in ("minecraft:air", "minecraft:cave_air"):
                    continue
                out.add((int(parts[1]), int(parts[3])))
            elif parts[0] == "fill" and len(parts) >= 8:
                if block_name(parts[7]) in ("minecraft:air", "minecraft:cave_air"):
                    continue
                x0, _y0, z0, x1, _y1, z1 = (int(v) for v in parts[1:7])
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        out.add((x, z))
        return out

    def hits(self, cols):
        """The placements that write a block into any of `cols`, a set of (x, z)."""
        xs = [c[0] for c in cols]
        zs = [c[1] for c in cols]
        x0, z0, x1, z1 = min(xs), min(zs), max(xs), max(zs)
        out = []
        for pid, a, b, c, d in self.rects:
            if c < x0 or a > x1 or d < z0 or b > z1:
                continue
            if self.columns(pid) & cols:
                out.append(pid)
        return out


def spawn_free_hits(rect, doc):
    x0, z0, x1, z1 = rect
    out = []
    for zone in doc["spawn_free_zones"]:
        a, b, c, d = zone["box"]
        if not (c < x0 or a > x1 or d < z0 or b > z1):
            out.append(zone["id"])
    return out


def check(rec, e, geo, g, level, level_src, ferries, occ, suppression, spawn_blocks):
    """Everything this tool refuses to write. Compared with the data and the heightmap, never with the model."""
    bad = []
    did = rec["id"]
    docks = {d["id"]: d for d in ferries["docks"]}

    # --- the dock is a dock, and a stop on a line
    if did not in docks:
        bad.append("%s is not a dock in data/ferries.json" % did)
        return bad
    if not any(did in ln["stops"] for ln in ferries["lines"]):
        bad.append("%s: no line in data/ferries.json stops here; a dock nothing calls at is not built" % did)
    if docks[did].get("near") and list(docks[did]["near"]) != list(rec["near"]):
        bad.append("%s: near %s disagrees with data/ferries.json's %s; the dock moved and this record did not"
                   % (did, rec["near"], docks[did]["near"]))

    # --- the shore column, derived again from the heightmap. A `host` dock stands on somebody else's built
    # jetty (its deck, not the heightmap), so the shore rule does not apply to it: its ground comes from the
    # settlement's own measured plan data and the ferryman check below is what holds it honest.
    if rec["structure"] == "host":
        if not rec.get("settlement"):
            bad.append("%s: a host dock must name the settlement whose measured ground it stands on" % did)
        if rec["host"]["built_by"] not in (docks[did].get("built_by") or ""):
            bad.append("%s: data/ferries.json built_by does not name %s, the tool that builds this dock"
                       % (did, rec["host"]["built_by"]))
        return bad + ferryman_problems(rec, e, g, level, docks[did])
    found = shore_column(g, rec["near"], rec["out"], level, int(rec["shore"]["search_radius"]),
                         int(rec["shore"]["min_reach"]), int(rec["shore"]["min_dry"]), int(rec.get("width", 3)))
    if found is None:
        bad.append("%s: no column within %d of %s is dry with %d water columns out to the %s and %d dry back: "
                   "the heightmap has no shore here" % (did, rec["shore"]["search_radius"], rec["near"],
                                                        rec["shore"]["min_reach"], rec["out"],
                                                        rec["shore"]["min_dry"]))
        return bad
    if list(found) != list(rec["shore"]["at"]):
        bad.append("%s: the shore rule finds %s on the heightmap, but the record was authored against %s. The "
                   "ground moved under this dock; re-site it, do not edit the number"
                   % (did, list(found), rec["shore"]["at"]))

    # --- the deck stands at the water line
    if geo["deck_y"] != level + 2:
        bad.append("%s: deck y%d, but the water level is y%d (%s) and a jetty deck stands 2 above it"
                   % (did, geo["deck_y"], level, level_src))

    if rec["structure"] == "jetty":
        # --- every deck column under the water that is actually PAINTED, not merely under a level.
        # F7: a column can be below a lake's level and outside its basin polygons, where nothing is painted
        # and the dock stands dry. tools/water_mask.py is the one definition; it is given the whole deck,
        # because a footprint half out of the lake is half dry.
        import water_mask as WM
        body = "sea" if rec["water"]["kind"] == "sea" else rec["water"]["body"]
        bad += ["%s: %s" % (did, m) for m in
                WM.claim(body, geo["deck"], g, min_submersion=1, label="dock %s deck" % did)]
        dry = [(x, z, g(x, z)) for x, z in geo["deck"] if g(x, z) >= level]
        if dry:
            bad.append("%s: %d deck cell(s) do not stand over water (the water level is y%d); first %s"
                       % (did, len(dry), level, dry[:3]))
        hx, hz = geo["head"]
        depth = level - g(hx, hz)
        if depth < int(rec["min_head_depth"]):
            bad.append("%s: the head at %s has %d block(s) of water under it; the record asks for %d. A deck "
                       "that does not reach the water is not a dock" % (did, [hx, hz], depth, rec["min_head_depth"]))
        # --- the landward walk: dry, and no step over one block
        ax, az = geo["along"]
        sx, sz = geo["shore"]
        walk = [(sx - ax * i, sz - az * i) for i in range(0, int(rec["shore"]["min_dry"]) + 1)]
        hs = [g(x, z) for x, z in walk]
        if min(hs) < level:
            bad.append("%s: the walk inland from the root dips to y%d, under the water level y%d: the dock has "
                       "no walkable connection to land" % (did, min(hs), level))
        jumps = [(walk[i], hs[i], hs[i + 1]) for i in range(len(hs) - 1) if abs(hs[i + 1] - hs[i]) > 1]
        if jumps:
            bad.append("%s: the walk inland steps more than one block at %s (y%d to y%d): nobody walks that"
                       % (did, list(jumps[0][0]), jumps[0][1], jumps[0][2]))

    if rec["structure"] in ("quay_head", "host"):
        # a dock that leans on somebody else's blocks: that somebody has to exist, and have been built
        host = rec["host"]
        if host.get("placement") and host["placement"] not in occ.ids:
            bad.append("%s: its host placement %r is not in data/placements.json; the quay leans on nothing"
                       % (did, host["placement"]))

    # the forecourt is walked: every board must lie on dry ground
    wet = [(x, z, g(x, z)) for x, z in geo["apron"] if g(x, z) < level]
    if wet:
        bad.append("%s: %d forecourt cell(s) stand in water (the water level is y%d); first %s"
                   % (did, len(wet), level, wet[:3]))

    # --- nothing over another placement, nothing in a spawn-free zone
    rect = e.rect()
    cols = {(x, z) for x, _y, z in e.solid_cells()}
    if rect and cols:
        hit = occ.hits(cols)
        if hit:
            bad.append("%s: its blocks %s land on columns %s already writes in data/placements.json"
                       % (did, rect, hit[:4]))
        zones = spawn_free_hits(rect, suppression)
        if zones:
            bad.append("%s: its blocks %s fall inside spawn-free zone(s) %s" % (did, rect, zones))

    # --- no block a spawn condition names (data/spawn_blocks.json, contract C4)
    named = sorted({block_name(s) for s in e.cells.values() if block_name(s) in spawn_blocks["blocks"]})
    if named:
        bad.append("%s: writes %s, which data/spawn_blocks.json lists as spawn condition block(s): a dock would "
                   "decide encounters wherever it stands" % (did, named))

    return bad + ferryman_problems(rec, e, g, level, docks[did])


def ferryman_problems(rec, e, g, level, d):
    """The ferryman and the landing data/ferries.json carries for this dock: the same rule tools/ferries.py
    applies at R17F, checked here so a bad edit fails at the cheap gate instead of at the re-apply."""
    bad = []
    did = rec["id"]
    if d.get("status") != "built":
        bad.append("%s: data/ferries.json still calls it %r; a dock this tool builds is built"
                   % (did, d.get("status")))
    solid = e.solid_cells()
    for part in ("ferryman", "landing"):
        spot = (d.get(part) or {}).get("at")
        if not (isinstance(spot, list) and len(spot) == 3):
            bad.append("%s: data/ferries.json has no %s.at [x, y, z]" % (did, part))
            continue
        x, y, z = spot
        gy = g(x, z)
        if gy < level:
            bad.append("%s %s at %s: the ground there is y%d, under the water level y%d" % (did, part, spot, gy, level))
        elif y != gy + 1:
            bad.append("%s %s at %s: stands at y%d but its ground is y%d, so it must stand at y%d"
                       % (did, part, spot, y, gy, gy + 1))
        for dy in (0, 1):
            if (x, y + dy, z) in solid:
                bad.append("%s %s at %s: this dock writes %s into the cell at y%d"
                           % (did, part, spot, solid[(x, y + dy, z)], y + dy))
        for x0, z0, x1, z1 in d.get("keep_clear") or []:
            if x0 <= x <= x1 and z0 <= z <= z1:
                bad.append("%s %s at %s: inside the dock's own keep-clear box %s" % (did, part, spot, [x0, z0, x1, z1]))
    fm, la = (d.get("ferryman") or {}).get("at"), (d.get("landing") or {}).get("at")
    if fm and la and math.dist(fm, la) < 2:
        bad.append("%s: its landing is within 2 blocks of its ferryman: an arrival lands in the NPC" % did)
    return bad


# ---------------------------------------------------------------------------------------------------- output
def summary(rec, e, geo, level, level_src, ferries):
    d = {x["id"]: x for x in ferries["docks"]}[rec["id"]]
    lines = [ln["id"] for ln in ferries["lines"] if rec["id"] in ln["stops"]]
    return {
        "id": rec["id"], "name": rec["name"], "structure": rec["structure"],
        "near": rec["near"], "out": rec["out"], "shore": (rec.get("shore") or {}).get("at"),
        "water_level": level, "water_level_source": level_src, "deck_y": geo["deck_y"],
        "length": geo["length"], "head": list(geo["head"]), "rect": e.rect(),
        "ferryman": (d.get("ferryman") or {}).get("at"), "landing": (d.get("landing") or {}).get("at"),
        "lines": lines, "commands": len([l for l in e.ops if not l.startswith("#")]),
        "cells": len(e.cells), "landward": rec["landward"],
    }


def write_function(name, lines):
    cmds = function_limits.ensure_loaded(lines)
    refused = function_limits.check_lines(cmds, name)
    if refused:
        raise SystemExit("%s: %d command(s) the server would refuse: %s" % (name, len(refused), refused[:3]))
    (FUNCS / ("%s.mcfunction" % name)).write_text("\n".join(cmds) + "\n", encoding="utf-8")
    return cmds


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("report", "build"):
        q = sub.add_parser(name)
        q.add_argument("--dock", default=None, help="one dock only (default: every record)")
        q.add_argument("--source-root", default=None)
        if name == "build":
            q.add_argument("--out", default=str(PACK))
    a = p.parse_args(argv)
    if a.source_root:
        os.environ["COBBLERS_SOURCE_ROOT"] = a.source_root

    doc = load(DOCKS)
    if doc.get("schema") != SCHEMA:
        raise SystemExit("data/ferry_docks.json: schema is %r, expected %r" % (doc.get("schema"), SCHEMA))
    recs = [r for r in doc["docks"] if not a.dock or r["id"] == a.dock]
    if not recs:
        raise SystemExit("no dock record %r in data/ferry_docks.json (fail closed)" % a.dock)

    world = load(WORLD)
    ferries = load(FERRIES)
    occ = Occupancy(load(PLACEMENTS))
    suppression = load(SUPPRESSION)
    spawn_blocks = load(SPAWN_BLOCKS)
    base = ground_mod.load()

    out, problems = [], []
    for rec in recs:
        # a dock inside a settlement that does not stand on the heightmap (the sea town's decks, the islet, the
        # cavern floor) takes that settlement's own measured plan ground - still never a world save
        g = base if not rec.get("settlement") else ground_mod.for_settlement(rec["settlement"],
                                                                            base=ground_mod.load())
        level, level_src = water_level(rec, world)
        e, geo = build_one(rec, g, level)
        problems += check(rec, e, geo, g, level, level_src, ferries, occ, suppression, spawn_blocks)
        out.append((rec, e, geo, summary(rec, e, geo, level, level_src, ferries)))

    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "report.json").write_text(json.dumps({"docks": [s for _r, _e, _g, s in out]}, indent=1) + "\n",
                                        encoding="utf-8")
    for _r, _e, _g, s in out:
        print("%-24s %-10s shore %-14s deck y%-3d %2d long, head %-14s -> %s"
              % (s["id"], s["structure"], str(s["shore"]), s["deck_y"], s["length"], str(s["head"]),
                 ", ".join(s["lines"])))
        if a.cmd == "report":
            print("   landward: %s" % s["landward"])

    if problems:
        print("\n%d PROBLEM(S):" % len(problems), file=sys.stderr)
        for m in problems:
            print("  " + m, file=sys.stderr)
        return 1

    if a.cmd == "build":
        if PACK.exists():
            shutil.rmtree(PACK)
        FUNCS.mkdir(parents=True)
        (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                          "Cobblers: the ferry docks (tools/ferry_docks.py)"}}, indent=2) + "\n",
                                          encoding="utf-8")
        done = []
        for rec, e, _geo, _s in out:
            if rec["structure"] == "host":
                continue
            write_function(rec["id"], e.ops)
            done.append(rec["id"])
        (FUNCS / "index.txt").write_text("\n".join(done) + "\n", encoding="utf-8")
        print("wrote %s (%d function(s))" % (PACK, len(done)))
    else:
        print("\n%d dock(s) checked, no problem" % len(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
