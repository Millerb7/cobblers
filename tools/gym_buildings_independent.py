#!/usr/bin/env python
"""Independent audit of the five authored gym buildings (the .mcfunction files of the gym_buildings pack).

WHY THIS EXISTS. `tools/gym_buildings.py` is the generator and it fail-closes on its own record: the block
allow-list, `bounds`, block support, the spawner, the chest. Every one of those expectations comes out of
`data/gym_buildings/<gym>.json`, which is what the generator read, so a clean build proves the generator ran
(CLAUDE.md, "Verify before claiming": an expectation derived from the artifact being checked is not an
expectation). Five different agents wrote the five records and none of them was allowed to write a test
(principle 16). This audit re-reads the emitted command text and compares it with sources the generator does
not write:

  the site      data/placements.json: the gym's own lot rect and `level` from the settlement's town plan, the
                town's other placements, anchors and streets
  the ground    tools/ground.py, rounded - the canonical heightmap, never a world save
  the rules     data/gym_interiors.json `rules`: max_fall 12 (a longer fall must land on hay),
                max_submerged_run 14
  the zones     data/spawn_suppression.json: the gym's spawn-free box
  Misty         data/gym_interiors.json gym2: the one interior still built, whose dig and shell no new
                building may touch
  the world     every other data/*.json file, scanned for anything that already claims the same columns
  the physics   a player-movement model written here (walk, step, sprint jump with a reach table, ladders,
                swimming, soul-sand bubble columns, fall damage) run over the voxels the functions produce,
                seeded from the lot's own perimeter at pad level - not from the door the record declares

Checks (each prints only a problem; the codes in brackets are what tests ask for):

  SITE     every write inside the gym lot rect [lot]; every written column seated on the pad, not floating over
           it [float]; nothing written below the pad that opens into untouched ground [breach]; the emitted
           extent inside the gym's spawn-free box [spawn]; every block in a namespace the modpack carries
           [palette]
  TOWN     no other placement, non-gym anchor or street of the same town under the building [town]
  OVERLAP  no two buildings write the same cell [gym_cells]; nothing written into Misty's dig or shell
           [misty]; no other data file's coordinates inside a building [data_claim]
  ROUTE    the route's own waypoints are legal, reachable positions that lead to the next [waypoint, step];
           the leader's spawner is reachable [unreachable]; no reachable position from which the start cannot
           be regained [trap]; no fall that kills [fatal] or costs more than the rules allow [harsh];
           every room the route names before the leader is unavoidable [skip]; a jump the movement model
           allows across a gap the design calls uncrossable [gap]
  WATER    every source sealed in its box [leak]; lava the same [lava]; a long fall landing in water too
           shallow [landing]; a submerged position with no way to air [drown_trap] or past one breath [drown]
  BLOCKS   ladders with nothing behind them [ladder], lanterns hanging from or standing on air [lantern],
           chains with neither [chain], falling blocks over a hole [falling], leaves without persistent=true
           [leaves]

  python tools/gym_buildings_independent.py [--functions DIR] [--source-root ROOT] [--gym N] [--verbose]
Exit 0 with one line when clean; 1 with the problems; 2 when there is nothing built to audit.

NOT COVERED. This is a model of vanilla, not a measurement of it. Whether a soul-sand bubble column really
lifts a player thirteen blocks, whether a lantern really pops, whether an rctmod spawner really spawns its
leader and whether the jump reach table matches the game are runtime facts and need an experiment in a running
Minecraft, not pytest (.claude/rules/testing.md).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# The ground rule (tools/ground_rule.py): this tool reads no world. Ground is the heightmap and the town plan.
WORLD_READS = set()

DEFAULT_FUNCS = ROOT / "build" / "datapacks" / "cobblers_gym_buildings" / "data" / "cobblers" / "function" / "gym_buildings"

# ---- numbers this audit holds itself (NOT read from data/gym_buildings/*.json) ---------------------------------
MAX_FALL = 12                # data/gym_interiors.json rules.max_fall: a longer fall must land on hay
MAX_FALL_DAMAGE = 10         # health points a route may cost in one uncushioned fall
LETHAL_DAMAGE = 20           # a full health bar
MIN_LANDING_WATER = 1        # water this deep under a long fall cancels it. ONE, not two: in vanilla a
                             # single water block takes the whole of a fall of any height (the water-bucket
                             # save rests on it), so two was a margin with no rule behind it - the comment
                             # here said so. It was raised as a finding, not papered over: at two it made
                             # 429 problems against Koga's Reed House, whose floor IS a one-deep wadeable
                             # flood and whose every walkway is five to seven above it, and no building of
                             # that shape could ever pass. The integrating session changed it on 2026-09-29
                             # and queued the in-game check: a seven-block fall into one block of water.
                             # Until that check is done this line is the audit's weakest claim.
MAX_SUBMERGED_ROUNDTRIP = 28 # blocks of head-under-water travel in and out (rules.max_submerged_run 14, both ways)
SEED_MARGIN = 0              # the seed ring is the lot rect itself, at pad level

# The jump reach table. `gap` is the number of empty columns between the take-off block and the landing block;
# the key is the landing floor's height relative to the take-off (+1 = up one, -3 = down three). These are the
# vanilla sprint-jump distances, taken at the GENEROUS end on purpose: an audit that understates a player's
# reach misses shortcuts, which is the failure that matters here. docs/world-building/GYM_BUILDINGS.md states
# the rule the buildings are held to - "no gap of four blocks or less where a sprint jump would skip a stage".
REACH = {1: 3, 0: 4, -1: 5, -2: 5, -3: 6}
DEEP_DROP_REACH = 6          # a drop of four or more: terminal velocity is not reached, the arc keeps flattening

FACING = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
# a ladder[facing=east] hangs on the block to its WEST (tools/gym_buildings.py BEHIND, and the state this
# repository already uses); the value is the offset of the carrying cell.
BEHIND = {"north": (0, 0, 1), "south": (0, 0, -1), "east": (-1, 0, 0), "west": (1, 0, 0)}

# Namespaces the modpack carries (modpack/manifest + docs/world-building/BUILD_PALETTE.md providers). A block
# from anywhere else is a block that will not place.
KNOWN_NAMESPACES = {"minecraft", "cobblemon", "rctmod"}


# ------------------------------------------------------------------------------------------------------- the text
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: (replace|outline|hollow|keep|destroy))?(?: (\S+))?$")
SET = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$")


def parse(text, name="?"):
    """[(index, kind, box, state, mode, filter)] for the fills/setblocks, and the lines nothing here understands."""
    ops, unknown = [], []
    for i, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("forceload "):
            continue
        m = FILL.match(line)
        if m:
            x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
            ops.append((i, "fill", (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1)),
                        m.group(7), m.group(8), m.group(9)))
            continue
        m = SET.match(line)
        if m:
            x, y, z = (int(v) for v in m.groups()[:3])
            ops.append((i, "set", (x, y, z, x, y, z), m.group(4), None, None))
            continue
        unknown.append("%s:%d %s" % (name, i + 1, line[:80]))
    return ops, unknown


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def props(state):
    if "[" not in state:
        return {}
    body = state.split("[", 1)[1].split("]", 1)[0]
    return dict(kv.split("=", 1) for kv in body.split(",") if "=" in kv)


# ----------------------------------------------------------------------------------------------- block classes
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
# Blocks a player's body passes through. Lanterns and chains have a thin collision box; treating them as
# passable is the generous direction (it can only add reachable cells, never hide one).
PASS = {"minecraft:lantern", "minecraft:soul_lantern", "minecraft:chain", "minecraft:torch",
        "minecraft:wall_torch", "minecraft:soul_torch", "minecraft:light"}
CUSHION = {"minecraft:hay_block"}
FALLING = {"minecraft:sand", "minecraft:red_sand", "minecraft:gravel", "minecraft:suspicious_sand",
           "minecraft:suspicious_gravel", "minecraft:anvil", "minecraft:pointed_dripstone"}
NEEDS_BELOW = FALLING | {"minecraft:torch", "minecraft:soul_torch", "minecraft:redstone_torch",
                         "minecraft:rail", "minecraft:powered_rail", "minecraft:detector_rail",
                         "minecraft:activator_rail", "minecraft:flower_pot", "minecraft:scaffolding",
                         "minecraft:lectern", "minecraft:grindstone", "minecraft:brewing_stand"}
NEEDS_BEHIND = {"minecraft:ladder", "minecraft:wall_torch", "minecraft:soul_wall_torch"}
LANTERN_STANDS_ON = {"minecraft:chain"}


def cls_of(state):
    n = block_name(state)
    if n in AIR:
        return "air"
    if n == "minecraft:water":
        return "water"
    if n == "minecraft:lava":
        return "lava"
    if n == "minecraft:ladder":
        return "ladder"
    if n == "minecraft:scaffolding":
        return "scaf"
    if n in CUSHION:
        return "hay"
    if n in PASS:
        return "pass"
    return "solid"


OPEN = {"air", "water", "ladder", "scaf", "pass", "sky"}
SUPPORT = {"solid", "hay", "rock"}
CLIMB = {"ladder", "scaf"}


# ------------------------------------------------------------------------------------------------ the site
class Site:
    """Everything about one gym that comes from data/placements.json and the heightmap. Nothing from the
    building's own record except which settlement it claims."""

    def __init__(self, gid, settlement, placements, ground):
        self.id = gid
        self.settlement = settlement
        plan_rec = (placements.get("settlements") or {}).get(settlement)
        if not plan_rec:
            raise SystemExit("%s: data/placements.json has no settlement %r" % (gid, settlement))
        self.plan = plan_rec["plan"]
        anchors = [a for a in self.plan.get("anchors") or [] if a.get("role") in ("gym", "waterfront_gym")]
        if len(anchors) != 1:
            raise SystemExit("%s: expected one gym anchor in %s's plan, found %d" % (gid, settlement, len(anchors)))
        self.anchor = anchors[0]
        self.lot = tuple(self.anchor["rect"])          # x0 z0 x1 z1
        self.level = self.anchor.get("level")
        if self.level is None:
            raise SystemExit("%s: the gym anchor %s has no `level`" % (gid, self.anchor.get("id")))
        recs = [r for r in placements["placements"] if isinstance(r, dict)]
        self.others = [r for r in recs if r.get("settlement") == settlement
                       and not (r.get("kind") in ("gym", "donor") and str(r.get("id", "")).startswith(gid + "_"))]
        self.ground = ground

    def in_lot(self, x, z):
        x0, z0, x1, z1 = self.lot
        return x0 <= x <= x1 and z0 <= z <= z1

    def surface(self, x, z):
        """The Y of the topmost ground block before the building is written: the levelled pad inside the lot,
        the rounded heightmap outside it."""
        if self.in_lot(x, z):
            return self.level
        return int(round(self.ground(x, z)))


