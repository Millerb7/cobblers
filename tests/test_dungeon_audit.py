"""The independent audit of the dungeon engine (tools/dungeon.py) and the run tag's blackout half (E1).

Written by the test author, who wrote neither (CLAUDE.md principle 16). Static checks are tools/dungeon_audit.py's;
the behaviour runs the GENERATED functions of both packs on tests/rift_audit_sim.py (pocket_sim plus the dungeon
pack's commands, written for this audit, not the builder's extension) and on tests/test_dungeon_death.py's blackout
harness. Every expectation is hand-computed from DUNGEONS.md (the rates, the 100-tick credit window, the 40-tick
arrival, the ladder, the clock table), never from tools/dungeon.py. The mutations edit the GENERATORS' source in
memory and leave every data file alone ("How to prove an audit is independent").

Not covered here (it needs a server): that vanilla's kill credit is 100 ticks and reaches the blackout as a wild kill
(ASSUMED in DUNGEONS.md 2.5), that Cobblemon runs q.run_command synchronously, that `kill` passes a totem (B2 ran),
the battle callback's chain (C1), the logout behaviour of a battle (LO1), the recall of an owned Pokemon (P1), and DX1.
"""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon_audit as DA  # noqa: E402
import rift_audit_sim as RS  # noqa: E402
import test_blackout_pack as TB  # noqa: E402
import test_dungeon_death as DD  # noqa: E402

DG = DA.dungeon_files()
BO = DA.blackout_files()
BT = DA.blackout_terms()
TAG, TAIL_END, BACKSTOP, EXEMPT = BT["tag"], BT["tail_end"], BT["backstop"], BT["exempt"]
FNS = DA.functions(DG)
OW, POCKET = RS.OW, RS.POCKET
PASS = 20                                   # the keeper's period: DUNGEONS.md 2.1, "each keeper pass (20 ticks)"
PICK_KEY = "cobblers_dg_pick"


# ------------------------------------------------------------------------------------------------- generator mutation


def mutated(module, old, new, *more):
    """A copy of tools/<module>.py with each `old` replaced by its `new` in its SOURCE (each exactly once), loaded
    fresh. The data files are never touched."""
    path = ROOT / "tools" / ("%s.py" % module)
    src = path.read_text(encoding="utf-8")
    pairs = [(old, new)] + list(zip(more[::2], more[1::2]))
    for o, n in pairs:
        assert src.count(o) == 1, "the mutation's anchor is not unique in tools/%s.py: %r" % (module, o)
        src = src.replace(o, n)
    mod = types.ModuleType("%s_audit_mutant" % module)
    mod.__file__ = str(path)
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


# ------------------------------------------------------------------------------------------------- driving a run


def crafted_sigil(band, files=DG):
    """The band's sigil as a Crafter makes it from the generated recipe: EXP-083 step 7 read the crafted Soot Sigil's
    custom_data number as a BYTE."""
    r = json.loads(files["data/cobblers/recipe/dg_sigil_b%d.json" % band])["result"]
    (key, v), = r["components"]["minecraft:custom_data"].items()
    return [r["id"], {key: (v, "b")}, 1]


def reward(w, prefix):
    (fn,) = [a["rewards"]["function"] for k, a in w.advs.items() if k.startswith(prefix)]
    return fn


def outside(files=DG):
    """Where the engine puts a player out: the overworld tp in the dungeon's out function."""
    for l in DA.body(DA.functions(files)["cobblers:dungeons/m/out_ns"]):
        m = re.search(r"in minecraft:overworld run tp @s (\S+) (\S+) (\S+)", l)
        if m:
            return [float(v) for v in m.groups()]
    raise AssertionError("no out point")


def new_world(dg=None, bo=None):
    return RS.world(dg or DG, bo or BO)


def player(w, name="Ash", cap=20, band=1, files=DG):
    p = w.player(name, OW, outside(files))
    w.set(name, "cobblers.lc_cap", cap)
    p.inventory.append(crafted_sigil(band, files))
    p.inventory.append(["minecraft:iron_pickaxe", {}, 1])        # their own: must never be taken
    return p


def PS_ctx(p):
    return RS.PS.Ctx(p, p.dim, p.pos, p.yaw)


