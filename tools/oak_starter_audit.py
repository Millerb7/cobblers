#!/usr/bin/env python
"""Independent audit of "Oak gives the starter" (the owner's priority zero), from the COMPILED dialogue and the config.

Written by a test author, not by the session that built it (builder commit a93f059). It never imports
tools/compile_dialogue.py or tests/test_oak_starter.py: it reads what the compiler WROTE (the dialogue JSON and the
callback Molang in build/datapacks/cobblers_dialogue), parses the Molang with its own tokenizer and parser, and runs
it on its own small model of the player, the scoreboard and Cobblemon's starter state.

WHERE THE EXPECTATIONS COME FROM
  the brief      the owner's priority zero: a new player is starter-locked, Oak's offer is the only thing that opens
                 the starter screen, "Not yet" leaves the offer standing, a player who has chosen never sees it again,
                 and nothing past Oak's send-off (any write of the main quest's stage) happens without a starter.
  Cobblemon      OpenStarterScreenCommand @1.8.0 as RELAYED by the builder and docs/research/notes/starter-selection.md
                 section 5 (not re-read from the jar here): a player who has chosen gets nothing and the command
                 returns 0; anyone else is unlocked, prompted and sent the list, and it returns 1. chooseStarter
                 refuses a locked player and a second pick. That is the model's `openstarterscreen`; see OPEN below.
  vanilla        `execute store result score` into an objective that does not exist stores nothing; `if score ...
                 matches N` is false for a holder with no score.
  the data       only to NAME things: the main quest's stage field and its initial value (data/quests.json,
                 data/progression.json) and the five species (the brief, checked against the config). No node id, no
                 expected page order and no response id is read from data/dialogue.json: the offer is found in the
                 compiled output as the page whose option runs openstarterscreen.

WHAT IS CHECKED
  P1  Oak's compiled conversation, explored over every option and every talk/pick order from a fresh player (and a
      legacy player who chose before the lock): the offer page is shown before any write of the main stage, and no
      write of the main stage happens unless Cobblemon says the player has chosen AND the player carries the tag.
      Every other compiled dialogue (and any callback or function) that writes the main stage is checked by guard:
      from the initial stage, with the starter tag absent, no write is reachable.
  P2  exactly one `openstarterscreen` in all compiled dialogue and every file of every pack under build/datapacks, and
      it is in Oak's dialogue (the one an NPC class named Oak opens); no file gives or spawns one of the five species
      (a give/spawn/summon/loot verb with the species on the same line or in the same Molang string; a give/spawn
      whose species is a macro is flagged when its pack names a starter species anywhere).
  P3  "Not yet" (the offer's other options) closes with the offer still standing: the next talk shows the offer again;
      a player carrying the tag, at any cursor value, never sees the offer or the page that leads to it.
  P4  modpack/config/cobblemon/starters.json: allowStarterOnJoin FALSE (the owner, 2026-10-06: "Oak offering the
      starters in the lab as a scene rather than a menu on join"; it was true from 2026-10-05), exactly the five
      aspect=cobblers_starter_1
      entries; no pack under build/datapacks (nor modpack/) ships data/<ns>/starters/.
  P5  REPORTED, not failed: quests, flags and rewards the data makes available before Oak that assume a party (a
      battle, an encounter, a party check); FAILED: an RCT initial level cap below the starters' level.
  P6  liveness: from every explored state in which the player has chosen, some sequence of talks reaches the send-off.

WHAT IT DOES NOT COVER (a running server, an experiment): that the starter_chosen callback fires; that the client keeps
the starter screen when the dialogue closes; that a locked player's own key is refused; that openstarterscreen
returns what the relayed reading says. OPEN, printed every run: if openstarterscreen FAILS at run time (throws),
1.20.3+ `execute store result` stores 0 on failure (vanilla semantics, relayed from memory, not read from source
here), which is the value the compiled action reads as "already chosen".

  python tools/oak_starter_audit.py [--packs build/datapacks] [--dialogue <pack>] [--compile]
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "build" / "datapacks"
CONFIG = ROOT / "modpack" / "config" / "cobblemon" / "starters.json"
RCT = ROOT / "modpack" / "config" / "rctmod-server.toml"

STARTERS = {"cosmog", "kubfu", "typenull", "poipole", "meltan",       # the brief / NATIVE_STARTERS_COST.md 6a
            "larvesta"}                                               # the sixth, the owner 2026-10-08
STARTER_ASPECT = "cobblers_starter_1"
# P2's give/spawn sweep names the five mythicals only. Larvesta is wild by design (data/spawns.json, levels 38-53) and
# an ambient display in two towns (data/ambient_towns/gorge_hamlet.json, gym7_town.json, spawned through a macro), so
# naming the species would fault those as starter gives. NOT covered: a give of Larvesta WITH aspect=cobblers_starter_1
# (the real leak) -- left for the test author to add, keyed on the aspect rather than the species.
SPECIES_RE = re.compile(r"(?<![a-z0-9_])(?:cobblemon:)?(cosmog|kubfu|type_?null|poipole|meltan)(?![a-z0-9_])", re.I)
GIVE_RE = re.compile(r"(?<![a-z0-9_])(give_?pokemon\w*|pokegive\w*|spawn_?pokemon\w*|pokespawn\w*|summon|give|loot)"
                     r"(?![a-z0-9_])", re.I)
POKEGIVE_RE = re.compile(r"(?<![a-z0-9_])(give_?pokemon\w*|pokegive\w*|spawn_?pokemon\w*|pokespawn\w*)(?![a-z0-9_])",
                         re.I)
UNCATCHABLE_RE = re.compile(r"(?<![a-z0-9_])uncatchable(?![a-z0-9_])", re.I)
SCREEN = "openstarterscreen"
DIALOGUE_PACK = "cobblers_dialogue"           # compile_dialogue.py's default pack under build/datapacks
NPC_NAME = re.compile(r"\boak\b", re.I)

# KNOWN defects in the builder's work: the problem list must equal this set exactly (a new one fails; a fixed one
# fails until it is removed here). Key: (check, short id). None at the time of writing (2026-10-04, a93f059).
KNOWN: dict = {}

OPEN = [
    "openstarterscreen's results (0 = already chosen, 1 = opened) are RELAYED from the builder's reading of "
    "OpenStarterScreenCommand.kt @1.8.0; not re-read here.",
    "if openstarterscreen throws at run time, `execute store result` stores 0 on failure in 1.20.3+ (relayed from "
    "memory of vanilla, not read from source here) and the compiled action would read that 0 as 'already chosen' "
    "and tag a player with no starter. Needs an in-game check, not a pytest.",
]


# ===================================================================================================== Molang
class MolangError(Exception):
    pass


_TOK = re.compile(r"\s*(?:(?P<str>'(?:\\.|[^'\\])*')|(?P<num>\d+(?:\.\d+)?)"
                  r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
                  r"|(?P<op>==|!=|<=|>=|&&|\|\||[!?:=(){};+\-<>*/,]))")


def tokenize(text):
    out, i = [], 0
    text = text.rstrip()
    while i < len(text):
        m = _TOK.match(text, i)
        if not m or m.end() == i:
            if text[i:].strip() == "":
                break
            raise MolangError("cannot tokenize at %r" % text[i:i + 30])
        i = m.end()
        kind = m.lastgroup
        v = m.group(kind)
        if kind == "str":
            v = v[1:-1].replace("\\'", "'")
        elif kind == "num":
            v = float(v)
        out.append((kind, v))
    return out


class Parser:
    def __init__(self, text):
        self.t = tokenize(text)
        self.i = 0

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else (None, None)

    def is_op(self, v):
        return self.peek() == ("op", v)

    def take(self, v=None):
        tok = self.peek()
        if tok[0] is None or (v is not None and tok != ("op", v)):
            raise MolangError("expected %r, got %r" % (v, tok))
        self.i += 1
        return tok

    def program(self):
        stmts = []
        while self.peek()[0] is not None:
            s = self.stmt()
            if s is not None:
                stmts.append(s)
        return ("block", stmts)

    def stmt(self):
        if self.is_op(";"):
            self.take()
            return None
        if self.peek() == ("name", "return"):
            self.take()
            e = self.expr()
            if self.is_op(";"):
                self.take()
            return ("return", e)
        e = self.expr()
        if self.is_op(";"):
            self.take()
        return e

    def block(self):
        self.take("{")
        stmts = []
        while not self.is_op("}"):
            if self.peek()[0] is None:
                raise MolangError("unclosed block")
            s = self.stmt()
            if s is not None:
                stmts.append(s)
        self.take("}")
        return ("block", stmts)

    def expr(self):
        lhs = self.ternary()
        if self.is_op("="):
            self.take()
            if lhs[0] != "name":
                raise MolangError("assignment to %r" % (lhs,))
            return ("assign", lhs[1], self.expr())
        return lhs

    def ternary(self):
        c = self.binop(0)
        if self.is_op("?"):
            self.take()
            a = self.branch()
            b = None
            if self.is_op(":"):
                self.take()
                b = self.branch()
            return ("tern", c, a, b)
        return c

    def branch(self):
        return self.block() if self.is_op("{") else self.ternary()

    LEVELS = [("||",), ("&&",), ("==", "!=", "<", ">", "<=", ">="), ("+", "-"), ("*", "/")]

    def binop(self, lvl):
        if lvl == len(self.LEVELS):
            return self.unary()
        a = self.binop(lvl + 1)
        while self.peek()[0] == "op" and self.peek()[1] in self.LEVELS[lvl]:
            op = self.take()[1]
            a = ("bin", op, a, self.binop(lvl + 1))
        return a

    def unary(self):
        if self.is_op("!"):
            self.take()
            return ("not", self.unary())
        if self.is_op("-"):
            self.take()
            return ("neg", self.unary())
        return self.primary()

    def primary(self):
        kind, v = self.peek()
        if kind == "num":
            self.take()
            return ("num", v)
        if kind == "str":
            self.take()
            return ("str", v)
        if self.is_op("("):
            self.take()
            e = self.expr()
            self.take(")")
            return e
        if self.is_op("{"):
            return self.block()
        if kind == "name":
            self.take()
            if self.is_op("("):
                self.take()
                args = []
                while not self.is_op(")"):
                    args.append(self.expr())
                    if self.is_op(","):
                        self.take()
                self.take(")")
                return ("call", v, args)
            return ("name", v)
        raise MolangError("unexpected %r" % ((kind, v),))


def parse(text):
    return Parser(text).program()


DATA = object()          # the value of q.player.data()


class Return(Exception):
    def __init__(self, v):
        self.v = v


class Run:
    """One script evaluation against a mutable player model `w` (dict). Hooks report page shows and stage writes."""

    def __init__(self, w, model, v=None):
        self.w, self.m = w, model
        self.v = v if v is not None else {}
        self.t = {}
        self.page, self.closed = None, False

    def truth(self, x):
        if isinstance(x, str):
            return x != ""
        return x != 0

    def read(self, name):
        if name.startswith("t.d."):
            if self.t.get("d") is not DATA:
                return 0.0
            return self.w["data"].get(name[4:], 0.0)
        if name.startswith("v."):
            return self.v.get(name[2:], 0.0)
        if name.startswith("t."):
            return self.t.get(name[2:], 0.0)
        if name == "q.player.uuid":
            return "PLAYER-UUID"
        if name == "q.player.username":
            return "Player"
        raise MolangError("read of %s" % name)

    def write(self, name, val):
        if name.startswith("t.d."):
            if self.t.get("d") is not DATA:
                raise MolangError("write of %s before t.d = q.player.data()" % name)
            key = name[4:]
            self.w["data"][key] = val
            self.m.on_write(self, key, val)
        elif name.startswith("v."):
            self.v[name[2:]] = val
        elif name.startswith("t."):
            self.t[name[2:]] = val
        else:
            raise MolangError("write of %s" % name)

    def call(self, fn, args):
        a = [self.ev(x) for x in args]
        if fn == "q.player.data":
            return DATA
        if fn == "q.player.save_data":
            return 1.0
        if fn == "q.player.has_tag":
            return 1.0 if a[0] in self.w["tags"] else 0.0
        if fn == "q.run_command":
            self.m.command(self.w, a[0])
            return 1.0
        if fn == "q.dialogue.set_page":
            self.page = a[0]
            return 1.0
        if fn == "q.dialogue.close":
            self.closed = True
            return 1.0
        if fn == "q.npc.start_battle":
            self.closed = True
            return 1.0
        raise MolangError("call of %s" % fn)

    def ev(self, n):
        k = n[0]
        if k == "num" or k == "str":
            return n[1]
        if k == "name":
            return self.read(n[1])
        if k == "assign":
            val = self.ev(n[2])
            self.write(n[1], val)
            return val
        if k == "call":
            return self.call(n[1], n[2])
        if k == "not":
            return 0.0 if self.truth(self.ev(n[1])) else 1.0
        if k == "neg":
            return -self.ev(n[1])
        if k == "bin":
            op = n[1]
            if op == "&&":
                return 1.0 if self.truth(self.ev(n[2])) and self.truth(self.ev(n[3])) else 0.0
            if op == "||":
                return 1.0 if self.truth(self.ev(n[2])) or self.truth(self.ev(n[3])) else 0.0
            x, y = self.ev(n[2]), self.ev(n[3])
            if op == "+":
                if isinstance(x, str) or isinstance(y, str):
                    return "%s%s" % (x if isinstance(x, str) else int(x), y if isinstance(y, str) else int(y))
                return x + y
            if op in ("==", "!="):
                same = type(x) is type(y) and x == y
                return 1.0 if same == (op == "==") else 0.0
            raise MolangError("operator %s" % op)
        if k == "tern":
            if self.truth(self.ev(n[1])):
                return self.ev(n[2])
            return self.ev(n[3]) if n[3] is not None else 0.0
        if k == "block":
            r = 0.0
            for s in n[1]:
                r = self.ev(s)
            return r
        if k == "return":
            raise Return(self.ev(n[1]))
        raise MolangError("node %s" % k)

    def exec(self, text):
        try:
            self.ev(parse(text))
        except Return as r:
            return r.v
        return None


# ===================================================================================================== the player model
class Model:
    """The player, the scoreboard and Cobblemon's starter state, as the compiled commands touch them."""

    def __init__(self, stage_key):
        self.stage_key = stage_key
        self.writes = []            # (value, chosen, tagged, offer_seen) per write of the main stage, current talk
        self.unknown = []           # commands the model does not interpret
        self.screens = 0

    def on_write(self, run, key, val):
        if key == self.stage_key:
            w = run.w
            self.writes.append((val, w["chosen"], STARTER_TAG_HOLDER["tag"] in w["tags"], w["offer_seen"]))

    def command(self, w, cmd):
        return self._cmd(w, cmd.strip())

    def _cmd(self, w, cmd):
        """The command's result (int), or None when it fails (vanilla: nothing is stored on a parse failure)."""
        m = re.fullmatch(r"scoreboard objectives add (\S+) dummy", cmd)
        if m:
            w["objectives"].add(m.group(1))
            return 1
        m = re.fullmatch(r"execute as (PLAYER-UUID|Player|@s) (.*)", cmd)
        if m:
            return self._sub(w, m.group(2))
        m = re.fullmatch(r"tag (PLAYER-UUID|Player|@s) (add|remove) (\S+)", cmd)
        if m:
            (w["tags"].add if m.group(2) == "add" else w["tags"].discard)(m.group(3))
            return 1
        self.unknown.append(cmd)
        return None

    def _sub(self, w, rest):
        m = re.fullmatch(r"run (.*)", rest)
        if m:
            return self._leaf(w, m.group(1))
        m = re.fullmatch(r"if score @s (\S+) matches (-?\d+) (.*)", rest)
        if m:
            obj, n, more = m.group(1), int(m.group(2)), m.group(3)
            if w["scores"].get(obj) != n:
                return None
            return self._sub(w, more)
        m = re.fullmatch(r"store result score @s (\S+) (.*)", rest)
        if m:
            obj, more = m.group(1), m.group(2)
            r = self._sub(w, more)
            if r is not None and obj in w["objectives"]:
                w["scores"][obj] = r
            return r
        # a progression flag probe (compile_dialogue's `flag` condition; first in Oak's dialogue 2026-10-06, the League
        # rules choice). The explored players hold no flag, so it never passes (integrator edit to the model only)
        m = re.fullmatch(r"if entity @s\[advancements=\{cobblers:flag/[a-z0-9_]+=true\}\] (.*)", rest)
        if m:
            return None
        # compile_dialogue's `function` effect runs as AND at the player; the position changes nothing modelled here
        m = re.fullmatch(r"at @s (.*)", rest)
        if m:
            return self._sub(w, m.group(1))
        self.unknown.append("execute as @s " + rest)
        return None

    # A progression flag's grant (test author, 2026-10-08, for the held Pallet -> gym 1 waypoint in
    # docs/world-building/WALK_P2.md section 2). tools/progression_pack.py writes flag/<id>/grant (`advancement grant
    # @s only cobblers:flag/<id>`) only for a flag data/progression.json declares with set_by.kind quest_transition;
    # an advancement moves neither the starter state nor the main stage, so a grant of such a flag is a success that
    # touches nothing this audit checks. Any other flag has no grant function, and stays an unmodelled command.
    flag_registry = None

    def _grantable(self, fid):
        if Model.flag_registry is None:
            prog = json.loads((Path(__file__).resolve().parent.parent / "data" / "progression.json")
                              .read_text(encoding="utf-8"))
            Model.flag_registry = {f["id"]: f for f in prog.get("flags") or []}
        f = Model.flag_registry.get(fid)
        return f is not None and (f.get("set_by") or {}).get("kind") == "quest_transition"

    def _leaf(self, w, cmd):
        m = re.fullmatch(r"scoreboard players set @s (\S+) (-?\d+)", cmd)
        if m:
            if m.group(1) not in w["objectives"]:
                return None
            w["scores"][m.group(1)] = int(m.group(2))
            return 1
        m = re.fullmatch(r"tag @s (add|remove) (\S+)", cmd)
        if m:
            (w["tags"].add if m.group(1) == "add" else w["tags"].discard)(m.group(2))
            return 1
        # Oak's League rules choice (2026-10-06, integrator edit to the model only): rctmod's series command and the
        # mode tag move neither the starter state nor the main stage, so they are modelled as successes that touch
        # nothing this audit checks. Their own guarantees are docs/mechanics/OAK_AND_CHALLENGE.md's audit list
        m = re.fullmatch(r"rctmod player set series ([a-z0-9_]+) @s", cmd)
        if m:
            return 1
        m = re.fullmatch(r"function cobblers:flag/([a-z0-9_]+)/grant", cmd)
        if m and self._grantable(m.group(1)):
            return 1
        if re.fullmatch(r"%s @s" % SCREEN, cmd):
            # RELAYED semantics (see OPEN): a player who has chosen gets nothing and 0; anyone else is unlocked and 1
            if w["chosen"]:
                return 0
            w["unlocked"] = True
            self.screens += 1
            return 1
        self.unknown.append(cmd)
        return None


