#!/usr/bin/env python
"""The jungle's lost temples' offline audit: the BUILT pack (build/datapacks/cobblers_jungle_temples), the R9JT steps and
the tools/reapply.py wiring, against data/jungle_temples.json, every other data file, the canonical heightmap, the
painted water and the Cobblemon 1.8 jar.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/jungle_temples.py,
tools/southern_residents.py, tools/northern_residents.py or tools/resident_encounters.py, nor any audit built on them.
It replays the emitted .mcfunction text with its own parser, takes ground from tools/ground.py (round(h)) and water
from tools/water_mask.py plus data/rivers.json, and derives every expectation with its own code: the floors, the cache
spots, the keep-clear list, the authored x/z, the bearing to Sunset West. The only things taken from the generator are
its OUTPUTS: the pack, and the steps it hands tools/reapply.py (read in a subprocess, never imported here).
tests/test_jungle_temples_audit.py mutates the GENERATOR's code and leaves the data alone.

  pack      only pack.mcmeta and one build function per temple: no load or tick tag, so nothing acts uncalled; every
            command a plain fill or setblock (a conditional fill only ever clears to air); tools/function_limits.py
  ys        each structure's floor is max(round(ground)) over its footprint, relief <= rules.max_foundation; the record's
            "yN at the centre" is the heightmap's; each cache's spot (its `at` and `feet_dy` on that floor) is
            data/rewards.json's container + 1 and inside its trigger, and the container block is written there
  writes    every written and cleared column inside the record's bbox; every block in blocks.ids; no block of
            data/spawn_blocks.json (unless data/spawn_block_policy.json whitelists it for the jungle), no chest, no bed,
            nothing that gives light; nothing on a column whose round(ground) is at or below the sea or that is wet;
            nothing at or under the ground outside a structure footprint; nothing under the ground at all except the
            Ring Court's undercroft (x -4..4, z -4..4, floor-5..floor); a footprint column's lowest block rests on the
            ground; outside a footprint, only leaves and vines may hang free
  hold      every vine face, ladder, wall sign and carpet is backed by a full block in the replayed world
  reach     a walker of this file's own (two blocks tall, one-block jumps, safe drops of three, ladders and vines
            climbable, a trapdoor openable, carpet breakable) gets from outside each temple to its cache spot and back;
            the Ring Court's cache is NOT reachable with the trapdoor shut nor without climbing (the eye is the only
            way, down a ladder of five on the pillar's south face under the ring's centre); the Green Stair's summit is
            NOT reachable without climbing (its top stair fell) and is with the vines
  siting    every written, cleared and cache column inside data/regions.json long_isle_south; at least
            rules.authored_clearance from every x/z another data file authors (our three cache rewards excepted by id)
            and from every data/routes.json min/max box as a filled rectangle; outside every town footprint + clearance
            and every Rift zone box; at least rules.keep_clear.blocks from every entry of a keep-clear list THIS file
            derives (every elder, named resident, donor placement footprint, portal, ferry dock or stop within
            KEEP_CLEAR_RADIUS of a temple, and every ferry dock or stop in FERRY_BOX), and that list is a subset of the
            record's; the centre's cell is the record's
  mark      the Harbour Mark's arm (the slabs off its column) points within 45 degrees of Sunset West's centre and its
            harbour dock (data/towns.json, data/ferries.json sunset_quay); the HARBOUR sign faces along the arm; the
            distance the story_rule states is the measured one
  caches    each a data/rewards.json cache with non-empty contents, every item in the jar; within the economy curve
            derived from every OTHER cache in data/rewards.json at its tier (data/encounter_design.json, by the
            sub-region its container stands in): no more stacks, items or evolution stones than any cache of that tier
            or lower gives; the record's band inside that tier's band
  steps     per temple a forceload of a box holding every write, its build, and the release; nothing else
  wiring    tools/reapply.py: the prepare jobs jungle_temples after far_south and jungle_temples_audit after
            jungle_temples; R9JT appended once, jungle_temples.placement_steps(), after R9FS and before R9E; the pack in
            SERVER_PACKS and not in WORLD_LOCAL
  ruins     the six superseded jungle ruins are out of data/placements.json placements, in superseded_placements, and
            named by no tool's code (docstrings and comments excepted, reported) and by no built pack present

NOT checked, and it needs a running server: that the blocks land and stay (a vine or carpet a later update pops); that
a player can see and break the moss carpet over the trapdoor and open it (survival assumed; adventure mode would bar
it); that the advancement fires and pays once (the rewards pack is not read here: tools/rewards_pack.py's own checks);
trees, boulders or anything a world already holds outside the clear boxes (the walker takes unwritten air above the
ground as passable); that the signs read.

  python tools/jungle_temples_audit.py [--pack DIR] [--jar JAR] [--source-root R] [-v]
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import re
import subprocess
import sys
import tempfile
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_jungle_temples"
RECORD = "jungle_temples.json"
SCHEMA = "cobblers.jungle-temples/1"
GENERATOR = "jungle_temples"
PACK_FORMAT = 48  # Minecraft 1.21.1
# The design, as this audit reads it from the checklist and each temple's situation (not from the generator):
# the Ring Court's undercroft, the only place anything is built under the ground (local x0, z0, x1, z1, dy0, dy1)
UNDERCROFT = {"ring_court": (-4, -4, 4, 4, -5, 0)}
# which temple's cache is reached only by climbing, and which only through its trapdoor
NEEDS_CLIMB = ("ring_court", "vine_pyramid")
THROUGH_TRAPDOOR = ("ring_court",)
LADDER_RUN = {"ring_court": 5}          # "a ladder down five blocks"
# the climb the design names, which alone must reach the cache: the Ring Court's ladder on the pillar's south face, and
# the Green Stair's vines on the third tier's NORTH face (a vine on a north face hangs on its south side: south=true)
CLIMB_ROUTE = {
    "ring_court": ("by the ladder on the pillar's south face",
                   lambda st: base(st) == "minecraft:ladder" and props(st).get("facing") == "south"),
    "vine_pyramid": ("by the vines on a north face",
                     lambda st: base(st) == "minecraft:vine" and props(st).get("south") == "true"),
}
# The keep-clear derivation: everything of these kinds within this radius of a temple centre (the checklist: "every
# elder ... whose trunk is within 400 of a temple"), and every ferry dock or stop in the checklist's box
KEEP_CLEAR_RADIUS = 400
FERRY_BOX = (6832, 6632, 8167, 8023)
# Step order in tools/reapply.py: (after, before)
STEP_AFTER, STEP_BEFORE = "R9FS", "R9E"
PREPARE_AFTER = "far_south"
RUINS = ("ruin_great_hall", "ruin_west_wall", "ruin_east_court", "ruin_north_gate", "ruin_court_east", "ruin_court_west")
SAFE_DROP = 3
# Blocks that give light (the ruins are "lit by nothing"): any id containing one of these
LIGHT = ("torch", "lantern", "glowstone", "shroomlight", "campfire", "candle", "jack_o_lantern", "lamp", "end_rod",
         "beacon", "froglight", "sea_pickle", "magma_block", "lava", "fire", "glow_lichen", "crying_obsidian")

# Defects this audit found in the committed build, reported to the builder and NOT fixed here (the data is not this
# audit's). Each prints as KNOWN and does not fail the run; a KNOWN that no longer fires is STALE and does fail, so the
# list cannot outlive its defect. (check, text, ruling)
KNOWN = [
    ("mark", "harbour_mark: the story_rule says Sunset West is about 5.8 km away; measured",
     "2026-10-04: data/jungle_temples.json harbour_mark.story_rule says Sunset West's quay is 'about 5.8 km' due west; "
     "from the centre (7560, 7328) to data/towns.json sunset_west's centre (2660, 6490) is 4.97 km and to "
     "data/ferries.json sunset_quay's near point (2630, 6521) 5.00 km. The bearing is right (about 9 degrees north of "
     "west); the distance in the prose is not. Builder: the text"),
]


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, cat, msg):
        self.errors.append("%s: %s" % (cat, msg))

    def note(self, msg):
        self.notes.append(msg)

    def has(self, cat, text=""):
        return any(e.startswith(cat + ":") and text in e for e in self.errors)


def jload(name, data=DATA):
    return json.loads((Path(data) / name).read_text(encoding="utf-8"))


def classify(errors, known=None):
    """(real, known_hits, stale)."""
    known = KNOWN if known is None else known
    real, hits = [], []
    for e in errors:
        (hits if any(e.startswith(c + ":") and t in e for c, t, _w in known) else real).append(e)
    stale = [k for k in known if not any(e.startswith(k[0] + ":") and k[1] in e for e in errors)]
    return real, hits, stale


# ------------------------------------------------------------------ block states


def base(state):
    """'minecraft:vine[north=true]{..}' -> 'minecraft:vine'."""
    return re.split(r"[\[{]", state, 1)[0]


def props(state):
    m = re.match(r"[^\[{]*\[([^\]]*)\]", state)
    if not m:
        return {}
    out = {}
    for kv in m.group(1).split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            out[k.strip()] = v.strip()
    return out


DIRS = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0), "up": (0, 1, 0),
        "down": (0, -1, 0)}
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east", "up": "down", "down": "up"}
TERRAIN = "<terrain>"
AIR = "minecraft:air"


def is_sign(b):
    return b.endswith("_sign")


def passable(b):
    """A block a player's body can be in: air, carpet (breakable, a sixteenth high), vines, ladders, signs and
    trapdoors (openable)."""
    return b in (AIR, "minecraft:cave_air", "minecraft:moss_carpet", "minecraft:vine", "minecraft:ladder") \
        or is_sign(b) or b.endswith("_trapdoor") or b.endswith("_carpet")


def climbable(b):
    return b in ("minecraft:vine", "minecraft:ladder")


def tall(b):
    """A wall or fence: 1.5 high, so nothing stands on it from a one-block jump."""
    return (b.endswith("_wall") and not is_sign(b)) or b.endswith("_fence")


def full(b):
    """A full cube face, the backing a vine, ladder or wall sign needs."""
    if b == TERRAIN:
        return True
    if passable(b) or tall(b):
        return False
    return not any(b.endswith(s) for s in ("_slab", "_stairs", "decorated_pot", "_pane", "_button", "_door"))


# ------------------------------------------------------------------ the replay (this file's own parser)

_COORD = r"(-?\d+)"
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+?(?:\[[^\]]*\])?(?:\{.*\})?)(?: (replace|keep|destroy|hollow|outline)(?: (\S+))?)?$"
                  % ((_COORD,) * 6))
SETBLOCK = re.compile(r"^setblock %s %s %s (\S+?(?:\[[^\]]*\])?(?:\{.*\})?)(?: (replace|keep|destroy))?$" % ((_COORD,) * 3))


class Replay:
    """One build function, replayed in order: `blocks` {(x, y, z): state} for every unconditional write (later wins),
    `clears` [(x0, y0, z0, x1, y1, z1, filter)] for every `fill ... minecraft:air replace <filter>`, and `bad`
    [(line number, text, why)] for anything else."""

    def __init__(self, text):
        self.blocks, self.clears, self.bad, self.order = {}, [], [], []
        for n, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = FILL.match(line)
            if m:
                x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
                st, mode, filt = m.group(7), m.group(8), m.group(9)
                lo = (min(x0, x1), min(y0, y1), min(z0, z1))
                hi = (max(x0, x1), max(y0, y1), max(z0, z1))
                if mode == "replace" and filt:
                    if base(st) != AIR:
                        self.bad.append((n, line, "a conditional fill that places a block, not a clear"))
                    else:
                        self.clears.append(lo + hi + (filt,))
                    continue
                if mode not in (None, "replace"):
                    self.bad.append((n, line, "fill mode %s is not a plain write" % mode))
                    continue
                for x in range(lo[0], hi[0] + 1):
                    for y in range(lo[1], hi[1] + 1):
                        for z in range(lo[2], hi[2] + 1):
                            self.blocks[(x, y, z)] = st
                self.order.append(("fill", lo, hi, st))
                continue
            m = SETBLOCK.match(line)
            if m:
                x, y, z = (int(v) for v in m.groups()[:3])
                if m.group(5) not in (None, "replace"):
                    self.bad.append((n, line, "setblock mode %s is not a plain write" % m.group(5)))
                    continue
                self.blocks[(x, y, z)] = m.group(4)
                self.order.append(("setblock", (x, y, z), (x, y, z), m.group(4)))
                continue
            self.bad.append((n, line, "not a fill or setblock: a build function here only places blocks"))

    def columns(self):
        cols = {(x, z) for x, _y, z in self.blocks}
        for c in self.clears:
            cols |= {(x, z) for x in range(c[0], c[3] + 1) for z in range(c[2], c[5] + 1)}
        return cols

    def cleared(self, x, y, z):
        return any(c[0] <= x <= c[3] and c[1] <= y <= c[4] and c[2] <= z <= c[5] for c in self.clears)


class World:
    """The replayed world: a written block, else the ground's terrain at or under round(ground), else air (cleared,
    or the heightmap's bare air: what a world already holds there is not known offline)."""

    def __init__(self, R, g, blocked=(), no_climb=False, climb_ok=None):
        """`blocked` cells are walls (a trapdoor held shut); `no_climb` makes nothing climbable; `climb_ok(state)`
        limits climbing to the ladders and vines it accepts."""
        self.R, self.g, self.blocked, self.no_climb, self.climb_ok = R, g, set(blocked), no_climb, climb_ok
        self._g = {}

    def ground(self, x, z):
        k = (x, z)
        if k not in self._g:
            self._g[k] = self.g(x, z)
        return self._g[k]

    def at(self, x, y, z):
        st = self.R.blocks.get((x, y, z))
        if st is not None:
            return base(st)
        return TERRAIN if y <= self.ground(x, z) else AIR

    def free(self, x, y, z):
        if (x, y, z) in self.blocked:
            return False
        return passable(self.at(x, y, z))

    def climb(self, x, y, z):
        if self.no_climb or (x, y, z) in self.blocked or not climbable(self.at(x, y, z)):
            return False
        return self.climb_ok is None or self.climb_ok(self.R.blocks.get((x, y, z), ""))

    def floor(self, x, y, z):
        """A block a player can stand on: solid and not tall, or a (shut) trapdoor."""
        b = self.at(x, y, z)
        if b.endswith("_trapdoor"):
            return True
        return not passable(b) and not tall(b)


