"""tools/carry_players.py and the blackout claim ledger: what a re-export carries of the pack's world state.

Written by the test author, not by the session that changed the carry (a71fc28).

Independent sources: vanilla Minecraft saves a command storage namespace <ns> to data/command_storage_<ns>.dat in the
world; tools/blackout_pack.py keeps the claim ledger in `cobblers_recovery:ledger` so that it has a file of its own,
while the shared `cobblers` storage holds, among other things, the re-apply's own progress (the coordinator,
2026-09-27: "the shared cobblers storage must never be carried"); every campaign pack keeps per-player state in scores
(data/scoreboard.dat). Fake worlds come from tests/test_carry_players.py's builders.

Not covered: whether a carried ledger or scoreboard loads in the new world (runtime), and whether a claim's guardian,
which lives in an entity file the carry does not take, is rebuilt from the carried ledger there (recovery/maintain;
EXP-042 proved a rebuild on staging, not after a re-export).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import blackout_pack as BP  # noqa: E402
import carry_players as C  # noqa: E402
from test_carry_players import A, _player, _world  # noqa: E402

LEDGER_FILE = "data/command_storage_cobblers_recovery.dat"
SHARED_FILE = "data/command_storage_cobblers.dat"


@pytest.fixture
def worlds(tmp_path):
    return _world(tmp_path / "old", (A,)), _world(tmp_path / "new", ())


# Without it the ledger's storage and the file the carry takes drift apart (a renamed namespace, a renamed glob), and
# open claims are silently lost at the next re-export.
def test_the_carried_ledger_file_is_the_packs_ledger_namespace():
    ns = BP.LEDGER.split(":", 1)[0]
    assert "data/command_storage_%s.dat" % ns == LEDGER_FILE
    assert ns != "cobblers", "the ledger must not share the cobblers storage file"
    assert LEDGER_FILE in [g for _, g, _ in C.WORLD_WIDE]


# Without it the open item claims owed to players are lost at a re-export, or arrive altered.
def test_the_claim_ledger_is_carried_byte_for_byte_when_present(worlds, tmp_path):
    old, new = worlds
    (old / LEDGER_FILE).write_bytes(b"open claims")
    r = C.carry(old, new, tmp_path / "m.json")
    assert (new / LEDGER_FILE).read_bytes() == b"open claims"
    assert r["categories"]["recovery_ledger"] == {"before": 1, "after": 1}
    assert LEDGER_FILE in json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))["files"]["recovery_ledger"]
    # and the verify notices if it goes missing afterwards
    (new / LEDGER_FILE).unlink()
    with pytest.raises(C.CarryError, match="missing after the copy"):
        C.verify(tmp_path / "m.json")


# Without it a world where nobody has lost a claim yet (no ledger file) cannot be carried at all.
def test_a_world_without_a_ledger_carries(worlds, tmp_path):
    old, new = worlds
    r = C.carry(old, new, tmp_path / "m.json")
    assert r["categories"]["recovery_ledger"] == {"before": 0, "after": 0}
    assert not (new / LEDGER_FILE).exists()


# Without it the re-apply's own progress, kept in the shared cobblers storage, is carried into a fresh export and the
# re-apply there believes steps are done that are not; no other command storage travels either.
def test_the_shared_cobblers_storage_is_never_carried(worlds, tmp_path):
    old, new = worlds
    (old / SHARED_FILE).write_bytes(b"reapply progress")
    (old / "data" / "command_storage_minecraft.dat").write_bytes(b"other storage")
    (old / LEDGER_FILE).write_bytes(b"open claims")
    C.carry(old, new, tmp_path / "m.json")
    assert not (new / SHARED_FILE).exists()
    assert sorted(p.name for p in (new / "data").glob("command_storage_*")) == ["command_storage_cobblers_recovery.dat"]
    files = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))["files"]
    assert not [rel for cat in files.values() for rel in cat if rel == SHARED_FILE]


# Without it a world whose scores were lost (checkpoints, Surf timers, fatigue, flag counters) carries "cleanly" and
# every player silently loses that state.
def test_a_world_without_a_scoreboard_is_refused(worlds, tmp_path):
    old, new = worlds
    (old / "data" / "scoreboard.dat").unlink()
    with pytest.raises(C.CarryError, match="no scoreboard file"):
        C.carry(old, new, tmp_path / "m.json")
    assert not (new / "playerdata").exists()


# Without it the scoreboard now being required could mask the badge check: a disagreeing world must still be refused
# for its badges once its scores are present, and for its scores (not a badge message) when they are not, so the
# fixture's added scoreboard in test_carry_fails_when_badges_and_rctmod_disagree only lets that test reach the check.
def test_the_badge_check_is_reached_with_scores_and_a_missing_scoreboard_is_named_first(tmp_path):
    old, new = _world(tmp_path / "old", ()), _world(tmp_path / "new", ())
    _player(old, A, flags=("gym1_cleared",), defeats=[], memory=[])
    (old / "data" / "rctmod.trainers.ver.dat").write_bytes(b"v")
    with pytest.raises(C.CarryError) as e:
        C.carry(old, new, tmp_path / "m.json")
    assert "no scoreboard file" in str(e.value) and "gym1_cleared" not in str(e.value)
    (old / "data" / "scoreboard.dat").write_bytes(b"scores")
    with pytest.raises(C.CarryError, match="gym1_cleared .*the flag says beaten"):
        C.carry(old, new, tmp_path / "m.json")
