#!/usr/bin/env python
"""Trainer income by leg and by badge, measured from the trainer files the game reads, under CobbleDollars' payout.

Unit U0 of docs/mechanics/ECONOMY_OVERHAUL.md (section 9). It replaces data/markets.json `income_basis` model B
(RELAYED from docs/research/INCOME_MEASUREMENT.md, a linear $13 a level that the jar contradicts) with a model computed
from data. It writes only that block; `python tools/markets.py prices --write` then re-prices the income-gate lines.

THE FORMULA (docs/research/notes/paid-services-and-npc-payouts.md B2, read from CobbleDollars' battleVictory bytecode;
VERIFIED there, RELAYED here). Over the losing actor's Pokemon list, levels L_i, S = sum(L_i):

    B      = max(1, int(5 * S * sum(L_i / 50.0)))       = S^2 / 10 before truncation
    amount = B + random.nextBetween(B / 2, 2 * B)         (inclusive both ends: ASSUMED by the note)
    credit = floor(amount * cobbleDollarsIncomeMultiplier) (1.25, modpack/config/cobbledollars/common.json)

  Derivation of the expected credit: 5 * S * (S / 50) = S^2 / 10 = B. A uniform draw on [B/2, 2B] has mean
  (B/2 + 2B) / 2 = 1.25 B, so E[amount] = B + 1.25 B = 2.25 B. Then E[credit] = 1.25 * 2.25 * S^2 / 10
  = 2.8125 S^2 / 10 = 0.28125 S^2. That continuous figure is what the tables carry (`expected` below); the exact
  expectation under the integer truncations (`exact`, every draw enumerated) is a few dollars lower per battle and is
  reported beside it so the difference is visible, never folded in.

THE ROSTERS: tools/route_trainers.files(), the emitter's own in-memory pack -- the same files build/datapacks/
cobblers_trainers is written from, and the same source tools/player_guide_battles.py reads. Not data/trainers.json
directly, because the pack is what the game reads: the eight leaders and the League are emitted at their upstream ids
(kanto_brock, ...), and Challenge mode's copies are the `<id><suffix>` files tools/challenge_mode.py adds. A trainer with
no Challenge file (the mansion guardians) fights the same team in both modes.

WHO COUNTS, per leg N (on the way to badge N), in the player guide's meeting order (tools/player_guide_battles.py):
  - the route trainers of the route whose to_town is gymN_town (data/routes.json), by their seat's walked_distance
    (data/route_trainers.json, data/late_route_trainers.json); optional off-road trainers included, as the guide does;
  - leg 1 also: the Gastly mansion's five guardians (data/mansion_guardians.json, on Route 1; the guide leaves them
    out, the design's section 1.1 counts them);
  - the gym's juniors (data/gym_junior_trainers.json), by trainer_order (the guide's measured walk order needs the
    replayed hall builds; order does not change a leg's sum);
  - the leader (data/gym_trainers.json, emitted at its upstream id).
  Then Victory Road (data/vr_trainers.json, by route_progress) and the League (data/league_trainers.json, by order).

WHAT IT DOES NOT COUNT, on purpose, and says so in the block it writes:
  - wild battles: CobbleDollars pays them under the same formula (earnCobbleDollarsFromWildPokemon true). Whether they
    stay on is owner question 1 (ECONOMY_OVERHAUL.md P2); every figure here assumes they pay nothing;
  - Heaven's Arena (data/arena_trainers.json, unseated, its own purse: ECONOMY_OVERHAUL.md section 6);
  - the Compact HQ tower's seven (data/hq_trainers.json): after badge 8, reported under `post_badge_8`, not in any
    badge's figure;
  - Cobbleverse's own roaming trainers and anything a donor template places: this enumerates OUR pack only;
  - rematches: every counted trainer is beaten once.

Nothing here is verified in game. One payout read back in a running server against `exact` is EXP-A's job.

  python tools/income_model.py            # print the table, both modes, against the design's columns
  python tools/income_model.py --write    # write the block into data/markets.json income_basis
  python tools/income_model.py --check    # exit 1 if data/markets.json's block is not what this computes
  python tools/income_model.py --json     # the block, as JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

MARKETS = ROOT / "data" / "markets.json"
CD_CONFIG = ROOT / "modpack" / "config" / "cobbledollars" / "common.json"
TRAINERS = "data/rctmod/trainers/%s.json"
GENERATED_BY = "tools/income_model.py --write"

# ECONOMY_OVERHAUL.md section 1.1 "Cumulative" (Normal) and section 4.1 "Challenge leg income": the design's hand
# arithmetic (COMPUTED there, no shell), carried here only to be compared, never to be matched
DESIGN_NORMAL_CUM = {1: 4033, 2: 8609, 3: 18576, 4: 34991, 5: 56424, 6: 90132, 7: 134330, 8: 202835, "vr": 252176,
                     "league": 427227}
DESIGN_CHALLENGE_LEG = {1: 8691, 2: 11304, 3: 20175, 4: 31066, 5: 35191, 6: 57730, 7: 73867, 8: 100823, "vr": 58152}


def doc(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def multiplier():
    cfg = json.loads(CD_CONFIG.read_text(encoding="utf-8"))
    return cfg["cobbleDollarsIncomeMultiplier"]


def kotlin_b(levels):
    """B exactly as battleVictory computes it: an Int level sum times a Double running sum of level / 50.0."""
    s = sum(levels)
    f = 0.0
    for lv in levels:
        f += lv / 50.0
    return max(1, int(5 * s * f))


def expected(levels, mult=1.25):
    """The continuous expectation 1.25 * 2.25 * S^2 / 10, scaled to `mult` (0.28125 S^2 at 1.25)."""
    s = sum(levels)
    return float(Fraction(s * s, 10) * Fraction(9, 4) * Fraction(mult))


_EXACT = {}


def exact(levels, mult=1.25):
    """The exact expectation: every draw of nextBetween(B/2, 2B) (Kotlin Int division for B/2), floor(amount * mult)."""
    b = kotlin_b(levels)
    key = (b, mult)
    if key not in _EXACT:
        lo, hi = b // 2, 2 * b
        m = Fraction(mult)
        tot = sum(int((b + u) * m) for u in range(lo, hi + 1))
        _EXACT[key] = tot / (hi - lo + 1)
    return _EXACT[key]


def legs():
    """[(leg key, [(trainer id, upstream-or-own id in the pack, kind)])] in meeting order."""
    import route_trainers as RT
    recs = {r["id"]: r for r in doc("data/trainers.json")["trainers"]}
    for e in doc("data/mansion_guardians.json")["trainers"] + doc("data/vr_trainers.json")["trainers"]:
        if "rct" in e and e["id"] not in recs:
            recs[e["id"]] = e
    routes = {r["id"]: r for r in doc("data/routes.json")["routes"]}
    by_route = {}
    for name in ("data/route_trainers.json", "data/late_route_trainers.json"):
        for s in doc(name)["trainers"]:
            by_route.setdefault(recs[s["id"]]["route_id"], []).append((s["walked_distance"], s["id"]))
    for s in doc("data/vr_trainers.json")["trainers"]:
        by_route.setdefault(recs[s["id"]]["route_id"], []).append((s["route_progress"], s["id"]))
    for lst in by_route.values():
        lst.sort()
    leg_route = {r["to_town"]: rid for rid, r in routes.items()}
    juniors = {}
    for s in doc("data/gym_junior_trainers.json")["trainers"]:
        juniors.setdefault(s["gym"], []).append(s["id"])
    for g in juniors:
        juniors[g].sort(key=lambda t: (recs[t].get("trainer_order") or 0, t))
    over, held = RT.overrides()
    if held:
        raise SystemExit("held overrides, nothing emitted for them, so a leg would be short: %s" % held)
    leaders = {e["order"]: e for e in doc("data/gym_trainers.json")["trainers"]}
    league = sorted(doc("data/league_trainers.json")["trainers"], key=lambda e: e["order"])
    out = []
    for n in range(1, 9):
        rows = [(t, t, "route") for _d, t in by_route.get(leg_route["gym%d_town" % n], [])]
        if n == 1:
            rows += [(e["id"], e["id"], "mansion") for e in doc("data/mansion_guardians.json")["trainers"]]
        rows += [(t, t, "junior") for t in juniors.get("gym%d" % n, [])]
        e = leaders[n]
        rows.append((e["id"], e["upstream_trainer_id"], "leader"))
        out.append((n, rows))
    out.append(("vr", [(t, t, "route") for _d, t in by_route.get(leg_route["league"], [])]))
    out.append(("league", [(e["id"], e["upstream_trainer_id"], "league") for e in league]))
    out.append(("hq_tower", [(e["id"], e["id"], "hq") for e in doc("data/hq_trainers.json")["trainers"]]))
    return out


def measure(mult=None):
    import route_trainers as RT
    import challenge_mode as CM
    mult = multiplier() if mult is None else mult
    pack = RT.files()
    sfx = CM.suffix()
    counted = set()
    model = {"multiplier": mult, "suffix": sfx, "legs": []}
    for leg, rows in legs():
        rowout = []
        for tid, fid, kind in rows:
            n = pack.get(TRAINERS % fid)
            if n is None:
                raise SystemExit("%s: no trainer file %s in the emitted pack" % (tid, TRAINERS % fid))
            c = pack.get(TRAINERS % (fid + sfx))
            nl = [m["level"] for m in n["team"]]
            cl = [m["level"] for m in c["team"]] if c else nl
            if tid in counted:
                raise SystemExit("%s is counted twice" % tid)
            counted.add(tid)
            rowout.append({"id": tid, "file": fid, "kind": kind, "challenge_file": (fid + sfx) if c else None,
                           "normal": {"S": sum(nl), "expected": expected(nl, mult), "exact": exact(nl, mult)},
                           "challenge": {"S": sum(cl), "expected": expected(cl, mult), "exact": exact(cl, mult)}})
        model["legs"].append({"leg": leg, "trainers": rowout})
    # every trainer file in the pack is either counted or named as not counted
    ids = {k[len("data/rctmod/trainers/"):-5] for k in pack if k.startswith("data/rctmod/trainers/")}
    files_counted = {r["file"] for L in model["legs"] for r in L["trainers"]} | \
                    {r["challenge_file"] for L in model["legs"] for r in L["trainers"] if r["challenge_file"]}
    model["not_counted_files"] = sorted(ids - files_counted)
    return model


def totals(model, mode, field="expected"):
    leg, cum, run = {}, {}, 0.0
    for L in model["legs"]:
        v = sum(r[mode][field] for r in L["trainers"])
        leg[L["leg"]] = v
        if L["leg"] != "hq_tower":
            run += v
            cum[L["leg"]] = run
    return leg, cum


def block(model, old):
    """The data/markets.json income_basis block. target_ratio, target_source and counts are the curve's, not the
    income model's, and are carried from the block being replaced."""
    nl, nc = totals(model, "normal")
    cl, cc = totals(model, "challenge")
    xl, xc = totals(model, "normal", "exact")
    yl, yc = totals(model, "challenge", "exact")
    r = lambda d, keys: {str(k): int(round(d[k])) for k in keys}
    badges = range(1, 9)
    S = lambda mode: {str(L["leg"]): [t[mode]["S"] for t in L["trainers"]] for L in model["legs"]}
    prev = {k: old[k] for k in ("source", "cumulative_by_badge", "leg_by_badge") if k in old}
    if old.get("generated_by") == GENERATED_BY:
        prev = old.get("superseded_model_b") or prev
    else:
        prev["superseded_by"] = "tools/income_model.py (unit U0, 2026-10-10): model B was linear in levels; the jar pays quadratically"
    return {
        "relayed": False,
        "generated_by": GENERATED_BY,
        "source": "measured from data: the trainer files tools/route_trainers.files() emits (the pack the game reads; "
                  "Challenge = tools/challenge_mode.py's <id>%s copies) under CobbleDollars' battleVictory payout" % model["suffix"],
        "formula": "per battle won against an NPC, S = the losing team's level sum: B = max(1, int(5*S*sum(L/50))) = "
                   "S^2/10; amount = B + nextBetween(B/2, 2B); credit = floor(amount * %s). Expected credit = %s * "
                   "2.25 * S^2/10 = %s*S^2 (a uniform draw on [B/2, 2B] has mean 1.25B, so E[amount] = 2.25B)"
                   % (model["multiplier"], model["multiplier"], float(Fraction(9, 40) * Fraction(model["multiplier"]))),
        "formula_source": "docs/research/notes/paid-services-and-npc-payouts.md B2 (CobbleDollars battleVictory "
                          "bytecode 370-567, VERIFIED there; the uniform inclusive draw is ASSUMED there); "
                          "cobbleDollarsIncomeMultiplier from modpack/config/cobbledollars/common.json",
        "verified_in_game": False,
        "unverified": "no payout has been read back in game against this model. The two measured payouts ($732, $600, "
                      "docs/research/INCOME_MEASUREMENT.md) were against UPSTREAM kanto_brock at multiplier 0.5, not "
                      "our roster (ECONOMY_OVERHAUL.md P1)",
        "excluded": "wild battles (CobbleDollars pays them under the same formula while earnCobbleDollarsFromWildPokemon "
                    "is true: owner question 1, ECONOMY_OVERHAUL.md P2; every figure here assumes they pay nothing); "
                    "Heaven's Arena; rematches; Cobbleverse's roaming trainers and donor-template trainers; the Compact "
                    "HQ tower (post_badge_8, not in any badge)",
        "counts_trainers": "leg N: Route N's trainers (optional ones included), Route 1's five mansion guardians in "
                           "leg 1, gym N's juniors, gym N's leader; each beaten once",
        "cumulative_by_badge": r(nc, badges),
        "leg_by_badge": r(nl, badges),
        "challenge": {"cumulative_by_badge": r(cc, badges), "leg_by_badge": r(cl, badges)},
        "post_badge_8": {"normal": {"victory_road": int(round(nl["vr"])), "league": int(round(nl["league"])),
                                    "hq_tower": int(round(nl["hq_tower"])),
                                    "cumulative_through_league": int(round(nc["league"]))},
                         "challenge": {"victory_road": int(round(cl["vr"])), "league": int(round(cl["league"])),
                                       "hq_tower": int(round(cl["hq_tower"])),
                                       "cumulative_through_league": int(round(cc["league"]))}},
        "exact_expectation": {"why": "the same expectation with battleVictory's integer truncations, every draw "
                                     "enumerated; the tables above use the continuous figure",
                              "normal_cumulative_by_badge": r(xc, badges),
                              "challenge_cumulative_by_badge": r(yc, badges)},
        "level_sums": {"normal": S("normal"), "challenge": S("challenge")},
        "target_ratio": old["target_ratio"],
        "target_source": old["target_source"],
        "counts": old["counts"],
        "superseded_model_b": prev,
    }


