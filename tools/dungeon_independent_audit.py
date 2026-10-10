#!/usr/bin/env python3
"""The independent audit of the dungeon pack: can a run be finished, and can a player always leave?

Reads the GENERATED pack (the .mcfunction text, the NPC class files and the victory callback) and the authored records
(data/dungeons.json for each room's kind and gate, data/blackout.json for the exempt tag). It never calls the builders'
own geometry, walk check or plan (tools/dungeon_rooms.py plan()/layout(), tools/dungeon_grid.py, dungeon.points());
the one thing borrowed is tools/dungeon_clock.required(), the formula of DUNGEON_ROOMS.md 7 (paces, fight minutes),
fed with walks this audit measures itself.

How (an audit that shares the builder's derivation checks nothing, CLAUDE.md):
  * a block model replayed from the shell's own fill/setblock lines, plus every room's reset, on a numpy grid; the
    solid/passable/climbable table is this file's own (BLOCKS below), unknown ids are solid;
  * a 2-high, 1-wide player who steps up 1 (not onto a fence, wall or bars), drops any height, climbs vines and swims,
    and jumps a flat gap of up to 3 or a rising gap of up to 2 (DUNGEONS.md V6, the design rule);
  * the gates as the generated `clear` functions open them, run by this file's own command interpreter; a cell a
    room's clear opens is shut in every state before that room is cleared, so one minimax walk answers every state;
  * the hooks by SIMULATION: the real keeper runs once a pass with a simulated player walking the dungeon; a battle
    the player starts is won through the real victory callback, wild Pokemon are defeated by removing them, puzzles
    are solved by search over their own controls.

Pass 2 (AUDIT2, DUNGEON_ROOMS.md 1a and 9), all read from the generated text and walked on this file's own graph:
  * EVERY slot is walked from its own shell (a variant -- mirror, seed, swap, order -- is a different dungeon); rooms
    are found by their own shell boxes in x, y and z (`room_at`), never by x; a slot's records are its variant's as
    1a describes them (`slot_records`, this file's reading, not the kit's resolve());
  * forks: each route ALONE (the others' boxes solid) reaches the far rip and traps no one in its own gate order; the
    clock pays for the slowest choice of routes and never for side rooms; side rooms are walked back out of (the trap
    walk covers every reached cell);
  * secrets: the rift pick (its generated can_break) breaks nothing but seams and cracked faces; a broken face opens
    a chamber in its own room, walked back out of, and the slot reset puts the face back; a balcony alcove is reached
    by jumping and not by a player who never jumps; each relic's pickup (`relic_<id>` in the tick) is reached with its
    trick and not without; shortcuts open only from their far room, are never needed (the far rip is walked to with
    them shut), trap no one when open, and the slot reset shuts them;
  * set pieces: the member walked through the room, waiting at every fourth cell, and the pass holders run to their
    end with the member parked outside every box; in every block state seen: no block where a player may stand, every
    cell a player can be on reaches a ledge, a door or a teleporting floor, new water never stands on a ledge or runs
    on into an open cell, standing on a ledge the way out is not cut, and the slot reset and the piece's own
    restore/drain give back the room exactly;
  * parkour v2: every ledge stood on, the chasm's lowest floor all catch, each ledge reached from the one before
    without falling, and the fork two ways (with every platform of the first taken away, a second still finishes);
  * life: every ambient spot (the storage table life/load writes) stands in its own room, on a cell a body stands on,
    not in a doorway or the cell beside one; the room's reset, the slot's free and its tend (a stale run) remove them,
    simulated through the generated storage walker;
  * the return margin: m/margin run on the member gives the warning's estimate; the real walk back (this graph, every
    gate open, at the margin's own pace) is compared per room: MARGIN names where the warning comes late.

A swimmer at the water's top block climbs onto ground one over a step (two over the water block): this file's
judgement of 1.21 (the flood's ledges rely on it), not run in game.

Exit status 1 on any finding. What this does NOT cover: anything Minecraft decides at runtime (whether Cobblemon
removes a fainted wild Pokemon, whether `runmolang` and `start_battle` behave as EXP-078 assumes, collision of
partial blocks, a sprint player outrunning a one-second keeper pass, whether a walking player outruns the collapse --
its pace against the walk's is not modelled, only that a fall is caught and the floor comes back), co-op (members_max
1), fights' balance, where the kit's own trail runs (a Pokemon on the walked line is not checked, only doorways), and
the route-and-gate states of two forks taken in different orders (each choice of routes is walked on its own).
"""
import argparse
import collections
from array import array
import heapq
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "dungeons.json"
BLACKOUT = ROOT / "data" / "blackout.json"
FN = "cobblers:dungeons/"
CHAIN_LIMIT = 65536            # vanilla gamerule maxCommandChainLength default
ENTITY_REACH = 3.0             # 1.21 player.entity_interaction_range default
BLOCK_REACH = 4.5              # 1.21 player.block_interaction_range default
UNITS_PER_S = 200               # DUNGEONS.md 2.1 (the owner, 2026-10-10): tenth-ticks, 12,000 units a minute at x1
EYE = 1.62
PLAYER = "P"                   # the simulated player's name and uuid

# ------------------------------------------------------------------------------------------------- the block table
# This file's own judgement of 1.21.1 collision, by base id. Anything not named is SOLID (the safe default for "can a
# player get out": an unknown block can only make a way look shut, which the audit then reports and a reader checks).
SOLID, TALL, CLIMB, WATER, NOSUP, HAZARD = 1, 2, 4, 8, 16, 32
_PASS = """air cave_air void_air light short_grass tall_grass fern large_fern dead_bush seagrass tall_seagrass kelp
kelp_plant glow_lichen moss_carpet hanging_roots spore_blossom lever torch wall_torch soul_torch soul_wall_torch
redstone_torch redstone_wall_torch redstone_wire rail powered_rail detector_rail activator_rail tripwire string
candle sea_pickle small_dripleaf dandelion poppy blue_orchid allium azure_bluet red_tulip orange_tulip white_tulip
pink_tulip oxeye_daisy cornflower lily_of_the_valley torchflower pink_petals sunflower lilac rose_bush peony
oak_sapling spruce_sapling birch_sapling jungle_sapling acacia_sapling dark_oak_sapling mangrove_propagule
cherry_sapling brown_mushroom red_mushroom crimson_roots warped_roots nether_sprouts sugar_cane snow
lily_pad""".split()
_CLIMB = ("vine cave_vines cave_vines_plant ladder scaffolding weeping_vines weeping_vines_plant twisting_vines "
          "twisting_vines_plant").split()
_TALL_SUFFIX = ("_fence", "_wall", "_fence_gate")
_TALL = {"iron_bars", "glass_pane", "chain"} | {c + "_stained_glass_pane" for c in
         "white orange magenta light_blue yellow lime pink gray light_gray cyan purple blue brown green red black".split()}
_HAZARD = {"lava", "fire", "soul_fire", "magma_block", "campfire", "soul_campfire", "cactus", "sweet_berry_bush",
           "powder_snow", "wither_rose", "pointed_dripstone", "cobweb"}
_NOSUP = {"big_dripleaf"}       # stood on, it tilts and drops you; walked into, it blocks


def base_id(block):
    b = block.split("[", 1)[0].split("{", 1)[0]
    return b.split(":", 1)[1] if ":" in b else b


def block_flags(block):
    b = base_id(block)
    if b == "water":
        return WATER
    if b in _PASS or b.endswith("_carpet") or b.endswith("_button") or b.endswith("_pressure_plate") \
            or b.endswith("_candle") or b.endswith("_sign") and "wall" in b:
        return 0
    if b in _CLIMB:
        return CLIMB
    f = SOLID
    if b in _TALL or b.endswith(_TALL_SUFFIX):
        f |= TALL
    if b in _HAZARD:
        f |= HAZARD
    if b in _NOSUP:
        f |= NOSUP
    return f


def norm_block(s):
    """minecraft:<id> for a bare id; states and NBT kept as written."""
    head = re.match(r"[^\[{]*", s).group(0)
    return s if ":" in head else "minecraft:" + s


def states_of(block):
    m = re.search(r"\[([^\]]*)\]", block)
    if not m:
        return {}
    return dict(kv.split("=", 1) for kv in m.group(1).split(",") if "=" in kv)


DEFAULT_STATES = {"powered": "false"}


def block_matches(have, pred):
    """`if block` semantics: same id, and every state the predicate names holds (missing ones take vanilla defaults)."""
    if base_id(have) != base_id(pred) or pred.startswith("#"):
        return False
    hs = states_of(have)
    for k, v in states_of(pred).items():
        if hs.get(k, DEFAULT_STATES.get(k)) != v:
            return False
    m = re.search(r"\{(.*)\}$", pred)
    return not m or m.group(1) in have


# ------------------------------------------------------------------------------------------------- the pack
class Pack:
    def __init__(self, files):
        self.files = files
        self.fns = {}
        for rel, body in files.items():
            m = re.match(r"data/([^/]+)/function/(.+)\.mcfunction$", rel)
            if m:
                self.fns["%s:%s" % (m.group(1), m.group(2))] = [ln.strip() for ln in body.splitlines()]

    @classmethod
    def from_dir(cls, path):
        path = Path(path)
        return cls({str(p.relative_to(path)).replace("\\", "/"): p.read_text(encoding="utf-8")
                    for p in path.rglob("*") if p.is_file()})

    def lines(self, fid):
        return [ln for ln in self.fns.get(fid, []) if ln and not ln.startswith("#")]

    def has(self, fid):
        return fid in self.fns


def tokens(s):
    """Split a command at top-level spaces, keeping JSON, NBT, selectors and quoted strings whole."""
    out, cur, depth, quote, esc = [], [], 0, None, False
    for ch in s:
        if esc:
            cur.append(ch)
            esc = False
            continue
        if ch == "\\":
            cur.append(ch)
            esc = True
            continue
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            cur.append(ch)
            continue
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        if ch == " " and depth == 0:
            if cur:
                out.append("".join(cur))
                cur = []
            continue
        cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def split_args(s):
    out, cur, depth = [], [], 0
    for ch in s:
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    if cur:
        out.append("".join(cur))
    return [a.split("=", 1) if "=" in a else [a, ""] for a in out]


def snbt(s):
    """The SNBT the pack writes into storage: compounds, lists, quoted strings, numbers (suffix dropped), bare words."""
    pos = [0]

    def ws():
        while pos[0] < len(s) and s[pos[0]] in " \t":
            pos[0] += 1

    def val():
        ws()
        c = s[pos[0]]
        if c == "{":
            pos[0] += 1
            out = {}
            ws()
            if s[pos[0]] == "}":
                pos[0] += 1
                return out
            while True:
                ws()
                if s[pos[0]] in "\"'":
                    k = string()
                else:
                    m = re.compile(r"[A-Za-z0-9_.+-]+").match(s, pos[0])
                    k = m.group(0)
                    pos[0] = m.end()
                ws()
                assert s[pos[0]] == ":", s[pos[0]:pos[0] + 20]
                pos[0] += 1
                out[k] = val()
                ws()
                if s[pos[0]] == ",":
                    pos[0] += 1
                    continue
                assert s[pos[0]] == "}", s[pos[0]:pos[0] + 20]
                pos[0] += 1
                return out
        if c == "[":
            pos[0] += 1
            out = []
            ws()
            if s[pos[0]] == "]":
                pos[0] += 1
                return out
            while True:
                out.append(val())
                ws()
                if s[pos[0]] == ",":
                    pos[0] += 1
                    continue
                assert s[pos[0]] == "]", s[pos[0]:pos[0] + 20]
                pos[0] += 1
                return out
        if c in "\"'":
            return string()
        m = re.compile(r"[A-Za-z0-9_.+-]+").match(s, pos[0])
        pos[0] = m.end()
        w = m.group(0)
        n = re.fullmatch(r"(-?\d+)[bBsSlL]?", w)
        if n:
            return int(n.group(1))
        n = re.fullmatch(r"(-?\d*\.?\d+)[fFdD]?", w)
        if n:
            return float(n.group(1))
        return {"true": 1, "false": 0}.get(w, w)

    def string():
        q = s[pos[0]]
        pos[0] += 1
        out = []
        while s[pos[0]] != q:
            if s[pos[0]] == "\\":
                pos[0] += 1
            out.append(s[pos[0]])
            pos[0] += 1
        pos[0] += 1
        return "".join(out)
    return val()


def nbt_path(path):
    """`a.b[0].c` -> ["a", "b", 0, "c"]."""
    out = []
    for part in path.split("."):
        m = re.match(r"([^\[]*)((?:\[-?\d+\])*)$", part)
        if m.group(1):
            out.append(m.group(1))
        out += [int(v) for v in re.findall(r"\[(-?\d+)\]", m.group(2))]
    return out


def in_range(v, rng):
    if v is None:
        return False
    if ".." in rng:
        lo, hi = rng.split("..")
        return (lo == "" or v >= float(lo)) and (hi == "" or v <= float(hi))
    return v == float(rng)


def sel_box(args):
    """A selector's x/y/z/dx/dy/dz as the inclusive-of-blocks volume vanilla tests: [x, x+dx+1)."""
    d = dict((k, v) for k, v in args)
    if not any(k in d for k in ("dx", "dy", "dz")):
        return None
    x, y, z = float(d["x"]), float(d["y"]), float(d["z"])
    out = []
    for o, k in ((x, "dx"), (y, "dy"), (z, "dz")):
        s = float(d.get(k, 0))
        out.append((o + min(s, 0), o + max(s, 0) + 1))
    return out


def hits_box(pos, box, w=0.6, h=1.8):
    (x0, x1), (y0, y1), (z0, z1) = box
    px, py, pz = pos
    return px - w / 2 < x1 and px + w / 2 > x0 and py < y1 and py + h > y0 and pz - w / 2 < z1 and pz + w / 2 > z0


def box_dist(p, lo, hi):
    return math.sqrt(sum(max(lo[i] - p[i], 0, p[i] - hi[i]) ** 2 for i in range(3)))


# ------------------------------------------------------------------------------------------------- the world
class World:
    def __init__(self, lo, hi):
        self.lo = lo
        self.shape = tuple(hi[i] - lo[i] + 1 for i in range(3))
        self.g = np.zeros(self.shape, dtype=np.int32)
        self.pal = ["minecraft:air"]
        self.idx = {"minecraft:air": 0}
        self.writes_outside = []

    def copy(self):
        w = World.__new__(World)
        w.lo, w.shape, w.g = self.lo, self.shape, self.g.copy()
        w.pal, w.idx, w.writes_outside = self.pal, self.idx, []
        return w

    def bid(self, block):
        i = self.idx.get(block)
        if i is None:
            i = self.idx[block] = len(self.pal)
            self.pal.append(block)
        return i

    def get(self, x, y, z):
        i = [int(math.floor(v)) - self.lo[k] for k, v in enumerate((x, y, z))]
        if any(i[k] < 0 or i[k] >= self.shape[k] for k in range(3)):
            return "minecraft:air"
        return self.pal[self.g[i[0], i[1], i[2]]]

    def write(self, a, b, block, mode="replace", filt=None):
        lo = [min(a[k], b[k]) for k in range(3)]
        hi = [max(a[k], b[k]) for k in range(3)]
        if any(lo[k] < self.lo[k] or hi[k] >= self.lo[k] + self.shape[k] for k in range(3)):
            self.writes_outside.append((tuple(lo), tuple(hi), block))
        cl = [max(lo[k], self.lo[k]) - self.lo[k] for k in range(3)]
        ch = [min(hi[k], self.lo[k] + self.shape[k] - 1) - self.lo[k] for k in range(3)]
        if any(cl[k] > ch[k] for k in range(3)):
            return
        sl = tuple(slice(cl[k], ch[k] + 1) for k in range(3))
        v = self.bid(block)
        if mode == "keep":
            sub = self.g[sl]
            sub[sub == 0] = v
        elif filt is not None:
            ids = np.array([i for i, b in enumerate(self.pal) if block_matches(b, filt) or
                            (not states_of(filt) and base_id(b) == base_id(filt))], dtype=np.int32)
            sub = self.g[sl]
            sub[np.isin(sub, ids)] = v
        elif mode in ("hollow", "outline"):
            sub = self.g[sl]
            inner = sub[1:-1, 1:-1, 1:-1].copy()
            sub[...] = v
            if mode == "hollow":
                sub[1:-1, 1:-1, 1:-1] = 0
            else:
                sub[1:-1, 1:-1, 1:-1] = inner
        else:
            self.g[sl] = v

    def flags(self):
        tab = np.array([block_flags(b) for b in self.pal], dtype=np.int32)
        return tab[self.g]


# ------------------------------------------------------------------------------------------------- the interpreter
class Ent:
    _n = 0

    def __init__(self, typ, pos, name=None, tags=()):
        Ent._n += 1
        self.type, self.pos, self.tags = typ, tuple(pos), set(tags)
        self.name = name or "e%d" % Ent._n
        self.meta = {}
        self.alive = True
        self.born = 0


class Frame:
    __slots__ = ("returned", "value")

    def __init__(self):
        self.returned, self.value = False, None


class Ctx:
    __slots__ = ("ex", "pos", "macro")

    def __init__(self, ex=None, pos=(0.0, 0.0, 0.0), macro=None):
        self.ex, self.pos, self.macro = ex, pos, macro

    def but(self, **kw):
        c = Ctx(self.ex, self.pos, self.macro)
        for k, v in kw.items():
            setattr(c, k, v)
        return c


