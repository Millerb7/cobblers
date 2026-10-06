"""tools/challenge_mode_audit.py: the independent audit of Oak's lab scene and Challenge mode.

What these tests prove: the audit's own models (vanilla's template rotation, rctmod's level-cap formula, the selector
interpreter that runs the route swap, the fill/setblock replay) give hand-computed answers on synthetic inputs; the
real build carries exactly the defects recorded below and nothing else; and the audit is INDEPENDENT of the code it
checks -- each mutation edits a GENERATOR's source (tools/challenge_mode.py, tools/compile_dialogue.py) and leaves
every data file untouched, and the audit must fail with the named check.

What they do not prove: anything at run time. Whether rctmod refuses the other mode, reproduces the cap, lets two
identities stand, or swaps a team on a TrainerId merge is RCT_PER_PLAYER_MODE.md section 7 (E1-E8), in a running
Minecraft. The real-build and mutation tests need the local server snapshot's zips and skip without them.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import challenge_mode_audit as A  # noqa: E402

# The defects the real build has today (found by this audit, 2026-10-06). Each is (check, Challenge id). When the
# builder moves a spawner, its entries leave this set and the test says so: update it, never widen it.
KNOWN = {
    # Misty's second spawner is the floor of a one-wide water channel: seagrass and water over it, a warped-plank
    # rim and glass between it and Misty. The self-placing line tests for air, so it is never set.
    ("P:headroom", "kanto_misty_challenge"),
    ("P:room", "kanto_misty_challenge"),
    # Bruno's second spawner has a minecraft:light block over it: `if block ... minecraft:air` is false, never set.
    ("P:headroom", "kanto_league_bruno_challenge"),
}


@pytest.fixture(scope="module")
def up():
    try:
        return A.Upstream()
    except FileNotFoundError as e:
        pytest.skip("the local server snapshot is not here: %s" % e)


def keyed(audit):
    out = set()
    for code, msg in audit.problems:
        ids = [w.strip(",:'\"") for w in msg.split() if w.strip(",:'\"").endswith("_challenge")]
        out.add((code, ids[0] if ids else msg[:60]))
    return out


def fresh(monkeypatch, name, edits=()):
    """Load tools/<name>.py into sys.modules with exact text edits applied; each edit must match exactly once, so a
    mutation can never silently do nothing."""
    path = ROOT / "tools" / ("%s.py" % name)
    src = path.read_text(encoding="utf-8")
    for old, new in edits:
        assert src.count(old) == 1, "the mutation's anchor is not unique in %s: %r" % (name, old[:60])
        src = src.replace(old, new)
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    monkeypatch.setitem(sys.modules, name, mod)
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


def run(up, only):
    return A.Audit(A.Artifacts(), up).run(only)


@pytest.fixture(scope="module")
def baseline(up):
    return keyed(run(up, A.CHECKS))


# ------------------------------------------------------------------------------------------------ the models
# Without it a wrong rotation would put every template spawner in the wrong place and P would check the wrong cells.
def test_rotation_follows_vanillas_pivot_rule():
    assert A.rotate((1, 0, 2), (10, 5, 10), "none") == (11, 5, 12)
    assert A.rotate((1, 0, 2), (10, 5, 10), "clockwise_90") == (8, 5, 11)
    assert A.rotate((1, 0, 2), (10, 5, 10), "clockwise_180") == (9, 5, 8)
    assert A.rotate((1, 0, 2), (10, 5, 10), "counterclockwise_90") == (12, 5, 9)


# Without it the cap comparison could agree with itself on a wrong formula (LevelUtils, RCT_PER_PLAYER_MODE.md s3).
def test_trainer_level_takes_the_max_over_requirements_and_the_trainers_own_offset():
    mobs = {"a": {}, "b": {"requiredDefeats": [["a"]]}, "c": {"requiredDefeats": [["b"]], "relativeLevelCap": -2}}
    top = {"a": 20, "b": 18, "c": 30}
    lv = {t: A.trainer_level(t, top, mobs, None, 0) for t in mobs}
    assert lv == {"a": 20, "b": 20, "c": 28}
    assert A.chain_order(mobs) == ["a", "b", "c"]
    assert A.cap_curve(["a", "b", "c"], lv, 20) == [20, 20, 28, 100]
    mobs["b"]["relativeLevelCap"] = 5
    assert A.trainer_level("b", top, mobs, None, 0) == 23


# Without it a branched chain would be compared as if it were linear.
def test_a_branched_chain_is_not_taken_for_a_line():
    assert A.chain_order({"a": {}, "b": {"requiredDefeats": [["a"]]}, "c": {"requiredDefeats": [["a"]]}}) is None


SWAP = [
    'execute as @e[type=rctmod:trainer,x=10.5,y=64,z=20.5,distance=..24,nbt={TrainerId:"t",InBattle:0b}] at @s '
    'as @p[distance=..9.0] if entity @s[tag=m] run data merge entity '
    '@e[type=rctmod:trainer,distance=..0.5,nbt={TrainerId:"t",InBattle:0b},limit=1] {TrainerId:"t_c"}',
    'execute as @e[type=rctmod:trainer,x=10.5,y=64,z=20.5,distance=..24,nbt={TrainerId:"t_c",InBattle:0b}] at @s '
    'as @p[distance=..9.0] unless entity @s[tag=m] run data merge entity '
    '@e[type=rctmod:trainer,distance=..0.5,nbt={TrainerId:"t_c",InBattle:0b},limit=1] {TrainerId:"t"}',
    'execute as @e[type=rctmod:trainer,x=10.5,y=64,z=20.5,distance=..24,nbt={TrainerId:"t_c",InBattle:0b}] at @s '
    'unless entity @a[distance=..9.0] run data merge entity @s {TrainerId:"t"}',
]


def swap(start, battle, players, lines=SWAP, seat=(10, 64, 20)):
    m = A.SeatModel(seat, [{"id": start, "battle": battle}], [{"d": d, "tags": set(t)} for d, t in players])
    for line in lines:
        m.run(line)
    return [t["id"] for t in m.trainers]


# Without it the swap check would trust an interpreter nobody had checked against hand-worked cases.
@pytest.mark.parametrize("start,battle,players,want", [
    ("t", False, [], "t"),                           # nobody near: Normal
    ("t", False, [(3, "m")], "t_c"),                 # a Challenge player near: Challenge
    ("t_c", False, [(3, "")], "t"),                  # a Normal player near: back to Normal
    ("t", False, [(1, ""), (3, "m")], "t"),          # the nearest decides
    ("t_c", False, [(1, "m"), (3, "")], "t_c"),
    ("t_c", False, [(9.5, "m")], "t"),               # just outside the reach: nobody near
    ("t", True, [(3, "m")], "t"),                    # never in a battle
    ("t_c", True, [], "t_c"),
])
def test_the_selector_model_runs_the_swap_as_vanilla_would(start, battle, players, want):
    assert swap(start, battle, players) == [want]


# Without it a swap anchored at another seat would be counted as acting here.
def test_a_selector_anchored_at_another_seat_reaches_nobody_here():
    assert swap("t", False, [(3, "m")], seat=(50, 64, 50)) == ["t"]


# Without it the gym replay could misread hollow fills, keep fills or replace filters.
def test_the_replay_reads_fill_modes_and_setblock():
    w = A.Replay(["fill 0 10 0 4 14 4 minecraft:stone_bricks hollow",
                  "fill 0 10 0 4 10 4 minecraft:oak_planks replace minecraft:stone_bricks",
                  "fill 2 11 2 2 12 2 minecraft:glass keep",
                  "setblock 1 10 1 rctmod:trainer_spawner{TrainerIds:[\"x\"]}"], level=9)
    assert w.at((2, 12, 2)) == "minecraft:glass"            # inside the hollow: air, so keep writes
    assert w.at((0, 10, 0)) == "minecraft:oak_planks"       # replace hit the floor of the shell
    assert w.at((0, 12, 0)) == "minecraft:stone_bricks"     # the wall, not replaced
    assert w.at((3, 12, 3)) == "minecraft:air"
    assert w.at((9, 9, 9)) == "minecraft:stone" and w.at((9, 10, 9)) == "minecraft:air"
    assert w.spawners() == [((1, 10, 1), ["x"])]


# ------------------------------------------------------------------------------------------------ the real build
# Without it a new defect in the lab, the series command, the bosses, the spawners or the swap would pass unseen; and
# a fixed one would stay listed as known.
def test_the_real_build_has_exactly_the_known_spawner_defects(baseline):
    assert baseline == KNOWN


# Without it the audit could quietly skip the swap for most seats and still pass.
def test_every_seat_with_a_challenge_team_was_swapped(up):
    a = run(up, "R")
    n = [x for x in a.notes if x.startswith("R: the swap was run for")]
    assert n and int(n[0].split()[6]) >= 51


# ------------------------------------------------------------------------------------------------ independence
# Each mutation edits the GENERATOR and leaves data/ alone. The audit must fail with the named check, and the failure
# must be new (not one of the KNOWN defects).
MUTATIONS = {
    # the once-lock dropped: an enum field at its initial value compiles to "always true"
    "lock_dropped": ("compile_dialogue", [(
        'if fdef.get("type") == "enum" and v == fdef.get("initial"):\n'
        '                return "(%s == %s || %s == 0)" % (f, lit(v), f)',
        'if fdef.get("type") == "enum" and v == fdef.get("initial"):\n'
        '                return "1"')], "M", "M:guarded"),
    # the gym1_cleared refusal dropped: a flag condition compiles to "never held"
    "gym1_dropped": ("compile_dialogue", [(
        "            return \"q.player.has_tag('%s')\" % tag\n        if k == \"player_tag\":",
        "            return \"0\"\n        if k == \"player_tag\":")], "M", "M:gym1"),
    # the actors and hint no longer wait for the pick
    "starter_ignored": ("compile_dialogue", [(
        "return \"q.player.has_tag('%s')\" % STARTER_TAG", "return \"0\"")], "S", "S:actor_after_pick"),
    # one Challenge ace five levels over its Normal counterpart
    "ace_plus_5": ("challenge_mode", [(
        '        out["data/rctmod/trainers/%s.json" % cid] = team\n',
        '        if cid == "kanto_misty_challenge":\n'
        '            top = max(m["level"] for m in team["team"])\n'
        '            team["team"] = [dict(m, level=m["level"] + 5) if m["level"] == top else m for m in team["team"]]\n'
        '        out["data/rctmod/trainers/%s.json" % cid] = team\n')], "B", "B:cap"),
    # the chain dropped: every Challenge boss open from the start
    "chain_dropped": ("challenge_mode", [(
        'req = [[r + sfx] for r in e.get("upstream_required") or []]', "req = []")], "B", "B:chain"),
    # the Challenge leader takes the Normal leader's identity (rctmod's fallback is the name)
    "identity_shared": ("challenge_mode", [(
        'team["identity"] = identity', 'team["identity"] = rct["name"]["literal"]')], "B", "B:identity"),
    # a Challenge boss that drops loot
    "loot_filled": ("challenge_mode", [(
        'out["data/rctmod/loot_table/trainers/single/%s.json" % cid] = {"pools": []}',
        'out["data/rctmod/loot_table/trainers/single/%s.json" % cid] = {"pools": [{"rolls": 1, "entries": '
        '[{"type": "minecraft:item", "name": "minecraft:diamond"}]}]}')], "B", "B:loot"),
    # the second spawner one block up: on top of the floor, not in it
    "spawner_raised": ("challenge_mode", [(
        '        x, y, z = e["spawner"]["at"]\n        out[',
        '        x, y, z = e["spawner"]["at"]\n        y += 1\n        out[')], "P", "P:floor"),
    # the self-placing line tests the wrong cells
    "cycle_off_by_one": ("challenge_mode", [(
        "x, y + 1, z, x, y + 2, z, NS, cid", "x, y + 2, z, x, y + 3, z, NS, cid")], "P", "P:cycle"),
    # the swap acts during a battle
    "swap_in_battle": ("challenge_mode", [
        ("distance=..24,nbt={TrainerId:\"%s\",InBattle:0b}]'", "distance=..24,nbt={TrainerId:\"%s\"}]'"),
        ("distance=..0.5,nbt={TrainerId:\"%s\",InBattle:0b},limit=1]", "distance=..0.5,nbt={TrainerId:\"%s\"},limit=1]"),
    ], "R", "R:swap"),
    # the swap never returns a seat to the Normal id when the player walks away
    "swap_never_returns": ("challenge_mode", [(
        '        "execute as %s at @s unless entity @a[distance=..%s] run data merge entity @s {TrainerId:\\"%s\\"}"\n'
        '        % (sel(cid), near, tid),\n', "")], "R", "R:swap"),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_mutated_generator_fails_the_audit(name, up, monkeypatch, baseline):
    module, edits, only, code = MUTATIONS[name]
    fresh(monkeypatch, module, edits)
    # the importers pick the mutated module up from sys.modules
    if module == "challenge_mode":
        fresh(monkeypatch, "route_trainers")
    if module == "compile_dialogue":
        fresh(monkeypatch, "scenes_pack")
    got = keyed(run(up, only))
    new = {k for k in got - baseline}
    assert code in {c for c, _ in new}, "mutation %s: the audit did not fail %s (new problems: %s)" % (name, code, new)


# Without it a mutation test could pass because the generator raised instead of the audit catching it.
def test_the_unmutated_generators_give_the_baseline(up, monkeypatch, baseline):
    fresh(monkeypatch, "challenge_mode")
    fresh(monkeypatch, "route_trainers")
    fresh(monkeypatch, "compile_dialogue")
    fresh(monkeypatch, "scenes_pack")
    assert keyed(run(up, A.CHECKS)) == baseline
