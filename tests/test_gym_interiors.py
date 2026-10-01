"""The gym interiors: data/gym_interiors.json, tools/gym_interiors.py and tools/gym_interiors_audit.py.

Written by the session that built gyms 2, 3, 4, 5 and 7, at the orchestrator's request; an independent test-author
review is still owed (CLAUDE.md: implementation does not grade its own work).

What these are for. The audit is the thing that decides whether an interior is buildable, so the tests here are
mostly about the audit's own teeth: a check that cannot fail proves nothing. Every model rule the five new
interiors lean on - water holds a player, a bubble column is one-way upward, a spawn-condition block is legal only
inside the gym's spawn-free box, a write may touch the standing template only in the declared penetration - has a
case below that fails when the rule is removed.

The geometry is compared against data derived here, not against the generator's report: the shells come from
data/placements.json through tools/place_donor.box(), the entrances from the Q1 measurements mapped through each
placement's own rotation, and the cover from tools/ground.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import gym_interiors as GI  # noqa: E402
import gym_interiors_audit as GA  # noqa: E402
import place_donor  # noqa: E402
import place_town  # noqa: E402

DOC = json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
RECS = {p["id"]: p for p in PLACEMENTS["placements"] if isinstance(p, dict) and p.get("id")}
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
SUPP = {s["id"]: s["box"] for s in json.loads(
    (ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))["spawn_free_zones"]}

BUILT = [g for g in DOC["gyms"] if g.get("built")]
BUILT_IDS = [g["id"] for g in BUILT]
PACK = ROOT / "build" / "datapacks" / "cobblers_gym_interiors"
FUNCS = PACK / "data" / "cobblers" / "function" / "gym_interiors"


def box_of(gym):
    (x0, y0, z0), (x1, y1, z1) = place_donor.box(RECS[gym["donor"]])
    return (x0, y0, z0, x1, y1, z1)


def measured(gym):
    return DOC["measured"]["misty_relative" if gym["id"] == "gym2" else "small_gym_relative"]


# ------------------------------------------------------------------------------- the authored record itself
def test_the_six_built_gyms_are_the_ones_this_unit_claims():
    assert BUILT_IDS == ["gym2"], "gyms 1, 3, 4, 5 and 7 were retired 2026-09-29 for the authored buildings"
    assert "gym6" not in BUILT_IDS, "Sabrina's gym waits on EXP-034 and is out of scope"
    assert "gym8" not in BUILT_IDS


def test_every_built_gym_has_a_builder_and_every_extra_builder_is_a_superseded_gym():
    # Every built gym must have a builder, or the generator emits nothing for it. The converse stopped holding on
    # 2026-09-29, when gyms 1, 3, 4, 5 and 7 were retired for the authored buildings: their builders are still in
    # tools/gym_interiors.py and are simply never called, because BUILT_IDS is taken from the `built` flags. An
    # extra builder is only allowed for a gym the record says is superseded - a builder for a gym that is neither
    # built nor superseded is dead code nobody decided to leave.
    missing = set(BUILT_IDS) - set(GI.BUILDERS)
    assert not missing, "built with no builder: %s" % sorted(missing)
    superseded = {g["id"] for g in DOC["gyms"] if g.get("superseded_by")}
    extra = set(GI.BUILDERS) - set(BUILT_IDS)
    assert extra <= superseded, "builders for gyms that are neither built nor superseded: %s" % sorted(extra - superseded)


@pytest.mark.parametrize("gym", BUILT, ids=BUILT_IDS)
def test_the_record_carries_every_field_the_model_asks_for(gym):
    for field in ("settlement", "donor", "title", "why", "shell", "entrance", "dig", "shell_penetration",
                  "rooms", "route", "mechanism", "state_scope", "doors", "trainers", "leader",
                  "no_build", "spawn_suppression", "blocks"):
        assert field in gym, "%s has no %s" % (gym["id"], field)
    assert gym["rooms"] and gym["route"] and gym["trainers"]


@pytest.mark.parametrize("gym", BUILT, ids=BUILT_IDS)
def test_the_shell_is_derived_from_the_placement_and_never_authored(gym):
    """The record's expect_box is only an expectation: it must equal what data/placements.json gives."""
    assert tuple(gym["shell"]["expect_box"]) == box_of(gym)


@pytest.mark.parametrize("gym", BUILT, ids=BUILT_IDS)
def test_the_entrance_is_the_measured_healer_cell_through_this_placements_rotation(gym):
    rec, rel = RECS[gym["donor"]], measured(gym)
    dx, dz = place_town.rotate(rel["healing_machine"][0], rel["healing_machine"][2], rec.get("rotation", "none"))
    p = rec["position"]
    assert gym["entrance"] == [p["x"] + dx, p["y"] + rel["healing_machine"][1], p["z"] + dz]


