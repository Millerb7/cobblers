"""The Field of Swords (data/dungeons.json `field_of_swords`): a new dungeon authored to data/dungeon_prize_roster.json
(unit NEW-SWORDS, 2026-10-11) on the hill keep theme (data/dungeon_themes.json `hill_keep`).

The author's own tests (the independent audit is another agent's), in the pattern of the three existing dungeons' files.
What they hold the record to:

  shape     every room type the owner named (maze, puzzle, parkour, resources, nest, habitat, stand, mini-boss) and at
            least three of ours; connectors at most 40 long and at least 7 wide; most rooms not boxes; the route turns,
            doubles back and drops;
  length    tools/dungeon_clock.py's required time on the MAIN route about 32 minutes at band 1, the clock the tool's plus
            the collapse's 25 s, every band under D17's hour; its vaults priced on its own clock, so it moves no other
            dungeon's vault budget (MEGA-INTEGRATE);
  pacing    no two fight rooms back to back on any route; the safe room about two thirds in; the collapse before the boss;
  choices   two forks you can see out of crossroads, one three ways; a four-room WING ending in the prize habitat; two
            parkours; at least three of the six optional rooms on side entries; three secrets with relics; a shortcut;
            four variants;
  prize     the roster's pools exactly (no rare prize: the roster has none), Iron Crown held back by its model gate,
            Keldeo from band 5, every member a legendary/mythical/paradox by the jar, named by no other dungeon;
  variety   every trainer a team pool, the champion a species pool, the boss an alternate crew, at every band;
  species   every species named is in the Cobblemon 1.8.0 jar, and no fight but the prize holds a legend;
  rip       at the x slot given (x1625 +- 10), on the heightmap's dry ground, clear of the other rips.

Not covered: anything in a running Minecraft.
"""
from __future__ import annotations

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
RIP = {r["legacy_dungeon"]: r for r in DOC["rips"] if r.get("legacy_dungeon")}   # the test rips (data/dungeon_rips.json)
FS = next(d for d in DOC["dungeons"] if d["id"] == "field_of_swords")
OWNER_KINDS = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room"}
FIGHTS = {"stand", "gauntlet", "ambush", "miniboss", "nest", "habitat", "boss_arena"}
CONNECTORS = {"drift", "stairs"}
ENDS = {"entry_room", "exit_room"}
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
SETPIECE_ALLOWANCE_S = 25      # clock_why: one fall of the collapse, priced as the tool prices a fall (15 + 10)
LEGEND = {"legendary", "mythical", "ultra_beast", "paradox"}


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def slots():
    return [s for s in D.slots(DOC) if s["dungeon"]["id"] == FS["id"]]


def slot1():
    return slots()[0]


def records(d=FS):
    return list(R._walk_records(d["rooms"]))


def by_id(rid):
    return next(r for r in records() if r["id"] == rid)


def variant_records():
    out = []
    for s in R.variant_slots(DOC, FS, slots()):
        out += records(R.resolve(DOC, FS, s))
    return out


def main_layout(slot=None):
    return [r for r in R.layout(DOC, FS, slot or slot1()) if r["route"] == "main"]


def pass3_side(r):
    return r["kind"] == "side" and not any(x["kind"] in EXTRA_KINDS for x in r["rooms"])


# ------------------------------------------------------------------------------------------------- shape


def test_every_room_type_the_owner_named_is_there_and_three_of_ours():
    k = {r["kind"] for r in records()}
    assert OWNER_KINDS <= k, OWNER_KINDS - k
    assert len((OURS & k) - {"ambush"}) >= 3, OURS & k
    top = [r["kind"] for r in FS["rooms"]]
    assert top[0] == "entry_room" and top[-2:] == ["boss_arena", "exit_room"]
    assert FS["theme"] == "hill_keep" and FS["test"] is True and RIP[FS["id"]]["test"] is True
    assert FS["gate_flag"] == "cobblers:flag/gym6_cleared" and FS["first_band"] == 4 and FS["short"] == "fs"


