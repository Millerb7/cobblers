"""Dungeon fishing item catches (tools/dungeon_extras2.py item_catches, data/dungeon_extras2.json fishing.item_catches).

The owner (2026-10-17) hooked a tripwire hook in the Flooded Ruin's cast_pool: a Poke Rod bite that is not a Pokemon rolls the loot
table cobblemon:fishing/pokerod (junk 66 / pokerod_treasure 17 / vanilla treasure 17, both treasure entries gated on open water, which a
one-deep pool is not). The generator now overrides that table: in the pocket dimension it rolls a dungeon table of hits only,
anywhere else exactly the upstream entries.

These tests EVALUATE the generated table with a small loot-table interpreter that knows only the three conditions the table uses
(location_check on the dimension, inverted, entity_properties in_open_water), so what is checked is what Minecraft would choose, not
the generator's own idea of it. What this does NOT prove: that Cobblemon's bobber passes the origin the way a vanilla fishing context
does (the table is declared type minecraft:fishing, which requires origin, so a context without one would be refused when the table
loads), nor anything in a running game (experiments/EXP-090).
"""
from __future__ import annotations

import copy
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_extras2 as DX  # noqa: E402
import test_dungeon_extras2 as TX  # noqa: E402

JAR = TX.JAR
JAR_182 = Path("C:/Users/wnd/Documents/cobblers-local/server-mods-1.8.2/Cobblemon-fabric-1.8.2+1.21.1.jar")
POCKET = "cobblers:pocket"
CFG = DX.item_cfg()


def holds(cond, ctx):
    k = cond["condition"]
    if k == "minecraft:location_check":
        p = cond["predicate"]
        assert set(p) == {"dimension"}, "the interpreter knows only a dimension test: %r" % p
        return ctx["dimension"] == p["dimension"]
    if k == "minecraft:inverted":
        return not holds(cond["term"], ctx)
    if k == "minecraft:entity_properties":
        assert cond["entity"] == "this"
        ts = cond["predicate"]["type_specific"]
        assert ts["type"] == "cobblemon:poke_bobber"
        return ctx["open_water"] == ts["in_open_water"]
    raise AssertionError("unknown condition %r" % k)


def chosen(table, ctx):
    """{value: weight} the pool can roll in this context: only entries whose conditions all hold (a failed condition drops the
    entry from the total weight, as LootPool does)."""
    assert len(table["pools"]) == 1 and table["pools"][0]["rolls"] == 1.0
    out = {}
    for e in table["pools"][0]["entries"]:
        assert e["type"] == "minecraft:loot_table"
        if all(holds(c, ctx) for c in e.get("conditions", [])):
            out[e["value"]] = (e["weight"], e.get("quality", 0))
    return out


def upstream_table(jar):
    with zipfile.ZipFile(jar) as z:
        return json.loads(z.read("data/cobblemon/loot_table/fishing/pokerod.json"))


@pytest.fixture(scope="module")
def doc():
    return TX.xdoc("flooded_ruin")


def override(doc):
    return DX.pokerod_override(doc)


# ------------------------------------------------------------------------------------------------- the override


@pytest.mark.parametrize("open_water", (False, True))
def test_a_cast_in_the_pocket_rolls_the_dungeon_table_and_nothing_else(doc, open_water):
    # breaks if the dimension test is lost or the upstream entries are not inverted: the owner's tripwire hook comes back
    assert chosen(override(doc), {"dimension": POCKET, "open_water": open_water}) == {CFG["table"]: (1, 0)}