# ------------------------------------------------------------------ the walker


def node_ok(W, x, y, z):
    return W.free(x, y, z) and W.free(x, y + 1, z) and (
        W.floor(x, y - 1, z) or W.climb(x, y, z) or W.climb(x, y - 1, z))


def neighbours(W, n):
    x, y, z = n
    out = []
    on_climb = W.climb(x, y, z) or W.climb(x, y - 1, z)
    # straight up and down a ladder or vine (or a jump into one that starts a block up)
    if (on_climb or W.climb(x, y + 1, z)) and node_ok(W, x, y + 1, z) and W.free(x, y + 2, z):
        out.append((x, y + 1, z))
    # down a ladder or vine, or through a trapdoor underfoot (opened)
    trap_under = W.at(x, y - 1, z).endswith("_trapdoor") and (x, y - 1, z) not in W.blocked
    if (W.climb(x, y, z) or W.climb(x, y - 1, z) or trap_under) and node_ok(W, x, y - 1, z):
        out.append((x, y - 1, z))
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, nz = x + dx, z + dz
        if node_ok(W, nx, y, nz):
            out.append((nx, y, nz))
            continue
        # a one-block jump (or a step off the top of a ladder): head room over the take-off
        if W.free(x, y + 2, z) and node_ok(W, nx, y + 1, nz):
            out.append((nx, y + 1, nz))
            continue
        # a drop of up to SAFE_DROP, falling past nothing solid
        if W.free(nx, y, nz) and W.free(nx, y + 1, nz):
            for d in range(1, SAFE_DROP + 1):
                if not W.free(nx, y - d, nz):
                    break
                if node_ok(W, nx, y - d, nz):
                    out.append((nx, y - d, nz))
                    break
    return out


