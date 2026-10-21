#!/usr/bin/env python
"""The independent audit of the refillable mining caves (data/mining_caves.json, pack cobblers_mining_caves).

Written by test-author (unit CAVES audit, 2026-10-10), who built none of the caves (CLAUDE.md principle 16). Nothing
here imports tools/mining_caves.py or tools/mines.py: the expectation is derived from data/mining_caves.json's own
`geometry.rules` text and the canonical ground (tools/ground.py), and the pack is read as text and run by this file's
own command model (Sim), whose vanilla 1.21.1 semantics are stated where they are used, not read from a jar:

  * `@a[x,y,z,dx,dy,dz]` / `@e[...]` match an entity whose bounding box intersects the box from (x, y, z) to
    (x + dx + 1, y + dy + 1, z + dz + 1) (EntitySelectorParser adds one to a non-negative size; AABB.intersects is
    strict, so a box that only touches does not match);
  * `execute if loaded` is true only for an entity-ticking chunk whose entities are loaded;
  * `return 0` (also under `execute ... run`) ends the function it is in;
  * an unset score fails `if score ... matches`, so `unless score ... matches` succeeds on it;
  * a player is 0.6 x 1.8 x 0.6 standing, 0.6 x 1.5 sneaking, 0.6 x 0.6 crawling, 0.2 x 0.2 asleep.

What it checks, per gallery:
  geometry    the restore's writes (the `_rock` fills and the variants' setblocks) are exactly the gallery's body and
              shell as the rules text defines them, and the body/shell blocks are the record's host and shell
  filter      every restore write is either a `fill ... replace #cobblers:cave_resettable` or a setblock guarded by
              `execute if block <same cell> <host>`; the tag holds no block with a block entity a player keeps things in
  guard       before the restore is called: the period test, `unless loaded` over every chunk the guard box touches,
              and `@a` and `@e[type=cobblemon:pokemon]` over a box that is the writes grown by one on every side
  callers     restore_<g> is called only from check_<g>, which is called only from the cave's near_ function, which
              the drive calls only under an approach selector that contains every guard box
  run         (Sim) nobody is buried: a player or Pokemon whose box meets a written cell gets no write at all; an
              unloaded chunk gets none; the clock does not let a gallery restore twice inside its period across a
              restart or a re-approach
  walk        (the real heightmap) the built cave is walkable, in 1-block steps both ways, from outside its mouth to
              the hall beside every gallery
  keep clear  (--inputs-root, a full checkout) the distance from every column the pack writes to towns, route paths
              and legs, corridor boxes, placements, painted water, the water export's changed columns and every other
              built pack's writes; and (2026-10-20) the same for a host cave's host earthwork (the hill a cave is
              entered by, data/placements.json), judged outside every town footprint (its distance against the caves'
              town margin reported for a look) and clear of every x/z any other data file authors, swept (a trainer's
              seat, a Habitat Block, a portal); a host's entry.host.keep_clear_shared names what it shares by design
  economy     yield per reset, per player hour and the server's ceiling, priced from data/bank.json

Not covered, and it needs a running server: that the commands parse and do what the stated vanilla semantics say;
Pokemon AI pathing into a gallery mid-restore; mobs other than players and cobblemon:pokemon (a tamed wolf, a
Cobblemon NPC, an armour stand) are not guarded and can be buried; the outside terrain's trees and builds (the walk
reads the heightmap, not the world); the yields' Fortune and drop counts (vanilla loot tables, assumed).

  python tools/mining_caves_audit.py [--pack DIR] [--inputs-root <full checkout>] [--no-walk]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "mining_caves.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_mining_caves"
TAG = "#cobblers:cave_resettable"
FN = "cobblers:mining_caves/"

# Blocks with a block entity a player stores things in, or a block whose loss is a player's loss (vanilla 1.21.1 and
# the pack's mods named in CLAUDE.md). A tag entry matching any of these substrings is a fault.
KEEPS = ("chest", "barrel", "shulker_box", "hopper", "furnace", "smoker", "dispenser", "dropper", "crafter",
         "brewing_stand", "bookshelf", "decorated_pot", "lectern", "jukebox", "campfire", "bed", "sign", "banner",
         "spawner", "beacon", "conduit", "enchanting_table", "anvil", "pc", "healing_machine", "display_case",
         "cabinet", "drawer", "crate", "safe", "waystone", "trainer_spawner", "skull", "head")
SIZES = {"standing": (0.6, 1.8), "sneaking": (0.6, 1.5), "crawling": (0.6, 0.6), "asleep": (0.2, 0.2)}

# Vanilla 1.21.1 ore loot (assumed, not read from a jar): (item, mean count without Fortune, Fortune III multiplier)
DROPS = {
    "coal": ("minecraft:coal", 1.0, 2.2), "iron": ("minecraft:raw_iron", 1.0, 2.2),
    "copper": ("minecraft:raw_copper", 3.5, 2.2), "lapis": ("minecraft:lapis_lazuli", 6.5, 2.2),
    "gold": ("minecraft:raw_gold", 1.0, 2.2), "redstone": ("minecraft:redstone", 4.5, 6.0 / 4.5),
    "diamond": ("minecraft:diamond", 1.0, 2.2), "emerald": ("minecraft:emerald", 1.0, 2.2),
}


class AuditError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def base(block):
    return block.split("[")[0].split("{")[0]


# ------------------------------------------------------------------ the expectation, from the rules text

def frame(anchor, front):
    """(u, d) -> (x, z), from the rules text: 'north means the player stands north and the passage runs +z'; u runs
    +x on a north or south front and +z on a west or east one; side left is u < 0."""
    ax, az = anchor
    return {"north": lambda u, d: (ax + u, az + d), "south": lambda u, d: (ax + u, az - d),
            "west": lambda u, d: (ax + d, az + u), "east": lambda u, d: (ax - d, az + u)}[front]


def expected(spec, cave, ground):
    """{"y0", "yh", "galleries": {id: {"body": {cell}, "shell": {cell}, "box": (x0, y0, z0, x1, y1, z1)}}}."""
    geo = spec["geometry"]
    hw, W, D, H = geo["passage_half_width"], geo["gallery_width"], geo["gallery_depth"], geo["gallery_height"]
    xz = frame(cave["entry"]["anchor"], cave["entry"]["front"])
    row = sorted(int(ground(*xz(u, -1))) for u in range(-hw - 1, hw + 2))
    y0 = row[(len(row) - 1) // 2]
    yh = y0 - cave["drop"]
    hall0 = cave["drop"] + 1
    out = {}
    for g in cave["galleries"]:
        s = -1 if g["side"] == "left" else 1
        d_first = hall0 + g["slot"] * (W + 2)            # the slot's first row: one shell row, W body rows, one shell
        body, shell = set(), set()
        for d in range(d_first, d_first + W + 2):
            for k in range(0, D + 1):
                x, z = xz(s * (hw + 1 + k), d)
                for y in range(yh, yh + H + 2):
                    inside = d_first + 1 <= d <= d_first + W and k < D and yh + 1 <= y <= yh + H
                    (body if inside else shell).add((x, y, z))
        cells = body | shell
        xs, ys, zs = zip(*cells)
        out[g["id"]] = {"body": body, "shell": shell, "box": (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)),
                        "side": s, "face_d": d_first + 1 + W // 2}
    return {"y0": y0, "yh": yh, "galleries": out, "xz": xz}


# ------------------------------------------------------------------ reading the pack

def read_pack(pack=PACK):
    pack = Path(pack)
    fdir = pack / "data" / "cobblers" / "function" / "mining_caves"
    if not fdir.is_dir():
        raise AuditError("no built pack at %s (python tools/mining_caves.py build)" % pack)
    fns = {p.relative_to(fdir).with_suffix("").as_posix(): p.read_text(encoding="utf-8").splitlines()
           for p in fdir.rglob("*.mcfunction")}
    tag = json.loads((pack / "data" / "cobblers" / "tags" / "block" / "cave_resettable.json").read_text(encoding="utf-8"))
    return fns, tag["values"]


SEL = re.compile(r"@([ae])\[([^\]]*)\]")


def selector(text):
    """'@a[x=1,y=2,...]' -> (kind, {key: value})."""
    m = SEL.search(text)
    if not m:
        return None
    return m.group(1), dict(kv.split("=", 1) for kv in m.group(2).split(","))


def sel_box(args):
    """The block range [x0..x1] etc. an x/dx selector covers (dx >= 0 assumed; a negative size is a fault here)."""
    x, y, z = (int(args[k]) for k in "xyz")
    dx, dy, dz = (int(args.get(k, 0)) for k in ("dx", "dy", "dz"))
    if min(dx, dy, dz) < 0:
        raise AuditError("a negative selector size: %s" % args)
    return (x, y, z, x + dx, y + dy, z + dz)


def contains(outer, inner):
    return all(outer[i] <= inner[i] for i in range(3)) and all(outer[i] >= inner[i] for i in range(3, 6))


def grow(box, n):
    return tuple(box[i] - n for i in range(3)) + tuple(box[i] + n for i in range(3, 6))


def rock_writes(lines):
    """{cell: block} of a `_rock` function, and the problems: every write must be a filtered fill over the tag."""
    out, probs = {}, []
    for l in lines:
        t = l.split()
        if not t or t[0].startswith("#"):
            continue
        if t[0] != "fill" or len(t) != 10 or t[8] != "replace" or t[9] != TAG:
            probs.append("an unfiltered or unexpected restore write: %r" % l)
            continue
        x0, y0, z0, x1, y1, z1 = map(int, t[1:7])
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    out[(x, y, z)] = t[7]
    return out, probs


VAR = re.compile(r"^execute if block (-?\d+) (-?\d+) (-?\d+) (\S+) run setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$")


def variant_writes(lines, host):
    out, probs = {}, []
    for l in lines:
        if not l.strip() or l.startswith("#"):
            continue
        m = VAR.match(l)
        if not m or m.group(1, 2, 3) != m.group(5, 6, 7) or m.group(4) != host:
            probs.append("a variant write not guarded by `if block <same cell> %s`: %r" % (host, l))
            continue
        out[tuple(int(v) for v in m.group(5, 6, 7))] = m.group(8)
    return out, probs


def callers(fns, target):
    return sorted(n for n, ls in fns.items() for l in ls if not l.startswith("#") and ("function " + FN + target) in l
                  and l.rstrip().endswith(FN + target))


def static_problems(spec, fns, tag, ground):
    """Every rule above that reads the pack as text. [] is a pass."""
    probs = []
    period = spec["restore"]["period_ticks"]
    nv = spec["restore"]["variants"]
    for v in tag:
        if v.startswith("#"):
            probs.append("the tag holds a nested tag %s: what it pulls in is not checked here" % v)
        if any(k in base(v).split(":")[-1] for k in KEEPS):
            probs.append("the tag holds %s: a restore would delete a player's block and what it holds" % v)
    load_ = fns.get("load", [])
    if "scoreboard players set #period mcv.t %d" % period not in load_:
        probs.append("load does not set #period to the record's %d ticks" % period)
    drive = [l for l in fns.get("drive", []) if l.startswith("execute if entity @a[")]
    for cave in spec["caves"]:
        yl = spec["yields"][cave["yield"]]
        host = yl["host"]
        ex = expected(spec, cave, ground)
        near = "near_%s" % cave["id"]
        app = [l for l in drive if l.endswith("function %s%s" % (FN, near))]
        if len(app) != 1:
            probs.append("%s: the drive calls %s %d times, not once under an approach selector" % (cave["id"], near, len(app)))
            app_box = None
        else:
            app_box = sel_box(selector(app[0])[1])
        if callers(fns, near) != ["drive"]:
            probs.append("%s: %s is called from %s, not only the drive" % (cave["id"], near, callers(fns, near)))
        for gid, e in ex["galleries"].items():
            want = e["body"] | e["shell"]
            rock, p1 = rock_writes(fns.get("galleries/%s_rock" % gid, []))
            probs += ["%s: %s" % (gid, p) for p in p1]
            if set(rock) != want:
                probs.append("%s: the restore's fill covers %d cells outside the gallery and misses %d of it"
                             % (gid, len(set(rock) - want), len(want - set(rock))))
            wrong = sorted(c for c in rock if (c in e["body"] and rock[c] != host) or (c in e["shell"] and rock[c] != cave["shell"]))
            if wrong:
                probs.append("%s: %d formation cells put back the wrong block, e.g. %s %s" % (gid, len(wrong), wrong[0], rock[wrong[0]]))
            for k in range(nv):
                vw, p2 = variant_writes(fns.get("galleries/%s_v%d" % (gid, k), []), host)
                probs += ["%s v%d: %s" % (gid, k, p) for p in p2]
                out = sorted(set(vw) - e["body"])
                if out:
                    probs.append("%s v%d: %d ore writes outside the body, e.g. %s" % (gid, k, len(out), out[0]))
                for ore, y in yl["ores"].items():
                    n = sum(1 for b in vw.values() if b == ore)
                    if n != y["per_variant"][k]:
                        probs.append("%s v%d: %d %s, the record says %d" % (gid, k, n, ore, y["per_variant"][k]))
                hw = spec["geometry"]["passage_half_width"]
                ew = cave["entry"]["front"] in ("east", "west")
                for c, b in vw.items():
                    if b in (yl.get("hidden_only") or []):
                        u = c[2] - cave["entry"]["anchor"][1] if ew else c[0] - cave["entry"]["anchor"][0]
                        depth = abs(u) - (hw + 1)            # 0 is the face the hall shows
                        if depth < 2:
                            probs.append("%s v%d: hidden ore %s at %s is %d into the body, under 2" % (gid, k, b, c, depth))
            # the guard, read in order up to the restore call
            chk = [l for l in fns.get("galleries/check_%s" % gid, []) if l and not l.startswith("#")]
            call = "function %sgalleries/restore_%s" % (FN, gid)
            if call not in chk:
                probs.append("%s: check never calls the restore" % gid)
                continue
            pre = chk[:chk.index(call)]
            if not any(re.fullmatch(r"execute if score #d mcv\.t < #period mcv\.t run return 0", l) for l in pre):
                probs.append("%s: no period test before the restore" % gid)
            need = grow(e["box"], 1)
            for kind, typ in (("a", None), ("e", "cobblemon:pokemon")):
                hits = []
                for l in pre:
                    if l.startswith("execute if entity @%s[" % kind) and l.endswith("run return 0"):
                        k_, args = selector(l)
                        if typ is None or args.get("type") == typ:
                            hits.append(sel_box(args))
                if not any(contains(h, need) for h in hits):
                    probs.append("%s: no @%s%s guard over the gallery grown by one %s (found %s)" % (
                        gid, kind, "[type=%s]" % typ if typ else "", need, hits))
            loaded = set()
            for l in pre:
                m = re.fullmatch(r"execute unless loaded (-?\d+) (-?\d+) (-?\d+) run return 0", l)
                if m:
                    loaded.add((int(m.group(1)) >> 4, int(m.group(3)) >> 4))
            chunks = {(cx, cz) for cx in range(need[0] >> 4, (need[3] >> 4) + 1) for cz in range(need[2] >> 4, (need[5] >> 4) + 1)}
            if not chunks <= loaded:
                probs.append("%s: chunks %s of the guard box are never tested `unless loaded`" % (gid, sorted(chunks - loaded)))
            if callers(fns, "galleries/restore_%s" % gid) != ["galleries/check_%s" % gid]:
                probs.append("%s: the restore is called from %s" % (gid, callers(fns, "galleries/restore_%s" % gid)))
            if callers(fns, "galleries/check_%s" % gid) != [near]:
                probs.append("%s: the check is called from %s" % (gid, callers(fns, "galleries/check_%s" % gid)))
            if app_box is not None and not contains(app_box, need):
                probs.append("%s: the guard box %s is not inside the approach box %s" % (gid, need, app_box))
    return probs


# ------------------------------------------------------------------ the command model

class Sim:
    """A world small enough to run the caves' driver: blocks, entities (kind, type, aabb), loaded chunks, game time and
    scores. Every write is recorded in `writes` as (cell, block, game time)."""

    def __init__(self, fns, tag, natural, loaded=None, seed=1):
        self.fns, self.tag = fns, set(tag)
        self.natural = natural                  # (x, y, z) -> block for a cell never written
        self.blocks = {}
        self.entities = []
        self.loaded = loaded                    # None: every chunk; else a set of (cx, cz)
        self.gt = 1_000_000
        self.scores = {}
        self.rng = random.Random(seed)
        self.writes = []
        self.depth = 0

    def block(self, c):
        return self.blocks.get(c) or self.natural(c)

    def set(self, c, b):
        self.blocks[c] = b
        self.writes.append((c, b, self.gt))

    def score(self, holder, obj):
        return self.scores.get((holder, obj))

    def matches(self, holder, obj, rng):
        v = self.score(holder, obj)
        if v is None:
            return False
        lo, _, hi = rng.partition("..")
        if ".." not in rng:
            return v == int(rng)
        return (lo == "" or v >= int(lo)) and (hi == "" or v <= int(hi))

    def select(self, kind, args):
        x0, y0, z0, x1, y1, z1 = sel_box(args)
        box = (x0, y0, z0, x1 + 1, y1 + 1, z1 + 1)
        out = []
        for e in self.entities:
            if kind == "a" and e["kind"] != "player":
                continue
            if "type" in args and e.get("type") != args["type"]:
                continue
            a = e["aabb"]
            if all(a[i] < box[i + 3] and a[i + 3] > box[i] for i in range(3)):
                out.append(e)
        return out

    def is_loaded(self, x, z):
        return self.loaded is None or (x >> 4, z >> 4) in self.loaded

    def call(self, name):
        name = name[len(FN):] if name.startswith(FN) else name
        if name not in self.fns:
            raise AssertionError("the simulator does not know function %s" % name)
        self.depth += 1
        if self.depth > 50:
            raise AssertionError("the simulator does not know a call chain this deep")
        try:
            for line in self.fns[name]:
                if line.strip() and not line.startswith("#"):
                    if self.run(line.split()) == "return":
                        break
        finally:
            self.depth -= 1

    def run(self, t):
        h = t[0]
        if h == "return":
            return "return"
        if h == "function":
            self.call(t[1])
            return None
        if h == "forceload":
            return None
        if h == "scoreboard":
            return self.scoreboard(t)
        if h == "setblock":
            self.set(tuple(map(int, t[1:4])), t[4])
            return None
        if h == "fill":
            x0, y0, z0, x1, y1, z1 = map(int, t[1:7])
            filt = t[9] if len(t) > 9 and t[8] == "replace" else None
            if filt is not None and filt != TAG and not filt.startswith("minecraft:"):
                raise AssertionError("the simulator does not know the filter %s" % filt)
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        cur = base(self.block((x, y, z)))
                        if filt is None or (filt == TAG and cur in self.tag) or cur == filt:
                            self.set((x, y, z), t[7])
            return None
        if h == "execute":
            return self.execute(t[1:])
        raise AssertionError("the simulator does not know %r" % " ".join(t))

    def scoreboard(self, t):
        if t[1] == "objectives":
            return None
        op = t[2]
        if op in ("set", "add", "remove"):
            v = int(t[5])
            cur = self.score(t[3], t[4]) or 0
            self.scores[(t[3], t[4])] = v if op == "set" else cur + v if op == "add" else cur - v
            return None
        if op == "operation":
            a, ao, o, b, bo = t[3], t[4], t[5], t[6], t[7]
            x, y = self.score(a, ao) or 0, self.score(b, bo) or 0
            r = {"=": y, "+=": x + y, "-=": x - y, "%=": x % y if y else x, ">": max(x, y), "<": min(x, y)}[o]
            self.scores[(a, ao)] = r
            return None
        raise AssertionError("the simulator does not know scoreboard %s" % op)

    def execute(self, t):
        i = 0
        while i < len(t):
            w = t[i]
            if w == "run":
                return self.run(t[i + 1:])
            if w in ("if", "unless"):
                want = w == "if"
                k = t[i + 1]
                if k == "score":
                    if t[i + 4] == "matches":
                        ok, i = self.matches(t[i + 2], t[i + 3], t[i + 5]), i + 6
                    else:
                        a, b = self.score(t[i + 2], t[i + 3]), self.score(t[i + 5], t[i + 6])
                        o = t[i + 4]
                        ok = a is not None and b is not None and {"<": a < b, "<=": a <= b, "=": a == b, ">": a > b, ">=": a >= b}[o]
                        i += 7
                elif k == "entity":
                    kind, args = selector(t[i + 2])
                    ok, i = bool(self.select(kind, args)), i + 3
                elif k == "loaded":
                    ok, i = self.is_loaded(int(t[i + 2]), int(t[i + 4])), i + 5
                elif k == "block":
                    c = tuple(map(int, t[i + 2:i + 5]))
                    ok, i = base(self.block(c)) == base(t[i + 5]), i + 6
                else:
                    raise AssertionError("the simulator does not know execute %s %s" % (w, k))
                if ok != want:
                    return None
                continue
            if w == "store":
                holder, obj = t[i + 3], t[i + 4]
                rest = t[i + 5:]
                if rest[:4] == ["run", "time", "query", "gametime"]:
                    self.scores[(holder, obj)] = self.gt
                elif rest[:3] == ["run", "random", "value"]:
                    lo, hi = map(int, rest[3].split(".."))
                    self.scores[(holder, obj)] = self.rng.randint(lo, hi)
                else:
                    raise AssertionError("the simulator does not know store %s" % rest)
                return None
            raise AssertionError("the simulator does not know execute %s" % w)
        return None

    def tick(self, n=1):
        for _ in range(n):
            self.gt += 1
            self.call("tick")


def player(x, y, z, pose="standing", kind="player", typ=None):
    w, h = SIZES[pose]
    return {"kind": kind, "type": typ or ("minecraft:player" if kind == "player" else None),
            "aabb": (x - w / 2, y, z - w / 2, x + w / 2, y + h, z + w / 2), "at": (x, y, z), "pose": pose}


def meets(aabb, cell):
    x, y, z = cell
    return aabb[0] < x + 1 and aabb[3] > x and aabb[1] < y + 1 and aabb[4] > y and aabb[2] < z + 1 and aabb[5] > z


def natural_from(ground, rock="minecraft:stone"):
    return lambda c: rock if c[1] <= ground(c[0], c[2]) else "minecraft:air"


class Built:
    """Every cave's build function and the driver's load, run once on the ground; fresh() copies the result."""

    def __init__(self, spec, fns, tag, ground):
        self.spec, self.fns, self.tag, self.ground = spec, fns, tag, ground
        s = Sim(fns, tag, natural_from(ground))
        for cave in spec["caves"]:
            s.call("build_%s" % cave["id"])
        s.call("load")
        self.blocks, self.scores, self.gt = dict(s.blocks), dict(s.scores), s.gt

    def fresh(self, loaded=None, seed=1):
        s = Sim(self.fns, self.tag, natural_from(self.ground), loaded=loaded, seed=seed)
        s.blocks, s.scores, s.gt = dict(self.blocks), dict(self.scores), self.gt
        return s


def grow_cells(cells, n):
    out = set()
    for (x, y, z) in cells:
        for dx in range(-n, n + 1):
            for dy in range(-n, n + 1):
                for dz in range(-n, n + 1):
                    out.add((x + dx, y + dy, z + dz))
    return out


def mine_out(s, body):
    for c in body:
        s.blocks[c] = "minecraft:air"


def due_only(s, spec, gid):
    """The state in which gallery `gid` is due and every other gallery was restored a moment ago (so the cave's first
    gallery checked does not take the turn and push the rest back by the stagger)."""
    period = spec["restore"]["period_ticks"]
    for cave in spec["caves"]:
        for g in cave["galleries"]:
            s.scores[("#%s" % g["id"], "mcv.last")] = s.gt - period - 1 if g["id"] == gid else s.gt
    return s


def visitor_for(spec, ex, e):
    """A player on the hall floor across the hall from the gallery: inside the approach box, outside the guard."""
    hw = spec["geometry"]["passage_half_width"]
    x, z = ex["xz"](-e["side"] * hw, e["face_d"])
    return player(x + 0.5, ex["yh"] + 1, z + 0.5)


def stances(spec, ex, e):
    """Entity positions whose box meets the gallery grown by one: hugging the hall wall beside it, and at a spread of
    the body's and shell's cells in every pose (a player who mined in, dug into the shell, or lies asleep there)."""
    hw = spec["geometry"]["passage_half_width"]
    hx, hz = ex["xz"](e["side"] * hw, e["face_d"])
    out = [(hx + 0.5 + dx, ex["yh"] + 1, hz + 0.5 + dz, "standing") for dx in (-0.29, 0.29) for dz in (-0.29, 0.29)]
    for c in sorted(e["body"])[::5] + sorted(e["shell"])[::9]:
        for pose in SIZES:
            out.append((c[0] + 0.5, c[1], c[2] + 0.5, pose))
    return out


def run_problems(spec, fns, tag, ground, built=None, only=None):
    """The command model's checks on the pack, with each gallery's cells from `expected` (not from the pack)."""
    probs = []
    built = built or Built(spec, fns, tag, ground)
    every = spec["restore"]["every_ticks"]
    period = spec["restore"]["period_ticks"]
    for cave in spec["caves"]:
        ex = expected(spec, cave, ground)
        for gid, e in ex["galleries"].items():
            if only and gid not in only:
                continue
            cells = e["body"] | e["shell"]
            ring = grow_cells(cells, 1)
            # the control: the gallery mined out, a visitor across the hall: a restore happens
            s = due_only(built.fresh(), spec, gid)
            mine_out(s, e["body"])
            s.entities.append(visitor_for(spec, ex, e))
            s.tick(every)
            if not {w[0] for w in s.writes} & cells:
                probs.append("%s: the control (a player across the hall, the gallery mined out) got no restore: "
                             "the checks below would pass on nothing" % gid)
                continue
            # anyone whose box meets the gallery grown by one: nothing is written at all
            for (x, y, z, pose) in stances(spec, ex, e):
                bad = None
                for who in ("player", "pokemon"):
                    s = due_only(built.fresh(), spec, gid)
                    mine_out(s, e["body"])
                    s.entities.append(visitor_for(spec, ex, e))
                    ent = player(x, y, z, pose) if who == "player" else player(x, y, z, pose, "mob", "cobblemon:pokemon")
                    s.entities.append(ent)
                    s.tick(every)
                    if any(meets(ent["aabb"], w[0]) for w in s.writes):
                        bad = "%s: a %s %s at %s is written over (buried)" % (gid, who, pose, (x, y, z))
                    elif any(meets(ent["aabb"], c) for c in ring) and any(w[0] in cells for w in s.writes):
                        bad = "%s: a %s %s at %s, inside the gallery grown by one, still got a restore" % (gid, who, pose, (x, y, z))
                    if bad:
                        break
                if bad:
                    probs.append(bad)
                    break
            # one chunk of the gallery's guard box not loaded: no write
            g1 = grow(e["box"], 1)
            chunks = {(cx, cz) for cx in range(g1[0] >> 4, (g1[3] >> 4) + 1) for cz in range(g1[2] >> 4, (g1[5] >> 4) + 1)}
            every_chunk = {(cx, cz) for cx in range((g1[0] >> 4) - 8, (g1[3] >> 4) + 9)
                           for cz in range((g1[2] >> 4) - 8, (g1[5] >> 4) + 9)}
            for gone in sorted(chunks):
                s = due_only(built.fresh(loaded=every_chunk - {gone}), spec, gid)
                mine_out(s, e["body"])
                s.entities.append(visitor_for(spec, ex, e))
                s.tick(every)
                if any(w[0] in cells for w in s.writes):
                    probs.append("%s: restored with chunk %s of its guard box unloaded" % (gid, gone))
                    break
        gid0 = cave["galleries"][0]["id"]
        if not only or gid0 in only:
            probs += ["%s: %s" % (gid0, p) for p in clock_problems(spec, built, ground, cave, gid0, period)]
    return probs


def restore_times(s, cells):
    return sorted({w[2] for w in s.writes if w[0] in cells})


def clock_run(spec, built, ground, cave, gid, action):
    """Mine the gallery out every pass for 2.6 periods while `action` (restart: minecraft:load again; reapproach: the
    player leaves the approach box and comes back) repeats: the game times its restores wrote at."""
    ex = expected(spec, cave, ground)
    e = ex["galleries"][gid]
    every = spec["restore"]["every_ticks"]
    s = built.fresh()
    v = visitor_for(spec, ex, e)
    s.entities.append(v)
    for i in range(int(2.6 * spec["restore"]["period_ticks"] / every)):
        mine_out(s, e["body"])
        if action == "restart":
            s.call("load")
        elif action == "reapproach":
            if i % 2 and v in s.entities:
                s.entities.remove(v)
            elif not i % 2 and v not in s.entities:
                s.entities.append(v)
        s.tick(every)
    return restore_times(s, e["body"] | e["shell"])


def clock_problems(spec, built, ground, cave, gid, period):
    out = []
    for action in ("restart", "reapproach"):
        ts = clock_run(spec, built, ground, cave, gid, action)
        if len(ts) < 2:
            out.append("%s: %d restores in 2.6 periods: the clock never ran (a check that passes on nothing)" % (action, len(ts)))
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        if gaps and min(gaps) < period:
            out.append("%s: two restores %d ticks apart, under the period %d" % (action, min(gaps), period))
    return out


# ------------------------------------------------------------------ walking the built cave

PASS = ("minecraft:air", "minecraft:cave_air")
# A closed bottom-half trapdoor (the old mine's sleepers) is 3/16 of a block: a player's feet stand in its cell, so it
# is neither a wall nor a floor (vanilla 1.21.1 TrapDoorBlock's bottom shape; tests/test_route1_old_mine.py's THIN)
THIN = "(closed bottom trapdoor)"


def apply_lines(written, lines):
    """Replay fills and setblocks into {(x, y, z): block}, in order, last write winning; block states dropped except that
    a closed bottom-half trapdoor reads THIN. A fill with a filter (replace, keep, destroy, hollow, outline) is refused:
    what it leaves depends on the world, which this model does not hold."""
    for line in lines:
        t = line.split()
        if not t or t[0] not in ("fill", "setblock"):
            continue
        if t[0] == "setblock":
            c0 = c1 = tuple(map(int, t[1:4]))
            blk = t[4]
            extra = t[5:]
        else:
            x0, y0, z0, x1, y1, z1 = map(int, t[1:7])
            c0, c1 = (min(x0, x1), min(y0, y1), min(z0, z1)), (max(x0, x1), max(y0, y1), max(z0, z1))
            blk = t[7]
            extra = t[8:]
        if extra:
            raise AuditError("a filtered write the model cannot replay: %s" % line[:90])
        b = base(blk)
        if b.endswith("_trapdoor") and "half=bottom" in blk and "open=false" in blk:
            b = THIN
        for x in range(c0[0], c1[0] + 1):
            for y in range(c0[1], c1[1] + 1):
                for z in range(c0[2], c1[2] + 1):
                    written[(x, y, z)] = b
    return written


def host_of(cave):
    """entry.host of a cave entered from its host mine (entry.mouth false), else None."""
    e = cave.get("entry") or {}
    return e.get("host") if e.get("mouth", True) is False else None


def host_lines(cave):
    """The host earthwork's commands, read from data/placements.json (the text R8 runs), never from its generator."""
    h = host_of(cave)
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    rec = next((p for p in doc["placements"] if p["id"] == h["placement"]), None)
    if rec is None:
        raise AuditError("%s: entry.host.placement %s has no record in data/placements.json" % (cave["id"], h["placement"]))
    return list(rec.get("commands") or [])


