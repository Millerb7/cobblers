#!/usr/bin/env python
"""The players' item and money guide, docs/player/items.html: how money is earned and spent, and, for every item a
player can get from a PUBLIC source, where and for how much.

  python tools/player_guide_items.py            # write docs/player/items.html and register it in guides.json
  python tools/player_guide_items.py --check    # regenerate in memory; exit 1 if the page or its entry is stale
  python tools/player_guide_items.py --out F    # write elsewhere (not the site's page, not registered)

WHY A GENERATOR OF ITS OWN. The site is one generator per page: guides.json names each page's generator and
tools/player_site.py runs that generator's main() once per entry, so a generator that wrote two pages would run twice
and register one. Its inputs (the economy's tables) share nothing with the battle, map or starter guides beyond the
shared module and the jar's display names, which it imports.

THE SECTIONS, each one a key of the shared section filter (player_site.filter_nav):
  money   how money works: trainer wins (data/markets.json income_basis, written by tools/income_model.py), wild battles
          paying nothing (modpack/config/cobbledollars/common.json), the bank, the Produce Buyer
          (data/produce_buyer.json) and the paid training services (data/training_services.json)
  buy     the item dictionary: every item a player can buy, with each place, seller and price
            counters and stalls   data/markets.json `stock` of every SITED record (tools/markets.py merchant_records:
                                  what the merchants carry), at the merchant's unit price, price // count
                                  (tools/markets.py merchant_shop). `held_stock` and `superseded_stock` are NOT on
                                  sale, and an unsited record's stock is not either: none of them is ever a source
            Poke Marts            data/traders.json stock_policy.mart (the basics, the badge tiers, the Training shelf)
                                  by each clerk's tier (tools/traders.py mart_tiers); the trainer card and the
                                  Assayer's stones from the same policy
  barter  data/direct_trades.json `lines` whose status is approved: item-for-item trades
  sell    what the bank buys (modpack/config/cobbledollars/bank.json, the file CobbleDollars reads, written by
          tools/bank.py) and the Produce Buyer's crates
  craft   the training items' recipes (docs/mechanics/SERVICES_AND_CRAFTING.md section 1), read from the Cobblemon jar

WHAT THE PAGE NEVER LISTS (the owner, 2026-10-08: "A player seeing an item with no source will go looking for it, and
that is exactly the discovery we are protecting"). An item enters the dictionary only through a source above; an item
whose only source is a cache, shrine, legendary, story reward or dungeon is LEFT OUT, not listed as "found in the
world". So:
  - a held or superseded counter line is never a source, and an item with nothing else is left out (and named in this
    tool's console output, never on the page);
  - the bank's buy list leaves out what the bank can never be offered (data/bank.json `unreachable`) and the namespaces
    in HIDDEN_NAMESPACES, whose items are story and altar items;
  - no coordinate, NPC seat or keeper position is printed: a seller is named by its town and its keeper's name.
tests/test_player_site_leaks.py holds the page to that.

Not checked in a running game: the prices are the data's (the counters' merchants, the Marts' authored lines), the
income is computed from the trainers' teams by tools/income_model.py, and the Produce Buyer and the training services
have not been run (experiments EXP-061, EXP-062).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import player_site  # noqa: E402  the shared header, footer, filter and manifest of docs/player/
import player_guide_battles as PB  # noqa: E402  the jar finder
import markets as MK  # noqa: E402  which records the merchants carry, and their unit prices
import traders as TR  # noqa: E402  the Mart clerks' tiers and shelves

OUT = ROOT / "docs" / "player" / "items.html"
GUIDE = {"file": "items.html", "title": "Items and money", "label": "Items and money", "order": 30,
         "description": "How money works, and every item you can buy, barter for, sell or craft: where, from whom "
                        "and for how much.",
         "generator": "tools/player_guide_items.py"}
BANK = "modpack/config/cobbledollars/bank.json"
COMMON = "modpack/config/cobbledollars/common.json"
# namespaces whose items the bank buys but the page does not name: LumyMon's feathers are given by the story and
# used at its altars (docs/research/notes/lumymon-altars.md; data/research_station.json is their one source)
HIDDEN_NAMESPACES = {"lumymon": "LumyMon's feathers and altar items: story items, never sold (data/research_station.json)"}
# the training items whose recipe matters (docs/mechanics/SERVICES_AND_CRAFTING.md section 1); recipes from the jar
CRAFTED = ("medicinal_brew", "pp_up", "hp_up", "protein", "iron", "calcium", "zinc", "carbos",
           "health_mochi", "muscle_mochi", "resist_mochi", "genius_mochi", "clever_mochi", "swift_mochi",
           "fresh_start_mochi", "power_weight", "power_bracer", "power_belt", "power_lens", "power_band",
           "power_anklet", "health_feather", "muscle_feather", "resist_feather", "genius_feather", "clever_feather",
           "swift_feather")
STATIONS = {"cobblemon:brewing_stand": "brewing stand", "cobblemon:cooking_pot_shapeless": "campfire pot",
            "cobblemon:cooking_pot": "campfire pot", "minecraft:crafting_shaped": "crafting table",
            "minecraft:crafting_shapeless": "crafting table"}
TAGS = {"c:concretes": "any concrete", "c:gems/diamond": "Diamond"}
# vanilla ids whose title-cased id is not the game's English name (minecraft:potion in a recipe is the water bottle,
# not a Potion); the Cobblemon jar carries no vanilla names, and the rest title-case to the game's own
VANILLA_NAMES = {"minecraft:potion": "Water Bottle", "minecraft:beef": "Raw Beef", "minecraft:chicken": "Raw Chicken",
                 "minecraft:mutton": "Raw Mutton", "minecraft:rabbit": "Raw Rabbit",
                 "minecraft:porkchop": "Raw Porkchop", "minecraft:diamond_block": "Block of Diamond",
                 "minecraft:netherite_block": "Block of Netherite", "minecraft:quartz": "Nether Quartz"}
EXAMPLE_LEVEL_SUMS = (20, 60, 150, 300)
SECTIONS = (("money", "How money works"), ("buy", "Where to buy"), ("barter", "Barter"), ("sell", "Selling"),
            ("craft", "Crafting"))

esc = player_site.esc
money = MK.money


def doc(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def pretty(ident):
    return " ".join(w.capitalize() for w in re.split(r"[_\s/-]+", str(ident).split(":")[-1]) if w)


# ------------------------------------------------------------------------------------------------ names


class Names:
    """An item's display name: the shelves' own `name` (data/markets.json), else the Cobblemon jar's, else the id
    title-cased (counted in `guessed`)."""

    def __init__(self, jar, mk):
        self.lang = json.loads(zipfile.ZipFile(jar).read("assets/cobblemon/lang/en_us.json").decode("utf-8"))
        self.shelf = {}

        def walk(n):
            if isinstance(n, dict):
                if isinstance(n.get("item"), str) and isinstance(n.get("name"), str):
                    self.shelf.setdefault(n["item"], n["name"])
                for v in n.values():
                    walk(v)
            elif isinstance(n, list):
                for v in n:
                    walk(v)
        walk(mk)
        self.guessed = set()

    def __call__(self, ident):
        if ident in VANILLA_NAMES:
            return VANILLA_NAMES[ident]
        if ident in self.shelf:  # a shelf's note on its line ("Copper Ingots (ball cores)") is not the item's name
            return re.sub(r"\s*\([^)]*\)$", "", self.shelf[ident])
        ns, _, path = ident.rpartition(":")
        for key in ("item.%s.%s" % (ns or "minecraft", path), "block.%s.%s" % (ns or "minecraft", path)):
            if key in self.lang:
                return self.lang[key]
        self.guessed.add(ident)
        return pretty(ident)


# ------------------------------------------------------------------------------------------------ inputs


def place_names(mk):
    """{town id: display name}: data/towns.json, then each data/markets.json places_beyond_towns record's own file's
    top-level display_name or name (a farm with a stand and no town record)."""
    out = {t["id"]: t.get("display_name") or pretty(t["id"]) for t in doc("data/towns.json")["towns"]}
    for p in mk.get("places_beyond_towns") or []:
        d = doc(p["source"])
        out.setdefault(p["town"], d.get("display_name") or d.get("name") or pretty(p["town"]))
    return out


def shop_sources(mk, towns):
    """{item: [source]} of every line a sited counter or stall's merchant carries, at its unit price; and the
    [(record id, line)] of every held, superseded or unsited line (never a source)."""
    out, not_sold = {}, []
    sited = {id(r) for r, _k in MK.merchant_records(mk)}
    for rec in (mk.get("counters") or []) + (mk.get("stalls") or []):
        for key in ("held_stock", "superseded_stock"):
            not_sold += [(rec["id"], key, line) for line in rec.get(key) or []]
        if id(rec) not in sited:
            not_sold += [(rec["id"], "unsited", line) for line in rec.get("stock") or []]
            continue
        for line in rec.get("stock") or []:
            # the seller is named by its shop screen's title (the record's `category`, its CobbleMerchantShop
            # category), not its keeper's name: "Fisher", Pacifidlog's keeper, is also a story NPC's label in
            # data/dialogue.json, and the leak test rightly cannot tell the two apart
            out.setdefault(line["item"], []).append({
                "kind": "shop", "line": "%s/%s" % (rec["id"], line["id"]), "town": towns[rec["town"]],
                "seller": rec.get("category") or "the market", "keeper": (rec.get("keeper") or {}).get("name"),
                "price": int(line["price"]) // int(line.get("count") or 1),
                "gate": mk.get("badges", {}).get(line["gate"]) if line.get("gate") else None})
    return out, not_sold


def mart_sources(td, towns):
    """{item: [source]} of the Poke Marts' authored shelves: the basics, each badge tier, the Training shelf, the
    trainer card and the Assayer's stones."""
    policy = td["stock_policy"]
    tiers = TR.mart_tiers(td, doc("data/towns.json"))
    clerks = [r for r in td["traders"] if r.get("stock") == "mart"]
    out = {}

    def where(badges, item):
        hit, dear = [], []
        for r in clerks:
            if tiers.get(r["id"], 0) >= badges:
                hit.append(towns[r["settlement"]])
                if item in TR.early_reach_prices(policy, r["id"]):
                    dear.append(towns[r["settlement"]])
        return sorted(set(hit)), sorted(set(dear))

    def add(item, badges, price, shelf):
        hit, dear = where(badges, item)
        if hit:
            out.setdefault(item, []).append({"kind": "mart", "badges": badges, "towns": hit, "dearer": dear,
                                             "price": price, "shelf": shelf})
    for item in TR.mart_items(policy):
        add(item, 0, None, "basics")
    for t in policy["mart"].get("tiers") or []:
        for item in t.get("items") or []:
            add(item, t["badges"], None, "badge tier")
    tr = policy["mart"].get("training") or {}
    for t in tr.get("tiers") or []:
        for off in t.get("items") or []:
            add(off["item"], t["badges"], int(off["price"]), tr.get("category") or "Training")
    card = TR.card_policy(policy)
    if card:
        rec = next(r for r in td["traders"] if r["id"] == card["trader"])
        out.setdefault(card["item"], []).append({"kind": "clerk", "town": towns[rec["settlement"]],
                                                 "seller": "the Poke Mart", "price": int(card["price"])})
    st = policy.get("stones") or {}
    for rec in [r for r in td["traders"] if r.get("stock") == "stones"]:
        for item in st.get("items") or []:
            out.setdefault(item, []).append({"kind": "clerk", "town": towns[rec["settlement"]],
                                             "seller": st.get("name") or "the Exchange", "price": int(st["price"])})
    return out


