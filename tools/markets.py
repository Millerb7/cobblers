#!/usr/bin/env python
"""Town markets: a keeper beside each Mart whose shelf is gated per player by badge, paid in CobbleDollars.
Generated from data/markets.json into the world-local datapack build/datapacks/cobblers_markets.

The design is docs/mechanics/MARKET_GATING.md section 4 (the mechanism), docs/mechanics/PROGRESSION_LADDER.md
revision 2 (the curve) and docs/mechanics/TIERED_GOODS.md (the ids, read from the server's jars). Nothing new in the
game: it is the ferry (tools/ferries.py) with the teleport replaced by a give.

  the keeper     a Cobblemon NPC whose class opens a dialogue (tools/compile_dialogue.py, EXP-022), placed over RCON by
                 spawnnpcat after a restart (tools/reapply.py R17M, the "npc" action), facing its plaza
  the menu       one page, one option per shelf item; an option gated on a badge is visible only to a player holding
                 it (compile_dialogue "flag" -> isVisible, probed per player). No cursor, no field: stateless, so two
                 players at one keeper cannot disturb each other's menu (MARKET_GATING.md "Principle 12")
  the purchase   a function run as the player by the option: refuse a second submit inside the cooldown, re-check the
                 gate, read the balance (`cobbledollars query`, EXP-040), refuse if short with nothing taken, charge by
                 the blackout's proven macro (`$cobbledollars remove @s $(amount)`, EXP-042 run 1), re-read and refuse
                 unless the balance fell by exactly the price, then give AS the player (EXP-022 bug 1) and, if the give
                 reports failure, add the price back (`$cobbledollars add @s $(amount)`: the command is VERIFIED from
                 the jar, EXP-040; the refund branch is NOT run in game)
  the recipes    every Sophisticated Backpacks item a built counter sells has its recipe switched off in
                 modpack/config/sophisticatedcore-common.toml (`enabledItems`, "<id>|false"), the mod's own documented
                 key, written by `overlay` from the base file so the overlay differs from Cobbleverse's in nothing else

Only counters whose status is "sited" are emitted; the rest of the region's shelves live in the data, each with why.

The audit is offline and fails closed (the implementer's audit; its tests belong to the test author):

  data       every town in data/towns.json has a counter or a no_counter reason; every gate is a badge flag that
             data/progression.json declares and tools/progression_pack.py plans; a critical-path counter gates on its
             own badge; prices are positive whole dollars and every unit price is ABOVE data's bank sell-back for the
             same item (a shop at or under it is a money printer, PROGRESSION_LADDER 6.4)
  curve      on the critical path, every badge's cumulative ask (one of each option, a pick-one group at its dearest,
             stretch items aside) is at most income_basis.target_ratio of the cumulative income; with the stretch
             items it never exceeds the income; backpack tiers unlock in tier order and cost more as they rise
  recipes    the committed overlay is exactly what `overlay` writes; every Sophisticated Backpacks item a built
             counter sells is off, unless left_craftable says why; nothing sold only by an unbuilt counter is off
  sites      every built keeper stands one above its plan ground (the plaza's graded paving inside the plaza, else
             tools/ambient.py Site: the street paving or the heightmap), on a cell and its four neighbours that no
             lot, anchor, lamp, building (1-block margin), earthwork or dressing piece takes, 3.5+ blocks from every
             other placed NPC and every trader clerk, 3+ from every walked route line, above the sea; on its Mart's
             DOOR side (the Mart anchor's `facing`), inside its town's footprint, off every street's paved width, and
             facing its plaza's centre (R17M: "beside its town's Mart and turned to face its plaza")
  the output every purchase function checks the cooldown first, the gate before the balance, reads before it charges,
             refuses below exactly the price, charges once by the macro, verifies, and gives only after the verify;
             every function passes tools/function_limits.py; every dialogue offers exactly its counter's stock with a
             gated option hidden behind isVisible

  python tools/markets.py build    [--out DIR]                     write the pack (no heightmap needed)
  python tools/markets.py audit    [--source-root R] [--skip-dressing]   exit 1 on any problem
  python tools/markets.py overlay  [--check]                       write (or check) the recipe overlay
  python tools/markets.py ids      --jar-dir <server>/mods         every sold id is an item in an installed jar (read only)
  python tools/markets.py report                                   the curve, badge by badge

What it does NOT cover: the Mart clerks and the Assayer (tools/traders.py, R14), RCT's own trainer-association NPC
(spawnTrainerAssociation, PROGRESSION_LADDER 5.1), and anything a template or a mod sells. A player can still buy
from those; this tool says nothing about them (CLAUDE.md "Our list is not the world").
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import compile_dialogue as CD  # noqa: E402
import function_limits  # noqa: E402

DATA = ROOT / "data" / "markets.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_markets"
NS = "cobblers"
SCORE, COOLDOWN, GAVE = "cobblers_market", "cobblers_market_cd", "cobblers_market_gave"
STORAGE = "%s:markets" % NS
ID = re.compile(r"[a-z0-9_]+")
ITEM = re.compile(r"[a-z0-9_.\-]+:[a-z0-9_/.\-]+")
SB = "sophisticatedbackpacks:"
BACKPACK_TIERS = ["backpack", "copper_backpack", "iron_backpack", "gold_backpack", "diamond_backpack", "netherite_backpack"]
NPC_CLEAR = 3.5        # reapply's npc action counts cobblemon:npc within 2 blocks; the ferry audit uses 2.5 + 0.5
ROUTE_CLEAR = 3.0      # tools/npc_seats.py MIN_ROUTE: an immovable NPC this close to a walked line stands in the road
YAW_SLACK = 15.0
# The ground rule (tools/ground_rule.py): nothing here reads a world; every position comes from the plan and the heightmap.
WORLD_READS: set = set()


class MarketError(SystemExit):
    pass


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def emitted(doc):
    return [c for c in doc["counters"] if c.get("status") == "sited"]


def buy_fn(counter, item):
    return "%s:markets/%s/%s" % (NS, counter["id"], item["id"])


def text(s, color="gray"):
    return json.dumps({"text": s, "color": color}, ensure_ascii=False)


def fill(template, **kw):
    for k, v in kw.items():
        template = template.replace("{%s}" % k, str(v))
    if re.search(r"\{[a-z_]+\}", template):
        raise MarketError("message %r names a placeholder this tool does not fill" % template)
    return template


def money(n):
    return "{:,}".format(int(n))


def option_text(doc, item):
    m = doc["messages"]
    if int(item["count"]) > 1:
        return fill(m["option_count"], item=item["name"], count=item["count"], price=money(item["price"]))
    return fill(m["option"], item=item["name"], price=money(item["price"]))


# ---------------------------------------------------------------------------------------------------- the dialogue
def conversation(doc, counter):
    """(conversation, quest) for one keeper, in data/dialogue.json's and data/quests.json's shape, compiled by
    tools/compile_dialogue.py as it compiles every other conversation. A menu: no cursor, no field."""
    qid = "market_%s" % counter["id"]
    responses, transitions = [], []
    for it in counter["stock"]:
        tid = "buy_%s" % it["id"]
        conds = [{"kind": "flag", "flag": it["gate"]}] if it.get("gate") else []
        transitions.append({"id": tid, "conditions": conds,
                            "effects": [{"kind": "function", "function": buy_fn(counter, it)}]})
        r = {"id": "r_%s" % it["id"], "text": option_text(doc, it),
             "actions": [{"kind": "quest_transition", "transition": tid}, {"kind": "close_dialogue"}]}
        if conds:
            r["visible_when"] = conds[0]
        responses.append(r)
    responses.append({"id": "r_leave", "text": doc["messages"]["leave"], "actions": [{"kind": "close_dialogue"}]})
    keeper = counter["keeper"]
    conv = {"id": "dlg_market_%s" % counter["id"], "quest_id": qid, "npc_id": "npc_market_%s" % counter["id"],
            "npc_name": keeper["name"], "scope": "player", "speakers": {"keeper": keeper["name"]},
            "cursor": {"progression_field": None, "initial_node": "menu"},
            "entry_rules": [{"priority": 10, "when": {"kind": "always"}, "node": "menu"}],
            "nodes": [{"id": "menu", "kind": "choice", "speaker": "keeper", "text": keeper["greeting"],
                       "responses": responses}]}
    quest = {"id": qid, "progression_field_refs": [], "transitions": transitions, "rewards": []}
    return conv, quest


# ---------------------------------------------------------------------------------------------------- the purchase
def buy_lines(doc, counter, it):
    m = doc["messages"]
    price, count = int(it["price"]), int(it["count"])
    kw = dict(item=it["name"], price=money(price), count=count)
    out = ["# Generated by tools/markets.py from data/markets.json: %s, %s x%d for $%d (as and at the player, from the "
           "keeper's dialogue)" % (counter["id"], it["item"], count, price),
           "# a second submit of the same click, or a purchase straight after one, does nothing",
           "execute store result score #now %s run time query gametime" % SCORE,
           "execute if score @s %s > #now %s run return 0" % (COOLDOWN, SCORE)]
    if it.get("gate"):
        msg = fill(m["gated"], requirement=doc["badges"][it["gate"]], **kw)
        out.append("execute unless entity @s[advancements={%s:flag/%s=true}] run return run tellraw @s %s"
                   % (NS, it["gate"], text(msg, "gold")))
    before, _, after = m["short"].partition("{balance}")
    refuse = json.dumps([{"text": "", "color": "gold"}, {"text": fill(before, **kw)},
                         {"score": {"name": "@s", "objective": SCORE}}, {"text": fill(after, **kw)}], ensure_ascii=False)
    out += ["# the price, $%d: read the balance first (EXP-040), refuse if it is short, nothing taken" % price,
            "execute store result score @s %s run cobbledollars query @s" % SCORE,
            "execute unless score @s %s matches %d.. run return run tellraw @s %s" % (SCORE, price, refuse),
            "# from here the click is spent: a second one inside the cooldown is refused above",
            "scoreboard players operation @s %s = #now %s" % (COOLDOWN, SCORE),
            "scoreboard players add @s %s %d" % (COOLDOWN, int(doc["purchase"]["cooldown_ticks"])),
            "data modify storage %s charge.amount set value %d" % (STORAGE, price),
            "function %s:markets/charge with storage %s charge" % (NS, STORAGE),
            "# the charge must have taken exactly the price, or nothing is given",
            "execute store result score #after %s run cobbledollars query @s" % SCORE,
            "scoreboard players operation #want %s = @s %s" % (SCORE, SCORE),
            "scoreboard players remove #want %s %d" % (SCORE, price),
            "execute unless score #after %s = #want %s run return run tellraw @s %s"
            % (SCORE, SCORE, text(fill(m["charge_failed"], **kw), "red")),
            "# the give, as the player (EXP-022 bug 1); its success into an objective that exists (EXP-022 bug 2)",
            "scoreboard objectives add %s dummy" % GAVE,
            "scoreboard players set @s %s 0" % GAVE,
            "execute store success score @s %s run give @s %s %d" % (GAVE, it["item"], count),
            "execute unless score @s %s matches 1 run function %s:markets/refund with storage %s charge" % (GAVE, NS, STORAGE),
            "execute unless score @s %s matches 1 run return run tellraw @s %s" % (GAVE, text(fill(m["give_failed"], **kw), "red")),
            "tellraw @s %s" % text(fill(m["paid"], **kw))]
    return out


def build(doc):
    """{relative path in the pack: content (list of lines, or a JSON object)} and the NPCs to place."""
    files = {"pack.mcmeta": {"pack": {"pack_format": 48, "description": "Cobblers town markets (generated by tools/markets.py)"}},
             "data/minecraft/tags/function/load.json": {"values": ["%s:markets/load" % NS]}}
    fn = lambda rel: "data/%s/function/markets/%s.mcfunction" % (NS, rel)
    files[fn("load")] = ["# the markets' scores: the balance read, each player's cooldown after a click, and the give's success",
                         "scoreboard objectives add %s dummy" % SCORE, "scoreboard objectives add %s dummy" % COOLDOWN,
                         "scoreboard objectives add %s dummy" % GAVE]
    # the blackout charge's macro, proven in game (EXP-042 run 1: $725 to $652), and its inverse for a failed give
    files[fn("charge")] = ["$cobbledollars remove @s $(amount)"]
    files[fn("refund")] = ["$cobbledollars add @s $(amount)"]
    fields = {f["id"]: f for f in json.loads(
        (ROOT / "data" / "progression.json").read_text(encoding="utf-8")).get("quest_fields") or []}
    npcs = []
    for c in emitted(doc):
        for it in c["stock"]:
            files[fn("%s/%s" % (c["id"], it["id"]))] = buy_lines(doc, c, it)
        conv, quest = conversation(doc, c)
        got = CD.compile_conversation(conv, {quest["id"]: quest}, fields)
        clash = [k for k in got if k in files]
        if clash:
            raise MarketError("%s writes %s twice" % (c["id"], clash))
        files.update(got)
        npcs.append((conv["id"], tuple(c["at"]), "%s:%s" % (NS, conv["npc_id"]), c["yaw"]))
    return files, npcs


def npc_placements(doc=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for tools/reapply.py's "npc" action, from the committed data."""
    doc = doc or load()
    return [("dlg_market_%s" % c["id"], tuple(c["at"]), "%s:npc_market_%s" % (NS, c["id"]), c["yaw"]) for c in emitted(doc)]


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(content) + "\n" if isinstance(content, list) else json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        f.write_text(body, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------------------------------- the recipes
def disabled_set(doc):
    """Every Sophisticated Backpacks item a BUILT counter sells, less the declared left_craftable."""
    keep = set((doc["recipe_overlay"].get("left_craftable") or {}).keys())
    return sorted({it["item"] for c in emitted(doc) for it in c["stock"] if it["item"].startswith(SB)} - keep)


def overlay_text(doc):
    ro = doc["recipe_overlay"]
    base = (ROOT / ro["base"]).read_text(encoding="utf-8")
    out = base
    for item in disabled_set(doc):
        on, off = '"%s|true"' % item, '"%s|false"' % item
        n = out.count(on)
        if n != 1:
            raise MarketError("overlay: %s appears %d times as enabled in %s, not once" % (item, n, ro["base"]))
        out = out.replace(on, off)
    return out


# ---------------------------------------------------------------------------------------------------- the audit
def bank_prices():
    """{item: sell price} from the base pack's bank, overridden by ours where one exists."""
    out = {}
    for p in (ROOT / "base-pack/cobbleverse/config/cobbledollars/bank.json", ROOT / "modpack/config/cobbledollars/bank.json"):
        if p.is_file():
            for e in json.loads(p.read_text(encoding="utf-8")).get("bank") or []:
                out[e["item"]] = int(e["price"])
    return out


def static_problems(doc, planned_flags, towns, traders):
    out = []
    town_ids = [t["id"] for t in towns]
    covered = [c.get("town") for c in doc["counters"]] + [n.get("town") for n in doc.get("no_counter") or []]
    for t in town_ids:
        if covered.count(t) != 1:
            out.append("town %s: %d entries across counters and no_counter, not 1" % (t, covered.count(t)))
    for t in covered:
        if t not in town_ids:
            out.append("%r is not a town in data/towns.json" % t)
    for n in doc.get("no_counter") or []:
        if not n.get("why"):
            out.append("no_counter %s: no why" % n.get("town"))
    badges = doc.get("badges") or {}
    for f in badges:
        if f not in planned_flags:
            out.append("badge flag %s is not planned by tools/progression_pack.py (no advancement)" % f)
    bank = bank_prices()
    seen = set()
    for c in doc["counters"]:
        cid = c.get("id") or ""
        if not ID.fullmatch(cid) or cid in seen:
            out.append("counter id %r is malformed or repeated" % cid)
        seen.add(cid)
        if c.get("status") not in ("sited", "unsited"):
            out.append("counter %s: status %r" % (cid, c.get("status")))
        if c.get("status") == "unsited" and not c.get("unsited_why"):
            out.append("counter %s: unsited with no unsited_why" % cid)
        if c.get("path") not in ("critical", "off_path"):
            out.append("counter %s: path %r" % (cid, c.get("path")))
        tr = c.get("near_trader")
        if tr is not None and (tr not in traders or traders[tr]["settlement"] != c["town"]):
            out.append("counter %s: near_trader %r is not a trader in %s" % (cid, tr, c["town"]))
        if c.get("status") == "sited":
            if tr is None:
                out.append("counter %s: sited with no near_trader to stand beside" % cid)
            if not (isinstance(c.get("at"), list) and len(c["at"]) == 3 and isinstance(c.get("yaw"), (int, float))):
                out.append("counter %s: sited without at [x, y, z] and yaw" % cid)
        k = c.get("keeper") or {}
        if not k.get("name") or not k.get("greeting"):
            out.append("counter %s: keeper without name or greeting" % cid)
        if not c.get("stock"):
            out.append("counter %s: no stock" % cid)
        own = "gym%d_cleared" % c["badge"] if c.get("path") == "critical" and c.get("badge") else None
        ids = set()
        for it in c.get("stock") or []:
            where = "counter %s item %s" % (cid, it.get("id"))
            if not ID.fullmatch(it.get("id") or "") or it["id"] in ids:
                out.append("%s: id malformed or repeated" % where)
            ids.add(it.get("id"))
            if not ITEM.fullmatch(it.get("item") or ""):
                out.append("%s: item %r is not ns:path" % (where, it.get("item")))
            if not it.get("name") or not it.get("why"):
                out.append("%s: no name or why" % where)
            cnt, price = it.get("count"), it.get("price")
            if not (isinstance(cnt, int) and 1 <= cnt <= 64):
                out.append("%s: count %r" % (where, cnt))
                continue
            if not (isinstance(price, int) and price > 0):
                out.append("%s: price %r is not a positive whole number" % (where, price))
                continue
            sell = bank.get(it["item"])
            if sell is not None and price / cnt <= sell:
                out.append("%s: $%s each is not above the bank's sell-back of $%d: buy and sell is free money"
                           % (where, money(price / cnt), sell))
            g = it.get("gate")
            if g is not None and g not in badges:
                out.append("%s: gate %r is not a declared badge" % (where, g))
            if own and g != own:
                out.append("%s: a critical-path counter at badge %d gates on %r, not its own %s" % (where, c["badge"], g, own))
            if c.get("path") == "critical" and c.get("badge") == 0 and g is not None:
                out.append("%s: Pallet's shelf is gated" % where)
            if it.get("strand") not in ("convenience", "power"):
                out.append("%s: strand %r" % (where, it.get("strand")))
    # backpack tiers: in tier order along the critical path, and dearer as they rise
    tier_at = {}
    for c in doc["counters"]:
        if c.get("path") != "critical":
            continue
        for it in c["stock"]:
            name = it["item"][len(SB):] if it["item"].startswith(SB) else None
            if name in BACKPACK_TIERS:
                if name in tier_at:
                    out.append("backpack tier %s is sold at two critical counters" % name)
                tier_at[name] = (c["badge"], it["price"])
    sold = [t for t in BACKPACK_TIERS if t in tier_at]
    for lo, hi in zip(sold, sold[1:]):
        if not (tier_at[lo][0] < tier_at[hi][0] and tier_at[lo][1] < tier_at[hi][1]):
            out.append("backpack tier %s (badge %d, $%d) does not come before and cost less than %s (badge %d, $%d)"
                       % (lo, tier_at[lo][0], tier_at[lo][1], hi, tier_at[hi][0], tier_at[hi][1]))
    # no item whose recipe goes off may be sold only by an unbuilt counter
    off = set(disabled_set(doc))
    unbuilt = {it["item"] for c in doc["counters"] if c.get("status") != "sited" for it in c["stock"]}
    built = {it["item"] for c in emitted(doc) for it in c["stock"]}
    for item in sorted((unbuilt - built) & off):
        out.append("%s: its recipe is off but only an unbuilt counter sells it" % item)
    return out


def curve(doc):
    """[(badge, cumulative ask without stretch, with every stretch item due by then, cumulative income, ratio)] on
    the critical path. A stretch item counts from its affordable_by badge: before that it is meant to be out of reach
    (decision B7, 'price as the gate')."""
    basis = doc["income_basis"]
    rows, cum, cum_s = [], 0, 0
    stretch = [it for c in doc["counters"] if c.get("path") == "critical" for it in c["stock"] if it.get("stretch")]
    for b in range(0, 9):
        cum_s += sum(it["price"] for it in stretch if it.get("affordable_by") == b)
        for c in doc["counters"]:
            if c.get("path") != "critical" or c.get("badge") != b:
                continue
            groups = {}
            for it in c["stock"]:
                if it.get("stretch"):
                    continue
                key = it.get("group") or it["id"]
                groups[key] = max(groups.get(key, 0), it["price"])
            cum += sum(groups.values())
        if b == 0:
            continue
        inc = int(basis["cumulative_by_badge"][str(b)])
        rows.append((b, cum, cum + cum_s, inc, cum / inc))
    return rows


def curve_problems(doc):
    out = []
    target = float(doc["income_basis"]["target_ratio"])
    for b, ask, ask_s, inc, ratio in curve(doc):
        if ratio > target:
            out.append("badge %d: the critical path asks $%s of $%s earned, %.2f of income, over the declared %.2f"
                       % (b, money(ask), money(inc), ratio, target))
        if ask_s > inc:
            out.append("badge %d: with the stretch items due by then the critical path asks $%s, more than the $%s "
                       "earned" % (b, money(ask_s), money(inc)))
    for c in doc["counters"]:
        for it in c["stock"]:
            if it.get("stretch") and not (isinstance(it.get("affordable_by"), int) and
                                          c.get("badge") is not None and c["badge"] < it["affordable_by"] <= 8):
                out.append("counter %s item %s: a stretch item needs affordable_by, a badge after its own and at most 8"
                           % (c["id"], it["id"]))
    return out


def overlay_problems(doc):
    out = []
    ro = doc["recipe_overlay"]
    path = ROOT / ro["file"]
    try:
        want = overlay_text(doc)
    except MarketError as e:
        return [str(e)]
    if not path.is_file():
        return ["%s does not exist: run python tools/markets.py overlay" % ro["file"]]
    if path.read_text(encoding="utf-8") != want:
        out.append("%s is not what the data writes: run python tools/markets.py overlay" % ro["file"])
    for item in (ro.get("left_craftable") or {}):
        if not any(it["item"] == item for c in doc["counters"] for it in c["stock"]):
            out.append("left_craftable %s is sold nowhere: the entry is stale" % item)
    return out


def other_npcs(doc, traders):
    import ferries as F
    import npc_seats as NS_
    out = [(w, tuple(p)) for w, p in F.other_npcs()]
    out += [("ferryman %s" % n[0], tuple(n[1])) for n in F.npc_placements(F.load())]
    out += [("seat %s" % n[2], tuple(n[1])) for n in NS_.placements()]
    out += [("trader %s" % t, (v["position"]["x"], v["position"]["y"], v["position"]["z"])) for t, v in traders.items()]
    return out


def site_problems(doc, traders, source_root=None, skip_dressing=False):
    import ambient as A
    import ground as G
    import npc_seats as NS_
    out, report = [], []
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    dressing = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
    towns = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}
    if skip_dressing:
        report.append("NOT CHECKED: the dressing pieces (--skip-dressing); run the audit in a full checkout")
        dressing = {"towns": {}}
    rules = A.load()["rules"]
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    sea = int(world["vertical"]["sea_level"])
    base = G.Ground(source_root)
    route = NS_._route_points()
    others = other_npcs(doc, traders)
    built = emitted(doc)
    sites = {}
    for c in built:
        where = "counter %s at %s" % (c["id"], c["at"])
        x, y, z = c["at"]
        s = c["town"]
        if s not in sites:
            try:
                sites[s] = A.Site(s, base, placements, dressing, None, rules)
            except SystemExit as e:  # town_dressing.town_plan exits when derived/towns/<s>_plan.json is missing
                sites[s] = e
        site = sites[s]
        if isinstance(site, SystemExit):
            out.append("%s: the town's site model cannot be built: %s" % (where, str(site)[:200]))
            continue
        plan = (placements["settlements"].get(s) or {}).get("plan") or {}
        want_y = stand_y(site, plan, x, z)
        if y != want_y:
            out.append("%s: stands at y%d, but the plan's ground there puts it at y%d" % (where, y, want_y))
        out += frontage_problems(where, c, plan, towns.get(s), site)
        if y - 1 < sea:
            out.append("%s: its ground y%d is under the sea level y%d" % (where, y - 1, sea))
        for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            why = site.blocked(x + dx, z + dz)
            if why:
                out.append("%s: the cell (%d, %d) is taken by %s" % (where, x + dx, z + dz, why))
        for what, q in others + [("keeper %s" % o["id"], tuple(o["at"])) for o in built if o is not c]:
            if math.dist((x, y, z), q) < NPC_CLEAR:
                out.append("%s: %.1f blocks from %s at %s" % (where, math.dist((x, y, z), q), what, q))
        if len(route):
            d = float(min(((route[:, 0] - x) ** 2 + (route[:, 1] - z) ** 2) ** 0.5))
            if d < ROUTE_CLEAR:
                out.append("%s: %.1f blocks from a walked route line" % (where, d))
        tr = traders[c["near_trader"]]["position"]
        report.append("%s: ground y%d, cell and neighbours free, %.0f blocks from its clerk"
                      % (where, y - 1, math.dist((x, z), (tr["x"], tr["z"]))))
    return out, report


