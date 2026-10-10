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

Exit status 1 on any finding. What this does NOT cover: anything Minecraft decides at runtime (whether Cobblemon
removes a fainted wild Pokemon, whether `runmolang` and `start_battle` behave as EXP-078 assumes, collision of
partial blocks, a sprint player outrunning a one-second keeper pass), co-op (members_max 1), and fights' balance.
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
            if len(toks) > 2:
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
    for s in out:
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
        for ln in pack.lines(FN + "slot/s%d/arrive" % s.g):
            m = re.search(r"tp @s (\S+) (\S+) (\S+)", ln)
            if m:
                s.arrive = tuple(float(v) for v in m.groups())
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


def room_rec(s, r):
    for x in (s.rec or {}).get("rooms", []):
        if x["id"] == r:
            return x
    return {"id": r, "kind": "?", "params": {}}


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
            if head2:
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


def room_of_x(s, x):
    for r in s.rooms:
        b = s.boxes.get(r)
        if b and b[0] <= x <= b[3]:
            return r
    return None


def parse_falls(pack, s, r):
    """The room tick's catch boxes (lines that run `fall`), the fall's teleports by dg.ck value, and the ledge boxes
    that set dg.ck."""
    catch, tps, sets = [], {}, []
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
    return catch, tps, sets


