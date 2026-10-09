"""Direct trades: a vanilla villager with fixed item-for-item offers (data/direct_trades.json, EXP-055).

The owner, 2026-10-07: late-game items by direct trade, no money where possible. CobbleDollars cannot barter (an
Offer holds item, price and stock only: docs/OVERNIGHT_REVIEW_2026-10-06.md N63), so this writes a world-local pack,
cobblers_direct_trades, with two villagers, each with its Offers written into its summon. Run by tools/reapply.py
step R18DT, both at once, each as tools/chunk_look.py's look-then-act chain (N155: a force-loaded chunk's saved
entities arrive after a summon is accepted, so a fixed wait let the de-duplication miss an old villager and the summon
doubled it): the chain force-loads its box, does its block checks and its kill and summon only once the barterer's
saved copy is seen there (or blind after 300 ticks), de-duplicates 100 ticks later, counts into
#direct_trades_<place|counter> cobblers_chunk_look and releases the box:

  place     EXP-055's experiment villager: carves a small buried booth under the Holdfast counter and summons the
            experiment offers there (the data's `site` and `barterer`).
  counter   the barterer players use (the owner, 2026-10-08: "Players trade at Northlight's counter"): inside the
            Northlight Mart beside the counter, summoned with every approved line (`counter_site`, `counter_barterer`).
            Its spot is checked against the Mart's template, turned by its placement and seated on its clerk record's
            floor, never a world: every column within lightning reach must hold a roof block far enough above the
            villager (the booth's lightning rule, applied to a roof).

What is placed: the experiment offers at Holdfast, and the barter lines whose `approved` is true at Northlight. A line
with `approved: false` is built into nothing: it appears in `edges` for the economy audit and in no function. Every
offer carries the data's fixed_trade fields; the fields and why they hold a price still are cited in
experiments/EXP-055-direct-trade-villager/README.md. An approved line is refused unless its inputs, valued by the
data's `pricing.values` (each checked against the Bank file and data/markets.json), lie within `pricing.band` of its
reference price on the counter (the owner, 2026-10-08: an alternative path, not a bypass).

What this does NOT cover: any other villager in the world (vanilla-generated ones keep vanilla trades), and the
CobbleDollars merchants (data/markets.json), which price in money. The Mart's roof is checked as the template and the
place function's read-back of it; a block somebody adds above the roof only raises the strike point.

    python tools/direct_trades.py build     # writes build/datapacks/cobblers_direct_trades
    python tools/direct_trades.py plan      # the booth, the offers placed and held, the step
    python tools/direct_trades.py edges     # every item-for-item edge, held lines included, as JSON
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import chunk_look as CL  # noqa: E402
import function_limits  # noqa: E402

DATA = ROOT / "data" / "direct_trades.json"
BANK = ROOT / "modpack" / "config" / "cobbledollars" / "bank.json"   # tools/bank.py's output, what the server reads
MARKETS = ROOT / "data" / "markets.json"
PLACEMENTS = ROOT / "data" / "placements.json"
TRADERS = ROOT / "data" / "traders.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_direct_trades"
PACK_FORMAT = 48  # Minecraft 1.21.1
KIND = "minecraft:villager"
STEP = "R18DT"
OBJECTIVE = "cob_dt"
BREACH_TAG = "direct_trades_breach"
# the Offers.Recipes keys of vanilla 1.21.1's MerchantOffer codec, in its own order (EXP-055 'Fields': read from the
# 1.21.1 client jar's string constants). A key outside this set is refused rather than written.
RECIPE_KEYS = ("buy", "buyB", "sell", "uses", "maxUses", "rewardExp", "specialPrice", "demand", "priceMultiplier", "xp")
FIXED_KEYS = ("uses", "maxUses", "rewardExp", "specialPrice", "demand", "priceMultiplier", "xp")
LINE_STATUSES = ("proposal", "approved", "retired")
# a bolt reaches 3 blocks under its strike point, which is the top of the highest block (EXP-055 'Lightning'); the
# villager is 1.95 tall. So its feet must be at least this far under the lowest ground within LIGHTNING_REACH
LIGHTNING_CLEARANCE = 4
LIGHTNING_REACH = 4
AIR = ("minecraft:air", "minecraft:structure_void", "minecraft:cave_air")
COUNTER_BREACH = "#counter_breach"


class DirectTradeError(ValueError):
    pass


def load(path=None):
    return json.loads(Path(path or DATA).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------------------ offers
def _cost(c):
    return {"id": c["id"], "count": int(c["count"])}


def recipe(offer, fixed):
    """The Offers.Recipes entry for an offer: its costs and result, then every fixed-trade field (the offer's own
    `overrides` win, for the experiment's control). Keys in the codec's order; buyB only when the offer has one."""
    r = {"buy": _cost(offer["buy"])}
    if offer.get("buyB"):
        r["buyB"] = _cost(offer["buyB"])
    r["sell"] = _cost(offer["sell"])
    over = offer.get("overrides") or {}
    for k in FIXED_KEYS:
        v = over.get(k, fixed[k])
        r[k] = float(v) if k == "priceMultiplier" else (bool(v) if k == "rewardExp" else int(v))
    return r


def placed_lines(doc):
    """The barter lines that go into the villager: approved ones only."""
    return [ln for ln in doc["lines"] if ln.get("approved") is True]


def held_lines(doc):
    return [ln for ln in doc["lines"] if ln.get("approved") is not True]


def placed_offers(doc):
    return list(doc["experiment_offers"]) + placed_lines(doc)


def recipes(doc):
    return [recipe(o, doc["fixed_trade"]) for o in placed_offers(doc)]


def _experiment_ids(doc):
    return {o["id"] for o in doc["experiment_offers"]}


def experiment_recipes(doc):
    """The Holdfast villager's: the placed offers that are experiment offers."""
    ids = _experiment_ids(doc)
    return [recipe(o, doc["fixed_trade"]) for o in placed_offers(doc) if o["id"] in ids]


def counter_recipes(doc):
    """The Northlight barterer's: every other placed offer (the approved lines)."""
    ids = _experiment_ids(doc)
    return [recipe(o, doc["fixed_trade"]) for o in placed_offers(doc) if o["id"] not in ids]


def edges(doc):
    """Every item-for-item edge the data authors, placed or held: what the economy audit checks for loops."""
    out = []
    for kind, offers in (("experiment", doc["experiment_offers"]), ("line", doc["lines"])):
        for o in offers:
            ins = [_cost(o["buy"])] + ([_cost(o["buyB"])] if o.get("buyB") else [])
            out.append({"id": o["id"], "kind": kind,
                        "placed": kind == "experiment" or o.get("approved") is True,
                        "status": o.get("status", "experiment"),
                        "inputs": ins, "output": _cost(o["sell"])})
    return out


# ------------------------------------------------------------------------------------------------------------ checks
def check(doc):
    """Problems with the data, each a sentence. Empty means the pack may be written."""
    p = []
    ft = doc.get("fixed_trade") or {}
    for k in FIXED_KEYS:
        if k not in ft:
            p.append("fixed_trade has no %s: every fixed field is written explicitly, no default is relied on" % k)
    if p:
        return p
    if float(ft["priceMultiplier"]) != 0.0:
        p.append("fixed_trade.priceMultiplier is %s, not 0: demand and reputation would move the price"
                 % ft["priceMultiplier"])
    if int(ft["xp"]) != 0:
        p.append("fixed_trade.xp is %s, not 0: trades would raise the villager's experience" % ft["xp"])
    if int(ft["uses"]) != 0 or int(ft["demand"]) != 0 or int(ft["specialPrice"]) != 0:
        p.append("fixed_trade uses, demand and specialPrice must start at 0")
    if int(ft["maxUses"]) < 1000:
        p.append("fixed_trade.maxUses %s is a stock one player can empty for everyone" % ft["maxUses"])
    for key in ("barterer", "counter_barterer"):
        b = doc[key]
        if b["profession"] in ("minecraft:none", "minecraft:nitwit"):
            p.append("the %s's profession %s has no trades table" % (key, b["profession"]))
        if int(b["level"]) != 5:
            p.append("the %s's level %s is not 5: a level-up would add vanilla trades" % (key, b["level"]))
    if doc["barterer"]["tag"] == doc["counter_barterer"]["tag"]:
        p.append("the two barterers share tag %s: each one's de-duplication would kill the other"
                 % doc["barterer"]["tag"])
    ids = set()
    lines = doc.get("lines") or []
    if len(lines) > int(doc["rules"]["max_lines"]):
        p.append("%d barter lines, over the short list's %s" % (len(lines), doc["rules"]["max_lines"]))
    for o in list(doc["experiment_offers"]) + lines:
        oid = o.get("id")
        if oid in ids:
            p.append("offer id %s is authored twice" % oid)
        ids.add(oid)
        for slot in ("buy", "buyB", "sell"):
            c = o.get(slot)
            if c is None:
                if slot != "buyB":
                    p.append("%s has no %s" % (oid, slot))
                continue
            if ":" not in str(c.get("id", "")):
                p.append("%s %s id %r is not namespaced" % (oid, slot, c.get("id")))
            if not 1 <= int(c.get("count", 0)) <= 64:
                p.append("%s %s count %s is outside 1-64" % (oid, slot, c.get("count")))
        if o.get("buyB") and o["buyB"]["id"] == o["buy"]["id"]:
            p.append("%s pays %s in both slots: the trade screen's auto-fill leaves the second empty"
                     % (oid, o["buy"]["id"]))
        for k in (o.get("overrides") or {}):
            if k not in FIXED_KEYS:
                p.append("%s overrides %s, which is not a fixed-trade field" % (oid, k))
    for o in doc["experiment_offers"]:
        if set(o.get("overrides") or {}) - {"priceMultiplier"}:
            p.append("%s: an experiment offer may override priceMultiplier only (the control)" % o["id"])
        # never a gain: the output is one of the offer's own inputs, at no more than the worst-case count paid of it
        # (cost A can be discounted to 1; cost B never is)
        s = o["sell"]
        paid = [1 if o["buy"]["id"] == s["id"] else 0,
                int(o["buyB"]["count"]) if o.get("buyB") and o["buyB"]["id"] == s["id"] else 0]
        if s["count"] > max(paid):
            p.append("%s can gain %s: its output is not covered by its own worst-case inputs" % (o["id"], s["id"]))
    for ln in lines:
        st = ln.get("status")
        if st not in LINE_STATUSES:
            p.append("line %s status %r is not one of %s" % (ln.get("id"), st, LINE_STATUSES))
        if (ln.get("approved") is True) != (st == "approved"):
            p.append("line %s: approved %r disagrees with status %r" % (ln.get("id"), ln.get("approved"), st))
        if int(ln["buy"]["count"]) != 1:
            p.append("line %s cost A count is %s, not 1: Hero of the Village would discount it"
                     % (ln["id"], ln["buy"]["count"]))
        if not ln.get("buyB"):
            p.append("line %s has no buyB: its bulk cost belongs there, where no discount reaches" % ln["id"])
        for k in ("late_game_why", "inputs_why"):
            if not ln.get(k):
                p.append("line %s has no %s" % (ln["id"], k))
        if ln.get("overrides"):
            p.append("line %s overrides the fixed-trade fields" % ln["id"])
    return p


# ------------------------------------------------------------------------------------------------------------ prices
def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def counter_prices(markets=None):
    """{(counter id, line id): price} of every counter line in data/markets.json."""
    m = markets if markets is not None else _read(MARKETS)
    return {(c["id"], s["id"]): int(s["price"]) for c in m.get("counters") or [] for s in c.get("stock") or []}


def bank_prices(bank=None):
    """{item: the higher price the Bank pays}, from tools/bank.py's committed output."""
    entries = (bank if bank is not None else _read(BANK))["bank"]
    out = {}
    for e in entries:
        out[e["item"]] = max(out.get(e["item"], 0), int(e["price"]))
    return out


def line_value(doc, ln):
    """What the player gives up for a line's inputs, from pricing.values: cost A at its count (1), cost B as
    authored. None for an input with no value."""
    vals = doc["pricing"]["values"]
    total = 0
    for slot in ("buy", "buyB"):
        c = ln.get(slot)
        if not c:
            continue
        v = vals.get(c["id"])
        if v is None:
            return None
        total += int(v["value"]) * int(c["count"])
    return total


def reference_price(ln, prices):
    ref = ln.get("reference") or {}
    try:
        return sum(prices[(ref["counter"], lid)] for lid in ref["lines"])
    except KeyError:
        return None


def pricing_problems(doc, markets=None, bank=None):
    """Each approved line's input value within pricing.band of its reference; every pricing.values entry agreeing
    with the file it names."""
    p = []
    pr = doc.get("pricing")
    if not pr:
        return ["no pricing block: an approved line cannot be held to the counter's price"]
    prices = counter_prices(markets)
    bp = bank_prices(bank)
    for item, v in sorted(pr["values"].items()):
        src = v.get("from")
        if src == "bank":
            want = bp.get(v["item"])
        elif src == "bank_block":
            want = 9 * bp[v["item"]] if v["item"] in bp else None
        elif src == "counter":
            want = prices.get((v.get("counter"), v.get("line")))
        else:
            p.append("pricing value %s has source %r, not bank, bank_block or counter" % (item, src))
            continue
        if want is None:
            p.append("pricing value %s: its source (%s %s) has no price" % (item, src, v.get("item") or v.get("line")))
        elif int(v["value"]) != want:
            p.append("pricing value %s is %s, its source (%s) says %s: stale" % (item, v["value"], src, want))
    lo, hi = float(pr["band"][0]), float(pr["band"][1])
    for ln in doc.get("lines") or []:
        if ln.get("approved") is not True:
            continue
        ref = reference_price(ln, prices)
        val = line_value(doc, ln)
        if ref is None:
            p.append("line %s: its reference %r names no counter price" % (ln["id"], ln.get("reference")))
        elif val is None:
            p.append("line %s: an input has no value in pricing.values" % ln["id"])
        elif not lo * ref <= val <= hi * ref:
            p.append("line %s: inputs worth $%d against a reference of $%d (%.2f, outside the band %s-%s)"
                     % (ln["id"], val, ref, val / ref, lo, hi))
    return p


# ------------------------------------------------------------------------------------------------------------ booth
def booth(doc, g):
    """The booth from the heightmap: the 5x5 shell's footprint centred on the site, feet `depth` under its lowest
    ground. Refuses a site where the feet are not LIGHTNING_CLEARANCE under the lowest ground within reach."""
    s = doc["site"]
    x, z, depth = int(s["x"]), int(s["z"]), int(s["depth_below_ground"])
    foot = g.box(x - 2, z - 2, x + 2, z + 2)
    reach = g.box(x - LIGHTNING_REACH, z - LIGHTNING_REACH, x + LIGHTNING_REACH, z + LIGHTNING_REACH)
    gmin, gmax, rmin = int(foot.min()), int(foot.max()), int(reach.min())
    feet = gmin - depth
    if feet > rmin - LIGHTNING_CLEARANCE:
        raise DirectTradeError("the booth's feet y%d are not %d under the lowest ground y%d within %d blocks"
                               % (feet, LIGHTNING_CLEARANCE, rmin, LIGHTNING_REACH))
    return {"villager": (x, feet, z),
            "shell": ((x - 2, feet - 1, z - 2), (x + 2, feet + 3, z + 2)),
            "interior": ((x - 1, feet, z - 1), (x + 1, feet + 2, z + 1)),
            "light": (x, feet + 3, z),
            "ground": {"footprint_min": gmin, "footprint_max": gmax, "reach_min": rmin,
                       "ground_at_site": int(g(x, z)), "rock_over_ceiling": gmin - (feet + 3)}}


# the Mart clerk's jigsaw name in the CobbleTowns templates (tools/sea_town.py CLERK_JIGSAW, which seats the clerk
# record one block above it)
CLERK_JIGSAW = "cobblemoncitytowns:shopkeeper_main"


def _placement(pid, placements=None):
    pl = placements if placements is not None else _read(PLACEMENTS)
    rows = pl["placements"] if isinstance(pl, dict) else pl
    hit = [p for p in rows if p.get("id") == pid]
    if len(hit) != 1:
        raise DirectTradeError("counter_site.building %s: %d placements carry that id, not 1" % (pid, len(hit)))
    return hit[0]


def _trader(tid, traders=None):
    tr = traders if traders is not None else _read(TRADERS)
    hit = [t for t in tr["traders"] if t.get("id") == tid]
    if len(hit) != 1:
        raise DirectTradeError("counter_site.clerk %s: %d trader records carry that id, not 1" % (tid, len(hit)))
    return hit[0]


def counter_spot(doc, placements=None, traders=None):
    """The Northlight barterer's spot from the plan: the building's template turned and placed as tools/place_town.py
    seats it, its floor from the clerk record (one above the clerk jigsaw, tools/sea_town.py clerk_record). Refuses a
    spot whose feet or head is not air, whose floor is not solid, or where any column within lightning_reach holds no
    template block lightning_clearance or more above the feet."""
    import nbt
    import place_town as PT
    s = doc["counter_site"]
    reach, clear = int(s["lightning_reach"]), int(s["lightning_clearance"])
    if reach < LIGHTNING_REACH or clear < LIGHTNING_CLEARANCE:
        raise DirectTradeError("counter_site reach %d / clearance %d are under the booth's %d / %d"
                               % (reach, clear, LIGHTNING_REACH, LIGHTNING_CLEARANCE))
    p = _placement(s["building"], placements)
    clerk = _trader(s["clerk"], traders)
    if clerk.get("building") != p["id"]:
        raise DirectTradeError("clerk %s stands in %s, not %s" % (clerk["id"], clerk.get("building"), p["id"]))
    path = ROOT / p["file"]
    info = PT.template_info(path)
    rot = PT.rotation_for(info["entrance"], p["facing"])
    if p.get("rotation") and p["rotation"] != rot:
        raise DirectTradeError("%s: rotation %s does not turn its %s entrance to face %s" % (p["id"], p["rotation"],
                                                                                             info["entrance"], p["facing"]))
    mnx, mnz, _w, _d = PT.footprint(info["size"], rot)
    px, pz = p["position"]["x"] - mnx, p["position"]["z"] - mnz
    _, tdoc = nbt.load(path)
    pal = tdoc["palette"]
    jig = None
    raw = []
    for blk in tdoc["blocks"]:
        name = pal[blk["state"]]["Name"]
        extra = blk.get("nbt") or {}
        if name == "minecraft:jigsaw":
            if extra.get("name") == CLERK_JIGSAW:
                jig = blk["pos"]
            name = (extra.get("final_state") or "minecraft:air").split("[")[0]   # place_town sets the final state
        raw.append((blk["pos"], name))
    if jig is None:
        raise DirectTradeError("%s holds no %s jigsaw: no clerk to seat the floor on" % (p["file"], CLERK_JIGSAW))
    cx, cz = PT.rotate(jig[0], jig[2], rot)
    if (px + cx, pz + cz) != (int(clerk["position"]["x"]), int(clerk["position"]["z"])):
        raise DirectTradeError("clerk %s at (%s, %s) is not over its template's jigsaw at (%d, %d)"
                               % (clerk["id"], clerk["position"]["x"], clerk["position"]["z"], px + cx, pz + cz))
    oy = int(clerk["position"]["y"]) - 1 - jig[1]
    cells, top = {}, {}
    for (tx, ty, tz), name in raw:
        rx, rz = PT.rotate(tx, tz, rot)
        w = (px + rx, oy + ty, pz + rz)
        cells[w] = name
        if name not in AIR:
            top[(w[0], w[2])] = max(top.get((w[0], w[2]), w[1]), w[1])
    x, z, feet = int(s["x"]), int(s["z"]), int(clerk["position"]["y"])
    for y, want in ((feet - 1, "solid"), (feet, "air"), (feet + 1, "air")):
        is_air = cells.get((x, y, z), "minecraft:air") in AIR
        if is_air != (want == "air"):
            raise DirectTradeError("the counter barterer's cell (%d, %d, %d) is not %s in %s" % (x, y, z, want, p["id"]))
    roof = []
    for zz in range(z - reach, z + reach + 1):
        for xx in range(x - reach, x + reach + 1):
            t = top.get((xx, zz))
            if t is None or t < feet + clear:
                raise DirectTradeError("column (%d, %d), within %d of the counter barterer, has %s: not %d above its "
                                       "feet y%d" % (xx, zz, reach, "no roof" if t is None else "its top at y%d" % t,
                                                     clear, feet))
            roof.append((xx, t, zz))
    return {"villager": (x, feet, z), "roof": roof, "floor": (x, feet - 1, z), "building": p["id"],
            "roof_min": min(r[1] for r in roof), "template_origin": (px, oy, pz), "rotation": rot}


def shell_cells(b):
    (x0, y0, z0), (x1, y1, z1) = b["shell"]
    (ix0, iy0, iz0), (ix1, iy1, iz1) = b["interior"]
    return [(x, y, z) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1) for x in range(x0, x1 + 1)
            if not (ix0 <= x <= ix1 and iy0 <= y <= iy1 and iz0 <= z <= iz1)]


