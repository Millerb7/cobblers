"""The Street That Ends at Nothing (data/dungeons.json `street`): a new dungeon authored to the prize roster
(data/dungeon_prize_roster.json `street`, COVERAGE 2026-10-11) and its design (docs/mechanics/DUNGEON_2_STREET.md), on
the city theme (OVERWORLD2), unit NEW-STREET.

The author's own tests (the independent audit is another agent's). What they hold the record to:

  shape     every room type the owner named (maze, puzzle, parkour, resources, nest, habitat, stand, mini-boss) and at
            least three of ours; connectors at most 40 long and at least 7 wide; most rooms not boxes; the route turns
            (doors in four walls), doubles back west, climbs to the rooftops and walks east OVER the rooms it came along;
  length    tools/dungeon_clock.py's required time on the MAIN route about 32 minutes at band 1, the record's clock the
            tool's plus the set piece's stated allowance, every band under D17's hour, no lockout of its own;
  pacing    no two fight rooms back to back on any route in any variant; the safe room about two thirds in; the set piece
            (collapse: the street ending in nothing) the room before the boss;
  choices   two forks out of crossroads, one three ways, each way its own look and sign, asking different things; a WING of
            four rooms (a hard parkour, a secret, the prize habitat at its dead end) never on the clock; the prize's pools
            are exactly the roster's; two parkours; four secrets each with a relic; a shortcut back toward the entry;
            four distinct variants; at least three of the six optional rooms, each off the route;
  variety   rotation pools on the stands, the mini-boss and the boss (DUNGEON_ROOMS.md 14);
  walk      the room kit's own checks on every variant and branch;
  species   every species named is in the Cobblemon 1.8.0 jar; no legendary, mythical, Ultra Beast or paradox fights; the
            roster's rare prizes and their lines fight nowhere in this dungeon;
  rip       on the test trail at the x slot 1550, on the heightmap's ground, clear of the other rips and the old mine.

Not covered: anything in a running Minecraft.
"""
from __future__ import annotations

import copy
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_clock as C  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_rooms as R  # noqa: E402

DOC = D.load()
RIP = {r["legacy_dungeon"]: r for r in DOC["rips"] if r.get("legacy_dungeon")}   # the test rips (data/dungeon_rips.json)
ST = next(d for d in DOC["dungeons"] if d["id"] == "street")
OWNER_KINDS = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room"}
FIGHTS = {"stand", "gauntlet", "ambush", "miniboss", "nest", "habitat", "boss_arena"}
CONNECTORS = {"drift", "stairs"}
ENDS = {"entry_room", "exit_room"}
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
SETPIECE_ALLOWANCE_S = 25      # clock_why: one fall onto the set piece's catch floor, priced as the tool prices a fall
# the roster's rare prizes and their whole lines: none of them fights here, so the prize stays the find
PRIZE_LINES = {"beldum", "metang", "metagross", "honedge", "doublade", "aegislash", "deino", "zweilous", "hydreigon",
               "litwick", "lampent", "chandelure", "dreepy", "drakloak", "dragapult"}


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def slots():
    return [s for s in D.slots(DOC) if s["dungeon"]["id"] == "street"]


def slot1():
    return slots()[0]


def records(d=ST):
    return list(R._walk_records(d["rooms"]))


def variant_records():
    out = []
    for s in R.variant_slots(DOC, ST, slots()):
        out += records(R.resolve(DOC, ST, s))
    return out


def main_layout(slot=None):
    return [r for r in R.layout(DOC, ST, slot or slot1()) if r["route"] == "main"]


def wing():
    w = [r for r in ST["rooms"] if r["kind"] == "side" and not any(x["kind"] in EXTRA_KINDS for x in r["rooms"])]
    assert len(w) == 1
    return w[0]


# ------------------------------------------------------------------------------------------------- shape


