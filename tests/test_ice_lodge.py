"""tools/ice_lodge_audit.py against tools/ice_lodge.py: the clean pack audits clean, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the independent
half of the proof is the mutation standard of CLAUDE.md, "How to prove an audit is independent": every tamper case
below changes the generator's CODE (a function wrapped, its guard switched off) and leaves data/ice_lodge.json, the
spawn policy and the heightmap alone. A record-side mutation moves the expectation and the output together and proves
nothing. The builder's own `guards` are switched off for those cases, because the point is what the AUDIT catches.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT, or the committed .claude/settings.json); a skip names it. NOT
covered, and it needs a running server: that the fills land, that ice stays where no light reaches it, that the
open-water treasure check holds at the Lead, that water spawns anything, that the holekeeper renders and talks.
"""
import json
import math
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ice_lodge as L  # noqa: E402
import ice_lodge_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "ice_lodge.json").read_text(encoding="utf-8"))


def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def run(ground, out, guards_off=False, steps=True):
    doc = L.load()
    if guards_off:
        orig = L.guards
        L.guards = lambda *a, **k: {"nearest_authored_point": 0}
        try:
            written, _pl, _m = L.files(doc, ground)
        finally:
            L.guards = orig
    else:
        written, _pl, _m = L.files(doc, ground)
    L.write(written, out)
    rep = A.audit(REC, ground, out, L.placement_steps(doc) if steps else None)
    if os.environ.get("ICE_TEST_VERBOSE"):
        print("  audit:", len(rep.errors), "problem(s):", [e[:110] for e in rep.errors[:2]])
    return rep


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


def test_the_committed_lodge_is_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []
    assert rep.notes and "blocks replayed" in rep.notes[0]


# ------------------------------------------------------------------------------------- the record and its neighbours
def test_the_premise_is_the_measured_one():
    # the owner's brief said the hut "sits at the major river's source"; the water data says the trunk's cut head is far
    # from the hut, so the tarn is authored and the keeper says where the creek comes up
    rv = jload("rivers.json")
    trunk = next(c for c in rv["courses"] if c["id"] == "major_river_trunk")
    hx, hz = trunk["source"]["x"], trunk["source"]["z"]
    pc = jload("placements.json")["settlements"]["merian_hut"]["plan"]["anchors"][0]["rect"]
    centre = ((pc[0] + pc[2]) / 2, (pc[1] + pc[3]) / 2)
    d = math.hypot(hx - centre[0], hz - centre[1])
    assert 600 < d < 800, d
    assert (hx, hz) == (3132, 1632)
    lm = next(l for l in jload("landmarks.json")["landmarks"] if l["id"] == "merian")
    assert "no basin holds water" in lm["status_basis"]
    assert REC["premise_check"]["river_head"].startswith("the major river's cut course")


def test_the_hut_keeps_what_other_systems_rely_on():
    # the records the brief named, unchanged by this unit: the Centre's id and rect, the waystone, the blackout
    # checkpoint, the larder, the ambient town's 6, and no write of this pack inside any of them
    pl = jload("placements.json")["settlements"]["merian_hut"]["plan"]
    assert [a["id"] for a in pl["anchors"]] == ["merian_hut_pokecenter", "merian_woodshed", "merian_stable"]
    assert pl["waystone"]["position"] == [2800, 1034]
    assert jload("blackout.json")["checkpoints"]["ids"]["merian_hut_pokecenter"] == 10
    assert any(s["id"] == "merian_hut_larder" for s in jload("markets.json")["stalls"])
    at = jload("ambient_towns/merian_hut.json")
    assert at["counts"]["total"] == 6 and len(at["workers"]) == 2 and len(at["situations"]) == 2


def test_nothing_written_is_near_the_huts_own_buildings(ground):
    # a list-free check of our list: every [x, z] or [x, y, z] in the hut's records and its ambient file, every rect
    pl = jload("placements.json")["settlements"]["merian_hut"]["plan"]
    pts = [tuple(pl["waystone"]["position"]), tuple(pl["npc"]["at"])]
    rects = [a["rect"] for a in pl["anchors"]] + [pl["plaza"]["rect"]]
    pc = jload("plaza_centres.json")["towns"]["merian_hut"]
    rects.append(pc["square"]["rect"])
    for st in pc["stalls"]:
        pts += [tuple(st["at"][::2]), tuple(st["keeper_at"][:3:2])]
    pts += [tuple(p["at"]) for p in pc["pieces"]]
    pts.append(tuple(pc["centrepiece"]["at"]))
    am = jload("ambient_towns/merian_hut.json")
    for w in am["workers"]:
        pts += [tuple(w["at"]), tuple(w["face"])]
    for s in am["situations"]:
        pts.append((s["at"][0], s["at"][2]))
    doc = L.load()
    pln = L.plan(doc, ground)
    cols = {(x, z) for (x, _y, z) in pln["blocks"]}
    for (x, z) in pts:
        assert min(max(abs(x - a), abs(z - b)) for a, b in cols) >= 4, (x, z)
    for x0, z0, x1, z1 in rects:
        near = [c for c in cols if x0 - 3 <= c[0] <= x1 + 3 and z0 - 3 <= c[1] <= z1 + 3]
        assert not near, (x0, z0, x1, z1, near[:3])


