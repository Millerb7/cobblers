"""tools/dune_ruin_audit.py against tools/dune_ruin.py: the clean pack passes, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the independent
half of the proof is the mutation standard of CLAUDE.md, "How to prove an audit is independent": every tamper case
below changes the generator's CODE (a function wrapped or replaced, a constant changed) and leaves data/dune_ruin.json,
data/habitat_blocks.json, data/rewards.json and the dialogue records alone. A record-side mutation moves the
expectation and the output together and proves nothing.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. NOT covered, and it needs a running server: that
the fills land, that the world's ground under the Khan is sand, that Cofagrigus spawn in the vault and stay, that the
cache grants, that the salvager appears.
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402
import dune_ruin as D  # noqa: E402
import dune_ruin_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "dune_ruin.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def run(ground, out, steps=None, placements=None):
    doc = D.load()
    written, _pl = D.files(doc, ground)
    D.write(written, out)
    return A.audit(REC, ground, out, steps if steps is not None else D.placement_steps(doc, ground),
                   placements if placements is not None else D.npc_placements(doc, ground))


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


def _wrap(monkeypatch, name, after):
    orig = getattr(D, name)

    def wrapped(p, *a, **k):
        r = orig(p, *a, **k)
        after(p)
        return r
    monkeypatch.setattr(D, name, wrapped)


# ------------------------------------------------------------------------------------------- the committed place
def test_the_committed_khan_is_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []


def test_the_records_agree_with_the_plan(ground):
    """The bounds, the Habitat Block, the cache and the salvager's spot, as committed, are where the plan puts them."""
    pl = D.plan(D.load(), ground)
    assert REC["bounds"]["khan"] == pl["bounds"]["khan"]
    assert REC["bounds"]["road"] == pl["bounds"]["road"]
    hb = {b["id"]: b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]}
    b = hb[REC["habitat"]["block"]]
    assert pl["habitat_block"] == (b["position"]["x"], b["position"]["y"], b["position"]["z"])
    rw = {r["id"]: r for r in json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))["rewards"]}
    r = rw[REC["find"]["reward"]]
    assert tuple(r["container"]["at"]) == pl["barrel"]
    assert r["trigger"] == pl["trigger"]


def test_the_build_rebuilds_byte_identical(ground):
    a, _ = D.files(D.load(), ground)
    b, _ = D.files(D.load(), ground)
    assert a == b


def test_the_audit_imports_nothing_from_the_generator_outside_main():
    src = (ROOT / "tools" / "dune_ruin_audit.py").read_text(encoding="utf-8")
    body = src.split("\ndef main(")[0]
    assert not re.search(r"^\s*(import dune_ruin\b|from dune_ruin\b)", body, re.M)


# ------------------------------------------------------------------------------------------- generator mutations
def test_a_vault_one_block_taller_is_caught(ground, tmp_path, monkeypatch):
    u = REC["undercroft"]
    ux, uz = u["centre_local"]
    n = u["interior_half"]

    def open_ceiling(p):
        for lx in range(ux - n, ux + n + 1):
            for lz in range(uz - n, uz + n + 1):
                if (lx, lz) != tuple(u["trapdoor_local"]):
                    p.put(lx, p.F, lz, "minecraft:air")
    _wrap(monkeypatch, "undercroft", open_ceiling)
    rep = run(ground, tmp_path)
    assert any("taller than the record" in e for e in rep.errors)


def test_a_trapdoor_left_out_unseals_the_vault(ground, tmp_path, monkeypatch):
    tx, tz = REC["undercroft"]["trapdoor_local"]

    def no_trapdoor(p):
        k = (p.cx + tx, p.F, p.cz + tz)
        p.hung.pop(k)
        p.solid[k] = "minecraft:air"
    _wrap(monkeypatch, "undercroft", no_trapdoor)
    rep = run(ground, tmp_path)
    assert any(e.startswith("vault: with the trapdoor closed") for e in rep.errors)


def test_a_bricked_door_left_open_lets_a_player_walk_in(ground, tmp_path, monkeypatch):
    dx, dz = REC["undercroft"]["bricked_door_local"]
    tx, tz = REC["undercroft"]["trapdoor_local"]

    def open_door(p):
        for y in (p.F + 1, p.F + 2):
            p.put(dx, y, dz, "minecraft:air")
    _wrap(monkeypatch, "undercroft", open_door)
    rep = run(ground, tmp_path)
    assert any("store is reachable on foot" in e for e in rep.errors)