# ------------------------------------------------------------------------------------------------- the voxels
class World:
    """The written cells of one building over a natural world that is rock to the surface and sky above."""

    def __init__(self, site, ops):
        self.site = site
        self.cells = {}
        for (_i, _kind, b, state, mode, filt) in ops:
            if filt or mode in ("replace", "keep", "destroy") and filt:
                continue
            shell = mode in ("outline", "hollow")
            for x in range(b[0], b[3] + 1):
                for y in range(b[1], b[4] + 1):
                    for z in range(b[2], b[5] + 1):
                        if shell and not (x in (b[0], b[3]) or y in (b[1], b[4]) or z in (b[2], b[5])):
                            if mode == "hollow":
                                self.cells[(x, y, z)] = "minecraft:air"
                            continue
                        if mode == "keep" and self.at((x, y, z)) != "minecraft:air":
                            continue
                        self.cells[(x, y, z)] = state
        self._cls = {}
        xs = [c[0] for c in self.cells] or [0]
        ys = [c[1] for c in self.cells] or [0]
        zs = [c[2] for c in self.cells] or [0]
        self.extent = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

    def at(self, c):
        return self.cells.get(c)

    def natural(self, c):
        x, y, z = c
        return "rock" if y <= self.site.surface(x, z) else "sky"

    def cls(self, c):
        v = self._cls.get(c)
        if v is None:
            st = self.cells.get(c)
            v = cls_of(st) if st is not None else self.natural(c)
            self._cls[c] = v
        return v

    def state(self, c):
        return self.cells.get(c) or self.natural(c)

    def is_open(self, c):
        return self.cls(c) in OPEN

    def supports(self, c):
        return self.cls(c) in SUPPORT

    def water(self, c):
        return self.cls(c) == "water"