def walk_audit(pack, s, shell, start, F):
    """Entry to exit with every gate open; from every reached cell back to the back rip in every gate state; void
    falls; catch floors; the slot's box; the per-room walk for the clock. Returns (graph, per-room walk, path)."""
    # the gates: run each room's clear in order on the start world; a cell a clear changes from solid to passable is
    # that room's gate cell. A clear that shuts a passable cell, or opens one another clear also touches, is reported.
    w = start.copy()
    sim = Sim(pack, w)
    entrant(sim, s, 1)
    sim.player.pos = (-1000.0, -1000.0, -1000.0)
    gate = np.full(w.shape, -1, np.int16)
    gated_rooms = []
    for i, r in enumerate(s.rooms):
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
        c, tps, sets = parse_falls(pack, s, r)
        ck_any |= set(sets)
        if c:
            falls[r] = (c, tps)
    need, rev, voids = None, None, None
    # pass 1: reach (catch nodes are not expanded), so the catch set can be restricted to reached nodes after
    need, rev, voids = minimax_forward(gr, [a], set())
    for r, (cboxes, tps) in falls.items():
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
        F.add("VOID", s, room_of_x(s, gr.xyz(u)[0]), gr.xyz(u), "a step from here falls out of the shell into the void")
    # the exit and the back rip
    far, back = s.rips.get("far"), s.rips.get("back")
    reached = list(need)
    exits = zone_nodes(gr, reached, far, ENTITY_REACH) if far else set()
    backs = zone_nodes(gr, reached, back, ENTITY_REACH) if back else set()
    if not exits:
        xmax = max(gr.xyz(n)[0] for n in reached)
        F.add("WALK", s, room_of_x(s, xmax), None, "the far rip cannot be reached with every gate open "
              "(the walk ends at x %d)" % xmax)
    if not backs:
        F.add("TRAP", s, s.rooms[0], s.arrive, "the back rip cannot be reached from the arrival")
    big = 1 << 20
    backv0 = minimax_back(rev, {n: -1 for n in backs}, None)
    # a catch node returns when every checkpoint its fall can send it to returns (the value is their worst)
    dests, stale = {}, {}
    for r, (cb, tps) in falls.items():
        dn = []
        for k, p in sorted(tps.items()):
            i = gr.idx(*Sim.blk(p))
            if not gr.N[i]:
                F.add("PARKOUR", s, r, p, "checkpoint dg.ck %d teleports to a place a player cannot stand" % k)
            dn.append(i)
        dests[r] = dn
        if not tps:
            F.add("PARKOUR", s, r, None, "its fall teleports nowhere")
        missing = sorted(ck_any - set(tps))
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
            by_room[room_of_x(s, gr.xyz(n)[0])].append((n, nv, bv))
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
            F.add("BOUNDS", s, room_of_x(s, gr.xyz(out[0])[0]), gr.xyz(out[0]),
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
            r = room_of_x(s, gr.xyz(path[i])[0])
            x0, x1 = gr.xyz(path[i - 1])[0], gr.xyz(path[i])[0]
            walks[r] += abs(x1 - x0) + abs(gr.xyz(path[i])[2] - gr.xyz(path[i - 1])[2]) or 1
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
        return room_of_x(self.s, int(math.floor(p[0])))

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
                    if b[0] < gr.xyz(n)[0] < b[3] and any(hits_box((gr.xyz(n)[0] + 0.5, gr.xyz(n)[1], gr.xyz(n)[2] + 0.5), bx)
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
        stand = [n for n in need if b[0] < gr.xyz(n)[0] < b[3]]
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
        base = ss[0]
        bw = writes(base)
        for s in ss[1:]:
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


def clock_audit(pack, doc, s, walks, F):
    """The record's clocks against tools/dungeon_clock.required() fed with THIS audit's walks, and the generated
    threshold's clock against the record."""
    sys.path.insert(0, str(ROOT / "tools"))
    import dungeon_clock as DC
    rooms = []
    for r in s.rooms:
        rec = room_rec(s, r)
        rooms.append({"id": r, "kind": rec.get("kind"), "walk": walks.get(r, 0), "gate": rec.get("gate", "cleared" if
                      rec.get("kind") == "boss_arena" else "open"), "params": rec.get("params") or {}})
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
        req = sum(DC.required(doc, s.rec, b["band"], rooms).values())
        mine = int(math.ceil(req * slack / 60.0)) * 60
        if have < mine:
            F.add("CLOCK", s, None, None, "band %s: the record's clock %d s is under %d s, the clock formula fed with this "
                  "audit's measured walk of %d blocks (tools/dungeon_clock.py measured %s)"
                  % (k, have, mine, sum(walks.values()), their_total))
        if start and start.get(b["band"]) is not None and start[b["band"]] != have * 80:
            F.add("CLOCK", s, None, None, "band %s: the threshold sets dg.clock %d, the record's %d s is %d"
                  % (k, start[b["band"]], have, have * 80))
    return sum(walks.values()), their_total


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
        for s in ss:
            first = s is ss[0]
            if not first and not all_slots:
                continue
            say = progress or (lambda m: None)
            say("%s s%d: shell" % (s.dungeon, s.g))
            shell = slot_world(pack, s)
            start, _ = start_world(pack, s, shell)
            if first:
                say("%s s%d: walk" % (s.dungeon, s.g))
                gr, walks, extra = walk_audit(pack, s, shell, start, F)
                reset_audit(pack, s, start, F)
                if extra:
                    path, total, catch, need = extra
                    puzzle_audit(pack, s, start, gr, need, F)
                    vault_audit(pack, doc, s, start, gr, need, F)
                    if walks:
                        info[d["id"]] = clock_audit(pack, doc, s, walks, F)
                    first_gr = (gr, path, catch)
                else:
                    first_gr = None
            if first_gr is None or first_gr[1] is None:
                continue
            gr, path, catch = first_gr
            rg = gr
            if not first:
                if shell.shape != gr.world.shape:
                    F.add("SLOT", s, None, None, "its shell's extent differs from slot %d's" % ss[0].k)
                    continue
                rg = _moved_graph(gr, shell.lo)     # same flat indices: the SLOT check proves the shells are moved copies
            for band in (bands if first else bands[:1]):
                for mode in (modes if first and band == bands[0] else ("win",)):
                    say("%s s%d: run band %d %s" % (s.dungeon, s.g, band, mode))
                    Run(pack, s, start, band, caps, exempt, mode, F, rg, path, catch).go()
    return F, info


def _moved_graph(gr, lo):
    """Slot 1's walk graph, read in another slot's frame (its world's corner)."""
    w = World.__new__(World)
    w.lo = tuple(lo)
    w.shape, w.g, w.pal, w.idx, w.writes_outside = gr.world.shape, gr.world.g, gr.world.pal, gr.world.idx, []
    g2 = Graph.__new__(Graph)
    g2.__dict__.update(gr.__dict__)
    g2.world = w
    return g2


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
    ap.add_argument("--quick", action="store_true", help="slot 1 of each dungeon, band 1, every mode")
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
