#!/usr/bin/env python
"""Independent audit of the economy: the Mart tiers (data/traders.json stock_policy.mart), the material exchange
(data/bank.json exchanges, the exchange_for lines of data/markets.json) and the Bank's buy list (data/bank.json ->
modpack/config/cobbledollars/bank.json through tools/bank.py).

Written by an agent that built none of the three. NOTHING here prices, tiers or checks with the builders' helpers
(tools/bank.py problems/craft_problems/exchange_problems/effort_rows, tools/traders.py mart_tier_items for an
expectation, tools/markets.py curve). The generators are CALLED only to obtain their output, the artifact under test:

  the bank      tools/bank.py text(load())  -- the file it writes -- and the committed modpack/config/cobbledollars/
                bank.json, which must be byte-equal (the committed file is what install copies to the server)
  the sellers   tools/markets.py build()             -> the summon lines of every sited counter's and stall's merchant
                tools/apricorn_farm.py merchant_data -> Hollin's stall merchant
                tools/traders.py town_functions      -> every shopkeeper's summon line, read from the shopkeeper
                                                        templates in a server's datapacks/mods (the offline snapshot)
                base-pack defaultShop                -> whatever merchant falls back to it
                Every shop is parsed from the emitted SNBT by this file's own reader, never from the data files.

Where each expectation comes from:
  arbitrage   the cheapest way to OBTAIN an item with money: the cheapest unit price any seller above offers, lowered by
              every vanilla or mod recipe (crafting, smelting, blasting, smoking, campfire, stonecutting, smithing) whose
              inputs are all obtainable that way, iterated to a fixed point; recipes and item tags are read from the
              jars (the vanilla 1.21.1 client jar and the server's mods/datapacks). FAILURE when the effective bank
              price of an item is above that cost (money from nothing); REPORT when it is equal (break-even).
  tiers       data/progression.json's chapters (chapter_N unlocked_by gym(N-1)_cleared: the badges a player holds on
              chapter N) and data/routes.json's critical routes (chapter, from_town, to_town, polyline). A gym town's
              Mart: the badges held on the route that ARRIVES there; the hometown: 0. An off-path Mart: the badges held
              on the critical route whose polyline passes nearest the clerk (ties to the fewer badges). FAILURE when
              the clerk's claimed tier (tools/traders.py mart_tiers, the builder's) is ABOVE this, or when the emitted
              shelf carries a tier line above the claimed tier. The reach gate (data/towns.json gates/access) is
              REPORTED: an ungated off-path Mart with a tier above 0 sells to a player who walked there early, which
              the tier_rule says the owner accepted ("a player who reaches a town early buys its shelf early").
  exchange    per exchange_for line, from the EMITTED offer price and the EFFECTIVE bank: dollars the material earns,
              the ratio price / earned, the reward against the leg income where it is sold (data/markets.json
              income_basis, RELAYED model B), and gathering hours against battling hours. The gathering rates and
              max_leg_hours are the builder's ASSUMED numbers (data/bank.json) -- there is no other source -- and are
              labelled so; the raw-material decomposition comes from the jars' recipes, not the builder's tables.
              These are REPORT lines: no threshold is derivable from the data, so none is invented.
  ids         an item exists when a jar carries a lang key item.<ns>.<path>/block.<ns>.<path> or an item model
              assets/<ns>/models/item/<path>.json. FAILURE for an id we author (data/bank.json buys, data/markets.json,
              data/apricorn_farm.json, the stock policy's authored shops); REPORT for an upstream id (the base bank,
              defaultShop, a BCA template offer).
  afk         a stated table of vanilla 1.21.1 items an unattended farm produces (below, AFK_FARMABLE), each with its
              mechanism; REPORT its effective bank price, the file:line that sets it, and whether data/bank.json
              overrides the base.
  barter      the item-for-item edges of data/direct_trades.json (the barterer, EXP-055), read by THIS file -- never
              through tools/direct_trades.py's edges() -- and the Offers.Recipes of the villager its place function
              emits, read by this file's SNBT reader (tools/direct_trades.py files() is CALLED only for its output, on
              a flat stand-in ground: the offers do not depend on the ground). Two groups, reported separately:
              "placed" (what the emitted villager offers) and "proposal" (every line that is not approved).
              Every cost A counts as 1 (vanilla 1.21.1 MerchantOffer clamps a discounted cost A to at least 1, and
              Hero of the Village takes at least 1 off it whatever priceMultiplier is -- read from the client jar's
              bytecode, 2026-10-06); a cost B as authored (no discount reaches it, same source). FAILURE when a
              cycle across the Bank, every seller, the recipes and the barter edges ends with more money or more of
              any barter item than it started with and the cycle needs a barter edge (a gain that exists without
              one is REPORTED as pre-existing); FAILURE when the emitted villager offers a recipe no placed data
              offer authors, omits one, or writes a fixed field (uses, maxUses, rewardExp, specialPrice, demand,
              priceMultiplier, xp) that is missing or differs from the data (the codec's defaults are maxUses 4,
              rewardExp true and xp 1, so a missing field is a different trade). The play-loop rules B1-B4
              (docs/mechanics/MINECRAFT_PLAY_LOOPS.md) are REPORTED: B1 an input that cannot be bought, B2 no input
              in AFK_FARMABLE, B3 no output the Bank buys (or one recipe away from one), B4 no cost A over 1 and no
              non-zero priceMultiplier on a line.
              Since 2026-10-08 the data declares TWO villagers (`barterer` at `site` with the experiment offers,
              `counter_barterer` at `counter_site` with the approved lines): FAILURE unless each is summoned once, on
              its site's block, with exactly its own offers. BYPASS: FAILURE when a line's worst-case inputs, valued at
              the Bank's price (a storage block through its jar recipe) or else their cheapest money price, are worth
              less than the output's cheapest money path, or, where it has none, the counter lines the line names as
              its reference (the owner, 2026-10-08: "an alternative path, not a bypass"). PREMIUM: FAILURE when the
              Bank pays more for the output than the inputs are worth to it. An arena prize sold as stock is REPORTED.
  forceload   every block the R18DT functions read or write and every summon they place, read from the EMITTED
              functions, must lie in a chunk a forceload holds when the step runs them, and no hold may be released
              before a function they schedule has had its ticks (tools/direct_trades.py steps(), the reapply step).
  Mart prices the early-reach band of data/traders.json stock_policy.mart.early_reach_pricing, recomputed from its
              criterion over the EMITTED shelves (mart_price_checks); a ball in the convenience band fails the band's
              stated premise. Training lines (stock_policy.mart.training) join the tier table.
  vitamins    EV_IV_TRAINING.md 4.2 E2: no vitamin obtainable at or under the Bank's own vitamin price.
  rewards     a counter line selling a gym leader's first-win reward ahead of the counter's badge, or in an ungated
              off-path town, is REPORTED with the income at that badge (the counters have no early-reach band).

  python tools/economy_audit.py [--server-dir SNAPSHOT] [--vanilla-jar JAR] [--no-jars]

Exit 1 on any FAILURE. The last line is the problem count.

What this does NOT cover:
  - anything in a running game: that a merchant's purchase or the Bank's sale completes (P-7), duplication or races;
  - a merchant a donor template places that no data file names, natural CobbleDollars merchants, villagers' trades,
    loot (chests, bastions, Pasture Loot, Pickup), quests and rewards that hand out a bought item;
  - recipes added by our own generated datapacks after the snapshot date, brewing (Cobblemon's medicine brews are not
    recipe JSON), custom/special recipes, and container remainders (a bucket given back is counted as consumed);
  - smelting fuel (counted as free, so a smelting chain is flagged at its most generous);
  - whether vanilla mob spawning is on (the AFK table lists what a farm WOULD make);
  - the gathering rates, the leg incomes and max_leg_hours, which are assumed or relayed until timed in staging;
  - the stability of the off-path tier: it is the nearest critical route, and the margin to the next route is printed
    because a few blocks can move it;
  - for barter: that the villager trades at all, keeps its offers, or that its cost A really stays put in a running game
    (EXP-055); a gain that needs more than BARTER_ROUNDS conversion rounds; a cycle that pays in an item no seller,
    recipe or barter produces from the item it starts with (that is a conversion of gathered goods, not a loop, and
    B1-B3 report it); B2 against inputs made one recipe away from a farmed item (gold in a netherite ingot);
  - for the barterers' sites: anything a world holds (the place function's own read-back is what refuses a missing
    roof); lightning beyond the template's roof; whether a villager in the Mart blocks a player's path (judged by hand
    from the template, not checked here); forceload for any reapply step other than R18DT;
  - the reach a clerk or counter is priced for: early_reach_pricing.traders is the owner's list, and an ungated town not
    on it (Northlight, Fossick) is reported, never failed.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import re
import sys
import zipfile
from functools import lru_cache
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

DATA = ROOT / "data"
BASE_BANK = ROOT / "base-pack" / "cobbleverse" / "config" / "cobbledollars" / "bank.json"
BASE_SHOP = ROOT / "base-pack" / "cobbleverse" / "config" / "cobbledollars" / "default_shop.json"
OUR_SHOP = ROOT / "modpack" / "config" / "cobbledollars" / "default_shop.json"
COMMITTED_BANK = ROOT / "modpack" / "config" / "cobbledollars" / "bank.json"
DIRECT_TRADES = DATA / "direct_trades.json"

DEFAULT_SNAPSHOT = "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05"
DEFAULT_VANILLA = "C:/Users/wnd/AppData/Roaming/ModrinthApp/meta/versions/1.21.1-0.19.5/1.21.1-0.19.5.jar"

# Vanilla 1.21.1 items an unattended farm makes once built (the chunk loaded, nobody acting). The mechanism is the
# audit's statement of vanilla behaviour, not read from the repository.
# {item: (mechanism, [vanilla mobs the farm needs to SPAWN])}: a farm whose mob the server's mobsbegone blacklist
# names is reported as blocked by that config (whether mobsbegone also stops a villager-summoned golem or a spawner is
# not read here).
AFK_FARMABLE = {
    "minecraft:wheat": ("villager farmer or observer/piston crop farm", []),
    "minecraft:carrot": ("villager farmer crop farm", []),
    "minecraft:potato": ("villager farmer crop farm", []),
    "minecraft:baked_potato": ("potatoes from a villager farm through an auto-fed furnace", []),
    "minecraft:beetroot": ("villager farmer crop farm", []),
    "minecraft:bread": ("three wheat from a crop farm, one craft (a crafter block automates it)", []),
    "minecraft:melon_slice": ("observer melon farm", []),
    "minecraft:pumpkin_pie": ("observer pumpkin farm + sugar cane farm + chicken egg farm (crafter)",
                              ["minecraft:chicken"]),
    "minecraft:dried_kelp": ("kelp farm into a furnace array fuelled by dried kelp blocks", []),
    "minecraft:sweet_berries": ("berry bush under a dispenser of bone meal with a water flush", []),
    "minecraft:glow_berries": ("cave vines harvested by a piston/observer machine", []),
    "minecraft:cod": ("AFK fishing (a player online, idle): fishing loot, no fish mob needed", []),
    "minecraft:salmon": ("AFK fishing", []),
    "minecraft:tropical_fish": ("AFK fishing", []),
    "minecraft:pufferfish": ("AFK fishing", []),
    "minecraft:cooked_cod": ("AFK fishing into an auto-fed furnace", []),
    "minecraft:cooked_salmon": ("AFK fishing into an auto-fed furnace", []),
    "minecraft:cookie": ("wheat and cocoa farms, one craft", []),
    "minecraft:mushroom_stew": ("mushroom farm + bowls from a tree farm, one craft", []),
    "minecraft:cake": ("milk, sugar cane, egg and wheat farms, one craft", ["minecraft:cow", "minecraft:chicken"]),
    "minecraft:apple": ("oak leaves decaying in a tree farm", []),
    "minecraft:chicken": ("chicken egg farm with a lava cooker", ["minecraft:chicken"]),
    "minecraft:cooked_chicken": ("egg-fed chicken cooker", ["minecraft:chicken"]),
    "minecraft:iron_ingot": ("iron golem farm", ["minecraft:iron_golem"]),
    "minecraft:iron_nugget": ("iron golem farm", ["minecraft:iron_golem"]),
    "minecraft:string": ("spider spawner or dark-room mob farm", ["minecraft:spider"]),
    "minecraft:bone": ("skeleton spawner or dark-room mob farm", ["minecraft:skeleton"]),
    "minecraft:gunpowder": ("creeper farm", ["minecraft:creeper"]),
    "minecraft:spider_eye": ("spider spawner farm", ["minecraft:spider"]),
    "minecraft:feather": ("chicken farm", ["minecraft:chicken"]),
    "minecraft:slime_ball": ("slime chunk farm", ["minecraft:slime"]),
    "minecraft:ender_pearl": ("enderman farm", ["minecraft:enderman"]),
    "minecraft:amethyst_shard": ("a budding amethyst geode with an observer/piston harvester", []),
    "minecraft:nether_wart": ("nether wart under an observer/piston harvester", []),
    "minecraft:redstone": ("witch farm", ["minecraft:witch"]),
}
MOB_BLACKLIST = "mobsbegone-blacklist.json"


class AuditError(Exception):
    pass


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ SNBT reader
class _Snbt:
    """A reader for the SNBT the generators write (dicts, lists, quoted strings, plain scalars). Its own, so a shop is
    read the way the server reads the summon, not the way a generator meant it."""

    def __init__(self, s):
        self.s, self.i = s, 0

    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in " \t\r\n":
            self.i += 1

    def value(self):
        self.ws()
        c = self.s[self.i]
        if c == "{":
            return self.compound()
        if c == "[":
            return self.list_()
        if c in "\"'":
            return self.string()
        return self.scalar()

    def compound(self):
        self.i += 1
        out = {}
        self.ws()
        if self.s[self.i] == "}":
            self.i += 1
            return out
        while True:
            self.ws()
            if self.s[self.i] in "\"'":
                key = self.string()
            else:
                m = re.compile(r"[A-Za-z0-9_.+\-]+").match(self.s, self.i)
                if not m:
                    raise AuditError("SNBT: no key at %d: %r" % (self.i, self.s[self.i:self.i + 30]))
                key, self.i = m.group(0), m.end()
            self.ws()
            if self.s[self.i] != ":":
                raise AuditError("SNBT: ':' expected at %d" % self.i)
            self.i += 1
            out[key] = self.value()
            self.ws()
            c = self.s[self.i]
            self.i += 1
            if c == "}":
                return out
            if c != ",":
                raise AuditError("SNBT: ',' or '}' expected at %d" % (self.i - 1))

    def list_(self):
        self.i += 1
        out = []
        self.ws()
        if re.match(r"[BIL];", self.s[self.i:self.i + 2]):
            self.i += 2
        self.ws()
        if self.s[self.i] == "]":
            self.i += 1
            return out
        while True:
            out.append(self.value())
            self.ws()
            c = self.s[self.i]
            self.i += 1
            if c == "]":
                return out
            if c != ",":
                raise AuditError("SNBT: ',' or ']' expected at %d" % (self.i - 1))

    def string(self):
        q = self.s[self.i]
        self.i += 1
        buf = []
        while True:
            c = self.s[self.i]
            if c == "\\":
                buf.append(self.s[self.i + 1])
                self.i += 2
                continue
            self.i += 1
            if c == q:
                return "".join(buf)
            buf.append(c)

    def scalar(self):
        m = re.compile(r"[^,}\]\s]+").match(self.s, self.i)
        self.i = m.end()
        return m.group(0)


def parse_snbt(s):
    return _Snbt(s).value()


SUMMON = re.compile(r"^summon\s+(\S+)\s+\S+\s+\S+\s+\S+\s+(\{.*\})\s*$")


def summons(lines):
    """[(entity kind, nbt)] of every summon line."""
    out = []
    for ln in lines:
        m = SUMMON.match(ln.strip()) if isinstance(ln, str) else None
        if m:
            out.append((m.group(1), parse_snbt(m.group(2))))
    return out


def _int(x):
    return int(re.sub(r"[bslBSL]$", "", str(x)))


def shop_offers(nbt):
    """[(category, item id, count, price)] of an entity's CobbleMerchantShop."""
    out = []
    for cat in nbt.get("CobbleMerchantShop") or []:
        for off in cat.get("Offers") or []:
            item = off.get("Item") or {}
            out.append((str(cat.get("Category")), str(item.get("id")), _int(item.get("count", 1)),
                        _int(off.get("Price"))))
    return out


