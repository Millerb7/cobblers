#!/usr/bin/env python
"""The Challenge voucher's schedule, computed from data: data/challenge_mode.json `voucher.computed`.

The owner, 2026-10-22: "i dont see enough cushion for challenge players, they should have it easier." The rule
(data/challenge_mode.json voucher.rule, from the build brief of the same day):

  BASKET(t) = six Pokemon trained at tier t -- each a level raise, an EV spread and all six IVs, at
              data/training_services.json's price_by_tier[t] -- plus two answer TMs for the next boss at the TM
              shelf's tier-t unit price (data/markets.json price_policies.tm_tier, tools/markets.py tm_tier_unit),
              counted only when some tier-t shelf line answers that boss (no shelf sells TMs at tier 0).
  GRANT     = BASKET(t) x voucher.rule.multiplier (1.5), rounded UP to voucher.rule.round_to, where t is the badges
              the player holds when the grant is paid: Oak's at the mode choice is tier 0 (the first leg), the gym-N
              clear is tier N (the leg it opens).

Every price the basket reads rises with badges (the owner, 2026-10-21), so the grants RISE too: the old front-loading
(the owner after the 2026-10-10 overnight, decision (2): "more per gym early, the same total by the end") cannot hold
together with "each grant covers its badge's basket" -- a front-loaded schedule would either pay gym 1 the largest
basket of the game or pay later gyms less than their basket. The brief allows the later grants to be larger; this
tool chooses the rule over the shape and says so in the block it writes (`shape_chosen`).

THE GRANT itself is built elsewhere: Oak's step by the Challenge confirm (data/quests.json effect challenge_voucher,
whose cash --check holds to Oak's step), the eight gym steps by tools/progression_pack.py voucher_grants, in cash.

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
SERVICES = ROOT / "data" / "training_services.json"
GENERATED_BY = "tools/challenge_voucher.py --write"
STEPS = [("oak_mode_choice", 0)] + [("gym%d_cleared" % n, n) for n in range(1, 9)]
# the boss a tier-t answer line answers: data/markets.json counter lines carry it in `answers`, by its first word
NEXT_BOSS = {1: "kanto_misty", 2: "kanto_ltsurge", 3: "kanto_erika", 4: "kanto_koga", 5: "kanto_sabrina",
             6: "kanto_blaine", 7: "kanto_giovanni", 8: "the League"}


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def team_cost(services, t, team):
    """One tier's training for `team` Pokemon: a raise, an EV spread and every IV each."""
    s = services["services"]
    per = int(s["raise"]["price_by_tier"][str(t)]) + int(s["ev"]["price_by_tier"][str(t)]) \
        + 6 * int(s["iv"]["price_per_stat_by_tier"][str(t)])
    return team * per


def tm_cost(markets, t, n):
    """n answer TMs at tier t, or 0 when no tier-t shelf line answers the next boss."""
    import markets as M
    answers = [it for _c, it, _h in M.tm_tier_lines(markets)
               if it.get("tier") == t and str(it.get("answers", "")).startswith(NEXT_BOSS.get(t, "?"))]
    return (n * M.tm_tier_unit(markets, t), len(answers)) if answers else (0, 0)


