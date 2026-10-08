#!/usr/bin/env python
"""Independent audit of the town markets: data/markets.json, the generated pack cobblers_markets, the keepers R17M
places, and the recipe overlay modpack/config/sophisticatedcore-common.toml.

Written by an agent that did not build the markets, against docs/mechanics/TIERED_GOODS.md section 4 (A-1..A-5).
NOTHING here is imported from tools/markets.py or derived with its helpers: every expectation comes from a design
document, a data file another system owns, or the server's jars, and the generated pack is read as files.

  where each expectation comes from
    ids        the server's jars: an item exists when a jar's assets/<ns>/lang/en_us.json carries item.<ns>.<path> or
               block.<ns>.<path> (nested META-INF/jars too), or when it has both an item model and an item-tag entry
               (TMCraft's code-named TMs; see JarIndex)
    gates      the badge a town's gym awards: data/progression.json's gymN_cleared flags name their town
               (waystone.town), data/towns.json orders the gym towns. A critical-path shelf is gated on its own town's
               badge (PROGRESSION_LADDER.md 1.1 "Flag" column); an off-path shelf is ungated or gated on 1.2's flag
               for that town (1.2 and 5.4: "where travel already gates a shelf, leave it ungated"). Since 2026-10-06
               (the owner: "should be the villagers with ui only"; data/markets.json decisions counters_are_merchants)
               a counter is a CobbleDollars merchant, whose screen shows one list to every player (MARKET_GATING.md 1):
               no line may carry a gate, the design's gate is held against the line's gate_dropped record, and each
               built counter whose shelf the ladder gates is a FINDING (sold before the badge), not a fault
    the window the merchant's own screen: each built counter is one cobbledollars:cobble_merchant summon tagged
               <stall_merchant.tag>_<id>, NoAI, named its keeper; the pack ships no dialogue or NPC class
    payment    the screen charges the offer's Price per item: one offer per shelf line, Item count 1, Price x the line's
               count = the line's price, no offer without a line; no function in the pack gives or charges (it could
               charge twice). Read with town_squares_audit's SNBT reader, not the builder's writer
    removal    the Cobblemon dialogue keeper each merchant replaces stood on the seat (spawnnpcat at the integer
               block): a kill of type=cobblemon:npc centred on the merchant must reach hypot(0.5, 0.5)
    tiers      PROGRESSION_LADDER.md 2.1 (tier -> badge: leather 0, copper 1, iron 3, gold 7, diamond 8, netherite
               a reward, never sold) and 2.3.1 ("the tiers above leather must not be craftable")
    overlay    the base file base-pack/cobbleverse/config/sophisticatedcore-common.toml; the jars' recipe JSON for
               the sophisticatedcore:item_enabled load condition (A-3)
    curve      ECONOMY_OVERHAUL.md section 7 R2 (2026-10-10, replacing 0.2's model B): 0.3's band 0.65-0.70 of
               (the critical path's convenience lines + data/markets.json curve_rule's fight allowance) over (trainer
               income, income_basis re-summed from its own level sums at 0.28125 S^2 + curve_rule's produce allowance
               + one gathering hour a leg at data/bank.json effort_model's tier rate); power lines leave it. R2's hard
               check: fights <= trainer income at every badge. 0.3's "a ladder that is exactly affordable is
               unaffordable": with the stretch items the ask stays below what the road earns. A critical stall's
               gated convenience lines count as a counter's would; its provisions never do
    curve rule data/markets.json price_policies.curve_scale's own criterion, re-derived (curve_price_faults): every
               critical-path convenience line carries the rule, and its price is list_price x its leg's scale,
               rounded; the band must be 0.3's. The ladder's numbers are relative worth, so a ruled line is held to
               the ladder by its list_price (what it carried before R2), every other line by its price
    floors    PROGRESSION_LADDER.md 6.4: a shop's unit price above bank.json's sell price for the same item
    keepers    the town's plan in data/placements.json (streets with their widths, anchor lots), every placed
               building's footprint (its template's size turned by its rotation), data/route_paths.json's walked
               lines (tools/npc_seats.py MIN_ROUTE, the repo's rule for an immovable NPC beside a walked line), and
               every other NPC the data places (reapply's "npc" action dedupes within 2 blocks)

  python tools/markets_audit.py --server-dir <server> [--pack build/datapacks/cobblers_markets] [--source-root R]
  python tools/markets_audit.py --jar-dir <folder of jars>          the same, jars from elsewhere
  python tools/markets_audit.py --no-jars                           everything but the jar checks (said so)

FAULT lines fail the run (exit 1). FINDING lines are disagreements between the data and a design document that do
not break the game (a price the ladder set differently and no document declares); they are printed, not failed.

What this does NOT cover: anything in a running game (G-1..G-6 of TIERED_GOODS 4); the town-dressing pieces' extents
(only their anchor cells are measured); recipes added by datapacks other than the jars' own; whether
cobbleDollarsIncomeMultiplier scales bank sales (U-1; the floors are reported under both readings); and the
keeper's height against its ground (the builder's plan-ground check).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DEFAULT_PACK = ROOT / "build" / "datapacks" / "cobblers_markets"
BASE_OVERLAY = ROOT / "base-pack" / "cobbleverse" / "config" / "sophisticatedcore-common.toml"
OVERLAY = ROOT / "modpack" / "config" / "sophisticatedcore-common.toml"
BANK = ROOT / "base-pack" / "cobbleverse" / "config" / "cobbledollars" / "bank.json"
INCOME_KEY_FILES = (ROOT / "modpack" / "config" / "cobbledollars" / "common.json",
                    ROOT / "base-pack" / "cobbleverse" / "config" / "cobbledollars" / "common.json")
SB = "sophisticatedbackpacks:"

# ------------------------------------------------------------------------------------------------ the design, cited
# PROGRESSION_LADDER.md 2.1 "The real numbers" (and 1.1 rows 0, 1, 3, 7, 8): the badge at which each tier is sold.
# netherite is "reward, not sold" (2.1) and "champion_cleared's reward item ... not a sale" (1.1 row 9).
TIER_ORDER = ["backpack", "copper_backpack", "iron_backpack", "gold_backpack", "diamond_backpack", "netherite_backpack"]
TIER_BADGE = {"backpack": 0, "copper_backpack": 1, "iron_backpack": 3, "gold_backpack": 7, "diamond_backpack": 8}
NEVER_SOLD = {SB + "netherite_backpack", SB + "everlasting_upgrade", SB + "infinity_upgrade",
              SB + "survival_infinity_upgrade",   # 1.5: "They end the economy the markets exist for (Q-6)"
              "cobblemon:rare_candy"}             # TIERED_GOODS 2.6 states the campaign never sells it (level cap)
# 2.3.1: "The tiers above leather must not be craftable" -- so the leather pack is the one sold item that may keep
# its recipe
MAY_STAY_CRAFTABLE = {SB + "backpack"}
# 1.2 "Flag" column, per off-path town. 5.4: "Where travel already gates a shelf, leave it ungated", so None is
# always allowed off the path; a flag, when used, must be the one 1.2 names
OFF_PATH_FLAG = {"mining_town": "gym3_cleared", "sunset_west": "gym5_cleared", "northlight": "gym6_cleared",
                 "tea_town": None, "sea_town": None, "tableland_stop": None}
# 0.3: "cumulative spend stays near 0.65-0.70 of cumulative income at every badge"; ECONOMY_OVERHAUL.md section 7 R2:
# "The band stays", with a new numerator and denominator (curve_terms)
CURVE_BAND = (0.65, 0.70)
# ECONOMY_OVERHAUL.md 1.1 / docs/research/notes/paid-services-and-npc-payouts.md B2: CobbleDollars' expected credit per
# NPC battle won is 1.25 x 2.25 x S^2/10 = 0.28125 S^2 (S the losing team's level sum)
PAYOUT_PER_S2 = 1.25 * 2.25 / 10
# R2's numerator counts these strands' lines and drops the rest: convenience is in, power "leaves it"; provision is
# the stalls' food and goods (tools/markets.py STRANDS), never a counter's
CURVE_STRANDS = {"convenience": True, "power": False, "provision": False}
DATA_BANK = ROOT / "data" / "bank.json"
BLACKOUT = ROOT / "data" / "blackout.json"
PRODUCE_BUYER = ROOT / "data" / "produce_buyer.json"
# 1.3 shows crafting_upgrade "separately because B7 makes it a stretch purchase", its "with crafting bought" column
# starting at badge 3; section 4 (B7): "visible from badge 1, affordable around badge 3". The only stretch the ladder has
STRETCH_FROM = {SB + "crafting_upgrade": 3}

# 1.1 and 1.2's per-item prices (unit prices), with the town the ladder sells them in. Keys are the ids the ladder
# names; TIERED_GOODS 3 corrects ids that do not exist (RENAMED) and declares moves and drops (DECLARED).
LADDER = {
    SB + "backpack": ("hometown", 300), "comforts:sleeping_bag": ("hometown", 250),
    SB + "stonecutter_upgrade": ("gym1_town", 1800), SB + "anvil_upgrade": ("gym1_town", 2500),
    SB + "copper_backpack": ("gym1_town", 1200), SB + "crafting_upgrade": ("gym1_town", 7500),
    SB + "tank_upgrade": ("gym2_town", 1500), SB + "filter_upgrade": ("gym2_town", 1200),
    SB + "advanced_filter_upgrade": ("gym2_town", 2500),
    SB + "iron_backpack": ("gym3_town", 4500), SB + "battery_upgrade": ("gym3_town", 2000),
    SB + "xp_pump_upgrade": ("gym3_town", 2000),
    SB + "feeding_upgrade": ("gym4_town", 2000), SB + "advanced_feeding_upgrade": ("gym4_town", 4500),
    "cobblecuisine:malasada": ("gym4_town", 900), "cobblecuisine:pokepuff": ("gym4_town", 500),
    SB + "pickup_upgrade": ("gym5_town", 1500), SB + "advanced_magnet_upgrade": ("gym5_town", 3000),
    SB + "smoking_upgrade": ("gym5_town", 2000), "mega_showdown:mega_bracelet": ("gym5_town", 7500),
    SB + "smithing_upgrade": ("gym6_town", 3000), SB + "stack_upgrade_starter_tier": ("gym6_town", 2000),
    SB + "stack_upgrade_tier_1": ("gym6_town", 3500), SB + "stack_upgrade_tier_2": ("gym6_town", 6000),
    SB + "smelting_upgrade": ("gym7_town", 2800), SB + "auto_smelting_upgrade": ("gym7_town", 4500),
    SB + "blasting_upgrade": ("gym7_town", 2500), SB + "gold_backpack": ("gym7_town", 8000),
    SB + "inception_upgrade": ("gym8_town", 7000), SB + "diamond_backpack": ("gym8_town", 10000),
    "obc:bottle_cap_gold": ("gym8_town", 6000),
    SB + "compacting_upgrade": ("mining_town", 2000), SB + "advanced_compacting_upgrade": ("mining_town", 3500),
    SB + "void_upgrade": ("mining_town", 1200), SB + "advanced_void_upgrade": ("mining_town", 2500),
    "waystones:blank_scroll": ("sunset_west", 400), "waystones:return_scroll": ("sunset_west", 1200),
    "waystones:warp_scroll": ("sunset_west", 3500), "waystones:bound_scroll": ("sunset_west", 2600),
    "cobblemon:great_ball": ("sunset_west", 750), "cobblemon:ultra_ball": ("sunset_west", 1000),
    "comforts:hammock": ("northlight", 800),
    "cobblemon:hp_up": ("northlight", 3500), "cobblemon:protein": ("northlight", 3500),
    "cobblemon:iron": ("northlight", 3500), "cobblemon:calcium": ("northlight", 3500),
    "cobblemon:zinc": ("northlight", 3500), "cobblemon:carbos": ("northlight", 3500),
}
# TIERED_GOODS 2.6 / 3: ids the ladder named that do not exist, and what replaced them
RENAMED = {"comforts:sleeping_bag": "comforts:sleeping_bag_brown", "cobblecuisine:malasada": "cobblecuisine:sweet_malasada",
           "cobblecuisine:pokepuff": "cobblecuisine:sweet_pokepuff", "comforts:hammock": "comforts:hammock_white"}
# TIERED_GOODS 3, row by row: ladder items dropped, moved, or added, with the row's reason. Nothing else is declared.
DECLARED_DROPPED = {SB + "advanced_filter_upgrade": "Viltri Quay's shelf ran to 102% of its leg",
                    SB + "advanced_magnet_upgrade": "Fenhide with the bracelet ran to 98% of its leg",
                    SB + "stack_upgrade_tier_2": "crafted from the bought tier 1"}
DECLARED_MOVED = {SB + "smoking_upgrade": "gym7_town", "cobblemon:great_ball": "gym3_town",
                  "cobblemon:ultra_ball": "gym6_town"}
DECLARED_ADDED = {SB + "magnet_upgrade": ("gym5_town", 1500)}
# 1.2 tea_town: "CobbleCuisine consumables at a discount, 500/900 less a margin": strictly under Greenhollow's
DISCOUNT_UNDER = {"tea_town": "gym4_town"}


class AuditError(Exception):
    pass


# ------------------------------------------------------------------------------------------------ inputs
PLAZA_CONTRACT = ROOT / "data" / "plaza_centres.json"


def contract_seats(path=None):
    """{stall id: keeper_at [x, y, z, yaw]} from the squares' contract (2026-10-03: the owner moved the market keepers
    onto the town squares' stalls; the squares' builder writes data/plaza_centres.json, "stalls": [{"id", "keeper_at",
    ...}] per town). Read here on its own, not through tools/markets.py, so a keeper the builder moves wrongly is
    still caught. {} when the file is absent: every keeper then stands where data/markets.json sites it."""
    p = Path(path) if path is not None else PLAZA_CONTRACT
    out = {}
    if not p.is_file():
        return out
    stack = [read_json(p)]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "stalls" and isinstance(v, list):
                    for s in v:
                        kp = s.get("keeper_at") if isinstance(s, dict) else None
                        if isinstance(kp, list) and len(kp) == 4:
                            out[s["id"]] = kp
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(o, list):
            stack.extend(o)
    return out


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def load_pack(pack):
    """{relative path: text} for a built pack directory, or a dict from a generator (list of lines / JSON object)."""
    if isinstance(pack, dict):
        out = {}
        for rel, body in pack.items():
            out[rel] = "\n".join(body) + "\n" if isinstance(body, list) else (
                body if isinstance(body, str) else json.dumps(body))
        return out
    pack = Path(pack)
    if not pack.is_dir():
        raise AuditError("no built pack at %s (run tools/markets.py build first)" % pack)
    return {f.relative_to(pack).as_posix(): f.read_text(encoding="utf-8") for f in pack.rglob("*") if f.is_file()}


def town_badges(progression, towns):
    """{town id: (badge number, flag id)} for the eight gym towns, from the flags' own waystone towns and towns.json's
    order; the hometown is badge 0 with no flag."""
    order = {t["id"]: t.get("order") for t in towns["towns"] if t.get("role") == "gym_town"}
    out = {"hometown": (0, None)}
    for f in progression["flags"]:
        town = (f.get("waystone") or {}).get("town")
        if (f.get("set_by") or {}).get("kind") == "trainer_defeat" and town in order:
            out[town] = (int(order[town]), f["id"])
    return out


def flag_badge(tb):
    return {flag: n for n, flag in tb.values() if flag}


def trainer_income(markets_doc):
    """{badge: cumulative Normal trainer income} (ECONOMY_OVERHAUL R1): data/markets.json income_basis, generated by
    tools/income_model.py, which must say relayed: false. Re-derived here from the block's own level sums under the
    expectation PAYOUT_PER_S2 * S^2 a battle and required to equal cumulative_by_badge exactly (the continuous sum,
    rounded): a hand-edited figure or a changed formula fails. The level sums themselves are checked against the
    rosters by tests/test_income_model.py's own reader, not here."""
    ib = markets_doc.get("income_basis") or {}
    if ib.get("relayed") is not False:
        raise AuditError("income_basis.relayed is %r: R1 wants trainer income generated from the rosters "
                         "(tools/income_model.py), relayed false" % (ib.get("relayed"),))
    cum = ib.get("cumulative_by_badge") or {}
    sums = (ib.get("level_sums") or {}).get("normal") or {}
    out, run = {}, 0.0
    for b in range(1, 9):
        if str(b) not in cum or str(b) not in sums:
            raise AuditError("income_basis: no cumulative_by_badge or level_sums.normal for badge %d" % b)
        run += sum(PAYOUT_PER_S2 * int(s) ** 2 for s in sums[str(b)])
        if int(cum[str(b)]) != round(run):
            raise AuditError("income_basis: badge %d's cumulative %s is not the %.5f*S^2 sum of its own level sums "
                             "(%d)" % (b, cum[str(b)], PAYOUT_PER_S2, round(run)))
        out[b] = int(cum[str(b)])
    return out


