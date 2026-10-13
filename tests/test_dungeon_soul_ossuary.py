"""The Soul Ossuary (`soul_ossuary` in data/dungeons.json), authored by unit NEW-OSSUARY (2026-10-11) to the roster's entry
(data/dungeon_prize_roster.json soul_ossuary) on the soul_sand_valley theme.

The author's own tests (the independent review is another agent's, and tools/dungeon_independent_audit.py walks it on its
own graph): the record builds and walks in all four variants; its main route's required time is about 32 minutes at band
1 with every clock under an hour; the rooms are shaped, turn, climb, drop, double back and stack; every room type the
owner named is there; two forks through crossroads (one three ways); a four-room optional wing ending in the prize
habitat (the roster's pool, legendary only from band 5 as the roster gives it, the model-gated species dropped); two
parkours; at least three of the six optional rooms as side rooms; three secrets with relics; a shortcut; four variants;
the lights-out set piece in the soul valley's own palette before the boss; per-run variety through the rotation pools on
every trainer, the mini-boss and the boss; the boss's ace is the roster's Ultra Beast; species from the 1.8.0 jar,
themed (no Fire type but the ace, no doll species but the ones the roster assigns); the rip on dry measured ground on the
test trail. Two GENERATOR mutations: the set piece's palette entry ignored, and rooms that never touch.

Not covered: anything in a running Minecraft; bands 5 and 6 balance (untuned, the simulator has no Pokemon past gym 8).
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
import dungeon_audit as DA  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import dungeon_setpieces as SP  # noqa: E402

DID = "soul_ossuary"
DOC = D.load()
RIP = {r["legacy_dungeon"]: r for r in DOC["retired_rips"]}   # the 13 test rips, RETIRED 2026-10-13 (retired_rips in data/dungeon_rips.json): the records are kept
SO = next(d for d in DOC["dungeons"] if d["id"] == DID)
SLOTS = [s for s in D.slots(DOC) if s["dungeon"]["id"] == DID]
SLOT = SLOTS[0]
RECORDS = list(R._walk_records(SO["rooms"]))
FIGHTS = {"stand", "gauntlet", "ambush", "nest", "miniboss", "habitat", "boss_arena"}
OWNER_NAMED = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "bank_vault", "dark_room", "collapse_bridge", "safe_room", "setpiece"}
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
ROSTER = json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))
ENTRY = next(e for e in ROSTER["dungeons"] if e["id"] == DID)


def by_id(rid):
    """A room, fork or side entry by id, anywhere in the record."""
    def walk(rooms):
        for r in rooms:
            yield r
            for sub in ([r] if r["kind"] == "side" else []) + r.get("routes", []):
                yield from walk(sub["rooms"])
    return next(r for r in walk(SO["rooms"]) if r["id"] == rid)


def wing():
    (w,) = [r for r in SO["rooms"] if r["kind"] == "side" and len(r["rooms"]) > 1
            and not any(x["kind"] in EXTRA_KINDS for x in r["rooms"])]
    return w


@pytest.fixture(scope="module")
def walks():
    return {R.variant_of(DOC, SO, s)["id"]: DC.walked(DOC, SO, s)[0] for s in R.variant_slots(DOC, SO, SLOTS)}


@pytest.fixture(scope="module")
def pack():
    return D.build(DOC)


# ------------------------------------------------------------------------------------------------- the record


def test_a_test_dungeon_open_to_every_band_with_its_own_clock_and_no_lockout_of_its_own():
    assert SO["theme"] == "soul_sand_valley" and SO["test"] is True and SO["test_why"]
    assert SO["gate_flag"] == "cobblers:flag/gym8_cleared" and SO["first_band"] == 5, "the roster's campaign gate and floor"
    assert SO["short"] not in [d["short"] for d in DOC["dungeons"] if d is not SO]
    assert set(SO["clock_s_by_band"]) == {str(b["band"]) for b in DOC["engine"]["bands"]}
    assert max(SO["clock_s_by_band"].values()) <= 3600
    assert "lockout_ticks" not in SO and D.lockout_of(DOC, SO) == DOC["engine"]["lockout_ticks"]


def test_the_engine_and_the_room_kit_find_no_problem_with_it_in_any_variant():
    assert R.problems(DOC, SO) == []
    assert [p for p in D.problems(DOC) if DID in p] == []
    for s in R.variant_slots(DOC, SO, SLOTS):
        assert SP.check_setpieces(DOC, R.resolve(DOC, SO, s), s) == []


def test_the_clock_is_about_32_minutes_required_at_band_one_and_the_authored_clock_covers_the_formula(walks):
    slack = DOC["engine"]["clock"]["slack_factor"]
    want = DC.derive(DOC, SO)
    own = SO["clock_s_by_band"]
    for b, s in want.items():
        assert s <= own[b] <= s + 120, (b, own[b], s)
    req1 = max(sum(DC.required(DOC, SO, 1, DC.clock_rooms(DOC, SO, 1, w)).values()) for w in walks.values())
    assert 30 * 60 <= req1 <= 34 * 60, req1 / 60
    assert abs(own["1"] - req1 * slack) <= 120
    assert DC.clock_problems(DOC, SO) == []
    assert DA.design_room_clocks()[DID] == [own[str(b)] // 60 for b in range(1, 7)]
    assert "set piece" in SO["clock_why"]


def test_rooms_are_shaped_turn_climb_drop_double_back_and_the_catacomb_runs_under_the_nave():
    rooms = R.layout(DOC, SO, SLOT)
    shaped = [r for r in rooms if r["shape"] != "box"]
    assert len(shaped) > len(rooms) / 2 and len({r["shape"] for r in shaped}) >= 5
    assert {d["side"] for r in rooms for d in r["doors"]} == {"north", "south", "east", "west"}
    assert [r["id"] for r in rooms if r.get("dir") == "west"]
    floors = [r["floor_in"] for r in rooms]
    assert max(floors) - min(floors) >= 10
    for r in rooms:
        if R.flags_of(r["kind"])["connector"]:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
    by = {r["id"]: r for r in rooms}
    u, c = by["catacomb"], by["nave"]
    assert u["xa"] < c["xb"] and c["xa"] < u["xb"] and u["za"] < c["zb"] and c["za"] < u["zb"] and u["ceil_y"] < c["hull_lo"]


def test_every_room_type_the_owner_named_is_there_with_ours_the_heal_and_the_set_piece():
    kinds = {r["kind"] for r in RECORDS}
    assert OWNER_NAMED <= kinds, OWNER_NAMED - kinds
    assert len(kinds & OURS) >= 5, kinds & OURS
    assert any(r["kind"] == "safe_room" and r.get("params", {}).get("healer") for r in RECORDS)
    main = [r for r in SO["rooms"] if r["kind"] not in R.CONTAINERS]
    assert main[0]["kind"] == "entry_room" and [r["kind"] for r in main][-3:] == ["setpiece", "boss_arena", "exit_room"]


def test_no_two_fights_meet_on_any_route_and_the_heal_is_about_two_thirds_in(walks):
    for s in R.variant_slots(DOC, SO, SLOTS):
        rooms = R.layout(DOC, SO, s)
        by_i = {r["i"]: r for r in rooms}
        for r in rooms:
            for d in r["doors"]:
                if d["dir"] == "out" and not d.get("shortcut"):
                    assert not (r["kind"] in FIGHTS and by_i[d["to"]]["kind"] in FIGHTS), (r["id"], by_i[d["to"]]["id"])
    for vid, rows in walks.items():
        order = {r["id"]: k for k, r in enumerate(rows)}
        path = sorted(DC.clock_rooms(DOC, SO, 1, rows), key=lambda r: order[r["id"]])
        total = sum(r["walk"] for r in path)
        before = 0
        for r in path:
            if r["kind"] == "safe_room":
                break
            before += r["walk"]
        assert 0.6 <= before / total <= 0.8, (vid, before / total)


# ------------------------------------------------------------------------------------------------- choices and the wing


def test_two_forks_each_through_a_crossroads_that_sees_every_way_one_of_them_three_ways():
    top = SO["rooms"]
    forks = [(k, r) for k, r in enumerate(top) if r["kind"] == "fork"]
    assert sorted(len(f["routes"]) for _k, f in forks) == [2, 3]
    looks = set(R.load_themes()["themes"]["soul_sand_valley"]["crossroads"]["looks"])
    for k, f in forks:
        assert top[k - 1]["kind"] == "crossroads"
        lk = [rt["look"] for rt in f["routes"]]
        assert len(set(lk)) == len(lk) and set(lk) <= looks and all(rt.get("sign") for rt in f["routes"])
    for s in R.variant_slots(DOC, SO, SLOTS):
        rooms = R.layout(DOC, SO, s)
        for k, f in forks:
            host = next(r for r in rooms if r["id"] == top[k - 1]["id"])
            outs = [d["side"] for d in host["doors"] if d["dir"] == "out"]
            assert len(outs) == len(f["routes"]) == len(set(outs)), outs
            join = next(r for r in rooms if r["id"] == top[k + 1]["id"])
            assert len([d for d in join["doors"] if d["dir"] == "in"]) == len(f["routes"])


def test_the_ways_ask_different_things_and_the_safe_way_is_the_long_way(walks):
    ways = {rt["id"]: {r["kind"] for r in rt["rooms"]} for rt in by_id("ways")["routes"]}
    assert ways["pickers"] & {"stand", "gauntlet"} and "collapse_bridge" in ways["spine"]
    assert not ways["riverbed"] & {"collapse_bridge", "parkour", "stand", "gauntlet", "ambush", "nest"}
    court = {rt["id"]: {r["kind"] for r in rt["rooms"]} for rt in by_id("court_fork")["routes"]}
    assert "puzzle" in court["seal"] and "dark_room" in court["crypt"] and "puzzle" not in court["crypt"]
    walk = lambda rows, f, rt: sum(r["walk"] for r in rows if r["route"] == "%s/%s" % (f, rt))  # noqa: E731
    for vid, rows in walks.items():
        assert walk(rows, "ways", "riverbed") > walk(rows, "ways", "spine"), vid
        assert walk(rows, "court_fork", "crypt") > walk(rows, "court_fork", "seal"), vid


def test_a_four_room_optional_wing_ending_in_the_prize_the_clock_never_counts(walks):
    w = wing()
    kinds = [r["kind"] for r in w["rooms"]]
    assert len(kinds) == 4 and R.flags_of(kinds[0])["connector"] and kinds[-1] == "habitat"
    (pk,) = [r for r in w["rooms"] if r["kind"] == "parkour"]
    assert pk["params"]["hard"] is True and pk["params"]["sections"] >= 5
    end = w["rooms"][-1]
    assert end["params"].get("prize") and end.get("gate", "open") == "open"
    assert [s["type"] for s in end["secrets"]] == ["balcony"] and end["params"].get("relic")
    ids = {r["id"] for r in w["rooms"]}
    assert SO["rooms"][[r["id"] for r in SO["rooms"]].index(w["id"]) - 1]["kind"] == "safe_room", "healed before the wing"
    for s in R.variant_slots(DOC, SO, SLOTS):
        by = {r["id"]: r for r in R.layout(DOC, SO, s)}
        assert all(by[i]["route"] == w["id"] for i in ids)
        assert not [d for d in by[end["id"]]["doors"] if d["dir"] == "out"]
    for rows in walks.values():
        for b in range(1, 7):
            assert not ids & {r["id"] for r in DC.clock_rooms(DOC, SO, b, rows)}


def test_two_parkours_a_six_section_main_one_and_a_hard_one_in_the_wing():
    pks = {r["id"]: r for r in RECORDS if r["kind"] == "parkour"}
    assert len(pks) == 2
    (main,) = [r for r in SO["rooms"] if r["kind"] == "parkour"]
    assert main["params"]["sections"] == 6 and main["width"] == 25 and not main["params"].get("hard")
    for s in R.variant_slots(DOC, SO, SLOTS):
        built = {b.room["id"]: b for b in R.slot_build(DOC, SO, s)}
        for rid, r in pks.items():
            m = built[rid].meta
            assert len(m["ledges"]) == r["params"]["sections"] + 1, (rid, s["k"])
            assert (m["fork"] is None) == bool(r["params"].get("hard")), rid


def test_four_optional_rooms_as_side_rooms_off_the_route_never_paid_and_the_bank_vault_within_budget():
    import dungeon_greed as DG
    for s in SLOTS:
        lay = R.layout(DOC, SO, s)
        mine = [r for r in lay if r["kind"] in EXTRA_KINDS]
        assert len({r["kind"] for r in mine}) >= 3, s["g"]
        for r in mine:
            assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open", (s["g"], r["id"])
        bait = next(r for r in mine if r["kind"] == "bait_room")
        lure = next(r for r in lay if r["id"] == bait["params"]["lure_room"])
        assert lure["route"] == "main" and lure["kind"] not in FIGHTS | {"parkour"}
        bank = next(r for r in mine if r["kind"] == "bank_vault")
        main_ids = {r["id"] for r in lay if r["route"] == "main"}
        assert set(bank["params"]["clue_rooms"]) <= main_ids, "every digit is on the way: none on a fork route"
        assert all(next(r for r in lay if r["id"] == c)["i"] < bank["i"] for c in bank["params"]["clue_rooms"])
    rooms = DC.walked(DOC, SO)[0]
    paid = {r["id"] for b in DOC["engine"]["bands"] for r in DC.clock_rooms(DOC, SO, b["band"], rooms)}
    assert not paid & {r["id"] for r in rooms if r["kind"] in EXTRA_KINDS}
    assert [x for x in DG.vault_over(DOC) if x[0] == DID] == []


# ------------------------------------------------------------------------------------------------- the prize


def test_the_prize_is_the_rosters_pool_legendary_from_band_five_the_model_gated_dropped(pack):
    import dungeon_prize as PZ
    end = wing()["rooms"][-1]
    pz = end["params"]["prize"]
    assert pz["roster"] == DID and PZ.room_problems(DOC, SO, end) == []
    assert ENTRY["rare_pool_by_band"] == {} and not pz.get("rare_by_band") and not pz.get("rare_pool_by_band")
    roster_species = {sp for v in ENTRY["legendary_pool_by_band"].values() for sp in v}
    named = set(pz.get("legendary_by_band", {}).values()) | {sp for v in pz.get("legendary_pool_by_band", {}).values() for sp in v}
    assert named <= roster_species, "only the roster's species: none moved here from another dungeon"
    for b in range(1, 7):
        got = PZ.pool_at(DOC, end, b)
        if str(b) not in ENTRY["legendary_pool_by_band"]:
            assert got is None, (b, got)
            continue
        pool, leg = got
        assert leg and set(pool) <= roster_species
        assert all(not PZ.model_gated(DOC, sp) for sp in pool)
        gated = {sp for sp in roster_species if PZ.model_gated(DOC, sp)}
        assert set(pool) == roster_species - gated, (b, pool)
    files = pack
    for s in SLOTS:
        base = R.room_fn(SO, end, s, "")
        enter = files["data/%s/function/%s.mcfunction" % (R.NS, (base + "enter").split(":", 1)[1])]
        for b in (5, 6):
            assert "run function %sprize/spawn_b%d" % (base, b) in enter, (s["g"], b)
        for b in (1, 2, 3, 4):
            assert "prize/spawn_b%d" % b not in enter, (s["g"], b)


# ------------------------------------------------------------------------------------------------- secrets, shortcut, variants


def test_three_secrets_with_unique_relics_and_short_lore():
    secret_rooms = [r for r in RECORDS if r.get("secrets")]
    assert sorted(s["type"] for r in secret_rooms for s in r["secrets"]) == ["balcony", "cracked", "cracked"]
    relics = []
    for r in secret_rooms:
        p = r["params"]
        assert re.fullmatch(r"so_[a-z0-9_]+", p["relic"]) and len(p.get("relic_name", "")) <= 32
        assert 0 < len(p["lore"]) <= 160 and p["lore"].isascii() and p["lore"].isprintable()
        relics.append(p["relic"])
    assert len(relics) == len(set(relics)) == 3
    for s in R.variant_slots(DOC, SO, SLOTS):
        built = {b.room["id"]: b for b in R.slot_build(DOC, SO, s)}
        for r in secret_rooms:
            assert built[r["id"]].anchors.get("secret"), (r["id"], s["k"])


def test_a_shortcut_back_into_the_nave_opened_from_the_far_side(pack):
    scs = [(r["id"], sc) for r in RECORDS for sc in r.get("shortcuts") or []]
    assert len(scs) == 1 and scs[0][1]["to"] == "nave"
    far_id, sc = scs[0]
    for s in R.variant_slots(DOC, SO, SLOTS):
        rooms = {r["id"]: r for r in R.layout(DOC, SO, s)}
        assert rooms["nave"]["i"] < rooms[far_id]["i"]
        assert [d for d in rooms[far_id].get("shortcut_doors", []) if d["dir"] == "out"]
    assert any(k.endswith("/room/%s/%s/s%d/shortcut_%s.mcfunction" % (DID, far_id, SLOT["g"], sc["id"])) for k in pack)


def test_four_distinct_variants_one_per_slot():
    vs = SO["variants"]
    assert len(vs) == 4 and [R.variant_of(DOC, SO, s)["id"] for s in SLOTS] == [v["id"] for v in vs]
    assert any(v.get("mirror") for v in vs) and any(v.get("seed") for v in vs) and any(v.get("swap") for v in vs)
    shapes = set()
    for s in SLOTS:
        rooms = R.layout(DOC, SO, s)
        built = R.slot_build(DOC, SO, s)
        shapes.add(tuple((r["id"], r["za"] - s["z0"], r["kind"], len(b.ops)) for r, b in zip(rooms, built)))
    assert len(shapes) == 4


def test_the_set_piece_is_lights_out_in_the_soul_valleys_own_palette():
    (sp,) = [r for r in RECORDS if r["kind"] == "setpiece"]
    assert sp["params"]["piece"] == "lights_out" and sp["params"]["pit"] == 0
    pal = SP.palette("lights_out", "soul_sand_valley", R.load_themes()["themes"]["soul_sand_valley"])
    assert pal["trunk"].startswith("minecraft:bone_block") and "jungle" not in json.dumps(pal)
    built = {b.room["id"]: b for b in R.slot_build(DOC, SO, SLOT)}
    raw = {op[2] for op in built[sp["id"]].ops if op[0] in ("fill", "set")}
    assert pal["trunk"] in raw and {pal["floor_plant"], pal["floor_plant2"], pal["carpet"]} <= raw
    assert not {"minecraft:jungle_log[axis=y]", "minecraft:fern", "minecraft:moss_carpet"} & raw


# ------------------------------------------------------------------------------------------------- fights and variety


def test_every_trainer_rotates_two_teams_a_band_the_miniboss_a_pool_and_the_boss_an_alternate_crew():
    bands = {str(b["band"]) for b in DOC["engine"]["bands"]}
    for s in R.variant_slots(DOC, SO, SLOTS):
        for r in R._walk_records(R.resolve(DOC, SO, s)["rooms"]):
            if r["kind"] in ("stand", "gauntlet", "ambush"):
                assert r["gate"] == "cleared" and DF.stand_problems(DOC, r) == [], r["id"]
                for t in r["params"]["trainers"]:
                    assert "team_by_band" not in t and set(t["team_pool_by_band"]) == bands
                    assert all(len(v) == 2 and v[0] != v[1] for v in t["team_pool_by_band"].values()), t["name"]
    (mb,) = [r for r in RECORDS if r["kind"] == "miniboss"]
    pool = mb["params"]["species_pool_by_band"]
    assert set(pool) == bands and all(len(v) >= 2 for v in pool.values()) and mb["params"]["catchable"] is True
    bo = SO["boss"]
    assert bo["heal_between_stages"] is True and len(bo["stage_level_offsets"]) == 2
    assert set(bo["teams_alt_by_band"]) == bands
    for b in bands:
        for crews in [bo["teams"][b]] + bo["teams_alt_by_band"][b]:
            assert len(crews) == 2 and all(1 <= len(c) <= 6 for c in crews)
            assert {c[-1] for c in crews} == {ENTRY["ub_boss"]["species"]}, "the roster's Ultra Beast is the ace"


def all_species():
    out = set()
    for r in RECORDS:
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for teams in t["team_pool_by_band"].values():
                for team in teams:
                    out |= set(team)
        out |= set(p.get("species", [])) if isinstance(p.get("species"), list) else set()
        for v in p.get("species_pool_by_band", {}).values():
            out |= set(v)
    bo = SO["boss"]
    for crews in list(bo["teams"].values()) + [c for alts in bo["teams_alt_by_band"].values() for c in alts]:
        for c in crews:
            out |= set(c)
    return out


@pytest.fixture(scope="module")
def jar_species():
    import battle_sim as B
    try:
        sp, _m, _c = B.load_pack(B.find_jar())
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar on this machine")
    return sp


def doll_species():
    """COBBLEVERSE_COMPATIBILITY.md's 40 species with no client model (they render as the substitute doll)."""
    t = (ROOT / "docs" / "research" / "COBBLEVERSE_COMPATIBILITY.md").read_text(encoding="utf-8")
    i = t.index("except these 40")
    line = t[i:].split("\n", 2)[1]
    out = {w.strip(" .") for w in line.split(",")}
    assert len(out) == 40, len(out)
    return out