def walk_problems(spec, fns, ground):
    """BFS over the built cave on the ground, 1-block steps up or down, from outside the mouth to the hall cell beside
    every gallery's middle row. Moves are symmetric, so reaching a gallery is also walking back out.

    A cave entered from its host mine (entry.mouth false) is walked from entry.host.walk_from over the host's earthwork
    (data/placements.json, as R8 leaves it) with the cave's build over it (R9OC runs after R8), in that order."""
    probs = []
    for cave in spec["caves"]:
        written = {}
        own = fns.get("build_%s" % cave["id"], [])
        if not own:
            probs.append("%s: no build function" % cave["id"])
            continue
        host = host_of(cave)
        if host:
            apply_lines(written, host_lines(cave))
        apply_lines(written, own)

        def passable(c):
            b = written.get(c)
            if b is None:
                return c[1] > ground(c[0], c[2])
            return b in PASS

        def feet_ok(c):
            return passable(c) or written.get(c) == THIN

        def floor_ok(c):
            return not passable(c) and written.get(c) != THIN

        ex = expected(spec, cave, ground)
        xz, hw = ex["xz"], spec["geometry"]["passage_half_width"]
        xs = [c[0] for c in written]
        zs = [c[2] for c in written]
        lim = (min(xs) - 8, min(zs) - 8, max(xs) + 8, max(zs) + 8)
        sx, sz = host["walk_from"] if host else xz(0, -3)
        start = (sx, int(ground(sx, sz)) + 1, sz)
        if not (feet_ok(start) and passable((sx, start[1] + 1, sz)) and floor_ok((sx, start[1] - 1, sz))):
            probs.append("%s: the walk's start %s is not a cell a player stands in" % (cave["id"], start))
        seen = {start}
        q = deque([start])
        while q:
            x, y, z = q.popleft()
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = x + dx, z + dz
                if not (lim[0] <= nx <= lim[2] and lim[1] <= nz <= lim[3]):
                    continue
                for dy in (0, 1, -1):
                    ny = y + dy
                    n = (nx, ny, nz)
                    if n in seen:
                        continue
                    if not (feet_ok(n) and passable((nx, ny + 1, nz)) and floor_ok((nx, ny - 1, nz))):
                        continue
                    if dy == 1 and not passable((x, y + 2, z)):
                        continue
                    if dy == -1 and not passable((nx, y + 1, nz)):
                        continue
                    seen.add(n)
                    q.append(n)
        for gid, e in ex["galleries"].items():
            hx, hz = xz(e["side"] * hw, e["face_d"])
            if (hx, ex["yh"] + 1, hz) not in seen:
                probs.append("%s %s: the hall beside the gallery (%d, %d, %d) is not walkable from outside the mouth %s"
                             % (cave["id"], gid, hx, ex["yh"] + 1, hz, start))
    return probs


