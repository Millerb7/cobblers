#!/usr/bin/env python
"""The players' held-item guide, docs/player/held-items.html: every item a Pokemon can hold, and every public way to get
it, with where and how often.

  python tools/player_guide_held_items.py            # write docs/player/held-items.html and register it in guides.json
  python tools/player_guide_held_items.py --check    # regenerate in memory; exit 1 if the page or its entry is stale
  python tools/player_guide_held_items.py --out F    # write elsewhere (not the site's page, not registered)

WHICH ITEMS. Cobblemon 1.8.0's own list: the item tag cobblemon:held/is_held_item in the jar
(data/cobblemon/tags/item/held/is_held_item.json), with the tags it names expanded (#cobblemon:type_gems, the terrain
seeds). Nothing is added by hand. Every one is on the page; one with no source this guide knows says so.

THE SOURCES (an item can have several), each from the file that decides it:
  Shops         the items page's own readers (tools/player_guide_items.py): data/markets.json sited counter stock at the
                unit price, the Poke Marts' shelves by badge tier, the barter board's approved lines. A held, superseded
                or unsited line is never a source. Prices are on items.html; this page names the place and the price.
  Crafting      every recipe in the Cobblemon 1.8.0 jar whose result is the item (crafting table, furnace, stonecutter,
                brewing stand), worded as items.html words the training items' recipes. Only the Cobblemon jar is read:
                the Cobbleverse datapack carries no override of a Cobblemon recipe (checked 2026-10-12 against
                COBBLEVERSE-DP-v31.zip), but another mod's recipe for the same item would not be listed.
  Dungeon vaults  data/dungeons.json vault and bank-vault loot, read by the dungeon guide's own collect()
                (tools/player_guide_dungeons.py) so the two pages cannot disagree. A stack is a fixed item or a weighted
                `one_of`; the chance a chest holds an item is the stack's `chance` (default 1) times the item's weight
                over the stack's total weight, and an item in two stacks of one chest is 1 - (1-p)(1-q). Every chest of a
                vault is the same table and rolls on its own.
  Wild drops    the drops page's own model (tools/player_guide_drops.py collect()): the species the region map lists,
                the jar's drop tables with the datapack's and our fixes. Chances per defeat are that page's.
  Carried       data/spawns.json `held_items`: a wild spawn of a listed species sometimes holds the item, a percentage
                per appearance (tools/build_encounters.py stamps them from data/encounter_design.json rules.held_items;
                the owner, 2026-10-05: "rare enough to be a find rather than a farm"). Only species the region map lists.
  Alpha spoils  the type gems: data/alpha_spoils.json (a wild alpha Pokemon of that type pays them when defeated).

WHAT THE PAGE NEVER LISTS. An item given by a cache, a shrine, a boss, a quest or a reward chest (the secret files of
tests/test_player_site_leaks.py: data/rewards.json, legendaries, entei_boss.json and the rest) gets no line for it: those
are discoveries, so such an item shows as "no source known to this guide". The Arena's prizes and the Challenge
voucher are not listed: the battle guide leaves the Arena out, and the voucher is a schedule nothing grants yet. No
species the jar labels legendary, mythical, ultra_beast or paradox is ever named (the dungeon guide's rule, checked with
its own Dex). No coordinate is printed.

Not checked in a running game: the drop and carry chances are the data's, the vaults have not run on a server, and the
recipes are the jar's.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import player_site  # noqa: E402  the shared header, footer, filter, search and manifest of docs/player/
import player_guide_battles as PB  # noqa: E402  the Cobblemon jar finder
import player_guide_items as PI  # noqa: E402  shops, Marts, barter and item names
import player_guide_drops as PD  # noqa: E402  wild drops and the wild species list
import player_guide_dungeons as PG  # noqa: E402  the vault loot and the legendary-label check

OUT = ROOT / "docs" / "player" / "held-items.html"
GUIDE = {"file": "held-items.html", "title": "Held items", "label": "Held items", "order": 33,
         "description": "Every item a Pokemon can hold and every way to get it: shops, crafting, dungeon vaults, wild "
                        "drops and wild Pokemon that carry one.",
         "generator": "tools/player_guide_held_items.py"}
HELD_TAG = "data/cobblemon/tags/item/held/is_held_item.json"
SPAWNS = "data/spawns.json"
ALPHA = "data/alpha_spoils.json"
VIA = (("shop", "Shops"), ("craft", "Crafting"), ("vault", "Dungeon vaults"), ("drop", "Wild drops"),
       ("carried", "Carried by wild Pokemon"), ("alpha", "Alpha spoils"), ("none", "No source"))
RECIPE_STATIONS = dict(PI.STATIONS, **{"minecraft:smelting": "furnace", "minecraft:stonecutting": "stonecutter"})
SECTIONS = (("items", "By item"), ("vaults", "Dungeon vaults"), ("none", "No source known"))
DROP_SHOW = 8                      # wild species shown before the rest fold into "and N more"

esc = player_site.esc
pretty = PI.pretty


def doc(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ the held list


def held_items(jar):
    """[item id] of cobblemon:held/is_held_item with every #tag expanded, in the tag's order, de-duplicated."""
    z = zipfile.ZipFile(jar)

    def values(tag_path):
        d = json.loads(z.read("data/cobblemon/tags/item/%s.json" % tag_path).decode("utf-8-sig"))
        return d["values"]
    out = []

    def walk(vals):
        for v in vals:
            v = v["id"] if isinstance(v, dict) else v
            if v.startswith("#cobblemon:"):
                walk(values(v[len("#cobblemon:"):]))
            elif v.startswith("#"):
                raise SystemExit("held list names tag %s, which this page does not expand" % v)
            elif v not in out:
                out.append(v)
    d = json.loads(z.read(HELD_TAG).decode("utf-8-sig"))
    walk(d["values"])
    if len(out) < 100:
        raise SystemExit("read only %d held items from %s" % (len(out), HELD_TAG))
    return out


