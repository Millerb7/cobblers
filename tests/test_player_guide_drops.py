"""docs/player/drops.html (tools/player_guide_drops.py): every Pokemon on it is one the region map lists, none is a
legendary, mythical, Ultra Beast or paradox, each one's drops are exactly its drop table's (the jar's, or the
Cobbleverse datapack's species_additions where it carries one) with nothing invented, each chance agrees with a
simulation of Cobblemon's DropTable.getDrops, and --check catches a stale page.

The expectations do not come from the generator's model:
  - the species are read from the PUBLISHED region map (docs/player/region-map.html's inline data), not from
    tools/player_guide_map.py;
  - the drop tables are read here from the jar and the datapack with this file's own reader;
  - the chances come from roll(), a Monte Carlo of getDrops written here from the bytecode reading in the generator's
    docstring (first success in order, a miss counts one, chosen entries leave), not from the generator's exact sum.
test_the_simulation_bites mutates the GENERATOR (its chosen() replaced by one that ignores the order of the pass) and
shows the comparison fails.
"""
from __future__ import annotations

import html
import json
import random
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import test_player_site_filter as FILTER  # noqa: E402

PAGE = ROOT / "docs" / "player" / "drops.html"
MAP = ROOT / "docs" / "player" / "region-map.html"
HIDDEN_LABELS = {"legendary", "mythical", "ultra_beast", "paradox"}
TRIALS = 20000
SAMPLE = 60


def _inputs():
    import player_guide_battles as PB
    import player_guide_drops as G
    try:
        return PB.find_jar(), G.find_dp(), G.find_vanilla()
    except SystemExit as e:
        pytest.skip("missing an input: %s" % e)


@pytest.fixture(scope="module")
def raw():
    return PAGE.read_text(encoding="utf-8")


def page_rows(raw):
    """{species: {item: chance}} of the By Pokemon section."""
    sec = re.search(r'<section id="pokemon" data-section="pokemon">(.*?)</section>', raw, re.S)
    assert sec, "no By Pokemon section"
    out = {}
    for sp, body in re.findall(r'<tr id="mon-[^"]*" data-drop data-sp="([^"]+)"[^>]*>(.*?)</tr>', sec.group(1), re.S):
        out[html.unescape(sp)] = {html.unescape(i): float(c)
                                  for i, c in re.findall(r'<li data-item="([^"]+)" data-chance="([0-9.]+)"', body)}
    return out


def map_species():
    m = re.search(r'<script id="data"[^>]*>(.*?)</script>', MAP.read_text(encoding="utf-8"), re.S)
    assert m, "no inline data in region-map.html"
    return {s[0] for s in json.loads(m.group(1))["species"]}


# ------------------------------------------------------------------ an independent reader of the tables


@pytest.fixture(scope="module")
def tables():
    jar, dp, vanilla = _inputs()
    base, forms, labels = {}, {}, {}
    with zipfile.ZipFile(jar) as z:
        for n in z.namelist():
            m = re.fullmatch(r"data/cobblemon/species/[^/]+/([a-z0-9_]+)\.json", n)
            if m:
                d = json.loads(z.read(n).decode("utf-8-sig"))
                base[m.group(1)] = d.get("drops")
                labels[m.group(1)] = set(d.get("labels") or [])
                for f in d.get("forms") or []:
                    for a in f.get("aspects") or []:
                        if "drops" in f:
                            forms[(m.group(1), a)] = f["drops"]
    with zipfile.ZipFile(dp) as z:
        for n in z.namelist():
            if "/species_additions/" in n and n.endswith(".json"):
                d = json.loads(z.read(n).decode("utf-8-sig"))
                if "drops" in d:
                    base[d["target"].split(":")[-1]] = d["drops"]
    with zipfile.ZipFile(vanilla) as z:
        vlang = json.loads(z.read("assets/minecraft/lang/en_us.json").decode("utf-8"))

    def table(sp):
        head, *aspects = sp.split()
        for a in aspects:
            if (head, a) in forms:
                return forms[(head, a)]
        return base[head]

    def real(item):
        ns, _, p = item.partition(":")
        return ns != "minecraft" or "item.minecraft.%s" % p in vlang or "block.minecraft.%s" % p in vlang
    return {"table": table, "labels": labels, "real": real}


def _rng(v):
    if isinstance(v, int):
        return v, v
    a, _, b = str(v).partition("-")
    return int(a), int(b or a)


def roll(table, rng):
    """One defeat by DropTable.getDrops: {item: count dropped}."""
    lo, hi = _rng(table.get("amount", 1))
    amt = rng.randint(lo, hi)
    ents = table.get("entries") or []
    pool = [e for e in ents if int(e.get("quantity", 1)) <= amt]
    got, picked, taken = {}, 0, []
    while pool:
        sel = next((e for e in pool if rng.random() * 100 < float(e.get("percentage", 100))), None)
        if sel is None:
            picked += 1
        else:
            taken.append(sel)
            picked += int(sel.get("quantity", 1))
            pool = [e for e in pool if not ((e is sel and int(e.get("maxSelectableTimes", 1)) <= taken.count(sel))
                                            or int(e.get("quantity", 1)) > amt - picked)]
        if picked >= amt:
            break
    for e in taken:
        n = rng.randint(*_rng(e["quantityRange"])) if "quantityRange" in e else int(e.get("quantity", 1))
        if n > 0:
            got[e["item"]] = got.get(e["item"], 0) + n
    return got


def simulated(table, seed):
    rng = random.Random(seed)
    hits = {}
    for _ in range(TRIALS):
        for item in roll(table, rng):
            hits[item] = hits.get(item, 0) + 1
    return {i: n / TRIALS for i, n in hits.items()}