def click(w, p, prefix):
    w.call(reward(w, prefix), PS_ctx(p))


def score(w, p, obj):
    return w.get(p.name, obj)


def to_pass_edge(w):
    """Tick until the keeper has just run (the next keeper is PASS ticks away)."""
    while (w.scheduled.get("cobblers:dungeons/keeper", 0) - w.gametime) != PASS:
        w.tick(1)


def until(w, cond, limit=2000):
    for _ in range(limit):
        if cond():
            return w.gametime
        w.tick(1)
    raise AssertionError("never happened in %d ticks" % limit)


def enter(w, p):
    """Click the rip (with a sigil) on a pass edge, then wait for the arrival. Returns (click tick, arrival tick)."""
    to_pass_edge(w)
    p.dim, p.pos = OW, outside()
    t0 = w.gametime
    click(w, p, "cobblers:dungeons/rip_")
    t1 = until(w, lambda: p.dim == POCKET)
    return t0, t1


def cross(w, p):
    """Walk past the entry room's board: 17 blocks east of the arrival point, then one pass."""
    p.pos = [p.pos[0] + 17, p.pos[1], p.pos[2]]
    to_pass_edge(w)
    w.tick(PASS)
    assert score(w, p, "dg.st") == 3, "the clock did not start past the threshold"


def has_pick(p):
    return any(PICK_KEY in s[1] for s in p.inventory)


def own_pick(p):
    return any(s[0] == "minecraft:iron_pickaxe" and not s[1] for s in p.inventory)


def sigils_held(p):
    return sum(s[2] for s in p.inventory if "cobblers_dg_sigil" in s[1])


def watch(w, p, ticks):
    """[(tick, dim, holds the run tag, dead)] after each of `ticks` ticks."""
    out = []
    for _ in range(ticks):
        w.tick(1)
        out.append((w.gametime, p.dim, TAG in p.tags, p.dead))
    return out


def timer_death(w, p, ticks_left=60):
    """A live run's clock set to `ticks_left` ticks of x1 clock on a pass edge (the moment of a wild hit), then run to
    the timer's kill. Returns (hit tick, death record)."""
    to_pass_edge(w)
    w.set(p.name, "dg.clock", ticks_left * DA.UNITS_PER_TICK)
    hit = w.gametime
    until(w, lambda: p.dead, 400)
    return hit, w.deaths[-1]


# ================================================================================================ static (the tool)


# Without it a check of tools/dungeon_audit.py that fails on the real packs goes unseen: V15's static half, the timer,
# V1, V12, C1 and the sigils, each over the generated packs.
@pytest.mark.parametrize("check", sorted(DA.CHECKS))
def test_the_generated_packs_pass_the_static_audit(check):
    assert DA.CHECKS[check](DG, BO, None) == []


# Without it the V15 spawn check could pass on a pack with no spawn site at all (the list would be empty).
def test_the_spawn_check_sees_every_engine_spawn():
    sites = DA.spawn_sites(FNS)
    assert sites and all(re.fullmatch(r"cobblers:dungeons/slot/s\d+/spawn", s) for s, _h in sites), sites
    assert len(sites) == len([f for f in FNS if re.fullmatch(r"cobblers:dungeons/slot/s\d+/spawn", f)])


# ================================================================================================ V15 / E1, behaviour


# Without it the run tag could be added at the arrival (inside the slot) instead of at the click, so a wild hit at the
# rip's mouth during the delay credits a claim; or the arrival could come early (E1 item 1: "before the 40-tick
# arrival delay").
def test_the_run_tag_is_on_the_player_at_the_click_and_the_arrival_waits_at_least_40_ticks():
    for offset in (0, 1, 19):                       # the click lands anywhere between two keeper passes
        w = new_world()
        p = player(w)
        to_pass_edge(w)
        w.tick(offset)
        t0 = w.gametime
        click(w, p, "cobblers:dungeons/rip_")
        assert TAG in p.tags and p.dim == OW, (offset, p.tags, p.dim)
        assert sigils_held(p) == 0, "the sigil is taken at the click"
        t1 = until(w, lambda: p.dim == POCKET)
        assert t1 - t0 >= DA.ARRIVAL_DELAY_TICKS, (offset, t1 - t0)
        assert TAG in p.tags