def test_fewer_richer_rooms_short_wide_connectors_and_mostly_not_boxes():
    # the MAIN route (what every run walks) at most 20 rooms; the forks' ways and the wing are choices, not length
    assert len(main_layout()) <= 20, [r["id"] for r in main_layout()]
    assert sum(r["kind"] in CONNECTORS for r in main_layout()) <= 5, "the main route is rooms, not corridors"
    lay = R.layout(DOC, FS, slot1())
    for r in lay:
        if r["kind"] in CONNECTORS:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
        elif r["kind"] == "collapse_bridge" or r["route"] != "main":
            # the wall-walk is a wall's top and the crypt a crypt: narrow by design, never under the connector's 7
            assert 9 <= r["width"] <= 62, (r["id"], r["width"])
        elif r["kind"] not in ENDS:
            assert 15 <= r["width"] <= 62, (r["id"], r["width"])
    shaped = [r for r in lay if r["kind"] not in CONNECTORS | ENDS | R.BOX_ONLY_KINDS]
    assert sum(r["shape"] != "box" for r in shaped) >= len(shaped) * 0.6, [(r["id"], r["shape"]) for r in shaped]


def test_the_route_turns_doubles_back_and_drops():
    lay = R.layout(DOC, FS, slot1())
    assert {x["side"] for r in lay for x in R.room_doors(r)} == {"north", "south", "east", "west"}
    assert any(r["in_side"] == "east" for r in lay), "walked back west"
    floors = {r["floor_in"] for r in lay}
    assert max(floors) - min(floors) >= 20, floors
    main = main_layout()
    # the chapel walk runs back beside the tiltyard; the gaol runs under it
    assert any(a["xa"] <= b["xb"] and b["xa"] <= a["xb"] and (a["zb"] < b["za"] or b["zb"] < a["za"])
               and a["floor_in"] == b["floor_in"] for a in main for b in main if a["i"] < b["i"])


# ------------------------------------------------------------------------------------------------- length


def _required_by_band():
    walks = [C.walked(DOC, FS, s)[0] for s in R.variant_slots(DOC, FS, slots())]
    return {b["band"]: max(sum(C.required(DOC, FS, b["band"], C.clock_rooms(DOC, FS, b["band"], w)).values())
                           for w in walks) for b in DOC["engine"]["bands"]}


def test_about_32_minutes_required_at_band_1_and_the_clock_is_the_tools_plus_the_set_piece_allowance():
    req = _required_by_band()
    assert 30 * 60 <= req[1] <= 34 * 60, req[1] / 60
    slack = DOC["engine"]["clock"]["slack_factor"]
    own = FS["clock_s_by_band"]
    for b, s in req.items():
        assert own[str(b)] == math.ceil((s + SETPIECE_ALLOWANCE_S) * slack / 60) * 60, (b, own[str(b)])
        assert own[str(b)] <= 3600, "every band under D17's hour"
    assert "lockout_ticks" not in FS
    assert str(SETPIECE_ALLOWANCE_S) + " s" in FS["clock_why"]
    assert C.clock_problems(DOC, FS) == []


def test_the_vault_budget_of_its_vaults_is_its_own_clocks_and_no_other_dungeons_moves():
    # MEGA-INTEGRATE (2026-10-11): each dungeon's vaults are priced on its own clock, so this dungeon's clock moves no
    # other dungeon's vault budget (the old test held every band at or over the shortest other dungeon's)
    import dungeon_greed as DG
    without = dict(DOC, dungeons=[d for d in DOC["dungeons"] if d is not FS])
    for d in without["dungeons"][:3]:
        assert DG.vault_budget(DOC, dungeon=d) == DG.vault_budget(without, dungeon=d), d["id"]
    assert not [x for x in DG.vault_over(DOC) if x[0] == FS["id"]]


