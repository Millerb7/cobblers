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
# 2026-10-06: Misty's and Bruno's Challenge spawners moved to air cells (1605, 132, 2873), (3695, 127, 2437).
# 2026-10-06, the one-leader rule (P1) on Brock, the first boss in single_leader.rollout (commit c8b5090):
#   P1:retire        FIXED in ab0de08 (the retire now keeps the Normal-id trainer nearest the one spawner and kills
#                    the rest): the cycle renamed the old Challenge trainer to kanto_brock before R17L's retire ran
#   P1:retire_kills  the retire's kill guard is "no player within 17 of the RETIRED cell", but the swap follows a
#                    player within 17 of the ONE spawner two blocks east. ab0de08 put every kill under the second-
#                    spawner block test, so a RE-RUN no longer kills; the FIRST run still kills the one leader while a
#                    Challenge player stands 15.5 east of him (once the cycle has swapped him to the Challenge id)
KNOWN = {("P1:retire_kills", "kanto_brock_challenge")}


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


# ------------------------------------------------------------------------------------------------ the 3-D model
SPW = 'rctmod:trainer_spawner{TrainerIds:["%s"]}'


def cworld(start="t", battle=False, players=(), inbattle=True, extra=()):
    """A spawner at (0, 64, 0) holding `start`, its trainer standing on it, players at (x, 65, 0.5)."""
    return A.CommandWorld({(0, 64, 0): SPW % start, (0, 63, 0): "minecraft:redstone_block"},
                          [{"id": start, "battle": battle, "pos": (0.5, 65.0, 0.5)}] + list(extra),
                          [{"pos": (0.5 + x, 65.0, 0.5), "tags": set(t)} for x, t in players], inbattle=inbattle)


# Without it P1 would trust a world model whose block, selector and nbt rules nobody had worked by hand.
def test_the_command_world_follows_vanillas_execute_rules():
    w = cworld(players=[(3, "m"), (6, "")])
    w.run('execute positioned 0.5 64 0.5 as @p[distance=..10] if entity @s[tag=m] '
          'run data merge block 0 64 0 {TrainerIds:["t_c"]}')
    assert w.blocks[(0, 64, 0)] == SPW % "t_c"                  # the nearest (3, tagged) decided
    w.run('execute unless block 0 64 0 rctmod:trainer_spawner{TrainerIds:["t_c"]} run setblock 0 64 0 minecraft:stone')
    assert w.blocks[(0, 64, 0)] == SPW % "t_c"                  # the predicate matched, so unless stopped it
    w.run('execute if block 0 63 0 minecraft:redstone_block run data merge block 0 63 0 {TrainerIds:["x"]}')
    assert w.blocks[(0, 63, 0)] == "minecraft:redstone_block"   # no block entity: a merge changes nothing
    w.run('execute positioned 0.5 64 0.5 unless entity @a[distance=..2] run data merge entity '
          '@e[type=rctmod:trainer,x=0.5,y=64,z=0.5,distance=..24,nbt={TrainerId:"t",InBattle:0b},limit=1] {TrainerId:"t_c"}')
    assert [t["id"] for t in w.trainers] == ["t_c"]
    w.run('execute positioned 0.5 64 0.5 if entity @a[distance=..2] run kill @e[type=rctmod:trainer,distance=..24]')
    assert len(w.trainers) == 1                                 # nobody within 2: no kill
    w.run('execute positioned 10.5 64 0.5 run kill @e[type=rctmod:trainer,distance=..9]')
    assert len(w.trainers) == 1                                 # the trainer is 10.05 away: out of 9
    w.run('execute positioned 10.5 64 0.5 run kill @e[type=rctmod:trainer,distance=..10.1]')
    assert w.trainers == []


# Without it a merge vanilla would refuse at load could be modelled as working.
def test_the_command_world_refuses_a_multi_target_merge_as_vanilla_does():
    with pytest.raises(ValueError):
        cworld().run('execute positioned 0.5 64 0.5 run data merge entity @e[type=rctmod:trainer,distance=..5] {TrainerId:"x"}')


# Without it the InBattle report would rest on a model that cannot tell a saved byte from an absent tag.
def test_without_a_saved_inbattle_no_inbattle_predicate_matches():
    sel = '@e[type=rctmod:trainer,x=0.5,y=64,z=0.5,distance=..5,nbt={TrainerId:"t",InBattle:%s}]'
    line = 'execute positioned 0.5 64 0.5 if entity %s run setblock 9 9 9 minecraft:stone'
    for inb, battle, form, hit in [(True, True, "1b", True), (True, False, "0b", True), (True, False, "1b", False),
                                   (False, True, "1b", False), (False, False, "0b", False)]:
        w = cworld(battle=battle, inbattle=inb)
        w.run(line % (sel % form))
        assert ((9, 9, 9) in w.blocks) == hit, (inb, battle, form)


