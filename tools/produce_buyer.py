#!/usr/bin/env python
"""The Produce Buyer: farm goods sold by the crate to a dialogue NPC, on a price that falls with every badge and a
per-player allowance that resets each leg. Generated from data/produce_buyer.json into the world-local datapack
build/datapacks/cobblers_produce_buyer; the buyer is placed by tools/reapply.py R18PB.

The owner, 2026-10-10: "farm products pay the early game on a declining price. AFK-farmable food must not pay for
everything -- cap it or exclude it." docs/mechanics/ECONOMY_OVERHAUL.md 2.2 and BUILD LIST U2. The bank (tools/bank.py)
no longer buys anything an unattended farm makes (data/bank.json afk_rule); this is where those goods sell instead.

Every piece is one already in use (tools/ferries.py is the pattern, read for it):
  the buyer      a Cobblemon NPC whose class opens a dialogue compiled in memory by tools/compile_dialogue.py's
                 compile_conversation (the ferryman's shape): one page, one option per crate kind, and "Not today."
  the sale       a function run as and at the player by the option (compile_dialogue "function"):
                   1. a second submit inside the cooldown does nothing
                   2. the badge count is the number of cobblers:flag/gymN_cleared advancements the player holds; when it
                      differs from the count of the player's last sale the allowance (cob_pb_sold) resets: per leg
                   3. the price and the leg's crates come from the schedule's row for that count; a price of 0 refuses
                   4. a spent allowance refuses
                   5. count the crate's items (`clear @s <item> 0`, ASSUMED to count without removing: EXP-061)
                      and refuse when short, nothing taken
                   6. the click is spent (the cooldown starts); read the balance (`cobbledollars query @s`)
                   7. TAKE the crate (`clear @s <item> <count>`); unless exactly <count> went, short_take counts the
                      crate, records the taken share of the price as owed (cob_pb_owed) and stops, nothing paid
                   8. COUNT the crate as sold (cob_pb_sold) before anything can return: the cap fails closed
                   9. PAY through `$cobbledollars give @s $(amount)` and re-read the balance: unless it rose by exactly
                      the price, record the price as owed (cob_pb_owed) and say so
The checks (offline, fail closed; the independent audit is test-author's tools/produce_buyer_audit.py):
  static   the schedule covers badges 0..8 once each, never rises, ends at 0, and sums to campaign_cap; the badge flags
           are flags tools/progression_pack.py plans; every crate has a positive count and valid ids; no crate item
           is still bought by the bank (data/bank.json afk_rule moved them here); no authored seller sells a crate item
           at or under the crate's top price / count per unit (tools/bank.py sell_points)
  output   every sale counts before it takes, takes before it pays, counts the crate against the allowance before any
           return after the take, pays once and verifies after it, charges nothing
           (`cobbledollars remove` never appears) and passes tools/function_limits.py
  seat     each site's spot recomputed from its anchor's plan (tools/apricorn_farm.py plan() and spot(), the canonical
           heightmap, never a world) equals the site's expected_at, off the farm's paths and 3.5 blocks from its other
           NPCs and from every walked route line by 3

  python tools/produce_buyer.py build  [--out DIR]          write the pack (no heightmap needed)
  python tools/produce_buyer.py check  [--source-root R]    static, output and seat checks; exit 1 on a problem

What it does NOT cover: whether the dialogue opens and the function runs in game (EXP-061), a seller a donor template
places that no data file names, and the trader templates' shops unless tools/bank.py is given a server dir.
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
NS = "cobblers"
FOLDER = "produce_buyer"
ITEM = re.compile(r"[a-z0-9_.\-]+:[a-z0-9_/.\-]+")
ID = re.compile(r"[a-z0-9_]+")
NPC_CLEAR = 3.5     # tools/markets.py NPC_CLEAR: reapply's npc action counts cobblemon:npc within 2 blocks
MIN_ROUTE = 3.0     # tools/npc_seats.py MIN_ROUTE
WORLD_READS: set = set()   # the ground rule: every seat comes from a plan over the canonical heightmap


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


def rows(doc):
    """[(lo, hi, price, crates)] from schedule.rows."""
    return [(int(r["badges"][0]), int(r["badges"][1]), int(r["price"]), int(r["crates"])) for r in doc["schedule"]["rows"]]


def schedule_at(doc, badges):
    for lo, hi, price, crates in rows(doc):
        if lo <= badges <= hi:
            return price, crates
    return None


def campaign_total(doc):
    return sum((hi - lo + 1) * price * crates for lo, hi, price, crates in rows(doc))


# ---------------------------------------------------------------------------------------------------------- the pack
def leg_lines(doc):
    """cobblers:produce_buyer/leg, as the player: #badges, the allowance reset on a changed count, #price and #cap."""
    S = doc["runtime"]["scores"]
    T = S["temp"]
    out = ["# Generated by tools/produce_buyer.py from data/produce_buyer.json: the player's leg, as the player",
           "# the badge count: one per progression flag the player holds (tools/progression_pack.py's advancements)",
           "scoreboard players set #badges %s 0" % T]
    for f in doc["badge_flags"]:
        out.append("execute if entity @s[advancements={%s:flag/%s=true}] run scoreboard players add #badges %s 1"
                   % (NS, f, T))
    out += ["# a new leg (the count changed since this player's last sale, or no sale yet): the allowance resets",
            "execute unless score @s %s = #badges %s run scoreboard players set @s %s 0" % (S["leg"], T, S["sold"]),
            "scoreboard players operation @s %s = #badges %s" % (S["leg"], T),
            "scoreboard players add @s %s 0" % S["sold"],
            "# the schedule's row for this count: the price per crate and the crates the leg allows",
            "scoreboard players set #price %s 0" % T,
            "scoreboard players set #cap %s 0" % T]
    for lo, hi, price, crates in rows(doc):
        rng = "%d" % lo if lo == hi else "%d..%d" % (lo, hi)
        out.append("execute if score #badges %s matches %s run scoreboard players set #price %s %d" % (T, rng, T, price))
        out.append("execute if score #badges %s matches %s run scoreboard players set #cap %s %d" % (T, rng, T, crates))
    return out


