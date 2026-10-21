"""The Ash Bell (data/dungeons.json `ash_bell`): the first of the prize roster's Nether dungeons
(data/dungeon_prize_roster.json `ash_bell`, theme nether_wastes), authored full length on the room kit (unit NEW-ASHBELL,
2026-10-11). The Burned Tower of the old story sunk into the wastes: NETHER_ENCOUNTERS.md 3.1.

The author's own tests (the independent audit, tools/dungeon_independent_audit.py, is another agent's). What they hold
the record to, the owner's standing asks for every dungeon (DUNGEON_PASS2.md, DUNGEON_ROOMS.md 1a/1b, 12-14):

  shape     every room type the owner named, three of ours and three of the six optional rooms (as side rooms, never
            paid by the clock); connectors at most 40 long and at least 7 wide; most rooms take a non-box outline; the
            route turns, doubles back and drops;
  length    tools/dungeon_clock.py's required time about 32 minutes at band 1, the record's clock the tool's plus the set
            piece's stated allowance, every band under D17's hour, no lockout of its own;
  pacing    no two fight rooms back to back in any variant; the safe room about two thirds in; the collapse right
            before the boss;
  choices   two forks out of crossroads, one three ways, each look distinct; the optional WING (a hard parkour, a balcony
            secret, the prize habitat); two parkours (the main six sections with a fork, the wing's hard with none);
            three secrets with relics; a shortcut; four distinct variants;
  variety   the per-run rotation pools: two teams a band for every trainer, a species pool for the mini-boss, an
            alternate crew list for the boss (DUNGEON_ROOMS.md 14);
  prize     exactly the roster's species: Raikou (band 5), Raikou (band 6; Ho-Oh moved to the world tree 2026-10-21), Raging Bolt and Sandy Shocks held back by their model
            gate; the Beast Ball key from band 4; nothing below band 5;
  walk      the room kit's own checks (every variant and branch);
  species   every species named is in the Cobblemon 1.8.0 jar, none a doll or a mis-assembled model, no legendary
            outside the prize;
  rip       on the test trail at x1450, on the heightmap's ground, clear of the old mine and of the other rips.

And a GENERATOR mutation: the clock test is tied to tools/dungeon_clock.py's own derivation, not to numbers copied from
it: slowing the tool's parkour pace (the code, the data untouched) must make the authored clock wrong.

Not covered: anything in a running Minecraft.
"""
from __future__ import annotations

import copy
import json
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
RIP = {r["legacy_dungeon"]: r for r in DOC["retired_rips"]}   # the 13 test rips, RETIRED 2026-10-13 (retired_rips in data/dungeon_rips.json): the records are kept
AB = next(d for d in DOC["dungeons"] if d["id"] == "ash_bell")
OWNER_KINDS = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room"}
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
FIGHTS = {"stand", "gauntlet", "ambush", "miniboss", "nest", "habitat", "boss_arena"}
CONNECTORS = {"drift", "stairs"}
ENDS = {"entry_room", "exit_room"}
SETPIECE_ALLOWANCE_S = 25      # clock_why: one fall back to the ledge, priced as the tool prices a fall (15 + 10)
ROSTER = json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def slots():
    return [s for s in D.slots(DOC) if s["dungeon"]["id"] == "ash_bell"]


def slot1():
    return slots()[0]


def records(d=AB):
    return list(R._walk_records(d["rooms"]))


def variant_records():
    out = []
    for s in R.variant_slots(DOC, AB, slots()):
        out += records(R.resolve(DOC, AB, s))
    return out


def solo():
    """The pack doc with this dungeon alone (its slots renumbered from 1): building the whole pack for one room's files
    took 150 s; nothing here reads another dungeon's functions."""
    doc = copy.deepcopy(DOC)
    doc["dungeons"] = [d for d in doc["dungeons"] if d["id"] == "ash_bell"]
    ff = doc["engine"]["sigils"]["free_first_entry"]
    ff["dungeons"] = [x for x in ff["dungeons"] if x == "ash_bell"]
    return doc