# Without it a stage NPC stands in the slot without claims.exempt_tag until the keeper's backstop a pass later, and a
# loss to it in that window is the victor-side gap D20 closes (V15: "tags the entity ... in the same function").
@pytest.mark.parametrize("site", [s for s, _h in DA.spawn_sites(FNS)])
def test_every_npc_an_engine_spawn_makes_carries_the_exempt_tag_when_the_spawn_returns(site):
    g = int(re.search(r"/s(\d+)/spawn$", site).group(1))
    for band in range(1, 7):
        for stage in (1, 2, 3):
            w = new_world()
            p = player(w)
            p.dim = POCKET
            p.pos = [90.0, 96.0, 1056.0 + 128 * (g - 1)]
            for obj, v in (("dg.band", band), ("dg.stage", stage), ("dg.slot", g), ("dg.run", 1)):
                w.set(p.name, obj, v)
            w.set("#s%d" % g, "dg.run", 1)
            w.call(site, PS_ctx(p))
            assert len(w.npcs) == 1, (site, band, stage, w.log)
            assert EXEMPT in w.npcs[0].tags, (site, band, stage, w.npcs[0].tags)


def _exit_paths():
    return ["back_before_threshold", "back_after_threshold", "far", "timer_death", "put_out_mid_run",
            "dead_run_on_relog"]


def run_exit(path, dg=None):
    """Drive one way out of a run. Returns (world, player, E: the last tick the player was in the slot alive or the
    death tick)."""
    w = new_world(dg)
    p = player(w, files=dg or DG)
    enter(w, p)
    if path == "back_before_threshold":
        to_pass_edge(w)
        w.tick(7)
        e = w.gametime
        click(w, p, "cobblers:dungeons/back")
        assert p.dim == OW
        return w, p, e
    cross(w, p)
    if path in ("back_after_threshold", "far"):
        to_pass_edge(w)
        w.tick(1)
        e = w.gametime
        click(w, p, "cobblers:dungeons/%s" % ("back" if path.startswith("back") else "far"))
        assert p.dim == OW, path
        return w, p, e
    if path == "timer_death":
        _hit, d = timer_death(w, p)
        w.tick(1)
        w.respawn(p)
        return w, p, d["t"]
    if path == "put_out_mid_run":
        to_pass_edge(w)
        w.tick(3)
        e = w.gametime
        p.dim, p.pos = OW, [500.5, 80.0, 500.5]               # a waystone or another pack moved them
        return w, p, e
    if path == "dead_run_on_relog":
        to_pass_edge(w)
        w.set(p.name, "dg.clock", 200)                       # 50 ticks of clock left at x1
        p.online = False
        w.tick(PASS * 10)
        p.online = True
        until(w, lambda: p.dead, 100)
        e = w.gametime
        w.tick(1)
        w.respawn(p)
        return w, p, e
    raise AssertionError(path)


def tail_end_tick(w, p, limit=600):
    for t, _dim, held, _dead in watch(w, p, limit):
        if not held:
            return t
    raise AssertionError("the run tag never went")


# Without it a hit taken in the slot can credit an overworld death a second later and make a claim (E1 item 3: "the
# tag outlives the run by a tail of 100 ticks after every way out"), or the tail's end delivers a claim inside the
# slot or while the tag is still held (item 4). Measured from the last tick in the slot to the tick the tag goes.
@pytest.mark.parametrize("path", _exit_paths())
def test_the_run_tag_outlives_every_way_out_by_the_credit_window_and_ends_outside_the_pocket(path):
    w, p, e = run_exit(path)
    r = tail_end_tick(w, p)
    assert r - e >= DA.CREDIT_WINDOW_TICKS, (path, r - e)
    assert r - e >= BT["tail"], (path, r - e)
    assert p.dim == OW
    ends = [d for d in w.delivered if d["t"] == r]
    assert len(ends) == 1 and ends[0]["dim"] == OW and TAG not in ends[0]["tags"], (path, w.delivered)
    assert all(d["dim"] == OW and TAG not in d["tags"] for d in w.delivered), w.delivered