def in_rect(rect, x, z):
    return min(rect[0], rect[2]) <= x <= max(rect[0], rect[2]) and min(rect[1], rect[3]) <= z <= max(rect[1], rect[3])


def stand_y(site, plan, x, z):
    """The y a keeper stands at: one above the plaza's paving inside the plaza (the town plan grades it flat to
    plan.plaza.y, so the heightmap is not its surface there), else one above the street paving or the heightmap."""
    pz = plan.get("plaza") or {}
    if pz.get("rect") and pz.get("y") is not None and in_rect(pz["rect"], x, z):
        return int(pz["y"]) + 1
    return site.y(x, z)


def plaza_yaw(plan, x, z):
    """The yaw (Minecraft's: 0 = +z, 90 = -x) from the centre of cell (x, z) to the centre of the town's plaza."""
    r = plan["plaza"]["rect"]
    cx = (min(r[0], r[2]) + max(r[0], r[2]) + 1) / 2.0
    cz = (min(r[1], r[3]) + max(r[1], r[3]) + 1) / 2.0
    return math.degrees(math.atan2(-(cx - x - 0.5), cz - z - 0.5))


FACING = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def frontage_problems(where, c, plan, town, site):
    """R17M's intent: each keeper 'beside its town's Mart and turned to face its plaza'. So: on the Mart's DOOR side
    (the Mart anchor's `facing`, data/placements.json) and not past its far wall, inside the town's footprint
    (data/towns.json), off every street's paved width (a keeper there stands in the road), and facing the plaza."""
    out = []
    x, _y, z = c["at"]
    marts = [a for a in plan.get("anchors") or [] if a.get("role") == "pokemart"]
    if len(marts) != 1:
        return ["%s: its town plan has %d Mart anchors, not 1, so its door side is unknown" % (where, len(marts))]
    a = marts[0]
    f = FACING.get(a.get("facing"))
    if f is None:
        return ["%s: the Mart anchor %s has no facing" % (where, a["id"])]
    x0, z0, x1, z1 = a["rect"]
    x0, x1, z0, z1 = min(x0, x1), max(x0, x1), min(z0, z1), max(z0, z1)
    front = {(-1, 0): x < x0, (1, 0): x > x1, (0, -1): z < z0, (0, 1): z > z1}[f]
    if not front:
        out.append("%s: not on its Mart %s's door side (%s of %s)" % (where, a["id"], a["facing"], a["rect"]))
    fp = (town or {}).get("footprint")
    if not fp or not (fp["min_x"] <= x <= fp["max_x"] and fp["min_z"] <= z <= fp["max_z"]):
        out.append("%s: outside its town's footprint %s" % (where, fp))
    if (x, z) in site.street_y:
        out.append("%s: stands on a street's paved width" % where)
    if not (plan.get("plaza") or {}).get("rect"):
        out.append("%s: its town has no plaza to face" % where)
    else:
        want = plaza_yaw(plan, x, z)
        if abs((c["yaw"] - want + 180) % 360 - 180) > YAW_SLACK:
            out.append("%s: faces yaw %s, but its plaza's centre is at yaw %.0f" % (where, c["yaw"], want))
    return out