def roster_entry():
    ds = ROSTER["dungeons"]
    return ds["ash_bell"] if isinstance(ds, dict) else next(x for x in ds if x["id"] == "ash_bell")


# ------------------------------------------------------------------------------------------------- shape


def test_every_room_type_the_owner_named_three_of_ours_and_three_optional_rooms():
    k = {r["kind"] for r in records()}
    assert OWNER_KINDS <= k, OWNER_KINDS - k
    assert len((OURS & k) - {"ambush"}) >= 3, OURS & k
    assert len(EXTRA_KINDS & k) >= 3, EXTRA_KINDS & k
    top = [r["kind"] for r in AB["rooms"]]
    assert top[0] == "entry_room" and top[-2:] == ["boss_arena", "exit_room"]
    assert AB["theme"] == "nether_wastes" and AB["test"] is True
    assert AB["gate_flag"] == "cobblers:flag/gym8_cleared" and AB["first_band"] == 5, "the roster's gate and floor (the draw, 2026-10-13)"
    assert RIP[AB["id"]]["test"] is True


def test_the_optional_rooms_stand_off_the_route_open_and_never_paid():
    rooms = C.walked(DOC, AB)[0]
    paid = {r["id"] for b in DOC["engine"]["bands"] for r in C.clock_rooms(DOC, AB, b["band"], rooms)}
    for s in slots():
        extra = [r for r in R.layout(DOC, AB, s) if r["kind"] in EXTRA_KINDS]
        assert len({r["kind"] for r in extra}) >= 3, s["k"]
        for r in extra:
            assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open", (s["k"], r["id"])
            assert r["id"] not in paid, r["id"]
    bank = next(r for r in records() if r["kind"] == "bank_vault")
    ids = {r["id"] for r in records()}
    assert set(bank["params"]["clue_rooms"]) <= ids and len(bank["params"]["clue_rooms"]) == 3
    bait = next(r for r in records() if r["kind"] == "bait_room")
    assert bait["params"]["lure_room"] in ids


def test_short_wide_connectors_and_mostly_not_boxes():
    lay = R.layout(DOC, AB, slot1())
    assert len([r for r in lay if r["route"] == "main"]) <= 18
    for r in lay:
        if r["kind"] in CONNECTORS:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
    shaped = [r for r in lay if r["kind"] not in CONNECTORS | ENDS | R.BOX_ONLY_KINDS | EXTRA_KINDS]
    assert sum(r["shape"] != "box" for r in shaped) >= len(shaped) * 0.7, [(r["id"], r["shape"]) for r in shaped]


def test_the_route_turns_doubles_back_and_drops():
    lay = R.layout(DOC, AB, slot1())
    assert {x["side"] for r in lay for x in R.room_doors(r)} == {"north", "south", "east", "west"}
    assert any(r["in_side"] == "east" for r in lay), "a room walked back west"
    assert max(x["y"] - r["floor_in"] for r in lay for x in R.room_doors(r)) >= 12, "a door on a high landing"
    floors = {r["floor_in"] for r in lay}
    assert max(floors) - min(floors) >= 20, floors
    main = [r for r in lay if r["route"] == "main"]
    assert any(a["xa"] <= b["xb"] and b["xa"] <= a["xb"] and (a["zb"] < b["za"] or b["zb"] < a["za"] or a["floor_in"] != b["floor_in"])
               for a in main for b in main if a["i"] < b["i"] - 1), "the return runs beside or under rooms it came along"


# ------------------------------------------------------------------------------------------------- length


def _required_by_band(doc=DOC, d=AB):
    ss = [s for s in D.slots(doc) if s["dungeon"]["id"] == d["id"]]
    walks = [C.walked(doc, d, s)[0] for s in R.variant_slots(doc, d, ss)]
    return {b["band"]: max(sum(C.required(doc, d, b["band"], C.clock_rooms(doc, d, b["band"], w)).values()) for w in walks)
            for b in doc["engine"]["bands"]}


