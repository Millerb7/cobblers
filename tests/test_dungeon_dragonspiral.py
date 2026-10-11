"""The Dragonspiral (data/dungeons.json `dragonspiral`, theme `ice_spire`): a proposed dungeon of
data/dungeon_prize_roster.json (unit COVERAGE, 2026-10-11, the Tao trio's home) authored at full length by unit
NEW-DRAGONSPIRAL (2026-10-11) to the owner's standing asks (DUNGEON_PASS2.md, DUNGEON_ROOMS.md 1a, 1b, 12-14).

The author's own tests (the independent audit is another agent's). What they hold the record to:

  shape     every room type the owner named (maze, puzzle, parkour, resources, nest, habitat, stand, mini-boss) and three
            of ours; connectors at most 40 long and at least 7 wide; most rooms not boxes; the route turns, doubles back
            and CLIMBS (a spire: the second half 18 above the first);
  length    tools/dungeon_clock.py's required time on the clock's path about 32 minutes at band 1, the record's clock the
            tool's plus the set piece's 25 s x 1.25, every band under the hour, no lockout of its own;
  pacing    no two fight rooms back to back; the safe room 0.55-0.8 in; the set piece (collapse) right before the boss;
  choices   two crossroads forks (three ways and two), distinct looks; the optional wing (a fork route marked optional:
            a hard parkour, a balcony secret, the prize habitat) never on the clock; two parkours (six sections, and a
            hard one); five of the six optional rooms on side entries; three secrets with relics; a shortcut; four
            variants;
  prize     exactly the roster's: Kyurem, Reshiram, Zekrom at band 6 only (the jar's `restricted`), Beast Ball keyed,
            and nothing below band 6 (the roster names no rare pool);
  variety   every trainer rotates 2-3 teams a band, the mini-boss 2-3 species a band, the boss an alternate crew;
  species   every species named is in the Cobblemon 1.8.0 jar, none a doll or a mis-assembled model;
  walk      the room kit's own checks (every variant and branch walked) and the engine's;
  rip       the brief's slot, x1600 +- 10 on the test trail, on the heightmap's dry ground, clear of the other rips.

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
DS = next(d for d in DOC["dungeons"] if d["id"] == "dragonspiral")
OWNER_KINDS = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room"}
EXTRA_KINDS = {"bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber"}
FIGHTS = {"stand", "gauntlet", "ambush", "miniboss", "nest", "habitat", "boss_arena"}
CONNECTORS = {"drift", "stairs"}
ENDS = {"entry_room", "exit_room"}
SETPIECE_ALLOWANCE_S = 25
ROSTER = json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def slots():
    return [s for s in D.slots(DOC) if s["dungeon"]["id"] == "dragonspiral"]


def slot1():
    return slots()[0]


def records(d=DS):
    return list(R._walk_records(d["rooms"]))


def variant_records():
    out = []
    for s in R.variant_slots(DOC, DS, slots()):
        out += records(R.resolve(DOC, DS, s))
    return out


def main_layout(slot=None):
    return [r for r in R.layout(DOC, DS, slot or slot1()) if r["route"] == "main"]


def _forks():
    top = DS["rooms"]
    return [(top[k - 1], r) for k, r in enumerate(top) if r["kind"] == "fork"]


def _wing():
    routes = [rt for _h, f in _forks() for rt in f["routes"] if rt.get("optional")]
    assert len(routes) == 1
    return routes[0]


def _prize_room():
    return _wing()["rooms"][-2]


# ------------------------------------------------------------------------------------------------- shape


def test_every_room_type_the_owner_named_is_there_and_three_of_ours():
    k = {r["kind"] for r in records()}
    assert OWNER_KINDS <= k, OWNER_KINDS - k
    assert len((OURS & k) - {"ambush"}) >= 3, OURS & k
    top = [r["kind"] for r in DS["rooms"]]
    assert top[0] == "entry_room" and top[-2:] == ["boss_arena", "exit_room"]
    assert DS["theme"] == "ice_spire" and DS["test"] is True and DS["rip"]["test"] is True
    assert DS["gate_flag"] is None and "siting_pending" not in DS["rip"], "an overworld test dungeon, open to every band"


def test_short_wide_connectors_and_mostly_not_boxes():
    lay = R.layout(DOC, DS, slot1())
    for r in lay:
        if r["kind"] in CONNECTORS:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
        elif r["kind"] not in ENDS:
            assert 15 <= r["width"] <= 62, (r["id"], r["width"])
    shaped = [r for r in lay if r["kind"] not in CONNECTORS | ENDS | R.BOX_ONLY_KINDS | EXTRA_KINDS]
    assert sum(r["shape"] != "box" for r in shaped) >= len(shaped) * 0.7, [(r["id"], r["shape"]) for r in shaped]


def test_the_route_turns_doubles_back_and_climbs_the_spire():
    lay = R.layout(DOC, DS, slot1())
    assert {x["side"] for r in lay for x in R.room_doors(r)} == {"north", "south", "east", "west"}
    assert any(r["in_side"] == "east" for r in lay), "walked back west"
    main = main_layout()
    entry, boss = main[0], next(r for r in main if r["kind"] == "boss_arena")
    assert boss["floor_in"] - entry["floor_in"] >= 18, "the summit stands well above the gate"
    floors = [r["floor_in"] for r in main]
    assert floors == sorted(floors), "the main route never goes down: a climb"
    # the doubled-back gallery runs over the rookery: two main rooms share x, the later one higher
    assert any(a["xa"] <= b["xb"] and b["xa"] <= a["xb"] and b["floor_in"] - a["floor_in"] >= 12
               for a in main for b in main if a["i"] < b["i"])


# ------------------------------------------------------------------------------------------------- length


def _required_by_band():
    walks = [C.walked(DOC, DS, s)[0] for s in R.variant_slots(DOC, DS, slots())]
    return {b["band"]: max(sum(C.required(DOC, DS, b["band"], C.clock_rooms(DOC, DS, b["band"], w)).values()) for w in walks)
            for b in DOC["engine"]["bands"]}


def test_about_32_minutes_required_at_band_1_and_the_clock_is_the_tools_plus_the_set_piece_allowance():
    req = _required_by_band()
    assert 29 * 60 <= req[1] <= 34 * 60, req[1] / 60
    slack = DOC["engine"]["clock"]["slack_factor"]
    own = DS["clock_s_by_band"]
    for b, s in req.items():
        derived = math.ceil((s + SETPIECE_ALLOWANCE_S) * slack / 60) * 60
        if b == 4:
            # authored over the derived so this dungeon is not the shortest band-4 clock the vault and resources budgets
            # read (clock_why); never under it
            assert own["4"] == 2640 and own["4"] > derived, (own["4"], derived)
        else:
            assert own[str(b)] == derived, (b, own[str(b)])
        assert own[str(b)] <= 3600
    assert "lockout_ticks" not in DS
    assert "25 s" in DS["clock_why"]
    assert C.clock_problems(DOC, DS) == []


# ------------------------------------------------------------------------------------------------- pacing


def test_no_two_fights_back_to_back_on_any_route_in_any_variant():
    for s in R.variant_slots(DOC, DS, slots()):
        lay = R.layout(DOC, DS, s)
        by_i = {r["i"]: r for r in lay}
        for a in lay:
            for x in R.room_doors(a):
                if x["dir"] == "out" and not x.get("shortcut"):
                    b = by_i[x["to"]]
                    assert not (a["kind"] in FIGHTS and b["kind"] in FIGHTS), (s["k"], a["id"], b["id"])


def test_the_safe_room_two_thirds_in_and_the_collapse_before_the_boss():
    # measured along the MAIN walk, as the Night Shift's test does (the same spine: the safe room after the climb and
    # the double-back, before the second crossroads)
    rooms = C.walked(DOC, DS, slot1())[0]
    at, run = {}, 0
    for r in rooms:
        if r["route"] == "main":
            run += r["walk"]
            at[r["id"]] = run
    safe = next(r["id"] for r in records() if r["kind"] == "safe_room")
    assert 0.6 <= at[safe] / run <= 0.8, at[safe] / run
    main = [r for r in DS["rooms"] if r["kind"] not in ("fork", "side")]
    i = [r["kind"] for r in main].index("boss_arena")
    assert main[i - 1]["kind"] == "setpiece" and main[i - 1]["params"]["piece"] == "collapse"
    assert [r["kind"] for r in records()].count("setpiece") == 1


# ------------------------------------------------------------------------------------------------- choices


def test_two_forks_you_can_see_each_out_of_a_crossroads_one_of_them_three_ways():
    forks = _forks()
    assert len(forks) == 2 and all(h["kind"] == "crossroads" for h, _f in forks)
    assert sorted(len(f["routes"]) for _h, f in forks) == [2, 3]
    looks = set(R.load_themes()["themes"]["ice_spire"]["crossroads"]["looks"])
    for _h, f in forks:
        ls = [rt["look"] for rt in f["routes"]]
        assert len(set(ls)) == len(ls) and set(ls) <= looks and all(rt.get("sign") for rt in f["routes"])
        assert sum(1 for rt in f["routes"] if not rt.get("optional")) >= 1
    three = next(f for _h, f in forks if len(f["routes"]) == 3)
    kinds = {frozenset({r["kind"] for r in rt["rooms"]} - CONNECTORS) for rt in three["routes"]}
    assert kinds == {frozenset({"collapse_bridge"}), frozenset({"dark_room"}), frozenset({"puzzle"})}, kinds
    for s in R.variant_slots(DOC, DS, slots()):
        lay = R.layout(DOC, DS, s)
        by_id = {r["id"]: r for r in lay}
        for h, f in forks:
            exits = [x for x in R.room_doors(by_id[h["id"]]) if x["dir"] == "out" and not x.get("shortcut")]
            assert len(exits) == len(f["routes"]), (s["k"], h["id"])
            for i, a in enumerate(exits):
                for b in exits[i + 1:]:
                    assert a["side"] != b["side"] or abs(a["c"] - b["c"]) >= 10, (s["k"], h["id"])


def test_the_wing_is_optional_a_hard_parkour_guards_the_prize_and_the_clock_never_pays_it():
    w = _wing()
    ks = [r["kind"] for r in w["rooms"]]
    assert 2 <= len(ks) <= 4 and ks[0] not in R.BOX_ONLY_KINDS
    hard = [r for r in w["rooms"] if r["kind"] == "parkour"]
    assert len(hard) == 1 and hard[0]["params"].get("hard") is True
    pz = _prize_room()
    assert pz["kind"] == "habitat" and pz.get("gate", "open") == "open" and pz["params"].get("prize")
    assert w["rooms"][w["rooms"].index(pz) - 1]["kind"] == "parkour", "the hard parkour is the room before the prize"
    assert any(s["type"] == "balcony" for s in pz.get("secrets") or [])
    ids = {r["id"] for r in w["rooms"]}
    for s in R.variant_slots(DOC, DS, slots()):
        walked = C.walked(DOC, DS, s)[0]
        for b in DOC["engine"]["bands"]:
            assert not {r["id"] for r in C.clock_rooms(DOC, DS, b["band"], walked)} & ids


def test_two_parkours_the_main_one_six_sections_the_wings_hard_with_no_easy_fork():
    import dungeon_parkour as P
    main = next(r for r in records() if r["kind"] == "parkour" and not r["params"].get("hard"))
    hard = next(r for r in records() if r["kind"] == "parkour" and r["params"].get("hard"))
    assert main["params"]["sections"] == 6 and main["width"] == 25 and main["length"] >= 30 * 6 - 10 + 2
    assert hard["params"]["sections"] >= 4
    for s in R.variant_slots(DOC, DS, slots()):
        dd = R.resolve(DOC, DS, s)
        bs = {b.room["id"]: b for b in R.slot_build(DOC, DS, s)}
        _route, ledges, _lv, fork_i = P.plan_route(dd, bs[main["id"]].room)
        assert len(ledges) == 7 and fork_i is not None, (s["k"], len(ledges), fork_i)
        route, ledges, _lv, fork_i = P.plan_route(dd, bs[hard["id"]].room)
        assert len(ledges) == hard["params"]["sections"] + 1 and fork_i is None, s["k"]
        assert sum(1 for h in route.hops if h["n"] == P.FLAT_MAX) >= 4, s["k"]


def test_five_of_the_six_optional_rooms_each_on_a_side_entry_open_and_never_paid():
    sides = [r for r in DS["rooms"] if r["kind"] == "side"]
    placed = {x["kind"] for sd in sides for x in sd["rooms"]}
    assert len(placed & EXTRA_KINDS) >= 5, placed
    assert not [r["id"] for r in records() if r["kind"] in EXTRA_KINDS and r.get("gate", "open") != "open"]
    on_side = {x["id"] for sd in sides for x in sd["rooms"]}
    assert {r["id"] for r in records() if r["kind"] in EXTRA_KINDS} <= on_side
    walked = C.walked(DOC, DS, slot1())[0]
    paid = {r["id"] for r in C.clock_rooms(DOC, DS, 1, walked)}
    assert not paid & on_side
    bank = next(r for r in records() if r["kind"] == "bank_vault")
    names = {r["id"] for r in records()}
    assert set(bank["params"]["clue_rooms"]) <= names


def test_three_secrets_two_cracked_one_balcony_each_with_a_relic_and_its_lore():
    found = [(r, s) for r in records() for s in r.get("secrets") or []]
    assert sorted(s["type"] for _r, s in found) == ["balcony", "cracked", "cracked"]
    relics = []
    for r, _s in found:
        p = r["params"]
        assert re.fullmatch(r"dsp_[a-z0-9_]+", p["relic"])
        assert p["lore"] and len(p["lore"]) <= 160 and all(32 <= ord(c) < 127 for c in p["lore"])
        assert len(p.get("relic_name", "")) <= 32
        relics.append(p["relic"])
    assert len(set(relics)) == 3


def test_the_shortcut_opens_back_from_the_warm_room_on_one_floor():
    far = [r for r in records() if r.get("shortcuts")]
    assert len(far) == 1
    lay = R.layout(DOC, DS, slot1())
    by_id = {r["id"]: r for r in lay}
    f, near = by_id[far[0]["id"]], by_id[far[0]["shortcuts"][0]["to"]]
    assert near["i"] < f["i"] and near["route"] == f["route"] == "main" and f["kind"] == "safe_room"
    df, dn = f["shortcut_doors"][0], near["shortcut_doors"][0]
    assert df["y"] == dn["y"] and df["c"] == dn["c"]


def test_four_distinct_variants_one_per_slot():
    vs = DS["variants"]
    assert len(vs) == 4 and len({v["id"] for v in vs}) == 4
    assert any(v.get("mirror") for v in vs) and any(v.get("seed") for v in vs)
    assert any(v.get("swap") for v in vs) and any(v.get("order") for v in vs)
    assert [R.variant_of(DOC, DS, s)["id"] for s in slots()] == [v["id"] for v in vs]
    shapes = {tuple((r["id"], r["xa"] - s["x0"], r["za"] - s["z0"], r["shape"]) for r in R.layout(DOC, DS, s)) for s in slots()}
    assert len(shapes) == 4
    d = next(v for v in vs if v.get("order"))
    top = [r["id"] for r in DS["rooms"]]
    assert sorted(d["order"]) == sorted(top) and d["order"] != top and d["order"][0] == top[0] and d["order"][-1] == top[-1]


# ------------------------------------------------------------------------------------------------- the prize


@pytest.fixture(scope="module")
def jar():
    import dungeon_prize as PZ
    labels = PZ.jar_labels()
    if labels is None:
        pytest.skip("no Cobblemon 1.8 jar")
    return labels


def test_the_prize_is_exactly_the_rosters_band_6_restricted_trio_and_nothing_below(jar):
    import dungeon_prize as PZ
    room = _prize_room()
    pz = room["params"]["prize"]
    entry = next(e for e in ROSTER["dungeons"] if e["id"] == "dragonspiral")
    assert pz["roster"] == "dragonspiral"
    assert entry["legendary_pool_by_band"] == {"6": ["kyurem", "reshiram", "zekrom"]} and not entry.get("rare_pool_by_band")
    # the room adds nothing of its own: the roster is the pool
    assert not {k for k in pz if k.endswith("_by_band")}, pz
    assert "species" not in room["params"], "no resident: the trio is the hidden prize"
    for b in range(1, 6):
        assert PZ.pool_at(DOC, room, b) is None, b
    pool, leg = PZ.pool_at(DOC, room, 6)
    assert leg is True and sorted(pool) == ["kyurem", "reshiram", "zekrom"]
    for sp in ("kyurem", "reshiram", "zekrom"):
        assert {"legendary", "restricted"} <= jar[sp], sp
    assert PZ.room_problems(DOC, DS, room) == []


def test_the_prize_spawns_at_band_6s_lower_cap_and_takes_the_beast_ball_only():
    import key_ball as KB
    s = slot1()
    files = D.build(DOC)
    base = "data/cobblers/function/dungeons/room/dragonspiral/%s/s%d/prize/" % (_prize_room()["id"], s["g"])
    spawns = {k: v for k, v in files.items() if k.startswith(base + "spawn_b")}
    assert spawns and all(k[len(base):].startswith("spawn_b6") for k in spawns), sorted(spawns)
    for v in spawns.values():
        assert "level=100 no_ai" in v and v.rstrip().endswith("prize/bind")
    assert "tag @s add %s" % KB.boss_tag() in files[base + "bind.mcfunction"].split("\n")
    assert KB.boss_problems(KB.load()) == []


# ------------------------------------------------------------------------------------------------- fights and variety


def test_every_trainer_rotates_teams_the_miniboss_species_and_the_boss_an_alternate_crew():
    for r in records():
        p = r.get("params") or {}
        if r["kind"] in ("stand", "gauntlet", "ambush"):
            assert DF.stand_problems(DOC, r) == [], r["id"]
            assert r["gate"] == "cleared"
            for t in p["trainers"]:
                assert "team_by_band" not in t
                assert all(len(v) >= 2 for v in t["team_pool_by_band"].values()), t["name"]
        elif r["kind"] == "miniboss":
            assert all(len(v) >= 2 for v in p["species_pool_by_band"].values())
            assert p["level_offset"] <= 0 and p.get("catchable") is True and r["gate"] == "cleared"
    bo = DS["boss"]
    assert bo["heal_between_stages"] is True and len(bo["stage_level_offsets"]) == 2
    for b in D.bands(DOC):
        crews = [bo["teams"][str(b["band"])]] + bo["teams_alt_by_band"][str(b["band"])]
        assert len(crews) >= 2
        for stages in crews:
            assert len(stages) == 2 and len({c[-1] for c in stages}) == 1, "one ace, last in both stages"


def _named():
    out = set()
    for r in variant_records():
        p = r.get("params") or {}
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for teams in t.get("team_pool_by_band", {}).values():
                out |= {x for team in teams for x in team}
        out |= set(p.get("species", [])) if r["kind"] == "nest" else set()
        for v in p.get("species_pool_by_band", {}).values():
            out |= set(v)
    bo = DS["boss"]
    for crews in list(bo["teams"].values()) + [c for alts in bo["teams_alt_by_band"].values() for c in alts]:
        out |= {x for c in crews for x in c}
    return out


def test_every_species_is_in_the_jar_and_none_is_a_doll_a_legend_or_misassembled(jar):
    named = _named()
    assert not sorted(x for x in named if x not in jar), "missing from the jar"
    text = (ROOT / "docs" / "research" / "COBBLEVERSE_COMPATIBILITY.md").read_text(encoding="utf-8")
    m = re.search(r"^(arctibax, blacephalon[^\n]*)$", text, re.M)
    dolls = {s.strip().rstrip(".") for s in m.group(1).split(",")}
    bad = {"pidgeot", "talonflame", "arbok", "crobat", "cofagrigus", "skarmory", "tyranitar", "garganacl", "goodra",
           "primarina", "nidoking", "turtonator", "appletun", "archaludon"}
    assert not named & (dolls | bad), named & (dolls | bad)
    assert not [x for x in named if jar[x] & {"legendary", "mythical", "ultra_beast", "paradox"}]


# ------------------------------------------------------------------------------------------------- the walk


def test_the_dragonspiral_builds_and_walks_with_no_problem_in_every_variant_and_branch():
    assert R.problems(DOC, DS) == []
    assert not [p for p in D.problems(DOC) if "dragonspiral" in p]


def test_it_builds_its_functions_and_its_shell_fits_the_chain():
    s = slot1()
    D.build(DOC)
    assert R.chain_problems(DOC, DS, s) == []
    assert 0.3e6 < D.shell_blocks(DOC, s) < 1.2e6


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_is_in_its_slot_on_the_trail_clear_of_the_other_rips():
    f = DS["rip"]["frame"]
    cx = (f["x0"] + f["x1"]) / 2
    assert abs(cx - 1600) <= 10 and abs(f["z"] - 4118) <= 4
    for o in DOC["dungeons"]:
        if o["id"] == "dragonspiral" or "frame" not in o.get("rip", {}):
            continue
        of = o["rip"]["frame"]
        assert f["x0"] > of["x1"] + 4 or f["x1"] < of["x0"] - 4 or abs(f["z"] - of["z"]) > 6, o["id"]
    mine = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]["route1_old_mine"]
    x0, z0, x1, z1 = mine["plan"]["footprint"]["rect"]
    assert f["x0"] > x1 + 10
    cx_, cy, cz = DS["rip"]["click"]
    assert cz == f["z"] + 1 and cy == f["y"] and cx_ == (f["x0"] + f["x1"]) // 2
    _ox, _oy, oz, _ = DS["rip"]["outside"]
    assert oz - 0.5 > cz + 1.5


def test_the_rip_is_on_the_heightmaps_ground_and_not_in_water():
    try:
        import ground as GR
        g = GR.load()
    except Exception as e:  # noqa: BLE001
        pytest.skip("no heightmap: %s" % e)
    f = DS["rip"]["frame"]
    assert {g(x, z) + 1 for x in range(f["x0"], f["x1"] + 1) for z in (f["z"], f["z"] + 1)} == {f["y"]}
    ox, oy, oz, _ = DS["rip"]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy
    sea = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]
    assert f["y"] - 1 > sea


def test_the_slots_follow_the_dungeons_index_and_do_not_overlap():
    doc = copy.deepcopy(DOC)
    i = [d["id"] for d in doc["dungeons"]].index("dragonspiral")
    per = doc["engine"]["slots"]["per_dungeon"]
    assert [s["g"] for s in D.slots(doc) if s["dungeon"]["id"] == "dragonspiral"] == list(range(i * per + 1, i * per + per + 1))
    assert not [p for p in D.problems(doc) if "meets" in p]
