"""The Compact HQ tower (tools/hq_tower.py, data/hq_tower.json, data/hq_trainers.json) and the finale's Scenes 1-4 as
data (data/progression.json, data/quests.json, data/dialogue.json).

The builder's own tests; an independent audit is a separate job. Needs the canonical heightmap for the build tests (the
city's build runs in memory); a skip names it. NOT covered, and it needs a running server: whether runmolang reads the
stage as the dialogues write it, the gates against two players at different stages, the NPCs and the seven fights.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import hq_tower as H  # noqa: E402

STAGE = "quest.main_worldshift_reveal.stage"
CODEX = ["rift_crisis_pending", "deep_handoff_received", "hq_crossed", "anchor_shutdown", "cradle_open",
         "rift_released", "league_recognized"]


def doc(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def stage_values():
    return next(f for f in doc("progression.json")["quest_fields"] if f["id"] == STAGE)["allowed_values"]


# ------------------------------------------------------------------ the story as data

def test_the_stage_enum_carries_codexs_sequence_in_its_order():
    vals = stage_values()
    assert [v for v in vals if v in CODEX] == CODEX
    # contiguous: nothing slips between two finale stages
    i = vals.index(CODEX[0])
    assert vals[i:i + len(CODEX)] == CODEX


def _transitions():
    q = next(q for q in doc("quests.json")["quests"] if q["id"] == "main_worldshift_reveal")
    return {t["id"]: t for t in q["transitions"]}


def _invocations(tid):
    out = []
    for c in doc("dialogue.json")["conversations"]:
        for n in c["nodes"]:
            for a in n.get("actions_after_acknowledge") or []:
                if a.get("transition") == tid:
                    out.append((c["id"], c["npc_id"], "line " + n["id"]))
            for r in n.get("responses") or []:
                for a in r.get("actions") or []:
                    if a.get("transition") == tid:
                        out.append((c["id"], c["npc_id"], "option " + r["id"]))
        for rule in c.get("entry_rules") or []:
            for a in rule.get("actions") or []:
                if a.get("transition") == tid:
                    out.append((c["id"], c["npc_id"], "entry"))
    return out


@pytest.mark.parametrize("tid,frm,to,npc", [
    ("record_deep_handoff_received", "rift_crisis_pending", "deep_handoff_received", "npc_finale_nia_calder"),
    ("record_hq_crossed", "deep_handoff_received", "hq_crossed", "npc_finale_brann_saye"),
    ("record_anchor_shutdown", "hq_crossed", "anchor_shutdown", "npc_finale_oren_pell"),
    ("record_cradle_open", "anchor_shutdown", "cradle_open", "npc_finale_elara_venn"),
])
def test_each_finale_stage_has_one_setter_from_the_stage_before_it(tid, frm, to, npc):
    t = _transitions()[tid]
    assert t["conditions"] == [{"kind": "progression_equals", "field": STAGE, "value": frm}]
    assert {"kind": "set_progression", "field": STAGE, "value": to} in t["effects"]
    calls = _invocations(tid)
    assert len(calls) == 1 and calls[0][1] == npc, calls
    # and nothing else in the quest writes that stage
    others = [x for x, tt in _transitions().items() if x != tid and any(
        e.get("field") == STAGE and e.get("value") == to for e in tt["effects"])]
    assert others == []
    # the NPC is one data/hq_tower.json seats
    assert npc in {n["id"] for n in H.load()["npcs"]}


def test_the_four_conversations_compile():
    import compile_dialogue as C
    for cid in ("dlg_main_finale_nia", "dlg_main_finale_brann", "dlg_main_finale_oren", "dlg_main_finale_elara"):
        quests, fields = None, None
        dl = doc("dialogue.json")
        conv = next(c for c in dl["conversations"] if c["id"] == cid)
        qd = {q["id"]: q for q in doc("quests.json")["quests"]}
        fields = {f["id"]: f for f in doc("progression.json")["quest_fields"]}
        out = C.compile_conversation(conv, qd, fields)
        assert out, cid


def test_the_relic_door_guard_still_admits_from_rift_crisis_pending_on():
    """The four new stages sit after rift_crisis_pending, so the ring-0 guard's 'that stage or later' must list them:
    a player Nia has briefed is still let into the HQ's room (tools/relic_underground_audit.py's rule)."""
    vals = stage_values()
    want = vals[vals.index("rift_crisis_pending"):]
    t = _transitions()["relic_hq_admit"]
    assert t["conditions"][0]["values"] == want
    g = next(c for c in doc("dialogue.json")["conversations"] if c["id"] == "dlg_main_relic_hq_guard")
    assert g["entry_rules"][0]["when"]["values"] == want
    opt = next(r for n in g["nodes"] for r in n.get("responses") or [] if r["id"] == "r_go")
    assert opt["visible_when"]["values"] == want


# ------------------------------------------------------------------ the gates

def _molang():
    return next(l for l in H.gate_lines(H.load()) if "runmolang" in l)


@pytest.mark.parametrize("gate,first", [("door", "deep_handoff_received"), ("climb", "hq_crossed")])
def test_each_gate_tags_exactly_the_stages_from_its_own_on(gate, first):
    spec = H.load()
    g = spec["gates"][gate]
    assert g["from_stage"] == first
    vals = stage_values()
    mol = _molang()
    seg = mol.split("q.run_command('tag ' + q.player.uuid + ' add %s')" % g["tag"])[0]
    seg = seg.rsplit("? {", 1)[0].rsplit("(", 1)[-1] if gate == "door" else seg.rsplit(";", 2)[-1]
    named = {v for v in vals if "== '%s'" % v in seg}
    assert named == set(vals[vals.index(first):]), (gate, sorted(named))


def test_the_gates_move_only_unqualified_survival_players_inside_their_boxes():
    lines = H.gate_lines(H.load())
    tps = [l for l in lines if l.startswith("tp ")]
    assert len(tps) == 2
    for l in tps:
        sel = l.split()[1]
        assert "tag=!cobblers_hq_" in sel and "gamemode=!creative" in sel and "gamemode=!spectator" in sel
        assert sel.startswith("@a[x=")
    # the tags are refreshed over a box that holds both gated boxes
    spec = H.load()
    tb = spec["gates"]["tag_box"]
    for g in ("door", "climb"):
        b = spec["gates"][g]["box"]
        assert all(tb[i] <= b[i] for i in range(3)) and all(tb[i] >= b[i] for i in range(3, 6))


def test_the_door_box_holds_the_tower_and_its_doorway_and_not_the_set_back():
    spec = H.load()
    b = spec["gates"]["door"]["box"]
    t = spec["tower"]
    x0, z0, x1, z1 = t["box"]
    assert (b[0], b[2], b[3], b[5]) == (x0, z0, x1 + 1, z1)        # walls, interior and the section wall it cuts
    assert b[1] == t["base"] and b[4] >= t["top"] + 1
    for c in spec["door"]["cells"]:
        assert H._in(tuple(c), b)
    sx, sy, sz, _yaw = spec["gates"]["door"]["set_back"]
    # the selector's box is [x, x + dx + 1): a player centred on the set-back cell is wholly outside it
    assert sx - 0.3 >= b[3] + 1
    # nothing under y67: the relic site's stair runs under the tower
    assert b[1] >= 67


def test_the_climb_box_starts_above_the_briefing_hall():
    spec = H.load()
    b = spec["gates"]["climb"]["box"]
    s1 = spec["storeys"][H.storey_index(spec, "hq_s1")]
    s2 = spec["storeys"][H.storey_index(spec, "hq_s2")]
    assert b[1] == s2["floor"]                         # the foundry's floor: a player on the hall (y74..75.8) is under it
    assert spec["gates"]["climb"]["set_back"][1] == s1["floor"] + 1
    ix0, iz0, ix1, iz1 = spec["tower"]["interior"]
    assert (b[0], b[2], b[3], b[5]) == (ix0, iz0, ix1, iz1)


# ------------------------------------------------------------------ the trainers

def test_the_seven_are_seated_through_route_trainers():
    import route_trainers as RT
    seats = {t: (p, y) for t, p, y in RT.placements()}
    for t in H.trainers():
        assert seats[t["id"]] == (tuple(t["seat"]), t["yaw"])
    files = RT.files()
    for t in H.trainers():
        assert "data/rctmod/trainers/%s.json" % t["id"] in files
        assert any(l.startswith("# %s" % t["id"]) for l in files["data/cobblers/function/trainers/cycle.mcfunction"])


def test_the_teams_are_banded_under_the_league_cap_and_reuse_known_movesets():
    known = {}
    for r in doc("trainers.json")["trainers"]:
        for m in r.get("team") or []:
            known.setdefault(m["species"], []).append(m.get("moveset"))
    for t in H.trainers():
        assert t["team"] == t["rct"]["team"]
        for m in t["team"]:
            assert 55 <= m["level"] <= 59, (t["id"], m)
            assert m["moveset"] in known.get(m["species"], []), (t["id"], m["species"])


def test_npc_placements_name_the_four_classes():
    got = H.npc_placements()
    assert [c for c, _p, _k, _y in got] == ["dlg_main_finale_nia", "dlg_main_finale_brann", "dlg_main_finale_elara",
                                             "dlg_main_finale_oren"]
    assert all(k == "cobblers:" + n["id"] for (_c, _p, k, _y), n in zip(got, H.load()["npcs"]))


# ------------------------------------------------------------------ reapply

def test_reapply_runs_the_blocks_after_the_city_and_the_relic_site_and_the_npcs_after_r18ru():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.index('("R9DC"') < src.index('("R9RU"') < src.index('("R9HQ"') < src.index('("R9E"')
    assert src.index('("R18RU"') < src.index('("R18HQ"')
    assert '"hq_tower:build", "hq_tower.py", "build"' in src
    import reapply
    assert "cobblers_hq_tower" in reapply.SERVER_PACKS
    assert "cobblers_hq_tower" in reapply.WORLD_LOCAL            # the gate cycle moves players on its own tick


# ------------------------------------------------------------------ the build (the heightmap)

@pytest.fixture(scope="module")
def built():
    import ground as G
    import terrain as T
    s = T.env_source_root()
    try:
        G.Ground(s)
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)
    cells, plan, dc_spec = H.city(s)
    return s, cells, plan, dc_spec


def test_the_build_is_clean(built):
    s = built[0]
    _spec, W, probs, reach = H.build(s)
    assert probs == []
    assert len(W) > 400 and len(reach) > 500


def test_every_write_is_inside_the_tower_or_its_doorway(built):
    _s, cells, plan, dc_spec = built
    spec = H.load()
    W = H.writes(spec, cells)
    t = spec["tower"]
    ix0, iz0, ix1, iz1 = t["interior"]
    door = {tuple(c) for c in spec["door"]["cells"]}
    for p in W:
        assert p in door or (ix0 <= p[0] <= ix1 and iz0 <= p[2] <= iz1 and t["base"] <= p[1] <= t["top"]), p
    # the stair cuts nothing out of the walls
    assert all(cells.get(p, "minecraft:air") != "minecraft:air" for p in door)


def test_every_storey_has_a_flight_and_its_head_is_railed(built):
    _s, cells, _plan, _dc = built
    spec = H.load()
    st = H.stair_cells(spec)
    assert sorted(st) == list(range(len(spec["storeys"]) - 1))
    W = H.writes(spec, cells)
    for n, c in st.items():
        for (i, k, y) in c["holes"]:
            assert W[(3429 + i, y, 3304 + k)][0] == "minecraft:air"
        for (i, k, y) in c["rails"]:
            assert W[(3429 + i, y, 3304 + k)][0].startswith("minecraft:iron_bars")


def test_a_blocked_flight_breaks_the_walk(built, monkeypatch):
    """Mutate the generator, not the data: crates round the foundry's stair foot must fail the walk. (One crate on the
    foot alone does not: the first step is a one-block jump from the floor beside it, which a player can make.)"""
    _s, cells, _plan, _dc = built
    spec = H.load()
    real = H.furnishing

    def blocked(sp):
        f = real(sp)
        f["hq_s2"] = f["hq_s2"] + [(i, k, dy, H.BARREL) for (i, k) in ((8, 0), (7, 0), (7, 1)) for dy in (0, 1)]
        return f
    monkeypatch.setattr(H, "furnishing", blocked)
    W = H.writes(spec, cells)
    probs, _reach = H.check_walk(spec, W, cells)
    assert any("top storey" in p for p in probs), probs


def test_a_short_flight_fails_closed(monkeypatch):
    """A flight one step short of its storey's rise is refused, not built."""
    sides = dict(H.SIDES)
    sides["E"] = dict(sides["E"], steps=sides["E"]["steps"][:-1])
    monkeypatch.setattr(H, "SIDES", sides)
    with pytest.raises(SystemExit):
        H.stair_cells(H.load())


def test_a_seat_off_the_floor_is_named(built, monkeypatch):
    _s, cells, _plan, _dc = built
    spec = H.load()
    real = H.seats
    monkeypatch.setattr(H, "seats", lambda sp: [(k, i, n, (x, y + 2, z)) for (k, i, n, (x, y, z)) in real(sp)])
    W = H.writes(spec, cells)
    probs, _reach = H.check_walk(spec, W, cells)
    assert sum("does not stand on a floor" in p for p in probs) == len(real(spec))


def test_nia_stands_on_the_citys_sidewalk_and_a_lifted_seat_is_named(built):
    _s, cells, _plan, _dc = built
    spec = H.load()
    assert H.check_outside_seats(spec, cells) == []
    lifted = json.loads(json.dumps(spec))
    for n in lifted["npcs"]:
        if not n.get("storey"):
            n["at"][1] += 1
    assert any("no floor under it" in p for p in H.check_outside_seats(lifted, cells))
