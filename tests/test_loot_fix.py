"""tools/loot_fix.py: every container we place is a Lootr container with a loot table that exists on the server.

Offline: the server's table list is injected, never read. Each test says what breaks without it.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import loot_fix as LF  # noqa: E402

PLAINS = "minecraft:chests/village/village_plains_house"
TEMPLE = "minecraft:chests/village/village_temple"
EXISTING = {PLAINS, TEMPLE, "minecraft:chests/village/village_toolsmith", "minecraft:chests/abandoned_mineshaft",
            "minecraft:chests/simple_dungeon", "minecraft:chests/ruined_portal", "minecraft:chests/village/village_shepherd",
            "minecraft:chests/village/village_cartographer"}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    """Inject the server's table list and no stage file; restore the module's caches after."""
    saved = dict(LF._cache)
    LF._cache.clear()
    LF._cache["tables"] = set(EXISTING)
    LF._cache["stages"] = {}
    monkeypatch.setattr(LF, "tier_at", lambda x, z: (1, "test"))
    yield
    LF._cache.clear()
    LF._cache.update(saved)


def template(blocks):
    """A loaded-template shape: palette plus blocks of (pos, name, properties, nbt)."""
    pal, out = [], []
    for pos, name, props, nbt in blocks:
        entry = {"Name": name, **({"Properties": props} if props else {})}
        if entry not in pal:
            pal.append(entry)
        out.append({"pos": list(pos), "state": pal.index(entry), **({"nbt": nbt} if nbt is not None else {})})
    return {"size": [8, 4, 8], "palette": pal, "blocks": out}


CHEST = {"facing": "north", "type": "single", "waterlogged": "false"}


def test_a_bad_table_round_trips_to_the_world_position_and_a_table_that_exists():
    # without this a rebuild brings back the red Lootr error: the placed position is wrong or the table still missing.
    # Expected position written by hand from Minecraft's clockwise_90 rule, (x, z) -> (-z, x), not from the tool.
    doc = template([((2, 1, 3), "minecraft:chest", CHEST, {"id": "minecraft:chest", "LootTable": "cobblemoncitytowns:pallet_town/chest_small"})])
    p = {"id": "t_house", "kind": "house", "pack_template": "x:house", "position": {"x": 100, "y": 70, "z": 200},
         "rotation": "clockwise_90", "mirror": "none"}
    (r,) = LF.donor_records(p, doc, "test")
    assert r["pos"] == [100 - 3, 71, 200 + 2]
    assert r["facing"] == "east"                     # north turned clockwise
    assert r["old_table"] == "cobblemoncitytowns:pallet_town/chest_small"
    assert r["new_table"] == PLAINS and r["new_table"] in EXISTING
    assert r["action"] == "fix_missing"
    cmd = LF.source_commands(r)
    assert cmd == ['setblock 97 71 202 lootr:lootr_chest[facing=east,type=single,waterlogged=false]{LootTable:"%s"}' % PLAINS]


def test_minecraft_empty_is_never_a_new_table():
    # Lootr rejects minecraft:empty as a missing table (the owner saw it 2026-10-21)
    doc = template([((0, 0, 0), "minecraft:chest", CHEST, {"id": "minecraft:chest", "LootTable": "minecraft:empty"})])
    (r,) = LF.donor_records({"id": "a", "kind": "house", "pack_template": "x:y", "position": {"x": 0, "y": 0, "z": 0}}, doc, "test")
    assert r["action"] == "fix_empty" and r["new_table"] != "minecraft:empty" and r["new_table"] in EXISTING


def test_an_empty_barrel_with_no_table_is_given_one_but_a_stocked_barrel_is_left():
    # a stocked container's authored items are the point of it; an empty one is decoration that can hold loot
    doc = template([((0, 0, 0), "minecraft:barrel", {"facing": "up", "open": "false"}, {"id": "minecraft:barrel", "Items": []}),
                    ((1, 0, 0), "minecraft:barrel", {"facing": "up", "open": "false"},
                     {"id": "minecraft:barrel", "Items": [{"id": "minecraft:bread", "count": 1, "Slot": 0}]})])
    a, b = LF.donor_records({"id": "a", "kind": "house", "pack_template": "x:y", "position": {"x": 0, "y": 5, "z": 0}}, doc, "test")
    assert a["action"] == "add_table" and a["lootr_block"] == "lootr:lootr_barrel" and a["new_table"] in EXISTING
    assert b["action"] == "skip_items" and LF.source_commands(b) == []


def test_a_valid_own_table_is_kept_until_stage_tables_exist_then_restaged():
    doc = template([((0, 0, 0), "minecraft:chest", CHEST, {"id": "minecraft:chest", "LootTable": PLAINS})])
    p = {"id": "a", "kind": "house", "pack_template": "x:y", "position": {"x": 0, "y": 0, "z": 0}}
    (r,) = LF.donor_records(p, doc, "test")
    assert r["action"] == "keep" and LF.source_commands(r) == []
    # the stage file lands: no code change, the container now names cobblers:chests/<stage>/<kind>
    LF._cache["stages"] = {"stage1": {"tiers": [1, 2], "kinds": {"house": {"rolls": 2, "entries": [{"item": "minecraft:bread", "weight": 1}]},
                                                                "other": {"rolls": 1, "entries": [{"item": "minecraft:bread"}]}}}}
    (r,) = LF.donor_records(p, doc, "test")
    assert r["action"] == "restage" and r["new_table"] == "cobblers:chests/stage1/house" and not r["placeholder"]
    assert r["new_table"] in LF.known_tables()


def test_a_stripped_container_gets_a_table_back():
    # place_town and clear_loot donors strip the template's table: the world holds an empty plain container
    doc = template([((0, 0, 0), "minecraft:chest", CHEST, {"id": "minecraft:chest", "LootTable": PLAINS})])
    (r,) = LF.donor_records({"id": "a", "kind": "house", "pack_template": "x:y", "clear_loot": True,
                             "position": {"x": 0, "y": 0, "z": 0}}, doc, "test")
    assert r["action"] == "restore_stripped" and LF.source_commands(r)


@pytest.mark.parametrize("rot,mirror,want", [("none", "none", "north"), ("clockwise_90", "none", "east"), ("180", "none", "south"),
                                             ("counterclockwise_90", "none", "west"), ("none", "left_right", "south"),
                                             ("none", "front_back", "north"), ("clockwise_90", "left_right", "west")])
def test_facing_turns_as_the_template_does(rot, mirror, want):
    # mirror first (left_right negates z), then the rotation: the order place_donor.transform uses
    assert LF.turn_facing("north", rot, mirror) == want


def test_a_double_chest_keeps_its_halves_and_a_mirror_swaps_them():
    doc = template([((0, 0, 0), "minecraft:chest", {"facing": "south", "type": "left", "waterlogged": "false"},
                     {"id": "minecraft:chest", "LootTable": "gone:x"})])
    p = {"id": "a", "kind": "house", "pack_template": "x:y", "position": {"x": 0, "y": 0, "z": 0}, "mirror": "front_back"}
    (r,) = LF.donor_records(p, doc, "test")
    assert r["properties"]["type"] == "right"


def test_other_containers_have_their_own_lootr_blocks():
    assert LF.container_block("minecraft:trapped_chest") == "lootr:lootr_trapped_chest"
    assert LF.container_block("minecraft:red_shulker_box") == "lootr:lootr_shulker"
    assert LF.container_block("sophisticatedstorage:barrel") is None       # Lootr has no block for it
    assert LF.container_block("minecraft:furnace") is None


def test_kind_rules_do_not_read_minecraft_as_mine():
    # "minecraft:chests/..." contains "mine": the rule must not make every house a mine
    assert LF.kind_of({"id": "h", "kind": "house"}, "repurposed_structures:villages/plains/houses/small_house_1", PLAINS) == "house"
    assert LF.kind_of({"id": "m", "kind": "donor"}, "bca:default/structures/the_miners_den", None) == "mine"
    assert LF.kind_of({"id": "legendary_zapdos_tower", "kind": "donor"}, "cobbleverse:legendary/zapdos", None) == "legendary_site"


def test_the_legendary_site_never_gets_a_table_that_can_give_a_gate_item(monkeypatch):
    # the owner, 2026-10-21: no feather, summon item or key in an instanced chest at a legendary site
    monkeypatch.setattr(LF, "table_text", lambda t: '{"name": "lumymon:thunder_feather"}' if t == TEMPLE else "{}")
    doc = template([((0, 0, 0), "minecraft:chest", CHEST, {"id": "minecraft:chest", "LootTable": TEMPLE})])
    (r,) = LF.donor_records({"id": "legendary_x", "kind": "donor", "pack_template": "x:y", "position": {"x": 0, "y": 0, "z": 0}}, doc, "test")
    assert r["kind"] == "legendary_site" and r["action"] == "replace_gate_table" and r["new_table"] != TEMPLE
    assert any("gate item" in b for b in LF.problems([dict(r, new_table=TEMPLE, action="fix_missing")]))


def test_the_commands_are_guarded_and_grouped_by_area(tmp_path):
    doc = template([((0, 0, 0), "minecraft:chest", CHEST, {"id": "minecraft:chest", "LootTable": "gone:x"}),
                    ((40, 0, 0), "minecraft:chest", CHEST, {"id": "minecraft:chest", "LootTable": "gone:x"})])
    recs = LF.donor_records({"id": "a", "kind": "house", "pack_template": "x:y", "position": {"x": 0, "y": 5, "z": 0}}, doc, "test")
    out = tmp_path / "c.txt"
    areas, n = LF.write_commands({"containers": recs}, out, area=2)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert n == 2 and areas == 2                      # 40 blocks is a different 32-block area
    assert sum(l.startswith("forceload add") for l in lines) == 2 and sum(l.startswith("forceload remove") for l in lines) == 2
    # guarded: a wrong Y must place nothing
    assert sum(l.startswith("execute if block") for l in lines) == 4
    assert not any(l.startswith("setblock") for l in lines)


def test_the_sigil_in_a_stage_table_is_the_dungeon_engine_item_not_a_lookalike():
    # without this a table could hand out a sherd the rip does not accept: the match is custom_data cobblers_dg_sigil:<band>b
    import dungeon
    ddoc = dungeon.load()
    x = next(s for s in dungeon.sigils(ddoc) if s["band"] == 2)
    stage = {"tiers": [1], "sigil": {"band": 2, "chance": 0.5}, "kinds": {"house": {"rolls": 1, "entries": [{"item": "minecraft:bread"}]}}}
    table = LF.table_json("stage1", stage, "house", stage["kinds"]["house"])
    pool = table["pools"][-1]
    entry = pool["entries"][0]
    assert entry["name"] == x["item"] == "minecraft:prize_pottery_sherd"
    comps = entry["functions"][0]["components"]
    assert comps["minecraft:custom_data"] == {ddoc["engine"]["sigils"]["custom_data_key"]: 2}
    assert comps == dungeon.sigil_recipe(x, ddoc)["result"]["components"]
    assert pool["conditions"][0]["chance"] == 0.5


def test_stage_tables_are_written_where_the_stage_file_says(tmp_path):
    LF._cache["stages"] = {"s1": {"kinds": {"house": {"rolls": [1, 2], "entries": [{"item": "minecraft:bread", "weight": 3, "count": [1, 4]}]}}}}
    assert LF.write_tables(tmp_path) == 1
    t = json.loads((tmp_path / "data/cobblers/loot_table/chests/s1/house.json").read_text(encoding="utf-8"))
    assert t["type"] == "minecraft:chest" and t["pools"][0]["rolls"] == {"type": "minecraft:uniform", "min": 1, "max": 2}
    assert t["pools"][0]["entries"][0]["functions"][0]["count"] == {"type": "minecraft:uniform", "min": 1, "max": 4}


# ---- the committed data


FIXES = ROOT / "data" / "loot_fixes.json"


@pytest.mark.skipif(not FIXES.is_file(), reason="data/loot_fixes.json not generated")
def test_the_committed_fixes_have_no_duplicate_position_and_never_minecraft_empty():
    doc = json.loads(FIXES.read_text(encoding="utf-8"))
    recs = doc["containers"]
    assert len({tuple(r["pos"]) for r in recs}) == len(recs)
    for r in recs:
        assert r["new_table"] != "minecraft:empty"
        if r["action"] not in ("keep", "skip_items"):
            assert r["new_table"] and r["lootr_block"].startswith("lootr:")
    # every record's stage and kind are ones the remap defines
    kinds = set(json.loads((ROOT / "data" / "loot_remap.json").read_text(encoding="utf-8"))["placeholder_by_kind"])
    assert {r["kind"] for r in recs} <= kinds


@pytest.mark.skipif(not FIXES.is_file(), reason="data/loot_fixes.json not generated")
def test_pallets_eight_known_chests_are_in_the_fixes_at_the_positions_seen_live():
    # positions read off the live world by the owner's fix (docs/STATE.md, donor chests): independent of this tool
    seen = [(1491, 118, 5311), (1492, 118, 5311), (1491, 122, 5318), (1416, 116, 5281), (1432, 117, 5280),
            (1427, 117, 5301), (1427, 117, 5302), (1447, 117, 5311)]
    have = {tuple(r["pos"]): r for r in json.loads(FIXES.read_text(encoding="utf-8"))["containers"]}
    for pos in seen:
        assert pos in have, pos
        assert have[pos]["old_table"].startswith("cobblemoncitytowns:")


LAB = ROOT / "kits" / "structures" / "campaign" / "f4" / "pallet" / "rare_structures" / "lab.nbt"


@pytest.mark.skipif(not LAB.is_file(), reason="kits not hydrated")
def test_place_town_reads_the_labs_three_containers_with_the_missing_table():
    # the placers own template reader sees the three chests the owner hit; without it the source fix never runs for them
    import place_town
    cs = place_town.template_info(LAB)["containers"]
    assert len(cs) == 3 and {c["table"] for c in cs} == {"cobblemoncitytowns:pallet_town/chest_lab"}