# ------------------------------------------------------------------------------------------------ the bank
def bank_entries_emitted(bank_mod=None):
    bank_mod = bank_mod or importlib.import_module("bank")
    return json.loads(bank_mod.text(bank_mod.load()))["bank"]


def bank_effective(entries):
    """{item: price} the Bank pays; on a repeated id the higher (the audit cannot tell which entry the jar matches
    first, and the higher one is the exploit)."""
    out = {}
    for e in entries:
        out[e["item"]] = max(out.get(e["item"], 0), int(e["price"]))
    return out


def line_of(path, item):
    """1-based line of the first `"item": "<id>"` in a JSON file, or None."""
    pat = '"item": "%s"' % item
    for n, ln in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if pat in ln:
            return n
    return None


# ------------------------------------------------------------------------------------------------ the sellers
class Sale:
    __slots__ = ("where", "town", "item", "unit", "ours", "sited")

    def __init__(self, where, town, item, unit, ours, sited=True):
        self.where, self.town, self.item, self.unit, self.ours, self.sited = where, town, item, unit, ours, sited


def market_sales(markets_mod=None):
    """Every sited counter's and stall's offers, read from the summon lines markets.build() emits."""
    markets_mod = markets_mod or importlib.import_module("markets")
    doc = markets_mod.load()
    files, _ = markets_mod.build(doc)
    town_of = {r["id"]: r["town"] for r in (doc.get("counters") or []) + (doc.get("stalls") or [])}
    tag = doc["stall_merchant"]["tag"]
    out, seen = [], 0
    for path, lines in files.items():
        if not isinstance(lines, list):
            continue
        for kind, nbt in summons(lines):
            seen += 1
            tags = [t for t in nbt.get("Tags") or [] if t.startswith(tag + "_") and t != tag + "_new"]
            rid = tags[0][len(tag) + 1:] if tags else "?"
            for cat, item, cnt, price in shop_offers(nbt):
                out.append(Sale("markets %s / %s" % (rid, cat), town_of.get(rid), item, price / cnt, True))
    if seen and not out:
        raise AuditError("markets.build() emitted %d summons and this reader found no offer in any" % seen)
    # unsited records: not in the world yet, carried as unsited sales (reported, never failed)
    for grp in ("counters", "stalls"):
        for rec in doc.get(grp) or []:
            if rec.get("status") != "sited":
                for it in rec.get("stock") or []:
                    out.append(Sale("markets %s (UNSITED) %s" % (grp[:-1], rec["id"]), rec.get("town"), it["item"],
                                    (int(it["price"]) // int(it.get("count") or 1)), True, sited=False))
    return out


def apricorn_sales():
    af = importlib.import_module("apricorn_farm")
    nbt = parse_snbt(importlib.import_module("traders").to_snbt(af.merchant_data(af.load())))
    return [Sale("apricorn farm / %s" % cat, "apricorn_farm", item, price / cnt, True)
            for cat, item, cnt, price in shop_offers(nbt)]


def default_shop_sales():
    p = OUR_SHOP if OUR_SHOP.is_file() else BASE_SHOP
    out = []
    for cat in read_json(p).get("defaultShop") or []:
        for name, offers in cat.items():
            for o in offers:
                out.append(Sale("defaultShop / %s" % name, None, o["item"], float(o["price"]), False))
    return out


def trader_sales(server_dir, traders_mod=None):
    """(sales, {trader id: set of offered ids}, {trader id: claimed tier}) from traders.town_functions' summons."""
    tr = traders_mod or importlib.import_module("traders")
    doc = read_json(DATA / "traders.json")
    tiers = tr.mart_tiers(doc, tr.load_towns())
    cache = {}
    entity = lambda t: cache.setdefault(t, tr.entity_of(server_dir, t))   # noqa: E731
    by_town = {}
    for r in doc["traders"]:
        by_town.setdefault(r["settlement"], []).append(r)
    out, offered = [], {}
    authored = {r["id"] for r in doc["traders"] if r.get("stock") == "stones"}
    card = (doc["stock_policy"].get("trainer_card") or {})
    for town, recs in sorted(by_town.items()):
        for _name, lines in tr.town_functions(town, recs, entity, doc["stock_policy"], tiers).items():
            for kind, nbt in summons(lines):
                rid = next((t[len(tr.TAG_ALL) + 1:] for t in nbt.get("Tags") or []
                            if t.startswith(tr.TAG_ALL + "_") and t != tr.TAG_NEW), "?")
                for cat, item, cnt, price in shop_offers(nbt):
                    offered.setdefault(rid, set()).add(item)
                    ours = rid in authored or (item == card.get("item") and rid == card.get("trader"))
                    out.append(Sale("trader %s / %s" % (rid, cat), town, item, price / cnt, ours))
    return out, offered, tiers


# ------------------------------------------------------------------------------------------------ the jars
class Jars:
    """Items, item tags and recipes read from the vanilla jar and a server's mods/ and datapacks/."""

    def __init__(self):
        self.items, self.tags, self.recipes = set(), {}, []

    def scan_zip(self, z, where, depth=0):
        for name in z.namelist():
            self.scan_entry(name, lambda n=name: z.read(n), where)
            if depth == 0 and name.startswith("META-INF/jars/") and name.endswith(".jar"):
                try:
                    with zipfile.ZipFile(BytesIO(z.read(name))) as inner:
                        self.scan_zip(inner, "%s!%s" % (where, name), depth + 1)
                except zipfile.BadZipFile:
                    pass

    def scan_dir(self, d, where):
        d = Path(d)
        for p in d.rglob("*"):
            if p.is_file():
                self.scan_entry(p.relative_to(d).as_posix(), p.read_bytes, where)

    def scan_entry(self, name, read, where):
        m = re.fullmatch(r"assets/([^/]+)/lang/en_us\.json", name)
        if m:
            try:
                lang = json.loads(read().decode("utf-8-sig"))
            except ValueError:
                return
            for k in lang:
                km = re.fullmatch(r"(?:item|block)\.([a-z0-9_.\-]+)\.([a-z0-9_./\-]+)", k)
                if km:
                    self.items.add("%s:%s" % km.groups())
            return
        m = re.fullmatch(r"assets/([^/]+)/models/item/(.+)\.json", name)
        if m:
            self.items.add("%s:%s" % m.groups())
            return
        m = re.fullmatch(r"data/([^/]+)/tags/items?/(.+)\.json", name)
        if m:
            try:
                vals = json.loads(read().decode("utf-8-sig")).get("values") or []
            except ValueError:
                return
            key = "%s:%s" % m.groups()
            for v in vals:
                v = v.get("id") if isinstance(v, dict) else v
                if isinstance(v, str):
                    self.tags.setdefault(key, set()).add(v)
            return
        m = re.fullmatch(r"data/([^/]+)/recipes?/(.+)\.json", name)
        if m:
            try:
                r = json.loads(read().decode("utf-8-sig"))
            except ValueError:
                return
            if isinstance(r, dict):
                self.recipes.append(("%s:%s" % m.groups(), r))

    def tag_items(self, tag, seen=None):
        seen = seen or set()
        if tag in seen:
            return set()
        seen.add(tag)
        out = set()
        for v in self.tags.get(tag, ()):
            out |= self.tag_items(v[1:], seen) if v.startswith("#") else {v}
        return out

    def ingredient(self, ing):
        """The set of item ids an ingredient accepts, or None when it is a shape this reader does not know."""
        if isinstance(ing, str):
            return self.tag_items(ing[1:]) if ing.startswith("#") else {ing}
        if isinstance(ing, list):
            out = set()
            for x in ing:
                got = self.ingredient(x)
                if got is None:
                    return None
                out |= got
            return out
        if isinstance(ing, dict):
            if "item" in ing:
                return {ing["item"]}
            if "tag" in ing:
                return self.tag_items(ing["tag"])
        return None

    def conversions(self):
        """[(recipe name, kind, [(accepted ids, count)], result id, result count)] of every recipe this reader can
        price: shaped and shapeless crafting, the four cooking kinds, stonecutting and smithing_transform."""
        out = []
        for name, r in self.recipes:
            t = str(r.get("type", "")).replace("minecraft:", "")
            res = r.get("result")
            if isinstance(res, str):
                rid, rcount = res, int(r.get("count", 1))
            elif isinstance(res, dict):
                rid, rcount = res.get("id") or res.get("item"), int(res.get("count", 1))
            else:
                continue
            if not isinstance(rid, str):
                continue
            ings = []
            if t == "crafting_shaped":
                key, pattern = r.get("key") or {}, r.get("pattern") or []
                counts = {}
                for row in pattern:
                    for ch in row:
                        if ch != " ":
                            counts[ch] = counts.get(ch, 0) + 1
                for ch, n in counts.items():
                    ings.append((self.ingredient(key.get(ch)), n))
            elif t == "crafting_shapeless":
                for ing in r.get("ingredients") or []:
                    ings.append((self.ingredient(ing), 1))
            elif t in ("smelting", "blasting", "smoking", "campfire_cooking", "stonecutting"):
                ings.append((self.ingredient(r.get("ingredient")), 1))
            elif t == "smithing_transform":
                for k in ("template", "base", "addition"):
                    ings.append((self.ingredient(r.get(k)), 1))
            else:
                continue
            if not ings or any(acc is None or not acc for acc, _ in ings):
                continue
            out.append((name, t, ings, rid, max(1, rcount)))
        return out


@lru_cache(maxsize=4)
def load_jars(server_dir, vanilla_jar):
    j = Jars()
    with zipfile.ZipFile(vanilla_jar) as z:
        j.scan_zip(z, Path(vanilla_jar).name)
    sd = Path(server_dir)
    for p in sorted((sd / "mods").glob("*.jar")):
        with zipfile.ZipFile(p) as z:
            j.scan_zip(z, p.name)
    for p in sorted((sd / "datapacks").glob("*")):
        if p.suffix == ".zip":
            try:
                with zipfile.ZipFile(p) as z:
                    j.scan_zip(z, p.name)
            except zipfile.BadZipFile:
                continue
        elif p.is_dir():
            j.scan_dir(p, p.name)
    return j


# ------------------------------------------------------------------------------------------------ arbitrage
def cheapest(sales, conversions, rounds=6):
    """{item: (unit cost, how)}: the least money that obtains one, by buying it or by a recipe whose every input is
    obtainable that way (fuel counted as free)."""
    best = {}
    for s in sales:
        if s.sited and (s.item not in best or s.unit < best[s.item][0]):
            best[s.item] = (s.unit, "buy at %s for $%g" % (s.where, s.unit))
    for _ in range(rounds):
        changed = False
        for name, kind, ings, rid, rcount in conversions:
            total, parts = 0.0, []
            for acc, n in ings:
                c = min(((best[i][0], i) for i in acc if i in best), default=None)
                if c is None:
                    break
                total += c[0] * n
                parts.append("%d x %s" % (n, c[1]))
            else:
                unit = total / rcount
                if rid not in best or unit < best[rid][0] - 1e-9:
                    best[rid] = (unit, "%s %s (%s -> %d)" % (kind, name, " + ".join(parts), rcount))
                    changed = True
        if not changed:
            break
    return best


def chain(best, item, depth=0):
    cost, how = best[item]
    text = "%s $%.2f: %s" % (item, cost, how)
    if depth < 3 and not how.startswith("buy at"):
        subs = re.findall(r"\d+ x ([a-z0-9_.\-]+:[a-z0-9_/.\-]+)", how)
        for s in subs:
            if s in best and s != item:
                text += " | " + chain(best, s, depth + 1)
    return text


def arbitrage(bank_prices, best):
    """(failures, reports): an item the Bank pays more for than it costs to obtain, or exactly that."""
    fails, reps = [], []
    for item, pay in sorted(bank_prices.items()):
        if item not in best:
            continue
        cost = best[item][0]
        if pay > cost + 1e-9:
            fails.append("ARBITRAGE %s: the Bank pays $%d, obtainable for $%.2f -- %s" % (item, pay, cost, chain(best, item)))
        elif abs(pay - cost) < 1e-9:
            reps.append("break-even %s: the Bank pays $%d, obtainable for exactly that -- %s" % (item, pay, best[item][1]))
    return fails, reps


def unsited_arbitrage(bank_prices, sales):
    return ["UNSITED %s sells %s at $%g, the Bank pays $%d: free money the day it is sited"
            % (s.where, s.item, s.unit, bank_prices[s.item])
            for s in sales if not s.sited and s.item in bank_prices and bank_prices[s.item] >= s.unit]


# ------------------------------------------------------------------------------------------------ tiers
def chapter_badges(progression):
    """{chapter id: badges held while playing it}: the gymN_cleared flags in the transitive unlocked_by chain."""
    ch = {c["id"]: c for c in progression["chapters"]}
    gyms = {f["id"] for f in progression["flags"] if re.fullmatch(r"gym\d+_cleared", f["id"])}
    unlocks = {}
    for c in progression["chapters"]:
        for f in c.get("unlocks") or []:
            unlocks[f] = c["id"]

    def held(cid, seen=()):
        out = set()
        for f in ch[cid].get("unlocked_by") or []:
            if f in gyms:
                out.add(f)
            if f in unlocks and unlocks[f] not in seen:
                out |= held(unlocks[f], seen + (cid,))
        return out
    return {cid: len(held(cid)) for cid in ch}


def _seg(px, pz, a, b):
    ax, az, bx, bz = a["x"], a["z"], b["x"], b["z"]
    dx, dz = bx - ax, bz - az
    ln = dx * dx + dz * dz
    t = 0.0 if ln == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / ln))
    return math.hypot(px - ax - t * dx, pz - az - t * dz)


def critical_routes(progression, routes_doc):
    """[(route id, badges held on it, from_town, to_town, polyline)] of every route a chapter names."""
    cb = chapter_badges(progression)
    out = []
    for r in routes_doc["routes"]:
        if r.get("chapter") in cb:
            out.append((r["id"], cb[r["chapter"]], r.get("from_town"), r.get("to_town"), r["corridor"]["polyline"]))
    return out


def independent_tier(settlement, pos, crit):
    """(tier, how, nearest by badge count {badges: distance}) for a Mart clerk at pos."""
    arriving = [b for _rid, b, _f, to, _pl in crit if to == settlement]
    starts = [b for _rid, b, fr, _to, _pl in crit if fr == settlement]
    near = {}
    for rid, b, _f, _t, pl in crit:
        d = min(_seg(pos["x"], pos["z"], pl[i], pl[i + 1]) for i in range(len(pl) - 1))
        near[b] = min(near.get(b, 1e18), d)
    if arriving:
        return min(arriving), "arrives on the chapter route ending here", near
    if starts and not arriving:
        return min(starts), "the critical path starts here", near
    d0 = min(near.values())
    b = min(k for k, d in near.items() if d - d0 <= 1.0)
    return b, "nearest critical route %.0f blocks" % d0, near


def tier_table(mart):
    """({item: badges}, {item: authored price or None}, [failures]) from the DATA's two tier tables:
    stock_policy.mart.tiers (ids; the price is the shopkeeper template's) and stock_policy.mart.training.tiers
    ({item, price}; the price is authored there). Read here, not through tools/traders.py."""
    tier, price, fails = {}, {}, []
    tables = [("mart.tiers", mart.get("tiers") or []),
              ("mart.training.tiers", (mart.get("training") or {}).get("tiers") or [])]
    for where, tiers in tables:
        for t in tiers:
            for o in t.get("items") or []:
                iid = o.get("item") if isinstance(o, dict) else o
                if iid in tier:
                    fails.append("TIER %s is listed twice across the tier tables (again in %s): one line, one tier"
                                 % (iid, where))
                tier[iid] = int(t["badges"])
                price[iid] = int(o["price"]) if isinstance(o, dict) and o.get("price") is not None else None
    return tier, price, fails


def tier_checks(trader_doc, claimed, offered, progression, routes_doc, towns_doc):
    """(failures, reports)."""
    fails, reps = [], []
    policy = trader_doc["stock_policy"]
    mart = policy["mart"]
    item_tier, _authored, f = tier_table(mart)
    fails += f
    basics = set(mart.get("items") or [])
    card = policy.get("trainer_card") or {}
    crit = critical_routes(progression, routes_doc)
    towns = {t["id"]: t for t in towns_doc["towns"]}
    for r in trader_doc["traders"]:
        if r.get("stock") != "mart":
            continue
        rid = r["id"]
        mine, how, near = independent_tier(r["settlement"], r["position"], crit)
        theirs = claimed.get(rid)
        if theirs is None:
            fails.append("TIER %s: no claimed tier" % rid)
            continue
        if theirs > mine:
            fails.append("TIER LEAK %s (%s): claimed tier %d, independent %d (%s)" % (rid, r["settlement"], theirs, mine, how))
        elif theirs < mine:
            reps.append("tier differs %s (%s): claimed %d, independent %d (%s): the shelf is behind the road, not ahead"
                        % (rid, r["settlement"], theirs, mine, how))
        if how.startswith("nearest") and len(near) > 1:
            d = sorted(near.items(), key=lambda kv: kv[1])
            reps.append("tier margin %s: %s" % (rid, ", ".join("%d badges at %.0f" % (b, x) for b, x in d[:3])))
        for item in sorted(offered.get(rid, ())):
            if item in basics or (item == card.get("item") and rid == card.get("trader")):
                continue
            if item not in item_tier:
                fails.append("TIER %s sells %s, which is neither a Mart basic nor a tier line" % (rid, item))
            elif item_tier[item] > theirs:
                fails.append("TIER LEAK %s sells %s (tier %d) at claimed tier %d" % (rid, item, item_tier[item], theirs))
            elif item_tier[item] > mine:
                fails.append("TIER LEAK %s sells %s (tier %d) above the independent tier %d" % (rid, item, item_tier[item], mine))
        missing = {i for i, b in item_tier.items() if b <= theirs} - offered.get(rid, set())
        if offered.get(rid) is not None and missing:
            reps.append("short shelf %s: claimed tier %d but %s not offered" % (rid, theirs, ", ".join(sorted(missing))))
        town = towns.get(r["settlement"]) or {}
        if not town.get("critical_path") and not town.get("gates") and theirs > 0:
            early = sorted((b, x) for b, x in near.items() if b < theirs)
            above = sorted(i for i in offered.get(rid, ()) if item_tier.get(i, 0) > 0)
            reps.append("reachable early %s (%s): ungated (data/towns.json gates %r, access %r), tier %d shelf %s; "
                        "distance from each route held with fewer badges: %s"
                        % (rid, r["settlement"], town.get("gates"), town.get("access"), theirs,
                           ", ".join(i.split(":")[1] for i in above) or "-",
                           ", ".join("%d badges %.0f" % bx for bx in early) or "-"))
    return fails, reps


# ------------------------------------------------------------------------------------------------ Mart prices
def _is_ball(item):
    return item.split(":")[-1].endswith("_ball")


def mart_price_checks(trader_doc, markets_doc, shelf):
    """(failures, reports) for the PRICES on the emitted Mart shelves. `shelf` is {clerk id: {item: unit price}} read
    from the emitted summons. The rule is data/traders.json stock_policy.mart.early_reach_pricing.criterion, applied
    here with this file's own arithmetic:
      - the normal price of a training line is the one stock_policy.mart.training authors; of a template line, the one
        every clerk NOT listed in early_reach_pricing.traders charges (they must agree: one item, one normal price);
      - an ordinary clerk charges the normal price; no clerk charges less;
      - a listed clerk reachable with R badges, for a tier line of badges T, d = T - R: d <= 0 the normal price;
        1 <= d <= convenience_within at least normal x convenience_markup rounded up to round_to (more is REPORTED);
        d > convenience_within more than data/markets.json income_basis.cumulative_by_badge[T] (the most a player with
        T-1 badges has, the criterion's own reading);
      - no ball in the convenience band: the band's stated premise (convenience_within_why) is that nothing in it
        changes what a player can catch, so a ball there is a FAILURE of the premise, not of the arithmetic."""
    fails, reps = [], []
    mart = trader_doc["stock_policy"]["mart"]
    tier_of, authored, _f = tier_table(mart)
    basics = set(mart.get("items") or [])
    erp = mart.get("early_reach_pricing") or {}
    early = {rid: int(v["reachable_from_badges"]) for rid, v in (erp.get("traders") or {}).items()}
    within = int(erp.get("convenience_within") or 0)
    markup = float(erp.get("convenience_markup") or 1)
    step = int(erp.get("round_to") or 1)
    income = {int(k): float(v) for k, v in ((markets_doc.get("income_basis") or {}).get("cumulative_by_badge")
                                            or {}).items()}
    normal = {i: p for i, p in authored.items() if p is not None}
    seen = {}
    for rid, items in shelf.items():
        if rid in early:
            continue
        for i, p in items.items():
            seen.setdefault(i, set()).add(p)
    for i, ps in sorted(seen.items()):
        if len(ps) > 1:
            fails.append("PRICE %s sells at %s across the ordinary Marts: one item, one normal price"
                         % (i, ", ".join("$%g" % p for p in sorted(ps))))
        if i in normal and ps != {normal[i]}:
            fails.append("PRICE training line %s sells at %s at the ordinary Marts; the data authors $%d"
                         % (i, ", ".join("$%g" % p for p in sorted(ps)), normal[i]))
        normal.setdefault(i, min(ps))
    for rid, items in sorted(shelf.items()):
        for i, p in sorted(items.items()):
            n = normal.get(i)
            if n is not None and p < n - 1e-9:
                fails.append("PRICE UNDER %s sells %s at $%g, below its normal $%g" % (rid, i, p, n))
    for rid, reach in sorted(early.items()):
        if rid not in shelf:
            fails.append("PRICE early-reach clerk %s has no emitted shelf" % rid)
            continue
        bands = {"normal": 0, "convenience": 0, "gate": 0}
        for i, p in sorted(shelf[rid].items()):
            if i in basics or i not in tier_of:
                continue
            t, n = tier_of[i], normal.get(i)
            d = t - reach
            bands["normal" if d <= 0 else "convenience" if d <= within else "gate"] += 1
            if n is None:
                reps.append("price %s %s: no normal price to compare (no ordinary clerk sells it)" % (rid, i))
                if d <= within:
                    continue
            if d <= 0:
                if abs(p - n) > 1e-9:
                    reps.append("price %s %s at $%g, tier %d within reach %d: normal is $%g" % (rid, i, p, t, reach, n))
            elif d <= within:
                floor = math.ceil(n * markup / step - 1e-9) * step
                if p < floor - 1e-9:
                    fails.append("PRICE CONVENIENCE %s sells %s (tier %d, reach %d) at $%g, under normal $%g x %g = $%d"
                                 % (rid, i, t, reach, p, n, markup, floor))
                elif p > floor + 1e-9:
                    reps.append("price %s %s (tier %d, reach %d) at $%g, above the convenience price $%d"
                                % (rid, i, t, reach, p, floor))
                if _is_ball(i):
                    fails.append("CONVENIENCE BALL %s sells %s (tier %d) to a player with %d badges at $%g: the band's "
                                 "premise is that nothing in it changes what a player can catch" % (rid, i, t, reach, p))
            else:
                cap = income.get(t)
                if cap is None:
                    fails.append("PRICE GATE %s %s: tier %d has no income_basis.cumulative_by_badge entry" % (rid, i, t))
                elif p <= cap:
                    fails.append("PRICE GATE %s sells %s (tier %d, reach %d) at $%g: a player with %d badges can hold "
                                 "$%g (income_basis, RELAYED)" % (rid, i, t, reach, p, t - 1, cap))
        reps.append("price bands %s (reach %d): %d normal, %d convenience, %d income-gated tier line(s) checked"
                    % (rid, reach, bands["normal"], bands["convenience"], bands["gate"]))
    return fails, reps


def reward_ahead_report(markets_doc, progression, towns_doc):
    """REPORT lines: a counter line selling a gym leader's first-win reward (data/progression.json
    upstream_neutralised.first_win_rewards, flag gymN_cleared) at a counter whose own badge is below N, or in a town
    data/towns.json leaves ungated off the critical path. No threshold: the counters have no early-reach band in the data
    (early_reach_pricing lists Mart clerks only), so this names the line, the gap and the income at the counter's badge
    for the owner rather than inventing a gate."""
    reps = []
    fwr = ((progression.get("upstream_neutralised") or {}).get("first_win_rewards") or {}).get("trainers") or {}
    leader_of = {}
    for tid, t in fwr.items():
        m = re.fullmatch(r"gym(\d+)_cleared", str(t.get("flag")))
        if not m:
            continue
        for i in list(t.get("items") or []) + list(t.get("one_of") or []):
            leader_of.setdefault(i, (int(m.group(1)), tid))
    income = (markets_doc.get("income_basis") or {}).get("cumulative_by_badge") or {}
    towns = {t["id"]: t for t in towns_doc.get("towns") or []}
    for c in markets_doc.get("counters") or []:
        b = c.get("badge")
        town = towns.get(c.get("town")) or {}
        open_early = not town.get("critical_path") and not town.get("gates")
        for s in c.get("stock") or []:
            if s["item"] not in leader_of:
                continue
            n, tid = leader_of[s["item"]]
            if (isinstance(b, int) and n > b) or open_early:
                reps.append("leader reward on sale %s/%s %s at $%s: %s's gym-%d reward; counter badge %s%s; income "
                            "through badge %s is $%s (RELAYED)"
                            % (c.get("town"), c["id"], s["item"], s["price"], tid, n, b,
                               ", town ungated off the critical path (reachable before any badge)" if open_early else "",
                               b, income.get(str(b), "?")))
    return reps


# ------------------------------------------------------------------------------------------------ the vitamin rule
# docs/mechanics/EV_IV_TRAINING.md:33 names the six vitamins; its section 4.2 (E2): nothing -- seller, recipe chain or
# barter -- may yield a vitamin at or under the Bank's vitamin price, or a vitamin is a money printer. The threshold is
# the Bank's own effective price for each, read from the emitted bank, not a constant.
VITAMINS = ("cobblemon:hp_up", "cobblemon:protein", "cobblemon:iron", "cobblemon:calcium", "cobblemon:zinc",
            "cobblemon:carbos")


def vitamin_checks(best, bank_prices):
    fails, reps = [], []
    for v in VITAMINS:
        pay = bank_prices.get(v)
        if pay is None:
            reps.append("vitamin %s: the Bank does not buy it, so E2 has no threshold" % v)
            continue
        if v in best and best[v][0] <= pay + 1e-9:
            fails.append("VITAMIN %s obtainable for $%.2f, at or under the Bank's $%d (EV_IV_TRAINING.md 4.2 E2) -- %s"
                         % (v, best[v][0], pay, chain(best, v)))
    return fails, reps


# ------------------------------------------------------------------------------------------------ the exchange
def raw_decomposition(item, conversions, mined, depth=0):
    """{raw mined item: count} for one `item`, through the jars' recipes, choosing the recipe whose inputs are all
    mined (directly or in turn); None when there is none."""
    if item in mined:
        return {item: 1.0}
    if depth > 3:
        return None
    for name, kind, ings, rid, rcount in conversions:
        if rid != item:
            continue
        total = {}
        for acc, n in ings:
            sub = None
            for a in sorted(acc):
                sub = raw_decomposition(a, conversions, mined, depth + 1)
                if sub:
                    break
            if not sub:
                break
            for k, v in sub.items():
                total[k] = total.get(k, 0) + v * n / rcount
        else:
            return total
    return None


def exchange_report(markets_doc, sales, bank_prices, bank_doc, conversions, progression, routes_doc):
    """REPORT lines, one per exchange_for line."""
    reps = []
    income = markets_doc["income_basis"]["leg_by_badge"]
    em = bank_doc.get("effort_model") or {}
    leg_hours = em.get("max_leg_hours")
    rates = {b["item"]: (b.get("rate_per_hour") or 0, b.get("rate_per_hour_upper") or b.get("rate_per_hour") or 0)
             for b in bank_doc.get("buys") or []}
    mined = {i for i, (r, _u) in rates.items() if r}
    crit = critical_routes(progression, routes_doc)
    emitted = {}
    for s in sales:
        if s.sited and s.where.startswith("markets "):
            emitted.setdefault((s.where.split(" ")[1], s.item), s.unit)
    for c in markets_doc.get("counters") or []:
        for ln in c.get("stock") or []:
            ex = ln.get("exchange_for")
            if not ex:
                continue
            mat, n = ex["item"], int(ex["count"])
            price = emitted.get((c["id"], ln["item"]))
            pay = bank_prices.get(mat)
            head = "exchange %s/%s %s for %d x %s:" % (c["town"], c["id"], ln["item"], n, mat)
            if price is None:
                reps.append("%s NOT EMITTED (counter status %s): nothing to compare" % (head, c.get("status")))
                continue
            if pay is None:
                reps.append("%s the Bank does not buy %s: the material earns nothing" % (head, mat))
                continue
            earned = n * pay
            pos = {"x": c["at"][0], "z": c["at"][2]}
            tier, how, _near = independent_tier(c["town"], pos, crit)
            leg = income.get(str(tier + 1))
            parts = ["offer $%g, material earns %d x $%d = $%d (offer/earned %.3f)" % (price, n, pay, earned, price / earned)]
            if leg:
                parts.append("independent tier %d (%s): reward = %.2f of leg %d's income $%d (RELAYED)"
                             % (tier, how, price / leg, tier + 1, leg))
            dec = raw_decomposition(mat, conversions, mined)
            hours = None
            if dec and leg and leg_hours:
                hours = sum(v * n / rates[k][0] for k, v in dec.items())
                hours_up = sum(v * n / rates[k][1] for k, v in dec.items())
                fight = price / (leg / float(leg_hours))
                flag = " SHORTCUT: gathering is faster than battling here" if hours < fight else ""
                parts.append("gathering %.1f h (upper %.1f h) of %s at ASSUMED rates vs battling %.1f h at $%d per %s h "
                             "(ASSUMED max_leg_hours): ratio %.2f (upper %.2f)%s"
                             % (hours, hours_up, " + ".join("%g %s" % (v * n, k) for k, v in sorted(dec.items())),
                                fight, leg, leg_hours, hours / fight, hours_up / fight, flag))
            else:
                parts.append("hours: NOT DERIVABLE (%s)" % ("no recipe path from a mined item with a rate" if not dec
                                                             else "no leg income or max_leg_hours"))
            claimed = c.get("badge")
            cleg = income.get(str(claimed + 1)) if isinstance(claimed, int) else None
            if cleg and claimed != tier:
                parts.append("at the counter's own badge %d instead: %.2f of leg %d's $%d%s"
                             % (claimed, price / cleg, claimed + 1, cleg,
                                (", gathering/battling ratio %.2f" % (hours / (price / (cleg / float(leg_hours)))))
                                if hours is not None else ""))
            cheaper = sorted({"%s $%g" % (s.where, s.unit) for s in sales
                              if s.sited and s.item == ln["item"] and s.unit < price})
            if cheaper:
                parts.append("SOLD CHEAPER elsewhere: %s" % ", ".join(cheaper))
            if ln["item"] in bank_prices:
                parts.append("BOUGHT BACK by the Bank at $%d" % bank_prices[ln["item"]])
            reps.append("%s %s" % (head, "; ".join(parts)))
    return reps


# ------------------------------------------------------------------------------------------------ ids and AFK
def id_checks(items_known, bank_entries, bank_doc, sales, markets_doc):
    fails, reps = [], []
    ours_bank = {b["item"] for b in bank_doc.get("buys") or []}
    for e in bank_entries:
        if e["item"] not in items_known:
            (fails if e["item"] in ours_bank else reps).append(
                "MISSING ID %s: bought by the Bank (%s)" % (e["item"], "data/bank.json buys" if e["item"] in ours_bank
                                                          else "the base list"))
    for s in sales:
        if s.item not in items_known:
            (fails if s.ours else reps).append("MISSING ID %s: sold at %s" % (s.item, s.where))
    for c in markets_doc.get("counters") or []:
        for ln in c.get("stock") or []:
            ex = ln.get("exchange_for")
            if ex and ex["item"] not in items_known:
                fails.append("MISSING ID %s: the exchange material of %s/%s" % (ex["item"], c["id"], ln["id"]))
    return sorted(set(fails)), sorted(set(reps))


def mob_blacklist(server_dir=None):
    """(set of blacklisted entity ids, the file read): the server's config if given, else the base pack's."""
    for p in ([Path(server_dir) / "config" / MOB_BLACKLIST] if server_dir else []) + \
             [ROOT / "base-pack" / "cobbleverse" / "config" / MOB_BLACKLIST]:
        if p.is_file():
            return set(read_json(p)), p
    return set(), None


def afk_report(bank_prices, bank_doc, server_dir=None):
    reps = []
    ours = {b["item"]: b for b in bank_doc.get("buys") or []}
    base = {e["item"]: int(e["price"]) for e in read_json(BASE_BANK)["bank"]}
    black, black_src = mob_blacklist(server_dir)
    for item, (how, mobs) in sorted(AFK_FARMABLE.items()):
        if item not in bank_prices:
            continue
        blocked = [m for m in mobs if m in black]
        if blocked:
            how += " [BLOCKED unless spawned otherwise: %s blacklisted in %s]" % (", ".join(blocked), black_src.name)
        elif mobs:
            how += " [needs %s, not blacklisted]" % ", ".join(mobs)
        if item in ours:
            src = "data/bank.json:%s" % line_of(DATA / "bank.json", item)
        else:
            src = "base-pack/cobbleverse/config/cobbledollars/bank.json:%s" % line_of(BASE_BANK, item)
        over = ("overridden by data/bank.json" if item in ours and item in base else
                "added by data/bank.json" if item in ours else "NOT overridden (base price stands)")
        reps.append("afk %s $%d (%s) -- %s; %s" % (item, bank_prices[item], src, how, over))
    return reps


# ------------------------------------------------------------------------------------------------ barter
MONEY = "$"
BARTER_ROUNDS = 16
# vanilla 1.21.1 MerchantOffer: the codec's keys and defaults, read from the client jar's bytecode (class dbu, its
# RecordCodecBuilder: uses 0, maxUses 4, rewardExp true, specialPrice 0, demand 0, priceMultiplier 0.0f, xp 1)
OFFER_DEFAULTS = {"uses": 0, "maxUses": 4, "rewardExp": True, "specialPrice": 0, "demand": 0, "priceMultiplier": 0.0,
                  "xp": 1}
FIXED_FIELDS = tuple(OFFER_DEFAULTS)


class Barter:
    """One item-for-item edge. `pays` is the worst case for the player's counterparty: cost A at 1, cost B as authored;
    `authored` the counts as written."""
    __slots__ = ("id", "group", "pays", "authored", "gets", "fields", "experiment")

    def __init__(self, oid, group, pays, authored, gets, fields=None, experiment=False):
        self.id, self.group, self.pays, self.authored, self.gets = oid, group, pays, authored, gets
        self.fields, self.experiment = fields or {}, experiment

    def conversion(self):
        return ("barter:%s" % self.id, "barter(%s)" % self.group, [({i}, n) for i, n in self.pays], self.gets[0],
                self.gets[1])


def _scalar(v):
    """An SNBT scalar the reader left as text -> int, float or bool."""
    s = str(v)
    if s in ("true", "false"):
        return s == "true"
    m = re.fullmatch(r"(-?\d+)([bBsSlL]?)", s)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"(-?\d*\.?\d+(?:[eE]-?\d+)?)([fFdD]?)", s)
    if m:
        return float(m.group(1))
    return s


