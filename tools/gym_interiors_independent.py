#!/usr/bin/env python
"""Independent audit of the emitted gym interiors (the six .mcfunction files of the gym_interiors pack).

WHY THIS EXISTS. tools/gym_interiors_audit.py was written by the agent that wrote tools/gym_interiors.py, and it
takes its expectations from data/gym_interiors.json, which is what the generator read. That proves the generator
ran, not that the interiors fit their sites (CLAUDE.md, "Verify before claiming": an expectation derived from the
artifact being checked is not an expectation). This audit reads the emitted text and nothing the generator
computed, and compares it with sources the generator does not write:

  the site      data/placements.json: the gym's own lot (settlement plan anchor `gym` rect and `level`), the shell's
                position/size/rotation (box worked out here, not imported from place_donor), every other
                placement, anchor and street in the same town
  the ground    tools/ground.py, rounded: the heightmap, never a world save
  the physics   a player-movement model written here (walk, one-block jump, fall damage, ladders, scaffolding,
                swimming, crawling, bubble columns) run over the voxels the functions produce
  the shell     docs/mechanics/GYM_INTERIORS.md "Q1 ANSWERED": the interior floor is 2 above the shell's base
                (26 for Misty's), which is where the shaft must end
  the world     every other data/*.json file, scanned for anything that already claims the same columns

Checks (each prints only a problem):
  SITE     every write inside the gym's lot; nothing above the ground outside the shell; nothing written into the
           shell except one vertical column, on the healing machine's cell, ending at the hall floor; every open cell
           has cover to the surface and to the hall floor; no open cell touches sky or the shell's inside except
           through that column; no other building, anchor or street of the town on the lot; the dig inside its
           spawn-free zone; no spawn-condition block in the palette
  HEALER   the healing-machine removal covers each of the eight placed shells exactly
  OVERLAP  no two gyms write the same cell; no other data file's coordinates land in a dig
  ROUTE    the physics graph from the shaft top: every design waypoint is a legal position and reachable and leads to
           the next, every reachable position can get back to the shaft top (no trap), no fall kills, no room joins a
           room the route does not join it to, no outbound room can be skipped, no guard can be walked round (a
           sight ball round his seat), one-block-high passages are only entered from deep water
  WATER    every water source is sealed (no air beside it or under it) and its spread is sized, landing water is deep
           enough, no submerged pocket is too far from air
  BLOCKS   ladders have a wall behind them, scaffolding columns stand on something, lanterns hang from or stand on a
           block, leaves are persistent

  python tools/gym_interiors_independent.py [--functions DIR] [--source-root ROOT] [--verbose]
Exit 0 with one line when clean; 1 with the problems; 2 when there is nothing built to audit.
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

# The ground rule (tools/ground_rule.py): this tool reads no world. Ground is the heightmap.
WORLD_READS = set()

DEFAULT_FUNCS = ROOT / "build" / "datapacks" / "cobblers_gym_interiors" / "data" / "cobblers" / "function" / "gym_interiors"


def built_gyms(root=ROOT):
    """The gyms data/gym_interiors.json still marks `built`, which is what tools/gym_interiors.py emits.

    The owner's 2026-09-29 redesign (docs/world-building/GYM_BUILDINGS_BRIEF.md) replaced the works under gyms 1, 3, 4,
    5 and 7 with authored buildings and set those records `built: false`; only Misty's gym 2 is still carved. Auditing a
    fixed list would report five missing functions and hide the one interior that is left. The buildings that superseded
    them are audited by tools/gym_buildings_independent.py, which carries every check in this file across."""
    try:
        doc = json.loads((Path(root) / "data" / "gym_interiors.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return (2,)
    return tuple(sorted(int(g["id"][3:]) for g in doc["gyms"] if g.get("built")))


GYM_NUMBERS = built_gyms()

# ---- numbers this audit holds itself (NOT read from data/gym_interiors.json) -----------------------------------------
INTERIOR_FLOOR = {"misty": 26}      # docs/mechanics/GYM_INTERIORS.md Q1: standable floor above the shell's base
INTERIOR_FLOOR_DEFAULT = 2
MIN_COVER = 3                       # solid blocks between the top of any open cell and the surface / the hall floor
MAX_FALL_DAMAGE = 10                # health points (5 hearts) a route may cost in one uncushioned fall
LETHAL_DAMAGE = 20                  # a full health bar
MIN_LANDING_WATER = 2               # water this deep negates any fall (the wiki says one; two leaves a margin)
MAX_SUBMERGED_ROUNDTRIP = 28        # blocks of head-under-water travel in and out (300 ticks of air at ~2 blocks/s)
JUMP = 1                            # a player clears one block by jumping, not two

FACING = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


# ------------------------------------------------------------------------------------------------------- the text
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SET = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$")


def parse(text, name="?"):
    """[(index, kind, box, state)] for the fills/setblocks, and a list of lines nothing here understands."""
    ops, unknown = [], []
    for i, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("forceload "):
            continue
        m = FILL.match(line)
        if m:
            x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
            ops.append((i, "fill", (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1)),
                        m.group(7), m.group(8)))
            continue
        m = SET.match(line)
        if m:
            x, y, z = (int(v) for v in m.groups()[:3])
            ops.append((i, "set", (x, y, z, x, y, z), m.group(4), None))
            continue
        unknown.append("%s:%d %s" % (name, i + 1, line[:80]))
    return ops, unknown


def block_name(state):
    return state.split("[", 1)[0]


def props(state):
    if "[" not in state:
        return {}
    return dict(kv.split("=", 1) for kv in state[state.index("[") + 1:state.rindex("]")].split(",") if "=" in kv)


# ----------------------------------------------------------------------------------------------- block classes
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
PASS = {"minecraft:lantern", "minecraft:soul_lantern", "minecraft:sculk_sensor", "minecraft:stonecutter",
        "minecraft:torch", "minecraft:wall_torch"}   # shorter than a step (or hung clear of the head): no wall, no floor


def cls_of(state):
    n = block_name(state)
    if n in AIR:
        return "air"
    if n == "minecraft:water":
        return "water"
    if n == "minecraft:ladder":
        return "ladder"
    if n == "minecraft:scaffolding":
        return "scaf"
    if n == "minecraft:hay_block":
        return "hay"
    if n in PASS:
        return "pass"
    return "solid"


OPEN = {"air", "water", "ladder", "scaf", "pass", "sky"}
SUPPORT = {"solid", "hay", "rock", "shell"}
CLIMB = {"ladder", "scaf"}


# ------------------------------------------------------------------------------------------------ the site
def shell_box(rec):
    """Inclusive box of a placed template, worked out here from Minecraft's rotation of a size about its corner."""
    x, y, z = rec["position"]["x"], rec["position"]["y"], rec["position"]["z"]
    sx, sy, sz = rec["size"]
    rot = rec.get("rotation", "none")
    if rot == "none":
        xs, zs = (x, x + sx - 1), (z, z + sz - 1)
    elif rot == "180":
        xs, zs = (x - sx + 1, x), (z - sz + 1, z)
    elif rot == "clockwise_90":
        xs, zs = (x - sz + 1, x), (z, z + sx - 1)
    elif rot == "counterclockwise_90":
        xs, zs = (x, x + sz - 1), (z - sx + 1, z)
    else:
        raise ValueError("unknown rotation %r" % rot)
    return (xs[0], y, zs[0], xs[1], y + sy - 1, zs[1])


