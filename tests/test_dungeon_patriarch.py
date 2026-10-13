"""Under the Patriarch (`patriarch`, data/dungeons.json), authored on the room kit by unit NEW-PATRIARCH (2026-10-11) from
docs/mechanics/DUNGEON_3_PATRIARCH.md and the roster's `patriarch` entry (data/dungeon_prize_roster.json), theme
`great_tree`.

The author's own tests (the independent review is another agent's): the record builds and walks in all four variants;
its MAIN route's required time is about 32 minutes at band 1 and every clock is under an hour; the route descends 40
blocks through the Taproot and walks back west UNDER the first fork; two crossroads (three ways, then two) whose ways ask
different things; a four-room optional WING (a connector, a climb, a hard parkour) ending in the PRIZE habitat, whose
pools are exactly the roster's; a six-section main parkour; four optional rooms (bait, eggs, fishing, the crows' hoard
inside the vault budget); a cracked and a balcony secret with their relics; a shortcut back toward the entry; the
lights-out set piece before the Heart; trainers, mini-boss and boss rotating through pools; the Deino line as the boss's
ace and the roster's Ultra Beast pair as its band 4-6 alternates; every species in the Cobblemon 1.8.0 jar; the rip on dry
measured ground on the test trail. Two GENERATOR mutations (glow vines off, rooms that never touch) and the checks say so.

Not covered: anything in a running Minecraft; Yveltal (E-P6/E-P7, not built); the fight, puzzle and prize kinds' behaviour.
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

DOC = D.load()
RIP = {r["legacy_dungeon"]: r for r in DOC["rips"] if r.get("legacy_dungeon")}   # the test rips (data/dungeon_rips.json)
PT = next(d for d in DOC["dungeons"] if d["id"] == "patriarch")
SLOTS = [s for s in D.slots(DOC) if s["dungeon"]["id"] == "patriarch"]
SLOT = SLOTS[0]
RECORDS = list(R._walk_records(PT["rooms"]))
FIGHTS = {"stand", "gauntlet", "ambush", "nest", "miniboss", "habitat", "boss_arena"}
OWNER_NAMED = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room", "setpiece"}
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
ROSTER = json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))
ROSTER_PT = next(e for e in ROSTER["dungeons"] if e["id"] == "patriarch")


def by_id(rid):
    return next(r for r in RECORDS if r["id"] == rid)


@pytest.fixture(scope="module")
def walks():
    out = {}
    for s in R.variant_slots(DOC, PT, SLOTS):
        out[R.variant_of(DOC, PT, s)["id"]] = DC.walked(DOC, PT, s)[0]
    return out


@pytest.fixture(scope="module")
def pack():
    return D.build(DOC)


# ------------------------------------------------------------------------------------------------- the record


def test_the_patriarch_is_a_test_dungeon_after_the_first_three_with_no_lockout_of_its_own():
    ids = [d["id"] for d in DOC["dungeons"]]
    assert ids.index("patriarch") > max(ids.index(x) for x in ("night_shift", "jungle", "flooded_ruin")), \
        "appended: slots are numbered in list order (DUNGEON_3_PATRIARCH.md 8), so it never moves a built shell"
    assert PT["theme"] == "great_tree" and PT["test"] is True and PT["test_why"]
    assert PT["gate_flag"] is None and "spine" not in PT
    assert PT["short"] not in [d["short"] for d in DOC["dungeons"] if d is not PT]
    assert set(PT["clock_s_by_band"]) == {str(b["band"]) for b in DOC["engine"]["bands"]}
    assert max(PT["clock_s_by_band"].values()) <= 3600
    assert "lockout_ticks" not in PT and D.lockout_of(DOC, PT) == DOC["engine"]["lockout_ticks"]


def test_the_engine_and_the_room_kit_find_no_problem_with_it_in_any_variant():
    assert R.problems(DOC, PT) == []
    assert [p for p in D.problems(DOC) if "patriarch" in p or "pt" in p.split()] == []
    for s in R.variant_slots(DOC, PT, SLOTS):
        assert SP.check_setpieces(DOC, R.resolve(DOC, PT, s), s) == []


def test_the_clock_is_about_32_minutes_required_at_band_one_and_covers_the_formula(walks):
    slack = DOC["engine"]["clock"]["slack_factor"]
    want = DC.derive(DOC, PT)
    own = PT["clock_s_by_band"]
    for b, s in want.items():
        # the formula plus the set piece's allowance at every band (MEGA-INTEGRATE: each dungeon's vaults are priced on
        # its own clock, so band 4 is no longer held at the shortest band-4 clock standing)
        req = max(sum(DC.required(DOC, PT, int(b), DC.clock_rooms(DOC, PT, int(b), w)).values()) for w in walks.values())
        assert own[b] == int(-(-((req + 25) * slack) // 60)) * 60, (b, own[b], req)
        assert s <= own[b] <= s + 120, (b, own[b], s)
    req1 = max(sum(DC.required(DOC, PT, 1, DC.clock_rooms(DOC, PT, 1, w)).values()) for w in walks.values())
    assert 30 * 60 <= req1 <= 34 * 60, req1 / 60
    assert abs(own["1"] - (req1 + 25) * slack) <= 60
    assert DC.clock_problems(DOC, PT) == []
    assert DA.design_room_clocks()["patriarch"] == [own[str(b)] // 60 for b in range(1, 7)]


def test_adding_the_patriarch_moves_no_other_dungeons_vault_budget():
    import dungeon_greed as DG
    without = dict(DOC, dungeons=[d for d in DOC["dungeons"] if d is not PT])
    # each dungeon's vaults are priced on its own clock (MEGA-INTEGRATE), so no other dungeon's budget moves
    for d in without["dungeons"]:
        assert DG.vault_budget(DOC, dungeon=d) == DG.vault_budget(without, dungeon=d), d["id"]
    assert DG.vault_over(DOC) == []


def test_wide_rooms_short_connectors_and_a_tall_shaft(walks):
    for rows in walks.values():
        assert len(DC.clock_rooms(DOC, PT, 1, rows)) <= 24
    for r in R.layout(DOC, PT, SLOT):
        if R.flags_of(r["kind"])["connector"]:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
        elif r["route"] == "main" and r["kind"] not in ("entry_room", "exit_room"):
            assert 25 <= r["width"] <= 62, (r["id"], r["width"])
    assert by_id("taproot_head")["height"] >= 24 and by_id("cradle")["height"] >= 20


def test_most_rooms_are_shaped_and_the_route_descends_doubles_back_and_walks_under_itself():
    for s in R.variant_slots(DOC, PT, SLOTS):
        rooms = R.layout(DOC, PT, s)
        shaped = [r for r in rooms if r["shape"] != "box"]
        assert len(shaped) > 0.6 * len(rooms) and len({r["shape"] for r in shaped}) >= 5
        assert {d["side"] for r in rooms for d in r["doors"]} == {"north", "south", "east", "west"}
        by = {r["id"]: r for r in rooms}
        entry, heart = by["root_door"], by["the_heart"]
        assert entry["floor_in"] - heart["floor_in"] >= 36, "the Taproot's descent: the Heart lies 40 under the Root Door"
        assert by["taproot_head"]["doors"][0]["y"] - by["taproot_head"]["floor_in"] >= 20, "entered high up the shaft's wall"
        assert [r["id"] for r in rooms if r.get("dir") == "west"] == ["taproot", "root_walk", "root_cellar"]
        # the way back west runs UNDER the first fork: stacked rooms
        under = {(a["id"], b["id"]) for a in rooms for b in rooms
                 if a["i"] > b["i"] and a["ceil_y"] < b["hull_lo"] and a["xa"] < b["xb"] and b["xa"] < a["xb"]
                 and a["za"] < b["zb"] and b["za"] < a["zb"]}
        assert ("clear_pool", "crow_roost") in under and ("root_walk", "rot_hollow") in under, sorted(under)[:6]


def test_every_room_type_the_owner_named_is_there_with_ours_the_heal_and_the_set_piece():
    kinds = {r["kind"] for r in RECORDS}
    assert OWNER_NAMED <= kinds, OWNER_NAMED - kinds
    assert len(kinds & OURS) >= 5, kinds & OURS
    assert by_id("clear_pool")["kind"] == "safe_room" and by_id("clear_pool")["params"]["healer"] is True
    main = [r for r in PT["rooms"] if r["kind"] not in R.CONTAINERS]
    assert main[0]["kind"] == "entry_room" and [r["kind"] for r in main][-3:] == ["setpiece", "boss_arena", "exit_room"]
    sp = by_id("heart_dark")
    assert sp["params"]["piece"] == "lights_out" and sp["params"]["pit"] == 0


def test_the_pacing_no_two_fights_meet_and_the_heal_near_the_middle(walks):
    for s in R.variant_slots(DOC, PT, SLOTS):
        rooms = R.layout(DOC, PT, s)
        by_i = {r["i"]: r for r in rooms}
        for r in rooms:
            for d in r["doors"]:
                if d["dir"] == "out" and not d.get("shortcut"):
                    n = by_i[d["to"]]
                    assert not (r["kind"] in FIGHTS and n["kind"] in FIGHTS), (r["id"], n["id"])
    for vid, rows in walks.items():
        path = DC.clock_rooms(DOC, PT, 1, rows)
        order = {r["id"]: k for k, r in enumerate(rows)}
        path.sort(key=lambda r: order[r["id"]])
        total = sum(r["walk"] for r in path)
        before = sum(r["walk"] for r in path[:[r["kind"] for r in path].index("safe_room")])
        # the pool comes after the forager's and the crows' four fights and before the Pruner's two, the guard and the
        # boss: 40-60% of the paid walk (the six-section root bridges are after it)
        assert 0.4 <= before / total <= 0.6, (vid, before / total)


# ------------------------------------------------------------------------------------------------- replayability


def route_walk(rows, fork, route):
    return sum(r["walk"] for r in rows if r["route"] == "%s/%s" % (fork, route))


def route_kinds(route):
    return {r["kind"] for r in route["rooms"]}


def test_two_forks_each_through_a_crossroads_that_sees_every_way_one_of_them_three_ways():
    top = PT["rooms"]
    forks = [(k, r) for k, r in enumerate(top) if r["kind"] == "fork"]
    assert sorted(len(f["routes"]) for _k, f in forks) == [2, 3]
    looks = set(json.loads((ROOT / "data" / "dungeon_themes.json").read_text(encoding="utf-8"))["themes"]["great_tree"]
                ["crossroads"]["looks"])
    for k, f in forks:
        assert top[k - 1]["kind"] == "crossroads", top[k - 1]["id"]
        lk = [rt["look"] for rt in f["routes"]]
        assert len(set(lk)) == len(lk) and set(lk) <= looks and all(rt.get("sign") for rt in f["routes"])
        assert not any(rt.get("optional") for rt in f["routes"])
    for s in R.variant_slots(DOC, PT, SLOTS):
        rooms = R.layout(DOC, PT, s)
        built = {b.room["id"]: b for b in R.slot_build(DOC, PT, s)}
        for k, f in forks:
            host = next(r for r in rooms if r["id"] == top[k - 1]["id"])
            outs = [d["side"] for d in host["doors"] if d["dir"] == "out"]
            assert len(outs) == len(f["routes"]) == len(set(outs)), outs
            assert built[host["id"]].anchors.get("hub")
            join = next(r for r in rooms if r["id"] == top[k + 1]["id"])
            assert len([d for d in join["doors"] if d["dir"] == "in"]) == len(f["routes"])


def test_the_ways_ask_different_things_and_the_clock_pays_the_slower(walks):
    hol = {rt["id"]: rt for rt in next(r for r in PT["rooms"] if r["id"] == "f_hollow")["routes"]}
    assert set(hol) == {"roost", "heartrot", "sap_run"}
    assert route_kinds(hol["roost"]) & {"stand", "gauntlet"}, "the crows: a fight"
    assert "dark_room" in route_kinds(hol["heartrot"]) and "collapse_bridge" in route_kinds(hol["sap_run"])
    deep = {rt["id"]: rt for rt in next(r for r in PT["rooms"] if r["id"] == "f_deep")["routes"]}
    assert "puzzle" in route_kinds(deep["sap_locks"]) and not route_kinds(deep["long_root"]) - {"drift", "stairs"}
    for vid, rows in walks.items():
        assert route_walk(rows, "f_deep", "long_root") > route_walk(rows, "f_deep", "sap_locks"), vid
        for b in range(1, 7):
            paid = {r["route"] for r in DC.clock_rooms(DOC, PT, b, rows) if r["route"] != "main"}
            assert paid == {"f_hollow/roost", "f_deep/sap_locks"}, (vid, b, paid)


def wing():
    (w,) = [r for r in PT["rooms"] if r["kind"] == "side" and len(r["rooms"]) == 4]
    return w


def test_a_four_room_optional_wing_ends_in_the_prize_over_the_main_route(walks):
    w = wing()
    kinds = [r["kind"] for r in w["rooms"]]
    assert kinds == ["drift", "stairs", "parkour", "habitat"] and w["rooms"][1]["rise"] > 0
    pk = w["rooms"][2]
    assert pk["params"]["hard"] is True and pk["params"]["sections"] >= 5 and pk["width"] == 25
    end = w["rooms"][-1]
    assert end["params"].get("prize") and end.get("gate", "open") == "open" and "species" not in end["params"]
    assert [s["type"] for s in end["secrets"]] == ["balcony"] and end["params"].get("relic")
    ids = {r["id"] for r in w["rooms"]}
    for s in R.variant_slots(DOC, PT, SLOTS):
        rooms = R.layout(DOC, PT, s)
        by = {r["id"]: r for r in rooms}
        assert all(by[i]["route"] == w["id"] for i in ids)
        assert not [d for d in by[end["id"]]["doors"] if d["dir"] == "out"], "a dead end"
        p = by[pk["id"]]
        assert [r["id"] for r in rooms if r["route"] == "main" and r["ceil_y"] < p["hull_lo"] and r["xa"] <= p["xb"]
                and p["xa"] <= r["xb"] and r["za"] <= p["zb"] and p["za"] <= r["zb"]], "the crown run is over the main route"
    for rows in walks.values():
        for b in range(1, 7):
            assert not ids & {r["id"] for r in DC.clock_rooms(DOC, PT, b, rows)}


def test_four_optional_rooms_off_the_main_route_none_paid(walks):
    sides = [r for r in PT["rooms"] if r["kind"] == "side" and r is not wing()]
    kinds = sorted(x["kind"] for s in sides for x in s["rooms"] if x["kind"] not in ("drift",))
    assert kinds == ["bait_room", "egg_room", "fishing_room", "vault"], kinds
    assert len({"bait_room", "egg_room", "fishing_room"} & EXTRA_KINDS) == 3
    for s in SLOTS:
        lay = R.layout(DOC, PT, s)
        for r in lay:
            if r["kind"] in EXTRA_KINDS | {"vault"}:
                assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open", (s["g"], r["id"])
        bait = next(r for r in lay if r["kind"] == "bait_room")
        lure = next(r for r in lay if r["id"] == bait["params"]["lure_room"])
        assert lure["route"] == "main" and lure["kind"] not in FIGHTS | {"parkour"}
    for rows in walks.values():
        paid = {r["id"] for b in range(1, 7) for r in DC.clock_rooms(DOC, PT, b, rows)}
        assert not paid & {x["id"] for s in sides for x in s["rooms"]}


def test_the_crows_hoard_pays_no_more_than_the_runs_time_gathering():
    import dungeon_greed as DG
    budget = DG.vault_budget(DOC, dungeon=PT)     # its own clock's (MEGA-INTEGRATE)
    v = by_id("crows_hoard")
    tbl = DG.load()
    for b, spec in v["params"]["loot_by_band"].items():
        assert DG.chest_cp(tbl, spec) <= 0.95 * budget[int(b)] // v["params"]["chests"], b


def test_two_parkours_a_six_section_main_one_and_a_hard_one_in_the_wing():
    pks = {r["id"]: r for r in RECORDS if r["kind"] == "parkour"}
    assert set(pks) == {"root_bridges", "crown_run"}
    main = pks["root_bridges"]
    assert main["params"]["sections"] == 6 and main["width"] == 25 and main["length"] >= 30 * 6 - 10 + 2
    assert not main["params"].get("hard")
    for s in R.variant_slots(DOC, PT, SLOTS):
        built = {b.room["id"]: b for b in R.slot_build(DOC, PT, s)}
        for rid, r in pks.items():
            m = built[rid].meta
            assert len(m["ledges"]) == r["params"]["sections"] + 1, (rid, s["k"])
            assert (m["fork"] is None) == bool(r["params"].get("hard")), (rid, m["fork"])


def test_the_prize_pools_are_exactly_the_rosters_and_spawned_only_when_rolled(pack):
    import dungeon_prize as PZ
    end = wing()["rooms"][-1]
    assert end["params"]["prize"]["roster"] == "patriarch"
    assert PZ.room_problems(DOC, PT, end) == []
    lf = DOC["engine"]["prize"]["legendary_from_band"]
    for b in range(1, 7):
        kind = "legendary" if b >= lf else "rare"
        want = [sp for sp in ROSTER_PT["%s_pool_by_band" % kind][str(b)] if not PZ.model_gated(DOC, sp)]
        assert PZ.pool_at(DOC, end, b) == (want, b >= lf), b
    files = pack
    for s in SLOTS:
        base = R.room_fn(PT, end, s, "")
        rel = lambda name: "data/%s/function/%s.mcfunction" % (R.NS, (base + name).split(":", 1)[1])  # noqa: E731
        enter = files[rel("enter")]
        for b in range(1, 7):
            pool, leg = PZ.pool_at(DOC, end, b)
            for k, sp in enumerate(pool, 1):
                assert "run function %s%s" % (base, PZ.spawn_name(b, k)) in enter
                body = files[rel(PZ.spawn_name(b, k))]
                assert "species=%s" % sp in body or sp in body
                assert any(ln.endswith(PZ.bind_name(DOC, sp, leg)) for ln in body.split("\n")), (s["g"], b, sp)
        assert "random value 1..100" in "".join(v for k, v in files.items() if k.endswith("/slot/s%d/start.mcfunction" % s["g"]))


def test_two_secrets_one_cracked_one_balcony_each_with_a_unique_relic():
    secret_rooms = [r for r in RECORDS if r.get("secrets")]
    assert sorted(s["type"] for r in secret_rooms for s in r["secrets"]) == ["balcony", "cracked"]
    relics = []
    for r in secret_rooms:
        p = r["params"]
        assert re.fullmatch(r"pt_[a-z0-9_]+", p["relic"]) and len(p.get("relic_name", "")) <= 32
        assert 0 < len(p["lore"]) <= 160 and p["lore"].isascii() and p["lore"].isprintable()
        relics.append(p["relic"])
    assert len(set(relics)) == 2
    for s in R.variant_slots(DOC, PT, SLOTS):
        built = {b.room["id"]: b for b in R.slot_build(DOC, PT, s)}
        for r in secret_rooms:
            assert len(built[r["id"]].meta["secrets"]) == 1 and built[r["id"]].anchors.get("secret"), (r["id"], s["k"])


def test_a_shortcut_from_the_pool_back_onto_the_root_walk(pack):
    scs = [(r["id"], sc) for r in RECORDS for sc in r.get("shortcuts") or []]
    assert scs == [("clear_pool", {"id": "c1", "to": "root_walk"})]
    for s in R.variant_slots(DOC, PT, SLOTS):
        rooms = {r["id"]: r for r in R.layout(DOC, PT, s)}
        far, near = rooms["clear_pool"], rooms["root_walk"]
        assert near["i"] < far["i"] and [d for d in far.get("shortcut_doors", []) if d["dir"] == "out"]
    assert any(k.endswith("/room/patriarch/clear_pool/s%d/shortcut_c1.mcfunction" % SLOT["g"]) for k in pack)


def test_four_distinct_variants_one_per_slot():
    vs = PT["variants"]
    assert [R.variant_of(DOC, PT, s)["id"] for s in SLOTS] == [v["id"] for v in vs] == ["a", "b", "c", "d"]
    assert any(v.get("mirror") for v in vs) and any(v.get("seed") for v in vs) and any(v.get("swap") for v in vs)
    shapes = set()
    for s in SLOTS:
        rooms = R.layout(DOC, PT, s)
        built = R.slot_build(DOC, PT, s)
        shapes.add(tuple((r["id"], r["za"] - s["z0"], r["kind"], len(b.ops)) for r, b in zip(rooms, built)))
    assert len(shapes) == 4


# ------------------------------------------------------------------------------------------------- fights


def test_the_stands_and_the_ambushes_hold_their_pools_in_every_variant():
    for s in R.variant_slots(DOC, PT, SLOTS):
        for r in R._walk_records(R.resolve(DOC, PT, s)["rooms"]):
            if r["kind"] in ("stand", "gauntlet", "ambush"):
                assert r["gate"] == "cleared" and DF.stand_problems(DOC, r) == [], r["id"]
                for t in r["params"]["trainers"]:
                    assert all(len(v) == 2 for v in t["team_pool_by_band"].values()), (r["id"], t["name"])
            if r["kind"] in ("gauntlet", "ambush"):
                tr = r["params"]["triggers"]
                assert len(tr) == len(r["params"]["trainers"]) and tr == sorted(tr) and 0 < tr[0] and tr[-1] < 1


def test_the_wild_rooms_carry_the_contracts_fields():
    bands = {str(b["band"]) for b in D.bands(DOC)}
    nest = by_id("absol_hollow")["params"]
    assert nest["species"][0] == "absol" and set(nest["count_by_band"]) == bands and nest["clear"] == "pass"
    mb = by_id("heart_guard")
    p = mb["params"]
    assert mb["gate"] == "cleared" and set(p["species_pool_by_band"]) == bands and p["level_offset"] <= 0 and p["catchable"]
    assert all(len(v) == 3 for v in p["species_pool_by_band"].values())


def test_the_boss_two_stages_a_heal_between_the_deino_line_and_the_ultra_beast_pair():
    bo = PT["boss"]
    assert bo["heal_between_stages"] is True and len(bo["stage_level_offsets"]) == 2
    assert bo["name"] not in [d["boss"]["name"] for d in DOC["dungeons"] if d is not PT]
    ace = {"1": "deino", "2": "deino", "3": "zweilous", "4": "zweilous", "5": "hydreigon", "6": "hydreigon"}
    for b, crews in bo["teams"].items():
        assert [c[-1] for c in crews] == [ace[b], ace[b]] and all(1 <= len(c) <= 6 for c in crews)
    for b in ("4", "5", "6"):
        alts = bo["teams_alt_by_band"][b]
        assert sorted(a[1][-1] for a in alts) == ["celesteela", "kartana"] and all(a[0][-1] == ace[b] for a in alts)
        assert all(len(a[k]) == len(bo["teams"][b][k]) for a in alts for k in (0, 1)), "the clock prices teams[band]"
    assert set(ROSTER_PT["ub_boss"]["species"]) == {"kartana", "celesteela"}
    assert "yveltal" not in json.dumps(bo), "Yveltal's wild stage (E-P6) is not built"


# ------------------------------------------------------------------------------------------------- species


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
    for crews in list(PT["boss"]["teams"].values()) + [c for alts in PT["boss"]["teams_alt_by_band"].values() for c in alts]:
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


def test_every_species_is_in_the_cobblemon_jar_and_no_fight_holds_a_legendary_but_the_ub_pair(jar_species):
    import battle_sim as B
    assert sorted(s for s in all_species() if B.key(s) not in jar_species) == []
    legend = {s for s in all_species() if set(jar_species[B.key(s)].get("labels", [])) & {"legendary", "mythical", "ultra_beast"}}
    assert legend == {"kartana", "celesteela"}, legend


def test_the_roster_pools_carry_the_jars_labels(jar_species):
    import battle_sim as B
    for b, pool in ROSTER_PT["rare_pool_by_band"].items():
        for sp in pool:
            assert not set(jar_species[B.key(sp)].get("labels", [])) & {"legendary", "mythical", "ultra_beast", "paradox"}, sp
    for b, pool in ROSTER_PT["legendary_pool_by_band"].items():
        for sp in pool:
            labels = set(jar_species[B.key(sp)].get("labels", []))
            assert labels & {"legendary", "mythical", "ultra_beast", "paradox"}, sp
            assert b == "6" or "restricted" not in labels, (b, sp)


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_stands_on_the_test_trail_clear_of_the_old_mine_and_the_other_rips():
    import route1_old_mine as M
    f = RIP[PT["id"]]["frame"]
    assert f["x0"] > max(x for x, _z in M.TRAIL) + 4
    for x in range(f["x0"], f["x1"] + 1):
        assert M.rise(x, f["z"]) == 0 and M.rise(x, f["z"] + 1) == 0
    for d in DOC["dungeons"]:
        if d is not PT:
            o = RIP[d["id"]]["frame"]
            assert f["x1"] + 3 < o["x0"] or o["x1"] + 3 < f["x0"] or abs(f["z"] - o["z"]) > 3, d["id"]
    assert RIP[PT["id"]]["click"] == [(f["x0"] + f["x1"]) // 2, f["y"], f["z"] + 1]


def test_the_rip_stands_on_the_heightmaps_ground_and_above_the_sea():
    try:
        import ground as GR
        import terrain as T
        g = GR.load()
    except Exception as e:                                   # no heightmap on this machine
        pytest.skip("no canonical heightmap: %s" % e)
    f = RIP[PT["id"]]["frame"]
    sea = T.sea_level(g.world)
    for x in range(f["x0"], f["x1"] + 1):
        for z in (f["z"], f["z"] + 1, f["z"] + 2):
            assert round(g(x, z)) + 1 == f["y"] and g(x, z) > sea, (x, z, g(x, z))
    ox, oy, oz, _yaw = RIP[PT["id"]]["outside"]
    assert round(g(int(ox), int(oz))) + 1 == oy


# ------------------------------------------------------------------------------------------------- generator mutations


def test_mutating_the_glow_vines_off_leaves_rooms_dark_and_the_walk_check_says_so(monkeypatch):
    R._BUILT.clear()
    monkeypatch.setitem(R.DRESS, "glow_vines", (lambda ctx, spec: None, "light"))
    bad = R.walk_problems(DOC, PT, SLOT)
    R._BUILT.clear()
    assert any("no light" in p for p in bad), bad[:3]


def test_mutating_the_kit_so_rooms_never_touch_loses_the_shortcut_and_the_plan_check_says_so(monkeypatch):
    R._BUILT.clear()
    monkeypatch.setattr(R, "_touch", lambda far, near: None)
    bad = R.plan_problems(DOC, PT, SLOT)
    R._BUILT.clear()
    assert any("shortcut c1" in p and "does not touch" in p for p in bad), bad[:3]


def test_the_build_writes_one_shell_function_per_room_inside_the_chain_budget(pack):
    shell = [k for k in pack if "/shells/s%d/" % SLOT["g"] in k]
    assert len(shell) == len(R.layout(DOC, PT, SLOT))
    for s in SLOTS:
        assert R.chain_problems(DOC, PT, s) == []