def sell_lines(doc, crate):
    S, rt, m = doc["runtime"]["scores"], doc["runtime"], doc["messages"]
    T = S["temp"]
    n = int(crate["count"])
    item = predicate(crate)
    store = doc["runtime"]["storage"]
    short = json.dumps([{"text": "", "color": "gold"}, {"text": fill(m["short"], count=n, label=crate["label"])},
                        {"score": {"name": "#have", "objective": T}}, {"text": m["short_after"]}], ensure_ascii=False)
    paid = json.dumps([{"text": "", "color": "green"}, {"text": fill(m["paid"], label=crate["label"])},
                       {"text": "+$"}, {"score": {"name": "#price", "objective": T}},
                       {"text": ". Crates left before your next badge: "}, {"score": {"name": "#left", "objective": T}}],
                      ensure_ascii=False)
    return [
        "# Generated by tools/produce_buyer.py from data/produce_buyer.json: sell a crate of %d %s (as and at the "
        "player, from the Produce Buyer's dialogue)" % (n, crate["label"]),
        "# 1. a second submit of the same click, or a sale straight after one, does nothing",
        "execute store result score #now %s run time query gametime" % T,
        "execute if score @s %s > #now %s run return 0" % (S["cooldown"], T),
        "# 2-3. the leg: badges, the allowance reset, the price and the cap",
        "function %s" % fn_id("leg"),
        "execute if score #price %s matches ..0 run return run tellraw @s %s" % (T, text(m["closed"], "gold")),
        "# 4. the leg's allowance",
        "execute if score @s %s >= #cap %s run return run tellraw @s %s" % (S["sold"], T, text(m["spent"], "gold")),
        "# 5. count the crate's items without taking any (clear with a count of 0), refuse when short",
        "execute store result score #have %s run clear @s %s 0" % (T, item),
        "execute unless score #have %s matches %d.. run return run tellraw @s %s" % (T, n, short),
        "# 6. from here the click is spent; the balance before",
        "scoreboard players operation @s %s = #now %s" % (S["cooldown"], T),
        "scoreboard players add @s %s %d" % (S["cooldown"], int(rt["cooldown_ticks"])),
        "execute store result score #before %s run cobbledollars query @s" % T,
        "scoreboard players set #n %s %d" % (T, n),
        "# 7. TAKE the crate first: exactly %d, or nothing is paid (a short take counts the crate and records the "
        "taken share as owed: %s)" % (n, fn_id("short_take")),
        "execute store result score #took %s run clear @s %s %d" % (T, item, n),
        "execute unless score #took %s matches %d run return run function %s" % (T, n, fn_id("short_take")),
        "# 8. COUNT the crate against the leg's allowance before anything below can return: the cap fails closed",
        "scoreboard players add @s %s 1" % S["sold"],
        "# 9. PAY the schedule's price, then the balance must have risen by exactly that",
        "execute store result storage %s pay.amount int 1 run scoreboard players get #price %s" % (store, T),
        "function %s with storage %s pay" % (fn_id("pay"), store),
        "execute store result score #after %s run cobbledollars query @s" % T,
        "scoreboard players operation #want %s = #before %s" % (T, T),
        "scoreboard players operation #want %s += #price %s" % (T, T),
        "execute unless score #after %s = #want %s run scoreboard players operation @s %s += #price %s"
        % (T, T, S["owed"], T),
        "execute unless score #after %s = #want %s run return run tellraw @s %s" % (T, T, text(m["pay_failed"], "red")),
        "scoreboard players operation #left %s = #cap %s" % (T, T),
        "scoreboard players operation #left %s -= @s %s" % (T, S["sold"]),
        "tellraw @s %s" % paid]