class Sim:
    """A small mcfunction interpreter over a World: scores, block writes, entity selectors, schedule, macros, the
    Cobblemon commands as events. What it does not know it counts in `unknown` and treats as a no-op that succeeds."""

    def __init__(self, pack, world, rand=None, npc_classes=None):
        self.pack, self.w = pack, world
        self.scores = {}
        self.ents = []
        self.player = None
        self.rand = rand or (lambda lo, hi: lo)
        self.scheduled = []
        self.calls = collections.Counter()
        self.unknown = collections.Counter()
        self.events = []            # ("battle", npc) ("spawn_npc", ent) ("spawn_pkmn", ent) ("refused", npc)
        self.in_battle = False
        self.no_wild_spawn = False
        self.call_log = None
        self.depth = 0
        self.tick = 0
        self._parsed = {}
        self.storage = {}

    # -- command storage (`data ... storage`, `function ... with storage`): a dict per storage id
    def _walk_path(self, ns, path, make):
        node = self.storage.setdefault(ns, {}) if make else self.storage.get(ns)
        steps = nbt_path(path)
        for k, st in enumerate(steps):
            last = k == len(steps) - 1
            if node is None:
                return None, None
            if isinstance(st, int):
                if not isinstance(node, list) or not -len(node) <= st < len(node):
                    return None, None
                if last:
                    return node, st
                node = node[st]
            else:
                if not isinstance(node, dict):
                    return None, None
                if last:
                    return node, st
                if st not in node:
                    if not make:
                        return None, None
                    node[st] = {}
                node = node[st]
        return None, None

    def storage_get(self, ns, path):
        if not path:
            return self.storage.get(ns)
        parent, key = self._walk_path(ns, path, False)
        if parent is None:
            return None
        if isinstance(key, int):
            return parent[key]
        return parent.get(key)

    def storage_set(self, ns, path, value):
        parent, key = self._walk_path(ns, path, True)
        if parent is None:
            return 0
        parent[key] = value
        return 1

    def storage_del(self, ns, path):
        parent, key = self._walk_path(ns, path, False)
        if parent is None or (not isinstance(key, int) and key not in parent):
            return 0
        del parent[key]
        return 1

    # -- entities and selectors
    def add_player(self, pos):
        self.player = Ent("minecraft:player", pos, PLAYER)
        self.ents.append(self.player)
        return self.player

    def alive(self):
        return [e for e in self.ents if e.alive]

    def select(self, tok, ctx):
        if not tok.startswith("@"):
            return [e for e in self.alive() if e.name == tok]
        kind = tok[1]
        args = split_args(tok[3:-1]) if len(tok) > 2 and tok[2] == "[" else []
        if kind == "s":
            cands = [ctx.ex] if ctx.ex is not None and ctx.ex.alive else []
        elif kind in "apr":
            cands = [e for e in self.alive() if e.type == "minecraft:player"]
        else:
            cands = self.alive()
        origin = list(ctx.pos)
        for k, v in args:
            if k in ("x", "y", "z"):
                origin["xyz".index(k)] = float(v)
        box = sel_box(args)
        out = []
        for e in cands:
            ok = True
            for k, v in args:
                if k == "type":
                    neg = v.startswith("!")
                    t = norm_block(v[1:] if neg else v)
                    ok = (e.type != t) if neg else (e.type == t)
                elif k == "tag":
                    if v == "":
                        ok = not e.tags
                    elif v.startswith("!"):
                        ok = v[1:] not in e.tags
                    else:
                        ok = v in e.tags
                elif k == "name":
                    ok = e.name == v
                elif k == "distance":
                    ok = in_range(math.dist(origin, e.pos), v)
                elif k == "scores":
                    for kv in v.strip("{}").split(","):
                        if kv:
                            o, r = kv.split("=", 1)
                            if not in_range(self.scores.get((e.name, o)), r):
                                ok = False
                if not ok:
                    break
            if ok and box is not None and not hits_box(e.pos, box):
                ok = False
            if ok:
                out.append(e)
        d = dict((k, v) for k, v in args)
        if d.get("sort") == "nearest" or kind in "pn":
            out.sort(key=lambda e: math.dist(origin, e.pos))
        if "limit" in d:
            out = out[:int(d["limit"])]
        elif kind in "pn":
            out = out[:1]
        return out

    def holders(self, tok, ctx):
        if tok == "*":
            return sorted({h for h, _o in self.scores})
        if tok.startswith("@"):
            return [e.name for e in self.select(tok, ctx)]
        return [tok]

    # -- coordinates
    @staticmethod
    def coord(tok, base):
        if tok.startswith("~"):
            return base + (float(tok[1:]) if len(tok) > 1 else 0.0)
        return float(tok)

    def pos3(self, toks, ctx):
        return tuple(self.coord(toks[i], ctx.pos[i]) for i in range(3))

    @staticmethod
    def blk(p):
        return tuple(int(math.floor(v)) for v in p)

    # -- running
    def call(self, fid, ctx, macro=None):
        if fid.startswith("#"):
            return None
        if ":" not in fid:
            fid = "minecraft:" + fid
        self.calls[fid] += 1
        if self.call_log is not None:
            self.call_log.append(fid)
        if not self.pack.has(fid):
            self.unknown["function " + fid] += 1
            return None
        self.depth += 1
        if self.depth > 200:
            raise RuntimeError("call depth over 200 at %s" % fid)
        fr = Frame()
        c = ctx.but(macro=macro)
        try:
            for ln in self.pack.lines(fid):
                if ln.startswith("$"):
                    if macro is None:
                        continue
                    ln = re.sub(r"\$\(([A-Za-z0-9_]+)\)", lambda m: str(macro.get(m.group(1), "")), ln[1:])
                self.run_line(ln, c, fr)
                if fr.returned:
                    break
        finally:
            self.depth -= 1
        return fr.value if fr.returned else 1

    def run_line(self, ln, ctx, fr):
        toks = self._parsed.get(ln)
        if toks is None:
            toks = self._parsed[ln] = tokens(ln)
        return self.run_toks(toks, ctx, fr)

    def run_toks(self, toks, ctx, fr):
        head = toks[0]
        if head == "execute":
            return self.execute(toks, 1, ctx, fr)
        if head == "return":
            if len(toks) > 1 and toks[1] == "run":
                v = self.run_toks(toks[2:], ctx, fr)
                fr.returned, fr.value = True, v
                return v
            fr.returned = True
            fr.value = None if len(toks) > 1 and toks[1] == "fail" else (int(toks[1]) if len(toks) > 1 else 0)
            return fr.value
        if head == "function":
            macro = None
            if len(toks) > 4 and toks[2] == "with" and toks[3] == "storage":
                v = self.storage_get(toks[4], toks[5] if len(toks) > 5 else "")
                if not isinstance(v, dict):
                    return None            # vanilla: a macro call whose compound is missing fails
                macro = {k: (x if isinstance(x, str) else str(x)) for k, x in v.items()}
            elif len(toks) > 2:
                macro = dict(re.findall(r'([A-Za-z0-9_]+):"((?:[^"\\]|\\.)*)"', toks[2]))
            return self.call(toks[1], ctx, macro)
        if head == "scoreboard":
            return self.scoreboard(toks, ctx)
        if head == "setblock":
            p = self.blk(self.pos3(toks[1:4], ctx))
            self.w.write(p, p, norm_block(toks[4]))
            return 1
        if head == "fill":
            a = self.blk(self.pos3(toks[1:4], ctx))
            b = self.blk(self.pos3(toks[4:7], ctx))
            mode = toks[8] if len(toks) > 8 else "replace"
            filt = norm_block(toks[9]) if mode == "replace" and len(toks) > 9 else None
            self.w.write(a, b, norm_block(toks[7]), mode, filt)
            return 1
        if head in ("tp", "teleport"):
            return self.tp(toks, ctx)
        if head == "tag":
            for e in self.select(toks[1], ctx):
                (e.tags.add if toks[2] == "add" else e.tags.discard)(toks[3])
            return 1
        if head == "kill":
            n = 0
            for e in self.select(toks[1], ctx) if len(toks) > 1 else [ctx.ex]:
                if e is not None and e is not self.player:
                    e.alive = False
                    n += 1
            return n
        if head == "summon":
            p = self.pos3(toks[2:5], ctx) if len(toks) > 4 else ctx.pos
            e = Ent(norm_block(toks[1]), p)
            m = re.search(r"Tags:\[([^\]]*)\]", toks[5] if len(toks) > 5 else "")
            if m:
                e.tags |= {t.strip().strip('"') for t in m.group(1).split(",") if t.strip()}
            m = re.search(r"width:([0-9.]+)f?,height:([0-9.]+)", toks[5] if len(toks) > 5 else "")
            if m:
                e.meta["wh"] = (float(m.group(1)), float(m.group(2)))
            e.born = self.tick
            self.ents.append(e)
            return 1
        if head == "spawnnpcat":
            p = self.pos3(toks[1:4], ctx)
            e = Ent("cobblemon:npc", p)
            e.meta.update(cls=toks[4], level=int(toks[5]) if len(toks) > 5 else None)
            e.born = self.tick
            self.ents.append(e)
            self.events.append(("spawn_npc", e))
            return 1
        if head == "spawnpokemonat":
            if self.no_wild_spawn:
                return 0
            p = self.pos3(toks[1:4], ctx)
            e = Ent("cobblemon:pokemon", p)
            e.meta.update(species=toks[4], props=" ".join(toks[5:]))
            e.born = self.tick
            self.ents.append(e)
            self.events.append(("spawn_pkmn", e))
            return 1
        if head == "runmolang":
            return self.molang(toks, ctx)
        if head == "data":
            if toks[1] == "get" and toks[2] == "entity":
                es = self.select(toks[3], ctx)
                m = re.match(r"Pos\[(\d)\]", toks[4]) if len(toks) > 4 else None
                if es and m:
                    return int(math.floor(es[0].pos[int(m.group(1))]))
                return None
            if toks[1] == "modify" and toks[2] == "storage" and len(toks) > 6 and toks[5] == "set":
                if toks[6] == "value":
                    return self.storage_set(toks[3], toks[4], snbt(" ".join(toks[7:])))
                if toks[6] == "from" and toks[7] == "storage":
                    v = self.storage_get(toks[8], toks[9] if len(toks) > 9 else "")
                    return None if v is None else self.storage_set(toks[3], toks[4], json.loads(json.dumps(v)))
            if toks[1] == "remove" and toks[2] == "storage":
                return self.storage_del(toks[3], toks[4])
            if toks[1] == "get" and toks[2] == "storage":
                v = self.storage_get(toks[3], toks[4] if len(toks) > 4 else "")
                return v if isinstance(v, int) else (len(v) if isinstance(v, (list, dict, str)) else None)
            if toks[2] == "storage":
                self.unknown["data storage " + toks[1]] += 1
            return 1
        if head == "schedule":
            if toks[1] == "function":
                if len(toks) > 4 and toks[4] == "replace":
                    self.scheduled = [s for s in self.scheduled if s != toks[2]]
                self.scheduled.append(toks[2])
            elif toks[1] == "clear":
                self.scheduled = [s for s in self.scheduled if s != toks[2]]
            return 1
        if head == "random":
            lo, hi = toks[2].split("..")
            return self.rand(int(lo), int(hi))
        if head in ("title", "tellraw", "playsound", "particle", "effect", "give", "clear", "gamemode", "bossbar",
                    "forceload", "advancement", "ride", "item", "attribute", "say", "stopsound", "recipe", "xp",
                    "spawnpoint", "damage", "loot", "trigger", "gamerule"):
            return 1
        self.unknown[head] += 1
        return 1

    def scoreboard(self, toks, ctx):
        if toks[1] != "players":
            return 1
        op = toks[2]
        if op == "get":
            hs = self.holders(toks[3], ctx)
            return self.scores.get((hs[0], toks[4])) if hs else None
        if op in ("set", "add", "remove"):
            n = int(toks[5])
            hs = self.holders(toks[3], ctx)
            for h in hs:
                k = (h, toks[4])
                if op == "set":
                    self.scores[k] = n
                else:
                    self.scores[k] = self.scores.get(k, 0) + (n if op == "add" else -n)
            return self.scores.get((hs[0], toks[4])) if hs else None
        if op == "reset":
            for h in self.holders(toks[3], ctx):
                for k in [k for k in self.scores if k[0] == h and (len(toks) < 5 or k[1] == toks[4])]:
                    del self.scores[k]
            return 1
        if op == "operation":
            ts, src = self.holders(toks[3], ctx), self.holders(toks[6], ctx)
            if not src:
                return None
            sv = self.scores.get((src[0], toks[7]))
            if sv is None:
                return None
            for h in ts:
                k = (h, toks[4])
                tv = self.scores.get(k, 0)
                o = toks[5]
                if o == "=":
                    tv = sv
                elif o == "+=":
                    tv += sv
                elif o == "-=":
                    tv -= sv
                elif o == "*=":
                    tv *= sv
                elif o == "/=":
                    tv = tv // sv if sv else tv
                elif o == "%=":
                    tv = tv % sv if sv else tv
                elif o == "<":
                    tv = min(tv, sv)
                elif o == ">":
                    tv = max(tv, sv)
                elif o == "><":
                    self.scores[(src[0], toks[7])] = tv
                    tv = sv
                self.scores[k] = tv
            return 1
        if op == "enable":
            return 1
        self.unknown["scoreboard " + op] += 1
        return 1

    def tp(self, toks, ctx):
        args = toks[1:]
        if args and (args[0].startswith("@") or (len(args) in (1, 2) and not re.match(r"[-~0-9.]", args[0]))):
            targets = self.select(args[0], ctx)
            args = args[1:]
        else:
            targets = [ctx.ex] if ctx.ex else []
        if not args:
            return 0
        if len(args) >= 3:
            p = self.pos3(args[:3], ctx)
        else:
            dest = self.select(args[0], ctx)
            if not dest:
                return 0
            p = dest[0].pos
        for e in targets:
            if e is not None:
                e.pos = p
                if e is self.player:
                    self.events.append(("tp", p))
        return len(targets)

    def molang(self, toks, ctx):
        script = toks[1].strip('"')
        targets = toks[2:]
        who = self.select(targets[0], ctx) if targets else ([ctx.ex] if ctx.ex else [])
        if "q.entity.discard" in script:
            for e in who:
                if e is not self.player:
                    e.alive = False
            return 1
        if "start_battle" in script:
            npcs = self.select(targets[1], ctx) if len(targets) > 1 else []
            if not who or not npcs:
                self.events.append(("battle_no_target", ctx.ex))
                return 0
            if self.in_battle:
                for cmd in molang_commands(script, {"q.player.uuid": PLAYER}, branch="refuse"):
                    self.run_toks(tokens(cmd), Ctx(), Frame())
                return 0
            self.in_battle = True
            self.events.append(("battle", npcs[0]))
            return 1
        if "q.player.in_battle == 0" in script:
            if self.in_battle:
                return 0
            for cmd in molang_commands(script, {"q.player.uuid": PLAYER}):
                self.run_toks(tokens(cmd), Ctx(), Frame())
            return 1
        self.unknown["molang " + script[:40]] += 1
        return 1

    def execute(self, toks, i, ctx, fr):
        n = len(toks)
        while i < n:
            t = toks[i]
            if t == "run":
                return self.run_toks(toks[i + 1:], ctx, fr)
            if t in ("as", "at"):
                es = self.select(toks[i + 1], ctx)
                res = None
                for e in es:
                    c = ctx.but(ex=e) if t == "as" else ctx.but(pos=e.pos)
                    r = self.execute(toks, i + 2, c, fr)
                    if r:
                        res = (res or 0) + (r if isinstance(r, int) else 1)
                    if fr.returned:
                        break
                return res
            if t == "in":
                i += 2
                continue
            if t == "positioned":
                if toks[i + 1] == "as":
                    es = self.select(toks[i + 2], ctx)
                    res = None
                    for e in es:
                        r = self.execute(toks, i + 3, ctx.but(pos=e.pos), fr)
                        res = r if r else res
                    return res
                ctx = ctx.but(pos=self.pos3(toks[i + 1:i + 4], ctx))
                i += 4
                continue
            if t in ("anchored", "align"):
                i += 2
                continue
            if t == "rotated":
                i += 3 if toks[i + 1] != "as" else 3
                continue
            if t == "facing":
                i += 4 if toks[i + 1] == "entity" else 4
                continue
            if t in ("if", "unless"):
                ok, used = self.cond(toks, i + 1, ctx)
                if ok is None:
                    return None
                if ok != (t == "if"):
                    return None
                i += 1 + used
                if i >= n:
                    return 1
                continue
            if t == "store":
                kind, what = toks[i + 1], toks[i + 2]
                if what == "storage":           # store <kind> storage <ns> <path> <type> <scale>
                    r = self.execute(toks, i + 7, ctx, fr)
                    v = (1 if r else 0) if kind == "success" else \
                        (int(r) if isinstance(r, (int, float)) and not isinstance(r, bool) else (1 if r is True else 0))
                    self.storage_set(toks[i + 3], toks[i + 4], int(v * float(toks[i + 6])))
                    return r
                if what != "score":
                    self.unknown["store " + what] += 1
                    r = self.execute(toks, i + 6 if what in ("block", "entity", "storage") else i + 5, ctx, fr)
                    return r
                hs, obj = self.holders(toks[i + 3], ctx), toks[i + 4]
                r = self.execute(toks, i + 5, ctx, fr)
                if kind == "success":
                    v = 1 if r else 0
                else:
                    v = int(r) if isinstance(r, (int, float)) and not isinstance(r, bool) else (1 if r is True else 0)
                for h in hs:
                    self.scores[(h, obj)] = v
                return r
            self.unknown["execute " + t] += 1
            return None
        return 1

    def cond(self, toks, i, ctx):
        k = toks[i]
        if k == "score":
            hs = self.holders(toks[i + 1], ctx)
            v = self.scores.get((hs[0], toks[i + 2])) if hs else None
            if toks[i + 3] == "matches":
                return in_range(v, toks[i + 4]), 5
            o = toks[i + 3]
            hs2 = self.holders(toks[i + 4], ctx)
            w = self.scores.get((hs2[0], toks[i + 5])) if hs2 else None
            if v is None or w is None:
                return False, 6
            return {"=": v == w, "<": v < w, "<=": v <= w, ">": v > w, ">=": v >= w}[o], 6
        if k == "block":
            p = self.blk(self.pos3(toks[i + 1:i + 4], ctx))
            return block_matches(self.w.get(*p), norm_block(toks[i + 4])), 5
        if k == "entity":
            return bool(self.select(toks[i + 1], ctx)), 2
        if k == "data":
            if toks[i + 1] == "block":
                p = self.blk(self.pos3(toks[i + 2:i + 5], ctx))
                return (toks[i + 5] + ":") in self.w.get(*p), 6
            if toks[i + 1] == "storage":
                return self.storage_get(toks[i + 2], toks[i + 3]) is not None, 4
            self.unknown["if data " + toks[i + 1]] += 1
            return False, 4
        if k == "items":
            return False, 4
        if k == "function":
            r = self.call(toks[i + 1], ctx)
            return bool(r), 2
        if k == "dimension":
            return True, 2
        if k == "loaded":
            return True, 4
        self.unknown["if " + k] += 1
        return None, 1


def molang_commands(script, names, branch=None):
    """The command strings of a molang script's q.run_command(...) calls, names substituted. A start_battle script's
    single run_command is its refusal branch."""
    out = []
    for m in re.finditer(r"q\.run_command\((.*?)\);", script):
        parts = []
        for piece in re.split(r"\s*\+\s*", m.group(1)):
            piece = piece.strip()
            if piece.startswith("'") and piece.endswith("'"):
                parts.append(piece[1:-1])
            else:
                parts.append(names.get(piece, piece))
        out.append("".join(parts))
    return out


