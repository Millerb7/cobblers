#!/usr/bin/env python
"""The CobbleDollars Bank's buy list as data: what a player can sell at any merchant, and for how much.

The owner (2026-10-05): "need to make a way for players to earn money playing through minecraft game loop, like
selling minerals in brocks town". CobbleDollars already has the mechanism: shift + right-click on any
cobbledollars:cobble_merchant (or the Bank button on its shop screen) opens a Bank that buys items at the prices in
ONE server-wide file, config/cobbledollars/bank.json (read in the jar: data/bank.json `mechanism.verified`). The base
pack's list buys emeralds, medicine, vitamins, feathers of the birds and food, and no ore, no apricorn, no berry but
two. This tool writes our overlay of that file from data/bank.json: the base list unchanged, then our `buys`.

  write    python tools/bank.py write                     modpack/config/cobbledollars/bank.json from the data
  check    python tools/bank.py check [--server-dir S]    the data's rules and the committed file; exit 1 on a problem
  report   python tools/bank.py report                    the buy list and the hourly estimate, labelled as one

Getting it into the game: tools/reapply.py install copies modpack/config onto the server; then `cobbledollars reload`
(the jar's reload re-reads bank.json and syncs it to players) or a boot. Nothing else: no pack, no function, no NPC.

`check` compares every price the bank pays with every authored place that SELLS that item, and refuses a sale price at
or below the bank's (buy and sell would be free money). What it reads:
  data/markets.json        every counter's and stall's stock, whatever its status
  data/apricorn_farm.json  Hollin's stall merchant
  data/traders.json        the stock policy's authored shops (the Exchange's stones, the trainer card) and, with
                           --server-dir, every shopkeeper's template shop after the policy filter (read from
                           <server>/mods/*.jar and <server>/datapacks/*.zip only, as tools/traders.py does)
  the defaultShop          base-pack/cobbleverse/config/cobbledollars/default_shop.json, ours over it if present
The material exchange (2026-10-06, docs/mechanics/MATERIAL_EXCHANGE.md; the owner: "Netherite traded for a Master Ball
is the shape"). A CobbleMerchantShop takes only CobbleDollars (data/bank.json exchanges.barter_answer, read in the jar),
so an exchange is the bank buying the material and a counter selling the reward at EXACTLY N x the bank's price for it
(a data/markets.json stock line with exchange_for {item, count}). `check` also holds:
  crafts       a crafted item pays its inputs' bank total to total + CRAFT_MAX
  unreachable  nothing the world cannot supply is bought by our list (a base price on one is reported as dormant)
  effort_model each tier's assumed gathering hour against the battle income of the leg it opens (half_wage, upper_wage)
  exchanges    every exchange_for line: material bought, price exact, off-path sited counter in exchanges.towns, kind
               declared, at or above its kind's floor (read from the shelves, never a constant), never bought back
What the exchange checks do NOT cover: the rates (ASSUMED until timed), anything sold outside data/markets.json at
or under an exchange price (a donor template's merchant), and whether a merchant purchase completes in game (P-7).

What it does NOT cover (CLAUDE.md "Our list is not the world"): a merchant a donor template places that no data file
names, a natural CobbleMerchant, crafting and smelting chains other than raw -> ingot, renewable supplies in the world,
and duplication. Those are the independent audit's (data/bank.json audit_checklist). Without --server-dir the
shopkeeper templates are not read, and the run says so.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

DATA = ROOT / "data" / "bank.json"
BASE_DEFAULT = ROOT / "base-pack" / "cobbleverse" / "config" / "cobbledollars"
OURS = ROOT / "modpack" / "config" / "cobbledollars"
MARKETS = ROOT / "data" / "markets.json"
FARM = ROOT / "data" / "apricorn_farm.json"
TRADERS = ROOT / "data" / "traders.json"
SPAWN_BLOCKS = ROOT / "data" / "spawn_blocks.json"
ITEM = re.compile(r"[a-z0-9_.\-]+:[a-z0-9_/.\-]+")
# raw -> smelted: the smelted item pays at least the raw one and at most raw + SMELT_MAX (data/bank.json rules)
SMELTS = {"minecraft:raw_copper": "minecraft:copper_ingot", "minecraft:raw_iron": "minecraft:iron_ingot",
          "minecraft:raw_gold": "minecraft:gold_ingot", "minecraft:ancient_debris": "minecraft:netherite_scrap"}
SMELT_MAX = 2
# a crafted item (data/bank.json crafts) pays its inputs' bank total to that total + CRAFT_MAX(total)
CRAFT_MAX = lambda total: max(2, total // 100)   # noqa: E731
# the material exchange (data/bank.json exchanges, docs/mechanics/MATERIAL_EXCHANGE.md): a counter line carrying
# exchange_for costs exactly count x the bank's price for that material
EXCHANGE_KINDS = ("evolution_item", "held_item", "ball")
WORLD_READS: set = set()   # nothing here reads a world


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def base_entries(doc):
    return json.loads((ROOT / doc["base"]).read_text(encoding="utf-8"))["bank"]


def entries(doc):
    """The file CobbleDollars reads: the base's entries in order, then ours."""
    return list(base_entries(doc)) + [{"item": b["item"], "price": b["price"]} for b in doc["buys"]]


