"""The Night Shift at full length (unit DG-NS, 2026-10-09): data/dungeons.json `night_shift` on the room kit, and its
clock from tools/dungeon_clock.py.

The builder's own tests (the dungeon's independent audit is another agent's). They build the record, walk it with the
kit's walk check, measure its walked length, check that every room kind the owner named is in it and every species
is in the Cobblemon 1.8.0 jar, and hold the clock to the formula. The MUTATIONS change the GENERATOR (the clock's
fight pace, the per-dungeon clock lookup, the walk's jumps) and leave data/dungeons.json alone.

Not covered: anything in a running Minecraft. The fight kinds (stand, gauntlet, miniboss, nest, habitat, the healer)
and the puzzle and vault are other units'; until they merge those rooms build as themed empty rooms.
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
import dungeon_audit as DA  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_rooms as R  # noqa: E402

DOC = D.load()
NS = next(d for d in DOC["dungeons"] if d["id"] == "night_shift")
ROOMS = NS["rooms"]
OWNER_KINDS = ("maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss")
OURS = ("gauntlet", "vault", "dark_room", "collapse_bridge", "safe_room")      # ambush counts as gauntlet
FIGHTS = ("stand", "gauntlet", "ambush", "miniboss", "boss_arena")             # rooms whose fight gates the way on
CONNECTORS = ("drift", "stairs")
ULTRA_BEASTS = {"nihilego", "buzzwole", "pheromosa", "xurkitree", "celesteela", "kartana", "guzzlord", "poipole",
                "naganadel", "stakataka", "blacephalon"}


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


# ------------------------------------------------------------------------------------------------- build and walk


def test_the_night_shift_is_on_rooms_builds_and_walks_with_no_problem():
    assert NS["theme"] == "mine" and "spine" not in NS
    assert DOC["dungeons"][0]["id"] == "night_shift", "the Night Shift stays dungeon 1 (its slots are rows 1-4)"
    doc = ns_doc()
    assert D.problems(doc) == []
    files = D.build(doc)
    assert any("/shells/s1/" in k for k in files)
    pt = D.points(doc, D.slots(doc)[0])
    for key in ("arrive", "back", "board", "threshold_x", "spot", "gate", "far"):
        assert pt[key] is not None, key
    assert pt["length"] <= DOC["engine"]["slots"]["strip_length"]


def test_its_walked_length_is_full_length_and_its_rooms_are_wide_and_its_connectors_short():
    rooms, total = DC.walked(DOC, NS)
    assert 1200 <= total <= 1600, total
    for r in rooms:
        if r["kind"] in CONNECTORS:
            assert r["x_len"] <= 40 and r["width"] >= 7, r["id"]
        elif r["kind"] not in ("entry_room", "exit_room"):
            assert 30 <= r["width"] <= 62, (r["id"], r["width"])


def test_every_room_kind_the_owner_named_is_in_it_and_three_of_ours_and_the_boss_and_the_exit():
    kinds = [kind_of(r) for r in ROOMS]
    for k in OWNER_KINDS:
        assert k in kinds, k
    assert sum(k in kinds for k in OURS) >= 3
    assert kinds[0] == "entry_room" and kinds[-2:] == ["boss_arena", "exit_room"]


def test_the_pacing_breathes_between_fights_and_puts_greed_and_the_rest_where_the_brief_says():
    kinds = [kind_of(r) for r in ROOMS]
    gating = [i for i, r in enumerate(ROOMS) if kind_of(r) in FIGHTS]
    for a, b in zip(gating, gating[1:]):
        between = [kinds[i] for i in range(a + 1, b) if kinds[i] not in CONNECTORS]
        assert between, "two fights back to back: %s and %s" % (ROOMS[a]["id"], ROOMS[b]["id"])
    rooms, total = DC.walked(DOC, NS)
    at, run = {}, 0
    for r in rooms:
        run += r["walk"]
        at[r["id"]] = run
    safe = next(r["id"] for r in ROOMS if r["kind"] == "safe_room")
    assert 0.55 <= at[safe] / total <= 0.8, at[safe] / total
    seam = kinds.index("resources")
    assert seam < kinds.index("gauntlet") < kinds.index("boss_arena"), "the seam comes before the hardest stretch"


# ------------------------------------------------------------------------------------------------- the params contract and species


def species_used():
    out = set()
    for r in ROOMS:
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for team in t["team_by_band"].values():
                out |= set(team)
        out |= set(p.get("species", [])) if isinstance(p.get("species"), list) else ({p["species"]} if "species" in p else set())
        out |= set(p.get("species_by_band", {}).values())
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
    by = {r["id"]: r for r in ROOMS}
    for r in ROOMS:
        p = r.get("params", {})
        k = kind_of(r)
        if k in ("stand", "gauntlet"):
            assert r.get("gate") == "cleared" and p["trainers"], r["id"]
            for t in p["trainers"]:
                assert t["name"] and sorted(t["team_by_band"]) == sorted(bands)
                assert all(len(t["team_by_band"][b]) == members[b] for b in bands), (r["id"], t["name"])
            if k == "gauntlet":
                tr = p["triggers"]
                assert len(tr) == len(p["trainers"]) and all(0 < x < 1 for x in tr) and tr == sorted(tr)
        elif k == "miniboss":
            assert sorted(p["species_by_band"]) == sorted(bands) and p["level_offset"] <= 0 and p.get("catchable") is False
        elif k == "nest":
            assert p["species"] and sorted(p["count_by_band"]) == sorted(bands) and len(p["level_spread"]) == 2
            assert max(p["count_by_band"].values()) <= 6
        elif k == "habitat":
            caps = {str(b["band"]): max(b["caps"]) for b in DOC["engine"]["bands"]}
            assert all(p["level_by_band"][b] <= caps[b] for b in bands), "never above the band's upper cap"
            assert p.get("fight_only", True) is True
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


def test_the_habitat_legendary_is_used_nowhere_else_and_is_no_ultra_beast():
    sp = next(r for r in ROOMS if r["kind"] == "habitat")["params"]["species"]
    assert sp not in ULTRA_BEASTS
    hits = []
    for f in (ROOT / "data").rglob("*.json"):
        if f.name in ("dungeons.json", "id_authorship.json"):
            continue
        if re.search(r'"%s"' % sp, f.read_text(encoding="utf-8"), re.I):
            hits.append(f.name)
    assert not hits, hits
    others = [r for d in DOC["dungeons"] if d["id"] != "night_shift" for r in d.get("rooms", [])
              if r.get("params", {}).get("species") == sp]
    assert not others


# ------------------------------------------------------------------------------------------------- the clock


def test_the_clock_is_the_formulas_and_the_design_table_says_the_same():
    want = DC.derive(DOC, NS)
    own = NS["clock_s_by_band"]
    for b, s in want.items():
        assert s <= own[b] <= s + 120, (b, own[b], s)
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


def test_mutating_the_walk_to_forbid_jumps_makes_the_collapse_unwalkable_and_the_measure_refuses(monkeypatch):
    real = DC.walk_distance
    monkeypatch.setattr(DC, "walk_distance", lambda g, s, e, jumps=False, cls=None: real(g, s, e, False, cls))
    with pytest.raises(R.RoomError, match="collapse"):
        DC.walked(DOC, NS)