def test_the_probes_in_the_world_file_are_the_plans(ground):
    doc = L.load()
    pl = L.plan(doc, ground)
    want = L.presence_probes(doc, pl)
    have = {"ice_lodge": jload("world_probes.json")["places"]["ice_lodge"]}
    assert want == have, "regenerate: python tools/ice_lodge.py probes --write"
    assert len(have["ice_lodge"]) >= 25


def test_the_policy_allows_water_here_and_only_water():
    pol = jload("spawn_block_policy.json")["whitelist"]
    mine = [w for w in pol if "ice_lodge" in (w.get("scope") or "")]
    assert len(mine) == 1 and mine[0]["blocks"] == ["minecraft:water"]
    sb = set(jload("spawn_blocks.json")["blocks"])
    assert "minecraft:water" in sb
    # no concrete, no coloured wool: contract C4 (CLAUDE.md), and the record names none
    assert not [b for b in REC["blocks"]["ids"] if "concrete" in b or "wool" in b]
    assert (set(REC["blocks"]["ids"]) & sb) == {"minecraft:water"}


def test_reapply_registers_the_pack_the_jobs_and_the_step():
    import reapply
    assert "cobblers_ice_lodge" in reapply.SERVER_PACKS
    assert "cobblers_ice_lodge" not in reapply.EXCLUDED and "cobblers_ice_lodge" not in reapply.WORLD_LOCAL
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    order = [src.index(s) for s in ('("R18CW"', '("R18IL"', '("R14",')]
    assert order == sorted(order)
    assert 'add("ice_lodge:build"' in src and 'add("ice_lodge_audit"' in src
    assert src.index('add("ice_lodge:build"') < src.index('add("ice_lodge_audit"')


def test_the_keepers_conversation_is_declared_and_promises_nothing():
    fields = {f["id"]: f for f in jload("progression.json")["quest_fields"]}
    f = fields["quest.ice_lodge.keeper_cursor"]
    assert f["initial"] == "hub" and f["scope"] == "player" and f["quest_id"] == "ice_lodge"
    conv, quest = L.conversation(REC)
    assert quest["progression_field_refs"] == [f["id"]]
    ids = [t["id"] for t in REC["keeper"]["topics"]]
    assert len(ids) == len(set(ids)) >= 6
    text = " ".join([REC["keeper"]["greeting"]] + [t["says"] for t in REC["keeper"]["topics"]]).lower()
    # nothing in her talk is a mechanic that does not exist: no prize, reward, derby, contest, trade or quest
    assert not re.search(r"\b(prize|reward|derby|contest|competition|trade|quest|win|winner)\b", text)
    # and the source of the river is told as the measured thing: the creek is a walk away, not here
    src = next(t for t in REC["keeper"]["topics"] if t["id"] == "source")
    assert "south and east" in src["says"]


def test_the_note_and_the_hook_exist():
    note = (ROOT / "docs" / "world-building" / "ICE_LODGE.md").read_text(encoding="utf-8")
    for h in ("## 5.", "## 6."):
        assert h in note
    assert "pokerod_treasure" in note and "in_open_water" in note
    assert "NOT BUILT" in note


# ------------------------------------------------------------------------------------------- generator mutations
def _wrap(monkeypatch, name, after):
    orig = getattr(L, name)

    def wrapped(p, *a, **k):
        r = orig(p, *a, **k)
        after(p, r)
        return r
    monkeypatch.setattr(L, name, wrapped)


SY = REC["tarn"]["surface_y"]
WT = REC["tarn"]["water_top_y"]


def test_a_tarn_one_layer_shallower_is_caught(ground, tmp_path, monkeypatch):
    def thin(p, r):
        for (x, z) in L.tarn_mask(REC):
            if (x + z) % 7 == 0:
                p.solid.pop((x, WT, z), None)
                p.put(x, WT, z, "minecraft:gravel")
    _wrap(monkeypatch, "pool", thin)
    rep = run(ground, tmp_path, guards_off=True)
    assert "tarn" in checks(rep)


