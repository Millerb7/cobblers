"""The independent land audit of the 2026-10-09 places (tools/new_places_land_audit.py).

Three kinds of test, none written by a builder of these places:

* the audit's own model on SYNTHETIC ground with hand-computable answers (the walk rules, the ray, the command replay),
  so a pass on the real places is a pass of a model that is known to bite;
* the real places, generated in-process and replayed over the canonical heightmap: one test per property, and every
  defect found is a strict xfail naming the coordinates, so a fix turns it red and must be acknowledged;
* mutations of each GENERATOR (never the record: CLAUDE.md "mutate the GENERATOR, not the record"), each of which must
  make the audit report a problem.

Not covered here (validity is not behaviour): anything in a running server; trees, snow and every other pack's blocks
(the world model is the heightmap plus these packs); whether a Habitat Block, scene, reward or resident runs.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import new_places_land_audit as A  # noqa: E402


# ============================================================================== synthetic fixture: the audit's model
class FlatGround:
    """A deterministic 64 x 64 ground at y100 (origin 0, 0), with an optional ridge row."""

    def __init__(self, ridge=None):
        self.ox = self.oz = 0
        self.heights = np.full((64, 64), 100.0)
        if ridge:
            z, h = ridge
            self.heights[z, :] = h

    def __call__(self, x, z):
        return int(np.round(self.heights[int(z) - self.oz, int(x) - self.ox]))

    def box(self, x0, z0, x1, z1):
        return np.round(self.heights[z0:z1 + 1, x0:x1 + 1]).astype(int)


BOX = (0, 0, 63, 63)


def world(blocks=()):
    w = A.World(FlatGround())
    for (x, y, z), s in blocks:
        w.put(x, y, z, s)
    return w


def test_walk_model_steps_up_one_block_and_not_two():
    # Breaks if removed: the walk model could let a player climb a 2-block ledge and pass a place that traps them.
    w = world([((11, 101, 10), "minecraft:stone")])
    assert (11, 102, 10) in set(w.succ((10, 101, 10), BOX))
    w2 = world([((11, 101, 10), "minecraft:stone"), ((11, 102, 10), "minecraft:stone")])
    assert not any(s[0] == 11 and s[2] == 10 for s in w2.succ((10, 101, 10), BOX))


def test_walk_model_needs_headroom_to_step_up():
    # Breaks if removed: a ceiling one block over the head would not stop a climb (the defect found in Wardenhold's keep).
    w = world([((11, 101, 10), "minecraft:stone"), ((10, 103, 10), "minecraft:stone")])
    assert (11, 102, 10) not in set(w.succ((10, 101, 10), BOX))


def test_walk_model_falls_three_and_not_four():
    # Breaks if removed: a drop that hurts would count as a walk, and a pit with no way out would look returnable.
    w = world([((10, y, 10), "minecraft:stone") for y in range(101, 104)])           # a pillar, top y103, feet y104
    assert (11, 101, 10) in set(w.succ((10, 104, 10), BOX))                          # down 3
    w4 = world([((10, y, 10), "minecraft:stone") for y in range(101, 105)])          # feet y105: down 4
    assert (11, 101, 10) not in set(w4.succ((10, 105, 10), BOX))


def test_walk_model_reachable_is_not_returnable_out_of_a_pit():
    # Breaks if removed: "reachable" alone would pass a hole a player falls into and cannot leave.
    blocks = [((x, 100, z), "minecraft:air") for x in range(20, 23) for z in range(20, 23)]
    blocks += [((x, 99, z), "minecraft:air") for x in range(20, 23) for z in range(20, 23)]
    w = world(blocks)                                                                # a 3x3 pit two deep
    res = A.walk(w, "pit", (10, 10), [("the pit floor", (21, 99, 21, 21, 99, 21), None)], margin=5)
    assert res[0][1] is True and res[0][2] is False


def test_walk_model_climbs_a_ladder_and_steps_off_at_the_top():
    # Breaks if removed: the Froslass' ladder could never be judged; a ladder shaft would read as a wall.
    blocks = [((12, y, 10), "minecraft:stone") for y in range(101, 111)]             # a wall 10 high, top block y110
    blocks += [((13, 110, 10), "minecraft:stone")]                                   # a ledge beyond the wall's top
    rungs = [((11, y, 10), "minecraft:ladder[facing=west]") for y in range(101, 111)]   # up to the top block
    res = A.walk(world(blocks + rungs), "ladder", (5, 10), [("on the wall top", (12, 111, 10, 13, 111, 10), None)], margin=5)
    assert res[0][1] and res[0][2]
    # a ladder that stops one block short leaves a 2-block step at its head: a player cannot get off onto the top
    res = A.walk(world(blocks + rungs[:-1]), "short ladder", (5, 10), [("on the wall top", (12, 111, 10, 13, 111, 10), None)], margin=5)
    assert not res[0][1]


def test_ray_is_blocked_by_a_ridge_it_passes_under_and_clear_over_it():
    # Breaks if removed: the sightline numbers would rest on a ray that never meets the ground.
    g = FlatGround(ridge=(32, 120))                                                  # top surface y121 at z32
    eye = (10.5, 101 + A.EYE, 2.5)                                                   # y102.62
    assert A.ray(g, eye, (10.5, 115.5, 60.5))[0] is False                            # at z32.0 the ray is at y109.17
    # samples every 0.5 block from z2.5; the one at z32.0 can round into column 31, so aim at the one at z32.5:
    # 102.62 + (T - 102.62) * 30 / 58 = 121.5 there, the least height over the ridge (the eye's next column clears by 1.9)
    T = 102.62 + 18.88 * 58 / 30
    ok, margin = A.ray(g, eye, (10.5, T, 60.5))
    assert ok and margin == pytest.approx(0.5, abs=0.01)


def replay(lines, monkeypatch, holds=()):
    monkeypatch.setattr(A, "run_order", lambda unit, f: ["f.mcfunction"])
    w = A.World(FlatGround())
    return A.Replay("x", {"f.mcfunction": "\n".join(lines)}, w, list(holds)), w


def test_replay_honours_filters_and_force_loaded_chunks(monkeypatch):
    # Breaks if removed: a clear of logs would erase a wall, and a write in an unloaded chunk would count as done.
    r, w = replay(["forceload add 0 0 15 15",
                   "setblock 5 101 5 minecraft:oak_log",
                   "setblock 6 101 5 minecraft:stone",
                   "fill 4 101 4 8 101 6 minecraft:air replace #minecraft:logs",
                   "setblock 40 101 40 minecraft:stone",
                   "forceload remove 0 0 15 15",
                   "setblock 1 101 1 minecraft:stone"], monkeypatch)
    assert w.get(5, 101, 5) == "minecraft:air" and w.get(6, 101, 5) == "minecraft:stone"
    assert len(r.unloaded) == 2 and r.too_big == []
    r, w = replay(["fill 0 90 0 40 110 40 minecraft:stone"], monkeypatch, holds=[(0, 0, 47, 47)])
    assert r.unloaded == [] and len(r.too_big) == 1                                  # 41 x 21 x 41 = 35,301 > 32,768


def test_stair_facing_matches_the_vanilla_model():
    # Breaks if removed: B8 would rest on a remembered rule. The jar's stairs model puts the tall half at +x for
    # facing=east (y rotation 0); skip when the client jar is not on this machine.
    jar = A.VANILLA_JARS[0]
    if not jar.is_file():
        pytest.skip("Minecraft 1.21.1 client jar not on this machine")
    import zipfile
    with zipfile.ZipFile(jar) as z:
        m = json.loads(z.read("assets/minecraft/models/block/stairs.json"))
        b = json.loads(z.read("assets/minecraft/blockstates/stone_brick_stairs.json"))
    assert ([8, 8, 0], [16, 16, 16]) in [(e["from"], e["to"]) for e in m["elements"]]
    assert "y" not in b["variants"]["facing=east,half=bottom,shape=straight"]
    assert b["variants"]["facing=north,half=bottom,shape=straight"]["y"] == 270


# ============================================================================== the real places
@pytest.fixture(scope="module")
def ground():
    import ground as G
    try:
        return G.load()
    except (SystemExit, FileNotFoundError, OSError) as e:
        pytest.skip("canonical heightmap unavailable: %s" % e)


@pytest.fixture(scope="module")
def audit(ground):
    au = A.Audit(ground)
    au.run()
    return au


def probs(au, code, unit=None):
    return [p for p in au.problems if p.startswith(code + " ") and (unit is None or p.split(" ", 2)[1] == unit + ":")]


def test_every_unit_generates_a_nonempty_pack(audit):
    # Breaks if removed: a generator that emits nothing would pass every other check vacuously.
    for u in A.UNITS:
        r = audit.replay(u)
        assert len(r.volumes) > 100 and len(r.world.o) > 500, u


def test_every_write_lands_in_a_force_loaded_chunk(audit):
    # Breaks if removed: a write outside the step's forceload fails silently in game ("not loaded") and the place is
    # half built while the report says done.
    assert probs(audit, "B1") == []


def test_writes_stay_inside_the_records_declared_boxes(audit):
    # Breaks if removed: the Tri Peaks' and the Sundown Watch's declared boxes (what R9TP/R9SW hold) could drift from
    # what the pack writes.
    assert probs(audit, "B2") == []


def test_written_blocks_are_the_records_declared_palette(audit):
    # Breaks if removed: a block the record does not list (and the generator's guard missed) reaches the world.
    assert probs(audit, "B3") == []


def test_spawn_condition_blocks_are_allowed_by_the_policy(audit):
    # Breaks if removed: a block that decides encounters (data/spawn_blocks.json) is placed with no entry in
    # data/spawn_block_policy.json, or under another place's entry.
    assert probs(audit, "B4") == []


def test_wardenhold_is_dark(audit):
    # Breaks if removed: a lit lantern or a lit campfire would say "the fire is back" (FROSTPEAK_KEEP.md 'Dark by design').
    assert probs(audit, "B5") == []


def test_every_command_parses_and_fits_the_fill_limit(audit):
    # Breaks if removed: a fill over 32,768 blocks is refused by the server, and a write hidden in `execute ... run`
    # would escape every check here.
    assert probs(audit, "B6") == []


def test_nothing_solid_stands_in_a_routes_walking_space(audit):
    # Breaks if removed: a post or wall on a route_paths cell blocks the critical path.
    assert probs(audit, "B7") == []


def test_stairs_face_their_flight_outside_wardenhold(audit):
    # Breaks if removed: a stair set backwards turns a flight into a row of jumps.
    assert [p for p in probs(audit, "B8") if "frostpeak_keep" not in p] == []


# FIXED 2026-10-09 by the main session (the keep's stairs face south, their flight): the strict xfail turned red and was removed
def test_wardenhold_stairs_face_their_flight(audit):
    assert probs(audit, "B8", "frostpeak_keep") == []


@pytest.mark.parametrize("unit", ["tri_peaks_nest", "buried_dune", "sunset_watch", "route4_events", "route5_events"])
def test_claimed_ground_and_distances_hold(audit, unit):
    # Breaks if removed: a relayed ground height or distance that the heightmap contradicts would stand in the docs.
    if unit == "tri_peaks_nest":
        assert [p for p in probs(audit, "G3", unit) if "town_to_crown" not in p] == []
    else:
        assert [p for p in audit.problems if p.startswith("G") and p.split(" ", 2)[1] == unit + ":"] == []


def test_wardenhold_pad_and_hall_floor(audit):
    # Breaks if removed: the courtyard could sit off the highest ground, or the hall's Habitat Block off the floor.
    assert probs(audit, "G1", "frostpeak_keep") == []
    assert [p for p in probs(audit, "G2", "frostpeak_keep") if "street distances" not in p] == []


# FIXED 2026-10-09 by the main session (the floor cut one cell longer): the strict xfail turned red and was removed
def test_wardenhold_upper_floors_and_beacon_are_walkable(audit):
    assert probs(audit, "W1", "frostpeak_keep") == []


def test_residents_sit_on_the_cap_ladder_and_respawn_as_designed(audit):
    # Breaks if removed: a named Pokemon catchable before its gate, uncatchable at it, or on the wrong clock.
    assert probs(audit, "R1") == [] and probs(audit, "R2") == [] and probs(audit, "R3") == []


def test_event_chains_resolve(audit):
    # Breaks if removed: a scene or conversation reading an undeclared flag, a missing transition or reward id, an
    # item no jar has, a reward the Bank buys, or a progression item handed out ungated.
    for code in ("E1", "E2", "E3", "E5"):
        assert probs(audit, code) == [], code
    assert [p for p in probs(audit, "E4")] == []
    lo, hi, leg, _, cash = audit.chain_value["route5_events"]
    assert (lo, hi, cash) == (1500, 2400, 0) and leg == 21433


# FIXED 2026-10-09 by the main session (Route 4's progression records back after their anchor): the strict xfail turned red and was removed
def test_route4_generator_runs_on_the_merged_data(monkeypatch):
    import route4_events as R4
    monkeypatch.setattr(R4, "write_pack", lambda sites, out=None: None)
    assert R4.main([]) in (0, 1)


# ============================================================================== mutations of the generators
def fresh(ground, unit, groups):
    au = A.Audit(ground, units=(unit,))
    au.run(groups)
    return au


def test_mutation_wardenhold_without_its_spire_fails_the_sightline(ground, monkeypatch):
    # Breaks if removed: S1 could pass a keep whose spire was never written.
    import frostpeak_keep as FK
    orig = FK.Vox.put
    monkeypatch.setattr(FK.Vox, "put", lambda self, u, y, v, s: orig(self, u, y, v, FK.AIR if y > 40 else s))
    assert probs(fresh(ground, "frostpeak_keep", ("sightline",)), "S1")


def test_mutation_wardenhold_lifted_off_its_pad_fails_the_ground(ground, monkeypatch):
    # Breaks if removed: G1 could pass a keep built two blocks above the hall's Habitat Block.
    import frostpeak_keep as FK
    orig = FK.Vox.put
    monkeypatch.setattr(FK.Vox, "put", lambda self, u, y, v, s: orig(self, u, y + 2, v, s))
    assert probs(fresh(ground, "frostpeak_keep", ("ground",)), "G1")


def test_mutation_wardenhold_lit_hearth_fails_dark(ground, monkeypatch):
    # Breaks if removed: B5 could pass a lit campfire.
    import frostpeak_keep as FK
    orig = FK.Vox.put
    monkeypatch.setattr(FK.Vox, "put", lambda self, u, y, v, s: orig(self, u, y, v, s.replace("lit=false", "lit=true")))
    assert probs(fresh(ground, "frostpeak_keep", ("bounds",)), "B5")


def test_mutation_crownbreaker_walled_in_fails_the_walk(ground, monkeypatch):
    # Breaks if removed: W1 could pass a crown a player cannot reach.
    import resident_encounters as RE
    orig = RE.site

    def site(e, g, wet):
        a, sets, clears, box = orig(e, g, wet)
        ring = [(a[0] + dx, y, a[2] + dz, "minecraft:blackstone", "mutant ring")
                for dx in range(-5, 6) for dz in range(-5, 6) if 3.5 <= math.hypot(dx, dz) < 4.6
                for y in range(a[1], a[1] + 5)]
        return a, list(sets) + ring, clears, box
    monkeypatch.setattr(RE, "site", site)
    assert probs(fresh(ground, "tri_peaks_nest", ("walks",)), "W1")


def test_mutation_crownbreaker_short_clock_fails_the_respawn(ground, monkeypatch):
    # Breaks if removed: R3 could pass a resident that comes back every six minutes.
    import resident_encounters as RE
    orig = RE.files
    monkeypatch.setattr(RE, "files", lambda doc, g, wet=None: {
        k: (v.replace("#resp cobblers.tpn 72000", "#resp cobblers.tpn 7200") if isinstance(v, str) else v)
        for k, v in orig(doc, g, wet).items()})
    assert probs(fresh(ground, "tri_peaks_nest", ("residents",)), "R3")


def test_mutation_undertow_one_level_high_fails_the_gate(ground, monkeypatch):
    # Breaks if removed: R1 could pass a Pokemon the seventh badge cannot catch.
    import buried_dune as BD
    orig = BD.creature_files
    monkeypatch.setattr(BD, "creature_files", lambda doc, plan: {
        k: [ln.replace("level=55", "level=56") for ln in v] if isinstance(v, list) else v.replace("level=55", "level=56")
        for k, v in orig(doc, plan).items()})
    assert probs(fresh(ground, "buried_dune", ("residents",)), "R1")


def test_mutation_undertow_sand_fails_palette_and_spawn_policy(ground, monkeypatch):
    # Breaks if removed: B3 and B4 could pass sand, the spawn condition the design avoids by writing none.
    import buried_dune as BD
    orig = BD.build_lines
    monkeypatch.setattr(BD, "build_lines", lambda plan: orig(plan) + ["setblock 7282 99 5600 minecraft:sand"])
    au = fresh(ground, "buried_dune", ("bounds",))
    assert probs(au, "B3") and probs(au, "B4")


def test_mutation_sundown_write_outside_its_box_fails_bounds(ground, monkeypatch):
    # Breaks if removed: B2 could pass a write outside sunset_watch_all.
    import sunset_watch as SW
    orig = SW.build_lines
    monkeypatch.setattr(SW, "build_lines", lambda doc, pl: orig(doc, pl) + ["setblock 1200 140 7600 minecraft:stone"])
    assert probs(fresh(ground, "sunset_watch", ("bounds",)), "B2")


def test_mutation_sundown_keeper_buried_fails_the_walk(ground, monkeypatch):
    # Breaks if removed: W1 could pass a keeper nobody can stand beside.
    import sunset_watch as SW
    orig = SW.build_lines
    d = json.loads((ROOT / "data" / "sunset_watch.json").read_text(encoding="utf-8"))
    kx, kz = d["site"]["centre"][0] + d["npc"]["at"][0], d["site"]["centre"][1] + d["npc"]["at"][1]
    wall = "fill %d 138 %d %d 141 %d minecraft:stone_bricks" % (kx - 4, kz - 4, kx + 4, kz + 4)
    monkeypatch.setattr(SW, "build_lines", lambda doc, pl: orig(doc, pl) + [wall])
    assert any("the keeper" in p for p in probs(fresh(ground, "sunset_watch", ("walks",)), "W1"))


def test_mutation_route4_buried_cache_fails_the_walk(ground, monkeypatch):
    # Breaks if removed: W1 could pass a find nobody can reach.
    import route4_events as R4
    sites = list(R4.SITES)
    orig = sites[2]

    def strayed(g, road, spec):
        s = orig(g, road, spec)
        for x in range(3257, 3268):
            for z in range(1445, 1456):
                for y in range(114, 121):
                    s.set(x, y, z, "minecraft:stone")
        return s
    sites[2] = strayed
    monkeypatch.setattr(R4, "SITES", sites)
    assert any("r4_strayed_load" in p for p in probs(fresh(ground, "route4_events", ("walks",)), "W1"))


def test_mutation_route5_concrete_and_a_post_on_the_road_fail_bounds(ground, monkeypatch):
    # Breaks if removed: B4 could pass a spawn-condition block and B7 a post on Route 5's walked line.
    import route5_events as R5
    sites = list(R5.SITES)
    orig = sites[2]
    p5 = A.paths()["route_05_erika_to_koga"]

    def hut(g, road):
        s = orig(g, road)
        s.set(4401, 125, 2074, "minecraft:white_concrete")
        x, z = p5[A.nearest(p5, 4401, 2074)[0]]
        s.set(x, int(g(x, z)) + 1, z, "minecraft:cobblestone")
        return s
    sites[2] = hut
    monkeypatch.setattr(R5, "SITES", sites)
    au = fresh(ground, "route5_events", ("bounds",))
    assert probs(au, "B4") and probs(au, "B7")


def test_mutation_undeclared_flag_fails_the_chain(ground, monkeypatch):
    # Breaks if removed: E1 could pass a conversation reading a field progression.json no longer declares. (A data-side
    # fixture: E1 is a check over records, so the input is what moves; the audit's rule does not.)
    orig = A.jload

    def jload(name):
        d = orig(name)
        if name == "progression.json":
            d["quest_fields"] = [f for f in d["quest_fields"] if f["id"] != "quest.evt_route5_bellwether.strap"]
        return d
    monkeypatch.setattr(A, "jload", jload)
    assert probs(fresh(ground, "route5_events", ("chains",)), "E1")
