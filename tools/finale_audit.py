#!/usr/bin/env python
"""Independent audit of the Rift finale: the HQ chain (Nia, Brann, Oren, Elara), the two fights, the release.

Written by test-author, 2026-10-04, who did not build what it audits; re-pointed the same day by a second test-author
to the reconciled finale (commit 62b953c, merged at 9c51444): ONE Brann and ONE Elara, each a Cobblemon NPC in the HQ
tower who talks AND fights (a `simple` party compiled by tools/compile_dialogue.py, `q.npc.start_battle`), each win
recorded by the cobblers_hq_tower battle_victory callback, and the release at cradle_open.

WHAT IT READS. The EMITTED packs under --packs (default build/datapacks), never the generators' functions:
  cobblers_dialogue           the five compiled conversations of the chain, EXECUTED by this file's Molang interpreter;
                              Brann's and Elara's NPC classes (their parties)
  cobblers_hq_tower           the battle_victory callback, EXECUTED with NPC and player entities; won_brann/won_elara;
                              the gate cycle, EXECUTED for players at every stage
  cobblers_progression        the flag's advancement (must be impossible to earn) and its grant function
  cobblers_relic_underground  release_fx; the carve functions REPLAYED over the cradle (the binder's stand) when built
  cobblers_rift_zones         z5's zone/admit/turn_back, EXECUTED by this file's own command model
  cobblers_levelcap           battle_check and party_compare, EXECUTED: each fight's choice runs them first (U54), with
                              the model player's RCT cap (MODEL_CAP, or none) and party's highest level; check_over_cap
  every pack                  swept for anything that grants the flag, writes a defeat field, calls a won function, or
                              writes a chain stage
and the Cobblemon 1.8 jar (species learnsets and abilities, held items), under experiments/EXP-000-*/runtime/server/mods.
Where each NPC stands is what step R18HQ places: tools/hq_tower.py npc_placements(), at (x + 0.5, y, z + 0.5)
(tools/reapply.py's `tp ... %d.5 %d %d.5` after spawnnpcat) -- the placement, not the callback's selector.

WHERE THE EXPECTATIONS COME FROM (none from the artifact being checked):
  the integrating session's brief (2026-10-04) and the finale doc's scenes: the stage chain CHAIN below -- Nia
      rift_crisis_pending -> deep_handoff_received; Brann's fight, then hq_crossed only with brann_defeated; Oren
      hq_crossed -> anchor_shutdown; Elara's fight, then cradle_open only with elara_defeated; the binder's "Release
      Hoopa." and rift_crisis_resolved only at cradle_open with both fields. The door opens at deep_handoff_received,
      the climb above the briefing hall at hq_crossed, each for every later stage
  data/finale_trainers.json: each fight's team (the party must equal it), display names
  data/progression.json: the stage enum (every value walked) and the two fields' declarations
  the level cap after gym 8: RCT's own rule over the first Elite Four member in data/trainers.json
  data/hq_tower.json: the tower's box and storey floors (where the gate test stands its players)
  data/relic_underground.json: the cradle's centre, radius and floor, the binder's stand
  data/rift_zones.json: z5's pass

THE CONVERSATION WALK. For each of the chain's five conversations, every start state -- every stage value and unset,
each defeat field unset/0/1, the flag held or not, and the conversation's cursor unset, at each page that acts, and at
its last page -- is opened, and every reachable page, acknowledge and visible option is taken, including re-opening
after each change and, when a choice starts the NPC's battle, both outcomes: a loss (nothing changes) and a win (the
EMITTED callback run for that NPC at its placed spot). Every stage write, defeat-field write, battle start, flag grant
and visible "Release Hoopa." is recorded with the state it happened in. Then the joint story walk: from a player at
rift_crisis_pending, all five conversations in any order until nothing new is reached.

THE DOOR KEEPER (re-pointed 2026-10-05 by a second test-author for c2ef17c, "Elara at the HQ door"): her compiled
conversation run by a player standing in front of her, every action directly from every stage, and the emitted gate
cycle run on the players her moves leave; the door stages come from data/hq_tower.json's door GATE. check_door_keeper.

WHAT IT DOES NOT COVER. Nothing here ran in Minecraft: that a choice opens the battle, that `t.l.uuid` and
`t.w.player.uuid` are what Cobblemon 1.8 exposes to a battle_victory callback, that the class's party fights at its
levels, that a loss runs the blackout pack's NPC-loss path (only the sweep says it writes no defeat field), that the
gate tp lands where the model puts it. The tower's blocks are tools/hq_tower_audit.py's. Move legality is "in the
species' or a pre-evolution's list in the jar at or below the Pokemon's level, or by TM/tutor/egg".

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
import zlib
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PACKS = ROOT / "build" / "datapacks"

# ---- the contract, from the integrating session's brief and the finale doc (not from any generator)
FLAG = "rift_crisis_resolved"
FLAG_ADV = "cobblers:flag/%s" % FLAG
FLAG_GRANT_FN = "cobblers:flag/%s/grant" % FLAG
QUEST = "main_worldshift_reveal"
STAGE = "quest.%s.stage" % QUEST
PENDING = "rift_crisis_pending"
RELEASE_STAGE = "cradle_open"
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

# the finale's order: the stage each scene reads, the one it writes, and what the write needs besides the stage
ORDER = [PENDING, "deep_handoff_received", "hq_crossed", "anchor_shutdown", RELEASE_STAGE, RELEASED,
         "league_recognized"]
CHAIN = [
    {"who": "nia", "conv": "dlg_main_finale_nia", "npc": "npc_finale_nia_calder",
     "from": PENDING, "to": "deep_handoff_received", "needs": ()},
    {"who": "brann", "conv": "dlg_main_finale_brann", "npc": "npc_finale_brann_saye",
     "from": "deep_handoff_received", "to": "hq_crossed", "needs": (BRANN_FIELD,), "fight": BRANN_FIELD},
    {"who": "oren", "conv": "dlg_main_finale_oren", "npc": "npc_finale_oren_pell",
     "from": "hq_crossed", "to": "anchor_shutdown", "needs": ()},
    {"who": "elara", "conv": "dlg_main_finale_elara", "npc": "npc_finale_elara_venn",
     "from": "anchor_shutdown", "to": RELEASE_STAGE, "needs": (ELARA_FIELD,), "fight": ELARA_FIELD},
    {"who": "binder", "conv": CONV, "npc": "npc_main_relic_hall_binder",
     "from": RELEASE_STAGE, "to": RELEASED, "needs": (BRANN_FIELD, ELARA_FIELD), "grants": True},
]
FIGHTS = {c["who"]: c for c in CHAIN if c.get("fight")}
WON_FN = {"brann": "cobblers:hq_tower/won_brann", "elara": "cobblers:hq_tower/won_elara"}
CALLBACK = "cobblers_hq_tower/data/cobblemon/callbacks/battle_victory/cobblers_hq_tower.molang"
DOOR_OPEN = set(ORDER[1:])          # the tower door: deep_handoff_received and every later stage
CLIMB_OPEN = set(ORDER[2:])         # above the briefing hall: hq_crossed and every later stage
# the model player's RCT level cap: the finale comes after gym 8, where the cap is 60 (level_cap_after_gym8(), pinned by
# tests/test_finale_audit.py). The value only has to be a real cap; the over-cap check (check_over_cap) is rctmod's
# rule -- a party whose highest level is STRICTLY over the cap is refused -- not anything a generator computes
MODEL_CAP = 60


def key(field):
    """The player-data key a quest field is stored under (docs: compile_dialogue's 'state' contract, EXP-022)."""
    return "cobblers__" + field.replace(".", "__")


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

# =============================================================== Molang: this file's own interpreter

class MolangError(Exception):
    pass


TOK = re.compile(r"\s*(?:(?P<num>\d+(?:\.\d+)?)|(?P<str>'(?:\\.|[^'\\])*')|(?P<name>[A-Za-z_][A-Za-z0-9_.]*)"
                 r"|(?P<op>==|!=|<=|>=|&&|\|\||[!?:=+(){};,\-<>]))")


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

    # MoLang's precedence: comparisons bind tighter than equality, looser than + (the level-cap pack's party_compare,
    # `q.player.party.highest_level > N`, sweep U54)
    LEVELS = [("||",), ("&&",), ("==", "!="), ("<", ">", "<=", ">="), ("+",)]

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
        if k == "name" and v == "for_each" and self.peek("("):
            # for_each(t.x, <list>, { body }): Cobblemon's own loop (the battle_victory callbacks use it)
            self.take("(")
            kk, var = self.take()
            if kk != "name":
                raise MolangError("for_each needs a variable, got %r" % (var,))
            self.take(",")
            seq = self.expr()
            self.take(",")
            body = self.block()
            self.take(")")
            return ("foreach", var, seq, body)
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

    def __init__(self, world, player, vars_=None, npc=None, ctx=None):
        self.w, self.p = world, player
        self.npc = npc                      # the conversation's NPC (q.npc), an Entity
        self.ctx = ctx or {}                # c.* (a callback's context: c.scriptable_losers, c.player_winners)
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
        if name == "q.player":
            return self.p
        if name == "q.player.party.highest_level":
            # the party's highest level (the quantity rctmod's canBattleAgainst compares with the cap)
            return self.p.party
        if name.startswith("v."):
            return self.vars.get(name[2:], 0)
        if name.startswith("c."):
            if name not in self.ctx:
                raise MolangError("unknown context %s" % name)
            return self.ctx[name]
        if name.startswith("t."):
            parts = name.split(".")
            if len(parts) > 2 and isinstance(self.temp.get("t." + parts[1]), dict):
                obj = self.temp["t." + parts[1]]
                for p in parts[2:]:
                    if not isinstance(obj, dict) or p not in obj:
                        raise MolangError("%s: no member %s" % (name, p))
                    obj = obj[p]
                return obj
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
            if op in ("<", ">", "<=", ">="):
                if isinstance(a, str) or isinstance(b, str):
                    raise MolangError("%r %s %r: a comparison of a string" % (a, op, b))
                return 1 if {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op] else 0
        if k == "call":
            return self.call(e[1], [self.eval(a) for a in e[2]])
        if k == "foreach":
            seq = self.eval(e[2])
            if not isinstance(seq, list):
                raise MolangError("for_each over %r" % (seq,))
            for item in seq:
                self.temp[e[1]] = item
                self.block(e[3])
            return 0
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
        if name == "q.npc.start_battle":
            # Cobblemon's NPC battle against the talking player (the jar's dialogues/npc-example.json). Recorded with
            # the player's data at that moment; the walk then follows both outcomes
            if self.npc is None:
                raise MolangError("q.npc.start_battle with no NPC")
            if len(args) != 2 or args[0] is not self.p:
                raise MolangError("q.npc.start_battle(%r): only (q.player, format) is modelled" % (args,))
            self.w.battles.append((self.npc, args[1], dict(self.p.data)))
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
    type = "minecraft:player"

    def __init__(self, uuid="00000000-0000-0000-0000-00000000c0b1", pos=(3363.5, 13.0, 3312.5)):
        self.uuid = uuid
        self.data, self.adv, self.tags, self.scores = {}, set(), set(), {}
        self.gamemode, self.pos, self.saves = "survival", pos, 0
        self.vehicle = None
        # the RCT level cap `rctmod player get level_cap` answers (None: the command fails) and the party's highest
        # level; the default sits AT the post-gym-8 cap, so every walk also crosses the strictly-over boundary (U54)
        self.cap, self.party = MODEL_CAP, MODEL_CAP

    def snapshot(self):
        return (tuple(sorted(self.data.items(), key=lambda kv: kv[0])), frozenset(self.adv))


class Entity:
    """A non-player entity a command can be executed as (a Cobblemon NPC: type cobblemon:npc)."""

    def __init__(self, uuid, pos, type_="cobblemon:npc", name=None):
        self.uuid, self.pos, self.type, self.name = uuid, pos, type_, name
        self.tags, self.scores, self.data, self.adv = set(), {}, {}, set()
        self.gamemode, self.vehicle = None, None


SERVER_AT = (0.0, 0.0, 0.0)


class World:
    """Runs emitted functions and server commands. Every command a finale path reaches must be modelled; anything
    else raises Unmodelled, so the audit fails closed rather than skipping a line. `entities` are the other things
    a selector can find: every player (for @a) and every NPC (for `execute as <uuid>`)."""

    def __init__(self, functions, entities=()):
        self.functions = functions          # {"ns:path": [lines]}
        self.log = []                       # (kind, detail, player data snapshot, advancements)
        self.depth = 0
        self.entities = {e.uuid: e for e in entities}
        self.battles = []                   # (npc, format, player data) from q.npc.start_battle
        self.storage = {}                   # command storage: {"ns:id": {key: value}} (macro arguments)

    def players(self):
        return [e for e in self.entities.values() if isinstance(e, Player)]

    def targets(self, sel, me, at):
        """The entities a target argument names: @s, @a[...], or a uuid."""
        if sel == "@s" or (me is not None and sel == me.uuid):
            return [me] if me is not None else []
        if sel.startswith("@s["):
            return [me] if me is not None and select(me, sel[2:], at) else []
        if sel == "@a" or sel.startswith("@a["):
            pool = self.players()
            if isinstance(me, Player) and me.uuid not in self.entities:
                pool = [me] + pool
            return [p for p in pool if select(p, sel[2:], at)]
        if sel in self.entities:
            return [self.entities[sel]]
        if re.fullmatch(r"[0-9a-f-]{36}", sel):
            return []                                       # a uuid of nothing loaded: the command does nothing
        raise Unmodelled("target %s" % sel)

    def function(self, fid, p, at=None, macro=None):
        if fid not in self.functions:
            raise Unmodelled("function %s is in no pack" % fid)
        lines = [ln.strip() for ln in self.functions[fid]]
        if any(ln.startswith("$") for ln in lines):
            # a macro function (1.20.2+): run without arguments, or missing one, it fails whole and runs nothing
            need = {k for ln in lines if ln.startswith("$") for k in re.findall(r"\$\((\w+)\)", ln)}
            if macro is None or not need <= set(macro):
                raise Unmodelled("macro function %s called without %s" % (fid, sorted(need - set(macro or {}))))
        self.log.append(("function", fid, dict(p.data) if p else {}, frozenset(p.adv) if p else frozenset()))
        self.depth += 1
        if self.depth > 40:
            raise Unmodelled("function recursion through %s" % fid)
        try:
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                if line.startswith("$"):
                    line = re.sub(r"\$\((\w+)\)", lambda m: str(macro[m.group(1)]), line[1:])
                if self.command(line, p, at=at) == "return":
                    break
        finally:
            self.depth -= 1

    def _log(self, kind, detail, p):
        self.log.append((kind, detail, dict(p.data) if p else {}, frozenset(p.adv) if p else frozenset()))

    def command(self, cmd, p, server=False, at=None):
        at = at or (p.pos if p is not None else SERVER_AT)
        w = cmd.split()
        head = w[0]
        if head == "execute":
            return self.execute(w[1:], 0, p, at, cmd)
        if head == "function":
            macro = None
            if len(w) > 2 and w[2] == "with":
                if w[3] != "storage" or len(w) not in (5, 6):
                    raise Unmodelled(cmd)
                st = self.storage.get(w[4], {})
                macro = dict(st) if len(w) == 5 else st.get(w[5])
                if not isinstance(macro, dict):
                    raise Unmodelled("function %s with storage %s: no compound there" % (w[1], " ".join(w[4:])))
            elif len(w) > 2:
                macro = snbt_compound(" ".join(w[2:]), cmd)
            self.function(w[1], p, at, macro)
            return None
        if head == "return":
            return "return"
        if head == "rctmod":
            # `rctmod player get level_cap <player>`: its result is the cap; a cap that does not read fails the command
            if w[1:4] != ["player", "get", "level_cap"] or len(w) != 5:
                raise Unmodelled(cmd)
            (t,) = self.targets(w[4], p, at)
            return ("result", 0 if t.cap is None else int(t.cap))
        if head == "advancement" and p is not None and w[2] in ("@s", p.uuid) and w[3] == "only":
            (p.adv.add if w[1] == "grant" else p.adv.discard)(w[4])
            self._log("advancement", "%s %s" % (w[1], w[4]), p)
            return None
        if head == "advancement":
            raise Unmodelled("advancement form %s" % cmd)
        if head == "scoreboard":
            if w[1] == "objectives":
                return None
            if w[1] == "players" and w[3].startswith("#"):
                return None                                 # a fake player (a clock): nobody's state
            if w[1] == "players" and p is not None and w[3] == "@s" and w[2] == "get" and len(w) == 5:
                v = p.scores.get(w[4])
                return ("result", 0 if v is None else v)    # an unset score fails the command: 0 is stored
            if w[1] == "players" and p is not None and w[3] == "@s":
                if w[2] == "set":
                    p.scores[w[4]] = int(w[5])
                elif w[2] == "add":
                    p.scores[w[4]] = p.scores.get(w[4], 0) + int(w[5])
                elif w[2] == "reset":
                    p.scores.pop(w[4], None)
                else:
                    raise Unmodelled(cmd)
                self._log("score", "%s %s" % (w[4], p.scores.get(w[4])), p)
                return None
            raise Unmodelled(cmd)
        if head == "tag":
            for t in self.targets(w[1], p, at):
                (t.tags.add if w[2] == "add" else t.tags.discard)(w[3])
            return None
        if head == "runmolang":
            m = re.match(r'runmolang "(.*)" (@s)$', cmd)
            if not m:
                raise Unmodelled(cmd)
            Molang(self, p).run(m.group(1).replace('\\"', '"'))
            return None
        if head in ("tp", "title") and (w[1].startswith("@a") or w[1].startswith("@s[")):
            for t in self.targets(w[1], p, at):
                self._log(head, cmd, t)
                if head == "tp":
                    t.pos = tuple(float(v) for v in w[2:5])
            return None
        if head in ("title", "tellraw", "particle", "playsound", "tp", "spawnpoint", "say"):
            self._log(head, cmd, p)
            if head == "tp" and p is not None:
                try:
                    p.pos = tuple(float(v) for v in (w[2:5] if w[1] == "@s" else w[1:4]))
                except ValueError:
                    pass
            return None
        if head == "ride" and len(w) == 3 and w[2] == "dismount":
            for t in self.targets(w[1], p, at):
                t.vehicle = None
                self._log("ride", cmd, t)
            return None
        if head in ("fill", "setblock", "summon", "clone", "kill", "data", "item", "give", "clear", "loot"):
            self._log("world_change", cmd, p)
            return None
        raise Unmodelled(cmd)

    def execute(self, w, i, me, at, raw):
        """One `execute` chain from word i, as `me` at `at`. A selector naming several entities forks the chain."""
        store = None
        while i < len(w):
            sub = w[i]
            if sub == "run":
                if me is None:
                    return None
                r = self.command(" ".join(w[i + 1:]), me, at=at)
                if store is None:
                    return r
                # `execute store result ...`: the command's result (0 when it failed) goes to a score or to storage
                if not (isinstance(r, tuple) and r[0] == "result"):
                    raise Unmodelled("store result of a command the model gives no result: %s" % raw)
                if store[0] == "score":
                    if store[1] != "@s":
                        raise Unmodelled(raw)
                    me.scores[store[2]] = r[1]
                else:
                    self.storage.setdefault(store[1], {})[store[2]] = r[1]
                return None
            if sub == "store":
                if store is not None or w[i + 1] != "result":
                    raise Unmodelled(raw)
                if w[i + 2] == "score":
                    store = ("score", w[i + 3], w[i + 4])
                    i += 5
                elif w[i + 2] == "storage" and w[i + 5:i + 7] == ["int", "1"] and "." not in w[i + 4]:
                    store = ("storage", w[i + 3], w[i + 4])
                    i += 7
                else:
                    raise Unmodelled(raw)
                continue
            if store is not None and sub != "run":
                raise Unmodelled("a subcommand after store: %s" % raw)
            if sub in ("as", "at"):
                got = self.targets(w[i + 1], me, at)
                if len(got) != 1 or got[0] is not me:
                    out = None
                    for t in got:
                        r = self.execute(w, i + 2, t if sub == "as" else me, t.pos if sub == "at" else at, raw)
                        out = r if r is not None else out
                    return out
                if sub == "at":
                    at = me.pos
                i += 2
                continue
            if sub == "positioned":
                at = tuple(float(v) for v in w[i + 1:i + 4])
                i += 4
                continue
            if sub == "on":
                if w[i + 1] != "vehicle":
                    raise Unmodelled(raw)
                if me is None or me.vehicle is None:
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
                    got = me is not None and select(me, sel[2:], at)
                    i += 3
                elif kind == "score":
                    if w[i + 2] != "@s" or w[i + 4] != "matches":
                        raise Unmodelled(raw)
                    got = me is not None and in_range(me.scores.get(w[i + 3]), w[i + 5])
                    i += 6
                else:
                    raise Unmodelled(raw)
                if got != want:
                    return None
                continue
            raise Unmodelled(raw)
        return None


def snbt_compound(s, cmd):
    """A flat SNBT compound of macro arguments, {k:"text"} or {k:123}; anything else is not modelled."""
    s = s.strip()
    if not (s.startswith("{") and s.endswith("}")):
        raise Unmodelled(cmd)
    out = {}
    for part in [x for x in s[1:-1].split(",") if x.strip()]:
        k, _, v = part.partition(":")
        v = v.strip()
        if re.fullmatch(r'"[^"]*"', v):
            out[k.strip()] = v[1:-1]
        elif re.fullmatch(r"-?\d+", v):
            out[k.strip()] = int(v)
        else:
            raise Unmodelled(cmd)
    return out


def in_range(v, rng):
    """`matches` semantics: an unset score matches nothing."""
    if v is None:
        return False
    if ".." in rng:
        lo, hi = rng.split("..")
        return (lo == "" or v >= float(lo)) and (hi == "" or v <= float(hi))
    return v == float(rng)


def select(p, args, at):
    """@s[...] / @a[...] arguments against one entity. Only the arguments the finale's functions use are modelled."""
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
            elif k == "type":
                neg = v.startswith("!")
                if (p.type == v.lstrip("!")) == neg:
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
        # the hitbox (0.6 x 1.8) intersecting the box's cells, as Minecraft's dx/dy/dz test does
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
    """{'brann': record, 'elara': record} from data/finale_trainers.json, matched by the finale doc's names."""
    out = {}
    for t in jload(Path(data) / "finale_trainers.json")["trainers"]:
        for who, name in NAMES.items():
            if t.get("display_name") == name:
                out[who] = t
    return out


def placed_spots():
    """{npc id: (x + 0.5, y, z + 0.5)}: where step R18HQ stands each HQ NPC (tools/hq_tower.py npc_placements(), the
    list R18HQ spawns from; tools/reapply.py then tps each to its block's centre)."""
    sys.path.insert(0, str(ROOT / "tools"))
    import hq_tower
    out = {}
    for _conv, (x, y, z), cls, _yaw in hq_tower.npc_placements():
        out[cls.split(":", 1)[1]] = (x + 0.5, float(y), z + 0.5)
    return out


def npc_uuid(npc_id):
    return "00000000-0000-0000-0000-%012x" % zlib.crc32(npc_id.encode("utf-8"))


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
    vals = (fields.get(STAGE) or {}).get("allowed_values") or []
    for v in ORDER:
        if v not in vals:
            bad.append("%s has no value %s" % (STAGE, v))
    if all(v in vals for v in ORDER) and [v for v in vals if v in ORDER] != ORDER:
        bad.append("%s orders the finale's stages %s, the chain is %s" % (STAGE, [v for v in vals if v in ORDER], ORDER))
    return bad


def stage_values(data=DATA):
    fields = {f["id"]: f for f in jload(Path(data) / "progression.json")["quest_fields"]}
    return list(fields[STAGE]["allowed_values"])


def contract(data):
    """The release rule, on a player's data: stage cradle_open and both fields 1."""
    return (data.get(key(STAGE)) == RELEASE_STAGE and data.get(key(BRANN_FIELD)) == 1
            and data.get(key(ELARA_FIELD)) == 1)


def check_finale_order(data=DATA):
    """data/hq_tower.json finale_order against CHAIN: a disagreement between the builder's record and the brief."""
    bad = []
    order = jload(Path(data) / "hq_tower.json").get("finale_order") or []
    got = [(s.get("reads", "").split(" AND ")[0].strip(), (s.get("writes") or "").split()[0]) for s in order]
    want = [(c["from"], c["to"]) for c in CHAIN]
    if got != want:
        bad.append("data/hq_tower.json finale_order reads/writes %s; the chain is %s" % (got, want))
    return bad


# ------------------------------------------------------------------ the parties

PROP = re.compile(r"^(?P<species>[a-z0-9_]+)((?: [a-z_]+=\S+)*)$")


def parse_properties(s):
    """A Cobblemon properties string as compile_dialogue emits it, read back: {species, level, moveset, ability,
    heldItem, nature}. Unknown keys are kept under their own name, so an extra key is visible."""
    m = PROP.match(s.strip())
    if not m:
        raise ValueError("not a properties string: %r" % s)
    out = {"species": m.group("species")}
    for part in s.split()[1:]:
        k, v = part.split("=", 1)
        if k == "level":
            out["level"] = int(v)
        elif k == "moves":
            out["moveset"] = v.split(",")
        elif k == "held_item":
            out["heldItem"] = v.split(":", 1)[1] if v.startswith("cobblemon:") else v
        else:
            out[k] = v
    return out


def jar_items(jar):
    """The item ids the jar names (item.cobblemon.<id> in its en_us lang file), or None."""
    try:
        z = zipfile.ZipFile(jar)
        lang = json.loads(z.read("assets/cobblemon/lang/en_us.json"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None
    return {k[len("item.cobblemon."):] for k in lang if k.startswith("item.cobblemon.") and k.count(".") == 2}


def check_parties(packs, recs, cap, jar):
    """Each fighting NPC's emitted class: its dialogue, its name, a click never starts a battle, and a `simple` party
    equal to data/finale_trainers.json's team, member for member, under the cap and legal in the jar."""
    bad, notes = [], []
    species = jar_species(jar) if jar else None
    items = jar_items(jar) if jar else None
    if species is None:
        bad.append("no Cobblemon 1.8 jar found: move and ability legality NOT checked (pass --jar)")
    for who, c in FIGHTS.items():
        f = Path(packs) / "cobblers_dialogue" / "data" / "cobblers" / "npcs" / ("%s.json" % c["npc"])
        if not f.is_file():
            bad.append("%s: no emitted NPC class %s" % (who, f))
            continue
        k = jload(f)
        if (k.get("interaction") or {}).get("dialogue") != "cobblers:%s" % c["conv"]:
            bad.append("%s: the class opens %s, not cobblers:%s" % (c["npc"], k.get("interaction"), c["conv"]))
        if k.get("names") != [NAMES[who]]:
            bad.append("%s: named %s, the finale doc's is %r" % (c["npc"], k.get("names"), NAMES[who]))
        if (k.get("battleConfiguration") or {}).get("canChallenge") is not False:
            bad.append("%s: canChallenge is not false, so a click can start the fight outside the conversation's "
                       "stage" % c["npc"])
        party = k.get("party") or {}
        if party.get("type") != "simple":
            bad.append("%s: party type %r, not simple" % (c["npc"], party.get("type")))
            continue
        try:
            got = [parse_properties(s) for s in party.get("pokemon") or []]
        except ValueError as e:
            bad.append("%s: %s" % (c["npc"], e))
            continue
        want = [{kk: m[kk] for kk in ("species", "level", "moveset", "ability", "heldItem", "nature") if m.get(kk)}
                for m in (recs.get(who) or {}).get("team") or []]
        if not want:
            bad.append("%s: data/finale_trainers.json has no team for it" % who)
        if got != want:
            bad.append("%s: the party %s is not data/finale_trainers.json's team %s" % (c["npc"], got, want))
        for m in got:
            if m.get("level", 0) > cap:
                bad.append("%s: %s level %d over the post-gym-8 cap %d" % (c["npc"], m["species"], m["level"], cap))
            if species is not None:
                bad += ["%s: %s" % (c["npc"], p) for p in legality(species, m)]
            if items is not None and m.get("heldItem") and m["heldItem"] not in items:
                bad.append("%s: %s holds %s, which the jar has no item for" % (c["npc"], m["species"], m["heldItem"]))
        notes.append("%s: %d Pokemon, levels %s, cap %d" % (c["npc"], len(got), [m.get("level") for m in got], cap))
    return bad, notes


# ------------------------------------------------------------------ the fights' callback

def callback_src(packs):
    f = Path(packs) / CALLBACK
    return f.read_text(encoding="utf-8") if f.is_file() else None


def victory(packs, functions, losers, winners, others=()):
    """One battle_victory callback run: `losers` and `winners` are entities (an Entity is an NPC, a Player a player);
    `others` are loaded but not in the battle. Runs the EMITTED callback in the model; returns the World."""
    src = callback_src(packs)
    if src is None:
        raise Unmodelled("no emitted %s" % CALLBACK)
    w = World(functions, list(losers) + list(winners) + list(others))
    ctx = {"c.scriptable_losers": [{"is_npc": 1 if isinstance(e, Entity) else 0, "uuid": e.uuid} for e in losers],
           "c.player_winners": [{"player": {"uuid": e.uuid}} for e in winners if isinstance(e, Player)]}
    Molang(w, None, ctx=ctx).run(src)
    return w


def check_defeat_fields(packs, functions, spots=None):
    """The callback, run for every outcome a fight can have. Beating Brann at his placed spot writes brann_defeated = 1
    for each WINNING player and nothing else; a loss, a bystander, another NPC losing, and an NPC elsewhere write
    nothing."""
    bad = []
    spots = spots or placed_spots()
    fk = {"brann": key(BRANN_FIELD), "elara": key(ELARA_FIELD)}
    others = [n for n in spots if n not in (c["npc"] for c in FIGHTS.values())]
    for who, c in FIGHTS.items():
        if c["npc"] not in spots:
            bad.append("%s: R18HQ places no %s" % (who, c["npc"]))
            continue
        spot = spots[c["npc"]]
        cases = []
        npc = Entity(npc_uuid(c["npc"]), spot)
        p, q, r = (Player(uuid="00000000-0000-0000-0000-0000000000a1"),
                   Player(uuid="00000000-0000-0000-0000-0000000000b2"),
                   Player(uuid="00000000-0000-0000-0000-0000000000c3"))
        cases.append(("one player beats %s" % who, [npc], [p], [q], {p: {fk[who]: 1}, q: {}}))
        cases.append(("two players beat %s together" % who, [npc], [p, r], [q], {p: {fk[who]: 1}, r: {fk[who]: 1},
                                                                                 q: {}}))
        cases.append(("a player loses to %s" % who, [p], [npc], [q], {p: {}, q: {}}))
        far = Entity(npc_uuid(c["npc"] + "-far"), (spot[0], spot[1], spot[2] + 8))
        cases.append(("an NPC 8 blocks from %s's spot is beaten" % who, [far], [p], [npc], {p: {}}))
        for o in others:
            e = Entity(npc_uuid(o), spots[o])
            cases.append(("%s is beaten" % o, [e], [p], [npc], {p: {}}))
        for name, losers, winners, rest, want in cases:
            for pl in (p, q, r):
                pl.data, pl.adv = {}, set()
            try:
                victory(packs, functions, losers, winners, rest)
            except (Unmodelled, MolangError) as e:
                bad.append("%s: the callback does not run in the model: %s" % (name, e))
                continue
            for pl, exp in want.items():
                got = {k: v for k, v in pl.data.items() if k in fk.values()}
                if got != exp:
                    bad.append("%s: player %s ends with %s, the rule is %s" % (name, pl.uuid[-2:], got, exp))
                if FLAG_ADV in pl.adv:
                    bad.append("%s: grants %s" % (name, FLAG))
    return bad


# ------------------------------------------------------------------ the conversation walk

def dialogue_of(packs, conv=CONV):
    f = Path(packs) / "cobblers_dialogue" / "data" / "cobblers" / "dialogues" / ("%s.json" % conv)
    return jload(f) if f.is_file() else None


def sig(data, adv):
    return (tuple(sorted(data.items(), key=lambda kv: kv[0])), frozenset(adv))


def unsig(s):
    return dict(s[0]), set(s[1])


class Conversation:
    """One compiled conversation in the model, its outcomes memoised by player state. expand(state) opens it once
    and takes every page, acknowledge and visible option reachable without closing; each action is one outcome:
    (events, the state it leaves). A battle start forks: the state as it was (a loss) and the state after the
    EMITTED callback for the winner (a win). Events: ("grant", data) when the flag's grant runs, ("stage", pre, new),
    ("field", pre, key, new) for a defeat field a conversation writes itself, ("battle", pre), ("offer", data) when
    CHOICE is visible."""

    def __init__(self, dlg, functions, npc=None, win=None, pos=None, party=None):
        self.dlg, self.functions, self.npc, self.win = dlg, functions, npc, win
        self.pos = pos                      # where the talking player stands; None: the old default, far from all
        self.party = party                  # (RCT cap or None, party's highest level); None: the Player default
        self.pages = {p["id"]: p for p in dlg["pages"]}
        self.memo = {}

    def run(self, src, data, adv):
        w, p = World(self.functions), (Player(pos=self.pos) if self.pos is not None else Player())
        p.data, p.adv = dict(data), set(adv)
        if self.party is not None:
            p.cap, p.party = self.party
        pos0 = p.pos
        m = Molang(w, p, npc=self.npc)
        m.run(src)
        ev = [("grant", d) for kind, detail, d, _a in w.log if kind == "function" and detail == FLAG_GRANT_FN]
        if self.pos is not None and p.pos != pos0:
            ev.append(("moved", dict(data), p.pos))        # only when a position was given: the door keeper's admit
        if p.data.get(key(STAGE)) != data.get(key(STAGE)):
            ev.append(("stage", dict(data), p.data.get(key(STAGE))))
        for f in (BRANN_FIELD, ELARA_FIELD):
            if p.data.get(key(f)) != data.get(key(f)):
                ev.append(("field", dict(data), key(f), p.data.get(key(f))))
        nxt = [sig(p.data, p.adv)]
        for _npc, _fmt, d in w.battles:
            ev.append(("battle", d))
            if self.win is not None:
                won = Player()
                won.data, won.adv = dict(p.data), set(p.adv)
                self.win(won)
                nxt.append(sig(won.data, won.adv))
        page = None if m.closed else m.page
        if page is not None and self.party is not None:
            ev.append(("page", dict(data), page))           # the page this action shows (check_over_cap's walks)
        return ev, nxt, (dict(p.data), set(p.adv)), page

    def expand(self, s):
        if s in self.memo:
            return self.memo[s]
        data, adv = unsig(s)
        out = []
        ev, nxt, (d, a), page = self.run(self.dlg["initializationAction"], data, adv)
        out.append((ev, nxt))
        frontier, inner = ([(d, a, page)] if page is not None else []), set()
        while frontier:
            d0, a0, pid = frontier.pop()
            isig = (sig(d0, a0), pid)
            if isig in inner:
                continue
            inner.add(isig)
            pg = self.pages.get(pid)
            if pg is None:
                raise MolangError("set_page(%r): no such page" % pid)
            inp = pg.get("input")
            actions = []
            if isinstance(inp, str):
                actions.append(inp)
            elif isinstance(inp, dict) and inp.get("type") == "option":
                for opt in inp["options"]:
                    vis = opt.get("isVisible")
                    if vis is None:
                        shown = True
                    else:
                        p = Player()
                        p.data, p.adv = dict(d0), set(a0)
                        shown = truthy(Molang(World(self.functions), p, npc=self.npc).run(vis))
                    if shown:
                        if opt["text"] == CHOICE:
                            out.append(([("offer", dict(d0))], []))
                        actions.append(opt["action"])
            for act in actions:
                ev, nxt, (d1, a1), page = self.run(act, d0, a0)
                out.append((ev, nxt))
                if page is not None:
                    frontier.append((d1, a1, page))
        self.memo[s] = out
        return out

    def reach(self, start, limit=20000):
        """(every state reached from start, every event on the way)."""
        seen, events, q = {start}, [], deque([start])
        while q:
            s = q.popleft()
            for ev, nxt in self.expand(s):
                events += ev
                for n in nxt:
                    if n not in seen:
                        seen.add(n)
                        q.append(n)
            if len(seen) > limit:
                raise MolangError("more than %d states" % limit)
        return seen, events


def walk(dlg, functions, start, npc=None, win=None):
    """Compatibility: (grant runs, states reached, offered) from one start state (data, adv)."""
    seen, events = Conversation(dlg, functions, npc, win).reach(sig(*start))
    return [(e[1], None) for e in events if e[0] == "grant"], len(seen), any(e[0] == "offer" for e in events)


def acting_pages(dlg):
    """The pages whose own script acts: a stage write, a battle, the grant."""
    stage_w = re.compile(r"%s\s*=\s*'" % re.escape(key(STAGE)))
    out = []
    for p in dlg["pages"]:
        t = json.dumps(p)
        if stage_w.search(t) or "start_battle" in t or FLAG_GRANT_FN in t:
            out.append(p["id"])
    return out


def cursor_field(conv, data=DATA):
    for c in jload(Path(data) / "dialogue.json")["conversations"]:
        if c["id"] == conv:
            return (c.get("cursor") or {}).get("progression_field")
    return None


def start_states(data_dir, dlg, conv=CONV):
    cf = cursor_field(conv, data_dir)
    cursors = [None] + (acting_pages(dlg) + [dlg["pages"][-1]["id"]] if cf else [])
    cursors = list(dict.fromkeys(cursors))
    for stage in [None] + stage_values(data_dir):
        for b in (None, 0, 1):
            for e in (None, 0, 1):
                for flag in (False, True):
                    for c in cursors:
                        d = {}
                        if stage is not None:
                            d[key(STAGE)] = stage
                        if b is not None:
                            d[key(BRANN_FIELD)] = b
                        if e is not None:
                            d[key(ELARA_FIELD)] = e
                        if c is not None:
                            d[key(cf)] = c
                        yield d, ({FLAG_ADV} if flag else set())


def win_for(packs, functions, npc_id, spot):
    """The win outcome of a battle with npc_id: the EMITTED callback, the NPC standing at its placed spot."""
    def win(player):
        npc = Entity(npc_uuid(npc_id), spot)
        victory(packs, functions, [npc], [player])
    return win


def conversations(packs, functions, spots=None):
    """{who: Conversation} for the chain; a missing compiled conversation is absent."""
    spots = spots if spots is not None else placed_spots()
    out = {}
    for c in CHAIN:
        dlg = dialogue_of(packs, c["conv"])
        if dlg is None:
            continue
        spot = spots.get(c["npc"], (3363.5, 13.0, 3312.5))
        npc = Entity(npc_uuid(c["npc"]), spot)
        win = win_for(packs, functions, c["npc"], spot) if c.get("fight") and callback_src(packs) else None
        out[c["who"]] = Conversation(dlg, functions, npc, win)
    return out


def check_conversation(packs, functions, data_dir=DATA, spots=None, only=None):
    """Every chain conversation, executed from every start state; the rules in the module docstring."""
    bad, notes = [], []
    convs = conversations(packs, functions, spots)
    total, good = 0, {}
    for c in CHAIN:
        if only and c["who"] not in only:
            continue
        cv = convs.get(c["who"])
        if cv is None:
            bad.append("the compiled %s is not in %s/cobblers_dialogue" % (c["conv"], packs))
            continue
        good[c["who"]] = 0
        for data, adv in start_states(data_dir, cv.dlg, c["conv"]):
            total += 1
            try:
                _seen, events = cv.reach(sig(data, adv))
            except (Unmodelled, MolangError) as e:
                bad.append("%s does not run in the model from %s: %s" % (c["conv"], data, e))
                break
            bad += rule_events(c, events, data)
            st = data.get(key(STAGE))
            if st == c["from"] and all(data.get(key(f)) == 1 for f in c["needs"] if f != c.get("fight")):
                writes = [e for e in events if e[0] == "stage" and e[2] == c["to"]]
                if not writes:
                    bad.append("%s from %s never writes %s" % (c["conv"], data, c["to"]))
                else:
                    good[c["who"]] += 1
                if c.get("fight") and data.get(key(c["fight"])) != 1 \
                        and not any(e[0] == "battle" for e in events):
                    bad.append("%s from %s never starts the fight" % (c["conv"], data))
                if c.get("grants"):
                    if not any(e[0] == "grant" for e in events):
                        bad.append("from %s (the rule holds) the release never grants %s" % (data, FLAG))
                    if not any(e[0] == "offer" for e in events):
                        bad.append("from %s the choice %r is never shown" % (data, CHOICE))
            if len(bad) > 30:
                bad.append("... stopped after 30")
                return dedupe(bad), notes
    notes.append("conversation: %d start states walked over %d conversations; each scene's write reached from %s"
                 % (total, len(good), good))
    return dedupe(bad), notes


def dedupe(xs):
    return list(dict.fromkeys(xs))


def check_guards(packs, functions, data_dir=DATA, spots=None):
    """Each page that acts, its script run DIRECTLY from every start state, as if a restored cursor or a later entry
    rule landed there: a stage write, a grant or a defeat-field write must carry its own guard, not only the route to
    it (record_hq_crossed must itself need brann_defeated). A battle start is not judged here: a choice's battle is
    guarded by the route to the choice (its visibility), which the walk above judges."""
    bad = []
    convs = conversations(packs, functions, spots)
    n = 0
    for c in CHAIN:
        cv = convs.get(c["who"])
        if cv is None:
            continue
        starts = list(start_states(data_dir, cv.dlg, c["conv"]))
        for pid in acting_pages(cv.dlg):
            inp = cv.pages[pid].get("input")
            acts = [inp] if isinstance(inp, str) else [o["action"] for o in (inp or {}).get("options", [])]
            for act in acts:
                for data, adv in starts:
                    n += 1
                    try:
                        ev = cv.run(act, data, adv)[0]
                    except (Unmodelled, MolangError) as e:
                        bad.append("%s page %s does not run in the model: %s" % (c["conv"], pid, e))
                        break
                    ev = [e for e in ev if e[0] in ("stage", "grant", "field")]
                    bad += ["%s page %s run directly: %s" % (c["conv"], pid, b) for b in rule_events(c, ev, data)]
                    if len(bad) > 30:
                        return dedupe(bad) + ["... stopped after 30"]
    return dedupe(bad)


def rule_events(c, events, start):
    """The per-event rules for chain conversation c."""
    bad = []
    for e in events:
        if e[0] == "stage":
            pre, new = e[1], e[2]
            if (pre.get(key(STAGE)), new) != (c["from"], c["to"]):
                bad.append("%s writes stage %s from %s; its only write is %s -> %s"
                           % (c["conv"], new, pre.get(key(STAGE)), c["from"], c["to"]))
            elif not all(pre.get(key(f)) == 1 for f in c["needs"]):
                bad.append("%s writes %s without %s (state %s)" % (c["conv"], new, list(c["needs"]),
                                                                   {k: v for k, v in pre.items() if "cursor" not in k}))
        elif e[0] == "field":
            bad.append("%s writes %s = %r itself; only the fight's callback may" % (c["conv"], e[2], e[3]))
        elif e[0] == "battle":
            if not c.get("fight"):
                bad.append("%s starts a battle" % c["conv"])
            elif e[1].get(key(STAGE)) != c["from"]:
                bad.append("%s starts its fight at stage %r, not %s" % (c["conv"], e[1].get(key(STAGE)), c["from"]))
        elif e[0] == "grant":
            if not c.get("grants"):
                bad.append("%s grants %s" % (c["conv"], FLAG))
            elif not contract(e[1]):
                bad.append("%s is granted in a state that fails the rule: stage %r, brann %r, elara %r (start %s)"
                           % (FLAG, e[1].get(key(STAGE)), e[1].get(key(BRANN_FIELD)), e[1].get(key(ELARA_FIELD)),
                              start))
        elif e[0] == "offer":
            if not contract(e[1]):
                bad.append("the choice %r is shown from %s, where the rule fails" % (CHOICE, e[1]))
    return bad


def check_story(packs, functions, spots=None, limit=20000):
    """The joint walk: a player at rift_crisis_pending talks to the five in any order, fights, wins or loses, until
    nothing new is reached. The flag must be reachable; on every state reached the order must hold."""
    bad, notes = [], []
    convs = conversations(packs, functions, spots)
    if len(convs) != len(CHAIN):
        return ["the story walk needs all five conversations; have %s" % sorted(convs)], notes
    start = sig({key(STAGE): PENDING}, set())
    seen, q = {start}, deque([start])
    try:
        while q:
            s = q.popleft()
            for cv in convs.values():
                for _ev, nxt in cv.expand(s):
                    for n in nxt:
                        if n not in seen:
                            seen.add(n)
                            q.append(n)
            if len(seen) > limit:
                return ["the story walk passed %d states" % limit], notes
    except (Unmodelled, MolangError) as e:
        return ["the story walk does not run in the model: %s" % e], notes
    stages = set()
    for s in seen:
        d, a = unsig(s)
        st = d.get(key(STAGE))
        stages.add(st)
        i = ORDER.index(st) if st in ORDER else -1
        if d.get(key(BRANN_FIELD)) == 1 and i < 1:
            bad.append("brann_defeated at stage %s" % st)
        if d.get(key(ELARA_FIELD)) == 1 and i < 3:
            bad.append("elara_defeated at stage %s" % st)
        if i >= 2 and d.get(key(BRANN_FIELD)) != 1:
            bad.append("stage %s reached without brann_defeated" % st)
        if i >= 4 and d.get(key(ELARA_FIELD)) != 1:
            bad.append("stage %s reached without elara_defeated" % st)
        if (FLAG_ADV in a) != (st == RELEASED):
            bad.append("the flag is %s at stage %s" % ("held" if FLAG_ADV in a else "not held", st))
    if stages != set(ORDER[:6]):
        bad.append("the story reaches stages %s, the chain is %s" % (sorted(map(str, stages)), ORDER[:6]))
    if not any(FLAG_ADV in s[1] for s in seen):
        bad.append("the story from %s never reaches %s" % (PENDING, FLAG))
    notes.append("story: %d states reached from %s; stages %s" % (len(seen), PENDING,
                                                                  [o for o in ORDER if o in stages]))
    return dedupe(bad), notes


def over_cap_nodes(data=DATA):
    """{conversation id: over_cap_node} for each npc_battle action in data/dialogue.json: the AUTHORED refusal line."""
    out = {}
    for c in jload(Path(data) / "dialogue.json")["conversations"]:
        for n in c.get("nodes") or []:
            for r in n.get("responses") or []:
                for a in r.get("actions") or []:
                    if a.get("kind") == "npc_battle" and a.get("over_cap_node"):
                        out[c["id"]] = a["over_cap_node"]
    return out


def check_over_cap(packs, functions, data_dir=DATA, spots=None):
    """THE LEVEL CAP (sweep U54, review N57). Brann and Elara are cobblemon:npc, which rctmod's own over-cap refusal
    never reaches, so their conversations must apply rctmod's rule: a party whose highest level is STRICTLY over the
    player's RCT cap never starts the fight and is shown the authored over_cap_node instead, changing no stage, field
    or flag. At the cap the fight starts; with a cap that does not read it starts too (the direction a catch takes:
    failing closed would wall the finale off for everyone while RCT is unreadable). NO TRAP: from every state a
    refusal can leave the player in (the cursor at the refusal line, the conversation closed on it), a party back
    under the cap reaches the fight. Walked from every start state with the fight open (the stage it needs, the
    field not yet 1), executing the compiled conversation, the emitted battle_check and its party_compare."""
    bad, notes = [], []
    convs = conversations(packs, functions, spots)
    refusal = over_cap_nodes(data_dir)
    counts = {}
    for who, c in FIGHTS.items():
        cv = convs.get(who)
        if cv is None:
            bad.append("the compiled %s is not in %s/cobblers_dialogue" % (c["conv"], packs))
            continue
        node = refusal.get(c["conv"])
        if node is None:
            bad.append("%s: data/dialogue.json's npc_battle names no over_cap_node" % c["conv"])
            continue

        def conv(party):
            return Conversation(cv.dlg, functions, cv.npc, cv.win, party=party)

        over, under = conv((MODEL_CAP, MODEL_CAP + 1)), conv((MODEL_CAP, MODEL_CAP - 10))
        others = (("at the cap", conv((MODEL_CAP, MODEL_CAP))), ("with a cap that does not read", conv((None, 100))))
        starts = [(d, a) for d, a in start_states(data_dir, cv.dlg, c["conv"])
                  if d.get(key(STAGE)) == c["from"] and d.get(key(c["fight"])) != 1]
        left = 0
        try:
            for d, a in starts:
                s = sig(d, a)
                seen, ev = over.reach(s)
                if any(e[0] == "battle" for e in ev):
                    bad.append("%s: a party at %d over a cap of %d starts the fight from %s"
                               % (c["conv"], MODEL_CAP + 1, MODEL_CAP, d))
                if not any(e[0] == "page" and e[2] == node for e in ev):
                    bad.append("%s: the refusal %s is never shown to an over-cap party from %s" % (c["conv"], node, d))
                if any(e[0] in ("stage", "field", "grant") for e in ev):
                    bad.append("%s: an over-cap party changes the story from %s: %s"
                               % (c["conv"], d, [e for e in ev if e[0] in ("stage", "field", "grant")][:2]))
                for s2 in seen:
                    d2 = dict(s2[0])
                    if d2.get(key(STAGE)) == c["from"] and d2.get(key(c["fight"])) != 1:
                        left += 1
                        if not any(e[0] == "battle" for e in under.reach(s2)[1]):
                            bad.append("%s: a trap -- from %s, left by a refusal, a party back under the cap never "
                                       "reaches the fight" % (c["conv"], d2))
                for what, cvx in others:
                    if not any(e[0] == "battle" for e in cvx.reach(s)[1]):
                        bad.append("%s: a party %s never starts the fight from %s" % (c["conv"], what, d))
        except (Unmodelled, MolangError) as e:
            bad.append("%s does not run in the model with a level cap: %s" % (c["conv"], e))
            continue
        counts[who] = (len(starts), left)
        if len(bad) > 30:
            break
    notes.append("over_cap: {who: (start states with the fight open, states a refusal leaves)} %s" % counts)
    return dedupe(bad), notes


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
    p.data = {key(STAGE): RELEASE_STAGE, key(BRANN_FIELD): 1, key(ELARA_FIELD): 1}
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


# ------------------------------------------------------------------ the gates

def gate_points(data=DATA):
    """Where the gate test stands its players, from data/hq_tower.json: the tower's centre column at the ground
    storey, the briefing hall, and the top storey (each storey's floor + 1)."""
    h = jload(Path(data) / "hq_tower.json")
    ix0, iz0, ix1, iz1 = h["tower"]["interior"]
    cx, cz = (ix0 + ix1) / 2 + 0.5, (iz0 + iz1) / 2 + 0.5
    st = h["storeys"]
    return {"ground": (cx, float(st[0]["floor"] + 1), cz), "hall": (cx, float(st[1]["floor"] + 1), cz),
            "top": (cx, float(st[-1]["floor"] + 1), cz)}, h["tower"]["box"], st[1]["floor"], st[2]["floor"]


def check_gates(functions, data=DATA):
    """The EMITTED gate cycle, run once with one player per (stage, place) and once more: a player at the door's
    stage or later stays on the ground and in the hall, any earlier is set outside the tower; above the hall a player
    stays only from hq_crossed on, and a player let through the door but not the climb is set onto the hall's floor.
    Creative passes. The second run moves nobody (the set-backs are outside their gates). Nothing is ever built."""
    bad, notes = [], []
    cyc = "cobblers:hq_tower/cycle"
    if cyc not in functions:
        return ["no emitted %s" % cyc], notes
    for fn in (cyc, "cobblers:hq_tower/tick", "cobblers:hq_tower/load"):
        for line in functions[fn] if fn in functions else []:
            if line.split()[:1] and line.split()[0] in ("fill", "setblock", "clone", "summon", "place"):
                bad.append("%s builds: %s" % (fn, line))
    pts, box, hall_floor, climb_floor = gate_points(data)
    x0, z0, x1, z1 = box

    def in_tower(pos):
        return x0 <= math.floor(pos[0]) <= x1 + 1 and z0 <= math.floor(pos[2]) <= z1      # x1 + 1: the door cut

    players, want = [], {}
    n = 0
    for stage in [None] + stage_values(data):
        for place, pos in pts.items():
            for mode in ("survival", "creative"):
                n += 1
                p = Player(uuid="00000000-0000-0000-0000-%012d" % n, pos=pos)
                p.gamemode = mode
                if stage is not None:
                    p.data[key(STAGE)] = stage
                players.append(p)
                door, climb = stage in DOOR_OPEN, stage in CLIMB_OPEN
                if mode == "creative" or (door and (place != "top" or climb)):
                    want[p.uuid] = ("stays", stage, place, mode)
                elif door:
                    want[p.uuid] = ("hall", stage, place, mode)
                else:
                    want[p.uuid] = ("outside", stage, place, mode)
    w = World(functions, players)
    try:
        w.function(cyc, None)
        after1 = {p.uuid: p.pos for p in players}
        w.function(cyc, None)
    except (Unmodelled, MolangError) as e:
        return bad + ["the gate cycle does not run in the model: %s" % e], notes
    for p in players:
        how, stage, place, mode = want[p.uuid]
        pos0 = pts[place]
        if how == "stays" and after1[p.uuid] != pos0:
            bad.append("a %s player at stage %s in the %s is moved to %s" % (mode, stage, place, after1[p.uuid]))
        if how == "outside" and in_tower(after1[p.uuid]):
            bad.append("a player at stage %s in the %s is left inside the tower at %s" % (stage, place, after1[p.uuid]))
        if how == "hall" and not (in_tower(after1[p.uuid]) and hall_floor < after1[p.uuid][1] < climb_floor):
            bad.append("a player at stage %s on the %s storey is moved to %s, not the briefing hall"
                       % (stage, place, after1[p.uuid]))
        if p.pos != after1[p.uuid]:
            bad.append("the cycle's second run moves a player at stage %s from %s to %s: a set-back inside its gate"
                       % (stage, after1[p.uuid], p.pos))
    notes.append("gates: %d players (every stage x ground/hall/top x survival/creative) in one cycle" % len(players))
    return dedupe(bad)[:30], notes


# ------------------------------------------------------------------ the door keeper (2026-10-05)

def facing(yaw):
    """Minecraft's yaw as a unit step on the grid: 0 faces +z (south), 90 faces -x (west), -90 +x, 180 -z."""
    r = math.radians(yaw)
    return (int(round(-math.sin(r))), int(round(math.cos(r))))


def placed_yaws():
    """{npc id: yaw} from the same list R18HQ spawns from (tools/hq_tower.py npc_placements())."""
    sys.path.insert(0, str(ROOT / "tools"))
    import hq_tower
    return {cls.split(":", 1)[1]: yaw for _conv, _at, cls, yaw in hq_tower.npc_placements()}


def check_door_keeper(packs, functions, data=DATA, spots=None, yaws=None):
    """Elara keeps the tower door (the owner, 2026-10-05). Expectations from data/hq_tower.json's GATES (the door
    gate's from_stage over the stage enum, which must equal the brief's DOOR_OPEN) and the tower's interior, and from
    where R18HQ places her and which way she faces -- never from the door_keeper block or its function:
      admit   every action of her compiled conversation, run DIRECTLY from every stage by a player standing in the
              cell in front of her (as a restored cursor would), moves that player into the tower only at a door
              stage; and the walk from each door stage, her battle forked both ways, reaches a move inside (the
              stages whose move is made only after a later stage is written are named in the note)
      landing a player at a door stage where the admit put them is not moved by the emitted cycle (twice); a player
              before the door stage there is set outside the tower (the gate behind her still bites)
      the hole a survival player of any stage in the cell behind her is moved by the cycle onto the line in front of
              her (outside the tower, within her admit's reach of her again), and a second cycle moves nobody
      inside  a player at a door stage on the threshold cell just inside the hole is not moved: the exit cannot
              strand (eject) a player who is legitimately inside.
    Not covered: whether her body blocks the doorway in game, and whether Cobblemon opens her dialogue at that range."""
    bad, notes = [], []
    h = jload(Path(data) / "hq_tower.json")
    vals = stage_values(data)
    door_from = h["gates"]["door"]["from_stage"]
    doors = set(vals[vals.index(door_from):]) if door_from in vals else set()
    if doors != DOOR_OPEN:
        bad.append("the door gate opens at %s on (data/hq_tower.json gates.door), the chain's door is %s"
                   % (door_from, sorted(DOOR_OPEN)))
    ix0, iz0, ix1, iz1 = h["tower"]["interior"]
    bx0, bz0, bx1, bz1 = h["tower"]["box"]

    def inside(pos):
        return ix0 <= math.floor(pos[0]) <= ix1 and iz0 <= math.floor(pos[2]) <= iz1

    def in_tower(pos):        # the box, its walls and the section wall's door cut (x1 + 1), as check_gates
        return bx0 <= math.floor(pos[0]) <= bx1 + 1 and bz0 <= math.floor(pos[2]) <= bz1

    spots = spots if spots is not None else placed_spots()
    yaws = yaws if yaws is not None else placed_yaws()
    elara = FIGHTS["elara"]
    spot = spots.get(elara["npc"])
    if spot is None or elara["npc"] not in yaws:
        return ["the door keeper %s is not placed by R18HQ" % elara["npc"]], notes
    fx, fz = facing(yaws[elara["npc"]])
    sx, sy, sz = math.floor(spot[0]), int(spot[1]), math.floor(spot[2])
    front = (sx + fx + 0.5, float(sy), sz + fz + 0.5)
    hole = (sx - fx + 0.5, float(sy), sz - fz + 0.5)
    threshold = (sx - 2 * fx + 0.5, float(sy), sz - 2 * fz + 0.5)
    if in_tower(front) or not in_tower(hole) or not inside(threshold):
        bad.append("Elara at %s facing %s: in front %s is %s the tower, behind her %s is %s it, two behind %s is %s "
                   "the interior -- she does not stand in the doorway facing out"
                   % ((sx, sy, sz), (fx, fz), front, "in" if in_tower(front) else "outside", hole,
                      "in" if in_tower(hole) else "outside", threshold, "in" if inside(threshold) else "outside"))
    dlg = dialogue_of(packs, elara["conv"])
    if dlg is None:
        return bad + ["the compiled %s is not in %s/cobblers_dialogue" % (elara["conv"], packs)], notes
    npc = Entity(npc_uuid(elara["npc"]), spot)
    cv = Conversation(dlg, functions, npc, None, pos=front)
    acts = []
    for pg in dlg["pages"]:
        inp = pg.get("input")
        acts += [inp] if isinstance(inp, str) else [o["action"] for o in (inp or {}).get("options", [])]
    admitted, landings, n = set(), {}, 0
    try:
        for stage in [None] + vals:
            for e in (None, 0, 1):
                d = {key(STAGE): stage} if stage is not None else {}
                if e is not None:
                    d[key(ELARA_FIELD)] = e
                for act in acts:
                    n += 1
                    for ev in cv.run(act, d, set())[0]:
                        if ev[0] == "moved" and inside(ev[2]):
                            admitted.add(stage)
                            landings.setdefault(stage, ev[2])
    except (Unmodelled, MolangError) as e:
        return bad + ["%s does not run in the model for a player at her door: %s" % (elara["conv"], e)], notes
    for st in sorted(map(str, admitted - doors)):
        bad.append("Elara lets a player at stage %s into the tower (the door gate opens at %s)" % (st, door_from))
    # the walk forks her battle both ways (the EMITTED callback for the win): at anchor_shutdown she lets a player in
    # only after the fight, so "reaches a move inside" is judged over the walk, whatever stage the move is made at
    win = win_for(packs, functions, elara["npc"], spot) if callback_src(packs) else None
    walk_cv = Conversation(dlg, functions, npc, win, pos=front)
    later = []
    for st in sorted(doors):
        try:
            _seen, evs = walk_cv.reach(sig({key(STAGE): st}, set()))
        except (Unmodelled, MolangError) as e:
            bad.append("%s from %s does not run in the model: %s" % (elara["conv"], st, e))
            continue
        moved = [ev for ev in evs if ev[0] == "moved" and inside(ev[2])]
        if not moved:
            bad.append("a player at stage %s talking to Elara at her door is never let in" % st)
            continue
        landings.setdefault(st, moved[0][2])
        if not any(ev[1].get(key(STAGE)) == st for ev in moved):
            later.append(st)
    # the emitted cycle against players where her moves put them
    cyc = "cobblers:hq_tower/cycle"
    if cyc not in functions:
        return dedupe(bad) + ["no emitted %s" % cyc], notes
    players, want, k = [], {}, 0

    def player(stage, pos, how):
        nonlocal k
        k += 1
        p = Player(uuid="00000000-0000-0000-0000-%012d" % (900000 + k), pos=pos)
        if stage is not None:
            p.data[key(STAGE)] = stage
        players.append(p)
        want[p.uuid] = (how, stage, pos)

    landing = next(iter(landings.values()), None)
    for stage in [None] + vals:
        if landing is not None:
            player(stage, landing, "stays" if stage in doors else "outside")
        player(stage, hole, "in_front")
        if stage in doors:
            player(stage, threshold, "stays")
    w = World(functions, players)
    try:
        w.function(cyc, None)
        after1 = {p.uuid: p.pos for p in players}
        w.function(cyc, None)
    except (Unmodelled, MolangError) as e:
        return dedupe(bad) + ["the gate cycle does not run in the model: %s" % e], notes
    for p in players:
        how, stage, pos0 = want[p.uuid]
        a = after1[p.uuid]
        if how == "stays" and a != pos0:
            bad.append("a player at stage %s legitimately inside at %s is moved to %s" % (stage, pos0, a))
        if how == "outside" and in_tower(a):
            bad.append("a player at stage %s where Elara's admit lands (%s) is left inside at %s" % (stage, pos0, a))
        if how == "in_front":
            ax, az = math.floor(a[0]) - sx, math.floor(a[2]) - sz
            on_line = (ax * fz - az * fx) == 0 and (ax * fx + az * fz) >= 1 and int(round(a[1])) == sy
            if not on_line or in_tower(a) or math.dist(a, spot) > 6:
                bad.append("a player at stage %s behind Elara at %s is moved to %s, not in front of her outside the "
                           "tower" % (stage, pos0, a))
        if p.pos != a:
            bad.append("the cycle's second run moves a player at stage %s from %s to %s" % (stage, a, p.pos))
    notes.append("door keeper: Elara at %s facing %s; %d direct actions run from her door; admitted at %s; let in "
                 "only after a later stage from %s; %d players cycled (admit landing, the hole, the threshold)"
                 % ((sx, sy, sz), (fx, fz), n, [s for s in vals if s in admitted], sorted(later), len(players)))
    return dedupe(bad)[:30], notes


# ------------------------------------------------------------------ the sweep

CALLS_GRANT = re.compile(re.escape(FLAG_GRANT_FN) + r"(?![a-z0-9_/])")
GRANT_FORMS = re.compile(r"advancement\s+grant\s+\S+\s+(everything|from|through|until|only)\b\s*(\S*)")


def check_sweep(packs):
    """Every emitted function, dialogue and callback: who grants the flag, who calls its grant, who writes the two
    defeat fields, who calls the won functions, who writes each chain stage. Allowed: the flag's own grant function,
    the binder's release_001 page; won_brann / won_elara alone write their field, the hq_tower callback alone calls
    them; each chain stage written by its own scene's conversation alone."""
    bad, seen = [], {"grant_callers": [], "grant_lines": [], "field_writers": {}, "won_callers": {}, "stage_writers": {}}
    fkeys = {key(BRANN_FIELD): "brann", key(ELARA_FIELD): "elara"}
    write = {k: re.compile(r"\b%s\s*=(?!=)" % re.escape(k)) for k in fkeys}
    won = {who: re.compile(re.escape(fn) + r"(?![a-z0-9_/])") for who, fn in WON_FN.items()}
    stage_w = {c["to"]: re.compile(r"%s\s*=\s*'%s'" % (re.escape(key(STAGE)), c["to"])) for c in CHAIN}
    root = Path(packs)
    for f in sorted(root.rglob("*")):
        if f.suffix not in (".mcfunction", ".json", ".molang") or not f.is_file():
            continue
        raw = f.read_bytes()
        hit = (b"rift_crisis_resolved" in raw or b"_defeated" in raw or b"hq_tower/won_" in raw
               or b"main_worldshift_reveal__stage" in raw
               or (b"advancement grant" in raw and (b" everything" in raw or b" through " in raw
                                                    or b" until " in raw or b" from " in raw)))
        if not hit:
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
        for who, rx in won.items():
            if rx.search(text):
                seen["won_callers"].setdefault(who, []).append(rel)
        for st, rx in stage_w.items():
            if rx.search(text):
                seen["stage_writers"].setdefault(st, []).append(rel)
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
    for k, who in fkeys.items():
        want = ["cobblers_hq_tower/data/cobblers/function/hq_tower/%s.mcfunction" % WON_FN[who].split("/")[-1]]
        if seen["field_writers"].get(k, []) != want:
            bad.append("%s is written by %s; only %s may write it" % (k, seen["field_writers"].get(k, []), want))
    for who in WON_FN:
        if seen["won_callers"].get(who, []) != [CALLBACK]:
            bad.append("%s is called from %s; only the battle_victory callback %s may"
                       % (WON_FN[who], seen["won_callers"].get(who, []), CALLBACK))
    for c in CHAIN:
        want = ["cobblers_dialogue/data/cobblers/dialogues/%s.json" % c["conv"]]
        if seen["stage_writers"].get(c["to"], []) != want:
            bad.append("stage %s is written by %s; only %s may write it" % (c["to"], seen["stage_writers"].get(c["to"], []),
                                                                         want))
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


def check_cradle(packs, functions, data=DATA):
    """The binder's stand is reachable from the passage in the cradle as built (the release is spoken there). Since
    the reconciliation nobody fights in the cradle, so there are no seats and no sight to check here."""
    bad, notes = [], []
    pack = Path(packs) / "cobblers_relic_underground"
    if not (pack / "data" / "cobblers" / "function" / "relic_underground" / "index.txt").is_file():
        return ["the relic pack is not built at %s: the binder's stand is NOT checked" % pack], notes
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
    pz0, pz1 = geo["passage_z"]
    outside = {c for c in ss if pz0 <= c[2] <= pz1 and px0 <= c[0] <= px1 and math.hypot(c[0] - cx, c[2] - cz) > r}
    if not outside:
        return ["no standable passage cell outside the cradle in the band z%d-%d: the walk has no start"
                % (pz0, pz1)], notes
    free = reach(cells, ss, outside)
    if geo["binder"] not in free:
        bad.append("the binder's stand %s is not reachable from the passage as built" % (geo["binder"],))
    notes.append("cradle: %d standable cells replayed, %d reached from the passage, the binder's stand %s"
                 % (len(ss), len(free), "among them" if geo["binder"] in free else "NOT among them"))
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

def audit(packs=PACKS, jar=None, data=DATA, skip_jar=False, spots=None):
    packs = Path(packs)
    functions = LazyFunctions(function_index(packs))
    recs = finale_ids(data)
    results = {}
    problems = []
    if sorted(recs) != ["brann", "elara"]:
        problems.append("data/finale_trainers.json does not carry both %s" % sorted(NAMES.values()))
        return problems, results
    spots = spots if spots is not None else placed_spots()
    cap = level_cap_after_gym8(data)
    results["cap"] = cap
    problems += check_fields(data)
    problems += check_finale_order(data)
    jp = None if skip_jar else find_jar(jar)
    b, n = check_parties(packs, recs, cap, jp)
    if skip_jar:
        b = [x for x in b if not x.startswith("no Cobblemon 1.8 jar")]
    problems += b
    results["parties"] = n
    results["jar"] = str(jp) if jp else None
    problems += check_defeat_fields(packs, functions, spots)
    b, n = check_conversation(packs, functions, data, spots)
    problems += b
    results["conversation"] = n
    problems += check_guards(packs, functions, data, spots)
    b, n = check_story(packs, functions, spots)
    problems += b
    results["story"] = n
    b, n = check_over_cap(packs, functions, data, spots)
    problems += b
    results["over_cap"] = n
    problems += check_release_effects(packs, functions)
    problems += check_progression(packs)
    b, n = check_gates(functions, data)
    problems += b
    results["gates"] = n
    b, n = check_door_keeper(packs, functions, data, spots)
    problems += b
    results["door_keeper"] = n
    b, seen = check_sweep(packs)
    problems += b
    results["sweep"] = seen
    b, n = check_cradle(packs, functions, data)
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
    for k in ("parties", "conversation", "story", "gates", "door_keeper", "cradle"):
        for line in results.get(k) or []:
            print("  " + line)
    print("  jar: %s" % results.get("jar"))
    for p in problems:
        print("PROBLEM " + p)
    print("finale_audit: %d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