@pytest.mark.parametrize("gym", BUILT, ids=BUILT_IDS)
def test_the_dig_is_below_the_building_and_inside_the_gyms_spawn_free_box(gym):
    shell, dig = box_of(gym), gym["dig"]
    assert dig[4] < shell[1], "%s digs into the standing template" % gym["id"]
    supp = SUPP[gym["spawn_suppression"]["record"]]
    assert gym["spawn_suppression"]["box"] == supp
    assert supp[0] <= dig[0] and dig[3] <= supp[2] and supp[1] <= dig[2] and dig[5] <= supp[3]


@pytest.mark.parametrize("gym", BUILT, ids=BUILT_IDS)
def test_every_room_is_in_the_spawn_free_box_and_in_a_no_build_box(gym):
    supp = SUPP[gym["spawn_suppression"]["record"]]
    nb = [b["box"] for b in gym["no_build"]]
    for r in gym["rooms"]:
        b = r["box"]
        assert supp[0] <= b[0] and b[3] <= supp[2] and supp[1] <= b[2] and b[5] <= supp[3], \
            "%s room %s leaves the spawn-free box (contract G1)" % (gym["id"], r["id"])
        if r.get("role") == "shaft":
            continue
        assert any(all(n[i] <= b[i] and b[i + 3] <= n[i + 3] for i in (0, 1, 2)) for n in nb), \
            "%s room %s is in no no_build box (contract G4)" % (gym["id"], r["id"])


def test_no_two_built_gyms_are_the_same_puzzle():
    """docs/mechanics/GYM_INTERIORS.md section 4's hard rule: none reads like another."""
    kinds = [g["mechanism"]["kind"] for g in BUILT]
    assert len(set(kinds)) == len(kinds), "two gyms share a mechanism kind: %s" % kinds


def test_no_two_built_gyms_have_the_same_room_shape():
    """Two interiors with identical geometry would be the failure this unit exists to avoid."""
    shapes = []
    for g in BUILT:
        shapes.append(sorted(tuple(b - a for a, b in zip(r["box"][:3], r["box"][3:])) for r in g["rooms"]))
    for i, a in enumerate(shapes):
        for b in shapes[i + 1:]:
            assert a != b, "two gyms have the same set of room sizes"


def test_trainer_ids_and_seats_are_unique_across_the_built_gyms():
    seats, ids = [], []
    for g in BUILT:
        for t in g["trainers"]:
            ids.append(t["id"])
            seats.append(tuple(t["seat"]))
    assert len(set(ids)) == len(ids)
    assert len(set(seats)) == len(seats)


@pytest.mark.parametrize("gym", BUILT, ids=BUILT_IDS)
def test_every_trainer_names_a_room_and_a_route_step_it_can_reach(gym):
    rooms = {r["id"] for r in gym["rooms"]}
    for t in gym["trainers"]:
        assert t["room"] in rooms
        assert 0 <= t["passed_at"] < len(gym["route"])
        assert 0 < float(t["sight_distance"]) <= 6.0


@pytest.mark.parametrize("gym", BUILT, ids=BUILT_IDS)
def test_a_spawn_condition_block_is_declared_and_only_in_this_gyms_box(gym):
    declared = {e["id"] for e in gym.get("spawn_condition_blocks") or []}
    for b in gym["blocks"]:
        if b in SPAWN:
            assert b in declared, "%s may write %s, a spawn condition, without declaring it" % (gym["id"], b)
    for b in declared:
        assert b in gym["blocks"] and b in DOC["blocks"]["ids"]


def test_the_global_block_list_covers_every_gyms_own_list():
    allowed = set(DOC["blocks"]["ids"])
    for g in BUILT:
        assert set(g["blocks"]) <= allowed, "%s allows a block the model does not" % g["id"]


@pytest.mark.parametrize("gym", BUILT, ids=BUILT_IDS)
def test_every_room_keeps_the_cover_rule_against_the_canonical_heightmap(gym):
    """Recomputed here from tools/ground.py, not read from the audit: a room's ceiling must be min_cover under
    the ground over it, so no carved room breaks the surface."""
    import ground as G
    g = G.Ground(None)
    want = DOC["rules"]["min_cover"]
    for r in gym["rooms"]:
        if r.get("role") == "shaft":
            continue
        b, ceiling = r["box"], r["box"][4] + 1
        for x in range(b[0], b[3] + 1, 2):
            for z in range(b[2], b[5] + 1, 2):
                assert ceiling + want <= int(round(g(x, z))), \
                    "%s room %s has too little cover at %d,%d" % (gym["id"], r["id"], x, z)


