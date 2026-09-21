"""tools/location_titles.py and the shared name list (tools/signposts.place_names).

Written in the same session as the tool: the titles themselves are not verified in game (they need a player to walk
in); these tests hold the data and the pack's shape.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import location_titles as LT  # noqa: E402
import signposts  # noqa: E402


def test_every_titled_place_has_a_name_and_a_box():
    # A settlement with no name would title as nothing, or the build would stop: the owner's rule is that every
    # settlement has at least its working name in data/signposts.json until a display name lands.
    regs = LT.regions()
    sets = LT.settlements(regs)
    assert len(regs) == 21
    assert not [s["id"] for s in sets if not s["name"] or not s["box"]]
    assert not [r["id"] for r in regs if not r["name"] or not r["boxes"]]


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


def test_the_pack_pairs_every_enter_with_a_leave(tmp_path):
    LT.build(tmp_path / "pack")
    adv = tmp_path / "pack" / "data" / "cobblers" / "advancement" / "titles"
    fn = tmp_path / "pack" / "data" / "cobblers" / "function" / "titles"
    ins = sorted(p.name[3:] for p in adv.glob("in_*.json"))
    outs = sorted(p.name[4:] for p in adv.glob("out_*.json"))
    assert ins == outs and len(ins) == 21 + len(LT.settlements(LT.regions()))
    for key in ins:
        key = key[:-5]
        enter = (fn / ("enter_%s.mcfunction" % key)).read_text(encoding="utf-8")
        leave = (fn / ("leave_%s.mcfunction" % key)).read_text(encoding="utf-8")
        # entering arms the leave, leaving re-arms the enter: without both a title shows once per life
        assert "advancement revoke @s only cobblers:titles/out_%s" % key in enter
        assert leave.strip() == "advancement revoke @s only cobblers:titles/in_%s" % key
        a = json.loads((adv / ("in_%s.json" % key)).read_text(encoding="utf-8"))
        assert "display" not in a                    # hidden: no toast, nothing in the advancement screen
        assert a["rewards"]["function"] == "cobblers:titles/enter_%s" % key
        o = json.loads((adv / ("out_%s.json" % key)).read_text(encoding="utf-8"))
        assert o["criteria"]["here"]["conditions"]["player"][1]["condition"] == "minecraft:inverted"


def test_region_titles_give_way_to_a_settlement(tmp_path):
    LT.build(tmp_path / "pack")
    fn = tmp_path / "pack" / "data" / "cobblers" / "function" / "titles"
    text = (fn / "enter_region_pallet_fields.mcfunction").read_text(encoding="utf-8")
    title_lines = [l for l in text.splitlines() if l.lstrip().startswith(("title", "execute")) and "title @s" in l]
    assert title_lines and all("unless predicate cobblers:titles/in_any_settlement" in l for l in title_lines)
    assert (tmp_path / "pack" / "data" / "cobblers" / "predicate" / "titles" / "in_any_settlement.json").is_file()


def test_leaving_needs_distance_past_the_edge():
    # Hysteresis: the leave box is the enter box grown, so walking a border does not re-title at every step.
    tight = LT._inside([(0, 0, 9, 9)])
    loose = LT._inside([(0, 0, 9, 9)], grow=16)
    assert loose["predicate"]["location"]["position"]["x"]["min"] == tight["predicate"]["location"]["position"]["x"]["min"] - 16