def test_ice_over_the_lead_is_caught(ground, tmp_path, monkeypatch):
    x0, z0, x1, z1 = REC["lead"]["box"]

    def freeze(p, r):
        p.put((x0 + x1) // 2, SY, (z0 + z1) // 2, "minecraft:ice")
    _wrap(monkeypatch, "lead", freeze)
    rep = run(ground, tmp_path, guards_off=True)
    assert "lead" in checks(rep) or "tarn" in checks(rep)


def test_a_shelter_door_walled_up_is_caught(ground, tmp_path, monkeypatch):
    s = REC["shelters"][0]
    cx, cz = s["c"]
    n = REC["shelter"]["size"] // 2
    door = {"west": (cx - n, cz), "east": (cx + n, cz), "north": (cx, cz - n), "south": (cx, cz + n)}[s["door"]]

    def wall(p, r):
        p.doors[:] = [d for d in p.doors if (d[0][0], d[0][2]) != door]
        for h in (1, 2):
            p.put(door[0], SY + h, door[1], "minecraft:spruce_planks")
    _wrap(monkeypatch, "shelters", wall)
    rep = run(ground, tmp_path, guards_off=True)
    assert "walk" in checks(rep) or "shelters" in checks(rep)


def test_a_lodge_with_its_lanterns_taken_is_caught(ground, tmp_path, monkeypatch):
    def dark(p, r):
        for k in [k for k, s in p.hung.items() if A.base(s) == "minecraft:lantern" and k[1] == REC["lodge"]["floor_y"] + 2]:
            p.hung.pop(k)
    _wrap(monkeypatch, "lodge", dark)
    rep = run(ground, tmp_path, guards_off=True)
    assert "light" in checks(rep)


def test_a_lantern_beside_the_ice_is_caught(ground, tmp_path, monkeypatch):
    # a level-15 light 3 blocks from plain ice: it melts the ice it stands on
    h = REC["stations"][0]["hole"]

    def lamp(p, r):
        p.hang(h[0] - 1, SY + 1, h[1] - 1, "minecraft:lantern[hanging=false]")
    _wrap(monkeypatch, "lodge", lamp)
    rep = run(ground, tmp_path, guards_off=True)
    assert any(e.startswith("light:") and "plain ice" in e for e in rep.errors)


def test_a_hole_cut_where_no_hole_is_declared_is_caught(ground, tmp_path, monkeypatch):
    mask = L.tarn_mask(REC)
    spot = (2790, 1096)
    assert spot in mask

    def hole(p, r):
        p.put(spot[0], SY, spot[1], "minecraft:air")
    _wrap(monkeypatch, "pool", hole)
    rep = run(ground, tmp_path, guards_off=True)
    assert "water" in checks(rep) or "tarn" in checks(rep)


def test_concrete_in_the_pack_is_caught(ground, tmp_path, monkeypatch):
    def conc(p, r):
        p.solid[(2770, 108, 1055)] = "minecraft:white_concrete"
    _wrap(monkeypatch, "lodge", conc)
    rep = run(ground, tmp_path, guards_off=True)
    assert "palette" in checks(rep)


def test_a_keeper_buried_in_a_barrel_is_caught(ground, tmp_path, monkeypatch):
    # the builder checks her spot in plan(); this writes the barrel AFTER that check, in the emitted function, so it is
    # the audit that has to see it
    kx, kz = REC["keeper"]["at"]
    orig = L.build_lines

    def lines(doc, pl):
        return orig(doc, pl) + ["setblock %d %d %d minecraft:barrel[facing=up]" % (kx, REC["lodge"]["floor_y"] + 1, kz)]
    monkeypatch.setattr(L, "build_lines", lines)
    rep = run(ground, tmp_path, guards_off=True)
    assert "keeper" in checks(rep) or "walk" in checks(rep)


def test_the_builder_refuses_a_keeper_in_a_barrel_itself(ground, monkeypatch):
    kx, kz = REC["keeper"]["at"]

    def barrel(p, r):
        p.put(kx, REC["lodge"]["floor_y"] + 1, kz, "minecraft:barrel[facing=up]")
    _wrap(monkeypatch, "lodge", barrel)
    with pytest.raises(SystemExit) as e:
        L.files(L.load(), ground)
    assert "two blocks of air" in str(e.value)


def test_a_misordered_step_list_is_caught(ground, tmp_path):
    doc = L.load()
    written, _pl, _m = L.files(doc, ground)
    L.write(written, tmp_path)
    steps = list(L.placement_steps(doc))
    steps.reverse()
    rep = A.audit(REC, ground, tmp_path, steps)
    assert "keeper" in checks(rep)


def test_a_builder_guard_refuses_a_palette_break_and_a_hot_ice_cell(ground, monkeypatch):
    # the builder's own guards (not the audit): the cases above switch them off, this one leaves them on
    doc = L.load()

    def lamp(p, r):
        h = REC["stations"][0]["hole"]
        p.hang(h[0] - 1, SY + 1, h[1] - 1, "minecraft:lantern[hanging=false]")
    _wrap(monkeypatch, "lodge", lamp)
    with pytest.raises(SystemExit) as e:
        L.files(doc, ground)
    assert "plain ice" in str(e.value)
