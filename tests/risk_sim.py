"""A command interpreter for the dungeon risk's generated functions (tools/dungeon_risk.py), from vanilla 1.21.1 semantics.

Written for tests/test_dungeon_risk.py. The engine's own harness (tests/rift_audit_sim.py) records the risk's five entry
points instead of running them; this one runs them, as generated, against a modelled player. It models only what the
risk emits, and raises Unsupported on anything else, so a new construct fails a test instead of passing it:

  storage     NBT paths with dotted and quoted keys, [n] and [-1], [] (every element), [{filter}] and a trailing
              {filter} on a compound; data modify set value|from, append value|from (every match), data remove,
              data get (a number, or a list's or a compound's size); if|unless data storage|entity; store result
              storage. NBT types are NOT kept (1b and 1 are the same here): a type mismatch the real game would
              refuse is not caught (the generator writes and reads its own values in one form; EXP-098 checks it)
  players     an inventory {slot: {id, count, components}} with slots 0..35, -106 (offhand), 100..103 (armour),
              its NBT view (Inventory, with Slot), UUID int array, dimension, position, money (cobbledollars give/
              query), a party and a PC of Pokemon {id, sp, held}, in_battle
  entities    item entities (Item, Thrower, Owner, PickupDelay, Age), a merchant (Offers.Recipes, CustomName)
  runmolang   the risk's two catch scripts only, read as MoLang would run them: the UUID the script compares, then
              the guard clauses it contains (in battle, a held item, the party's last); remove_by_id removes only
              when the script calls it. Its q.run_command is QUEUED, run by drain() (EXP-022)
"""
from __future__ import annotations

import copy
import json
import math
import re

import mcfunction_sim as MS


class Unsupported(Exception):
    pass


class Failed(Exception):
    pass


class Return(Exception):
    def __init__(self, v):
        self.v = v


def snbt(s):
    return MS.snbt(s)


def render(v):
    """A macro argument: a string bare, a number bare, a compound or list as SNBT."""
    if isinstance(v, str):
        return str(v)
    if isinstance(v, bool):
        return "1b" if v else "0b"
    if isinstance(v, (int, float)):
        return str(v)
    return to_snbt(v)


def to_snbt(v):
    if isinstance(v, dict):
        return "{" + ",".join("%s:%s" % (k if re.fullmatch(r"[A-Za-z0-9_]+", k) else json.dumps(k), to_snbt(x))
                              for k, x in v.items()) + "}"
    if isinstance(v, list):
        return "[" + ",".join(to_snbt(x) for x in v) + "]"
    if isinstance(v, str):
        return json.dumps(v)
    return str(v)


def match(want, have):
    if isinstance(want, dict):
        return isinstance(have, dict) and all(k in have and match(v, have[k]) for k, v in want.items())
    return want == have


