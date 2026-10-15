#!/usr/bin/env python
"""The Trading Post (the Produce Buyer, generalised): goods sold to a dialogue NPC at a FIXED spine price, with no cap,
no allowance and no price that falls with badges. Generated from data/produce_buyer.json into the world-local datapack
build/datapacks/cobblers_produce_buyer; the NPCs are placed by tools/reapply.py R18PB.

docs/mechanics/ECONOMY_V2.md 2.2 and the owner's answers (section 7, 2026-10-13): E3 "no cap: farming is allowed",
E1 cobble at its spine worth, E2 two ways to sell, E6 arena trophies never sellable, E8 a Trading Post at every town
square that has a market and at the ports, E10 no co-op pooling. The bank (tools/bank.py) buys the minerals; this is
where everything else a player can dig, cut, grow, catch or find sells.

Every piece is one already in use (tools/ferries.py is the pattern, read for it):
  the buyer      a Cobblemon NPC whose class opens a dialogue compiled in memory by tools/compile_dialogue.py's
                 compile_conversation (the ferryman's shape): one page, "sell everything I can", one option per crate
                 kind, and "Not today."
  a crate        a function run as and at the player by the option (compile_dialogue "function"):
                   1. a second submit inside the cooldown does nothing
                   2. count the crate's items (`clear @s <item> 0`, ASSUMED to count without removing: EXP-061) and
                      refuse when short, nothing taken
                   3. the click is spent (the cooldown starts); read the balance (`cobbledollars query @s`)
                   4. TAKE the crate (`clear @s <item> <count>`); unless exactly <count> went, short_take records the
                      taken share of the price as owed and stops, nothing paid
                   5. PAY through `$cobbledollars give @s $(amount)` and re-read the balance: unless it rose by exactly
                      the price, record the price as owed and say so
  everything     sell/all: the cooldown, the balance, then per category (sellall/<id>) a dry-run count, the whole
                 crates' worth of items divided out, a BOUNDED take through the macro take/<id> (`clear @s <item> $(n)`),
                 the taken share credited to #total; then every specimen (sellall/specimens: `clear @s <item>`, pieces
                 x price); then ONE pay of #total and the same balance re-read. Nothing returns between the first take
                 and the pay except the "nothing taken" gate.
The checks (offline, fail closed; the independent audit is unit B4's, not this file's):
  static   every crate priced from its declared rate and the bank's own tier wage (the spine), no item in two crates,
           none in never_sold, none bought by the bank, no authored seller at or under its unit worth (tools/bank.py
           sell_points), the specimens re-derived from docs/research/notes/drops-1.8.0.json
  output   no allowance anywhere, every sale counts before it takes, takes before it pays, pays once and verifies after
           it, charges nothing (`cobbledollars remove` never appears) and passes tools/function_limits.py
  seats    Hollin's: recomputed from tools/apricorn_farm.py's plan. A town square's: held to the squares builder's own
           model (tools/plaza_centre.py Town and plan_town) plus the floors in the data
  closure  (optional, needs jars) every crate item and specimen against the cheapest way to BUY it by any recipe
           (tools/economy_audit.py cheapest), and against recipes whose inputs are all priced

  python tools/produce_buyer.py build   [--out DIR]                     write the pack (no heightmap needed)
  python tools/produce_buyer.py check   [--source-root R] [--server-dir S] [--jars-dir J] [--vanilla-jar V]
  python tools/produce_buyer.py prices                                   the table: unit worth, crate worth, P
  python tools/produce_buyer.py seats   [--source-root R]                propose a seat per unseated square site

What it does NOT cover: whether the dialogue opens and the functions run in game (EXP-061); a seller a donor template
places that no data file names, and the trader templates' shops unless tools/bank.py is given a server dir; a recipe the
jars do not carry; whether a kitchen/pharmacy input's rate is true (milk, hearty grains, vivichoke and the rest of the
`harvest` class are ESTIMATES, data/produce_buyer.json kitchen_pharmacy.classes): the independent audit cannot price an
input nothing sells, so those goods' margins rest on the estimate and the audit reports "no member is obtainable with
money" for them. Kitchen and pharmacy goods are `crates` entries marked "kp" and derived by `goods`; `check` re-derives
them (kp_problems) and, with --jars-dir, reads every recipe they cite back from the jars.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "produce_buyer.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_produce_buyer"
ITEM = re.compile(r"[a-z0-9_.\-]+:[a-z0-9_/.\-]+")
ID = re.compile(r"[a-z0-9_]+")
NS = "cobblers"
FOLDER = "produce_buyer"
RESERVED_IDS = ("all", "specimens")
NPC_CLEAR = 3.5     # tools/markets.py NPC_CLEAR: reapply's npc action counts cobblemon:npc within 2 blocks
MIN_ROUTE = 3.0     # tools/npc_seats.py MIN_ROUTE
WORLD_READS: set = set()   # the ground rule: every seat comes from a plan over the canonical heightmap
TANK_MARGIN = 1     # cells kept clear round a piece of the square (a stall's posts, the centrepiece)


class BuyerError(SystemExit):
    pass


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fn_id(rel):
    return "%s:%s/%s" % (NS, FOLDER, rel)


def fn_path(rel):
    return "data/%s/function/%s/%s.mcfunction" % (NS, FOLDER, rel)


def tag_id(crate):
    return "#%s:%s/%s" % (NS, FOLDER, crate["id"])


def predicate(crate):
    """The `clear` item argument: one item, the jar's tag the crate names, or this pack's tag of its items."""
    if crate.get("tag"):
        return crate["tag"]
    if len(crate["items"]) == 1:
        return crate["items"][0]
    return tag_id(crate)


def text(s, color="gray"):
    return json.dumps({"text": s, "color": color}, ensure_ascii=False)


def fill(template, **kw):
    for k, v in kw.items():
        template = template.replace("{%s}" % k, str(v))
    if re.search(r"\{[a-z_]+\}", template):
        raise BuyerError("message %r names a placeholder this tool does not fill" % template)
    return template


# ------------------------------------------------------------------------------------------------------- the spine
def wages():
    """{tier: the tier's typical hour in dollars}, from data/bank.json's own rates (tools/bank.py tier_hours), never a
    copy: the spine is 'consistent by construction' only while one place says what an hour of a tier is worth."""
    import bank
    return {k: v[0] for k, v in bank.tier_hours(bank.load()).items()}


def round_half_up(x):
    return int(math.floor(x + 0.5))


def crate_price(crate, wage):
    """worth($) = count x W(tier) / rate_per_hour, a whole dollar per crate (ECONOMY_V2 1.1)."""
    return round_half_up(crate["count"] * wage[crate["tier"]] / crate["rate_per_hour"])


def prices(doc, wage=None):
    """{crate id: dollars a crate pays}."""
    wage = wage or wages()
    return {c["id"]: crate_price(c, wage) for c in doc["crates"]}


def unit_worth(crate, price):
    return price / crate["count"]


def notes_of(doc):
    return json.loads((ROOT / doc["specimens"]["notes_file"]).read_text(encoding="utf-8"))


def best_drop(notes, item):
    """The best per-defeat drop chance of an item among the species our world spawns (docs/research/notes/
    drops-1.8.0.json: a dropper is [species, form, per_defeat, ranch_per_hour, live]); None with no live dropper."""
    rec = notes["items"].get(item)
    live = [d[2] for d in (rec or {}).get("droppers") or [] if d[4]]
    return max(live) if live else None


def specimen_prices(doc, wage=None, notes=None):
    """{item: dollars a piece pays}: W(early) / (ko_per_hour x best chance), rounded, from $1 to cap_p x $100."""
    sp = doc["specimens"]
    wage = wage or wages()
    notes = notes or notes_of(doc)
    out = {}
    for item in sp["items"]:
        best = best_drop(notes, item)
        if not best:
            raise BuyerError("specimen %s has no live dropper in %s" % (item, sp["notes_file"]))
        raw = wage[sp["wage_tier"]] / (sp["ko_per_hour"] * best)
        out[item] = max(1, min(int(sp["cap_p"]) * 100, round_half_up(raw)))
    return out


# ---------------------------------------------------------------------------------------------------------- kitchen and pharmacy
# ECONOMY_V2 2.2's "crafts rule": a crafted good is worth its inputs' worth plus a step cost, max($2, 1%) a craft, shared
# over the craft's yield. Every INPUT has a worth on the spine (a crate unit; a rate an hour of one kind of gathering, from
# the record's `classes`; or a derivation through another recipe). A good is sold as a crate of `n` (a whole-dollar price
# rounded DOWN, never up) and its crate is an ordinary entry of `crates` carrying `"kp": true` and `"menu": false`, so the
# independent audit (tools/economy_audit.py tp_expected / buyer_checks) reads it with no special case: count x W(tier) /
# rate is the price, and rate_per_hour here is back-solved from the derived price. `check` re-derives the price from the
# record's inputs and fails when a crate drifts from it.
KP_COUNTS = (1, 2, 4, 8, 16, 32, 64)


def kp(doc):
    return doc.get("kitchen_pharmacy") or {}


def _frac(x):
    from fractions import Fraction
    return Fraction(str(x))


def kp_base(doc, wage, notes, bank_prices):
    """({item: unit worth as a Fraction}, [problems]) for every input that is not made by a recipe: a unit of every
    crate that is not itself a kitchen/pharmacy good, then the record's `raw` inputs by class."""
    from fractions import Fraction
    k = kp(doc)
    W = {t: _frac(v) for t, v in wage.items()}
    base, problems = {}, []
    cunit = {}
    for c in doc["crates"]:
        if c.get("kp"):
            continue
        cunit[c["id"]] = Fraction(crate_price(c, wage), c["count"])
        for i in c["items"]:
            base[i] = cunit[c["id"]]
    classes = k.get("classes") or {}
    for item in k.get("sold") or []:
        # a good a live wild Pokemon also drops is worth no more than its drop: W(early) / (ko_per_hour x chance)
        best = best_drop(notes, item)
        if best and (classes.get("drop") or {}).get("ko_per_hour"):
            base[item] = W[classes["drop"]["tier"]] / (_frac(classes["drop"]["ko_per_hour"]) * _frac(best))
    for item, r in sorted((k.get("raw") or {}).items()):
        cls, spec = r.get("class"), classes.get(r.get("class")) or {}
        if item in base:
            problems.append("kitchen_pharmacy raw %s is already a unit of a crate: one price" % item)
            continue
        if cls in ("harvest", "dig"):
            if spec.get("tier") not in W or not (isinstance(spec.get("rate_per_hour"), (int, float))
                                                 and spec["rate_per_hour"] > 0) or not spec.get("why"):
                problems.append("kitchen_pharmacy class %s needs a tier, a positive rate_per_hour and a why" % cls)
                continue
            base[item] = W[spec["tier"]] / _frac(spec["rate_per_hour"])
        elif cls == "drop":
            best = best_drop(notes, item)
            if not best:
                problems.append("kitchen_pharmacy raw %s: class drop but no live dropper in the notes" % item)
                continue
            base[item] = W[spec["tier"]] / (_frac(spec["ko_per_hour"]) * _frac(best))
        elif cls == "mineral":
            if r.get("of") not in bank_prices:
                problems.append("kitchen_pharmacy raw %s: the bank does not buy %s" % (item, r.get("of")))
                continue
            base[item] = _frac(bank_prices[r["of"]]) / _frac(r.get("per", 1))
        elif cls == "crate":
            if r.get("crate") not in cunit:
                problems.append("kitchen_pharmacy raw %s: no crate %s" % (item, r.get("crate")))
                continue
            base[item] = cunit[r["crate"]]
        else:
            problems.append("kitchen_pharmacy raw %s: class %r is not one of %s" % (item, cls, sorted(classes) + ["mineral", "crate"]))
    return base, problems


def kp_derive(doc, base, recipes_of):
    """({sold item: dict(n, price, unit, recipe, rc, tot, step, picks)}, {item: dict(recipe, rc, picks, unit)}, [problems]).
    `recipes_of(item)` -> [(name, yield, [([accepted ids], count)])]. The unit worth of an item is the least of its base
    worth and of every recipe's (inputs + step) / yield, each input at its cheapest accepted member; a SOLD item's step is
    max(flat, pct of the inputs) and it carries a sale price floor(n x unit) for the smallest n (of KP_COUNTS) that makes
    the crate worth `crate_floor_dollars`; a sold item used as an input is worth what the post pays for it. An item
    reached through a cycle is never cached (a route cut short would overstate its worth)."""
    import math
    k = kp(doc)
    sold = list(k.get("sold") or [])
    flat, pct = _frac(k["step_cost"]["flat"]), _frac(k["step_cost"]["percent"]) / 100
    floor_d = int(k.get("crate_floor_dollars", 10))
    memo, out, chosen, problems = {}, {}, {}, []

    def u(item, stack):
        """-> (unit worth or None, cut: a route was skipped because it ran through `stack`)"""
        if item in out:
            return out[item]["unit"], False
        if item in memo:
            return memo[item], False
        best, cut = None, False
        for name, rc, slots in recipes_of(item):
            tot, ok, picks = _frac(0), True, []
            for cands, n in slots:
                vals = []
                for a in sorted(cands):
                    if a == item or a in stack:
                        cut = True
                        continue
                    x, c2 = u(a, stack + (item,))
                    cut = cut or c2
                    if x is not None:
                        vals.append((x, a))
                if not vals:
                    ok = False
                    break
                x, a = min(vals)
                tot += x * n
                picks.append((a, n))
            if not ok:
                continue
            step = max(flat, tot * pct) if item in sold else _frac(0)
            val = (tot + step) / rc
            if best is None or val < best[0]:
                best = (val, name, rc, tot, step, picks)
        have = base.get(item)
        if best is not None and (have is None or best[0] < have):
            val = best[0]
            chosen[item] = dict(recipe=best[1], rc=best[2], picks=best[5], unit=val, tot=best[3], step=best[4])
        else:
            val = have
        if item in sold and (best is not None or have is not None):
            # the cheaper of the two routes is the price: a good a wild Pokemon also drops sells at no more than its drop
            # (W / (60 x its chance)), nor than crafting it
            via = best if best is not None and (have is None or best[0] <= have) else (have, "drop", 1, have, _frac(0), [])
            n = next((c for c in KP_COUNTS if math.floor(c * via[0]) >= floor_d), KP_COUNTS[-1])
            price = math.floor(n * via[0])
            if price < 1:
                problems.append("kitchen_pharmacy %s: derives to %s a unit: under $1 a crate even at %d" % (item, float(via[0]), n))
                return None, cut
            out[item] = dict(n=n, price=price, unit=_frac(price) / n, recipe=via[1], rc=via[2], tot=via[3],
                             step=via[4], picks=via[5], derived=via[0])
            return out[item]["unit"], False
        if not cut and val is not None:
            memo[item] = val
        return val, cut

    for item in sold:
        if item not in out:
            x, _ = u(item, ())
            if item not in out:
                problems.append("kitchen_pharmacy sold %s: no recipe whose every input has a worth" % item)
    return out, chosen, problems


def kp_data_recipes(doc):
    rec = kp(doc).get("recipes") or {}
    return lambda item: [(r["name"], int(r["yield"]), [([p], int(n)) for p, n in r["in"]]) for r in rec.get(item) or []]


def kp_jar_recipes(doc, jars):
    """Every jar recipe by result id, with every accepted id of each slot, plus the record's own `world_recipes`."""
    by = {}
    for name, _kind, ings, rid, rc in jars.conversions():
        by.setdefault(rid, []).append((name, rc, [(sorted(a), n) for a, n in ings]))
    for item, r in (kp(doc).get("world_recipes") or {}).items():
        by.setdefault(item, []).append((r["name"], int(r["yield"]), [([p], int(n)) for p, n in r["in"]]))
    return lambda item: by.get(item, [])


def kp_crate_id(item):
    return "kp_" + item.split(":", 1)[1].replace("/", "_")


def kp_crates(doc, derived, wage):
    """The `crates` entries the record must carry for the derivation (what `goods` prints)."""
    out = []
    for item in kp(doc)["sold"]:
        d = derived[item]
        rate = float("%.6g" % (d["n"] * float(wage["early"]) / d["price"]))
        out.append({"id": kp_crate_id(item), "kp": True, "menu": False, "label": item.split(":", 1)[1].replace("_", " "),
                    "count": d["n"], "tier": "early", "rate_per_hour": rate, "items": [item],
                    "rate_why": "back-solved from the crafts-rule price in kitchen_pharmacy (see its rule)"})
    return out


def kp_problems(doc, wage, notes, bank_prices, jars=None):
    """(problems, reports): the record's derivation re-run from its own inputs, the crates it must carry, and (with jars)
    every recipe it cites against the jar and the cheapest jar route against the record's."""
    k = kp(doc)
    if not k:
        return [], []
    out, rep = [], []
    base, p = kp_base(doc, wage, notes, bank_prices)
    out += p
    derived, _chosen, p = kp_derive(doc, base, kp_data_recipes_with_world(doc))
    out += p
    have = {c["items"][0]: c for c in doc["crates"] if c.get("kp")}
    for item in k["sold"]:
        c, d = have.get(item), derived.get(item)
        if d is None:
            continue
        if c is None:
            out.append("kitchen_pharmacy %s is sold but has no kp crate (python tools/produce_buyer.py goods prints it)" % item)
            continue
        got = crate_price(c, wage)
        if c.get("id") != kp_crate_id(item) or c["count"] != d["n"] or got != d["price"] or c.get("menu") is not False \
                or c.get("tier") != "early" or c["items"] != [item]:
            out.append("kitchen_pharmacy %s: the crate (%s, %d for $%d) is not the derivation's (%d for $%d): run "
                       "`python tools/produce_buyer.py goods` and copy" % (item, c.get("id"), c["count"], got, d["n"], d["price"]))
    for item, c in have.items():
        if item not in k["sold"]:
            out.append("crate %s is a kitchen_pharmacy good but %s is not in kitchen_pharmacy.sold" % (c["id"], item))
    for item in k["sold"]:
        if item in (k.get("not_sold") or {}):
            out.append("kitchen_pharmacy %s is both sold and in not_sold" % item)
    for item in sorted(k.get("recipes") or {}):
        for r in k["recipes"][item]:
            if not r.get("in") or int(r.get("yield", 0)) < 1 or not r.get("name"):
                out.append("kitchen_pharmacy recipe for %s: needs a name, a yield and inputs" % item)
    rep.append("kitchen_pharmacy: %d goods derived from %d recipes and %d raw inputs" % (len(derived), sum(len(v) for v in (k.get("recipes") or {}).values()), len(k.get("raw") or {})))
    if jars is not None:
        jr = kp_jar_recipes(doc, jars)
        jd, _jc, p = kp_derive(doc, base, jr)
        out += ["jars: " + x for x in p]
        for item in k["sold"]:
            a, b = derived.get(item), jd.get(item)
            if a and b and (a["price"], a["n"]) != (b["price"], b["n"]):
                out.append("kitchen_pharmacy %s: the record derives %d for $%d; the jars' cheapest recipe chain derives "
                           "%d for $%d (a cheaper route exists, or the record cites a recipe the jars do not have)"
                           % (item, a["n"], a["price"], b["n"], b["price"]))
            elif a and not b:
                out.append("kitchen_pharmacy %s: derives from the record but not from the jars" % item)
        by = {}
        for name, _kind, ings, rid, rc in jars.conversions():
            by[name] = (rid, rc, [(sorted(x), n) for x, n in ings])
        for item, rs in sorted((k.get("recipes") or {}).items()):
            for r in rs:
                if r["name"] not in by:
                    if r["name"] not in {w["name"] for w in (k.get("world_recipes") or {}).values()}:
                        out.append("kitchen_pharmacy recipe %s is not in the jars" % r["name"])
                    continue
                rid, rc, slots = by[r["name"]]
                if rid != item or rc != int(r["yield"]) or len(slots) != len(r["in"]):
                    out.append("kitchen_pharmacy recipe %s: the jar makes %d x %s from %d slots; the record says %d x %s from %d"
                               % (r["name"], rc, rid, len(slots), r["yield"], item, len(r["in"])))
                    continue
                for (acc, n), (pick, rn) in zip(slots, r["in"]):
                    if pick not in acc or n != rn:
                        out.append("kitchen_pharmacy recipe %s: %d x %s is not an accepted slot of the jar's (%s)"
                                   % (r["name"], rn, pick, ", ".join(acc[:4])))
        rep.append("kitchen_pharmacy: %d recipes read back from the jars; the cheapest jar chain matches the record for %d of %d goods"
                   % (sum(len(v) for v in (k.get("recipes") or {}).values()),
                      sum(1 for i in k["sold"] if derived.get(i) and jd.get(i) and (derived[i]["price"], derived[i]["n"]) == (jd[i]["price"], jd[i]["n"])),
                      len(k["sold"])))
    return out, rep


def kp_data_recipes_with_world(doc):
    own = kp_data_recipes(doc)
    wr = kp(doc).get("world_recipes") or {}

    def f(item):
        out = list(own(item))
        if item in wr:
            r = wr[item]
            out.append((r["name"], int(r["yield"]), [([p], int(n)) for p, n in r["in"]]))
        return out
    return f


# ---------------------------------------------------------------------------------------------------------- the pack
def short_take_lines(doc):
    """cobblers:produce_buyer/short_take, as the player, when a crate's take removed fewer than the crate's count
    (#took of #n). Unreachable after the dry-run count gate, kept fail closed: the taken share of the price,
    #price x #took / #n rounded down, is recorded as owed. Nothing is paid here."""
    S, m = doc["runtime"]["scores"], doc["messages"]
    T = S["temp"]
    return ["# Generated by tools/produce_buyer.py from data/produce_buyer.json: a short take (as the player)",
            "# the taken share of the price is owed: #price x #took / #n",
            "scoreboard players operation #part %s = #price %s" % (T, T),
            "scoreboard players operation #part %s *= #took %s" % (T, T),
            "scoreboard players operation #part %s /= #n %s" % (T, T),
            "scoreboard players operation @s %s += #part %s" % (S["owed"], T),
            "tellraw @s %s" % text(m["take_failed"], "red"),
            "# an explicit return, so the caller's `return run function` stops the sale whatever the version does "
            "with a function that returns nothing",
            "return 1"]


def pay_tail(doc, amount_obj):
    """The pay and its verification, shared by a crate and by sell-all: pay `amount_obj` once, re-read the balance,
    record the amount as owed unless the balance rose by exactly it."""
    S, store = doc["runtime"]["scores"], doc["runtime"]["storage"]
    T = S["temp"]
    return ["execute store result storage %s pay.amount int 1 run scoreboard players get %s %s" % (store, amount_obj, T),
            "function %s with storage %s pay" % (fn_id("pay"), store),
            "execute store result score #after %s run cobbledollars query @s" % T,
            "scoreboard players operation #want %s = #before %s" % (T, T),
            "scoreboard players operation #want %s += %s %s" % (T, amount_obj, T),
            "execute unless score #after %s = #want %s run scoreboard players operation @s %s += %s %s"
            % (T, T, S["owed"], amount_obj, T),
            "execute unless score #after %s = #want %s run return run tellraw @s %s"
            % (T, T, text(doc["messages"]["pay_failed"], "red"))]


def cooldown_head(doc):
    S = doc["runtime"]["scores"]
    T = S["temp"]
    return ["# 1. a second submit of the same click, or a sale straight after one, does nothing",
            "execute store result score #now %s run time query gametime" % T,
            "execute if score @s %s > #now %s run return 0" % (S["cooldown"], T)]


def spend_click(doc):
    S, rt = doc["runtime"]["scores"], doc["runtime"]
    T = S["temp"]
    return ["scoreboard players operation @s %s = #now %s" % (S["cooldown"], T),
            "scoreboard players add @s %s %d" % (S["cooldown"], int(rt["cooldown_ticks"])),
            "execute store result score #before %s run cobbledollars query @s" % T]


def sell_lines(doc, crate, price):
    """cobblers:produce_buyer/sell/<id>: one exact crate."""
    S, m = doc["runtime"]["scores"], doc["messages"]
    T = S["temp"]
    n = int(crate["count"])
    item = predicate(crate)
    short = json.dumps([{"text": "", "color": "gold"}, {"text": fill(m["short"], count=n, label=crate["label"])},
                        {"score": {"name": "#have", "objective": T}}, {"text": m["short_after"]}], ensure_ascii=False)
    paid = json.dumps([{"text": "", "color": "green"}, {"text": fill(m["paid"], label=crate["label"])},
                       {"text": "+$"}, {"score": {"name": "#price", "objective": T}}, {"text": "."}],
                      ensure_ascii=False)
    return (["# Generated by tools/produce_buyer.py from data/produce_buyer.json: sell a crate of %d %s for $%d (as and "
             "at the player, from the Trading Post's dialogue)" % (n, crate["label"], price)]
            + cooldown_head(doc)
            + ["# 2. count the crate's items without taking any (clear with a count of 0), refuse when short",
               "execute store result score #have %s run clear @s %s 0" % (T, item),
               "execute unless score #have %s matches %d.. run return run tellraw @s %s" % (T, n, short),
               "# 3. from here the click is spent; the balance before",
               ] + spend_click(doc)
            + ["scoreboard players set #price %s %d" % (T, price),
               "scoreboard players set #n %s %d" % (T, n),
               "# 4. TAKE the crate first: exactly %d, or nothing is paid (a short take records the taken share as "
               "owed: %s)" % (n, fn_id("short_take")),
               "execute store result score #took %s run clear @s %s %d" % (T, item, n),
               "execute unless score #took %s matches %d run return run function %s" % (T, n, fn_id("short_take")),
               "# 5. PAY the crate's price, then the balance must have risen by exactly that"]
            + pay_tail(doc, "#price") + ["tellraw @s %s" % paid])


def sellall_lines(doc, crate, price):
    """cobblers:produce_buyer/sellall/<id>: count, take every whole crate with a bounded take, credit #total."""
    S, store = doc["runtime"]["scores"], doc["runtime"]["storage"]
    T = S["temp"]
    n = int(crate["count"])
    item = predicate(crate)
    return ["# Generated by tools/produce_buyer.py from data/produce_buyer.json: every whole crate of %s the player "
            "holds, taken and credited to #total (the caller pays once)" % crate["label"],
            "scoreboard players set #n %s %d" % (T, n),
            "scoreboard players set #price %s %d" % (T, price),
            "execute store result score #have %s run clear @s %s 0" % (T, item),
            "scoreboard players operation #crates %s = #have %s" % (T, T),
            "scoreboard players operation #crates %s /= #n %s" % (T, T),
            "execute if score #crates %s matches ..0 run return 0" % T,
            "scoreboard players operation #take %s = #crates %s" % (T, T),
            "scoreboard players operation #take %s *= #n %s" % (T, T),
            "execute store result storage %s take.n int 1 run scoreboard players get #take %s" % (store, T),
            "# a take that cannot run leaves #took 0, so nothing is credited for it",
            "scoreboard players set #took %s 0" % T,
            "function %s with storage %s take" % (fn_id("take/%s" % crate["id"]), store),
            "execute unless score #took %s = #take %s run scoreboard players set #short %s 1" % (T, T, T),
            "scoreboard players operation #part %s = #price %s" % (T, T),
            "scoreboard players operation #part %s *= #took %s" % (T, T),
            "scoreboard players operation #part %s /= #n %s" % (T, T),
            "scoreboard players operation #total %s += #part %s" % (T, T)]


def take_lines(doc, crate):
    """cobblers:produce_buyer/take/<id>: the bounded take, a macro function (`function ... with storage`)."""
    T = doc["runtime"]["scores"]["temp"]
    return ["# Generated by tools/produce_buyer.py: the bounded take of %s. A macro: $(n) is read from storage "
            "%s take.n. `clear` reports how many it removed (ASSUMED, ECONOMY_V2 U2)" % (crate["label"],
                                                                                         doc["runtime"]["storage"]),
            "$execute store result score #took %s run clear @s %s $(n)" % (T, predicate(crate))]


def specimen_lines(doc, sprices):
    """cobblers:produce_buyer/sellall/specimens: every piece of every specimen, by the piece."""
    T = doc["runtime"]["scores"]["temp"]
    out = ["# Generated by tools/produce_buyer.py from data/produce_buyer.json: every found item the Trading Post buys "
           "by the piece, taken whole (`clear @s <item>` removes every match and reports the number) and credited to "
           "#total"]
    for item in sorted(sprices):
        out += ["# %s at $%d a piece" % (item, sprices[item]),
                "scoreboard players set #price %s %d" % (T, sprices[item]),
                "scoreboard players set #took %s 0" % T,
                "execute store result score #took %s run clear @s %s" % (T, item),
                "scoreboard players operation #part %s = #took %s" % (T, T),
                "scoreboard players operation #part %s *= #price %s" % (T, T),
                "scoreboard players operation #total %s += #part %s" % (T, T)]
    return out


def sell_all_lines(doc):
    S, m = doc["runtime"]["scores"], doc["messages"]
    T = S["temp"]
    paid = json.dumps([{"text": "", "color": "green"}, {"text": m["paid_all"]}, {"text": "+$"},
                       {"score": {"name": "#total", "objective": T}}, {"text": "."}], ensure_ascii=False)
    out = ["# Generated by tools/produce_buyer.py from data/produce_buyer.json: sell everything the Trading Post buys "
           "(as and at the player). Each category and the specimens take what they count and add its pay to #total; "
           "the one pay is at the end"]
    out += cooldown_head(doc)
    out += ["# 2. from here the click is spent; the balance before; nothing earned yet"] + spend_click(doc)
    out += ["scoreboard players set #total %s 0" % T, "scoreboard players set #short %s 0" % T,
            "# 3. every category, then the specimens: each COUNTS, then TAKES, then adds to #total. None returns out of "
            "this function, so nothing taken is left unpaid"]
    out += ["function %s" % fn_id("sellall/%s" % c["id"]) for c in doc["crates"]]
    out += ["function %s" % fn_id("sellall/specimens"),
            "# 4. nothing taken: #total is 0 only when no take ran (a whole-crate or whole-piece take credits at least $1)",
            "execute if score #total %s matches ..0 run return run tellraw @s %s" % (T, text(m["nothing"], "gold")),
            "# 5. PAY the total once, then the balance must have risen by exactly that"]
    out += pay_tail(doc, "#total")
    out += ["execute if score #short %s matches 1 run tellraw @s %s" % (T, text(m["short_note"], "gold")),
            "tellraw @s %s" % paid]
    return out


def conversation(doc, site, crate_prices):
    """(conversation, quest) for one site's buyer, in data/dialogue.json's and data/quests.json's shape (the ferry's)."""
    qid = "produce_buyer_%s" % site["id"]
    m = doc["messages"]
    responses = [{"id": "r_all", "text": m["all"],
                  "actions": [{"kind": "quest_transition", "transition": "sell_all"}, {"kind": "close_dialogue"}]}]
    transitions = [{"id": "sell_all", "conditions": [],
                    "effects": [{"kind": "function", "function": fn_id("sell/all")}]}]
    for c in doc["crates"]:
        if c.get("menu") is False:
            continue    # a kitchen/pharmacy good: sold only by "sell everything I can" (too many to list as buttons)
        tid = "sell_%s" % c["id"]
        transitions.append({"id": tid, "conditions": [],
                            "effects": [{"kind": "function", "function": fn_id("sell/%s" % c["id"])}]})
        responses.append({"id": "r_%s" % c["id"], "text": "A crate of %d %s ($%d)" % (c["count"], c["label"],
                                                                                   crate_prices[c["id"]]),
                          "actions": [{"kind": "quest_transition", "transition": tid}, {"kind": "close_dialogue"}]})
    responses.append({"id": "r_leave", "text": m["leave"], "actions": [{"kind": "close_dialogue"}]})
    conv = {"id": "dlg_produce_buyer_%s" % site["id"], "quest_id": qid, "npc_id": "npc_produce_buyer_%s" % site["id"],
            "npc_name": site["name"], "scope": "player", "speakers": {"buyer": site["name"]},
            "cursor": {"progression_field": None, "initial_node": "menu"},
            "entry_rules": [{"priority": 10, "when": {"kind": "always"}, "node": "menu"}],
            "nodes": [{"id": "menu", "kind": "choice", "speaker": "buyer", "text": doc["greeting"],
                       "responses": responses}]}
    return conv, {"id": qid, "progression_field_refs": [], "transitions": transitions, "rewards": []}


def build(doc, wage=None, notes=None):
    """{relative path in the pack: content (list of lines, or a JSON object)}."""
    import compile_dialogue as CD
    S = doc["runtime"]["scores"]
    cp = prices(doc, wage)
    sp = specimen_prices(doc, wage, notes)
    files = {"pack.mcmeta": {"pack": {"pack_format": 48,
                                      "description": "Cobblers Trading Post (generated by tools/produce_buyer.py)"}},
             "data/minecraft/tags/function/load.json": {"values": [fn_id("load")]}}
    files[fn_path("load")] = ["# the Trading Post's scores: the sale's arithmetic, each player's cooldown and anything "
                              "owed after a failed payment"] + \
        ["scoreboard objectives add %s dummy" % S[k] for k in ("temp", "cooldown", "owed")]
    files[fn_path("pay")] = ["# CobbleDollars' own command, the macro tools/arena_runtime.py and tools/blackout_pack.py use",
                             "$cobbledollars give @s $(amount)"]
    files[fn_path("short_take")] = short_take_lines(doc)
    # the kitchen/pharmacy crates have no menu line (menu: false; the 14-option dialogue is the owner's): their
    # single-good sell functions are named here as the operator's entry points, the way rip_scheduler's init names
    # stop/start/close_all, so prepare's reachability check sees them and the independent audit still reads them
    unmenued = [fn_id("sell/%s" % c["id"]) for c in doc["crates"] if c.get("menu") is False]
    files[fn_path("sell/all")] = sell_all_lines(doc) + (
        ["# single-good entry points with no menu line (operator, over RCON): %s" % ", ".join(unmenued[i:i + 6])
         for i in range(0, len(unmenued), 6)] if unmenued else [])
    files[fn_path("sellall/specimens")] = specimen_lines(doc, sp)
    for c in doc["crates"]:
        files[fn_path("sell/%s" % c["id"])] = sell_lines(doc, c, cp[c["id"]])
        files[fn_path("sellall/%s" % c["id"])] = sellall_lines(doc, c, cp[c["id"]])
        files[fn_path("take/%s" % c["id"])] = take_lines(doc, c)
        if not c.get("tag") and len(c["items"]) > 1:
            files["data/%s/tags/item/%s/%s.json" % (NS, FOLDER, c["id"])] = {"values": list(c["items"])}
    for site in doc["sites"]:
        if site.get("status") == "unsited":
            continue
        conv, quest = conversation(doc, site, cp)
        got = CD.compile_conversation(conv, {quest["id"]: quest}, {})
        clash = [k for k in got if k in files]
        if clash:
            raise BuyerError("site %s writes %s twice" % (site["id"], clash))
        files.update(got)
    return files


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(content) + "\n" if isinstance(content, list) else \
            json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        f.write_text(body, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------------------------------------- the seats
ANCHORS = ("apricorn_farm", "town_square")


def sited(doc):
    return [s for s in doc["sites"] if s.get("status") != "unsited"]


def apricorn_seat(site, plan_cache, g=None):
    """(x, y, z), the plan, and the farm's other NPCs [(who, (x, y, z))] for the farm site, from its anchor's plan."""
    import apricorn_farm as AF
    if "apricorn_farm" not in plan_cache:
        import ground as G
        doc = AF.load()
        plan_cache["apricorn_farm"] = AF.plan(doc, g or G.load())
    p, farmer, merchant = plan_cache["apricorn_farm"]
    lx, lz = site["at_local"]
    try:
        xyz = AF.spot(p, lx, lz, "the trading post %s" % site["id"])
    except AF.FarmError as e:
        raise BuyerError(str(e))
    return xyz, p, [("the farmer", farmer), ("the stall merchant", merchant)]


def npc_placements(doc=None, g=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for tools/reapply.py's "npc" action (R18PB). Hollin's position is
    recomputed from its anchor's plan, so a moved farm moves the post with it (and check fails until expected_at is
    updated); a town square's is the site's authored `at`, held by check to the squares builder's model."""
    doc = doc or load()
    cache = {}
    out = []
    for site in sited(doc):
        if site["anchor"] == "apricorn_farm":
            xyz, _p, _o = apricorn_seat(site, cache, g)
        else:
            xyz = site["at"]
        out.append(("dlg_produce_buyer_%s" % site["id"], tuple(xyz), "%s:npc_produce_buyer_%s" % (NS, site["id"]),
                    site["yaw"]))
    return out


_ROUTE = []


def route_points():
    if not _ROUTE:
        paths = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
        _ROUTE.extend((x, z) for v in paths.values() for x, z in v)
    return _ROUTE


def plaza_refs():
    """plaza_centre.refs_of(), except that derived/signposts.json is optional here: a checkout without it reads no
    signposts (the square is held to every other rule) and says so through square_model()['signposts']."""
    import plaza_centre as PC
    sp = ROOT / "derived" / "signposts.json"
    if sp.is_file():
        return PC.refs_of(), True
    return {
        "traders": PC.load_json(ROOT / "data" / "traders.json").get("traders") or [],
        "markets": [c for c in PC.load_json(ROOT / "data" / "markets.json").get("counters") or []
                    if c.get("status") == "sited"],
        "seats": PC.load_json(ROOT / "data" / "npc_seats.json").get("seats") or [],
        "ambient": PC.load_json(ROOT / "data" / "ambient.json").get("workers") or [],
        "walked": PC.load_json(ROOT / "data" / "route_paths.json")["paths"],
        "signposts": [],
        "scenes": PC.load_json(ROOT / "data" / "scenes.json")["scenes"],
        "dressing": PC.load_json(ROOT / "data" / "town_dressing.json"),
    }, False


def square_model(settlement, source_root=None, cache=None):
    """The squares builder's own view of one settlement (tools/plaza_centre.py): {town, occupied, points, signposts}.
    `occupied` is every column a piece of the square stands on or reaches, `points` every NPC cell (the town's
    traders, market keepers, seats, working Pokemon, and each stall's keeper and customer cells). Needs
    derived/towns/<settlement>_plan.json (python tools/town_plan.py <settlement>) for a settlement with a plan."""
    if cache is not None and settlement in cache:
        return cache[settlement]
    import ground as G
    import plaza_centre as PC
    data = PC.load_json(PC.DATA)
    doc = PC.load_json(ROOT / "data" / "placements.json")
    if settlement not in data["towns"]:
        raise BuyerError("data/plaza_centres.json has no square for %r" % settlement)
    g = PC.ground_for(settlement, G.Ground(source_root), doc, source_root)
    refs, has_signposts = plaza_refs()
    rec = dict(data["towns"][settlement], _town=settlement)
    town = PC.Town(settlement, rec, doc, g, refs)
    _cmds, report = PC.plan_town(settlement, data["towns"][settlement], doc, g, refs, data)
    occupied, points = set(), [(c[0], c[1]) for c, _why in town.npcs]
    for p in report["pieces"]:
        occupied |= {tuple(c) for c in p["columns"]}
        if p.get("keeper_at"):
            points.append((p["keeper_at"][0], p["keeper_at"][2]))
            occupied.add((p["keeper_at"][0], p["keeper_at"][2]))
            occupied.add(tuple(p["customer"]))
    model = {"town": town, "occupied": occupied, "points": points, "signposts": has_signposts}
    if cache is not None:
        cache[settlement] = model
    return model


def cell_problems(model, x, z, others=()):
    """Why a standing NPC cannot be at (x, z) on this square, from the squares builder's model and the existing floors."""
    town = model["town"]
    out = []
    why = town.blocked(x, z)
    if why:
        out.append("(%d, %d) is blocked on the square: %s" % (x, z, why))
    near = [(x + i, z + j) for i in range(-TANK_MARGIN, TANK_MARGIN + 1) for j in range(-TANK_MARGIN, TANK_MARGIN + 1)
            if (x + i, z + j) in model["occupied"]]
    if near:
        out.append("(%d, %d) is within %d of a piece of the square at %s" % (x, z, TANK_MARGIN, sorted(near)[0]))
    for (px, pz) in list(model["points"]) + list(others):
        d = math.hypot(x - px, z - pz)
        if d < NPC_CLEAR:
            out.append("(%d, %d) is %.1f blocks from an NPC at (%d, %d) (under %.1f)" % (x, z, d, px, pz, NPC_CLEAR))
    pts = [p for p in route_points() if abs(p[0] - x) <= 60 and abs(p[1] - z) <= 60]
    d = min(math.hypot(x - a, z - b) for a, b in pts) if pts else float("inf")
    if d < MIN_ROUTE:
        out.append("(%d, %d) is %.1f blocks from a walked route line (under %.1f): an immovable NPC there blocks the "
                   "road" % (x, z, d, MIN_ROUTE))
    return out


def yaw_toward(x, z, tx, tz):
    """Minecraft yaw (0 south, 90 west, 180 north, -90 east) for standing at (x, z) and facing (tx, tz)."""
    deg = round(math.degrees(math.atan2(-(tx - x), tz - z)))
    return deg - 360 if deg > 180 else deg + 360 if deg < -180 else deg


def propose_seats(doc, source_root=None):
    """{site id: {at, yaw, why}} for every town-square site with no `at` yet: the free cell nearest its counter."""
    markets = {c["id"]: c for c in json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))["counters"]}
    cache, out = {}, {}
    for site in sited(doc):
        if site["anchor"] != "town_square" or site.get("at"):
            continue
        model = square_model(site["settlement"], source_root, cache)
        counter = markets[site["counter"]]
        cx, cz = counter["at"][0], counter["at"][2]
        town = model["town"]
        x0, z0, x1, z1 = town.rect
        mid = ((x0 + x1) / 2.0, (z0 + z1) / 2.0)
        taken = [(s["at"][0], s["at"][2]) for s in sited(doc) if s.get("at") and s["id"] != site["id"]]
        # the market's own side of the square: the counter's nearest point on the square (the counter itself when it
        # stands on it), so a Mart across the town from the plaza does not drag the post across the plaza
        tx, tz = min(max(cx, x0), x1), min(max(cz, z0), z1)
        best = None
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if cell_problems(model, x, z, taken):
                    continue
                key = (math.hypot(x - tx, z - tz), math.hypot(x - cx, z - cz), x, z)
                if best is None or key < best:
                    best = key
        if best is None:
            out[site["id"]] = None
            continue
        _d, _dc, x, z = best
        out[site["id"]] = {"at": [x, town.floor_at(x, z) + 1, z], "yaw": yaw_toward(x, z, *mid),
                           "from_square_edge_target": round(_d, 1), "from_counter": round(_dc, 1),
                           "signposts_read": model["signposts"]}
    return out


