"""Heaven's Arena's money: the purse policy and the clawback of CobbleDollars' own automatic NPC-win payout
(data/arena_fights.json prizes.purse_policy; docs/mechanics/ECONOMY_OVERHAUL.md section 6; tools/arena_runtime.py,
unit ARENACAP).

Written by the builder of the feature, because the brief asked for it; an independent test author should extend it.
The generated functions run in tests/test_arena_runtime_build.py's command model (imported, not copied), extended here
with the three commands this feature adds and nothing else:

  cobbledollars query <player>      its result is the balance (CobbleDollarsCommand.query returns BigInteger.intValue)
  cobbledollars give|remove <p> <n> n >= 1 (BigIntegerArgumentType.bigInt(1)); remove takes min(n, balance)
  time query gametime               a clock the test sets

CobbleDollars' own payout is modelled as the jar does it (docs/research/notes/paid-services-and-npc-payouts.md B2):
a credit to the winner on BATTLE_VICTORY, at a moment the test chooses -- before the arena's callback or after it,
because the jar does not fix the order. The worst-case credit is computed HERE from the bytecode formula and
modpack/config/cobbledollars/common.json, never from tools/arena_runtime.cd_bound. The expected purses come from the
data's `typical` figures and the economy design's own sum ($47,050 for the first clears of ranks 1-4).

Not covered (needs a server, experiments/EXP-060-arena-payout): that `cobbledollars query` stores the balance through
`execute store result`; that CobbleDollars really credits an arena win; which handler runs first.
"""
import copy
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("arena_build_model", ROOT / "tests" / "test_arena_runtime_build.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
AR = M.AR

FIGHTS = M.FIGHTS
RANKS = M.RANKS
EXAM = {e["rank"]: e["purse_typical"] for e in FIGHTS["rank_up_fights"]}
POLICY = FIGHTS["prizes"]["purse_policy"]
GYM8, LANCE, CHAMP = M.GYM8, M.LANCE, M.CHAMP
MULT = Decimal(str(json.loads((ROOT / "modpack" / "config" / "cobbledollars" / "common.json")
                              .read_text(encoding="utf-8"))["cobbleDollarsIncomeMultiplier"]))


def jar_max(levels):
    """The largest credit CobbleDollars' battleVictory can make for one loser with these levels (bytecode 370-567):
    B = max(1, int(5 * sum * sum(L / 50.0))); amount = B + nextBetween(B/2, 2B), at most 3B; floor(amount * mult)."""
    b = max(1, int(5 * sum(levels) * sum(lv / 50.0 for lv in levels)))
    return int(Decimal(3 * b) * MULT)


class MoneySim(M.Sim):
    def __init__(self, pack, auto=0, order="before"):
        self.gametime = 0
        self.auto, self.order = auto, order
        self.removed = []
        super().__init__(pack)

    def query(self, cmd, ctx):
        t = cmd.split(" ")
        if t[:2] == ["cobbledollars", "query"] and len(t) == 3:
            (e,) = self.select(t[2], ctx)
            return self.money.get(e.uuid, 0)
        if t == ["time", "query", "gametime"]:
            return self.gametime
        return super().query(cmd, ctx)

    def command(self, line, ctx):
        t = line.split(" ")
        if t[0] == "cobbledollars":
            assert len(t) == 4 and t[1] in ("give", "remove"), "unmodelled: %s" % line
            (e,) = self.select(t[2], ctx)
            n = int(t[3])
            assert n >= 1, "the jar's give/remove refuse an amount under 1: %s" % line
            bal = self.money.get(e.uuid, 0)
            if t[1] == "give":
                self.money[e.uuid] = bal + n
            else:
                self.money[e.uuid] = bal - min(n, bal)
                self.removed.append(min(n, bal))
            return
        return super().command(line, ctx)

    def credit(self, player):
        self.money[player.uuid] = self.money.get(player.uuid, 0) + self.auto

    def result(self, player, won):
        if won and self.auto and self.order == "before":
            self.credit(player)
        super().result(player, won)
        if won and self.auto and self.order == "after":
            self.credit(player)

    def bal(self, p):
        return self.money.get(p.uuid, 0)


def bout(sim, p, won=True):
    sim.tick(AR.GO_TICKS)
    sim.result(p, won)
    sim.tick(AR.END_TICKS)


@pytest.fixture(scope="module")
def pack():
    return AR.files(M.FIXTURE)


def rank1_win(sim, p):
    sim.click(p, "floor_ring")
    bout(sim, p)


REP, REP_WINS = POLICY["repeat_purse"], POLICY["daily_cap_wins"]
R1 = RANKS[1]["purse"]["typical"]
R1_MAX = jar_max([RANKS[1]["levels"]["top"]] * RANKS[1]["members"])
LEG3, BONUS3 = RANKS[3]["purse"]["typical_per_leg"], RANKS[3]["purse"]["clear_bonus"]


def repeat_player(sim):
    """A rank-4 player without Lance at the floor ring fights rank 3 (the highest it offers that they hold): a rank
    they have cleared, so every win there is a repeat."""
    p = sim.player(adv=[GYM8])
    sim.scores[(p.uuid, "ar.rank")] = 4
    return p


# ------------------------------------------------------------------ the purse policy, as the economy design set it

def test_the_knobs_are_the_economy_designs():
    assert (REP, REP_WINS, POLICY["day_ticks"]) == (200, 3, 24000)
    assert POLICY["cobbledollars_auto_payout"]["kept_cap"] == 0
    assert "ECONOMY_OVERHAUL" in POLICY["source"]


def test_the_first_clears_of_ranks_1_to_4_pay_the_designs_47050_once(pack):
    sim = MoneySim(pack)
    p = sim.player(adv=[GYM8, LANCE])
    for _ in range(3):                                  # rank 1: three wins, then the exam
        rank1_win(sim, p)
    rank1_win(sim, p)
    assert sim.sc(p, "ar.rank") == 2
    for _ in range(4):                                  # rank 2: three wins, then the exam
        rank1_win(sim, p)
    assert sim.sc(p, "ar.rank") == 3
    for _ in range(2):                                  # rank 3: two clears of two legs, then the two-leg exam
        sim.click(p, "floor_ring")
        bout(sim, p)
        bout(sim, p)
    sim.click(p, "floor_ring")
    bout(sim, p)
    bout(sim, p)
    assert sim.sc(p, "ar.rank") == 4
    p.pos = [3620.0, 20.0, 3200.0]
    for _ in range(3):                                  # rank 4: two wins, then the exam
        sim.click(p, "door_ring")
        bout(sim, p)
    assert sim.sc(p, "ar.rank") == 5
    want = (3 * R1 + EXAM[1]) + (3 * RANKS[2]["purse"]["typical"] + EXAM[2]) \
        + (2 * (2 * LEG3 + BONUS3) + EXAM[3]) + (2 * RANKS[4]["purse"]["typical"] + EXAM[4])
    assert want == 47050, "the economy design's figure (ECONOMY_OVERHAUL section 6) no longer matches the data"
    assert sim.bal(p) == want


def test_a_cleared_rank_pays_the_flat_repeat_three_times_a_day_then_resets(pack):
    sim = MoneySim(pack)
    p = repeat_player(sim)
    sim.click(p, "floor_ring")
    assert sim.mine(p)[0].cls == "cobblers:arena_rank_3"
    for _ in range(2):
        bout(sim, p)                                    # a whole clear: two repeats, no clear bonus
    sim.click(p, "floor_ring")
    for _ in range(2):
        bout(sim, p)                                    # two more wins: only one is still paid today
    assert sim.bal(p) == REP * REP_WINS
    assert any("used up" in line for u, line in sim.said if u == p.uuid)
    sim.gametime += POLICY["day_ticks"]
    sim.click(p, "floor_ring")
    bout(sim, p)
    assert sim.bal(p) == REP * (REP_WINS + 1)
    assert sim.sc(p, "ar.wins") in (None, 0), "a cleared rank counts no progress"


def test_two_players_each_get_their_own_first_clear_and_their_own_repeat_count(pack):
    sim = MoneySim(pack)
    p = sim.player(adv=[GYM8])
    rank1_win(sim, p)
    q = sim.player(adv=[GYM8])
    rank1_win(sim, q)
    assert sim.bal(p) == sim.bal(q) == R1
    a, b = repeat_player(sim), repeat_player(sim)
    for x in (a, b):
        for _ in range(REP_WINS):
            sim.click(x, "floor_ring")
            bout(sim, x, True)
            bout(sim, x, False)
    assert sim.bal(a) == sim.bal(b) == REP * REP_WINS


def test_a_failed_gauntlet_keeps_its_paid_legs_and_re_won_legs_are_repeats(pack):
    sim = MoneySim(pack)
    p = sim.player(adv=[GYM8])
    sim.scores[(p.uuid, "ar.rank")] = 3
    sim.click(p, "floor_ring")
    bout(sim, p, True)
    bout(sim, p, False)
    assert sim.bal(p) == LEG3
    sim.click(p, "floor_ring")
    bout(sim, p, True)                                  # leg 1 again: already paid for this clear -> a repeat
    assert sim.bal(p) == LEG3 + REP
    bout(sim, p, True)                                  # leg 2 and the clear: never paid
    assert sim.bal(p) == 2 * LEG3 + REP + BONUS3
    assert sim.sc(p, "ar.wins") == 1


def test_an_exam_leg_won_then_lost_is_not_paid_twice(pack):
    sim = MoneySim(pack)
    p = sim.player(adv=[GYM8])
    sim.scores[(p.uuid, "ar.rank")] = 3
    sim.scores[(p.uuid, "ar.wins")] = RANKS[3]["advance"]["clears_at_rank"]
    first_leg = M.AR.purse([m["level"] for m in M.TRAINERS["arena_tier_1_champion"]["team"]], AR.purse_rule(FIGHTS))
    for _ in range(2):
        sim.click(p, "floor_ring")
        bout(sim, p, True)
        bout(sim, p, False)
    assert sim.bal(p) == first_leg + REP


def _streak_purse(k):
    st = RANKS[9]["streak"]
    lv, m = M._streak(k, st)
    return (13 * (m * lv - m * (m - 1) // 2) + 24) // 50 * 50


def test_a_streak_pays_only_new_bests_and_its_bonus_only_then(pack):
    bonus = RANKS[9]["purse"]["every_5th_win_bonus"]
    sim = MoneySim(pack)
    p = sim.player(pos=(3660, 20, 3200), adv=[GYM8, LANCE, CHAMP])
    sim.scores[(p.uuid, "ar.rank")] = 9
    sim.click(p, "crown_ring")
    for _ in range(5):
        bout(sim, p)
    first = sum(_streak_purse(k) for k in range(5)) + bonus
    assert sim.bal(p) == first
    bout(sim, p, False)
    sim.click(p, "crown_ring")
    for _ in range(6):
        bout(sim, p)
    # wins 1-5 again are repeats (three paid today, no bonus); win 6 extends the best
    assert sim.bal(p) == first + REP * REP_WINS + _streak_purse(5)
    assert sim.sc(p, "ar.spaid") == 6


# ------------------------------------------------------------------ CobbleDollars' own payout is taken back

@pytest.mark.parametrize("order", ["before", "after"])
def test_cobbledollars_auto_payout_is_taken_back_whichever_handler_runs_first(pack, order):
    sim = MoneySim(pack, auto=R1_MAX, order=order)
    p = sim.player(adv=[GYM8])
    sim.money[p.uuid] = 5000
    rank1_win(sim, p)
    assert sim.bal(p) == 5000 + R1, (order, sim.bal(p))
    assert sum(sim.removed) == R1_MAX


@pytest.mark.parametrize("order", ["before", "after"])
def test_a_repeat_win_nets_only_the_flat_repeat_even_with_the_auto_payout(pack, order):
    lv = RANKS[3]["levels"]["top"]
    sim = MoneySim(pack, auto=jar_max([lv] * RANKS[3]["members"]), order=order)
    p = repeat_player(sim)
    sim.click(p, "floor_ring")
    bout(sim, p, True)
    assert sim.bal(p) == REP


def test_the_largest_streak_payouts_are_taken_back(pack):
    sim = MoneySim(pack, order="after")
    p = sim.player(pos=(3660, 20, 3200), adv=[GYM8, LANCE, CHAMP])
    sim.scores[(p.uuid, "ar.rank")] = 9
    st = RANKS[9]["streak"]
    sim.click(p, "crown_ring")
    for k in range(3):
        lv, m = M._streak(k, st)
        sim.auto = jar_max([lv] * m)
        bout(sim, p)
    assert sim.bal(p) == sum(_streak_purse(k) for k in range(3))


def test_a_loss_takes_nothing(pack):
    sim = MoneySim(pack, auto=R1_MAX)
    p = sim.player(adv=[GYM8])
    sim.money[p.uuid] = 4321
    sim.click(p, "floor_ring")
    bout(sim, p, False)
    assert sim.bal(p) == 4321 and not sim.removed


def test_the_clawback_never_takes_more_than_cobbledollars_could_pay(pack):
    """A gain larger than the jar's maximum for this opponent (a teammate's gift mid-battle) is not all taken."""
    extra = 7000
    sim = MoneySim(pack, auto=R1_MAX + extra, order="before")
    p = sim.player(adv=[GYM8])
    rank1_win(sim, p)
    assert sim.bal(p) >= R1 + extra - AR.CLAW_MARGIN
    assert sum(sim.removed) <= R1_MAX + AR.CLAW_MARGIN


def test_leaving_right_after_a_win_still_takes_a_late_payout_back(pack):
    sim = MoneySim(pack, auto=R1_MAX, order="after")
    p = sim.player(adv=[GYM8])
    sim.click(p, "floor_ring")
    sim.tick(AR.GO_TICKS)
    sim.result(p, True)
    sim.ents.remove(p)                          # offline: @a no longer sees them, the clear-up never runs
    sim.tick(AR.END_TICKS)
    sim.ents.append(p)
    sim.scores[(p.uuid, "ar.left")] = 1
    sim.tick()
    assert sim.bal(p) == R1 and sim.sc(p, "ar.live") == 0


def test_a_stale_baseline_never_claws_later_income(pack):
    """Route income earned between arena visits is never measured: only a win reads the baseline."""
    sim = MoneySim(pack)
    p = sim.player(adv=[GYM8])
    rank1_win(sim, p)
    sim.money[p.uuid] += 9000                   # a day of trainers
    sim.click(p, "floor_ring")
    sim.call("arena/lose_run", p)
    sim.click(p, "floor_ring")
    bout(sim, p, False)
    assert sim.bal(p) == R1 + 9000 and not sim.removed


def test_the_generated_functions_snapshot_before_the_battle_and_settle_before_paying(pack):
    fn = {k[len("data/cobblers/function/arena/"):-len(".mcfunction")]: v for k, v in pack.items()
          if k.startswith("data/cobblers/function/arena/")}
    begin = fn["bout/begin"]
    snap = next(i for i, l in enumerate(begin) if "cd/snap" in l)
    start = next(i for i, l in enumerate(begin) if "start_battle" in l)
    assert snap < start
    won = fn["won"]
    assert won.index("function cobblers:arena/cd/settle") < won.index("function cobblers:arena/purse")
    assert any("cd/last" in l for l in fn["after"]) and any("cd/last" in l for l in fn["rejoined"])
    assert any(l.startswith("$execute store result score @s ar.bal run cobbledollars query @s") for l in fn["cd/snap"])
    assert any(l.startswith("$cobbledollars remove @s ") for l in fn["cd/claw"])


# ------------------------------------------------------------------ the knobs fail closed

def _policy(**kw):
    f = copy.deepcopy(FIGHTS)
    f["prizes"]["purse_policy"].update(kw)
    return f


@pytest.mark.parametrize("bad", [-1, "200", None, 1.5, True])
def test_a_bad_knob_fails_closed(bad):
    with pytest.raises(SystemExit):
        AR.files(M.FIXTURE, fights=_policy(repeat_purse=bad))


def test_keeping_any_of_the_auto_payout_is_refused_until_it_is_built():
    f = copy.deepcopy(FIGHTS)
    f["prizes"]["purse_policy"]["cobbledollars_auto_payout"]["kept_cap"] = 500
    with pytest.raises(SystemExit):
        AR.files(M.FIXTURE, fights=f)


def test_a_missing_policy_fails_closed():
    f = copy.deepcopy(FIGHTS)
    del f["prizes"]["purse_policy"]
    with pytest.raises(SystemExit):
        AR.files(M.FIXTURE, fights=f)


def test_a_zero_repeat_pays_nothing():
    sim = MoneySim(AR.files(M.FIXTURE, fights=_policy(repeat_purse=0)))
    p = repeat_player(sim)
    sim.click(p, "floor_ring")
    bout(sim, p)
    assert sim.bal(p) == 0


# ------------------------------------------------------------------ mutants of the GENERATOR (data untouched)

def _mutant_pack(old, new):
    return M._mutant(M.AR_SRC, old, new, "arena_runtime_payout_mutant", ROOT / "tools" / "arena_runtime.py") \
        .files(M.FIXTURE)


def test_mutation_no_first_clawback_is_caught():
    mp = _mutant_pack('        "function %s" % F_("cd/settle"),\n        "function %s" % F_("purse"),',
                      '        "function %s" % F_("purse"),')
    sim = MoneySim(mp, auto=R1_MAX, order="before")
    p = sim.player(adv=[GYM8])
    rank1_win(sim, p)
    assert sim.bal(p) != R1, "dropping the clawback in `won` went unnoticed"


def test_mutation_no_second_look_is_caught():
    mp = _mutant_pack('           "execute if score @s ar.claw matches 1 run function %s" % F_("cd/last"),\n', '')
    sim = MoneySim(mp, auto=R1_MAX, order="after")
    p = sim.player(adv=[GYM8])
    rank1_win(sim, p)
    assert sim.bal(p) != R1, "dropping the clear-up's second look went unnoticed"


def test_mutation_no_snapshot_is_caught():
    mp = _mutant_pack('        "function %s {x:\\"\\"}" % F_("cd/snap"),\n        "runmolang',
                      '        "runmolang')
    sim = MoneySim(mp, auto=R1_MAX, order="before")
    p = sim.player(adv=[GYM8])
    rank1_win(sim, p)
    assert sim.bal(p) != R1, "dropping the pre-battle snapshot went unnoticed"


def test_mutation_a_tighter_bound_is_caught():
    mp = _mutant_pack("level_sum * level_sum // 10 * 3 * mult_pm", "level_sum * level_sum // 10 * 2 * mult_pm")
    sim = MoneySim(mp, auto=R1_MAX, order="before")
    p = sim.player(adv=[GYM8])
    rank1_win(sim, p)
    assert sim.bal(p) != R1, "a bound under the jar's maximum went unnoticed"


def test_mutation_every_win_paying_in_full_is_caught():
    mp = _mutant_pack('"execute if score @s ar.first matches 1 run return run function %s" % F_("purse_full")',
                      '"return run function %s" % F_("purse_full")')
    sim = MoneySim(mp)
    p = repeat_player(sim)
    sim.click(p, "floor_ring")
    bout(sim, p)
    assert sim.bal(p) != REP, "a cleared rank paying the full purse went unnoticed"


def test_mutation_no_daily_cap_is_caught():
    mp = _mutant_pack('            "scoreboard players add @s ar.rday 1",\n', '            "scoreboard players add @s ar.rday 0",\n')
    sim = MoneySim(mp)
    p = repeat_player(sim)
    for _ in range(REP_WINS + 1):
        sim.click(p, "floor_ring")
        bout(sim, p, True)
        bout(sim, p, False)
    assert sim.bal(p) != REP * REP_WINS, "an uncapped repeat went unnoticed"