def parse_path(path):
    """['key' | int | '[]' | ('filter', snbt)] with ('leaf', snbt) for a compound filter after a key."""
    out, i = [], 0
    while i < len(path):
        c = path[i]
        if c == ".":
            i += 1
            continue
        if c == '"':
            j = path.index('"', i + 1)
            out.append(path[i + 1:j])
            i = j + 1
            continue
        if c == "[":
            j, depth = i, 0
            while True:
                if path[j] in "[{":
                    depth += 1
                elif path[j] in "]}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            body = path[i + 1:j]
            if body == "":
                out.append("[]")
            elif body.startswith("{"):
                out.append(("filter", snbt(body)))
            else:
                out.append(int(body))
            i = j + 1
            continue
        if c == "{":
            j, depth = i, 0
            while True:
                if path[j] == "{":
                    depth += 1
                elif path[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out.append(("leaf", snbt(path[i:j + 1])))
            i = j + 1
            continue
        m = re.match(r"[A-Za-z0-9_\-]+", path[i:])
        if not m:
            raise Unsupported("nbt path %r" % path)
        out.append(m.group(0))
        i += len(m.group(0))
    return out


def resolve(root, path, create=False):
    """Every (container, key) the path names in root."""
    parts = parse_path(path)
    cur = [(None, None, root)]
    for n, p in enumerate(parts):
        last = n == len(parts) - 1
        nxt = []
        for _c, _k, v in cur:
            if isinstance(p, tuple) and p[0] == "leaf":
                if match(p[1], v):
                    nxt.append((_c, _k, v))
                continue
            if isinstance(p, str) and p != "[]":
                if not isinstance(v, dict):
                    continue
                if p not in v:
                    if not create:
                        continue
                    following = parts[n + 1] if n + 1 < len(parts) else None
                    v[p] = [] if (following == "[]" or isinstance(following, int)) else {}
                nxt.append((v, p, v[p]))
            elif p == "[]":
                if isinstance(v, list):
                    nxt += [(v, k, x) for k, x in enumerate(v)]
            elif isinstance(p, int):
                if isinstance(v, list) and -len(v) <= p < len(v):
                    nxt.append((v, p % len(v), v[p]))
            elif p[0] == "filter":
                if isinstance(v, list):
                    nxt += [(v, k, x) for k, x in enumerate(v) if match(p[1], x)]
        cur = nxt
    return [(c, k) for c, k, _v in cur if c is not None]


def get_all(root, path):
    return [c[k] for c, k in resolve(root, path)]


class Player:
    def __init__(self, name, n):
        self.name, self.kind = name, "player"
        self.uuid = [n, 2 * n, 3 * n, 4 * n]
        self.inv = {}
        self.tags = set()
        self.dim, self.pos, self.rot = "cobblers:pocket", [0.0, 100.0, 0.0], [0.0, 0.0]
        self.online, self.alive = True, True
        self.party, self.pc = [], []
        self.in_battle = False
        self.messages = []
        self.alive_entity = True

    @property
    def uid(self):
        return "%08x-0000-0000-0000-%012x" % (self.uuid[0], self.uuid[0])

    def nbt(self):
        return {"UUID": list(self.uuid),
                "Inventory": [dict(copy.deepcopy(v), Slot=k) for k, v in sorted(self.inv.items())]}


class Ent:
    def __init__(self, etype, dim, pos, nbt):
        self.kind, self.type, self.dim, self.pos = "entity", etype, dim, list(pos)
        self.nbt = nbt
        self.tags = set(nbt.pop("Tags", []))
        self.alive = True
        self.name = "%s@%s" % (etype, pos)


class Ctx:
    def __init__(self, ent, dim, pos, rot=(0.0, 0.0)):
        self.ent, self.dim, self.pos, self.rot = ent, dim, list(pos), list(rot)

    def but(self, **kw):
        c = Ctx(self.ent, self.dim, self.pos, self.rot)
        for k, v in kw.items():
            setattr(c, k, v)
        return c


SLOT_NAMES = {"weapon.offhand": -106, "armor.feet": 100, "armor.legs": 101, "armor.chest": 102, "armor.head": 103}


def item_pred(text):
    """`*[minecraft:custom_data~{k:1b}]` or `<id>[minecraft:custom_data~{k:1b}]` -> (id or None, {k: v})."""
    m = re.fullmatch(r"(\*|[a-z0-9_:]+)(?:\[minecraft:custom_data~(\{.*\})\])?", text)
    if not m:
        raise Unsupported("item predicate %r" % text)
    return (None if m.group(1) == "*" else m.group(1)), (snbt(m.group(2)) if m.group(2) else None)


def stack_ok(st, pred):
    iid, cd = pred
    if iid and st.get("id") != iid:
        return False
    if cd is not None:
        have = (st.get("components") or {}).get("minecraft:custom_data") or {}
        return match(cd, have)
    return True


def tokens(cmd):
    out, cur, depth, q = [], "", 0, None
    for ch in cmd:
        if q:
            cur += ch
            if ch == q and not cur.endswith("\\" + q):
                q = None
            continue
        if ch in "\"'":
            q = ch
            cur += ch
            continue
        if ch in "[{(":
            depth += 1
        elif ch in "]})":
            depth -= 1
        if ch == " " and depth == 0:
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


class World:
    def __init__(self, functions, ns="cobblers"):
        self.f = dict(functions)
        self.ns = ns
        self.players, self.ents = [], []
        self.storage, self.scores = {}, {}
        self.money = {}
        self.queue = []
        self.log = []
        self.pay_fails = False
        self.enabled = set()
        # item tags, as far as a test needs them (Cobblemon 1.8.2's data/cobblemon/tags/item/poke_balls.json, in part)
        self.item_tags = {"#cobblemon:poke_balls": {"cobblemon:poke_ball", "cobblemon:great_ball", "cobblemon:beast_ball"}}

    # ---- helpers -------------------------------------------------------------------------------------------
    def player(self, name="Ash"):
        p = Player(name, len(self.players) + 1)
        self.players.append(p)
        self.money[name] = 0
        return p

    def holder(self, h, ctx):
        if h == "@s":
            return [ctx.ent.name] if ctx.ent is not None else []
        if h.startswith("#"):
            return [h]
        return [e.name for e in self.select(h, ctx)]

    def get(self, h, o):
        return self.scores.get((h, o))

    def setv(self, h, o, v):
        self.scores[(h, o)] = int(v)

    def store(self, sid):
        return self.storage.setdefault(sid, {})

    def score(self, p, o):
        return self.scores.get((p.name, o))

    # ---- selectors ------------------------------------------------------------------------------------------
    def select(self, sel, ctx):
        m = re.fullmatch(r"@([saepr])(?:\[(.*)\])?", sel)
        if not m:
            raise Unsupported("selector %r" % sel)
        kind, args = m.group(1), MS._args(m.group(2) or "")
        if kind == "s":
            pool = [ctx.ent] if ctx.ent is not None else []
        elif kind in ("a", "p"):
            pool = [p for p in self.players if p.online]
        else:
            pool = [e for e in self.ents if e.alive] + [p for p in self.players if p.online and p.alive]
        out = []
        for e in pool:
            ok = True
            for k, v in args:
                if k == "type":
                    ok = ok and ((e.kind == "player" and v == "minecraft:player") or getattr(e, "type", None) == v)
                elif k == "tag":
                    ok = ok and ((v[1:] not in e.tags) if v.startswith("!") else (v in e.tags))
                elif k == "distance":
                    lo, hi = MS._range(v)
                    d = math.dist(e.pos, ctx.pos)
                    ok = ok and e.dim == ctx.dim and lo <= d <= hi
                elif k == "scores":
                    for part in v.strip("{}").split(","):
                        o, _, r = part.partition("=")
                        lo, hi = MS._range(r)
                        sv = self.get(e.name, o)
                        ok = ok and sv is not None and lo <= sv <= hi
                elif k == "limit":
                    pass
                else:
                    raise Unsupported("selector argument %s" % k)
            if ok:
                out.append(e)
        if kind == "p":
            out = sorted(out, key=lambda e: math.dist(e.pos, ctx.pos))[:1]
        lim = [int(v) for k, v in args if k == "limit"]
        return out[:lim[0]] if lim else out

    # ---- functions -----------------------------------------------------------------------------------------
    def call(self, name, ctx, args=None):
        if name not in self.f:
            raise AssertionError("function %s is called but not defined" % name)
        lines = self.f[name]
        if any(l.startswith("$") for l in lines) and args is None:
            raise Failed("macro without arguments")
        try:
            for ln in lines:
                if not ln.strip() or ln.startswith("#"):
                    continue
                if ln.startswith("$"):
                    def sub(m):
                        if m.group(1) not in args:
                            raise Failed("macro lacks %s" % m.group(1))
                        return render(args[m.group(1)])
                    ln = re.sub(r"\$\(([A-Za-z0-9_]+)\)", sub, ln[1:])
                try:
                    self.run(ln, ctx)
                except Failed:
                    pass
        except Return as r:
            return r.v
        return 0

    def as_player(self, p, name):
        return self.call(self.ns + ":dungeons/" + name, Ctx(p, p.dim, p.pos))

    def drain(self):
        while self.queue:
            cmd, ctx = self.queue.pop(0)
            self.run(cmd, ctx)

    def tick(self, n=1):
        for _ in range(n):
            self.call(self.ns + ":dungeons/risk/tick", Ctx(None, "minecraft:overworld", [0, 0, 0]))
            self.drain()

    # ---- commands ------------------------------------------------------------------------------------------
    def run(self, cmd, ctx):
        return self.run_t(tokens(cmd), ctx)

    def run_t(self, t, ctx):
        h = t[0]
        if h == "execute":
            return self.execute(t[1:], ctx)
        if h == "return":
            if t[1] == "run":
                try:
                    v = self.run_t(t[2:], ctx)
                except Failed:
                    v = 0
                raise Return(v)
            raise Return(int(t[1]) if t[1] != "fail" else 0)
        if h == "function":
            name = t[1]
            if len(t) == 2:
                return self.call(name, ctx)
            if t[2] == "with":
                vals = get_all(self.store(t[4]), t[5])
                if len(vals) != 1 or not isinstance(vals[0], dict):
                    raise Failed("with: no compound")
                return self.call(name, ctx, vals[0])
            return self.call(name, ctx, snbt(" ".join(t[2:])))
        if h == "scoreboard":
            return self.scoreboard(t, ctx)
        if h == "data":
            return self.data(t, ctx)
        if h in ("tellraw", "title", "playsound"):
            for e in self.select(t[1], ctx) if h != "playsound" else []:
                e.messages.append((h, " ".join(t[2:])))
            if h == "playsound":
                return 1
            return 1
        if h == "tag":
            for e in self.select(t[1], ctx):
                (e.tags.add if t[2] == "add" else e.tags.discard)(t[3])
            return 1
        if h == "kill":
            found = self.select(t[1], ctx)
            if not found:
                raise Failed("kill nothing")
            for e in found:
                e.alive = False
            return len(found)
        if h == "summon":
            if t[2:5] != ["~", "~", "~"] and t[2:5] != ["~", "~0.5", "~"]:
                raise Unsupported("summon at %s" % t[2:5])
            nbt = snbt(" ".join(t[5:])) if len(t) > 5 else {}
            pos = list(ctx.pos)
            e = Ent(t[1], ctx.dim, pos, nbt)
            self.ents.append(e)
            return 1
        if h == "tp":
            return 1
        if h == "item" and t[1] == "replace" and t[2] == "entity" and t[5:] == ["with", "minecraft:air"]:
            n = 0
            for e in self.select(t[3], ctx):
                slot = t[4]
                k = int(slot.split(".")[1]) if slot.startswith("container.") else SLOT_NAMES.get(slot)
                if k is None:
                    raise Unsupported("slot %s" % slot)
                e.inv.pop(k, None)
                n += 1
            return n
        if h == "clear":
            pred = item_pred(t[2])
            took = 0
            for e in self.select(t[1], ctx):
                for k in [k for k, st in e.inv.items() if stack_ok(st, pred)]:
                    took += e.inv.pop(k)["count"]
            if not took:
                raise Failed("clear nothing")
            return took
        if h == "give":
            return 1
        if h == "cobbledollars":
            p = self.select(t[2], ctx)[0]
            if t[1] == "query":
                return self.money[p.name]
            if t[1] == "give":
                if not self.pay_fails:
                    self.money[p.name] += int(t[3])
                return 1
        if h == "runmolang":
            return self.molang(t[1][1:-1], self.select(t[2], ctx)[0])
        raise Unsupported("command %r" % " ".join(t))

    def scoreboard(self, t, ctx):
        if t[1] == "objectives":
            return 1
        op = t[2]
        if op == "enable":
            for h in self.holder(t[3], ctx):
                self.enabled.add((h, t[4]))
            return 1
        if op == "get":
            v = self.get(self.holder(t[3], ctx)[0], t[4])
            if v is None:
                raise Failed("no score")
            return v
        if op in ("set", "add", "remove"):
            n = 0
            for hd in self.holder(t[3], ctx):
                cur = self.get(hd, t[4]) or 0
                v = int(t[5])
                self.setv(hd, t[4], v if op == "set" else cur + v if op == "add" else cur - v)
                n += 1
            return n
        if op == "reset":
            for hd in self.holder(t[3], ctx):
                self.scores.pop((hd, t[4]), None)
            return 1
        if op == "operation":
            src = self.get(self.holder(t[6], ctx)[0], t[7]) or 0
            for hd in self.holder(t[3], ctx):
                a = self.get(hd, t[4]) or 0
                o = t[5]
                r = {"=": src, "+=": a + src, "-=": a - src, "*=": a * src,
                     "/=": (a // src) if src else a, "%=": (a % src) if src else a}[o]
                self.setv(hd, t[4], r)
            return 1
        raise Unsupported("scoreboard %s" % t)

    def nbt_of(self, kind, target, ctx):
        if kind == "storage":
            return self.store(target)
        es = self.select(target, ctx)
        if len(es) != 1:
            raise Failed("entity target")
        e = es[0]
        return e.nbt() if e.kind == "player" else e.nbt

    def data(self, t, ctx):
        if t[1] == "get":
            vals = get_all(self.nbt_of(t[2], t[3], ctx), t[4])
            if len(vals) != 1:
                raise Failed("data get: %d" % len(vals))
            v = vals[0]
            if isinstance(v, (dict, list, str)):
                return len(v)
            return int(math.floor(v))
        if t[1] == "remove":
            root = self.nbt_of(t[2], t[3], ctx)
            hits = resolve(root, t[4])
            if not hits:
                raise Failed("remove nothing")
            for c, k in sorted(hits, key=lambda ck: -ck[1] if isinstance(ck[1], int) else 0):
                del c[k]
            return len(hits)
        if t[1] == "modify":
            kind, target, path, op = t[2], t[3], t[4], t[5]
            if kind == "entity":
                es = self.select(target, ctx)
                if len(es) != 1 or es[0].kind == "player":
                    raise Failed("data modify entity")
            root = self.nbt_of(kind, target, ctx)
            if t[6] == "value":
                vals = [snbt(" ".join(t[7:]))]
            elif t[6] == "from":
                vals = copy.deepcopy(get_all(self.nbt_of(t[7], t[8], ctx), t[9]))
                if not vals:
                    raise Failed("from nothing")
            else:
                raise Unsupported("data modify %s" % t[6])
            if op == "set":
                if len(vals) != 1:
                    raise Failed("set: many")
                parts = parse_path(path)
                head = ".".join(p if isinstance(p, str) and re.fullmatch(r"[A-Za-z0-9_\-]+", p) else
                                ('"%s"' % p if isinstance(p, str) else "[%d]" % p) for p in parts[:-1])
                parent = [root] if not head else [c[k] for c, k in resolve(root, head, create=True)]
                if not parent or not isinstance(parts[-1], (str, int)):
                    raise Failed("set: no parent")
                for pv in parent:
                    pv[parts[-1]] = copy.deepcopy(vals[0])
                return 1
            if op == "append":
                lists = [c[k] for c, k in resolve(root, path, create=True)]
                if not lists or not isinstance(lists[0], list):
                    raise Failed("append: not a list")
                lists[0].extend(copy.deepcopy(vals))
                return len(vals)
            raise Unsupported("data modify op %s" % op)
        raise Unsupported("data %s" % t[1])

    def execute(self, t, ctx):
        ctxs, stores, i = [ctx], [], 0
        while i < len(t):
            w = t[i]
            if w == "run":
                total = 0
                for c in ctxs:
                    try:
                        r, ok = self.run_t(t[i + 1:], c), True
                    except Failed:
                        r, ok = 0, False
                    for st in stores:
                        v = (1 if ok else 0) if st[0] == "success" else (r if ok else 0)
                        if st[1] == "score":
                            for hd in self.holder(st[2], c):
                                self.setv(hd, st[3], v)
                        else:
                            root = self.store(st[2])
                            parts = st[3].rsplit(".", 1)
                            parent = [root] if len(parts) == 1 else [cc[k] for cc, k in resolve(root, parts[0], create=True)]
                            for pv in parent:
                                pv[parts[-1]] = int(v * st[5])
                    total += r
                return total
            if w == "as":
                ctxs = [c.but(ent=e) for c in ctxs for e in self.select(t[i + 1], c)]
                i += 2
            elif w == "at":
                ctxs = [c.but(dim=e.dim, pos=list(e.pos), rot=list(getattr(e, "rot", [0, 0])))
                        for c in ctxs for e in self.select(t[i + 1], c)]
                i += 2
            elif w == "rotated":
                i += 3
            elif w == "positioned":
                i += 4
            elif w in ("if", "unless"):
                want, kind = w == "if", t[i + 1]
                if kind == "score" and t[i + 4] == "matches":
                    lo, hi = MS._range(t[i + 5])

                    def pred(c, h=t[i + 2], o=t[i + 3], lo=lo, hi=hi):
                        hs = self.holder(h, c)
                        v = self.get(hs[0], o) if hs else None
                        return v is not None and lo <= v <= hi
                    i += 6
                elif kind == "score":
                    def pred(c, h=t[i + 2], o=t[i + 3], op=t[i + 4], h2=t[i + 5], o2=t[i + 6]):
                        a, b = self.get(self.holder(h, c)[0], o), self.get(self.holder(h2, c)[0], o2)
                        return a is not None and b is not None and {"=": a == b, "<": a < b, ">": a > b}[op]
                    i += 7
                elif kind == "entity":
                    def pred(c, s=t[i + 2]):
                        return bool(self.select(s, c))
                    i += 3
                elif kind == "dimension":
                    def pred(c, d=t[i + 2]):
                        return c.dim == d
                    i += 3
                elif kind == "data":
                    def pred(c, k=t[i + 2], tg=t[i + 3], path=t[i + 4]):
                        try:
                            return bool(get_all(self.nbt_of(k, tg, c), path))
                        except Failed:
                            return False
                    i += 5
                elif kind == "items" and t[i + 2] == "entity":
                    def pred(c, s=t[i + 3], slot=t[i + 4], it=t[i + 5]):
                        if slot == "contents":
                            if not it.startswith("#") or it not in self.item_tags:
                                raise Unsupported("contents predicate %r" % it)
                            return any(e.kind != "player" and (e.nbt.get("Item") or {}).get("id") in self.item_tags[it]
                                       for e in self.select(s, c))
                        p = item_pred(it)
                        for e in self.select(s, c):
                            if slot == "container.*":
                                ks = range(0, 36)
                            elif slot == "armor.*":
                                ks = range(100, 104)
                            elif slot == "weapon.mainhand":
                                ks = [0]
                            else:
                                ks = [SLOT_NAMES[slot]]
                            if any(k in e.inv and stack_ok(e.inv[k], p) for k in ks):
                                return True
                        return False
                    i += 6
                else:
                    raise Unsupported("execute if %s" % kind)
                ctxs = [c for c in ctxs if pred(c) == want]
            elif w == "store":
                stores.append((t[i + 1], t[i + 2], t[i + 3], t[i + 4],
                               t[i + 5] if t[i + 2] == "storage" else None,
                               float(t[i + 6]) if t[i + 2] == "storage" else 1))
                i += 7 if t[i + 2] == "storage" else 5
            else:
                raise Unsupported("execute %s" % w)
        if not ctxs:
            raise Failed("conditions")
        return len(ctxs)

    # ---- the two MoLang scripts ------------------------------------------------------------------------------
    def molang(self, script, p):
        m = re.search(r"t\.x\.id == '([^']+)'", script)
        if not m:
            raise Unsupported("runmolang %r" % script[:80])
        pid = m.group(1)
        where = 1 if any(x["id"] == pid for x in p.party) else 2 if any(x["id"] == pid for x in p.pc) else 0
        store = p.party if where == 1 else p.pc if where == 2 else []
        mon = next((x for x in store if x["id"] == pid), None)
        removes = "remove_by_id" in script
        o = where
        if removes:
            o = 0
            if where:
                if "q.player.in_battle == 1" in script and p.in_battle:
                    o = 6
                elif "t.e == 0" in script and mon.get("held"):
                    o = 5
                elif where == 1 and "q.player.party.count <= 1" in script and len(p.party) <= 1:
                    o = 7
                else:
                    store.remove(mon)
                    o = 3 if where == 1 else 4
        rx = re.compile(r"\(t\.%s == %d\) \? \{ q\.run_command\('execute as ' \+ q\.player\.uuid \+ '(.*?)'\); \};"
                        % ("o" if removes else "f", o))
        hit = rx.search(script)
        if hit is None and removes and o == 0:
            hit = re.search(r"\(t\.f == 0\) \? \{ q\.run_command\('execute as ' \+ q\.player\.uuid \+ '(.*?)'\); \};", script)
        if hit:
            self.queue.append(("execute as @s" + hit.group(1).replace(" at @s", " at @s", 1),
                               Ctx(p, p.dim, p.pos)))
        self.log.append(("molang", pid, o))
        return 1