# ------------------------------------------------------------------ a cave entered from its host, and its retired mouth

def hall_cells(spec, cave, ex):
    """{(x, y, z)}: the hall's floor, air and roof (|u| <= hw, y yh .. yh + PH + 1) and its two walls at the air's height
    (|u| = hw + 1, y yh + 1 .. yh + PH), from the rules text ('the hall: floor yh = y0 - drop, from d = drop + 1, 3 wide
    and passage_height high, as long as the galleries along it need')."""
    geo = spec["geometry"]
    hw, PH, W = geo["passage_half_width"], geo["passage_height"], geo["gallery_width"]
    slots = max(g["slot"] for g in cave["galleries"]) + 1
    d0 = cave["drop"] + 1
    out = set()
    for d in range(d0, d0 + slots * (W + 2)):
        for u in range(-hw - 1, hw + 2):
            x, z = ex["xz"](u, d)
            ys = range(ex["yh"], ex["yh"] + PH + 2) if abs(u) <= hw else range(ex["yh"] + 1, ex["yh"] + PH + 1)
            for y in ys:
                out.add((x, y, z))
    return out


def opening_cells(cave):
    x0, y0, z0, x1, y1, z1 = host_of(cave)["opening"]
    return {(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)}


def host_problems(spec, fns, ground):
    """A cave entered from its host mine: the opening is in the hall's wall (|u| = hw + 1, a hall row, the hall's air
    height) and in no gallery; the cave's build writes it air and writes nothing of a mouth (no cell at d <= drop - 1,
    where the rules text puts the mouth and incline); the host's earthwork, replayed as R8 leaves it, leaves every
    opening cell air and writes no other cell the cave's build writes."""
    probs = []
    for cave in spec["caves"]:
        host = host_of(cave)
        if not host:
            continue
        cid = cave["id"]
        ex = expected(spec, cave, ground)
        hw, PH = spec["geometry"]["passage_half_width"], spec["geometry"]["passage_height"]
        xz = ex["xz"]
        gal = set().union(*[e["body"] | e["shell"] for e in ex["galleries"].values()])
        wallrow = set()
        for d in range(cave["drop"] + 1, cave["drop"] + 1 + (max(g["slot"] for g in cave["galleries"]) + 1)
                       * (spec["geometry"]["gallery_width"] + 2)):
            for s in (-1, 1):
                x, z = xz(s * (hw + 1), d)
                wallrow |= {(x, y, z) for y in range(ex["yh"] + 1, ex["yh"] + PH + 1)}
        # 'or in its near end wall (d = drop, |u| <= passage_half_width, the hall's air height)' (the rules text,
        # 2026-10-20: the Fossick galleries, whose every slot holds a gallery on both sides)
        for u in range(-hw, hw + 1):
            x, z = xz(u, cave["drop"])
            wallrow |= {(x, y, z) for y in range(ex["yh"] + 1, ex["yh"] + PH + 1)}
        op = opening_cells(cave)
        if not op <= wallrow:
            probs.append("%s: %d opening cell(s) are not in the hall's wall, e.g. %s" % (cid, len(op - wallrow), sorted(op - wallrow)[0]))
        if op & gal:
            probs.append("%s: the opening cuts into a gallery at %s" % (cid, sorted(op & gal)[0]))
        build = apply_lines({}, fns.get("build_%s" % cid, []))
        shut = sorted(c for c in op if build.get(c) not in PASS)
        if shut:
            probs.append("%s: the cave's build leaves %d opening cell(s) closed, e.g. %s %s" % (cid, len(shut), shut[0], build.get(shut[0])))
        ax, az = cave["entry"]["anchor"]
        mouth = []
        for (x, y, z) in build:
            d = (ax - x) if cave["entry"]["front"] == "east" else (x - ax) if cave["entry"]["front"] == "west" else \
                (z - az) if cave["entry"]["front"] == "north" else (az - z)
            if d < cave["drop"]:
                mouth.append((x, y, z))
        if mouth:
            probs.append("%s: the build still writes %d cell(s) where the old mouth and incline were (d < %d), e.g. %s"
                         % (cid, len(mouth), cave["drop"], sorted(mouth)[0]))
        hl = host_lines(cave)
        cols = {(x, z) for x, _y, z in build}
        hostw = {c: b for c, b in apply_lines({}, [l for l in hl if _touches(l, cols)]).items() if (c[0], c[2]) in cols}
        closed = sorted(c for c in op if hostw.get(c) not in PASS)
        if closed:
            probs.append("%s: the host's earthwork leaves %d opening cell(s) not air, e.g. %s" % (cid, len(closed), closed[0]))
        both = sorted(c for c in hostw if c in build and c not in op)
        if both:
            probs.append("%s: the host's earthwork and the cave's build both write %d cell(s), e.g. %s (%s / %s)"
                         % (cid, len(both), both[0], hostw[both[0]], build[both[0]]))
    return probs


