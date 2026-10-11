"""The Drowned Reliquary (data/dungeons.json `flooded_ruin`): the third test dungeon, re-authored for pass 2 (DG2-RUIN)
and pass 3 (DG3-RUIN, 2026-10-10, docs/mechanics/DUNGEON_PASS2.md "Pass 3", DUNGEON_ROOMS.md 1b).

The author's own tests (the independent audit is another agent's). What they hold the record to:

  shape     every room type the owner named is present (maze, puzzle, parkour, resources, nest, habitat, stand,
            mini-boss) and at least three of ours; connectors at most 40 long and at least 7 wide; most rooms take a
            non-box outline; the route turns (doors in four walls), doubles back (a room left by its west wall) and drops
            (a landing door, two floor levels);
  length    tools/dungeon_clock.py's required time on the MAIN route about 32 minutes at band 1 (forks at their slowest
            non-optional route, the wing never), the record's clock the tool's plus the set piece's stated allowance,
            every band under D17's hour and no lockout of its own;
  pacing    no two fight rooms back to back on any route; the safe room about two thirds in; the set piece the room
            before the boss;
  choices   (pass 3) two forks you can see, each out of a crossroads with a distinct look per route, one of them three
            ways, the routes asking different things (danger, length, a puzzle); a WING of four rooms (a hard parkour, a
            secret, the prize habitat at its dead end) off the nave; the prize's species per band and its gating; two
            parkours (the main one six sections, the wing's hard); the vault inside KIT3's budget; three secrets (two
            cracked, one balcony) carrying a relic and its lore; a shortcut back toward the entry; four distinct variants;
  walk      the room kit's own checks (tools/dungeon_rooms.py problems(): every variant and branch walked);
  species   every species named, in every variant, is in the Cobblemon 1.8.0 jar; the prize's legendary is a legendary
            or mythical, no Ultra Beast, and nothing else in data/ or DUNGEONS.md 8 uses it;
  params    the wave-2 params contract's fields, in range (levels never above the band's upper cap);
  rip       within 60 blocks of the Night Shift's, on the heightmap's ground, outside the old mine.

And a GENERATOR mutation: the ruin's tall halls are lit from the floor (theme hull.tall_lights, dungeon_rooms
floor_lights / cap_dark_dressing). Switching either off in the code, with the data untouched, must leave cells in the
dark and the walk check must say so.

Not covered: anything in a running Minecraft.
"""
from __future__ import annotations

import copy
import glob
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
RUIN = next(d for d in DOC["dungeons"] if d["id"] == "flooded_ruin")
NS = next(d for d in DOC["dungeons"] if d["id"] == "night_shift")
OWNER_KINDS = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room"}
FIGHTS = {"stand", "gauntlet", "ambush", "miniboss", "nest", "habitat", "boss_arena"}
CONNECTORS = {"drift", "stairs"}
ENDS = {"entry_room", "exit_room"}
SETPIECE_ALLOWANCE_S = 25      # clock_why: one sweep back, priced as the tool prices a fall (15 + 10)


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def slots():
    return [s for s in D.slots(DOC) if s["dungeon"]["id"] == "flooded_ruin"]


def slot1():
    return slots()[0]


def records(d=RUIN):
    return list(R._walk_records(d["rooms"]))


# the six optional kinds of DUNGEON_ROOMS.md 12-13 (PLACE-ROOMS, 2026-10-11): placed after pass 3 on side entries of
# their own; the pass-3 counts and the sealed wing below are about the rest
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}


def pass3_side(r):
    return r["kind"] == "side" and not any(x["kind"] in EXTRA_KINDS for x in r["rooms"])


def kinds():
    return [r["kind"] for r in records()]


def variant_records():
    """Every room record as each slot's variant builds it."""
    out = []
    for s in R.variant_slots(DOC, RUIN, slots()):
        out += records(R.resolve(DOC, RUIN, s))
    return out


def main_layout(slot=None):
    return [r for r in R.layout(DOC, RUIN, slot or slot1()) if r["route"] == "main"]


# ------------------------------------------------------------------------------------------------- shape


def test_every_room_type_the_owner_named_is_there_and_three_of_ours():
    k = set(kinds())
    assert OWNER_KINDS <= k, OWNER_KINDS - k
    assert len((OURS & k) - {"ambush"}) >= 3, OURS & k
    top = [r["kind"] for r in RUIN["rooms"]]
    assert top[0] == "entry_room" and top[-2:] == ["boss_arena", "exit_room"]
    assert RUIN["theme"] == "flooded_ruin" and RUIN["test"] is True and RUIN["rip"]["test"] is True
    assert RUIN["gate_flag"] is None


