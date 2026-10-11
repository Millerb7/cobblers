"""The Overgrown Temple (`jungle`, dungeon 2 in data/dungeons.json), re-authored for pass 3 by unit DG3-JUNGLE on pass 2's
rooms (DG2-JUNGLE).

The author's own tests (the independent review is another agent's): the record builds and walks in all four variants
(the room kit's walk check, every door of every room, every route of both forks, the wing and the side room, the secrets
with their tricks), its MAIN route's required time is about 32 minutes at band 1 with every clock at most an hour (so no
lockout of its own), its rooms turn, climb, drop and double back with most of them shaped, it has every room type the
owner named. Pass 3 (DUNGEON_ROOMS.md 1b): two forks each through a crossroads that sees every way out, one of them
three ways, the routes asking different things (a fight, a fall, the long way; a puzzle, the dark); a four-room optional
WING (a connector, a climb, a hard parkour) ending in the PRIZE habitat (a rare non-legendary below the Beast Ball stage,
Zarude from it) with a balcony secret; a six-section main parkour; the treasury inside the vault budget. Also a cracked
and a balcony secret with their relics, a shortcut back toward the entry, four distinct variants and the lights-out set
piece before the boss, names only species in the Cobblemon 1.8.0 jar, and keeps its rip by the Night Shift's on dry
ground. Two GENERATOR mutations: the glow vines off leave rooms dark, and rooms that never touch lose the shortcut; the
walk and plan checks say so.

Not covered: anything in a running Minecraft, the fight and puzzle kinds' behaviour, the prize's roll and catch in game.
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
JG = next(d for d in DOC["dungeons"] if d["id"] == "jungle")
SLOTS = [s for s in D.slots(DOC) if s["dungeon"]["id"] == "jungle"]
SLOT = SLOTS[0]
RECORDS = list(R._walk_records(JG["rooms"]))     # every room of the record, routes and the side room (no swaps)
FIGHTS = {"stand", "gauntlet", "ambush", "nest", "miniboss", "habitat", "boss_arena"}
OWNER_NAMED = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
# the six optional kinds of DUNGEON_ROOMS.md 12-13 (PLACE-ROOMS, 2026-10-11): their side entries are not the pass-3 wing
# or the treasury the tests below are about
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}


def pass3_side(r):
    return r["kind"] == "side" and not any(x["kind"] in EXTRA_KINDS for x in r["rooms"])
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room", "setpiece"}
CONNECTORS = {"drift", "stairs"}


def kinds_in_order(rooms):
    return [r["kind"] for r in rooms]


@pytest.fixture(scope="module")
def walks():
    """{variant id: [walked rows]} over the slot of each variant (tools/dungeon_clock.py, the kit's own grids)."""
    out = {}
    for s in R.variant_slots(DOC, JG, SLOTS):
        out[R.variant_of(DOC, JG, s)["id"]] = DC.walked(DOC, JG, s)[0]
    return out


@pytest.fixture(scope="module")
def pack():
    """The generated pack, built once for the module (tools/dungeon.py build)."""
    return D.build(DOC)


# ------------------------------------------------------------------------------------------------- the record


def test_the_jungle_is_dungeon_two_a_test_dungeon_with_its_own_short_clock_and_no_lockout_of_its_own():
    ids = [d["id"] for d in DOC["dungeons"]]
    assert ids.index("jungle") == 1, ids
    assert JG["theme"] == "jungle" and JG["test"] is True and JG["test_why"]
    assert JG["gate_flag"] is None and "spine" not in JG
    assert JG["short"] not in [d["short"] for d in DOC["dungeons"] if d is not JG]
    assert set(JG["clock_s_by_band"]) == {str(b["band"]) for b in DOC["engine"]["bands"]}
    # every band's clock is at most an hour, so D17's hour lockout applies again (the brief: drop the dungeon's own)
    assert max(JG["clock_s_by_band"].values()) <= 3600
    assert "lockout_ticks" not in JG and "lockout_why" not in JG
    assert D.lockout_of(DOC, JG) == DOC["engine"]["lockout_ticks"]


def test_the_engine_and_the_room_kit_find_no_problem_with_it_in_any_variant():
    assert R.problems(DOC, JG) == []
    assert [p for p in D.problems(DOC) if "jungle" in p or "jg" in p.split()] == []
    for s in R.variant_slots(DOC, JG, SLOTS):
        assert R.walk_problems(DOC, JG, s) == [], R.variant_of(DOC, JG, s)["id"]
        assert SP.check_setpieces(DOC, R.resolve(DOC, JG, s), s) == []


def test_the_clock_is_about_32_minutes_required_at_band_one_and_the_authored_clock_covers_the_formula(walks):
    slack = DOC["engine"]["clock"]["slack_factor"]
    want = DC.derive(DOC, JG)
    own = JG["clock_s_by_band"]
    for b, s in want.items():
        assert s <= own[b] <= s + 120, (b, own[b], s)       # the formula, plus the set piece's allowance (clock_why)
    req1 = max(sum(DC.required(DOC, JG, 1, DC.clock_rooms(DOC, JG, 1, w)).values()) for w in walks.values())
    assert 30 * 60 <= req1 <= 34 * 60, req1 / 60
    assert 38 * 60 <= own["1"] <= 42 * 60 and abs(own["1"] - req1 * slack) <= 120
    assert DC.clock_problems(DOC, JG) == []
    assert DA.design_room_clocks()["jungle"] == [own[str(b)] // 60 for b in range(1, 7)]
    assert "setpiece" in JG["clock_why"] or "set piece" in JG["clock_why"]


def test_fewer_rooms_than_pass_one_on_the_way_wide_rooms_and_short_connectors(walks):
    for rows in walks.values():                              # pass 1 had 26 rooms; the way the clock pays (main, one route a fork)
        assert len(DC.clock_rooms(DOC, JG, 1, rows)) < 26
    for r in R.layout(DOC, JG, SLOT):
        if R.flags_of(r["kind"])["connector"]:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
        elif r["route"] == "main" and r["kind"] not in ("entry_room", "exit_room", "safe_room"):
            assert 24 <= r["width"] <= 62, (r["id"], r["width"])   # the undercroft, 24, runs under the colonnade
    assert max(r["height"] for r in RECORDS) >= 20, "a canopy hall"


def test_most_rooms_are_shaped_and_the_route_turns_climbs_drops_and_doubles_back():
    rooms = R.layout(DOC, JG, SLOT)
    shaped = [r for r in rooms if r["shape"] != "box"]
    can = [r for r in rooms if r["kind"] not in R.BOX_ONLY_KINDS | {"stairs", "entry_room", "exit_room", "vault", "puzzle"}]
    assert len(shaped) >= 0.8 * len(can) and len(shaped) > len(rooms) / 2, (len(shaped), len(can), len(rooms))
    assert len({r["shape"] for r in shaped}) >= 5
    sides = {d["side"] for r in rooms for d in r["doors"]}
    assert sides == {"north", "south", "east", "west"}
    assert any(r["doors"] and any(d["y"] > r["floor_in"] for d in r["doors"] if d["dir"] == "out") for r in rooms), "a landing"
    assert [r["id"] for r in rooms if r.get("dir") == "west"], "a stretch walked back west"
    floors = [r["floor_in"] for r in rooms]
    assert max(floors) - min(floors) >= 10, "climbs and drops"
    by = {r["id"]: r for r in rooms}
    # the undercroft is walked UNDER the colonnade: stacked rooms
    u, c = by["undercroft"], by["colonnade"]
    assert u["xa"] < c["xb"] and c["xa"] < u["xb"] and u["za"] < c["zb"] and c["za"] < u["zb"] and u["ceil_y"] < c["hull_lo"]


def test_every_room_type_the_owner_named_is_there_with_ours_the_heal_and_the_set_piece():
    kinds = {r["kind"] for r in RECORDS}
    assert OWNER_NAMED <= kinds, OWNER_NAMED - kinds
    assert len(kinds & OURS) >= 5, kinds & OURS
    assert any(r["kind"] == "safe_room" and r.get("params", {}).get("healer") for r in RECORDS)
    main = [r for r in JG["rooms"] if r["kind"] not in R.CONTAINERS]
    assert main[0]["kind"] == "entry_room" and kinds_in_order(main)[-2:] == ["boss_arena", "exit_room"]


def test_the_pacing_no_two_fights_meet_on_any_route_the_heal_about_two_thirds_in(walks):
    for s in R.variant_slots(DOC, JG, SLOTS):
        rooms = R.layout(DOC, JG, s)
        by_i = {r["i"]: r for r in rooms}
        for r in rooms:                                     # along every door out, on every route
            for d in r["doors"]:
                if d["dir"] == "out" and not d.get("shortcut"):
                    n = by_i[d["to"]]
                    assert not (r["kind"] in FIGHTS and n["kind"] in FIGHTS), (r["id"], n["id"])
    for vid, rows in walks.items():
        path = [r for r in DC.clock_rooms(DOC, JG, 1, rows)]
        order = {r["id"]: k for k, r in enumerate(rows)}
        path.sort(key=lambda r: order[r["id"]])
        total = sum(r["walk"] for r in path)
        before = 0
        for r in path:
            if r["kind"] == "safe_room":
                break
            before += r["walk"]
        assert 0.6 <= before / total <= 0.8, (vid, before / total)
    ids = [r["id"] for r in JG["rooms"]]
    kinds = [r["kind"] for r in JG["rooms"]]
    wing = next(k for k, r in enumerate(JG["rooms"]) if pass3_side(r) and len(r["rooms"]) > 1)
    assert kinds.index("resources") < min([kinds.index(k) for k in ("miniboss", "boss_arena")] + [wing])
    assert ids.index("shrine") == wing - 1, "the wing leaves the shrine: healed before the hard parkour and the prize"


def test_the_temple_is_dressed_stone_and_the_jungle_dense(walks):
    by = {b.room["id"]: b for b in R.slot_build(DOC, JG, SLOT)}
    names = lambda b: {op[2].split("[")[0] for op in b.ops if op[0] in ("fill", "set")}  # noqa: E731
    for rid in ("colonnade", "sanctum", "altar"):
        assert {"minecraft:mossy_stone_bricks", "minecraft:chiseled_stone_bricks"} & names(by[rid]), rid
    logs = [r["id"] for r in R.layout(DOC, JG, SLOT) if r["kind"] == "drift" and "minecraft:jungle_log" in names(by[r["id"]])]
    assert len(logs) >= 4, logs
    assert "minecraft:cave_vines" in names(by["sanctum"]), "the canopy hall is lit by glow berries"


# ------------------------------------------------------------------------------------------------- replayability


def route_walk(rows, fork, route):
    return sum(r["walk"] for r in rows if r["route"] == "%s/%s" % (fork, route))


def route_kinds(route):
    return {r["kind"] for r in route["rooms"]}


def test_two_forks_each_through_a_crossroads_that_sees_every_way_one_of_them_three_ways(walks):
    top = JG["rooms"]
    forks = [(k, r) for k, r in enumerate(top) if r["kind"] == "fork"]
    assert len(forks) == 2
    assert sorted(len(f["routes"]) for _k, f in forks) == [2, 3]
    looks = set((DOC_THEMES()["jungle"].get("crossroads") or {}).get("looks") or {})
    for k, f in forks:
        host = top[k - 1]
        assert host["kind"] == "crossroads", host["id"]
        lk = [rt["look"] for rt in f["routes"]]
        assert len(set(lk)) == len(lk) and set(lk) <= looks, lk
        assert all(rt.get("sign") for rt in f["routes"]), "every way out of a crossroads is signed"
        assert not any(rt.get("optional") for rt in f["routes"]), "both forks are the way on; the wing is the optional part"
    for s in R.variant_slots(DOC, JG, SLOTS):                  # each exit on its own wall, the hub anchor built
        rooms = R.layout(DOC, JG, s)
        built = {b.room["id"]: b for b in R.slot_build(DOC, JG, s)}
        for k, f in forks:
            host = next(r for r in rooms if r["id"] == top[k - 1]["id"])
            outs = [d["side"] for d in host["doors"] if d["dir"] == "out"]
            assert len(outs) == len(f["routes"]) == len(set(outs)), outs
            assert built[host["id"]].anchors.get("hub")
            join = next(r for r in rooms if r["id"] == top[k + 1]["id"])
            assert len([d for d in join["doors"] if d["dir"] == "in"]) == len(f["routes"]), "every way rejoins"


def DOC_THEMES():
    return json.loads((ROOT / "data" / "dungeon_themes.json").read_text(encoding="utf-8"))["themes"]


def test_the_routes_ask_different_things_and_the_clock_pays_the_slower(walks):
    gorge = next(r for r in JG["rooms"] if r["id"] == "gorge")
    by = {rt["id"]: rt for rt in gorge["routes"]}
    assert set(by) == {"poachers", "bridge", "gorge_floor"}
    assert route_kinds(by["poachers"]) & {"stand", "gauntlet"}, "the poachers' trail is a fight"
    assert "collapse_bridge" in route_kinds(by["bridge"]), "the bridge can drop the walker (a fall costs the clock)"
    assert not route_kinds(by["gorge_floor"]) & {"collapse_bridge", "parkour", "stand", "gauntlet", "ambush", "nest"}
    court = next(r for r in JG["rooms"] if r["id"] == "court_fork")
    cb = {rt["id"]: rt for rt in court["routes"]}
    assert "puzzle" in route_kinds(cb["glyph"]) and "dark_room" in route_kinds(cb["roots"])
    assert "puzzle" not in route_kinds(cb["roots"])
    for vid, rows in walks.items():
        # the safe way is the long way; the dark way round the glyph door is longer than the door
        assert route_walk(rows, "gorge", "gorge_floor") > route_walk(rows, "gorge", "bridge"), vid
        assert route_walk(rows, "court_fork", "roots") > route_walk(rows, "court_fork", "glyph"), vid
        for b in range(1, 7):
            paid = {r["route"] for r in DC.clock_rooms(DOC, JG, b, rows) if r["route"] != "main"}
            assert paid == {"gorge/poachers", "court_fork/glyph"}, (vid, b, paid)


def wing():
    (w,) = [r for r in JG["rooms"] if pass3_side(r) and len(r["rooms"]) > 1]
    return w


def test_a_four_room_optional_wing_a_connector_a_climb_a_hard_parkour_and_the_prize_at_its_end(walks):
    w = wing()
    kinds = [r["kind"] for r in w["rooms"]]
    assert 3 <= len(kinds) <= 4 and R.flags_of(kinds[0])["connector"] and kinds[-1] == "habitat"
    (pk,) = [r for r in w["rooms"] if r["kind"] == "parkour"]
    assert pk["params"]["hard"] is True and pk["params"]["sections"] >= 5
    end = w["rooms"][-1]
    assert end["params"].get("prize") and end.get("gate", "open") == "open"
    assert [s["type"] for s in end.get("secrets", [])] == ["balcony"] and end["params"].get("relic")
    ids = {r["id"] for r in w["rooms"]}
    for s in R.variant_slots(DOC, JG, SLOTS):
        rooms = R.layout(DOC, JG, s)
        by = {r["id"]: r for r in rooms}
        assert all(by[i]["route"] == w["id"] for i in ids)
        assert not [d for d in by[end["id"]]["doors"] if d["dir"] == "out"], "a dead end"
        # it climbs over the temple: the hard parkour and the prize hall stand above main-route rooms
        lo = by[pk["id"]]["hull_lo"]
        under = [r["id"] for r in rooms if r["route"] == "main" and r["ceil_y"] < lo
                 and r["xa"] <= by[pk["id"]]["xb"] and by[pk["id"]]["xa"] <= r["xb"]
                 and r["za"] <= by[pk["id"]]["zb"] and by[pk["id"]]["za"] <= r["zb"]]
        assert under, "the wing's parkour runs over the main route"
    for rows in walks.values():
        for b in range(1, 7):
            assert not ids & {r["id"] for r in DC.clock_rooms(DOC, JG, b, rows)}, "the clock never counts the wing"


def test_one_side_room_the_treasury_a_dead_end_the_clock_does_not_count(walks):
    sides = [r for r in JG["rooms"] if pass3_side(r) and len(r["rooms"]) == 1]
    assert len(sides) == 1 and sides[0]["rooms"][0]["kind"] == "vault"
    side_ids = {r["id"] for r in sides[0]["rooms"]}
    rooms = R.layout(DOC, JG, SLOT)
    for r in rooms:
        if r["id"] in side_ids:
            assert r["route"] == sides[0]["id"]
    last = next(r for r in rooms if r["id"] == sides[0]["rooms"][-1]["id"])
    assert not [d for d in last["doors"] if d["dir"] == "out"]
    for rows in walks.values():
        assert not side_ids & {r["id"] for r in DC.clock_rooms(DOC, JG, 1, rows)}


def test_two_parkours_a_six_section_main_one_and_a_hard_one_in_the_wing():
    pks = {r["id"]: r for r in RECORDS if r["kind"] == "parkour"}
    assert len(pks) == 2
    main = [r for r in JG["rooms"] if r["kind"] == "parkour"]
    assert len(main) == 1 and main[0]["params"]["sections"] == 6 and main[0]["width"] == 25
    assert main[0]["length"] >= 30 * 6 - 10 + 2 and not main[0]["params"].get("hard")
    (hard,) = [r for r in pks.values() if r["params"].get("hard")]
    assert hard["width"] == 25 and hard["length"] >= 30 * hard["params"]["sections"] - 10 + 2
    for s in R.variant_slots(DOC, JG, SLOTS):                  # PARKOUR2 planned every section, the easy fork on the main one only
        built = {b.room["id"]: b for b in R.slot_build(DOC, JG, s)}
        for rid, r in pks.items():
            m = built[rid].meta
            assert len(m["ledges"]) == r["params"]["sections"] + 1, (rid, s["k"])
            assert (m["fork"] is None) == bool(r["params"].get("hard")), (rid, m["fork"])


def test_the_prize_is_rare_before_the_beast_ball_stage_and_zarude_from_it_spawned_only_when_rolled(pack):
    import dungeon_prize as PZ
    end = wing()["rooms"][-1]
    pz = end["params"]["prize"]
    lf = DOC["engine"]["prize"]["legendary_from_band"]
    assert set(pz["rare_by_band"]) == {str(b) for b in range(1, lf)}
    assert set(pz["legendary_by_band"]) == {str(b) for b in range(lf, 7)} and set(pz["legendary_by_band"].values()) == {"zarude"}
    assert PZ.room_problems(DOC, JG, end) == []
    assert "species" not in end["params"], "Zarude is the prize now, not a resident every run"
    files = pack
    for s in SLOTS:
        base = R.room_fn(JG, end, s, "")
        rel = lambda name: "data/%s/function/%s.mcfunction" % (R.NS, (base + name).split(":", 1)[1])  # noqa: E731
        enter = files[rel("enter")]
        for b in range(1, 7):
            assert "dg.rs matches 1 if score @s dg.band matches %d run function %sprize/spawn_b%d" % (b, base, b) in enter
            sp = files[rel("prize/spawn_b%d" % b)]
            assert any(ln.endswith("prize/bind" if b >= lf else "prize/rare_bind") for ln in sp.split("\n")), (s["g"], b)
        assert "random value 1..100" in "".join(v for k, v in files.items() if k.endswith("/slot/s%d/start.mcfunction" % s["g"]))


def test_the_treasury_pays_no_more_than_the_runs_time_gathering():
    import dungeon_greed as DG
    over = [x for x in DG.vault_over(DOC) if x[0] == "jungle"]
    assert over == [], over
    budget = DG.vault_budget(DOC, dungeon=JG)     # its own clock's (MEGA-INTEGRATE)
    (vault,) = [r for r in RECORDS if r["kind"] == "vault"]
    n = vault["params"]["chests"]
    tbl = DG.load()
    for b, spec in vault["params"]["loot_by_band"].items():
        assert DG.chest_cp(tbl, spec) <= 0.95 * budget[int(b)] // n, (b, DG.chest_cp(tbl, spec), budget[int(b)] // n)


def test_two_secrets_one_cracked_one_balcony_each_room_carrying_a_unique_relic_and_short_lore():
    secret_rooms = [r for r in RECORDS if r.get("secrets")]
    types = sorted(s["type"] for r in secret_rooms for s in r["secrets"])
    assert types == ["balcony", "cracked"], types
    relics = []
    for r in secret_rooms:
        assert len(r["secrets"]) == 1, r["id"]               # one secret per room: the relic is the room's param
        p = r["params"]
        assert re.fullmatch(r"[a-z0-9_]+", p["relic"]) and p["relic"].startswith("jg_")
        assert 0 < len(p["lore"]) <= 160 and p["lore"].isascii() and p["lore"].isprintable()
        assert 1 <= p["lore"].count(".") + p["lore"].count("!") + p["lore"].count("?") <= 3
        assert len(p.get("relic_name", "")) <= 32
        relics.append(p["relic"])
    assert len(relics) == len(set(relics)) == 2
    assert not [r["id"] for r in RECORDS if r.get("params", {}).get("relic") and not r.get("secrets")]
    for s in R.variant_slots(DOC, JG, SLOTS):                 # built in every variant, with its relic spot
        built = {b.room["id"]: b for b in R.slot_build(DOC, JG, s)}
        for r in secret_rooms:
            meta = built[r["id"]].meta["secrets"]
            assert len(meta) == 1 and built[r["id"]].anchors.get("secret"), (r["id"], s["k"])


def test_a_shortcut_back_toward_the_entry_opened_from_the_far_side_only(pack):
    scs = [(r["id"], sc) for r in RECORDS for sc in r.get("shortcuts") or []]
    assert len(scs) == 1
    far_id, sc = scs[0]
    for s in R.variant_slots(DOC, JG, SLOTS):
        rooms = {r["id"]: r for r in R.layout(DOC, JG, s)}
        far, near = rooms[far_id], rooms[sc["to"]]
        assert near["i"] < far["i"] and not far.get("layout_errors")
        assert [d for d in far.get("shortcut_doors", []) if d["dir"] == "out"]
        assert [d for d in near.get("shortcut_doors", []) if d["dir"] == "in"]
    files = pack
    assert any(k.endswith("/room/jungle/%s/s%d/shortcut_%s.mcfunction" % (far_id, SLOT["g"], sc["id"])) for k in files)


def test_four_distinct_variants_one_per_slot_using_mirror_seed_and_swap():
    vs = JG["variants"]
    assert len(vs) == 4 and len({v["id"] for v in vs}) == 4
    assert [R.variant_of(DOC, JG, s)["id"] for s in SLOTS] == [v["id"] for v in vs]
    assert any(v.get("mirror") for v in vs) and any(v.get("seed") for v in vs) and any(v.get("swap") for v in vs)
    assert len({json.dumps({k: v[k] for k in v if k != "id"}, sort_keys=True) for v in vs}) == 4
    shapes = []
    for s in SLOTS:
        rooms = R.layout(DOC, JG, s)
        built = R.slot_build(DOC, JG, s)
        shapes.append(tuple((r["id"], r["za"] - s["z0"], r["kind"], len(b.ops)) for r, b in zip(rooms, built)))
        assert rooms[0]["kind"] == "entry_room" and rooms[-1]["kind"] == "exit_room"
    assert len(set(shapes)) == 4, "each slot lays its rooms differently"


def test_the_set_piece_is_the_lights_out_the_climax_before_the_boss():
    main = [r for r in JG["rooms"] if r["kind"] not in R.CONTAINERS]
    sp = [r for r in RECORDS if r["kind"] == "setpiece"]
    assert len(sp) == 1 and sp[0]["params"]["piece"] == "lights_out" and sp[0]["params"]["pit"] == 0
    assert main[-3]["kind"] == "setpiece" and main[-2]["kind"] == "boss_arena"


# ------------------------------------------------------------------------------------------------- the params contract


def rooms_of(*kinds):
    return [r for r in RECORDS if r["kind"] in kinds]


def test_the_stands_and_the_ambushes_follow_the_members_by_band_and_the_triggers_are_one_per_trainer():
    for s in R.variant_slots(DOC, JG, SLOTS):
        for r in R._walk_records(R.resolve(DOC, JG, s)["rooms"]):
            if r["kind"] in ("stand", "gauntlet", "ambush"):
                assert r["gate"] == "cleared"
                assert DF.stand_problems(DOC, r) == [], r["id"]
            if r["kind"] in ("gauntlet", "ambush"):
                tr = r["params"]["triggers"]
                assert len(tr) == len(r["params"]["trainers"]) and tr == sorted(tr) and 0 < tr[0] and tr[-1] < 1


def test_the_wild_rooms_carry_the_contracts_fields_within_the_band_caps():
    bands = {str(b["band"]): b for b in D.bands(DOC)}
    for r in rooms_of("nest"):
        p = r["params"]
        assert p["species"] and set(p["count_by_band"]) == set(bands) and r["gate"] == "cleared"
        lo, hi = p["level_spread"]
        assert 0 <= lo <= hi
    for r in rooms_of("miniboss"):
        p = r["params"]
        assert set(p["species_by_band"]) == set(bands) and p["level_offset"] <= 0 and p.get("catchable", True) is True   # the owner, 2026-10-10: every dungeon Pokemon catchable
    for r in rooms_of("habitat"):
        p = r["params"]
        assert r.get("gate", "open") == "open", "the prize is optional: the slack pays for it (clock_why)"
        assert p.get("prize") and not DF.is_wild_room(r), "a prize habitat with no resident (pass 3)"
    for r in rooms_of("puzzle"):
        p = r["params"]
        assert p["variant"] in ("levers", "sequence", "plates") and p["penalty_s"] > 0 and r["gate"] == "cleared"
    for r in rooms_of("vault"):
        p = r["params"]
        assert r.get("gate", "open") == "open" and 1 <= p["chests"] <= 8 and p["clock_cost_s"] > 0
        assert set(p["loot_by_band"]) == set(bands) and r["length"] >= 4 * p["chests"] + 12
    for r in rooms_of("safe_room"):
        assert r["params"]["healer"] is True


def test_the_boss_has_a_crew_per_stage_per_band_the_ace_last_and_the_same_ace_in_every_stage():
    bo = JG["boss"]
    assert bo["name"] != DOC["dungeons"][0]["boss"]["name"]
    for b in D.bands(DOC):
        crews = bo["teams"][str(b["band"])]
        assert len(crews) == len(bo["stage_level_offsets"])
        assert len({c[-1] for c in crews}) == 1
        assert all(1 <= len(c) <= 6 for c in crews)


# ------------------------------------------------------------------------------------------------- species


def all_species():
    out = set()
    for r in RECORDS:
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for team in t["team_by_band"].values():
                out |= set(team)
        out |= set(p.get("species", [])) if isinstance(p.get("species"), list) else ({p["species"]} if "species" in p else set())
        out |= set(p.get("species_by_band", {}).values())
        for key in ("rare_by_band", "legendary_by_band"):
            out |= set((p.get("prize") or {}).get(key, {}).values())
    for crews in JG["boss"]["teams"].values():
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


def test_every_species_is_in_the_cobblemon_jar(jar_species):
    import battle_sim as B
    assert sorted(s for s in all_species() if B.key(s) not in jar_species) == []


def data_users(sp):
    return sorted(p.name for p in (ROOT / "data").rglob("*.json")
                  if p.name != "dungeons.json" and re.search(r"\b%s\b" % sp, p.read_text(encoding="utf-8"), re.I))


def test_the_prize_is_a_mythical_no_other_data_file_uses_and_before_it_a_rare_that_is_no_set_piece(jar_species):
    import battle_sim as B
    (hab,) = rooms_of("habitat")
    pz = hab["params"]["prize"]
    for sp in set(pz["legendary_by_band"].values()):
        labels = set(jar_species[B.key(sp)].get("labels", []))
        # no Ultra Beast yet: KIT3 found key_ball's x5 would stack on the Beast Ball's own x5
        assert labels & {"legendary", "mythical"} and "ultra_beast" not in labels, labels
        assert data_users(sp) == []
    for sp in set(pz["rare_by_band"].values()):
        labels = set(jar_species[B.key(sp)].get("labels", []))
        assert not labels & {"legendary", "mythical", "ultra_beast"}, labels
        # Hakamo-o: wild only (the Long Isle's jungle, tier 8, rare; Jangmo-o its find), never a scene, gift or trainer
        assert set(data_users(sp)) <= {"spawns.json", "encounter_design.json"}, data_users(sp)


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_stands_by_the_night_shifts_on_the_trail_clear_of_the_old_mine_and_the_other_rips():
    import route1_old_mine as M
    f = JG["rip"]["frame"]
    ns = DOC["dungeons"][0]["rip"]["frame"]
    cx, cz = (f["x0"] + f["x1"]) / 2, f["z"]
    assert ((cx - (ns["x0"] + ns["x1"]) / 2) ** 2 + (cz - ns["z"]) ** 2) ** 0.5 <= 60
    assert f["x0"] > max(M.TRAIL[-1][0], max(x for x, _z in M.TRAIL)) + 4, "east of the old mine's footprint"
    for x in range(f["x0"], f["x1"] + 1):
        assert M.rise(x, f["z"]) == 0 and M.rise(x, f["z"] + 1) == 0
    for d in DOC["dungeons"]:
        if d is JG:
            continue
        o = d["rip"]["frame"]
        assert f["x1"] + 3 < o["x0"] or o["x1"] + 3 < f["x0"] or abs(f["z"] - o["z"]) > 3, d["id"]
    assert JG["rip"]["click"] == [cx, f["y"], f["z"] + 1]


def test_the_rip_stands_on_the_heightmaps_ground_and_above_the_sea():
    try:
        import ground as GR
        import terrain as T
        g = GR.load()
    except Exception as e:                                   # no heightmap on this machine
        pytest.skip("no canonical heightmap: %s" % e)
    f = JG["rip"]["frame"]
    sea = T.sea_level(g.world)
    for x in range(f["x0"], f["x1"] + 1):
        for z in (f["z"], f["z"] + 1):
            assert g(x, z) + 1 == f["y"] and g(x, z) > sea, (x, z, g(x, z))
    ox, oy, oz, _yaw = JG["rip"]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy


# ------------------------------------------------------------------------------------------------- generator mutations


def test_mutating_the_glow_vines_off_leaves_rooms_dark_and_the_walk_check_says_so(monkeypatch):
    R._BUILT.clear()
    monkeypatch.setitem(R.DRESS, "glow_vines", (lambda ctx, spec: None, "light"))
    bad = R.walk_problems(DOC, JG, SLOT)
    R._BUILT.clear()
    assert any("no light" in p for p in bad), bad[:3]


def test_mutating_the_kit_so_rooms_never_touch_loses_the_shortcut_and_the_plan_check_says_so(monkeypatch):
    R._BUILT.clear()
    monkeypatch.setattr(R, "_touch", lambda far, near: None)
    bad = R.plan_problems(DOC, JG, SLOT)
    R._BUILT.clear()
    assert any("shortcut c1" in p and "does not touch" in p for p in bad), bad[:3]


def test_the_build_writes_one_shell_function_per_room_inside_the_chain_budget(pack):
    files = pack
    shell = [k for k in files if "/shells/s%d/" % SLOT["g"] in k]
    assert len(shell) == len(R.layout(DOC, JG, SLOT))
    for s in SLOTS:
        assert R.chain_problems(DOC, JG, s) == []
    assert R.total_blocks(DOC, SLOT) < 1.2e6


def test_the_new_rooms_are_placed_off_the_route_and_every_one_is_optional():
    """PLACE-ROOMS (2026-10-11, the owner: "I want to see the new rooms"): the jungle holds a fishing room, a wishing well
    and a bait room, each on a side entry (never the main route, never a fork route), gate open, never paid by the
    clock, in every variant; the bait's lure room is a living room on the main route."""
    new = {"fishing_room", "wishing_well", "bait_room"}
    for s in SLOTS:
        lay = R.layout(DOC, JG, s)
        mine = [r for r in lay if r["kind"] in new]
        assert sorted(r["kind"] for r in mine) == sorted(new), s["g"]
        for r in mine:
            assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open", (s["g"], r["id"])
        bait = next(r for r in mine if r["kind"] == "bait_room")
        lure = next(r for r in lay if r["id"] == bait["params"]["lure_room"])
        assert lure["route"] == "main" and lure["kind"] not in FIGHTS | {"parkour"}, lure["id"]
    rooms = DC.walked(DOC, JG)[0]
    paid = {r["id"] for b in DOC["engine"]["bands"] for r in DC.clock_rooms(DOC, JG, b["band"], rooms)}
    assert not paid & {r["id"] for r in rooms if r["kind"] in new}, "the clock never pays for an optional room"
