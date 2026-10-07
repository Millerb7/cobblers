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
    killed, reachable = [], []
    for up, e in sorted(d["bosses"].items()):
        w = lag_world(up, e, cycle, second_spawner=False)
        rl = [l for l in mod.retire_lines(up, up + SFX, e) if not l.startswith("#")]
        for l in rl:
            w.run(l)
        if not w.trainers:
            killed.append(up)
        # which leaders the Challenge-id kill can reach at all: its own anchor and radius, read from its text
        n, _r = swap_anchor(cycle, up + SFX)
        for l in rl:
            m = re.search(r'positioned (-?\d+)\.5 (-?\d+) (-?\d+)\.5 .*run kill @e\[type=rctmod:trainer,distance=\.\.'
                          r'(\d+),nbt=\{TrainerId:"%s",' % re.escape(up + SFX), l)
            if m and dist(tuple(float(v) + (0.5 if i != 1 else 0) for i, v in enumerate(m.groups()[:3])),
                          stand(n)) <= float(m.group(4)):
                reachable.append(up)
    # Gated, nobody dies. Ungated, every leader the kill can reach dies: all but a boss whose one spawner moved out of
    # the kill's radius (Lance, data/challenge_mode.json single_leader.move, 30.6 from his retired cell: 2026-10-09).
    # Every boss that did not move must be among them, so the mutation still bites wherever `has` is the only guard.
    unmoved = {up for up, e in d["bosses"].items() if not (e.get("single_leader") or {}).get("move")}
    assert unmoved <= set(reachable)
    assert (killed == []) if gated else (killed == sorted(reachable)), (killed, reachable)


# ------------------------------------------------------------------------------------------------ open defects
# Recorded as strict xfails: each flips to a pass, and fails the run, the day the generator is fixed, so the
# record cannot go stale. Defect text and path:line are in the reason.

# The FIRST run has the same lag window, and there `has` holds: the one leader, still on the Challenge id, is killed
# out of battle. Low impact if rctmod's spawner respawns him (not verified); R17L run with nobody online cannot hit it.
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
# group the player actually at that boss is refused (wrong_series) until nearer. Measured from the cycle's own lines.
# Agatha (3695, 138, 2417) and Lance's template spawner (3695, 148, 2421) were 10.8 apart against a reach of 17; the
# owner moved Lance's one spawner to (3676, 148, 2445) on 2026-10-09 (single_leader.move), 35.3 from Agatha, so no
# pair of seats is within reach of the other. This is the coarse seat-to-seat rule; the floor-cell rule, which still
# finds Agatha/Bruno and Bruno/Lorelei, is the next test.
KNOWN_SHARED_REACH = set()


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


# ------------------------------------------------------------------------------------------------ the League floors
LEAGUE = ("kanto_league_lorelei", "kanto_league_bruno", "kanto_league_agatha", "kanto_league_lance",
          "kanto_champion_blue")
# The owner's rule (2026-10-09, data/challenge_mode.json bosses.kanto_league_lance.single_leader.move.rule), judged
# here on the audit's own placed template (tools/challenge_mode_audit.py TemplateWorld and passable, not
# tools/league_separation.py) and with no walk: a cell counts as one boss's when it is a floor (solid, two passable
# cells over it) within 4 of that boss's seat height. Shared cells of these two pairs are open owner decisions
# (2026-10-09: "AGATHA AND LANCE ... move one spawner"; the other pairs were not named). Measured 2026-10-09:
# Agatha/Bruno 451 cells, Bruno/Lorelei 184 with this model (league_separation, which walks the floor, says 450 and
# 208); every pair with Lance at his moved seat 0.
KNOWN_SHARED_FLOORS = {("kanto_league_agatha", "kanto_league_bruno"), ("kanto_league_bruno", "kanto_league_lorelei")}


def _league_world(up):
    pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    p = [r for r in pl["placements"] if isinstance(r, dict) and r.get("id") == "league_building"][0]
    level = [a.get("level") for a in pl["settlements"][p["settlement"]]["plan"]["anchors"] if a.get("id") == p["lot"]][0]
    size, cells = up.template("kanto_league")
    pos = p["position"]
    return A.TemplateWorld(size, cells, (pos["x"], pos["y"], pos["z"]), p["rotation"], level)