# ------------------------------------------------------------------------------------------------- structure, from the pack
class Slot:
    pass


def discover(pack, doc):
    """Every slot the pack builds: its dungeon, rooms in shell order with their shell boxes, the room hooks the
    keeper dispatches, the arrival, the rips and the slot's box -- all read from the generated text."""
    recs = {d["id"]: d for d in doc["dungeons"]}
    gs = sorted(int(m.group(1)) for f in pack.fns for m in [re.fullmatch(re.escape(FN) + r"shells/s(\d+)", f)] if m)
    out = []
    for g in gs:
        s = Slot()
        s.g = g
        s.rooms = [ln.split("/")[-1] for ln in pack.lines(FN + "shells/s%d" % g) if ln.startswith("function ")]
        s.dungeon = None
        for f in pack.fns:
            m = re.fullmatch(re.escape(FN) + r"room/([^/]+)/([^/]+)/s%d/\w+" % g, f)
            if m and m.group(2) == s.rooms[0]:
                s.dungeon = m.group(1)
                break
        s.rec = recs.get(s.dungeon)
        out.append(s)
    for d in doc["dungeons"]:
        mine = [s for s in out if s.dungeon == d["id"]]
        for k, s in enumerate(mine, 1):
            s.k = k
            s.vi, s.recs, s.forks, s.sides = slot_records(d, k)
    for s in out:
        if not hasattr(s, "recs"):
            s.k, s.vi, s.recs, s.forks, s.sides = 0, None, {}, {}, {}
        s.boxes = {}
        for r in s.rooms:
            xs = []
            for ln in pack.lines(FN + "shells/s%d/%s" % (s.g, r)):
                t = tokens(ln)
                if t[0] == "fill":
                    xs.append([int(float(v)) for v in t[1:7]])
                elif t[0] == "setblock":
                    p = [int(float(v)) for v in t[1:4]]
                    xs.append(p + p)
            if xs:
                a = np.array(xs)
                s.boxes[r] = (int(min(a[:, 0].min(), a[:, 3].min())), int(min(a[:, 1].min(), a[:, 4].min())),
                              int(min(a[:, 2].min(), a[:, 5].min())), int(max(a[:, 0].max(), a[:, 3].max())),
                              int(max(a[:, 1].max(), a[:, 4].max())), int(max(a[:, 2].max(), a[:, 5].max())))
        s.dispatch = collections.defaultdict(list)
        for ln in pack.lines(FN + "slot/s%d/rooms" % s.g):
            m = re.match(r"execute if entity @s\[([^\]]*)\].* run function " + re.escape(FN) +
                         r"room/[^/]+/([^/]+)/s\d+/(\w+)$", ln)
            if m:
                s.dispatch[(m.group(2), m.group(3))].append(sel_box(split_args(m.group(1))))
        s.arrive = None
        s.pick = set()      # what the rift pick given at arrival may break (its can_break), base ids
        for ln in pack.lines(FN + "slot/s%d/arrive" % s.g):
            m = re.search(r"tp @s (\S+) (\S+) (\S+)", ln)
            if m:
                s.arrive = tuple(float(v) for v in m.groups())
            m = re.search(r"can_break=\{predicates:\[\{blocks:\[([^\]]*)\]", ln)
            if m:
                s.pick |= {base_id(b.strip().strip('"')) for b in m.group(1).split(",") if b.strip()}
        s.rips = {}
        short = (s.rec or {}).get("short", "?")
        for ln in pack.lines(FN + "shells/entities_act"):
            if "minecraft:interaction" in ln and '"dg.shell.%s%d"' % (short, getattr(s, "k", 0)) in ln:
                t = tokens(ln[ln.index("summon"):])
                p = tuple(float(v) for v in t[2:5])
                m = re.search(r"width:([0-9.]+)f?,height:([0-9.]+)", t[5])
                w, h = float(m.group(1)), float(m.group(2))
                kind = "back" if "dg.rip_back" in ln else "far" if "dg.rip_far" in ln else None
                if kind:
                    s.rips[kind] = ((p[0] - w / 2, p[1], p[2] - w / 2), (p[0] + w / 2, p[1] + h, p[2] + w / 2))
        s.box = None
        for ln in pack.lines(FN + "m/member"):
            m = re.match(r"execute if score @s dg\.slot matches %d unless entity @s\[([^\]]*)\] run return run function "
                         % s.g + re.escape(FN) + "m/left", ln)
            if m:
                s.box = sel_box(split_args(m.group(1)))
    return out


def slot_records(d, k):
    """DUNGEON_ROOMS.md 1a as this file reads it (not the kit's resolve()): slot k builds variants[(k - 1) % n]; a
    variant's `swap` replaces a room's fields, `params` merged one level; forks' routes and side rooms are rooms too.
    Returns (variant index or None, {room id: record}, {fork id: {route id: [room ids]}}, {side id: [room ids]})."""
    vs = (d or {}).get("variants") or []
    vi = (k - 1) % len(vs) if vs else None
    swap = (vs[vi].get("swap") or {}) if vs else {}
    recs, forks, sides = {}, {}, {}

    def take(entries, into):
        for e in entries:
            if e.get("kind") == "fork":
                forks[e["id"]] = {}
                for rt in e.get("routes") or []:
                    forks[e["id"]][rt["id"]] = []
                    take(rt.get("rooms") or [], forks[e["id"]][rt["id"]])
            elif e.get("kind") == "side":
                sides[e["id"]] = []
                take(e.get("rooms") or [], sides[e["id"]])
            else:
                rec = dict(e)
                for f, v in (swap.get(e["id"]) or {}).items():
                    rec[f] = dict(rec.get("params") or {}, **v) if f == "params" and isinstance(v, dict) else v
                recs[e["id"]] = rec
                if into is not None:
                    into.append(e["id"])
    take((d or {}).get("rooms") or [], None)
    return vi, recs, forks, sides


def room_rec(s, r):
    rec = getattr(s, "recs", {}).get(r)
    if rec is not None:
        return rec
    for x in (s.rec or {}).get("rooms", []):
        if x["id"] == r:
            return x
    return {"id": r, "kind": "?", "params": {}}


def room_at(s, x, y, z):
    """The room whose shell box (every block its shell function writes) holds the cell; where boxes meet (a shortcut's
    door cut through the near wall, a door's shared columns), the smallest. Rooms are found by their own boxes in
    all three axes: a route that turns, doubles back in x or is stacked under another room is mapped as built."""
    best = None
    for r, b in s.boxes.items():
        if b[0] <= x <= b[3] and b[1] <= y <= b[4] and b[2] <= z <= b[5]:
            v = (b[3] - b[0] + 1) * (b[4] - b[1] + 1) * (b[5] - b[2] + 1)
            if best is None or v < best[0]:
                best = (v, r)
    return best[1] if best else None


def room_of_node(s, gr, n):
    return room_at(s, *gr.xyz(n))


def gated(rec):
    return rec.get("gate", "cleared" if rec.get("kind") == "boss_arena" else "open") == "cleared"


def room_fn(s, r, name):
    return FN + "room/%s/%s/s%d/%s" % (s.dungeon, r, s.g, name)


# ------------------------------------------------------------------------------------------------- findings
class Findings(list):
    def __init__(self):
        super().__init__()
        self.stats = collections.defaultdict(collections.Counter)

    def add(self, cat, s, room, at, msg):
        self.append({"cat": cat, "dungeon": s.dungeon if s is not None else "-", "slot": s.g if s is not None else 0,
                     "room": room or "-", "at": tuple(int(v) for v in at) if at else None, "msg": msg})


def fmt(f):
    at = " @ %d %d %d" % f["at"] if f["at"] else ""
    return "%-9s %s s%d %s%s: %s" % (f["cat"], f["dungeon"], f["slot"], f["room"], at, f["msg"])


# ------------------------------------------------------------------------------------------------- worlds
def slot_world(pack, s):
    xs = [b for b in s.boxes.values()]
    lo = [min(b[0] for b in xs) - 6, min(b[1] for b in xs) - 4, min(b[2] for b in xs) - 6]
    hi = [max(b[3] for b in xs) + 6, max(b[4] for b in xs) + 5, max(b[5] for b in xs) + 6]
    if s.box:
        lo = [min(lo[i], int(s.box[i][0]) - 2) for i in range(3)]
        hi = [max(hi[i], int(s.box[i][1]) + 2) for i in range(3)]
    w = World(lo, hi)
    sim = Sim(pack, w)
    for r in s.rooms:
        sim.call(FN + "shells/s%d/%s" % (s.g, r), Ctx())
    return w


def entrant(sim, s, band):
    p = sim.player or sim.add_player((s.arrive or (0, 0, 0)))
    for o, v in (("dg.band", band), ("dg.slot", s.g), ("dg.st", 3), ("dg.run", 1), ("dg.id", 1)):
        sim.scores[(PLAYER, o)] = v
    return p


def start_world(pack, s, shell, band=1):
    w = shell.copy()
    sim = Sim(pack, w)
    entrant(sim, s, band)
    sim.call(FN + "slot/s%d/reset" % s.g, Ctx(ex=sim.player, pos=sim.player.pos))
    return w, sim


