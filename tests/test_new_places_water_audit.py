"""Tests for tools/new_places_water_audit.py: the independent water, light and reach audit of the Drowned Quarry, the
Glowcap Hollow pool, the Merian ice lodge's tarn, Gull Rock and Hummock Mere.

Three layers:
  1. the audit's own machinery on a synthetic world small enough to compute by hand (replay, containment, light,
     reach, swim distance), so a place passing is not the only evidence the checks work;
  2. each real place, generated to a temporary directory and replayed over the canonical heightmap;
  3. mutations of each GENERATOR (its code monkeypatched; data/*.json untouched) that the audit must catch.

What these tests do NOT cover: anything in a running game (whether the fills land, whether water flows as modelled,
whether ice melts or freezes, whether a player really climbs out where the model says), natural caves and vegetation
the heightmap does not hold, and the shell's protection against such caves (see the audit's docstring).
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import new_places_water_audit as A  # noqa: E402


# ------------------------------------------------------------------------------------------------ synthetic world


class FlatBase(A.Base):
    """x 0..9 a pond: ground y58, water y59..y62. x 10..39 a bank: ground y62 (level with the water, so it holds it),
    standing surface y63. Nothing in it leaks before a build touches it."""

    def __init__(self):
        self.cols = {}
        for x in range(-4, 48):
            for z in range(-4, 48):
                self.cols[(x, z)] = (58, 62) if x <= 9 else (62, None)


def synth(cmds):
    rp = A.Replay(FlatBase())
    rp.command("forceload add 0 0 31 31", "t", None)
    for c in cmds:
        rp.command(c, "t", None)
    return rp


def test_synthetic_base_layers():
    # Removing this lets a wrong world-before (water at the ground block, or air under the level) pass unnoticed.
    b = FlatBase()
    assert b.state(3, 58, 3) == "base:terrain" and b.state(3, 59, 3) == "base:water"
    assert b.state(3, 62, 3) == "base:water" and b.state(3, 63, 3) == "base:air"
    assert b.state(20, 62, 3) == "base:terrain" and b.state(20, 63, 3) == "base:air"
    assert A.containment(synth([])) == []


def test_replay_filter_and_keep_follow_the_cell_at_that_moment():
    # Removing this lets `replace #minecraft:replaceable` (which takes water) and `keep` be replayed as plain fills.
    rp = synth(["fill 2 59 2 4 63 2 minecraft:air replace #minecraft:replaceable",
                "fill 2 63 3 2 63 3 minecraft:stone keep",
                "fill 2 59 4 2 59 4 minecraft:stone keep"])
    assert rp.get(3, 60, 2) == "minecraft:air"                       # water is replaceable: drained
    assert rp.get(3, 58, 2) == "base:terrain"                       # under the fill
    assert rp.get(2, 63, 3) == "minecraft:stone"                    # keep over air writes
    assert rp.get(2, 59, 4) == "base:water"                         # keep over water does not


def test_replay_refuses_unheld_chunks_and_oversized_fills():
    # Removing this lets a write the server would refuse (unloaded chunk, > 32768 blocks) count as built.
    rp = synth(["setblock 40 63 0 minecraft:stone", "fill 0 0 0 40 40 40 minecraft:stone"])
    kinds = [k for k, _m in rp.problems]
    assert "hold" in kinds and "fill" in kinds
    assert rp.get(40, 63, 0) == "base:air" and rp.get(5, 5, 5) == "base:terrain"


def test_containment_finds_water_beside_air_and_air_beside_water():
    # Removing this loses the leak check: water placed on dry ground, or a carve the pond drains into.
    rp = synth(["setblock 20 63 5 minecraft:water",                 # on the bank: flows sideways and nowhere holds it
                "setblock 12 64 12 minecraft:air",                  # air in air: nothing
                "setblock 10 60 3 minecraft:air"])                  # the bank cut under the pond's level
    leaks = A.containment(rp)
    assert ((20, 63, 5), (21, 63, 5)) in leaks and ((20, 63, 5), (19, 63, 5)) in leaks
    assert ((9, 60, 3), (10, 60, 3)) in leaks                       # the pond drains into the cut
    assert not any(o == (12, 64, 12) for _w, o in leaks)
    assert len(leaks) == 5


def test_waterlogged_blocks_are_water_and_a_mushroom_is_washed():
    # Removing this lets a waterlogged block on dry land, or water beside a plant it washes out, pass.
    rp = synth(["setblock 20 63 8 minecraft:lantern[hanging=false,waterlogged=true]",
                "setblock 20 63 20 minecraft:water", "setblock 21 63 20 minecraft:red_mushroom",
                "setblock 19 63 20 minecraft:stone", "setblock 20 63 19 minecraft:stone", "setblock 20 63 21 minecraft:stone"])
    leaks = A.containment(rp)
    assert any(w == (20, 63, 8) for w, _o in leaks)
    assert [l for l in leaks if l[0] == (20, 63, 20)] == [((20, 63, 20), (21, 63, 20))]


def test_light_at_ice_hand_computed():
    # Removing this loses the melt check. A lantern 3 blocks from ice gives it 12 (melts), 5 blocks gives 10 (holds);
    # a lantern walled in by stone gives nothing.
    rp = synth(["setblock 20 63 10 minecraft:lantern", "setblock 23 63 10 minecraft:ice",
                "setblock 20 63 15 minecraft:ice", "setblock 25 63 10 minecraft:ice"])
    assert A.light_at_ice(rp) == ([((23, 63, 10), 12)], 12)
    rp2 = synth(["setblock 20 63 10 minecraft:lantern", "setblock 22 63 10 minecraft:ice",
                 "setblock 21 63 10 minecraft:stone", "setblock 19 63 10 minecraft:stone",
                 "setblock 20 64 10 minecraft:stone", "setblock 20 63 9 minecraft:stone", "setblock 20 63 11 minecraft:stone"])
    assert A.light_at_ice(rp2) == ([], 0)


def test_nav_steps_jumps_falls_and_climb_out():
    # Removing this lets the reach checks pass a 2-block ledge as climbable or a 4-block drop as returnable.
    rp = synth(["fill 15 63 0 15 63 31 minecraft:stone",            # a 1-high step: climbable
                "fill 18 63 0 18 64 31 minecraft:stone",            # a 2-high wall: not
                "fill 25 63 0 31 66 31 minecraft:stone"])           # a 4-high plateau
    nav = A.Nav(rp, (11, 58, 0, 31, 75, 3))
    fwd = nav.reach([("s", 12, 1, 63.0)])
    assert ("s", 15, 1, 64.0) in fwd and ("s", 17, 1, 63.0) in fwd
    assert ("s", 18, 1, 65.0) not in fwd and ("s", 20, 1, 63.0) not in fwd
    down = nav.reach([("s", 26, 1, 67.0)])
    assert ("s", 24, 1, 63.0) not in down                           # a 4-block fall is over FALL 3
    # the pond: a swimmer at the top water block climbs onto a surface one block above the water, not two
    nav3 = A.Nav(synth(["fill 10 63 0 10 63 31 minecraft:stone"]), (6, 55, 0, 14, 70, 3))
    assert ("s", 10, 1, 64.0) in nav3.reach([("w", 8, 62, 1)])
    nav4 = A.Nav(synth(["fill 10 63 0 10 64 31 minecraft:stone"]), (6, 55, 0, 14, 70, 3))
    assert not any(n[0] == "s" and n[1] >= 10 for n in nav4.reach([("w", 8, 62, 1)]))


def test_swim_distance_hand_computed():
    # Removing this loses the proof that the quarry's swim lengths are measured, not assumed: a breathing cell at
    # (1, 51, 5), one block down, then 20 along a sealed tube; no corner cut through the rock.
    rp = synth(["fill 0 40 0 31 63 31 minecraft:stone", "fill 1 50 5 21 50 5 minecraft:water",
                "setblock 1 51 5 minecraft:water", "setblock 1 52 5 minecraft:air"])
    d, breath = A.swim_distances(rp, (0, 45, 0, 25, 55, 10), {"end": [(21, 50, 5)], "none": [(30, 50, 30)]})
    assert breath == [(1, 51, 5)]
    assert d == {"end": 21.0, "none": None}


def test_even_odd_matches_water_mask():
    # Removing this lets the audit's raster of the lake basins drift from tools/water_mask.py's own rule.
    import numpy as np
    import water_mask as WM
    polys = [[(0, 0), (20, 0), (20, 10), (10, 18), (0, 10)], [(4, 4), (8, 4), (8, 8), (4, 8)]]
    X, Z = np.meshgrid(np.arange(-2, 23), np.arange(-2, 21))
    got = A.even_odd(polys, X, Z)
    for zi in range(Z.shape[0]):
        for xi in range(X.shape[1]):
            assert bool(got[zi, xi]) == WM.in_polygons(polys, int(X[zi, xi]), int(Z[zi, xi]))


# ------------------------------------------------------------------------------------------------ the real places


@pytest.fixture(scope="module")
def world():
    import ground as G
    try:
        g = G.load()
    except Exception as e:                                          # pragma: no cover
        pytest.skip("the canonical heightmap is not available: %s" % e)
    return g, A.Base(g)


def run(place, world, tmp, check=True):
    g, base = world
    steps, pack = A.generate(place, Path(tmp) / place, g, check=check)
    return A.AUDITS[place](g, base, pack, steps)[0]


@pytest.fixture(scope="module")
def clean(world, tmp_path_factory):
    return {p: run(p, world, tmp_path_factory.mktemp(p)) for p in A.PLACES}


def test_base_raster_agrees_with_water_mask_level_at(world):
    # Removing this lets the world-before disagree with the painted water at the places themselves.
    import water_mask as WM
    g, base = world
    rnd = random.Random(7)
    pts = [(6340 + rnd.randrange(200), 4090 + rnd.randrange(70)) for _ in range(25)] + \
          [(5220 + rnd.randrange(60), 1900 + rnd.randrange(50)) for _ in range(25)] + \
          [(6850 + rnd.randrange(140), 2600 + rnd.randrange(100)) for _ in range(25)]
    b2 = A.Base(g)
    b2.prime(6330, 4080, 6560, 4170)
    b2.prime(5210, 1895, 5290, 1955)
    b2.prime(6840, 2595, 6995, 2705)
    for x, z in pts:
        assert b2.col(x, z)[1] == WM.level_at(x, z, g, base.bodies, base.sea)[1], (x, z)


@pytest.mark.parametrize("place", A.PLACES)
def test_place_holds_its_water(clean, place):
    # Removing this lets a place write water where nothing holds it, or open a cell a lake drains into.
    r = clean[place]
    assert r.measured["leaks"] == 0 and r.measured["water_cells_made_open"] == 0, r.problems


@pytest.mark.parametrize("place", A.PLACES)
def test_place_writes_inside_its_box_and_its_forceloads(clean, place):
    # Removing this lets a write land outside the declared box, or in a chunk the re-application never loaded.
    r = clean[place]
    assert not [p for p in r.problems if p[0] in ("bounds", "hold", "fill", "replay")], r.problems


@pytest.mark.parametrize("place", A.PLACES)
def test_place_writes_no_unscoped_spawn_condition(clean, place):
    # Removing this lets a block that decides encounters in data/spawn_blocks.json slip in unwhitelisted.
    assert not [p for p in clean[place].problems if p[0] == "spawn"]


@pytest.mark.parametrize("place", A.PLACES)
def test_place_routes_reachable_and_returnable(clean, place):
    # Removing this lets a promised route be unreachable, or a softlock where a player can get in and not out.
    assert not [p for p in clean[place].problems if p[0] in ("reach", "swim", "fatigue")], clean[place].problems


def test_quarry_swim_gate_from_the_rules(clean):
    # Removing this loses the independent recomputation of the Dive gate (DROWNED_QUARRY.md section 4).
    m = clean["drowned_quarry"].measured
    d = m["swim_blocks"]
    surf = A.surf_air()
    assert surf == 60.0                                             # 900 ticks of bonus + vanilla's 15 s
    assert m["breathing_cells_past_portal"] == 0                    # no air to rest in, anywhere in the working
    assert 2 * d["portal"] / A.SPRINT_SWIM < A.AIR_NO_MOUNT         # no mount touches the mouth and returns
    assert d["hall_door"] / A.SPRINT_SWIM > A.AIR_NO_MOUNT          # no mount cannot reach the door
    assert 2 * d["hall_door"] / A.SPRINT_SWIM <= surf               # Surf reaches the door and returns
    assert 2 * d["sump"] / A.SPRINT_SWIM > surf                     # only Dive spends a fight in the sump


def test_lodge_ice_stays_below_the_melt_light(clean):
    # Removing this lets a lantern or campfire sit close enough to plain ice to melt it (ASSUMED vanilla rule).
    m = clean["ice_lodge"].measured
    assert m["ice_over_light"] == 0 and m["brightest_plain_ice"] <= A.MELT_ABOVE
    assert m["hole_and_lead_water"] > 0 and m["hole_water_trapped"] == 0


def test_rookery_short_swim_under_the_first_fatigue_hit(clean):
    # Removing this lets "reached by a short swim" stand with no swim measured against data/blackout.json's fatigue.
    m = clean["rookery"].measured
    assert all(m["skerry%d_highest_stand" % k] is not None for k in range(6))
    assert m["shore_swim_fatigue_ticks"] < A.jload("data/blackout.json")["surface"]["collapse_ticks"]


def test_quarry_shell_written_round_every_flooded_cell(clean):
    # Removing this loses the only check that the shell (the guard against caves no heightmap shows) was written.
    m = clean["drowned_quarry"].measured
    assert m["shell_cells_required"] > 0 and m["shell_cells_missing"] == 0


def test_quarry_wake_zone_reachable_by_a_swimmer(clean):
    # Removing this lets the Gyarados sit where no swimmer can come within its trigger radius.
    assert clean["drowned_quarry"].measured["swim_blocks"]["wake"] is not None


def test_hummock_wake_reachable_by_wading(clean):
    # Removing this lets the Hummock's wake trigger sit out of every wader's reach.
    assert "wake" not in clean["hummock_mere"].checks()


@pytest.mark.xfail(strict=True, reason="DEFECT data/rookery.json + tools/rookery.py: the Gullmother wakes for a player "
                   "within 12 of (6940.5, 83, 2650.5) (rookery/gullmother/hold), but the nearest position a player can "
                   "swim or climb to and leave is 17.9 blocks away, on the stack's talus at (6948.5, 67, 2650.5); the "
                   "ledges (sea+6, +11, +14) and the crown (y82) cannot be climbed from the water. Without a flying "
                   "mount or placed blocks she never wakes.")
def test_rookery_gullmother_wake_reachable(clean):
    # Removing this hides that Gull Rock's resident cannot be woken by a player who swims and climbs.
    assert "wake" not in clean["rookery"].checks()


# ------------------------------------------------------------------------------------------------ the mutations


def test_mutation_quarry_shell_course_removed(world, tmp_path, monkeypatch):
    # Removing this loses the proof that a shell one course thin (margin - 1) is found, though the heightmap's rock
    # would hide it from every water check.
    import drowned_quarry as DQ
    orig = DQ._dilate
    monkeypatch.setattr(DQ, "_dilate", lambda mask, m: orig(mask, m - 1))
    r = run("drowned_quarry", world, tmp_path)
    assert r.checks() == ["shell"] and r.measured["shell_cells_missing"] > 0


def test_mutation_quarry_hall_top_left_as_air(world, tmp_path, monkeypatch):
    # Removing this loses the proof that containment and the no-air rule bite on the quarry's own output.
    import drowned_quarry as DQ
    orig = DQ.carve_files

    def mutated(doc, M, ground):
        fn = orig(doc, M, ground)
        i = max(k for k, l in enumerate(fn["carve_void"]) if l.startswith("fill "))
        fn["carve_void"][i] = fn["carve_void"][i].replace("minecraft:water", "minecraft:air")
        return fn
    monkeypatch.setattr(DQ, "carve_files", mutated)
    r = run("drowned_quarry", world, tmp_path)
    assert "containment" in r.checks() or "swim" in r.checks(), r.measured
    assert r.measured["breathing_cells_past_portal"] > 0


def test_mutation_quarry_dog_leg_fill_dropped(world, tmp_path, monkeypatch):
    # Removing this loses the proof that the swim check notices a blocked adit (a dropped water fill).
    import drowned_quarry as DQ
    doc = A.jload("data/drowned_quarry.json")
    p1, p2 = doc["geometry"]["road"]["points"][1:3]
    cell = (p1[0], doc["geometry"]["floor_y"] + 3, (p1[1] + p2[1]) // 2)
    orig = DQ.carve_files

    def mutated(d, M, ground):
        fn = orig(d, M, ground)

        def holds(line):
            v = [int(t) for t in line.split()[1:7]]
            return all(min(v[i], v[i + 3]) <= cell[i] <= max(v[i], v[i + 3]) for i in range(3))
        fn["carve_void"] = [l for l in fn["carve_void"] if not (l.startswith("fill ") and holds(l))]
        return fn
    monkeypatch.setattr(DQ, "carve_files", mutated)
    r = run("drowned_quarry", world, tmp_path)
    assert r.measured["swim_blocks"]["sump"] is None and "swim" in r.checks()


def test_mutation_fungal_pool_one_block_high(world, tmp_path, monkeypatch):
    # Removing this loses the proof that a pool surface above its own rim is caught (a shifted water fill).
    import fungal_isle as FI
    orig = FI.Plan.put

    def put(self, o, layer, x, y, z, state):
        return orig(self, o, layer, x, y + (1 if layer == "water" else 0), z, state)
    monkeypatch.setattr(FI.Plan, "put", put)
    r = run("fungal_isle", world, tmp_path, check=False)
    assert "containment" in r.checks(), r.measured


def test_mutation_fungal_bowl_walls_sheer(world, tmp_path, monkeypatch):
    # Removing this loses the proof that a bowl a player falls into and cannot climb out of is a softlock found.
    import fungal_isle as FI

    def profile(P, yc, r):
        bw, pl = P["bowl"], P["pool"]
        if r >= bw["rim_radius"]:
            return None
        extra = pl["deep"] if r <= pl["deep_radius"] else pl["mid"] if r <= pl["mid_radius"] else \
            pl["shallow"] if r <= pl["shallow_radius"] else 0
        return yc - bw["depth"] - extra, extra
    monkeypatch.setattr(FI, "hollow_profile", profile)
    r = run("fungal_isle", world, tmp_path, check=False)
    assert r.measured["bowl_trapped"] > 0 and "reach" in r.checks()


def test_mutation_lodge_shelter_floor_plain_ice(world, tmp_path, monkeypatch):
    # Removing this loses the proof that ice under a shelter's lantern is found by the melt check.
    import ice_lodge as IL
    orig = IL.shelters

    def mutated(p, mask, taken):
        out = orig(p, mask, taken)
        sy = p.doc["tarn"]["surface_y"]
        for (x, y, z), s in list(p.solid.items()):
            if y == sy and s == p.doc["shelter"]["floor"]:
                p.solid[(x, y, z)] = "minecraft:ice"
        return out
    monkeypatch.setattr(IL, "shelters", mutated)
    monkeypatch.setattr(IL, "guards", lambda *a, **k: {})
    r = run("ice_lodge", world, tmp_path)
    assert "light" in r.checks() and r.measured["brightest_plain_ice"] > A.MELT_ABOVE


def test_mutation_lodge_doors_walled_up(world, tmp_path, monkeypatch):
    # Removing this loses the proof that a sealed lodge or shelter (the keeper unreachable) is found.
    import ice_lodge as IL

    def door(self, x, z, y, facing, hinge):
        for d in (0, 1):
            self.put(x, y + d, z, "minecraft:spruce_planks")
    monkeypatch.setattr(IL.Plan, "door", door)
    monkeypatch.setattr(IL, "guards", lambda *a, **k: {})
    r = run("ice_lodge", world, tmp_path)
    assert any("keeper" in m or "inside shelter" in m for c, m in r.problems if c == "reach"), r.problems


def test_mutation_lodge_hole_cut_into_the_water(world, tmp_path, monkeypatch):
    # Removing this loses the proof that an air cell cut below the water line of the tarn is a leak found.
    import ice_lodge as IL
    orig = IL.stations

    def mutated(p, mask, taken):
        orig(p, mask, taken)
        for s in p.doc["stations"]:
            p.put(s["hole"][0], p.doc["tarn"]["water_top_y"], s["hole"][1], "minecraft:air")
    monkeypatch.setattr(IL, "stations", mutated)
    monkeypatch.setattr(IL, "guards", lambda *a, **k: {})
    r = run("ice_lodge", world, tmp_path)
    assert "containment" in r.checks()


def test_mutation_rookery_skerries_sheer(world, tmp_path, monkeypatch):
    # Removing this loses the proof that a tidal rock a swimmer cannot climb onto is found (a dropped tread).
    import rookery as RK
    orig = RK._cone

    def cone(de, r_base, r_top, base_y, top_y, exp):
        if exp == 0.7:                                              # the skerries' own profile constant
            return float(top_y) if de <= r_base * 0.5 else None
        return orig(de, r_base, r_top, base_y, top_y, exp)
    monkeypatch.setattr(RK, "_cone", cone)
    r = run("rookery", world, tmp_path, check=False)
    assert "reach" in r.checks() and "fatigue" in r.checks()


def test_mutation_hummock_clear_from_the_lake_level(world, tmp_path, monkeypatch):
    # Removing this loses the proof that a `replace #minecraft:replaceable` clear reaching the lake (it takes water)
    # is found: the flood rule data/hummock_mere.json names.
    import hummock_mere as HM
    orig = HM.plan

    def mutated(doc, r, g, wet):
        s = orig(doc, r, g, wet)
        c = s.clears[-1]
        s.clears[-1] = (c[0], s.L, c[2], c[3], c[4], c[5])
        return s
    monkeypatch.setattr(HM, "plan", mutated)
    r = run("hummock_mere", world, tmp_path, check=False)
    assert "pocket" in r.checks() or "containment" in r.checks()
    assert r.measured["water_cells_made_open"] > 0


def test_mutation_hummock_roots_waterlogged_in_the_air(world, tmp_path, monkeypatch):
    # Removing this loses the proof that a waterlogged block above the surface (a water source in the air) is found.
    import hummock_mere as HM
    monkeypatch.setattr(HM, "root", lambda s, x, y, z, L: "minecraft:mangrove_roots[waterlogged=true]")
    r = run("hummock_mere", world, tmp_path, check=False)
    assert "containment" in r.checks()


def test_mutation_hummock_mound_out_of_wading_reach(world, tmp_path, monkeypatch):
    # Removing this loses the proof that the crest a wader must reach is checked by reach, not assumed.
    import hummock_mere as HM
    orig = HM.mound_top

    def top(d, profile, L):
        t = orig(d, profile, L)
        return None if t is None else t + 3
    monkeypatch.setattr(HM, "mound_top", top)
    r = run("hummock_mere", world, tmp_path, check=False)
    assert any("crest" in m for c, m in r.problems if c == "reach"), r.problems