def _feet_distance(cell, seat):
    """Least distance from the swap's point over `seat` to a player's feet over `cell`: x and z across the cell, y from
    cell + 0.5 (a slab) to cell + 2.25 (a jump), as the rule's record defines it."""
    px, py, pz = seat[0] + 0.5, seat[1], seat[2] + 0.5
    x, y, z = cell
    dx, dz = max(x - px, 0, px - x - 1), max(z - pz, 0, pz - z - 1)
    dy = max(y + 0.5 - py, 0, py - y - 2.25)
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def _shared_floor_cells(w, a, sa, b, sb, reach):
    out = 0
    r = int(reach) + 1
    for x in range(sa[0] - r, sa[0] + r + 1):
        for z in range(sa[2] - r, sa[2] + r + 1):
            for y in range(sa[1] - 4, sa[1] + 5):
                c = (x, y, z)
                if (_feet_distance(c, sa) <= reach and _feet_distance(c, sb) <= reach and A.solid_floor(w.at(c))
                        and A.passable(w.at((x, y + 1, z))) and A.passable(w.at((x, y + 2, z)))):
                    out += 1
    return out


# Without it a League seat whose floor lies inside another boss's swap reach would arrive unseen: a player standing at
# one boss would choose the other's id through the ceiling (distance is 3-D), and in a mixed group the player at that
# boss is refused (wrong_series). The seats are read from the cycle's own lines, so Lance is judged where the move puts
# him. Not covered: a player on a THIRD storey (measured 2026-10-09: 702 floor cells of Agatha's storey are within
# Lance's new reach, against 754 at his template seat), stairs between storeys, and whether rctmod's sight passes floors.
def test_the_league_floors_inside_two_swap_reaches_are_the_owners_open_pairs(built_all):
    try:
        up = A.Upstream()
    except FileNotFoundError as e:
        pytest.skip("the local server snapshot is not here: %s" % e)
    files, _d = built_all
    cycle = lines(files[CYCLE])
    seats = {b: swap_anchor(cycle, b + SFX) for b in LEAGUE}
    w = _league_world(up)
    counts = {}
    for a, b in itertools.combinations(sorted(LEAGUE), 2):
        (sa, ra), (sb, rb) = seats[a], seats[b]
        reach = max(ra, rb)
        counts[(a, b)] = _shared_floor_cells(w, a, sa, b, sb, reach) + _shared_floor_cells(w, b, sb, a, sa, reach)
    assert {k for k, v in counts.items() if v} == KNOWN_SHARED_FLOORS, counts
    assert counts[("kanto_league_agatha", "kanto_league_lance")] == 0, counts


# Without it the floor check above could pass on a model that finds nothing: at Lance's TEMPLATE seat the same count
# must find Agatha and Lance sharing floor cells (the defect the owner moved him for: 1261 with this model, 1181 by
# league_separation).
def test_the_floor_check_finds_agatha_and_lance_at_lances_template_seat():
    try:
        up = A.Upstream()
    except FileNotFoundError as e:
        pytest.skip("the local server snapshot is not here: %s" % e)
    w = _league_world(up)
    seats = {i: c for c, ids in w.spawners() for i in ids}
    reach = CM.reach()
    a, l = seats["kanto_league_agatha"], seats["kanto_league_lance"]
    assert l == tuple(DATA["bosses"]["kanto_league_lance"]["single_leader"]["move"]["from"])
    assert _shared_floor_cells(w, "a", a, "l", l, reach) + _shared_floor_cells(w, "l", l, "a", a, reach) > 0


# ------------------------------------------------------------------------------------------------ Lance's move
def _audit_lance(monkeypatch, edits=()):
    """The P audit with Lance alone in the rollout (in memory), over tools/challenge_mode.py with `edits` applied."""
    try:
        up = A.Upstream()
    except FileNotFoundError as e:
        pytest.skip("the local server snapshot is not here: %s" % e)
    d = copy.deepcopy(DATA)
    d["single_leader"]["rollout"] = ["kanto_league_lance"]
    _exec_into(monkeypatch, "challenge_mode", edits, d)
    _exec_into(monkeypatch, "route_trainers")
    orig = A.Audit.doc
    monkeypatch.setattr(A.Audit, "doc", lambda self, name: copy.deepcopy(d) if name == "challenge_mode.json"
                        else orig(self, name))
    return A.Audit(A.Artifacts(), up).run("P")