# ------------------------------------------------------------------------------------------------- the walk
class Graph:
    """The player's moves over one world: flat indices into the world grid, `gate` the room index whose clear opens a
    cell (-1 none). Edges are generated on demand; the reverse adjacency is kept for the nodes the forward walk meets."""

    def __init__(self, world, gate=None):
        f = world.flags()
        self.world = world
        self.shape = world.shape
        nx, ny, nz = self.shape
        self.SY, self.SX = nz, ny * nz
        solid = (f & SOLID) != 0
        passable = ~solid
        climbw = (f & (CLIMB | WATER)) != 0
        support = solid & ((f & NOSUP) == 0)
        hazard = (f & HAZARD) != 0
        node = np.zeros(self.shape, bool)
        node[:, 1:-1, :] = passable[:, 1:-1, :] & passable[:, 2:, :] & (support[:, :-2, :] | climbw[:, 1:-1, :]) \
            & ~hazard[:, 1:-1, :] & ~hazard[:, :-2, :]
        land = np.full(self.shape, -1, dtype=np.int64)        # -1 blocked, -2 void, else flat index of the landing
        flat = np.arange(nx * ny * nz, dtype=np.int64).reshape(self.shape)
        land[:, 0, :] = np.where(node[:, 0, :], flat[:, 0, :], np.where(passable[:, 0, :], -2, -1))
        for y in range(1, ny):
            land[:, y, :] = np.where(node[:, y, :], flat[:, y, :], np.where(passable[:, y, :], land[:, y - 1, :], -1))
        self.P = bytearray(passable.ravel().astype(np.uint8).tobytes())
        self.N = bytearray(node.ravel().astype(np.uint8).tobytes())
        self.CW = bytearray(climbw.ravel().astype(np.uint8).tobytes())
        self.WA = bytearray(((f & WATER) != 0).ravel().astype(np.uint8).tobytes())
        self.jumps = True           # False: the walk of a player who never jumps (a balcony secret's "without the trick")
        self.T = bytearray(((f & TALL) != 0).ravel().astype(np.uint8).tobytes())
        self.L = array("q", land.ravel().tobytes())
        g = gate if gate is not None else np.full(self.shape, -1, np.int16)
        self.G = array("h", g.astype(np.int16).ravel().tobytes())
        self.levels = sorted(int(v) for v in np.unique(g)) if gate is not None else [-1]
        if -1 not in self.levels:
            self.levels = [-1] + self.levels
        self.flags = f

    def idx(self, x, y, z):
        lo = self.world.lo
        return ((x - lo[0]) * self.shape[1] + (y - lo[1])) * self.shape[2] + (z - lo[2])

    def xyz(self, i):
        lo = self.world.lo
        z = i % self.shape[2]
        y = (i // self.shape[2]) % self.shape[1]
        x = i // (self.shape[1] * self.shape[2])
        return (x + lo[0], y + lo[1], z + lo[2])

    def edges(self, u):
        """[(v, need, cost)]; v == -2 a fall into the void."""
        P, N, L, G, SY = self.P, self.N, self.L, self.G, self.SY
        out = []
        head2 = P[u + 2 * SY]
        for d in (self.SX, -self.SX, 1, -1):
            v = u + d
            if P[v] and P[v + SY]:
                t = L[v]
                if t != -1:
                    out.append((t, max(G[v], G[v + SY], G[t] if t >= 0 else -1, G[t + SY] if t >= 0 else -1), 1))
            elif N[v + SY] and head2 and not self.T[v]:
                out.append((v + SY, max(G[v + SY], G[v + 2 * SY], G[u + 2 * SY]), 1))
            elif self.WA[u] and not self.WA[u + SY] and head2 and P[u + 3 * SY] and N[v + 2 * SY] \
                    and not self.T[v + SY]:
                # out of the water's top block onto ground one higher than a step: a swimmer at the surface
                # rises against the bank (the flood's ledges stand one over its surface, tools/dungeon_setpieces.py)
                out.append((v + 2 * SY, max(G[v + 2 * SY], G[v + 3 * SY], G[u + 2 * SY], G[u + 3 * SY]), 2))
            if head2 and self.jumps:
                need = G[u + 2 * SY]
                for k in (1, 2, 3):
                    w = u + d * k
                    if not (P[w] and P[w + SY] and P[w + 2 * SY]) or N[w]:
                        break
                    need = max(need, G[w], G[w + SY], G[w + 2 * SY])
                    lnd = u + d * (k + 1)
                    if N[lnd]:
                        out.append((lnd, max(need, G[lnd], G[lnd + SY]), k + 1))
                    elif k <= 2 and N[lnd + SY] and P[w + 3 * SY]:
                        out.append((lnd + SY, max(need, G[lnd + SY], G[lnd + 2 * SY]), k + 1))
                    elif P[lnd] and P[lnd + SY] and L[lnd] >= 0:
                        t = L[lnd]
                        out.append((t, max(need, G[t], G[t + SY]), k + 1))
        if self.CW[u]:
            if N[u + SY]:
                out.append((u + SY, max(G[u + SY], G[u + 2 * SY]), 1))
            if P[u - SY]:
                t = L[u - SY]
                if t != -1:
                    out.append((t, G[t] if t >= 0 else -1, 1))
        return out


def minimax_forward(gr, sources, catch):
    """need[n]: the least, over paths from a source, of the largest gate index crossed (-1 none). Catch nodes are
    reached but not left (their teleport is modelled separately). Returns need and the reverse adjacency and voids."""
    need = {}
    rev = collections.defaultdict(list)
    voids = []
    blocked = []
    levels = gr.levels
    for lv in levels:
        q = collections.deque()
        if lv == levels[0]:
            for s in sources:
                if s not in need:
                    need[s] = lv
                    q.append(s)
        keep = []
        for ne, u, v in blocked:
            if ne <= lv:
                if v not in need:
                    need[v] = lv
                    q.append(v)
            else:
                keep.append((ne, u, v))
        blocked = keep
        while q:
            u = q.popleft()
            if u in catch:
                continue
            for v, ne, _c in gr.edges(u):
                if v == -2:
                    voids.append(u)
                    continue
                rev[v].append((u, ne))
                if v in need:
                    continue
                if ne <= lv:
                    need[v] = lv
                    q.append(v)
                else:
                    blocked.append((ne, u, v))
    return need, rev, voids


def minimax_back(rev, seeds, _levels=None):
    """back[n]: the least, over paths from n to a seed, of the largest gate index crossed; seeds is {node: value}."""
    back = {}
    heap = [(v, n) for n, v in seeds.items()]
    heapq.heapify(heap)
    while heap:
        v, n = heapq.heappop(heap)
        if n in back:
            continue
        back[n] = v
        for u, ne in rev.get(n, ()):
            if u not in back:
                heapq.heappush(heap, (max(v, ne), u))
    return back


def walk_out(gr, starts, good, limit=200000):
    """The start nodes that cannot WALK (no teleport) to any node of `good`."""
    seen = set(starts)
    q = collections.deque(starts)
    radj = collections.defaultdict(list)
    hit = set()
    while q and len(seen) < limit:
        u = q.popleft()
        if u in good:
            hit.add(u)
            continue
        for v, _ne, _c in gr.edges(u):
            if v < 0:
                continue
            radj[v].append(u)
            if v not in seen:
                seen.add(v)
                q.append(v)
    esc = set(hit)
    q = collections.deque(hit)
    while q:
        v = q.popleft()
        for u in radj.get(v, ()):
            if u not in esc:
                esc.add(u)
                q.append(u)
    return [n for n in starts if n not in esc]


def shortest(gr, src, goals, catch):
    """Walk length (jumps cost their length) and the path from src to the nearest goal, every gate open."""
    dist = {src: 0}
    prev = {}
    heap = [(0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist.get(u, 1 << 60):
            continue
        if u in goals:
            path = [u]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return d, path[::-1]
        if u in catch:
            continue
        for v, _ne, c in gr.edges(u):
            if v < 0:
                continue
            nd = d + c
            if nd < dist.get(v, 1 << 60):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    return None, None


def zone_nodes(gr, nodes, box, reach):
    lo, hi = box
    out = set()
    for n in nodes:
        x, y, z = gr.xyz(n)
        if box_dist((x + 0.5, y + EYE, z + 0.5), lo, hi) <= reach:
            out.add(n)
    return out


def parse_falls(pack, s, r):
    """The room tick's catch boxes (lines that run `fall`), the fall's teleports by dg.ck value, and the ledge boxes
    that set dg.ck."""
    catch, tps, sets = [], {}, []
    norm = None     # (lo, hi, to): `execute unless score @s dg.ck matches lo..hi run scoreboard players set @s dg.ck to`
    tick = room_fn(s, r, "tick")
    fall = room_fn(s, r, "fall")
    for ln in pack.lines(tick):
        m = re.match(r"execute if entity @s\[([^\]]*)\] run function (\S+)$", ln)
        if m and m.group(2) == fall:
            catch.append(sel_box(split_args(m.group(1))))
        m = re.search(r"scoreboard players set @s dg\.ck (\d+)", ln)
        if m:
            sets.append(int(m.group(1)))
    for ln in pack.lines(fall):
        m = re.match(r"execute if score @s dg\.ck matches (\d+) run tp @s (\S+) (\S+) (\S+)", ln)
        if m:
            tps[int(m.group(1))] = tuple(float(v) for v in m.group(2, 3, 4))
        m = re.match(r"execute unless score @s dg\.ck matches (\d+)\.\.(\d+) run scoreboard players set @s dg\.ck (\d+)$", ln)
        if m and not tps:       # only a guard that runs BEFORE the teleports re-routes them
            norm = tuple(int(v) for v in m.groups())
    return catch, tps, sets, norm


def walk_audit(pack, s, shell, start, F, blocked=()):
    """Entry to exit with every gate open; from every reached cell back to the back rip in every gate state; void
    falls; catch floors; the slot's box; the per-room walk for the clock. Returns (graph, per-room walk, path).
    `blocked`: rooms whose whole shell box is made solid first (a fork's other routes: does this route alone finish,
    and trap no one, in the gate order a player on it meets?)."""
    # the gates: run each room's clear in order on the start world; a cell a clear changes from solid to passable is
    # that room's gate cell. A clear that shuts a passable cell, or opens one another clear also touches, is reported.
    w = start.copy()
    sim = Sim(pack, w)
    entrant(sim, s, 1)
    sim.player.pos = (-1000.0, -1000.0, -1000.0)
    gate = np.full(w.shape, -1, np.int16)
    gated_rooms = []
    for r in blocked:
        b = s.boxes[r]
        w.write(b[:3], b[3:], "minecraft:bedrock")
    for i, r in enumerate(s.rooms):
        if r in blocked:
            continue
        before = w.flags()
        sim.call(room_fn(s, r, "clear"), Ctx(ex=sim.player, pos=sim.player.pos))
        after = w.flags()
        opened = ((before & SOLID) != 0) & ((after & SOLID) == 0)
        shut = ((before & SOLID) == 0) & ((after & SOLID) != 0)
        if shut.any():
            p = np.argwhere(shut)[0] + np.array(w.lo)
            F.add("GATE", s, r, p, "its clear shuts %d passable cells" % int(shut.sum()))
        if opened.any():
            gate[opened & (gate < 0)] = i
            gated_rooms.append(r)
        rec = room_rec(s, r)
        if gated(rec) and not opened.any():
            F.add("SOFTLOCK", s, r, None, "the record gates this room (`cleared`) but its clear opens nothing")
        if not gated(rec) and opened.any():
            p = np.argwhere(opened)[0] + np.array(w.lo)
            F.add("GATE", s, r, p, "an open-gate room's clear opens %d cells: they are shut until it runs" % int(opened.sum()))
    gr = Graph(w, gate)
    if s.arrive is None:
        F.add("WALK", s, None, None, "no arrival teleport in slot/s%d/arrive" % s.g)
        return gr, None, None
    a = gr.idx(*Sim.blk(s.arrive))
    if not gr.N[a]:
        F.add("WALK", s, s.rooms[0], s.arrive, "the arrival point is not a place a player can stand")
        return gr, None, None
    # catch floors: a cell inside a room's dispatched tick box AND one of that tick's fall boxes
    catch, catch_room, ck_any = set(), {}, set()
    falls = {}
    for r in s.rooms:
        c, tps, sets, norm = parse_falls(pack, s, r)
        ck_any |= set(sets)
        if c:
            falls[r] = (c, tps, norm)
    need, rev, voids = None, None, None
    # pass 1: reach (catch nodes are not expanded), so the catch set can be restricted to reached nodes after
    need, rev, voids = minimax_forward(gr, [a], set())
    for r, (cboxes, tps, _norm) in falls.items():
        ticks = s.dispatch.get((r, "tick"), [])
        for n in need:
            x, y, z = gr.xyz(n)
            p = (x + 0.5, y, z + 0.5)
            if any(hits_box(p, b) for b in cboxes) and any(hits_box(p, b) for b in ticks):
                catch.add(n)
                catch_room[n] = r
    if catch:
        need, rev, voids = minimax_forward(gr, [a], catch)
    for u in sorted(set(voids))[:1]:
        F.add("VOID", s, room_of_node(s, gr, u), gr.xyz(u), "a step from here falls out of the shell into the void")
    # the exit and the back rip
    far, back = s.rips.get("far"), s.rips.get("back")
    reached = list(need)
    exits = zone_nodes(gr, reached, far, ENTITY_REACH) if far else set()
    backs = zone_nodes(gr, reached, back, ENTITY_REACH) if back else set()
    if not exits:
        far_c = ((far[0][0] + far[1][0]) / 2, (far[0][2] + far[1][2]) / 2) if far else (0, 0)
        last = min(reached, key=lambda n: abs(gr.xyz(n)[0] - far_c[0]) + abs(gr.xyz(n)[2] - far_c[1]))
        F.add("WALK", s, room_of_node(s, gr, last), gr.xyz(last), "the far rip cannot be reached with every gate open "
              "(the nearest cell reached to it is here)")
    if not backs:
        F.add("TRAP", s, s.rooms[0], s.arrive, "the back rip cannot be reached from the arrival")
    big = 1 << 20
    backv0 = minimax_back(rev, {n: -1 for n in backs}, None)
    # a catch node returns when every checkpoint its fall can send it to returns (the value is their worst)
    dests, stale = {}, {}
    for r, (cb, tps, norm) in falls.items():
        dn = []
        for k, p in sorted(tps.items()):
            i = gr.idx(*Sim.blk(p))
            if not gr.N[i]:
                F.add("PARKOUR", s, r, p, "checkpoint dg.ck %d teleports to a place a player cannot stand" % k)
            dn.append(i)
        dests[r] = dn
        if not tps:
            F.add("PARKOUR", s, r, None, "its fall teleports nowhere")
        # a value the fall re-routes before its teleports (the guard) lands where the guard's value does, if that teleports
        routed = {v for v in ck_any if norm and not norm[0] <= v <= norm[1] and norm[2] in tps}
        missing = sorted(ck_any - set(tps) - routed)
        if missing:
            stale[r] = missing
    backv = backv0
    for _ in range(len(falls) + 2):
        seeds = {n: -1 for n in backs}
        for n in catch:
            vals = [backv.get(i, big) for i in dests[catch_room[n]]]
            v = max(vals) if vals else big
            if v < big:
                seeds[n] = min(seeds.get(n, big), v)
        nb = minimax_back(rev, seeds, None)
        if nb == backv:
            break
        backv = nb
    # stale dg.ck: a value set by another room and not handled by this room's fall leaves no teleport at all, so the
    # catch floor must be walkable out of on its own
    good = {n for n, v in backv0.items() if v < big and n not in catch}
    for r, missing in stale.items():
        cn = [n for n in catch if catch_room[n] == r]
        if not cn:
            continue
        stuck = walk_out(gr, cn, good)
        if stuck:
            F.add("TRAP", s, r, gr.xyz(stuck[0]),
                  "dg.ck is the member's own score, set by every parkour and bridge room (values %s), and this room's "
                  "fall teleports only for %s: a member carrying %s from another room's ledge who falls here gets no "
                  "teleport, %d catch-floor cells have no walk out, and the fall is charged again every pass"
                  % (sorted(ck_any), sorted(falls[r][1]), missing, len(stuck)))
    # traps: reachable before some gate opens, and not back to the back rip until a later gate opens (or never)
    by_room = collections.defaultdict(list)
    for n, nv in need.items():
        bv = backv.get(n, big)
        if bv > nv:
            by_room[room_of_node(s, gr, n)].append((n, nv, bv))
    for r, lst in by_room.items():
        never = [t for t in lst if t[2] >= big]
        until = [t for t in lst if t[2] < big]
        if never:
            ins = [u for u, _ne in rev.get(never[0][0], ()) if backv.get(u, big) < big]
            F.add("TRAP", s, r, gr.xyz(never[0][0]), "%d reachable cells cannot get back to the back rip at all%s"
                  % (len(never), " (one is entered from %d %d %d)" % gr.xyz(ins[0]) if ins else ""))
        if until:
            g = until[0][2]
            F.add("TRAP", s, r, gr.xyz(until[0][0]), "%d reachable cells cannot get back until room %s is cleared"
                  % (len(until), s.rooms[g] if 0 <= g < len(s.rooms) else g))
    # a member put back by a tick (`tp @s <x> ~ ~`, the gauntlet's barrier) lands where it can stand
    for r in s.rooms:
        for ln in pack.lines(room_fn(s, r, "tick")):
            m = re.search(r"if entity @s\[([^\]]*)\] run tp @s (\S+) ~ ~$", ln)
            if not m:
                continue
            bx, tx = sel_box(split_args(m.group(1))), float(m.group(2))
            bad = []
            for n in need:
                x, y, z = gr.xyz(n)
                if hits_box((x + 0.5, y, z + 0.5), bx):
                    d = gr.idx(int(math.floor(tx)), y, z)
                    if not (gr.P[d] and gr.P[d + gr.SY]):
                        bad.append((int(math.floor(tx)), y, z))
            F.stats[s.dungeon]["put_back_lines"] += 1
            if bad:
                F.add("FIGHT", s, r, bad[0], "the put-back `tp @s %s ~ ~` lands %d standing places inside a block"
                      % (m.group(2), len(bad)))
    # every reached cell inside the slot's box (else the keeper puts the member out of the run)
    if s.box:
        out = [n for n in need if not hits_box((gr.xyz(n)[0] + 0.5, gr.xyz(n)[1], gr.xyz(n)[2] + 0.5), s.box)]
        if out:
            F.add("BOUNDS", s, room_of_node(s, gr, out[0]), gr.xyz(out[0]),
                  "%d reachable cells are outside the slot's box: standing there ends the run" % len(out))
    # holes: an interior column of a room with nothing solid in it, top to bottom
    sol = (gr.flags & SOLID) != 0
    for r in s.rooms:
        b = s.boxes.get(r)
        if not b:
            continue
        lo = gr.world.lo
        sub = sol[b[0] + 1 - lo[0]:b[3] - lo[0], :, b[2] + 1 - lo[2]:b[5] - lo[2]]
        holes = np.argwhere(~sub.any(axis=1))
        if len(holes):
            F.add("VOID", s, r, (holes[0][0] + b[0] + 1, b[1], holes[0][1] + b[2] + 1),
                  "%d interior columns have no block at all: a fall there leaves the shell" % len(holes))
    # the walk, per room, for the clock
    d, path = shortest(gr, a, exits, catch) if exits else (None, None)
    F.stats[s.dungeon].update(cells_reached=len(need), catch_cells=len(catch), gate_cells=int((gate >= 0).sum()),
                              gates_opened=len(gated_rooms), exit_cells=len(exits), back_cells=len(backs))
    walks = None
    if path:
        walks = collections.Counter()
        for i in range(1, len(path)):
            r = room_of_node(s, gr, path[i])
            x0, x1 = gr.xyz(path[i - 1])[0], gr.xyz(path[i])[0]
            walks[r] += abs(x1 - x0) + abs(gr.xyz(path[i])[2] - gr.xyz(path[i - 1])[2]) or 1
    gr.info = {"arrive": a, "need": need, "rev": rev, "backv": backv, "exits": exits, "backs": backs, "catch": catch,
               "catch_room": catch_room, "falls": falls, "dests": dests, "path": path}
    return gr, walks, (path, d, catch, need)


# ------------------------------------------------------------------------------------------------- the simulated run
def npc_levels(pack, cls):
    ns, name = cls.split(":", 1)
    body = pack.files.get("data/%s/npcs/%s.json" % (ns, name))
    if body is None:
        return None
    party = json.loads(body).get("party", {}).get("pokemon", [])
    return [int(m.group(1)) for p in party for m in [re.search(r"level=(\d+)", p)] if m]


def victory(pack):
    """The callback's commands for a battle an NPC LOSES to a player: the scriptable_losers block, up to the
    scriptable_winners one."""
    body = pack.files.get("data/cobblemon/callbacks/battle_victory/cobblers_dungeons.molang", "")
    cut = body.find("c.scriptable_winners")
    return re.findall(r"q\.run_command\((.*?)\);", body[:cut] if cut >= 0 else body)


def run_victory(sim, pack, npc):
    names = {"t.l.uuid": npc.name, "t.w.player.username": PLAYER, "t.w.uuid": PLAYER}
    for raw in victory(pack):
        cmd = molang_commands("q.run_command(%s);" % raw, names)[0]
        sim.run_toks(tokens(cmd), Ctx(), Frame())


class Run:
    """One simulated run of one slot at one band: the real keeper once a pass, the player walking the shortest path
    of the all-open walk, battles won through the real callback, wild Pokemon defeated, puzzles solved."""

    def __init__(self, pack, s, shell, band, caps, exempt, mode, F, gr, path, catch):
        self.pack, self.s, self.band, self.caps, self.exempt, self.mode, self.F = pack, s, band, caps, exempt, mode, F
        self.gr, self.path, self.catch = gr, path, catch
        self.sim = Sim(pack, shell.copy())
        self.sim.no_wild_spawn = mode == "nospawn"
        self.forfeited = set()
        self.seen_spawn = set()
        self.reported = set()

    def say(self, cat, room, at, msg):
        key = (cat, room, msg[:60])
        if key not in self.reported:
            self.reported.add(key)
            self.F.add(cat, self.s, room, at, "[band %d, %s] %s" % (self.band, self.mode, msg))

    def here(self):
        p = self.sim.player.pos
        return room_at(self.s, *(int(math.floor(v)) for v in p))

    def keeper(self):
        sim = self.sim
        sim.tick += 1
        sched, sim.scheduled = sim.scheduled, []
        for fid in sched:
            if fid != FN + "keeper":
                sim.call(fid, Ctx())
        sim.call(FN + "keeper", Ctx())
        self.after_pass()

    def after_pass(self):
        sim = self.sim
        ev, sim.events = sim.events, []
        room = self.here()
        self.tps += [e[1] for e in ev if e[0] == "tp"]
        for e in ev:
            if e[0] in ("spawn_npc", "spawn_pkmn"):
                ent = e[1]
                if e[0] == "spawn_npc":
                    lv = npc_levels(self.pack, ent.meta["cls"])
                    if lv is None:
                        self.say("FIGHT", room, ent.pos, "NPC class %s has no file in the pack" % ent.meta["cls"])
                    elif lv and max(lv) > self.caps[self.band]:
                        self.say("LEVEL", room, ent.pos, "%s fields level %d over the band's upper cap %d"
                                 % (ent.meta["cls"], max(lv), self.caps[self.band]))
                else:
                    m = re.search(r"level=(\d+)", ent.meta["props"])
                    if not m:
                        self.say("LEVEL", room, ent.pos, "a %s spawned with no level" % ent.meta["species"])
                    elif int(m.group(1)) > self.caps[self.band]:
                        self.say("LEVEL", room, ent.pos, "a %s at level %s over the band's upper cap %d"
                                 % (ent.meta["species"], m.group(1), self.caps[self.band]))
            elif e[0] == "battle":
                npc = e[1]
                if not self.claw_open:
                    self.say("MONEY", room, npc.pos, "a battle with %s started with no clawback begin before it"
                             % npc.meta.get("cls"))
                self.claw_open = False
                self.F.stats[self.s.dungeon]["battles"] += 1
                if "dg.boss" in npc.tags:
                    self.boss_battles += 1
                if self.mode == "forfeit" and npc.meta.get("cls") not in self.forfeited:
                    self.forfeited.add(npc.meta.get("cls"))
                    sim.in_battle = False
                    continue
                before = sim.calls[FN + "claw/settle"]
                run_victory(sim, self.pack, npc)
                sim.in_battle = False
                if "dg.npc" in npc.tags and sim.calls[FN + "claw/settle"] == before:
                    self.say("MONEY", room, npc.pos, "a won battle with %s did not settle the clawback" % npc.meta.get("cls"))
                if "dg.npc" not in npc.tags:
                    self.say("MONEY", room, npc.pos, "%s fought without dg.npc: the callback never settles it"
                             % npc.meta.get("cls"))
            elif e[0] == "battle_no_target":
                self.say("FIGHT", room, None, "a battle start found no NPC to fight")
        for ent in sim.alive():
            if ent.type in ("cobblemon:npc", "cobblemon:pokemon") and self.exempt not in ent.tags                     and ent.name not in self.seen_spawn:
                self.seen_spawn.add(ent.name)
                self.say("EXEMPT", room, ent.pos, "a spawned %s (%s) lacks the blackout's exempt tag %s"
                         % (ent.type, ent.meta.get("cls") or ent.meta.get("species"), self.exempt))
        # defeat the wild Pokemon of the room the player waits in, once they have stood a pass
        if self.mode != "nospawn" and self.waiting:
            for ent in sim.alive():
                if ent.type == "cobblemon:pokemon" and sim.tick - ent.born >= 2 and ("dg.r." + (room or "")) in ent.tags:
                    if self.mode == "forfeit" and sim.tick - ent.born < 6:
                        continue
                    ent.alive = False
                    self.F.stats[self.s.dungeon]["wild_defeated"] += 1

    def standable(self, n):
        x, y, z = self.gr.xyz(n)
        w = self.sim.w
        fa, fh, fb = (block_flags(w.get(x, y + k, z)) for k in (0, 1, -1))
        return not fa & SOLID and not fh & SOLID and (fb & SOLID and not fb & NOSUP or fa & (CLIMB | WATER))

    def go(self):
        sim, s = self.sim, self.s
        self.claw_open = False
        self.waiting = False
        self.tps = []
        self.boss_battles = 0
        sim.add_player(s.arrive)
        sim.call(FN + "load", Ctx())
        sim.scheduled = []
        sim.scores[(PLAYER, "dg.band")] = self.band
        sim.scores[(PLAYER, "dg.id")] = 1
        sim.scores[("#pick", "dg.t")] = s.g
        sim.scores[("#sig", "dg.t")] = self.band
        sim.call(FN + "door/go_%s" % s.rec["short"], Ctx(ex=sim.player, pos=sim.player.pos))
        orig_call = sim.call

        def call(fid, ctx, macro=None):
            if fid == FN + "claw/begin":
                self.claw_open = True
            return orig_call(fid, ctx, macro)
        sim.call = call
        path = self.path
        i, steps, waited, last_room = 0, 0, 0, None
        ended = None
        for _ in range(12):           # the arrival delay
            self.keeper()
            if sim.scores.get((PLAYER, "dg.st")) == 2:
                break
        if sim.scores.get((PLAYER, "dg.st")) != 2:
            self.say("RUN", None, sim.player.pos, "the member never arrives (dg.st %s)" % sim.scores.get((PLAYER, "dg.st")))
            return False
        self.tps = []
        guard = 0
        while i < len(path) and guard < 20000:
            guard += 1
            st = sim.scores.get((PLAYER, "dg.st"), 0)
            if st not in (2, 3):
                ended = st
                break
            nxt = path[i]
            if self.standable(nxt):
                x, y, z = self.gr.xyz(nxt)
                sim.player.pos = (x + 0.5, float(y), z + 0.5)
                i += 1
                steps += 1
                waited = 0
                self.waiting = False
                if steps >= 4:
                    steps = 0
                    self.keeper()
            else:
                self.waiting = True
                room = self.here()
                if room and room_rec(s, room).get("kind") == "puzzle" and waited in (2, 30):
                    solve_puzzle(self, room)
                self.keeper()
                waited += 1
                if waited > 150:
                    x, y, z = self.gr.xyz(nxt)
                    state = {k[0]: v for k, v in sim.scores.items() if k[0].startswith("#s%dr" % s.g) and k[1] == "dg.rs"}
                    self.say("SOFTLOCK", room, (x, y, z), "the way on stays shut after %d passes waiting in the room "
                             "(room scores %s)" % (waited, dict(sorted(state.items())[:8])))
                    return False
            tps, self.tps = self.tps, []
            for tp in tps[-1:]:
                n = self.gr.idx(*Sim.blk(tp))
                if n in path[max(0, i - 400):i + 400]:
                    i = path.index(n, max(0, i - 400)) + 1
                else:
                    d, np_ = shortest(self.gr, n, set(path[-3:]), self.catch)
                    if np_ is None:
                        self.say("WALK", self.here(), tp, "teleported to a place with no walk on to the exit")
                        return False
                    path = path[:i] + np_
        if ended is not None and ended not in (2, 3):
            self.say("RUN", self.here(), sim.player.pos, "the run ended (dg.st %s) before the far rip; calls %s"
                     % (ended, {k.split("/")[-1]: v for k, v in sim.calls.items() if k.startswith(FN + "m/") and
                                k.split("/")[-1] in ("left", "void", "out", "end", "timeout", "zero")}))
            return False
        if sim.calls[FN + "slot/s%d/boss_done" % s.g] == 0 and self.mode == "win":
            self.say("BOSS", None, None, "the run reached the far rip without the boss chain finishing")
        stages = len(((s.rec.get("boss") or {}).get("teams") or {}).get(str(self.band)) or [])
        if self.mode == "win" and stages and self.boss_battles != stages:
            self.say("BOSS", None, None, "the boss was fought %d times; the record's band has %d stages"
                     % (self.boss_battles, stages))
        sim.call(FN + "far", Ctx(ex=sim.player, pos=sim.player.pos))
        self.F.stats[s.dungeon]["runs_finished"] += 1
        return True


# ------------------------------------------------------------------------------------------------- puzzles
def controls_in(world, box):
    x0, y0, z0, x1, y1, z1 = box
    out = []
    lo = world.lo
    sub = world.g[x0 - lo[0]:x1 - lo[0] + 1, y0 - lo[1]:y1 - lo[1] + 1, z0 - lo[2]:z1 - lo[2] + 1]
    for i in np.unique(sub):
        b = world.pal[i]
        bid = base_id(b)
        if bid == "lever" or bid.endswith("_button") or bid.endswith("_pressure_plate"):
            for p in np.argwhere(sub == i):
                out.append((int(p[0]) + x0, int(p[1]) + y0, int(p[2]) + z0))
    return sorted(out)


def press(sim, p):
    b = sim.w.get(*p)
    st = states_of(b)
    if base_id(b) == "lever":
        st["powered"] = "false" if st.get("powered", "false") == "true" else "true"
    else:
        st["powered"] = "true"
    nb = "minecraft:%s[%s]" % (base_id(b), ",".join("%s=%s" % kv for kv in sorted(st.items())))
    sim.w.write(p, p, nb)


def unpress(sim, ctrls):
    for p in ctrls:
        b = sim.w.get(*p)
        if base_id(b) != "lever" and states_of(b).get("powered") == "true":
            st = states_of(b)
            st["powered"] = "false"
            sim.w.write(p, p, "minecraft:%s[%s]" % (base_id(b), ",".join("%s=%s" % kv for kv in sorted(st.items()))))


def is_room_holder(h, prefix):
    """#s1r1 owns #s1r1, #s1r1x, #s1r1t2 -- not #s1r12."""
    return h.startswith(prefix) and (len(h) == len(prefix) or not h[len(prefix)].isdigit())


def puzzle_snapshot(sim, cells, prefix):
    return (tuple(sim.w.get(*c) for c in cells),
            tuple(sorted((k, v) for k, v in sim.scores.items() if is_room_holder(k[0], prefix))))


def puzzle_restore(sim, cells, snap):
    for c, b in zip(cells, snap[0]):
        sim.w.write(c, c, b)
    for k in [k for k in sim.scores if is_room_holder(k[0], snap[2])]:
        del sim.scores[k]
    for k, v in snap[1]:
        sim.scores[k] = v


def written_cells(pack, s, r):
    out = set()
    for f in pack.fns:
        if f.startswith(FN + "room/%s/%s/s%d/" % (s.dungeon, r, s.g)) and not f.endswith("/reset"):
            for ln in pack.lines(f):
                t = tokens(ln[ln.index(" run ") + 5:] if ln.startswith("execute") and " run " in ln else ln)
                if t[0] == "setblock" and not any(v.startswith("~") for v in t[1:4]):
                    out.add(tuple(int(float(v)) for v in t[1:4]))
    return sorted(out)


def puzzle_space(sim, s, r, pos, limit=6000):
    """Explore every state the room's controls reach (each action: flip a lever or press a button or plate, then one
    keeper pass of the room); returns (states, edges, solved set, controls). A state is solved when the room's dg.rs is 2."""
    b = s.boxes[r]
    ctrls = controls_in(sim.w, b)
    cells = sorted(set(ctrls) | set(written_cells(sim.pack, s, r)))
    prefix = "#s%dr%d" % (s.g, s.rooms.index(r))
    holder = (prefix, "dg.rs")
    rooms_fn = FN + "slot/s%d/rooms" % s.g

    def snap():
        a, sc = puzzle_snapshot(sim, cells, prefix)
        return (a, sc, prefix)

    def key(sn):
        return (sn[0], sn[1])
    start = snap()
    seen = {key(start): start}
    edges = collections.defaultdict(set)
    q = collections.deque([start])
    solved = set()
    while q and len(seen) < limit:
        st = q.popleft()
        k0 = key(st)
        if dict(st[1]).get(holder) == 2:
            solved.add(k0)
            continue
        for c in ctrls:
            puzzle_restore(sim, cells, st)
            sim.player.pos = pos
            press(sim, c)
            sim.call(rooms_fn, Ctx(ex=sim.player, pos=sim.player.pos))
            unpress(sim, ctrls)
            nst = snap()
            k1 = key(nst)
            edges[k0].add(k1)
            if k1 not in seen:
                seen[k1] = nst
                q.append(nst)
    puzzle_restore(sim, cells, start)
    return seen, edges, solved, ctrls, (len(seen) >= limit)


def solve_puzzle(run, r):
    """In the simulated run: find the shortest action list to the room's clear and do it."""
    sim, s = run.sim, run.s
    b = s.boxes[r]
    ctrls = controls_in(sim.w, b)
    cells = sorted(set(ctrls) | set(written_cells(sim.pack, s, r)))
    prefix = "#s%dr%d" % (s.g, s.rooms.index(r))
    holder = (prefix, "dg.rs")
    rooms_fn = FN + "slot/s%d/rooms" % s.g
    pos = sim.player.pos
    clk = sim.scores.get((PLAYER, "dg.clock"))
    start = puzzle_snapshot(sim, cells, prefix) + (prefix,)
    prev = {(start[0], start[1]): None}
    q = collections.deque([start])
    goal = None
    while q and len(prev) < 6000:
        st = q.popleft()
        if dict(st[1]).get(holder) == 2:
            goal = st
            break
        for c in ctrls:
            puzzle_restore(sim, cells, st)
            press(sim, c)
            sim.call(rooms_fn, Ctx(ex=sim.player, pos=pos))
            unpress(sim, ctrls)
            nst = puzzle_snapshot(sim, cells, prefix) + (prefix,)
            k = (nst[0], nst[1])
            if k not in prev:
                prev[k] = ((st[0], st[1]), c, st)
                q.append(nst)
    puzzle_restore(sim, cells, start)
    sim.scores[(PLAYER, "dg.clock")] = clk
    sim.events = [e for e in sim.events if e[0] != "tp"]
    if goal is None:
        run.say("PUZZLE", r, None, "no sequence of its %d controls solves the rolled target" % len(ctrls))
        return False
    acts = []
    k = (goal[0], goal[1])
    while prev[k] is not None:
        pk, c, _st = prev[k]
        acts.append(c)
        k = pk
    run.F.stats[s.dungeon]["puzzles_solved_in_run"] += 1
    for c in reversed(acts):
        press(sim, c)
        sim.call(rooms_fn, Ctx(ex=sim.player, pos=pos))
        unpress(sim, ctrls)
    return True


def vault_audit(pack, doc, s, start, gr, need, F):
    """A vault charges the clock once per chest opened, by the record's clock_cost_s in the threshold's own units
    (the threshold's dg.clock over the record's clock seconds)."""
    own = s.rec.get("clock_s_by_band") or {}
    unit = None
    for ln in pack.lines(FN + "slot/s%d/start" % s.g):
        m = re.match(r"execute if score @s dg\.band matches 1 run scoreboard players set @s dg\.clock (\d+)", ln)
        if m and own.get("1"):
            unit = int(m.group(1)) / float(own["1"])
    for i, r in enumerate(s.rooms):
        rec = room_rec(s, r)
        if rec.get("kind") != "vault":
            continue
        cost = (rec.get("params") or {}).get("clock_cost_s")
        b = s.boxes[r]
        disp = s.dispatch.get((r, "enter"), [])
        pos = next(((gr.xyz(n)[0] + 0.5, float(gr.xyz(n)[1]), gr.xyz(n)[2] + 0.5) for n in need
                    if in_box(s, r, gr, n) and any(hits_box((gr.xyz(n)[0] + 0.5, gr.xyz(n)[1], gr.xyz(n)[2] + 0.5), bx)
                                                          for bx in disp)), None)
        if pos is None or unit is None or cost is None:
            F.add("VAULT", s, r, None, "cannot test: no standing place in the room, no threshold clock or no clock_cost_s")
            continue
        sim = Sim(pack, start.copy())
        entrant(sim, s, 1)
        sim.player.pos = pos
        sim.call(FN + "slot/s%d/reset" % s.g, Ctx(ex=sim.player, pos=pos))
        sim.scores[(PLAYER, "dg.clock")] = 10 ** 7
        rooms = FN + "slot/s%d/rooms" % s.g
        sim.call(rooms, Ctx(ex=sim.player, pos=pos))
        lo = sim.w.lo
        sub = sim.w.g[b[0] - lo[0]:b[3] - lo[0] + 1, b[1] - lo[1]:b[4] - lo[1] + 1, b[2] - lo[2]:b[5] - lo[2] + 1]
        chests = [tuple(int(v) for v in p + np.array(b[:3])) for p in np.argwhere(
            np.isin(sub, [k for k, bl in enumerate(sim.w.pal) if "LootTable" in bl]))]
        if not chests:
            F.add("VAULT", s, r, None, "no chest with a loot table after the reset")
            continue
        for c in chests:
            before = sim.scores[(PLAYER, "dg.clock")]
            bl = sim.w.get(*c)
            sim.w.write(c, c, re.sub(r"\{.*\}$", "", bl))          # opened: the loot table is spent
            for _ in range(3):
                sim.call(rooms, Ctx(ex=sim.player, pos=pos))
            got = before - sim.scores[(PLAYER, "dg.clock")]
            F.stats[s.dungeon]["vault_chests_checked"] += 1
            if got != round(cost * unit):
                F.add("VAULT", s, r, c, "opening this chest and three passes cost %d clock units; the record's %s s is %d"
                      % (got, cost, round(cost * unit)))


def puzzle_audit(pack, s, start, gr, need, F):
    """Every rolled target of every puzzle room is solvable with its controls, every control is in reach of a cell the
    player stands on, and no state a wrong attempt reaches is a dead end."""
    for i, r in enumerate(s.rooms):
        if room_rec(s, r).get("kind") != "puzzle":
            continue
        enter = pack.lines(room_fn(s, r, "enter"))
        rng = None
        for ln in enter:
            m = re.search(r"random value (\d+)\.\.(\d+)", ln)
            if m:
                rng = (int(m.group(1)), int(m.group(2)))
        b = s.boxes[r]
        stand = [n for n in need if in_box(s, r, gr, n)]
        if not stand:
            F.add("PUZZLE", s, r, None, "no cell of the room is reached, so no control can be used")
            continue
        ctrls = controls_in(start, b)
        if not ctrls:
            F.add("PUZZLE", s, r, None, "the room has no lever, button or plate")
            continue
        for c in ctrls:
            best = min(box_dist((gr.xyz(n)[0] + 0.5, gr.xyz(n)[1] + EYE, gr.xyz(n)[2] + 0.5), c, tuple(v + 1 for v in c))
                       for n in stand)
            if best > BLOCK_REACH:
                F.add("PUZZLE", s, r, c, "this control is %.1f blocks from the nearest place to stand (reach %.1f)"
                      % (best, BLOCK_REACH))
        disp = s.dispatch.get((r, "enter"), [])
        pos = None
        for n in stand:
            x, y, z = gr.xyz(n)
            if any(hits_box((x + 0.5, y, z + 0.5), bx) for bx in disp):
                pos = (x + 0.5, float(y), z + 0.5)
                break
        if pos is None:
            F.add("PUZZLE", s, r, None, "no reachable cell is inside the room's dispatched box: enter never runs")
            continue
        for v in range(rng[0], rng[1] + 1) if rng else [None]:
            sim = Sim(pack, start.copy(), rand=(lambda lo, hi, v=v: v if v is not None else lo))
            entrant(sim, s, 1)
            sim.player.pos = pos
            sim.call(FN + "slot/s%d/reset" % s.g, Ctx(ex=sim.player, pos=pos))
            sim.call(FN + "slot/s%d/rooms" % s.g, Ctx(ex=sim.player, pos=pos))
            if sim.scores.get(("#s%dr%d" % (s.g, i), "dg.rs")) != 1:
                F.add("PUZZLE", s, r, None, "standing in the room does not enter it (dg.rs %s)"
                      % sim.scores.get(("#s%dr%d" % (s.g, i), "dg.rs")))
                break
            seen, edges, solved, _c, truncated = puzzle_space(sim, s, r, pos)
            if not solved:
                F.add("PUZZLE", s, r, None, "rolled target %s: no sequence of its %d controls solves it (%d states)"
                      % (v, len(ctrls), len(seen)))
                continue
            F.stats[s.dungeon]["puzzle_targets_solvable"] += 1
            if truncated:
                continue
            good = set(solved)
            radj = collections.defaultdict(set)
            for a_, bs in edges.items():
                for b_ in bs:
                    radj[b_].add(a_)
            q = collections.deque(good)
            while q:
                x = q.popleft()
                for y in radj.get(x, ()):
                    if y not in good:
                        good.add(y)
                        q.append(y)
            dead = [k for k in seen if k not in good]
            if dead:
                F.add("PUZZLE", s, r, None, "rolled target %s: %d of %d states a player can reach can no longer be solved"
                      % (v, len(dead), len(seen)))


# ------------------------------------------------------------------------------------------------- resets restore
def reset_audit(pack, s, start, F):
    """Every block a room's runtime functions write (tick, fall, restore, go, won, clear, the variants...), its reset
    puts back to the start of a run: a run's collapsed span, raised barrier or pulled lever never outlives the run."""
    for r in s.rooms:
        w = start.copy()
        sim = Sim(pack, w)
        entrant(sim, s, 1)
        cells = set()
        for f in sorted(pack.fns):
            if not f.startswith(FN + "room/%s/%s/s%d/" % (s.dungeon, r, s.g)) or f.endswith("/reset"):
                continue
            for ln in pack.lines(f):
                body = ln[ln.index(" run ") + 5:] if ln.startswith("execute") and " run " in ln else ln
                t = tokens(body)
                if t[0] in ("fill", "setblock") and not any(v.startswith("~") for v in t[1:7 if t[0] == "fill" else 4]):
                    sim.run_toks(t, Ctx(ex=sim.player, pos=sim.player.pos), Frame())
                    c = [int(float(v)) for v in t[1:7 if t[0] == "fill" else 4]]
                    if t[0] == "setblock":
                        c = c + c
                    cells.add(tuple(c))
        # a player mines what a tick watches (`unless block`: the seam) and takes a vault's chest contents
        for ln in pack.lines(room_fn(s, r, "tick")):
            m = re.search(r"(if|unless) block (-?\d+) (-?\d+) (-?\d+) (\S+)", ln)
            if m and (m.group(1) == "if") == (base_id(m.group(5)) == "air"):
                m = re.match(r"(-?\d+) (-?\d+) (-?\d+)", " ".join(m.group(2, 3, 4)))
                c = tuple(int(v) for v in m.groups())
                w.write(c, c, "minecraft:air")
                cells.add(c + c)
        if not cells:
            continue
        F.stats[s.dungeon]["rooms_reset_checked"] += 1
        sim.call(room_fn(s, r, "reset"), Ctx(ex=sim.player, pos=sim.player.pos))
        lo = w.lo
        for c in sorted(cells):
            sl = tuple(slice(min(c[k], c[k + 3]) - lo[k], max(c[k], c[k + 3]) - lo[k] + 1) for k in range(3))
            a, b = w.g[sl], start.g[sl]
            diff = np.argwhere(np.array([w.pal[i] for i in a.ravel()]).reshape(a.shape) !=
                               np.array([start.pal[i] for i in b.ravel()]).reshape(b.shape))
            if len(diff):
                p = tuple(int(diff[0][k]) + min(c[k], c[k + 3]) for k in range(3))
                F.add("RESET", s, r, p, "after a run's writes the reset leaves %s where the run started with %s"
                      % (w.get(*p), start.get(*p)))
                break


# ------------------------------------------------------------------------------------------------- pass 2 (AUDIT2)
# Routes, secrets, shortcuts, set pieces, parkour v2, life and the return margin, each read from the generated text and
# walked on this file's own graph. What the pass-2 builders' checks (dungeon_rooms.problems, dungeon_setpieces,
# dungeon_parkour, dungeon_life) decide is never asked.
def tick_boxes(pack, s, r, target):
    """[(conds, box)] of the room tick's lines `execute [if score H matches R]... if entity @s[box] run <target...>`;
    conds [(holder, range, negate)]."""
    out = []
    for ln in pack.lines(room_fn(s, r, "tick")):
        if " run " not in ln:
            continue
        head, body = ln.split(" run ", 1)
        if not body.startswith(target):
            continue
        m = re.search(r"if entity @s\[([^\]]*)\]", head)
        if not m:
            continue
        conds = [(h, rg, k == "unless") for k, h, rg in re.findall(r"(if|unless) score (\S+) dg\.rs matches (\S+)", head)]
        out.append((conds, sel_box(split_args(m.group(1))), body))
    return out


def conds_hold(scores, conds):
    return all(in_range(scores.get((h, "dg.rs")), rg) != neg for h, rg, neg in conds)


def ledge_boxes(pack, s, r):
    """{dg.ck value: box} of the tick's checkpoint lines."""
    out = {}
    for _c, box, body in tick_boxes(pack, s, r, "scoreboard players set @s dg.ck "):
        out[int(body.split()[-1])] = box
    return out


def node_pos(gr, n):
    x, y, z = gr.xyz(n)
    return (x + 0.5, float(y), z + 0.5)


def in_box(s, r, gr, n):
    b = s.boxes.get(r)
    x, y, z = gr.xyz(n)
    return bool(b) and b[0] <= x <= b[3] and b[1] <= y <= b[4] and b[2] <= z <= b[5]


def reach_from(gr, sources, catch=frozenset(), limit=400000):
    seen = set(sources)
    q = collections.deque(sources)
    while q and len(seen) < limit:
        u = q.popleft()
        if u in catch:
            continue
        for v, _ne, _c in gr.edges(u):
            if v >= 0 and v not in seen:
                seen.add(v)
                q.append(v)
    return seen


def returnable(gr, need, backs, catch):
    """The reached nodes that can walk back to the back rip, every gate open (a catch node counts as returned: the
    walk audit proves its teleport lands well)."""
    rev = collections.defaultdict(list)
    for u in need:
        if u in catch:
            continue
        for v, _ne, _c in gr.edges(u):
            if v >= 0:
                rev[v].append(u)
    ok = set(backs) | (set(catch) & set(need))
    q = collections.deque(ok)
    while q:
        v = q.popleft()
        for u in rev.get(v, ()):
            if u not in ok:
                ok.add(u)
                q.append(u)
    return ok


def crop(world, lo, hi):
    """A copy of the world's box lo..hi (sharing the palette), so a state's graph is built on the room, not the slot."""
    lo = [max(lo[k], world.lo[k]) for k in range(3)]
    hi = [min(hi[k], world.lo[k] + world.shape[k] - 1) for k in range(3)]
    w = World.__new__(World)
    w.lo = tuple(lo)
    w.shape = tuple(hi[k] - lo[k] + 1 for k in range(3))
    sl = tuple(slice(lo[k] - world.lo[k], hi[k] - world.lo[k] + 1) for k in range(3))
    w.g = world.g[sl].copy()
    w.pal, w.idx, w.writes_outside = world.pal, world.idx, []
    # a solid frame, so no edge leaves the array (the frame is outside the room: callers count it as left)
    v = w.bid("minecraft:bedrock")
    w.g[0, :, :] = w.g[-1, :, :] = v
    w.g[:, :, 0] = w.g[:, :, -1] = v
    w.g[:, 0, :] = w.g[:, -1, :] = v
    return w


def box_slice(world, b, pad=0):
    return tuple(slice(max(0, b[k] - pad - world.lo[k]), b[k + 3] + pad - world.lo[k] + 1) for k in range(3))


def route_audit(pack, s, shell, start, F, base_walks):
    """A fork's routes: each one ALONE (the other routes' boxes made solid) reaches the far rip and traps no one in the
    gate order a player on it meets. Returns [(rooms the clock pays for, per-room walk)] per route choice."""
    side = {r for rooms in s.sides.values() for r in rooms}
    paid = [r for r in s.rooms if r not in side]
    if not s.forks:
        return [(paid, base_walks)] if base_walks else []
    out = []
    import itertools
    known = {(f["cat"], f["slot"], f["room"], f["at"]) for f in F}
    for combo in itertools.product(*[[(f, r) for r in routes] for f, routes in sorted(s.forks.items())]):
        blocked = set()
        for f, rid in combo:
            for other, rooms in s.forks[f].items():
                if other != rid:
                    blocked |= set(rooms)
        blocked &= set(s.boxes)
        T = Findings()
        _gr, walks, _extra = walk_audit(pack, s, shell, start, T, blocked=sorted(blocked))
        label = ", ".join("%s/%s" % c for c in combo)
        for f in T:
            if f["cat"] in ("WALK", "TRAP", "VOID") and (f["cat"], f["slot"], f["room"], f["at"]) not in known:
                F.add(f["cat"], s, f["room"], f["at"], "[route %s alone] %s" % (label, f["msg"]))
        F.stats[s.dungeon]["fork_routes_walked"] += 1
        if walks:
            out.append(([r for r in paid if r not in blocked], walks))
    return out


def relic_triggers(pack, s, r):
    """{relic id: (centre, radius)} from the tick's `execute positioned X Y Z if entity @s[distance=..R] run function
    .../relic_<id>` lines."""
    out = {}
    for ln in pack.lines(room_fn(s, r, "tick")):
        m = re.match(r"execute positioned (\S+) (\S+) (\S+) if entity @s\[distance=\.\.([0-9.]+)\] run function "
                     + re.escape(room_fn(s, r, "relic_")) + r"(\w+)$", ln)
        if m:
            out[m.group(5)] = (tuple(float(v) for v in m.group(1, 2, 3)), float(m.group(4)))
    return out


def trigger_nodes(gr, s, r, centre, radius):
    b = s.boxes[r]
    out = set()
    for x in range(int(centre[0] - radius) - 1, int(centre[0] + radius) + 2):
        for z in range(int(centre[2] - radius) - 1, int(centre[2] + radius) + 2):
            for y in range(int(centre[1] - radius) - 1, int(centre[1] + radius) + 2):
                if not (b[0] <= x <= b[3] and b[2] <= z <= b[5]):
                    continue
                n = gr.idx(x, y, z)
                if gr.N[n] and math.dist((x + 0.5, y, z + 0.5), centre) <= radius:
                    out.add(n)
    return out


def secret_audit(pack, s, start, gr, F):
    """Secrets (DUNGEON_ROOMS 1a, 9): the rift pick breaks nothing but seams and cracked faces; each cracked face opens
    a chamber reached only through it, walked back out of, and put back by the slot reset; each balcony alcove is
    reached with a jump and not without one; each relic's pickup is reached WITH its secret's trick and not without."""
    info = getattr(gr, "info", None)
    if not info:
        return
    need, backs, catch = info["need"], info["backs"], info["catch"]
    lo = start.lo
    # every cell of the start world the pick may break, by room
    ids = [i for i, b in enumerate(start.pal) if base_id(b) in s.pick]
    cells = [tuple(int(v) for v in p + np.array(lo)) for p in np.argwhere(np.isin(start.g, ids))] if ids else []
    by_room = collections.defaultdict(list)
    for c in cells:
        by_room[room_at(s, *c)].append(c)
    for r, cs in sorted(by_room.items(), key=lambda kv: str(kv[0])):
        rec = room_rec(s, r) if r else {}
        n_cracked = sum(1 for x in rec.get("secrets") or [] if x.get("type") == "cracked")
        if rec.get("kind") == "resources":
            continue
        if not n_cracked:
            F.add("SECRET", s, r, cs[0], "the rift pick may break %d cells here (%s) and the room has no seam and no "
                  "cracked secret" % (len(cs), base_id(start.get(*cs[0]))))
        elif len(cs) != 2 * n_cracked:
            F.add("SECRET", s, r, cs[0], "%d cracked secrets and %d breakable cells (a face is 1 x 2)" % (n_cracked, len(cs)))
    for r in s.rooms:
        rec = room_rec(s, r)
        secs = rec.get("secrets") or []
        if not secs:
            continue
        trig = relic_triggers(pack, s, r)
        F.stats[s.dungeon]["relic_triggers"] += len(trig)
        tnodes = {k: trigger_nodes(gr, s, r, c, rad) for k, (c, rad) in trig.items()}
        for k, ns in tnodes.items():
            if not ns:
                F.add("SECRET", s, r, trig[k][0], "relic %s: no cell a player can stand on is within its pickup" % k)
        cracked = [x for x in secs if x.get("type") == "cracked"]
        balcony = [x for x in secs if x.get("type") == "balcony"]
        faces = [c for c in by_room.get(r, [])]
        # the faces as groups (each 1 x 2 face is one group of touching cells)
        groups = []
        for c in faces:
            for g in groups:
                if any(sum(abs(c[i] - d[i]) for i in range(3)) == 1 for d in g):
                    g.append(c)
                    break
            else:
                groups.append([c])
        if cracked and not groups:
            F.add("SECRET", s, r, None, "%d cracked secrets and no face the pick may break" % len(cracked))
        reached_by_group = {}
        for gi, g in enumerate(groups):
            w2 = gr.world.copy()                 # every gate open, this face broken
            for c in g:
                w2.write(c, c, "minecraft:air")
            g2 = Graph(w2)
            seen = reach_from(g2, [info["arrive"]], catch)
            new = seen - set(need)
            F.stats[s.dungeon]["cracked_faces_checked"] += 1
            if not new:
                F.add("SECRET", s, r, g[0], "breaking this face opens no cell a player could not already reach")
            ok = returnable(g2, seen, set(backs), catch)
            stuck = [n for n in new if n not in ok]
            if stuck:
                F.add("TRAP", s, r, g2.xyz(stuck[0]), "behind the cracked face: %d cells with no walk back" % len(stuck))
            away = sorted(n for n in new if room_of_node(s, g2, n) != r)
            if away:
                F.add("SECRET", s, r, g2.xyz(away[0]), "breaking this face opens %d cells outside its own room (%s): a "
                      "way round the route" % (len(away), room_of_node(s, g2, away[0])))
            reached_by_group[gi] = seen
            # the slot's reset puts the face back
            w3 = start.copy()
            for c in g:
                w3.write(c, c, "minecraft:air")
            sim = Sim(pack, w3)
            entrant(sim, s, 1)
            sim.call(FN + "slot/s%d/reset" % s.g, Ctx(ex=sim.player, pos=sim.player.pos))
            for c in g:
                if w3.get(*c) != start.get(*c):
                    F.add("RESET", s, r, c, "a broken cracked face is %s after the slot's reset, %s before"
                          % (w3.get(*c), start.get(*c)))
                    break
        nj = set()
        if balcony:
            gr.jumps = False
            try:
                nj = reach_from(gr, [n for n in need if not in_box(s, r, gr, n)], catch)
            finally:
                gr.jumps = True
            jump_only = {n for n in need if in_box(s, r, gr, n)} - nj
            F.stats[s.dungeon]["balcony_rooms_checked"] += 1
            if not jump_only:
                F.add("SECRET", s, r, None, "a balcony secret, and every cell of the room is reached without a jump")
        # each relic is its secret's: the record names it on the secret (or on the room, for a room's only secret)
        typ = {}
        for x in secs:
            rid = x.get("relic") or ((rec.get("params") or {}).get("relic") if len(secs) == 1 else None)
            if rid:
                typ[rid] = x.get("type")
        for rid in sorted(set(typ) - set(trig)):
            F.add("SECRET", s, r, None, "the record's relic %s has no pickup line in the room's tick" % rid)
        for k, ns in tnodes.items():
            t = typ.get(k)
            if t is None:
                F.add("SECRET", s, r, trig[k][0], "the tick picks up relic %s, which no secret of the record names" % k)
                continue
            if not ns:
                continue
            plain = ns & set(need)
            if t == "cracked":
                if plain:
                    F.add("SECRET", s, r, gr.xyz(sorted(plain)[0]), "relic %s is picked up with every face whole" % k)
                if not any(ns & reached_by_group[gi] for gi in reached_by_group):
                    F.add("SECRET", s, r, trig[k][0], "relic %s is not reached with any cracked face broken" % k)
            elif t == "balcony":
                if not plain:
                    F.add("SECRET", s, r, trig[k][0], "relic %s is not reached even with jumps" % k)
                if ns & nj:
                    F.add("SECRET", s, r, gr.xyz(sorted(ns & nj)[0]), "relic %s is picked up without a jump" % k)


def shortcut_audit(pack, s, start, gr, F):
    """Shortcuts (1a): `room/<d>/<far>/s<g>/shortcut_<id>` opens a way; it is opened only from the far room's own cells,
    the far rip was reached with it shut (never the only way), opening it traps no one, and the slot reset shuts it."""
    info = getattr(gr, "info", None)
    if not info:
        return
    need, backs, catch = info["need"], info["backs"], info["catch"]
    for r in s.rooms:
        rec = room_rec(s, r)
        pre = room_fn(s, r, "shortcut_")
        fns = sorted(f for f in pack.fns if f.startswith(pre))
        declared = {c["id"]: c for c in rec.get("shortcuts") or []}
        for cid in sorted(set(declared) - {f[len(pre):] for f in fns}):
            F.add("SHORTCUT", s, r, None, "the record's shortcut %s has no function %s%s" % (cid, pre, cid))
        for fid in fns:
            cid = fid[len(pre):]
            near = (declared.get(cid) or {}).get("to")
            F.stats[s.dungeon]["shortcuts_checked"] += 1
            w = gr.world.copy()
            before = w.flags()
            sim = Sim(pack, w)
            entrant(sim, s, 1)
            sim.call(fid, Ctx(ex=sim.player, pos=sim.player.pos))
            opened = ((before & SOLID) != 0) & ((w.flags() & SOLID) == 0)
            if not opened.any():
                F.add("SHORTCUT", s, r, None, "shortcut %s opens nothing" % cid)
                continue
            oc = [tuple(int(v) for v in p + np.array(w.lo)) for p in np.argwhere(opened)]
            rooms = {room_at(s, *c) for c in oc}
            if near and near not in rooms:
                F.add("SHORTCUT", s, r, oc[0], "shortcut %s opens cells in %s, not into %s" % (cid, sorted(map(str, rooms)), near))
            trig = [box for _c, box, body in tick_boxes(pack, s, r, "function " + fid)]
            tn = {n for n in need if any(hits_box(node_pos(gr, n), b) for b in trig)}
            if not tn:
                F.add("SHORTCUT", s, r, None, "shortcut %s: no reached cell stands in its trigger" % cid)
            wrong = {room_at(s, *gr.xyz(n)) for n in tn} - {r}
            if wrong:
                F.add("SHORTCUT", s, r, gr.xyz(sorted(tn)[0]), "shortcut %s is opened from %s, not from its own (far) "
                      "room" % (cid, sorted(map(str, wrong))))
            g2 = Graph(w)
            seen = reach_from(g2, [info["arrive"]], catch)
            ok = returnable(g2, seen, set(backs), catch)
            stuck = [n for n in seen if n not in ok]
            if stuck:
                F.add("TRAP", s, r, g2.xyz(stuck[0]), "with shortcut %s open, %d cells cannot get back" % (cid, len(stuck)))
            # the slot reset shuts it
            w3 = start.copy()
            sim = Sim(pack, w3)
            entrant(sim, s, 1)
            sim.call(fid, Ctx(ex=sim.player, pos=sim.player.pos))
            sim.call(FN + "slot/s%d/reset" % s.g, Ctx(ex=sim.player, pos=sim.player.pos))
            for c in oc:
                if w3.get(*c) != start.get(*c):
                    F.add("RESET", s, r, c, "shortcut %s is still open after the slot's reset (%s, was %s)"
                          % (cid, w3.get(*c), start.get(*c)))
                    break
            # once opened in a run, the next run starts shut: the holder the function guards on is back at 0
            # the guard is the holder the shortcut function itself tests: a vault keeps its chests on the same
            # #s<g>r<i>c<j> shape (tools/dungeon_puzzles.py), and those are not a shortcut's (false RESET, 2026-10-10)
            guards = {h for ln in pack.lines(fid) for h in re.findall(r"#s%dr\d+c\d+" % s.g, ln)}
            hold = [h for h, _o in sim.scores if h in guards]
            if any(sim.scores.get((h, "dg.rs")) not in (0, None) for h in hold):
                F.add("RESET", s, r, None, "shortcut %s's once-a-run guard is not reset by the slot's reset" % cid)


def _gravity(sim, w):
    p = sim.player.pos
    x, y, z = (int(math.floor(v)) for v in p)
    k = 0
    while k < 80:
        below, at = block_flags(w.get(x, y - 1, z)), block_flags(w.get(x, y, z))
        if at & (WATER | CLIMB) or (below & SOLID and not below & NOSUP):
            break
        y -= 1
        k += 1
    sim.player.pos = (p[0], float(y), p[2])


def setpiece_audit(pack, s, start, gr, F):
    """Set pieces (tools/dungeon_setpieces.py): the member is walked through the room and made to wait at points of
    it while the REAL tick runs (a fall the floor gives way under is followed); every block state the room passes through
    is collected, and in each one every cell a player can be on still reaches a ledge, a door out or a floor that
    teleports; new water never touches a door, a ledge's top or a cell it would flow into; and the slot reset (and the
    piece's own restore/drain) puts the room back exactly."""
    info = getattr(gr, "info", None)
    if not info:
        return
    need, path = info["need"], info["path"] or []
    for i, r in enumerate(s.rooms):
        rec = room_rec(s, r)
        if rec.get("kind") != "setpiece":
            continue
        piece = (rec.get("params") or {}).get("piece", "?")
        b = s.boxes[r]
        ledges = ledge_boxes(pack, s, r)
        own = [n for n in path if in_box(s, r, gr, n)] or sorted((n for n in need if in_box(s, r, gr, n)),
                                                                 key=lambda n: gr.xyz(n)[0])
        if not own:
            F.add("SETPIECE", s, r, None, "no reached cell in the room")
            continue
        rescue = [(c, box) for tgt in ("function " + room_fn(s, r, ""),)
                  for c, box, body in tick_boxes(pack, s, r, tgt)
                  if any(ln.startswith("tp @s") or " run tp @s" in ln for ln in pack.lines(body.split()[1]))]
        states = {}
        restores = sorted({body.split()[1] for _c, _b, body in tick_boxes(pack, s, r, "function " + room_fn(s, r, ""))
                           if body.split()[1].rsplit("/", 1)[-1] in ("restore", "drain")})

        def snap(sim, label):
            key = sim.w.g[box_slice(sim.w, b)].tobytes()
            if key not in states:
                states[key] = (sim.w.copy(), dict(sim.scores), label)

        def fresh():
            sim = Sim(pack, start.copy())
            entrant(sim, s, 1)
            sim.call(FN + "slot/s%d/reset" % s.g, Ctx(ex=sim.player, pos=sim.player.pos))
            # a member in this room has cleared every room before it: their gates stand open, as the walk's gate
            # states have them. Without this the reset's shut gate at this room's own door in (the previous room's
            # door out) read as a block filling cells a player stands in (TRAP at every set piece, 2026-10-10)
            for prev in s.rooms[:i]:
                fn_clear = room_fn(s, prev, "clear")
                if pack.lines(fn_clear):
                    sim.call(fn_clear, Ctx(ex=sim.player, pos=sim.player.pos))
            sim.player.pos = node_pos(gr, own[0])
            sim.call(room_fn(s, r, "enter"), Ctx(ex=sim.player, pos=sim.player.pos))
            return sim

        def step(sim, n=None, label=""):
            if n is not None:
                sim.player.pos = node_pos(gr, n)
            sim.tick += 1
            sim.call(room_fn(s, r, "tick"), Ctx(ex=sim.player, pos=sim.player.pos))
            _gravity(sim, sim.w)
            snap(sim, label)

        sim = fresh()
        entered_w = sim.w.copy()      # the room as a member finds it: the gates before it cleared (open)
        snap(sim, "entered")
        for k in range(0, len(own), 3):                  # walked through, a keeper pass every 3 cells
            step(sim, own[k], "walked to %d %d %d" % gr.xyz(own[k]))
        for k in range(len(own) - 1, -1, -6):           # and back
            step(sim, own[k], "walked back to %d %d %d" % gr.xyz(own[k]))
        for st in range(0, len(own), 4):                 # walked to every fourth cell and kept waiting there
            sim = fresh()
            for k in range(0, st + 1, 3):
                step(sim, own[k])
            for t in range(45):
                step(sim, None, "waited %d passes at %d %d %d" % ((t + 1,) + gr.xyz(own[st])))
        # the holders swept: every pass counter the tick keeps (#s<g>r<i>m<j>) started at 0, the member parked where no
        # box of the tick holds them (west of the room, then east of it: a piece keyed on x closes all or nothing),
        # the tick run until nothing changes: every value the tick can reach, each pass's writes on the last's
        hold = sorted({h for ln in pack.lines(room_fn(s, r, "tick"))
                       for h in re.findall(r"#s%dr%dm\d+" % (s.g, i), ln)})
        for side, px in (("west", b[0] - 40.5), ("east", b[3] + 40.5)):
            sim = fresh()
            for h in hold:
                if sim.scores.get((h, "dg.rs"), 0) < 0:
                    sim.scores[(h, "dg.rs")] = 0
            sim.player.pos = (px, float(b[1] + 1), (b[2] + b[5]) / 2.0)
            last = None
            for t in range(120):
                sim.tick += 1
                sim.call(room_fn(s, r, "tick"), Ctx(ex=sim.player, pos=sim.player.pos))
                sim.player.pos = (px, float(b[1] + 1), (b[2] + b[5]) / 2.0)
                now = tuple(sim.scores.get((h, "dg.rs")) for h in hold)
                snap(sim, "holders %s = %s, the member parked %s" % (",".join(h[-2:] for h in hold), now, side))
                if now == last:
                    break
                last = now
            F.stats[s.dungeon]["setpiece_holder_passes"] += t + 1
        F.stats[s.dungeon]["setpiece_states"] += len(states)
        pad = 12
        start_sl = box_slice(start, b)
        reported = set()
        # the way on: from any state, a member standing on a ledge (and that ledge's tick run once) can still walk to the
        # room's way out -- a piece that never puts back what it took is a run nobody finishes, even if nobody is trapped
        k_out = max((k for k, n in enumerate(path or []) if in_box(s, r, gr, n)), default=None)
        out_cells = [gr.xyz(n) for n in (path or [])[k_out + 1:k_out + 4]] if k_out is not None else []
        perches = [[n for n in need if in_box(s, r, gr, n) and hits_box(node_pos(gr, n), lb)][:1]
                   for _k, lb in sorted(ledges.items())] or [[own[0]]]
        for key, (w, scores, label) in list(states.items()):
            if not out_cells:
                break
            for perch in perches:
                if not perch:
                    continue
                w2 = w.copy()
                sim2 = Sim(pack, w2)
                entrant(sim2, s, 1)
                sim2.scores.update(scores)
                sim2.player.pos = node_pos(gr, perch[0])
                sim2.call(room_fn(s, r, "tick"), Ctx(ex=sim2.player, pos=sim2.player.pos))
                cw = crop(w2, [b[0] - pad, b[1] - pad, b[2] - pad], [b[3] + pad, b[4] + pad, b[5] + pad])
                g2 = Graph(cw)
                src = g2.idx(*Sim.blk(sim2.player.pos))
                tgt = {g2.idx(*c) for c in out_cells}
                if not (reach_from(g2, [src]) & tgt) and ("WAYON",) not in reported:
                    reported.add(("WAYON",))
                    F.add("SOFTLOCK", s, r, Sim.blk(sim2.player.pos), "[set piece %s, %s] standing on this ledge "
                          "(its tick run) the way out of the room stays cut" % (piece, label))
        for key, (w, scores, label) in states.items():
            cw = crop(w, [b[0] - pad, b[1] - pad, b[2] - pad], [b[3] + pad, b[4] + pad, b[5] + pad])
            g2 = Graph(cw)
            # where a player can be: every cell of the room the plain walk reached, fallen to where it lands now
            starts = set()
            encased = []
            for n in need:
                if not in_box(s, r, gr, n):
                    continue
                m = g2.idx(*gr.xyz(n))
                if g2.N[m]:
                    starts.add(m)
                elif g2.P[m] and g2.L[m] >= 0:
                    starts.add(g2.L[m])
                elif not (g2.P[m] and g2.P[m + g2.SY]):
                    encased.append(gr.xyz(n))       # the piece put a block where a player may be standing
            if encased and ("ENCASE",) not in reported:
                reported.add(("ENCASE",))
                F.add("TRAP", s, r, encased[0], "[set piece %s, %s] %d cells a player may stand in are filled with "
                      "blocks" % (piece, label, len(encased)))
            good = set()
            allc = reach_from(g2, list(starts))
            for m in allc:
                x, y, z = g2.xyz(m)
                p = (x + 0.5, float(y), z + 0.5)
                if not (b[0] <= x <= b[3] and b[1] <= y <= b[4] and b[2] <= z <= b[5]):
                    good.add(m)
                elif any(hits_box(p, lb) for lb in ledges.values()):
                    good.add(m)
                elif any(conds_hold(scores, c) and hits_box(p, box) for c, box in rescue):
                    good.add(m)
            stuck = walk_out(g2, list(allc), good, limit=10 ** 7)
            if stuck and ("TRAP",) not in reported:
                reported.add(("TRAP",))
                F.add("TRAP", s, r, g2.xyz(stuck[0]), "[set piece %s, %s] %d cells a player can be on reach no ledge, "
                      "door or teleporting floor" % (piece, label, len(stuck)))
            # water the piece placed
            sub, st0 = w.g[box_slice(w, b, 1)], start.g[box_slice(start, b, 1)]
            wat = np.array([base_id(x) == "water" for x in w.pal])
            new = wat[sub] & ~wat[st0]
            if new.any():
                o = [max(b[k] - 1, w.lo[k]) for k in range(3)]
                for p in np.argwhere(new):
                    c = tuple(int(p[k]) + o[k] for k in range(3))
                    pos = (c[0] + 0.5, float(c[1]), c[2] + 0.5)
                    flow = [d for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0))
                            if not block_flags(w.get(c[0] + d[0], c[1] + d[1], c[2] + d[2])) & (SOLID | WATER)]
                    if any(hits_box(pos, lb) for lb in ledges.values()):
                        msg = "water stands on a ledge's top"
                    elif flow:
                        msg = "water placed here flows on into %d open neighbours (it spreads past what the drain clears)" % len(flow)
                    elif room_at(s, *c) != r:
                        msg = "water placed outside the room's box"
                    else:
                        continue
                    if ("FLOOD", msg[:20]) not in reported:
                        reported.add(("FLOOD", msg[:20]))
                        F.add("SETPIECE", s, r, c, "[%s, %s] %s" % (piece, label, msg))
            # the slot reset, and the piece's own restore/drain, put the room back
            for fid in ["reset"] + restores:
                w2 = w.copy()
                sim2 = Sim(pack, w2)
                entrant(sim2, s, 1)
                sim2.scores.update(scores)
                sim2.call(FN + "slot/s%d/reset" % s.g if fid == "reset" else fid, Ctx(ex=sim2.player, pos=sim2.player.pos))
                # the slot reset puts back the START (every gate shut); the piece's own restore/drain runs mid-run and
                # puts back the room as the member ENTERED it (the gates before it open): against the start, the open
                # gate at its own door in read as a fault (8 false RESETs, 2026-10-10)
                base = start if fid == "reset" else entered_w
                diff = np.argwhere(w2.g[box_slice(w2, b)] != base.g[box_slice(base, b)])
                if len(diff):
                    c = tuple(int(diff[0][k]) + b[k] for k in range(3))
                    tag = ("RESET", fid)
                    if tag not in reported:
                        reported.add(tag)
                        F.add("RESET", s, r, c, "[set piece %s, %s] after %s the room has %s where it started with %s "
                              "(%d cells differ)" % (piece, label, fid.rsplit("/", 1)[-1], w2.get(*c), base.get(*c), len(diff)))


def _components(gr, nodes, ban):
    """Connected sets of `nodes` (less `ban`) by walking only: no jump, no drop of more than one."""
    comp = {}
    k = 0
    saved, gr.jumps = gr.jumps, False
    try:
        for n in nodes:
            if n in comp or n in ban:
                continue
            comp[n] = k
            q = collections.deque([n])
            while q:
                u = q.popleft()
                for v, _ne, _c in gr.edges(u):
                    if v >= 0 and v in nodes and v not in ban and v not in comp and abs(gr.xyz(v)[1] - gr.xyz(u)[1]) <= 1:
                        comp[v] = k
                        q.append(v)
            k += 1
    finally:
        gr.jumps = saved
    return comp


def _route(gr, src, dst, allowed, forbid):
    prev = {n: None for n in src}
    q = collections.deque(src)
    while q:
        u = q.popleft()
        if u in dst:
            out = [u]
            while prev[out[-1]] is not None:
                out.append(prev[out[-1]])
            return out[::-1]
        for v, _ne, _c in gr.edges(u):
            if v >= 0 and v in allowed and v not in forbid and v not in prev:
                prev[v] = u
                q.append(v)
    return None


def parkour_audit(pack, s, gr, F):
    """Parkour v2 (tools/dungeon_parkour.py): every ledge is stood on; the lowest floor of the chasm is all catch (a fall
    never lands where nothing teleports); from each ledge to the next there is a way on this file's jumps without
    falling; and the fork is two ways: with every platform the first way stands on taken away, a second still
    finishes."""
    info = getattr(gr, "info", None)
    if not info:
        return
    need, catch = info["need"], info["catch"]
    for r in s.rooms:
        rec = room_rec(s, r)
        if rec.get("kind") != "parkour":
            continue
        ledges = ledge_boxes(pack, s, r)
        room = {n for n in need if in_box(s, r, gr, n)}
        if not room or not ledges:
            F.add("PARKOUR", s, r, None, "no reached cell or no checkpoint line in the room")
            continue
        lnodes = {k: {n for n in room if hits_box(node_pos(gr, n), bx)} for k, bx in ledges.items()}
        for k, ns in sorted(lnodes.items()):
            if not ns:
                F.add("PARKOUR", s, r, None, "checkpoint %d's ledge is never stood on" % k)
        low = min(gr.xyz(n)[1] for n in room)
        bare = [n for n in room if gr.xyz(n)[1] == low and n not in catch]
        if bare:
            F.add("PARKOUR", s, r, gr.xyz(bare[0]), "%d cells of the chasm's floor are not a catch floor: a fall there "
                  "is not teleported" % len(bare))
        allowed = room - set(catch)
        ledge_all = set().union(*lnodes.values())
        comps = _components(gr, allowed, ledge_all)
        forks = []
        order = sorted(lnodes)
        for a, z in zip(order, order[1:]):
            if not lnodes[a] or not lnodes[z]:
                continue
            p1 = _route(gr, lnodes[a], lnodes[z], allowed, set())
            if p1 is None:
                F.add("PARKOUR", s, r, None, "no way from ledge %d to ledge %d without falling" % (a, z))
                continue
            used = {comps[n] for n in p1 if n in comps}
            forbid = {n for n, c in comps.items() if c in used}
            p2 = _route(gr, lnodes[a], lnodes[z], allowed, forbid)
            if p2 is not None:
                forks.append((a, z))
        F.stats[s.dungeon]["parkour_fork_sections"] += len(forks)
        p = rec.get("params") or {}
        want = p.get("fork", len(ledges) - 1 >= 3)
        if want is not False and want is not None and not forks:
            F.add("PARKOUR", s, r, None, "the record asks for a fork (params.fork %r, %d sections) and no section has a "
                  "second way that finishes when the first way's platforms are taken away" % (p.get("fork"), len(ledges) - 1))


def life_audit(pack, s, start, gr, F):
    """LIFE's ambient Pokemon (tools/dungeon_life.py), read from the table the pack loads into storage: every spot is a
    place it can stand, in its own room and clear of the doors; and the generated cleanup really removes them -- the
    room's reset its own, the slot's free all of them, the slot's tend a stale run's."""
    info = getattr(gr, "info", None)
    if not info:
        return
    need = info["need"]
    table = {}
    for ln in pack.lines(FN + "life/load"):
        m = re.match(r"data modify storage (\S+) life\.s%d\.r(\d+)v(\d+)b(\d+) set value (.*)$" % s.g, ln)
        if m:
            table[(int(m.group(2)), int(m.group(3)), int(m.group(4)))] = snbt(m.group(5))
    if not table:
        return
    # door cells: a reached cell beside a reached cell of another room
    doors = set()
    for n in need:
        ra = room_of_node(s, gr, n)
        for d in (gr.SX, -gr.SX, 1, -1):
            v = n + d
            if v in need and room_of_node(s, gr, v) != ra:
                doors.add(gr.xyz(n))
    reported = set()
    for (ri, v, band), entries in sorted(table.items()):
        r = s.rooms[ri] if ri < len(s.rooms) else None
        for e in entries:
            c = tuple(int(math.floor(float(e[k]))) for k in ("x", "y", "z"))
            F.stats[s.dungeon]["life_spots_checked"] += 1
            if room_at(s, *c) != r:
                msg = "an ambient %s's spot is in %s, not its room" % (e.get("species"), room_at(s, *c))
            elif not gr.N[gr.idx(*c)]:
                msg = "an ambient %s's spot is not a place it can stand (%s)" % (e.get("species"), start.get(*c))
            elif any(abs(c[0] - d[0]) <= 1 and abs(c[2] - d[2]) <= 1 and abs(c[1] - d[1]) <= 1 for d in doors):
                msg = "an ambient %s spawns in a doorway or the cell beside one" % e.get("species")
            else:
                continue
            if (r, c) not in reported:         # one line per spot (the variants and bands share spots)
                reported.add((r, c))
                F.add("LIFE", s, r, c, msg)
    # the cleanup, by simulation: enter every room with life, then each cleanup must leave none of what it owns
    rooms = sorted({ri for ri, _v, _b in table})

    def populated():
        sim = Sim(pack, start.copy())
        entrant(sim, s, 1)
        sim.scores[("#s%d" % s.g, "dg.run")] = 1
        sim.call(FN + "load", Ctx())
        sim.call(FN + "life/load", Ctx())
        sim.call(FN + "slot/s%d/reset" % s.g, Ctx(ex=sim.player, pos=sim.player.pos))
        for ri in rooms:
            sim.player.pos = node_pos(gr, next((n for n in need if room_of_node(s, gr, n) == s.rooms[ri]), info["arrive"]))
            sim.call(room_fn(s, s.rooms[ri], "enter"), Ctx(ex=sim.player, pos=sim.player.pos))
        return sim

    def life(sim, ri=None):
        return [e for e in sim.alive() if e.type == "cobblemon:pokemon" and "dg.lf" in e.tags and
                (ri is None or sim.scores.get((e.name, "dg.rs")) == ri)]
    sim = populated()
    n0 = len(life(sim))
    F.stats[s.dungeon]["life_spawned"] += n0
    if not n0:
        F.add("LIFE", s, None, None, "entering every room with ambient life spawns none in the simulation")
        return
    loose = [e for e in life(sim) if not {"dg.keep", "dg.s%d" % s.g}.issubset(e.tags)]
    if loose:
        F.add("LIFE", s, None, loose[0].pos, "%d ambient Pokemon lack the keep or slot tag" % len(loose))
    for ri in rooms:
        before = {e.name for e in life(sim) if sim.scores.get((e.name, "dg.rs")) != ri}
        sim.call(room_fn(s, s.rooms[ri], "reset"), Ctx(ex=sim.player, pos=sim.player.pos))
        if life(sim, ri):
            F.add("LIFE", s, s.rooms[ri], None, "the room's reset leaves %d of its ambient Pokemon" % len(life(sim, ri)))
        if {e.name for e in life(sim)} != before:
            F.add("LIFE", s, s.rooms[ri], None, "the room's reset removes another room's ambient Pokemon")
    for fid, how in (("free", None), ("tend", "stale")):
        sim = populated()
        if how == "stale":
            sim.scores[("#s%d" % s.g, "dg.run")] = sim.scores.get(("#s%d" % s.g, "dg.run"), 0) + 1000
        sim.call(FN + "slot/s%d/%s" % (s.g, fid), Ctx(ex=sim.player, pos=sim.player.pos))
        if life(sim):
            F.add("LIFE", s, None, None, "slot %s%s leaves %d ambient Pokemon" % (fid, " (a stale run)" if how else "",
                                                                                 len(life(sim))))


def margin_audit(pack, doc, s, gr, F):
    """The return margin (m/margin) prices the way back by x alone. Run the generated margin on the member at a cell to
    get its estimate; measure the real walk back to the back rip on this file's graph (every gate open) at the same
    pace; report each room where the warning would come late, and by how much (DUNGEON_ROOMS 8: a finding for the
    integrator, not a trap)."""
    info = getattr(gr, "info", None)
    if not info or not info["backs"]:
        return
    need, catch = info["need"], info["catch"]
    di = [d["id"] for d in doc["dungeons"]].index(s.dungeon) + 1
    sim = Sim(pack, World((0, 0, 0), (1, 1, 1)))
    entrant(sim, s, 1)
    sim.call(FN + "load", Ctx())
    sim.scores[(PLAYER, "dg.dun")] = di
    sim.scores[(PLAYER, "dg.clock")] = 10 ** 8
    sim.scores[(PLAYER, "dg.rate")] = 1

    # A rooms dungeon's margin prices the room's own walk back (dg.wb), set each pass by the generated
    # slot/s<g>/rooms from the hull the member stands in; a spine dungeon's prices x. Both are READ from the generated
    # text here and run through the real m/margin: never the generator's numbers (DG2-INTEGRATE moved the margin from x
    # to dg.wb; this read x alone and reported 260 late rooms the pack does not have).
    wb_boxes = []
    for ln in pack.lines(FN + "slot/s%d/rooms" % s.g):
        m = re.match(r"execute if entity @s\[([^\]]*)\] run scoreboard players set @s dg\.wb (\d+)$", ln)
        if m:
            wb_boxes.append((sel_box(split_args(m.group(1))), int(m.group(2))))

    def wb_at(n):
        x, y, z = gr.xyz(n)
        val = None
        for box, v in wb_boxes:            # in order: the last box that holds the cell stands, as the function does
            if box and all(lo <= c + 0.5 < hi for c, (lo, hi) in zip((x, y, z), box)):
                val = v
        return val

    def est(x, wb=None):
        sim.player.pos = (x + 0.5, 96.0, 0.5)
        if wb is None:
            sim.scores.pop((PLAYER, "dg.wb"), None)
        else:
            sim.scores[(PLAYER, "dg.wb")] = wb
        sim.call(FN + "m/margin", Ctx(ex=sim.player, pos=sim.player.pos))
        return sim.scores.get(("#bk", "dg.t"))
    x0 = int(min(gr.xyz(n)[0] for n in need))
    rooms_mode = bool(wb_boxes)
    if rooms_mode:
        e1, e2 = est(x0, 0), est(x0, 560)
    else:
        e1, e2 = est(x0), est(x0 + 560)
    if e1 is None or e2 is None or e2 == e1:
        F.add("MARGIN", s, None, None, "m/margin gives no estimate the audit can read")
        return
    pace = 560.0 / (e2 - e1)                       # blocks a second the margin assumes
    # the real walk back: Dijkstra from the back rip over reversed edges, jumps at their length, falls taken as caught
    radj = collections.defaultdict(list)
    for u in need:
        if u in catch:
            continue
        for v, _ne, c in gr.edges(u):
            if v >= 0:
                radj[v].append((u, c))
    dist = {n: 0 for n in info["backs"]}
    heap = [(0, n) for n in info["backs"]]
    heapq.heapify(heap)
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist.get(v, 1 << 60):
            continue
        for u, c in radj.get(v, ()):
            if d + c < dist.get(u, 1 << 60):
                dist[u] = d + c
                heapq.heappush(heap, (d + c, u))
    worst = {}
    for n, d in dist.items():
        x = gr.xyz(n)[0]
        if rooms_mode:
            w = wb_at(n)
            if w is None:          # out of every hull (a door column): the member keeps the last room's value
                continue
            late = d / pace - (e1 + w / pace)
        else:
            late = d / pace - (e1 + (x - x0) / pace)
        r = room_of_node(s, gr, n)
        if late > worst.get(r, (0,))[0]:
            worst[r] = (late, n, d)
    F.stats[s.dungeon]["margin_rooms_checked"] += len({room_of_node(s, gr, n) for n in dist})
    for r, (late, n, d) in sorted(worst.items(), key=lambda kv: -kv[1][0]):
        F.add("MARGIN", s, r, gr.xyz(n), "the way-back warning comes %d s late here: the walk back is %d blocks, the "
              "margin prices %d (%s, plus its fixed extra)" % (math.ceil(late), d, round(d - late * pace),
                                                                 "the room's dg.wb" if rooms_mode else "x alone"))


# ------------------------------------------------------------------------------------------------- static checks
def count_commands(pack, fid, memo, stack=()):
    if fid in memo:
        return memo[fid]
    if fid in stack:
        return 0
    n = 0
    for ln in pack.lines(fid):
        n += 1
        for m in re.finditer(r"(?:^|\brun )function (\S+)", ln):
            n += count_commands(pack, m.group(1), memo, stack + (fid,))
    memo[fid] = n
    return n


def static_audit(pack, doc, slots, F):
    eng = doc["engine"]
    sl = eng["slots"]
    border = eng["pocket"]["border"]
    margin = eng["pocket"].get("border_margin", 0)
    memo = {}
    # the chain limit: every place/s<g> under it; any function in the pack over it is named
    for s in slots:
        n = count_commands(pack, FN + "place/s%d" % s.g, memo)
        if n >= CHAIN_LIMIT:
            F.add("LIMIT", s, None, None, "place/s%d runs %d commands, over the chain limit %d" % (s.g, n, CHAIN_LIMIT))
    for f in sorted(pack.fns):
        n = count_commands(pack, f, memo)
        if n >= CHAIN_LIMIT:
            F.add("LIMIT", None, f.split(":", 1)[1], None, "runs %d commands in one chain, over %d: anything that calls "
                  "it is cut short silently" % (n, CHAIN_LIMIT))
    # every write of a slot inside its strip and the pocket's border; the slots' write boxes disjoint
    boxes = {}
    for s in slots:
        di = [d["id"] for d in doc["dungeons"]].index(s.dungeon)
        z0 = sl["rows_from_z"] + (di * sl["per_dungeon"] + s.k - 1) * sl["row_spacing"]
        x0 = sl.get("origin_x", 0)
        strip = (x0, z0, x0 + sl["strip_length"] - 1, z0 + sl["strip_width_max"] - 1)
        allw = []
        pre = (FN + "shells/s%d/" % s.g, FN + "slot/s%d/" % s.g)
        for f in pack.fns:
            if f.startswith(pre) or re.match(re.escape(FN) + r"room/[^/]+/[^/]+/s%d/" % s.g, f):
                for ln in pack.lines(f):
                    body = ln[ln.index(" run ") + 5:] if ln.startswith("execute") and " run " in ln else ln
                    t = tokens(body)
                    if t[0] in ("fill", "setblock") and not any(v.startswith("~") for v in t[1:4]):
                        c = [int(float(v)) for v in t[1:7 if t[0] == "fill" else 4]]
                        if t[0] == "setblock":
                            c = c + c
                        allw.append(c)
                        if min(c[0], c[3]) < strip[0] or max(c[0], c[3]) > strip[2] or \
                                min(c[2], c[5]) < strip[1] or max(c[2], c[5]) > strip[3]:
                            F.add("BOUNDS", s, f.split("/")[-2] if "/room/" in f else None, c[:3],
                                  "%s writes outside the slot's strip x %d..%d z %d..%d" % (f.split(":", 1)[1], *strip))
                        if min(c[0], c[2], c[3], c[5]) < border[0] + margin or max(c[0], c[2], c[3], c[5]) > border[1] - margin:
                            F.add("BOUNDS", s, None, c[:3], "a write past the pocket's border less its margin")
        if allw:
            a = np.array(allw)
            boxes[s.g] = (int(min(a[:, 0].min(), a[:, 3].min())), int(min(a[:, 2].min(), a[:, 5].min())),
                          int(max(a[:, 0].max(), a[:, 3].max())), int(max(a[:, 2].max(), a[:, 5].max())))
    gs = sorted(boxes)
    for i, g in enumerate(gs):
        for h in gs[i + 1:]:
            a, b = boxes[g], boxes[h]
            if a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]:
                F.add("BOUNDS", None, None, None, "slots s%d and s%d write into overlapping boxes %s %s" % (g, h, a, b))
    # slots of one dungeon are one dungeon: every slot's block writes are slot 1's moved by the row spacing
    by_d = collections.defaultdict(list)
    for s in slots:
        by_d[s.dungeon].append(s)

    def writes(s):
        out = collections.Counter()
        for r in s.rooms:
            for ln in pack.lines(FN + "shells/s%d/%s" % (s.g, r)):
                t = tokens(ln)
                if t[0] in ("fill", "setblock"):
                    out[(t[0], tuple(t[1:]))] += 1
        return out
    for d, ss in by_d.items():
        for s in ss:
            base = next(t for t in ss if t.vi == s.vi)     # slots of one variant are one dungeon
            if base is s:
                continue
            bw = writes(base)
            dz = (s.k - base.k) * sl["row_spacing"]
            moved = collections.Counter()
            for (h, t), n in bw.items():
                t = list(t)
                for zi in ((2, 5) if h == "fill" else (2,)):
                    t[zi] = str(int(float(t[zi])) + dz)
                moved[(h, tuple(t))] = n
            if moved != writes(s):
                F.add("SLOT", s, None, None, "the shell is not slot %d's moved %d in z (%d writes differ)"
                      % (base.k, dz, sum((moved - writes(s)).values()) + sum((writes(s) - moved).values())))
    # the overworld rips: each frame as the data places it, and no two rips' blocks or clicks within reach of each other
    rips = []
    for d in doc["dungeons"]:
        fr = d["rip"]["frame"]
        want = (fr["x0"], fr["y"], fr["z"], fr["x1"], fr["y"] + fr["height"] - 1, fr["z"])
        got = []
        for ln in pack.lines(FN + "rips/blocks_%s" % d["short"]):
            t = tokens(ln)
            if t[0] == "fill":
                got.append([int(float(v)) for v in t[1:7]])
        if got:
            a = np.array(got)
            have = (int(a[:, 0].min()), int(a[:, 1].min()), int(a[:, 2].min()),
                    int(a[:, 3].max()), int(a[:, 4].max()), int(a[:, 5].max()))
            if have != want:
                F.add("RIP", None, d["id"], None, "the rip's blocks span %s, the record's frame %s" % (have, want))
        else:
            F.add("RIP", None, d["id"], None, "no rip blocks for %s" % d["short"])
            continue
        click = None
        for ln in pack.lines(FN + "rips/entities_act"):
            if "minecraft:interaction" in ln and '"dg.rip_%s"' % d["short"] in ln:
                t = tokens(ln[ln.index("summon"):])
                click = tuple(float(v) for v in t[2:5])
        rips.append((d["id"], have, click))
    for i, (da, ba, ca) in enumerate(rips):
        for db, bb, cb in rips[i + 1:]:
            if ba[0] <= bb[3] and bb[0] <= ba[3] and ba[2] <= bb[5] and bb[2] <= ba[5] and ba[1] <= bb[4] and bb[1] <= ba[4]:
                F.add("RIP", None, da, None, "its frame overlaps %s's" % db)
            if ca and cb and math.dist(ca, cb) <= 3 + 2 * ENTITY_REACH:
                F.add("RIP", None, da, None, "its click is %.1f from %s's: one stand reaches both" % (math.dist(ca, cb), db))
    # every battle start in the pack follows a clawback begin in the same function
    for f in pack.fns:
        if not f.startswith(FN):
            continue
        seen_begin = False
        for ln in pack.lines(f):
            if "claw/begin" in ln or "claw/boss_begin" in ln:
                seen_begin = True
            if "start_battle" in ln and not seen_begin:
                F.add("MONEY", None, f.split(":", 1)[1], None, "a battle starts with no clawback begin before it")
    # the victory callback settles every dg.npc
    if not any("dg.npc" in c and "claw/settle" in c for c in victory(pack)):
        F.add("MONEY", None, "callback", None, "the battle_victory callback has no settle for a dg.npc loser")