# ---------------------------------------------------------------------------------------------- the movement
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Moves:
    """The player-movement graph. Nodes are feet cells a player can hold: standing, on a ladder, or in water."""

    def __init__(self, world, box=None):
        self.w = world
        self.box = box                  # (x0, y0, z0, x1, y1, z1) the graph may not leave, or None
        self.bubble = self._bubble_cells()
        self.fatal = set()              # (from, to, damage)
        self.harsh = {}                 # (from, to) -> damage
        self.lands = {}                 # (from, to) -> (kind, water depth, distance)
        self.jumps = {}                 # (from, to) -> gap, for jumps over a real void only

    def _bubble_cells(self):
        out = set()
        w = self.w
        for c, st in w.cells.items():
            if block_name(st) == "minecraft:soul_sand":
                x, y, z = c
                y += 1
                while w.water((x, y, z)):
                    out.add((x, y, z))
                    y += 1
        return out

    def inside(self, c):
        if self.box is None:
            return True
        b = self.box
        return b[0] <= c[0] <= b[3] and b[1] <= c[1] <= b[4] and b[2] <= c[2] <= b[5]

    def body_ok(self, c):
        """'stand' when two open cells, 'crawl' when the feet are in water and the head in a block."""
        w = self.w
        x, y, z = c
        if not w.is_open(c):
            return None
        if w.is_open((x, y + 1, z)):
            return "stand"
        if w.water(c):
            return "crawl"
        return None

    def stable(self, c):
        w = self.w
        x, y, z = c
        if w.cls(c) in CLIMB or w.water(c):
            return True
        return w.supports((x, y - 1, z))

    def submerged(self, c):
        x, y, z = c
        return self.w.water(c) and (self.w.water((x, y + 1, z)) or self.body_ok(c) == "crawl")

    def fall(self, start, top):
        """Fall from feet cell `top` in that column. (landing, damage, kind, water depth) or None if it never lands."""
        w = self.w
        x, _y, z = top
        d0 = start[1]
        cy = top[1]
        floor = (self.box[1] - 4) if self.box else -64
        while cy >= floor:
            c = (x, cy, z)
            if not w.is_open(c):
                return None
            if w.cls(c) in CLIMB:
                return c, 0, "climb", 0
            if w.water(c):
                depth, yy = 0, cy
                while w.water((x, yy, z)):
                    depth += 1
                    yy -= 1
                dist = d0 - cy
                dmg = 0 if depth >= MIN_LANDING_WATER else max(0, dist - 3)
                return c, dmg, "water", depth
            below = (x, cy - 1, z)
            if w.supports(below):
                dist = d0 - cy
                dmg = max(0, dist - 3)
                kind = "hay" if w.cls(below) == "hay" else "solid"
                if kind == "hay":
                    dmg *= 0.2
                return c, dmg, kind, 0
            cy -= 1
        return None

    def _record_fall(self, n, d):
        r = self.fall(n, d)
        if r is None:
            return None
        land, dmg, kind, depth = r
        dist = n[1] - land[1]
        if dmg >= LETHAL_DAMAGE:
            self.fatal.add((n, land, dmg))
            return None
        if dmg > MAX_FALL_DAMAGE:
            self.harsh[(n, land)] = dmg
        self.lands[(n, land)] = (kind, depth, dist)
        return land

    def run_up(self, n, dx, dz, need):
        """`need` open standable cells behind the take-off, in line: the run a sprint needs."""
        w = self.w
        x, y, z = n
        for i in range(1, need + 1):
            c = (x - dx * i, y, z - dz * i)
            if self.body_ok(c) != "stand" or not w.supports((c[0], c[1] - 1, c[2])):
                return False
        return True

    def jump_targets(self, n):
        """Every sprint-jump landing from a standing node, by the REACH table. Yields (dest, gap, void),
        where `void` says every column crossed is open air at the take-off's own feet level: a real leap,
        not a hop over a doorway or a low wall."""
        w = self.w
        x, y, z = n
        if self.body_ok(n) != "stand" or not w.supports((x, y - 1, z)) or w.water(n):
            return
        if not w.is_open((x, y + 2, z)):
            return                              # no room to leave the ground
        for dx, dz in DIRS:
            for dy, reach in list(REACH.items()) + [(-99, DEEP_DROP_REACH)]:
                lo, hi = (-99, -4) if dy == -99 else (dy, dy)
                for gap in range(1, reach + 1):
                    k = gap + 1
                    if dy == -99:
                        # a run-off into open air: the arc carries the player `gap` columns out and then they
                        # FALL, so the landing is whatever the fall model says - the first water, ladder or
                        # floor in that column, never something past it.
                        top = (x + dx * k, y, z + dz * k)
                        if self.body_ok(top) is None or self.stable(top):
                            continue
                        r = self.fall(n, top)
                        if r is None or r[0][1] > y - 4:
                            continue            # a short drop: the REACH rows above already cover it
                        dests = [r[0]]
                    else:
                        dests = [(x + dx * k, y + dy, z + dz * k)]
                    for d in dests:
                        if self.body_ok(d) is None:
                            continue
                        if dy != -99 and (self.body_ok(d) != "stand" or not w.supports((d[0], d[1] - 1, d[2]))):
                            continue
                        need = 0 if gap < 2 else (1 if gap == 2 else 2)
                        if need and not self.run_up(n, dx, dz, need):
                            continue
                        # the arc: the body passes over the gap at the take-off's height
                        arc = []
                        for i in range(1, k):
                            arc.append((x + dx * i, y, z + dz * i))
                            arc.append((x + dx * i, y + 1, z + dz * i))
                            if d[1] > y:
                                arc.append((x + dx * i, y + 2, z + dz * i))
                        if not all(w.is_open(c) for c in arc):
                            continue
                        # a real leap: no column crossed has a floor anywhere between the landing's level and
                        # the take-off's. A hop over a doorway, a bed or a pool is not a gap in a puzzle.
                        void = all(not any(w.supports((x + dx * i, yy, z + dz * i)) or w.water((x + dx * i, yy, z + dz * i))
                                           for yy in range(min(y, d[1]) - 1, y))
                                   for i in range(1, k))
                        if dy == -99:
                            if self._record_fall(n, (x + dx * k, y, z + dz * k)) is None:
                                continue        # the drop kills: not an edge
                        yield d, gap, void
                        break                   # the nearest landing in this column wins

    def edges(self, n):
        w = self.w
        out = []
        x, y, z = n
        here = self.body_ok(n)
        sub = self.submerged(n) or here == "crawl"
        in_bubble = n in self.bubble
        for dx, dz in DIRS:
            for dy in (0, 1):
                d = (x + dx, y + dy, z + dz)
                if not self.inside(d):
                    continue
                ok = self.body_ok(d)
                if ok is None:
                    continue
                if ok == "crawl" and not sub:
                    continue                    # a one-high hole is entered submerged or not at all
                if dy == 1:
                    if not w.supports((d[0], d[1] - 1, d[2])):
                        continue
                    if not w.is_open((x, y + 2, z)) or not w.is_open((d[0], d[1] + 1, d[2])):
                        continue
                    if here == "crawl":
                        continue
                    out.append((d, "step"))
                    continue
                if self.stable(d):
                    out.append((d, "swim" if w.water(d) else "walk"))
                else:
                    land = self._record_fall(n, d)
                    if land is not None and self.inside(land):
                        out.append((land, "fall"))
        for d, gap, void in self.jump_targets(n):
            if self.inside(d):
                if void:
                    self.jumps[(n, d)] = gap
                out.append((d, "jump"))
        for dy in (1, -1):
            d = (x, y + dy, z)
            if not self.inside(d):
                continue
            ok = self.body_ok(d)
            if ok is None:
                continue
            if ok == "crawl" and not sub:
                continue
            if dy < 0 and (in_bubble or d in self.bubble):
                continue                        # a soul-sand bubble column will not let you down
            cur_climb = w.cls(n) in CLIMB
            if w.water(n) and w.water(d):
                out.append((d, "swim"))
            elif dy == 1 and in_bubble and w.water(d):
                out.append((d, "ride"))
            elif cur_climb and w.cls(d) in CLIMB:
                out.append((d, "climb"))
            elif dy == 1 and w.cls(d) in CLIMB and (self.stable(n) or w.water(n)):
                out.append((d, "climb"))
            elif dy == -1 and cur_climb and not w.water(d):
                if self.stable(d):
                    out.append((d, "walk"))
                else:
                    land = self._record_fall(n, d)
                    if land is not None and self.inside(land):
                        out.append((land, "fall"))
            elif dy == 1 and w.water(d) and w.cls(n) in CLIMB:
                out.append((d, "swim"))
        return out

    def graph(self, starts):
        adj = {}
        q = deque()
        for s in starts:
            if s not in adj:
                adj[s] = None
                q.append(s)
        while q:
            n = q.popleft()
            es = self.edges(n)
            adj[n] = es
            for d, _ in es:
                if d not in adj:
                    adj[d] = None
                    q.append(d)
        for k, v in list(adj.items()):
            if v is None:
                adj[k] = []
        return adj