# Without it the keep-the-nearest retire could be judged by a model that sorts from the wrong point or ignores tags.
def test_sort_nearest_is_measured_from_the_position_reached_and_tag_filters_apply():
    far = {"id": "t", "battle": False, "pos": (6.5, 65.0, 0.5)}           # 6 east of the spawner
    w = cworld(extra=[far])                                                # the spawner's own trainer at 0.5
    w.run('execute positioned 6.5 64 0.5 as @e[type=rctmod:trainer,distance=..24,nbt={TrainerId:"t"},'
          'sort=nearest,limit=1] run tag @s add keep')
    assert [sorted(t.get("tags", ())) for t in w.trainers] == [[], ["keep"]]   # nearest to x6.5 is the far one
    w.run('execute positioned 0.5 64 0.5 run kill @e[type=rctmod:trainer,distance=..24,tag=!keep]')
    assert [t["pos"][0] for t in w.trainers] == [6.5]
    w.run("tag @e[type=rctmod:trainer,tag=keep] remove keep")             # a bare line: no position needed
    assert w.trainers[0]["tags"] == set()
    w2 = cworld(extra=[dict(far)])
    w2.run('execute positioned 6.5 64 0.5 as @e[type=rctmod:trainer,distance=..24,sort=furthest,limit=1] '
           'run tag @s add keep')
    assert [sorted(t.get("tags", ())) for t in w2.trainers] == [["keep"], []]
    with pytest.raises(ValueError):
        cworld().run('execute positioned 0.5 64 0.5 run kill @e[type=rctmod:trainer,sort=random,limit=1]')


# Without it a selector anchored by x/y/z could be measured from the execute position instead.
def test_a_selector_origin_overrides_the_execute_position():
    w = cworld(players=[(3, "m")])
    w.run('execute positioned 100 64 100 as @p[x=0.5,y=65,z=0.5,distance=..4] run setblock 1 1 1 minecraft:stone')
    assert (1, 1, 1) in w.blocks
    w2 = cworld(players=[(3, "m")])
    w2.run('execute positioned 100 64 100 as @p[distance=..4] run setblock 1 1 1 minecraft:stone')
    assert (1, 1, 1) not in w2.blocks


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
    # --- one leader (P1). Each edits tools/challenge_mode.py and leaves data/challenge_mode.json alone.
    # the retire one block east of where the second spawner stood
    "retire_off_by_one": ("challenge_mode", [(
        "    floor, under = restore_blocks(up, entry)\n",
        "    floor, under = restore_blocks(up, entry)\n    x += 1\n")], "P", "P1:retire_at"),
    # the restore puts back the air over the floor instead of the floor
    "restore_wrong_floor": ("challenge_mode", [(
        "return e.at(x, y, z), e.at(x, y - 1, z)", "return e.at(x, y + 1, z), e.at(x, y - 1, z)")], "P", "P1:restore"),
    # the battle guard dropped from the swap: the spawner changes under a battle
    "single_swap_blind_to_battle": ("challenge_mode", [(
        '    head = "execute if loaded', '    busy = ""\n    head = "execute if loaded')], "P", "P1:swap"),
    # the retire kills the old trainer even in a battle
    "retire_kills_in_battle": ("challenge_mode", [(
        "sel = 'type=rctmod:trainer,distance=..%d,nbt={TrainerId:\"%s\",InBattle:0b}'",
        "sel = 'type=rctmod:trainer,distance=..%d,nbt={TrainerId:\"%s\"}'")], "P", "P1:retire_battle"),
    # the Challenge-id kill no longer waits for the second spawner: a re-run kills again
    "retire_kill_without_has": ("challenge_mode", [(
        '"execute %s %s run kill @e[%s]" % (has, near, sel % (SEAT_BOX, cid))',
        '"execute %s run kill @e[%s]" % (near, sel % (SEAT_BOX, cid))')], "P", "P1:rerun_kills"),
    # the Normal-id kill spares nobody: the one leader goes with the renamed old trainer
    "retire_keeps_nobody": ("challenge_mode", [(
        ',tag=!cobblers_keep_leader]" % (has, near', ']" % (has, near')], "P", "P1:retire"),
    # the keep measured from the OLD seat: the renamed old trainer is kept and the one leader killed
    "retire_keeps_the_old_one": ("challenge_mode", [(
        "% (has, near, nx, ny, nz, sel % (SEAT_BOX, up))", "% (has, near, x, y, z, sel % (SEAT_BOX, up))")],
        "P", "P1:retire"),
    # Brock's second spawner put back while Brock is still in the rollout
    "second_spawner_back": ("challenge_mode", [(
        "        if up in single:\n", "        if up in single and False:\n")], "P", "P1:count"),
}


# Without it the narrow R:summon exception could be widened into one that excuses any kill in a retire function.
def test_the_retire_kill_is_excused_only_in_its_exact_shape(up, monkeypatch):
    fresh(monkeypatch, "challenge_mode", [(
        '"execute %s %s run kill @e[%s]" % (has, near, sel % (SEAT_BOX, cid))',
        '"execute %s run kill @e[%s]" % (near, sel % (SEAT_BOX, cid))')])
    fresh(monkeypatch, "route_trainers")
    assert "R:summon" in {c for c, _ in keyed(run(up, "R"))}


# Without it the exception could excuse a kill the unmutated build does not even make.
def test_the_unmutated_retire_kill_is_excused(baseline):
    assert "R:summon" not in {c for c, _ in baseline}


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
