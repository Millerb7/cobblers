#!/usr/bin/env python
"""Independent audit of the Rift finale's confrontation and release (Brann, Elara, the binder, rift_crisis_resolved).

Written by test-author, 2026-10-04, who did not build what it audits (commits 3e0f5ad, d968d79, 33c277c). The
owner: "set rift_crisis_resolved ourselves at the quest stage that ends the crisis ... the cradle chamber, the
confrontation with Elara and Brann, the release".

WHAT IT READS. The EMITTED packs under --packs (default build/datapacks), never the generators' functions:
  cobblers_dialogue           the compiled binder conversation, EXECUTED by this file's own Molang interpreter
  cobblers_trainers           the rctmod trainer, mob, won function, defeat advancement and cycle for both trainers
  cobblers_progression        the flag's advancement (must be impossible to earn) and its grant function
  cobblers_relic_underground  the carve functions, REPLAYED cell by cell over the cradle, and release_fx
  cobblers_rift_zones         z5's zone/admit/turn_back, EXECUTED by this file's own command model
  every pack                  swept for anything that grants the flag or writes either defeat field
and the Cobblemon 1.8 jar (species learnsets and abilities), found under experiments/EXP-000-*/runtime/server/mods.

WHERE THE EXPECTATIONS COME FROM (none from the artifact being checked):
  the finale doc (codex/trainer-modes docs/story/NPCS_AND_RIFT_FINALE.md): one flag, rift_crisis_resolved, set at
      the release; the release writes stage rift_released and League cursor league_001; the choice is
      "Release Hoopa."; Brann is "Captain Brann Saye", Elara "Director Elara Venn"; no capture; the cradle centre
  the owner's brief (2026-10-04): the flag at stage rift_crisis_pending AND brann_defeated AND elara_defeated only
  data/progression.json: the stage enum (every value walked) and the two fields' declarations
  the level cap after gym 8: RCT's own rule (max(initialLevelCap, next required trainer's highest level +
      relativeLevelCap), modpack/config/rctmod-server.toml) over the first Elite Four member in data/trainers.json
  data/relic_underground.json: the cradle's centre, radius and floor, and the passage's band (the walk's start)
  data/rift_zones.json: z5's pass

THE CONVERSATION WALK. Every start state -- every stage value and unset, each defeat field unset/0/1, the flag held
or not, and every cursor value -- is opened, and every reachable page, acknowledge and visible option is taken,
including re-opening the conversation after each change, until nothing new is reached. Every run of
cobblers:flag/rift_crisis_resolved/grant is recorded with the state it ran in. The rule: it runs ONLY in a state at
stage rift_crisis_pending with both fields 1, and from every such state it is reachable.

WHAT IT DOES NOT COVER. Nothing here ran in Minecraft. rctmod's sight check (forceBattleOnSight, its look ticks,
its level-difference limit), the defeat_count trigger firing for these two ids, the compiled pages rendering, and
the particles showing are each proven for other seats and conversations, or not at all. The walk is 4-neighbour
with a one-block step up and a three-block drop, and treats every block a carve function writes as solid except
air and light; it knows only the cells the relic pack writes and treats the rest as rock (the shell's claim, not
checked against a world). Move legality is "in the species' or a pre-evolution's list in the jar at or below the
Pokemon's level, or by TM/tutor/egg"; whether rctmod checks legality at all is not asked.

  python tools/finale_audit.py [--packs build/datapacks] [--jar PATH] [--json OUT]
Exit 0 clean, 1 problems.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import sys
import zipfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PACKS = ROOT / "build" / "datapacks"

# ---- the contract, from the finale doc and the owner's brief (not from any generator)
FLAG = "rift_crisis_resolved"
FLAG_ADV = "cobblers:flag/%s" % FLAG
FLAG_GRANT_FN = "cobblers:flag/%s/grant" % FLAG
QUEST = "main_worldshift_reveal"
STAGE = "quest.%s.stage" % QUEST
PENDING = "rift_crisis_pending"
RELEASED = "rift_released"
LEAGUE_CURSOR = ("quest.%s.league_cursor" % QUEST, "league_001")
BRANN_FIELD = "quest.%s.brann_defeated" % QUEST
ELARA_FIELD = "quest.%s.elara_defeated" % QUEST
CONV = "dlg_main_relic_hall_release"
CHOICE = "Release Hoopa."
NAMES = {"brann": "Captain Brann Saye", "elara": "Director Elara Venn"}
RELEASE_FX = "cobblers:relic_underground/release_fx"
PASSABLE = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:light"}
UNKNOWN = "unknown:rock"


def key(field):
    """The player-data key a quest field is stored under (docs: compile_dialogue's 'state' contract, EXP-022)."""
    return "cobblers__" + field.replace(".", "__")


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# =============================================================== Molang: this file's own interpreter

class MolangError(Exception):
    pass


TOK = re.compile(r"\s*(?:(?P<num>\d+(?:\.\d+)?)|(?P<str>'(?:\\.|[^'\\])*')|(?P<name>[A-Za-z_][A-Za-z0-9_.]*)"
                 r"|(?P<op>==|!=|&&|\|\||[!?:=+(){};,\-<>]))")


def tokens(src):
    out, i = [], 0
    while i < len(src):
        if src[i:].strip() == "":
            break
        m = TOK.match(src, i)
        if not m:
            raise MolangError("cannot read %r" % src[i:i + 30])
        i = m.end()
        for k in ("num", "str", "name", "op"):
            if m.group(k) is not None:
                v = m.group(k)
                if k == "str":
                    v = re.sub(r"\\(.)", r"\1", v[1:-1])
                elif k == "num":
                    v = float(v) if "." in v else int(v)
                out.append((k, v))
    out.append(("end", None))
    return out


class Parser:
    def __init__(self, src):
        self.t, self.i = tokens(src), 0

    def peek(self, v=None):
        k, x = self.t[self.i]
        return (k, x) if v is None else (k == "op" and x == v)

    def take(self, v=None):
        k, x = self.t[self.i]
        if v is not None and not (k == "op" and x == v):
            raise MolangError("expected %r at token %d, got %r" % (v, self.i, x))
        self.i += 1
        return k, x

    def program(self, close=None):
        stmts = []
        while True:
            if self.peek()[0] == "end" or (close and self.peek(close)):
                return stmts
            if self.peek(";"):
                self.take()
                continue
            stmts.append(self.stmt())

    def block(self):
        self.take("{")
        body = self.program("}")
        self.take("}")
        return body

    def stmt(self):
        if self.peek() == ("name", "return"):
            self.take()
            return ("return", self.expr())
        e = self.expr()
        if self.peek("="):
            self.take()
            if e[0] != "var":
                raise MolangError("assignment to %r" % (e,))
            return ("set", e[1], self.expr())
        if self.peek("?"):
            self.take()
            yes = self.block()
            no = []
            if self.peek(":"):
                self.take()
                no = self.block()
            return ("if", e, yes, no)
        return ("expr", e)

    def expr(self):
        return self.binary(0)

    LEVELS = [("||",), ("&&",), ("==", "!="), ("+",)]

    def binary(self, lvl):
        if lvl == len(self.LEVELS):
            return self.unary()
        left = self.binary(lvl + 1)
        while self.peek()[0] == "op" and self.peek()[1] in self.LEVELS[lvl]:
            op = self.take()[1]
            left = ("bin", op, left, self.binary(lvl + 1))
        return left

    def unary(self):
        if self.peek("!"):
            self.take()
            return ("not", self.unary())
        if self.peek("-"):
            self.take()
            return ("neg", self.unary())
        return self.primary()

    def primary(self):
        k, v = self.take()
        if k in ("num", "str"):
            return ("lit", v)
        if k == "op" and v == "(":
            e = self.expr()
            self.take(")")
            return e
        if k == "name":
            if self.peek("("):
                self.take()
                args = []
                while not self.peek(")"):
                    args.append(self.expr())
                    if self.peek(","):
                        self.take()
                self.take(")")
                return ("call", v, args)
            return ("var", v)
        raise MolangError("unexpected %r" % (v,))


_AST = {}


def parse(src):
    if src not in _AST:
        _AST[src] = Parser(src).program()
    return _AST[src]


class Return(Exception):
    def __init__(self, v):
        self.v = v


class Molang:
    """Runs one Molang source as one player. page/closed record the dialogue requests (the last one wins)."""

    def __init__(self, world, player, vars_=None):
        self.w, self.p = world, player
        self.temp = {}
        self.vars = vars_ if vars_ is not None else {}
        self.page, self.closed = None, False

    def run(self, src):
        try:
            self.block(parse(src))
        except Return as r:
            return r.v
        return None

    def block(self, stmts):
        for s in stmts:
            self.stmt(s)

    def stmt(self, s):
        k = s[0]
        if k == "return":
            raise Return(self.eval(s[1]))
        if k == "set":
            self.assign(s[1], self.eval(s[2]))
        elif k == "if":
            self.block(s[2] if truthy(self.eval(s[1])) else s[3])
        else:
            self.eval(s[1])

    def assign(self, name, value):
        if name == "t.d":
            self.temp["t.d"] = value
        elif name.startswith("t.d."):
            store = self.temp.get("t.d")
            if not isinstance(store, dict):
                raise MolangError("t.d.%s written before t.d = q.player.data()" % name[4:])
            store[name[4:]] = value
        elif name.startswith("v."):
            self.vars[name[2:]] = value
        elif name.startswith("t."):
            self.temp[name] = value
        else:
            raise MolangError("assignment to %s" % name)

    def var(self, name):
        if name == "q.player.uuid":
            return self.p.uuid
        if name.startswith("t.d."):
            store = self.temp.get("t.d")
            if not isinstance(store, dict):
                raise MolangError("%s read before t.d = q.player.data()" % name)
            return store.get(name[4:], 0)
        if name == "t.d":
            return self.temp.get("t.d", 0)
        if name.startswith("v."):
            return self.vars.get(name[2:], 0)
        if name.startswith("t."):
            return self.temp.get(name, 0)
        raise MolangError("unknown variable %s" % name)

    def eval(self, e):
        k = e[0]
        if k == "lit":
            return e[1]
        if k == "var":
            return self.var(e[1])
        if k == "not":
            return 0 if truthy(self.eval(e[1])) else 1
        if k == "neg":
            return -self.eval(e[1])
        if k == "bin":
            op = e[1]
            if op == "&&":
                return 1 if truthy(self.eval(e[2])) and truthy(self.eval(e[3])) else 0
            if op == "||":
                return 1 if truthy(self.eval(e[2])) or truthy(self.eval(e[3])) else 0
            a, b = self.eval(e[2]), self.eval(e[3])
            if op == "==":
                return 1 if same(a, b) else 0
            if op == "!=":
                return 0 if same(a, b) else 1
            if op == "+":
                return (str(a) + str(b)) if isinstance(a, str) or isinstance(b, str) else a + b
        if k == "call":
            return self.call(e[1], [self.eval(a) for a in e[2]])
        raise MolangError("cannot evaluate %r" % (e,))

    def call(self, name, args):
        if name == "q.player.data":
            return self.p.data
        if name == "q.player.save_data":
            self.p.saves += 1
            return 1
        if name == "q.player.has_tag":
            return 1 if args[0] in self.p.tags else 0
        if name == "q.run_command":
            self.w.command(args[0], self.p, server=True)
            return 1
        if name == "q.dialogue.set_page":
            self.page, self.closed = args[0], False
            return 1
        if name == "q.dialogue.close":
            self.closed = True
            return 1
        raise MolangError("unknown query %s" % name)


def truthy(v):
    if isinstance(v, str):
        return v != ""
    return bool(v)


def same(a, b):
    if isinstance(a, str) != isinstance(b, str):
        return False
    return a == b


# =============================================================== commands: this file's own model

class Unmodelled(Exception):
    pass


class Player:
    def __init__(self, uuid="00000000-0000-0000-0000-00000000c0b1", pos=(3363.5, 13.0, 3312.5)):
        self.uuid = uuid
        self.data, self.adv, self.tags, self.scores = {}, set(), set(), {}
        self.gamemode, self.pos, self.saves = "survival", pos, 0
        self.vehicle = None

    def snapshot(self):
        return (tuple(sorted(self.data.items(), key=lambda kv: kv[0])), frozenset(self.adv))


class World:
    """Runs emitted functions and server commands for one player. Every command a finale path reaches must be
    modelled; anything else raises Unmodelled, so the audit fails closed rather than skipping a line."""

    def __init__(self, functions):
        self.functions = functions          # {"ns:path": [lines]}
        self.log = []                       # (kind, detail, player data snapshot)
        self.depth = 0

    def function(self, fid, p, at=None):
        if fid not in self.functions:
            raise Unmodelled("function %s is in no pack" % fid)
        self.log.append(("function", fid, dict(p.data), frozenset(p.adv)))
        self.depth += 1
        if self.depth > 40:
            raise Unmodelled("function recursion through %s" % fid)
        try:
            for line in self.functions[fid]:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if self.command(line, p, at=at) == "return":
                    break
        finally:
            self.depth -= 1

    def command(self, cmd, p, server=False, at=None):
        at = at or p.pos
        w = cmd.split()
        head = w[0]
        if head == "execute":
            return self.execute(w[1:], p, at, cmd)
        if head == "function":
            self.function(w[1], p, at)
            return None
        if head == "return":
            return "return"
        if head == "advancement" and w[2] in ("@s", p.uuid) and w[3] == "only":
            (p.adv.add if w[1] == "grant" else p.adv.discard)(w[4])
            self.log.append(("advancement", "%s %s" % (w[1], w[4]), dict(p.data), frozenset(p.adv)))
            return None
        if head == "advancement":
            raise Unmodelled("advancement form %s" % cmd)
        if head == "scoreboard":
            if w[1] == "objectives":
                return None
            if w[1] == "players" and w[3] == "@s":
                if w[2] == "set":
                    p.scores[w[4]] = int(w[5])
                elif w[2] == "add":
                    p.scores[w[4]] = p.scores.get(w[4], 0) + int(w[5])
                elif w[2] == "reset":
                    p.scores.pop(w[4], None)
                else:
                    raise Unmodelled(cmd)
                self.log.append(("score", "%s %s" % (w[4], p.scores.get(w[4])), dict(p.data), frozenset(p.adv)))
                return None
            raise Unmodelled(cmd)
        if head == "tag" and w[1] in ("@s", p.uuid):
            (p.tags.add if w[2] == "add" else p.tags.discard)(w[3])
            return None
        if head == "runmolang":
            m = re.match(r'runmolang "(.*)" (@s)$', cmd)
            if not m:
                raise Unmodelled(cmd)
            Molang(self, p).run(m.group(1).replace('\\"', '"'))
            return None
        if head in ("title", "tellraw", "particle", "playsound", "tp", "spawnpoint", "say"):
            self.log.append((head, cmd, dict(p.data), frozenset(p.adv)))
            if head == "tp":
                try:
                    p.pos = tuple(float(v) for v in (w[2:5] if w[1] == "@s" else w[1:4]))
                except ValueError:
                    pass
            return None
        if head in ("fill", "setblock", "summon", "clone", "kill", "data", "item", "give", "clear", "loot"):
            self.log.append(("world_change", cmd, dict(p.data), frozenset(p.adv)))
            return None
        raise Unmodelled(cmd)

    def execute(self, w, p, at, raw):
        i, me = 0, p
        while i < len(w):
            sub = w[i]
            if sub == "run":
                if me is None:
                    return None
                return self.command(" ".join(w[i + 1:]), me, at=at)
            if sub in ("as", "at"):
                sel = w[i + 1]
                ok = sel in ("@s", p.uuid) or (sel.startswith("@s[") and select(p, sel[2:], at))
                if not ok:
                    raise Unmodelled("execute %s %s in %s" % (sub, sel, raw))
                if sub == "at":
                    at = p.pos
                i += 2
                continue
            if sub == "positioned":
                at = tuple(float(v) for v in w[i + 1:i + 4])
                i += 4
                continue
            if sub == "on":
                if w[i + 1] != "vehicle":
                    raise Unmodelled(raw)
                if p.vehicle is None:
                    return None
                i += 2
                continue
            if sub in ("if", "unless"):
                want = sub == "if"
                kind = w[i + 1]
                if kind == "entity":
                    sel = w[i + 2]
                    if not sel.startswith("@s"):
                        raise Unmodelled(raw)
                    got = select(p, sel[2:], at)
                    i += 3
                elif kind == "score":
                    if w[i + 2] != "@s" or w[i + 4] != "matches":
                        raise Unmodelled(raw)
                    got = in_range(p.scores.get(w[i + 3]), w[i + 5])
                    i += 6
                else:
                    raise Unmodelled(raw)
                if got != want:
                    return None
                continue
            raise Unmodelled(raw)
        return None


def in_range(v, rng):
    """`matches` semantics: an unset score matches nothing."""
    if v is None:
        return False
    if ".." in rng:
        lo, hi = rng.split("..")
        return (lo == "" or v >= float(lo)) and (hi == "" or v <= float(hi))
    return v == float(rng)


def select(p, args, at):
    """@s[...] against one player. Only the arguments the finale's functions use are modelled."""
    if not args:
        return True
    body = args.strip()[1:-1]
    parts, depth, cur = [], 0, ""
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    kv = {}
    for part in parts:
        k, v = part.split("=", 1)
        kv.setdefault(k.strip(), []).append(v.strip())
    box = {}
    # x/y/z move the origin; with dx/dy/dz they are a volume, with distance the centre of a sphere
    origin = tuple(float(kv[a][0]) if a in kv else at[i] for i, a in enumerate(("x", "y", "z")))
    for k, vs in kv.items():
        for v in vs:
            if k == "gamemode":
                neg = v.startswith("!")
                if (p.gamemode == v.lstrip("!")) == neg:
                    return False
            elif k == "advancements":
                for item in v[1:-1].split(","):
                    a, want = item.split("=")
                    if (a.strip() in p.adv) != (want.strip() == "true"):
                        return False
            elif k == "tag":
                neg = v.startswith("!")
                if (v.lstrip("!") in p.tags) == neg:
                    return False
            elif k in ("x", "y", "z"):
                pass
            elif k in ("dx", "dy", "dz"):
                box[k] = float(v)
            elif k == "distance":
                d = math.dist(p.pos, origin)
                lo, _, hi = v.partition("..")
                if (lo and d < float(lo)) or (hi and d > float(hi)):
                    return False
            else:
                raise Unmodelled("selector argument %s" % k)
    if box:
        ox, oy, oz = origin
        x0, x1 = sorted((ox, ox + box.get("dx", 0)))
        y0, y1 = sorted((oy, oy + box.get("dy", 0)))
        z0, z1 = sorted((oz, oz + box.get("dz", 0)))
        # the player's hitbox (0.6 x 1.8) intersecting the box's cells, as Minecraft's dx/dy/dz test does
        px, py, pz = p.pos
        if not (px + 0.3 > x0 and px - 0.3 < x1 + 1 and py + 1.8 > y0 and py < y1 + 1 and pz + 0.3 > z0
                and pz - 0.3 < z1 + 1):
            return False
    return True


# =============================================================== the packs

def function_index(packs):
    """{"ns:path": [lines]} for every .mcfunction in every pack under packs (lazy: paths first)."""
    idx = {}
    for f in sorted(Path(packs).glob("*/data/*/function/**/*.mcfunction")):
        parts = f.relative_to(Path(packs)).parts           # pack, data, ns, function, ...path
        ns, path = parts[2], "/".join(parts[4:])[:-len(".mcfunction")]
        idx.setdefault("%s:%s" % (ns, path), f)
    return idx


class LazyFunctions(dict):
    def __init__(self, paths):
        super().__init__()
        self.paths = paths

    def __contains__(self, k):
        return k in self.paths

    def __getitem__(self, k):
        if not dict.__contains__(self, k):
            dict.__setitem__(self, k, self.paths[k].read_text(encoding="utf-8").splitlines())
        return dict.__getitem__(self, k)


# =============================================================== expectations, from the data and the doc

def level_cap_after_gym8(data=DATA, rct_toml=ROOT / "modpack" / "config" / "rctmod-server.toml"):
    """RCT's own rule (docs/research/notes/level-cap-catch-block.md, LevelUtils): max(initialLevelCap, the next
    required trainer's highest level + relativeLevelCap). After gym 8 the next required trainer is the first Elite
    Four member."""
    toml = Path(rct_toml).read_text(encoding="utf-8")
    init = int(re.search(r"^\s*initialLevelCap\s*=\s*(-?\d+)", toml, re.M).group(1))
    rel = int(re.search(r"^\s*relativeLevelCap\s*=\s*(-?\d+)", toml, re.M).group(1))
    t = jload(Path(data) / "trainers.json")["trainers"]
    first = min((r for r in t if r["class"] == "elite_four"), key=lambda r: r["order"])
    return max(init, max(m["level"] for m in first["rct"]["team"]) + rel)


def finale_ids(data=DATA):
    """{'brann': id, 'elara': id}, matched by the finale doc's display names."""
    out = {}
    for t in jload(Path(data) / "finale_trainers.json")["trainers"]:
        for who, name in NAMES.items():
            if t.get("display_name") == name:
                out[who] = t["id"]
    return out


# =============================================================== the checks

def check_fields(data=DATA):
    bad = []
    fields = {f["id"]: f for f in jload(Path(data) / "progression.json")["quest_fields"]}
    for f in (BRANN_FIELD, ELARA_FIELD):
        d = fields.get(f)
        if not d:
            bad.append("data/progression.json does not declare %s" % f)
        elif d.get("type") != "boolean" or d.get("scope") != "player":
            bad.append("%s is %s/%s, not a per-player boolean" % (f, d.get("type"), d.get("scope")))
    st = fields.get(STAGE, {})
    for v in (PENDING, RELEASED):
        if v not in (st.get("allowed_values") or []):
            bad.append("%s has no value %s" % (STAGE, v))
    return bad


def stage_values(data=DATA):
    fields = {f["id"]: f for f in jload(Path(data) / "progression.json")["quest_fields"]}
    return list(fields[STAGE]["allowed_values"])


def contract(data):
    """The owner's rule, on a player's data: stage pending and both fields 1."""
    return (data.get(key(STAGE)) == PENDING and data.get(key(BRANN_FIELD)) == 1
            and data.get(key(ELARA_FIELD)) == 1)


def check_trainers(packs, ids, cap, jar):
    """The emitted rctmod files for both, the won functions, the advancements, and the jar's learnsets."""
    bad, notes = [], []
    tp = Path(packs) / "cobblers_trainers"
    species = jar_species(jar) if jar else None
    if species is None:
        bad.append("no Cobblemon 1.8 jar found: move and ability legality NOT checked (pass --jar)")
    for who, tid in ids.items():
        f = tp / "data" / "rctmod" / "trainers" / ("%s.json" % tid)
        if not f.is_file():
            bad.append("%s: no emitted rctmod trainer %s" % (who, f))
            continue
        t = jload(f)
        if t.get("name", {}).get("literal") != NAMES[who]:
            bad.append("%s: emitted name %r, the finale doc's is %r" % (tid, t.get("name"), NAMES[who]))
        team = t.get("team") or []
        if not team:
            bad.append("%s: empty team" % tid)
        for m in team:
            if m["level"] > cap:
                bad.append("%s: %s level %d over the post-gym-8 cap %d" % (tid, m["species"], m["level"], cap))
            if species is not None:
                bad += ["%s: %s" % (tid, p) for p in legality(species, m)]
        notes.append("%s: %d Pokemon, levels %s, cap %d" % (tid, len(team), [m["level"] for m in team], cap))
        mob = tp / "data" / "rctmod" / "mobs" / "trainers" / "single" / ("%s.json" % tid)
        if not mob.is_file():
            bad.append("%s: no emitted mob file" % tid)
        else:
            mj = jload(mob)
            if mj.get("maxTrainerDefeats") != 1:
                bad.append("%s: maxTrainerDefeats %r, a story fight is beaten once" % (tid, mj.get("maxTrainerDefeats")))
            if mj.get("series") or mj.get("requiredDefeats"):
                bad.append("%s: joins an rctmod series, which would move every player's level cap" % tid)
        adv = tp / "data" / "cobblers" / "advancement" / "trainer" / ("%s.json" % tid)
        if not adv.is_file():
            bad.append("%s: no defeat advancement" % tid)
            continue
        crit = list(jload(adv)["criteria"].values())
        if len(crit) != 1 or crit[0].get("trigger") != "rctmod:defeat_count" \
                or crit[0].get("conditions", {}).get("trainer_ids") != [tid] \
                or crit[0].get("conditions", {}).get("count") != 1:
            bad.append("%s: the advancement is not rctmod:defeat_count for [%s] at count 1: %s" % (tid, tid, crit))
    return bad, notes


def sight_of(packs, tid):
    """(forceBattleOnSight, forceBattleMaxDistance) from the emitted mob file."""
    f = Path(packs) / "cobblers_trainers" / "data" / "rctmod" / "mobs" / "trainers" / "single" / ("%s.json" % tid)
    mj = jload(f)
    return bool(mj.get("forceBattleOnSight")), float(mj.get("forceBattleMaxDistance") or 0)


def seat_of(functions, tid):
    """The trainer's standing position as the emitted cycle holds it: the tp target of its home line."""
    for line in functions["cobblers:trainers/cycle"]:
        if 'TrainerId:"%s"' % tid in line and " run tp @s " in line:
            x, y, z = (float(v) for v in line.rsplit(" run tp @s ", 1)[1].split()[:3])
            return (x, y, z)
    return None


def defeat_events(packs, functions, tid, p, world):
    """A player beats tid: every emitted advancement whose criterion is rctmod:defeat_count for tid at count 1
    rewards its function, as and at the player. Returns the advancements that fired."""
    fired = []
    for f in sorted(Path(packs).glob("*/data/*/advancement/**/*.json")):
        try:
            a = jload(f)
        except ValueError:
            continue
        for c in (a.get("criteria") or {}).values():
            cond = c.get("conditions") or {}
            if c.get("trigger") == "rctmod:defeat_count" and tid in (cond.get("trainer_ids") or []) \
                    and cond.get("count", 1) <= 1:
                fired.append(str(f))
                fn = (a.get("rewards") or {}).get("function")
                if fn:
                    world.function(fn, p)
    return fired


def check_defeat_fields(packs, functions, ids):
    """Beat one trainer at a time from a clean player: exactly that trainer's field becomes 1, the other stays 0."""
    bad = []
    want = {"brann": key(BRANN_FIELD), "elara": key(ELARA_FIELD)}
    for who, tid in ids.items():
        w, p = World(functions), Player()
        try:
            fired = defeat_events(packs, functions, tid, p, w)
        except (Unmodelled, MolangError) as e:
            bad.append("%s's won path does not run in the model: %s" % (tid, e))
            continue
        if not fired:
            bad.append("%s: no emitted advancement fires on rctmod defeat_count for it" % tid)
        for other, k in want.items():
            got = p.data.get(k, 0)
            if other == who and got != 1:
                bad.append("%s: beating it leaves %s at %r, not 1" % (tid, k, got))
            if other != who and got != 0:
                bad.append("%s: beating it sets %s (%r), the OTHER trainer's field" % (tid, k, got))
        if FLAG_ADV in p.adv:
            bad.append("%s: beating it grants %s directly" % (tid, FLAG))
    return bad


# ------------------------------------------------------------------ the conversation walk

def dialogue_of(packs):
    f = Path(packs) / "cobblers_dialogue" / "data" / "cobblers" / "dialogues" / ("%s.json" % CONV)
    return jload(f) if f.is_file() else None


def walk(dlg, functions, start, max_states=4000):
    """Every path through the compiled conversation from one player state. Returns (grant runs, states reached,
    offered): grant runs are the player data each grant ran in; offered is True when the choice CHOICE was
    ever visible."""
    pages = {p["id"]: p for p in dlg["pages"]}
    grants, seen, offered = [], set(), False
    q = deque([start])
    while q and len(seen) < max_states:
        data, adv = q.popleft()
        sig = (tuple(sorted(data.items())), frozenset(adv))
        if sig in seen:
            continue
        seen.add(sig)

        def fresh():
            p = Player()
            p.data, p.adv = dict(data), set(adv)
            return p

        # open the conversation
        w, p = World(functions), fresh()
        m = Molang(w, p)
        m.run(dlg["initializationAction"])
        grants += collect(w)
        frontier = []                                   # (player state, page id) still to take
        if not m.closed and m.page is not None:
            frontier.append((dict(p.data), set(p.adv), m.page))
        q.append((dict(p.data), set(p.adv)))
        inner = set()
        while frontier:
            d0, a0, pid = frontier.pop()
            isig = (tuple(sorted(d0.items())), frozenset(a0), pid)
            if isig in inner:
                continue
            inner.add(isig)
            page = pages.get(pid)
            if page is None:
                raise MolangError("set_page(%r): no such page" % pid)
            inp = page.get("input")
            actions = []
            if isinstance(inp, str):
                actions.append(inp)
            elif isinstance(inp, dict) and inp.get("type") == "option":
                for opt in inp["options"]:
                    p = Player()
                    p.data, p.adv = dict(d0), set(a0)
                    vis = opt.get("isVisible")
                    shown = True if vis is None else truthy(Molang(World(functions), p).run(vis))
                    if shown:
                        if opt["text"] == CHOICE:
                            offered = True
                        actions.append(opt["action"])
            for act in actions:
                w, p = World(functions), Player()
                p.data, p.adv = dict(d0), set(a0)
                m = Molang(w, p)
                m.run(act)
                grants += collect(w)
                q.append((dict(p.data), set(p.adv)))           # closing here and re-opening later
                if not m.closed and m.page is not None:
                    frontier.append((dict(p.data), set(p.adv), m.page))
    return grants, len(seen), offered


def collect(w):
    return [(d, a) for kind, detail, d, a in w.log if kind == "function" and detail == FLAG_GRANT_FN]


def start_states(data_dir, dlg):
    cursor_key = key("quest.%s.relic_release_cursor" % QUEST)
    cursors = [None] + [p["id"] for p in dlg["pages"]]
    for stage in [None] + stage_values(data_dir):
        for b in (None, 0, 1):
            for e in (None, 0, 1):
                for flag in (False, True):
                    for c in (None, "release_001", cursors[-1]) if len(cursors) > 1 else (None,):
                        d = {}
                        if stage is not None:
                            d[key(STAGE)] = stage
                        if b is not None:
                            d[key(BRANN_FIELD)] = b
                        if e is not None:
                            d[key(ELARA_FIELD)] = e
                        if c is not None:
                            d[cursor_key] = c
                        yield d, ({FLAG_ADV} if flag else set())


def check_conversation(packs, functions, data_dir=DATA):
    """The compiled binder conversation, executed from every start state."""
    bad, notes = [], []
    dlg = dialogue_of(packs)
    if dlg is None:
        return ["the compiled %s is not in %s/cobblers_dialogue" % (CONV, packs)], notes
    starts = list(start_states(data_dir, dlg))
    reachable_from_good = 0
    for data, adv in starts:
        try:
            grants, n, offered = walk(dlg, functions, (data, adv))
        except (Unmodelled, MolangError) as e:
            bad.append("the conversation does not run in the model from %s: %s" % (data, e))
            break
        for d, _a in grants:
            if not contract(d):
                bad.append("%s is granted in a state that fails the rule: stage %r, brann %r, elara %r (start %s)"
                           % (FLAG, d.get(key(STAGE)), d.get(key(BRANN_FIELD)), d.get(key(ELARA_FIELD)), data))
        if contract(data):
            if not grants:
                bad.append("from %s (the rule holds) the release never grants %s" % (data, FLAG))
            else:
                reachable_from_good += 1
            if not offered:
                bad.append("from %s the choice %r is never shown" % (data, CHOICE))
        elif offered:
            bad.append("the choice %r is shown from %s, where the rule fails" % (CHOICE, data))
        if len(bad) > 20:
            bad.append("... stopped after 20")
            break
    notes.append("conversation: %d start states walked; the grant reachable from %d (those meeting the rule)"
                 % (len(starts), reachable_from_good))
    return bad, notes


def check_release_effects(packs, functions):
    """From a state meeting the rule, the release run: the flag, the stage, the League cursor, and release_fx last,
    @s-only, nothing built or spawned."""
    bad = []
    dlg = dialogue_of(packs)
    if dlg is None:
        return ["no compiled %s" % CONV]
    page = next((p for p in dlg["pages"] if p["id"] == "release_001"), None)
    if page is None:
        return ["the compiled conversation has no release_001 page"]
    bad += release_fx_lines_problems(functions)
    # the releasing player stands at the binder (data/relic_underground.json geometry.release.at)
    w, p = World(functions), Player(pos=tuple(v + 0.5 if i != 1 else float(v)
                                              for i, v in enumerate(cradle_geometry()["binder"])))
    p.data = {key(STAGE): PENDING, key(BRANN_FIELD): 1, key(ELARA_FIELD): 1}
    try:
        Molang(w, p).run(page["input"])
    except (Unmodelled, MolangError) as e:
        return bad + ["release_001 does not run in the model: %s" % e]
    if FLAG_ADV not in p.adv:
        bad.append("release_001 at the rule's state does not grant %s" % FLAG_ADV)
    if p.data.get(key(STAGE)) != RELEASED:
        bad.append("release_001 leaves the stage at %r, the doc's write is %r" % (p.data.get(key(STAGE)), RELEASED))
    if p.data.get(key(LEAGUE_CURSOR[0])) != LEAGUE_CURSOR[1]:
        bad.append("release_001 leaves the League cursor at %r" % p.data.get(key(LEAGUE_CURSOR[0])))
    calls = [d for k, d, *_ in w.log if k == "function"]
    if RELEASE_FX not in calls:
        bad.append("release_001 never runs %s" % RELEASE_FX)
    elif FLAG_GRANT_FN in calls and calls.index(RELEASE_FX) < calls.index(FLAG_GRANT_FN):
        bad.append("release_fx runs before the grant")
    elif not any(k in ("particle", "playsound") for k, *_ in w.log):
        bad.append("release_fx shows nothing to a player at the binder's stand %s (its reach test returned)" % (p.pos,))
    for k, d, *_ in w.log:
        if k == "world_change":
            bad.append("the release changes the world: %s" % d)
    return bad


def release_fx_lines_problems(functions):
    """release_fx read line by line: every viewer @s, nothing built or spawned."""
    bad = []
    if RELEASE_FX in functions:
        for line in functions[RELEASE_FX]:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            h = s.split()[0]
            if h == "particle" and not s.endswith(" @s"):
                bad.append("release_fx shows a particle to more than the releasing player: %s" % s)
            if h == "playsound" and s.split()[3] != "@s":
                bad.append("release_fx plays a sound to more than the releasing player: %s" % s)
            if h in ("title", "tellraw") and s.split()[1] != "@s":
                bad.append("release_fx messages more than the releasing player: %s" % s)
            if h in ("summon", "fill", "setblock", "clone", "kill", "give", "loot", "spawnpokemon", "pokespawn"):
                bad.append("release_fx changes the world or spawns: %s" % s)
    else:
        bad.append("%s is in no pack" % RELEASE_FX)
    return bad


def check_progression(packs):
    bad = []
    pp = Path(packs) / "cobblers_progression" / "data" / "cobblers"
    adv = pp / "advancement" / "flag" / ("%s.json" % FLAG)
    if not adv.is_file():
        return ["no emitted advancement %s" % FLAG_ADV]
    trig = {c.get("trigger") for c in jload(adv)["criteria"].values()}
    if trig != {"minecraft:impossible"}:
        bad.append("%s can be earned by its own criteria %s: only the grant may set it" % (FLAG_ADV, sorted(trig)))
    if "parent" in jload(adv):
        bad.append("%s has a parent: `advancement grant ... through/until` on it would reach the flag" % FLAG_ADV)
    return bad


# ------------------------------------------------------------------ the sweep

CALLS_GRANT = re.compile(re.escape(FLAG_GRANT_FN) + r"(?![a-z0-9_/])")
GRANT_FORMS = re.compile(r"advancement\s+grant\s+\S+\s+(everything|from|through|until|only)\b\s*(\S*)")


def check_sweep(packs, ids):
    """Every emitted function and compiled dialogue: who grants the flag, who calls its grant, who writes the two
    defeat fields. Allowed: the flag's own grant function (its one line), the binder's release_001 page, and each
    trainer's own won function."""
    bad, seen = [], {"grant_callers": [], "grant_lines": [], "field_writers": {}}
    fkeys = {key(BRANN_FIELD): ids.get("brann"), key(ELARA_FIELD): ids.get("elara")}
    write = {k: re.compile(r"\b%s\s*=(?!=)" % re.escape(k)) for k in fkeys}
    root = Path(packs)
    for f in sorted(root.rglob("*")):
        if f.suffix not in (".mcfunction", ".json") or not f.is_file():
            continue
        raw = f.read_bytes()
        hit_flag = b"rift_crisis_resolved" in raw
        hit_field = b"brann_defeated" in raw or b"elara_defeated" in raw
        hit_every = b"advancement grant" in raw and (b" everything" in raw or b" through " in raw
                                                     or b" until " in raw or b" from " in raw)
        if not (hit_flag or hit_field or hit_every):
            continue
        text = raw.decode("utf-8", "replace")
        rel = f.relative_to(root).as_posix()
        for m in GRANT_FORMS.finditer(text):
            form, target = m.group(1), m.group(2)
            if form == "everything":
                bad.append("%s: `advancement grant ... everything` would grant %s" % (rel, FLAG))
            elif form in ("from", "through", "until") and target.startswith("cobblers:flag"):
                bad.append("%s: `advancement grant ... %s %s` may reach %s" % (rel, form, target, FLAG))
            elif form == "only" and target == FLAG_ADV:
                seen["grant_lines"].append(rel)
        if CALLS_GRANT.search(text):
            seen["grant_callers"].append(rel)
        for k, rx in write.items():
            if rx.search(text):
                seen["field_writers"].setdefault(k, []).append(rel)
    want_grant = "cobblers_progression/data/cobblers/function/flag/%s/grant.mcfunction" % FLAG
    if seen["grant_lines"] != [want_grant]:
        bad.append("`advancement grant ... only %s` is in %s; only %s may hold it"
                   % (FLAG_ADV, seen["grant_lines"], want_grant))
    want_caller = "cobblers_dialogue/data/cobblers/dialogues/%s.json" % CONV
    if seen["grant_callers"] != [want_caller]:
        bad.append("%s is called from %s; only %s may call it" % (FLAG_GRANT_FN, seen["grant_callers"], want_caller))
    else:
        dlg = jload(root / want_caller)
        pages = [p["id"] for p in dlg["pages"] if CALLS_GRANT.search(json.dumps(p))]
        if CALLS_GRANT.search(dlg.get("initializationAction", "")):
            bad.append("the conversation's entry action calls the grant")
        if pages != ["release_001"]:
            bad.append("the grant is called from pages %s; only release_001 may" % pages)
    for k, tid in fkeys.items():
        want = ["cobblers_trainers/data/cobblers/function/trainers/won/%s.mcfunction" % tid]
        if seen["field_writers"].get(k, []) != want:
            bad.append("%s is written by %s; only %s may write it" % (k, seen["field_writers"].get(k, []), want))
    return bad, seen


# ------------------------------------------------------------------ the cradle, replayed

FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: (replace|keep|destroy|hollow|"
                  r"outline)(?: (\S+))?)?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)(?: (replace|keep|destroy))?$")


def norm(b):
    b = b.split("[")[0].split("{")[0]
    return b if ":" in b else "minecraft:" + b


def replay(pack, box):
    """{(x, y, z): block} inside box (x0, y0, z0, x1, y1, z1) after the relic pack's block functions, in its own
    index order. Cells it never writes are UNKNOWN (rock, the shell's claim)."""
    pack = Path(pack)
    fdir = pack / "data" / "cobblers" / "function" / "relic_underground"
    order = [l.strip() for l in (fdir / "index.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    tags = {}
    for t in (pack / "data").glob("*/tags/block/*.json"):
        tags["#%s:%s" % (t.parts[-4], t.stem)] = {norm(v) for v in jload(t)["values"]}
    X0, Y0, Z0, X1, Y1, Z1 = box
    cells = {}
    for name in order:
        for line in (fdir / (name + ".mcfunction")).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = FILL.match(line)
            if m:
                x0, y0, z0, x1, y1, z1 = (int(v) for v in m.group(1, 2, 3, 4, 5, 6))
                b, mode, filt = norm(m.group(7)), m.group(8), m.group(9)
            else:
                s = SETBLOCK.match(line)
                if not s:
                    raise Unmodelled("%s: %s" % (name, line))
                x0, y0, z0 = (int(v) for v in s.group(1, 2, 3))
                x1, y1, z1 = x0, y0, z0
                b, mode, filt = norm(s.group(4)), s.group(5), None
            if mode in ("hollow", "outline", "destroy"):
                raise Unmodelled("%s: fill mode %s" % (name, mode))
            xa, xb = max(min(x0, x1), X0), min(max(x0, x1), X1)
            ya, yb = max(min(y0, y1), Y0), min(max(y0, y1), Y1)
            za, zb = max(min(z0, z1), Z0), min(max(z0, z1), Z1)
            if xa > xb or ya > yb or za > zb:
                continue
            for x in range(xa, xb + 1):
                for y in range(ya, yb + 1):
                    for z in range(za, zb + 1):
                        cur = cells.get((x, y, z), UNKNOWN)
                        if mode == "keep" and cur not in PASSABLE:
                            continue
                        if mode == "replace" and filt:
                            allowed = tags[filt] if filt.startswith("#") else {norm(filt)}
                            if cur not in allowed:
                                continue
                        cells[(x, y, z)] = b
    return cells


def passable(cells, c):
    return cells.get(c, UNKNOWN) in PASSABLE


def stand(cells, x, y, z):
    """A player can stand with feet at y: a solid block under, feet and head clear."""
    return not passable(cells, (x, y - 1, z)) and passable(cells, (x, y, z)) and passable(cells, (x, y + 1, z))


def stands(cells, box):
    X0, Y0, Z0, X1, Y1, Z1 = box
    return {(x, y, z) for (x, y, z) in cells if stand(cells, x, y, z) and Y0 < y < Y1}


def neighbours(cells, ss, c):
    x, y, z = c
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for dy in (1, 0, -1, -2, -3):
            n = (x + dx, y + dy, z + dz)
            if n not in ss:
                continue
            if dy == 1 and not passable(cells, (x, y + 2, z)):
                continue                          # no head room to jump the step
            if dy < 0 and not all(passable(cells, (x + dx, y + k, z + dz)) for k in range(dy + 1, 2)):
                continue                          # the drop's column must be open
            yield n
            break


def reach(cells, ss, starts, forbidden=frozenset()):
    seen = {s for s in starts if s not in forbidden}
    q = deque(seen)
    while q:
        c = q.popleft()
        for n in neighbours(cells, ss, c):
            if n not in seen and n not in forbidden:
                seen.add(n)
                q.append(n)
    return seen


def cradle_geometry(data=DATA):
    g = jload(Path(data) / "relic_underground.json")["geometry"]
    cr, pa = g["cradle"], g["passage"]
    rel = g["release"]
    return {"centre": tuple(cr["centre"]), "radius": cr["radius"], "floor": cr["floor_y"],
            "passage_z": tuple(pa["interior"]["z"]), "passage_x": (pa["stops_at_x"], pa["from"][0]),
            "binder": tuple(rel["at"])}


def check_cradle(packs, functions, ids, data=DATA):
    """Both seats standable in the cradle as built, and Brann's sight on every way out of the passage."""
    bad, notes = [], []
    pack = Path(packs) / "cobblers_relic_underground"
    if not (pack / "data" / "cobblers" / "function" / "relic_underground" / "index.txt").is_file():
        return ["the relic pack is not built at %s: the seats and the sight are NOT checked" % pack], notes
    geo = cradle_geometry(data)
    cx, cz = geo["centre"]
    r = geo["radius"]
    px0, px1 = geo["passage_x"]
    box = (cx - r - 2, geo["floor"] - 8, cz - r - 2, px1 + 2, geo["floor"] + 20, cz + r + 2)
    try:
        cells = replay(pack, box)
    except Unmodelled as e:
        return ["the relic pack's carve does not replay: %s" % e], notes
    ss = stands(cells, box)
    seats = {}
    for who, tid in ids.items():
        s = seat_of(functions, tid)
        if s is None:
            bad.append("%s: the emitted cycle holds it nowhere" % tid)
            continue
        seats[who] = s
        c = (math.floor(s[0]), int(round(s[1])), math.floor(s[2]))
        if math.hypot(c[0] - cx, c[2] - cz) > r:
            bad.append("%s's seat %s is outside the cradle (centre %s, radius %d)" % (tid, c, geo["centre"], r))
        if c[1] - 1 != geo["floor"]:
            bad.append("%s's seat %s does not stand on the cradle floor y%d" % (tid, c, geo["floor"]))
        if not stand(cells, *c):
            bad.append("%s's seat %s as built: under %s, feet %s, head %s -- not a floor with two air"
                       % (tid, c, cells.get((c[0], c[1] - 1, c[2]), UNKNOWN), cells.get(c, UNKNOWN),
                          cells.get((c[0], c[1] + 1, c[2]), UNKNOWN)))
    if "brann" not in seats:
        return bad, notes
    on_sight, dist = sight_of(packs, ids["brann"])
    if not on_sight or dist <= 0:
        bad.append("%s does not battle on sight, so nothing orders the confrontation" % ids["brann"])
        return bad, notes
    bx, by, bz = seats["brann"]
    sight = {c for c in ss if math.dist((c[0] + 0.5, c[1], c[2] + 0.5), (bx, by, bz)) <= dist}
    pz0, pz1 = geo["passage_z"]
    in_band = lambda c: pz0 <= c[2] <= pz1 and px0 <= c[0] <= px1
    outside = {c for c in ss if in_band(c) and math.hypot(c[0] - cx, c[2] - cz) > r}
    floor = {c for c in ss if math.hypot(c[0] - cx, c[2] - cz) <= r and c[1] == geo["floor"] + 1 and not in_band(c)}
    if not outside:
        bad.append("no standable passage cell outside the cradle in the band z%d-%d: the walk has no start"
                   % (pz0, pz1))
        return bad, notes
    free = reach(cells, ss, outside)
    if not (free & floor):
        bad.append("the passage does not reach the cradle's floor at all as built")
        return bad, notes
    bs = geo["binder"]
    if bs not in free:
        bad.append("the binder's stand %s is not reachable from the passage as built" % (bs,))
    dodged = reach(cells, ss, outside, frozenset(sight))
    escaped = sorted(dodged & floor)
    if escaped:
        bad.append("Brann's sight (%.1f from %s) does not cover the way in: %d cradle floor cells are reached from "
                   "the passage without entering it, e.g. %s" % (dist, seats["brann"], len(escaped), escaped[:3]))
    if bs in dodged:
        bad.append("the binder is reached without passing Brann's sight")
    notes.append("cradle: %d standable cells replayed, %d in Brann's sight (%.1f), %d passage cells outside the "
                 "cradle, %d reachable without his sight, none on the cradle floor" if not escaped else
                 "cradle: %d standable, %d in sight (%.1f), %d passage starts, %d reachable without sight")
    notes[-1] = notes[-1] % (len(ss), len(sight), dist, len(outside), len(dodged))
    return bad, notes


# ------------------------------------------------------------------ z5

def check_z5(packs, functions, data=DATA):
    """z5 opens on the flag: from data/rift_zones.json's pass, the emitted zone check run in the model."""
    bad = []
    z5 = jload(Path(data) / "rift_zones.json")["zones"]["z5"]
    p = z5["pass"]
    if p.get("advancements") != [FLAG_ADV]:
        bad.append("data/rift_zones.json z5's pass is %s, not %s" % (p.get("advancements"), FLAG_ADV))
    zone = "cobblers:rift_zones/z5/zone"
    if zone not in functions:
        return bad + ["no emitted %s (cobblers_rift_zones not built?)" % zone]
    adv = Path(packs) / "cobblers_rift_zones" / "data" / "cobblers" / "advancement" / "rift_zones" / "z5_zone.json"
    if not adv.is_file() or (jload(adv).get("rewards") or {}).get("function") != zone:
        bad.append("the z5 location advancement does not reward %s" % zone)
    obj = None
    for line in functions[zone]:
        m = re.search(r"unless score @s (\S+) matches 1\.\.", line)
        if m:
            obj = m.group(1)
    for holds, mode in ((False, "survival"), (True, "survival"), (False, "creative")):
        w, pl = World(functions), Player(pos=(3600.5, 100.0, 2600.5))
        pl.gamemode = mode
        if holds:
            pl.adv.add(FLAG_ADV)
        try:
            w.function(zone, pl)
        except Unmodelled as e:
            return bad + ["z5's zone check does not run in the model: %s" % e]
        turned = any(d == "cobblers:rift_zones/z5/turn_back" for k, d, *_ in w.log if k == "function")
        if holds and turned:
            bad.append("z5 turns back a player holding %s" % FLAG)
        if holds and (obj is None or pl.scores.get(obj) != 1):
            bad.append("z5 does not admit (score %s) a player holding %s" % (obj, FLAG))
        if not holds and mode == "survival" and not turned:
            bad.append("z5 lets a survival player without %s stay" % FLAG)
        if not holds and pl.scores.get(obj):
            bad.append("z5 gives its pass to a player without %s (%s mode)" % (FLAG, mode))
        # and again, once admitted: the score holds
        if holds:
            w2 = World(functions)
            w2.function(zone, pl)
            if any(d.endswith("/turn_back") for k, d, *_ in w2.log if k == "function"):
                bad.append("z5 turns back an admitted player on the next check")
    return bad


# ------------------------------------------------------------------ the jar

def find_jar(given=None):
    if given:
        return Path(given) if Path(given).is_file() else None
    pats = [ROOT / "experiments" / "EXP-000-cobblemon-1.8-compat" / "runtime" / "server" / "mods"]
    if ROOT.parent.name == "worktrees":
        main = ROOT.parent.parent.parent
        pats.append(main / "experiments" / "EXP-000-cobblemon-1.8-compat" / "runtime" / "server" / "mods")
        pats += [Path(p) for p in sorted(glob.glob(str(ROOT.parent / "*" / "experiments" / "EXP-000-cobblemon-1.8-compat"
                                                       / "runtime" / "server" / "mods")))]
    else:
        pats += [Path(p) for p in sorted(glob.glob(str(ROOT / ".claude" / "worktrees" / "*" / "experiments"
                                                       / "EXP-000-cobblemon-1.8-compat" / "runtime" / "server" / "mods")))]
    for d in pats:
        hits = sorted(d.glob("Cobblemon-fabric-1.8*.jar")) if d.is_dir() else []
        if hits:
            return hits[0]
    return None


def jar_species(jar):
    try:
        z = zipfile.ZipFile(jar)
    except (OSError, zipfile.BadZipFile):
        return None
    out = {}
    for n in z.namelist():
        if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
            out[n.rsplit("/", 1)[1][:-5]] = (z, n)
    return out


def legality(species, mon):
    """A move is learnable when the species or a pre-evolution lists it at a level <= the Pokemon's, or by tm,
    tutor or egg. The ability must be one the species lists (hidden included)."""
    bad = []
    sid = mon["species"].lower()
    if sid not in species:
        return ["species %s is not in the jar" % sid]
    chain, cur = [], sid
    while cur and cur in species and len(chain) < 4:
        z, n = species[cur]
        d = json.loads(z.read(n))
        chain.append(d)
        cur = (d.get("preEvolution") or "").split(" ")[0].lower() or None
    how = {}
    for d in chain:
        for e in d.get("moves") or []:
            k, mv = e.split(":", 1)
            how.setdefault(mv, set()).add(k)
    for mv in mon.get("moveset") or []:
        ks = how.get(mv, set())
        ok = any(k in ("tm", "tutor", "egg") for k in ks) or any(k.isdigit() and int(k) <= mon["level"] for k in ks)
        if not ok:
            bad.append("%s (level %d) cannot learn %s (jar: %s)" % (sid, mon["level"], mv, sorted(ks) or "never"))
    abil = [a.split(":", 1)[-1] for a in chain[0].get("abilities") or []]
    if mon.get("ability") and mon["ability"] not in abil:
        bad.append("%s cannot have ability %s (jar: %s)" % (sid, mon["ability"], abil))
    return bad


# =============================================================== run

def audit(packs=PACKS, jar=None, data=DATA, skip_jar=False):
    packs = Path(packs)
    functions = LazyFunctions(function_index(packs))
    ids = finale_ids(data)
    results = {}
    problems = []
    if sorted(ids) != ["brann", "elara"]:
        problems.append("data/finale_trainers.json does not carry both %s" % sorted(NAMES.values()))
        return problems, results
    cap = level_cap_after_gym8(data)
    results["cap"] = cap
    problems += check_fields(data)
    jp = None if skip_jar else find_jar(jar)
    b, n = check_trainers(packs, ids, cap, jp)
    if skip_jar:
        b = [x for x in b if not x.startswith("no Cobblemon 1.8 jar")]
    problems += b
    results["trainers"] = n
    results["jar"] = str(jp) if jp else None
    problems += check_defeat_fields(packs, functions, ids)
    b, n = check_conversation(packs, functions, data)
    problems += b
    results["conversation"] = n
    problems += check_release_effects(packs, functions)
    problems += check_progression(packs)
    b, seen = check_sweep(packs, ids)
    problems += b
    results["sweep"] = seen
    b, n = check_cradle(packs, functions, ids, data)
    problems += b
    results["cradle"] = n
    problems += check_z5(packs, functions, data)
    return problems, results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--packs", default=str(PACKS))
    ap.add_argument("--jar")
    ap.add_argument("--json", help="write the full result here")
    ap.add_argument("--source-root", help="accepted for prepare's job list; nothing here reads the heightmap")
    a = ap.parse_args(argv)
    problems, results = audit(a.packs, a.jar)
    if a.json:
        Path(a.json).write_text(json.dumps({"problems": problems, "results": results}, indent=1, default=list),
                                encoding="utf-8")
    for k in ("trainers", "conversation", "cradle"):
        for line in results.get(k) or []:
            print("  " + line)
    print("  jar: %s" % results.get("jar"))
    for p in problems:
        print("PROBLEM " + p)
    print("finale_audit: %d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
