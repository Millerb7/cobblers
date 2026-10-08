"""Independent audit of the Beast Ball key (tools/key_ball.py, data/key_ball.json, commit ae40f64).

Written by a different agent from the builder, without reading tests/test_key_ball.py or the builder's research note.
Every expectation here comes from one of three places, never from the generator's own code:

1. THE JAR MODEL below: Cobblemon 1.8.0's capture path as read from the bytecode of the server snapshot's
   Cobblemon-fabric-1.8.0+1.21.1.jar on 2026-10-08 (javap; class and method named at each step).
2. A MoLang interpreter of this file's own, for the subset the repo's callbacks use. It refuses any query or entity
   name the jar does not expose (the name sets are listed beside it), so a typo in a generator fails here instead of
   silently reading 0 in game.
3. The owner's rules (data/key_ball.json `decision`, relayed in the audit brief) and the other data files.

What the generated callbacks are run against: the real generated files (key_ball.build, and the level cap's, the Hoopa
cradle's and Ursaluna's poke_ball_capture_calculated scripts from their own generators), the real refund function, and a
small command interpreter that knows only the commands those files use (an unknown command fails the test).

NOT covered (validity is not runtime behaviour, .claude/rules/testing.md): nothing here throws a ball in a running
Minecraft. The jar model is a reading of bytecode, not a run; vanilla `give`'s full-inventory drop is modelled from
vanilla's documented behaviour, not read; Fabric's load order for the recipe override and MoLang's real string and
temp-variable semantics are assumed to match the interpreter. Those are experiments/EXP-064's to prove in game.
"""
from __future__ import annotations

import io
import itertools
import json
import re
import sys
import types
import zipfile
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import key_ball  # noqa: E402
import entei_boss  # noqa: E402
import hoopa_cradle  # noqa: E402
import levelcap_pack  # noqa: E402
import ursaluna_cave  # noqa: E402

SNAPSHOT = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05")
COBBLEMON_JAR = SNAPSHOT / "mods" / "Cobblemon-fabric-1.8.0+1.21.1.jar"
FABRIC_API_JAR = SNAPSHOT / "mods" / "fabric-api-0.116.14+1.21.1.jar"

CAPTURE = "poke_ball_capture_calculated"
RATE = "pokemon_catch_rate_calculated"

# ------------------------------------------------------------------------------------------------ the jar model
# Every PokeBall Cobblemon 1.8.0 registers (the string constants of com/cobblemon/mod/common/api/pokeball/PokeBalls,
# read 2026-10-08). Each one's item id is its ball id (assets/cobblemon/lang/en_us.json has item.cobblemon.<name> for
# all 48).
ALL_BALLS = tuple("cobblemon:" + n for n in (
    "ancient_azure_ball ancient_citrine_ball ancient_feather_ball ancient_gigaton_ball ancient_great_ball "
    "ancient_heavy_ball ancient_ivory_ball ancient_jet_ball ancient_leaden_ball ancient_origin_ball ancient_poke_ball "
    "ancient_roseate_ball ancient_slate_ball ancient_ultra_ball ancient_verdant_ball ancient_wing_ball azure_ball "
    "beast_ball cherish_ball citrine_ball dive_ball dream_ball dusk_ball fast_ball friend_ball great_ball heal_ball "
    "heavy_ball level_ball love_ball lure_ball luxury_ball master_ball moon_ball nest_ball net_ball park_ball "
    "poke_ball premier_ball quick_ball repeat_ball roseate_ball safari_ball slate_ball sport_ball timer_ball "
    "ultra_ball verdant_ball").split())
# PokeBalls: the two balls built with GuaranteedModifier. CobblemonCaptureCalculator.processCapture returns
# CaptureContext.successful for them BEFORE it calls getCatchRate, so pokemon_catch_rate_calculated never fires.
GUARANTEED = {"cobblemon:master_ball", "cobblemon:ancient_origin_ball"}
# PokeBalls: beast_ball = LabelModifier(5.0, true, "ultra_beast"). LabelModifier.isValid is false for a Pokemon without
# the label, and processCapture then uses 1.0 (not 0.1: the jar's tooltip "0.1x otherwise" is not what the code does).
BEAST = "cobblemon:beast_ball"


def ball_modifier(ball, labels):
    if ball == BEAST:
        return 5.0 if "ultra_beast" in labels else 1.0
    return 1.0  # every other ball's own modifier is outside this audit; the key's rule is the only thing compared


# The names each MoLang struct exposes in the jar (the string constants of the *MoLangFunctions classes and the two
# events' context maps). The interpreter refuses any other name.
ENTITY_NAMES = {"has_tag", "add_tag", "remove_tag", "uuid"}            # EntityMoLangFunctions (subset used)
LIVING_NAMES = {"is_player"}                                           # LivingEntityMoLangFunctions
PLAYER_NAMES = {"is_player", "uuid", "is_creative", "username"}        # PlayerMoLangFunctions (subset used)
BALL_NAMES = {"ball_type", "capture_state"}                            # EmptyPokeBallEntity struct lambdas
RATE_CONTEXT = {"thrower", "poke_ball_entity", "pokemon_entity", "catch_rate"}   # PokemonCatchRateEvent
RATE_FUNCTIONS = {"set_catch_rate"}
CAPTURE_CONTEXT = {"thrower", "pokemon", "poke_ball", "is_successful_capture", "is_critical_capture"}
CAPTURE_FUNCTIONS = {"set_shakes", "set_critical_capture"}             # PokeBallCaptureCalculatedEvent
GENERAL = {"run_command"}                                              # GeneralMoLangFunctions