def curve_terms(markets_doc, effort_doc, blackout_doc):
    """R2's terms per badge 1-8, each CUMULATIVE: (fights, produce, gather, problems). Every number is read from
    data/markets.json curve_rule (the values the design declares), data/bank.json effort_model and buys (the tier and
    its rate), and data/blackout.json money (the blackout part of the fight allowance). Nothing is shared with
    tools/markets.py or tools/bank.py."""
    P = []
    cr = markets_doc.get("curve_rule") or {}
    fa = cr.get("fight_allowance") or {}
    per = fa.get("per_leg")
    if not isinstance(per, int) or isinstance(per, bool) or per <= 0:
        P.append("curve: curve_rule.fight_allowance.per_leg %r is not a positive whole number (R2 declares it)" % (per,))
        per = 0
    parts = fa.get("parts") or {}
    if sum(int(v) for v in parts.values()) != per:
        P.append("curve: curve_rule.fight_allowance.parts %s sum to %d, not per_leg %d" % (parts, sum(int(v) for v in parts.values()), per))
    money = (blackout_doc or {}).get("money") or {}
    if "cap" in money and "percent" in money:
        charge = -(-int(money["cap"]) * int(money["percent"]) // 100)      # ceil(cap * percent / 100), its charge_rule
        if parts.get("blackout") != charge:
            P.append("curve: curve_rule.fight_allowance.parts.blackout %r is not data/blackout.json's charge %d "
                     "(ceil(cap %s x percent %s / 100))" % (parts.get("blackout"), charge, money["cap"], money["percent"]))
    else:
        P.append("curve: data/blackout.json money has no cap and percent: the fight allowance's blackout part is unchecked")
    held = (cr.get("produce_allowance") or {}).get("by_badges_held") or {}
    hours = cr.get("gathering_hours_per_leg")
    if not isinstance(hours, (int, float)) or isinstance(hours, bool) or hours < 0:
        P.append("curve: curve_rule.gathering_hours_per_leg %r is not a number of hours" % (hours,))
        hours = 0
    tiers = ((effort_doc or {}).get("effort_model") or {}).get("tiers") or {}
    buys = (effort_doc or {}).get("buys") or []
    rate = {}
    for name, t in tiers.items():
        src = set((t or {}).get("from_tiers") or [])
        rate[name] = sum(int(b.get("rate_per_hour") or 0) * int(b.get("price") or 0) for b in buys if b.get("tier") in src)
    fights, produce, gather = {}, {}, {}
    f = p = g = 0
    for leg in range(1, 9):
        f += per
        if str(leg - 1) in held:
            p += int(held[str(leg - 1)])
        else:
            P.append("curve: curve_rule.produce_allowance.by_badges_held has no figure for %d badges held (leg %d)"
                     % (leg - 1, leg))
        opened = [(t.get("opens_leg"), n) for n, t in tiers.items()
                  if isinstance((t or {}).get("opens_leg"), int) and t["opens_leg"] <= leg]
        top = max((o for o, _n in opened), default=None)
        at = sorted(n for o, n in opened if o == top)
        if len(at) != 1:
            P.append("curve: leg %d: data/bank.json effort_model opens %s as its latest tier; R2 counts one gathering "
                     "hour at THE tier's rate" % (leg, at or "no tier"))
        else:
            g += hours * rate[at[0]]
        fights[leg], produce[leg], gather[leg] = f, p, g
    return fights, produce, gather, P


# ------------------------------------------------------------------------------------------------ the jars
class JarIndex:
    """Items and the recipes that produce selected ids, read from a folder of jars.

    An id is an item when a jar's lang carries item.<ns>.<path> or block.<ns>.<path>, OR when it has BOTH an item model
    (assets/<ns>/models/item/<path>.json) AND a place in an item tag (data/<ns>/tags/item/*.json). The second rule is
    for items whose display name is built in code: TMCraft's per-move TMs (tmcraft-1.4.19+1.8.0.jar, read in the
    2026-10-05 offline snapshot's mods/) carry no lang key -- assets/tmcraft/lang/en_us.json has 65 keys, none of them
    item.tmcraft.tm_* -- but each has assets/tmcraft/models/item/tm_<move>.json and is listed by
    data/tmcraft/tags/item/tm_moves.json (929 values, tmcraft:tm_bide among them), and data/tmcraft/recipe/tm_<move>.json
    names it as its result. A model alone is not enough (a model can exist for a block-only or unused id); vanilla's
    tag loader refuses a tag naming an unregistered required id, so a tag entry is a registry fact."""

    def __init__(self, items=(), recipes=(), models=(), tagged=()):
        self.items = set(items)
        self.recipes = list(recipes)       # (where, result id, [conditions])
        self.models = set(models)          # ids with an item model
        self.tagged = set(tagged)          # ids an item tag lists

    def is_item(self, i):
        return i in self.items or (i in self.models and i in self.tagged)

    @classmethod
    def from_dir(cls, jar_dir, want_results=()):
        jars = sorted(Path(jar_dir).glob("*.jar"))
        if not jars:
            raise AuditError("no jars in %s" % jar_dir)
        idx = cls()
        want = set(want_results)
        for j in jars:
            with zipfile.ZipFile(j) as z:
                idx._scan(z, j.name, want)
        return idx

    def _scan(self, z, where, want, depth=0):
        for name in z.namelist():
            if re.fullmatch(r"assets/[^/]+/lang/en_us\.json", name):
                try:
                    lang = json.loads(z.read(name).decode("utf-8-sig"))
                except ValueError:
                    continue
                for k in lang:
                    m = re.fullmatch(r"(?:item|block)\.([a-z0-9_.\-]+)\.([a-z0-9_./\-]+)", k)
                    if m:
                        self.items.add("%s:%s" % (m.group(1), m.group(2)))
            elif re.fullmatch(r"assets/([^/]+)/models/item/(.+)\.json", name):
                m = re.fullmatch(r"assets/([^/]+)/models/item/(.+)\.json", name)
                self.models.add("%s:%s" % m.groups())
            elif re.fullmatch(r"data/[^/]+/tags/items?/.+\.json", name):
                try:
                    vals = json.loads(z.read(name).decode("utf-8-sig")).get("values") or []
                except (ValueError, AttributeError):
                    continue
                for v in vals:
                    v = v.get("id") if isinstance(v, dict) and v.get("required", True) else v
                    if isinstance(v, str) and not v.startswith("#"):
                        self.tagged.add(v)
            elif want and re.fullmatch(r"data/[^/]+/recipes?/.+\.json", name):
                raw = z.read(name)
                if not any(w.encode() in raw for w in want):
                    continue
                try:
                    r = json.loads(raw.decode("utf-8-sig"))
                except ValueError:
                    continue
                res = recipe_result(r)
                if res in want:
                    self.recipes.append(("%s!%s" % (where, name), res, r.get("fabric:load_conditions") or []))
            elif depth == 0 and name.startswith("META-INF/jars/") and name.endswith(".jar"):
                with zipfile.ZipFile(BytesIO(z.read(name))) as inner:
                    self._scan(inner, "%s!%s" % (where, name), want, depth + 1)


def recipe_result(r):
    res = r.get("result")
    if isinstance(res, str):
        return res
    if isinstance(res, dict):
        return res.get("id") or res.get("item")
    return None


# ------------------------------------------------------------------------------------------------ the overlay
def enabled_items(text):
    """[(id, enabled)] of the toml's enabledItems list."""
    m = re.search(r"^\s*enabledItems\s*=\s*\[(.*?)\]\s*$", text, re.M | re.S)
    if not m:
        raise AuditError("no enabledItems list")
    out = []
    for s in re.findall(r'"([^"]*)"', m.group(1)):
        item, _, flag = s.rpartition("|")
        if flag not in ("true", "false"):
            raise AuditError("enabledItems entry %r is not '<id>|true|false'" % s)
        out.append((item, flag == "true"))
    return out


def overlay_problems(base_text, overlay_text, sold_sb):
    """The overlay differs from the base only by Sophisticated Backpacks entries switched true -> false; each switched
    item is sold at a built counter; every Sophisticated Backpacks item a built counter sells is switched, except the
    leather pack. Returns (problems, the switched-off set)."""
    out = []
    strip = lambda t: re.sub(r"^\s*enabledItems\s*=.*$", "", t, flags=re.M)
    if strip(base_text) != strip(overlay_text):
        out.append("overlay: a line other than enabledItems differs from the base file")
    base, over = enabled_items(base_text), enabled_items(overlay_text)
    if [i for i, _ in base] != [i for i, _ in over]:
        out.append("overlay: enabledItems does not list the base's ids in the base's order (added, removed or moved)")
    b = dict(base)
    off = set()
    for item, on in over:
        if item not in b:
            continue
        if on and not b[item]:
            out.append("overlay: %s switched ON against the base" % item)
        if not on and b[item]:
            off.add(item)
            if not item.startswith(SB):
                out.append("overlay: %s switched off, but it is not a Sophisticated Backpacks item" % item)
    for item in sorted(off - set(sold_sb)):
        out.append("overlay: %s has its recipe switched off but no built counter sells it, so it cannot be had" % item)
    for item in sorted(set(sold_sb) - off - MAY_STAY_CRAFTABLE):
        out.append("overlay: %s is sold at a built counter but its recipe is still on (PROGRESSION_LADDER 2.3.1)" % item)
    return out, off


def recipe_gate_problems(off, index):
    """A-3: every jar recipe that makes a switched-off item carries the item_enabled condition on that item."""
    out = []
    made = {}
    for where, res, conds in index.recipes:
        if res not in off:
            continue
        made.setdefault(res, []).append(where)
        ok = any(c.get("condition") == "sophisticatedcore:item_enabled" and c.get("itemRegistryName") == res
                 for c in conds if isinstance(c, dict))
        if not ok:
            out.append("recipe %s makes %s without the sophisticatedcore:item_enabled condition on it, so switching "
                       "it off leaves this recipe" % (where, res))
    for item in sorted(off):
        if item not in made:
            out.append("recipe: no jar recipe makes %s; the overlay switches off nothing (or the jar index is wrong)"
                       % item)
    return out


# ------------------------------------------------------------------------------------------------ the command model
class Unmodelled(Exception):
    pass


class Player:
    """One player and the server state a market function touches. charge_works / give_works force the failures."""

    def __init__(self, balance, flags=(), now=1000, charge_works=True, give_works=True, objectives=(), overdraw=False):
        self.balance, self.flags, self.now = balance, set(flags), now
        self.charge_works, self.give_works = charge_works, give_works
        # what `cobbledollars remove` does to a balance smaller than the amount is NOT known (no experiment reads
        # it), so the short scenarios run under both readings: refused, and taken anyway (the balance goes negative)
        self.overdraw = overdraw
        self.objectives = set(objectives)
        self.scores = {}
        self.storage = {}
        self.inventory = []
        self.said = []
        self.problems = []


SEL_ADV = re.compile(r"^@s\[advancements=\{([a-z0-9_.\-]+:[a-z0-9_/.\-]+)=(true|false)\}\]$")


def run_function(pack, ref, p, macro=None, depth=0):
    """Execute data/<ns>/function/<path>.mcfunction against Player p. Returns ('return', value) or ('end', None)."""
    if depth > 8:
        raise Unmodelled("function recursion")
    ns, path = ref.split(":", 1)
    rel = "data/%s/function/%s.mcfunction" % (ns, path)
    if rel not in pack:
        raise Unmodelled("function %s does not exist in the pack" % ref)
    for raw in pack[rel].splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("$"):
            if macro is None:
                raise Unmodelled("macro line in %s called without arguments: %s" % (ref, line))
            line = re.sub(r"\$\(([a-z_]+)\)", lambda m: str(macro[m.group(1)]), line[1:])
        kind, val = command(pack, line, p, depth)
        if kind == "return":
            return kind, val
    return "end", None


def score_get(p, holder, obj):
    return p.scores.get((holder, obj))


def command(pack, line, p, depth):
    """('ok', result) | ('fail', 0) | ('return', value). result is the command's integer result."""
    t = line.split(" ")
    head = t[0]
    if head == "execute":
        return execute(pack, t[1:], p, depth)
    if head == "return":
        if t[1] == "run":
            k, v = command(pack, " ".join(t[2:]), p, depth)
            return "return", (v if k != "return" else v)
        return "return", int(t[1])
    if head == "tellraw":
        p.said.append(" ".join(t[2:]))
        return "ok", 1
    if head == "time" and t[1:] == ["query", "gametime"]:
        return "ok", p.now
    if head == "cobbledollars":
        if t[2] != "@s":
            raise Unmodelled(line)
        if t[1] == "query":
            return "ok", p.balance
        n = int(t[3])
        if t[1] == "remove":
            if p.charge_works and 0 < n and (n <= p.balance or p.overdraw):
                p.balance -= n
                return "ok", 1
            return "fail", 0
        if t[1] == "add":
            p.balance += n
            return "ok", 1
        raise Unmodelled(line)
    if head == "scoreboard":
        if t[1] == "objectives" and t[2] == "add":
            p.objectives.add(t[3])
            return "ok", 1
        if t[1] == "players":
            op, holder, obj = t[2], t[3], t[4]
            if obj not in p.objectives:
                p.problems.append("scoreboard on objective %s that does not exist: %s" % (obj, line))
                return "fail", 0
            if op in ("set", "add", "remove"):
                n = int(t[5])
                cur = score_get(p, holder, obj) or 0
                p.scores[(holder, obj)] = n if op == "set" else cur + n if op == "add" else cur - n
                return "ok", 1
            if op == "operation":
                o, h2, obj2 = t[5], t[6], t[7]
                v2 = score_get(p, h2, obj2)
                if v2 is None:
                    return "fail", 0
                cur = score_get(p, holder, obj) or 0
                p.scores[(holder, obj)] = {"=": v2, "+=": cur + v2, "-=": cur - v2}[o]
                return "ok", 1
        raise Unmodelled(line)
    if head == "data" and t[1:3] == ["modify", "storage"] and t[5:7] == ["set", "value"]:
        store = p.storage.setdefault(t[3], {})
        keys = t[4].split(".")
        for k in keys[:-1]:
            store = store.setdefault(k, {})
        store[keys[-1]] = int(t[7])
        return "ok", 1
    if head == "function":
        macro = None
        if len(t) > 2:
            if t[2:4] != ["with", "storage"]:
                raise Unmodelled(line)
            macro = p.storage.get(t[4], {})
            for k in t[5].split("."):
                macro = macro.get(k, {}) if isinstance(macro, dict) else {}
            macro = dict(macro)
        kind, val = run_function(pack, t[1], p, macro, depth + 1)
        return "ok", (val if kind == "return" else 1)
    if head == "give":
        if t[1] != "@s":
            raise Unmodelled("give to %s (EXP-022 bug 1: give as the player, to @s)" % t[1])
        if not p.give_works:
            return "fail", 0
        p.inventory.append((t[2], int(t[3]) if len(t) > 3 else 1))
        return "ok", 1
    raise Unmodelled(line)


def execute(pack, t, p, depth):
    store = None
    i = 0
    while i < len(t):
        w = t[i]
        if w in ("as", "at"):
            if t[i + 1] != "@s":
                raise Unmodelled("execute %s %s" % (w, t[i + 1]))
            i += 2
        elif w == "store":
            store = (t[i + 1], t[i + 3], t[i + 4])     # result|success, holder, objective
            if t[i + 2] != "score":
                raise Unmodelled("execute store %s" % t[i + 2])
            i += 5
        elif w in ("if", "unless"):
            want = w == "if"
            if t[i + 1] == "score":
                v = score_get(p, t[i + 2], t[i + 3])
                if t[i + 4] == "matches":
                    rng = t[i + 5]
                    lo, _, hi = rng.partition("..")
                    if ".." not in rng:
                        lo = hi = rng
                    ok = v is not None and (lo == "" or v >= int(lo)) and (hi == "" or v <= int(hi))
                    i += 6
                else:
                    o, v2 = t[i + 4], score_get(p, t[i + 5], t[i + 6])
                    cmp = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, "=": lambda a, b: a == b,
                           ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}[o]
                    ok = v is not None and v2 is not None and cmp(v, v2)
                    i += 7
                passed = ok if want else not ok
            elif t[i + 1] == "entity":
                m = SEL_ADV.match(t[i + 2])
                if not m:
                    raise Unmodelled("execute %s entity %s" % (w, t[i + 2]))
                adv = m.group(1)
                has = adv.startswith("cobblers:flag/") and adv[len("cobblers:flag/"):] in p.flags
                ok = has if m.group(2) == "true" else not has
                passed = ok if want else not ok
                i += 3
            else:
                raise Unmodelled("execute %s %s" % (w, t[i + 1]))
            if not passed:
                if store and store[0] == "success" and store[2] in p.objectives:
                    p.scores[(store[1], store[2])] = 0
                return "fail", 0
        elif w == "run":
            kind, val = command(pack, " ".join(t[i + 1:]), p, depth)
            if store:
                how, holder, obj = store
                if obj in p.objectives:       # EXP-022 bug 2: a store into a missing objective fails silently
                    p.scores[(holder, obj)] = (1 if kind != "fail" else 0) if how == "success" else (val or 0)
            return kind, val
        else:
            raise Unmodelled("execute ... %s" % w)
    raise Unmodelled("execute without run")


