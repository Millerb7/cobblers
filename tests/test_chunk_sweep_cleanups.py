"""tools/chunk_look.py sweep and the staging-only tower cleanups (tools/articuno_tower.py, tools/zapdos_tower.py), N155.

A force-loaded chunk's SAVED entities arrive some ticks after the forceload (staging 2026-10-08, the stall merchants).
The towers' cleanups killed the decorative entities a template can carry in the tick they force-loaded the box, so an
item frame or armour stand whose chunk was slower outlived the cleanup. The sweep repeats the kills every 20 ticks from
tick 40 to 300, then counts what went and releases. A kill-only cleanup does not fit chunk_look.chain() (nothing to
summon or de-duplicate), hence the sweep.

The world is tests/test_markets_merchant_load.py's LateWorld; the entity functions take their boxes from the record, so
no heightmap is needed. Written by the implementer of the fix (minecraft-systems-dev); an independent test-author
review is still owed (CLAUDE.md principle 16).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import articuno_tower as AT  # noqa: E402
import chunk_look as CL  # noqa: E402
import chunk_look_audit as CA  # noqa: E402
import mcfunction_sim as S  # noqa: E402
import zapdos_tower as ZT  # noqa: E402
from test_markets_merchant_load import LateWorld  # noqa: E402

TOWERS = {"articuno": (AT, lambda: AT.shoulder_box()), "zapdos": (ZT, lambda: ZT.old_box())}


def _inside(box):
    """Three entities a paste can leave, inside the box, in different corners (so in different chunks when it spans)."""
    x0, seat, z0, x1, _top, z1 = box
    return [S.Entity("minecraft:item_frame", (x0 + 0.5, seat + 2, z0 + 0.5)),
            S.Entity("minecraft:armor_stand", (x1 + 0.5, seat + 1, z1 + 0.5)),
            S.Entity("minecraft:item", ((x0 + x1) / 2 + 0.5, seat + 1, (z0 + z1) / 2 + 0.5))]


def _world(fns, delay, box):
    w = LateWorld(fns, delay)
    for e in _inside(box):
        w.save(e)
    w.save(S.Entity("minecraft:item_frame", (box[0] - 40.5, box[1] + 2, box[2] + 0.5)))     # outside: must stay
    return w


def _left(w, box):
    x0, _s, z0, x1, _t, z1 = box
    return [e for e in w.entities if e.alive and x0 <= e.pos[0] <= x1 + 1 and z0 <= e.pos[2] <= z1 + 1]


def _old_shape(mod, box):
    """The pre-N155 entity half: force-load and kill in one tick, release."""
    x0, _seat, z0, x1, _top, z1 = box
    kills = [l for l in mod.cleanup_entity_functions()[mod.ENTITIES_FN + "_look"]
             if " kill " in l and not l.startswith("#")]
    return {mod.ENTITIES_FN: ["forceload add %d %d %d %d" % (x0, z0, x1, z1)]
            + ["kill " + l.split(" run kill ", 1)[1] for l in kills] + ["forceload remove %d %d %d %d" % (x0, z0, x1, z1)]}


@pytest.mark.parametrize("tower", sorted(TOWERS))
@pytest.mark.parametrize("delay", [1, 100])
def test_the_old_one_tick_kill_leaves_what_arrives_late(tower, delay):
    # Without it the sweep has nothing to fix.
    mod, box = TOWERS[tower][0], TOWERS[tower][1]()
    w = _world(_old_shape(mod, box), delay, box)
    w.run(mod.ENTITIES_FN, CL.STEP_TICKS)
    assert len(_left(w, box)) == 3


@pytest.mark.parametrize("tower", sorted(TOWERS))
@pytest.mark.parametrize("delay", [0, 40, 100, 299])
def test_the_sweep_kills_everything_in_the_box_that_arrives_inside_the_window(tower, delay):
    # Without it a re-run on staging leaves frames, stands or dropped items at the old site.
    mod, box = TOWERS[tower][0], TOWERS[tower][1]()
    w = _world(mod.cleanup_entity_functions(), delay, box)
    w.run(mod.ENTITIES_FN, CL.STEP_TICKS)
    assert _left(w, box) == []
    assert len([e for e in w.entities if e.alive]) == 1, "the sweep killed outside its box"
    assert w.scores[("#" + mod.ENTITIES_HOLDER, CL.OBJ)] == 3 and not w.forced


@pytest.mark.parametrize("tower", sorted(TOWERS))
def test_the_sweep_reads_minus_one_until_it_ends(tower):
    # Without it a reader could take an earlier run's count.
    mod, box = TOWERS[tower][0], TOWERS[tower][1]()
    w = _world(mod.cleanup_entity_functions(), 20, box)
    w.run(mod.ENTITIES_FN, 100)
    assert w.scores[("#" + mod.ENTITIES_HOLDER, CL.OBJ)] == -1 and w.forced


def _write(tmp_path, fns):
    for rel, lines in CL.files(fns).items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("tower", sorted(TOWERS))
def test_the_audit_passes_the_sweep_and_names_the_old_shape(tower, tmp_path):
    # Without it the one-tick kill could come back and pass.
    mod, box = TOWERS[tower][0], TOWERS[tower][1]()
    assert CA.sweep_problems(_write(tmp_path / "ok", mod.cleanup_entity_functions()), mod.ENTITIES_FN) == []
    probs = CA.sweep_problems(_write(tmp_path / "old", _old_shape(mod, box)), mod.ENTITIES_FN)
    assert any("kills in the tick it force-loads" in p for p in probs)


def test_a_generator_with_a_short_window_or_an_early_release_is_named(tmp_path, monkeypatch):
    # The GENERATOR mutated: fewer looks (the window under 300 ticks), and the look releasing the box itself.
    monkeypatch.setattr(CL, "POLLS", 5)
    fns = AT.cleanup_entity_functions()
    rm = next(l for l in fns[AT.ENTITIES_FN + "_done"] if l.startswith("forceload remove"))
    fns[AT.ENTITIES_FN + "_look"] = fns[AT.ENTITIES_FN + "_look"] + [rm]
    probs = CA.sweep_problems(_write(tmp_path, fns), AT.ENTITIES_FN)
    assert any("under %d" % CA.BLIND_MIN in p for p in probs)
    assert any("the sweep is not over" in p for p in probs)
    w = _world(fns, 150, AT.shoulder_box())
    w.run(AT.ENTITIES_FN, CL.STEP_TICKS)
    assert len(_left(w, AT.shoulder_box())) == 3


@pytest.mark.parametrize("tower", sorted(TOWERS))
def test_the_block_half_holds_the_box_and_hands_it_to_the_sweep_without_releasing_it(tower):
    # Without it the block function's own `forceload remove` would release the chunks under the sweep (a forceload is
    # per chunk, not counted), and the sweep's later kills would find nothing loaded.
    import ground as G
    from terrain import TerrainUnavailable
    try:
        g = G.load()
    except TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is not available here (%s)" % str(e)[:80])
    mod = TOWERS[tower][0]
    lines = [l for l in mod.cleanup_commands(g) if not l.startswith("#")]
    assert lines[0].startswith("forceload add ") and lines[-1] == "function %s" % mod.ENTITIES_FN
    assert not [l for l in lines if l.startswith(("forceload remove", "kill "))]
    x0, _s, z0, x1, _t, z1 = TOWERS[tower][1]()
    assert lines[0] == "forceload add %d %d %d %d" % (x0, z0, x1, z1)


def test_the_audit_never_imports_the_generator():
    src = (ROOT / "tools" / "chunk_look_audit.py").read_text(encoding="utf-8")
    assert "import chunk_look\n" not in src and "from chunk_look " not in src