def _touches(line, cols):
    """Whether a fill or setblock line's x/z box meets any of cols (a cheap prefilter before replaying it)."""
    t = line.split()
    if not t or t[0] not in ("fill", "setblock"):
        return False
    if t[0] == "setblock":
        return (int(t[1]), int(t[3])) in cols
    x0, x1 = sorted((int(t[1]), int(t[4])))
    z0, z1 = sorted((int(t[3]), int(t[6])))
    return any(x0 <= x <= x1 and z0 <= z <= z1 for (x, z) in cols)


def old_entry_cells(rt, ground):
    """{(x, y, z): role} of the retired mouth as the rules text defines it, read from the retired record's frozen spec and
    cave: the mouth row d = 0 and the incline d = 1 .. drop, 3 wide ('stair n at y0 - n + 1'), passage_height of air over
    each, the posts at |u| = hw + 1 on the mouth row and the beam over it. Cuttings' extra air and the skin are not
    modelled: this is the core the restore must cover, not all it may write."""
    fs, fc = rt["frozen_spec"], rt["frozen_cave"]
    geo = fs["geometry"]
    hw, PH = geo["passage_half_width"], geo["passage_height"]
    xz = frame(fc["entry"]["anchor"], fc["entry"]["front"])
    row = sorted(int(ground(*xz(u, -1))) for u in range(-hw - 1, hw + 2))
    y0 = row[(len(row) - 1) // 2]
    out = {}
    for d in range(0, fc["drop"] + 1):
        ft = y0 if d == 0 else y0 - d + 1
        for u in range(-hw, hw + 1):
            x, z = xz(u, d)
            out[(x, ft, z)] = "floor" if d == 0 else "stair"
            for y in range(ft + 1, ft + PH + 1):
                out[(x, y, z)] = "air"
    for u in (-hw - 1, hw + 1):
        x, z = xz(u, 0)
        for y in range(y0 + 1, y0 + PH + 1):
            out[(x, y, z)] = "post"
    for u in range(-hw - 1, hw + 2):
        x, z = xz(u, 0)
        out[(x, y0 + PH + 1, z)] = "beam"
    return out, y0


def in_box(c, box):
    """The selector box semantics stated at the top: x .. x + dx + 1 (a block cell inside it, here)."""
    x0, y0, z0, x1, y1, z1 = box
    return x0 <= c[0] <= x1 and y0 <= c[1] <= y1 and z0 <= c[2] <= z1


def reroute_problems(spec, fns, ground):
    """A cave with a retired entry (step R9OCR): its restore puts every core cell of the old mouth (old_entry_cells, the
    rules text over the frozen record) back to the record's terrain on the heightmap's ground, except the hall's new
    end wall (the cells of the drop row at the hall's air height, which become the cave's wall), and writes no cell of
    the hall or a gallery; it runs only behind probes on the old frame and with nobody held; every cell it or the
    passage writes solid is inside a held box; the passage is gated on the opening not yet being air, leaves the
    opening air, writes nothing of the hall or a gallery but the opening, and writes exactly what the host's earthwork
    leaves in those cells (so a live world rerouted matches a fresh export)."""
    probs = []
    for cave in spec["caves"]:
        rt = cave.get("retired_entry")
        if not rt:
            continue
        cid = cave["id"]
        ent = fns.get("reroute/%s" % cid)
        rst = fns.get("reroute/%s_restore" % cid)
        con = fns.get("reroute/%s_connect" % cid)
        if not (ent and rst and con):
            probs.append("%s: the reroute's entry, restore or connect function is missing" % cid)
            continue
        ex = expected(spec, cave, ground)
        core, _y0 = old_entry_cells(rt, ground)
        restored = apply_lines({}, rst)
        t = rt["terrain"]
        hw, PH = spec["geometry"]["passage_half_width"], spec["geometry"]["passage_height"]
        endwall = set()
        for u in range(-hw, hw + 1):
            x, z = ex["xz"](u, cave["drop"])
            endwall |= {(x, y, z) for y in range(ex["yh"] + 1, ex["yh"] + PH + 1)}
        op = opening_cells(cave)
        wrong = []
        for c in sorted(core):
            g = ground(c[0], c[2])
            # an end-wall cell that is the opening (the near end wall is where the host's passage comes in) is air
            want = ("minecraft:air" if c in endwall and c in op else base(cave["wall"]) if c in endwall
                    else base(t["deep"]) if c[1] <= g - 3 else base(t["under"])
                    if c[1] <= g - 1 else base(t["surface"]) if c[1] == g else "minecraft:air")
            if restored.get(c) != want:
                wrong.append((c, restored.get(c), want))
        if wrong:
            probs.append("%s: the restore leaves %d core cell(s) of the old mouth wrong, e.g. %s is %s, want %s"
                         % (cid, len(wrong), wrong[0][0], wrong[0][1], wrong[0][2]))
        keep = hall_cells(spec, cave, ex) | set().union(*[e["body"] | e["shell"] for e in ex["galleries"].values()])
        hit = sorted(c for c in restored if c in keep)
        if hit:
            probs.append("%s: the restore writes %d cell(s) of the hall or a gallery, e.g. %s" % (cid, len(hit), hit[0]))
        # the gate: tags, the count, then the calls behind `matches 0`
        body = [l for l in ent if l and not l.startswith("#")]
        holder = None
        boxes = []
        for l in body:
            m = re.fullmatch(r"execute store result score (#\S+) cobblers_chunk_look if entity @a\[tag=(\S+)\]", l)
            if m:
                holder = m.group(1)
            if l.startswith("tag @a[") and holder is None:
                k_, args = selector(l.split(" add ")[0][4:])
                boxes.append(sel_box(args))
        if holder is None:
            probs.append("%s: the reroute never counts the held players" % cid)
            continue
        calls_r = [l for l in body if l.endswith("run function %sreroute/%s_restore" % (FN, cid))]
        calls_c = [l for l in body if l.endswith("run function %sreroute/%s_connect" % (FN, cid))]
        gate = "execute if score %s cobblers_chunk_look matches 0 " % holder
        if not calls_r or not all(l.startswith(gate + "if block ") for l in calls_r):
            probs.append("%s: the restore is not called only behind the held count and a probe" % cid)
        for l in calls_r:
            m = re.match(re.escape(gate) + r"if block (-?\d+) (-?\d+) (-?\d+) (\S+) run", l)
            if not m:
                continue
            p = tuple(int(m.group(i)) for i in (1, 2, 3))
            if core.get(p) not in ("beam", "stair") or m.group(4) not in (base(rt["frozen_cave"]["timber"]), base(rt["frozen_cave"]["stair"])):
                probs.append("%s: probe %s %s is not the old frame's beam or a first stair" % (cid, p, m.group(4)))
            elif restored.get(p) == m.group(4):
                probs.append("%s: the restore leaves the probe %s showing: a second run would restore again" % (cid, p))
        hl = host_lines(cave)
        probe = host_of(cave).get("probe")
        if not probe:
            if len(calls_c) != 1 or not re.fullmatch(re.escape(gate) + r"unless block (-?\d+) (-?\d+) (-?\d+) minecraft:air run .*", calls_c[0]):
                probs.append("%s: the passage is not called once behind the held count and the opening's air" % cid)
            else:
                m = re.match(re.escape(gate) + r"unless block (-?\d+) (-?\d+) (-?\d+)", calls_c[0])
                if tuple(int(m.group(i)) for i in (1, 2, 3)) not in op:
                    probs.append("%s: the passage's gate cell is not in the opening" % cid)
        else:
            # a host that declares entry.host.probe gates its passage on that block being missing: the gate names it, the
            # host's earthwork (data/placements.json, replayed here) leaves exactly it there, and neither the old mouth,
            # nor the restore, nor the cave's build puts it there, or the passage would never be cut in the live world
            pc, pb = tuple(probe[:3]), probe[3]
            want_gate = re.escape(gate) + r"unless block %d %d %d %s run .*" % (pc + (re.escape(pb),))
            if len(calls_c) != 1 or not re.fullmatch(want_gate, calls_c[0]):
                probs.append("%s: the passage is not called once behind the held count and the probe %s %s's absence"
                             % (cid, list(pc), pb))
            left = apply_lines({}, [l for l in hl if _touches(l, {(pc[0], pc[2])})]).get(pc)
            if left != pb:
                probs.append("%s: the host's earthwork leaves %s at the probe %s, not %s: the passage would be cut on "
                             "every run" % (cid, left, list(pc), pb))
            if pc in core and core[pc] in ("beam", "post", "stair", "floor") or restored.get(pc) == pb \
                    or apply_lines({}, fns.get("build_%s" % cid, [])).get(pc) == pb:
                probs.append("%s: the probe %s is a cell the old mouth, the restore or the cave's build writes" % (cid, list(pc)))
        cut = apply_lines({}, con)
        shut = sorted(c for c in op if cut.get(c) not in PASS)
        if shut:
            probs.append("%s: the passage leaves %d opening cell(s) closed, e.g. %s" % (cid, len(shut), shut[0]))
        hit = sorted(c for c in cut if c in keep and c not in op)
        if hit:
            probs.append("%s: the passage writes %d cell(s) of the hall or a gallery, e.g. %s" % (cid, len(hit), hit[0]))
        unheld = sorted(c for c, b in list(restored.items()) + list(cut.items())
                        if b not in PASS and not any(in_box(c, bx) for bx in boxes))
        if unheld:
            probs.append("%s: %d solid write(s) stand outside every held box (a player there would be buried), e.g. %s"
                         % (cid, len(unheld), unheld[0]))
        cols = {(x, z) for x, _y, z in cut}
        fresh = apply_lines({}, [l for l in hl if _touches(l, cols)])
        differ = sorted(c for c, b in cut.items() if fresh.get(c) != b)
        if differ:
            probs.append("%s: the passage writes %d cell(s) differently from what the host's earthwork leaves, e.g. %s "
                         "(%s / %s): a rerouted world would not match a fresh export" % (cid, len(differ), differ[0],
                                                                                      cut[differ[0]], fresh.get(differ[0])))
    return probs


# ------------------------------------------------------------------ keeping clear, against a full checkout

WRITE = re.compile(r"\b(fill|setblock|clone)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+))?")
PLACE = re.compile(r"\bplace\s+(template|structure|feature|jigsaw)\s+\S+\s+(?:\S+\s+\S+\s+)?(-?\d+)\s+(-?\d+)\s+(-?\d+)")


def pack_columns(fns):
    cols = set()
    for ls in fns.values():
        for l in ls:
            for m in WRITE.finditer(l):
                x0, z0 = int(m.group(2)), int(m.group(4))
                x1, z1 = (int(m.group(5)), int(m.group(7))) if m.group(5) else (x0, z0)
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        cols.add((x, z))
    return cols


def seg_dist(px, pz, a, b):
    ax, az = a[0], a[1]
    bx, bz = b[0], b[1]
    vx, vz = bx - ax, bz - az
    L = vx * vx + vz * vz
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * vx + (pz - az) * vz) / L))
    return math.hypot(px - ax - t * vx, pz - az - t * vz)


