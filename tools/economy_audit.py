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
    because a few blocks can move it.
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


def tier_checks(trader_doc, claimed, offered, progression, routes_doc, towns_doc):
    """(failures, reports)."""
    fails, reps = [], []
    policy = trader_doc["stock_policy"]
    mart = policy["mart"]
    item_tier = {}
    for t in mart.get("tiers") or []:
        for i in t["items"]:
            item_tier[i] = t["badges"]
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


# ------------------------------------------------------------------------------------------------ the run
def audit(server_dir=None, vanilla_jar=None, markets_mod=None, bank_mod=None, use_jars=True, traders_mod=None):
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

    if claimed is not None:
        f, r = tier_checks(trader_doc, claimed, offered, progression, routes_doc, towns_doc)
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