def test_fewer_richer_rooms_short_wide_connectors_and_mostly_not_boxes():
    rs = [r for r in records() if r["kind"] not in EXTRA_KINDS]
    # pass 3 adds two forks and a wing; the MAIN route stays at most 18 rooms
    assert len(rs) <= 28, len(rs)
    assert len(main_layout()) <= 18, [r["id"] for r in main_layout()]
    conn = [r for r in rs if r["kind"] in CONNECTORS]
    # a fit landing per route that is not the fork's first, the nave (the second fork's join) and the wing's shaft stair
    assert len(conn) <= 5, [r["id"] for r in conn]
    lay = R.layout(DOC, RUIN, slot1())
    for r in lay:
        if r["kind"] in CONNECTORS:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
        elif r["kind"] not in ENDS:
            assert 15 <= r["width"] <= 62, (r["id"], r["width"])
    shaped = [r for r in lay if r["kind"] not in CONNECTORS | ENDS | R.BOX_ONLY_KINDS]
    assert sum(r["shape"] != "box" for r in shaped) >= len(shaped) * 0.7, [(r["id"], r["shape"]) for r in shaped]


def test_the_route_turns_doubles_back_and_drops():
    lay = R.layout(DOC, RUIN, slot1())
    sides = {x["side"] for r in lay for x in R.room_doors(r)}
    assert sides == {"north", "south", "east", "west"}
    # walked back west: a room entered by its east wall
    assert any(r["in_side"] == "east" for r in lay)
    # a drop: a door on a landing well above its room's floor, and the route on two floor levels at least 20 apart
    assert max(x["y"] - r["floor_in"] for r in lay for x in R.room_doors(r)) >= 12
    floors = {r["floor_in"] for r in lay}
    assert max(floors) - min(floors) >= 20, floors
    # the return walk runs beside the rooms it came along: two main rooms share x but not z
    main = main_layout()
    assert any(a["xa"] <= b["xb"] and b["xa"] <= a["xb"] and (a["zb"] < b["za"] or b["zb"] < a["za"])
               and a["floor_in"] == b["floor_in"] for a in main for b in main if a["i"] < b["i"])


# ------------------------------------------------------------------------------------------------- length


def _required_by_band():
    walks = [C.walked(DOC, RUIN, s)[0] for s in R.variant_slots(DOC, RUIN, slots())]
    out = {}
    for b in DOC["engine"]["bands"]:
        out[b["band"]] = max(sum(C.required(DOC, RUIN, b["band"], C.clock_rooms(DOC, RUIN, b["band"], w)).values())
                             for w in walks)
    return out


def test_about_32_minutes_required_at_band_1_and_the_clock_is_the_tools_plus_the_set_piece_allowance():
    req = _required_by_band()
    assert 29 * 60 <= req[1] <= 34 * 60, req[1] / 60
    slack = DOC["engine"]["clock"]["slack_factor"]
    own = RUIN["clock_s_by_band"]
    for b, s in req.items():
        assert own[str(b)] == math.ceil((s + SETPIECE_ALLOWANCE_S) * slack / 60) * 60, (b, own[str(b)])
        assert own[str(b)] <= 3600, "every band under D17's hour"
    assert 38 * 60 <= own["1"] <= 42 * 60
    assert "lockout_ticks" not in RUIN and "lockout_why" not in RUIN
    assert str(SETPIECE_ALLOWANCE_S) + " s" in RUIN["clock_why"]
    assert C.clock_problems(DOC, RUIN) == []


# ------------------------------------------------------------------------------------------------- pacing


def _neighbours(lay):
    by_i = {r["i"]: r for r in lay}
    for r in lay:
        for x in R.room_doors(r):
            if x["dir"] == "out" and not x.get("shortcut"):
                yield r, by_i[x["to"]]


def test_no_two_fights_back_to_back_on_any_route_in_any_variant():
    for s in R.variant_slots(DOC, RUIN, slots()):
        for a, b in _neighbours(R.layout(DOC, RUIN, s)):
            assert not (a["kind"] in FIGHTS and b["kind"] in FIGHTS), (s["k"], a["id"], b["id"])


def test_the_safe_room_two_thirds_in_and_the_set_piece_before_the_boss():
    rooms = C.walked(DOC, RUIN, slot1())[0]
    paid = sorted(C.clock_rooms(DOC, RUIN, 1, rooms), key=lambda r: [x["id"] for x in rooms].index(r["id"]))
    cost = [sum(C.required(DOC, {}, 1, [r]).values()) for r in paid]
    total = sum(cost) + C.required(DOC, RUIN, 1, [])["boss"]
    at = {r["id"]: sum(cost[:k]) / total for k, r in enumerate(paid)}
    safe = next(r["id"] for r in records() if r["kind"] == "safe_room")
    assert 0.55 <= at[safe] <= 0.8, at[safe]
    main = [r for r in RUIN["rooms"] if r["kind"] not in ("fork", "side")]
    i = [r["kind"] for r in main].index("boss_arena")
    sp = main[i - 1]
    assert sp["kind"] == "setpiece" and sp["params"]["piece"] == "flood"
    assert [r["kind"] for r in records()].count("setpiece") == 1