def rotate_offset(dx, dz, rot):
    """A template-relative offset in the world, for Minecraft's four structure rotations (clockwise turns x,z to -z,x)."""
    if rot == "none":
        return dx, dz
    if rot == "180":
        return -dx, -dz
    if rot == "clockwise_90":
        return -dz, dx
    if rot == "counterclockwise_90":
        return dz, -dx
    raise ValueError("unknown rotation %r" % rot)


class Site:
    """Everything about one gym that comes from data/placements.json and the heightmap."""

    def __init__(self, n, placements, ground, measured=None):
        self.n = n
        self.town = "gym%d_town" % n
        recs = [r for r in placements["placements"] if isinstance(r, dict)]
        donors = [r for r in recs if r.get("id", "").startswith("gym%d_" % n) and r.get("pack_template")
                  and r.get("kind") in ("gym", "donor")]
        if len(donors) != 1:
            raise SystemExit("gym%d: expected exactly one donor placement in data/placements.json, found %d" % (n, len(donors)))
        self.rec = donors[0]
        self.shell = shell_box(self.rec)
        plan = placements["settlements"][self.town]["plan"]
        anchor = [a for a in plan["anchors"] if a["role"] in ("gym", "waterfront_gym")]
        if len(anchor) != 1:
            raise SystemExit("gym%d: expected one gym anchor in %s's plan" % (n, self.town))
        self.lot = tuple(anchor[0]["rect"])            # x0 z0 x1 z1
        self.level = anchor[0].get("level")
        self.plan = plan
        self.others = [r for r in recs if r.get("settlement") == self.town and r is not self.rec]
        self.ground = ground
        floor = INTERIOR_FLOOR["misty"] if "misty" in self.rec["id"] else INTERIOR_FLOOR_DEFAULT
        self.hall_stand = self.rec["position"]["y"] + floor      # feet level of a player standing in the hall
        self.hall_floor_top = self.hall_stand - 1
        # where the healing machine stood in the template, the one hall cell known to be free floor (docs/mechanics/
        # GYM_INTERIORS.md Q1, measured from the Cobbleverse templates; carried in data/gym_interiors.json `measured`)
        self.healer = None
        if measured:
            rel = measured["misty_relative" if "misty" in self.rec["id"] else "small_gym_relative"]["healing_machine"]
            dx, dz = rotate_offset(rel[0], rel[2], self.rec.get("rotation", "none"))
            self.healer = (self.rec["position"]["x"] + dx, self.rec["position"]["y"] + rel[1], self.rec["position"]["z"] + dz)
        x0, z0, x1, z1 = self.lot
        self._h = ground.box(x0, z0, x1, z1)

    def surface(self, x, z):
        """The lowest the surface can be here: the heightmap, or the lot's levelled height if that is lower."""
        x0, z0, x1, z1 = self.lot
        if not (x0 <= x <= x1 and z0 <= z <= z1):
            return int(self.ground(x, z))
        h = int(self._h[z - z0, x - x0])
        return min(h, self.level) if self.level is not None else h

    def in_lot(self, x, z):
        x0, z0, x1, z1 = self.lot
        return x0 <= x <= x1 and z0 <= z <= z1

    def in_shell(self, x, y, z):
        b = self.shell
        return b[0] <= x <= b[3] and b[1] <= y <= b[4] and b[2] <= z <= b[5]

    def in_shell_footprint(self, x, z):
        b = self.shell
        return b[0] <= x <= b[3] and b[2] <= z <= b[5]


# ------------------------------------------------------------------------------------------------- the voxels
class World:
    """The written cells of one gym, in order, over a natural world that is rock under the surface, the shell's
    box where the shell stands, and sky above."""

    def __init__(self, site, ops):
        self.site = site
        self.cells = {}
        self.history = defaultdict(list)     # cell -> [(op index, state)]
        for (i, kind, b, state, filt) in ops:
            if filt:
                continue      # a replace-filtered fill only swaps blocks that are already there
            for x in range(b[0], b[3] + 1):
                for y in range(b[1], b[4] + 1):
                    for z in range(b[2], b[5] + 1):
                        self.cells[(x, y, z)] = state
                        self.history[(x, y, z)].append((i, state))
        self._cls = {}
        self.hall_col = None     # (x, z) of the one column the works open into the hall

    def natural(self, c):
        s = self.site
        x, y, z = c
        if s.in_shell(x, y, z):
            if self.hall_col == (x, z) and y >= s.hall_stand:
                return "sky"     # the hall itself: open air over its floor
            return "shell"
        if y <= s.surface(x, z):
            return "rock"
        return "sky"

    def cls(self, c):
        v = self._cls.get(c)
        if v is None:
            st = self.cells.get(c)
            v = cls_of(st) if st is not None else self.natural(c)
            self._cls[c] = v
        return v

    def state(self, c):
        return self.cells.get(c)

    def is_open(self, c):
        return self.cls(c) in OPEN

    def supports(self, c):
        return self.cls(c) in SUPPORT

    def water(self, c):
        return self.cls(c) == "water"