def _pays(buy, buy_b):
    """Worst-case inputs: cost A clamped to 1, cost B as authored; one entry per item."""
    out = {}
    if buy:
        out[buy[0]] = out.get(buy[0], 0) + 1
    if buy_b:
        out[buy_b[0]] = out.get(buy_b[0], 0) + buy_b[1]
    return sorted(out.items())


def _cost_of(c):
    return (str(c["id"]), int(_scalar(c.get("count", 1)))) if c else None


def barter_data(doc):
    """[Barter] of every offer data/direct_trades.json authors. group "placed" for the experiment offers and any line
    whose approved is true OR whose status is "approved" (either is enough to count it as live); "proposal" for the
    rest. The expected fixed fields are the data's fixed_trade with the offer's own overrides."""
    out = []
    fixed = doc.get("fixed_trade") or {}
    groups = [("placed", o, True) for o in doc.get("experiment_offers") or []]
    for ln in doc.get("lines") or []:
        live = ln.get("approved") is True or ln.get("status") == "approved"
        groups.append(("placed" if live else "proposal", ln, False))
    for group, o, exp in groups:
        buy, buy_b, sell = _cost_of(o.get("buy")), _cost_of(o.get("buyB")), _cost_of(o.get("sell"))
        fields = {k: fixed.get(k) for k in FIXED_FIELDS}
        fields.update({k: v for k, v in (o.get("overrides") or {}).items()})
        out.append(Barter(o.get("id"), group, _pays(buy, buy_b), (buy, buy_b), sell, fields, exp))
    return out