STARTER_TAG_HOLDER = {"tag": None}     # the tag Oak's compiled action reads after openstarterscreen (found, not assumed)


def freeze(w):
    return (tuple(sorted((k, v) for k, v in w["data"].items())), frozenset(w["tags"]),
            tuple(sorted(w["scores"].items())), frozenset(w["objectives"]), w["chosen"], w["unlocked"],
            w["offer_seen"], w["notyet"])


def thaw(f):
    return {"data": dict(f[0]), "tags": set(f[1]), "scores": dict(f[2]), "objectives": set(f[3]), "chosen": f[4],
            "unlocked": f[5], "offer_seen": f[6], "notyet": f[7]}


# ===================================================================================================== reading the build
def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dialogues_in(root):
    """{dialogue id 'ns:path': (file, json)} for every data/<ns>/dialogues/**.json under root."""
    out = {}
    for f in sorted(Path(root).rglob("*.json")):
        parts = f.relative_to(root).parts
        if "dialogues" in parts:
            i = parts.index("dialogues")
            if i >= 2 and parts[i - 2] == "data":
                did = "%s:%s" % (parts[i - 1], "/".join(parts[i + 1:])[:-5])
                try:
                    out[did] = (f, read_json(f))
                except ValueError:
                    pass
    return out


def npc_classes_in(root):
    out = []
    for f in sorted(Path(root).rglob("*.json")):
        parts = f.relative_to(root).parts
        if "npcs" in parts:
            try:
                out.append((f, read_json(f)))
            except ValueError:
                pass
    return out


