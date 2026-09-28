"""SOUTHERN_RIFT_MEGA.md 13 / 13.1, the owner's redesign of the gulch: independent tests.

Written by a test author who did not build it (the builder's own suites are tests/test_gulch_mine.py,
tests/test_gate_clocks.py and tests/gulch_sim.py, which the build session updated itself). Nothing here uses the
builder's simulator or its model's checks: the functions are run on tests/mcfunction_sim.py (a vanilla interpreter
written by the test author) extended below with what the keeper needs, the built pack is replayed by this file's own
parser, and every expectation comes from the design text, the data's own words, the heightmap (tools/ground.py) and
the sculpt's lip ring (tools/rift_heightmap.py), never from the generated output.

Spec-only (always run): the Mega spawn macro and its claim; the respawn clock under kill / wait / reload / restart /
leave / camp / unload (a seeded fuzz and an exact schedule); who may write the clock; the drop roll inert without a
farm and, on a synthetic farm den, only for the victor, owner-only, at the tier's chance, once per Mega; the 2-stone
price at the Cutters and in the recipe raiser (synthetic jars); no free stone anywhere; the faces warded every tick
beyond reach and never rewritten; the cove town's count, footprints, streets, zone and Victory Road.

With the heightmap (COBBLERS_SOURCE_ROOT; skipped NOT_EXECUTED without it, marked slow): the sculpt's gap is the
wall's band; the wall reaches the crag tops measured here; nobody walks from the plateau into the gulch, only to the
grille; the ward holds the plug and grille beyond a survival player's reach; every cove doorway is walked to from the
gate's arrival on the replayed world by this file's own walker; house floors sit on tools/ground.py's ground; no
spawn-condition block is written; tools/gulch_mine_audit.py catches nine planted faults and passes the clean pack.

Not covered (needs a running server, SOUTHERN_RIFT_MEGA.md 13.1 "Proofs this adds"): that the macro spawns a Mega after
a plain restart in game (EXP-046 is the evidence the simulator encodes); that battle_fainted fires the MoLang callback
and `pokemon.id` renders as the text megas/pid builds; that an item entity's Owner keeps other players off it; that
Mining Fatigue IV stops a real pickaxe; the world's own trees and foliage in the walk (the replay knows only the
heightmap and the pack); Fight or Flight's aggression.
"""
from __future__ import annotations

import copy
import itertools
import json
import math
import os
import random
import re
import shutil
import sys
import types
import uuid
import zipfile
from collections import deque
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import gulch_mine as GM          # noqa: E402  (the generator under test: only its file-writing functions are called)
import mcfunction_sim as MS      # noqa: E402

SPEC = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))
NS_F = "cobblers:gulch_mine/"
SQUARE = (4300.5, 89.0, 4850.5)       # the town square: inside driver.approach, 145 from either Mega's anchor
FAR = (3000.5, 80.0, 3000.5)          # outside every approach box
GT0 = 10_000_000
REACH = 4.5 + 1.0                     # ServerPlayerGameMode (1.20.5+) accepts a break within block_interaction_range
                                      # (4.5) + 1 of the eyes; the vanilla client stops at 4.5. The stricter is used
EYE, HALF_W, HEIGHT = 1.62, 0.3, 1.8


# ============================================================================================ the interpreter, extended

def _uuid_text(ints):
    """Java's UUID from an NBT int array (UUIDUtil.uuidFromIntArray), as UUID.toString() writes it."""
    v = 0
    for i in ints:
        v = (v << 32) | (i & 0xFFFFFFFF)
    return str(uuid.UUID(int=v))


def _ptoks(path):
    out, i = [], 0
    while i < len(path):
        c = path[i]
        if c == ".":
            i += 1
        elif c == "[":
            depth, j, q = 0, i, False
            while True:
                ch = path[j]
                if ch == '"':
                    q = not q
                elif not q and ch in "[{":
                    depth += 1
                elif not q and ch in "]}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = path[i + 1:j]
            out.append(("all",) if inner == "" else ("filter", MS.snbt(inner)) if inner.startswith("{") else ("idx", int(inner)))
            i = j + 1
        else:
            m = re.match(r"[A-Za-z0-9_+\-]+", path[i:])
            if not m:
                raise MS.Unsupported("NBT path %r" % path)
            out.append(("key", m.group(0)))
            i += len(m.group(0))
    return out


def _walk_nbt(root, toks, create):
    cur = [root]
    for n, t in enumerate(toks):
        nxt, after = [], (toks[n + 1] if n + 1 < len(toks) else None)
        for node in cur:
            if t[0] == "key" and isinstance(node, dict):
                if t[1] not in node and create:
                    node[t[1]] = [] if after and after[0] != "key" else {}
                if t[1] in node:
                    nxt.append(node[t[1]])
            elif t[0] == "idx" and isinstance(node, list) and -len(node) <= t[1] < len(node):
                nxt.append(node[t[1]])
            elif t[0] == "filter" and isinstance(node, list):
                hit = [e for e in node if isinstance(e, dict) and MS._nbt_match(t[1], e)]
                if not hit and create:                 # vanilla's MatchElementNode creates the element it looked for
                    node.append(copy.deepcopy(t[1]))
                    hit = [node[-1]]
                nxt += hit
            elif t[0] == "all" and isinstance(node, list):
                nxt += node
        cur = nxt
    return cur


