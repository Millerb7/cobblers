#!/usr/bin/env python
"""The Challenge voucher's schedule, computed from data: data/challenge_mode.json `voucher.computed`.

The owner, after the 2026-10-10 overnight (docs/STATE.md 'Owner decisions after the 2026-10-10 overnight' (2)):
"front-load it. More per gym early, the same total by the end. The point is a real choice: overspend early for power
and ration later, or hold back and buy late. Take the ladder's measured total rather than my $100k guess."

This is the SCHEDULE only. Nothing here grants anything: the grant (Oak's action, a give in each leader's reward
function, the mode tag, once per player) is a later unit's (docs/mechanics/ECONOMY_OVERHAUL.md BUILD LIST U6).
The reasoning is docs/mechanics/SERVICES_AND_CRAFTING.md.

THE TOTAL = Oak's cash + the answer kits at bank value + the power kit at Mart prices.
  - Oak's cash: the largest multiple of price_policies.income_gate.round_to STRICTLY below the cheapest income-gate
    line on any counter (data/markets.json), so the voucher alone buys no gated power line before badge 1
    (ECONOMY_OVERHAUL.md 4.4's own rule, recomputed here instead of carried).
  - The kits: voucher.kits, each material priced at data/bank.json's price (tools/bank.py prices). The QUANTITIES are
    ECONOMY_OVERHAUL.md 1.4's (RELAYED: a design, no barter line carries them yet, U4); the prices are measured.
  - The power kit: the six power items at data/traders.json stock_policy.mart.training's price. It is there because
    of the services decision: with the EV service priced above the hour it saves (data/training_services.json
    price_rule), a Challenge player, who plays with no Minecraft by the owner's design, trains EVs by battle with a
    power item held; that is the spend the decision obliges.

THE SHAPE (voucher.shape): Oak's grant is the cash above; the rest is shared over the eight gym-clear grants in
inverse proportion to the measured Challenge income of the leg each grant opens (data/markets.json
income_basis.challenge.leg_by_badge; the gym-8 grant opens Victory Road and the League, income_basis.post_badge_8).
The poorest leg gets the most, and every grant after the first is smaller than the one before it.

DELIVERY (voucher.delivery): a grant pays the next unpaid kits in materials first, whole kits only, then cash. Cash
cannot buy back a material (no seller sells raw ore or diamonds, rule B1), so a kit has to ride on a grant early
enough; the tool fails if any kit would arrive after the gym it answers.

  python tools/challenge_voucher.py            # print the schedule
  python tools/challenge_voucher.py --write    # write voucher.computed into data/challenge_mode.json
  python tools/challenge_voucher.py --check    # exit 1 if the file's voucher.computed is not what this computes
"""
from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

