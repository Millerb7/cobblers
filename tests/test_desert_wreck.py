"""tools/desert_wreck.py: the Brass Petrel, the dead reef, Castellan and the strand's pool (data/desert_wreck.json).

The BUILDER's tests, written by the agent that wrote the generator: they hold the plan to the brief and the rules,
recomputing what they can from the heightmap and the shared data files rather than from the plan. They are not the
independent audit, which is another agent's (docs/world-building/DESERT_WRECK.md, "What an audit must check").

Needs the canonical heightmap; a skip names it. NOT covered, and it needs a running server: that the fills land, that
the dune's sand lies on the bow's deck as planned, that the natural Habitat Blocks redirect spawns (EXP-021) and how far
up and down they reach (EXP-033, unrun), that Galarian Corsola spawns from the pool's `modifiers`, that the cache grants,
that Castellan appears for a gym7_cleared player and wakes within 3.
"""
import copy
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import desert_wreck as DW  # noqa: E402
import function_limits  # noqa: E402

DOC = DW.load()
SEA = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8")).get("sea_level", 62)
# every vanilla 1.21.1 block that gives off light: a lantern is the only one the brief allows
EMITTERS = {"minecraft:" + b for b in (
    "lantern soul_lantern torch wall_torch soul_torch soul_wall_torch redstone_torch glowstone sea_lantern shroomlight "
    "jack_o_lantern redstone_lamp light campfire soul_campfire end_rod beacon magma_block glow_lichen sea_pickle "
    "crying_obsidian respawn_anchor ochre_froglight verdant_froglight pearlescent_froglight candle white_candle "
    "lava fire soul_fire conduit amethyst_cluster sculk_catalyst enchanting_table ender_chest brewing_stand "
    "furnace smoker blast_furnace lit_pumpkin copper_bulb trial_spawner vault").split()}


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.load()
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture(scope="module")
def pl(ground):
    return DW.plan(DOC, ground)


# ------------------------------------------------------------------ the record


def test_the_world_json_sea_level_is_the_generators():
    assert DW.SEA == SEA


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d["blocks"]["ids"].append("minecraft:glowstone"), "forbidden"),
    (lambda d: d["blocks"]["ids"].append("minecraft:soul_sand"), "forbidden"),
    (lambda d: d["residents"][0]["pokemon"].update(trigger=20), "trigger"),
    (lambda d: d["wreck"].update(depth=6), "depth"),
    (lambda d: d["wreck"]["hold"].update(spill_slope_to=40), "follow"),
])
def test_the_record_is_refused_when_it_breaks_a_rule(tmp_path, mutate, msg):
    d = copy.deepcopy(DOC)
    mutate(d)
    f = tmp_path / "w.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        DW.load(f)
    assert msg in str(e.value)


def test_every_sign_line_fits_a_sign():
    for k, lines in DOC["signs"].items():
        if k == "sign_rule":
            continue
        assert len(lines) <= 4 and all(len(t) <= 15 for t in lines), (k, lines)


# ------------------------------------------------------------------ the plan


def test_the_plan_passes_its_own_guards_and_is_the_same_every_time(ground, pl):
    assert DW.problems(DOC, pl, ground) == []
    assert DW.plan(DOC, ground)["blocks"] == pl["blocks"]


def test_the_recorded_bounds_are_the_plans(pl):
    assert pl["bounds"] == {k: v for k, v in DOC["bounds"].items() if k != "why"}


def test_every_block_written_is_allowed_and_only_lanterns_give_light(pl):
    written = {DW.base(s) for s in pl["blocks"].values()}
    assert written <= set(DOC["blocks"]["ids"]), sorted(written - set(DOC["blocks"]["ids"]))
    assert written & EMITTERS == {"minecraft:lantern"}
    assert not written & {"minecraft:water", "minecraft:bubble_column", "minecraft:soul_sand", "minecraft:magma_block",
                          "minecraft:chest", "minecraft:trapped_chest"}
    assert not any("bed" == DW.base(s).rsplit("_", 1)[-1] for s in pl["blocks"].values())


def test_the_spawn_conditions_written_are_declared_and_whitelisted_for_this_place(pl):
    spawn = set(_load("spawn_blocks.json")["blocks"])
    written = {DW.base(s) for s in pl["blocks"].values()} & spawn
    assert written == set(DOC["blocks"]["spawn_conditions"]), sorted(written ^ set(DOC["blocks"]["spawn_conditions"]))
    pol = [w for w in _load("spawn_block_policy.json")["whitelist"] if "desert_wreck" in w["scope"]]
    assert pol and written <= set(pol[0]["blocks"])