def purchase_problems(pack, ref, item, price, count, gate, objectives, other_flags=()):
    """Run one purchase function under seven scenarios. Each returns a problem string when the money or the item ends
    up anywhere but where the design says (MARKET_GATING 4, criteria 2-4 of its section 5)."""
    out = []
    has = {gate} if gate else set()
    want = [(item, count)]

    def go(label, p, expect_bal, expect_inv, runs=1, gap=0):
        try:
            for k in range(runs):
                p.now += gap if k else 0
                run_function(pack, ref, p)
        except Unmodelled as e:
            out.append("%s: %s: a command outside the audit's model: %s" % (ref, label, e))
            return
        if p.problems:
            out.append("%s: %s: %s" % (ref, label, "; ".join(p.problems)))
        if p.balance != expect_bal or p.inventory != expect_inv:
            out.append("%s: %s: balance %d (expected %d), given %s (expected %s)"
                       % (ref, label, p.balance, expect_bal, p.inventory, expect_inv))

    mk = lambda bal, **kw: Player(bal, kw.pop("flags", has | set(other_flags)), objectives=objectives, **kw)
    go("a qualifying player with $%d" % (price + 137), mk(price + 137), 137, want)
    go("a qualifying player with exactly the price", mk(price), 0, want)
    go("a player $1 short", mk(price - 1), price - 1, [])
    go("a player $1 short, on a CobbleDollars that lets remove overdraw", mk(price - 1, overdraw=True), price - 1, [])
    p = mk(price - 1)
    try:
        run_function(pack, ref, p)
        if not p.said:
            out.append("%s: a player $1 short is told nothing" % ref)
    except Unmodelled:
        pass
    if gate:
        go("a rich player without %s" % gate, mk(price * 3, flags=set(other_flags) - {gate}), price * 3, [])
    go("a charge that takes nothing", mk(price + 50, charge_works=False), price + 50, [])
    go("a give that fails", mk(price + 50, give_works=False), price + 50, [])
    go("the same click submitted twice in one tick", mk(price * 2 + 9), price + 9, want, runs=2, gap=0)
    go("a second purchase after the cooldown", mk(price * 2 + 9), 9, want * 2, runs=2, gap=1200)
    return out


