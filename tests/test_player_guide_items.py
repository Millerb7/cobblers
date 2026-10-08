"""docs/player/items.html (tools/player_guide_items.py): every line a merchant carries is on the page at its price,
no held, superseded or unsited line is offered as on sale, an item with no public source is not on the page at all,
and the shared section filter and search box are whole.

The expectations are read from the data directly, not from the generator's model: data/markets.json for the shelves
(a SITED record's `stock` is on sale at price // count, the merchant's unit price; tools/markets.py merchant_shop),
data/towns.json and markets.json `places_beyond_towns` for the place names, modpack/config/cobbledollars/bank.json
for what the bank buys.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import test_player_site_filter as FILTER  # noqa: E402

PAGE = ROOT / "docs" / "player" / "items.html"


def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw():
    return PAGE.read_text(encoding="utf-8")


def _text(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def _section(raw, key):
    m = re.search(r'<section id="%s" data-section="%s">(.*?)</section>' % (key, key), raw, re.S)
    assert m, "no section %s" % key
    return m.group(1)


def _rows(block):
    """{item id: [the text of each <li> in its row]} of a section's table rows; the id is the row's <span class="id">."""
    out = {}
    for tr in re.findall(r"<tr data-item[^>]*>(.*?)</tr>", block, re.S):
        ident = re.search(r'<span class="id">([^<]*)</span>', tr)
        if ident:
            out[html.unescape(ident.group(1))] = [_text(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", tr, re.S)]
    return out


def _places():
    mk = _json("data/markets.json")
    out = {t["id"]: t["display_name"] for t in _json("data/towns.json")["towns"]}
    for p in mk.get("places_beyond_towns") or []:
        d = _json(p["source"])
        out.setdefault(p["town"], d.get("display_name") or d.get("name"))
    return out


def _records():
    mk = _json("data/markets.json")
    return (mk.get("counters") or []) + (mk.get("stalls") or [])


def test_every_line_on_sale_is_on_the_page_with_its_price(raw):
    rows = _rows(_section(raw, "buy"))
    places = _places()
    missing = []
    n = 0
    for rec in _records():
        if rec.get("status") != "sited":
            continue
        for line in rec.get("stock") or []:
            n += 1
            unit = int(line["price"]) // int(line.get("count") or 1)
            want = "%s: %s, $%s" % (places[rec["town"]], rec["category"], format(unit, ","))
            if want not in rows.get(line["item"], []):
                missing.append((rec["id"], line["id"], want))
    assert n > 100 and not missing, missing[:10]


def test_no_held_line_is_offered(raw):
    """A held, superseded or unsited line is never on sale: its seller is never named for it, and an item with no
    other public source is not on the page at all (the owner, 2026-10-08: an item with no source is a discovery)."""
    buy = _rows(_section(raw, "buy"))
    page = _text(raw)
    places = _places()
    sold = {line["item"] for r in _records() if r.get("status") == "sited" for line in r.get("stock") or []}
    trades = _json("data/traders.json")["stock_policy"]
    mart = set(trades["mart"]["items"]) | {i for t in trades["mart"]["tiers"] for i in t["items"]} | \
        {o["item"] for t in trades["mart"]["training"]["tiers"] for o in t["items"]} | \
        set(trades["stones"]["items"]) | {trades["trainer_card"]["item"]}
    barter = {ln["sell"]["id"] for ln in _json("data/direct_trades.json")["lines"] if ln.get("status") == "approved"}
    bad, checked = [], 0
    for rec in _records():
        lines = [(k, line) for k in ("held_stock", "superseded_stock") for line in rec.get(k) or []]
        if rec.get("status") != "sited":
            lines += [("unsited", line) for line in rec.get("stock") or []]
        for kind, line in lines:
            checked += 1
            item = line["item"]
            seller = "%s: %s" % (places[rec["town"]], rec["category"])
            if any(li.startswith(seller) and li.endswith("$" + format(int(line["price"]) // int(line.get("count") or 1), ","))
                   for li in buy.get(item, [])):
                bad.append((kind, rec["id"], line["id"], "offered as on sale"))
            if item not in sold | mart | barter and item in buy:
                bad.append((kind, rec["id"], line["id"], "on the page with no public source"))
            if item not in sold | mart | barter and "<span class=\"id\">%s</span>" % item in raw:
                bad.append((kind, rec["id"], line["id"], "named on the page with no public source"))
    assert checked > 0 and not bad, bad
    assert "not on sale" not in page.lower()


def test_the_bank_list_is_the_banks(raw):
    sell = _section(raw, "sell")
    shown = {}
    for tr in re.findall(r"<tr data-item[^>]*>(.*?)</tr>", sell, re.S):
        ident = re.search(r'<span class="id">([^<]*)</span>', tr).group(1)
        shown[ident] = _text(re.findall(r'<td class="n">(.*?)</td>', tr)[-1])
    bank = {e["item"]: e["price"] for e in _json("modpack/config/cobbledollars/bank.json")["bank"]}
    for item, price in shown.items():
        assert bank.get(item) is not None and price == "$" + format(bank[item], ","), (item, price)
    unreachable = {u["item"] for u in _json("data/bank.json")["unreachable"]}
    assert not unreachable & set(shown), unreachable & set(shown)
    assert "lumymon" not in raw.lower()  # story and altar items: never named
    assert len(shown) >= len(bank) - len(unreachable & set(bank)) - sum(i.startswith("lumymon:") for i in bank)


def test_wild_battles_pay_nothing_is_said(raw):
    common = _json("modpack/config/cobbledollars/common.json")
    money = _text(_section(raw, "money"))
    assert common["earnCobbleDollarsFromWildPokemon"] is False and "Wild battles pay nothing" in money
    ib = _json("data/markets.json")["income_basis"]
    for k, v in ib["leg_by_badge"].items():
        assert "Gym %s $%s" % (k, format(v, ",")) in money, k


def test_the_filter_and_the_search(raw):
    assert FILTER.filter_problems(raw) == []
    keys = [k for k, _t, _a in FILTER.nav_buttons(raw)]
    assert keys == ["all", "money", "buy", "barter", "sell", "craft"]
    q = re.search(r'<input type="search" id="[^"]+" data-search="([^"]+)"', raw)
    assert q and html.unescape(q.group(1)) == "[data-item]"
    rows = re.findall(r'<tr data-item data-name="([^"]*)"', raw)
    assert len(rows) > 200 and all(r == r.lower() and r for r in rows)


def test_the_page_is_current():
    import player_guide_items as G
    import player_guide_battles as PB
    try:
        PB.find_jar()
    except SystemExit as e:
        pytest.skip("no Cobblemon 1.8 jar: %s" % e)
    assert G.main(["--check"]) == 0