def reachable(adj, starts, blocked=frozenset()):
    seen = set()
    q = deque()
    for s in starts:
        if s in adj and s not in blocked:
            seen.add(s)
            q.append(s)
    while q:
        c = q.popleft()
        for d, _ in adj.get(c) or ():
            if d not in seen and d not in blocked:
                seen.add(d)
                q.append(d)
    return seen


# ------------------------------------------------------------------------------------------------ the report
class Report:
    def __init__(self):
        self.items = []          # (gym id, code, text)
        self.notes = []

    def add(self, gid, kind, code, msg):
        self.items.append((gid, code, "%s %s: %s" % (gid, kind, msg)))

    @property
    def problems(self):
        return [t for _, _, t in self.items]

    def codes(self, gid=None):
        return {c for g, c, _ in self.items if gid is None or g == gid}


def box_str(b):
    return "%d,%d,%d..%d,%d,%d" % tuple(b)


# ------------------------------------------------------------------------------------------------ site checks
def check_site(rep, gid, site, world, ops, zones):
    ext = world.extent
    stray = [b for (_i, _k, b, _s, _m, f) in ops if f is None and not (site.in_lot(b[0], b[2]) and site.in_lot(b[3], b[5]))]
    if stray:
        rep.add(gid, "SITE", "lot", "%d write(s) outside the gym lot rect %s from data/placements.json, e.g. %s"
                % (len(stray), list(site.lot), box_str(stray[0])))
    # the pad: a written column must be seated on it, not floating over a gap of untouched air
    floating = []
    cols = defaultdict(list)
    for (x, y, z) in world.cells:
        cols[(x, z)].append(y)
    for (x, z), ys in cols.items():
        lo = min(ys)
        surf = site.surface(x, z)
        if lo > surf + 1 and any(world.cls((x, yy, z)) == "solid" for yy in ys):
            # is there a written solid anywhere between the surface and this column's foot? then it is carried
            if not any((x, yy, z) in world.cells for yy in range(surf + 1, lo)):
                floating.append((x, lo, z, surf))
    if floating:
        floating.sort()
        rep.add(gid, "SITE", "float", "%d written column(s) start above the pad with untouched air under them, e.g. "
                "x%d z%d starts at y%d over ground y%d" % (len(floating), floating[0][0], floating[0][2], floating[0][1], floating[0][3]))
    # an excavation below the pad that opens into untouched ground
    breach = []
    for c in world.cells:
        x, y, z = c
        if y > site.surface(x, z) or not world.is_open(c):
            continue
        for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)):
            nb = (x + d[0], y + d[1], z + d[2])
            if nb in world.cells:
                continue
            if world.natural(nb) == "rock":
                continue                       # untouched rock is a wall, which is what we want
            breach.append((c, nb))
            break
    if breach:
        breach.sort()
        rep.add(gid, "SITE", "breach", "%d open cell(s) below the pad open into untouched air, e.g. %s beside %s"
                % (len(breach), breach[0][0], breach[0][1]))
    # the spawn-free box
    mine = [zn for zn in zones if zn["box"][0] <= (ext[0] + ext[3]) // 2 <= zn["box"][2]
            and zn["box"][1] <= (ext[2] + ext[5]) // 2 <= zn["box"][3]]
    if len(mine) != 1:
        rep.add(gid, "SITE", "spawn", "%d spawn-free zone(s) in data/spawn_suppression.json hold this building's "
                "centre; expected one" % len(mine))
    else:
        zb = mine[0]["box"]
        out = [(x, z) for (x, _y, z) in world.cells if not (zb[0] <= x <= zb[2] and zb[1] <= z <= zb[3])]
        if out:
            xs = sorted({x for x, _ in out})
            zs = sorted({z for _, z in out})
            rep.add(gid, "SITE", "spawn", "%d written cell(s) lie outside the spawn-free zone %s %s: x%d..%d z%d..%d "
                    "(the build reaches x%d..%d z%d..%d). Wild spawns can appear on that part of the building"
                    % (len(out), mine[0]["id"], zb, xs[0], xs[-1], zs[0], zs[-1], ext[0], ext[3], ext[2], ext[5]))
    # the palette
    bad = sorted({block_name(s).split(":")[0] for s in world.cells.values()} - KNOWN_NAMESPACES)
    if bad:
        rep.add(gid, "SITE", "palette", "block(s) from namespace(s) %s, which the modpack does not carry" % bad)


def check_town(rep, gid, site, world):
    ext = world.extent
    fx0, fz0, fx1, fz1 = ext[0], ext[2], ext[3], ext[5]
    for r in site.others:
        p = r.get("position") or {}
        if isinstance(p.get("x"), int) and fx0 <= p["x"] <= fx1 and fz0 <= p["z"] <= fz1:
            rep.add(gid, "TOWN", "town", "placement %s (%s) stands at (%d,%d) inside the building's footprint"
                    % (r.get("id"), r.get("kind"), p["x"], p["z"]))
    for a in site.plan.get("anchors") or []:
        if a.get("role") in ("gym", "waterfront_gym"):
            continue
        ax0, az0, ax1, az1 = a["rect"]
        if not (ax1 < fx0 or ax0 > fx1 or az1 < fz0 or az0 > fz1):
            rep.add(gid, "TOWN", "town", "anchor %s (%s) %s overlaps the building's footprint x%d..%d z%d..%d"
                    % (a.get("id"), a.get("role"), a["rect"], fx0, fx1, fz0, fz1))
    for s in site.plan.get("streets") or []:
        pl, half = s["polyline"], s["width"] / 2.0
        for (ax, az), (bx, bz) in zip(pl, pl[1:]):
            steps = int(max(abs(bx - ax), abs(bz - az), 1))
            for k in range(steps + 1):
                px, pz = ax + (bx - ax) * k / steps, az + (bz - az) * k / steps
                if fx0 - half <= px <= fx1 + half and fz0 - half <= pz <= fz1 + half:
                    rep.add(gid, "TOWN", "town", "street %s (width %s) runs over the building at about (%d,%d)"
                            % (s.get("id"), s.get("width"), px, pz))
                    break
            else:
                continue
            break


# ------------------------------------------------------------------------------------------- overlap checks
def scan_claims(doc, boxes):
    """(gym, json path, coordinates) for every point or rect in doc that falls in a building's written extent."""
    out = []

    def hit(kind, a):
        res = []
        for n, b in boxes.items():
            if kind == "pt3":
                x, y, z = a
                ok = b[0] <= x <= b[3] and b[1] <= y <= b[4] and b[2] <= z <= b[5]
            elif kind == "pt2":
                ok = b[0] <= a[0] <= b[3] and b[2] <= a[1] <= b[5]
            elif kind == "rect":
                ok = not (a[2] < b[0] or a[0] > b[3] or a[3] < b[2] or a[1] > b[5])
            else:
                ok = not (a[3] < b[0] or a[0] > b[3] or a[5] < b[2] or a[2] > b[5] or a[4] < b[1] or a[1] > b[4])
            if ok:
                res.append(n)
        return res

    def walk(o, path):
        if isinstance(o, dict):
            if isinstance(o.get("x"), (int, float)) and isinstance(o.get("z"), (int, float)):
                y = o.get("y")
                for n in hit("pt3" if isinstance(y, (int, float)) else "pt2",
                             (o["x"], y, o["z"]) if isinstance(y, (int, float)) else (o["x"], o["z"])):
                    out.append((n, path, (o["x"], y, o["z"])))
            for k, v in o.items():
                walk(v, path + "/" + str(k))
        elif isinstance(o, list):
            nums = o and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in o)
            if nums and len(o) in (4, 6) and any(abs(o[i + 2 if len(o) == 4 else i + 3] - o[i]) > 600
                                                 for i in ((0, 1) if len(o) == 4 else (0, 2))):
                pass    # a map-sized region, not a claim on these columns
            elif nums and 200 < abs(o[0]) < 9000 and len(o) in (2, 3, 4, 6):
                kind = {2: "pt2", 3: "pt3", 4: "rect", 6: "box"}[len(o)]
                for n in hit(kind, tuple(o)):
                    out.append((n, path, tuple(o)))
            else:
                for i, v in enumerate(o):
                    walk(v, path + "[%d]" % i)

    walk(doc, "")
    return out