# ------------------------------------------------------------------------------------------------ the dialogue
TAG_PROBE = re.compile(r"advancements=\{cobblers:flag/([a-z0-9_]+)=true\}\] run tag @s add ([a-z0-9_]+)")
TAG_REMOVE = re.compile(r"tag ' \+ q\.player\.uuid \+ ' remove ([a-z0-9_]+)")


def probes(molang):
    """{tag: flag} probed by a MoLang string, only where the tag is removed before it is (re)added."""
    out = {}
    removed = set()
    for m in re.finditer(r"%s|%s" % (TAG_REMOVE.pattern, TAG_PROBE.pattern), molang):
        if m.group(1):
            removed.add(m.group(1))
        elif m.group(3) in removed:
            out[m.group(3)] = m.group(2)
    return out


def dialogue_problems(counter_id, pack, stock, gate_of):
    """The window: one option per shelf item running that item's function; a gated item's option visible only with a
    tag the probe sets from its gate flag, and its action re-probing before it runs; nothing written to quest state."""
    out = []
    rel = "data/cobblers/dialogues/dlg_market_%s.json" % counter_id
    if rel not in pack:
        return ["%s: no dialogue %s" % (counter_id, rel)]
    d = json.loads(pack[rel])
    init = d.get("initializationAction") or ""
    init_tags = probes(init)
    opts = [o for pg in d.get("pages") or [] for o in ((pg.get("input") or {}).get("options") or [])]
    ran = {}
    for o in opts:
        act = o.get("action") or ""
        fns = re.findall(r"run function (cobblers:markets/[a-z0-9_/]+)'", act)
        if not fns:
            continue
        if len(fns) != 1:
            out.append("%s: option %r runs %d functions" % (counter_id, o.get("text"), len(fns)))
            continue
        ran.setdefault(fns[0], []).append(o)
    for it in stock:
        ref = "cobblers:markets/%s/%s" % (counter_id, it["id"])
        got = ran.pop(ref, [])
        if len(got) != 1:
            out.append("%s: %d options run %s (expected one)" % (counter_id, len(got), ref))
            continue
        o = got[0]
        price = int(it["price"])
        if "${:,}".format(price) not in (o.get("text") or ""):
            out.append("%s: option %r does not show the price $%s it charges" % (counter_id, o.get("text"), "{:,}".format(price)))
        gate = gate_of(it)
        vis = o.get("isVisible")
        act = o.get("action") or ""
        if gate:
            if not vis:
                out.append("%s: %s is gated on %s but its option is visible to everyone" % (counter_id, it["id"], gate))
                continue
            vt = re.findall(r"has_tag\('([a-z0-9_]+)'\)", vis)
            if len(vt) != 1 or init_tags.get(vt[0]) != gate:
                out.append("%s: %s's option is shown on %s, not on a tag the menu probes from %s"
                           % (counter_id, it["id"], vt and init_tags.get(vt[0]), gate))
            at = probes(act)
            guard = re.search(r"\(q\.player\.has_tag\('([a-z0-9_]+)'\)\) \? \{ q\.run_command\('execute as ' \+ "
                              r"q\.player\.uuid \+ ' at @s run function " + re.escape(ref) + "'", act)
            if not guard or at.get(guard.group(1)) != gate:
                out.append("%s: %s's option runs its purchase without re-probing %s first" % (counter_id, it["id"], gate))
        elif vis and "has_tag" in vis:
            out.append("%s: %s is ungated but its option is hidden behind %s" % (counter_id, it["id"], vis))
    for ref in ran:
        out.append("%s: an option runs %s, which no shelf item names" % (counter_id, ref))
    blob = json.dumps(d)
    if re.search(r"t\.d\.[a-z_]+\s*=|set_data|q\.player\.data\(\)\.[a-z_]+\s*=", blob):
        out.append("%s: the menu writes quest state; a shop menu must be stateless (MARKET_GATING principle 12)" % counter_id)
    return out


# ------------------------------------------------------------------------------------------------ the merchants
# Since 2026-10-06 (data/markets.json decisions counters_are_merchants) no counter has a dialogue menu or a purchase
# function: the command model and the window check above (run_function, purchase_problems, dialogue_problems) audit
# no generated file any more and are kept, with their synthetic tests, for the per-player shop MARKET_GATING.md
# section 4 describes. What the pack holds now is read here.
MERCHANT_KIND = "cobbledollars:cobble_merchant"
_SUMMON = re.compile(r"(?:^|\brun )summon (\S+) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)(?: (.+))?$")
_CALL = re.compile(r"(?:^|\brun |^schedule )function ([a-z0-9_.\-]+:[a-z0-9_./\-]+)")


def _snbt(text):
    # town_squares_audit's reader: written by another agent for its own audit, not tools/traders.py's writer
    import town_squares_audit as TSA
    return TSA.snbt(text)


def merchant_summons(pack, only=None):
    """[{kind, pos (x, y, z), block, nbt, tags, yaw, file}] for every summon in the pack's functions (or in the
    functions in `only`). An unreadable SNBT is a summon with an empty nbt, so it is still counted."""
    out = []
    for rel, body in sorted(pack.items()):
        if not rel.endswith(".mcfunction") or (only is not None and rel not in only):
            continue
        for raw in body.splitlines():
            m = _SUMMON.search(raw.strip())
            if not m or raw.strip().startswith("#"):
                continue
            try:
                nbt = _snbt(m.group(5)) if m.group(5) else {}
            except ValueError:
                nbt = {}
            pos = tuple(float(m.group(k)) for k in (2, 3, 4))
            tags = [t for t in (nbt.get("Tags") or []) if isinstance(t, str)]
            rot = nbt.get("Rotation")
            out.append({"kind": m.group(1), "pos": pos, "block": tuple(math.floor(v) for v in pos), "nbt": nbt,
                        "tags": tags, "yaw": rot[0] if isinstance(rot, list) and rot else None, "file": rel})
    return out


def npc_kills(pack):
    """[((x, y, z) centre, radius, file)] of every `kill @e[type=cobblemon:npc,x=,y=,z=,distance=..r]` in the pack."""
    out = []
    for rel, body in pack.items():
        if not rel.endswith(".mcfunction"):
            continue
        for raw in body.splitlines():
            if raw.strip().startswith("#"):
                continue
            for sel in re.findall(r"kill @e\[([^\]]*)\]", raw):
                a = dict(x.split("=", 1) for x in sel.split(",") if "=" in x)
                r = re.fullmatch(r"\.\.(\d+(?:\.\d+)?)", a.get("distance", ""))
                if a.get("type") == "cobblemon:npc" and r and all(k in a for k in "xyz"):
                    out.append(((float(a["x"]), float(a["y"]), float(a["z"])), float(r.group(1)), rel))
    return out


