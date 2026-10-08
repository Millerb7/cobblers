"""tools/training_services.py: the paid training services' generated pack, EXECUTED in a small command model.

The builder's own tests (the independent audit is a test author's job). Every purchase path is run against the
generated functions, not read as text: a player with a party, a balance, a cap and badges clicks a slot option, and
the model applies each command the pack emits. The model's Pokemon follow the bytecode facts relayed in
docs/research/notes/paid-services-and-npc-payouts.md A1-A2: testpartyslot matches level= by equality, pokemoneditother
on an empty slot fails, EVs.canSet refuses a set that would pass 510, IVs clamp 0..31.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import training_services as T  # noqa: E402

DOC = T.load()
FILES = T.build(DOC)
PREFIX = "data/cobblers/function/"
FNS = {p[len(PREFIX):-len(".mcfunction")]: ls for p, ls in FILES.items()
       if p.startswith(PREFIX) and p.endswith(".mcfunction")}
STATS = T.STATS


class Mon:
    def __init__(self, level, evs=None, ivs=None):
        self.level = level
        self.evs = dict.fromkeys(STATS, 0)
        self.evs.update(evs or {})
        self.ivs = dict.fromkeys(STATS, 0)
        self.ivs.update(ivs or {})


class Player:
    """One player and the server commands the pack uses."""

    def __init__(self, balance=10_000, cap=30, party=None, flags=(), remove_works=True, edit_works=True):
        self.balance, self.cap, self.flags = balance, cap, set(flags)
        self.party = party if party is not None else {1: Mon(12)}
        self.remove_works, self.edit_works = remove_works, edit_works
        self.scores, self.storage, self.time, self.log = {}, {}, 1000, []

    # ------------------------------------------------------------------ the model
    def call(self, name, args=None):
        lines = FNS[name]
        for raw in lines:
            if not raw or raw.startswith("#"):
                continue
            line = raw
            if raw.startswith("$"):
                line = re.sub(r"\$\((\w+)\)", lambda m: str(args[m.group(1)]), raw[1:])
            kind, val = self.run(line)
            if kind == "return":
                return val
        return 0

    def run(self, cmd):
        """('return', v) for a return, else ('ok', result) where result None is a failed command."""
        if cmd.startswith("return run "):
            return "return", self.cmd(cmd[len("return run "):]) or 0
        if cmd.startswith("return "):
            return "return", int(cmd.split()[1])
        if cmd.startswith("execute "):
            return self.execute(cmd[len("execute "):])
        return "ok", self.cmd(cmd)

    def score(self, h, o):
        return self.scores.get((h, o))

    def execute(self, rest):
        store = None
        while True:
            if rest.startswith("run "):
                inner = rest[4:]
                kind, val = self.run(inner)
                if store:
                    self.put(store, val or 0)
                return kind, val
            t = rest.split(" ")
            if t[0] == "store":
                if t[2] == "score":
                    store, rest = ("score", t[3], t[4]), " ".join(t[5:])
                else:   # store result storage S path int 1
                    store, rest = ("storage", t[4]), " ".join(t[7:])
                continue
            if t[0] in ("if", "unless"):
                want = t[0] == "if"
                if t[1] == "score":
                    v = self.score(t[2], t[3])
                    if t[4] == "matches":
                        r = t[5]
                        if ".." in r:
                            lo, hi = r.split("..")
                            ok = v is not None and (not lo or v >= int(lo)) and (not hi or v <= int(hi))
                        else:
                            ok = v == int(r)
                        rest = " ".join(t[6:])
                    else:
                        w = self.score(t[5], t[6])
                        ok = v is not None and w is not None and {"=": v == w, ">": v > w, "<": v < w}[t[4]]
                        rest = " ".join(t[7:])
                elif t[1] == "entity":
                    m = re.fullmatch(r"@s\[advancements=\{cobblers:flag/(\w+)=true\}\]", t[2])
                    assert m, t[2]
                    ok, rest = m.group(1) in self.flags, " ".join(t[3:])
                else:
                    raise AssertionError("execute %s" % rest)
                if ok != want:
                    return "ok", None
                continue
            raise AssertionError("execute %s" % rest)

    def put(self, store, v):
        if store[0] == "score":
            self.scores[(store[1], store[2])] = v
        else:
            self.storage[store[1]] = v

    def args(self, path):
        pre = path + "."
        return {k[len(pre):]: v for k, v in self.storage.items() if k.startswith(pre)}

    def cmd(self, c):
        t = c.split(" ")
        if c.startswith("scoreboard objectives add"):
            return 1
        if t[:2] == ["scoreboard", "players"]:
            op, h, o = t[2], t[3], t[4]
            if op == "set":
                self.scores[(h, o)] = int(t[5])
            elif op == "add":
                self.scores[(h, o)] = (self.score(h, o) or 0) + int(t[5])
            elif op == "remove":
                self.scores[(h, o)] = (self.score(h, o) or 0) - int(t[5])
            elif op == "operation":
                assert t[5] == "="
                self.scores[(h, o)] = self.score(t[6], t[7])
            elif op == "get":
                return self.score(h, o)
            return self.score(h, o)
        if c == "time query gametime":
            return self.time
        if c == "rctmod player get level_cap @s":
            return self.cap
        if t[0] == "cobbledollars":
            n = int(t[3]) if len(t) > 3 else 0
            self.log.append(c)
            if t[1] == "query":
                return self.balance
            if t[1] == "remove":
                if self.remove_works:
                    self.balance -= n
                return 1
            if t[1] == "give":
                self.balance += n
                return 1
        if t[0] == "testpartyslot":
            mon = self.party.get(int(t[2]))
            if mon is None:
                return None
            for p in t[3:]:
                k, v = p.split("=")
                if k != "level":
                    raise AssertionError("testpartyslot %s is not modelled (only level= is VERIFIED)" % k)
                if mon.level != int(v):
                    return 0
            return 1
        if t[0] == "pokemoneditother":
            self.log.append(c)
            mon = self.party.get(int(t[2]))
            if mon is None or not self.edit_works:
                return None
            for p in t[3:]:
                k, v = p.split("=")
                v = int(v)
                if k == "level":
                    mon.level = max(1, min(100, v))
                elif k.endswith("_ev"):
                    s, v = k[:-3], max(0, min(252, v))
                    if sum(mon.evs.values()) - mon.evs[s] + v <= 510:     # EVs.canSet
                        mon.evs[s] = v
                elif k.endswith("_iv"):
                    mon.ivs[k[:-3]] = max(0, min(31, v))
                else:
                    raise AssertionError(k)
            return 1
        if t[0] == "tellraw":
            self.log.append(c)
            return 1
        if t[:3] == ["data", "modify", "storage"]:
            path, value = t[4], " ".join(t[7:])
            for k in [k for k in self.storage if k == path or k.startswith(path + ".")]:
                del self.storage[k]
            if value.startswith("{"):
                for k, v in re.findall(r'(\w+):("(?:[^"]*)"|-?\d+)', value[1:-1]):
                    self.storage["%s.%s" % (path, k)] = v[1:-1] if v.startswith('"') else int(v)
            else:
                self.storage[path] = int(value)
            return 1
        if t[0] == "function":
            name = t[1].split(":", 1)[1]
            args = self.args(t[5]) if len(t) > 2 and t[2] == "with" else {}
            return self.call(name, args)
        raise AssertionError("unmodelled command %r" % c)

    # ------------------------------------------------------------------ the player's view
    def click(self, rel):
        self.call("training_services/" + rel)
        return self

    def edits(self):
        return [l for l in self.log if l.startswith("pokemoneditother")]

    def told(self):
        return [l for l in self.log if l.startswith("tellraw")]


def price(key):
    return DOC["services"][key]["price"]


# ------------------------------------------------------------------------------------------------- the level rule
def test_builders_own_audit_of_the_output_is_clean():
    assert T.output_problems(DOC, FILES) == []


def test_no_line_writes_a_level_but_the_cap_read():
    lv = [l for ls in FNS.values() for l in ls if "pokemoneditother" in l and re.search(r"\b(level|lvl|l)=", l)]
    assert lv == ["$pokemoneditother @s $(slot) level=$(cap)"]
    caps = [l for ls in FNS.values() for l in ls if "req.cap" in l]
    assert caps == ["execute store result storage %s req.cap int 1 run scoreboard players get @s %s" % (T.STORAGE, T.CAP)]


def test_the_output_audit_catches_an_authored_level():
    """Mutate the GENERATOR's output (not the data): a level that is not the cap read is named."""
    bad = copy.deepcopy(FILES)
    p = PREFIX + "training_services/raise/apply.mcfunction"
    bad[p] = [l.replace("level=$(cap)", "level=100") for l in bad[p]]
    assert any("writes a level other than the cap" in x for x in T.output_problems(DOC, bad))