def test_a_vault_floor_raised_off_the_habitat_block_is_caught(ground, tmp_path, monkeypatch):
    u = REC["undercroft"]
    ux, uz = u["centre_local"]
    n = u["interior_half"]

    def raise_floor(p):
        floor = p.F - u["air_height"] - 1
        for lx in range(ux - n, ux + n + 1):
            for lz in range(uz - n, uz + n + 1):
                p.put(lx, floor, lz, "minecraft:sandstone")
                p.put(lx, floor + 1, lz, REC["blocks"]["vault_floor"])
    _wrap(monkeypatch, "undercroft", raise_floor)
    rep = run(ground, tmp_path)
    assert "habitat" in checks(rep) and "vault" in checks(rep)


def test_lintels_raised_off_the_sand_line_are_caught(ground, tmp_path, monkeypatch):
    def raise_lintels(p):
        for lx in range(-p.A, p.A + 1):
            for lz in (-p.A, p.A):
                if abs(lx) > 1:
                    p.solid.pop((p.cx + lx, p.F + 4, p.cz + lz), None)
                    p.put(lx, p.F + 5, lz, p.doc["blocks"]["trim"])
    _wrap(monkeypatch, "khan", raise_lintels)
    rep = run(ground, tmp_path)
    assert "drowned" in checks(rep)


def test_a_dark_gap_in_a_buried_room_is_caught(ground, tmp_path, monkeypatch):
    def hollow(p):
        p.put(13, p.F + 3, 0, "minecraft:air")
        p.put(13, p.F + 4, 0, "minecraft:air")
    _wrap(monkeypatch, "khan", hollow)
    rep = run(ground, tmp_path)
    assert any(e.startswith("drowned: a dark gap") for e in rep.errors)