def reachable(pack, root):
    """The pack paths of every function `root` runs, following `function`, `schedule function` and `execute ... run
    function` inside the pack."""
    seen, todo = set(), [root]
    while todo:
        fid = todo.pop()
        ns, path = fid.split(":", 1)
        rel = "data/%s/function/%s.mcfunction" % (ns, path)
        if rel in seen or rel not in pack:
            continue
        seen.add(rel)
        todo += [m.group(1) for line in pack[rel].splitlines() for m in _CALL.finditer(line.strip())]
    return seen


def pack_keepers(pack, doc, root):
    """[(counter id, (x, y, z) block, yaw)] of every counter merchant summoned by a function `root` reaches."""
    prefix = (doc.get("stall_merchant") or {}).get("tag") or "cobblers_stall"
    ids = {c["id"] for c in doc["counters"]}
    out = []
    for m in merchant_summons(pack, reachable(pack, root)):
        for t in m["tags"]:
            if t.startswith(prefix + "_") and t[len(prefix) + 1:] in ids:
                out.append((t[len(prefix) + 1:], m["block"], m["yaw"]))
    return out


# ------------------------------------------------------------------------------------------------ keepers
def seg_dist(px, pz, a, b):
    (ax, az), (bx, bz) = a, b
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))


def poly_dist(px, pz, pts):
    if len(pts) == 1:
        return math.hypot(px - pts[0][0], pz - pts[0][1])
    return min(seg_dist(px, pz, a, b) for a, b in zip(pts, pts[1:]))


def keeper_problems(cid, at, plan, footprints, walked, others, min_route):
    """A keeper's cell (x, z) must lie in no street (centre within half its width of the polyline), no anchor lot, no
    building footprint, not within min_route of a walked line, and no other NPC within reapply's 2-block dedupe."""
    out = []
    x, y, z = at
    cx, cz = x + 0.5, z + 0.5
    for st in plan.get("streets") or []:
        d = poly_dist(cx, cz, st["polyline"])
        if d < st.get("width", 1) / 2.0:
            out.append("keeper %s at %s stands in street %s (%.1f from its line, half-width %.1f)"
                       % (cid, list(at), st["id"], d, st.get("width", 1) / 2.0))
    for an in plan.get("anchors") or []:
        x0, z0, x1, z1 = an["rect"]
        if min(x0, x1) <= x <= max(x0, x1) and min(z0, z1) <= z <= max(z0, z1):
            out.append("keeper %s at %s stands inside anchor lot %s %s" % (cid, list(at), an["id"], an["rect"]))
    for pid, (x0, z0, x1, z1) in footprints.items():
        if x0 <= x <= x1 and z0 <= z <= z1:
            out.append("keeper %s at %s stands inside building %s (%d..%d, %d..%d)" % (cid, list(at), pid, x0, x1, z0, z1))
    for rid, pts in walked.items():
        d = poly_dist(cx, cz, pts) if pts else 1e9
        if d < min_route:
            out.append("keeper %s at %s is %.1f blocks from walked line %s (an immovable NPC closer than %.1f stands "
                       "in the road)" % (cid, list(at), d, rid, min_route))
    for what, q in others:
        qx, qy, qz = q
        for ex, ez in ((qx, qz), (qx + 0.5, qz + 0.5)):
            if math.dist((x, y, z), (ex, qy, ez)) <= 2.0:
                out.append("keeper %s at %s is within 2 blocks of %s at %s: reapply's npc step would take one for the "
                           "other" % (cid, list(at), what, list(q)))
                break
    return out


FACING = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def frontage_problems(cid, at, yaw, plan):
    """A keeper stands BESIDE its Mart (MARKET_GATING 4: 'A Mart gets a clerk and a quartermaster'; R17M's own
    comment: 'each beside its town's Mart and turned to face its plaza'). From the plan: the Mart anchor's `facing` is
    its door's side (gym1_town's reading: 'door facing the plaza'), so a keeper beyond the Mart's opposite face stands
    behind the building; and with Minecraft's yaw (0 = +z, 90 = -x) a plaza whose nearest point lies behind the
    keeper's facing half-plane is a plaza it has its back to."""
    out = []
    x, _y, z = at
    marts = [a for a in plan.get("anchors") or [] if a.get("role") == "pokemart"]
    for a in marts:
        f = FACING.get(a.get("facing"))
        if not f:
            continue
        x0, z0, x1, z1 = a["rect"]
        x0, x1, z0, z1 = min(x0, x1), max(x0, x1), min(z0, z1), max(z0, z1)
        behind = {(-1, 0): x > x1, (1, 0): x < x0, (0, -1): z > z1, (0, 1): z < z0}[f]
        if behind:
            out.append("keeper %s at %s stands behind its Mart %s (door faces %s; the keeper is past the far wall)"
                       % (cid, list(at), a["id"], a["facing"]))
    pz = (plan.get("plaza") or {}).get("rect")
    if pz and yaw is not None:
        px = min(max(x + 0.5, min(pz[0], pz[2])), max(pz[0], pz[2]) + 1)
        pzz = min(max(z + 0.5, min(pz[1], pz[3])), max(pz[1], pz[3]) + 1)
        r = math.radians(yaw)
        ahead = -math.sin(r) * (px - x - 0.5) + math.cos(r) * (pzz - z - 0.5)
        if ahead < 0:
            out.append("keeper %s at %s faces yaw %s, with its back to its plaza %s" % (cid, list(at), yaw, pz))
    return out


def building_footprints(settlement, placements, templates):
    """{placement id: (x0, z0, x1, z1)} as each building's placer seats it (place_donor.footprint: a pack donor turns
    about its position, a town building starts at its minimum corner), and the ids whose size could not be read."""
    sys.path.insert(0, str(TOOLS))
    import place_donor as PD
    out, unknown = {}, []
    for q in placements["placements"]:
        if q.get("settlement") != settlement or q.get("kind") == "earthwork" or not q.get("position"):
            continue
        size, _why = PD.template_size(q, templates)
        if size is None:
            unknown.append(q["id"])
            continue
        out[q["id"]] = PD.footprint(q, size)
    return out, unknown


def other_npcs(exclude_prefix="dlg_market_"):
    """Every other NPC the data places, as (what, (x, y, z)), and what could not be enumerated."""
    sys.path.insert(0, str(TOOLS))
    out, missing = [], []
    for t in read_json(ROOT / "data" / "traders.json")["traders"]:
        p = t.get("position") or {}
        if "x" in p:
            out.append(("trader %s" % t["id"], (p["x"], p["y"], p["z"])))
    srcs = [("ferries", lambda m: m.npc_placements(m.load())), ("npc_seats", lambda m: m.placements()),
            ("old_orchard", lambda m: m.npc_placements()), ("dune_ruin", lambda m: m.npc_placements()),
            ("ursaluna_cave", lambda m: m.npc_placements()), ("relic_underground", lambda m: m.npc_placements()),
            ("drovers_hollow", lambda m: m.npc_placements())]
    for mod, call in srcs:
        try:
            m = __import__(mod)
            for n in call(m):
                pos = next(v for v in n if isinstance(v, (tuple, list)) and len(v) == 3)
                label = next((v for v in n if isinstance(v, str)), "?")
                if not str(label).startswith(exclude_prefix):
                    out.append(("%s %s" % (mod, label), tuple(pos)))
        except BaseException as e:      # a placer that cannot list its NPCs here is named, not hidden
            missing.append("%s (%s)" % (mod, str(e)[:120]))
    return out, missing


# ------------------------------------------------------------------------------------------------ the curve (R2)
def curve_records(doc, crit):
    """The records whose lines R2's numerator reads: every counter in a critical-path town (`crit`, town_badges), and,
    of a stall in one, only its GATED lines (data/markets.json price_policies.curve_scale criterion: 'every critical
    counter's, a critical stall's gated ones'; an ungated stall line is a provision, never a rung). A stall copy keeps
    its id and town."""
    out = [c for c in doc["counters"] if c["town"] in crit]
    for s in doc.get("stalls") or []:
        gated = [it for it in s.get("stock") or [] if it.get("gate")]
        if s.get("town") in crit and gated:
            out.append(dict(s, stock=gated))
    return out


