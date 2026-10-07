"""One leader per gym: the retire function and the swap, judged by a reader that wrote none of it (A1 re-audit,
2026-10-08, after the integrator both fixed the retire and edited the auditor's test to match: review N95).

Every expectation here is derived from the GENERATED TEXT and from data the generator does not compute: the old
seat is data/challenge_mode.json `spawner.at`; the one spawner and the swap's reach are read back out of the cycle's
own lines; the guard's radius out of the retire's own lines. The rule that joins them is the triangle inequality,
not the generator's formula. Mutations edit tools/challenge_mode.py, never data/. Template bosses are judged with
`single_leader.rollout` set to "all" on an IN-MEMORY copy of the data; the file's rollout stays Brock.

What this does not prove: anything rctmod does. Whether a spawner respawns a killed leader, whether an orphaned
trainer (its spawner gone) despawns, whether InBattle reads 1b during a battle (staging saw 0b on a standing trainer
only), and whether a TrainerId merge changes the team (E7) are the staging and in-game proofs in
docs/mechanics/ONE_LEADER_SWAP.md.
"""
from __future__ import annotations

import copy
import itertools
import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import challenge_mode as CM  # noqa: E402
import challenge_mode_audit as A  # noqa: E402
import route_trainers as RT  # noqa: E402

DATA = json.loads((ROOT / "data" / "challenge_mode.json").read_text(encoding="utf-8"))
SFX = DATA["id_suffix"]
TAG = DATA["mode"]["tag"]
SPAWNER = "rctmod:trainer_spawner"
CYCLE = "data/cobblers/function/trainers/challenge/cycle.mcfunction"
RETIRE = "data/cobblers/function/trainers/challenge/retire_%s.mcfunction"


def _all():
    d = copy.deepcopy(DATA)
    d["single_leader"]["rollout"] = "all"
    return d


@pytest.fixture(scope="module")
def built_all():
    """The trainers pack with every boss standing as one leader (in memory)."""
    d = _all()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(CM, "doc", lambda: d)
        return RT.files(), d


def lines(v):
    return [l.strip() for l in (v if isinstance(v, list) else str(v).splitlines()) if l.strip()]


def mutated(monkeypatch, edits, d):
    """tools/challenge_mode.py with exact text edits (each must match once), reading the in-memory data `d`."""
    path = ROOT / "tools" / "challenge_mode.py"
    src = path.read_text(encoding="utf-8")
    for old, new in edits:
        assert src.count(old) == 1, "mutation anchor not unique: %r" % old[:60]
        src = src.replace(old, new)
    mod = types.ModuleType("challenge_mode")
    mod.__file__ = str(path)
    exec(compile(src, str(path), "exec"), mod.__dict__)
    mod.doc = lambda: d
    return mod


def swap_anchor(cycle, cid):
    """(one spawner cell, swap reach) read from the cycle line that merges the spawner to the Challenge id."""
    rx = re.compile(r"positioned (-?\d+)\.5 (-?\d+) (-?\d+)\.5 as @p\[distance=\.\.([0-9.]+)\] if entity @s\[tag=%s\] "
                    r".* run data merge block (-?\d+) (-?\d+) (-?\d+) \{TrainerIds:\[\"%s\"\]\}$"
                    % (re.escape(TAG), re.escape(cid)))
    hits = [m for m in (rx.search(l) for l in cycle) if m]
    assert len(hits) == 1, "%s: %d swap lines merge the spawner to the Challenge id" % (cid, len(hits))
    m = hits[0]
    at, block = tuple(int(x) for x in m.groups()[:3]), tuple(int(x) for x in m.groups()[4:7])
    assert at == block, "%s: the swap measures the player from %s but merges the spawner at %s" % (cid, at, block)
    return at, float(m.group(4))


GUARD = re.compile(r"positioned (-?\d+)\.5 (-?\d+) (-?\d+)\.5 unless entity @a\[distance=\.\.([0-9.]+)\] run kill ")


def dist(a, b):
    return sum((p - q) ** 2 for p, q in zip(a, b)) ** 0.5