@pytest.mark.parametrize("cap", [20, 25, 35, 55, 60, 62])
@pytest.mark.parametrize("slot", [1, 4, 6])
def test_a_raise_sets_exactly_the_read_cap_and_charges_once(cap, slot):
    p = Player(cap=cap, party={slot: Mon(7)}).click("raise/slot%d" % slot)
    assert p.party[slot].level == cap
    assert p.balance == 10_000 - price("raise")
    assert [l for l in p.log if l.startswith("cobbledollars remove")] == ["cobbledollars remove @s %d" % price("raise")]


def test_the_raise_follows_a_changed_cap_not_a_stored_one():
    p = Player(cap=25, party={1: Mon(5), 2: Mon(5)}).click("raise/slot1")
    p.cap, p.time = 40, p.time + 100
    p.click("raise/slot2")
    assert (p.party[1].level, p.party[2].level) == (25, 40)


# ------------------------------------------------------------------------------------------ every refusal is free
REFUSALS = {
    "cap unread": dict(cap=0),
    "cap past the flat service": dict(cap=100),
    "cap one past max_cap": dict(cap=DOC["services"]["raise"]["max_cap"] + 1),
    "empty slot": dict(party={2: Mon(10)}),
    "slot at the cap": dict(party={1: Mon(30)}),
    "slot above the cap": dict(party={1: Mon(31)}),
    "short by one": dict(balance=price("raise") - 1),
    "no money": dict(balance=0),
}