def seat_problems(doc, g=None, source_root=None, cache=None):
    out = []
    cache = {} if cache is None else cache
    plan_cache = {}
    pts = route_points()
    mine = [(s["id"], s["at"]) for s in sited(doc) if s["anchor"] == "town_square" and s.get("at")]
    for site in sited(doc):
        w = "site %s" % site.get("id")
        if not (isinstance(site.get("yaw"), (int, float)) and -180 <= site["yaw"] <= 180):
            out.append("%s: yaw %r is not a Minecraft yaw" % (w, site.get("yaw")))
        if site.get("anchor") == "apricorn_farm":
            try:
                xyz, p, others = apricorn_seat(site, plan_cache, g)
            except BuyerError as e:
                out.append("%s: %s" % (w, e.code))
                continue
            if list(xyz) != list(site.get("expected_at") or []):
                out.append("%s: its spot is %s from the plan, the data says expected_at %s" % (w, list(xyz),
                                                                                          site.get("expected_at")))
            if (xyz[0], xyz[2]) in p.path_cols:
                out.append("%s: stands on a path at %s" % (w, xyz))
            if (xyz[0], xyz[2]) in p.reserved:
                out.append("%s: stands on a column %s claims" % (w, p.reserved[(xyz[0], xyz[2])]))
            for who, o in others:
                d = math.hypot(xyz[0] - o[0], xyz[2] - o[2])
                if d < NPC_CLEAR:
                    out.append("%s: %.1f blocks from %s at %s (under %.1f)" % (w, d, who, o, NPC_CLEAR))
            d = min(math.hypot(xyz[0] - x, xyz[2] - z) for x, z in pts) if pts else float("inf")
            if d < MIN_ROUTE:
                out.append("%s: %.1f blocks from a walked route line; an immovable NPC there blocks the road" % (w, d))
        elif site.get("anchor") == "town_square":
            at = site.get("at")
            if not at or len(at) != 3:
                out.append("%s: a town-square site with no `at` (python tools/produce_buyer.py seats proposes one)" % w)
                continue
            try:
                model = square_model(site["settlement"], source_root, cache)
            except (BuyerError, SystemExit) as e:
                out.append("%s: no model of the square: %s" % (w, getattr(e, "code", e)))
                continue
            x, y, z = at
            if model["town"].floor_at(x, z) + 1 != y:
                out.append("%s: stands at y%d, but the square's floor there is y%d (a seat is floor + 1)"
                           % (w, y, model["town"].floor_at(x, z)))
            others = [(a[0], a[2]) for i, a in mine if i != site["id"]]
            for p in cell_problems(model, x, z, others):
                out.append("%s: %s" % (w, p))
    return out