# ------------------------------------------------------------------------------------------------ MoLang subset
TOKEN = re.compile(r"\s*(?:('[^']*')|(\d+(?:\.\d+)?)|([A-Za-z_][A-Za-z0-9_]*)|(==|!=|\|\||&&|[?:;{}().,+\-*/=!<>]))")


def tokenize(src):
    out, i = [], 0
    src = src.strip()
    while i < len(src):
        m = TOKEN.match(src, i)
        if not m or m.end() == i:
            raise SyntaxError("MoLang: cannot read %r" % src[i:i + 30])
        s, n, name, op = m.groups()
        out.append(("str", s[1:-1]) if s is not None else ("num", float(n)) if n is not None
                   else ("name", name) if name is not None else ("op", op))
        i = m.end()
        while i < len(src) and src[i].isspace():
            i += 1
    return out


class Parser:
    def __init__(self, src):
        self.t, self.i = tokenize(src), 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def op(self, v):
        return self.peek() == ("op", v)

    def take(self, v=None):
        tok = self.peek()
        if v is not None and tok != ("op", v):
            raise SyntaxError("MoLang: expected %r, got %r" % (v, tok))
        self.i += 1
        return tok

    def program(self):
        out = []
        while self.i < len(self.t):
            out.append(self.stmt())
        return out

    def stmt(self):
        e = self.expr()
        self.take(";")
        return e

    def block(self):
        self.take("{")
        body = []
        while not self.op("}"):
            body.append(self.stmt())
        self.take("}")
        return ("block", body)

    def expr(self):
        left = self.cond()
        if self.op("="):
            self.take()
            return ("set", left, self.expr())
        return left

    def cond(self):
        c = self.binary(0)
        if self.op("?"):
            self.take()
            then = self.block() if self.op("{") else self.binary(0)
            els = None
            if self.op(":"):
                self.take()
                els = self.block() if self.op("{") else self.binary(0)
            return ("if", c, then, els)
        return c

    LEVELS = (("||",), ("&&",), ("==", "!="), ("<", ">"), ("+", "-"), ("*", "/"))

    def binary(self, lvl):
        if lvl == len(self.LEVELS):
            return self.unary()
        left = self.binary(lvl + 1)
        while self.peek()[0] == "op" and self.peek()[1] in self.LEVELS[lvl]:
            o = self.take()[1]
            left = ("bin", o, left, self.binary(lvl + 1))
        return left

    def unary(self):
        if self.op("!"):
            self.take()
            return ("not", self.unary())
        return self.postfix()

    def postfix(self):
        e = self.primary()
        while True:
            if self.op("."):
                self.take()
                kind, name = self.take()
                assert kind == "name", name
                e = ("member", e, name)
            elif self.op("("):
                self.take()
                args = []
                while not self.op(")"):
                    args.append(self.expr())
                    if self.op(","):
                        self.take()
                self.take(")")
                e = ("call", e, args)
            else:
                return e

    def primary(self):
        kind, v = self.take()
        if kind in ("str", "num"):
            return (kind, v)
        if kind == "name":
            return ("name", v)
        if v == "(":
            e = self.expr()
            self.take(")")
            return e
        raise SyntaxError("MoLang: unexpected %r" % v)


class Struct:
    """A MoLang struct exposing only `names`: a value, or a callable taking the call's arguments."""

    def __init__(self, names):
        self.names = dict(names)

    def get(self, name, args):
        if name not in self.names:
            raise AttributeError("MoLang name %r is not exposed by the jar here" % name)
        v = self.names[name]
        return v(*args) if callable(v) else v


def run_molang(src, q, temps):
    def ev(n):
        k = n[0]
        if k in ("str", "num"):
            return n[1]
        if k == "name":
            if n[1] == "q":
                return q
            if n[1] == "t":
                return temps
            raise NameError(n[1])
        if k == "member":
            obj = ev(n[1])
            if obj is temps:
                if n[2] not in temps:
                    raise NameError("t.%s read before it is set" % n[2])
                return temps[n[2]]
            return obj.get(n[2], [])
        if k == "call":
            f = n[1]
            assert f[0] == "member", f
            return ev(f[1]).get(f[2], [ev(a) for a in n[2]])
        if k == "set":
            tgt = n[1]
            assert tgt[0] == "member" and tgt[1] == ("name", "t"), tgt
            temps[tgt[2]] = ev(n[2])
            return None
        if k == "bin":
            a, b = ev(n[2]), ev(n[3])
            o = n[1]
            if o == "+":
                if isinstance(a, str) and isinstance(b, str):
                    return a + b
                assert isinstance(a, float) and isinstance(b, float), (a, b)
                return a + b
            if o == "==":
                return 1.0 if a == b else 0.0
            if o == "!=":
                return 1.0 if a != b else 0.0
            if o == "&&":
                return 1.0 if a and b else 0.0
            if o == "||":
                return 1.0 if a or b else 0.0
            return {"-": lambda: a - b, "*": lambda: a * b, "/": lambda: a / b,
                    "<": lambda: float(a < b), ">": lambda: float(a > b)}[o]()
        if k == "not":
            return 0.0 if ev(n[1]) else 1.0
        if k == "if":
            branch = n[2] if ev(n[1]) else n[3]
            if branch is not None:
                ev(branch)
            return None
        if k == "block":
            for s in n[1]:
                ev(s)
            return None
        raise ValueError(k)

    for stmt in Parser(src).program():
        ev(stmt)


