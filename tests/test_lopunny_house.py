"""tools/lopunny_house_audit.py against tools/lopunny_house.py: the clean pack passes, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the independent
half of the proof is the mutation standard of CLAUDE.md, "How to prove an audit is independent": every tamper case
below changes the generator's CODE (a function wrapped or replaced, a constant changed) and leaves
data/lopunny_house.json, data/habitat_blocks.json and the quest records alone. A record-side mutation moves the
expectation and the output together and proves nothing.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. NOT covered, and it needs a running server
(experiments/EXP-052-lopunny-show): that the fills land, that Buneary spawn in the room and stay there, that the party
callback tags a player, that the option appears, and that the bell is given.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402
import lopunny_house as L  # noqa: E402
import lopunny_house_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "lopunny_house.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def run(ground, out, steps=None):
    doc = L.load()
    written, _pl = L.files(doc, ground)
    L.write(written, out)
    return A.audit(REC, ground, out, steps if steps is not None else L.placement_steps(doc, ground))


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


def test_the_committed_house_is_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []


def test_the_house_sits_on_the_owners_spot_and_the_block_on_the_cellar_floor(ground):
    pl = L.plan(L.load(), ground)
    hb = {b["id"]: b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]}
    b = hb[REC["buneary"]["block"]]
    assert REC["site"]["centre"] == [6950, 1360]
    assert pl["habitat_block"] == (b["position"]["x"], b["position"]["y"], b["position"]["z"])


# ------------------------------------------------------------------------------------------- generator mutations
def _wrap(monkeypatch, name, after):
    orig = getattr(L, name)

    def wrapped(p, *a, **k):
        r = orig(p, *a, **k)
        after(p)
        return r
    monkeypatch.setattr(L, name, wrapped)


def test_a_cellar_one_block_taller_is_caught(ground, tmp_path, monkeypatch):
    n = REC["cellar"]["interior_half"]

    def open_ceiling(p):
        for lx in range(-n, n + 1):
            for lz in range(-n, n + 1):
                p.put(lx, -1, lz, "minecraft:air")
    _wrap(monkeypatch, "cellar", open_ceiling)
    rep = run(ground, tmp_path)
    assert any("taller than the record" in e for e in rep.errors)


def test_a_trapdoor_left_out_unseals_the_cellar(ground, tmp_path, monkeypatch):
    n = REC["cellar"]["interior_half"]

    def no_trapdoor(p):
        k = (p.cx - n, p.hf, p.cz - n)
        p.hung.pop(k)
        p.solid[k] = "minecraft:air"
    _wrap(monkeypatch, "house", no_trapdoor)        # after the house, whose floor would close the hole again
    rep = run(ground, tmp_path)
    assert any(e.startswith("cellar: with the trapdoor closed") for e in rep.errors)


def test_a_cellar_floor_raised_off_the_habitat_block_is_caught(ground, tmp_path, monkeypatch):
    n = REC["cellar"]["interior_half"]
    floor = -(REC["cellar"]["air_height"] + 2)

    def raise_floor(p):
        for lx in range(-n, n + 1):
            for lz in range(-n, n + 1):
                p.put(lx, floor, lz, "minecraft:stone")
                if (lx, lz) not in ((-n, -n),):
                    p.put(lx, floor + 1, lz, REC["blocks"]["cellar_floor"])
    _wrap(monkeypatch, "cellar", raise_floor)
    rep = run(ground, tmp_path)
    assert "habitat" in checks(rep) and "cellar" in checks(rep)


def test_a_house_seated_a_block_high_is_caught(ground, tmp_path, monkeypatch):
    orig = L.Plan.__init__

    def init(self, doc, g):
        orig(self, doc, g)
        self.hf += 1
    monkeypatch.setattr(L.Plan, "__init__", init)
    rep = run(ground, tmp_path)
    assert {"seat", "habitat", "npc"} <= set(checks(rep))


def test_hung_blocks_written_bottom_up_drop_the_lantern_off_its_chain(ground, tmp_path, monkeypatch):
    orig = L._runs
    monkeypatch.setattr(L, "_runs", lambda blocks, top_down=False: orig(blocks, top_down=False))
    rep = run(ground, tmp_path)
    assert any("written before what holds it up" in e for e in rep.errors)


def test_signs_written_before_the_walls_are_caught(ground, tmp_path, monkeypatch):
    orig = L.build_lines

    def hung_first(doc, pl):
        p = pl["plan"]
        lines = orig(doc, pl)
        hung = L._runs(p.hung, top_down=True)
        rest = [l for l in lines if l not in set(hung)]
        return rest[:4] + hung + rest[4:]
    monkeypatch.setattr(L, "build_lines", hung_first)
    rep = run(ground, tmp_path)
    assert "attached" in checks(rep)


def test_a_clearing_that_stops_short_of_the_ears_is_caught(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(L, "CLEAR_UP", 6)
    rep = run(ground, tmp_path)
    assert "clear" in checks(rep)


def test_a_spawn_condition_slipped_past_the_palette_is_caught(ground, tmp_path, monkeypatch):
    def white_rug(p):
        p.hung[(p.cx, p.hf + 1, p.cz - 2)] = "minecraft:white_carpet"
    _wrap(monkeypatch, "house", white_rug)
    rep = run(ground, tmp_path)
    assert any(e.startswith("blocks: minecraft:white_carpet is a spawn condition") for e in rep.errors)


def test_a_callback_looking_for_the_wrong_species_is_caught(ground, tmp_path, monkeypatch):
    orig = L.callback_text
    monkeypatch.setattr(L, "callback_text", lambda doc: orig(doc).replace("cobblemon:lopunny", "cobblemon:buneary"))
    rep = run(ground, tmp_path)
    assert "check" in checks(rep)


def test_a_callback_that_chains_the_species_read_is_caught(ground, tmp_path, monkeypatch):
    orig = L.callback_text

    def chained(doc):
        return orig(doc).replace("  t.id = t.p.species.identifier;\n", "").replace("t.id ==", "t.p.species.identifier ==")
    monkeypatch.setattr(L, "callback_text", chained)
    rep = run(ground, tmp_path)
    assert "check" in checks(rep)


def test_a_callback_that_never_untags_is_caught(ground, tmp_path, monkeypatch):
    orig = L.callback_text
    monkeypatch.setattr(L, "callback_text", lambda doc: orig(doc).replace(" remove ", " add "))
    rep = run(ground, tmp_path)
    assert "check" in checks(rep)


def test_steps_that_do_not_hold_the_chunks_are_caught(ground, tmp_path):
    doc = L.load()
    steps = [s for s in L.placement_steps(doc, ground) if s[0] == "fn"]
    rep = run(ground, tmp_path, steps=steps)
    assert "steps" in checks(rep)


# ------------------------------------------------------------------------------------------- the dialogue side
def test_player_tag_compiles_to_a_tag_read_and_refuses_a_bad_tag():
    c = CD.Compiler.__new__(CD.Compiler)
    assert c.cond({"kind": "player_tag", "tag": "cobblers_lopunny_in_party"}, {}) == \
        "q.player.has_tag('cobblers_lopunny_in_party')"
    with pytest.raises(CD.Unsupported):
        c.cond({"kind": "player_tag", "tag": "x'); q.run_command('op"}, {})


def test_the_conversation_compiles_and_only_shows_the_option_with_the_tag():
    _d, quests, fields = CD.load(ROOT / "data")
    conv = next(c for c in _d["conversations"] if c["id"] == REC["npc"]["conversation"])
    got = CD.compile_conversation(conv, quests, fields)
    page = next(p for p in got["data/cobblers/dialogues/%s.json" % conv["id"]]["pages"] if p["id"] == "hub")
    show = next(o for o in page["input"]["options"] if o["value"] == "r_show")
    assert "q.player.has_tag('%s')" % REC["lopunny_check"]["tag"] in show["isVisible"]
    # the transition checks it again when chosen, so a stale page cannot grant
    assert "has_tag('%s')" % REC["lopunny_check"]["tag"] in show["action"]
    others = [o for o in page["input"]["options"] if o["value"] != "r_show"]
    assert all("isVisible" not in o for o in others)


# ------------------------------------------------------------------------------------------- the re-application
def test_the_build_runs_before_the_habitat_blocks_once_it_is_a_step(ground, monkeypatch):
    import reapply
    monkeypatch.setattr(reapply, "indexed", lambda *a, **k: ["stub"])
    try:
        steps = reapply.steps()
    except SystemExit as e:                   # a worktree has no derived/ (CLAUDE.md): reapply fails closed with SystemExit
        pytest.skip("NOT_EXECUTED: tools/reapply.py steps() could not be built here: %s" % e)
    ids = [s[0] for s in steps]
    mine = [i for i, s in enumerate(steps) if ("fn", "cobblers:lopunny_house/build") in [tuple(a) for a in s[2]]]
    if not mine:
        pytest.skip("NOT_EXECUTED: tools/reapply.py has no step running cobblers:lopunny_house/build yet (the "
                    "integrating session adds it, BEFORE R9E)")
    assert mine[0] < ids.index("R9E"), "the build would write stone bricks over the Habitat Block R9E places"