def _expected_clock(req, slack):
    return {str(b): math.ceil((s + SETPIECE_ALLOWANCE_S) * slack / 60) * 60 for b, s in req.items()}


def test_about_32_minutes_required_at_band_1_and_the_clock_is_the_tools_plus_the_set_piece_allowance():
    req = _required_by_band()
    assert 30 * 60 <= req[1] <= 34 * 60, req[1] / 60
    slack = DOC["engine"]["clock"]["slack_factor"]
    want = _expected_clock(req, slack)
    own = AB["clock_s_by_band"]
    # every band the formula's (MEGA-INTEGRATE: each dungeon's vaults are priced on its own clock, so band 4 is no longer
    # raised to keep another dungeon's vault budget)
    assert own == want
    assert all(v <= 3600 for v in own.values()), "every band under D17's hour"
    assert "lockout_ticks" not in AB
    assert str(SETPIECE_ALLOWANCE_S) + " s" in AB["clock_why"]
    assert C.clock_problems(DOC, AB) == []


def test_mutating_the_clock_tools_parkour_pace_makes_the_authored_clock_wrong(monkeypatch):
    # the generator, not the record: a slower parkour pace in tools/dungeon_clock.py, data/dungeons.json untouched
    monkeypatch.setattr(C, "PARKOUR_BPS", C.PARKOUR_BPS / 2)
    req = _required_by_band()
    assert AB["clock_s_by_band"] != _expected_clock(req, DOC["engine"]["clock"]["slack_factor"])
    assert C.clock_problems(DOC, AB), "a slower pace derives a longer clock than the record's"


# ------------------------------------------------------------------------------------------------- pacing


def _neighbours(lay):
    by_i = {r["i"]: r for r in lay}
    for r in lay:
        for x in R.room_doors(r):
            if x["dir"] == "out" and not x.get("shortcut"):
                yield r, by_i[x["to"]]


def test_no_two_fights_back_to_back_on_any_route_in_any_variant():
    for s in R.variant_slots(DOC, AB, slots()):
        for a, b in _neighbours(R.layout(DOC, AB, s)):
            assert not (a["kind"] in FIGHTS and b["kind"] in FIGHTS), (s["k"], a["id"], b["id"])


def test_the_heal_comes_before_the_last_stretch_and_the_collapse_right_before_the_boss():
    # NOT "two thirds in": by the tool's paces the vigil room sits at 49% of the paid band-1 time with the boss (53% of the
    # walk), as the Night Shift's lamp cabin (50%, 58%), whose geometry this stretch shares; the jungle and the ruin sit at
    # 63%. What the heal does hold to: after it the route has the second fork, the choir's two fights, the collapse and the
    # boss, and no other fight; every other required fight is behind it
    safe = next(r for r in records() if r["kind"] == "safe_room")
    assert safe["params"].get("healer") is True
    for s in R.variant_slots(DOC, AB, slots()):
        rooms = C.walked(DOC, AB, s)[0]
        paid = sorted(C.clock_rooms(DOC, AB, 1, rooms), key=lambda r: [x["id"] for x in rooms].index(r["id"]))
        k = [r["id"] for r in paid].index(safe["id"])
        after = [r["id"] for r in paid[k + 1:] if r["kind"] in FIGHTS]
        assert after == ["choir_hall", "belfry"], (s["k"], after)
        assert [r for r in paid[:k] if r["kind"] in FIGHTS], s["k"]
    main = [r for r in AB["rooms"] if r["kind"] not in ("fork", "side")]
    sp = main[[r["kind"] for r in main].index("boss_arena") - 1]
    assert sp["kind"] == "setpiece" and sp["params"]["piece"] == "collapse"
    assert [r["kind"] for r in records()].count("setpiece") == 1