# Without it a player still in the pocket when their tail runs out (in another pocket room, or not yet put out) is
# untagged and delivered to at their feet in the pocket (E1 interface 5).
def test_the_tail_end_waits_while_the_player_is_in_the_pocket():
    w = new_world()
    p = player(w)
    p.dim, p.pos = POCKET, [-768.5, 96.0, -768.5]            # Entei's first room, far from every slot
    p.tags.add(TAG)
    w.set(p.name, "dg.tail", 40)
    w.tick(PASS * 10)
    assert TAG in p.tags and not w.delivered
    p.dim, p.pos = OW, [10.5, 70.0, 10.5]
    w.tick(PASS * 2)
    assert TAG not in p.tags and len(w.delivered) == 1 and w.delivered[0]["dim"] == OW


# Without it a stale tag (a logout during the tail, a run that ended without one) exempts the player in the overworld
# for good; and the backstop must never fire in the pocket (E1 item 3, "the tag cannot go stale").
def test_a_stale_run_tag_is_swept_in_the_overworld_and_never_in_the_pocket():
    w = new_world()
    p = player(w)
    p.tags.add(TAG)
    p.dim, p.pos = POCKET, [-768.5, 96.0, -768.5]
    w.tick(PASS * 3)
    assert TAG in p.tags
    p.dim, p.pos = OW, [10.5, 70.0, 10.5]
    w.tick(PASS)
    assert TAG not in p.tags and len(w.delivered) == 1


# Without it the timer's kill within the credit window of a wild hit (the owner's case, DUNGEONS.md 2.5) takes items
# into a guardian: the engine's death must reach the blackout with the run tag still held, and the blackout must then
# make no claim on either credited path, while the same death without the tag still claims (so the harness reaches
# the claim at all).
@pytest.mark.parametrize("path", DD.PATHS)
def test_a_wild_hit_then_the_timer_kill_60_ticks_later_makes_no_claim(path):
    w = new_world()
    p = player(w)
    enter(w, p)
    cross(w, p)
    hit, death = timer_death(w, p, ticks_left=60)
    assert death["t"] - hit == 60, death["t"] - hit                 # within vanilla's window (ASSUMED 100 ticks)
    assert TAG in death["tags"] and death["dim"] == POCKET
    fns = TB.functions(BO)
    s = DD._death(fns, path, player_tags=tuple(death["tags"]))
    assert DD.seizure(s) == [], DD.seizure(s)
    assert DD.blackout_cost(s), s.log
    control = DD._death(fns, path, player_tags=tuple(death["tags"] - {TAG}))
    assert "called recovery/make" in DD.seizure(control)
    # a second death in the overworld inside the window of that hit is still exempt
    w.tick(1)
    w.respawn(p)
    w.tick(PASS)
    assert TAG in p.tags and w.gametime - hit <= DA.CREDIT_WINDOW_TICKS


# Without it the run's death handling could free the tag on respawn, before the tail (E1: "never the tag removed").
def test_the_respawn_after_a_death_keeps_the_run_tag():
    w, p, e = run_exit("timer_death")
    w.tick(PASS * 2)
    assert score(w, p, "dg.st") == 0 and TAG in p.tags


# ================================================================================================ V15 mutations


# Without it the V15 spawn check is not shown to bite: a stage spawn that no longer binds its NPC (the keeper's
# backstop would tag it a pass later) must fail both the static check and the spawn-returns behaviour.
def test_a_stage_spawn_that_does_not_tag_its_npc_is_caught():
    mod = mutated("dungeon", 'F("slot/s%d/bind_boss" % g)),',
                  'F("slot/s%d/bind_boss" % g)) if False else "# AUDIT MUTANT: the stage spawn binds nothing",')
    files = DA.dungeon_files(mod)
    assert any("does not tag the spawned entity" in x for x in DA.check_v15(files, BO))
    w = new_world(files)
    p = player(w, files=files)
    p.dim, p.pos = POCKET, [90.0, 96.0, 1056.0]
    for obj, v in (("dg.band", 1), ("dg.stage", 1), ("dg.slot", 1), ("dg.run", 1)):
        w.set(p.name, obj, v)
    w.set("#s1", "dg.run", 1)
    w.call("cobblers:dungeons/slot/s1/spawn", PS_ctx(p))
    assert w.npcs and EXEMPT not in w.npcs[0].tags