# ------------------------------------------------------------------------------------------------- choices


def _forks():
    top = RUIN["rooms"]
    return [(top[k - 1], r) for k, r in enumerate(top) if r["kind"] == "fork"]


def test_two_forks_you_can_see_each_out_of_a_crossroads_one_of_them_three_ways():
    forks = _forks()
    assert len(forks) == 2 and all(h["kind"] == "crossroads" for h, _f in forks)
    assert sorted(len(f["routes"]) for _h, f in forks) == [2, 3]
    looks = set(R.load_themes()["themes"]["flooded_ruin"]["crossroads"]["looks"])
    for _h, f in forks:
        ls = [rt["look"] for rt in f["routes"]]
        assert len(set(ls)) == len(ls) and set(ls) <= looks, ls
        assert all(rt.get("sign") for rt in f["routes"]), f["id"]
        assert not any(rt.get("optional") for rt in f["routes"]), "both forks are ways on; the wing is the optional part"
    for s in R.variant_slots(DOC, RUIN, slots()):
        lay = R.layout(DOC, RUIN, s)
        by_id = {r["id"]: r for r in lay}
        for h, f in forks:
            host = by_id[h["id"]]
            exits = [x for x in R.room_doors(host) if x["dir"] == "out" and not x.get("shortcut")]
            assert len(exits) == len(f["routes"]), (s["k"], h["id"])
            # every way leaves the host by its own door, the doors well apart: no two near-identical doors on one wall
            for i, a in enumerate(exits):
                for b in exits[i + 1:]:
                    assert a["side"] != b["side"] or abs(a["c"] - b["c"]) >= 10, (s["k"], h["id"])
            # and every route rejoins at the one room after the fork
            join = next(r for r in lay if r["route"] == "main" and r["i"] > host["i"]
                        and any(x.get("join_of") is not None for x in R.room_doors(r)))
            ends = {lay[x["to"]]["route"] for x in R.room_doors(join) if x["dir"] == "in"}
            assert ends == {"%s/%s" % (f["id"], rt["id"]) for rt in f["routes"]}, (s["k"], ends)
    for b in R.slot_build(DOC, RUIN, slot1()):
        if b.room["kind"] == "crossroads":
            assert b.anchors.get("hub"), b.room["id"]   # the sight check from it is problems()'s (the walk test below)


def _route_kinds(f):
    return {rt["id"]: {r["kind"] for r in rt["rooms"]} for rt in f["routes"]}


def test_the_routes_ask_different_things_danger_length_and_a_puzzle():
    three = next(f for _h, f in _forks() if len(f["routes"]) == 3)
    k3 = _route_kinds(three)
    assert {frozenset(v - CONNECTORS) for v in k3.values()} == {
        frozenset({"collapse_bridge"}), frozenset({"dark_room"}), frozenset({"puzzle"})}, k3
    two = next(f for _h, f in _forks() if len(f["routes"]) == 2)
    k2 = _route_kinds(two)
    assert {frozenset(v - CONNECTORS) for v in k2.values()} == {frozenset({"maze"}), frozenset({"miniboss"})}, k2
    # the danger way is the shortest walk of the three, the dark one winds, the puzzle way costs the most time at band 1
    rooms = C.walked(DOC, RUIN, slot1())[0]
    walk = {rt["id"]: sum(r["walk"] for r in rooms if r["route"] == "%s/%s" % (three["id"], rt["id"])) for rt in three["routes"]}
    danger = next(rt["id"] for rt in three["routes"] if "collapse_bridge" in k3[rt["id"]])
    assert walk[danger] == min(walk.values()), walk
    paid = {r["id"] for r in C.clock_rooms(DOC, RUIN, 1, rooms)}
    puzzle = next(rt for rt in three["routes"] if "puzzle" in k3[rt["id"]])
    assert {r["id"] for r in puzzle["rooms"]} <= paid, "the clock pays the slowest way of the three: the puzzle's"


def _wing():
    sides = [r for r in RUIN["rooms"] if pass3_side(r)]
    assert len(sides) == 1
    return sides[0]


