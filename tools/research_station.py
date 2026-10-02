#!/usr/bin/env python
"""The legendary and mythical research station on the west sea coast, from data/research_station.json.

The owner, 2026-10-02, on the approved proposal (docs/world-building/RESEARCH_STATION.md): "Shrew Lake south shore,
the Latias and Latios shrine, hold every item until EXP-048 proves an altar responds, Moltres yes, no waystone,
surveyor stays at the dig camp"; and later the same day, moving it: "research station should be near 552 2812 not the
lake". Everything but the site stands. Every part is an existing, proven piece; nothing here is new machinery:

  the strand     four buildings on the coast's dry ground (the Institute, the Archive, the bunkhouse, the wet lab),
                 seated the repository's way: the floor on max(ground under the walls) + 1, ground from tools/ground.py
                 (the canonical heightmap, rounded), never a world. The ground between them is paved in the station's
                 signature tuff and copper where it is dry; trees and plants are cleared from the water's level + 1 up,
                 which no water reaches.
  the walks      jetty, junction, bridge, the spine boardwalk, the pier and the platforms: data/sea_town.json's rules.
                 A deck block replaces the top water layer, so it is AT the water's level (the sea's y62, data/world.json)
                 and the walk one above. Every column is re-measured (tools/water_mask.py's rule, level_at: the site's
                 body of water where the ground is below its level, a lake inside its basin before the sea) and a deck
                 over water shallower than its kind's min_depth, or over ground above the deck, is refused.
  the shrine     the Eon shrine on the platform: lumymon:latias_altar and lumymon:latios_altar, set directly by
                 setblock on a tuff dais, and the lumymon:summon_anchor between them. No template.
  the study pool NOT in this pack: one ACTIVATED Habitat Block in data/habitat_blocks.json (placed with every other
                 block, R9E) set in a post under the study deck; this pack writes that post, so it must run BEFORE R9E
                 (tools/lopunny_house.py's rule).
  the people     NOT in this pack: four conversations in data/dialogue.json and four quests in data/quests.json,
                 compiled with every other one by tools/compile_dialogue.py --all, and placed by R9F from
                 data/rewards.json (npc_grant), as Hopgood and the Abandoned Cut's digger are.
  the hold       data/research_station.json economy.issuing, THE ONE SWITCH. This pack's tick function keeps the tags
                 every item route requires: false (today) REMOVES them from every player, and the earning
                 advancements are not shipped at all; true adds them and ships the advancements. See economy.switch.
                 Under it the crown (post_champion_cap) and the Eon dews (eon_issuing) each keep a hold of their own,
                 so the switch thrown for the three feathers (the owner, 2026-10-02) issues the feathers only.

  python tools/research_station.py build   [--source-root R] [--out DIR] [--data FILE]   write the pack
  python tools/research_station.py plan    [--source-root R]                              the numbers; writes nothing
  python tools/research_station.py cleanup [--source-root R] [--old-rev REV] [--out DIR]
                 STAGING ONLY, one-off: the first station, on Shrew Lake's south strand as built from REV (42ce560),
                 put back to the heightmap world wherever this build does not write, and its four NPCs removed at
                 their old seats; -> build/staging/cobblers_research_station_cleanup (outside build/datapacks, so
                 tools/reapply.py's coverage check never asks a step for it). See cleanup().

The re-application (tools/reapply.py is not edited here): placement_steps() is the step, BEFORE R9E.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "research_station.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_research_station"
CLEANUP_OUT = ROOT / "build" / "staging" / "cobblers_research_station_cleanup"
OLD_REV = "42ce560"   # the commit whose tools/research_station.py and data/research_station.json built the lake station
SCHEMA = "cobblers.research-station/1"
NS = "cobblers"
FN = "research_station"
PACK_FORMAT = 48  # Minecraft 1.21.1
ZONES = ("strand", "crossing", "platform", "study_pool")
SIDES = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}
SIGN_ROTATION = {"south": 0, "west": 4, "north": 8, "east": 12}
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class StationError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise StationError("%s: schema must be %s" % (path, SCHEMA))
    seen = {}
    for zone in ZONES:
        z = doc["zones"][zone]
        for key in ("walks", "buildings", "signs"):
            for i in z.get(key) or []:
                if i in seen:
                    raise StationError("%s is in two zones: %s and %s" % (i, seen[i], zone))
                seen[i] = zone
    for key in ("walks", "buildings", "signs"):
        for rec in doc[key]:
            if rec["id"] not in seen:
                raise StationError("%s %s belongs to no zone" % (key[:-1], rec["id"]))
    return doc


def _base(state):
    return state.split("[")[0].split("{")[0]


def in_rect(x, z, r):
    return r[0] <= x <= r[2] and r[1] <= z <= r[3]


def cells(r):
    return [(x, z) for x in range(r[0], r[2] + 1) for z in range(r[1], r[3] + 1)]


def standing_sign(facing, lines):
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
    return "minecraft:spruce_sign[rotation=%d]{front_text:{messages:[%s]}}" % (SIGN_ROTATION[facing], q)


def fence(n=False, s=False, e=False, w=False):
    b = lambda v: "true" if v else "false"  # noqa: E731
    return "minecraft:spruce_fence[east=%s,north=%s,south=%s,waterlogged=false,west=%s]" % (b(e), b(n), b(s), b(w))


def pane(axis):
    if axis == "x":
        return "minecraft:glass_pane[east=true,north=false,south=false,waterlogged=false,west=true]"
    return "minecraft:glass_pane[east=false,north=true,south=true,waterlogged=false,west=false]"


LANTERN = "minecraft:lantern[hanging=false,waterlogged=false]"
HANGING = "minecraft:lantern[hanging=true,waterlogged=false]"


# ------------------------------------------------------------------------------------------------------------ water
class Surface:
    """tools/water_mask.py level_at(), with each lake's basin boxed first so a column far from every lake is not
    ray-cast against every basin: (body id, surface y) for the painted water over a column, or (None, None)."""

    def __init__(self, g):
        import water_mask as W
        self.g, self.W = g, W
        self.bodies = W.bodies()
        self.sea = W.sea_level()
        self.boxes = {}
        for bid, b in self.bodies.items():
            pts = [q for ring in b["basin"] for q in ring]
            if pts:
                self.boxes[bid] = (min(q[0] for q in pts), min(q[1] for q in pts),
                                   max(q[0] for q in pts), max(q[1] for q in pts))

    def at(self, x, z):
        h = self.g(x, z)
        best = (None, None)
        for bid, (x0, z0, x1, z1) in self.boxes.items():
            b = self.bodies[bid]
            if h < b["level_y"] and x0 <= x <= x1 and z0 <= z <= z1 and self.W.in_polygons(b["basin"], x, z):
                if best[1] is None or b["level_y"] > best[1]:
                    best = (bid, b["level_y"])
        if best[0] is not None:
            return best
        return ("sea", self.sea) if h < self.sea else (None, None)


class Water:
    """Depth of the site's body of water (site.water: "sea", or a lake's landmark id) by tools/water_mask.py's rule."""

    def __init__(self, doc, g):
        self.g = g
        self.s = Surface(g)
        body = doc["site"]["water"]
        if body == "sea":
            self.level = self.s.sea
        elif body in self.s.bodies:
            self.level = self.s.bodies[body]["level_y"]
        else:
            raise StationError("site.water %r is neither \"sea\" nor a water body in data/landmarks.json" % body)
        if self.level != doc["site"]["level_y"]:
            raise StationError("site.level_y %s is not %s's level y%s (data/world.json, data/landmarks.json)"
                               % (doc["site"]["level_y"], body, self.level))
        self.body = body
        self._cache = {}

    def depth(self, x, z):
        """Blocks of the site's water over the column, or None where it is dry (or another body's water)."""
        k = (x, z)
        if k not in self._cache:
            bid, level = self.s.at(x, z)
            self._cache[k] = (level - self.g(x, z)) if bid == self.body else None
        return self._cache[k]


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """Per zone, two passes of blocks {(x, y, z): state}: the structure, then what hangs on it (a lantern, a sign, a
    ladder, a banner), so nothing attached is placed before what holds it. Doors are their own ordered pairs."""

    def __init__(self, doc, g):
        self.doc, self.g = doc, g
        self.w = Water(doc, g)
        self.level = self.w.level
        self.allowed = set(doc["blocks"]["ids"])
        self.zone = None
        self.solid = {z: {} for z in ZONES}
        self.hung = {z: {} for z in ZONES}
        self.doors = {z: [] for z in ZONES}
        self.clear = {z: [] for z in ZONES}       # (x0, y0, z0, x1, y1, z1) cleared of plants first
        self.floors = {}                           # building id -> floor block y
        self.walk_cells = {}                       # (x, z) -> walk id, the deck columns
        self.lit_cells = []                        # (x, y, z): feet places the light model must reach
        self.npcs = {}
        self.habitat = None
        self.lanterns = []

    def _check(self, state):
        if _base(state) not in self.allowed:
            raise StationError("%s is not in data/research_station.json blocks.ids" % _base(state))

    def put(self, x, y, z, state):
        self._check(state)
        self.solid[self.zone][(x, y, z)] = state

    def hang(self, x, y, z, state):
        self._check(state)
        self.hung[self.zone][(x, y, z)] = state
        if _base(state) == "minecraft:lantern":
            self.lanterns.append((x, y, z))

    def door(self, x, y, z, facing):
        for half, d in (("lower", 0), ("upper", 1)):
            st = "minecraft:spruce_door[facing=%s,half=%s,hinge=left,open=false,powered=false]" % (facing, half)
            self._check(st)
            self.doors[self.zone].append(((x, y + d, z), st))

    def blocks(self, zone=None):
        out = {}
        for zn in ([zone] if zone else ZONES):
            out.update(self.solid[zn])
            out.update(self.hung[zn])
            out.update(dict(self.doors[zn]))
        return out