# ---------------------------------------------------------------------------------------------------------- checks
def all_crate_items(doc):
    return {i for c in doc["crates"] for i in c["items"]}


def grant_text(doc):
    out = {}
    for rel in doc["specimens"]["grant_files"]:
        p = ROOT / rel
        if p.is_file():
            out[rel] = p.read_text(encoding="utf-8")
    return out


def never_problems(doc, item, spawn_blocks, unreachable, w, spawn_ok=None):
    """Why an item may not be sold at all. `spawn_ok` is a crate's `spawn_block_ok` reason: a renewable harvest (a crop
    whose plant stays or regrows) may share its id with a spawn-condition block; nothing else may."""
    ns = doc["never_sold"]
    out = []
    if item in set(ns["ids"]):
        out.append("%s: %s is in never_sold" % (w, item))
    for pat in ns["patterns"]:
        if re.search(pat["regex"], item):
            out.append("%s: %s matches never_sold %r (%s)" % (w, item, pat["regex"], pat["why"]))
    if item in spawn_blocks and not spawn_ok:
        out.append("%s: %s is a spawn-condition block (data/spawn_blocks.json): paying for it strips encounters out of "
                   "the world" % (w, item))
    if item in unreachable:
        out.append("%s: %s is in data/bank.json `unreachable`" % (w, item))
    return out


