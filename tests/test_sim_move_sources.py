"""tools/sim_move_sources.py: every move source a starter form measured by `tools/mythical_starters.py measure` has is
one the simulator's pool can see, or is exempt by name with a reason (mythical_starters.MEASURE_UNMODELLED).

Written by a test author, not by the builder of the Smeargle line or of `measure`. The owner, 2026-10-08: measure gave
Smeargle no Sketch from the cap's removal (e25882e) to b1280c0, and 9/35 was reported as a measurement
(docs/OVERNIGHT_REVIEW_2026-10-06.md N165).

Two layers. The synthetic tests drive `sources` and `gaps_at` with a hand-built line and pool whose expected faults
are countable by eye, so the rule is tested apart from the real data. The jar tests run the check against the real
simulator, and every mutation changes the SIMULATOR's code (tools/mythical_starters.py's text, re-executed as a new
module) and leaves data/mythical_starters.json alone; an autouse fixture fails a test that changes the record.

Not covered: whether the pool's moves are the ones choose_moveset picks, battle_sim's own gym assessment of
catchable species, when a disc or tutor is obtainable, and anything at runtime (EXP-065 for Smeargle's U-turn TM).
"""
from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import battle_sim as B  # noqa: E402
import mythical_starters as M  # noqa: E402  the simulator under mutation
import sim_move_sources as S  # noqa: E402  the check under test

DATA = ROOT / "data" / "mythical_starters.json"
SRC = ROOT / "tools" / "mythical_starters.py"


@pytest.fixture(autouse=True)
def record_untouched():
    # without it a mutation could edit the record and move the expectation with the output, proving nothing
    before = hashlib.sha256(DATA.read_bytes()).hexdigest()
    yield
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == before, "a test changed data/mythical_starters.json"


# ------------------------------------------------------------------------------------------------ synthetic

DOC = {"levels": {"stage_2": 30, "final": 45}}
LINE = {"id": "x", "stages": [{"stage": 1, "species": "a"}], "final": ["b"],
        "moves": ["1:sketch", "5:tackle", "40:surf", "tm:uturn", "tm:rest"],
        "tm_additions": [{"move": "uturn", "decision": "test"}]}
SKETCHABLE = {"tackle", "uturn", "ember", "surf", "rest"}
ALLSP = {"b": {"moves": ["1:pound", "50:hyperbeam", "tm:rest", "tm:flamethrower", "egg:wish"],
               "forms": [{"name": "Alt", "moves": ["1:ember"]}]}}


# the split by kind is the check's whole input; if it drifts, every later verdict is about the wrong sets
def test_a_stage_forms_sources_are_split_by_kind_from_the_record():
    got = S.sources(DOC, LINE, ("stage", 1), 10, ALLSP, SKETCHABLE)
    assert got == {"form:level": {"sketch", "tackle"}, "form:tm_addition": {"uturn"}, "form:tm": {"rest"},
                   "sketch": SKETCHABLE}


# a final keeps what its stages learnt (benched) beside its own native list; losing either hides a source
def test_a_native_finals_sources_are_its_jar_learnset_plus_the_benched_stage_moves():
    got = S.sources(DOC, LINE, ("final", "b"), 50, ALLSP, SKETCHABLE)
    assert got["native:level"] == {"pound", "hyperbeam"}
    assert got["native:tm"] == {"rest", "flamethrower"} and got["native:egg"] == {"wish"}
    assert got["benched:level"] == {"sketch", "tackle", "surf"}       # up to the final's level, 45
    assert got["benched:tm_addition"] == {"uturn"} and got["benched:tm"] == {"rest"}
    assert got["sketch"] == SKETCHABLE                                 # Sketch stays benched too


# a named form with its own moves replaces the species' list; reading the species instead would check the wrong form
def test_a_named_form_with_its_own_moves_replaces_the_species_list():
    assert S.native_learnset(ALLSP, "b alt") == ["1:ember"]
    assert S.native_learnset(ALLSP, "b") == ALLSP["b"]["moves"]


# the Smeargle case's twin: a tm: addition the pool ignores is named, with the move
def test_a_tm_addition_the_pool_does_not_hold_is_named():
    srcs = S.sources(DOC, LINE, ("stage", 1), 10, ALLSP, SKETCHABLE)
    probs, _ = S.gaps_at(srcs, {"sketch", "tackle", "rest", "ember"}, {}, set())
    assert probs == ["form:tm_addition: the pool has none of uturn"]


# a level move at or below the cap must be in the pool unless measure drops it by name (SELF_KO)
def test_a_missing_level_move_is_named_unless_excluded_by_name():
    srcs = S.sources(DOC, LINE, ("stage", 1), 10, ALLSP, SKETCHABLE)
    pool = {"sketch", "uturn", "rest"}
    assert S.gaps_at(srcs, pool, {}, set())[0] == ["form:level: tackle the pool lacks"]
    assert S.gaps_at(srcs, pool, {}, {"tackle"})[0] == []


# a pool move with no source means the simulator invented a move; a number built on it is not a measurement
def test_a_pool_move_no_source_gives_is_named():
    srcs = S.sources(DOC, LINE, ("stage", 1), 10, ALLSP, SKETCHABLE)
    probs, _ = S.gaps_at(srcs, {"sketch", "tackle", "uturn", "rest", "hyperbeam"}, {}, set())
    assert probs == ["the pool has hyperbeam, which no source gives"]