# ------------------------------------------------------------------------------------------------ the world
class Entity:
    def __init__(self, uuid, player=False, gamemode="survival", tags=(), labels=(), catch_rate=3.0,
                 uncatchable=False, capacity=10 ** 6):
        self.uuid, self.player, self.gamemode = uuid, player, gamemode
        self.tags, self.labels, self.catch_rate = set(tags), set(labels), float(catch_rate)
        self.uncatchable, self.capacity = uncatchable, capacity
        self.inv, self.dropped, self.messages = Counter(), Counter(), []

    def struct(self):
        names = {"has_tag": lambda t: 1.0 if t in self.tags else 0.0,
                 "add_tag": lambda t: self.tags.add(t) or 1.0,
                 "remove_tag": lambda t: self.tags.discard(t) or 1.0,
                 "uuid": self.uuid, "is_player": 1.0 if self.player else 0.0}
        if self.player:
            names.update({"is_creative": 1.0 if self.gamemode == "creative" else 0.0, "username": self.uuid})
        allowed = ENTITY_NAMES | (PLAYER_NAMES if self.player else LIVING_NAMES)
        return Struct({k: v for k, v in names.items() if k in allowed})

    def receive(self, item, n):
        """Vanilla /give: what fits goes in, the rest drops at the player's feet for that player alone."""
        room = max(0, self.capacity - sum(self.inv.values()))
        self.inv[item] += min(n, room)
        if n > room:
            self.dropped[item] += n - room


class World:
    def __init__(self, files, over_cap=()):
        self.files = dict(files)
        self.entities = {}
        self.over_cap = set(over_cap)          # thrower uuids the level cap's check finds over their cap
        self.commands, self.gives = [], []
        self.order = None                      # a forced script order, to show the order does not matter

    def add(self, e):
        self.entities[e.uuid] = e
        return e

    # Cobblemon's CobblemonCallbacks.reload sorts each event's scripts by resource path; run() resolves them in
    # turn in one runtime, with the event's context and functions added to `q`.
    def scripts(self, event):
        paths = sorted(p for p in self.files if p.startswith("data/cobblemon/callbacks/%s/" % event))
        if self.order is not None and event == CAPTURE:
            paths = [paths[i] for i in self.order]
        return paths

    def fire(self, event, context, functions):
        q = Struct({**context, **functions, "run_command": lambda c: self.command(c, None) or 1.0})
        temps = {}
        for p in self.scripts(event):
            run_molang(self.files[p], q, temps)

    # ---- the commands the generated files use, and nothing else
    def command(self, cmd, ex):
        self.commands.append(cmd)
        if cmd.startswith("execute "):
            rest = cmd[len("execute "):]
            while True:
                if rest.startswith("as "):
                    sel, rest = rest[3:].split(" ", 1)
                    ex = ex if sel == "@s" else self.entities.get(sel)
                    if ex is None:
                        return        # "No entity was found": nothing runs
                elif rest.startswith("at @s "):
                    rest = rest[len("at @s "):]
                elif rest.startswith(("unless entity ", "if entity ")):
                    neg = rest.startswith("unless")
                    sel, rest = rest.split(" ", 2)[2].split(" ", 1)
                    if self.matches(sel, ex) == neg:
                        return
                elif rest.startswith("run "):
                    return self.command(rest[4:], ex)
                else:
                    raise AssertionError("unmodelled execute clause: %r" % rest)
        if cmd.startswith("function "):
            m = re.match(r"function ([a-z0-9_.-]+:[a-z0-9_./-]+)(?: (\{.*\}))?$", cmd)
            assert m, cmd
            fid, snbt = m.groups()
            args = dict(re.findall(r'(\w+):"([^"]*)"', snbt or ""))
            if fid == "%s:levelcap/check" % levelcap_pack.NS:
                # the level cap's function needs rctmod; its verdict is the tag its callback reads back
                ex.tags.discard(levelcap_pack.OVER)
                if ex.uuid in self.over_cap:
                    ex.tags.add(levelcap_pack.OVER)
                return
            ns, path = fid.split(":", 1)
            body = self.files["data/%s/function/%s.mcfunction" % (ns, path)]
            for line in body.split("\n"):
                if not line.strip() or line.startswith("#"):
                    continue
                if line.startswith("$"):
                    line = re.sub(r"\$\((\w+)\)", lambda mm: args[mm.group(1)], line[1:])
                assert "$(" not in line, line
                self.command(line, ex)
            return
        if cmd.startswith("give "):
            _, sel, item, n = cmd.split(" ")
            assert sel == "@s" and ex is not None, cmd
            assert ex.player, "give targets players only; a give to %s fails" % ex.uuid
            assert item in ALL_BALLS, "give of %r, which is not a Cobblemon ball item" % item
            self.gives.append((ex.uuid, item, int(n)))
            ex.receive(item, int(n))
            return
        if cmd.startswith("tellraw @s "):
            ex.messages.append(json.loads(cmd[len("tellraw @s "):])["text"])
            return
        raise AssertionError("unmodelled command: %r" % cmd)

    def matches(self, sel, ex):
        m = re.match(r"@s\[gamemode=(!?)(\w+)\]$", sel)
        assert m, sel
        hit = ex.gamemode == m.group(2)
        return (not hit) if m.group(1) else hit

    # ---- one throw, as Cobblemon 1.8.0 runs it
    def throw(self, thrower, target, ball):
        # PokeBallItem.use: ItemStack.consume(1, player) does not shrink the stack for infinite materials (creative)
        if not (thrower.player and thrower.gamemode == "creative"):
            assert thrower.inv[ball] >= 1, "nothing to throw"
            thrower.inv[ball] -= 1
        ball_struct = Struct({"ball_type": ball, "capture_state": "NOT"})
        # EmptyPokeBallEntity.onHitEntity: an uncatchable target is refused here: drop() spawns the ball item where it
        # hit (not for a creative thrower) and the capture events never fire
        if target.uncatchable:
            if not (thrower.player and thrower.gamemode == "creative"):
                thrower.dropped[ball] += 1
            return ("dropped_at_hit",)
        # CobblemonCaptureCalculator.processCapture
        if ball in GUARANTEED:
            result = ("success", 4)
        else:
            ev = {"rate": target.catch_rate}
            ctx = {"thrower": thrower.struct(), "poke_ball_entity": ball_struct, "pokemon_entity": target.struct(),
                   "catch_rate": target.catch_rate}         # a snapshot taken in the event's constructor
            fns = {"set_catch_rate": lambda r: ev.__setitem__("rate", float(r)) or 1.0}
            assert set(ctx) == RATE_CONTEXT and set(fns) == RATE_FUNCTIONS
            self.fire(RATE, ctx, fns)
            result = ("roll", ev["rate"] * ball_modifier(ball, target.labels))
        box = {"r": result}

        def set_shakes(n, success=None):   # PokeBallCaptureCalculatedEvent functions$lambda$0
            n = int(n)
            box["r"] = ("success", n) if (success if success is not None else n == 4) else ("fail", n)
            return 1.0

        def set_critical(n=1):             # functions$lambda$1: a forced (critical) success
            box["r"] = ("success", int(n))
            return 1.0
        ctx = {"thrower": thrower.struct(), "pokemon": target.struct(), "poke_ball": ball_struct,
               "is_successful_capture": 1.0 if result[0] == "success" else 0.0, "is_critical_capture": 0.0}
        fns = {"set_shakes": set_shakes, "set_critical_capture": set_critical}
        assert set(ctx) == CAPTURE_CONTEXT and set(fns) == CAPTURE_FUNCTIONS
        self.fire(CAPTURE, ctx, fns)
        # beginCapture -> shakeBall: a failed result ends in breakFree, which discards the ball with no item
        return box["r"]