def test_the_wing_is_four_rooms_a_hard_parkour_a_secret_and_the_prize_at_its_dead_end_never_on_the_clock():
    w = _wing()
    kinds_ = [r["kind"] for r in w["rooms"]]
    assert len(kinds_) == 4 and kinds_[0] not in R.BOX_ONLY_KINDS
    assert any(r["kind"] == "parkour" and r["params"].get("hard") is True for r in w["rooms"])
    assert any(s["type"] in ("cracked", "balcony") for r in w["rooms"] for s in r.get("secrets") or [])
    last = w["rooms"][-1]
    assert last["kind"] == "habitat" and last["params"].get("prize") and last.get("gate") == "open"
    # the hard parkour guards the prize: it is the room before it
    assert w["rooms"][-2]["kind"] == "parkour"
    for s in R.variant_slots(DOC, RUIN, slots()):
        lay = R.layout(DOC, RUIN, s)
        hab = next(r for r in lay if r["id"] == last["id"])
        assert hab["last"] and hab["route"] == w["id"]
        assert not [x for x in R.room_doors(hab) if x["dir"] == "out"]
        wing_ids = {r["id"] for r in w["rooms"]}
        for b in DOC["engine"]["bands"]:
            paid = {r["id"] for r in C.clock_rooms(DOC, RUIN, b["band"], C.walked(DOC, RUIN, s)[0])}
            assert not paid & wing_ids, (s["k"], b["band"], paid & wing_ids)
        # the wing goes DOWN under the main route: the sealed deep (the stair is the wing's own, its shaft beside the hall)
        assert hab["floor_in"] < min(r["floor_in"] for r in lay if r["route"] == "main" and r["kind"] == "boss_arena")


@pytest.fixture(scope="module")
def jar():
    import dungeon_prize as PZ
    labels = PZ.jar_labels()
    if labels is None:
        pytest.skip("no Cobblemon 1.8 jar")
    return labels


def test_the_prize_is_a_rare_dragon_before_the_beast_ball_stage_and_regidrago_from_it(jar):
    import dungeon_prize as PZ
    room = _wing()["rooms"][-1]
    pz = room["params"]["prize"]
    lf = DOC["engine"]["prize"]["legendary_from_band"]
    assert sorted(int(k) for k in pz["rare_by_band"]) == list(range(1, lf))
    assert sorted(int(k) for k in pz["legendary_by_band"]) == list(range(lf, 7))
    for sp in pz["rare_by_band"].values():
        assert not jar[sp] & {"legendary", "mythical", "ultra_beast"}, sp
    for sp in pz["legendary_by_band"].values():
        assert jar[sp] & {"legendary", "mythical"} and "ultra_beast" not in jar[sp], sp   # no Ultra Beast prize yet (KIT3)
    assert set(pz["legendary_by_band"].values()) == {"regidrago"}
    assert PZ.room_problems(DOC, RUIN, room) == []
    # no resident: a legendary standing there every run would be no hidden prize
    assert "species" not in room["params"]
    # the chance rises with the band and is never certain
    ch = [PZ.chance(DOC, room, b) for b in range(1, 7)]
    assert ch == sorted(ch) and 0 < ch[0] and ch[-1] < 100, ch
    # the rare prizes are no set piece and no dungeon's other Pokemon (they may spawn wild in the world, data/spawns.json)
    others = [r for r in variant_records() if r["id"] != room["id"]]
    named = {x for _r, x in named_species() if _r != room["id"]} | {x for crews in RUIN["boss"]["teams"].values() for c in crews for x in c}
    for sp in pz["rare_by_band"].values():
        assert sp not in named, sp
        word = re.compile(r"(?<![a-z])%s(?![a-z])" % sp)
        for f in glob.glob(str(ROOT / "data" / "*.json")):
            if Path(f).name in ("spawns.json", "encounter_design.json", "spawn_blocks.json", "dungeons.json"):
                continue
            assert not word.search(Path(f).read_text(encoding="utf-8").lower()), (sp, Path(f).name)
    assert others


def test_the_prize_is_rolled_spawned_at_the_lower_cap_and_only_its_legendary_takes_the_beast_ball():
    import key_ball as KB
    s = slot1()
    files = D.build(DOC)
    room = _wing()["rooms"][-1]
    base = "data/cobblers/function/dungeons/room/flooded_ruin/%s/s%d/" % (room["id"], s["g"])
    lf = DOC["engine"]["prize"]["legendary_from_band"]
    for b in DOC["engine"]["bands"]:
        sp = files[base + "prize/spawn_b%d.mcfunction" % b["band"]]
        assert "level=%d no_ai" % b["caps"][0] in sp, b
        assert sp.rstrip().endswith("prize/bind" if b["band"] >= lf else "prize/rare_bind"), b
    tag = "tag @s add %s" % KB.boss_tag()
    assert tag in files[base + "prize/bind.mcfunction"].split("\n")
    assert tag not in files[base + "prize/rare_bind.mcfunction"].split("\n")
    start = files["data/cobblers/function/dungeons/slot/s%d/start.mcfunction" % s["g"]]
    assert start.count("random value 1..100") >= 6 and "A diver swears" in start
    assert KB.boss_problems(KB.load()) == []


