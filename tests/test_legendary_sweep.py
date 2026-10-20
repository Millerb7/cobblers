"""The legendaries sweep (2026-10-06): data/adopted_legendary_sites.json sweep_sites and catalogue_2026_10_06, their
data/placements.json records, their activation items' one source in data/rewards.json, and tools/rewards_pack.py's
requires_flags.

Written by the builder of the sweep, so these are the builder's checks; docs/world-building/LEGENDARY_SWEEP.md "What an
audit must check" is what an independent reader owes.

The independent sides, none of them the record:
  the terrain    tools/ground.py, rounded: the seat is re-derived by this file's own loop, not tools/hidden_sites.seat
  the template   template-relative positions of the altar blocks, stated HERE as read from the NBT on 2026-10-06
                 (the giratina_altar at [23, 12, 20] of legendarymonuments:giratina_island/main/222; the darkrai_shrine
                 at [49, 46, 33] of lumymon:newmoon_island); the record's world positions must follow from them
  the cap        docs/mechanics/LEAGUE_LEVEL_CAP.md: only the Champion's cap (100) holds an 85-99 Giratina or a 70-85
                 Darkrai, so both items must require champion_cleared
  the catalogue  data/legendaries.json and the adopted `sites`: every legendary the repository already places or
                 authors must appear in the catalogue with that status
"""
from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import adopted_sites  # noqa: E402
import legendary_sweep as S  # noqa: E402
import rewards_pack as R  # noqa: E402

DOC = json.loads((ROOT / "data" / "adopted_legendary_sites.json").read_text(encoding="utf-8"))
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
REWARDS = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
LEGENDARIES = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))
SWEEP = {s["id"]: s for s in DOC["sweep_sites"]}
IDS = sorted(SWEEP)
CATALOGUE = DOC["catalogue_2026_10_06"]["templates"]

# The Giratina piece was the one SUNK site and the Red Chain its cache; the owner retired both on 2026-10-09 (Giratina
# lives in Wardenhold now: data/frostpeak_keep_quest.json). The records are kept under superseded_* and serve here as
# the in-memory FIXTURE for the sunk-seat rule and the champion-flag cache rule, which no live site exercises any more.
# Nothing below puts them back into a file.
RETIRED_SITE = next(s for s in DOC["superseded_sweep_sites"]["records"] if s["id"] == "sweep_giratina_shrine")
RETIRED_PLACEMENT = next(p for p in json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
                         ["superseded_placements"]["records"] if p["id"] == "legendary_giratina_shrine")
RETIRED_CHAIN = next(r for r in REWARDS["superseded_rewards"]["records"] if r["id"] == "sweep_red_chain")
FIXTURE_DOC = dict(DOC, sweep_sites=DOC["sweep_sites"] + [RETIRED_SITE])
FIXTURE_PLACEMENTS = PLACEMENTS + [RETIRED_PLACEMENT]

# read from the template NBT, 2026-10-06 (the server snapshot's jars), NOT from the record
ALTAR_IN_TEMPLATE = {"sweep_giratina_shrine": ("lumymon:giratina_altar", (23, 12, 20)),
                     "sweep_newmoon_island": ("lumymon:darkrai_shrine", (49, 46, 33))}
ITEM = {"sweep_giratina_shrine": "lumymon:red_chain", "sweep_newmoon_island": "lumymon:nightmare_weaver"}
CHAMPION_ONLY = ["champion_cleared"]


@pytest.fixture(scope="module")
def ground():
    import ground as G
    from terrain import TerrainUnavailable
    try:
        return G.load()
    except TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])


def record(sid):
    return next(q for q in PLACEMENTS if q["id"] == SWEEP[sid]["scheduled_as"])


def cheapest_seat(heights):
    """This file's own derivation: the y in the measured range that moves the fewest blocks, ties to the lowest."""
    hs = [int(v) for v in heights.ravel().tolist()]
    best = None
    for y in range(min(hs), max(hs) + 1):
        cost = sum(abs(h - y) for h in hs)
        if best is None or cost < best[1]:
            best = (y, cost)
    return best[0]


