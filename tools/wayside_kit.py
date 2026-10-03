#!/usr/bin/env python
"""Shared pieces of the three southern wayside places of 2026-10-03: the Challengers' Cairn (tools/challengers_cairn.py),
the Dry Cistern (tools/dry_cistern.py) and the Surveyors' Benchmark (tools/survey_benchmark.py).

Nothing here is new machinery. Every piece is the Drovers' Hollow's (tools/drovers_hollow.py), lifted so that three
small places do not carry three copies of it:

  Plan              two passes of blocks, the structure then what hangs on it, each block checked against the record's
                    own `blocks.ids` (the generator refuses anything else).
  palette guard     a record's `blocks.ids` may hold no Cobblemon spawn condition (data/spawn_blocks.json) unless a
                    data/spawn_block_policy.json entry whose scope names the place allows it, and no chest (a Gimmighoul
                    condition, tools/portals_audit.py) or bed (a respawn point, which the blackout owns). Checked when a
                    record loads, so a bad palette fails the generator before a block is planned.
  shell_then_void   the Ursaluna den's carve (tools/ursaluna_cave.py): a shell filled SOLID `margin` blocks beyond every
                    void block, never in the top `keep` blocks of a column, then the void cut out of it.
  stair_passage     a rock-cut stair from a chamber up to the ground: roofed while it has two or more blocks of ground
                    over it, an open trench between dressed walls after that, a dressed face over the mouth.
  runs / build      setblock and fill lines, the structure bottom up and what hangs top down (tools/drovers_hollow.py).
  sightline         the least clearance of a standing eye's line to a point over the heightmap (tools/drovers_hollow.py).

Ground is tools/ground.py's (the canonical heightmap, rounded), passed in as `g`. Nothing here reads a world.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK_FORMAT = 48  # Minecraft 1.21.1
NS = "cobblers"
CLEAR_MARGIN = 3
SIGHT_RANGE = 250
# The ground rule (tools/ground_rule.py): nothing here reads a world.
WORLD_READS: set = set()

FACING = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}
NEVER = {"minecraft:chest": "a chest is a Gimmighoul spawn condition (tools/portals_audit.py)",
         "minecraft:trapped_chest": "a chest is a Gimmighoul spawn condition (tools/portals_audit.py)",
         "minecraft:white_bed": "a bed sets a respawn point, which the blackout's checkpoints own"}


class PlaceError(SystemExit):
    pass


def base(state):
    return state.split("[")[0].split("{")[0]


def unsafe_blocks(ids, place_id):
    """{block: why} for every id in `ids` a place may not write: a spawn condition (data/spawn_blocks.json) that no
    data/spawn_block_policy.json entry scoped to `place_id` allows, a chest or a bed."""
    cond = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    allowed = {b for w in policy["whitelist"] if place_id in (w.get("scope") or "") for b in w["blocks"]}
    out = {}
    for b in ids:
        if b in NEVER:
            out[b] = NEVER[b]
        elif b.endswith("_bed"):
            out[b] = NEVER["minecraft:white_bed"]
        elif b in cond and b not in allowed:
            out[b] = "a Cobblemon spawn condition (data/spawn_blocks.json) no policy entry scoped to %s allows" % place_id
    return out


def load_record(path, schema, place_id):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != schema:
        raise PlaceError("%s: schema must be %s" % (path, schema))
    if doc.get("id") != place_id:
        raise PlaceError("%s: id must be %s" % (path, place_id))
    bad = unsafe_blocks(doc["blocks"]["ids"], place_id)
    if bad:
        raise PlaceError("%s blocks.ids holds %s" % (path, "; ".join("%s: %s" % kv for kv in sorted(bad.items()))))
    return doc


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """{(x, y, z): state} in two passes: `solid` (the structure, in the order written) and `hung` (what hangs on it)."""

    def __init__(self, allowed, place_id):
        self.allowed, self.place_id = set(allowed), place_id
        self.solid, self.hung = {}, {}

    def _chk(self, state):
        if base(state) not in self.allowed:
            raise PlaceError("%s is not in data/%s.json blocks.ids" % (base(state), self.place_id))

    def put(self, x, y, z, state):
        self._chk(state)
        self.solid[(x, y, z)] = state

    def hang(self, x, y, z, state):
        self._chk(state)
        self.hung[(x, y, z)] = state

    def blocks(self):
        out = dict(self.solid)
        out.update(self.hung)
        return out


def wall_sign(kind, facing, lines):
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
    return "minecraft:%s_wall_sign[facing=%s]{front_text:{messages:[%s]}}" % (kind, facing, q)


def lantern(hanging):
    return "minecraft:lantern[hanging=%s,waterlogged=false]" % ("true" if hanging else "false")


def stair(kind, facing):
    return "minecraft:%s_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (kind, facing)


def fence(kind, e=False, w=False, n=False, s=False):
    return "minecraft:%s_fence[east=%s,west=%s,north=%s,south=%s,waterlogged=false]" % (
        kind, str(e).lower(), str(w).lower(), str(n).lower(), str(s).lower())


def pick(x, y, z, choices):
    """A deterministic choice from `choices` by position: the same record always writes the same blocks."""
    return choices[(x * 73856093 ^ y * 19349663 ^ z * 83492791) % len(choices)]


# ------------------------------------------------------------------------------------------------------------- carving
def shell(g, voids, margin, keep):
    """Every block within `margin` (Chebyshev) of a void, at or below its column's ground minus `keep`, not a void."""
    out, tops = set(), {}
    for (x, y, z) in voids:
        for dx in range(-margin, margin + 1):
            for dz in range(-margin, margin + 1):
                cx, cz = x + dx, z + dz
                top = tops.get((cx, cz))
                if top is None:
                    top = tops[(cx, cz)] = g(cx, cz) - keep
                for dy in range(-margin, margin + 1):
                    if y + dy <= top:
                        out.add((cx, y + dy, cz))
    return out - set(voids)