def zone_of(doc, key, rid):
    for zone in ZONES:
        if rid in (doc["zones"][zone].get(key) or []):
            return zone
    raise StationError("%s belongs to no zone" % rid)


# ------------------------------------------------------------------------------------------------------------ walks
def holes(doc):
    d = doc["dive"]
    (cx, cz), n = d["at"], d["half"]
    return {(x, z) for x in range(cx - n, cx + n + 1) for z in range(cz - n, cz + n + 1)}


def building_rects(doc):
    return {b["id"]: b["rect"] for b in doc["buildings"]}


def walks(p):
    doc, w, L = p.doc, p.w, p.level
    rules = doc["rules"]
    pav = doc["paving"]
    hole = holes(doc)
    rects = building_rects(doc)
    for wk in doc["walks"]:
        for c in cells(wk["rect"]):
            if c in p.walk_cells:
                raise StationError("walk %s overlaps walk %s at %s" % (wk["id"], p.walk_cells[c], c))
            p.walk_cells[c] = wk["id"]
    for wk in doc["walks"]:
        p.zone = zone_of(doc, "walks", wk["id"])
        kind, r = wk["kind"], wk["rect"]
        need = rules["min_depth"][kind]
        x0, z0, x1, z1 = r
        for x, z in cells(r):
            d = w.depth(x, z)
            if d is None:
                if kind not in rules["landfall_kinds"] or p.g(x, z) != L:
                    raise StationError("walk %s (%s) at (%d, %d) stands on ground y%d, above the deck y%d"
                                       % (wk["id"], kind, x, z, p.g(x, z), L))
            elif d < need:
                raise StationError("walk %s (%s) at (%d, %d) is over %d of water; its kind needs %d"
                                   % (wk["id"], kind, x, z, d, need))
        p.clear[p.zone].append((x0, L + 1, z0, x1, L + rules["clear_above"], z1))
        under = {c for b in doc["buildings"] if b["on"] == "deck" for c in cells(b["rect"])}
        for x, z in cells(r):
            if (x, z) in hole:
                continue
            framed = x1 - x0 >= 2 and z1 - z0 >= 2
            if wk.get("deck") == "platform":
                st = pav["platform"]
            elif framed and z in (z0, z1):
                st = "%s[axis=x]" % pav["frame"]
            elif framed and x in (x0, x1):
                st = "%s[axis=z]" % pav["frame"]
            else:
                st = pav["deck"]
            p.put(x, L, z, st)
            if (x, z) not in under:
                p.lit_cells.append((x, L + 1, z))
        # posts: at every corner and every post_every along each edge, where there is water to stand in
        every = rules["post_every"]
        posts = set()
        for x in range(x0, x1 + 1):
            if (x - x0) % every == 0 or x == x1:
                posts |= {(x, z0), (x, z1)}
        for z in range(z0, z1 + 1):
            if (z - z0) % every == 0 or z == z1:
                posts |= {(x0, z), (x1, z)}
        for x, z in sorted(posts):
            if (x, z) in hole or p.w.depth(x, z) is None:
                continue
            for y in range(p.g(x, z) + 1, L):
                p.put(x, y, z, "%s[axis=y]" % pav["post"])
        rails_and_lamps(p, wk, under, rects)


def outward(r, x, z):
    """The sides of the rect this edge cell faces out of."""
    out = []
    if z == r[1]:
        out.append("north")
    if z == r[3]:
        out.append("south")
    if x == r[0]:
        out.append("west")
    if x == r[2]:
        out.append("east")
    return out


def rails_and_lamps(p, wk, under, rects):
    doc, L = p.doc, p.level
    r = wk["rect"]
    x0, z0, x1, z1 = r
    hole = holes(doc)
    every = doc["rules"]["lamp_every"]
    narrow = min(x1 - x0, z1 - z0) <= 2

    def opening(x, z, side):
        dx, dz = SIDES[side]
        n = (x + dx, z + dz)
        return n in p.walk_cells or any(in_rect(n[0], n[1], rr) for rr in rects.values())

    railed = set()
    if wk.get("rails"):
        for x, z in cells(r):
            sides = outward(r, x, z)
            if not sides or (x, z) in under or (x, z) in hole:
                continue
            if all(opening(x, z, s) for s in sides):
                continue
            railed.add((x, z))
    lamps = set()
    if narrow:
        long_x = (x1 - x0) >= (z1 - z0)
        n = (x1 - x0 + 1) if long_x else (z1 - z0 + 1)
        for i in range(n):
            if long_x:
                a, b = (x0 + i, z0), (x0 + i, z1)
            else:
                a, b = (x0, z0 + i), (x1, z0 + i)
            if i % every == 0:
                lamps.add(a)
            if i % every == every // 2:
                lamps.add(b)
    else:
        for x, z in cells(r):
            sides = outward(r, x, z)
            if not sides:
                continue
            corner = len(sides) == 2
            along = (x - x0) if sides[0] in ("north", "south") else (z - z0)
            if corner or along % every == 0:
                lamps.add((x, z))
    lamps = {c for c in lamps if c not in under and c not in hole
             and not any(opening(c[0], c[1], s) for s in outward(r, *c))}
    for x, z in sorted(railed - lamps):
        def conn(dx, dz):
            n = (x + dx, z + dz)
            return n in railed or n in lamps
        p.put(x, L + 1, z, fence(n=conn(0, -1), s=conn(0, 1), e=conn(1, 0), w=conn(-1, 0)))
    for x, z in sorted(lamps):
        def conn(dx, dz):
            n = (x + dx, z + dz)
            return n in railed
        p.put(x, L + 1, z, fence(n=conn(0, -1), s=conn(0, 1), e=conn(1, 0), w=conn(-1, 0)))
        p.put(x, L + 2, z, fence())
        p.hang(x, L + 3, z, LANTERN)
    for c in railed | lamps:
        if (c[0], L + 1, c[1]) in p.lit_cells:
            p.lit_cells.remove((c[0], L + 1, c[1]))