def short_take_lines(doc):
    """cobblers:produce_buyer/short_take, as the player, when the take removed fewer than the crate's count (#took of
    #n). Unreachable after the dry-run count gate, kept fail closed: the crate counts against the allowance and the
    taken share of the price, #price x #took / #n rounded down, is recorded as owed. Nothing is paid here."""
    S, m = doc["runtime"]["scores"], doc["messages"]
    T = S["temp"]
    return ["# Generated by tools/produce_buyer.py from data/produce_buyer.json: a short take (as the player)",
            "# the crate counts against the leg's allowance whatever happened: the cap fails closed",
            "scoreboard players add @s %s 1" % S["sold"],
            "# the taken share of the price is owed: #price x #took / #n",
            "scoreboard players operation #part %s = #price %s" % (T, T),
            "scoreboard players operation #part %s *= #took %s" % (T, T),
            "scoreboard players operation #part %s /= #n %s" % (T, T),
            "scoreboard players operation @s %s += #part %s" % (S["owed"], T),
            "tellraw @s %s" % text(m["take_failed"], "red"),
            "# an explicit return, so the caller's `return run function` stops the sale whatever the version does "
            "with a function that returns nothing",
            "return 1"]


def conversation(doc, site):
    """(conversation, quest) for one site's buyer, in data/dialogue.json's and data/quests.json's shape (the ferry's)."""
    qid = "produce_buyer_%s" % site["id"]
    responses, transitions = [], []
    for c in doc["crates"]:
        tid = "sell_%s" % c["id"]
        transitions.append({"id": tid, "conditions": [],
                            "effects": [{"kind": "function", "function": fn_id("sell/%s" % c["id"])}]})
        responses.append({"id": "r_%s" % c["id"], "text": c["option"],
                          "actions": [{"kind": "quest_transition", "transition": tid}, {"kind": "close_dialogue"}]})
    responses.append({"id": "r_leave", "text": doc["messages"]["leave"], "actions": [{"kind": "close_dialogue"}]})
    conv = {"id": "dlg_produce_buyer_%s" % site["id"], "quest_id": qid, "npc_id": "npc_produce_buyer_%s" % site["id"],
            "npc_name": site["name"], "scope": "player", "speakers": {"buyer": site["name"]},
            "cursor": {"progression_field": None, "initial_node": "menu"},
            "entry_rules": [{"priority": 10, "when": {"kind": "always"}, "node": "menu"}],
            "nodes": [{"id": "menu", "kind": "choice", "speaker": "buyer", "text": site["greeting"],
                       "responses": responses}]}
    return conv, {"id": qid, "progression_field_refs": [], "transitions": transitions, "rewards": []}