def text(doc):
    return json.dumps({"bank": entries(doc)}, indent=2) + "\n"


def prices(doc):
    return {e["item"]: int(e["price"]) for e in entries(doc)}


def write(doc):
    out = ROOT / doc["output"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text(doc), encoding="utf-8", newline="\n")
    return out


# ------------------------------------------------------------------------------------------------ sell points
def _v(x):
    return x[1] if isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], int) else x


def shop_points(where, shop):
    """(where, item, unit price) of a CobbleMerchantShop-shaped list (template NBT or authored)."""
    out = []
    for cat in _v(shop) or []:
        cat = _v(cat)
        for off in _v(cat.get("Offers")) or []:
            off = _v(off)
            item = _v(off.get("Item")) or {}
            iid, cnt = _v(item.get("id")), int(_v(item.get("count")) or 1)
            out.append(("%s / %s" % (where, _v(cat.get("Category"))), str(iid), int(str(_v(off.get("Price")))) / cnt))
    return out


def sell_points(server_dir=None):
    """Every authored place that sells an item, as (where, item, unit price); and what was not read."""
    pts, skipped = [], []
    m = json.loads(MARKETS.read_text(encoding="utf-8"))
    for grp in ("counters", "stalls"):
        for rec in m.get(grp) or []:
            for it in rec.get("stock") or []:
                pts.append(("markets %s %s" % (grp[:-1], rec["id"]), it["item"], it["price"] / (it.get("count") or 1)))
    farm = json.loads(FARM.read_text(encoding="utf-8")).get("merchant") or {}
    for it in farm.get("stock") or []:
        pts.append(("apricorn farm stall", it["item"], float(it["price"])))
    tdoc = json.loads(TRADERS.read_text(encoding="utf-8"))
    policy = tdoc.get("stock_policy") or {}
    st = policy.get("stones") or {}
    for iid in st.get("items") or []:
        pts.append(("the Exchange (stock_policy.stones)", iid, float(st["price"])))
    card = policy.get("trainer_card") or {}
    if card.get("item"):
        pts.append(("trainer card (stock_policy.trainer_card)", card["item"], float(card["price"])))
    shop_file = OURS / "default_shop.json"
    if not shop_file.is_file():
        shop_file = BASE_DEFAULT / "default_shop.json"
    for cat in json.loads(shop_file.read_text(encoding="utf-8")).get("defaultShop") or []:
        for name, offers in cat.items():
            for o in offers:
                pts.append(("defaultShop / %s" % name, o["item"], float(o["price"])))
    if server_dir is None:
        skipped.append("the %d data/traders.json shopkeepers' template shops (no --server-dir)" % len(tdoc["traders"]))
    else:
        import traders
        for t in tdoc["traders"]:
            _, data = traders.entity_of(server_dir, t["template"])      # SystemExit when a template is missing
            shop, _, _ = traders.apply_stock_policy(data, policy, stock=t.get("stock"), rid=t["id"])
            pts.extend(shop_points("trader %s" % t["id"], shop.get("CobbleMerchantShop")))
    return pts, skipped