# ------------------------------------------------------------------------------------------------- pacing


def _neighbours(lay):
    by_i = {r["i"]: r for r in lay}
    for r in lay:
        for x in R.room_doors(r):
            if x["dir"] == "out" and not x.get("shortcut"):
                yield r, by_i[x["to"]]


def test_no_two_fights_back_to_back_on_any_route_in_any_variant():
    for s in R.variant_slots(DOC, FS, slots()):
        for a, b in _neighbours(R.layout(DOC, FS, s)):
            assert not (a["kind"] in FIGHTS and b["kind"] in FIGHTS), (s["k"], a["id"], b["id"])


def test_the_safe_room_two_thirds_in_and_the_collapse_before_the_boss():
    rooms = C.walked(DOC, FS, slot1())[0]
    paid = sorted(C.clock_rooms(DOC, FS, 1, rooms), key=lambda r: [x["id"] for x in rooms].index(r["id"]))
    cost = [sum(C.required(DOC, {}, 1, [r]).values()) for r in paid]
    total = sum(cost) + C.required(DOC, FS, 1, [])["boss"]
    at = {r["id"]: sum(cost[:k]) / total for k, r in enumerate(paid)}
    assert 0.55 <= at["infirmary"] <= 0.8, at["infirmary"]
    main = [r for r in FS["rooms"] if r["kind"] not in ("fork", "side")]
    i = [r["kind"] for r in main].index("boss_arena")
    assert main[i - 1]["kind"] == "setpiece" and main[i - 1]["params"]["piece"] == "collapse"
    assert [r["kind"] for r in records()].count("setpiece") == 1


# ------------------------------------------------------------------------------------------------- choices


def _forks():
    top = FS["rooms"]
    return [(top[k - 1], r) for k, r in enumerate(top) if r["kind"] == "fork"]


def test_two_forks_you_can_see_each_out_of_a_crossroads_one_of_them_three_ways():
    forks = _forks()
    assert len(forks) == 2 and all(h["kind"] == "crossroads" for h, _f in forks)
    assert sorted(len(f["routes"]) for _h, f in forks) == [2, 3]
    looks = set(R.load_themes()["themes"]["hill_keep"]["crossroads"]["looks"])
    for _h, f in forks:
        ls = [rt["look"] for rt in f["routes"]]
        assert len(set(ls)) == len(ls) and set(ls) <= looks, ls
        assert all(rt.get("sign") for rt in f["routes"]) and not any(rt.get("optional") for rt in f["routes"])
    three = next(f for _h, f in forks if len(f["routes"]) == 3)
    kinds = {frozenset({r["kind"] for r in rt["rooms"]} - CONNECTORS) for rt in three["routes"]}
    assert kinds == {frozenset({"stand"}), frozenset({"collapse_bridge"}), frozenset()}, kinds
    for s in R.variant_slots(DOC, FS, slots()):
        lay = R.layout(DOC, FS, s)
        ids = {r["id"]: r for r in lay}
        for h, f in forks:
            exits = [x for x in R.room_doors(ids[h["id"]]) if x["dir"] == "out" and not x.get("shortcut")]
            assert len(exits) == len(f["routes"]), (s["k"], h["id"])
            for i, a in enumerate(exits):
                for b in exits[i + 1:]:
                    assert a["side"] != b["side"] or abs(a["c"] - b["c"]) >= 10, (s["k"], h["id"])


def _wing():
    sides = [r for r in FS["rooms"] if pass3_side(r)]
    assert len(sides) == 1
    return sides[0]