def build(doc):
    """{relative path in the pack: content (list of lines, or a JSON object)}."""
    import compile_dialogue as CD
    S = doc["runtime"]["scores"]
    files = {"pack.mcmeta": {"pack": {"pack_format": 48,
                                      "description": "Cobblers Produce Buyer (generated by tools/produce_buyer.py)"}},
             "data/minecraft/tags/function/load.json": {"values": [fn_id("load")]}}
    files[fn_path("load")] = ["# the Produce Buyer's scores: the sale's arithmetic, each player's cooldown, leg, crates "
                              "sold this leg and anything owed after a failed payment"] + \
        ["scoreboard objectives add %s dummy" % S[k] for k in ("temp", "cooldown", "leg", "sold", "owed")]
    files[fn_path("leg")] = leg_lines(doc)
    files[fn_path("pay")] = ["# CobbleDollars' own command, the macro tools/arena_runtime.py and tools/blackout_pack.py use",
                             "$cobbledollars give @s $(amount)"]
    files[fn_path("short_take")] = short_take_lines(doc)
    for c in doc["crates"]:
        files[fn_path("sell/%s" % c["id"])] = sell_lines(doc, c)
        if not c.get("tag") and len(c["items"]) > 1:
            files["data/%s/tags/item/%s/%s.json" % (NS, FOLDER, c["id"])] = {"values": list(c["items"])}
    for site in doc["sites"]:
        conv, quest = conversation(doc, site)
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
ANCHORS = ("apricorn_farm",)


def seat(site, plan_cache, g=None):
    """(x, y, z), the plan, and the anchor's other NPCs [(who, (x, y, z))] for one site, from its anchor's plan."""
    if site.get("anchor") not in ANCHORS:
        raise BuyerError("site %s: anchor %r is not one of %s" % (site.get("id"), site.get("anchor"), ANCHORS))
    import apricorn_farm as AF
    if "apricorn_farm" not in plan_cache:
        import ground as G
        doc = AF.load()
        plan_cache["apricorn_farm"] = AF.plan(doc, g or G.load())
    p, farmer, merchant = plan_cache["apricorn_farm"]
    lx, lz = site["at_local"]
    try:
        xyz = AF.spot(p, lx, lz, "the produce buyer %s" % site["id"])
    except AF.FarmError as e:
        raise BuyerError(str(e))
    return xyz, p, [("the farmer", farmer), ("the stall merchant", merchant)]