def recipes_for(jar, want):
    """{item: [(station, [(count, ingredient)], made)]} for every jar recipe whose result is in `want`. Stops on a
    recipe type it cannot put in words."""
    z = zipfile.ZipFile(jar)
    out = {}
    for n in sorted(z.namelist()):
        if not (n.startswith("data/cobblemon/recipe/") and n.endswith(".json")):
            continue
        r = json.loads(z.read(n).decode("utf-8-sig"))
        res = r.get("result")
        res = res.get("id") if isinstance(res, dict) else (res if isinstance(res, str) else None)
        if res not in want:
            continue
        typ = r.get("type")
        if typ not in RECIPE_STATIONS:
            raise SystemExit("%s: recipe type %r is not one this page can put in words" % (n, typ))
        if typ == "cobblemon:brewing_stand":
            parts = [(1, r["bottle"]), (1, r["input"])]
        elif typ in ("minecraft:smelting", "minecraft:stonecutting"):
            parts = [(1, r["ingredient"])]
        elif "ingredients" in r:
            parts = []
            for i in r["ingredients"]:
                hit = next((k for k, (_c, p) in enumerate(parts) if p == i), None)
                if hit is None:
                    parts.append((1, i))
                else:
                    parts[hit] = (parts[hit][0] + 1, i)
        elif "pattern" in r:
            counts = {}
            for ch in "".join(r["pattern"]):
                if ch != " ":
                    counts[ch] = counts.get(ch, 0) + 1
            parts = [(counts[k], r["key"][k]) for k in sorted(counts)]
        else:
            raise SystemExit("%s: a %s recipe with no ingredients this page can read" % (n, typ))
        made = int((r.get("result") or {}).get("count") or 1) if isinstance(r.get("result"), dict) else 1
        out.setdefault(res, []).append((RECIPE_STATIONS[typ], parts, made))
    return out


class NameMap:
    """names[id] -> display name, for PI.ingredient (which indexes a dict)."""

    def __init__(self, fn):
        self.fn = fn

    def __getitem__(self, ident):
        return self.fn(ident)


def tag_name(tag):
    """"c:ingots/gold" -> "Gold Ingot (any)", "c:dusts/redstone" -> "Redstone Dust (any)": the tag path read backwards, its
    category singular. A tag items.html already words (PI.TAGS) keeps that wording."""
    if tag in PI.TAGS:
        return PI.TAGS[tag]
    path = tag.split(":")[-1]
    if "/" in path:
        cat, kind = path.split("/", 1)
        cat = cat[:-1] if cat.endswith("s") else cat
        return "%s %s (any)" % (pretty(kind), pretty(cat))
    return pretty(path) + " (any)"


