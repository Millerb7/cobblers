#!/usr/bin/env python
"""What crafting a shelf TM costs in money: every TMCraft TM a counter sells, its recipe's inputs valued at the bank.

The owner, 2026-10-22: "if a player wants to craft it should seem worth it". data/markets.json price_policies.tm_tier
crafting_floor holds every TM line's price at or above its crafted route's bank value / max_ratio, so crafting costs at
most that share of the shelf. This tool measures the crafted route; tools/markets.py applies the floor.

THE VALUATION (read from the server's recipes, never a world). An item is worth:
  the bank's buy price, when data/bank.json's bank buys it (tools/bank.py prices: base + buys): using it in a recipe
      gives up selling it, so that is what it costs in money. Not decomposed further;
  else its cheapest recipe (crafting shaped or shapeless, smithing transform, smelting, blasting, stonecutting) whose
      inputs are themselves valued this way, choosing first the recipe that leaves the fewest distinct inputs unpriced,
      then the cheapest; a recipe that needs the item itself (a cycle) is skipped. A TMCraft item always decomposes;
      any other item only through a recipe leaving at most one input unpriced, else it is itself unpriced (a feather
      is a chicken's drop, not some mod's recipe from diamonds). The smithing template is valued by its from-scratch
      recipe (seven gold ingots, a blaze powder, a cobbled deepslate), not by duplication: the dearer, stricter figure;
  else UNPRICED: worth $0 in money, listed by id. The bank buys no type gem, no held item, no mob drop and no block a
      TM names, so every TM has unpriced inputs: they cost play (an alpha's gem drop, a fight, a trip), not dollars.
      This is the brief's own measure ("valued at data/bank.json's buy prices"), and it is the floor of the money cost,
      not the effort cost.
A tag ingredient (#minecraft:planks) is unpriced as itself: the tool does not read tags.

What it reads: the mods (nested jars too), the global datapacks (`datapacks/`, not `extra/`) and the vanilla jar, the
same sources and load order as tools/tm_gate.py read_server. Pass --server-dir, or --mods-dir and --datapacks-dir for a
copy outside the server tree (the local store's server-mods-1.8.2 and a snapshot's datapacks/). The recipe content is
not committed: data/tm_craft_cost.json keeps, per TM, only the bank-bought raw inputs with their counts and the
unpriced inputs' ids, so the floor is computed offline from the committed table and today's bank prices.

  python tools/tm_craft_cost.py --mods-dir <mods> --datapacks-dir <datapacks> --vanilla-jar <jar> --write
  python tools/tm_craft_cost.py ... --check       # the committed table is what the recipes give today
  python tools/tm_craft_cost.py --report          # offline: each line's craft value, its price and the ratio
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

OUT = ROOT / "data" / "tm_craft_cost.json"
MARKETS = ROOT / "data" / "markets.json"
SCHEMA = "cobblers.tm_craft_cost/1"
GRID = ("minecraft:crafting_shaped", "minecraft:crafting_shapeless")
COOK = ("minecraft:smelting", "minecraft:blasting", "minecraft:smoking", "minecraft:campfire_cooking",
        "minecraft:stonecutting")
SMITH = ("minecraft:smithing_transform",)
# how deep a recipe chain is followed before the item is left unpriced: the TM, its blank disc's four smithing steps
# (copper -> iron -> gold -> diamond -> netherite), an ingot, its raw ore. Deeper chains only reach the same raw items
MAX_DEPTH = 8


class CraftCostError(ValueError):
    pass


def read_sources(mods_dir, datapacks_dir, vanilla_jar):
    """The loaded recipes {id: (source, json)}, read as tools/tm_gate.py read_server reads a server, plus the jars."""
    import tm_gate as TG
    mods = Path(mods_dir)
    if not mods.is_dir():
        raise CraftCostError("no mods folder at %s" % mods)
    raw, mod_ids = [], {"minecraft", "java", "fabricloader"}
    jars = {}
    if vanilla_jar:
        TG._zip_entries(zipfile.ZipFile(vanilla_jar), "vanilla", raw, set(), 0)
        jars["vanilla"] = Path(vanilla_jar).name
    for jar in sorted(mods.glob("*.jar")):
        TG._zip_entries(zipfile.ZipFile(jar), jar.name, raw, mod_ids, 10)
        if jar.name.startswith("tmcraft-"):
            jars["tmcraft"] = jar.name
            jars["tmcraft_sha256"] = hashlib.sha256(jar.read_bytes()).hexdigest()
    packs = []
    dp = Path(datapacks_dir) if datapacks_dir else None
    if dp and dp.is_dir():
        for p in sorted(dp.iterdir()):
            if p.suffix == ".zip":
                TG._zip_entries(zipfile.ZipFile(p), "datapack:" + p.name, raw, set(), 20)
                packs.append(p.name)
            elif p.is_dir() and p.name != "extra":
                TG._folder_entries(p, "datapack:" + p.name, raw, 20)
                packs.append(p.name)
    raw.sort(key=lambda t: t[0])
    server = {"entries": [e for _, e in raw], "mod_ids": mod_ids, "disabled_adv_ns": set(), "moves": []}
    res = TG.resolve(server)
    jars["mods"] = len(list(mods.glob("*.jar")))
    jars["datapacks"] = [p for p in packs if p.endswith(".zip")]
    jars["datapack_folders"] = sum(1 for p in packs if not p.endswith(".zip"))
    return res["recipes"], jars


def _alts(ing):
    """One ingredient slot's alternatives: item ids, or '#tag'."""
    out = []
    for a in (ing if isinstance(ing, list) else [ing]):
        if isinstance(a, dict) and isinstance(a.get("item"), str):
            out.append(a["item"])
        elif isinstance(a, dict) and isinstance(a.get("tag"), str):
            out.append("#" + a["tag"])
        elif isinstance(a, str):
            out.append(a)
    return out


