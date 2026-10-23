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
    dungeons = _data("dungeons.json")["dungeons"]
    assert model["total"] == len(zones) == _data("nuzlocke_zones.json")["counts"]["total"]
    # the page's tracker holds the area zones, then one zone per dungeon
    assert len(page_json["zones"]) == len(zones) + len(dungeons)
    assert sum(len(g["zones"]) for g in model["groups"]) == len(zones) + len(dungeons)
    # every zone appears once on the page as a card
    html = PAGE.read_text(encoding="utf-8")
    assert html.count('class="nz-zone"') == len(zones) + len(dungeons)
    keys = {z["key"] for z in model["zones"] + model["dungeons"]}
    assert len(keys) == len(zones) + len(dungeons), "two zones share a page key"


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
    # the one page that names legendaries (the owner, 2026-10-23): the allowance is the leak test's own allow_for(PAGE)
    found = L.leaks(PAGE.read_text(encoding="utf-8"), L.secrets(), L.allow_for(PAGE))
    assert not found, found[:10]
    # a zone's data id is an id of a secret record elsewhere (data/rewards.json names vr_bloom): never printed
    raw = PAGE.read_text(encoding="utf-8")
    for z in _data("nuzlocke_zones.json")["zones"]:
        if z["zone"].startswith("vr_"):
            assert z["zone"] not in raw


def test_the_committed_page_is_current():
    assert N.main(["--check"]) == 0


# ------------------------------------------------------------------------------------------------ legendaries, dungeons
# The owner, 2026-10-23: "nuzlocke page should show dungeons and legendaries per area, so a player can count those";
# legendaries NAMED on this page only; "just dungeon name ... i have 1 encounter no matter the level".


def _cards():
    """{card key: the card's html} read from the finished page, not from the generator's model."""
    html = PAGE.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r'<article class="nz-zone" id="z-(\w+)".*?</article>', html, re.S):
        out[m.group(1)] = m.group(0)
    return out


_LANG = []


def _display(sp):
    if not _LANG:
        z = zipfile.ZipFile(__import__("player_guide_battles").find_jar())
        _LANG.append(json.loads(z.read("assets/cobblemon/lang/en_us.json").decode("utf-8")))
    return _LANG[0]["cobblemon.species.%s.name" % sp]


def test_zone_keys_are_unchanged_so_saved_ticks_survive():
    """The tracker saves ticks under each zone's key. A key is sha1 of the zone's data id, written here again rather than
    taken from the generator; one golden pair pins the formula to what the page published before legendaries and
    dungeons were added (its card id for Maze Forest). Without this a re-hash would silently wipe every player's run."""
    import hashlib
    assert N.zone_key("route1_maze_forest") == "zd0dafd55"
    cards = _cards()
    for z in _data("nuzlocke_zones.json")["zones"]:
        assert "z" + hashlib.sha1(z["zone"].encode()).hexdigest()[:8] in cards, z["zone"]