def test_the_wing_is_four_rooms_a_hard_parkour_then_the_prize_at_its_dead_end_never_on_the_clock():
    w = _wing()
    ks = [r["kind"] for r in w["rooms"]]
    assert len(ks) == 4 and ks[0] not in R.BOX_ONLY_KINDS
    assert w["rooms"][-2]["kind"] == "parkour" and w["rooms"][-2]["params"].get("hard") is True
    last = w["rooms"][-1]
    assert last["kind"] == "habitat" and last["params"].get("prize") and last.get("gate") == "open"
    wing_ids = {r["id"] for r in w["rooms"]}
    for s in R.variant_slots(DOC, FS, slots()):
        lay = R.layout(DOC, FS, s)
        hab = next(r for r in lay if r["id"] == last["id"])
        assert hab["last"] and hab["route"] == w["id"] and not [x for x in R.room_doors(hab) if x["dir"] == "out"]
        for b in DOC["engine"]["bands"]:
            paid = {r["id"] for r in C.clock_rooms(DOC, FS, b["band"], C.walked(DOC, FS, s)[0])}
            assert not paid & wing_ids, (s["k"], b["band"])


def test_two_parkours_the_main_one_six_sections_the_wings_hard():
    import dungeon_parkour as P
    main = by_id("ramparts")
    hard = by_id("broken_spire")
    assert main["params"]["sections"] == 6 and main["width"] == 25 and main["id"] in {r["id"] for r in FS["rooms"]}
    assert hard["params"]["hard"] is True and hard["params"]["sections"] >= 4
    for s in R.variant_slots(DOC, FS, slots()):
        dd = R.resolve(DOC, FS, s)
        bs = {b.room["id"]: b for b in R.slot_build(DOC, FS, s)}
        _route, ledges, _lv, fork_i = P.plan_route(dd, bs[main["id"]].room)
        assert len(ledges) == 7 and fork_i is not None, (s["k"], len(ledges))
        _route, ledges, _lv, fork_i = P.plan_route(dd, bs[hard["id"]].room)
        assert len(ledges) == hard["params"]["sections"] + 1 and fork_i is None, s["k"]


def test_at_least_three_of_the_six_optional_rooms_on_side_entries_never_paid():
    for s in slots():
        lay = R.layout(DOC, FS, s)
        extra = [r for r in lay if r["kind"] in EXTRA_KINDS]
        assert len({r["kind"] for r in extra}) >= 3, s["g"]
        for r in extra:
            assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open", (s["g"], r["id"])
    rooms = C.walked(DOC, FS)[0]
    paid = {r["id"] for b in DOC["engine"]["bands"] for r in C.clock_rooms(DOC, FS, b["band"], rooms)}
    assert not paid & {r["id"] for r in rooms if r["kind"] in EXTRA_KINDS}
    # the strongroom's code is chalked in main-route rooms the walker has passed before reaching it
    bank = by_id("strongroom")
    order = [r["id"] for r in main_layout()]
    host = "inner_steps"
    for c in bank["params"]["clue_rooms"]:
        assert c in order and order.index(c) < order.index(host), c


def test_three_secrets_two_cracked_one_balcony_each_with_a_relic_and_its_lore():
    found = [(r, s) for r in records() for s in r.get("secrets") or []]
    assert sorted(s["type"] for _r, s in found) == ["balcony", "cracked", "cracked"]
    relics = []
    for r, _s in found:
        p = r["params"]
        assert re.fullmatch(r"[a-z0-9_]+", p["relic"]) and p["relic"].startswith("fs_")
        assert p["lore"] and len(p["lore"]) <= 160 and all(32 <= ord(c) < 127 for c in p["lore"])
        assert 0 < len(p.get("relic_name", "")) <= 32
        relics.append(p["relic"])
    assert len(set(relics)) == len(relics)
    for b in R.slot_build(DOC, FS, slot1()):
        if b.room.get("secrets"):
            assert b.anchors.get("secret"), b.room["id"]


def test_the_shortcut_opens_back_from_the_chapel_walk_into_the_tiltyard():
    lay = R.layout(DOC, FS, slot1())
    ids = {r["id"]: r for r in lay}
    f, near = ids["chapel_walk"], ids["tiltyard"]
    assert near["i"] < f["i"] and near["route"] == f["route"] == "main"
    df, dn = f["shortcut_doors"][0], near["shortcut_doors"][0]
    assert df["y"] == dn["y"] and df["c"] == dn["c"]