# ------------------------------------------------------------------------------------------------ the rules
def problems(doc, server_dir=None):
    out = []
    base = {e["item"] for e in base_entries(doc)}
    seen = set()
    for b in doc.get("buys") or []:
        iid, price = b.get("item"), b.get("price")
        w = "buys %s" % iid
        if not ITEM.fullmatch(iid or ""):
            out.append("%s: not ns:path" % w)
        if iid in seen:
            out.append("%s: listed twice" % w)
        seen.add(iid)
        if iid in base:
            out.append("%s: already in the base bank at its own price; changing a base price is a separate decision" % w)
        if not (isinstance(price, int) and not isinstance(price, bool) and price > 0):
            out.append("%s: price %r is not a positive whole number" % (w, price))
        for k in ("group", "tier", "supply", "why"):
            if not b.get(k):
                out.append("%s: no %s" % (w, k))
        if not isinstance(b.get("rate_per_hour"), int) or b["rate_per_hour"] < 0:
            out.append("%s: rate_per_hour must be a whole number, 0 when no rate is claimed" % w)
    never = {n["item"]: n.get("why") for n in doc.get("never_buy") or []}
    for n in doc.get("never_buy") or []:
        if not n.get("why"):
            out.append("never_buy %s: no why" % n.get("item"))
    bank = prices(doc)
    for iid in sorted(set(bank) & set(never)):
        out.append("%s is bought at $%d but never_buy says: %s" % (iid, bank[iid], never[iid]))
    spawn = set(json.loads(SPAWN_BLOCKS.read_text(encoding="utf-8"))["blocks"])
    in_place = {b["item"] for b in doc.get("buys") or [] if b.get("in_place") is True}
    if in_place and not doc.get("in_place_evidence"):
        out.append("buys marked in_place with no in_place_evidence")
    for iid in sorted(in_place - spawn):
        out.append("buys %s: in_place is only for an item whose block is a spawn condition; this one is not" % iid)
    for iid in sorted((seen & spawn) - in_place):
        out.append("buys %s: a block a spawn condition names (data/spawn_blocks.json): the bank would pay players to "
                   "strip it out of the world" % iid)
    for raw, ingot in SMELTS.items():
        if raw in bank and ingot in bank and not bank[raw] <= bank[ingot] <= bank[raw] + SMELT_MAX:
            out.append("%s pays $%d against %s's $%d: a smelted item pays raw to raw + %d"
                       % (ingot, bank[ingot], raw, bank[raw], SMELT_MAX))
        if (raw in bank) != (ingot in bank):
            out.append("%s and %s: one is bought and not the other" % (raw, ingot))
    out += craft_problems(doc, bank)
    unreachable = {u.get("item"): u.get("why") for u in doc.get("unreachable") or []}
    for u in doc.get("unreachable") or []:
        if not ITEM.fullmatch(u.get("item") or "") or not u.get("why"):
            out.append("unreachable %r: needs item ns:path and why" % u)
    for iid in sorted(seen & set(unreachable)):
        out.append("buys %s: listed unreachable (%s); a price on what no player can get is a promise the world breaks"
                   % (iid, unreachable[iid]))
    pts, skipped = sell_points(server_dir)
    for where, iid, unit in pts:
        if iid in bank and unit <= bank[iid]:
            out.append("%s sells %s at $%s each, at or below the bank's $%d: buy and sell is free money"
                       % (where, iid, ("%g" % unit), bank[iid]))
    m = json.loads(MARKETS.read_text(encoding="utf-8"))
    out += [p for p, _ in effort_rows(doc, m) if p]
    out += exchange_problems(doc, m, bank)
    if (m.get("stall_merchant") or {}).get("kind") != "cobbledollars:cobble_merchant":
        out.append("data/markets.json stall_merchant.kind is not cobbledollars:cobble_merchant: stalls no longer open "
                   "the bank, and buyer_towns cannot be counted from them")
    for town in (doc.get("buyer_towns") or {}).get("towns") or []:
        if not merchants_in(m, town):
            out.append("buyer_towns %s: no sited stall merchant, so no place in town opens the bank" % town)
    f = ROOT / doc["output"]
    if not f.is_file():
        out.append("%s is missing: run tools/bank.py write" % doc["output"])
    elif json.loads(f.read_text(encoding="utf-8")) != json.loads(text(doc)):
        out.append("%s differs from what data/bank.json writes: run tools/bank.py write" % doc["output"])
    return out, skipped, len(pts)


def craft_problems(doc, bank):
    """data/bank.json crafts: a crafted item pays its inputs' bank total to total + CRAFT_MAX(total)."""
    out = []
    for item, inputs in sorted(((doc.get("crafts") or {}).get("recipes") or {}).items()):
        missing = sorted(i for i in inputs if i not in bank)
        if item not in bank or missing:
            out.append("crafts %s: the item%s not bought (%s)" % (
                item, "" if item in bank else " and/or its inputs", ", ".join(missing) or item))
            continue
        total = sum(bank[i] * int(n) for i, n in inputs.items())
        if not total <= bank[item] <= total + CRAFT_MAX(total):
            out.append("crafts %s pays $%d against its inputs' $%d at the bank: a crafted item pays its inputs to "
                       "inputs + %d" % (item, bank[item], total, CRAFT_MAX(total)))
    return out


