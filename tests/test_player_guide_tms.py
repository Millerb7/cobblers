"""docs/player/tms.html (tools/player_guide_tms.py): every TM is on the page once, under the badge the crafting gate gives
it, with the score table's move, type, kind, power and accuracy; every way to get one is the data's.

The expectations are read from the data and the jar by this file, not from the generator's model:
  - the badge of each TM is re-derived here from data/tm_gate.json (shelf lines in data/markets.json first, then an
    outlier group's hand placement, then the score's band, then the chain raises) with this file's own band function. When
    the offline server snapshot is present the gate's own plan (tools/tm_gate.py --plan-out) is the third witness.
  - counters: data/markets.json `stock` of a SITED record, at price // count, in the town data/towns.json names; a
    held, superseded or unsited line is never offered.
  - leaders: data/progression.json first_win_rewards `one_of`, with data/gym_trainers.json for the name and gym.
  - the TM Machine: data/cobblemon/tms/*.json in the Cobblemon 1.8.0 jar.
Without the jar the tests that need it SKIP with the reason; none passes without reading one.

Mutation: test_the_badge_check_bites changes the GENERATOR (tm_gate.band is told every score is one band higher) and
shows the check, which does not call that function, reports the page.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import test_player_site_filter as FILTER  # noqa: E402
import test_player_guide_dungeons as DT  # noqa: E402  the jar finder and the legendary-name reader

PAGE = ROOT / "docs" / "player" / "tms.html"
SNAPSHOT = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05")
needs_jar = DT.needs_jar


def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _text(s):
    t = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())
    return re.sub(r"\s+([,.;:)])", r"\1", t)


@pytest.fixture(scope="module")
def raw():
    assert PAGE.is_file(), "run python tools/player_guide_tms.py"
    return PAGE.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------ the page, parsed


def _rows(raw):
    """{tm item id: {"badge": N or "machine", "cells": [...], "lis": [text of each <li>]}} for the badge sections."""
    out = {}
    for sec in re.finditer(r'<section id="badge-(\d)" data-section="badge-\d">(.*?)</section>', raw, re.S):
        for tr in re.findall(r"<tr data-tm[^>]*>(.*?)</tr>", sec.group(2), re.S):
            ident = html.unescape(re.search(r'<span class="id">([^<]*)</span>', tr).group(1))
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            assert ident not in out, "%s is on the page twice" % ident
            out[ident] = {"badge": int(sec.group(1)), "name": _text(tds[0].split("<span")[0]),
                          "type": _text(tds[1]), "kind": _text(tds[2]), "power": _text(tds[3]), "acc": _text(tds[4]),
                          "lis": [_text(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", tds[5], re.S)]}
    return out


# ------------------------------------------------------------------------------------------------ the badge, again


def _band(score, bands):
    s = round(score, 1)
    if s < bands["badge_1_below"]:
        return 1
    for b, top in sorted((int(k), v) for k, v in bands["top"].items()):
        if s <= top:
            return b
    return bands["above_top"]


def expected_badges():
    gate, scores, mk = _json("data/tm_gate.json"), _json("docs/mechanics/TM_POWER_GATE.json")["tms"], _json("data/markets.json")
    shelf = {}
    for c in mk["counters"]:
        for key in ("stock", "held_stock"):
            for line in c.get(key) or []:
                if line["item"].startswith("tmcraft:tm_") and isinstance(line.get("gate_badge"), int):
                    shelf[line["item"]] = min(line["gate_badge"], shelf.get(line["item"], 99))
    hand = {}
    for g in gate["badge_rule"]["power"]["outliers"]:
        for item, b in (g.get("place") or {}).items():
            hand[item] = b
    out = {}
    for item, row in scores.items():
        out[item] = shelf.get(item) or hand.get(item) or _band(row["score"], gate["badge_rule"]["power"]["bands"])
    for r in gate["badge_rule"]["chain"]["raises"]:
        assert out[r["item"]] == r["from"], r
        out[r["item"]] = r["to"]
    return out


def badge_problems(raw):
    rows, want = _rows(raw), expected_badges()
    bad = []
    if set(rows) != set(want):
        bad.append("TMs on the page differ from the score table: %s" % sorted(set(rows) ^ set(want))[:5])
    bad += ["%s is under badge %s, the gate says %s" % (i, rows[i]["badge"], b) for i, b in want.items()
            if i in rows and rows[i]["badge"] != b]
    return bad


def test_every_tm_is_on_the_page_once_under_its_badge(raw):
    assert badge_problems(raw) == []
    assert len(_rows(raw)) == 802


def test_the_badge_check_bites(raw, monkeypatch):
    """A record-side mutation moves the expectation and the output together. This one changes the generator's band
    function and leaves the data alone; the check above does not use that function."""
    import player_guide_tms as G
    if not DT.JAR:
        pytest.skip("no Cobblemon 1.8 jar")
    real = G.final_badges

    def later(gate, scores, shelf):  # every TM one badge late, as a wrong band function would place it
        placed = real(gate, scores, shelf)
        return {k: dict(v, badge=min(8, v["badge"] + 1)) for k, v in placed.items()}
    monkeypatch.setattr(G, "final_badges", later)
    mutated = G.render(G.collect(str(DT.JAR)))
    assert badge_problems(mutated)
    # and the page itself, edited by hand, is caught: move one row to another section
    first = re.search(r'(<tr data-tm data-name="absorb [^>]*>.*?</tr>)', raw, re.S).group(1)
    moved = raw.replace(first, "", 1).replace('<section id="badge-2" data-section="badge-2">',
                                              '<section id="badge-2" data-section="badge-2">' + first, 1)
    assert badge_problems(moved)


@pytest.mark.skipif(not SNAPSHOT.is_dir(), reason="the 2026-10-05 server snapshot is not on this machine")
def test_the_badges_equal_the_gates_own_plan(tmp_path):
    """Third witness: tools/tm_gate.py's plan for the snapshot (the gate the world runs) gives the same badge per TM."""
    plan = tmp_path / "plan.json"
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "tm_gate.py"), "--server-dir", str(SNAPSHOT), "--check",
                        "--plan-out", str(plan)], capture_output=True, text=True, timeout=200)
    assert p.returncode == 0, p.stdout[-400:] + p.stderr[-400:]
    got = {k: v["badge"] for k, v in json.loads(plan.read_text(encoding="utf-8"))["tms"].items()}
    assert got == expected_badges()