def test_one_live_sweep_site_and_the_giratina_piece_retired_out_of_every_list_a_tool_builds():
    # 2026-10-09 the owner retired the Giratina piece; no placer may paste it again
    assert IDS == ["sweep_newmoon_island"]
    assert {s["seat"]["kind"] for s in FIXTURE_DOC["sweep_sites"]} == {"sunk", "floating"}
    assert "legendary_giratina_shrine" not in {p.get("id") for p in PLACEMENTS}
    assert "sweep_red_chain" not in {r["id"] for r in REWARDS["rewards"]}
    assert "giratina_griseous" not in {r["id"] for r in REWARDS["rewards"]}
    assert RETIRED_SITE.get("retired") and RETIRED_PLACEMENT.get("status") == "retired"


# ------------------------------------------------------------------------------------------------- the seat


@pytest.mark.parametrize("sid", IDS)
def test_the_seat_is_the_heightmaps(sid, ground):
    s, q = SWEEP[sid], record(sid)
    x, y, z = (q["position"][k] for k in "xyz")
    sx, sy, sz = s["size"]
    h = ground.box(x, z, x + sx - 1, z + sz - 1)
    if s["seat"]["kind"] == "sunk":
        assert y + s["seat"]["ground_layer"] == cheapest_seat(h)
        for x_, z_ in ((x, z), (x + sx - 1, z + sz - 1)):
            assert ground(x_, z_) > 62
    else:
        assert y - int(h.max()) == s["seat"]["gap"] >= S.FLOAT_GAP_MIN
    assert y + sy - 1 <= DOC["ceiling"]["runtime_top_y"]


@pytest.mark.parametrize("sid", IDS)
def test_the_sweep_check_is_clean(sid, ground):
    assert S.check(ground)[sid] == []


def test_a_sunk_site_reseated_by_one_block_is_caught(ground):
    # (the fixture's own check is not clean any more: its retired caches, kept in data/rewards.json superseded_rewards,
    # are authored points at its edge; only the seat rule is under test here)
    assert not any("cheapest seat" in b for b in S.check(ground, FIXTURE_DOC, FIXTURE_PLACEMENTS)["sweep_giratina_shrine"])
    q = copy.deepcopy(FIXTURE_PLACEMENTS)
    for r in q:
        if r["id"] == "legendary_giratina_shrine":
            r["position"]["y"] += 1
    bad = S.check(ground, FIXTURE_DOC, q)["sweep_giratina_shrine"]
    assert any("cheapest seat" in b for b in bad), bad


def test_a_floating_site_lowered_into_its_trees_is_caught(ground):
    q = copy.deepcopy(PLACEMENTS)
    for r in q:
        if r["id"] == "legendary_newmoon_island":
            r["position"]["y"] -= 10
    bad = S.check(ground, DOC, q)["sweep_newmoon_island"]
    assert any("gap" in b for b in bad), bad


def _build_limit():
    # this file's own reading of the height pack the world loads, not tools/legendary_sweep.runtime_top or the record's
    # ceiling: the highest buildable layer is min_y + height - 1
    d = json.loads((ROOT / "modpack" / "datapacks" / "cobblers_height" / "data" / "minecraft" / "dimension_type"
                    / "overworld.json").read_text(encoding="utf-8"))
    return d["min_y"] + d["height"] - 1


NEWMOON_LAYERS = 58     # newmoon_island.nbt size [101, 58, 100], read from LumyMon-0.6.6.jar 2026-10-06 and 2026-10-20


def test_newmoon_island_touches_the_build_limit():
    # the owner, 2026-10-20: "raise darkrais island way into the air, where it touches the build limit". Without it
    # the island could sit anywhere under the limit, or its box run over it and lose its top layers
    q = record("sweep_newmoon_island")
    assert q["size"][1] == NEWMOON_LAYERS
    assert q["position"]["y"] + NEWMOON_LAYERS - 1 == _build_limit() == 575
    assert SWEEP["sweep_newmoon_island"]["seat"].get("top_at_runtime_top") is True