def molang_strings(dlg):
    """(where, kind, text) for every Molang string of a compiled dialogue."""
    out = [("initializationAction", "init", dlg.get("initializationAction") or "")]
    for p in dlg.get("pages") or []:
        inp = p.get("input")
        if isinstance(inp, str):
            out.append(("page %s input" % p.get("id"), "input", inp))
        elif isinstance(inp, dict):
            for o in inp.get("options") or []:
                out.append(("page %s option %s action" % (p.get("id"), o.get("value")), "action", o.get("action") or ""))
                if o.get("isVisible"):
                    out.append(("page %s option %s isVisible" % (p.get("id"), o.get("value")), "visible", o["isVisible"]))
    return out


def text_files(root, exclude=None):
    """(path, text) for every file under root a datapack can run or load (gzip .nbt decompressed; zips opened),
    skipping the tree `exclude` (a stale compiled dialogue when the audit was pointed at a fresh one)."""
    root = Path(root)
    if not root.exists():
        return
    ex = Path(exclude).resolve() if exclude is not None else None
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        if ex is not None and ex in f.resolve().parents:
            continue
        try:
            if f.suffix == ".nbt":
                raw = gzip.decompress(f.read_bytes())
                yield f, raw.decode("utf-8", "replace")
            elif f.suffix == ".zip":
                with zipfile.ZipFile(f) as z:
                    for n in z.namelist():
                        if not n.endswith("/"):
                            yield Path("%s!/%s" % (f, n)), z.read(n).decode("utf-8", "replace")
            elif f.suffix in (".png", ".ogg", ".jar"):
                continue
            else:
                yield f, f.read_bytes().decode("utf-8", "replace")
        except (OSError, ValueError, zipfile.BadZipFile, EOFError):
            yield f, ""


