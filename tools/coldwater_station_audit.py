#!/usr/bin/env python
"""Independent audit of Coldwater Station: replays the BUILT pack against its own reading of the data.

What it reads: build/datapacks/cobblers_coldwater_station (the emitted functions, NPC classes, dialogues, the
advancement and steps.txt), data/coldwater_station.json, data/ferries.json, data/ferry_docks.json,
data/portals.json, data/sea_life.json, data/towns.json, data/placements.json, data/legendaries.json,
data/progression.json, data/spawn_blocks.json, data/spawn_block_policy.json, data/world.json, every other
data/*.json for the authored-clearance sweep, and the canonical heightmap through tools/ground.py (rounded).

What it never does: import tools/coldwater_station.py, tools/portals.py or tools/frostpeak_camp.py. Every expectation
below is recomputed here from the data and the heightmap: the floors, the arch's geometry and rules, the bearings,
ranges and quaternion directions, the lane distance. tests/test_coldwater_station_audit.py proves that by mutating
the GENERATOR (data untouched) and watching this fail.

The checks (one line each in the output):

  station_square     every station setblock/fill inside the site square
  station_dry        no station write on a column whose ground is under the sea (round(ground) < sea level)
  station_above      no write at or below the ground block (y <= round(ground))
  station_clears     the only fills are air clears replacing #minecraft:replaceable, #minecraft:logs, #minecraft:leaves
  station_blocks     every block in blocks.ids; none a spawn condition (data/spawn_blocks.json, policy whitelist noted)
  station_floors     each piece (its written columns, by nearest top-level piece) starts at max(ground)+1; every write
                     under that is foundation, contiguous from ground+1
  forceload          every written column of every function inside a forceload added in that function, and removed
  npcs               one spawnnpcat per researcher, at its column, y = host floor + 1, on a full block of its host,
                     two cells of air above the floor (a carpet allowed at the feet)
  npc_classes        each NPC class names the researcher and a dialogue the pack ships
  dialogue           every authored line present with the recomputed numbers, no placeholder left, the actions only
                     move a declared cursor (data/progression.json quest_fields) to a page that exists
  signs              the notes board's sign texts equal the authored templates filled with the recomputed numbers
  instruments        two block_displays: tube block and scale, pivot at deck floor + 2.2, R*z equal to the unit vector to
                     the target (1e-3), the tube's axis through the pivot; the telescope's sight line clear
  arch_geometry      portal/build writes exactly the 5x5 apron at max(ground) (footings to ground+1), jambs, sheet,
                     lintel and lamps from data/portals.json blocks.dive, facing as authored, plus the buoy and lantern
  arch_rules         relief, submersion, water over the lintel, the distances from portals, towns, placements and
                     legendary mouths (data/portals.json rules)
  arch_click         one interaction with the click tag at the cell in front of the sheet; the advancement fires on the
                     tag and runs touch; touch revokes first, refuses without the dive tag with its locked message,
                     then calls destination; destination only speaks (no tp, execute in, scoreboard, tag, give, ...)
  lane               every emitted arch column (grown by 3) and the click within the coldwater_crossing lane
                     (data/sea_life.json exclusions.ferry_lane_half_width_blocks) between the two landings
  sea_packs          from the BUILT cobblers_sea_life / cobblers_sea_floor packs: no write within 3 of the arch
                     (NOT RUN, and a problem only with --require-sea, when those packs are absent)
  ferry              coldwater_crossing's fare and gates equal the Northlight packet's; stops, docks, the two dock
                     records agree, id_authorship declares the jetty
  dock_clearance     every station column >= rules.dock_clearance from the jetty's keep_clear, ferryman and landing
  authored_clearance every station column >= rules.authored_clearance from every point another data/*.json authors,
                     outside every box and polygon (data/cells.json labels and data/regions.json boundaries excepted)

What it does NOT cover (validity, not behavior): whether the server accepts each command, whether the NPCs stand
once spawned, whether a block_display renders where the transformation says, whether the advancement fires on a
click, whether the ferry charges and gates in game. Those are the in-game probes in data/coldwater_station.json
audit_checklist. The sight line is a sampled walk (0.02 block steps), not an exact voxel traversal. The
authored-clearance sweep recognises points ([x, z] / [x, y, z] lists, {x, z} dicts), boxes (min_x.. dicts, {x: [a, b],
z: [c, d]}, four-number lists under box-like keys) and polygons; a shape in any other encoding is not seen.

  python tools/coldwater_station_audit.py [--pack DIR] [--inputs-root CHECKOUT] [--source-root DIR] [--require-sea]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PACK = ROOT / "build" / "datapacks" / "cobblers_coldwater_station"
FN = "data/cobblers/function/coldwater_station"
STATION_TAG = "cobblers_coldwater_station"
PIVOT_ABOVE_FLOOR = 2.2          # data/coldwater_station.json audit_checklist: "pivot at its deck floor + 2.2"
SEA_MARGIN = 3                   # audit_checklist: "neither writes a block within 3 of the arch"
CLEAR_FILTERS = {"#minecraft:replaceable", "#minecraft:logs", "#minecraft:leaves"}
FACING = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
# a stub and the click path may only speak; anything else changes state
STUB_ALLOWED = {"tellraw", "title", "playsound", "particle"}
FULL_SUFFIX = ("_planks", "_log", "_wood", "_wool", "_ice", "bookshelf", "barrel", "cobblestone", "smoker",
               "cartography_table", "polished_deepslate", "copper_block", "_bricks", "prismarine", "stone")


# ------------------------------------------------------------------------------------------------ small geometry
def bearing(dx, dz):
    """Clockwise from north (-z), degrees in [0, 360)."""
    return math.degrees(math.atan2(dx, -dz)) % 360


def qrot(q, v):
    """Rotate v by the unit quaternion q = [x, y, z, w] (Minecraft's order)."""
    x, y, z, w = q
    vx, vy, vz = v
    # t = 2 * cross(q.xyz, v); v' = v + w t + cross(q.xyz, t)
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    return [vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx)]


def seg_dist(p, a, b):
    ax, az = a
    bx, bz = b
    px, pz = p
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L2))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))


def box_dist(x, z, box):
    x0, z0, x1, z1 = box
    gx = max(0, min(x0, x1) - x, x - max(x0, x1))
    gz = max(0, min(z0, z1) - z, z - max(z0, z1))
    return math.hypot(gx, gz)


