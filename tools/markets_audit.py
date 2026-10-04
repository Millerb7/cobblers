#!/usr/bin/env python
"""Independent audit of the town markets: data/markets.json, the generated pack cobblers_markets, the keepers R17M
places, and the recipe overlay modpack/config/sophisticatedcore-common.toml.

Written by an agent that did not build the markets, against docs/mechanics/TIERED_GOODS.md section 4 (A-1..A-5).
NOTHING here is imported from tools/markets.py or derived with its helpers: every expectation comes from a design
document, a data file another system owns, or the server's jars, and the generated pack is read as files.

  where each expectation comes from
    ids        the server's jars: an item exists when a jar's assets/<ns>/lang/en_us.json carries item.<ns>.<path> or
               block.<ns>.<path> (nested META-INF/jars too)
    gates      the badge a town's gym awards: data/progression.json's gymN_cleared flags name their town
               (waystone.town), data/towns.json orders the gym towns. A critical-path shelf is gated on its own town's
               badge (PROGRESSION_LADDER.md 1.1 "Flag" column); an off-path shelf is ungated or gated on 1.2's flag
               for that town (1.2 and 5.4: "where travel already gates a shelf, leave it ungated")
    the window MARKET_GATING.md 4: a gated option is visible only to a player holding the flag (isVisible reads a
               tag the dialogue's probe sets from the advancement), the option re-probes before it runs anything, and
               the menu is stateless (principle 12: no quest field written)
    payment    MARKET_GATING.md 4 + tools/ferries.py's docstring ("read the balance, refuse if it is short, charge
               ..., verify the balance fell by exactly the fare, and only then deliver"), checked by EXECUTING each
               generated function in a small command model under seven scenarios, not by matching its text
    tiers      PROGRESSION_LADDER.md 2.1 (tier -> badge: leather 0, copper 1, iron 3, gold 7, diamond 8, netherite
               a reward, never sold) and 2.3.1 ("the tiers above leather must not be craftable")
    overlay    the base file base-pack/cobbleverse/config/sophisticatedcore-common.toml; the jars' recipe JSON for
               the sophisticatedcore:item_enabled load condition (A-3)
    curve      PROGRESSION_LADDER.md 0.2's model-B income table, parsed from the document; 0.3's target band
               "cumulative spend stays near 0.65-0.70 of cumulative income at every badge"; 0.3's "a ladder that is
               exactly affordable is unaffordable" (the whole ask, stretch and off-path included, below income)
    floors     PROGRESSION_LADDER.md 6.4: a shop's unit price above bank.json's sell price for the same item
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
LADDER_DOC = ROOT / "docs" / "mechanics" / "PROGRESSION_LADDER.md"
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
# 0.3: "cumulative spend stays near 0.65-0.70 of cumulative income at every badge"
CURVE_BAND = (0.65, 0.70)
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


def ladder_income(text=None):
    """{badge: cumulative income, model B} parsed from PROGRESSION_LADDER.md 0.2's table (the bold column)."""
    text = text if text is not None else LADDER_DOC.read_text(encoding="utf-8")
    sec = text.split("### 0.2", 1)[1].split("### 0.3", 1)[0]
    out = {}
    for m in re.finditer(r"^\|\s*badge (\d)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|\s*\*\*([\d,]+)\*\*\s*\|", sec, re.M):
        out[int(m.group(1))] = int(m.group(4).replace(",", ""))
    if sorted(out) != list(range(1, 9)):
        raise AuditError("PROGRESSION_LADDER.md 0.2: expected model B for badges 1-8, read %s" % sorted(out))
    return out


# ------------------------------------------------------------------------------------------------ the jars
class JarIndex:
    """Items (from lang keys) and the recipes that produce selected ids, read from a folder of jars."""

    def __init__(self, items=(), recipes=()):
        self.items = set(items)
        self.recipes = list(recipes)       # (where, result id, [conditions])

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


