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
  buyer       ECONOMY_V2 5.2 A4 under the owner's E3 (no cap, no allowance): the Trading Post (tools/produce_buyer.py
              build(), the emitted pack, read line by line by tp_read). ORDER: each crate's sale counts (clear ... 0),
              gates short, reads the balance, takes exactly N with an exact gate at once, pays ONCE through the
              `$cobbledollars give` macro an amount equal to a literal #price never rewritten after the take, and
              re-reads the balance; sell-all calls every category once and the specimens, credits each from what its
              bounded take REMOVED (#took, reset before it), never returns between its first take and its ONE pay of
              #total except the nothing-taken gate, and re-reads. NO ALLOWANCE: no line reads a badge count, a cap, a
              leg or the v1 scores. SPINE (A1 for the post): every crate's emitted count and price must equal count x
              W(tier) / rate_per_hour from data/produce_buyer.json, a whole dollar, with W(tier) summed HERE from
              data/bank.json buys (rate_per_hour x price over effort_model.tiers[t].from_tiers, ECONOMY_V2 1.1), and
              every specimen's W(early) / (ko_per_hour x the best live per_defeat in the notes file the record names),
              $1 to cap_p x $100; exact, no slack. ARBITRAGE: every item a sale accepts -- every member of its tag as the
              jars define it, mod members included -- must not be obtainable with money (every sited seller including
              each Mart's template shop, every jar recipe, every placed barter edge, run to a fixed point) for LESS than
              the unit the post pays; the proposal lines are judged separately; a post good the wandering trader's
              offers reach (taken as free) FAILS once emerald has a dollar path. Break-even, unsited sellers under a
              unit, Bank double channels and the ranch's unattended income (tp_ranch_report) are REPORTED.
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
              Since ECONOMY_V2 (2026-10-13) a reference line is a money line as it stood (stock or superseded_stock),
              or `reference.bank`, the spine (1 P = $100): items valued at the effective Bank; the Master Ball's spine
              worth is the owner's E4 (OWNER_SPINE: 2 netherite ingots at the Bank), stated here, so a data reference
              that drifts from it is REPORTED and not used. A placed top-tier line with no derivable value FAILS.
  top tier    ECONOMY_V2 5.2 A3 (top_tier_checks): a reachability search from dollars (every seller, sited or not; every
              jar recipe; every barter edge; the vanilla wandering trader's emerald offers, a STATED table) to the
              top tier (TOP_TIER, from the design) and its inputs (TOP_TIER_INPUTS + every input of a line selling
              one). FAILURE for each reached. Rule B1 above stays a REPORT for the experiment lines.
  bank v2     ECONOMY_V2 5.2 A5 and A2 (bank_v2_checks), over the emitted and committed bank, base entries included:
              FAILURE for a cobblemon: id; FAILURE when an entry's upper rate x $1 exceeds 1.5 x the fight hour of the
              leg its tier opens (income_basis.leg_by_badge / max_leg_hours; the nether leg from data/nether_gate.json,
              not the bank's claim). An entry with no declared rate is judged at the design's 2.2 estimate (BULK_RATES)
              or REPORTED. NOT here: A1 (re-deriving every price from the spine: the per-item split of a tier's wage
              is not determined by the data; the Trading Post's crates ARE recomputed, under `buyer`) and A6
              (villager trades beyond the wandering trader's table). A4 is `buyer` above.
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
  - for the Trading Post: that the dialogue opens and runs the function as the player, that `clear ... 0` removes
    nothing, that the bounded macro take removes at most $(n) and reports it, that `cobbledollars query` returns the
    balance (relayed) -- EXP-061; conversions that are not recipes (a block broken for its drops, a tool used on a
    block, a mob bred or hatched: an egg, wheat fed to cows), checked by hand on 2026-10-13 against every sited offer
    and none undercuts a unit, but not by code; recipes in our own generated datapacks after the snapshot date; the
    rates behind every crate (ESTIMATES until timed, U3) -- the audit proves the post pays no more than money costs,
    not that its prices are right;
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
from fractions import Fraction
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
COMMITTED_BANK = ROOT / "modpack" / "config" / "cobbledollars" / "default_bank.json"
DIRECT_TRADES = DATA / "direct_trades.json"

DEFAULT_SNAPSHOT = "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05"
DEFAULT_VANILLA = "C:/Users/wnd/AppData/Roaming/ModrinthApp/meta/versions/1.21.1-0.19.5/1.21.1-0.19.5.jar"
# the server's mod set after the Cobblemon 1.8.2 lockstep update (101 jars, Cobblemon-fabric-1.8.2+1.21.1.jar among
# them); the 2026-10-05 snapshot's mods/ is Cobblemon 1.8.0. Its datapacks/ and config/ are still the snapshot's.
DEFAULT_MODS = "C:/Users/wnd/Documents/cobblers-local/server-mods-1.8.2"

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
def load_jars(server_dir, vanilla_jar, mods_dir=None):
    """The vanilla jar, the mods (`mods_dir` when given, else the server's mods/) and the server's datapacks/."""
    j = Jars()
    with zipfile.ZipFile(vanilla_jar) as z:
        j.scan_zip(z, Path(vanilla_jar).name)
    sd = Path(server_dir)
    for p in sorted((Path(mods_dir) if mods_dir else sd / "mods").glob("*.jar")):
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
        if not cheapest_round(best, conversions):
            break
    return best


def cheapest_round(best, conversions):
    """One pass of every conversion over `best`, in place; True when any cost fell."""
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
    return changed


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


# ------------------------------------------------------------------------------------------------ the Trading Post (A4)
# ECONOMY_V2 5.2 A4 under the owner's E3 (section 7, 2026-10-13: "No cap: farming is allowed. The Trading Post buys at
# fixed spine prices with no allowance"). With no allowance the ONLY guard against printing money is that nothing a
# player can buy, craft from bought inputs, or barter for costs less than the Trading Post pays for it: one unit of
# slack is a printer, so there is no tolerance anywhere below.
TP_ROUNDS = 200     # a cap on cheapest_fixed_point's rounds; reaching it is a FAILURE (not converged), never a tuned depth
_STORE = re.compile(r"^execute store result score (#\w+) (\S+) run clear @s (\S+)(?: (\d+))?$")
_ALLOWANCE = re.compile(r"#badges\b|#cap\b|advancements=|/leg\b|\bcob_pb_(?:leg|sold)\b")


def _cmds(lines):
    return [ln.strip() for ln in lines if isinstance(ln, str) and ln.strip() and not ln.strip().startswith("#")]


def buyer_emitted(pb_mod=None):
    pb = pb_mod or importlib.import_module("produce_buyer")
    return pb.build(pb.load())


def bank_tier_wages(bank_doc):
    """{tier: W(tier) in dollars}: ECONOMY_V2 1.1's "the tier's typical hour", which data/bank.json effort_model.derivation
    defines as "the sum over its items of rate_per_hour x price" over the buys whose tier is one of the tier's
    from_tiers. Summed HERE from the record; tools/bank.py tier_hours (the builder's) is never called. Exact (Fraction)."""
    out = {}
    for name, t in ((bank_doc.get("effort_model") or {}).get("tiers") or {}).items():
        src = set((t or {}).get("from_tiers") or [])
        out[name] = sum((Fraction(str(b["rate_per_hour"])) * Fraction(str(b["price"]))
                         for b in bank_doc.get("buys") or [] if b.get("tier") in src and b.get("rate_per_hour")),
                        Fraction(0))
    return out


def _half_up(x):
    """A whole dollar, halves up, exactly (x is a Fraction)."""
    return int(math.floor(Fraction(x) + Fraction(1, 2)))


def tp_expected(pb_doc, wages, notes):
    """({crate id: (count, dollars a crate, record items)}, {specimen: dollars a piece or None}) by this file's arithmetic from the
    record (data/produce_buyer.json: count, tier, rate_per_hour; specimens.ko_per_hour, wage_tier, cap_p) and the wage
    above: a crate is count x W(tier) / rate, a whole dollar (ECONOMY_V2 1.1); a specimen W(wage_tier) / (ko_per_hour x
    the best per_defeat of a LIVE dropper in the notes file the record names), from $1 to cap_p x P_DOLLARS (2.2
    "Specimens"). The drop chances are the research note's (RELAYED: a 1.8.0 scan); nothing here is the generator's."""
    crates = {}
    for c in pb_doc.get("crates") or []:
        w = wages.get(c.get("tier"))
        price = None if w is None else _half_up(Fraction(int(c["count"])) * w / Fraction(str(c["rate_per_hour"])))
        crates[c["id"]] = (int(c["count"]), price, set(c.get("items") or []))
    sp = pb_doc.get("specimens") or {}
    spec = {}
    for item in sp.get("items") or []:
        rec = ((notes or {}).get("items") or {}).get(item) or {}
        live = [Fraction(str(d[2])) for d in rec.get("droppers") or [] if len(d) > 4 and d[4]]
        w = wages.get(sp.get("wage_tier"))
        if not live or w is None:
            spec[item] = None
            continue
        raw = w / (Fraction(str(sp["ko_per_hour"])) * max(live))
        spec[item] = max(1, min(int(sp["cap_p"]) * P_DOLLARS, _half_up(raw)))
    return crates, spec


def _fn_path(fid):
    ns, p = fid.split(":", 1)
    return "data/%s/function/%s.mcfunction" % (ns, p)


def _fid(path):
    m = re.match(r"^data/([^/]+)/function/(.+)\.mcfunction$", path)
    return "%s:%s" % m.groups() if m else path


def tag_members(files, jars, tag, seen=None):
    """(item ids, resolved) a `#ns:path` predicate matches at runtime: the pack's own tag file and, unless it says
    replace, the jars' tag of the same id (tags merge across packs), nested tags followed. Unresolved when the tag is
    neither the pack's nor known to the jars given (or no jars were given for a tag the pack does not own)."""
    seen = set() if seen is None else seen
    if tag in seen:
        return set(), True
    seen.add(tag)
    ns, p = tag.split(":", 1)
    mine = files.get("data/%s/tags/item/%s.json" % (ns, p))
    vals, ok = [], True
    if isinstance(mine, dict):
        vals += list(mine.get("values") or [])
    if not (isinstance(mine, dict) and mine.get("replace")):
        if jars is not None and tag in jars.tags:
            vals += sorted(jars.tags[tag])
        elif not isinstance(mine, dict):
            ok = False
    out = set()
    for v in vals:
        v = v.get("id") if isinstance(v, dict) else v
        if not isinstance(v, str):
            continue
        if v.startswith("#"):
            got, k = tag_members(files, jars, v[1:], seen)
            out |= got
            ok = ok and k
        else:
            out.add(v)
    return out, ok


def _pay_tail_problems(w, C, start, amount_obj, pay_fns, store_ok=True):
    """Failures of one sale's pay: exactly one `function <pay> with storage <s> <path>` after `start`, its amount stored
    from `amount_obj` after `start` and before it, the pay function exactly the CobbleDollars give macro, then the
    balance re-read and compared with #before + the amount. Returns (failures, index of the pay or None)."""
    fails = []
    pays = [i for i, ln in enumerate(C) if re.match(r"^function \S+ with storage \S+ \S+$", ln)]
    if len(pays) != 1:
        return ["%s %d pay calls; exactly one" % (w, len(pays))], None
    pi = pays[0]
    fid, store, path = re.match(r"^function (\S+) with storage (\S+) (\S+)$", C[pi]).groups()
    if pay_fns.get(_fn_path(fid)) != ["$cobbledollars give @s $(amount)"]:
        fails.append("%s the pay call %s is not exactly one `$cobbledollars give @s $(amount)`" % (w, fid))
    amt = [i for i, ln in enumerate(C) if ln == "execute store result storage %s %s.amount int 1 run scoreboard players "
           "get %s %s" % (store, path, amount_obj[0], amount_obj[1])]
    if not amt or not (start < amt[-1] < pi):
        fails.append("%s the paid amount is not %s stored after the take and before the pay" % (w, amount_obj[0]))
    if pi < start:
        fails.append("%s it pays before it takes" % w)
    T = amount_obj[1]
    rr = [i for i, ln in enumerate(C) if ln == "execute store result score #after %s run cobbledollars query @s" % T]
    want = [i for i, ln in enumerate(C) if ln == "scoreboard players operation #want %s += %s %s" % (T, amount_obj[0], T)]
    base = [i for i, ln in enumerate(C) if ln == "scoreboard players operation #want %s = #before %s" % (T, T)]
    cmp_ = [i for i, ln in enumerate(C) if ln.startswith("execute unless score #after %s = #want %s run " % (T, T))]
    if not (rr and want and base and cmp_ and pi < rr[0] < cmp_[0] and base[0] < want[0] < cmp_[0]):
        fails.append("%s no balance re-read after the pay compared with #before + %s" % (w, amount_obj[0]))
    return fails, pi


def tp_read(files, jars=None):
    """(failures, crates, specimens, notes) read from tools/produce_buyer.py build()'s OUTPUT line by line:
    crates {id: dict(pred, n, price, items, resolved)}, specimens {item: price}. The checks (A4's order properties):

    every `sell/<id>`: the cooldown gate before the count; ONE dry-run count `clear @s <p> 0` (vanilla 1.21.1: a maxCount
    of 0 counts and removes nothing, read from the client jar 2026-10-10) with a short gate on the crate's N between it
    and the take; #before read before the take; ONE take `clear @s <p> N` of the same predicate, followed AT ONCE by an
    exact gate on N whose failure branch pays nothing; #price set once, unconditionally, to a literal, before the take
    and never written after it; no return between the gate and the ONE pay; the pay amount is #price; the balance is
    re-read after the pay.
    `sell/all`: the cooldown gate first; #before and #total = 0 before its first call; every crate's sellall/<id> and
    the specimens called exactly once and nothing else; no return between the first call and the ONE pay except the
    nothing-taken gate on #total; the pay amount is #total; the balance re-read.
    every `sellall/<id>`: the same N, #price and predicate as sell/<id>; a dry-run count, then #took set to 0, then the
    bounded take (a macro whose ONE line stores `clear @s <p> $(n)` into #took), then the credit #part = #price x #took
    / #n added to #total: the credit comes from what the take REMOVED, never from what was counted or asked for.
    `sellall/specimens`: per item a literal #price, #took reset, `clear @s <item>` into #took, #part = #took x #price
    added to #total; an item taken twice is a FAILURE.
    The pack as a whole: exactly one function carries `cobbledollars give` (the pay macro), none `cobbledollars remove`;
    no line reads a badge count, an allowance score or a leg (E3: no allowance, a crate pays the same at every badge)."""
    fails, notes = [], []
    fns = {k: _cmds(v) for k, v in files.items() if isinstance(v, list) and k.endswith(".mcfunction")}
    gives = sorted(k for k, v in fns.items() if any("cobbledollars give" in ln for ln in v))
    if len(gives) != 1:
        fails.append("BUYER %d functions carry `cobbledollars give` (%s); exactly one, the pay macro"
                     % (len(gives), ", ".join(gives[:4])))
    for k, v in sorted(fns.items()):
        if any("cobbledollars remove" in ln for ln in v):
            fails.append("BUYER %s takes money (`cobbledollars remove`)" % k)
        hit = next((ln for ln in v if _ALLOWANCE.search(ln)), None)
        if hit and "/produce_buyer/" in k:
            fails.append("BUYER %s keeps allowance machinery (E3: none): %s" % (k, hit[:100]))
    sell = {m.group(1): k for k in fns for m in [re.search(r"/produce_buyer/sell/([a-z0-9_]+)\.mcfunction$", k)] if m}
    crates = {}
    for crate, path in sorted(sell.items()):
        if crate == "all":
            continue
        C, w = fns[path], "BUYER %s:" % crate
        stored = [(i, _STORE.match(ln)) for i, ln in enumerate(C) if re.search(r"\bclear @s ", ln)]
        if any(m is None for _i, m in stored):
            fails.append("%s a clear is not stored into a score (its count is unread)" % w)
            continue
        counts = [(i, m) for i, m in stored if m.group(4) == "0"]
        takes = [(i, m) for i, m in stored if m.group(4) not in (None, "0")]
        if len(counts) != 1 or len(takes) != 1 or any(m.group(4) is None for _i, m in stored):
            fails.append("%s %d dry-run counts and %d takes (and %d take-alls); exactly one count and one take"
                         % (w, len(counts), len(takes), sum(1 for _i, m in stored if m.group(4) is None)))
            continue
        (ci, cm), (ti, tm) = counts[0], takes[0]
        n, pred, T = int(tm.group(4)), tm.group(3), tm.group(2)
        if ti < ci:
            fails.append("%s it takes before it counts" % w)
        if cm.group(3) != pred:
            fails.append("%s it counts %s and takes %s" % (w, cm.group(3), pred))
        short = [i for i, ln in enumerate(C) if re.match(r"^execute unless score %s \S+ matches %d\.\. run return"
                                                         % (re.escape(cm.group(1)), n), ln)]
        if not short or not (ci < short[0] < ti):
            fails.append("%s no short gate of %d between the count and the take" % (w, n))
        gate = re.match(r"^execute unless score %s \S+ matches %d run return(?: run (.*))?$" % (re.escape(tm.group(1)), n),
                        C[ti + 1]) if ti + 1 < len(C) else None
        if gate is None:
            fails.append("%s the take is not followed at once by an exact gate on %d taken" % (w, n))
        elif gate.group(1) and gate.group(1).startswith("function "):
            body = fns.get(_fn_path(gate.group(1).split()[1])) or []
            if any(re.match(r"^function \S+ with storage ", ln) or "cobbledollars" in ln for ln in body):
                fails.append("%s the short-take branch %s pays" % (w, gate.group(1).split()[1]))
        cd = [i for i, ln in enumerate(C) if re.match(r"^execute if score @s \S+ > #now \S+ run return", ln)]
        if not cd or cd[0] > ci:
            fails.append("%s the cooldown gate is missing or comes after the count" % w)
        before = [i for i, ln in enumerate(C) if ln == "execute store result score #before %s run cobbledollars query @s" % T]
        if not before or before[0] > ti:
            fails.append("%s the balance is not read before the take" % w)
        psets = [(i, ln) for i, ln in enumerate(C)
                 if re.search(r"\bscoreboard players (?:set|add|remove|reset|operation) #price ", ln)]
        lit = [(i, re.match(r"^scoreboard players set #price \S+ (\d+)$", ln)) for i, ln in psets]
        if len(lit) != 1 or lit[0][1] is None or lit[0][0] > ti:
            fails.append("%s #price is not set exactly once, unconditionally, to a literal before the take (%s)"
                         % (w, "; ".join(ln[:60] for _i, ln in psets) or "never set"))
            price = None
        else:
            price = int(lit[0][1].group(1))
        f, pi = _pay_tail_problems(w, C, ti, ("#price", T), fns)
        fails += f
        if pi is not None:
            between = [C[i] for i in range(ti + 2, pi) if re.search(r"\breturn\b", C[i])]
            if between:
                fails.append("%s a return between the take and the pay keeps the goods unpaid: %s" % (w, between[0][:80]))
        if pred.startswith("#"):
            items, ok = tag_members(files, jars, pred[1:])
        else:
            items, ok = {pred}, True
        crates[crate] = dict(pred=pred, n=n, price=price, items=items, resolved=ok, obj=T)
    # ---- sell everything
    allp = sell.get("all")
    specimens = {}
    if allp is None:
        fails.append("BUYER the pack has no sell/all function (E2: two ways to sell)")
        return fails, crates, specimens, notes
    C, w = fns[allp], "BUYER sell/all:"
    calls = [(i, ln.split()[1]) for i, ln in enumerate(C) if re.match(r"^function \S+$", ln)]
    T = next((c["obj"] for c in crates.values()), None) or "?"
    if not calls:
        fails.append("%s calls nothing" % w)
        return fails, crates, specimens, notes
    first = calls[0][0]
    cd = [i for i, ln in enumerate(C) if re.match(r"^execute if score @s \S+ > #now \S+ run return", ln)]
    if not cd or cd[0] > first:
        fails.append("%s the cooldown gate is missing or comes after the first take" % w)
    zero = [i for i, ln in enumerate(C) if ln == "scoreboard players set #total %s 0" % T]
    if not zero or zero[0] > first:
        fails.append("%s #total is not set to 0 before the first take" % w)
    before = [i for i, ln in enumerate(C) if ln == "execute store result score #before %s run cobbledollars query @s" % T]
    if not before or before[0] > first:
        fails.append("%s the balance is not read before the first take" % w)
    f, pi = _pay_tail_problems(w, C, first, ("#total", T), fns)
    fails += f
    if pi is not None:
        if any(i > pi for i, _f in calls):
            fails.append("%s a sale function is called after the pay" % w)
        for i in range(first, pi):
            if re.search(r"\breturn\b", C[i]) and not re.match(r"^execute if score #total \S+ matches \.\.0 run return",
                                                                 C[i]):
                fails.append("%s a return between the first take and the pay keeps goods unpaid: %s" % (w, C[i][:80]))
    called = {}
    for _i, fid in calls:
        called[fid] = called.get(fid, 0) + 1
    want = {re.sub(r"/sell/([a-z0-9_]+)$", r"/sellall/\1", _fid(sell[c])) for c in crates}
    spec_fid = next((fid for fid in called if fid.endswith("/sellall/specimens")), None)
    for fid in sorted(want):
        if called.get(fid, 0) != 1:
            fails.append("%s calls %s %d times; every category exactly once" % (w, fid, called.get(fid, 0)))
    for fid, k in sorted(called.items()):
        if fid not in want and fid != spec_fid:
            fails.append("%s calls %s, which is not a category's sell-all" % (w, fid))
        elif k != 1:
            fails.append("%s calls %s %d times" % (w, fid, k))
    for fid in sorted(called):
        body = fns.get(_fn_path(fid))
        if body is None:
            fails.append("%s calls %s, which the pack does not define" % (w, fid))
            continue
        if any(re.match(r"^function \S+ with storage \S+ pay$", ln) or "cobbledollars" in ln for ln in body):
            fails.append("%s %s pays or reads money itself (sell-all pays once, at the end)" % (w, fid))
        if fid == spec_fid:
            continue
        crate = fid.rsplit("/", 1)[1]
        cr = crates.get(crate)
        wc = "BUYER sellall/%s:" % crate
        sets = {}
        for ln in body:
            m = re.match(r"^scoreboard players set (#n|#price) \S+ (\d+)$", ln)
            if m:
                sets.setdefault(m.group(1), []).append(int(m.group(2)))
        if cr and (sets.get("#n") != [cr["n"]] or sets.get("#price") != [cr["price"]]):
            fails.append("%s sets #n %s and #price %s; the crate's own sale is %d for $%s"
                         % (wc, sets.get("#n"), sets.get("#price"), cr["n"], cr["price"]))
        cnt = [i for i, ln in enumerate(body) if re.match(r"^execute store result score #have \S+ run clear @s (\S+) 0$", ln)]
        mac = [(i, re.match(r"^function (\S+) with storage (\S+) (\S+)$", ln)) for i, ln in enumerate(body)]
        mac = [(i, m) for i, m in mac if m]
        reset = [i for i, ln in enumerate(body) if re.match(r"^scoreboard players set #took \S+ 0$", ln)]
        if len(cnt) != 1 or len(mac) != 1:
            fails.append("%s %d dry-run counts and %d take calls; exactly one of each" % (wc, len(cnt), len(mac)))
            continue
        ci, (mi, mm) = cnt[0], mac[0]
        cpred = re.match(r"^execute store result score #have \S+ run clear @s (\S+) 0$", body[ci]).group(1)
        tbody = fns.get(_fn_path(mm.group(1))) or files.get(_fn_path(mm.group(1))) or []
        tbody = [ln for ln in tbody if ln.strip() and not ln.strip().startswith("#")]
        tk = re.match(r"^\$execute store result score #took \S+ run clear @s (\S+) \$\(n\)$", tbody[0]) \
            if len(tbody) == 1 else None
        if tk is None:
            fails.append("%s the take %s is not ONE bounded macro take into #took" % (wc, mm.group(1)))
        elif cr and (tk.group(1) != cr["pred"] or cpred != cr["pred"]):
            fails.append("%s counts %s and takes %s; the crate's sale takes %s" % (wc, cpred, tk.group(1), cr["pred"]))
        if not reset or not (ci < reset[-1] < mi):
            fails.append("%s #took is not reset to 0 between the count and the take (a failed take would credit the last"
                         " sale's count)" % wc)
        nset = [i for i, ln in enumerate(body) if re.match(r"^execute store result storage %s %s\.n int 1 run scoreboard "
                                                          r"players get #take \S+$" % (re.escape(mm.group(2)),
                                                                                       re.escape(mm.group(3))), ln)]
        arith = ["#crates %s = #have", "#crates %s /= #n", "#take %s = #crates", "#take %s *= #n"]
        pos = [next((i for i, ln in enumerate(body) if ln.startswith("scoreboard players operation " + a % T)), None)
               for a in arith]
        if None in pos or pos != sorted(pos) or not nset or not (ci < pos[0] and pos[-1] < nset[0] < mi):
            fails.append("%s the bounded take is not whole crates of what was counted (#have / #n x #n)" % wc)
        credit = ["#part %s = #price" % T, "#part %s *= #took" % T, "#part %s /= #n" % T, "#total %s += #part" % T]
        cpos = [next((i for i, ln in enumerate(body) if ln.startswith("scoreboard players operation " + a)), None)
                for a in credit]
        mult = [ln for ln in body if re.match(r"^scoreboard players operation #part \S+ \*= ", ln)]
        if None in cpos or cpos != sorted(cpos) or cpos[0] < mi or len(mult) != 1:
            fails.append("%s the credit is not #price x #took / #n after the take, added once to #total (%s)"
                         % (wc, "; ".join(mult) or "no multiplier"))
        if any(re.search(r"\breturn\b", body[i]) for i in range(mi, len(body))):
            fails.append("%s a return after the take can leave what it took uncredited" % wc)
    if spec_fid:
        body = fns.get(_fn_path(spec_fid)) or []
        price, reset = None, False
        for i, ln in enumerate(body):
            m = re.match(r"^scoreboard players set #price \S+ (\d+)$", ln)
            if m:
                price, reset = int(m.group(1)), False
                continue
            if re.match(r"^scoreboard players set #took \S+ 0$", ln):
                reset = True
                continue
            m = _STORE.match(ln)
            if m:
                item = m.group(3)
                ok = (m.group(1) == "#took" and reset and price is not None and i + 3 < len(body)
                      and body[i + 1] == "scoreboard players operation #part %s = #took %s" % (T, T)
                      and body[i + 2] == "scoreboard players operation #part %s *= #price %s" % (T, T)
                      and body[i + 3] == "scoreboard players operation #total %s += #part %s" % (T, T))
                if not ok:
                    fails.append("BUYER specimens %s: not a reset #took, a literal #price and a credit of #took x #price "
                                 "added once to #total" % item)
                if item in specimens:
                    fails.append("BUYER specimens %s is taken twice (at $%s and $%s)" % (item, specimens[item], price))
                specimens[item] = price
                price, reset = None, False
    else:
        notes.append("BUYER sell/all calls no specimen function: no specimen is bought")
    return fails, crates, specimens, notes


def cheapest_fixed_point(sales, conversions, cap=TP_ROUNDS):
    """(cheapest(), converged): cheapest() run until a round changes nothing. A cap reached is reported, not trusted."""
    best = cheapest(sales, [], rounds=0)
    for _ in range(cap):
        if not cheapest_round(best, conversions):
            return best, True
    return best, False


def buyer_checks(files, best, jars=None, expected=None, bank_prices=None, best_proposal=None, unsited=(),
                 converged=True, units_out=None, wandering=None):
    """(failures, reports) for the Trading Post (A4). `best` is the least money that obtains each item through every
    sited seller, every jar recipe and every PLACED barter edge (cheapest_fixed_point); `best_proposal` adds the proposal
    lines. `expected` is tp_expected()'s ({crate: (count, price)}, {specimen: price}) from the record and the bank, or
    None (a hand-written pack).

    FAILURE: any order property of tp_read; a crate or specimen whose emitted count or price is not the spine's
    (A1, exact: no rounding slack beyond the whole dollar the rule itself names); a crate or specimen in the record and
    not in the pack or the reverse; a crate whose predicate cannot be enumerated; ARBITRAGE when any item a sale
    accepts (every member of its tag, mod members included) is obtainable with money for LESS than the unit the post
    pays; a top-tier item or input sold; emerald obtainable with money while the wandering trader (WANDERING_TRADER)
    sells a Trading Post good for emeralds. REPORT: break-even (equal), the margin of every crate, unsited sellers
    under a unit, an item the Bank also buys."""
    fails, crates, specimens, notes = tp_read(files, jars)
    reps = list(notes)
    if not converged:
        fails.append("BUYER the money-cost search did not reach a fixed point in %d rounds: the arbitrage below is not "
                     "proved" % TP_ROUNDS)
    if expected is not None:
        ecr, esp = expected
        for cid in sorted(set(ecr) | set(crates)):
            if cid not in crates:
                fails.append("BUYER %s: the record's crate has no readable sell function in the pack" % cid)
                continue
            if cid not in ecr:
                fails.append("BUYER %s: the pack sells a crate the record does not declare" % cid)
                continue
            n, price, items = ecr[cid]
            got = crates[cid]
            if got["n"] != n or got["price"] != price:
                fails.append("BUYER SPINE %s: the pack takes %d for $%s; count x W(tier) / rate is %d for $%s"
                             % (cid, got["n"], got["price"], n, price))
            if got["resolved"] and items - got["items"]:
                reps.append("buyer %s: the record lists %d item(s) the pack's predicate does not accept: %s"
                            % (cid, len(items - got["items"]), ", ".join(sorted(items - got["items"])[:6])))
            if got["resolved"] and got["items"] - items:
                reps.append("buyer %s: the predicate %s accepts %d item(s) the record does not list (priced below like "
                            "the rest): %s" % (cid, got["pred"], len(got["items"] - items),
                                               ", ".join(sorted(got["items"] - items)[:12])))
        for item in sorted(set(esp) | set(specimens)):
            want, got = esp.get(item, "absent"), specimens.get(item, "absent")
            if want is None:
                fails.append("BUYER SPINE specimen %s: no live dropper in the notes, so no derivable price" % item)
            elif want != got:
                fails.append("BUYER SPINE specimen %s: the pack pays $%s a piece; the spine's is $%s" % (item, got, want))
    # ---- what each item is worth to the post: the highest unit any channel pays (two crates are the exploit's choice)
    unit, src = {}, {}
    for cid, c in sorted(crates.items()):
        if not c["resolved"]:
            (fails if jars is not None else reps).append(
                "BUYER %s: the predicate %s cannot be enumerated%s: its members are not priced"
                % (cid, c["pred"], "" if jars is not None else " without the jars (a PARTIAL run)"))
        if c["price"] is None or not c["n"]:
            continue
        for i in c["items"]:
            u = Fraction(c["price"], c["n"])
            if u > unit.get(i, Fraction(-1)):
                unit[i], src[i] = u, "crate %s (%d for $%d)" % (cid, c["n"], c["price"])
    for i, p in specimens.items():
        if p is not None and Fraction(p) > unit.get(i, Fraction(-1)):
            unit[i], src[i] = Fraction(p), "specimen at $%d a piece" % p
    if units_out is not None:
        units_out.update(unit)
    tops = set(TOP_TIER) | set(TOP_TIER_INPUTS)
    for i in sorted(set(unit) & tops):
        fails.append("BUYER TOP TIER %s is bought by the Trading Post (%s): a top-tier good sold back is a money line"
                     % (i, src[i]))
    tight = []
    for i in sorted(unit):
        u = unit[i]
        got = best.get(i)
        if got is not None and u:
            tight.append((got[0] / float(u), i))
        if got is not None and got[0] < float(u) - 1e-9:
            fails.append("BUYER ARBITRAGE %s: money obtains one for $%.4f and the Trading Post pays $%.4f (%s), $%.4f a "
                         "unit, no cap -- %s" % (i, got[0], u, src[i], float(u) - got[0], chain(best, i)))
        elif got is not None and abs(got[0] - float(u)) <= 1e-9:
            reps.append("buyer break-even %s: money obtains one for exactly the $%.4f the post pays (%s)" % (i, u, src[i]))
        elif best_proposal is not None and i in best_proposal and best_proposal[i][0] < float(u) - 1e-9:
            fails.append("BUYER ARBITRAGE (proposal) %s: once the proposed barter lines go live money obtains one for "
                         "$%.4f against the post's $%.4f (%s) -- %s" % (i, best_proposal[i][0], u, src[i],
                                                                         chain(best_proposal, i)))
        for s in unsited:
            if s.item == i and not s.sited and s.unit < float(u) - 1e-9:
                reps.append("buyer LATENT %s: %s sells it at $%g, under the post's $%.4f; a loop the day it is sited"
                            % (i, s.where, s.unit, u))
        if bank_prices and i in bank_prices:
            reps.append("buyer two channels %s: the Bank pays $%d and the post $%.4f (%s)" % (i, bank_prices[i], u, src[i]))
    # the wandering trader: `wandering` is the money cost with every WANDERING_TRADER item FREE (its emerald price and
    # count are not stated here), so a post good it reaches -- directly or through a recipe -- has no provable margin
    if wandering is not None:
        wt = sorted(i for i in unit if i in wandering and wandering[i][0] < float(unit[i]) - 1e-9)
    else:
        wt = sorted(set(WANDERING_TRADER) & set(unit))
    if "minecraft:emerald" in best and wt:
        fails.append("BUYER emerald has a dollar path ($%.2f: %s) and the wandering trader's offers reach %s; no offer "
                     "count is stated here, so no margin can be shown" % (best["minecraft:emerald"][0],
                                                                          best["minecraft:emerald"][1], ", ".join(wt)))
    elif wt:
        reps.append("buyer: emerald has no dollar path, so the %d Trading Post goods the wandering trader's offers reach "
                    "(directly or by a recipe) are outside money: %s" % (len(wt), ", ".join(wt)))
    for cid, c in sorted(crates.items()):
        rows = sorted((best[i][0] / float(Fraction(c["price"], c["n"])), i) for i in c["items"] if i in best) \
            if c["price"] else []
        reps.append("buyer %s: %d for $%s ($%.4f a unit), %d item(s) accepted; %s" % (
            cid, c["n"], c["price"], float(Fraction(c["price"] or 0, c["n"] or 1)), len(c["items"]),
            "cheapest by money %s at %.2fx the unit (%s)" % (rows[0][1], rows[0][0], best[rows[0][1]][1])
            if rows else "no member is obtainable with money"))
    if tight:
        r, i = min(tight)
        reps.append("buyer tightest margin: %s, money cost %.2fx what the post pays (%s); %d of %d priced items have a "
                    "money path" % (i, float(r), src[i], len(tight), len(unit)))
    return fails, reps


def tp_ranch_report(jars, units, server_dir=None, notes=None, wage=None):
    """REPORT what a pastured Pokemon earns at the Trading Post unattended (E3 allows it; information for the owner,
    never a FAILURE): drops an hour = 60 x drop_chance_per_minute x 1200 / tick_per_minute (PastureLoot.json); per drop
    each entry pays its expected picks (expected_picks: Cobblemon's own roll) x its mean quantity x the post's unit,
    over every entry the pasture blacklist does not name. `notes` (docs/research/notes/drops-1.8.0.json, RELAYED)
    marks which species spawn in our world; the jars' tables (the server's Cobblemon) are the drops."""
    pl, _src = pasture_config(server_dir)
    per_hour = 60.0 * float(pl.get("drop_chance_per_minute", 0)) * 1200.0 / float(pl.get("tick_per_minute", 1200) or 1200)
    limit = None
    if server_dir and (Path(server_dir) / "config" / "cobblemon" / "main.json").is_file():
        limit = read_json(Path(server_dir) / "config" / "cobblemon" / "main.json").get("defaultPasturedPokemonLimit")
    black = set(pl.get("item_blacklist") or [])
    live = set()
    for _item, rec in ((notes or {}).get("items") or {}).items():
        for d in rec.get("droppers") or []:
            if len(d) > 4 and d[4]:
                live.add(d[0])
    rows = {}
    for _w, sid, d in jars.species:
        ents = [e for e in d.get("entries") or [] if isinstance(e, dict)]
        picks = expected_picks(d)
        money, parts = 0.0, []
        for pk, e in zip(picks, ents):
            it = e.get("item")
            if it in units and it not in black and pk > 0:
                v = pk * _qty(e) * float(units[it])
                money += v
                parts.append((v, it))
        if money > 0:
            name = sid.rsplit("/", 1)[-1]
            rows[name] = (money * per_hour, name, ", ".join(i.split(":")[1] for _v, i in sorted(parts, reverse=True)[:3]))
    reps = []
    if not rows:
        return ["buyer ranch: no pastured species drops a Trading Post good"]
    ranked = sorted(rows.values(), reverse=True)
    lv = [r for r in ranked if r[1] in live]
    reps.append("buyer ranch: %.1f drops an hour per pastured Pokemon (PastureLoot.json); %d species drop a Trading Post "
                "good, %d of them spawn in our world (the drops note, RELAYED)" % (per_hour, len(ranked), len(lv)))
    for tag, rs in (("any species", ranked[:5]), ("live species", lv[:5])):
        for money, name, what in rs:
            reps.append("buyer ranch (%s) %s: $%.0f an hour per pastured Pokemon (%s)%s" % (
                tag, name, money, what, "; a pasture of %d: $%.0f an hour" % (limit, money * limit) if limit else ""))
    if wage:
        reps.append("buyer ranch against the hand wage: W(early) is $%.0f an hour; the best live species pastured %s "
                    "earns $%.0f an hour unattended" % (float(wage), "%d deep" % limit if limit else "alone",
                                                        lv[0][0] * (limit or 1) if lv else 0))
    return reps


# ------------------------------------------------------------------------------------------------ barter
MONEY = "$"
BARTER_ROUNDS = 16
# ---- ECONOMY_V2 (docs/mechanics/ECONOMY_V2.md; the owner's answers, section 7, 2026-10-13). Stated HERE from the design,
# never read from data/bank.json exchanges.barter_only or tools/bank.py (the builder's list and checks).
P_DOLLARS = 100             # 1.1: 1 P = $100 (the owner's E11: the unit field is worth_p)
# 2.4 + E4 + E5: the top tier has no dollar line; it is bought at the Station Exchange with what dollars cannot buy
TOP_TIER = ("cobblemon:master_ball", "cobblemon:ability_capsule", "cobblemon:focus_sash", "cobblemon:expert_belt",
            "cobblemon:eviolite", "cobblemon:assault_vest", "cobblemon:choice_specs", "cobblemon:destiny_knot")
# 3.3 and 5.2 A3: the inputs no dollar may reach (each top-tier barter line's own inputs are added to these)
TOP_TIER_INPUTS = ("minecraft:ancient_debris", "minecraft:netherite_scrap", "minecraft:netherite_ingot",
                   "minecraft:netherite_block", "minecraft:diamond", "minecraft:diamond_block")
# E4: the Master Ball's worth on the spine is "about 2 netherite ingots" ("30 is too steep, it should be more
# accessible"), valued at the Bank's own ingot price (1.1: the minerals are already on the spine)
OWNER_SPINE = {"cobblemon:master_ball": (("minecraft:netherite_ingot", 2),
                                         "the owner's E4 (ECONOMY_V2.md section 7): 'about 2 netherite ingots'")}
# 2 and 5.2 A2: a bank entry's upper hour at the $1 unit floor is at most this many times its opening leg's fight hour
UNIT_FLOOR_FACTOR = 1.5
# 2.2's ESTIMATE rates per hour (and tier) for the bulk and renewable goods v2 sends to the Trading Post. A2 applies
# them to any bank entry that declares no rate of its own, so a bulk block that drifts into the Bank (a base entry
# un-removed, a generator change) is judged rather than skipped. Wood and crops are below the floor at these rates;
# the AFK rule, not A2, keeps them out.
BULK_RATES = dict(
    [(i, (3300, "early")) for i in ("minecraft:cobblestone", "minecraft:cobbled_deepslate", "minecraft:stone",
                                    "minecraft:andesite", "minecraft:diorite", "minecraft:granite", "minecraft:tuff",
                                    "minecraft:dirt", "minecraft:sand", "minecraft:red_sand", "minecraft:gravel")]
    + [(i, (15000, "nether")) for i in ("minecraft:netherrack", "minecraft:blackstone", "minecraft:basalt",
                                        "minecraft:soul_sand")]
    + [(i, (2000, "early")) for i in ("minecraft:melon_slice", "minecraft:dried_kelp", "minecraft:sugar_cane",
                                      "minecraft:bamboo", "minecraft:cactus")]
    + [("cobblemon:relic_coin", (2000, "early")), ("minecraft:wheat", (1000, "early")),
       ("minecraft:nether_wart", (1000, "nether"))])
# Vanilla 1.21.1's wandering trader, every offer priced in emeralds (WanderingTraderTrades: code, not JSON, so this
# is a STATED table from vanilla knowledge, ASSUMED until read from the jar; 1.21.2+ reworked it). A3 adds each as an
# emerald -> item edge, so a dollar path through a bought emerald is followed.
WANDERING_TRADER = (
    "minecraft:sea_pickle", "minecraft:slime_ball", "minecraft:glowstone", "minecraft:nautilus_shell", "minecraft:fern",
    "minecraft:sugar_cane", "minecraft:pumpkin", "minecraft:kelp", "minecraft:cactus", "minecraft:dandelion",
    "minecraft:poppy", "minecraft:blue_orchid", "minecraft:allium", "minecraft:azure_bluet", "minecraft:red_tulip",
    "minecraft:orange_tulip", "minecraft:white_tulip", "minecraft:pink_tulip", "minecraft:oxeye_daisy",
    "minecraft:cornflower", "minecraft:lily_of_the_valley", "minecraft:wheat_seeds", "minecraft:beetroot_seeds",
    "minecraft:pumpkin_seeds", "minecraft:melon_seeds", "minecraft:acacia_sapling", "minecraft:birch_sapling",
    "minecraft:dark_oak_sapling", "minecraft:jungle_sapling", "minecraft:oak_sapling", "minecraft:spruce_sapling",
    "minecraft:cherry_sapling", "minecraft:mangrove_propagule", "minecraft:red_dye", "minecraft:white_dye",
    "minecraft:blue_dye", "minecraft:pink_dye", "minecraft:black_dye", "minecraft:green_dye", "minecraft:light_gray_dye",
    "minecraft:magenta_dye", "minecraft:yellow_dye", "minecraft:gray_dye", "minecraft:purple_dye",
    "minecraft:light_blue_dye", "minecraft:lime_dye", "minecraft:orange_dye", "minecraft:brown_dye", "minecraft:cyan_dye",
    "minecraft:brain_coral_block", "minecraft:bubble_coral_block", "minecraft:fire_coral_block",
    "minecraft:horn_coral_block", "minecraft:tube_coral_block", "minecraft:vine", "minecraft:brown_mushroom",
    "minecraft:red_mushroom", "minecraft:lily_pad", "minecraft:small_dripleaf", "minecraft:sand", "minecraft:red_sand",
    "minecraft:pointed_dripstone", "minecraft:rooted_dirt", "minecraft:moss_block", "minecraft:tropical_fish_bucket",
    "minecraft:pufferfish_bucket", "minecraft:packed_ice", "minecraft:blue_ice", "minecraft:gunpowder",
    "minecraft:podzol")
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


def barter_checks(sales, conversions, bank_prices, best, doc=None, dt_mod=None, edges_out=None):
    """(failures, reports, notes) for the barter edges. `edges_out`, a list, receives every edge audited: the emitted
    villagers' offers and the proposal lines."""
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
    if edges_out is not None:
        edges_out += placed + proposal
    seeds ={MONEY} | {i for b in placed + proposal for i, _n in b.pays} | {b.gets[0] for b in placed + proposal}
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
    # a reference line is a money line as it stood: since ECONOMY_V2 (E5) the top tier's lines sit in superseded_stock
    counter = {(c["id"], s.get("id")): float(s["price"]) for c in md.get("counters") or []
               for s in (c.get("stock") or []) + (c.get("superseded_stock") or [])}
    ref_by_out = {}
    for ln in doc.get("lines") or []:
        ref = ln.get("reference") or {}
        out_id = (ln.get("sell") or {}).get("id")
        try:
            if ref.get("lines"):
                ref_by_out[out_id] = (sum(counter[(ref["counter"], lid)] for lid in ref["lines"]),
                                      "the money line(s) %s as they stood" % "+".join(ref["lines"]))
            elif ref.get("bank"):
                ref_by_out[out_id] = (sum(int(r.get("count", 1)) * bank_prices[r["item"]] for r in ref["bank"]),
                                      "the spine: %s at the Bank" % " + ".join("%d x %s" % (int(r.get("count", 1)),
                                                                                        r["item"]) for r in ref["bank"]))
        except (KeyError, TypeError, AttributeError):
            pass
    for out_id, ((item, n), why) in OWNER_SPINE.items():
        if item not in bank_prices:
            continue
        own = (n * float(bank_prices[item]), "the spine: %d x %s at the Bank, %s" % (n, item, why))
        if out_id in ref_by_out and abs(ref_by_out[out_id][0] - own[0]) > 1e-6:
            reps.append("barter spine %s: the data's reference is $%.0f (%s); the owner's is $%.0f, and is the one "
                        "used" % (out_id, ref_by_out[out_id][0], ref_by_out[out_id][1], own[0]))
        ref_by_out[out_id] = own
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
            price, how = ref_by_out[out][0] * cnt, ref_by_out[out][1]
        else:
            price, how = None, None
        if unknown:
            reps.append("barter value (%s) %s: NOT DERIVABLE, no value for %s" % (b.group, b.id, ", ".join(unknown)))
            if b.group == "placed" and out in TOP_TIER:
                fails.append("BARTER UNVALUED (placed) %s: no value for %s, so the line cannot be shown not to be a "
                             "bypass" % (b.id, ", ".join(unknown)))
        elif price is None:
            reps.append("barter value (%s) %s: inputs worth $%.0f; the output has no money price to compare"
                        % (b.group, b.id, vals))
            if b.group == "placed" and out in TOP_TIER:
                fails.append("BARTER UNVALUED (placed) %s: inputs worth $%.0f and no money line, reference or spine "
                             "worth for %s to hold them against" % (b.id, vals, out))
        else:
            reps.append("barter value (%s) %s: inputs worth $%.0f (%.2f P) against $%.0f (%.2f P, %s): %.3f"
                        % (b.group, b.id, vals, vals / P_DOLLARS, price, price / P_DOLLARS, how,
                           vals / price if price else float("inf")))
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


# ------------------------------------------------------------------------------------------------ ECONOMY_V2
def money_reach(sales, conversions):
    """{item: (how, [inputs])}: every item dollars can obtain. Any seller's offer (sited or not: an unsited line is a
    dollar path the day it is sited), closed under every conversion whose every input slot dollars can fill. Pure
    reachability: no prices, so no rounding, and no round limit (it runs to a fixed point)."""
    reach = {}
    for s in sorted(sales, key=lambda s: (not s.sited, s.unit)):
        if s.item not in reach:
            reach[s.item] = ("buy at %s for $%g%s" % (s.where, s.unit, "" if s.sited else " (UNSITED)"), [])
    changed = True
    while changed:
        changed = False
        for name, kind, ings, rid, _rcount in conversions:
            if rid in reach:
                continue
            picks = []
            for acc, _n in ings:
                hit = next((i for i in sorted(acc) if i in reach), None)
                if hit is None:
                    break
                picks.append(hit)
            else:
                reach[rid] = ("%s %s from %s" % (kind, name, " + ".join(picks)), picks)
                changed = True
    return reach


def reach_chain(reach, item, depth=0):
    how, picks = reach[item]
    text = "%s: %s" % (item, how)
    if depth < 4:
        for p in picks:
            if p != item:
                text += " | " + reach_chain(reach, p, depth + 1)
    return text


def top_tier_checks(sales, conversions, edges, wandering=WANDERING_TRADER):
    """(failures, reports): ECONOMY_V2 5.2 A3. No dollar reaches a top-tier output (TOP_TIER) or any of its inputs
    (TOP_TIER_INPUTS and every input of a barter line selling one), through every seller (counters, stalls, the
    Marts' template shops, the default shop, sited or not), every recipe in the jars, every barter edge (placed,
    proposed and experiment) and the vanilla wandering trader's emerald offers. The Bank only buys, so it adds no
    edge from dollars; the Produce Buyer pays dollars only. FAILURE for each one reached, with the path."""
    fails, reps = [], []
    inputs = set(TOP_TIER_INPUTS)
    for b in edges:
        if not b.experiment and b.gets and b.gets[0] in TOP_TIER:
            inputs |= {i for i, _n in b.pays}
    wt = [("wandering_trader:%s" % i.split(":", 1)[1], "wandering trader offer (vanilla 1.21.1, STATED)",
           [({"minecraft:emerald"}, 1)], i, 1) for i in wandering]
    reach = money_reach(sales, list(conversions) + [b.conversion() for b in edges] + wt)
    for kind, items in (("OUTPUT", TOP_TIER), ("INPUT", sorted(inputs - set(TOP_TIER)))):
        for item in items:
            if item in reach:
                fails.append("TOP TIER %s %s has a dollar path: %s" % (kind, item, reach_chain(reach, item)))
    barterable = {b.gets[0] for b in edges if not b.experiment and b.group == "placed" and b.gets}
    for item in TOP_TIER:
        if item not in barterable:
            reps.append("top tier %s: no placed barter line sells it, so it has no route at all" % item)
    reps.append("top tier: %d outputs and %d inputs checked against %d seller offers, %d recipes, %d barter edges and "
                "%d wandering-trader offers; emerald is %s" % (
                    len(TOP_TIER), len(inputs - set(TOP_TIER)), len(sales), len(conversions), len(edges), len(wt),
                    "reachable from dollars (%s)" % reach["minecraft:emerald"][0] if "minecraft:emerald" in reach
                    else "not reachable from dollars"))
    return fails, reps


def fight_hours(markets_doc, bank_doc):
    """{leg: the leg's fight hour}: data/markets.json income_basis.leg_by_badge / data/bank.json max_leg_hours (both
    the only sources there are: an expectation and an ASSUMPTION, labelled so there)."""
    legs = (markets_doc.get("income_basis") or {}).get("leg_by_badge") or {}
    H = float((bank_doc.get("effort_model") or {}).get("max_leg_hours") or 0)
    if H <= 0:
        raise AuditError("data/bank.json effort_model.max_leg_hours is missing or not positive")
    return {int(k): float(v) / H for k, v in legs.items()}


def opening_legs(bank_doc, gate_doc):
    """{tier: the leg it opens in}. early: leg 1 (the Bank opens at every merchant in every town, ECONOMY_V2 1.2);
    nether: the leg after the Nether gate's gym (data/nether_gate.json gate_flag, MEASURED there), never the bank's own
    claim; deep: data/bank.json's opens_leg, which has no other source."""
    tiers = (bank_doc.get("effort_model") or {}).get("tiers") or {}
    out = {"early": 1, "deep": int((tiers.get("deep") or {}).get("opens_leg") or 1)}
    m = re.search(r"gym(\d+)_cleared", str(gate_doc.get("gate_flag") or ""))
    out["nether"] = int(m.group(1)) if m else 8
    return out


def bank_v2_checks(entries, bank_doc, markets_doc, gate_doc):
    """(failures, reports): ECONOMY_V2 5.2 A5 and A2 on the bank the player reaches (tools/bank.py's output, base
    entries included).
      A5 NAMESPACE: FAILURE for any cobblemon: id (R-V2-3).
      A2 UNIT FLOOR: an entry's rate (data/bank.json rate_per_hour_upper, else rate_per_hour; else BULK_RATES, the
         design's estimate) x $1 must be at most UNIT_FLOOR_FACTOR x the fight hour of the leg its tier opens. An entry
         with no rate from either source is REPORTED, never passed silently. A crafted entry (declared rate 0) is
         judged by its inputs' rows, not its own."""
    fails, reps = [], []
    for e in entries:
        if str(e["item"]).startswith("cobblemon:"):
            fails.append("NAMESPACE %s is in the Bank at $%s: no cobblemon: item is bankable (ECONOMY_V2 R-V2-3)"
                         % (e["item"], e["price"]))
    fh = fight_hours(markets_doc, bank_doc)
    legs = opening_legs(bank_doc, gate_doc)
    claimed = ((bank_doc.get("effort_model") or {}).get("tiers") or {}).get("nether", {}).get("opens_leg")
    if claimed is not None and int(claimed) != legs["nether"]:
        reps.append("unit floor: data/bank.json says the nether tier opens at leg %s; the gate says leg %d (used)"
                    % (claimed, legs["nether"]))
    declared = {b["item"]: b for b in bank_doc.get("buys") or []}
    for e in sorted({e["item"]: e for e in entries}.values(), key=lambda e: e["item"]):
        item = e["item"]
        b = declared.get(item)
        if b is not None:
            rate = float(b.get("rate_per_hour_upper") or b.get("rate_per_hour") or 0)
            tier, src = b.get("tier"), "data/bank.json"
            if rate == 0:
                continue                      # crafted or smelted: its raw input carries the rate
        elif item in BULK_RATES:
            rate, tier = BULK_RATES[item]
            src = "ECONOMY_V2 2.2 (ESTIMATE)"
        else:
            reps.append("unit floor %s: no rate declared or stated, so A2 cannot judge it" % item)
            continue
        leg = legs.get(tier)
        if leg not in fh:
            reps.append("unit floor %s: tier %r opens at no leg with a fight hour" % (item, tier))
            continue
        cap = UNIT_FLOOR_FACTOR * fh[leg]
        if rate > cap:
            fails.append("UNIT FLOOR %s: %g an hour (%s) at the $1 floor pays $%.0f an hour, over %g x the leg-%d fight "
                         "hour ($%.0f): not bankable" % (item, rate, src, rate, UNIT_FLOOR_FACTOR, leg, cap))
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


_CALL = re.compile(r"(?:^|\brun\s+)function\s+(\S+)\s*$")


def _chain_texts(fn_text, entry):
    """{function: text} reached from entry by `function` and `schedule function` lines, entry included."""
    out, todo = {}, [entry]
    while todo:
        name = todo.pop()
        if name in out:
            continue
        text = fn_text(name)
        if text is None:
            continue
        out[name] = text
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#"):
                continue
            todo += [m.group(1) for m in (_CALL.search(line), _SCHEDULE.search(line)) if m]
    return out


def _forceload_boxes(text, verb):
    """[(cx0, cz0, cx1, cz1)] chunk boxes of a function's own `forceload <verb>` lines."""
    out = []
    for line in text.splitlines():
        m = _FORCELOAD.match(line.strip())
        if m and m.group(1) == verb:
            x0, z0 = int(m.group(2)), int(m.group(3))
            x1, z1 = (int(m.group(4)), int(m.group(5))) if m.group(4) else (x0, z0)
            out.append((min(x0, x1) >> 4, min(z0, z1) >> 4, max(x0, x1) >> 4, max(z0, z1) >> 4))
    return out


def forceload_checks(files, steps, step_id="R18DT"):
    """Failures: a step runs a function that touches a chunk no forceload holds at that moment, or removes the hold
    before a function the run scheduled has had its ticks. A function's chunks are those of every function its run
    reaches (calls and schedules, followed), and a forceload the chain adds itself holds them as a step's would.
    Read from the emitted functions and the step list (the
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
            # the whole chain the function starts (N155: tools/chunk_look.py's look-then-act chains do their block work
            # in a function a look calls, ticks later), and the boxes the chain force-loads itself, which hold its
            # chunks for its life (tools/chunk_look_audit.py proves a chain releases them only at its end)
            chain = _chain_texts(fn_text, v)
            own = [b for t in chain.values() for b in _forceload_boxes(t, "add")]
            for fname, ftext in sorted(chain.items()):
                for ch, (x, z) in sorted(touched_chunks(ftext).items()):
                    if not covered(ch) and not any(a <= ch[0] <= c and b <= ch[1] <= d for a, b, c, d in own):
                        fails.append("FORCELOAD %s runs %s, which touches chunk %s at (%d, %d): no forceload holds it%s"
                                     % (step_id, v, ch, x, z, "" if fname == v else " (in %s)" % fname))
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
          direct_trades_mod=None, direct_trades_doc=None, produce_buyer_mod=None, mods_dir=None):
    """(failures, reports, notes). `mods_dir` replaces the server snapshot's mods/ (default_mods_dir())."""
    fails, reps, notes = [], [], []
    bank_doc = read_json(DATA / "bank.json")
    markets_doc = read_json(DATA / "markets.json")
    trader_doc = read_json(DATA / "traders.json")
    progression = read_json(DATA / "progression.json")
    routes_doc = read_json(DATA / "routes.json")
    towns_doc = read_json(DATA / "towns.json")

    emitted = bank_entries_emitted(bank_mod)
    import bank as _bank_tool  # reads either CobbleDollars form (Beta-6 writes a bare list)
    committed = _bank_tool.committed_entries(COMMITTED_BANK)
    emitted = [{"item": e["item"], "price": int(e["price"])} for e in emitted]
    if emitted != committed:
        diff = sorted({e["item"] for e in emitted} ^ {e["item"] for e in committed}
                      | {a["item"] for a, b in zip(emitted, committed) if a != b})
        fails.append("STALE BANK: modpack/config/cobbledollars/default_bank.json is not tools/bank.py's output (%d entries vs "
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
        jars = load_jars(str(server_dir), str(vanilla_jar), str(mods_dir) if mods_dir else None)
        conversions = jars.conversions()
        notes.append("mods read from %s" % (mods_dir or Path(server_dir) / "mods"))
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
    edges = []
    f, r, n = barter_checks(sales, conversions, bank_prices, best, doc=direct_trades_doc, dt_mod=direct_trades_mod,
                            edges_out=edges)
    fails += f
    reps += r
    notes += n
    f, r = top_tier_checks(sales, conversions, edges)
    fails += f
    reps += r
    f, r = bank_v2_checks(emitted + [e for e in committed if e not in emitted], bank_doc, markets_doc,
                          read_json(DATA / "nether_gate.json"))
    fails += f
    reps += r

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
    # the Trading Post (A4): every sited seller, every jar recipe and every barter edge, run to a fixed point
    pb_doc = read_json(DATA / "produce_buyer.json")
    pb_notes = read_json(ROOT / pb_doc["specimens"]["notes_file"]) if (pb_doc.get("specimens") or {}).get("notes_file") \
        else {}
    wages = bank_tier_wages(bank_doc)
    placed = [b.conversion() for b in edges if b.group == "placed"]
    proposal = [b.conversion() for b in edges if b.group != "placed"]
    best_tp, ok1 = cheapest_fixed_point(sales, conversions + placed)
    best_tp_all, ok2 = cheapest_fixed_point(sales, conversions + placed + proposal) if proposal else (None, True)
    free = [Sale("the wandering trader (its emerald offers taken as free)", None, i, 0.0, False) for i in WANDERING_TRADER]
    best_wt, ok3 = cheapest_fixed_point(sales + free, conversions + placed)
    units = {}
    try:
        files = buyer_emitted(produce_buyer_mod)
    except Exception as exc:                       # the generator refusing its data is itself the finding
        fails.append("BUYER the generator emitted nothing: %s" % str(exc).splitlines()[0][:200])
        files = None
    if files is not None:
        f, r = buyer_checks(files, best_tp, jars if conversions else None, tp_expected(pb_doc, wages, pb_notes),
                            bank_prices, best_tp_all, [s for s in sales if not s.sited], ok1 and ok2 and ok3, units,
                            best_wt)
        fails += f
        reps += r
        notes.append("trading post: %d priced items against %d sale offers, %d recipes and %d barter edges, W(tier) %s "
                     "summed from data/bank.json" % (len(units), sum(1 for s in sales if s.sited), len(conversions),
                                                     len(placed) + len(proposal),
                                                     ", ".join("%s $%s" % (k, float(v)) for k, v in sorted(wages.items()))))
        if conversions:
            reps += tp_ranch_report(jars, units, sd, pb_notes, wages.get("early"))
    return fails, reps, notes


def default_server_dir():
    return os.environ.get("COBBLERS_SNAPSHOT_DIR") or (DEFAULT_SNAPSHOT if Path(DEFAULT_SNAPSHOT).is_dir() else None)


def default_mods_dir():
    return os.environ.get("COBBLERS_MODS_DIR") or (DEFAULT_MODS if Path(DEFAULT_MODS).is_dir() else None)


def default_vanilla_jar():
    return os.environ.get("COBBLERS_VANILLA_JAR") or (DEFAULT_VANILLA if Path(DEFAULT_VANILLA).is_file() else None)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server-dir", default=default_server_dir(),
                   help="an OFFLINE server snapshot (mods/, datapacks/); never the live server")
    p.add_argument("--vanilla-jar", default=default_vanilla_jar())
    p.add_argument("--mods-dir", default=default_mods_dir(),
                   help="a folder of the server's mod jars, read instead of the snapshot's mods/ (default: "
                        "COBBLERS_MODS_DIR, else %s when it exists)" % DEFAULT_MODS)
    p.add_argument("--no-jars", action="store_true")
    a = p.parse_args(argv)
    fails, reps, notes = audit(a.server_dir, a.vanilla_jar, use_jars=not a.no_jars, mods_dir=a.mods_dir)
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