SKIP_FILES = {"placements.json", "spawn_suppression.json", "gym_interiors.json", "world.json"}


def check_overlap(rep, worlds, root, misty):
    seen = {}
    for gid, w in worlds.items():
        for c in w.cells:
            if c in seen and seen[c] != gid:
                rep.add(gid, "OVERLAP", "gym_cells", "writes cell %s that %s also writes" % (c, seen[c]))
                break
            seen[c] = gid
    if misty:
        for gid, w in worlds.items():
            for label, b in misty:
                hits = [c for c in w.cells if b[0] <= c[0] <= b[3] and b[1] <= c[1] <= b[4] and b[2] <= c[2] <= b[5]]
                if hits:
                    rep.add(gid, "OVERLAP", "misty", "%d cell(s) inside Misty's %s %s, which is still built and "
                            "must not be touched, e.g. %s" % (len(hits), label, box_str(b), sorted(hits)[0]))
    boxes = {gid: w.extent for gid, w in worlds.items()}
    for f in sorted((root / "data").glob("*.json")):
        if f.name in SKIP_FILES:
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for gid, path, what in scan_claims(doc, boxes):
            if "site_history" in path:
                continue
            rep.add(gid, "OVERLAP", "data_claim", "%s%s names %s, inside the building" % (f.name, path[:70], what))


# --------------------------------------------------------------------------------------------- route checks
def room_of(rooms, c):
    best = None
    for rid, b in rooms:
        if b[0] <= c[0] <= b[3] and b[1] <= c[1] <= b[4] and b[2] <= c[2] <= b[5]:
            vol = (b[3] - b[0] + 1) * (b[4] - b[1] + 1) * (b[5] - b[2] + 1)
            if best is None or vol < best[0]:
                best = (vol, rid)
    return best[1] if best else None


def node_near(adj, c):
    """The graph node at c, or one block above or below it (a route waypoint may name the block or the feet)."""
    for cand in (c, (c[0], c[1] + 1, c[2]), (c[0], c[1] - 1, c[2]), (c[0], c[1] + 2, c[2])):
        if cand in adj:
            return cand
    return None