def chance_problems(rows, tables, species):
    out = []
    for k, sp in enumerate(species):
        sim = simulated(tables["table"](sp) or {}, k)
        sim = {i: p for i, p in sim.items() if tables["real"](i)}
        page = rows[sp]
        for item in set(sim) | set(page):
            a, b = page.get(item, 0.0), sim.get(item, 0.0)
            tol = 5 * (max(b * (1 - b), 1e-4) / TRIALS) ** 0.5 + 0.002
            if abs(a - b) > tol:
                out.append("%s %s: page %.4f, simulated %.4f" % (sp, item, a, b))
    return out


def _sample(rows):
    """The listed species with the most to get wrong (several partial entries) first, then a spread of the rest."""
    busy = sorted(rows, key=lambda s: (-len(rows[s]), s))
    return list(dict.fromkeys(busy[:SAMPLE // 2] + sorted(rows)[::max(1, len(rows) // (SAMPLE // 2))]))[:SAMPLE]


# ------------------------------------------------------------------ the tests


def test_the_species_are_the_region_maps(raw):
    on_page = set(page_rows(raw))
    on_map = map_species()
    assert on_page == on_map, "drops page and region map disagree: only here %s, only on the map %s" % (
        sorted(on_page - on_map)[:10], sorted(on_map - on_page)[:10])
    assert len(on_page) > 400


def test_no_hidden_species(raw, tables):
    bad = sorted(sp for sp in page_rows(raw) if tables["labels"].get(sp.split()[0], set()) & HIDDEN_LABELS)
    assert not bad, "legendary, mythical, Ultra Beast or paradox species listed: %s" % bad


def test_every_drop_is_its_tables_and_nothing_invented(raw, tables):
    problems = []
    for sp, items in page_rows(raw).items():
        t = tables["table"](sp) or {}
        named = {e["item"] for e in t.get("entries") or []}
        want = {i for i in named if tables["real"](i)}
        # an entry drops nothing, and is rightly absent, when its stack can only be empty, its percentage is 0, or
        # the 100% entries before it always fill the amount first (Litleo: Rotten Flesh at 100% and amount 1, so its
        # Blaze Powder and Rawst Berry are never rolled)
        never, sure = set(), 0
        for e in t.get("entries") or []:
            if (_rng(e.get("quantityRange", 1))[1] <= 0 or float(e.get("percentage", 100)) <= 0
                    or sure >= _rng(t.get("amount", 1))[1]):
                never.add(e["item"])
            if float(e.get("percentage", 100)) >= 100:
                sure += int(e.get("quantity", 1))
        if set(items) - named:
            problems.append("%s: invented %s" % (sp, sorted(set(items) - named)))
        if want - set(items) - never:
            problems.append("%s: missing %s" % (sp, sorted(want - set(items) - never)))
    assert not problems, problems[:10]


def test_the_chances_match_a_simulation(raw, tables):
    rows = page_rows(raw)
    problems = chance_problems(rows, tables, _sample(rows))
    assert not problems, problems[:10]


def test_the_simulation_bites(tables, monkeypatch):
    """Mutate the generator: a chosen() that gives each entry its bare percentage, ignoring that a pass stops at the
    first success and that the amount bounds the passes. The page it renders must fail the comparison."""
    import player_guide_drops as G
    jar, dp, vanilla = _inputs()
    rows = page_rows(PAGE.read_text(encoding="utf-8"))
    species = {sp: sp for sp in _sample(rows)[:20]}

    def naive(amount, ents):
        out = {}
        sets = [frozenset()]
        probs = [1.0]
        for i, e in enumerate(ents):
            sets, probs = sets + [s | {i} for s in sets], [c * (1 - e["p"]) for c in probs] + [c * e["p"] for c in probs]
        for s, c in zip(sets, probs):
            out[s] = out.get(s, 0.0) + c
        return out
    monkeypatch.setattr(G, "chosen", naive)
    mutated = page_rows(G.render(G.collect(str(jar), str(dp), str(vanilla), species=species)))
    assert chance_problems(mutated, tables, sorted(species)), "a generator that ignores the pass order still passed"


def test_the_filter_and_the_search(raw):
    assert FILTER.filter_problems(raw) == []
    assert [k for k, _t, _a in FILTER.nav_buttons(raw)] == ["all", "pokemon", "items"]
    q = re.search(r'<input type="search" id="[^"]+" data-search="([^"]+)"', raw)
    assert q and html.unescape(q.group(1)) == "[data-drop]"
    names = re.findall(r'data-drop data-(?:sp|item)="[^"]*" data-name="([^"]*)"', raw)
    assert len(names) > 600 and all(n == n.lower() and n for n in names)


def test_every_link_lands(raw):
    ids = set(re.findall(r' id="([^"]+)"', raw))
    inner = set(re.findall(r'href="#([^"]+)"', raw))
    assert inner and not inner - ids, sorted(inner - ids)[:10]
    on_map = map_species()
    to_map = {html.unescape(s).replace("%20", " ") for s in re.findall(r'href="region-map\.html#pokemon=([^"]+)"', raw)}
    assert to_map == on_map


def test_the_page_is_current():
    import player_guide_drops as G
    _inputs()
    assert G.main(["--check"]) == 0


def test_check_catches_a_stale_page(tmp_path):
    import player_guide_drops as G
    _inputs()
    stale = tmp_path / "drops.html"
    stale.write_text(PAGE.read_text(encoding="utf-8").replace("Drops nothing.", "Drops a Master Ball.", 1),
                     encoding="utf-8")
    assert G.main(["--check", "--out", str(stale)]) == 1