def test_every_room_type_the_owner_named_is_there_and_three_of_ours():
    k = {r["kind"] for r in records()}
    assert OWNER_KINDS <= k, OWNER_KINDS - k
    assert len((OURS & k) - {"ambush"}) >= 3, OURS & k
    top = [r["kind"] for r in ST["rooms"]]
    assert top[0] == "entry_room" and top[-2:] == ["boss_arena", "exit_room"]
    assert ST["theme"] == "city" and ST["test"] is True and RIP[ST["id"]]["test"] is True and ST["gate_flag"] is None


def test_short_wide_connectors_and_mostly_not_boxes():
    lay = R.layout(DOC, ST, slot1())
    for r in lay:
        if r["kind"] in CONNECTORS:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
    shaped = [r for r in lay if r["kind"] not in CONNECTORS | ENDS | R.BOX_ONLY_KINDS | EXTRA_KINDS]
    assert sum(r["shape"] != "box" for r in shaped) >= len(shaped) * 0.5, [(r["id"], r["shape"]) for r in shaped]


def test_the_route_turns_doubles_back_and_walks_the_rooftops_over_the_street():
    lay = R.layout(DOC, ST, slot1())
    by = {r["id"]: r for r in lay}
    assert {x["side"] for r in lay for x in R.room_doors(r)} == {"north", "south", "east", "west"}
    assert [r["id"] for r in lay if r["route"] == "main" and r["dir"] == "west"] == ["back_alley", "tram_cut", "roof_stair", "roof_turn"]
    assert by["roof_stair"]["rise"] >= 12
    # the rooftops maze is STACKED over the street it came along: over the Avenue and the Fold, above their ceilings
    top = by["rooftops"]
    for low in ("avenue", "first_fold"):
        r = by[low]
        assert top["xa"] <= r["xb"] and r["xa"] <= top["xb"] and top["za"] <= r["zb"] and r["za"] <= top["zb"], low
        assert top["floor_in"] > r["ceil_y"], low
    # the wing goes DOWN under the street to the drowned plaza
    assert by["drowned_plaza"]["floor_in"] < by["gate_road"]["floor_in"] - 20


# ------------------------------------------------------------------------------------------------- length


def _required_by_band():
    walks = [C.walked(DOC, ST, s)[0] for s in R.variant_slots(DOC, ST, slots())]
    return {b["band"]: max(sum(C.required(DOC, ST, b["band"], C.clock_rooms(DOC, ST, b["band"], w)).values()) for w in walks)
            for b in DOC["engine"]["bands"]}


def test_about_32_minutes_required_at_band_1_and_the_clock_is_the_tools_plus_the_set_piece_allowance():
    req = _required_by_band()
    assert 29 * 60 <= req[1] <= 34 * 60, req[1] / 60
    slack = DOC["engine"]["clock"]["slack_factor"]
    own = ST["clock_s_by_band"]
    for b, s in req.items():
        assert own[str(b)] == math.ceil((s + SETPIECE_ALLOWANCE_S) * slack / 60) * 60, (b, own[str(b)])
        assert own[str(b)] <= 3600, "every band under D17's hour"
    assert "lockout_ticks" not in ST
    assert str(SETPIECE_ALLOWANCE_S) + " s" in ST["clock_why"]
    assert C.clock_problems(DOC, ST) == []


# ------------------------------------------------------------------------------------------------- pacing


def _neighbours(lay):
    by_i = {r["i"]: r for r in lay}
    for r in lay:
        for x in R.room_doors(r):
            if x["dir"] == "out" and not x.get("shortcut"):
                yield r, by_i[x["to"]]


def test_no_two_fights_back_to_back_on_any_route_in_any_variant():
    for s in R.variant_slots(DOC, ST, slots()):
        for a, b in _neighbours(R.layout(DOC, ST, s)):
            assert not (a["kind"] in FIGHTS and b["kind"] in FIGHTS), (s["k"], a["id"], b["id"])