@pytest.mark.parametrize("dy,want", [(1, "over the runtime top"), (-1, "top_at_runtime_top")])
def test_newmoon_island_off_the_build_limit_is_caught(ground, dy, want):
    # one block over the limit loses the top layer; one under is not where the owner put it
    q = copy.deepcopy(PLACEMENTS)
    for r in q:
        if r["id"] == "legendary_newmoon_island":
            r["position"]["y"] += dy
    bad = S.check(ground, DOC, q)["sweep_newmoon_island"]
    assert any(want in b for b in bad), bad


def test_the_old_newmoon_seat_has_only_air_to_restore(ground):
    # this file's own column loop: every column under the old box has its rounded ground below the box's bottom, so
    # filling the box with air is the restore (data/placements.json legendary_newmoon_island superseded_seats)
    q = record("sweep_newmoon_island")
    (old,) = q["superseded_seats"]
    x0, y0, z0 = (old["position"][k] for k in "xyz")
    assert (x0, y0, z0) == (24, 141, 5582) and old["restore"] == "air"
    sx, _sy, sz = old["size"]
    top = max(ground(x, z) for x in range(x0, x0 + sx) for z in range(z0, z0 + sz))
    assert top < y0, top


def test_a_site_moved_onto_a_route_is_caught(ground):
    # Viridian-side Route 1 country: the move must trip the route rule (and others), never pass
    q = copy.deepcopy(FIXTURE_PLACEMENTS)
    for r in q:
        if r["id"] == "legendary_giratina_shrine":
            r["position"]["x"], r["position"]["z"] = 1466 - 21, 5036 - 19
    bad = S.check(ground, FIXTURE_DOC, q)["sweep_giratina_shrine"]
    assert any("route path" in b for b in bad), bad


# ------------------------------------------------------------------------------------- one author, one source


@pytest.mark.parametrize("sid", IDS)
def test_one_placements_record_and_every_consumer_sees_the_site(sid):
    assert S.placement_problems(SWEEP[sid], PLACEMENTS) == []
    assert sid in {s["id"] for s in adopted_sites.sites()}
    assert sid not in {s["id"] for s in DOC["sites"]}     # never held to the surface-seat contract


@pytest.mark.parametrize("sid", IDS)
def test_the_items_one_source_is_a_champion_cache_at_the_altar(sid):
    item = ITEM[sid]
    givers = [r for r in REWARDS["rewards"] for c in r.get("contents") or [] if c["item"] == item]
    assert len(givers) == 1, [r["id"] for r in givers]
    r = givers[0]
    assert r["kind"] == "cache" and r["requires_flags"] == CHAMPION_ONLY
    assert r["contents"] == [{"item": item, "count": 1, "verification": r["contents"][0]["verification"]}]
    block, (tx, ty, tz) = ALTAR_IN_TEMPLATE[sid]
    q = record(sid)
    want = [q["position"]["x"] + tx, q["position"]["y"] + ty, q["position"]["z"] + tz]
    assert r["container"] == {"block": block, "at": want}
    lo, hi = r["trigger"]["min"], r["trigger"]["max"]
    assert all(a <= v <= b for a, v, b in zip(lo, want, hi))


@pytest.mark.parametrize("sid", IDS)
def test_nothing_else_in_data_names_the_item(sid):
    """No quest, no placement's remove/keep list, no other file hands the item out: the cache is the one source."""
    item = ITEM[sid]
    for f in sorted((ROOT / "data").glob("*.json")):
        if f.name in ("rewards.json", "adopted_legendary_sites.json"):
            continue
        assert item not in f.read_text(encoding="utf-8"), f.name


def test_the_cache_advancement_holds_the_flag_in_its_one_condition():
    for rid in ("sweep_red_chain", "sweep_nightmare_weaver"):
        r = RETIRED_CHAIN if rid == "sweep_red_chain" else next(x for x in REWARDS["rewards"] if x["id"] == rid)
        (crit,) = R.advancement(r)["criteria"].values()
        (cond,) = crit["conditions"]["player"]
        assert cond["predicate"]["type_specific"] == {"type": "minecraft:player",
                                                      "advancements": {"cobblers:flag/champion_cleared": True}}
        assert cond["predicate"]["location"]["dimension"] == "minecraft:overworld"


