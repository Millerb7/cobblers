"""tools/drop_fixes.py and data/drop_fixes.json: the sweep over every species drop table the server loads, and our fixes.

The sweep is the guard: a new drop entry naming no registered item, or one the roll can never reach, in any installed
jar, the global datapacks or our own species packs, fails test_the_sweep_finds_nothing_unaccounted until it is fixed
or held open in data/drop_fixes.json with a reason. The roll is checked against a simulation written here from the
jar's DropTable.getDrops (not imported from the tool), and the generator is mutated to show the checks bite.

Skips when the offline snapshot's jars or the COBBLEVERSE datapack are absent (an agent worktree may have neither).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import drop_fixes as DF  # noqa: E402

TRIALS = 40000


@pytest.fixture(scope="module")
def inputs():
    try:
        return DF.default_inputs()
    except SystemExit as e:
        pytest.skip("missing an input: %s" % e)


@pytest.fixture(scope="module")
def doc():
    return DF.load()


@pytest.fixture(scope="module")
def upstream_faults(inputs, doc):
    fs, _bad = DF.sweep(doc, with_fixes=False, inputs=inputs)
    return fs


# ------------------------------------------------------------------ an independent roll


def _rng(v):
    if isinstance(v, int):
        return v, v
    a, _, b = str(v).partition("-")
    return int(a), int(b or a)


def roll(table, rng):
    """One defeat by DropTable.getDrops (javap 2026-10-08): (indices chosen, {item: count dropped})."""
    lo, hi = _rng(table.get("amount", 1))
    amt = rng.randint(lo, hi)
    ents = table.get("entries") or []
    pool = [i for i, e in enumerate(ents) if int(e.get("quantity", 1)) <= amt]
    picked, taken = 0, []
    while picked < amt and pool:
        sel = next((i for i in pool if rng.random() * 100 < float(ents[i].get("percentage", 100))), None)
        if sel is None:
            picked += 1
            continue
        taken.append(sel)
        picked += int(ents[sel].get("quantity", 1))
        pool = [i for i in pool if not ((i == sel and int(ents[i].get("maxSelectableTimes", 1)) <= taken.count(sel))
                                        or int(ents[i].get("quantity", 1)) > amt - picked)]
    got = {}
    for i in taken:
        e = ents[i]
        n = rng.randint(*_rng(e["quantityRange"])) if "quantityRange" in e else int(e.get("quantity", 1))
        if n > 0:
            got[e["item"]] = got.get(e["item"], 0) + n
    return set(taken), got


def simulate(table, seed=0, trials=TRIALS):
    rng = random.Random(seed)
    chosen, items = {}, {}
    for _ in range(trials):
        t, g = roll(table, rng)
        for i in t:
            chosen[i] = chosen.get(i, 0) + 1
        for it in g:
            items[it] = items.get(it, 0) + 1
    return {i: n / trials for i, n in chosen.items()}, {i: n / trials for i, n in items.items()}


def tol(p, trials=TRIALS):
    return 5 * (max(p * (1 - p), 1e-4) / trials) ** 0.5 + 0.002


# ------------------------------------------------------------------ the tests


def test_the_data_checks(inputs, doc):
    mods, zips, vanilla = inputs
    problems = DF.check(doc, DF.upstream_files(doc, zips), DF.items_known(mods, zips, vanilla, {}),
                        DF.species_tables(mods, zips))
    assert problems == []


def test_the_sweep_finds_nothing_unaccounted(inputs, doc):
    _fs, bad = DF.sweep(doc, inputs=inputs)
    assert bad == [], ["%s: %s" % (f["species"], f["detail"]) for f in bad][:10]


def test_the_sweep_finds_upstreams_faults(upstream_faults, doc):
    """The owner's three, by name, and every fault upstream ships is fixed or held open; every fix names a real one."""
    keys = {(f["species"], f["kind"], f.get("item")) for f in upstream_faults}
    for k in [("helioptile", "missing_item", "minecraft:sun_stone"), ("heliolisk", "missing_item", "minecraft:sun_stone"),
              ("spritzee", "missing_item", "minecraft:kebia_berry"), ("litleo", "unreachable", "minecraft:blaze_powder"),
              ("litleo", "unreachable", "cobblemon:rawst_berry")]:
        assert k in keys, k
    fixed = {(fx["species"],) + tuple(s.split(" ", 1)) for fx in doc["fixes"] for s in fx["fixes"]}
    held = {(o["species"], o["kind"], o.get("item")) for o in doc["open"]}
    assert keys == fixed | held, ("not fixed or held", sorted(keys - fixed - held), "fixed but not a fault",
                                  sorted(fixed - keys))