# ------------------------------------------------------------------------------------------------- choices


def _forks():
    top = AB["rooms"]
    return [(top[k - 1], r) for k, r in enumerate(top) if r["kind"] == "fork"]


def test_two_forks_out_of_crossroads_one_three_ways_each_way_its_own_look_and_door():
    forks = _forks()
    assert len(forks) == 2 and all(h["kind"] == "crossroads" for h, _f in forks)
    assert sorted(len(f["routes"]) for _h, f in forks) == [2, 3]
    looks = set(R.load_themes()["themes"]["nether_wastes"]["crossroads"]["looks"])
    for _h, f in forks:
        ls = [rt["look"] for rt in f["routes"]]
        assert len(set(ls)) == len(ls) and set(ls) <= looks, ls
        assert all(rt.get("sign") for rt in f["routes"])
        assert any(not rt.get("optional") for rt in f["routes"])
    for s in R.variant_slots(DOC, AB, slots()):
        by_id = {r["id"]: r for r in R.layout(DOC, AB, s)}
        for h, f in forks:
            exits = [x for x in R.room_doors(by_id[h["id"]]) if x["dir"] == "out" and not x.get("shortcut")]
            assert len(exits) == len(f["routes"]), (s["k"], h["id"])
            for i, a in enumerate(exits):
                for b in exits[i + 1:]:
                    assert a["side"] != b["side"] or abs(a["c"] - b["c"]) >= 10, (s["k"], h["id"])


def test_the_three_ways_ask_danger_length_or_a_puzzle():
    three = next(f for _h, f in _forks() if len(f["routes"]) == 3)
    k3 = {rt["id"]: frozenset({r["kind"] for r in rt["rooms"]} - CONNECTORS) for rt in three["routes"]}
    assert set(k3.values()) == {frozenset({"collapse_bridge"}), frozenset({"dark_room"}), frozenset({"puzzle"})}, k3


def _wing():
    two = next(f for _h, f in _forks() if len(f["routes"]) == 2)
    return next(rt for rt in two["routes"] if rt.get("optional"))


def test_the_wing_is_optional_a_hard_parkour_guarding_the_prize_never_on_the_clock():
    w = _wing()
    kinds = [r["kind"] for r in w["rooms"]]
    assert 2 <= len(kinds) <= 4 and kinds[0] not in R.BOX_ONLY_KINDS
    hab = next(r for r in w["rooms"] if r["kind"] == "habitat")
    i = kinds.index("habitat")
    assert kinds[i - 1] == "parkour" and w["rooms"][i - 1]["params"].get("hard") is True
    assert hab["params"].get("prize") and hab.get("gate", "open") == "open"
    assert any(s["type"] == "balcony" for s in hab.get("secrets") or [])
    ids = {r["id"] for r in w["rooms"]}
    for s in R.variant_slots(DOC, AB, slots()):
        for b in DOC["engine"]["bands"]:
            paid = {r["id"] for r in C.clock_rooms(DOC, AB, b["band"], C.walked(DOC, AB, s)[0])}
            assert not paid & ids, (s["k"], b["band"], paid & ids)


def test_two_parkours_the_main_one_six_sections_with_its_fork_the_wings_hard_with_none():
    import dungeon_parkour as P
    main = next(r for r in records() if r["kind"] == "parkour" and not r["params"].get("hard"))
    hard = next(r for r in records() if r["kind"] == "parkour" and r["params"].get("hard"))
    assert main["params"]["sections"] == 6 and main["width"] == 25 and main["length"] >= 30 * 6 - 10 + 2
    assert hard["id"] in {r["id"] for r in _wing()["rooms"]} and hard["params"]["sections"] >= 4
    for s in R.variant_slots(DOC, AB, slots()):
        dd = R.resolve(DOC, AB, s)
        bs = {b.room["id"]: b for b in R.slot_build(DOC, AB, s)}
        _route, ledges, _lv, fork_i = P.plan_route(dd, bs[main["id"]].room)
        assert len(ledges) == 7 and fork_i is not None, (s["k"], len(ledges), fork_i)
        route, ledges, _lv, fork_i = P.plan_route(dd, bs[hard["id"]].room)
        assert len(ledges) == hard["params"]["sections"] + 1 and fork_i is None, (s["k"], len(ledges))