def test_a_trench_without_its_steps_cuts_the_way_in(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(D, "trench", lambda p: None)
    rep = run(ground, tmp_path)
    assert "way in" in checks(rep)


def test_a_gate_passage_one_block_high_is_caught(ground, tmp_path, monkeypatch):
    def low_gate(p):
        for lz in range(-p.H - 1, -p.A + 1):
            p.put(0, p.F + 6, lz, p.doc["blocks"]["wall"])
            p.put(-1, p.F + 6, lz, p.doc["blocks"]["wall"])
            p.put(1, p.F + 6, lz, p.doc["blocks"]["wall"])
    _wrap(monkeypatch, "gate", low_gate)
    rep = run(ground, tmp_path)
    assert "way in" in checks(rep)


def test_a_vault_without_its_lanterns_is_caught(ground, tmp_path, monkeypatch):
    def dark(p):
        for k in [k for k, s in p.hung.items() if s.startswith("minecraft:soul_lantern[hanging=true")]:
            p.hung.pop(k)
    _wrap(monkeypatch, "undercroft", dark)
    rep = run(ground, tmp_path)
    assert any(e.startswith("light: the vault has no lantern") for e in rep.errors)


def test_a_hall_lit_at_one_end_only_leaves_dark_places(ground, tmp_path, monkeypatch):
    def one_lamp(p):
        for k in [k for k, s in p.hung.items() if s.startswith("minecraft:lantern") and k[1] in (p.F + 2, p.F + 4)
                  and 11 <= k[2] - p.cz <= 15 and k[0] - p.cx > -6]:
            p.hung.pop(k)
    _wrap(monkeypatch, "hall", one_lamp)
    rep = run(ground, tmp_path)
    assert any(e.startswith("light:") and "hall" in e for e in rep.errors)


def test_sand_written_into_the_khan_is_caught(ground, tmp_path, monkeypatch):
    def drift(p):
        p.solid[(p.cx + 20, p.S + 1, p.cz)] = "minecraft:sand"
    _wrap(monkeypatch, "courtyard", drift)
    rep = run(ground, tmp_path)
    assert any(e.startswith("blocks: minecraft:sand") for e in rep.errors)


def test_a_milestone_seated_high_is_caught(ground, tmp_path, monkeypatch):
    orig = D.road

    def lifted(p):
        posts = orig(p)
        x, z, y = posts[3]
        for dy in (1, 2, 3):
            for d in (p.solid, p.hung):
                if (x, y + dy, z) in d:
                    d[(x, y + dy + 2, z)] = d.pop((x, y + dy, z))
        return posts
    monkeypatch.setattr(D, "road", lifted)
    rep = run(ground, tmp_path)
    assert "road" in checks(rep)


def test_a_road_that_stops_short_of_the_gate_is_caught(ground, tmp_path, monkeypatch):
    orig = D.road

    def short(p):
        posts = orig(p)
        for x, z, y in posts[-3:]:
            for dy in (1, 2, 3):
                p.solid.pop((x, y + dy, z), None)
                p.hung.pop((x, y + dy, z), None)
        return posts[:-3]
    monkeypatch.setattr(D, "road", short)
    rep = run(ground, tmp_path)
    assert "road" in checks(rep)


def test_signs_lanterns_and_ladders_written_before_the_walls_are_caught(ground, tmp_path, monkeypatch):
    orig = D.build_lines

    def hung_first(doc, pl):
        lines = orig(doc, pl)
        hung = D._runs(pl["plan"].hung, top_down=True)
        rest = [l for l in lines if l not in set(hung)]
        at = next(i for i, l in enumerate(rest) if l.startswith("# 2."))
        return rest[:at] + hung + rest[at:]
    monkeypatch.setattr(D, "build_lines", hung_first)
    rep = run(ground, tmp_path)
    assert any("written before what holds it up" in e for e in rep.errors)


def test_a_clearing_that_stops_short_of_the_tower_is_caught(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(D, "CLEAR_OVER", -10)
    rep = run(ground, tmp_path)
    assert "clear" in checks(rep)


def test_steps_that_do_not_hold_the_chunks_are_caught(ground, tmp_path):
    steps = [s for s in D.placement_steps(D.load(), ground) if s[0] == "fn"]
    rep = run(ground, tmp_path, steps=steps)
    assert "steps" in checks(rep)


def test_a_salvager_placed_off_her_spot_is_caught(ground, tmp_path):
    (cid, (x, y, z), cls), = D.npc_placements(D.load(), ground)
    rep = run(ground, tmp_path, placements=[(cid, (x, y + 1, z), cls)])
    assert "npc" in checks(rep)


# ------------------------------------------------------------------------------------------- the dialogue side
def test_the_conversation_compiles_and_its_cursor_names_every_node():
    d, quests, fields = CD.load(ROOT / "data")
    conv = next(c for c in d["conversations"] if c["id"] == REC["npc"]["conversation"])
    CD.compile_conversation(conv, quests, fields)
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    field = next(f for v in prog.values() if isinstance(v, list) for f in v
                 if isinstance(f, dict) and f.get("id") == conv["cursor"]["progression_field"])
    assert field["allowed_values"] == [n["id"] for n in conv["nodes"]]


def test_the_salvager_points_at_the_store_without_handing_it_over():
    d = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    conv = next(c for c in d["conversations"] if c["id"] == REC["npc"]["conversation"])
    text = " ".join(n.get("text", "") for n in conv["nodes"]).lower()
    assert "west wall" in text and "store" in text
    assert not any(n.get("actions") for n in conv["nodes"]) and not conv.get("quest_transitions")


# ------------------------------------------------------------------------------------------- the re-application
def test_reapply_runs_the_khan_before_the_habitat_blocks_and_the_salvager_after_the_seats():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    steps_src = src.split("\ndef steps(")[1].split("\ndef ")[0]
    assert steps_src.index('"R9DU"') < steps_src.index('"R9E"'), "R9DU would write sandstone over R9E's block"
    assert steps_src.index('"R17N"') < steps_src.index('"R18DU"')
    assert '"cobblers_dune_ruin"' in src
    assert 'add("dune_ruin:build", "dune_ruin.py", "build", *src)' in src
    assert 'add("dune_ruin_audit", "dune_ruin_audit.py", *src)' in src


def test_the_build_runs_before_the_habitat_blocks_once_it_is_a_step(ground, monkeypatch):
    import reapply
    monkeypatch.setattr(reapply, "indexed", lambda *a, **k: ["stub"])
    try:
        steps = reapply.steps()
    except SystemExit as e:                   # a worktree has no derived/ (CLAUDE.md): reapply fails closed with SystemExit
        pytest.skip("NOT_EXECUTED: tools/reapply.py steps() could not be built here: %s" % e)
    ids = [s[0] for s in steps]
    mine = [i for i, s in enumerate(steps) if ("fn", "cobblers:dune_ruin/build") in [tuple(a) for a in s[2]]]
    assert mine and mine[0] < ids.index("R9E"), "the build would write sandstone over the Habitat Block R9E places"