@pytest.mark.parametrize("why", sorted(REFUSALS))
def test_every_raise_refusal_charges_nothing_and_edits_nothing(why):
    kw = dict(REFUSALS[why])
    p = Player(**kw).click("raise/slot1")
    assert p.balance == kw.get("balance", 10_000), why
    assert not [l for l in p.log if l.startswith("cobbledollars remove")], why
    assert p.edits() == [], why
    assert p.told(), "a refusal says why: %s" % why


def test_a_charge_that_takes_nothing_does_nothing():
    p = Player(remove_works=False).click("raise/slot1")
    assert p.balance == 10_000 and p.edits() == [] and p.party[1].level == 12


def test_an_edit_that_does_not_take_is_refunded():
    p = Player(edit_works=False).click("raise/slot1")
    assert p.balance == 10_000
    assert "cobbledollars give @s %d" % price("raise") in p.log


def test_a_second_click_inside_the_cooldown_buys_nothing():
    p = Player(party={1: Mon(5)}).click("raise/slot1")
    p.party[1].level = 5                    # as if the first had not landed: the second must still not charge
    p.click("raise/slot1")
    assert p.balance == 10_000 - price("raise")
    p.time += DOC["cooldown_ticks"]
    p.click("raise/slot1")
    assert p.balance == 10_000 - 2 * price("raise")


@pytest.mark.parametrize("rel,flags", [("ev/physical_sweeper/slot1", ()), ("ev/physical_sweeper/slot1", ("gym1_cleared",)),
                                       ("iv/attack/slot1", ("gym2_cleared",)), ("iv/all/slot1", ("gym7_cleared",))])
def test_ev_and_iv_without_their_badge_charge_nothing(rel, flags):
    p = Player(flags=flags).click(rel)
    assert p.balance == 10_000 and p.edits() == [] and p.told()


@pytest.mark.parametrize("rel", ["ev/special_wall/slot3", "iv/speed/slot3", "iv/all/slot3"])
def test_ev_and_iv_on_an_empty_slot_charge_nothing(rel):
    p = Player(flags=("gym2_cleared", "gym8_cleared")).click(rel)
    assert p.balance == 10_000 and p.edits() == []


def test_ev_and_iv_short_of_money_charge_nothing():
    for rel, key in (("ev/bulky_special/slot1", "ev"), ("iv/all/slot1", "iv")):
        need = price("ev") if key == "ev" else DOC["services"]["iv"]["price_per_stat"] * 6
        p = Player(balance=need - 1, flags=("gym2_cleared", "gym8_cleared")).click(rel)
        assert p.balance == need - 1 and p.edits() == [], rel