def output_problems(doc, files):
    out = []
    fn = lambda rel: "data/%s/function/markets/%s.mcfunction" % (NS, rel)
    if files.get(fn("charge")) != ["$cobbledollars remove @s $(amount)"]:
        out.append("the charge macro is not the blackout's proven form")
    if files.get(fn("refund")) != ["$cobbledollars add @s $(amount)"]:
        out.append("the refund macro is not the documented add")
    for c in emitted(doc):
        for it in c["stock"]:
            path = fn("%s/%s" % (c["id"], it["id"]))
            body = files.get(path)
            if body is None:
                out.append("%s: no purchase function" % path)
                continue
            cmds = [x for x in body if x and not x.startswith("#")]
            where = lambda pred: [i for i, x in enumerate(cmds) if pred(x)]
            cd_check = where(lambda x: x.startswith("execute if score @s %s > #now" % COOLDOWN))
            gates = where(lambda x: "advancements={" in x)
            query = where(lambda x: "cobbledollars query" in x)
            refuse = where(lambda x: x.startswith("execute unless score @s %s matches" % SCORE))
            cd_set = where(lambda x: x.startswith("scoreboard players operation @s %s" % COOLDOWN))
            charge = where(lambda x: x.startswith("function %s:markets/charge" % NS))
            verify = where(lambda x: x.startswith("execute unless score #after %s = #want" % SCORE))
            give = where(lambda x: " run give @s " in x)
            refund = where(lambda x: "markets/refund" in x)
            if not cd_check or cd_check[0] != min(cd_check + gates + query + charge + give):
                out.append("%s: the cooldown is not checked before everything else" % path)
            if bool(gates) != bool(it.get("gate")) or len(gates) > 1:
                out.append("%s: %d gate checks for gate %r" % (path, len(gates), it.get("gate")))
            if gates and "flag/%s=true" % it["gate"] not in cmds[gates[0]]:
                out.append("%s: checks the wrong flag: %s" % (path, cmds[gates[0]]))
            if len(charge) != 1 or len(give) != 1:
                out.append("%s: %d charges and %d gives, not 1 and 1" % (path, len(charge), len(give)))
                continue
            if gates and query and gates[0] > query[0]:
                out.append("%s: the gate is checked after the balance is read" % path)
            if not (len(query) == 2 and refuse and verify and query[0] < refuse[0] < charge[0] < query[1] < verify[0] < give[0]):
                out.append("%s: not read, refuse-if-short, charge, re-read, verify, then give" % path)
            if refuse and cmds[refuse[0]].split()[6] != "%d.." % it["price"]:
                out.append("%s: refuses below %s, not the price %d" % (path, cmds[refuse[0]].split()[6], it["price"]))
            amount = [x for x in cmds if x.startswith("data modify storage %s charge.amount set value" % STORAGE)]
            if amount != ["data modify storage %s charge.amount set value %d" % (STORAGE, it["price"])]:
                out.append("%s: charges %s, not the price %d" % (path, amount, it["price"]))
            if not (cd_set and cd_set[0] < charge[0]):
                out.append("%s: the cooldown is not set before the charge" % path)
            if cmds[give[0]] != "execute store success score @s %s run give @s %s %d" % (GAVE, it["item"], it["count"]):
                out.append("%s: gives %r, not %s x%d" % (path, cmds[give[0]], it["item"], it["count"]))
            if not (refund and refund[0] > give[0]):
                out.append("%s: no refund after a failed give" % path)
    for rel, body in files.items():
        if rel.endswith(".mcfunction"):
            refused = function_limits.check_lines(body, rel)
            if refused:
                out.append("%s: %d command(s) the server would refuse" % (rel, len(refused)))
    for c in emitted(doc):
        dlg = files.get("data/%s/dialogues/dlg_market_%s.json" % (NS, c["id"]))
        npc = files.get("data/%s/npcs/npc_market_%s.json" % (NS, c["id"]))
        if dlg is None or npc is None:
            out.append("counter %s: no compiled dialogue or NPC class" % c["id"])
            continue
        got = set()
        for o in dlg["pages"][0]["input"]["options"]:
            m = re.search(r"function %s:markets/([a-z0-9_]+)/([a-z0-9_]+)'" % NS, o["action"])
            if m:
                got.add((m.group(1), m.group(2), "isVisible" in o))
        want = {(c["id"], it["id"], bool(it.get("gate"))) for it in c["stock"]}
        if got != want:
            out.append("counter %s: its dialogue offers %s, the data %s" % (c["id"], sorted(got), sorted(want)))
    return out