def test_the_deck_is_the_transom_sand_plus_stern_show_and_the_keel_depth_under_it(ground, pl):
    w = DOC["wreck"]
    tz = w["bow_z"] + w["length"] - 1
    half = w["stern_taper"][-1]
    assert pl["D"] == max(ground(w["x"] + dx, tz) for dx in range(-half, half + 1)) + w["stern_show"]
    assert pl["K"] == pl["D"] - w["depth"]


def test_the_bow_is_buried_to_the_rail_and_the_keel_nowhere_shows(ground, pl):
    w = DOC["wreck"]
    D, K = pl["D"], pl["K"]
    for lz in range(3):
        h = w["bow_taper"][lz]
        for dx in range(-h, h + 1):
            assert ground(w["x"] + dx, w["bow_z"] + lz) >= D + 1
    p = pl["plan"]
    for lz in range(w["length"]):
        for dx in range(-p.hw0(lz), p.hw0(lz) + 1):
            g = ground(w["x"] + dx, w["bow_z"] + lz)
            assert g > K and g >= SEA, (dx, lz, g)


def test_nothing_is_carved_out_of_or_poured_into_the_sea(ground, pl):
    for (x, y, z), s in pl["blocks"].items():
        g = ground(x, z)
        if g < SEA:
            assert g == SEA - 1 and y == SEA and DW.base(s) not in ("minecraft:air", "minecraft:sand"), ((x, y, z), s)


def test_the_clearing_never_names_water(ground, pl):
    lines = [l for l in DW.build_lines(DOC, pl) if not l.startswith("#")]
    assert lines and not any("#minecraft:replaceable" in l or l.rstrip().endswith("minecraft:water") for l in lines)


def test_the_way_in_is_one_step_from_the_sand(ground, pl):
    w = DOC["wreck"]
    t = w["length"] - 1
    floor = pl["D"] - w["hold"]["floor_below_deck"]
    for dx in range(-w["breach_half"], w["breach_half"] + 1):
        x, z = w["x"] + dx, w["bow_z"] + t
        outside = ground(x, z + 1)
        col = [pl["blocks"].get((x, y, z)) for y in range(floor, floor + 6)]
        sill = max(y for y in range(floor, floor + 6) if pl["blocks"].get((x, y, z)) != "minecraft:air"
                   and y <= floor + 2)
        assert outside - sill <= 1 and sill - floor <= 1, (dx, outside, sill, floor, col)
        assert pl["blocks"][(x, sill + 1, z)] == "minecraft:air" and pl["blocks"][(x, sill + 2, z)] == "minecraft:air"


def test_every_air_cell_inside_is_lit_by_a_lantern(pl):
    assert DW.dark_cells(pl) == set()


def test_the_hatch_ladder_reaches_the_deck(pl):
    p = pl["plan"]
    hz = DOC["wreck"]["hatch_at"]
    x, z = p.xz(0, hz)
    for y in range(p.floor + 1, p.D):
        assert pl["blocks"][(x, y, z)].startswith("minecraft:ladder[facing=south")
    assert pl["blocks"][(x, p.D, z)].startswith("minecraft:spruce_trapdoor")
    assert DW.base(pl["blocks"][(x, p.D - 1, z - 1)]) == DOC["blocks"]["mast"]     # what the ladder hangs on


def test_no_sand_hangs_over_air(pl):
    # the written sand (spill and breach sill) stands on something; the dune's own sand lies on the deck
    for (x, y, z), s in pl["blocks"].items():
        if s == "minecraft:sand":
            assert pl["blocks"].get((x, y - 1, z), "x") != "minecraft:air", (x, y, z)


# ------------------------------------------------------------------ the records in the shared files


def test_the_shared_records_are_what_the_plan_writes(pl):
    habs, pool, reward = DW.records(DOC, pl)
    hb = {b["id"]: b for b in _load("habitat_blocks.json")["blocks"]}
    for h in habs:
        assert hb.get(h["id"]) == h, h["id"]
    sp = _load("spawns.json")
    assert [h for h in sp["habitats"] if h["id"] == DOC["pool"]["id"]] == [pool["habitat"]]
    assert [e for e in sp["entries"] if e.get("scope") == DOC["pool"]["id"]] == pool["entries"]
    rw = {r["id"]: r for r in _load("rewards.json")["rewards"]}
    assert rw.get(reward["id"]) == reward


def test_the_wards_touch_without_overlapping_and_sit_in_no_written_block(pl):
    ws = pl["wards"]
    assert len(ws) == 2
    d = math.dist(ws[0][1], ws[1][1])
    assert d >= ws[0][2] + ws[1][2]
    for _i, xyz, _r in ws:
        assert xyz not in pl["blocks"]
    others = [b for b in _load("habitat_blocks.json")["blocks"] if b.get("style") == "natural"
              and b["id"] not in {w[0] for w in ws}]
    for i, (x, y, z), r in ws:
        for b in others:
            q = b["position"]
            assert math.dist((x, y, z), (q["x"], q["y"], q["z"])) >= r + b["range_of_influence"], (i, b["id"])


