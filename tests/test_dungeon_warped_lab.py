"""The Warped Laboratory (`warped_lab` in data/dungeons.json), authored by unit NEW-WARPED (2026-10-11) to the roster entry
of data/dungeon_prize_roster.json on the `warped_forest` theme.

The author's own tests (the independent review is another agent's): the record builds and walks in all four variants (the
room kit's walk check, every door, every route of both forks, the wing and the side rooms, the secrets with their tricks);
its MAIN route's required time is about 32 minutes at band 1 with every clock under an hour; it has every room type the
owner named and ours, two forks through crossroads (one three ways), a four-room optional WING ending in the PRIZE habitat
whose pool is exactly the roster's (Genesect, Iron Valiant, Iron Jugulis at bands 5 and 6, nothing before), two parkours
(six sections main, a hard one in the wing), the lights-out set piece before the boss, three secrets with relics, a
shortcut, four distinct variants, at least three of the six optional rooms off the route, rotation pools on every trainer,
the mini-boss and the boss (two stages, a full heal between); every species is in the Cobblemon 1.8.0 jar and no crew or
team holds a legendary; its rip stands on dry heightmap ground on the test trail. One GENERATOR mutation: rooms that never
touch lose the shortcut and the plan check says so.

Not covered: anything in a running Minecraft; the fight, puzzle and prize behaviour in game; bands 5-6 balance (untuned).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_audit as DA  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import dungeon_setpieces as SP  # noqa: E402

DOC = D.load()
RIP = {r["legacy_dungeon"]: r for r in DOC["rips"] if r.get("legacy_dungeon")}   # the test rips (data/dungeon_rips.json)
WL = next(d for d in DOC["dungeons"] if d["id"] == "warped_lab")
SLOTS = [s for s in D.slots(DOC) if s["dungeon"]["id"] == "warped_lab"]
SLOT = SLOTS[0]
RECORDS = list(R._walk_records(WL["rooms"]))
FIGHTS = {"stand", "gauntlet", "ambush", "nest", "miniboss", "habitat", "boss_arena"}
OWNER_NAMED = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room", "setpiece"}
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
ROSTER = next(x for x in json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))["dungeons"]
              if x["id"] == "warped_lab")


def all_variant_records():
    out = []
    for s in R.variant_slots(DOC, WL, SLOTS):
        out += list(R._walk_records(R.resolve(DOC, WL, s)["rooms"]))
    return out


def teams_of(t):
    """Every team a trainer can field, by band (team_by_band or the pool)."""
    out = {}
    for b in range(1, 7):
        out[b] = DF.team_pool(t, b)
    return out


@pytest.fixture(scope="module")
def walks():
    return {R.variant_of(DOC, WL, s)["id"]: DC.walked(DOC, WL, s)[0] for s in R.variant_slots(DOC, WL, SLOTS)}


@pytest.fixture(scope="module")
def pack():
    return D.build(DOC)


@pytest.fixture(scope="module")
def jar():
    import battle_sim as B
    try:
        sp, _m, _c = B.load_pack(B.find_jar())
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar on this machine")
    return {k: set(v.get("labels", [])) for k, v in sp.items()}


# ------------------------------------------------------------------------------------------------- the record


def test_a_test_dungeon_on_the_warped_theme_open_to_every_band_with_no_lockout_of_its_own():
    assert WL["theme"] == "warped_forest" and WL["test"] is True and WL["test_why"]
    assert WL["gate_flag"] == "cobblers:flag/gym8_cleared" and WL["first_band"] == 5 and "spine" not in WL
    assert WL["short"] not in [d["short"] for d in DOC["dungeons"] if d is not WL]
    assert set(WL["clock_s_by_band"]) == {str(b["band"]) for b in DOC["engine"]["bands"]}
    assert max(WL["clock_s_by_band"].values()) <= 3600
    assert "lockout_ticks" not in WL and D.lockout_of(DOC, WL) == DOC["engine"]["lockout_ticks"]


def test_the_engine_and_the_room_kit_find_no_problem_in_any_variant():
    assert R.problems(DOC, WL) == []
    for s in R.variant_slots(DOC, WL, SLOTS):
        assert R.walk_problems(DOC, WL, s) == [], R.variant_of(DOC, WL, s)["id"]
        assert SP.check_setpieces(DOC, R.resolve(DOC, WL, s), s) == []
        assert R.chain_problems(DOC, WL, s) == []


def test_the_clock_is_about_32_minutes_required_at_band_one_and_covers_the_formula(walks):
    slack = DOC["engine"]["clock"]["slack_factor"]
    want = DC.derive(DOC, WL)
    own = WL["clock_s_by_band"]
    for b, s in want.items():
        assert s <= own[b] <= s + 120, (b, own[b], s)          # the formula plus the set piece's 25 s (clock_why)
    req1 = max(sum(DC.required(DOC, WL, 1, DC.clock_rooms(DOC, WL, 1, w)).values()) for w in walks.values())
    assert 30 * 60 <= req1 <= 34 * 60, req1 / 60
    assert abs(own["1"] - (req1 + 25) * slack) <= 60
    assert DC.clock_problems(DOC, WL) == []
    assert DA.design_room_clocks()["warped_lab"] == [own[str(b)] // 60 for b in range(1, 7)]


def test_every_room_type_the_owner_named_ours_three_optional_rooms_and_the_set_piece_before_the_boss():
    kinds = {r["kind"] for r in RECORDS}
    assert OWNER_NAMED <= kinds, OWNER_NAMED - kinds
    assert len(kinds & OURS) >= 6, kinds & OURS
    assert len(kinds & EXTRA_KINDS) >= 3, kinds & EXTRA_KINDS
    assert any(r["kind"] == "safe_room" and r["params"].get("healer") for r in RECORDS)
    main = [r for r in WL["rooms"] if r["kind"] not in R.CONTAINERS]
    assert main[0]["kind"] == "entry_room" and [r["kind"] for r in main[-3:]] == ["setpiece", "boss_arena", "exit_room"]
    (sp,) = [r for r in RECORDS if r["kind"] == "setpiece"]
    assert sp["params"]["piece"] == "lights_out" and sp["params"]["pit"] == 0


def test_the_optional_rooms_are_off_the_route_open_and_never_paid(walks):
    for s in SLOTS:
        for r in R.layout(DOC, WL, s):
            if r["kind"] in EXTRA_KINDS | {"vault"}:
                assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open", (s["g"], r["id"])
    bank = [r for r in RECORDS if r["kind"] == "bank_vault"]
    if bank:
        main_ids = {r["id"] for r in WL["rooms"] if r["kind"] not in R.CONTAINERS}
        assert set(bank[0]["params"]["clue_rooms"]) <= main_ids
    for rows in walks.values():
        paid = {r["id"] for b in range(1, 7) for r in DC.clock_rooms(DOC, WL, b, rows)}
        assert not paid & {r["id"] for r in rows if r["kind"] in EXTRA_KINDS | {"vault"}}


def test_the_route_turns_climbs_drops_doubles_back_and_runs_under_itself():
    rooms = R.layout(DOC, WL, SLOT)
    shaped = [r for r in rooms if r["shape"] != "box"]
    assert len(shaped) > len(rooms) / 2 and len({r["shape"] for r in shaped}) >= 5
    assert {d["side"] for r in rooms for d in r["doors"]} == {"north", "south", "east", "west"}
    assert [r["id"] for r in rooms if r.get("dir") == "west"]
    floors = [r["floor_in"] for r in rooms]
    assert max(floors) - min(floors) >= 10
    by = {r["id"]: r for r in rooms}
    u, w = by["cold_store"], by["ward"]
    assert u["xa"] < w["xb"] and w["xa"] < u["xb"] and u["za"] < w["zb"] and w["za"] < u["zb"] and u["ceil_y"] < w["hull_lo"]


def test_the_pacing_no_two_fights_meet_and_the_heal_comes_before_the_last_third(walks):
    for s in R.variant_slots(DOC, WL, SLOTS):
        rooms = R.layout(DOC, WL, s)
        by_i = {r["i"]: r for r in rooms}
        for r in rooms:
            for d in r["doors"]:
                if d["dir"] == "out" and not d.get("shortcut"):
                    n = by_i[d["to"]]
                    assert not (r["kind"] in FIGHTS and n["kind"] in FIGHTS), (r["id"], n["id"])
    for vid, rows in walks.items():
        order = {r["id"]: k for k, r in enumerate(rows)}
        path = sorted(DC.clock_rooms(DOC, WL, 1, rows), key=lambda r: order[r["id"]])
        total = sum(r["walk"] for r in path)
        before = 0
        for r in path:
            if r["kind"] == "safe_room":
                break
            before += r["walk"]
        assert 0.55 <= before / total <= 0.85, (vid, before / total)


# ------------------------------------------------------------------------------------------------- choices


def test_two_forks_through_crossroads_one_three_ways_each_way_signed_and_seen(walks):
    top = WL["rooms"]
    forks = [(k, r) for k, r in enumerate(top) if r["kind"] == "fork"]
    assert sorted(len(f["routes"]) for _k, f in forks) == [2, 3]
    for k, f in forks:
        assert top[k - 1]["kind"] == "crossroads"
        lk = [rt["look"] for rt in f["routes"]]
        assert len(set(lk)) == len(lk) and all(rt.get("sign") for rt in f["routes"])
        assert not any(rt.get("optional") for rt in f["routes"])
    for s in R.variant_slots(DOC, WL, SLOTS):
        rooms = R.layout(DOC, WL, s)
        for k, f in forks:
            host = next(r for r in rooms if r["id"] == top[k - 1]["id"])
            outs = [d["side"] for d in host["doors"] if d["dir"] == "out"]
            assert len(outs) == len(f["routes"]) == len(set(outs)), outs
            join = next(r for r in rooms if r["id"] == top[k + 1]["id"])
            assert len([d for d in join["doors"] if d["dir"] == "in"]) == len(f["routes"])
    f1 = {rt["id"]: {r["kind"] for r in rt["rooms"]} for rt in forks[0][1]["routes"]}
    assert "stand" in f1["observation"] and "collapse_bridge" in f1["catwalk"]
    assert not f1["coolant"] & ({"collapse_bridge", "parkour"} | FIGHTS)
    f2 = {rt["id"]: {r["kind"] for r in rt["rooms"]} for rt in forks[1][1]["routes"]}
    assert "maze" in f2["archive"] and "dark_room" in f2["servers"]


def wing():
    (w,) = [r for r in WL["rooms"] if r["kind"] == "side" and len(r["rooms"]) == 4]
    return w


def test_a_four_room_wing_off_the_infirmary_a_climb_a_hard_parkour_and_the_prize_at_its_dead_end(walks):
    w = wing()
    kinds = [r["kind"] for r in w["rooms"]]
    assert R.flags_of(kinds[0])["connector"] and kinds[-1] == "habitat"
    top_ids = [r["id"] for r in WL["rooms"]]
    assert WL["rooms"][top_ids.index(w["id"]) - 1]["kind"] == "safe_room"
    (pk,) = [r for r in w["rooms"] if r["kind"] == "parkour"]
    assert pk["params"]["hard"] is True and pk["params"]["sections"] >= 5 and pk["width"] == 25
    end = w["rooms"][-1]
    assert end.get("gate", "open") == "open" and [s["type"] for s in end["secrets"]] == ["balcony"]
    ids = {r["id"] for r in w["rooms"]}
    for s in R.variant_slots(DOC, WL, SLOTS):
        by = {r["id"]: r for r in R.layout(DOC, WL, s)}
        assert all(by[i]["route"] == w["id"] for i in ids)
        assert not [d for d in by[end["id"]]["doors"] if d["dir"] == "out"]
    for rows in walks.values():
        for b in range(1, 7):
            assert not ids & {r["id"] for r in DC.clock_rooms(DOC, WL, b, rows)}


def test_two_parkours_a_six_section_main_one_and_the_hard_one():
    pks = [r for r in RECORDS if r["kind"] == "parkour"]
    assert len(pks) == 2
    (main,) = [r for r in WL["rooms"] if r["kind"] == "parkour"]
    assert main["params"]["sections"] == 6 and main["width"] == 25 and not main["params"].get("hard")
    assert main["length"] >= 30 * 6 - 10 + 2
    for s in R.variant_slots(DOC, WL, SLOTS):
        built = {b.room["id"]: b for b in R.slot_build(DOC, WL, s)}
        for r in pks:
            m = built[r["id"]].meta
            assert len(m["ledges"]) == r["params"]["sections"] + 1, (r["id"], s["k"])
            assert (m["fork"] is None) == bool(r["params"].get("hard"))


def test_the_prize_is_exactly_the_rosters_pool_from_band_five_and_nothing_before(pack, jar):
    import dungeon_prize as PZ
    end = wing()["rooms"][-1]
    pz = end["params"]["prize"]
    assert pz["roster"] == "warped_lab" and "species" not in end["params"]
    assert not {k for k in pz if k.endswith("_by_band")}, "the roster is the only source: no species moved here or added"
    assert PZ.room_problems(DOC, WL, end) == []
    for b in range(1, 7):
        got = PZ.pool_at(DOC, end, b)
        want = [sp for sp in (ROSTER["legendary_pool_by_band"].get(str(b)) or []) if not PZ.model_gated(DOC, sp)]
        assert (got[0] if got else []) == want, (b, got)
        for sp in want:
            assert jar[sp] & {"legendary", "mythical", "ultra_beast", "paradox"}, sp
    assert not ROSTER["rare_pool_by_band"]
    base = "data/cobblers/function/dungeons/room/warped_lab/%s/s%d/" % (end["id"], SLOT["g"])
    for b in range(1, 7):
        name = base + "prize/spawn_b%d.mcfunction" % b
        if b >= 5:
            assert pack[name].rstrip().endswith("prize/bind"), b
            assert "level=%d no_ai" % DOC["engine"]["bands"][b - 1]["caps"][0] in pack[name]
        else:
            assert name not in pack, b


def test_the_locker_pays_no_more_than_the_runs_time_gathering():
    import dungeon_greed as DG
    assert [x for x in DG.vault_over(DOC) if x[0] == "warped_lab"] == []


def test_three_secrets_two_cracked_one_balcony_each_with_a_unique_relic():
    rooms = [r for r in RECORDS if r.get("secrets")]
    assert sorted(s["type"] for r in rooms for s in r["secrets"]) == ["balcony", "cracked", "cracked"]
    relics = [r["params"]["relic"] for r in rooms]
    assert len(set(relics)) == 3 and all(x.startswith("wl_") for x in relics)
    for r in rooms:
        p = r["params"]
        assert 0 < len(p["lore"]) <= 160 and p["lore"].isascii() and p["lore"].isprintable() and len(p["relic_name"]) <= 32
    for s in R.variant_slots(DOC, WL, SLOTS):
        built = {b.room["id"]: b for b in R.slot_build(DOC, WL, s)}
        for r in rooms:
            assert built[r["id"]].anchors.get("secret"), (r["id"], s["k"])


def test_a_shortcut_back_toward_the_entry_opened_from_the_far_side(pack):
    scs = [(r["id"], sc) for r in RECORDS for sc in r.get("shortcuts") or []]
    assert len(scs) == 1
    far_id, sc = scs[0]
    for s in R.variant_slots(DOC, WL, SLOTS):
        rooms = {r["id"]: r for r in R.layout(DOC, WL, s)}
        assert rooms[sc["to"]]["i"] < rooms[far_id]["i"]
        assert [d for d in rooms[far_id].get("shortcut_doors", []) if d["dir"] == "out"]
    assert any(k.endswith("/room/warped_lab/%s/s%d/shortcut_%s.mcfunction" % (far_id, SLOT["g"], sc["id"])) for k in pack)


def test_four_distinct_variants_one_per_slot():
    vs = WL["variants"]
    assert [R.variant_of(DOC, WL, s)["id"] for s in SLOTS] == [v["id"] for v in vs] and len(vs) == 4
    assert len({json.dumps({k: v[k] for k in v if k != "id"}, sort_keys=True) for v in vs}) == 4
    shapes = set()
    for s in SLOTS:
        rooms, built = R.layout(DOC, WL, s), R.slot_build(DOC, WL, s)
        shapes.add(tuple((r["id"], r["za"] - s["z0"], r["kind"], len(b.ops)) for r, b in zip(rooms, built)))
    assert len(shapes) == 4


# ------------------------------------------------------------------------------------------------- fights and variety


def test_every_trainer_mini_boss_and_the_boss_rotate_per_run_within_the_contract():
    for s in R.variant_slots(DOC, WL, SLOTS):
        for r in R._walk_records(R.resolve(DOC, WL, s)["rooms"]):
            if r["kind"] in ("stand", "gauntlet", "ambush"):
                assert r["gate"] == "cleared" and DF.stand_problems(DOC, r) == [], r["id"]
                for t in r["params"]["trainers"]:
                    assert all(len(t["team_pool_by_band"][str(b)]) >= 2 for b in range(1, 7)), t["name"]
            if r["kind"] in ("gauntlet", "ambush"):
                assert len(r["params"]["triggers"]) == len(r["params"]["trainers"])
    (mb,) = [r for r in RECORDS if r["kind"] == "miniboss"]
    pool = mb["params"]["species_pool_by_band"]
    assert set(pool) == {str(b) for b in range(1, 7)} and all(len(v) >= 3 for v in pool.values())
    assert mb["params"]["catchable"] is True and mb["params"]["level_offset"] <= 0
    bo = WL["boss"]
    assert bo["heal_between_stages"] is True and len(bo["stage_level_offsets"]) == 2
    for b in range(1, 7):
        for crews in [bo["teams"][str(b)]] + bo["teams_alt_by_band"][str(b)]:
            assert len(crews) == 2 and len({c[-1] for c in crews}) == 1 and all(1 <= len(c) <= 6 for c in crews)
    (nest,) = [r for r in RECORDS if r["kind"] == "nest"]
    assert nest["gate"] == "cleared" and set(nest["params"]["count_by_band"]) == {str(b) for b in range(1, 7)}


def species_named():
    out = set()
    for r in all_variant_records():
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for teams in teams_of(t).values():
                for team in teams:
                    out |= set(team)
        if isinstance(p.get("species"), list):
            out |= set(p["species"])
        for v in (p.get("species_pool_by_band") or {}).values():
            out |= set(v)
    bo = WL["boss"]
    for crews in list(bo["teams"].values()) + [c for alts in bo["teams_alt_by_band"].values() for c in alts]:
        for c in crews:
            out |= set(c)
    return out


def test_every_species_is_in_the_jar_and_none_in_a_fight_is_a_legend(jar):
    import battle_sim as B
    named = species_named()
    assert sorted(s for s in named if B.key(s) not in jar) == []
    assert sorted(s for s in named if jar[B.key(s)] & {"legendary", "mythical", "ultra_beast", "paradox"}) == []


def test_the_extras_data_carry_a_warped_row_and_its_checks_pass(jar):
    import dungeon_extras2 as DX2
    x2 = json.loads((ROOT / "data" / "dungeon_extras2.json").read_text(encoding="utf-8"))
    assert "warped_forest" in x2["fishing"]["species"] and "warped_forest" in x2["eggs"]["vendor"]
    assert x2["fossils"]["dig"]["warped_forest"] not in (ROOT / "data" / "dungeon_themes.json").read_text(encoding="utf-8")
    sp = DX2.jar_species()
    assert [p for p in DX2.data_problems(DOC, sp) if "warped" in p] == []


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_stands_on_the_test_trail_clear_of_the_old_mine_and_the_other_rips():
    import route1_old_mine as M
    f = RIP[WL["id"]]["frame"]
    assert f["x0"] > max(x for x, _z in M.TRAIL) + 4
    for x in range(f["x0"], f["x1"] + 1):
        assert M.rise(x, f["z"]) == 0
    for d in DOC["dungeons"]:
        if d is not WL:
            o = RIP[d["id"]]["frame"]
            assert f["x1"] + 3 < o["x0"] or o["x1"] + 3 < f["x0"] or abs(f["z"] - o["z"]) > 3, d["id"]
    assert RIP[WL["id"]]["click"] == [(f["x0"] + f["x1"]) // 2, f["y"], f["z"] + 1]


def test_the_rip_stands_on_the_heightmaps_ground_above_the_sea():
    try:
        import ground as GR
        import terrain as T
        g = GR.load()
    except Exception as e:
        pytest.skip("no canonical heightmap: %s" % e)
    f = RIP[WL["id"]]["frame"]
    sea = T.sea_level(g.world)
    for x in range(f["x0"], f["x1"] + 1):
        for z in (f["z"], f["z"] + 1, f["z"] + 2):
            assert g(x, z) + 1 == f["y"] and g(x, z) > sea, (x, z, g(x, z))
    ox, oy, oz, _yaw = RIP[WL["id"]]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy
    assert D.rip_restore_measured(RIP[WL["id"]], g) == RIP[WL["id"]]["restore"]


# ------------------------------------------------------------------------------------------------- generator mutation


def test_mutating_the_kit_so_rooms_never_touch_loses_the_shortcut_and_the_plan_check_says_so(monkeypatch):
    R._BUILT.clear()
    monkeypatch.setattr(R, "_touch", lambda far, near: None)
    bad = R.plan_problems(DOC, WL, SLOT)
    R._BUILT.clear()
    assert any("shortcut c1" in p and "does not touch" in p for p in bad), bad[:3]