def clock_audit(pack, doc, s, walk_sets, F):
    """The record's clocks against tools/dungeon_clock.required() fed with THIS audit's walks, and the generated
    threshold's clock against the record. `walk_sets`: [(rooms paid for, per-room walk)], one per choice of fork route
    (side rooms are optional and never paid); the clock must cover the slowest."""
    sys.path.insert(0, str(ROOT / "tools"))
    import dungeon_clock as DC
    sets = []
    for paid, walks in walk_sets:
        rooms = []
        for r in paid:
            rec = room_rec(s, r)
            rooms.append({"id": r, "kind": rec.get("kind"), "walk": walks.get(r, 0), "gate": rec.get("gate", "cleared" if
                          rec.get("kind") == "boss_arena" else "open"), "params": rec.get("params") or {}})
        sets.append((rooms, walks))
    slack = float(doc["engine"]["clock"]["slack_factor"])
    own = s.rec.get("clock_s_by_band") or {}
    try:
        theirs, their_total = DC.walked(doc, s.rec)
    except Exception as e:                      # noqa: BLE001 -- the comparison is informational
        theirs, their_total = None, None
        F.add("CLOCK", s, None, None, "tools/dungeon_clock.walked() failed: %s" % e)
    start = {}
    for ln in pack.lines(FN + "slot/s%d/start" % s.g):
        m = re.match(r"execute if score @s dg\.band matches (\d+) run scoreboard players set @s dg\.clock (\d+)", ln)
        if m:
            start[int(m.group(1))] = int(m.group(2))
    for b in doc["engine"]["bands"]:
        k = str(b["band"])
        have = int(own.get(k, b["clock_s"]))
        req, walks = max(((sum(DC.required(doc, s.rec, b["band"], rooms).values()), walks) for rooms, walks in sets),
                         key=lambda t: t[0])
        mine = int(math.ceil(req * slack / 60.0)) * 60
        if have < mine:
            F.add("CLOCK", s, None, None, "band %s: the record's clock %d s is under %d s, the clock formula fed with this "
                  "audit's measured walk of %d blocks (tools/dungeon_clock.py measured %s)"
                  % (k, have, mine, sum(walks.values()), their_total))
        if start and start.get(b["band"]) is not None and start[b["band"]] != have * UNITS_PER_S:
            F.add("CLOCK", s, None, None, "band %s: the threshold sets dg.clock %d, the record's %d s is %d"
                  % (k, start[b["band"]], have, have * UNITS_PER_S))
    return max(sum(w.values()) for _r, w in sets), their_total