def test_four_distinct_variants_one_per_slot():
    vs = FS["variants"]
    assert len(vs) == 4 and len({v["id"] for v in vs}) == 4
    assert [R.variant_of(DOC, FS, s)["id"] for s in slots()] == [v["id"] for v in vs]
    shapes = set()
    for s in slots():
        shapes.add(tuple((r["id"], r["xa"] - s["x0"], r["za"] - s["z0"], r["shape"], r["kind"])
                         for r in R.layout(DOC, FS, s)))
    assert len(shapes) == 4


# ------------------------------------------------------------------------------------------------- the prize


@pytest.fixture(scope="module")
def jar():
    import dungeon_prize as PZ
    labels = PZ.jar_labels()
    if labels is None:
        pytest.skip("no Cobblemon 1.8 jar")
    return labels


def test_the_prize_is_the_rosters_pool_exactly_with_no_rare_prize_and_iron_crown_held_by_its_gate(jar):
    import dungeon_prize as PZ
    room = _wing()["rooms"][-1]
    entry = PZ.roster_entry("field_of_swords")
    assert entry and entry["rare_pool_by_band"] == {} and room["params"]["prize"]["roster"] == "field_of_swords"
    lf = DOC["engine"]["prize"]["legendary_from_band"]
    for b in range(1, 7):
        got = PZ.pool_at(DOC, room, b)
        if b < lf:
            assert got is None, (b, got)          # the roster names no rare prize: the field holds none below band 4
            continue
        pool, leg = got
        want = [sp for sp in entry["legendary_pool_by_band"][str(b)] if not PZ.model_gated(DOC, sp)]
        assert leg and pool == want, (b, pool)
        assert all(jar[sp] & LEGEND for sp in pool) and not any("ultra_beast" in jar[sp] for sp in pool)
        assert ("keldeo" in pool) == (b >= 5)
    assert PZ.model_gate("ironcrown") and "ironcrown" not in PZ.pool_at(DOC, room, 4)[0]
    assert "species" not in room["params"], "a resident would be no hidden prize"
    assert PZ.room_problems(DOC, FS, room) == []
    others = [d for d in DOC["dungeons"] if d["id"] != FS["id"]]
    for sp in {x for v in entry["legendary_pool_by_band"].values() for x in v}:
        word = re.compile(r"(?<![a-z])%s(?![a-z])" % sp)
        assert not any(word.search(json.dumps(d).lower()) for d in others), sp


@pytest.fixture(scope="module")
def built():
    return D.build(DOC)


def test_the_prize_spawns_from_band_4_at_the_lower_cap_and_takes_the_beast_ball(built):
    import key_ball as KB
    s = slot1()
    room = _wing()["rooms"][-1]
    base = "data/cobblers/function/dungeons/room/field_of_swords/%s/s%d/" % (room["id"], s["g"])
    for b in DOC["engine"]["bands"]:
        sp = built.get(base + "prize/spawn_b%d.mcfunction" % b["band"])
        if b["band"] < 4:
            assert sp is None, b["band"]
            continue
        assert "level=%d no_ai" % b["caps"][0] in sp and sp.rstrip().endswith("prize/bind"), b["band"]
    assert "tag @s add %s" % KB.boss_tag() in built[base + "prize/bind.mcfunction"].split("\n")
    start = built["data/cobblers/function/dungeons/slot/s%d/start.mcfunction" % s["g"]]
    assert "A sentry swears" in start


# ------------------------------------------------------------------------------------------------- variety and species