# ---------------------------------------------------------------------------------------------- the movement
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Moves:
    """The player-movement graph. Nodes are feet cells."""

    def __init__(self, world):
        self.w = world
        self.bubble = self._bubble_cells()
        self.fatal = set()     # (from, to, damage) falls that kill
        self.refused = set()   # (from, to): a one-high flooded passage that the player cannot enter from there
        self.harsh = {}        # (from, to) -> damage, uncushioned falls above MAX_FALL_DAMAGE
        self.lands = {}        # (from, to) -> (kind, water depth)

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

    def body_ok(self, c):
        """Can a player's body be at feet cell c: normal (two open cells) or crawling (feet in water, head in stone)."""
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
        return w.supports((x, y - 1, z)) or w.cls((x, y - 1, z)) == "scaf"

    def submerged(self, c):
        x, y, z = c
        return self.w.water(c) and (self.w.water((x, y + 1, z)) or self.body_ok(c) == "crawl")

    def fall(self, start, top):
        """Fall from feet cell `top` (already unsupported) in column of `start`. Returns (landing cell, damage, kind, depth)
        or None when the column never lands (it would be the world's floor)."""
        w = self.w
        x, y, z = top
        d0 = start[1]
        cy = y
        while True:
            c = (x, cy, z)
            if not w.is_open((x, cy, z)):
                return None
            if w.cls(c) in CLIMB:
                return c, 0, "climb", 0
            if w.water(c):
                # depth of water from here down to the first solid
                depth, yy = 0, cy
                while w.water((x, yy, z)):
                    depth += 1
                    yy -= 1
                dist = d0 - cy
                dmg = 0 if depth >= 2 else max(0, dist - 3)
                return c, dmg, "water", depth
            below = (x, cy - 1, z)
            if w.supports(below):
                dist = d0 - cy
                dmg = max(0, dist - 3)
                kind = "hay" if w.cls(below) == "hay" else "solid"
                if kind == "hay":
                    dmg = dmg * 0.2
                return c, dmg, kind, 0
            if cy < -60:
                return None
            cy -= 1

    def edges(self, n):
        """[(dest, why)] from stable node n."""
        w = self.w
        out = []
        x, y, z = n
        here = self.body_ok(n)
        sub = self.submerged(n) or here == "crawl"
        in_bubble = n in self.bubble
        for dx, dz in DIRS:
            for dy in (0, 1):
                d = (x + dx, y + dy, z + dz)
                ok = self.body_ok(d)
                if ok is None:
                    continue
                if ok == "crawl" and not sub:
                    self.refused.add((n, d))
                    continue                    # a one-high hole is entered submerged or not at all
                if dy == 1:
                    # a jump: the ledge is under the destination, and there is room over the start
                    if not w.supports((d[0], d[1] - 1, d[2])):
                        continue
                    if not w.is_open((x, y + 2, z)) or not w.is_open((d[0], d[1] + 1, d[2])):
                        continue
                    if here == "crawl":
                        continue
                    out.append((d, "step"))
                    continue
                if self.stable(d):
                    out.append((d, "walk" if not w.water(d) else "swim"))
                else:
                    r = self.fall(n, d)
                    if r is None:
                        continue
                    land, dmg, kind, depth = r
                    if dmg >= LETHAL_DAMAGE:
                        self.fatal.add((n, land, dmg))
                        continue
                    if dmg > MAX_FALL_DAMAGE:
                        self.harsh[(n, land)] = dmg
                    self.lands[(n, land)] = (kind, depth, n[1] - land[1])
                    out.append((land, "fall"))
        # a running jump over a gap of one or two blocks, level or one lower
        if here == "stand" and w.supports((x, y - 1, z)):
            for dx, dz in DIRS:
                for k in (2, 3):
                    for dy in (0, -1):
                        d = (x + dx * k, y + dy, z + dz * k)
                        if self.body_ok(d) != "stand" or not w.supports((d[0], d[1] - 1, d[2])):
                            continue
                        arc = [(x + dx * i, y + h, z + dz * i) for i in range(1, k) for h in (0, 1, 2)]
                        if dy == -1:
                            arc += [(x + dx * i, y - 1, z + dz * i) for i in range(1, k)]
                            arc = [c for c in arc if c[1] >= y]
                        if k == 3:
                            # a two-block gap needs a sprint, so two blocks of floor to run up on behind the take-off
                            run = [(x - dx * i, y, z - dz * i) for i in (1, 2)]
                            if not all(w.is_open(c) and w.is_open((c[0], c[1] + 1, c[2])) and w.supports((c[0], c[1] - 1, c[2])) for c in run):
                                continue
                        if all(w.is_open(c) for c in arc) and w.is_open((x, y + 2, z)):
                            out.append((d, "jump"))
        # up and down
        for dy in (1, -1):
            d = (x, y + dy, z)
            ok = self.body_ok(d)
            if ok is None:
                continue
            if ok == "crawl" and not sub:
                self.refused.add((n, d))
                continue
            if dy < 0 and (in_bubble or d in self.bubble):
                continue                        # a bubble column will not let you down
            cur_climb = w.cls(n) in CLIMB
            if w.water(n) and w.water(d):
                out.append((d, "swim"))
            elif cur_climb and dy == 1 and w.cls(d) in CLIMB:
                out.append((d, "climb"))
            elif cur_climb and dy == -1 and w.cls(d) in CLIMB:
                out.append((d, "climb"))
            elif dy == -1 and cur_climb and not w.water(d):
                # let go of the rungs over open air: a fall
                if self.stable(d):
                    out.append((d, "walk"))
                else:
                    r = self.fall(n, d)
                    if r:
                        land, dmg, kind, depth = r
                        if dmg >= LETHAL_DAMAGE:
                            self.fatal.add((n, land, dmg))
                        else:
                            if dmg > MAX_FALL_DAMAGE:
                                self.harsh[(n, land)] = dmg
                            self.lands[(n, land)] = (kind, depth, n[1] - land[1])
                            out.append((land, "fall"))
            elif dy == 1 and w.water(d) and not w.water(n) and w.cls(n) in CLIMB:
                out.append((d, "swim"))
            elif dy == 1 and w.water(n) and here == "stand" and not w.water(d):
                pass                            # you cannot swim up out of water into air; you jump onto a ledge
            elif dy == -1 and w.water(d) and not w.water(n) and self.stable(n):
                # standing on a ledge you cannot step down into water below your feet except by a horizontal move
                pass
        return out

    def graph(self, start):
        adj = {}
        q = deque([start])
        adj[start] = None
        while q:
            n = q.popleft()
            es = self.edges(n)
            adj[n] = es
            for d, _ in es:
                if d not in adj:
                    adj[d] = None
                    q.append(d)
        return adj


# ------------------------------------------------------------------------------------------------ the checks
def load_texts(funcs_dir):
    d = Path(funcs_dir)
    texts = {}
    for n in GYM_NUMBERS:
        f = d / ("gym%d.mcfunction" % n)
        texts[n] = f.read_text(encoding="utf-8") if f.is_file() else None
    hp = d / "healers.mcfunction"
    return texts, (hp.read_text(encoding="utf-8") if hp.is_file() else "")


