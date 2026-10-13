"""docs/player/held-items.html (tools/player_guide_held_items.py): every held item of the Cobblemon 1.8.0 jar is on the page
once, each source is the data's, an item with no source says so, and nothing secret or legendary is named.

The expectations are read by this file from the data and the jar, not from the generator's model:
  - the item list: the jar's data/cobblemon/tags/item/held/is_held_item.json with this file's own tag expansion;
  - dungeon vaults: data/dungeons.json walked here (forks and sides included), the loot of each vault from its params or
    the defaults in data/dungeon_puzzles.json / data/dungeon_extras.json, a stack's chance times the item's weight over the
    stack's weights, combined over stacks as 1-(1-p)(1-q);
  - wild drops: the drops page (docs/player/drops.html) as published, which its own test holds to a simulation of the
    game's roll; the two pages must name the same Pokemon and the same chances for every held item;
  - carried items: data/spawns.json held_items, for the species the drops page lists;
  - shops: data/markets.json sited stock at price // count; recipes: the jar's recipe files; barter: data/direct_trades.json.
Without the jar the tests that need it SKIP with the reason; none passes without reading one.

Mutation: test_the_vault_check_bites changes the GENERATOR (stack_options is told to ignore a stack's `chance`) and shows
the check, which does not call it, reports the page.
"""
from __future__ import annotations

import html
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import test_player_site_filter as FILTER  # noqa: E402
import test_player_guide_dungeons as DT  # noqa: E402  the jar finder, the legendary-name reader and the room walk

PAGE = ROOT / "docs" / "player" / "held-items.html"
DROPS = ROOT / "docs" / "player" / "drops.html"
needs_jar = DT.needs_jar
STATIONS = ("Crafting table", "Furnace", "Stonecutter", "Brewing stand", "Campfire pot")


def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _text(s):
    t = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())
    return re.sub(r"\s+([,.;:)])", r"\1", t)


@pytest.fixture(scope="module")
def raw():
    assert PAGE.is_file(), "run python tools/player_guide_held_items.py"
    return PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def zjar():
    if not DT.JAR:
        pytest.skip("no Cobblemon 1.8 jar")
    return zipfile.ZipFile(DT.JAR)


def _section(raw, key):
    m = re.search(r'<section id="%s" data-section="%s">(.*?)</section>' % (key, key), raw, re.S)
    assert m, key
    return m.group(1)


def _rows(raw):
    """{item id: {"name", "cell" (html), "lis" [text], "words"}} of the By item table."""
    out = {}
    for m in re.finditer(r'<tr data-held data-name="([^"]*)"><td>([^<]*)<span class="id">([^<]*)</span></td><td>(.*?)</td></tr>',
                         _section(raw, "items"), re.S):
        ident = html.unescape(m.group(3))
        assert ident not in out, ident
        out[ident] = {"name": html.unescape(m.group(2)), "cell": m.group(4), "words": html.unescape(m.group(1)),
                      "lis": [_text(li) for li in re.findall(r"<li[^>]*>(?:(?!<li).)*?</li>", m.group(4), re.S)]}
    return out


# ------------------------------------------------------------------------------------------------ the list


def held_ids(z):
    def vals(path):
        return json.loads(z.read("data/cobblemon/tags/item/%s.json" % path).decode("utf-8-sig"))["values"]
    out = []

    def walk(vs):
        for v in vs:
            v = v["id"] if isinstance(v, dict) else v
            if v.startswith("#cobblemon:"):
                walk(vals(v[len("#cobblemon:"):]))
            elif v not in out:
                out.append(v)
    walk(vals("held/is_held_item"))
    return out


@needs_jar
def test_the_items_are_cobblemons_held_list(raw, zjar):
    want = held_ids(zjar)
    rows = _rows(raw)
    assert set(rows) == set(want) and len(rows) == len(want) >= 100, set(rows) ^ set(want)
    assert "water gem" in " ".join(r["name"].lower() for r in rows.values())  # #cobblemon:type_gems was expanded


# ------------------------------------------------------------------------------------------------ vaults


def pct(p):
    v = p * 100
    return ("%.1f%%" % v).replace(".0%", "%") if v < 10 else "%d%%" % round(v)