# ----------------------------------------------------------------------------------------------- the EVs and IVs
@pytest.mark.parametrize("spread", DOC["services"]["ev"]["spreads"], ids=lambda s: s["id"])
def test_an_ev_spread_replaces_the_old_one_whatever_it_was(spread):
    old = Mon(20, evs={"attack": 252, "speed": 252, "hp": 6})          # a full 510 already
    p = Player(party={1: old}, flags=("gym2_cleared",)).click("ev/%s/slot1" % spread["id"])
    assert p.party[1].evs == {s: spread["evs"].get(s, 0) for s in STATS}
    assert p.balance == 10_000 - price("ev")


def test_without_the_zeroing_the_510_rule_would_keep_the_old_spread():
    """The reason for the first command: the model's canSet refuses the new spread on a full Pokemon."""
    p = Player(party={1: Mon(20, evs={"attack": 252, "speed": 252, "hp": 6})})
    p.cmd("pokemoneditother @s 1 hp_ev=252 defence_ev=252 special_defence_ev=4")
    assert p.party[1].evs["defence"] == 0


def test_every_spread_fits_under_510():
    for s in DOC["services"]["ev"]["spreads"]:
        assert sum(s["evs"].values()) <= 510 and set(s["evs"]) <= set(STATS)


def test_iv_one_stat_and_all_six():
    p = Player(flags=("gym8_cleared",)).click("iv/special_attack/slot1")
    assert p.party[1].ivs["special_attack"] == 31 and sum(p.party[1].ivs.values()) == 31
    per = DOC["services"]["iv"]["price_per_stat"]
    assert p.balance == 10_000 - per
    p.time += 100
    p.click("iv/all/slot1")
    assert set(p.party[1].ivs.values()) == {31} and p.balance == 10_000 - 7 * per


# --------------------------------------------------------------------------------------------------- the dialogue
def test_each_keeper_offers_six_slots_per_service_and_gates_ev_and_iv():
    for k in DOC["keepers"]:
        d = FILES["data/cobblers/dialogues/dlg_training_keeper_%s.json" % T.keeper_id(k)]
        pages = {p["id"]: p for p in d["pages"]}
        hub = {o["value"]: o for o in pages["hub"]["input"]["options"]}
        assert "isVisible" not in hub["r_raise"]
        text = json.dumps(d)
        for rid, flag in (("r_ev", "gym2_cleared"), ("r_iv", "gym8_cleared")):
            tag = re.search(r"has_tag\('([a-z0-9_]+)'\)", hub[rid]["isVisible"]).group(1)
            assert "advancements={cobblers:flag/%s=true}] run tag @s add %s" % (flag, tag) in text, (rid, flag)
        for n in range(1, 7):
            assert "training_services/raise/slot%d'" % n in json.dumps(pages["raise"])
        for pid, page in pages.items():
            if pid in ("hub", "ev", "iv"):
                continue
            slots = [o for o in page["input"]["options"] if "/slot" in o["action"]]
            assert len(slots) == 6, pid


def test_every_function_a_dialogue_names_exists():
    named = set()
    for p, c in FILES.items():
        if p.startswith("data/cobblers/dialogues/"):
            named |= set(re.findall(r"function cobblers:(training_services/[a-z0-9_/]+)", json.dumps(c)))
    assert named and named <= set(FNS)


# ------------------------------------------------------------------------------------------------ seats and wiring
def test_npc_placements_come_from_the_committed_data():
    got = T.npc_placements(DOC)
    assert len(got) == 8 == len({g[0] for g in got}) == len({g[2] for g in got})
    assert all(len(g[1]) == 3 and isinstance(g[3], int) for g in got)


def test_seats_are_the_heightmap_seats():
    try:
        problems = T.seat_problems(DOC)
    except (FileNotFoundError, SystemExit, OSError) as e:
        pytest.skip("no heightmap here: %s" % e)
    assert problems == []


def test_reapply_builds_installs_and_places_it():
    import reapply as R
    assert "cobblers_training_services" in R.SERVER_PACKS and "cobblers_training_services" in R.WORLD_LOCAL
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert 'add("training_services:build", "training_services.py", "build")' in src
    assert '("R17TS"' in src and 'cobblers:training_services/load' in src
