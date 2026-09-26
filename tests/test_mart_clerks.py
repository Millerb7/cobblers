"""Mart clerks (data/traders.json stock "mart") against the placed Marts, their templates and the stock policy.

Written by the test author, not by the session that added the clerks to data/traders.json and tools/traders.py.

What is asserted: every Mart building a town placement report places (derived/towns/*_placement.json, a building id
ending "pokemart") has exactly one mart trader, and every mart trader names such a building in its own settlement; the
clerk stands on the template's shopkeeper jigsaw (cobblemoncitytowns:shopkeeper_main, or
cobblemoncitytowns:pokemart_shopkeeper_spawner in structure_pokemart), read here from the template NBT and carried
through the report's command_position and rotation with tools/place_town.rotate, one block up, and the two cells it
stands in are air in the template; a clerk faces its building's facing; apply_stock_policy keeps exactly the Mart
items for "mart" and still withholds for "regional"; static_problems flags a bad facing and an unknown stock;
town_functions names a clerk "Poke Mart" (the policy's name) and turns it with the vanilla yaw for its facing; the
function mode refuses a Mart whose template lacks a Mart item, and writes one whose template has them all; the Mart
items are Cobblemon 1.8.0 items.

derived/ and build/ are gitignored and disposable: without the placement reports or the built town templates the
position tests SKIP, and a skip is not a pass. The Cobblemon jar is read from the EXP-000 runtime copy
(tools/battle_sim.JAR_CANDIDATES) or $COBBLERS_COBBLEMON_JAR, never from the live server tree (CLAUDE.md, live
server safety); without one that test SKIPs.

Not covered, and it needs a running server: that the summoned clerk stands behind the counter and does not fall
(the floor under it is the jigsaw's final_state), that the shop screen opens with three offers, that the name and
rotation render, and that `verify --rcon` reads the Mart stock back.
"""
from __future__ import annotations

import copy
import glob
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import nbt  # noqa: E402
import place_town  # noqa: E402
import traders as TR  # noqa: E402
from test_structure_inventory import nbt_bytes  # noqa: E402

DOC = json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))
POLICY = DOC["stock_policy"]
MARTS = [t for t in DOC["traders"] if t.get("stock") == "mart"]
MART_ITEMS = {"cobblemon:poke_ball", "cobblemon:potion", "cobblemon:antidote"}   # the owner's decision, 2026-09-25
SHOPKEEPER = {"cobblemoncitytowns:shopkeeper_main", "cobblemoncitytowns:pokemart_shopkeeper_spawner"}
TOWNS = ROOT / "derived" / "towns"
BUILT = ROOT / "build" / "datapacks" / "cobblers_towns"
# Minecraft's entity yaw: 0 looks south (+z), 90 west, 180 north, -90 east
VANILLA_YAW = {"south": 0.0, "west": 90.0, "north": 180.0, "east": -90.0}


def _marts_placed():
    """{building id: (settlement, building record)} for every Mart a placement report places."""
    reports = sorted(TOWNS.glob("*_placement.json"))
    if not reports:
        pytest.skip("no derived/towns/*_placement.json: run tools/place_town.py (derived/ is gitignored)")
    out = {}
    for f in reports:
        town = f.name[:-len("_placement.json")]
        for b in json.loads(f.read_text(encoding="utf-8")).get("buildings") or []:
            if b["id"].endswith("pokemart"):
                out[b["id"]] = (town, b)
    return out


def _template_path(template_id):
    ns, rel = template_id.split(":", 1)
    built = BUILT / "data" / ns / "structure" / (rel + ".nbt")
    if built.is_file():
        return built
    if not BUILT.is_dir():
        pytest.skip("no build/datapacks/cobblers_towns (python tools/place_town.py writes it); the template is read "
                    "from the pack that places it")
    pytest.fail("%s is placed by the towns pack but %s does not hold it" % (template_id, built))