def test_species_are_in_the_jar_themed_no_fire_but_the_ace_and_no_doll_but_the_rosters(jar_species):
    import battle_sim as B
    sp = all_species()
    assert sorted(s for s in sp if B.key(s) not in jar_species) == []
    ace = ENTRY["ub_boss"]["species"]
    fire = sorted(s for s in sp if "fire" in (jar_species[B.key(s)].get("primaryType"), jar_species[B.key(s)].get("secondaryType")))
    assert fire == [ace], fire
    legend = {"legendary", "mythical", "ultra_beast", "paradox"}
    assert sorted(s for s in sp if set(jar_species[B.key(s)].get("labels", [])) & legend) == [ace]
    assert sorted(sp & doll_species()) == [ace], "the ace is the roster's; it renders as the doll until atm_subset ships"


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_is_a_test_rip_on_the_trail_clear_of_the_old_mine_and_the_other_rips():
    import route1_old_mine as M
    rip = RIP[SO["id"]]
    f = rip["frame"]
    assert rip["test"] is True
    cx = (f["x0"] + f["x1"]) / 2
    assert abs(cx - 1525) <= 10 and f["x1"] - f["x0"] == 4
    assert f["x0"] > max(x for x, _z in M.TRAIL) + 4
    for d in DOC["dungeons"]:
        if d is not SO:
            o = RIP[d["id"]]["frame"]
            assert f["x1"] + 3 < o["x0"] or o["x1"] + 3 < f["x0"] or abs(f["z"] - o["z"]) > 3, d["id"]
    assert rip["click"] == [cx, f["y"], f["z"] + 1]