# ------------------------------------------------------------------------------------------------ fixtures
def key_files(mod=key_ball):
    return mod.build(mod.load(), check_bosses=False)


def folder_files(kb_files):
    """Every pack that writes a poke_ball_capture_calculated script, from its own generator, plus the key pack."""
    files = dict(kb_files)
    files.update(levelcap_pack.files(json.loads((ROOT / "data" / "level_cap.json").read_text(encoding="utf-8"))))
    files.update(hoopa_cradle.callbacks(hoopa_cradle.load()))
    files.update(ursaluna_cave.callback_files(ursaluna_cave.load()))
    return files


@pytest.fixture(scope="module")
def kb():
    return key_files()


DOC = key_ball.load()
TAG = DOC["tag"]
MSG_COUNT = lambda e: len(e.messages)  # noqa: E731


def boss(**kw):
    return Entity("boss", tags={TAG}, catch_rate=3, **kw)


def survivor(uuid="p1", ball=None, n=1, **kw):
    p = Entity(uuid, player=True, **kw)
    if ball:
        p.inv[ball] += n
    return p


# ------------------------------------------------------------------------------------------------ property checks
# Plain functions raising AssertionError, so the mutation tests below can run the same check against a mutant.
def check_refused_and_returned(files, ball):
    w = World(files)
    p = w.add(survivor(ball=ball))
    b = w.add(boss())
    out = w.throw(p, b, ball)
    assert out[0] == "fail", "%s at a dungeon boss was not refused: %r" % (ball, out)
    assert +p.inv == Counter({ball: 1}), "%s: the thrower holds %r afterwards, not the same ball back" % (ball, +p.inv)
    assert not +p.dropped
    assert MSG_COUNT(p) == 1, p.messages


def check_beast_rolls_at_five(files, base=3.0):
    w = World(files)
    p = w.add(survivor(ball=BEAST))
    b = w.add(Entity("boss", tags={TAG}, catch_rate=base))
    out = w.throw(p, b, BEAST)
    assert out == ("roll", base * DOC["multiplier"]), "a Beast Ball at a dungeon boss: %r, want the jar's roll at x%s" % (
        out, DOC["multiplier"])
    assert DOC["multiplier"] == 5
    assert +p.inv == Counter() and not w.gives and not p.messages, "a Beast Ball's allowed throw is consumed"


def check_untagged_untouched(files):
    for labels, want in (((), 1.0), (("ultra_beast",), 5.0), (("legendary",), 1.0)):
        w = World(files)
        p = w.add(survivor(ball=BEAST))
        t = w.add(Entity("wild", labels=labels, catch_rate=45))
        assert w.throw(p, t, BEAST) == ("roll", 45 * want), labels
        assert not w.commands
    w = World(files)
    p = w.add(survivor(ball="cobblemon:master_ball"))
    t = w.add(Entity("lugia", labels=("legendary",), catch_rate=3))
    assert w.throw(p, t, "cobblemon:master_ball") == ("success", 4), "an overworld legendary refused a Master Ball"
    assert not w.commands and not p.messages


def check_no_refund_to_a_non_player(files):
    w = World(files)
    mob = w.add(Entity("zombie", player=False))
    mob.inv["cobblemon:ultra_ball"] = 1
    b = w.add(boss())
    assert w.throw(mob, b, "cobblemon:ultra_ball")[0] == "fail"
    assert not w.commands, "a non-player's refused ball issued %r" % w.commands


def check_creative_makes_no_ball(files):
    for ball in ("cobblemon:master_ball", "cobblemon:poke_ball"):
        w = World(files)
        p = w.add(survivor(ball=ball, gamemode="creative"))
        b = w.add(boss())
        assert w.throw(p, b, ball)[0] == "fail"
        assert +p.inv == Counter({ball: 1}) and not +p.dropped, "creative: %r" % (+p.inv,)