# ------------------------------------------------------------------------------------------------ the figures


def test_move_type_kind_power_and_accuracy_are_the_score_tables(raw):
    table = _json("docs/mechanics/TM_POWER_GATE.json")["tms"]
    rows = _rows(raw)
    bad = []
    for item, t in table.items():
        r = rows[item]
        want = (t["move"], t["type"], t["category"], "-" if not t["base_power"] else str(t["base_power"]),
                "-" if t["accuracy"] is True else str(t["accuracy"]))
        if (r["name"], r["type"], r["kind"], r["power"], r["acc"]) != want:
            bad.append((item, (r["name"], r["type"], r["kind"], r["power"], r["acc"]), want))
    assert not bad, bad[:5]


def test_every_tm_can_be_crafted_and_says_when(raw):
    table = _json("docs/mechanics/TM_POWER_GATE.json")["tms"]
    for item, r in _rows(raw).items():
        grade = table[item]["disc_grade"]
        want = "Craft (%s blank disc)" % grade if grade else "Craft"
        assert want in r["lis"], (item, r["lis"])


# ------------------------------------------------------------------------------------------------ counters


def test_counter_lines_are_the_sited_stock_and_only_that(raw):
    mk, towns = _json("data/markets.json"), {t["id"]: t["display_name"] for t in _json("data/towns.json")["towns"]}
    for p in mk.get("places_beyond_towns") or []:
        d = _json(p["source"])
        towns.setdefault(p["town"], d.get("display_name") or d.get("name"))
    rows = _rows(raw)
    want, refused = {}, set()
    for c in mk["counters"] + (mk.get("stalls") or []):
        for line in c.get("stock") or []:
            if line["item"].startswith("tmcraft:tm_"):
                if c.get("status") == "sited":
                    price = int(line["price"]) // int(line.get("count") or 1)
                    want.setdefault(line["item"], set()).add("Counter in %s (%s): $%s" % (towns[c["town"]], c["category"],
                                                                                         format(price, ",")))
                else:
                    refused.add(line["item"])
        for key in ("held_stock", "superseded_stock"):
            refused |= {line["item"] for line in c.get(key) or [] if line["item"].startswith("tmcraft:tm_")}
    assert len(want) == 10, want  # the sited shelf today; a change here is a change to this page's claim
    for item, r in rows.items():
        got = {li for li in r["lis"] if li.startswith("Counter in")}
        assert got == want.get(item, set()), (item, got, want.get(item))
    assert refused - set(want), "no held line to refuse: the check is vacuous"
    assert "northlight" not in raw.lower(), "a held counter is named"


# ------------------------------------------------------------------------------------------------ leaders


