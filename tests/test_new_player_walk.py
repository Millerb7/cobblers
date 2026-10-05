"""tools/new_player_walk.py: the fresh player's walk, on a synthetic world small enough to compute by hand.

Nothing here reads the real heightmap, the real packs or the Cobblemon jar: every input is a fixture written below
(a flat 260 x 120 heightmap at y70 with sea at y62, a one-species dex, a one-starter config, one route, one gym), so a
step count can be checked against arithmetic and each mutation names the one thing it breaks.

NOT COVERED (validity is not behaviour, .claude/rules/testing.md): whether a player can actually walk, whether
Cobblemon applies the forms, whether rctmod spawns the leader, fires the advancement or moves the cap. The real-data
run and the generator mutations that proved each stage bites are recorded in the commit that added this file.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import new_player_walk as W  # noqa: E402


# ------------------------------------------------------------------------------------------------- the fixture

class FlatGround:
    """(x, z) -> y over a numpy (z, x) array with its origin at 0, 0, and the box() the walk reads."""

    def __init__(self, h):
        self.h = h

    def __call__(self, x, z):
        return int(self.h[z, x])

    def box(self, x0, z0, x1, z1):
        return self.h[z0:z1 + 1, x0:x1 + 1]


def flat(y=70, w=260, h=120):
    return np.full((h, w), y, dtype=np.int64)


def mon(name, base, moves):
    return {"name": name, "primaryType": "Normal", "abilities": ["none"], "evolutions": [], "weight": 100,
            "baseStats": {k: base for k in ("hp", "attack", "defence", "special_attack", "special_defence", "speed")},
            "moves": moves, "implemented": True}


DEX = {"hero": mon("Hero", 90, ["1:tackle"]), "dummy": mon("Dummy", 30, ["1:tackle"]),
       "sidekick": mon("Sidekick", 60, ["1:tackle"])}
MOVES = {"tackle": {"power": 40, "category": "Physical", "type": "Normal", "accuracy": 100, "contact": True},
         "growl": {"power": 0, "category": "Status", "type": "Normal", "accuracy": 100, "contact": False}}
CHART = {"normal": {}}

ROUTE = [[x, 60] for x in range(60, 181)]          # 121 points along z60
OAK = [52, 71, 60]
SPAWN = (45, 71, 60)
LOT = [200, 50, 215, 70]


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")


def team(*levels, species="dummy"):
    return {"name": {"literal": "x"}, "team": [{"species": species, "moveset": ["tackle"], "level": lv}
                                                for lv in levels]}


def make_world(tmp, *, novice=(6,), forced=True, brock=(18, 20), misty=(25,), form_moves=("1:tackle",),
               aspect="s1", spawner=True, loot='loot give @s loot cobblers:first_win/kanto_brock',
               badge="cobbleversebadges:kanto_boulder_badge"):
    root, packs = tmp / "root", tmp / "root" / "packs"
    write(root / "data" / "route_paths.json", {"paths": {"route_01_a_to_b": ROUTE}})
    write(root / "data" / "npc_seats.json", {"seats": [{"id": "npc_main_pallet_oak", "at": OAK}]})
    write(root / "data" / "gym_buildings" / "gym1.json", {"site": {"lot_rect": LOT}})
    write(root / "data" / "gym_interiors.json", {"gyms": []})
    write(root / "modpack" / "config" / "rctmod-server.toml", "initialLevelCap = 20\nrelativeLevelCap = 0\n")
    write(root / "modpack" / "config" / "cobblemon" / "starters.json",
          {"starters": [{"name": "c", "pokemon": ["hero level=5 aspect=s1"]}]})
    write(packs / "cobblers_mythical_starters" / "data" / "cobblers" / "species_additions" / "hero.json",
          {"target": "cobblemon:hero", "forms": [{"name": "Starter", "aspects": [aspect], "baseStats":
                                                  DEX["hero"]["baseStats"], "moves": list(form_moves),
                                                  "evolutions": []}]})
    write(packs / "cobblers_towns" / "data" / "cobblers" / "function" / "towns" / "hometown.mcfunction",
          "say hi\nsetworldspawn %d %d %d\n" % SPAWN)
    write(packs / "cobblers_dialogue" / "data" / "cobblers" / "npcs" / "npc_main_pallet_oak.json", {})
    tr = packs / "cobblers_trainers" / "data"
    write(tr / "rctmod" / "trainers" / "route_01_trainer_01.json", team(*novice))
    write(tr / "rctmod" / "mobs" / "trainers" / "single" / "route_01_trainer_01.json",
          {"forceBattleOnSight": forced, "forceBattleMaxDistance": 8.0})
    write(tr / "cobblers" / "function" / "trainers" / "cycle.mcfunction",
          'execute as @e[type=rctmod:trainer,x=100.5,y=71,z=62.5,distance=..24,nbt={TrainerId:"route_01_trainer_01",'
          'InBattle:0b}] positioned 100.5 71 62.5 unless entity @s[distance=..0.75] run tp @s 100.5 71 62.5\n')
    write(tr / "rctmod" / "trainers" / "kanto_brock.json", team(*brock))
    write(tr / "rctmod" / "trainers" / "kanto_misty.json", team(*misty))
    pool = packs / "cobblers_spawns" / "data" / "cobblers" / "spawn_pool_world" / "routes" / "route_01_a_to_b.json"
    write(pool, {"spawns": [
        {"pokemon": "dummy", "level": "4-12", "condition": {"minX": 60, "maxX": 70, "minZ": 55, "maxZ": 65}},
        {"pokemon": "sidekick", "level": "10-14", "condition": {"minX": 165, "maxX": 175, "minZ": 55, "maxZ": 65}}]})
    write(packs / "cobblers_gym_buildings" / "data" / "cobblers" / "function" / "gym_buildings" / "gym1.mcfunction",
          'setblock 207 72 60 rctmod:trainer_spawner{TrainerIds:["kanto_brock"]}\n' if spawner else "say none\n")
    prog = packs / "cobblers_progression" / "data" / "cobblers"
    for n, tid in ((1, "kanto_brock"), (2, "kanto_misty")):
        write(prog / "advancement" / "flag" / ("gym%d_cleared.json" % n),
              {"criteria": {"d": {"trigger": "rctmod:defeat_count", "conditions": {"trainer_ids": [tid], "count": 1}}},
               "rewards": {"function": "cobblers:flag/gym%d_cleared/granted" % n}})
    write(prog / "function" / "flag" / "gym1_cleared" / "granted.mcfunction", "function cobblers:x\n%s\n" % loot)
    write(prog / "loot_table" / "first_win" / "kanto_brock.json",
          {"pools": [{"rolls": 1, "entries": [{"type": "minecraft:item", "name": badge}]}]})
    return root, packs


def inputs(root, packs, ground=None, water=(62, {}), audit=None, oak=(0, "oak_starter_audit: ok -- 0 problem(s)")):
    return W.Inputs(root=root, packs=packs, ground=FlatGround(ground if ground is not None else flat()),
                    battle=(DEX, MOVES, CHART), raw=DEX, water=water,
                    gym_audit=audit or ({"gym1": []}, {"gym1": True}), oak=lambda _inp: oak)


def stage(stages, sid):
    return next(s for s in stages if s.id == sid)


def check(st, name):
    return next(c for c in st.checks if c["check"] == name)


# ------------------------------------------------------------------------------------------------- the walk model

def test_walk_counts_four_connected_steps_on_flat_ground(tmp_path):
    # without this, a step count could be anything and "reached" would be the only claim the walk makes
    inp = inputs(*make_world(tmp_path))
    ev = W.walk(inp, [(45, 60)], [(51, 60)])
    assert ev["reached"] and ev["steps"] == 6
    ev = W.walk(inp, [(45, 60)], [(55, 70)])
    assert ev["steps"] == 10 + 10                   # 4-connected: |dx| + |dz|


def test_a_two_block_rise_stops_the_walk_and_a_one_block_stair_opens_it(tmp_path):
    # without this, the climb rule could admit a wall a player cannot jump
    g = flat()
    g[:, 100:] = 72
    inp = inputs(*make_world(tmp_path), ground=g)
    assert not W.walk(inp, [(90, 60)], [(110, 60)])["reached"]
    g[80, 100] = 71                                 # one stair column at z80
    ev = W.walk(inputs(*make_world(tmp_path), ground=g), [(90, 60)], [(110, 60)])
    assert ev["reached"] and ev["steps"] == 20 + 2 * 20     # across, plus the detour to z80 and back


def test_a_three_block_drop_is_walked_down_and_never_up(tmp_path):
    # without this, the walk would be symmetric and miss a ledge a player can leave but not return over
    g = flat()
    g[:, 100:] = 73
    inp = inputs(*make_world(tmp_path), ground=g)
    assert W.walk(inp, [(110, 60)], [(90, 60)])["reached"]
    assert not W.walk(inp, [(90, 60)], [(110, 60)])["reached"]


def test_sea_and_painted_lakes_are_not_walked(tmp_path):
    # without this, a route through the sea or a lake would read as walkable
    g = flat()
    g[:, 100] = 60                                  # a trench under sea level y62
    assert not W.walk(inputs(*make_world(tmp_path), ground=g), [(90, 60)], [(110, 60)])["reached"]
    lake = {"l": {"level_y": 75, "basin": [[(98, -5), (102, -5), (102, 130), (98, 130)]]}}
    assert not W.walk(inputs(*make_world(tmp_path), water=(62, lake)), [(90, 60)], [(110, 60)])["reached"]
    dry = {"l": {"level_y": 65, "basin": lake["l"]["basin"]}}       # its level is under the ground: nothing painted
    assert W.walk(inputs(*make_world(tmp_path), water=(62, dry)), [(90, 60)], [(110, 60)])["reached"]


def test_the_corridor_confines_a_route_walk_and_names_where_it_stuck(tmp_path):
    # without this, a route could pass by a detour far off its walked line, or fail without saying where
    g = flat()
    g[20:100, 100] = 90                             # a wall across the line, open only at z<20 and z>=100
    inp = inputs(*make_world(tmp_path), ground=g)
    line = [tuple(p) for p in ROUTE]
    ev = W.walk(inp, [line[0]], [line[-1]], line=line, radius=16)
    assert not ev["reached"]
    assert ev["stuck_after"] == [99, 60] and ev["stuck_walked"] == 39
    assert W.walk(inp, [line[0]], [line[-1]])["reached"]           # the free walk goes round


# ------------------------------------------------------------------------------------------------- the stages

def run(tmp_path, only=None, **kw):
    ground = kw.pop("ground", None)
    audit = kw.pop("audit", None)
    oak = kw.pop("oak", (0, "oak_starter_audit: ok -- 0 problem(s)"))
    root, packs = make_world(tmp_path, **kw)
    return W.run(inputs(root, packs, ground=ground, audit=audit, oak=oak), only)


def test_the_fixture_player_reaches_and_beats_gym_1(tmp_path):
    # without this, none of the failures below would mean anything: they must be the mutation, not the fixture
    stages = run(tmp_path, {"spawn_to_oak", "starter", "route_1", "gym_1"})
    assert [(s.id, s.verdict) for s in stages] == [("spawn_to_oak", "PASS"), ("starter", "PASS"),
                                                   ("route_1", "PASS"), ("gym_1", "PASS")]
    assert check(stage(stages, "spawn_to_oak"), "walk_spawn_to_oak")["evidence"]["steps"] == 6
    r1 = stage(stages, "route_1")
    assert check(r1, "walk_corridor")["evidence"]["steps"] == 120
    assert check(r1, "walk_to_gym_lot")["evidence"]["steps"] == 200 - 2 - 180   # to the lot's ring at x198
    assert "route_01_trainer_01" in check(r1, "must_pass_trainers")["evidence"]["summary"]
    # the novice is fought at the wilds met before x100 (dummy, up to L12), not the route's top (sidekick, L14)
    assert check(r1, "beat:route_01_trainer_01")["evidence"]["by_starter"]["hero"]["level"] == 12
    assert check(stage(stages, "gym_1"), "cap_advances")["verdict"] == "PASS"


def test_a_forced_route_trainer_the_starter_cannot_beat_fails_route_1(tmp_path):
    # without this, a first forced fight above the starter's reach would ship (CRITICAL_PATH_WALK_1's risk)
    st = stage(run(tmp_path, {"route_1"}, novice=(60,)), "route_1")
    assert st.verdict == "FAIL"
    assert check(st, "beat:route_01_trainer_01")["evidence"]["summary"].endswith("loses: ['hero']")


def test_an_unforced_trainer_is_not_must_pass_but_is_reported(tmp_path):
    # without this, every optional trainer would gate the walk, or a hard one would vanish without a word
    st = stage(run(tmp_path, {"route_1"}, novice=(60,), forced=False), "route_1")
    assert st.verdict == "PASS"
    assert any("optional trainer route_01_trainer_01" in w for w in st.warnings)


def test_a_starter_with_no_damaging_move_fails_the_starter_stage(tmp_path):
    # without this, a form shipping only status moves (vanilla Cosmog: Splash, Teleport) would pass
    st = stage(run(tmp_path, {"starter"}, form_moves=("1:growl",)), "starter")
    assert st.verdict == "FAIL" and "0 damaging" in check(st, "moves:hero")["evidence"]


def test_a_config_aspect_with_no_built_form_fails_the_starter_stage(tmp_path):
    # without this, the config could name an aspect the forms pack does not carry and fall back to vanilla
    st = stage(run(tmp_path, {"starter"}, aspect="other"), "starter")
    assert st.verdict == "FAIL" and "no form with that aspect" in check(st, "moves:hero")["evidence"]


def test_oaks_audit_failing_fails_the_starter_stage(tmp_path):
    # without this, Oak not offering the screen would leave the starter stage green
    st = stage(run(tmp_path, {"starter"}, oak=(1, "PROBLEM P2 nothing\noak_starter_audit: FAIL -- 1 problem(s)")),
               "starter")
    assert check(st, "oak_offers_screen")["verdict"] == "FAIL"
    assert check(st, "oak_offers_screen")["evidence"]["problems"] == ["PROBLEM P2 nothing"]


def test_no_spawner_for_the_leader_fails_gym_1(tmp_path):
    # without this, a gym whose leader is never spawned would pass on its roster alone
    assert check(stage(run(tmp_path, {"gym_1"}, spawner=False), "gym_1"), "leader_spawner")["verdict"] == "FAIL"


def test_only_blocking_gym_audit_codes_fail_the_hall(tmp_path):
    # without this, a seat overlap would stop the walk, or an unreachable leader would not
    audit = ({"gym1": [("unreachable", "gym1 ROUTE: the leader's spawner cannot be reached")]}, {"gym1": True})
    assert check(stage(run(tmp_path, {"gym_1"}, audit=audit), "gym_1"), "hall_walk")["verdict"] == "FAIL"
    audit = ({"gym1": [("data_claim", "gym1 OVERLAP: a seat inside")]}, {"gym1": True})
    st = stage(run(tmp_path, {"gym_1"}, audit=audit), "gym_1")
    assert check(st, "hall_walk")["verdict"] == "PASS" and any("OVERLAP" in w for w in st.warnings)


def test_a_commented_out_loot_line_or_a_badgeless_table_fails_the_badge(tmp_path):
    # without this, the first version passed a granted function whose loot line was commented out
    st = stage(run(tmp_path, {"gym_1"}, loot="# loot give @s loot cobblers:first_win/kanto_brock"), "gym_1")
    assert check(st, "badge_wired")["verdict"] == "FAIL"
    st = stage(run(tmp_path / "b", {"gym_1"}, badge="tmcraft:tm_bide"), "gym_1")
    assert check(st, "badge_wired")["verdict"] == "FAIL"


def test_a_leader_too_strong_at_the_cap_fails_gym_1(tmp_path, monkeypatch):
    # without this, a leader no starter-and-catchables team can beat at the cap would pass
    st = stage(run(tmp_path, {"gym_1"}, brock=(20,) * 6), "gym_1")
    assert check(st, "beat:kanto_brock")["verdict"] == "PASS"     # six weak dummies at the cap: still beaten
    # ... but not at L14, the top wild level on route 1: the six levels between are XP, which is not modelled
    assert check(st, "cap_reachable")["verdict"] == "NOT_MODELLED" and st.verdict == "NOT_MODELLED"
    monkeypatch.setitem(DEX, "titan", mon("Titan", 200, ["1:tackle"]))
    root, packs = make_world(tmp_path / "b")
    p = packs / "cobblers_trainers" / "data" / "rctmod" / "trainers" / "kanto_brock.json"
    p.write_text(json.dumps(team(*(20,) * 6, species="titan")), encoding="utf-8")
    st = stage(W.run(inputs(root, packs), {"gym_1"}), "gym_1")
    assert check(st, "beat:kanto_brock")["verdict"] == "FAIL" and st.verdict == "FAIL"


def test_a_cap_that_does_not_rise_after_the_badge_fails(tmp_path):
    # without this, a next leader at or under this cap (no cap advance) would pass
    assert check(stage(run(tmp_path, {"gym_1"}, misty=(20,)), "gym_1"), "cap_advances")["verdict"] == "FAIL"


def test_a_missing_built_artifact_fails_never_passes(tmp_path):
    # without this, a pack prepare did not build would read as a clean stage
    root, packs = make_world(tmp_path)
    (packs / "cobblers_towns" / "data" / "cobblers" / "function" / "towns" / "hometown.mcfunction").unlink()
    st = stage(W.run(inputs(root, packs), {"spawn_to_oak"}), "spawn_to_oak")
    assert st.verdict == "FAIL" and check(st, "spawn_set")["verdict"] == "FAIL"


# ------------------------------------------------------------------------------------------------- the zones

def zone_pack(packs, body, admit="scoreboard players set @s cob_pass_z9 1\n", box=(100, 104, -64, 320, 0, 119)):
    """A built zone z9 over x100-104 (every z of the flat world), its function `body`, its admit function `admit`."""
    d = packs / "cobblers_rift_zones" / "data" / "cobblers"
    x0, x1, y0, y1, z0, z1 = box
    write(d / "advancement" / "rift_zones" / "z9_zone.json",
          {"criteria": {"here": {"trigger": "minecraft:location", "conditions": {"player": [
              {"condition": "minecraft:any_of", "terms": [{"condition": "minecraft:entity_properties", "entity": "this",
                                                          "predicate": {"location": {"position": {
                                                              "x": {"min": x0, "max": x1}, "y": {"min": y0, "max": y1},
                                                              "z": {"min": z0, "max": z1}}}}}]}]}}},
           "rewards": {"function": "cobblers:rift_zones/z9/zone"}})
    write(d / "function" / "rift_zones" / "z9" / "zone.mcfunction", body)
    write(d / "function" / "rift_zones" / "z9" / "admit.mcfunction", admit)


ADMIT = ("execute if entity @s[advancements={cobblers:flag/gym1_cleared=true}] unless score @s cob_pass_z9 matches 1.. "
         "run function cobblers:rift_zones/z9/admit\n")
TURN = ("execute if entity @s[gamemode=!creative] unless score @s cob_pass_z9 matches 1.. "
        "run function cobblers:rift_zones/z9/turn_back\n")
GRANT_LATE = ("execute if entity @s[advancements={cobblers:flag/gym1_cleared=true}] "
              "run function cobblers:rift_zones/z9/admit\n")


def test_a_zone_admits_a_flag_only_on_a_line_before_its_turn_back(tmp_path):
    # without this, a grant that runs after the teleport (CRITICAL_PATH_WALK_2 item 1's shape) would read as a pass
    root, packs = make_world(tmp_path)
    zone_pack(packs, "advancement revoke @s only cobblers:rift_zones/z9_zone\n" + ADMIT + TURN)
    z = W.zone_checks(packs)["z9"]
    assert z["turns_back"] and z["objective"] == "cob_pass_z9"
    assert z["boxes"] == [(100, 104, -64, 320, 0, 119)]
    assert W.zone_passable(z, {"cobblers:flag/gym1_cleared"}) and not W.zone_passable(z, set())
    zone_pack(packs, TURN + GRANT_LATE)
    assert not W.zone_passable(W.zone_checks(packs)["z9"], {"cobblers:flag/gym1_cleared"})


def test_an_admit_that_never_sets_the_pass_score_admits_nobody(tmp_path):
    # without this, a line that calls an admit function writing the wrong objective would count as a pass
    root, packs = make_world(tmp_path)
    zone_pack(packs, ADMIT + TURN, admit="scoreboard players set @s cob_pass_z1 1\n")
    assert not W.zone_passable(W.zone_checks(packs)["z9"], {"cobblers:flag/gym1_cleared"})


def test_a_zone_function_no_advancement_calls_is_not_enforced(tmp_path):
    # without this, a held zone (built functions, no zone advancement: z4 today) would close the walk
    root, packs = make_world(tmp_path)
    zone_pack(packs, TURN)
    (packs / "cobblers_rift_zones" / "data" / "cobblers" / "advancement" / "rift_zones" / "z9_zone.json").unlink()
    assert W.zone_checks(packs) == {}


def test_a_closed_zone_stops_route_1_and_the_flag_reopens_it(tmp_path):
    # without this, a route through a zone the player's badges do not open would read as walkable
    root, packs = make_world(tmp_path)
    zone_pack(packs, ADMIT + TURN)
    r1 = stage(W.run(inputs(root, packs), {"route_1"}), "route_1")
    ev = check(r1, "walk_corridor")["evidence"]
    assert not ev["reached"] and ev["closed_zones"] == ["z9"] and ev["stuck_after"] == [99, 60]
    w = W.Walker(inputs(root, packs))
    ev = w.walk_held({"cobblers:flag/gym1_cleared"}, [(60, 60)], [(180, 60)], line=[tuple(p) for p in ROUTE])
    assert ev["reached"] and ev["steps"] == 120 and "closed_zones" not in ev


def test_a_stand_inside_a_zone_its_flags_do_not_open_fails(tmp_path):
    # without this, Victory Road's fights 8-10 inside z5 (CRITICAL_PATH_WALK_2 item 1) would pass again
    root, packs = make_world(tmp_path)
    zone_pack(packs, TURN + GRANT_LATE)
    w = W.Walker(inputs(root, packs))
    st = W.Stage("s", "s")
    w.zones_admit(st, "a", {"cobblers:flag/gym1_cleared"}, 102, 70, 60, "x")
    w.zones_admit(st, "b", set(), 110, 70, 60, "y")
    w.zones_admit(st, "c", set(), 102, 400, 60, "z")          # above the box's y range
    assert [c["verdict"] for c in st.checks] == ["FAIL", "PASS", "PASS"]
    assert "only its knock box" in st.checks[0]["evidence"]["summary"]


# ------------------------------------------------------------------------------------------------- victory road

def vr_world(tmp_path, seat="100.5 71 62.5", forced=True):
    root, packs = make_world(tmp_path, forced=forced)
    write(root / "data" / "vr_trainers.json", {"trainers": [{"id": "route_01_trainer_01", "seat": [100, 71, 62],
                                                             "eye_contact": True}]})
    cyc = packs / "cobblers_trainers" / "data" / "cobblers" / "function" / "trainers" / "cycle.mcfunction"
    cyc.write_text('execute as @e[nbt={TrainerId:"route_01_trainer_01",InBattle:0b}] positioned %s run tp @s\n'
                   % seat, encoding="utf-8")
    return root, packs


def test_an_authored_stand_seated_where_the_data_puts_it_passes(tmp_path):
    # without this, the seat check could fail every correct seat (the half-block centring)
    w = W.Walker(inputs(*vr_world(tmp_path)))
    st = W.Stage("s", "s")
    w.vr_stands(st, set())
    assert [(c["check"], c["verdict"]) for c in st.checks] == [("seated:route_01_trainer_01", "PASS"),
                                                                ("zone_admits:route_01_trainer_01", "PASS")]


def test_a_stand_seated_elsewhere_unseated_or_not_forcing_fails(tmp_path):
    # without this, a cycle that seats a Victory Road trainer two blocks off, or never, or a mob that never
    # initiates where the data says eye contact, would pass
    for i, kw in enumerate(({"seat": "102.5 71 62.5"}, {"seat": "1 1 1\n"}, {"forced": False})):
        root, packs = vr_world(tmp_path / str(i), **kw)
        if i == 1:
            (packs / "cobblers_trainers" / "data" / "cobblers" / "function" / "trainers" / "cycle.mcfunction"
             ).write_text("say nobody\n", encoding="utf-8")
        st = W.Stage("s", "s")
        W.Walker(inputs(root, packs)).vr_stands(st, set())
        assert check(st, "seated:route_01_trainer_01")["verdict"] == "FAIL", kw


# ------------------------------------------------------------------------------------------------- the League

def test_template_rect_rotates_about_the_corner():
    # without this, the League's footprint would be computed in the wrong quadrant: x3635-3754 z2375-2485 is the
    # footprint data/placements.json league_building chosen_because states for (3754, 2375) clockwise_90
    size = [111, 159, 120]
    assert W.template_rect(3754, 2375, size, "clockwise_90") == [3635, 2375, 3754, 2485]
    assert W.template_rect(0, 0, size, "none") == [0, 0, 110, 119]
    assert W.template_rect(0, 0, size, "180") == [-110, -119, 0, 0]
    assert W.template_rect(0, 0, size, "counterclockwise_90") == [0, -110, 119, 0]


def test_a_flag_is_emitted_only_by_a_grant_something_calls(tmp_path):
    # without this, the flag past Victory Road's caves could be granted by a function nothing runs, or by a
    # commented-out line, and the leg it opens would read as open
    root, packs = make_world(tmp_path)
    prog = packs / "cobblers_progression" / "data" / "cobblers"
    write(prog / "advancement" / "flag" / "rift_crisis_resolved.json",
          {"criteria": {"set": {"trigger": "minecraft:impossible"}}})
    assert W.flag_emitted(packs, W.CRISIS_FLAG)[0] == "FAIL"
    g = prog / "function" / "flag" / "rift_crisis_resolved" / "grant.mcfunction"
    write(g, "# advancement grant @s only cobblers:flag/rift_crisis_resolved\n")
    assert W.flag_emitted(packs, W.CRISIS_FLAG)[0] == "FAIL"
    write(g, "advancement grant @s only cobblers:flag/rift_crisis_resolved\n")
    v, ev = W.flag_emitted(packs, W.CRISIS_FLAG)
    assert v == "FAIL" and "nothing built calls" in ev
    write(packs / "cobblers_dialogue" / "data" / "cobblers" / "dialogues" / "d.json",
          {"x": "q.run_command('run function cobblers:flag/rift_crisis_resolved/grant')"})
    assert W.flag_emitted(packs, W.CRISIS_FLAG)[0] == "PASS"


# ------------------------------------------------------------------------------------------------- the verdicts

def test_not_modelled_is_never_pass_and_fail_dominates():
    # without this, a stage with an unmodelled check could report PASS (the brief's rule)
    s = W.Stage("x", "x")
    assert s.verdict == "NOT_MODELLED"              # nothing checked is not a pass
    s.add("a", "PASS", "")
    s.add("b", "NOT_MODELLED", "")
    assert s.verdict == "NOT_MODELLED"
    s.add("c", "FAIL", "")
    assert s.verdict == "FAIL"


def test_known_failures_do_not_fail_the_run_and_a_fixed_one_does(monkeypatch):
    # without this, KNOWN could hide a new failure, or outlive the defect it names
    monkeypatch.setattr(W, "KNOWN", {("s", "k"): "why"})
    s = W.Stage("s", "s")
    s.add("k", "FAIL", "")
    assert W.triage([s]) == ([], [("s", "k")], [])
    s.add("other", "FAIL", "")
    assert W.triage([s])[0] == ["s"]
    t = W.Stage("s", "s")
    t.add("k", "PASS", "")
    assert W.triage([t]) == ([], [], [("s", "k")])


def test_the_walk_is_the_last_prepare_job_after_oaks_audit():
    # without this, the walk could run before the packs it reads are built (CLAUDE.md "A success report is not
    # the work": a stage reading yesterday's build would report on yesterday's game)
    import inspect
    import reapply
    jobs = reapply.prepare_jobs(types.SimpleNamespace(source_root="x", server_dir="x"))
    names = [n for n, _f in jobs]
    assert names[-1] == "new_player_walk"
    assert inspect.getclosurevars(jobs[-1][1]).nonlocals.get("tool") == "new_player_walk.py"
    assert names.index("oak_starter_audit") == len(names) - 2