def test_the_safe_room_two_thirds_in_and_the_set_piece_before_the_boss():
    rooms = C.walked(DOC, ST, slot1())[0]
    ids = [x["id"] for x in rooms]
    paid = sorted(C.clock_rooms(DOC, ST, 1, rooms), key=lambda r: ids.index(r["id"]))
    cost = [sum(C.required(DOC, {}, 1, [r]).values()) for r in paid]
    total = sum(cost) + C.required(DOC, ST, 1, [])["boss"]
    at = {r["id"]: sum(cost[:k]) / total for k, r in enumerate(paid)}
    assert 0.55 <= at["far_kerb"] <= 0.8, at["far_kerb"]
    main = [r for r in ST["rooms"] if r["kind"] not in ("fork", "side")]
    sp = main[[r["kind"] for r in main].index("boss_arena") - 1]
    assert sp["kind"] == "setpiece" and sp["params"]["piece"] == "collapse"
    assert [r["kind"] for r in records()].count("setpiece") == 1


# ------------------------------------------------------------------------------------------------- choices


def _forks():
    top = ST["rooms"]
    return [(top[k - 1], r) for k, r in enumerate(top) if r["kind"] == "fork"]


def test_two_forks_out_of_crossroads_one_three_ways_each_way_seen_and_told_apart():
    forks = _forks()
    assert len(forks) == 2 and all(h["kind"] == "crossroads" for h, _f in forks)
    assert sorted(len(f["routes"]) for _h, f in forks) == [2, 3]
    looks = set(R.load_themes()["themes"]["city"]["crossroads"]["looks"])
    for _h, f in forks:
        ls = [rt["look"] for rt in f["routes"]]
        assert len(set(ls)) == len(ls) and set(ls) <= looks, ls
        assert all(rt.get("sign") for rt in f["routes"]) and not any(rt.get("optional") for rt in f["routes"])
    for s in R.variant_slots(DOC, ST, slots()):
        lay = R.layout(DOC, ST, s)
        by_id = {r["id"]: r for r in lay}
        for h, f in forks:
            exits = [x for x in R.room_doors(by_id[h["id"]]) if x["dir"] == "out" and not x.get("shortcut")]
            assert len(exits) == len(f["routes"]), (s["k"], h["id"])
            for i, a in enumerate(exits):
                for b in exits[i + 1:]:
                    assert a["side"] != b["side"] or abs(a["c"] - b["c"]) >= 10, (s["k"], h["id"])


def test_the_ways_ask_different_things():
    kinds = {f["id"]: {rt["id"]: {r["kind"] for r in rt["rooms"]} - CONNECTORS for rt in f["routes"]} for _h, f in _forks()}
    assert sorted(map(sorted, kinds["f_square"].values())) == [["collapse_bridge"], ["dark_room"], ["nest"]]
    assert sorted(map(sorted, kinds["f_crossing"].values())) == [["miniboss"], ["puzzle"]]
    rooms = C.walked(DOC, ST, slot1())[0]
    walk = {rt: sum(r["walk"] for r in rooms if r["route"] == "f_square/" + rt) for rt in kinds["f_square"]}
    assert walk["boardwalk"] == min(walk.values()), walk


def test_the_wing_is_four_rooms_the_hard_parkour_guarding_the_prize_at_its_dead_end_never_on_the_clock():
    w = wing()
    assert len(w["rooms"]) == 4 and w["rooms"][0]["kind"] not in R.BOX_ONLY_KINDS
    hard, last = w["rooms"][-2], w["rooms"][-1]
    assert hard["kind"] == "parkour" and hard["params"].get("hard") is True
    assert last["kind"] == "habitat" and last["params"].get("prize") and last.get("gate") == "open"
    assert any(r.get("secrets") for r in w["rooms"])
    ids = {r["id"] for r in w["rooms"]}
    for s in R.variant_slots(DOC, ST, slots()):
        hab = next(r for r in R.layout(DOC, ST, s) if r["id"] == last["id"])
        assert hab["route"] == w["id"] and not [x for x in R.room_doors(hab) if x["dir"] == "out"]
        walked = C.walked(DOC, ST, s)[0]
        for b in DOC["engine"]["bands"]:
            assert not {r["id"] for r in C.clock_rooms(DOC, ST, b["band"], walked)} & ids


