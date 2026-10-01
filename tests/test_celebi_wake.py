"""The wake of the sleeping Celebi: the three faults that made it uncatchable, and the keeper that undid it.

`docs/mechanics/CELEBI_WAKE.md`, `data/sapling_celebi.json`, `data/legendaries.json` (`celebi_wake`),
`tools/sapling_celebi.py`, `tools/legendaries.py`.

Three faults were recorded on 2026-09-29 (`docs/NIGHT_REVIEW.md`) and each one alone made the encounter
impossible:

  the level     Celebi was authored at 70. `data/level_cap.json` refuses a catch STRICTLY above the thrower's RCT
                level cap, a Master Ball included, so a legendary above the cap of its own gate cannot be caught at
                all. The expectation here is NOT read from either file under test: the cap bound after eight badges
                is recomputed from `data/trainers.json` (the authored ladder: the gym ace levels and the Elite
                Four's own teams), which is where the caps actually come from.
  `uncatchable` it was a spawn property, stored in the Pokemon's own data, and nothing verified clears it on a
                spawned entity, so it would have survived the wake.
  the keeper    `celebi/keep` teleports the Celebi back onto its branch every 40 ticks. Right while it sleeps,
                fatal the moment it wakes: it would pin a woken Celebi through its own battle. This is the one that
                regresses silently, so it is tested from several directions: that `keep` is unreachable except
                behind the awake guard, that the guard comes first, that the wake sets the very score the guard
                reads, and that `dress` (and only `dress`) clears it again.

Nothing here runs a server. What it cannot show is in `docs/mechanics/CELEBI_WAKE.md` section 7: that a thrown
ball bounces off the shell, that the `SelectedItem` selector matches, and that a woken Celebi can be battled.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import legendaries as L  # noqa: E402
import sapling_celebi as SC  # noqa: E402

SAPLING = SC.load()
CELEBI = SC.files(SAPLING)
LEG = L.load()
REC = next(r for r in LEG["encounters"] if r["id"] == "celebi_wake")
OPEN = L._celebi_wake(REC, LEG, LEG["namespace"])["legendary/celebi_wake/open"]
TRAINERS = json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))


def fn(name):
    return CELEBI["data/cobblers/function/%s.mcfunction" % name].splitlines()


def body(name):
    """the commands, without the comments the design is written in"""
    return [l for l in fn(name) if l.strip() and not l.lstrip("$").startswith("#")]


def cap_bound_after_eight_badges():
    """The highest level RCT's cap can reach once gym 8 is cleared, from the authored ladder alone.

    `max(initialLevelCap, min over the next trainers of their team's highest level + relativeLevelCap)`
    (LevelUtils at rctmod v0.19.0-beta, docs/research/notes/level-cap-catch-block.md). After eight badges the
    next set is the Elite Four, so the cap is at most the weakest of their teams. A MINIMUM over the set, so
    this is an upper bound and the real cap can only be lower.
    """
    tops = [max(m["level"] for m in t["team"]) for t in TRAINERS["trainers"] if t.get("class") == "elite_four"]
    assert len(tops) == 4, tops
    return min(tops)


# Without it the Celebi is authored above the cap of its own gate and every ball breaks free, a Master Ball
# included: the encounter is a wall and nothing in the game says why. This is the level-70 fault.
def test_celebi_is_at_or_below_the_cap_its_gate_can_reach():
    bound = cap_bound_after_eight_badges()
    assert REC["gate"]["flags"] == ["gym8_cleared"], "the bound above is computed for this gate only"
    assert SAPLING["level"] <= bound, "level %s is above the after-8-badges bound %s" % (SAPLING["level"], bound)
    assert SAPLING["level"] <= REC["cap_at_gate"], (SAPLING["level"], REC["cap_at_gate"])
    assert REC["cap_at_gate"] <= bound, "cap_at_gate %s claims more than the ladder allows" % REC["cap_at_gate"]
    # and it is still a late-game legendary, not a route Pokemon
    assert SAPLING["level"] >= max(TRAINERS["generation_contract"]["gym_ace_levels"])


# Without it the two files disagree and the spawn command (which reads data/sapling_celebi.json) puts a Celebi in
# the world at a level the legendary record never audited.
def test_both_files_carry_the_same_level_and_the_spawn_uses_it():
    assert SAPLING["level"] == REC["level"]
    cmd = [v for k, v in SC.placement_steps(SAPLING) if k == "cmd" and "spawnpokemonat" in v]
    assert len(cmd) == 1 and "level=%d " % SAPLING["level"] in cmd[0] + " ", cmd


# Without it the Celebi is spawned uncatchable. That is stored in the Pokemon's own data (EXP-023) and no verified
# command clears it on a spawned entity, so the ball is refused for ever and the wake changes nothing.
def test_uncatchable_is_off_the_spawn_and_the_generator_refuses_to_put_it_back(tmp_path):
    assert "uncatchable" not in SAPLING["spawn_properties"]
    for _k, v in SC.placement_steps(SAPLING):
        assert "uncatchable" not in str(v)
    tampered = json.loads((ROOT / "data" / "sapling_celebi.json").read_text(encoding="utf-8"))
    tampered["spawn_properties"] = ["uncatchable", "no_ai"]
    p = tmp_path / "tampered.json"
    p.write_text(json.dumps(tampered), encoding="utf-8")
    try:
        SC.load(p)
    except SystemExit as e:
        assert "uncatchable" in str(e)
    else:
        raise AssertionError("the generator built a Celebi that could never be caught")


# Without it the keeper teleports the woken Celebi back onto its branch every 40 ticks, through the battle and the
# catch the wake exists to give. THE FAULT: keep must be unreachable while it is awake.
def test_the_keeper_stands_down_when_it_is_awake():
    near = body("celebi/near")
    guard = "execute if %s run return 0" % SC.awake_if(1)
    assert guard in near, near
    assert near.index(guard) == 0, "the guard must come before anything else near does: %s" % near
    assert "function cobblers:celebi/keep" in near
    # and keep is reachable from nowhere else
    callers = [n for n, t in CELEBI.items() if "cobblers:celebi/keep" in t.replace("cobblers:celebi/keeper", "")]
    assert callers == ["data/cobblers/function/celebi/near.mcfunction"], callers
    assert "cobblers:celebi/near" in "\n".join(fn("celebi/keeper"))
    assert "cobblers:celebi/keep\n" not in "\n".join(fn("celebi/keeper")) + "\n"


# Without it the keeper's guard reads a score nothing ever sets, so it never stands down and the fault above is
# back with the test still green. The wake and the guard must name the same holder and objective.
def test_the_wake_sets_the_score_the_keeper_stands_down_on():
    assert SC.awake_set(1) in OPEN, OPEN
    # in the same function that takes the shell off, and after the gate refuses
    gate = [i for i, l in enumerate(OPEN) if "advancements={cobblers:flag/gym8_cleared=true}" in l and "return 0" in l]
    assert gate and gate[0] < OPEN.index(SC.awake_set(1)), OPEN
    fills = [l for l in OPEN if l.startswith("fill ")]
    assert len(fills) == 1 and fills[0].endswith("minecraft:air replace minecraft:barrier"), fills
    x0, y0, z0, x1, y1, z1 = SC.shell_box(SAPLING)
    assert fills[0].startswith("fill %d %d %d %d %d %d " % (x0, y0, z0, x1, y1, z1)), fills[0]
    assert SC.awake_set(1) != SC.awake_set(0)


# Without it a woken Celebi is put back to sleep by a restart (load resetting the score) or the flag outlives the
# entity it describes (dress not resetting it), and a freshly re-applied dormant Celebi is never kept.
def test_only_dress_clears_the_awake_flag():
    clear = SC.awake_set(0)
    where = sorted(n.split("/")[-1] for n, text in CELEBI.items() if clear in text)
    assert where == ["dress.mcfunction"], where
    assert clear not in "\n".join(fn("celebi/load")), "a restart must not put a woken Celebi back to sleep"
    assert "data merge entity @s {" in "\n".join(fn("celebi/dress")), "dress must still be the dormant dressing"


# Without it a re-application walls a woken Celebi back in, or (the other way round) leaves the dormant Celebi it
# just summoned with no shell at all, where a sword kills it in three hits (EXP-023).
def test_the_shell_skips_only_a_woken_celebi_that_is_still_there():
    shell = body("celebi/shell")
    guard = shell[0]
    assert guard.startswith("execute if %s " % SC.awake_if(1)), shell
    assert "if entity @e[tag=%s]" % SC.TAG in guard, guard
    assert guard.endswith("run return 0")
    assert len([l for l in shell if l.startswith("fill ")]) == 2, shell


# Without it the trigger loses its gate (anyone wakes it), its item (it wakes on approach) or its radius (it wakes
# from the road), and none of that would show up anywhere else.
def test_the_wake_trigger_carries_the_gate_the_item_and_the_radius():
    w = SAPLING["wake"]
    line = [l for l in body("celebi/wake_check") if l.startswith("execute ")]
    assert len(line) == 1, line
    line = line[0]
    assert "distance=..%d" % int(w["radius"]) in line
    assert 'nbt={SelectedItem:{id:"%s"}}' % w["item"] in line
    for f in w["gate_flags"]:
        assert "cobblers:flag/%s=true" % f in line
    assert "run function cobblers:celebi/wake" in line
    # the advancement trigger EXP-023 proposed is unsound here and must not come back (it burns, and the shell
    # seals every face of the branch block)
    assert not [k for k in CELEBI if k.endswith(".json") and "advancement" in k], sorted(CELEBI)
    assert "item_used_on_block" not in "\n".join(CELEBI.values())
    # the gate is enforced by open itself, not only by the caller
    assert any("advancements={cobblers:flag/%s=true}" % w["gate_flags"][0] in l and "return 0" in l for l in OPEN)


# Without it the wake calls a function no installed pack holds and the server logs an unknown function, or the
# rctmod line is parsed at server start before rctmod's command exists (EXP-046) and the advisory silently never
# fires.
def test_every_function_the_pack_calls_exists_here_or_in_the_legendaries_pack():
    have = {k[len("data/cobblers/function/"):-len(".mcfunction")]
            for k in CELEBI if k.endswith(".mcfunction")}
    called = set()
    for text in CELEBI.values():
        called |= set(re.findall(r"function cobblers:([a-z0-9_/]+)", text))
    outside = called - have
    assert outside == {"legendary/celebi_wake/open"}, sorted(outside)
    assert SC.WAKE_FN == "cobblers:legendary/celebi_wake/open"
    assert OPEN, "the legendaries generator no longer emits the function the Celebi pack calls"
    rct = [l for l in body("celebi/cap_advice") if "rctmod" in l]
    assert len(rct) == 1 and rct[0].startswith("$"), rct


# Without it one of the two packs is not installed, or is installed server-wide instead of into the world, and the
# cross-pack call above cannot resolve.
def test_both_packs_travel_together():
    import reapply
    for pack in ("cobblers_celebi", "cobblers_legendaries"):
        assert pack in reapply.SERVER_PACKS, pack
        assert pack in reapply.WORLD_LOCAL, pack


# Without it a line of the pack is refused or silently dropped by the server (an over-long command, an unloaded
# write); the new wake functions write blocks through open, which the waking player holds loaded.
def test_the_server_would_accept_every_new_function():
    import function_limits
    for name, text in CELEBI.items():
        if name.endswith(".mcfunction"):
            assert function_limits.check_lines(text.splitlines(), name) == [], name