def _shopkeeper_cells(template_id):
    """[(pos, name)] of shopkeeper jigsaws, and {pos: block name} of the template."""
    _, doc = nbt.load(_template_path(template_id))
    pal = doc["palette"]
    at = {tuple(b["pos"]): pal[b["state"]]["Name"] for b in doc["blocks"]}
    jig = [(tuple(b["pos"]), (b.get("nbt") or {}).get("name")) for b in doc["blocks"]
           if pal[b["state"]]["Name"] == "minecraft:jigsaw" and (b.get("nbt") or {}).get("name") in SHOPKEEPER]
    return jig, at


# Without it the manifest could shrink to nothing and every per-clerk check below would pass on an empty list.
# Updated 2026-09-26: the count was hard-coded 13; the sea town added a fourteenth Mart (sea_town_mart in
# data/traders.json, sea_town_pokemart in its placement). The expectation now comes from the placement reports, an
# independent source (a town's layout, not the traders manifest), so a new town's Mart does not need this edited.
def test_the_manifest_has_one_mart_clerk_per_placed_mart_and_the_policy_names_the_three_items():
    placed = _marts_placed()
    # a floor, not the expectation: the reports themselves must not shrink (14 placed Marts on 2026-09-26)
    assert len(placed) >= 14, "the placement reports place fewer Marts than before: %s" % sorted(placed)
    assert len(MARTS) == len(placed), (len(MARTS), sorted(placed))
    assert set(POLICY["mart"]["items"]) == MART_ITEMS
    assert POLICY["mart"]["name"] == "Poké Mart"


# Without it a placed Mart has no clerk (a shop that sells nothing), two clerks, or a clerk stands in a building that
# no town places (summoned into thin air or someone's house).
def test_every_placed_mart_has_exactly_one_clerk_and_every_clerk_has_a_placed_mart():
    placed = _marts_placed()
    assert placed, "no Mart in any placement report"
    by_building = {}
    for t in MARTS:
        by_building.setdefault(t.get("building"), []).append(t["id"])
    doubled = {b: ids for b, ids in by_building.items() if len(ids) > 1}
    assert not doubled, doubled
    assert set(placed) - set(by_building) == set(), "placed Marts with no clerk"
    assert set(by_building) - set(placed) == set(), "clerks in buildings no placement report places"
    for t in MARTS:
        assert placed[t["building"]][0] == t["settlement"], (t["id"], placed[t["building"]][0], t["settlement"])


# Without it a clerk is summoned inside a wall, behind the wrong counter, or a block above the floor (the placement
# rotated or moved the building and the manifest kept the old spot).
@pytest.mark.parametrize("rec", MARTS, ids=[t["id"] for t in MARTS])
def test_a_clerk_stands_on_its_templates_shopkeeper_jigsaw_as_placed(rec):
    placed = _marts_placed()
    if rec["building"] not in placed:
        pytest.fail("%s names %s, which no placement report places" % (rec["id"], rec["building"]))
    _town, b = placed[rec["building"]]
    jig, at = _shopkeeper_cells(b["template_placed"])
    assert len(jig) == 1, "%s: want one shopkeeper jigsaw, found %s" % (b["template_placed"], jig)
    (tx, ty, tz), _name = jig[0]
    px, oy, pz = b["command_position"]
    rx, rz = place_town.rotate(tx, tz, b["rotation"])
    want = {"x": px + rx, "y": oy + ty + 1, "z": pz + rz}
    assert rec["position"] == want, (rec["id"], rec["position"], want)
    # the clerk's feet and head cells: air in the template, so the summon is not inside a counter or a shelf
    for dy in (1, 2):
        assert at.get((tx, ty + dy, tz)) == "minecraft:air", (rec["id"], dy, at.get((tx, ty + dy, tz)))


# Without it a NoAI clerk stares at a side wall or away from the door (it never turns its head on its own).
@pytest.mark.parametrize("rec", MARTS, ids=[t["id"] for t in MARTS])
def test_a_clerk_faces_the_way_its_building_faces(rec):
    placed = _marts_placed()
    assert rec.get("facing") == placed[rec["building"]][1]["facing"], rec["id"]


# ------------------------------------------------------------------------------------------------ the stock policy