def test_two_parkours_the_main_one_six_sections_with_its_fork_the_wings_hard_with_none():
    import dungeon_parkour as P
    main = next(r for r in records() if r["kind"] == "parkour" and not r["params"].get("hard"))
    hard = next(r for r in records() if r["kind"] == "parkour" and r["params"].get("hard"))
    assert main["params"]["sections"] == 6 and main["width"] == 25 and main["length"] >= 30 * 6 - 10 + 2
    assert hard["params"]["sections"] >= 4 and hard["id"] in {r["id"] for r in _wing()["rooms"]}
    assert main["id"] in {r["id"] for r in RUIN["rooms"]}, "the long one is on the main route"
    for s in R.variant_slots(DOC, RUIN, slots()):
        dd = R.resolve(DOC, RUIN, s)
        bs = {b.room["id"]: b for b in R.slot_build(DOC, RUIN, s)}
        route, ledges, _lv, fork_i = P.plan_route(dd, bs[main["id"]].room)
        assert len(ledges) == 7 and fork_i is not None, (s["k"], len(ledges), fork_i)
        route, ledges, _lv, fork_i = P.plan_route(dd, bs[hard["id"]].room)
        assert len(ledges) == hard["params"]["sections"] + 1 and fork_i is None, (s["k"], len(ledges))
        assert sum(1 for h in route.hops if h["n"] == P.FLAT_MAX) >= 4, s["k"]


def test_the_vault_is_inside_the_budget_at_every_band_and_a_dearer_chest_is_not():
    import dungeon_greed as DG
    table = DG.load()
    assert not [x for x in DG.vault_over(DOC, table) if x[0] == "flooded_ruin"]
    budget = DG.vault_budget(DOC, table)
    well = next(r for r in records() if r["kind"] == "vault")
    for b in range(1, 7):
        _k, spec = __import__("dungeon_puzzles").loot_for(well["params"], DOC["engine"]["bands"], b)
        v = DG.chest_cp(table, spec)
        assert v is not None and v <= 0.9 * budget[b] // well["params"]["chests"], (b, v)   # a margin for the budget moving
    # mutation: a revive at band 1 (500 cp) is named, and refused once enforced
    doc = copy.deepcopy(DOC)
    d = next(x for x in doc["dungeons"] if x["id"] == "flooded_ruin")
    next(r for r in R._walk_records(d["rooms"]) if r["kind"] == "vault")["params"]["loot_by_band"]["1"] = [{"item": "cobblemon:revive", "count": 1}]
    table["vault_budget"]["enforce"] = True
    assert any("flooded_ruin vault offering_well band 1" in p for p in DG.vault_problems(doc, table))


def test_three_secrets_two_cracked_one_balcony_each_with_a_relic_and_its_lore():
    found = [(r, s) for r in records() for s in r.get("secrets") or []]
    assert sorted(s["type"] for _r, s in found) == ["balcony", "cracked", "cracked"]
    relics = []
    for r, s in found:
        p = r["params"]
        assert len(r["secrets"]) == 1
        assert re.fullmatch(r"[a-z0-9_]+", p["relic"]) and p["relic"].startswith("fr_")
        assert p["lore"] and len(p["lore"]) <= 160 and all(32 <= ord(c) < 127 for c in p["lore"])
        assert len(p.get("relic_name", "")) <= 32
        relics.append(p["relic"])
    assert len(set(relics)) == len(relics)
    assert not [r["id"] for r in records() if "relic" in r.get("params", {}) and not r.get("secrets")]
    for b in R.slot_build(DOC, RUIN, slot1()):
        if b.room.get("secrets"):
            assert b.anchors.get("secret"), b.room["id"]
    assert set(R.pick_blocks(RUIN)) >= {R.load_themes()["themes"]["flooded_ruin"]["shapes"]["secret_block"]}


def test_the_shortcut_opens_back_toward_the_entry_on_one_floor():
    far = [r for r in records() if r.get("shortcuts")]
    assert len(far) == 1 and len(far[0]["shortcuts"]) == 1
    lay = R.layout(DOC, RUIN, slot1())
    by_id = {r["id"]: r for r in lay}
    f = by_id[far[0]["id"]]
    near = by_id[far[0]["shortcuts"][0]["to"]]
    assert near["i"] < f["i"] and near["route"] == f["route"] == "main"
    df, dn = f["shortcut_doors"][0], near["shortcut_doors"][0]
    assert df["y"] == dn["y"] and df["c"] == dn["c"]
    # it skips rooms: between the near room and the far one the route passes at least two others
    assert f["i"] - near["i"] >= 3
    # toward the entry: the near room is the one the entry opens into
    assert near["i"] <= 2, near["id"]
    assert not f.get("layout_errors")
    # opened from the far side only: the far room's own function, and the far room's tick runs it
    fns = D.build(DOC)
    name = "shortcut_%s" % far[0]["shortcuts"][0]["id"]
    assert any(k.endswith("/%s/s%d/%s.mcfunction" % (f["id"], slot1()["g"], name)) for k in fns), name