def guard_problems(retire, cycle, d):
    out = []
    for up, e in sorted(d["bosses"].items()):
        cid = up + SFX
        c = tuple(e["spawner"]["at"])
        n, reach = swap_anchor(cycle, cid)
        kills = [l for l in retire(up, cid, e) if " run kill " in l]
        if not kills:
            out.append("%s: no kill line" % cid)
        for l in kills:
            m = GUARD.search(l)
            if not m:
                out.append("%s: a kill with no player guard: %s" % (cid, l[:100]))
                continue
            at, r = tuple(int(x) for x in m.groups()[:3]), float(m.group(4))
            # any player the swap can follow is within reach of n, hence within reach + |c n| of c
            if at != c or r < reach + dist(c, n):
                out.append("%s: guard ..%g at %s; a player %g from the one spawner %s is %g from the old seat %s"
                           % (cid, r, at, reach, n, reach + dist(c, n), c))
    return out


# ------------------------------------------------------------------------------------------------ the guard
# Without it the retire's kill could take the one leader while a Challenge player within the swap's reach has
# turned him to the Challenge id (the defect 2650a73 found for Brock); judged here for all thirteen.
def test_the_retire_guard_covers_every_player_the_swap_can_follow(built_all):
    files, d = built_all
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(CM, "doc", lambda: d)
        assert guard_problems(CM.retire_lines, lines(files[CYCLE]), d) == []


# Without it the guard check above could pass on a generator it cannot fail: the guard narrowed to the swap's reach
# must be caught for some boss (Blue's seats are 5 apart, Brock's 2).
def test_the_guard_check_fails_a_generator_whose_guard_ignores_the_gap(built_all, monkeypatch):
    files, d = built_all
    mut = mutated(monkeypatch, [("reach() + math.ceil(gap))", "reach())")], d)
    bad = guard_problems(mut.retire_lines, lines(files[CYCLE]), d)
    assert any("kanto_brock_challenge" in b for b in bad) and len(bad) >= 13


# Without it the swap's reach could shrink below rctmod's sight, and a trainer would start a battle on sight with a
# player whose mode it never read.
def test_the_swap_reach_covers_rctmods_force_battle_distance(built_all):
    files, d = built_all
    fb = float(A.toml_value(ROOT / "modpack" / "config" / "rctmod-server.toml", "forceBattleMaxDistance"))
    for up in d["bosses"]:
        _n, reach = swap_anchor(lines(files[CYCLE]), up + SFX)
        assert reach >= fb, (up, reach, fb)


# ------------------------------------------------------------------------------------------------ idempotence
def ungated(retire_lines, d):
    """Retire lines that change the world without first testing that the second spawner still stands."""
    out = []
    for up, e in sorted(d["bosses"].items()):
        cid = up + SFX
        x, y, z = e["spawner"]["at"]
        has = 'execute if block %d %d %d %s{TrainerIds:["%s"]} ' % (x, y, z, SPAWNER, cid)
        for l in retire_lines(up, cid, e):
            if l.startswith("#") or re.fullmatch(r"tag @e\[type=rctmod:trainer,tag=\w+\] remove \w+", l):
                continue   # a comment, or the bare clean-up of the retire's own keep tag
            if not l.startswith(has):
                out.append("%s: %s" % (cid, l[:110]))
    return out


# Without it a re-run of R17L (every re-apply runs it) could kill again. The integrator replaced the auditor's
# "kill without has" mutation (9c08840) on the argument that the widened guard makes `has` redundant; it does not:
# see the next test. Every effect line must test the second spawner first.
def test_every_effect_line_of_the_retire_waits_for_the_second_spawner(built_all):
    _files, d = built_all
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(CM, "doc", lambda: d)
        assert ungated(CM.retire_lines, d) == []


# Without it the gate check above could pass on a generator that drops the gate.
def test_the_gate_check_fails_a_kill_without_the_block_test(built_all, monkeypatch):
    _files, d = built_all
    mut = mutated(monkeypatch, [('"execute %s %s run kill @e[%s]" % (has, near, sel % (SEAT_BOX, cid))',
                                 '"execute %s run kill @e[%s]" % (near, sel % (SEAT_BOX, cid))')], d)
    assert len(ungated(mut.retire_lines, d)) == 13


def stand(cell):
    return (cell[0] + 0.5, cell[1] + 1.0, cell[2] + 0.5)


def lag_world(up, e, cycle, second_spawner):
    """The leader still on the Challenge id with nobody near: a Challenge player left the swap's reach (or a battle
    ended) less than one cycle (10 ticks) ago, so the nobody-near line has not yet run."""
    cid = up + SFX
    c = tuple(e["spawner"]["at"])
    n, _r = swap_anchor(cycle, cid)
    blocks = {n: '%s{TrainerIds:["%s"]}' % (SPAWNER, cid), (n[0], n[1] - 1, n[2]): "minecraft:redstone_block",
              c: '%s{TrainerIds:["%s"]}' % (SPAWNER, cid) if second_spawner else "minecraft:stone",
              (c[0], c[1] - 1, c[2]): "minecraft:redstone_block" if second_spawner else "minecraft:stone"}
    return A.CommandWorld(blocks, [{"id": cid, "battle": False, "pos": stand(n), "who": "leader"}], [])