@pytest.fixture(scope="module")
def jar():
    import dungeon_prize as PZ
    labels = PZ.jar_labels()
    if labels is None:
        pytest.skip("no Cobblemon 1.8 jar")
    return labels


def test_the_prize_pools_are_exactly_the_rosters_and_the_gated_bands_fill_once_the_models_ship(jar):
    import json
    import dungeon_prize as PZ
    room = wing()["rooms"][-1]
    assert room["params"]["prize"]["roster"] == "street"
    assert PZ.room_problems(DOC, ST, room) == []
    roster = next(e for e in json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))["dungeons"]
                  if e["id"] == "street")
    lf = DOC["engine"]["prize"]["legendary_from_band"]
    gated = lambda sp: PZ.model_gated(DOC, sp)  # noqa: E731
    for b in range(1, 7):
        key = "legendary_pool_by_band" if b >= lf else "rare_pool_by_band"
        want = [sp for sp in roster.get(key, {}).get(str(b), []) if not gated(sp)]
        got = PZ.pool_at(DOC, room, b)
        assert (got[0] if got else []) == want, (b, got, want)
        for sp in want:
            assert bool(jar[sp] & {"legendary", "mythical", "ultra_beast", "paradox"}) == (b >= lf), (b, sp)
    # Palkia is restricted: band 6 only, and it is there now
    assert PZ.pool_at(DOC, room, 6)[0][0] == "palkia" and "restricted" in jar["palkia"]
    # bands 4-5 are empty only because every roster species there is model-gated (atm_subset): deliver it and they fill
    doc = copy.deepcopy(DOC)
    doc["engine"]["prize"]["models_delivered"] = ["atm_subset"]
    for b in (4, 5):
        assert PZ.pool_at(doc, room, b)[0] == roster["legendary_pool_by_band"][str(b)], b


def test_the_prize_is_spawned_at_the_lower_cap_and_its_ultra_beast_bound_native():
    import key_ball as KB
    s = slot1()
    files = D.build(DOC)
    room = wing()["rooms"][-1]
    base = "data/cobblers/function/dungeons/room/street/%s/s%d/" % (room["id"], s["g"])
    for b in (1, 2, 3, 6):
        cap = next(x for x in DOC["engine"]["bands"] if x["band"] == b)["caps"][0]
        assert "level=%d no_ai" % cap in files[base + "prize/spawn_b%d.mcfunction" % b], b
    assert "A tram driver swears" in files["data/cobblers/function/dungeons/slot/s%d/start.mcfunction" % s["g"]]
    assert KB.boss_problems(KB.load()) == []


def test_two_parkours_the_main_one_six_sections_the_wings_hard():
    main = next(r for r in records() if r["kind"] == "parkour" and not r["params"].get("hard"))
    hard = next(r for r in records() if r["kind"] == "parkour" and r["params"].get("hard"))
    assert main["params"]["sections"] == 6 and main["width"] == 25 and main["id"] in {r["id"] for r in ST["rooms"]}
    assert hard["params"]["sections"] >= 4 and hard["id"] in {r["id"] for r in wing()["rooms"]}


def test_four_secrets_each_with_its_own_relic_and_lore():
    found = [(r, s) for r in records() for s in r.get("secrets") or []]
    assert sorted(s["type"] for _r, s in found) == ["balcony", "balcony", "cracked", "cracked"]
    relics = []
    for r, _s in found:
        p = r["params"]
        assert re.fullmatch(r"st_[a-z0-9_]+", p["relic"]) and len(p.get("relic_name", "")) <= 32
        assert p["lore"] and len(p["lore"]) <= 160 and all(32 <= ord(c) < 127 for c in p["lore"])
        relics.append(p["relic"])
    assert len(set(relics)) == 4