# an unmodelled kind passes only when exempt; without the exemption the same pool is a fault
def test_an_unmodelled_kind_needs_its_exemption():
    srcs = S.sources(DOC, LINE, ("final", "b"), 50, ALLSP, SKETCHABLE)
    pool = {"pound", "hyperbeam", "sketch", "tackle", "surf", "uturn", "rest", "ember"}
    exempt = {"native:tm": "r", "native:egg": "r"}
    assert S.gaps_at(srcs, pool, exempt, set())[0] == []
    probs = S.gaps_at(srcs, pool, {"native:egg": "r"}, set())[0]
    assert probs == ["native:tm: the pool has none of flamethrower"]   # rest is also a benched tm, so not native's


# ------------------------------------------------------------------------------------------------ the real simulator

@pytest.fixture(scope="module")
def jar():
    try:
        return B.find_jar()
    except B.SimError as exc:
        pytest.skip("no Cobblemon 1.8.0 jar: %s" % exc)


@pytest.fixture(scope="module")
def doc():
    return json.loads(DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def plan(jar, doc):
    return M.measure_plan(doc, jar)


def mutant(old, new):
    """tools/mythical_starters.py with `old` replaced once by `new`, as a fresh module."""
    text = SRC.read_text(encoding="utf-8")
    assert text.count(old) == 1, "the mutation's anchor is gone from tools/mythical_starters.py: %r" % old
    mod = types.ModuleType("mythical_starters_mutant")
    mod.__file__ = str(SRC)
    exec(compile(text.replace(old, new), str(SRC), "exec"), mod.__dict__)
    return mod


# the property itself on today's code: without it the check could be red on the real simulator and nobody would know
def test_todays_simulator_sees_every_measured_move_source(doc, plan):
    assert S.check_plan(doc, plan) == []


# THE regression the owner named: Sketch re-gated on sketch_cap (the pre-b1280c0 code) must fail, naming Smeargle
def test_sketch_gated_on_the_cap_again_is_named(jar, doc):
    bad = mutant('if "1:sketch" in line["moves"]:', 'if "sketch_cap" in line:')
    probs = S.check_plan(doc, bad.measure_plan(doc, jar))
    sk = [p for p in probs if "Sketch" in p]
    assert sk and all("starter_smeargle" in p for p in sk), probs
    for n in (1, 2, 3):                          # all three Smeargle forms, each named
        assert any(p.startswith("starter_smeargle stage %d:" % n) for p in sk), sk


# the pool ignoring the forms' tm: entries (U-turn's TM, the owner's 2026-10-08 decision) must fail, naming uturn
def test_tm_entries_dropped_from_the_pool_are_named(jar, doc):
    bad = mutant("moves=list(line[\"moves\"]) + tms,\n", "moves=list(line[\"moves\"]),\n")
    probs = S.check_plan(doc, bad.measure_plan(doc, jar))
    assert probs and all("form:tm_addition: the pool has none of uturn" in p and "starter_smeargle" in p
                         for p in probs), probs


# a form's own learnset replaced by the jar species' list (the in-game form overrides it) must fail on form:level
def test_a_forms_own_moves_overridden_is_named(jar, doc):
    bad = mutant("moves=list(line[\"moves\"]) + tms,\n",
                 "moves=list(allsp[B.key(s[\"species\"])].get(\"moves\") or []) + tms,\n")
    probs = S.check_plan(doc, bad.measure_plan(doc, jar))
    assert any("form:level" in p for p in probs), probs


# measure must refuse to print a number from a pool that misses a source: a broken tool's number is not a measurement
def test_measure_refuses_when_a_source_is_unseen(jar, doc, monkeypatch):
    bad = mutant('if "1:sketch" in line["moves"]:', 'if "sketch_cap" in line:')
    bad_plan = bad.measure_plan(doc, jar)
    monkeypatch.setattr(M, "measure_plan", lambda d: bad_plan)
    with pytest.raises(SystemExit) as e:
        M.measure(doc)
    assert "starter_smeargle" in str(e.value) and "Sketch" in str(e.value)


# an exemption must say why, must exempt something, and must go once the pool models the kind
def test_exemptions_are_reasoned_live_and_still_needed(doc, plan):
    base = dict(M.MEASURE_UNMODELLED)
    assert all(str(v).strip() for v in base.values())
    probs = S.check_plan(doc, plan, exempt=dict(base, **{"native:special": "x"}))
    assert probs == ["MEASURE_UNMODELLED 'native:special' exempts nothing: no measured form has that source"]
    probs = S.check_plan(doc, plan, exempt=dict(base, **{"form:tm_addition": "x"}))
    assert probs == ["MEASURE_UNMODELLED 'form:tm_addition': the pool now models it; drop the exemption"]
    probs = S.check_plan(doc, plan, exempt=dict(base, **{"native:tm": " "}))
    assert probs == ["MEASURE_UNMODELLED 'native:tm' has no reason"]


# dropping an exemption turns its kind back into named faults: the list is what lets them pass, not a silent skip
def test_without_the_native_tm_exemption_the_finals_are_named(doc, plan):
    exempt = {k: v for k, v in M.MEASURE_UNMODELLED.items() if k != "native:tm"}
    # (the exemption hygiene may also speak: a kind whose moves the now non-exempt TM list covers exempts nothing)
    faults = [p for p in S.check_plan(doc, plan, exempt=exempt) if not p.startswith("MEASURE_UNMODELLED")]
    assert faults and all("native:tm: the pool has none of" in p for p in faults)
    assert {p.split()[0] for p in faults} == {ln["id"] for ln in doc["lines"] if ln["final"]}