# Every problem carries a short code so a test can ask for one property of one gym. The table is the whole mapping.
CODES = (
    ("write(s) outside the lot", "lot"),
    ("into the shell in", "shell_column"), ("the column into the shell", "shell_column"), ("the shell column", "shell_column"),
    ("stand above the ground", "above_ground"),
    ("blocks of cover", "cover"), ("touch sky", "breach"), ("touch shell", "breach"),
    ("is positioned inside the gym's lot", "town"), ("overlaps the gym's lot", "town"), ("runs over the dig", "town"),
    ("spawn-free zone", "spawn"),
    ("that gym", "gym_cells"), ("lot meets", "lot_lot"), ("inside the dig", "data_claim"),
    ("is not a place a player can stand", "shaft_top"), ("cannot be regained", "trap"), ("that would kill", "fatal"), ("uncushioned fall", "harsh"),
    ("design waypoint(s)", "waypoint"), ("the design's step from", "step"), ("are joined", "room_join"),
    ("can be skipped", "skip_room"), ("can be walked round", "guard"),
    ("one-block-high", "crawl"), ("lands in water", "landing"), ("water source(s)", "leak"), ("ladder cell(s)", "ladder"), ("lantern(s)", "lantern"),
    ("leaf block(s)", "leaves"), ("a loaded spawn condition names", "palette"),
    ("scaffolding column", "scaffold"), ("no way to air", "drown_trap"), ("under water there and back", "drown"),
    ("healing-machine", "healer"), ("no emitted function", "missing"), ("cannot model", "unmodelled"),
)


class Report:
    def __init__(self):
        self.items = []          # (gym number, code, text)
        self.notes = []

    def add(self, gym, kind, msg):
        code = next((c for frag, c in CODES if frag in msg), "unknown")
        self.items.append((gym, code, "gym%s %s: %s" % (gym, kind, msg)))

    @property
    def problems(self):
        return [t for _, _, t in self.items]

    def codes(self, gym=None):
        return {c for g, c, _ in self.items if gym is None or g == gym}


def box_str(b):
    return "%d,%d,%d..%d,%d,%d" % b


def check_site(rep, site, world, ops):
    n = site.n
    shell = site.shell
    pos_col = None
    # every write inside the lot
    stray = defaultdict(list)
    for (i, kind, b, state, filt) in ops:
        if filt:
            continue
        if not (site.in_lot(b[0], b[2]) and site.in_lot(b[3], b[5])):
            stray["outside the lot rect %s" % (site.lot,)].append(b)
    for why, bs in stray.items():
        rep.add(n, "SITE", "%d write(s) %s, e.g. %s" % (len(bs), why, box_str(bs[0])))
    # writes into the shell: one column only
    cols = defaultdict(list)
    above = []
    for c, st in world.cells.items():
        x, y, z = c
        if site.in_shell(x, y, z):
            cols[(x, z)].append((y, st))
        elif site.in_lot(x, z) and y > site.surface(x, z) and not site.in_shell_footprint(x, z):
            above.append(c)
    if len(cols) != 1:
        rep.add(n, "SITE", "writes reach into the shell in %d columns %s; the works may open the hall in exactly one"
                % (len(cols), sorted(cols)[:4]))
    else:
        (col, cells), = cols.items()
        pos_col = col
        if site.healer and (col[0], col[1]) != (site.healer[0], site.healer[2]):
            rep.add(n, "SITE", "the column into the shell at %s is not where the healing machine stood, %s: the one hall cell known to be free floor"
                    % (col, (site.healer[0], site.healer[2])))
        ys = sorted(y for y, _ in cells)
        if ys[-1] != site.hall_stand:
            rep.add(n, "SITE", "the column into the shell at %s ends at y%d, but the hall floor's standing level is y%d"
                    % (col, ys[-1], site.hall_stand))
        if ys != list(range(ys[0], ys[-1] + 1)):
            rep.add(n, "SITE", "the column into the shell at %s has gaps: y%s" % (col, ys))
        bad = sorted({block_name(st) for _, st in cells} - {"minecraft:air", "minecraft:scaffolding"})
        if bad:
            rep.add(n, "SITE", "the shell column %s holds %s, not just air and scaffolding" % (col, bad))
    if above:
        rep.add(n, "SITE", "%d written cell(s) stand above the ground outside the shell, e.g. %s" % (len(above), above[0]))
    # cover
    thin = []
    for c, st in world.cells.items():
        if cls_of(st) not in ("air", "water", "ladder", "scaf", "pass"):
            continue
        x, y, z = c
        if pos_col and (x, z) == pos_col:
            continue
        if site.in_shell(x, y, z):
            continue
        cover = site.surface(x, z) - y
        if site.in_shell_footprint(x, z):
            cover = min(cover, site.hall_floor_top - y)
        if cover < MIN_COVER and world.cls(c) != "solid":
            thin.append((cover, c))
    if thin:
        thin.sort()
        rep.add(n, "SITE", "%d open cell(s) with under %d blocks of cover, thinnest %d at %s" % (len(thin), MIN_COVER, thin[0][0], thin[0][1]))
    # breach: an open written cell touching sky or the shell's inside
    breach = []
    for c in world.cells:
        if not world.is_open(c) or world.cls(c) == "sky":
            continue
        x, y, z = c
        if pos_col and (x, z) == pos_col:
            continue
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            nb = (x + d[0], y + d[1], z + d[2])
            if nb in world.cells:
                continue
            nat = world.natural(nb)
            if nat in ("sky", "shell"):
                breach.append((c, nat))
                break
    if breach:
        rep.add(n, "SITE", "%d open cell(s) touch %s, e.g. %s" % (len(breach), breach[0][1], breach[0][0]))
    # the town
    x0, z0, x1, z1 = site.lot
    for r in site.others:
        p = r.get("position") or {}
        if "x" in p and x0 <= p["x"] <= x1 and z0 <= p["z"] <= z1:
            rep.add(n, "SITE", "placement %s (%s) is positioned inside the gym's lot" % (r.get("id"), r.get("kind")))
    for a in site.plan["anchors"]:
        if a["role"] in ("gym", "waterfront_gym"):
            continue
        ax0, az0, ax1, az1 = a["rect"]
        if not (ax1 < x0 or ax0 > x1 or az1 < z0 or az0 > z1):
            rep.add(n, "SITE", "anchor %s overlaps the gym's lot" % a["id"])
    xs = [c[0] for c in world.cells]
    zs = [c[2] for c in world.cells]
    dx0, dx1, dz0, dz1 = min(xs), max(xs), min(zs), max(zs)
    for s in site.plan["streets"]:
        pl, w = s["polyline"], s["width"] / 2.0
        for (ax, az), (bx, bz) in zip(pl, pl[1:]):
            lo_x, hi_x, lo_z, hi_z = min(ax, bx) - w, max(ax, bx) + w, min(az, bz) - w, max(az, bz) + w
            if not (hi_x < dx0 or lo_x > dx1 or hi_z < dz0 or lo_z > dz1):
                # the segment's bounding box meets the lot; refine by sampling the segment
                steps = max(abs(bx - ax), abs(bz - az), 1)
                for k in range(steps + 1):
                    px, pz = ax + (bx - ax) * k / steps, az + (bz - az) * k / steps
                    if dx0 - w <= px <= dx1 + w and dz0 - w <= pz <= dz1 + w:
                        rep.add(n, "SITE", "street %s runs over the dig at about (%d,%d)" % (s["id"], px, pz))
                        break
                else:
                    continue
                break
    # the palette: no block that a loaded spawn condition names (data/spawn_blocks.json), water aside, which the spawn-free zone covers
    root0 = Path(__file__).resolve().parent.parent
    named = json.loads((root0 / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]
    bad_blocks = sorted({block_name(st) for st in world.cells.values()} & set(named) - {"minecraft:water"})
    if bad_blocks:
        rep.add(n, "SITE", "the works use %s, which a loaded spawn condition names (data/spawn_blocks.json): it would change what spawns" % bad_blocks)
    # no wild spawns in the works: the spawn-free zone of data/spawn_suppression.json holds the whole dig
    root = Path(__file__).resolve().parent.parent
    zones = json.loads((root / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))["spawn_free_zones"]
    cx, cz = (shell[0] + shell[3]) // 2, (shell[2] + shell[5]) // 2
    mine = [z for z in zones if z["box"][0] <= cx <= z["box"][2] and z["box"][1] <= cz <= z["box"][3]]
    if len(mine) != 1:
        rep.add(n, "SPAWN", "%d spawn-free zone(s) hold the shell's centre; expected one" % len(mine))
    else:
        zb = mine[0]["box"]
        if dx0 < zb[0] or dx1 > zb[2] or dz0 < zb[1] or dz1 > zb[3]:
            rep.add(n, "SPAWN", "the dig x%d..%d z%d..%d is not inside its spawn-free zone %s (%s)" % (dx0, dx1, dz0, dz1, zb, mine[0]["id"]))
    return pos_col


def check_overlap(rep, sites, worlds, root):
    # cell level, gym against gym
    seen = {}
    for n, w in worlds.items():
        for c in w.cells:
            if c in seen and seen[c] != n:
                rep.add(n, "OVERLAP", "writes cell %s that gym%d also writes" % (c, seen[c]))
                break
            seen[c] = n
    # the lot rects and shells of different gyms do not meet
    ns = sorted(sites)
    for i, a in enumerate(ns):
        for b in ns[i + 1:]:
            la, lb = sites[a].lot, sites[b].lot
            if not (la[2] < lb[0] or la[0] > lb[2] or la[3] < lb[1] or la[1] > lb[3]):
                rep.add(a, "OVERLAP", "lot meets gym%d's lot" % b)
    # other content that names these columns
    data = root / "data"
    boxes = {}
    for n, w in worlds.items():
        xs = [c[0] for c in w.cells]
        zs = [c[2] for c in w.cells]
        ys = [c[1] for c in w.cells]
        boxes[n] = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))
    for f in sorted(data.glob("*.json")):
        if f.name == "gym_interiors.json":
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for gid, path, what in scan_claims(doc, boxes):
            if f.name == "placements.json" and "/anchors[" in path:
                continue                        # the lots themselves
            if f.name == "spawn_suppression.json":
                continue                        # the spawn-free zones are meant to cover the digs
            if "site_history" in path:
                continue                        # a record of where a site was looked at, not a build
            if f.name == "placements.json" and path.startswith("/placements[") and gid in worlds and \
                    ("gym%d_" % gid) in json.dumps(doc["placements"][int(path.split("[")[1].split("]")[0])])[:120]:
                continue                        # the gym's own placement
            rep.add(gid, "OVERLAP", "%s%s names %s, inside the dig" % (f.name, path[:60], what))


