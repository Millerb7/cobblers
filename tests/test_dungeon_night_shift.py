"""The Night Shift, pass 3 (unit DG3-NS, 2026-10-10; pass 2 was DG2-NS): data/dungeons.json `night_shift` re-authored
to the owner's pass-3 notes (docs/mechanics/DUNGEON_PASS2.md "Pass 3", DUNGEON_ROOMS.md 1b): two crossroads you can see
(the pit bottom THREE ways: danger, length or a puzzle; the onsetting two), an optional WING that rejoins (the old shaft:
a hard parkour guarding the Sump, where the hidden PRIZE is), two parkours (the Collapse six sections and 25 wide, the
ladders hard), the pay office inside the vault budget; and everything pass 2 made true: rooms of many shapes, a route
that climbs, drops, doubles back and turns across the strip, three secrets with relics and lore, a shortcut, four
variants, the Collapse set piece and the clock from tools/dungeon_clock.py.

The builder's own tests (the dungeon's independent audit is another agent's; the brief that asked for them is the
orchestrator's). They build the record, walk it with the kit's walk check in every variant, measure its walked length,
check that every room kind the owner named is in it and every species is in the Cobblemon 1.8.0 jar, and hold the clock
to the formula. The MUTATIONS change the GENERATOR (the clock's fight pace, the per-dungeon clock lookup, the walk's jumps,
the fork's join, the secrets' placement, the clock's optional-route rule, the greed price of a chest) and leave
data/dungeons.json alone.

Not covered: anything in a running Minecraft (the looks, the rumour, the prize's spawn and the Beast Ball key).
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
import dungeon_audit as DA  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_rooms as R  # noqa: E402

DOC = D.load()
NS = next(d for d in DOC["dungeons"] if d["id"] == "night_shift")
ITEMS = R.flatten(NS)
ALL = [it["rec"] for it in ITEMS]                                   # every room, routes and the side room included
MAIN = [it["rec"] for it in ITEMS if it["route"] == "main"]
OWNER_KINDS = ("maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss")
OURS = ("gauntlet", "vault", "dark_room", "collapse_bridge", "safe_room")      # ambush counts as gauntlet
FIGHTS = ("stand", "gauntlet", "ambush", "miniboss", "boss_arena")             # rooms whose fight gates the way on
CONNECTORS = ("drift", "stairs")
ULTRA_BEASTS = {"nihilego", "buzzwole", "pheromosa", "xurkitree", "celesteela", "kartana", "guzzlord", "poipole",
                "naganadel", "stakataka", "blacephalon"}
SETPIECE_ALLOWANCE_S = 25      # clock_why: one fall onto the Collapse's catch floor, which the tool does not price


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def ns_doc():
    doc = copy.deepcopy(DOC)
    doc["dungeons"] = [d for d in doc["dungeons"] if d["id"] == "night_shift"]
    return doc


def kind_of(r):
    return "gauntlet" if r["kind"] == "ambush" else r["kind"]


def ns_slots(doc=DOC):
    return [s for s in R._slots_for(doc) if s["dungeon"]["id"] == "night_shift"]


def main_walk(rooms):
    return sum(r["walk"] for r in rooms if r["route"] == "main")


# ------------------------------------------------------------------------------------------------- build and walk


def test_the_night_shift_is_on_rooms_builds_and_walks_with_no_problem_in_every_variant():
    assert NS["theme"] == "mine" and "spine" not in NS
    assert DOC["dungeons"][0]["id"] == "night_shift", "the Night Shift stays dungeon 1 (its slots are rows 1-4)"
    doc = ns_doc()
    assert D.problems(doc) == []          # every variant: layout, walk (every branch), pits, secrets, shortcut, clock
    files = D.build(doc)
    assert any("/shells/s1/" in k for k in files)
    for s in D.slots(doc):
        pt = D.points(doc, s)
        for key in ("arrive", "back", "board", "threshold_x", "spot", "gate", "far"):
            assert pt[key] is not None, (s["g"], key)
        assert pt["length"] <= DOC["engine"]["slots"]["strip_length"]


def test_its_main_route_is_full_length_and_its_rooms_are_wide_and_its_connectors_short():
    rooms, total = DC.walked(DOC, NS)
    path = sum(r["walk"] for r in DC.clock_rooms(DOC, NS, 1, rooms))    # the main route and the slower way of each fork
    assert 1400 <= path <= 1800, path
    assert total >= path + 400, "the faster ways, the pay office and the old shaft's wing are walked as well"
    for s in R.variant_slots(DOC, NS, ns_slots()):
        assert main_walk(DC.walked(DOC, NS, s)[0]) >= 1100, s["g"]
    built = {r["id"]: r for r in R.layout(DOC, NS, ns_slots()[0])}
    for r in ALL:
        b = built[r["id"]]
        if r["kind"] in CONNECTORS:
            assert b["length"] <= 40 and b["width"] >= 7, r["id"]
    for r in MAIN:
        if r["kind"] not in CONNECTORS + ("entry_room", "exit_room", "setpiece"):
            assert 28 <= r["width"] <= 62, (r["id"], r["width"])
    assert sum(r["kind"] in CONNECTORS for r in MAIN) <= 4, "the main route is rooms, not drifts"


def test_most_rooms_are_not_boxes_and_the_route_turns_climbs_drops_and_doubles_back():
    lay = R.layout(DOC, NS, ns_slots()[0])
    eligible = [r for r in lay if r["kind"] not in R.BOX_ONLY_KINDS]
    shaped = [r for r in eligible if r["shape"] != "box"]
    assert len(shaped) * 2 > len(lay) and len(shaped) >= len(eligible) - 4, [r["id"] for r in eligible if r["shape"] == "box"]
    assert len({r["shape"] for r in shaped}) >= 6
    sides = {x["side"] for r in lay for x in r["doors"]}
    assert sides == {"north", "south", "east", "west"}
    assert any(x["y"] - r["floor_in"] >= 4 and x["dir"] == "out" for r in lay for x in r["doors"]), "a climb to a landing"
    assert any(x["y"] - r["floor_in"] >= 12 and x["dir"] == "in" for r in lay for x in r["doors"]), "a drop from a landing"
    assert any(r["dir"] == "west" for r in lay if r["route"] == "main"), "the route doubles back"
    floors = {r["floor_in"] for r in lay}
    assert max(floors) - min(floors) >= 14

    def stacked(a, b):
        return not (a["xb"] < b["xa"] or b["xb"] < a["xa"] or a["zb"] < b["za"] or b["zb"] < a["za"])
    assert sum(stacked(a, b) for k, a in enumerate(lay) for b in lay[k + 1:]) >= 4, "rooms run under earlier rooms"


def test_every_room_kind_the_owner_named_is_in_it_and_three_of_ours_and_the_boss_and_the_exit():
    kinds = [kind_of(r) for r in ALL]
    for k in OWNER_KINDS:
        assert k in kinds, k
    assert sum(k in kinds for k in OURS) >= 3
    main = [kind_of(r) for r in MAIN]
    assert main[0] == "entry_room" and main[-2:] == ["boss_arena", "exit_room"]


def test_the_pacing_breathes_between_fights_and_puts_greed_and_the_rest_where_the_brief_says():
    kinds = [kind_of(r) for r in MAIN]
    gating = [i for i, r in enumerate(MAIN) if kind_of(r) in FIGHTS]
    for a, b in zip(gating, gating[1:]):
        between = [kinds[i] for i in range(a + 1, b) if kinds[i] not in CONNECTORS]
        assert between, "two fights back to back: %s and %s" % (MAIN[a]["id"], MAIN[b]["id"])
    assert not any(kind_of(r) in FIGHTS for r in ALL if r not in MAIN), "no fight on a branch"
    rooms, _total = DC.walked(DOC, NS)
    at, run = {}, 0
    for r in rooms:
        if r["route"] == "main":
            run += r["walk"]
            at[r["id"]] = run
    safe = next(r["id"] for r in MAIN if r["kind"] == "safe_room")
    assert 0.6 <= at[safe] / run <= 0.8, at[safe] / run
    seam = kinds.index("resources")
    assert seam < kinds.index("gauntlet") < kinds.index("boss_arena"), "the seam comes before the hardest stretch"


# ------------------------------------------------------------------------------------------------- replayability


def crossroads():
    rs = NS["rooms"]
    return [(rs[k], rs[k + 1]) for k in range(len(rs) - 1) if rs[k]["kind"] == "crossroads"]


def by_route(rooms):
    out = {}
    for r in rooms:
        out.setdefault(r["route"], []).append(r)
    return out


def test_two_crossroads_each_open_a_fork_you_can_see_one_of_them_three_ways_each_way_by_its_own_wall():
    import dungeon_crossroads as XR
    xs = crossroads()
    assert len(xs) >= 2 and all(f["kind"] == "fork" for _x, f in xs)
    assert any(len(f["routes"]) == 3 for _x, f in xs), "one of them three ways"
    looks = set(XR.looks_of(R.theme_for(NS)))
    for _x, f in xs:
        ls = [rt["look"] for rt in f["routes"]]
        assert len(set(ls)) == len(ls) and set(ls) <= looks, ls
        assert all(rt.get("sign") for rt in f["routes"]), "every way is signed"
    for s in R.variant_slots(DOC, NS, ns_slots()):
        assert XR.geometry_checks(DOC, NS, s) == [], s["g"]           # from the hub every exit's opening is in sight
        lay = R.layout(DOC, NS, s)
        for x, f in xs:
            host = next(r for r in lay if r["id"] == x["id"])
            outs = [d for d in host["doors"] if d["dir"] == "out"]
            assert len(outs) == len(f["routes"]) and len({d["side"] for d in outs}) == len(outs), (s["g"], x["id"])
            routes = {"%s/%s" % (f["id"], rt["id"]) for rt in f["routes"]}
            assert {lay[d["to"]]["route"] for d in outs} == routes
            after = [r for r in lay if r["route"] == "main" and r["i"] > host["i"]][0]
            ins = [d for d in after["doors"] if d["dir"] == "in"]
            assert {lay[d["to"]]["route"] for d in ins} == routes, "every way rejoins at the room after the fork"


def test_the_pit_bottoms_three_ways_ask_different_things_danger_length_or_a_puzzle():
    f = next(f for _x, f in crossroads() if len(f["routes"]) == 3)
    kinds = {rt["id"]: [r["kind"] for r in rt["rooms"]] for rt in f["routes"]}
    danger = [k for k, ks in kinds.items() if any(R.flags_of(x)["pit"] for x in ks)]
    puzzle = [k for k, ks in kinds.items() if "puzzle" in ks]
    long_ = [k for k in kinds if k not in danger + puzzle]
    assert len(danger) == 1 and len(puzzle) == 1 and len(long_) == 1, kinds
    assert not any(rt.get("optional") for rt in f["routes"]), "all three are the way on"
    long_rt = next(rt for rt in f["routes"] if rt["id"] == long_[0])
    assert all(r.get("gate", "open") == "open" for r in long_rt["rooms"]), "the long way asks nothing but walking"
    for s in R.variant_slots(DOC, NS, ns_slots()):
        rooms = DC.walked(DOC, NS, s)[0]
        br = by_route(rooms)
        walk = {k: sum(r["walk"] for r in br["%s/%s" % (f["id"], k)]) for k in kinds}
        assert walk[long_[0]] > walk[danger[0]], (s["g"], walk)
        cost = {k: sum(DC.required(DOC, NS, 1, br["%s/%s" % (f["id"], k)]).values()) for k in kinds}
        assert cost[danger[0]] - DC.CUES_S > walk[danger[0]] / DC.WALK_BPS, "the danger is priced as a fall"
        paid = {r["route"] for r in DC.clock_rooms(DOC, NS, 1, rooms)}
        assert "%s/%s" % (f["id"], max(cost, key=cost.get)) in paid, "the clock covers the slowest way"


def test_the_side_room_is_an_optional_dead_end():
    sides = [r for r in NS["rooms"] if r["kind"] == "side"]
    assert sides
    lay = R.layout(DOC, NS, ns_slots()[0])
    for sd in sides:
        last = [r for r in lay if r["route"] == sd["id"]][-1]
        assert last["last"] and not [x for x in last["doors"] if x["dir"] == "out"], sd["id"]
        assert last["gate"] == "open"
    paid = {r["id"] for b in DOC["engine"]["bands"]
            for r in DC.clock_rooms(DOC, NS, b["band"], DC.walked(DOC, NS)[0])}
    assert not paid & {r["id"] for sd in sides for r in sd["rooms"]}, "the clock does not pay for a side room"


def wing():
    f = next(f for _x, f in crossroads() if any(rt.get("optional") for rt in f["routes"]))
    return f, next(rt for rt in f["routes"] if rt.get("optional"))


def test_the_old_shaft_is_an_optional_wing_a_hard_parkour_guards_and_the_clock_never_pays():
    f, w = wing()
    assert any(not rt.get("optional") for rt in f["routes"]), "the other way is the way on"
    rooms = w["rooms"]
    ks = [r["kind"] for r in rooms]
    assert 3 <= len(rooms) <= 4 and ks.count("parkour") == 1 and ks.count("habitat") == 1, ks
    assert ks.index("parkour") < ks.index("habitat"), "the hard parkour guards the habitat"
    assert all(k in CONNECTORS for k in ks[ks.index("habitat") + 1:]), "the habitat is the wing's end (then the road back)"
    hab = rooms[ks.index("habitat")]
    assert hab.get("secrets") and hab.get("gate", "open") == "open", "a secret in the wing; nothing waits on the prize"
    ids = {r["id"] for r in rooms}
    walks = [DC.walked(DOC, NS, s)[0] for s in R.variant_slots(DOC, NS, ns_slots())]
    for rooms_w in walks:
        assert sum(r["walk"] for r in rooms_w if r["id"] in ids) >= 250, "an immense wing, walked by the check"
        for b in DOC["engine"]["bands"]:
            assert not {r["id"] for r in DC.clock_rooms(DOC, NS, b["band"], rooms_w)} & ids, "the clock never pays it"
    lay = R.layout(DOC, NS, ns_slots()[0])
    assert all(r["optional"] for r in lay if r["id"] in ids)


def test_mutating_the_clock_to_pay_optional_routes_makes_the_authored_clock_too_short(monkeypatch):
    real = DC.clock_rooms

    def pays_wing(doc, d, band, rooms):          # the optional route counted as if it were on the way on
        return real(doc, d, band, [dict(r, route="main") if r.get("optional") else r for r in rooms])
    monkeypatch.setattr(DC, "clock_rooms", pays_wing)
    bad = DC.clock_problems(DOC, NS)
    assert any("under the derived" in p for p in bad), bad[:2]


def secrets():
    return [(r, s) for r in ALL for s in r.get("secrets") or []]


def prize_rooms():
    return [r for r in ALL if (r.get("params") or {}).get("prize")]


def test_the_prize_is_hidden_at_the_wings_end_rare_before_the_beast_ball_stage_and_volcanion_from_it():
    import dungeon_prize as PZ
    habs = prize_rooms()
    assert len(habs) == 1
    hab = habs[0]
    _f, w = wing()
    assert hab in w["rooms"], "the prize is in the optional wing, never on the way on"
    pz = hab["params"]["prize"]
    lf = PZ.legendary_from(DOC)
    nb = len(DOC["engine"]["bands"])
    assert sorted(pz["rare_by_band"], key=int) == [str(b) for b in range(1, lf)]
    assert sorted(pz["legendary_by_band"], key=int) == [str(b) for b in range(lf, nb + 1)]
    assert set(pz["legendary_by_band"].values()) == {"volcanion"}, "the dungeon's own legendary (D18)"
    assert "species" not in hab["params"], "no resident: the legendary is a find, not a fixture"
    assert not [r["id"] for r in ALL if (r.get("params") or {}).get("species") == "volcanion"]
    assert PZ.room_problems(DOC, NS, hab) == []                       # the jar's labels: rare is no legendary, and back
    labels = PZ.jar_labels()
    if labels is not None:
        assert not any(labels[s] & PZ.LEGEND_LABELS for s in pz["rare_by_band"].values())
        assert labels["volcanion"] & PZ.LEGEND_LABELS
    files = D.build(ns_doc())
    for s in D.slots(ns_doc()):
        base = "data/cobblers/function/dungeons/room/night_shift/%s/s%d/prize/" % (hab["id"], s["g"])
        bind = files[base + "bind.mcfunction"]
        assert "cobblers.key_boss" in bind and "cobblers.key_boss" not in files[base + "rare_bind.mcfunction"]
        for band in range(1, nb + 1):
            want = (pz["legendary_by_band"] if band >= lf else pz["rare_by_band"])[str(band)]
            assert 'species:"%s"' % want in files[base + "spawn_b%d.mcfunction" % band], (s["g"], band)
        start = files["data/cobblers/function/dungeons/slot/s%d/start.mcfunction" % s["g"]]
        assert "random value 1..100" in start, "rolled per run at the threshold: not there every run"


def test_the_secrets_a_cracked_face_and_a_balcony_each_with_a_relic_and_lore():
    # the relic rules (DG2-RELICS): a room with ONE secret carries relic / lore / relic_name in its own params, a room
    # with two in each secret record; every secret has one; no relic on a room without a secret
    ss = secrets()
    assert len(ss) >= 2 and {s["type"] for _r, s in ss} >= {"cracked", "balcony"}

    def holder(r, s):
        return r["params"] if len(r["secrets"]) == 1 else s
    relics = [holder(r, s)["relic"] for r, s in ss]
    assert len(set(relics)) == len(relics) and all(re.fullmatch(r"ns_[a-z0-9_]+", x) for x in relics)
    assert not [r["id"] for r in ALL if (r.get("params") or {}).get("relic") and not r.get("secrets")]
    for r, s in ss:
        h = holder(r, s)
        lore = h["lore"]
        assert 20 <= len(lore) < 160 and all(32 <= ord(c) < 127 for c in lore), (s["id"], len(lore))
        assert 1 <= len(re.findall(r"[.!?]['\"]?(\s|$)", lore)) <= 2, s["id"]
        assert 0 < len(h.get("relic_name", "x")) <= 32
    for s in R.variant_slots(DOC, NS, ns_slots()):
        for b in R.slot_build(DOC, NS, s):
            want = b.room.get("secrets") or []
            if not want:
                continue
            assert len(b.anchors.get("secret", [])) == len(want), (s["g"], b.room["id"])
            cracked = sum(x.get("type") == "cracked" for x in want)
            assert len(b.anchors.get("secret_door", [])) == 2 * cracked, (s["g"], b.room["id"])


def test_the_shortcut_opens_from_the_far_room_back_into_an_earlier_one():
    order = [r["id"] for r in ALL]
    scs = [(r, c) for r in ALL for c in r.get("shortcuts") or []]
    assert len(scs) >= 1
    doc = ns_doc()
    files = D.build(doc)
    for r, c in scs:
        assert order.index(c["to"]) < order.index(r["id"]), "back toward the entry"
        for s in D.slots(doc):
            name = "dungeons/room/night_shift/%s/s%d/shortcut_%s" % (r["id"], s["g"], c["id"])
            assert any(k.endswith(name + ".mcfunction") for k in files), name


def test_four_variants_one_per_slot_each_plays_differently():
    vs = NS["variants"]
    assert len(vs) == 4 and len({v["id"] for v in vs}) == 4
    used = set()
    for v in vs:
        used |= {k for k in ("mirror", "seed", "swap", "order") if v.get(k)}
    assert used == {"mirror", "seed", "swap", "order"}
    slots = ns_slots()
    assert [R.variant_of(DOC, NS, s)["id"] for s in slots] == [v["id"] for v in vs]
    sigs = set()
    for s in slots:
        lay = R.layout(DOC, NS, s)
        sigs.add(tuple((r["id"], r["za"] - s["z0"], r["zb"] - s["z0"], r["shape"]) for r in lay))
    assert len(sigs) == 4, "two slots lay out the same"


def test_the_collapse_set_piece_is_the_climax_before_the_boss():
    sp = [r for r in ALL if r["kind"] == "setpiece"]
    assert len(sp) == 1 and sp[0]["params"]["piece"] == "collapse" and sp[0] in MAIN
    kinds = [r["kind"] for r in MAIN]
    i, boss = kinds.index("setpiece"), kinds.index("boss_arena")
    assert i < boss and all(k in CONNECTORS for k in kinds[i + 1:boss])
    assert kinds.index("safe_room") < i and kinds.index("gauntlet") < i
    files = D.build(ns_doc())
    assert any("/room/night_shift/%s/s1/tick" % sp[0]["id"] in k for k in files)


# ------------------------------------------------------------------------------------------------- the params contract and species


def species_used():
    out = set()
    for r in R.all_records(NS):
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for team in t["team_by_band"].values():
                out |= set(team)
        out |= set(p.get("species", [])) if isinstance(p.get("species"), list) else ({p["species"]} if "species" in p else set())
        out |= set(p.get("species_by_band", {}).values())
        for key in ("rare_by_band", "legendary_by_band"):
            out |= set((p.get("prize") or {}).get(key, {}).values())
    for stages in NS["boss"]["teams"].values():
        for s in stages:
            out |= set(s)
    return out


def test_every_species_is_in_the_cobblemon_jar():
    import battle_sim as B
    try:
        jar = B.find_jar()
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar here")
    sp, _m, _c = B.load_pack(jar)
    missing = sorted(s for s in species_used() if B.key(s) not in sp)
    assert not missing, missing


def test_the_params_follow_the_contract():
    bands = [str(b["band"]) for b in DOC["engine"]["bands"]]
    members = DOC["engine"]["stands"]["members_by_band"]
    by = {r["id"]: r for r in ALL}
    for r in ALL:
        p = r.get("params", {})
        k = kind_of(r)
        if k in ("stand", "gauntlet"):
            assert r.get("gate") == "cleared" and p["trainers"], r["id"]
            for t in p["trainers"]:
                assert t["name"] and sorted(t["team_by_band"]) == sorted(bands)
                eased = t.get("members_eased_by_band") or {}
                assert all(len(t["team_by_band"][b]) == members[b] - eased.get(b, 0) for b in bands), (r["id"], t["name"])
                assert not eased or t.get("members_eased_why"), (r["id"], t["name"])
            if k == "gauntlet":
                tr = p["triggers"]
                assert len(tr) == len(p["trainers"]) and all(0 < x < 1 for x in tr) and tr == sorted(tr)
        elif k == "miniboss":
            assert sorted(p["species_by_band"]) == sorted(bands) and p["level_offset"] <= 0 and p.get("catchable", True) is True   # the owner, 2026-10-10: every dungeon Pokemon catchable
        elif k == "nest":
            assert p["species"] and sorted(p["count_by_band"]) == sorted(bands) and len(p["level_spread"]) == 2
            assert max(p["count_by_band"].values()) <= 6
        elif k == "habitat" and "species" in p:
            caps = {str(b["band"]): max(b["caps"]) for b in DOC["engine"]["bands"]}
            assert all(p["level_by_band"][b] <= caps[b] for b in bands), "never above the band's upper cap"
            assert p.get("fight_only", False) is False   # the owner, 2026-10-10: a legendary is a prize, catchable from the Beast Ball band
        elif k == "habitat":
            assert p.get("prize") and r.get("gate", "open") == "open", r["id"]   # the prize's own test holds the rest
        elif k == "puzzle":
            assert p["variant"] in ("levers", "sequence", "plates") and p["penalty_s"] > 0
            assert 3 <= p.get("size", p.get("length", p.get("count", 0))) <= 6
            assert r["height"] >= (6 if p["variant"] == "sequence" else 5)
        elif k == "vault":
            assert r.get("gate", "open") == "open" and 1 <= p["chests"] <= 8 and p["clock_cost_s"] > 0
            assert r["length"] >= 4 * p["chests"] + 12
            assert all(len(p["loot_by_band"][b]) == p["chests"] for b in bands), "one stack per chest"
        elif k == "safe_room":
            assert p.get("healer") is True
    assert by["sump"].get("gate", "open") == "open" and by["powerhouse"]["params"]["clear"] == "pass", "the optional rooms"
    for v in NS["variants"]:
        for rid, over in (v.get("swap") or {}).items():
            p = dict(by[rid].get("params", {}), **over.get("params", {}))
            if by[rid]["kind"] == "puzzle":
                assert p["variant"] in ("levers", "sequence", "plates") and 3 <= p.get("length", p.get("size", 0)) <= 6


def test_two_parkours_the_collapse_six_sections_and_25_wide_on_the_way_on_the_ladders_hard_in_the_wing():
    pks = [r for r in ALL if r["kind"] == "parkour"]
    assert len(pks) == 2
    easy = [r for r in pks if not r["params"].get("hard")]
    hard = [r for r in pks if r["params"].get("hard") is True]
    assert len(easy) == 1 and len(hard) == 1
    _f, w = wing()
    assert hard[0] in w["rooms"] and easy[0] not in w["rooms"]
    assert 5 <= easy[0]["params"]["sections"] <= 6 and easy[0]["width"] >= 25, "the owner: longer"
    assert hard[0]["params"]["sections"] >= 5 and hard[0]["width"] >= 25
    for r in pks:
        assert r["length"] - 2 >= 30 * r["params"]["sections"] - 10, r["id"]     # DUNGEON_ROOMS.md 1b's interior
    for s in R.variant_slots(DOC, NS, ns_slots()):
        built = {b.room["id"]: b for b in R.slot_build(DOC, NS, s)}
        e, h = built[easy[0]["id"]].meta, built[hard[0]["id"]].meta
        assert len(e["ledges"]) == easy[0]["params"]["sections"] + 1 and e["fork"], (s["g"], "planned in full")
        assert len(h["ledges"]) == hard[0]["params"]["sections"] + 1 and not h["fork"], (s["g"], "no easy fork")


def test_the_pay_office_is_inside_the_vault_budget_and_a_dearer_chest_is_named():
    import dungeon_greed as DG
    vaults = [r for r in ALL if r["kind"] == "vault"]
    assert vaults
    assert not [x for x in DG.vault_over(DOC) if x[0] == "night_shift"], "every band, every chest"


def test_mutating_the_chest_price_up_puts_the_pay_office_over_the_budget(monkeypatch):
    import dungeon_greed as DG
    real = DG.chest_cp
    monkeypatch.setattr(DG, "chest_cp", lambda table, spec: None if real(table, spec) is None else 2 * real(table, spec))
    assert any(x[:2] == ("night_shift", "pay_office") for x in DG.vault_over(DOC))


def test_the_prize_legendary_is_used_nowhere_else_and_is_no_ultra_beast():
    sp = next(iter(set(prize_rooms()[0]["params"]["prize"]["legendary_by_band"].values())))
    assert sp not in ULTRA_BEASTS
    hits = []
    for f in (ROOT / "data").rglob("*.json"):
        if f.name in ("dungeons.json", "id_authorship.json"):
            continue
        if re.search(r'"%s"' % sp, f.read_text(encoding="utf-8"), re.I):
            hits.append(f.name)
    assert not hits, hits
    others = [r for d in DOC["dungeons"] if d["id"] != "night_shift" for r in R.all_records(d) if d.get("rooms")
              if r.get("params", {}).get("species") == sp]
    assert not others


# ------------------------------------------------------------------------------------------------- the clock


def test_the_clock_is_the_formulas_plus_the_set_piece_allowance_and_the_design_table_says_the_same():
    want = DC.derive(DOC, NS)
    own = NS["clock_s_by_band"]
    slack = float(DOC["engine"]["clock"]["slack_factor"])
    walks = [DC.walked(DOC, NS, s)[0] for s in R.variant_slots(DOC, NS, ns_slots())]
    for b in DOC["engine"]["bands"]:
        k = str(b["band"])
        req = max(sum(DC.required(DOC, NS, b["band"], DC.clock_rooms(DOC, NS, b["band"], w)).values()) for w in walks)
        assert own[k] == int(math.ceil((req + SETPIECE_ALLOWANCE_S) * slack / 60.0)) * 60, (k, own[k])
        assert want[k] <= own[k] <= want[k] + 120 and own[k] <= 3600, (k, own[k], want[k])
    assert 30 * 60 <= sum(DC.required(DOC, NS, 1, DC.clock_rooms(DOC, NS, 1, walks[0])).values()) <= 34 * 60
    assert "lockout_ticks" not in NS, "every band's clock is an hour or under: D17's hour applies"
    assert "%d s" % SETPIECE_ALLOWANCE_S in NS["clock_why"]
    assert DA.design_room_clocks()["night_shift"] == [own[str(b)] // 60 for b in range(1, 7)]
    assert DC.clock_problems(DOC, NS) == []


def test_the_generated_threshold_and_board_use_the_dungeons_own_clock():
    doc = ns_doc()
    files = D.build(doc)
    fns = DA.functions(files)
    got = {}
    for _f, ls in fns.items():
        for l in DA.body(ls):
            m = DA.BAND_CLOCK_RE.search(l)
            if m:
                got.setdefault(int(m.group(1)), set()).add(int(m.group(2)))
    unit = DOC["engine"]["clock"]["units_per_tick"] * 20
    assert got == {int(b): {s * unit} for b, s in NS["clock_s_by_band"].items()}
    assert DA.check_v12(files) == []
    board = D.board_text(doc, doc["dungeons"][0], D.slots(doc)[0])
    assert " ".join("%s:%d:00" % (b, s // 60) for b, s in sorted(NS["clock_s_by_band"].items())) in board


def test_a_dungeon_with_rooms_and_no_own_clock_is_named_by_the_warnings():
    doc = ns_doc()
    doc["dungeons"][0].pop("clock_s_by_band")
    assert any("no clock_s_by_band" in w for w in D.warnings(doc))
    assert not any("no clock_s_by_band" in w for w in D.warnings(ns_doc()))


# ------------------------------------------------------------------------------------------------- generator mutations


def test_mutating_the_clocks_fight_pace_up_makes_the_authored_clock_too_short_and_problems_says_so(monkeypatch):
    monkeypatch.setattr(DC, "FIGHT_BASE_S", DC.FIGHT_BASE_S * 2)
    bad = D.problems(ns_doc())
    assert any("under the derived" in p for p in bad), bad[:3]


def test_mutating_the_clock_lookup_back_to_the_bands_is_caught_by_the_audit_against_the_design_table(monkeypatch):
    monkeypatch.setattr(D, "clock_s", lambda d, b: int(b["clock_s"]))
    bad = DA.check_v12(D.build(ns_doc()))
    assert len([x for x in bad if "DUNGEON_ROOMS.md 7 (night_shift)" in x]) == 4, bad[:2]     # one per slot


def test_mutating_the_walk_to_forbid_jumps_makes_the_jump_rooms_unwalkable_and_the_measure_refuses(monkeypatch):
    real = DC.walk_distance
    monkeypatch.setattr(DC, "walk_distance", lambda g, s, e, jumps=False, cls=None: real(g, s, e, False, cls))
    with pytest.raises(R.RoomError, match="stulls|gantry|collapse|ladders"):
        DC.walked(DOC, NS)


def test_mutating_the_fork_join_so_the_safe_route_is_not_stretched_is_caught(monkeypatch):
    real = R._place

    def no_fit(doc, d, slot, i, r, inc, item, length_override=None):
        return real(doc, d, slot, i, r, inc, item, None if r.get("length") == "fit" else length_override)
    monkeypatch.setattr(R, "_place", no_fit)
    bad = D.problems(ns_doc())
    assert any(re.search(r"lamp_road|pump_road|haul_road|sump_road|powerhouse|haulage", p) for p in bad), bad[:3]


def test_mutating_the_cracked_secret_to_plain_rock_is_caught(monkeypatch):
    real = R._cracked

    def plain(room, side, cx, s):
        g = real(room, side, cx, s)
        if g is None:
            return g
        ops = g["ops"]
        g["ops"] = lambda wall, light, shp: ops(wall, light, dict(shp, secret_block=wall))
        return g
    monkeypatch.setattr(R, "_cracked", plain)
    bad = D.problems(ns_doc())
    assert any("s_face" in p or "lower_face" in p or "the_fall" in p for p in bad), bad[:3]


def test_the_new_rooms_are_placed_off_the_route_and_every_one_is_optional():
    """PLACE-ROOMS (2026-10-11, the owner: "I want to see the new rooms"): the Night Shift holds a bank vault, a fossil
    chamber and an egg room, each on a side entry (never the main route, never a fork route), gate open, never paid by
    the clock, in every variant; the vault's code is chalked in three main-route rooms before it."""
    new = {"bank_vault", "fossil_chamber", "egg_room"}
    for s in ns_slots():
        lay = R.layout(DOC, NS, s)
        mine = [r for r in lay if r["kind"] in new]
        assert sorted(r["kind"] for r in mine) == sorted(new), s["g"]
        for r in mine:
            assert r["route"] != "main" and "/" not in r["route"] and r["gate"] == "open", (s["g"], r["id"])
        bank = next(r for r in mine if r["kind"] == "bank_vault")
        by_id = {r["id"]: r for r in lay}
        clues = bank["params"]["clue_rooms"]
        assert len(clues) == 3 and all(by_id[c]["route"] == "main" and by_id[c]["i"] < bank["i"] for c in clues)
    rooms = DC.walked(DOC, NS)[0]
    paid = {r["id"] for b in DOC["engine"]["bands"] for r in DC.clock_rooms(DOC, NS, b["band"], rooms)}
    assert not paid & {r["id"] for r in rooms if r["kind"] in new}, "the clock never pays for an optional room"