def barter_lines(dt, mk, towns):
    counter = next(c for c in mk["counters"] if c["id"] == dt["counter_site"]["near_counter"])
    town = towns[counter["town"]]
    who = dt["counter_barterer"]["name"]
    return [{"id": ln["id"], "town": town, "seller": who, "sell": ln["sell"],
             "give": [ln["buy"]] + ([ln["buyB"]] if ln.get("buyB") else [])}
            for ln in dt.get("lines") or [] if ln.get("status") == "approved"]


def recipes(jar):
    """{item id: [(station, [(count, ingredient)], made)]} for CRAFTED, read from the jar. Stops on a shape it does
    not read."""
    z = zipfile.ZipFile(jar)
    want = {"cobblemon:%s" % c for c in CRAFTED}
    out = {}
    for n in sorted(z.namelist()):
        if not (n.startswith("data/cobblemon/recipe/") and n.endswith(".json")):
            continue
        r = json.loads(z.read(n).decode("utf-8"))
        res = r.get("result")
        res = res.get("id") if isinstance(res, dict) else None  # some recipes carry a list of results: none we want
        if res not in want:
            continue
        typ = r.get("type")
        if typ not in STATIONS:
            raise SystemExit("%s: recipe type %r is not one this page can put in words" % (n, typ))
        if typ == "cobblemon:brewing_stand":
            parts = [(1, r["bottle"]), (1, r["input"])]
        elif "ingredients" in r:  # shapeless: the same ingredient twice is said once, with its count
            parts = []
            for i in r["ingredients"]:
                hit = next((k for k, (_c, p) in enumerate(parts) if p == i), None)
                if hit is None:
                    parts.append((1, i))
                else:
                    parts[hit] = (parts[hit][0] + 1, i)
        elif "pattern" in r:
            counts = {}
            for ch in "".join(r["pattern"]):
                if ch != " ":
                    counts[ch] = counts.get(ch, 0) + 1
            parts = [(counts[k], r["key"][k]) for k in sorted(counts)]
        else:
            raise SystemExit("%s: a %s recipe with no ingredients this page can read" % (n, typ))
        out.setdefault(res, []).append((STATIONS[typ], parts, int((r.get("result") or {}).get("count") or 1)))
    missing = sorted(want - set(out))
    if missing:
        raise SystemExit("the jar has no recipe for %s" % ", ".join(missing))
    return out