def render(b):
    """The block as data/markets.json writes it: two-space indent, one key a line, each value on its own line."""
    lines = ["  \"income_basis\": {"]
    items = list(b.items())
    for i, (k, v) in enumerate(items):
        if isinstance(v, dict) and k in ("challenge", "post_badge_8", "exact_expectation", "level_sums",
                                         "superseded_model_b"):
            lines.append("    %s: {" % json.dumps(k))
            sub = list(v.items())
            for j, (k2, v2) in enumerate(sub):
                lines.append("      %s: %s%s" % (json.dumps(k2), json.dumps(v2, ensure_ascii=False),
                                                 "," if j < len(sub) - 1 else ""))
            lines.append("    }" + ("," if i < len(items) - 1 else ""))
        else:
            lines.append("    %s: %s%s" % (json.dumps(k), json.dumps(v, ensure_ascii=False),
                                           "," if i < len(items) - 1 else ""))
    lines.append("  },")
    return lines


def write(b, path=MARKETS):
    text = path.read_text(encoding="utf-8")
    rows = text.split("\n")
    start = [i for i, r in enumerate(rows) if r == "  \"income_basis\": {"]
    if len(start) != 1:
        raise SystemExit("%s: expected one '  \"income_basis\": {' line, found %d" % (path, len(start)))
    i = start[0]
    end = next(j for j in range(i + 1, len(rows)) if rows[j] in ("  },", "  }"))
    new = rows[:i] + render(b) + rows[end + 1:]
    out = "\n".join(new)
    json.loads(out)
    if out != text:
        path.write_text(out, encoding="utf-8", newline="\n")
        return True
    return False


