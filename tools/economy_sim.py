#!/usr/bin/env python
"""A Monte Carlo of the campaign's economy with the dungeons in it: players over hours of play, badge by badge.

Written 2026-10-09 for the owner's question "Dungeons change the economy: entry costs, held rewards, drops, the greed
ladder. Re-run the economy model with them in and tell me whether it is still where it needs to be". It SIMULATES: every
number in docs/mechanics/ECONOMY_SIM_2026-10-09.md is this tool's output, not reasoning.

WHAT IS READ FROM DATA (change the file and the result moves; tests/test_economy_sim.py mutates these):
  data/markets.json   income_basis.level_sums (every battle of every leg, Normal and Challenge), curve_rule (the fight
                      allowance and the produce allowance), every counter line (the shelf), the Beast Ball's price
  data/bank.json      what the bank pays (buys) and the declared rate_per_hour of each tier (the gathering hour)
  data/dungeons.json  the bands, clocks, sigil recipes, the greed ladder, the boss's aces, escorts and level offsets
  data/blackout.json  the flat death charge (cap x percent)
  data/produce_buyer.json, data/training_services.json, data/mining_caves.json (the seam's ore mix)
  modpack/config/cobbledollars/common.json   the income multiplier and which battles pay

THE PAYOUT (docs/research/notes/paid-services-and-npc-payouts.md B2, read from CobbleDollars' battleVictory bytecode;
VERIFIED there, the inclusive uniform draw ASSUMED there): over the losing team, levels L_i, S = sum L_i,
    B = max(1, int(5*S*sum(L_i/50)))  (= S*S//10),  amount = B + uniform_int(B//2, 2B),  credit = floor(amount * 1.25).
Each battle is DRAWN. This tool never uses the expectation to price a battle.

THE TWO DEFECTS, as they stand today (the scenario names):
  as_built   boss stages pay the NPC payout (no clawback: dungeons.json engine.clawback.status) and the TM gate's
             `recipe give @s *` opens every sigil recipe for up to recipe_sync_period_ticks (200)
  design     the contract: a dungeon win pays $0 net (the clawback works) and the window does not exist
  defect1    design + the boss payout only
  defect2    design + the recipe window only
  stands_unclawed   COUNTERFACTUAL, not a defect today: as_built plus the three stands paying the same payout. The
             stands are not built (dungeons.json status); this is what building them before the clawback would do.

WHAT IS ASSUMED (not measured anywhere; each is a named parameter, swept in the report where it matters):
  - hours: a leg's fights take effort_model.max_leg_hours (4, ASSUMED there); Victory Road 4 h, the League 2 h, the HQ tower 2 h
  - the gathering hour pays the bank's declared typical rate x U(0.7, 1.3) (the rates are ASSUMED in bank.json)
  - deaths outside dungeons: Poisson(1) a leg (2 for Challenge), each charged the flat blackout, never more than cash
  - dungeon fights: P(win a boss stage) by player type, P(win a stand) 0.97, P(a fall or other death in a run) 0.04
  - the run's time: DUNGEONS.md 4.2's required minutes (RELAYED, planning), split 7.4 : 15.2 around the seam as 4.3 worked
    for band 1, times one lognormal(0, 0.12) factor a run; the seam digs 4 blocks in 0.5 minute (4.3)
  - the seam's ore mix per band is not authored (step 6): it is data/mining_caves.json's per-reset yields scaled to 24
    blocks, bands 3-4 without diamond, bands 5-6 with face_diamonds (default 1). Vanilla drops without Fortune
  - the Night Shift is the only dungeon (D19), one run an hour of uptime (lockout_ticks 72000)
  - a player spends nothing but: the leg's Mart + ferries (curve_rule.fight_allowance), deaths, and the critical path's
    convenience lines (the curve's own ask), cheapest first. The late shelf is what is left to buy

WHAT IT DOES NOT MODEL: the items dungeons hold in escrow (gems, candies, battle items, first-clear prizes) have no
dollar value here because no counter sells them and the bank buys none (checked: no candy or gem line in the counters
except one steel gem); co-op; the Heaven's Arena purse; rematches; Cobbleverse's roaming trainers; the stands' fights
(they are in the time and the death rate, not in the payout, unless stands_unclawed).

  python tools/economy_sim.py                  # the full report (markdown) for the default seed and 300 players a cell
  python tools/economy_sim.py --runs 100 --seed 7
  python tools/economy_sim.py --json out.json
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DOC_PATHS = {
    "markets": "data/markets.json", "bank": "data/bank.json", "dungeons": "data/dungeons.json",
    "blackout": "data/blackout.json", "produce": "data/produce_buyer.json",
    "services": "data/training_services.json", "caves": "data/mining_caves.json",
    "nether_gate": "data/nether_gate.json", "key_ball": "data/key_ball.json", "entei": "data/entei_boss.json",
    "cd": "modpack/config/cobbledollars/common.json",
}

# DUNGEONS.md 4.2, "Required" column (minutes), RELAYED. Clock = ceil(required x 1.25); the test checks this against
# dungeons.json bands[].clock_s so a re-timed clock that leaves this stale is caught.
REQUIRED_MIN = {1: 22.6, 2: 24.6, 3: 25.1, 4: 27.1, 5: 29.1, 6: 31.1}
SEAM_PRE_MIN, SEAM_POST_MIN, SEAM_DIG_FREE_MIN = 7.4, 15.2, 0.5     # DUNGEONS.md 4.3 (band 1), RELAYED
BACK_WALK_MIN = 1.9                                                   # 4.3: ~630 blocks at sprint
# Vanilla 1.21.1 ore drops with no Fortune (ASSUMED here, vanilla knowledge, not read from a jar): (item, lo, hi)
ORE_DROPS = {"coal_ore": ("minecraft:coal", 1, 1), "iron_ore": ("minecraft:raw_iron", 1, 1),
             "copper_ore": ("minecraft:raw_copper", 2, 5), "lapis_ore": ("minecraft:lapis_lazuli", 4, 9),
             "redstone_ore": ("minecraft:redstone", 4, 5), "gold_ore": ("minecraft:raw_gold", 1, 1),
             "diamond_ore": ("minecraft:diamond", 1, 1)}
# DUNGEONS.md 9.2: area gems per stand by band (items; counted, never priced)
GEMS_PER_STAND = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3}
# Stand members by band (DUNGEONS.md 5.3), used only by the stands_unclawed counterfactual
STAND_MEMBERS = {1: 2, 2: 3, 3: 3, 4: 4, 5: 5, 6: 6}
# docs/mechanics/PROGRESSION_LADDER.md 4.1 (RELAYED): the cap is the next required leader's ace: 20/25/.../55 holding
# 0..7 badges; 60 holding 8 (62 after Victory Road); 100 once the Champion has fallen
CAP_BY_BADGES = {k: 20 + 5 * k for k in range(8)}
CAP_BY_BADGES[8] = 60
CHAMPION_CAP = 100
SEAM_TAKE_CANDIDATES = (4, 9, 14, 19, 24)       # the top of each ladder tier: 4 is the free tier (x1)

SCENARIOS = {
    "as_built": dict(pay_boss=True, window=True, stands=False),
    "design": dict(pay_boss=False, window=False, stands=False),
    "defect1": dict(pay_boss=True, window=False, stands=False),
    "defect2": dict(pay_boss=False, window=True, stands=False),
    "stands_unclawed": dict(pay_boss=True, window=True, stands=True),
}

PLAYER_TYPES = {
    # hours: gather hours a leg; produce: sells the allowance; runs: dungeon runs a leg; idle: AFK-farm hours a leg
    "fighter": dict(mode="normal", gather=0.0, produce=False, runs=0, take="free", idle=0, deaths=1.0, p_stage=0.88),
    "baseline": dict(mode="normal", gather=1.0, produce=True, runs=0, take="free", idle=0, deaths=1.0, p_stage=0.88),
    "steady": dict(mode="normal", gather=1.0, produce=True, runs=1, take="free", idle=0, deaths=1.0, p_stage=0.88),
    "greedy": dict(mode="normal", gather=1.0, produce=True, runs=4, take="best", idle=0, deaths=1.0, p_stage=0.92),
    "afk": dict(mode="normal", gather=1.0, produce=True, runs=0, take="free", idle=6, deaths=1.0, p_stage=0.88),
    "challenge": dict(mode="challenge", gather=1.0, produce=True, runs=1, take="free", idle=0, deaths=2.0, p_stage=0.88),
}
P_STAND, P_OTHER, TIME_SIGMA = 0.97, 0.04, 0.12
PRE_STANDS, POST_STANDS = 2, 1       # DUNGEONS.md 4.3: two stands before the seam, one after
GATHER_NOISE = (0.7, 1.3)
POST_CHAMPION_HOURS = 10
WINDOW_STAGE = "5"       # the leg a tm_gate plan change is assumed to re-sync (any; the effect is bounded by one sigil's difference)
VR_HOURS, LEAGUE_HOURS, HQ_HOURS = 4.0, 2.0, 2.0


class SimError(Exception):
    pass


def load_docs(root=ROOT):
    return {k: json.loads((Path(root) / p).read_text(encoding="utf-8")) for k, p in DOC_PATHS.items()}


# ------------------------------------------------------------------------------------------------- the world


class World:
    """Everything the sim reads, derived from the documents once. Build it from `docs` so a test can mutate a copy."""

    def __init__(self, docs, face_diamonds=1, p_stage=None):
        self.docs = docs
        d, mk, bk = docs["dungeons"], docs["markets"], docs["bank"]
        self.mult = Fraction(str(docs["cd"]["cobbleDollarsIncomeMultiplier"]))
        if docs["cd"].get("earnCobbleDollarsFromNPC") is not True:
            raise SimError("earnCobbleDollarsFromNPC is not true: no trainer pays and every figure here is void")
        if docs["cd"].get("earnCobbleDollarsFromWildPokemon") is not False:
            raise SimError("earnCobbleDollarsFromWildPokemon is not false: wild battles would pay and the model omits them")
        ib = mk["income_basis"]
        self.level_sums = ib["level_sums"]
        self.leg_hours = float(bk["effort_model"]["max_leg_hours"])
        cr = mk["curve_rule"]
        self.fight_parts = cr["fight_allowance"]["parts"]
        self.essentials = int(self.fight_parts["mart"]) + int(self.fight_parts["ferries"])
        money = docs["blackout"]["money"]
        self.blackout = -(-int(money["cap"]) * int(money["percent"]) // 100)         # ceil(cap * percent / 100)
        self.produce_rows = docs["produce"]["schedule"]["rows"]
        # bank prices (what a sale pays) and the declared rates
        self.price = {b["item"]: int(b["price"]) for b in bk["buys"]}
        # a smelted gold ingot pays raw + 2 (bank.json crafts.removed_inputs: 4 ingots = $88 of a $900 netherite ingot)
        self.price.setdefault("minecraft:gold_ingot", self.price["minecraft:raw_gold"] + 2)
        self.rate = {b["item"]: float(b.get("rate_per_hour") or 0) for b in bk["buys"]}
        self.tier_hour = {}
        for name, t in bk["effort_model"]["tiers"].items():
            self.tier_hour[name] = sum(float(b["rate_per_hour"]) * int(b["price"]) for b in bk["buys"]
                                       if b.get("tier") in set(t["from_tiers"]))
        self.tier_opens_badges = {n: int(t["opens_leg"]) - 1 for n, t in bk["effort_model"]["tiers"].items()}
        # the Nether is gated on badge 8 (data/nether_gate.json), not on the bank's opens_leg 7: the gate wins
        gf = docs["nether_gate"]["gate_flag"]
        self.nether_badge = int(gf.rsplit("gym", 1)[1].split("_")[0])
        self.bank_nether_badge = self.tier_opens_badges.get("nether")
        self.tier_opens_badges["nether"] = self.nether_badge
        # dungeons
        eng = d["engine"]
        self.clock_min = {b["band"]: b["clock_s"] / 60.0 for b in eng["bands"]}
        self.band_caps = {b["band"]: b["caps"] for b in eng["bands"]}
        self.ladder = [(r["taken"], r["rate"]) for r in eng["clock"]["ladder"]]
        self.sigils = {x["band"]: x for x in eng["sigils"]["ladder"]}
        self.sigil_value = {b: sum(self.price[i] * n for i, n in x["recipe"]) for b, x in self.sigils.items()}
        self.sigil_minutes = {b: self.gather_minutes(x["recipe"]) for b, x in self.sigils.items()}
        self.lockout_min = eng["lockout_ticks"] / 20 / 60
        self.dungeon = d["dungeons"][0]
        self.boss_teams = {b: self.boss_stage_teams(b) for b in self.clock_min}
        self.face_diamonds = face_diamonds
        self.p_stage_override = p_stage
        # counters
        self.shelf_due, self.late_shelf = self.read_shelf()
        self.beast_ball = self.counter_price("cobblemon:beast_ball")
        self.master_ball = self.counter_price("cobblemon:master_ball")
        self.services = docs["services"]["services"]

    # --- gathering time for a recipe, at the bank's declared rates (DUNGEONS.md 7.4's "Gathering" column)
    def gather_minutes(self, recipe):
        raw = {"minecraft:iron_ingot": ("minecraft:raw_iron", 1), "minecraft:gold_ingot": ("minecraft:raw_gold", 1),
               "minecraft:coal": ("minecraft:coal", 1), "minecraft:redstone": ("minecraft:redstone", 1),
               "minecraft:diamond": ("minecraft:diamond", 1), "minecraft:netherite_scrap": ("minecraft:ancient_debris", 1),
               "minecraft:netherite_ingot": None}
        minutes = 0.0
        for item, n in recipe:
            if item == "minecraft:netherite_ingot":      # 4 scrap (debris) + 4 gold ingots (bank.json crafts)
                minutes += self.gather_minutes([["minecraft:netherite_scrap", 4], ["minecraft:gold_ingot", 4]]) * n
                continue
            src, per = raw[item]
            minutes += n * per / self.rate[src] * 60.0
        return minutes

    def counter_price(self, item):
        for c in self.docs["markets"]["counters"]:
            for it in c["stock"]:
                if it["item"] == item:
                    return int(it["price"])
        raise SimError("no counter sells %s" % item)

    def read_shelf(self):
        """({leg: [price, ...]} the critical path's convenience lines due that leg, a pick-one group at its dearest,
        stretch aside -- the curve's own ask; [(price, available at badge, id, path)] the late shelf: everything else)."""
        due, groups, late = {}, {}, []
        for c in self.docs["markets"]["counters"]:
            for it in c["stock"]:
                price = int(it["price"])
                crit_conv = c["path"] == "critical" and it.get("strand") == "convenience" and not it.get("stretch")
                if crit_conv:
                    leg = max(1, int(c["badge"] or 0))
                    if it.get("group"):
                        k = (leg, c["id"], it["group"])
                        groups[k] = max(groups.get(k, 0), price)
                    else:
                        due.setdefault(leg, []).append(price)
                else:
                    avail = max(int(c["badge"] or 0), int(it.get("gate_badge") or 0))
                    if it.get("stretch"):
                        avail = max(avail, int(it["affordable_by"]))
                    late.append((price, avail, "%s/%s" % (c["id"], it["id"]), c["path"]))
        for (leg, _r, _g), p in groups.items():
            due.setdefault(leg, []).append(p)
        return due, late

    # --- levels and bands
    def boss_stage_teams(self, band):
        """[[levels]] per stage, derived here from data/dungeons.json (not by tools/dungeon.py's boss_classes)."""
        bo = self.dungeon["boss"]
        base = min(self.band_caps[band])
        offs = bo["stage_level_offsets"]
        teams = []
        for k, off in enumerate(offs, 1):
            team = [base + off]
            if k == len(offs) and band >= bo["escort_from_band"]:
                team.append(base + bo["escort_level_offset"])
            teams.append(team)
        return teams

    def stand_team(self, band):
        base = min(self.band_caps[band])
        return [base - 2 + (i % 2) for i in range(STAND_MEMBERS[band])]       # cap-2 .. cap-1 (5.3)

    def band_of(self, badges, champion=False):
        cap = CHAMPION_CAP if champion else CAP_BY_BADGES[badges]
        for b in sorted(self.band_caps):
            if max(self.band_caps[b]) >= cap:
                return b
        raise SimError("no band for cap %d" % cap)

    def rate_of(self, taken):
        r = self.ladder[0][1]
        for t, rate in self.ladder:
            if taken >= t:
                r = rate
        return r

    def mult_of(self, taken):
        return self.rate_of(taken) / float(self.ladder[0][1])

    def seam_face(self, band):
        """The 24-block face as a list of ore names (largest-remainder rounding of the cave yields)."""
        y = self.docs["caves"]["yields"]
        if band <= 2:
            w = {k: v["mean"] for k, v in y["early"]["ores"].items() if "lapis" not in k}
        else:
            w = {k: v["mean"] for k, v in y["deep"]["ores"].items() if "diamond" not in k}
        w = {k.replace("minecraft:", "").replace("deepslate_", ""): float(v) for k, v in w.items()}
        n_dia = self.face_diamonds if band >= 5 else 0
        total = 24 - n_dia
        s = sum(w.values())
        raw = {k: v * total / s for k, v in w.items()}
        counts = {k: int(math.floor(v)) for k, v in raw.items()}
        for k in sorted(raw, key=lambda k: -(raw[k] - counts[k]))[: total - sum(counts.values())]:
            counts[k] += 1
        face = [k for k, n in counts.items() for _ in range(n)] + ["diamond_ore"] * n_dia
        return face

    def expected_face_value(self, band):
        v = 0.0
        for ore in self.seam_face(band):
            item, lo, hi = ORE_DROPS[ore]
            v += (lo + hi) / 2.0 * self.price[item]
        return v

    def credit(self, levels, rng):
        """One battleVictory credit for a loser team of these levels."""
        s = sum(levels)
        b = max(1, s * s // 10)
        amount = b + rng.randint(b // 2, 2 * b)
        return int(amount * self.mult)

    def credit_range(self, levels):
        s = sum(levels)
        b = max(1, s * s // 10)
        return int((b + b // 2) * self.mult), int((b + 2 * b) * self.mult)

    def produce_allowance(self, badges):
        for r in self.produce_rows:
            lo, hi = r["badges"]
            if lo <= badges <= hi:
                return int(r["price"]) * int(r["crates"])
        return 0

    def gather_hour_value(self, badges):
        best = 0.0
        for name, h in self.tier_hour.items():
            if badges >= self.tier_opens_badges[name]:
                best = max(best, h)
        return best

    def fight_hour(self, key):
        """Expected income of a leg per fight hour (the existing model's own parity yardstick)."""
        sums = self.level_sums["normal"][str(key)]
        tot = sum(0.28125 * s * s for s in sums)
        return tot / self.leg_hours


# ------------------------------------------------------------------------------------------------- one dungeon run


def dungeon_run(w, band, n_take, rng, p_stage, scen, hours_pad=True):
    """One Night Shift run at `band` taking n_take seam blocks. Returns a dict of what it paid and cost (no cash
    state: the caller applies the blackout). Draw order never depends on `scen`, so scenarios pair exactly."""
    R = REQUIRED_MIN[band]
    clock = w.clock_min[band]
    pre_share = SEAM_PRE_MIN / (SEAM_PRE_MIN + SEAM_POST_MIN)
    pre_walk = pre_share * R - SEAM_DIG_FREE_MIN
    post = (1 - pre_share) * R
    dig_per = SEAM_DIG_FREE_MIN / 4.0
    X = rng.lognormvariate(0.0, TIME_SIGMA)
    other = rng.random() < P_OTHER
    other_at = rng.random()
    stand_draws = [rng.random() for _ in range(PRE_STANDS + POST_STANDS)]
    stage_draws = [rng.random() for _ in range(len(w.boss_teams[band]))]
    stage_credit = [w.credit(t, rng) for t in w.boss_teams[band]]
    stand_credit = [w.credit(w.stand_team(band), rng) for _ in range(PRE_STANDS + POST_STANDS)]
    mined = [(rng.randint(ORE_DROPS[o][1], ORE_DROPS[o][2]), o) for o in w.seam_face(band)]
    rng.shuffle(mined)
    r = dict(ore=0.0, boss=0.0, stands=0.0, stage_wins=0, stand_wins=0, finished=False, turned_back=False,
             died=False, cause=0, real_min=0.0, took=0, gems=0, bundle=False)

    def die(cause):
        r["died"], r["cause"] = True, cause
        return r

    # before the seam
    used = 0.0
    for i in range(PRE_STANDS):
        if stand_draws[i] > P_STAND:
            return die(2)
        r["stand_wins"] += 1
        r["stands"] += stand_credit[i]
    if other and other_at < pre_share:
        return die(3)
    used += pre_walk * X
    # the seam: a block at a time, the clock already ticking at the rate the blocks taken so far set
    taken = 0
    dig_real = 0.0
    for k in range(n_take):
        used += dig_per * w.mult_of(taken)
        dig_real += dig_per
        taken += 1
        item = ORE_DROPS[mined[k][1]]
        r["ore"] += mined[k][0] * w.price[item[0]]
    r["took"] = taken
    r["real_min"] = pre_walk * X + dig_real
    remaining = clock - used
    if remaining <= 0:
        return die(1)
    m = w.mult_of(taken)
    need_est = post * m
    if need_est > remaining:                                # the player reads the board and turns back
        r["turned_back"] = True
        if BACK_WALK_MIN * m > remaining:
            return die(1)
        r["real_min"] += BACK_WALK_MIN
        r["gems"] = GEMS_PER_STAND[band] * r["stand_wins"]
        return r
    actual = post * X * m
    boss_start = 0.55                                       # of the post-seam time: walk and parkour, a stand, then the boss
    if actual > remaining:
        f = remaining / actual
        if f < boss_start:
            return die(1)
        reached = min(len(stage_draws), max(1, math.ceil((f - boss_start) / (1 - boss_start) * len(stage_draws))))
        for i in range(reached):
            if stage_draws[i] > p_stage:
                return die(2)
            r["stage_wins"] += 1
            r["boss"] += stage_credit[i]
        return die(1)
    r["real_min"] += post * X
    # after the seam: a stand, a fall, the boss
    if stand_draws[PRE_STANDS] > P_STAND:
        return die(2)
    r["stand_wins"] += 1
    r["stands"] += stand_credit[PRE_STANDS]
    if other and other_at >= pre_share:
        return die(3)
    for i in range(len(stage_draws)):
        if stage_draws[i] > p_stage:
            return die(2)
        r["stage_wins"] += 1
        r["boss"] += stage_credit[i]
    r["finished"] = True
    r["bundle"] = True
    r["gems"] = GEMS_PER_STAND[band] * r["stand_wins"]
    return r


def run_net(w, band, r, scen, cash_cap=None):
    """Money from one run: seam sold, plus the boss (and stand) payout the scenario lets through, less the sigil's
    bank value (what its inputs would have fetched) and the blackout on a death. cash_cap bounds the blackout."""
    pay = 0.0
    if scen["pay_boss"]:
        pay += r["boss"]
    if scen["stands"]:
        pay += r["stands"]
    death = 0
    if r["died"]:
        death = w.blackout if cash_cap is None else min(w.blackout, max(0, cash_cap))
    return r["ore"] + pay - w.sigil_value[band] - death, pay, death


def best_take(w, band, scen, p_stage, seed=0, n=400):
    """The greedy player's choice: the seam take (top of a ladder tier) with the best mean net money, found by playing
    each candidate n times on the same draws. Deterministic in `seed`."""
    best = None
    for take in SEAM_TAKE_CANDIDATES:
        rng = random.Random("best:%s:%d:%d:%s" % (seed, band, n, sorted(scen.items())))
        tot = 0.0
        for _ in range(n):
            r = dungeon_run(w, band, take, rng, p_stage, scen)
            net, _p, _d = run_net(w, band, r, scen)
            tot += net
        mean = tot / n
        if best is None or mean > best[1]:
            best = (take, mean)
    return best[0]


# ------------------------------------------------------------------------------------------------- one player


def poisson(rng, lam):
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def stage_list(w):
    """[(key, badges held, fight keys, fight hours)] the playthrough, then the post-Champion loop."""
    out = [(str(n), n - 1, [str(n)], w.leg_hours) for n in range(1, 9)]
    out.append(("vr", 8, ["vr"], VR_HOURS))
    out.append(("league", 8, ["league"], LEAGUE_HOURS))
    out.append(("hq_tower", 8, ["hq_tower"], HQ_HOURS))
    return out


class Ledger(dict):
    CATS = ("fights", "gather", "produce", "seam", "boss_pay", "stand_pay", "sigils", "deaths", "dungeon_deaths",
            "essentials", "shelf")

    def __init__(self):
        super().__init__({c: 0.0 for c in self.CATS})


def play(w, ptype, scen, seed_key, take_cache, sweep_p=None):
    """One player through every stage. Returns [stage records]; each a dict of the stage's ledger and state."""
    cfg = PLAYER_TYPES[ptype]
    rng = random.Random(seed_key)
    p_stage = w.p_stage_override if w.p_stage_override is not None else cfg["p_stage"]
    cash = 0.0
    backlog = []
    records = []
    stages = stage_list(w) + [("champion", 8, [], float(POST_CHAMPION_HOURS))]
    for key, badges, fkeys, hours in stages:
        champion = key == "champion"
        if champion and ptype != "greedy":
            continue
        led = Ledger()
        start_cash = cash
        # --- fights
        for fk in fkeys:
            for s in w.level_sums[cfg["mode"]][fk]:
                c = w.credit([s], rng) if s > 0 else 0
                led["fights"] += c
                cash += c
        # --- the gathering hour(s), sold to the bank
        if cfg["gather"] and (key.isdigit() or key == "vr"):
            v = w.gather_hour_value(badges) * cfg["gather"] * rng.uniform(*GATHER_NOISE)
            led["gather"] += v
            cash += v
        # --- the produce allowance (per player, per leg: fills once)
        if cfg["produce"] and not champion and key not in ("hq_tower", "league"):
            a = w.produce_allowance(badges)
            led["produce"] += a
            cash += a
        # --- dungeon runs
        band = w.band_of(badges, champion=champion)
        runs = cfg["runs"] if not champion else POST_CHAMPION_HOURS
        run_hours, dstats = 0.0, dict(runs=0, finished=0, died=0, turned=0, gems=0, bundles=0)
        if runs and key not in ("league", "hq_tower"):
            if cfg["take"] == "best":
                ck = (band, tuple(sorted(scen.items())), p_stage)
                if ck not in take_cache:
                    take_cache[ck] = best_take(w, band, scen, p_stage)
                take = take_cache[ck]
            else:
                take = 4
            for run_i in range(runs):
                r = dungeon_run(w, band, take, rng, p_stage, scen)
                # defect 2, worst case: the leg a tm_gate plan change re-syncs, the first sigil is crafted in the
                # window from the next band's recipe (the rip accepts a higher band's sigil when none of its own is held)
                sig_band = band + 1 if (scen["window"] and key == WINDOW_STAGE and run_i == 0
                                        and band + 1 in w.sigil_value) else band
                sig_cost = w.sigil_value[sig_band]
                led["seam"] += r["ore"]
                led["boss_pay"] += r["boss"] if scen["pay_boss"] else 0.0
                led["stand_pay"] += r["stands"] if scen["stands"] else 0.0
                led["sigils"] -= sig_cost
                dstats["runs"] += 1
                dstats["finished"] += r["finished"]
                dstats["died"] += r["died"]
                dstats["turned"] += r["turned_back"]
                dstats["gems"] += r["gems"]
                dstats["bundles"] += r["bundle"]
                cash += r["ore"] + (r["boss"] if scen["pay_boss"] else 0.0) + (r["stands"] if scen["stands"] else 0.0)
                cash -= sig_cost
                if r["died"]:
                    d = min(w.blackout, max(0.0, cash))
                    led["dungeon_deaths"] -= d
                    cash -= d
                run_hours += max(w.lockout_min, r["real_min"]) / 60.0
        # --- deaths outside dungeons
        if not champion:
            for _ in range(poisson(rng, cfg["deaths"])):
                d = min(w.blackout, max(0.0, cash))
                led["deaths"] -= d
                cash -= d
        # --- essentials (Mart + ferries) first, then the shelf cheapest first
        short = 0.0
        if not champion and key not in ("league", "hq_tower"):
            e = min(float(w.essentials), max(0.0, cash))
            short = w.essentials - e
            led["essentials"] -= e
            cash -= e
            leg_n = int(key) if key.isdigit() else None
            if leg_n:
                backlog += list(w.shelf_due.get(leg_n, []))
            for p in sorted(backlog):
                if cash >= p:
                    cash -= p
                    led["shelf"] -= p
                    backlog.remove(p)
        gross = sum(v for k, v in led.items() if v > 0)
        active = run_hours if champion else hours + (cfg["gather"] if (key.isdigit() or key == "vr") else 0.0) + run_hours
        records.append(dict(stage=key, badges=badges, band=band, ledger=dict(led), cash_in=gross,
                            cash_end=cash, start_cash=start_cash, hours=active, idle_hours=cfg["idle"] * (0 if champion else 1),
                            ess_short=short, backlog=sum(backlog), backlog_n=len(backlog), dungeon=dstats))
    return records


# ------------------------------------------------------------------------------------------------- aggregation


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return 0.0
    i = min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))
    return xs[i]


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def simulate(w, ptypes=None, scenarios=None, runs=300, seed=1):
    """{scenario: {ptype: [stage summary]}}: every player is its own seeded stream, and a scenario pairs with the
    others on the same player index (the draws are consumed in the same order)."""
    ptypes = ptypes or list(PLAYER_TYPES)
    scenarios = scenarios or ["as_built", "design"]
    out = {}
    for sn in scenarios:
        scen = SCENARIOS[sn]
        out[sn] = {}
        take_cache = {}
        for pt in ptypes:
            recs = [play(w, pt, scen, "%s:%s:%d" % (seed, pt, i), take_cache) for i in range(runs)]
            summary = []
            for j in range(len(recs[0])):
                col = [r[j] for r in recs]
                led = {c: mean(x["ledger"][c] for x in col) for c in Ledger.CATS}
                inc_h = [x["cash_in"] / x["hours"] if x["hours"] else 0.0 for x in col]
                net_h = [(x["cash_end"] - x["start_cash"]) / x["hours"] if x["hours"] else 0.0 for x in col]
                summary.append(dict(
                    stage=col[0]["stage"], badges=col[0]["badges"], band=col[0]["band"], hours=mean(x["hours"] for x in col),
                    idle_hours=col[0]["idle_hours"], ledger=led, cash_in=mean(x["cash_in"] for x in col),
                    income_h=mean(inc_h), income_h_p10=pct(inc_h, 0.1), income_h_p90=pct(inc_h, 0.9),
                    net_h=mean(net_h), savings=mean(x["cash_end"] for x in col), savings_p10=pct([x["cash_end"] for x in col], 0.1),
                    ess_short_p=mean(1.0 if x["ess_short"] > 0 else 0.0 for x in col),
                    backlog=mean(x["backlog"] for x in col),
                    backlog_p=mean(1.0 if x["backlog_n"] > 0 else 0.0 for x in col),
                    dungeon={k: mean(x["dungeon"][k] for x in col) for k in col[0]["dungeon"]}))
            out[sn][pt] = summary
    return out


def affordable_share(w, savings, badges):
    """Of the late shelf's lines available at `badges`, the value share buyable with `savings` taking the cheapest first."""
    lines = sorted((p for p, av, _i, _path in w.late_shelf if av <= badges))
    total = sum(lines)
    spent = 0
    for p in lines:
        if spent + p > savings:
            break
        spent += p
    return (spent / total if total else 1.0), total


def dungeon_table(w, runs=2000, seed=1, p_stage=0.9, scenarios=("design", "as_built")):
    """Per band, per scenario, per seam take: net money per run and per wall hour, the finish and death rates."""
    rows = []
    for band in sorted(w.clock_min):
        for sn in scenarios:
            scen = SCENARIOS[sn]
            for take in SEAM_TAKE_CANDIDATES:
                rng = random.Random("dt:%s:%d:%d:%s" % (seed, band, take, "paired"))
                tot = dict(net=0.0, ore=0.0, pay=0.0, fin=0, died=0, turned=0, wall=0.0, gems=0)
                for _ in range(runs):
                    r = dungeon_run(w, band, take, rng, p_stage, scen)
                    net, pay, death = run_net(w, band, r, scen)
                    tot["net"] += net
                    tot["ore"] += r["ore"]
                    tot["pay"] += pay
                    tot["fin"] += r["finished"]
                    tot["died"] += r["died"]
                    tot["turned"] += r["turned_back"]
                    tot["gems"] += r["gems"]
                    tot["wall"] += max(w.lockout_min, r["real_min"]) / 60.0
                rows.append(dict(band=band, scenario=sn, take=take, net=tot["net"] / runs, ore=tot["ore"] / runs,
                                 pay=tot["pay"] / runs, finished=tot["fin"] / runs, died=tot["died"] / runs,
                                 turned=tot["turned"] / runs, wall=tot["wall"] / runs, gems=tot["gems"] / runs,
                                 net_h=tot["net"] / tot["wall"]))
    return rows


def parity_hours(w):
    """The fight hour a dungeon hour is compared with, per band: the lowest fight hour among the legs played in the
    band (the conservative one: it is the leg where a dungeon hour is likeliest to look good)."""
    legs_in_band = {}
    for key, badges, _f, _h in stage_list(w):
        band = w.band_of(badges)
        if key in ("hq_tower", "league"):
            continue
        legs_in_band.setdefault(band, []).append(key)
    out = {}
    for band, keys in legs_in_band.items():
        fh = []
        for k in keys:
            if k == "vr":
                fh.append(sum(0.28125 * s * s for s in w.level_sums["normal"]["vr"]) / VR_HOURS)
            else:
                fh.append(w.fight_hour(k))
        out[band] = (min(fh), keys)
    out[6] = (w.fight_hour("8"), ["8 (no leg after the Champion: leg 8's hour)"])
    return out


# ------------------------------------------------------------------------------------------------- the late game's bill

BEAST_THROWS = (4, 19)         # data/key_ball.json multiplier_why: "about 4 throws on a sleeping boss at 1 HP and 19 at full
                               # HP" (research note section 5, RELAYED; the tool checks the data still says it)
PARITY, R5_CEILING, WATCH = 1.0, 1.5, 0.5   # x the band's fight hour: ECONOMY_OVERHAUL.md R5 (parity; upper hour 1.5x)


def sinks(w):
    """[(label, low, high, note)] what the late game can ask of a player's money, each priced from the data."""
    sv = w.services
    max_cap = int(sv["raise"]["max_cap"])
    caps = sorted({c for caps in w.band_caps.values() for c in caps if c <= max_cap})
    ash = 2 * w.price["minecraft:netherite_ingot"]
    shelf_all = sum(p for p, _a, _i, _path in w.late_shelf)
    rows = [
        ("The late shelf: every counter line not on the curve (off-path counters, critical power, stretch), one of each",
         shelf_all, shelf_all, "data/markets.json counters; includes the Master Ball and one Beast Ball"),
        ("Level-raise service for a team of six at every cap step (%d steps x 6 x $%d)" % (len(caps), sv["raise"]["price"]),
         len(caps) * 6 * sv["raise"]["price"], len(caps) * 6 * sv["raise"]["price"], "optional; STATE says ~$30,000"),
        ("Effort training, one Pokemon (EV spread)", sv["ev"]["price"], sv["ev"]["price"], "per Pokemon"),
        ("Perfect IVs, all six stats of one Pokemon", 6 * sv["iv"]["price_per_stat"], 6 * sv["iv"]["price_per_stat"],
         "per stat, bought again at full price even at 31 (services.iv.repeat_rule)"),
        ("EV + IV for a team of six", 6 * (sv["ev"]["price"] + 6 * sv["iv"]["price_per_stat"]),
         6 * (sv["ev"]["price"] + 6 * sv["iv"]["price_per_stat"]), "STATE's '~$50,000 if fully used' predates the per-hour pricing rule"),
        ("Beast Balls for ONE boss catch (Entei, built)", BEAST_THROWS[0] * w.beast_ball, BEAST_THROWS[1] * w.beast_ball,
         "4 throws asleep at 1 HP .. 19 at full HP; a failed throw spends the ball (key_ball.json)"),
        ("Tower Ash for an Entei attempt (2 netherite ingots at the bank)", ash, ash,
         "per attempt; lockout 24,000 ticks (20 min of uptime): a farm-mode hour can cost 3 ashes"),
    ]
    return rows


# ------------------------------------------------------------------------------------------------- the report


def money(x):
    return "{:,.0f}".format(x)


def ratio(x, y):
    return "%.2f" % (x / y) if y else "-"


def best_row(rows, band, scen):
    cand = [r for r in rows if r["band"] == band and r["scenario"] == scen]
    return max(cand, key=lambda r: r["net_h"])


def row_at(rows, band, scen, take):
    return next(r for r in rows if r["band"] == band and r["scenario"] == scen and r["take"] == take)


def cumulative_income(seq):
    out, c = {}, 0.0
    for st in seq:
        c += st["cash_in"]
        out[st["stage"]] = c
    return out


def verdict_flag(r):
    if r >= R5_CEILING:
        return "PRINTS (over the R5 ceiling)"
    if r >= PARITY:
        return "PARITY BROKEN"
    return "ok"


def build_report(w, runs=300, seed=1, dungeon_runs=3000):
    sim = simulate(w, runs=runs, seed=seed, scenarios=["as_built", "design"],
                   ptypes=["fighter", "baseline", "steady", "afk", "challenge", "greedy"])
    aux = simulate(w, runs=runs, seed=seed, scenarios=["defect1", "defect2", "stands_unclawed"], ptypes=["steady", "greedy"])
    allsim = {**sim, **aux}
    rows = dungeon_table(w, runs=dungeon_runs, seed=seed, p_stage=0.9,
                         scenarios=("design", "as_built", "stands_unclawed"))
    par = parity_hours(w)
    out = []
    P = out.append
    data = {"sim": allsim, "dungeon_rows": rows, "parity": {str(k): v[0] for k, v in par.items()}}

    P("### T1. The boss payout per run, re-derived from the formula and data/dungeons.json\n")
    P("| Band | Stage teams (levels; a + is the escort) | Stage S | Per run, min-max | Per run, mean of 4,000 draws |")
    P("|---|---|---|---:|---:|")
    rng = random.Random("payout")
    for b in sorted(w.clock_min):
        teams = w.boss_teams[b]
        lo = sum(w.credit_range(t)[0] for t in teams)
        hi = sum(w.credit_range(t)[1] for t in teams)
        m = mean(sum(w.credit(t, rng) for t in teams) for _ in range(4000))
        P("| %d | %s | %s | $%s-%s | $%s |" % (b, "; ".join("+".join(map(str, t)) for t in teams),
                                              ", ".join(str(sum(t)) for t in teams), money(lo), money(hi), money(m)))

    P("\n### T2. One dungeon run, by band (p(win a boss stage) 0.9; %d runs a cell; best seam take per scenario)\n" % dungeon_runs)
    P("| Band | Badges held | Sigil bank value | Gather min | Seam face value | Fight hour (parity) | Design: take, net/run | Design net/h | Design / parity | As built: take, finish, die | As built net/h | As built / parity | Verdict (as built) | Gathering hour at that badge | As built / gathering | Stands unclawed net/h (x parity) |")
    P("|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|---|---:|---:|---|")
    for b in sorted(w.clock_min):
        d, a, s = best_row(rows, b, "design"), best_row(rows, b, "as_built"), best_row(rows, b, "stands_unclawed")
        badges = {1: "0-1", 2: "2-3", 3: "4-5", 4: "6-7", 5: "8", 6: "Champion"}[b]
        fh = par[b][0]
        gh = w.gather_hour_value({1: 0, 2: 2, 3: 4, 4: 6, 5: 8, 6: 8}[b])
        P("| %d | %s | $%s | %.0f | $%s | $%s | %d, $%s | $%s | %s | %d, %.0f%%, %.0f%% | $%s | %s | %s | $%s | %sx | $%s (%sx) |" % (
            b, badges, money(w.sigil_value[b]), w.sigil_minutes[b], money(w.expected_face_value(b)), money(fh),
            d["take"], money(d["net"]), money(d["net_h"]), ratio(d["net_h"], fh), a["take"], 100 * a["finished"],
            100 * a["died"], money(a["net_h"]), ratio(a["net_h"], fh), verdict_flag(a["net_h"] / fh), money(gh),
            ratio(a["net_h"], gh), money(s["net_h"]), ratio(s["net_h"], fh)))
    data["verdicts"] = {b: verdict_flag(best_row(rows, b, "as_built")["net_h"] / par[b][0]) for b in par}

    P("\n### T3. The greed ladder: net money per run by seam take (blocks), design vs as built\n")
    P("| Band | Scenario | " + " | ".join("take %d (x%.2g)" % (t, w.mult_of(t)) for t in SEAM_TAKE_CANDIDATES) + " |")
    P("|---|---|" + "---:|" * len(SEAM_TAKE_CANDIDATES))
    for b in (1, 3, 4, 6):
        for sn in ("design", "as_built"):
            P("| %d | %s | %s |" % (b, sn, " | ".join("$%s" % money(row_at(rows, b, sn, t)["net"]) for t in SEAM_TAKE_CANDIDATES)))

    P("\n### T4. Income per active hour by stage (as built; mean of %d players per type)\n" % runs)
    names = ["fighter", "steady", "afk", "challenge", "greedy"]
    P("| Stage | Badges | Fight hour | " + " | ".join(names) + " |")
    P("|---|---:|---:|" + "---:|" * len(names))
    for st in sim["as_built"]["steady"]:
        fh = w.fight_hour(st["stage"]) if st["stage"].isdigit() else None
        cells = [money(next(x for x in sim["as_built"][n] if x["stage"] == st["stage"])["income_h"]) for n in names]
        P("| %s | %d | %s | %s |" % (st["stage"], st["badges"], money(fh) if fh else "-", " | ".join(cells)))
    g = next(x for x in sim["as_built"]["greedy"] if x["stage"] == "champion")
    gd = next(x for x in sim["design"]["greedy"] if x["stage"] == "champion")
    P("| champion, 10 h of runs | 8+ | (leg 8: %s) | - | - | - | - | %s gross, **%s net** (design: %s gross, %s net) |" % (
        money(par[6][0]), money(g["income_h"]), money(g["net_h"]), money(gd["income_h"]), money(gd["net_h"])))
    P("\nActive hours: fights (4 a leg, VR 4, League 2, HQ 2) + the gathering hour + dungeon hours (1 per run, the lockout). "
      "The AFK farmer's 6 idle hours a leg are not counted. 'Income' is every dollar in (fights, gathering, produce, ore, boss payout), "
      "before costs.")

    P("\n### T5. Savings and what the late shelf lets them buy (as built; savings = cash after the Mart, ferries, deaths, sigils and the curve's own shelf)\n")
    shelf_total = sum(p for p, _a, _i, _p in w.late_shelf)
    P("| After | Fighter savings | Steady savings | Steady buys of late shelf | Greedy savings (as built) | Greedy (design) | Challenge savings | Steady cum. income | Starves? (steady / fighter) |")
    P("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    cum = cumulative_income(sim["as_built"]["steady"])
    for st in sim["as_built"]["steady"]:
        k = st["stage"]

        def at(sn, pt, k=k):
            return next(x for x in sim[sn][pt] if x["stage"] == k)
        badges_after = st["badges"] + (1 if k.isdigit() else 0)
        share, tot = affordable_share(w, st["savings"], badges_after)
        fgt = at("as_built", "fighter")
        starve_f = "BACKLOG %.0f%%" % (100 * fgt["backlog_p"]) if fgt["backlog_p"] >= 0.10 else "no"
        starve_s = "BACKLOG %.0f%%" % (100 * st["backlog_p"]) if st["backlog_p"] >= 0.10 else ("ESSENTIALS SHORT" if st["ess_short_p"] >= 0.01 else "no")
        P("| %s | $%s | $%s | %.0f%% of $%s | $%s | $%s | $%s | $%s | %s / %s |" % (
            k, money(fgt["savings"]), money(st["savings"]), 100 * share, money(tot), money(at("as_built", "greedy")["savings"]),
            money(at("design", "greedy")["savings"]), money(at("as_built", "challenge")["savings"]), money(cum[k]), starve_s, starve_f))
    gc = next(x for x in sim["as_built"]["greedy"] if x["stage"] == "champion")
    gcd = next(x for x in sim["design"]["greedy"] if x["stage"] == "champion")
    P("| champion +10 h of runs | - | - | - | $%s | $%s | - | - | - |" % (money(gc["savings"]), money(gcd["savings"])))
    P("\nThe whole late shelf is $%s (one of each line). 'Buys of late shelf' takes the lines available at that badge, cheapest first." % money(shelf_total))

    P("\n### T6. The two defects, separated (campaign end = after the HQ tower; post = after 10 more hours of band-6 runs)\n")
    P("| Scenario | Steady: savings at end | Steady vs design | Greedy: savings at end | Greedy vs design | Greedy: post-Champion 10 h | vs design |")
    P("|---|---:|---:|---:|---:|---:|---:|")

    def last(sn, pt, stage):
        return next(x for x in allsim[sn][pt] if x["stage"] == stage)["savings"]
    base_s, base_g, base_p = last("design", "steady", "hq_tower"), last("design", "greedy", "hq_tower"), last("design", "greedy", "champion")
    for sn in ("design", "defect1", "defect2", "as_built", "stands_unclawed"):
        s_, g_, p_ = last(sn, "steady", "hq_tower"), last(sn, "greedy", "hq_tower"), last(sn, "greedy", "champion")
        P("| %s | $%s | %+.0f | $%s | %+.0f | $%s | %+.0f |" % (sn, money(s_), s_ - base_s, money(g_), g_ - base_g, money(p_), p_ - base_p))
    data["defects"] = {sn: {"steady": last(sn, "steady", "hq_tower"), "greedy": last(sn, "greedy", "hq_tower"),
                            "post": last(sn, "greedy", "champion")} for sn in allsim if sn in SCENARIOS}

    P("\n### T7. The late game's bill (priced from the data)\n")
    P("| Item | Low | High | Note |")
    P("|---|---:|---:|---|")
    for label, lo, hi, note in sinks(w):
        P("| %s | $%s | $%s | %s |" % (label, money(lo), money(hi), note))
    cum_end = cumulative_income(sim["as_built"]["steady"])["hq_tower"]
    P("\nSteady player, cumulative income through the League and HQ tower: $%s; savings then: $%s (as built)." % (
        money(cum_end), money(sim["as_built"]["steady"][-1]["savings"])))

    P("\n### T8. Sensitivity: how the as-built dungeon hour moves with the assumptions I could not measure\n")
    P("| Band | p(win a stage) | Finish | Net/h as built (best take) | Parity ratio |")
    P("|---|---:|---:|---:|---:|")
    sens = []
    for b in (1, 4, 6):
        for ps in (0.75, 0.9, 0.97, 1.0):
            r = best_row(dungeon_table(w, runs=max(60, dungeon_runs // 2), seed=seed, p_stage=ps, scenarios=("as_built",)), b, "as_built")
            sens.append((b, ps, r))
            P("| %d | %.2f | %.0f%% | $%s | %s |" % (b, ps, 100 * r["finished"], money(r["net_h"]), ratio(r["net_h"], par[b][0])))
    data["sensitivity"] = [(b, ps, r["net_h"]) for b, ps, r in sens]
    P("\nSeam diamonds on the band-6 face (design, greed take 24, turn back):\n")
    P("| Diamonds on the face | Face value | Net/run (take 24) | Net/h |")
    P("|---:|---:|---:|---:|")
    for nd in (0, 1, 3, 6, 12):
        w2 = World(w.docs, face_diamonds=nd)
        r = row_at(dungeon_table(w2, runs=max(60, dungeon_runs // 2), seed=seed, p_stage=0.9, scenarios=("design",)), 6, "design", 24)
        P("| %d | $%s | $%s | $%s |" % (nd, money(w2.expected_face_value(6)), money(r["net"]), money(r["net_h"])))

    P("\n### T9. The held rewards are items, not dollars (design, seam take 4 = the free tier and finish the run; p(win a stage) 0.9)\n")
    P("| Band | Finish rate | Area gems a run | Boss bundle (relayed, DUNGEONS.md 9.2) | Bundles an hour |")
    P("|---|---:|---:|---|---:|")
    bundles = {1: "1 M + 2 S candies", 2: "3 M candies", 3: "1 L + 2 M candies", 4: "2 L + 1 M, 1-2 IV candies",
               5: "1 XL, 2-3 IV candies, 1 Rare Candy", 6: "2 XL, 3-4 IV candies, 1-2 Rare Candy"}
    for b in sorted(w.clock_min):
        r = row_at(rows, b, "design", 4)
        P("| %d | %.0f%% | %.1f | %s | %.2f |" % (b, 100 * r["finished"], r["gems"], bundles[b], r["finished"] / r["wall"]))
    sold = sorted({it["item"] for c in w.docs["markets"]["counters"] for it in c["stock"]
                   if "candy" in it["item"] or it["item"].endswith("_gem")})
    bought = sorted(b["item"] for b in w.docs["bank"]["buys"] if "candy" in b["item"] or b["item"].endswith("_gem"))
    P("\nCounter lines selling a candy or a type gem: %d (%s). Bank lines buying one: %d. So a reward has no dollar price anywhere "
      "in the economy and a held reward cannot be sold: its worth is the levels and TM crafts it saves." % (
          len(sold), ", ".join(sold) or "none", len(bought)))
    data["reward_sold_or_bought"] = [sold, bought]

    P("\n### T10. What the dungeons do to the money the curve was built on (steady player, per leg)\n")
    P("| Stage | Curve income (fights+gather+produce) | Spend on the curve (Mart, ferries, deaths, shelf) | Spend / income, no dungeons | Dungeon net, design | Dungeon net, as built | Dungeon net / curve income, design | as built |")
    P("|---|---:|---:|---:|---:|---:|---:|---:|")
    ratios = {}
    for st in sim["design"]["steady"]:
        k = st["stage"]
        if k in ("vr", "league", "hq_tower"):
            continue
        base = next(x for x in sim["design"]["baseline"] if x["stage"] == k)["ledger"]
        inc = base["fights"] + base["gather"] + base["produce"]
        spend = -(base["essentials"] + base["deaths"] + base["shelf"])

        def dnet(sn, k=k):
            led = next(x for x in sim[sn]["steady"] if x["stage"] == k)["ledger"]
            return led["seam"] + led["boss_pay"] + led["stand_pay"] + led["sigils"] + led["dungeon_deaths"]
        ratios[k] = (spend / inc, dnet("design") / inc, dnet("as_built") / inc)
        P("| %s | $%s | $%s | %.2f | $%s | $%s | %+.1f%% | %+.1f%% |" % (
            k, money(inc), money(spend), spend / inc, money(dnet("design")), money(dnet("as_built")),
            100 * dnet("design") / inc, 100 * dnet("as_built") / inc))
    data["curve_ratio"] = ratios
    P("\nThe curve's own target is spend/income 0.65-0.70 (markets.json income_basis.target_ratio). Early legs read above it (the pure curve "
      "ask is not met by trainer money alone there: the design covers it with produce and mining, which the baseline player does).")

    P("\n### T11. Every loop against the yardstick (a non-fighting hour may pay at most the band's fight hour; R5's upper hour is 1.5x)\n")
    P("| Loop | $/h | Yardstick | Ratio | Verdict |")
    P("|---|---:|---:|---:|---|")
    loops = []
    for name, t in w.docs["bank"]["effort_model"]["tiers"].items():
        opens = max(1, int(t["opens_leg"]))
        fh = w.fight_hour(str(opens))
        loops.append(("Gathering, %s tier typical hour (opens leg %d)" % (name, opens), w.tier_hour[name], fh))
    up = sum(float(b.get("rate_per_hour_upper") or b["rate_per_hour"]) * int(b["price"]) for b in w.docs["bank"]["buys"]
             if b.get("tier") == "nether")
    loops.append(("Gathering, Nether upper hour (bed or TNT; 30 debris), vs leg 8", up, w.fight_hour("8")))
    afk_cap = sum(int(r["price"]) * int(r["crates"]) for r in w.produce_rows)
    loops.append(("AFK produce farm, the whole campaign's cap spread over its first 10 hours", afk_cap / 10.0, w.fight_hour("1")))
    for b in sorted(w.clock_min):
        a = best_row(rows, b, "as_built")
        loops.append(("Night Shift band %d, as built, best take %d" % (b, a["take"]), a["net_h"], par[b][0]))
    for b in (4, 6):
        a = best_row(rows, b, "design")
        loops.append(("Night Shift band %d, design (clawback works)" % b, a["net_h"], par[b][0]))
    for label, v, y in loops:
        P("| %s | $%s | $%s | %s | %s |" % (label, money(v), money(y), ratio(v, y), verdict_flag(v / y) if v > 0 else "pays nothing / a sink"))
    P("\nSinks that run on a clock: Entei with a Tower Ash every 20 minutes of uptime is -$%s an hour in ash alone (+ drops that no counter or bank buys)." % money(
        3 * 2 * w.price["minecraft:netherite_ingot"]))
    return data, out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=300, help="players per cell")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--dungeon-runs", type=int, default=3000, help="runs a cell of the per-band dungeon tables")
    ap.add_argument("--json", default=None, help="also write the numbers here")
    ap.add_argument("--write-doc", default=None,
                    help="replace the text between the economy_sim markers in this markdown file with the tables")
    a = ap.parse_args(argv)
    w = World(load_docs())
    data, lines = build_report(w, a.runs, a.seed, a.dungeon_runs)
    if a.write_doc:
        f = Path(a.write_doc)
        text = f.read_text(encoding="utf-8")
        b, e = "<!-- economy_sim:tables:begin -->", "<!-- economy_sim:tables:end -->"
        if b not in text or e not in text:
            raise SystemExit("%s has no %s ... %s markers" % (f, b, e))
        head, rest = text.split(b, 1)
        tail = rest.split(e, 1)[1]
        stamp = "_Generated by `python tools/economy_sim.py --runs %d --seed %d --write-doc ...`; do not edit between the markers._\n\n" % (a.runs, a.seed)
        f.write_text(head + b + "\n" + stamp + "\n".join(lines) + "\n" + e + tail, encoding="utf-8", newline="\n")
        print("wrote %d table lines into %s" % (len(lines), f))
        return 0
    print("\n".join(lines))
    if a.json:
        Path(a.json).write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())