# Without it `has` could be dropped as "defence in depth". It is the only thing that keeps a RE-RUN from killing the
# one leader in the lag window: a Challenge player stepped out of reach under 10 ticks ago, the leader still carries
# the Challenge id, nobody is within the guard. The integrator's argument assumed the cycle had converged.
@pytest.mark.parametrize("gated", [True, False])
def test_a_rerun_in_the_lag_window_kills_nobody_only_because_of_the_block_test(built_all, monkeypatch, gated):
    files, d = built_all
    cycle = lines(files[CYCLE])
    mod = mutated(monkeypatch, [] if gated else [(
        '"execute %s %s run kill @e[%s]" % (has, near, sel % (SEAT_BOX, cid))',
        '"execute %s run kill @e[%s]" % (near, sel % (SEAT_BOX, cid))')], d)
    killed = []
    for up, e in sorted(d["bosses"].items()):
        w = lag_world(up, e, cycle, second_spawner=False)
        for l in [l for l in mod.retire_lines(up, up + SFX, e) if not l.startswith("#")]:
            w.run(l)
        if not w.trainers:
            killed.append(up)
    assert (killed == []) if gated else (len(killed) == 13), killed


# ------------------------------------------------------------------------------------------------ open defects
# Recorded as strict xfails: each flips to a pass, and fails the run, the day the generator is fixed, so the
# record cannot go stale. Defect text and path:line are in the reason.

# The FIRST run has the same lag window, and there `has` holds: the one leader, still on the Challenge id, is killed
# out of battle. Low impact if rctmod's spawner respawns him (not verified); R17L run with nobody online cannot hit it.
@pytest.mark.xfail(strict=True, reason="tools/challenge_mode.py:376 kills every Challenge-id trainer within 24 of the "
                   "old seat; the one leader is 1-5 blocks away and carries that id for up to 10 ticks after a "
                   "Challenge player leaves reach or a battle ends")
def test_the_first_run_never_kills_the_one_leader_in_the_lag_window(built_all):
    files, d = built_all
    cycle = lines(files[CYCLE])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(CM, "doc", lambda: d)
        up, e = "kanto_brock", d["bosses"]["kanto_brock"]
        w = lag_world(up, e, cycle, second_spawner=True)
        for l in [l for l in CM.retire_lines(up, up + SFX, e) if not l.startswith("#")]:
            w.run(l)
    assert any(t.get("who") == "leader" for t in w.trainers)


# A player within the guard on the FIRST run: the kills are skipped but the two setblocks still run (they test `has`
# only), so the second spawner goes and its trainer stays. No later run can remove it, because every line now fails
# `has`. The cycle then renames it to the Normal id: two leaders, for good. single_leader_verify reports it (two
# Normal ids, or "NOT checked" while a player is within 17), but the remedy is by hand.
@pytest.mark.xfail(strict=True, reason="tools/challenge_mode.py:381-382: the setblocks are gated by `has` but not by "
                   "the player guard, so a run with a player near orphans the old trainer and a re-run cannot repair it")
def test_a_first_run_with_a_player_near_leaves_no_orphaned_second_trainer(built_all):
    files, d = built_all
    cycle = lines(files[CYCLE])
    up, e = "kanto_brock", d["bosses"]["kanto_brock"]
    cid = up + SFX
    c = tuple(e["spawner"]["at"])
    n, _r = swap_anchor(cycle, cid)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(CM, "doc", lambda: d)
        rl = [l for l in CM.retire_lines(up, cid, e) if not l.startswith("#")]
    w = A.CommandWorld({n: '%s{TrainerIds:["%s"]}' % (SPAWNER, up), (n[0], n[1] - 1, n[2]): "minecraft:redstone_block",
                        c: '%s{TrainerIds:["%s"]}' % (SPAWNER, cid), (c[0], c[1] - 1, c[2]): "minecraft:redstone_block"},
                       [{"id": up, "battle": False, "pos": stand(n), "who": "leader"},
                        {"id": cid, "battle": False, "pos": stand(c), "who": "old"}],
                       [{"pos": (n[0] + 6.5, n[1] + 1.0, n[2] + 0.5), "tags": set()}])
    for l in rl:
        w.run(l)
    w.players = []          # the player walks off; R17L runs again on the next re-apply
    for l in rl:
        w.run(l)
    spawner_gone = not str(w.blocks.get(c, "")).startswith(SPAWNER)
    orphans = [t for t in w.trainers if t.get("who") == "old"]
    assert not (spawner_gone and orphans), "second spawner removed, its trainer left standing: %s" % orphans