def ingredient(names, count, part):
    """One ingredient in words, as items.html words it (PI.ingredient) but with readable tag names."""
    if isinstance(part, list):  # any one of these
        return " or ".join(ingredient(names, count, p) for p in part)
    if "item" in part:
        what = names(part["item"])
    elif "tag" in part:
        what = tag_name(part["tag"])
    else:
        raise SystemExit("an ingredient this page cannot put in words: %r" % (part,))
    return "%d %s" % (count, what) if count > 1 else what


def ingredient_ids(parts):
    ids = set()
    for _c, p in parts:
        for q in (p if isinstance(p, list) else [p]):
            if "item" in q:
                ids.add(q["item"])
    return ids


# ------------------------------------------------------------------------------------------------ vaults


def stack_options(s):
    """[(item, chance a chest holds it from this stack, count)] for one loot stack."""
    chance = s.get("chance", 1)
    if "one_of" in s:
        total = sum(o["weight"] for o in s["one_of"])
        return [(o["item"], chance * o["weight"] / total, o.get("count", 1)) for o in s["one_of"]]
    return [(s["item"], chance, s.get("count", 1))]


def vault_chances(dungeons, bands, held):
    """[{dungeon, name, kind, vault, chests, rows: {band: {item: (chance, counts)}}}] for the held items in every vault
    and bank vault, from the dungeon guide's own model. An item in two stacks of one chest combines as 1-(1-p)(1-q)."""
    out = []
    for x in dungeons:
        for v in x["vaults"]:
            rows = {}
            for b in bands:
                miss, counts = {}, {}
                for s in v["rows"][b] or []:
                    for item, p, count in stack_options(s):
                        if item in held and p > 0:
                            miss[item] = miss.get(item, 1.0) * (1.0 - p)
                            counts.setdefault(item, []).append(count)
                if miss:
                    rows[b] = {i: (1.0 - m, counts[i]) for i, m in miss.items()}
            if rows:
                out.append({"dungeon": x["id"], "dname": x["name"], "kind": v["kind"], "vault": v["name"],
                            "chests": v["chests"], "rows": rows})
    return out


# ------------------------------------------------------------------------------------------------ the model


def carried(species_stems, dex):
    """{item: {stem: sorted percentages}} from data/spawns.json held_items, for the species the region map lists and
    that the jar does not label legendary-class. Also the number of species withheld by the label."""
    out, withheld = {}, set()
    for e in doc(SPAWNS)["entries"]:
        for h in e.get("held_items") or []:
            stem = PG.compact(e["species"])
            if stem not in species_stems:
                continue
            if dex.is_legend(stem):
                withheld.add(stem)
                continue
            out.setdefault(h["item"], {}).setdefault(stem, set()).add(float(h["percentage"]))
    return {i: {s: sorted(p) for s, p in d.items()} for i, d in out.items()}, withheld