def expected_vaults(held):
    """{(dungeon name, vault title): {band: {item: chance}}} for the held items, from data/dungeons.json."""
    doc = _json("data/dungeons.json")
    puz, ex1 = _json("data/dungeon_puzzles.json"), _json("data/dungeon_extras.json")
    bands = [b["band"] for b in doc["engine"]["bands"]]

    def pretty(s):
        return " ".join(w.capitalize() for w in re.split(r"[_\s-]+", str(s).split(":")[-1]) if w)

    out = {}
    for d in doc["dungeons"]:
        for r in DT._walk(d["rooms"]):
            p = r.get("params") or {}
            if r["kind"] == "vault":
                lb, title = p.get("loot_by_band") or puz["default_loot_by_band"], pretty(r.get("name") or r["id"])
            elif r["kind"] == "bank_vault":
                lb, title = p.get("loot_by_band") or ex1["bank_vault"]["default_loot_by_band"], pretty(r["id"])
            else:
                continue
            per_band = {}
            for b in bands:
                keys = sorted(int(k) for k in lb if int(k) <= b)
                miss = {}
                for s in (lb[str(keys[-1])] if keys else []):
                    ch = s.get("chance", 1)
                    opts = ([(o["item"], ch * o["weight"] / sum(x["weight"] for x in s["one_of"])) for o in s["one_of"]]
                            if "one_of" in s else [(s["item"], ch)])
                    for item, q in opts:
                        if item in held and q > 0:
                            miss[item] = miss.get(item, 1.0) * (1.0 - q)
                if miss:
                    per_band[b] = {i: 1.0 - m for i, m in miss.items()}
            if per_band:
                out[(d["name"], title)] = per_band
    return out


def page_vaults(raw):
    """{(dungeon name, vault title): {band: {item name: pct text}}} from the Dungeon vaults section."""
    out = {}
    for m in re.finditer(r"<h3><a [^>]*>([^<]*)</a>: ([^<]*?)(?: \(bank vault, code lock\))?</h3>(.*?)</table>",
                         _section(raw, "vaults"), re.S):
        bands = {}
        for tr in re.findall(r"<tr data-held[^>]*>(.*?)</tr>", m.group(3), re.S):
            band, cell = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            items = {}
            for part in _text(cell).split("; "):
                name, _, p = part.rpartition(" ")
                items[re.sub(r" \([^)]*\)$", "", name)] = p
            bands[int(_text(band))] = items
        out[(html.unescape(m.group(1)), html.unescape(m.group(2)))] = bands
    return out


def vault_problems(raw, held):
    rows = _rows(raw)
    name_to_id = {r["name"]: i for i, r in rows.items()}
    want = expected_vaults(held)
    got = page_vaults(raw)
    bad = []
    if set(got) != set(want):
        bad.append("vaults differ: %s" % sorted(set(got) ^ set(want)))
    for key, bands in want.items():
        for b, items in bands.items():
            have = {name_to_id[n]: p for n, p in got.get(key, {}).get(b, {}).items()}
            if have != {i: pct(c) for i, c in items.items()}:
                bad.append((key, b, have, {i: pct(c) for i, c in items.items()}))
    # the By item rows say the same per item
    by_item = {}
    for (dn, title), bands in want.items():
        for b, items in bands.items():
            for i, c in items.items():
                by_item.setdefault(i, set()).add((dn, title, b, pct(c)))
    for i, r in rows.items():
        seen = set()
        for li in r["lis"]:
            m = re.fullmatch(r"(.+?), (.+?)(?: \(bank vault, code lock\))?: (band .*) per chest", li)
            if m:
                for b, p in re.findall(r"band (\d+) ([\d.]+%)", m.group(3)):
                    seen.add((m.group(1), m.group(2), int(b), p))
        if seen != by_item.get(i, set()):
            bad.append(("By item row", i, sorted(seen ^ by_item.get(i, set()))[:3]))
    return bad


@needs_jar
def test_vault_chances_equal_the_dungeon_data(raw, zjar):
    held = set(held_ids(zjar))
    want = expected_vaults(held)
    assert len(want) >= 8 and sum(len(b) for b in want.values()) > 30  # non-vacuous: real vaults, real bands
    assert vault_problems(raw, held) == []


@needs_jar
def test_the_vault_check_bites(raw, zjar, monkeypatch):
    """Mutate the generator, not the data: a stack's `chance` is ignored. The check reads the dungeon data itself."""
    import player_guide_held_items as G
    real = G.stack_options

    def no_chance(s):
        return real(dict(s, chance=1))
    monkeypatch.setattr(G, "stack_options", no_chance)
    mutated = G.render(G.collect(str(DT.JAR)))
    assert vault_problems(mutated, set(held_ids(zjar)))


# ------------------------------------------------------------------------------------------------ drops and carriers


_FRESH = {}


def _fresh_drops_html():
    """The drops page as its generator renders it from today's data, not the committed file: the committed page can lag
    the data (2026-10-12 it did, and its generator could not run until the map learned `dimensions`), and this test is
    about the two pages agreeing, not about either being current (the drops test holds that)."""
    if "t" not in _FRESH:
        import player_guide_drops as PD
        _FRESH["t"] = PD.render(PD.collect())
    return _FRESH["t"]


