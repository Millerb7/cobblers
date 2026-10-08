"""tools/chunk_look.py and the instrument tubes of the Frostpeak camp and Coldwater Station (R18F, R18CW), N155.

A force-loaded chunk accepts a summon at once but its SAVED entities arrive later (staging 2026-10-08, the stall
merchants). The tubes' old function force-loaded, killed the site's displays and summoned new ones in one tick, so a
re-run whose chunk's displays had not arrived killed nothing and doubled every tube. The fix is R17M's shape
(tools/markets.py, a35a7b6) made reusable: look until a display is seen (or blind after 300 ticks), then kill and
summon, then de-duplicate, count and release.

The world is tests/test_markets_merchant_load.py's LateWorld (tests/mcfunction_sim.py with late saved entities and
`schedule`). The packs are built from synthetic displays, so no heightmap is needed except for R18CW's step list.

Written by the implementer of the fix (minecraft-systems-dev); an independent test-author review is still owed
(CLAUDE.md principle 16).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import chunk_look as CL  # noqa: E402
import chunk_look_audit as CA  # noqa: E402
import frostpeak_camp as FC  # noqa: E402
import mcfunction_sim as S  # noqa: E402
from test_markets_merchant_load import LateWorld  # noqa: E402

TAG = FC.TAG
ENTRY = FC.INSTRUMENTS_FN
HOLDER = FC.INSTRUMENTS_HOLDER
PIVOTS = [(716.5, 115.2, 691.5), (709.5, 115.2, 691.5)]      # two tubes, two chunks (x 704-719)


def _displays():
    out = []
    for i, (x, y, z) in enumerate(PIVOTS):
        out.append({"id": "tube%d" % i, "pivot": [x, y, z], "aim": [x, y + 10, z - 50], "bearing": 0.0,
                    "elevation": 10.0,
                    "command": 'summon minecraft:block_display %.2f %.2f %.2f {block_state:{Name:"minecraft:stone"},'
                               'Tags:["%s","tube%d"]}' % (x, y, z, TAG, i)})
    return out


def _old_shape():
    """The pre-fix instrument function, as tools/frostpeak_camp.py emitted it before this change."""
    xs, zs = [p[0] for p in PIVOTS], [p[2] for p in PIVOTS]
    box = "%d %d %d %d" % (min(xs) // 1, min(zs) // 1, max(xs) // 1, max(zs) // 1)
    lines = ["forceload add " + box,
             "kill @e[type=minecraft:block_display,tag=%s,x=%.1f,y=%.1f,z=%.1f,distance=..24]"
             % (TAG, sum(xs) / 2, PIVOTS[0][1], sum(zs) / 2)]
    lines += [d["command"] for d in _displays()]
    return {ENTRY: lines + ["forceload remove " + box]}


def _world(fns, delay, seeded=True):
    w = LateWorld(fns, delay)
    if seeded:
        for i, (x, y, z) in enumerate(PIVOTS):
            w.save(S.Entity("minecraft:block_display", (x, y, z), tags=(TAG, "tube%d" % i)))
    return w


def _tubes(w):
    return len(w.living("minecraft:block_display", TAG))


# --------------------------------------------------------------------------------------------- the simulated world
@pytest.mark.parametrize("delay", [1, 20, 60])
def test_the_old_one_tick_shape_doubles_every_tube_when_the_saved_displays_arrive_late(delay):
    # Without it the fix has nothing to fix: this is what a re-run did to the tubes.
    w = _world(_old_shape(), delay)
    w.run(ENTRY, CL.STEP_TICKS)
    assert _tubes(w) == 2 * len(PIVOTS)


@pytest.mark.parametrize("delay", [0, 1, 20, 60, 150, 299, 350])
def test_the_chain_leaves_one_of_each_however_late_the_displays_arrive(delay):
    # Without it a re-run doubles the tubes again; 350 is past the blind act and caught by the de-duplication.
    w = _world(FC.instrument_functions(_displays()), delay)
    w.run(ENTRY, CL.STEP_TICKS + 5)
    assert _tubes(w) == len(PIVOTS)
    assert sorted(t for e in w.living("minecraft:block_display", TAG) for t in e.tags if t.startswith("tube")) == \
        ["tube0", "tube1"]
    assert not any(TAG + "_new" in e.tags for e in w.living("minecraft:block_display", TAG))
    assert w.scores[("#" + HOLDER, CL.OBJ)] == len(PIVOTS)
    assert not w.forced, "the chain left its chunks force-loaded"


def test_a_first_run_with_nothing_to_see_acts_blind_inside_the_step_wait():
    # Without it a fresh world (an export erases entities) would never get its tubes.
    w = _world(FC.instrument_functions(_displays()), 20, seeded=False)
    w.run(ENTRY, CL.STEP_TICKS + 5)
    acted = [t for t, _e in w.logged("summon")]
    assert acted and min(acted) == CL.BLIND_TICKS
    assert _tubes(w) == len(PIVOTS) and CL.STEP_SECONDS * 20 >= CL.STEP_TICKS


def test_the_count_reads_minus_one_until_the_chain_ends():
    # Without it reapply could read an earlier run's count and pass a chain that never finished.
    w = _world(FC.instrument_functions(_displays()), 20)
    w.run(ENTRY, 50)
    assert w.scores[("#" + HOLDER, CL.OBJ)] == -1


def _act_at_once(monkeypatch):
    """The generator mutated: the entry runs the act in the tick it force-loads (no look)."""
    orig = CL.chain

    def at_once(base, *a, **k):
        fns = orig(base, *a, **k)
        fns[base] = fns[base] + ["function %s_act" % base]
        return fns
    monkeypatch.setattr(CL, "chain", at_once)


def test_dropping_the_look_in_the_generator_doubles_again(monkeypatch):
    # Without it the look could be removed and the simulated test above would not notice.
    _act_at_once(monkeypatch)
    w = _world(FC.instrument_functions(_displays()), 150)
    w.run(ENTRY, CL.STEP_TICKS + 5)
    assert _tubes(w) == 2 * len(PIVOTS)


# --------------------------------------------------------------------------------------------- the chain's audit
def _write(tmp_path, fns):
    for rel, lines in CL.files(fns).items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


def test_the_audit_passes_the_chain_and_never_imports_its_generator(tmp_path):
    # Without it the audit could fail everything, or share the generator's code and agree with its bugs.
    assert CA.problems(_write(tmp_path, FC.instrument_functions(_displays())), ENTRY, TAG) == []
    src = (ROOT / "tools" / "chunk_look_audit.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+(chunk_look|frostpeak_camp|coldwater_station)\b", src, re.M)


def test_the_audit_names_the_old_shape(tmp_path):
    # Without it the one-tick shape could come back and pass.
    probs = CA.problems(_write(tmp_path, _old_shape()), ENTRY, TAG)
    assert any("in the tick it force-loads" in p for p in probs)


def test_the_audit_names_an_act_with_no_look(tmp_path, monkeypatch):
    # The generator mutation above, caught statically as well.
    _act_at_once(monkeypatch)
    probs = CA.problems(_write(tmp_path, FC.instrument_functions(_displays())), ENTRY, TAG)
    assert any("in the tick it force-loads" in p for p in probs)


def test_the_audit_names_a_release_before_the_end_and_a_short_blind_limit(tmp_path, monkeypatch):
    # Without it the chain could release its chunks under the act, or act blind before the displays could arrive.
    monkeypatch.setattr(CL, "POLLS", 3)
    fns = FC.instrument_functions(_displays())
    rm = next(l for l in fns[ENTRY + "_done"] if l.startswith("forceload remove"))
    fns[ENTRY + "_look"] = fns[ENTRY + "_look"] + [rm]
    probs = CA.problems(_write(tmp_path, fns), ENTRY, TAG)
    assert any("the chain is not over" in p for p in probs)
    assert any("under %d" % CA.BLIND_MIN in p for p in probs)


def test_the_audit_names_a_look_that_proves_nothing(tmp_path):
    # Without it a look at some other entity could mark the box shown while the site's displays are still out.
    fns = FC.instrument_functions(_displays())
    fns[ENTRY + "_look"] = [l.replace("tag=%s," % TAG, "tag=someone_else,") if " if entity " in l else l
                            for l in fns[ENTRY + "_look"]]
    probs = CA.problems(_write(tmp_path, fns), ENTRY, TAG)
    assert any("without a look or the blind limit" in p for p in probs)


# --------------------------------------------------------------------------------------------- the reapply steps
def _order(acts, box):
    kinds = [(k, v) for k, v in acts]
    rm = kinds.index(("cmd", "forceload remove " + box))
    start = next(i for i, (k, v) in enumerate(kinds) if k == "fn" and v.endswith("/instruments"))
    wait = kinds[start + 1]
    check = kinds[start + 2]
    return rm, start, wait, check


def test_r18f_releases_its_own_forceload_before_the_chain_and_reads_the_count_back():
    # Without it the step's remove would release the chunks under the chain (a forceload is per chunk, not counted).
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    block = src[src.index('out.append(("R18F"'):src.index('out.append(("R18A"')]
    assert block.index('("cmd", "forceload remove 680 680 735 735")') < block.index("frostpeak_camp.instrument_steps()")
    assert "frostpeak_camp/instruments" not in block
    acts = FC.instrument_steps()
    assert acts[0] == ("fn", ENTRY) and acts[1] == ("wait", CL.STEP_SECONDS)
    assert acts[2] == ("check", ("chunk_look", HOLDER, 2, "the Frostpeak camp's instrument tubes"))
    assert 'kind == "check" and isinstance(v, tuple) and v[0] == "chunk_look"' in src


def test_r18cw_releases_its_own_forceload_before_the_chain_and_reads_the_count_back():
    import coldwater_station as CS
    import ground as G
    try:
        g = G.Ground()
    except Exception as e:      # the canonical heightmap is outside the repo
        pytest.skip("canonical heightmap unavailable: %s" % e)
    acts = CS.placement_steps(None, g)
    rm, start, wait, check = _order(acts, "%d %d %d %d" % CS.forceload_box())
    assert rm < start
    assert wait == ("wait", CL.STEP_SECONDS)
    assert check == ("check", ("chunk_look", CS.INSTRUMENTS_HOLDER, 2, "Coldwater Station's instrument tubes"))
