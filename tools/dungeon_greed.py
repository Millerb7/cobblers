#!/usr/bin/env python
"""GREED: one system that weighs everything a run takes and turns it into the clock's rate (unit GREED, 2026-10-10).

The owner (2026-10-10): "any Pokemon caught should count as a resource, so the clock should run faster. We will need a
system to weigh all valuables, like 20 coal or a diamond is 1 point, and 2 points is +0.1x faster or something." And
on staging the same day: ore mined in a Night Shift wall "did not count", and "it should". This replaces the D13 step
ladder (5 / 10 / 15 / 20 blocks taken -> x1.25 / 1.5 / 2 / 3), which counted one thing only (a seam cell going to air).

Mechanism rung: datapack plus generator. Vanilla statistics, a Cobblemon callback the repository has already run, and
scoreboard arithmetic; nothing here needs a scripting layer or a mod.

THE TABLE (data/dungeon_greed.json): points in cp (a hundredth of a point; 1 point = $100 of the economy's prices,
the owner's two anchors pinned: 20 coal = 1 point, 1 diamond = 1 point). `items` (each with its price source), `groups`
(the Mega Stones, by id from the Mega Showdown jar), `blocks` (a block's cp is DERIVED from its `drops` x the items'
cp, and checked here), `loot_tables` (a string loot table a vault names), `catches` (by room kind and band), `rate`.

THE MEASURE: three source events, each counted once, in the world, never from an inventory:
  1. MINED. One objective per valued block the rift pick can break in any dungeon, criterion `minecraft.mined:<id>`
     (EXP-073 R1: the criteria parse on staging, PASS; that they rise in adventure mode under can_break is that
     experiment's open owner part). Zeroed at the threshold (greed/zero, from slot/s<g>/start); each pass with the clock
     running (m/clock, before the charge) greed/mined adds count x the block's cp and zeroes the count. So EVERY block
     the member mines anywhere in the run counts at its table value: a seam, a wall, a pile. Anything mined before
     the threshold, in the tail or between runs is zeroed at the next threshold and never converted.
  2. OPENED. A vault chest's loot (tools/dungeon_puzzles.py: its tick sees the LootTable tag go) credits the chest's
     EXPECTED value for the entrant's band (chest_cp: chance x mean count x the item's cp, summed), once per chest.
  3. CAUGHT. The `pokemon_captured` callback (data/cobblemon/callbacks/pokemon_captured/cobblers_dungeons.molang; the
     same `q.player.uuid` -> function shape EXP-042 session 5 ran, relayed in EXP-053's table) runs greed/catch as the
     catcher. It gates on a live run (dg.st 3), reads the room kind from where the catcher stands (the caught entity is
     already gone at the hook), and credits catches.cp_by_band[kind][band].
  Every credit goes through greed/add: `dg.gp` only ever has cp ADDED, and the rate is only ever RAISED. So: loot carried
  in never counts (no event), dropping and re-picking changes nothing (no event), a stash, a pet or a teammate holding
  loot changes nothing (members_max is 1: solo, D16; with co-op the mined stat is per player, so each member is charged
  for their own mining), releasing a catch refunds nothing, and a seam cell is not ALSO counted by the seam (its old
  greed/take hook is gone: the stat is the one measure).

THE RATE: rate = min(cap, base + floor(dg.gp / per_step_cp)) = min(30, 10 + floor(cp / 200)); units_per_tick is 10,
so x1 is 10 and 0.1x is one unit; the bar shows x<rate/10>.<rate%10> and the points taken to a tenth.

Interface (tools/dungeon.py build() and functions() call these): objective_lines, load_lines, functions, callback_path /
callback, chest_lines (the vault), zero_lines and bar data via OBJ_G; problems(doc) is registered in dungeon.problems.
What this does NOT cover: items a wild Pokemon drops (no source event proven), relics (unpriced by design), escrow.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

TABLE = ROOT / "data" / "dungeon_greed.json"
CALLBACK_PATH = "data/cobblemon/callbacks/pokemon_captured/cobblers_dungeons.molang"
OBJ_G = {"gp": "dg.gp",   # cp taken this run (only ever added to)
         "rx": "dg.rx",   # the bar: rate / 10
         "ry": "dg.ry",   # the bar: rate % 10
         "gw": "dg.gw",   # the bar: whole points taken
         "gt": "dg.gt"}   # the bar: tenths of a point
MINED = "dg.m%d"          # one per counted block, criterion minecraft.mined:<block>
SOURCES = ("owner", "bank", "bank_removed", "market", "derived", "unpriced")
KINDS = ("ambient", "nest", "miniboss", "habitat")
CATCH_KINDS = ("nest", "miniboss", "habitat")       # the room kinds a catch is read from; elsewhere is ambient
CATCH_ALIAS = {"fishing_room": "nest"}              # RT-B: a fished catch is a living room's, weighed as a nest's
ID = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_/.-]+$")


def load(path=TABLE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def item_cp(table, item):
    """The cp of one item, or None if the table does not price it."""
    row = table["items"].get(item)
    if row is not None:
        return int(row["cp"])
    for g in table.get("groups", {}).values():
        if item in g["ids"]:
            return int(g["cp"])
    return None


def derived_block_cp(table, block):
    """A block's cp from its drops: sum(mean count x item cp), rounded. None if a drop is unpriced or no row."""
    row = table["blocks"].get(block)
    if row is None:
        return None
    total = 0.0
    for it, n in row["drops"].items():
        v = item_cp(table, it)
        if v is None:
            return None
        total += float(n) * v
    return int(round(total))


