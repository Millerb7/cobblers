"""A small world model for the gulch pack's functions (tests/test_gulch_mine.py and the contracts).

Written by the test author from vanilla Minecraft 1.21.1 command semantics, not from tools/gulch_mine.py. It extends
tests/test_blackout_pack.py's scoreboard simulator with what the gulch's gate, keeper and faces use:

  execute   a chain of `as <selector>` (one branch per selected entity; none: nothing runs and nothing is stored),
            `positioned x y z` / `positioned as`, `if|unless entity|score|loaded|block`, `on vehicle`, `store result|
            success score`, `run`. A chain that ends in `if entity <selector>` stores the number of entities matched
            (vanilla's count), any other condition-only chain 1 or 0.
  selectors @s, @a, @e with type, tag (and !tag, repeated), gamemode (and !), advancements={id=true|false},
            x/y/z with dx/dy/dz (the entity's hitbox meets the block cuboid [x, x + d + 1)) or distance (..r, from
            the selector's x/y/z or the execution position), limit and sort=nearest|furthest.
  entities  dicts: kind "player" or "pokemon", pos (feet), tags, and for a player mode and flags (advancement ids),
            for a Pokemon species and the spawn line's words. A player's hitbox is 0.6 x 1.8, a Pokemon's 1 x 1.
  commands  tp, tag add/remove, kill, spawnpokemonat (a Pokemon at the block's centre), data merge entity, fill ...
            replace #tag and setblock into a block dict; `random value a..b` from a seeded generator; the game time.

Anything else the functions ask the model fails the test (strict), so a new command is seen, not skipped.
"""
from __future__ import annotations

import math
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import test_blackout_pack as TB  # noqa: E402


class NotModelled(RuntimeError):
    """A command this world model deliberately does not simulate.

    Raised rather than guessed. A contract test that catches it reports NOT_EXECUTED with the command, so
    an unsimulated path can never be mistaken for a satisfied one (.claude/rules/testing.md: "Never
    describe an unexecuted check as passing")."""


HALF = {"player": 0.3, "pokemon": 0.5, "villager": 0.3}
HEIGHT = {"player": 1.8, "pokemon": 1.0, "villager": 1.95}


def split_filters(body):
    out, depth, cur = [], 0, ""
    for ch in body:
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return [f.split("=", 1) for f in out]


