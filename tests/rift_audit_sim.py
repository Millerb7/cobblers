"""The test author's world for the dungeon engine audit: tests/pocket_sim.py plus the commands cobblers_dungeons uses.

Written for tests/test_dungeon_audit.py (and C24 in tests/test_system_contracts.py) from vanilla and Cobblemon
semantics, NOT from tools/dungeon.py and NOT from tests/test_dungeon.py's own extension of pocket_sim. Where it
models something the builder's harness also models, it was written separately, and differs on purpose in three places:

  items        custom_data values keep their NBT TYPE (`1b` is not `1`): a partial match `custom_data~{k:1b}`
               matches a byte only, as vanilla's NbtUtils.compareNbt does (EXP-083: the int form missed a crafted
               sigil). A crafted sigil is given as a byte (EXP-083 step 7).
  runmolang    `q.run_command(...)` runs AT ONCE, inside the runmolang (Cobblemon dispatches it synchronously), not
               queued for later.
  death        `kill` of a player marks them dead (out of @e, still in @a), adds 1 to every deathCount objective and
               records the tags they held at that instant, which is what the blackout reads (its death path runs on
               the death itself). `respawn()` brings them back in the overworld.

The blackout's run-tag functions (recovery/run_tail_end, run_tag_stale) are loaded verbatim from the generated
blackout pack; recovery/deliver is recorded (who, when, which dimension, which tags) instead of run, because what it
does is the blackout's own test (tests/test_dungeon_death.py, C24). cobblers:levelcap/battle_check is a no-op: a test
sets cobblers.lc_cap itself. Not modelled: battles (a test says who is in one), block collision, chunk loading of
NPCs beyond pocket_sim's rule, and anything Cobblemon does between a battle and its callback.
"""
from __future__ import annotations

import json
import re

import pocket_sim as PS

OW = "minecraft:overworld"
POCKET = "cobblers:pocket"
CHECKPOINT = (OW, (100.5, 70.0, 100.5))          # where the blackout returns a dead player (any overworld point)
TYPED = re.compile(r"([A-Za-z0-9_]+):(-?\d+)([bBsSlL]?)")
ITEM = re.compile(r"([a-z0-9_.\-]+:[a-z0-9_/.\-]+)(?:\[(.*)\])?$", re.S)


def typed_compound(snbt):
    """'{k:1b,j:2}' -> {'k': (1, 'b'), 'j': (2, '')}: numbers with their NBT type suffix."""
    return {m.group(1): (int(m.group(2)), m.group(3).lower()) for m in TYPED.finditer(snbt)}


def item_spec(text):
    """'id[minecraft:custom_data=|~{...},...]' -> (id, {key: (value, type)}, is_partial)."""
    m = ITEM.match(text)
    if not m:
        raise PS.Unsupported("item %r" % text)
    cd = re.search(r"minecraft:custom_data([~=])(\{[^}]*\})", m.group(2) or "")
    return m.group(1), (typed_compound(cd.group(2)) if cd else {}), bool(cd and cd.group(1) == "~")


def stack_matches(stack, pred):
    iid, want, _partial = pred
    return stack[0] == iid and all(stack[1].get(k) == v for k, v in want.items())