def scan_claims(doc, boxes):
    """(gym, json path, coordinates) for every point or rect in doc that falls in a gym's written extent."""
    out = []

    def hit(kind, a):
        res = []
        for n, b in boxes.items():
            if kind in ("pt3",):
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
            if nums and len(o) in (4, 6) and any(abs(o[i + 2 if len(o) == 4 else i + 3] - o[i]) > 600 for i in ((0, 1) if len(o) == 4 else (0, 2))):
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


def check_routes(rep, site, world, design_route, pos_col, trainers=(), doors=()):
    n = site.n
    if pos_col is None:
        return None
    start = (pos_col[0], site.hall_stand, pos_col[1])
    mv = Moves(world)
    if mv.body_ok(start) is None or not mv.stable(start):
        rep.add(n, "ROUTE", "the shaft top %s is not a place a player can stand (cell %s)" % (start, world.state(start)))
        return None
    adj = mv.graph(start)
    # every reachable node gets home
    rev = defaultdict(list)
    for a, es in adj.items():
        for d, _ in es:
            rev[d].append(a)
    home = {start}
    q = deque([start])
    while q:
        c = q.popleft()
        for p in rev[c]:
            if p not in home:
                home.add(p)
                q.append(p)
    trapped = [c for c in adj if c not in home]
    if trapped:
        trapped.sort()
        rep.add(n, "ROUTE", "%d reachable position(s) from which the shaft cannot be regained (a trap), e.g. %s (%s); lowest %s"
                % (len(trapped), trapped[0], describe(world, trapped[0]), min(trapped, key=lambda c: c[1])))
    if mv.fatal:
        f = sorted(mv.fatal)[0]
        rep.add(n, "ROUTE", "%d fall(s) that would kill, e.g. %s -> %s for %.0f damage" % (len(mv.fatal), f[0], f[1], f[2]))
    if mv.harsh:
        (a, b), dmg = sorted(mv.harsh.items())[0]
        rep.add(n, "ROUTE", "%d uncushioned fall(s) over %d damage, e.g. %s -> %s for %.0f" % (len(mv.harsh), MAX_FALL_DAMAGE, a, b, dmg))
    for (a, b), (kind, depth, dist) in sorted(mv.lands.items()):
        if kind == "water" and depth < MIN_LANDING_WATER and dist >= 4:
            rep.add(n, "WATER", "a %d-block fall from %s lands in water %d deep at %s (needs %d)" % (dist, a, depth, b, MIN_LANDING_WATER))
    # design waypoints
    dead = []
    for wp in design_route:
        c = tuple(wp["at"])
        ok = mv.body_ok(c)
        near = [a for a in [(c[0], c[1] + d, c[2]) for d in (-1, 1)] if mv.body_ok(a) and mv.stable(a) and a in adj]
        if ok is None or not mv.stable(c):
            if not near:
                dead.append((wp, "is not a legal standing or swimming position in the emitted blocks (cell holds %s)"
                             % (world.state(c) or world.natural(c))))
        elif c not in adj and not near:
            dead.append((wp, "cannot be reached from the shaft top"))
    if dead:
        wp, why = dead[0]
        rep.add(n, "ROUTE", "%d design waypoint(s) cannot be reached from the shaft top; the first is %s (%s: %s), which %s"
                % (len(dead), tuple(wp["at"]), wp.get("room"), wp.get("what", "")[:40], why))
    # a one-high flooded passage is only entered swimming, and swimming starts with the head under water
    marks = [tuple(wp["at"]) for wp, _ in dead]
    seen_mouth = set()
    for src, dst in sorted(mv.refused):
        if src in adj and any(max(abs(dst[0] - m[0]), abs(dst[1] - m[1]), abs(dst[2] - m[2])) <= 2 for m in marks):
            key = (dst[0], dst[2])
            if key in seen_mouth:
                continue
            seen_mouth.add(key)
            below = sum(1 for k in range(0, 6) if world.water((src[0], src[1] + k, src[2])))
            rep.add(n, "ROUTE", "a one-block-high flooded passage at %s (%s) can only be entered swimming, but the cell in front of it, %s, holds %d block(s) of water "
                    "over the player's feet: the head is never under, so a player walking up to it is stopped by its roof"
                    % (dst, world.state((dst[0], dst[1] + 1, dst[2])) or "rock", src, below))
    # the design's own steps, walked: each waypoint must lead to the next in the movement graph
    def node_of(wp):
        c = tuple(wp["at"])
        for cand in (c, (c[0], c[1] - 1, c[2]), (c[0], c[1] + 1, c[2])):
            if cand in adj:
                return cand
        return None

    def dist(a, b):
        seen, q = {a: 0}, deque([a])
        while q:
            c = q.popleft()
            if c == b:
                return seen[c]
            for d, _ in adj.get(c) or []:
                if d not in seen:
                    seen[d] = seen[c] + 1
                    q.append(d)
        return None

    nodes = [(wp, node_of(wp)) for wp in design_route]
    for (w0, a), (w1, b) in zip(nodes, nodes[1:]):
        if a is None or b is None:
            continue                # already reported as not a legal or reachable position
        l1 = abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
        d = dist(a, b)
        if d is None or d > 2 * l1 + 6:
            rep.add(n, "ROUTE", "the design's step from %s (%s: %s) to %s (%s: %s) is %s in the emitted blocks (%d apart as the crow flies)"
                    % (tuple(w0["at"]), w0.get("room"), w0.get("what", "")[:34], tuple(w1["at"]), w1.get("room"), w1.get("what", "")[:34],
                       "impossible" if d is None else "%d moves" % d, l1))
    def bfs(a, blocked=frozenset()):
        seen, q = {a: 0}, deque([a])
        while q:
            c = q.popleft()
            for d, _ in adj.get(c) or []:
                if d not in seen and d not in blocked:
                    seen[d] = seen[c] + 1
                    q.append(d)
        return seen

    # a guard that can be walked round: the waypoint after a trainer's seat, reached without ever coming within his sight
    for t in trainers:
        seat = tuple(t["seat"])
        reach_r = float(t["sight_distance"])
        idx = None
        for i, (wp, a) in enumerate(nodes):
            if a is not None and max(abs(a[0] - seat[0]), abs(a[1] - seat[1]), abs(a[2] - seat[2])) <= 3:
                idx = i
                break
        if idx is None:
            continue
        rep.notes.append("gym%d guard %s: %d positions within sight of his seat" % (n, t["id"], sum(1 for c in adj if (c[0] - seat[0]) ** 2 + (c[1] - seat[1]) ** 2 + (c[2] - seat[2]) ** 2 <= reach_r ** 2)))
        blocked = frozenset(c for c in adj if (c[0] - seat[0]) ** 2 + (c[1] - seat[1]) ** 2 + (c[2] - seat[2]) ** 2 <= reach_r ** 2)
        for j in range(idx + 1, len(nodes)):
            tgt = nodes[j][1]
            if tgt is None or tgt in blocked:
                continue
            if start not in blocked and tgt in bfs(start, blocked):
                rep.add(n, "ROUTE", "guard %s at %s (sight %.1f) can be walked round: %s (%s) is reachable without coming within his sight"
                        % (t["id"], seat, reach_r, tuple(nodes[j][0]["at"]), nodes[j][0].get("room")))
            break
    n_out = len(outbound({'route': design_route, 'doors': doors}))
    return mv, adj, start, nodes[:n_out]


