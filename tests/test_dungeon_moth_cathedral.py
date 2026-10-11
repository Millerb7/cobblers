"""The Moth Cathedral (`moth_cathedral`, a crimson-forest TEST dungeon in data/dungeons.json), authored by unit NEW-MOTH
(2026-10-11) to data/dungeon_prize_roster.json's proposed entry.

The author's own tests (the independent review is another agent's: tools/dungeon_independent_audit.py): the record builds
and walks in all four variants (the room kit's walk check, every door, every route of both forks, the wing and the side
rooms, the secrets with their tricks), its required time is about 32 minutes at band 1 with every clock under an hour,
the route turns, climbs, doubles back and runs ABOVE an earlier room, two forks each through a crossroads (one three
ways), an optional wing that goes DOWN to the prize habitat behind a hard parkour, a six-section main parkour, three of
the six optional rooms, two secrets with relics, a shortcut, four variants, the lights-out set piece before a two-stage
boss with a full heal between, per-run rotation pools on every trainer, the mini-boss and the boss, the prize exactly as
the roster assigns, every species in the Cobblemon 1.8.0 jar, and a rip on dry measured ground on the test trail.

Not covered: anything in a running Minecraft; bands 5-6 balance (the simulator has no Pokemon past gym 8).
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_audit as DA  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import dungeon_setpieces as SP  # noqa: E402

DOC = D.load()
MC = next(d for d in DOC["dungeons"] if d["id"] == "moth_cathedral")
SLOTS = [s for s in D.slots(DOC) if s["dungeon"]["id"] == "moth_cathedral"]
SLOT = SLOTS[0]
RECORDS = list(R._walk_records(MC["rooms"]))
FIGHTS = {"stand", "gauntlet", "ambush", "nest", "miniboss", "habitat", "boss_arena"}
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
ROSTER = json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def walks():
    out = {}
    for s in R.variant_slots(DOC, MC, SLOTS):
        out[R.variant_of(DOC, MC, s)["id"]] = DC.walked(DOC, MC, s)[0]
    return out


def rooms_of(kind):
    return [r for r in RECORDS if r["kind"] == kind]


def trainers():
    return [t for r in RECORDS for t in (r.get("params") or {}).get("trainers", [])]


# ------------------------------------------------------------------------------------------------- the record


def test_a_test_dungeon_on_the_crimson_forest_theme_with_its_own_clock_and_no_lockout_of_its_own():
    assert MC["test"] is True and MC["rip"]["test"] is True and MC["theme"] == "crimson_forest"
    assert "nether-rip-siting" in MC["rip"]["siting_pending"]
    assert MC["short"] not in {d["short"] for d in DOC["dungeons"] if d is not MC}
    assert set(MC["clock_s_by_band"]) == {str(b["band"]) for b in DOC["engine"]["bands"]}
    assert max(MC["clock_s_by_band"].values()) <= 3600
    assert "lockout_ticks" not in MC and D.lockout_of(DOC, MC) == DOC["engine"]["lockout_ticks"]
    # the roster's gate is recorded, not set, while the owner walks it as a playtester (gate_flag_why)
    assert MC["gate_flag"] is None and "gym8_cleared" in MC["gate_flag_why"]


def test_the_engine_and_the_room_kit_find_no_problem_with_it_in_any_variant():
    assert R.problems(DOC, MC) == []
    assert [p for p in D.problems(DOC) if "moth_cathedral" in p] == []
    for s in R.variant_slots(DOC, MC, SLOTS):
        assert R.walk_problems(DOC, MC, s) == [], R.variant_of(DOC, MC, s)["id"]
        assert SP.check_setpieces(DOC, R.resolve(DOC, MC, s), s) == []


def test_the_clock_is_about_32_minutes_required_at_band_one_and_the_authored_clock_covers_the_formula(walks):
    want = DC.derive(DOC, MC)
    own = MC["clock_s_by_band"]
    slack = float(DOC["engine"]["clock"]["slack_factor"])
    for b, s in want.items():
        # the formula plus the set piece's 25 s allowance, every band (MEGA-INTEGRATE: each dungeon's vaults are priced on
        # its own clock, so band 4 no longer stands at the others' shortest)
        req = max(sum(DC.required(DOC, MC, int(b), DC.clock_rooms(DOC, MC, int(b), w)).values()) for w in walks.values())
        assert own[b] == math.ceil((req + 25) * slack / 60.0) * 60, (b, own[b], s)
        assert s <= own[b] <= s + 120, (b, own[b], s)
    req1 = max(sum(DC.required(DOC, MC, 1, DC.clock_rooms(DOC, MC, 1, w)).values()) for w in walks.values())
    assert 30 * 60 <= req1 <= 34 * 60, req1 / 60
    assert 38 * 60 <= own["1"] <= 42 * 60
    assert DC.clock_problems(DOC, MC) == []
    assert DA.design_room_clocks()["moth_cathedral"] == [own[str(b)] // 60 for b in range(1, 7)]


def test_wide_rooms_short_connectors_and_a_route_that_turns_climbs_doubles_back_and_runs_over_itself():
    rooms = R.layout(DOC, MC, SLOT)
    for r in rooms:
        if R.flags_of(r["kind"])["connector"]:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
    shaped = [r for r in rooms if r["shape"] != "box"]
    assert len(shaped) > len(rooms) / 2 and len({r["shape"] for r in shaped}) >= 4
    assert {d["side"] for r in rooms for d in r["doors"]} == {"north", "south", "east", "west"}
    assert [r["id"] for r in rooms if r.get("dir") == "west"], "a stretch walked back west"
    floors = [r["floor_in"] for r in rooms]
    assert max(floors) - min(floors) >= 30, "the triforium climbs, the crypt drops"
    by = {r["id"]: r for r in rooms}
    t, g = by["triforium"], by["moth_gallery"]
    assert t["xa"] < g["xb"] and g["xa"] < t["xb"] and t["za"] < g["zb"] and g["za"] < t["zb"] and g["ceil_y"] < t["hull_lo"]


def test_every_room_type_the_owner_named_with_the_heal_the_set_piece_and_three_optional_rooms():
    kinds = {r["kind"] for r in RECORDS}
    assert {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"} <= kinds
    assert {"gauntlet", "ambush", "dark_room", "collapse_bridge", "safe_room", "setpiece"} <= kinds
    assert any(r["kind"] == "safe_room" and r["params"].get("healer") for r in RECORDS)
    extras = [r for r in RECORDS if r["kind"] in EXTRA_KINDS]
    assert len({r["kind"] for r in extras}) >= 3
    sides = [r for r in MC["rooms"] if r["kind"] == "side" and any(x["kind"] in EXTRA_KINDS for x in r["rooms"])]
    assert all(x.get("gate", "open") == "open" for s in sides for x in s["rooms"])
    main = [r for r in MC["rooms"] if r["kind"] not in R.CONTAINERS]
    assert main[0]["kind"] == "entry_room" and [r["kind"] for r in main][-3:] == ["setpiece", "boss_arena", "exit_room"]


def test_no_two_fights_meet_on_any_route_of_any_variant():
    for s in R.variant_slots(DOC, MC, SLOTS):
        rooms = R.layout(DOC, MC, s)
        by_i = {r["i"]: r for r in rooms}
        for r in rooms:
            for d in r["doors"]:
                if d["dir"] == "out" and not d.get("shortcut"):
                    n = by_i[d["to"]]
                    assert not (r["kind"] in FIGHTS and n["kind"] in FIGHTS), (r["id"], n["id"])


# ------------------------------------------------------------------------------------------------- replayability


def test_two_forks_each_through_a_crossroads_that_sees_every_way_one_of_them_three_ways():
    top = MC["rooms"]
    forks = [(k, r) for k, r in enumerate(top) if r["kind"] == "fork"]
    assert sorted(len(f["routes"]) for _k, f in forks) == [2, 3]
    for k, f in forks:
        assert top[k - 1]["kind"] == "crossroads"
        lk = [rt["look"] for rt in f["routes"]]
        assert len(set(lk)) == len(lk) and all(rt.get("sign") for rt in f["routes"])
        assert not any(rt.get("optional") for rt in f["routes"])
    for s in R.variant_slots(DOC, MC, SLOTS):
        rooms = R.layout(DOC, MC, s)
        for k, f in forks:
            host = next(r for r in rooms if r["id"] == top[k - 1]["id"])
            outs = [d["side"] for d in host["doors"] if d["dir"] == "out"]
            assert len(outs) == len(f["routes"]) == len(set(outs)), outs
            join = next(r for r in rooms if r["id"] == top[k + 1]["id"])
            assert len([d for d in join["doors"] if d["dir"] == "in"]) == len(f["routes"])


def test_the_crossing_offers_a_fall_a_fight_and_the_long_safe_way_and_the_clock_pays_the_slower(walks):
    f = next(r for r in MC["rooms"] if r["id"] == "f_crossing")
    kinds = {rt["id"]: {r["kind"] for r in rt["rooms"]} for rt in f["routes"]}
    assert "collapse_bridge" in kinds["choir"] and "ambush" in kinds["sexton"]
    assert not kinds["font"] & (FIGHTS | {"collapse_bridge", "parkour"})
    for vid, rows in walks.items():
        paid = {r["route"] for r in DC.clock_rooms(DOC, MC, 1, rows) if r["route"] != "main"}
        assert "f_crossing/sexton" in paid, (vid, paid)


def test_an_optional_wing_down_into_the_crypt_a_hard_parkour_and_the_prize_at_its_end(walks):
    (w,) = [r for r in MC["rooms"] if r["kind"] == "side" and len(r["rooms"]) > 1]
    kinds = [r["kind"] for r in w["rooms"]]
    assert 3 <= len(kinds) <= 4 and R.flags_of(kinds[0])["connector"] and kinds[-1] == "habitat"
    (pk,) = [r for r in w["rooms"] if r["kind"] == "parkour"]
    assert pk["params"]["hard"] is True and pk["params"]["sections"] >= 5 and pk["width"] == 25
    end = w["rooms"][-1]
    assert end.get("gate", "open") == "open" and [s["type"] for s in end["secrets"]] == ["balcony"]
    by = {r["id"]: r for r in R.layout(DOC, MC, SLOT)}
    assert by[end["id"]]["floor_in"] < by["lady_chapel"]["floor_in"] - 20, "the crypt is below the chapel"
    ids = {r["id"] for r in w["rooms"]}
    for rows in walks.values():
        for b in range(1, 7):
            assert not ids & {r["id"] for r in DC.clock_rooms(DOC, MC, b, rows)}


def test_two_parkours_a_six_section_main_one_and_the_hard_one():
    main = [r for r in MC["rooms"] if r["kind"] == "parkour"]
    assert len(main) == 1 and main[0]["params"]["sections"] == 6 and main[0]["width"] == 25
    assert len(rooms_of("parkour")) == 2
    for s in R.variant_slots(DOC, MC, SLOTS):
        built = {b.room["id"]: b for b in R.slot_build(DOC, MC, s)}
        for r in rooms_of("parkour"):
            m = built[r["id"]].meta
            assert len(m["ledges"]) == r["params"]["sections"] + 1
            assert (m["fork"] is None) == bool(r["params"].get("hard"))


def test_the_prize_is_exactly_the_rosters_from_band_five_and_nothing_below():
    import dungeon_prize as PZ
    (hab,) = rooms_of("habitat")
    pz = hab["params"]["prize"]
    entry = next(e for e in ROSTER["dungeons"] if e["id"] == "moth_cathedral")
    assert pz["roster"] == "moth_cathedral" and not entry["rare_pool_by_band"] and "rare_by_band" not in pz
    assert set(pz["legendary_by_band"]) == set(entry["legendary_pool_by_band"]) == {"5", "6"}
    for b, sp in pz["legendary_by_band"].items():
        assert sp in entry["legendary_pool_by_band"][b]
    assert PZ.room_problems(DOC, MC, hab) == []


def test_two_secrets_with_unique_relics_and_a_shortcut_back_toward_the_entry():
    secret_rooms = [r for r in RECORDS if r.get("secrets")]
    assert sorted(s["type"] for r in secret_rooms for s in r["secrets"]) == ["balcony", "cracked", "cracked"]
    relics = [r["params"]["relic"] for r in secret_rooms]
    assert len(set(relics)) == len(relics) and all(re.fullmatch(r"mc_[a-z_]+", x) for x in relics)
    assert all(len(r["params"]["lore"]) <= 160 for r in secret_rooms)
    (clo,) = [r for r in RECORDS if r.get("shortcuts")]
    ids = [r["id"] for r in RECORDS]
    assert ids.index(clo["shortcuts"][0]["to"]) < ids.index(clo["id"])


def test_four_distinct_variants():
    v = MC["variants"]
    assert len(v) == 4 and len({json.dumps(x, sort_keys=True) for x in v}) == 4
    assert any(x.get("mirror") for x in v) and any(x.get("seed") for x in v) and any(x.get("swap") for x in v)


def test_the_set_piece_is_the_lights_out_with_a_crimson_palette():
    (sp,) = rooms_of("setpiece")
    assert sp["params"]["piece"] == "lights_out"
    pal = SP.palette("lights_out", "crimson_forest", R.load_themes()["themes"]["crimson_forest"])
    assert pal["trunk"].startswith("minecraft:crimson_stem") and "fern" not in pal["floor_plant"]


# ------------------------------------------------------------------------------------------------- fights


def test_every_trainer_rotates_two_teams_a_band_and_the_mini_boss_three_species():
    for t in trainers():
        assert "team_by_band" not in t and set(t["team_pool_by_band"]) == {str(b) for b in range(1, 7)}
        assert all(len(v) == 2 for v in t["team_pool_by_band"].values()), t["name"]
    (mb,) = rooms_of("miniboss")
    assert all(len(set(v)) == 3 for v in mb["params"]["species_pool_by_band"].values())


def test_the_boss_is_two_stages_healed_between_the_ace_last_and_the_same_in_every_crew():
    bo = MC["boss"]
    assert bo["heal_between_stages"] is True and bo["stage_level_offsets"] == [-1, 0]
    for b in range(1, 7):
        crews = [bo["teams"][str(b)]] + bo["teams_alt_by_band"][str(b)]
        aces = {st[-1] for crew in crews for st in crew}
        assert len(aces) == 1 and all(len(crew) == 2 for crew in crews), (b, aces)
    assert {bo["teams"][str(b)][0][-1] for b in (4, 5, 6)} == {"volcarona"}


@pytest.fixture(scope="module")
def jar_species():
    import battle_sim as B
    try:
        sp, _m, _c = B.load_pack(B.find_jar())
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar on this machine")
    return sp


def all_species():
    out = set()
    for t in trainers():
        for teams in t["team_pool_by_band"].values():
            for team in teams:
                out |= set(team)
    for r in RECORDS:
        p = r.get("params") or {}
        out |= set(p.get("species") or [])
        for v in (p.get("species_pool_by_band") or {}).values():
            out |= set(v)
        out |= set(((p.get("prize") or {}).get("legendary_by_band") or {}).values())
    bo = MC["boss"]
    for crews in list(bo["teams"].values()) + [c for alts in bo["teams_alt_by_band"].values() for c in alts]:
        for st in (crews if isinstance(crews[0][0], str) else [s for c in crews for s in c]):
            out |= set(st)
    return out


def test_every_species_is_in_the_jar_and_no_fight_fields_a_legend_or_another_dungeons_rare_prize(jar_species):
    import battle_sim as B
    names = all_species()
    assert sorted(s for s in names if B.key(s) not in jar_species) == []
    (hab,) = rooms_of("habitat")
    prize = set(hab["params"]["prize"]["legendary_by_band"].values())
    rare = {s for e in ROSTER["dungeons"] for v in (e.get("rare_pool_by_band") or {}).values() for s in v}
    for s in names - prize:
        labels = set(jar_species[B.key(s)].get("labels", []))
        assert not labels & {"legendary", "mythical", "ultra_beast", "paradox"}, s
        assert s not in rare, s


def test_no_species_renders_as_a_doll_or_a_mis_assembled_model():
    # docs/research/COBBLEVERSE_COMPATIBILITY.md's doll list and the mis-assembled models (NETHER-THEMES' rule, DUNGEON_ROOMS.md 11);
    # the roster's model-gated prize species are dropped by tools/dungeon_prize.py until delivered, so they are not asked here
    text = (ROOT / "docs" / "research" / "COBBLEVERSE_COMPATIBILITY.md").read_text(encoding="utf-8")
    m = re.search(r"^(arctibax, blacephalon[^\n]*)$", text, re.M)
    assert m, "the doll list moved: re-read the compatibility note"
    dolls = {s.strip().rstrip(".") for s in m.group(1).split(",")}
    misassembled = {"pidgeot", "talonflame", "arbok", "crobat", "cofagrigus", "skarmory", "tyranitar", "garganacl", "goodra",
                    "primarina", "nidoking", "turtonator", "appletun", "archaludon"}
    gated = {s for s, rec in ROSTER["species"].items() if rec.get("model_gate")}
    assert sorted((all_species() - gated) & (dolls | misassembled)) == []


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_stands_on_the_test_trail_clear_of_the_old_mine_and_the_other_rips():
    import route1_old_mine as M
    f = MC["rip"]["frame"]
    cx = (f["x0"] + f["x1"]) / 2
    assert 1465 <= cx <= 1485 and abs(f["z"] - 4118) <= 3, "the x slot the orchestrator gave (x1475 +- 10)"
    assert f["x0"] > max(x for x, _z in M.TRAIL) + 4
    for d in DOC["dungeons"]:
        if d is not MC:
            o = d["rip"]["frame"]
            assert f["x1"] + 3 < o["x0"] or o["x1"] + 3 < f["x0"] or abs(f["z"] - o["z"]) > 3, d["id"]
    assert MC["rip"]["click"] == [cx, f["y"], f["z"] + 1]
    assert all(col == ["minecraft:air"] * f["height"] for col in MC["rip"]["restore"].values())


def test_the_rip_stands_on_the_heightmaps_dry_ground():
    try:
        import ground as GR
        import terrain as T
        g = GR.load()
    except Exception as e:                                   # no heightmap on this machine
        pytest.skip("no canonical heightmap: %s" % e)
    f = MC["rip"]["frame"]
    sea = T.sea_level(g.world)
    for x in range(f["x0"], f["x1"] + 1):
        for z in (f["z"], f["z"] + 1):
            assert round(g(x, z)) + 1 == f["y"] and g(x, z) > sea, (x, z, g(x, z))
    ox, oy, oz, _yaw = MC["rip"]["outside"]
    assert round(g(int(ox), int(oz))) + 1 == oy
