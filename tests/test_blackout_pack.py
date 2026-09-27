"""tools/blackout_pack.py: the cobblers_blackout datapack (blackout, recovery claims, the water ladder).

Written by the test author, not by the session that wrote the tool (commits 562eeb6..5d522d7). Swim fatigue (the
pack's surface/* functions) is tested in tests/test_surface_exhaustion.py, on the simulator defined here;
tools/open_water.py, which the pack no longer reads (2262aa3), in tests/test_open_water.py.

Independent sources: data/blackout.json and data/water_mounts.json (the authored rules and numbers);
data/placements.json (every Center: kind "service", id ending "_pokecenter") and data/progression.json (every town
waystone); docs/mechanics/DEATH_AND_WIPE.md as the tool's docstring cites it (a claim is written before anything is
removed; claims resolve before the guardian is released; Master, Ancient Origin, Cherish and Park Balls and the Kubfu
scrolls are never lost); vanilla Minecraft 1.21.1 command semantics written into the small simulator below (scoreboard
arithmetic is 32-bit, `/=` floors, `<` is min; a `dx` volume selects an entity whose hitbox meets the block cuboid
[x, x + dx + 1); `data get ... Pos[0]` floors; the player hitbox is 0.6 wide; a player's offhand is Inventory slot -106);
and the in-game finding of 2026-09-26 (EXP-042, staging) that Cobblemon fires only callbacks under its own namespace.

The simulator runs the generated functions on a scoreboard and a command storage, expanding a macro call from the
storage or inline compound it names, with stubs for what only a server knows (the CobbleDollars balance, the game time,
health, block tests, a vehicle). It executes the generated text, so it tests the pack, not the Python that wrote it.

The claim ledger's storage is `cobblers_recovery:ledger` (its own namespace, so Minecraft saves it to
data/command_storage_cobblers_recovery.dat, which tools/carry_players.py carries; tests/test_carry_recovery_ledger.py);
its function paths stay `cobblers:recovery/...`.

What this does not cover, and needs a running server (EXP-042): that Cobblemon fires the callbacks and exposes the
MoLang fields they read; that `cobbledollars query` returns the balance; that the oxygen_bonus modifier holds air; that
the Respiration override loads and neutralises existing books and helmets; that `item modify ... set_count add` takes
the planned amount from the right slot; that a rebuilt guardian keeps its data; that macro lines parse on the server.
"""
from __future__ import annotations

import copy
import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import blackout_pack as BP  # noqa: E402


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


CFG = _load("blackout.json")
MOUNTS = _load("water_mounts.json")
PLACEMENTS = _load("placements.json")
PROGRESSION = _load("progression.json")
NS = "cobblers"
LEDGER = "cobblers_recovery:ledger"          # the claim ledger's storage (the coordinator, 2026-09-27)
FN_DIR = "data/%s/function/" % NS


def build(cfg=None, mounts=None, placements=None, progression=None):
    return BP.build(copy.deepcopy(cfg or CFG), copy.deepcopy(mounts or MOUNTS),
                    copy.deepcopy(placements or PLACEMENTS), copy.deepcopy(progression or PROGRESSION))


PACK = build()


def functions(pack):
    """{"blackout/charge": [lines]} for every generated .mcfunction."""
    return {k[len(FN_DIR):-len(".mcfunction")]: v.splitlines() for k, v in pack.items()
            if k.startswith(FN_DIR) and k.endswith(".mcfunction")}


FNS = functions(PACK)


def commands(name):
    """The non-comment, non-blank lines of one generated function."""
    return [l for l in FNS[name] if l.strip() and not l.lstrip().startswith("#")]


# ------------------------------------------------------------------------------------------------ a small simulator

RETURN = object()


def wrap32(v):
    return ((int(v) + 2 ** 31) % 2 ** 32) - 2 ** 31


def in_range(v, r):
    if ".." not in r:
        return v == int(r)
    lo, hi = r.split("..")
    return (lo == "" or v >= int(lo)) and (hi == "" or v <= int(hi))


def inline_args(text):
    """{key: value} of a flat SNBT compound such as {id:3,slot:"container.0"}; values keep their literal text."""
    body = text.strip()
    assert body.startswith("{") and body.endswith("}"), text
    out = {}
    for part in re.findall(r'(\w+):("[^"]*"|[^,}]*)', body[1:-1]):
        out[part[0]] = part[1][1:-1] if part[1].startswith('"') else part[1]
    return out


