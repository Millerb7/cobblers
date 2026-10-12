"""The bait room's lure rolls (tools/dungeon_extras.py lure_lines / lure_roll_lines / lure_variants / tier_problems).

The owner (2026-10-12): a lured Pokemon gets two SEPARATE rolls, a chance to be shiny and a chance to be an alpha (so a lure may be
shiny only, alpha only, both or neither); it stays at the band's lower level cap. The table gives each bait a tier
(`bait_room.tiers[<id>] = {shiny_chance, alpha_chance, why}`, `baits[n].tier`).

What this file proves, FAST (no dungeon build): the generated lure lines, run by tests/pocket_sim.py's World on a tiny pack of just
those lines, roll each chance by its own `random value`, add `shiny=true` / `alpha=true` exactly when that roll falls inside the
bait's tier chance, add nothing at a chance of 0 and always at 1, spawn one Pokemon, and are unchanged from the text the module
wrote before tiers existed when the table has none. The generator is mutated (not the data) to show the checks bite.

NOT proved here: that Cobblemon 1.8.0's `spawnpokemonat` honours `shiny=true` / `alpha=true` (EXP needed; the property names are
read from the jar's PokemonProperties constant pool, see the comment in dungeon_extras.py), and the full dungeon build with
tiers (the slow modules tests/test_dungeon_extras.py cover the build with the table as committed).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon_extras as DX  # noqa: E402
import pocket_sim as PS  # noqa: E402

N = DX.ROLL_N
HZ = "#s1r2_z"
DIM = "cobblers:pocket"
LOWER = {1: 12, 2: 20}                      # band -> the band's lower cap (what the engine passes as level=)


def table(tiers=True):
    """A bait table with every tier shape: always-shiny, always-alpha, both, neither, a mid chance, a tiny one."""
    baits = [("a", "S"), ("b", "A"), ("c", "B"), ("d", "N"), ("e", "M"), ("f", "F")]
    br = {"baits": [{"id": "cobblemon:%s_berry" % n, "name": "%s berry" % n, "tier": t, "source": "somewhere",
                     "species_by_band": {"1": "rattata", "2": "raticate"}} for n, t in baits]}
    if not tiers:
        for b in br["baits"]:
            del b["tier"], b["source"]
        return br
    br["tiers"] = {
        "S": {"shiny_chance": 1.0, "alpha_chance": 0.0, "why": "always shiny"},
        "A": {"shiny_chance": 0.0, "alpha_chance": 1.0, "why": "always alpha"},
        "B": {"shiny_chance": 1.0, "alpha_chance": 1.0, "why": "both"},
        "N": {"shiny_chance": 0.0, "alpha_chance": 0.0, "why": "neither"},
        "M": {"shiny_chance": 0.25, "alpha_chance": 0.5, "why": "mid"},
        "F": {"shiny_chance": 0.0025, "alpha_chance": 0.0001, "why": "tiny"},
    }
    return br


def lines_of(br):
    return DX.lure_lines(br, {b: "level=%d" % lv for b, lv in LOWER.items()}, HZ, DIM, "cobblers:dungeons/at", "cobblers:dungeons/bind",
                         "dg.keep", (10, 64, 20), 3)


def run_lure(br, bait, band, rs, ra, tmp_path):
    """Run the lure lines for one bait index (1-based) and band with the two queued rolls (shiny's first); the spawned Pokemon."""
    fns = {"cobblers:dungeons/lure": lines_of(br),
           "cobblers:dungeons/at": ["$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"],
           "cobblers:dungeons/bind": ["tag @s add bound"]}
    w = PS.World(tmp_path, fns)
    w.objectives |= {"dg.t", "dg.rs", "dg.band"}
    p = w.player("Ash", DIM, (10, 64, 20))
    w.set(p.name, "dg.band", band)
    w.set(HZ, "dg.rs", bait)
    w.random_by_range = {(1, N): [rs, ra]}
    w.call("cobblers:dungeons/lure", PS.Ctx(p, DIM, p.pos))
    return [e for e in w.spawned if e.alive], w


def props_of(e):
    return set(e.props)


# ------------------------------------------------------------------------------------------------ the lines

def test_two_rolls_two_scores_and_each_flag_reads_only_its_own_roll():
    lines = lines_of(table())
    stores = [l for l in lines if "run random value" in l]
    assert len(stores) == 2 and all(l.endswith("run random value 1..%d" % N) for l in stores), stores
    held = [l.split("score ")[1].split(" ")[0] for l in stores]
    assert len(set(held)) == 2, "the shiny and the alpha roll must be stored in different scores: %s" % held
    shiny_roll, alpha_roll = held
    for l in lines:
        if "players set %s " % DX.FLAG_S in l and l.endswith(" 1"):
            assert "score %s " % shiny_roll in l and "score %s " % alpha_roll not in l, l
        if "players set %s " % DX.FLAG_A in l and l.endswith(" 1"):
            assert "score %s " % alpha_roll in l and "score %s " % shiny_roll not in l, l


def test_a_chance_of_zero_writes_no_flag_line_and_no_variant_that_could_carry_the_property():
    br = table()
    lines = lines_of(br)
    flag_s = [l for l in lines if l.startswith("execute if score %s dg.rs matches" % HZ) and "players set %s " % DX.FLAG_S in l]
    flag_a = [l for l in lines if l.startswith("execute if score %s dg.rs matches" % HZ) and "players set %s " % DX.FLAG_A in l]
    shiny_baits = {int(l.split("matches ")[1].split(" ")[0]) for l in flag_s}
    alpha_baits = {int(l.split("matches ")[1].split(" ")[0]) for l in flag_a}
    assert shiny_baits == {1, 3, 5, 6}, "S, B, M, F can be shiny; A and N (chance 0) cannot: %s" % shiny_baits
    assert alpha_baits == {2, 3, 5, 6}, "A, B, M, F can be alpha; S and N cannot: %s" % alpha_baits
    n_spawns = lambda bait: len([l for l in lines if "run function cobblers:dungeons/at" in l and "matches %d if score @s dg.band matches 1" % bait in l])
    assert [n_spawns(i) for i in (1, 2, 3, 4, 5, 6)] == [1, 1, 1, 1, 4, 4]       # a sure thing needs one line; a chance, two per roll


# ------------------------------------------------------------------------------------------------ what the lure is

CASES = [
    # (bait index, shiny roll, alpha roll, the props the spawn carries)
    (5, 2500, 5000, {"level=12", "shiny=true", "alpha=true"}),        # M: both rolls on the edge of the chance
    (5, 2500, 5001, {"level=12", "shiny=true"}),                      # shiny only
    (5, 2501, 5000, {"level=12", "alpha=true"}),                      # alpha only
    (5, 2501, 5001, {"level=12"}),                                    # neither
    (5, 1, 10000, {"level=12", "shiny=true"}),                        # the rolls are not one: low shiny roll, high alpha roll
    (5, 10000, 1, {"level=12", "alpha=true"}),
    (6, 25, 1, {"level=12", "shiny=true", "alpha=true"}),             # F: 0.0025 -> 25, 0.0001 -> 1 (of 10000)
    (6, 26, 2, {"level=12"}),
    (6, 25, 2, {"level=12", "shiny=true"}),
    (1, 10000, 10000, {"level=12", "shiny=true"}),                    # chance 1 always; the alpha chance 0 never, even on a roll of 1
    (1, 1, 1, {"level=12", "shiny=true"}),
    (2, 10000, 10000, {"level=12", "alpha=true"}),
    (2, 1, 1, {"level=12", "alpha=true"}),
    (3, 10000, 10000, {"level=12", "shiny=true", "alpha=true"}),
    (4, 1, 1, {"level=12"}),                                          # N: a roll of 1 is the luckiest there is, and still nothing
    (4, 10000, 10000, {"level=12"}),
]


@pytest.mark.parametrize("bait,rs,ra,want", CASES)
def test_each_property_is_added_exactly_when_its_own_roll_lands_inside_its_chance(bait, rs, ra, want, tmp_path):
    got, _w = run_lure(table(), bait, 1, rs, ra, tmp_path)
    assert len(got) == 1, "exactly one Pokemon is lured: %s" % got
    assert props_of(got[0]) == want
    assert got[0].nbt["Pokemon"]["Level"] == LOWER[1], "it stays at the band's lower cap, catchable"
    assert not ({"uncatchable", "no_ai"} & props_of(got[0]))


def test_the_species_and_level_follow_the_band_and_the_bait_not_the_tier(tmp_path):
    got, _w = run_lure(table(), 3, 2, 10000, 10000, tmp_path)
    assert [(e.nbt["Pokemon"]["Species"], e.nbt["Pokemon"]["Level"]) for e in got] == [("cobblemon:raticate", LOWER[2])]


def test_a_bait_without_a_tier_in_a_table_that_has_tiers_rolls_nothing(tmp_path):
    br = table()
    del br["baits"][4]["tier"]
    got, _w = run_lure(br, 5, 1, 1, 1, tmp_path)
    assert len(got) == 1 and props_of(got[0]) == {"level=12"}


# ------------------------------------------------------------------------------------------------ old data is untouched

def old_lines(br):
    """The lure body as tools/dungeon_extras.py wrote it at 88bdde1 (before tiers): no rolls, one spawn line per bait and band."""
    from dungeon_fights import macro_args
    out = []
    for bi, bait in enumerate(br["baits"], 1):
        for bn, lv in LOWER.items():
            sp = bait["species_by_band"][str(bn)]
            cond = "if score %s dg.rs matches %d if score @s dg.band matches %d" % (HZ, bi, bn)
            out.append("execute %s in %s run function %s %s" % (cond, DIM, "cobblers:dungeons/at", macro_args(
                x="10.5", y="64", z="20.5", species=sp, props="level=%d" % lv)))
            out.append("execute %s in %s positioned 10.5 64 20.5 as @e[type=cobblemon:pokemon,tag=!dg.keep,distance=..3,sort=nearest,limit=1] "
                       "run function cobblers:dungeons/bind" % (cond, DIM))
    return out


def test_a_table_without_tiers_generates_exactly_the_text_it_always_did():
    br = table(tiers=False)
    assert lines_of(br) == old_lines(br)
    assert not any("random" in l or "shiny" in l or "alpha" in l for l in lines_of(br))


def test_the_committed_table_without_tiers_keeps_the_old_text_and_with_them_is_checked():
    br = DX.load()["bait_room"]
    if "tiers" not in br:
        lines = lines_of(br)
        assert not any(DX.PROP_SHINY in l or DX.PROP_ALPHA in l or "random" in l for l in lines)
    assert DX.tier_problems(br) == []


# ------------------------------------------------------------------------------------------------ mutate the GENERATOR

def test_one_roll_feeding_both_properties_is_caught(monkeypatch, tmp_path):
    # the generator's mutation (data untouched): the alpha roll is stored in the shiny roll's score. The case table then fails.
    monkeypatch.setattr(DX, "ROLL_A", DX.ROLL_S)
    with pytest.raises(AssertionError):
        test_two_rolls_two_scores_and_each_flag_reads_only_its_own_roll()
    failed = 0
    for i, (bait, rs, ra, want) in enumerate(CASES):
        got, _w = run_lure(table(), bait, 1, rs, ra, tmp_path / str(i))
        failed += not (len(got) == 1 and props_of(got[0]) == want)
    assert failed, "with one roll behind both properties the independent cases must disagree"


def test_a_threshold_off_by_one_is_caught(monkeypatch, tmp_path):
    monkeypatch.setattr(DX, "threshold", lambda p: int(round(float(p) * N)) + 1)
    failed = 0
    for i, (bait, rs, ra, want) in enumerate(CASES):
        got, _w = run_lure(table(), bait, 1, rs, ra, tmp_path / str(i))
        failed += not (len(got) == 1 and props_of(got[0]) == want)
    assert failed, "the edge cases (2500/2501, 25/26) must notice a threshold that is one too wide"


# ------------------------------------------------------------------------------------------------ the checks

def test_the_fixture_table_is_clean():
    assert DX.tier_problems(table()) == []
    assert DX.tier_problems(table(tiers=False)) == []


def mutated(fn):
    br = table()
    fn(br)
    return DX.tier_problems(br)


@pytest.mark.parametrize("fn,want", [
    (lambda b: b["baits"][0].update(tier="ghost"), "not one of tiers"),
    (lambda b: b["baits"][0].pop("tier"), "not one of tiers"),
    (lambda b: b["tiers"]["S"].update(shiny_chance=1.5), "must be a number in [0, 1]"),
    (lambda b: b["tiers"]["S"].update(alpha_chance=-0.1), "must be a number in [0, 1]"),
    (lambda b: b["tiers"]["S"].update(shiny_chance=True), "must be a number in [0, 1]"),
    (lambda b: b["tiers"]["S"].update(shiny_chance="0.5"), "must be a number in [0, 1]"),
    (lambda b: b["tiers"]["S"].pop("alpha_chance"), "must be a number in [0, 1]"),
    (lambda b: b["tiers"]["S"].update(alpha_chance=0.00005), "finer than the roll"),
    (lambda b: b["tiers"]["S"].update(why=" "), "non-empty `why`"),
    (lambda b: b["baits"][1].update(source=""), "`source` is a non-empty text"),
    (lambda b: b.update(tiers={}), "tiers is an object"),
])
def test_a_bad_tier_table_is_refused(fn, want):
    bad = mutated(fn)
    assert any(want in x for x in bad), bad


def test_a_tier_named_without_a_tiers_table_is_refused():
    br = table(tiers=False)
    br["baits"][2]["tier"] = "S"
    assert any("has no `tiers`" in x for x in DX.tier_problems(br))


def doc_with(br, monkeypatch, labels):
    monkeypatch.setitem(DX._DATA, str(DX.DATA), {**DX.load(), "bait_room": br})
    monkeypatch.setattr(DX, "species_labels", lambda: labels)
    monkeypatch.setattr(DX, "item_known", lambda i: None)
    return {"engine": {"bands": [{"band": 1}, {"band": 2}]}}


@pytest.mark.parametrize("label", ["legendary", "mythical", "ultra_beast", "paradox"])
def test_a_prize_class_species_is_refused_as_a_lure(monkeypatch, label):
    labels = {"rattata": set(), "raticate": {label}}
    bad = DX.table_problems(doc_with(table(), monkeypatch, labels), force=True)
    assert any("raticate is a legendary" in x for x in bad), bad
    assert not any("rattata is a legendary" in x for x in bad)


def test_an_ordinary_table_passes_the_table_checks(monkeypatch):
    labels = {"rattata": {"gen1"}, "raticate": set()}
    assert DX.table_problems(doc_with(table(), monkeypatch, labels), force=True) == []


# ------------------------------------------------------------------------------------------------ the player guide

def test_the_guide_prints_each_baits_tier_and_both_chances_and_nothing_without_tiers():
    import player_guide_dungeons as PG
    try:
        model = PG.collect()
    except SystemExit as e:                                  # no Cobblemon jar on this machine: the guide cannot be built
        pytest.skip("guide needs the jar: %s" % e)
    plain = PG.render(model)
    br = model["ex1"]["bait_room"]
    if "tiers" not in br:
        assert "Shiny chance" not in plain, "no tiers in the data: the guide prints no chances"
    tabled = copy.deepcopy(br)
    tabled["tiers"] = {"rare": {"shiny_chance": 0.0025, "alpha_chance": 0.05, "why": "t"},
                       "common": {"shiny_chance": 0.0, "alpha_chance": 0.01, "why": "t"}}
    for i, b in enumerate(tabled["baits"]):
        b["tier"] = "rare" if i == 0 else "common"
    model["ex1"]["bait_room"] = tabled
    html = PG.render(model)
    assert "<th>Tier</th><th>Shiny chance</th><th>Alpha chance</th>" in html
    assert "<td>Rare</td><td>0.25%</td><td>5%</td>" in html
    assert "<td>Common</td><td>0%</td><td>1%</td>" in html