class _FlatGround:
    """A level stand-in for tools/ground.py: the barterer's offers do not depend on the ground."""

    class _Box:
        def min(self):
            return 100

        def max(self):
            return 100

    def __call__(self, x, z):
        return 100

    def box(self, *_a):
        return self._Box()


SUMMON_AT = re.compile(r"^summon\s+(\S+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s")


class Emitted(tuple):
    """(kind, [recipe dict], tags, (x, y, z) or None, function path) of one summon. A tuple, so (kind, recipes) still
    unpacks from its first two fields."""
    __slots__ = ()

    def __new__(cls, kind, recipes, tags=(), pos=None, path=None):
        return tuple.__new__(cls, (kind, recipes, tuple(tags), pos, path))


def barter_emitted(dt_mod=None, doc=None, files=None):
    """[Emitted] of every summon in the functions tools/direct_trades.py emits, read by this file."""
    if files is None:
        dt_mod = dt_mod or importlib.import_module("direct_trades")
        doc = doc if doc is not None else read_json(DIRECT_TRADES)
        files, _res = dt_mod.files(doc, _FlatGround())
    out = []
    for path, text in sorted(files.items()):
        if not path.endswith(".mcfunction"):
            continue
        for line in text.splitlines():
            line = line.strip()
            got = summons([line])
            if not got:
                continue
            kind, nbt = got[0]
            m = SUMMON_AT.match(line)
            pos = tuple(float(m.group(k)) for k in (2, 3, 4)) if m else None
            out.append(Emitted(kind, list(((nbt.get("Offers") or {}).get("Recipes")) or []),
                               [str(t) for t in nbt.get("Tags") or []], pos, path))
    return out


