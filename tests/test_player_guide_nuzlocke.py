"""tools/player_guide_nuzlocke.py: the Nuzlocke tracker page (docs/player/nuzlocke.html).

What breaks without each test:
  zone count         a page that drops or doubles a zone lets a player skip or repeat a catch
  order              zones out of progression order send a player to a zone they cannot reach yet
  evolution lines    a wrong line makes the dupes clause flag the wrong species (or miss one)
  species lists      a species outside a zone's own spawn scope, or a legendary-class one, on the page
  caps               a cap that disagrees with the gym aces the player is told to expect
  leaks              docs/player/ is public; the page names no secret (the site's own leak check, run on this page)
  staleness          the committed page must be what the generator writes now

The species check reads the spawn table and the jar's labels on its own, not through the generator's functions.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import player_guide_nuzlocke as N  # noqa: E402

PAGE = ROOT / "docs" / "player" / "nuzlocke.html"
LEGEND_LABELS = {"legendary", "mythical", "ultra_beast", "paradox"}


def _data(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def model():
    return N.collect()


@pytest.fixture(scope="module")
def page_json():
    m = re.search(r'<script id="nz-data" type="application/json">(.*?)</script>', PAGE.read_text(encoding="utf-8"), re.S)
    assert m, "docs/player/nuzlocke.html carries no nz-data block"
    return json.loads(m.group(1))


def test_zone_count_equals_the_zones_file(model, page_json):
    zones = _data("nuzlocke_zones.json")["zones"]
    assert model["total"] == len(zones) == _data("nuzlocke_zones.json")["counts"]["total"]
    assert len(page_json["zones"]) == len(zones)
    assert sum(len(g["zones"]) for g in model["groups"]) == len(zones)
    # every zone appears once on the page as a card
    html = PAGE.read_text(encoding="utf-8")
    assert html.count('class="nz-zone"') == len(zones)
    assert len({z["key"] for z in model["zones"]}) == len(zones), "two zones share a page key"


def test_zones_are_in_progression_order(model):
    zs = model["zones"]
    assert [z["no"] for z in zs] == list(range(1, len(zs) + 1))
    assert [z["tier"] for z in zs] == sorted(z["tier"] for z in zs)
    # within a tier, zones on a route leg come before the ones off every leg, and legs in route order
    legs = [lg["route"] for lg in _data("nuzlocke_zones.json")["legs"]]
    for tier in {z["tier"] for z in zs}:
        same = [z for z in zs if z["tier"] == tier]
        flags = [z["on_path"] for z in same]
        assert flags == sorted(flags, reverse=True), "tier %d lists an off-path zone before an on-path one" % tier
        places = [z["place"] for z in same if z["on_path"]]
        assert places == sorted(places)
    assert model["zones"][0]["id"] == _data("nuzlocke_zones.json")["legs"][0]["zones"][0]["zone"], legs[:1]


def test_evolution_lines_come_from_the_jar(model):
    names = ["pichu", "pikachu", "raichu", "eevee", "vaporeon", "jolteon", "rattata", "raticate", "pidgey", "pidgeotto",
             "magikarp", "gyarados", "abra", "alakazam"]
    lines = N.evolution_lines(names)
    assert lines["pichu"] == lines["pikachu"] == lines["raichu"]
    assert lines["eevee"] == lines["vaporeon"] == lines["jolteon"]
    assert lines["rattata"] == lines["raticate"] and lines["pidgey"] == lines["pidgeotto"]
    assert lines["magikarp"] == lines["gyarados"] and lines["abra"] == lines["alakazam"]
    assert len({lines[s] for s in ("pichu", "eevee", "rattata", "pidgey", "magikarp", "abra")}) == 6
    # on the page: a regional form shares its base species' line, and two evolution stages in the data share one
    mons = model["mons"]
    again = N.evolution_lines(list(mons))
    for sp, (_name, line) in mons.items():
        assert line == again[N.base_of(sp)]
    by_base = {}
    for sp, (_n, line) in mons.items():
        assert by_base.setdefault(N.base_of(sp), line) == line, "forms of %s sit in two lines" % sp


def _jar_labels():
    import player_guide_battles as PB
    z = zipfile.ZipFile(PB.find_jar())
    out = {}
    for n in z.namelist():
        m = re.fullmatch(r"data/cobblemon/species/[^/]+/([a-z0-9_]+)\.json", n)
        if m:
            out[m.group(1)] = set(json.loads(z.read(n).decode("utf-8")).get("labels") or [])
    return out


def test_each_zone_lists_only_its_own_spawnable_species_and_no_legendary(model):
    labels = _jar_labels()
    spawns = _data("spawns.json")["entries"]
    nz = {z["zone"]: z for z in _data("nuzlocke_zones.json")["zones"]}
    for z in model["zones"]:
        scopes = nz[z["id"]].get("pools") or [z["id"]]
        want = {e["species"] for e in spawns if e["scope"] in scopes and e.get("ambient") and e.get("weight", 0) > 0
                and not e.get("heart") and not (labels[e["species"].split()[0]] & LEGEND_LABELS)}
        assert set(z["mons"]) == want, z["id"]
    shown = {N.base_of(s) for s in model["mons"]}
    assert not [s for s in shown if labels[s] & LEGEND_LABELS], "a legendary-class species is on the page"
    assert model["dropped"], "the check expects some legendary-class rows to have been dropped (Buzzwole, Pheromosa)"


def test_badge_caps_match_the_gym_aces():
    aces = _data("trainers.json")["generation_contract"]["gym_ace_levels"]
    caps = [c for _l, c in N.collect()["caps"]]
    assert caps[:8] == aces, "the cap after n badges is the next gym's top level"
    assert caps[8] == 60 and caps[-1] == 100 and len(caps) == 11


def _leak_module():
    spec = importlib.util.spec_from_file_location("leakcheck", ROOT / "tests" / "test_player_site_leaks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_page_carries_no_secret():
    L = _leak_module()
    found = L.leaks(PAGE.read_text(encoding="utf-8"), L.secrets())
    assert not found, found[:10]
    # a zone's data id is an id of a secret record elsewhere (data/rewards.json names vr_bloom): never printed
    raw = PAGE.read_text(encoding="utf-8")
    for z in _data("nuzlocke_zones.json")["zones"]:
        if z["zone"].startswith("vr_"):
            assert z["zone"] not in raw


def test_the_committed_page_is_current():
    assert N.main(["--check"]) == 0