def compute(cdoc=None, markets=None, services=None):
    cdoc = cdoc if cdoc is not None else read(CHALLENGE)
    markets = markets if markets is not None else read(MARKETS)
    services = services if services is not None else read(SERVICES)
    rule = cdoc["voucher"]["rule"]
    mult = Fraction(str(rule["multiplier"]))
    step = int(rule["round_to"])
    team, tms = int(rule["team"]), int(rule["answer_tms"])
    sched = []
    for at, t in STEPS:
        train = team_cost(services, t, team)
        tm, lines = tm_cost(markets, t, tms)
        basket = train + tm
        value = int(-(-(mult * basket) // step)) * step
        sched.append({"at": at, "tier": t, "training": train, "tms": tm, "answer_lines": lines, "basket": basket,
                      "value": value, "cash": value})
    total = sum(g["value"] for g in sched)
    vals = [g["value"] for g in sched[1:]]
    rising = all(b >= a for a, b in zip(vals, vals[1:]))
    return {
        "generated_by": GENERATED_BY,
        "rule": "grant = basket(t) x %s rounded up to $%d; basket(t) = %d Pokemon x (raise + EV spread + six IVs) at "
                "data/training_services.json price_by_tier[t] + %d answer TMs at data/markets.json price_policies.tm_tier's "
                "tier-t price (none at tier 0: no shelf sells TMs there); t = badges held when paid"
                % (rule["multiplier"], step, team, tms),
        "shape_chosen": "RISING%s: each grant covers its own badge's basket (the owner, 2026-10-22), and every price in "
                        "the basket rises with badges (2026-10-21), so the later grants are larger. Front-loading (the "
                        "owner's 2026-10-10 decision (2)) would pay gym 1 more than its basket or a later gym less than "
                        "its own, and the 2026-10-22 brief lets the later grants be larger"
                        % ("" if rising else " (NOT monotone: a basket fell)"),
        "total": total,
        "schedule": sched,
    }


def problems(c, rule):
    """The schedule's own invariants, beyond equality with the file: every grant at least multiplier x its basket and
    a whole multiple of round_to, Oak first, then the eight gyms in order."""
    out = []
    mult, step = Fraction(str(rule["multiplier"])), int(rule["round_to"])
    if [g["at"] for g in c["schedule"]] != [s for s, _ in STEPS]:
        out.append("the steps are not Oak then gyms 1-8: %s" % [g["at"] for g in c["schedule"]])
    for g in c["schedule"]:
        if g["value"] < mult * g["basket"] or g["value"] % step or g["cash"] != g["value"]:
            out.append("%s: value %d against basket %d" % (g["at"], g["value"], g["basket"]))
    return out


OAK_GIFTS_FN = "cobblers:challenge/oak_gifts"


def gift_problems(doc, markets, quests):
    """data/challenge_mode.json tm_gifts against the shelves (the owner, 2026-10-22: "challenge mode should be given
    tms"): each gym step gives exactly the tier-N shelf lines that answer the boss after gym N (the lines tm_cost reads
    for the basket), the Oak step names the first boss and is called by Oak's voucher transition, once."""
    import markets as M
    g = doc.get("tm_gifts")
    if not g:
        return ["data/challenge_mode.json has no tm_gifts block"]
    out = []
    steps = g.get("by_step") or {}
    if list(steps) != [s for s, _ in STEPS]:
        out.append("the steps are not Oak then gyms 1-8: %s" % list(steps))
    for at, t in STEPS:
        if at == "oak_mode_choice":
            continue
        want = sorted({it["item"] for _c, it, _h in M.tm_tier_lines(markets)
                       if it.get("tier") == t and str(it.get("answers", "")).startswith(NEXT_BOSS[t])})
        got = sorted((steps.get(at) or {}).get("items") or [])
        if got != want:
            out.append("%s gives %s, the tier-%d shelf answers %s with %s" % (at, got, t, NEXT_BOSS[t], want))
    oak = steps.get("oak_mode_choice") or {}
    if not str(oak.get("boss", "")).startswith("kanto_brock") or not oak.get("items"):
        out.append("oak_mode_choice must give the first boss's (kanto_brock) answers")
    trans = [t for q in quests["quests"] for t in q.get("transitions") or []
             if any(e.get("kind") == "challenge_voucher" and e.get("at") == "oak_mode_choice" for e in t.get("effects") or [])]
    calls = [t for t in trans if any(e.get("kind") == "function" and e.get("function") == OAK_GIFTS_FN
                                     for e in t.get("effects") or [])]
    if len(trans) != 1 or len(calls) != 1:
        out.append("Oak's voucher transition must call %s once (found %d voucher transition(s), %d calling it)"
                   % (OAK_GIFTS_FN, len(trans), len(calls)))
    return out


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
    print("total $%d over %d grants (%s)" % (c["total"], len(c["schedule"]), c["shape_chosen"].split(":")[0]))
    cum = 0
    for g in c["schedule"]:
        cum += g["value"]
        print("  %-16s tier %d  training $%6d + TMs $%5d = basket $%6d  -> grant $%6d  cumulative $%d"
              % (g["at"], g["tier"], g["training"], g["tms"], g["basket"], g["value"], cum))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--write", action="store_true")
    p.add_argument("--check", action="store_true")
    a = p.parse_args(argv)
    text = CHALLENGE.read_text(encoding="utf-8")
    doc = json.loads(text)
    c = compute(doc)
    bad = problems(c, doc["voucher"]["rule"])
    if bad:
        for b in bad:
            print("PROBLEM %s" % b)
        return 1
    if a.check:
        if doc["voucher"].get("computed") != c:
            print("data/challenge_mode.json voucher.computed is not what tools/challenge_voucher.py computes: run --write")
            return 1
        # every quest effect that pays a voucher step must pay that step's cash (tools/compile_dialogue.py
        # challenge_voucher): a moved schedule would otherwise leave Oak paying the old amount
        steps = {g["at"]: g["cash"] for g in c["schedule"]}
        quests = json.loads((CHALLENGE.parent / "quests.json").read_text(encoding="utf-8"))
        paid = [e for q in quests["quests"] for t in q.get("transitions") or [] for e in t.get("effects") or []
                if e.get("kind") == "challenge_voucher"]
        wrong = [e for e in paid if steps.get(e.get("at")) != e.get("cash")]
        if wrong:
            for e in wrong:
                print("data/quests.json challenge_voucher at %r pays %r, the schedule says %r"
                      % (e.get("at"), e.get("cash"), steps.get(e.get("at"))))
            return 1
        gift_bad = gift_problems(doc, read(MARKETS), quests)
        for b in gift_bad:
            print("PROBLEM tm_gifts: %s" % b)
        if gift_bad:
            return 1
        print("voucher current: total $%d over %d grants; %d paid by quest effects, matching; TM gifts: %d steps, "
              "%d TMs, each gym's the shelf's answer set" % (c["total"], len(c["schedule"]), len(paid),
                                                             len(doc["tm_gifts"]["by_step"]),
                                                             sum(len(s["items"]) for s in doc["tm_gifts"]["by_step"].values())))
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