def describe(world, c):
    return "%s over %s" % (world.state(c) or world.natural(c), world.state((c[0], c[1] - 1, c[2])) or world.natural((c[0], c[1] - 1, c[2])))


def room_of(rooms, c):
    """The smallest room box that holds cell c."""
    best = None
    for rid, b in rooms:
        if b[0] <= c[0] <= b[3] and b[1] <= c[1] <= b[4] and b[2] <= c[2] <= b[5]:
            vol = (b[3] - b[0] + 1) * (b[4] - b[1] + 1) * (b[5] - b[2] + 1)
            if best is None or vol < best[0]:
                best = (vol, rid)
    return best[1] if best else None


def path_cells(a, d, how):
    """The cells a move passes through, ends included. A jump crosses the gap at the take-off's height."""
    if how != "jump":
        return [a, d]
    k = max(abs(d[0] - a[0]), abs(d[2] - a[2]))
    sx, sz = (d[0] > a[0]) - (d[0] < a[0]), (d[2] > a[2]) - (d[2] < a[2])
    return [(a[0] + sx * i, a[1], a[2] + sz * i) for i in range(k)] + [d]


def outbound(design):
    """The design's waypoints up to (not including) the first that stands in a one-way door: the way in."""
    oneway = {d["id"] for d in design.get("doors", []) if "one way" in (d.get("why") or "")}
    out = []
    for wp in design["route"]:
        if wp.get("room") in oneway:
            break
        out.append(wp)
    return out