def test_leader_lines_are_the_first_win_pools(raw):
    prog = _json("data/progression.json")
    pools = {}

    def walk(n):
        if isinstance(n, dict):
            if isinstance(n.get("first_win_rewards"), dict):
                pools.update(n["first_win_rewards"]["trainers"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(prog)
    gyms = {g["upstream_trainer_id"]: g for g in _json("data/gym_trainers.json")["trainers"]}
    want = {}
    for tid, rec in pools.items():
        tms = [i for i in rec.get("one_of") or [] if i.startswith("tmcraft:")]
        for item in set(tms):
            gym = int(re.fullmatch(r"gym(\d)_cleared", rec["flag"]).group(1))
            n = tms.count(item)
            say = "the one TM it gives" if len(tms) == 1 else "%d%% chance, one of %d" % (round(100 * n / len(tms)), len(tms))
            want.setdefault(item, set()).add("Gym %d leader %s, first win only (%s)" % (gym, gyms[tid]["display_name"], say))
    assert len(want) == 23
    for item, r in _rows(raw).items():
        got = {li for li in r["lis"] if li.startswith("Gym ")}
        assert got == want.get(item, set()), (item, got, want.get(item))


# ------------------------------------------------------------------------------------------------ the TM Machine


@needs_jar
def test_machine_lines_are_the_jars_native_tms(raw):
    z = zipfile.ZipFile(DT.JAR)
    lang = json.loads(z.read("assets/cobblemon/lang/en_us.json").decode("utf-8"))
    native = {}
    for n in z.namelist():
        if n.startswith("data/cobblemon/tms/") and n.endswith(".json"):
            d = json.loads(z.read(n).decode("utf-8-sig"))
            native[d["moveName"]] = d
    rows = _rows(raw)
    twin = {i.split("tm_", 1)[1]: i for i in rows}
    for mid, d in native.items():
        if mid not in twin:
            continue
        lis = [li for li in rows[twin[mid]]["lis"] if li.startswith("TM Machine")]
        assert len(lis) == 1, (mid, lis)
        for need in d["recipe"]:
            key = need.get("item") or need.get("tag")
            if "item" in need:  # the gem names are the jar's own
                name = lang.get("item.cobblemon.%s" % key.split(":")[1])
                if name:
                    assert name in lis[0], (mid, name, lis[0])
        assert ("always on offer" in lis[0]) == (d["obtainMethods"][0]["variant"] == "cobblemon:default"), (mid, lis[0])
    assert all("TM Machine" not in li for i, r in rows.items() if i.split("tm_", 1)[1] not in native for li in r["lis"])
    only = set(native) - set(twin)
    section = re.search(r'<section id="machine" data-section="machine">(.*?)</section>', raw, re.S).group(1)
    assert len(re.findall(r"<tr data-tm", section)) == len(only) > 0
    for mid in only:
        assert (lang.get("cobblemon.move.%s" % mid) or mid) in html.unescape(section), mid


# ------------------------------------------------------------------------------------------------ the page's contract


def test_the_filter_the_search_and_the_chips(raw):
    assert FILTER.filter_problems(raw) == []
    keys = [k for k, _t, _a in FILTER.nav_buttons(raw)]
    assert keys == ["all", "how"] + ["badge-%d" % b for b in range(1, 9)] + ["machine"]
    q = re.search(r'<input type="search" id="([^"]+)" data-search="([^"]+)"', raw)
    assert q and html.unescape(q.group(2)) == "[data-tm]"
    chips = re.findall(r'<button type="button" data-fill="([^"]*)" data-fill-for="([^"]*)"', raw)
    assert len(chips) == 21 and {f for _v, f in chips} == {q.group(1)}
    names = [m.lower() for m in re.findall(r'<tr data-tm data-name="([^"]*)"', raw)]
    for value, _f in chips:  # a chip that matches nothing is a dead button
        assert any(value in n for n in names), value
    js = (ROOT / "docs" / "player" / "assets" / "site.js").read_text(encoding="utf-8")
    assert "data-fill" in js and "data-fill-for" in js


def test_no_secret_and_no_legendary_name(raw):
    """TMs found in caches and rewards are discoveries: the page names no cache, shrine, reward or place for a TM, and no
    species the jar labels legendary-class appears."""
    low = _text(raw).lower()
    for word in ("cache", "barrel", "shrine", "reward chest", "victory road"):
        assert word not in low, word
    assert "left for you to discover" in low
    if DT.JAR:
        assert DT.named_species(raw, DT._species()) == set()


def test_the_page_is_registered_and_current():
    import player_guide_tms as G
    import player_guide_battles as PB
    try:
        PB.find_jar()
    except SystemExit as e:
        pytest.skip("no Cobblemon 1.8 jar: %s" % e)
    assert G.main(["--check"]) == 0
    guides = _json("docs/player/guides.json")["guides"]
    assert [g["file"] for g in guides if g["file"] == "tms.html"] == ["tms.html"]