class Sim:
    """Runs generated functions against one player (@s) and fake players (#name).

    query(cmd) answers `store result` commands only a server can (a balance, the game time, health, a position);
    cond(kind, toks) answers `if block|entity|data|items|loaded` tests and `on <relation>` (false: no such entity, so
    the rest of the chain has no executor and neither runs nor stores). Every function call is recorded; a generated
    function is executed, a macro one with its arguments substituted from the named storage or inline compound, as
    Minecraft does. A call to a function the pack does not have is recorded in `missing` (Minecraft: an error)."""

    def __init__(self, fns=None, query=None, cond=None):
        self.fns = fns or FNS
        self.score, self.storage, self.calls, self.log, self.missing = {}, {}, [], [], []
        self.query = query or (lambda cmd: 0)
        self.cond = cond or (lambda kind, toks: False)

    def get(self, h, o):
        return self.score.get((h, o), 0)

    def set(self, h, o, v):
        self.score[(h, o)] = wrap32(v)

    def call(self, name, args=None):
        for line in self.fns[name]:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("$"):
                assert args is not None, "macro function %s called without arguments" % name
                for k in MACRO_REF.findall(line):
                    assert k in args, "macro %s needs $(%s), not in %s" % (name, k, sorted(args))
                line = MACRO_REF.sub(lambda m: str(args[m.group(1)]), line[1:])
            if self.command(line) is RETURN:
                return

    def args_from(self, rest):
        if rest.startswith("with storage "):
            _, _, ns, path = rest.split(" ", 3)
            return {p[len(path) + 1:]: v for (n, p), v in self.storage.items() if n == ns and p.startswith(path + ".")}
        return inline_args(rest)

    def command(self, cmd):
        t = cmd.split(" ")
        if t[0] == "execute":
            return self.execute(t[1:])
        if t[0] == "return":
            if t[1] == "run":
                self.command(" ".join(t[2:]))
            return RETURN
        if t[0] == "scoreboard" and t[1] == "players":
            self.players(t[2:])
            return None
        if t[0] == "function":
            name = t[1].split(":", 1)[1]
            rest = " ".join(t[2:])
            self.calls.append((name, rest, dict(self.storage)))
            if name not in self.fns:
                self.missing.append(t[1])
            elif any(l.startswith("$") for l in self.fns[name]):
                self.call(name, self.args_from(rest))
            else:
                self.call(name)
            return None
        self.log.append(cmd)
        return None

    def value(self, cmd):
        t = cmd.split(" ")
        if t[:3] == ["scoreboard", "players", "get"]:
            return self.get(t[3], t[4])
        return self.query(cmd)

    def store(self, st, v):
        if st[1] == "score":
            self.set(st[2], st[3], v if st[0] == "result" else int(bool(v)))
        else:
            self.storage[(st[2], st[3])] = int(v * float(st[5]))

    def execute(self, t):
        ok, st, i = True, None, 0
        while i < len(t):
            w = t[i]
            if w in ("if", "unless"):
                kind = t[i + 1]
                if kind == "score":
                    # vanilla: a score that is not set fails every test on it, `matches` and comparisons alike
                    a = self.get(t[i + 2], t[i + 3])
                    known = (t[i + 2], t[i + 3]) in self.score
                    if t[i + 4] == "matches":
                        res, n = known and in_range(a, t[i + 5]), 6
                    else:
                        b = self.get(t[i + 5], t[i + 6])
                        known = known and (t[i + 5], t[i + 6]) in self.score
                        res = known and {"<": a < b, "<=": a <= b, "=": a == b, ">": a > b, ">=": a >= b}[t[i + 4]]
                        n = 7
                else:
                    n = {"entity": 3, "block": 6, "loaded": 5,
                         "data": 5 if t[i + 2] in ("storage", "entity") else 7,
                         "items": 6 if t[i + 2] == "entity" else 8}[kind]
                    res = self.cond(kind, t[i + 2:i + n])
                ok = ok and (res if w == "if" else not res)
                i += n
            elif w == "store":
                if t[i + 2] == "score":
                    st, i = (t[i + 1], "score", t[i + 3], t[i + 4]), i + 5
                else:
                    st, i = (t[i + 1], "storage", t[i + 3], t[i + 4], t[i + 5], t[i + 6]), i + 7
            elif w in ("as", "at", "anchored", "in"):
                i += 2
            elif w == "on":
                if ok and not self.cond("on", [t[i + 1]]):
                    return None                      # no such entity: the chain has no executor left
                i += 2
            elif w == "positioned":
                i += 3 if t[i + 1] == "as" else 4
            elif w == "run":
                if not ok:
                    return None
                rest = " ".join(t[i + 1:])
                if st:
                    self.store(st, self.value(rest))
                    return None
                return self.command(rest)
            else:
                raise AssertionError("simulator: unknown execute token %r in %r" % (w, " ".join(t)))
        if st:
            self.store(st, 1 if ok else 0)
        return None

    def players(self, t):
        op = t[0]
        if op == "set":
            self.set(t[1], t[2], int(t[3]))
        elif op == "add":
            self.set(t[1], t[2], self.get(t[1], t[2]) + int(t[3]))
        elif op == "remove":
            self.set(t[1], t[2], self.get(t[1], t[2]) - int(t[3]))
        elif op == "reset":
            self.score.pop((t[1], t[2]), None)
        elif op == "operation":
            h, o, oper, h2, o2 = t[1:6]
            a, b = self.get(h, o), self.get(h2, o2)
            r = {"=": lambda: b, "+=": lambda: a + b, "-=": lambda: a - b, "*=": lambda: a * b,
                 "/=": lambda: a // b if b else a, "%=": lambda: a % b if b else a,
                 "<": lambda: min(a, b), ">": lambda: max(a, b)}[oper]()
            self.set(h, o, r)
        elif op == "get":
            pass
        else:
            raise AssertionError("simulator: scoreboard players %s" % op)


def load_functions(pack=None):
    """The functions minecraft:load runs, in order, from the pack's own load tag."""
    tag = json.loads((pack or PACK)["data/minecraft/tags/function/load.json"])
    return [v.split(":", 1)[1] for v in tag["values"]]


def loaded_sim(**kw):
    """A simulator after every function in the load tag has run (every constant set)."""
    s = Sim(**kw)
    for f in load_functions():
        s.call(f)
    return s


# Without it the tests below could pass on a simulator that ignores what it is given: it must refuse a command it does
# not know, floor-divide, take `<` as min, wrap at 32 bits, and stop a function at `return`.
def test_the_simulator_follows_minecraft_arithmetic_and_refuses_what_it_does_not_know():
    s = Sim(fns={"t/a": ["scoreboard players set #a x -7", "scoreboard players set #b x 2",
                         "scoreboard players operation #a x /= #b x", "scoreboard players set #c x 5",
                         "scoreboard players operation #c x < #b x", "scoreboard players set #d x 2147483647",
                         "scoreboard players add #d x 1", "execute if score #c x matches 2 run return 0",
                         "scoreboard players set #e x 1"]})
    s.call("t/a")
    assert (s.get("#a", "x"), s.get("#c", "x"), s.get("#d", "x"), s.get("#e", "x")) == (-4, 2, -2 ** 31, 0)
    with pytest.raises(AssertionError):
        Sim(fns={"t/b": ["execute facing 0 0 0 run say hi"]}).call("t/b")
    # a macro call substitutes from its inline compound or its storage, and refuses a missing key
    m = Sim(fns={"t/m": ["$scoreboard players set #m x $(v)"],
                 "t/c": ["function cobblers:t/m {v:7}", "execute store result storage a:b s.v int 1 run scoreboard "
                         "players get #m x", "scoreboard players add #m x 1", "function cobblers:t/m with storage a:b s",
                         "function cobblers:t/none"]})
    m.call("t/c")
    assert m.get("#m", "x") == 7 and m.missing == ["cobblers:t/none"], (m.score, m.missing)
    with pytest.raises(AssertionError):
        Sim(fns={"t/m": ["$say $(v)"], "t/c": ["function cobblers:t/m {w:1}"]}).call("t/c")
    # `on vehicle` with no vehicle ends the chain: nothing runs and nothing is stored
    v = Sim(fns={"t/v": ["scoreboard players set #r x 5", "execute store success score #r x on vehicle if entity @s"]})
    v.call("t/v")
    assert v.get("#r", "x") == 5
    # an unset score fails `if score` (so `unless` passes), whatever the range
    u = Sim(fns={"t/u": ["execute unless score @s y matches -2147483648.. run scoreboard players set #u x 1",
                         "execute if score @s y matches ..0 run scoreboard players set #v x 1"]})
    u.call("t/u")
    assert (u.get("#u", "x"), ("#v", "x") in u.score) == (1, False)


# ------------------------------------------------------------------------------------------------ pack basics

# Without it a pack_format change ships a pack Minecraft 1.21.1 lists as incompatible (48 is 1.21.1's data format).
def test_pack_format_is_48():
    assert json.loads(PACK["pack.mcmeta"])["pack"]["pack_format"] == 48


# Without it the pack overrides a vanilla file by accident: the only minecraft-namespace files are the deliberate
# Respiration override and the load/tick function tags, which merge (no replace:true) rather than replace, and which
# name exactly the pack's own entry points (blackout/load and surface/load; blackout/tick).
def test_the_only_upstream_paths_are_the_respiration_override_and_merging_function_tags():
    upstream = sorted(k for k in PACK if k.startswith("data/minecraft/"))
    assert upstream == ["data/minecraft/enchantment/respiration.json", "data/minecraft/tags/function/load.json",
                        "data/minecraft/tags/function/tick.json"], upstream
    want = {"load": ["%s:blackout/load" % NS, "%s:surface/load" % NS], "tick": ["%s:blackout/tick" % NS]}
    for k, values in want.items():
        tag = json.loads(PACK["data/minecraft/tags/function/%s.json" % k])
        assert not tag.get("replace"), tag
        assert tag["values"] == values, tag
    assert not [k for k in PACK if k.startswith("data/") and k.split("/")[1] not in (NS, "minecraft", "cobblemon")]