CHALLENGE = ROOT / "data" / "challenge_mode.json"
MARKETS = ROOT / "data" / "markets.json"
TRADERS = ROOT / "data" / "traders.json"
GENERATED_BY = "tools/challenge_voucher.py --write"


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def oak_cash(markets):
    """(cash, cheapest income-gate price): the largest multiple of round_to strictly below the cheapest line."""
    pol = markets["price_policies"]["income_gate"]
    step = int(pol["round_to"])
    gated = [int(l["price"]) for c in markets["counters"] for l in c.get("stock") or []
             if l.get("price_rule") == "income_gate"]
    if not gated:
        raise SystemExit("no income_gate line on any counter: Oak's cash has no bar to stay under")
    low = min(gated)
    return ((low - 1) // step) * step, low


def kit_value(kit, prices):
    total = 0
    for part in ("tm", "held", "extra"):
        for item, n in (kit.get(part) or {}).items():
            if item not in prices:
                raise SystemExit("voucher.kits for_leg %s: %s is not bought by the bank, so it has no value here"
                                 % (kit.get("for_leg"), item))
            total += prices[item] * int(n)
    return total


def power_kit_value(v, traders):
    want = v["power_kit"]["items"]
    have = {}
    for tier in traders["stock_policy"]["mart"]["training"]["tiers"]:
        for it in tier["items"]:
            have[it["item"]] = int(it["price"])
    missing = [i for i in want if i not in have]
    if missing:
        raise SystemExit("voucher.power_kit: %s not on the Mart's training shelf" % ", ".join(missing))
    return sum(have[i] for i in want)


def opens_income(markets, v):
    """[(grant flag, income of the leg the grant opens)] for the eight gym-clear grants."""
    ch = markets["income_basis"]["challenge"]["leg_by_badge"]
    post = markets["income_basis"]["post_badge_8"]["challenge"]
    out = []
    for n in range(1, 9):
        inc = int(ch[str(n + 1)]) if n < 8 else int(post["victory_road"]) + int(post["league"])
        out.append(("gym%d_cleared" % n, inc))
    return out


def compute(cdoc=None, markets=None, traders=None, bank_prices=None):
    import bank
    cdoc = cdoc if cdoc is not None else read(CHALLENGE)
    markets = markets if markets is not None else read(MARKETS)
    traders = traders if traders is not None else read(TRADERS)
    prices = bank_prices if bank_prices is not None else bank.prices(bank.load())
    v = cdoc["voucher"]
    cash0, low = oak_cash(markets)
    kits = sorted(v["kits"], key=lambda k: k["for_leg"])
    kv = [(k["for_leg"], kit_value(k, prices)) for k in kits]
    kits_total = sum(x for _, x in kv)
    pk = power_kit_value(v, traders)
    total = cash0 + kits_total + pk
    rest = total - cash0
    grants = opens_income(markets, v)
    w = [Fraction(1, inc) for _, inc in grants]
    raw = [rest * x / sum(w) for x in w]
    step = int(v["shape"]["round_to"])
    vals = [int(r // step) * step for r in raw]
    vals[0] += rest - sum(vals)                     # the rounding goes to the first gym grant: the total is exact
    sched = [{"at": "oak_mode_choice", "value": cash0, "cash": cash0, "kits": []}]
    queue = list(kv)
    late = []
    for (flag, inc), val in zip(grants, vals):
        budget, carried = val, []
        while queue and queue[0][1] <= budget:
            leg, x = queue.pop(0)
            budget -= x
            carried.append(leg)
        sched.append({"at": flag, "opens_income": inc, "value": val, "kits": carried, "cash": budget})
    # every kit must be in hand before the gym it answers: the kit for leg L (to badge L) by the grant at gym L-1's
    # clear; the League kit (for_leg 9) by gym 8's
    where = {leg: i for i, g in enumerate(sched) for leg in g["kits"]}
    for leg, _ in kv:
        if leg not in where:
            late.append("the kit for leg %d is on no grant: the grants after it are each smaller than it" % leg)
        elif where[leg] > leg - 1:
            late.append("the kit for leg %d arrives at %s, after the gym it answers" % (leg, sched[where[leg]]["at"]))
    if late:
        raise SystemExit("voucher: " + "; ".join(late))
    vals_all = [g["value"] for g in sched[1:]]
    if any(b > a for a, b in zip(vals_all, vals_all[1:])):
        raise SystemExit("voucher: a gym grant is larger than the one before it, so the schedule is not front-loaded")
    back = [cash0] + [x for _, x in kv]
    return {
        "generated_by": GENERATED_BY,
        "oak_cash": cash0,
        "oak_cash_bar": "the cheapest income_gate line on any counter is $%d (data/markets.json); Oak's cash is the "
                        "largest multiple of $%d strictly below it" % (low, int(markets["price_policies"]["income_gate"]["round_to"])),
        "kits_value_by_leg": {str(leg): x for leg, x in kv},
        "kits_total": kits_total,
        "power_kit_value": pk,
        "total": total,
        "total_was": "ECONOMY_OVERHAUL.md 4.4: $4,000 + $10,748 = about $14,750 (RELAYED review N148); this adds the "
                     "power kit the services decision obliges ($%d)" % pk,
        "schedule": sched,
        "back_loaded_was": back,
    }


def render(v):
    """The voucher block as data/challenge_mode.json writes it: one key a line, every value compact on its line."""
    lines = ["  \"voucher\": {"]
    keys = list(v)
    for i, k in enumerate(keys):
        if k == "computed":
            c = v[k]
            lines.append("    \"computed\": {")
            ck = list(c)
            for j, kk in enumerate(ck):
                if kk == "schedule":
                    lines.append("      \"schedule\": [")
                    for s_i, s in enumerate(c[kk]):
                        lines.append("        %s%s" % (json.dumps(s, ensure_ascii=False), "," if s_i < len(c[kk]) - 1 else ""))
                    lines.append("      ]%s" % ("," if j < len(ck) - 1 else ""))
                else:
                    lines.append("      %s: %s%s" % (json.dumps(kk), json.dumps(c[kk], ensure_ascii=False),
                                                     "," if j < len(ck) - 1 else ""))
            lines.append("    }%s" % ("," if i < len(keys) - 1 else ""))
        elif k == "kits":
            lines.append("    \"kits\": [")
            for k_i, kit in enumerate(v[k]):
                lines.append("      %s%s" % (json.dumps(kit, ensure_ascii=False), "," if k_i < len(v[k]) - 1 else ""))
            lines.append("    ]%s" % ("," if i < len(keys) - 1 else ""))
        else:
            lines.append("    %s: %s%s" % (json.dumps(k), json.dumps(v[k], ensure_ascii=False), "," if i < len(keys) - 1 else ""))
    lines.append("  }")
    return "\n".join(lines)


def splice(text, block):
    """Replace the file's top-level "voucher" block (it must be the last key) with `block`."""
    start = text.find("\n  \"voucher\": {")
    if start < 0:
        raise SystemExit("data/challenge_mode.json has no top-level voucher block to write into")
    end = text.find("\n  }\n}", start)
    if end < 0:
        raise SystemExit("data/challenge_mode.json: the voucher block must be the last top-level key")
    return text[:start + 1] + block + text[end + 4:]


def report(c):
    print("total $%d = Oak cash $%d + kits $%d + power kit $%d" % (c["total"], c["oak_cash"], c["kits_total"],
                                                                 c["power_kit_value"]))
    cum = 0
    for g in c["schedule"]:
        cum += g["value"]
        print("  %-16s $%6d  (cash $%d, kits for legs %s)  cumulative $%d"
              % (g["at"], g["value"], g["cash"], g["kits"] or "-", cum))
    print("  back-loaded (ECONOMY_OVERHAUL 4.4): %s" % c["back_loaded_was"])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--write", action="store_true")
    p.add_argument("--check", action="store_true")
    a = p.parse_args(argv)
    text = CHALLENGE.read_text(encoding="utf-8")
    doc = json.loads(text)
    c = compute(doc)
    if a.check:
        if doc["voucher"].get("computed") != c:
            print("data/challenge_mode.json voucher.computed is not what tools/challenge_voucher.py computes: run --write")
            return 1
        print("voucher current: total $%d over %d grants" % (c["total"], len(c["schedule"])))
        return 0
    if a.write:
        v = dict(doc["voucher"])
        v["computed"] = c
        new = splice(text, render(v))
        json.loads(new)
        if new != text:
            CHALLENGE.write_text(new, encoding="utf-8", newline="\n")
        print("data/challenge_mode.json voucher %s" % ("written" if new != text else "unchanged"))
        return 0
    report(c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