def test_three_secrets_two_cracked_one_balcony_each_with_a_relic_and_its_lore():
    found = [(r, s) for r in records() for s in r.get("secrets") or []]
    assert sorted(s["type"] for _r, s in found) == ["balcony", "cracked", "cracked"]
    relics = []
    for r, _s in found:
        p = r["params"]
        assert re.fullmatch(r"ab_[a-z0-9_]+", p["relic"])
        assert p["lore"] and len(p["lore"]) <= 160 and all(32 <= ord(c) < 127 for c in p["lore"])
        assert len(p.get("relic_name", "")) <= 32
        relics.append(p["relic"])
    assert len(set(relics)) == 3
    assert set(R.pick_blocks(AB)) >= {R.load_themes()["themes"]["nether_wastes"]["shapes"]["secret_block"]}


def test_the_shortcut_opens_back_onto_the_return_on_one_floor():
    far = [r for r in records() if r.get("shortcuts")]
    assert len(far) == 1 and len(far[0]["shortcuts"]) == 1
    by_id = {r["id"]: r for r in R.layout(DOC, AB, slot1())}
    f, near = by_id[far[0]["id"]], by_id[far[0]["shortcuts"][0]["to"]]
    assert near["i"] < f["i"] and near["route"] == f["route"] == "main"
    df, dn = f["shortcut_doors"][0], near["shortcut_doors"][0]
    assert df["y"] == dn["y"] and df["c"] == dn["c"]


def test_four_distinct_variants_one_per_slot():
    vs = AB["variants"]
    assert len(vs) == 4 and len({v["id"] for v in vs}) == 4
    assert any(v.get("mirror") for v in vs) and any(v.get("seed") for v in vs)
    assert any(v.get("swap") for v in vs) and any(v.get("order") for v in vs)
    assert [R.variant_of(DOC, AB, s)["id"] for s in slots()] == [v["id"] for v in vs]
    shapes = {tuple((r["id"], r["xa"] - s["x0"], r["za"] - s["z0"], r["shape"]) for r in R.layout(DOC, AB, s)) for s in slots()}
    assert len(shapes) == 4
    d = next(v for v in vs if v.get("order"))
    top = [r["id"] for r in AB["rooms"]]
    assert sorted(d["order"]) == sorted(top) and d["order"] != top and d["order"][0] == top[0] and d["order"][-1] == top[-1]


# ------------------------------------------------------------------------------------------------- variety


def test_every_fight_rotates_two_teams_a_trainer_a_species_pool_and_an_alternate_boss_crew():
    trainers = [t for r in records() if r["kind"] in ("stand", "gauntlet") for t in r["params"]["trainers"]]
    assert len(trainers) == 4
    for t in trainers:
        assert "team_by_band" not in t
        assert all(len(v) == 2 for v in t["team_pool_by_band"].values()), t["name"]
    mb = next(r for r in records() if r["kind"] == "miniboss")
    assert "species_by_band" not in mb["params"]
    assert all(len(v) >= 2 for v in mb["params"]["species_pool_by_band"].values())
    alt = AB["boss"]["teams_alt_by_band"]
    assert set(alt) == {str(b["band"]) for b in D.bands(DOC)}
    for b, crews in alt.items():
        assert crews[0] != AB["boss"]["teams"][b]


# ------------------------------------------------------------------------------------------------- prize