def collect(jar_path=None):
    jar = PB.find_jar(jar_path)
    mk, td, dt = doc("data/markets.json"), doc("data/traders.json"), doc("data/direct_trades.json")
    bank_doc = doc("data/bank.json")
    towns = place_names(mk)
    name = Names(jar, mk)
    shops, not_sold = shop_sources(mk, towns)
    marts = mart_sources(td, towns)
    barter = barter_lines(dt, mk, towns)
    crafts = recipes(jar)
    buy = {}
    for src in (shops, marts):
        for item, rows in src.items():
            buy.setdefault(item, []).extend(rows)
    obtainable = set(buy) | {b["sell"]["id"] for b in barter} | set(crafts)
    # the bank's buy list, less what can never be offered and the hidden namespaces
    unreachable = {u["item"]: u.get("why", "") for u in bank_doc.get("unreachable") or []}
    sell, excluded = [], []
    for e in doc(BANK)["bank"]:
        ns = e["item"].split(":")[0]
        if ns in HIDDEN_NAMESPACES:
            excluded.append((e["item"], "the bank buys it; " + HIDDEN_NAMESPACES[ns]))
        elif e["item"] in unreachable:
            excluded.append((e["item"], "the bank buys it; data/bank.json unreachable"))
        else:
            sell.append({"item": e["item"], "price": int(e["price"])})
    for rid, key, line in not_sold:
        if line["item"] not in obtainable:
            excluded.append((line["item"], "%s %s of %s, sold nowhere" % (key, line["id"], rid)))
    names = {i: name(i) for i in sorted(obtainable | {s["item"] for s in sell}
                                        | {g["id"] for b in barter for g in b["give"]}
                                        | {q["item"] for rs in crafts.values() for _s, ps, _m in rs for _c, p in ps
                                           for q in (p if isinstance(p, list) else [p]) if "item" in q})}
    common = doc(COMMON)
    return {"buy": buy, "barter": barter, "crafts": crafts, "sell": sell, "names": names,
            "excluded": sorted(set(excluded)), "guessed": sorted(name.guessed), "not_sold": not_sold,
            "income": mk["income_basis"], "multiplier": float(common.get("cobbleDollarsIncomeMultiplier", 1)),
            "wild_pays": bool(common.get("earnCobbleDollarsFromWildPokemon")),
            "produce": doc("data/produce_buyer.json"), "services": doc("data/training_services.json")["services"],
            "badges": mk.get("badges", {})}