def slots(recipe):
    """[(alternatives, count)] one recipe consumes, and the result count; None for a type this tool does not read."""
    t = recipe.get("type")
    r = recipe.get("result")
    n = (r.get("count") or 1) if isinstance(r, dict) else 1
    if t == "minecraft:crafting_shapeless":
        return [(_alts(i), 1) for i in recipe.get("ingredients") or []], n
    if t == "minecraft:crafting_shaped":
        key = recipe.get("key") or {}
        counts = {}
        for row in recipe.get("pattern") or []:
            for ch in row:
                if ch != " ":
                    counts[ch] = counts.get(ch, 0) + 1
        return [(_alts(key.get(ch)), c) for ch, c in sorted(counts.items())], n
    if t in SMITH:
        return [(_alts(recipe.get(k)), 1) for k in ("template", "base", "addition") if recipe.get(k)], n
    if t in COOK:
        return [(_alts(recipe.get("ingredient")), 1)], n
    return None


def result_of(recipe):
    r = recipe.get("result")
    if isinstance(r, dict):
        return r.get("id") or r.get("item")
    return r if isinstance(r, str) else None


class Valuer:
    """value(item) -> (unpriced count, money, {bank item: Fraction}, {unpriced id: Fraction}); see the module doc."""

    def __init__(self, recipes, bank):
        self.bank = bank
        self.by_result = {}
        for rid in sorted(recipes):
            _src, doc = recipes[rid]
            got = result_of(doc)
            s = slots(doc)
            if isinstance(got, str) and s is not None and s[0]:
                self.by_result.setdefault(got, []).append((rid, s))
        self.memo = {}

    def value(self, item, stack=()):
        if item in self.memo:
            return self.memo[item]
        if item in self.bank:
            v = (0, Fraction(self.bank[item]), {item: Fraction(1)}, {})
            self.memo[item] = v
            return v
        if item in stack:
            return None
        if item.startswith("#") or len(stack) >= MAX_DEPTH:
            return (1, Fraction(0), {}, {item: Fraction(1)})
        best = None
        for _rid, (ss, n) in self.by_result.get(item, []):
            money, leaves, unpriced = Fraction(0), {}, {}
            ok = True
            for alts, c in ss:
                opts = [v for v in (self.value(a, stack + (item,)) for a in alts) if v is not None]
                if not opts:
                    ok = False
                    break
                o = min(opts, key=lambda v: (v[0], v[1]))
                money += o[1] * c
                for k, q in o[2].items():
                    leaves[k] = leaves.get(k, 0) + q * c
                for k, q in o[3].items():
                    unpriced[k] = unpriced.get(k, 0) + q * c
            if not ok:
                continue
            cand = (len(unpriced), money / n, {k: q / n for k, q in leaves.items()},
                    {k: q / n for k, q in unpriced.items()})
            if best is None or (cand[0], cand[1]) < (best[0], best[1]):
                best = cand
        # a TMCraft item (a TM, a blank, the template) has no source but its recipe, so it always decomposes. Any other
        # item decomposes only through a recipe leaving at most ONE input unpriced; else it is itself the unpriced
        # input (a feather is a chicken's drop, not the 18 diamonds of some mod's feather recipe: a recipe that turns
        # priced goods into a gatherable item is not how a player gets it)
        if best is None or (not item.startswith("tmcraft:") and best[0] > 1):
            best = (1, Fraction(0), {}, {item: Fraction(1)})
        if not stack or not best[3]:
            self.memo[item] = best   # a value found under a cycle guard may be partial: kept only when complete
        return best


def shelf_tms(markets=None):
    """Every TMCraft TM a counter line sells (stock), in file order, without repeats."""
    doc = markets if markets is not None else json.loads(MARKETS.read_text(encoding="utf-8"))
    seen = []
    for c in doc.get("counters") or []:
        for it in c.get("stock") or []:
            i = it.get("item", "")
            if i.startswith("tmcraft:tm_") and i not in seen:
                seen.append(i)
    return seen


