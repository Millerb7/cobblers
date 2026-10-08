"""Heaven's Arena's clawback of CobbleDollars' own NPC-win payout, at its edges (unit ARENACAP, independent audit).

Written by the auditor of tools/arena_runtime.py's money (it did not build the feature). The generated functions run in
tests/test_arena_runtime_build.py's command model, whose `cobbledollars query|give|remove` and `time query gametime`
follow the jar's and vanilla's own rules (cited there). CobbleDollars' credit for a win is computed HERE from the
bytecode formula (CobbleDollarsEventsKt.battleVictory: B = max(1, int(5 * S * sum(L / 50.0))), amount = B +
nextIntBetweenInclusive(B / 2, 2B), floor(amount * cobbleDollarsIncomeMultiplier)) and never from tools/arena_runtime.

The question each test answers: can the arena take money that was NOT CobbleDollars' payout, or leave some of that
payout with the player? Both handlers answer the same BATTLE_VICTORY at Priority.NORMAL (Cobblemon's CallbackHandler
and CobbleDollars.init both subscribe without a priority), so which runs first is mod init order: every test runs
both orders. A strict xfail is a defect found and reported, not fixed (the auditor does not edit the builder): it
turns red the day the defect is fixed, so the marker is removed then.

Not covered (needs a server, experiments/EXP-060-arena-payout): which handler runs first; whether a player can type
`/cobbledollars pay` while Cobblemon's battle screen is open; that `execute store result ... run cobbledollars query`
stores the balance.
"""
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("arena_build_model_edges", ROOT / "tests" / "test_arena_runtime_build.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
AR = M.AR
POLICY = M.FIGHTS["prizes"]["purse_policy"]
R1 = M.RANKS[1]
MULT = Decimal(str(json.loads((ROOT / "modpack" / "config" / "cobbledollars" / "common.json")
                              .read_text(encoding="utf-8"))["cobbleDollarsIncomeMultiplier"]))


def credit(levels, top_draw):
    """CobbleDollars' credit for one NPC loser with these levels; top_draw picks nextIntBetweenInclusive's end."""
    b = max(1, int(5 * sum(levels) * sum(lv / 50.0 for lv in levels)))
    return int(Decimal(b + (2 * b if top_draw else b // 2)) * MULT)


# rank 1's pool: `members` at the band's top at most, at top - (members - 1) at least (draw.levels)
R1_MIN = credit([R1["levels"]["top"] - (R1["members"] - 1)] * R1["members"], False)
R1_MAX = credit([R1["levels"]["top"]] * R1["members"], True)


class CD(M.Sim):
    """The model with CobbleDollars' own handler: `auto` credited to the winner before or after the arena's callback."""

    def __init__(self, pack, auto, order):
        self.auto, self.order = auto, order
        super().__init__(pack)

    def result(self, player, won):
        if won and self.order == "before":
            self.money[player.uuid] = self.money.get(player.uuid, 0) + self.auto
        super().result(player, won)
        if won and self.order == "after":
            self.money[player.uuid] = self.money.get(player.uuid, 0) + self.auto


@pytest.fixture(scope="module")
def pack():
    return AR.files(M.FIXTURE)


def first_win(pack, order, auto=R1_MIN, mid=0, post=0, start=50000):
    """A rank-1 player's first win; `mid` moves the balance during the battle (after the bout's snapshot), `post`
    inside the two seconds after the win (before the clear-up). Returns what the player kept beyond the arena's own
    purse and the outside transfer: 0 when the clawback took exactly CobbleDollars' payout."""
    sim = CD(pack, auto, order)
    p = sim.player(adv=[M.GYM8])
    sim.money[p.uuid] = start
    sim.click(p, "floor_ring")
    sim.tick(AR.GO_TICKS)
    assert sim.started, "the bout never started"
    sim.money[p.uuid] += mid
    sim.result(p, True)
    sim.money[p.uuid] += post
    sim.tick(AR.END_TICKS)
    assert sim.sc(p, "ar.live") == 0
    return sim.money[p.uuid] - start - R1["purse"]["typical"] - mid - post, sim


ORDERS = ["before", "after"]


# Protects: the arena's purse is the only money an arena win leaves, whichever handler runs first and at either end of
# CobbleDollars' random credit. If removed, a win could again pay twice (the purse and CobbleDollars' quadratic pay).
@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("auto", [R1_MIN, R1_MAX], ids=["min_credit", "max_credit"])
def test_an_arena_win_keeps_none_of_cobbledollars_payout(pack, order, auto):
    kept, sim = first_win(pack, order, auto=auto)
    assert kept == 0 and sum(sim.removed) == auto


# Protects: the clawback never takes the player's OWN money. FOUND 2026-10-10 (ARENACAP audit): cd/settle
# (tools/arena_runtime.py:910-924) takes the whole balance gain since the bout's snapshot (bout/begin, :683), up to the
# bound, so a teammate's `cobbledollars pay` (permission level NONE) landing during the battle or in the two seconds
# after the win is removed with the payout. data/arena_fights.json purse_policy.cobbledollars_auto_payout.known_edges
# names the first half; the owner has not accepted it.
# 2026-10-08 (N143, the builder; marks only, the assertion untouched): the xfail is lifted for the two cases the
# per-tick baseline and the next-tick second look close -- the callback first with money arriving before it, and
# CobbleDollars first with money arriving after it. It stays on the two that read the window the code still measures.
_OPEN = pytest.mark.xfail(strict=True, reason="defect: a transfer to the player inside the clawback window is clawed back")


@pytest.mark.parametrize("order,when", [
    pytest.param("before", "mid", marks=_OPEN, id="mid-before"),
    pytest.param("after", "mid", id="mid-after"),
    pytest.param("before", "post", id="post-before"),
    pytest.param("after", "post", marks=_OPEN, id="post-after")])
def test_a_transfer_to_the_player_inside_the_window_is_never_clawed_back(pack, order, when):
    kept, _sim = first_win(pack, order, **{when: 1000})
    assert kept == 0, "the player lost %d of their own money" % -kept


# Protects: paying money away cannot shelter CobbleDollars' payout from the clawback where the design holds today: a
# payout taken at the callback is gone before a later debit, and a debit before the callback is re-baselined before a
# late payout. If removed, a regression in either look would let the payout stay.
@pytest.mark.parametrize("order,when", [("before", "post"), ("after", "mid")])
def test_paying_away_outside_the_open_window_keeps_none_of_the_payout(pack, order, when):
    kept, _sim = first_win(pack, order, **{when: -R1_MIN})
    assert kept == 0


# Protects: the same, where it does NOT hold. FOUND 2026-10-10: the clawback reads a balance DELTA, so a debit in the
# window it measures shrinks it: CobbleDollars first -> a `cobbledollars pay` away during the battle; the arena's
# callback first -> a pay away in the 2 s (END_TICKS, :106) before the clear-up's second look (`after`, :979). The
# player keeps the whole payout, a partner pays it back, on every win -- including repeats past the daily cap. The
# payout is many times the purse (rank 1 up to R1_MAX against a 2,200 purse; rank 4 up to about 23,000).
@pytest.mark.xfail(strict=True, reason="defect: a pay-away inside the open window keeps CobbleDollars' payout")
@pytest.mark.parametrize("order,when", [("before", "mid"), ("after", "post")])
def test_paying_away_inside_the_open_window_keeps_none_of_the_payout(pack, order, when):
    kept, _sim = first_win(pack, order, **{when: -R1_MIN})
    assert kept == 0, "the player kept %d of CobbleDollars' %d" % (kept, R1_MIN)


# Protects: the daily cap's clock is game time: `time set` / `time add` (day time only, vanilla TimeCommand) never
# reset it, and only the next period of game time does. If removed, a cap keyed on the day clock (which `time set`
# rewinds, and whose 0..23999 value never leaves period 0) would pass.
def test_the_repeat_cap_follows_game_time_and_survives_time_set(pack):
    sim = M.Sim(pack)
    p = sim.player(adv=[M.GYM8])
    sim.scores[(p.uuid, "ar.rank")] = 4                 # the floor ring then offers rank 3: a cleared rank
    sim.gametime = POLICY["day_ticks"] * 5 + 10

    def win():
        before = sim.money.get(p.uuid, 0)
        sim.click(p, "floor_ring")
        M._bout(sim, p)
        if sim.sc(p, "ar.live"):                        # rank 3 is a gauntlet: end the run after one leg
            sim.tick(AR.GO_TICKS)
            sim.result(p, False)
            sim.tick(AR.END_TICKS)
        return sim.money.get(p.uuid, 0) - before
    paid = [win() for _ in range(POLICY["daily_cap_wins"] + 1)]
    assert paid == [POLICY["repeat_purse"]] * POLICY["daily_cap_wins"] + [0]
    sim.command("time set 0", {"s": None, "pos": [0, 0, 0]})
    sim.command("time add 24000", {"s": None, "pos": [0, 0, 0]})
    assert win() == 0
    sim.gametime = POLICY["day_ticks"] * 6 + 10
    assert win() == POLICY["repeat_purse"]


# Protects: the streak's runtime bound (cd/bound_streak, scoreboard arithmetic) covers the largest streak opponent and
# does not overflow a Java int. If removed, a streak whose bound wrapped negative would take nothing back at all.
def test_the_largest_streak_bound_covers_cobbledollars_and_fits_a_score(pack):
    st = next(r for r in M.FIGHTS["ranks"] if r["format"] == "streak")
    sim = M.Sim(pack)
    p = sim.player(adv=[M.GYM8, M.LANCE, M.CHAMP])
    sim.scores[(p.uuid, "ar.kind")] = 3
    sim.scores[(p.uuid, "ar.streak")] = 10 ** 6         # past every growth step: the largest team at the cap
    sim.call("arena/cd/bound", p)
    # the data: level_max, and at_level_max "members +1 every 6 wins, to 6" -- six Pokemon at level_max
    assert st["streak"]["at_level_max"].endswith("to 6")
    top = credit([st["streak"]["level_max"]] * 6, True)
    assert 0 < top <= sim.sc(p, "ar.cmax") < 2 ** 31
