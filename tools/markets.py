#!/usr/bin/env python
"""Town markets: a CobbleDollars merchant at every counter and every stall, paid through the merchant's own screen.
Generated from data/markets.json into the world-local datapack build/datapacks/cobblers_markets.

The design is docs/mechanics/PROGRESSION_LADDER.md revision 2 (the curve) and docs/mechanics/TIERED_GOODS.md (the
ids, read from the server's jars). Since 2026-10-06 (the owner, after playing: "need the steve traders gone. the
button list for purchases is bad, should be the villagers with ui only"; data/markets.json `decisions`
counters_are_merchants) every seller is a CobbleDollars merchant, `cobbledollars:cobble_merchant`
(docs/research/notes/cobbleverse-merchants.md), summoned by stalls/merchants/<town>_place with a CobbleMerchantShop
built from its lines (data/markets.json `stall_merchant`): one category, one offer per line at the line's unit price,
Item count 1. The merchant's own screen takes the money, so no seller has a dialogue, NPC class or purchase function.

  the keeper     a merchant at its seat (the squares' contract keeper_at, else the record's at/yaw), named, NoAI,
                 turned to the seat's yaw. Its town's place step first runs <town>_clear, which kills every
                 cobblemon:npc within remove_radius of each merchant seat (the dialogue keepers R17M placed with
                 spawnnpcat until 2026-10-04 at the stalls and 2026-10-06 at the counters: they carry no tag, so they
                 are known by their seat), then summons; 100 ticks later <town>_done kills older copies of each
                 merchant, where the new one stands. R17M reads every merchant back from the world (verify)
  the gates      none. The screen shows one list to every player (MARKET_GATING.md section 1), so a line cannot wait
                 for a badge: every counter line that was gated keeps its old gate in `gate_dropped` {gate, decision,
                 why}, and a line still carrying a gate is refused. A counter's badge still places it on the curve
                 and the backpack ladder
  the recipes    every Sophisticated Backpacks item a built counter sells has its recipe switched off in
                 modpack/config/sophisticatedcore-common.toml (`enabledItems`, "<id>|false"), the mod's own documented
                 key, written by `overlay` from the base file so the overlay differs from Cobbleverse's in nothing else

Only counters and stalls whose status is "sited" are emitted; the rest live in the data, each with why.

The stalls (2026-10-03, the owner: "more traders, and new ones ... per town, reading as the place"): data/markets.json
`stalls`, the town squares' stalls, merchants since 2026-10-04 (the owner: "the steve villagers aren't it, it should
be the cobbleverse ones that have nice ui"). A stall is not a counter: the one-counter-per-town rule, the backpack
ladder and the clerk rule stay the counters'. Its own rules:
  stock      what the place makes: every line names the jar it was verified in (`verified`); an id not verified is
             listed under `unverified` and never emitted; no Sophisticated Backpacks item (the ladder is the
             counters'); no item that is, or places, a block a spawn condition names (data/spawn_blocks.json: a
             player who buys it could decide encounters); a `provision` line is ungated, vanilla, and none of the
             vanilla items that win fights or print money (NOT_PROVISION); no line is gated (the merchant)
  site       each keeper stands at its stall: the squares' contract, data/plaza_centres.json ("stalls": [{"id":
             "<town>_stall_<n>", "at", "facing", "keeper_at": [x, y, z, yaw], "sells"}]), wins when it names the
             record's `stall`; otherwise the record's own `at`/`yaw`, measured on the plaza from the data (the
             fallback). A contract seat is held to its stall: within STALL_REACH of the stall's `at` and facing its
             customers, along the stall's `facing` (since 2026-10-04 the keeper stands at the tent's open front, in
             front of the table; on Pacifidlog's deck too, where a fallback faces the raft's centre instead). A
             counter may name a `stall` too: its keeper then moves onto the square. When the contract
             exists, every stall in it must be staffed by exactly one record (an empty stall is the complaint the
             owner made)
  places     data/markets.json `places_beyond_towns` names settlements that are not in data/towns.json (the
             Windward Deep's city) so the coverage rule sees them (CLAUDE.md "Our list is not the world")

The audit is offline and fails closed (the implementer's audit; its tests belong to the test author):

  data       every town in data/towns.json has a counter or a no_counter reason; every badge flag is planned by
             tools/progression_pack.py; no counter line is gated, and a line whose gate was dropped records it
             (gate_dropped: a declared badge, the decision in `decisions`, why; on a critical-path counter its own
             badge -- until 2026-10-06 the rule was "a critical-path counter gates on its own badge"); prices are
             positive whole dollars that divide by their count, and every unit price is ABOVE data's bank sell-back
             for the same item (a shop at or under it is a money printer, PROGRESSION_LADDER 6.4)
  curve      ECONOMY_OVERHAUL.md section 7 R2 (2026-10-10): on the critical path, every badge's cumulative ask (the
             convenience lines, a pick-one group at its dearest, stretch items aside, plus curve_rule's fight
             allowance) over what the road earns (trainer income + produce allowance + one gathering hour a leg at
             data/bank.json effort_model's tier) is inside price_policies.curve_scale.band; with the stretch items it
             stays below what the road earns; fights never exceed trainer income. Every curve line is priced by the
             curve rule (curve_prices: one scale a leg on its list_price, to the band's midpoint), never by hand;
             backpack tiers unlock in tier order and cost more as they rise
  recipes    the committed overlay is exactly what `overlay` writes; every Sophisticated Backpacks item a built
             counter sells is off, unless left_craftable says why; nothing sold only by an unbuilt counter is off
  sites      every built keeper stands one above its plan ground (the plaza's graded paving inside the plaza, else
             tools/ambient.py Site: the street paving or the heightmap), on a cell and its four neighbours that no
             lot, anchor, lamp, building (1-block margin), earthwork or dressing piece takes, 3.5+ blocks from every
             other placed NPC and every trader clerk, 3+ from every walked route line, above the sea; on its Mart's
             DOOR side (the Mart anchor's `facing`), inside its town's footprint, off every street's paved width, and
             facing its plaza's centre (R17M: "beside its town's Mart and turned to face its plaza")
  the output one merchant summon per sited counter and stall, holding exactly its lines (merchant_problems); no
             dialogue, NPC class, purchase function or charge macro emitted for any seller; each town's place step
             runs its _clear (the old dialogue keepers, by seat) before its summons; every function passes
             tools/function_limits.py

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
import function_limits  # noqa: E402

DATA = ROOT / "data" / "markets.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_markets"
NS = "cobblers"
SCORE, COOLDOWN, GAVE = "cobblers_market", "cobblers_market_cd", "cobblers_market_gave"
ID = re.compile(r"[a-z0-9_]+")
ITEM = re.compile(r"[a-z0-9_.\-]+:[a-z0-9_/.\-]+")
SB = "sophisticatedbackpacks:"
BACKPACK_TIERS = ["backpack", "copper_backpack", "iron_backpack", "gold_backpack", "diamond_backpack", "netherite_backpack"]
NPC_CLEAR = 3.5        # reapply's npc action counts cobblemon:npc within 2 blocks; the ferry audit uses 2.5 + 0.5
ROUTE_CLEAR = 3.0      # tools/npc_seats.py MIN_ROUTE: an immovable NPC this close to a walked line stands in the road
YAW_SLACK = 15.0
PLAZAS = ROOT / "data" / "plaza_centres.json"      # the squares' contract (another builder's); absent is allowed
SPAWN_BLOCKS = ROOT / "data" / "spawn_blocks.json"
STALL_ID = re.compile(r"([a-z0-9_]+)_stall_([0-9]+)")
STALL_REACH = 4.0      # a keeper at a contract stall stands within this of the stall's own `at` (it serves across it)
STRANDS = ("convenience", "power", "provision")
# vanilla items that win fights, skip the game's gates, or that the bank buys back as currency: never a provision
NOT_PROVISION = re.compile(r"minecraft:(?:diamond_.*|netherite_.*|enchanted_.*|totem_of_undying|elytra|experience_bottle|"
                           r"ender_pearl|ender_eye|emerald.*|golden_apple|.*_spawn_egg|.*shulker_box|beacon|spawner|"
                           r"trial_key|ominous_.*|name_tag|saddle|.*_horse_armor)")
# an item that places a different block than its own id: the spawn check reads the block it puts down
PLACES = {"minecraft:wheat_seeds": "minecraft:wheat", "minecraft:beetroot_seeds": "minecraft:beetroots",
          "minecraft:sweet_berries": "minecraft:sweet_berry_bush", "minecraft:glow_berries": "minecraft:cave_vines",
          "minecraft:torch": "minecraft:wall_torch", "minecraft:redstone": "minecraft:redstone_wire",
          "minecraft:potato": "minecraft:potatoes", "minecraft:carrot": "minecraft:carrots",
          "minecraft:melon_seeds": "minecraft:melon_stem", "minecraft:pumpkin_seeds": "minecraft:pumpkin_stem",
          "minecraft:water_bucket": "minecraft:water", "minecraft:lava_bucket": "minecraft:lava"}
# The ground rule (tools/ground_rule.py): nothing here reads a world; every position comes from the plan and the heightmap.
WORLD_READS: set = set()


class MarketError(SystemExit):
    pass


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def emitted(doc):
    return [c for c in doc["counters"] if c.get("status") == "sited"]


def emitted_stalls(doc):
    return [s for s in doc.get("stalls") or [] if s.get("status") == "sited"]


def merchant_records(doc):
    """[(record, kind)] of every sited seller, each a CobbleDollars merchant since 2026-10-06: the counters ('counter'),
    then the stalls ('stall')."""
    return [(c, "counter") for c in emitted(doc)] + [(s, "stall") for s in emitted_stalls(doc)]


def load_plazas(path=None):
    """{stall id: the stall's contract record, with '_town'} from data/plaza_centres.json, the squares' builder's
    contract: per town, "stalls": [{"id": "<town>_stall_<n>", "at", "facing", "keeper_at": [x, y, z, yaw], "sells"}].
    The file's outer shape is the other builder's, so every "stalls" list anywhere in it is read, and its town is the
    nearest enclosing "town" field or dict key. {} when the file does not exist: every keeper then stands at its own
    record's fallback position."""
    p = Path(path) if path is not None else PLAZAS
    if not p.is_file():
        return {}
    out = {}

    def walk(o, town):
        if isinstance(o, dict):
            town = o.get("town") if isinstance(o.get("town"), str) else town
            for k, v in o.items():
                if k == "stalls" and isinstance(v, list):
                    for s in v:
                        if isinstance(s, dict) and s.get("id"):
                            if s["id"] in out:
                                raise MarketError("%s: stall %s appears twice" % (p.name, s["id"]))
                            out[s["id"]] = dict(s, _town=town)
                elif isinstance(v, (dict, list)):
                    walk(v, k if isinstance(v, dict) and k not in ("towns", "plazas") else town)
        elif isinstance(o, list):
            for v in o:
                walk(v, town)

    walk(json.loads(p.read_text(encoding="utf-8")), None)
    return out


def contract_keeper(rec, plazas):
    """The contract's keeper_at [x, y, z, yaw] for this record's stall, or None."""
    s = plazas.get(rec.get("stall")) if rec.get("stall") else None
    k = (s or {}).get("keeper_at")
    if isinstance(k, list) and len(k) == 4 and all(isinstance(v, (int, float)) for v in k):
        return k
    return None


def position(rec, plazas):
    """(at [x, y, z], yaw, source): the squares' contract when it seats this record's stall, else the record's own."""
    k = contract_keeper(rec, plazas)
    if k is not None:
        return [int(k[0]), int(k[1]), int(k[2])], k[3], "contract"
    return rec.get("at"), rec.get("yaw"), "record"


def money(n):
    return "{:,}".format(int(n))


# ---------------------------------------------------------------------------------------------------- the pack
def build(doc, plazas=None):
    """{relative path in the pack: content (list of lines, or a JSON object)} and the dialogue NPCs to place (none since
    2026-10-06: every seller is a merchant, summoned by MERCHANTS_FN)."""
    plazas = load_plazas() if plazas is None else plazas
    files = {"pack.mcmeta": {"pack": {"pack_format": 48, "description": "Cobblers town markets (generated by tools/markets.py)"}},
             "data/minecraft/tags/function/load.json": {"values": ["%s:markets/load" % NS]}}
    # R17M runs cobblers:markets/load by name (tools/reapply.py, not this tool's to edit), so it stays: the scores the
    # dialogue purchases used, harmless now that nothing charges here
    files["data/%s/function/markets/load.mcfunction" % NS] = [
        "# the markets' scores (kept: tools/reapply.py R17M runs this function by name; no seller charges here since "
        "2026-10-06)",
        "scoreboard objectives add %s dummy" % SCORE, "scoreboard objectives add %s dummy" % COOLDOWN,
        "scoreboard objectives add %s dummy" % GAVE]
    if merchant_records(doc):
        got = merchant_functions(doc, plazas)
        clash = [k for k in got if k in files]
        if clash:
            raise MarketError("the merchants write %s twice" % clash)
        files.update(got)
    return files, []


def npc_placements(doc=None, plazas=None):
    """The counters' Cobblemon dialogue keepers for tools/reapply.py's "npc" action: since 2026-10-06 none (every
    counter keeper is a CobbleDollars merchant, stall_merchants below, placed by R17M through MERCHANTS_FN; decision
    counters_are_merchants). Kept, and kept empty, so R17M's composition still reads."""
    return []


def stall_placements(doc=None, plazas=None):
    """The stall keepers that are Cobblemon dialogue NPCs, in npc_placements' shape: since 2026-10-04 none (every
    stall keeper is a CobbleDollars merchant, stall_merchants below, placed by R17M through MERCHANTS_FN). Kept, and
    kept empty, so a caller that still counts dialogue stall keepers gets none rather than an error."""
    return []


# ---------------------------------------------------------------------------------------------------- the merchants
MERCHANTS_DIR = "stalls/merchants"
MERCHANTS_FN = "%s:%s/all" % (NS, MERCHANTS_DIR)
MERCHANT_LOAD_WAIT = 40     # ticks from forceload to summon (tools/traders.py LOAD_WAIT, measured 2026-09-21)
MERCHANT_DEDUPE_WAIT = 100  # ticks from summon to the removals (tools/traders.py DEDUPE_WAIT)
MERCHANT_MARGIN = 8         # force-loaded round a town's stalls: every old keeper stood within remove_radius of a seat


def merchant_cfg(doc):
    cfg = doc.get("stall_merchant")
    if not isinstance(cfg, dict):
        raise MarketError("data/markets.json has no stall_merchant block: the stall keepers cannot be summoned")
    return cfg


def merchant_tag(doc, stall):
    return "%s_%s" % (merchant_cfg(doc)["tag"], stall["id"])


def merchant_shop(stall):
    """The seller's CobbleMerchantShop: one category, one offer per stock line at the line's unit price (count 1, the
    only Item.count verified in a merchant offer; data/markets.json stall_merchant.offers). A stall's or a counter's."""
    return [{"Category": stall["category"],
             "Offers": [{"Item": {"count": 1, "id": it["item"]}, "Price": str(int(it["price"]) // int(it["count"]))}
                        for it in stall["stock"]]}]


def stall_merchants(doc=None, plazas=None):
    """[{stall, kind, town, at (x, y, z), yaw, tag, name, data}] for every sited counter and stall: the merchant R17M
    summons. `stall` is the record's id (a counter's too: the ids never repeat across the two lists, collision_problems)."""
    doc = doc or load()
    plazas = load_plazas() if plazas is None else plazas
    cfg = merchant_cfg(doc)
    out = []
    for s, kind in merchant_records(doc):
        at, yaw, _src = position(s, plazas)
        tag = merchant_tag(doc, s)
        data = {"CustomName": json.dumps({"text": s["keeper"]["name"]}, ensure_ascii=False),
                "VillagerData": dict(cfg["villager_data"]),
                "CobbleMerchantShop": merchant_shop(s),
                # NoAI: a merchant with AI walked 2-40 blocks off its stall (tools/traders.py); NoAI never turns its
                # head, so the rotation is the seat's yaw, facing the customers
                "NoAI": True, "PersistenceRequired": True, "Invulnerable": True, "Silent": True,
                "Rotation": [float(yaw), 0.0],
                "Tags": [cfg["tag"], tag, cfg["tag"] + "_new"]}
        out.append({"stall": s["id"], "kind": kind, "town": s["town"], "at": tuple(int(v) for v in at), "yaw": yaw,
                    "tag": tag, "name": s["keeper"]["name"], "data": data})
    return out


def merchant_box(ms):
    xs, zs = [m["at"][0] for m in ms], [m["at"][2] for m in ms]
    return min(xs) - MERCHANT_MARGIN, min(zs) - MERCHANT_MARGIN, max(xs) + MERCHANT_MARGIN, max(zs) + MERCHANT_MARGIN


def merchant_functions(doc, plazas):
    """{pack path: lines}: per town, tools/traders.py's three steps (force-load and wait; clear the dialogue keepers
    the merchants replace, then summon with a "new" tag; 100 ticks later, where the new merchant stands, kill the older
    copies of it, drop the tag, release), and `all`, which starts every town's at once.

    <town>_clear kills every cobblemon:npc within remove_radius of each of the town's merchant seats, unguarded and
    BEFORE the summons (2026-10-06: "need the steve traders gone"): the dialogue keepers R17M placed with spawnnpcat
    carry no tag and their classes are no longer shipped, so a seat is the only handle on them, and a merchant that
    failed to summon must still not leave a Steve behind. Every other placed NPC stands NPC_CLEAR+ from a seat (the
    site rules), so the radius reaches no one else. A cobble_merchant is not a cobblemon:npc, so no merchant is hit."""
    import traders as TR
    cfg = merchant_cfg(doc)
    new, radius = cfg["tag"] + "_new", float(cfg["remove_radius"])
    rel = lambda name: "data/%s/function/%s/%s.mcfunction" % (NS, MERCHANTS_DIR, name)
    ref = lambda name: "%s:%s/%s" % (NS, MERCHANTS_DIR, name)
    by_town = {}
    for m in stall_merchants(doc, plazas):
        by_town.setdefault(m["town"], []).append(m)
    files = {rel("all"): ["# Generated by tools/markets.py from data/markets.json: every town's stall merchants (R17M)"]
             + ["function %s" % ref(t) for t in sorted(by_town)]}
    for town, ms in sorted(by_town.items()):
        box = "%d %d %d %d" % merchant_box(ms)
        files[rel(town)] = ["# Generated by tools/markets.py: the stall merchants of %s" % town,
                            "# force-load the stalls and give their saved entities time to load before anything is summoned",
                            "forceload add %s" % box,
                            "schedule function %s %dt replace" % (ref(town + "_place"), MERCHANT_LOAD_WAIT)]
        place = ["# Generated by tools/markets.py; called by %s" % ref(town), "# chunks-loaded-by: %s" % ref(town),
                 "# first the Cobblemon dialogue keepers the merchants replace, then the merchants",
                 "function %s" % ref(town + "_clear")]
        clear = ["# Generated by tools/markets.py; called by %s before its summons: every cobblemon:npc on a merchant "
                 "seat of %s (the dialogue keepers R17M placed with spawnnpcat: no tag, known by the seat)"
                 % (ref(town + "_place"), town), "# chunks-loaded-by: %s" % ref(town)]
        done = ["# Generated by tools/markets.py; %d ticks after the summons: one merchant per seat, then release"
                % MERCHANT_DEDUPE_WAIT]
        for m in sorted(ms, key=lambda q: q["stall"]):
            x, y, z = m["at"]
            place += ["# %s %s: %s, yaw %s" % (m["kind"], m["stall"], m["name"], m["yaw"]),
                      TR.summon_line(cfg["kind"], x, y, z, m["data"])]
            clear += ["# %s %s" % (m["kind"], m["stall"]),
                      "kill @e[type=cobblemon:npc,x=%d.5,y=%d,z=%d.5,distance=..%s]" % (x, y, z, radius)]
            here = "execute if entity @e[tag=%s,tag=%s] run " % (m["tag"], new)
            done += ["# %s" % m["stall"],
                     here + "kill @e[tag=%s,tag=!%s]" % (m["tag"], new),
                     "tag @e[tag=%s,tag=%s] remove %s" % (m["tag"], new, new)]
        place.append("schedule function %s %dt replace" % (ref(town + "_done"), MERCHANT_DEDUPE_WAIT))
        done.append("forceload remove %s" % box)
        files[rel(town + "_place")] = place
        files[rel(town + "_clear")] = clear
        files[rel(town + "_done")] = done
    return files


def shop_offers(snbt):
    """[(item id, price string)] from CobbleMerchantShop SNBT, a summon's or a `data get`'s (spaces allowed, either key
    order: the game may write an item's id before its count). An offer is an object holding exactly one object."""
    out = []
    for o in re.findall(r"\{[^{}]*\{[^{}]*\}[^{}]*\}", snbt):
        i, p = re.search(r'\bid:\s*"([^"]+)"', o), re.search(r'\bPrice:\s*"([^"]*)"', o)
        if i and p:
            out.append((i.group(1), p.group(1)))
    return out


def verify(rc, doc=None, plazas=None):
    """Problems, read from a running server over RCON (tools/reapply.py R17M's check, after MERCHANTS_FN and its wait):
    each sited counter and stall has exactly one merchant with its tag, standing on its seat, holding exactly its
    lines' offers, and no Cobblemon NPC within remove_radius (the dialogue keeper it replaced). Force-loads each town's
    seats while it reads."""
    import time
    doc = doc or load()
    cfg = merchant_cfg(doc)
    radius = float(cfg["remove_radius"])
    stalls = {s["id"]: s for s, _kind in merchant_records(doc)}
    by_town = {}
    for m in stall_merchants(doc, plazas):
        by_town.setdefault(m["town"], []).append(m)
    count = lambda reply: int(re.search(r"count: (\d+)", reply).group(1)) if re.search(r"count: (\d+)", reply) else 0
    out = []
    for town, ms in sorted(by_town.items()):
        box = "%d %d %d %d" % merchant_box(ms)
        rc("forceload add %s" % box)
        x0, y0, z0 = ms[0]["at"]
        for _ in range(30):
            if "passed" in rc("execute if loaded %d %d %d" % (x0, y0, z0)):
                break
            time.sleep(1)
        for m in ms:
            x, y, z = m["at"]
            sel = "@e[type=%s,tag=%s]" % (cfg["kind"], m["tag"])
            n = 0
            for _ in range(12):            # a chunk's entities load after its blocks (reapply's npc action)
                n = count(rc("execute if entity %s" % sel))
                if n:
                    break
                time.sleep(0.5)
            if n != 1:
                out.append("%s: %d merchants tagged %s, not 1" % (m["stall"], n, m["tag"]))
                continue
            npcs = count(rc("execute if entity @e[type=cobblemon:npc,x=%d.5,y=%d,z=%d.5,distance=..%s]" % (x, y, z, radius)))
            if npcs:
                out.append("%s: %d Cobblemon NPC(s) still within %s of its merchant" % (m["stall"], npcs, radius))
            if "passed" not in rc("execute if entity @e[type=%s,tag=%s,x=%d.5,y=%d,z=%d.5,distance=..0.6]"
                                  % (cfg["kind"], m["tag"], x, y, z)):
                out.append("%s: its merchant is not on its seat (%d, %d, %d)" % (m["stall"], x, y, z))
            shop = rc("data get entity %s CobbleMerchantShop" % sel.replace("]", ",limit=1]"))
            got = shop_offers(shop)
            want = [(it["item"], str(int(it["price"]) // int(it["count"]))) for it in stalls[m["stall"]]["stock"]]
            if sorted(got) != sorted(want):
                out.append("%s: its shop reads %s, the stall's lines %s" % (m["stall"], sorted(got), sorted(want)))
        rc("forceload remove %s" % box)
    return out


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


# ---------------------------------------------------------------------------------------------------- price policies
# data/markets.json price_policies.income_gate (the owner, 2026-10-09: "TMs AT COUNTERS: price them above the income
# gate"). A stock line carrying price_rule "income_gate" and a declared gate_badge B is priced by THIS rule, never by
# hand: per unit, the smallest multiple of round_to strictly above income_basis.cumulative_by_badge[B] (the most a
# player with B-1 badges can hold, data/traders.json stock_policy.mart.early_reach_pricing's INCOME GATE); an exchange
# line keeps its material and takes the smallest whole count of it whose bank value clears the same bar, priced at
# exactly count x the bank's price (data/bank.json exchanges.shape). `prices --write` writes the result into the data;
# the audit refuses a line whose price is not the rule's. A counter's held_stock carries lines the rule prices but
# nothing sells, each with its reason.
POLICY = "income_gate"
GATE_BADGES = range(1, 9)


def income_gate_policy(doc):
    return ((doc.get("price_policies") or {}).get(POLICY)) or {}


def policy_lines(doc):
    """[(counter, line, held)] for every counter line (stock or held_stock) under the income-gate rule."""
    return [(c, it, held) for c in doc.get("counters") or [] for held, key in ((False, "stock"), (True, "held_stock"))
            for it in c.get(key) or [] if it.get("price_rule") == POLICY]


def leader_badges(progression=None):
    """{item: the lowest gym N whose leader's first win offers it} from data/progression.json
    upstream_neutralised.first_win_rewards (flag gymN_cleared, items and one_of)."""
    prog = progression or json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    out = {}
    fwr = ((prog.get("upstream_neutralised") or {}).get("first_win_rewards") or {}).get("trainers") or {}
    for t in fwr.values():
        m = re.fullmatch(r"gym(\d+)_cleared", str(t.get("flag")))
        if m:
            for i in list(t.get("items") or []) + list(t.get("one_of") or []):
                out[i] = min(out.get(i, 99), int(m.group(1)))
    return out


def policy_price(doc, it, bank=None):
    """(price, exchange count or None) that the income-gate rule gives line `it`."""
    gb = it.get("gate_badge")
    if isinstance(gb, bool) or gb not in GATE_BADGES:
        raise MarketError("line %s: gate_badge %r is not a whole badge 1-8" % (it.get("id"), gb))
    cum = ((doc.get("income_basis") or {}).get("cumulative_by_badge") or {}).get(str(gb))
    if not isinstance(cum, int):
        raise MarketError("line %s: income_basis.cumulative_by_badge has no badge %d" % (it.get("id"), gb))
    cnt = it.get("count") or 1
    ex = it.get("exchange_for")
    if ex:
        bank = bank_prices() if bank is None else bank
        if ex.get("item") not in bank:
            raise MarketError("line %s: the bank does not buy its exchange material %r" % (it.get("id"), ex.get("item")))
        n = cum // bank[ex["item"]] + 1
        return n * bank[ex["item"]] * cnt, n
    step = int(income_gate_policy(doc).get("round_to") or 0)
    if step <= 0:
        raise MarketError("price_policies.income_gate.round_to must be a positive whole number")
    return (cum // step + 1) * step * cnt, None


def ball_ceiling(doc):
    """(unit price, line id) of the cheapest `ball` exchange line on a counter: tools/bank.py's exchange floor needs
    every ball exchange to cost MORE than the dearest non-exchange line on any shelf, so a stocked income-gate line
    must stay under this."""
    got = [(it["price"] / (it.get("count") or 1), it["id"]) for c in doc.get("counters") or []
           for it in c.get("stock") or [] if it.get("exchange_for") and it.get("kind") == "ball"]
    return min(got) if got else (None, None)


def price_policy_problems(doc, progression=None, bank=None):
    out = []
    pol = income_gate_policy(doc)
    lines = policy_lines(doc)
    if lines and not pol:
        return ["%d line(s) name price_rule income_gate but data/markets.json has no price_policies.income_gate"
                % len(lines)]
    leaders = leader_badges(progression)
    ceiling, ceiling_id = ball_ceiling(doc)
    for c, it in [(c, it) for c in doc.get("counters") or [] for it in c.get("stock") or []
                  if "gate_badge" in it and it.get("price_rule") != POLICY]:
        out.append("counter %s item %s: gate_badge without price_rule income_gate (its price would be hand-typed)"
                   % (c["id"], it.get("id")))
    seen = {}
    for c, it, held in lines:
        where = "counter %s %s %s" % (c["id"], "held line" if held else "item", it.get("id"))
        seen.setdefault(it.get("item"), []).append(where)
        try:
            price, n = policy_price(doc, it, bank)
        except MarketError as e:
            out.append("%s: %s" % (where, e))
            continue
        if not it.get("gate_why"):
            out.append("%s: no gate_why (why badge %s is this item's gate)" % (where, it.get("gate_badge")))
        if it.get("price") != price:
            out.append("%s: price %r is not the income-gate rule's $%d (run tools/markets.py prices --write)"
                       % (where, it.get("price"), price))
        if n is not None and (it.get("exchange_for") or {}).get("count") != n:
            out.append("%s: exchange_for count %r is not the rule's %d" % (where, it["exchange_for"].get("count"), n))
        lb = leaders.get(it.get("item"))
        if it.get("item", "").startswith("tmcraft:") and lb != it.get("gate_badge"):
            out.append("%s: a leader's TM gates on the badge its leader gives (gym %s in data/progression.json "
                       "first_win_rewards), not %r" % (where, lb, it.get("gate_badge")))
        unit = price / (it.get("count") or 1)
        if held:
            h = it.get("held") or {}
            if not h.get("reason") or not h.get("why"):
                out.append("%s: held with no held.reason and held.why" % where)
            elif h["reason"] == "ball_floor" and ceiling is not None and unit < ceiling:
                out.append("%s: held for the ball floor, but its $%s is now under %s's $%s: release it to stock"
                           % (where, money(unit), ceiling_id, money(ceiling)))
        elif not it.get("exchange_for") and ceiling is not None and unit >= ceiling:
            out.append("%s: $%s is not under %s's $%s, so the Master Ball exchange would fall under tools/bank.py's "
                       "ball floor: hold it (held_stock, reason ball_floor)" % (where, money(unit), ceiling_id,
                                                                                 money(ceiling)))
    for item, ws in seen.items():
        if len(ws) > 1:
            out.append("%s is under the income-gate rule twice: %s" % (item, "; ".join(ws)))
    return out


def price_table(doc, bank=None):
    """[(counter, line, held, price, exchange count)] for every income-gate line."""
    return [(c, it, held) + policy_price(doc, it, bank) for c, it, held in policy_lines(doc)]


def write_prices(path, doc, bank=None):
    """Rewrite each income-gate line's price (and exchange count) in the data file's own text, one line per stock
    entry, so nothing else in the file moves. Returns the number of lines changed."""
    text = Path(path).read_text(encoding="utf-8")
    rows = text.split("\n")
    changed = 0
    table = price_table(doc, bank)
    if curve_policy(doc):
        _scales, cp = curve_prices(doc)
        table += [(c, it, False, cp[(c["id"], it["id"])], None) for c, it in curve_lines(doc)
                  if it.get("price_rule") == CURVE_POLICY]
    for c, it, held, price, n in table:
        key = '{"id": "%s", "item": "%s"' % (it["id"], it["item"])
        hits = [i for i, r in enumerate(rows) if key in r]
        if len(hits) != 1:
            raise MarketError("prices --write: %d lines of %s carry %s; expected one" % (len(hits), path, key))
        i = hits[0]
        new = re.sub(r'"price": -?\d+', '"price": %d' % price, rows[i], count=1)
        if n is not None:
            new = re.sub(r'("exchange_for": \{"item": "[^"]+", "count": )\d+', r"\g<1>%d" % n, new, count=1)
        if new != rows[i]:
            rows[i] = new
            changed += 1
    if changed:
        Path(path).write_text("\n".join(rows), encoding="utf-8", newline="\n")
    return changed


def static_problems(doc, planned_flags, towns, traders):
    out = []
    town_ids = [t["id"] for t in towns]
    # settlements that are not in data/towns.json but are places a player arrives and could spend (the Deep's city):
    # each names the file that authors it, which must exist, and is then held to the same coverage rule
    for b in doc.get("places_beyond_towns") or []:
        if not b.get("town") or not b.get("source") or not b.get("why"):
            out.append("places_beyond_towns: %r needs town, source and why" % b)
            continue
        if not (ROOT / b["source"]).is_file():
            out.append("places_beyond_towns %s: its source %s does not exist" % (b["town"], b["source"]))
        if b["town"] in town_ids:
            out.append("places_beyond_towns %s is already a town in data/towns.json" % b["town"])
        town_ids.append(b["town"])
    covered =[c.get("town") for c in doc["counters"]] + [n.get("town") for n in doc.get("no_counter") or []]
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
    decided = {d.get("id") for d in doc.get("decisions") or []}
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
            # a keeper stands beside its Mart's clerk, or at a stall on its square (Redbrow has no Mart: its
            # Prospector keeps a stall on the yard instead, 2026-10-03)
            if tr is None and not c.get("stall"):
                out.append("counter %s: sited with no near_trader to stand beside and no stall" % cid)
            if not (isinstance(c.get("at"), list) and len(c["at"]) == 3 and isinstance(c.get("yaw"), (int, float))):
                out.append("counter %s: sited without at [x, y, z] and yaw" % cid)
        k = c.get("keeper") or {}
        if not k.get("name") or not k.get("greeting"):
            out.append("counter %s: keeper without name or greeting" % cid)
        if '"' in (k.get("name") or "") or "\\" in (k.get("name") or ""):
            out.append("counter %s: keeper name %r carries a quote or backslash (it is the merchant's CustomName)"
                       % (cid, k.get("name")))
        cat = c.get("category")
        if not isinstance(cat, str) or not cat.strip() or len(cat) > 32 or '"' in cat or "\\" in cat:
            out.append("counter %s: category %r is not 1-32 characters without quotes (the merchant screen's category)"
                       % (cid, cat))
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
            if price % cnt:
                out.append("%s: $%d for %d does not divide: the merchant sells singly, at the line's unit price "
                           "(stall_merchant.offers)" % (where, price, cnt))
            # the gates (changed 2026-10-06, decision counters_are_merchants: "should be the villagers with ui only").
            # Until then: every line of a critical-path counter gated on its own badge, Pallet's on none. A merchant
            # shows one list to every player, so no line may carry a gate; the old rule now holds the RECORD of the
            # dropped gate instead: on a critical-path counter every line names its own badge in gate_dropped
            g, gd = it.get("gate"), it.get("gate_dropped")
            if g is not None:
                out.append("%s: gated on %r, but its merchant shows every line to every player (decision "
                           "counters_are_merchants): record the old gate in gate_dropped" % (where, g))
            if gd is not None:
                if not (isinstance(gd, dict) and gd.get("gate") in badges and gd.get("decision") in decided
                        and gd.get("why")):
                    out.append("%s: gate_dropped %r needs a declared badge `gate`, a `decision` in data/markets.json "
                               "decisions and a `why`" % (where, gd))
                    continue
            dropped = gd.get("gate") if isinstance(gd, dict) else None
            if own and dropped != own:
                out.append("%s: a critical-path counter at badge %d records a dropped gate %r, not its own %s"
                           % (where, c["badge"], dropped, own))
            if c.get("path") == "critical" and c.get("badge") == 0 and dropped is not None:
                out.append("%s: Pallet's shelf was never gated" % where)
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


def spawn_block_ids():
    if not SPAWN_BLOCKS.is_file():
        raise MarketError("%s is missing: the stalls' spawn-block check cannot run" % SPAWN_BLOCKS)
    return set(json.loads(SPAWN_BLOCKS.read_text(encoding="utf-8"))["blocks"])


def stall_problems(doc, towns, plazas):
    """The stalls' static rules (module docstring, 'The stalls') and the squares' contract against the data."""
    out = []
    town_ids = {t["id"] for t in towns} | {b.get("town") for b in doc.get("places_beyond_towns") or []}
    badges = doc.get("badges") or {}
    crit = {c["town"]: c.get("badge") for c in doc["counters"] if c.get("path") == "critical"}
    bank, spawn = bank_prices(), spawn_block_ids()
    cfg = doc.get("stall_merchant")
    if not isinstance(cfg, dict):
        out.append("stall_merchant: missing (every stall keeper is a CobbleDollars merchant)")
    else:
        vd = cfg.get("villager_data") or {}
        if cfg.get("kind") != "cobbledollars:cobble_merchant" or vd.get("profession") != cfg.get("kind") \
                or vd.get("level") != 99 or not vd.get("type"):
            out.append("stall_merchant: kind and villager_data are not the BCA templates' cobble_merchant, level 99 "
                       "(docs/research/notes/cobbleverse-merchants.md 1)")
        if not ID.fullmatch(cfg.get("tag") or ""):
            out.append("stall_merchant: tag %r" % cfg.get("tag"))
        r = cfg.get("remove_radius")
        if not (isinstance(r, (int, float)) and 1.0 <= r <= NPC_CLEAR - 0.5):
            out.append("stall_merchant: remove_radius %r is not 1 to %.1f (every other NPC stands %.1f+ away)"
                       % (r, NPC_CLEAR - 0.5, NPC_CLEAR))
    staffed = {}
    for c in doc["counters"]:
        if c.get("stall"):
            m = STALL_ID.fullmatch(c["stall"])
            if not m or m.group(1) != c["town"]:
                out.append("counter %s: stall %r is not %s_stall_<n>" % (c["id"], c["stall"], c["town"]))
            if c.get("status") == "sited":
                staffed.setdefault(c["stall"], []).append("counter %s" % c["id"])
    seen = set()
    for s in doc.get("stalls") or []:
        sid = s.get("id") or ""
        where = "stall %s" % sid
        if not ID.fullmatch(sid) or sid in seen:
            out.append("stall id %r is malformed or repeated" % sid)
        seen.add(sid)
        town = s.get("town")
        if town not in town_ids:
            out.append("%s: town %r is neither in data/towns.json nor in places_beyond_towns" % (where, town))
        m = STALL_ID.fullmatch(s.get("stall") or "")
        if not m or m.group(1) != town:
            out.append("%s: stall %r is not %s_stall_<n>" % (where, s.get("stall"), town))
        if s.get("status") not in ("sited", "unsited"):
            out.append("%s: status %r" % (where, s.get("status")))
        if s.get("status") == "unsited" and not s.get("unsited_why"):
            out.append("%s: unsited with no unsited_why" % where)
        if s.get("status") == "sited":
            staffed.setdefault(s.get("stall"), []).append(where)
            if contract_keeper(s, plazas) is None and not (
                    isinstance(s.get("at"), list) and len(s["at"]) == 3 and isinstance(s.get("yaw"), (int, float))):
                out.append("%s: sited, but neither the squares' contract nor its record gives at [x, y, z] and yaw" % where)
        if s.get("path") not in ("critical", "off_path"):
            out.append("%s: path %r" % (where, s.get("path")))
        if s.get("path") == "critical" and (town not in crit or s.get("badge") != crit[town]):
            out.append("%s: on the critical path, but its badge %r is not its town's counter's %r"
                       % (where, s.get("badge"), crit.get(town)))
        k = s.get("keeper") or {}
        if not k.get("name") or not k.get("greeting"):
            out.append("%s: keeper without name or greeting" % where)
        if '"' in (k.get("name") or "") or "\\" in (k.get("name") or ""):
            out.append("%s: keeper name %r carries a quote or backslash (it is the merchant's CustomName)" % (where, k.get("name")))
        cat = s.get("category")
        if not isinstance(cat, str) or not cat.strip() or len(cat) > 32 or '"' in cat or "\\" in cat:
            out.append("%s: category %r is not 1-32 characters without quotes (the merchant screen's category)" % (where, cat))
        if not s.get("theme") or not s.get("sells"):
            out.append("%s: no theme or sells" % where)
        if not s.get("stock"):
            out.append("%s: no stock" % where)
        held = set()
        for u in s.get("unverified") or []:
            if not u.get("item") or not u.get("why"):
                out.append("%s: an unverified entry needs item and why: %r" % (where, u))
            held.add(u.get("item"))
        own = "gym%d_cleared" % s["badge"] if s.get("path") == "critical" and s.get("badge") else None
        ids = set()
        for it in s.get("stock") or []:
            w = "%s item %s" % (where, it.get("id"))
            if not ID.fullmatch(it.get("id") or "") or it["id"] in ids:
                out.append("%s: id malformed or repeated" % w)
            ids.add(it.get("id"))
            item = it.get("item") or ""
            if not ITEM.fullmatch(item):
                out.append("%s: item %r is not ns:path" % (w, item))
            if not it.get("name") or not it.get("why"):
                out.append("%s: no name or why" % w)
            if not it.get("verified"):
                out.append("%s: no `verified` (the jar its id was read from): an unverified id is listed under "
                           "unverified and never emitted" % w)
            if item in held:
                out.append("%s: %s is listed unverified and stocked" % (w, item))
            if item.startswith(SB):
                out.append("%s: a Sophisticated Backpacks item: the ladder is the counters'" % w)
            placed = PLACES.get(item, item)
            if item in spawn or placed in spawn:
                out.append("%s: %s%s is a block a spawn condition names (data/spawn_blocks.json): a player who buys it "
                           "decides encounters" % (w, item, "" if placed == item else " (it places %s)" % placed))
            cnt, price = it.get("count"), it.get("price")
            if not (isinstance(cnt, int) and 1 <= cnt <= 64):
                out.append("%s: count %r" % (w, cnt))
                continue
            if not (isinstance(price, int) and price > 0):
                out.append("%s: price %r is not a positive whole number" % (w, price))
                continue
            sell = bank.get(item)
            if sell is not None and price / cnt <= sell:
                out.append("%s: $%s each is not above the bank's sell-back of $%d" % (w, money(price / cnt), sell))
            if price % cnt:
                out.append("%s: $%d for %d does not divide: the merchant sells singly, at the line's unit price "
                           "(stall_merchant.offers)" % (w, price, cnt))
            g = it.get("gate")
            if g is not None and g not in badges:
                out.append("%s: gate %r is not a declared badge" % (w, g))
            if g is not None:
                out.append("%s: gated on %r, but a stall's merchant shows every line to every player "
                           "(stall_merchant.gated_lines): a gated line belongs on a counter" % (w, g))
            strand = it.get("strand")
            if strand not in STRANDS:
                out.append("%s: strand %r" % (w, strand))
            elif strand == "provision":
                if g is not None:
                    out.append("%s: a provision is ungated (a gated line is convenience or power, and on the curve)" % w)
                if not item.startswith("minecraft:") or NOT_PROVISION.fullmatch(item):
                    out.append("%s: %s is not a provision (vanilla, and none of NOT_PROVISION)" % (w, item))
            elif own and g != own:
                out.append("%s: a %s line on the critical path gates on %r, not its town's own %s" % (w, strand, g, own))
    for sid, who in sorted(staffed.items()):
        if len(who) > 1:
            out.append("stall %s is staffed by %s: one keeper per stall" % (sid, " and ".join(who)))
    for sid, st in sorted(plazas.items()):
        m = STALL_ID.fullmatch(sid)
        if not m:
            out.append("plaza contract: stall id %r is not <town>_stall_<n>" % sid)
            continue
        if st.get("_town") and st["_town"] != m.group(1):
            out.append("plaza contract: stall %s is listed under town %s" % (sid, st["_town"]))
        if len(staffed.get(sid, [])) != 1:
            out.append("plaza contract: stall %s is staffed by %d built keepers, not 1 (an empty stall is what the owner "
                       "asked to end)" % (sid, len(staffed.get(sid, []))))
        k, a = st.get("keeper_at"), st.get("at")
        if not (isinstance(k, list) and len(k) == 4 and all(isinstance(v, (int, float)) for v in k)):
            out.append("plaza contract: stall %s has no keeper_at [x, y, z, yaw]" % sid)
        elif isinstance(a, list) and len(a) == 3 and math.dist((k[0], k[2]), (a[0], a[2])) > STALL_REACH:
            out.append("plaza contract: stall %s's keeper_at is %.1f blocks from its stall, over %.1f"
                       % (sid, math.dist((k[0], k[2]), (a[0], a[2])), STALL_REACH))
    return out


def contract_report(doc, plazas):
    """Lines, not problems: where each keeper that names a stall stands, and any theme the two builders disagree on."""
    if not plazas:
        return ["NOT PRESENT: data/plaza_centres.json (the squares' contract): every keeper stands at its record's "
                "fallback site"]
    out = []
    for rec in [c for c in doc["counters"] if c.get("stall")] + list(doc.get("stalls") or []):
        st = plazas.get(rec["stall"])
        if contract_keeper(rec, plazas) is None:
            out.append("%s: stall %s is not seated by the contract: fallback site %s" % (rec["id"], rec["stall"], rec.get("at")))
        elif st.get("sells") and rec.get("sells") and st["sells"] != rec["sells"]:
            out.append("%s: the contract's stall %s sells %r, the record %r" % (rec["id"], rec["stall"], st["sells"], rec["sells"]))
    return out


def priced(doc):
    """The critical path's priced records: every counter, and each stall's gated lines (an ungated provision is not a
    rung on the ladder; a gated stall line is, and counts exactly as a counter's would)."""
    recs = [c for c in doc["counters"] if c.get("path") == "critical"]
    for s in doc.get("stalls") or []:
        gated = [it for it in s.get("stock") or [] if it.get("gate")]
        if s.get("path") == "critical" and gated:
            recs.append(dict(s, stock=gated))
    return recs


def r2_earned(doc, effort=None):
    """{badge 1-8: (cumulative fight allowance, cumulative trainer income, cumulative earned)} under ECONOMY_OVERHAUL.md
    section 7 R2, this tool's own reading (nothing imported from an audit): earned = trainer income
    (income_basis.cumulative_by_badge) + curve_rule.produce_allowance (leg N is played holding N-1 badges) +
    curve_rule.gathering_hours_per_leg hours a leg at the rate of the data/bank.json effort_model tier opened last by
    that leg, a tier's hour being the sum of rate_per_hour x price over the buys of its from_tiers. MarketError when a
    term is missing."""
    try:
        effort = effort if effort is not None else json.loads(BANK_DATA.read_text(encoding="utf-8"))
        cr = doc["curve_rule"]
        per = int(cr["fight_allowance"]["per_leg"])
        produce = cr["produce_allowance"]["by_badges_held"]
        hours = float(cr["gathering_hours_per_leg"])
        tiers = effort["effort_model"]["tiers"]
        hour = {n: sum(int(b["rate_per_hour"]) * int(b["price"]) for b in effort["buys"]
                       if b.get("tier") in set(t["from_tiers"])) for n, t in tiers.items()}
        trainer = doc["income_basis"]["cumulative_by_badge"]
        out, extra = {}, 0.0
        for leg in GATE_BADGES:
            opened = sorted((t["opens_leg"], n) for n, t in tiers.items() if t["opens_leg"] <= leg)
            latest = [n for o, n in opened if o == opened[-1][0]]
            if len(latest) != 1:
                raise MarketError("curve: leg %d opens %s together in data/bank.json effort_model; R2 counts one "
                                  "tier's hour" % (leg, latest))
            extra += int(produce[str(leg - 1)]) + hours * hour[latest[0]]
            out[leg] = (per * leg, int(trainer[str(leg)]), int(trainer[str(leg)]) + extra)
        return out
    except (KeyError, TypeError, ValueError, IndexError) as e:
        raise MarketError("curve: R2's terms cannot be read (data/markets.json curve_rule / income_basis, data/bank.json "
                          "effort_model): %r" % (e,))


def curve_lines(doc):
    """[(record, line)] the R2 numerator counts: the convenience lines of the critical path's priced records (every
    counter, a stall's gated lines; priced()). Power lines leave the curve (R2); a provision is never a rung."""
    return [(c, it) for c in priced(doc) for it in c["stock"] if it.get("strand") == "convenience"]


def line_leg(rec, it):
    """The leg a curve line is bought in: its record's badge (the hometown's 0 is spent in leg 1), or, for a stretch
    line, its affordable_by badge (decision B7, 'price as the gate')."""
    b = it["affordable_by"] if it.get("stretch") else rec.get("badge")
    return max(1, int(b))


def leg_shelf(lines, price_of):
    """{leg: what the curve counts of that leg's non-stretch lines, a pick-one group at its dearest}."""
    out, groups = {}, {}
    for rec, it in lines:
        if it.get("stretch"):
            continue
        leg = line_leg(rec, it)
        if it.get("group"):
            k = (leg, rec["id"], it["group"])
            groups[k] = max(groups.get(k, 0), price_of(rec, it))
        else:
            out[leg] = out.get(leg, 0) + price_of(rec, it)
    for (leg, _r, _g), p in groups.items():
        out[leg] = out.get(leg, 0) + p
    return out


def curve(doc, effort=None):
    """[(badge, cumulative ask, the ask with every stretch item due by then, cumulative earned, ratio)] on the
    critical path under ECONOMY_OVERHAUL.md section 7 R2: ask = the convenience lines (curve_lines, stretch aside, a
    group at its dearest) + the fight allowance; earned = r2_earned. A stretch item counts from its affordable_by
    badge: before that it is meant to be out of reach."""
    lines = curve_lines(doc)
    shelf = leg_shelf(lines, lambda _r, it: int(it["price"]))
    stretch = {}
    for rec, it in lines:
        if it.get("stretch"):
            stretch[line_leg(rec, it)] = stretch.get(line_leg(rec, it), 0) + int(it["price"])
    rows, cum, cum_s = [], 0, 0
    for b, (fights, _trainer, earned) in sorted(r2_earned(doc, effort).items()):
        cum += shelf.get(b, 0)
        cum_s += stretch.get(b, 0)
        rows.append((b, cum + fights, cum + cum_s + fights, earned, (cum + fights) / earned))
    return rows


# ---------------------------------------------------------------------------------------------------- the curve rule
# data/markets.json price_policies.curve_scale (unit CURVEPRICE, 2026-10-10): ECONOMY_OVERHAUL.md section 7 R2 holds
# every badge's (convenience + fights) / earned in the 0.65-0.70 band. The convenience lines keep their relative worth
# as `list_price` (the price each carried before R2) and the rule sets `price`: leg by leg, one scale on that leg's
# lines, the one that brings the cumulative ask to the band's midpoint of what the road has earned by that badge,
# given what the earlier legs actually cost after rounding. A stretch line takes the scale of its affordable_by leg.
CURVE_POLICY = "curve_scale"
BANK_DATA = ROOT / "data" / "bank.json"


def curve_policy(doc):
    return ((doc.get("price_policies") or {}).get(CURVE_POLICY)) or {}


def curve_band(doc):
    band = curve_policy(doc).get("band")
    if not (isinstance(band, list) and len(band) == 2 and all(isinstance(x, (int, float)) for x in band)
            and 0 < band[0] < band[1] < 1):
        raise MarketError("price_policies.curve_scale.band must be [low, high], 0 < low < high < 1 (R2's 0.65-0.70)")
    return float(band[0]), float(band[1])


def curve_prices(doc, effort=None):
    """({leg: scale}, {(record id, line id): price}) the curve rule gives every curve line carrying price_rule
    curve_scale. Each price is list_price x its leg's scale, rounded to the nearest multiple of round_to x count (at
    least one such multiple); the leg's scale is (midpoint x earned[leg] - fights[leg] - what legs before it cost at
    their rounded prices) / the leg's list shelf. MarketError if a leg's scale is not positive (the band is then
    unreachable at that badge from this shelf)."""
    lo, hi = curve_band(doc)
    mid = (lo + hi) / 2
    step = int(curve_policy(doc).get("round_to") or 0)
    if step <= 0:
        raise MarketError("price_policies.curve_scale.round_to must be a positive whole number")
    lines = [(r, it) for r, it in curve_lines(doc) if it.get("price_rule") == CURVE_POLICY]
    for r, it in lines:
        lp = it.get("list_price")
        if isinstance(lp, bool) or not isinstance(lp, int) or lp <= 0:
            raise MarketError("counter %s item %s: price_rule curve_scale needs a positive whole list_price"
                              % (r["id"], it["id"]))
    fixed = [(r, it) for r, it in curve_lines(doc) if it.get("price_rule") != CURVE_POLICY]
    list_shelf = leg_shelf(lines, lambda _r, it: it["list_price"])
    fixed_shelf = leg_shelf(fixed, lambda _r, it: int(it["price"]))
    earned = r2_earned(doc, effort)

    def rounded(it, s):
        unit = step * int(it.get("count") or 1)
        return max(unit, int(math.floor(it["list_price"] * s / unit + 0.5)) * unit)

    scales, prices, spent = {}, {}, 0
    for leg in GATE_BADGES:
        fights, _t, got = earned[leg]
        want = mid * got - fights - spent - fixed_shelf.get(leg, 0)
        base = list_shelf.get(leg, 0)
        if base:
            if want <= 0:
                raise MarketError("curve: leg %d: the legs before it and its fixed lines already ask %.0f of the "
                                  "midpoint's %.0f, so no positive scale reaches the band"
                                  % (leg, spent + fixed_shelf.get(leg, 0) + fights, mid * got))
            scales[leg] = want / base
            for r, it in lines:
                if line_leg(r, it) == leg and not it.get("stretch"):
                    prices[(r["id"], it["id"])] = rounded(it, scales[leg])
        leg_lines = [(r, it) for r, it in lines if line_leg(r, it) == leg and not it.get("stretch")]
        spent += leg_shelf(leg_lines, lambda r, it: prices[(r["id"], it["id"])]).get(leg, 0) + fixed_shelf.get(leg, 0)
    for r, it in lines:
        if it.get("stretch"):
            leg = line_leg(r, it)
            if leg not in scales:
                raise MarketError("counter %s item %s: a stretch line's affordable_by leg %d has no other curve line "
                                  "to take its scale from" % (r["id"], it["id"], leg))
            prices[(r["id"], it["id"])] = rounded(it, scales[leg])
    return scales, prices


def curve_policy_problems(doc, effort=None):
    out = []
    pol = curve_policy(doc)
    lines = curve_lines(doc)
    ruled = [(r, it) for r, it in lines if it.get("price_rule") == CURVE_POLICY]
    if not pol:
        return ["%d curve line(s) name price_rule curve_scale but data/markets.json has no price_policies.curve_scale"
                % len(ruled)] if ruled else []
    on_curve = {(r["id"], it["id"]) for r, it in lines}
    for c in doc["counters"] + list(doc.get("stalls") or []):
        for it in c.get("stock") or []:
            if it.get("price_rule") == CURVE_POLICY and (c["id"], it["id"]) not in on_curve:
                out.append("%s item %s: price_rule curve_scale off the curve (an off-path record, a provision or a "
                           "power line): the rule prices only the R2 numerator's lines" % (c["id"], it["id"]))
    for r, it in lines:
        if it.get("price_rule") != CURVE_POLICY:
            out.append("%s item %s: a critical-path convenience line without price_rule curve_scale (its price would "
                       "be hand-typed onto the curve)" % (r["id"], it["id"]))
    try:
        _scales, prices = curve_prices(doc, effort)
    except MarketError as e:
        return out + [str(e)]
    ceiling, ceiling_id = ball_ceiling(doc)
    for r, it in ruled:
        want = prices[(r["id"], it["id"])]
        if it.get("price") != want:
            out.append("%s item %s: price %r is not the curve rule's $%d (list $%d; run tools/markets.py prices "
                       "--write)" % (r["id"], it["id"], it.get("price"), want, it["list_price"]))
        if ceiling is not None and want / (it.get("count") or 1) >= ceiling:
            out.append("%s item %s: the curve rule's $%d is not under %s's $%s, the ball floor (R4, the owner's): the "
                       "band is unreachable at badge %d without it" % (r["id"], it["id"], want, ceiling_id,
                                                                      money(ceiling), line_leg(r, it)))
    return out


def curve_problems(doc, effort=None):
    out = []
    try:
        lo, hi = curve_band(doc)
        rows = curve(doc, effort)
        earned = r2_earned(doc, effort)
    except MarketError as e:
        return [str(e)]
    for b, ask, ask_s, got, ratio in rows:
        if not lo <= round(ratio, 2) <= hi:
            out.append("badge %d: the critical path asks $%s (convenience + fights) of $%s earned, %.3f, outside "
                       "%.2f-%.2f (ECONOMY_OVERHAUL R2)" % (b, money(ask), money(got), ratio, lo, hi))
        if ask_s >= got:
            out.append("badge %d: with the stretch items due by then the critical path asks $%s, not below the $%s "
                       "earned" % (b, money(ask_s), money(got)))
        fights, trainer, _g = earned[b]
        if fights > trainer:
            out.append("badge %d: the fight allowance $%s is more than trainer income $%s (R2's hard check)"
                       % (b, money(fights), money(trainer)))
    for c in doc["counters"] + list(doc.get("stalls") or []):
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


def keepers(doc, plazas):
    """[(label, record, at, yaw, source, rule)] for every keeper built: rule 'frontage' (beside its Mart, facing its
    plaza: R17M's original claim) for a counter at its own site with a clerk; 'stall' for a stall keeper, and for a
    counter seated at a stall by the contract or standing at its square's stall with no clerk (Redbrow)."""
    out = []
    for c in emitted(doc):
        at, yaw, src = position(c, plazas)
        rule = "stall" if src == "contract" or (c.get("stall") and not c.get("near_trader")) else "frontage"
        out.append(("counter %s" % c["id"], c, at, yaw, src, rule))
    for s in emitted_stalls(doc):
        at, yaw, src = position(s, plazas)
        out.append(("stall %s" % s["id"], s, at, yaw, src, "stall"))
    return out


def donor_footprints(settlement, placements):
    """{placement id: (x0, z0, x1, z1)} of every building placed in a town with no plan (a donor town: Pallet), from
    its template's size, rotation and placer (place_donor.footprint: a pack donor turns about its position); and the
    ids whose size could not be read."""
    import place_donor as PD
    import town_character as TC
    templates = TC.Templates(TC.default_pack_dir(), TC.default_vanilla_jar())
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


def earthwork_blocks(placements, settlement, positions):
    """{(x, y, z): block} that the settlement's earthworks leave at the given positions, replaying their fill and
    setblock commands in order (air removes). A `fill ... replace <filter>` or `keep` is applied as written for the
    filters it can read and conservatively (as placed) otherwise: an over-report is a refusal, never a pass."""
    want = set(positions)
    got = {}
    for q in placements["placements"]:
        if q.get("settlement") != settlement or q.get("kind") != "earthwork":
            continue
        for cmd in q.get("commands") or []:
            t = cmd.split()
            try:
                if t and t[0] == "fill" and len(t) >= 8:
                    a = [int(v) for v in t[1:7]]
                    lo, hi = [min(a[i], a[i + 3]) for i in range(3)], [max(a[i], a[i + 3]) for i in range(3)]
                    hit = [p for p in want if all(lo[i] <= p[i] <= hi[i] for i in range(3))]
                    block, mode = t[7], t[8:]
                elif t and t[0] == "setblock" and len(t) >= 5:
                    p = tuple(int(v) for v in t[1:4])
                    hit, block, mode = ([p] if p in want else []), t[4], t[5:]
                else:
                    continue
            except ValueError:
                continue
            for p in hit:
                cur = got.get(p, "minecraft:air")
                if mode[:1] == ["keep"] and not cur.startswith("minecraft:air"):
                    continue
                if mode[:1] == ["replace"] and len(mode) > 1 and not mode[1].startswith("#") \
                        and cur.split("[")[0] != mode[1].split("[")[0]:
                    continue
                got[p] = block
    return {p: b for p, b in got.items() if not b.split("[")[0].endswith(":air")}


def contract_face(st, x, z):
    """The cell a keeper the squares' contract seats at (x, z) looks at: its customers', one step along the stall's
    `facing`. Since 2026-10-04 the keeper stands in front of the tent's table on the open side (plaza_centre.py, the
    owner: "the stalls all block the villager from access") and faces out, away from `at`; before then it stood behind
    a counter and faced `at`, which was the same direction."""
    d = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}.get((st or {}).get("facing"))
    return (x + d[0], z + d[1]) if d else None


def facing_yaw(x, z, tx, tz):
    """The Minecraft yaw from the cell (x, z) to the cell (tx, tz): 0 south, 90 west, -90 east, 180 north."""
    return math.degrees(math.atan2(-(tx - x), tz - z))


def deck_problems(where, x, y, z, yaw, s, plan, placements, world, face=None):
    """A keeper on a sea town's decks (data/placements.json `ground: sea_deck`): the town is one earthwork, so a plan
    Site would call every deck cell taken. On a deck cell with its four neighbours (tools/sea_town.py deck_ground),
    standing one above the deck, nothing the earthworks build in its two blocks or its neighbours', on the town's
    square and facing its centre -- or, for a keeper the squares' contract seats at a stall (`face`, its customers'
    cell, contract_face), facing its customers, as every contract keeper does."""
    import sea_town as ST
    out = []
    level, deck = ST.deck_ground(world)
    if y != level + 1:
        out.append("%s: stands at y%d, but the deck is y%d" % (where, y, level))
    cells = [(x + dx, z + dz) for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))]
    for c in cells:
        if c not in deck:
            out.append("%s: the cell %s is not a deck cell" % (where, c))
    occ = earthwork_blocks(placements, s, [(cx, y + h, cz) for cx, cz in cells for h in (0, 1)])
    for p, b in sorted(occ.items()):
        out.append("%s: %s stands at %s" % (where, b, p))
    pz = (plan.get("plaza") or {}).get("rect")
    if not pz or not in_rect(pz, x, z):
        out.append("%s: not on its town's square %s" % (where, pz))
    elif face is not None:
        want = facing_yaw(x, z, face[0], face[1])
        if abs((yaw - want + 180) % 360 - 180) > YAW_SLACK:
            # the wording is tests/test_town_traders_build.py's; `face` is the customers' cell since 2026-10-04
            out.append("%s: faces yaw %s, but its stall at %s is at yaw %.0f" % (where, yaw, list(face), want))
    elif abs((yaw - plaza_yaw(plan, x, z) + 180) % 360 - 180) > YAW_SLACK:
        out.append("%s: faces yaw %s, but its square's centre is at yaw %.0f" % (where, yaw, plaza_yaw(plan, x, z)))
    return out


def site_problems(doc, traders, source_root=None, skip_dressing=False, plazas=None):
    import ambient as A
    import ground as G
    import npc_seats as NS_
    plazas = load_plazas() if plazas is None else plazas
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
    built = keepers(doc, plazas)
    sites = {}
    for label, c, at, yaw, src, rule in built:
        where = "%s at %s" % (label, at)
        x, y, z = at
        s = c["town"]
        plan = (placements["settlements"].get(s) or {}).get("plan") or {}
        if not plan:
            # a donor town (Pallet): no plan, so no Site model; ground from the heightmap, rounded (CLAUDE.md "Ground
            # comes from the heightmap"), and the cell outside every placed building's footprint
            want_y = int(round(base(x, z))) + 1
            if y != want_y:
                out.append("%s: stands at y%d, but the heightmap's ground there puts it at y%d" % (where, y, want_y))
            fps, unknown = donor_footprints(s, placements)
            if unknown:
                out.append("%s: buildings whose size cannot be read: %s" % (where, unknown[:6]))
            for pid, (x0, z0, x1, z1) in sorted(fps.items()):
                if x0 - 1 <= x <= x1 + 1 and z0 - 1 <= z <= z1 + 1:
                    out.append("%s: inside building %s or its 1-block margin" % (where, pid))
            site, rule = None, "donor"
        elif (placements["settlements"].get(s) or {}).get("ground") == "sea_deck":
            # Pacifidlog. NOT the frontage rule: besides the earthwork, data/towns.json's sea_town footprint (x7020-7280,
            # z6704-7238) is the pre-resite site, 2,000 blocks from the plan's (centre 5160, 7380), so a footprint
            # check would refuse every cell of the built town (reported 2026-10-03; towns.json is not this tool's)
            a = plazas[c["stall"]].get("at") if src == "contract" else None
            face = contract_face(plazas[c["stall"]], x, z) if isinstance(a, list) and len(a) == 3 else None
            out += deck_problems(where, x, y, z, yaw, s, plan, placements, world, face=face)
            if face is not None and math.dist((x, z), (a[0], a[2])) > STALL_REACH:
                out.append("%s: %.1f blocks from its stall at %s" % (where, math.dist((x, z), (a[0], a[2])), a))
            rule = "deck"
        else:
            if s not in sites:
                try:
                    sites[s] = A.Site(s, base, placements, dressing, None, dict(rules, avoid_plaza_pieces=False))  # a stall stands on its piece
                except SystemExit as e:  # town_dressing.town_plan exits when derived/towns/<s>_plan.json is missing
                    sites[s] = e
            site = sites[s]
            if isinstance(site, SystemExit):
                out.append("%s: the town's site model cannot be built: %s" % (where, str(site)[:200]))
                continue
            want_y = stand_y(site, plan, x, z)
            if y != want_y:
                out.append("%s: stands at y%d, but the plan's ground there puts it at y%d" % (where, y, want_y))
            if rule == "frontage":
                out += frontage_problems(where, dict(c, at=at, yaw=yaw), plan, towns.get(s), site)
            elif src == "contract":
                a = plazas[c["stall"]].get("at")
                if isinstance(a, list) and len(a) == 3 and math.dist((x, z), (a[0], a[2])) > STALL_REACH:
                    out.append("%s: %.1f blocks from its stall at %s" % (where, math.dist((x, z), (a[0], a[2])), a))
                face = contract_face(plazas[c["stall"]], x, z)
                if face is not None:
                    want = facing_yaw(x, z, face[0], face[1])
                    if abs((yaw - want + 180) % 360 - 180) > YAW_SLACK:
                        out.append("%s: faces yaw %s, but its stall's customers at %s are at yaw %.0f"
                                   % (where, yaw, list(face), want))
            else:
                # a fallback stall site: on the square itself, turned to its centre (where the stall will stand)
                pz = (plan.get("plaza") or {}).get("rect")
                if not pz or not in_rect(pz, x, z):
                    out.append("%s: a stall keeper off its town's plaza %s" % (where, pz))
                elif abs((yaw - plaza_yaw(plan, x, z) + 180) % 360 - 180) > YAW_SLACK:
                    out.append("%s: faces yaw %s, but its plaza's centre is at yaw %.0f" % (where, yaw, plaza_yaw(plan, x, z)))
            for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                why = site.blocked(x + dx, z + dz)
                if why:
                    out.append("%s: the cell (%d, %d) is taken by %s" % (where, x + dx, z + dz, why))
        # below the sea level on the surface is under water; a settlement on a cavern's floor (the Displaced City,
        # tools/ground.py GROUND_KINDS) is below it by design and dry, its air the cavern plan's, so the rule is the
        # surface's only (2026-10-05: the summit square is at y46 against the sea's y62)
        if y - 1 < sea and (placements["settlements"].get(s) or {}).get("ground") != "cavern_floor":
            out.append("%s: its ground y%d is under the sea level y%d" % (where, y - 1, sea))
        for what, q in others + [(o[0], tuple(o[2])) for o in built if o[1] is not c]:
            if math.dist((x, y, z), q) < NPC_CLEAR:
                out.append("%s: %.1f blocks from %s at %s" % (where, math.dist((x, y, z), q), what, q))
        if len(route):
            d = float(min(((route[:, 0] - x) ** 2 + (route[:, 1] - z) ** 2) ** 0.5))
            if d < ROUTE_CLEAR:
                out.append("%s: %.1f blocks from a walked route line" % (where, d))
        tr = traders.get(c.get("near_trader") or "", {}).get("position")
        report.append("%s: ground y%d, %s rule, from the %s%s" % (
            where, y - 1, rule, src, "" if not tr else ", %.0f blocks from its clerk" % math.dist((x, z), (tr["x"], tr["z"]))))
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


def output_problems(doc, files, plazas=None):
    """The pack as emitted: since 2026-10-06 no counter has a purchase function or a charge macro (markets/ holds only
    load), and merchant_problems holds every seller to its merchant (no dialogue or NPC class anywhere in the pack);
    every function passes tools/function_limits.py."""
    out = []
    for k in files:
        if k.startswith("data/%s/function/markets/" % NS) and k != "data/%s/function/markets/load.mcfunction" % NS:
            out.append("%s: a counter's purchase function or charge macro is emitted (every counter is a merchant "
                       "since 2026-10-06)" % k)
    for rel, body in files.items():
        if rel.endswith(".mcfunction"):
            refused = function_limits.check_lines(body, rel)
            if refused:
                out.append("%s: %d command(s) the server would refuse" % (rel, len(refused)))
    return out + merchant_problems(doc, files, plazas)


def merchant_problems(doc, files, plazas=None):
    """The merchants as emitted (every sited counter's and stall's), read back from the generated text and held to the
    data: one summon per seller, of the merchant entity, with its keeper's name, the four flags and the profession; a
    single category named by its `category`; exactly its stock lines in order, each Item count 1 at a price that
    times the line's count is the line's price; the dialogue keeper it replaces removed by its seat in _clear, which
    _place runs before its summons; no dialogue, NPC class or purchase function left for a seller (nothing charges
    twice). With `plazas`, also each summon's block and rotation against the seat."""
    out = []
    cfg = merchant_cfg(doc)
    kind, radius = cfg["kind"], float(cfg["remove_radius"])
    mdir = "data/%s/function/%s/" % (NS, MERCHANTS_DIR)
    mfiles = {k: v for k, v in files.items() if k.startswith(mdir)}
    for k in files:
        if (k.startswith("data/%s/function/stalls/" % NS) and not k.startswith(mdir)) or \
                re.match(r"data/%s/(dialogues|npcs)/" % NS, k):
            out.append("%s: a seller's dialogue, NPC class or purchase function is emitted beside its merchant" % k)
    for k, body in mfiles.items():
        if any(re.search(r"(?:^|\brun )(?:cobbledollars|give|function \S+markets/(?:charge|refund)) ", x)
               for x in body if not x.startswith("#")):
            out.append("%s: a merchant function charges or gives (the merchant's screen does both)" % k)
    summons = [x for body in mfiles.values() for x in body if x.startswith("summon ")]
    seats = {}
    if plazas is not None:
        for s, _kind in merchant_records(doc):
            at, yaw, _src = position(s, plazas)
            seats[s["id"]] = (tuple(int(v) for v in at), yaw)
    all_fn = mfiles.get(mdir + "all.mcfunction") or []
    for s, skind in merchant_records(doc):
        w = "%s %s merchant" % (skind, s["id"])
        tag = '"%s_%s"' % (cfg["tag"], s["id"])
        mine = [x for x in summons if tag in x]
        if len(mine) != 1:
            out.append("%s: %d summons carry its tag, not 1" % (w, len(mine)))
            continue
        line = mine[0]
        parts = line.split(" ", 5)
        if parts[1] != kind:
            out.append("%s: summons %s, not %s" % (w, parts[1], kind))
        for flag in ("NoAI:1b", "PersistenceRequired:1b", "Invulnerable:1b", "Silent:1b"):
            if flag not in line:
                out.append("%s: no %s" % (w, flag))
        if 'profession:"%s"' % cfg["villager_data"]["profession"] not in line or "level:99" not in line:
            out.append("%s: not a level-99 %s" % (w, cfg["villager_data"]["profession"]))
        if '\\"%s\\"' % s["keeper"]["name"] not in line:
            out.append("%s: not named %r" % (w, s["keeper"]["name"]))
        cats = re.findall(r'Category:"([^"]*)"', line)
        if cats != [s.get("category")]:
            out.append("%s: categories %s, not [%r]" % (w, cats, s.get("category")))
        got = shop_offers(line)
        want = [(it["item"], it["price"], it["count"]) for it in s["stock"]]
        if [g[0] for g in got] != [x[0] for x in want]:
            out.append("%s: offers %s, the %s's lines %s" % (w, [g[0] for g in got], skind, [x[0] for x in want]))
        else:
            for (iid, p), (_i, price, cnt) in zip(got, want):
                if not p.isdigit() or int(p) * cnt != price:
                    out.append("%s: %s at %r each, but the line is %d for $%d" % (w, iid, p, cnt, price))
        counts = re.findall(r"Item:\{count:(\d+)", line)
        if counts != ["1"] * len(s["stock"]):
            out.append("%s: Item counts %s, not 1 each" % (w, counts))
        town_fn = "function %s:%s/%s" % (NS, MERCHANTS_DIR, s["town"])
        if town_fn not in all_fn:
            out.append("%s: %s/all does not start %s" % (w, MERCHANTS_DIR, s["town"]))
        x, y, z = (int(float(v)) for v in parts[2:5])
        # the dialogue keeper it replaces: killed by its seat in <town>_clear, which <town>_place runs before any
        # summon (2026-10-06); _done kills only older copies of the merchant, where the new one stands
        place = mfiles.get(mdir + "%s_place.mcfunction" % s["town"]) or []
        clear = mfiles.get(mdir + "%s_clear.mcfunction" % s["town"]) or []
        done = mfiles.get(mdir + "%s_done.mcfunction" % s["town"]) or []
        npc_kill = "kill @e[type=cobblemon:npc,x=%d.5,y=%d,z=%d.5,distance=..%s]" % (x, y, z, radius)
        if npc_kill not in clear:
            out.append("%s: its town's _clear does not remove the dialogue keeper at its seat" % w)
        call = "function %s:%s/%s_clear" % (NS, MERCHANTS_DIR, s["town"])
        first = [i for i, q in enumerate(place) if q.startswith("summon ")]
        if call not in place or (first and place.index(call) > first[0]):
            out.append("%s: its town's _place does not run _clear before its summons" % w)
        if any("cobblemon:npc" in d for d in done if not d.startswith("#")):
            out.append("%s: its town's _done kills a Cobblemon NPC (the removal is _clear's, before the summons)" % w)
        if any(q.startswith("kill ") and not q.startswith("kill @e[type=cobblemon:npc,") for q in clear):
            out.append("%s: its town's _clear kills something other than a Cobblemon NPC" % w)
        if s["id"] in seats:
            (sx, sy, sz), yaw = seats[s["id"]]
            if (x, y, z) != (sx, sy, sz) or parts[2:5] != ["%d.5" % sx, str(sy), "%d.5" % sz]:
                out.append("%s: summoned at %s, its seat is %s" % (w, parts[2:5], [sx, sy, sz]))
            rot = re.search(r"Rotation:\[(-?[0-9.]+)f,", line)
            if not rot or abs(float(rot.group(1)) - float(yaw)) > 1e-6:
                out.append("%s: rotation %s, the seat's yaw %s" % (w, rot and rot.group(1), yaw))
    return out


def collision_problems(doc):
    """No counter and stall share an id: each names its merchant's tag (<stall_merchant.tag>_<id>), and two records with
    one tag would be summoned, de-duplicated and verified as one."""
    out = []
    seen = {}
    for kind, recs in (("counter", doc["counters"]), ("stall", doc.get("stalls") or [])):
        for c in recs:
            if c.get("id") in seen:
                out.append("%s %s shares its id (its merchant's tag) with %s %s" % (kind, c["id"], seen[c["id"]], c["id"]))
            seen[c.get("id")] = kind
    return out


def audit(doc, source_root=None, skip_dressing=False, plazas=None):
    import progression_pack as PP
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    planned = {f["id"] for f in PP.plan(prog, placements=placements)["flags"]}
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    traders = {t["id"]: t for t in json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))["traders"]}
    plazas = load_plazas() if plazas is None else plazas
    problems = static_problems(doc, planned, towns, traders) + stall_problems(doc, towns, plazas) + \
        collision_problems(doc) + price_policy_problems(doc, prog) + curve_policy_problems(doc)
    if problems:
        return problems, contract_report(doc, plazas)
    problems += curve_problems(doc) + overlay_problems(doc)
    files, _ = build(doc, plazas)
    problems += output_problems(doc, files, plazas)
    p, report = site_problems(doc, traders, source_root, skip_dressing, plazas)
    return problems + p, contract_report(doc, plazas) + report


# ---------------------------------------------------------------------------------------------------- the jars
def jar_items(jar_dir):
    """{item id} from every jar's lang files (item.<ns>.<path> and block.<ns>.<path> keys) and item models
    (assets/<ns>/models/item/<path>.json). Read only. The models count since 2026-10-08: TMCraft's per-move TMs
    (tmcraft:tm_<move>) have an item model and no lang key, the shape tools/economy_audit.py already accepts."""
    return jar_items_of(sorted(Path(jar_dir).glob("*.jar")))


def jar_items_of(jars):
    ids = set()
    for jp in jars:
        with zipfile.ZipFile(jp) as z:
            for n in z.namelist():
                m = re.fullmatch(r"assets/([a-z0-9_.\-]+)/models/item/([a-z0-9_/.\-]+)\.json", n)
                if m:
                    ids.add("%s:%s" % m.groups())
                    continue
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
    j.add_argument("--jar", action="append", default=[],
                   help="a further jar to read (repeatable): the Minecraft 1.21.1 jar for the stalls' minecraft: ids; "
                        "without one, every minecraft: id is reported NOT CHECKED")
    sub.add_parser("report")
    pr = sub.add_parser("prices", help="the price rules' price per line (price_policies.income_gate and curve_scale)")
    pr.add_argument("--write", action="store_true", help="write the rule's prices into the data file")
    args = p.parse_args(argv)
    doc = load(args.data)
    if args.cmd == "prices":
        inc = doc["income_basis"]["cumulative_by_badge"]
        ceiling, ceiling_id = ball_ceiling(doc)
        for c, it, held, price, n in price_table(doc):
            print("%-18s %-22s gate badge %d (income $%s)  $%s%s  %s" % (
                c["id"], it["id"], it["gate_badge"], money(inc[str(it["gate_badge"])]), money(price),
                " = %d x %s" % (n, it["exchange_for"]["item"]) if n is not None else "",
                "HELD (%s)" % (it.get("held") or {}).get("reason") if held else "stock"))
        print("ball ceiling: %s at $%s" % (ceiling_id, money(ceiling) if ceiling is not None else "?"))
        if curve_policy(doc):
            scales, cp = curve_prices(doc)
            print("curve rule (price_policies.curve_scale), scale by leg: %s"
                  % " ".join("%d:%.3f" % kv for kv in sorted(scales.items())))
            for c, it in curve_lines(doc):
                if it.get("price_rule") == CURVE_POLICY:
                    print("%-18s %-28s leg %d  list $%s -> $%s%s" % (
                        c["id"], it["id"], line_leg(c, it), money(it["list_price"]), money(cp[(c["id"], it["id"])]),
                        "  (stretch)" if it.get("stretch") else ""))
        if args.write:
            print("wrote %d line(s) in %s" % (write_prices(args.data, doc), args.data))
        return 0
    if args.cmd == "build":
        files, npcs = build(doc)
        write(files, args.out)
        print("wrote %d files to %s: %d counters built of %d, %d stalls built of %d, %d merchant summons, %d dialogue "
              "keepers" % (len(files), args.out, len(emitted(doc)), len(doc["counters"]), len(emitted_stalls(doc)),
                           len(doc.get("stalls") or []),
                           sum(1 for body in files.values() if isinstance(body, list) for x in body if x.startswith("summon ")),
                           len(npcs)))
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
        for jp in args.jar:
            have |= jar_items_of([Path(jp)])
        sold = sorted({it["item"] for c in doc["counters"] + list(doc.get("stalls") or []) for it in c["stock"]})
        vanilla_read = any(i.startswith("minecraft:") for i in have)
        unchecked = [i for i in sold if i.startswith("minecraft:") and not vanilla_read]
        missing = [i for i in sold if i not in have and i not in unchecked]
        for i in unchecked:
            print("NOT CHECKED %s: no Minecraft jar given (--jar)" % i)
        for i in missing:
            print("PROBLEM %s is not an item in any jar read" % i)
        print("ids: %d sold, %d found, %d missing, %d not checked"
              % (len(sold), len(sold) - len(missing) - len(unchecked), len(missing), len(unchecked)))
        return 1 if missing else 0
    if args.cmd == "report":
        for bdg, ask, ask_s, inc, ratio in curve(doc):
            print("badge %d: ask $%s (with stretch $%s) of $%s earned: %.2f" % (bdg, money(ask), money(ask_s), money(inc), ratio))
        for c in doc["counters"]:
            if c.get("path") == "off_path":
                print("off path %s (%s, %s): $%s" % (c["id"], c["town"], c["status"], money(sum(it["price"] for it in c["stock"]))))
        for s in doc.get("stalls") or []:
            gated = sum(it["price"] for it in s["stock"] if it.get("gate"))
            print("stall %s (%s, %s, %s): $%s of provisions, $%s gated%s" % (
                s["id"], s["town"], s["path"], s["status"],
                money(sum(it["price"] for it in s["stock"] if it.get("strand") == "provision")), money(gated),
                " (on the curve)" if gated and s["path"] == "critical" else ""))
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