def collect(jar_path=None):
    jar = PB.find_jar(jar_path)
    held = held_items(jar)
    hs = set(held)
    mk = doc("data/markets.json")
    im = PI.collect(jar_path)
    dm = PD.collect(jar_path)
    gm = PG.collect(jar_path)
    dex = gm["dex"]
    names = PI.Names(jar, mk)
    crafts = recipes_for(jar, hs)
    # the dungeon guide's rule: a species the jar labels legendary, mythical, ultra_beast or paradox is never named, even
    # when the region map lists it as wild (the map's pools do, 2026-10-12: Buzzwole and Pheromosa on long_isle_south)
    legend = {m["sp"] for m in dm["mons"] if dex.is_legend(m["sp"].split()[0])}
    mons = [m for m in dm["mons"] if m["sp"] not in legend]
    wild_stems = {m["sp"].split()[0] for m in mons}
    carry, withheld = carried(wild_stems, dex)
    withheld |= {sp.split()[0] for sp in legend}
    alpha = doc(ALPHA)["type_tables"]
    gems = {alpha["gem"].replace("<type>", t): t for t in alpha["types"]}
    vaults = vault_chances(gm["dungeons"], gm["nb"], hs)
    by_vault = {}
    for v in vaults:
        for b, row in v["rows"].items():
            for item, (p, counts) in row.items():
                by_vault.setdefault(item, {}).setdefault((v["dungeon"], v["vault"]), {"v": v, "bands": {}})["bands"][b] = (p, counts)
    stem_name = {m["sp"].split()[0]: m["name"] for m in mons}
    items = []
    for item in held:
        shop = list(im["buy"].get(item, []))
        barter = [b for b in im["barter"] if b["sell"]["id"] == item]
        drops = [(mon, d) for mon, d in dm["items"].get(item, []) if mon["sp"] not in legend]
        rec = {"item": item, "shop": shop, "barter": barter, "craft": crafts.get(item, []),
               "vault": sorted(by_vault.get(item, {}).values(), key=lambda e: (e["v"]["dname"], e["v"]["vault"])),
               "drop": sorted(drops, key=lambda md: (-md[1]["chance"], md[0]["name"].lower())),
               "carried": sorted(((stem_name[s], ps) for s, ps in carry.get(item, {}).items()), key=lambda t: t[0].lower()),
               "alpha": gems.get(item)}
        rec["via"] = [k for k, _t in VIA[:-1] if (shop or barter if k == "shop" else rec[k])]
        items.append(rec)
    names_all = {i: names(i) for i in held}
    for r in items:
        for _st, parts, _m in r["craft"]:
            for ing in ingredient_ids(parts):
                names_all.setdefault(ing, names(ing))
        for b in r["barter"]:
            for g in b["give"]:
                names_all.setdefault(g["id"], names(g["id"]))
    return {"items": items, "names": names_all, "name_fn": names, "vaults": vaults, "bands": gm["nb"],
            "jar": jar.name, "withheld": sorted(withheld), "badges": im["badges"], "drop_method": dm["method"],
            "crafts_n": len(crafts)}


# ------------------------------------------------------------------------------------------------ render


def pct_text(p):
    return PG.pct_text(p)


def count_text(counts):
    flat = sorted({PG.count_text(c) for c in counts})
    return "" if flat == ["1"] else " (%s)" % " or ".join(flat)


def shop_lis(r, m):
    lis = []
    srcs = sorted(r["shop"], key=lambda s: (s.get("price") is None, s.get("price") or 0, PI.where_words(s)))
    for s in srcs:
        lis.append('<li data-src="shop">%s, %s</li>' % (esc(PI.where_words(s)), esc(PI.price_words(s))))
    for b in r["barter"]:
        give = " and ".join("%d %s" % (g["count"], m["names"][g["id"]]) for g in b["give"])
        lis.append('<li data-src="barter">Barter in %s (%s): give %s for %s</li>'
                   % (esc(b["town"]), esc(b["seller"]), esc(give),
                      "one" if b["sell"]["count"] == 1 else str(b["sell"]["count"])))
    return lis


def craft_lis(r, m):
    lis = []
    for st, parts, made in r["craft"]:
        what = " + ".join(ingredient(m["name_fn"], c, p) for c, p in parts)
        lis.append('<li data-src="craft">%s: %s%s</li>' % (esc(st.capitalize()), esc(what),
                                                         esc(" (makes %d)" % made) if made > 1 else ""))
    return lis


def vault_lis(r):
    lis = []
    for e in r["vault"]:
        v = e["v"]
        bands = ", ".join("band %d %s%s" % (b, pct_text(p), count_text(c)) for b, (p, c) in sorted(e["bands"].items()))
        lis.append('<li data-src="vault"><a href="dungeons.html#%s">%s</a>, %s%s: %s per chest</li>'
                   % (esc(PG.slug(v["dungeon"])), esc(v["dname"]), esc(v["vault"]),
                      " (bank vault, code lock)" if v["kind"] == "bank_vault" else "", esc(bands)))
    return lis


def drop_lis(r):
    drops = r["drop"]
    if not drops:
        return []

    def li(mon, d):
        return ('<li data-src="drop"><a href="drops.html#%s">%s</a>%s: %s</li>'
                % (esc(PD.anchor("item-", r["item"])), esc(mon["name"]), esc(PD.count_words(d)),
                   esc(PD.chance_words(d["chance"]))))
    shown = "".join(li(mon, d) for mon, d in drops[:DROP_SHOW])
    rest = drops[DROP_SHOW:]
    if not rest:
        return [shown]
    more = "".join(li(mon, d) for mon, d in rest)
    return [shown, '<li data-src="drop"><details><summary>and %d more wild Pokemon</summary><ul>%s</ul></details></li>'
            % (len(rest), more)]


