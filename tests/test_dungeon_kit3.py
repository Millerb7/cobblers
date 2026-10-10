"""KIT3 (DUNGEON_ROOMS.md 1b): crossroads and looks, wings and optional routes, 5-6 section and hard parkour, the hidden
prize, the vault budget. The builder's own tests (the independent audit is AUDIT2's, tests/test_dungeon_independent_audit.py).

Fixture: tests/fixtures/dungeon_kit3_demo.json (a three-way crossroads, an optional rejoining route with a vault, a dead-end
wing of a connector, a hard five-section parkour and a prize habitat, a six-section main parkour, four variants).
Mutations change the GENERATOR (the code under test) and leave the record alone wherever the claim is about the code.
Not covered: anything in a running Minecraft (the looks' appearance, `random value`, the Beast Ball key, signs' text).
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_clock as C  # noqa: E402
import dungeon_crossroads as X  # noqa: E402
import dungeon_greed as DG  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_parkour as P  # noqa: E402
import dungeon_prize as PZ  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import key_ball as KB  # noqa: E402

FX = json.loads((ROOT / "tests" / "fixtures" / "dungeon_kit3_demo.json").read_text(encoding="utf-8"))
BASE = D.load()


def fx_doc(theme="mine", rooms=None, variants=True):
    doc = copy.deepcopy(BASE)
    d = doc["dungeons"][0]
    d["theme"] = theme
    d["rooms"] = copy.deepcopy(rooms if rooms is not None else FX["rooms"])
    d["variants"] = copy.deepcopy(FX["variants"]) if variants else []
    d.pop("spine", None)
    d.pop("clock_s_by_band", None)
    doc["dungeons"] = [d]
    doc["engine"]["sigils"]["free_first_entry"]["dungeons"] = [d["id"]]
    doc["engine"]["slots"]["per_dungeon"] = 4
    return doc


def slot1(doc):
    return D.slots(doc)[0]


def builts(doc, slot=None):
    d = doc["dungeons"][0]
    return {b.room["id"]: b for b in R.slot_build(doc, d, slot or slot1(doc))}


def find(rooms, rid):
    for r in R._walk_records(rooms):
        if r["id"] == rid:
            return r
    for r in rooms:
        if r["id"] == rid:
            return r
    raise KeyError(rid)


def count(b, block):
    return sum(int((b.grid.a == b.grid.idx[n]).sum()) for n in b.grid.names() if G.base(n) == block)


@pytest.fixture(autouse=True)
def fresh():
    R._BUILT.clear()
    yield


@pytest.fixture(scope="module")
def mine():
    R._BUILT.clear()
    doc = fx_doc("mine")
    return doc, R.problems(doc, doc["dungeons"][0])


# ------------------------------------------------------------------------------------------------- the fixture builds


def test_the_fixture_builds_with_no_problem_in_the_mine(mine):
    # breaks if any KIT3 structure (a 3-way crossroads, the looks, an optional route, a wing, long and hard parkour, the
    # prize) fails the kit's own walk check or plan in any of the four variants
    _doc, bad = mine
    assert bad == [], bad[:5]


@pytest.mark.parametrize("theme", ["jungle", "flooded_ruin"])
def test_the_crossroads_and_its_looks_build_in_every_theme(theme):
    # breaks if a theme's looks are missing or its look blocks break the walk check; the kit's checks only (a LIFE spot in
    # the ruin's d1, variant d, is LIFE's own finding and is not asked about here)
    doc = fx_doc(theme)
    bad = [p for p in R.problems(doc, doc["dungeons"][0]) if " life: " not in p]
    assert bad == [], bad[:5]


def test_whole_engine_problems_are_clean_on_the_fixture():
    doc = fx_doc("mine")
    assert D.problems(doc) == []


# ------------------------------------------------------------------------------------------------- looks


def test_every_look_restyles_its_door_on_both_sides():
    # breaks if a look is applied on one side only, or not at all
    doc = fx_doc("mine", variants=False)
    bs = builts(doc)
    looks = R.load_themes()["themes"]["mine"]["crossroads"]["looks"]
    for route_room, look in (("g_a", "lit"), ("o_a", "dark"), ("s_a", "flooded")):
        lk = looks[look]
        for rid in ("cross", route_room):
            b = bs[rid]
            door = next(x for x in R.room_doors(b.room) if x.get("look") == look)
            (_o, frames, _l) = R._door_cols(b.room, door)
            for fx_, fz in frames:
                assert G.base(b.grid.block_at(fx_, door["y"], fz)) == G.base(lk["frame"]), (rid, look)
            if lk.get("lamp"):
                assert count(b, G.base(lk["lamp"])) >= 2, (rid, look)
            if lk.get("water"):
                assert count(b, "minecraft:water") >= 6, (rid, look)


def test_the_host_carries_one_sign_per_route_and_the_route_rooms_none():
    doc = fx_doc("mine", variants=False)
    bs = builts(doc)
    signs = bs["cross"].meta.get("signs") or []
    assert sorted(tuple(s[3]) for s in signs) == sorted([("GANTRY",), ("OLD DRIFT", "KEEP OUT"), ("SUMP",)])
    for rid in ("g_a", "o_a", "s_a"):
        assert not bs[rid].meta.get("signs")
    sb = X.sign_block(R.load_themes()["themes"]["mine"], "north", ["OLD DRIFT", "KEEP OUT"])
    assert sb.startswith("minecraft:spruce_wall_sign[facing=south]{front_text:{messages:['\"OLD DRIFT\"','\"KEEP OUT\"','\"\"','\"\"']}")


def test_windows_are_cut_only_where_both_rooms_have_wall_and_never_outside_a_rooms_box():
    # breaks if a window lands outside either room's wall span or on another door's frame
    doc = fx_doc("mine", variants=False)
    rooms = R.layout(doc, doc["dungeons"][0], slot1(doc))
    n = 0
    for r in rooms:
        for door in R.room_doors(r):
            for p in door.get("windows") or []:
                n += 1
                lo, hi = X._along_range(r, door["side"])
                assert lo <= p <= hi
                assert not any(o is not door and o["side"] == door["side"] and abs(o["c"] - p) <= 2 for o in R.room_doors(r))
    assert n >= 2


def test_a_mutated_look_that_writes_through_the_neighbours_wall_is_refused(monkeypatch):
    # the generator writes its window two columns deep (into the next room's wall): the kit's own-box check must bite
    real = X.look_ops

    def deep(ctx):
        real(ctx)
        for door in R.room_doors(ctx.room):
            if door.get("look") and door["side"] == "east":
                w = R.wall_line(ctx.room, "east")
                ctx.add(R.setb((w + 1, door["y"] + 1, door["c"] + 3), "minecraft:iron_bars"))
    monkeypatch.setattr(R, "POST_DRESS_FNS", [deep])
    doc = fx_doc("mine", variants=False)
    bad = R.problems(doc, doc["dungeons"][0])
    assert any("outside" in p or "writes" in p for p in bad), bad[:5]


def test_a_mutated_trench_on_the_door_row_breaks_the_walk_check(monkeypatch):
    # water on the cell inside the door (row 0) leaves the door's own cell without a floor: the walk check must name it
    real = X._approach

    def wet_door_row(ctx, door, lk):
        real(ctx, door, lk)
        if lk.get("water"):
            x, y, z = R.inner_cell(ctx.room, door)
            ctx.add(R.setb((x, y - 2, z), lk["bed"]))
            ctx.add(R.setb((x, y - 1, z), "minecraft:water"))
    monkeypatch.setattr(X, "_approach", wet_door_row)
    doc = fx_doc("mine", variants=False)
    bad = R.problems(doc, doc["dungeons"][0])
    assert bad, "a flooded door cell must fail the walk check"


# ------------------------------------------------------------------------------------------------- crossroads checks


def _rooms():
    return copy.deepcopy(FX["rooms"])


def test_a_crossroads_must_be_followed_by_a_fork():
    rooms = _rooms()
    i = [r["id"] for r in rooms].index("f1")
    fork = rooms.pop(i)
    rooms.insert(i + 1, fork)        # court now stands between the crossroads and its fork
    doc = fx_doc("mine", rooms, variants=False)
    bad = X.record_checks(doc, doc["dungeons"][0], R.resolve(doc, doc["dungeons"][0], slot1(doc)), R.theme_for(doc["dungeons"][0]))
    assert any("must be a fork" in p for p in bad), bad


@pytest.mark.parametrize("edit,needle", [
    (lambda f: f["routes"][1].pop("look"), "needs a look"),
    (lambda f: f["routes"][1].update(look="lit"), "look different"),
    (lambda f: f["routes"][1].update(look="neon"), "is not one of"),
    (lambda f: f["routes"][1].update(sign="THIS SIGN IS FAR TOO LONG"), "sign line"),
    (lambda f: f["routes"][1].update(sign=["A", "B", "C", "D"]), "1..3 lines"),
    (lambda f: f["routes"].append(copy.deepcopy(f["routes"][2]) or f["routes"][-1].update(id="four", look="lit")), "at most 3"),
    (lambda f: [rt.update(optional=True) for rt in f["routes"]], "every route is optional"),
])
def test_crossroads_record_checks_bite(edit, needle):
    rooms = _rooms()
    edit(find(rooms, "f1"))
    doc = fx_doc("mine", rooms, variants=False)
    d = doc["dungeons"][0]
    bad = X.record_checks(doc, d, d, R.theme_for(d))
    assert any(needle in p for p in bad), bad


def test_two_exits_closer_than_the_gap_on_one_wall_are_refused():
    # the pass-2 complaint: two near-identical doors on one wall. The dark route moved to the east wall beside route 0
    rooms = _rooms()
    f1 = find(rooms, "f1")
    f1["routes"][1]["from"] = {"side": "east", "dz": -6}
    f1["routes"][1]["rooms"][0]["in"] = {"side": "west"}
    doc = fx_doc("mine", rooms, variants=False)
    # (the moved route also overlaps route 0's rooms, which the plan check names first; the exit check is asked directly)
    bad = X.geometry_checks(doc, doc["dungeons"][0], slot1(doc))
    assert any("apart (at least %d" % X.EXIT_GAP in p for p in bad), bad[:5]


def test_the_hub_must_see_every_exit_and_the_sight_check_bites(monkeypatch):
    # generator mutation: the hub put in the crossroads' north-west corner behind a pillar of rock; the record is untouched
    doc = fx_doc("mine", variants=False)
    assert X.geometry_checks(doc, doc["dungeons"][0], slot1(doc)) == []
    real = X.kind_crossroads

    def walled(doc_, d, slot, room, theme):
        res = real(doc_, d, slot, room, theme)
        hx, hy, hz = res["anchors"]["hub"]
        ops = [R.fill((hx - 2, hy, hz - 2, hx + 2, hy + 3, hz - 1), "minecraft:stone"),
               R.fill((hx - 2, hy, hz + 1, hx + 2, hy + 3, hz + 2), "minecraft:stone"),
               R.fill((hx + 1, hy, hz - 1, hx + 2, hy + 3, hz + 1), "minecraft:stone")]
        return dict(res, blocks=ops)
    R.KINDS["crossroads"] = walled
    try:
        R._BUILT.clear()
        bad = X.geometry_checks(doc, doc["dungeons"][0], slot1(doc))
    finally:
        R.KINDS["crossroads"] = real
    assert any("cannot be seen from the hub" in p for p in bad), bad


# ------------------------------------------------------------------------------------------------- wings, optional routes, the clock


def test_a_wing_of_five_rooms_and_a_wing_opening_on_a_box_only_kind_are_refused():
    rooms = _rooms()
    w = find(rooms, "w_lair")
    w["rooms"] = w["rooms"] + [copy.deepcopy(w["rooms"][0]) for _ in range(2)]
    for k, r in enumerate(w["rooms"][3:]):
        r["id"] = "w_extra%d" % k
    doc = fx_doc("mine", rooms, variants=False)
    d = doc["dungeons"][0]
    assert any("at most 4 rooms" in p for p in X.record_checks(doc, d, d, R.theme_for(d)))
    rooms = _rooms()
    find(rooms, "w_lair")["rooms"].pop(0)        # the wing now opens straight onto the parkour
    doc = fx_doc("mine", rooms, variants=False)
    d = doc["dungeons"][0]
    assert any("put a connector first" in p for p in X.record_checks(doc, d, d, R.theme_for(d)))


def test_the_clock_never_pays_for_an_optional_route_or_a_wing():
    doc = fx_doc("mine", variants=False)
    d = doc["dungeons"][0]
    clk = C.derive(doc, d)
    rows, _tot = C.walked(doc, d, slot1(doc))
    assert {r["id"] for r in rows if r["optional"]} == {"l_a", "l_vault", "l_c"}
    paid = {r["id"] for r in C.clock_rooms(doc, d, 1, rows)}
    assert not paid & {"l_a", "l_vault", "l_c", "w_a", "w_pk", "w_lair_end"}
    assert clk
    # the same loop made mandatory (it is the longer way) raises the required seconds: the exclusion is what kept it out
    # (the minute rounding of the clock can hide 5 seconds, so the unrounded required time is compared)
    req = sum(C.required(doc, {}, 1, C.clock_rooms(doc, d, 1, rows)).values())
    rooms = _rooms()
    find(rooms, "f2")["routes"][1]["optional"] = False
    doc2 = fx_doc("mine", rooms, variants=False)
    d2 = doc2["dungeons"][0]
    R._BUILT.clear()
    rows2, _t = C.walked(doc2, d2, slot1(doc2))
    req2 = sum(C.required(doc2, {}, 1, C.clock_rooms(doc2, d2, 1, rows2)).values())
    assert req2 > req, (req, req2)


def test_a_route_leaving_the_crossroads_by_a_side_wall_walks_its_own_way(monkeypatch):
    # the fixture's dark and flooded routes leave by the north and south walls and reach the court by its far doors: the
    # clock adds the difference to their first and last rooms (the independent audit measured a band-3 minute without it)
    doc = fx_doc("mine", variants=False)
    d = doc["dungeons"][0]
    ex = C.route_extras(doc, d, slot1(doc))
    ids = {b.room["i"]: b.room["id"] for b in R.slot_build(doc, d, slot1(doc))}
    named = {ids[i] for i, v in ex.items() if v > 0}
    assert {"o_a", "s_a"} <= named and "g_a" not in named, named
    with_extra = C.derive(doc, d)
    monkeypatch.setattr(C, "route_extras", lambda *a, **k: {})
    R._BUILT.clear()
    assert sum(C.derive(doc, d).values()) < sum(with_extra.values())


# ------------------------------------------------------------------------------------------------- parkour


def test_six_and_five_section_parkours_plan_and_the_hard_one_is_all_tier_three_with_no_easy_way():
    doc = fx_doc("mine", variants=False)
    bs = builts(doc)
    for rid, s in (("pk", 6), ("w_pk", 5)):
        route, ledges, _lv, fork_i = P.plan_route(doc["dungeons"][0], bs[rid].room)
        assert len(ledges) == s + 1
        if rid == "w_pk":
            assert fork_i is None
            assert sum(1 for h in route.hops if h["n"] == P.FLAT_MAX) >= 6
        else:
            assert fork_i is not None


def test_parkour_sections_over_six_are_refused():
    rooms = _rooms()
    find(rooms, "pk")["params"]["sections"] = 7
    doc = fx_doc("mine", rooms, variants=False)
    d = doc["dungeons"][0]
    assert any("sections is 2..6" in p for p in X.record_checks(doc, d, d, R.theme_for(d)))


# ------------------------------------------------------------------------------------------------- the prize


@pytest.fixture(scope="module")
def pack():
    R._BUILT.clear()
    doc = fx_doc("mine")
    return doc, D.build(doc)


def lines(files, name):
    return files["data/cobblers/function/dungeons/%s.mcfunction" % name].split("\n")


def test_the_prize_is_rolled_at_the_threshold_for_every_band_it_has_and_told_on_the_board(pack):
    doc, files = pack
    st = lines(files, "slot/s1/start")
    rolls = [l for l in st if "random value 1..100" in l]
    assert len(rolls) == 6
    room = find(doc["dungeons"][0]["rooms"], "w_lair_end")
    for b in range(1, 7):
        c = PZ.chance(doc, room, b)
        assert any(("matches %d " % b) in l and ("matches ..%d " % c) in l for l in st), b
    assert PZ.chance(doc, room, 1) == 20 and PZ.chance(doc, room, 2) == doc["engine"]["prize"]["chance_by_band"][1]
    assert any("data merge entity" in l and "Rumour: A miner swears" in l for l in st)
    # the arrival puts the board back WITHOUT the rumour
    arr = [l for l in lines(files, "slot/s1/arrive") if "data merge entity" in l]
    assert len(arr) == 1 and "Rumour" not in arr[0]
    # the roll comes after the clock is set and the greed zeroed: it is this run's, past the sigil
    assert st.index(rolls[0]) > max(i for i, l in enumerate(st) if "greed/zero" in l)


def test_the_prize_spawns_at_the_bands_lower_cap_and_only_legendary_bands_carry_the_key_tag(pack):
    doc, files = pack
    tag = KB.boss_tag()
    base = "room/night_shift/w_lair_end/s1/"
    for b in doc["engine"]["bands"]:
        sp = lines(files, base + "prize/spawn_b%d" % b["band"])
        assert any("level=%d no_ai" % b["caps"][0] in l for l in sp), b
        leg = b["band"] >= doc["engine"]["prize"]["legendary_from_band"]
        assert any(l.endswith("prize/bind" if leg else "prize/rare_bind") for l in sp)
    assert "tag @s add %s" % tag in lines(files, base + "prize/bind")
    assert "tag @s add %s" % tag not in lines(files, base + "prize/rare_bind")
    reset = lines(files, base + "reset")
    assert any("dg.pz.w_lair_end" in l and "discard" in l for l in reset)
    assert "scoreboard players set #s1r21p dg.rs 0" in reset
    enter = lines(files, base + "enter")
    assert any("#s1r21p dg.rs matches 1 if score @s dg.band matches 4 run function" in l for l in enter)


def test_a_band_with_no_chance_never_rolls(pack):
    rooms = _rooms()
    find(rooms, "w_lair_end")["params"]["prize"]["chance_by_band"] = {"1": 0}
    doc = fx_doc("mine", rooms, variants=False)
    st = PZ.start_lines(doc, slot1(doc))
    assert not any("matches 1 store result" in l for l in st)


def test_key_ball_accepts_the_prize_and_bites_when_its_bind_drops_the_tag(monkeypatch):
    kb = KB.load()
    assert any(b["id"] == "dungeon_prize" for b in kb["bosses"])
    assert KB.boss_problems(kb) == []
    tag = "tag @s add %s" % KB.boss_tag()
    real = PZ.bind_lines
    monkeypatch.setattr(PZ, "bind_lines", lambda *a, **k: [l for l in real(*a, **k) if l != tag])
    bad = KB.boss_problems(kb)
    assert bad and all("dungeon_prize" in p for p in bad), bad


def test_with_no_authored_prize_key_ball_checks_the_reference_bind():
    files = PZ.build(D.load())
    assert list(files) == ["data/cobblers/function/dungeons/prize/reference/bind.mcfunction"]
    assert "tag @s add %s" % KB.boss_tag() in files[list(files)[0]].split("\n")


@pytest.mark.parametrize("edit,needle", [
    (lambda p: p["rare_by_band"].update({"4": "gabite"}), "the rare prize is below band 4"),
    (lambda p: p["legendary_by_band"].update({"3": "kartana"}), "the legendary prize is from band 4"),
    (lambda p: p.update(colour="red"), "unknown key"),
    (lambda p: p.update(rumour='a "quoted" rumour'), "prize.rumour"),
    (lambda p: p.update(chance_by_band={"1": 150}), "chance_by_band"),
])
def test_prize_record_checks_bite(edit, needle):
    rooms = _rooms()
    edit(find(rooms, "w_lair_end")["params"]["prize"])
    doc = fx_doc("mine", rooms, variants=False)
    bad = PZ.room_problems(doc, doc["dungeons"][0], find(rooms, "w_lair_end"))
    assert any(needle in p for p in bad), bad


def test_a_prize_outside_an_open_habitat_is_refused():
    rooms = _rooms()
    r = find(rooms, "w_lair_end")
    doc = fx_doc("mine", rooms, variants=False)
    assert any("gate is open" in p for p in PZ.room_problems(doc, doc["dungeons"][0], dict(r, gate="cleared")))
    assert any("lives in a habitat" in p for p in PZ.room_problems(doc, doc["dungeons"][0], dict(r, kind="nest")))


@pytest.mark.skipif(PZ.jar_labels() is None, reason="the Cobblemon 1.8.0 jar is not on this machine")
def test_the_jar_decides_what_is_legendary():
    rooms = _rooms()
    p = find(rooms, "w_lair_end")["params"]["prize"]
    p["rare_by_band"]["1"] = "nihilego"            # an Ultra Beast before the Beast Ball stage
    p["legendary_by_band"]["5"] = "garchomp"       # not a legendary
    p["legendary_by_band"]["6"] = "notamon"
    doc = fx_doc("mine", rooms, variants=False)
    bad = PZ.room_problems(doc, doc["dungeons"][0], find(rooms, "w_lair_end"))
    assert any("nihilego is ultra_beast" in x for x in bad), bad
    assert any("garchomp is not a legendary" in x for x in bad), bad
    assert any("notamon is not a species" in x for x in bad), bad


def test_the_engine_prize_defaults_rise_with_band_and_keep_the_lower_cap():
    assert PZ.engine_problems(BASE) == []
    doc = copy.deepcopy(BASE)
    doc["engine"]["prize"]["chance_by_band"] = [30, 10, 15, 20, 25, 30]
    assert any("rise with the band" in p for p in PZ.engine_problems(doc))
    doc = copy.deepcopy(BASE)
    doc["engine"]["prize"]["level"] = "upper_cap"
    assert any("lower_cap" in p for p in PZ.engine_problems(doc))


# ------------------------------------------------------------------------------------------------- the vault budget


def test_the_vault_budget_is_the_runs_gathering_wage_by_band():
    # the numbers DUNGEON_ROOMS.md 1b states, from the live data (tools/economy_sim.py World, the dungeons' clocks)
    assert DG.vault_budget(BASE) == {1: 330, 2: 774, 3: 792, 4: 864, 5: 1441, 6: 1526}


def test_the_pass2_vaults_are_over_budget_and_named_until_enforced_then_refused():
    over = DG.vault_over(BASE)
    assert {(d, r) for d, r, *_ in over} >= {("night_shift", "pay_office"), ("jungle", "treasury")}
    assert DG.vault_problems(BASE) == []                       # not enforced: the three dungeons still build
    assert len(D.warnings(BASE)) >= len(over)
    table = DG.load()
    table["vault_budget"]["enforce"] = True
    assert len(DG.vault_problems(BASE, table)) == len(over)


def test_the_fixtures_vault_is_inside_the_budget_and_a_dearer_chest_is_not():
    doc = fx_doc("mine", variants=False)
    table = DG.load()
    table["vault_budget"]["enforce"] = True
    assert DG.vault_problems(doc, table) == []
    rooms = _rooms()
    find(rooms, "l_vault")["params"]["loot_by_band"]["1"] = [{"item": "cobblemon:revive", "count": 1}]
    doc = fx_doc("mine", rooms, variants=False)
    bad = DG.vault_problems(doc, table)
    assert any("l_vault band 1" in p and "500 cp" in p for p in bad), bad


def test_the_contract_is_published_in_dungeon_rooms_md():
    text = (ROOT / "docs" / "mechanics" / "DUNGEON_ROOMS.md").read_text(encoding="utf-8")
    sec = text.split("## 1b.", 1)[1].split("\n## 2.", 1)[0]
    for word in ("crossroads", "look", "optional", "sections", "hard", "rare_by_band", "legendary_by_band", "chance_by_band",
                 "rumour", "vault_budget"):
        assert word in sec, word
    nums = DG.vault_budget(BASE)
    assert "band 1 %d cp, 2 %d, 3 %d, 4 %d, 5 %d, 6 %d" % tuple(nums[b] // 4 for b in range(1, 7)) in sec