def test_the_pool_band_is_tier_7_and_no_evolution_spawns_below_its_level():
    tiers = _load("encounter_design.json")["rules"]["tiers"]
    assert DOC["pool"]["band"] == tiers[str(DOC["pool"]["tier"])]["band"]
    evolves_at = {"palossand": 42, "cursola": 38, "barbaracle": 39, "sandaconda": 36}   # Cobblemon 1.8.0 jar, 2026-10-05
    lo = DOC["pool"]["band"][0]
    for row in DOC["pool"]["entries"]:
        if row[0] in evolves_at:
            assert (row[1] == "authored-only") == (evolves_at[row[0]] > lo), row


def test_the_compiled_pool_names_a_species_and_carries_the_form_as_modifiers():
    import compile_spawns as CS
    sp = _load("spawns.json")
    h = next(x for x in sp["habitats"] if x["id"] == DOC["pool"]["id"])
    ents = [e for e in sp["entries"] if e["mechanism"] == "habitat_block" and e["scope"] == h["id"]]
    doc, _summary = CS.compile_habitat(h, ents)
    assert all(" " not in s["species"] for s in doc["spawns"])
    cors = [s for s in doc["spawns"] if s["species"] == "corsola"]
    assert cors and cors[0]["modifiers"] == "galarian"
    assert not [s for s in doc["spawns"] if s["species"] in ("palossand", "barbaracle")]


def test_the_cache_trigger_stands_round_the_sea_chest_inside_the_cabin(pl):
    bx, by, bz = pl["barrel"]
    assert pl["blocks"][(bx, by, bz)].startswith("minecraft:barrel")
    t = pl["trigger"]
    inside = [(x, y, z) for x in range(t["min"][0], t["max"][0] + 1) for y in range(t["min"][1], t["max"][1] + 1)
              for z in range(t["min"][2], t["max"][2] + 1)]
    assert any(pl["blocks"].get(c) == "minecraft:air" for c in inside), "nowhere in the trigger to stand"
    p = pl["plan"]
    assert t["min"][1] == p.D + 1 and all(p.xz(-p.hw0(37), 37)[0] < c[0] < p.xz(p.hw0(37), 37)[0] for c in inside)


# ------------------------------------------------------------------ Castellan


def test_castellan_stands_dry_at_the_tide_line_off_every_road(ground, pl):
    import numpy as np
    ax, ay, az = pl["resident"]
    assert ground(ax, az) >= SEA and ay == ground(ax, az) + 1
    assert any(ground(ax + dx, az + dz) < SEA for dx in range(-3, 4) for dz in range(-3, 4))
    paths = np.array([p for pl_ in _load("route_paths.json")["paths"].values() for p in pl_], float)
    clear = _load("encounter_design.json")["rules"]["hearts"]["clear_of_path_blocks"]
    assert float(np.min(np.hypot(paths[:, 0] - ax, paths[:, 1] - az))) >= clear


def test_castellans_level_is_under_the_strands_ceiling_and_its_leash_clear_of_every_nest(pl):
    pk = DOC["residents"][0]["pokemon"]
    ceiling = _load("encounter_design.json")["rules"]["hearts"]["next_cap"][str(DOC["pool"]["tier"])]
    assert pk["level"] <= ceiling and pk["appears_after"]
    ax, _ay, az = pl["resident"]
    for b in _load("habitat_blocks.json")["blocks"]:
        if b.get("style") == "activated":
            d = math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az)
            assert d >= b["activated"]["spawn_range"] + pk["leash"], b["id"]


# ------------------------------------------------------------------ the pack


def test_the_pack_is_a_whole_pack_the_server_accepts(ground):
    written, pl = DW.files(DOC, ground)
    ns, F = DOC["build"]["namespace"], DOC["build"]["folder"]
    build = written["data/%s/function/%s/build.mcfunction" % (ns, F)].splitlines()
    assert function_limits.check_lines(build, "build") == []
    for f in ("keep", "hold", "wake", "settle", "spawn", "bind"):
        assert "data/%s/function/%s/castellan/%s.mcfunction" % (ns, F, f) in written
    assert "data/%s/function/%s/castellan/bind_new.mcfunction" % (ns, F) not in written   # gated: never summoned
    assert json.loads(written["data/minecraft/tags/function/load.json"]) == {"values": ["%s:%s/load" % (ns, F)]}
    keep = written["data/%s/function/%s/castellan/keep.mcfunction" % (ns, F)]
    assert "advancements={cobblers:flag/gym7_cleared=true}" in keep
    assert DW.entity_steps(DOC) == []
    steps = DW.placement_steps(DOC, ground)
    assert steps[2] == ("fn", "%s:%s/build" % (ns, F))