# ------------------------------------------------------------------------------------------------------------ buildings
def seat(p, b):
    if b["on"] == "deck":
        for x, z in cells(b["rect"]):
            if (x, z) not in p.walk_cells:
                raise StationError("building %s stands off its deck at (%d, %d)" % (b["id"], x, z))
        return p.level
    above = p.doc["rules"]["land_above_level"]
    for x, z in cells(b["rect"]):
        if p.w.depth(x, z) is not None:
            raise StationError("building %s stands in the water at (%d, %d)" % (b["id"], x, z))
        if p.g(x, z) < p.level + above:
            raise StationError("building %s stands on ground y%d at (%d, %d), under the water's level + %d"
                               % (b["id"], p.g(x, z), x, z, above))
    return max(p.g(x, z) for x, z in cells(b["rect"])) + 1


def building(p, b):
    doc = p.doc
    p.zone = zone_of(doc, "buildings", b["id"])
    pal = doc["palettes"][b["palette"]]
    x0, z0, x1, z1 = b["rect"]
    H = b["height"]
    f = seat(p, b)
    p.floors[b["id"]] = f
    p.clear[p.zone].append((x0 - 1, f + 1, z0 - 1, x1 + 1, f + H + 2 + doc["rules"]["clear_above"], z1 + 1))
    side, at = b["door"]["side"], b["door"]["at"]
    dx, dz = SIDES[side]
    door_xz = (at, z0 if side == "north" else z1) if side in ("north", "south") else (x0 if side == "west" else x1, at)
    if b["on"] == "land":
        for x, z in cells(b["rect"]):
            for y in range(p.g(x, z) + 1, f):
                p.put(x, y, z, pal["foundation"])
    for x, z in cells(b["rect"]):
        ring = x in (x0, x1) or z in (z0, z1)
        inner = not ring
        if b.get("glass_floor") and inner and not (x in (x0 + 1, x1 - 1) or z in (z0 + 1, z1 - 1)):
            p.put(x, f, z, "minecraft:glass")
        else:
            p.put(x, f, z, pal["floor"])
        for dy in range(1, H + 1):
            if inner:
                p.put(x, f + dy, z, "minecraft:air")
            elif x in (x0, x1) and z in (z0, z1):
                p.put(x, f + dy, z, "%s[axis=y]" % pal["corner"])
            elif dy == H:
                st = pal["band"]
                if "log" in st:
                    st += "[axis=%s]" % ("x" if z in (z0, z1) else "z")
                p.put(x, f + dy, z, st)
            else:
                p.put(x, f + dy, z, pal["wall"])
        if inner:
            p.lit_cells.append((x, f + 1, z))
    # windows: panes at dy 2-3 every third block of each wall, away from the corners and the door
    if b.get("windows", True):
        for x, z in cells(b["rect"]):
            if (x in (x0, x1)) == (z in (z0, z1)):
                continue
            if abs(x - door_xz[0]) + abs(z - door_xz[1]) <= 1:
                continue
            along = (x - x0) if z in (z0, z1) else (z - z0)
            if along % 3 != 2:
                continue
            for dy in (2, 3):
                if dy < H:
                    p.put(x, f + dy, z, pane("x" if z in (z0, z1) else "z"))
    # the roof: flat copper over the walls, a slab lip one block out
    for x in range(x0 - 1, x1 + 2):
        for z in range(z0 - 1, z1 + 2):
            if in_rect(x, z, b["rect"]):
                p.put(x, f + H + 1, z, pal["roof"])
            else:
                p.put(x, f + H + 1, z, pal["roof_edge"] + "[type=bottom,waterlogged=false]")
    # the door, and on land the steps down to the ground outside it
    ox, oz = door_xz
    p.put(ox, f + 1, oz, "minecraft:air")
    p.put(ox, f + 2, oz, "minecraft:air")
    p.door(ox, f + 1, oz, OPPOSITE[side])
    if b["on"] == "land":
        k = 1
        while True:
            sx, sz, y = ox + dx * k, oz + dz * k, f - (k - 1)
            if p.g(sx, sz) >= y:
                break
            p.put(sx, y, sz, "minecraft:tuff_brick_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]"
                  % OPPOSITE[side])
            for yy in range(p.g(sx, sz) + 1, y):
                p.put(sx, yy, sz, pal["foundation"])
            p.lit_cells.append((sx, y + 1, sz))
            k += 1
    # the light: lanterns hanging from the ceiling on a grid
    xs = list(range(x0 + 2, x1 - 1, 4)) or [(x0 + x1) // 2]
    zs = list(range(z0 + 2, z1 - 1, 4)) or [(z0 + z1) // 2]
    for x in xs:
        for z in zs:
            p.hang(x, f + H, z, HANGING)
    FITS[b["fit"]](p, b, f)
    return f


def _fit(p, f, items):
    for x, dy, z, st in items:
        if dy == "hang":
            p.hang(x, f + 1, z, st)
        else:
            p.put(x, f + dy, z, st)


def _deep(b):
    """(z of the row `d` blocks in from the door wall, the facing back toward the door) for a north or south door."""
    x0, z0, x1, z1 = b["rect"]
    side = b["door"]["side"]
    if side not in ("north", "south"):
        raise StationError("building %s: its fit is laid out from a north or south door, not %s" % (b["id"], side))
    return (lambda d: z0 + d if side == "north" else z1 - d), side


def fit_institute(p, b, f):
    """The reception desk across the room six in from the door, the Director's place behind it; bookshelves down both
    side walls, a cartography table either side at the back, the sightings banners on the back wall."""
    x0, z0, x1, z1 = b["rect"]
    row, toward = _deep(b)
    items = [(x, 1, row(6), "minecraft:spruce_slab[type=top,waterlogged=false]") for x in range(x0 + 5, x0 + 12)]
    items += [(x0 + 4, 1, row(6), "minecraft:lectern[facing=%s,has_book=false,powered=false]" % toward)]
    items += [(x0 + 11, 2, row(6), LANTERN)]
    for x in (x0 + 1, x1 - 1):
        for d in range(2, (z1 - z0) - 1):
            if d % 3 != 1:
                for dy in (1, 2):
                    items.append((x, dy, row(d), "minecraft:bookshelf"))
    items += [(x0 + 2, 1, row(8), "minecraft:cartography_table"), (x0 + 14, 1, row(8), "minecraft:cartography_table")]
    _fit(p, f, items)
    for x in range(x0 + 2, x1 - 1, 2):
        p.hang(x, f + 3, row(z1 - z0 - 1), "minecraft:cyan_wall_banner[facing=%s]" % toward)
    for x in range(x0 + 6, x0 + 11):
        for d in (2, 3):
            p.hang(x, f + 1, row(d), "minecraft:cyan_carpet")


def fit_archive(p, b, f):
    """Bookshelves down both side walls, four empty glass cases across the room three in from the door, the reading
    lectern against the back wall."""
    x0, z0, x1, z1 = b["rect"]
    row, toward = _deep(b)
    items = []
    for x in (x0 + 1, x1 - 1):
        for d in range(2, (z1 - z0) - 1):
            if d % 3 != 2:
                for dy in (1, 2, 3):
                    items.append((x, dy, row(d), "minecraft:bookshelf" if dy != 2 else "minecraft:chiseled_bookshelf[facing=%s,slot_0_occupied=false,slot_1_occupied=false,slot_2_occupied=false,slot_3_occupied=false,slot_4_occupied=false,slot_5_occupied=false]" % ("east" if x == x0 + 1 else "west")))
    for x in (x0 + 2, x0 + 4, x0 + 6, x0 + 8):
        items += [(x, 1, row(3), "minecraft:polished_tuff"), (x, 2, row(3), "minecraft:glass")]
    items += [(x0 + 5, 1, row(z1 - z0 - 1), "minecraft:lectern[facing=%s,has_book=false,powered=false]" % toward)]
    _fit(p, f, items)


def fit_bunkhouse(p, b, f):
    """Carpet bedrolls along the wall away from the door, two barrels by it."""
    x0, z0, x1, z1 = b["rect"]
    row, _toward = _deep(b)
    depth = z1 - z0
    for x in (x0 + 1, x0 + 3, x1 - 3, x1 - 1):
        for d in (depth - 1, depth - 2):
            p.hang(x, f + 1, row(d), "minecraft:light_gray_carpet")
    _fit(p, f, [(x0 + 1, 1, row(2), "minecraft:barrel[facing=up,open=false]"),
                (x1 - 1, 1, row(2), "minecraft:barrel[facing=up,open=false]")])


def fit_wet_lab(p, b, f):
    x0, z0, x1, z1 = b["rect"]
    _fit(p, f, [(x1 - 1, 1, z0 + 1, "minecraft:cauldron"), (x1 - 1, 1, z0 + 2, "minecraft:cauldron"),
                (x1 - 1, 1, z1 - 1, "minecraft:brewing_stand[has_bottle_0=false,has_bottle_1=false,has_bottle_2=false]"),
                (x1 - 2, 1, z1 - 1, "minecraft:barrel[facing=up,open=false]"),
                (x0 + 2, 1, z1 - 1, "minecraft:crafting_table")])


def fit_hydrophone(p, b, f):
    x0, z0, x1, z1 = b["rect"]
    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
    # the hatch: an open trapdoor at the water's surface, waterlogged, and the line hanging into it
    p.put(cx, f, cz, "minecraft:spruce_trapdoor[facing=north,half=top,open=true,powered=false,waterlogged=true]")
    for y in range(f + 1, f + b["height"] + 1):
        p.hang(cx, y, cz, "minecraft:chain[axis=y,waterlogged=false]")
    _fit(p, f, [(x0 + 1, 1, z0 + 1, "minecraft:lectern[facing=south,has_book=false,powered=false]"),
                (x1 - 1, 1, z0 + 1, "minecraft:barrel[facing=up,open=false]")])


def fit_weather(p, b, f):
    x0, z0, x1, z1 = b["rect"]
    _fit(p, f, [(x1 - 1, 1, z0 + 1, "minecraft:cartography_table"), (x1 - 1, 1, z0 + 2, "minecraft:barrel[facing=up,open=false]"),
                (x0 + 1, 1, z0 + 1, "minecraft:lectern[facing=south,has_book=false,powered=false]")])


def fit_samples(p, b, f):
    x0, z0, x1, z1 = b["rect"]
    _fit(p, f, [(x0 + 1, 1, z0 + 1, "minecraft:barrel[facing=up,open=false]"), (x0 + 1, 2, z0 + 1, "minecraft:barrel[facing=up,open=false]"),
                (x0 + 1, 1, z1 - 1, "minecraft:cauldron")])


def fit_darkroom(p, b, f):
    x0, z0, x1, z1 = b["rect"]
    _fit(p, f, [(x1 - 1, 1, z0 + 1, "minecraft:cauldron"), (x1 - 1, 1, z1 - 1, "minecraft:barrel[facing=up,open=false]")])
    p.hang(x0 + 1, f + 1, z0 + 1, "minecraft:red_carpet")


def fit_observatory(p, b, f):
    """A chart table and a lectern against the wall opposite an east or west door, the lectern facing the room."""
    x0, z0, x1, z1 = b["rect"]
    side = b["door"]["side"]
    if side not in ("east", "west"):
        raise StationError("building %s: its fit is laid out from an east or west door, not %s" % (b["id"], side))
    x = x1 - 1 if side == "west" else x0 + 1
    _fit(p, f, [(x, 1, z0 + 1, "minecraft:cartography_table"),
                (x, 1, z1 - 1, "minecraft:lectern[facing=%s,has_book=false,powered=false]" % side)])


FITS = {"institute": fit_institute, "archive": fit_archive, "bunkhouse": fit_bunkhouse, "wet_lab": fit_wet_lab,
        "hydrophone": fit_hydrophone, "weather": fit_weather, "samples": fit_samples, "darkroom": fit_darkroom,
        "observatory": fit_observatory}


# ------------------------------------------------------------------------------------------------------------ the strand
def plaza(p):
    doc = p.doc
    p.zone = "strand"
    r = doc["plaza"]["rect"]
    pav = doc["paving"]
    rects = [b["rect"] for b in doc["buildings"] if b["on"] == "land"]
    stairs = {(x, z) for (x, y, z), st in p.solid["strand"].items() if "stairs" in st}
    p.clear["strand"].append((r[0], p.level + 1, r[1], r[2], p.level + doc["rules"]["clear_above"] + 6, r[3]))
    every = pav["inlay_every"]
    for x, z in cells(r):
        if p.w.depth(x, z) is not None or any(in_rect(x, z, rr) for rr in rects) or (x, z) in stairs \
                or (x, z) in p.walk_cells:
            continue
        near = any(in_rect(x, z, (rr[0] - 1, rr[1] - 1, rr[2] + 1, rr[3] + 1)) for rr in rects)
        if (x - r[0]) % every == 0 or (z - r[1]) % every == 0:
            st = pav["inlay"]
        elif near:
            st = pav["border"]
        else:
            st = pav["field"]
        y = p.g(x, z)
        p.put(x, y, z, st)
        p.lit_cells.append((x, y + 1, z))
    # lamp posts on the inlay grid's crossings, where they block no door, step or wall
    for x in range(r[0] + every // 2, r[2] + 1, every):
        for z in range(r[1] + every // 2, r[3] + 1, every):
            if p.w.depth(x, z) is not None or (x, z) in stairs or (x, z) in p.walk_cells:
                continue
            if any(in_rect(x, z, (rr[0] - 1, rr[1] - 1, rr[2] + 1, rr[3] + 1)) for rr in rects):
                continue
            y = p.g(x, z)
            p.put(x, y + 1, z, fence())
            p.put(x, y + 2, z, fence())
            p.hang(x, y + 3, z, LANTERN)
            if (x, y + 1, z) in p.lit_cells:
                p.lit_cells.remove((x, y + 1, z))


# ------------------------------------------------------------------------------------------------------------ shrine
def shrine(p):
    doc = p.doc
    p.zone = "platform"
    s = doc["shrine"]
    cx, cz = s["centre"]
    n = s["dais_half"]
    L = p.level
    d = p.w.depth(cx, cz)
    if d is None or d < s["min_depth"]:
        raise StationError("the shrine's centre (%d, %d) is over %s of water; shrine.min_depth is %d" % (cx, cz, d, s["min_depth"]))
    for x in range(cx - n, cx + n + 1):
        for z in range(cz - n, cz + n + 1):
            if (x, z) not in p.walk_cells:
                raise StationError("the dais at (%d, %d) is off the platform" % (x, z))
            ex, ez = abs(x - cx) == n, abs(z - cz) == n
            if ex and ez:
                st = "minecraft:tuff_bricks"
            elif ez:
                st = "minecraft:tuff_brick_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (
                    "south" if z < cz else "north")
            elif ex:
                st = "minecraft:tuff_brick_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (
                    "east" if x < cx else "west")
            elif (x, z) == (cx, cz):
                st = "minecraft:chiseled_tuff_bricks"
            elif x == cx or z == cz:
                st = doc["paving"]["inlay"]
            else:
                st = "minecraft:polished_tuff"
            p.put(x, L + 1, z, st)
            if not (ex and ez):
                p.lit_cells.append((x, L + 2, z))
            if (x, L + 1, z) in p.lit_cells:
                p.lit_cells.remove((x, L + 1, z))
    for key in ("latias", "latios"):
        a = s[key]
        p.put(a["at"][0], L + 2, a["at"][1], "%s[facing=%s]" % (a["block"], a["facing"]))
        p.lit_cells.remove((a["at"][0], L + 2, a["at"][1]))
    an = s["anchor"]
    p.put(an["at"][0], L + 2, an["at"][1], an["block"])
    p.lit_cells.remove((an["at"][0], L + 2, an["at"][1]))
    for (x, z), key in (((cx - n, cz - n), "latias"), ((cx - n, cz + n), "latias"),
                        ((cx + n, cz - n), "latios"), ((cx + n, cz + n), "latios")):
        p.hang(x, L + 2, z, "%s[rotation=0]" % s["banners"][key])
    for dx in (-(n + 2), n + 2):
        for dz in (-(n + 2), n + 2):
            x, z = cx + dx, cz + dz
            p.put(x, L + 1, z, fence())
            p.put(x, L + 2, z, fence())
            p.hang(x, L + 3, z, LANTERN)
            if (x, L + 1, z) in p.lit_cells:
                p.lit_cells.remove((x, L + 1, z))


def mast(p):
    doc = p.doc
    p.zone = "crossing"
    m = doc["mast"]
    x, z = m["at"]
    if (x, z) not in p.walk_cells:
        raise StationError("the mast at (%d, %d) is off the decks" % (x, z))
    L = p.level
    for y in range(L + 1, L + m["height"] + 1):
        p.put(x, y, z, "minecraft:stripped_spruce_log[axis=y]")
    top = L + m["height"]
    p.put(x - 1, top - 1, z, fence(e=True))
    p.put(x + 1, top - 1, z, fence(w=True))
    p.put(x, top + 1, z, "minecraft:waxed_oxidized_copper")
    if (x, L + 1, z) in p.lit_cells:
        p.lit_cells.remove((x, L + 1, z))


def signs(p):
    doc = p.doc
    for s in doc["signs"]:
        p.zone = zone_of(doc, "signs", s["id"])
        x, z = s["at"]
        y = p.g(x, z) + 1 if s["on"] == "plaza" else p.level + 1
        if s["on"] == "deck" and (x, z) not in p.walk_cells:
            raise StationError("sign %s is off the decks" % s["id"])
        p.hang(x, y, z, standing_sign(s["facing"], s["lines"]))
        if (x, y, z) in p.lit_cells:
            p.lit_cells.remove((x, y, z))


def study_pool(p):
    doc = p.doc
    p.zone = "study_pool"
    x, z = doc["study_pool"]["habitat_post"]
    if (x, z) not in p.walk_cells:
        raise StationError("the habitat post is not under a deck")
    d = p.w.depth(x, z)
    if d is None or d < 3:
        raise StationError("the habitat post at (%d, %d) is not in 3 or more of water" % (x, z))
    for y in range(p.g(x, z) + 1, p.level):
        p.put(x, y, z, "%s[axis=y]" % doc["paving"]["post"])
    # the Habitat Block replaces the post's middle (R9E, after this pack)
    p.habitat = (x, p.g(x, z) + 1 + (p.level - p.g(x, z) - 1) // 2, z)


def light_fill(p):
    """More lamp posts where the standing lamps leave a place dark, greedily, by an estimate that ignores walls
    (15 less the 3D Manhattan distance to the nearest lantern) held one above min_light for that reason. The audit
    floods real block light, walls and all, from what is written; this only decides where the extra posts go."""
    doc = p.doc
    need = doc["rules"]["min_light"] + 1
    reach = 15 - need
    blocks = p.blocks()
    keep = {tuple(s["at"]) for s in doc["signs"]} | {tuple(doc["mast"]["at"])} | {tuple(n["at"]) for n in doc["npcs"]}
    rects = building_rects(doc)
    for b in doc["buildings"]:
        dx, dz = SIDES[b["door"]["side"]]
        x0, z0, x1, z1 = b["rect"]
        side, at = b["door"]["side"], b["door"]["at"]
        ox, oz = (at, z0 if side == "north" else z1) if side in ("north", "south") else (x0 if side == "west" else x1, at)
        keep |= {(ox + dx * k, oz + dz * k) for k in range(1, 4)}
    places = [c for c in p.lit_cells if blocks.get(c, "minecraft:air") == "minecraft:air"
              and blocks.get((c[0], c[1] - 1, c[2]), "minecraft:air") != "minecraft:air"]
    hole = holes(doc)
    under = {c for b in doc["buildings"] for c in cells(rects[b["id"]])}
    cands = {}   # (x, z) -> (zone, foot y)
    for wk in doc["walks"]:
        zone = zone_of(doc, "walks", wk["id"])
        r = wk["rect"]
        wide = min(r[2] - r[0], r[3] - r[1]) > 2
        for x, z in cells(r):
            sides = outward(r, x, z)
            if (not sides and not wide) or (x, z) in hole or (x, z) in under or (x, z) in keep:
                continue
            nbrs = [(x + SIDES[s][0], z + SIDES[s][1]) for s in sides]
            if any(n in p.walk_cells or n in under for n in nbrs):
                continue
            if blocks.get((x, p.level + 1, z), "minecraft:air") != "minecraft:air":
                continue
            cands[(x, z)] = (zone, p.level + 1)
    pr = doc["plaza"]["rect"]
    for x, z in cells(pr):
        if p.w.depth(x, z) is not None or (x, z) in keep or (x, z) in p.walk_cells:
            continue
        if any(in_rect(x, z, (rr[0] - 2, rr[1] - 2, rr[2] + 2, rr[3] + 2)) for rr in rects.values()):
            continue
        y = p.g(x, z) + 1
        if blocks.get((x, y, z), "minecraft:air") == "minecraft:air" and (x, y - 1, z) in blocks:
            cands[(x, z)] = ("strand", y)

    def est(c):
        return max((15 - abs(c[0] - l[0]) - abs(c[1] - l[1]) - abs(c[2] - l[2]) for l in p.lanterns), default=0)
    dark = {c for c in places if est(c) < need}
    while dark:
        best, score = None, 0
        for (x, z), (zone, y) in cands.items():
            lamp = (x, y + 2, z)
            n = sum(1 for c in dark if abs(c[0] - x) + abs(c[1] - lamp[1]) + abs(c[2] - z) <= reach)
            if n > score:
                best, score = (x, z), n
        if best is None:
            raise StationError("%d standing place(s) stay dark and no lamp post can reach them: %s" % (len(dark), sorted(dark)[:3]))
        zone, y = cands.pop(best)
        p.zone = zone
        x, z = best
        p.put(x, y, z, fence())
        p.put(x, y + 1, z, fence())
        p.hang(x, y + 2, z, LANTERN)
        if (x, y, z) in p.lit_cells:
            p.lit_cells.remove((x, y, z))
        dark = {c for c in dark if c != (x, y, z) and abs(c[0] - x) + abs(c[1] - y - 2) + abs(c[2] - z) > reach}


def npcs(p):
    doc = p.doc
    blocks = p.blocks()
    for n in doc["npcs"]:
        x, z = n["at"]
        if n["in"] in p.floors:
            y = p.floors[n["in"]] + 1
            r = building_rects(doc)[n["in"]]
            if not (r[0] < x < r[2] and r[1] < z < r[3]):
                raise StationError("%s is not inside %s" % (n["id"], n["in"]))
        else:
            if p.walk_cells.get((x, z)) != n["in"]:
                raise StationError("%s is not on the %s deck" % (n["id"], n["in"]))
            y = p.level + 1
        for yy in (y, y + 1):
            if blocks.get((x, yy, z), "minecraft:air") != "minecraft:air":
                raise StationError("%s's spot (%d, %d, %d) is not two blocks of air: %s" % (n["id"], x, yy, z, blocks[(x, yy, z)]))
        if blocks.get((x, y - 1, z), "minecraft:air") == "minecraft:air":
            raise StationError("%s's spot (%d, %d, %d) has nothing under it" % (n["id"], x, y, z))
        p.npcs[n["id"]] = (x, y, z)


def plan(doc, g):
    p = Plan(doc, g)
    walks(p)
    for b in doc["buildings"]:
        building(p, b)
    plaza(p)
    shrine(p)
    mast(p)
    signs(p)
    study_pool(p)
    light_fill(p)
    npcs(p)
    return p


# ------------------------------------------------------------------------------------------------------------ the pack
def _runs(blocks, top_down=False):
    """setblock and fill lines for {(x, y, z): state}, one fill per run of one state along x, bottom up (or top down)."""
    out = []
    keys = sorted(blocks, key=lambda k: (-k[1] if top_down else k[1], k[2], k[0]))
    i = 0
    while i < len(keys):
        x, y, z = keys[i]
        st = blocks[keys[i]]
        j = i
        while (j + 1 < len(keys) and keys[j + 1] == (keys[j][0] + 1, y, z) and blocks[keys[j + 1]] == st
               and "{" not in st):
            j += 1
        if j == i:
            out.append("setblock %d %d %d %s" % (x, y, z, st))
        else:
            out.append("fill %d %d %d %d %d %d %s" % (x, y, z, keys[j][0], y, z, st))
        i = j + 1
    return out


def zone_lines(p, zone):
    out = ["# Generated by tools/research_station.py from data/research_station.json. Re-run to rebuild; do not edit.",
           "# The research station on the west sea coast: zone %s." % zone,
           "# Run BEFORE R9E: the Habitat Block %s sits in a post the study_pool zone writes."
           % p.doc["study_pool"]["habitat_block"],
           "# 1. clear trees, leaves and plants over everything above the water's surface (y%d and up)" % (p.level + 1)]
    for (x0, y0, z0, x1, y1, z1) in p.clear[zone]:
        if y0 <= p.level:
            raise StationError("a clear box reaches y%d, at or below the water's surface y%d" % (y0, p.level))
        for tag in ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable"):
            out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the structure, bottom up")
    over = set(p.hung[zone]) | {k for k, _st in p.doors[zone]}
    out += _runs({k: st for k, st in p.solid[zone].items() if k not in over})
    out.append("# 3. what hangs on it, from the top: lanterns, chains, banners, signs, carpets")
    out += _runs(p.hung[zone], top_down=True)
    out.append("# 4. the doors, lower half then upper")
    out += ["setblock %d %d %d %s" % (k + (st,)) for k, st in p.doors[zone]]
    return out


def zone_box(p, zone):
    ks = list(p.blocks(zone)) + [(c[0], 0, c[2]) for c in p.clear[zone]] + [(c[3], 0, c[5]) for c in p.clear[zone]]
    xs = [k[0] for k in ks]
    zs = [k[2] for k in ks]
    return (min(xs), min(zs), max(xs), max(zs))


# ------------------------------------------------------------------------------------------------------------ economy
def tags(doc):
    return doc["economy"]["tags"]


def crown_open(doc):
    e = doc["economy"]
    cap = e.get("post_champion_cap")
    return bool(e["issuing"]) and isinstance(cap, int) and cap >= 70


def eon_open(doc):
    """The Eon dews have their own hold under the one switch (economy.eon_issuing): the owner's 2026-10-02 decision
    names the three feathers only, so throwing economy.issuing for them must not issue the dews too."""
    e = doc["economy"]
    return bool(e["issuing"]) and e.get("eon_issuing") is True


def tick_lines(doc):
    t = tags(doc)
    out = ["# Generated by tools/research_station.py: THE SWITCH (data/research_station.json economy.issuing = %s)."
           % str(bool(doc["economy"]["issuing"])).lower(),
           "# Every item route in the station's four conversations requires %s (the crown %s, the dews also %s)."
           % (t["issuing"], t["issuing_crown"], t["issuing_eon"])]
    if doc["economy"]["issuing"]:
        out.append("tag @a[tag=!%s] add %s" % (t["issuing"], t["issuing"]))
    else:
        out.append("tag @a[tag=%s] remove %s" % (t["issuing"], t["issuing"]))
    if crown_open(doc):
        out.append("tag @a[tag=!%s] add %s" % (t["issuing_crown"], t["issuing_crown"]))
    else:
        out.append("tag @a[tag=%s] remove %s" % (t["issuing_crown"], t["issuing_crown"]))
    if eon_open(doc):
        out.append("tag @a[tag=!%s] add %s" % (t["issuing_eon"], t["issuing_eon"]))
    else:
        out.append("tag @a[tag=%s] remove %s" % (t["issuing_eon"], t["issuing_eon"]))
    return out


def crown_offering_lines(doc):
    t = tags(doc)
    h = doc["economy"]["harvest"]
    return ["# Generated by tools/research_station.py: the archivist counts and takes the cemetery's harvest.",
            "# Run as the player by the archivist's offer_harvest transition. Does nothing unless the crown is issued,",
            "# or if this player has already paid. clear <item> 0 counts without taking.",
            "execute unless entity @s[tag=%s] run return 0" % t["issuing_crown"],
            "execute if entity @s[tag=%s] run return 0" % t["harvest_paid"],
            "scoreboard objectives add cobblers_station dummy",
            "execute store result score @s cobblers_station run clear @s %s 0" % h["item"],
            "execute if score @s cobblers_station matches %d.. run clear @s %s %d" % (h["count"], h["item"], h["count"]),
            "execute if score @s cobblers_station matches %d.. run tag @s add %s" % (h["count"], t["harvest_paid"])]


def _player(*preds):
    return [{"condition": "minecraft:entity_properties", "entity": "this", "predicate": pr} for pr in preds]


def _box(x0, y0, z0, x1, y1, z1):
    # a position predicate reads the feet as a double: max + 1 takes in the whole of the last block (tools/rewards_pack.py)
    return {"x": {"min": x0, "max": x1 + 1}, "y": {"min": y0, "max": y1 + 1}, "z": {"min": z0, "max": z1 + 1}}


def storm_box(doc):
    # through tools/adopted_sites.py: the tower is scheduled (data/placements.json legendary_zapdos_tower), so its
    # position is no longer in the adopted record's `placement` block
    import adopted_sites
    w = adopted_sites.where(adopted_sites.site("adopted_zapdos_tower"))
    if w["rotation"] != "none" or w["mirror"] != "none":
        raise SystemExit("storm_box assumes the Zapdos tower unturned; it is %s/%s" % (w["rotation"], w["mirror"]))
    (cx, cz), y = w["corner"], w["y"]
    sx, sy, sz = w["size"]
    top = doc["economy"]["storm_log"]["top_storey"]
    return (cx, y + sy - top, cz, cx + sx - 1, y + sy - 1, cz + sz - 1)


def ember_box(doc):
    """The Craters' Moltres tower's whole placement box (economy.ember_survey). The tower is PASTED by /place template,
    which writes no structure reference, so a location predicate on the structure cannot fire there: the survey is a
    position box, as storm_log is (the trigger box of tools/rewards_pack.py)."""
    es = doc["economy"]["ember_survey"]
    site = next(s for s in json.loads((ROOT / "data" / "adopted_legendary_sites.json").read_text(encoding="utf-8"))["sites"]
                if s["id"] == es["site"])
    (cx, cz), y = site["placement"]["corner"], site["placement"]["y"]
    sx, sy, sz = site["size"]
    if site["placement"].get("rotation", "none") not in ("none", None):
        raise StationError("ember_survey: %s is rotated; the box assumes rotation none" % es["site"])
    return (cx, y, cz, cx + sx - 1, y + sy - 1, cz + sz - 1)


def courier_box(doc, g):
    camp = json.loads((ROOT / "data" / "frostpeak_camp.json").read_text(encoding="utf-8"))
    piece = next(q for q in camp["pieces"] if q["id"] == "frostpeak_camp_instrument_deck")
    (ax, az), (hx, hz) = piece["at"], piece["half"]
    x0, z0, x1, z1 = ax - hx, az - hz, ax + hx, az + hz
    gs = [g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    return (x0, min(gs), z0, x1, max(gs) + doc["economy"]["courier"]["rise"], z1)


def _item_json(spec):
    """'minecraft:spyglass[minecraft:custom_data={cobblers_station:courier_case}]' -> an advancement item predicate."""
    item, _, comp = spec.partition("[")
    out = {"items": item}
    if comp:
        key, _, val = comp.rstrip("]").partition("=")
        k, _, v = val.strip("{}").partition(":")
        out["components"] = {key: {k: v}}
    return out


def earning(doc, g):
    """{name: (advancement, reward function lines)} - shipped ONLY while economy.issuing is true."""
    t = tags(doc)
    c = doc["economy"]["courier"]

    def adv(trigger, player):
        return {"criteria": {"earned": {"trigger": trigger, "conditions": {"player": player}}},
                "rewards": {"function": None}}
    out = {
        "storm_log": (adv("minecraft:location", _player({"location": {"position": _box(*storm_box(doc)),
                                                                         "dimension": "minecraft:overworld"}})
                          + [{"condition": "minecraft:weather_check", "thundering": True}]),
                      ["tag @s add %s" % t["storm_log"],
                       'tellraw @s {"text":"You log the storm over the thunder tower. Shrew Station will want to hear of it.","color":"yellow"}']),
        "ember_survey": (adv("minecraft:location", _player({"location": {"position": _box(*ember_box(doc)),
                                                                            "dimension": "minecraft:overworld"}})),
                         ["tag @s add %s" % t["ember_survey"],
                          'tellraw @s {"text":"You note the fire tower\'s stones and the heat off the crater. Shrew Station will want to hear of it.","color":"gold"}']),
        "lake_trio": (adv("minecraft:tick", _player({"type_specific": {"type": "minecraft:player", "advancements": {
            "cobblers:legendary/mesprit/met": True, "cobblers:legendary/azelf/met": True, "cobblers:legendary/uxie/met": True}}})),
                      ["tag @s add %s" % t["lake_trio"],
                       'tellraw @s {"text":"Mesprit, Azelf and Uxie: you have met all three. The shrine keeper at Shrew Station keeps a ledger.","color":"aqua"}']),
        "courier_delivery": (adv("minecraft:location", _player({"location": {"position": _box(*courier_box(doc, g)),
                                                                                "dimension": "minecraft:overworld"},
                                                                   "equipment": {"mainhand": _item_json(c["case"])}})),
                             ["clear @s %s 1" % c["case"], "give @s %s 1" % c["notes"],
                              'tellraw @s {"text":"Dr. Halvard takes the spyglass, checks its scale against her own, and hands you her season\'s notes.","color":"white"}']),
    }
    for name, (a, _lines) in out.items():
        a["rewards"]["function"] = "%s:%s/earned/%s" % (NS, FN, name)
    return out


# ------------------------------------------------------------------------------------------------------------ files
def files(doc, g):
    p = plan(doc, g)
    out = {"pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                               "Cobblers: Shrew Station, the legendary and mythical research station (tools/research_station.py)"}},
                                     indent=2) + "\n"}
    for zone in ZONES:
        lines = function_limits.ensure_loaded(zone_lines(p, zone))
        bad = function_limits.check_lines(lines, "build_%s" % zone)
        if bad:
            raise StationError("build_%s: %d command(s) the server would refuse: %s" % (zone, len(bad), bad[:3]))
        out["data/%s/function/%s/build_%s.mcfunction" % (NS, FN, zone)] = "\n".join(lines) + "\n"
    out["data/%s/function/%s/tick.mcfunction" % (NS, FN)] = "\n".join(tick_lines(doc)) + "\n"
    out["data/minecraft/tags/function/tick.json"] = json.dumps({"values": ["%s:%s/tick" % (NS, FN)]}, indent=2) + "\n"
    out["data/%s/function/%s/crown_offering.mcfunction" % (NS, FN)] = "\n".join(crown_offering_lines(doc)) + "\n"
    if doc["economy"]["issuing"]:
        for name, (a, lines) in earning(doc, g).items():
            out["data/%s/advancement/%s/%s.json" % (NS, FN, name)] = json.dumps(a, indent=2) + "\n"
            out["data/%s/function/%s/earned/%s.mcfunction" % (NS, FN, name)] = "\n".join(
                ["# Generated by tools/research_station.py: shipped only while economy.issuing is true."] + lines) + "\n"
    return out, p


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, as one step BEFORE R9E: per zone, hold the chunks, build, release (R9LH's shape)."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    p = plan(doc, g)
    out = []
    for zone in ZONES:
        hold = "%d %d %d %d" % zone_box(p, zone)
        out += [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build_%s" % (NS, FN, zone)),
                ("cmd", "forceload remove " + hold)]
    return out


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def report(doc, p):
    b = p.blocks()
    lines = ["water %s level y%d: decks y%d, walks y%d" % (doc["site"]["water"], p.level, p.level, p.level + 1),
             "floors: %s" % ", ".join("%s y%d" % kv for kv in sorted(p.floors.items())),
             "blocks written: %d (%s)" % (len(b), ", ".join("%s %d" % (z, len(p.blocks(z))) for z in ZONES)),
             "lanterns: %d; lit cells to check: %d" % (len(p.lanterns), len(p.lit_cells)),
             "habitat block (study post): %s" % (p.habitat,),
             "npcs: %s" % json.dumps({k: list(v) for k, v in p.npcs.items()}),
             "shrine: latias %s, latios %s, anchor %s (y%d)" % (doc["shrine"]["latias"]["at"], doc["shrine"]["latios"]["at"],
                                                              doc["shrine"]["anchor"]["at"], p.level + 2),
             "issuing: %s; crown: %s; dews: %s" % (doc["economy"]["issuing"], crown_open(doc), eon_open(doc)),
             "steps (before R9E): %s" % json.dumps([list(s) for s in placement_steps(doc, p.g)])]
    return lines


# ------------------------------------------------------------------------------------------------------------ cleanup
# STAGING ONLY, one-off (tools/sea_drift.py cleanup's pattern). The owner moved the station from Shrew Lake's south
# strand to the west coast on 2026-10-02 after the lake build had been applied to staging (R9RS). This puts every cell
# the lake build wrote, and this build does not, back to the heightmap world, and removes the lake build's four NPCs.
# What it cannot put back, stated: the trees, plants and snow the lake build's clear fills took off the strand (the
# heightmap does not say where they stood), and Psyduck already spawned by the old Habitat Block (wild Pokemon; they
# despawn as wild Pokemon do).
AIR = "minecraft:air"


def old_station(rev=OLD_REV, g=None):
    """The first station's generator, record and plan as built at `rev` (git show), run on today's heightmap, and its
    npc_grant records from that rev's data/rewards.json (what R9F seated)."""
    import importlib.util
    import subprocess
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="research_station_old_"))
    text = {}
    for rel in ("tools/research_station.py", "data/research_station.json", "data/rewards.json"):
        text[rel] = subprocess.run(["git", "show", "%s:%s" % (rev, rel)], cwd=ROOT, capture_output=True, text=True,
                                   encoding="utf-8", check=True).stdout
    (tmp / "research_station_old.py").write_text(text["tools/research_station.py"], encoding="utf-8")
    (tmp / "research_station_old.json").write_text(text["data/research_station.json"], encoding="utf-8")
    spec = importlib.util.spec_from_file_location("research_station_old", tmp / "research_station_old.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = mod.load(tmp / "research_station_old.json")
    p = mod.plan(doc, g)
    grants = {r["id"]: r for r in json.loads(text["data/rewards.json"])["rewards"] if r.get("kind") == "npc_grant"}
    return mod, doc, p, grants


def _float_height(g, x, z):
    h = getattr(g, "heights", None)
    return float(h[int(z) - g.oz, int(x) - g.ox]) if h is not None else float(g(x, z))


def natural(s, g, x, y, z):
    """The heightmap world's block at a cell: air over the ground, the water that tools/water_mask.py level_at() paints
    (a lake to its level, the sea to y62) between the ground and its surface, and the ground under it.

    The ground's own block is ASSUMED from tools/paint_maps.py's rules, which is what the export was told to paint:
    inside a lake basin where the float height is under the level + 2 (its bank, and its wet edge where the rounded
    ground meets the level) sand - the wet edge is really gravel or clay by paint_maps' noise, which is not reproduced
    here - and elsewhere grass (Shrew Lake's shores are the blossom preset, GRASS). Under it dirt, then stone. Only the
    ground's top block is ever asked for: the lake build wrote nothing deeper (its plaza paving and its jetty's
    landfall deck replaced the ground block itself; every other write stood above the ground or in the water)."""
    gy = g(x, z)
    if y > gy:
        bid, level = s.at(x, z)
        return "minecraft:water" if bid is not None and y <= level else AIR
    if y == gy:
        hf = _float_height(g, x, z)
        for bid, (x0, z0, x1, z1) in s.boxes.items():
            b = s.bodies[bid]
            if x0 <= x <= x1 and z0 <= z <= z1 and hf < b["level_y"] + 2 and s.W.in_polygons(b["basin"], x, z):
                return "minecraft:sand"
        return "minecraft:grass_block"
    return "minecraft:dirt" if y >= gy - 3 else "minecraft:stone"


def npc_box(seat):
    """A tight box round one seat: the seat's column and one block round it, from the feet to the head. Never a bare
    distance sweep (the brief): a sweep would take any NPC that wandered near, this takes the one R9F seated there."""
    x, y, z = seat
    return "x=%d,y=%d,z=%d,dx=2,dy=1,dz=2" % (x - 1, y, z - 1)


def cleanup(new_p, g, rev=OLD_REV):
    """({"restore": [commands]}, counts, {npc id: old seat}, the old plan): every cell the lake build's pack wrote,
    and this build does not, put back to the heightmap world (natural()), the old Habitat Block's cell included."""
    _mod, _odoc, op, grants = old_station(rev, g)
    s = Surface(g)
    olds = op.blocks()
    news = new_p.blocks()
    cells = set(olds)
    if op.habitat:
        cells.add(tuple(op.habitat))
    counts = {"to_water": 0, "to_air": 0, "ground_top_restored": 0, "under_ground": 0, "air_over_air_skipped": 0,
              "kept_because_this_build_writes_it": 0}
    todo = {}
    for c in sorted(cells):
        if c in news:
            counts["kept_because_this_build_writes_it"] += 1
            continue
        x, y, z = c
        nat = natural(s, g, x, y, z)
        if nat == AIR and _base(olds.get(c, AIR)) == AIR:
            counts["air_over_air_skipped"] += 1
            continue
        todo[c] = nat
        gy = g(x, z)
        if y > gy:
            counts["to_water" if nat == "minecraft:water" else "to_air"] += 1
        elif y == gy:
            counts["ground_top_restored"] += 1
        else:
            counts["under_ground"] += 1
    import rift_mines as RM   # its column runs and command shape, not its model (tools/sea_drift.py does the same)
    cols = {}
    for (x, y, z), b in todo.items():
        cols.setdefault((x, z), []).append((y, b))
    out = []
    for (x, z) in sorted(cols):
        out += [RM.cmd(x, a, c, z, b) for a, c, b in RM.column_runs(x, z, cols[(x, z)])]
    seats = {}
    for n in _odoc["npcs"]:
        seat = tuple(op.npcs[n["id"]])
        rec = grants.get(n["reward"])
        if rec is None or tuple(rec["npc_at"]) != seat:
            raise StationError("the old %s's seat %s is not %s's npc_at at %s (%s)"
                               % (n["id"], seat, n["reward"], rev, rec and rec.get("npc_at")))
        seats[n["id"]] = seat
    return {"restore": out}, counts, seats, op


def npc_cleanup_lines(seats, folder):
    """Two functions: hold each old seat's chunk and come back in 60 ticks, when its entities have loaded (a chunk's
    entities load after its blocks: tools/reapply.py's npc step and tools/rift_mines.py's carts), then remove the
    cobblemon:npc in each seat's tight box, storing how many went, and release."""
    chunks = sorted({(x >> 4, z >> 4) for x, _y, z in seats.values()})
    hold = ["# Generated by tools/research_station.py cleanup: STAGING ONLY. The first station's four NPCs, at the seats",
            "# the lake build gave them (git show %s, data/rewards.json npc_grant npc_at). Their chunks are held here and"
            % OLD_REV, "# the removal runs 60 ticks on, when their entities have loaded."]
    hold += ["forceload add %d %d" % (cx * 16, cz * 16) for cx, cz in chunks]
    hold += ["schedule function %s:%s/npcs_go 60t replace" % (NS, folder)]
    go = ["# chunks-loaded-by: %s:%s/npcs" % (NS, folder),
          "# how many went at each seat: data get storage %s:%s npcs (1 each is the expected answer)" % (NS, folder)]
    for nid, seat in sorted(seats.items()):
        go.append("execute store result storage %s:%s npcs.%s int 1 run kill @e[type=cobblemon:npc,%s]"
                  % (NS, folder, nid, npc_box(seat)))
    go += ["forceload remove %d %d" % (cx * 16, cz * 16) for cx, cz in chunks]
    return hold, go


def write_cleanup(out, lines, seats, rev=OLD_REV):
    import rift_mines as RM
    out = Path(out)
    fn, order = RM.write_blocks(out, lines, ("restore",), "tools/research_station.py cleanup",
                                "Cobblers STAGING ONLY: the first Shrew Station (%s, Shrew Lake's south strand) put back "
                                "to the heightmap world, and its four NPCs removed" % rev)
    folder = out.name.replace("cobblers_", "")
    hold, go = npc_cleanup_lines(seats, folder)
    for name, body in (("npcs", hold), ("npcs_go", go)):
        bad = function_limits.check_lines(body, name)
        if bad:
            raise StationError("cleanup function %s would be refused: %s" % (name, bad[:2]))
        (fn / (name + ".mcfunction")).write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    order = list(order) + ["npcs"]
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8", newline="\n")
    return fn, order


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "plan", "cleanup"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=None)
    ap.add_argument("--source-root")
    ap.add_argument("--old-rev", default=OLD_REV, help="cleanup: the commit that built the lake station")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, p = files(doc, g)
    if a.cmd == "plan":
        print("\n".join(report(doc, p)))
        return 0
    if a.cmd == "cleanup":
        lines, counts, seats, _op = cleanup(p, g, a.old_rev)
        out = Path(a.out) if a.out else CLEANUP_OUT
        fn, order = write_cleanup(out, lines, seats, a.old_rev)
        print(json.dumps(counts))
        print("old seats: %s" % json.dumps({k: list(v) for k, v in seats.items()}))
        print("wrote %s: %d functions (%d restore, then npcs -> npcs_go), %d restore commands (cobblers:%s/..., in "
              "index.txt order)" % (out, len(order) + 1, len(order) - 1, len(lines["restore"]), fn.name))
        return 0
    a.out = a.out or str(DEFAULT_OUT)
    write(out_files, a.out)
    n = sum(1 for rel, t in out_files.items() if rel.endswith(".mcfunction")
            for l in t.splitlines() if l and not l.startswith("#"))
    print("research_station: %d files -> %s (%d commands)" % (len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