class Sim(MS.World):
    """tests/mcfunction_sim.py plus what the gulch keeper uses: objectives remove, every scoreboard operation (/= and %=
    floor, as Mth.floorDiv / positiveModulo), time query gametime, random value, dx/dy/dz volumes (an entity is in when
    its box meets [x, x+dx+1)), gamemode, `execute on <relation>`, `if data`, `return run`, NBT paths with compound
    filters (a filtered set that matches nothing appends, as vanilla), set/append/remove/get storage and entity data
    ("nothing changed" fails, so `store success` sees it), title. Entities not yet loaded after a restart are hidden
    from @e."""

    def __init__(self, fns, seed=1):
        super().__init__({NS_F + k: v for k, v in fns.items()})
        self.tags = {"load": [NS_F + "load"], "tick": [NS_F + "tick"]}
        self.rng = random.Random(seed)
        self.rolls = []
        self.titles = []
        self.hidden = {}
        self.unloaded = set()
        self._loaded = lambda x, z: (math.floor(x) // 16, math.floor(z) // 16) not in self.unloaded

    def player(self, pos, mode="survival", name=None):
        e = self.add_player(pos, name or "p%d" % (len(self.entities) + 1))
        e.mode = mode
        e.nbt["UUID"] = [self.rng.randint(-2 ** 31, 2 ** 31 - 1) for _ in range(4)]
        e.uuid = _uuid_text(e.nbt["UUID"])
        return e

    def restart(self, hide_for):
        """A server restart: the scoreboard, storage and game time persist, minecraft:load runs, and the saved Pokemon
        entities come back hide_for ticks after their chunks."""
        for e in self.entities:
            if e.alive and e.type == "cobblemon:pokemon":
                self.hidden[e.uid] = self.tick_no + hide_for
        self.run_load()

    def _visible(self, e):
        return self.hidden.get(e.uid, -1) <= self.tick_no

    # -- selectors
    def select(self, sel, ctx, single=False):
        if not sel.startswith("@"):
            return [e for e in self.entities if e.alive and sel in (getattr(e, "uuid", None), getattr(e, "name", None))]
        m = re.match(r"@([aepsr])(?:\[(.*)\])?$", sel)
        if not m:
            raise MS.Unsupported(sel)
        kind, args = m.group(1), MS._args(m.group(2) or "")
        if kind == "s":
            pool = [ctx.executor] if ctx.executor is not None and ctx.executor.alive else []
        elif kind in "ap":
            pool = [e for e in self.entities if e.alive and e.type == "minecraft:player"]
        else:
            pool = [e for e in self.entities if e.alive and self.loaded(e.pos[0], e.pos[2]) and self._visible(e)]
        origin, vol = list(ctx.pos), {}
        for k, v in args:
            if k in ("x", "y", "z"):
                origin["xyz".index(k)] = float(v)
            if k in ("dx", "dy", "dz"):
                vol[k] = float(v)
        limit, sort = (1, "nearest") if kind == "p" else (None, "arbitrary")
        for k, v in args:
            neg, val = v.startswith("!"), v.lstrip("!")
            if k == "type":
                t = val if ":" in val else "minecraft:" + val
                pool = [e for e in pool if (e.type == t) != neg]
            elif k == "tag":
                pool = [e for e in pool if (val in e.tags) != neg]
            elif k == "gamemode":
                pool = [e for e in pool if (getattr(e, "mode", "survival") == val) != neg]
            elif k == "distance":
                lo, hi = MS._range(v)
                pool = [e for e in pool if lo <= math.dist(e.pos, origin) <= hi]
            elif k == "limit":
                limit = int(v)
            elif k == "sort":
                sort = v
            elif k not in ("x", "y", "z", "dx", "dy", "dz"):
                raise MS.Unsupported("selector argument %s" % k)
        if vol:
            lo = origin
            hi = [origin[0] + vol.get("dx", 0) + 1, origin[1] + vol.get("dy", 0) + 1, origin[2] + vol.get("dz", 0) + 1]

            def meets(e):
                w, h = (HALF_W, HEIGHT) if e.type == "minecraft:player" else (0.25, 0.5)
                a = (e.pos[0] - w, e.pos[1], e.pos[2] - w)
                b = (e.pos[0] + w, e.pos[1] + h, e.pos[2] + w)
                return all(a[i] < hi[i] and b[i] > lo[i] for i in range(3))
            pool = [e for e in pool if meets(e)]
        if sort == "nearest":
            pool = sorted(pool, key=lambda e: math.dist(e.pos, origin))
        elif sort == "furthest":
            pool = sorted(pool, key=lambda e: -math.dist(e.pos, origin))
        return pool[:limit] if limit is not None else pool

    # -- scores
    def c_scoreboard(self, rest, ctx):
        t = rest.split()
        if t[0] == "objectives":
            if t[1] == "add":
                if t[2] in self.objectives:
                    raise MS.Failed("objective exists")
                self.objectives.add(t[2])
                return 1
            if t[1] == "remove":
                if t[2] not in self.objectives:
                    raise MS.Failed("no objective")
                self.objectives.discard(t[2])
                self.scores = {k: v for k, v in self.scores.items() if k[1] != t[2]}
                return 1
            raise MS.Unsupported(rest)
        op = t[1]
        if op == "get":
            return self.get_score(t[2], t[3], ctx)
        if op in ("set", "add", "remove"):
            if t[3] not in self.objectives:
                raise MS.Failed("no objective")
            h = self.holder(t[2], ctx)
            cur = self.scores.get((h, t[3]), 0)
            self.scores[(h, t[3])] = int(t[4]) if op == "set" else cur + int(t[4]) if op == "add" else cur - int(t[4])
            return self.scores[(h, t[3])]
        if op == "reset":
            h = self.holder(t[2], ctx)
            self.scores = {k: v for k, v in self.scores.items() if not (k[0] == h and (len(t) < 4 or k[1] == t[3]))}
            return 1
        if op == "operation":
            a, ao, o, b, bo = t[2:7]
            if ao not in self.objectives or bo not in self.objectives:
                raise MS.Failed("no objective")
            ha, hb = self.holder(a, ctx), self.holder(b, ctx)
            x, y = self.scores.get((ha, ao), 0), self.scores.get((hb, bo), 0)
            if o in ("/=", "%=") and y == 0:
                raise MS.Failed("divide by zero")
            r = {"=": lambda: y, "+=": lambda: x + y, "-=": lambda: x - y, "*=": lambda: x * y, "/=": lambda: x // y,
                 "%=": lambda: x % y, "<": lambda: min(x, y), ">": lambda: max(x, y), "><": lambda: y}[o]()
            self.scores[(ha, ao)] = int(r)
            if o == "><":
                self.scores[(hb, bo)] = x
            return int(r)
        raise MS.Unsupported(rest)

    def c_time(self, rest, ctx):
        if rest.strip() != "query gametime":
            raise MS.Unsupported(rest)
        return GT0 + self.tick_no

    def c_random(self, rest, ctx):
        m = re.fullmatch(r"value (-?\d+)\.\.(-?\d+)", rest.strip())
        if not m:
            raise MS.Unsupported(rest)
        lo, hi = int(m.group(1)), int(m.group(2))
        v = self.rolls.pop(0) if self.rolls else self.rng.randint(lo, hi)
        assert lo <= v <= hi, (v, lo, hi)
        return v

    def c_title(self, rest, ctx):
        sel, _kind, text = rest.split(" ", 2)
        for e in self.select(sel, ctx):
            self.titles.append((e, json.loads(text)["text"]))
        return 1

    def c_return(self, rest, ctx):
        if rest.startswith("run "):
            raise MS.Return(self.command(rest[4:], ctx) or 0)
        raise MS.Return(int(rest))

    def c_spawnpokemonat(self, rest, ctx, from_macro):
        r = super().c_spawnpokemonat(rest, ctx, from_macro)
        if r:
            e = self.entities[-1]
            e.props = rest.split()[4:]
            e.nbt["Pokemon"]["UUID"] = [self.rng.randint(-2 ** 31, 2 ** 31 - 1) for _ in range(4)]
        return r

    # -- data
    def storage_get(self, sid, path, record=True):
        got = _walk_nbt(self.storage.setdefault(sid, {}), _ptoks(path), False)
        if not got:
            raise MS.Failed("no data at %s" % path)
        return got[0]

    def storage_set(self, sid, path, value):
        toks = _ptoks(path)
        for p in _walk_nbt(self.storage.setdefault(sid, {}), toks[:-1], True):
            p[toks[-1][1]] = value

    def c_data(self, rest, ctx):
        t = rest.split(" ")
        if t[0] == "merge":
            return super().c_data(rest, ctx)

        def target(i):
            if t[i] == "storage":
                return self.storage.setdefault(t[i + 1], {}), i + 2
            if t[i] == "entity":
                ents = self.select(t[i + 1], ctx)
                if len(ents) != 1:
                    raise MS.Failed("one entity wanted")
                return ents[0].nbt, i + 2
            raise MS.Unsupported(rest)
        if t[0] == "get":
            root, i = target(1)
            got = _walk_nbt(root, _ptoks(t[i]), False)
            if not got:
                raise MS.Failed("no data")
            v = got[0]
            return int(math.floor(v * (float(t[i + 1]) if len(t) > i + 1 else 1.0))) if isinstance(v, (int, float)) else len(v)
        if t[0] == "remove":
            root, i = target(1)
            toks, n = _ptoks(t[i]), 0
            for p in _walk_nbt(root, toks[:-1], False):
                last = toks[-1]
                if last[0] == "key" and isinstance(p, dict) and last[1] in p:
                    del p[last[1]]
                    n += 1
                elif last[0] == "filter" and isinstance(p, list):
                    keep = [e for e in p if not (isinstance(e, dict) and MS._nbt_match(last[1], e))]
                    n += len(p) - len(keep)
                    p[:] = keep
            if not n:
                raise MS.Failed("nothing removed")
            return n
        if t[0] == "modify":
            root, i = target(1)
            toks, op, how = _ptoks(t[i]), t[i + 1], t[i + 2]
            if how == "value":
                value = MS.snbt(" ".join(t[i + 3:]))
            elif how == "from":
                src, j = target(i + 3)
                got = _walk_nbt(src, _ptoks(t[j]), False) if len(t) > j else [src]
                if not got:
                    raise MS.Failed("no source")
                value = copy.deepcopy(got[0])
            else:
                raise MS.Unsupported(rest)
            n = 0
            for p in _walk_nbt(root, toks[:-1], True):
                k = toks[-1][1]
                if op == "set":
                    if not isinstance(p, dict) or toks[-1][0] != "key":
                        raise MS.Unsupported(rest)
                    if k not in p or p[k] != value:
                        p[k] = copy.deepcopy(value)
                        n += 1
                elif op == "append":
                    p.setdefault(k, []).append(copy.deepcopy(value))
                    n += 1
                else:
                    raise MS.Unsupported(rest)
            if not n:
                raise MS.Failed("nothing changed")
            return n
        raise MS.Unsupported(rest)

    # -- execute
    def _execute(self, toks, i, ctx, stores):
        while i < len(toks):
            t = toks[i]
            if t == "run":
                try:
                    r, ok = self.command(" ".join(toks[i + 1:]), ctx), True
                except MS.Failed:
                    r, ok = 0, False
                self._store(stores, ctx, r, ok)
                return r
            if t in ("as", "at"):
                total = 0
                for e in self.select(toks[i + 1], ctx):
                    c = ctx.but(executor=e) if t == "as" else ctx.but(pos=tuple(e.pos), rot=tuple(e.rot))
                    total += self._execute(toks, i + 2, c, stores) or 0
                return total
            if t == "positioned":
                ctx, i = ctx.but(pos=self.coords(toks[i + 1:i + 4], ctx)), i + 4
                continue
            if t == "on":
                e = getattr(ctx.executor, toks[i + 1], None) if ctx.executor is not None else None
                if e is None or not e.alive:
                    return 0
                ctx, i = ctx.but(executor=e), i + 2
                continue
            if t == "store":
                what, kind = toks[i + 1], toks[i + 2]
                if kind == "score":
                    stores, i = stores + [(what, "score", toks[i + 3], toks[i + 4])], i + 5
                elif kind == "storage":
                    stores, i = stores + [(what, "storage", toks[i + 3], toks[i + 4], toks[i + 5], float(toks[i + 6]))], i + 7
                else:
                    raise MS.Unsupported("store %s" % kind)
                continue
            if t in ("if", "unless"):
                want, kind = t == "if", toks[i + 1]
                if kind == "score":
                    try:
                        a = self.get_score(toks[i + 2], toks[i + 3], ctx)
                        if toks[i + 4] == "matches":
                            lo, hi = MS._range(toks[i + 5])
                            ok, n = lo <= a <= hi, 6
                        else:
                            b = self.get_score(toks[i + 5], toks[i + 6], ctx)
                            ok, n = {"<": a < b, "<=": a <= b, "=": a == b, ">": a > b, ">=": a >= b}[toks[i + 4]], 7
                    except MS.Failed:
                        ok, n = False, (6 if toks[i + 4] == "matches" else 7)
                    count = int(ok)
                elif kind == "entity":
                    count, n = len(self.select(toks[i + 2], ctx)), 3
                elif kind == "loaded":
                    x, _y, z = self.coords(toks[i + 2:i + 5], ctx)
                    count, n = int(self.loaded(x, z)), 5
                elif kind == "data":
                    if toks[i + 2] == "storage":
                        root = self.storage.get(toks[i + 3], {})
                    else:
                        ents = self.select(toks[i + 3], ctx)
                        root = ents[0].nbt if len(ents) == 1 else None
                    count = 0 if root is None else len(_walk_nbt(root, _ptoks(toks[i + 4]), False))
                    n = 5
                else:
                    raise MS.Unsupported("execute if %s" % kind)
                passed = (count > 0) == want
                if i + n >= len(toks):
                    r = (count if kind == "entity" and want else 1) if passed else 0
                    self._store(stores, ctx, r, passed)
                    return r
                if not passed:
                    return 0
                i += n
                continue
            raise MS.Unsupported("execute %s" % t)
        return 0


# ============================================================================================ spec helpers

def model_of(spec, anchor_y=47):
    """What keeper_files reads: the spec, each mine slot's anchor at a floor y (the y does not matter to the logic)."""
    spec = copy.deepcopy(spec)
    for s in spec["megas"]["slots"]:
        s["_anchor"] = [s["anchor"][0], anchor_y, s["anchor"][1]]
    return types.SimpleNamespace(spec=spec)


def farm_spec(respawn=None):
    """A synthetic farm (none is in the data: SOUTHERN_RIFT_MEGA.md 13.1 holds them), in the shape tools/gulch_mine.py
    reads: an outer den and a deeper den, far from the mine, with their own approach box."""
    spec = copy.deepcopy(SPEC)
    dens = [{"id": "den_outer", "species": "aggron", "aspect": "mega_evolution=mega", "level": 60,
             "anchor": [5050, 100, 5050], "leash": 24},
            {"id": "den_deep", "species": "tyranitar", "aspect": "mega_evolution=mega", "level": 67, "tier": "deeper",
             "anchor": [5090, 100, 5090], "leash": 24}]
    if respawn:
        for d in dens:
            d["respawn_ticks"] = respawn
    spec["farms"] = [{"id": "testfarm", "name": "the test farm", "tier": "outer",
                      "zone": {"polygon": [[5000, 5000], [5120, 5000], [5120, 5120], [5000, 5120]],
                               "turn_back": [4990.5, 100, 5060.5, 90]},
                      "approach": [4980, 40, 4980, 5140, 160, 5140], "dens": dens}]
    return spec


_ZB = {}


def zboxes(spec):
    key = json.dumps(spec["zone"]["polygon"])
    if key not in _ZB:
        _ZB[key] = GM.zone_boxes(spec["zone"]["polygon"])
    return _ZB[key]


def all_functions(spec):
    m = model_of(spec)
    fns = dict(GM.gate_files(m, zboxes(spec))[1])
    fns.update(GM.cutter_files(m))
    fns.update(GM.keeper_files(m))
    return fns


def executable(lines):
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def calls_of(lines):
    return {m.group(1) for l in executable(lines) for m in re.finditer(r"function cobblers:gulch_mine/(\S+)", l)}


def reachable(fns, roots):
    seen, todo = set(), list(roots)
    while todo:
        f = todo.pop()
        if f in seen or f not in fns:
            continue
        seen.add(f)
        todo += calls_of(fns[f])
    return seen


def den_megas(w, den):
    return [e for e in w.entities if e.alive and e.type == "cobblemon:pokemon" and "%s.%s" % (SPEC["megas"]["tag"], den) in e.tags]


def poly_in(poly, px, pz):
    c = False
    for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1]):
        if (z0 > pz) != (z1 > pz) and px < x0 + (pz - z0) * (x1 - x0) / (z1 - z0):
            c = not c
    return c


