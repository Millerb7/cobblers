"""tools/location_titles.py and the shared name list (tools/signposts.place_names).

Written in the same session as the tool: the titles themselves are not verified in game (they need a player to walk
in); these tests hold the data and the pack's shape.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import location_titles as LT  # noqa: E402
import signposts  # noqa: E402


def test_every_titled_place_has_a_name_and_a_box():
    # A settlement with no name would title as nothing, or the build would stop: the owner's rule is that every
    # settlement has at least its working name in data/signposts.json until a display name lands.
    sets = LT.settlements(LT.regions())
    zs = LT.zones()
    assert len(zs) == sum(1 for z in zone_doc()["zones"] if z["kind"] != "site")
    assert not [s["id"] for s in sets if not s["name"] or not s["box"]]
    assert not [z["zone"] for z in zs if not z["name"] or not z["subtitle"] or not z["boxes"]]


def test_titles_cover_settlements_not_landmark_trees():
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    ids = {s["id"] for s in LT.settlements(LT.regions())}
    for t in towns:
        assert (t["id"] in ids) == (t.get("kind") != "landmark_tree"), t["id"]
    assert "route1_mansion" in ids


def test_a_display_name_wins_over_the_working_name(monkeypatch):
    # Signs and titles must change together when the owner names a town.
    real = signposts.load

    def fake(name):
        d = real(name)
        if name == "towns.json":
            d = json.loads(json.dumps(d))
            next(t for t in d["towns"] if t["id"] == "gym1_town")["display_name"] = "Pewter Test"
            # a town with no display name falls back to its working name (the hometown has a real display name
            # since 2026-09-27, so the fallback is exercised by clearing it here rather than relying on the data)
            next(t for t in d["towns"] if t["id"] == "hometown")["display_name"] = None
        return d
    monkeypatch.setattr(signposts, "load", fake)
    assert signposts.place_names()["gym1_town"] == "Pewter Test"
    assert signposts.place_names()["hometown"] == "Pallet"


def test_the_displaced_city_titles_in_its_cavern_not_on_the_summit():
    # Its towns.json footprint is the old surface site; the city is in the cavern, and the summit over it is not in it.
    s = next(s for s in LT.settlements(LT.regions()) if s["id"] == "displaced_city")
    plan = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]["displaced_city"]["plan"]
    assert list(s["box"]) == plan["footprint"]["rect"]
    assert s["y"] and s["y"][1] < 115


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("titles") / "pack"
    LT.build(out)
    return out


def zone_doc():
    return json.loads((ROOT / "data" / "nuzlocke_zones.json").read_text(encoding="utf-8"))


def test_the_pack_titles_exactly_the_catch_zones_and_the_settlements(pack):
    # The owner, 2026-10-06: the titles fire for the Nuzlocke zones' boundaries (and settlements), not the regions.
    adv = pack / "data" / "cobblers" / "advancement" / "titles"
    ins = {p.name[3:-5] for p in adv.glob("in_*.json")}
    zones = {"zone_" + z["zone"] for z in zone_doc()["zones"] if z["kind"] != "site"}
    places = {"place_" + s["id"] for s in LT.settlements(LT.regions())}
    assert ins == zones | places
    assert not [k for k in ins if k.startswith("region_")]
    # a site zone is titled by its settlement
    for z in zone_doc()["zones"]:
        if z["kind"] == "site":
            assert "place_" + z["settlement"] in ins


def test_the_pack_pairs_every_enter_with_a_leave(pack):
    adv = pack / "data" / "cobblers" / "advancement" / "titles"
    fn = pack / "data" / "cobblers" / "function" / "titles"
    ins = sorted(p.name[3:-5] for p in adv.glob("in_*.json"))
    outs = sorted(p.name[4:-5] for p in adv.glob("out_*.json"))
    assert ins == outs
    rearm = (fn / "rearm_places.mcfunction").read_text(encoding="utf-8")
    for key in ins:
        enter = (fn / ("enter_%s.mcfunction" % key)).read_text(encoding="utf-8")
        leave = (fn / ("leave_%s.mcfunction" % key)).read_text(encoding="utf-8")
        # entering arms the leave, leaving re-arms the enter: without both a title shows once per life
        assert "advancement revoke @s only cobblers:titles/out_%s" % key in enter
        assert leave.strip().splitlines()[-1] == "advancement revoke @s only cobblers:titles/in_%s" % key
        assert "advancement revoke @s only cobblers:titles/in_%s\n" % key in rearm
        a = json.loads((adv / ("in_%s.json" % key)).read_text(encoding="utf-8"))
        assert "display" not in a                    # hidden: no toast, nothing in the advancement screen
        assert a["rewards"]["function"] == "cobblers:titles/enter_%s" % key
        o = json.loads((adv / ("out_%s.json" % key)).read_text(encoding="utf-8"))
        assert o["criteria"]["here"]["conditions"]["player"][1]["condition"] == "minecraft:inverted"


def test_zone_titles_give_way_to_a_settlement_and_come_back_after_it(pack):
    fn = pack / "data" / "cobblers" / "function" / "titles"
    text = (fn / "enter_zone_pallet_meadows.mcfunction").read_text(encoding="utf-8")
    first_title = next(i for i, l in enumerate(text.splitlines()) if "title @s" in l)
    guard = next(i for i, l in enumerate(text.splitlines()) if "in_enclosure" in l)
    assert guard < first_title
    # retry, not hold: the zone's own in_ is revoked inside a settlement, so it titles on stepping out
    assert text.splitlines()[guard].endswith("return run advancement revoke @s only cobblers:titles/in_zone_pallet_meadows")


def test_the_pack_loads_and_ticks_through_the_1_21_folders(pack):
    tags = pack / "data" / "minecraft" / "tags" / "function"
    assert json.loads((tags / "load.json").read_text(encoding="utf-8"))["values"] == ["cobblers:titles/load"]
    assert json.loads((tags / "tick.json").read_text(encoding="utf-8"))["values"] == ["cobblers:titles/tick"]
    assert json.loads((pack / "pack.mcmeta").read_text(encoding="utf-8"))["pack"]["pack_format"] == 48
    load = (pack / "data" / "cobblers" / "function" / "titles" / "load.mcfunction").read_text(encoding="utf-8")
    assert "scoreboard objectives add cob_t_left minecraft.custom:minecraft.leave_game" in load


def test_leaving_needs_distance_past_the_edge():
    # Hysteresis: the leave box is the enter box grown, so walking a border does not re-title at every step.
    tight = LT._inside([(0, 0, 9, 9, None, None)])
    loose = LT._inside([(0, 0, 9, 9, None, None)], grow=16)
    assert loose["predicate"]["location"]["position"]["x"]["min"] == tight["predicate"]["location"]["position"]["x"]["min"] - 16
