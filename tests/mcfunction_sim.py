"""A small Minecraft 1.21.1 command interpreter for the generated function packs tests run over ticks.

Written by the test author from vanilla semantics, not from the generators, for the subset the ambient and level-cap
packs use:

  execute   as / at / positioned / on target / if|unless score (matches and comparisons) / entity / loaded / data
            entity, store result|success score|storage, run; a trailing condition is the command's result (the entity
            count for `if entity`), as vanilla does
  scoreboard objectives add, players set|add|remove|get|operation (= and +=)
  tag, data merge entity, data modify storage ... set value, data remove entity, data get entity (scale 1)
  effect give, summon (interaction, item_display), tp (absolute, ~ and yaw/pitch), kill, item replace entity ...
  contents with, playsound, particle, tellraw, fill (recorded), forceload add|remove, return
  function <name> [{snbt}] | [with storage <id> <path>]: a function with any `$` line is a macro function; called
            without arguments, or with an argument it lacks, it fails whole (nothing in it runs), as MacroFunction does.
            A macro argument renders a string without quotes and anything else as SNBT
  spawnpokemonat (Cobblemon): spawns a NoAI Pokemon only when the line came from a macro. EXP-046 measured that a
            plain line parsed at server start spawns nothing until a /reload re-parses it, so a plain line is recorded
            as `inert_spawn` and does nothing
  rctmod player get level_cap @s: the cap the test gives the player; with none, the command fails

Selectors see only entities whose chunk is loaded (`loaded(x, z)`, plus force-loaded chunks). A selector's `distance`
is measured from its x/y/z arguments, else from the execution position; the server's own position (a tick or load
function, an RCON command) is the world spawn, as MinecraftServer.createCommandSourceStack() places it. A failed
command stores 0 through `execute store result` (CommandResultCallback on failure). An unknown command raises
Unsupported, so a construct the interpreter does not model fails the test instead of passing silently.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path


class Unsupported(Exception):
    pass


class Failed(Exception):
    """A command that fails in game (nothing found, a missing score, a bad path)."""


class Return(Exception):
    def __init__(self, value):
        self.value = value


# ------------------------------------------------------------------------------------------------ SNBT

class _Snbt:
    NUM = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?[bBsSlLfFdD]?$")

    def __init__(self, s):
        self.s, self.i = s, 0

    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1

    def value(self):
        self.ws()
        c = self.s[self.i]
        if c == "{":
            self.i += 1
            out = {}
            self.ws()
            if self.s[self.i] == "}":
                self.i += 1
                return out
            while True:
                self.ws()
                k = self.string_or_word()
                self.ws()
                assert self.s[self.i] == ":", "SNBT: expected : at %d in %r" % (self.i, self.s[:200])
                self.i += 1
                out[k] = self.value()
                self.ws()
                if self.s[self.i] == ",":
                    self.i += 1
                    continue
                assert self.s[self.i] == "}", "SNBT: expected '}' at %d in %r" % (self.i, self.s)
                self.i += 1
                return out
        if c == "[":
            self.i += 1
            out = []
            self.ws()
            if self.s[self.i] == "]":
                self.i += 1
                return out
            while True:
                out.append(self.value())
                self.ws()
                if self.s[self.i] == ",":
                    self.i += 1
                    continue
                assert self.s[self.i] == "]", "SNBT: expected ']' in %r" % self.s
                self.i += 1
                return out
        if c in "\"'":
            return Str(self.quoted())
        w = self.word()
        if w in ("true", "false"):
            return 1 if w == "true" else 0
        if self.NUM.match(w):
            body = w.rstrip("bBsSlLfFdD") if w[-1] in "bBsSlLfFdD" else w
            f = float(body)
            if w[-1] in "fFdD" or "." in body or "e" in body.lower():
                return f
            return int(f)
        return Str(w)

    def quoted(self):
        q = self.s[self.i]
        self.i += 1
        out = []
        while self.s[self.i] != q:
            if self.s[self.i] == "\\":
                self.i += 1
            out.append(self.s[self.i])
            self.i += 1
        self.i += 1
        return "".join(out)

    def word(self, extra="_-.+:"):
        j = self.i
        while self.i < len(self.s) and (self.s[self.i].isalnum() or self.s[self.i] in extra):
            self.i += 1
        if j == self.i:
            raise AssertionError("SNBT: unexpected %r at %d in %r" % (self.s[self.i:self.i + 10], self.i, self.s[:200]))
        return self.s[j:self.i]

    def string_or_word(self):
        return self.quoted() if self.s[self.i] in "\"'" else self.word("_-.+")


class Str(str):
    """An NBT string (so a macro renders it without quotes and a number with none)."""


_SNBT_CACHE = {}


def snbt(s):
    if s not in _SNBT_CACHE:
        p = _Snbt(s)
        v = p.value()
        p.ws()
        assert p.i == len(s), "SNBT: trailing text in %r" % s
        _SNBT_CACHE[s] = v
    import copy
    return copy.deepcopy(_SNBT_CACHE[s])


def render(v):
    """A macro argument as MacroFunction renders it."""
    if isinstance(v, str):
        return str(v)
    if isinstance(v, bool):
        return "1b" if v else "0b"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    raise Unsupported("macro argument %r" % (v,))


def split_path(path):
    """An NBT path `a.b[3].c` as ['a', 'b', 3, 'c']."""
    out = []
    for part in re.finditer(r"([A-Za-z0-9_]+)|\[(-?\d+)\]|(\.)", path):
        if part.group(1):
            out.append(part.group(1))
        elif part.group(2) is not None:
            out.append(int(part.group(2)))
    return out


# ------------------------------------------------------------------------------------------------ entities

class Entity:
    _next = 0

    def __init__(self, etype, pos, nbt=None, tags=()):
        Entity._next += 1
        self.uid = Entity._next
        self.type = etype if ":" in etype else "minecraft:" + etype
        self.pos = [float(v) for v in pos]
        self.rot = [0.0, 0.0]
        self.nbt = dict(nbt or {})
        self.tags = set(tags)
        self.effects = {}
        self.item = None
        self.alive = True
        self.messages = []           # tellraw to this entity (players)
        self.heard = []              # playsound delivered to this entity (players)

    def __repr__(self):
        return "<%s #%d %s %s>" % (self.type, self.uid, sorted(self.tags), [round(v, 2) for v in self.pos])


class Ctx:
    __slots__ = ("executor", "pos", "rot")

    def __init__(self, executor, pos, rot=(0.0, 0.0)):
        self.executor, self.pos, self.rot = executor, tuple(pos), tuple(rot)

    def but(self, executor=None, pos=None, rot=None):
        return Ctx(self.executor if executor is None else executor, self.pos if pos is None else pos,
                   self.rot if rot is None else rot)


def _range(spec):
    if ".." in spec:
        a, b = spec.split("..")
        return (float(a) if a else -math.inf, float(b) if b else math.inf)
    v = float(spec)
    return (v, v)


def _args(body):
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
    return [tuple(a.split("=", 1)) for a in out]


def _nbt_match(want, have):
    if isinstance(want, dict):
        return isinstance(have, dict) and all(k in have and _nbt_match(v, have[k]) for k, v in want.items())
    return want == have


# ------------------------------------------------------------------------------------------------ the world

class World:
    def __init__(self, functions, spawn=(0.0, 64.0, 0.0), loaded=None):
        """functions: {'ns:path': [lines]}."""
        self.functions = functions
        self.spawn = tuple(float(v) for v in spawn)
        self.entities = []
        self.scores = {}
        self.objectives = set()
        self.storage = {}
        self._loaded = loaded or (lambda x, z: True)
        self.forced = set()
        self.log = []                 # (tick, kind, detail)
        self.log_fn = []              # the function each log entry was made in (None: a command outside one)
        self.stack = []
        self.lookups = []             # (path, index, length) of every list index a path resolved
        self.errors = []              # failures that vanilla reports only in the log
        self.tick_no = 0
        self.rct_cap = {}             # player uid -> the level cap `rctmod player get level_cap` returns
        self.calls = []               # (tick, function) for every function run
        self.tags = {"load": [], "tick": []}
        self.terrain = lambda x, y, z: "minecraft:air"   # what stands in a cell no logged write has touched

    def block_at(self, x, y, z):
        """The block in a cell: the latest plain `fill` / `setblock` in the log that covers it, else terrain(x, y, z).
        A write with a filter (`replace <block>`) is not modelled and is skipped, so a test that needs a block state
        gives it as terrain or writes it plainly. Added 2026-10-12 for `execute if block` (tools/legendaries.py's
        retired-chamber cleanup probes the old pedestal)."""
        x, y, z = (int(math.floor(v)) for v in (x, y, z))
        for entry in reversed(self.log):
            kind, detail = entry[1], entry[2]
            if kind == "fill":
                a, b, tok = detail
                if (len(tok) == 1 or (len(tok) == 2 and tok[1] in ("replace", "destroy"))) and \
                        all(min(a[i], b[i]) <= v <= max(a[i], b[i]) for i, v in enumerate((x, y, z))):
                    return tok[0]
            elif kind == "setblock":
                t = detail.split()
                if len(t) in (4, 5) and (len(t) == 4 or t[4] in ("replace", "destroy")) \
                        and tuple(int(float(v)) for v in t[:3]) == (x, y, z):
                    return t[3]
        return self.terrain(x, y, z)

    # -- loading
    @classmethod
    def from_pack(cls, pack_dir, **kw):
        pack_dir = Path(pack_dir)
        fns = {}
        for p in (pack_dir / "data").glob("*/function/**/*.mcfunction"):
            ns = p.relative_to(pack_dir / "data").parts[0]
            rel = p.relative_to(pack_dir / "data" / ns / "function").with_suffix("").as_posix()
            fns["%s:%s" % (ns, rel)] = p.read_text(encoding="utf-8").splitlines()
        w = cls(fns, **kw)
        for kind in ("load", "tick"):
            t = pack_dir / "data" / "minecraft" / "tags" / "function" / ("%s.json" % kind)
            w.tags[kind] = json.loads(t.read_text(encoding="utf-8"))["values"] if t.is_file() else []
        return w

    def _log(self, entry):
        self.log.append(entry)
        self.log_fn.append(self.stack[-1] if self.stack else None)

    def logged(self, kind, fn_prefix=""):
        """[(tick, detail)] of one kind of entry, made in functions whose name starts with fn_prefix."""
        return [(e[0], e[2]) for e, f in zip(self.log, self.log_fn)
                if e[1] == kind and (f or "").startswith(fn_prefix)]

    def loaded(self, x, z):
        return (math.floor(x) // 16, math.floor(z) // 16) in self.forced or self._loaded(x, z)

    def server(self):
        return Ctx(None, self.spawn)

    def add_player(self, pos, name="p"):
        e = Entity("minecraft:player", pos)
        e.name = name
        self.entities.append(e)
        return e

    def add(self, e):
        self.entities.append(e)
        return e

    def living(self, etype=None, tag=None):
        return [e for e in self.entities if e.alive and (etype is None or e.type == etype)
                and (tag is None or tag in e.tags)]

    def run_load(self):
        for f in self.tags.get("load", []):
            self.function(f, self.server())

    def tick(self, n=1):
        for _ in range(n):
            self.tick_no += 1
            for f in self.tags.get("tick", []):
                self.function(f, self.server())

    # -- functions
    def function(self, name, ctx, args=None):
        if name not in self.functions:
            raise Failed("unknown function %s" % name)
        lines = self.functions[name]
        is_macro = any(l.lstrip().startswith("$") for l in lines)
        if is_macro:
            if args is None:
                self.errors.append("macro function %s called without arguments" % name)
                raise Failed("macro function without arguments")
            body = []
            for l in lines:
                s = l.strip()
                if s.startswith("$"):
                    keys = re.findall(r"\$\(([A-Za-z0-9_]+)\)", s)
                    missing = [k for k in keys if k not in args]
                    if missing:
                        self.errors.append("%s: missing macro argument(s) %s" % (name, missing))
                        raise Failed("missing macro argument")
                    body.append((re.sub(r"\$\(([A-Za-z0-9_]+)\)", lambda m: render(args[m.group(1)]), s[1:]), True))
                else:
                    body.append((s, False))
        else:
            body = [(l.strip(), False) for l in lines]
        self.calls.append((self.tick_no, name))
        result = 0
        self.stack.append(name)
        try:
            for line, from_macro in body:
                if not line or line.startswith("#"):
                    continue
                try:
                    result = self.command(line, ctx, from_macro)
                except Failed:
                    result = 0
        except Return as r:
            return r.value
        finally:
            self.stack.pop()
        return result

    # -- selectors
    def select(self, sel, ctx, single=False):
        if not sel.startswith("@"):
            # a UUID or a player name
            return [e for e in self.entities if e.alive and sel in (getattr(e, "uuid", None), getattr(e, "name", None))]
        m = re.match(r"@([aepsr])(?:\[(.*)\])?$", sel)
        if not m:
            raise Unsupported("selector %r" % sel)
        kind, body = m.group(1), m.group(2) or ""
        args = _args(body)
        if kind == "s":
            pool = [ctx.executor] if ctx.executor is not None and ctx.executor.alive else []
        elif kind in "ap":
            pool = [e for e in self.entities if e.alive and e.type == "minecraft:player"]
        else:
            pool = [e for e in self.entities if e.alive and self.loaded(e.pos[0], e.pos[2])]
        origin = list(ctx.pos)
        limit, sort = None, ("nearest" if kind == "p" else "arbitrary")
        for k, v in args:
            if k in ("x", "y", "z"):
                origin["xyz".index(k)] = float(v)
        for k, v in args:
            if k == "type":
                t = v if ":" in v else "minecraft:" + v
                pool = [e for e in pool if e.type == t]
            elif k == "tag":
                if v.startswith("!"):
                    pool = [e for e in pool if v[1:] not in e.tags]
                else:
                    pool = [e for e in pool if v in e.tags]
            elif k == "distance":
                lo, hi = _range(v)
                pool = [e for e in pool if lo <= math.dist(e.pos, origin) <= hi]
            elif k == "limit":
                limit = int(v)
            elif k == "sort":
                sort = v
            elif k == "nbt":
                want = snbt(v)
                pool = [e for e in pool if _nbt_match(want, e.nbt)]
            elif k in ("x", "y", "z"):
                pass
            elif k in ("dx", "dy", "dz"):
                # vanilla's volume is the box from the origin to origin + d, grown by one block, met by the entity's
                # hitbox; this simplification takes the entity's position in [origin, origin + d + 1)
                i, d = "xyz".index(k[1]), float(v)
                lo, hi = min(origin[i], origin[i] + d), max(origin[i], origin[i] + d) + 1
                pool = [e for e in pool if lo <= e.pos[i] < hi]
            else:
                raise Unsupported("selector argument %s" % k)
        if sort == "nearest":
            pool = sorted(pool, key=lambda e: math.dist(e.pos, origin))
        elif sort == "furthest":
            pool = sorted(pool, key=lambda e: -math.dist(e.pos, origin))
        elif sort not in ("arbitrary",):
            raise Unsupported("sort %s" % sort)
        if kind == "p":
            limit = 1
        if limit is not None:
            pool = pool[:limit]
        return pool

    # -- scores
    def holder(self, h, ctx):
        if h == "@s":
            if ctx.executor is None:
                raise Failed("@s with no executor")
            return "e%d" % ctx.executor.uid
        if h.startswith("@"):
            raise Unsupported("score holder %s" % h)
        return h

    def get_score(self, h, obj, ctx):
        key = (self.holder(h, ctx), obj)
        if obj not in self.objectives:
            raise Failed("no objective %s" % obj)
        if key not in self.scores:
            raise Failed("no score %s %s" % key)
        return self.scores[key]

    def set_score(self, h, obj, v, ctx):
        if obj not in self.objectives:
            raise Failed("no objective %s" % obj)
        self.scores[(self.holder(h, ctx), obj)] = int(v)

    # -- storage
    def storage_get(self, sid, path, record=True):
        cur = self.storage.get(sid, {})
        for key in split_path(path):
            if isinstance(key, int):
                if not isinstance(cur, list):
                    raise Failed("not a list at %s" % path)
                if record:
                    self.lookups.append((path, key, len(cur)))
                if not -len(cur) <= key < len(cur):
                    self.errors.append("index out of bounds: %s (length %d)" % (path, len(cur)))
                    raise Failed("index out of bounds")
                cur = cur[key]
            else:
                if not isinstance(cur, dict) or key not in cur:
                    self.errors.append("no data at %s %s" % (sid, path))
                    raise Failed("no data")
                cur = cur[key]
        return cur

    def storage_set(self, sid, path, value):
        keys = split_path(path)
        cur = self.storage.setdefault(sid, {})
        for key in keys[:-1]:
            if isinstance(key, int):
                raise Unsupported("set through a list index")
            cur = cur.setdefault(key, {})
        cur[keys[-1]] = value

    # -- positions
    def coords(self, toks, ctx):
        out = []
        for i, t in enumerate(toks):
            if t.startswith("~"):
                out.append(ctx.pos[i] + (float(t[1:]) if len(t) > 1 else 0.0))
            elif t.startswith("^"):
                raise Unsupported("local coordinates")
            else:
                out.append(float(t))
        return tuple(out)

    # -- commands
    def command(self, line, ctx, from_macro=False):
        head, _, rest = line.partition(" ")
        f = getattr(self, "c_" + head, None)
        if f is None:
            raise Unsupported("command %r" % line)
        if head == "spawnpokemonat":
            return f(rest, ctx, from_macro)
        return f(rest, ctx)

    def c_return(self, rest, ctx):
        raise Return(int(rest))

    def c_function(self, rest, ctx):
        # `with storage <id> [<path>]`: the path is optional (FunctionCommand: no path takes the whole compound)
        m = re.match(r"(\S+)(?:\s+with\s+storage\s+(\S+)(?:\s+(\S+))?|\s+(\{.*\}))?\s*$", rest)
        if not m:
            raise Unsupported("function %r" % rest)
        name, sid, path, inline = m.groups()
        args = None
        if sid:
            if path is None:
                if sid not in self.storage:
                    self.errors.append("no data at %s" % sid)
                    raise Failed("no data")
                args = self.storage[sid]
            else:
                args = self.storage_get(sid, path)
            if not isinstance(args, dict):
                raise Failed("macro arguments not a compound")
        elif inline:
            args = snbt(inline)
        return self.function(name, ctx, args)

    def c_scoreboard(self, rest, ctx):
        t = rest.split()
        if t[0] == "objectives" and t[1] == "add":
            self.objectives.add(t[2])
            return 1
        if t[0] != "players":
            raise Unsupported("scoreboard %s" % rest)
        op = t[1]
        if op == "get":
            return self.get_score(t[2], t[3], ctx)
        if op in ("set", "add", "remove"):
            key_h, obj, v = t[2], t[3], int(t[4])
            if obj not in self.objectives:
                raise Failed("no objective")
            holders = [self.holder(key_h, ctx)]
            for h in holders:
                cur = self.scores.get((h, obj), 0)
                self.scores[(h, obj)] = v if op == "set" else cur + v if op == "add" else cur - v
            return self.scores[(holders[0], obj)]
        if op == "operation":
            a, ao, o, b, bo = t[2:7]
            if o not in ("=", "+="):
                raise Unsupported("operation %s" % o)
            v = self.get_score(b, bo, ctx)
            if o == "+=":
                v += self.get_score(a, ao, ctx)
            self.set_score(a, ao, v, ctx)
            return v
        raise Unsupported("scoreboard players %s" % op)

    def c_tag(self, rest, ctx):
        sel, verb, name = rest.split()
        ents = self.select(sel, ctx)
        n = 0
        for e in ents:
            if verb == "add" and name not in e.tags:
                e.tags.add(name)
                n += 1
            elif verb == "remove" and name in e.tags:
                e.tags.discard(name)
                n += 1
        if not n:
            raise Failed("tag changed nothing")
        return n

    def c_data(self, rest, ctx):
        t = rest.split(" ", 3)
        if t[0] == "merge" and t[1] == "entity":
            ents = self.select(t[2], ctx)
            if len(ents) != 1:
                raise Failed("data merge needs one entity")
            ents[0].nbt.update(snbt(t[3]))
            return 1
        if t[0] == "modify" and t[1] == "storage":
            sid, rest2 = t[2], t[3]
            path, verb, how, val = rest2.split(" ", 3)
            if (verb, how) != ("set", "value"):
                raise Unsupported("data modify %s %s" % (verb, how))
            self.storage_set(sid, path, snbt(val))
            return 1
        if t[0] == "remove" and t[1] == "entity":
            ents = self.select(t[2], ctx)
            if len(ents) != 1 or t[3] not in ents[0].nbt:
                raise Failed("nothing to remove")
            del ents[0].nbt[t[3]]
            return 1
        if t[0] == "get" and t[1] == "entity":
            ents = self.select(t[2], ctx)
            if len(ents) != 1:
                raise Failed("data get needs one entity")
            parts = t[3].split()
            cur = ents[0].nbt
            for k in split_path(parts[0]):
                if not isinstance(cur, dict) or k not in cur:
                    raise Failed("no data")
                cur = cur[k]
            scale = float(parts[1]) if len(parts) > 1 else 1.0
            return int(math.floor(cur * scale))
        raise Unsupported("data %s" % rest)

    def c_effect(self, rest, ctx):
        t = rest.split()
        if t[0] != "give":
            raise Unsupported("effect %s" % rest)
        ents = self.select(t[1], ctx)
        for e in ents:
            e.effects[t[2]] = (t[3], int(t[4]) if len(t) > 4 else 0)
        if not ents:
            raise Failed("no target")
        return len(ents)

    def c_summon(self, rest, ctx):
        m = re.match(r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(\{.*\}))?$", rest)
        etype, x, y, z, data = m.groups()
        e = Entity(etype, self.coords([x, y, z], ctx))
        d = snbt(data) if data else {}
        e.tags |= set(d.pop("Tags", []))
        if "item" in d:
            e.item = str(d["item"]["id"])
        e.nbt.update(d)
        self.entities.append(e)
        self._log((self.tick_no, "summon", e))
        return 1

    def c_tp(self, rest, ctx):
        t = rest.split()
        ents = self.select(t[0], ctx)
        pos = self.coords(t[1:4], ctx)
        rot = None
        if len(t) >= 6:
            rot = (float(t[4]) if not t[4].startswith("~") else ctx.rot[0], float(t[5]) if not t[5].startswith("~") else ctx.rot[1])
        for e in ents:
            e.pos = list(pos)
            if rot:
                e.rot = list(rot)
            self._log((self.tick_no, "tp", (e, tuple(pos), rot)))
        if not ents:
            raise Failed("no entity")
        return len(ents)

    def c_kill(self, rest, ctx):
        ents = self.select(rest.strip(), ctx)
        for e in ents:
            e.alive = False
            self._log((self.tick_no, "kill", e))
        if not ents:
            raise Failed("no entity")
        return len(ents)

    def c_item(self, rest, ctx):
        m = re.match(r"replace entity (\S+) contents with (\S+)$", rest)
        if not m:
            raise Unsupported("item %s" % rest)
        ents = self.select(m.group(1), ctx)
        for e in ents:
            e.item = m.group(2)
            self._log((self.tick_no, "item", (e, m.group(2))))
        if not ents:
            raise Failed("no entity")
        return len(ents)

    def c_playsound(self, rest, ctx):
        t = rest.split()
        name, _source, sel = t[0], t[1], t[2]
        pos = self.coords(t[3:6], ctx) if len(t) >= 6 else ctx.pos
        hearers = self.select(sel, ctx)
        for p in hearers:
            p.heard.append((self.tick_no, name, pos))
        self._log((self.tick_no, "playsound", (name, pos, [p.uid for p in hearers])))
        if not hearers:
            raise Failed("no player heard it")
        return len(hearers)

    def c_particle(self, rest, ctx):
        m = re.match(r"(\S+?(?:\{.*\})?)\s+(\S+)\s+(\S+)\s+(\S+)", rest)
        name = m.group(1)
        pos = self.coords([m.group(2), m.group(3), m.group(4)], ctx)
        self._log((self.tick_no, "particle", (name, pos)))
        return 1

    def c_tellraw(self, rest, ctx):
        sel, _, text = rest.partition(" ")
        ents = self.select(sel, ctx)
        for e in ents:
            e.messages.append(json.loads(text))
        if not ents:
            raise Failed("no player")
        return len(ents)

    def c_fill(self, rest, ctx):
        t = rest.split()
        a = self.coords(t[0:3], ctx)
        b = self.coords(t[3:6], ctx)
        if not (self.loaded(a[0], a[2]) and self.loaded(b[0], b[2])):
            self.errors.append("fill into an unloaded chunk: %s" % rest)
            raise Failed("unloaded")
        self._log((self.tick_no, "fill", (a, b, t[6:])))
        return 1

    def c_forceload(self, rest, ctx):
        t = rest.split()
        x0, z0 = int(t[1]), int(t[2])
        x1, z1 = (int(t[3]), int(t[4])) if len(t) > 3 else (x0, z0)
        chunks = {(cx, cz) for cx in range(min(x0, x1) // 16, max(x0, x1) // 16 + 1)
                  for cz in range(min(z0, z1) // 16, max(z0, z1) // 16 + 1)}
        if t[0] == "add":
            self.forced |= chunks
        else:
            self.forced -= chunks
        return len(chunks)

    def c_spawnpokemonat(self, rest, ctx, from_macro):
        if not from_macro:
            self._log((self.tick_no, "inert_spawn", rest))
            return 0
        t = rest.split()
        pos = self.coords(t[0:3], ctx)
        species = t[3]
        props = dict(p.split("=", 1) if "=" in p else (p, True) for p in t[4:])
        e = Entity("cobblemon:pokemon", pos, nbt={"Pokemon": {"Species": species, "Level": int(props.get("level", 1))}})
        if props.get("no_ai"):
            e.nbt["NoAI"] = 1
        if props.get("uncatchable"):
            e.nbt["Uncatchable"] = 1
        self.entities.append(e)
        self._log((self.tick_no, "spawn", e))
        return 1

    def c_rctmod(self, rest, ctx):
        m = re.match(r"player get level_cap (\S+)$", rest)
        if not m:
            raise Unsupported("rctmod %s" % rest)
        ents = self.select(m.group(1), ctx)
        if len(ents) != 1 or ents[0].uid not in self.rct_cap:
            raise Failed("no cap")
        return int(self.rct_cap[ents[0].uid])

    # -- execute
    def c_execute(self, rest, ctx):
        toks = rest.split(" ")
        return self._execute(toks, 0, ctx, [])

    def _execute(self, toks, i, ctx, stores):
        """Run execute's subcommands from toks[i] in context ctx; stores are (kind, target...) to write the result."""
        total = 0
        while i < len(toks):
            t = toks[i]
            if t == "run":
                cmd = " ".join(toks[i + 1:])
                try:
                    r, ok = self.command(cmd, ctx), True
                except Failed:
                    r, ok = 0, False
                self._store(stores, ctx, r, ok)
                return r
            if t == "as":
                ents = self.select(toks[i + 1], ctx)
                for e in ents:
                    total += self._execute(toks, i + 2, ctx.but(executor=e), stores) or 0
                return total
            if t == "at":
                ents = self.select(toks[i + 1], ctx)
                for e in ents:
                    total += self._execute(toks, i + 2, ctx.but(pos=tuple(e.pos), rot=tuple(e.rot)), stores) or 0
                return total
            if t == "positioned":
                ctx = ctx.but(pos=self.coords(toks[i + 1:i + 4], ctx))
                i += 4
                continue
            if t == "on":
                if toks[i + 1] != "target":
                    raise Unsupported("on %s" % toks[i + 1])
                who = (ctx.executor.nbt.get("interaction") or {}).get("player") if ctx.executor else None
                tgt = [e for e in self.entities if e.alive and e.uid == who]
                if not tgt:
                    return 0
                ctx = ctx.but(executor=tgt[0])
                i += 2
                continue
            if t == "store":
                what, kind = toks[i + 1], toks[i + 2]
                if kind == "score":
                    stores = stores + [(what, "score", toks[i + 3], toks[i + 4])]
                    i += 5
                elif kind == "storage":
                    stores = stores + [(what, "storage", toks[i + 3], toks[i + 4], toks[i + 5], float(toks[i + 6]))]
                    i += 7
                else:
                    raise Unsupported("store %s" % kind)
                continue
            if t in ("if", "unless"):
                want = t == "if"
                kind = toks[i + 1]
                if kind == "score":
                    h, o = toks[i + 2], toks[i + 3]
                    if toks[i + 4] == "matches":
                        lo, hi = _range(toks[i + 5])
                        try:
                            ok = lo <= self.get_score(h, o, ctx) <= hi
                        except Failed:
                            ok = False
                        n = 6
                    else:
                        op, h2, o2 = toks[i + 4], toks[i + 5], toks[i + 6]
                        try:
                            a, b = self.get_score(h, o, ctx), self.get_score(h2, o2, ctx)
                            ok = {"<": a < b, "<=": a <= b, "=": a == b, ">": a > b, ">=": a >= b}[op]
                        except Failed:
                            ok = False
                        n = 7
                    count = 1 if ok else 0
                elif kind == "entity":
                    count = len(self.select(toks[i + 2], ctx))
                    n = 3
                elif kind == "loaded":
                    x, y, z = self.coords(toks[i + 2:i + 5], ctx)
                    count = 1 if self.loaded(x, z) else 0
                    n = 5
                elif kind == "block":
                    x, y, z = self.coords(toks[i + 2:i + 5], ctx)
                    # an unloaded chunk matches no block (vanilla: the test fails, not errors)
                    count = 1 if self.loaded(x, z) and \
                        self.block_at(x, y, z).split("[")[0] == toks[i + 5].split("[")[0] else 0
                    n = 6
                elif kind == "data" and toks[i + 2] == "entity":
                    ents = self.select(toks[i + 3], ctx)
                    count = 1 if len(ents) == 1 and toks[i + 4] in ents[0].nbt else 0
                    n = 5
                else:
                    raise Unsupported("execute if %s" % kind)
                passed = (count > 0) == want
                if i + n >= len(toks):                      # a trailing condition is the result
                    r = (count if kind == "entity" and want else 1) if passed else 0
                    self._store(stores, ctx, r, passed)
                    return r
                if not passed:
                    return 0
                i += n
                continue
            raise Unsupported("execute %s" % t)
        return total

    def _store(self, stores, ctx, r, ok):
        for s in stores:
            v = (r if ok else 0) if s[0] == "result" else (1 if ok else 0)
            if s[1] == "score":
                self.set_score(s[2], s[3], v, ctx)
            else:
                _w, _k, sid, path, typ, scale = s
                if typ != "int":
                    raise Unsupported("store type %s" % typ)
                self.storage_set(sid, path, int(math.floor(v * scale)))