# ------------------------------------------------------------------------------------------------ the League
# Without it a new pair of one-leader seats inside each other's swap reach would arrive unseen. Each pair is a place
# where a player standing at one boss chooses the other boss's id through the floor (distance is 3-D): in a mixed
# group the player actually at that boss is refused (wrong_series) until nearer. Measured from the cycle's own lines;
# Agatha (3695, 138, 2417) and Lance (3695, 148, 2421) are 10.8 apart (dy 10, dz 4) against a reach of 17. An owner
# decision before the League's rollout, not a defect of Brock's.
KNOWN_SHARED_REACH = {("kanto_league_agatha", "kanto_league_lance")}


def test_the_one_leader_seats_inside_each_others_reach_are_the_known_ones(built_all):
    files, d = built_all
    cycle = lines(files[CYCLE])
    seats = {up: swap_anchor(cycle, up + SFX) for up in d["bosses"]}
    pairs = {(a, b) for a, b in itertools.combinations(sorted(seats), 2)
             if dist(stand(seats[a][0]), stand(seats[b][0])) <= max(seats[a][1], seats[b][1])}
    assert pairs == KNOWN_SHARED_REACH


# Without it the thirteen could be rolled out with P1 (the 3-D command model in tools/challenge_mode_audit.py) never
# having run over the template bosses: this runs it with rollout "all" in memory and wants no problem. It needs the
# snapshot's DP-v31 zip for the templates and skips without it.
def test_the_challenge_audit_passes_p1_for_all_thirteen_in_memory(monkeypatch):
    try:
        up = A.Upstream()
    except FileNotFoundError as e:
        pytest.skip("the local server snapshot is not here: %s" % e)
    d = _all()
    monkeypatch.setattr(CM, "doc", lambda: d)
    orig = A.Audit.doc
    monkeypatch.setattr(A.Audit, "doc", lambda self, name: copy.deepcopy(d) if name == "challenge_mode.json"
                        else orig(self, name))
    a = A.Audit(A.Artifacts(), up).run("PR")
    assert [p for p in a.problems if p[0].startswith(("P1", "R:summon", "P:count"))] == []


def _exec_into(monkeypatch, name, edits=(), d=None):
    path = ROOT / "tools" / ("%s.py" % name)
    src = path.read_text(encoding="utf-8")
    for old, new in edits:
        assert src.count(old) == 1, "mutation anchor not unique: %r" % old[:60]
        src = src.replace(old, new)
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    monkeypatch.setitem(sys.modules, name, mod)
    exec(compile(src, str(path), "exec"), mod.__dict__)
    if d is not None:
        mod.doc = lambda: d
    return mod


# Without it the template restore (the audit's donor-substitution replay, 2026-10-08) could agree with anything:
# the generator's template branch putting floor and under back the wrong way round must fail P1:restore for the
# template bosses, with data/challenge_mode.json untouched.
def test_the_template_restore_check_fails_a_generator_that_swaps_floor_and_under(monkeypatch):
    try:
        up = A.Upstream()
    except FileNotFoundError as e:
        pytest.skip("the local server snapshot is not here: %s" % e)
    d = _all()
    _exec_into(monkeypatch, "challenge_mode", [('return r["floor"], r["under"]', 'return r["under"], r["floor"]')], d)
    _exec_into(monkeypatch, "route_trainers")
    orig = A.Audit.doc
    monkeypatch.setattr(A.Audit, "doc", lambda self, name: copy.deepcopy(d) if name == "challenge_mode.json"
                        else orig(self, name))
    a = A.Audit(A.Artifacts(), up).run("P")
    hit = {m.split()[0] for c, m in a.problems if c == "P1:restore"}
    assert hit == {u + SFX for u in ("kanto_misty", "kanto_league_lorelei", "kanto_league_bruno",
                                     "kanto_league_agatha", "kanto_league_lance", "kanto_champion_blue")}, hit