def walk(W, starts, box):
    """{node: parent} for every node reached from `starts` inside box (x0, y0, z0, x1, y1, z1)."""
    x0, y0, z0, x1, y1, z1 = box
    seen = {s: None for s in starts if node_ok(W, *s)}
    q = deque(seen)
    while q:
        n = q.popleft()
        for m in neighbours(W, n):
            if m in seen or not (x0 <= m[0] <= x1 and y0 <= m[1] <= y1 and z0 <= m[2] <= z1):
                continue
            seen[m] = n
            q.append(m)
    return seen


def path_to(seen, n):
    out = []
    while n is not None:
        out.append(n)
        n = seen[n]
    return out[::-1]


def outside_starts(W, bbox, pad=2):
    """Standing places on the ring `pad` blocks outside the bbox, on the ground."""
    x0, z0, x1, z1 = bbox
    out = []
    for x in range(x0 - pad, x1 + pad + 1):
        for z in (z0 - pad, z1 + pad):
            out.append((x, W.ground(x, z) + 1, z))
    for z in range(z0 - pad, z1 + pad + 1):
        for x in (x0 - pad, x1 + pad):
            out.append((x, W.ground(x, z) + 1, z))
    return out


def walk_box(W, bbox, R, pad=3):
    ys = [k[1] for k in R.blocks] or [0]
    gs = [W.ground(x, z) for x in (bbox[0], bbox[2]) for z in (bbox[1], bbox[3])]
    return (bbox[0] - pad, min(ys + gs) - 2, bbox[1] - pad, bbox[2] + pad, max(ys + gs) + 4, bbox[3] + pad)


def reach(W, bbox, R, spot):
    """(in, out, path in): the spot reached from outside, outside reached from the spot, and the path in."""
    box = walk_box(W, bbox, R)
    starts = outside_starts(W, bbox)
    fwd = walk(W, starts, box)
    back = walk(W, [tuple(spot)], box)
    ss = set(starts)
    return tuple(spot) in fwd, any(s in back for s in ss), (path_to(fwd, tuple(spot)) if tuple(spot) in fwd else [])


# ------------------------------------------------------------------ the world from data


class Water:
    """(x, z) -> the painted water's surface y over that column, or None: tools/water_mask.py's lakes and the sea, and
    data/rivers.json's graded corridors (half the widest width plus one) near the given centres."""

    def __init__(self, g, centres, data=DATA):
        import water_mask as WM
        self.g, self.WM, self.bodies = g, WM, WM.bodies()
        self.sea = int(jload("world.json", data)["vertical"]["sea_level"])
        self.river = []
        for c in jload("rivers.json", data).get("courses") or []:
            w = max((c.get("character") or {}).get("width") or [32])
            for p in c.get("graded_polyline") or []:
                if any(math.hypot(p[0] - x, p[1] - z) < 800 for x, z in centres):
                    self.river.append((p[0], p[1], p[2], w / 2.0 + 1))
        self.cache = {}

    def __call__(self, x, z):
        k = (x, z)
        if k not in self.cache:
            lv = self.WM.level_at(x, z, self.g, self.bodies, self.sea)[1]
            if lv is None:
                gy = self.g(x, z)
                for px, pz, sy, half in self.river:
                    if math.hypot(px - x, pz - z) <= half and gy < sy:
                        lv = round(sy)
                        break
            self.cache[k] = lv
        return self.cache[k]


def in_poly(x, z, poly):
    inside, n = False, len(poly)
    for k in range(n):
        (xa, za), (xb, zb) = poly[k][:2], poly[(k + 1) % n][:2]
        if (za > z) != (zb > z) and x < xa + (z - za) * (xb - xa) / float(zb - za):
            inside = not inside
    return inside


def cell_of(x, z, data=DATA):
    gr = jload("world.json", data)["grid"]
    n = gr["cell_size"]
    return gr["row_labels"][int(z - gr["origin_z"]) // n] + gr["column_labels"][int(x - gr["origin_x"]) // n]


def box_dist(x, z, b):
    return math.hypot(max(b[0] - x, 0, x - b[2]), max(b[1] - z, 0, z - b[3]))


def authored(data, skip_ids, record=RECORD):
    """(points [(x, z, file)], rects [(x0, z0, x1, z1, file)]) for every x/z another data file authors: a dict with
    numeric x and z; a list of two numbers; a list of three read as [x, y, z] AND [x, z, y]; a list of four (x1 >= x0,
    z1 >= z0) or a min/max dict as a filled rectangle when smaller than a cell, else (lists only) by its corners. A dict
    whose id is in skip_ids is skipped whole."""
    cell = jload("world.json", data)["grid"]["cell_size"]
    pts, rects = [], []

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def walk_(o, f):
        if isinstance(o, dict):
            if o.get("id") in skip_ids:
                return
            if num(o.get("x")) and num(o.get("z")):
                pts.append((o["x"], o["z"], f))
            if all(num(o.get(k)) for k in ("min_x", "max_x", "min_z", "max_z")):
                if o["max_x"] - o["min_x"] + 1 < cell and o["max_z"] - o["min_z"] + 1 < cell:
                    rects.append((o["min_x"], o["min_z"], o["max_x"], o["max_z"], f))
            for v in o.values():
                walk_(v, f)
        elif isinstance(o, list):
            if o and len(o) in (2, 3, 4) and all(num(v) for v in o):
                if len(o) == 2:
                    pts.append((o[0], o[1], f))
                elif len(o) == 3:
                    pts.extend([(o[0], o[2], f), (o[0], o[1], f)])
                elif o[2] >= o[0] and o[3] >= o[1]:
                    if o[2] - o[0] + 1 < cell and o[3] - o[1] + 1 < cell:
                        rects.append((o[0], o[1], o[2], o[3], f))
                    else:
                        pts.extend([(o[0], o[1], f), (o[2], o[1], f), (o[0], o[3], f), (o[2], o[3], f)])
            else:
                for v in o:
                    walk_(v, f)

    for p in sorted(Path(data).glob("*.json")):
        if p.name != record:
            walk_(json.loads(p.read_text(encoding="utf-8")), p.name)
    return pts, rects


def corridor_rects(data):
    out = []

    def walk_(o):
        if isinstance(o, dict):
            if all(isinstance(o.get(k), (int, float)) for k in ("min_x", "max_x", "min_z", "max_z")):
                out.append((o["min_x"], o["min_z"], o["max_x"], o["max_z"], "routes.json corridor %s" % o.get("id")))
            for v in o.values():
                walk_(v)
        elif isinstance(o, list):
            for v in o:
                walk_(v)
    walk_(jload("routes.json", data).get("routes"))
    return out


def _points_in(o):
    """Every (x, z) a record names: x/z dicts, [x, y, z] triples and [x, z] pairs."""
    out = []
    if isinstance(o, dict):
        if isinstance(o.get("x"), (int, float)) and isinstance(o.get("z"), (int, float)):
            out.append((o["x"], o["z"]))
        for k, v in o.items():
            if k in ("why", "note"):
                continue
            out += _points_in(v)
    elif isinstance(o, list):
        if o and len(o) in (2, 3) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in o):
            out.append((o[0], o[-1]) if len(o) == 3 else (o[0], o[1]))
        else:
            for v in o:
                out += _points_in(v)
    return out