def stair_passage(g, first, direction, floor0, half_width, height):
    """The steps of a rock-cut stair from a chamber's edge up to the ground, as a list of dicts:
    {j, floor, cols [(x, z)], open, sides [(x, z)]}. Step 0 is a landing at `floor0` on the column `first` (and
    `half_width` columns either side, across the direction); each step after it is one further along `direction` and
    one higher. A step is roofed while every column of it has two or more blocks of ground over its `height` blocks of
    air, and open (a trench to the sky) once one has less. The last step is the one level with the
    ground (a stair cut into the ground's top block), so the way out is never a one-block jump; the stair ends before
    a step whose floor would stand above the ground of any of its columns."""
    dx, dz = direction
    px, pz = -dz, dx                       # across the passage
    out = []
    for j in range(0, 64):
        cx, cz = first[0] + dx * j, first[1] + dz * j
        cols = [(cx + px * k, cz + pz * k) for k in range(-half_width, half_width + 1)]
        floor = floor0 + j
        if j > 0 and any(floor > g(x, z) for x, z in cols):
            return out
        sides = [(cx + px * (half_width + 1), cz + pz * (half_width + 1)),
                 (cx - px * (half_width + 1), cz - pz * (half_width + 1))]
        opened = any(g(x, z) - (floor + height) < 2 for x, z in cols)
        out.append({"j": j, "floor": floor, "cols": cols, "open": opened, "sides": sides})
    raise PlaceError("a stair passage from %s never reached the ground in 64 steps" % (first,))


def passage_voids(g, steps, height):
    out = set()
    for s in steps:
        for x, z in s["cols"]:
            top = g(x, z) if s["open"] else s["floor"] + height
            for y in range(s["floor"] + 1, top + 1):
                out.add((x, y, z))
    return out


def dress_passage(p, g, steps, height, direction, floor_block, stair_kind, wall_choices, face_block):
    """The stair's floor, the dressed walls of its open trench, and a dressed face over its mouth (the last roofed
    step's ground, from the passage roof up to the ground's top, is written in face_block so the opening has a lintel)."""
    facing = FACING[direction]
    for s in steps:
        for x, z in s["cols"]:
            p.put(x, s["floor"], z, floor_block if s["j"] == 0 else stair(stair_kind, facing))
        if s["open"]:
            for x, z in s["sides"]:
                for y in range(s["floor"], max(g(x, z), s["floor"]) + 1):
                    p.put(x, y, z, pick(x, y, z, wall_choices))
    roofed = [s for s in steps if not s["open"]]
    opened = [s for s in steps if s["open"]]
    if roofed and opened:
        last = roofed[-1]
        for x, z in last["cols"] + last["sides"]:
            for y in range(last["floor"] + height + 1, g(x, z) + 1):
                p.put(x, y, z, face_block)


