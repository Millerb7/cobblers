"""Independent audit of the paid training services (unit SERVICES, 2026-10-10; built in 9282306 by another agent).

How this is independent of the builder: the pack is built by the generator's own CLI into a temporary folder, and
every .mcfunction and dialogue JSON is then READ FROM DISK and executed by the small command model below, written
for this audit from the command semantics in docs/research/notes/paid-services-and-npc-payouts.md A1/A2 (and
Minecraft 1.21.1's execute/return/macro rules). Nothing is imported from tools/training_services.py or from the
builder's tests; the expectations come from data/training_services.json and the model's own player state. The
mutation tests change the GENERATOR's source text (data untouched) and show the checks go red.

The model's assumptions, each of which is a game question and not proven here (EXP-062):
  - a function runs to completion on the server thread, so two players' clicks never interleave mid-function;
  - a command that throws (an empty slot) fails, and `execute store result` then stores 0;
  - `execute store result ... run function F` stores nothing when F does not `return`;
  - `cobbledollars remove` takes exactly its amount or nothing; `query` returns the balance;
  - `pokemoneditother` applies EV entries one by one, each refused silently past 510 (note A1, ASSUMED there).

What this does NOT cover: whether any of those commands behaves so in the running game; moves and evolutions a
level set skips; the dialogue client delivering a click twice (modelled as two calls in one tick).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "tools" / "training_services.py"
DOC = json.loads((ROOT / "data" / "training_services.json").read_text(encoding="utf-8"))
GROUNDS = json.loads((ROOT / "data" / "training_grounds.json").read_text(encoding="utf-8"))
NS = "cobblers:training_services/"
STATS = ("hp", "attack", "defence", "special_attack", "special_defence", "speed")
RAISE = DOC["services"]["raise"]["price"]
EV = DOC["services"]["ev"]["price"]
IV1 = DOC["services"]["iv"]["price_per_stat"]
MAX_CAP = DOC["services"]["raise"]["max_cap"]


# ----------------------------------------------------------------------------------------------- reading the pack
def read_pack(out):
    out = Path(out)
    fns = {}
    for f in out.glob("data/cobblers/function/**/*.mcfunction"):
        rel = f.relative_to(out / "data" / "cobblers" / "function").with_suffix("").as_posix()
        fns["cobblers:" + rel] = f.read_text(encoding="utf-8").splitlines()
    dialogues = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in out.glob("data/cobblers/dialogues/*.json")}
    npcs = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in out.glob("data/cobblers/npcs/*.json")}
    return {"fns": fns, "dialogues": dialogues, "npcs": npcs}


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("ts_pack")
    r = subprocess.run([sys.executable, str(GEN), "build", "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return read_pack(out)


def build_mutant(out, replacements):
    """Build the pack from a text-mutated copy of the generator (data/ untouched)."""
    src = GEN.read_text(encoding="utf-8")
    for old, new in replacements:
        assert src.count(old) == 1, "mutation anchor not found exactly once: %r" % old
        src = src.replace(old, new)
    g = {"__name__": "training_services_mutant", "__file__": str(GEN)}
    exec(compile(src, str(GEN), "exec"), g)  # noqa: S102 - the mutant generator, run as the real one would be
    g["write"](g["build"](g["load"]()), out)
    return read_pack(out)


# ----------------------------------------------------------------------------------------------- the command model
class Fail(Exception):
    pass


class Return(Exception):
    def __init__(self, value):
        self.value = value


class Player:
    def __init__(self, name, balance=0, cap=30, party=None, flags=()):
        self.name, self.balance, self.cap = name, balance, cap
        self.party = list(party or [None] * 6)
        self.flags = set(flags)
        self.msgs = []


def mon(level, evs=None, ivs=None):
    return {"level": level, "evs": dict(evs or {}), "ivs": dict(ivs or {})}


def snbt(s):
    s = s.strip()
    if s.startswith("{"):
        parts, cur, q = [], "", False
        for ch in s[1:-1]:
            if ch == '"':
                q = not q
            if ch == "," and not q:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        if cur.strip():
            parts.append(cur)
        out = {}
        for p in parts:
            k, _, v = p.partition(":")
            out[k.strip()] = snbt(v)
        return out
    if s.startswith('"'):
        return s[1:-1]
    return int(s)


class Game:
    def __init__(self, pack, remove="ok", give="ok", edit="ok", cap_read="ok", drain_after_remove=0):
        self.fns = pack["fns"]
        self.scores, self.storage, self.time = {}, {}, 1000
        self.remove, self.give, self.edit, self.cap_read = remove, give, edit, cap_read
        self.drain = drain_after_remove
        self.calls = []
        self.run("cobblers:training_services/load", None, None)

    # scores
    def holder(self, h, p):
        return p.name if h == "@s" else h

    def get(self, h, o, p):
        return self.scores.get((self.holder(h, p), o))

    def put(self, h, o, p, v):
        self.scores[(self.holder(h, p), o)] = int(v)

    # storage
    def sget(self, sid, path):
        cur = self.storage.get(sid, {})
        for k in path.split("."):
            if not isinstance(cur, dict) or k not in cur:
                raise Fail("storage %s %s missing" % (sid, path))
            cur = cur[k]
        return cur

    def sset(self, sid, path, v):
        cur = self.storage.setdefault(sid, {})
        ks = path.split(".")
        for k in ks[:-1]:
            cur = cur.setdefault(k, {})
        cur[ks[-1]] = v

    # functions
    def run(self, fid, args, p):
        """Returns the function's return value, or None when it did not return."""
        if fid not in self.fns:
            raise Fail("unknown function %s" % fid)
        self.calls.append(fid)
        lines = []
        for line in self.fns[fid]:
            if not line.strip() or line.startswith("#"):
                continue
            if line.startswith("$"):
                if args is None:
                    raise Fail("macro function %s called without arguments" % fid)
                def sub(m):
                    if m.group(1) not in args:
                        raise Fail("macro %s: no key %s" % (fid, m.group(1)))
                    return str(args[m.group(1)])
                line = re.sub(r"\$\(([a-z_]+)\)", sub, line[1:])
            lines.append(line)
        for line in lines:
            try:
                self.cmd(line, p)
            except Return as r:
                return r.value
            except Fail:
                continue
        return None

    def party_mon(self, p, slot):
        slot = int(slot)
        if not 1 <= slot <= 6:
            raise Fail("slot out of range")
        m = p.party[slot - 1]
        if m is None:
            raise Fail("empty slot")
        return m

    def props(self, s):
        out = []
        for kv in s.split():
            k, _, v = kv.partition("=")
            out.append((k, int(v)))
        return out

    def cmd(self, line, p):
        t = line.split(" ")
        head = t[0]
        if head == "scoreboard":
            if t[1] == "objectives":
                return 1
            op = t[2]
            if op == "set":
                self.put(t[3], t[4], p, int(t[5]))
                return int(t[5])
            if op in ("add", "remove"):
                v = (self.get(t[3], t[4], p) or 0) + (int(t[5]) if op == "add" else -int(t[5]))
                self.put(t[3], t[4], p, v)
                return v
            if op == "get":
                v = self.get(t[3], t[4], p)
                if v is None:
                    raise Fail("unset")
                return v
            if op == "operation":
                a, o = (t[3], t[4]), t[5]
                b = self.get(t[6], t[7], p) or 0
                cur = self.get(*a, p) or 0
                v = {"=": b, "+=": cur + b, "-=": cur - b}[o]
                self.put(*a, p, v)
                return v
            raise AssertionError("model does not know: %s" % line)
        if head == "time" and t[1:] == ["query", "gametime"]:
            return self.time
        if head == "return":
            if t[1] == "run":
                try:
                    v = self.cmd(" ".join(t[2:]), p)
                except Fail:
                    v = 0
                raise Return(v)
            raise Return(int(t[1]))
        if head == "execute":
            return self.execute(t, p)
        if head == "function":
            args = None
            if len(t) > 2:
                assert t[2:4] == ["with", "storage"], line
                args = self.sget(t[4], t[5])
            return self.run(t[1], args, p)
        if head == "data" and t[1:3] == ["modify", "storage"] and t[5:7] == ["set", "value"]:
            self.sset(t[3], t[4], snbt(" ".join(t[7:])))
            return 1
        if head == "tellraw":
            assert t[1] == "@s"
            j = json.loads(" ".join(t[2:]))
            parts = j if isinstance(j, list) else [j]
            txt = ""
            for c in parts:
                if "score" in c:
                    txt += str(self.get(c["score"]["name"], c["score"]["objective"], p))
                else:
                    txt += c.get("text", "")
            p.msgs.append(txt)
            return 1
        if head == "cobbledollars":
            assert t[2] == "@s", line
            if t[1] == "query":
                return p.balance
            n = int(t[3])
            if t[1] == "remove":
                if self.remove != "ok" or p.balance < n:
                    raise Fail("remove refused")
                p.balance -= n + self.drain
                return 1
            if t[1] == "give":
                if self.give != "ok":
                    raise Fail("give refused")
                p.balance += n
                return 1
        if head == "rctmod" and t[1:4] == ["player", "get", "level_cap"] and t[4] == "@s":
            if self.cap_read != "ok":
                raise Fail("cap unread")
            return p.cap
        if head == "testpartyslot":
            assert t[1] == "@s"
            m = self.party_mon(p, t[2])
            for k, v in self.props(" ".join(t[3:])):
                if k not in ("level", "lvl", "l"):
                    raise AssertionError("model does not know testpartyslot %s" % k)
                if m["level"] != v:
                    return 0
            return 1
        if head == "pokemoneditother":
            assert t[1] == "@s"
            m = self.party_mon(p, t[2])
            props = self.props(" ".join(t[3:]))
            for k, _ in props:
                base = re.sub(r"_(ev|iv)$", "", k)
                if k not in ("level", "lvl", "l") and (base not in STATS or base == k):
                    raise Fail("unknown property %s" % k)   # a parse failure: nothing is applied
            if self.edit == "fail":
                raise Fail("edit refused")
            if self.edit == "noop":
                return 1
            for k, v in props:
                if k in ("level", "lvl", "l"):
                    m["level"] = max(1, min(100, v))
                elif k.endswith("_iv"):
                    m["ivs"][k[:-3]] = max(0, min(31, v))
                else:
                    s, v = k[:-3], max(0, min(252, v))
                    if sum(m["evs"].values()) - m["evs"].get(s, 0) + v <= 510:
                        m["evs"][s] = v
            return 1
        raise AssertionError("model does not know: %s" % line)

    def execute(self, t, p):
        stores, i, inner = [], 1, None
        while i < len(t):
            w = t[i]
            if w == "run":
                inner = " ".join(t[i + 1:])
                break
            if w == "store":
                assert t[i + 1] == "result", t
                if t[i + 2] == "score":
                    stores.append(("score", t[i + 3], t[i + 4]))
                    i += 5
                else:
                    stores.append(("storage", t[i + 3], t[i + 4]))
                    i += 7
            elif w in ("if", "unless"):
                if t[i + 1] == "score":
                    a = self.get(t[i + 2], t[i + 3], p)
                    if t[i + 4] == "matches":
                        r = t[i + 5]
                        if ".." in r:
                            lo, hi = r.split("..")
                            ok = a is not None and (lo == "" or a >= int(lo)) and (hi == "" or a <= int(hi))
                        else:
                            ok = a is not None and a == int(r)
                        i += 6
                    else:
                        b = self.get(t[i + 5], t[i + 6], p)
                        ok = a is not None and b is not None and {
                            "=": a == b, ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[t[i + 4]]
                        i += 7
                elif t[i + 1] == "entity":
                    m = re.fullmatch(r"@s\[advancements=\{cobblers:flag/([a-z0-9_]+)=true\}\]", t[i + 2])
                    assert m, t
                    ok = m.group(1) in p.flags
                    i += 3
                else:
                    raise AssertionError("model does not know execute %s" % t[i + 1])
                if w == "unless":
                    ok = not ok
                if not ok:
                    raise Fail("condition")
            else:
                raise AssertionError("model does not know execute %s" % w)
        try:
            v = self.cmd(inner, p)
        except Fail:
            v = 0
        if v is None:      # a function that did not return: nothing is stored
            return None
        for s in stores:
            if s[0] == "score":
                self.put(s[1], s[2], p, v)
            else:
                self.sset(s[1], s[2], int(v))
        return v


# ------------------------------------------------------------------------------------------------ dialogue harness
def option_fn(pack, keeper, page, text):
    d = pack["dialogues"]["dlg_training_keeper_%s" % keeper]
    pg = next(x for x in d["pages"] if x["id"] == page)
    opt = next(o for o in pg["input"]["options"] if o["text"] == text)
    m = re.search(r"run function ([a-z0-9_:/]+)'", opt["action"])
    assert m, opt["action"]
    return m.group(1)


def click(game, pack, p, page, slot, keeper="gym1"):
    game.run(option_fn(pack, keeper, page, "Slot %d" % slot), None, p)


# ------------------------------------------------------------------------------------------------- the checks
def check_raise_sets_exactly_the_cap(pack):
    out = []
    for cap in (20, 25, 40, 61, MAX_CAP):
        for slot in (1, 4, 6):
            p = Player("A", balance=1200, cap=cap)
            p.party[slot - 1] = mon(5)
            g = Game(pack)
            click(g, pack, p, "raise", slot)
            got = p.party[slot - 1]["level"]
            if got != cap or p.balance != 1200 - RAISE:
                out.append("cap %d slot %d: level %d balance %d" % (cap, slot, got, p.balance))
    return out


def check_raise_never_leaves_a_slot_over_the_cap(pack):
    """Sweep: charged iff raised; a raised slot lands exactly on the cap; nothing else moves."""
    out = []
    for cap in (1, 2, 19, 20, 30, 61, 62, 63, 64, 99, 100):
        for lv in sorted({1, max(1, cap - 1), cap, min(100, cap + 1), 100}):
            p = Player("A", balance=10000, cap=cap, party=[mon(lv), mon(7), None, None, None, None])
            g = Game(pack)
            click(g, pack, p, "raise", 1)
            got, paid = p.party[0]["level"], 10000 - p.balance
            should = lv < cap <= MAX_CAP
            if should and (got != cap or paid != RAISE):
                out.append("cap %d lv %d: should raise, got %d paid %d" % (cap, lv, got, paid))
            if not should and (got != lv or paid != 0):
                out.append("cap %d lv %d: should refuse, got %d paid %d" % (cap, lv, got, paid))
            if p.party[1]["level"] != 7:
                out.append("cap %d lv %d: another slot moved" % (cap, lv))
            if got > max(lv, cap):
                out.append("cap %d lv %d: left at %d, over the cap" % (cap, lv, got))
    return out


def check_raise_refusals_charge_nothing(pack):
    out = []
    cases = {
        "cap unread": (dict(cap_read="fail"), Player("A", 5000, 30, [mon(5)] + [None] * 5)),
        "cap zero": ({}, Player("A", 5000, 0, [mon(5)] + [None] * 5)),
        "post-Champion cap 100": ({}, Player("A", 5000, 100, [mon(5)] + [None] * 5)),
        "cap 63": ({}, Player("A", 5000, 63, [mon(5)] + [None] * 5)),
        "empty slot": ({}, Player("A", 5000, 30)),
        "at cap": ({}, Player("A", 5000, 30, [mon(30)] + [None] * 5)),
        "above cap": ({}, Player("A", 5000, 30, [mon(45)] + [None] * 5)),
        "one dollar short": ({}, Player("A", RAISE - 1, 30, [mon(5)] + [None] * 5)),
    }
    for why, (kw, p) in cases.items():
        before = (p.balance, [m and dict(m) for m in p.party])
        g = Game(pack, **kw)
        click(g, pack, p, "raise", 1)
        if (p.balance, [m and dict(m) for m in p.party]) != before:
            out.append("%s: state changed" % why)
        if not p.msgs or "Nothing was charged" not in p.msgs[-1]:
            out.append("%s: the player is not told nothing was charged: %s" % (why, p.msgs))
        if g.get("A", "cob_ts_cd", p) is not None:
            out.append("%s: a refusal before the charge set the cooldown" % why)
    return out


def check_raise_charge_must_take_exactly_the_price(pack):
    """A charge that took nothing, or took more than the price, must not be followed by the edit."""
    out = []
    for kw in (dict(remove="fail"), dict(drain_after_remove=1)):
        p = Player("A", 5000, 30, [mon(5)] + [None] * 5)
        Game_ = Game(pack, **kw)
        click(Game_, pack, p, "raise", 1)
        if p.party[0]["level"] != 5:
            out.append("%s: edited after a charge that was not exactly the price" % kw)
    return out


def check_raise_edit_that_does_not_take_is_refunded_once(pack):
    out = []
    for edit in ("fail", "noop"):
        p = Player("A", 5000, 30, [mon(5)] + [None] * 5)
        g = Game(pack, edit=edit)
        click(g, pack, p, "raise", 1)
        if p.balance != 5000:
            out.append("edit %s: balance %d, not refunded to 5000 exactly" % (edit, p.balance))
    return out


def check_double_click_buys_once(pack):
    out = []
    for page, price, flags in (("raise", RAISE, ()), ("ev_physical_sweeper", EV, ("gym2_cleared",)),
                               ("iv_all", 6 * IV1, ("gym8_cleared",))):
        p = Player("A", 50000, 30, [mon(5)] + [None] * 5, flags)
        g = Game(pack)
        click(g, pack, p, page, 1)
        click(g, pack, p, page, 1)
        if p.balance != 50000 - price:
            out.append("%s: two clicks in one tick paid %d" % (page, 50000 - p.balance))
        g.time += DOC["cooldown_ticks"]
        if page == "raise":
            p.party[0]["level"] = 5
        click(g, pack, p, page, 1)
        if p.balance != 50000 - 2 * price:
            out.append("%s: a click after the cooldown was not served" % page)
    return out


def check_players_do_not_share_a_purchase(pack):
    """Two players in one tick, and a stale request in storage from an earlier purchase."""
    out = []
    g = Game(pack)
    g.storage["cobblers:training_services"] = {"req": {"slot": 6, "cap": 100, "x": ""}, "charge": {"amount": 1}}
    a = Player("A", 5000, 40, [mon(5), mon(6)] + [None] * 4)
    b = Player("B", 5000, 25, [mon(3), mon(4)] + [None] * 4)
    click(g, pack, a, "raise", 2)
    click(g, pack, b, "raise", 1)
    if (a.party[1]["level"], a.party[0]["level"], a.balance) != (40, 5, 5000 - RAISE):
        out.append("A: %s balance %d" % (a.party, a.balance))
    if (b.party[0]["level"], b.party[1]["level"], b.balance) != (25, 4, 5000 - RAISE):
        out.append("B: %s balance %d" % (b.party, b.balance))
    return out


def check_ev_spread_replaces_the_old_one(pack):
    out = []
    for sp in DOC["services"]["ev"]["spreads"]:
        p = Player("A", 5000, 30, [mon(20, evs={"hp": 252, "defence": 252, "speed": 6})] + [None] * 5,
                   ("gym2_cleared",))
        g = Game(pack)
        click(g, pack, p, "ev_%s" % sp["id"], 1)
        want = {s: sp["evs"].get(s, 0) for s in STATS}
        got = {s: p.party[0]["evs"].get(s, 0) for s in STATS}
        if got != want or p.balance != 5000 - EV:
            out.append("%s: evs %s balance %d" % (sp["id"], got, p.balance))
    return out


def check_iv_sets_only_what_was_bought(pack):
    out = []
    for oid, stats, price in [(s, (s,), IV1) for s in STATS] + [("all", STATS, 6 * IV1)]:
        p = Player("A", 9000, 30, [mon(20, ivs={s: 3 for s in STATS})] + [None] * 5, ("gym8_cleared",))
        g = Game(pack)
        click(g, pack, p, "iv_%s" % oid, 1)
        want = {s: (DOC["services"]["iv"]["value"] if s in stats else 3) for s in STATS}
        if p.party[0]["ivs"] != want or p.balance != 9000 - price:
            out.append("%s: ivs %s balance %d" % (oid, p.party[0]["ivs"], p.balance))
    return out


def check_ev_iv_gates_and_refusals_charge_nothing(pack):
    out = []
    for page, flags in (("ev_bulky_special", ()), ("ev_bulky_special", ("gym8_cleared",)),
                        ("iv_speed", ("gym2_cleared",)), ("iv_all", ())):
        p = Player("A", 50000, 30, [mon(20)] + [None] * 5, flags)
        g = Game(pack)
        click(g, pack, p, page, 1)
        if p.balance != 50000 or p.party[0] != mon(20):
            out.append("%s without its badge (%s): charged or edited" % (page, flags))
    for page, flag in (("ev_bulky_special", "gym2_cleared"), ("iv_speed", "gym8_cleared")):
        for p in (Player("A", 50000, 30, None, (flag,)), Player("A", 10, 30, [mon(20)] + [None] * 5, (flag,))):
            g = Game(pack)
            click(g, pack, p, page, 1)
            if p.balance not in (50000, 10):
                out.append("%s empty or short: charged" % page)
    return out


def check_every_option_maps_to_its_slot(pack):
    """All eight keepers: Slot N runs a function that writes slot N and nothing else differs between keepers."""
    out = []
    for keeper in ["gym%d" % n for n in range(1, 9)]:
        d = pack["dialogues"]["dlg_training_keeper_%s" % keeper]
        for pg in d["pages"]:
            for o in pg["input"]["options"]:
                m = re.fullmatch(r"Slot (\d)", o["text"])
                if not m:
                    continue
                fid = option_fn(pack, keeper, pg["id"], o["text"])
                body = "\n".join(pack["fns"].get(fid, []))
                if "{slot:%s," % m.group(1) not in body:
                    out.append("%s %s %s -> %s does not write slot %s" % (keeper, pg["id"], o["text"], fid, m.group(1)))
    return out


ALL_CHECKS = [check_raise_sets_exactly_the_cap, check_raise_never_leaves_a_slot_over_the_cap,
              check_raise_refusals_charge_nothing, check_raise_charge_must_take_exactly_the_price,
              check_raise_edit_that_does_not_take_is_refunded_once, check_double_click_buys_once,
              check_players_do_not_share_a_purchase, check_ev_spread_replaces_the_old_one,
              check_iv_sets_only_what_was_bought, check_ev_iv_gates_and_refusals_charge_nothing,
              check_every_option_maps_to_its_slot]


# ------------------------------------------------------------------------------------------------- the tests
# Removing this lets a raise write a level other than the read cap (over the cap locks the player out of trainers).
def test_a_raise_lands_exactly_on_the_read_cap_and_charges_the_price(pack):
    assert check_raise_sets_exactly_the_cap(pack) == []


# Removing this lets some cap/level combination raise a slot over the cap, charge without raising, or raise free.
def test_no_cap_and_level_combination_leaves_a_slot_over_the_cap_or_charges_for_nothing(pack):
    assert check_raise_never_leaves_a_slot_over_the_cap(pack) == []


# Removing this lets a refused raise (cap unread, cap past 62, empty/at/above cap, short) take money or edit.
def test_every_raise_refusal_leaves_money_and_party_untouched(pack):
    assert check_raise_refusals_charge_nothing(pack) == []


# Removing this lets the edit follow a charge that took nothing (free training) or the wrong amount.
def test_the_edit_follows_only_a_charge_of_exactly_the_price(pack):
    assert check_raise_charge_must_take_exactly_the_price(pack) == []


# Removing this lets a raise that did not take keep the player's money, or refund it twice.
def test_a_raise_that_does_not_take_is_refunded_exactly_once(pack):
    assert check_raise_edit_that_does_not_take_is_refunded_once(pack) == []


# Removing this lets a doubled dialogue submit buy twice, or a cooldown that never ends block later purchases.
def test_two_clicks_in_one_tick_buy_once_and_the_cooldown_ends(pack):
    assert check_double_click_buys_once(pack) == []


# Removing this lets one player's purchase or a stale request in the shared storage edit another slot or level.
def test_global_storage_does_not_leak_between_players_or_purchases(pack):
    assert check_players_do_not_share_a_purchase(pack) == []


# Removing this lets an EV spread keep part of the old one (the 510 rule) or charge the wrong price.
def test_an_ev_spread_replaces_whatever_was_there(pack):
    assert check_ev_spread_replaces_the_old_one(pack) == []


# Removing this lets an IV purchase change a stat that was not bought or charge the wrong price.
def test_an_iv_purchase_sets_only_the_stats_bought(pack):
    assert check_iv_sets_only_what_was_bought(pack) == []


# Removing this lets a player without the badge, with an empty slot or short of money be charged for EV/IV.
def test_ev_and_iv_refusals_charge_nothing(pack):
    assert check_ev_iv_gates_and_refusals_charge_nothing(pack) == []


# Removing this lets "Slot 3" in some keeper's dialogue edit a different slot.
def test_every_slot_option_of_every_keeper_edits_that_slot(pack):
    assert check_every_option_maps_to_its_slot(pack) == []


# DEFECT (recorded, not fixed): the EV and IV runs charge, then edit without reading the edit back, then print
# "Done" unconditionally. An edit that fails after the charge keeps the player's money and tells them it worked.
# strict: when the generator gains a read-back and refund, this xfail turns into a failure, and the marker goes.
@pytest.mark.xfail(strict=True, reason="tools/training_services.py:241-248 stat_run: no read-back, no refund")
@pytest.mark.parametrize("page,flag,price", [("ev_physical_sweeper", "gym2_cleared", EV),
                                             ("iv_all", "gym8_cleared", 6 * IV1)])
def test_an_ev_or_iv_edit_that_does_not_take_keeps_the_players_money(pack, page, flag, price):
    p = Player("A", 50000, 30, [mon(20)] + [None] * 5, (flag,))
    click(Game(pack, edit="fail"), pack, p, page, 1)
    assert p.balance == 50000 and not any(m.startswith("Done") for m in p.msgs)


# Removing this lets a menu page strand the player (no way back or out), or the entry depend on a cursor a relog
# or another keeper left behind.
def test_no_keeper_menu_can_strand_the_player(pack):
    for did, d in pack["dialogues"].items():
        assert "menu_cursor" not in d["initializationAction"], did
        assert "v.cobblers_entry = 'hub'" in d["initializationAction"], did
        pages = {pg["id"]: pg for pg in d["pages"]}
        edges = {}
        for pid, pg in pages.items():
            opts = pg["input"]["options"]
            assert opts, (did, pid)
            edges[pid] = set()
            for o in opts:
                a = o["action"]
                targets = re.findall(r"set_page\('([a-z0-9_]+)'\)", a)
                assert targets or "q.dialogue.close()" in a, (did, pid, o["text"])
                if "run function" in a:
                    assert a.rstrip().endswith("q.dialogue.close();"), (did, pid, o["text"])
                for x in targets:
                    assert x in pages, (did, pid, x)
                    edges[pid].add(x)
        # every page reaches the hub (back) and the hub reaches every page
        for start in pages:
            seen, todo = {start}, [start]
            while todo:
                for n in edges[todo.pop()]:
                    if n not in seen:
                        seen.add(n)
                        todo.append(n)
            assert "hub" in seen or start == "hub", (did, start)
            if start == "hub":
                assert seen == set(pages), (did, set(pages) - seen)


# Removing this lets a keeper be pushed, killed or despawned off its seat, or stand on the sign or the block.
def test_each_keeper_is_fixed_and_stands_beside_its_sign_not_on_it():
    sign = GROUNDS["sign"]["offset"]
    gs = {g["id"]: g for g in GROUNDS["grounds"]}
    assert sorted(k["ground"] for k in DOC["keepers"]) == sorted(gs)
    for k in DOC["keepers"]:
        s = gs[k["ground"]]["site"]
        x, _, z = k["at"]
        sx, sz = s["x"] + sign[0], s["z"] + sign[1]
        assert (x, z) not in ((s["x"], s["z"]), (sx, sz)), k["ground"]
        assert max(abs(x - sx), abs(z - sz)) <= 3, k["ground"]


def test_each_keeper_npc_is_invulnerable_and_immovable(pack):
    assert len(pack["npcs"]) == 8
    for nid, n in pack["npcs"].items():
        assert n["canDespawn"] is False and n["isInvulnerable"] is True and n["isMovable"] is False, nid
        assert n["interaction"]["dialogue"] == "cobblers:" + nid.replace("npc_", "dlg_"), nid


# Removing this lets a keeper stand inside the ground or float: y must be the canonical ground, rounded, plus one.
def test_each_keeper_stands_on_the_heightmap_ground():
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as G
    try:
        g = G.load()
    except (FileNotFoundError, OSError, SystemExit) as e:
        pytest.skip("no heightmap here: %s" % e)
    for k in DOC["keepers"]:
        x, y, z = k["at"]
        assert y == g(x, z) + 1, (k["ground"], y, g(x, z))


# ------------------------------------------------------------------------------------------------- mutations
MUTATIONS = {
    "the raise writes level=100": (
        [('"$pokemoneditother @s $(slot) level=$(cap)",', '"$pokemoneditother @s $(slot) level=100",')],
        check_raise_sets_exactly_the_cap),
    "the after-charge check never fires": (
        [('"execute unless score #after %s = #want %s run return run tellraw @s %s"',
          '"execute if score #after %s = #nobody %s run return run tellraw @s %s"')],
        check_raise_charge_must_take_exactly_the_price),
    "the refund is dropped": (
        [('"execute unless score #done %s matches 1 run function %s with storage %s charge" % (SCORE, fn_id("refund"), '
          'STORAGE),', '')],
        check_raise_edit_that_does_not_take_is_refunded_once),
    "the refund runs twice": (
        [('"execute unless score #done %s matches 1 run function %s with storage %s charge" % (SCORE, fn_id("refund"), '
          'STORAGE),', '"execute unless score #done %s matches 1 run function %s with storage %s charge" % (SCORE, '
          'fn_id("refund"), STORAGE),' * 2)],
        check_raise_edit_that_does_not_take_is_refunded_once),
    "the cooldown never fires": (
        [('"execute if score @s %s > #now %s run return 0"', '"execute if score @s %s > #never %s run return 0"')],
        check_double_click_buys_once),
    "the max_cap ceiling is dropped": (
        [('% (CAP, top + 1, text(m["cap_closed"]', '% (CAP, 100000, text(m["cap_closed"]')],
        check_raise_refusals_charge_nothing),
    "the above-cap refusal is dropped": (
        [('"execute if score #lv %s > @s %s run return run tellraw @s %s"',
          '"execute if score #lv %s > #nobody %s run return run tellraw @s %s"')],
        check_raise_never_leaves_a_slot_over_the_cap),
    "the EV zeroing is dropped": (
        [('" ".join("%s_ev=0" % s for s in STATS)', '"hp_ev=0"')],
        check_ev_spread_replaces_the_old_one),
    "the IV option writes every stat": (
        [('props=iv_props(stats, int(iv["value"]))', 'props=iv_props(STATS, int(iv["value"]))')],
        check_iv_sets_only_what_was_bought),
}


# Removing this loses the proof that the checks above bite on the generator rather than agreeing with it.
@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_mutated_generator_turns_its_check_red(name, tmp_path, pack):
    reps, check = MUTATIONS[name]
    mutant = build_mutant(tmp_path / "mutant", reps)
    assert check(pack) == [], "the check fails on the real pack too"
    assert check(mutant) != [], "%s: the check stayed green" % name
