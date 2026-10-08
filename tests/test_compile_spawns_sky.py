"""tools/compile_spawns.py: which compiled spawn conditions require canSeeSky.

Written by the test author, not by the session that wrote the compiler or its canSeeSky fix.

Independent source: the owner's in-game finding on staging, 2026-09-26 (commit ad48221's message and marine_condition's
docstring): Cobblemon 1.8.0 records a column's sky flag once, at the top of the spawning zone, so under a deep lake it
reads false and a forced canSeeSky empties every submerged and seafloor entry (/checkspawn on the floor of Lake Viltri
and Shrew Lake found nothing). Entries that stand on land or on the surface keep canSeeSky, which is what keeps land
rosters out of caves.

The fix (ad48221, PR #61) is merged, so the submerged/seafloor cases are ordinary tests; they were strict xfails while
the fix was on its own branch.

Not covered, and it needs a running server: whether a submerged entry without canSeeSky now spawns under a deep lake,
and whether a cave pool of water under land picks up lake rosters it should not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_spawns as CS  # noqa: E402

UNDERWATER = ("submerged", "seafloor")
IN_THE_OPEN = ("grounded", "surface")


def _entry(position, **kw):
    e = {"species": "magikarp", "bucket": "common", "level": "5-10", "weight": 10.0, "spawnable_position": position}
    e.update(kw)
    return e


# Without it a land or surface roster loses canSeeSky and spawns in caves under its box.
@pytest.mark.parametrize("position", IN_THE_OPEN)
def test_land_and_surface_box_entries_require_the_sky(position):
    cond = CS.box_condition(0, 31, 0, 31, _entry(position, biomes=["#minecraft:is_river"]))
    assert cond["canSeeSky"] is True, cond
    assert (cond["minX"], cond["maxX"], cond["minZ"], cond["maxZ"]) == (0, 31, 0, 31)
    assert cond["biomes"] == ["#minecraft:is_river"]
    # an entry authored with no spawnable_position is grounded, and grounded keeps the sky
    e = _entry(position)
    del e["spawnable_position"]
    assert CS.box_condition(0, 31, 0, 31, e)["canSeeSky"] is True


# Without it every submerged and seafloor entry in a lake, river, route or sub-region box is emptied by a sky test that
# reads false under deep water.
@pytest.mark.parametrize("position", UNDERWATER)
def test_submerged_and_seafloor_box_entries_do_not_require_the_sky(position):
    cond = CS.box_condition(0, 31, 0, 31, _entry(position, biomes=["#minecraft:is_river"]))
    assert "canSeeSky" not in cond, cond


# ------------------------------------------------------------------------------------- off the overworld (N154)
# Under the Nether's roof no column sees the sky, so a forced canSeeSky empties every grounded Nether entry. The
# dimension is the entry's own conditions.dimensions, the Cobblemon 1.8.0 SpawningCondition field
# (docs/research/notes/spawn-dimension-condition-1.8.0.md).

NETHER = "minecraft:the_nether"


# Without it every grounded or surface entry bound to the Nether (or the End) compiles with canSeeSky and never spawns.
@pytest.mark.parametrize("position", IN_THE_OPEN)
@pytest.mark.parametrize("dims", [[NETHER], ["minecraft:the_end"], [NETHER, "minecraft:overworld"], []])
def test_an_entry_bound_off_the_overworld_does_not_require_the_sky(position, dims):
    cond = CS.box_condition(0, 31, 0, 31, _entry(position, conditions={"dimensions": dims}))
    assert "canSeeSky" not in cond, cond
    assert cond["dimensions"] == dims


# Without it an entry that names the overworld explicitly loses the sky test that keeps it out of caves.
@pytest.mark.parametrize("position", IN_THE_OPEN)
def test_an_entry_bound_to_the_overworld_keeps_the_sky(position):
    cond = CS.box_condition(0, 31, 0, 31, _entry(position, conditions={"dimensions": ["minecraft:overworld"]}))
    assert cond["canSeeSky"] is True, cond


# Without it a typo ("the_nether", a bare string) compiles silently and the entry spawns in no dimension or every one.
@pytest.mark.parametrize("dims", ["minecraft:the_nether", ["the_nether"], [3]])
def test_a_malformed_dimension_list_fails_closed(dims):
    with pytest.raises(SystemExit):
        CS.box_condition(0, 31, 0, 31, _entry("grounded", conditions={"dimensions": dims}))


# Without it the unit tests above pass while a compile path that does not go through box_condition (route, sub-region,
# heart, waterway, Mega den) still forces the sky on a Nether entry. The data is copied and one grounded entry is bound
# to the Nether; everything else, and every other entry's sky, is the real data's.
def test_a_nether_bound_entry_compiles_without_the_sky_on_every_path(tmp_path):
    doc = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    target = next(e for e in doc["entries"] if e.get("ambient") and not e.get("heart")
                  and (e.get("spawnable_position") or "grounded") == "grounded"
                  and e.get("mechanism") == "spawn_json_coordinate_boxes" and not (e.get("conditions") or {}))
    target["conditions"] = {"dimensions": [NETHER]}
    spawns = tmp_path / "spawns.json"
    spawns.write_text(json.dumps(doc), encoding="utf-8")
    out = tmp_path / "out"
    assert CS.main(["--spawns", str(spawns), "--out", str(out)]) == 0
    base = out / "data" / "cobblers" / "spawn_pool_world"
    bound = [(p.name, s) for p in base.rglob("*.json") for s in json.loads(p.read_text(encoding="utf-8")).get("spawns") or []
             if s["condition"].get("dimensions")]
    assert bound, "the Nether-bound entry %s compiled nowhere" % target["id"]
    assert all(s["condition"]["dimensions"] == [NETHER] for _, s in bound)
    forced = [(n, s["id"]) for n, s in bound if "canSeeSky" in s["condition"]]
    assert not forced, (len(forced), forced[:5])


# ------------------------------------------------------------------------------------------------ the whole output

@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    """{relative path: doc} for every spawn_pool_world file the real data compiles to, through the CLI."""
    out = tmp_path_factory.mktemp("cobblers_spawns")
    assert CS.main(["--out", str(out)]) == 0
    base = out / "data" / "cobblers" / "spawn_pool_world"
    docs = {p.relative_to(base).as_posix(): json.loads(p.read_text(encoding="utf-8")) for p in base.rglob("*.json")}
    assert docs, "the compile wrote no spawn_pool_world files"
    return docs


def _spawns(compiled, positions, marine=None):
    for rel, doc in compiled.items():
        if marine is not None and rel.startswith("marine/") != marine:
            continue
        for s in doc.get("spawns") or []:
            if s.get("spawnablePositionType") in positions:
                yield rel, s


# Without it the unit test above could pass while the data re-adds canSeeSky to underwater entries through their
# authored conditions, or a compile path that does not use box_condition forces it.
def test_no_compiled_submerged_or_seafloor_entry_requires_the_sky(compiled):
    under = list(_spawns(compiled, UNDERWATER))
    assert len(under) >= 1000, len(under)          # 3,677 + 217 on the data ad48221 was measured against, marine aside
    bad = [(rel, s["id"]) for rel, s in under if "canSeeSky" in s["condition"]]
    assert not bad, (len(bad), bad[:5])


# Without it a land or surface entry compiles without its sky test (and spawns in caves), or a marine surface entry
# loses the canSeeSky its data authors (marine_condition forces nothing, so the data must carry it).
def test_every_compiled_land_and_surface_entry_requires_the_sky(compiled):
    # overworld entries only: an entry bound off the overworld must NOT carry it (the N154 test above); the Nether's
    # compiled tables (spawn_pool_world/nether/, 2026-10-08) are all such entries. Narrowed by the Nether tables'
    # builder, not by test-author: tests/test_nether_encounters.py holds the Nether side.
    open_ = [(rel, s) for rel, s in _spawns(compiled, IN_THE_OPEN)
             if s["condition"].get("dimensions") in (None, ["minecraft:overworld"])]
    assert not [rel for rel, _ in open_ if rel.startswith("nether/")], "a Nether pool lost its dimension binding"
    assert len(open_) >= 1000, len(open_)
    assert any(rel.startswith("marine/") for rel, _ in open_), "no marine surface entry: the check lost its marine teeth"
    bad = [(rel, s["id"]) for rel, s in open_ if s["condition"].get("canSeeSky") is not True]
    assert not bad, (len(bad), bad[:5])


# Without it the marine rosters, deep water already, regain a forced canSeeSky and empty the open sea.
def test_compiled_marine_underwater_entries_do_not_require_the_sky(compiled):
    under = list(_spawns(compiled, UNDERWATER, marine=True))
    assert under, "no marine underwater entry compiled"
    bad = [(rel, s["id"]) for rel, s in under if "canSeeSky" in s["condition"]]
    assert not bad, (len(bad), bad[:5])
