"""tools/old_orchard_audit.py against tools/old_orchard.py: the clean pack passes, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the independent
half of the proof is the mutation standard of CLAUDE.md, "How to prove an audit is independent": every tamper case
below changes the generator's CODE (a function wrapped or replaced, a constant changed) and leaves
data/old_orchard.json, data/habitat_blocks.json, data/rewards.json and the quest records alone. A record-side mutation
moves the expectation and the output together and proves nothing.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. NOT covered, and it needs a running server:
that the fills land, that Applin spawn round the tree, that the cache grants, that the keeper renders and talks.
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import old_orchard as L  # noqa: E402
import old_orchard_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "old_orchard.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def run(ground, out):
    doc = L.load()
    written, _pl = L.files(doc, ground)
    L.write(written, out)
    return A.audit(REC, ground, out, L.placement_steps(doc), L.npc_placements(doc, ground))


def test_the_committed_orchard_is_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []


def test_the_records_agree_with_the_plan(ground):
    pl = L.plan(L.load(), ground)
    hb = {b["id"]: b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]}
    b = hb[REC["applin"]["block"]]
    assert pl["habitat_block"] == (b["position"]["x"], b["position"]["y"], b["position"]["z"])
    rw = {r["id"]: r for r in json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))["rewards"]}
    assert tuple(rw[REC["find"]["reward"]]["container"]["at"]) == pl["barrel"]


def test_the_keep_out_boxes_are_the_palm_saplings_own(ground):
    # recomputed from tools/themed_saplings.py, the tool that places the palm: if the palm moves, this fails
    import themed_saplings as TS
    sd = TS.sides()
    site = [s for s in TS.load_pins() if s["id"] == "sapling_palm_sunset_east"][0]
    _pos, fp = TS.place(site, sd["palm"])
    want = {fp}
    for c in TS.setting(site, sd, ground):
        if c.startswith("place template"):
            m = c.split()
            side = [v for v in sd.values() if v["template_id"] == m[2]][0]
            sx, _sy, sz = side["source"]["size"]
            want.add(TS.footprint(int(m[3]), int(m[5]), sx, sz, m[6]))
    have = {(b["min"][0], b["min"][1], b["max"][0], b["max"][1]) for b in REC["keep_out"]["boxes"]
            if b["id"] != "palm_dressing"}
    assert {tuple(int(v) for v in w) for w in want} == have


def test_the_resident_anchor_is_dry_and_untouched(ground):
    res = next(r for r in json.loads((ROOT / "data" / "resident_encounters.json").read_text(encoding="utf-8"))["encounters"]
               if r["id"] == "orchard_sleeper")
    ax, az = res["location"]["x"], res["location"]["z"]
    assert [ax, az] == REC["resident"]["anchor"]
    assert ground(ax, az) > 62                   # above sea level y62 after the water export
    pl = L.plan(L.load(), ground)
    assert min(((k[0] - ax) ** 2 + (k[2] - az) ** 2) ** 0.5 for k in pl["blocks"]) > 4


def test_reapply_runs_the_orchard_before_the_habitat_blocks_and_the_keeper_after_r17n():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    order = [src.index(s) for s in ('("R9LH"', '("R9SO"', '("R9E"', '("R17N"', '("R18SO"')]
    assert order == sorted(order)
    assert '"cobblers_old_orchard"' in src
    assert 'add("old_orchard:build"' in src and 'add("old_orchard_audit"' in src


# ------------------------------------------------------------------------------------------- generator mutations
def _wrap(monkeypatch, name, after):
    orig = getattr(L, name)

    def wrapped(p, *a, **k):
        r = orig(p, *a, **k)
        after(p, r)
        return r
    monkeypatch.setattr(L, name, wrapped)


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


def test_a_row_moved_onto_the_sleeper_is_caught(ground, tmp_path, monkeypatch):
    ax, az = REC["resident"]["anchor"]
    orig = L.tree

    def tree(p, x, z):
        if x == REC["orchard"]["cols_x"][-1] and z == REC["orchard"]["rows_z"][2]:
            return orig(p, ax - 3, az)                 # the last tree planted three blocks from the anchor
        return orig(p, x, z)
    monkeypatch.setattr(L, "tree", tree)
    rep = run(ground, tmp_path)
    assert "resident" in checks(rep)


def test_a_cellar_one_block_taller_is_caught(ground, tmp_path, monkeypatch):
    n = REC["cellar"]["interior_half"]
    cx, cz = REC["press_house"]["centre"]

    def open_ceiling(p, floor_y):
        hf = floor_y + REC["cellar"]["air_height"] + 2
        for a in range(-n, n + 1):
            for b in range(-n, n + 1):
                p.put(cx + a, hf - 1, cz + b, "minecraft:air")
    _wrap(monkeypatch, "cellar", open_ceiling)
    rep = run(ground, tmp_path)
    assert any("taller than the record" in e for e in rep.errors)


def test_a_trapdoor_left_out_unseals_the_cellar(ground, tmp_path, monkeypatch):
    n = REC["cellar"]["interior_half"]
    cx, cz = REC["press_house"]["centre"]

    def no_trapdoor(p, floor_y):
        hf = floor_y + REC["cellar"]["air_height"] + 2
        p.put(cx - n, hf, cz - n, "minecraft:air")
    _wrap(monkeypatch, "cellar", no_trapdoor)
    rep = run(ground, tmp_path)
    assert any("trapdoor shut the room is open" in e for e in rep.errors)


def test_the_finds_barrel_moved_is_caught(ground, tmp_path, monkeypatch):
    n = REC["cellar"]["interior_half"]
    cx, cz = REC["press_house"]["centre"]

    def moved(p, floor_y):
        p.put(cx + n, floor_y + 1, cz + n, "minecraft:air")
        p.put(cx - n, floor_y + 1, cz + n - 1, "minecraft:barrel[facing=east,open=false]")
    _wrap(monkeypatch, "cellar", moved)
    rep = run(ground, tmp_path)
    assert any(e.startswith("find: the container") for e in rep.errors)


def test_leaves_that_decay_are_caught(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LEAVES", "minecraft:oak_leaves[persistent=false,waterlogged=false]")
    rep = run(ground, tmp_path)
    assert any("not persistent" in e for e in rep.errors)


def test_hung_blocks_written_bottom_up_are_caught(ground, tmp_path, monkeypatch):
    orig = L._runs
    monkeypatch.setattr(L, "_runs", lambda blocks, top_down=False: orig(blocks, False))
    rep = run(ground, tmp_path)
    assert any("written before what holds it" in e for e in rep.errors)


def test_signs_and_lanterns_before_their_walls_are_caught(ground, tmp_path, monkeypatch):
    orig = L.build_lines

    def hung_first(doc, pl):
        lines = orig(doc, pl)
        hung = [l for l in lines if "lantern" in l or "wall_sign" in l]
        return [l for l in lines if l not in hung][:4] + hung + [l for l in lines if l not in hung][4:]
    monkeypatch.setattr(L, "build_lines", hung_first)
    rep = run(ground, tmp_path)
    assert "attached" in checks(rep)


def test_a_hole_in_the_press_house_floor_is_caught(ground, tmp_path, monkeypatch):
    cx, cz = REC["press_house"]["centre"]

    def hole(p, r):
        hf, _ridge = r
        p.put(cx + 2, hf, cz + 2, "minecraft:air")
    _wrap(monkeypatch, "press_house", hole)
    rep = run(ground, tmp_path)
    assert any("press-house floor at" in e for e in rep.errors)


def test_a_post_in_the_palms_grove_is_caught(ground, tmp_path, monkeypatch):
    def stray(p, _r):
        y = p.g(2812, 7060) + 1
        p.put(2812, y, 7060, "minecraft:oak_fence[east=false,west=false,north=false,south=false,waterlogged=false]")
    _wrap(monkeypatch, "lantern_posts", stray)
    rep = run(ground, tmp_path)
    assert any("keep_out palm_sapling" in e for e in rep.errors)


def test_the_applin_tree_killed_is_caught(ground, tmp_path, monkeypatch):
    hz, hx = REC["applin"]["tree"]
    orig = L.tree_kind
    monkeypatch.setattr(L, "tree_kind", lambda doc, x, z: "dead" if (x, z) == (hx, hz) else orig(doc, x, z))
    rep = run(ground, tmp_path)
    assert any("no crown over its trunk" in e for e in rep.errors)


def test_a_clear_left_out_is_caught(ground, tmp_path, monkeypatch):
    orig = L.Plan.clear

    def no_tree_clears(self, x0, z0, x1, z1, y0, y1, tags=L.CLEAR_TAGS):
        if y1 - y0 >= 6 and x1 - x0 <= 10:              # the trees' clears
            return
        return orig(self, x0, z0, x1, z1, y0, y1, tags)
    monkeypatch.setattr(L.Plan, "clear", no_tree_clears)
    rep = run(ground, tmp_path)
    assert "clear" in checks(rep)


def test_a_keeper_step_moved_into_the_leash_is_caught(ground, tmp_path, monkeypatch):
    ax, az = REC["resident"]["anchor"]
    orig = L.npc_placements

    def closer(doc=None, g=None):
        conv, (_x, _y, _z), cls = orig(doc, g)[0]
        return [(conv, (ax - 10, ground(ax - 10, az) + 1, az), cls)]
    monkeypatch.setattr(L, "npc_placements", closer)
    rep = run(ground, tmp_path)
    assert any(e.startswith("npc: the npc step") for e in rep.errors)


def test_the_jar_confirms_slakoth_and_vigoroth_cannot_spawn_in_the_band(ground):
    # the audit's pool rule, fed the pool the brief first proposed: Slakoth evolves at 18, so a 43-53 Slakoth fails
    ev = A._jar_evolutions()
    if ev is None:
        pytest.skip("no Cobblemon jar to read evolutions from")
    nxt, pre = ev
    assert nxt["slakoth"] == 18 and nxt["vigoroth"] == 36
    assert 53 > nxt["slakoth"] + 4 and 53 > nxt["vigoroth"] + 4 and 43 > nxt["vigoroth"] + 4


def test_the_report_writes_nothing(ground, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("COBBLERS_SOURCE_ROOT", os.environ.get("COBBLERS_SOURCE_ROOT", ""))
    before = set(tmp_path.iterdir())
    assert L.main(["--report", "--out", str(tmp_path / "pack")]) == 0
    assert set(tmp_path.iterdir()) == before
    assert re.search(r"press-house floor y\d+", capsys.readouterr().out)