def test_the_shortcut_opens_from_the_tram_cut_back_into_the_first_fold():
    lay = R.layout(DOC, ST, slot1())
    by = {r["id"]: r for r in lay}
    far, near = by["tram_cut"], by["first_fold"]
    assert near["i"] < far["i"] and far["i"] - near["i"] >= 3
    assert far["shortcut_doors"][0]["y"] == near["shortcut_doors"][0]["y"]
    fns = D.build(DOC)
    assert any(k.endswith("/tram_cut/s%d/shortcut_c_fold.mcfunction" % slot1()["g"]) for k in fns)


def test_four_distinct_variants():
    vs = ST["variants"]
    assert len(vs) == 4 and any(v.get("mirror") for v in vs) and any(v.get("swap") for v in vs) and any(v.get("order") for v in vs)
    d = next(v for v in vs if v.get("order"))
    top = [r["id"] for r in ST["rooms"]]
    assert sorted(d["order"]) == sorted(top) and d["order"] != top and d["order"][0] == top[0] and d["order"][-1] == top[-1]
    shapes = {tuple((r["id"], r["xa"] - s["x0"], r["za"] - s["z0"], r["shape"]) for r in R.layout(DOC, ST, s)) for s in slots()}
    assert len(shapes) == 4


def test_at_least_three_optional_rooms_each_off_the_route_and_never_paid():
    rooms = C.walked(DOC, ST)[0]
    paid = {r["id"] for b in DOC["engine"]["bands"] for r in C.clock_rooms(DOC, ST, b["band"], rooms)}
    for s in slots():
        mine = [r for r in R.layout(DOC, ST, s) if r["kind"] in EXTRA_KINDS]
        assert len({r["kind"] for r in mine}) >= 3, s["g"]
        for r in mine:
            assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open" and r["id"] not in paid
    bank = next(r for r in records() if r["kind"] == "bank_vault")
    ids = [r["id"] for r in records()]
    assert all(ids.index(c) > ids.index(bank["id"]) for c in bank["params"]["clue_rooms"]), \
        "the code is found further down the street; the tram cut's shortcut brings the player back"


def test_rotation_pools_on_the_stands_the_mini_boss_and_the_boss():
    stands = [r for r in records() if r["kind"] == "stand"]
    assert len(stands) == 3 and all(t.get("team_pool_by_band") for r in stands for t in r["params"]["trainers"])
    assert next(r for r in records() if r["kind"] == "miniboss")["params"].get("species_pool_by_band")
    assert set(ST["boss"]["teams_alt_by_band"]) == {str(b["band"]) for b in DOC["engine"]["bands"]}
    assert ST["boss"]["heal_between_stages"] is True and len(ST["boss"]["stage_level_offsets"]) == 2


# ------------------------------------------------------------------------------------------------- the walk


def test_the_street_builds_and_walks_with_no_problem_in_every_variant_and_branch():
    assert R.problems(DOC, ST) == []
    assert not [p for p in D.problems(DOC) if "street" in p]


def test_the_street_builds_its_functions_and_its_shell_fits_the_chain():
    s = slot1()
    files = D.build(DOC)
    assert len([k for k in files if "/shells/s%d/" % s["g"] in k]) == len(records())
    assert R.chain_problems(DOC, ST, s) == []
    assert 0.3e6 < D.shell_blocks(DOC, s) < 1.5e6


# ------------------------------------------------------------------------------------------------- species


@pytest.fixture(scope="module")
def species():
    import battle_sim as B
    try:
        jar = B.find_jar()
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar")
    sp, _m, _c = B.load_pack(jar)
    return sp, B.key


def fighting_species():
    out = []
    for r in variant_records():
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for team in (t.get("team_by_band") or {}).values():
                out += [(r["id"], x) for x in team]
            for teams in (t.get("team_pool_by_band") or {}).values():
                out += [(r["id"], x) for team in teams for x in team]
        if r["kind"] == "nest":
            out += [(r["id"], x) for x in p.get("species", [])]
        out += [(r["id"], x) for x in (p.get("species_by_band") or {}).values()]
        out += [(r["id"], x) for v in (p.get("species_pool_by_band") or {}).values() for x in v]
    bo = ST["boss"]
    for crews in bo["teams"].values():
        out += [("boss", x) for c in crews for x in c]
    for alts in bo.get("teams_alt_by_band", {}).values():
        out += [("boss", x) for alt in alts for c in alt for x in c]
    return out