def declared_barterers(doc):
    """[(key, tag, site x, site z, offer ids)] of the villagers data/direct_trades.json declares, read from the data's
    own pairing: `barterer` stands at `site` and carries the experiment offers (site.role: "experiment ... carrying the
    experiment offers only"); `counter_barterer` stands at `counter_site` and carries every approved line
    (counter_site.role: "production ... carrying every approved line"). Empty when the data declares neither, in which
    case one villager carrying every placed offer is expected (the shape before 2026-10-08)."""
    out = []
    live = [ln.get("id") for ln in doc.get("lines") or []
            if ln.get("approved") is True or ln.get("status") == "approved"]
    for key, site_key, ids in (("barterer", "site", [o.get("id") for o in doc.get("experiment_offers") or []]),
                               ("counter_barterer", "counter_site", live)):
        b, s = doc.get(key), doc.get(site_key)
        if isinstance(b, dict) and b.get("tag") and isinstance(s, dict):
            out.append((key, b["tag"], int(s["x"]), int(s["z"]), ids))
    return out


def emitted_checks(data_edges, emitted, doc=None):
    """(failures, [Barter] of the placed group as emitted): every emitted recipe must be a placed data offer with every
    fixed field written and equal to the data's; with declared barterers, each declared villager is summoned exactly
    once, at its site's block, carrying exactly its own offers."""
    fails = []
    placed = [b for b in data_edges if b.group == "placed"]
    by_key = {}
    for b in placed:
        by_key.setdefault((b.authored, b.gets), []).append(b)
    villagers = [e for e in emitted if e[0] == "minecraft:villager"]
    declared = declared_barterers(doc or {})
    if not declared:
        if len(villagers) != 1:
            fails.append("BARTER EMITTED %d villager summons, not 1" % len(villagers))
    else:
        if len(villagers) != len(declared):
            fails.append("BARTER EMITTED %d villager summons; the data declares %d barterer(s) (%s)"
                         % (len(villagers), len(declared), ", ".join(d[0] for d in declared)))
        tags = {d[1] for d in declared}
        for e in villagers:
            if not tags & set(e[2]):
                fails.append("BARTER EMITTED a villager in %s carrying no declared barterer's tag (%s)"
                             % (e[4], ", ".join(e[2]) or "no tags"))
        for key, tag, sx, sz, ids in declared:
            mine = [e for e in villagers if tag in e[2]]
            if len(mine) != 1:
                fails.append("BARTER EMITTED %d villager(s) tagged %s (%s), not 1" % (len(mine), tag, key))
                continue
            e = mine[0]
            if e[3] is None or (math.floor(e[3][0]), math.floor(e[3][2])) != (sx, sz):
                fails.append("BARTER EMITTED %s summoned at %s, not on its site's block (%d, %d)" % (key, e[3], sx, sz))
            want = {}
            for b in placed:
                if b.id in ids:
                    want[(b.authored, b.gets)] = want.get((b.authored, b.gets), 0) + 1
            got = {}
            for r in e[1]:
                k = ((_cost_of(r.get("buy")), _cost_of(r.get("buyB"))), _cost_of(r.get("sell")))
                got[k] = got.get(k, 0) + 1
            if got != want:
                fails.append("BARTER EMITTED %s carries %d offer(s) that are not its own and lacks %d of its own "
                             "(the data puts %s on it)" % (key, sum(max(0, n - want.get(k, 0)) for k, n in got.items()),
                                                           sum(max(0, n - got.get(k, 0)) for k, n in want.items()),
                                                           ", ".join(ids) or "nothing"))
    out, seen = [], set()
    for e in villagers:
        for r in e[1]:
            buy, buy_b, sell = _cost_of(r.get("buy")), _cost_of(r.get("buyB")), _cost_of(r.get("sell"))
            match = by_key.get(((buy, buy_b), sell)) or []
            if not match:
                fails.append("BARTER EMITTED an offer no placed data offer authors: %s + %s -> %s"
                             % (buy, buy_b, sell))
                edge = Barter("emitted:%s" % (sell[0] if sell else "?"), "placed", _pays(buy, buy_b), (buy, buy_b),
                              sell)
            else:
                edge = match[0]
                seen.add(edge.id)
            for k in FIXED_FIELDS:
                if k not in r:
                    fails.append("BARTER EMITTED %s omits %s: the codec default %r applies, not the data's %r"
                                 % (edge.id, k, OFFER_DEFAULTS[k], edge.fields.get(k)))
                    continue
                got, want = _scalar(r[k]), edge.fields.get(k)
                if k == "rewardExp":
                    got = bool(got) if not isinstance(got, str) else got
                    want = bool(want)
                if isinstance(got, str) or want is None or abs(float(got) - float(want)) > 1e-9:
                    fails.append("BARTER EMITTED %s writes %s=%r, the data says %r" % (edge.id, k, r[k], want))
            out.append(Barter(edge.id, "placed", _pays(buy, buy_b), (buy, buy_b), sell, edge.fields, edge.experiment))
    for b in placed:
        if b.id not in seen:
            fails.append("BARTER NOT EMITTED %s: placed in the data, absent from the villager" % b.id)
    return fails, out