def test_the_prize_is_exactly_the_rosters_and_nothing_below_band_5():
    import dungeon_prize as PZ
    hab = next(r for r in records() if r["kind"] == "habitat")
    pz = hab["params"]["prize"]
    assert pz["roster"] == "ash_bell" and "rare_by_band" not in pz and "rare_pool_by_band" not in pz
    entry = roster_entry()
    for b, sp in pz["legendary_by_band"].items():
        assert sp in entry["legendary_pool_by_band"][b], (b, sp)
    assert sorted(pz["legendary_by_band"]) == ["5", "6"] and not entry["rare_pool_by_band"]
    assert PZ.room_problems(DOC, AB, hab) == []
    assert "species" not in hab["params"], "a resident would be no hidden prize"


def test_the_prize_spawns_at_the_lower_cap_with_the_beast_ball_key_and_the_model_gate_holds_raging_bolt_back():
    import key_ball as KB
    doc = solo()
    s = next(x for x in D.slots(doc) if x["k"] == 1)
    files = D.build(doc)
    hab = next(r for r in records() if r["kind"] == "habitat")
    base = "data/cobblers/function/dungeons/room/ash_bell/%s/s%d/" % (hab["id"], s["g"])
    spawns = {k[len(base):]: v for k, v in files.items() if k.startswith(base + "prize/spawn_")}
    # band 6 is Raikou alone since Ho-Oh moved to the world tree (2026-10-21): Raging Bolt and Sandy Shocks are held back
    # by the same model gate, so the pool has one member and there is no spawn_b6_2
    assert sorted(spawns) == ["prize/spawn_b5.mcfunction", "prize/spawn_b6.mcfunction"]
    caps = {b["band"]: b["caps"][0] for b in D.bands(DOC)}
    for name, body in spawns.items():
        band = int(re.search(r"_b(\d)", name).group(1))
        assert "level=%d no_ai" % caps[band] in body, name
        assert body.rstrip().endswith("prize/bind"), name
        assert "ragingbolt" not in body, "Raging Bolt's model is the AllTheMons subset's: gated until delivered"
        assert "sandyshocks" not in body, "Sandy Shocks is gated by the same model subset"
    tag = "tag @s add %s" % KB.boss_tag()
    assert tag in files[base + "prize/bind.mcfunction"].split("\n")
    assert KB.boss_problems(KB.load()) == []


# ------------------------------------------------------------------------------------------------- the walk


def test_the_ash_bell_builds_and_walks_with_no_problem_in_every_variant_and_branch():
    doc = solo()
    assert D.problems(doc) == []
    assert not [w for w in D.warnings(doc) if "ash_bell" in w]


def test_the_shell_fits_the_chain():
    s = slot1()
    assert R.chain_problems(DOC, AB, s) == []
    assert 0.3e6 < D.shell_blocks(DOC, s) < 1.2e6


# ------------------------------------------------------------------------------------------------- species


@pytest.fixture(scope="module")
def jar():
    import battle_sim as B
    try:
        path = B.find_jar()
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar")
    sp, _m, _c = B.load_pack(path)
    return sp, B.key


def named_species():
    out = []

    def leaves(where, x):
        if isinstance(x, str):
            out.append((where, x))
        elif isinstance(x, list):
            for y in x:
                leaves(where, y)
        elif isinstance(x, dict):
            for y in x.values():
                leaves(where, y)

    for r in variant_records():
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            leaves(r["id"], t.get("team_pool_by_band") or t.get("team_by_band"))
        if r["kind"] == "nest":
            leaves(r["id"], p["species"])
        leaves(r["id"], p.get("species_pool_by_band") or p.get("species_by_band") or {})
    leaves("boss", AB["boss"]["teams"])
    leaves("boss", AB["boss"]["teams_alt_by_band"])
    return out