# any namespace, so a call into the wrong one (cobblers_recovery:ledger/..., a storage id used as a function path) is
# seen; a path runs to whitespace, a quote or the end, and may hold a macro reference
CALL = re.compile(r"function ([a-z0-9_.-]+):((?:[a-z0-9_/.-]|\$\([a-z_]+\))*)")


def _call_rest(line, end):
    """The argument part after a function name: 'with storage ns path' or an inline compound, else ''."""
    tail = line[end:]
    m = re.match(r" with (?:storage|entity|block) \S+ \S+", tail)
    if m:
        return m.group(0).strip()
    if tail.startswith(" {"):
        return tail[1:tail.index("}") + 1]
    return ""


def _references(pack=None):
    """[(where, namespace, called path, the rest of the call)] across functions, callbacks, advancements and tags.
    The rest is None where the call is not a function command (a tag, an advancement reward, MoLang)."""
    pack = pack or PACK
    out = []
    for k, v in pack.items():
        if k.endswith(".mcfunction"):
            where = k[len(FN_DIR):-len(".mcfunction")]
            for l in v.splitlines():
                if l.startswith("#"):
                    continue
                for m in CALL.finditer(l):
                    out.append((where, m.group(1), m.group(2), _call_rest(l, m.end())))
        elif k.endswith(".molang"):
            for m in CALL.finditer(v):
                out.append((k, m.group(1), m.group(2), None))
        elif k.endswith(".json") and ("/tags/function/" in k or "/advancement/" in k):
            doc = json.loads(v)
            for n in list(doc.get("values") or []) + [(doc.get("rewards") or {}).get("function")]:
                if n:
                    ns, path = n.split(":", 1)
                    out.append((k, ns, path, None))
    return out


# The macro-built function names the pack may call, and what each may resolve to. A new one fails the test below until
# it is described here. There are none since 2262aa3 (the sea-row lookup surface/r/$(z) went with the distance bands).
MACRO_NAMES = {}


# Without it a renamed or misspelt function fails at runtime (an unknown function in a datapack function stops the
# whole file from loading; a callback's run_command reports an error), or a call names the wrong namespace: moving the
# ledger's storage to cobblers_recovery:ledger once sent every claim call to cobblers_recovery:ledger/..., functions
# that do not exist (the coordinator's own slip, fixed in 5d522d7).
def test_every_function_the_pack_names_is_a_function_it_generates():
    refs = _references()
    assert len(refs) >= 80, len(refs)
    wrong_ns = sorted({(w, ns, f) for w, ns, f, _ in refs if ns != NS})
    assert not wrong_ns, wrong_ns
    missing = []
    for w, _, f, _ in refs:
        if "$(" in f:
            assert f in MACRO_NAMES, "an undescribed macro-built function name: %s in %s" % (f, w)
            if not any(MACRO_NAMES[f].fullmatch(n) for n in FNS):
                missing.append((w, f))
        elif f == "blackout/battle_loss_" and w.endswith(".molang"):
            continue                 # the battle_victory callback's name ends in a MoLang concatenation, see below
        elif f not in FNS:
            missing.append((w, f))
    assert not missing, missing
    # the battle_victory callback builds the name from t.kind: every kind it can assign must be a generated function
    mol = PACK["data/cobblemon/callbacks/battle_victory/cobblers_blackout.molang"]
    kinds = set(re.findall(r"t\.kind = '([a-z]+)'", mol))
    assert kinds == {"other", "wild", "npc"}, kinds
    assert "blackout/battle_loss_' + t.kind" in mol
    assert all("blackout/battle_loss_%s" % k in FNS for k in kinds), kinds


# Without it the check above goes blind to the slip it exists for: a call into the ledger's storage namespace, rebuilt
# here by hand on a copy of the pack, must be reported.
def test_the_reference_check_sees_a_call_into_the_ledger_namespace():
    bad = dict(PACK)
    k = FN_DIR + "recovery/commit.mcfunction"
    bad[k] = bad[k].replace("function %s:recovery/apply\n" % NS, "function %s/apply\n" % LEDGER)
    assert bad[k] != PACK[k]
    assert ("recovery/commit", "cobblers_recovery", "ledger/apply") in [(w, ns, f) for w, ns, f, _ in _references(bad)]


# ------------------------------------------------------------------------------------------------ macros

MACRO_REF = re.compile(r"\$\(([a-z_]+)\)")


def _macro_functions():
    return {n for n, lines in FNS.items() if any(l.startswith("$") for l in lines)}


# Without it a macro line without a $( reference, or a plain line that carries one, is a function that fails to load
# (a `$` line needs a macro reference) or sends a literal "$(x)" to the command parser.
def test_macro_lines_and_only_macro_lines_carry_macro_references():
    bad = [(n, l) for n, lines in FNS.items() for l in lines
           if (l.startswith("$") and "$(" not in l) or (l[:1] not in "$#" and "$(" in l)]
    assert not bad, bad[:5]


# Without it a macro function is called bare, which Minecraft rejects at run time ("macro function called without
# arguments"), and an inline compound that lacks a key the macro uses fails the same way.
def test_every_macro_function_is_called_with_arguments_that_cover_its_keys():
    macros = _macro_functions()
    assert len(macros) >= 20, sorted(macros)
    keys = {n: set(MACRO_REF.findall("\n".join(l for l in FNS[n] if l.startswith("$")))) for n in macros}
    calls = [(w, f, rest) for w, _, f, rest in _references() if f in macros and rest is not None]
    assert calls, "no calls found: the reference scan is broken"
    bad = []
    for where, f, rest in calls:
        if rest.startswith("with "):
            continue
        if not rest.startswith("{"):
            bad.append((where, f, "called without arguments"))
            continue
        given = set(re.findall(r"([a-z_]+):", rest.split("}")[0] + "}"))
        if not keys[f] <= given:
            bad.append((where, f, "missing %s" % sorted(keys[f] - given)))
    assert not bad, bad
    # the callbacks call two macro functions from MoLang with an inline compound built in the string (written there as
    # {victor:"' + ... + '",name:"...); its keys must cover the macros' keys too
    victory = PACK["data/cobblemon/callbacks/battle_victory/cobblers_blackout.molang"]
    captured = PACK["data/cobblemon/callbacks/pokemon_captured/cobblers_recovery.molang"]

    def inline(text, fn):
        return set(re.findall(r'[{,](\w+):"', text.split(fn, 1)[1].split("');", 1)[0]))

    assert keys["blackout/battle_loss_wild"] <= inline(victory, "blackout/battle_loss_' + t.kind + '"), \
        inline(victory, "blackout/battle_loss_' + t.kind + '")
    assert keys["recovery/defeated"] == {"resolver"}
    assert keys["recovery/defeated"] <= inline(victory, "recovery/defeated")
    assert keys["recovery/defeated"] <= inline(captured, "recovery/defeated")