@pytest.mark.parametrize("dimension", ("minecraft:overworld", "minecraft:the_nether", "minecraft:the_end", "cobblers:other"))
@pytest.mark.parametrize("open_water", (False, True))
def test_a_cast_anywhere_else_rolls_exactly_the_upstream_entries(doc, dimension, open_water):
    # breaks if the override leaks out of the pocket: every angler on the server would lose the vanilla/Cobblemon treasure
    up = {e["value"]: (e["weight"], e.get("quality", 0)) for e in CFG["upstream"]["entries"]
          if all(holds(c, {"dimension": dimension, "open_water": open_water}) for c in e.get("conditions", []))}
    assert chosen(override(doc), {"dimension": dimension, "open_water": open_water}) == up
    if not open_water:
        assert up == {"minecraft:gameplay/fishing/junk": (66, -2)}, "upstream: only junk outside open water"
    else:
        assert set(up) == {"minecraft:gameplay/fishing/junk", "cobblemon:fishing/pokerod_treasure", "minecraft:gameplay/fishing/treasure"}


def test_the_dimension_tested_is_the_pockets_and_the_spawn_pool_is_boxed_to_the_same_one(doc):
    # the fishing spawn pool is boxed to engine.pocket.dimension; the loot override must name the very same dimension
    assert doc["engine"]["pocket"]["dimension"] == POCKET
    cond = DX.in_pocket(doc)
    assert cond == {"condition": "minecraft:location_check", "predicate": {"dimension": POCKET}}
    files = D.build(doc)
    pool = json.loads(files[DX.spawn_pool_path(doc["dungeons"][0])])
    assert all(e["condition"]["dimensions"] == [POCKET] for e in pool["spawns"])


def test_the_override_is_emitted_at_the_upstream_path_with_the_dungeon_table_beside_it(doc):
    files = D.build(doc)
    assert DX.POKEROD_PATH == "data/cobblemon/loot_table/fishing/pokerod.json"
    assert json.loads(files[DX.POKEROD_PATH]) == override(doc)
    assert json.loads(files["data/cobblers/loot_table/dungeons/fishing/treasure.json"]) == DX.item_table(doc)


def test_no_dungeon_without_a_fishing_room_overrides_the_table():
    # breaks if the override ships with a dungeon build that has nothing to fish: a global change with no reason
    d = TX.xdoc("mine", rooms=[r for r in TX.FIX if r["kind"] != "fishing_room"])
    assert DX.POKEROD_PATH not in D.build(d)


def test_the_upstream_copy_in_the_data_is_the_jars_table(doc):
    # the data stores the upstream entries verbatim; a Cobblemon update that changes them must fail here, not silently diverge
    for jar in (JAR, JAR_182):
        if not jar.is_file():
            pytest.skip("Cobblemon jar not on this machine: %s" % jar)
        t = upstream_table(jar)
        up = CFG["upstream"]
        assert t["type"] == up["type"] and t["random_sequence"] == up["random_sequence"], jar
        assert len(t["pools"]) == 1
        pool = t["pools"][0]
        assert (pool["rolls"], pool["bonus_rolls"]) == (up["rolls"], up["bonus_rolls"]), jar
        assert pool["entries"] == up["entries"], jar


def test_the_upstream_entries_survive_unchanged_but_for_the_one_added_condition(doc):
    base = CFG["upstream"]["entries"]
    got = override(doc)["pools"][0]["entries"][1:]
    assert len(got) == len(base)
    for g, b in zip(got, base):
        assert g["conditions"][0] == {"condition": "minecraft:inverted", "term": DX.in_pocket(doc)}
        rest = copy.deepcopy(g)
        rest["conditions"] = rest["conditions"][1:]
        if not rest["conditions"]:
            del rest["conditions"]
        assert rest == b


# ------------------------------------------------------------------------------------------------- the dungeon table