def npc_placements(doc=None, g=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for tools/reapply.py's "npc" action (R18PB). The position is the
    site's spot recomputed from its anchor's plan, so a moved farm moves the buyer with it (and check fails until
    expected_at is updated)."""
    doc = doc or load()
    cache = {}
    out = []
    for site in doc["sites"]:
        xyz, _p, _o = seat(site, cache, g)
        out.append(("dlg_produce_buyer_%s" % site["id"], tuple(xyz), "%s:npc_produce_buyer_%s" % (NS, site["id"]),
                    site["yaw"]))
    return out


def seat_problems(doc, g=None):
    out = []
    cache = {}
    paths = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    pts = [(x, z) for v in paths.values() for x, z in v]
    for site in doc["sites"]:
        w = "site %s" % site.get("id")
        try:
            xyz, p, others = seat(site, cache, g)
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
        if not (isinstance(site.get("yaw"), (int, float)) and -180 <= site["yaw"] <= 180):
            out.append("%s: yaw %r is not a Minecraft yaw" % (w, site.get("yaw")))
    return out


# ---------------------------------------------------------------------------------------------------------- checks
def static_problems(doc, planned_flags, bank_prices, sell_points):
    out = []
    rs = rows(doc)
    covered = []
    for lo, hi, price, crates in rs:
        if lo > hi or price < 0 or crates < 0:
            out.append("schedule row %d..%d: badges out of order or a negative price or crate count" % (lo, hi))
        covered += list(range(lo, hi + 1))
        if (price == 0) != (crates == 0):
            out.append("schedule row %d..%d: a zero price must have zero crates, and the other way round" % (lo, hi))
    if sorted(covered) != list(range(0, len(doc["badge_flags"]) + 1)):
        out.append("schedule: badges %s, not 0..%d once each" % (sorted(covered), len(doc["badge_flags"])))
    seq = [schedule_at(doc, b) for b in sorted(set(covered))]
    for (p0, _c0), (p1, _c1) in zip(seq, seq[1:]):
        if p1 > p0:
            out.append("schedule: the price rises (%d to %d): it may only fall with badges" % (p0, p1))
    if seq and seq[-1] != (0, 0):
        out.append("schedule: the last row pays %r; after the last badge the buyer pays nothing" % (seq[-1],))
    if campaign_total(doc) != doc["schedule"].get("campaign_cap"):
        out.append("schedule: price x crates sums to %d per player, campaign_cap says %r"
                   % (campaign_total(doc), doc["schedule"].get("campaign_cap")))
    for f in doc["badge_flags"]:
        if f not in planned_flags:
            out.append("badge flag %s is not a flag tools/progression_pack.py plans" % f)
    seen = set()
    for c in doc["crates"]:
        w = "crate %s" % c.get("id")
        if not ID.fullmatch(c.get("id") or "") or c["id"] in seen:
            out.append("%s: id not [a-z0-9_] or listed twice" % w)
        seen.add(c.get("id"))
        if not (isinstance(c.get("count"), int) and 0 < c["count"] <= 64 * 36):
            out.append("%s: count %r is not a positive whole number an inventory can hold" % (w, c.get("count")))
        if not c.get("items") or not all(ITEM.fullmatch(i) for i in c["items"]):
            out.append("%s: items must be ns:path ids" % w)
        if c.get("tag") and not (c["tag"].startswith("#") and ITEM.fullmatch(c["tag"][1:])):
            out.append("%s: tag %r is not #ns:path" % (w, c["tag"]))
        if c.get("tag") and not c.get("tag_verified"):
            out.append("%s: a jar tag with no tag_verified source" % w)
        for k in ("label", "option"):
            if not c.get(k):
                out.append("%s: no %s" % (w, k))
        top = max((price for _lo, _hi, price, _c in rs), default=0)
        unit = top / c["count"] if c.get("count") else 0
        for i in c.get("items") or []:
            if i in bank_prices:
                out.append("%s: the bank still buys %s at $%d: data/bank.json afk_rule moved farm goods here"
                           % (w, i, bank_prices[i]))
        for where, i, u in sell_points:
            if i in set(c.get("items") or []) and u <= unit:
                out.append("%s: %s sells %s at $%g each, at or under the crate's top $%g a unit: buying a crate to "
                           "sell it pays" % (w, where, i, u, unit))
    for k in ("leave", "closed", "spent", "short", "short_after", "paid", "take_failed", "pay_failed"):
        if not doc["messages"].get(k):
            out.append("messages.%s is missing" % k)
    sids = [s.get("id") for s in doc["sites"]]
    if not sids or len(set(sids)) != len(sids) or not all(ID.fullmatch(s or "") for s in sids):
        out.append("sites: none, a repeated id or an id not [a-z0-9_]")
    return out


def output_problems(doc, files):
    """Every sale counts, then takes, then pays once and verifies; nothing charges; every function within limits."""
    import function_limits
    out = []
    store = doc["runtime"]["storage"]
    pay_call = "function %s with storage %s pay" % (fn_id("pay"), store)
    for c in doc["crates"]:
        rel = fn_path("sell/%s" % c["id"])
        body = files.get(rel)
        if not body:
            out.append("crate %s: no sell function" % c["id"])
            continue
        cmds = [ln for ln in body if not ln.startswith("#")]
        item = predicate(c)
        idx = lambda pred: next((i for i, ln in enumerate(cmds) if pred(ln)), None)   # noqa: E731
        count = idx(lambda ln: ln.endswith("run clear @s %s 0" % item))
        take = idx(lambda ln: ln.endswith("run clear @s %s %d" % (item, c["count"])))
        took_ok = idx(lambda ln: ln.startswith("execute unless score #took") and "matches %d run return" % c["count"] in ln)
        pay = idx(lambda ln: ln == pay_call)
        after = idx(lambda ln: "#after" in ln and "cobbledollars query" in ln)
        verify = idx(lambda ln: ln.startswith("execute unless score #after") and "run return" in ln)
        sold = idx(lambda ln: ln.startswith("scoreboard players add @s %s 1" % doc["runtime"]["scores"]["sold"]))
        order = [count, take, took_ok, sold, pay, after, verify]
        if None in order or order != sorted(order):
            out.append("crate %s: the sale is not count < take < take-check < count-sold < pay < re-read < verify "
                       "(%s)" % (c["id"], order))
        # fail closed: after the take, nothing returns before the crate is counted against the allowance, and the
        # short-take return runs the function that counts it and records the owed share
        if None not in (take, sold):
            early = [ln for ln in cmds[take + 1:sold] if "return" in ln]
            if early != [cmds[took_ok]] or not cmds[took_ok].endswith("run return run function %s" % fn_id("short_take")):
                out.append("crate %s: a return between the take and the count other than the short-take function: "
                           "the cap could fail open (%s)" % (c["id"], early))
        if sum(1 for ln in cmds if ln == pay_call) != 1:
            out.append("crate %s: pays %d times" % (c["id"], sum(1 for ln in cmds if ln == pay_call)))
        if any("cobbledollars remove" in ln or "cobbledollars give" in ln for ln in cmds):
            out.append("crate %s: a CobbleDollars change outside the pay macro" % c["id"])
    st = [ln for ln in (files.get(fn_path("short_take")) or []) if not ln.startswith("#")]
    sold_obj, owed_obj = doc["runtime"]["scores"]["sold"], doc["runtime"]["scores"]["owed"]
    if not st or st[0] != "scoreboard players add @s %s 1" % sold_obj \
            or not any(ln.startswith("scoreboard players operation @s %s += " % owed_obj) for ln in st) \
            or any("cobbledollars" in ln for ln in st) \
            or [ln for ln in st if "return" in ln] != ["return 1"] or st[-1] != "return 1":
        out.append("short_take: must first count the crate (%s), record the owed share (%s), move no money and end "
                   "with `return 1` (its only return)" % (sold_obj, owed_obj))
    pay = files.get(fn_path("pay")) or []
    if [ln for ln in pay if not ln.startswith("#")] != ["$cobbledollars give @s $(amount)"]:
        out.append("the pay function is not exactly the proven macro `$cobbledollars give @s $(amount)`")
    for rel, body in sorted(files.items()):
        if rel.endswith(".mcfunction") and any("cobbledollars remove" in ln for ln in body):
            out.append("%s charges: the buyer never takes money" % rel)
        if rel.endswith(".mcfunction"):
            refused = function_limits.check_lines(body, rel)
            if refused:
                out.append("%s: %s" % (rel, refused))
    for site in doc["sites"]:
        if "data/%s/dialogues/dlg_produce_buyer_%s.json" % (NS, site["id"]) not in files:
            out.append("site %s: no compiled dialogue" % site["id"])
    return out


def check(doc=None, source_root=None, server_dir=None):
    import bank
    import ground as G
    import progression_pack as PP
    doc = doc or load()
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    planned = {f["id"] for f in PP.plan(prog, placements=placements)["flags"]}
    bdoc = bank.load()
    pts, skipped = bank.sell_points(server_dir)
    out = static_problems(doc, planned, bank.prices(bdoc), pts)
    if out:
        return out, skipped
    out += output_problems(doc, build(doc))
    out += seat_problems(doc, G.load(source_root))
    return out, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(DEFAULT_OUT))
    c = sub.add_parser("check")
    c.add_argument("--source-root")
    c.add_argument("--server-dir", help="an OFFLINE snapshot: also read the traders' template shops (tools/bank.py)")
    a = ap.parse_args(argv)
    doc = load()
    if a.cmd == "build":
        files = build(doc)
        write(files, a.out)
        print("wrote %s (%d files, %d crate kinds, %d site(s))" % (a.out, len(files), len(doc["crates"]),
                                                                 len(doc["sites"])))
        return 0
    out, skipped = check(doc, a.source_root, a.server_dir)
    for p in out:
        print("PROBLEM " + p)
    for s in skipped:
        print("NOT CHECKED " + s)
    print("produce_buyer: %d problems; %d crate kinds, %d site(s), campaign cap $%d per player%s"
          % (len(out), len(doc["crates"]), len(doc["sites"]), campaign_total(doc),
             "" if not skipped else " (partial: %d source(s) not read)" % len(skipped)))
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