def paths_in(root):
    root = Path(root)
    if not root.exists():
        return []
    out = []
    for f in root.rglob("*"):
        if f.is_file() and f.suffix == ".zip":
            try:
                with zipfile.ZipFile(f) as z:
                    out += ["%s!/%s" % (f.as_posix(), n) for n in z.namelist()]
            except zipfile.BadZipFile:
                pass
        out.append(f.as_posix())
    return out


# ===================================================================================================== the checks
class Audit:
    def __init__(self, dialogue_dir, packs_dir, config, data_dir, rct, extra_starter_roots=()):
        self.dialogue_dir, self.packs_dir = Path(dialogue_dir), Path(packs_dir)
        self.config, self.data_dir, self.rct = Path(config), Path(data_dir), Path(rct)
        self.extra_roots = [Path(r) for r in extra_starter_roots]
        self.problems, self.reports, self.notes = [], [], []

    def fail(self, check, key, msg):
        self.problems.append((check, key, msg))

    # ------------------------------------------------------------------ the main stage, named from the data
    def stage_field(self):
        quests = read_json(self.data_dir / "quests.json")["quests"]
        mains = [q["id"] for q in quests if q["id"].startswith("main_")]
        prog = {f["id"]: f for f in read_json(self.data_dir / "progression.json")["quest_fields"]}
        out = []
        for qid in mains:
            fid = "quest.%s.stage" % qid
            if fid in prog:
                out.append(("cobblers__quest__%s__stage" % qid, prog[fid].get("initial")))
        if len(out) != 1:
            raise SystemExit("oak_starter_audit: expected one main quest stage field, found %r" % out)
        return out[0]

    # ------------------------------------------------------------------ P2 sweep
    def roots(self):
        """[(root, excluded subtree)]: the compiled dialogue, then every pack, minus a stale copy of the dialogue pack
        when the dialogue audited is not the one under the packs."""
        out = [(self.dialogue_dir, None)]
        if self.packs_dir.exists():
            d, pk = self.dialogue_dir.resolve(), self.packs_dir.resolve()
            inside = pk in d.parents
            out.append((self.packs_dir, None if inside else self.packs_dir / DIALOGUE_PACK))
        return out

    def sweep(self):
        roots = [r for r, _ in self.roots()]
        seen, screens, gives, macro_sites, starter_named, displays = set(), [], [], [], {}, []
        for r, ex in self.roots():
            for f, text in text_files(r, ex):
                key = str(Path(f).resolve()) if "!/" not in str(f) else str(f)
                if key in seen:
                    continue
                seen.add(key)
                n = text.count(SCREEN)
                if n:
                    screens.append((f, n))
                low = text.lower()
                has_species = SPECIES_RE.search(low) is not None
                if has_species:
                    starter_named[self.pack_of(f, r)] = f
                if not (has_species or "$(" in text):
                    continue
                for unit in re.split(r"[\n;]", text):
                    if POKEGIVE_RE.search(unit) and "$(" in unit and not SPECIES_RE.search(unit):
                        macro_sites.append((f, r, unit.strip()[:160]))
                    if SPECIES_RE.search(unit) and GIVE_RE.search(unit):
                        # a display: only spawn verbs, and the Cobblemon `uncatchable` flag on the same line (VERIFIED
                        # in game, EXP-023; docs/research/notes/wild-mega-pokemon.md) -- Oak's lab actors, 2026-10-06
                        verbs = {m.group(1).lower() for m in GIVE_RE.finditer(unit)}
                        if all(v.startswith(("spawn", "pokespawn")) for v in verbs) and UNCATCHABLE_RE.search(unit):
                            displays.append(f)
                            continue
                        gives.append((f, unit.strip()[:160]))
        if displays:
            self.notes.append("P2 %d uncatchable display spawn(s) of a starter species, not counted as gives (%d file(s))"
                      % (len(displays), len(set(map(str, displays)))))
        for f, unit in gives:
            self.fail("P2", "starter_given:%s" % Path(str(f)).name, "%s gives or spawns a starter species: %s" % (f, unit))
        for f, r, unit in macro_sites:
            pk = self.pack_of(f, r)
            if pk in starter_named:
                self.fail("P2", "starter_macro:%s" % Path(str(f)).name,
                          "%s gives/spawns a macro species and its pack names a starter species (%s): %s"
                          % (f, starter_named[pk], unit))
        self.notes.append("P2 swept %d files under %s; %d macro give/spawn sites"
                          % (len(seen), " + ".join(str(r) for r in roots), len(macro_sites)))
        return screens

    def pack_of(self, f, root):
        rel = Path(str(f).split("!/")[0]).resolve().relative_to(Path(root).resolve()).parts
        return (str(Path(root).resolve()), rel[0] if len(rel) > 1 else "")

    # ------------------------------------------------------------------ P4
    def check_config(self):
        cfg = read_json(self.config)
        # the owner, 2026-10-06: "Oak offering the starters in the lab as a scene rather than a menu on join" -- the
        # rule is back to a93f059's: locked on join, Oak's offer is the one door (integrator edit, the owner's call)
        if cfg.get("allowStarterOnJoin") is not False:
            self.fail("P4", "allow_on_join", "%s allowStarterOnJoin is %r, not false: the chooser opens on join instead "
                      "of in Oak's lab" % (self.config, cfg.get("allowStarterOnJoin")))
        entries = [p for c in cfg.get("starters") or [] for p in c.get("pokemon") or []]
        species, bad = set(), []
        for e in entries:
            toks = e.split()
            sp = toks[0].lower().split(":")[-1] if toks else ""
            species.add(sp)
            if "aspect=%s" % STARTER_ASPECT not in toks:
                bad.append(e)
        if len(entries) != len(STARTERS) or species != STARTERS or bad:
            self.fail("P4", "five_entries", "%s offers %d entries %r (want exactly the six with aspect=%s; without "
                      "it: %r)" % (self.config, len(entries), sorted(species), STARTER_ASPECT, bad))
        level = None
        for e in entries:
            m = re.search(r"\blevel=(\d+)", e)
            if m:
                level = max(level or 0, int(m.group(1)))
        ship = []
        for root in [self.packs_dir, self.dialogue_dir] + self.extra_roots:
            for p in paths_in(root):
                if re.search(r"(^|/)data/[^/]+/starters/", p.split("!/")[-1] if "!/" in p else p):
                    ship.append(p)
        if ship:
            self.fail("P4", "starters_datapack", "a pack ships data/<ns>/starters/ (with useConfigStarters %r a "
                      "datapack list REPLACES the config's): %s" % (cfg.get("useConfigStarters"), sorted(set(ship))[:5]))
        return level

    # ------------------------------------------------------------------ P1 (global), by guard
    def tri(self, n, stage, tag):
        """Three-valued value of a guard expression: a value, or None (unknown)."""
        k = n[0]
        if k in ("num", "str"):
            return n[1]
        if k == "name":
            return stage if n[1] == "t.d." + self.stage_key else None
        if k == "call":
            if n[1] == "q.player.has_tag" and n[2] and n[2][0][0] == "str" and n[2][0][1] == tag:
                return 0.0
            return None
        if k == "not":
            x = self.tri(n[1], stage, tag)
            return None if x is None else (0.0 if self.truthy(x) else 1.0)
        if k == "bin":
            op = n[1]
            a, b = self.tri(n[2], stage, tag), self.tri(n[3], stage, tag)
            if op == "&&":
                if (a is not None and not self.truthy(a)) or (b is not None and not self.truthy(b)):
                    return 0.0
                return None if a is None or b is None else 1.0
            if op == "||":
                if (a is not None and self.truthy(a)) or (b is not None and self.truthy(b)):
                    return 1.0
                return None if a is None or b is None else 0.0
            if a is None or b is None:
                return None
            if op in ("==", "!="):
                same = type(a) is type(b) and a == b
                return 1.0 if same == (op == "==") else 0.0
            return None
        return None

    @staticmethod
    def truthy(x):
        return x != "" if isinstance(x, str) else x != 0

    def stage_writes(self, node, guards, out):
        """(value node, [(cond, polarity)]) for every assignment to the main stage under node."""
        k = node[0]
        if k == "assign":
            if node[1] == "t.d." + self.stage_key:
                out.append((node[2], list(guards)))
            self.stage_writes(node[2], guards, out)
        elif k == "tern":
            self.stage_writes(node[1], guards, out)
            self.stage_writes(node[2], guards + [(node[1], True)], out)
            if node[3] is not None:
                self.stage_writes(node[3], guards + [(node[1], False)], out)
        elif k == "block":
            for s in node[1]:
                self.stage_writes(s, guards, out)
        elif k in ("not", "neg", "return"):
            self.stage_writes(node[1], guards, out)
        elif k == "bin":
            self.stage_writes(node[2], guards, out)
            self.stage_writes(node[3], guards, out)
        elif k == "call":
            for a in node[2]:
                self.stage_writes(a, guards, out)
        return out

    def global_stage(self, oak_file, tag, oak_tagless_writes):
        write_re = re.compile(r"%s\s*=(?!=)" % re.escape(self.stage_key))
        edges = []           # (where, value or None, guards)
        seen = set()
        for r, ex in self.roots():
            for f, text in text_files(r, ex):
                if not write_re.search(text):
                    continue
                key = str(Path(str(f).split("!/")[0]).resolve())
                if key in seen:
                    continue
                seen.add(key)
                strings = []
                if f.suffix == ".json" and "dialogues" in Path(str(f)).parts:
                    if Path(str(f)).resolve() == Path(oak_file).resolve():
                        continue                  # explored exactly in P1 below (by file: a stale copy is not skipped)
                    strings = [(w, t) for w, _, t in molang_strings(json.loads(text))]
                elif f.suffix == ".molang":
                    strings = [("callback", text)]
                else:
                    for m in re.finditer(r'runmolang\s+"((?:\\.|[^"\\])*)"', text):
                        strings.append(("runmolang", m.group(1).replace('\\"', '"').replace("\\\\", "\\")))
                    if not strings:
                        self.fail("P1", "stage_write_unparsed:%s" % Path(str(f)).name,
                                  "%s writes the main stage outside a dialogue, callback or runmolang" % f)
                for where, t in strings:
                    if not write_re.search(t):
                        continue
                    try:
                        ast = parse(t)
                    except MolangError as e:
                        self.fail("P1", "stage_write_unparsed:%s" % Path(str(f)).name, "%s %s: %s" % (f, where, e))
                        continue
                    for val, guards in self.stage_writes(ast, [], []):
                        edges.append(("%s %s" % (Path(str(f)).name, where), val[1] if val[0] == "str" else None, guards))
        start = {self.stage_initial, 0.0}
        S = set(start) | {v for v, _ in oak_tagless_writes}
        changed = True
        while changed:
            changed = False
            for where, val, guards in edges:
                ok = any(all(self.tri(c, s, tag) is None or self.truthy(self.tri(c, s, tag)) == pol
                             for c, pol in guards) for s in S)
                if ok:
                    if val is None:
                        self.fail("P1", "stage_write_any:%s" % where, "%s writes a computed main stage reachable "
                                  "without the starter tag" % where)
                        continue
                    if val not in S:
                        S.add(val)
                        changed = True
        tagless = sorted(str(s) for s in S - start)
        if tagless:
            self.fail("P1", "stage_without_starter", "main stage values reachable with no starter tag from %r: %s"
                      % (self.stage_initial, tagless))
        self.notes.append("P1 global: %d main-stage writes outside Oak's dialogue, none reachable without the tag"
                          % len(edges) if not tagless else "P1 global: %d writes" % len(edges))

    def dialogue_id(self, f):
        parts = Path(str(f)).parts
        i = parts.index("dialogues")
        return "%s:%s" % (parts[i - 1], "/".join(parts[i + 1:])[:-5])

    # ------------------------------------------------------------------ P1/P3/P6 in Oak's dialogue, explored
    def explore(self, dlg, tag, callbacks):
        pages = {p["id"]: p for p in dlg["pages"]}
        offer = [pid for pid, p in pages.items() if isinstance(p.get("input"), dict)
                 and any(SCREEN in (o.get("action") or "") for o in p["input"].get("options") or [])]
        if len(offer) != 1:
            self.fail("P1", "offer_page", "Oak's dialogue has %d pages offering the starter screen" % len(offer))
            return []
        offer = offer[0]
        model = Model(self.stage_key)
        STARTER_TAG_HOLDER["tag"] = tag
        events = []          # (from frozen, to frozen, kind, shown pages, writes)

        def talk(w):
            """[(end world, shown pages, writes, chose option values)] for every option path of one talk."""
            results = []
            w["notyet"] = False
            r = Run(w, model)
            model.writes = []
            r.exec(dlg["initializationAction"])
            stack = [(w, r.page if not r.closed else None, r.v, [], list(model.writes), [], None)]
            while stack:
                w0, page, v, shown, writes, opts, ny = stack.pop()
                if ny is not None and len(writes) > ny:
                    self.fail("P3", "not_yet_returns", "'Not yet' (options %s) goes on to write the main stage %r "
                              "in the same talk instead of leaving the offer standing" % (opts, writes[ny:]))
                    ny = None
                if page is None:
                    results.append((w0, shown, writes, opts))
                    continue
                if len(shown) > 64:
                    self.fail("P1", "no_settle", "Oak's dialogue shows more than 64 pages in one talk: %s" % shown[-8:])
                    continue
                if page not in pages:
                    self.fail("P1", "bad_page:%s" % page, "Oak's dialogue sets page %r, which it does not have" % page)
                    continue
                if page == offer:
                    w0["offer_seen"] = True
                inp = pages[page].get("input")
                if isinstance(inp, str):
                    w1, v1 = copy.deepcopy(w0), dict(v)
                    rr = Run(w1, model, v1)
                    model.writes = []
                    rr.exec(inp)
                    stack.append((w1, None if rr.closed else rr.page, v1, shown + [page], writes + model.writes, opts,
                                  ny))
                    continue
                for o in inp.get("options") or []:
                    if o.get("isVisible"):
                        vis = Run(copy.deepcopy(w0), model, {}).exec(o["isVisible"])
                        if vis is not None and not Run(w0, model).truth(vis):
                            continue
                    w1, v1 = copy.deepcopy(w0), dict(v)
                    w1["notyet"] = page == offer and SCREEN not in (o.get("action") or "")
                    rr = Run(w1, model, v1)
                    model.writes = []
                    rr.page = None
                    rr.exec(o.get("action") or "")
                    nxt = None if rr.closed else rr.page
                    if nxt is None and not rr.closed:
                        self.fail("P1", "option_dangles:%s" % o.get("value"),
                                  "option %s on page %s neither moves nor closes" % (o.get("value"), page))
                    stack.append((w1, nxt, v1, shown + [page], writes + model.writes, opts + [o.get("value")],
                                  len(writes) if w1["notyet"] else ny))
            return results

        def pick(w):
            if not w["unlocked"] or w["chosen"]:
                return None
            w1 = copy.deepcopy(w)
            w1["chosen"] = True
            for cb in callbacks:
                Run(w1, model).exec(cb)
            return w1

        def base(chosen, tags=(), cursor_key=None, cursor=None):
            w = {"data": {}, "tags": set(tags), "scores": {}, "objectives": set(), "chosen": chosen,
                 "unlocked": chosen, "offer_seen": False, "notyet": False}
            if cursor_key is not None:
                w["data"][cursor_key] = cursor
            return freeze(w)

        fresh = base(False)
        legacy = base(True)
        seeds = [fresh, legacy]
        graph, todo, seen = {}, list(seeds), set(seeds)
        lead_in = None
        while todo:
            f = todo.pop()
            w = thaw(f)
            out = []
            for end, shown, writes, opts in talk(copy.deepcopy(w)):
                end["notyet"] = end["notyet"] and not writes
                g = freeze(end)
                out.append((g, "talk", shown, writes, opts))
                if f == fresh and lead_in is None and offer in shown:
                    lead_in = shown[:shown.index(offer) + 1]
                for val, chosen, tagged, offer_seen in writes:
                    if not offer_seen:
                        self.fail("P1", "write_before_offer", "talk %s writes the main stage %r before the offer page "
                                  "was ever shown (from %s)" % (shown, val, "fresh" if f == fresh else "a later state"))
                    if not chosen or not tagged:
                        self.fail("P1", "write_without_starter", "talk %s (options %s) writes the main stage %r with "
                                  "chosen=%s tagged=%s" % (shown, opts, val, chosen, tagged))
                if w["notyet"] and not w["chosen"]:
                    first_choice = next((p for p in shown if isinstance(pages[p].get("input"), dict)), None)
                    # the first choice the next talk offers is the offer again (a write before it is P1's
                    # write_before_offer; a write after it is the player's own choice on the offer)
                    if first_choice != offer:
                        self.fail("P3", "not_yet_returns", "after 'Not yet' the next talk shows %s (first choice %r), "
                                  "not the offer" % (shown, first_choice))
                if tag in w["tags"] and offer in shown:
                    self.fail("P3", "tagged_sees_offer", "a player carrying %s is shown the offer: %s" % (tag, shown))
            p = pick(w)
            if p is not None:
                out.append((freeze(p), "pick", [], [], []))
            graph[f] = out
            for g, *_ in out:
                if g not in seen:
                    seen.add(g)
                    todo.append(g)
        # P3: a tagged player at every cursor value Oak's dialogue can hold, plus unset, never sees the offer or its lead-in
        cursor_keys = set()
        for d in (thaw(s)["data"] for s in seen):
            cursor_keys |= {k for k, v in d.items() if isinstance(v, str) and v in pages}
        for ck in sorted(cursor_keys):
            for cur in list(pages) + [None]:
                w = thaw(base(True, (tag,), ck if cur else None, cur))
                for end, shown, writes, opts in talk(w):
                    hit = [p for p in shown if p in (lead_in or [offer])]
                    if hit:
                        self.fail("P3", "tagged_sees_offer", "a player carrying %s with %s=%r is shown %s"
                                  % (tag, ck, cur, hit))
        # P3: a "Not yet" from the fresh path was exercised
        if not any(thaw(s)["notyet"] for s in seen):
            self.fail("P3", "no_not_yet", "the offer has no option that closes it without the screen ('Not yet')")
        # P6: from every state where the player has chosen, the send-off is reachable
        good = {f for f, outs in graph.items() if any(wr for _, _, _, wr, _ in outs)}
        changed = True
        while changed:
            changed = False
            for f, outs in graph.items():
                if f not in good and any(g in good for g, *_ in outs):
                    good.add(f)
                    changed = True
        stuck = [f for f in graph if f[4] and f not in good and not any(
            True for (k, v) in f[0] if k == self.stage_key)]
        if stuck:
            self.fail("P6", "chosen_cannot_reach_sendoff", "%d explored states where the player has chosen and no "
                      "talk reaches the send-off, e.g. data=%r tags=%r" % (len(stuck), dict(stuck[0][0]),
                                                                            sorted(stuck[0][1])))
        if model.unknown:
            self.fail("P1", "unmodelled_command", "Oak's dialogue runs commands this model does not interpret: %s"
                      % sorted(set(model.unknown))[:4])
        tagless = [(v, None) for f, outs in graph.items() for _, _, _, wr, _ in outs
                   for (v, chosen, tagged, _) in wr if not tagged]
        self.notes.append("P1/P3/P6 Oak: %d states explored from a fresh and a legacy player; offer page %s, lead-in %s; "
                          "%d screen openings" % (len(seen), offer, lead_in, model.screens))
        return tagless

    # ------------------------------------------------------------------ P5
    def before_oak(self, starter_level):
        quests = read_json(self.data_dir / "quests.json")["quests"]
        stage_field = "quest.%s.stage" % self.stage_key.split("__")[2]
        reports, by_reason = [], {}
        for q in quests:
            if q["id"].startswith("main_"):
                continue
            text = json.dumps(q)
            gated = stage_field in json.dumps([t["conditions"] for t in q.get("transitions") or []]) or \
                "starter_chosen" in text or q.get("progression_gate")
            if gated:
                continue
            why = []
            if q.get("kind") == "trainer_record":
                why.append("a trainer battle")
            if "encounter" in q:
                why.append("a wild encounter")
            if any(k in q for k in ("lopunny_check", "levels")) or any(
                    c.get("kind") == "player_tag" for t in q.get("transitions") or [] for c in t["conditions"]):
                why.append("a party check")
            for w in why:
                by_reason.setdefault(w, []).append(q["id"])
        for w, ids in sorted(by_reason.items()):
            reports.append("%d quest(s) with no stage or starter gate assume a party (%s): %s"
                           % (len(ids), w, ", ".join(ids)))
        prog = read_json(self.data_dir / "progression.json")
        flags = {f["id"]: f for f in prog.get("flags") or []}
        for ch in prog.get("chapters") or []:
            if not ch.get("unlocked_by"):
                for fid in ch.get("unlocks") or []:
                    if (flags.get(fid) or {}).get("set_by", {}).get("kind") == "trainer_defeat":
                        reports.append("chapter %s is open from the start and its flag %s needs a won battle"
                                       % (ch["id"], fid))
        rewards = read_json(self.data_dir / "rewards.json")["rewards"]
        poke_items = re.compile(r"(potion|revive|berry|candy|_stone|everstone|leftovers|band|bell|milk|scroll)")
        n = sum(1 for r in rewards if any(poke_items.search(c.get("item", "")) for c in r.get("contents") or []))
        reports.append("rewards: %d of %d carry Pokemon-use items; none gives a Pokemon (P2 sweeps the functions); "
                       "harmless without a party" % (n, len(rewards)))
        cap = None
        if self.rct.exists():
            m = re.search(r"^\s*initialLevelCap\s*=\s*(\d+)", self.rct.read_text(encoding="utf-8"), re.M)
            cap = int(m.group(1)) if m else None
        if cap is None:
            self.fail("P5", "no_initial_cap", "%s has no initialLevelCap" % self.rct)
        elif starter_level is not None and cap < starter_level:
            self.fail("P5", "cap_below_starter", "RCT initialLevelCap %d is below the starters' level %d"
                      % (cap, starter_level))
        else:
            reports.append("RCT initialLevelCap %s >= the starters' level %s" % (cap, starter_level))
        self.reports += reports

    # ------------------------------------------------------------------ run
    def run(self):
        self.stage_key, self.stage_initial = self.stage_field()
        starter_level = self.check_config()
        if not self.dialogue_dir.exists():
            self.fail("P1", "no_dialogue", "no compiled dialogue at %s (run compile_dialogue.py --all)"
                      % self.dialogue_dir)
            self.before_oak(starter_level)
            return
        screens = self.sweep()
        dlgs = dialogues_in(self.dialogue_dir)
        npcs = npc_classes_in(self.dialogue_dir)
        total = sum(n for _, n in screens)
        oak_ids = {(c.get("interaction") or {}).get("dialogue") for _, c in npcs
                   if any(NPC_NAME.search(n or "") for n in c.get("names") or [])}
        if total != 1:
            self.fail("P2", "screen_count", "%d openstarterscreen occurrences (want exactly 1): %s"
                      % (total, [(str(f), n) for f, n in screens]))
        oak = None
        for did, (f, dlg) in dlgs.items():
            if any(f.resolve() == Path(str(s)).resolve() for s, _ in screens):
                if did not in oak_ids:
                    self.fail("P2", "screen_not_oak:%s" % did, "%s runs openstarterscreen and no NPC class named Oak "
                              "opens it (Oak opens %s)" % (did, sorted(x for x in oak_ids if x)))
                else:
                    oak = (did, dlg, f)
        if oak is None:
            self.fail("P2", "no_oak_screen", "no dialogue opened by an NPC named Oak runs openstarterscreen")
            self.before_oak(starter_level)
            return
        did, dlg, oak_file = oak
        # the tag the offer's action reads after the command is the starter tag: found in the output, not assumed
        offer_actions = [o.get("action") or "" for p in dlg["pages"] if isinstance(p.get("input"), dict)
                         for o in p["input"].get("options") or [] if SCREEN in (o.get("action") or "")]
        tags = set(re.findall(r"has_tag\('([^']+)'\)", offer_actions[0])) if offer_actions else set()
        tag = sorted(tags)[0] if len(tags) == 1 else None
        if tag is None:
            self.fail("P1", "starter_tag", "the offer's action reads %r, not exactly one tag" % sorted(tags))
            self.before_oak(starter_level)
            return
        callbacks = [t for f, t in text_files(self.dialogue_dir)
                     if "starter_chosen" in Path(str(f)).parts and str(f).endswith(".molang")]
        if not callbacks:
            self.notes.append("no starter_chosen callback in the dialogue pack: a pick is tagged only by Oak's 0 result")
        oak_tagless = self.explore(dlg, tag, callbacks)
        self.global_stage(oak_file, tag, oak_tagless)
        self.before_oak(starter_level)


