"""The Starfall Crater (`starfall`, theme `night_crater`), authored by unit NEW-STARFALL (2026-10-11) to the roster's
proposal (data/dungeon_prize_roster.json starfall) on the room kit's pass-3 record.

The author's own tests (the independent review is another agent's: tools/dungeon_independent_audit.py): the record builds
and walks in all four variants (the kit's walk check, every door, both forks' routes, the wing and the side rooms, the
secrets with their tricks); its required time is about 32 minutes at band 1 with every clock under an hour; it turns,
climbs, drops and doubles back with most rooms shaped; it has every room type the owner named. Two crossroads, one of
three ways, every way in sight from its hub; a four-room optional WING (a connector, a hard parkour, the PRIZE habitat
with a balcony secret, a climb back) the clock never pays; a six-section main parkour; at least three of the six optional
rooms on side entries; the vault inside the budget; three secrets with relics, a shortcut, four distinct variants, the
lights-out set piece before a two-stage boss healed between stages; rotation pools on both stands, both ambushers, the
mini-boss and the boss; the prize exactly the roster's pools (bands 5 and 6 only); names only species in the Cobblemon
1.8.0 jar; the rip on dry measured ground at the x1675 slot. Two GENERATOR mutations: the crater's lights off leave rooms
dark, and rooms that never touch lose the shortcut; the walk and plan checks say so.

Not covered: anything in a running Minecraft; the fight and puzzle kinds' behaviour; the prize's roll and catch in game.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import dungeon_setpieces as SP  # noqa: E402

DOC = D.load()
RIP = {r["legacy_dungeon"]: r for r in DOC["rips"] if r.get("legacy_dungeon")}   # the test rips (data/dungeon_rips.json)
SF = next(d for d in DOC["dungeons"] if d["id"] == "starfall")
SLOTS = [s for s in D.slots(DOC) if s["dungeon"]["id"] == "starfall"]
SLOT = SLOTS[0]
RECORDS = list(R._walk_records(SF["rooms"]))
FIGHTS = {"stand", "gauntlet", "ambush", "nest", "miniboss", "habitat", "boss_arena"}
OWNER_NAMED = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room", "setpiece"}
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
ROSTER = next(e for e in json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))["dungeons"]
              if e["id"] == "starfall")


@pytest.fixture(scope="module")
def walks():
    out = {}
    for s in R.variant_slots(DOC, SF, SLOTS):
        out[R.variant_of(DOC, SF, s)["id"]] = DC.walked(DOC, SF, s)[0]
    return out


@pytest.fixture(scope="module")
def pack():
    return D.build(DOC)


def top(rid):
    return next(r for r in SF["rooms"] if r["id"] == rid)


def rec(rid):
    return next(r for r in RECORDS if r["id"] == rid)


# ------------------------------------------------------------------------------------------------- the record


def test_a_test_dungeon_on_the_crater_theme_with_its_own_clock_and_no_lockout_of_its_own():
    assert SF["theme"] == "night_crater" and SF["test"] is True and SF["test_why"]
    assert SF["gate_flag"] == "cobblers:flag/gym8_cleared" and SF["first_band"] == 5, "the roster's gate and floor (the draw, 2026-10-13)"
    assert SF["short"] not in [d["short"] for d in DOC["dungeons"] if d is not SF]
    assert set(SF["clock_s_by_band"]) == {str(b["band"]) for b in DOC["engine"]["bands"]}
    assert max(SF["clock_s_by_band"].values()) < 3600
    assert "lockout_ticks" not in SF and D.lockout_of(DOC, SF) == DOC["engine"]["lockout_ticks"]
    assert len(SLOTS) == DOC["engine"]["slots"]["per_dungeon"]


def test_the_engine_and_the_room_kit_find_no_problem_with_it_in_any_variant():
    assert R.problems(DOC, SF) == []
    assert [p for p in D.problems(DOC) if "starfall" in p] == []
    for s in R.variant_slots(DOC, SF, SLOTS):
        assert R.walk_problems(DOC, SF, s) == [], R.variant_of(DOC, SF, s)["id"]
        assert SP.check_setpieces(DOC, R.resolve(DOC, SF, s), s) == []


def test_the_clock_is_about_32_minutes_required_at_band_one_and_the_authored_clock_covers_the_formula(walks):
    slack = DOC["engine"]["clock"]["slack_factor"]
    want = DC.derive(DOC, SF)
    own = SF["clock_s_by_band"]
    # the formula plus the set piece's 25 s at every band (MEGA-INTEGRATE: each dungeon's vaults are priced on its own
    # clock, so no band is raised to the shortest other dungeon's any more)
    for b, s in want.items():
        req = max(sum(DC.required(DOC, SF, int(b), DC.clock_rooms(DOC, SF, int(b), w)).values()) for w in walks.values())
        assert own[b] == int(-(-((req + 25) * slack) // 60)) * 60, (b, own[b], req)
        assert s <= own[b] <= s + 120, (b, own[b], s)
    req1 = max(sum(DC.required(DOC, SF, 1, DC.clock_rooms(DOC, SF, 1, w)).values()) for w in walks.values())
    assert 30 * 60 <= req1 <= 35 * 60, req1 / 60
    assert abs(own["1"] - req1 * slack) <= 120
    assert DC.clock_problems(DOC, SF) == []
    assert "set piece" in SF["clock_why"]


def test_wide_rooms_short_connectors_and_a_route_that_turns_climbs_drops_and_doubles_back():
    rooms = R.layout(DOC, SF, SLOT)
    for r in rooms:
        if R.flags_of(r["kind"])["connector"]:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
    shaped = [r for r in rooms if r["shape"] != "box"]
    assert len({r["shape"] for r in shaped}) >= 5
    assert {d["side"] for r in rooms for d in r["doors"]} == {"north", "south", "east", "west"}
    assert any(any(d["y"] > r["floor_in"] for d in r["doors"] if d["dir"] == "out") for r in rooms), "a landing"
    assert [r["id"] for r in rooms if r.get("dir") == "west"], "a stretch walked back west"
    floors = [r["floor_in"] for r in rooms]
    assert max(floors) - min(floors) >= 10, "climbs and drops"


def test_every_room_type_the_owner_named_is_there_with_ours_the_heal_and_the_set_piece():
    kinds = {r["kind"] for r in RECORDS}
    assert OWNER_NAMED <= kinds, OWNER_NAMED - kinds
    assert len(kinds & OURS) >= 5, kinds & OURS
    assert any(r["kind"] == "safe_room" and r.get("params", {}).get("healer") for r in RECORDS)
    main = [r for r in SF["rooms"] if r["kind"] not in R.CONTAINERS]
    assert main[0]["kind"] == "entry_room" and [r["kind"] for r in main][-3:] == ["setpiece", "boss_arena", "exit_room"]
    (sp,) = [r for r in RECORDS if r["kind"] == "setpiece"]
    assert sp["params"]["piece"] == "lights_out" and sp["params"]["pit"] == 0, "the crater's set piece: the stars go out"


def test_the_pacing_no_two_fights_meet_on_any_route_and_the_heal_past_halfway(walks):
    for s in R.variant_slots(DOC, SF, SLOTS):
        rooms = R.layout(DOC, SF, s)
        by_i = {r["i"]: r for r in rooms}
        for r in rooms:
            for d in r["doors"]:
                if d["dir"] == "out" and not d.get("shortcut"):
                    n = by_i[d["to"]]
                    assert not (r["kind"] in FIGHTS and n["kind"] in FIGHTS), (r["id"], n["id"])
    for vid, rows in walks.items():
        path = list(DC.clock_rooms(DOC, SF, 1, rows))
        order = {r["id"]: k for k, r in enumerate(rows)}
        path.sort(key=lambda r: order[r["id"]])
        total = sum(r["walk"] for r in path)
        before = 0
        for r in path:
            if r["kind"] == "safe_room":
                break
            before += r["walk"]
        assert 0.5 <= before / total <= 0.85, (vid, before / total)   # measured 0.53 (variant a): past halfway by blocks, before the long climb, the procession and the boss


# ------------------------------------------------------------------------------------------------- forks and the wing


def test_two_forks_each_through_a_crossroads_that_sees_every_way_one_of_them_three_ways():
    rooms = SF["rooms"]
    forks = [(k, r) for k, r in enumerate(rooms) if r["kind"] == "fork"]
    assert sorted(len(f["routes"]) for _k, f in forks) == [2, 3]
    for k, f in forks:
        assert rooms[k - 1]["kind"] == "crossroads"
        lk = [rt["look"] for rt in f["routes"]]
        assert len(set(lk)) == len(lk) and all(rt.get("sign") for rt in f["routes"])
    for s in R.variant_slots(DOC, SF, SLOTS):
        lay = R.layout(DOC, SF, s)
        built = {b.room["id"]: b for b in R.slot_build(DOC, SF, s)}
        for k, f in forks:
            host = next(r for r in lay if r["id"] == rooms[k - 1]["id"])
            outs = [d["side"] for d in host["doors"] if d["dir"] == "out"]
            assert len(outs) == len(f["routes"]) == len(set(outs)), outs
            assert built[host["id"]].anchors.get("hub")
            join = next(r for r in lay if r["id"] == rooms[k + 1]["id"])
            assert len([d for d in join["doors"] if d["dir"] == "in"]) == len(f["routes"])


def test_the_three_ways_ask_different_things_and_the_clock_pays_a_non_optional_one(walks):
    by = {rt["id"]: {r["kind"] for r in rt["rooms"]} for rt in top("f_rim")["routes"]}
    assert "collapse_bridge" in by["sky_bridge"] and "dark_room" in by["the_crack"] and "puzzle" in by["lake"]
    for rows in walks.values():
        for b in range(1, 7):
            paid = {r["route"] for r in DC.clock_rooms(DOC, SF, b, rows) if r["route"] != "main"}
            assert not any(p.startswith("f_lens/the_scar") for p in paid), "the wing is never paid"
            assert any(p.startswith("f_rim/") for p in paid) and "f_lens/star_stair" in paid, paid


def test_a_four_room_optional_wing_a_hard_parkour_and_the_prize_with_a_balcony_secret_the_clock_never_counts(walks):
    (wing,) = [rt for rt in top("f_lens")["routes"] if rt.get("optional")]
    kinds = [r["kind"] for r in wing["rooms"]]
    assert len(kinds) == 4 and R.flags_of(kinds[0])["connector"] and "habitat" in kinds
    (pk,) = [r for r in wing["rooms"] if r["kind"] == "parkour"]
    assert pk["params"]["hard"] is True and pk["params"]["sections"] >= 5
    (hab,) = [r for r in wing["rooms"] if r["kind"] == "habitat"]
    assert hab["params"].get("prize") and hab.get("gate", "open") == "open" and not DF.is_wild_room(hab)
    assert [s["type"] for s in hab["secrets"]] == ["balcony"] and hab["params"].get("relic")
    ids = {r["id"] for r in wing["rooms"]}
    for rows in walks.values():
        for b in range(1, 7):
            assert not ids & {r["id"] for r in DC.clock_rooms(DOC, SF, b, rows)}


def test_two_parkours_a_six_section_main_one_and_a_hard_one_in_the_wing():
    pks = {r["id"]: r for r in RECORDS if r["kind"] == "parkour"}
    assert len(pks) == 2
    (hard,) = [r for r in pks.values() if r["params"].get("hard")]
    (main,) = [r for r in pks.values() if not r["params"].get("hard")]
    assert main["params"]["sections"] == 6 and main["width"] == 25 and hard["width"] == 25
    for s in R.variant_slots(DOC, SF, SLOTS):
        built = {b.room["id"]: b for b in R.slot_build(DOC, SF, s)}
        for rid, r in pks.items():
            m = built[rid].meta
            assert len(m["ledges"]) == r["params"]["sections"] + 1, (rid, s["k"])
            assert (m["fork"] is None) == bool(r["params"].get("hard")), (rid, m["fork"])


def test_at_least_three_of_the_six_optional_rooms_each_on_a_side_entry_never_paid():
    for s in SLOTS:
        lay = R.layout(DOC, SF, s)
        mine = [r for r in lay if r["kind"] in EXTRA_KINDS]
        assert len({r["kind"] for r in mine}) >= 3
        for r in mine:
            assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open", (s["g"], r["id"])
    rows = DC.walked(DOC, SF)[0]
    paid = {r["id"] for b in DOC["engine"]["bands"] for r in DC.clock_rooms(DOC, SF, b["band"], rows)}
    assert not paid & {r["id"] for r in rows if r["kind"] in EXTRA_KINDS | {"vault"}}


def test_the_vault_pays_no_more_than_the_runs_time_gathering():
    import dungeon_greed as DG
    assert [x for x in DG.vault_over(DOC) if x[0] == "starfall"] == []


def test_three_secrets_each_with_a_unique_relic_and_short_lore_and_one_shortcut(pack):
    secret_rooms = [r for r in RECORDS if r.get("secrets")]
    assert sorted(s["type"] for r in secret_rooms for s in r["secrets"]) == ["balcony", "cracked", "cracked"]
    relics = [r["params"]["relic"] for r in secret_rooms]
    assert len(set(relics)) == 3 and all(re.fullmatch(r"sf_[a-z0-9_]+", x) for x in relics)
    for r in secret_rooms:
        lore = r["params"]["lore"]
        assert 0 < len(lore) <= 160 and lore.isascii() and lore.isprintable()
    scs = [(r["id"], sc) for r in RECORDS for sc in r.get("shortcuts") or []]
    assert len(scs) == 1
    far_id, sc = scs[0]
    for s in R.variant_slots(DOC, SF, SLOTS):
        rooms = {r["id"]: r for r in R.layout(DOC, SF, s)}
        assert rooms[sc["to"]]["i"] < rooms[far_id]["i"]
        assert [d for d in rooms[far_id].get("shortcut_doors", []) if d["dir"] == "out"]
    assert any(k.endswith("/room/starfall/%s/s%d/shortcut_%s.mcfunction" % (far_id, SLOT["g"], sc["id"])) for k in pack)


def test_four_distinct_variants_one_per_slot():
    vs = SF["variants"]
    assert len(vs) == 4 and [R.variant_of(DOC, SF, s)["id"] for s in SLOTS] == [v["id"] for v in vs]
    assert any(v.get("mirror") for v in vs) and any(v.get("seed") for v in vs) and any(v.get("swap") for v in vs)
    shapes = []
    for s in SLOTS:
        rooms = R.layout(DOC, SF, s)
        built = R.slot_build(DOC, SF, s)
        shapes.append(tuple((r["id"], r["za"] - s["z0"], r["kind"], len(b.ops)) for r, b in zip(rooms, built)))
    assert len(set(shapes)) == 4


# ------------------------------------------------------------------------------------------------- fights and variety


def test_the_stands_and_ambushes_rotate_two_teams_a_band_and_pass_the_fight_checks():
    n = 0
    for s in R.variant_slots(DOC, SF, SLOTS):
        for r in R._walk_records(R.resolve(DOC, SF, s)["rooms"]):
            if r["kind"] in ("stand", "gauntlet", "ambush"):
                assert r["gate"] == "cleared" and DF.stand_problems(DOC, r) == [], r["id"]
                for t in r["params"]["trainers"]:
                    assert "team_by_band" not in t and all(len(v) >= 2 for v in t["team_pool_by_band"].values()), t["name"]
                    n += 1
    assert n == 4 * 4


def test_the_miniboss_rotates_catchable_non_legendaries_and_the_boss_has_two_crews_a_band_with_one_ace():
    import dungeon_prize as PZ
    labels = PZ.jar_labels()
    mb = rec("strike_bowl")["params"]
    assert mb["catchable"] is True and mb["level_offset"] <= 0
    for b, pool in mb["species_pool_by_band"].items():
        assert len(pool) >= 2
        if labels:
            assert not any(set(labels.get(sp, ())) & {"legendary", "mythical", "ultra_beast", "paradox"} for sp in pool)
    bo = SF["boss"]
    assert bo["heal_between_stages"] is True and len(bo["stage_level_offsets"]) == 2
    assert bo["name"] not in [d["boss"]["name"] for d in DOC["dungeons"] if d is not SF]
    for b in range(1, 7):
        crews = [bo["teams"][str(b)]] + bo["teams_alt_by_band"][str(b)]
        for stages in crews:
            assert len(stages) == 2 and all(1 <= len(c) <= 6 for c in stages)
        assert len({c[-1] for stages in crews for c in stages}) == 1, b
        assert len({json.dumps(c) for c in crews}) == len(crews)


def test_the_prize_is_exactly_the_rosters_pools_bands_five_and_six_only(pack):
    import dungeon_prize as PZ
    hab = rec("impact")
    pz = hab["params"]["prize"]
    assert pz["roster"] == "starfall" and not pz.get("rare_by_band") and not pz.get("legendary_by_band")
    assert not pz.get("rare_pool_by_band") and not pz.get("legendary_pool_by_band"), "the roster's pools, nothing added"
    assert PZ.room_problems(DOC, SF, hab) == []
    for b in range(1, 7):
        want = [sp for sp in ROSTER["legendary_pool_by_band"].get(str(b), []) if not PZ.model_gated(DOC, sp)]
        got = PZ.pool_at(DOC, hab, b)
        assert (got[0] if got else []) == want, (b, got)
        assert not got or got[1] is True, "a legendary pool: the Beast Ball key"
    assert not ROSTER["rare_pool_by_band"]
    base = R.room_fn(SF, hab, SLOT, "")
    enter = pack["data/%s/function/%s.mcfunction" % (R.NS, (base + "enter").split(":", 1)[1])]
    assert "prize/spawn_b5" in enter and "prize/spawn_b6" in enter and "prize/spawn_b1" not in enter


def all_species():
    out = set()

    def add(x):
        if isinstance(x, str):
            out.add(x)
        elif isinstance(x, (list, tuple)):
            for y in x:
                add(y)
        elif isinstance(x, dict):
            for y in x.values():
                add(y)
    for r in RECORDS:
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            add(t.get("team_by_band", {}))
            add(t.get("team_pool_by_band", {}))
        if r["kind"] in ("nest", "habitat") and "species" in p:
            add(p["species"])
        add(p.get("species_by_band", {}))
        add(p.get("species_pool_by_band", {}))
    add(SF["boss"]["teams"])
    add(SF["boss"]["teams_alt_by_band"])
    add(ROSTER["legendary_pool_by_band"])
    return out


def test_every_species_is_in_the_cobblemon_jar():
    import battle_sim as B
    try:
        sp, _m, _c = B.load_pack(B.find_jar())
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar on this machine")
    assert sorted(s for s in all_species() if B.key(s) not in sp) == []


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_stands_at_its_slot_on_the_trail_clear_of_the_other_rips():
    f = RIP[SF["id"]]["frame"]
    cx = (f["x0"] + f["x1"]) / 2
    assert abs(cx - 1675) <= 10 and abs(f["z"] - 4118) <= 3 and RIP[SF["id"]]["test"] is True
    for d in DOC["dungeons"]:
        if d is SF:
            continue
        o = RIP[d["id"]]["frame"]
        assert f["x1"] + 3 < o["x0"] or o["x1"] + 3 < f["x0"] or abs(f["z"] - o["z"]) > 3, d["id"]
    assert RIP[SF["id"]]["click"] == [cx, f["y"], f["z"] + 1]


def test_the_rip_stands_on_the_heightmaps_ground_and_above_the_sea():
    try:
        import ground as GR
        import terrain as T
        g = GR.load()
    except Exception as e:
        pytest.skip("no canonical heightmap: %s" % e)
    f = RIP[SF["id"]]["frame"]
    sea = T.sea_level(g.world)
    for x in range(f["x0"], f["x1"] + 1):
        for z in (f["z"], f["z"] + 1):
            assert g(x, z) + 1 == f["y"] and g(x, z) > sea, (x, z, g(x, z))
    ox, oy, oz, _yaw = RIP[SF["id"]]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy


# ------------------------------------------------------------------------------------------------- generator mutations


def test_mutating_the_starlight_in_the_floor_off_leaves_the_tall_halls_dark_and_the_walk_check_says_so(monkeypatch):
    # the crater's tall rooms (the slip, the strike bowl, the impact) are lit from the floor course (hull.tall_lights)
    R._BUILT.clear()
    monkeypatch.setattr(R, "floor_lights", lambda *a, **k: None)
    monkeypatch.setattr(R, "cap_dark_dressing", lambda *a, **k: None)
    monkeypatch.setattr(R, "light_dark_cells", lambda *a, **k: None)
    bad = R.walk_problems(DOC, SF, SLOT)
    R._BUILT.clear()
    assert any("no light" in p for p in bad), bad[:3]


def test_mutating_the_kit_so_rooms_never_touch_loses_the_shortcut_and_the_plan_check_says_so(monkeypatch):
    R._BUILT.clear()
    monkeypatch.setattr(R, "_touch", lambda far, near: None)
    bad = R.plan_problems(DOC, SF, SLOT)
    R._BUILT.clear()
    assert any("shortcut c_camp" in p and "does not touch" in p for p in bad), bad[:3]


def test_the_build_writes_one_shell_function_per_room_inside_the_chain_budget(pack):
    shell = [k for k in pack if "/shells/s%d/" % SLOT["g"] in k]
    assert len(shell) == len(R.layout(DOC, SF, SLOT))
    for s in SLOTS:
        assert R.chain_problems(DOC, SF, s) == []
