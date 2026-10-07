#!/usr/bin/env python
"""Town traders as data: the manifest (data/traders.json), its re-application function, and presence checks.

A trader is an entity, and a re-export regenerates every region and entity file from the WorldPainter project,
so a trader summoned in game is gone after the next export. The manifest is the source, like the Habitat Blocks
(tools/habitat_blocks.py): this tool writes the function that puts every trader back, and checks that each one
stands exactly once. Nothing is summoned by hand.

  function   python tools/traders.py function [--server-dir <server>] [--out build/datapacks/cobblers_vendors]
             then: /reload and /function cobblers:towns/vendors_<settlement>, and wait 8 seconds for it to finish
  verify     python tools/traders.py verify --rcon <server dir>     a running server, under the coordination lock
             python tools/traders.py verify --world <stopped world>  an offline snapshot or disposable copy

Each trader is summoned from the entity in its shopkeeper template: the trade list, name and look come from the
installed pack, and only the fields the engine owns are dropped. The function runs in three ticks' worth of steps,
each spaced by what was measured on the disposable world on 2026-09-21:

  vendors_<town>        force-load the plaza, then wait 40 ticks.
  vendors_<town>_place  summon every trader with a "new" tag.
  vendors_<town>_done   100 ticks later: where a new trader stands, kill every older one with its tag and any
                        untagged copy of it on its spot, drop the "new" tag, release the plaza.

Why the waits, measured with an old trader saved in an unloaded chunk and a new one summoned N ticks after
`forceload add`: at 1 and 2 ticks the chunk accepts a summon but its saved entities are not loaded yet, so a kill by
tag finds nothing and the old trader survives beside the new (old 1, new 1); at 20 and 100 ticks the kill finds it
(old 0, new 1). The first version killed at 2 ticks, and every run stacked another trader on each spot. Deduplicating
100 ticks after the summon, and only where the new one exists, makes a re-run converge on one trader per spot even if
loading is slower, and leaves the old trader standing if a summon ever fails.

Counting has the same trap: an entity in a chunk that is not force-loaded or near a player is invisible to @e even
while its chunk is still unloading, so a count taken after the plaza is released reads 0 with every trader in place.
That reading is what looked like "the function summons nothing". verify --rcon force-loads the plaza and waits for
the count to settle before it believes it.

Ownership: generated output under build/ (gitignored). Who stands where is authored in data/traders.json.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import nbt  # noqa: E402

MANIFEST = ROOT / "data" / "traders.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_vendors"
STATUSES = ("planned", "placed", "verified")
PLACED = ("placed", "verified")
TAG_ALL = "cobblers_vendor"
TAG_NEW = "cobblers_vendor_new"
LOAD_WAIT = 40      # ticks from forceload to summon: saved entities load within 20 (measured), doubled
DEDUPE_WAIT = 100   # ticks from summon to the de-duplication and release
SPOT_RADIUS = 3     # a trader wanders a little; further than this from its spot is not standing there
PLAZA_MARGIN = 48    # force-loaded round the plaza, so strays that walked off are found too
STOCKS = ("regional", "withdrawn", "mart", "stones")
# The Exchange (docs/mechanics/STONE_ECONOMY.md section 8): a clerk whose shop is authored here, not filtered from its
# template, selling the ten evolution stones at one price and buying nothing. The offer's shape, {Item:{count,id},
# Price:"<n>"} with the price as a string, is the shape the shopkeeper templates themselves carry
# (bca:stores/store_workers/shopkeeper_ds_general in COBBLEVERSE-DP-v31.zip, read 2026-09-28); that a shop authored
# from scratch sells in game is proof P-7, not run.
STONE_ITEM = re.compile(r"cobblemon:[a-z]+_stone")
YAW = {"south": 0.0, "west": 90.0, "north": 180.0, "east": -90.0}


# The ground rule (tools/ground_rule.py): the functions here that read a world, each only to check, never to
# decide a position: `verify` counts traders in a stopped world; placement never reads one.
WORLD_READS = {'main', 'world_counts', 'world_problems'}


def tag_of(tid):
    return "%s_%s" % (TAG_ALL, tid)


def find_template(server_dir, template_id):
    """The raw nbt of a template the server can place, from a mod jar or a datapack."""
    ns, rel = template_id.split(":", 1)
    names = ("data/%s/structure/%s.nbt" % (ns, rel), "data/%s/structures/%s.nbt" % (ns, rel))
    sources = sorted(glob.glob(os.path.join(server_dir, "mods", "*.jar"))) + \
        sorted(glob.glob(os.path.join(server_dir, "datapacks", "*.zip")))
    for path in sources:
        try:
            z = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError):  # not a readable jar
            continue
        for name in names:
            if name in z.namelist():
                return z.read(name)
    raise SystemExit("template not found in the installed packs: %s" % template_id)


def to_snbt(value):
    """NBT value -> the SNBT a command takes."""
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int):
        return to_snbt(value[1])
    if isinstance(value, dict):
        return "{%s}" % ",".join('%s:%s' % (k, to_snbt(v)) for k, v in value.items())
    if isinstance(value, list):
        return "[%s]" % ",".join(to_snbt(v) for v in value)
    if isinstance(value, bool):
        return "1b" if value else "0b"
    if isinstance(value, float):
        return "%sf" % value
    if isinstance(value, int):
        return str(value)
    # SNBT has no unicode escape, and json.dumps writes one for any non-ASCII character: a
    # trader whose shop category is spelled with an accent stopped the whole function loading.
    text = str(value).replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"')
    return '"%s"' % text


# Keep what the trader is, drop what the engine owns. A copied UUID collides with the entity already in the
# world on a re-run, Pos and Motion fight the summon's own coordinates, and the brain and attribute block only
# lengthen the command.
ENGINE_OWNED = ("UUID", "Pos", "Motion", "Rotation", "Brain", "attributes", "Attributes", "HurtByTimestamp",
                "HurtTime", "DeathTime", "FallDistance", "FallFlying", "PortalCooldown", "OnGround", "Air",
                "AbsorptionAmount", "fabric:attachments", "cardinal_components", "Bukkit.updateLevel",
                "WorldUUIDLeast", "WorldUUIDMost", "Tags")


MERCHANT = "cobbledollars:cobble_merchant"


def summon_line(kind, x, y, z, data):
    """The summon command for a trader standing on block (x, y, z): centred on the block, feet at y. Shared with
    tools/markets.py, whose stall merchants are authored rather than read from a template."""
    return "summon %s %d.5 %d %d.5 %s" % (kind, x, y, z, to_snbt(data))


def entity_of(server_dir, template_id):
    """(entity id, nbt dict without engine-owned fields) of the trader in a shopkeeper template."""
    _, root = nbt.loads(find_template(server_dir, template_id))
    entities = root.get("entities") or []
    if not entities:
        raise SystemExit("%s holds no entity to summon" % template_id)
    data = dict(entities[0].get("nbt") or {})
    kind = data.pop("id", "minecraft:villager")
    kind = kind[1] if isinstance(kind, tuple) else kind
    for k in ENGINE_OWNED:
        data.pop(k, None)
    return str(kind), data


def _v(x):
    return x[1] if isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], int) else x


def mart_items(policy):
    return set(((policy or {}).get("mart") or {}).get("items") or [])


def mart_tier_items(policy, tier=0):
    """The Mart's tier lines a clerk at `tier` adds to the basics: every stock_policy.mart.tiers entry whose badges
    are <= tier (the owner's play-test note 9, 2026-10-05: scale the Mart with the gyms)."""
    out = set()
    for t in ((policy or {}).get("mart") or {}).get("tiers") or []:
        if isinstance(t, dict) and isinstance(t.get("badges"), int) and t["badges"] <= int(tier or 0):
            out.update(t.get("items") or [])
    return out


def mart_tiers(doc, towns_doc):
    """{trader id: tier} for every Mart clerk, by stock_policy.mart.tier_rule: the badges a critical-path player
    holds arriving at its town (critical towns: max(0, order - 1)); an off-path clerk takes the tier of the critical
    town whose centre is nearest the clerk's own position (straight line). A record's own mart_tier overrides, and must say why. The merchant
    screen cannot gate per player (data/markets.json decision counters_are_merchants), so the tier is the town's."""
    towns = {t.get("id"): t for t in (towns_doc or {}).get("towns") or [] if isinstance(t, dict)}
    crit = {}
    for tid, t in towns.items():
        if t.get("critical_path") and isinstance(t.get("order"), int):
            crit[tid] = max(0, t["order"] - 1)
    out = {}
    for r in (doc or {}).get("traders") or []:
        if not isinstance(r, dict) or r.get("stock") != "mart":
            continue
        if isinstance(r.get("mart_tier"), int) and not isinstance(r.get("mart_tier"), bool):
            out[r["id"]] = r["mart_tier"]
            continue
        sid = r.get("settlement")
        if sid in crit:
            out[r["id"]] = crit[sid]
            continue
        # where the clerk itself stands, not the town's recorded centre: data/towns.json still puts Pacifidlog at its
        # pre-move site (7210, 6960), 2 km from the deck the clerk stands on (REVIEW 58)
        here = r.get("position") if isinstance(r.get("position"), dict) else (towns.get(sid) or {}).get("centre")
        if not here or not crit:
            out[r["id"]] = 0                              # unknown position: the basics only, never more
            continue
        near = min(crit, key=lambda c: ((towns[c]["centre"]["x"] - here["x"]) ** 2
                                        + (towns[c]["centre"]["z"] - here["z"]) ** 2, c))
        out[r["id"]] = crit[near]
    return out


def load_towns():
    return json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))