def _drops_page():
    t = _fresh_drops_html()
    legend = DT._species()  # the held page never names these, wild or not (the dungeon guide's rule)
    legend_names = {n.lower() for e in legend.values() for n in e["names"]}
    by_item = {}
    for m in re.finditer(r'<tr id="item-[^"]*" data-drop data-item="([^"]*)"[^>]*>(.*?)</tr>', t, re.S):
        by_item[html.unescape(m.group(1))] = {
            (html.unescape(n), _text(c).strip(), w.strip())
            for n, c, w in re.findall(r'<li data-sp="[^"]*"><a href="#mon-[^"]*">([^<]*)</a>([^:<]*): ([^<]*)</li>', m.group(2))
            if html.unescape(n).lower() not in legend_names}
    mons = {html.unescape(sp): html.unescape(re.search(r"<b>([^<]*)</b>", body).group(1))
            for sp, body in re.findall(r'<tr id="mon-[^"]*" data-drop data-sp="([^"]*)"[^>]*>(.*?)</tr>', t, re.S)
            if sp.split()[0] not in legend}
    return by_item, mons


@needs_jar
def test_wild_drops_are_the_drops_pages(raw):
    by_item, _mons = _drops_page()
    rows = _rows(raw)
    n = 0
    for ident, r in rows.items():
        got = {(html.unescape(nm), _text(c).strip(), w.strip()) for nm, c, w in re.findall(
            r'<li data-src="drop"><a href="drops\.html#[^"]*">([^<]*)</a>([^:<]*): ([^<]*)</li>', r["cell"])}
        assert got == by_item.get(ident, set()), (ident, sorted(got ^ by_item.get(ident, set()))[:3])
        n += len(got)
    assert n > 100  # non-vacuous
    for ident, r in rows.items():  # the link goes to the item's own row on the drops page
        for target in re.findall(r'href="drops\.html#(item-[^"]*)"', r["cell"]):
            assert 'id="%s"' % target in _fresh_drops_html()


@needs_jar
def test_carried_items_are_the_spawn_data_for_listed_species(raw, zjar):
    lang = json.loads(zjar.read("assets/cobblemon/lang/en_us.json").decode("utf-8"))
    _by_item, mons = _drops_page()
    wild = {sp.split()[0] for sp in mons}
    want = {}
    for e in _json("data/spawns.json")["entries"]:
        stem = re.sub(r"[^a-z0-9]", "", e["species"].split(":")[-1].lower())
        for h in e.get("held_items") or []:
            if stem in wild:
                want.setdefault(h["item"], {}).setdefault(lang["cobblemon.species.%s.name" % stem], set()).add(float(h["percentage"]))
    assert len(want) >= 10
    for ident, r in _rows(raw).items():
        got = {}
        for li in r["lis"]:
            if li.startswith("Sometimes held by a wild "):
                for part in li[len("Sometimes held by a wild "):].split("; "):
                    m = re.fullmatch(r"(.+?) \(([\d.]+)%(?: to ([\d.]+)%)? of appearances\)", part)
                    got[m.group(1)] = {float(m.group(2)), float(m.group(3) or m.group(2))}
        exp = {n: {min(p), max(p)} for n, p in want.get(ident, {}).items()}
        assert got == exp, (ident, got, exp)


# ------------------------------------------------------------------------------------------------ shops, barter, recipes