def test_every_legendary_row_is_in_the_zone_whose_ground_holds_it_and_has_a_checkbox():
    """Rows are checked against the sources' own coordinates with a point-in-polygon written here: the chambers' mouths
    and portals (data/legendaries.json), the sanctuaries' centres, the Hoopa cradle's spot, the Giratina keep, the
    Rayquaza summit. Without it a row could sit in the wrong area's card and send a player to count it there."""
    import hashlib
    regions = _data("regions.json")["subregions"]
    cards = _cards()

    def inside(poly, x, z):
        hit = False
        for i in range(len(poly)):
            (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % len(poly)]
            if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
                hit = not hit
        return hit

    def zone_at(x, z):
        return next(s["id"] for s in regions if any(inside(p, x, z) for p in s["polygons"]))

    want = []
    for r in _data("legendaries.json")["encounters"]:
        if r["status"] == "sited":
            at = r["mouth"] if r["kind"] == "lake_grotto" else r["portal"]
            want.append((r["species"], zone_at(*at)))
    for s in _data("sanctuaries.json")["sanctuaries"]:
        for sp in [s["occupant"]["species"]] + list(s["occupant"].get("co_occupants") or []):
            want.append((sp, zone_at(*s["site"]["centre"])))
    h = _data("hoopa_cradle.json")["spot"]
    want.append(("hoopa", zone_at(h[0], h[2])))
    want.append(("giratina", zone_at(*_data("frostpeak_keep.json")["site"]["centre"])))
    ry = _data("rayquaza_sky.json")["site"]["summit"]
    want.append(("rayquaza", zone_at(ry["x"], ry["z"])))
    sh = _data("research_station.json")["shrine"]
    import location_titles as LT
    bands = LT._marine_bands()
    for sp in ("latias", "latios"):
        x, z = sh[sp]["at"]
        want.append((sp, next(b for b, boxes in bands.items() if any(a <= x <= c and e <= z <= f for a, c, e, f in boxes))))
    # the adopted and sweep sites: the placement record's corner plus half the template's size, the species read from the
    # site's own display text ("Calyrex, with Spectrier", "Necrozma (Dawn Wings)") by the jar's display names
    labels = _jar_labels()
    shown = {_display(sp).lower(): sp for sp, ls in labels.items() if ls & LEGEND_LABELS}
    placements = {p["id"]: p for p in _data("placements.json")["placements"]}
    sites = _data("adopted_legendary_sites.json")
    for s in sites["sites"] + sites["sweep_sites"]:
        if s.get("scheduled_as"):
            p = placements[s["scheduled_as"]]["position"]
            cx, cz = p["x"], p["z"]
        else:
            cx, cz = s["placement"]["corner"]
        x, z = cx + s["size"][0] // 2, cz + s["size"][2] // 2
        species = [shown[w.lower()] for w in re.findall(r"[A-Za-z]+", s["legendary"]) if w.lower() in shown]
        assert species, s["legendary"]
        want += [(sp, zone_at(x, z)) for sp in species]
    assert len(want) >= 35, len(want)       # 37 today; the other 9 rows come from data/spawns.json entries (below)
    for sp, zone in want:
        key = "z" + hashlib.sha1(zone.encode()).hexdigest()[:8]
        assert key in cards, (sp, zone, "the zone has no card")
        lk = "l" + hashlib.sha1(("legendary:%s:%s" % (zone, sp)).encode()).hexdigest()[:8]
        assert 'data-leg="%s"' % lk in cards[key], (sp, zone, "no checkbox in its zone's card")
        assert _display(sp) in re.sub(r"<[^>]+>", " ", cards[key]).replace("&#x27;", "'"), (sp, zone, "not named")
    # the wild entries: a legendary-class ambient entry scoped to a zone is a row in that zone, any other (a tower's grounds,
    # an elder tree's crown pool) is a row somewhere
    doc = _data("nuzlocke_zones.json")
    have = {(z["zone"], r["species"]) for z in doc["zones"] for r in z.get("legendaries") or ()}
    zone_ids = {z["zone"] for z in doc["zones"]}
    legend = {s for s, ls in labels.items() if ls & LEGEND_LABELS}
    seen = 0
    for e in _data("spawns.json")["entries"]:
        sp = e["species"].split()[0]
        if sp in legend and e.get("ambient") and e.get("weight", 0) > 0 and not e.get("heart"):
            seen += 1
            assert (e["scope"], sp) in have if e["scope"] in zone_ids else any(h[1] == sp for h in have), (e["scope"], sp)
    assert seen >= 8, seen
    # and nothing else is ticked into a card: the page's checkboxes are exactly the zones file's rows
    rows = sum(len(z.get("legendaries") or ()) for z in _data("nuzlocke_zones.json")["zones"])
    assert sum(c.count("data-leg=") for c in cards.values()) == rows == _data("nuzlocke_zones.json")["counts"]["legendaries"]


def test_every_dungeon_is_one_zone_of_its_own_with_no_level_and_no_species_list():
    """data/dungeons.json is the list, by the dungeon's player-facing name. Without this a dungeon could be dropped, or
    show a level and a species list that would make it look like a place with a table."""
    cards = _cards()
    html = PAGE.read_text(encoding="utf-8")
    dungeons = _data("dungeons.json")["dungeons"]
    assert len(dungeons) >= 13
    import hashlib
    for d in dungeons:
        key = "z" + hashlib.sha1(("dungeon_" + d["id"]).encode()).hexdigest()[:8]
        assert key in cards, d["name"]
        card = cards[key]
        assert "<h3>" in card and d["name"] in card
        assert "Dungeon" in card and "whatever the level" in card
        assert "What lives here" not in card and "data-leg=" not in card
        assert "Levels " not in card and "cap " not in card
    assert '<h2>Dungeons <small>%d zones</small></h2>' % len(dungeons) in html
    # they come after every area zone
    first_dungeon = min(html.index(c) for c in (cards["z" + hashlib.sha1(("dungeon_" + d["id"]).encode()).hexdigest()[:8]]
                                                for d in dungeons))
    assert all(html.index(c) < first_dungeon for k, c in cards.items()
               if k not in {"z" + hashlib.sha1(("dungeon_" + d["id"]).encode()).hexdigest()[:8] for d in dungeons})