def test_a_cache_without_requires_flags_has_no_player_predicate():
    r = next(x for x in REWARDS["rewards"] if x["kind"] == "cache" and "requires_flags" not in x)
    (crit,) = R.advancement(r)["criteria"].values()
    assert "type_specific" not in crit["conditions"]["player"][0]["predicate"]


@pytest.mark.parametrize("bad,why", [(["not_a_flag"], "does not declare"), ([], "non-empty"), ("champion_cleared", "non-empty"),
                                     (["Champion"], "non-empty")])
def test_requires_flags_is_refused_unless_declared_flags(bad, why):
    r = copy.deepcopy(RETIRED_CHAIN)
    assert not R.problems({"rewards": [r]})             # the fixture is a valid cache before the bad flag
    r["requires_flags"] = bad
    assert any(why in p for p in R.problems({"rewards": [r]}))


def test_requires_flags_on_an_npc_grant_is_refused():
    g = {"id": "g", "kind": "npc_grant", "npc_at": [1, 2, 3], "quest": "q", "requires_flags": ["champion_cleared"],
         "contents": [{"item": "a:b", "count": 1, "verification": "x in y.jar"}]}
    assert any("npc_grant" in p for p in R.problems({"rewards": [g]}))


# MUTATE THE GENERATOR: a rewards_pack that drops the flag predicate must be caught here.
def test_a_rewards_pack_that_forgets_the_flag_is_caught(monkeypatch):
    real = R.advancement

    def broken(r):
        a = real(r)
        for c in a["criteria"].values():
            for cond in c["conditions"]["player"]:
                cond["predicate"].pop("type_specific", None)
        return a
    monkeypatch.setattr(R, "advancement", broken)
    with pytest.raises((AssertionError, KeyError)):
        test_the_cache_advancement_holds_the_flag_in_its_one_condition()


# ------------------------------------------------------------------------------------------------- spread


def test_every_legendary_site_is_800_from_every_other():
    """Centre to centre, every adopted and sweep site and Hoopa's cradle, by this file's own arithmetic."""
    pts = {s["id"]: adopted_sites.centre(s, PLACEMENTS) for s in adopted_sites.sites()}
    hoopa = json.loads((ROOT / "data" / "hoopa_cradle.json").read_text(encoding="utf-8"))["spot"]
    pts["hoopa"] = [hoopa[0], hoopa[2]]
    for sid in IDS:
        for other, c in pts.items():
            if other != sid:
                d = math.hypot(pts[sid][0] - c[0], pts[sid][1] - c[1])
                assert d >= 800, (sid, other, round(d))


# ------------------------------------------------------------------------------------------------- the catalogue


def test_the_catalogue_names_every_site_the_repository_places():
    by_template = {t["template"]: t for t in CATALOGUE}
    for s in DOC["sites"]:
        assert by_template[s["template"]]["status"] == "adopted", s["template"]
    for s in DOC["sweep_sites"]:
        assert by_template[s["template"]]["status"] == "placed_by_sweep"
        assert by_template[s["template"]]["where"] == s["id"]


def test_every_ours_authored_entry_names_a_record_that_exists():
    enc = {e["id"] for e in LEGENDARIES["encounters"]}
    for t in CATALOGUE:
        if t["status"] == "ours_authored" and "data/legendaries.json" in t["where"]:
            named = t["where"].split("data/legendaries.json ")[1].split()[0]
            assert named in enc, (t["template"], named)


def test_catalogue_statuses_and_counts():
    assert all(t["status"] in S.STATUSES for t in CATALOGUE)
    assert len({t["template"] for t in CATALOGUE}) == len(CATALOGUE) == 39
    assert all(t["loaded"] is False for t in CATALOGUE if t["status"] == "not_loaded")
    assert sum(1 for t in CATALOGUE if t["loaded"]) == 22
