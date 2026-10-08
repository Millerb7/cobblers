#!/usr/bin/env python
"""The players' drop guide, docs/player/drops.html: for every Pokemon a player can meet in the wild, what it drops when
defeated and how often; and, the other way round, for every item that is dropped, which wild Pokemon drop it.

  python tools/player_guide_drops.py            # write docs/player/drops.html and register it in guides.json
  python tools/player_guide_drops.py --check    # regenerate in memory; exit 1 if the page or its entry is stale
  python tools/player_guide_drops.py --out F    # write elsewhere (not the site's page, not registered)

WHY A PAGE OF ITS OWN, not a section of items.html. items.html lists an item only through a source a player can use
on purpose (a shop, a barter, the bank, a recipe); 607 Pokemon and their ~1,400 drop lines would bury that dictionary,
and the site is one generator per page (tools/player_site.py runs each manifest entry's generator once). So this page
links to items.html instead of repeating it: where the bank or the Produce Buyer takes a dropped item, the item row
says so and links to items.html#sell or #money, with no price here.

WHICH POKEMON: exactly those the region map lists, from tools/player_guide_map.py wild_species() (the compiled spawn
pools, less heart entries, Mega den rows, habitat pools and land pools with no dry ground). Nothing is listed from a
hand list, so a legendary, mythical, dungeon boss or story-only species is absent here for the same reason it is absent
from the map: it is in no pool the map reads. Each Pokemon links to region-map.html#pokemon=<species>.

WHAT EACH ONE DROPS: the species' `drops` table in Cobblemon-fabric-1.8.0+1.21.1.jar (data/cobblemon/species/), the
form's own table where a form carries one (an "alolan" spawn reads the form whose aspects include "alolan"), with the
COBBLEVERSE datapack's species_additions `drops` REPLACING the jar's where present (24 species, read 2026-10-08:
Applin, Litleo, Stunky and the rest). Both are read, never copied. Checked once, by hand, not by this tool: the
Cobbleverse pack's 14 full species files and Mega Showdown's 53 differ from the jar's drops only for Kyurem and Calyrex;
no other mod jar or datapack in the 2026-10-05 server snapshot carries a species drop table.

HOW A TABLE ROLLS (DropTable.getDrops and ItemDropEntry in the jar, read with javap 2026-10-08):
  - `amount` is an IntRange; one value is drawn from it per defeat (a bare number n is n..n).
  - entries whose `quantity` (default 1) exceeds the amount are dropped from the pool first.
  - then, while the picked total is below the amount and the pool is not empty: ONE pass over the pool in order takes
    the FIRST entry whose roll succeeds (nextFloat() * 100 < `percentage`, default 100). A success adds the entry and
    its quantity to the total and removes it once chosen `maxSelectableTimes` (default 1) times; a pass with no
    success adds 1 to the total. After a success, every entry whose quantity exceeds what is left also leaves.
  - each chosen entry drops one stack of `quantityRange` (a uniform draw, so "0-1" is nothing half the time) or, with
    no range, `quantity` items.
So a 100% entry is always taken first and the rest share what is left, in order. chosen() below computes the chance of
each set of entries being taken, EXACTLY over that algorithm (no sampling); the page's "about 1 in N" for an item is
the chance that some entry naming it is taken with a stack that is not empty (Snorlax names Apple twice). Each
percentage is the game's own roll; tests/test_player_guide_drops.py checks the page against a simulation of it.
A table this tool cannot put in words (an entry with no item, maxSelectableTimes above 1, an unknown key) stops it.

Where the items land: modpack/config/cobblemon/main.json defaultDropItemMethod (read here, worded by DROP_METHOD).

Not checked in a running game: the rates are the jar's tables run through the algorithm above; no defeat was counted.
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import re
import sys
import zipfile
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import player_site  # noqa: E402  the shared header, footer, filter, search and manifest of docs/player/
import player_guide_battles as PB  # noqa: E402  the Cobblemon jar finder
import player_guide_map as PM  # noqa: E402  which Pokemon the region map lists, and their names

OUT = ROOT / "docs" / "player" / "drops.html"
GUIDE = {"file": "drops.html", "title": "What wild Pokemon drop", "label": "Drops", "order": 35,
         "description": "For every Pokemon you can meet in the wild, what it drops when you defeat it and how often; "
                        "and for every dropped item, which Pokemon to look for.",
         "generator": "tools/player_guide_drops.py"}
DP_NAME = "COBBLEVERSE-DP-v31.zip"
# the vanilla client jar carries the game's English item names (the Cobblemon jar has only its own); the same default
# as tools/economy_audit.py DEFAULT_VANILLA
VANILLA_JAR = "C:/Users/wnd/AppData/Roaming/ModrinthApp/meta/versions/1.21.1-0.19.5/1.21.1-0.19.5.jar"
COBBLEMON_MAIN = ROOT / "modpack" / "config" / "cobblemon" / "main.json"
DROP_METHOD = {"on-entity": "Drops fall to the ground where the Pokemon was.",
               "on-player": "Drops fall to the ground at your feet.",
               "to-inventory": "Drops go straight into your inventory (or fall at your feet when it is full)."}
ENTRY_KEYS = {"item", "percentage", "quantity", "quantityRange", "maxSelectableTimes"}
SECTIONS = (("pokemon", "By Pokemon"), ("items", "By item"))

esc = player_site.esc


# ------------------------------------------------------------------------------------------------ inputs


def find_dp(explicit=None):
    """The COBBLEVERSE datapack zip: --dp, COBBLERS_COBBLEVERSE_DP, the patched runtime copy in build/cobbleverse/, the
    main checkout's COBBLEVERSE/datapacks/, then an offline server snapshot's datapacks/. Riding is all the patch
    changes (tools/patch_cobbleverse_riding.py), so every copy carries the same drops."""
    cands = [explicit, os.environ.get("COBBLERS_COBBLEVERSE_DP"), str(ROOT / "build" / "cobbleverse" / DP_NAME),
             str(ROOT / "COBBLEVERSE" / "datapacks" / DP_NAME)]
    cands += sorted(glob("C:/Users/wnd/Documents/cobblers-local/server-snapshot-*/datapacks/" + DP_NAME), reverse=True)
    for c in cands:
        if c and Path(c).is_file():
            return Path(c)
    raise SystemExit("no %s: pass --dp, or set COBBLERS_COBBLEVERSE_DP" % DP_NAME)


def find_vanilla(explicit=None):
    for c in (explicit, os.environ.get("COBBLERS_VANILLA_JAR"), VANILLA_JAR):
        if c and Path(c).is_file():
            return Path(c)
    raise SystemExit("no vanilla 1.21.1 jar for the item names: pass --vanilla-jar, or set COBBLERS_VANILLA_JAR")


def _json(z, name):
    return json.loads(z.read(name).decode("utf-8-sig"))


def species_tables(jar, dp):
    """{species file stem: {"drops": table or None, "forms": {aspect: table}}} from the jar, with the datapack's
    species_additions `drops` replacing the species-level table."""
    out = {}
    with zipfile.ZipFile(jar) as z:
        for n in z.namelist():
            m = re.fullmatch(r"data/cobblemon/species/[^/]+/([a-z0-9_]+)\.json", n)
            if not m:
                continue
            d = _json(z, n)
            forms = {}
            for f in d.get("forms") or []:
                if "drops" in f:
                    for asp in f.get("aspects") or []:
                        forms[asp] = f["drops"]
            out[m.group(1)] = {"drops": d.get("drops"), "forms": forms, "from": "jar"}
    with zipfile.ZipFile(dp) as z:
        for n in z.namelist():
            if not re.fullmatch(r"data/[^/]+/species_additions/.+\.json", n):
                continue
            d = _json(z, n)
            if "drops" not in d:
                continue
            if any("drops" in f for f in d.get("forms") or [] if isinstance(f, dict)):
                raise SystemExit("%s: a species_additions form drop table; this page reads only species-level ones" % n)
            stem = str(d.get("target", "")).split(":")[-1]
            if stem not in out:
                raise SystemExit("%s targets %r, which the jar has no species file for" % (n, d.get("target")))
            out[stem]["drops"] = d["drops"]
            out[stem]["from"] = "datapack"
    return out


def table_for(tables, sp):
    """(table, source words) for a compiled `pokemon` string: "rattata", "sandshrew alolan"."""
    parts = sp.split()
    rec = tables.get(parts[0])
    if rec is None:
        raise SystemExit("the region map lists %r and the jar has no species file %s.json" % (sp, parts[0]))
    for asp in parts[1:]:
        if "=" in asp:
            raise SystemExit("%r: a property this page cannot match to a form" % sp)
        if asp in rec["forms"]:
            return rec["forms"][asp], "jar form"
    return rec["drops"], rec["from"]


def item_names(jar, vanilla):
    lang = {}
    for path, key in ((vanilla, "assets/minecraft/lang/en_us.json"), (jar, "assets/cobblemon/lang/en_us.json")):
        with zipfile.ZipFile(path) as z:
            lang.update(_json(z, key))
    guessed = set()

    def known(ident):
        ns, _, p = ident.partition(":")
        return any(k in lang for k in ("item.%s.%s" % (ns, p), "block.%s.%s" % (ns, p)))

    def name(ident):
        ns, _, p = ident.partition(":")
        for k in ("item.%s.%s" % (ns, p), "block.%s.%s" % (ns, p)):
            if k in lang:
                return lang[k]
        guessed.add(ident)
        return " ".join(w.capitalize() for w in p.split("_"))
    return name, guessed, known


# ------------------------------------------------------------------------------------------------ the roll


def _range(v, what):
    if isinstance(v, int):
        return v, v
    if isinstance(v, str) and re.fullmatch(r"\d+-\d+", v):
        lo, hi = (int(x) for x in v.split("-"))
        if lo <= hi:
            return lo, hi
    if isinstance(v, str) and v.isdigit():
        return int(v), int(v)
    raise SystemExit("%s %r is not a range this page reads" % (what, v))


def parse(table, where):
    """(amount (lo, hi), [entry]) with every default filled in; stops on a shape it cannot word."""
    lo, hi = _range(table.get("amount", 1), "%s amount" % where)
    ents = []
    for e in table.get("entries") or []:
        extra = set(e) - ENTRY_KEYS
        if extra or "item" not in e:
            raise SystemExit("%s: a drop entry this page cannot put in words: %r" % (where, e))
        if int(e.get("maxSelectableTimes", 1)) != 1:
            raise SystemExit("%s: maxSelectableTimes %r; this page words only entries chosen at most once" % (where, e))
        q = int(e.get("quantity", 1))
        stack = _range(e["quantityRange"], "%s quantityRange" % where) if "quantityRange" in e else (q, q)
        ents.append({"item": e["item"], "p": min(1.0, max(0.0, float(e.get("percentage", 100.0)) / 100.0)),
                     "quantity": q, "stack": stack})
    return (lo, hi), ents


def chosen(amount, ents):
    """{frozenset of entry indices: chance that exactly those entries are chosen in one defeat}, exactly, by
    DropTable.getDrops (see the module docstring). Sets, not one chance per entry, because a table may name one item
    twice (Snorlax's two Apple entries) and "at least one Apple" needs both together."""
    q = [e["quantity"] for e in ents]
    p = [e["p"] for e in ents]

    def one(amt):
        @functools.lru_cache(maxsize=None)
        def go(pool, picked):
            """{set chosen from here on: chance}, from a pass over `pool` with `picked` already counted."""
            out = {}

            def add(prefix, chance, sub):
                for s, c in sub.items():
                    out[prefix | s] = out.get(prefix | s, 0.0) + chance * c
            miss = 1.0
            for i in pool:
                hit = miss * p[i]
                miss *= 1.0 - p[i]
                if hit <= 0:
                    continue
                now = picked + q[i]
                rest = tuple(j for j in pool if j != i and q[j] <= amt - now)
                add(frozenset([i]), hit, go(rest, now) if now < amt and rest else {frozenset(): 1.0})
            if miss > 0:
                add(frozenset(), miss, go(pool, picked + 1) if picked + 1 < amt else {frozenset(): 1.0})
            return out
        start = tuple(i for i in range(len(ents)) if q[i] <= amt)
        return go(start, 0) if start and amt > 0 else {frozenset(): 1.0}

    lo, hi = amount
    total = {}
    for amt in range(lo, hi + 1):
        for s, c in one(amt).items():
            total[s] = total.get(s, 0.0) + c / (hi - lo + 1)
    return total


def lines(table, where):
    """[{item, chance (at least one of it in a defeat), lo, hi (how many when there are some), mean (per defeat)}],
    one line per item (entries naming the same item are added together), in the table's order."""
    if not table:
        return []
    amount, ents = parse(table, where)
    sets = chosen(amount, ents)

    def empty(e):  # chance the entry's stack is empty
        slo, shi = e["stack"]
        return (min(shi, 0) - slo + 1) / (shi - slo + 1) if slo <= 0 else 0.0
    out = []
    for item in dict.fromkeys(e["item"] for e in ents):
        idx = [i for i, e in enumerate(ents) if e["item"] == item]
        chance = 0.0
        for s, c in sets.items():
            none = 1.0
            for i in idx:
                if i in s:
                    none *= empty(ents[i])
            chance += c * (1.0 - none) if any(i in s for i in idx) else 0.0
        if chance <= 1e-12:
            continue
        mean = sum(c * sum((ents[i]["stack"][0] + ents[i]["stack"][1]) / 2.0 for i in idx if i in s)
                   for s, c in sets.items())
        out.append({"item": item, "chance": min(chance, 1.0), "lo": min(max(ents[i]["stack"][0], 1) for i in idx),
                    "hi": sum(ents[i]["stack"][1] for i in idx), "mean": mean})
    return out


# ------------------------------------------------------------------------------------------------ the model


def collect(jar_path=None, dp_path=None, vanilla_path=None, species=None):
    jar = PB.find_jar(jar_path)
    dp = find_dp(dp_path)
    name, guessed, known = item_names(jar, find_vanilla(vanilla_path))
    tables = species_tables(jar, dp)
    species = species if species is not None else PM.wild_species()
    mons, void = [], []
    for sp in sorted(species, key=lambda s: (species[s].lower(), s)):
        table, src = table_for(tables, sp)
        ds = lines(table, sp)
        # a minecraft: id vanilla does not have is no item (upstream typos: "minecraft:sun_stone" for cobblemon's).
        # It still takes its turn in the roll, so the chances above count it; it is only left off the page.
        void += [(sp, d["item"]) for d in ds if d["item"].startswith("minecraft:") and not known(d["item"])]
        ds = [d for d in ds if not (d["item"].startswith("minecraft:") and not known(d["item"]))]
        mons.append({"sp": sp, "name": species[sp], "from": src, "drops": ds, "void": [i for s, i in void if s == sp]})
    items = {}
    for m in mons:
        for d in m["drops"]:
            items.setdefault(d["item"], []).append((m, d))
    names = {i: name(i) for i in items}
    import player_guide_items as PI  # the items page's own sell list and crates, so the links cannot disagree with it
    im = PI.collect(jar_path)
    sold = {s["item"] for s in im["sell"]}
    crated = {i for c in im["produce"]["crates"] for i in c.get("items") or []}
    method = json.loads(COBBLEMON_MAIN.read_text(encoding="utf-8")).get("defaultDropItemMethod")
    if method not in DROP_METHOD:
        raise SystemExit("%s defaultDropItemMethod %r is not one this page can put in words" % (COBBLEMON_MAIN, method))
    return {"mons": mons, "items": items, "names": names, "guessed": sorted(guessed & set(items)), "sold": sold,
            "crated": crated, "method": method, "jar": jar.name, "dp": dp.name, "void": void}


# ------------------------------------------------------------------------------------------------ render


def chance_words(p):
    """A per-defeat chance in plain words: "every defeat", "about 1 in 40 defeats", "about 3 in 4 defeats"."""
    if p >= 0.995:
        return "every defeat"
    if p >= 0.9:
        return "nearly every defeat"
    if p < 0.1:
        return "about 1 in %d defeats" % round(1 / p)
    for b in range(2, 21):
        a = round(p * b)
        if 1 <= a < b and abs(a / b - p) <= 0.1 * min(p, 1 - p):
            return "about %d in %d defeats" % (a, b)
    return "about %d in 100 defeats" % round(p * 100)


def pct(p):
    return "%s%%" % ("%.3g" % (p * 100))


def anchor(prefix, ident):
    return prefix + re.sub(r"[^a-z0-9]+", "-", ident.lower()).strip("-")


def count_words(d):
    return "" if d["hi"] == 1 else " (%d)" % d["hi"] if d["lo"] == d["hi"] else " (%d-%d)" % (d["lo"], d["hi"])


def render_mons(m):
    rows = []
    for mon in m["mons"]:
        ds = sorted(mon["drops"], key=lambda d: (-d["chance"], m["names"][d["item"]].lower()))
        lis = "".join('<li data-item="%s" data-chance="%.6f"><a href="#%s">%s</a>%s: %s <span class="pct">%s</span></li>'
                      % (esc(d["item"]), d["chance"], anchor("item-", d["item"]), esc(m["names"][d["item"]]),
                         esc(count_words(d)), esc(chance_words(d["chance"])), esc(pct(d["chance"])))
                      for d in ds)
        none = ("Drops nothing: its drop table names an item the game does not have." if mon["void"]
                else "Drops nothing.")
        what = "<ul>%s</ul>" % lis if lis else "<p>%s</p>" % none
        words = " ".join([mon["name"], mon["sp"]] + [m["names"][d["item"]] for d in ds]).lower()
        rows.append('<tr id="%s" data-drop data-sp="%s" data-name="%s"><td><b>%s</b> <a class="where" '
                    'href="region-map.html#pokemon=%s">where</a></td><td>%s</td></tr>'
                    % (anchor("mon-", mon["sp"]), esc(mon["sp"]), esc(words), esc(mon["name"]),
                       esc(mon["sp"].replace(" ", "%20")), what))
    return ('<section %s><h2>By Pokemon</h2><p>Every Pokemon you can meet in the wild, A to Z, and what it drops. '
            '"Where" opens it on the region map; an item name jumps to the Pokemon that drop it.</p>'
            '<div class="wide"><table><thead><tr><th>Pokemon</th><th>Drops, and how often</th></tr></thead>'
            '<tbody>%s</tbody></table></div></section>' % (player_site.section_attr("pokemon"), "".join(rows)))


def render_items(m):
    rows = []
    for item in sorted(m["items"], key=lambda i: (m["names"][i].lower(), i)):
        by = sorted(m["items"][item], key=lambda md: (-md[1]["chance"], md[0]["name"].lower()))
        lis = "".join('<li data-sp="%s"><a href="#%s">%s</a>%s: %s</li>'
                      % (esc(mon["sp"]), anchor("mon-", mon["sp"]), esc(mon["name"]), esc(count_words(d)),
                         esc(chance_words(d["chance"]))) for mon, d in by)
        also = []
        if item in m["sold"]:
            also.append('<a href="items.html#sell">the bank buys it</a>')
        if item in m["crated"]:
            also.append('<a href="items.html#money">the Produce Buyer takes it by the crate</a>')
        note = '<p class="also">Also: %s.</p>' % " and ".join(also) if also else ""
        rows.append('<tr id="%s" data-drop data-item="%s" data-name="%s"><td>%s<span class="id">%s</span>%s</td>'
                    '<td><ul>%s</ul></td></tr>'
                    % (anchor("item-", item), esc(item), esc(("%s %s" % (m["names"][item], item)).lower()),
                       esc(m["names"][item]), esc(item), note, lis))
    return ('<section %s><h2>By item</h2><p>Every item a wild Pokemon drops, A to Z, with the Pokemon that drop it, '
            'likeliest first. Prices are on <a href="items.html">Items and money</a>.</p><div class="wide"><table>'
            '<thead><tr><th>Item</th><th>Dropped by</th></tr></thead><tbody>%s</tbody></table></div></section>'
            % (player_site.section_attr("items"), "".join(rows)))


def render(m):
    n_drop = sum(1 for mon in m["mons"] if mon["drops"])
    body = ('<main><h1>What wild Pokemon drop</h1><p class="lead">Defeat a wild Pokemon and it may drop items. Here is '
            'what each of the %d Pokemon you can meet in the wild drops, and which Pokemon to look for when you want '
            'an item. Search by Pokemon or item.</p>'
            '<div class="box"><p>How to read it: "Bone (1-2): about 1 in 4 defeats" means that in about one defeat in '
            'four you get one or two Bones. Each defeat is rolled on its own, and a Pokemon can drop several things '
            'at once. %s</p></div>%s%s%s%s'
            '<section id="not-covered"><h2>What this page leaves out</h2><ul>'
            '<li>Pokemon you cannot meet in the wild here, and any you only find in hidden or special places: those '
            'are left for you to discover.</li>'
            '<li>Prices: what the bank pays is on <a href="items.html#sell">Items and money</a>.</li>'
            '<li>What happens in a running game: the chances are worked out from Cobblemon\'s drop tables, not counted '
            'defeat by defeat. Where the game differs, the game is right: say so.</li></ul></section></main>'
            % (len(m["mons"]), esc(DROP_METHOD[m["method"]]),
               player_site.filter_nav(SECTIONS, label="Show one part"),
               player_site.search_box("[data-drop]", "Find a Pokemon or item", "e.g. Geodude or Bone"),
               render_mons(m), render_items(m)))
    sources = ('<p class="src">From the region map\'s wild Pokemon (%d, of which %d drop something), the drop tables in '
               '%s with the Cobbleverse datapack\'s changes (%s), and modpack/config/cobblemon/main.json.</p>'
               % (len(m["mons"]), n_drop, esc(m["jar"]), esc(m["dp"])))
    return player_site.page(GUIDE, body, body_class="page-drops", not_covered_href="#not-covered",
                            sources_html=sources)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--jar", help="the Cobblemon 1.8 jar (default: the offline snapshot's mods folder)")
    p.add_argument("--dp", help="the COBBLEVERSE datapack zip (default: see find_dp)")
    p.add_argument("--vanilla-jar", help="a Minecraft 1.21.1 jar with assets/minecraft/lang/en_us.json")
    p.add_argument("--check", action="store_true", help="regenerate in memory; exit 1 if the page differs or its "
                                                        "guides.json entry is not current")
    a = p.parse_args(argv)
    model = collect(a.jar, a.dp, a.vanilla_jar)
    text = render(model)
    out = Path(a.out)
    entry = GUIDE if out.resolve() == OUT.resolve() else None  # a page written elsewhere is not the site's
    counts = "%d Pokemon (%d drop something), %d items" % (len(model["mons"]), sum(1 for x in model["mons"]
                                                                                    if x["drops"]), len(model["items"]))
    if a.check:
        ok, why = player_site.check(out, text, entry)
        if not ok:
            print("%s is %s: run python tools/player_site.py" % (out, why))
            return 1
        print("%s is current (%s)" % (out, counts))
        return 0
    did = player_site.write(out, text, entry)
    print("%s %s: %s, %d bytes" % (did, out, counts, len(text.encode("utf-8"))))
    for sp, item in model["void"]:
        print("  left out %s's %s: no such vanilla item (an upstream typo; it never drops)" % (sp, item))
    if model["guessed"]:
        print("  named from the id (no jar name): %s" % ", ".join(model["guessed"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