def derive_keep_clear(doc, data=DATA):
    """[(id, box (x0, z0, x1, z1), source)]: this audit's own keep-clear list. Every elder, named resident encounter,
    donor placement (its whole footprint), portal, and ferry dock within KEEP_CLEAR_RADIUS of a temple centre, and
    every ferry dock (or line stop) in FERRY_BOX."""
    centres = [tuple(t["site"]["centre"]) for t in doc["temples"]]

    def near(b):
        return any(box_dist(x, z, b) <= KEEP_CLEAR_RADIUS for x, z in centres)

    out = []
    for e in jload("elder_trees.json", data)["elders"]:
        b = (e["x"], e["z"], e["x"], e["z"])
        if near(b):
            out.append((e["id"], b, "data/elder_trees.json"))
    for e in jload("resident_encounters.json", data)["encounters"]:
        loc = e.get("location") or {}
        if isinstance(loc.get("x"), (int, float)):
            b = (loc["x"], loc["z"], loc["x"], loc["z"])
            if near(b):
                out.append((e["id"], b, "data/resident_encounters.json"))
    for p in jload("placements.json", data)["placements"]:
        pos, size = p.get("position") or {}, p.get("size")
        if p.get("kind") != "donor" or not isinstance(pos.get("x"), (int, float)) or not size:
            continue
        sx, sz = size[0], size[2]
        r = max(sx, sz)
        if (p.get("anchor_mode") or "corner") == "corner" and p.get("rotation") in (None, "none"):
            b = (pos["x"], pos["z"], pos["x"] + sx - 1, pos["z"] + sz - 1)
        else:
            # a centred or rotated paste: hold every way it can extend from its anchor
            b = (pos["x"] - r + 1, pos["z"] - r + 1, pos["x"] + r - 1, pos["z"] + r - 1)
        if near(b):
            out.append((p["id"], b, "data/placements.json (donor footprint)"))
    for p in jload("portals.json", data)["portals"]:
        at = p.get("at")
        if at:
            b = (at[0], at[-1], at[0], at[-1])
            if near(b):
                out.append((p["id"], b, "data/portals.json"))
    fer = jload("ferries.json", data)
    for d in fer["docks"]:
        pts = _points_in({k: v for k, v in d.items() if k not in ("keep_clear",)})
        if not pts:
            continue
        b = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        fx0, fz0, fx1, fz1 = FERRY_BOX
        in_box = any(fx0 <= x <= fx1 and fz0 <= z <= fz1 for x, z in pts)
        if near(b) or in_box:
            out.append((d["id"], b, "data/ferries.json docks"))
    return out


# ------------------------------------------------------------------ expectations from the data and the ground


def floors(t, g):
    """{piece name: (floor y, relief, footprint (x0, z0, x1, z1) in world coordinates)} for every structure piece."""
    cx, cz = t["site"]["centre"]
    out = {}
    for p in t["pieces"]:
        if p["kind"] != "structure":
            continue
        x0, z0, x1, z1 = p["footprint"]
        gs = [g(cx + a, cz + b) for a in range(x0, x1 + 1) for b in range(z0, z1 + 1)]
        out[p["name"]] = (max(gs), max(gs) - min(gs), (cx + x0, cz + z0, cx + x1, cz + z1))
    return out


def cache_spot(t, c, fl):
    cx, cz = t["site"]["centre"]
    lx, lz, piece = c["at"]
    if piece not in fl:
        return None
    return (cx + lx, fl[piece][0] + int(c["feet_dy"]), cz + lz)


# ------------------------------------------------------------------ the checks


def check_pack(doc, pack, rep):
    """{temple id: text}; only pack.mcmeta and one build per temple, no tags."""
    b = doc["build"]
    pack = Path(pack)
    meta = pack / "pack.mcmeta"
    if not meta.is_file():
        rep.err("pack", "%s has no pack.mcmeta" % pack)
    else:
        pf = json.loads(meta.read_text(encoding="utf-8")).get("pack", {}).get("pack_format")
        if pf != PACK_FORMAT:
            rep.err("pack", "pack_format %s, Minecraft 1.21.1 is %d" % (pf, PACK_FORMAT))
    want = {"data/%s/function/%s/%s/build.mcfunction" % (b["namespace"], b["folder"], t["id"]): t["id"]
            for t in doc["temples"]}
    fns = {}
    for f in sorted(pack.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(pack).as_posix()
        if rel == "pack.mcmeta":
            continue
        if rel in want:
            fns[want[rel]] = f.read_text(encoding="utf-8")
        else:
            rep.err("pack", "%s is not one of the temples' build functions (a tag would make the pack act uncalled)" % rel)
    for rel, tid in want.items():
        if tid not in fns:
            rep.err("pack", "%s has no build function %s" % (tid, rel))
    import function_limits
    for tid, text in fns.items():
        for n, cmd, why in function_limits.check_lines(text.splitlines(), where=tid):
            rep.err("pack", "%s/build:%d %s" % (tid, n, why))
    return fns


def check_blocks(doc, t, R, rep, data):
    tid = t["id"]
    allowed = set(doc["blocks"]["ids"])
    spawn = set(jload("spawn_blocks.json", data)["blocks"])
    pol = jload("spawn_block_policy.json", data)
    white = {x for w in pol.get("whitelist") or [] if "jungle" in (w.get("scope") or "") for x in w["blocks"]}
    written = Counter(base(st) for st in R.blocks.values())
    for b in sorted(written):
        if b not in allowed:
            rep.err("writes", "%s: writes %s, not in blocks.ids (%d)" % (tid, b, written[b]))
        if b in spawn and b not in white:
            rep.err("writes", "%s: writes %s, a spawn condition (data/spawn_blocks.json)" % (tid, b))
        if b in ("minecraft:chest", "minecraft:trapped_chest") or b.endswith("_chest"):
            rep.err("writes", "%s: writes %s (a Gimmighoul condition; the design forbids chests)" % (tid, b))
        if b.endswith("_bed"):
            rep.err("writes", "%s: writes %s (the blackout's checkpoints own respawn)" % (tid, b))
        if any(k in b for k in LIGHT):
            rep.err("writes", "%s: writes %s, which gives light (the ruins are lit by nothing)" % (tid, b))
    for n, line, why in R.bad:
        rep.err("writes", "%s/build:%d %s: %s" % (tid, n, why, line[:100]))


def check_ground(doc, t, R, g, water, fl, rep, data):
    """Dry, above the sea, nothing at or under the ground but a footprint's floor and the undercroft, every footprint
    column resting on the ground, nothing else hanging free but leaves and vines."""
    tid = t["id"]
    sea = int(jload("world.json", data)["vertical"]["sea_level"])
    rules = doc["rules"]
    if rules.get("dry_above") is not None and rules["dry_above"] < sea:
        rep.err("ground", "rules.dry_above %s is below the sea level y%d" % (rules["dry_above"], sea))
    cx, cz = t["site"]["centre"]
    m = re.search(r"\by(\d+) at the centre", (t.get("site") or {}).get("measured") or "")
    if not m:
        rep.err("ground", "%s: site.measured states no 'yN at the centre'" % tid)
    elif int(m.group(1)) != g(cx, cz):
        rep.err("ground", "%s: site.measured says y%s at the centre, the heightmap gives y%d" % (tid, m.group(1), g(cx, cz)))
    for name, (f, relief, _b) in fl.items():
        if relief > rules["max_foundation"]:
            rep.err("ground", "%s %s: the ground under the footprint varies by %d (max_foundation %d)"
                    % (tid, name, relief, rules["max_foundation"]))
        rep.note("%s %s: floor y%d, relief %d" % (tid, name, f, relief))
    cols = R.columns()
    low = sorted((x, z, g(x, z)) for x, z in cols if g(x, z) <= sea)
    if low:
        rep.err("ground", "%s: %d written column(s) at or below y%d, the sea, e.g. %s" % (tid, len(low), sea, low[:3]))
    wet = sorted((x, z) for x, z in cols if water(x, z) is not None)
    if wet:
        rep.err("ground", "%s: %d written column(s) wet, e.g. %s" % (tid, len(wet), wet[:3]))
    feet = [b for _n, (_f, _r, b) in fl.items()]

    def in_feet(x, z):
        return any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for b in feet)

    uc = UNDERCROFT.get(tid)
    first = next(iter(fl.values()))[0] if fl else None

    def in_undercroft(x, y, z):
        return uc is not None and cx + uc[0] <= x <= cx + uc[2] and cz + uc[1] <= z <= cz + uc[3] \
            and first + uc[4] <= y <= first + uc[5]

    under, dug = [], []
    for (x, y, z), st in R.blocks.items():
        gy = g(x, z)
        if y < gy and not in_undercroft(x, y, z):
            under.append((x, y, z, base(st)))
        elif y <= gy and not in_feet(x, z):
            dug.append((x, y, z, base(st)))
    if under:
        rep.err("ground", "%s: %d write(s) under the ground outside the undercroft, e.g. %s" % (tid, len(under), sorted(under)[:3]))
    if dug:
        rep.err("ground", "%s: %d write(s) into the ground outside every structure footprint, e.g. %s" % (tid, len(dug), sorted(dug)[:3]))
    for c in R.clears:
        if c[1] <= min(g(x, z) for x in range(c[0], c[3] + 1) for z in range(c[2], c[5] + 1)):
            rep.err("ground", "%s: a clear %s reaches the ground" % (tid, list(c[:6])))
    lowest = {}
    for (x, y, z), st in R.blocks.items():
        b = base(st)
        if b == AIR:
            continue
        if in_feet(x, z) or b not in ("minecraft:jungle_leaves", "minecraft:vine"):
            if (x, z) not in lowest or y < lowest[(x, z)][0]:
                lowest[(x, z)] = (y, b)
    floating = sorted((x, z, y, b) for (x, z), (y, b) in lowest.items() if y > g(x, z) + 1)
    if floating:
        rep.err("ground", "%s: %d column(s) whose lowest block does not rest on the ground, e.g. %s"
                % (tid, len(floating), floating[:3]))
    for name, (f, relief, b) in fl.items():
        gaps = []
        for x in range(b[0], b[2] + 1):
            for z in range(b[1], b[3] + 1):
                if (x, z) not in lowest or g(x, z) >= f:
                    continue
                for y in range(g(x, z) + 1, f + 1):
                    if passable(base(R.blocks.get((x, y, z), AIR))):
                        gaps.append((x, y, z))
                        break
        if gaps:
            rep.err("ground", "%s %s: the foundation has a gap under the floor y%d, e.g. %s" % (tid, name, f, gaps[:3]))