class RiftWorld(PS.World):
    def __init__(self, files, extra_functions=None):        # noqa: D401 - files, not a directory
        self.pack = None
        self.files = files
        self.functions, self.advs, self.loot, self.callbacks = {}, {}, {}, {}
        for rel, text in files.items():
            m = re.fullmatch(r"data/([^/]+)/function/(.+)\.mcfunction", rel)
            if m:
                self.functions["%s:%s" % (m.group(1), m.group(2))] = text.splitlines()
            m = re.fullmatch(r"data/([^/]+)/advancement/(.+)\.json", rel)
            if m:
                self.advs["%s:%s" % (m.group(1), m.group(2))] = json.loads(text)
        self.functions.update(extra_functions or {})
        self.ents, self.scores, self.objectives, self.storage = [], {}, set(), {}
        self.gametime, self.scheduled, self.forced = 1_000_000, {}, {}
        self.block_writes, self.calls, self.spawned, self.log, self.rolls = [], [], [], [], []
        self.death_objs, self.deaths, self.delivered, self.started = set(), [], [], []
        self.battle, self.caps, self.npcs, self.titles = set(), {}, [], []
        self.hooks = {}

    def boot(self):
        self.scheduled = {}
        for f in json.loads(self.files["data/minecraft/tags/function/load.json"])["values"]:
            self.call(f, self.server_ctx())

    # ---- players --------------------------------------------------------------------------------------------
    def die(self, p):
        p.dead = True
        for obj in self.death_objs:
            self.scores[(p.holder, obj)] = (self.get(p.holder, obj) or 0) + 1
        self.deaths.append({"t": self.gametime, "name": p.name, "tags": frozenset(p.tags), "dim": p.dim,
                            "pos": tuple(p.pos), "inv": [list(s) for s in p.inventory]})

    def respawn(self, p, where=CHECKPOINT):
        p.dead = False
        p.dim, p.pos = where[0], list(where[1])

    def give_item(self, p, text, n=1):
        iid, cd, _ = item_spec(text)
        p.inventory.append([iid, cd, n])

    def has(self, p, text):
        pred = item_spec(text)
        return sum(s[2] for s in p.inventory if stack_matches(s, pred))

    # ---- functions --------------------------------------------------------------------------------------------
    def call(self, name, ctx, args=None):
        if name in self.hooks:
            self.calls.append((name, ctx.ent.name if ctx.ent is not None and ctx.ent.kind == "player" else None))
            return self.hooks[name](self, ctx, args)
        return super().call(name, ctx, args)

    def select(self, sel, ctx):
        m = re.search(r",?scores=\{([^}]*)\}", sel)
        if not m:
            return super().select(sel, ctx)
        rest = sel.replace(m.group(0), "").replace("[,", "[").replace("[]", "")
        out = []
        for e in super().select(rest, ctx):
            ok = True
            for part in m.group(1).split(","):
                obj, _, rng = part.partition("=")
                lo, hi = PS._range(rng)
                v = self.get(e.holder, obj)
                ok = ok and v is not None and lo <= v <= hi
            if ok:
                out.append(e)
        return out

    def run_tokens(self, t, ctx, from_macro=False, raw=None):
        h = t[0]
        if h == "execute":
            return self.execute(t[1:], ctx, from_macro)
        if h == "scoreboard" and t[1:3] == ["objectives", "add"] and len(t) > 4 and t[4] == "deathCount":
            self.death_objs.add(t[3])
        if h == "tag" and t[2] == "remove":
            for e in self.select(t[1], ctx):
                e.tags.discard(t[3])
            return 1
        if h in ("title", "playsound", "particle", "ride", "recipe", "bossbar"):
            if h == "title":
                for e in self.select(t[1], ctx):
                    self.titles.append((self.gametime, e.name, t[2], " ".join(t[3:])))
            return 1
        if h == "gamemode":
            for e in self.select(t[2], ctx):
                e.gamemode = t[1]
            return 1
        if h == "give":
            iid, cd, _ = item_spec(t[2])
            for e in self.select(t[1], ctx):
                e.inventory.append([iid, cd, int(t[3]) if len(t) > 3 else 1])
            return 1
        if h == "clear":
            pred = item_spec(t[2])
            n = int(t[3]) if len(t) > 3 else 10 ** 9
            took = 0
            for e in self.select(t[1], ctx):
                for s in list(e.inventory):
                    if took < n and stack_matches(s, pred):
                        k = min(s[2], n - took)
                        s[2] -= k
                        took += k
                        if not s[2]:
                            e.inventory.remove(s)
            if not took:
                raise PS.Failed("clear: no items")
            return took
        if h == "kill":
            found = self.select(t[1], ctx)
            if not found:
                raise PS.Failed("kill: nothing")
            for e in found:
                if e.kind == "player":
                    self.die(e)
                else:
                    e.alive = False
            return len(found)
        if h == "runmolang":
            expr = t[1][1:-1]
            targets = self.select(t[2], ctx) if len(t) > 2 else ([ctx.ent] if ctx.ent is not None else [])
            if "q.entity.discard" in expr:
                for e in targets:
                    e.alive = False
                return 1
            if "start_battle" in expr:
                npcs = self.select(t[3], ctx)
                self.started.append((self.gametime, [e.name for e in targets], [e.uid for e in npcs]))
                return 1
            m = re.fullmatch(r"\(q\.player\.in_battle == 0\) \? \{ q\.run_command\('(.*?)' \+ q\.player\.uuid \+ '(.*?)'\); \};", expr)
            if not m:
                raise PS.Unsupported("runmolang %r" % expr)
            for p in targets:
                if p.name not in self.battle:
                    self.run(m.group(1) + p.uid + m.group(2), self.server_ctx())
            return 1
        if h == "spawnnpcat":
            if not from_macro:
                self.log.append("inert " + " ".join(t))
                return 0
            pos = [float(v) for v in t[1:4]]
            e = PS.Ent("cobblemon:npc", ctx.dim, pos, nbt={"cls": t[4], "level": int(t[5])})
            self.ents.append(e)
            self.npcs.append(e)
            return 1
        if h == "rctmod" and t[1:4] == ["player", "get", "level_cap"]:
            e = self.one(t[4], ctx)
            if e.name not in self.caps:
                raise PS.Failed("no cap")
            return self.caps[e.name]
        return super().run_tokens(t, ctx, from_macro, raw)

    def execute(self, t, ctx, from_macro):
        """vanilla `execute`: as / at / in / positioned / if|unless (score, entity, items) / store result (score,
        bossbar) / run; with no `run`, the conditions' result."""
        ctxs, stores, i = [ctx], [], 0
        while i < len(t):
            w = t[i]
            if w == "run":
                total = 0
                for c in ctxs:
                    try:
                        r, ok = self.run_tokens(t[i + 1:], c, from_macro), True
                    except PS.Failed:
                        r, ok = 0, False
                    for st in stores:
                        if st[0] == "score":
                            for hd in self.holders(st[1], c):
                                self.set(hd, st[2], r if ok else 0)
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
                ctxs = [c.but(pos=[c.pos[k] + float(v[1:] or 0) if v.startswith("~") else float(v)
                                   for k, v in enumerate(t[i + 1:i + 4])]) for c in ctxs]
                i += 4
            elif w in ("if", "unless"):
                want, kind = w == "if", t[i + 1]
                if kind == "score" and t[i + 4] == "matches":
                    lo, hi = PS._range(t[i + 5])

                    def pred(c, h=t[i + 2], o=t[i + 3], lo=lo, hi=hi):
                        v = self.get(self.holders(h, c)[0], o)
                        return v is not None and lo <= v <= hi
                    i += 6
                elif kind == "score":
                    def pred(c, h=t[i + 2], o=t[i + 3], op=t[i + 4], h2=t[i + 5], o2=t[i + 6]):
                        a, b = self.get(self.holders(h, c)[0], o), self.get(self.holders(h2, c)[0], o2)
                        if a is None or b is None:
                            return False
                        return {"=": a == b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
                    i += 7
                elif kind == "entity":
                    def pred(c, s=t[i + 2]):
                        return bool(self.select(s, c))
                    i += 3
                elif kind == "items" and t[i + 2] == "entity":
                    def pred(c, s=t[i + 3], slot=t[i + 4], it=t[i + 5]):
                        p = item_spec(it)
                        for e in self.select(s, c):
                            if slot == "armor.chest":
                                if any(x[0] == p[0] for x in getattr(e, "armor", [])):
                                    return True
                            elif any(stack_matches(x, p) for x in e.inventory):
                                return True
                        return False
                    i += 6
                else:
                    raise PS.Unsupported("execute %s %s" % (w, kind))
                kept = []
                for c in ctxs:
                    try:
                        r = pred(c)
                    except PS.Failed:
                        r = False
                    if r == want:
                        kept.append(c)
                ctxs = kept
            elif w == "store":
                if t[i + 1] != "result":
                    raise PS.Unsupported("execute store %s" % t[i + 1])
                if t[i + 2] == "score":
                    stores.append(("score", t[i + 3], t[i + 4]))
                    i += 5
                elif t[i + 2] == "bossbar":
                    stores.append(("bossbar",))
                    i += 5
                else:
                    raise PS.Unsupported("execute store result %s" % t[i + 2])
            else:
                raise PS.Unsupported("execute %s" % w)
        if not ctxs:
            raise PS.Failed("conditions failed")
        return len(ctxs)


def deliver_hook(world, ctx, args):
    """recovery/deliver, recorded: who, when, where and whether they still held the run tag."""
    p = ctx.ent
    world.delivered.append({"t": world.gametime, "name": p.name if p else None, "dim": p.dim if p else None,
                            "tags": frozenset(p.tags) if p else frozenset()})
    return 0


def world(dungeon_files, blackout_files, ns="cobblers"):
    """A booted world holding the dungeon pack and the blackout's two run-tag functions (verbatim)."""
    extra = {}
    for name in ("recovery/run_tail_end", "recovery/run_tag_stale"):
        rel = "data/%s/function/%s.mcfunction" % (ns, name)
        if rel in blackout_files:
            extra["%s:%s" % (ns, name)] = blackout_files[rel].splitlines()
    extra["%s:levelcap/battle_check" % ns] = ["# no-op: the test sets cobblers.lc_cap"]
    w = RiftWorld(dungeon_files, extra)
    w.hooks["%s:recovery/deliver" % ns] = deliver_hook
    w.objectives |= {"cobblers.lc_cap"}
    w.boot()
    return w
