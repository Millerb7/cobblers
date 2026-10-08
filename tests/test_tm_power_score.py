"""tools/tm_power_score.py: the scorer behind the TM gate's power rule, and its --check.

Written by a reviewer, not by the session that built the power rule (2026-10-08). Until now nothing tested the scorer
itself: tests/test_tm_gate.py reads the COMMITTED table (docs/mechanics/TM_POWER_GATE.json) and checks eleven of its
scores, and nothing anywhere ran `tm_power_score.py --check`, so a score edited by hand in the table (with a matching
power_badge) passed tools/tm_gate.py.

Where the expectations come from:
  - the term tests: synthetic move records (ids that are in none of the tool's hand tables), each scored by hand from
    docs/mechanics/TM_POWER_GATE.md 2.1 and 2.2, arithmetic in the comment;
  - REAL_BY_HAND: 28 real moves whose fields were read from Mega Showdown's moves.js in the 2026-10-05 snapshot
    (sha256 6e41d189...) and scored by hand the same way; their bands from TM_POWER_GATE.md 3, typed below;
  - --check: a synthetic server (tests/tm_gate_fixture.py) and a moves dump written here.
The mutation tests rewrite the scorer's SOURCE in memory and leave every data file alone.

Not covered: whether the valuation is good (the owner's judgement), and the node step that dumps moves.js unless node
and the snapshot are both present (the last test).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import tm_power_score as S  # noqa: E402
import tm_gate_fixture as F  # noqa: E402

SNAPSHOT = Path(os.environ.get("COBBLERS_SERVER_SNAPSHOT",
                               "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05"))
TABLE = ROOT / "docs" / "mechanics" / "TM_POWER_GATE.json"


def band_by_hand(score):
    """docs/mechanics/TM_POWER_GATE.md 3, typed here: badge 1 below 35; tops 54/64/74/84/94/104 inclusive; 8 above.
    Rounded to 0.1 first, as the table prints a score."""
    s = round(score, 1)
    if s < 35:
        return 1
    for b, top in ((2, 54), (3, 64), (4, 74), (5, 84), (6, 94), (7, 104)):
        if s <= top:
            return b
    return 8


def _mv(category="Physical", bp=0, acc=100, pp=15, **kw):
    return dict({"name": "fixture", "category": category, "basePower": bp, "accuracy": acc, "pp": pp,
                 "priority": 0, "flags": {}, "target": "normal"}, **kw)


# id -> (move record, the score by hand). Ids are prefixed fx_ so no NOMINAL / CONDITIONAL / SEC_CODE entry applies.
DAMAGING = {
    "fx_plain": (_mv(bp=80), 80.0),                                                     # 80
    "fx_acc_burn": (_mv(bp=100, acc=90, pp=10, secondary={"chance": 30, "status": "brn"}), 98.1),  # .9 x (100 + 9)
    "fx_2to5": (_mv(bp=25, pp=10, multihit=[2, 5]), 77.5),                               # 25 x 3.1
    "fx_fixed_hits": (_mv(bp=30, pp=30, multihit=2), 60.0),                              # 30 x 2
    "fx_charge": (_mv(bp=120, pp=10, flags={"charge": 1}), 60.0),                        # 120 x .5
    "fx_recharge": (_mv(bp=150, acc=90, pp=5, flags={"recharge": 1}), 64.125),           # .9 x 150 x .5 x .95
    "fx_recoil": (_mv(bp=120, recoil=[1, 3]), 100.0),                                    # 120 x (1 - 1/6)
    "fx_drain": (_mv(bp=75, pp=10, drain=[1, 2]), 90.0),                                 # 75 + .4 x .5 x 75
    "fx_priority1": (_mv(bp=40, pp=30, priority=1), 55.0),                               # 40 + 15
    "fx_priority3": (_mv(bp=40, pp=30, priority=3), 70.0),                               # 40 + 15 x 2 (two counted)
    "fx_negative": (_mv(bp=150, acc=90, pp=5, priority=-3), 118.25),                     # .9 x 150 x .95 - 10
    "fx_pivot": (_mv(bp=70, pp=20, selfSwitch=True), 90.0),                              # 70 + 20
    "fx_selfdrop": (_mv(category="Special", bp=130, acc=90, pp=5, self={"boosts": {"spa": -2}}), 94.4775),
    #                                                                                    .9 x 130 x .85 x .95
    "fx_faint": (_mv(bp=200, pp=5, selfdestruct="always"), 66.5),                        # 200 x .35 x .95
    "fx_locked": (_mv(bp=120, pp=10, self={"volatileStatus": "lockedmove"}), 102.0),     # 120 x .85
    "fx_speed_drop": (_mv(bp=60, acc=95, secondary={"chance": 100, "boosts": {"spe": -1}}), 66.5),  # .95 x (60 + 10)
    "fx_flinch": (_mv(bp=80, secondary={"chance": 30, "volatileStatus": "flinch"}), 84.5),  # 80 + .3 x 15
    "fx_self_raise": (_mv(bp=50, pp=20, secondary={"chance": 100, "self": {"boosts": {"spe": 1}}}), 62.0),  # 50 + 12
    "fx_crash": (_mv(bp=130, acc=90, pp=10, hasCrashDamage=True), 105.3),                # .9 x 130 x .9
    "fx_always_crit": (_mv(bp=60, pp=10, willCrit=True), 90.0),                          # 60 x 1.5
    "fx_true_acc": (_mv(category="Special", bp=60, acc=True, pp=20), 60.0),              # never misses: x1
}
STATUS = {
    "fx_par": (_mv(category="Status", acc=90, pp=20, status="par"), 90.0),               # .9 x 100
    "fx_sleep_low_pp": (_mv(category="Status", pp=5, status="slp"), 104.5),               # 110 x .95
    "fx_plus2": (_mv(category="Status", acc=True, pp=20, target="self", boosts={"atk": 2}), 70.0),  # 35 x 2
    "fx_plus3": (_mv(category="Status", acc=True, pp=20, target="self", boosts={"atk": 3}), 87.5),  # 70 + 35 / 2
    # Shell Smash's fields: 70 for the better +2, half of 70 for the other, speed +2 = 60, each defence -1 = -20
    "fx_smash": (_mv(category="Status", acc=True, target="self",
                     boosts={"def": -1, "spd": -1, "atk": 2, "spa": 2, "spe": 2}), 125.0),
    "fx_growl2": (_mv(category="Status", pp=30, boosts={"atk": -1, "spa": -1}), 30.0),   # 15 + 15
    "fx_hazard": (_mv(category="Status", acc=True, pp=20, target="foeSide", sideCondition="stealthrock"), 85.0),
    "fx_heal": (_mv(category="Status", acc=True, pp=10, target="self", heal=[1, 2]), 75.0),
    "fx_phaze": (_mv(category="Status", acc=True, pp=20, forceSwitch=True, priority=-6), 45.0),
    "fx_rain": (_mv(category="Status", acc=True, pp=5, target="all", weather="RainDance"), 47.5),  # 50 x .95
    "fx_ally": (_mv(category="Status", acc=True, pp=20, target="adjacentAlly", boosts={"atk": 2}), 10.5),  # .15 x 70
}

# Real moves, fields read from the snapshot's moves.js, scored by hand from TM_POWER_GATE.md 2 (the arithmetic is in
# the comment), banded by hand from 3. They are the moves the shelf disagreements, the chain raises and the outlier
# groups 5, 7, 9 and 15 turn on, plus a few anchors.
REAL_BY_HAND = {
    "thunderbolt": (93.0, 6),    # 90 + 10% par x 30
    "toxic": (85.5, 6),          # 90% x tox 95
    "uturn": (90.0, 6),          # 70 + pivot 20 (group 5 then places it at 5)
    "scald": (89.0, 6),          # 80 + 30% brn x 30
    "headbutt": (74.5, 5),       # 70 + 30% flinch x 15: half a point over the badge-4 top
    "hyperbeam": (64.1, 4),      # 90% x 150 x .5 recharge x .95 (5 PP)
    "closecombat": (102.9, 7),   # 120 x .95 x .95 (def, spd -1) x .95 (5 PP)
    "stunspore": (75.0, 5),      # 75% x par 100
    "spore": (110.0, 8),         # slp 110
    "bonemerang": (90.0, 6),     # 90% x 50 x 2
    "boneclub": (56.5, 3),       # 85% x (65 + 10% flinch x 15)
    "surf": (90.0, 6),           # 90
    "swordsdance": (70.0, 4),    # +2 atk: 35 x 2
    "stealthrock": (85.0, 6),    # hazard 85
    "knockoff": (65.0, 4),       # 65; the item effect is code, not valued
    "drainpunch": (90.0, 6),     # 75 + .4 x 1/2 x 75
    "outrage": (102.0, 7),       # 120 x .85 locked
    "bravebird": (100.2, 7),     # 120 x (1 - .5 x .33)
    "extremespeed": (106.0, 8),  # 80 x .95 (5 PP) + priority 2 x 15
    "roar": (45.0, 2),           # forces a switch 45
    "nobleroar": (30.0, 1),      # two target stages x 15
    "doublekick": (60.0, 3),     # 30 x 2
    "triplekick": (46.8, 2),     # 90% x nominal 52 (TM_POWER_GATE.md 2.1: power computed)
    "shockwave": (60.0, 3),      # 60, never misses
    "overheat": (94.5, 7),       # 90% x 130 x .85 (spa -2) x .95 (5 PP)
    "rockslide": (71.5, 4),      # 90% x (75 + 30% flinch x 15) = 71.55, printed 71.5
    "sludgebomb": (94.5, 7),     # 90 + 30% psn x 15
    "ironhead": (84.5, 6),       # 80 + 30% flinch x 15
}


def _mutant(*subs):
    """tools/tm_power_score.py with its own source rewritten in memory, as a fresh module."""
    src = Path(S.__file__).read_text(encoding="utf-8")
    for old, new in subs:
        assert old in src, "mutation target %r is no longer in the scorer; re-aim it" % old
        src = src.replace(old, new, 1)
    mod = types.ModuleType("tm_power_score_mutant")
    mod.__file__ = S.__file__
    exec(compile(src, "<mutant tm_power_score>", "exec"), mod.__dict__)  # noqa: S102 - deliberate, test-only
    return mod


def term_failures(mod):
    out = []
    for mid, (mv, want) in DAMAGING.items():
        got = mod.score_damaging(mid, mv)[0]
        if abs(got - want) > 1e-6:
            out.append("%s: %s, by hand %s" % (mid, got, want))
    for mid, (mv, want) in STATUS.items():
        got = mod.score_status(mid, mv)[0]
        if abs(got - want) > 1e-6:
            out.append("%s: %s, by hand %s" % (mid, got, want))
    return out


# Without it a change to any term of the documented rule (accuracy, hits, recoil, drain, priority, pivot, PP ...)
# rescored every TM and moved badges with nothing to say the scorer no longer does what TM_POWER_GATE.md 2 says.
def test_each_term_of_the_score_is_the_documented_arithmetic():
    assert term_failures(S) == []


# Without it the term test above could be passing whatever the scorer did: each mutant breaks one term of the
# generator's code and the hand arithmetic must name the move that term decides.
@pytest.mark.parametrize("subs, named", [
    ((("return a * (p * h * m + s) + flat * (a if flat > 0 else 1), a, why", "return (p * h * m + s) + flat, a, why"),),
     "fx_acc_burn"),
    ((("PIVOT_DAMAGING, PHAZE_DAMAGING = 20, 10", "PIVOT_DAMAGING, PHAZE_DAMAGING = 0, 10"),), "fx_pivot"),
    ((("flat += PRIORITY_PLUS * min(pr, 2)", "flat += PRIORITY_PLUS * pr"),), "fx_priority3"),
    ((("    if (mv.get(\"pp\") or 99) <= LOW_PP[0]:\n        m *=", "    if (mv.get(\"pp\") or 99) < LOW_PP[0]:\n        m *="),),
     "fx_recharge"),
    ((("v += 0.5 * stage(off[1], OFFENSE_STAGE)", "v += stage(off[1], OFFENSE_STAGE)"),), "fx_smash"),
    ((("MULTIHIT_2_5 = 3.1", "MULTIHIT_2_5 = 3.5"),), "fx_2to5"),
])
def test_mutants_of_the_scorer_are_caught(subs, named):
    fails = term_failures(_mutant(*subs))
    assert any(f.startswith(named + ":") for f in fails), fails


# Without it the committed table could carry a score the documented rule does not give for the moves the shelf
# disagreements, the chain raises and the pivot/set-up/recharge groups turn on, and the gate would place them by it.
def test_the_committed_table_scores_real_moves_as_worked_by_hand():
    table = json.loads(TABLE.read_text(encoding="utf-8"))["tms"]
    wrong = {}
    for move, (score, badge) in REAL_BY_HAND.items():
        row = table["tmcraft:tm_" + move]
        assert band_by_hand(score) == badge, move  # the hand band agrees with the hand score
        if (row["score"], row["power_badge"]) != (score, badge):
            wrong[move] = ((row["score"], row["power_badge"]), (score, badge))
    assert wrong == {}


# Without it a row whose power_badge is not its score's band (by the bands typed here, not tm_gate.band) could sit in
# the table; tools/tm_gate.py checks the same thing but with its own band(), so a fault in both would agree.
def test_every_rows_power_badge_is_its_scores_band_by_hand():
    table = json.loads(TABLE.read_text(encoding="utf-8"))["tms"]
    wrong = {k: (r["score"], r["power_badge"], band_by_hand(r["score"])) for k, r in table.items()
             if r["power_badge"] != band_by_hand(r["score"])}
    assert wrong == {}
    assert len(table) == 802  # the 2026-10-05 snapshot's crafted TMs


# ---------------------------------------------------------------- --check against a synthetic server

def _server_with_moves(tmp):
    """The fixture server and a moves dump for its 31 TMs: every one a plain 60-power Normal move except Tackle (40)."""
    server, _, exp = F.build_server(tmp)
    moves = {rid.split("tm_", 1)[1]: _mv(bp=60) for rid in exp["tms"]}
    moves["tackle"] = _mv(bp=40)
    mj = Path(tmp) / "moves.json"
    mj.write_text(json.dumps(moves), encoding="utf-8")
    return server, mj, moves


def _run(mod, server, mj, out, check):
    argv = ["--server-dir", str(server), "--moves-json", str(mj), "--out", str(out)] + (["--check"] if check else [])
    return mod.main(argv)


def stale_check_failures(mod, tmp):
    """Write a table, then make it stale four ways; --check must return 1 for each and 0 for the fresh one."""
    tmp = Path(tmp)
    server, mj, moves = _server_with_moves(tmp)
    out = tmp / "table.json"
    fails = []
    if _run(mod, server, mj, out, False) != 0:
        return ["the write itself failed"]
    fresh = out.read_text(encoding="utf-8")
    if _run(mod, server, mj, out, True) != 0:
        fails.append("a fresh table is reported stale")
    # 1. a score edited by hand, with its power_badge kept consistent (tools/tm_gate.py accepts this one)
    doc = json.loads(fresh)
    assert doc["tms"]["tmcraft:tm_tackle"]["score"] == 40.0  # the write scored Tackle at its 40
    out.write_text(fresh.replace('"score": 40.0, "power_badge": 2', '"score": 60.0, "power_badge": 3'),
                   encoding="utf-8")
    if _run(mod, server, mj, out, True) != 1:
        fails.append("a hand-edited score passed --check")
    # 2. the move data changed (a new Mega Showdown, same moves.js path)
    out.write_text(fresh, encoding="utf-8")
    moves["tackle"] = _mv(bp=90)
    mj.write_text(json.dumps(moves), encoding="utf-8")
    if _run(mod, server, mj, out, True) != 1:
        fails.append("a changed move passed --check")
    moves["tackle"] = _mv(bp=40)
    mj.write_text(json.dumps(moves), encoding="utf-8")
    # 3. the jar's moves.js has another sha256 (the dump is the same; the table records the jar's hash)
    jar = server / "mods" / F.MSD_JAR
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("fabric.mod.json", json.dumps({"id": "mega_showdown"}))
        z.writestr(F.MSD_MOVES, F.MSD_TEXT + "// another release\n")
    if _run(mod, server, mj, out, True) != 1:
        fails.append("a moves.js with another sha256 passed --check")
    # 4. no committed table at all
    out.unlink()
    if _run(mod, server, mj, out, True) != 1:
        fails.append("a missing table passed --check")
    return fails


# Without it --check, the only thing that says the committed scores are the scorer's own, could pass a stale table:
# a hand edit, a changed move or a new moves.js would all reach the gate unnoticed.
def test_check_fails_on_a_stale_table(tmp_path, capsys):
    assert stale_check_failures(S, tmp_path) == []


# Without it the --check test above could be passing on a comparison that never fails.
def test_mutant_check_that_always_passes_is_caught(tmp_path, capsys):
    m = _mutant(("        if old == text:", "        if True:"))
    fails = stale_check_failures(m, tmp_path)
    assert "a hand-edited score passed --check" in fails and "a missing table passed --check" in fails, fails


# Without it the committed table could drift from what the scorer makes of the server's real moves.js (a hand edit, a
# constant changed without a rewrite), and nothing in the repository ran --check to say so.
@pytest.mark.skipif(not (SNAPSHOT / "mods").is_dir() or shutil.which("node") is None,
                    reason="needs the server snapshot and node")
def test_the_committed_table_is_what_the_scorer_makes_of_the_snapshot(capsys):
    assert S.main(["--server-dir", str(SNAPSHOT), "--check"]) == 0, capsys.readouterr().out