class World(TB.Sim):
    def __init__(self, fns, tags=None, seed=7):
        super().__init__(fns=fns, query=self._query, cond=self._cond)
        self.gt = 0
        self.entities = []
        self.me = None                     # the executing entity (None: the server)
        self.pos = (0.0, 0.0, 0.0)
        self.loaded = lambda x, y, z: True
        self.blocks = {}
        self.storage = {}                   # (x, y, z) -> block id, what fill and setblock left
        self.block_tags = tags or {}       # "#ns:tag" -> set of ids
        self.rng = random.Random(seed)
        self.effects = []                  # (entity, effect line)
        self.titles = []

    # ---------------------------------------------------------------- entities
    def player(self, pos, flags=(), mode="survival", tags=()):
        e = {"kind": "player", "pos": tuple(pos), "flags": set(flags), "mode": mode, "tags": set(tags), "vehicle": None}
        self.entities.append(e)
        return e

    def pokemon(self, pos, tags=(), species="x"):
        e = {"kind": "pokemon", "pos": tuple(pos), "tags": set(tags), "species": species}
        self.entities.append(e)
        return e

    def villager(self, pos, tags=()):
        e = {"kind": "villager", "pos": tuple(pos), "tags": set(tags)}
        self.entities.append(e)
        return e

    def alive(self, e):
        return any(x is e for x in self.entities)

    def select(self, sel, origin=None):
        origin = origin or self.pos
        if sel == "@s":
            return [self.me] if self.me is not None else []
        m = re.fullmatch(r"@([aes])(?:\[(.*)\])?", sel)
        assert m, "the gulch model does not know the selector %s" % sel
        kind, filters = m.group(1), split_filters(m.group(2) or "")
        cands = [self.me] if kind == "s" else [e for e in self.entities if kind == "e" or e["kind"] == "player"]
        cands = [e for e in cands if e is not None]
        f = {}
        for k, v in filters:
            f.setdefault(k, []).append(v)
        ox, oy, oz = (float(f["x"][0]) if "x" in f else origin[0], float(f["y"][0]) if "y" in f else origin[1],
                      float(f["z"][0]) if "z" in f else origin[2])
        out = []
        for e in cands:
            ok = True
            for k, vals in f.items():
                for v in vals:
                    neg = v.startswith("!")
                    w = v[1:] if neg else v
                    if k == "type":
                        t = {"player": "minecraft:player", "pokemon": "cobblemon:pokemon", "villager": "minecraft:villager"}[e["kind"]]
                        ok &= (t != w) if neg else (t == w)
                    elif k == "tag":
                        ok &= (w not in e["tags"]) if neg else (w in e["tags"])
                    elif k == "gamemode":
                        assert e["kind"] == "player", sel
                        ok &= (e["mode"] != w) if neg else (e["mode"] == w)
                    elif k == "advancements":
                        for adv, val in re.findall(r"([a-z0-9_:/.]+)=(true|false)", v):
                            ok &= e["kind"] == "player" and ((adv in e["flags"]) == (val == "true"))
                    elif k in ("x", "y", "z", "dx", "dy", "dz", "limit", "sort", "distance"):
                        pass
                    else:
                        raise AssertionError("the gulch model does not know the selector filter %s in %s" % (k, sel))
            if not ok:
                continue
            px, py, pz = e["pos"]
            if "dx" in f or "dy" in f or "dz" in f:
                dx, dy, dz = (float(f.get(a, ["0"])[0]) for a in ("dx", "dy", "dz"))
                h, ht = HALF[e["kind"]], HEIGHT[e["kind"]]
                if not (px - h < ox + dx + 1 and px + h > ox and py < oy + dy + 1 and py + ht > oy
                        and pz - h < oz + dz + 1 and pz + h > oz):
                    continue
            if "distance" in f:
                lo, _, hi = f["distance"][0].partition("..")
                d = math.dist((px, py, pz), (ox, oy, oz))
                if (lo and d < float(lo)) or (hi and d > float(hi)):
                    continue
            out.append(e)
        if "sort" in f:
            out.sort(key=lambda e: math.dist(e["pos"], (ox, oy, oz)), reverse=f["sort"][0] == "furthest")
        if "limit" in f:
            out = out[:int(f["limit"][0])]
        return out

    # ---------------------------------------------------------------- server answers
    def _query(self, cmd):
        if cmd == "time query gametime":
            return self.gt
        m = re.fullmatch(r"random value (-?\d+)\.\.(-?\d+)", cmd)
        if m:
            return self.rng.randint(int(m.group(1)), int(m.group(2)))
        raise AssertionError("the gulch model does not know the query %s" % cmd)

    def _cond(self, kind, toks):
        if kind == "entity":
            return bool(self.select(toks[0]))
        if kind == "loaded":
            return self.loaded(*(int(v) for v in toks[:3]))
        if kind == "block":
            x, y, z, what = toks
            b = self.blocks.get((int(x), int(y), int(z)), "minecraft:air")
            return b.split("[")[0] in self.block_tags[what] if what.startswith("#") else b == what
        raise AssertionError("the gulch model does not know `%s %s`" % (kind, toks))

    # ---------------------------------------------------------------- execute, with executors
    def execute(self, t):
        self.as_sel = None
        ctxs = [(self.me, self.pos)]
        st, i, last_entity = None, 0, None
        while i < len(t):
            w = t[i]
            if w == "as":
                ctxs = [(e, p) for me, p in ctxs for e in self._with(me, p, lambda: self.select(t[i + 1]))]
                self.as_sel = t[i + 1]
                i += 2
            elif w == "positioned":
                if t[i + 1] == "as":
                    ctxs = [(me, e["pos"]) for me, p in ctxs for e in self._with(me, p, lambda: self.select(t[i + 2]))]
                    i += 3
                else:
                    xyz = tuple(float(v) for v in t[i + 1:i + 4])
                    ctxs = [(me, xyz) for me, _p in ctxs]
                    i += 4
            elif w == "on":
                assert t[i + 1] == "vehicle", t
                ctxs = [(me["vehicle"], p) for me, p in ctxs if me is not None and me.get("vehicle") is not None]
                i += 2
            elif w in ("if", "unless"):
                kind = t[i + 1]
                if kind == "score":
                    n = 6 if t[i + 4] == "matches" else 7
                    sub = t[i:i + n]
                    keep = []
                    for me, p in ctxs:
                        # the score tests read fake players only: run the base simulator's test on this one token run
                        ok = self._score_test(sub)
                        if ok:
                            keep.append((me, p))
                    ctxs = keep
                else:
                    n = {"entity": 3, "block": 6, "loaded": 5}[kind]
                    keep = []
                    for me, p in ctxs:
                        res = self._with(me, p, lambda: self._cond(kind, t[i + 2:i + n]))
                        if (res if w == "if" else not res):
                            keep.append((me, p))
                    if kind == "entity" and w == "if" and i + n == len(t):
                        last_entity = t[i + 2]
                    ctxs = keep
                i += n
            elif w == "store":
                assert t[i + 2] == "score", t
                st, i = (t[i + 1], t[i + 3], t[i + 4]), i + 5
            elif w == "run":
                rest = " ".join(t[i + 1:])
                ret = None
                for me, p in ctxs:
                    if st:
                        v = self._with(me, p, lambda: self.value(rest))
                        self.set(st[1], st[2], v if st[0] == "result" else int(bool(v)))
                    else:
                        r = self._with(me, p, lambda: self.command(rest))
                        ret = r if r is TB.RETURN else ret
                return ret
            else:
                raise AssertionError("the gulch model: unknown execute token %r in %r" % (w, " ".join(t)))
        if st:
            if last_entity is not None and st[0] == "result":
                v = sum(len(self._with(me, p, lambda: self.select(last_entity))) for me, p in [(self.me, self.pos)])
                v = v if ctxs else 0
            else:
                v = 1 if ctxs else 0
            self.set(st[1], st[2], v)
        return None

    def _score_test(self, sub):
        w, _kind, h, o = sub[:4]
        known = (h, o) in self.score
        a = self.get(h, o)
        if sub[4] == "matches":
            res = known and TB.in_range(a, sub[5])
        else:
            b = self.get(sub[5], sub[6])
            known = known and (sub[5], sub[6]) in self.score
            res = known and {"<": a < b, "<=": a <= b, "=": a == b, ">": a > b, ">=": a >= b}[sub[4]]
        return res if w == "if" else not res

    def _with(self, me, pos, fn):
        old = self.me, self.pos
        self.me, self.pos = me, pos
        try:
            return fn()
        finally:
            self.me, self.pos = old

    # ---------------------------------------------------------------- commands
    def command(self, cmd):
        t = cmd.split(" ")
        if t[0] == "tp":
            assert t[1] == "@s", cmd
            if self.me is not None:
                self.me["pos"] = tuple(float(v) for v in t[2:5])
                if len(t) > 5:
                    self.me["yaw"] = float(t[5])
            self.log.append(cmd)
            return None
        if t[0] == "tag" and t[2] in ("add", "remove"):
            for e in self.select(t[1]):
                (e["tags"].add if t[2] == "add" else e["tags"].discard)(t[3])
            return None
        if t[0] == "kill":
            for e in self.select(t[1]):
                self.entities = [x for x in self.entities if x is not e]
            self.log.append(cmd)
            return None
        if t[0] == "spawnpokemonat":
            x, y, z = (int(v) for v in t[1:4])
            e = self.pokemon((x + 0.5, y, z + 0.5), species=t[4])
            e["props"] = t[4:]
            self.log.append(cmd)
            return None
        if t[0] == "data" and t[1] == "merge" and t[2] == "entity":
            if self.me is not None:
                self.me.setdefault("nbt", []).append(" ".join(t[4:]))
            return None
        if t[0] == "fill":
            x0, y0, z0, x1, y1, z1 = (int(v) for v in t[1:7])
            block = t[7]
            mode = t[8:] if len(t) > 8 else []
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        cur = self.blocks.get((x, y, z), "minecraft:air")
                        if mode and mode[0] == "replace":
                            if cur.split("[")[0] not in self.block_tags[mode[1]]:
                                continue
                        self.blocks[(x, y, z)] = block
            self.log.append(cmd)
            return None
        if t[0] == "setblock":
            self.blocks[tuple(int(v) for v in t[1:4])] = t[4]
            return None
        if t[0] == "effect":
            self.effects.append((self.me, cmd))
            return None
        if t[0] == "title":
            self.titles.append((self.me, cmd))
            return None
        if t[0] == "data":
            # The farm dens' drop roll (tools/gulch_mine.py keeper_files) is the only thing in this build
            # that touches NBT storage, and it did not exist until a farm den existed to serve: the data
            # had no `farms` key, so these lines were never generated and this model never saw them.
            #
            # What is modelled here: `data modify storage <ns> <path> set value <json>`, which is how the
            # keeper's load function seeds the hex-digit table and the empty den list. That is a plain
            # assignment and the model can hold it honestly.
            #
            # What is NOT modelled: `set from entity ... UUID`, `append value`, and an indexed read of
            # `dens[{id:"..."}]`. Those are the roll's per-player identity path, and a model that guessed
            # at them would hand back a PASS for a contract it had not actually simulated, which is worse
            # than no answer. So they raise NotModelled and the contract reports NOT_EXECUTED.
            self.log.append(cmd)
            m = re.match(r"^data modify storage (\S+) (\S+) set value (.*)$", cmd)
            if m:
                self.storage.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
                return None
            if cmd.startswith("execute unless data storage") or " run data modify storage " in cmd:
                return super().command(cmd)
            raise NotModelled(cmd)
        if t[0] in ("scoreboard", "function", "execute", "return") or t[0] in ("advancement", "give", "forceload", "schedule"):
            if t[0] in ("advancement", "give", "forceload", "schedule"):
                self.log.append(cmd)
                return None
            return super().command(cmd)
        raise AssertionError("the gulch model does not know the command %s" % cmd)

    def tick(self, n=1, name="gulch_mine/tick"):
        """n server ticks: the game time advances, then the pack's tick function runs (minecraft:tick)."""
        for _ in range(n):
            self.gt += 1
            self.call(name)