def check_bbox(t, R, spots, rep):
    tid = t["id"]
    x0, z0, x1, z1 = t["bbox"]
    out = sorted((x, z) for x, z in R.columns() | {(s[0], s[2]) for s in spots if s}
                 if not (x0 <= x <= x1 and z0 <= z <= z1))
    if out:
        rep.err("writes", "%s: %d written, cleared or cache column(s) outside the bbox %s, e.g. %s" % (tid, len(out), t["bbox"], out[:3]))


def check_hold(t, R, W, rep):
    """Every vine face, ladder, wall sign and carpet backed."""
    tid = t["id"]
    for (x, y, z), st in sorted(R.blocks.items()):
        b, pr = base(st), props(st)
        need = []
        if b == "minecraft:vine":
            faces = [d for d in ("north", "south", "east", "west", "up") if pr.get(d) == "true"]
            if not faces:
                rep.err("hold", "%s: a vine at %s has no face" % (tid, (x, y, z)))
            need = faces
        elif b == "minecraft:ladder" or b.endswith("_wall_sign"):
            if pr.get("facing") not in DIRS:
                rep.err("hold", "%s: %s at %s has no facing" % (tid, b, (x, y, z)))
                continue
            need = [OPPOSITE[pr["facing"]]]
        elif b.endswith("_carpet"):
            # a carpet survives on anything that is not air (CarpetBlock.canSurvive: !isEmptyBlock(below))
            nb = W.at(x, y - 1, z)
            if nb in (AIR, "minecraft:cave_air"):
                rep.err("hold", "%s: %s at %s stands on air" % (tid, b, (x, y, z)))
            continue
        elif is_sign(b):
            need = ["down"]
        for d in need:
            dx, dy, dz = DIRS[d]
            nb = W.at(x + dx, y + dy, z + dz)
            if not full(nb) and not (d == "down" and not passable(nb)):
                rep.err("hold", "%s: %s at %s is not backed: %s side is %s" % (tid, b, (x, y, z), d, nb))


def check_reach(t, R, g, spot, rep):
    tid = t["id"]
    if spot is None:
        return
    W = World(R, g)
    i, o, path = reach(W, t["bbox"], R, spot)
    if not i:
        rep.err("reach", "%s: the cache spot %s cannot be reached from outside" % (tid, list(spot)))
    if not o:
        rep.err("reach", "%s: no way back out from the cache spot %s" % (tid, list(spot)))
    used = sorted({n for n in path if W.climb(*n) or W.climb(n[0], n[1] - 1, n[2])})
    rep.note("%s: the way in is %d steps; climbable cells on it: %s" % (tid, len(path), used[:12]))
    if tid in NEEDS_CLIMB:
        Wn = World(R, g, no_climb=True)
        i2, o2, _p = reach(Wn, t["bbox"], R, spot)
        if i2 and o2:
            rep.err("reach", "%s: the cache spot %s is reached both ways without climbing (the design: only by climbing)"
                    % (tid, list(spot)))
    if tid in CLIMB_ROUTE:
        what, ok = CLIMB_ROUTE[tid]
        Wr = World(R, g, climb_ok=ok)
        i4, o4, p4 = reach(Wr, t["bbox"], R, spot)
        if not (i4 and o4):
            rep.err("reach", "%s: the cache spot %s is not reached %s (in %s, out %s)" % (tid, list(spot), what, i4, o4))
        other = sorted({n for n in path if W.climb(*n) and not ok(R.blocks.get(n, ""))})
        if other:
            rep.note("%s: the shortest way in also climbs elsewhere than %s: %s" % (tid, what, other))
    if tid in THROUGH_TRAPDOOR:
        traps = [k for k, st in R.blocks.items() if base(st).endswith("_trapdoor")]
        if not traps:
            rep.err("reach", "%s: no trapdoor is written (the eye)" % tid)
        else:
            Wt = World(R, g, blocked=traps)
            i3, _o3, _p = reach(Wt, t["bbox"], R, spot)
            if i3:
                rep.err("reach", "%s: the cache spot is reached with the trapdoor shut (the design: only through the eye)" % tid)
            if i and not any(n in traps for n in path):
                rep.err("reach", "%s: the way in does not pass the trapdoor" % tid)


def check_eye(t, R, fl, rep):
    """The Ring Court's eye: a trapdoor at the ring's centre on the court's top layer, a ladder of LADDER_RUN under it,
    every rung on the pillar's south face (facing south, a solid block north of it)."""
    tid = t["id"]
    if tid not in LADDER_RUN:
        return
    cx, cz = t["site"]["centre"]
    f = next(iter(fl.values()))[0]
    top = [k for k, st in R.blocks.items() if base(st).endswith("_trapdoor")]
    if not top:
        return
    tx, ty, tz = top[0]
    if (tx, tz) != (cx, cz):
        rep.err("eye", "%s: the trapdoor is at %s, not the ring's centre (%d, %d)" % (tid, top[0], cx, cz))
    run = []
    y = ty - 1
    while base(R.blocks.get((tx, y, tz), AIR)) == "minecraft:ladder":
        run.append(y)
        y -= 1
    if len(run) != LADDER_RUN[tid]:
        rep.err("eye", "%s: a ladder of %d under the trapdoor, the design says %d" % (tid, len(run), LADDER_RUN[tid]))
    for y in run:
        if props(R.blocks[(tx, y, tz)]).get("facing") != "south":
            rep.err("eye", "%s: the rung at y%d is not on a south face" % (tid, y))
    rep.note("%s: trapdoor %s, floor y%d, ladder y%s..y%s" % (tid, top[0], f, run[-1] if run else None, run[0] if run else None))