def curve_price_faults(doc, crit, income, effort, blackout):
    """FAULT lines for data/markets.json price_policies.curve_scale, re-derived from the policy's own words and this
    audit's R2 terms (curve_terms, trainer_income), nothing from tools/markets.py:

      a critical-path convenience line carries price_rule curve_scale and a positive whole list_price; no line off
      that set carries the rule. Leg by leg (a town's badge, the hometown's 0 spent in leg 1), one scale:
        (band midpoint x earned by that badge - fights by then - what the earlier legs cost at the rule's own rounded
         prices, worked out here - this leg's unruled curve lines) / this leg's list shelf   (a group at its dearest)
      and each price is list_price x scale rounded to the nearest multiple of round_to x count (half up), never below
      one such multiple. A stretch line takes the scale of its STRETCH_FROM leg (the ladder's own), and must say so in
      affordable_by.

    The band must be 0.3's CURVE_BAND: the policy cannot move the band the design holds. `income` None (already a
    fault) checks only the records. What this does NOT check: that the rule's prices are any good as prices (that is
    curve_faults' band, and the ladder's list_price comparison)."""
    F = []
    pol = (doc.get("price_policies") or {}).get("curve_scale")
    ruled_anywhere = [(c["id"], it["id"]) for c in doc["counters"] + list(doc.get("stalls") or [])
                      for it in c.get("stock") or [] if it.get("price_rule") == "curve_scale"]
    if not pol:
        if ruled_anywhere:
            F.append("curve rule: %d line(s) carry price_rule curve_scale but data/markets.json has no "
                     "price_policies.curve_scale" % len(ruled_anywhere))
        return F
    band = pol.get("band")
    if not (isinstance(band, list) and len(band) == 2 and tuple(band) == CURVE_BAND):
        F.append("curve rule: price_policies.curve_scale.band %r is not PROGRESSION_LADDER 0.3's %s" % (band, list(CURVE_BAND)))
        return F
    step = pol.get("round_to")
    if isinstance(step, bool) or not isinstance(step, int) or step <= 0:
        F.append("curve rule: price_policies.curve_scale.round_to %r is not a positive whole number" % (step,))
        return F
    mid = (band[0] + band[1]) / 2
    on_curve = []                                        # (record, line, leg)
    for c in curve_records(doc, crit):
        for it in c["stock"]:
            if it.get("strand") != "convenience":
                continue
            if it.get("stretch"):
                if it["item"] not in STRETCH_FROM:
                    continue                             # curve_faults names it
                if it.get("affordable_by") != STRETCH_FROM[it["item"]]:
                    F.append("curve rule: %s/%s is a stretch line affordable_by %r; the ladder makes it affordable "
                             "at badge %d" % (c["id"], it["id"], it.get("affordable_by"), STRETCH_FROM[it["item"]]))
                leg = STRETCH_FROM[it["item"]]
            else:
                leg = crit[c["town"]]
            on_curve.append((c, it, max(1, leg)))
    keys = {(c["id"], it["id"]) for c, it, _l in on_curve}
    for k in ruled_anywhere:
        if k not in keys:
            F.append("curve rule: %s/%s carries price_rule curve_scale but is not a critical-path convenience line "
                     "(the rule prices only R2's numerator)" % k)
    ok = []
    for c, it, leg in on_curve:
        if it.get("price_rule") != "curve_scale":
            F.append("curve rule: %s/%s is a critical-path convenience line without price_rule curve_scale "
                     "(its price would be hand-typed onto the curve)" % (c["id"], it["id"]))
            continue
        lp = it.get("list_price")
        if isinstance(lp, bool) or not isinstance(lp, int) or lp <= 0:
            F.append("curve rule: %s/%s carries price_rule curve_scale with list_price %r, not a positive whole "
                     "number" % (c["id"], it["id"], lp))
            continue
        ok.append((c, it, leg))
    if income is None:
        return F
    fights, produce, gather, _tp = curve_terms(doc, effort, blackout)      # curve_faults reports _tp

    def shelf(rows, value):
        """{leg: sum of value(record, line)} over non-stretch rows, a (record, group) at its dearest."""
        out, groups = {}, {}
        for c, it, leg in rows:
            if it.get("stretch"):
                continue
            if it.get("group"):
                k = (leg, c["id"], it["group"])
                groups[k] = max(groups.get(k, 0), value(c, it))
            else:
                out[leg] = out.get(leg, 0) + value(c, it)
        for (leg, _c, _g), v in groups.items():
            out[leg] = out.get(leg, 0) + v
        return out

    def rule(it, s):
        unit = step * int(it.get("count") or 1)
        return max(unit, int(math.floor(it["list_price"] * s / unit + 0.5)) * unit)

    # the earlier legs are counted at the RULE's prices (worked out here leg by leg), never at the prices written in
    # the file: an expectation read from the artifact under check is not an expectation, and one mispriced line
    # then faults alone instead of moving every later leg's figure with it. Unruled lines (already faults) count
    # at their written price: there is nothing else to count them at
    ruled_ids = {(c["id"], it["id"]) for c, it, _l in ok}
    lists = shelf(ok, lambda _c, it: it["list_price"])
    unruled = shelf([r for r in on_curve if (r[0]["id"], r[1]["id"]) not in ruled_ids],
                    lambda _c, it: int(it["price"]))
    scale, expect, before = {}, {}, 0
    for leg in range(1, 9):
        earned = income[leg] + produce[leg] + gather[leg]
        want = mid * earned - fights[leg] - before - unruled.get(leg, 0)
        here = [r for r in ok if r[2] == leg and not r[1].get("stretch")]
        if lists.get(leg):
            if want <= 0:
                F.append("curve rule: leg %d: fights %d, the earlier legs' %d and this leg's unruled %d already ask "
                         "more than the band's midpoint of %g earned; no positive scale exists"
                         % (leg, fights[leg], before, unruled.get(leg, 0), mid * earned))
            else:
                scale[leg] = want / lists[leg]
                for c, it, _l in here:
                    expect[(c["id"], it["id"])] = rule(it, scale[leg])
        before += unruled.get(leg, 0) + shelf([r for r in here if (r[0]["id"], r[1]["id"]) in expect],
                                              lambda c, it: expect[(c["id"], it["id"])]).get(leg, 0)
    for c, it, leg in ok:
        if leg not in scale:
            if lists.get(leg) is None:
                F.append("curve rule: %s/%s is a stretch line whose leg %d has no other ruled line to take its scale "
                         "from" % (c["id"], it["id"], leg))
            continue
        unit = step * int(it.get("count") or 1)
        want = rule(it, scale[leg])
        if int(it["price"]) != want:
            F.append("curve rule: %s/%s costs $%d; price_policies.curve_scale gives list $%d x leg %d's scale %.4f "
                     "= $%d (rounded to $%d)" % (c["id"], it["id"], int(it["price"]), it["list_price"], leg,
                                                 scale[leg], want, unit))
    return F


def curve_faults(doc, crit, income, effort, blackout):
    """(faults, notes) of ECONOMY_OVERHAUL.md section 7 R2 over data/markets.json `doc`. `crit` is {critical-path
    town: its badge} (town_badges), `income` {badge: cumulative trainer income} or None (already a fault), `effort`
    data/bank.json and `blackout` data/blackout.json (curve_terms)."""
    F, N = [], []
    shelf = {}
    for c in curve_records(doc, crit):
        groups, s = {}, 0
        for it in c["stock"]:
            if it.get("strand") not in CURVE_STRANDS:
                F.append("curve: %s/%s has strand %r; R2 counts convenience lines and drops power, so a line of no "
                         "known strand cannot be placed" % (c["id"], it["id"], it.get("strand")))
                continue
            if it.get("stretch") or not CURVE_STRANDS[it["strand"]]:
                continue
            if it.get("group"):
                groups[it["group"]] = max(groups.get(it["group"], 0), int(it["price"]))
            else:
                s += int(it["price"])
        shelf[crit[c["town"]]] = shelf.get(crit[c["town"]], 0) + s + sum(groups.values())
    fights, produce, gather, tp = curve_terms(doc, effort, blackout)
    F += tp
    if income is None:
        return F, N
    earned = {b: income[b] + produce[b] + gather[b] for b in range(1, 9)}
    cum = shelf.get(0, 0)
    lo, hi = CURVE_BAND
    ratios = []
    for b in range(1, 9):
        cum += shelf.get(b, 0)
        ask = cum + fights[b]
        r = ask / earned[b]
        ratios.append("%d:(%d+%d)/(%d+%d+%g)=%.2f" % (b, cum, fights[b], income[b], produce[b], gather[b], r))
        if not lo <= round(r, 2) <= hi:
            F.append("curve: after badge %d convenience %d + fights %d = %d of trainer income %d + produce %d + "
                     "gathering %g = %g is %.3f, outside %.2f-%.2f (ECONOMY_OVERHAUL R2)"
                     % (b, cum, fights[b], ask, income[b], produce[b], gather[b], earned[b], r, lo, hi))
        # R2: "The hard check stays: fights <= trainer income at every badge"
        if fights[b] > income[b]:
            F.append("curve: after badge %d the fight allowance %d is more than trainer income %d: the road does "
                     "not pay for its own fights (ECONOMY_OVERHAUL R2)" % (b, fights[b], income[b]))
    N.append("curve R2 (badge:(convenience+fights)/(trainer+produce+gathering), critical path, stretch aside, a "
             "group at its dearest): %s" % " ".join(ratios))
    if not PRODUCE_BUYER.is_file():
        N.append("curve: the produce allowance (%d by badge 8) is curve_rule's declared schedule; the Produce Buyer "
                 "(U2, data/produce_buyer.json) is not built, so no NPC pays it yet" % produce[8])
    # 1.3's "with crafting bought" column: the stretch purchase counted from the badge its shelf opens, and 0.3's
    # "a ladder that is exactly affordable is unaffordable", in R2's terms: the ask with its stretch items stays
    # below what the road earns
    stretch = {}
    for c in curve_records(doc, crit):
        for it in c["stock"]:
            if it.get("stretch"):
                if it["item"] not in STRETCH_FROM:
                    F.append("curve: %s/%s is kept out of the curve as a stretch purchase; the ladder names no "
                             "such stretch (only %s)" % (c["id"], it["id"], sorted(STRETCH_FROM)))
                    continue
                b = STRETCH_FROM[it["item"]]
                stretch[b] = stretch.get(b, 0) + int(it["price"])
    cum = shelf.get(0, 0) + stretch.get(0, 0)
    for b in range(1, 9):
        cum += shelf.get(b, 0) + stretch.get(b, 0)
        if cum + fights[b] >= earned[b]:
            F.append("curve: after badge %d the ask with its stretch items, %d + fights %d, is not below what the "
                     "road earns, %g (PROGRESSION_LADDER 0.3, 1.3; ECONOMY_OVERHAUL R2)"
                     % (b, cum, fights[b], earned[b]))
    return F, N