def load_cumulative_income():
    """{badges: cumulative income} from data/markets.json income_basis.cumulative_by_badge (RELAYED model B): the
    money a player has earned by the time they hold that many badges, before any spending."""
    doc = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
    cum = ((doc.get("income_basis") or {}).get("cumulative_by_badge")) or {}
    return {int(k): int(v) for k, v in cum.items()}


def early_reach_policy(policy):
    return (((policy or {}).get("mart") or {}).get("early_reach_pricing")) or {}


def _tier_item_ids(t):
    """The item ids of one tier entry: a Mart tier lists ids, a training tier lists {item, price} offers."""
    return [i["item"] if isinstance(i, dict) else i for i in t.get("items") or []]


def priced_tiers(policy):
    """Every tier entry the early-reach rule prices: stock_policy.mart.tiers, then mart.training.tiers."""
    mart = (policy or {}).get("mart") or {}
    return list(mart.get("tiers") or []) + list((mart.get("training") or {}).get("tiers") or [])


def early_reach_prices(policy, rid, income=None):
    """{item id: (band, value)} for the tier lines a Mart clerk listed in stock_policy.mart.early_reach_pricing sells
    above the badges R its town is reachable with. By the distance d = T - R of a line of tier T:
      1 <= d <= convenience_within  ("markup", factor): the normal price times convenience_markup (the owner,
                                    2026-10-08: a low tier is a convenience, not a gate);
      d > convenience_within        ("floor", price): more than cumulative_by_badge[T], the most a player with T-1
                                    badges has earned (they earn leg T while holding T-1), rounded UP to round_to (the
                                    owner, 2026-10-07: late stock out of reach early).
    apply_price() turns a band into a price and never goes below the normal one. A clerk not listed, and lines with
    T <= R: absent (the normal price)."""
    erp = early_reach_policy(policy)
    rec = (erp.get("traders") or {}).get(rid)
    if not rec:
        return {}
    reach = rec["reachable_from_badges"]
    step = int(erp.get("round_to") or 1)
    within = int(erp.get("convenience_within") or 0)
    markup = erp.get("convenience_markup") or 1
    income = load_cumulative_income() if income is None else income
    out = {}
    for t in priced_tiers(policy):
        tier = t["badges"]
        if tier <= reach:
            continue
        if tier - reach <= within:
            band = ("markup", markup)
        else:
            if tier not in income:
                raise SystemExit("early_reach_pricing: %s sells a tier-%d line, but data/markets.json income_basis "
                                 "has no cumulative_by_badge[%d]" % (rid, tier, tier))
            band = ("floor", (income[tier] // step + 1) * step)      # strictly above the income, on the step
        for iid in _tier_item_ids(t):
            out[iid] = band
    return out


def apply_price(normal, band, step=1):
    """The price of a line with normal price `normal` under an early-reach band (early_reach_prices), never lower
    than normal: a floor raises it to the floor; a markup multiplies it, rounded UP to step."""
    if band is None:
        return normal
    kind, value = band
    if kind == "floor":
        return max(normal, int(value))
    if kind == "markup":
        raw = normal * value
        return max(normal, int(-(-raw // step) * step))
    raise ValueError("unknown early-reach band %r" % (kind,))


def _price_offer(off, band, step=1):
    """The offer with its Price set by the early-reach band, in the template's own value shape."""
    orig, off = off, _v(off)
    raw = off.get("Price")
    was = int(str(_v(raw)))
    price = apply_price(was, band, step)
    if price == was:
        return orig
    new = dict(off)
    new["Price"] = (raw[0], str(price)) if isinstance(raw, tuple) else str(price)
    return new


def stone_items(policy):
    return list(((policy or {}).get("stones") or {}).get("items") or [])


def card_policy(policy):
    return ((policy or {}).get("trainer_card") or {})


def card_shop(policy):
    """The trainer card's own category, appended to the one Mart clerk that stocks it (nothing else is added)."""
    c = card_policy(policy)
    return [{"Category": c["category"],
             "Offers": [{"Item": {"count": 1, "id": c["item"]}, "Price": str(int(c["price"]))}]}]


def mart_shop_items(policy, rid=None, tier=0):
    """Every item id a Mart clerk's shop should offer: the basic items and its tier's lines (mart_tier_items), plus
    the trainer card at the one clerk the policy names. Used by the shop filter and by the in-game verify, so the two
    cannot disagree."""
    items = set(mart_items(policy)) | mart_tier_items(policy, tier)
    if rid is not None and card_policy(policy) and rid == card_policy(policy).get("trader"):
        items.add(card_policy(policy)["item"])
    return items


def stone_shop(policy):
    """The Exchange's CobbleMerchantShop: one category, every stone once at the policy's price, unlimited."""
    st = policy["stones"]
    return [{"Category": st["category"],
             "Offers": [{"Item": {"count": 1, "id": iid}, "Price": str(int(st["price"]))} for iid in st["items"]]}]


def apply_stock_policy(data, policy, stock=None, rid=None, tier=0):
    """(data with the shop filtered, kept item ids, withheld item ids).

    The shopkeeper templates sell whatever BCA stocked: ultra balls, max revives, X items next to the fish and
    bread. Until the badge-gated stock is designed, a trader sells only what the policy in data/traders.json
    leaves: whole categories and single items are withheld, and a category left empty is dropped. A Mart clerk
    (stock "mart") is the other way round: it sells only the policy's basic Mart items, whatever else the
    template carries, widened by its `tier` (mart_tier_items: the template's own offers for the lines up to that
    many badges, at the template's prices) -- plus, at the single clerk stock_policy.trainer_card names, one authored
    offer for rctmod:trainer_card, which no shopkeeper template carries and which nothing else in the region sells."""
    shop = data.get("CobbleMerchantShop")
    if stock == "stones":
        # the Exchange: the template's whole shop is replaced by the authored one (nothing of it is kept)
        if not stone_items(policy):
            return data, [], []
        held = [_v(_v(_v(off).get("Item")).get("id")) for cat in _v(shop or []) for off in _v(_v(cat).get("Offers")) or []]
        out = dict(data)
        out["CobbleMerchantShop"] = stone_shop(policy)
        return out, stone_items(policy), held
    if shop is None or not policy:
        return data, None, []                      # nothing to filter: not "nothing left"
    cats_out, kept, held = [], [], []
    no_cat = set(policy.get("withhold_categories") or [])
    no_item = set(policy.get("withhold_items") or [])
    only = (mart_items(policy) | mart_tier_items(policy, tier)) if stock == "mart" else None
    # the early-reach price gate (stock_policy.mart.early_reach_pricing, 2026-10-07): only a listed Mart clerk
    floors = early_reach_prices(policy, rid) if stock == "mart" and rid is not None else {}
    step = int(early_reach_policy(policy).get("round_to") or 1)
    for cat in _v(shop):
        cat = _v(cat)
        name = _v(cat.get("Category"))
        offers = []
        for off in _v(cat.get("Offers")) or []:
            iid = _v(_v(_v(off).get("Item")).get("id"))
            if (iid not in only) if only is not None else (name in no_cat or iid in no_item):
                held.append(iid)
            else:
                kept.append(iid)
                offers.append(_price_offer(off, floors[iid], step) if iid in floors else off)
        if offers:
            c = dict(cat)
            c["Offers"] = offers
            cats_out.append(c)
    if stock == "mart" and card_policy(policy) and rid is not None and rid == card_policy(policy).get("trader"):
        # rctmod:trainer_card is in no shopkeeper template and in no shop of ours: without the card
        # `spawningRequiresTrainerCard = true` (modpack/config/rctmod-server.toml:87) means no RCT trainer ever
        # spawns naturally for that player. Authored, like the Exchange's stones, in the offer shape the
        # templates themselves carry. Appended after the filter, so the filter still governs the basics.
        card = card_policy(policy)
        cats_out = cats_out + card_shop(policy)
        kept = kept + [card["item"]]
        held = [i for i in held if i != card["item"]]
    out = dict(data)
    out["CobbleMerchantShop"] = cats_out
    return out, kept, held


def display_name(data):
    """The plain name a template gives its trader, or None. CustomName is a JSON text component."""
    raw = data.get("CustomName")
    raw = raw[1] if isinstance(raw, tuple) else raw
    if not isinstance(raw, str):
        return None
    try:
        v = json.loads(raw)
    except ValueError:
        return None
    if isinstance(v, dict):
        v = v.get("text")
    return v if isinstance(v, str) and v and '"' not in v else None


def stray_selector(kind, name, x, y, z):
    """Untagged entities that are copies of this trader: same type and name within the plaza margin, or, for a
    trader without a name, same type on its spot."""
    if name:
        return 'type=%s,name="%s",tag=!%s,x=%d.5,y=%d,z=%d.5,distance=..%d' % (kind, name, TAG_ALL, x, y, z, PLAZA_MARGIN)
    return "type=%s,tag=!%s,x=%d.5,y=%d,z=%d.5,distance=..%d" % (kind, TAG_ALL, x, y, z, SPOT_RADIUS)


def plaza_box(recs):
    xs = [r["position"]["x"] for r in recs]
    zs = [r["position"]["z"] for r in recs]
    return min(xs) - PLAZA_MARGIN, min(zs) - PLAZA_MARGIN, max(xs) + PLAZA_MARGIN, max(zs) + PLAZA_MARGIN


def town_functions(town, recs, entity, policy=None, tiers=None):
    """{function name: lines} for one settlement. entity(template id) -> (kind, nbt dict). A trader the stock
    policy leaves with nothing to sell is withdrawn: no summon, and any copy already standing is removed. `tiers`
    is mart_tiers()'s {id: tier}; a Mart clerk missing from it sells the basics only."""
    tiers = tiers or {}
    box = "%d %d %d %d" % plaza_box(recs)
    loader = ["# Generated by tools/traders.py from data/traders.json: the traders of %s" % town,
              "# force-load the plaza and give its saved traders time to load before anything is summoned",
              "forceload add %s" % box,
              "schedule function cobblers:towns/vendors_%s_place %dt replace" % (town, LOAD_WAIT)]
    place = ["# Generated by tools/traders.py; called by cobblers:towns/vendors_%s" % town,
             # the loader force-loads the plaza and the _done step releases it, after the summons are saved
             "# chunks-loaded-by: cobblers:towns/vendors_%s" % town]
    done = ["# Generated by tools/traders.py; %d ticks after the summons: one trader per spot, then release" % DEDUPE_WAIT]
    for rec in sorted(recs, key=lambda q: q["id"]):
        kind, data = entity(rec["template"])
        template_name = display_name(data)
        data, kept, _held = apply_stock_policy(dict(data), policy, rec.get("stock"), rec["id"], tiers.get(rec["id"], 0))
        x, y, z = (rec["position"][k] for k in "xyz")
        tag = tag_of(rec["id"])
        if kept == [] or rec.get("stock") == "withdrawn":
            name = display_name(data)
            done += ["# %s: withdrawn, nothing left to sell under the stock policy" % rec["id"],
                     "kill @e[tag=%s]" % tag, "kill @e[%s]" % stray_selector(kind, name, x, y, z)]
            continue
        data["Tags"] = [TAG_ALL, tag, TAG_NEW]
        data["PersistenceRequired"] = True
        # The template's merchant keeps its AI and walks: copies summoned with it were found 2 to 40 blocks off
        # their stalls. A stall trader stands still.
        data["NoAI"] = True
        if rec.get("stock") == "mart":
            # the clerk is named for the shop, not for the template it was read from
            data["CustomName"] = json.dumps({"text": policy["mart"]["name"]}, ensure_ascii=False)
        if rec.get("stock") == "stones":
            data["CustomName"] = json.dumps({"text": policy["stones"]["name"]}, ensure_ascii=False)
        if rec.get("facing"):
            # NoAI never turns its head: a clerk summoned without a rotation stares at the wall behind the counter
            data["Rotation"] = [YAW[rec["facing"]], 0.0]
        name = display_name(data)
        if name != template_name:
            # a copy under the template's own name, left by structure placement or an earlier run, is still a copy
            done.append("kill @e[%s]" % stray_selector(kind, template_name, x, y, z))
        place += ["# %s: %s" % (rec["id"], rec["template"]),
                  # a jigsaw left by the earlier attempt that placed traders as structures
                  "execute if block %d %d %d minecraft:jigsaw run setblock %d %d %d minecraft:air" % (x, y, z, x, y, z),
                  "execute if block %d %d %d minecraft:jigsaw run setblock %d %d %d minecraft:air" % (x, y + 1, z, x, y + 1, z),
                  summon_line(kind, x, y, z, data)]
        done += ["# %s" % rec["id"],
                 "execute if entity @e[tag=%s,tag=%s] run kill @e[tag=%s,tag=!%s]" % (tag, TAG_NEW, tag, TAG_NEW),
                 # untagged copies of this trader, left by structure placement or by hand: same type and name,
                 # anywhere round the plaza, since the earlier copies could walk
                 "execute if entity @e[tag=%s,tag=%s] run kill @e[%s]" % (tag, TAG_NEW, stray_selector(kind, name, x, y, z)),
                 # this trader's own "new" tag only: stripping it from every entity let the first town's pass
                 # clear the second town's before that town de-duplicated, and the second town kept stacking
                 "tag @e[tag=%s,tag=%s] remove %s" % (tag, TAG_NEW, TAG_NEW)]
    place.append("schedule function cobblers:towns/vendors_%s_done %dt replace" % (town, DEDUPE_WAIT))
    done += ["forceload remove %s" % box]
    return {"vendors_%s" % town: loader, "vendors_%s_place" % town: place, "vendors_%s_done" % town: done}


def static_problems(doc, placements_doc=None, plans_dir=None):
    """[(record id or None, message)] for rules that need no world."""
    out = []
    recs = doc.get("traders") if isinstance(doc, dict) else None
    if not isinstance(recs, list):
        return [(None, '"traders" must be a list')]
    towns = {s.get("id") for s in (placements_doc or {}).get("settlements") or [] if isinstance(s, dict)}
    seen, spots = set(), {}
    for r in recs:
        rid = r.get("id") if isinstance(r, dict) else None
        if not rid:
            out.append((None, "every trader needs an id"))
            continue
        if not re.fullmatch(r"[a-z0-9_]+", rid):
            out.append((rid, "id must be lower-case letters, digits and underscores (it becomes an entity tag)"))
        if rid in seen:
            out.append((rid, "duplicate id"))
        seen.add(rid)
        pos = r.get("position")
        if not (isinstance(pos, dict) and all(isinstance(pos.get(k), int) and not isinstance(pos.get(k), bool) for k in "xyz")):
            out.append((rid, "position must be {x, y, z} integers"))
            continue
        key = (pos["x"], pos["y"], pos["z"])
        if key in spots:
            out.append((rid, "stands on the same block as %s" % spots[key]))
        spots[key] = rid
        if not (isinstance(r.get("template"), str) and ":" in r["template"]):
            out.append((rid, "template must be a namespaced template id"))
        if r.get("stock") not in STOCKS:
            out.append((rid, "stock must be one of %s" % ", ".join(STOCKS)))
        if r.get("facing") is not None and r["facing"] not in YAW:
            out.append((rid, "facing must be one of %s" % ", ".join(YAW)))
        if r.get("stock") == "mart" and not mart_items(doc.get("stock_policy")):
            out.append((rid, "a Mart clerk, but stock_policy.mart lists no items"))
        if "mart_tier" in r:
            mt = r.get("mart_tier")
            if r.get("stock") != "mart":
                out.append((rid, "mart_tier on a trader whose stock is %r, not \"mart\"" % r.get("stock")))
            if not (isinstance(mt, int) and not isinstance(mt, bool) and 0 <= mt <= 8):
                out.append((rid, "mart_tier must be a whole number of badges, 0-8"))
            if not r.get("mart_tier_why"):
                out.append((rid, "mart_tier overrides the town-position rule, so it needs mart_tier_why"))
        if r.get("stock") == "stones":
            st = (doc.get("stock_policy") or {}).get("stones") or {}
            items = st.get("items") or []
            if not items:
                out.append((rid, "the Exchange, but stock_policy.stones lists no items"))
            bad = [i for i in items if not (isinstance(i, str) and STONE_ITEM.fullmatch(i))]
            if bad:
                out.append((rid, "stock_policy.stones sells %s, which is not an evolution stone id" % ", ".join(map(str, bad))))
            if len(set(items)) != len(items):
                out.append((rid, "stock_policy.stones lists an item twice"))
            if st.get("buys") is not False:
                out.append((rid, "stock_policy.stones must say buys: false: a face is an unlimited supply, so a stone "
                                 "with a sell price makes it a money printer (STONE_ECONOMY.md section 8)"))
            if not (isinstance(st.get("price"), int) and not isinstance(st.get("price"), bool) and st["price"] > 0):
                out.append((rid, "stock_policy.stones.price must be a positive integer"))
            if not (isinstance(st.get("name"), str) and st["name"] and isinstance(st.get("category"), str) and st["category"]):
                out.append((rid, "stock_policy.stones needs a name and a category"))
        if r.get("status") not in STATUSES:
            out.append((rid, "status must be one of %s" % ", ".join(STATUSES)))
        if towns and r.get("settlement") not in towns:
            out.append((rid, "settlement %r is not a settlement in data/placements.json" % r.get("settlement")))
        if plans_dir is not None and not r.get("building"):
            # a trader inside a building (a Mart clerk behind its counter) stands on that building's floor, not
            # on the plaza
            plan = Path(plans_dir) / ("%s_plan.json" % r.get("settlement"))
            if plan.is_file():
                p = json.loads(plan.read_text(encoding="utf-8"))
                py = (p.get("plaza") or {}).get("y")
                if isinstance(py, int) and pos["y"] != py + 1:
                    out.append((rid, "stands at y%d, but the town plan paves the plaza at y%d, so it should be y%d"
                                % (pos["y"], py, py + 1)))
    card = card_policy(doc.get("stock_policy"))
    if card:
        # The card is a prerequisite rather than stock: one clerk sells it, and it is the only thing in the region
        # that lets an RCT trainer spawn at all. A policy block naming a clerk that is not a Mart, or no clerk, is
        # a dead config of exactly the kind this block exists to fix.
        # NOT CHECKED HERE: that the named clerk exists at all. A manifest passed to this function can legitimately
        # be a subset of one trader (tests/test_mart_clerks.py's function-mode fixtures), so absence cannot be a
        # fault of every manifest -- but in data/traders.json it is, and a typo there emits no card and says nothing.
        # That check needs the canonical manifest and belongs in a test (test-author owns it).
        by_id = {r.get("id"): r for r in recs if isinstance(r, dict)}
        who = card.get("trader")
        if who in by_id and by_id[who].get("stock") != "mart":
            out.append((who, "stock_policy.trainer_card names it, but its stock is %r, not \"mart\": the card is "
                             "appended to a Mart clerk's shop" % by_id[who].get("stock")))
        if not (isinstance(card.get("item"), str) and ":" in card["item"]):
            out.append((None, "stock_policy.trainer_card.item must be a namespaced item id"))
        if not (isinstance(card.get("price"), int) and not isinstance(card.get("price"), bool) and card["price"] > 0):
            out.append((None, "stock_policy.trainer_card.price must be a positive integer"))
        if not (isinstance(card.get("category"), str) and card["category"]):
            out.append((None, "stock_policy.trainer_card needs a category"))
        if card.get("buys") is not False:
            out.append((None, "stock_policy.trainer_card must say buys: false: nothing in CobbleDollars' bank.json "
                              "buys the card back, and a licence with a sell price is sold twice"))
        if len([r for r in recs if isinstance(r, dict) and r.get("id") == who]) > 1:
            out.append((who, "two traders carry the id the trainer card is attached to"))
    erp = early_reach_policy(doc.get("stock_policy"))
    if erp:
        by_id = {r.get("id"): r for r in recs if isinstance(r, dict)}
        rt = erp.get("round_to")
        if not (isinstance(rt, int) and not isinstance(rt, bool) and rt > 0):
            out.append((None, "stock_policy.mart.early_reach_pricing.round_to must be a positive integer"))
        cw, cm = erp.get("convenience_within", 0), erp.get("convenience_markup", 1)
        if not (isinstance(cw, int) and not isinstance(cw, bool) and 0 <= cw <= 8):
            out.append((None, "stock_policy.mart.early_reach_pricing.convenience_within must be a whole number of "
                              "badges, 0-8"))
        if not (isinstance(cm, (int, float)) and not isinstance(cm, bool) and cm >= 1):
            out.append((None, "stock_policy.mart.early_reach_pricing.convenience_markup must be a number >= 1: a "
                              "convenience is never cheaper than the normal price"))
        for k in ("convenience_within", "convenience_markup"):
            if k in erp and not erp.get(k + "_why"):
                out.append((None, "stock_policy.mart.early_reach_pricing.%s needs a %s_why" % (k, k)))
        if erp.get("income_source") != "data/markets.json income_basis.cumulative_by_badge":
            out.append((None, "stock_policy.mart.early_reach_pricing.income_source must name the income it is "
                              "computed from: data/markets.json income_basis.cumulative_by_badge"))
        for who, e in sorted((erp.get("traders") or {}).items()):
            rb = (e or {}).get("reachable_from_badges")
            if who in by_id and by_id[who].get("stock") != "mart":
                out.append((who, "early_reach_pricing names it, but its stock is %r, not \"mart\"" % by_id[who].get("stock")))
            if not (isinstance(rb, int) and not isinstance(rb, bool) and 0 <= rb <= 8):
                out.append((who, "early_reach_pricing.reachable_from_badges must be a whole number of badges, 0-8"))
            if not (e or {}).get("why"):
                out.append((who, "early_reach_pricing needs a why: the badges a town is reachable with is a finding"))
    tiers = ((doc.get("stock_policy") or {}).get("mart") or {}).get("tiers")
    if tiers is not None:
        seen_items = set(mart_items(doc.get("stock_policy")))
        if not isinstance(tiers, list):
            out.append((None, "stock_policy.mart.tiers must be a list"))
            tiers = []
        for t in tiers:
            b = t.get("badges") if isinstance(t, dict) else None
            if not (isinstance(b, int) and not isinstance(b, bool) and 1 <= b <= 8):
                out.append((None, "stock_policy.mart.tiers: badges must be 1-8 (tier 0 is mart.items), got %r" % (b,)))
            for iid in (t.get("items") if isinstance(t, dict) else None) or []:
                if not (isinstance(iid, str) and ":" in iid):
                    out.append((None, "stock_policy.mart.tiers: %r is not a namespaced item id" % (iid,)))
                elif iid in seen_items:
                    out.append((None, "stock_policy.mart.tiers: %s is listed twice (or is already a basic item)" % iid))
                seen_items.add(iid)
    return out


def rcon_counts(server_dir, recs, settle=(4, 30), policy=None, leaks=None, tiers=None):
    """{id: (tagged count anywhere loaded, tagged count on its spot, untagged copies on its spot)} from a running
    server. Force-loads each plaza and polls until two samples agree: entities appear some ticks after their chunk.
    With a policy and a leaks dict, also reads each standing trader's shop and records withheld items it still sells."""
    import runtime_guard
    module, pw = runtime_guard.rcon(server_dir)
    run = lambda c: module.run([c], pw, timeout=120)[0].strip()

    def n(sel):
        run("execute store result score #n cobblers_traders if entity %s" % sel)
        return int(re.search(r"has (-?\d+)", run("scoreboard players get #n cobblers_traders")).group(1))

    run("scoreboard objectives add cobblers_traders dummy")
    ents = {r["template"]: entity_of(server_dir, r["template"]) for r in recs}
    by_town = {}
    for r in recs:
        by_town.setdefault(r["settlement"], []).append(r)
    out = {}
    for town, trs in by_town.items():
        box = "%d %d %d %d" % plaza_box(trs)
        run("forceload add %s" % box)
        try:
            step, limit = settle
            last, waited = None, 0
            while True:
                time.sleep(step)
                waited += step
                now = {}
                for r in trs:
                    x, y, z = (r["position"][k] for k in "xyz")
                    spot = "x=%d.5,y=%d,z=%d.5,distance=..%d" % (x, y, z, SPOT_RADIUS)
                    now[r["id"]] = (n("@e[tag=%s]" % tag_of(r["id"])), n("@e[tag=%s,%s]" % (tag_of(r["id"]), spot)),
                                    n("@e[%s]" % stray_selector(ents[r["template"]][0], display_name(ents[r["template"]][1]), x, y, z)))
                if now == last or waited >= limit:
                    out.update(now)
                    break
                last = now
            if policy is not None and leaks is not None:
                held = set(policy.get("withhold_items") or [])
                for r in trs:
                    if r.get("stock") == "withdrawn" or not out[r["id"]][0]:
                        continue
                    shop = run("data get entity @e[tag=%s,limit=1] CobbleMerchantShop" % tag_of(r["id"]))
                    ids = set(re.findall(r'id: "([^"]+)"', shop))
                    cats = set(re.findall(r'Category: "([^"]+)"', shop))
                    if r.get("stock") in ("mart", "stones"):
                        # a Mart sells the basic items and nothing else, and all of them; the Exchange the stones
                        want = mart_shop_items(policy, r["id"], (tiers or {}).get(r["id"], 0)) \
                            if r.get("stock") == "mart" else set(stone_items(policy))
                        bad = sorted(ids - want) + sorted("missing " + i for i in want - ids)
                    else:
                        bad = sorted(ids & held) + sorted("category " + c for c in cats & set(policy.get("withhold_categories") or []))
                    if bad:
                        leaks[r["id"]] = bad
        finally:
            run("forceload remove %s" % box)
    return out


def world_counts(world_dir, recs):
    """{id: (tagged count in the chunks around its spot, tagged on its spot, None)} from a stopped world's
    entity files. Untagged copies are not counted offline."""
    import runtime_guard
    world = Path(runtime_guard.check(world_dir, "read"))
    want = {}
    for r in recs:
        x, z = r["position"]["x"], r["position"]["z"]
        for cx in range((x >> 4) - 1, (x >> 4) + 2):
            for cz in range((z >> 4) - 1, (z >> 4) + 2):
                want.setdefault((cx >> 5, cz >> 5), set()).add((cx & 31, cz & 31))
    found = []
    for (rx, rz), chunks in want.items():
        path = world / "entities" / ("r.%d.%d.mca" % (rx, rz))
        if not path.is_file():
            continue
        for _, _, ch in nbt.region_chunks(path, wanted=chunks):
            for e in ch.get("Entities") or []:
                tags = [t[1] if isinstance(t, tuple) else t for t in e.get("Tags") or []]
                pos = [p[1] if isinstance(p, tuple) else p for p in e.get("Pos") or []]
                found.append((set(tags), pos))
    out = {}
    for r in recs:
        tag = tag_of(r["id"])
        x, y, z = (r["position"][k] + 0.5 if k != "y" else r["position"][k] for k in "xyz")
        mine = [p for tags, p in found if tag in tags]
        near = [p for p in mine if len(p) == 3 and ((p[0] - x) ** 2 + (p[1] - y) ** 2 + (p[2] - z) ** 2) ** 0.5 <= SPOT_RADIUS]
        out[r["id"]] = (len(mine), len(near), None)
    return out


def problems_from_counts(counts, withdrawn=()):
    out = []
    for rid, (total, on_spot, strays) in sorted(counts.items()):
        if rid in withdrawn:
            if total or strays:
                out.append((rid, "withdrawn under the stock policy, but %d tagged and %s untagged copies stand"
                            % (total, strays if strays is not None else "?")))
            continue
        if total == 0:
            out.append((rid, "absent: no entity carries %s" % tag_of(rid)))
        elif total > 1:
            out.append((rid, "%d copies carry %s; there must be one" % (total, tag_of(rid))))
        if total and not on_spot:
            out.append((rid, "not on its spot: none within %d blocks" % SPOT_RADIUS))
        if strays:
            out.append((rid, "%d untagged copies of it round the plaza" % strays))
    return out


def world_problems(doc, world_dir):
    """[(id, message)] for placed/verified traders missing, doubled or off their spot in a stopped world."""
    recs = [r for r in doc.get("traders") or [] if isinstance(r, dict) and r.get("status") in PLACED]
    return problems_from_counts(world_counts(world_dir, recs), {r["id"] for r in recs if r.get("stock") == "withdrawn"})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest", default=str(MANIFEST))
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("function")
    f.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_ROOT"),
                   help="the server whose packs hold the shopkeeper templates; defaults to $COBBLERS_SERVER_ROOT")
    f.add_argument("--out", default=str(DEFAULT_OUT))
    v = sub.add_parser("verify")
    g = v.add_mutually_exclusive_group(required=True)
    g.add_argument("--world")
    g.add_argument("--rcon", metavar="SERVER_DIR")
    v.add_argument("--settlement", action="append", help="only these towns (default: every trader in the manifest)")
    sub.add_parser("tiers", help="each Mart clerk's tier and what it sells (no server needed)")
    a = p.parse_args(argv)
    doc = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    problems = static_problems(doc, placements, ROOT / "derived" / "towns")
    if problems:
        for rid, m in problems:
            print("ERROR %s: %s" % (rid, m))
        return 1
    recs = doc["traders"]
    tiers = mart_tiers(doc, load_towns())
    if a.cmd == "tiers":
        policy = doc.get("stock_policy")
        for r in sorted((r for r in recs if r.get("stock") == "mart"), key=lambda q: (tiers[q["id"]], q["id"])):
            add = sorted(mart_tier_items(policy, tiers[r["id"]]))
            print("%-18s %-12s tier %d%s  +%d: %s" % (r["id"], r["settlement"], tiers[r["id"]],
                                                     " (override)" if "mart_tier" in r else "", len(add),
                                                     ", ".join(i.split(":")[1] for i in add) or "-"))
            floors = early_reach_prices(policy, r["id"])
            if floors:
                held = {i: b for i, b in floors.items() if i in add}
                show = lambda b: ("x%s" % b[1]) if b[0] == "markup" else str(b[1])
                for kind, label in (("markup", "convenience (normal price x markup)"), ("floor", "income gate")):
                    part = sorted(((i, b) for i, b in held.items() if b[0] == kind), key=lambda kv: (kv[1][1], kv[0]))
                    print("%-18s   early-reach %s, reachable at %d badges: %s"
                          % ("", label, early_reach_policy(policy)["traders"][r["id"]]["reachable_from_badges"],
                             ", ".join("%s %s" % (i.split(":")[1], show(b)) for i, b in part) or "-"))
        return 0
    if a.cmd == "function":
        if not a.server_dir:
            raise SystemExit("no server directory: pass --server-dir, or set COBBLERS_SERVER_ROOT")
        cache = {}
        entity = lambda t: cache.setdefault(t, entity_of(a.server_dir, t))
        out = Path(a.out)
        fdir = out / "data" / "cobblers" / "function" / "towns"
        fdir.mkdir(parents=True, exist_ok=True)
        (out / "pack.mcmeta").write_text(json.dumps(
            {"pack": {"pack_format": 48, "description": "Cobblers town traders (generated)"}}, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        policy = doc.get("stock_policy")
        for r in recs:
            _, kept, held = apply_stock_policy(dict(entity(r["template"])[1]), policy, r.get("stock"), r["id"],
                                               tiers.get(r["id"], 0))
            if r.get("stock") == "mart":
                # a tier line the template does not stock would be silently missing from the shelf: refuse
                missing = (mart_items(policy) | mart_tier_items(policy, tiers.get(r["id"], 0))) - set(kept or [])
                if missing:
                    raise SystemExit("%s: a Mart clerk read from %s, which does not sell %s"
                                     % (r["id"], r["template"], ", ".join(sorted(missing))))
                continue
            if r.get("stock") == "stones":
                continue                                   # authored, not filtered: static_problems checked it
            want = "withdrawn" if kept == [] else "regional"
            if r.get("stock") != want:
                raise SystemExit("%s: data/traders.json says stock %r, but the stock policy leaves it %s (%d kept, %d "
                                 "withheld); record what it will actually be" % (r["id"], r.get("stock"), want, len(kept or []), len(held)))
        by_town = {}
        for r in recs:
            by_town.setdefault(r["settlement"], []).append(r)
        for town, trs in sorted(by_town.items()):
            for name, lines in town_functions(town, trs, entity, policy, tiers).items():
                refused = function_limits.check_lines(lines, name)
                if refused:
                    raise SystemExit("%s: %d command(s) the server would refuse" % (name, len(refused)))
                (fdir / ("%s.mcfunction" % name)).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            print("wrote vendors_%s: %d traders" % (town, len(trs)))
        return 0
    if a.settlement:
        recs = [r for r in recs if r["settlement"] in a.settlement]
    leaks = {}
    counts = world_counts(a.world, recs) if a.world else rcon_counts(a.rcon, recs, policy=doc.get("stock_policy"), leaks=leaks,
                                                                     tiers=tiers)
    problems = problems_from_counts(counts, {r["id"] for r in recs if r.get("stock") == "withdrawn"})
    problems += [(rid, "still sells withheld stock: %s" % ", ".join(v)) for rid, v in sorted(leaks.items())]
    for rid, (total, on_spot, strays) in sorted(counts.items()):
        print("%-16s %d tagged, %d on its spot%s" % (rid, total, on_spot, "" if strays is None else ", %d untagged copies" % strays))
    for rid, m in problems:
        print("PROBLEM %s: %s" % (rid, m))
    print("%d traders checked, %d problems" % (len(counts), len(problems)))
    if not counts:
        # fail closed: a selection that matches no trader (a mistyped --settlement, an empty manifest) checked nothing
        print("PROBLEM: no trader was checked")
        return 1
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