def test_every_trainer_a_team_pool_the_champion_a_species_pool_the_boss_an_alternate_crew_at_every_band():
    bands = [str(b["band"]) for b in DOC["engine"]["bands"]]
    for r in variant_records():
        p = r.get("params") or {}
        if r["kind"] in ("stand", "gauntlet", "ambush"):
            assert DF.stand_problems(DOC, r) == [], r["id"]
            for t in p["trainers"]:
                assert sorted(t["team_pool_by_band"]) == bands and "team_by_band" not in t
                assert all(len(v) >= 2 for v in t["team_pool_by_band"].values()), t["name"]
            assert r["gate"] == "cleared"
        elif r["kind"] == "miniboss":
            assert sorted(p["species_pool_by_band"]) == bands and all(len(v) >= 3 for v in p["species_pool_by_band"].values())
            assert p["level_offset"] <= 0 and p.get("catchable") is True and r["gate"] == "cleared"
    alt = FS["boss"]["teams_alt_by_band"]
    assert sorted(alt) == bands and FS["boss"]["heal_between_stages"] is True
    for k in bands:
        for crews in [FS["boss"]["teams"][k]] + alt[k]:
            assert len(crews) == len(FS["boss"]["stage_level_offsets"]) == 2
        assert alt[k][0] != FS["boss"]["teams"][k]


def named_species():
    out = []
    for r in variant_records():
        p = r.get("params") or {}
        for t in p.get("trainers") or []:
            for teams in t.get("team_pool_by_band", {}).values():
                out += [(r["id"], x) for team in teams for x in team]
        if r["kind"] == "nest":
            out += [(r["id"], x) for x in p["species"]]
        for v in (p.get("species_pool_by_band") or {}).values():
            out += [(r["id"], x) for x in v]
    for src in (FS["boss"]["teams"], {k: [c for alt in v for c in alt] for k, v in FS["boss"]["teams_alt_by_band"].items()}):
        out += [("boss", x) for crews in src.values() for crew in crews for x in crew]
    return out


def test_every_species_named_is_in_the_jar_and_no_fight_holds_a_legend(jar):
    names = named_species()
    missing = sorted({x for _r, x in names if x not in jar})
    assert not missing, missing
    assert not [(r, x) for r, x in names if jar[x] & LEGEND]


# ------------------------------------------------------------------------------------------------- the walk and the rip


def test_the_keep_builds_and_walks_with_no_problem_in_every_variant_and_branch():
    assert R.problems(DOC, FS) == []


def test_the_rip_is_at_its_slot_clear_of_the_other_rips():
    f = RIP[FS["id"]]["frame"]
    cx = (f["x0"] + f["x1"]) / 2
    assert abs(cx - 1625) <= 10 and f["x1"] - f["x0"] == 4
    for d in DOC["dungeons"]:
        if d["id"] == FS["id"]:
            continue
        o = RIP[d["id"]]["frame"]
        assert math.dist((cx, f["z"]), ((o["x0"] + o["x1"]) / 2, o["z"])) > 20, d["id"]
    mine = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]["route1_old_mine"]
    x0, _z0, x1, _z1 = mine["plan"]["footprint"]["rect"]
    assert f["x0"] > x1 + 50
    cxk, cy, cz = RIP[FS["id"]]["click"]
    assert cz == f["z"] + 1 and cy == f["y"] and cxk == (f["x0"] + f["x1"]) // 2
    assert RIP[FS["id"]]["outside"][2] - 0.5 > cz + 1.5


def test_the_rip_is_on_the_heightmaps_dry_ground():
    try:
        import ground as GR
        g = GR.load()
    except Exception as e:  # noqa: BLE001  (no heightmap in this checkout)
        pytest.skip("no heightmap: %s" % e)
    f = RIP[FS["id"]]["frame"]
    feet = {round(g(x, z)) + 1 for x in range(f["x0"], f["x1"] + 1) for z in (f["z"], f["z"] + 1)}
    assert feet == {f["y"]}, feet
    ox, oy, oz, _ = RIP[FS["id"]]["outside"]
    assert round(g(int(ox), int(oz))) + 1 == oy
    sea = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]
    assert f["y"] - 1 > sea
