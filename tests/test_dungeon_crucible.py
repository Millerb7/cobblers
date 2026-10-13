"""The Crucible (data/dungeons.json `crucible`): a forge under the Nether in the basalt delta theme, authored as a TEST
dungeon on the old mine's trail (NEW-CRUCIBLE, 2026-10-11; data/dungeon_prize_roster.json `crucible`, NETHER_ENCOUNTERS.md
3.2, docs/mechanics/DUNGEON_PASS2.md "Overnight 2026-10-11").

The author's own tests (the independent audit is another agent's). What they hold the record to:

  shape     every room type the owner named (maze, puzzle, parkour, resources, nest, habitat, stand, mini-boss) and at
            least three of ours; connectors at most 40 long and at least 7 wide; most rooms not boxes; the route turns
            (doors in four walls), doubles back (rooms entered by their east wall) and drops (a door 18 up, floors 20 apart);
  length    tools/dungeon_clock.py's required time on the MAIN route about 31 minutes at band 1 (forks at their slowest
            non-optional route, the wing never), the record's clock the tool's plus the set piece's 25 s, every band under
            D17's hour, no lockout of its own;
  pacing    no two fight rooms back to back on any route in any variant; the safe room 0.55-0.8 of the paid run; the
            collapse the room before the boss;
  choices   two forks out of crossroads, one three ways, distinct looks and signs, the routes asking different things; a
            wing of four rooms (a hard parkour guarding the prize habitat at its dead end) the clock never pays, down under
            the main route; two parkours; the bank vault inside KIT3's budget; three secrets with relics; a shortcut; four
            variants; three of the six optional rooms, all off the route;
  prize     the roster's pools (legendary at band 6 only, model-gated until the ATM subset is delivered) and the test
            dungeon's own rare pools at bands 1-3, by the jar's labels;
  variety   a trainer's team_pool_by_band, the mini-boss's species_pool_by_band and the boss's teams_alt_by_band;
  species   every species in the 1.8.0 jar, no legendary/mythical/Ultra Beast/paradox in a fight, NO Fire type in any fight
            (NETHER_ENCOUNTERS.md 3.2), Heatran nowhere in the record (its home is its own boss room);
  rip       on the heightmap's ground, dry, clear of the old mine and of the other test rips, siting_pending recorded.

And a GENERATOR mutation: the basalt delta's tall halls are lit from the floor (theme hull.tall_lights); switching the kit's
floor lights and its dark-cell lighting off, with the data untouched, must leave the Crucible's cells dark and the walk check
must say so.

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
CR = next(d for d in DOC["dungeons"] if d["id"] == "crucible")
OWNER_KINDS = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room"}
FIGHTS = {"stand", "gauntlet", "ambush", "miniboss", "nest", "habitat", "boss_arena"}
CONNECTORS = {"drift", "stairs"}
ENDS = {"entry_room", "exit_room"}
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
SETPIECE_ALLOWANCE_S = 25      # clock_why: one fall onto the collapse's catch floor, priced as the tool prices a fall (15 + 10)


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def slots():
    return [s for s in D.slots(DOC) if s["dungeon"]["id"] == "crucible"]


def slot1():
    return slots()[0]


def records(d=CR):
    return list(R._walk_records(d["rooms"]))


def kinds():
    return [r["kind"] for r in records()]


def variant_records():
    out = []
    for s in R.variant_slots(DOC, CR, slots()):
        out += records(R.resolve(DOC, CR, s))
    return out


def main_layout(slot=None):
    return [r for r in R.layout(DOC, CR, slot or slot1()) if r["route"] == "main"]


def by_id(rid):
    return next(r for r in records() if r["id"] == rid)


# ------------------------------------------------------------------------------------------------- shape


def test_every_room_type_the_owner_named_is_there_and_three_of_ours():
    k = set(kinds())
    assert OWNER_KINDS <= k, OWNER_KINDS - k
    assert len((OURS & k) - {"ambush"}) >= 3, OURS & k
    top = [r["kind"] for r in CR["rooms"]]
    assert top[0] == "entry_room" and top[-2:] == ["boss_arena", "exit_room"]
    assert CR["theme"] == "basalt_deltas" and CR["test"] is True and RIP[CR["id"]]["test"] is True
    assert CR["gate_flag"] == "cobblers:flag/champion_cleared" and CR["first_band"] == 6, "the roster's gate and floor (the draw, 2026-10-13)"


def test_fewer_richer_rooms_short_wide_connectors_and_mostly_not_boxes():
    rs = [r for r in records() if r["kind"] not in EXTRA_KINDS]
    assert len(rs) <= 32, len(rs)
    assert len(main_layout()) <= 18, [r["id"] for r in main_layout()]
    lay = R.layout(DOC, CR, slot1())
    for r in lay:
        if r["kind"] in CONNECTORS:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
        elif r["kind"] not in ENDS:
            assert 15 <= r["width"] <= 62, (r["id"], r["width"])
    shaped = [r for r in lay if r["kind"] not in CONNECTORS | ENDS | R.BOX_ONLY_KINDS | EXTRA_KINDS]
    assert sum(r["shape"] != "box" for r in shaped) >= len(shaped) * 0.6, [(r["id"], r["shape"]) for r in shaped]


def test_the_route_turns_doubles_back_and_drops():
    lay = R.layout(DOC, CR, slot1())
    sides = {x["side"] for r in lay for x in R.room_doors(r)}
    assert sides == {"north", "south", "east", "west"}
    assert sum(r["in_side"] == "east" for r in main_layout()) >= 2, "the slag run and the chain way are walked back west"
    assert max(x["y"] - r["floor_in"] for r in lay for x in R.room_doors(r)) >= 16
    floors = {r["floor_in"] for r in lay}
    assert max(floors) - min(floors) >= 20, floors
    # the walk back west runs UNDER the anvil court: two main rooms share x and z, one above the other
    main = main_layout()
    assert any(a["xa"] <= b["xb"] and b["xa"] <= a["xb"] and a["za"] <= b["zb"] and b["za"] <= a["zb"]
               and a["floor_in"] - b["floor_in"] >= 12 for a in main for b in main)


# ------------------------------------------------------------------------------------------------- length


def _walks():
    return [C.walked(DOC, CR, s)[0] for s in R.variant_slots(DOC, CR, slots())]


def _required_by_band(walks):
    out = {}
    for b in DOC["engine"]["bands"]:
        out[b["band"]] = max(sum(C.required(DOC, CR, b["band"], C.clock_rooms(DOC, CR, b["band"], w)).values()) for w in walks)
    return out


def test_about_31_minutes_required_at_band_1_and_the_clock_is_the_tools_plus_the_set_piece_allowance():
    req = _required_by_band(_walks())
    assert 29 * 60 <= req[1] <= 34 * 60, req[1] / 60
    slack = DOC["engine"]["clock"]["slack_factor"]
    own = CR["clock_s_by_band"]
    for b, s in req.items():
        assert own[str(b)] == math.ceil((s + SETPIECE_ALLOWANCE_S) * slack / 60) * 60, (b, own[str(b)], s)
        assert own[str(b)] <= 3600, "every band under D17's hour"
    assert 38 * 60 <= own["1"] <= 42 * 60
    assert "lockout_ticks" not in CR and "lockout_why" not in CR
    assert str(SETPIECE_ALLOWANCE_S) + " s" in CR["clock_why"]
    assert C.clock_problems(DOC, CR) == []


# ------------------------------------------------------------------------------------------------- pacing


def _neighbours(lay):
    by_i = {r["i"]: r for r in lay}
    for r in lay:
        for x in R.room_doors(r):
            if x["dir"] == "out" and not x.get("shortcut"):
                yield r, by_i[x["to"]]


def test_no_two_fights_back_to_back_on_any_route_in_any_variant():
    for s in R.variant_slots(DOC, CR, slots()):
        for a, b in _neighbours(R.layout(DOC, CR, s)):
            assert not (a["kind"] in FIGHTS and b["kind"] in FIGHTS), (s["k"], a["id"], b["id"])


def test_the_safe_room_meets_the_second_fork_late_and_the_collapse_is_before_the_boss():
    rooms = C.walked(DOC, CR, slot1())[0]
    paid = sorted(C.clock_rooms(DOC, CR, 1, rooms), key=lambda r: [x["id"] for x in rooms].index(r["id"]))
    cost = [sum(C.required(DOC, {}, 1, [r]).values()) for r in paid]
    total = sum(cost) + C.required(DOC, CR, 1, [])["boss"]
    at = {r["id"]: sum(cost[:k]) / total for k, r in enumerate(paid)}
    safe = next(r for r in records() if r["kind"] == "safe_room")
    assert safe["params"].get("healer") is True
    assert 0.55 <= at[safe["id"]] <= 0.8, at[safe["id"]]
    main = [r for r in CR["rooms"] if r["kind"] not in ("fork", "side")]
    i = [r["kind"] for r in main].index("boss_arena")
    sp = main[i - 1]
    assert sp["kind"] == "setpiece" and sp["params"]["piece"] == "collapse"
    assert kinds().count("setpiece") == 1


# ------------------------------------------------------------------------------------------------- choices


def _forks():
    top = CR["rooms"]
    return [(top[k - 1], r) for k, r in enumerate(top) if r["kind"] == "fork"]


def test_two_forks_you_can_see_each_out_of_a_crossroads_one_of_them_three_ways():
    forks = _forks()
    assert len(forks) == 2 and all(h["kind"] == "crossroads" for h, _f in forks)
    assert sorted(len(f["routes"]) for _h, f in forks) == [2, 3]
    looks = set(R.load_themes()["themes"]["basalt_deltas"]["crossroads"]["looks"])
    for _h, f in forks:
        ls = [rt["look"] for rt in f["routes"]]
        assert len(set(ls)) == len(ls) and set(ls) <= looks, ls
        assert all(rt.get("sign") for rt in f["routes"]), f["id"]
        assert not any(rt.get("optional") for rt in f["routes"])
    for s in R.variant_slots(DOC, CR, slots()):
        lay = R.layout(DOC, CR, s)
        ids = {r["id"]: r for r in lay}
        for h, f in forks:
            host = ids[h["id"]]
            exits = [x for x in R.room_doors(host) if x["dir"] == "out" and not x.get("shortcut")]
            assert len(exits) == len(f["routes"]), (s["k"], h["id"])
            for i, a in enumerate(exits):
                for b in exits[i + 1:]:
                    assert a["side"] != b["side"] or abs(a["c"] - b["c"]) >= 10, (s["k"], h["id"])
            join = next(r for r in lay if r["route"] == "main" and r["i"] > host["i"]
                        and any(x.get("join_of") is not None for x in R.room_doors(r)))
            ends = {lay[x["to"]]["route"] for x in R.room_doors(join) if x["dir"] == "in"}
            assert ends == {"%s/%s" % (f["id"], rt["id"]) for rt in f["routes"]}, (s["k"], ends)


def _route_kinds(f):
    return {rt["id"]: {r["kind"] for r in rt["rooms"]} for rt in f["routes"]}


def test_the_routes_ask_different_things_and_the_clock_pays_the_slow_one():
    three = next(f for _h, f in _forks() if len(f["routes"]) == 3)
    k3 = _route_kinds(three)
    assert {frozenset(v - CONNECTORS) for v in k3.values()} == {
        frozenset({"collapse_bridge"}), frozenset({"dark_room"}), frozenset({"puzzle"})}, k3
    two = next(f for _h, f in _forks() if len(f["routes"]) == 2)
    k2 = _route_kinds(two)
    assert {frozenset(v - CONNECTORS) for v in k2.values()} == {frozenset({"gauntlet"}), frozenset({"miniboss"})}, k2
    rooms = C.walked(DOC, CR, slot1())[0]
    walk = {rt["id"]: sum(r["walk"] for r in rooms if r["route"] == "%s/%s" % (three["id"], rt["id"])) for rt in three["routes"]}
    danger = next(rt["id"] for rt in three["routes"] if "collapse_bridge" in k3[rt["id"]])
    assert walk[danger] == min(walk.values()), walk
    paid = {r["id"] for r in C.clock_rooms(DOC, CR, 1, rooms)}
    puzzle = next(rt for rt in three["routes"] if "puzzle" in k3[rt["id"]])
    mill = next(rt for rt in two["routes"] if "gauntlet" in k2[rt["id"]])
    assert {r["id"] for r in puzzle["rooms"]} <= paid and {r["id"] for r in mill["rooms"]} <= paid


def _wing():
    sides = [r for r in CR["rooms"] if r["kind"] == "side" and not any(x["kind"] in EXTRA_KINDS for x in r["rooms"])]
    assert len(sides) == 1
    return sides[0]


def test_the_wing_is_four_rooms_a_hard_parkour_a_secret_and_the_prize_at_its_dead_end_never_on_the_clock():
    w = _wing()
    ks = [r["kind"] for r in w["rooms"]]
    assert len(ks) == 4 and ks[0] not in R.BOX_ONLY_KINDS
    assert any(s["type"] in ("cracked", "balcony") for r in w["rooms"] for s in r.get("secrets") or [])
    last = w["rooms"][-1]
    assert last["kind"] == "habitat" and last["params"].get("prize") and last.get("gate") == "open"
    assert w["rooms"][-2]["kind"] == "parkour" and w["rooms"][-2]["params"].get("hard") is True
    wing_ids = {r["id"] for r in w["rooms"]}
    for s in R.variant_slots(DOC, CR, slots()):
        lay = R.layout(DOC, CR, s)
        hab = next(r for r in lay if r["id"] == last["id"])
        assert hab["last"] and hab["route"] == w["id"]
        assert not [x for x in R.room_doors(hab) if x["dir"] == "out"]
        for b in DOC["engine"]["bands"]:
            paid = {r["id"] for r in C.clock_rooms(DOC, CR, b["band"], C.walked(DOC, CR, s)[0])}
            assert not paid & wing_ids, (s["k"], b["band"], paid & wing_ids)
        boss = next(r for r in lay if r["kind"] == "boss_arena")
        assert hab["floor_in"] < boss["floor_in"]


def test_two_parkours_the_main_one_six_sections_with_its_fork_the_wings_hard_with_none():
    import dungeon_parkour as P
    main = next(r for r in records() if r["kind"] == "parkour" and not r["params"].get("hard"))
    hard = next(r for r in records() if r["kind"] == "parkour" and r["params"].get("hard"))
    assert main["params"]["sections"] == 6 and main["width"] == 25 and main["length"] >= 30 * 6 - 10 + 2
    assert main["id"] in {r["id"] for r in CR["rooms"]}, "the long one is on the main route"
    assert hard["params"]["sections"] >= 4 and hard["id"] in {r["id"] for r in _wing()["rooms"]}
    for s in R.variant_slots(DOC, CR, slots()):
        dd = R.resolve(DOC, CR, s)
        bs = {b.room["id"]: b for b in R.slot_build(DOC, CR, s)}
        _route, ledges, _lv, fork_i = P.plan_route(dd, bs[main["id"]].room)
        assert len(ledges) == 7 and fork_i is not None, (s["k"], len(ledges), fork_i)
        route, ledges, _lv, fork_i = P.plan_route(dd, bs[hard["id"]].room)
        assert len(ledges) == hard["params"]["sections"] + 1 and fork_i is None, (s["k"], len(ledges))
        assert sum(1 for h in route.hops if h["n"] == P.FLAT_MAX) >= 4, s["k"]


def test_three_secrets_two_cracked_one_balcony_each_with_a_relic_and_its_lore():
    found = [(r, s) for r in records() for s in r.get("secrets") or []]
    assert sorted(s["type"] for _r, s in found) == ["balcony", "cracked", "cracked"]
    relics = []
    for r, _s in found:
        p = r["params"]
        assert len(r["secrets"]) == 1
        assert re.fullmatch(r"[a-z0-9_]+", p["relic"]) and p["relic"].startswith("cr_")
        assert p["lore"] and len(p["lore"]) <= 160 and all(32 <= ord(c) < 127 for c in p["lore"])
        assert len(p.get("relic_name", "")) <= 32
        relics.append(p["relic"])
    assert len(set(relics)) == len(relics)
    assert not [r["id"] for r in records() if "relic" in r.get("params", {}) and not r.get("secrets")]
    for b in R.slot_build(DOC, CR, slot1()):
        if b.room.get("secrets"):
            assert b.anchors.get("secret"), b.room["id"]
    assert R.load_themes()["themes"]["basalt_deltas"]["shapes"]["secret_block"] in set(R.pick_blocks(CR))


def test_the_shortcut_opens_from_the_bellows_hall_back_into_the_slag_run():
    far = [r for r in records() if r.get("shortcuts")]
    assert len(far) == 1 and len(far[0]["shortcuts"]) == 1
    for s in R.variant_slots(DOC, CR, slots()):
        lay = R.layout(DOC, CR, s)
        ids = {r["id"]: r for r in lay}
        f = ids[far[0]["id"]]
        near = ids[far[0]["shortcuts"][0]["to"]]
        assert near["i"] < f["i"] and near["route"] == f["route"] == "main"
        df, dn = f["shortcut_doors"][0], near["shortcut_doors"][0]
        assert df["y"] == dn["y"] and df["c"] == dn["c"]
        assert not f.get("layout_errors")


def test_four_distinct_variants_one_per_slot_each_built_differently():
    vs = CR["variants"]
    assert len(vs) == 4 and len({v["id"] for v in vs}) == 4
    assert any(v.get("mirror") for v in vs) and any(v.get("seed") for v in vs)
    assert any(v.get("swap") for v in vs) and any(v.get("order") for v in vs)
    assert [R.variant_of(DOC, CR, s)["id"] for s in slots()] == [v["id"] for v in vs]
    shapes = []
    for s in slots():
        lay = R.layout(DOC, CR, s)
        shapes.append(tuple((r["id"], r["xa"] - s["x0"], r["za"] - s["z0"], r["shape"], r["kind"]) for r in lay))
    assert len(set(shapes)) == 4
    d = next(v for v in vs if v.get("order"))
    top = [r["id"] for r in CR["rooms"]]
    assert sorted(d["order"]) == sorted(top) and d["order"] != top
    assert d["order"][0] == top[0] and d["order"][-1] == top[-1]


def test_three_optional_rooms_off_the_route_and_never_paid():
    want = {"bank_vault", "egg_room", "fossil_chamber"}
    rooms = C.walked(DOC, CR)[0]
    paid = {r["id"] for b in DOC["engine"]["bands"] for r in C.clock_rooms(DOC, CR, b["band"], rooms)}
    for s in slots():
        lay = R.layout(DOC, CR, s)
        mine = [r for r in lay if r["kind"] in EXTRA_KINDS]
        assert sorted(r["kind"] for r in mine) == sorted(want), s["g"]
        for r in mine:
            assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open", (s["g"], r["id"])
            assert r["id"] not in paid


def test_the_bank_vault_is_inside_the_budget_and_its_clue_rooms_come_before_it():
    import dungeon_greed as DG
    table = DG.load()
    assert not [x for x in DG.vault_over(DOC, table) if x[0] == "crucible"]
    vault = next(r for r in records() if r["kind"] == "bank_vault")
    order = [r["id"] for r in records()]
    for c in vault["params"]["clue_rooms"]:
        assert order.index(c) < order.index(vault["id"]), c


# ------------------------------------------------------------------------------------------------- the prize


@pytest.fixture(scope="module")
def jar():
    import dungeon_prize as PZ
    labels = PZ.jar_labels()
    if labels is None:
        pytest.skip("no Cobblemon 1.8 jar")
    return labels


def _prize_room():
    return _wing()["rooms"][-1]


def test_the_prize_is_the_rosters_and_rare_only_before_the_beast_ball_stage(jar):
    import dungeon_prize as PZ
    room = _prize_room()
    pz = room["params"]["prize"]
    assert pz["roster"] == "crucible" and "species" not in room["params"]
    lf = DOC["engine"]["prize"]["legendary_from_band"]
    assert sorted(int(k) for k in pz["rare_pool_by_band"]) == list(range(1, lf))
    for pool in pz["rare_pool_by_band"].values():
        for sp in pool:
            assert not jar[sp] & {"legendary", "mythical", "ultra_beast", "paradox"}, sp
    # no legendary of the room's own: the legendary pool is exactly the roster's (band 6)
    assert not pz.get("legendary_by_band") and not pz.get("legendary_pool_by_band")
    entry = PZ.roster_entry("crucible")
    # Iron Hands (re-homed from the cut Zero Dig) and Heatran (the owner's fallback for its boss stage), both 2026-10-12,
    # are the pool's species that are not model-gated
    assert entry["legendary_pool_by_band"] == {"6": ["stakataka", "gougingfire", "ironhands", "heatran"]}
    assert PZ.room_problems(DOC, CR, room) == []
    ch = [PZ.chance(DOC, room, b) for b in range(1, 7)]
    assert ch == sorted(ch) and 0 < ch[0] and ch[-1] < 100, ch


def test_the_band_6_prize_waits_for_the_models_and_then_is_the_rosters_pair():
    import dungeon_prize as PZ
    room = _prize_room()
    doc = copy.deepcopy(DOC)
    gated = [PZ.model_gated(doc, sp) for sp in ("stakataka", "gougingfire")]
    if doc["engine"]["prize"].get("models_delivered"):
        pytest.skip("the ATM subset is delivered: the gate no longer applies")
    assert gated == [True, True]
    # before delivery band 6 offers Iron Hands and Heatran (neither gated); bands 4 and 5 have no pool
    assert [PZ.pool_at(doc, room, b) for b in (4, 5, 6)] == [None, None, (["ironhands", "heatran"], True)]
    doc["engine"]["prize"]["models_delivered"] = ["atm_subset"]
    assert PZ.pool_at(doc, room, 6) == (["stakataka", "gougingfire", "ironhands", "heatran"], True)
    assert PZ.pool_at(doc, room, 4) is None and PZ.pool_at(doc, room, 5) is None


def test_the_rare_prize_is_spawned_at_the_lower_cap_and_takes_any_ball():
    import dungeon_prize as PZ
    s = slot1()
    room = next(r for r in R.layout(DOC, CR, s) if r["id"] == _prize_room()["id"])
    fns, _enter, spawns, _pos = PZ.prize_functions(DOC, CR, s, room)
    if not DOC["engine"]["prize"].get("models_delivered"):
        # band 6 spawns Iron Hands, the one non-gated species of the roster pool (2026-10-12); 4 and 5 have none
        assert sorted(spawns) == [1, 2, 3, 6], sorted(spawns)
    for b in (1, 2, 3):
        text = "\n".join(fns["prize/spawn_b%d" % b])
        assert "level=%d no_ai" % DOC["engine"]["bands"][b - 1]["caps"][0] in text, b
        assert text.rstrip().endswith("prize/rare_bind"), b
        assert all(not leg for _sp, _lv, leg in spawns[b])
    if not DOC["engine"]["prize"].get("models_delivered"):
        # band 6's legendary spawns are Iron Hands (a paradox) and Heatran, each binding through prize/bind (2026-10-12)
        assert [(sp, leg) for sp, _lv, leg in spawns[6]] == [("ironhands", True), ("heatran", True)], spawns[6]
        assert "prize/bind" in fns


# ------------------------------------------------------------------------------------------------- the walk


def test_the_crucible_builds_and_walks_with_no_problem_in_every_variant_and_branch():
    assert R.problems(DOC, CR) == []


def test_the_crucible_builds_its_functions_and_its_shell_fits_the_chain():
    s = slot1()
    assert R.chain_problems(DOC, CR, s) == []
    assert 0.3e6 < D.shell_blocks(DOC, s) < 1.2e6


def _tall_rooms():
    t = R.load_themes()["themes"]["basalt_deltas"]["hull"]
    under = t["tall_lights"]["under"]
    return [r["id"] for r in R.layout(DOC, CR, slot1())
            if 15 - t["min_light"] - (r["ceil_y"] - min(r["floor_in"], r["floor_out"])) < under]


def test_the_tall_halls_are_tall():
    assert {"crucible_heart", "gear_pit", "heart_chamber"} <= set(_tall_rooms())


def test_mutating_the_hull_light_generator_off_leaves_cells_dark_and_the_walk_check_says_so(monkeypatch):
    # The basalt delta's own dressing glows (froglight seams, the canopy's lights), so the floor lights and the dark-cell
    # fill alone going leave nothing dark (measured: 0 findings). The kit's three light sources off (the ceiling lattice,
    # the tall halls' floor lights, the dark-cell fill), with the data untouched, must leave the Crucible's cells dark.
    for name in ("hull_lights", "floor_lights", "light_dark_cells"):
        monkeypatch.setattr(R, name, lambda *a, **k: None)
    bad = R.problems(DOC, CR)
    dark = [p for p in bad if "have no light" in p]
    rooms = {p.split(" room ")[1].split(" ")[0] for p in dark}
    assert "tappers_floor" in rooms and len(rooms) >= 10, (sorted(rooms), bad[:5])


# ------------------------------------------------------------------------------------------------- species


@pytest.fixture(scope="module")
def species():
    import battle_sim as B
    try:
        jar_ = B.find_jar()
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar")
    sp, _m, _c = B.load_pack(jar_)
    return sp, B.key


def fight_species():
    """(room, species) for every Pokemon that fights: trainers (every pool team), the mini-boss pool, the nest, the boss."""
    out = []
    for r in variant_records():
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for team in (t.get("team_by_band") or {}).values():
                out += [(r["id"], x) for x in team]
            for pool in (t.get("team_pool_by_band") or {}).values():
                out += [(r["id"], x) for team in pool for x in team]
        if r["kind"] == "nest":
            out += [(r["id"], x) for x in p.get("species", [])]
        out += [(r["id"], x) for x in (p.get("species_by_band") or {}).values()]
        out += [(r["id"], x) for pool in (p.get("species_pool_by_band") or {}).values() for x in pool]
    bo = CR["boss"]
    for crews in list(bo["teams"].values()) + [c for alts in (bo.get("teams_alt_by_band") or {}).values() for c in alts]:
        for crew in crews:
            out += [("boss", x) for x in crew]
    return out


def test_every_species_named_is_in_the_jar(species):
    sp, key = species
    prize = [x for pool in _prize_room()["params"]["prize"]["rare_pool_by_band"].values() for x in pool]
    missing = sorted({x for _r, x in fight_species() if key(x) not in sp} | {x for x in prize if key(x) not in sp})
    assert not missing, missing


def test_no_legendary_and_no_fire_type_fights_anywhere(species):
    sp, key = species
    for where, x in fight_species():
        s = sp[key(x)]
        assert not set(s.get("labels", [])) & {"legendary", "mythical", "ultra_beast", "paradox"}, (where, x)
        assert "fire" not in {str(s.get("primaryType")).lower(), str(s.get("secondaryType")).lower()}, (where, x)
    # Heatran's home is its own boss room (data/dungeon_prize_roster.json heatran), never this record
    assert "heatran" not in {x for _r, x in fight_species()}


def test_variety_rotation_pools_on_a_trainer_the_mini_boss_and_the_boss():
    rs = records()
    trainers = [t for r in rs for t in (r.get("params", {}).get("trainers") or []) if isinstance(t, dict)]
    assert sum(1 for t in trainers if t.get("team_pool_by_band")) >= 2
    mb = next(r for r in rs if r["kind"] == "miniboss")
    assert all(len(v) >= 2 for v in mb["params"]["species_pool_by_band"].values())
    alt = CR["boss"]["teams_alt_by_band"]
    assert set(alt) == {str(b["band"]) for b in D.bands(DOC)}


# ------------------------------------------------------------------------------------------------- params


def test_the_fight_params_follow_the_contract_and_never_pass_the_bands_upper_cap():
    bands = {str(b["band"]): b for b in D.bands(DOC)}
    ends = {c["rooms"][-1]["id"] for c in CR["rooms"] if c.get("kind") == "side" and c.get("rooms")}
    for r in variant_records():
        p = r.get("params", {})
        if r["kind"] in ("stand", "gauntlet", "ambush"):
            assert DF.stand_problems(DOC, r) == [], r["id"]
            assert DF.stand_classes(DOC, CR, r)
            if r["kind"] != "stand":
                tr = p["triggers"]
                assert len(tr) == len(p["trainers"]) and tr == sorted(tr) and all(0 < t < 1 for t in tr)
            assert r["gate"] == "cleared"
        elif r["kind"] == "miniboss":
            assert set(p["species_pool_by_band"]) == set(bands) and p["level_offset"] <= 0 and p.get("catchable") is True
            assert r["gate"] == "cleared"
        elif r["kind"] == "nest":
            assert set(p["count_by_band"]) == set(bands) and p["species"] and p.get("clear") == "pass"
        elif r["kind"] == "habitat":
            assert r["id"] in ends and r["gate"] == "open" and p.get("prize") and "level_by_band" not in p
        elif r["kind"] == "puzzle":
            assert p["variant"] in ("levers", "sequence", "plates") and p["penalty_s"] > 0
        elif r["kind"] == "setpiece":
            assert p["piece"] == "collapse"


def test_the_boss_has_two_stages_a_heal_and_one_ace_last_in_every_crew():
    bo = CR["boss"]
    others = {d["boss"]["name"] for d in DOC["dungeons"] if d["id"] != "crucible"}
    assert bo["name"] not in others
    assert len(bo["stage_level_offsets"]) == 2 and bo["heal_between_stages"] is True and bo["heal_cue"]
    for b in D.bands(DOC):
        for crews in [bo["teams"][str(b["band"])]] + bo["teams_alt_by_band"][str(b["band"])]:
            assert len(crews) == 2
            assert len({c[-1] for c in crews}) == 1, "one ace, sent out last in every stage"
            assert crews[0][-1] == ("tinkatuff" if b["band"] <= 2 else "tinkaton")


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_stands_on_the_trail_clear_of_the_old_mine_and_the_other_rips():
    f = RIP[CR["id"]]["frame"]
    assert 1415 <= (f["x0"] + f["x1"]) // 2 <= 1435, "the launch brief's x slot 1425 (+-10)"
    import json
    mine = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]["route1_old_mine"]
    x0, z0, x1, z1 = mine["plan"]["footprint"]["rect"]
    for x in range(f["x0"] - 1, f["x1"] + 2):
        for z in range(f["z"] - 1, f["z"] + 5):
            assert not (x0 <= x <= x1 and z0 <= z <= z1), (x, z)
    for d in DOC["dungeons"]:
        if d["id"] == "crucible":
            continue
        o = RIP[d["id"]]["frame"]
        assert f["x0"] > o["x1"] + 2 or f["x1"] < o["x0"] - 2 or abs(f["z"] - o["z"]) > 4, d["id"]
        cx, _cy, cz = RIP[d["id"]]["click"]
        mx, _my, mz = RIP[CR["id"]]["click"]
        assert abs(cx - mx) > 4 or abs(cz - mz) > 4, d["id"]
    cx, cy, cz = RIP[CR["id"]]["click"]
    assert cz == f["z"] + 1 and cy == f["y"] and cx == (f["x0"] + f["x1"]) // 2
    _ox, _oy, oz, _yaw = RIP[CR["id"]]["outside"]
    assert oz - 0.5 > cz + 1.5


def test_the_rip_is_on_the_heightmaps_ground_and_not_in_water():
    try:
        import ground as GR
        g = GR.load()
    except Exception as e:  # noqa: BLE001  (no heightmap in this checkout)
        pytest.skip("no heightmap: %s" % e)
    f = RIP[CR["id"]]["frame"]
    feet = {g(x, z) + 1 for x in range(f["x0"], f["x1"] + 1) for z in (f["z"], f["z"] + 1)}
    assert feet == {f["y"]}, feet
    ox, oy, oz, _ = RIP[CR["id"]]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy
    import json
    sea = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]
    assert f["y"] - 1 > sea


def test_the_slots_follow_the_dungeons_index():
    i = [d["id"] for d in DOC["dungeons"]].index("crucible")
    ss = slots()
    per = DOC["engine"]["slots"]["per_dungeon"]
    assert [s["g"] for s in ss] == list(range(i * per + 1, i * per + per + 1))
