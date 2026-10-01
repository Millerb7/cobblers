"""A small world model for the gulch pack's functions (tests/test_gulch_mine.py and the contracts).

Written by the test author from vanilla Minecraft 1.21.1 command semantics, not from tools/gulch_mine.py. It extends
tests/test_blackout_pack.py's scoreboard simulator with what the gulch's gate, keeper and faces use:

  execute   a chain of `as <selector>` (one branch per selected entity; none: nothing runs and nothing is stored),
            `positioned x y z` / `positioned as`, `if|unless entity|score|loaded|block|data storage`,
            `on vehicle|attacker|owner`, `store result|success score|storage`, `run`. A chain that ends in
            `if entity <selector>` stores the number of entities matched (vanilla's count), any other
            condition-only chain 1 or 0.
  selectors @s, @a, @e with type, tag (and !tag, repeated), gamemode (and !), advancements={id=true|false},
            x/y/z with dx/dy/dz (the entity's hitbox meets the block cuboid [x, x + d + 1)) or distance (..r, from
            the selector's x/y/z or the execution position), limit and sort=nearest|furthest.
  entities  dicts: kind "player", "pokemon", "villager" or "item", pos (feet), tags, nbt (a real NBT compound, so
            `data merge|modify|get entity` behave), uuid (an int array, as vanilla stores one), and for a player
            mode and flags (advancement ids), for a Pokemon species and the spawn line's words. A player's hitbox
            is 0.6 x 1.8, a Pokemon's 1 x 1, an item's 0.25 cube.
  commands  tp, tag add/remove, kill, spawnpokemonat (a Pokemon at the block's centre), summon minecraft:item,
            fill ... replace #tag and setblock into a block dict; `random value a..b` from a seeded generator;
            the game time.
  storage   command storage as real NBT, on tests/nbt_sim.py's SNBT parser and NbtPathArgument grammar (so a
            filtered element `dens[{id:"..."}]` and an index `hex[3]` resolve as Minecraft resolves them):
            `data modify storage <ns> <path> set|append value <snbt>`, `set|append from storage <ns> <path>`,
            `set|append from entity <selector> <path>`, `data remove storage`, `data get entity`,
            `data modify entity <selector> <path> set from entity <selector> <path>`, and
            `function ... with storage <ns> <path>` (MacroFunction's rendering). A `set` that changes nothing
            succeeds 0 and a source element that does not exist fails, which is what the drop roll's
            hitter comparison is built on.

Anything else the functions ask the model fails the test (strict), so a new command is seen, not skipped: an
unknown command is an AssertionError and a deliberately unmodelled one is NotModelled.
"""
from __future__ import annotations

import math
import random
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import nbt_sim as N  # noqa: E402
import test_blackout_pack as TB  # noqa: E402


class NotModelled(RuntimeError):
    """A command this world model deliberately does not simulate.

    Raised rather than guessed. A contract test that catches it reports NOT_EXECUTED with the command, so
    an unsimulated path can never be mistaken for a satisfied one (.claude/rules/testing.md: "Never
    describe an unexecuted check as passing")."""


HALF = {"player": 0.3, "pokemon": 0.5, "villager": 0.3, "item": 0.125}
HEIGHT = {"player": 1.8, "pokemon": 1.0, "villager": 1.95, "item": 0.25}
TYPE = {"player": "minecraft:player", "pokemon": "cobblemon:pokemon", "villager": "minecraft:villager",
        "item": "minecraft:item"}