def cover(g, voids, skip=lambda x, z: False):
    """{void: ground over its column minus its y} for every void block whose column `skip` does not exclude."""
    return {(x, y, z): g(x, z) - y for (x, y, z) in voids if not skip(x, z)}


# ------------------------------------------------------------------------------------------------------------ the pack
def runs(blocks, top_down=False):
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


def above_ground_box(blocks, g):
    above = [(x, z) for (x, y, z) in blocks if y > g(x, z)]
    xs = [k[0] for k in above]
    zs = [k[1] for k in above]
    return (min(xs) - CLEAR_MARGIN, min(zs) - CLEAR_MARGIN, max(xs) + CLEAR_MARGIN, max(zs) + CLEAR_MARGIN)


def build_lines(header, p, clear, clear_y):
    x0, z0, x1, z1 = clear
    y0, y1 = clear_y
    out = list(header) + ["# 1. clear the trees, plants and snow layers over everything this writes above the ground"]
    for tag in ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable"):
        out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the structure, bottom up")
    out += runs({k: st for k, st in p.solid.items() if k not in p.hung})
    out.append("# 3. what hangs on it, from the top")
    out += runs(p.hung, top_down=True)
    return out


def pack_files(fn, description, lines):
    import function_limits
    lines = function_limits.ensure_loaded(lines)
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise PlaceError("%s build: %d command(s) the server would refuse: %s" % (fn, len(bad), bad[:3]))
    return {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description": description}}, indent=2) + "\n",
        "data/%s/function/%s/build.mcfunction" % (NS, fn): "\n".join(lines) + "\n",
    }


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def hold_box(blocks, clear):
    ks = list(blocks)
    return (min(min(k[0] for k in ks), clear[0]), min(min(k[2] for k in ks), clear[1]),
            max(max(k[0] for k in ks), clear[2]), max(max(k[2] for k in ks), clear[3]))


def placement_steps(hold, fn):
    """Hold the chunks, build, release: the shape of R9LH, R9HF and R9DU."""
    box = "%d %d %d %d" % hold
    return [("cmd", "forceload add " + box), ("wait", 3), ("fn", "%s:%s/build" % (NS, fn)),
            ("cmd", "forceload remove " + box)]


# ---------------------------------------------------------------------------------------------------------- reporting
def sightline(g, frm, to, eye=1.62):
    fx, fz = frm
    ey = g(fx, fz) + 1 + eye
    tx, ty, tz = to
    n = int(math.hypot(tx - fx, tz - fz) * 2)
    worst = 1e9
    for i in range(1, n):
        t = i / float(n)
        x, z = fx + (tx - fx) * t, fz + (tz - fz) * t
        y = ey + (ty + 0.5 - ey) * t
        worst = min(worst, y - (g(int(math.floor(x)), int(math.floor(z))) + 1))
    return worst


def visible_from_route(g, path, target, step=4):
    n, best = 0, (None, -1e9)
    for x, z in path[::step]:
        if math.hypot(x - target[0], z - target[2]) > SIGHT_RANGE:
            continue
        c = sightline(g, (x, z), target)
        if c > 0:
            n += 1
        if c > best[1]:
            best = ((x, z), c)
    return n, best


def route_paths():
    return json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]


def distance_to_paths(bbox, names):
    x0, z0, x1, z1 = bbox
    paths = route_paths()
    best = 1e9
    for n in names:
        for x, z in paths[n]:
            best = min(best, math.hypot(max(x0 - x, 0, x - x1), max(z0 - z, 0, z - z1)))
    return best


def reward_check(reward_id, container, trigger):
    """'matches' when data/rewards.json's cache `reward_id` names this container and trigger box, else what differs."""
    doc = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
    r = next((r for r in doc["rewards"] if r["id"] == reward_id), None)
    if r is None:
        return "MISSING: no cache %s in data/rewards.json" % reward_id
    got = (tuple(r["container"]["at"]), tuple(r["trigger"]["min"]), tuple(r["trigger"]["max"]))
    want = (tuple(container), tuple(trigger[0]), tuple(trigger[1]))
    return "matches" if got == want else "MISMATCH: data/rewards.json has %s, the plan %s" % (got, want)