# ------------------------------------------------------------------------------------------------ the audit
def audit(doc, pack, overlay_text, base_text, progression, towns, bank, income=None, index=None, placements=None,
          templates=None, walked=None, others=None, min_route=3.0, keepers=None, income_multiplier=1.0,
          effort=None, blackout=None):
    """(faults, findings, notes). `pack` is {rel: text}; `keepers` the counters' merchants R17M summons [(counter id,
    (x,y,z) block, yaw)] (pack_keepers), `index` a JarIndex or None (jar checks then NOT CHECKED). `income` is
    {badge: cumulative trainer income}, default trainer_income(doc); `effort` data/bank.json and `blackout`
    data/blackout.json (R2's gathering hour and fight allowance), default the files."""
    F, W, N = [], [], []
    if income is None:
        try:
            income = trainer_income(doc)
        except AuditError as e:
            F.append("curve: %s" % e)
            income = None
    effort = effort if effort is not None else read_json(DATA_BANK)
    blackout = blackout if blackout is not None else read_json(BLACKOUT)
    tb = town_badges(progression, towns)
    fb = flag_badge(tb)
    flags = {f["id"] for f in progression["flags"]}
    # since 2026-10-06 (the owner: "should be the villagers with ui only"; data/markets.json decisions
    # counters_are_merchants) a counter's keeper is a CobbleDollars merchant: known in the pack by the summon carrying
    # its tag <stall_merchant.tag>_<counter id>, read with town_squares_audit's own SNBT reader (not the builder's)
    prefix = (doc.get("stall_merchant") or {}).get("tag") or "cobblers_stall"
    counters = {c["id"]: c for c in doc["counters"]}
    by_counter = {}
    for m in merchant_summons(pack):
        named = [t[len(prefix) + 1:] for t in m["tags"] if t.startswith(prefix + "_") and t[len(prefix) + 1:] in counters]
        for cid in named:
            by_counter.setdefault(cid, []).append(m)
    built_ids = sorted(by_counter)
    sited = sorted(c["id"] for c in doc["counters"] if c.get("status") == "sited")
    if built_ids != sited:
        F.append("pack: counter merchants summoned for %s, but data/markets.json sites %s" % (built_ids, sited))
    for cid, ms in sorted(by_counter.items()):
        if len(ms) != 1:
            F.append("pack: %d merchant summons carry counter %s's tag, not 1" % (len(ms), cid))
    built = [counters[i] for i in built_ids if i in counters]

    # --- gates against the design. A merchant shows one list to every player (MARKET_GATING.md section 1), so no
    # counter line may carry a gate; the gate each line USED to carry is kept in gate_dropped and is still held to the
    # design (until 2026-10-06 this rule read `gate` itself: a critical-path shelf gated on its own town's badge)
    def design_gate_ok(c, gate):
        town = c["town"]
        if town in tb:
            return gate == tb[town][1], "its town's own badge flag %s" % tb[town][1]
        if town in OFF_PATH_FLAG:
            return gate in (None, OFF_PATH_FLAG[town]), "none or %s (PROGRESSION_LADDER 1.2, 5.4)" % OFF_PATH_FLAG[town]
        return False, "a town the ladder gives no market"

    def dropped(it):
        gd = it.get("gate_dropped")
        return gd.get("gate") if isinstance(gd, dict) else None

    decided = {d.get("id") for d in doc.get("decisions") or []}
    for c in doc["counters"]:
        for it in c["stock"]:
            if it.get("gate"):
                F.append("gate: %s/%s is gated on %s, but its merchant shows every line to every player "
                         "(MARKET_GATING 1)" % (c["id"], it["id"], it["gate"]))
            gd = it.get("gate_dropped")
            if gd is not None and not (isinstance(gd, dict) and gd.get("decision") in decided and gd.get("why")):
                F.append("gate: %s/%s's gate_dropped %r names no recorded decision and why" % (c["id"], it["id"], gd))
            g = dropped(it)
            if g and g not in flags:
                F.append("gate: %s/%s records the gate %s, which data/progression.json does not declare"
                         % (c["id"], it["id"], g))
            ok, why = design_gate_ok(c, g)
            if not ok:
                F.append("gate: %s/%s (town %s) records the gate %s; the design says %s"
                         % (c["id"], it["id"], c["town"], g, why))
            if it["item"] in NEVER_SOLD:
                F.append("shelf: %s/%s sells %s, which the ladder never sells" % (c["id"], it["id"], it["item"]))
    for c in built:
        lost = sorted({dropped(it) for it in c["stock"] if dropped(it)})
        if lost:
            W.append("window: %s (%s): PROGRESSION_LADDER gates its shelf on %s; data/markets.json drops the gate "
                     "(decision counters_are_merchants), so its %d gated lines are on sale to a player who reaches the "
                     "town without that badge" % (c["id"], c["town"], " / ".join(lost),
                                                 sum(1 for it in c["stock"] if dropped(it))))

    def expected_gate(c):
        town = c["town"]
        if town in tb:
            return lambda it: tb[town][1]
        return lambda it: dropped(it) if dropped(it) in (None, OFF_PATH_FLAG.get(town)) else "<undesigned>"

    # --- the pack: load, and the merchant's screen as the only shop window and the only payment
    load_tag = json.loads(pack.get("data/minecraft/tags/function/load.json", "{}") or "{}")
    if "cobblers:markets/load" not in (load_tag.get("values") or []):
        F.append("pack: the load tag does not run cobblers:markets/load")
    for rel in pack:
        if re.match(r"data/cobblers/(dialogues|npcs)/", rel):
            F.append("pack: %s is a dialogue or NPC class; every seller is a merchant since 2026-10-06" % rel)
    for rel, body in pack.items():
        if rel.endswith(".mcfunction") and re.search(r"(?m)(?:^|\brun )(?:give @s |cobbledollars (?:remove|add) )", body):
            F.append("payment: %s gives or charges; the merchant's own screen does both, so this could charge twice" % rel)
    offered = set()
    all_kills = npc_kills(pack)
    for c in built:
        m = by_counter[c["id"]][0]
        d = m["nbt"]
        if m["kind"] != MERCHANT_KIND:
            F.append("merchant: %s summons %s, not %s" % (c["id"], m["kind"], MERCHANT_KIND))
        if d.get("NoAI") != 1:
            F.append("merchant: %s has AI (NoAI %r): it walks off its seat" % (c["id"], d.get("NoAI")))
        try:
            nm = json.loads(d.get("CustomName") or "null")
            nm = nm.get("text") if isinstance(nm, dict) else nm
        except ValueError:
            nm = d.get("CustomName")
        if nm != (c.get("keeper") or {}).get("name"):
            F.append("merchant: %s is named %r, its keeper %r" % (c["id"], nm, (c.get("keeper") or {}).get("name")))
        offers = [o for cat in (d.get("CobbleMerchantShop") or []) if isinstance(cat, dict)
                  for o in (cat.get("Offers") or []) if isinstance(o, dict)]
        for it in c["stock"]:
            hit = [o for o in offers if (o.get("Item") or {}).get("id") == it["item"]]
            if len(hit) != 1:
                F.append("payment: %s offers %s %d times, not once" % (c["id"], it["item"], len(hit)))
                continue
            o = hit[0]
            offers.remove(o)
            offered.add(it["item"])
            p = o.get("Price")
            if o["Item"].get("count") != 1:
                F.append("payment: %s offers %s %r at a time; the screen sells singly" % (c["id"], it["item"],
                                                                                        o["Item"].get("count")))
            if not (isinstance(p, str) and p.isdigit()) or int(p) * int(it["count"]) != int(it["price"]):
                F.append("payment: %s sells %s at %r each; the shelf's line is %d for $%d"
                         % (c["id"], it["item"], p, int(it["count"]), int(it["price"])))
        for o in offers:
            F.append("payment: %s offers %r, which no shelf line sells" % (c["id"], o))
            if isinstance(o.get("Item"), dict) and o["Item"].get("id"):
                offered.add(o["Item"]["id"])
        # the Cobblemon dialogue keeper it replaces (spawnnpcat at the integer seat, reapply's npc action, so within
        # hypot(0.5, 0.5) of the merchant's centre) must be killed by a selector centred on the merchant
        cx, cy, cz = m["pos"]
        kills = [k for k in all_kills if math.dist(k[0], (cx, cy, cz)) < 0.01]
        if not any(r >= math.hypot(0.5, 0.5) for _c, r, _f in kills):
            F.append("merchant: %s: no kill of type=cobblemon:npc centred on its merchant reaches the dialogue keeper "
                     "R17M placed on that seat (a Steve left beside it)" % c["id"])
    sold_built = {it["item"] for c in built for it in c["stock"]}
    if offered != sold_built:
        F.append("pack: the counters' merchants offer %s, but the built shelves sell %s"
                 % (sorted(offered - sold_built), sorted(sold_built - offered)))

    # --- ids against the jars
    every = sorted({it["item"] for c in doc["counters"] for it in c["stock"]} | offered)
    if index is None:
        N.append("NOT CHECKED: ids and recipes against the jars (no jar folder given)")
    else:
        for i in every:
            if not index.is_item(i):
                F.append("id: %s is not an item in any server jar" % i)

    # --- the overlay and the recipes
    sold_sb = {it["item"] for c in built for it in c["stock"] if it["item"].startswith(SB)}
    probs, off = overlay_problems(base_text, overlay_text, sold_sb)
    F += probs
    if index is not None:
        F += recipe_gate_problems(off, index)

    # --- tiers
    first = {}
    for c in built:
        for it in c["stock"]:
            g = expected_gate(c)(it)
            b = fb.get(g, 0) if g else (tb[c["town"]][0] if c["town"] in tb else 0)
            first[it["item"]] = min(first.get(it["item"], 99), b)
    for c in doc["counters"]:      # an unsited counter's ungated stock is not for sale yet; only Pallet's matters
        if c.get("status") != "sited" and c["town"] == "hometown":
            for it in c["stock"]:
                first.setdefault(it["item"], None)
    last = -1
    for tier in TIER_ORDER:
        item = SB + tier
        want = TIER_BADGE.get(tier)
        have = first.get(item)
        if want is None:
            if item in first:
                F.append("tiers: %s is sold; the ladder makes it a reward, never a sale" % item)
            continue
        if item in off and have is None:
            F.append("tiers: %s's recipe is off but no built counter sells it" % item)
        if have is not None:
            if have != want:
                F.append("tiers: %s first sold at badge %s; the ladder places it at badge %d" % (item, have, want))
            if have < last:
                F.append("tiers: %s is sold at badge %d, before the tier below it (badge %d)" % (item, have, last))
            last = max(last, have)
        elif tier != "backpack":
            F.append("tiers: %s is sold at no built counter; the ladder sells it at badge %d" % (item, want))

    # --- prices: the curve, the whole ask, the ladder's items, the floors
    # ECONOMY_OVERHAUL.md section 7 R2 (replacing PROGRESSION_LADDER 0.3's every-line-over-model-B form): the band
    # 0.65-0.70 holds (the critical path's CONVENIENCE lines + the declared fight allowance) over (trainer income + the
    # produce allowance + one gathering hour a leg at the tier's rate), every term cumulative. Power lines leave the
    # numerator: "power is never priced in money a fighter can reach" (1.3), so their price is a gate, not an ask
    crit = {t: n for t, (n, _f) in tb.items()}
    cf, cn = curve_faults(doc, crit, income, effort, blackout)
    F += cf
    N += cn
    # data/markets.json price_policies.curve_scale: a convenience line's price is the rule's, not a hand figure
    F += curve_price_faults(doc, crit, income, effort, blackout)
    whole = {}
    for c in doc["counters"]:
        groups = {}
        for it in c["stock"]:
            g = dropped(it)           # the badge the line was designed to wait for (gate_dropped since 2026-10-06)
            b = fb[g] if g in fb else (crit.get(c["town"], 1) if c["town"] in crit else 1)
            b = max(b, 1)
            if it.get("group"):
                key = (c["id"], it["group"])
                if int(it["price"]) > groups.get(key, (0, 0))[0]:
                    groups[key] = (int(it["price"]), b)
            else:
                whole[b] = whole.get(b, 0) + int(it["price"])
        for price, b in groups.values():
            whole[b] = whole.get(b, 0) + price
    tot = sum(whole.values())
    # a measurement, not a rule: 1.3 quotes "about $129,350" for the full ladder, counting one of each power-strand
    # line rather than every option, so no threshold is derivable for one-of-every-option
    if income is not None:
        N.append("one of every option on every shelf, stretch and off-path included: %d against badge 8's trainer "
                 "income %d (%.2f)" % (tot, income[8], tot / income[8]))

    # The ladder's numbers are relative worth, set before R2. A line priced by price_policies.curve_scale keeps that
    # worth as list_price and its price is the rule's scale of it (curve_price_faults), so the ladder is held against
    # list_price there; every other line, and the discount rule below (what a player pays), against price
    town_of, paid_of = {}, {}
    for c in doc["counters"]:
        for it in c["stock"]:
            ruled = it.get("price_rule") == "curve_scale" and isinstance(it.get("list_price"), int)
            worth = it["list_price"] if ruled else int(it["price"])
            town_of.setdefault(it["item"], []).append((c["town"], worth / int(it["count"]), c["id"], ruled))
            paid_of.setdefault(it["item"], []).append((c["town"], int(it["price"]) / int(it["count"]), c["id"]))
    for lid, (ltown, lprice) in LADDER.items():
        item = RENAMED.get(lid, lid)
        sold = [s for s in town_of.get(item, []) if s[0] not in DISCOUNT_UNDER]
        if not sold:
            if lid not in DECLARED_DROPPED:
                W.append("ladder: %s (%s, $%d) is on no shelf and TIERED_GOODS 3 does not say it was dropped"
                         % (lid, ltown, lprice))
            continue
        if lid in DECLARED_DROPPED:
            F.append("ladder: %s is declared dropped (TIERED_GOODS 3) but is sold" % lid)
        for town, unit, cid, ruled in sold:
            wt = DECLARED_MOVED.get(item, ltown)
            if town != wt:
                W.append("ladder: %s is sold at %s (%s); the ladder sells it at %s and no move is declared"
                         % (item, cid, town, wt))
            if unit != lprice:
                W.append("ladder: %s at %s %s $%g each; the ladder prices it at $%d and TIERED_GOODS 3 does not "
                         "declare the change" % (item, cid, "lists (list_price, curve_scale) at" if ruled else "costs",
                                                 unit, lprice))
    for item, (town, price) in DECLARED_ADDED.items():
        for t, unit, cid, ruled in town_of.get(item, []):
            if t != town or unit != price:
                W.append("ladder: %s at %s for $%g%s; TIERED_GOODS 3 declares it at %s for $%d"
                         % (item, cid, unit, " (list_price, curve_scale)" if ruled else "", town, price))
    for cheap, dear in DISCOUNT_UNDER.items():
        for item, rows in paid_of.items():
            a = [u for t, u, _ in rows if t == cheap]
            b = [u for t, u, _ in rows if t == dear]
            if a and b and not max(a) < min(b):
                F.append("discount: %s costs $%g at %s, not under %s's $%g (PROGRESSION_LADDER 1.2)"
                         % (item, max(a), cheap, dear, min(b)))
    sell = {e["item"]: int(e["price"]) for e in bank["bank"]}
    for c in doc["counters"]:
        for it in c["stock"]:
            if it["item"] in sell:
                unit = int(it["price"]) / int(it["count"])
                if not unit > sell[it["item"]]:
                    F.append("floor: %s/%s sells at $%g each, not above bank.json's $%d sell-back (PROGRESSION_LADDER 6.4)"
                             % (c["id"], it["id"], unit, sell[it["item"]]))
                for m, why in ((income_multiplier, "the overlay's cobbleDollarsIncomeMultiplier"),
                               (2.5, "PROGRESSION_LADDER 0.5's reading")):
                    if m > 1 and not unit > sell[it["item"]] * m:
                        W.append("floor: %s/%s at $%g each is not above the sell-back $%d x %.2f (%s), so if U-1 finds the "
                                 "multiplier scales bank sales it is a money printer"
                                 % (c["id"], it["id"], unit, sell[it["item"]], m, why))

    # --- the keepers R17M places: since 2026-10-06 the counters' merchants, summoned by the functions R17M runs
    # (keepers: [(counter id, (x, y, z) block, yaw)], read from those functions' summons by pack_keepers)
    if keepers is not None:
        # where each built keeper should stand: its stall's keeper_at when the squares' contract seats it (the owner,
        # 2026-10-03: keepers onto the squares), else data/markets.json's own `at`
        seats = contract_seats()
        want_at = {c["id"]: [int(v) for v in seats[c["stall"]][:3]] if c.get("stall") in seats else list(c["at"])
                   for c in built}
        want_yaw = {c["id"]: seats[c["stall"]][3] if c.get("stall") in seats else c.get("yaw") for c in built}
        byid = {}
        for k in keepers:
            byid.setdefault(k[0], []).append(k)
        for c in built:
            ks = byid.pop(c["id"], [])
            if len(ks) != 1:
                F.append("keeper: R17M summons %d merchants for %s" % (len(ks), c["id"]))
                continue
            k = ks[0]
            if tuple(k[1]) != tuple(want_at[c["id"]]):
                F.append("keeper: R17M summons %s's merchant at %s; the data sites it at %s"
                         % (c["id"], list(k[1]), want_at[c["id"]]))
            if k[2] is None or abs((float(k[2]) - float(want_yaw[c["id"]]) + 180) % 360 - 180) > 0.01:
                F.append("keeper: R17M turns %s's merchant to yaw %s; its seat's is %s" % (c["id"], k[2], want_yaw[c["id"]]))
        for cid in byid:
            F.append("keeper: R17M summons a merchant for %s, which no built counter is" % cid)
        if placements is not None:
            plans = placements["settlements"]
            for c in built:
                plan = (plans.get(c["town"]) or {}).get("plan") or {}
                fps, unknown = building_footprints(c["town"], placements, templates)
                if unknown:
                    F.append("keeper: %s's town has buildings whose size cannot be read, so the keeper is not checked "
                             "against them: %s" % (c["id"], unknown[:6]))
                if not plan:
                    N.append("keeper %s: town %s has no street plan; checked against buildings and walked lines only"
                             % (c["id"], c["town"]))
                mine = [k for k in keepers if k[0] != c["id"]]
                at = tuple(want_at[c["id"]])
                F += keeper_problems(c["id"], at, plan, fps, walked or {},
                                     (others or []) + [("keeper %s" % k[0], tuple(k[1])) for k in mine], min_route)
                fr = frontage_problems(c["id"], at, seats[c["stall"]][3] if c.get("stall") in seats else c.get("yaw"), plan)
                if c.get("stall") in seats:
                    # a keeper moved onto its square's stall is no longer "beside its Mart": only its facing is held
                    fr = [f for f in fr if "behind its Mart" not in f]
                F += fr
                if plan.get("plaza"):
                    x0, z0, x1, z1 = plan["plaza"]["rect"]
                    dx = max(x0 - at[0], 0, at[0] - x1)
                    dz = max(z0 - at[2], 0, at[2] - z1)
                    N.append("keeper %s: %.0f blocks from its plaza" % (c["id"], math.hypot(dx, dz)))
    else:
        N.append("NOT CHECKED: the keepers' placements (none given)")
    return F, W, N