def check_shortcuts(rep, site, world, adj, design, start, nodes_out):
    """Rooms the movement graph joins that the design's route never joins, and outbound rooms that can be skipped."""
    n = site.n
    rooms = [(r["id"], tuple(r["box"])) for r in design["rooms"]]
    seq = []
    for wp in design["route"]:
        r = wp.get("room")
        if r and (not seq or seq[-1] != r):
            seq.append(r)
    allowed = {frozenset((a, b)) for a, b in zip(seq, seq[1:])}
    found = defaultdict(list)
    label = {c: room_of(rooms, c) for c in adj}
    for a, es in adj.items():
        ra0 = label[a]
        if ra0 is None:
            continue
        # follow the moves out of a through positions that belong to no room (a hole cut between two rooms) to the next room
        seen = {a}
        stack = [(a, None)]
        while stack:
            c, first = stack.pop()
            for d, how in adj.get(c) or []:
                cells = [room_of(rooms, x) for x in path_cells(c, d, how)]
                labels = [x for i, x in enumerate(cells) if x and (i == 0 or x != cells[i - 1])]
                pairs = [(x, y) for x, y in zip(labels, labels[1:]) if x != y]
                if c != a:
                    pairs = [(ra0, y) for y in labels if y != ra0]
                for x, y in pairs:
                    if frozenset((x, y)) not in allowed:
                        found[frozenset((x, y))].append((a, d, how))
                if label[d] is None and d not in seen:
                    seen.add(d)
                    stack.append((d, first or (a, d, how)))
    for pair, ex in sorted(found.items(), key=lambda kv: sorted(kv[0])):
        a, d, how = ex[0]
        rep.add(n, "ROUTE", "rooms %s are joined (%d moves, e.g. %s -> %s by %s) but the design's route never joins them: a shortcut"
                % (" and ".join(sorted(pair)), len(ex), a, d, how))
    # an outbound room that is not on every way to the far end can be skipped
    far, far_i = None, None
    for i in range(len(nodes_out) - 1, -1, -1):
        wp, c = nodes_out[i]
        if c is not None and c in adj:
            far, far_i = (wp, c), i
            break
    if far is None:
        return
    far_room = room_of(rooms, far[1])
    start_room = room_of(rooms, start)
    todo = []
    for wp, c in nodes_out[:far_i + 1]:
        r = wp.get("room")
        if r and r not in todo and r not in (far_room, start_room):
            todo.append(r)
    for r in todo:
        seen, q = {start}, deque([start])
        while q:
            c = q.popleft()
            for d, how in adj.get(c) or []:
                if d in seen or any(room_of(rooms, x) == r for x in path_cells(c, d, how)):
                    continue
                seen.add(d)
                q.append(d)
        if far[1] in seen:
            rep.add(n, "ROUTE", "outbound room %s can be skipped: %s (%s) is reachable from the shaft top without ever entering it"
                    % (r, tuple(far[0]["at"]), far[0].get("room")))


def flow_extent(world, sources):
    """Air cells that flowing water from the sources reaches: 7 blocks along a floor, down any drop, never into a
    ladder, a block or a lantern. An upper bound (the game routes toward the nearest drop first)."""
    src = set(sources)
    best = {c: 0 for c in src}
    q = deque((c, 0) for c in src)
    free = ("air", "sky")
    while q:
        c, lvl = q.popleft()
        x, y, z = c
        below = (x, y - 1, z)
        if world.cls(below) in free:
            if below not in best or (best[below] > 0 and below not in src):
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


def check_water(rep, site, world, adj):
    n = site.n
    # 1. sealed sources
    leaks = []
    for c, st in world.cells.items():
        if world.cls(c) != "water" or block_name(st) != "minecraft:water":
            continue
        x, y, z = c
        for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)):
            nb = (x + d[0], y + d[1], z + d[2])
            nc = world.cls(nb)
            if nc in ("air", "sky"):
                leaks.append((c, nb))
                break
    if leaks:
        leaks.sort()
        ys = sorted({c[1] for c, _ in leaks})
        wet = flow_extent(world, [c for c, _ in leaks])
        walk = sum(1 for c in wet if adj is not None and c in adj)
        rep.add(n, "WATER", "%d water source(s) with air beside or under them, which will flow out of their box, e.g. %s into %s (y%s); "
                "the flow wets about %d air cells, %d of them on the walked route"
                % (len(leaks), leaks[0][0], leaks[0][1], ys[0] if len(ys) == 1 else "%d..%d" % (ys[0], ys[-1]), len(wet), walk))
    # 2. ladders need a wall; scaffolding needs a floor
    bad = []
    for c, st in world.cells.items():
        nm = block_name(st)
        if nm == "minecraft:ladder":
            f = props(st).get("facing")
            dx, dz = FACING[f]
            back = (c[0] - dx, c[1], c[2] - dz)
            if not world.supports(back):
                bad.append((c, back, world.state(back) or world.natural(back)))
    if bad:
        bad.sort()
        rep.add(n, "BLOCKS", "%d ladder cell(s) with nothing solid behind them, e.g. %s (behind: %s at %s); the ladder will not survive"
                % (len(bad), bad[0][0], bad[0][2], bad[0][1]))
    hung = []
    for c, st in world.cells.items():
        if block_name(st) in ("minecraft:lantern", "minecraft:soul_lantern"):
            up = props(st).get("hanging") == "true"
            hold = (c[0], c[1] + (1 if up else -1), c[2])
            if not world.supports(hold):
                hung.append((c, "above" if up else "below", world.state(hold) or world.natural(hold)))
    if hung:
        hung.sort()
        rep.add(n, "BLOCKS", "%d lantern(s) with nothing to hang from or stand on, e.g. %s (%s it: %s); they drop as items on the first block update"
                % (len(hung), hung[0][0], hung[0][1], hung[0][2]))
    leaves = sorted(c for c, st in world.cells.items() if block_name(st).endswith("_leaves") and props(st).get("persistent") != "true")
    if leaves:
        rep.add(n, "BLOCKS", "%d leaf block(s) without persistent=true, e.g. %s %s: with no log within six blocks they decay and vanish, wall and all"
                % (len(leaves), leaves[0], world.state(leaves[0])))
    foot = []
    for c, st in world.cells.items():
        if block_name(st) == "minecraft:scaffolding":
            below = (c[0], c[1] - 1, c[2])
            if world.cls(below) != "scaf" and not world.supports(below):
                # a horizontal scaffolding neighbour also holds it (stability distance)
                if not any(world.cls((c[0] + dx, c[1], c[2] + dz)) == "scaf" for dx, dz in DIRS):
                    foot.append(c)
    if foot:
        foot.sort()
        rep.add(n, "BLOCKS", "%d scaffolding column foot(feet) over nothing, e.g. %s over %s; it will fall" % (len(foot), foot[0], world.state((foot[0][0], foot[0][1] - 1, foot[0][2])) or "air"))
    # 3. drowning: every submerged position reaches air, and the round trip from air stays inside one breath
    if adj is None:
        return
    mv = Moves(world)
    sub = {c for c in adj if world.water((c[0], c[1] + 1, c[2])) and world.water(c) or mv.body_ok(c) == "crawl"}
    rev = defaultdict(list)
    fwd = defaultdict(list)
    for a, es in adj.items():
        for d, _ in es:
            rev[d].append(a)
            fwd[a].append(d)
    to_air = {}
    q = deque()
    for c in adj:
        if c not in sub:
            to_air[c] = 0
            q.append(c)
    while q:
        c = q.popleft()
        for p in rev[c]:
            if p in sub and p not in to_air:
                to_air[p] = to_air[c] + 1
                q.append(p)
    stuck = [c for c in sub if c not in to_air]
    if stuck:
        stuck.sort()
        rep.add(n, "WATER", "%d submerged position(s) with no way to air, e.g. %s (a drowning trap)" % (len(stuck), stuck[0]))
    from_air = {}
    q = deque()
    for c in adj:
        if c not in sub:
            from_air[c] = 0
            q.append(c)
    while q:
        c = q.popleft()
        for d in fwd[c]:
            if d in sub and d not in from_air:
                from_air[d] = from_air[c] + 1
                q.append(d)
    worst = None
    for c in sub:
        if c in to_air and c in from_air:
            t = to_air[c] + from_air[c]
            if worst is None or t > worst[0]:
                worst = (t, c)
    if worst:
        rep.notes.append("gym%d longest head-under-water trip there and back: %d blocks (limit %d), at %s" % (n, worst[0], MAX_SUBMERGED_ROUNDTRIP, worst[1]))
    if worst and worst[0] > MAX_SUBMERGED_ROUNDTRIP:
        rep.add(n, "WATER", "a player can be %d blocks under water there and back from %s, over the %d one breath allows"
                % (worst[0], worst[1], MAX_SUBMERGED_ROUNDTRIP))
    # 4. a crawl hole entered from a dry or shallow mouth
    for a, es in adj.items():
        for d, how in es:
            pass