def test_the_dungeon_table_is_the_data_and_only_hits(doc):
    t = DX.item_table(doc)
    names = [e["name"] for e in t["pools"][0]["entries"]]
    assert names == [e["item"] for e in CFG["entries"]]
    junk = {"minecraft:tripwire_hook", "minecraft:string", "minecraft:stick", "minecraft:bone", "minecraft:rotten_flesh",
            "minecraft:bowl", "minecraft:leather", "minecraft:lily_pad", "minecraft:ink_sac", "minecraft:water_bottle",
            "minecraft:cod", "minecraft:salmon", "minecraft:pufferfish", "minecraft:tropical_fish"}
    assert not set(names) & junk
    # the owner's list: enchanted books, gold, balls
    assert "minecraft:book" in names and "minecraft:gold_ingot" in names and "cobblemon:poke_ball" in names
    book = next(e for e in t["pools"][0]["entries"] if e["name"] == "minecraft:book")
    assert book["functions"] == [{"function": "minecraft:enchant_with_levels", "levels": 30, "options": "#minecraft:on_random_loot"}]


def test_the_table_prices_against_the_greed_and_cash_tables_and_stays_proportionate():
    assert DX.item_problems(DX.load()) == []
    lo, hi = CFG["range_cp"]
    ev = DX.item_ev_cp()
    greed = json.loads((ROOT / "data" / "dungeon_greed.json").read_text(encoding="utf-8"))
    band_catch = greed["catches"]["cp_by_band"]["nest"]
    assert lo == min(band_catch) and hi >= max(band_catch), "the range is one catch at the bottom band to a bit over the top band"
    assert lo <= ev <= hi, ev


def test_nothing_in_the_table_sells_for_cash():
    bank = json.loads((ROOT / "data" / "bank.json").read_text(encoding="utf-8"))
    pb = json.loads((ROOT / "data" / "produce_buyer.json").read_text(encoding="utf-8"))
    items = {e["item"] for e in CFG["entries"]}
    assert not items & {b["item"] for b in bank["buys"]}
    assert not items & set(pb["specimens"]["items"])


def test_the_data_checks_bite():
    bad = copy.deepcopy(DX.load())
    bad["fishing"]["item_catches"]["entries"].append({"item": "cobblemon:dragon_scale", "count": [1, 1], "weight": 5, "cp_each": 10,
                                                      "cp_source": "proxy", "why": "x"})
    assert any("specimen" in p for p in DX.item_problems(bad))
    bad = copy.deepcopy(DX.load())
    bad["fishing"]["item_catches"]["entries"][0]["cp_each"] = 999
    assert any("not data/dungeon_greed.json" in p for p in DX.item_problems(bad))
    bad = copy.deepcopy(DX.load())
    bad["fishing"]["item_catches"]["entries"].append({"item": "minecraft:diamond", "count": [1, 1], "weight": 1000, "cp_each": 100, "cp_source": "greed"})
    assert any("cash" in p or "outside range_cp" in p for p in DX.item_problems(bad))


# ------------------------------------------------------------------------------------------------- mutation of the GENERATOR


@pytest.mark.parametrize("mutation", ("wrong_dimension", "no_inverse"))
def test_mutation_a_generator_that_leaks_or_misses_the_pocket_is_caught(doc, monkeypatch, mutation):
    """Change the generator, leave the data alone: the evaluator must disagree with the pocket/elsewhere contract."""
    if mutation == "wrong_dimension":
        monkeypatch.setattr(DX, "in_pocket", lambda d: {"condition": "minecraft:location_check", "predicate": {"dimension": "minecraft:overworld"}})
    else:
        real = DX.pokerod_override

        def no_inverse(d):
            t = real(d)
            for e in t["pools"][0]["entries"][1:]:
                e["conditions"] = e["conditions"][1:]
            return t
        monkeypatch.setattr(DX, "pokerod_override", no_inverse)
    t = DX.pokerod_override(doc)
    in_pocket = chosen(t, {"dimension": POCKET, "open_water": True})
    elsewhere = chosen(t, {"dimension": "minecraft:overworld", "open_water": False})
    ok = in_pocket == {CFG["table"]: (1, 0)} and elsewhere == {"minecraft:gameplay/fishing/junk": (66, -2)}
    assert not ok, "the mutation passed the contract"