def tier_hours(doc):
    """{tier: (typical hour, upper hour)} from effort_model.tiers: sum of rate x price over the tiers it draws from."""
    tiers = (doc.get("effort_model") or {}).get("tiers") or {}
    out = {}
    for name, t in tiers.items():
        src = set(t.get("from_tiers") or [])
        rows = [b for b in doc["buys"] if b.get("tier") in src]
        out[name] = (sum(b["rate_per_hour"] * b["price"] for b in rows),
                     sum(b.get("rate_per_hour_upper", b["rate_per_hour"]) * b["price"] for b in rows))
    return out


def effort_rows(doc, markets_doc):
    """[(problem or None, report line)] for every effort_model tier: half_wage and upper_wage against the battle income
    of the leg where the tier opens (data/markets.json income_basis.leg_by_badge, relayed model B)."""
    em = doc.get("effort_model")
    if not em:
        return []
    legs = {int(k): int(v) for k, v in ((markets_doc.get("income_basis") or {}).get("leg_by_badge") or {}).items()}
    H = em.get("max_leg_hours")
    rows = []
    for name, (typ, up) in sorted(tier_hours(doc).items()):
        leg = (em["tiers"][name] or {}).get("opens_leg")
        if leg not in legs or not isinstance(H, (int, float)) or H <= 0:
            rows.append(("effort_model tier %s: opens_leg %r is not a leg in income_basis.leg_by_badge, or "
                         "max_leg_hours %r is not positive" % (name, leg, H), ""))
            continue
        inc = legs[leg]
        line = ("tier %s (opens leg %d, battle income $%d): typical hour $%d x %gh = $%d against half the leg $%d; "
                "upper hour $%d x %gh = $%d against the leg" % (name, leg, inc, typ, H, typ * H, inc // 2, up, H, up * H))
        broken = [r for r, bad in (("half_wage", typ * H > inc / 2), ("upper_wage", up * H > inc)) if bad]
        rows.append(("effort_model %s: %s" % (" and ".join(broken), line) if broken else None, line))
    return rows


def exchange_lines(markets_doc):
    """[(record kind, record, line)] for every markets stock line carrying exchange_for."""
    out = []
    for grp in ("counters", "stalls"):
        for rec in markets_doc.get(grp) or []:
            for it in rec.get("stock") or []:
                if "exchange_for" in it:
                    out.append((grp[:-1], rec, it))
    return out


def exchange_floors(doc, markets_doc):
    """{kind: (floor, where it came from)}, each read from data, never a constant (data/bank.json exchanges.floors)."""
    stones = (json.loads(TRADERS.read_text(encoding="utf-8")).get("stock_policy") or {}).get("stones") or {}
    held = set((((doc.get("exchanges") or {}).get("floors") or {}).get("held_item") or {}).get("from_items") or [])
    units, held_units = [], []
    for grp in ("counters", "stalls"):
        for rec in markets_doc.get(grp) or []:
            for it in rec.get("stock") or []:
                if "exchange_for" in it:
                    continue
                u = it["price"] / (it.get("count") or 1)
                units.append(u)
                if it["item"] in held:
                    held_units.append((u, it["item"]))
    return {"evolution_item": (stones.get("price"), "data/traders.json stock_policy.stones.price"),
            "held_item": (max(held_units)[0] if held_units else None, "the dearest held item on a shelf (%s)"
                          % (max(held_units)[1] if held_units else "none sold")),
            "ball": (max(units) if units else None, "the dearest non-exchange line on any shelf")}, \
        sorted(held - {i for _, i in held_units})


def exchange_problems(doc, markets_doc, bank):
    out = []
    ex = doc.get("exchanges") or {}
    towns = set(ex.get("towns") or [])
    floors, stale = exchange_floors(doc, markets_doc)
    for i in stale:
        out.append("exchanges.floors.held_item names %s, which no shelf sells: the floor is read from a stale list" % i)
    for k, (f, src) in floors.items():
        if f is None:
            out.append("exchanges floor for %s cannot be read (%s)" % (k, src))
    for kind, rec, it in exchange_lines(markets_doc):
        w = "%s %s line %s" % (kind, rec.get("id"), it.get("id"))
        ef = it.get("exchange_for") or {}
        mat, n = ef.get("item"), ef.get("count")
        if kind != "counter":
            out.append("%s: an exchange line on a stall: a stall's power line is ungated and its theme is checked by "
                       "word; exchanges live on counters" % w)
        if rec.get("path") != "off_path":
            out.append("%s: on the critical path, so on the price curve; an exchange is sold off the path" % w)
        if rec.get("status") != "sited":
            out.append("%s: its counter is not sited, so nothing sells it" % w)
        if rec.get("town") not in towns:
            out.append("%s: town %s is not in data/bank.json exchanges.towns" % (w, rec.get("town")))
        if mat not in bank:
            out.append("%s: exchange_for %r is not bought by the bank: the effort has no dollar value" % (w, mat))
            continue
        if not (isinstance(n, int) and not isinstance(n, bool) and n > 0):
            out.append("%s: exchange_for count %r is not a positive whole number" % (w, n))
            continue
        cnt = it.get("count") or 1
        if it.get("price") != n * bank[mat] * cnt:
            out.append("%s: $%s is not %d x the bank's $%d for %s = $%d: the exchange would lie about its rate"
                       % (w, it.get("price"), n, bank[mat], mat, n * bank[mat] * cnt))
        if it.get("item") in bank:
            out.append("%s: the bank buys %s back at $%d: a round trip" % (w, it["item"], bank[it["item"]]))
        k = it.get("kind")
        if k not in EXCHANGE_KINDS or k not in (ex.get("kinds") or {}):
            out.append("%s: kind %r is not one of %s (and declared in exchanges.kinds)" % (w, k, EXCHANGE_KINDS))
        elif floors[k][0] is not None:
            unit = it["price"] / cnt
            ok = unit >= floors[k][0] if k == "evolution_item" else unit > floors[k][0]
            if not ok:
                out.append("%s: $%g is under the %s floor $%g (%s): cheaper power than the shelves already price"
                           % (w, unit, k, floors[k][0], floors[k][1]))
    return out


def merchants_in(markets_doc, town):
    return [s["id"] for s in markets_doc.get("stalls") or [] if s.get("town") == town and s.get("status") == "sited"]


# ------------------------------------------------------------------------------------------------ report
def report(doc):
    lines = []
    bank = prices(doc)
    m = json.loads(MARKETS.read_text(encoding="utf-8"))
    for grp in ("minerals", "apricorns", "berries", "drops", "nether"):
        row = ["%s $%d" % (b["item"].split(":", 1)[1], b["price"]) for b in doc["buys"] if b["group"] == grp]
        lines.append("%s: %s" % (grp, ", ".join(row)))
    for tier in ("early", "deep"):
        tiers = ("early",) if tier == "early" else ("early", "deep")
        hour = [(b["item"], b["rate_per_hour"], bank[b["item"]]) for b in doc["buys"]
                if b["tier"] in tiers and b["rate_per_hour"] and b["group"] == "minerals"]
        lines.append("%s mining hour (ESTIMATE, assumed rates): %s = $%d" % (
            tier, " + ".join("%d %s x $%d" % (r, i.split(":", 1)[1], p) for i, r, p in hour),
            sum(r * p for _, r, p in hour)))
    for town in doc["buyer_towns"]["towns"]:
        lines.append("bank opens in %s at: %s" % (town, ", ".join(merchants_in(m, town)) or "NOWHERE"))
    for _, line in effort_rows(doc, m):
        lines.append("effort (ESTIMATE, assumed rates): " + line)
    for kind, rec, it in exchange_lines(m):
        ef = it["exchange_for"]
        lines.append("exchange at %s (%s): %s for %d %s = $%d" % (rec["id"], rec["town"], it["item"].split(":", 1)[1],
                                                                ef["count"], ef["item"].split(":", 1)[1], it["price"]))
    base = {e["item"] for e in base_entries(doc)}
    for u in doc.get("unreachable") or []:
        if u["item"] in base:
            lines.append("DORMANT base price: %s at $%d, which no player can get (%s)"
                         % (u["item"], bank[u["item"]], u["why"][:80]))
    lines.append("%d entries: %d base + %d ours" % (len(entries(doc)), len(base_entries(doc)), len(doc["buys"])))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("write")
    c = sub.add_parser("check")
    c.add_argument("--server-dir", help="read the shopkeeper templates from <dir>/mods/*.jar and <dir>/datapacks/*.zip")
    sub.add_parser("report")
    a = ap.parse_args(argv)
    doc = load()
    if a.cmd == "write":
        print("wrote %s (%d entries)" % (write(doc).relative_to(ROOT).as_posix(), len(entries(doc))))
        return 0
    if a.cmd == "report":
        print("\n".join(report(doc)))
        return 0
    out, skipped, n = problems(doc, a.server_dir)
    for p in out:
        print("PROBLEM " + p)
    for s in skipped:
        print("NOT CHECKED " + s)
    print("bank: %d problems; %d entries against %d sell points%s" % (
        len(out), len(entries(doc)), n, "" if not skipped else " (partial: %d source(s) not read)" % len(skipped)))
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