def check_one_refund_whatever_the_order(files):
    paths = World(files).scripts(CAPTURE)
    assert len(paths) == 4, paths
    for over in (False, True):
        for perm in itertools.permutations(range(len(paths))):
            w = World(files, over_cap={"p1"} if over else ())
            w.order = perm
            p = w.add(survivor(ball="cobblemon:master_ball"))
            b = w.add(boss())
            assert w.throw(p, b, "cobblemon:master_ball")[0] == "fail", perm
            assert sum(n for _, _, n in w.gives) == 1, "order %r, over cap %s: %r" % (perm, over, w.gives)
            assert +p.inv == Counter({"cobblemon:master_ball": 1})


def generated_message(files):
    text = files["data/cobblers/function/key_ball/refused.mcfunction"]
    lines = [ln for ln in text.split("\n") if ln.startswith("tellraw ")]
    assert len(lines) == 1, lines
    return json.loads(lines[0].split(" ", 2)[2])["text"]


def hint_vocabulary():
    """Words that would point a player at the key, read from the data that sells and defines it."""
    words = set()

    def add(s):
        words.update(w for w in re.findall(r"[a-z]+", str(s).lower()) if len(w) >= 4)
    add(DOC["key_ball"].split(":", 1)[1].replace("_ball", ""))
    markets = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
    towns = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}
    sellers = 0
    for grp in ("counters", "stalls"):
        for rec in markets.get(grp) or []:
            for it in rec.get("stock") or []:
                if it.get("item") == DOC["key_ball"]:
                    sellers += 1
                    add(it.get("name", "").replace("Ball", ""))
                    add(rec.get("id"))
                    add((rec.get("keeper") or {}).get("name"))
                    add(rec.get("category"))
                    t = towns.get(rec.get("town")) or {}
                    add(t.get("display_name"))
                    add(t.get("region", "").replace("the_", ""))
                    add(t.get("subregion", "").replace("_", " "))
                    words.update({str(it["price"]), "{:,}".format(it["price"])})
    assert sellers >= 1, "nothing sells the key, so the vocabulary is empty"
    for b in DOC["bosses"]:
        bdoc = json.loads((ROOT / b["data"]).read_text(encoding="utf-8"))
        add(bdoc["species"]["id"])
    add("ultra")   # the jar's own label for what the ball is for (PokeBalls: LabelModifier ... "ultra_beast")
    # commerce: this audit's own list, not the builder's
    words.update({"sell", "sells", "sold", "buy", "bought", "shop", "store", "mart", "merchant", "trader", "counter",
                  "price", "dollar", "dollars", "coin", "cost", "market", "vendor"})
    words.discard("ball")
    words.discard("master")
    return words


def check_message_names_nothing(files):
    msg = generated_message(files)
    assert "Even a Master Ball will not close on it." in msg, "the owner's line is gone: %r" % msg
    said = re.findall(r"[a-z0-9,]+", msg.lower())
    vocab = hint_vocabulary()
    hits = sorted({w for w in said for v in vocab if w.strip(",") == v or w.rstrip("s") == v.rstrip("s")})
    assert not hits, "the refusal line hints at the key: %s" % hits
    assert "$" not in msg


def never_passes(cond):
    """Fabric API 0.116.14 semantics (DefaultResourceConditionTypes): the list under fabric:load_conditions must all
    pass; fabric:true passes; fabric:not inverts `value`; and/or take `values`."""
    k = cond.get("condition")
    if k == "fabric:true":
        return False
    if k == "fabric:not":
        return not never_passes(cond["value"])
    if k == "fabric:and":
        return any(never_passes(c) for c in cond["values"])
    if k == "fabric:or":
        return all(never_passes(c) for c in cond["values"])
    raise AssertionError("condition %r is not one this audit can decide" % k)


def check_recipe_closed(files):
    want = {"data/cobblemon/recipe/beast_ball.json", "data/cobblemon/advancement/recipes/balls/beast_ball.json"}
    assert want <= set(files), sorted(files)
    for p in want:
        body = json.loads(files[p])
        assert set(body) == {"fabric:load_conditions"}, "%s carries %s: were the condition ignored it would load" % (
            p, sorted(body))
        conds = body["fabric:load_conditions"]
        assert isinstance(conds, list) and conds
        assert any(never_passes(c) for c in conds), "%s can load: %r" % (p, conds)


def spawned_entei_binds(files):
    """{appear file: [bind function ids]} for every function that spawns an Entei (the boss tool's spawn_at)."""
    out = {}
    for rel, text in files.items():
        if not rel.endswith(".mcfunction"):
            continue
        lines = text.split("\n")
        spawns = [ln for ln in lines if "spawn_at" in ln and 'props:"entei ' in ln]
        if spawns:
            out[rel] = (spawns, re.findall(r"run function (\S+/bind)\b", text))
    return out


def check_every_spawned_entei_is_tagged(files):
    sites = spawned_entei_binds(files)
    assert sites, "no function spawns an Entei: the check has nothing to read"
    for rel, (spawns, binds) in sites.items():
        assert any("uncatchable" in s for s in spawns) and any("uncatchable" not in s for s in spawns), (
            "%s: both the catch-mode and the farm-mode Entei spawn here" % rel)
        assert binds, "%s spawns an Entei and binds nothing" % rel
        for fid in binds:
            ns, path = fid.split(":", 1)
            body = files["data/%s/function/%s.mcfunction" % (ns, path)].split("\n")
            assert "tag @s add %s" % TAG in body, "%s: the Entei it binds is not tagged %s" % (fid, TAG)