def test_the_zones_file_holds_a_home_for_every_legendary_class_species():
    """The roster (data/dungeon_prize_roster.json) says each legendary-class species has one home. Every species in the
    jar's label set is either a row, a dungeon's, a starter's or a named exclusion in the zones file: a species in none
    of them is one the page silently omits (CLAUDE.md 'Our list is not the world')."""
    labels = _jar_labels()
    legend = {s for s, ls in labels.items() if ls & LEGEND_LABELS}
    doc = _data("nuzlocke_zones.json")
    rows = {r["species"] for z in doc["zones"] for r in z.get("legendaries") or ()}
    reg = doc["legendary_register"]
    homed = rows | set(reg["dungeon_held"]) | {e["species"] for e in reg["excluded"]}
    assert legend == set(_data("dungeon_prize_roster.json")["species"]), "the roster and the jar disagree"
    assert legend <= homed, sorted(legend - homed)
    assert rows <= legend and not rows & set(reg["dungeon_held"]), "a dungeon's legendary is also a row"
    assert not rows & {e["species"] for e in reg["excluded"]}


# -- saved progress: the page's own script run against stand-in browser objects (node), not a re-statement of it
NODE_HARNESS = r"""
const fs = require('fs');
const [,, scriptPath, dataPath, savedPath] = process.argv;
const data = fs.readFileSync(dataPath, 'utf8');
const saved = fs.readFileSync(savedPath, 'utf8');
const els = {};
function stub(name) {
  if (els[name]) return els[name];
  const e = { textContent: '', value: '', hidden: false, checked: false, attrs: {}, children: [],
    addEventListener() {}, setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k] || null; },
    appendChild(c) { return c; }, removeChild() {}, firstChild: null, querySelector() { return stub('child'); },
    querySelectorAll() { return []; } };
  els[name] = e; return e;
}
const listeners = {};
const store = {};
if (saved !== 'NONE') store['cobblers-nuzlocke-v1'] = saved;
global.localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } };
global.document = { getElementById: id => (id === 'nz-data' ? { textContent: data } : stub('#' + id)), querySelector: s => stub(s),
  querySelectorAll: () => [], createElement: () => stub('new'), addEventListener: (t, f) => { listeners[t] = f; }, activeElement: null, body: stub('body') };
global.URL = {}; global.Blob = function () {}; global.alert = () => {}; global.confirm = () => true; global.FileReader = function () {};
eval(fs.readFileSync(scriptPath, 'utf8'));
listeners.DOMContentLoaded();
console.log(JSON.stringify({ caught: els['#nz-caught'].textContent, failed: els['#nz-failed'].textContent,
  skipped: els['#nz-skipped'].textContent, left: els['#nz-left'].textContent, legs: els['#nz-legs'].textContent,
  cap: els['#nz-cap'].textContent, badges: els['#nz-badges'].value }));
"""


def _run_page_script(tmp_path, saved):
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed: the page script cannot be run (NOT_EXECUTED)")
    script, data, sv, harness = (tmp_path / n for n in ("page.js", "data.json", "saved.json", "harness.js"))
    script.write_text(N.SCRIPT, encoding="utf-8")
    data.write_text(re.search(r'<script id="nz-data" type="application/json">(.*?)</script>',
                              PAGE.read_text(encoding="utf-8"), re.S).group(1), encoding="utf-8")
    sv.write_text(saved if isinstance(saved, str) else json.dumps(saved), encoding="utf-8")
    harness.write_text(NODE_HARNESS, encoding="utf-8")
    out = subprocess.run([node, str(harness), str(script), str(data), str(sv)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-600:]
    return {k: str(v) for k, v in json.loads(out.stdout.strip().splitlines()[-1]).items()}


def test_a_save_from_before_legendaries_loads_and_counts_its_zones(tmp_path, page_json):
    """A tracker saved by the page as it was (no `legs` field) must still load, with its caught and skipped zones counted
    and no legendary ticked; a save with ticks keeps the valid ones and drops a key the page does not hold; a damaged
    save is ignored. The same script the page ships runs here against stand-in browser objects."""
    zk = [z["id"] for z in page_json["zones"]]
    old = {"v": 1, "badges": 2, "zones": {zk[0]: {"s": "caught", "sp": "", "other": "Rattata", "nick": "Ratty"},
                                          zk[1]: {"s": "skipped", "sp": "", "other": "", "nick": ""}}}
    got = _run_page_script(tmp_path, old)
    assert (got["caught"], got["skipped"], got["failed"], got["legs"]) == ("1", "1", "0", "0"), got
    assert got["badges"] == "2" and got["left"] == str(len(zk) - 2)
    leg = next(l[0] for z in page_json["zones"] for l in z["legs"])
    new = dict(old, legs={leg: True, "lffffffff": True})
    assert _run_page_script(tmp_path, new)["legs"] == "1"
    assert _run_page_script(tmp_path, "{not json")["caught"] == "0"
    assert _run_page_script(tmp_path, "NONE")["left"] == str(len(zk))
    # a dungeon is a zone like any other: its saved status counts
    dz = page_json["zones"][-1]["id"]
    assert _run_page_script(tmp_path, {"v": 1, "badges": 0, "zones": {dz: {"s": "failed"}}})["failed"] == "1"