# Without it a respawn handler that removes the run tag (the order E1 forbids) is not shown to be caught: the static
# remover check and the measured tail both fail.
def test_removing_the_run_tag_in_the_respawn_handler_is_caught():
    mod = mutated("dungeon", 'died += ["function %s" % F("m/lines"), "function %s" % F("m/end")]',
                  'died += ["tag @s remove %s" % RUN_TAG, "function %s" % F("m/lines"), "function %s" % F("m/end")]')
    files = DA.dungeon_files(mod)
    assert any("is removed by" in x for x in DA.check_v15(files, BO))
    w, p, e = run_exit("timer_death", files)
    for _t, _d, held, _dead in watch(w, p, PASS * 2):
        pass
    assert TAG not in p.tags and w.gametime - e < DA.CREDIT_WINDOW_TICKS


# Without it the deliver guard's absence is not shown to be caught: a claim settled while its owner is in a run drops
# at their feet in the slot again (E1 item 4).
def test_dropping_the_deliver_guard_is_caught():
    mod = mutated("blackout_pack", '"execute if entity @s[tag=%s] run return 0" % dg_tag] if dg_tag else [])',
                  '"# AUDIT MUTANT: no deliver guard"] if dg_tag else [])')
    files = DA.blackout_files(mod)
    assert any("recovery/deliver's first command" in x for x in DA.check_v15(DG, files))
    drops, _s = DD._delivery(TB.functions(files), (TAG,))
    assert drops, "the mutant must drop the items in the slot"
    drops, _s = DD._delivery(TB.functions(BO), (TAG,))
    assert drops == []


# Without it a tail shorter than the credit window passes: the measured tail of every way out must fall below 100.
def test_a_tail_shorter_than_the_credit_window_is_caught():
    mod = mutated("dungeon", "tail_start = TAIL + P", "tail_start = TAIL + P - 40")
    files = DA.dungeon_files(mod)
    short = []
    for path in ("back_after_threshold", "timer_death", "put_out_mid_run"):
        w, p, e = run_exit(path, files)
        short.append(tail_end_tick(w, p) - e)
    assert min(short) < DA.CREDIT_WINDOW_TICKS, short


# Without them the timer, V1, V12, C1 and sigil checks are not shown to bite: each mutant generator (data untouched)
# must fail its own check by name.
NO_PROBLEMS = ('bad = problems(doc,', 'bad = [] and problems(doc,')
OTHER_MUTANTS = {
    "timer: the timer's kill is a damage": ("timer", "uses `damage`", (
        '"scoreboard players set @s %s 1" % O["cause"],\n        "kill @s"]',
        '"scoreboard players set @s %s 1" % O["cause"],\n        "damage @s 1000 minecraft:outside_border"]')),
    "V1: the slots' rows move into the probe row and the rescue box": ("V1", "meets", (
        'z0 = s["rows_from_z"] + (g - 1) * s["row_spacing"]', 'z0 = -700 + (g - 1) * s["row_spacing"]') + NO_PROBLEMS),
    "V12: the lockout is shorter than the longest clock": ("V12", "under the longest clock", (
        'lock = e["lockout_ticks"]', 'lock = 40000') + NO_PROBLEMS),
    "C1: the NPC spawn is a plain line": ("C1", "plain line", (
        '"$spawnnpcat $(x) $(y) $(z) $(cls) $(level)"', '"spawnnpcat 0 96 0 cobblers:dg_ns_boss_b1_s1 18"')),
    "sigils: the predicate is the int form": ("sigils", "not the byte form", (
        'return "%s[minecraft:custom_data~{%s:%db}]"', 'return "%s[minecraft:custom_data~{%s:%d}]"')),
}


@pytest.mark.parametrize("name", sorted(OTHER_MUTANTS))
def test_each_static_check_fails_its_generator_mutant(name):
    check, words, pairs = OTHER_MUTANTS[name]
    files = DA.dungeon_files(mutated("dungeon", *pairs))
    probs = DA.CHECKS[check](files, BO, None)
    assert any(words in x for x in probs), (name, probs)