# ------------------------------------------------------------------------------------------------- the audit
def build_files(doc=None):
    sys.path.insert(0, str(ROOT / "tools"))
    import dungeon as D
    return D.build(doc if doc is not None else D.load())


def audit(files, doc, blackout=None, only=None, bands=None, all_slots=True, modes=("win", "forfeit", "nospawn"),
          progress=None):
    pack = Pack(files)
    blackout = blackout if blackout is not None else json.loads(BLACKOUT.read_text(encoding="utf-8"))
    exempt = blackout.get("exempt_tag") or next((v for k, v in _walk_json(blackout) if k == "exempt_tag"), "cobblers.gm")
    caps = {b["band"]: max(b["caps"]) for b in doc["engine"]["bands"]}
    bands = bands or [b["band"] for b in doc["engine"]["bands"]]
    F = Findings()
    slots = discover(pack, doc)
    static_audit(pack, doc, slots, F)
    info = {}
    for d in doc["dungeons"]:
        if only and d["id"] not in only:
            continue
        ss = [s for s in slots if s.dungeon == d["id"]]
        if not ss:
            F.add("SLOT", None, d["id"], None, "the pack builds no slot for this dungeon")
            continue
        variants_seen = set()
        for s in ss:
            first = s is ss[0]
            new_variant = s.vi not in variants_seen       # the first slot that builds this variant (None: no variants)
            variants_seen.add(s.vi)
            if not first and not all_slots and not new_variant:
                continue
            say = progress or (lambda m: None)
            say("%s s%d: shell" % (s.dungeon, s.g))
            have = set(s.rooms)
            want = set(s.recs) if s.recs else have
            if have != want:
                F.add("SLOT", s, None, None, "the shell builds rooms %s the record (variant %s) does not have, and lacks %s"
                      % (sorted(have - want), s.vi, sorted(want - have)))
            shell = slot_world(pack, s)
            start, _ = start_world(pack, s, shell)
            # every slot is walked on ITS OWN shell: a variant (mirror, seed, swap, order) is a different dungeon
            say("%s s%d: walk" % (s.dungeon, s.g))
            gr, walks, extra = walk_audit(pack, s, shell, start, F)
            if extra is None or extra[0] is None:
                continue
            path, total, catch, need = extra
            if new_variant:
                reset_audit(pack, s, start, F)
                puzzle_audit(pack, s, start, gr, need, F)
                vault_audit(pack, doc, s, start, gr, need, F)
            say("%s s%d: routes, secrets, shortcuts, set pieces, parkour, life, margin" % (s.dungeon, s.g))
            walk_sets = route_audit(pack, s, shell, start, F, walks)
            secret_audit(pack, s, start, gr, F)
            shortcut_audit(pack, s, start, gr, F)
            setpiece_audit(pack, s, start, gr, F)
            parkour_audit(pack, s, gr, F)
            if new_variant:
                life_audit(pack, s, start, gr, F)
            margin_audit(pack, doc, s, gr, F)
            if walk_sets:
                got = clock_audit(pack, doc, s, walk_sets, F)
                info[d["id"]] = max(info.get(d["id"], got), got, key=lambda t: t[0])
            for band in (bands if first else bands[:1]):
                for mode in (modes if first and band == bands[0] else ("win",)):
                    say("%s s%d: run band %d %s" % (s.dungeon, s.g, band, mode))
                    Run(pack, s, start, band, caps, exempt, mode, F, gr, path, catch).go()
    return F, info