def rect_dist(px, pz, x0, z0, x1, z1):
    dx = max(x0 - px, 0, px - x1)
    dz = max(z0 - pz, 0, pz - z1)
    return max(dx, dz)


def cave_functions(spec, fns, cave):
    """The functions that write one cave's blocks: its build and its galleries' rock and variants."""
    gids = [g["id"] for g in cave["galleries"]]
    return {k: v for k, v in fns.items() if k == "build_%s" % cave["id"]
            or any(k.startswith("galleries/%s_" % gid) for gid in gids)}


def other_pack_writes(packs_dir, own="cobblers_mining_caves"):
    """[(x0, z0, x1, z1, why)] of every absolute fill/setblock/clone box and placed-structure origin in every other pack."""
    out = []
    packs = Path(packs_dir)
    for pd in sorted(p for p in packs.iterdir() if p.is_dir() and p.name != own):
        for f in (pd / "data").rglob("*.mcfunction") if (pd / "data").is_dir() else []:
            text = f.read_text(encoding="utf-8", errors="replace")
            for m in WRITE.finditer(text):
                ax, az = int(m.group(2)), int(m.group(4))
                bx, bz = (int(m.group(5)), int(m.group(7))) if m.group(5) else (ax, az)
                out.append((min(ax, bx), min(az, bz), max(ax, bx), max(az, bz), "write", "%s/%s" % (pd.name, f.name)))
            for m in PLACE.finditer(text):
                ax, az = int(m.group(2)), int(m.group(4))
                out.append((ax, az, ax, az, "place " + m.group(1), "%s/%s" % (pd.name, f.name)))
    return out