# Without it a predicate in the int form would pass every text check yet never find a crafted sigil (EXP-083): run
# on the simulator, the int-form mutant refuses a player holding a crafted Soot Sigil, and the real pack takes it.
def test_a_crafted_sigil_opens_the_rip_and_the_int_form_would_not():
    _check, _w, pairs = OTHER_MUTANTS["sigils: the predicate is the int form"]
    for files, opens in ((DG, True), (DA.dungeon_files(mutated("dungeon", *pairs)), False)):
        w = new_world(files)
        p = player(w, files=files)
        to_pass_edge(w)
        click(w, p, "cobblers:dungeons/rip_")
        assert (score(w, p, "dg.st") == 1) == opens and (sigils_held(p) == 0) == opens, (opens, p.inventory)


# ================================================================================================ the timer


# Without it the clock could fall at the wrong speed at some ladder rate (DUNGEONS.md 2.1: each pass subtracts 20 x
# rate quarter-ticks; the rates 4, 5, 6, 8, 12).
@pytest.mark.parametrize("rate", DA.DESIGN_RATES)
def test_the_clock_falls_twenty_ticks_of_its_rate_each_pass(rate):
    w = new_world()
    p = player(w)
    enter(w, p)
    cross(w, p)
    to_pass_edge(w)
    w.set(p.name, "dg.rate", rate)
    w.set(p.name, "dg.clock", 100000)
    for n in (1, 2, 3):
        w.tick(PASS)
        assert score(w, p, "dg.clock") == 100000 - n * PASS * rate, (rate, n, score(w, p, "dg.clock"))


# Without it the greed ladder could change the rate at the wrong count (D13: x1.25 at 5, x1.5 at 10, x2 at 15, x3 at
# 20, holding).
def test_the_greed_ladder_sets_the_owners_rates():
    want = {1: 4, 4: 4, 5: 5, 9: 5, 10: 6, 14: 6, 15: 8, 19: 8, 20: 12, 30: 12}
    w = new_world()
    p = player(w)
    enter(w, p)
    cross(w, p)
    for n in range(1, 31):
        w.call("cobblers:dungeons/greed/take", PS_ctx(p))
        if n in want:
            assert score(w, p, "dg.rate") == want[n], (n, score(w, p, "dg.rate"))


# Without it a player could be killed mid-battle at 0, or killed while the NPC payout's clawback still measures
# (E1 item 6), or never killed after both end (DUNGEONS.md 2.5 sudden death).
def test_at_zero_in_battle_the_kill_waits_for_the_battle_and_the_clawback():
    w = new_world()
    p = player(w)
    enter(w, p)
    cross(w, p)
    to_pass_edge(w)
    w.battle.add(p.name)
    w.set(p.name, "dg.clock", 80)
    w.tick(PASS * 4)
    assert not p.dead and score(w, p, "dg.clock") == 0 and score(w, p, "dg.st") == 4
    w.battle.discard(p.name)
    w.set(p.name, "dg.claw", 1)
    w.tick(PASS * 3)
    assert not p.dead
    w.set(p.name, "dg.claw", 0)
    w.tick(PASS)
    assert p.dead and w.deaths[-1]["tags"] >= {TAG}
    assert score(w, p, "dg.cause") == 1


# Without it a logout pauses the clock (D15): the absence is charged on return at the player's rate, so after the
# first pass back the clock is lower by every tick since the last pass they were seen, times the rate.
@pytest.mark.parametrize("rate", (4, 12))
@pytest.mark.parametrize("away_passes", (1, 7))
def test_a_logout_charges_every_tick_away_at_the_players_rate(rate, away_passes):
    w = new_world()
    p = player(w)
    enter(w, p)
    cross(w, p)
    to_pass_edge(w)
    w.set(p.name, "dg.rate", rate)
    w.set(p.name, "dg.clock", 150000)
    w.tick(PASS)
    c0 = score(w, p, "dg.clock")
    p.online = False
    w.tick(PASS * away_passes)                      # `away_passes` keeper passes run without them
    p.online = True
    w.tick(PASS)                                    # the first pass back: (away_passes + 1) passes since last seen
    assert score(w, p, "dg.clock") == c0 - (away_passes + 1) * PASS * rate