MOVE_MUTATIONS = {
    # the old cell left as air: a hole in Lance's floor where the spawner stood
    "move_restores_air": ([('ox, oy, oz, mv["from_restore"]),', 'ox, oy, oz, "minecraft:air"),')], "P1:move_restore"),
    # the new spawner one block east of the cell the swap follows
    "move_spawner_off_by_one": ([('    nx, ny, nz = mv["to"]\n    r = ', '    nx, ny, nz = mv["to"]\n    nx += 1\n    r = ')],
                                "P1:move_at"),
    # the battle guard dropped: the spawner moves while Lance is in a battle by it
    "move_in_battle": ([('nx, ny, nz, r, busy))', 'nx, ny, nz, r, ""))')], "P1:move_battle"),
    # the player guard reduced to nothing: the spawner moves with a Challenge player in battle range of the leader
    "move_ignores_players": ([('    r = "%g" % reach()\n    old = ', '    r = "0"\n    old = ')], "P1:retire_renames"),
    # R17L runs the move before the retire: the retire's kills no longer clear the old cell first
    "move_before_retire": ([(
        '        out.append("%s:trainers/challenge/retire_%s" % (NS, challenge_id(up)))\n'
        '        if move_of(up, d["bosses"][up]):\n'
        '            out.append("%s:trainers/challenge/move_%s" % (NS, up))\n',
        '        if move_of(up, d["bosses"][up]):\n'
        '            out.append("%s:trainers/challenge/move_%s" % (NS, up))\n'
        '        out.append("%s:trainers/challenge/retire_%s" % (NS, challenge_id(up)))\n')], "P1:wired"),
}


# Without it the new P1:move* checks could pass any move function: each mutation edits tools/challenge_mode.py (never
# data/) and must add its named failure to the unmutated generator's.
@pytest.mark.parametrize("name", sorted(MOVE_MUTATIONS))
def test_a_mutated_move_fails_the_audit(name, monkeypatch):
    base = {c for c, _m in _audit_lance(monkeypatch).problems}
    edits, code = MOVE_MUTATIONS[name]
    got = {c for c, _m in _audit_lance(monkeypatch, edits).problems}
    assert code in got - base, "mutation %s: the audit did not newly fail %s (got %s, base %s)" % (name, code, got, base)


# Without it P1:move_orphan could be a check that always fails: a move that also removes an idle trainer of either id
# by the old cell, under its own guards, before it moves the spawner, leaves Lance with no P1 problem at all. (The
# shape of a fix, written here to test the check; not a change to tools/challenge_mode.py.)
ORPHAN_FIX = [(
    '        "execute %s %s run setblock %d %d %d minecraft:redstone_block" % (old, guard, nx, ny - 1, nz),\n',
    '        "execute %s %s run kill @e[type=rctmod:trainer,x=%d.5,y=%d,z=%d.5,distance=..%d,nbt={TrainerId:\\"%s\\",'
    'InBattle:0b}]" % (old, guard, ox, oy, oz, SEAT_BOX, up),\n'
    '        "execute %s %s run kill @e[type=rctmod:trainer,x=%d.5,y=%d,z=%d.5,distance=..%d,nbt={TrainerId:\\"%s\\",'
    'InBattle:0b}]" % (old, guard, ox, oy, oz, SEAT_BOX, cid),\n'
    '        "execute %s %s run setblock %d %d %d minecraft:redstone_block" % (old, guard, nx, ny - 1, nz),\n')]


def test_the_orphan_check_passes_a_move_that_clears_the_old_cell(monkeypatch):
    a = _audit_lance(monkeypatch, ORPHAN_FIX)
    assert [p for p in a.problems if p[0].startswith("P1")] == []