def _walk_json(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k, v
            yield from _walk_json(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_json(v)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", help="a generated pack folder (default: build it in memory from data/dungeons.json)")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--only", action="append", help="a dungeon id (repeatable)")
    ap.add_argument("--bands", help="comma list (default all six)")
    ap.add_argument("--quick", action="store_true", help="band 1; slot 1 of each dungeon (every mode) and the first "
                    "slot of each other variant (a win); every pass-2 check on those slots")
    ap.add_argument("-v", action="store_true", help="progress")
    a = ap.parse_args(argv)
    doc = json.loads(Path(a.data).read_text(encoding="utf-8"))
    files = Pack.from_dir(a.pack).files if a.pack else build_files(doc)
    bands = [int(b) for b in a.bands.split(",")] if a.bands else ([1] if a.quick else None)
    F, info = audit(files, doc, only=a.only, bands=bands, all_slots=not a.quick,
                    progress=(lambda m: print("..", m, file=sys.stderr)) if a.v else None)
    for f in F:
        print(fmt(f))
    for d, st in sorted(F.stats.items()):
        print("checked %s: %s" % (d, ", ".join("%s %d" % kv for kv in sorted(st.items()))))
    for d, (mine, theirs) in info.items():
        print("walk %s: %d blocks measured here, %s by tools/dungeon_clock.py" % (d, mine, theirs))
    print("dungeon_independent_audit: %d finding(s)" % len(F))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
