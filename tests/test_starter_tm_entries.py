"""Smeargle the fast pivot (b1280c0, the owner 2026-10-08): what tests/test_mythical_starters_audit.py does not reach.

Written by a reviewer, not by the session that made the change. Two properties:

  1. tools/mythical_starters.py `measure` models Sketch for every line that keeps `1:sketch`, whether or not the line
     carries `sketch_cap` (with the cap off, keying on it measured Smeargle with no Sketch at all: 9/35 against the
     21/35 re-measured in this review). The duel is stubbed out: the property is which movepool is measured, not
     who wins, so other agents' changes to Smeargle's stage shapes do not move it.
  2. The mechanism the `tm:uturn` entry rests on is still in the jars: Cobblemon's `tm` learnset interpreter, and the
     native TM disc (TechnicalMachineItem), the TM Machine's filter (TechnicalMachine.filterTms) and TMCraft's own TM
     item (MoveTeachingItem.isLearnedByTM) all reading the form's TM list. Read with javap in review (2026-10-08,
     Cobblemon-fabric-1.8.0+1.21.1.jar, tmcraft-1.4.19+1.8.0.jar): TechnicalMachineItem refuses with
     tms.cannot_learn unless pokemon.getForm().getMoves().tmLearnableMoves() contains the move; tmLearnableMoves()
     returns a copy of Learnset.tmMoves; the static interpreter registered under "tm" returns that same list; and
     TMCraft's isLearnedByTM calls FormData.getMoves().getTmMoves(). The byte scan below only proves those references
     are still there after a jar update; the call order is the javap reading's.

Not covered (EXP-065): that a TM Machine or disc actually teaches U-turn to a starter Smeargle in game.
"""
from __future__ import annotations

import json
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import mythical_starters as MS  # noqa: E402

SNAPSHOT = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05")


@pytest.fixture(scope="module")
def jar():
    # the read-only snapshot's jar first: battle_sim.find_jar falls back to a 20-second rglob over every worktree
    snap = SNAPSHOT / "mods" / "Cobblemon-fabric-1.8.0+1.21.1.jar"
    if snap.is_file():
        return snap
    import battle_sim
    try:
        return Path(battle_sim.find_jar())
    except battle_sim.SimError as exc:
        pytest.skip("no Cobblemon 1.8.0 jar: %s" % exc)


def _mutant(*subs):
    src = Path(MS.__file__).read_text(encoding="utf-8")
    for old, new in subs:
        assert old in src, "mutation target %r is no longer in the generator; re-aim it" % old
        src = src.replace(old, new, 1)
    mod = types.ModuleType("mythical_starters_mutant")
    mod.__file__ = MS.__file__
    exec(compile(src, "<mutant mythical_starters>", "exec"), mod.__dict__)  # noqa: S102 - deliberate, test-only
    return mod


def _measured_as(mod, monkeypatch, jar):
    """{line id: {gym: what the line was measured as}} for Smeargle and Cosmog with no sketch_cap (as the record is
    today), every duel lost (stubbed)."""
    doc = json.loads(MS.DATA.read_text(encoding="utf-8"))
    doc["lines"] = [ln for ln in doc["lines"] if ln["id"] in ("starter_smeargle", "starter_cosmog")]
    for ln in doc["lines"]:
        ln.pop("sketch_cap", None)
    monkeypatch.setattr(mod, "wins_duel", lambda *a, **k: False)
    monkeypatch.setattr(MS.B, "find_jar", lambda: jar)
    res = mod.measure(doc)
    return {lid: {g: r["as"] for g, r in gyms.items()} for lid, gyms in res.items()}


# Without it measure could go back to keying Sketch on `sketch_cap`, and with the cap off (as now) report Smeargle
# without its movepool: the 9/35 that b1280c0 found and fixed.
def test_measure_models_sketch_for_a_line_that_keeps_it_with_no_cap(jar, monkeypatch):
    doc = json.loads(MS.DATA.read_text(encoding="utf-8"))
    sm = next(ln for ln in doc["lines"] if ln["id"] == "starter_smeargle")
    assert "1:sketch" in sm["moves"]  # the premise: the line keeps Sketch
    got = _measured_as(MS, monkeypatch, jar)
    assert got["starter_smeargle"] and all(a.endswith(" +sketch") for a in got["starter_smeargle"].values()), got
    assert not any(a.endswith("+sketch") for a in got["starter_cosmog"].values()), got  # no Sketch, no pool


# Without it the test above could be passing however measure decides.
def test_mutant_keying_sketch_on_the_cap_is_caught(jar, monkeypatch):
    m = _mutant(('            if "1:sketch" in line["moves"]:', '            if "sketch_cap" in line:'))
    got = _measured_as(m, monkeypatch, jar)
    assert not any(a.endswith("+sketch") for a in got["starter_smeargle"].values()), got


def _class(zf, name):
    return zf.read(name)


# Without it a Cobblemon update that moved the TM check off the form's TM list would leave `tm:uturn` teaching
# nothing, and every repository check (which reads only our data and the species files) would still pass.
def test_the_native_tm_paths_still_read_the_forms_tm_list(jar):
    z = zipfile.ZipFile(jar)
    item = _class(z, "com/cobblemon/mod/common/item/interactive/TechnicalMachineItem.class")
    assert b"tmLearnableMoves" in item and b"getForm" in item and b"tms.cannot_learn" in item
    machine = _class(z, "com/cobblemon/mod/common/api/tms/TechnicalMachine$Companion.class")
    assert b"filterTms" in machine and b"tmLearnableMoves" in machine
    learnset = _class(z, "com/cobblemon/mod/common/api/pokemon/moves/Learnset.class")
    assert b"tmInterpreter" in learnset and b"tmMoves" in learnset
    assert "data/cobblemon/tms/uturn.json" in z.namelist()  # the disc the Machine prints


# Without it a TMCraft update could stop reading the form's TM list, and the crafted tmcraft:tm_uturn (gated at
# badge 5, data/tm_gate.json outlier group 5) would stop being a second route for the same entry.
@pytest.mark.skipif(not (SNAPSHOT / "mods").is_dir(), reason="no server snapshot")
def test_tmcrafts_tm_item_reads_the_forms_tm_list():
    jars = sorted((SNAPSHOT / "mods").glob("tmcraft-*.jar"))
    assert len(jars) == 1, jars
    body = _class(zipfile.ZipFile(jars[0]), "kiwiapollo/tmcraft/item/MoveTeachingItem.class")
    assert b"isLearnedByTM" in body and b"getTmMoves" in body