def carried_lis(r):
    if not r["carried"]:
        return []
    parts = []
    for name, ps in r["carried"]:
        said = "%g%%" % ps[0] if len(ps) == 1 else "%g%% to %g%%" % (ps[0], ps[-1])
        parts.append("%s (%s of appearances)" % (name, said))
    return ['<li data-src="carried">Sometimes held by a wild %s</li>' % esc("; ".join(parts))]


def alpha_lis(r):
    if not r["alpha"]:
        return []
    return ['<li data-src="alpha">Paid by a wild alpha %s-type Pokemon when you defeat it (the stronger Pokemon marked on '
            'the region map)</li>' % esc(pretty(r["alpha"]))]


def item_row(r, m):
    nm = m["names"][r["item"]]
    lis = shop_lis(r, m) + craft_lis(r, m) + vault_lis(r) + drop_lis(r) + carried_lis(r) + alpha_lis(r)
    via = r["via"] or ["none"]
    who = [mon["name"] for mon, _d in r["drop"]] + [n for n, _p in r["carried"]] + [e["v"]["dname"] for e in r["vault"]]
    words = " ".join([nm, r["item"]] + who + ["via-%s" % v for v in via]).lower()
    cell = "<ul>%s</ul>" % "".join(lis) if lis else '<p class="none">No source known to this guide.</p>'
    return ('<tr data-held data-name="%s"><td>%s<span class="id">%s</span></td><td>%s</td></tr>'
            % (esc(words), esc(nm), esc(r["item"]), cell))


def render_items(m):
    rows = "".join(item_row(r, m) for r in sorted(m["items"], key=lambda r: (m["names"][r["item"]].lower(), r["item"])))
    return ('<section %s><h2>By item</h2><p>Every held item, A to Z. Prices are what the shop screen shows; the wild '
            'drop chances are per defeat. For what a shop or the bank pays, see <a href="items.html">Items and '
            'money</a>; for every wild drop, <a href="drops.html">What wild Pokemon drop</a>; for the dungeons, '
            '<a href="dungeons.html">Dungeons</a>.</p><div class="wide"><table><thead><tr><th>Item</th>'
            '<th>Where to get it</th></tr></thead><tbody>%s</tbody></table></div></section>'
            % (player_site.section_attr("items"), rows))


def render_vaults(m):
    nm = m["names"]
    by_dungeon = {}
    for v in m["vaults"]:
        by_dungeon.setdefault((v["dname"], v["dungeon"]), []).append(v)
    parts = []
    for (dname, did), vs in sorted(by_dungeon.items()):
        for v in vs:
            rows = []
            for b in m["bands"]:
                row = v["rows"].get(b)
                if not row:
                    continue
                cells = "; ".join("%s%s %s" % (nm[i], count_text(c), pct_text(p))
                                  for i, (p, c) in sorted(row.items(), key=lambda kv: (-kv[1][0], nm[kv[0]].lower())))
                rows.append('<tr data-held data-name="%s"><td class="n">%d</td><td>%s</td></tr>'
                            % (esc(" ".join([dname, v["vault"], cells]).lower()), b, esc(cells)))
            parts.append('<h3><a href="dungeons.html#%s">%s</a>: %s%s</h3><p class="small">%d chests, each rolled on its '
                         'own; the chance is that one chest holds the item.</p><div class="wide"><table><thead><tr>'
                         '<th class="n">Band</th><th>Held items one chest may hold, and the chance</th></tr></thead>'
                         '<tbody>%s</tbody></table></div>'
                         % (esc(PG.slug(did)), esc(dname), esc(v["vault"]),
                            " (bank vault, code lock)" if v["kind"] == "bank_vault" else "", v["chests"], "".join(rows)))
    return ('<section %s><h2>Dungeon vaults</h2><p>Held items in each dungeon\'s vault, by band. A vault chest holds '
            'other things too (balls, candies, berries); only held items are listed.</p>%s</section>'
            % (player_site.section_attr("vaults"), "".join(parts)))