def unit_costs(seed, conversions, sales, bank_prices, rounds=BARTER_ROUNDS):
    """{item: (cost in units of `seed`, how)} with the seed costing 1 and money the item '$': the least of the seed
    that obtains each item through the Bank (item -> $), the sited sellers ($ -> item) and the conversions (recipes and
    barter). A seed that comes back costing less than 1 is a gain: a cycle that ends with more than it started."""
    inf = float("inf")
    best = {seed: (1.0, "start with one %s" % seed)}
    sited = [s for s in sales if s.sited]
    for _ in range(rounds):
        changed = False
        for item, pay in bank_prices.items():
            if item in best and pay > 0 and item != MONEY:
                c = best[item][0] / pay
                if c < best.get(MONEY, (inf,))[0] * (1 - 1e-12):
                    best[MONEY] = (c, "sell %s to the Bank for $%d" % (item, pay))
                    changed = True
        if MONEY in best:
            m = best[MONEY][0]
            for s in sited:
                c = s.unit * m
                if c < best.get(s.item, (inf,))[0] * (1 - 1e-12):
                    best[s.item] = (c, "buy at %s for $%g" % (s.where, s.unit))
                    changed = True
        for name, kind, ings, rid, rcount in conversions:
            total, parts = 0.0, []
            for acc, n in ings:
                c = min(((best[i][0], i) for i in acc if i in best), default=None)
                if c is None:
                    break
                total += c[0] * n
                parts.append("%d x %s" % (n, c[1]))
            else:
                unit = total / rcount
                if unit < best.get(rid, (inf,))[0] * (1 - 1e-12):
                    best[rid] = (unit, "%s %s (%s -> %d)" % (kind, name, " + ".join(parts), rcount))
                    changed = True
        if best[seed][0] < 1 - 1e-9 or not changed:
            break
    return best


