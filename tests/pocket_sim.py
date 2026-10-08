"""A dimension-aware Minecraft 1.21.1 command interpreter for per-player pocket-dimension packs (first: Entei).

Written by the test author from vanilla semantics, NOT from tools/entei_boss.py, for tests/test_entei_boss_audit.py.
tests/mcfunction_sim.py has no dimensions and models only `=` among scoreboard operations; a pack whose safety rests
on WHICH dimension a selector searches needs both. What this one models:

  dimensions  every entity is in one; `execute in` sets the context's. A selector with a positional argument
              (x/y/z/dx/dy/dz/distance) searches only the context's dimension; one without searches every dimension
              (EXP-047 result 4). `@s` is never dimension-checked: EntitySelector tests the current entity against
              its predicate alone, so `@s[x=..,dx=..]` is a coordinate test only.
  boxes       dx/dy/dz select an entity whose bounding box meets [x, x+dx+1) x [y, y+dy+1) x [z, z+dz+1)
              (EntitySelectorParser.createAabb); players are 0.6 x 1.8.
  players     online / offline (an offline player is in no selector and their scores stay), dead (still in @a, not
              in @e), gamemode, advancements, an inventory of [item id, components, count] stacks.
  loading     a non-player entity is selectable, and killable, only while an online player is in its dimension
              within LOAD_RANGE blocks (x and z) or its chunk is force-loaded; otherwise it is frozen where it is.
  scoreboard  set / add / remove / get / operation (= += -= *= /= %= < > ><; /= and %= floored). `operation`
              creates a missing target AND source score at 0 (getOrCreatePlayerScore); `get` of a missing score
              fails; `if|unless score` with a missing score is false for `if` and true for `unless`; int32 wrap.
  execute     as / at / in / positioned (x y z | as <sel>) / if|unless score (matches | = < <= > >=) / if|unless
              entity / store result score|storage / run; `return <n>` and `return run <cmd>` end the function.
  functions   `function f`, `function f {snbt}`, `function f with storage <id> <path>`; a function with any `$`
              line is a macro and fails whole without arguments or with one it lacks (MacroFunction).
  and         time query gametime, advancement grant|revoke @s only, give, loot give, tellraw, tp (absolute, ~,
              yaw pitch), kill, tag add, effect give, data get entity <t> Pos[i] [scale], data merge|remove entity,
              schedule function, summon interaction, fill / setblock (recorded), forceload add|remove, and
              spawnpokemonat, which spawns only from a macro line (EXP-046: a plain line parsed at load does nothing).

Unmodelled commands raise Unsupported, so a construct this interpreter does not know fails the test instead of passing.
What it does NOT model: block collision and falling, chunk-load latency, battles (tests drive the callbacks), and
anything Cobblemon does between a ball hitting and the capture callback.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import mcfunction_sim as MS  # noqa: E402  (only its SNBT reader)
import nbt_sim as N  # noqa: E402  (only its MoLang reader)

LOAD_RANGE = 128
SPAWN = ("minecraft:overworld", (0.5, 64.0, 0.5))
INT_MIN, INT_MAX = -2 ** 31, 2 ** 31 - 1


class Unsupported(Exception):
    pass


class Failed(Exception):
    pass


class Return(Exception):
    def __init__(self, value):
        self.value = value


def wrap(v):
    return (v - INT_MIN) % 2 ** 32 + INT_MIN


def tokens(cmd):
    """Split at spaces outside brackets, braces and quotes."""
    out, cur, depth, q, i = [], "", 0, None, 0
    while i < len(cmd):
        ch = cmd[i]
        if q:
            cur += ch
            if ch == "\\" and i + 1 < len(cmd):
                cur += cmd[i + 1]
                i += 2
                continue
            if ch == q:
                q = None
            i += 1
            continue
        if ch in "\"'":
            q = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == " " and depth == 0:
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    if cur:
        out.append(cur)
    return out


def split_top(body, sep=","):
    out, cur, depth, q, i = [], "", 0, None, 0
    while i < len(body):
        ch = body[i]
        if q:
            cur += ch
            if ch == "\\" and i + 1 < len(body):
                cur += body[i + 1]
                i += 2
                continue
            if ch == q:
                q = None
            i += 1
            continue
        if ch in "\"'":
            q = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    if cur:
        out.append(cur)
    return out


def parse_item(text):
    """`id[comp=snbt,...]` -> (id, {comp: value}) with values as plain Python (SNBT floats and ints as numbers)."""
    m = re.fullmatch(r"([a-z0-9_.\-]+:[a-z0-9_/.\-]+)(?:\[(.*)\])?", text, re.S)
    if not m:
        raise Unsupported("item %r" % text)
    comps = {}
    for part in split_top(m.group(2) or ""):
        k, _, v = part.partition("=")
        comps[k] = plain(MS.snbt(v))
    return m.group(1), comps


def plain(v):
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [plain(x) for x in v]
    if isinstance(v, str):
        return str(v)
    return v


def same_components(a, b):
    """Component maps equal, numbers compared as numbers (SNBT 1 for true, 0.0f for 0.0)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same_components(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same_components(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return int(a) == int(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-9
    return a == b


class Ent:
    _n = 0

    def __init__(self, kind, dim, pos, name=None, tags=(), nbt=None, props=()):
        Ent._n += 1
        self.uid = "00000000-0000-0000-0000-%012d" % Ent._n
        self.kind = kind                    # "player", "cobblemon:pokemon", "minecraft:interaction"
        self.dim, self.pos = dim, [float(v) for v in pos]
        self.name = name
        self.tags = set(tags)
        self.nbt = dict(nbt or {})
        self.props = set(props)
        self.alive, self.online, self.dead = True, True, False
        self.gamemode = "survival"
        self.advancements = set()
        self.inventory = []
        self.party = []
        self.effects = []
        self.messages = []
        self.yaw = 0.0

    @property
    def holder(self):
        return self.name if self.kind == "player" else self.uid

    def aabb(self):
        w, h = (0.3, 1.8) if self.kind == "player" else (0.5, 1.5)
        x, y, z = self.pos
        return (x - w, y, z - w, x + w, y + h, z + w)

    def __repr__(self):
        return "<%s %s %s %s>" % (self.kind, self.name or self.uid[-4:], self.dim, [round(v, 2) for v in self.pos])


class Ctx:
    __slots__ = ("ent", "dim", "pos", "yaw")

    def __init__(self, ent, dim, pos, yaw=0.0):
        self.ent, self.dim, self.pos, self.yaw = ent, dim, tuple(pos), yaw

    def but(self, **kw):
        c = Ctx(self.ent, self.dim, self.pos, self.yaw)
        for k, v in kw.items():
            setattr(c, k, tuple(v) if k == "pos" else v)
        return c


def _range(spec):
    if ".." in spec:
        a, b = spec.split("..")
        return (float(a) if a else -math.inf, float(b) if b else math.inf)
    return (float(spec), float(spec))


class World:
    def __init__(self, pack_dir, extra_functions=None):
        self.pack = Path(pack_dir)
        self.functions, self.advs, self.loot, self.callbacks = {}, {}, {}, {}
        for p in self.pack.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(self.pack).as_posix()
            m = re.fullmatch(r"data/([^/]+)/function/(.+)\.mcfunction", rel)
            if m:
                self.functions["%s:%s" % (m.group(1), m.group(2))] = p.read_text(encoding="utf-8").splitlines()
            m = re.fullmatch(r"data/([^/]+)/advancement/(.+)\.json", rel)
            if m:
                self.advs["%s:%s" % (m.group(1), m.group(2))] = json.loads(p.read_text(encoding="utf-8"))
            m = re.fullmatch(r"data/([^/]+)/loot_table/(.+)\.json", rel)
            if m:
                self.loot["%s:%s" % (m.group(1), m.group(2))] = json.loads(p.read_text(encoding="utf-8"))
            m = re.fullmatch(r"data/cobblemon/callbacks/([^/]+)/[^/]+\.molang", rel)
            if m:
                self.callbacks.setdefault(m.group(1), []).append(N.Molang(p.read_text(encoding="utf-8")))
        self.functions.update(extra_functions or {})
        self.ents = []
        self.scores = {}
        self.objectives = set()
        self.storage = {}
        self.gametime = 1_000_000
        self.scheduled = {}
        self.forced = {}
        self.block_writes = []
        self.calls, self.spawned, self.log = [], [], []
        self.rolls = []             # loot rolls: each an index into the pool's entries; empty -> the first

    # ---- the world --------------------------------------------------------------------------------------------
    def player(self, name, dim, pos, advancements=()):
        p = Ent("player", dim, pos, name=name)
        p.advancements |= set(advancements)
        self.ents.append(p)
        return p

    def players(self):
        return [e for e in self.ents if e.kind == "player"]

    def loaded(self, e):
        if e.kind == "player":
            return e.online
        cx, cz = int(math.floor(e.pos[0])) >> 4, int(math.floor(e.pos[2])) >> 4
        if (cx, cz) in self.forced.get(e.dim, set()):
            return True
        return any(p.online and p.dim == e.dim and abs(p.pos[0] - e.pos[0]) <= LOAD_RANGE
                   and abs(p.pos[2] - e.pos[2]) <= LOAD_RANGE for p in self.players())

    def server_ctx(self):
        return Ctx(None, SPAWN[0], SPAWN[1])

    def boot(self):
        """A server start: every load-tagged function, as the server. Schedules from before are gone."""
        self.scheduled = {}
        tag = self.pack / "data" / "minecraft" / "tags" / "function" / "load.json"
        for f in json.loads(tag.read_text(encoding="utf-8"))["values"]:
            self.call(f, self.server_ctx())

    def tick(self, n=1):
        for _ in range(n):
            self.gametime += 1
            for f, due in sorted(self.scheduled.items()):
                if due <= self.gametime:
                    del self.scheduled[f]
                    self.call(f, self.server_ctx())

    # ---- scores -------------------------------------------------------------------------------------------------
    def get(self, holder, obj):
        return self.scores.get((holder, obj))

    def set(self, holder, obj, v):
        if obj not in self.objectives:
            raise Failed("unknown objective %s" % obj)
        self.scores[(holder, obj)] = wrap(int(v))

    def holders(self, h, ctx):
        if h == "@s":
            if ctx.ent is None:
                raise Failed("@s with no entity")
            return [ctx.ent.holder]
        if h.startswith("@"):
            found = self.select(h, ctx)
            if not found:
                raise Failed("no holder %s" % h)
            return [e.holder for e in found]
        return [h]

    # ---- selectors ------------------------------------------------------------------------------------------
    def select(self, sel, ctx):
        if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", sel):
            return [e for e in self.ents if e.uid == sel and e.alive and self.loaded(e)
                    and not (e.kind == "player" and e.dead)]
        m = re.fullmatch(r"@([aesp])(?:\[(.*)\])?", sel, re.S)
        if not m:
            raise Unsupported("selector %r" % sel)
        kind, body = m.group(1), m.group(2) or ""
        args = []
        for a in split_top(body):
            k, _, v = a.partition("=")
            args.append((k.strip(), v.strip()))
        keys = {k for k, _ in args}
        unknown = keys - {"x", "y", "z", "dx", "dy", "dz", "distance", "type", "tag", "gamemode", "advancements",
                          "nbt", "limit", "sort"}
        if unknown:
            raise Unsupported("selector arguments %s" % unknown)
        positional = bool(keys & {"x", "y", "z", "dx", "dy", "dz", "distance"})
        ox, oy, oz = ctx.pos
        for k, v in args:
            if k == "x":
                ox = float(v)
            elif k == "y":
                oy = float(v)
            elif k == "z":
                oz = float(v)
        if kind == "s":
            pool = [ctx.ent] if ctx.ent is not None and ctx.ent.alive else []
        elif kind in "ap":
            pool = [e for e in self.ents if e.kind == "player" and e.online]
        else:
            pool = [e for e in self.ents if e.alive and self.loaded(e) and not (e.kind == "player" and e.dead)]
        if positional and kind != "s":
            pool = [e for e in pool if e.dim == ctx.dim]
        d = {k: float(v) for k, v in args if k in ("dx", "dy", "dz")}
        box = None
        if d:
            x0, y0, z0 = ox, oy, oz
            x1, y1, z1 = ox + d.get("dx", 0) + 1, oy + d.get("dy", 0) + 1, oz + d.get("dz", 0) + 1
            box = (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1))
        out = []
        for e in pool:
            ok = True
            for k, v in args:
                if k == "type":
                    neg = v.startswith("!")
                    t = v.lstrip("!")
                    t = t if ":" in t else "minecraft:" + t
                    et = "minecraft:player" if e.kind == "player" else e.kind
                    ok = (et != t) if neg else (et == t)
                elif k == "tag":
                    ok = (v[1:] not in e.tags) if v.startswith("!") else (v in e.tags if v else not e.tags)
                elif k == "gamemode":
                    if e.kind != "player":
                        ok = False
                    else:
                        ok = (e.gamemode != v[1:]) if v.startswith("!") else (e.gamemode == v)
                elif k == "advancements":
                    if e.kind != "player":
                        ok = False
                    else:
                        for part in split_top(v.strip("{}")):
                            aid, _, want = part.rpartition("=")
                            if (aid in e.advancements) != (want == "true"):
                                ok = False
                elif k == "nbt":
                    want = plain(MS.snbt(v))
                    ok = MS._nbt_match(want, e.nbt)
                elif k == "distance":
                    lo, hi = _range(v)
                    dist = math.dist((ox, oy, oz), e.pos)
                    ok = lo <= dist <= hi
                if not ok:
                    break
            if ok and box is not None:
                a = e.aabb()
                ok = a[0] < box[3] and a[3] > box[0] and a[1] < box[4] and a[4] > box[1] and a[2] < box[5] and a[5] > box[2]
            if ok:
                out.append(e)
        sort = dict(args).get("sort")
        if sort in ("nearest", "furthest"):
            out.sort(key=lambda e: math.dist((ox, oy, oz), e.pos), reverse=sort == "furthest")
        lim = dict(args).get("limit")
        if kind == "p":
            out.sort(key=lambda e: math.dist((ox, oy, oz), e.pos))
            lim = lim or "1"
        if lim:
            out = out[:int(lim)]
        return out

    def one(self, sel, ctx):
        found = self.select(sel, ctx)
        if len(found) != 1:
            raise Failed("%s found %d" % (sel, len(found)))
        return found[0]

    # ---- functions ------------------------------------------------------------------------------------------
    def call(self, name, ctx, args=None):
        if name not in self.functions:
            raise AssertionError("function %s is called but the pack does not define it" % name)
        lines = self.functions[name]
        macro = any(l.startswith("$") for l in lines)
        if macro and args is None:
            raise Failed("macro %s called without arguments" % name)
        body = []
        for line in lines:
            if not line.strip() or line.startswith("#"):
                continue
            if line.startswith("$"):
                def sub(m):
                    if m.group(1) not in args:
                        raise Failed("macro %s lacks %s" % (name, m.group(1)))
                    return MS.render(args[m.group(1)])
                body.append((re.sub(r"\$\(([A-Za-z0-9_]+)\)", sub, line[1:]), True))
            else:
                body.append((line, False))
        self.calls.append((name, ctx.ent.name if ctx.ent is not None and ctx.ent.kind == "player" else None))
        try:
            for line, from_macro in body:
                try:
                    self.run(line, ctx, from_macro)
                except Failed:
                    pass
        except Return as r:
            return r.value
        return 0

    def run(self, cmd, ctx, from_macro=False):
        t = tokens(cmd)
        return self.run_tokens(t, ctx, from_macro, cmd)

    def run_tokens(self, t, ctx, from_macro=False, raw=None):
        h = t[0]
        if h == "execute":
            return self.execute(t[1:], ctx, from_macro)
        if h == "return":
            if t[1] == "run":
                try:
                    v = self.run_tokens(t[2:], ctx, from_macro)
                except Failed:
                    v = 0
                raise Return(v)
            raise Return(int(t[1]))
        if h == "function":
            return self.function_cmd(t, ctx)
        if h == "scoreboard":
            return self.scoreboard(t, ctx)
        if h == "time" and t[1:] == ["query", "gametime"]:
            return self.gametime % 2147483647
        if h == "advancement":
            if t[2] != "@s" or t[3] != "only":
                raise Unsupported(" ".join(t))
            e = ctx.ent
            if e is None or e.kind != "player":
                raise Failed("advancement on a non-player")
            (e.advancements.add if t[1] == "grant" else e.advancements.discard)(t[4])
            return 1
        if h == "give":
            n = int(t[3]) if len(t) > 3 else 1
            item, comps = parse_item(t[2])
            for e in self.select(t[1], ctx):
                e.inventory.append([item, comps, n])
            return 1
        if h == "loot" and t[1] == "give" and t[3] == "loot":
            table = self.loot[t[4]]
            for e in self.select(t[2], ctx):
                for pool in table["pools"]:
                    for _ in range(int(pool["rolls"])):
                        i = self.rolls.pop(0) if self.rolls else 0
                        entry = pool["entries"][i]
                        n = 1
                        for f in entry.get("functions", []):
                            if f["function"] == "minecraft:set_count":
                                n = int(f["count"])
                        e.inventory.append([entry["name"], {}, n])
            return 1
        if h == "tellraw":
            for e in self.select(t[1], ctx):
                e.messages.append(" ".join(t[2:]))
            return 1
        if h == "tp":
            targets = self.select(t[1], ctx)
            if not targets:
                raise Failed("tp: no target")
            for e in targets:
                pos = []
                for i, c in enumerate(t[2:5]):
                    pos.append(ctx.pos[i] + float(c[1:] or 0) if c.startswith("~") else float(c))
                e.dim, e.pos = ctx.dim, pos
                if len(t) > 5:
                    e.yaw = float(t[5])
            return len(targets)
        if h == "kill":
            found = self.select(t[1], ctx)
            for e in found:
                if e.kind == "player":
                    e.dead = True
                else:
                    e.alive = False
            if not found:
                raise Failed("kill: nothing")
            return len(found)
        if h == "tag" and t[2] == "add":
            for e in self.select(t[1], ctx):
                e.tags.add(t[3])
            return 1
        if h == "effect" and t[1] == "give":
            for e in self.select(t[2], ctx):
                e.effects.append((t[3], int(t[4]), int(t[5])))
            return 1
        if h == "data":
            if t[1] == "get" and t[2] == "entity":
                e = self.one(t[3], ctx)
                m = re.fullmatch(r"Pos\[(\d)\]", t[4])
                if not m:
                    raise Unsupported(" ".join(t))
                scale = float(t[5]) if len(t) > 5 else 1.0
                return int(math.floor(e.pos[int(m.group(1))] * scale))
            if t[1] == "merge" and t[2] == "entity":
                e = self.one(t[3], ctx)
                e.nbt.update(plain(MS.snbt(t[4])))
                return 1
            if t[1] == "remove" and t[2] == "entity":
                self.one(t[3], ctx)
                return 1
            raise Unsupported(" ".join(t))
        if h == "schedule" and t[1] == "function":
            self.scheduled[t[2]] = self.gametime + int(t[3].rstrip("t"))
            return 1
        if h == "summon":
            pos = [ctx.pos[i] + float(c[1:] or 0) if c.startswith("~") else float(c) for i, c in enumerate(t[2:5])]
            nbt = plain(MS.snbt(t[5])) if len(t) > 5 else {}
            e = Ent(t[1], ctx.dim, pos, tags=nbt.get("Tags", ()), nbt=nbt)
            self.ents.append(e)
            return 1
        if h in ("fill", "setblock"):
            self.block_writes.append((ctx.dim, " ".join(t)))
            return 1
        if h == "forceload":
            xs = [int(v) for v in t[2:]]
            x0, z0 = xs[0], xs[1]
            x1, z1 = (xs[2], xs[3]) if len(xs) > 2 else (x0, z0)
            chunks = {(cx, cz) for cx in range(min(x0, x1) >> 4, (max(x0, x1) >> 4) + 1)
                      for cz in range(min(z0, z1) >> 4, (max(z0, z1) >> 4) + 1)}
            s = self.forced.setdefault(ctx.dim, set())
            if t[1] == "add":
                s |= chunks
            else:
                s -= chunks
            return 1
        if h == "spawnpokemonat":
            if not from_macro:
                self.log.append("inert_spawn " + " ".join(t))
                return 0
            pos = [ctx.pos[i] + float(c[1:] or 0) if c.startswith("~") else float(c) for i, c in enumerate(t[1:4])]
            species = t[4] if ":" in t[4] else "cobblemon:" + t[4]
            props = t[5:]
            level = next((int(p.split("=")[1]) for p in props if p.startswith("level=")), 1)
            e = Ent("cobblemon:pokemon", ctx.dim, pos, nbt={"Pokemon": {"Species": species, "Level": level,
                                                                       "PokemonOriginalTrainerType": "NONE"}},
                    props=props)
            self.ents.append(e)
            self.spawned.append(e)
            return 1
        raise Unsupported("command %r" % " ".join(t))

    def function_cmd(self, t, ctx):
        name = t[1]
        if len(t) == 2:
            return self.call(name, ctx)
        if t[2] == "with" and t[3] == "storage":
            src = self.storage.get(t[4], {})
            for part in t[5].split("."):
                if not isinstance(src, dict) or part not in src:
                    raise Failed("no storage %s %s" % (t[4], t[5]))
                src = src[part]
            return self.call(name, ctx, dict(src))
        if t[2].startswith("{"):
            return self.call(name, ctx, MS.snbt(t[2]))
        raise Unsupported(" ".join(t))

    def scoreboard(self, t, ctx):
        if t[1] == "objectives" and t[2] == "add":
            self.objectives.add(t[3])
            return 1
        if t[1] != "players":
            raise Unsupported(" ".join(t))
        op = t[2]
        if op in ("set", "add", "remove"):
            n = int(t[5])
            for hd in self.holders(t[3], ctx):
                cur = self.get(hd, t[4]) or 0
                self.set(hd, t[4], n if op == "set" else cur + n if op == "add" else cur - n)
            return 1
        if op == "get":
            (hd,) = self.holders(t[3], ctx)
            v = self.get(hd, t[4])
            if v is None:
                raise Failed("no score %s %s" % (hd, t[4]))
            return v
        if op == "operation":
            tgt, tobj, o, src, sobj = t[3], t[4], t[5], t[6], t[7]
            for th in self.holders(tgt, ctx):
                for sh in self.holders(src, ctx):
                    a = self.get(th, tobj)
                    a = 0 if a is None else a
                    b = self.get(sh, sobj)
                    if b is None:
                        b = 0
                        self.set(sh, sobj, 0)
                    if o == "=":
                        a = b
                    elif o == "+=":
                        a += b
                    elif o == "-=":
                        a -= b
                    elif o == "*=":
                        a *= b
                    elif o in ("/=", "%="):
                        if b == 0:
                            raise Failed("divide by zero")
                        a = a // b if o == "/=" else a % b
                    elif o == "<":
                        a = min(a, b)
                    elif o == ">":
                        a = max(a, b)
                    elif o == "><":
                        self.set(sh, sobj, a)
                        a = b
                    else:
                        raise Unsupported(o)
                    self.set(th, tobj, a)
            return 1
        raise Unsupported(" ".join(t))

    def execute(self, t, ctx, from_macro):
        ctxs, stores, i = [ctx], [], 0
        while i < len(t):
            w = t[i]
            if w == "run":
                total = 0
                for c in ctxs:
                    try:
                        r, ok = self.run_tokens(t[i + 1:], c, from_macro), True
                    except Failed:
                        r, ok = 0, False
                    for st in stores:
                        self.store(st, c, r if ok else 0)
                    total += r
                return total
            if w == "as":
                ctxs = [c.but(ent=e) for c in ctxs for e in self.select(t[i + 1], c)]
                i += 2
            elif w == "at":
                ctxs = [c.but(dim=e.dim, pos=e.pos, yaw=e.yaw) for c in ctxs for e in self.select(t[i + 1], c)]
                i += 2
            elif w == "in":
                ctxs = [c.but(dim=t[i + 1]) for c in ctxs]
                i += 2
            elif w == "positioned":
                if t[i + 1] == "as":
                    ctxs = [c.but(pos=e.pos) for c in ctxs for e in self.select(t[i + 2], c)]
                    i += 3
                else:
                    new = []
                    for c in ctxs:
                        new.append(c.but(pos=[c.pos[k] + float(v[1:] or 0) if v.startswith("~") else float(v)
                                              for k, v in enumerate(t[i + 1:i + 4])]))
                    ctxs = new
                    i += 4
            elif w in ("if", "unless"):
                want = w == "if"
                kind = t[i + 1]
                if kind == "score":
                    if t[i + 4] == "matches":
                        lo, hi = _range(t[i + 5])

                        def pred(c, h=t[i + 2], o=t[i + 3], lo=lo, hi=hi):
                            hs = self.holders(h, c)
                            v = self.get(hs[0], o)
                            return v is not None and lo <= v <= hi
                        i += 6
                    else:
                        def pred(c, h=t[i + 2], o=t[i + 3], op=t[i + 4], h2=t[i + 5], o2=t[i + 6]):
                            a = self.get(self.holders(h, c)[0], o)
                            b = self.get(self.holders(h2, c)[0], o2)
                            if a is None or b is None:
                                return False
                            return {"=": a == b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
                        i += 7
                elif kind == "entity":
                    def pred(c, s=t[i + 2]):
                        return bool(self.select(s, c))
                    i += 3
                else:
                    raise Unsupported("execute %s %s" % (w, kind))
                kept = []
                for c in ctxs:
                    try:
                        r = pred(c)
                    except Failed:
                        r = False
                    if r == want:
                        kept.append(c)
                ctxs = kept
            elif w == "store":
                if t[i + 1] != "result":
                    raise Unsupported("execute store %s" % t[i + 1])
                if t[i + 2] == "score":
                    stores.append(("score", t[i + 3], t[i + 4]))
                    i += 5
                elif t[i + 2] == "storage":
                    stores.append(("storage", t[i + 3], t[i + 4], t[i + 5], float(t[i + 6])))
                    i += 7
                else:
                    raise Unsupported("execute store result %s" % t[i + 2])
            else:
                raise Unsupported("execute %s" % w)
        raise Unsupported("execute without run: %s" % " ".join(t))

    def store(self, st, ctx, value):
        if st[0] == "score":
            for hd in self.holders(st[1], ctx):
                self.set(hd, st[2], value)
        else:
            _, sid, path, typ, scale = st
            if typ != "int":
                raise Unsupported("store type %s" % typ)
            node = self.storage.setdefault(sid, {})
            parts = path.split(".")
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = int(math.floor(value * scale))

    # ---- what a player does (each drives only the vanilla or Cobblemon hook, never a pack function by name) -------
    def _criterion_item(self, adv):
        (crit,) = adv["criteria"].values()
        return crit

    def eat(self, p, index):
        """The player finishes eating the stack at `index`. Player.eat fires minecraft:consume_item (granting any
        advancement it matches, whose reward runs at once as the player) BEFORE LivingEntity.eat shrinks the stack."""
        stack = p.inventory[index]
        if "minecraft:food" not in stack[1]:
            raise AssertionError("not edible: %r" % (stack,))
        for aid, adv in self.advs.items():
            crit = adv.get("criteria", {})
            for c in crit.values():
                if c.get("trigger") != "minecraft:consume_item":
                    continue
                want = c.get("conditions", {}).get("item", {})
                if want.get("items") not in (None, stack[0]):
                    continue
                if not all(same_components(v, stack[1].get(k)) for k, v in want.get("components", {}).items()):
                    continue
                if aid not in p.advancements:
                    p.advancements.add(aid)
                    fn = adv.get("rewards", {}).get("function")
                    if fn:
                        self.call(fn, Ctx(p, p.dim, p.pos, p.yaw))
        stack[2] -= 1
        p.inventory = [s for s in p.inventory if s[2] > 0]

    def click(self, p, reach=3.0):
        """The player right-clicks the nearest interaction entity within reach in their dimension."""
        near = [e for e in self.ents if e.kind == "minecraft:interaction" and e.alive and e.dim == p.dim
                and math.dist(e.pos, p.pos) <= reach]
        if not near:
            return False
        target = min(near, key=lambda e: math.dist(e.pos, p.pos))
        for aid, adv in self.advs.items():
            for c in adv.get("criteria", {}).values():
                if c.get("trigger") != "minecraft:player_interacted_with_entity":
                    continue
                ok = True
                for cond in c.get("conditions", {}).get("entity", []):
                    pr = cond.get("predicate", {})
                    if pr.get("type") and pr["type"] != target.kind:
                        ok = False
                    if pr.get("nbt") and not set(MS.snbt(pr["nbt"]).get("Tags", [])) <= target.tags:
                        ok = False
                if ok and aid not in p.advancements:
                    p.advancements.add(aid)
                    fn = adv.get("rewards", {}).get("function")
                    if fn:
                        self.call(fn, Ctx(p, p.dim, p.pos, p.yaw))
        return True

    def run_callback(self, event, context=None, query=None):
        for mol in self.callbacks.get(event, []):
            for cmd in mol.run(context=context or {}, query=query or {}):
                try:
                    self.run(cmd, self.server_ctx())
                except Failed:
                    pass

    def catch(self, p, mon):
        """A ball from `p` captures `mon` (Cobblemon refuses an `uncatchable` one). Returns whether it was caught."""
        if "uncatchable" in mon.props or not mon.alive:
            return False
        mon.alive = False
        p.party.append(mon.nbt["Pokemon"]["Species"])
        self.run_callback("pokemon_captured", query={"pokemon": {"species": {"identifier": mon.nbt["Pokemon"]["Species"]}},
                                                     "player": {"uuid": p.uid}})
        return True

    def faint(self, p, mon, wild=True):
        """`mon` faints in a battle `p` is the first player of."""
        mon.alive = False
        self.run_callback("battle_fainted", context={
            "pokemon": {"actor": {"is_wild": 1 if wild else 0},
                        "pokemon": {"species": {"identifier": mon.nbt["Pokemon"]["Species"]}}},
            "players": [{"player": {"uuid": p.uid}}]})