# ------------------------------------------------------------------------------------------------------------ pack
def villager_nbt(doc, offers=None, who="barterer"):
    b = doc[who]
    tag = b["tag"]
    if offers is None:
        offers = experiment_recipes(doc) if who == "barterer" else counter_recipes(doc)
    return {"CustomName": json.dumps({"text": b["name"]}, ensure_ascii=False),
            "VillagerData": {"type": b["type"], "profession": b["profession"], "level": int(b["level"])},
            "Offers": {"Recipes": offers},
            "NoAI": True, "Invulnerable": True, "PersistenceRequired": True, "Silent": True,
            "Rotation": [float(b["yaw"]), 0.0],
            "Tags": [tag, tag + "_new"]}


def summon_line(doc, b, who="barterer"):
    import traders as TR
    x, y, z = b["villager"]
    return TR.summon_line(KIND, x, y, z, villager_nbt(doc, who=who))


def _scope(tag):
    return "type=%s,tag=%s" % (KIND, tag)


def _chain(doc, name, box, tag, act, note):
    """{name: lines} for one barterer's look-then-act chain (tools/chunk_look.py, N155) at <ns>:<folder>/<name>: the
    chain force-loads `box`, acts once the barterer's saved copy is seen there (or blind after 300 ticks: a first run),
    and 100 ticks after the act kills every copy without the new tag where a new one stands, counts the barterers into
    #<holder> cobblers_chunk_look (want 1) and releases the box. `act` runs its block checks first: a function's
    `execute if block` on a chunk not yet loaded reads false, and the act comes only after an entity there was seen, or
    300 ticks after the forceload. A breach ends the act before the kill (the standing barterer is kept), after
    scheduling the de-duplication, which then finds no new one, counts what stands and releases the box."""
    ns, fo = doc["namespace"], doc["folder"]
    base = "%s:%s/%s" % (ns, fo, name)
    scope = _scope(tag)
    fns = CL.chain(base, box, ["@e[%s]" % scope], act, [scope], tag + "_new", scope, holder(name), note=note)
    return {ref.split("/", 1)[1]: lines for ref, lines in fns.items()}