def static_problems(doc, bank_prices, sell_points, wage=None, notes=None, spawn_blocks=None, unreachable=None,
                    grants=None):
    out = []
    wage = wage or wages()
    notes = notes if notes is not None else notes_of(doc)
    spawn_blocks = set(spawn_blocks if spawn_blocks is not None
                       else json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    if unreachable is None:
        unreachable = {u["item"] for u in json.loads((ROOT / "data" / "bank.json").read_text(encoding="utf-8"))
                       .get("unreachable") or []}
    grants = grants if grants is not None else grant_text(doc)
    seen, owner = set(), {}
    cprice = {}
    for c in doc["crates"]:
        w = "crate %s" % c.get("id")
        if not ID.fullmatch(c.get("id") or "") or c["id"] in seen or c["id"] in RESERVED_IDS:
            out.append("%s: id not [a-z0-9_], listed twice or reserved (%s)" % (w, ", ".join(RESERVED_IDS)))
        seen.add(c.get("id"))
        if not (isinstance(c.get("count"), int) and 0 < c["count"] <= 64 * 36):
            out.append("%s: count %r is not a positive whole number an inventory can hold" % (w, c.get("count")))
            continue
        if c.get("tier") not in wage:
            out.append("%s: tier %r is not one of the bank's tiers %s" % (w, c.get("tier"), sorted(wage)))
            continue
        if not (isinstance(c.get("rate_per_hour"), (int, float)) and c["rate_per_hour"] > 0):
            out.append("%s: rate_per_hour %r is not a positive number" % (w, c.get("rate_per_hour")))
            continue
        price = crate_price(c, wage)
        cprice[c["id"]] = price
        if price < 1:
            out.append("%s: count %d x W(%s) $%g / %g an hour rounds to $%d: a crate must pay at least $1"
                       % (w, c["count"], c["tier"], wage[c["tier"]], c["rate_per_hour"], price))
        if not c.get("items") or not all(ITEM.fullmatch(i) for i in c["items"]):
            out.append("%s: items must be ns:path ids" % w)
        if c.get("tag") and not (c["tag"].startswith("#") and ITEM.fullmatch(c["tag"][1:])):
            out.append("%s: tag %r is not #ns:path" % (w, c["tag"]))
        if c.get("tag") and not c.get("tag_verified"):
            out.append("%s: a jar tag with no tag_verified source" % w)
        for k in ("label", "rate_why"):
            if not c.get(k):
                out.append("%s: no %s" % (w, k))
        unit = price / c["count"]
        for i in c.get("items") or []:
            if i in owner:
                out.append("%s: %s is also in crate %s: one item, one price" % (w, i, owner[i]))
            owner[i] = c["id"]
            out += never_problems(doc, i, spawn_blocks, unreachable, w, c.get("spawn_block_ok"))
            if i in bank_prices:
                out.append("%s: the bank buys %s at $%d: one channel per item (ECONOMY_V2 2)" % (w, i, bank_prices[i]))
        for where, i, u in sell_points:
            if i in set(c.get("items") or []) and u <= unit:
                out.append("%s: %s sells %s at $%g each, at or under the crate's $%g a unit: buying a crate to sell "
                           "it pays, and there is no cap" % (w, where, i, u, unit))
    # the specimens
    sp = doc["specimens"]
    items, excluded = list(sp["items"]), sp["excluded"]
    if len(set(items)) != len(items):
        out.append("specimens: an id is listed twice")
    sprice = {}
    for i in items:
        w = "specimen %s" % i
        if not ITEM.fullmatch(i) or not i.startswith("cobblemon:"):
            out.append("%s: a specimen is a cobblemon: id" % w)
        if i in owner:
            out.append("%s: also in crate %s" % (w, owner[i]))
        rec = notes["items"].get(i)
        if rec is None:
            out.append("%s: not in %s" % (w, sp["notes_file"]))
            continue
        if not rec.get("registered"):
            out.append("%s: not a registered item (a broken drop id)" % w)
        best = best_drop(notes, i)
        if not best:
            out.append("%s: no live dropper: nothing in our world drops it" % w)
            continue
        if rec.get("recipe_result_count"):
            out.append("%s: %d recipe(s) make it: a specimen is drop-only, so no craft can undercut a drop"
                       % (w, rec["recipe_result_count"]))
        if i in bank_prices or rec.get("bank_price") is not None:
            out.append("%s: the bank buys it" % w)
        if i in excluded:
            out.append("%s: listed in items and in excluded" % w)
        out += never_problems(doc, i, spawn_blocks, unreachable, w)
        for rel, body in grants.items():
            if i in body:
                out.append("%s: appears in %s (a prize or a dungeon reward is never sold)" % (w, rel))
        raw = wage[sp["wage_tier"]] / (sp["ko_per_hour"] * best)
        price = max(1, min(int(sp["cap_p"]) * 100, round_half_up(raw)))
        sprice[i] = price
        for where, si, u in sell_points:
            if si == i and u <= price:
                out.append("%s: %s sells it at $%g, at or under its $%d a piece: buying one to sell it pays"
                           % (w, where, u, price))
    pats = [re.compile(p["regex"]) for p in sp["excluded_patterns"]]
    for i, rec in sorted(notes["items"].items()):
        if not i.startswith("cobblemon:") or not rec.get("registered") or rec.get("recipe_result_count") \
                or rec.get("bank_price") is not None or not best_drop(notes, i):
            continue
        if i in items or i in excluded or any(p.search(i) for p in pats):
            continue
        out.append("specimen candidate %s (drop-only, live dropper, not banked) is neither in specimens.items nor in "
                   "specimens.excluded: decide it" % i)
    for i, e in excluded.items():
        if e.get("kind") == "granted" and not any(i in body for body in grants.values()):
            out.append("excluded %s is kind 'granted' but no grant file names it any more: a stale exclusion" % i)
        if not e.get("why"):
            out.append("excluded %s has no why" % i)
    for k in ("leave", "all", "short", "short_after", "paid", "paid_all", "nothing", "short_note", "take_failed",
              "pay_failed"):
        if not doc["messages"].get(k):
            out.append("messages.%s is missing" % k)
    sids = [s.get("id") for s in doc["sites"]]
    if not sids or len(set(sids)) != len(sids) or not all(ID.fullmatch(s or "") for s in sids):
        out.append("sites: none, a repeated id or an id not [a-z0-9_]")
    for s in doc["sites"]:
        if s.get("anchor") not in ANCHORS:
            out.append("site %s: anchor %r is not one of %s" % (s.get("id"), s.get("anchor"), ANCHORS))
        if s.get("status") == "unsited" and not s.get("unsited_why"):
            out.append("site %s: unsited with no unsited_why" % s.get("id"))
    for k in ("schedule",):
        if k in doc:
            out.append("the data still has %r: E3 removed the allowance" % k)
    return out


def counter_problems(doc):
    """E8: every sited data/markets.json counter has a Trading Post site (or a recorded reason it has none)."""
    markets = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
    have = {s.get("counter") for s in doc["sites"] if s.get("counter")}
    out = []
    for c in markets["counters"]:
        if c.get("status") == "sited" and c["id"] not in have:
            out.append("counter %s (%s) has no Trading Post site: E8 puts one at every town square with a market"
                       % (c["id"], c["town"]))
    for s in doc["sites"]:
        if s.get("anchor") == "town_square" and s.get("counter") not in {c["id"] for c in markets["counters"]}:
            out.append("site %s names counter %r, which data/markets.json does not have" % (s["id"], s.get("counter")))
    return out


def output_problems(doc, files):
    """No allowance; every sale counts, takes, pays once and verifies; nothing charges; every function within limits."""
    import function_limits
    out = []
    S = doc["runtime"]["scores"]
    store = S and doc["runtime"]["storage"]
    pay_call = "function %s with storage %s pay" % (fn_id("pay"), store)
    retired = doc["runtime"].get("scores_retired") or []
    for rel, body in sorted(files.items()):
        if not rel.endswith(".mcfunction"):
            continue
        cmds = [ln for ln in body if not ln.startswith("#")]
        for ln in cmds:
            if any(name in ln for name in retired) or re.search(r"#cap\b|\bcob_pb_(leg|sold)\b", ln):
                out.append("%s: names the retired allowance (%s): E3 has no allowance" % (rel, ln[:80]))
                break
        if any("cobbledollars remove" in ln for ln in cmds):
            out.append("%s charges: the buyer never takes money" % rel)
        refused = function_limits.check_lines(body, rel)
        if refused:
            out.append("%s: %s" % (rel, refused))
    for c in doc["crates"]:
        rel = fn_path("sell/%s" % c["id"])
        body = files.get(rel)
        if not body:
            out.append("crate %s: no sell function" % c["id"])
            continue
        cmds = [ln for ln in body if not ln.startswith("#")]
        item = predicate(c)
        idx = lambda pred: next((i for i, ln in enumerate(cmds) if pred(ln)), None)   # noqa: E731
        cool = idx(lambda ln: ln.endswith("run time query gametime"))
        count = idx(lambda ln: ln.endswith("run clear @s %s 0" % item))
        short = idx(lambda ln: ln.startswith("execute unless score #have") and "matches %d.. run return" % c["count"] in ln)
        before = idx(lambda ln: "#before" in ln and "cobbledollars query" in ln)
        take = idx(lambda ln: ln.endswith("run clear @s %s %d" % (item, c["count"])))
        took_ok = idx(lambda ln: ln.startswith("execute unless score #took") and "matches %d run return" % c["count"] in ln)
        pay = idx(lambda ln: ln == pay_call)
        after = idx(lambda ln: "#after" in ln and "cobbledollars query" in ln)
        verify = idx(lambda ln: ln.startswith("execute unless score #after") and "run return" in ln)
        order = [cool, count, short, before, take, took_ok, pay, after, verify]
        if None in order or order != sorted(order):
            out.append("crate %s: the sale is not cooldown < count < short-gate < balance < take < take-check < pay < "
                       "re-read < verify (%s)" % (c["id"], order))
        if None not in (take, pay):
            early = [ln for ln in cmds[take + 1:pay] if "return" in ln]
            if early != [cmds[took_ok]] or not cmds[took_ok].endswith("run return run function %s" % fn_id("short_take")):
                out.append("crate %s: a return between the take and the pay other than the short-take function "
                           "(%s)" % (c["id"], early))
        if sum(1 for ln in cmds if ln == pay_call) != 1:
            out.append("crate %s: pays %d times" % (c["id"], sum(1 for ln in cmds if ln == pay_call)))
        if any("cobbledollars give" in ln for ln in cmds):
            out.append("crate %s: a CobbleDollars change outside the pay macro" % c["id"])
        sa = [ln for ln in (files.get(fn_path("sellall/%s" % c["id"])) or []) if not ln.startswith("#")]
        macro = [ln for ln in (files.get(fn_path("take/%s" % c["id"])) or []) if not ln.startswith("#")]
        if macro != ["$execute store result score #took %s run clear @s %s $(n)" % (S["temp"], item)]:
            out.append("crate %s: take/%s is not exactly the one bounded-take macro line" % (c["id"], c["id"]))
        i_count = next((i for i, ln in enumerate(sa) if ln.endswith("run clear @s %s 0" % item)), None)
        i_div = next((i for i, ln in enumerate(sa) if ln.startswith("scoreboard players operation #crates") and "/=" in ln), None)
        i_gate = next((i for i, ln in enumerate(sa) if ln.startswith("execute if score #crates") and "run return 0" in ln), None)
        i_take = next((i for i, ln in enumerate(sa) if ln.startswith("function %s with storage" % fn_id("take/%s" % c["id"]))), None)
        i_credit = next((i for i, ln in enumerate(sa) if ln.startswith("scoreboard players operation #total") and "+=" in ln), None)
        order = [i_count, i_div, i_gate, i_take, i_credit]
        if None in order or order != sorted(order):
            out.append("crate %s: sellall is not count < divide < nothing-gate < bounded take < credit (%s)" % (c["id"], order))
        if any("cobbledollars" in ln for ln in sa):
            out.append("crate %s: sellall moves money itself: only sell/all pays, once" % c["id"])
    all_body = files.get(fn_path("sell/all")) or []
    ac = [ln for ln in all_body if not ln.startswith("#")]
    idx = lambda pred: next((i for i, ln in enumerate(ac) if pred(ln)), None)   # noqa: E731
    cool = idx(lambda ln: ln.endswith("run time query gametime"))
    before = idx(lambda ln: "#before" in ln and "cobbledollars query" in ln)
    first_take = idx(lambda ln: ln.startswith("function %s" % fn_id("sellall/")))
    last_take = max((i for i, ln in enumerate(ac) if ln.startswith("function %s" % fn_id("sellall/"))), default=None)
    nothing = idx(lambda ln: ln.startswith("execute if score #total") and "matches ..0 run return run tellraw" in ln)
    pay = idx(lambda ln: ln == pay_call)
    after = idx(lambda ln: "#after" in ln and "cobbledollars query" in ln)
    verify = idx(lambda ln: ln.startswith("execute unless score #after") and "run return" in ln)
    order = [cool, before, first_take, last_take, nothing, pay, after, verify]
    if None in order or order != sorted(order):
        out.append("sell/all: not cooldown < balance < takes < nothing-gate < pay < re-read < verify (%s)" % order)
    if None not in (first_take, pay):
        between = [ln for ln in ac[first_take:pay] if "return" in ln]
        if between != [ac[nothing]]:
            out.append("sell/all: a return between the first take and the pay other than the nothing-taken gate: "
                       "%s" % between)
    called = [ln.split()[1] for ln in ac if ln.startswith("function %s" % fn_id("sellall/"))]
    want = [fn_id("sellall/%s" % c["id"]) for c in doc["crates"]] + [fn_id("sellall/specimens")]
    if called != want:
        out.append("sell/all calls %s, not every category and then the specimens %s" % (called, want))
    if sum(1 for ln in ac if ln == pay_call) != 1:
        out.append("sell/all: pays %d times, not once" % sum(1 for ln in ac if ln == pay_call))
    if any("cobbledollars give" in ln for ln in ac):
        out.append("sell/all: a CobbleDollars change outside the pay macro")
    spec = [ln for ln in (files.get(fn_path("sellall/specimens")) or []) if not ln.startswith("#")]
    if any("cobbledollars" in ln or "return" in ln for ln in spec):
        out.append("sellall/specimens moves money or returns: only sell/all pays, and a return would strand a take")
    clears = [ln for ln in spec if " run clear @s " in ln]
    sp = doc["specimens"]["items"]
    if sorted(ln.rsplit(" ", 1)[-1] for ln in clears) != sorted(sp):
        out.append("sellall/specimens clears %d items, not the %d specimens" % (len(clears), len(sp)))
    st = [ln for ln in (files.get(fn_path("short_take")) or []) if not ln.startswith("#")]
    owed_obj = S["owed"]
    if not st or not any(ln.startswith("scoreboard players operation @s %s += " % owed_obj) for ln in st) \
            or any("cobbledollars" in ln for ln in st) \
            or [ln for ln in st if "return" in ln] != ["return 1"] or st[-1] != "return 1":
        out.append("short_take: must record the owed share (%s), move no money and end with `return 1` (its only "
                   "return)" % owed_obj)
    pay = files.get(fn_path("pay")) or []
    if [ln for ln in pay if not ln.startswith("#")] != ["$cobbledollars give @s $(amount)"]:
        out.append("the pay function is not exactly the proven macro `$cobbledollars give @s $(amount)`")
    for site in sited(doc):
        if "data/%s/dialogues/dlg_produce_buyer_%s.json" % (NS, site["id"]) not in files:
            out.append("site %s: no compiled dialogue" % site["id"])
    return out


def load_jars(jars_dir, vanilla_jar):
    """tools/economy_audit.py's reader over `jars_dir`: a server-shaped directory (mods/ and datapacks/ inside it) or a
    folder of mod jars (the local store's server-mods-1.8.2, which has no mods/ inside: read as the mods directory)."""
    import economy_audit as EA
    d = Path(jars_dir)
    if (d / "mods").is_dir():
        return EA.load_jars(str(d), str(vanilla_jar))
    return EA.load_jars(str(d), str(vanilla_jar), str(d))


def closure_problems(doc, jars_dir, vanilla_jar, server_dir=None, wage=None, notes=None):
    """(problems, reports) over the jars' recipes, using tools/economy_audit.py's own reader (read, never edited).
    1. BUY: the cheapest way to obtain each crate item or specimen with money, by any seller or any recipe of
       purchasable inputs (EA.cheapest), against its unit worth here: at or under it is a printer with no cap.
    2. VALUE-ADDED: a recipe whose result is sold here and whose every input is either sold here (valued at its sale
       unit) or purchasable (valued at its cheapest price) and whose result is worth MORE than its inputs.
    An input that is neither sold here nor purchasable (milk, a farmed mob drop with no seller) is not priced, so a
    recipe through one is counted in the report and not judged."""
    import economy_audit as EA
    jars = load_jars(jars_dir, vanilla_jar)
    conv = jars.conversions()
    sales = EA.market_sales() + EA.apricorn_sales() + EA.default_shop_sales()
    if server_dir:
        sales += EA.trader_sales(server_dir)[0]
    best = EA.cheapest(sales, conv)
    wage = wage or wages()
    cp = prices(doc, wage)
    sp = specimen_prices(doc, wage, notes)
    worth, label = {}, {}
    for c in doc["crates"]:
        members = set(c["items"])
        if c.get("tag"):
            members |= set(jars.tag_items(c["tag"][1:]))
        for i in members:
            worth[i] = cp[c["id"]] / c["count"]
            label[i] = "crate %s" % c["id"]
    for i, p in sp.items():
        worth[i] = float(p)
        label[i] = "specimen"
    problems, reports = [], []
    tight = {}
    for i, u in worth.items():
        if i in best:
            r = best[i][0] / u
            if label[i] not in tight or r < tight[label[i]][0]:
                tight[label[i]] = (r, i, best[i][0], u)
    for lab, (r, i, cost, u) in sorted(tight.items(), key=lambda kv: kv[1][0]):
        reports.append("closure margin %s: cheapest purchase %s at $%g against a sale worth $%g (%.1fx)" % (lab, i, cost, u, r))
    for i, u in sorted(worth.items()):
        if i in best and best[i][0] <= u + 1e-9:
            problems.append("%s %s is worth $%g here and costs $%g to obtain: %s" % (label[i], i, u, best[i][0],
                                                                                    EA.chain(best, i)))
    unpriced = 0
    for name, kind, ings, rid, rcount in conv:
        if rid not in worth:
            continue
        total, ok = 0.0, True
        for acc, n in ings:
            vals = [worth[i] for i in acc if i in worth] + [best[i][0] for i in acc if i in best]
            if not vals:
                ok = False
                break
            total += min(vals) * n
        if not ok:
            unpriced += 1
            continue
        allow = max(2.0, total / 100.0) if label[rid].startswith("crate kp_") else 0.0
        if worth[rid] * rcount > total + allow + 1e-9:
            problems.append("recipe %s (%s): %d x %s is worth $%g here, its inputs only $%g" % (name, kind, rcount, rid,
                                                                                               worth[rid] * rcount, total))
    reports.append("closure: %d crate/specimen items judged against %d priceable recipes; %d recipes into a sold item "
                   "have an input that is neither sold here nor purchasable (not judged)" % (len(worth), len(conv), unpriced))
    return problems, reports


def check(doc=None, source_root=None, server_dir=None, jars_dir=None, vanilla_jar=None):
    """(problems, not-checked notes, reports)."""
    import bank
    import ground as G
    doc = doc or load()
    bdoc = bank.load()
    pts, skipped = bank.sell_points(server_dir)
    wage = wages()
    reports = []
    out = static_problems(doc, bank.prices(bdoc), pts, wage=wage)
    out += counter_problems(doc)
    if out:
        return out, skipped, reports
    out += output_problems(doc, build(doc, wage))
    out += seat_problems(doc, G.load(source_root), source_root)
    jars = load_jars(jars_dir, vanilla_jar) if jars_dir else None
    notes = notes_of(doc)
    p, r = kp_problems(doc, wage, notes, bank.prices(bdoc), jars)
    out += p
    reports += r
    if jars_dir:
        p, r = closure_problems(doc, jars_dir, vanilla_jar, server_dir, wage)
        out += p
        reports += r
    else:
        skipped = skipped + ["closure: no --jars-dir: recipes were not judged (kitchen_pharmacy: the record's own arithmetic only)"]
    return out, skipped, reports


def price_table(doc):
    wage = wages()
    cp = prices(doc, wage)
    rows = ["%-12s %-11s %5s %7s %9s %8s %6s" % ("crate", "tier", "count", "rate/h", "crate $", "unit $", "P")]
    for c in doc["crates"]:
        rows.append("%-12s %-11s %5d %7d %9d %8.4f %6.2f" % (c["id"], c["tier"], c["count"], c["rate_per_hour"],
                                                              cp[c["id"]], cp[c["id"]] / c["count"], cp[c["id"]] / 100))
    sp = specimen_prices(doc, wage)
    rows.append("specimens (a piece): " + ", ".join("%s $%d" % (i.split(":")[1], p) for i, p in sorted(sp.items())))
    rows.append("wages: " + ", ".join("%s $%g" % kv for kv in sorted(wage.items())))
    return rows


def goods_cmd(doc, a):
    """Print the derivation of every kitchen/pharmacy good. With --jars-dir the recipes come from the jars (the authoring
    path); without it, from the record. --json prints the `crates` entries and the `recipes` table the record must carry."""
    import bank
    wage = wages()
    base, probs = kp_base(doc, wage, notes_of(doc), bank.prices(bank.load()))
    if a.jars_dir:
        vj = a.vanilla_jar
        if not vj:
            import economy_audit
            vj = economy_audit.DEFAULT_VANILLA
        recipes_of = kp_jar_recipes(doc, load_jars(a.jars_dir, vj))
    else:
        recipes_of = kp_data_recipes_with_world(doc)
    derived, chosen, p2 = kp_derive(doc, base, recipes_of)
    for x in probs + p2:
        print("PROBLEM " + x)
    if a.json:
        crates = kp_crates(doc, derived, wage)
        # the recipe table: the chosen route of every sold good and, below it, of every intermediate it used
        table, todo, seen = {}, [i for i in kp(doc)["sold"] if i in derived], set()
        world = kp(doc).get("world_recipes") or {}
        while todo:
            i = todo.pop()
            if i in seen:
                continue
            seen.add(i)
            c = derived.get(i) or chosen.get(i)
            if not c or c["recipe"] in {w["name"] for w in world.values()}:
                for pk, _n in (c or {}).get("picks", []):
                    todo.append(pk)
                continue
            table[i] = [{"name": c["recipe"], "yield": c["rc"], "in": [[pk, n] for pk, n in c["picks"]]}]
            todo += [pk for pk, _n in c["picks"]]
        print(json.dumps({"crates": crates, "recipes": dict(sorted(table.items()))}, indent=1, ensure_ascii=False))
        return 1 if probs + p2 else 0
    for item in kp(doc)["sold"]:
        d = derived.get(item)
        if d:
            print("%-34s %2d for $%-3d (unit %.4f)  %s  inputs %s  step $%.2f" % (
                item, d["n"], d["price"], float(d["unit"]), d["recipe"].split("/")[-1], ", ".join("%dx%s" % (n, p.split(":")[1]) for p, n in d["picks"]), float(d["step"])))
    return 1 if probs + p2 else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(DEFAULT_OUT))
    c = sub.add_parser("check")
    c.add_argument("--source-root")
    c.add_argument("--server-dir", help="an OFFLINE snapshot: also read the traders' template shops (tools/bank.py)")
    c.add_argument("--jars-dir", help="a directory with mods/*.jar (and optionally datapacks/): judge the recipes")
    c.add_argument("--vanilla-jar", help="the vanilla 1.21.1 jar for --jars-dir (default: tools/economy_audit.py's)")
    sub.add_parser("prices")
    g = sub.add_parser("goods", help="derive the kitchen/pharmacy goods from the record; --jars-dir also resolves the recipes")
    g.add_argument("--jars-dir")
    g.add_argument("--vanilla-jar")
    g.add_argument("--json", action="store_true", help="print the crates and recipes to paste into the record")
    s = sub.add_parser("seats")
    s.add_argument("--source-root")
    a = ap.parse_args(argv)
    doc = load()
    if a.cmd == "build":
        files = build(doc)
        write(files, a.out)
        print("wrote %s (%d files, %d crate kinds, %d specimens, %d site(s))"
              % (a.out, len(files), len(doc["crates"]), len(doc["specimens"]["items"]), len(sited(doc))))
        return 0
    if a.cmd == "prices":
        print("\n".join(price_table(doc)))
        return 0
    if a.cmd == "goods":
        return goods_cmd(doc, a)
    if a.cmd == "seats":
        got = propose_seats(doc, a.source_root)
        for sid, rec in got.items():
            print(sid, json.dumps(rec) if rec else "NO FREE CELL")
        return 0
    vj = a.vanilla_jar
    if a.jars_dir and not vj:
        import economy_audit
        vj = economy_audit.DEFAULT_VANILLA
    out, skipped, reports = check(doc, a.source_root, a.server_dir, a.jars_dir, vj)
    for p in out:
        print("PROBLEM " + p)
    for r in reports:
        print("REPORT " + r)
    for s_ in skipped:
        print("NOT CHECKED " + s_)
    print("produce_buyer: %d problems; %d crate kinds, %d specimens, %d site(s)%s"
          % (len(out), len(doc["crates"]), len(doc["specimens"]["items"]), len(sited(doc)),
             "" if not skipped else " (partial: %d note(s) above)" % len(skipped)))
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