def block_cp(table, block):
    row = table["blocks"].get(block)
    return None if row is None else int(row["cp"])


def chest_cp(table, spec):
    """The expected cp of one vault chest: a loot table id (the table's loot_tables row) or a list of stacks
    {"item", "count": n | [lo, hi], "chance"?} (tools/dungeon_puzzles.py loot_table). None if any part is unpriced."""
    if isinstance(spec, str):
        row = table.get("loot_tables", {}).get(spec)
        return None if row is None else int(row["cp"])
    total = 0.0
    for s in spec:
        v = item_cp(table, s["item"])
        if v is None:
            return None
        c = s.get("count", 1)
        mean = float(c) if isinstance(c, int) else (c[0] + c[1]) / 2.0
        total += float(s.get("chance", 1.0)) * mean * v
    return int(round(total))


def legendary_from_band(doc):
    return int(doc["engine"]["prize"]["legendary_from_band"])


def catch_cp(table, kind, band, doc=None):
    """cp for a catch of `kind` at `band`. A habitat's is its prize's: the rare non-legendary below the Beast Ball
    stage (engine.prize.legendary_from_band), the legendary or Ultra Beast from it on."""
    c = table["catches"]
    if kind == "habitat":
        doc = doc if doc is not None else _dg().load(_dg().DATA)
        h = c["habitat"]
        return int(h["legendary_cp"] if band >= legendary_from_band(doc) else h["rare_cp"])
    return int(c["cp_by_band"][kind][band - 1])