def check_route(rep, gid, site, world, record, mv, adj, starts):
    rooms = [(r["id"], tuple(r["box"])) for r in record.get("rooms") or []]
    route = record.get("route") or []
    reach = reachable(adj, starts)

    # 1. the leader's spawner must be reachable at all
    spawner = [c for c, s in world.cells.items() if block_name(s) == "rctmod:trainer_spawner"]
    stand = None
    if not spawner:
        rep.add(gid, "ROUTE", "unreachable", "no rctmod:trainer_spawner in the emitted function")
    else:
        sp = spawner[0]
        cands = [(sp[0] + dx, sp[1] + dy, sp[2] + dz) for dx, dz in DIRS + ((0, 0),) for dy in (0, 1)]
        got = [c for c in cands if c in reach]
        if not got:
            rep.add(gid, "ROUTE", "unreachable", "the leader's spawner at %s cannot be reached on foot from the "
                    "lot's perimeter: the gym cannot be finished" % (sp,))
        else:
            stand = got[0]

    # 2. the route's own waypoints
    pts = []
    for step in route:
        for key in ("from", "to"):
            if step.get(key):
                pts.append((step, key, tuple(step[key])))
    dead = []
    for step, key, c in pts:
        legal = [cand for cand in (c, (c[0], c[1] + 1, c[2]), (c[0], c[1] - 1, c[2]), (c[0], c[1] + 2, c[2]))
                 if mv.body_ok(cand) is not None and mv.stable(cand)]
        node = node_near(adj, c)
        if not legal:
            dead.append((step, key, c, "illegal", "is not a position a player can hold: the cell holds %s over %s"
                         % (world.state(c), world.state((c[0], c[1] - 1, c[2])))))
        elif node is None or node not in reach:
            dead.append((step, key, c, "cut off", "is a legal standing position but cannot be reached on foot "
                                                  "from the gym lot"))
    bad = {(id(s), k): kind for s, k, _c, kind, _w in dead}
    for step, key, c in pts:
        rep.notes.append("%s step %s %s %s %s: %s"
                         % (gid, step.get("step"), step.get("id"), key, list(c),
                            bad.get((id(step), key), "reached")))
    if dead:
        step, key, c, kind, why = dead[0]
        rep.add(gid, "ROUTE", "waypoint", "%d route waypoint(s) are not legal reachable positions (%d illegal, "
                "%d cut off); the first is step %s %s %s (%s), which %s"
                % (len(dead), sum(1 for d in dead if d[3] == "illegal"), sum(1 for d in dead if d[3] == "cut off"),
                   step.get("step"), key, list(c), step.get("id"), why))

    # 3. each step leads to the next
    def dist(a, b, limit=400):
        seen, q = {a: 0}, deque([a])
        while q:
            c = q.popleft()
            if c == b:
                return seen[c]
            if seen[c] > limit:
                return None
            for d, _ in adj.get(c) or ():
                if d not in seen:
                    seen[d] = seen[c] + 1
                    q.append(d)
        return None

    for step in route:
        a, b = step.get("from"), step.get("to")
        if not a or not b:
            continue
        na, nb = node_near(adj, tuple(a)), node_near(adj, tuple(b))
        if na is None or nb is None or na not in reach:
            continue                        # already reported
        l1 = abs(na[0] - nb[0]) + abs(na[1] - nb[1]) + abs(na[2] - nb[2])
        d = dist(na, nb)
        if d is None or d > 3 * l1 + 10:
            rep.add(gid, "ROUTE", "step", "step %s (%s) claims %s -> %s but that is %s in the emitted blocks "
                    "(%d apart as the crow flies)" % (step.get("step"), step.get("id"), list(a), list(b),
                                                      "impossible" if d is None else "%d moves" % d, l1))

    # 4. no trap: every reachable position can get back to a start
    rev = defaultdict(list)
    for a, es in adj.items():
        for d, _ in es:
            rev[d].append(a)
    home = set(s for s in starts if s in adj)
    q = deque(home)
    while q:
        c = q.popleft()
        for p in rev[c]:
            if p not in home:
                home.add(p)
                q.append(p)
    trapped = sorted(c for c in reach if c not in home)
    if trapped:
        rep.add(gid, "ROUTE", "trap", "%d reachable position(s) from which the way out cannot be regained (a trap), "
                "e.g. %s (%s over %s); lowest %s" % (len(trapped), trapped[0], world.state(trapped[0]),
                                                     world.state((trapped[0][0], trapped[0][1] - 1, trapped[0][2])),
                                                     min(trapped, key=lambda c: c[1])))

    # 4b. the same question asked of the design's own claim. When an early stage is broken, everything past it
    #     is cut off and the physics of the later stages goes untested - which is exactly where the builders
    #     said the risk was (Blaine's bubble column, Koga's chute). So run a second graph seeded at the route's
    #     own waypoints as well, and ask the later questions there: they hold IF the earlier stages are fixed.
    def legal_near(c):
        for cand in (c, (c[0], c[1] + 1, c[2]), (c[0], c[1] - 1, c[2]), (c[0], c[1] + 2, c[2])):
            if mv.inside(cand) and mv.body_ok(cand) is not None and mv.stable(cand):
                return cand
        return None

    wps = [n for n in (legal_near(tuple(s[k])) for s in route for k in ("from", "to") if s.get(k))
           if n is not None]
    adj2 = mv.graph(list(starts) + wps)
    reach2 = reachable(adj2, list(starts) + wps)
    rev2 = defaultdict(list)
    for a, es in adj2.items():
        for d, _ in es:
            rev2[d].append(a)
    home2 = set(s for s in starts if s in adj2)
    q = deque(home2)
    while q:
        c = q.popleft()
        for p in rev2[c]:
            if p not in home2:
                home2.add(p)
                q.append(p)
    trapped2 = sorted(c for c in reach2 if c not in home2 and c not in reach)
    if trapped2:
        rep.add(gid, "ROUTE", "trap_later", "%d position(s) on the design's own later stages from which the lot "
                "cannot be regained even with the earlier stages fixed (a trap), e.g. %s (%s over %s); lowest %s"
                % (len(trapped2), trapped2[0], world.state(trapped2[0]),
                   world.state((trapped2[0][0], trapped2[0][1] - 1, trapped2[0][2])),
                   min(trapped2, key=lambda c: c[1])))

    # 4c. every fall the design declares, measured from the cell the design names
    for step in route:
        how = (step.get("how") or "").lower()
        if "fall" not in how and "drop" not in how or not step.get("from"):
            continue
        a = tuple(step["from"])
        src = node_near(adj2, a) or a
        below = (src[0], src[1] - 1, src[2])
        r = mv.fall(src, below) if not mv.stable(below) else None
        if r is None and step.get("to"):
            t = tuple(step["to"])
            r = mv.fall((t[0], src[1], t[2]), (t[0], src[1] - 1, t[2]))
        if r is None:
            continue
        land, dmg, kind, depth = r
        dist_ = src[1] - land[1]
        rep.notes.append("%s step %s %s: a %d-block fall from %s lands %s (%s, water %d deep) for %.1f damage"
                         % (gid, step.get("step"), step.get("id"), dist_, src, land, kind, depth, dmg))
        if dist_ > MAX_FALL and kind not in ("hay", "water"):
            rep.add(gid, "ROUTE", "declared_fall", "step %s (%s) is a %d-block fall from %s onto %s at %s for %.1f "
                    "damage; data/gym_interiors.json rules.max_fall is %d and a longer fall must land on hay"
                    % (step.get("step"), step.get("id"), dist_, src, kind, land, dmg, MAX_FALL))
        elif dmg > MAX_FALL_DAMAGE:
            rep.add(gid, "ROUTE", "declared_fall", "step %s (%s) is a %d-block fall from %s onto %s at %s and costs "
                    "%.1f damage, over the %d a route may" % (step.get("step"), step.get("id"), dist_, src, kind,
                                                              land, dmg, MAX_FALL_DAMAGE))

    # 5. falls
    live_fatal = sorted((a, b, d) for (a, b, d) in mv.fatal if a in reach)
    if live_fatal:
        a, b, d = live_fatal[0]
        rep.add(gid, "ROUTE", "fatal", "%d fall(s) on the reachable route that would kill, e.g. %s -> %s for %.0f "
                "damage" % (len(live_fatal), a, b, d))
    live_harsh = sorted((k, v) for k, v in mv.harsh.items() if k[0] in reach)
    if live_harsh:
        (a, b), dmg = live_harsh[0]
        rep.add(gid, "ROUTE", "harsh", "%d uncushioned fall(s) over %d damage, e.g. %s -> %s for %.0f"
                % (len(live_harsh), MAX_FALL_DAMAGE, a, b, dmg))
    for (a, b), (kind, depth, d) in sorted(mv.lands.items()):
        if a not in reach:
            continue
        if d > MAX_FALL and kind not in ("hay", "water", "climb"):
            rep.add(gid, "ROUTE", "harsh", "a %d-block fall from %s lands on %s at %s; data/gym_interiors.json "
                    "rules.max_fall is %d and a longer fall must land on hay" % (d, a, kind, b, MAX_FALL))
        if kind == "water" and depth < MIN_LANDING_WATER and d >= 4:
            rep.add(gid, "WATER", "landing", "a %d-block fall from %s lands in water %d deep at %s (needs %d)"
                    % (d, a, depth, b, MIN_LANDING_WATER))

    # 6. nothing the route gates can be skipped
    if stand is not None and rooms:
        seq = []
        for step in route:
            for key in ("from", "to"):
                if not step.get(key):
                    continue
                r = room_of(rooms, tuple(step[key]))
                if r and (not seq or seq[-1] != r):
                    seq.append(r)
        leader_room = room_of(rooms, stand)
        gating = []
        # the route's FIRST room is the way in, not a gate: a player is meant to be able to reach it, and
        # closing it off only says the building has a second door. Every room after it must be unavoidable.
        for r in seq[1:]:
            if r == leader_room or r in gating:
                continue
            gating.append(r)
        boxes = {rid: b for rid, b in rooms}
        for r in gating:
            b = boxes[r]
            blocked = frozenset(c for c in adj if b[0] <= c[0] <= b[3] and b[1] <= c[1] <= b[4] and b[2] <= c[2] <= b[5])
            if not blocked:
                continue
            if stand in reachable(adj, starts, blocked):
                rep.add(gid, "ROUTE", "skip", "room %s %s can be skipped: the leader's spawner is still reachable "
                        "from the lot with every position in it closed off" % (r, list(b)))

    # 7. a gap the design calls uncrossable that the jump model crosses between two rooms the route
    #    does not join consecutively
    pair_ok = set()
    seq2 = []
    for step in route:
        for key in ("from", "to"):
            if step.get(key):
                r = room_of(rooms, tuple(step[key]))
                if r and (not seq2 or seq2[-1] != r):
                    seq2.append(r)
    for a, b in zip(seq2, seq2[1:]):
        pair_ok.add(frozenset((a, b)))
    wide = defaultdict(list)
    for (a, d), gap in mv.jumps.items():
        # only level-ish leaps: a jump DOWN off a walkway into the room below is the way down, not a shortcut,
        # and every elevated deck has one. A gate made of a gap is always crossed level or up.
        if a not in reach2 or gap < 2 or abs(d[1] - a[1]) > 1:
            continue
        ra, rd = room_of(rooms, a), room_of(rooms, d)
        if ra is None or rd is None or ra == rd or frozenset((ra, rd)) in pair_ok:
            continue
        wide[frozenset((ra, rd))].append((gap, a, d))
    for pair, ex in sorted(wide.items(), key=lambda kv: sorted(kv[0])):
        gap, a, d = max(ex)
        rep.add(gid, "ROUTE", "gap", "rooms %s are joined by a sprint jump over a real void (widest %d "
                "blocks, %d such jumps, e.g. %s -> %s) and the route never joins them"
                % (" and ".join(sorted(pair)), gap, len(ex), a, d))

    # 8. bubble columns. A soul-sand column is a one-way lift: it must carry a player from its foot to its head
    #    and it must not be descendable, or a room whose only exit it is becomes a trap or a way in.
    for c, st in sorted(world.cells.items()):
        if block_name(st) != "minecraft:soul_sand":
            continue
        col = sorted(cc for cc in mv.bubble if (cc[0], cc[2]) == (c[0], c[2]))
        if not col:
            continue
        foot, head = col[0], col[-1]
        inside_col = set(col)
        # the column's own moves, not what can be reached round it: does each cell lead to the one above,
        # does any lead to the one below, and can a player get in at the foot and out at the head at all?
        up_break = [cc for cc in col[:-1]
                    if (cc[0], cc[1] + 1, cc[2]) not in {d for d, _ in mv.edges(cc)}]
        down_edges = [(cc, (cc[0], cc[1] - 1, cc[2])) for cc in col
                      if (cc[0], cc[1] - 1, cc[2]) in {d for d, _ in mv.edges(cc)}
                      and (cc[0], cc[1] - 1, cc[2]) in inside_col]
        into_foot = [n for n in adj2 if n not in inside_col and foot in {d for d, _ in adj2[n]}]
        out_of_head = [d for d, _ in mv.edges(head) if d not in inside_col]
        if up_break:
            rep.add(gid, "ROUTE", "bubble", "the bubble column over the soul sand at %s breaks at %s: it does not "
                    "carry a player from its foot %s to its head %s" % (c, up_break[0], foot, head))
        if down_edges:
            rep.add(gid, "ROUTE", "bubble", "the bubble column over the soul sand at %s can be swum down (%s -> %s): "
                    "whatever it guards is reachable without the route" % (c, down_edges[0][0], down_edges[0][1]))
        if not into_foot:
            rep.add(gid, "ROUTE", "bubble", "nothing can reach the foot of the bubble column at %s: it is cased on "
                    "all four sides for every course, so it is not an entrance and not an exit" % (foot,))
        if not out_of_head:
            rep.add(gid, "ROUTE", "bubble", "the head of the bubble column at %s leads nowhere: a player carried up "
                    "it cannot step off" % (head,))
        rep.notes.append("%s bubble column over %s: %d cells, foot %s head %s, %d way(s) in at the foot, %d way(s) "
                         "off the head" % (gid, c, len(col), foot, head, len(into_foot), len(out_of_head)))

    # 9. the leader's chest must be reachable too, or the reward cannot be taken
    chests = [cc for cc, s in world.cells.items() if block_name(s) == "minecraft:chest"]
    if chests and stand is not None:
        open_from = [cc for ch in chests
                     for cc in [(ch[0] + dx, ch[1] + dy, ch[2] + dz) for dx, dz in DIRS for dy in (0, 1)]]
        if not any(cc in reach for cc in open_from):
            rep.add(gid, "ROUTE", "chest", "no chest can be opened from any reachable position (chests at %s)"
                    % sorted(chests)[:3])
    return reach, stand