# ------------------------------------------------------------------------------------------------ objectives

OBJ = re.compile(r"(?<![\w.])(bo\.[a-z]+)\b")


# Without it a function reads or writes an objective nobody created: every command on it fails, silently, every tick.
def test_every_objective_used_is_created_in_load():
    created = {l.split()[3] for l in FNS["blackout/load"] if l.startswith("scoreboard objectives add ")}
    used = set()
    for k, v in PACK.items():
        if k.endswith((".mcfunction", ".molang")):
            used |= set(OBJ.findall(v))
    assert len(used) >= 30, sorted(used)
    assert used <= created, sorted(used - created)


# Without it a constant read from bo.cfg that load never sets reads as 0: a division by a zero constant does nothing
# and a `< #max` cap takes everything to zero. The constants are set by the functions the load tag runs (blackout/load
# and surface/load); one set twice to different values would depend on the tag's order.
def test_every_constant_read_from_bo_cfg_is_set_in_load_from_the_data():
    loads = load_functions()
    assert loads == ["blackout/load", "surface/load"], loads
    set_, twice = {}, []
    for f in loads:
        for l in FNS[f]:
            if l.startswith("scoreboard players set #") and " bo.cfg " in l:
                k, v = l.split()[3], int(l.split()[5])
                if k in set_ and set_[k] != v:
                    twice.append((k, set_[k], v))
                set_[k] = v
    assert not twice, twice
    read = set()
    for n, lines in FNS.items():
        if n in loads:
            continue
        for l in lines:
            read |= set(re.findall(r"(#[a-z0-9-]+) bo\.cfg", l))
    assert read <= set(set_), sorted(read - set(set_))
    s = CFG["surface"]
    per = s["sample_ticks"]
    assert (set_["#fgain1"], set_["#fgain2"], set_["#frec"]) == (
        s["gain_shallow_per_tick"] * per, s["gain_deep_per_tick"] * per, s["recover_per_tick"] * per)
    assert (set_["#fwarn"], set_["#fslow"], set_["#fexh"], set_["#fcol"], set_["#fpulse"], set_["#fcap"]) == (
        s["warn_ticks"], s["slow_ticks"], s["exhausted_ticks"], s["collapse_ticks"], s["pulse_ticks"], s["cap_ticks"])
    assert (set_["#2"], set_["#fsample"]) == (2, per)
    w, c = CFG["water"], CFG["claims"]
    assert (set_["#pct"], set_["#surf"], set_["#regen"], set_["#pulse"], set_["#grace"], set_["#dedupe"]) == (
        CFG["money"]["percent"], w["surf_bonus_ticks"], w["pulse_regen_margin"], w["pulse_ticks"],
        w["partner_grace_ticks"], CFG["dedupe_ticks"])
    assert (set_["#bpct"], set_["#bmax"], set_["#mpct"], set_["#mmax"], set_["#cchance"]) == (
        c["categories"]["balls"]["percent"], c["categories"]["balls"]["max"], c["categories"]["medicine"]["percent"],
        c["categories"]["medicine"]["max"], c["categories"]["consumables"]["chance_percent"])


# ------------------------------------------------------------------------------------------------ checkpoints

def _centers():
    return [q["id"] for q in PLACEMENTS["placements"] if q.get("kind") == "service" and q["id"].endswith("_pokecenter")]


def _waystones():
    return ["waystone_%s" % f["waystone"]["town"] for f in PROGRESSION.get("flags", []) if f.get("waystone")]


# The checkpoint ids as data/blackout.json had them at 1b9bbc1 (2026-09-26). A player's saved checkpoint is this
# number (ids_rule), so a key may be added but never renumbered, and a retired number never goes to a new key.
FROZEN_IDS = {
    "hometown_pokecenter": 1, "gym1_pokecenter": 2, "gym2_pokecenter": 3, "gym3_pokecenter": 4, "gym4_pokecenter": 5,
    "gym5_pokecenter": 6, "gym6_pokecenter": 7, "gym7_pokecenter": 8, "gym8_pokecenter": 9,
    "merian_hut_pokecenter": 10, "gorge_hamlet_pokecenter": 11, "tableland_stop_pokecenter": 12,
    "rift_rim_stop_pokecenter": 13, "northlight_pokecenter": 14, "mining_pokecenter": 15, "tea_pokecenter": 16,
    "sunset_pokecenter": 17, "sea_town_pokecenter": 18, "waystone_gym1_town": 101, "waystone_gym2_town": 102,
    "waystone_gym3_town": 103, "waystone_gym4_town": 104, "waystone_gym5_town": 105, "waystone_gym6_town": 106,
    "waystone_gym7_town": 107, "waystone_gym8_town": 108,
}


# Without it a new Center or town waystone has no checkpoint and the pack build stops (or, if the check were lost, a
# player who heals there is returned to Hometown).
def test_every_center_and_town_waystone_has_a_checkpoint_id():
    ids = CFG["checkpoints"]["ids"]
    centers, ways = _centers(), _waystones()
    assert len(centers) >= 18 and len(ways) >= 8, (len(centers), len(ways))
    missing = [k for k in centers + ways if k not in ids]
    assert not missing, missing


# Without it two checkpoints share a number (a player's saved point resolves to the wrong place), or an existing number
# is renumbered or reused and every player who saved it is silently moved.
def test_checkpoint_ids_are_unique_and_never_renumbered_or_reused():
    ids = CFG["checkpoints"]["ids"]
    nums = list(ids.values())
    assert len(nums) == len(set(nums)), sorted(n for n in nums if nums.count(n) > 1)
    assert all(isinstance(n, int) and n > 0 for n in nums), nums     # 0 is the pallet (to_pallet sets bo.cp 0)
    changed = {k: (v, ids.get(k)) for k, v in FROZEN_IDS.items() if k in ids and ids[k] != v}
    assert not changed, changed
    reused = {k: v for k, v in ids.items() if k not in FROZEN_IDS and v in set(FROZEN_IDS.values())}
    assert not reused, reused


# Without it a Center or waystone with no id is dropped from the pack in silence instead of stopping the build.
@pytest.mark.parametrize("drop", ["gym3_pokecenter", "waystone_gym8_town"])
def test_the_build_fails_loudly_when_a_checkpoint_id_is_missing(drop):
    cfg = copy.deepcopy(CFG)
    del cfg["checkpoints"]["ids"][drop]
    with pytest.raises(SystemExit, match=drop):
        build(cfg)


# Without it two checkpoints given one number build a pack whose validate accepts either place for both.
def test_the_build_fails_loudly_when_a_checkpoint_id_is_used_twice():
    cfg = copy.deepcopy(CFG)
    cfg["checkpoints"]["ids"]["waystone_gym1_town"] = cfg["checkpoints"]["ids"]["gym1_pokecenter"]
    with pytest.raises(SystemExit, match="used twice"):
        build(cfg)


