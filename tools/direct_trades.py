"""Direct trades: a vanilla villager with fixed item-for-item offers (data/direct_trades.json, EXP-055).

The owner, 2026-10-07: late-game items by direct trade, no money where possible. CobbleDollars cannot barter (an
Offer holds item, price and stock only: docs/OVERNIGHT_REVIEW_2026-10-06.md N63), so this writes a world-local pack,
cobblers_direct_trades, whose place function carves a small buried booth under the Holdfast counter and summons one
minecraft:villager there with its Offers written into the summon. Run by tools/reapply.py step R18DT.

What is placed: the experiment offers, and the barter lines whose `approved` is true. A line with `approved: false`
(every line today: status "proposal") is built into nothing: it appears in `edges` for the economy audit and in no
function. Every offer carries the data's fixed_trade fields; the fields and why they hold a price still are cited in
experiments/EXP-055-direct-trade-villager/README.md.

What this does NOT cover: any other villager in the world (vanilla-generated ones keep vanilla trades), and the
CobbleDollars merchants (data/markets.json), which price in money.

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
import function_limits  # noqa: E402

DATA = ROOT / "data" / "direct_trades.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_direct_trades"
PACK_FORMAT = 48  # Minecraft 1.21.1
KIND = "minecraft:villager"
STEP = "R18DT"
DEDUPE_WAIT = 100  # ticks between the summon and the de-duplication (tools/apricorn_farm.py's shape)
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
    b = doc["barterer"]
    if b["profession"] in ("minecraft:none", "minecraft:nitwit"):
        p.append("the barterer's profession %s has no trades table" % b["profession"])
    if int(b["level"]) != 5:
        p.append("the barterer's level %s is not 5: a level-up would add vanilla trades" % b["level"])
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


def shell_cells(b):
    (x0, y0, z0), (x1, y1, z1) = b["shell"]
    (ix0, iy0, iz0), (ix1, iy1, iz1) = b["interior"]
    return [(x, y, z) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1) for x in range(x0, x1 + 1)
            if not (ix0 <= x <= ix1 and iy0 <= y <= iy1 and iz0 <= z <= iz1)]


# ------------------------------------------------------------------------------------------------------------ pack
def villager_nbt(doc, offers=None):
    b = doc["barterer"]
    tag = b["tag"]
    return {"CustomName": json.dumps({"text": b["name"]}, ensure_ascii=False),
            "VillagerData": {"type": b["type"], "profession": b["profession"], "level": int(b["level"])},
            "Offers": {"Recipes": offers if offers is not None else recipes(doc)},
            "NoAI": True, "Invulnerable": True, "PersistenceRequired": True, "Silent": True,
            "Rotation": [float(b["yaw"]), 0.0],
            "Tags": [tag, tag + "_new"]}


def summon_line(doc, b):
    import traders as TR
    x, y, z = b["villager"]
    return TR.summon_line(KIND, x, y, z, villager_nbt(doc))


def functions(doc, b):
    ns, fo = doc["namespace"], doc["folder"]
    tag = doc["barterer"]["tag"]
    new = tag + "_new"
    (x0, y0, z0), (x1, y1, z1) = b["shell"]
    lx, ly, lz = b["light"]
    place = ["# Generated by tools/direct_trades.py from data/direct_trades.json: the barterer's booth and the barterer "
             "(EXP-055). %d offer(s) placed, %d barter line(s) held for the owner."
             % (len(placed_offers(doc)), len(held_lines(doc))),
             "# chunks-loaded-by: tools/reapply.py %s" % STEP,
             "scoreboard objectives add %s dummy" % OBJECTIVE,
             "scoreboard players set #breach %s 0" % OBJECTIVE]
    # refuse to carve into a cave, a cellar or water: any shell cell that is air, water or lava stops the function.
    # On a re-run the shell is the booth's own stone, so the check passes and the booth is laid again unchanged
    place += ["execute if block %d %d %d #%s:%s run scoreboard players set #breach %s 1" % (x, y, z, ns, BREACH_TAG,
                                                                                            OBJECTIVE)
              for x, y, z in shell_cells(b)]
    place += ["execute if score #breach %s matches 1 run return fail" % OBJECTIVE,
              "fill %d %d %d %d %d %d %s hollow" % (x0, y0, z0, x1, y1, z1, doc["site"]["booth"]["shell"]),
              "setblock %d %d %d %s" % (lx, ly, lz, doc["site"]["booth"]["light"]),
              summon_line(doc, b),
              "schedule function %s:%s/place_done %dt replace" % (ns, fo, DEDUPE_WAIT)]
    done = ["# Generated by tools/direct_trades.py; %d ticks after the summon: one barterer, the older copies killed"
            % DEDUPE_WAIT,
            "execute if entity @e[type=%s,tag=%s,tag=%s] run kill @e[type=%s,tag=%s,tag=!%s]"
            % (KIND, tag, new, KIND, tag, new),
            "tag @e[type=%s,tag=%s,tag=%s] remove %s" % (KIND, tag, new, new)]
    return {"place": place, "place_done": done}


def files(doc, g):
    probs = check(doc)
    if probs:
        raise DirectTradeError("direct_trades: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = booth(doc, g)
    ns, fo = doc["namespace"], doc["folder"]
    fns = functions(doc, b)
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
    return out, {"booth": b, "commands": total}


# ------------------------------------------------------------------------------------------------------------ the step
def steps(doc=None):
    """R18DT: hold the booth's chunk, run the place function, wait out its de-duplication, release. From the data's
    x and z only, so the step list needs no heightmap."""
    doc = doc or load()
    x, z = int(doc["site"]["x"]), int(doc["site"]["z"])
    # the whole 5x5 footprint (booth()'s shell), not its centre: at (3634, 6462) the box's z6464 is the next chunk,
    # where an unloaded shell cell slips the breach check (A4 audit, 2026-10-07)
    box = "%d %d %d %d" % (x - 2, z - 2, x + 2, z + 2)
    return [("cmd", "forceload add %s" % box), ("wait", 3),
            ("fn", "%s:%s/place" % (doc["namespace"], doc["folder"])), ("wait", 7),
            ("cmd", "forceload remove %s" % box)]


def rcon_checks(doc=None):
    """The read-backs EXP-055 (a) runs over RCON with no player, each a command."""
    doc = doc or load()
    sel = "@e[type=%s,tag=%s]" % (KIND, doc["barterer"]["tag"])
    return ["execute if entity %s" % sel,
            "data get entity %s[limit=1] VillagerData" % sel,
            "data get entity %s[limit=1] Offers.Recipes" % sel,
            "data get entity %s[limit=1] NoAI" % sel,
            "scoreboard players get #breach %s" % OBJECTIVE]


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
    import ground as G
    out, res = files(doc, G.load())
    b = res["booth"]
    if a.cmd == "build":
        write(out, a.out)
    print("barterer at %s (ground %s); %d offers placed, %d lines held; %d commands; step %s: %s"
          % (b["villager"], json.dumps(b["ground"]), len(placed_offers(doc)), len(held_lines(doc)), res["commands"],
             STEP, json.dumps([list(s) for s in steps(doc)])))
    if a.cmd == "build":
        print("wrote %d files to %s" % (len(out), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