def check_siting(doc, t, cols, A, kc, rep, data):
    import numpy as np
    tid, rules = t["id"], doc["rules"]
    m = rules["authored_clearance"]
    sub = [s for s in jload("regions.json", data)["subregions"] if s["id"] == rules["subregion"]]
    if not sub:
        rep.err("siting", "no sub-region %s in data/regions.json" % rules["subregion"])
    else:
        polys = sub[0]["polygons"]
        out = sorted(c for c in cols if not any(in_poly(c[0], c[1], p) for p in polys))
        if out:
            rep.err("siting", "%s: %d column(s) outside %s, e.g. %s" % (tid, len(out), rules["subregion"], out[:3]))
    pts, rects = A
    C = np.array(sorted(cols), float)
    P = np.array([(a, b) for a, b, _f in pts], float)
    best = (1e18, None, None)
    for k in range(0, len(C), 128):
        blk = C[k:k + 128]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(int(v) for v in blk[j[0]]), pts[j[1]][2])
    for x0, z0, x1, z1, f in list(rects) + corridor_rects(data):
        dx = np.maximum(np.maximum(x0 - C[:, 0], C[:, 0] - x1), 0)
        dz = np.maximum(np.maximum(z0 - C[:, 1], C[:, 1] - z1), 0)
        d = np.hypot(dx, dz)
        j = int(np.argmin(d))
        if d[j] < best[0]:
            best = (float(d[j]), tuple(int(v) for v in C[j]), "%s (box %s)" % (f, [x0, z0, x1, z1]))
    if best[0] < m:
        rep.err("siting", "%s: (%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                % (tid, best[1][0], best[1][1], best[0], best[2], m))
    rep.note("%s: nearest authored x/z %.0f, from %s, in data/%s" % (tid, best[0], best[1], best[2]))
    for tw in jload("towns.json", data)["towns"]:
        f = tw.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            rep.err("siting", "%s: within %d of town %s's footprint" % (tid, m, tw["id"]))
    for k, zone in jload("rift_zones.json", data)["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                rep.err("siting", "%s: inside Rift zone %s" % (tid, k))
                break
    need = rules["keep_clear"]["blocks"]
    near = []
    for eid, b, src in kc:
        d = float(np.min(np.hypot(np.maximum(np.maximum(b[0] - C[:, 0], C[:, 0] - b[2]), 0),
                                  np.maximum(np.maximum(b[1] - C[:, 1], C[:, 1] - b[3]), 0))))
        near.append((d, eid))
        if d < need:
            rep.err("siting", "%s: %.0f blocks from %s (%s; keep-clear needs %d)" % (tid, d, eid, src, need))
    near.sort()
    rep.note("%s: nearest keep-clear %s" % (tid, ", ".join("%s %.0f" % (i, d) for d, i in near[:4])))
    cx, cz = t["site"]["centre"]
    if cell_of(cx, cz, data) != t.get("cell"):
        rep.err("siting", "%s: the centre is in cell %s, the record says %s" % (tid, cell_of(cx, cz, data), t.get("cell")))


def check_keep_clear_list(doc, kc, rep):
    """The record's keep_clear entries hold every entry this audit derives, with a box at least as large."""
    rec = {e["id"]: e["box"] for e in doc["rules"]["keep_clear"]["entries"]}
    for eid, b, src in kc:
        if eid not in rec:
            rep.err("keep_clear", "the record's keep_clear list lacks %s %s (%s, within %d of a temple)"
                    % (eid, list(b), src, KEEP_CLEAR_RADIUS))
            continue
        r = rec[eid]
        if not (r[0] <= b[0] and r[1] <= b[1] and r[2] >= b[2] and r[3] >= b[3]):
            rep.err("keep_clear", "the record holds %s as %s, smaller than its %s %s" % (eid, r, src, list(b)))


def check_mark(doc, R_by, data, rep):
    """The Harbour Mark's arm and HARBOUR sign point to Sunset West; the prose distance is the measured one."""
    t = [x for x in doc["temples"] if x["id"] == "harbour_mark"]
    if not t or "harbour_mark" not in R_by:
        rep.err("mark", "no harbour_mark temple or build")
        return
    t, R = t[0], R_by["harbour_mark"]
    cx, cz = t["site"]["centre"]
    arm = [(x, y, z) for (x, y, z), st in R.blocks.items() if base(st).endswith("_slab")
           and (x, z) != (cx, cz) and max(abs(x - cx), abs(z - cz)) <= 3]
    if not arm:
        rep.err("mark", "harbour_mark: no arm (slabs off the obelisk's column)")
        return
    ax = sum(x - cx for x, _y, _z in arm) / len(arm)
    az = sum(z - cz for _x, _y, z in arm) / len(arm)
    arm_ang = math.degrees(math.atan2(az, ax))
    tw = [x for x in jload("towns.json", data)["towns"] if x["id"] == "sunset_west"][0]["centre"]
    dock = [d for d in jload("ferries.json", data)["docks"] if d["id"] == "sunset_quay"]
    targets = [("sunset_west centre", (tw["x"], tw["z"]))]
    if dock:
        targets.append(("sunset_quay", tuple(dock[0]["near"])))
    for name, (x, z) in targets:
        ang = math.degrees(math.atan2(z - cz, x - cx))
        off = abs((ang - arm_ang + 180) % 360 - 180)
        dist = math.hypot(x - cx, z - cz)
        rep.note("harbour_mark: the arm points %.0f deg; %s is at %.0f deg, %.0f off, %.0f blocks" % (arm_ang, name, ang, off, dist))
        if off > 45:
            rep.err("mark", "harbour_mark: the arm points %.0f degrees off %s" % (off, name))
    signs = [(k, st) for k, st in R.blocks.items() if base(st).endswith("_wall_sign") and "HARBOUR" in st]
    if not signs:
        rep.err("mark", "harbour_mark: no sign reads HARBOUR")
    along = ((1 if ax > 0 else -1), 0) if abs(ax) >= abs(az) else (0, (1 if az > 0 else -1))
    for k, st in signs:
        dx, _dy, dz = DIRS.get(props(st).get("facing"), (0, 0, 0))
        if (dx, dz) != along:
            rep.err("mark", "harbour_mark: the HARBOUR sign at %s faces %s, not along the arm" % (k, props(st).get("facing")))
    km = re.search(r"about (\d+(?:\.\d+)?) km", t.get("story_rule") or "")
    if km:
        d = math.hypot(targets[-1][1][0] - cx, targets[-1][1][1] - cz) / 1000.0
        if abs(float(km.group(1)) - d) > 0.25:
            rep.err("mark", "harbour_mark: the story_rule says Sunset West is about %s km away; measured %.2f km to %s"
                    % (km.group(1), d, targets[-1][0]))


def _jar_item(jar, item):
    ns, _, path = item.partition(":")
    return "assets/%s/models/item/%s.json" % (ns, path) in jar


def economy_curve(data, skip):
    """{tier: (max stacks, max items, max stones)} over every other cache in data/rewards.json, by the sub-region its
    container stands in (data/encounter_design.json tables tier). Caches outside every tabled sub-region are left out."""
    subs = jload("regions.json", data)["subregions"]
    tab = jload("encounter_design.json", data)["tables"]
    by = {}
    for r in jload("rewards.json", data)["rewards"]:
        if r.get("kind") != "cache" or r["id"] in skip:
            continue
        at = (r.get("container") or {}).get("at") or (r.get("trigger") or {}).get("min")
        if not at:
            continue
        sid = next((s["id"] for s in subs if any(in_poly(at[0], at[2], p) for p in s.get("polygons") or [])), None)
        tier = (tab.get(sid) or {}).get("tier")
        if tier is None:
            continue
        c = r.get("contents") or []
        v = (len(c), sum(int(i["count"]) for i in c), sum(int(i["count"]) for i in c if _is_stone(i["item"])))
        by.setdefault(tier, []).append(v)
    return by


def _is_stone(item):
    return item.startswith("cobblemon:") and item.endswith("_stone") and item not in ("cobblemon:everstone",
                                                                                     "cobblemon:hard_stone")


def check_caches(doc, t, R, spot, jar, curve, rep, data):
    tid = t["id"]
    rw = {x["id"]: x for x in jload("rewards.json", data)["rewards"]}
    subs = jload("regions.json", data)["subregions"]
    tab = jload("encounter_design.json", data)["tables"]
    tiers = jload("encounter_design.json", data)["rules"]["tiers"]
    for c in t.get("caches") or []:
        rid = c["reward"]
        w = rw.get(rid)
        if not w or w.get("kind") != "cache":
            rep.err("caches", "%s: data/rewards.json %s is not a cache" % (tid, rid))
            continue
        contents = w.get("contents") or []
        if not contents:
            rep.err("caches", "%s: %s gives nothing" % (tid, rid))
        if jar is not None:
            for it in contents:
                if not _jar_item(jar, it["item"]):
                    rep.err("caches", "%s: %s gives %s, not an item in the Cobblemon jar" % (tid, rid, it["item"]))
        ct = w.get("container") or {}
        tr = w.get("trigger") or {}
        if spot is None:
            rep.err("caches", "%s: %s names no structure floor to stand on" % (tid, rid))
            continue
        want = [spot[0], spot[1] - 1, spot[2]]
        if ct.get("at") != want:
            rep.err("caches", "%s: %s container at %s; its spot on the heightmap's floor puts it at %s" % (tid, rid, ct.get("at"), want))
        if base(R.blocks.get(tuple(want), "")) != ct.get("block"):
            rep.err("caches", "%s: %s's %s is not written at %s (the build writes %s)"
                    % (tid, rid, ct.get("block"), want, R.blocks.get(tuple(want))))
        lo, hi = tr.get("min"), tr.get("max")
        if not (lo and hi and all(lo[i] <= spot[i] <= hi[i] for i in range(3))):
            rep.err("caches", "%s: %s's trigger %s..%s does not hold the spot %s" % (tid, rid, lo, hi, list(spot)))
        for dy in (0, 1):
            b = base(R.blocks.get((spot[0], spot[1] + dy, spot[2]), AIR))
            if b not in (AIR, "minecraft:moss_carpet"):
                rep.err("caches", "%s: %s's spot %s has %s at feet+%d (two blocks of standing room)" % (tid, rid, list(spot), b, dy))
        # the economy curve at this cache's tier
        sid = next((s["id"] for s in subs if any(in_poly(want[0], want[2], p) for p in s.get("polygons") or [])), None)
        tier = (tab.get(sid) or {}).get("tier")
        if tier is None:
            rep.err("caches", "%s: %s stands in sub-region %s, which has no tier" % (tid, rid, sid))
            continue
        peers = [v for k, vs in curve.items() if k <= tier for v in vs]
        mine = (len(contents), sum(int(i["count"]) for i in contents), sum(int(i["count"]) for i in contents if _is_stone(i["item"])))
        if not peers:
            rep.err("caches", "%s: no other cache at tier %d or below to measure %s against" % (tid, tier, rid))
        else:
            cap = tuple(max(v[k] for v in peers) for k in range(3))
            for k, what in enumerate(("stacks", "items", "evolution stones")):
                if mine[k] > cap[k]:
                    rep.err("caches", "%s: %s gives %d %s; no other cache at tier <= %d gives more than %d"
                            % (tid, rid, mine[k], what, tier, cap[k]))
            rep.note("%s: %s at tier %d gives %s against the curve's ceiling %s (%d peers)" % (tid, rid, tier, mine, cap, len(peers)))
        band = doc.get("band", {}).get("levels")
        tb = (tiers.get(str(tier)) or {}).get("band")
        if band and tb and not (tb[0] <= band[0] and band[1] <= tb[1]):
            rep.err("caches", "%s: the record's band %s is outside tier %d's band %s" % (tid, band, tier, tb))


def check_steps(doc, steps, R_by, rep):
    """Per temple: forceload add of a box holding every write, its build, forceload remove of the same box."""
    b = doc["build"]
    fns = {"%s:%s/%s/build" % (b["namespace"], b["folder"], t["id"]): t["id"] for t in doc["temples"]}
    called = Counter()
    held = None
    for s in steps:
        kind, v = s[0], s[1]
        if kind == "cmd" and v.startswith("forceload add "):
            held = [int(n) for n in v.split()[2:6]]
        elif kind == "cmd" and v.startswith("forceload remove "):
            if [int(n) for n in v.split()[2:6]] != held:
                rep.err("steps", "a forceload remove %s that is not the box held %s" % (v, held))
            held = None
        elif kind == "fn":
            tid = fns.get(v)
            if tid is None:
                rep.err("steps", "the step runs %s, not one of the temples' builds" % v)
                continue
            called[tid] += 1
            if held is None:
                rep.err("steps", "%s runs with nothing force-loaded" % v)
                continue
            R = R_by.get(tid)
            if R is not None:
                x0, z0, x1, z1 = min(held[0], held[2]), min(held[1], held[3]), max(held[0], held[2]), max(held[1], held[3])
                out = [c for c in R.columns() if not (x0 <= c[0] <= x1 and z0 <= c[1] <= z1)]
                if out:
                    rep.err("steps", "%s writes %d column(s) outside its forceload %s, e.g. %s" % (tid, len(out), held, out[:2]))
        elif kind == "wait":
            continue
        else:
            rep.err("steps", "an unexpected step %s" % (s,))
    if held is not None:
        rep.err("steps", "the steps end still holding %s" % held)
    for tid in fns.values():
        if called[tid] != 1:
            rep.err("steps", "%s's build runs %d time(s)" % (tid, called[tid]))


def check_wiring(doc, rep, text=None):
    text = text if text is not None else (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    jobs = [m.group(1) for m in re.finditer(r'add\("([^"]+)",\s*"([^"]+)\.py"', text)]
    for j in (PREPARE_AFTER, GENERATOR, GENERATOR + "_audit"):
        if j not in jobs:
            rep.err("wiring", "tools/reapply.py has no prepare job %s" % j)
    if all(j in jobs for j in (PREPARE_AFTER, GENERATOR, GENERATOR + "_audit")):
        if not jobs.index(PREPARE_AFTER) < jobs.index(GENERATOR) < jobs.index(GENERATOR + "_audit"):
            rep.err("wiring", "the prepare jobs are not %s, then %s, then %s_audit" % (PREPARE_AFTER, GENERATOR, GENERATOR))
    m = re.search(r'add\("%s_audit",\s*"([^"]+)"' % GENERATOR, text)
    if m and m.group(1) != Path(__file__).name:
        rep.err("wiring", "the prepare job %s_audit runs %s" % (GENERATOR, m.group(1)))
    order = [m.group(1) for m in re.finditer(r'out\.append\(\("(R[0-9A-Z]+)"', text)]
    calls = {m.group(1): m.group(2) for m in re.finditer(
        r'out\.append\(\("(R[0-9A-Z]+)",\s*"[^"]*",\s*\n?\s*([A-Za-z_]+\.[A-Za-z_]+)\(\)\)\)', text)}
    step = doc["build"]["step"]
    if order.count(step) != 1:
        rep.err("wiring", "tools/reapply.py appends step %s %d times" % (step, order.count(step)))
    else:
        if calls.get(step) != "%s.placement_steps" % GENERATOR:
            rep.err("wiring", "step %s is %s, not %s.placement_steps()" % (step, calls.get(step), GENERATOR))
        k = order.index(step)
        if STEP_AFTER not in order or order.index(STEP_AFTER) > k:
            rep.err("wiring", "step %s runs before %s" % (step, STEP_AFTER))
        if STEP_BEFORE not in order or order.index(STEP_BEFORE) < k:
            rep.err("wiring", "step %s runs after %s" % (step, STEP_BEFORE))
    tree = ast.parse(text)
    vals = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tg in node.targets:
                if getattr(tg, "id", None) in ("SERVER_PACKS", "WORLD_LOCAL"):
                    try:
                        vals[tg.id] = ast.literal_eval(node.value)
                    except ValueError:
                        vals[tg.id] = None
    pack = doc["build"]["pack"]
    if pack not in (vals.get("SERVER_PACKS") or ()):
        rep.err("wiring", "%s is not in tools/reapply.py SERVER_PACKS" % pack)
    if pack in (vals.get("WORLD_LOCAL") or ()):
        rep.err("wiring", "%s is in WORLD_LOCAL: a pack with no load or tick has no reason to be world-local" % pack)


def _code_strings(text):
    """Every string constant in a module's code, docstrings excepted."""
    tree = ast.parse(text)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
                docs.add(id(first.value))
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


def check_ruins(rep, data=DATA, tools=ROOT / "tools", builds=ROOT / "build" / "datapacks"):
    pl = jload("placements.json", data)
    live = {p.get("id") for p in pl["placements"]}
    sup = {r.get("id") for r in (pl.get("superseded_placements") or {}).get("records") or []}
    for r in RUINS:
        if r in live:
            rep.err("ruins", "%s is still in data/placements.json placements" % r)
        if r not in sup:
            rep.err("ruins", "%s is not in data/placements.json superseded_placements.records" % r)
    for p in sorted(Path(tools).glob("*.py")):
        if p.name == Path(__file__).name:
            continue
        text = p.read_text(encoding="utf-8")
        if not any(r in text for r in RUINS):
            continue
        try:
            strs = _code_strings(text)
        except SyntaxError:
            strs = [text]
        named = sorted({r for r in RUINS for s in strs if r in s})
        if named:
            rep.err("ruins", "tools/%s names %s in its code" % (p.name, named))
        else:
            rep.note("tools/%s names a superseded ruin in a docstring or comment only" % p.name)
    n = 0
    if Path(builds).is_dir():
        for f in Path(builds).rglob("*"):
            if f.is_file() and f.suffix in (".mcfunction", ".json", ".mcmeta"):
                n += 1
                t = f.read_text(encoding="utf-8", errors="replace")
                for r in RUINS:
                    if r in t:
                        rep.err("ruins", "the built %s names %s" % (f.relative_to(builds).as_posix(), r))
    rep.note("ruins: %d built pack file(s) under %s scanned" % (n, builds))


# ------------------------------------------------------------------ the whole audit


def audit(doc, g, water, pack, steps, data=DATA, jar=None, reapply_text=None, ruins=True):
    rep = Report()
    if doc.get("schema") != SCHEMA:
        rep.err("spec", "schema %s, expected %s" % (doc.get("schema"), SCHEMA))
    check_wiring(doc, rep, reapply_text)
    if ruins:
        check_ruins(rep, data)
    fns = check_pack(doc, pack, rep)
    own = {c["reward"] for t in doc["temples"] for c in t.get("caches") or []}
    A = authored(data, own)
    kc = derive_keep_clear(doc, data)
    rep.note("keep-clear, derived here (%d): %s" % (len(kc), ", ".join("%s %s" % (i, list(b)) for i, b, _s in kc)))
    check_keep_clear_list(doc, kc, rep)
    curve = economy_curve(data, own)
    R_by = {}
    for t in doc["temples"]:
        text = fns.get(t["id"])
        if text is None:
            continue
        R = Replay(text)
        R_by[t["id"]] = R
        fl = floors(t, g)
        spots = [cache_spot(t, c, fl) for c in t.get("caches") or []]
        check_blocks(doc, t, R, rep, data)
        check_ground(doc, t, R, g, water, fl, rep, data)
        check_bbox(t, R, spots, rep)
        W = World(R, g)
        check_hold(t, R, W, rep)
        check_eye(t, R, fl, rep)
        for s in spots:
            check_reach(t, R, g, s, rep)
            if s is not None and water(s[0], s[2]) is not None:
                rep.err("caches", "%s: the cache spot %s is on a wet column" % (t["id"], list(s)))
        cols = R.columns() | {(s[0], s[2]) for s in spots if s}
        if cols:
            check_siting(doc, t, cols, A, kc, rep, data)
        for s in spots or [None]:
            check_caches(doc, t, R, s, jar, curve, rep, data)
    check_mark(doc, R_by, data, rep)
    check_steps(doc, steps, R_by, rep)
    return rep


def generator_steps(source_root=None):
    """The steps the generator hands tools/reapply.py, read in a SUBPROCESS: its output, never imported here."""
    code = ("import sys, json; sys.path.insert(0, %r); import %s as J; import ground as G; "
            "print(json.dumps(J.placement_steps(None, G.load(%r))))" % (str(ROOT / "tools"), GENERATOR, source_root))
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError((res.stdout + res.stderr).strip()[-400:])
    return [tuple(s) for s in json.loads(res.stdout.strip().splitlines()[-1])]


def jar_names(path=None):
    import zipfile
    if path is None:
        import battle_sim
        path = battle_sim.find_jar()
    with zipfile.ZipFile(path) as z:
        return set(z.namelist())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=None, help="default build/datapacks/cobblers_jungle_temples; when that is absent "
                                                  "the generator is run into a temporary folder and that is audited")
    ap.add_argument("--jar", default=None, help="the Cobblemon 1.8 jar (default: tools/battle_sim.find_jar())")
    ap.add_argument("--source-root")
    ap.add_argument("-v", "--verbose", action="store_true", help="print the notes too")
    a = ap.parse_args(argv)
    import ground as G
    doc = jload(RECORD)
    g = G.load(a.source_root)
    try:
        steps = generator_steps(a.source_root)
    except RuntimeError as e:
        print("PROBLEM steps: the generator refuses to give its steps: %s" % e)
        return 1
    tmp = tempfile.TemporaryDirectory()
    pack = Path(a.pack) if a.pack else PACK
    if a.pack is None and not PACK.is_dir():
        pack = Path(tmp.name) / "cobblers_jungle_temples"
        cmd = [sys.executable, str(ROOT / "tools" / (GENERATOR + ".py")), "--out", str(pack)]
        if a.source_root:
            cmd += ["--source-root", a.source_root]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("PROBLEM pack: %s is absent and the generator refuses to write one: %s"
                  % (PACK, (res.stdout + res.stderr).strip()[-400:]))
            return 1
        print("jungle_temples_audit: %s is absent; auditing the generator's output in a temporary folder" % PACK)
    jar, jar_note = None, None
    try:
        jar = jar_names(a.jar)
    except Exception as e:                    # no jar anywhere: say so, never pass silently
        jar_note = "the item checks were NOT run: no Cobblemon 1.8 jar (%s)" % e
    water = Water(g, [tuple(t["site"]["centre"]) for t in doc["temples"]])
    rep = audit(doc, g, water, pack, steps, jar=jar)
    tmp.cleanup()
    if a.verbose:
        for n in rep.notes:
            print("note: %s" % n)
    real, hits, stale = classify(rep.errors)
    for e in hits:
        print("KNOWN %s" % e)
    for e in real:
        print("PROBLEM %s" % e)
    for c, t, _w in stale:
        print("PROBLEM stale: the KNOWN fault '%s' no longer fires (fixed?): remove it from KNOWN" % t)
    if jar_note:
        print("NOT CHECKED %s" % jar_note)
    bad = len(real) + len(stale)
    verdict = "clean" if not bad else "%d problem(s)" % bad
    print("jungle_temples_audit: %s, %d known defect(s)%s" % (verdict, len(hits), " (jar checks NOT run)" if jar_note else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