# Without it an absent player holds one of the slots past their clock, or loses it early (2.6: freed at the deadline).
# 130 ticks of clock at x1: spent between the 6th and 7th pass, so the slot is held after pass 6 and free after 7.
def test_an_absent_players_slot_is_freed_at_their_deadline_and_not_before():
    w = new_world()
    p = player(w)
    enter(w, p)
    cross(w, p)
    to_pass_edge(w)
    w.set(p.name, "dg.clock", 130 * 4 + PASS * 4)              # one more pass, present, takes 20 ticks
    w.tick(PASS)
    assert score(w, p, "dg.clock") == 130 * 4
    p.online = False
    w.tick(PASS * 6)
    assert w.get("#s1", "dg.own") == score(w, p, "dg.id")
    w.tick(PASS)
    assert w.get("#s1", "dg.own") == 0


# Without it a player returning to a run that died while they were away gets a pass of the live run first (the bar,
# the boss, the clock) before the kill, or no kill (2.6: "runs before the eject and before anything else").
def test_a_return_to_a_dead_run_is_killed_first_on_the_first_pass():
    w = new_world()
    a = player(w, "Ash")
    enter(w, a)
    cross(w, a)
    to_pass_edge(w)
    w.set(a.name, "dg.clock", 130 * 4 + PASS * 4)
    w.tick(PASS)                                    # seen once more: the slot's deadline is 130 ticks from here
    a.online = False
    w.tick(PASS * 8)
    assert w.get("#s1", "dg.own") == 0
    b = player(w, "Misty")
    enter(w, b)                                     # the freed slot 1 goes to someone else
    assert score(w, b, "dg.slot") == 1
    to_pass_edge(w)
    a.online = True
    mark = len(w.calls)
    w.tick(PASS)
    assert a.dead
    mine = [c for c, who in w.calls[mark:] if who == a.name]
    assert mine[:4] == ["cobblers:dungeons/m/member", "cobblers:dungeons/m/gap", "cobblers:dungeons/m/void",
                        "cobblers:dungeons/m/deadkill"], mine
    assert TAG in w.deaths[-1]["tags"] and not b.dead and b.dim == POCKET
    w.tick(1)
    w.respawn(a)
    w.tick(PASS)
    assert any(n == a.name and "closed without you" in txt for _t, n, _k, txt in w.titles), w.titles


# Without it the lockout could be measured on game time, which a re-export or /time set moves (2.5), or be shorter
# than an hour of uptime from the threshold (D17; V12 holds it to at least the longest clock).
def test_the_lockout_counts_an_hour_of_uptime_and_ignores_game_time():
    w = new_world()
    p = player(w)
    enter(w, p)
    cross(w, p)
    stamp = w.get("#up", "dg.up")
    click(w, p, "cobblers:dungeons/back")
    assert p.dim == OW and score(w, p, "dg.st") == 0
    p.inventory.append(crafted_sigil(1))
    w.gametime += 50_000_000                        # /time set, a re-export: game time leaps
    w.tick(1)
    click(w, p, "cobblers:dungeons/rip_")
    assert score(w, p, "dg.st") == 0 and sigils_held(p) == 1, "refused, sigil kept"
    until(w, lambda: w.get("#up", "dg.up") - stamp >= 72000 - PASS, 80000)
    to_pass_edge(w)
    click(w, p, "cobblers:dungeons/rip_")
    assert score(w, p, "dg.st") == 0, "still refused one pass before the hour"
    w.tick(PASS)
    assert w.get("#up", "dg.up") - stamp == 72000
    click(w, p, "cobblers:dungeons/rip_")
    assert score(w, p, "dg.st") == 1 and TAG in p.tags


# ================================================================================================ V13


# Without it a way out leaves the player in adventure mode in the overworld, or keeps the rift pick (an unbreakable
# free iron pickaxe in survival), or takes their own pickaxe by item id (DUNGEON_DEATH.md 4 rule 6).
@pytest.mark.parametrize("path", _exit_paths())
def test_every_way_out_restores_survival_and_takes_only_the_rift_pick(path):
    w, p, _e = run_exit(path)
    w.tick(PASS * 2)
    assert not p.dead and p.dim == OW, path
    assert p.gamemode == "survival" and "dg.adv" not in p.tags, (path, p.gamemode, p.tags)
    assert not has_pick(p) and own_pick(p), (path, p.inventory)