def _shop():
    ball_cat = POLICY["withhold_categories"][0]           # the policy's own spelling of the balls category
    return {"CobbleMerchantShop": [
        {"Category": ball_cat, "Offers": [{"Item": {"id": i, "count": 1}, "Price": "200"}
                                          for i in ("cobblemon:poke_ball", "cobblemon:great_ball", "cobblemon:ultra_ball")]},
        {"Category": "Medicine", "Offers": [{"Item": {"id": i, "count": 1}, "Price": "100"}
                                            for i in ("cobblemon:potion", "cobblemon:super_potion", "cobblemon:antidote",
                                                      "cobblemon:full_heal")]},
        {"Category": "Herbs", "Offers": [{"Item": {"id": i, "count": 1}, "Price": "50"}
                                         for i in ("cobblemon:medicinal_leek", "cobblemon:revival_herb")]}]}


def _offered(data):
    return {o["Item"]["id"] for c in data["CobbleMerchantShop"] for o in c["Offers"]}


# Without it a Mart sells whatever the template stocked (ultra balls and full heals in the first town), or loses one of
# its three basic items.
def test_a_mart_keeps_exactly_the_three_basic_items_whatever_else_the_template_sells():
    data, kept, held = TR.apply_stock_policy(_shop(), POLICY, "mart")
    assert set(kept) == MART_ITEMS and _offered(data) == MART_ITEMS
    assert set(held) == {"cobblemon:great_ball", "cobblemon:ultra_ball", "cobblemon:super_potion",
                         "cobblemon:full_heal", "cobblemon:medicinal_leek", "cobblemon:revival_herb"}
    assert "Herbs" not in [c["Category"] for c in data["CobbleMerchantShop"]], "a category left empty must be dropped"


# Without it the Mart exception leaks into the regional traders: a plaza stall selling Poke Balls again.
def test_a_regional_trader_still_withholds_under_the_same_policy():
    data, kept, held = TR.apply_stock_policy(_shop(), POLICY, "regional")
    assert "cobblemon:poke_ball" in held and "cobblemon:revival_herb" in held
    assert "cobblemon:medicinal_leek" in kept
    assert not _offered(data) & {"cobblemon:poke_ball", "cobblemon:great_ball", "cobblemon:ultra_ball"}


# Without it a typo in facing reaches YAW[...] as a KeyError at function time, or an unknown stock is summoned as if
# it were regional.
def test_static_rules_flag_a_bad_facing_and_an_unknown_stock():
    good = copy.deepcopy(MARTS[0])
    doc = {"stock_policy": POLICY, "traders": [
        good,
        dict(copy.deepcopy(good), id="x_bad_facing", facing="up", position={"x": 1, "y": 2, "z": 3}),
        dict(copy.deepcopy(good), id="x_bad_stock", stock="bargain", position={"x": 4, "y": 5, "z": 6})]}
    probs = TR.static_problems(doc)
    assert [m for rid, m in probs if rid == good["id"]] == []
    assert any(rid == "x_bad_facing" and "facing" in m for rid, m in probs), probs
    assert any(rid == "x_bad_stock" and "stock must be one of" in m for rid, m in probs), probs


# Without it a Mart is authored while the policy lists no Mart items, and the clerk is summoned with an empty shop.
def test_static_rules_flag_a_mart_without_mart_items_in_the_policy():
    doc = {"stock_policy": {k: v for k, v in POLICY.items() if k != "mart"}, "traders": [copy.deepcopy(MARTS[0])]}
    assert any("stock_policy.mart" in m for _, m in TR.static_problems(doc))


def _summon(lines):
    s = [l for l in lines if l.startswith("summon ")]
    assert len(s) == 1, lines
    return s[0]


