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
              overrides the base; a base item no longer bought is REPORTED with its base price and the base_removed
              line. The CHECK (2026-10-10, afk_farmable, never data/bank.json afk_rule's lists): the farm set is
              AFK_FARMABLE + AFK_EXTRA (less farms whose every mob the server's mobsbegone blacklist names), the loot of
              every block whose blockstate carries `age`, every gameplay/fishing loot table, the cobblemon:apricorns and
              cobblemon:berries tags, every species drop the server's PastureLoot.json item_blacklist does not name,
              the entity loot of every mob the blacklist does not name, and the closure under every recipe (crafting,
              cooking, Cobblemon's brewing stand and campfire pot). FAILURE for a bank price on an item in that set
              unless data/bank.json afk_rule.exceptions names it with a why and a decision (then REPORTED). For each
              excepted ranch drop the money per hour of a pastured Pokemon is REPORTED (expected_picks: Cobblemon's
              own drop roll, read from the jar).
  buyer       the Produce Buyer (tools/produce_buyer.py build(), the emitted pack, read line by line): the schedule from
              the leg function, the allowance reset guarded by a changed badge count, and in each sell function count
              (clear ... 0) -> short gate -> take exactly N -> exact gate -> one pay macro -> balance check. FAILURE on
              any break of that order; ARBITRAGE when a crate costs less with money (every seller and recipe) than the
              buyer's top price.
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
  - recipes added by our own generated datapacks after the snapshot date, custom/special recipes, vanilla potion
    brewing (code, not JSON; Cobblemon's brewing_stand recipes ARE read since 2026-10-10), and container remainders
    (a bucket given back is counted as consumed);
  - smelting and brewing fuel (counted as free, so a chain is flagged at its most generous; blaze powder is finite
    here: blaze rods come only from Nether chests, docs/research/OBTAINABILITY_SWEEP_2026-10-05.md, relayed);
  - for afk: whether a campfire pot or a brewing stand runs unattended (a crafting step is counted as the builder's
    `crafts` rule counts it: one craft from farmed goods is farmed), that Pasture Loot rolls the species table with
    its amount (ASSUMED), a species' forms' own drop tables, whether a seed is ever found (one is enough), and a
    harvester's real rate;
  - for the buyer: that the dialogue opens and runs the function as the player, that `cobbledollars query` returns the
    balance as its result (relayed), the cooldown's tick arithmetic, and a player's scoreboard name changing (a new
    holder, a fresh allowance) -- EXP-061;
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
_AGE = re.compile(r"(?:^|,)age=")


def _has_age(bs):
    """True when a blockstate file's variants or multipart conditions name an `age` property (random-tick growth)."""
    if not isinstance(bs, dict):
        return False
    if any(_AGE.search(k) for k in (bs.get("variants") or {})):
        return True
    for part in bs.get("multipart") or []:
        when = part.get("when") if isinstance(part, dict) else None
        conds = (when.get("OR") or when.get("AND") or [when]) if isinstance(when, dict) else []
        if any(isinstance(c, dict) and "age" in c for c in conds):
            return True
    return False


class Jars:
    """Items, item tags and recipes read from the vanilla jar and a server's mods/ and datapacks/."""

    def __init__(self):
        self.items, self.tags, self.recipes = set(), {}, []
        # the AFK reader's inputs: blocks whose blockstate carries `age` (random-tick growth), every loot table (all
        # copies: a datapack's copy and the jar's are both kept, so the union is the generous reading), and every
        # species / species_additions drop table [(where, file id, drops)]
        self.aged, self.loot, self.species = set(), {}, []

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
        m = re.fullmatch(r"assets/([^/]+)/blockstates/(.+)\.json", name)
        if m:
            try:
                bs = json.loads(read().decode("utf-8-sig"))
            except ValueError:
                return
            if _has_age(bs):
                self.aged.add("%s:%s" % m.groups())
            return
        m = re.fullmatch(r"data/([^/]+)/loot_tables?/(.+)\.json", name)
        if m:
            try:
                self.loot.setdefault("%s:%s" % m.groups(), []).append(json.loads(read().decode("utf-8-sig")))
            except ValueError:
                pass
            return
        m = re.fullmatch(r"data/([^/]+)/species(?:_additions)?/(.+)\.json", name)
        if m:
            try:
                sp = json.loads(read().decode("utf-8-sig"))
            except ValueError:
                return
            if isinstance(sp, dict) and isinstance(sp.get("drops"), dict):
                self.species.append((where, "%s:%s" % m.groups(), sp["drops"]))
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

    def loot_items(self, table, seen=None):
        """Every item id any copy of a loot table can drop: item entries, tag entries and nested loot_table
        references, through pools/entries/children (functions and conditions are not read: a conditional drop counts)."""
        seen = set() if seen is None else seen
        if table in seen:
            return set()
        seen.add(table)
        out = set()
        for doc in self.loot.get(table, ()):
            out |= self._loot_walk(doc, seen)
        return out

    def _loot_walk(self, node, seen):
        out = set()
        if isinstance(node, list):
            for x in node:
                out |= self._loot_walk(x, seen)
        elif isinstance(node, dict):
            t = str(node.get("type", "")).replace("minecraft:", "")
            name = node.get("name")
            if t == "item" and isinstance(name, str):
                out.add(name)
            elif t == "tag" and isinstance(name, str):
                out |= self.tag_items(name.lstrip("#"))
            elif t == "loot_table":
                v = node.get("value", name)
                if isinstance(v, str):
                    out |= self.loot_items(v if ":" in v else "minecraft:" + v, seen)
                elif isinstance(v, dict):
                    out |= self._loot_walk(v, seen)
            for k in ("pools", "entries", "children"):
                if k in node:
                    out |= self._loot_walk(node[k], seen)
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
            if t == "cobblemon:brewing_stand":
                # Cobblemon 1.8.0's brewing (data/cobblemon/recipe/brewing_stand/*.json: input, bottle, result): one
                # input over the stand's three bottles makes three results. The blaze powder fuel is counted free, as
                # smelting fuel is.
                ings = [(self.ingredient(r.get("bottle")), 3), (self.ingredient(r.get("input")), 1)]
                if any(acc is None or not acc for acc, _ in ings):
                    continue
                out.append((name, t, ings, rid, 3 * max(1, rcount)))
                continue
            if t in ("crafting_shaped", "cobblemon:cooking_pot"):
                key, pattern = r.get("key") or {}, r.get("pattern") or []
                counts = {}
                for row in pattern:
                    for ch in row:
                        if ch != " ":
                            counts[ch] = counts.get(ch, 0) + 1
                for ch, n in counts.items():
                    ings.append((self.ingredient(key.get(ch)), n))
            elif t in ("crafting_shapeless", "cobblemon:cooking_pot_shapeless"):
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
    removed = {r["item"]: r for r in ((bank_doc.get("base_removed") or {}).get("entries") or [])}
    for item, (how, _mobs) in sorted(AFK_FARMABLE.items()):
        if item in bank_prices or item not in base:
            continue
        where = ("data/bank.json:%s base_removed" % line_of(DATA / "bank.json", item) if item in removed
                 else "no record in data/bank.json base_removed")
        reps.append("afk %s base $%d (base-pack/cobbleverse/config/cobbledollars/bank.json:%s) -- %s; REMOVED from the "
                    "output (%s)" % (item, base[item], line_of(BASE_BANK, item), how, where))
    return reps


# ------------------------------------------------------------------------------------------------ afk: the check
# The auditor's own statement of what an unattended farm makes beyond AFK_FARMABLE, for growth the jars' blockstates do
# not show (sugar cane, kelp, cactus and bamboo change no model with age) and for the blocks no crop rule covers.
# {item or #tag: (mechanism, [vanilla mobs the farm needs])}
AFK_EXTRA = {
    "minecraft:pumpkin": ("observer pumpkin farm", []),
    "minecraft:sugar_cane": ("observer sugar cane farm", []),
    "minecraft:kelp": ("observer kelp farm", []),
    "minecraft:cactus": ("cactus farm", []),
    "minecraft:bamboo": ("observer bamboo farm", []),
    "minecraft:brown_mushroom": ("mushroom spread in the dark", []),
    "minecraft:red_mushroom": ("mushroom spread in the dark", []),
    "minecraft:chorus_fruit": ("chorus farm (the End)", []),
    "#minecraft:logs": ("a tree farm", []),
    "#minecraft:saplings": ("a tree farm", []),
    "minecraft:cobblestone": ("a cobblestone generator under an idle player's pickaxe", []),
    "minecraft:basalt": ("a basalt generator under an idle player's pickaxe", []),
    "minecraft:clay_ball": ("mud under pointed dripstone dries to clay", []),
    "minecraft:pointed_dripstone": ("a dripstone farm", []),
    "minecraft:bone_meal": ("a composter fed by a crop farm (composting is not a recipe)", []),
    "minecraft:egg": ("chicken egg farm", ["minecraft:chicken"]),
    "minecraft:honeycomb": ("bee farm", ["minecraft:bee"]),
    "minecraft:honey_bottle": ("bee farm", ["minecraft:bee"]),
    "minecraft:snowball": ("snow golem farm", ["minecraft:snow_golem"]),
    "minecraft:white_wool": ("sheep farm", ["minecraft:sheep"]),
    "minecraft:milk_bucket": ("a penned cow", ["minecraft:cow"]),
}
# entity loot tables that are not a farm whatever the blacklist says: the End is shut, a player is not a mob
NOT_A_MOB_FARM = {"minecraft:entities/ender_dragon": "the End is shut (data/bank.json unreachable)",
                  "minecraft:entities/player": "a player", "minecraft:entities/armor_stand": "placed, not spawned"}
PASTURE_LOOT = "PastureLoot.json"


PASTURE_LOOT_OVERLAY = ROOT / "modpack" / "config" / PASTURE_LOOT


def _rel(p):
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def pasture_config(server_dir=None, overlay=None):
    """(PastureLoot config, the file read): OUR overlay (modpack/config/PastureLoot.json) when it exists, because install
    copies modpack/config over the server's config/ and so the overlay is the file the server runs; else the server's
    if given; else the base pack's. A snapshot taken before the overlay existed carries the base file in its config/,
    and judging the ranch by it would audit a blacklist we no longer ship. Whether the overlay actually reached a server
    is tools/install_check.py's question, not this audit's. `overlay` replaces the overlay path (tests)."""
    ov = PASTURE_LOOT_OVERLAY if overlay is None else Path(overlay)
    for p in [ov] + ([Path(server_dir) / "config" / PASTURE_LOOT] if server_dir else []) + \
             [ROOT / "base-pack" / "cobbleverse" / "config" / PASTURE_LOOT]:
        if p.is_file():
            return read_json(p), p
    return {}, None


def ranch_drops(jars, blacklist):
    """{item: [(species file id, entry)]}: every species drop entry Pasture Loot can pay (its blacklist removed)."""
    out = {}
    for _where, sid, drops in jars.species:
        for ent in drops.get("entries") or []:
            it = ent.get("item") if isinstance(ent, dict) else None
            if isinstance(it, str) and it not in blacklist:
                out.setdefault(it, []).append((sid, ent))
    return out


def afk_farmable(jars, server_dir=None, conversions=None):
    """({item: (depth, how)}, [blocked report lines]): what an unattended farm makes, derived here and nowhere else.

    depth 0, the sources: AFK_FARMABLE and AFK_EXTRA (a farm whose every needed mob is on the server's mobsbegone
    blacklist is BLOCKED and left out); the drops of every block whose blockstate carries `age` (random-tick growth,
    harvested by water, piston or villager); every gameplay/fishing loot table (AFK fishing); the cobblemon:apricorns
    and cobblemon:berries tags (they regrow in place); every species drop Pasture Loot's item_blacklist does not name
    (a pastured Pokemon drops from its own table); the entity loot of every vanilla mob the blacklist does not name.
    depth n: a recipe (conversions) whose every slot accepts an item of depth < n."""
    black, _src = mob_blacklist(server_dir)
    farm, blocked = {}, []

    def add(item, how, depth=0):
        if item not in farm or depth < farm[item][0]:
            farm[item] = (depth, how)

    for item, (how, mobs) in sorted(list(AFK_FARMABLE.items()) + list(AFK_EXTRA.items())):
        if mobs and all(m in black for m in mobs):
            blocked.append("afk stated source blocked %s: %s needs %s, blacklisted" % (item, how, ", ".join(mobs)))
            continue
        for it in (jars.tag_items(item[1:]) if item.startswith("#") else {item}):
            add(it, "stated: " + how)
    for b in sorted(jars.aged):
        ns, p = b.split(":", 1)
        for it in jars.loot_items("%s:blocks/%s" % (ns, p)):
            add(it, "crop: %s grows by age and drops it" % b)
    for t in sorted(jars.loot):
        if t.split(":", 1)[1].startswith("gameplay/fishing"):
            for it in jars.loot_items(t):
                add(it, "fishing loot (%s)" % t)
    for tag in ("cobblemon:apricorns", "cobblemon:berries"):
        for it in jars.tag_items(tag):
            add(it, "grove: #%s regrows in place" % tag)
    pl, pl_src = pasture_config(server_dir)
    for it, ents in sorted(ranch_drops(jars, set(pl.get("item_blacklist") or [])).items()):
        names = sorted({s.rsplit("/", 1)[-1] for s, _e in ents})
        add(it, "ranch: Pasture Loot pays it from %d species (%s%s), %s does not blacklist it"
            % (len(names), ", ".join(names[:4]), ", ..." if len(names) > 4 else "",
               _rel(pl_src) if pl_src else "no PastureLoot config"))
    for t in sorted(jars.loot):
        m = re.fullmatch(r"minecraft:entities/([a-z0-9_]+)", t)
        if not m or t in NOT_A_MOB_FARM or ("minecraft:" + m.group(1)) in black:
            continue
        for it in jars.loot_items(t):
            add(it, "mob farm: minecraft:%s is not blacklisted" % m.group(1))
    conversions = jars.conversions() if conversions is None else conversions
    for _ in range(12):
        changed = False
        for name, kind, ings, rid, _rc in conversions:
            depth, parts = 0, []
            for acc, _n in ings:
                got = min(((farm[i][0], i) for i in acc if i in farm), default=None)
                if got is None:
                    break
                depth = max(depth, got[0])
                parts.append(got[1])
            else:
                if rid not in farm or depth + 1 < farm[rid][0]:
                    farm[rid] = (depth + 1, "%s %s from %s" % (kind, name, " + ".join(parts)))
                    changed = True
        if not changed:
            break
    return farm, blocked


def afk_chain(farm, item, depth=0):
    d, how = farm[item]
    text = "%s (%s)" % (item, how)
    if d and depth < 3:
        m = re.search(r" from (.+)$", how)
        for s in dict.fromkeys(m.group(1).split(" + ") if m else []):
            if s in farm and s != item and farm[s][0] < d:
                text += " <- " + afk_chain(farm, s, depth + 1)
    return text


def afk_checks(bank_prices, bank_doc, farm):
    """(failures, reports): FAILURE for every item the Bank buys that an unattended farm makes (afk_farmable), unless
    data/bank.json afk_rule.exceptions names it with a why and a decision (the owner's record; reported, not failed)."""
    fails, reps = [], []
    exc = {e.get("item"): e for e in ((bank_doc.get("afk_rule") or {}).get("exceptions") or [])}
    for item, pay in sorted(bank_prices.items()):
        if item not in farm:
            continue
        e = exc.get(item)
        if e and str(e.get("why") or "").strip() and str(e.get("decision") or "").strip():
            reps.append("afk exception %s $%d (%s): %s -- %s" % (item, pay, e["decision"], e["why"][:90],
                                                                 afk_chain(farm, item)))
        else:
            fails.append("AFK BANK %s: the Bank pays $%d and an unattended farm makes it -- %s"
                         % (item, pay, afk_chain(farm, item)))
    for item in sorted(exc):
        if item not in bank_prices or item not in farm:
            reps.append("afk stale exception %s: %s" % (item, "not bought" if item not in bank_prices
                                                         else "no farm found for it by this audit"))
    return fails, reps


def _qty(ent):
    r = ent.get("quantityRange")
    if isinstance(r, str) and re.fullmatch(r"\d+-\d+", r):
        a, b = (int(x) for x in r.split("-"))
        return (a + b) / 2.0
    return float(ent.get("quantity", 1))


def expected_picks(drops):
    """[expected times each entry is chosen in one roll] of a Cobblemon drop table, exactly, by the algorithm of
    DropTable.getDrops in Cobblemon-fabric-1.8.0+1.21.1.jar (read with javap 2026-10-10): until the picked total reaches
    `amount`, one pass over the remaining entries in order takes the first whose percentage roll succeeds (picked +=
    its quantity, default 1; it leaves the pool once chosen maxSelectableTimes, default 1 ASSUMED) or, when none does,
    counts a miss (picked += 1); an entry whose quantity exceeds what remains leaves the pool."""
    ents = [e for e in drops.get("entries") or [] if isinstance(e, dict)]
    amt = drops.get("amount", 1)
    amt = int(amt) if isinstance(amt, (int, float)) else int(str(amt).split("-")[-1])
    q = [int(e.get("quantity", 1)) for e in ents]
    p = [min(1.0, float(e.get("percentage", 100.0)) / 100.0) for e in ents]
    cap = [int(e.get("maxSelectableTimes", 1)) for e in ents]
    memo = {}

    def go(pool, chosen, picked):
        key = (pool, chosen, picked)
        if key in memo:
            return memo[key]
        out = [0.0] * len(ents)
        rem = [i for i in pool if q[i] <= amt - picked]
        if picked >= amt or not rem:
            memo[key] = out
            return out
        miss = 1.0
        for i in rem:
            pr = miss * p[i]
            miss *= 1.0 - p[i]
            if pr <= 0:
                continue
            ch = list(chosen)
            ch[i] += 1
            nxt = tuple(j for j in rem if not (j == i and ch[i] >= cap[i]))
            sub = go(nxt, tuple(ch), picked + q[i])
            out[i] += pr
            for k in range(len(ents)):
                out[k] += pr * sub[k]
        if miss > 0:
            sub = go(tuple(rem), chosen, picked + 1)
            for k in range(len(ents)):
                out[k] += miss * sub[k]
        memo[key] = out
        return out

    return go(tuple(i for i in range(len(ents)) if q[i] <= amt), tuple([0] * len(ents)), 0)


def ranch_money_report(jars, bank_prices, bank_doc, server_dir=None):
    """REPORT the Bank's money per hour from a pasture for every bought, excepted ranch drop: drops an hour =
    60 x drop_chance_per_minute x 1200 / tick_per_minute (PastureLoot.json); per drop an entry pays its expected picks
    (expected_picks: Cobblemon's own roll, read from the jar) x its mean quantityRange. That Pasture Loot rolls the
    species table through getDrops with the species' amount is ASSUMED (not read from pastureLoot's code). The pasture
    holds defaultPasturedPokemonLimit (config/cobblemon/main.json)."""
    pl, _src = pasture_config(server_dir)
    per_hour = 60.0 * float(pl.get("drop_chance_per_minute", 0)) * 1200.0 / float(pl.get("tick_per_minute", 1200) or 1200)
    limit = None
    if server_dir and (Path(server_dir) / "config" / "cobblemon" / "main.json").is_file():
        limit = read_json(Path(server_dir) / "config" / "cobblemon" / "main.json").get("defaultPasturedPokemonLimit")
    exc = {e.get("item") for e in ((bank_doc.get("afk_rule") or {}).get("exceptions") or [])}
    black = set(pl.get("item_blacklist") or [])
    drops = ranch_drops(jars, black)
    tables = {sid: d for _w, sid, d in jars.species}
    reps = []
    for item in sorted(exc):
        if item not in bank_prices or item not in drops:
            continue
        best = None
        for sid in sorted({s for s, _e in drops[item]}):
            d = tables[sid]
            picks = expected_picks(d)
            per_drop = sum(pk * _qty(e) for pk, e in zip(picks, [e for e in d.get("entries") or [] if isinstance(e, dict)])
                           if e.get("item") == item)
            row = (per_drop * per_hour * bank_prices[item], per_drop, sid.rsplit("/", 1)[-1])
            best = max(best, row) if best else row
        money, per_drop, sp = best
        reps.append("ranch money %s at $%d: best %s, %.3f a drop, $%.0f an hour per pastured Pokemon (%d species drop "
                    "it; %.1f drops an hour)%s" % (item, bank_prices[item], sp, per_drop, money,
                                                   len({s for s, _ in drops[item]}), per_hour,
                                                   "; a pasture of %d: $%.0f an hour" % (limit, money * limit)
                                                   if limit else ""))
    return reps


# ------------------------------------------------------------------------------------------------ the Produce Buyer
_PB_ROW = re.compile(r"^execute if score #badges (\S+) matches (\d+)(?:\.\.(\d+))? run scoreboard players set "
                     r"#(price|cap) \1 (-?\d+)$")


def _cmds(lines):
    return [ln.strip() for ln in lines if isinstance(ln, str) and ln.strip() and not ln.strip().startswith("#")]


def buyer_emitted(pb_mod=None):
    pb = pb_mod or importlib.import_module("produce_buyer")
    return pb.build(pb.load())


def buyer_checks(files, best, jars=None):
    """(failures, reports) over tools/produce_buyer.py build()'s OUTPUT, read here line by line.

    The leg function: the price and crate cap for each badge count 0-8, and the allowance reset, which must be guarded
    by a changed badge count (an unguarded reset is an allowance per sale). Each sell function, in order: the cooldown,
    the leg, the closed and spent gates, a COUNT with `clear @s <p> 0` (vanilla 1.21.1: a maxCount of 0 is a dry run, read
    from the client jar 2026-10-10) and its short gate, the TAKE of exactly N with an exact gate, then ONE pay through a
    macro function carrying `cobbledollars give`, and a balance check after it. FAILURE when the take is not before the
    pay, a gate follows the take, a return sits between take and pay, count and take differ in item or number, the count
    takes (a non-zero count), the pay is not once, `cobbledollars remove` appears, or the reset is unguarded. ARBITRAGE:
    a crate a player can buy with money (best: every seller and recipe) for less than the buyer's top price."""
    fails, reps = [], []
    leg = next((v for k, v in files.items() if k.endswith("/produce_buyer/leg.mcfunction")), None)
    if leg is None:
        return ["BUYER: the pack has no leg function"], reps
    L = _cmds(leg)
    price, cap = {}, {}
    for ln in L:
        m = _PB_ROW.match(ln)
        if m:
            lo, hi = int(m.group(2)), int(m.group(3) or m.group(2))
            for b in range(lo, hi + 1):
                (price if m.group(4) == "price" else cap)[b] = int(m.group(5))
    flags = [ln for ln in L if re.match(r"^execute if entity @s\[advancements=\{\S+=true\}\] run scoreboard players add "
                                         r"#badges \S+ 1$", ln)]
    if len(set(flags)) != len(flags):
        fails.append("BUYER leg: a badge flag is counted twice")
    resets = [ln for ln in L if re.search(r"(?:^|run )scoreboard players set @s \S+ 0$", ln)]
    guarded = [ln for ln in resets if re.match(r"^execute unless score @s (\S+) = #badges \S+ run ", ln)]
    if len(resets) != 1 or len(guarded) != 1:
        fails.append("BUYER leg: the allowance reset is not exactly one reset guarded by a changed badge count (%d "
                     "resets, %d guarded): an unguarded reset is a fresh allowance on every sale" % (len(resets), len(guarded)))
    else:
        legobj = re.match(r"^execute unless score @s (\S+) = ", guarded[0]).group(1)
        copy = [i for i, ln in enumerate(L) if re.match(r"^scoreboard players operation @s %s = #badges " % re.escape(legobj), ln)]
        if not copy or copy[0] < L.index(guarded[0]):
            fails.append("BUYER leg: the player's badge count is recorded before the reset compares it (the reset never "
                         "fires)" if copy else "BUYER leg: the badge count is never recorded (the reset fires every sale)")
    sched = [(b, price.get(b, 0), cap.get(b, 0)) for b in range(len(flags) + 1)]
    total = sum(p * c for _b, p, c in sched)
    reps.append("buyer schedule (emitted): %s; $%d a player over the campaign" % (
        ", ".join("%d badges $%d x %d" % row for row in sched), total))
    if any(sched[i][1] < sched[i + 1][1] for i in range(len(sched) - 1)):
        fails.append("BUYER leg: the emitted price rises with a badge")
    top = max((p for _b, p, _c in sched), default=0)

    pay_fns = {k: _cmds(v) for k, v in files.items() if isinstance(v, list) and "/produce_buyer/" in k}
    for path, lines in sorted(files.items()):
        m = re.search(r"/produce_buyer/sell/([a-z0-9_]+)\.mcfunction$", path)
        if not m:
            continue
        crate, C = m.group(1), _cmds(lines)
        w = "BUYER %s:" % crate
        idx = lambda pat: next((i for i, ln in enumerate(C) if re.search(pat, ln)), None)   # noqa: E731
        allx = lambda pat: [i for i, ln in enumerate(C) if re.search(pat, ln)]             # noqa: E731
        clears = [(i, re.match(r"^execute store result score (#\w+) \S+ run clear @s (\S+) (\d+)$", C[i]))
                  for i in allx(r"\bclear @s ")]
        if any(mm is None for _i, mm in clears):
            fails.append("%s a clear is not stored into a score (its count is unread)" % w)
            continue
        counts = [(i, mm) for i, mm in clears if mm.group(3) == "0"]
        takes = [(i, mm) for i, mm in clears if mm.group(3) != "0"]
        if len(counts) != 1:
            fails.append("%s %d dry-run counts (clear ... 0); the sale must count exactly once without taking" % (w, len(counts)))
            continue
        if len(takes) != 1:
            fails.append("%s %d takes; exactly one" % (w, len(takes)))
            continue
        (ci, cm), (ti, tm) = counts[0], takes[0]
        n = int(tm.group(3))
        if ti < ci:
            fails.append("%s it takes before it counts" % w)
        if cm.group(2) != tm.group(2):
            fails.append("%s it counts %s and takes %s" % (w, cm.group(2), tm.group(2)))
        short = idx(r"^execute unless score %s \S+ matches (\d+)\.\. run return" % re.escape(cm.group(1)))
        if short is None or not (ci < short < ti) or int(re.search(r"matches (\d+)\.\.", C[short]).group(1)) != n:
            fails.append("%s no short gate of %d between the count and the take" % (w, n))
        gate = idx(r"^execute unless score %s \S+ matches %d run return" % (re.escape(tm.group(1)), n))
        if gate is None or gate != ti + 1:
            fails.append("%s the take is not followed at once by an exact gate on %d taken" % (w, n))
        pays = allx(r"^function \S+ with storage ")
        gives = [k for k, v in pay_fns.items() if any("cobbledollars give" in ln for ln in v)]
        if len(pays) != 1:
            fails.append("%s %d pay calls; exactly one" % (w, len(pays)))
            continue
        pi = pays[0]
        fid = re.match(r"^function (\S+) with storage ", C[pi]).group(1)
        fns, fp = fid.split(":", 1)
        body = pay_fns.get("data/%s/function/%s.mcfunction" % (fns, fp)) or []
        if body != ["$cobbledollars give @s $(amount)"]:
            fails.append("%s the pay call %s is not exactly one `$cobbledollars give @s $(amount)`" % (w, fid))
        amt = idx(r"^execute store result storage \S+ pay\.amount int 1 run scoreboard players get #price \S+$")
        if amt is None or not (ti < amt < pi):
            fails.append("%s the paid amount is not the leg's #price, set after the take" % w)
        if pi < ti:
            fails.append("%s it pays before it takes" % w)
        between = [C[i] for i in range(ti + 2, pi) if re.search(r"\breturn\b", C[i])]
        if between:
            fails.append("%s a return between the take and the pay keeps the goods unpaid: %s" % (w, between[0][:80]))
        for pat, what in ((r"run time query gametime$", "the cooldown"), (r"^function \S*produce_buyer/leg$", "the leg"),
                          (r"^execute if score #price \S+ matches \.\.0 run return", "the closed gate"),
                          (r"^execute if score @s \S+ >= #cap \S+ run return", "the spent gate")):
            at = idx(pat)
            if at is None or at > ci:
                fails.append("%s %s is missing or comes after the count" % (w, what))
        if any("cobbledollars remove" in ln for ln in C) or any("cobbledollars give" in ln for ln in C):
            fails.append("%s the sell function moves money itself (only the pay macro may)" % w)
        if len(gives) != 1:
            fails.append("%s %d pay functions carry `cobbledollars give`" % (w, len(gives)))
        after = idx(r"^execute unless score #after \S+ = #want \S+ run return")
        if after is None or after < pi:
            fails.append("%s no balance check after the pay" % w)
        spent = idx(r"^execute if score @s \S+ >= #cap \S+ run return")
        sold_obj = re.match(r"^execute if score @s (\S+) >= ", C[spent]).group(1) if spent is not None else None
        inc = idx(r"^scoreboard players add @s %s 1$" % re.escape(sold_obj or "\0"))
        first_ret = next((i for i in range(ti + 2, len(C)) if re.search(r"\breturn\b", C[i])), None)
        if inc is None or (first_ret is not None and inc > first_ret):
            fails.append("%s a sale that took the crate can return before counting it against the allowance (command %s "
                         "returns, the count is command %s): if the balance check misfires after a real pay, every sale pays "
                         "and none is counted -- the cap fails open" % (w, first_ret, inc))
        # the crate's items, from the emitted predicate
        pred = tm.group(2)
        if pred.startswith("#"):
            ns, p = pred[1:].split(":", 1)
            tagf = files.get("data/%s/tags/item/%s.json" % (ns, p))
            items = set(tagf["values"]) if isinstance(tagf, dict) else (jars.tag_items(pred[1:]) if jars else set())
        else:
            items = {pred}
        if not items:
            reps.append("buyer %s: the predicate %s is not resolved here (no jars): its crate is not priced" % (crate, pred))
            continue
        got = min(((best[i][0], i) for i in items if i in best), default=None)
        if got is None:
            reps.append("buyer %s: a crate of %d (%s) cannot be bought with money: no seller or recipe" % (crate, n, pred))
            continue
        cost = got[0] * n
        if cost < top - 1e-9:
            fails.append("BUYER ARBITRAGE %s: a crate of %d costs $%.2f (%s) and the buyer pays $%d: $%.2f a crate, "
                         "inside the allowance -- %s" % (crate, n, cost, got[1], top, top - cost, chain(best, got[1])))
        else:
            reps.append("buyer %s: a crate of %d costs at least $%.2f with money (%s); the buyer pays at most $%d"
                        % (crate, n, cost, got[1], top))
    return fails, reps


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


# ------------------------------------------------------------------------------------------------ the Entei boss
def entei_files():
    """The Entei boss pack's generated files ({path: text}), built in memory by its own generator: what this audit
    reads is the OUTPUT that reaches the world, never data/entei_boss.json's description of it."""
    import entei_boss as EB
    return EB.build(EB.load())


def entei_checks(bank_prices, best, files=None):
    """(failures, reports) for the repeatable Entei (tools/entei_boss.py), from its generated loot tables, recipes and
    functions. The boss can be fought once per lockout for ever, so a drop the Bank buys is an unpriced mint; a
    function that pays CobbleDollars is a money reward the design forbids (data/entei_boss.json drops.rule); and a
    sigil the Bank buys for at least its ingredients' Bank value would make the entry a mint of its own.
    What it does NOT cover: whether a refused sigil comes back once and only once (a behaviour, tested by
    tests/test_entei_boss_audit.py on a simulator), and drops sold to a player-run shop (none exists)."""
    fails, reps = [], []
    if files is None:
        try:
            files = entei_files()
        except Exception as e:  # the generator fails closed on its own record: that is a finding here too
            return ["ENTEI the boss pack does not build: %s" % e], reps
    for path, text in sorted(files.items()):
        if "/loot_table/" not in path:
            continue
        for pool in json.loads(text).get("pools", []):
            for e in pool.get("entries", []):
                item = e.get("name") or ""
                if item in bank_prices:
                    fails.append("ENTEI drop %s (%s) is bought by the Bank at $%d: a boss fought once per lockout "
                                 "for ever would mint money" % (item, path, bank_prices[item]))
                if item.startswith("cobbledollars:"):
                    fails.append("ENTEI drop %s (%s) is money" % (item, path))
    for path, text in sorted(files.items()):
        if path.endswith(".mcfunction"):
            for n, line in enumerate(text.splitlines(), 1):
                if not line.startswith("#") and re.search(r"\bcobbledollars (add|give|set|pay)\b", line):
                    fails.append("ENTEI %s:%d pays money: %s" % (path, n, line.strip()))
    for path, text in sorted(files.items()):
        if "/recipe/" not in path:
            continue
        r = json.loads(text)
        res = (r.get("result") or {}).get("id")
        ings = [i.get("item") for i in r.get("ingredients", [])]
        value = sum(bank_prices.get(i, 0) for i in ings)
        cash = [best[i][0] for i in ings if i in best]
        if res in bank_prices and bank_prices[res] >= value:
            fails.append("ENTEI the sigil (%s, %s) sells to the Bank for $%d, at least its ingredients' $%d: "
                         "crafting it is a mint" % (path, res, bank_prices[res], value))
        reps.append("ENTEI entry: %s from %s; $%d of Bank value destroyed per sigil eaten; %s"
                    % (res, " + ".join(ings), value,
                       "cash path $%.0f" % sum(cash) if len(cash) == len(ings) else "no cash path (an ingredient is "
                       "sold by no counter)"))
        if value <= 0:
            reps.append("ENTEI entry costs nothing the Bank values: the lockout is the only limiter")
    return fails, reps


# ------------------------------------------------------------------------------------------------ the run
def audit(server_dir=None, vanilla_jar=None, markets_mod=None, bank_mod=None, use_jars=True, traders_mod=None,
          direct_trades_mod=None, direct_trades_doc=None, produce_buyer_mod=None):
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
    f, r = entei_checks(bank_prices, best)
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
    sd = server_dir if server_dir and Path(server_dir).is_dir() else None
    reps += afk_report(bank_prices, bank_doc, sd)
    if conversions:
        farm, blocked = afk_farmable(jars, sd, conversions)
        f, r = afk_checks(bank_prices, bank_doc, farm)
        fails += f
        reps += r + blocked + ranch_money_report(jars, bank_prices, bank_doc, sd)
        notes.append("afk: %d items an unattended farm makes (%d at depth 0), %d of the %d bank prices among them"
                     % (len(farm), sum(1 for d, _h in farm.values() if d == 0),
                        sum(1 for i in bank_prices if i in farm), len(bank_prices)))
    else:
        notes.append("NOT READ: the AFK farm set (no jars): the Bank's AFK check did not run; this is a PARTIAL run")
    f, r = buyer_checks(buyer_emitted(produce_buyer_mod), best, jars if conversions else None)
    fails += f
    reps += r
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