# Without it a stranger in a slot (not its member) keeps adventure or the pick when the sweep puts them out.
def test_the_eject_of_a_non_member_restores_survival_and_takes_the_pick():
    w = new_world()
    q = player(w, "Brock")
    q.dim, q.pos = POCKET, [30.5, 96.0, 1056.5]
    q.gamemode = "adventure"
    q.tags.add("dg.adv")
    q.inventory.append(["minecraft:iron_pickaxe", {PICK_KEY: (1, "b")}, 1])
    w.tick(PASS * 2)
    assert q.dim == OW and q.gamemode == "survival" and not has_pick(q) and own_pick(q)


# Without it a relog into a live run drops adventure or the pick (2.6: the run goes on; V13's last clause).
def test_a_relog_into_a_live_run_keeps_adventure_and_the_pick():
    w = new_world()
    p = player(w)
    enter(w, p)
    cross(w, p)
    p.online = False
    w.tick(PASS * 2)
    p.online = True
    w.tick(PASS * 2)
    assert p.dim == POCKET and score(w, p, "dg.st") == 3
    assert p.gamemode == "adventure" and has_pick(p) and TAG in p.tags


# Without it a sigil returned at the back rip is a different item from the crafted one, and the next click does not
# match it (EXP-083: the predicate must read the byte form a crafted sigil holds).
def test_a_refunded_sigil_is_the_crafted_one_and_opens_the_rip_again():
    w = new_world()
    p = player(w)
    enter(w, p)
    click(w, p, "cobblers:dungeons/back")
    assert sigils_held(p) == 1
    (s,) = [s for s in p.inventory if "cobblers_dg_sigil" in s[1]]
    assert s[:2] == crafted_sigil(1)[:2]
    w.tick(PASS * 7)                                # the tail ends
    click(w, p, "cobblers:dungeons/rip_")
    assert score(w, p, "dg.st") == 1 and sigils_held(p) == 0


# ================================================================================================ defects (strict xfail)


# Without it a player who logs out in the entry room past the hold comes back to a slot the keeper has FREED (owner 0,
# no tending, open to the next click) and carries on into a timed run there; once they have crossed the threshold, a
# second player's click takes the same slot, resets it under them, and the run-id check kills them for it (simulated:
# the sigil spent, the lockout stamped, $600 taken). data/dungeons.json keeper.entry_hold_why says "on their
# return the run is void and the sigil returned"; the engine frees the slot (slot/s<g>/free) without changing the
# slot's run id, and m/member voids on the run id only.
# FIXED 2026-10-09 by the main session (slot/s<g>/free now sets the slot's dg.run to 0): the strict xfail turned red
def test_a_player_whose_slot_was_freed_never_resumes_a_run_in_it():
    w = new_world()
    p = player(w)
    enter(w, p)
    p.online = False
    w.tick(PASS * 310)                              # past the 6,000-tick entry hold
    assert w.get("#s1", "dg.own") == 0
    p.online = True
    w.tick(PASS * 2)
    assert p.dim == OW and score(w, p, "dg.st") == 0 and sigils_held(p) == 1, (p.dim, score(w, p, "dg.st"))


# Without it the design's "dungeon wins pay $0 net" (DUNGEONS.md 11.4 new contracts) is silently untrue: a won boss
# stage is an NPC win, and CobbleDollars credits it (earnCobbleDollarsFromNPC true). Nothing in the pack measures a
# clawback: dg.claw is never set to 1. Size today: tools/dungeon_audit.py --payout (band 1 $202-$405 a run, band 6
# $11,062-$22,125), once an hour per player and dungeon.
@pytest.mark.xfail(strict=True, reason="DEFECT (known, step 6): a won boss stage keeps CobbleDollars' NPC payout; "
                                       "no function starts the dg.claw clawback")
def test_a_won_boss_stage_pays_nothing_net():
    assert DA.boss_payouts(DG) is None or any(
        re.search(r"scoreboard players set @s dg\.claw [1-9]", l) for ls in FNS.values() for l in DA.body(ls))