def authored_xz(skip_settlement=None, skip_placement=None):
    """[(x, z, file)]: every x/z any data/*.json but data/mining_caves.json authors, swept rather than listed (a trainer's
    seat, a Habitat Block, a portal, a resident, a dungeon rip, a shrine: whatever a file places, whether or not this
    audit knows the system). Read as keep_clear.why states the rule: x/z dicts, [x, z], [x, y, z] (both ways) and
    [x0, z0, x1, z1] boxes (corners, edge middles, centre). The host's own records in data/placements.json (its
    settlement and its earthwork) are skipped by key, not by coordinate."""
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    out = []

    def walk(o, f):
        if isinstance(o, dict):
            if num(o.get("x")) and num(o.get("z")):
                out.append((o["x"], o["z"], f))
            for k, v in o.items():
                if isinstance(k, str) and k.startswith("nearest_"):
                    continue                              # a note of ANOTHER place's point
                walk(v, f)
        elif isinstance(o, list):
            if len(o) == 2 and all(num(v) for v in o):
                out.append((o[0], o[1], f))
            elif len(o) == 3 and all(num(v) for v in o):
                out.extend([(o[0], o[2], f), (o[0], o[1], f)])
            elif len(o) == 4 and all(num(v) for v in o) and o[2] >= o[0] and o[3] >= o[1]:
                out.extend((x, z, f) for x in (o[0], (o[0] + o[2]) / 2, o[2]) for z in (o[1], (o[1] + o[3]) / 2, o[3]))
            else:
                for v in o:
                    walk(v, f)

    for p in sorted((ROOT / "data").glob("*.json")):
        if p.name == "mining_caves.json":
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        if p.name == "placements.json":
            doc = {"settlements": {k: v for k, v in doc["settlements"].items() if k != skip_settlement},
                   "placements": [q for q in doc["placements"] if q.get("id") != skip_placement]}
        walk(doc, p.name)
    return out