def half_up(v):
    return int(math.floor(v + 0.5))


def road_cols(rd):
    """data geometry.road, columns only: ceil(4 L) + 1 samples a segment, the (2 half + 1)^2 round each rounded point."""
    out = set()
    for a, b in zip(rd["path"], rd["path"][1:]):
        n = int(math.ceil(4 * math.hypot(b[0] - a[0], b[1] - a[1]))) + 1
        for s in range(n):
            f = s / (n - 1) if n > 1 else 0.0
            cx, cz = half_up(a[0] + (b[0] - a[0]) * f), half_up(a[1] + (b[1] - a[1]) * f)
            out |= {(cx + dx, cz + dz) for dx in range(-rd["half"], rd["half"] + 1) for dz in range(-rd["half"], rd["half"] + 1)}
    return out


def band_claims(band):
    """data geometry.band: {(x, z): j}, the least talus drop max(0, -d - core) wins, the first among equals."""
    w, out, drop = band["wall"], {}, {}
    for j, x, z, nx, nz in band["points"]:
        for d in range(-w["spread_out"], w["spread_in"] + 1):
            dr = max(0, -d - w["core"])
            cx, cz = half_up(x + nx * d), half_up(z + nz * d)
            for a, b in itertools.product((-1, 0, 1), repeat=2):
                c = (cx + a, cz + b)
                if c not in out or dr < drop[c]:
                    out[c], drop[c] = j, dr
    return out


def rect_cols(r):
    return {(x, z) for x in range(r[0], r[2] + 1) for z in range(r[1], r[3] + 1)}