def gains(seeds, conversions, sales, bank_prices):
    """{seed: (cost of one seed in seeds, how)} for every seed obtainable for less than one of itself."""
    out = {}
    for s in sorted(seeds):
        best = unit_costs(s, conversions, sales, bank_prices)
        if best[s][0] < 1 - 1e-9:
            out[s] = best[s]
    return out


def barter_checks(sales, conversions, bank_prices, best, doc=None, dt_mod=None):
    """(failures, reports, notes) for the barter edges."""
    fails, reps, notes = [], [], []
    if doc is None:
        if not DIRECT_TRADES.is_file():
            return fails, reps, ["NOT READ: data/direct_trades.json is absent; no barter edge audited"]
        doc = read_json(DIRECT_TRADES)
    data_edges = barter_data(doc)
    dt_mod = dt_mod or importlib.import_module("direct_trades")
    try:
        files, _res = dt_mod.files(doc, _FlatGround())
        emitted = barter_emitted(files=files)
    except Exception as exc:                       # the generator refusing its data is itself the finding
        fails.append("BARTER the generator emitted nothing: %s" % str(exc).splitlines()[0][:200])
        files, emitted = None, []
    f, placed = emitted_checks(data_edges, emitted, doc)
    fails += f
    if files is not None and hasattr(dt_mod, "steps"):
        fails += forceload_checks(files, dt_mod.steps(doc))
    elif files is not None:
        notes.append("NOT CHECKED: forceload cover (the barter generator given has no step list)")
    proposal = [b for b in data_edges if b.group == "proposal"]
    seeds = {MONEY} | {i for b in placed + proposal for i, _n in b.pays} | {b.gets[0] for b in placed + proposal}
    base = gains(seeds, conversions, sales, bank_prices)
    with_placed = gains(seeds, conversions + [b.conversion() for b in placed], sales, bank_prices)
    with_all = gains(seeds, conversions + [b.conversion() for b in placed + proposal], sales, bank_prices)
    for s, (c, how) in sorted(base.items()):
        reps.append("barter pre-existing gain %s: one costs %.4f of itself without any barter edge -- %s" % (s, c, how))
    for s, (c, how) in sorted(with_placed.items()):
        if s not in base:
            fails.append("BARTER LOOP (placed) %s: one costs %.4f of itself through the emitted villager -- %s"
                         % (s, c, how))
    for s, (c, how) in sorted(with_all.items()):
        if s not in base and s not in with_placed:
            fails.append("BARTER LOOP (proposal) %s: one costs %.4f of itself once the proposed lines go live -- %s"
                         % (s, c, how))
    notes.append("barter: %d placed offer(s) read from the emitted villager, %d proposal line(s) from the data; %d "
                 "seed(s) tested for a gain over %d conversions" % (len(placed), len(proposal), len(seeds),
                                                                     len(conversions)))
    afk = set(AFK_FARMABLE)
    recipes_from = {}
    for name, kind, ings, rid, rcount in conversions:
        for acc, _n in ings:
            for i in acc:
                recipes_from.setdefault(i, set()).add((rid, name))
    made_by = {}
    for name, kind, ings, rid, rcount in conversions:
        made_by.setdefault(rid, []).append(name)
    for b in placed + proposal:
        head = "barter %s (%s): %s -> %d x %s" % (b.id, b.group, " + ".join("%d x %s" % (n, i) for i, n in b.pays),
                                                 b.gets[1], b.gets[0])
        parts = []
        cost = [(i, n, best.get(i)) for i, n in b.pays]
        unbought = [i for i, _n, c in cost if c is None]
        if unbought:
            parts.append("cannot be bought: %s" % ", ".join(unbought))
        else:
            parts.append("inputs cost $%.2f to buy" % sum(n * c[0] for _i, n, c in cost))
            reps.append("barter rule B1 (%s) %s: every input can be bought (%s)"
                        % (b.group, b.id, ", ".join("%s $%.2f" % (i, c[0]) for i, _n, c in cost)))
        banked = [(i, n, bank_prices[i]) for i, n in b.pays if i in bank_prices]
        if banked:
            parts.append("the Bank would pay $%d for the inputs it buys (%s)"
                         % (sum(n * p for _i, n, p in banked), ", ".join("%d x %s at $%d" % (n, i, p)
                                                                        for i, n, p in banked)))
        out_item = b.gets[0]
        if out_item in best:
            parts.append("the output is otherwise obtainable for $%.2f (%s)" % (best[out_item][0], best[out_item][1]))
        if made_by.get(out_item):
            parts.append("the output has a recipe: %s" % ", ".join(sorted(made_by[out_item])[:3]))
        reps.append("%s; %s" % (head, "; ".join(parts)))
        for i, _n in b.pays:
            if i in afk:
                reps.append("barter rule B2 (%s) %s: input %s is made by an unattended farm (%s)"
                            % (b.group, b.id, i, AFK_FARMABLE[i][0]))
        if out_item in bank_prices:
            reps.append("barter rule B3 (%s) %s: the Bank buys the output %s at $%d"
                        % (b.group, b.id, out_item, bank_prices[out_item]))
        one_hop = sorted({rid for rid, _n in recipes_from.get(out_item, ()) if rid in bank_prices})
        if one_hop:
            reps.append("barter rule B3 (%s) %s: the output %s is one recipe from Bank-bought %s"
                        % (b.group, b.id, out_item, ", ".join(one_hop)))
        buy = b.authored[0]
        if buy and buy[1] > 1 and not b.experiment:
            reps.append("barter rule B4 (%s) %s: cost A is %d; Hero of the Village takes max(1, floor((0.3 + "
                        "0.0625 x amplifier) x %d)) off it whatever priceMultiplier is" % (b.group, b.id, buy[1],
                                                                                         buy[1]))
        pm = b.fields.get("priceMultiplier")
        if pm is not None and float(pm) != 0.0 and not b.experiment:
            reps.append("barter rule B4 (%s) %s: priceMultiplier %s lets reputation and demand move cost A"
                        % (b.group, b.id, pm))
    f, r = barter_value_checks(placed + proposal, doc, conversions, bank_prices, best)
    fails += f
    reps += r
    return fails, reps, notes


def liquidation(item, conversions, bank_prices):
    """The most money the Bank pays for one `item`: directly, or for what one single-input recipe turns one of it into
    (a storage block uncrafts to nine; read from the jars' recipes, not from data/direct_trades.json pricing.values).
    None when the Bank buys neither."""
    vals = []
    if item in bank_prices:
        vals.append(float(bank_prices[item]))
    for _name, _kind, ings, rid, rcount in conversions:
        if len(ings) == 1 and ings[0][1] == 1 and ings[0][0] == {item} and rid in bank_prices:
            vals.append(float(bank_prices[rid]) * rcount)
    return max(vals) if vals else None


def _arena_prizes():
    """{item: [prize id]} of data/arena_fights.json's once-per-player prizes."""
    p = DATA / "arena_fights.json"
    out = {}
    if not p.is_file():
        return out
    for it in ((read_json(p).get("prizes") or {}).get("items") or []):
        for c in it.get("contents") or []:
            out.setdefault(c.get("item"), []).append(it.get("id"))
    return out


def barter_value_checks(edges, doc, conversions, bank_prices, best):
    """(failures, reports) on what a barter costs against what its output costs in money.

    The value of an input is what the player gives up for it: its liquidation (the Bank) when the Bank buys it or what
    it uncrafts to, else its cheapest money price (`best`), else unknown. The price of the output is its cheapest money
    path (`best`: sellers and recipes); where it has none, the counter lines the data names as the line's reference
    (data/markets.json prices, read here). The owner, 2026-10-08: "the exchange should be an alternative path, not a
    bypass", so FAILURE (BYPASS) when the worst-case inputs (cost A at 1) are worth less than the output's price.
    FAILURE (PREMIUM) when the Bank buys the output for more than the inputs are worth to it -- turning goods into more
    money than the Bank's own prices allow -- and for a vitamin at or above (E2). A once-per-player arena prize sold
    as stock is REPORTED (data/bank.json kinds.not_built records why it was kept off the counters)."""
    fails, reps = [], []
    md = read_json(DATA / "markets.json")
    counter = {(c["id"], s.get("id")): float(s["price"]) for c in md.get("counters") or [] for s in c.get("stock") or []}
    ref_by_out = {}
    for ln in doc.get("lines") or []:
        ref = ln.get("reference") or {}
        try:
            ref_by_out[(ln.get("sell") or {}).get("id")] = sum(counter[(ref["counter"], lid)] for lid in ref["lines"])
        except (KeyError, TypeError):
            pass
    prizes = _arena_prizes()
    for b in edges:
        if b.experiment:
            continue
        vals, unknown = 0.0, []
        for i, n in b.pays:
            v = liquidation(i, conversions, bank_prices)
            if v is None and i in best:
                v = best[i][0]
            if v is None:
                unknown.append(i)
            else:
                vals += v * n
        out, cnt = b.gets
        if out in best:
            price, how = best[out][0] * cnt, "its cheapest money path, %s" % best[out][1]
        elif out in ref_by_out:
            price, how = ref_by_out[out] * cnt, "the counter lines named as its reference"
        else:
            price, how = None, None
        if unknown:
            reps.append("barter value (%s) %s: NOT DERIVABLE, no value for %s" % (b.group, b.id, ", ".join(unknown)))
        elif price is None:
            reps.append("barter value (%s) %s: inputs worth $%.0f; the output has no money price to compare"
                        % (b.group, b.id, vals))
        else:
            reps.append("barter value (%s) %s: inputs worth $%.0f against $%.0f (%s): %.3f"
                        % (b.group, b.id, vals, price, how, vals / price if price else float("inf")))
            if vals < price - 1e-6:
                fails.append("BARTER BYPASS (%s) %s: the worst-case inputs are worth $%.0f, under the output's $%.0f "
                             "(%s): cheaper than the counter" % (b.group, b.id, vals, price, how))
        pay = bank_prices.get(out)
        if pay is not None and not unknown:
            if pay * cnt > vals + 1e-6 or (out in VITAMINS and pay * cnt >= vals - 1e-6):
                fails.append("BARTER PREMIUM (%s) %s: the Bank pays $%d for %d x %s, inputs worth $%.0f"
                             % (b.group, b.id, pay * cnt, cnt, out, vals))
        if out in prizes:
            reps.append("barter trophy (%s) %s: %s is a once-per-player arena prize (data/arena_fights.json %s); "
                        "data/bank.json kinds.not_built kept it off the counters so a trophy does not become stock"
                        % (b.group, b.id, out, ", ".join(prizes[out])))
    return fails, reps