def test_unreachable_agrees_with_a_simulation(upstream_faults, inputs):
    tables = DF.species_tables(*inputs[:2])
    flagged = {(f["species"], f["entry"]) for f in upstream_faults if f["kind"] == "unreachable"}
    for sp in sorted({s for s, _ in flagged}):
        chosen, _items = simulate(tables[sp])
        n = len(tables[sp]["entries"])
        never = {(sp, i) for i in range(n) if chosen.get(i, 0) == 0}
        assert never == {k for k in flagged if k[0] == sp}, sp


def test_each_fixed_table_rolls_its_intent(doc):
    problems = []
    for k, fx in enumerate(doc["fixes"]):
        chosen, items = simulate(fx["drops"], seed=k)
        for e_i in range(len(fx["drops"]["entries"])):
            if chosen.get(e_i, 0) == 0:
                problems.append("%s entry %d never chosen" % (fx["species"], e_i))
        for item, want in fx["intent"].items():
            got = items.get(item, 0.0)
            if abs(got - want / 100.0) > tol(want / 100.0):
                problems.append("%s %s: simulated %.4f, intent %.4f" % (fx["species"], item, got, want / 100.0))
    assert problems == []


def test_the_owners_three_are_fixed_as_stated(doc):
    by = {fx["species"]: fx for fx in doc["fixes"]}
    assert by["helioptile"]["intent"] == {"cobblemon:sun_stone": 2.0}
    assert by["heliolisk"]["intent"] == {"cobblemon:sun_stone": 2.3}
    assert by["spritzee"]["intent"] == {"cobblemon:kebia_berry": 75.0}
    assert by["litleo"]["intent"] == {"minecraft:rotten_flesh": 50.0, "minecraft:blaze_powder": 5.0,
                                      "cobblemon:rawst_berry": 2.5}


def test_an_overlay_changes_the_drops_and_nothing_else(inputs, doc):
    up = DF.upstream_files(doc, inputs[1])
    out = DF.files(doc, up)
    for fx in doc["fixes"]:
        u = fx["upstream"]
        if u["via"] == "species_additions":
            ours = json.loads(out[u["path"]])
            assert {k: v for k, v in ours.items() if k != "drops"} == {k: v for k, v in up[u["path"]].items()
                                                                       if k != "drops"}, fx["species"]
            assert ours["drops"] == fx["drops"]
        else:
            ours = json.loads(out["data/cobblers/species_additions/drop_fix_%s.json" % fx["species"]])
            assert ours == {"target": "cobblemon:%s" % fx["species"], "drops": fx["drops"]}


def test_mutating_the_generator_to_ship_upstreams_table_fails_the_sweep(inputs, doc, monkeypatch):
    """Mutate files(): the overlay keeps upstream's drops for Litleo and Helioptile. The data is untouched."""
    real = DF.files

    def mutated(d, upstream):
        out = real(d, upstream)
        for fx in d["fixes"]:
            if fx["species"] in ("litleo", "helioptile"):
                p = fx["upstream"]["path"]
                out[p] = json.dumps(dict(json.loads(out[p]), drops=fx["upstream"]["drops"]))
        return out
    monkeypatch.setattr(DF, "files", mutated)
    _fs, bad = DF.sweep(doc, inputs=inputs)
    assert {f["species"] for f in bad} == {"litleo", "helioptile"}


def test_mutating_the_roll_is_caught(doc, monkeypatch):
    """Mutate chosen(): every entry rolled independently at its bare percentage, ignoring the pass order. The check's
    intent comparison must fail, as the simulation above would."""
    def naive(table):
        _a, ents = DF.parse(table)
        sets = {frozenset(): 1.0}
        for i, e in enumerate(ents):
            p = min(1.0, max(0.0, e["p"] / 100.0))
            nxt = {}
            for s, c in sets.items():
                nxt[s] = nxt.get(s, 0.0) + c * (1 - p)
                nxt[s | {i}] = nxt.get(s | {i}, 0.0) + c * p
            sets = nxt
        return sets
    monkeypatch.setattr(DF, "chosen", naive)
    problems = DF.check(doc)
    assert any("litleo" in p for p in problems), problems