def in_polygon(x, z, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, z1 = poly[i][0], poly[i][-1]
        x2, z2 = poly[(i + 1) % n][0], poly[(i + 1) % n][-1]
        if (z1 > z) != (z2 > z):
            xc = x1 + (z - z1) * (x2 - x1) / (z2 - z1)
            if x < xc:
                inside = not inside
    return inside


def block_id(state):
    return re.split(r"[\[{]", state, 1)[0]


# ------------------------------------------------------------------------------------------------------- parsing
def commands(path):
    """[(line number, command)] without comments or blanks."""
    out = []
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if s and not s.startswith("#"):
            out.append((i, s))
    return out


def parse_writes(cmds):
    """setblocks as (x, y, z, state); fills as (x0, y0, z0, x1, y1, z1, state, mode, filter)."""
    sets, fills, other = [], [], []
    for _i, c in cmds:
        if c.startswith("setblock "):
            t = c.split(" ", 4)
            sets.append((int(t[1]), int(t[2]), int(t[3]), t[4]))
        elif c.startswith("fill "):
            t = c.split(" ")
            a = [int(v) for v in t[1:7]]
            x0, x1 = sorted((a[0], a[3]))
            y0, y1 = sorted((a[1], a[4]))
            z0, z1 = sorted((a[2], a[5]))
            fills.append((x0, y0, z0, x1, y1, z1, t[7], t[8] if len(t) > 8 else None, t[9] if len(t) > 9 else None))
        else:
            other.append(c)
    return sets, fills, other


def forceload_problems(name, cmds):
    """Every written column inside a forceload added in this function; every add removed again."""
    probs = []
    added, removed = [], []
    for _i, c in cmds:
        t = c.split()
        if t[0] == "forceload" and t[1] in ("add", "remove"):
            v = [int(s) for s in t[2:6]] if len(t) >= 6 else [int(t[2]), int(t[3]), int(t[2]), int(t[3])]
            box = (min(v[0], v[2]), min(v[1], v[3]), max(v[0], v[2]), max(v[1], v[3]))
            (added if t[1] == "add" else removed).append(box)
    sets, fills, _ = parse_writes(cmds)
    cols = {(x, z) for x, _y, z, _s in sets}
    for f in fills:
        cols |= {(x, z) for x in range(f[0], f[3] + 1) for z in range(f[2], f[5] + 1)}
    for _i, c in cmds:
        m = re.match(r"summon \S+ (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)", c)
        if m:
            cols.add((math.floor(float(m.group(1))), math.floor(float(m.group(3)))))

    def chunked(b):
        return (b[0] >> 4, b[1] >> 4, b[2] >> 4, b[3] >> 4)
    for x, z in sorted(cols):
        if not any(b[0] >> 4 <= x >> 4 <= b[2] >> 4 and b[1] >> 4 <= z >> 4 <= b[3] >> 4 for b in added):
            probs.append("%s: column (%d, %d) is written outside every forceload the function adds" % (name, x, z))
            break
    if sorted(map(chunked, added)) != sorted(map(chunked, removed)):
        probs.append("%s: forceloads added %s are not the ones removed %s" % (name, added, removed))
    return probs


# --------------------------------------------------------------------------------------------------------- data
def load_json(root, rel):
    return json.loads((Path(root) / rel).read_text(encoding="utf-8"))


class Inputs:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        j = lambda rel: load_json(self.root, rel)   # noqa: E731
        self.doc = j("data/coldwater_station.json")
        self.ferries = j("data/ferries.json")
        self.ferry_docks = j("data/ferry_docks.json")
        self.portals = j("data/portals.json")
        self.sea_life = j("data/sea_life.json")
        self.towns = j("data/towns.json")
        self.placements = j("data/placements.json")
        self.legendaries = j("data/legendaries.json")
        self.progression = j("data/progression.json")
        self.spawn_blocks = j("data/spawn_blocks.json")
        self.policy = j("data/spawn_block_policy.json")
        self.world = j("data/world.json")
        self.id_authorship = (self.root / "data" / "id_authorship.json").read_text(encoding="utf-8")
        self.sea = self.world["vertical"]["sea_level"]

    def dock(self, did):
        return next(d for d in self.ferries["docks"] if d["id"] == did)

    def line(self, lid):
        return next(l for l in self.ferries["lines"] if l["id"] == lid)


# ------------------------------------------------------------------------------------------------------- the audit
class Audit:
    def __init__(self, inputs, pack, ground, sea_packs_root=None, require_sea=False):
        self.I = inputs
        self.d = inputs.doc
        self.pack = Path(pack)
        self.g = ground
        self.sea_root = Path(sea_packs_root) if sea_packs_root else None
        self.require_sea = require_sea
        self.results = []           # (check, [problems])
        self.notes = []

    def fn(self, rel):
        return self.pack / FN / (rel + ".mcfunction")

    def check(self, name, probs):
        self.results.append((name, list(probs)))

    # ---------------------------------------------------------------- the station's blocks
    def station(self):
        d, g, sea = self.d, self.g, self.I.sea
        cmds = commands(self.fn("build"))
        sets, fills, other = parse_writes(cmds)
        self.sets, self.fills = sets, fills
        cx, cz = d["site"]["corner"]
        n = d["site"]["size"]
        inside = lambda x, z: cx <= x < cx + n and cz <= z < cz + n   # noqa: E731
        sq, dry, above, clears = [], [], [], []
        for x, y, z, s in sets:
            if not inside(x, z):
                sq.append("setblock (%d, %d, %d) %s is outside the site square" % (x, y, z, block_id(s)))
            if g(x, z) < sea:
                dry.append("setblock (%d, %d, %d) on a water column (ground y%d)" % (x, y, z, g(x, z)))
            if y <= g(x, z):
                above.append("setblock (%d, %d, %d) %s is in the ground (ground y%d)" % (x, y, z, block_id(s), g(x, z)))
        for f in fills:
            x0, y0, z0, x1, y1, z1, s, mode, filt = f
            if s != "minecraft:air" or mode != "replace" or filt not in CLEAR_FILTERS:
                clears.append("fill %s is not an air clear of %s" % (f, sorted(CLEAR_FILTERS)))
            for x in range(x0, x1 + 1):
                for z in range(z0, z1 + 1):
                    if not inside(x, z):
                        sq.append("fill column (%d, %d) is outside the site square" % (x, z))
                    if g(x, z) < sea:
                        dry.append("fill column (%d, %d) on water (ground y%d)" % (x, z, g(x, z)))
                    # a filtered clear may start AT the ground block (its filter cannot take dirt or stone, and it
                    # catches a plant where the world's ground is one lower than round(h)), never under it
                    if y0 < g(x, z) or (y0 == g(x, z) and filt not in CLEAR_FILTERS):
                        above.append("fill from y%d at (%d, %d) reaches into the ground (y%d)" % (y0, x, z, g(x, z)))
        if other and any(not c.startswith("forceload") for c in other):
            clears.append("build has commands other than setblock/fill/forceload: %s"
                          % [c for c in other if not c.startswith("forceload")][:3])
        self.check("station_square", sq)
        self.check("station_dry", dry)
        self.check("station_above", above)
        self.check("station_clears", clears)
        self.check("station_blocks", self.block_problems([s for *_xyz, s in sets if block_id(s) != "minecraft:air"],
                                                         d["blocks"]["ids"], "station"))
        self.floors_check(sets)
        fl = []
        for rel in ("build", "instruments", "portal/build"):
            fl += forceload_problems(rel, commands(self.fn(rel)))
        self.check("forceload", fl)

    def block_problems(self, states, allowed, what):
        probs = []
        spawn = self.I.spawn_blocks["blocks"]
        white = {b for w in self.I.policy.get("whitelist", []) for b in w.get("blocks", [])}
        subst = {s["from"] for s in self.I.policy.get("substitutions", [])}
        for b in sorted({block_id(s) for s in states}):
            if allowed is not None and b not in allowed:
                probs.append("%s writes %s, not in its declared block list" % (what, b))
            if b in subst:
                probs.append("%s writes %s, which data/spawn_block_policy.json substitutes" % (what, b))
            if b in spawn:
                if b in white:
                    self.notes.append("%s writes %s, a spawn condition whitelisted by data/spawn_block_policy.json"
                                      % (what, b))
                else:
                    probs.append("%s writes %s, a spawn condition (data/spawn_blocks.json)" % (what, b))
        return probs

    def floors_check(self, sets):
        """Attribute each written column to the nearest top-level piece; its floor is max(ground)+1 over them."""
        d, g = self.d, self.g
        found = d["blocks"]["foundation"]
        tops = [p for p in d["pieces"] if "on" not in p]
        cols = {}
        for x, y, z, s in sets:
            cols.setdefault((x, z), []).append((y, s))
        owner, probs = {}, []
        for c in cols:
            ds = sorted((max(abs(c[0] - p["at"][0]), abs(c[1] - p["at"][1])), p["id"]) for p in tops)
            if len(ds) > 1 and ds[0][0] == ds[1][0]:
                probs.append("column %s is as near %s as %s: cannot attribute it" % (c, ds[0][1], ds[1][1]))
            owner[c] = ds[0][1]
        self.owner = owner
        self.cols = cols
        self.floor = {}
        for p in tops:
            mine = [c for c in cols if owner[c] == p["id"]]
            if not mine:
                probs.append("%s writes no block" % p["id"])
                continue
            F = max(g(*c) for c in mine) + 1
            self.floor[p["id"]] = F
            low = min(y for c in mine for y, s in cols[c] if block_id(s) != found)
            if low != F:
                probs.append("%s: its lowest non-foundation block is at y%d, its floor from the heightmap is y%d "
                             "(max ground %d + 1)" % (p["id"], low, F, F - 1))
            for c in mine:
                ys = {y: block_id(s) for y, s in cols[c]}
                for y, b in ys.items():
                    if y < F and b != found:
                        probs.append("%s: %s at %s y%d is under the floor y%d" % (p["id"], b, c, y, F))
                if any(y >= F for y in ys):
                    need = set(range(g(*c) + 1, F))
                    have = {y for y, b in ys.items() if y < F and b == found}
                    if need - have:
                        probs.append("%s: foundation at %s missing y%s (ground %d, floor %d)"
                                     % (p["id"], c, sorted(need - have), g(*c), F))
                    if have - need:
                        probs.append("%s: foundation at %s at y%s, outside ground+1..floor-1"
                                     % (p["id"], c, sorted(have - need)))
        for p in d["pieces"]:
            if "on" in p and p["on"] not in self.floor:
                probs.append("%s sits on %s, which has no floor" % (p["id"], p["on"]))
        self.check("station_floors", probs)

    # ---------------------------------------------------------------- numbers, recomputed
    def numbers(self):
        d, I = self.d, self.I
        pieces = {p["id"]: p for p in d["pieces"]}
        out, self.aims = {}, {}
        ax, az = d["portal"]["site"]["at"]
        apron_y = max(self.g(ax + i, az + k) for i in range(-2, 3) for k in range(-2, 3))
        self.apron_y = apron_y
        for p in d["pieces"]:
            if p.get("kind") != "instrument":
                continue
            host = pieces[p["on"]]["id"]
            x, z = p["at"]
            pivot = (x + 0.5, self.floor.get(host, 0) + PIVOT_ABOVE_FLOOR, z + 0.5)
            if p["target"] == "arch_buoy":
                aim = (ax + 0.5, I.sea + 1 + 0.5, az + 0.5)
                pre = "arch"
                out["arch_depth"] = "%d" % (I.sea - apron_y)
            elif p["target"] == "landing":
                fx, fy, fz = I.dock(d["ferry"]["far_dock"])["ferryman"]["at"]
                aim = (fx + 0.5, fy + 1.6, fz + 0.5)
                pre = "landing"
            else:
                raise SystemExit("coldwater_station_audit: unknown target %r" % p["target"])
            self.aims[p["id"]] = (pivot, aim)
            out[pre + "_bearing"] = "%03d" % round(bearing(aim[0] - pivot[0], aim[2] - pivot[2]))
            out[pre + "_range"] = "%d" % (round(math.hypot(aim[0] - pivot[0], aim[2] - pivot[2]) / 10) * 10)
        line = I.line(d["ferry"]["line"])
        out["fare"] = "%d" % line["fare"]
        out["gate"] = " and ".join(gt["says"] for gt in line.get("gates", []))
        self.nums = out
        return out

    @staticmethod
    def fill_text(t, nums):
        return re.sub(r"\{([a-z_]+)\}", lambda m: nums.get(m.group(1), m.group(0)), t)

    # ---------------------------------------------------------------- NPCs, dialogue, signs
    def npcs(self):
        d, g = self.d, self.g
        steps = (self.pack / "steps.txt").read_text(encoding="utf-8").splitlines()
        spawn = {}
        for s in steps:
            m = re.match(r"spawnnpcat (-?\d+) (-?\d+) (-?\d+) (\S+)$", s.strip())
            if m:
                spawn.setdefault(m.group(4), []).append(tuple(int(v) for v in m.group(1, 2, 3)))
        pieces = {p["id"]: p for p in d["pieces"]}
        world = {}
        for x, y, z, s in self.sets:
            world[(x, y, z)] = s
        probs = []
        for r in d["researchers"]:
            cls = "cobblers:npc_%s" % r["id"]
            got = spawn.pop(cls, [])
            if len(got) != 1:
                probs.append("%s: %d spawnnpcat lines (want 1)" % (r["id"], len(got)))
                continue
            x, y, z = got[0]
            host = r.get("on") or r.get("in")
            if "at" in r:
                want = tuple(r["at"])
            elif r.get("at_local") == [0, 0]:
                want = tuple(pieces[host]["at"])
            else:
                probs.append("%s: at_local %s is not one this audit can turn; not checked" % (r["id"], r.get("at_local")))
                continue
            if (x, z) != want:
                probs.append("%s spawns at (%d, %d), authored (%d, %d)" % ((r["id"], x, z) + want))
            F = self.floor.get(host)
            if F is None or y != F + 1:
                probs.append("%s spawns at y%d; its host %s's floor is y%s, so y%s" % (r["id"], y, host, F,
                                                                                  None if F is None else F + 1))
            if self.owner.get((x, z)) != host:
                probs.append("%s stands on (%d, %d), a column %s writes, not its host %s"
                             % (r["id"], x, z, self.owner.get((x, z)), host))
            under = world.get((x, y - 1, z))
            if under is None or not block_id(under).endswith(FULL_SUFFIX) or "type=bottom" in under \
                    or "type=top" in under:
                probs.append("%s at (%d, %d, %d) stands on %s, not a full block" % (r["id"], x, y, z, under))
            for dy, ok in ((0, ("minecraft:air", "_carpet")), (1, ("minecraft:air",))):
                cell = world.get((x, y + dy, z))
                if (cell is not None and not block_id(cell).endswith(ok)) or y + dy <= g(x, z):
                    probs.append("%s at (%d, %d, %d): y%d is %s, not air" % (r["id"], x, y, z, y + dy,
                                                                          cell or "ground"))
        for cls, at in spawn.items():
            probs.append("steps.txt spawns %s at %s, which no researcher authors" % (cls, at))
        self.check("npcs", probs)

        probs = []
        for r in d["researchers"]:
            f = self.pack / "data" / "cobblers" / "npcs" / ("npc_%s.json" % r["id"])
            if not f.exists():
                probs.append("%s: no NPC class %s" % (r["id"], f.name))
                continue
            c = json.loads(f.read_text(encoding="utf-8"))
            if c.get("names") != [r["name"]]:
                probs.append("%s: class names %s, authored %r" % (r["id"], c.get("names"), r["name"]))
            dlg = (c.get("interaction") or {}).get("dialogue", "")
            if dlg != "cobblers:dlg_%s" % r["id"] or not (self.pack / "data" / "cobblers" / "dialogues" /
                                                          ("dlg_%s.json" % r["id"])).exists():
                probs.append("%s: dialogue %r is not one the pack ships" % (r["id"], dlg))
        self.check("npc_classes", probs)

    def dialogue(self):
        nums = self.nums
        fields = {f["id"]: f for f in self.I.progression["quest_fields"]}
        probs = []
        for r in self.d["researchers"]:
            f = self.pack / "data" / "cobblers" / "dialogues" / ("dlg_%s.json" % r["id"])
            if not f.exists():
                probs.append("%s: no dialogue file" % r["id"])
                continue
            raw = f.read_text(encoding="utf-8")
            dj = json.loads(raw)
            texts = []
            pages = {p["id"] for p in dj.get("pages", [])}
            actions = [dj.get("initializationAction", "")]
            for p in dj.get("pages", []):
                texts += p.get("lines", [])
                inp = p.get("input")
                if isinstance(inp, str):            # a page that runs one action on continue
                    actions.append(inp)
                    continue
                for o in (inp or {}).get("options", []):
                    texts.append(o.get("text", ""))
                    actions.append(o.get("action", ""))
            want = [r["greeting"], r["leave"]] + [t["ask"] for t in r["topics"]] + [t["says"] for t in r["topics"]]
            for w in want:
                t = self.fill_text(w, nums)
                if t not in texts:
                    probs.append("%s: authored line %r, with the recomputed numbers, is not in the dialogue"
                                 % (r["id"], t[:70]))
            for t in texts:
                if re.search(r"\{[a-z_]+\}", t):
                    probs.append("%s: placeholder left in %r" % (r["id"], t[:70]))
            for a in actions:
                if re.search(r"command|give|teleport|\.tp\b|add_tag|tag\(", a):
                    probs.append("%s: an action does more than talk: %r" % (r["id"], a[:90]))
                for fld, val in re.findall(r"t\.d\.(\w+)\s*=\s*'([^']*)'", a):
                    m = re.match(r"cobblers__(.+)$", fld)
                    fid = m.group(1).replace("__", ".") if m else fld
                    fd = fields.get(fid)
                    if fd is None or fd.get("quest_id") != "coldwater_station":
                        probs.append("%s: sets %s, not a declared coldwater_station quest field" % (r["id"], fld))
                    elif val not in pages:
                        probs.append("%s: sets %s to %r, not a page of its dialogue" % (r["id"], fld, val))
        self.check("dialogue", probs)

    def signs(self):
        want = sorted(tuple(self.fill_text(t, self.nums) for t in s) for s in self.d["notes_board"]["signs"])
        got = []
        for x, y, z, s in self.sets:
            if "_sign" in block_id(s):
                m = re.search(r"messages:\[(.*)\]", s)
                lines = re.findall(r"'\"((?:[^\"\\]|\\.)*)\"'", m.group(1)) if m else []
                got.append(tuple(l.replace("\\'", "'") for l in lines))
        probs = []
        if sorted(got) != want:
            probs.append("sign texts %s differ from the authored ones with the recomputed numbers %s"
                         % (sorted(set(got) - set(want)), sorted(set(want) - set(got))))
        self.check("signs", probs)

    # ---------------------------------------------------------------- instruments
    def instruments(self):
        cmds = commands(self.fn("instruments"))
        probs = []
        disp = []
        killed = False
        for _i, c in cmds:
            if c.startswith("kill @e[type=minecraft:block_display,tag=%s" % STATION_TAG):
                killed = True
            if c.startswith("summon minecraft:block_display"):
                if not killed:
                    probs.append("a display is summoned before this station's old displays are killed")
                disp.append(c)
        inst = [p for p in self.d["pieces"] if p.get("kind") == "instrument"]
        if len(disp) != len(inst):
            probs.append("%d displays for %d instruments" % (len(disp), len(inst)))
        fnum = r"(-?[\d.]+)f?"
        for p in inst:
            mine = [c for c in disp if '"%s"' % p["id"] in c and '"%s"' % STATION_TAG in c]
            if len(mine) != 1:
                probs.append("%s: %d displays tagged with it" % (p["id"], len(mine)))
                continue
            c = mine[0]
            pos = [float(v) for v in re.match(r"summon \S+ (\S+) (\S+) (\S+)", c).groups()]
            name = re.search(r'Name:"([^"]+)"', c).group(1)
            vec = lambda key: [float(v) for v in re.findall(fnum, re.search(key + r":\[([^\]]*)\]", c).group(1))]  # noqa
            q, t, s = vec("left_rotation"), vec("translation"), vec("scale")
            right = vec("right_rotation")
            tube = p["tube"]
            pivot, aim = self.aims[p["id"]]
            if name != tube["block"]:
                probs.append("%s: tube block %s, authored %s" % (p["id"], name, tube["block"]))
            if any(abs(a - b) > 1e-3 for a, b in zip(s, (tube["width"], tube["width"], tube["length"]))):
                probs.append("%s: scale %s, authored width %s length %s" % (p["id"], s, tube["width"], tube["length"]))
            if any(abs(a - b) > 0.006 for a, b in zip(pos, pivot)):
                probs.append("%s: pivot %s, recomputed %s (its host's floor + %.1f)" % (p["id"], pos,
                                                                                         [round(v, 2) for v in pivot],
                                                                                         PIVOT_ABOVE_FLOOR))
            if any(abs(a - b) > 1e-4 for a, b in zip(right, (0, 0, 0, 1))):
                probs.append("%s: right_rotation %s is not the identity" % (p["id"], right))
            norm = math.sqrt(sum(v * v for v in q))
            if abs(norm - 1) > 2e-3:
                probs.append("%s: left_rotation norm %.4f" % (p["id"], norm))
            dv = [aim[k] - pivot[k] for k in range(3)]
            n = math.sqrt(sum(v * v for v in dv))
            dv = [v / n for v in dv]
            got = qrot([v / norm for v in q], [0, 0, 1])
            err = max(abs(a - b) for a, b in zip(got, dv))
            if err > 1e-3:
                probs.append("%s: the tube points %s, the target %s is at %s from the pivot (off by %.4f)"
                             % (p["id"], [round(v, 4) for v in got], p["target"], [round(v, 4) for v in dv], err))
            # the tube's axis, (w/2, w/2, L*u) scaled, rotated and translated, must pass through the pivot (0, 0, 0)
            w, L = s[0], s[2]
            a0 = [t[k] + v for k, v in enumerate(qrot([v / norm for v in q], [w / 2, w / 2, 0]))]
            ax = qrot([v / norm for v in q], [0, 0, L])
            al = math.sqrt(sum(v * v for v in ax)) or 1
            proj = -sum(a0[k] * ax[k] for k in range(3)) / (al * al)
            closest = [a0[k] + proj * ax[k] for k in range(3)]
            off = math.sqrt(sum(v * v for v in closest))
            if off > 0.02 or not 0 <= proj <= 1:
                probs.append("%s: the tube's axis misses the pivot by %.3f (at %.2f of its length)" % (p["id"], off, proj))
            if p["target"] == "arch_buoy":
                hit = self.sight_blocked(pivot, aim)
                if hit:
                    probs.append("%s: the sight line to the buoy lantern is blocked at %s" % (p["id"], hit))
        self.check("instruments", probs)

    def sight_blocked(self, a, b, step=0.02, skip=1.0):
        solid = {(x, y, z) for x, y, z, s in self.sets if block_id(s) != "minecraft:air"}
        n = math.dist(a, b)
        k = int(n / step)
        for i in range(k + 1):
            t = i * step
            if t < skip or t > n - 0.5:
                continue
            p = [a[j] + (b[j] - a[j]) * t / n for j in range(3)]
            c = (math.floor(p[0]), math.floor(p[1]), math.floor(p[2]))
            if c[1] <= self.g(c[0], c[2]) or c in solid:
                return c
        return None

    # ---------------------------------------------------------------- the arch
    def arch_expected(self):
        """{(x, y, z): block} from data/portals.json's dive palette and the docstring geometry, on round(ground)."""
        P = self.I.portals
        pal = P["blocks"]["dive"]
        site = self.d["portal"]["site"]
        ax, az = site["at"]
        fx, fz = FACING[site["facing"]]
        rx, rz = -fz, fx                    # along the arch, perpendicular to the facing
        ay = self.apron_y
        out = {}
        for i in range(-2, 3):
            for k in range(-2, 3):
                x, z = ax + i, az + k
                for y in range(self.g(x, z) + 1, ay):
                    out[(x, y, z)] = pal["apron"]
                out[(x, ay, z)] = pal["apron"]
        for r in range(-2, 3):
            x, z = ax + r * rx, az + r * rz
            for dy in (1, 2, 3):
                out[(x, ay + dy, z)] = pal["frame"] if abs(r) == 2 else pal["sheet"]
            out[(x, ay + 4, z)] = pal["lamp"] if abs(r) == 2 else pal["frame"]
        buoy = self.d["portal"]["buoy"]
        out[(ax, self.I.sea, az)] = buoy["float"]
        out[(ax, self.I.sea + 1, az)] = buoy["light"]
        return out

    def arch(self):
        I, d, g = self.I, self.d, self.g
        P = I.portals
        rules = P["rules"]
        site = d["portal"]["site"]
        ax, az = site["at"]
        cmds = commands(self.fn("portal/build"))
        sets, fills, other = parse_writes(cmds)
        built = {}
        for f in fills:
            if f[7] is not None:
                built.setdefault("_bad", []).append(f)
            for x in range(f[0], f[3] + 1):
                for y in range(f[1], f[4] + 1):
                    for z in range(f[2], f[5] + 1):
                        built[(x, y, z)] = f[6]
        for x, y, z, s in sets:
            built[(x, y, z)] = s
        bad = built.pop("_bad", [])
        self.arch_built = built
        want = self.arch_expected()
        probs = ["portal/build: a filtered fill %s" % (f,) for f in bad]
        for c, b in sorted(want.items()):
            if built.get(c) != b:
                probs.append("arch: %s should be %s, built %s" % (c, b, built.get(c)))
                if len(probs) > 12:
                    break
        extra = sorted(set(built) - set(want))
        if extra:
            probs.append("arch: %d writes the geometry does not have, first %s %s" % (len(extra), extra[0],
                                                                                     built[extra[0]]))
        probs += self.block_problems(list(built.values()), None, "portal/build")
        self.check("arch_geometry", probs)

        probs = []
        cols = [(ax + i, az + k) for i in range(-2, 3) for k in range(-2, 3)]
        gs = [g(*c) for c in cols]
        if max(gs) - min(gs) > rules["max_relief"]:
            probs.append("apron relief %d > %d" % (max(gs) - min(gs), rules["max_relief"]))
        for c, h in zip(cols, gs):
            if I.sea - h < rules["min_submersion"]:
                probs.append("apron column %s is %d under the sea (min %d)" % (c, I.sea - h, rules["min_submersion"]))
        if self.apron_y + 4 > I.sea - rules["min_water_above"]:
            probs.append("lintel top y%d is above sea %d - %d" % (self.apron_y + 4, I.sea, rules["min_water_above"]))
        for p in P["portals"]:
            dd = math.hypot(p["at"][0] - ax, p["at"][1] - az)
            if dd < rules["min_between_portals"]:
                probs.append("%.0f from portal %s (min %d)" % (dd, p["id"], rules["min_between_portals"]))
            if p["id"] == d["portal"]["id"]:
                probs.append("data/portals.json also carries %s" % p["id"])
        mt = rules["min_from_town_footprint"]["dive"]
        for t in I.towns.get("towns", []):
            fp = t.get("footprint") or {}
            if all(k in fp for k in ("min_x", "min_z", "max_x", "max_z")):
                dd = box_dist(ax, az, (fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"]))
                if dd < mt:
                    probs.append("%.0f from town %s's footprint (min %d)" % (dd, t.get("id"), mt))
        mp = rules["min_from_placement"]["dive"]
        for p in I.placements["placements"]:
            pos = p.get("position") or {}
            if "x" in pos and "z" in pos:
                dd = math.hypot(pos["x"] - ax, pos["z"] - az)
                if dd < mp:
                    probs.append("%.0f from placement %s (min %d)" % (dd, p["id"], mp))
        ml = rules["min_from_legendary_mouth"]
        for e in I.legendaries["encounters"]:
            if e.get("mouth"):
                dd = math.hypot(e["mouth"][0] - ax, e["mouth"][1] - az)
                if dd < ml:
                    probs.append("%.0f from %s's mouth (min %d)" % (dd, e["id"], ml))
        self.check("arch_rules", probs)
        self.click()

    def click(self):
        I, d = self.I, self.d
        hook = d["portal"]["hook"]
        tag = hook["click_tag"]
        site = d["portal"]["site"]
        ax, az = site["at"]
        fx, fz = FACING[site["facing"]]
        probs = []
        cmds = [c for _i, c in commands(self.fn("portal/build"))]
        summ = [c for c in cmds if c.startswith("summon minecraft:interaction")]
        if len(summ) != 1:
            probs.append("portal/build summons %d interactions (want 1)" % len(summ))
        self.click_cell = None
        for c in summ:
            x, y, z = (float(v) for v in re.match(r"summon \S+ (\S+) (\S+) (\S+)", c).groups())
            self.click_cell = (math.floor(x), math.floor(y), math.floor(z))
            want = (ax + fx + 0.5, self.apron_y + 1, az + fz + 0.5)
            if max(abs(a - b) for a, b in zip((x, y, z), want)) > 1e-6:
                probs.append("the click box is at %s, in front of the sheet is %s" % ((x, y, z), want))
            if '"%s"' % tag not in c:
                probs.append("the click box is not tagged %s" % tag)
            if cmds.index(c) < next((i for i, k in enumerate(cmds) if k.startswith("kill @e[type=minecraft:interaction,"
                                                                                  "tag=%s" % tag)), 10 ** 9):
                probs.append("the click box is summoned before its stale copies are killed")
        advp = self.pack / "data" / "cobblers" / "advancement" / "coldwater_station" / "portal_touch.json"
        adv_id = "cobblers:coldwater_station/portal_touch"
        if not advp.exists():
            probs.append("no advancement %s" % adv_id)
        else:
            adv = json.loads(advp.read_text(encoding="utf-8"))
            crit = list(adv.get("criteria", {}).values())
            ok = len(crit) == 1 and crit[0].get("trigger") == "minecraft:player_interacted_with_entity"
            ent = crit[0].get("conditions", {}).get("entity", []) if crit else []
            pred = ent[0].get("predicate", {}) if ent else {}
            if not ok or pred.get("type") != "minecraft:interaction" or '\\"%s\\"' % tag not in json.dumps(pred):
                probs.append("the advancement does not fire on an interaction tagged %s" % tag)
            if adv.get("rewards", {}).get("function") != hook["touch_function"]:
                probs.append("the advancement runs %s, the hook's touch is %s"
                             % (adv.get("rewards", {}).get("function"), hook["touch_function"]))
        touch = [c for _i, c in commands(self.fn("portal/touch"))]
        dive = I.portals["gates"]["dive"]
        dest = "function %s" % hook["destination_function"]
        if not touch or touch[0] != "advancement revoke @s only %s" % adv_id:
            probs.append("touch does not revoke %s first" % adv_id)
        gate_t = "execute unless entity @s[tag=%s] run tellraw @s " % dive["tag"]
        gate_r = "execute unless entity @s[tag=%s] run return 0" % dive["tag"]
        it = [i for i, c in enumerate(touch) if c.startswith(gate_t)]
        ir = [i for i, c in enumerate(touch) if c == gate_r]
        idest = [i for i, c in enumerate(touch) if c == dest]
        if len(it) != 1 or json.loads(touch[it[0]][len(gate_t):]).get("text") != dive["locked_message"]:
            probs.append("touch does not tell a non-diver data/portals.json gates.dive.locked_message")
        if len(ir) != 1 or len(idest) != 1 or not (it and it[0] < ir[0] < idest[0]):
            probs.append("touch does not refuse a non-diver (return) before calling the destination")
        for c in touch:
            if c.startswith("advancement revoke") or c == dest or c in (gate_r,) or c.startswith(gate_t):
                continue
            if re.fullmatch(r"execute as @e\[type=minecraft:interaction,tag=%s[^\]]*\] run data remove entity @s "
                            r"interaction" % re.escape(tag), c):
                continue
            probs.append("touch does something else: %r" % c[:90])
        stub = [c for _i, c in commands(self.fn("portal/destination"))]
        for c in stub:
            if c.split()[0] not in STUB_ALLOWED:       # an execute (in/as/run ...), tp, scoreboard, tag, give ...
                probs.append("destination is not a stub: %r" % c[:90])
        if not any(c.startswith("tellraw") and hook["sealed_message"] in c for c in stub):
            probs.append("destination does not say portal.hook.sealed_message")
        # nothing else in the pack reaches the destination
        for f in sorted(self.pack.rglob("*.mcfunction")):
            if f.name == "touch.mcfunction":
                continue
            if hook["destination_function"] in f.read_text(encoding="utf-8"):
                probs.append("%s calls the destination" % f.relative_to(self.pack))
        self.check("arch_click", probs)

    # ---------------------------------------------------------------- the lane and the sea packs
    def lane(self):
        I, d = self.I, self.d
        line = I.line(d["ferry"]["line"])
        probs = []
        if line.get("retired"):
            probs.append("%s is retired: sea_life no longer keeps its lane" % line["id"])
        stops = line["stops"]
        H = I.sea_life["exclusions"]["ferry_lane_half_width_blocks"]
        a = I.dock(stops[0])["landing"]["at"]
        b = I.dock(stops[-1])["landing"]["at"]
        if len(stops) != 2:
            probs.append("%s has %d stops; this audit measures the two-stop lane" % (line["id"], len(stops)))
        cols = {(x, z) for (x, _y, z) in self.arch_built}
        grown = {(x + i, z + k) for x, z in cols for i in range(-SEA_MARGIN, SEA_MARGIN + 1)
                 for k in range(-SEA_MARGIN, SEA_MARGIN + 1)}
        if self.click_cell:
            grown.add((self.click_cell[0], self.click_cell[2]))
        worst = max(((seg_dist(c, (a[0], a[2]), (b[0], b[2])), c) for c in grown), default=(0, None))
        self.notes.append("lane: the arch's farthest column (grown by %d) is %.1f from the line (half width %d)"
                          % (SEA_MARGIN, worst[0], H))
        if worst[0] > H:
            probs.append("arch column %s is %.1f from the %s line, outside the lane's half width %d"
                         % (worst[1], worst[0], line["id"], H))
        self.check("lane", probs)

        probs = []
        if not self.arch_built:
            self.check("sea_packs", ["no arch built to protect"])
            return
        xs = [c[0] for c in self.arch_built]
        ys = [c[1] for c in self.arch_built]
        zs = [c[2] for c in self.arch_built]
        box = (min(xs) - SEA_MARGIN, min(ys) - SEA_MARGIN, min(zs) - SEA_MARGIN,
               max(xs) + SEA_MARGIN, max(ys) + SEA_MARGIN, max(zs) + SEA_MARGIN)
        ran = []
        for name in ("cobblers_sea_life", "cobblers_sea_floor"):
            root = (self.sea_root or ROOT) / "build" / "datapacks" / name
            if not root.exists():
                self.notes.append("sea_packs: %s is not built under %s: NOT RUN for it (needs a full checkout's "
                                  "prepare)" % (name, root.parent))
                if self.require_sea:
                    probs.append("%s is absent and --require-sea was given" % name)
                continue
            ran.append(name)
            for f in sorted(root.rglob("*.mcfunction")):
                for x0, y0, z0, x1, y1, z1, blk in self.writes_boxes(f):
                    if x0 <= box[3] and x1 >= box[0] and y0 <= box[4] and y1 >= box[1] and z0 <= box[5] and z1 >= box[2]:
                        probs.append("%s %s writes %s over x%d-%d y%d-%d z%d-%d, within %d of the arch"
                                     % (name, f.name, blk, x0, x1, y0, y1, z0, z1, SEA_MARGIN))
                        break
        if ran:
            self.notes.append("sea_packs: checked %s" % ", ".join(ran))
        self.check("sea_packs", probs)

    @staticmethod
    def writes_boxes(path):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            m = re.search(r"(?:^|run )setblock (-?\d+) (-?\d+) (-?\d+) (\S+)", s)
            if m:
                x, y, z = (int(v) for v in m.group(1, 2, 3))
                yield (x, y, z, x, y, z, block_id(m.group(4)))
                continue
            m = re.search(r"(?:^|run )fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)", s)
            if m:
                v = [int(t) for t in m.group(1, 2, 3, 4, 5, 6)]
                yield (min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]),
                       max(v[2], v[5]), block_id(m.group(7)))

    # ---------------------------------------------------------------- the ferry and the clearances
    def ferry(self):
        I, d = self.I, self.d
        probs = []
        f = d["ferry"]
        line = I.line(f["line"])
        if line["stops"] != [f["dock"], f["far_dock"]]:
            probs.append("%s stops %s, authored %s -> %s" % (line["id"], line["stops"], f["dock"], f["far_dock"]))
        packets = [l for l in I.ferries["lines"] if f["far_dock"] in l["stops"] and l["id"] != line["id"]
                   and not l.get("retired")]
        if not packets:
            probs.append("no other line serves %s to compare the fare and gate with" % f["far_dock"])
        for pk in packets:
            if pk["fare"] != line["fare"]:
                probs.append("%s fare %s, %s's is %s" % (line["id"], line["fare"], pk["id"], pk["fare"]))
            gk = lambda l: sorted((gt.get("kind"), gt.get("flag")) for gt in l.get("gates", []))   # noqa: E731
            if gk(pk) != gk(line):
                probs.append("%s gates %s, %s's are %s" % (line["id"], gk(line), pk["id"], gk(pk)))
        fd = [x for x in I.ferry_docks.get("docks", []) if x.get("id") == f["dock"]]
        if len(fd) != 1:
            probs.append("data/ferry_docks.json has %d records for %s" % (len(fd), f["dock"]))
        elif fd[0].get("shore", {}).get("at") != I.dock(f["dock"]).get("near"):
            probs.append("data/ferry_docks.json shore %s, data/ferries.json near %s"
                         % (fd[0].get("shore", {}).get("at"), I.dock(f["dock"]).get("near")))
        if f["dock"] not in I.id_authorship:
            probs.append("data/id_authorship.json does not declare %s, which two data files carry" % f["dock"])
        self.check("ferry", probs)

        rules = d["rules"]
        jetty = I.dock(f["dock"])
        cols = set(self.cols)
        probs = []
        dc = rules["dock_clearance"]
        for c in sorted(cols):
            for box in jetty.get("keep_clear", []):
                if box_dist(c[0], c[1], box) < dc:
                    probs.append("station column %s is %.1f from the jetty keep_clear %s (min %d)"
                                 % (c, box_dist(c[0], c[1], box), box, dc))
            for who in ("ferryman", "landing"):
                x, _y, z = jetty[who]["at"]
                if math.hypot(c[0] - x, c[1] - z) < dc:
                    probs.append("station column %s is %.1f from the jetty %s (min %d)"
                                 % (c, math.hypot(c[0] - x, c[1] - z), who, dc))
        self.check("dock_clearance", probs)

        ac = rules["authored_clearance"]
        probs = []
        excl = {f["dock"], f["line"]}
        pts, boxes, polys = authored_things(I.root, excl)
        for c in sorted(cols):
            for src, x, z in pts:
                if math.hypot(c[0] - x, c[1] - z) < ac:
                    probs.append("station column %s is %.1f from %s (%d, %d) (min %d)"
                                 % (c, math.hypot(c[0] - x, c[1] - z), src, x, z, ac))
            for src, b in boxes:
                if box_dist(c[0], c[1], b) < ac:
                    probs.append("station column %s is %.1f from %s %s (min %d)" % (c, box_dist(c[0], c[1], b), src,
                                                                                   b, ac))
            for src, poly in polys:
                if in_polygon(c[0], c[1], poly):
                    probs.append("station column %s is inside %s" % (c, src))
        seen, uniq = set(), []
        for p in probs:                         # one line per source
            key = p.split(" from ")[-1] if " from " in p else p.split(" inside ")[-1]
            if key not in seen:
                seen.add(key)
                uniq.append(p)
        self.check("authored_clearance", uniq)

    def run(self):
        self.station()
        self.numbers()
        self.npcs()
        self.dialogue()
        self.signs()
        self.instruments()
        self.arch()
        self.lane()
        self.ferry()
        return self


BOX_KEYS = {"rect", "bbox", "box", "spawn_free_zone", "keep_clear", "bounds", "footprint", "area", "zone", "extent"}


def authored_things(root, exclude_ids):
    """(points, boxes, polygons) every other data/*.json authors, each with its source path."""
    pts, boxes, polys = [], [], []

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def walk(o, path, fname, key=None):
        if isinstance(o, dict):
            if o.get("id") in exclude_ids:
                return
            if num(o.get("x")) and num(o.get("z")):
                pts.append(("%s %s" % (fname, path), o["x"], o["z"]))
            if all(num(o.get(k)) for k in ("min_x", "min_z", "max_x", "max_z")):
                boxes.append(("%s %s" % (fname, path), (o["min_x"], o["min_z"], o["max_x"], o["max_z"])))
            xs, zs = o.get("x"), o.get("z")
            if isinstance(xs, list) and isinstance(zs, list) and len(xs) == 2 and len(zs) == 2 \
                    and all(num(v) for v in xs + zs):
                boxes.append(("%s %s" % (fname, path), (xs[0], zs[0], xs[1], zs[1])))
            for k, v in o.items():
                if fname == "regions.json" and k in ("polygons", "polygon"):
                    continue                    # region boundaries follow terrain; they are not things
                if k in ("polygons", "polygon"):
                    for poly in _polys(v):
                        polys.append(("%s %s/%s" % (fname, path, k), poly))
                walk(v, "%s/%s" % (path, k), fname, k)
        elif isinstance(o, list):
            if 2 <= len(o) <= 3 and all(num(v) for v in o):
                pts.append(("%s %s" % (fname, path), o[0], o[-1]))
            elif len(o) == 4 and all(num(v) for v in o) and key in BOX_KEYS:
                boxes.append(("%s %s" % (fname, path), tuple(o)))
            else:
                for i, v in enumerate(o):
                    walk(v, "%s/%d" % (path, i), fname, key)

    for f in sorted(glob.glob(str(Path(root) / "data" / "*.json"))):
        name = Path(f).name
        if name in ("coldwater_station.json", "cells.json", "regions.json", "world.json"):
            continue        # itself; cells are planning labels, regions boundaries, world.json the world's extents
        try:
            doc = json.loads(Path(f).read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        walk(doc, "", name)
    return pts, boxes, polys


def _polys(v):
    """A polygon is a list of >= 3 [x, z] pairs; a key may hold one or a list of them."""
    if isinstance(v, list) and len(v) >= 3 and all(isinstance(p, list) and len(p) in (2, 3) and
                                                   all(isinstance(c, (int, float)) for c in p) for p in v):
        return [v]
    out = []
    if isinstance(v, list):
        for p in v:
            out += _polys(p)
    return out


def report(audit):
    lines = []
    bad = 0
    for name, probs in audit.results:
        if probs:
            bad += len(probs)
            lines.append("FAIL %-19s %d problem(s)" % (name, len(probs)))
            lines += ["  PROBLEM %s" % p for p in probs]
        else:
            lines.append("ok   %s" % name)
    lines += ["  NOTE %s" % n for n in audit.notes]
    lines.append("coldwater_station_audit: %d checks, %d failed, %d problems"
                 % (len(audit.results), sum(1 for _n, p in audit.results if p), bad))
    return "\n".join(lines), bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--inputs-root", help="a checkout holding build/datapacks/cobblers_sea_life and cobblers_sea_floor")
    ap.add_argument("--source-root")
    ap.add_argument("--require-sea", action="store_true", help="fail when the sea packs are not built")
    a = ap.parse_args(argv)
    if not (Path(a.pack) / FN / "build.mcfunction").exists():
        print("coldwater_station_audit: no built pack at %s (run tools/coldwater_station.py build)" % a.pack)
        return 2
    import ground as G
    g = G.load(a.source_root)
    text, bad = report(Audit(Inputs(), a.pack, g, a.inputs_root, a.require_sea).run())
    print(text)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