def holder(name):
    """The score holder a chain counts its barterer into (objective chunk_look.OBJ)."""
    return "direct_trades_%s" % name


def _breach_end(doc, name, score):
    ns, fo = doc["namespace"], doc["folder"]
    return ["execute if score %s %s matches 1 run schedule function %s:%s/%s_done %dt replace"
            % (score, OBJECTIVE, ns, fo, name, CL.DEDUPE_WAIT),
            "execute if score %s %s matches 1 run return fail" % (score, OBJECTIVE)]


def counter_box(doc):
    """The Northlight chain's force-loaded box: every column the counter function reads (the roof within lightning
    reach), from the data's x and z only."""
    s = doc["counter_site"]
    x, z, r = int(s["x"]), int(s["z"]), int(s["lightning_reach"])
    return (x - r, z - r, x + r, z + r)


def booth_box(b):
    """The Holdfast chain's force-loaded box: the booth's whole 5x5 shell (at (3634, 6462) its z6464 is the next chunk,
    where an unloaded shell cell slips the breach check: A4 audit, 2026-10-07)."""
    (x0, _y0, z0), (x1, _y1, z1) = b["shell"]
    return (x0, z0, x1, z1)


def counter_functions(doc, c):
    """The Northlight barterer: read the Mart back (every roof block within lightning reach, the floor, the air), then
    summon, inside the look-then-act chain. Nothing is written but the villager."""
    x, y, z = c["villager"]
    fx, fy, fz = c["floor"]
    tag = doc["counter_barterer"]["tag"]
    br = "scoreboard players set %s %s 1" % (COUNTER_BREACH, OBJECTIVE)
    act = ["# Northlight barterer in %s, %d approved line(s). Refuses unless the Mart's roof, floor and air are where its "
           "template puts them" % (c["building"], len(counter_recipes(doc))),
           "scoreboard objectives add %s dummy" % OBJECTIVE,
           "scoreboard players set %s %s 0" % (COUNTER_BREACH, OBJECTIVE)]
    act += ["execute if block %d %d %d #minecraft:air run %s" % (rx, ry, rz, br) for rx, ry, rz in c["roof"]]
    act += ["execute if block %d %d %d #minecraft:air run %s" % (fx, fy, fz, br),
            "execute unless block %d %d %d #minecraft:air run %s" % (x, y, z, br),
            "execute unless block %d %d %d #minecraft:air run %s" % (x, y + 1, z, br)]
    act += _breach_end(doc, "counter", COUNTER_BREACH)
    act += ["kill @e[%s]" % _scope(tag), summon_line(doc, c, who="counter_barterer")]
    return _chain(doc, "counter", counter_box(doc), tag, act,
                  "tools/direct_trades.py from data/direct_trades.json counter_site")