# ------------------------------------------------------------------------------------------------ forceload
_BLOCK_AT = re.compile(r"\b(?:if|unless) block (-?\d+) (-?\d+) (-?\d+)")
_SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+)")
_FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+)")
_SCHEDULE = re.compile(r"\bschedule function (\S+) (\d+)t\b")
_FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+))?\s*$")


def touched_chunks(text):
    """{(chunk x, chunk z): an (x, z) in it} of every block a function reads or writes and every summon it places."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        pts = [(int(m.group(1)), int(m.group(3))) for m in _BLOCK_AT.finditer(line)]
        m = _SETBLOCK.match(line)
        if m:
            pts.append((int(m.group(1)), int(m.group(3))))
        m = _FILL.match(line)
        if m:
            x0, z0, x1, z1 = int(m.group(1)), int(m.group(3)), int(m.group(4)), int(m.group(6))
            for cx in range(min(x0, x1) >> 4, (max(x0, x1) >> 4) + 1):
                for cz in range(min(z0, z1) >> 4, (max(z0, z1) >> 4) + 1):
                    pts.append((max(min(x0, x1), cx * 16), max(min(z0, z1), cz * 16)))
        m = SUMMON_AT.match(line)
        if m:
            pts.append((math.floor(float(m.group(2))), math.floor(float(m.group(4)))))
        for x, z in pts:
            out.setdefault((x >> 4, z >> 4), (x, z))
    return out


def forceload_checks(files, steps, step_id="R18DT"):
    """Failures: a step runs a function that touches a chunk no forceload holds at that moment, or removes the hold
    before a function the run scheduled has had its ticks. Read from the emitted functions and the step list (the
    reapply step's actions), never from the data's coordinates: what is checked is what the server would run."""
    fails = []
    held = []                                            # [(cx0, cz0, cx1, cz1)]
    pending = []                                         # [(function, seconds still to wait, chunks)]

    def fn_text(name):
        ns, _, path = name.partition(":")
        return files.get("data/%s/function/%s.mcfunction" % (ns, path))

    def covered(ch):
        return any(a <= ch[0] <= c and b <= ch[1] <= d for a, b, c, d in held)

    for kind, v in steps:
        if kind == "cmd":
            m = _FORCELOAD.match(str(v))
            if m:
                x0, z0 = int(m.group(2)), int(m.group(3))
                x1, z1 = (int(m.group(4)), int(m.group(5))) if m.group(4) else (x0, z0)
                box = (min(x0, x1) >> 4, min(z0, z1) >> 4, max(x0, x1) >> 4, max(z0, z1) >> 4)
                if m.group(1) == "add":
                    held.append(box)
                else:
                    for fname, left, chunks in pending:
                        if left > 0 and any(box[0] <= c[0] <= box[2] and box[1] <= c[1] <= box[3] for c in chunks):
                            fails.append("FORCELOAD %s releases %s while %s, scheduled %.1f s earlier than it runs, "
                                         "still needs it" % (step_id, v, fname, left))
                    if box in held:
                        held.remove(box)
        elif kind == "wait":
            pending = [(f, left - float(v), ch) for f, left, ch in pending]
        elif kind == "fn":
            text = fn_text(v)
            if text is None:
                fails.append("FORCELOAD %s runs %s, which the pack does not emit" % (step_id, v))
                continue
            for ch, (x, z) in sorted(touched_chunks(text).items()):
                if not covered(ch):
                    fails.append("FORCELOAD %s runs %s, which touches chunk %s at (%d, %d): no forceload holds it"
                                 % (step_id, v, ch, x, z))
            for m in _SCHEDULE.finditer(text):
                sub = fn_text(m.group(1)) or ""
                chunks = set(touched_chunks(sub)) | set(touched_chunks(text))
                pending.append((m.group(1), int(m.group(2)) / 20.0, chunks))
    return fails


# ------------------------------------------------------------------------------------------------ the run
def audit(server_dir=None, vanilla_jar=None, markets_mod=None, bank_mod=None, use_jars=True, traders_mod=None,
          direct_trades_mod=None, direct_trades_doc=None):
    """(failures, reports, notes)."""
    fails, reps, notes = [], [], []
    bank_doc = read_json(DATA / "bank.json")
    markets_doc = read_json(DATA / "markets.json")
    trader_doc = read_json(DATA / "traders.json")
    progression = read_json(DATA / "progression.json")
    routes_doc = read_json(DATA / "routes.json")
    towns_doc = read_json(DATA / "towns.json")

    emitted = bank_entries_emitted(bank_mod)
    committed = read_json(COMMITTED_BANK)["bank"]
    if emitted != committed:
        diff = sorted({e["item"] for e in emitted} ^ {e["item"] for e in committed}
                      | {a["item"] for a, b in zip(emitted, committed) if a != b})
        fails.append("STALE BANK: modpack/config/cobbledollars/bank.json is not tools/bank.py's output (%d entries vs "
                     "%d; differing: %s)" % (len(committed), len(emitted), ", ".join(diff[:8])))
    bank_prices = bank_effective(emitted)
    for k, v in bank_effective(committed).items():
        bank_prices[k] = max(bank_prices.get(k, 0), v)
    dup = sorted({e["item"] for e in emitted if sum(1 for x in emitted if x["item"] == e["item"]) > 1})
    if dup:
        reps.append("bank lists an id twice: %s (the higher price is audited)" % ", ".join(dup))

    sales = market_sales(markets_mod) + apricorn_sales() + default_shop_sales()
    offered, claimed = {}, None
    if server_dir and Path(server_dir).is_dir():
        ts, offered, claimed = trader_sales(server_dir, traders_mod)
        sales += ts
    else:
        notes.append("NOT READ: the shopkeepers' template shops and the Mart tiers' emitted shelves (no --server-dir); "
                     "this is a PARTIAL run")

    conversions = []
    if use_jars and server_dir and vanilla_jar and Path(vanilla_jar).is_file() and Path(server_dir).is_dir():
        jars = load_jars(str(server_dir), str(vanilla_jar))
        conversions = jars.conversions()
        f, r = id_checks(jars.items, emitted, bank_doc, sales, markets_doc)
        fails += f
        reps += r
        notes.append("read %d items, %d tags, %d priceable recipes from the jars" % (len(jars.items), len(jars.tags),
                                                                                  len(conversions)))
    else:
        notes.append("NOT READ: recipes and item ids (no jars): arbitrage is direct sale only, ids unchecked; "
                     "this is a PARTIAL run")

    best = cheapest(sales, conversions)
    f, r = arbitrage(bank_prices, best)
    fails += f
    reps += r
    reps += unsited_arbitrage(bank_prices, sales)
    notes.append("arbitrage: %d bank prices against %d sale offers (%d sited) and %d recipes"
                 % (len(bank_prices), len(sales), sum(1 for s in sales if s.sited), len(conversions)))
    f, r, n = barter_checks(sales, conversions, bank_prices, best, doc=direct_trades_doc, dt_mod=direct_trades_mod)
    fails += f
    reps += r
    notes += n

    f, r = vitamin_checks(best, bank_prices)
    fails += f
    reps += r
    reps += reward_ahead_report(markets_doc, progression, towns_doc)

    if claimed is not None:
        f, r = tier_checks(trader_doc, claimed, offered, progression, routes_doc, towns_doc)
        fails += f
        reps += r
        marts = {t["id"] for t in trader_doc["traders"] if t.get("stock") == "mart"}
        shelf = {}
        for s in sales:
            m = re.match(r"trader (\S+) / ", s.where)
            if m and m.group(1) in marts:
                prev = shelf.setdefault(m.group(1), {}).get(s.item)
                if prev is not None and abs(prev - s.unit) > 1e-9:
                    fails.append("PRICE %s offers %s twice, at $%g and $%g" % (m.group(1), s.item, prev, s.unit))
                shelf[m.group(1)][s.item] = min(s.unit, prev if prev is not None else s.unit)
        f, r = mart_price_checks(trader_doc, markets_doc, shelf)
        fails += f
        reps += r

    reps += exchange_report(markets_doc, sales, bank_prices, bank_doc, conversions, progression, routes_doc)
    reps += afk_report(bank_prices, bank_doc, server_dir if server_dir and Path(server_dir).is_dir() else None)
    return fails, reps, notes


def default_server_dir():
    return os.environ.get("COBBLERS_SNAPSHOT_DIR") or (DEFAULT_SNAPSHOT if Path(DEFAULT_SNAPSHOT).is_dir() else None)


def default_vanilla_jar():
    return os.environ.get("COBBLERS_VANILLA_JAR") or (DEFAULT_VANILLA if Path(DEFAULT_VANILLA).is_file() else None)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server-dir", default=default_server_dir(),
                   help="an OFFLINE server snapshot (mods/, datapacks/); never the live server")
    p.add_argument("--vanilla-jar", default=default_vanilla_jar())
    p.add_argument("--no-jars", action="store_true")
    a = p.parse_args(argv)
    fails, reps, notes = audit(a.server_dir, a.vanilla_jar, use_jars=not a.no_jars)
    for n in notes:
        print("NOTE %s" % n)
    for r in reps:
        print("REPORT %s" % r)
    for f in fails:
        print("FAILURE %s" % f)
    print("economy_audit: %d problem(s), %d report line(s)%s"
          % (len(fails), len(reps), " -- PARTIAL run" if any("PARTIAL" in n for n in notes) else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