# ------------------------------------------------------------------------------------------------ render


def dollars(n):
    return "$" + money(n)


def where_words(s):
    if s["kind"] == "shop":
        gate = " (with %s)" % s["gate"] if s["gate"] else ""
        return "%s: %s%s" % (s["town"], s["seller"], gate)
    if s["kind"] == "clerk":
        return "%s: %s" % (s["town"], s["seller"])
    if s["badges"] == 0:
        return "Every Poke Mart"
    return "The Poke Marts of towns reached with %d badge%s: %s" % (s["badges"], "" if s["badges"] == 1 else "s",
                                                                   ", ".join(s["towns"]))


def price_words(s):
    said = "the Mart's price" if s.get("price") is None else dollars(s["price"])
    if s.get("dearer"):
        said += " (dearer at %s)" % ", ".join(s["dearer"])
    return said


def row_attrs(item, nm):
    return 'data-item data-name="%s"' % esc(("%s %s" % (nm, item)).lower())


def render_money(m):
    ib = m["income"]
    mult = m["multiplier"]
    ex = []
    for s in EXAMPLE_LEVEL_SUMS:
        b = max(1, s * s // 10)
        ex.append('<tr><td class="n">%d</td><td class="n">%s</td><td class="n">%s to %s</td></tr>'
                  % (s, dollars(int(mult * 2.25 * b)), dollars(int(mult * 1.5 * b)), dollars(int(mult * 3 * b))))
    legs = []
    ch = ib["challenge"]["leg_by_badge"]
    for k in sorted(ib["leg_by_badge"], key=int):
        legs.append('<tr><td>Gym %s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td></tr>'
                    % (k, dollars(ib["leg_by_badge"][k]), dollars(ch[k]), dollars(ib["cumulative_by_badge"][k])))
    post = ib["post_badge_8"]
    for key, label in (("victory_road", "Victory Road"), ("league", "The Elite Four and the Champion")):
        legs.append('<tr><td>%s</td><td class="n">%s</td><td class="n">%s</td><td></td></tr>'
                    % (label, dollars(post["normal"][key]), dollars(post["challenge"][key])))
    pb = m["produce"]
    crates = "".join("<li>%d %s</li>" % (c["count"], esc(c["label"])) for c in pb["crates"])
    sched = []
    for r in pb["schedule"]["rows"]:
        lo, hi = r["badges"]
        held = "%d" % lo if lo == hi else "%d to %d" % (lo, hi)
        sched.append('<tr><td>%s</td><td class="n">%s</td><td class="n">%d</td></tr>'
                     % (held, dollars(r["price"]) if r["price"] else "buys nothing", r["crates"]))
    sv = m["services"]
    badge = lambda g: m["badges"].get(g, g) if g else None
    ev_gate, iv_gate = badge(sv["ev"].get("gate")), badge(sv["iv"].get("gate"))
    return (
        '<section %s><h2>How money works</h2>'
        '<h3>Beating trainers</h3><p>Money comes from beating trainers. <b>Wild battles pay nothing.</b>%s A win pays '
        'by the beaten team\'s levels added up: on average about %s times the square of that total, and anywhere '
        'from two thirds to four thirds of the average.</p>'
        '<div class="wide"><table><thead><tr><th class="n">Team\'s levels added up</th><th class="n">Pays about</th>'
        '<th class="n">Range</th></tr></thead><tbody>%s</tbody></table></div>'
        '<p>Beating every trainer once on the way to each gym, the gym\'s own trainers and its leader pays about:</p>'
        '<div class="wide"><table><thead><tr><th>Up to and including</th><th class="n">Normal</th>'
        '<th class="n">Challenge</th><th class="n">Normal, running total</th></tr></thead><tbody>%s</tbody></table>'
        '</div><p class="small">Computed from the trainers\' teams, not counted in game; a rematch pays again.</p>'
        '<h3>The bank</h3><p>Every shopkeeper at a counter, a market stall or a Poke Mart opens the bank: shift and '
        'right-click them, or press the Bank button on their shop screen. Put items in and press Sell; each is paid '
        'at the bank\'s price, the same in every town. What it buys is under <a href="#sell">Selling</a>.</p>'
        '<h3>The Produce Buyer</h3><p>The Produce Buyer at the apricorn farm buys farm goods by the crate, and pays '
        'less as your badges grow. A crate is one of:</p><ul>%s</ul>'
        '<div class="wide"><table><thead><tr><th>Badges you hold</th><th class="n">Per crate</th>'
        '<th class="n">Crates until your next badge</th></tr></thead><tbody>%s</tbody></table></div>'
        '<h3>Paid training</h3><p>The coach at each training ground sells three shortcuts. Training by battle, or '
        'crafting the items (see <a href="#craft">Crafting</a>), is always cheaper.</p><ul>'
        '<li><b>Train to your cap</b>: %s a Pokemon, raised straight to your level cap (up to a cap of %d).</li>'
        '<li><b>Effort training</b>: %s a Pokemon, a two-stat training plan%s.</li>'
        '<li><b>Perfect a stat</b>: %s a stat, or %s for all six%s.</li></ul></section>'
        % (player_site.section_attr("money"),
           "" if not m["wild_pays"] else " (This server's settings say wild battles pay: tell an operator.)",
           "%.2f" % (mult * 2.25 / 10), "".join(ex), "".join(legs), crates, "".join(sched),
           dollars(sv["raise"]["price"]), sv["raise"]["max_cap"],
           dollars(sv["ev"]["price"]), ", once you hold %s" % ev_gate if ev_gate else "",
           dollars(sv["iv"]["price_per_stat"]), dollars(6 * sv["iv"]["price_per_stat"]),
           ", once you hold %s" % iv_gate if iv_gate else ""))


def render_buy(m):
    rows = []
    for item in sorted(m["buy"], key=lambda i: (m["names"][i].lower(), i)):
        srcs = sorted(m["buy"][item], key=lambda s: (s.get("price") is None, s.get("price") or 0, where_words(s)))
        lis = "".join('<li data-src="%s">%s, %s</li>' % (s["kind"], esc(where_words(s)), esc(price_words(s)))
                      for s in srcs)
        rows.append('<tr %s><td>%s<span class="id">%s</span></td><td><ul>%s</ul></td></tr>'
                    % (row_attrs(item, m["names"][item]), esc(m["names"][item]), esc(item), lis))
    return ('<section %s><h2>Where to buy</h2><p>Every item on sale, A to Z, with each place that sells it: the town '
            'and the title of the shop screen. Counter and stall prices are each; a shopkeeper sells to anyone who '
            'reaches the counter. A Poke Mart\'s stock '
            'grows with how far along the road its town is.</p><div class="wide"><table><thead><tr><th>Item</th>'
            '<th>Where, and the price</th></tr></thead><tbody>%s</tbody></table></div></section>'
            % (player_site.section_attr("buy"), "".join(rows)))


def render_barter(m):
    nm = m["names"]
    rows = []
    for b in m["barter"]:
        give = " and ".join("%d %s" % (g["count"], nm[g["id"]]) for g in b["give"])
        rows.append('<tr %s><td>%d %s</td><td>%s</td><td>%s: %s</td></tr>'
                    % (row_attrs(b["sell"]["id"], nm[b["sell"]["id"]]), b["sell"]["count"], esc(nm[b["sell"]["id"]]),
                       esc(give), esc(b["town"]), esc(b["seller"])))
    return ('<section %s><h2>Barter</h2><p>Item-for-item trades: no money changes hands. Put both items in the trade '
            'screen.</p><div class="wide"><table><thead><tr><th>You get</th><th>You give</th><th>Where</th></tr>'
            '</thead><tbody>%s</tbody></table></div></section>' % (player_site.section_attr("barter"), "".join(rows)))


def render_sell(m):
    nm = m["names"]
    rows = "".join('<tr %s><td>%s<span class="id">%s</span></td><td class="n">%s</td></tr>'
                   % (row_attrs(s["item"], nm[s["item"]]), esc(nm[s["item"]]), esc(s["item"]), dollars(s["price"]))
                   for s in sorted(m["sell"], key=lambda s: (nm[s["item"]].lower(), s["item"])))
    return ('<section %s><h2>Selling</h2><p>What the bank buys, at the same price everywhere. Anything not listed, it '
            'does not buy. Farm goods go to the Produce Buyer instead (<a href="#money">How money works</a>).</p>'
            '<div class="wide"><table><thead><tr><th>Item</th><th class="n">Pays each</th></tr></thead><tbody>%s'
            '</tbody></table></div></section>' % (player_site.section_attr("sell"), rows))


def ingredient(m, count, part):
    if isinstance(part, list):  # any one of these
        return " or ".join(ingredient(m, count, p) for p in part)
    if "item" in part:
        what = m["names"][part["item"]]
    elif "tag" in part:
        what = TAGS.get(part["tag"], pretty(part["tag"]) + " (any)")
    else:
        raise SystemExit("an ingredient this page cannot put in words: %r" % (part,))
    return "%d %s" % (count, what) if count > 1 else what


def render_craft(m):
    rows = []
    for item in sorted(m["crafts"], key=lambda i: (m["names"][i].lower(), i)):
        lis = "".join("<li>%s: %s%s</li>" % (esc(st), esc(" + ".join(ingredient(m, c, p) for c, p in parts)),
                                              esc(" (makes %d)" % made) if made > 1 else "")
                      for st, parts, made in m["crafts"][item])
        rows.append('<tr %s><td>%s</td><td><ul>%s</ul></td></tr>' % (row_attrs(item, m["names"][item]),
                                                                     esc(m["names"][item]), lis))
    return ('<section %s><h2>Crafting</h2><p>The training items worth making yourself: cheaper than buying them '
            'and far cheaper than paid training. A brewing stand cannot be crafted here (the region has no blaze '
            'rods), so brew at one you find standing in a town.</p><div class="wide"><table><thead><tr><th>Item</th>'
            '<th>Station and ingredients</th></tr></thead><tbody>%s</tbody></table></div></section>'
            % (player_site.section_attr("craft"), "".join(rows)))


def render(model):
    body = ('<main><h1>Items and money</h1><p class="lead">How you earn money, and every item you can buy, barter '
            'for, sell or craft. Pick a part, or search for an item by name.</p>%s%s%s%s%s%s%s'
            '<section id="not-covered"><h2>What this page leaves out</h2><ul>'
            '<li>Anything you can only find, win or be given in the world: those are left for you to discover.</li>'
            '<li>What a Poke Mart charges for its own basics: the price is on its shop screen.</li>'
            '<li>Prices and payouts in a running game: this page is generated from the campaign\'s data and has not '
            'been checked shop by shop. Where the game differs, the game is right: say so.</li></ul></section></main>'
            % (player_site.filter_nav(SECTIONS, label="Show one part"),
               player_site.search_box("[data-item]", "Find an item", "e.g. Potion"),
               render_money(model), render_buy(model), render_barter(model), render_sell(model), render_craft(model)))
    sources = ('<p class="src">From data/markets.json, data/traders.json, data/direct_trades.json, '
               'modpack/config/cobbledollars/, data/produce_buyer.json, data/training_services.json and the Cobblemon '
               '1.8.0 recipes.</p>')
    return player_site.page(GUIDE, body, body_class="page-items", not_covered_href="#not-covered",
                            sources_html=sources)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--jar", help="the Cobblemon 1.8 jar (default: the offline snapshot's mods folder)")
    p.add_argument("--check", action="store_true", help="regenerate in memory; exit 1 if the page differs or its "
                                                        "guides.json entry is not current")
    a = p.parse_args(argv)
    model = collect(a.jar)
    text = render(model)
    out = Path(a.out)
    entry = GUIDE if out.resolve() == OUT.resolve() else None  # a page written elsewhere is not the site's
    counts = "%d to buy, %d barter, %d to sell, %d to craft" % (len(model["buy"]), len(model["barter"]),
                                                               len(model["sell"]), len(model["crafts"]))
    if a.check:
        ok, why = player_site.check(out, text, entry)
        if not ok:
            print("%s is %s: run python tools/player_site.py" % (out, why))
            return 1
        print("%s is current (%s)" % (out, counts))
        return 0
    did = player_site.write(out, text, entry)
    print("%s %s: %s, %d bytes" % (did, out, counts, len(text.encode("utf-8"))))
    for item, why in model["excluded"]:
        print("  left out %-36s %s" % (item, why))
    if model["guessed"]:
        print("  named from the id (no shelf or jar name): %s" % ", ".join(model["guessed"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
