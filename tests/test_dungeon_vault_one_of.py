"""The vault's second stack form, {"one_of": [{"item", "weight", "count"?}, ...], "chance"?}.

  generator  ONE pool, rolls 1, an entry an option with its weight and its own set_count; the chance sits on the pool.
  old form   {"item", "count", "chance"} generates byte-identical output to 6c39444 (tests/fixtures/
             dungeon_pay_office_loot_6c39444.json holds the stacks and the text the old generator made for the Night
             Shift's pay_office, so a later edit to data/dungeons.json cannot move the baseline).
  refusal    a malformed one_of is refused by DP.check_loot (so R.problems and a build) and by the greed table
             (DG.chest_cp is None, DG.problems names it).
  greed      the value of a one_of is chance x the weight-weighted mean of count x cp; computed here from the table's
             own prices, not from any generator function.
  mutation   the GENERATOR is changed (the weight dropped from the emitted entry): the shape test must fail.

NOT proved here: that Minecraft rolls a weighted pool as the shape says (needs a run).
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

import dungeon_greed as DG  # noqa: E402
import dungeon_puzzles as DP  # noqa: E402

GOLD = json.loads((ROOT / "tests" / "fixtures" / "dungeon_pay_office_loot_6c39444.json").read_text(encoding="utf-8"))["bands"]
TABLE = DG.load()
PRICED = [i for i in TABLE["items"] if TABLE["items"][i]["cp"] > 0][:3]
BANDS = [1, 2, 3, 4, 5, 6]


def stack(chance=None):
    s = {"one_of": [{"item": PRICED[0], "weight": 3, "count": 2},
                    {"item": PRICED[1], "weight": 1, "count": [1, 4]},
                    {"item": PRICED[2], "weight": 6}]}
    if chance is not None:
        s["chance"] = chance
    return s


def check(s):
    return DP.check_loot("t", {"loot_by_band": {"1": [s]}}, BANDS)


# ------------------------------------------------------------------------------------------------- generator


def test_a_one_of_is_one_pool_with_a_weighted_entry_an_option_and_the_chance_on_the_pool():
    # without it a one_of could come out as a pool an option (every option drops) or lose its weights (equal odds)
    t = DP.loot_table([stack(0.25), {"item": PRICED[0], "count": 1}])
    assert t["type"] == "minecraft:chest" and len(t["pools"]) == 2
    pool = t["pools"][0]
    assert pool["rolls"] == 1 and len(pool["entries"]) == 3
    assert pool["conditions"] == [{"condition": "minecraft:random_chance", "chance": 0.25}]
    assert [e["weight"] for e in pool["entries"]] == [3, 1, 6]
    assert [e["name"] for e in pool["entries"]] == PRICED[:3]
    assert all(e["type"] == "minecraft:item" for e in pool["entries"])
    counts = [e["functions"] for e in pool["entries"]]
    assert counts[0] == [{"function": "minecraft:set_count", "count": 2}]
    assert counts[1] == [{"function": "minecraft:set_count", "count": {"type": "minecraft:uniform", "min": 1, "max": 4}}]
    assert counts[2] == [{"function": "minecraft:set_count", "count": 1}], "count defaults to 1"
    assert "weight" not in t["pools"][1]["entries"][0], "the plain stack is untouched"


def test_a_one_of_without_a_chance_has_no_condition():
    pool = DP.loot_table([stack()])["pools"][0]
    assert "conditions" not in pool


def test_the_old_stack_form_is_byte_identical_to_the_generator_at_6c39444_for_the_pay_office():
    assert sorted(GOLD) == ["1", "2", "3", "4", "5", "6"]
    for band, row in GOLD.items():
        assert json.dumps(DP.loot_table(row["stacks"]), indent=2) + "\n" == row["text"], band


def test_the_pack_writes_the_one_of_table_for_a_vault_room():
    # pack_files is what tools/dungeon.py build() writes the vaults' loot tables from. (A whole D.build of a fixture
    # dungeon takes ~7 minutes, and the greed budget refuses a dear chest there: not run in this file.)
    doc = {"dungeons": [{"id": "dd", "rooms": [{"id": "vv", "kind": "vault", "params": {"loot_by_band": {"1": [stack(0.5)]}}}]}]}
    files = DP.pack_files(doc)
    assert list(files) == ["data/cobblers/loot_table/dungeons/vault/dd/vv/b1.json"]
    t = json.loads(next(iter(files.values())))
    assert [e["weight"] for e in t["pools"][0]["entries"]] == [3, 1, 6]
    assert files["data/cobblers/loot_table/dungeons/vault/dd/vv/b1.json"] == json.dumps(DP.loot_table([stack(0.5)]), indent=2) + "\n"


# ------------------------------------------------------------------------------------------------- refusal

BAD = {
    "empty options": {"one_of": []},
    "not a list": {"one_of": "x"},
    "no weight": {"one_of": [{"item": PRICED[0]}]},
    "zero weight": {"one_of": [{"item": PRICED[0], "weight": 0}]},
    "negative weight": {"one_of": [{"item": PRICED[0], "weight": -1}]},
    "float weight": {"one_of": [{"item": PRICED[0], "weight": 1.5}]},
    "bool weight": {"one_of": [{"item": PRICED[0], "weight": True}]},
    "bare item": {"one_of": [{"item": "diamond", "weight": 1}]},
    "no item": {"one_of": [{"weight": 1}]},
    "count 0": {"one_of": [{"item": PRICED[0], "weight": 1, "count": 0}]},
    "count 65": {"one_of": [{"item": PRICED[0], "weight": 1, "count": 65}]},
    "count reversed": {"one_of": [{"item": PRICED[0], "weight": 1, "count": [4, 2]}]},
    "chance 0": dict(stack(), chance=0),
    "chance over 1": dict(stack(), chance=1.5),
    "chance string": dict(stack(), chance="0.5"),
    "item beside one_of": dict(stack(), item=PRICED[0]),
    "chance on an option": {"one_of": [{"item": PRICED[0], "weight": 1, "chance": 0.5}]},
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_a_malformed_one_of_is_refused_by_the_loot_check_and_unpriced_by_the_greed_table(name):
    s = BAD[name]
    assert check(s), name          # the build refuses (a vault's c.fail) and R.problems names it
    assert DG.chest_cp(TABLE, [s]) is None, name


def test_a_sound_one_of_passes_the_loot_check_including_a_chance_of_one():
    assert check(stack()) == [] and check(stack(1)) == [] and check(stack(0.01)) == []


def test_an_unpriced_option_makes_the_whole_one_of_unpriced_and_the_greed_problem_names_it():
    s = {"one_of": [{"item": PRICED[0], "weight": 1}, {"item": "minecraft:bedrock", "weight": 1}]}
    assert DG.chest_cp(TABLE, [s]) is None
    doc = json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))
    doc2 = copy.deepcopy(doc)
    d2, r2, k, _spec = DG.vault_specs(doc2)[0]      # the first real vault's first band, replaced by the unpriced one_of
    r2["params"]["loot_by_band"][str(k)] = [s]
    bad = [p for p in DG.problems(doc2) if "minecraft:bedrock" in p]
    assert bad, "the greed problem names the unpriced option"


# ------------------------------------------------------------------------------------------------- greed


def test_the_greed_value_of_a_one_of_is_the_weighted_mean_times_the_chance():
    # worked by hand from the table's own prices: not through DP, not through chest_cp's helpers
    p = [TABLE["items"][i]["cp"] for i in PRICED]
    mean = (3 * 2 * p[0] + 1 * 2.5 * p[1] + 6 * 1 * p[2]) / 10.0
    assert DG.chest_cp(TABLE, [stack()]) == int(round(mean))
    assert DG.chest_cp(TABLE, [stack(0.4)]) == int(round(0.4 * mean))
    # a plain stack beside it adds as before
    plain = {"item": PRICED[0], "count": 3, "chance": 0.5}
    assert DG.chest_cp(TABLE, [stack(0.4), plain]) == int(round(0.4 * mean + 0.5 * 3 * p[0]))


def test_a_single_option_one_of_prices_as_the_plain_stack():
    one = {"one_of": [{"item": PRICED[0], "weight": 7, "count": [2, 6]}], "chance": 0.5}
    assert DG.chest_cp(TABLE, [one]) == DG.chest_cp(TABLE, [{"item": PRICED[0], "count": [2, 6], "chance": 0.5}])


# ------------------------------------------------------------------------------------------------- mutation


def test_the_shape_test_catches_a_generator_that_drops_the_weight(monkeypatch):
    # the GENERATOR is changed (not the record): the same call with the weight stripped from the emitted entries
    real = DP.loot_table

    def no_weight(stacks):
        t = real(stacks)
        for pool in t["pools"]:
            for e in pool["entries"]:
                e.pop("weight", None)
        return t
    monkeypatch.setattr(DP, "loot_table", no_weight)
    with pytest.raises((KeyError, AssertionError)):
        test_a_one_of_is_one_pool_with_a_weighted_entry_an_option_and_the_chance_on_the_pool()
    monkeypatch.setattr(DP, "loot_table", real)
    test_a_one_of_is_one_pool_with_a_weighted_entry_an_option_and_the_chance_on_the_pool()