def _anchors():
    """{id: (kind, x, z, radius)} from the data, not from the tool."""
    ids, out = CFG["checkpoints"]["ids"], {}
    for q in PLACEMENTS["placements"]:
        if q.get("kind") == "service" and q["id"].endswith("_pokecenter"):
            out[ids[q["id"]]] = ("center", q["position"]["x"], q["position"]["z"], CFG["checkpoints"]["center_radius"])
    for f in PROGRESSION.get("flags", []):
        if f.get("waystone"):
            x, _, z = f["waystone"]["position"]
            out[ids["waystone_%s" % f["waystone"]["town"]]] = ("waystone", x, z,
                                                               CFG["checkpoints"]["waystone_arrival_radius"])
    return out


def _validates(cid, x, z):
    s = Sim()
    s.set("@s", "bo.cp", cid)
    s.set("@s", "bo.cpx", x)
    s.set("@s", "bo.cpz", z)
    s.set("@s", "bo.ok", 7)
    s.call("blackout/checkpoint/validate")
    return s.get("@s", "bo.ok")


# Without it a checkpoint the data holds is not in validate (the player is sent to Hometown every time), a point far
# from its checkpoint validates (a stale save teleports the player somewhere the Center no longer is), or one
# checkpoint's number accepts another's place.
def test_validate_accepts_every_checkpoint_at_its_anchor_and_refuses_outside_its_radius():
    anchors = _anchors()
    covered = {int(m) for m in re.findall(r"bo\.cp matches (\d+) ", "\n".join(FNS["blackout/checkpoint/validate"]))}
    assert covered == set(anchors) == set(CFG["checkpoints"]["ids"].values()), sorted(covered ^ set(anchors))
    for cid, (kind, x, z, r) in anchors.items():
        assert _validates(cid, x, z) == 1, (cid, kind)
        far = 2 * r + 1        # beyond the radius and beyond the doubled waystone tolerance
        for dx, dz in ((far, 0), (-far, 0), (0, far), (0, -far)):
            assert _validates(cid, x + dx, z + dz) == 0, (cid, kind, dx, dz)
        other = next(o for o in anchors if o != cid)
        if math.dist((x, z), anchors[other][1:3]) > 4 * r:
            assert _validates(other, x, z) == 0, (cid, other)
    assert _validates(9999, *anchors[1][1:3]) == 0


def _selector_boxes(name):
    """[(id, x, dx, z, dz)] of the `@s[x=..,dx=..]` volumes a set-checkpoint function tests."""
    out = []
    for l in FNS[name]:
        m = re.search(r"@s\[x=(-?\d+),y=-?\d+,z=(-?\d+),dx=(\d+),dy=\d+,dz=(\d+)\].*\{id:(\d+)\}", l)
        if m:
            x, z, dx, dz, cid = map(int, m.groups())
            out.append((cid, x, dx, z, dz))
    return out


# Without it a player the healing-machine (or waystone-arrival) test accepts saves a point that validate then refuses,
# and their next blackout sends them to Hometown instead of the Center they just used. Vanilla: a `dx` volume selects
# an entity whose hitbox (0.6 wide for a player) meets the cuboid [x, x + dx + 1), and the saved point is
# `data get entity @s Pos[0]`, which floors; so a selected player's saved x runs from x - 1 to x + dx + 1.
# (Found by this suite at 1b9bbc1 for Centers; fixed in 5d522d7.)
@pytest.mark.parametrize("kind", ["center", "waystone"])
def test_a_point_the_set_test_accepts_always_revalidates(kind):
    fn = {"center": "blackout/checkpoint/healer_used", "waystone": "blackout/checkpoint/waystones"}[kind]
    boxes = _selector_boxes(fn)
    assert len(boxes) >= 8, boxes
    bad = []
    for cid, x, dx, z, dz in boxes:
        # the extreme feet positions whose 0.6-wide hitbox still meets the cuboid, and their floored saves
        for px in (x - 0.29, x + dx + 1 + 0.29):
            for pz in (z - 0.29, z + dz + 1 + 0.29):
                if _validates(cid, math.floor(px), math.floor(pz)) != 1:
                    bad.append((cid, math.floor(px), math.floor(pz)))
    assert not bad, bad[:4]


# ------------------------------------------------------------------------------------------------ the charge

def _charge(balance):
    s = loaded_sim(query=lambda cmd: balance if cmd.startswith("cobbledollars query") else 0)
    s.call("blackout/charge")
    applied = [c for c in s.calls if c[0] == "blackout/charge_apply"]
    return s.get("@s", "bo.lost"), applied


# Without it the charge rounds down (a balance of 1 to 9 loses nothing, against the spec) or up by a whole unit on an
# exact multiple, or the amount the macro removes differs from the amount the message reports.
def test_the_charge_is_the_ceiling_of_percent_of_the_balance_and_at_least_one():
    pct = CFG["money"]["percent"]
    for bal in list(range(0, 1001)) + [9_999, 10_000, 10_001, 123_457, 2_000_000, 99_999_999]:
        lost, applied = _charge(bal)
        assert lost == math.ceil(bal * pct / 100), (bal, lost)
        if bal > 0:
            assert lost >= 1, bal
            assert len(applied) == 1 and applied[0][1] == "with storage %s:blackout charge" % NS, applied
            assert applied[0][2][("%s:blackout" % NS, "charge.amount")] == lost, (bal, applied)
            assert s_log(bal) == ["cobbledollars remove @s %d" % lost], s_log(bal)
        else:
            assert applied == [], (bal, applied)
    assert FNS["blackout/charge_apply"] == ["$cobbledollars remove @s $(amount)"]


def s_log(balance):
    """The CobbleDollars commands one charge sends, the macro expanded."""
    s = loaded_sim(query=lambda cmd: balance if cmd.startswith("cobbledollars query") else 0)
    s.call("blackout/charge")
    return [l for l in s.log if l.startswith("cobbledollars ")]