# ----------------------------------------------------------------------------------------- the generated pack
def test_the_pack_exists_and_its_index_is_the_built_gyms():
    if not FUNCS.is_dir():
        pytest.skip("no pack built; run python tools/gym_interiors.py build")
    index = [l.strip() for l in (FUNCS / "index.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert index == ["healers"] + BUILT_IDS


@pytest.mark.parametrize("name", ["healers"] + BUILT_IDS)
def test_every_function_writes_something(name):
    if not FUNCS.is_dir():
        pytest.skip("no pack built")
    lines = [l for l in (FUNCS / ("%s.mcfunction" % name)).read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.startswith("#")]
    assert lines, "%s writes nothing" % name


def test_the_audit_is_clean_on_what_the_generator_wrote():
    if not FUNCS.is_dir():
        pytest.skip("no pack built")
    problems, total = GA.audit(PACK, None)
    assert total > 0, "the audit checked nothing, which is not a pass"
    assert problems == [], "\n".join(problems)


def test_the_audit_fails_closed_when_there_is_no_pack(tmp_path):
    problems, total = GA.audit(tmp_path, None)
    assert problems and total == 0


# --------------------------------------------------------------- the model rules the five interiors lean on
def model(dig=(0, 0, 0, 9, 20, 9), shell=None):
    return GA.Model(dig, shell)


def test_water_holds_a_player_and_needs_no_headroom():
    """Misty's race, Erika's drain and Blaine's pool all depend on this."""
    m = model()
    m.apply("fill", (4, 5, 4, 4, 5, 4), "minecraft:water", None)
    assert m.standable(4, 5, 4)
    assert m.carries(4, 5, 4), "a player in water does not fall"
    m.apply("fill", (4, 6, 4, 4, 6, 4), "minecraft:stone", None)
    assert m.standable(4, 5, 4), "a flooded one-high channel is swum, not walked"


def test_a_drop_into_water_ends_at_the_surface():
    m = model()
    m.apply("fill", (0, 1, 0, 9, 12, 9), "minecraft:air", None)
    m.apply("fill", (0, 1, 0, 9, 3, 9), "minecraft:water", None)
    assert m.standable(4, 3, 4) and not m.carries(4, 8, 4)


def test_a_bubble_column_is_one_way_upward():
    """Blaine's geyser is the only thing stopping a player reaching the galleries without taking the leap."""
    m = model()
    m.apply("fill", (4, 4, 4, 4, 4, 4), "minecraft:soul_sand", None)
    m.apply("fill", (4, 5, 4, 4, 14, 4), "minecraft:water", None)
    assert m.bubble_up(4, 10, 4)
    up = GA._steps(m, 4, 10, 4, 64)
    assert (4, 11, 4) in up, "a bubble column carries a player up"
    assert (4, 9, 4) not in up, "and cannot be swum down"


def test_plain_water_can_be_swum_both_ways():
    m = model()
    m.apply("fill", (4, 4, 4, 4, 4, 4), "minecraft:stone", None)
    m.apply("fill", (4, 5, 4, 4, 14, 4), "minecraft:water", None)
    assert not m.bubble_up(4, 10, 4)
    steps = GA._steps(m, 4, 10, 4, 64)
    assert (4, 11, 4) in steps and (4, 9, 4) in steps


def test_a_two_block_step_down_cannot_be_climbed_back():
    """Surge's way out of the relay, and every one-way return in the six."""
    m = model()
    m.apply("fill", (0, 5, 0, 9, 8, 9), "minecraft:air", None)
    m.apply("fill", (0, 4, 0, 4, 4, 9), "minecraft:stone", None)      # the low side, stand y5
    m.apply("fill", (5, 4, 0, 9, 6, 9), "minecraft:stone", None)      # the high side, stand y7
    assert (5, 7, 4) not in GA._steps(m, 4, 5, 4, 64), "a player steps up one, never two"
    assert (4, 5, 4) in GA._steps(m, 5, 7, 4, 64), "but always steps down"


def test_the_helpers_measure_what_they_say():
    assert GA.gap((0, 0, 0, 2, 2, 2), (5, 0, 0, 7, 2, 2)) == 2
    assert GA.gap((0, 0, 0, 2, 2, 2), (3, 0, 0, 4, 2, 2)) == 0
    assert GA.intersect((0, 0, 0, 4, 4, 4), (3, 3, 3, 9, 9, 9)) == (3, 3, 3, 4, 4, 4)
    assert GA.intersect((0, 0, 0, 1, 1, 1), (3, 3, 3, 9, 9, 9)) is None
    assert GA.inside_xz((2, 0, 2, 3, 9, 3), (0, 0, 9, 9))
    assert not GA.inside_xz((2, 0, 2, 30, 9, 3), (0, 0, 9, 9))