# ------------------------------------------------------------------------------------------------ the audit
def audit(doc, pack, overlay_text, base_text, progression, towns, bank, income, index=None, placements=None,
          templates=None, walked=None, others=None, min_route=3.0, keepers=None, income_multiplier=1.0):
    """(faults, findings, notes). `pack` is {rel: text}; `keepers` the R17M placements [(dialogue, (x,y,z), class,
    yaw)], `index` a JarIndex or None (jar checks then NOT CHECKED)."""
    F, W, N = [], [], []
    tb = town_badges(progression, towns)
    fb = flag_badge(tb)
    flags = {f["id"] for f in progression["flags"]}
    built_ids = sorted(re.match(r"data/cobblers/npcs/npc_market_([a-z0-9_]+)\.json$", r).group(1)
                       for r in pack if re.match(r"data/cobblers/npcs/npc_market_[a-z0-9_]+\.json$", r))
    counters = {c["id"]: c for c in doc["counters"]}
    sited = sorted(c["id"] for c in doc["counters"] if c.get("status") == "sited")
    if built_ids != sited:
        F.append("pack: keepers built %s, but data/markets.json sites %s" % (built_ids, sited))
    built = [counters[i] for i in built_ids if i in counters]

    # --- gates against the design
    def design_gate_ok(c, gate):
        town = c["town"]
        if town in tb:
            return gate == tb[town][1], "its town's own badge flag %s" % tb[town][1]
        if town in OFF_PATH_FLAG:
            return gate in (None, OFF_PATH_FLAG[town]), "none or %s (PROGRESSION_LADDER 1.2, 5.4)" % OFF_PATH_FLAG[town]
        return False, "a town the ladder gives no market"

    for c in doc["counters"]:
        for it in c["stock"]:
            g = it.get("gate")
            if g and g not in flags:
                F.append("gate: %s/%s is gated on %s, which data/progression.json does not declare" % (c["id"], it["id"], g))
            ok, why = design_gate_ok(c, g)
            if not ok:
                F.append("gate: %s/%s (town %s) is gated on %s; the design says %s" % (c["id"], it["id"], c["town"], g, why))
            if it["item"] in NEVER_SOLD:
                F.append("shelf: %s/%s sells %s, which the ladder never sells" % (c["id"], it["id"], it["item"]))

    def expected_gate(c):
        town = c["town"]
        if town in tb:
            return lambda it: tb[town][1]
        return lambda it: it.get("gate") if it.get("gate") in (None, OFF_PATH_FLAG.get(town)) else "<undesigned>"

    # --- the pack: load, the window, the payment
    load_tag = json.loads(pack.get("data/minecraft/tags/function/load.json", "{}") or "{}")
    if "cobblers:markets/load" not in (load_tag.get("values") or []):
        F.append("pack: the load tag does not run cobblers:markets/load")
    loaded = set()
    p0 = Player(0)
    try:
        run_function(pack, "cobblers:markets/load", p0)
        loaded = set(p0.objectives)
    except Unmodelled as e:
        F.append("pack: cobblers:markets/load: %s" % e)
    for c in built:
        gate_of = expected_gate(c)
        F += ["window: %s" % s for s in dialogue_problems(c["id"], pack, c["stock"], gate_of)]
        npc = pack.get("data/cobblers/npcs/npc_market_%s.json" % c["id"])
        if npc:
            n = json.loads(npc)
            if (n.get("interaction") or {}).get("dialogue") != "cobblers:dlg_market_%s" % c["id"]:
                F.append("npc: %s does not open its own dialogue" % c["id"])
            if n.get("isMovable") is not False or n.get("canDespawn") is not False or n.get("isInvulnerable") is not True:
                F.append("npc: %s can be moved, despawned or killed" % c["id"])
        for it in c["stock"]:
            ref = "cobblers:markets/%s/%s" % (c["id"], it["id"])
            others_flags = {f for f in fb if f != gate_of(it)}
            F += ["payment: %s" % s for s in purchase_problems(pack, ref, it["item"], int(it["price"]), int(it["count"]),
                                                              gate_of(it), loaded, others_flags)]
    # the stalls (2026-10-03, data/markets.json `stalls`) share this pack under function/stalls/: their purchases are
    # not the counters' shelves, so they are left out of this comparison (tools/markets.py audits them; the
    # independent audit of the stalls is a separate unit)
    gives = set(re.findall(r"\bgive @s ([a-z0-9_.\-]+:[a-z0-9_/.\-]+)", "\n".join(
        v for k, v in pack.items() if k.endswith(".mcfunction") and not k.startswith("data/cobblers/function/stalls/"))))
    sold_built = {it["item"] for c in built for it in c["stock"]}
    if gives != sold_built:
        F.append("pack: functions give %s, but the built shelves sell %s"
                 % (sorted(gives - sold_built), sorted(sold_built - gives)))

    # --- ids against the jars
    every = sorted({it["item"] for c in doc["counters"] for it in c["stock"]} | gives)
    if index is None:
        N.append("NOT CHECKED: ids and recipes against the jars (no jar folder given)")
    else:
        for i in every:
            if i not in index.items:
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
    crit = {t: n for t, (n, _f) in tb.items()}
    shelf = {}
    for c in doc["counters"]:
        if c["town"] not in crit:
            continue
        groups, s = {}, 0
        for it in c["stock"]:
            if it.get("stretch"):
                continue
            if it.get("group"):
                groups[it["group"]] = max(groups.get(it["group"], 0), int(it["price"]))
            else:
                s += int(it["price"])
        shelf[crit[c["town"]]] = shelf.get(crit[c["town"]], 0) + s + sum(groups.values())
    cum = shelf.get(0, 0)
    lo, hi = CURVE_BAND
    ratios = []
    for b in range(1, 9):
        cum += shelf.get(b, 0)
        r = cum / income[b]
        ratios.append("%.2f" % r)
        if not lo <= round(r, 2) <= hi:
            F.append("curve: after badge %d the critical-path ask is %d of income %d = %.3f, outside %.2f-%.2f "
                     "(PROGRESSION_LADDER 0.3)" % (b, cum, income[b], r, lo, hi))
    N.append("curve (critical path, stretch aside, a group at its dearest): %s" % " / ".join(ratios))
    # 1.3's "with crafting bought" column: the stretch purchase counted from the badge its shelf opens, and 0.3's
    # "a ladder that is exactly affordable is unaffordable": the cumulative ask stays below cumulative income
    stretch = {}
    for c in doc["counters"]:
        for it in c["stock"]:
            if it.get("stretch"):
                if it["item"] not in STRETCH_FROM:
                    F.append("curve: %s/%s is kept out of the curve as a stretch purchase; the ladder names no such "
                             "stretch (only %s)" % (c["id"], it["id"], sorted(STRETCH_FROM)))
                    continue
                b = STRETCH_FROM[it["item"]]
                stretch[b] = stretch.get(b, 0) + int(it["price"])
    cum = shelf.get(0, 0) + stretch.get(0, 0)
    for b in range(1, 9):
        cum += shelf.get(b, 0) + stretch.get(b, 0)
        if cum >= income[b]:
            F.append("curve: after badge %d the critical-path ask with its stretch items is %d, not below income %d "
                     "(PROGRESSION_LADDER 0.3, 1.3)" % (b, cum, income[b]))
    whole = {}
    for c in doc["counters"]:
        groups = {}
        for it in c["stock"]:
            g = it.get("gate")
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
    N.append("one of every option on every shelf, stretch and off-path included: %d against badge 8's %d (%.2f)"
             % (tot, income[8], tot / income[8]))

    town_of = {}
    for c in doc["counters"]:
        for it in c["stock"]:
            town_of.setdefault(it["item"], []).append((c["town"], int(it["price"]) / int(it["count"]), c["id"]))
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
        for town, unit, cid in sold:
            wt = DECLARED_MOVED.get(item, ltown)
            if town != wt:
                W.append("ladder: %s is sold at %s (%s); the ladder sells it at %s and no move is declared"
                         % (item, cid, town, wt))
            if unit != lprice:
                W.append("ladder: %s at %s costs $%g each; the ladder prices it at $%d and TIERED_GOODS 3 does not "
                         "declare the change" % (item, cid, unit, lprice))
    for item, (town, price) in DECLARED_ADDED.items():
        for t, unit, cid in town_of.get(item, []):
            if t != town or unit != price:
                W.append("ladder: %s at %s for $%g; TIERED_GOODS 3 declares it at %s for $%d" % (item, cid, unit, town, price))
    for cheap, dear in DISCOUNT_UNDER.items():
        for item, rows in town_of.items():
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

    # --- the keepers R17M places
    if keepers is not None:
        # where each built keeper should stand: its stall's keeper_at when the squares' contract seats it (the owner,
        # 2026-10-03: keepers onto the squares), else data/markets.json's own `at`
        seats = contract_seats()
        want_at = {c["id"]: [int(v) for v in seats[c["stall"]][:3]] if c.get("stall") in seats else list(c["at"])
                   for c in built}
        byid = {}
        for k in keepers:
            m = re.fullmatch(r"dlg_market_([a-z0-9_]+)", k[0])
            byid.setdefault(m.group(1) if m else k[0], []).append(k)
        for c in built:
            ks = byid.pop(c["id"], [])
            if len(ks) != 1:
                F.append("keeper: R17M places %d keepers for %s" % (len(ks), c["id"]))
                continue
            k = ks[0]
            if tuple(k[1]) != tuple(want_at[c["id"]]) or k[2] != "cobblers:npc_market_%s" % c["id"]:
                F.append("keeper: R17M places %s at %s; the data sites it at %s" % (k[2], list(k[1]), want_at[c["id"]]))
            if "data/cobblers/npcs/npc_market_%s.json" % c["id"] not in pack:
                F.append("keeper: R17M places class %s, which the pack does not ship" % k[2])
        for cid in byid:
            F.append("keeper: R17M places %s, which no built counter is" % cid)
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
                mine = [k for k in keepers if not k[0].endswith("_" + c["id"])]
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
            keepers = r17m_keepers()
    F, W, N = audit(doc, pack, overlay_text, base_text, read_json(ROOT / "data" / "progression.json"),
                    read_json(ROOT / "data" / "towns.json"), read_json(BANK), ladder_income(), index=index,
                    placements=placements, templates=templates, walked=walked, others=others, keepers=keepers,
                    income_multiplier=income_multiplier(), min_route=min_route())
    return F, W, N + notes


def min_route():
    """tools/npc_seats.py MIN_ROUTE: the repo's rule for an immovable NPC beside a walked line."""
    import npc_seats
    return float(npc_seats.MIN_ROUTE)


def r17m_keepers():
    """The keepers reapply's R17M step places, read the way R17M reads them (its source names the call)."""
    src = (TOOLS / "reapply.py").read_text(encoding="utf-8")
    if not re.search(r'"R17M".*?markets\.npc_placements\(markets\.load\(\)\)', src, re.S):
        raise AuditError("tools/reapply.py has no R17M step placing markets.npc_placements(markets.load())")
    import markets
    return list(markets.npc_placements(markets.load()))


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