def report(model):
    nl, nc = totals(model, "normal")
    cl, cc = totals(model, "challenge")
    xl, xc = totals(model, "normal", "exact")
    print("multiplier %s; expected credit %.5f * S^2 per battle" % (model["multiplier"],
                                                                   float(Fraction(9, 40) * Fraction(model["multiplier"]))))
    print("%-8s %-7s %10s %10s %10s %7s | %10s %10s %10s %7s" % ("leg", "battles", "N leg", "N cum", "design", "dev",
                                                                 "C leg", "C cum", "design leg", "dev"))
    for L in model["legs"]:
        k = L["leg"]
        dn = DESIGN_NORMAL_CUM.get(k)
        dc = DESIGN_CHALLENGE_LEG.get(k)
        print("%-8s %-7d %10.0f %10s %10s %7s | %10.0f %10s %10s %7s" % (
            k, len(L["trainers"]), nl[k], "%.0f" % nc[k] if k in nc else "-", dn or "-",
            "%+.1f%%" % (100.0 * (nc[k] / dn - 1)) if dn else "-", cl[k], "%.0f" % cc[k] if k in cc else "-",
            dc or "-", "%+.1f%%" % (100.0 * (cl[k] / dc - 1)) if dc else "-"))
    print("exact (truncated) normal cumulative at badge 8: %.0f vs continuous %.0f" % (xc[8], nc[8]))
    for L in model["legs"]:
        print("  %s N: %s" % (L["leg"], ", ".join("%s=%d" % (t["id"], t["normal"]["S"]) for t in L["trainers"])))
        print("  %s C: %s" % (L["leg"], ", ".join("%d" % t["challenge"]["S"] for t in L["trainers"])))
    if model["not_counted_files"]:
        print("trainer files in the pack not counted: %s" % ", ".join(model["not_counted_files"]))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--write", action="store_true", help="write the block into data/markets.json income_basis")
    p.add_argument("--check", action="store_true", help="exit 1 if data/markets.json's block differs")
    p.add_argument("--json", action="store_true", help="print the block as JSON")
    a = p.parse_args(argv)
    model = measure()
    old = json.loads(MARKETS.read_text(encoding="utf-8"))["income_basis"]
    b = block(model, old)
    if a.json:
        print(json.dumps(b, indent=2))
        return 0
    if a.check:
        if old != b:
            print("data/markets.json income_basis is not what tools/income_model.py computes: run --write")
            return 1
        print("income_basis current")
        return 0
    if a.write:
        print("data/markets.json income_basis %s" % ("written" if write(b) else "unchanged"))
        return 0
    report(model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