def authored_rule(note, X, Z, box, host, need):
    """The nearest Euclidean distance from any of a host's columns to any x/z another data file authors. Every trainer
    sight distance the data records is 8 or under, so a seat this far off cannot see across the host either."""
    import numpy as np
    x0, z0, x1, z1 = box
    shared = set((host.get("keep_clear_shared") or {}).get("files") or [])
    note("an x/z another data file authors", 10 ** 6, need, "none within the box", "euclidean")
    for (ax, az, f) in authored_xz(host.get("settlement"), host.get("placement")):
        if not (x0 <= ax <= x1 and z0 <= az <= z1) or f in shared:
            continue
        note("an x/z another data file authors", float(np.hypot(X - ax, Z - az).min()), need,
             "%s (%s, %s)" % (f, ax, az), "euclidean")


def keep_clear(spec, fns, inputs_root, ground, R=64):
    """{(cave, rule): (nearest distance, the rule's distance, the nearest thing, metric)}: every column the cave's
    functions write against every keep-clear rule, nearest first. A distance over R is reported as R + 1."""
    import numpy as np
    from PIL import Image
    ir = Path(inputs_root)
    kc = spec["keep_clear"]
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    legs = [("leg %s-%s" % (l.get("from"), l.get("to")), l.get("polyline") or [])
            for l in json.loads((ir / "derived" / "routes" / "critical_legs.json").read_text(encoding="utf-8"))["legs"]]
    paths = list(json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"].items())
    routes = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))["routes"]
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
    others = other_pack_writes(ir / "build" / "datapacks")
    paint = ir / "build" / "paint"
    man = json.loads((paint / "manifest.json").read_text(encoding="utf-8"))
    changed = np.load(ir / "derived" / "water_shape" / "changed.npy", mmap_mode="r")
    res = {}
    # each cave's own writes, and (2026-10-20) a host cave's host earthwork as a subject of its own: the hill a cave is
    # entered by stands on the surface, so it must not cover a route, a placement, a portal, a Habitat Block or a
    # trainer's seat and sight line any more than the cave may
    subjects = []
    for cave in spec["caves"]:
        subjects.append((cave, cave["id"], pack_columns(cave_functions(spec, fns, cave)), False))
        if host_of(cave):
            subjects.append((cave, cave["id"] + " host", pack_columns({"host": host_lines(cave)}), True))
    for cave, key, colset, is_host in subjects:
        cols = np.array(sorted(colset))
        X, Z = cols[:, 0], cols[:, 1]
        x0, z0, x1, z1 = int(X.min()) - R, int(Z.min()) - R, int(X.max()) + R, int(Z.max()) + R

        def note(rule, d, need, what, metric="chebyshev"):
            k = (key, rule)
            d = float(min(d, R + 1))
            if k not in res or d < res[k][0]:
                res[k] = (d, need, what, metric)

        def rects(rule, boxes, need):
            """boxes: [(xa, za, xb, zb, what)]: the nearest Chebyshev distance from any column to any box."""
            note(rule, R + 1, need, "none within %d" % R)
            for (xa, za, xb, zb, what) in boxes:
                if xb < x0 or xa > x1 or zb < z0 or za > z1:
                    continue
                d = np.maximum(np.maximum(xa - X, X - xb), np.maximum(za - Z, Z - zb)).clip(min=0).min()
                note(rule, d, need, what)

        def grid(rule, mask, gx0, gz0, need, what):
            """mask: a bool (z, x) array whose [0, 0] is (gx0, gz0): the nearest Chebyshev distance to a True cell."""
            zz, xx = np.nonzero(mask)
            if not len(xx):
                note(rule, R + 1, need, "none within %d" % R)
                return
            px, pz = xx + gx0, zz + gz0
            best = R + 1
            for i in range(0, len(X), 256):
                xs, zs = X[i:i + 256, None], Z[i:i + 256, None]
                best = min(best, int(np.maximum(np.abs(px[None, :] - xs), np.abs(pz[None, :] - zs)).min()))
            note(rule, best, need, what)

        fps = [(t["footprint"]["min_x"], t["footprint"]["min_z"], t["footprint"]["max_x"], t["footprint"]["max_z"], t["id"])
               for t in towns if (t.get("footprint") or {}).get("min_x") is not None]
        if not is_host:
            rects("town footprint", fps, kc["town_margin"] + 1)
        else:
            # keep_clear.why gives town_margin to "every written column" of a CAVE; a host is a surface earthwork, the
            # town's own mine entrance. It is judged only to stand outside every footprint, and its distance against the
            # caves' margin is reported for the owner's look, not passed or failed here
            rects("town footprint", fps, 1)
            rects("town footprint + the caves' town_margin (look)", fps, kc["town_margin"] + 1)
            authored_rule(note, X, Z, (x0, z0, x1, z1), host_of(cave), kc["authored_clearance"] + 1)
        rects("spawn corridor box", [(b["min_x"], b["min_z"], b["max_x"], b["max_z"], "%s %s" % (rt["id"], b.get("id")))
                                     for rt in routes for b in (rt.get("spawn_scope") or {}).get("boxes") or []],
              kc["corridor_clearance"] + 1)
        rects("placement position", [(int(p["position"]["x"]), int(p["position"]["z"]), int(p["position"]["x"]),
                                      int(p["position"]["z"]), p["id"]) for p in placements
                                     if isinstance(p.get("position"), dict) and isinstance(p["position"].get("x"), (int, float))
                                     and isinstance(p["position"].get("z"), (int, float))], kc["placement_reach"] + 1)
        # a cave entered from its host mine: the host's earthwork and its towns-pack function ARE its way in, so they
        # are judged cell by cell (host_problems: nothing shared but the opening), not by distance
        host = host_of(cave) or {}
        ew = []
        for p in placements:
            if p["id"] == host.get("placement"):
                continue
            for cmd in p.get("commands") or []:
                for m in WRITE.finditer(cmd):
                    ax, az = int(m.group(2)), int(m.group(4))
                    bx, bz = (int(m.group(5)), int(m.group(7))) if m.group(5) else (ax, az)
                    ew.append((min(ax, bx), min(az, bz), max(ax, bx), max(az, bz), p["id"]))
        rects("earthwork command", ew, kc["earthwork_gap"] + 1)
        hostfn = "cobblers_towns/%s.mcfunction" % host["settlement"] if host.get("settlement") else None
        # a host's declared sharing (entry.host.keep_clear_shared: a named exception with its why, never a smaller
        # distance) is left out of its host subject's rules only, never out of the cave's own
        spacks = set((host.get("keep_clear_shared") or {}).get("packs") or []) if is_host else set()
        # the host's own town functions are the host: its towns-pack build and after-donor function, and its prep
        # (tools/town_plan.py's prep_<settlement>, which cobblers_reapply carries)
        own = {hostfn} | ({"cobblers_towns/%s_after_donors.mcfunction" % host["settlement"],
                           "cobblers_reapply/prep_%s.mcfunction" % host["settlement"]}
                          if is_host and host.get("settlement") else set())
        rects("another pack's write", [(a, b, c, d, w) for a, b, c, d, k, w in others if k == "write" and w not in own
                                       and w.split("/")[0] not in spacks], kc["pack_gap"] + 1)
        rects("another pack's placed structure origin", [(a, b, c, d, w) for a, b, c, d, k, w in others if k != "write"],
              TEMPLATE_HINT)
        note("route path or leg", R + 1, kc["road_clear"], "none within %d" % R, "euclidean")
        for name, pts in legs + paths:
            for a, b in zip(pts, pts[1:] or pts):
                if max(a[0], b[0]) < x0 or min(a[0], b[0]) > x1 or max(a[1], b[1]) < z0 or min(a[1], b[1]) > z1:
                    continue
                vx, vz = b[0] - a[0], b[1] - a[1]
                L = vx * vx + vz * vz
                t = np.zeros(len(X)) if L == 0 else (((X - a[0]) * vx + (Z - a[1]) * vz) / L).clip(0, 1)
                note("route path or leg", float(np.hypot(X - a[0] - t * vx, Z - a[1] - t * vz).min()),
                     kc["road_clear"], name, "euclidean")
        wet = np.zeros((z1 - z0 + 1, x1 - x0 + 1), bool)
        for w in man["water"]:
            mm = np.asarray(Image.open(paint / w["levels" if "levels" in w else "mask"])) > 0
            h_, w_ = mm.shape
            za, xa = max(z0, w["z"]), max(x0, w["x"])
            zb, xb = min(z1 + 1, w["z"] + h_), min(x1 + 1, w["x"] + w_)
            if za < zb and xa < xb:
                wet[za - z0:zb - z0, xa - x0:xb - x0] |= mm[za - w["z"]:zb - w["z"], xa - w["x"]:xb - w["x"]]
        grid("painted water (build/paint)", wet, x0, z0, kc["water_reach"] + 1, "build/paint/manifest.json water")
        sea = int(json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"])
        low = np.array([[ground(x, z) <= sea for x in range(x0, x1 + 1, 1)] for z in range(z0, z1 + 1)])
        grid("the sea (heightmap ground <= sea level)", low, x0, z0, kc["water_reach"] + 1, "y%d" % sea)
        grid("a column the water export changes", np.array(changed[z0:z1 + 1, x0:x1 + 1]) > 0, x0, z0,
             kc["water_changed_reach"] + 1, "derived/water_shape/changed.npy")
    return res


TEMPLATE_HINT = 25        # a placed structure's origin nearer than this is reported for a look, not judged (its size
                          # is in the template, which this audit does not read)


# ------------------------------------------------------------------ the economy

def economy(spec, bank_path=ROOT / "data" / "bank.json"):
    bank = json.loads(Path(bank_path).read_text(encoding="utf-8"))
    price = {e["item"]: e["price"] for e in bank["buys"]}
    per_hour = 72000 / spec["restore"]["period_ticks"]
    out = {}
    for cave in spec["caves"]:
        yl = spec["yields"][cave["yield"]]
        plain = fort = 0.0
        missing = []
        for ore, y in yl["ores"].items():
            kind = next(k for k in DROPS if k in ore)
            item, mean, f3 = DROPS[kind]
            if item not in price:
                missing.append(item)
                continue
            plain += y["mean"] * mean * price[item]
            fort += y["mean"] * mean * f3 * price[item]
        n = len(cave["galleries"])
        out[cave["id"]] = {"per_reset": round(plain, 1), "per_reset_fortune3": round(fort, 1),
                           "resets_per_hour_server": n * per_hour,
                           "server_hour": round(n * per_hour * plain), "server_hour_fortune3": round(n * per_hour * fort),
                           "player_hour_at_10_min": round(6 * plain), "unpriced": missing,
                           "diamonds_per_hour_server": n * per_hour * sum(y["mean"] for o, y in yl["ores"].items() if "diamond" in o)}
    return out


# ------------------------------------------------------------------ the CLI

def cached(g):
    memo = {}

    def ground(x, z):
        k = (int(x), int(z))
        if k not in memo:
            memo[k] = int(g(*k))
        return memo[k]
    return ground


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--inputs-root", help="a full checkout (build/datapacks, build/paint, derived/routes, derived/water_shape)")
    ap.add_argument("--no-walk", action="store_true")
    ap.add_argument("--no-run", action="store_true", help="skip the command model (it takes a minute)")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as G
    ground = cached(G.Ground())                  # the canonical heightmap, rounded (tools/ground.py)
    spec = load()
    fns, tag = read_pack(a.pack)
    probs = static_problems(spec, fns, tag, ground)
    print("static: %d problem(s)" % len(probs))
    hp = host_problems(spec, fns, ground) + reroute_problems(spec, fns, ground)
    print("host entry and retired mouth: %d problem(s)" % len(hp))
    probs += hp
    if not a.no_run:
        rp = run_problems(spec, fns, tag, ground)
        print("command model: %d problem(s)" % len(rp))
        probs += rp
    if not a.no_walk:
        wp = walk_problems(spec, fns, ground)
        print("walk: %d problem(s)" % len(wp))
        probs += wp
    if a.inputs_root:
        for (cid, rule), (d, need, what, metric) in sorted(keep_clear(spec, fns, a.inputs_root, ground).items()):
            look = rule.endswith("structure origin") or rule.endswith("(look)")
            bad = d < need and not look
            print("keep clear %-13s %-42s nearest %5.1f (%s) need >= %d  %s%s" % (
                cid, rule, d, metric, need, what, "  PROBLEM" if bad else "  LOOK" if look and d < need else ""))
            if bad:
                probs.append("keep clear %s: %s at %.1f, under %d (%s)" % (cid, rule, d, need, what))
    for cid, e in economy(spec).items():
        print("economy %s: %s" % (cid, json.dumps(e)))
    for p in probs:
        print("PROBLEM:", p)
    print("mining caves audit: %d problem(s)" % len(probs))
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