def income_multiplier():
    for f in INCOME_KEY_FILES:
        if f.is_file():
            return float(read_json(f).get("cobbleDollarsIncomeMultiplier", 1.0))
    return 1.0


def run(pack_dir=DEFAULT_PACK, jar_dir=None, keepers=None, files=None, overlay_text=None, with_world=True):
    """Gather the real inputs and audit. `files` (a generator's dict) overrides `pack_dir`; `keepers` defaults to
    what reapply's R17M step lists."""
    sys.path.insert(0, str(TOOLS))
    doc = read_json(ROOT / "data" / "markets.json")
    pack = load_pack(files if files is not None else pack_dir)
    base_text = BASE_OVERLAY.read_text(encoding="utf-8")
    overlay_text = overlay_text if overlay_text is not None else OVERLAY.read_text(encoding="utf-8")
    index = None
    if jar_dir:
        want = {item for item, on in enabled_items(overlay_text) if not on}
        index = JarIndex.from_dir(jar_dir, want)
    notes = []
    placements = templates = walked = others = None
    if with_world:
        placements = read_json(ROOT / "data" / "placements.json")
        import town_character as TC
        templates = TC.Templates(TC.default_pack_dir(), TC.default_vanilla_jar())
        walked = {k: [tuple(p) for p in v] for k, v in read_json(ROOT / "data" / "route_paths.json")["paths"].items()}
        others, missing = other_npcs()
        notes += ["NOT CHECKED: NPCs placed by %s could not be listed" % m for m in missing]
        if keepers is None:
            keepers = pack_keepers(pack, doc, r17m_root())
    F, W, N = audit(doc, pack, overlay_text, base_text, read_json(ROOT / "data" / "progression.json"),
                    read_json(ROOT / "data" / "towns.json"), read_json(BANK), index=index,
                    placements=placements, templates=templates, walked=walked, others=others, keepers=keepers,
                    income_multiplier=income_multiplier(), min_route=min_route())
    return F, W, N + notes


def min_route():
    """tools/npc_seats.py MIN_ROUTE: the repo's rule for an immovable NPC beside a walked line."""
    import npc_seats
    return float(npc_seats.MIN_ROUTE)


def r17m_root():
    """The function R17M runs to summon the merchants, read the way R17M names it (its source names the constant).
    Since 2026-10-06 the counters' keepers are merchants summoned by it; R17M's `npc` actions place none."""
    src = (TOOLS / "reapply.py").read_text(encoding="utf-8")
    block = re.search(r'out\.append\(\("R17M",.*?\)\)\)', src, re.S)
    if not block or '("fn", markets.MERCHANTS_FN)' not in block.group(0):
        raise AuditError("tools/reapply.py has no R17M step running markets.MERCHANTS_FN")
    import markets
    if markets.npc_placements(markets.load()):
        raise AuditError("markets.npc_placements still lists dialogue keepers for R17M to place beside the merchants")
    return markets.MERCHANTS_FN


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(DEFAULT_PACK))
    ap.add_argument("--server-dir", help="read <server>/mods (the jars only; nothing else in the server folder)")
    ap.add_argument("--jar-dir")
    ap.add_argument("--no-jars", action="store_true", help="skip the jar checks, and say so")
    ap.add_argument("--source-root", help="accepted so prepare passes it alike; nothing here reads the heightmap")
    a = ap.parse_args(argv)
    jar_dir = a.jar_dir or (str(Path(a.server_dir) / "mods") if a.server_dir else None) or os.environ.get("COBBLERS_JAR_DIR")
    if not jar_dir and not a.no_jars:
        print("FAULT: no jars to check ids against: pass --server-dir, --jar-dir or --no-jars")
        return 1
    try:
        F, W, N = run(a.pack, None if a.no_jars else jar_dir)
    except AuditError as e:
        print("FAULT: %s" % e)
        return 1
    for n in N:
        print("note: %s" % n)
    for w in W:
        print("FINDING: %s" % w)
    for f in F:
        print("FAULT: %s" % f)
    print("markets_audit: %d fault(s), %d finding(s)" % (len(F), len(W)))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