def uuid_text(ints):
    """Java's UUID.toString() of an NBT int array (UUIDUtil.uuidFromIntArray), as a selector names an entity."""
    v = 0
    for i in ints:
        v = (v << 32) | (i & 0xFFFFFFFF)
    return str(uuid.UUID(int=v))


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
        self.blocks = {}                   # (x, y, z) -> block id, what fill and setblock left
        self.nbt = {}                      # command storage: namespace -> the NBT root (tests/nbt_sim.py)
        self.block_tags = tags or {}       # "#ns:tag" -> set of ids
        self.rng = random.Random(seed)
        self.rolls = []                    # `random value a..b` answers from here first, so a test can fix the roll
        self.ids = random.Random(seed ^ 0x5EED)   # entity UUIDs: distinct and reproducible, never the roll's generator
        self.effects = []                  # (entity, effect line)
        self.titles = []
        self.failed = []                   # commands that failed (a data source with no element: nothing changes)

    # ---------------------------------------------------------------- entities
    def _uuid(self):
        """A fresh UUID as vanilla stores one: four signed 32-bit ints (UUIDUtil.uuidToIntArray)."""
        return N.IntArray(self.ids.getrandbits(32) - 2 ** 31 for _ in range(4))

    def player(self, pos, flags=(), mode="survival", tags=()):
        e = {"kind": "player", "pos": tuple(pos), "flags": set(flags), "mode": mode, "tags": set(tags), "vehicle": None}
        self.entities.append(self._claim(e))
        return e

    def pokemon(self, pos, tags=(), species="x"):
        e = {"kind": "pokemon", "pos": tuple(pos), "tags": set(tags), "species": species}
        self._claim(e)
        # a Cobblemon entity carries its Pokemon's own UUID besides the entity's (megas/pid reads Pokemon.UUID)
        e["nbt"]["Pokemon"] = {"UUID": self._uuid()}
        self.entities.append(e)
        return e

    def villager(self, pos, tags=()):
        e = {"kind": "villager", "pos": tuple(pos), "tags": set(tags)}
        self.entities.append(self._claim(e))
        return e

    def item(self, pos, nbt=None, tags=()):
        e = {"kind": "item", "pos": tuple(pos), "tags": set(tags)}
        self._claim(e)
        e["nbt"].update(nbt or {})
        e["tags"] |= set(e["nbt"].get("Tags", []))
        self.entities.append(e)
        return e

    def _claim(self, e):
        e.setdefault("nbt", {})["UUID"] = self._uuid()
        return e

    def alive(self, e):
        return any(x is e for x in self.entities)

    def select(self, sel, origin=None):
        origin = origin or self.pos
        if sel == "@s":
            return [self.me] if self.me is not None else []
        if not sel.startswith("@"):
            # vanilla: an entity may be named by its UUID's text. The drop roll's `$execute as $(who)` does
            # exactly that, with the UUID the battle_fainted callback handed it
            assert re.fullmatch(r"[0-9a-f-]{36}", sel), "the gulch model does not know the selector %s" % sel
            return [e for e in self.entities if uuid_text(e["nbt"]["UUID"]) == sel]
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
                        # vanilla: an unqualified entity type means the minecraft namespace (`type=player`)
                        same = TYPE[e["kind"]] == (w if ":" in w else "minecraft:" + w)
                        ok &= (not same) if neg else same
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
            return self.rolls.pop(0) if self.rolls else self.rng.randint(int(m.group(1)), int(m.group(2)))
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
        if kind == "data":
            if toks[0] == "storage":
                return bool(self.sget(toks[1], toks[2]))
            raise NotModelled("execute if data %s" % " ".join(toks))
        raise AssertionError("the gulch model does not know `%s %s`" % (kind, toks))

    # ---------------------------------------------------------------- command storage, as NBT
    def root(self, ns):
        return self.nbt.setdefault(ns, {})

    def sget(self, ns, path):
        """Every tag the NBT path resolves to in that storage (empty: the path has no element)."""
        return N.path_get(self.root(ns), N.parse_path(path))

    def enbt(self, sel, path):
        """`data ... from entity <sel> <path>`: the first selected entity's tag at that path, or None."""
        for e in self.select(sel):
            vals = N.path_get(e.setdefault("nbt", {}), N.parse_path(path))
            if vals:
                return vals[0]
        return None

    def args_from(self, rest):
        """MacroFunction's arguments: a string renders as its own text, a number as its digits (tests/nbt_sim.py)."""
        if rest.startswith("with storage "):
            _, _, ns, path = rest.split(" ", 3)
            vals = self.sget(ns, path)
            assert vals and isinstance(vals[-1], dict), "no compound at %s %s for a macro call" % (ns, path)
            return {k: N.macro_text(v) for k, v in vals[-1].items()}
        if rest.startswith("with "):
            raise NotModelled("function ... %s" % rest)
        return TB.inline_args(rest)

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
            elif w == "at":
                # vanilla: the position (and rotation, which nothing here reads) becomes the entity's
                ctxs = [(me, e["pos"]) for me, p in ctxs for e in self._with(me, p, lambda: self.select(t[i + 1]))]
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
                # vanilla: the related entity becomes the executor; with no such entity the chain ends there
                rel = t[i + 1]
                if rel not in ("vehicle", "attacker", "owner"):
                    raise NotModelled("execute on %s" % rel)
                ctxs = [(me[rel], p) for me, p in ctxs
                        if me is not None and me.get(rel) is not None and self.alive(me[rel])]
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
                    n = {"entity": 3, "block": 6, "loaded": 5,
                         "data": 5 if t[i + 2] in ("storage", "entity") else 7}[kind]
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
                if t[i + 2] == "score":
                    st, i = (t[i + 1], "score", t[i + 3], t[i + 4]), i + 5
                elif t[i + 2] == "storage":
                    st, i = (t[i + 1], "storage", t[i + 3], t[i + 4], t[i + 5], t[i + 6]), i + 7
                else:
                    raise NotModelled("execute store %s %s" % (t[i + 1], t[i + 2]))
            elif w == "run":
                rest = " ".join(t[i + 1:])
                ret = None
                for me, p in ctxs:
                    if st:
                        v = self._with(me, p, lambda: self.value(rest))
                        self._store(st, v)
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
            self._store(st, v)
        return None

    def _store(self, st, v):
        """`store result|success score|storage`: a data command answers with a Res (its result and its success)."""
        if isinstance(v, N.Res):
            v = v.result if st[0] == "result" else v.success
        if st[1] == "score":
            return self.set(st[2], st[3], v if st[0] == "result" else int(bool(v)))
        ns, path, typ, scale = st[2], st[3], st[4], float(st[5])
        n = v * scale
        tag = {"int": lambda: int(n), "byte": lambda: N.Byte(int(n)), "short": lambda: N.Short(int(n)),
               "long": lambda: N.Long(int(n)), "float": lambda: N.Float(n), "double": lambda: float(n)}[typ]()
        N.path_set(self.root(ns), N.parse_path(path), tag)

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
        if t[0] == "summon":
            # the only summon the gulch writes is the drop's item entity, at the executor's feet
            assert t[1] == "minecraft:item" and t[2:5] == ["~", "~", "~"], cmd
            self.item(self.pos, N.parse_snbt(" ".join(t[5:])))
            self.log.append(cmd)
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
            self.data(cmd, t)
            return None
        if t[0] in ("scoreboard", "function", "execute", "return") or t[0] in ("advancement", "give", "forceload", "schedule"):
            if t[0] in ("advancement", "give", "forceload", "schedule"):
                self.log.append(cmd)
                return None
            return super().command(cmd)
        raise AssertionError("the gulch model does not know the command %s" % cmd)

    def value(self, cmd):
        """A command run under `execute store`: its result and, for a data command, its success too."""
        t = cmd.split(" ")
        if t[0] == "data":
            return self.data(cmd, t)
        return super().value(cmd)

    # ---------------------------------------------------------------- the data command
    #
    # Only these forms. Everything else the gulch does not write is NotModelled rather than guessed: a model
    # that guesses hands back a PASS for a contract it never simulated (.claude/rules/testing.md).
    #
    #   data modify storage <ns> <path> set|append value <snbt>
    #   data modify storage <ns> <path> set|append from storage <ns> <path>
    #   data modify storage <ns> <path> set|append from entity <selector> <path>
    #   data modify entity <selector> <path> set from entity <selector> <path>
    #   data merge  entity <selector> <snbt>
    #   data remove storage <ns> <path>
    #   data get    entity <selector> <path>
    #
    # Vanilla's answers, which the drop roll is built on: `set` reports how many tags it changed, so setting a
    # tag to the value it already holds succeeds 0 (ERROR_MERGE_UNCHANGED); a source path with no element fails
    # and changes nothing (ERROR_GET_NOT_FOUND), which also succeeds 0.
    def data(self, cmd, t):
        self.log.append(cmd)
        op, what = t[1], t[2]
        if op == "merge" and what == "entity":
            tag = N.parse_snbt(" ".join(t[4:]))
            n = 0
            for e in self.select(t[3]):
                e.setdefault("nbt", {}).update(tag)
                n += len(tag)
            return N.Res(n, int(bool(n)))
        if op == "get" and what == "entity":
            v = self.enbt(t[3], t[4])
            if v is None:
                self.failed.append(cmd)
                return N.Res(0, 0)
            if isinstance(v, (dict, list, tuple, str)):
                return N.Res(len(v), 1)
            return N.Res(int(v), 1)
        if op == "remove" and what == "storage":
            n = N.path_remove(self.root(t[3]), N.parse_path(t[4]))
            if not n:
                self.failed.append(cmd)
            return N.Res(n, int(bool(n)))
        if op == "modify" and what in ("storage", "entity"):
            how, rest = t[5], cmd.split(" ", 6)[6]
            if how not in ("set", "append"):
                raise NotModelled(cmd)
            if rest.startswith("value "):
                vals = [N.parse_snbt(rest[len("value "):])]
            elif rest.startswith("from storage "):
                _, _, sns, spath = rest.split(" ", 3)
                vals = self.sget(sns, spath)
            elif rest.startswith("from entity "):
                _, _, ssel, spath = rest.split(" ", 3)
                v = self.enbt(ssel, spath)
                vals = [] if v is None else [v]
            else:
                raise NotModelled(cmd)
            if not vals:
                self.failed.append(cmd)                     # "found no elements matching": nothing changes
                return N.Res(0, 0)
            nodes = N.parse_path(t[4])
            roots = [self.root(t[3])] if what == "storage" else \
                    [e.setdefault("nbt", {}) for e in self.select(t[3])]
            n = 0
            for r in roots:
                n += N.path_set(r, nodes, vals[-1]) if how == "set" else N.path_append(r, nodes, vals)
            return N.Res(n, int(bool(n)))
        raise NotModelled(cmd)

    def tick(self, n=1, name="gulch_mine/tick"):
        """n server ticks: the game time advances, then the pack's tick function runs (minecraft:tick)."""
        for _ in range(n):
            self.gt += 1
            self.call(name)