def render_none(m):
    nm = m["names"]
    none = sorted((r for r in m["items"] if not r["via"] and not r["barter"]), key=lambda r: nm[r["item"]].lower())
    lis = "".join('<li data-held data-name="%s">%s</li>' % (esc((nm[r["item"]] + " via-none").lower()), esc(nm[r["item"]]))
                  for r in none)
    only = sorted((r for r in m["items"] if r["via"] == ["craft"] and not r["barter"]), key=lambda r: nm[r["item"]].lower())
    olis = "".join('<li data-held data-name="%s">%s</li>' % (esc((nm[r["item"]] + " craft only").lower()), esc(nm[r["item"]]))
                   for r in only)
    return ('<section %s><h2>No source known</h2><p>These %d held items have no shop, recipe, vault, drop or wild carrier '
            'on this guide. That does not mean they are nowhere: anything you can only find in the world is left out of '
            'the guides on purpose.</p><ul>%s</ul><h3>Only a recipe gives these</h3><p>%d items have no shop, vault, drop '
            'or wild carrier, only a crafting recipe (see their rows under By item).</p><ul>%s</ul></section>'
            % (player_site.section_attr("none"), len(none), lis, len(only), olis))


def chips():
    def chip(k, t):
        return ('<button type="button" data-fill="via-%s" data-fill-for="find" aria-pressed="false">%s</button>'
                % (esc(k), esc(t)))
    return '<div class="filter chips" aria-label="Show one kind of source">%s</div>' % "".join(chip(k, t) for k, t in VIA)


def render(m):
    n = len(m["items"])
    nsrc = sum(1 for r in m["items"] if r["via"] or r["barter"])
    body = ('<main><h1>Held items</h1><p class="lead">Every item a Pokemon can hold in battle (%d), and every way this '
            'guide knows to get one. Search by item, or pick a kind of source.</p>%s%s%s%s%s%s'
            '<section id="not-covered"><h2>What this page leaves out</h2><ul>'
            '<li>Items you can only find, win or be given somewhere in the world: those are left for you to discover, '
            'so an item whose only source is one shows here as having none.</li>'
            '<li>Recipes added by another mod: only Cobblemon\'s own recipes are read.</li>'
            '<li>What each item does in battle: Cobblemon\'s item descriptions say.</li>'
            '<li>What happens in a running game: chances are worked out from the data, not counted in play. Where the '
            'game differs, the game is right: say so.</li></ul></section></main>'
            % (n, player_site.filter_nav(SECTIONS, label="Show one part"),
               player_site.search_box("[data-held]", "Find a held item", "e.g. Leftovers, or a dungeon"), chips(),
               render_items(m), render_vaults(m), render_none(m)))
    sources = ('<p class="src">From the held-item list in %s, the shop and Mart data of the items page, data/dungeons.json '
               'vault loot, the wild drop tables of the drops page, data/spawns.json held items and '
               'data/alpha_spoils.json.</p>' % esc(m["jar"]))
    return player_site.page(GUIDE, body, body_class="page-held", not_covered_href="#not-covered", sources_html=sources)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--jar", help="the Cobblemon 1.8 jar (default: the offline snapshot's mods folder)")
    p.add_argument("--check", action="store_true", help="regenerate in memory; exit 1 if the page differs or its "
                                                        "guides.json entry is not current")
    a = p.parse_args(argv)
    model = collect(a.jar)
    text = render(model)
    out = Path(a.out)
    entry = GUIDE if out.resolve() == OUT.resolve() else None  # a page written elsewhere is not the site's
    its = model["items"]
    none = sum(1 for r in its if not r["via"] and not r["barter"])
    counts = "%d held items, %d with a source, %d without" % (len(its), len(its) - none, none)
    if a.check:
        ok, why = player_site.check(out, text, entry)
        if not ok:
            print("%s is %s: run python tools/player_site.py" % (out, why))
            return 1
        print("%s is current (%s)" % (out, counts))
        return 0
    did = player_site.write(out, text, entry)
    print("%s %s: %s, %d bytes" % (did, out, counts, len(text.encode("utf-8"))))
    if model["withheld"]:
        print("  species withheld by the jar's legendary labels (wild per the region map): %s" % ", ".join(model["withheld"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
