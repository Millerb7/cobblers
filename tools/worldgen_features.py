#!/usr/bin/env python
"""Inventory every modded worldgen feature the pack places, and where else its items come from.

A WorldPainter export generates no features, so anything the pack only ever
places through worldgen is absent from the map. For each non-vanilla placed
feature this reads, from the server's jars and datapacks:

  - the configured feature it places and the modded blocks it names
  - which biomes it is attached to, where that is data (biome tags named
    has_feature/..., NeoForge biome modifiers); Fabric code attachments are
    invisible here and reported as unknown
  - for each placed block, what item it drops (block loot tables)
  - for each of those items, every other source in data: crafting recipes,
    non-block loot tables (chests, archaeology, gameplay), villager trades
    in datapack JSON, and structure templates are listed by id

Each item is then summarised as worldgen-only, or also obtainable by loot or
crafting. Mob drops, code-driven rewards and trades added in code are not
visible to this tool and are called out as such.

  python tools/worldgen_features.py --server-dir <server-dir, under the lock>
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import spawn_biomes as SB

ROOT = Path(__file__).resolve().parent.parent
PLACED_RE = re.compile(r"^data/([^/]+)/worldgen/placed_feature/(.+)\.json$")
CONFIGURED_RE = re.compile(r"^data/([^/]+)/worldgen/configured_feature/(.+)\.json$")
LOOT_RE = re.compile(r"^data/([^/]+)/loot_tables?/(.+)\.json$")
RECIPE_RE = re.compile(r"^data/([^/]+)/recipes?/(.+)\.json$")
BIOME_TAG_RE = re.compile(r"^data/([^/]+)/tags/worldgen/biome/(.+)\.json$")
MODIFIER_RE = re.compile(r"^data/([^/]+)/(neoforge|forge)/biome_modifier/(.+)\.json$")
TRADES_RE = re.compile(r"^data/([^/]+)/trades/(.+)\.json$")
ID_RE = re.compile(r'"(?:Name|name|id|item|result|block)"\s*:\s*"([a-z0-9_.\-]+:[a-z0-9_/.\-]+)"')

CATEGORIES = [
    ("waystone", re.compile(r"waystone")),
    ("fossil", re.compile(r"fossil|prehistoric")),
    ("apricorn", re.compile(r"apricorn")),
    ("berry", re.compile(r"berr")),
    ("evolution stone", re.compile(r"(fire|water|thunder|leaf|moon|sun|shiny|dusk|dawn|ice)_stone")),
    ("mega / dynamax / z", re.compile(r"mega|keystone|max_mushroom|dynamax|z_crystal|galar_particle")),
    ("gem or type ore", re.compile(r"_ore|gem|tumblestone")),
    ("plant or ingredient", re.compile(r"mint|leek|herb|nut|root|grain|flower|seed|vivichoke|pep|tuber")),
    ("habitat", re.compile(r"habitat")),
]


def category(text):
    for name, rx in CATEGORIES:
        if rx.search(text):
            return name
    return "other"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_DIR"))
    p.add_argument("--out", default=str(ROOT / "derived" / "features" / "features.json"))
    p.add_argument("--markdown", default=None)
    a = p.parse_args(argv)
    if not a.server_dir:
        raise SystemExit("--server-dir or COBBLERS_SERVER_DIR is required")
    packs = SB.discover(a.server_dir)

    placed, configured, loot, recipes, btags, modifiers, trades = {}, {}, {}, {}, {}, {}, {}
    for pk in packs:
        for path in pk.files:
            for rx, table in ((PLACED_RE, placed), (CONFIGURED_RE, configured), (LOOT_RE, loot),
                              (RECIPE_RE, recipes), (BIOME_TAG_RE, btags), (TRADES_RE, trades)):
                m = rx.match(path)
                if m:
                    table["%s:%s" % m.groups()[:2]] = (pk, path)
                    break
            else:
                m = MODIFIER_RE.match(path)
                if m:
                    modifiers["%s:%s" % (m.group(1), m.group(3))] = (pk, path)

    def text(entry):
        pk, path = entry
        return pk.files[path]().decode("utf-8", "replace")

    # block -> dropped items, from block loot tables
    drops = {}
    for key, entry in loot.items():
        ns, rest = key.split(":", 1)
        if rest.startswith("blocks/"):
            block = "%s:%s" % (ns, rest[len("blocks/"):])
            drops[block] = sorted({i for i in ID_RE.findall(text(entry)) if i != block and not i.startswith("minecraft:")} | ({block} if block in text(entry) else set()))
    # item -> sources
    recipe_out = defaultdict(list)
    for key, entry in recipes.items():
        try:
            doc = json.loads(text(entry))
        except ValueError:
            continue
        res = doc.get("result") if isinstance(doc, dict) else None
        results = res if isinstance(res, list) else [res]
        for r in results:
            if isinstance(r, str):
                rid = r
            elif isinstance(r, dict):
                rid = r.get("id") or r.get("item")
            else:
                rid = None
            if isinstance(rid, str):
                recipe_out[rid].append(key)
    loot_in = defaultdict(list)
    for key, entry in loot.items():
        if key.split(":", 1)[1].startswith("blocks/"):
            continue
        for i in set(ID_RE.findall(text(entry))):
            loot_in[i].append(key)
    trade_in = defaultdict(list)
    for key, entry in trades.items():
        for i in set(ID_RE.findall(text(entry))):
            trade_in[i].append(key)

    # feature attachment through has_feature biome tags or modifiers
    attach = defaultdict(list)
    for key in btags:
        if "/has_feature/" in "/" + key.split(":", 1)[1] or key.split(":", 1)[1].startswith("has_feature/"):
            attach[key.split("has_feature/", 1)[1]].append("#" + key)
    for key, entry in modifiers.items():
        t = text(entry)
        for pf in re.findall(r'"([a-z0-9_]+:[a-z0-9_/]+)"', t):
            if pf in placed:
                attach[pf.split(":", 1)[1]].append("modifier " + key)

    NAME_RE = re.compile(r'"Name"\s*:\s*"([a-z0-9_.\-]+:[a-z0-9_/.\-]+)"')
    FEATREF_RE = re.compile(r'"feature"\s*:\s*"([a-z0-9_.\-]+:[a-z0-9_/.\-]+)"')

    def blocks_of(feature_ref, depth=0):
        """Modded block states a feature places ("Name" fields), following feature references."""
        if depth > 5:
            return set()
        if isinstance(feature_ref, str):
            entry = configured.get(feature_ref) or placed.get(feature_ref)
            if not entry:
                return set()
            raw = text(entry)
        else:
            raw = json.dumps(feature_ref)
        out = {b for b in NAME_RE.findall(raw) if not b.startswith("minecraft:")}
        for ref in FEATREF_RE.findall(raw):
            if ref != feature_ref:
                out |= blocks_of(ref, depth + 1)
        return out

    def code_placed(cf):
        """What a code-typed feature places when its JSON names no blocks."""
        t = (cf or {}).get("type") or ""
        conf = (cf or {}).get("config") or {}
        if conf.get("cobblemon_structures"):
            return ["template " + x for x in conf["cobblemon_structures"]]
        if not t.startswith("minecraft:"):
            return ["placed in code by feature type " + t]
        return []

    rows, items = [], {}
    for key, entry in sorted(placed.items()):
        if key.startswith("minecraft:"):
            continue
        try:
            doc = json.loads(text(entry))
        except ValueError:
            continue
        feat = doc.get("feature")
        cf = json.loads(text(configured[feat])) if isinstance(feat, str) and feat in configured else (feat if isinstance(feat, dict) else {})
        blocks = sorted(blocks_of(feat))
        coded = [] if blocks else code_placed(cf)
        item_rows = []
        for b in blocks:
            dropped = drops.get(b, [b])
            for it in dropped:
                if it not in items:
                    items[it] = {"item": it, "recipes": sorted(recipe_out.get(it, []))[:6],
                                 "loot_tables": sorted(loot_in.get(it, []))[:8],
                                 "trades": sorted(trade_in.get(it, [])),
                                 "placed_by_features": []}
                items[it]["placed_by_features"].append(key)
                item_rows.append(it)
        name = key.split(":", 1)[1]
        rows.append({
            "placed_feature": key, "source": entry[0].name, "feature_type": cf.get("type"),
            "category": category(key + " " + " ".join(blocks)),
            "blocks": blocks, "code_placed": coded, "items": sorted(set(item_rows)),
            "attached_via": sorted(set(attach.get(name, []) + attach.get(name.split("/")[-1], []))) or None,
            "placement": [pm.get("type") for pm in doc.get("placement") or []],
        })
    for it in items.values():
        it["placed_by_features"] = sorted(set(it["placed_by_features"]))
        if it["recipes"] and it["loot_tables"]:
            it["other_sources"] = "loot and crafting"
        elif it["recipes"]:
            it["other_sources"] = "crafting"
        elif it["loot_tables"]:
            it["other_sources"] = "loot"
        elif it["trades"]:
            it["other_sources"] = "trade"
        else:
            it["other_sources"] = "worldgen only (in data)"
    result = {"schema": "cobblers.derived.worldgen_features/1", "features": rows,
              "items": sorted(items.values(), key=lambda i: i["item"]),
              "notes": ["Sources in code (mob drops, scripted rewards, code-registered trades or recipes) are not visible here.",
                        "attached_via is null when a feature is attached to biomes in code (Fabric biome modification)."]}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    if a.markdown:
        lines = ["<!-- generated by tools/worldgen_features.py -->", "",
                 "| Item placed by worldgen | Features | Other sources in data | Recipes | Loot tables |",
                 "|---|---|---|---|---|"]
        for it in result["items"]:
            lines.append("| `%s` | %s | %s | %s | %s |" % (
                it["item"], ", ".join("`%s`" % f for f in it["placed_by_features"][:3]) + (" +%d" % (len(it["placed_by_features"]) - 3) if len(it["placed_by_features"]) > 3 else ""),
                it["other_sources"], len(it["recipes"]), len(it["loot_tables"])))
        Path(a.markdown).write_text("\n".join(lines) + "\n", encoding="utf-8")
    only = [i for i in result["items"] if i["other_sources"].startswith("worldgen only")]
    print("%d modded placed features, %d items placed; %d items with no other source in data -> %s"
          % (len(rows), len(items), len(only), out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