# ------------------------------------------------------------------------------------------------ the rules
@pytest.mark.parametrize("ball", [b for b in ALL_BALLS if b != BEAST])
def test_every_ball_but_the_key_is_refused_at_a_dungeon_boss_and_the_same_ball_comes_back(kb, ball):
    # breaks if a ball (the Master Ball, the guaranteed Ancient Origin Ball) catches a boss or comes back as another ball
    check_refused_and_returned(kb, ball)


def test_a_beast_ball_at_a_dungeon_boss_rolls_at_five_times_and_is_never_forced(kb):
    # breaks if the key is not x5, is forced into a catch, or is refunded (free retries)
    check_beast_rolls_at_five(kb, 3.0)
    check_beast_rolls_at_five(kb, 45.0)


def test_an_untagged_pokemon_and_an_overworld_legendary_are_untouched(kb):
    # breaks if the key's rate or refusal leaks to anything not carrying the boss tag
    check_untagged_untouched(kb)


def test_a_ball_thrown_by_a_non_player_refunds_nobody(kb):
    # breaks if the refund runs for a thrower that is not a player (a give with no player target)
    check_no_refund_to_a_non_player(kb)


def test_a_creative_throw_neither_costs_nor_makes_a_ball(kb):
    # breaks if a creative player's refused throw gives a ball the throw never took
    check_creative_makes_no_ball(kb)


def test_two_players_each_get_their_own_ball_back(kb):
    # breaks if the refund goes to anyone but the thrower of that ball
    w = World(kb)
    a = w.add(survivor("pa", ball="cobblemon:master_ball"))
    b = w.add(survivor("pb", ball="cobblemon:ultra_ball"))
    e = w.add(boss())
    w.throw(a, e, "cobblemon:master_ball")
    w.throw(b, e, "cobblemon:ultra_ball")
    assert +a.inv == Counter({"cobblemon:master_ball": 1}) and +b.inv == Counter({"cobblemon:ultra_ball": 1})


def test_one_refused_throw_gives_back_exactly_one_ball_whatever_the_folder_order(kb):
    # breaks if two capture scripts both refund, or if a refusal depends on which script runs last
    check_one_refund_whatever_the_order(folder_files(kb))


def test_no_capture_script_in_the_folder_can_force_a_catch(kb):
    # breaks if any pack's poke_ball_capture_calculated script sets a success, which would make the order matter
    files = folder_files(kb)
    caps = [p for p in files if p.startswith("data/cobblemon/callbacks/%s/" % CAPTURE)]
    for p in caps:
        src = files[p]
        assert "set_critical_capture" not in src, p
        for arg in re.findall(r"set_shakes\(([^)]*)\)", src):
            assert arg.strip() == "0", "%s: set_shakes(%s)" % (p, arg)
    rates = [p for p in files if p.startswith("data/cobblemon/callbacks/%s/" % RATE)]
    assert rates == [key_ball.CALLBACK % RATE], rates


def test_every_generator_that_writes_these_callbacks_is_in_the_folder_model():
    # breaks if a new pack starts writing a capture or catch-rate script this audit's order model does not run
    names = {p.stem for p in TOOLS.glob("*.py") if not p.stem.endswith("_audit")
             and re.search(r"callbacks/[%a-z_]*", p.read_text(encoding="utf-8"))
             and (CAPTURE in p.read_text(encoding="utf-8") or RATE in p.read_text(encoding="utf-8"))}
    assert names - {"reapply"} == {"key_ball", "levelcap_pack", "hoopa_cradle", "ursaluna_cave"}, sorted(names)


def test_the_level_cap_and_the_key_refusing_one_throw_refund_it_once(kb):
    # breaks if a Master Ball at an over-cap boss is refunded twice (both refuse) or not at all
    w = World(folder_files(kb), over_cap={"p1"})
    p = w.add(survivor(ball="cobblemon:master_ball"))
    w.add(boss())
    assert w.throw(p, w.entities["boss"], "cobblemon:master_ball")[0] == "fail"
    assert +p.inv == Counter({"cobblemon:master_ball": 1})


@pytest.mark.xfail(strict=True, reason="KNOWN GAP (data/key_ball.json does_not_cover[0]): the level cap refuses a "
                   "Beast Ball at an over-cap dungeon boss and nothing gives it back. Never bites for Entei (level 100, "
                   "post-Champion cap 100); bites the first key boss placed above a gate's cap")
def test_a_beast_ball_the_level_cap_refuses_at_a_dungeon_boss_comes_back(kb):
    # breaks (xpasses) the day the gap is closed: then make it a plain test
    w = World(folder_files(kb), over_cap={"p1"})
    p = w.add(survivor(ball=BEAST))
    w.add(boss())
    assert w.throw(p, w.entities["boss"], BEAST)[0] == "fail"
    assert +p.inv == Counter({BEAST: 1}), "the refused Beast Ball is gone"


def test_a_refund_to_a_full_inventory_drops_for_the_thrower_and_is_not_lost(kb):
    # breaks if the refund is a command that loses the ball when there is no room (vanilla give drops the rest)
    w = World(kb)
    p = w.add(survivor(ball="cobblemon:master_ball", capacity=0))   # no room left when the refund arrives
    w.add(boss())
    w.throw(p, w.entities["boss"], "cobblemon:master_ball")
    assert p.dropped["cobblemon:master_ball"] == 1 and p.inv["cobblemon:master_ball"] == 0


