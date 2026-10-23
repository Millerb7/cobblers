"""The mine crews (data/mine_crews.json, tools/mine_crews.py, data/mine_crew_trainers.json).

Offline: the heightmap and the committed data, no world, no server. Nothing here proves a crew fights in a running game;
it proves the generated seats stand on open floor in the BUILT mine functions, that the table's levels and teams obey its
own rules, and that tools/route_trainers.py emits and places every member. The seat check replays the built functions
(tools/mine_networks_audit.py read_pack and replay) and imports none of the generator's geometry; the mutation tests change the
GENERATOR (its lane, its yaw) and leave the data alone, because a mutation of the record moves the expectation and the
output together and proves nothing about independence (CLAUDE.md "How to prove an audit is independent").
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import mine_crews as C                 # noqa: E402
import mine_networks as MN             # noqa: E402
import route_trainers as RT            # noqa: E402

TABLE = C.table()
DOC = json.loads(C.OUT.read_text(encoding="utf-8"))
SEATS = DOC["trainers"]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("mine_crews_pack")
    nets = MN.all_networks()
    MN.write(MN.load(), nets, out=out)
    geos = {L.net["id"]: C.Geometry(L, m) for L, m in nets}
    return {"out": out, "geos": geos}


def test_the_committed_seat_file_is_what_the_generator_writes(built):
    # reproducibility: data/mine_crew_trainers.json comes from the table and the geometry alone
    doc, fields = C.build(TABLE, built["geos"])
    assert doc == DOC, "data/mine_crew_trainers.json is stale: python tools/mine_crews.py write"
    declared = {f["id"]: f for f in json.loads(C.PROGRESSION.read_text(encoding="utf-8"))["quest_fields"]}
    assert all(declared.get(f["id"]) == f for f in fields)


def test_every_seat_passes_the_independent_check_on_the_built_functions(built):
    problems = C.check(built["out"])
    assert problems == [], "\n".join(problems[:10])


def test_the_check_reads_the_built_functions_and_not_the_generators_geometry():
    # the check is the second reader: it must not import Layout, Model or the growth, or it shares the derivation
    src = Path(C.__file__).read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "check")
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    assert not names & {"Layout", "Model", "Geometry", "all_networks", "geometries", "main_candidates", "stope_candidates"}
    assert "read_pack" in names and "replay" in names


def test_a_generator_that_seats_on_the_rail_lane_is_caught(built, monkeypatch):
    # mutate the GENERATOR (the lane a main-line seat takes), not the data: the middle lane carries the rail
    # (and its own fitting guard, which would otherwise refuse the rail cell before the check ever saw it)
    monkeypatch.setattr(C, "LANE_OFFSETS", (0,))
    monkeypatch.setattr(C.Geometry, "open_cell", lambda self, x, y, z: (x, y, z) in self.m.air)
    doc, _f = C.build(TABLE, built["geos"])
    problems = C.check(built["out"], doc=doc)
    assert any("not open air" in p or "rail" in p for p in problems), problems[:5]


def test_a_generator_that_faces_the_wrong_way_is_caught(built, monkeypatch):
    # mutate the GENERATOR's yaw: a quarter turn from the drift's axis puts a trainer's gaze into the wall
    real = C.yaw_of
    monkeypatch.setattr(C, "yaw_of", lambda f: real((f[1], -f[0])))
    doc, _f = C.build(TABLE, built["geos"])
    problems = C.check(built["out"], doc=doc)
    assert any("faces a wall" in p for p in problems), problems[:5]


def test_the_check_catches_a_seat_moved_into_the_rock(built):
    doc = json.loads(json.dumps(DOC))
    e = doc["trainers"][0]
    e["seat"] = [e["seat"][0] + 4, e["seat"][1], e["seat"][2]]
    problems = C.check(built["out"], doc=doc)
    assert any("not open air" in p for p in problems), problems[:5]


# ------------------------------------------------------------------ the table's own rules

def test_each_network_has_eight_to_fourteen_and_exactly_one_shift_boss_at_the_deepest_stope():
    for net in TABLE["networks"]:
        crew = net["crew"]
        assert 8 <= len(crew) <= 14, net["id"]
        bosses = [s for s in crew if s["role"] == "shift_boss"]
        assert len(bosses) == 1 and bosses[0]["place"] == "stope"
        assert bosses[0]["level"] == max(s["level"] for s in crew), "the Shift Boss is not the deepest"
        assert sum(1 for s in crew if s["role"] == "foreman") == 1
        assert sum(1 for s in crew if s["place"] == "stope") >= 2


def test_levels_rise_with_depth_inside_the_networks_band():
    for net in TABLE["networks"]:
        lo, hi = net["band"]
        crew = sorted(net["crew"], key=lambda s: (s["level"], s["role"] == "shift_boss"))
        aces = [max(m["level"] for m in s["normal"]) for s in crew]
        assert all(lo <= m["level"] <= hi for s in crew for m in s["normal"]), net["id"]
        assert aces == sorted(aces) or all(b >= a - 1 for a, b in zip(aces, aces[1:])), (net["id"], aces)
        boss = next(s for s in crew if s["role"] == "shift_boss")
        assert max(m["level"] for m in boss["normal"]) == max(aces) == hi, "the boss should top the band"
        # the first level's crew starts at the band's floor: a player's first fight is the easiest
        assert min(aces) == lo


def test_the_bands_follow_the_badge_order():
    bands = {n["id"]: n["band"] for n in TABLE["networks"]}
    # Ridgeback (gym 4's town), the Hollow Seam (between gyms 6 and 7), the Craters (Fossick, gyms 7 to 8)
    assert bands["mn_ridgeback"][1] < bands["mn_gorge"][0] <= bands["mn_craters"][0] < bands["mn_gorge"][1] < bands["mn_craters"][1]


def test_team_shapes_and_challenge_levels():
    for net in TABLE["networks"]:
        for s in net["crew"]:
            n = len(s["normal"])
            want = {"miner": (2, 3), "foreman": (4, 4), "shift_boss": (5, 5)}[s["role"]]
            assert want[0] <= n <= want[1], (s["id"], n)
            ch = C.challenge_team(s)
            assert len(ch) in (n, n + 1)
            assert [m["level"] for m in ch[:n]] == [m["level"] for m in s["normal"]]
            assert max(m["level"] for m in ch) == max(m["level"] for m in s["normal"]), "the extra member must not top the ace"
            assert all("heldItem" in m for m in ch)
            if s["role"] != "miner":
                assert len(ch) == n + 1, "the foreman and the Shift Boss get the extra Challenge member"


def test_every_member_is_rock_ground_steel_or_fire_and_knows_its_moves():
    # the check reads the Cobblemon 1.8 jar; on a machine without it the types cannot be read and this says so
    species, why = C.jar_species()
    if species is None:
        pytest.skip("no Cobblemon jar on this machine: %s" % why)
    bad = []
    for net in TABLE["networks"]:
        for s in net["crew"]:
            for m in s["normal"] + C.challenge_team(s):
                sp = species[why(m["species"])]
                ty = {t.lower() for t in (sp.get("primaryType"), sp.get("secondaryType")) if t}
                if not ty & C.TYPES:
                    bad.append((s["id"], m["species"], sorted(ty)))
                bad += [(s["id"], m["species"], mv) for mv in m["moveset"] if not C.legal(sp, mv, m["level"])]
    assert bad == []


def test_ids_are_unique_and_nobody_else_authors_them():
    ids = [s["id"] for n in TABLE["networks"] for s in n["crew"]]
    assert len(ids) == len(set(ids)) == len(SEATS)
    roster = {t["id"] for t in json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))["trainers"]}
    assert not set(ids) & roster, "the roster already carries a mine id: two authors"


def test_no_seat_is_on_a_route_the_owner_said_none_on_routes():
    # the owner, 2026-10-22: "trainers there [in the mines] ... none on routes": every seat is inside its network's box
    nets = {n["id"]: n["box"] for n in json.loads((ROOT / "data" / "mine_networks.json").read_text(encoding="utf-8"))["networks"]}
    for e in SEATS:
        x0, z0, x1, z1 = nets[e["network"]]
        assert x0 <= e["seat"][0] <= x1 and z0 <= e["seat"][2] <= z1, e["id"]
        assert e["seat"][1] < 110, "a mine seat is underground: %s" % e["id"]


# ------------------------------------------------------------------ the existing machinery takes them

def test_route_trainers_seats_summons_and_cycles_every_member():
    recs, seats, _fields = RT.load()
    seated = {s["id"] for s in seats}
    ids = {e["id"] for e in SEATS}
    assert ids <= seated and ids <= set(recs)
    placed = {p[0]: p for p in RT.placements()}
    assert all(placed[e["id"]][1:] == (tuple(e["seat"]), e["yaw"]) for e in SEATS)
    files = RT.files()
    for tid in ids:
        for rel in ("data/rctmod/trainers/%s.json", "data/rctmod/mobs/trainers/single/%s.json",
                    "data/rctmod/dialogs/trainers/single/%s.json", "data/cobblers/advancement/trainer/%s.json",
                    "data/rctmod/trainers/%s_challenge.json"):
            assert rel % tid in files, rel % tid
        mob = files["data/rctmod/mobs/trainers/single/%s.json" % tid]
        assert mob["forceBattleOnSight"] is True and mob["maxTrainerDefeats"] == 1 and mob["series"] == []


def test_r17_comes_after_the_mines_are_carved():
    # a trainer summoned into rock before R9MN has carved it would stand in stone
    import reapply
    try:
        ids = [s[0] for s in reapply.steps()]
    except BaseException as exc:      # steps() reads index.txt of packs that `reapply.py prepare` builds; absent here
        pytest.skip("reapply.steps() needs the prepared packs: %s" % str(exc)[:80])
    assert ids.index("R9MN") < ids.index("R17")