def test_four_distinct_variants_one_per_slot_each_built_differently():
    vs = RUIN["variants"]
    assert len(vs) == 4 and len({v["id"] for v in vs}) == 4
    assert any(v.get("mirror") for v in vs) and any(v.get("seed") for v in vs)
    assert any(v.get("swap") for v in vs) and any(v.get("order") for v in vs)
    ids = [R.variant_of(DOC, RUIN, s)["id"] for s in slots()]
    assert ids == [v["id"] for v in vs]
    shapes = []
    for s in slots():
        lay = R.layout(DOC, RUIN, s)
        shapes.append(tuple((r["id"], r["xa"] - s["x0"], r["za"] - s["z0"], r["shape"], r["kind"]) for r in lay))
    assert len(set(shapes)) == 4


def test_the_order_variant_still_keeps_fights_apart_and_the_ends_in_place():
    d = next(v for v in RUIN["variants"] if v.get("order"))
    top = [r["id"] for r in RUIN["rooms"]]
    assert sorted(d["order"]) == sorted(top) and d["order"] != top
    assert d["order"][0] == top[0] and d["order"][-1] == top[-1]


# ------------------------------------------------------------------------------------------------- the walk


def test_the_ruin_builds_and_walks_with_no_problem_in_every_variant_and_branch():
    assert R.problems(DOC, RUIN) == []
    assert not [p for p in D.problems(DOC) if "flooded_ruin" in p]


def test_the_ruin_builds_its_functions_and_its_shell_fits_the_chain():
    s = slot1()
    files = D.build(DOC)
    shell = [k for k in files if "/shells/s%d/" % s["g"] in k]
    assert len(shell) == len(records())
    assert R.chain_problems(DOC, RUIN, s) == []
    assert 0.3e6 < D.shell_blocks(DOC, s) < 1.2e6


def _tall_rooms():
    t = R.load_themes()["themes"]["flooded_ruin"]["hull"]
    under = t["tall_lights"]["under"]
    return [r["id"] for r in R.layout(DOC, RUIN, slot1())
            if 15 - t["min_light"] - (r["ceil_y"] - min(r["floor_in"], r["floor_out"])) < under]


def test_the_tall_halls_are_lit_from_the_floor_and_the_ceiling_stays_sparse():
    tall = _tall_rooms()
    assert {"sealed_chamber", "flood_chamber", "guardian", "offering_well"} <= set(tall)
    th = R.load_themes()["themes"]["flooded_ruin"]
    for b in R.slot_build(DOC, RUIN, slot1()):
        if b.room["id"] not in tall or b.room["pit"] or R.flags_of(b.room["kind"])["dark"]:
            continue
        r = b.room
        floor = [p for p in b.lights if p[1] == r["floor_in"] - 1]
        ceil = [p for p in b.lights if p[1] == r["ceil_y"]]
        assert floor, r["id"]
        if max(R.landing_lifts(r).values() or [0]) >= 12:
            # a hall entered on a high landing (the offering well, 24 up): the kit lights the landing and its stair
            # from the ceiling 6 over them, so this ceiling is dense by design of the kit (hull_lights), not sparse
            continue
        area = (r["ix1"] - r["ix0"] + 1) * (r["iz1"] - r["iz0"] + 1)
        assert len(ceil) <= area / (th["hull"]["light_every"] ** 2) * 2 + 4, (r["id"], len(ceil))


@pytest.mark.parametrize("mutant", ["floor_lights", "cap_dark_dressing"])
def test_mutating_the_tall_light_generator_off_leaves_cells_dark_and_the_walk_check_says_so(monkeypatch, mutant):
    monkeypatch.setattr(R, mutant, lambda *a, **k: None)
    if mutant == "floor_lights":
        # pass 2 (KIT2) runs light_dark_cells on every pass-2 room, and every tall hall here is one (an outline, a side
        # door): it lights whatever the floor lights leave dark, so the floor lights alone going is not darkness any more.
        # Both of the hall's light sources off is: the walk check must say so (the check is what this test is about)
        monkeypatch.setattr(R, "light_dark_cells", lambda *a, **k: None)
    bad = R.problems(DOC, RUIN)
    assert any("have no light" in p for p in bad), bad


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