# Without it a balance large enough to overflow `balance * percent` in a 32-bit score is charged a negative amount
# (and `cobbledollars remove @s -N` either fails or pays the player), at the data's percent or any other the owner may
# set. (Found by this suite at 1b9bbc1: 214,748,355 and up at 10%; fixed in 5d522d7.)
@pytest.mark.parametrize("pct", [CFG["money"]["percent"], 1, 7, 33, 100])
def test_the_charge_is_correct_for_every_balance_a_score_can_hold(pct):
    cfg = copy.deepcopy(CFG)
    cfg["money"]["percent"] = pct
    fns = functions(build(cfg))
    for bal in (1, 99, 100, 101, 12_345, 214_748_355, 214_748_364, 500_000_000, 2 ** 31 - 100, 2 ** 31 - 1):
        s = Sim(fns=fns, query=lambda cmd, b=bal: b if cmd.startswith("cobbledollars query") else 0)
        for f in load_functions():
            s.call(f)
        s.call("blackout/charge")
        want = -(-bal * pct // 100)
        assert s.get("@s", "bo.lost") == want, (pct, bal, s.get("@s", "bo.lost"))
        assert [l for l in s.log if l.startswith("cobbledollars ")] == ["cobbledollars remove @s %d" % want]


# Without it one defeat reported twice (the battle loss, then the death it causes) is charged twice.
def test_a_second_report_within_dedupe_ticks_is_dropped_and_a_later_one_is_not():
    now = {"t": 0}
    s = loaded_sim(query=lambda cmd: now["t"] if cmd == "time query gametime" else 0)
    d = CFG["dedupe_ticks"]
    out = []
    for t in (10_000, 10_000 + d - 1, 10_000 + d + 5):
        now["t"] = t
        s.call("blackout/dedupe")
        out.append(s.get("#dup", "bo.tmp"))
    assert out == [0, 1, 0], out
    # every path into the charge goes through the dedupe first and stops on a duplicate
    for n in ("blackout/death", "blackout/battle_loss_wild", "blackout/battle_loss_npc", "blackout/battle_loss_other"):
        c = commands(n)
        i = c.index("function %s:blackout/dedupe" % NS)
        assert c[i + 1] == "execute if score #dup bo.tmp matches 1 run return 0", (n, c)
        assert c.index("function %s:blackout/charge" % NS) > i + 1, n


# ------------------------------------------------------------------------------------------------ claims

FORBIDDEN = {"cobblemon:master_ball", "cobblemon:ancient_origin_ball", "cobblemon:cherish_ball", "cobblemon:park_ball",
             "cobblemon:scroll_of_darkness", "cobblemon:scroll_of_waters"}


def _tag(cat):
    return set(json.loads(PACK["data/%s/tags/item/claim/%s.json" % (NS, cat)])["values"])


# Without it one item sits in two categories (counted and taken under both quotas), or a unique or story item (a
# Master Ball, the Kubfu scrolls) can be lost to a wild Pokemon, against the spec.
def test_claim_categories_are_disjoint_and_never_hold_a_unique_or_story_item():
    tags = {c: _tag(c) for c in ("balls", "medicine", "consumables")}
    for c, v in tags.items():
        assert v == set(CFG["claims"][c]) and len(v) >= 10, c
        assert all(re.fullmatch(r"[a-z0-9_]+:[a-z0-9_/]+", i) for i in v), c
    assert not tags["balls"] & tags["medicine"] and not tags["balls"] & tags["consumables"] \
        and not tags["medicine"] & tags["consumables"]
    every = set().union(*tags.values())
    assert not every & FORBIDDEN, sorted(every & FORBIDDEN)
    assert not [i for i in every if "scroll" in i], [i for i in every if "scroll" in i]


SCAN = re.compile(r"if items entity @s (\S+) #%s:claim/(\w+) run function %s:recovery/(take|take_pick) "
                  r"\{slot:\"([^\"]+)\",nbt:(-?\d+)" % (NS, NS))


# Without it a claim reaches into armour (a worn item is never a supply), skips part of the hotbar or the offhand, or
# reads one slot's count from another (the Inventory NBT slot of container.N is N, of weapon.offhand -106).
def test_the_scan_covers_the_main_inventory_and_offhand_and_never_armour():
    want = {"container.%d" % i: i for i in range(36)}
    want["weapon.offhand"] = -106
    seen = {}
    for l in commands("recovery/scan"):
        m = SCAN.search(l)
        assert m, l
        slot, cat, _, slot2, nbt = m.groups()
        assert slot == slot2 and int(nbt) == want.get(slot, "no such slot"), l
        seen.setdefault(slot, set()).add(cat)
    assert set(seen) == set(want), sorted(set(seen) ^ set(want))
    assert all(v == {"balls", "medicine", "consumables"} for v in seen.values())
    pack_text = "\n".join(v for k, v in PACK.items() if k.endswith(".mcfunction"))
    assert "armor." not in pack_text and "Slot:100b" not in pack_text


# Without it the plan-then-take split breaks: a scan or take step that removes items directly takes before the claim
# is written; `clear` with a count other than 0 removes rather than counts.
def test_only_the_apply_step_changes_the_inventory_and_every_clear_only_counts():
    changers = sorted(n for n, lines in FNS.items() if any(re.search(r"\bitem (modify|replace) entity @s\b", l)
                                                           for l in lines))
    assert changers == ["recovery/apply_one"], changers
    clears = [l for lines in FNS.values() for l in lines if re.search(r"(^|run )clear @s\b", l)]
    assert clears and all(l.rstrip().endswith(" 0") for l in clears), clears
    callers = sorted({w for w, _, f, _ in _references() if f == "recovery/apply"})
    assert callers == ["recovery/apply", "recovery/commit"], callers


def _index(lines, pred, what):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    assert hits, "%s: not found" % what
    return hits[0]


# Without it items are removed before the claim that records them is written (a failure part-way loses them for good,
# spec: "the claim is written before anything is removed"), or the guardian is bound to a claim that never landed.
def test_the_claim_is_appended_and_checked_before_items_are_removed_or_the_guardian_bound():
    c = FNS["recovery/commit"]
    F = "%s:recovery" % NS                   # function paths
    assert BP.LEDGER == LEDGER
    append = _index(c, lambda l: l == "data modify storage %s claims append from storage %s pending" % (LEDGER, LEDGER),
                    "append")
    check = _index(c, lambda l: l == "execute store success score #ok bo.tmp run function %s/verify with storage %s "
                                     "pending" % (F, LEDGER), "verify")
    abort = _index(c, lambda l: l.startswith("$execute if score #ok bo.tmp matches 0 run return run "), "abort")
    apply_ = _index(c, lambda l: l == "function %s/apply" % F, "apply")
    bind = _index(c, lambda l: "run function %s/bind" % F in l, "bind")
    assert append < check < abort < apply_ < bind, (append, check, abort, apply_, bind)
    # the verify reads this claim by the id commit gave it, before the append
    pid = _index(c, lambda l: l.startswith("execute store result storage %s pending.id " % LEDGER), "pending.id")
    assert pid < append
    # nothing before the append touches the inventory or the victor's tags
    assert not [l for l in c[:append] if "apply" in l or "bind" in l or "item modify" in l]
    # and recovery/make hands over to commit only after the scan has planned into pending
    m = FNS["recovery/make"]
    assert _index(m, lambda l: l == "function %s/scan" % F, "scan") < \
        _index(m, lambda l: l.startswith("$function %s/commit " % F), "commit")


def _verify(has_items):
    """Run recovery/verify for claim 7 against a ledger whose claim 7 has items or not; (log, returned early)."""
    seen = []
    s = Sim(cond=lambda kind, toks: seen.append(toks) or (kind == "data" and has_items))
    s.command("function %s:recovery/verify {id:7}" % NS)
    return s.log, seen


# Without it an aborted commit leaves an item-less claim "open" in the ledger with no guardian bound: maintenance then
# finds no guardian for it and rebuilds one from the victor's snapshot, a second copy of a Pokemon that still exists
# (found by this suite at 1b9bbc1: clear counts armour, the crafting grid and the cursor, which the scan skips; fixed
# in 5d522d7). The check must read this claim by its own id, not claims[-1] (which an earlier claim also satisfies).
def test_an_aborted_commit_leaves_no_open_claim_in_the_ledger():
    log, seen = _verify(has_items=False)
    assert seen == [["storage", LEDGER, "claims[{id:7}].items[0]"]], seen
    assert log == ["data remove storage %s claims[{id:7}]" % LEDGER], log
    log, seen = _verify(has_items=True)
    assert log == [], "a claim with items must stay in the ledger"
    assert commands("recovery/verify")[-1] == "return fail", "the abort must report failure to commit's store success"
    assert not [l for l in PACK[FN_DIR + "recovery/commit.mcfunction"].splitlines() if "claims[-1].items" in l]


STORAGE = re.compile(r'storage ([a-z0-9_.-]+:[a-z0-9_/.-]+)|"storage":"([^"]+)"')


# Without it the claim ledger drifts back into the shared cobblers storage, which Minecraft saves with the re-apply's
# own progress (data/command_storage_cobblers.dat): either open claims are lost at a re-export (the file is not
# carried) or the re-apply's progress is carried with them. Every storage the recovery functions touch is the ledger,
# the ledger is created at load, and no other storage holds claims.
def test_the_claim_ledger_lives_in_its_own_storage_namespace():
    used = {}
    for k, v in PACK.items():
        if k.endswith((".mcfunction", ".molang")):
            for m in STORAGE.finditer(v):
                used.setdefault(m.group(1) or m.group(2), set()).add(k)
    assert set(used) == {LEDGER, "%s:blackout" % NS}, sorted(used)
    recovery = [k for k in used[LEDGER]]
    assert all(k.startswith(FN_DIR + "recovery/") or k == FN_DIR + "blackout/load.mcfunction" for k in recovery), \
        sorted(k for k in recovery if not k.startswith(FN_DIR + "recovery/"))
    assert not [k for k in used["%s:blackout" % NS] if k.startswith(FN_DIR + "recovery/")]
    load = "\n".join(FNS["blackout/load"])
    assert "execute unless data storage %s claims run data modify storage %s claims set value []" % (LEDGER, LEDGER) \
        in load
    for k, v in PACK.items():
        assert "cobblers:recovery claims" not in v and "cobblers:blackout claims" not in v, k


# Without it the guardian is untagged before its claims resolve (a failure part-way loses every claim it held), or a
# Pokemon with no guardian number resolves claims numbered 0.
def test_claims_resolve_before_the_guardian_is_released_and_a_numberless_guardian_is_refused():
    d = commands("recovery/defeated")
    R = "%s:recovery" % NS                   # function paths
    assert d[0] == "execute unless score @s bo.g matches 1.. run return fail", d[0]
    resolve = _index(d, lambda l: l == "function %s/resolve_next" % R, "resolve")
    for what in ("tag @s remove cobblers.guardian", "function %s/unbind_tag" % R, "scoreboard players reset @s bo.g",
                 "data merge entity @s {PersistenceRequired:0b}"):
        assert _index(d, lambda l: l.startswith(what), what) > resolve, what
    # and the refusal really stops the function in the simulator: nothing after it runs
    s = Sim(fns={"t": [l for l in d if not l.startswith("$")]})
    s.call("t")
    assert s.calls == [] and s.log == [], (s.calls, s.log)


# ------------------------------------------------------------------------------------------------ callbacks

# Without it a callback is written where Cobblemon registers it but never fires it (data/cobblers/callbacks/, found in
# game 2026-09-26): battle losses, captures and the water party read would all do nothing.
def test_molang_callbacks_live_under_cobblemons_own_namespace():
    mol = sorted(k for k in PACK if k.endswith(".molang"))
    assert len(mol) == 3, mol
    for k in mol:
        assert re.fullmatch(r"data/cobblemon/callbacks/[a-z_]+/cobblers_[a-z_]+\.molang", k), k
    assert {k.split("/")[3] for k in mol} == {"battle_victory", "player_tick_pre", "pokemon_captured"}
    assert not [k for k in PACK if "/callbacks/" in k and not k.startswith("data/cobblemon/callbacks/")]


WATER_MOL = "data/cobblemon/callbacks/player_tick_pre/cobblers_water_mounts.molang"


# Without it a species in data/water_mounts.json gives no water support in game, a Surf species is read as Dive, or a
# Dive species in a party that also holds a Surf species is downgraded to Surf.
def test_the_water_mounts_molang_names_every_species_with_dive_checked_first():
    lines = PACK[WATER_MOL].splitlines()
    dive_i = _index(lines, lambda l: "t.best = 2;" in l, "dive line")
    surf_i = _index(lines, lambda l: "t.best = 1;" in l, "surf line")
    assert dive_i < surf_i
    ids = lambda l: set(re.findall(r"'cobblemon:([a-z0-9_]+)'", l))
    assert ids(lines[dive_i]) == set(MOUNTS["dive"]), ids(lines[dive_i]) ^ set(MOUNTS["dive"])
    assert ids(lines[surf_i]) == set(MOUNTS["surf"]), ids(lines[surf_i]) ^ set(MOUNTS["surf"])
    assert "t.best < 1 &&" in lines[surf_i], "a Surf species must not lower a Dive result"
    assert "t.p.current_hp > 0" in PACK[WATER_MOL], "fainted Pokemon must not count"
    for n in (0, 1, 2):
        assert "t.best == %d ? { q.run_command('scoreboard players set ' + q.player.username + ' bo.mount %d'); };" \
            % (n, n) in lines


# ------------------------------------------------------------------------------------------------ the water ladder

# Without it depth is judged on a different column than the data's deep_blocks (a shallow river counts as deep, or a
# trench never does), or depth is tested from the feet rather than the eyes.
@pytest.mark.parametrize("deep", [CFG["water"]["deep_blocks"], 3])
def test_the_deep_test_checks_exactly_deep_blocks_above_the_eyes(deep):
    cfg = copy.deepcopy(CFG)
    cfg["water"]["deep_blocks"] = deep
    tick = functions(build(cfg))["water/tick"]
    line = next(l for l in tick if l.endswith("run scoreboard players set @s bo.deep 1"))
    assert line.startswith("execute if score @s bo.sub matches 1 anchored eyes positioned ^ ^ ^ "), line
    offsets = [int(o) for o in re.findall(r"if block ~ ~(\d+) ~ #%s:water" % NS, line)]
    assert offsets == list(range(1, deep + 1)), offsets
    sub = next(l for l in tick if l.endswith("run scoreboard players set @s bo.sub 1"))
    assert "anchored eyes positioned ^ ^ ^ if block ~ ~ ~ #%s:water" % NS in sub, sub


def _deep_ticks(qual_by_tick, surf=0):
    """Run water/deep once per tick at depth; the qual score per tick; returns (breathing ticks, final bo.surf)."""
    s = loaded_sim()
    s.set("@s", "bo.surf", surf)
    s.set("@s", "bo.air", 300)
    s.set("@s", "bo.hasmod", 1)
    breathing = []
    for tick, q in enumerate(qual_by_tick):
        s.set("@s", "bo.qual", q)
        s.calls.clear()
        s.call("water/deep")
        if any(c[0] == "water/breathing" for c in s.calls):
            breathing.append(tick)
        assert s.get("@s", "bo.surf") <= CFG["water"]["surf_bonus_ticks"], tick
    return breathing, s.get("@s", "bo.surf")


# Without it the Surf bonus outlasts surf_bonus_ticks (Surf becomes Dive) or is refilled while still underwater.
def test_the_surf_timer_caps_at_surf_bonus_ticks():
    n = CFG["water"]["surf_bonus_ticks"]
    breathing, surf = _deep_ticks([1] * (n + 200))
    assert surf == n
    assert breathing and breathing[-1] < n + 1 and all(t not in breathing for t in range(n, n + 200))
    assert breathing == list(range(len(breathing))), "the bonus is one continuous stretch"


# Without it the Surf bonus is off the data by a tick (found by this suite at 1b9bbc1: 899 for 900; fixed in 5d522d7).
def test_the_surf_bonus_lasts_exactly_surf_bonus_ticks():
    n = CFG["water"]["surf_bonus_ticks"]
    breathing, _ = _deep_ticks([1] * (n + 50))
    assert len(breathing) == n, len(breathing)


# Without it time under Dive is free and losing the Dive partner at depth hands out a fresh Surf timer
# (spec: "Entering, swapping and leaving depth").
def test_time_under_dive_counts_against_the_surf_bonus():
    n = CFG["water"]["surf_bonus_ticks"]
    dive = 300
    breathing, surf = _deep_ticks([2] * dive + [1] * n)
    assert all(t in breathing for t in range(dive)), "Dive breathes throughout"
    surf_ticks = [t for t in breathing if t >= dive]
    assert surf == n
    assert len(surf_ticks) == n - dive, len(surf_ticks)
    # and Dive is unlimited: past the Surf cap it still breathes
    breathing, _ = _deep_ticks([2] * (n + 100))
    assert len(breathing) == n + 100


def _pulse(max_health, health):
    s = loaded_sim(query=lambda cmd: {"attribute @s minecraft:generic.max_health get 1": max_health,
                                      "data get entity @s Health 1": health}[cmd])
    s.call("water/pulse")
    applied = [c for c in s.calls if c[0] == "water/pulse_apply"]
    assert len(applied) == 1 and applied[0][1] == "with storage %s:blackout pulse" % NS, applied
    return applied[0][2][("%s:blackout" % NS, "pulse.amount")]


# Without it a player regenerating between hits survives the second drowning hit (EXP-042 run 1: 20 to 10, regenerated
# to 11, the second hit left 2), or a player well above half health is killed by one hit.
def test_a_drowning_hit_is_half_max_health_and_lethal_within_the_regen_margin():
    m = CFG["water"]["pulse_regen_margin"]
    assert m >= 1
    assert _pulse(20, 20) == 10
    assert _pulse(20, 10 + m + 1) == 10
    assert _pulse(20, 10 + m) >= 1000
    assert _pulse(20, 11) >= 1000                                   # the EXP-042 case
    assert _pulse(40, 20 + m) >= 1000 and _pulse(40, 20 + m + 1) == 20
    assert FNS["water/pulse_apply"] == ["$damage @s $(amount) minecraft:drown"]


# Without it the ladder gives the Water Breathing effect, which strip_vanilla clears the same tick (the ladder does
# nothing), or the ladder's own air modifier is never removed and a player keeps it after surfacing.
def test_the_ladder_uses_oxygen_bonus_never_water_breathing_and_removes_its_modifier():
    text = "\n".join(l for lines in FNS.values() for l in lines if not l.startswith("#"))
    assert not re.search(r"effect give [^\n]*water_breathing", text)
    assert not re.search(r"effect give [^\n]*conduit_power", text)
    add = [l for l in FNS["water/breathing"] if "modifier add" in l]
    assert add == ["execute unless score @s bo.hasmod matches 1 run attribute @s minecraft:generic.oxygen_bonus "
                   "modifier add cobblers:ladder %d add_value" % CFG["water"]["ladder_oxygen_bonus"]], add
    assert "attribute @s minecraft:generic.oxygen_bonus modifier remove cobblers:ladder" in FNS["water/unbreathe"]
    tick = FNS["water/tick"]
    assert "execute if score @s bo.brth matches 0 if score @s bo.hasmod matches 1 run function %s:water/unbreathe" \
        % NS in tick


# Without it a potion, a turtle shell or a conduit routes round the whole ladder (the owner, 2026-09-26).
def test_the_strip_clears_water_breathing_and_conduit_power_every_tick():
    strip = "\n".join(FNS["water/strip_vanilla"])
    assert "effect clear @s minecraft:water_breathing" in strip
    assert "effect clear @s minecraft:conduit_power" in strip
    assert FNS["water/tick"][-1] == "function %s:water/strip_vanilla" % NS      # unconditional, every tick
    assert "function %s:water/tick" % NS in "\n".join(FNS["blackout/tick"])


# Without it Respiration keeps working (an enchanted helmet or book routes round the ladder), or the override points at
# a tag that does not exist and the enchantment fails to load.
def test_respiration_is_overridden_with_no_effects_and_nothing_it_applies_to():
    r = json.loads(PACK["data/minecraft/enchantment/respiration.json"])
    assert "effects" not in r, r.get("effects")
    assert r["supported_items"] == "#%s:enchantable/none" % NS
    assert "primary_items" not in r
    assert json.loads(PACK["data/%s/tags/item/enchantable/none.json" % NS]) == {"values": []}


# Without it the Dive swim boost is left on after the player leaves the water or loses Dive (one modifier never removed),
# or swim_off removes a modifier swim_on never added.
def test_the_dive_swim_boost_adds_and_removes_the_same_two_modifiers():
    add = {tuple(m) for m in re.findall(r"attribute @s (\S+) modifier add (\S+) ", "\n".join(FNS["water/swim_on"]))}
    rem = {tuple(m) for m in re.findall(r"attribute @s (\S+) modifier remove (\S+)", "\n".join(FNS["water/swim_off"]))}
    assert add == rem == {("minecraft:generic.water_movement_efficiency", "cobblers:dive_swim"),
                          ("minecraft:generic.movement_speed", "cobblers:dive_swim")}, (add, rem)
    assert FNS["water/swim_on"][-1] == "scoreboard players set @s bo.swim 1"
    assert FNS["water/swim_off"][-1] == "scoreboard players set @s bo.swim 0"
    others = [n for n, lines in FNS.items() if n not in ("water/swim_on", "water/swim_off")
              and any("cobblers:dive_swim" in l for l in lines)]
    assert not others, others
