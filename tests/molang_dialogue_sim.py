"""A small simulator for the Molang tools/compile_dialogue.py emits, and for the handful of commands that Molang runs.

It exists so a multiplayer scenario can be played OFFLINE against the compiled output: several players, one world, each
player's own data and tags, one scoreboard, and the NPCs standing in it. It is not Minecraft. It runs exactly the
subset the compiler writes (statements, assignments, `cond ? { } : { }`, string `+`, && || !, == !=), and exactly the
commands the compiler's world constructs write; ANY other command raises, so a compiler change that writes a command
this file does not know fails loudly instead of being skipped. What it cannot say is whether Minecraft accepts a
command or how Cobblemon's dialogue screen behaves when its NPC moves: that needs a running server.
"""
import re
from collections import Counter

TOKEN = re.compile(r"\s*(?:('(?:[^'\\]|\\.)*')|(\d+(?:\.\d+)?)|([A-Za-z_][A-Za-z0-9_.]*)|(&&|\|\||==|!=|[?:(){};,=+!]))")


def tokenize(src):
    out, i = [], 0
    src = src.rstrip()
    while i < len(src):
        m = TOKEN.match(src, i)
        if not m:
            raise SyntaxError("molang: cannot tokenize at %r" % src[i:i + 40])
        i = m.end()
        s, n, ident, op = m.groups()
        out.append(("s", s[1:-1].replace("\\'", "'")) if s is not None else ("n", n) if n is not None else
                   ("i", ident) if ident is not None else ("o", op))
    return out


class Parser:
    """Molang subset -> Python source. Variables: V (the dialogue's v.*), D (the player's data, t.d.*)."""

    def __init__(self, src):
        self.t, self.p, self.lines = tokenize(src), 0, []

    def peek(self, k=0):
        return self.t[self.p + k] if self.p + k < len(self.t) else (None, None)

    def eat(self, val=None):
        tok = self.peek()
        if val is not None and tok[1] != val:
            raise SyntaxError("molang: expected %r, got %r near %r" % (val, tok, self.t[max(0, self.p - 3):self.p + 3]))
        self.p += 1
        return tok

    # expressions -> python expression strings
    def ternary(self):
        c = self.orexp()
        if self.peek() == ("o", "?") and self.peek(1) != ("o", "{"):
            self.eat("?")
            a = self.ternary()
            self.eat(":")
            b = self.ternary()
            return "(%s if %s else %s)" % (a, c, b)
        return c

    def orexp(self):
        e = self.andexp()
        while self.peek() == ("o", "||"):
            self.eat()
            e = "(%s or %s)" % (e, self.andexp())
        return e

    def andexp(self):
        e = self.eqexp()
        while self.peek() == ("o", "&&"):
            self.eat()
            e = "(%s and %s)" % (e, self.eqexp())
        return e

    def eqexp(self):
        e = self.addexp()
        while self.peek()[0] == "o" and self.peek()[1] in ("==", "!="):
            op = self.eat()[1]
            e = "(%s %s %s)" % (e, op, self.addexp())
        return e

    def addexp(self):
        e = self.unary()
        while self.peek() == ("o", "+"):
            self.eat()
            e = "(str(%s) + str(%s))" % (e, self.unary())
        return e

    def unary(self):
        if self.peek() == ("o", "!"):
            self.eat()
            return "(not %s)" % self.unary()
        return self.primary()

    def primary(self):
        kind, val = self.eat()
        if kind == "s":
            return repr(val)
        if kind == "n":
            return val
        if kind == "o" and val == "(":
            e = self.ternary()
            self.eat(")")
            return "(%s)" % e
        if kind != "i":
            raise SyntaxError("molang: unexpected %r" % (val,))
        if self.peek() == ("o", "("):
            self.eat("(")
            args = []
            while self.peek() != ("o", ")"):
                args.append(self.ternary())
                if self.peek() == ("o", ","):
                    self.eat()
            self.eat(")")
            return "%s(%s)" % (self.call_name(val), ", ".join(args))
        return self.read_var(val)

    @staticmethod
    def call_name(name):
        table = {"q.player.has_tag": "HAS_TAG", "q.player.save_data": "SAVE", "q.dialogue.close": "CLOSE",
                 "q.dialogue.set_page": "SET_PAGE", "q.run_command": "CMD", "q.player.data": "DATA"}
        if name not in table:
            raise SyntaxError("molang: unsupported call %s" % name)
        return table[name]

    @staticmethod
    def read_var(name):
        if name == "q.player.uuid":
            return "UUID"
        if name == "t.d":
            return "D"
        if name.startswith("t.d."):
            return "D.get(%r, 0)" % name[4:]
        if name.startswith("v."):
            return "V.get(%r, 0)" % name[2:]
        raise SyntaxError("molang: unsupported variable %s" % name)

    # statements -> self.lines
    def block(self, depth):
        self.eat("{")
        n0 = len(self.lines)
        while self.peek() != ("o", "}"):
            self.stmt(depth)
        self.eat("}")
        if len(self.lines) == n0:
            self.lines.append("    " * depth + "pass")

    def stmt(self, depth):
        ind = "    " * depth
        if self.peek()[0] == "i" and self.peek(1) == ("o", "="):
            name = self.eat()[1]
            self.eat("=")
            val = self.ternary()
            self.eat(";")
            if name == "t.d":
                self.lines.append(ind + "pass")
            elif name.startswith("t.d."):
                self.lines.append(ind + "D[%r] = %s" % (name[4:], val))
            elif name.startswith("v."):
                self.lines.append(ind + "V[%r] = %s" % (name[2:], val))
            else:
                raise SyntaxError("molang: cannot assign %s" % name)
            return
        e = self.ternary_head()
        if self.peek() == ("o", "?"):
            self.eat("?")
            self.lines.append(ind + "if %s:" % e)
            self.block(depth + 1)
            if self.peek() == ("o", ":"):
                self.eat(":")
                self.lines.append(ind + "else:")
                self.block(depth + 1)
            if self.peek() == ("o", ";"):
                self.eat(";")
            return
        self.lines.append(ind + e)
        if self.peek() == ("o", ";"):
            self.eat(";")

    def ternary_head(self):
        return self.orexp()

    def program(self):
        while self.p < len(self.t):
            self.stmt(0)
        return "\n".join(self.lines) or "pass"