# Without it a clerk is summoned under the template's name and with no rotation: it faces south whatever its door.
@pytest.mark.parametrize("facing", sorted(VANILLA_YAW))
def test_a_mart_clerk_is_named_for_the_shop_and_turned_to_its_facing(facing):
    rec = dict(copy.deepcopy(MARTS[0]), facing=facing)
    shop = _shop()
    shop["CustomName"] = json.dumps({"text": "General Shopkeeper"})
    f = TR.town_functions(rec["settlement"], [rec], lambda _t: ("cobbledollars:cobble_merchant", copy.deepcopy(shop)),
                          POLICY)
    line = _summon(f["vendors_%s_place" % rec["settlement"]])
    assert "Rotation:[%sf,0.0f]" % VANILLA_YAW[facing] in line, line
    assert TR.to_snbt(json.dumps({"text": "Poké Mart"}, ensure_ascii=False)) in line
    # a copy under the template's name, left by structure placement, is still removed
    assert any('name="General Shopkeeper"' in l for l in f["vendors_%s_done" % rec["settlement"]])


def _server(tmp_path, items):
    tpl = {"size": [1, 2, 1], "palette": [{"Name": "minecraft:air"}], "blocks": [],
           "entities": [{"pos": [0, 0, 0], "blockPos": [0, 0, 0], "nbt": {
               "id": "cobbledollars:cobble_merchant", "CustomName": json.dumps({"text": "General Shopkeeper"}),
               "CobbleMerchantShop": [{"Category": "Medicine", "Offers": [
                   {"Item": {"id": i, "count": 1}, "Price": "100"} for i in items]}]}}]}
    server = tmp_path / "server"
    (server / "datapacks").mkdir(parents=True)
    with zipfile.ZipFile(server / "datapacks" / "shops.zip", "w") as z:
        z.writestr("data/testshop/structure/clerk.nbt", nbt_bytes(tpl))
    manifest = tmp_path / "traders.json"
    rec = dict(copy.deepcopy(MARTS[0]), template="testshop:clerk")
    manifest.write_text(json.dumps({"stock_policy": POLICY, "traders": [rec]}), encoding="utf-8")
    return server, manifest, rec


# Without it a Mart is written from a template that cannot sell one of the basic items, and the town's only shop
# quietly lacks Poke Balls.
def test_the_function_mode_refuses_a_mart_whose_template_lacks_a_mart_item(tmp_path):
    server, manifest, rec = _server(tmp_path, ["cobblemon:poke_ball", "cobblemon:potion"])
    with pytest.raises(SystemExit) as e:
        TR.main(["--manifest", str(manifest), "function", "--server-dir", str(server), "--out", str(tmp_path / "out")])
    assert "cobblemon:antidote" in str(e.value) and rec["id"] in str(e.value)
    assert not list((tmp_path / "out").rglob("*.mcfunction"))


# The positive control for the refusal: without it the refusal test would also pass if every Mart were refused.
def test_the_function_mode_writes_a_mart_whose_template_sells_all_three(tmp_path):
    server, manifest, rec = _server(tmp_path, sorted(MART_ITEMS) + ["cobblemon:full_heal"])
    assert TR.main(["--manifest", str(manifest), "function", "--server-dir", str(server),
                    "--out", str(tmp_path / "out")]) == 0
    fn = tmp_path / "out" / "data" / "cobblers" / "function" / "towns" / ("vendors_%s_place.mcfunction" % rec["settlement"])
    line = _summon(fn.read_text(encoding="utf-8").splitlines())
    assert all(i in line for i in MART_ITEMS) and "cobblemon:full_heal" not in line


def _cobblemon_jar():
    import battle_sim
    cands = ([Path(os.environ["COBBLERS_COBBLEMON_JAR"])] if os.environ.get("COBBLERS_COBBLEMON_JAR") else []) \
        + list(battle_sim.JAR_CANDIDATES)
    for c in cands:
        if c.is_file():
            return c
    pytest.skip("no Cobblemon-fabric-1.8.0 jar outside the live server (EXP-000 runtime copy or $COBBLERS_COBBLEMON_JAR)")


# Without it a Mart item id is misspelled (cobblemon:pokeball) and the clerk's shop offers an item that does not exist.
def test_the_mart_items_are_cobblemon_items():
    names = set(zipfile.ZipFile(_cobblemon_jar()).namelist())
    missing = [i for i in sorted(MART_ITEMS) if "assets/cobblemon/models/item/%s.json" % i.split(":")[1] not in names]
    assert not missing, missing