# ------------------------------------------------------------------------------------------------ a world of real cells
# Added 2026-10-14 by the test author for the rip scheduler's independent audit (tools/dungeon_draw_audit.py, pack
# cobblers_rips). World above keeps no blocks (it reads its own write log); CellWorld keeps every cell a command writes, so
# a test can ask whether a world was given back EXACTLY. Written from vanilla 1.21.1 semantics, not from any generator.
# World is untouched: every existing user keeps its behaviour.

MODIFICATION_LIMIT = 32768        # gamerule commandModificationBlockLimit's default (fill, clone)


def _box(a, b):
    return tuple(int(math.floor(min(a[i], b[i]))) for i in range(3)), tuple(int(math.floor(max(a[i], b[i]))) for i in range(3))


def _cells(lo, hi):
    for x in range(lo[0], hi[0] + 1):
        for y in range(lo[1], hi[1] + 1):
            for z in range(lo[2], hi[2] + 1):
                yield (x, y, z)


class CellWorld(World):
    """World with a block in every cell and the commands that move them, as vanilla runs them:

      setblock x y z <block> [replace|keep|destroy]   fails (nothing written) in an unloaded chunk or when the cell already
                                                      holds the block (vanilla "Could not set the block")
      fill <from> <to> <block> [replace [<filter>]|keep|destroy]   every chunk of the box must be loaded; at most
                                                      MODIFICATION_LIMIT cells; fails when no cell changed
      clone <from> <to> <dest> [replace|masked] [normal|force|move]   source and destination must be loaded; a source and
                                                      destination that overlap fail in normal mode; the source is read
                                                      whole BEFORE anything is written; fails when no cell changed
      schedule function <f> <n>[t|s|d] [append|replace] / schedule clear <f>   run by advance(), as the server at spawn
      random value|roll <lo>..<hi>                    random_hook(lo, hi, function) decides (seeded rng by default)
      return run <command> / return fail
      execute ... in <dimension> ...                  accepted; this world has ONE dimension (a selector does not filter by
                                                      dimension), so a player meant to be elsewhere is placed far away
      @a/@e[scores={obj=range,...}]                   a holder with no score on the objective does not match
      scoreboard players reset <holder> [<objective>]

    A block is an opaque string, compared whole: a block state or a block entity's data written into it ("minecraft:chest
    [facing=north]{Items:[..]}") is kept by a clone and lost by anything else. `terrain(x, y, z)` is what a cell holds before
    any write. `entity_delay`: ticks after a chunk becomes force-loaded before the entities saved in it can be selected
    (vanilla loads a chunk's entities apart from its blocks; tools/chunk_look.py). 0 = at once. An entity summoned into a
    loaded chunk is there at once."""

    def __init__(self, functions, terrain=None, seed=1, entity_delay=0, **kw):
        super().__init__(functions, **kw)
        import random as _random
        self.cells = {}
        if terrain is not None:
            self.terrain = terrain
        self.rng = _random.Random(seed)
        self.random_hook = lambda lo, hi, fn: self.rng.randint(lo, hi)
        self.scheduled = []              # [due tick, sequence, function]
        self._seq = 0
        self.entity_delay = entity_delay
        self.forced_since = {}
        self.writes = []                 # (tick, function, kind, lo, hi): every write that landed

    # -- cells
    def block_at(self, x, y, z):
        c = (int(math.floor(x)), int(math.floor(y)), int(math.floor(z)))
        return self.cells[c] if c in self.cells else self.terrain(*c)

    def set_cell(self, c, block):
        self.cells[c] = block

    def chunks_loaded(self, lo, hi):
        return all(self.loaded(cx * 16, cz * 16) for cx in range(lo[0] // 16, hi[0] // 16 + 1)
                   for cz in range(lo[2] // 16, hi[2] // 16 + 1))

    def _landed(self, kind, lo, hi):
        self.writes.append((self.tick_no, self.stack[-1] if self.stack else None, kind, lo, hi))

    def c_setblock(self, rest, ctx):
        t = rest.split()
        c = tuple(int(math.floor(v)) for v in self.coords(t[0:3], ctx))
        block, mode = t[3], (t[4] if len(t) > 4 else "replace")
        if not self.chunks_loaded(c, c):
            self.errors.append("setblock into an unloaded chunk: %s" % rest)
            raise Failed("unloaded")
        if mode not in ("replace", "keep", "destroy"):
            raise Unsupported("setblock mode %s" % mode)
        if (mode == "keep" and self.block_at(*c) != "minecraft:air") or self.block_at(*c) == block:
            raise Failed("could not set the block")
        self.set_cell(c, block)
        self._log((self.tick_no, "setblock", rest))
        self._landed("setblock", c, c)
        return 1

    def c_fill(self, rest, ctx):
        t = rest.split()
        lo, hi = _box(self.coords(t[0:3], ctx), self.coords(t[3:6], ctx))
        block, mode = t[6], (t[7] if len(t) > 7 else "replace")
        filt = t[8] if mode == "replace" and len(t) > 8 else None
        if mode not in ("replace", "keep", "destroy"):
            raise Unsupported("fill mode %s" % mode)
        n = (hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1) * (hi[2] - lo[2] + 1)
        if n > MODIFICATION_LIMIT:
            self.errors.append("fill of %d cells: %s" % (n, rest))
            raise Failed("too many blocks")
        if not self.chunks_loaded(lo, hi):
            self.errors.append("fill into an unloaded chunk: %s" % rest)
            raise Failed("unloaded")
        changed = 0
        for c in _cells(lo, hi):
            have = self.block_at(*c)
            if filt and have.split("[")[0].split("{")[0] != filt.split("[")[0]:
                continue
            if mode == "keep" and have != "minecraft:air":
                continue
            if have != block:
                self.set_cell(c, block)
                changed += 1
        self._log((self.tick_no, "fill", (lo, hi, t[6:])))
        if not changed:
            raise Failed("no blocks were filled")
        self._landed("fill", lo, hi)
        return changed

    def c_clone(self, rest, ctx):
        t = rest.split()
        if t[0] == "from" or "to" in t[:12]:
            raise Unsupported("clone across dimensions: %s" % rest)
        lo, hi = _box(self.coords(t[0:3], ctx), self.coords(t[3:6], ctx))
        d = tuple(int(math.floor(v)) for v in self.coords(t[6:9], ctx))
        mask = t[9] if len(t) > 9 else "replace"
        how = t[10] if len(t) > 10 else "normal"
        if mask not in ("replace", "masked") or how not in ("normal", "force", "move"):
            raise Unsupported("clone %s %s" % (mask, how))
        size = tuple(hi[i] - lo[i] for i in range(3))
        dhi = tuple(d[i] + size[i] for i in range(3))
        n = (size[0] + 1) * (size[1] + 1) * (size[2] + 1)
        if n > MODIFICATION_LIMIT:
            self.errors.append("clone of %d cells: %s" % (n, rest))
            raise Failed("too many blocks")
        if how == "normal" and all(lo[i] <= dhi[i] and d[i] <= hi[i] for i in range(3)):
            self.errors.append("clone source and destination overlap: %s" % rest)
            raise Failed("overlap")
        if not (self.chunks_loaded(lo, hi) and self.chunks_loaded(d, dhi)):
            self.errors.append("clone with an unloaded chunk: %s" % rest)
            raise Failed("unloaded")
        src = {c: self.block_at(*c) for c in _cells(lo, hi)}
        changed = 0
        if how == "move":
            for c in src:
                if self.block_at(*c) != "minecraft:air":
                    self.set_cell(c, "minecraft:air")
        for (x, y, z), b in src.items():
            if mask == "masked" and b == "minecraft:air":
                continue
            c = (x - lo[0] + d[0], y - lo[1] + d[1], z - lo[2] + d[2])
            if self.block_at(*c) != b:
                changed += 1
            self.set_cell(c, b)
        self._log((self.tick_no, "clone", (lo, hi, d)))
        if not changed:
            raise Failed("no blocks were cloned")
        self._landed("clone", d, dhi)
        return changed

    # -- chunks and the entities in them
    def c_forceload(self, rest, ctx):
        t = rest.split()
        if t[0] == "query":
            raise Unsupported("forceload query")
        x0, z0 = int(float(t[1])), int(float(t[2]))
        x1, z1 = (int(float(t[3])), int(float(t[4]))) if len(t) > 3 else (x0, z0)
        chunks = {(cx, cz) for cx in range(min(x0, x1) // 16, max(x0, x1) // 16 + 1)
                  for cz in range(min(z0, z1) // 16, max(z0, z1) // 16 + 1)}
        if t[0] == "add":
            for ch in chunks - self.forced:
                if not self._loaded(ch[0] * 16, ch[1] * 16):
                    self.forced_since[ch] = self.tick_no
                    for e in self.entities:
                        if e.type != "minecraft:player" and (math.floor(e.pos[0]) // 16, math.floor(e.pos[2]) // 16) == ch:
                            e.visible_from = self.tick_no + self.entity_delay
            new = chunks - self.forced
            self.forced |= chunks
            if not new:
                raise Failed("no chunks were marked for force loading")
            return len(new)
        gone = chunks & self.forced
        self.forced -= chunks
        if not gone:
            raise Failed("no chunks were removed from force loading")
        return len(gone)

    def c_summon(self, rest, ctx):
        r = super().c_summon(rest, ctx)
        self.entities[-1].visible_from = self.tick_no
        return r

    def select(self, sel, ctx, single=False):
        want = None
        m = re.match(r"@([aepsr])\[(.*)\]$", sel)
        if m:
            args = _args(m.group(2))
            sc = [v for k, v in args if k == "scores"]
            if sc:
                want = [tuple(p.split("=", 1)) for p in sc[0].strip("{}").split(",") if p]
                rest = [("%s=%s" % (k, v)) for k, v in args if k != "scores"]
                sel = "@%s%s" % (m.group(1), "[%s]" % ",".join(rest) if rest else "")
        got = [e for e in super().select(sel, ctx, single)
               if e.type == "minecraft:player" or self.tick_no >= getattr(e, "visible_from", 0)]
        if want:
            def ok(e):
                for obj, rng in want:
                    v = self.scores.get(("e%d" % e.uid, obj))
                    lo, hi = _range(rng)
                    if v is None or not lo <= v <= hi:
                        return False
                return True
            got = [e for e in got if ok(e)]
        return got

    # -- scores, return, random, schedule, execute in
    def c_scoreboard(self, rest, ctx):
        t = rest.split()
        if t[0] == "players" and t[1] == "reset":
            h = self.holder(t[2], ctx)
            for key in [k for k in self.scores if k[0] == h and (len(t) < 4 or k[1] == t[3])]:
                del self.scores[key]
            return 1
        return super().c_scoreboard(rest, ctx)

    def c_return(self, rest, ctx):
        rest = rest.strip()
        if rest.startswith("run "):
            try:
                v = self.command(rest[4:], ctx)
            except Failed:
                v = 0
            raise Return(int(v or 0))
        if rest == "fail":
            raise Return(0)
        return super().c_return(rest, ctx)

    def c_random(self, rest, ctx):
        t = rest.split()
        if t[0] not in ("value", "roll"):
            raise Unsupported("random %s" % rest)
        lo, hi = (int(v) for v in t[1].split(".."))
        return int(self.random_hook(lo, hi, self.stack[-1] if self.stack else None))

    def c_schedule(self, rest, ctx):
        t = rest.split()
        if t[0] == "clear":
            n = len([s for s in self.scheduled if s[2] == t[1]])
            self.scheduled = [s for s in self.scheduled if s[2] != t[1]]
            if not n:
                raise Failed("nothing scheduled")
            return n
        if t[0] != "function":
            raise Unsupported("schedule %s" % rest)
        name, when = t[1], t[2]
        mode = t[3] if len(t) > 3 else "replace"
        n = int(float(when[:-1]) * {"t": 1, "s": 20, "d": 24000}[when[-1]]) if when[-1] in "tsd" else int(when)
        if n <= 0:
            raise Failed("schedule time must be positive")
        if name not in self.functions:
            raise Failed("unknown function %s" % name)
        if mode == "replace":
            self.scheduled = [s for s in self.scheduled if s[2] != name]
        self._seq += 1
        self.scheduled.append([self.tick_no + n, self._seq, name])
        return self.tick_no + n

    def advance(self, ticks):
        """Run the scheduled functions due in the next `ticks` ticks, in order (due tick, then the order they were
        scheduled), each as the server; the tick tag runs every tick if the pack has one."""
        end = self.tick_no + ticks
        while True:
            due = [s for s in self.scheduled if s[0] <= end]
            if self.tags.get("tick"):
                if self.tick_no >= end:
                    return
                self.tick_no += 1
                for f in self.tags["tick"]:
                    self.function(f, self.server())
            elif not due:
                self.tick_no = end
                return
            else:
                self.tick_no = max(self.tick_no, min(s[0] for s in due))
            now = sorted((s for s in self.scheduled if s[0] <= self.tick_no), key=lambda s: (s[0], s[1]))
            for s in now:
                if s in self.scheduled:
                    self.scheduled.remove(s)
                    self.function(s[2], self.server())

    def c_execute(self, rest, ctx):
        toks = rest.split(" ")
        out, i = [], 0
        while i < len(toks):
            if toks[i] == "run":
                out += toks[i:]
                break
            if toks[i] == "in":
                i += 2
                continue
            out.append(toks[i])
            i += 1
        return self._execute(out, 0, ctx, [])