def named_species():
    out = []
    for r in variant_records():
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for team in t["team_by_band"].values():
                out += [(r["id"], x) for x in team]
        out += [(r["id"], x) for x in p.get("species", []) if r["kind"] == "nest"]
        out += [(r["id"], x) for x in p.get("species_by_band", {}).values()]
        if r["kind"] == "habitat":
            if p.get("species"):
                out.append((r["id"], p["species"]))
            for key in ("rare_by_band", "legendary_by_band"):
                out += [(r["id"], x) for x in (p.get("prize") or {}).get(key, {}).values()]
    for crews in RUIN["boss"]["teams"].values():
        for crew in crews:
            out += [("boss", x) for x in crew]
    return out


def test_every_species_named_is_in_the_jar(species):
    sp, key = species
    missing = sorted({x for _r, x in named_species() if key(x) not in sp})
    assert not missing, missing


def test_the_prizes_legendary_is_a_legendary_or_mythical_no_ultra_beast_and_used_nowhere_else(species):
    sp, key = species
    legs = set(next(r for r in records() if r["kind"] == "habitat")["params"]["prize"]["legendary_by_band"].values())
    assert len(legs) == 1
    hab = legs.pop()
    labels = set(sp[key(hab)].get("labels", []))
    assert labels & {"legendary", "mythical"} and "ultra_beast" not in labels, labels
    word = re.compile(r"(?<![a-z])%s(?![a-z])" % re.escape(hab))
    import json

    def mentions(v):
        """Every dict in v with a string value that names the species."""
        if isinstance(v, dict):
            if any(isinstance(x, str) and word.search(x.lower()) for x in v.values()):
                yield v
            for x in v.values():
                yield from mentions(x)
        elif isinstance(v, list):
            for x in v:
                yield from mentions(x)

    for f in glob.glob(str(ROOT / "data" / "*.json")):
        name = Path(f).name
        if name == "dungeons.json":
            continue
        text = Path(f).read_text(encoding="utf-8")
        if name == "adopted_legendary_sites.json":
            # the catalogue of Cobbleverse's legendary structures: a donor that is NOT loaded homes nothing
            hits = list(mentions(json.loads(text)))
            assert all(h.get("loaded") is False for h in hits), [h.get("template") for h in hits]
            continue
        assert not word.search(text.lower()), f
    others = [d for d in DOC["dungeons"] if d["id"] != "flooded_ruin"]
    assert not any(word.search(str(d).lower()) for d in others)
    # DUNGEONS.md 8: the legendaries the owner approved for the planned dungeons (D18) are theirs
    doc8 = (ROOT / "docs" / "mechanics" / "DUNGEONS.md").read_text(encoding="utf-8")
    sec = doc8.split("## 8. Which legendaries", 1)[1].split("\n## ", 1)[0].lower()
    assert hab not in re.sub(r"[^a-z]", "", sec), "reserved in DUNGEONS.md 8"
    # no legendary, mythical or Ultra Beast fights for the salvagers or the boss
    for where, x in named_species():
        if x == hab:
            continue
        lb = set(sp[key(x)].get("labels", []))
        assert not lb & {"legendary", "mythical", "ultra_beast", "paradox"}, (where, x)


# ------------------------------------------------------------------------------------------------- params


def dead_ends():
    """Ids of the rooms a side entry ends in (the record's own shape: the last room of a `side` container). A dead end has
    no door out, so a gate there opens nothing: such a room is `open` (the sealed chamber, 2026-10-10: `cleared` was a
    SOFTLOCK finding, its clear opening nothing)."""
    return {c["rooms"][-1]["id"] for c in RUIN["rooms"] if c.get("kind") == "side" and c.get("rooms")}


def test_the_fight_params_follow_the_contract_and_never_pass_the_bands_upper_cap():
    bands = {str(b["band"]): b for b in D.bands(DOC)}
    ends = dead_ends()
    for r in variant_records():
        p = r.get("params", {})
        if r["kind"] in ("stand", "gauntlet", "ambush"):
            assert DF.stand_problems(DOC, r) == [], r["id"]
            assert DF.stand_classes(DOC, RUIN, r)
            if r["kind"] != "stand":
                tr = p["triggers"]
                assert len(tr) == len(p["trainers"]) and tr == sorted(tr) and all(0 < t < 1 for t in tr)
            assert r["gate"] == "cleared"
        elif r["kind"] == "miniboss":
            assert set(p["species_by_band"]) == set(bands) and p["level_offset"] <= 0 and p.get("catchable", True) is True   # the owner, 2026-10-10: every dungeon Pokemon catchable
            assert r["gate"] == "cleared"
        elif r["kind"] == "nest":
            assert set(p["count_by_band"]) == set(bands) and p["species"]
            lo, hi = p["level_spread"]
            assert 0 <= lo <= hi
        elif r["kind"] == "habitat":
            assert p.get("fight_only", False) is False and r["gate"] == ("open" if r["id"] in ends else "cleared"), r["id"]
            # pass 3: the habitat is the wing's prize room, its Pokemon spawned at the band's LOWER cap by the kit
            # (tools/dungeon_prize.py level_at), so no level of its own is authored to pass the upper cap
            assert p.get("prize") and "level_by_band" not in p, r["id"]
        elif r["kind"] == "puzzle":
            assert p["variant"] in ("levers", "sequence", "plates") and p["penalty_s"] > 0
        elif r["kind"] == "vault":
            assert r.get("gate", "open") == "open" and p["chests"] >= 1 and p["clock_cost_s"] > 0
            assert set(p["loot_by_band"]) == set(bands)
        elif r["kind"] == "safe_room":
            assert p.get("healer") is True
        elif r["kind"] == "setpiece":
            assert p["piece"] == "flood" and p["pit"] >= 6