def test_shop_and_barter_lines(raw):
    mk = _json("data/markets.json")
    towns = {t["id"]: t["display_name"] for t in _json("data/towns.json")["towns"]}
    for p in mk.get("places_beyond_towns") or []:
        d = _json(p["source"])
        towns.setdefault(p["town"], d.get("display_name") or d.get("name"))
    rows = _rows(raw)
    sold, never = {}, []
    for c in mk["counters"] + (mk.get("stalls") or []):
        for line in c.get("stock") or []:
            if c.get("status") == "sited":
                sold.setdefault(line["item"], set()).add("%s: %s, $%s" % (towns[c["town"]], c["category"], format(
                    int(line["price"]) // int(line.get("count") or 1), ",")))
            else:
                never.append((line["item"], c))
        for key in ("held_stock", "superseded_stock"):
            never += [(line["item"], c) for line in c.get(key) or []]
    n = 0
    for ident, r in rows.items():
        for want in sold.get(ident, set()):
            assert any(li.startswith(want) for li in r["lis"]), (ident, want)
            n += 1
        have = [li for li in r["lis"] if re.match(r"[A-Z][\w' .-]+: [^:]+, \$[\d,]+$", li) and "Barter" not in li]
        for li in have:
            assert any(li.startswith(w) for w in sold.get(ident, set())) or "Poke Marts" in li or "Every Poke Mart" in li, (ident, li)
    assert n > 10
    for ident, c in never:  # a line no merchant sells is not offered by that seller
        if ident in rows:
            assert not any(li.startswith("%s: %s" % (towns[c["town"]], c["category"])) and
                           ident not in sold for li in rows[ident]["lis"]), (ident, c["id"])
    barter = [ln for ln in _json("data/direct_trades.json")["lines"] if ln.get("status") == "approved"]
    for ln in barter:
        if ln["sell"]["id"] in rows:
            assert any(li.startswith("Barter in") for li in rows[ln["sell"]["id"]]["lis"]), ln["id"]
    approved = {ln["sell"]["id"] for ln in barter}
    for ident, r in rows.items():
        assert any(li.startswith("Barter in") for li in r["lis"]) == (ident in approved), ident


@needs_jar
def test_recipes_are_the_jars(raw, zjar):
    held = set(held_ids(zjar))
    made = {}
    for n in zjar.namelist():
        if n.startswith("data/cobblemon/recipe/") and n.endswith(".json"):
            r = json.loads(zjar.read(n).decode("utf-8-sig"))
            res = r.get("result")
            res = res.get("id") if isinstance(res, dict) else res
            if isinstance(res, str) and res in held:
                made.setdefault(res, []).append(r)
    assert len(made) > 60
    lang = json.loads(zjar.read("assets/cobblemon/lang/en_us.json").decode("utf-8"))
    for ident, r in _rows(raw).items():
        lis = [li for li in r["lis"] if li.split(":")[0] in STATIONS]
        assert len(lis) == len(made.get(ident, [])), (ident, lis)
        for rec in made.get(ident, []):
            ings = [v for v in (rec.get("key") or {}).values()] + list(rec.get("ingredients") or []) + \
                [rec[k] for k in ("ingredient", "input", "bottle") if k in rec]
            for ing in ings:
                for q in (ing if isinstance(ing, list) else [ing]):
                    name = lang.get("item.%s.%s" % tuple(q["item"].split(":"))) if "item" in q else None
                    if name and q["item"].startswith("cobblemon:"):
                        assert any(name in li for li in lis), (ident, name)


# ------------------------------------------------------------------------------------------------ gems, none, contract


def test_type_gems_are_the_alpha_spoils(raw):
    types = _json("data/alpha_spoils.json")["type_tables"]
    rows = _rows(raw)
    for t in types["types"]:
        ident = types["gem"].replace("<type>", t)
        lis = [li for li in rows[ident]["lis"] if li.startswith("Paid by a wild alpha")]
        assert len(lis) == 1 and ("%s-type" % t.capitalize()) in lis[0], (ident, lis)
    assert sum(1 for r in rows.values() if any(li.startswith("Paid by a wild alpha") for li in r["lis"])) == len(types["types"])


def test_an_item_with_no_source_says_so_and_only_it(raw):
    rows = _rows(raw)
    bare = {i for i, r in rows.items() if not r["lis"]}
    assert bare  # non-vacuous
    for i in bare:
        assert "No source known to this guide." in _text(rows[i]["cell"]) and "via-none" in rows[i]["words"], i
    for i, r in rows.items():
        assert ("via-none" in r["words"]) == (i in bare), i
    sec = _section(raw, "none")
    listed = set(re.findall(r'<li data-held data-name="([^"]*) via-none">', sec))
    assert listed == {rows[i]["name"].lower() for i in bare}


def test_the_filter_the_search_and_the_chips(raw):
    assert FILTER.filter_problems(raw) == []
    assert [k for k, _t, _a in FILTER.nav_buttons(raw)] == ["all", "items", "vaults", "none"]
    q = re.search(r'<input type="search" id="([^"]+)" data-search="([^"]+)"', raw)
    assert q and html.unescape(q.group(2)) == "[data-held]"
    chips = re.findall(r'<button type="button" data-fill="([^"]*)" data-fill-for="([^"]*)"', raw)
    assert [v for v, _f in chips] == ["via-%s" % k for k in ("shop", "craft", "vault", "drop", "carried", "alpha", "none")]
    assert {f for _v, f in chips} == {q.group(1)}
    words = [r["words"] for r in _rows(raw).values()]
    for v, _f in chips:
        assert any(v in w.split() for w in words), v


def test_no_secret_and_no_legendary_name(raw):
    low = _text(raw).lower()
    for word in ("cache", "barrel", "shrine", "reward chest", "victory road", "desert wreck", "entei"):
        assert word not in low, word
    assert "left for you to discover" in low
    if DT.JAR:
        assert DT.named_species(raw, DT._species()) == set()


def test_the_page_is_registered_and_current():
    import player_guide_held_items as G
    import player_guide_battles as PB
    try:
        PB.find_jar()
    except SystemExit as e:
        pytest.skip("no Cobblemon 1.8 jar: %s" % e)
    assert G.main(["--check"]) == 0
    guides = _json("docs/player/guides.json")["guides"]
    assert [g["file"] for g in guides if g["file"] == "held-items.html"] == ["held-items.html"]