def collision_problems(doc):
    """No conversation, quest or NPC id this tool emits may be authored elsewhere: compile_dialogue --all writes the
    same namespace, and a clash would silently replace one keeper or resident with the other."""
    out = []
    dlg = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    taken = {c["id"] for c in dlg.get("conversations") or []} | {c.get("npc_id") for c in dlg.get("conversations") or []}
    for c in doc["counters"]:
        for k in ("dlg_market_%s" % c["id"], "npc_market_%s" % c["id"]):
            if k in taken:
                out.append("%s is also authored in data/dialogue.json" % k)
    return out


def audit(doc, source_root=None, skip_dressing=False):
    import progression_pack as PP
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    planned = {f["id"] for f in PP.plan(prog, placements=placements)["flags"]}
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    traders = {t["id"]: t for t in json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))["traders"]}
    problems = static_problems(doc, planned, towns, traders) + collision_problems(doc)
    if problems:
        return problems, []
    problems += curve_problems(doc) + overlay_problems(doc)
    files, _ = build(doc)
    problems += output_problems(doc, files)
    p, report = site_problems(doc, traders, source_root, skip_dressing)
    return problems + p, report


# ---------------------------------------------------------------------------------------------------- the jars
def jar_items(jar_dir):
    """{item id} from every jar's lang files: item.<ns>.<path> and block.<ns>.<path> keys. Read only."""
    ids = set()
    for jp in sorted(Path(jar_dir).glob("*.jar")):
        with zipfile.ZipFile(jp) as z:
            for n in z.namelist():
                if re.fullmatch(r"assets/[^/]+/lang/en_us\.json", n):
                    try:
                        lang = json.loads(z.read(n).decode("utf-8", "replace"))
                    except ValueError:
                        continue
                    for k in lang:
                        m = re.fullmatch(r"(?:item|block)\.([a-z0-9_.\-]+)\.([a-z0-9_/.\-]+)", k)
                        if m:
                            ids.add("%s:%s" % m.groups())
    return ids


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default=str(DATA))
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(DEFAULT_OUT))
    b.add_argument("--source-root", help="unused: the build needs no heightmap (accepted so prepare passes it alike)")
    a = sub.add_parser("audit")
    a.add_argument("--source-root")
    a.add_argument("--skip-dressing", action="store_true",
                   help="for a worktree without derived/: the dressing pieces are reported NOT CHECKED")
    o = sub.add_parser("overlay")
    o.add_argument("--check", action="store_true")
    j = sub.add_parser("ids")
    j.add_argument("--jar-dir", required=True)
    sub.add_parser("report")
    args = p.parse_args(argv)
    doc = load(args.data)
    if args.cmd == "build":
        files, npcs = build(doc)
        write(files, args.out)
        print("wrote %d files to %s: %d counters built of %d, %d keepers"
              % (len(files), args.out, len(emitted(doc)), len(doc["counters"]), len(npcs)))
        return 0
    if args.cmd == "overlay":
        path = ROOT / doc["recipe_overlay"]["file"]
        want = overlay_text(doc)
        if args.check:
            ok = path.is_file() and path.read_text(encoding="utf-8") == want
            print("overlay %s: %s" % (path, "matches" if ok else "DIFFERS"))
            return 0 if ok else 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(want, encoding="utf-8", newline="\n")
        print("wrote %s: %d recipes off (%s)" % (path, len(disabled_set(doc)), ", ".join(disabled_set(doc))))
        return 0
    if args.cmd == "ids":
        have = jar_items(args.jar_dir)
        sold = sorted({it["item"] for c in doc["counters"] for it in c["stock"]})
        missing = [i for i in sold if i not in have]
        for i in missing:
            print("PROBLEM %s is not an item in any jar in %s" % (i, args.jar_dir))
        print("ids: %d sold, %d found, %d missing" % (len(sold), len(sold) - len(missing), len(missing)))
        return 1 if missing else 0
    if args.cmd == "report":
        for bdg, ask, ask_s, inc, ratio in curve(doc):
            print("badge %d: ask $%s (with stretch $%s) of $%s earned: %.2f" % (bdg, money(ask), money(ask_s), money(inc), ratio))
        for c in doc["counters"]:
            if c.get("path") == "off_path":
                print("off path %s (%s, %s): $%s" % (c["id"], c["town"], c["status"], money(sum(it["price"] for it in c["stock"]))))
        return 0
    problems, report = audit(doc, args.source_root, args.skip_dressing)
    for line in report:
        print(line)
    for pr in problems:
        print("PROBLEM", pr)
    print("market audit: %d problems" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