# --------------------------------------------------------------------------------------------- water & blocks
def flow_extent(world, sources, limit=4000):
    """Air cells flowing water from the sources reaches: seven along a floor, down any drop. An upper bound."""
    src = set(sources)
    best = {c: 0 for c in src}
    q = deque((c, 0) for c in src)
    free = ("air", "sky")
    while q and len(best) < limit:
        c, lvl = q.popleft()
        x, y, z = c
        below = (x, y - 1, z)
        if world.cls(below) in free:
            if below not in best:
                best[below] = 0
                q.append((below, 0))
            continue
        if lvl >= 7:
            continue
        for dx, dz in DIRS:
            nb = (x + dx, y, z + dz)
            if world.cls(nb) in free and best.get(nb, 99) > lvl + 1:
                best[nb] = lvl + 1
                q.append((nb, lvl + 1))
    return set(best) - src


def check_water(rep, gid, world, adj, reach):
    for fluid, code, spread in (("minecraft:water", "leak", 7), ("minecraft:lava", "lava", 3)):
        leaks = []
        for c, st in world.cells.items():
            if block_name(st) != fluid:
                continue
            x, y, z = c
            for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)):
                nb = (x + d[0], y + d[1], z + d[2])
                if world.cls(nb) in ("air", "sky"):
                    leaks.append((c, nb))
                    break
        if leaks:
            leaks.sort()
            wet = flow_extent(world, [c for c, _ in leaks])
            rep.add(gid, "WATER", code, "%d %s source(s) with air beside or under them, which will flow out of "
                    "their box, e.g. %s into %s; the flow reaches about %d open cells"
                    % (len(leaks), fluid.split(":")[1], leaks[0][0], leaks[0][1], len(wet)))
    if adj is None:
        return
    mv = Moves(world)
    sub = {c for c in reach if mv.submerged(c)}
    if not sub:
        return
    rev, fwd = defaultdict(list), defaultdict(list)
    for a, es in adj.items():
        for d, _ in es:
            rev[d].append(a)
            fwd[a].append(d)

    def spread_bfs(links):
        out, q = {}, deque()
        for c in reach:
            if c not in sub:
                out[c] = 0
                q.append(c)
        while q:
            c = q.popleft()
            for p in links[c]:
                if p in sub and p not in out:
                    out[p] = out[c] + 1
                    q.append(p)
        return out

    to_air = spread_bfs(rev)
    from_air = spread_bfs(fwd)
    stuck = sorted(c for c in sub if c not in to_air)
    if stuck:
        rep.add(gid, "WATER", "drown_trap", "%d submerged position(s) with no way to air, e.g. %s (a drowning trap)"
                % (len(stuck), stuck[0]))
    worst = None
    for c in sub:
        if c in to_air and c in from_air:
            t = to_air[c] + from_air[c]
            if worst is None or t > worst[0]:
                worst = (t, c)
    if worst:
        rep.notes.append("%s longest head-under-water trip there and back: %d blocks (limit %d), at %s"
                         % (gid, worst[0], MAX_SUBMERGED_ROUNDTRIP, worst[1]))
        if worst[0] > MAX_SUBMERGED_ROUNDTRIP:
            rep.add(gid, "WATER", "drown", "a player can be %d blocks under water there and back from %s, over the "
                    "%d one breath allows" % (worst[0], worst[1], MAX_SUBMERGED_ROUNDTRIP))