def report(a, partial):
    known = [p for p in a.problems if (p[0], p[1]) in KNOWN]
    new = [p for p in a.problems if (p[0], p[1]) not in KNOWN]
    fixed = sorted(set(KNOWN) - {(p[0], p[1]) for p in known})
    for n in a.notes:
        print("NOTE    %s" % n)
    for r in a.reports:
        print("REPORT  %s" % r)
    for o in OPEN:
        print("OPEN    %s" % o)
    for c, k, msg in known:
        print("KNOWN   %-3s %s" % (c, msg))
    for c, k, msg in new:
        print("PROBLEM %-3s %s" % (c, msg))
    for k in fixed:
        print("FIXED?  a KNOWN entry no longer found (remove it from KNOWN): %s" % (k,))
    bad = bool(new or fixed)
    print("oak_starter_audit: %s -- %d problem(s), %d known%s" % ("FAIL" if bad else "ok", len(new), len(known),
                                                                 "; PARTIAL: " + partial if partial else ""))
    return 1 if bad else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--packs", default=str(PACKS))
    p.add_argument("--dialogue", default=None, help="the compiled dialogue pack (default <packs>/cobblers_dialogue)")
    p.add_argument("--config", default=str(CONFIG))
    p.add_argument("--data", default=str(ROOT / "data"))
    p.add_argument("--rct", default=str(RCT))
    p.add_argument("--compile", action="store_true", help="compile the dialogue into a temp dir first and audit that")
    a = p.parse_args(argv)
    packs = Path(a.packs)
    partial = ""
    tmp = None
    if a.compile:
        tmp = tempfile.TemporaryDirectory()
        dlg = Path(tmp.name) / "cobblers_dialogue"
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "compile_dialogue.py"), "--all", "--out", str(dlg),
                            "--data", a.data], capture_output=True, text=True)
        if r.returncode != 0:
            print("oak_starter_audit: FAIL -- compile_dialogue.py exited %d: %s" % (r.returncode, r.stderr[-400:]))
            return 1
    else:
        dlg = Path(a.dialogue) if a.dialogue else packs / "cobblers_dialogue"
    if not packs.exists():
        partial = "%s absent: the P2/P4 sweep covered only the compiled dialogue" % packs
    try:
        audit = Audit(dlg, packs, a.config, a.data, a.rct, extra_starter_roots=[ROOT / "modpack"])
        audit.run()
        return report(audit, partial)
    finally:
        if tmp is not None:
            tmp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