def test_every_species_is_in_the_jar_none_a_doll_and_no_legendary_outside_the_prize(jar):
    sp, key = jar
    named = named_species()
    assert not sorted({x for _w, x in named if key(x) not in sp})
    text = (ROOT / "docs" / "research" / "COBBLEVERSE_COMPATIBILITY.md").read_text(encoding="utf-8")
    dolls = {s.strip().rstrip(".") for s in re.search(r"^(arctibax, blacephalon[^\n]*)$", text, re.M).group(1).split(",")}
    misassembled = {"pidgeot", "talonflame", "arbok", "crobat", "cofagrigus", "skarmory", "tyranitar", "garganacl", "goodra",
                    "primarina", "nidoking", "turtonator", "appletun", "archaludon"}
    assert not {x for _w, x in named} & (dolls | misassembled)
    for where, x in named:
        assert not set(sp[key(x)].get("labels", [])) & {"legendary", "mythical", "ultra_beast", "paradox"}, (where, x)


def test_the_fight_params_follow_the_contract():
    bands = {str(b["band"]) for b in D.bands(DOC)}
    for r in variant_records():
        p = r.get("params", {})
        if r["kind"] in ("stand", "gauntlet", "ambush"):
            assert DF.stand_problems(DOC, r) == [], r["id"]
            assert r["gate"] == "cleared"
            if r["kind"] != "stand":
                tr = p["triggers"]
                assert len(tr) == len(p["trainers"]) and tr == sorted(tr) and all(0 < t < 1 for t in tr)
        elif r["kind"] == "miniboss":
            assert set(p["species_pool_by_band"]) == bands and p["level_offset"] <= 0 and p["catchable"] is True
            assert r["gate"] == "cleared"
        elif r["kind"] == "nest":
            assert set(p["count_by_band"]) == bands and p["clear"] == "pass"
    bo = AB["boss"]
    assert bo["heal_between_stages"] is True and len(bo["stage_level_offsets"]) == 2 and max(bo["stage_level_offsets"]) <= 0
    for b in bands:
        for crews in [bo["teams"][b]] + bo["teams_alt_by_band"][b]:
            assert len(crews) == 2 and len({c[-1] for c in crews}) == 1, "one ace, sent out last in both stages"


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_is_on_the_test_trail_clear_of_the_mine_and_the_other_rips():
    f = RIP[AB["id"]]["frame"]
    assert abs((f["x0"] + f["x1"]) / 2 - 1450) <= 10 and abs(f["z"] - 4118) <= 4
    mine = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]["route1_old_mine"]
    x0, z0, x1, z1 = mine["plan"]["footprint"]["rect"]
    for x in range(f["x0"] - 1, f["x1"] + 2):
        for z in range(f["z"] - 1, f["z"] + 5):
            assert not (x0 <= x <= x1 and z0 <= z <= z1), (x, z)
    for d in DOC["dungeons"]:
        if d["id"] == "ash_bell":
            continue
        o = RIP[d["id"]]["frame"]
        assert f["x0"] > o["x1"] + 4 or f["x1"] < o["x0"] - 4 or abs(f["z"] - o["z"]) > 6, d["id"]
    cx, cy, cz = RIP[AB["id"]]["click"]
    assert cz == f["z"] + 1 and cy == f["y"] and cx == (f["x0"] + f["x1"]) // 2
    assert RIP[AB["id"]]["outside"][2] - 0.5 > cz + 1.5


def test_the_rip_is_on_the_heightmaps_ground_and_not_in_water():
    try:
        import ground as GR
        g = GR.load()
    except Exception as e:  # noqa: BLE001  (no heightmap in this checkout)
        pytest.skip("no heightmap: %s" % e)
    f = RIP[AB["id"]]["frame"]
    assert {g(x, z) + 1 for x in range(f["x0"], f["x1"] + 1) for z in (f["z"], f["z"] + 1)} == {f["y"]}
    ox, oy, oz, _ = RIP[AB["id"]]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy
    sea = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]
    assert f["y"] - 1 > sea
    import route1_old_mine as MINE
    assert D.rip_restore_measured(RIP[AB["id"]], g, MINE.build(g)) == RIP[AB["id"]]["restore"]