def test_the_boss_has_a_crew_per_stage_per_band_the_ace_last():
    bo = RUIN["boss"]
    assert bo["name"] != NS["boss"]["name"]
    for b in D.bands(DOC):
        crews = bo["teams"][str(b["band"])]
        assert len(crews) == len(bo["stage_level_offsets"])
        assert len({c[-1] for c in crews}) == 1, "one ace, sent out last in every stage"


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_stands_near_the_night_shifts_and_clear_of_the_old_mine():
    f, nf = RUIN["rip"]["frame"], NS["rip"]["frame"]
    c = ((f["x0"] + f["x1"]) / 2, f["z"])
    nc = ((nf["x0"] + nf["x1"]) / 2, nf["z"])
    assert math.dist(c, nc) <= 60
    assert f["x0"] > nf["x1"] + 2 or f["x1"] < nf["x0"] - 2 or abs(f["z"] - nf["z"]) > 4, "the frames overlap"
    import json
    mine = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]["route1_old_mine"]
    x0, z0, x1, z1 = mine["plan"]["footprint"]["rect"]
    for x in range(f["x0"] - 1, f["x1"] + 2):
        for z in range(f["z"] - 1, f["z"] + 5):
            assert not (x0 <= x <= x1 and z0 <= z <= z1), (x, z)
    cx, cy, cz = RUIN["rip"]["click"]
    assert cz == f["z"] + 1 and cy == f["y"] and cx == (f["x0"] + f["x1"]) // 2
    ox, oy, oz, _yaw = RUIN["rip"]["outside"]
    assert oz - 0.5 > cz + 1.5, "the leaving player stands outside the click interaction"


def test_the_rip_is_on_the_heightmaps_ground_and_not_in_water():
    try:
        import ground as GR
        g = GR.load()
    except Exception as e:  # noqa: BLE001  (no heightmap in this checkout)
        pytest.skip("no heightmap: %s" % e)
    f = RUIN["rip"]["frame"]
    feet = {g(x, z) + 1 for x in range(f["x0"], f["x1"] + 1) for z in (f["z"], f["z"] + 1)}
    assert feet == {f["y"]}, feet
    ox, oy, oz, _ = RUIN["rip"]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy
    import json
    sea = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]
    assert f["y"] - 1 > sea, "the ground under the rip is at or below the sea"


def test_the_slots_follow_the_dungeons_index_and_do_not_overlap():
    doc = copy.deepcopy(DOC)
    i = [d["id"] for d in doc["dungeons"]].index("flooded_ruin")
    ss = [s for s in D.slots(doc) if s["dungeon"]["id"] == "flooded_ruin"]
    per = doc["engine"]["slots"]["per_dungeon"]
    assert [s["g"] for s in ss] == list(range(i * per + 1, i * per + per + 1))
    assert not [p for p in D.problems(doc) if "meets" in p]


def test_the_new_rooms_are_placed_off_the_route_and_every_one_is_optional():
    """PLACE-ROOMS (2026-10-11, the owner: "I want to see the new rooms"): the flooded ruin holds a fishing room, a
    wishing well and a fossil chamber, each on a side entry (never the main route, never a fork route), gate open,
    never paid by the clock, in every variant."""
    new = {"fishing_room", "wishing_well", "fossil_chamber"}
    for s in slots():
        lay = R.layout(DOC, RUIN, s)
        mine = [r for r in lay if r["kind"] in new]
        assert sorted(r["kind"] for r in mine) == sorted(new), s["g"]
        for r in mine:
            assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open", (s["g"], r["id"])
    rooms = C.walked(DOC, RUIN)[0]
    paid = {r["id"] for b in DOC["engine"]["bands"] for r in C.clock_rooms(DOC, RUIN, b["band"], rooms)}
    assert not paid & {r["id"] for r in rooms if r["kind"] in new}, "the clock never pays for an optional room"
