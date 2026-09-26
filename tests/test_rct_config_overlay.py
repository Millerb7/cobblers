"""modpack/config/rctmod-server.toml: our overlay of Cobbleverse's RCT server config, and the simulator reading it.

Written by the test author, not by the session that wrote the overlay.

The owner set relativeLevelCap 0 on 2026-09-24 (Cobbleverse ships 5): a player meets each gym capped at its ace's
level, which is what data/trainers.json's generation_contract (relative_level_cap 0) was authored for. The overlay is
a copy of base-pack/cobbleverse/config/rctmod-server.toml with that one value changed.

What is asserted: after newline normalisation the overlay differs from the base file only in the relativeLevelCap
line (5 -> 0, same indentation, same place) and in added comment lines; the overlay reads initial 20, relative 0 and
the base file still 20, 5; tools/battle_sim.py reads the overlay when it exists and the base file when it does not.

Not covered, and it needs a running server: that the file reaches <server>/config/ (nothing copies overlay configs;
docs/STATE.md), that rctmod reads it, and that it computes the cap as its own comment says (EXP-003).
"""
import difflib
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import battle_sim as B  # noqa: E402

OVERLAY = ROOT / "modpack" / "config" / "rctmod-server.toml"
BASE = ROOT / "base-pack" / "cobbleverse" / "config" / "rctmod-server.toml"
KEY = re.compile(r"^(\s*)relativeLevelCap = (-?\d+)\s*$")


def _lines(p):
    return p.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")


# Without it the overlay carries more than the one decided change: a hand edit or a stale copy of the base file
# rides along (another cap, a series, a spawn setting) and changes the server's behaviour with no decision behind it.
def test_the_overlay_differs_from_the_base_only_in_relative_level_cap_and_comments():
    base, over = _lines(BASE), _lines(OVERLAY)
    removed, added = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=base, b=over, autojunk=False).get_opcodes():
        if op in ("replace", "delete"):
            removed += base[i1:i2]
        if op in ("replace", "insert"):
            added += over[j1:j2]
    assert not [l for l in removed if not KEY.match(l)], "base lines changed or removed: %s" % removed
    assert len(removed) == 1, removed
    new_keys = [l for l in added if not l.strip().startswith("#")]
    assert len(new_keys) == 1 and KEY.match(new_keys[0]), "non-comment lines added: %s" % new_keys
    old, new = KEY.match(removed[0]), KEY.match(new_keys[0])
    assert (old.group(2), new.group(2)) == ("5", "0")
    assert old.group(1) == new.group(1), "the key moved out of its section's indentation"
    # same place: the key's line number, counting only non-comment lines, is unchanged
    code = lambda ls: [l for l in ls if not l.strip().startswith("#")]
    assert code(base).index(removed[0]) == code(over).index(new_keys[0])


# Without it the overlay could set the cap on a key rctmod does not read (a typo, a second copy of the key), or the
# base file could change under us and the overlay silently diverge from a file that no longer says 5.
def test_the_overlay_reads_relative_0_and_the_base_still_5():
    assert B.level_caps(OVERLAY) == (20, 0)
    assert B.level_caps(BASE) == (20, 5)
    assert sum(1 for l in _lines(OVERLAY) if KEY.match(l)) == 1


# Without it the simulator keeps reading Cobbleverse's +5 and every gym it assesses is five levels easier than the
# game the server runs.
def test_battle_sim_reads_the_overlay_when_present():
    assert B.RCT_OVERLAY == OVERLAY and OVERLAY.is_file()
    assert B.RCT_BASE == BASE
    assert B.RCT_CONFIG == OVERLAY


# Without it removing the overlay would leave the simulator pointing at a missing file instead of the base pack's.
def test_battle_sim_falls_back_to_the_base_file_without_an_overlay(monkeypatch):
    real = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: False if self == OVERLAY else real(self))
    spec = importlib.util.spec_from_file_location("battle_sim_without_overlay", ROOT / "tools" / "battle_sim.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.RCT_CONFIG == BASE