def check_healers(rep, placements, healers_text):
    """The healer removal must cover each of the eight placed shells, worked out here from placements.json."""
    recs = [r for r in placements["placements"] if isinstance(r, dict) and r.get("pack_template") and r.get("kind") in ("gym", "donor")
            and re.match(r"gym[1-8]_", r.get("id", ""))]
    ops, _ = parse(healers_text, "healers")
    fills = [o for o in ops if o[4] == "cobblemon:healing_machine"]
    for r in recs:
        n = int(r["id"][3])
        box = shell_box(r)
        vol = (box[3] - box[0] + 1) * (box[4] - box[1] + 1) * (box[5] - box[2] + 1)
        mine = [f[2] for f in fills if f[2][0] >= box[0] and f[2][3] <= box[3] and f[2][2] >= box[2] and f[2][5] <= box[5]
                and f[2][1] >= box[1] and f[2][4] <= box[4]]
        got = sum((b[3] - b[0] + 1) * (b[4] - b[1] + 1) * (b[5] - b[2] + 1) for b in mine)
        if got != vol:
            rep.add(n, "HEALER", "the healing-machine removal covers %d of the %d cells of the shell %s" % (got, vol, box_str(box)))
    stray = [f for f in fills if not any(f[2][0] >= shell_box(r)[0] and f[2][3] <= shell_box(r)[3] and f[2][2] >= shell_box(r)[2]
                                         and f[2][5] <= shell_box(r)[5] and f[2][1] >= shell_box(r)[1] and f[2][4] <= shell_box(r)[4] for r in recs)]
    if stray:
        rep.add("s", "HEALER", "%d healing-machine fill(s) outside every placed shell, e.g. %s" % (len(stray), box_str(stray[0][2])))


def run(texts, healers_text, design, placements, ground, root=ROOT, only=None):
    rep = Report()
    if healers_text and not only:
        check_healers(rep, placements, healers_text)
    sites, worlds, allops, extras = {}, {}, {}, {}
    gyms = {int(g["id"][3:]): g for g in design["gyms"] if g.get("built")}
    for n in GYM_NUMBERS:
        if only and n not in only:
            continue
        if texts.get(n) is None:
            rep.add(n, "SITE", "no emitted function gym%d.mcfunction" % n)
            continue
        ops, unknown = parse(texts[n], "gym%d" % n)
        for u in unknown:
            rep.add(n, "SITE", "a command this audit cannot model: %s" % u)
        site = Site(n, placements, ground, design.get("measured"))
        sites[n], allops[n] = site, ops
        worlds[n] = World(site, ops)
    for n in sorted(sites):
        col = check_site(rep, sites[n], worlds[n], allops[n])
        worlds[n].hall_col = col
        res = check_routes(rep, sites[n], worlds[n], gyms[n]["route"], col, gyms[n]["trainers"], gyms[n].get("doors", [])) if n in gyms else None
        if res:
            mv, adj, start, nodes_out = res
            check_shortcuts(rep, sites[n], worlds[n], adj, gyms[n], start, nodes_out)
            check_water(rep, sites[n], worlds[n], adj)
            extras[n] = (mv, adj, start)
        else:
            check_water(rep, sites[n], worlds[n], None)
    check_overlap(rep, sites, worlds, root)
    return rep, sites, worlds, extras


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--functions", default=str(DEFAULT_FUNCS))
    ap.add_argument("--source-root", default=None)
    ap.add_argument("--verbose", action="store_true", help="also print the measurements behind the checks")
    a = ap.parse_args(argv)
    import ground as G
    texts, healers = load_texts(a.functions)
    if all(v is None for v in texts.values()):
        print("no emitted functions in %s: run python tools/gym_interiors.py build first" % a.functions)
        return 2
    design = json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    rep, sites, worlds, _ = run(texts, healers, design, placements, G.load(a.source_root))
    if a.verbose:
        for note in rep.notes:
            print("  note:", note)
    if rep.problems:
        for p in rep.problems:
            print(p)
        print("gym interiors (independent): %d problem(s) over %d interior(s)" % (len(rep.problems), len(sites)))
        return 1
    print("gym interiors (independent): clean over %d interior(s)" % len(sites))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