def test_the_farm_entei_refuses_at_the_hit_and_only_cobblemon_returns_the_ball(kb):
    # breaks if our refund also fires for the uncatchable farm Entei (Cobblemon already drops the ball: a duplicate)
    w = World(folder_files(kb))
    p = w.add(survivor(ball="cobblemon:master_ball"))
    e = w.add(boss(uncatchable=True))
    assert w.throw(p, e, "cobblemon:master_ball") == ("dropped_at_hit",)
    assert not w.commands
    assert p.inv["cobblemon:master_ball"] + p.dropped["cobblemon:master_ball"] == 1


def test_every_entei_the_boss_tool_spawns_carries_the_key_tag():
    # breaks if a spawn path of the dungeon boss (catch or farm mode) binds an Entei without the shared tag
    check_every_spawned_entei_is_tagged(entei_boss.build(entei_boss.load()))


def test_only_dungeon_bosses_carry_the_key_tag():
    # breaks if anything but a boss tool data/key_ball.json names puts the tag on a Pokemon (an overworld legendary)
    owners = {b["tool"] for b in DOC["bosses"]} | {"tools/key_ball.py"}
    hits = set()
    for p in list(TOOLS.glob("*.py")) + list((ROOT / "data").rglob("*.json")) + list((ROOT / "kits").rglob("*.json")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if TAG in text or "boss_tag(" in text:
            hits.add(p.relative_to(ROOT).as_posix())
    assert hits - {"data/key_ball.json"} <= owners, sorted(hits - owners)


def test_the_refusal_line_names_nothing(kb):
    # breaks if the generated line names the key, where it is sold, its price, the boss or a shop word
    check_message_names_nothing(kb)


def test_the_beast_ball_recipe_and_its_unlock_never_load(kb):
    # breaks if the override can load (the recipe makes 8 Beast Balls) or would load were its condition ignored
    check_recipe_closed(kb)


def test_blackout_never_claims_a_beast_ball():
    # breaks if a blackout can take a $5,000 key ball
    doc = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + [k])
        elif isinstance(o, list):
            assert BEAST not in o, "data/blackout.json %s lists %s" % (".".join(path), BEAST)
            for v in o:
                walk(v, path)
    walk(doc.get("claims") or {}, ["claims"])


# ------------------------------------------------------------------------------------------------ the economy
def shelf_lines(markets):
    for grp in ("counters", "stalls"):
        for rec in markets.get(grp) or []:
            for it in rec.get("stock") or []:
                yield grp, rec, it


def check_master_ball_above_every_shelf(markets):
    plain = [(it["price"] / (it.get("count") or 1), rec["id"], it["id"]) for _, rec, it in shelf_lines(markets)
             if "exchange_for" not in it]
    masters = [it["price"] / (it.get("count") or 1) for _, rec, it in shelf_lines(markets)
               if it.get("item") == "cobblemon:master_ball"]
    assert masters, "nothing sells a Master Ball"
    top = max(plain)
    for m in masters:
        assert m > top[0], "the Master Ball at $%g is not dearer than %s %s at $%g" % (m, top[1], top[2], top[0])
    return top


def test_the_master_ball_stays_dearer_than_every_shelf_line_with_the_beast_ball_added():
    # breaks if the key ball (or anything) is priced at or above the Master Ball, inverting the ball ladder
    markets = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
    check_master_ball_above_every_shelf(markets)
    beast = [(rec, it) for _, rec, it in shelf_lines(markets) if it.get("item") == BEAST]
    assert len(beast) == 1, "the key is sold at %d lines" % len(beast)
    rec, it = beast[0]
    towns = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}
    assert towns[rec["town"]]["display_name"] == "Cinderlee" and rec.get("status") == "sited"
    assert (it["price"], it.get("count")) == (5000, 1) and "exchange_for" not in it


def test_the_floor_check_bites_when_the_key_outprices_the_master_ball():
    # breaks if the floor check passes a shelf line dearer than the Master Ball (a check that cannot fail)
    markets = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
    for _, rec, it in shelf_lines(markets):
        if it.get("item") == BEAST:
            it["price"] = 30000
    with pytest.raises(AssertionError):
        check_master_ball_above_every_shelf(markets)


def test_no_bank_buys_a_ball_back():
    # breaks if a refunded (or bought) ball can be sold for dollars: a refund loop would then mint money
    bank = json.loads((ROOT / "data" / "bank.json").read_text(encoding="utf-8"))
    assert not [b["item"] for b in bank["buys"] if b["item"] in ALL_BALLS]
    cfg = ROOT / "modpack" / "config" / "cobbledollars" / "bank.json"
    if cfg.is_file():
        assert not [b["item"] for b in json.loads(cfg.read_text(encoding="utf-8"))["bank"] if b["item"] in ALL_BALLS]


# ------------------------------------------------------------------------------------------------ the jars
def walk_zip(zf, label, depth=0):
    for info in zf.infolist():
        n = info.filename
        if n.endswith((".jar", ".zip")) and depth < 4:
            try:
                yield from walk_zip(zipfile.ZipFile(io.BytesIO(zf.read(n))), label + "!" + n, depth + 1)
            except zipfile.BadZipFile:
                pass
        elif not n.endswith("/"):
            yield label, n, zf


