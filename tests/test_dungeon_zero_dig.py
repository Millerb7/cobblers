"""The Zero Dig (data/dungeons.json `zero_dig`): a full-length test dungeon in the desert_excavation theme, authored to
the prize roster (data/dungeon_prize_roster.json `zero_dig`, unit COVERAGE) by unit NEW-ZERODIG, 2026-10-11.

The author's own tests (the independent audit, tools/dungeon_independent_audit.py, is another agent's). What they hold
the record to, from the owner's standing asks for every dungeon (docs/mechanics/DUNGEON_PASS2.md):

  shape     every room type the owner named (maze, puzzle, parkour, resources, nest, habitat, stand, mini-boss) and at
            least three of the six optional rooms (DUNGEON_ROOMS.md 12-13), each on a side entry with its gate open;
  choices   two forks out of crossroads with a distinct look per route, one of them three ways; an optional WING (never
            paid by the clock) with a hard parkour and the prize habitat; two parkours (the main one six sections on a
            route the clock pays); the set piece the room before the boss; the safe room with a healer and a shortcut back
            toward the entry; three secrets each with a relic; four distinct variants;
  length    tools/dungeon_clock.py's required time about 32 minutes at band 1; the record's clock the tool's plus the set
            piece's 25 s x the slack, except band 4, held at the shortest other dungeon's so this one never lowers the
            shared vault and resource budgets; every band under an hour and no lockout of its own;
  variety   every trainer a rotation pool of two teams a band, the mini-boss a species pool, the boss an alternate crew
            per band; two boss stages with a full heal between;
  prize     the roster's pools, legendary bands 4-6 only and no rare band; the single forms are pool members that are not
            model-gated; the boss holds no legendary, mythical, Ultra Beast or paradox;
  species   every species named, in every variant, is in the Cobblemon 1.8.0 jar (skipped without it);
  walk      the room kit's own checks on every variant and branch;
  rip       on the heightmap's ground (skipped without it), dry, at the x slot it was given, clear of the other rips.

Not covered: anything in a running Minecraft.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_clock as C  # noqa: E402
import dungeon_rooms as R  # noqa: E402

DOC = D.load()
ZD = next(d for d in DOC["dungeons"] if d["id"] == "zero_dig")
SETPIECE_ALLOWANCE_S = 25
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
FIGHTS = {"stand", "gauntlet", "ambush", "miniboss", "nest", "habitat", "boss_arena"}


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def slots():
    return [s for s in D.slots(DOC) if s["dungeon"]["id"] == "zero_dig"]


def records(d=ZD):
    return list(R._walk_records(d["rooms"]))


def by_id(rid):
    return next(r for r in records() if r["id"] == rid)


def forks():
    return [r for r in ZD["rooms"] if r["kind"] == "fork"]


def variant_records():
    out = []
    for s in R.variant_slots(DOC, ZD, slots()):
        out += records(R.resolve(DOC, ZD, s))
    return out


# ------------------------------------------------------------------------------------------------- shape and choices


def test_every_room_type_the_owner_named_and_three_optional_rooms_each_off_the_route():
    kinds = {r["kind"] for r in records()}
    assert {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"} <= kinds
    sides = [r for r in ZD["rooms"] if r["kind"] == "side"]
    extra = [x for s in sides for x in s["rooms"] if x["kind"] in EXTRA_KINDS]
    assert len({x["kind"] for x in extra}) >= 3, [x["kind"] for x in extra]
    for x in extra:
        assert x.get("gate", "open") == "open", x["id"]
    on_route = [r["id"] for r in ZD["rooms"] if r["kind"] in EXTRA_KINDS]
    on_route += [x["id"] for f in forks() for rt in f["routes"] for x in rt["rooms"] if x["kind"] in EXTRA_KINDS]
    assert not on_route, on_route


def test_two_forks_out_of_crossroads_one_three_ways_each_route_its_own_look():
    top = ZD["rooms"]
    fs = forks()
    assert len(fs) >= 2
    for f in fs:
        i = top.index(f)
        assert top[i - 1]["kind"] == "crossroads", f["id"]
        looks = [rt["look"] for rt in f["routes"]]
        assert len(set(looks)) == len(looks), looks
        assert any(not rt.get("optional") for rt in f["routes"])
    assert max(len(f["routes"]) for f in fs) == 3


def test_the_wing_is_optional_with_a_hard_parkour_and_the_prize_habitat_never_paid_by_the_clock():
    wing = [rt for f in forks() for rt in f["routes"] if rt.get("optional")]
    assert len(wing) == 1
    ks = [x["kind"] for x in wing[0]["rooms"]]
    assert "habitat" in ks and "parkour" in ks and len(ks) >= 3
    hard = [x for x in wing[0]["rooms"] if x["kind"] == "parkour"]
    assert hard and all(x["params"].get("hard") for x in hard)
    hab = next(x for x in wing[0]["rooms"] if x["kind"] == "habitat")
    assert "prize" in hab["params"] and hab.get("gate", "open") == "open"
    rooms, _t = C.walked(DOC, ZD)
    paid = {r["id"] for r in C.clock_rooms(DOC, ZD, 1, rooms)}
    assert not paid & {x["id"] for x in wing[0]["rooms"]}


def test_two_parkours_the_main_one_six_sections_on_a_paid_route():
    pk = [r for r in records() if r["kind"] == "parkour"]
    assert len(pk) >= 2
    main = [r for r in pk if not r["params"].get("hard")]
    assert main and main[0]["params"]["sections"] == 6
    rooms, _t = C.walked(DOC, ZD)
    assert main[0]["id"] in {r["id"] for r in C.clock_rooms(DOC, ZD, 1, rooms)}


def test_the_set_piece_is_the_room_before_the_boss_and_the_safe_room_heals_with_a_shortcut_back():
    main = [r for r in ZD["rooms"] if r["kind"] not in ("fork", "side")]
    ks = [r["kind"] for r in main]
    i = ks.index("boss_arena")
    assert ks[i - 1] == "setpiece" and main[i - 1]["params"]["piece"] in ("collapse", "flood", "lights_out")
    safe = [r for r in main if r["kind"] == "safe_room"]
    assert safe and safe[0]["params"].get("healer") is True
    ids = [r["id"] for r in main]
    for sc in safe[0].get("shortcuts", []):
        assert ids.index(sc["to"]) < ids.index(safe[0]["id"])
    assert safe[0].get("shortcuts")


def test_three_secrets_each_with_its_relic_and_lore():
    sec = [r for r in records() if r.get("secrets")]
    assert len(sec) >= 3
    assert {s["type"] for r in sec for s in r["secrets"]} == {"cracked", "balcony"}
    relics = [r["params"]["relic"] for r in sec]
    assert len(set(relics)) == len(relics) and all(x.startswith("zd_") for x in relics)
    for r in sec:
        assert 0 < len(r["params"]["lore"]) <= 160


def test_four_distinct_variants_one_per_slot():
    vs = ZD["variants"]
    assert len(vs) == 4 == len(slots())
    keys = {(bool(v.get("mirror")), v.get("seed"), str(v.get("swap")), str(v.get("order"))) for v in vs}
    assert len(keys) == 4


def test_no_two_fight_rooms_back_to_back_on_the_main_route():
    main = [r for r in R.layout(DOC, ZD, slots()[0]) if r["route"] == "main"]
    for a, b in zip(main, main[1:]):
        assert not (a["kind"] in FIGHTS and b["kind"] in FIGHTS and a["kind"] != "nest" and b["kind"] != "nest"), (a["id"], b["id"])


# ------------------------------------------------------------------------------------------------- length


def _required_by_band():
    out = {}
    sl = slots()
    walks = [C.walked(DOC, ZD, s)[0] for s in R.variant_slots(DOC, ZD, sl)]
    for b in DOC["engine"]["bands"]:
        out[b["band"]] = max(sum(C.required(DOC, ZD, b["band"], C.clock_rooms(DOC, ZD, b["band"], w)).values()) for w in walks)
    return out


def test_about_32_minutes_required_at_band_1_and_the_clock_is_the_tools_plus_the_set_piece_allowance():
    req = _required_by_band()
    assert 30 * 60 <= req[1] <= 34 * 60, req[1] / 60
    slack = DOC["engine"]["clock"]["slack_factor"]
    own = ZD["clock_s_by_band"]
    others = [d for d in DOC["dungeons"] if d["id"] != "zero_dig" and d.get("clock_s_by_band")]
    for b, s in req.items():
        want = math.ceil((s + SETPIECE_ALLOWANCE_S) * slack / 60) * 60
        if b == 4:
            # held so this dungeon is never the shortest at band 4 (the vault and resource budgets price the shortest)
            want = max(want, min(int(d["clock_s_by_band"]["4"]) for d in others))
        assert own[str(b)] == want, (b, own[str(b)], want)
        assert own[str(b)] <= 3600
    assert "lockout_ticks" not in ZD
    assert C.clock_problems(DOC, ZD) == []


# ------------------------------------------------------------------------------------------------- variety and prize


def test_every_trainer_rotates_two_teams_the_miniboss_a_pool_the_boss_an_alternate_and_heals_between_stages():
    trainers = [t for r in records() if r["kind"] in ("stand", "gauntlet", "ambush") for t in r["params"]["trainers"]]
    assert len(trainers) >= 4
    for t in trainers:
        assert "team_by_band" not in t
        for b in map(str, range(1, 7)):
            assert len(t["team_pool_by_band"][b]) >= 2, (t["name"], b)
    mb = [r for r in records() if r["kind"] == "miniboss"]
    assert mb and all(len(v) >= 2 for r in mb for v in r["params"]["species_pool_by_band"].values())
    boss = ZD["boss"]
    assert boss["heal_between_stages"] is True
    for b in map(str, range(1, 7)):
        assert len(boss["teams"][b]) == 2
        assert all(len(alt) == 2 for alt in boss["teams_alt_by_band"][b])


def test_the_prize_is_the_rosters_legendary_pool_from_band_4_only():
    import json
    roster = json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))
    entry = next(e for e in roster["dungeons"] if e["id"] == "zero_dig")
    hab = [r for r in records() if r["kind"] == "habitat"]
    assert len(hab) == 1
    pz = hab[0]["params"]["prize"]
    assert pz["roster"] == "zero_dig" and "rare_by_band" not in pz and not entry["rare_pool_by_band"]
    assert set(pz["legendary_by_band"]) == {"4", "5", "6"}
    gated = {k for k, v in roster["species"].items() if v.get("model_gate")}
    for b, sp in pz["legendary_by_band"].items():
        assert sp in entry["legendary_pool_by_band"][b] and sp not in gated, (b, sp)
    assert len(pz.get("rumour", "")) <= 120


@pytest.fixture(scope="module")
def jar():
    import battle_sim as B
    try:
        j = B.find_jar()
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar")
    sp, _m, _c = B.load_pack(j)
    return sp, B.key


def named_species():
    out = []
    for r in variant_records():
        p = r.get("params") or {}
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for teams in t["team_pool_by_band"].values():
                out += [(r["id"], x) for team in teams for x in team]
        out += [(r["id"], x) for x in p.get("species", []) if r["kind"] == "nest"]
        out += [(r["id"], x) for v in p.get("species_pool_by_band", {}).values() for x in v]
        out += [(r["id"], x) for x in (p.get("prize") or {}).get("legendary_by_band", {}).values()]
    for crews in ZD["boss"]["teams"].values():
        out += [("boss", x) for crew in crews for x in crew]
    for alts in ZD["boss"]["teams_alt_by_band"].values():
        out += [("boss", x) for alt in alts for crew in alt for x in crew]
    return out


def test_every_species_named_is_in_the_jar_and_the_boss_holds_no_legendary(jar):
    sp, key = jar
    names = named_species()
    missing = sorted({x for _r, x in names if key(x) not in sp})
    assert not missing, missing
    special = {"legendary", "mythical", "ultra_beast", "paradox"}
    bad = sorted({x for r, x in names if r != "zero_point" and special & set(sp[key(x)].get("labels", []))})
    assert not bad, bad


# ------------------------------------------------------------------------------------------------- walk and rip


def test_the_zero_dig_builds_and_walks_with_no_problem_in_every_variant_and_branch():
    assert R.problems(DOC, ZD) == []


def test_the_rip_is_at_its_slot_clear_of_the_other_rips():
    f = ZD["rip"]["frame"]
    assert 1640 <= (f["x0"] + f["x1"]) / 2 <= 1660 and ZD["rip"]["test"] is True
    for d in DOC["dungeons"]:
        if d["id"] == "zero_dig":
            continue
        o = d["rip"]["frame"]
        assert f["x0"] > o["x1"] + 4 or f["x1"] < o["x0"] - 4 or abs(f["z"] - o["z"]) > 6, d["id"]
    cx, cy, cz = ZD["rip"]["click"]
    assert cz == f["z"] + 1 and cy == f["y"] and cx == (f["x0"] + f["x1"]) // 2


def test_the_rip_is_on_the_heightmaps_ground_and_not_in_water():
    try:
        import ground as GR
        g = GR.load()
    except Exception as e:  # noqa: BLE001  (no heightmap in this checkout)
        pytest.skip("no heightmap: %s" % e)
    import json
    f = ZD["rip"]["frame"]
    feet = {round(g(x, z)) + 1 for x in range(f["x0"], f["x1"] + 1) for z in (f["z"], f["z"] + 1)}
    assert feet == {f["y"]}, feet
    ox, oy, oz, _ = ZD["rip"]["outside"]
    assert round(g(int(ox), int(oz))) + 1 == oy
    sea = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]
    assert f["y"] - 1 > sea
    assert D.rip_restore_measured(ZD, lambda x, z: round(g(x, z))) == ZD["rip"]["restore"]