def test_the_rip_stands_on_the_heightmaps_ground_and_above_the_sea():
    try:
        import ground as GR
        import terrain as T
        g = GR.load()
    except Exception as e:
        pytest.skip("no canonical heightmap: %s" % e)
    f = RIP[SO["id"]]["frame"]
    sea = T.sea_level(g.world)
    for x in range(f["x0"] - 2, f["x1"] + 3):
        for z in range(f["z"], f["z"] + 5):
            assert g(x, z) + 1 == f["y"] and g(x, z) > sea, (x, z, g(x, z))
    ox, oy, oz, _yaw = RIP[SO["id"]]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy


# ------------------------------------------------------------------------------------------------- generator mutations


def test_mutating_the_palette_to_ignore_the_themes_entry_brings_the_jungle_back_and_the_check_sees_it(monkeypatch):
    real = SP.palette
    monkeypatch.setattr(SP, "palette", lambda piece, theme_id, theme: real(piece, "jungle" if piece == "lights_out" else theme_id, theme))
    R._BUILT.clear()
    try:
        built = {b.room["id"]: b for b in R.slot_build(DOC, SO, SLOT)}
    finally:
        R._BUILT.clear()
    (sp,) = [r for r in RECORDS if r["kind"] == "setpiece"]
    raw = {op[2] for op in built[sp["id"]].ops if op[0] in ("fill", "set")}
    assert "minecraft:jungle_log[axis=y]" in raw and "minecraft:bone_block[axis=y]" not in raw


def test_mutating_the_kit_so_rooms_never_touch_loses_the_shortcut_and_the_plan_check_says_so(monkeypatch):
    R._BUILT.clear()
    monkeypatch.setattr(R, "_touch", lambda far, near: None)
    bad = R.plan_problems(DOC, SO, SLOT)
    R._BUILT.clear()
    assert any("shortcut c1" in p and "does not touch" in p for p in bad), bad[:3]