@pytest.mark.skipif(not COBBLEMON_JAR.is_file(), reason="the offline server snapshot is local only")
def test_the_closed_files_shadow_the_only_recipe_that_makes_a_beast_ball(kb):
    # breaks if a second recipe (any jar, nested jars, any datapack) yields the key, or the closed paths miss the jar's
    makers, adv = set(), set()
    roots = list((SNAPSHOT / "mods").glob("*.jar")) + list((SNAPSHOT / "datapacks").glob("*.zip"))
    for path in roots:
        for label, n, zf in walk_zip(zipfile.ZipFile(path), path.name):
            parts = n.split("/")
            if len(parts) < 4 or parts[0] != "data" or not n.endswith(".json"):
                continue
            if parts[2] in ("recipe", "recipes"):
                body = zf.read(n).decode("utf-8", "ignore")
                if BEAST not in body:
                    continue
                res = json.loads(body).get("result")
                if res is not None and BEAST in json.dumps(res):
                    makers.add((label, "data/%s/recipe/%s" % (parts[1], "/".join(parts[3:]))))
            elif parts[2] == "advancement" and n.endswith("/recipes/balls/beast_ball.json"):
                adv.add("data/%s/advancement/%s" % (parts[1], "/".join(parts[3:])))
    assert {p for _, p in makers} == {"data/cobblemon/recipe/beast_ball.json"}, sorted(makers)
    assert all(lbl == COBBLEMON_JAR.name for lbl, _ in makers)
    assert adv and adv <= set(kb), sorted(adv)


@pytest.mark.skipif(not FABRIC_API_JAR.is_file(), reason="the offline server snapshot is local only")
def test_the_condition_keys_are_the_ones_fabric_api_reads():
    # breaks if the override's keys are not Fabric API 0.116.14's (the file would then fail to parse, not be skipped)
    outer = zipfile.ZipFile(FABRIC_API_JAR)
    name = [n for n in outer.namelist() if "fabric-resource-conditions-api-v1" in n and n.endswith(".jar")]
    assert len(name) == 1, name
    rc = zipfile.ZipFile(io.BytesIO(outer.read(name[0])))
    base = "net/fabricmc/fabric/"
    assert b"fabric:load_conditions" in rc.read(base + "api/resource/conditions/v1/ResourceConditions.class")
    assert b"condition" in rc.read(base + "api/resource/conditions/v1/ResourceCondition.class")
    types_ = rc.read(base + "impl/resource/conditions/DefaultResourceConditionTypes.class")
    assert b"\x00\x04true" in types_ and b"\x00\x03not" in types_
    assert b"\x00\x05value" in rc.read(base + "impl/resource/conditions/conditions/NotResourceCondition.class")
    mixins = json.loads(rc.read("fabric-resource-conditions-api-v1.mixins.json"))["mixins"]
    assert {"JsonDataLoaderMixin", "RecipeManagerMixin", "ServerAdvancementLoaderMixin"} <= set(mixins)


# ------------------------------------------------------------------------------------------------ mutations
def mutant(module, old, new):
    """`module`'s generator with one edit to its CODE (the data untouched), imported fresh."""
    path = TOOLS / (module.__name__ + ".py")
    src = path.read_text(encoding="utf-8")
    assert src.count(old) == 1, "the mutation's anchor %r is not unique in %s" % (old, path.name)
    m = types.ModuleType(module.__name__ + "_mutant")
    m.__file__ = str(path)
    exec(compile(src.replace(old, new), str(path), "exec"), m.__dict__)
    return m


KB_MUTATIONS = [
    ("refusal lets the ball hold", '"    q.set_shakes(0);",', '"    q.set_shakes(4);",',
     lambda f: check_refused_and_returned(f, "cobblemon:master_ball")),
    ("the key is refused too", '"    t.key = 1;",', '"    t.key = 0;",', lambda f: check_beast_rolls_at_five(f)),
    ("x5 becomes +5", 'q.set_catch_rate(q.catch_rate * %s);', 'q.set_catch_rate(q.catch_rate + %s);',
     lambda f: check_beast_rolls_at_five(f)),
    ("the rate leaks past the tag", '"t.pk = q.pokemon_entity;",\n            "t.pk.has_tag(\'%s\') ? {" % tag,',
     '"t.pk = q.pokemon_entity;",\n            "1 ? {",', check_untagged_untouched),
    ("the refund is another ball", "give @s $(ball) %d", "give @s cobblemon:poke_ball %d",
     lambda f: check_refused_and_returned(f, "cobblemon:master_ball")),
    ("the refund gives two", '% (ref["skip_gamemode"], ref["ball_count"])', '% (ref["skip_gamemode"], 2)',
     lambda f: check_one_refund_whatever_the_order(folder_files(f))),
    ("creative is refunded", '% (ref["skip_gamemode"], ref["ball_count"])', '% ("spectator", ref["ball_count"])',
     check_creative_makes_no_ball),
    ("non-players are refunded", '"    t.th.is_player ? {",', '"    1 ? {",', check_no_refund_to_a_non_player),
    ("the line names the shop", 'msg = json.dumps({"text": doc["message"],',
     'msg = json.dumps({"text": doc["message"] + " Cinderlee sells the cure.",', check_message_names_nothing),
    ("the recipe stays open", '[doc["recipe_off"]["condition"]]', '[{"condition": "fabric:true"}]',
     check_recipe_closed),
]


@pytest.mark.parametrize("label,old,new,check", KB_MUTATIONS, ids=[m[0] for m in KB_MUTATIONS])
def test_each_key_ball_check_fails_against_a_mutated_generator(kb, label, old, new, check):
    # breaks if a check above cannot tell the generator from a broken one (it would pass a shared derivation)
    check(kb)                                   # the real generator passes
    files = key_files(mutant(key_ball, old, new))
    with pytest.raises((AssertionError, KeyError, NameError)):
        check(files)


def test_the_spawn_tag_check_fails_against_a_boss_tool_that_forgets_the_tag():
    # breaks if the spawn-to-tag check would pass a boss tool that binds an untagged Entei
    m = mutant(entei_boss, '"tag @s add %s" % key_tag,', '"say %s" % key_tag,')
    with pytest.raises(AssertionError):
        check_every_spawned_entei_is_tagged(m.build(m.load()))