_CACHE = {}


def compile_molang(src):
    if src not in _CACHE:
        _CACHE[src] = compile(Parser(src).program(), "<molang>", "exec")
    return _CACHE[src]


class Npc:
    def __init__(self, nid, x, y, z):
        self.id, self.pos, self.tags = nid, (x + 0.5, y, z + 0.5), set()


class Player:
    def __init__(self, name):
        self.name, self.data, self.tags, self.inv, self.scores = name, {}, set(), Counter(), {}


class World:
    """The shared state: the scoreboard (objectives, fake-player scores), every player, every NPC, a log of commands."""

    def __init__(self):
        self.objectives, self.scores, self.players, self.npcs, self.errors = set(), {}, {}, [], []
        # function id -> its command lines, filled by a test from a generated pack (tools/scenes_pack.py build()); only
        # `scoreboard players set @s <objective> <n>` lines are run, as the player the function was called as
        self.functions = {}

    def run_molang(self, p, src):
        """Run Molang that is not a dialogue's (a scene zone's `runmolang`) as the player p."""
        env = {"V": {}, "D": p.data, "UUID": p.name, "HAS_TAG": lambda t: t in p.tags, "SAVE": lambda: None,
               "DATA": lambda: p.data, "CMD": lambda c: self.command(c), "CLOSE": lambda: None, "SET_PAGE": lambda pid: None}
        exec(compile_molang(src), env)

    def player(self, name):
        return self.players.setdefault(name, Player(name))

    @staticmethod
    def in_range(val, rng):
        if val is None:
            return False
        lo, _, hi = rng.partition("..")
        if ".." not in rng:
            return val == int(lo)
        return (not lo or val >= int(lo)) and (not hi or val <= int(hi))

    def holds(self, mode, holder, obj, rng, me=None):
        if obj not in self.objectives:
            raise RuntimeError("an `execute %s score` on the unknown objective %s: Minecraft fails the whole command" % (mode, obj))
        val = (me.scores if holder == "@s" else self.scores).get((holder, obj) if holder != "@s" else obj)
        hit = self.in_range(val, rng)
        return hit if mode == "if" else not hit

    def command(self, text, caller=None):
        t = text.strip()
        m = re.fullmatch(r"scoreboard objectives add (\S+) dummy", t)
        if m:
            self.objectives.add(m.group(1))
            return
        m = re.fullmatch(r"scoreboard players set (\S+) (\S+) (-?\d+)", t)
        if m:
            self.scores[(m.group(1), m.group(2))] = int(m.group(3))
            return
        m = re.fullmatch(r"tag (\S+) (add|remove) (\S+)", t)
        if m:
            p = self.players[m.group(1)]
            (p.tags.add if m.group(2) == "add" else p.tags.discard)(m.group(3))
            return
        m = re.fullmatch(r"execute as (\S+) (if|unless) score (\S+) (\S+) matches (\S+) run tag @s add (\S+)", t)
        if m:
            p = self.players[m.group(1)]
            if self.holds(m.group(2), m.group(3), m.group(4), m.group(5), p):
                p.tags.add(m.group(6))
            return
        m = re.fullmatch(r"execute (if|unless) score (\S+) (\S+) matches (\S+) run scoreboard players set (\S+) (\S+) (-?\d+)", t)
        if m:
            if self.holds(m.group(1), m.group(2), m.group(3), m.group(4)):
                self.scores[(m.group(5), m.group(6))] = int(m.group(7))
            return
        m = re.fullmatch(r"execute as (\S+) store success score @s (\S+) run give @s (\S+) (\d+)", t)
        if m:
            p = self.players[m.group(1)]
            p.inv[m.group(3)] += int(m.group(4))
            p.scores[m.group(2)] = 1
            return
        m = re.fullmatch(r"execute as (\S+) unless score @s (\S+) matches (\S+) run tag @s add (\S+)", t)
        if m:
            p = self.players[m.group(1)]
            if self.holds("unless", "@s", m.group(2), m.group(3), p):
                p.tags.add(m.group(4))
            return
        m = re.fullmatch(r"execute as @e\[type=cobblemon:npc,x=(-?\d+),y=(-?\d+),z=(-?\d+),distance=\.\.2,limit=1\] run tag @s add (\S+)", t)
        if m:
            x, y, z = map(int, m.groups()[:3])
            near = [n for n in self.npcs if sum((a - b) ** 2 for a, b in zip(n.pos, (x, y, z))) ** 0.5 <= 2]
            if near:
                near[0].tags.add(m.group(4))
            return
        m = re.fullmatch(r"tp @e\[type=cobblemon:npc,tag=(\S+),limit=1\] (\S+) (\S+) (\S+) (-?\d+) 0", t)
        if m:
            tagged = [n for n in self.npcs if m.group(1) in n.tags]
            if tagged:
                tagged[0].pos = (float(m.group(2)), float(m.group(3)), float(m.group(4)))
            return
        m = re.fullmatch(r"execute as (\S+) run tag @s (add|remove) (\S+)", t)      # tag_player / untag_player
        if m:
            p = self.players[m.group(1)]
            (p.tags.add if m.group(2) == "add" else p.tags.discard)(m.group(3))
            return
        m = re.fullmatch(r"execute as (\S+) at @s run function (\S+)", t)          # scene_function
        if m:
            p = self.players[m.group(1)]
            if m.group(2) not in self.functions:
                raise RuntimeError("function %s is not in the pack the test loaded" % m.group(2))
            for line in self.functions[m.group(2)]:
                if line.startswith("#"):
                    continue
                mm = re.fullmatch(r"scoreboard players set @s (\S+) (-?\d+)", line)
                if not mm:
                    raise RuntimeError("the simulator does not run this function line: %r" % line)
                p.scores[mm.group(1)] = int(mm.group(2))
            return
        raise RuntimeError("the simulator does not know this command (a compiler change?): %r" % t)