def _num(q):
    q = Fraction(q)
    return int(q) if q.denominator == 1 else round(float(q), 4)


def table(recipes, jars, bank):
    v = Valuer(recipes, bank)
    by = {}
    missing = []
    for tm in shelf_tms():
        if tm not in v.by_result:
            missing.append(tm)
            continue
        un, money, leaves, unpriced = v.value(tm)
        by[tm] = {"bank_value": _num(money),
                  "bank_inputs": {k: _num(q) for k, q in sorted(leaves.items())},
                  "unpriced": sorted(unpriced)}
    if missing:
        raise CraftCostError("no recipe makes %s in the recipes read" % ", ".join(missing))
    return {
        "schema": SCHEMA,
        "generated_by": "tools/tm_craft_cost.py --write (the recipes are read, never committed; see the tool's doc)",
        "status": "MEASURED from the recipes the server loads (the read is named in read_from); NOT crafted in game",
        "valuation": "an item is worth the bank's buy price (tools/bank.py prices) when the bank buys it, else its cheapest "
                     "recipe's inputs valued the same way (fewest unpriced inputs first, then the cheapest), else it is "
                     "unpriced ($0 in money; it costs play). bank_value is sum(bank_inputs x the bank's price) at "
                     "--write; tools/markets.py recomputes it from bank_inputs and today's prices",
        "read_from": jars,
        "by_tm": by,
    }


def bank_value(entry, bank):
    """Today's bank value of one TM's crafted route, from its committed bank inputs."""
    total = Fraction(0)
    for item, q in (entry.get("bank_inputs") or {}).items():
        if item not in bank:
            raise CraftCostError("%s is no longer bought by the bank: re-run tools/tm_craft_cost.py --write" % item)
        total += Fraction(str(q)) * bank[item]
    return total


def load(path=OUT):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise CraftCostError("%s: schema %r, expected %r" % (path, doc.get("schema"), SCHEMA))
    return doc


def render(doc):
    lines = ["{"]
    keys = [k for k in doc if k != "by_tm"]
    for k in keys:
        lines.append("  %s: %s," % (json.dumps(k), json.dumps(doc[k], ensure_ascii=False)))
    lines.append('  "by_tm": {')
    items = list(doc["by_tm"].items())
    for i, (tm, e) in enumerate(items):
        lines.append("    %s: %s%s" % (json.dumps(tm), json.dumps(e, ensure_ascii=False), "," if i < len(items) - 1 else ""))
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def report():
    import bank as B
    import markets as M
    bank = B.prices(B.load())
    doc = M.load()
    cc = load()
    rows = []
    for c in doc.get("counters") or []:
        for it in c.get("stock") or []:
            if it.get("price_rule") == M.TM_POLICY:
                bv = bank_value(cc["by_tm"][it["item"]], bank)
                unit = it["price"] / (it.get("count") or 1)
                rows.append((float(bv) / unit, c["id"], it["item"], float(bv), unit))
    for r, cid, item, bv, unit in sorted(rows, reverse=True):
        print("%-18s %-26s craft $%8.2f  shelf $%6d  ratio %.3f" % (cid, item, bv, unit, r))
    rs = sorted(r for r, *_ in rows)
    if rs:
        print("%d lines; worst %.3f, median %.3f" % (len(rs), rs[-1], rs[len(rs) // 2]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--server-dir")
    ap.add_argument("--mods-dir")
    ap.add_argument("--datapacks-dir")
    ap.add_argument("--vanilla-jar")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    if a.report:
        report()
        return 0
    import bank as B
    mods = a.mods_dir or (str(Path(a.server_dir) / "mods") if a.server_dir else None)
    dps = a.datapacks_dir or (str(Path(a.server_dir) / "datapacks") if a.server_dir else None)
    if not mods:
        ap.error("--server-dir or --mods-dir is required for --write and --check")
    if not a.vanilla_jar:
        ap.error("--vanilla-jar is required: without vanilla's recipes no ingot or tool decomposes")
    recipes, jars = read_sources(mods, dps, a.vanilla_jar)
    doc = table(recipes, jars, B.prices(B.load()))
    text = render(doc)
    if a.check:
        old = load()
        bad = sorted(tm for tm in set(old["by_tm"]) | set(doc["by_tm"]) if old["by_tm"].get(tm) != doc["by_tm"].get(tm))
        if bad:
            print("tm_craft_cost: %d TM(s) differ from the committed table: %s" % (len(bad), ", ".join(bad[:10])))
            return 1
        print("tm_craft_cost: the committed table matches the recipes (%d TMs)" % len(doc["by_tm"]))
        return 0
    if a.write:
        OUT.write_bytes(text.encode("utf-8"))   # LF, as .gitattributes keeps every JSON file
        print("wrote %s (%d TMs)" % (OUT.relative_to(ROOT), len(doc["by_tm"])))
    else:
        print(text[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