def check_blocks(rep, gid, world):
    ladders, lanterns, chains, falling = [], [], [], []
    for c, st in sorted(world.cells.items()):
        name = block_name(st)
        p = props(st)
        if name in NEEDS_BEHIND:
            d = BEHIND.get(p.get("facing", "north"))
            back = (c[0] + d[0], c[1], c[2] + d[2])
            if not world.supports(back):
                ladders.append((c, back, world.state(back)))
        elif name in ("minecraft:lantern", "minecraft:soul_lantern"):
            up = p.get("hanging") == "true"
            hold = (c[0], c[1] + (1 if up else -1), c[2])
            if not world.supports(hold) and block_name(world.state(hold) or "") not in LANTERN_STANDS_ON:
                lanterns.append((c, "above" if up else "below", world.state(hold)))
        elif name == "minecraft:chain":
            up, dn = world.state((c[0], c[1] + 1, c[2])), world.state((c[0], c[1] - 1, c[2]))
            if not world.supports((c[0], c[1] + 1, c[2])) and block_name(up or "") != "minecraft:chain" \
                    and not world.supports((c[0], c[1] - 1, c[2])) and block_name(dn or "") != "minecraft:chain":
                chains.append(c)
        elif name in NEEDS_BELOW:
            if not world.supports((c[0], c[1] - 1, c[2])):
                falling.append((c, name))
    if ladders:
        rep.add(gid, "BLOCKS", "ladder", "%d ladder cell(s) with nothing solid behind them, e.g. %s (behind: %s at %s)"
                % (len(ladders), ladders[0][0], ladders[0][2], ladders[0][1]))
    if lanterns:
        rep.add(gid, "BLOCKS", "lantern", "%d lantern(s) with nothing to hang from or stand on, e.g. %s (%s it: %s)"
                % (len(lanterns), lanterns[0][0], lanterns[0][1], lanterns[0][2]))
    if chains:
        rep.add(gid, "BLOCKS", "chain", "%d chain(s) with nothing over or under them, e.g. %s" % (len(chains), chains[0]))
    if falling:
        rep.add(gid, "BLOCKS", "falling", "%d block(s) that need something under them and have nothing, e.g. %s %s"
                % (len(falling), falling[0][0], falling[0][1]))
    leaves = sorted(c for c, st in world.cells.items()
                    if block_name(st).endswith("_leaves") and props(st).get("persistent") != "true")
    if leaves:
        rep.add(gid, "BLOCKS", "leaves", "%d leaf block(s) without persistent=true, e.g. %s %s: with no log within "
                "six blocks they decay" % (len(leaves), leaves[0], world.state(leaves[0])))


# ------------------------------------------------------------------------------------------------------ driver
def seeds(site, world):
    """The standable cells on the gym lot's own perimeter, at pad level: where a player arrives from the town.
    Independent of whatever the record calls its door."""
    x0, z0, x1, z1 = site.lot
    y = site.level + 1
    out = []
    ring = [(x, z) for x in range(x0, x1 + 1) for z in (z0, z1)] + \
           [(x, z) for z in range(z0 + 1, z1) for x in (x0, x1)]
    for x, z in ring:
        c = (x, y, z)
        if world.is_open(c) and world.is_open((x, y + 1, z)) and world.supports((x, y - 1, z)):
            out.append(c)
    return out


def graph_box(site, world):
    x0, z0, x1, z1 = site.lot
    e = world.extent
    return (x0, min(e[1], site.level) - 4, z0, x1, e[4] + 4, z1)


def run(texts, records, placements, ground, root=ROOT, only=None):
    rep = Report()
    zones = json.loads((root / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))["spawn_free_zones"]
    interiors = json.loads((root / "data" / "gym_interiors.json").read_text(encoding="utf-8"))
    misty = []
    for g in interiors["gyms"]:
        if g["id"] == "gym2" and g.get("built"):
            if g.get("dig"):
                misty.append(("dig", tuple(g["dig"])))
            if (g.get("shell") or {}).get("expect_box"):
                misty.append(("shell", tuple(g["shell"]["expect_box"])))
    sites, worlds, extras = {}, {}, {}
    for gid in sorted(records):
        if only and gid not in only:
            continue
        rec = records[gid]
        if texts.get(gid) is None:
            rep.add(gid, "SITE", "missing", "no emitted function %s.mcfunction" % gid)
            continue
        ops, unknown = parse(texts[gid], gid)
        for u in unknown:
            rep.add(gid, "SITE", "unmodelled", "a command this audit cannot model: %s" % u)
        site = Site(gid, rec["settlement"], placements, ground)
        world = World(site, ops)
        sites[gid], worlds[gid] = site, world
        check_site(rep, gid, site, world, ops, zones)
        check_town(rep, gid, site, world)
        check_blocks(rep, gid, world)
        st = seeds(site, world)
        if not st:
            rep.add(gid, "ROUTE", "unreachable", "no standable cell on the gym lot's perimeter at pad level y%d: "
                    "a player cannot get to the site" % (site.level + 1))
            check_water(rep, gid, world, None, set())
            continue
        mv = Moves(world, graph_box(site, world))
        adj = mv.graph(st)
        reach, stand = check_route(rep, gid, site, world, rec, mv, adj, st)
        check_water(rep, gid, world, adj, reach)
        extras[gid] = (mv, adj, st, reach, stand)
    check_overlap(rep, worlds, root, misty)
    return rep, sites, worlds, extras


def load_texts(funcs_dir, ids):
    d = Path(funcs_dir)
    out = {}
    for gid in ids:
        f = d / ("%s.mcfunction" % gid)
        out[gid] = f.read_text(encoding="utf-8") if f.is_file() else None
    return out


def load_records(root=ROOT):
    out = {}
    for p in sorted((root / "data" / "gym_buildings").glob("*.json")):
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--functions", default=str(DEFAULT_FUNCS))
    ap.add_argument("--source-root", default=None)
    ap.add_argument("--gym", action="append", default=None, help="one record only, e.g. gym7 (repeatable)")
    ap.add_argument("--verbose", action="store_true", help="also print the measurements behind the checks")
    a = ap.parse_args(argv)
    import ground as G

    records = load_records()
    if not records:
        print("data/gym_buildings holds no record: there is nothing to audit")
        return 2
    texts = load_texts(a.functions, sorted(records))
    if all(v is None for v in texts.values()):
        print("no emitted functions in %s: run python tools/gym_buildings.py build first" % a.functions)
        return 2
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    rep, sites, _worlds, _extras = run(texts, records, placements, G.load(a.source_root),
                                       only=set(a.gym) if a.gym else None)
    if a.verbose:
        for note in rep.notes:
            print("  note:", note)
    if rep.problems:
        for p in rep.problems:
            print(p)
        print("gym buildings (independent): %d problem(s) over %d building(s)" % (len(rep.problems), len(sites)))
        return 1
    print("gym buildings (independent): clean over %d building(s)" % len(sites))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