def functions(doc, b):
    ns = doc["namespace"]
    tag = doc["barterer"]["tag"]
    (x0, y0, z0), (x1, y1, z1) = b["shell"]
    lx, ly, lz = b["light"]
    act = ["# the experiment booth and EXP-055's villager. %d experiment offer(s) here; %d approved line(s) at the "
           "Northlight barterer, %d held."
           % (len(experiment_recipes(doc)), len(counter_recipes(doc)), len(held_lines(doc))),
           "scoreboard objectives add %s dummy" % OBJECTIVE,
           "scoreboard players set #breach %s 0" % OBJECTIVE]
    # refuse to carve into a cave, a cellar or water: any shell cell that is air, water or lava stops the function.
    # On a re-run the shell is the booth's own stone, so the check passes and the booth is laid again unchanged
    act += ["execute if block %d %d %d #%s:%s run scoreboard players set #breach %s 1" % (x, y, z, ns, BREACH_TAG,
                                                                                          OBJECTIVE)
            for x, y, z in shell_cells(b)]
    act += _breach_end(doc, "place", "#breach")
    act += ["fill %d %d %d %d %d %d %s hollow" % (x0, y0, z0, x1, y1, z1, doc["site"]["booth"]["shell"]),
            "setblock %d %d %d %s" % (lx, ly, lz, doc["site"]["booth"]["light"]),
            "kill @e[%s]" % _scope(tag),
            summon_line(doc, b)]
    return _chain(doc, "place", booth_box(b), tag, act, "tools/direct_trades.py from data/direct_trades.json")