OUT_DIR = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def door_col(b):
    """data geometry.cove: the middle of the door side, halved and rounded down."""
    x0, z0, x1, z1 = b["rect"]
    return {"north": ((x0 + x1) // 2, z0), "south": ((x0 + x1) // 2, z1), "west": (x0, (z0 + z1) // 2),
            "east": (x1, (z0 + z1) // 2)}[b["door"]]


def footprint(b):
    """A cove record's columns: its rect, and a house's steps (3 across the door's line at 1, 2 and 3 out)."""
    cols = rect_cols(b["rect"])
    if "door" in b:
        (dx, dz), (x, z) = OUT_DIR[b["door"]], door_col(b)
        cols |= {(x + dx * k + (s if dz else 0), z + dz * k + (s if dx else 0)) for k in (1, 2, 3) for s in (-1, 0, 1)}
    return cols


def ward_volumes(lines):
    """The tick's Mining Fatigue IV volumes: [(x0, y0, z0, x1, y1, z1)] of the selector's box, [x, x + dx + 1)."""
    out = []
    for l in executable(lines):
        m = re.fullmatch(r"execute as @a\[x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+),gamemode=!creative,"
                         r"gamemode=!spectator\] run effect give @s minecraft:mining_fatigue (\d+) 3 true", l)
        if m:
            x, y, z, dx, dy, dz = (int(v) for v in m.groups()[:6])
            out.append((x, y, z, x + dx + 1, y + dy + 1, z + dz + 1))
    return out


def least_eye_distance_outside(vol, box):
    """The least distance from the eyes of a player the volume does not select to the box [x0, x1) (both as reals):
    unselected means the player's box (0.6 wide, 1.8 high) misses the volume on at least one side, the other two
    coordinates free, so the six half-spaces give it exactly."""
    vx0, vy0, vz0, vx1, vy1, vz1 = vol
    bx0, by0, bz0, bx1, by1, bz1 = box
    return min(bx0 - (vx0 - HALF_W), (vx1 + HALF_W) - bx1, bz0 - (vz0 - HALF_W), (vz1 + HALF_W) - bz1,
               by0 - (vy0 - HEIGHT + EYE), (vy1 + EYE) - by1)


# ============================================================================================ the Megas' spawn

# Without it a plain `spawnpokemonat` line could come back into the pack (anywhere, for any den, farm dens included)
# and spawn nothing after a restart until a /reload (EXP-046): every spawnpokemonat in every generated function, with
# and without a farm, is the one `$` macro line of megas/spawn_at, and every den's spawn calls it.
@pytest.mark.parametrize("which", ["data", "with a farm"])
def test_every_spawnpokemonat_is_the_macro_line_and_every_den_spawns_through_it(which):
    spec = SPEC if which == "data" else farm_spec()
    fns = all_functions(spec)
    lines = [(n, l.strip()) for n, b in fns.items() for l in b if "spawnpokemonat" in l and not l.strip().startswith("#")]
    assert lines == [("megas/spawn_at", "$spawnpokemonat $(x) $(y) $(z) $(species) $(aspect) uncatchable level=$(level)")]
    dens = [s["id"] for s in spec["megas"]["slots"]] + [d["id"] for f in spec.get("farms", []) for d in f["dens"]]
    assert len(dens) == (2 if which == "data" else 4)
    for d in dens:
        assert calls_of(fns["megas/spawn_%s" % d]) == {"megas/spawn_at", "megas/bind_%s" % d}, d


# Without it a Mega could be spawned and left unclaimed (untagged, so the keeper counts none and spawns another; not
# persistent, so it despawns; not exempt from the blackout's claim): run on the interpreter, each den's spawn function
# leaves exactly one new Pokemon, of its species, Mega aspect, uncatchable, at its level, tagged and persistent, before
# the function returns. The same function with the macro call replaced by a plain line spawns nothing (the
# interpreter's EXP-046 rule), so the check is not blind.
@pytest.mark.parametrize("which", ["data", "with a farm"])
def test_each_den_spawn_leaves_one_claimed_mega_in_the_same_function(which):
    spec = SPEC if which == "data" else farm_spec()
    fns = GM.keeper_files(model_of(spec))
    dens = [("mine", s) for s in spec["megas"]["slots"]] + [(f["id"], d) for f in spec.get("farms", []) for d in f["dens"]]
    blackout = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))
    assert blackout["claims"]["exempt_tag"] == spec["megas"]["tag"]
    for site, d in dens:
        w = Sim(fns)
        w.run_load()
        w.function(NS_F + "megas/spawn_%s" % d["id"], w.server())
        (e,) = [x for x in w.entities if x.type == "cobblemon:pokemon"]
        assert e.nbt["Pokemon"]["Species"] == d["species"] and e.nbt["Pokemon"]["Level"] == d["level"]
        assert e.props == [d["aspect"], "uncatchable", "level=%d" % d["level"]] and e.nbt.get("Uncatchable") == 1
        want = {spec["megas"]["tag"], "%s.%s" % (spec["megas"]["tag"], d["id"])}
        if site != "mine":
            want.add(spec["megas"]["farm_tag"])
        assert e.tags == want and e.nbt.get("PersistenceRequired") in (1, True), (e.tags, e.nbt)
        plain = dict(fns)
        plain["megas/spawn_%s" % d["id"]] = [re.sub(r"^function cobblers:gulch_mine/megas/spawn_at \{x:(-?\d+),y:(-?\d+),"
                                                    r"z:(-?\d+),species:\"(\w+)\",aspect:\"(\S+?)\",level:(\d+)\}$",
                                                    r"spawnpokemonat \1 \2 \3 \4 \5 uncatchable level=\6", l)
                                             for l in fns["megas/spawn_%s" % d["id"]]]
        w2 = Sim(plain)
        w2.run_load()
        w2.function(NS_F + "megas/spawn_%s" % d["id"], w2.server())
        assert not [x for x in w2.entities if x.type == "cobblemon:pokemon"] and w2.logged("inert_spawn")


# ============================================================================================ the respawn clock

def _check_spawns(w, removed, resp, seen):
    """Every Mega spawn since the last look came at least resp after its den's Mega was removed; never two alive."""
    for (tick, kind, e) in w.log[seen[0]:]:
        if kind != "spawn":
            continue
        den = [t.split(".")[-1] for t in e.tags if t.count(".") == 2 and not t.endswith(".farm")]
        assert len(den) == 1, e.tags
        if den[0] in removed:
            assert tick - removed[den[0]] >= resp, ("back early", den[0], tick, removed[den[0]])
    seen[0] = len(w.log)
    for s in SPEC["megas"]["slots"]:
        assert len(den_megas(w, s["id"])) <= 1, ("two alive", s["id"])


# Without it the farm's rate limit has a hole: some sequence of what players (and the server) can do -- kill a Mega,
# wait, /reload, restart (entities back late), leave the approach box, come back, camp by the anchor, let the chunk
# unload -- brings a Mega back less than respawn_ticks after it was removed, or leaves two alive, or never brings it
# back once everyone steps away. A seeded random walk over those actions, on the real keeper (respawn_ticks cut to
# 1200 so it runs fast; the data's own value is checked below).
@pytest.mark.parametrize("seed", [3, 17, 2026])
def test_no_sequence_of_player_actions_brings_a_mega_back_early_and_it_always_comes_back(seed):
    spec = copy.deepcopy(SPEC)
    resp = spec["megas"]["respawn_ticks"] = 1200
    w = Sim(GM.keeper_files(model_of(spec)), seed)
    w.run_load()
    me = w.player(SQUARE)
    rng = random.Random(seed)
    removed, seen = {}, [0]
    w.tick(400)
    assert all(len(den_megas(w, s["id"])) == 1 for s in spec["megas"]["slots"])
    seen[0] = len(w.log)
    anchors ={s["id"]: (s["anchor"][0] + 0.5, 47.0, s["anchor"][1] + 0.5) for s in spec["megas"]["slots"]}
    chunks = {(a[0] // 16, a[2] // 16) for a in anchors.values()}
    for _ in range(150):
        act = rng.choice(["wait", "wait", "kill", "kill", "reload", "restart", "leave", "home", "camp", "unload", "load"])
        if act == "wait":
            n = rng.randint(1, 700)
        else:
            n = rng.randint(0, 60)
        if act == "kill":
            den = rng.choice(list(anchors))
            for e in den_megas(w, den):
                e.alive = False
                removed[den] = w.tick_no
        elif act == "reload":
            w.run_load()
        elif act == "restart":
            w.restart(rng.randint(0, 350))
        elif act == "leave":
            me.pos = list(FAR)
        elif act == "home":
            me.pos = list(SQUARE)
        elif act == "camp":
            a = anchors[rng.choice(list(anchors))]
            me.pos = [a[0] + rng.uniform(-20, 20), a[1], a[2] + rng.uniform(-15, 15)]
        elif act == "unload":
            w.unloaded |= chunks
        elif act == "load":
            w.unloaded.clear()
        for _t in range(n):
            w.tick()
            _check_spawns(w, removed, resp, seen)
    me.pos, w.unloaded = list(SQUARE), set()
    for _t in range(resp + 1200):
        w.tick()
        _check_spawns(w, removed, resp, seen)
    assert all(len(den_megas(w, s["id"])) == 1 for s in spec["megas"]["slots"]), "a Mega never came back"
    respawns = [x for x in w.log if x[1] == "spawn" and x[0] > 400]
    assert len(respawns) >= 3 and w.tick_no > 8 * resp, (len(respawns), w.tick_no)     # not a vacuous walk


# Without it the respawn clock is not the data's 15 minutes, or a /reload or a restart moves it (the owner's rule,
# SOUTHERN_RIFT_MEGA.md 13: "no repeatable action may reset it"): with the data's respawn_ticks, a Mega killed with a
# player in the square comes back within three keeper passes after respawn_ticks, and a run with a /reload every 1000
# ticks and a restart every 3000 (entities back 150 ticks late) brings it back on the very same tick.
def test_the_clock_is_the_datas_and_neither_reload_nor_restart_moves_it():
    resp, every = SPEC["megas"]["respawn_ticks"], SPEC["driver"]["every_ticks"]
    assert resp == 15 * 60 * 20, "SOUTHERN_RIFT_MEGA.md 13.1: the mine's two wait 15 minutes"
    fns = GM.keeper_files(model_of(SPEC))

    def run(disturb):
        w = Sim(fns)
        w.run_load()
        w.player(SQUARE)
        w.tick(500)
        (e,) = den_megas(w, "steelix")
        e.alive, t0, n0 = False, w.tick_no, len(w.log)
        for k in range(1, resp + 6 * every):
            if disturb and k % 1000 == 0:
                w.run_load()
            if disturb and k % 3000 == 0:
                w.restart(150)
            w.tick()
            if [x for x in w.log[n0:] if x[1] == "spawn"]:
                break
        spawns = [x[0] for x in w.log[n0:] if x[1] == "spawn" and "cobblers.gm.steelix" in x[2].tags]
        assert len(spawns) == 1, spawns
        return spawns[0] - t0
    quiet, busy = run(False), run(True)
    assert resp <= quiet <= resp + 3 * every, quiet
    assert busy == quiet, (busy, quiet)


# Without it something other than the keeper could move a den's respawn clock (a player-triggered advancement's
# function, the gate, the Cutters, the tick, a drop roll), or load could reset it on every restart, or the objective
# could be removed or a holder reset (all clocks back to "never set"). Every command in every generated function that
# can write gm.gone is listed and checked: load only sets an unset clock; only megas/gone_<den> starts one, and only
# megas/keep_<den> calls it; only megas/spawn_<den>, and the keeper on seeing its Mega, clear one; and nothing an
# advancement reward reaches can get to the keeper at all.
@pytest.mark.parametrize("which", ["data", "with a farm"])
def test_only_the_keeper_moves_a_respawn_clock(which):
    spec = SPEC if which == "data" else farm_spec()
    fns = all_functions(spec)
    writes = []
    for name, body in fns.items():
        for l in executable(body):
            l = l.lstrip("$")
            if re.search(r"scoreboard objectives remove gm\.gone\b|scoreboard players reset \S+\s*$", l):
                writes.append((name, "reset", l))
            elif re.search(r"scoreboard players reset \S+ gm\.gone\b", l):
                writes.append((name, "reset", l))
            elif re.search(r"scoreboard players (set|add|remove) \S+ gm\.gone\b|scoreboard players operation \S+ gm\.gone\b"
                           r"|store (result|success) score \S+ gm\.gone\b|operation \S+ \S+ >< \S+ gm\.gone\b", l):
                writes.append((name, "write", l))
    assert writes, "no clock is written at all: the check is blind"
    for name, kind, l in writes:
        assert kind != "reset", (name, l)
        den = name.rsplit("_", 1)[-1] if "/" in name else None
        if name == "load":
            assert re.fullmatch(r"execute unless score #(\w+) gm\.gone matches -2147483648\.\. run scoreboard players set "
                                r"#\1 gm\.gone 0", l), l
        elif name.startswith("megas/gone_"):
            assert l == "scoreboard players operation #%s gm.gone = #now gm.t" % name[len("megas/gone_"):], l
        elif name.startswith("megas/spawn_"):
            assert l == "scoreboard players set #%s gm.gone -1" % name[len("megas/spawn_"):], l
        elif name.startswith("megas/keep_"):
            d = name[len("megas/keep_"):]
            assert l == "execute if score #n gm.t matches 1.. run scoreboard players set #%s gm.gone -1" % d, l
        else:
            pytest.fail("%s writes a respawn clock: %s (den %s)" % (name, l, den))
    callers = {}
    for name, body in fns.items():
        for c in calls_of(body):
            callers.setdefault(c, set()).add(name)
    for name in fns:
        for pre, ok in (("megas/gone_", "megas/keep_"), ("megas/spawn_", "megas/keep_"), ("megas/keep_", "drive_")):
            if name.startswith(pre) and name != "megas/spawn_at":
                assert callers.get(name) and all(c.startswith(ok) for c in callers[name]), (name, callers.get(name))
    files, _ = GM.gate_files(model_of(spec), zboxes(spec))
    rewards = {a["rewards"]["function"].split("/", 1)[1] for a in files.values()}
    assert rewards and not [f for f in reachable(fns, rewards) if f.startswith(("megas/", "drive", "drops/"))]
    assert reachable(fns, ["tick"]) >= {"drive", "drive_mine"} and "megas/keep_steelix" in reachable(fns, ["tick"])


# ============================================================================================ the drop roll

DROP_FNS = ("drops/", "megas/pid", "megas/watch", "megas/hit_")


# Without it the drop machinery is live before any farm exists (SOUTHERN_RIFT_MEGA.md 13.1: "inert until a farm den
# exists in the data"), or missing once one does: with the data as it is, no drop function (roll, slain, hitter, give,
# fainted, hit, watch, pid) and no battle_fainted callback is generated, the Cutting Floor's Megas are not farm-tagged,
# and on the interpreter a player hurting and killing a Mega summons no item and writes no storage; with a synthetic
# farm den, all of them and the callback are generated (their behaviour is the tests below).
def test_the_drop_roll_is_inert_without_a_farm_den():
    assert not SPEC.get("farms"), "a farm is in the data now: this test's premise is gone"
    fns = GM.keeper_files(model_of(SPEC))
    assert not [n for n in fns if n.startswith(DROP_FNS)], [n for n in fns if n.startswith(DROP_FNS)]
    assert GM.callback_files(SPEC) == {}
    for s in SPEC["megas"]["slots"]:
        assert SPEC["megas"]["farm_tag"] not in " ".join(fns["megas/bind_%s" % s["id"]])
    w = Sim(fns)
    w.run_load()
    p = w.player(SQUARE)
    w.tick(400)
    (e,) = den_megas(w, "steelix")
    e.attacker = p
    w.tick(5)
    e.alive = False
    w.tick(400)
    assert not [x for x in w.entities if x.type == "minecraft:item"] and not w.storage.get("cobblers:gulch_mine")
    farm = farm_spec()
    ffns = GM.keeper_files(model_of(farm))
    for need in ("drops/fainted", "drops/give", "megas/pid", "megas/pid_hex", "megas/pid_join", "megas/watch"):
        assert need in ffns, need
    for d in ("den_outer", "den_deep"):
        assert {"drops/roll_%s" % d, "drops/slain_%s" % d, "drops/hitter_%s" % d, "megas/hit_%s" % d} <= set(ffns), d
    (cb,) = GM.callback_files(farm).items()
    assert cb[0] == "data/cobblemon/callbacks/battle_fainted/cobblers_gulch_drops.molang"
    assert "c.pokemon.actor.is_wild" in cb[1] and "function cobblers:gulch_mine/drops/fainted {pid:" in cb[1]


# Without it a generated function calls one the build no longer writes (a function removed for having no caller, its
# callers left behind): in game the line fails whenever it runs, and a later farm Mega would find no watch. With and
# without a farm, every function any generated function calls is generated.
@pytest.mark.parametrize("which", [
    pytest.param("data", marks=pytest.mark.xfail(strict=True, reason=(
        "tools/gulch_mine.py:1366 writes `execute as @e[...,tag=cobblers.gm.farm] run function .../megas/watch` into "
        "the tick unconditionally, and tools/gulch_mine.py:1474-1477 no longer writes megas/watch without a farm den"))),
    "with a farm"])
def test_every_called_function_is_generated(which):
    spec = SPEC if which == "data" else farm_spec()
    fns = all_functions(spec)
    dangling = sorted({(n, c) for n, b in fns.items() for c in calls_of(b) if c not in fns})
    assert not dangling, dangling


def _farm_world(respawn=400):
    spec = farm_spec(respawn)
    w = Sim(GM.keeper_files(model_of(spec)), seed=5)
    w.run_load()
    a = w.player((5030.5, 100, 4995.5), name="victor")      # in the farm's approach box, over 24 from both anchors
    b = w.player((5010.5, 100, 4990.5), name="bystander")
    w.tick(300)
    return spec, w, a, b


def _items(w):
    return [e for e in w.entities if e.alive and e.type == "minecraft:item"]


# Without it the Mega's Pokemon UUID stored at its claim is not the text Cobblemon's `pokemon.id` gives (the
# callback's $(pid)), so no battle win ever matches a den: the stored text equals Java's UUID.toString() of the
# entity's Pokemon.UUID int array, negative ints included, for many random UUIDs.
def test_the_stored_pid_is_the_pokemons_uuid_as_text():
    spec, w, _a, _b = _farm_world()
    negative = 0
    for _ in range(40):
        (e,) = den_megas(w, "den_outer")
        want = _uuid_text(e.nbt["Pokemon"]["UUID"])
        negative += any(i < 0 for i in e.nbt["Pokemon"]["UUID"])
        dens = w.storage["cobblers:gulch_mine"]["dens"]
        assert [d["pid"] for d in dens if d["id"] == "den_outer"] == [want]
        e.alive = False
        w.tick(1000)
    assert negative > 10


# Without it a battle win pays the wrong player, pays everyone, pays a finished stone, pays at another rate than the
# tier's, or pays twice for one Mega: on the callback's call (the fainted Mega's UUID and the first player in the
# battle), the victor alone gets one raw mega_stone at their feet whose Owner is the victor (vanilla 1.21.1 ItemEntity:
# only the owner picks it up), exactly when the roll (1..100) is at or under the tier's percent (outer 15, deeper 30),
# and a second call for the same Mega pays nothing.
@pytest.mark.parametrize("den,pct", [("den_outer", 15), ("den_deep", 30)])
@pytest.mark.parametrize("roll", ["1", "pct", "pct+1", "100"])
def test_a_battle_win_pays_only_the_victor_owner_only_at_the_tiers_chance_once(den, pct, roll):
    spec, w, a, b = _farm_world()
    assert spec["farm_tiers"]["outer"]["drop_percent"] == 15 and spec["farm_tiers"]["deeper"]["drop_percent"] == 30
    r = {"1": 1, "pct": pct, "pct+1": pct + 1, "100": 100}[roll]
    (e,) = den_megas(w, den)
    pid = _uuid_text(e.nbt["Pokemon"]["UUID"])
    w.rolls = [r]
    w.function(NS_F + "drops/fainted", w.server(), {"pid": pid, "who": a.uuid})
    e.alive = False
    got = _items(w)
    if r <= pct:
        (it,) = got
        assert it.nbt["Item"] == {"id": "mega_showdown:mega_stone", "count": 1}, it.nbt
        assert it.nbt["Owner"] == a.nbt["UUID"] and it.pos == a.pos and it.nbt.get("PickupDelay") == 0
    else:
        assert got == []
    w.rolls = [1]
    w.function(NS_F + "drops/fainted", w.server(), {"pid": pid, "who": b.uuid})
    w.tick(300)
    assert len(_items(w)) == len(got), "a second roll for the same Mega"
    assert not [i for i in _items(w) if i.nbt.get("Owner") == b.nbt["UUID"]]


# Without it a kill outside a battle pays nobody, pays a bystander, pays a player who hurt the Mega before it was last
# seen alive (then someone else, or a fall, killed it), or pays again after a battle already paid for it: the keeper's
# first sight of it gone rolls for the last player to hurt it -- directly or through their own Pokemon -- only when that
# hit came after the Mega was last seen alive, once.
@pytest.mark.parametrize("case", ["player hit", "pokemon hit", "stale hit", "battle then kill"])
def test_a_kill_pays_only_the_player_who_hurt_it_since_it_was_last_seen_alive(case):
    spec, w, a, b = _farm_world()
    (e,) = den_megas(w, "den_outer")
    if case == "pokemon hit":
        mon = w.add(MS.Entity("cobblemon:pokemon", (5040.5, 100, 5040.5)))
        mon.owner = b
        e.attacker = mon
    else:
        e.attacker = b
    w.tick(1)
    e.attacker = None
    if case == "stale hit":
        w.tick(2 * spec["driver"]["every_ticks"] + 5)        # a keeper pass sees it alive after the hit
    if case == "battle then kill":
        w.rolls = [1]
        w.function(NS_F + "drops/fainted", w.server(), {"pid": _uuid_text(e.nbt["Pokemon"]["UUID"]), "who": a.uuid})
    e.alive = False
    w.rolls = [1, 1, 1]
    w.tick(3 * spec["driver"]["every_ticks"] + 5)
    got = _items(w)
    if case == "stale hit":
        assert got == []
    elif case == "battle then kill":
        assert [i.nbt["Owner"] for i in got] == [a.nbt["UUID"]]
    else:
        (it,) = got
        assert it.nbt["Owner"] == b.nbt["UUID"] and it.pos == b.pos


# Without it a farm den of a tier gets some other level than its tier's: data farm_tiers gives each tier a level (outer
# 60, deeper 67; SOUTHERN_RIFT_MEGA.md 13's table), and a den that names only its tier should spawn at that level.
def test_a_farm_den_without_its_own_level_spawns_at_its_tiers_level():
    spec = farm_spec()
    for d in spec["farms"][0]["dens"]:
        del d["level"]
    fns = GM.keeper_files(model_of(spec))
    for d, lvl in (("den_outer", 60), ("den_deep", 67)):
        assert ("level:%d}" % lvl) in fns["megas/spawn_%s" % d][1]


# ============================================================================================ the price

# Without it the keyed stone's price drifts from the owner's (SOUTHERN_RIFT_MEGA.md 13: "The keyed-stone recipe
# therefore takes 2 raw stones", a diamond besides), at the Cutters or at the crafting table: every one of the sixty
# offers the Cutters are summoned with asks exactly 2 raw mega_showdown:mega_stone and 1 diamond, and the recipe raiser
# reads the same count.
def test_a_keyed_stone_costs_two_raw_stones_and_a_diamond_at_the_cutters_and_the_bench():
    import mega_recipes as MR
    assert SPEC["cutters"]["offer"]["raw_count"] == 2 and MR.RAW_COUNT == 2
    place = GM.cutter_files(model_of(SPEC))["cutters_place"]
    offers = [o for l in place if l.startswith("summon minecraft:villager")
              for o in re.findall(r"\{buy:\{[^}]*\},buyB:\{[^}]*\},sell:\{[^}]*\}", l)]
    assert len(offers) == 60
    for o in offers:
        assert o.startswith('{buy:{id:"mega_showdown:mega_stone",count:2},buyB:{id:"minecraft:diamond",count:1},sell:{'), o
        assert re.search(r'sell:\{id:"[a-z_]+:[a-z_]+ite[a-z_]*",count:1\}$', o), o


# Without it the recipe raiser writes another count, drops or changes an ingredient, touches a recipe's result, or
# writes outside its build folder: run end to end on two synthetic jars (a stone definition and a 3 x 3 recipe for every
# stone the data offers or leaves out, the raw stone once in the middle, corners empty), every written recipe holds the
# raw stone exactly twice and everything else as the jar had it.
def test_the_recipe_raiser_puts_exactly_two_raw_stones_in_every_recipe(tmp_path, monkeypatch):
    import mega_recipes as MR
    stones = [s for b in SPEC["cutters"]["benches"] for s in b["stones"]] + SPEC["cutters"]["left_out"]
    jars = {"mega_showdown": "mega_showdown-fabric-test.jar", "zamega": "zamega-fabric-test.jar"}
    recipes = {}
    for ns, name in jars.items():
        with zipfile.ZipFile(tmp_path / name, "w") as z:
            for s in stones:
                sns, sid = s.split(":")
                if sns != ns:
                    continue
                r = {"type": "minecraft:crafting_shaped", "category": "misc", "pattern": [" D ", "SMI", " D "],
                     "key": {"M": {"item": "mega_showdown:mega_stone"}, "D": {"item": "minecraft:diamond"},
                             "S": {"item": "cobblemon:%s_item" % sid}, "I": {"tag": "c:ingots/iron"}},
                     "result": {"id": s, "count": 1}}
                recipes[s] = r
                z.writestr("data/%s/mega_showdown/mega/%s.json" % (ns, sid), "{}")
                z.writestr("data/%s/recipe/%s.json" % (ns, sid), json.dumps(r))
    out = tmp_path / "out"
    monkeypatch.setattr(MR, "pins", lambda: {ns: (name, None) for ns, name in jars.items()})
    monkeypatch.setattr(MR, "OUT", out)
    monkeypatch.setattr(MR, "ROOT", tmp_path)
    assert MR.main(["--jar-dir", str(tmp_path)]) == 0
    written = sorted(out.rglob("*.json"))
    assert len(written) == len(stones) == 92

    def counts(r):
        c = {}
        for row in r["pattern"]:
            for ch in row:
                if ch != " ":
                    k = r["key"][ch]
                    c[k.get("item") or k.get("tag")] = c.get(k.get("item") or k.get("tag"), 0) + 1
        return c
    for s, jar in recipes.items():
        ns, sid = s.split(":")
        got = json.loads((out / "data" / ns / "recipe" / (sid + ".json")).read_text(encoding="utf-8"))
        want = counts(jar)
        want["mega_showdown:mega_stone"] = 2
        assert counts(got) == want and got["result"] == jar["result"] and got["key"] == jar["key"], s


# Without it free raw stones come back (the owner, SOUTHERN_RIFT_MEGA.md 13: "I don't want mega stones being free";
# "the arrival floor of 4 raw stones ... is dropped"): no generated function or advancement of the gulch gives, loots
# or summons a raw stone except drops/give, which only a farm den's roll reaches; no advancement rewards loot, items or
# experience; no data file but gulch_mine.json's price and drop names the raw stone.
@pytest.mark.parametrize("which", ["data", "with a farm"])
def test_no_raw_stone_is_given_anywhere_but_a_farm_roll(which):
    spec = SPEC if which == "data" else farm_spec()
    fns = all_functions(spec)
    files, _ = GM.gate_files(model_of(spec), zboxes(spec))
    for rel, adv in files.items():
        assert set(adv["rewards"]) == {"function"}, rel
    givers = {n for n, b in fns.items() for l in executable(b)
              if re.search(r"\b(give|loot|item replace|summon minecraft:item)\b", re.sub(r"function \S+", "", l))
              and "mining_fatigue" not in l}
    assert givers <= {"drops/give"}, givers
    assert ("drops/give" in fns) == (which != "data")
    if "drops/give" in fns:
        assert "mega_showdown:mega_stone" in " ".join(fns["drops/give"])
    callers = {n for n, b in fns.items() if "drops/give" in calls_of(b)}
    assert callers <= {n for n in fns if n.startswith(("drops/roll_", "drops/hitter_"))}, callers
    assert bool(callers) == (which != "data")
    for p in sorted((ROOT / "data").glob("*.json")):
        text = p.read_text(encoding="utf-8")
        if p.name == "gulch_mine.json":
            doc = json.loads(text)
            doc["cutters"]["offer"].pop("raw")
            doc.pop("drops")
            text = json.dumps(doc)
        assert not re.search(r'"mega_showdown:mega_stone"', text), p.name


# ============================================================================================ the faces

FACES = SPEC["mine"]["faces"]


# Without it a face can be dug from a spot the tick's ward does not cover (the owner: the faces are "unmineable
# scenery"), or the ward is not every tick, or it spares survival or adventure players: the tick holds one Mining
# Fatigue IV line per face whose volume keeps every eye it leaves out more than 5.5 from the face (the server's break
# range), and on the interpreter a survival and an adventure player at the face's front are fatigued on every tick
# while a creative and a spectator are not.
@pytest.mark.parametrize("face", FACES, ids=[f["id"] for f in FACES])
def test_each_face_is_warded_every_tick_beyond_breaking_reach(face):
    fns = GM.keeper_files(model_of(SPEC))
    x0, y0, z0, x1, y1, z1 = face["box"]
    box = (x0, y0, z0, x1 + 1, y1 + 1, z1 + 1)
    vols = [v for v in ward_volumes(fns["tick"]) if v[0] <= x0 and v[3] >= x1 + 1 and v[2] <= z0 and v[5] >= z1 + 1]
    assert len(vols) == 1, vols
    assert least_eye_distance_outside(vols[0], box) > REACH, least_eye_distance_outside(vols[0], box)
    w = Sim(fns)
    w.run_load()
    sx, sy, sz = face["stand"]
    ps = {m: w.player((sx + 0.5, sy, sz + 0.5), mode=m) for m in ("survival", "adventure", "creative", "spectator")}
    for _ in range(3):
        for p in ps.values():
            p.effects.clear()
        w.tick()
        assert {m for m, p in ps.items() if p.effects.get("minecraft:mining_fatigue", (0, -1))[1] == 3} == \
            {"survival", "adventure"}


# Without it the retired restore comes back (SOUTHERN_RIFT_MEGA.md 13: "the restore cycle is retired"): no function the
# tick, load, an advancement reward or the Cutters reach -- with or without a farm -- writes (fill, setblock, clone,
# place) into a face's box, and none of them runs a block pass.
@pytest.mark.parametrize("which", ["data", "with a farm"])
def test_nothing_that_runs_in_game_rewrites_a_face(which):
    spec = SPEC if which == "data" else farm_spec()
    fns = all_functions(spec)
    files, _ = GM.gate_files(model_of(spec), zboxes(spec))
    roots = ["tick", "load", "cutters"] + [a["rewards"]["function"].split("/", 1)[1] for a in files.values()]
    live = reachable(fns, roots)
    assert {"tick", "drive", "leash"} <= live
    assert not [f for f in live if re.match(r"\d", f)]
    for f in live:
        for l in executable(fns[f]):
            m = re.search(r"\b(fill|setblock|clone|place \w+ \S+) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))?", l)
            if not m:
                continue
            a = [int(v) for v in m.groups()[1:4]]
            b = [int(v) for v in m.groups()[4:7]] if m.group(5) else a
            for face in spec["mine"]["faces"]:
                fb = face["box"]
                assert not all(min(a[i], b[i]) <= fb[i + 3] and max(a[i], b[i]) >= fb[i] for i in range(3)), (f, l)


# ============================================================================================ the cove town

COVE = SPEC["cove"]
BUILDINGS = COVE["buildings"]


# Without it the town is not the one 13.1 describes (a section dropped, a kind miscounted, a building duplicated):
# 69 buildings, 4 lapidaries in the heart; a canteen, 2 washhouses and 15 dwellings for the workers; 4 headframes,
# 4 winch houses, 6 spoil heaps, 3 tool sheds and 7 bunkhouse dwellings for the miners; 3 crushers, 3 sorting sheds,
# 4 sluices, 10 ore piles and 3 spoil heaps for the extraction works; 34 lamp posts; every id once.
def test_the_cove_town_is_section_13_1s_sixty_nine_buildings():
    want = {("heart", "lapidary"): 4, ("workers", "canteen"): 1, ("workers", "washhouse"): 2, ("workers", "dwelling"): 15,
            ("miners", "headframe"): 4, ("miners", "winch"): 4, ("miners", "spoil_heap"): 6, ("miners", "toolshed"): 3,
            ("miners", "dwelling"): 7, ("extraction", "crusher"): 3, ("extraction", "sorting"): 3,
            ("extraction", "sluice"): 4, ("extraction", "ore_pile"): 10, ("extraction", "spoil_heap"): 3}
    got = {}
    for b in BUILDINGS:
        got[(b["section"], b["kind"])] = got.get((b["section"], b["kind"]), 0) + 1
    assert got == want and len(BUILDINGS) == 69 == sum(want.values())
    assert len({b["id"] for b in BUILDINGS}) == 69 and len(COVE["lamp_posts"]) == 34
    houses = {"dwelling", "canteen", "washhouse", "winch", "toolshed", "crusher", "sorting", "lapidary"}   # 13.1's houses
    assert all(("door" in b) == (b["kind"] in houses) for b in BUILDINGS)


# Without it two buildings share ground (one written over the other), a house's steps run into a neighbour, a lamp post
# stands inside a building, or a cove building lands on the square's houses: every building's footprint (its rect, and
# a house's steps) is disjoint from every other's, from the town's three houses and from every lamp post.
def test_no_cove_building_stands_on_another_or_on_a_lamp_post():
    fps = [(b["id"], footprint(b)) for b in BUILDINGS] + [(h["id"], rect_cols(h["rect"])) for h in SPEC["town"]["houses"]]
    for (ia, a), (ib, b) in itertools.combinations(fps, 2):
        assert not a & b, (ia, ib, sorted(a & b)[:3])
    lamps = {tuple(p) for p in COVE["lamp_posts"] + SPEC["town"]["lamp_posts"] + SPEC["gate"]["lamp_posts"]}
    for i, f in fps:
        assert not f & lamps, (i, sorted(f & lamps))


# Without it a building or its steps block a way (the gate's road, the cutting into the sunken floor), stand on the
# square or the yard, or in the rockslide wall: each footprint misses the road's and the cutting's columns (rasterised
# here from data geometry.road), the square, the yard, the adit's portal and the wall's band.
def test_no_cove_building_is_on_a_street_the_square_or_the_wall():
    ways = road_cols(SPEC["gate"]["road"])
    for p in COVE["paths"]:
        ways |= road_cols(p)
    t = SPEC["town"]
    keep = ways | rect_cols(t["square"]["rect"]) | rect_cols(t["yard"]["rect"]) | rect_cols(SPEC["mine"]["portal"]["open_rect"]) \
        | set(band_claims(SPEC["gate"]["band"]))
    assert len(ways) > 500
    for b in BUILDINGS:
        assert not footprint(b) & keep, (b["id"], sorted(footprint(b) & keep)[:3])


# Without it a building stands outside the gulch zone (where the sixth-badge gate does not guard it) or in Victory
# Road's corridor or caves: every footprint column's centre is inside the zone polygon (even-odd, its own words), no
# column lies within half the corridor's width of any segment of Victory Road's polyline (data/routes.json), and none
# within Victory Road's caves' reach of any point data/vr_caves.json names.
def test_the_cove_town_is_in_the_gulch_zone_and_clear_of_victory_road():
    cols = sorted(set().union(*[footprint(b) for b in BUILDINGS]) | {tuple(p) for p in COVE["lamp_posts"]})
    poly = SPEC["zone"]["polygon"]
    assert not [c for c in cols if not poly_in(poly, c[0] + 0.5, c[1] + 0.5)]
    vr = next(r for r in json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))["routes"] if r["id"] == "victory_road")
    pl = vr["corridor"]["polyline"]
    P = np.array(cols, float) + 0.5
    least = math.inf
    for a, b in zip(pl, pl[1:]):
        A, B = np.array([a["x"], a["z"]], float), np.array([b["x"], b["z"]], float)
        AB = B - A
        t = np.clip(((P - A) @ AB) / max(AB @ AB, 1e-9), 0, 1)
        d = np.hypot(*(P - (A + t[:, None] * AB)).T)
        half = max(a.get("corridor_width_blocks", vr["corridor"]["width_blocks"]),
                   b.get("corridor_width_blocks", vr["corridor"]["width_blocks"])) / 2.0
        assert d.min() > half, (a, b, float(d.min()))
        least = min(least, float(d.min()))
    caves = json.loads((ROOT / "data" / "vr_caves.json").read_text(encoding="utf-8"))
    pts = []

    def walk(o):
        if isinstance(o, list) and len(o) in (2, 3) and all(isinstance(v, (int, float)) for v in o):
            pts.append((o[0], o[-1]))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(caves)
    pts = [p for p in pts if abs(p[0]) > 1000 and abs(p[1]) > 1000]
    reach = caves["tunnels"]["reach"] + max(caves["caverns"]["radius"]) + 24
    assert pts
    assert min(math.hypot(c[0] - p[0], c[1] - p[1]) for c in cols[::7] for p in pts) > reach
    assert least > 100


# ============================================================================================ with the heightmap

@pytest.fixture(scope="module")
def src():
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("NOT_EXECUTED: COBBLERS_SOURCE_ROOT is not set (the canonical heightmap is outside the repo)")
    import ground as G
    import terrain as T
    try:
        g = G.Ground(root)
    except T.TerrainUnavailable as e:            # tools/terrain.py: a missing or unpinned heightmap, not executed
        pytest.skip("NOT_EXECUTED: no canonical heightmap under %s (%s)" % (root, e))
    return root, g


@pytest.fixture(scope="module")
def sculpt(src, tmp_path_factory):
    """The sculpt's lip ring, its inward normals and its entrances: derived/rift_sculpt/plan.json when present, else
    rebuilt from the heightmap by tools/rift_heightmap.py (the plan is that tool's output)."""
    if GM.SCULPT_PLAN.is_file():
        sc = json.loads(GM.SCULPT_PLAN.read_text(encoding="utf-8"))
        plan = {"ring": sc["ring"], "normals": sc["normals"], "entrances": sc["entrances"]}
    else:
        import rift_heightmap as RH
        b = RH.build(src[0])
        X0, _X1, Z0, _Z1 = b["box"]
        plan = {"ring": [[int(x) + X0, int(z) + Z0] for z, x in b["ring"]],
                "normals": [[round(float(nx), 4), round(float(nz), 4)] for nz, nx in b["nrm"]],
                "entrances": [{"ring": bi, **{k: v for k, v in e.items() if k != "why"}} for bi, e, _ in b["ent"]]}
    path = tmp_path_factory.mktemp("sculpt") / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    plan["path"] = path
    return plan


def _gap(sculpt):
    e = next(e for e in sculpt["entrances"] if e["id"] == SPEC["gate"]["band"]["entrance"])
    return e["ring"], e["gap"], len(sculpt["ring"])


def _crag_tops(sculpt, g):
    """SOUTHERN_RIFT_MEGA.md 13.1: "at each end, the rim's highest ground within 16 outward of the first ring point
    beyond the gap, measured on the heightmap"."""
    bi, gap, T = _gap(sculpt)
    out = []
    for side in (-1, 1):
        k = (bi + side * (gap + 1)) % T
        (x, z), (nx, nz) = sculpt["ring"][k], sculpt["normals"][k]
        out.append(max(g(half_up(x - nx * d), half_up(z - nz * d)) for d in range(0, 17)))
    return out


CMD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")
AIRS = ("minecraft:air", "minecraft:cave_air", "minecraft:void_air")


def replay(pack):
    fdir = pack / "data" / "cobblers" / "function" / "gulch_mine"
    names = [n for n in (fdir / "index.txt").read_text(encoding="utf-8").split("\n") if n.strip()]
    final = {}
    for n in names:
        for ln in (fdir / (n + ".mcfunction")).read_text(encoding="utf-8").splitlines():
            m = CMD.match(ln.strip())
            if not m:
                continue
            a = [int(v) for v in m.groups()[1:4]]
            b = [int(v) for v in m.groups()[4:7]] if m.group(5) else a
            for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                    for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
                        final[(x, y, z)] = m.group(8)
    return final


class Voxels:
    """The replayed world: solid at and under tools/ground.py's ground, then every write of the pack in index order. A
    door (not iron) is open; a wall or fence is solid and cannot be stood on; lanterns, chains, bars, slabs and the
    rest are solid (stricter than the audit's walker)."""

    def __init__(self, final, g):
        (self.X0, self.X1), (self.Z0, self.Z1), (self.Y0, self.Y1) = SPEC["grid"]["x"], SPEC["grid"]["z"], SPEC["grid"]["y"]
        self.shape = (self.X1 - self.X0 + 1, self.Z1 - self.Z0 + 1, self.Y1 - self.Y0 + 1)
        self.ground = g.box(self.X0, self.Z0, self.X1, self.Z1).T
        ys = np.arange(self.shape[2])[None, None, :] + self.Y0
        self.solid = ys <= self.ground[:, :, None]
        self.tall = np.zeros(self.shape, bool)
        for (x, y, z), b in final.items():
            i = self.ix(x, y, z)
            if i is None:
                continue
            n = b.split("[")[0]
            opened = n in AIRS or (n.endswith("_door") and n != "minecraft:iron_door")
            self.solid[i] = not opened
            self.tall[i] = n.endswith("_wall") or "fence" in n
        op = ~self.solid
        floor = self.solid & ~self.tall
        self.open = op
        self.stand = np.zeros(self.shape, bool)
        self.stand[:, :, 1:-1] = op[:, :, 1:-1] & op[:, :, 2:] & floor[:, :, :-2]

    def ix(self, x, y, z):
        if self.X0 <= x <= self.X1 and self.Z0 <= z <= self.Z1 and self.Y0 <= y <= self.Y1:
            return x - self.X0, z - self.Z0, y - self.Y0
        return None

    def walk(self, start):
        """Feet cells reached on foot: a step to a side column level, up 1 (head room to jump) or down up to 3 (the
        column open all the way down)."""
        s = self.ix(*start)
        assert s is not None and self.stand[s], ("not a place to stand", start)
        seen, dq = {s}, deque([s])
        nx, nz, ny = self.shape
        st, op = self.stand, self.open
        while dq:
            i, k, j = dq.popleft()
            for a, b in ((i + 1, k), (i - 1, k), (i, k + 1), (i, k - 1)):
                if not (0 <= a < nx and 0 <= b < nz):
                    continue
                for dj in (0, 1, -1, -2, -3):
                    c = j + dj
                    if not (1 <= c < ny - 1) or not st[a, b, c] or (a, b, c) in seen:
                        continue
                    if dj == 1 and not (j + 2 < ny and op[i, k, j + 2]):
                        continue
                    if dj < 0 and not op[a, b, c:j + 2].all():
                        continue
                    seen.add((a, b, c))
                    dq.append((a, b, c))
        return seen


@pytest.fixture(scope="module")
def built(src, tmp_path_factory):
    """The pack as tools/gulch_mine.py writes it (its model, lines and write; not its own checks), into a temporary
    folder, replayed by this file."""
    root, g = src
    out = tmp_path_factory.mktemp("gulch_indep") / "cobblers_gulch_mine"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(GM, "OUT", out)
        m, _near, _tops = GM.model(root)
        GM.write(m, GM.lines(m), GM.zone_boxes(m.spec["zone"]["polygon"]))
    final = replay(out)
    return out, final, Voxels(final, g)


@pytest.fixture(scope="module")
def walks(built):
    _out, _final, vox = built
    ax, ay, az, _ = SPEC["gate"]["arrive"]
    tx, ty, tz, _ = SPEC["gate"]["turn_back"]
    return vox.walk((int(math.floor(ax)), ay, int(math.floor(az)))), vox.walk((int(math.floor(tx)), ty, int(math.floor(tz))))


# Without it the rockslide wall is traced from some other gap than the sculpt's gulch_mouth (a stale trace, a shifted
# ring), and part of the mouth is left open: the data's band points are exactly the sculpt's ring points j = -gap..gap
# round the entrance, in order.
@pytest.mark.slow
def test_the_walls_band_is_the_sculpts_gulch_mouth_gap(sculpt):
    bi, gap, T = _gap(sculpt)
    want = [[j] + sculpt["ring"][(bi + j) % T] for j in range(-gap, gap + 1)]
    assert [p[:3] for p in SPEC["gate"]["band"]["points"]] == want
    assert gap == 44


# Without it the wall stops short of the crags (the owner's complaint: the plug at y122 "reads as passable"): the crest
# the data gives at each end is no lower than the crag top measured here on the heightmap less the jag, and on the
# replayed pack every ring point of the gap stands under unbroken rock from its ground to the crest line between those
# measured tops (less the jag), the plug to its flat top.
@pytest.mark.slow
def test_the_wall_fills_the_gulch_mouth_to_the_measured_crag_tops(src, sculpt, built):
    _root, g = src
    _out, final, vox = built
    lo, hi = _crag_tops(sculpt, g)
    wall = SPEC["gate"]["band"]["wall"]
    assert wall["top"][0] >= lo - wall["jag"] and wall["top"][1] >= hi - wall["jag"], (wall["top"], (lo, hi))
    bi, gap, T = _gap(sculpt)
    short = []
    for j in range(-gap, gap + 1):
        x, z = sculpt["ring"][(bi + j) % T]
        crest = lo + (hi - lo) * (j + gap) / (2.0 * gap)
        want = int(math.ceil(crest - wall["jag"]))
        i, k = x - vox.X0, z - vox.Z0
        col = vox.solid[i, k, :]
        top_solid = int(np.nonzero(col)[0].max()) + vox.Y0
        first_air_above_ground = next((y for y in range(int(vox.ground[i, k]) + 1, want + 1) if not col[y - vox.Y0]), None)
        if top_solid < want or first_air_above_ground is not None:
            short.append((j, (x, z), top_solid, want, first_air_above_ground))
    assert not short, short[:5]


# Without it the gulch mouth has a walkable way in besides the gate (a gap in the wall, a ramp round an end, a slot that
# leads past the grille): walking on the replayed world from the turn-back point on the plateau, a player reaches the
# knock alcove before the grille, and never the arrival behind it, the square, a hall, a cove doorway or any basin
# cell (ground at or under y120) inside the zone.
@pytest.mark.slow
def test_from_the_plateau_the_only_way_to_the_wall_is_the_grille_and_it_leads_nowhere(built, walks):
    _out, _final, vox = built
    inside, outside = walks
    k = SPEC["gate"]["knock"]
    knock = {vox.ix(x, y, z) for x in range(k[0], k[3] + 1) for y in range(k[1], k[4] + 1) for z in range(k[2], k[5] + 1)}
    assert knock & outside, "the knock alcove cannot be walked to"
    assert not inside & outside, (len(inside & outside), sorted(inside & outside)[:3])
    poly = SPEC["zone"]["polygon"]
    basin = [(i + vox.X0, j + vox.Y0, kk + vox.Z0) for i, kk, j in outside
             if vox.ground[i, kk] <= 120 and poly_in(poly, i + vox.X0 + 0.5, kk + vox.Z0 + 0.5)]
    assert not basin, basin[:5]
    assert len(outside) > 500


# Without it the plug or the grille can be dug by a survival player the gate's ward does not reach (the owner: "i can
# mine around the door"): the tick's gate ward volume is the data's ward, it holds every plug block (the band's columns
# with |j| <= half_j, less the slot) and every grille bar with ward_margin to spare, and no eye it leaves out is within
# 5.5 of them.
@pytest.mark.slow
def test_the_ward_holds_the_plug_and_grille_beyond_reach(built):
    _out, final, vox = built
    g = SPEC["gate"]
    pl, gr, w, mg = g["plug"], g["grille"], g["ward"], g["ward_margin"]
    claims = band_claims(g["band"])
    cols = {c for c, j in claims.items() if abs(j) <= pl["half_j"]
            and not (c[0] > pl["max_x"] and pl["trim_z"][0] <= c[1] <= pl["trim_z"][1])}
    cells = [(x, y, z) for (x, y, z), b in final.items() if (x, z) in cols and b not in AIRS and y > vox.ground[x - vox.X0, z - vox.Z0]]
    bars = [(gr["x"], y, z) for y in range(gr["y"][0], gr["y"][1] + 1) for z in range(gr["z"][0], gr["z"][1] + 1)]
    assert all(final.get(c) == "minecraft:iron_bars" for c in bars) and len(cells) > 1000
    cells += bars
    lo = [min(c[i] for c in cells) for i in range(3)]
    hi = [max(c[i] for c in cells) for i in range(3)]
    assert hi[1] >= pl["top_y"]
    assert w[0] + mg <= lo[0] and hi[0] <= w[3] - mg and w[2] + mg <= lo[2] and hi[2] <= w[5] - mg, (w, lo, hi)
    assert w[1] + mg <= lo[1] and hi[1] <= w[4] - mg, (w, lo, hi)
    fns = GM.keeper_files(model_of(SPEC))
    vols = ward_volumes(fns["tick"])
    assert (w[0], w[1], w[2], w[3] + 1, w[4] + 1, w[5] + 1) in vols
    box = (lo[0], lo[1], lo[2], hi[0] + 1, hi[1] + 1, hi[2] + 1)
    assert least_eye_distance_outside((w[0], w[1], w[2], w[3] + 1, w[4] + 1, w[5] + 1), box) > REACH


_DOORS = {}


def _door_y(final, b):
    """The y of every lower door half the replayed pack leaves in the house's door column."""
    if id(final) not in _DOORS:
        idx = {}
        for (x, y, z), bk in final.items():
            if "_door[" in bk and "half=lower" in bk:
                idx.setdefault((x, z), []).append(y)
        _DOORS[id(final)] = idx
    return sorted(_DOORS[id(final)].get(door_col(b), []))


# Without it a cove house's floor is set from something other than the canonical heightmap (a world's surface, a
# guess), and it floats or sinks: every house's door stands one over the highest tools/ground.py ground under its rect.
@pytest.mark.slow
def test_each_cove_houses_floor_is_the_highest_heightmap_ground_under_it(src, built):
    _root, g = src
    _out, final, _vox = built
    for b in BUILDINGS:
        if "door" not in b:
            continue
        ys = _door_y(final, b)
        want = max(g(x, z) for x, z in rect_cols(b["rect"])) + 1
        assert ys == [want], (b["id"], ys, want)


# Without it a house can be seen and not entered: a doorway walled in by the ground in front, steps too high, a
# neighbour, a heap or the rim of the sunken floor. On the replayed world, this file's own walker (4 sides, up 1 with
# head room, down 3 at most, walls and fences not stood on) reaches every cove house's doorway from the gate's arrival.
@pytest.mark.slow
def test_every_cove_doorway_is_walked_to_from_the_gates_arrival(built, walks):
    _out, final, vox = built
    inside, _outside = walks
    missed = []
    for b in BUILDINGS:
        if "door" not in b:
            continue
        x, z = door_col(b)
        (y,) = _door_y(final, b)
        if vox.ix(x, y, z) not in inside:
            missed.append((b["id"], (x, y, z)))
    assert not missed, missed
    sq = SPEC["town"]["square"]
    assert vox.ix(sq["centre"][0] + 4, sq["surface_y"] + 1, sq["centre"][1]) in inside


# Without it the build decides spawns or floods (a block a spawn condition names, data/spawn_blocks.json; a fluid)
# anywhere, the cove town included: no block the replayed pack writes is one, and the cove's own columns hold a real
# variety of written blocks (the check is not run on nothing).
@pytest.mark.slow
def test_no_block_the_pack_writes_is_a_spawn_condition_or_a_fluid(built):
    _out, final, _vox = built
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    used = {b.split("[")[0] for b in final.values()}
    assert not used & spawn, sorted(used & spawn)
    assert not used & {"minecraft:water", "minecraft:lava", "minecraft:flowing_water", "minecraft:flowing_lava"}
    cove = set().union(*[footprint(b) for b in BUILDINGS])
    in_cove = {b.split("[")[0] for (x, _y, z), b in final.items() if (x, z) in cove}
    assert len(in_cove) >= 25, sorted(in_cove)


# ============================================================================================ the audit, fault by fault

def _audit(pack, sculpt, tmp, spec_path=None):
    import gulch_mine_audit as GA
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(GA, "PACK", pack)
        mp.setattr(GA, "FN", pack / "data" / "cobblers" / "function" / "gulch_mine")
        mp.setattr(GA, "ADV", pack / "data" / "cobblers" / "advancement" / "gulch_mine")
        mp.setattr(GA, "SCULPT", sculpt["path"])
        mp.setattr(GA, "OUT", tmp / "audit.json")
        if spec_path:
            mp.setattr(GA, "SPEC", spec_path)
        probs, _notes = GA.audit(os.environ["COBBLERS_SOURCE_ROOT"])
    return probs


def _append(pack, fn, line):
    p = pack / "data" / "cobblers" / "function" / "gulch_mine" / (fn + ".mcfunction")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text((p.read_text(encoding="utf-8") if p.is_file() else "") + line + "\n", encoding="utf-8")


def _edit(pack, rel, old, new):
    p = pack / "data" / "cobblers" / rel
    text = p.read_text(encoding="utf-8")
    assert old in text, (rel, old)
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def _last_block_fn(pack):
    fdir = pack / "data" / "cobblers" / "function" / "gulch_mine"
    return [n for n in (fdir / "index.txt").read_text(encoding="utf-8").split("\n") if n.strip()][-1]


def _plant(name, pack, final, tmp):
    """Plant one fault in a copy of the pack (or the data); return the data path to audit against, if changed."""
    fa = FACES[0]
    if name == "plain spawn line":
        _append(pack, "megas/spawn_steelix", "spawnpokemonat 4446 47 4852 steelix mega_evolution=mega uncatchable level=54")
    elif name == "a gate function clears a clock":
        _append(pack, "gate/knock", "scoreboard players set #steelix gm.gone -1")
    elif name == "a face restore":
        _append(pack, "faces/restore", "setblock %d %d %d mega_showdown:mega_stone_crystal[facing=west]" % tuple(fa["box"][:3]))
    elif name == "a face unwarded":
        x0, y0, z0, x1, y1, z1 = fa["box"]
        m = SPEC["faces"]["ward_margin"]
        _edit(pack, "function/gulch_mine/tick.mcfunction",
              "execute as @a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d,gamemode=!creative,gamemode=!spectator] run effect give @s "
              "minecraft:mining_fatigue 3 3 true\n" % (x0 - m, y0 - m, z0 - m, x1 - x0 + 2 * m, y1 - y0 + 2 * m, z1 - z0 + 2 * m), "")
    elif name == "the old price":
        _edit(pack, "function/gulch_mine/cutters_place.mcfunction", 'buy:{id:"mega_showdown:mega_stone",count:2}',
              'buy:{id:"mega_showdown:mega_stone",count:4}')
    elif name == "a breach in the wall":
        j, x, z, _nx, _nz = SPEC["gate"]["band"]["points"][-15]
        _append(pack, _last_block_fn(pack), "fill %d 100 %d %d 204 %d minecraft:air" % (x, z, x, z))
    elif name == "a doorway walled up":
        b = BUILDINGS[0]
        x, z = door_col(b)
        (y,) = _door_y(final, b)
        _append(pack, _last_block_fn(pack), "fill %d %d %d %d %d %d minecraft:stone" % (x, y, z, x, y + 1, z))
    elif name == "the ward shrunk":
        p = pack / "data" / "cobblers" / "advancement" / "gulch_mine" / "gate_ward.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["criteria"]["here"]["conditions"]["player"][0]["predicate"]["location"]["position"]["x"]["min"] += 4
        p.write_text(json.dumps(doc), encoding="utf-8")
    elif name == "a building on the road":
        spec = copy.deepcopy(SPEC)
        b = next(b for b in spec["cove"]["buildings"] if b["id"] == "workers_dwelling_15")
        b["rect"] = [4296, 4741, 4304, 4749]
        p = tmp / "gulch_mine.json"
        p.write_text(json.dumps(spec), encoding="utf-8")
        return p
    return None


FAULTS = {
    "plain spawn line": r"megas: a plain spawnpokemonat line",
    "a gate function clears a clock": r"megas: gate/knock clears a respawn clock outside a spawn",
    "a face restore": r"faces: functions outside the build write a face",
    "a face unwarded": r"faces: face_a is not warded every tick",
    "the old price": r"cutters: an offer for \S+ is not 2 mega_showdown:mega_stone",
    "a breach in the wall": r"gate: the wall does not reach the crest",
    "a doorway walled up": r"walk: heart_lapidary_1's doorway .* is not reached",
    "the ward shrunk": r"gate: \d+ plug columns within 7 of the ward's edge",
    "a building on the road": r"cove: workers_dwelling_15 stands on the square, the yard, a way",
}


# Without it the audit's clean verdict proves nothing: on the untouched pack it is clean (so every fault below is the
# only change), and each of nine planted faults -- a plain spawn line, a gate function clearing a clock, a face
# restore, a face left unwarded, the old 4-stone price, a breach in the wall, a walled-up doorway, a shrunk ward, a
# building moved onto the road -- makes it report that fault by name.
@pytest.mark.slow
@pytest.mark.parametrize("fault", ["none"] + sorted(FAULTS))
def test_the_audit_is_clean_on_the_pack_and_names_each_planted_fault(fault, built, sculpt, tmp_path):
    out, final, _vox = built
    pack = tmp_path / "cobblers_gulch_mine"
    shutil.copytree(out, pack)
    spec_path = None if fault == "none" else _plant(fault, pack, final, tmp_path)
    probs = _audit(pack, sculpt, tmp_path, spec_path)
    if fault == "none":
        assert probs == [], probs
    else:
        assert [p for p in probs if re.search(FAULTS[fault], p)], probs