class Dialogue:
    """One open conversation of one player: the page on show, and whether it has closed."""

    def __init__(self, world, player, doc):
        self.world, self.player, self.doc = world, player, doc
        self.pages = {p["id"]: p for p in doc["pages"]}
        self.page, self.closed, self.V = None, False, {}
        self._run(doc["initializationAction"])
        self.shown = [self.page] if self.page else []

    def _run(self, src):
        w, p = self.world, self.player
        env = {"V": self.V, "D": p.data, "UUID": p.name,
               "HAS_TAG": lambda t: t in p.tags, "SAVE": lambda: None, "DATA": lambda: p.data,
               "CMD": lambda c: w.command(c), "CLOSE": self._close, "SET_PAGE": self._set_page}
        exec(compile_molang(src), env)

    def _close(self):
        self.closed, self.page = True, None

    def _set_page(self, pid):
        if pid not in self.pages:
            raise RuntimeError("set_page(%r): no such page in this dialogue" % (pid,))
        self.page, self.closed = pid, False

    def ack(self):
        """The player clicks through the page on show. Returns the page now on show, or None once the dialogue closed."""
        if self.page is None:
            return None
        self.V.clear()
        src = self.pages[self.page]["input"]
        self.page = None
        self._run(src)
        if self.page:
            self.shown.append(self.page)
        return self.page