def rate_of(table, cp):
    r = table["rate"]
    return min(int(r["cap"]), int(r["base"]) + int(cp) // int(r["per_step_cp"]))


def mult_of(table, cp):
    return rate_of(table, cp) / float(table["rate"]["base"])


def _dg():
    import dungeon as D     # lazy: tools/dungeon.py imports this module inside functions()
    return D


def _rooms():
    import dungeon_rooms as R
    return R


def breakable(doc):
    """Every block the rift pick may break in any dungeon: the engine's can_break and each dungeon's pick blocks."""
    R = _rooms()
    out = set(doc["engine"]["rift_pick"]["can_break"])
    for d in doc["dungeons"]:
        if R.has_rooms(d):            # a spine dungeon (no theme) breaks only the engine's list
            out |= set(R.pick_blocks(d))
    return sorted(out)


def counted(doc, table=None):
    """[(index, block, cp)]: the blocks a mined objective watches (pick-breakable, cp > 0), in name order."""
    table = table or load()
    vals = [(b, block_cp(table, b)) for b in breakable(doc)]
    return [(i, b, v) for i, (b, v) in enumerate([(b, v) for b, v in vals if v])]


def vault_specs(doc):
    """[(dungeon, room record, band key, spec)] for every vault room of every dungeon (all variants)."""
    R = _rooms()
    import dungeon_puzzles as DP
    out = []
    for d in doc["dungeons"]:
        for r in R.all_records(d):
            if r.get("kind") == "vault":
                for k, v in DP.loot_of(r.get("params") or {}).items():
                    out.append((d, r, int(k), v))
    return out


def problems(doc, table=None):
    table = table if table is not None else load()
    bad = []
    r = table.get("rate", {})
    upt = doc["engine"]["clock"]["units_per_tick"]
    if r.get("base") != upt:
        bad.append("greed.rate.base %r must equal engine.clock.units_per_tick %r (x1)" % (r.get("base"), upt))
    if r.get("base") != 10:
        bad.append("greed.rate.base must be 10: the bar prints the rate as x<rate/10>.<rate%10> (0.1x a unit)")
    if not (isinstance(r.get("per_step_cp"), int) and r["per_step_cp"] > 0):
        bad.append("greed.rate.per_step_cp must be a positive integer")
    if not (isinstance(r.get("cap"), int) and r.get("cap", 0) > r.get("base", 0)):
        bad.append("greed.rate.cap must be an integer above base (no rate 0, D1; a cap above x1)")
    for it, row in table.get("items", {}).items():
        if not ID.match(it):
            bad.append("greed item %r is not an id" % it)
        if not (isinstance(row.get("cp"), int) and row["cp"] >= 0) or not row.get("why"):
            bad.append("greed item %s: cp a non-negative integer, with its why" % it)
        if row.get("source") not in SOURCES:
            bad.append("greed item %s: source %r is none of %s" % (it, row.get("source"), ", ".join(SOURCES)))
    for name, g in table.get("groups", {}).items():
        if not (isinstance(g.get("cp"), int) and g["cp"] >= 0) or not all(ID.match(x) for x in g.get("ids", [])):
            bad.append("greed group %s: cp a non-negative integer and every id an id" % name)
        dup = [x for x in g.get("ids", []) if x in table.get("items", {})]
        if dup:
            bad.append("greed group %s: %s also has an items row (two prices)" % (name, ", ".join(dup)))
    for blk, row in table.get("blocks", {}).items():
        want = derived_block_cp(table, blk)
        if want is None:
            bad.append("greed block %s: a drop is unpriced" % blk)
        elif row.get("cp") != want:
            bad.append("greed block %s: cp %r, its drops make %d" % (blk, row.get("cp"), want))
    for blk in breakable(doc):
        if blk not in table.get("blocks", {}):
            bad.append("the rift pick can break %s and the greed table has no row for it: mining it would be free" % blk)
    for d, rm, k, spec in vault_specs(doc):
        if chest_cp(table, spec) is None:
            bad.append("%s vault %s band %d: its loot is not priced by the greed table (%s)"
                       % (d["id"], rm["id"], k, spec if isinstance(spec, str) else
                          ", ".join(s["item"] for s in spec if item_cp(table, s["item"]) is None)))
    c = table.get("catches", {})
    if tuple(sorted(c.get("kinds", {}), key=lambda k: c["kinds"][k])) != KINDS or sorted(c.get("kinds", {}).values()) != [1, 2, 3, 4]:
        bad.append("greed.catches.kinds must be ambient 1, nest 2, miniboss 3, habitat 4")
    nb = len(doc["engine"]["bands"])
    for k in KINDS[:3]:
        v = c.get("cp_by_band", {}).get(k)
        if not (isinstance(v, list) and len(v) == nb and all(isinstance(x, int) and x >= 0 for x in v)):
            bad.append("greed.catches.cp_by_band.%s: %d non-negative integers, one a band" % (k, nb))
    h = c.get("habitat", {})
    if not (isinstance(h.get("rare_cp"), int) and isinstance(h.get("legendary_cp"), int)
            and 0 < h["rare_cp"] < h["legendary_cp"]):
        bad.append("greed.catches.habitat: rare_cp and legendary_cp integers, 0 < rare < legendary (the owner: the rare "
                   "prize is high, below a legendary)")
    elif isinstance(r.get("cap"), int) and h["legendary_cp"] >= (r["cap"] - r.get("base", 0)) * r.get("per_step_cp", 1):
        bad.append("greed.catches.habitat.legendary_cp reaches the cap alone: a prize must not end a run by itself")
    lf = doc["engine"].get("prize", {}).get("legendary_from_band")
    if not (isinstance(lf, int) and 1 <= lf <= nb):
        bad.append("engine.prize.legendary_from_band must be a band (1..%d)" % nb)
    return bad


# ------------------------------------------------------------------------------------------------- functions


# ------------------------------------------------------------------------------------------------- the vault budget (KIT3)


def vault_hours(doc, dungeon=None):
    """{band: required hours} of ONE dungeon's run: its own clock (clock_s_by_band, else the engine band's clock_s)
    over the slack. A vault is paid out of the run it stands in, so it is priced on that run's clock (MEGA-INTEGRATE,
    2026-10-11). Until then every vault was priced on the SHORTEST dungeon's clock, so adding a short dungeon shrank
    every other dungeon's vaults and each new author padded a clock to avoid it.

    With no dungeon: the shortest rooms dungeon's clock per band (tools/dungeon_resources.py required_hours), the
    floor of every dungeon's budget -- what loot shared by every dungeon (a kind's default) may be held to."""
    slack = float(doc["engine"]["clock"]["slack_factor"])
    if dungeon is not None:
        own = dungeon.get("clock_s_by_band") or {}
        return {b["band"]: float(own.get(str(b["band"]), b["clock_s"])) / slack / 3600.0 for b in doc["engine"]["bands"]}
    import dungeon_resources as RS
    hours = RS.required_hours(doc)
    for b in doc["engine"]["bands"]:
        hours.setdefault(b["band"], b["clock_s"] / slack / 3600.0)
    return hours


def vault_budget(doc, table=None, dungeon=None):
    """{band: cp} a whole vault may hold (DUNGEON_ROOMS.md 1b): dollar_factor x the gathering tier open at the band's
    lowest badge count x vault_hours(doc, dungeon), every price and rate read from tools/economy_sim.py World
    (1 cp = $1). `dungeon` (a record of doc["dungeons"]) prices that dungeon's vaults on its own clock; without it, the
    floor over every rooms dungeon (the shortest clock)."""
    import dungeon_resources as RS
    import economy_sim as E
    table = table if table is not None else load()
    factor = float((table.get("vault_budget") or {}).get("dollar_factor", 1.0))
    w = E.World(E.load_docs())
    out = {}
    for band, h in sorted(vault_hours(doc, dungeon).items()):
        badges = RS.band_badges(doc, band)
        tier = max(v for n, v in w.tier_hour.items() if w.tier_opens_badges[n] <= badges)
        out[band] = int(math.floor(factor * tier * h + 1e-9))
    return out


def vault_over(doc, table=None):
    """[(dungeon id, room id, band, chest cp, chest budget)] for every vault chest over its band's budget (every
    variant's records, every band, the loot authored for that band or the one below it). Each dungeon's vaults are
    held to ITS OWN budget (vault_budget(doc, table, d): its own clock)."""
    import dungeon_puzzles as DP
    table = table if table is not None else load()
    R = _rooms()
    out = []
    seen = set()
    for d in doc["dungeons"]:
        if not R.has_rooms(d):
            continue
        budget = None
        for r in R.all_records(d):
            if r.get("kind") == "vault" and budget is None:
                budget = vault_budget(doc, table, d)
            if r.get("kind") != "vault" or (d["id"], r["id"]) in seen:
                continue
            seen.add((d["id"], r["id"]))
            p = r.get("params") or {}
            n = max(1, int(p.get("chests", 4)))
            for band in sorted(budget):
                _k, spec = DP.loot_for(p, doc["engine"]["bands"], band)
                if spec is None:
                    continue
                v = chest_cp(table, spec)
                lim = budget[band] // n
                if v is not None and v > lim:
                    out.append((d["id"], r["id"], band, v, lim))
    return out


def vault_problems(doc, table=None):
    """problems() when vault_budget.enforce is true; else nothing (warnings() names the chests over)."""
    table = table if table is not None else load()
    if not (table.get("vault_budget") or {}).get("enforce"):
        return []
    return ["%s vault %s band %d: a chest is worth %d cp, over the band's budget of %d a chest (data/dungeon_greed.json "
            "vault_budget: a vault never pays more than the run's time spent gathering)" % x for x in vault_over(doc, table)]


def vault_warnings(doc, table=None):
    table = table if table is not None else load()
    if (table.get("vault_budget") or {}).get("enforce"):
        return []
    return ["%s vault %s band %d: a chest is worth %d cp, over the vault budget of %d a chest (not enforced yet)" % x
            for x in vault_over(doc, table)]


def objective_lines(doc, table=None):
    table = table or load()
    out = ["scoreboard objectives add %s dummy" % v for v in OBJ_G.values()]
    out += ["scoreboard objectives add %s %s" % (MINED % i, criterion(b)) for i, b, _v in counted(doc, table)]
    return out


def criterion(block):
    """`minecraft.mined:minecraft.coal_ore`: the stat type and the block id, each with a dot for its colon (EXP-073
    step 2 parsed exactly this form on staging)."""
    return "minecraft.mined:" + block.replace(":", ".")


def load_lines(doc, table=None):
    table = table or load()
    D = _dg()
    t = D.OBJ["t"]
    out = ["scoreboard players set #gstep %s %d" % (t, table["rate"]["per_step_cp"]),
           "scoreboard players set #100 %s 100" % t]
    out += ["scoreboard players set #v%d %s %d" % (i, t, v) for i, _b, v in counted(doc, table)]
    return out


def zero_lines(doc, table=None):
    """At the threshold (slot/s<g>/start), as the member: nothing mined before this counts."""
    table = table or load()
    return ["scoreboard players set @s %s 0" % (MINED % i) for i, _b, _v in counted(doc, table)]


def chest_lines(doc, band_cp):
    """A vault chest opened, as the member: credit its expected cp for the entrant's band. band_cp {band: cp}."""
    D = _dg()
    t, band = D.OBJ["t"], D.OBJ["band"]
    out = ["scoreboard players set #gv %s 0" % t]
    out += ["execute if score @s %s matches %d run scoreboard players set #gv %s %d" % (band, b, t, v)
            for b, v in sorted(band_cp.items()) if v]
    return out + ["function %s" % D.F("greed/add")]


def functions(doc, table=None):
    table = table or load()
    D = _dg()
    R = _rooms()
    O, F, HEAD = D.OBJ, D.F, D.HEAD
    t, G = O["t"], OBJ_G
    rt = table["rate"]
    ds = D.dungeons(doc)
    out = {}
    out["greed/add"] = [
        HEAD, "# As a member: #gv %s cp taken (data/dungeon_greed.json), added to %s, which only ever rises. Only while" % (t, G["gp"]),
        "# the clock runs (dg.st 3): before the threshold, in sudden death and in the tail nothing is weighed",
        "execute unless score @s %s matches 3 run return 0" % O["st"],
        "execute unless score #gv %s matches 1.. run return 0" % t,
        "scoreboard players operation @s %s += #gv %s" % (G["gp"], t),
        "function %s" % F("greed/rate"),
        "return 1"]
    tight = ds[0]["messages"]["tightens"]
    msg = json.dumps([{"text": tight, "color": "red"}, {"text": "x", "color": "red"},
                      {"score": {"name": "@s", "objective": G["rx"]}, "color": "red"}, {"text": ".", "color": "red"},
                      {"score": {"name": "@s", "objective": G["ry"]}, "color": "red"}], ensure_ascii=False)
    out["greed/rate"] = [
        HEAD, "# The rate from the points taken: min(%d, %d + cp / %d), only ever raised (the owner, 2026-10-10: +0.1x a"
        % (rt["cap"], rt["base"], rt["per_step_cp"]),
        "# 2 points). Also the bar's numbers. Runs on any entity (EXP-084's marker form)",
        "scoreboard players operation #old %s = @s %s" % (t, O["rate"]),
        "scoreboard players operation #r %s = @s %s" % (t, G["gp"]),
        "scoreboard players operation #r %s /= #gstep %s" % (t, t),
        "scoreboard players add #r %s %d" % (t, rt["base"]),
        "execute if score #r %s matches %d.. run scoreboard players set #r %s %d" % (t, rt["cap"], t, rt["cap"]),
        "execute unless score @s %s matches %d.. run scoreboard players set @s %s %d" % (O["rate"], rt["base"], O["rate"], rt["base"]),
        "execute if score #r %s > @s %s run scoreboard players operation @s %s = #r %s" % (t, O["rate"], O["rate"], t),
        "scoreboard players operation @s %s = @s %s" % (G["rx"], O["rate"]),
        "scoreboard players operation @s %s /= #10 %s" % (G["rx"], t),
        "scoreboard players operation @s %s = @s %s" % (G["ry"], O["rate"]),
        "scoreboard players operation @s %s %%= #10 %s" % (G["ry"], t),
        "scoreboard players operation @s %s = @s %s" % (G["gw"], G["gp"]),
        "scoreboard players operation @s %s /= #100 %s" % (G["gw"], t),
        "scoreboard players operation @s %s = @s %s" % (G["gt"], G["gp"]),
        "scoreboard players operation @s %s /= #10 %s" % (G["gt"], t),
        "scoreboard players operation @s %s %%= #10 %s" % (G["gt"], t),
        "execute if score @s %s > #old %s run title @s actionbar %s" % (O["rate"], t, msg),
        "execute if score @s %s > #old %s run playsound minecraft:block.respawn_anchor.deplete master @s ~ ~ ~ 1 1" % (O["rate"], t),
        "return 1"]
    cnt = counted(doc, table)
    mined = [HEAD, "# As a member whose clock runs, each pass before the charge: every valued block mined since the last pass",
             "# (vanilla minecraft.mined stats, one objective a block, EXP-073 R1), at its table cp. Wherever it was mined",
             "scoreboard players set #gv %s 0" % t]
    for i, b, v in cnt:
        mined.append("execute if score @s %s matches 1.. run function %s" % (MINED % i, F("greed/m%d" % i)))
        out["greed/m%d" % i] = [
            HEAD, "# %s mined: %d cp each (data/dungeon_greed.json blocks)" % (b, v),
            "scoreboard players operation #m %s = @s %s" % (t, MINED % i),
            "scoreboard players operation #m %s *= #v%d %s" % (t, i, t),
            "scoreboard players operation #gv %s += #m %s" % (t, t),
            "scoreboard players set @s %s 0" % (MINED % i)]
    mined += ["execute if score #gv %s matches 1.. run function %s" % (t, F("greed/add"))]
    out["greed/mined"] = mined
    out["greed/zero"] = [HEAD, "# At the threshold, as the member: the points and the mined counts from zero, the rate at x1",
                         "scoreboard players set @s %s 0" % G["gp"],
                         "scoreboard players set @s %s %d" % (O["rate"], rt["base"])] + zero_lines(doc, table) + [
                         "function %s" % F("greed/rate")]
    # catches
    kinds = table["catches"]["kinds"]
    catch = [HEAD, "# The pokemon_captured callback, as the catcher at them (any catch on the server). Counted only in a live",
             "# run: the room kind from where they stand (the caught entity is gone at the hook), the value by kind and band",
             "execute unless score @s %s matches 3 run return 0" % O["st"],
             "scoreboard players set #gk %s %d" % (t, kinds["ambient"])]
    for s in D.slots(doc):
        d = s["dungeon"]
        if not R.has_rooms(d):
            continue
        rows = []
        for b in R.slot_build(doc, d, s):
            k = CATCH_ALIAS.get(b.room["kind"], b.room["kind"])
            if k in CATCH_KINDS:
                rows.append("execute if entity @s[%s] run scoreboard players set #gk %s %d" % (R.sel_box(b.room["box"]), t, kinds[k]))
        if rows:
            out["greed/s%d/kind" % s["g"]] = [HEAD, "# slot %d: the kind of the room the catcher stands in (nest, miniboss, habitat)" % s["g"]] + rows
            catch.append("execute if score @s %s matches %d run function %s" % (O["slot"], s["g"], F("greed/s%d/kind" % s["g"])))
    catch.append("scoreboard players set #gv %s 0" % t)
    for k in KINDS:
        for bi in range(1, len(doc["engine"]["bands"]) + 1):
            v = catch_cp(table, k, bi, doc)
            catch.append("execute if score #gk %s matches %d if score @s %s matches %d run scoreboard players set #gv %s %d"
                         % (t, kinds[k], O["band"], bi, t, v))
    catch += ["function %s" % F("greed/add")]
    out["greed/catch"] = catch
    out["greed/test_set"] = [
        HEAD, "# TEST HOOK (EXP-084 form): this entity's points to $(p) cp, and its rate. Never lowers the rate it has",
        "$scoreboard players set @s %s $(p)" % G["gp"],
        "function %s" % F("greed/rate")]
    return out


def callback(doc):
    D = _dg()
    return "\n".join([
        "'Generated by tools/dungeon_greed.py from data/dungeon_greed.json. Any catch: the dungeon engine weighs it only';",
        "'if the catcher is in a live run (greed/catch gates on dg.st 3).';",
        "q.run_command('execute as ' + q.player.uuid + ' at @s run function %s');" % D.F("greed/catch"), ""])


# ------------------------------------------------------------------------------------------------- report


def report(doc, table=None):
    table = table or load()
    R = _rooms()
    import dungeon_kinds as K
    lines = ["rate = min(%d, %d + cp // %d)" % (table["rate"]["cap"], table["rate"]["base"], table["rate"]["per_step_cp"])]
    themes = R.load_themes()
    for d in doc["dungeons"]:
        t = R.theme_for(d, themes)
        for r in R.all_records(d):
            if r["kind"] != "resources":
                continue
            n = int(r.get("params", {}).get("seam_blocks", 24))
            row = []
            for b in doc["engine"]["bands"]:
                cp = sum(block_cp(table, K.seam_block_for(t, b["band"], j, n)) or 0 for j in range(n))
                row.append("b%d %.2f" % (b["band"], cp / 100.0))
            lines.append("%s %s: the whole face (%d blocks), points: %s" % (d["id"], r["id"], n, ", ".join(row)))
    seen = set()
    for d, rm, k, spec in vault_specs(doc):
        key = (d["id"], rm["id"], k)
        if key in seen:
            continue
        seen.add(key)
        lines.append("%s %s from band %d: %.2f points a chest" % (d["id"], rm["id"], k, (chest_cp(table, spec) or 0) / 100.0))
    vb = vault_budget(doc, table)
    lines.append("vault budget (KIT3, a whole vault; a chest is its share): " + ", ".join("b%d %d cp" % kv for kv in sorted(vb.items()))
                 + (" (enforced)" if (table.get("vault_budget") or {}).get("enforce") else " (not enforced yet)"))
    lines += vault_warnings(doc, table)
    return lines


def main(argv=None):
    sys.path.insert(0, str(ROOT / "tools"))
    D = _dg()
    doc = D.load(D.DATA)
    bad = problems(doc)
    print("\n".join(report(doc)))
    for b in bad:
        print("PROBLEM " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