def test_every_species_named_is_in_the_jar_and_none_that_fights_is_legendary(species):
    sp, key = species
    named = fighting_species()
    assert not sorted({x for _r, x in named if key(x) not in sp})
    for where, x in named:
        assert not set(sp[key(x)].get("labels", [])) & {"legendary", "mythical", "ultra_beast", "paradox"}, (where, x)


def test_the_rosters_rare_prizes_fight_nowhere_here():
    assert not {(r, x) for r, x in fighting_species() if x in PRIZE_LINES}


def test_the_fight_params_follow_the_contract():
    bands = {str(b["band"]) for b in D.bands(DOC)}
    for r in variant_records():
        p = r.get("params", {})
        if r["kind"] in ("stand", "gauntlet", "ambush"):
            assert DF.stand_problems(DOC, r) == [], r["id"]
            assert r["gate"] == "cleared"
        elif r["kind"] == "miniboss":
            assert set(p.get("species_by_band", {})) | set(p.get("species_pool_by_band", {})) == bands
            assert p["level_offset"] <= 0 and p.get("catchable") is True and r["gate"] == "cleared"
        elif r["kind"] == "nest":
            assert set(p["count_by_band"]) == bands and r["gate"] == "cleared"
        elif r["kind"] == "safe_room":
            assert p.get("healer") is True


def test_the_boss_has_a_crew_per_stage_per_band_the_ace_last():
    bo = ST["boss"]
    for b in D.bands(DOC):
        crews = bo["teams"][str(b["band"])] + [c for alt in bo["teams_alt_by_band"][str(b["band"])] for c in alt]
        assert len({c[-1] for c in crews}) == 1 and crews[0][-1] in ("golett", "golurk"), b["band"]
        assert all(len(alt) == len(bo["stage_level_offsets"]) for alt in bo["teams_alt_by_band"][str(b["band"])])


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_stands_at_its_x_slot_clear_of_the_other_rips_and_the_old_mine():
    import json
    f = RIP[ST["id"]]["frame"]
    assert 1540 <= f["x0"] and f["x1"] <= 1560 and abs(f["z"] - 4118) <= 4
    for o in DOC["dungeons"]:
        if o["id"] == "street":
            continue
        of = RIP[o["id"]]["frame"]
        assert f["x0"] > of["x1"] + 6 or f["x1"] < of["x0"] - 6 or abs(f["z"] - of["z"]) > 8, o["id"]
    mine = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]["route1_old_mine"]
    x0, z0, x1, z1 = mine["plan"]["footprint"]["rect"]
    assert f["x0"] - 1 > x1 or f["x1"] + 1 < x0 or f["z"] + 5 < z0 or f["z"] - 1 > z1
    cx, cy, cz = RIP[ST["id"]]["click"]
    assert cz == f["z"] + 1 and cy == f["y"] and cx == (f["x0"] + f["x1"]) // 2
    assert RIP[ST["id"]]["outside"][2] - 0.5 > cz + 1.5


def test_the_rip_is_on_the_heightmaps_ground_and_not_in_water():
    try:
        import ground as GR
        g = GR.load()
    except Exception as e:  # noqa: BLE001  (no heightmap in this checkout)
        pytest.skip("no heightmap: %s" % e)
    import json
    f = RIP[ST["id"]]["frame"]
    assert {g(x, z) + 1 for x in range(f["x0"], f["x1"] + 1) for z in (f["z"], f["z"] + 1)} == {f["y"]}
    ox, oy, oz, _ = RIP[ST["id"]]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy
    sea = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]
    assert f["y"] - 1 > sea
