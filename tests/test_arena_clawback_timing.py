"""Heaven's Arena's clawback of CobbleDollars' own NPC-win payout, against the SERVER TICK (review N143 audit, 2026-10-08).

Written by an independent auditor of commit 3aaa71e (tools/arena_runtime.py: the per-tick baseline, cd/first, cd/last,
#cb_first, cd_least). It did not build the feature and takes nothing from the generator for an expectation.

What is reused: tests/test_arena_runtime_build.py's command model (`M.Sim`), for vanilla command semantics only --
scoreboard arithmetic, `execute`, macros, `return`, and CobbleDollars' `query|give|remove` (cited there). What is this
file's own, and is the point of it:

  * the PHASES of one server tick (MinecraftServer.tickServer, vanilla 1.21.1): the #tick functions run at its start;
    then the levels and other server-side work ("in tick"); then Fabric END_SERVER_TICK, where Cobblemon's battle tick
    emits BATTLE_VICTORY and BOTH handlers run back to back, in an order the jars do not fix (`order`). Player
    commands and packets (`cobbledollars pay`, a shop trade, a click) run BETWEEN ticks (ASSUMED, as the data's
    known_edges says, until EXP-060 step 8 measures it).
  * CobbleDollars' handler, from the jar's bytecode (CobbleDollars-fabric-2.0.0+Beta-5.1+1.21.1.jar,
    CobbleDollarsEventsKt.battleVictory 370-567, javap 2026-10-08): B = max(1, (int)(5*S (as double) * sum(L/50.0)))
    summed in team order; amount = B + method_43051(B/2, 2B) (lower end inclusive under either reading; the top is
    2B inclusive, the worst case); credit = new BigDecimal(String.valueOf(amount * multiplier)).toBigInteger(); it
    credits only when earnCobbleDollarsFromNPC is true. Levels from Cobblemon-fabric-1.8.0 PoolPartyProvider
    (javap): npcLevel + IntRange(0, levelVariation).random(), both ends inclusive.
  * `cobbledollars pay` from the same jar's CobbleDollarsCommand.pay: refused when the amount exceeds the payer's
    balance, else moved whole. A shop purchase is modelled as a debit refused when unaffordable (ASSUMED: the merchant
    screen was not disassembled; to the clawback it is the same balance delta as a pay-away).

"kept" below is what an arena win left the player beyond the arena's own `cobbledollars give` and the outside
transfers: 0 means CobbleDollars' payout was taken back exactly and nothing else was.

A strict xfail is a defect found and reported, not fixed (the auditor does not edit the builder).

NOT covered (a server, experiments/EXP-060-arena-payout): which handler really runs first; that player packets never
run inside a tick; that a client can send `/cobbledollars pay` inside the one ~50 ms phase after a win; the merchant
screen's own debit; server-side credits from other packs inside the win's own tick (none found in tools/ that a player
can trigger from the arena, not proven).
"""
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("arena_build_model_timing", ROOT / "tests" / "test_arena_runtime_build.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
AR = M.AR
CD_CFG = json.loads((ROOT / "modpack" / "config" / "cobbledollars" / "common.json").read_text(encoding="utf-8"))
MULT = CD_CFG["cobbleDollarsIncomeMultiplier"]
ORDERS = ["cd_first", "cb_first"]


# ------------------------------------------------------------------ the jar's payout, typed from the bytecode

def jar_b(levels):
    s, d = 0, 0.0
    for lv in levels:
        s += lv
        d += lv / 50.0
    return max(1, int(float(5 * s) * d))


def jar_credit(levels, draw):
    b = jar_b(levels)
    amount = b + (2 * b if draw == "max" else b // 2)
    return int(Decimal(repr(float(amount) * MULT)))


def team(pack, npc, extreme):
    """The levels CobbleDollars sums for this spawned opponent: its class file and its spawn level only."""
    cls = json.loads(json.dumps(pack["data/cobblers/npcs/%s.json" % npc.cls.split(":")[1]]))
    party = cls["party"]
    if party["type"] == "pool":
        var = party["pool"][0].get("levelVariation", 0)
        return [npc.level + (var if extreme == "max" else 0)] * int(party["maxPokemon"])
    return [int(p.split("level=")[1].split(" ")[0]) for p in party["pokemon"]]


# ------------------------------------------------------------------ the server around the pack, phase by phase

class World(M.Sim):
    def __init__(self, pack, order, cd_npc=True):
        self.order, self.cd_npc = order, cd_npc
        self.given, self.outside = {}, {}
        super().__init__(pack)

    def command(self, line, ctx):
        t = line.split(" ")
        if t[:2] == ["cobbledollars", "give"]:
            (e,) = self.select(t[2], ctx)
            self.given[e.uuid] = self.given.get(e.uuid, 0) + int(t[3])
        return super().command(line, ctx)

    def bal(self, p):
        return self.money.get(p.uuid, 0)

    # between ticks: a player's own command or packet
    def pay(self, a, b, n):
        if n < 1 or n > self.bal(a):
            return False                                 # CobbleDollarsCommand.pay: pay.fail, nothing moves
        self.money[a.uuid] = self.bal(a) - n
        self.money[b.uuid] = self.bal(b) + n
        self.outside[a.uuid] = self.outside.get(a.uuid, 0) - n
        self.outside[b.uuid] = self.outside.get(b.uuid, 0) + n
        return True

    def shop(self, a, price):
        if price > self.bal(a):
            return False
        self.money[a.uuid] = self.bal(a) - price
        self.outside[a.uuid] = self.outside.get(a.uuid, 0) - price
        return True

    # END_SERVER_TICK of the tick whose start has just run: the battle ends, both handlers answer BATTLE_VICTORY
    def end_of_tick(self, p, won, credit):
        def cobbledollars():
            if won and self.cd_npc:
                self.money[p.uuid] = self.bal(p) + credit
        handlers = [cobbledollars, lambda: self.result(p, won)]
        for h in (handlers if self.order == "cd_first" else handlers[::-1]):
            h()

    def offline(self, p):
        self.ents.remove(p)

    def online(self, p):
        self.ents.append(p)
        self.scores[(p.uuid, "ar.left")] = (self.get(p.uuid, "ar.left") or 0) + 1   # minecraft.leave_game

    def kept(self, p, start):
        return self.bal(p) - start - self.given.get(p.uuid, 0) - self.outside.get(p.uuid, 0)


def pack_now():
    return AR.files(M.FIXTURE)


@pytest.fixture(scope="module")
def pack():
    return pack_now()


def world(pack, order, start=50000, **kw):
    w = World(pack, order, **kw)
    p = w.player(adv=[M.GYM8])
    mate = w.player(pos=(3000, 20, 3000))                # a teammate far from every venue, never in a bout
    w.money[p.uuid], w.money[mate.uuid] = start, 1000000
    return w, p, mate


def bout(w, p, *, draw="max", extreme=None, during=None, in_tick=None, window=None, after=None, won=True,
         battle_ticks=6, venue="floor_ring"):
    """One bout, phase by phase. `during`: between two ticks mid-battle (a tick start follows before the result);
    `in_tick`: inside the win's own tick, after its #tick functions; `window`: the one inter-tick phase straight after
    the win; `after`: between ticks later in the clear-up. Returns CobbleDollars' credit for this win."""
    n0 = len(w.started)
    w.click(p, venue)
    for _ in range(AR.GO_TICKS + 2):
        if len(w.started) > n0:
            break
        w.tick(1)
    assert len(w.started) > n0, "the bout never started"
    (npc,) = [e for e in w.mine(p) if "cobblers_arena_done" not in e.tags]
    credit = jar_credit(team(w.pack, npc, extreme or draw), draw)
    for i in range(battle_ticks):
        if during and i == battle_ticks // 2:
            during()
        w.tick(1)
    if in_tick:
        in_tick()
    w.end_of_tick(p, won, credit)
    if window:
        window()
    w.tick(1)
    if after:
        after()
    w.tick(AR.END_TICKS)
    assert w.sc(p, "ar.live") == 0, "the run did not end"
    return credit


def _w(pack, order, **kw):
    w, p, mate = world(pack, order, **kw)
    w.pack = pack
    return w, p, mate


def learned(w, p):
    """An honest win first, so the callback-first order has seen a full payout this boot (#cb_first)."""
    bout(w, p)
    return w.bal(p)


def bounds(w, p):
    return w.sc(p, "ar.cmin"), w.sc(p, "ar.cmax")


# ------------------------------------------------------------------ closed: the per-tick baseline

# Protects: an honest arena win keeps none of CobbleDollars' payout, whichever handler runs first, at both ends of its
# random credit. If removed, the arena could again pay twice: its purse and CobbleDollars' quadratic payout.
@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("draw", ["min", "max"])
def test_an_honest_win_keeps_none_of_the_payout(pack, order, draw):
    w, p, _m = _w(pack, order)
    credit = bout(w, p, draw=draw)
    assert w.kept(p, 50000) == 0 and sum(w.removed) == credit


# Protects: money a teammate moves DURING the battle (between ticks, a tick start before the result) is never taken
# and never shelters the payout, in either order, gift or pay-away, small or larger than the bound. If removed, the
# per-tick re-read of ar.bal (tick's cd/snap line) could go and a teammate's gift would be taken with the payout.
@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("amount", [1000, 200000, -1000, "all"])
def test_money_moved_during_the_battle_is_never_measured(pack, order, amount):
    w, p, mate = _w(pack, order)

    def move():
        if amount == "all":
            assert w.pay(p, mate, w.bal(p))
        elif amount > 0:
            assert w.pay(mate, p, amount)
        else:
            assert w.pay(p, mate, -amount)
    bout(w, p, during=move)
    assert w.kept(p, 50000) == 0


# Protects: money moved later in the clear-up (after the next tick's look) is never taken. If removed, a look that
# ran past the tick after the win would take a teammate's gift.
@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("amount", [1000, -1000])
def test_money_moved_after_the_next_tick_is_never_measured(pack, order, amount):
    w, p, mate = _w(pack, order)
    bout(w, p, after=lambda: w.pay(mate, p, amount) if amount > 0 else w.pay(p, mate, -amount))
    assert w.kept(p, 50000) == 0


# Protects: with CobbleDollars' handler first, the payout is taken at the callback, inside the same END_SERVER_TICK,
# so the inter-tick phase after the win holds no measured money: a gift there is not taken, a pay-away there (even
# the whole balance, or a shop purchase) shelters nothing. If removed, a return to "always look again later" (the
# design before N143) would reopen both.
@pytest.mark.parametrize("act", ["gift", "pay_some", "pay_all", "shop"])
def test_with_cobbledollars_first_the_window_after_the_win_is_closed(pack, act):
    w, p, mate = _w(pack, "cd_first")
    learned(w, p)
    start = w.bal(p)
    w.given, w.outside, w.removed = {}, {}, []

    def window():
        {"gift": lambda: w.pay(mate, p, 3000), "pay_some": lambda: w.pay(p, mate, 3000),
         "pay_all": lambda: w.pay(p, mate, w.bal(p)), "shop": lambda: w.shop(p, 3000)}[act]()
    bout(w, p, draw="min", window=window)
    assert w.kept(p, start) == 0


# Protects: a loss, a flee/forfeit (no result) and a disconnect mid-bout take nothing, whatever money moves in any
# phase. If removed, a clawback armed for a bout that paid nothing could take the player's own money.
@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("how", ["loss", "forfeit", "disconnect"])
def test_a_bout_without_a_win_takes_nothing(pack, order, how):
    w, p, mate = _w(pack, order)
    learned(w, p)
    w.removed = []
    if how == "loss":
        bout(w, p, won=False, during=lambda: w.pay(mate, p, 7000), in_tick=lambda: None,
             window=lambda: w.pay(mate, p, 7000), after=lambda: w.pay(p, mate, 500))
    else:
        w.click(p, "floor_ring")
        w.tick(AR.GO_TICKS + 1)
        w.pay(mate, p, 7000)
        w.tick(2)
        (npc,) = w.mine(p)
        w.in_battle -= {p.uuid, npc.uuid}                 # the battle ends with no BATTLE_VICTORY
        if how == "disconnect":
            w.offline(p)
            w.tick(AR.SWEEP_TICKS * 3)
            w.online(p)
        w.pay(mate, p, 7000)
        w.tick(AR.SWEEP_TICKS * (AR.IDLE_SWEEPS + 2))
        assert w.sc(p, "ar.live") == 0, "the abandoned bout never ended"
    assert w.removed == [], "took %s from a bout CobbleDollars paid nothing for" % w.removed


# Protects: a player who disconnects in the phase straight after a callback-first win still has the payout taken
# when they return (the tick's cd/last line runs for them first). If removed, logging out on the win would keep it.
def test_a_disconnect_straight_after_a_win_still_gives_the_payout_back(pack):
    w, p, _m = _w(pack, "cb_first")
    w.click(p, "floor_ring")
    w.tick(AR.GO_TICKS + 1)
    (npc,) = w.mine(p)
    credit = jar_credit(team(pack, npc, "max"), "max")
    w.tick(3)
    w.end_of_tick(p, True, credit)
    w.offline(p)
    w.tick(200)
    w.online(p)
    w.tick(AR.END_TICKS + 2)
    assert w.kept(p, 50000) == 0 and sum(w.removed) == credit


# Protects: two players winning in the same tick are settled each against their own baseline. If removed, a shared
# temporary (#now) or baseline read for the wrong player would move one player's payout onto the other.
@pytest.mark.parametrize("order", ORDERS)
def test_two_winners_in_one_tick_are_settled_apart(pack, order):
    w, a, _m = _w(pack, order)
    b = w.player(pos=tuple(M.VENUE["door_ring"]["challenger_mark"][:3]), adv=[M.GYM8])
    w.scores[(b.uuid, "ar.rank")] = 4
    w.money[b.uuid] = 80000
    for q, venue in ((a, "floor_ring"), (b, "door_ring")):
        w.click(q, venue)
    w.tick(AR.GO_TICKS + 3)
    credits = {}
    for q in (a, b):
        (npc,) = w.mine(q)
        credits[q.uuid] = jar_credit(team(pack, npc, "min"), "min")
    for q in (a, b):
        w.end_of_tick(q, True, credits[q.uuid])
    w.tick(AR.END_TICKS + 2)
    assert (w.kept(a, 50000), w.kept(b, 80000)) == (0, 0)


# Protects: a restart (load) forgets the learned order, and the first callback-first win after it is still taken in
# full from its own gain. If removed, a stale #cb_first could survive a mod update that changed the handler order.
def test_after_a_restart_an_honest_win_is_still_taken_in_full(pack):
    w, p, _m = _w(pack, "cb_first")
    learned(w, p)
    w.call("arena/load", None)
    assert w.get("#cb_first", "ar.t") == 0
    start = w.bal(p)
    w.given, w.removed = {}, []
    credit = bout(w, p, draw="min")
    assert w.kept(p, start) == 0 and sum(w.removed) == credit


# Protects: with earnCobbleDollarsFromNPC false CobbleDollars pays no arena win and the arena takes nothing, even a
# gift at least the usual least payout landing in the window after a callback-first win. If removed, the generator's
# cd_pays_npc_wins check could go and a teammate's gift would be taken as a payout that never came.
def test_with_npc_pay_off_nothing_is_ever_taken(tmp_path):
    cfg = dict(CD_CFG, earnCobbleDollarsFromNPC=False)
    path = tmp_path / "common.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    pk = AR.files(M.FIXTURE, cd_config=path)
    for order in ORDERS:
        w, p, mate = _w(pk, order, cd_npc=False)
        bout(w, p, during=lambda: w.pay(mate, p, 20000), window=lambda: w.pay(mate, p, 20000))
        assert w.removed == [], (order, w.removed)


# Protects: the counters EXP-060 reads to learn the handler order count the right look. If removed, the experiment
# could report the order backwards.
@pytest.mark.parametrize("order", ORDERS)
def test_the_order_counters_name_the_look_that_took_the_payout(pack, order):
    w, p, _m = _w(pack, order)
    bout(w, p)
    assert (w.get("#cd_first", "ar.t") or 0, w.get("#cd_last", "ar.t") or 0) == \
        ((1, 0) if order == "cd_first" else (0, 1))


# ------------------------------------------------------------------ bounded: the callback-first window

# Protects the builder's stated bound: with the callback first, a teammate's gift in the phase after the win is taken
# only up to ar.cmax minus the payout. If removed, losing the clamp (`#now < ar.cmax`) would take a gift whole.
def test_callback_first_a_gift_in_the_window_is_taken_at_most_to_the_bound(pack):
    w, p, mate = _w(pack, "cb_first")
    learned(w, p)
    start = w.bal(p)
    w.given, w.outside = {}, {}
    credit = bout(w, p, draw="min", window=lambda: w.pay(mate, p, 200000))
    cmin, cmax = bounds(w, p)
    assert -w.kept(p, start) == cmax - credit


# The gift itself is still taken (the bound above, up to ar.cmax - payout: rank 1 up to 5,862). Reported, not
# accepted: data/arena_fights.json known_edges names it; the owner has not ruled.
@pytest.mark.xfail(strict=True, reason="defect (known, bounded): callback first, a gift in the phase after the win is "
                                       "taken up to ar.cmax - payout")
def test_callback_first_a_gift_in_the_window_is_never_taken(pack):
    w, p, mate = _w(pack, "cb_first")
    learned(w, p)
    start = w.bal(p)
    w.given, w.outside = {}, {}
    bout(w, p, draw="min", window=lambda: w.pay(mate, p, 3000))
    assert w.kept(p, start) == 0


# Protects the builder's stated bound for a PARTIAL pay-away once the order is learned: the player keeps at most the
# payout minus ar.cmin. If removed, losing the learned floor (`#now > ar.cmin` in cd/last_take) would let a pay-away
# of payout - cmin + 1 or more keep that much.
@pytest.mark.parametrize("act", ["pay", "shop"])
def test_callback_first_a_partial_pay_away_keeps_at_most_payout_minus_cmin(pack, act):
    w, p, mate = _w(pack, "cb_first")
    learned(w, p)
    start = w.bal(p)
    w.given, w.outside = {}, {}
    credit = bout(w, p, draw="max", window=lambda: (w.pay(p, mate, 9000) if act == "pay" else w.shop(p, 9000)))
    cmin, _cmax = bounds(w, p)
    assert 0 < w.kept(p, start) <= credit - cmin


# NEW (this audit): the bound above does not hold for a pay-away that empties the account. cd/last_take asks for at
# least ar.cmin, but `cobbledollars remove` takes min(amount, balance) (CobbleDollarsCommand.remove, javap), so a
# player who pays their WHOLE balance to a teammate in the phase after a callback-first win keeps the WHOLE payout,
# learned order or not: up to ar.cmax a win (rank 1 10,965; rank 8 exam 74,925; streak 6 x L95-100 135,000).
@pytest.mark.xfail(strict=True, reason="defect (new): callback first, emptying the balance in the phase after the win "
                                       "keeps the whole payout; remove is clamped to the balance")
def test_callback_first_emptying_the_balance_in_the_window_keeps_at_most_payout_minus_cmin(pack):
    w, p, mate = _w(pack, "cb_first")
    learned(w, p)
    start = w.bal(p)
    w.given, w.outside = {}, {}
    credit = bout(w, p, draw="max", window=lambda: w.pay(p, mate, w.bal(p)))
    cmin, _cmax = bounds(w, p)
    assert w.kept(p, start) <= credit - cmin, "kept %d of a %d payout" % (w.kept(p, start), credit)


# NEW (this audit): "the whole payout on the first such win after a restart" (known_edges) is every such win, not the
# first: #cb_first is learned only from a deferred gain of at least ar.cmin, which a player who pays away in the
# window never shows. Until someone wins honestly in that boot, every callback-first pay-away keeps the whole payout.
@pytest.mark.xfail(strict=True, reason="defect (new): unlearned, every pay-away win keeps the whole payout, not only "
                                       "the first after a restart")
def test_callback_first_only_the_first_pay_away_after_a_restart_keeps_the_payout(pack):
    w, p, mate = _w(pack, "cb_first")
    kept = []
    for _ in range(2):
        start = w.bal(p)
        w.given, w.outside = {}, {}
        credit = bout(w, p, draw="max", window=lambda: w.pay(p, mate, 9000))
        cmin, _cmax = bounds(w, p)
        kept.append(w.kept(p, start))
    assert kept[1] <= credit - cmin, "the second pay-away win kept %d" % kept[1]


# Known (data/arena_fights.json known_edges, "a gain of at least ar.cmin from a server-side credit in the win's own
# tick"): with the callback first, a server-side credit of at least ar.cmin landing after the #tick functions and
# before END_SERVER_TICK is taken as the payout, and the payout that follows is kept. Rank 1: a 6,000 credit is taken,
# a 5,103-10,965 payout kept. No player-triggered source of such a credit was found in tools/ (not proven).
@pytest.mark.xfail(strict=True, reason="defect (known): callback first, an in-tick credit >= ar.cmin is taken in place "
                                       "of the payout")
def test_callback_first_an_in_tick_credit_is_never_taken_for_the_payout(pack):
    w, p, mate = _w(pack, "cb_first")
    bout(w, p, draw="min", in_tick=lambda: w.pay(mate, p, 6000))
    assert w.kept(p, 50000) == 0


# ------------------------------------------------------------------ the bounds, against the jar, every opponent

def _opponents():
    fights = M.FIGHTS
    exams = {e["rank"]: e for e in fights["rank_up_fights"]}
    out = []
    for r in fights["ranks"]:
        if r["format"] == "streak":
            continue
        n, m, top = r["rank"], r["members"], r["levels"]["top"]
        out.append(("pool_%d" % n, 1, n, 0, [top - (m - 1)] * m, [top] * m))
        ex = exams[n]
        for leg, tid in enumerate(ex["legs"] if "legs" in ex else [ex["trainer"]]):
            lv = [x["level"] for x in M.TRAINERS[tid]["team"]]
            out.append(("exam_%d_%d" % (n, leg), 2, n, leg, lv, lv))
    return out


def _bound(pack, kind, rank, leg):
    sim = M.Sim(pack)
    p = sim.player(adv=[M.GYM8])
    for k, v in (("ar.kind", kind), ("ar.cur", rank), ("ar.leg", leg)):
        sim.scores[(p.uuid, k)] = v
    sim.call("arena/cd/bound", p)
    return sim.sc(p, "ar.cmin"), sim.sc(p, "ar.cmax")


# Protects: ar.cmin is never above the least CobbleDollars can credit for that opponent. If removed, an honest
# CobbleDollars-first win below a too-high cmin would be deferred and, unlearned, kept whole.
@pytest.mark.parametrize("case", _opponents(), ids=lambda c: c[0])
def test_cmin_is_never_above_the_jars_least_credit(pack, case):
    _id, kind, rank, leg, lo_lv, _hi = case
    assert _bound(pack, kind, rank, leg)[0] <= jar_credit(lo_lv, "min")


# The rank 3 pool (3 x L58-60): S = 180, and 3 x (60/50.0) sums to 3.5999999999999996 in a double, so the jar's B is
# 3239, its top credit 12,146; cd_bound uses S*S//10 = 3240 and allows 12,150. NEW (this audit): $4 of a player's own
# money can go with the payout when a gift lands in the window. Every other opponent's bound is exact.
_CMAX_OVER = {"pool_3"}


# Protects: ar.cmax is never above the most CobbleDollars can credit for that opponent (purse_policy: "never more than
# the most CobbleDollars could credit"). If removed, a bound with slack would take the player's own money with it.
@pytest.mark.parametrize("case", [pytest.param(c, marks=pytest.mark.xfail(
    strict=True, reason="defect (new): cd_bound ignores the double's rounding when 10 divides S")) if c[0] in _CMAX_OVER
    else c for c in _opponents()], ids=lambda c: c[0])
def test_cmax_is_never_above_the_jars_most_credit(pack, case):
    _id, kind, rank, leg, _lo, hi_lv = case
    assert _bound(pack, kind, rank, leg)[1] <= jar_credit(hi_lv, "max")


# Protects: the streak's runtime bounds (cd/bound_streak) bracket exactly the team streak/start spawns, at every
# streak length up to past the last growth step. If removed, a streak length whose bound missed its team would keep
# part of the payout (cmax low) or defer and keep all of it (cmin high).
def test_the_streak_bounds_bracket_the_spawned_team_at_every_length(pack):
    sim = M.Sim(pack)
    p = sim.player(adv=[M.GYM8, M.LANCE, M.CHAMP])
    var = {}
    for k, v in pack.items():
        if "/npcs/arena_streak_m" in k:
            var[int(k.split("_m")[-1].split(".")[0])] = v["party"]["pool"][0]["levelVariation"]
    bad = []
    for s in range(0, 120):
        sim.scores[(p.uuid, "ar.streak")] = s
        sim.scores[(p.uuid, "ar.kind")] = 3
        sim.call("arena/streak/start", p)
        args = sim.storage["cobblers:arena"]["args"]
        m, sl = int(args["cls"].split("_m")[-1]), args["level"]
        lo, hi = jar_credit([sl] * m, "min"), jar_credit([sl + var[m]] * m, "max")
        sim.call("arena/cd/bound", p)
        if not (sim.sc(p, "ar.cmin") <= lo and sim.sc(p, "ar.cmax") == hi):
            bad.append((s, m, sl, lo, hi, sim.sc(p, "ar.cmin"), sim.sc(p, "ar.cmax")))
    assert bad == []


# ------------------------------------------------------------------ mutants of the GENERATOR (data untouched)

def _mut(old, new):
    return M.ar_mutant(old, new)


# the per-tick baseline gone: a gift during the battle is taken with the payout
def test_mutation_no_per_tick_baseline_is_caught():
    mp = _mut('    "execute as @a[scores={ar.live=1}] if score @s ar.bal matches -2147483648.. unless score @s ar.claw '
              'matches 1 "\n        "run function %s {x:\\"\\"}" % F_("cd/snap"),\n', "")
    # draw "min" keeps the gift under the cmax clamp; 6000 is over rank 1's cmin, so callback-first cannot defer it
    for order in ORDERS:
        w, p, mate = _w(mp, order)
        bout(w, p, draw="min", during=lambda: w.pay(mate, p, 6000))
        assert w.kept(p, 50000) != 0, "dropping the per-tick re-read went unnoticed (%s)" % order


# cd/first always deferring (the pre-N143 design): with CobbleDollars first, a pay-away after the win keeps payout
def test_mutation_always_defer_is_caught(pack):
    mp = _mut('"execute if score #now ar.t < @s ar.cmin run return run scoreboard players set @s ar.claw 1",',
              '"return run scoreboard players set @s ar.claw 1",')
    w, p, mate = _w(mp, "cd_first")
    bout(w, p, window=lambda: w.pay(p, mate, w.bal(p)))
    assert w.kept(p, 50000) != 0, "always deferring went unnoticed"


# the clamp to ar.cmax gone: a gift in the callback-first window is taken whole
def test_mutation_no_cmax_clamp_is_caught():
    mp = _mut('"scoreboard players operation #now ar.t < @s ar.cmax",', '"# no clamp",')
    w, p, mate = _w(mp, "cb_first")
    learned(w, p)
    start = w.bal(p)
    w.given, w.outside = {}, {}
    credit = bout(w, p, draw="min", window=lambda: w.pay(mate, p, 200000))
    assert -w.kept(p, start) > bounds(w, p)[1] - credit, "dropping the cmax clamp went unnoticed"


# the learned floor gone: a pay-away of more than payout - cmin keeps that much
def test_mutation_no_learned_floor_is_caught():
    mp = _mut('"execute if score #cb_first ar.t matches 1 run scoreboard players operation #now ar.t > @s ar.cmin",',
              '"# no floor",')
    w, p, mate = _w(mp, "cb_first")
    learned(w, p)
    start = w.bal(p)
    w.given, w.outside = {}, {}
    credit = bout(w, p, draw="max", window=lambda: w.pay(p, mate, 9000))
    assert w.kept(p, start) > credit - bounds(w, p)[0], "dropping the learned floor went unnoticed"


# the next tick's look gone: a callback-first payout is kept
def test_mutation_no_next_tick_look_is_caught():
    mp = _mut('        "execute as @a[scores={ar.claw=1}] run function %s" % F_("cd/last"),\n', "")
    w, p, _m = _w(mp, "cb_first")
    bout(w, p)
    assert w.kept(p, 50000) != 0, "dropping the next tick's look went unnoticed"


# the earnCobbleDollarsFromNPC check gone: a gift is taken as a payout that never came
def test_mutation_npc_pay_flag_ignored_is_caught(tmp_path):
    cfg = dict(CD_CFG, earnCobbleDollarsFromNPC=False)
    path = tmp_path / "common.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    mod = M._mutant(M.AR_SRC, "    cd_npc = cd_pays_npc_wins(cd_config)\n", "    cd_npc = True\n",
                    "arena_runtime_timing_mutant", ROOT / "tools" / "arena_runtime.py")
    mp = mod.files(M.FIXTURE, cd_config=path)
    w, p, mate = _w(mp, "cb_first", cd_npc=False)
    bout(w, p, window=lambda: w.pay(mate, p, 20000))
    assert w.removed != [], "ignoring earnCobbleDollarsFromNPC went unnoticed"