def files(doc, g):
    probs = check(doc)
    if probs:
        raise DirectTradeError("direct_trades: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = booth(doc, g)
    c = counter_spot(doc)
    ns, fo = doc["namespace"], doc["folder"]
    fns = functions(doc, b)
    fns.update(counter_functions(doc, c))
    total = 0
    for name, lines in fns.items():
        bad = function_limits.check_lines(lines, name)
        if bad:
            raise DirectTradeError("%s: %d command(s) the server would refuse: %s" % (name, len(bad), bad[:3]))
        total += sum(1 for ln in lines if ln.strip() and not ln.startswith("#"))
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, fo, k): "\n".join(v) + "\n" for k, v in fns.items()}
    out["data/%s/tags/block/%s.json" % (ns, BREACH_TAG)] = json.dumps(
        {"values": ["#minecraft:air", "minecraft:water", "minecraft:lava"]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: direct trades, the barterer (tools/direct_trades.py)"}},
                                    indent=2) + "\n"
    return out, {"booth": b, "counter": c, "commands": total}


# ------------------------------------------------------------------------------------------------------------ the step
def steps(doc=None):
    """R18DT: both barterers' look-then-act chains (tools/chunk_look.py, N155) started at once, one wait for the whole
    chain, then each count read back (one barterer each). No step-level forceload: each chain holds and releases its
    own box (a forceload is per chunk, not counted, so a step's release would drop the chunk under the chain). The two
    boxes share no chunk (tests/test_direct_trades.py). From the data alone, so the step list needs no heightmap."""
    doc = doc or load()
    ns, fo = doc["namespace"], doc["folder"]
    per = [CL.steps("%s:%s/%s" % (ns, fo, name), holder(name), 1, label)
           for name, label in (("place", "the Holdfast booth's barterer"), ("counter", "the Northlight barterer"))]
    return [s[0] for s in per] + [per[0][1]] + [s[2] for s in per]


def rcon_checks(doc=None):
    """The read-backs EXP-055 (a) runs over RCON with no player, each a command: one selector per check, limit=1
    inside it (a second bracket group is a parse error: review N113)."""
    doc = doc or load()
    out = []
    for who, score in (("barterer", "#breach"), ("counter_barterer", COUNTER_BREACH)):
        tag = doc[who]["tag"]
        one = "@e[type=%s,tag=%s,limit=1]" % (KIND, tag)
        out += ["execute if entity @e[type=%s,tag=%s]" % (KIND, tag),
                "data get entity %s VillagerData" % one,
                "data get entity %s Offers.Recipes" % one,
                "data get entity %s NoAI" % one,
                "scoreboard players get %s %s" % (score, OBJECTIVE)]
    return out


# ------------------------------------------------------------------------------------------------------------ CLI
def write(out_files, out=OUT):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "plan", "edges"))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    doc = load()
    if a.cmd == "edges":
        print(json.dumps(edges(doc), indent=1))
        return 0
    priced = pricing_problems(doc)
    if priced:
        raise DirectTradeError("direct_trades pricing: %d problem(s):\n  %s" % (len(priced), "\n  ".join(priced)))
    import ground as G
    out, res = files(doc, G.load())
    b, c = res["booth"], res["counter"]
    if a.cmd == "build":
        write(out, a.out)
    prices = counter_prices()
    print("experiment villager at %s (ground %s), %d offers; Northlight barterer at %s in %s (lowest roof within "
          "reach y%d), %d lines, %d held; %d commands; step %s: %s"
          % (b["villager"], json.dumps(b["ground"]), len(experiment_recipes(doc)), c["villager"], c["building"],
             c["roof_min"], len(counter_recipes(doc)), len(held_lines(doc)), res["commands"], STEP,
             json.dumps([list(s) for s in steps(doc)])))
    for ln in placed_lines(doc):
        v, r = line_value(doc, ln), reference_price(ln, prices)
        print("  %s: inputs $%d, reference $%d (%.2f)" % (ln["id"], v, r, v / r))
    if a.cmd == "build":
        print("wrote %d files to %s" % (len(out), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
