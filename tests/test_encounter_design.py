"""The encounter design's targets (docs/mechanics/ENCOUNTER_DESIGN.md section 8), measured on the COMPILED spawn pack.

Written by the test author, not by the session that designed or built the tables. Nothing here reads or imports
tools/build_encounters.py or tools/encounter_audit.py: the chances, the placement on the gym sequence, the families
and the stages are computed here, from sources the generator does not own.

Independent sources:
- the design document: the tier caps (section 2), the theme type sets (section 7), the Victory Road zones, staple and
  misfits (section 7a) and the eight targets with their numbers (section 8) are parsed from, or checked against,
  the document's own text, written before the tables were built;
- the compiled pack, from tools/compile_spawns.py main(["--out", tmp]): spawn_pool_world/{routes,subregions}/*.json
  and habitat_pools/vrc_*.json. A route spawn id is `<box id>_<sub-region id>_<species>`;
- the Cobblemon 1.8.0 jar (tools/battle_sim find_jar/load_pack/key, shared infrastructure): types, base stats,
  preEvolution and evolutions (so stages and families), and the type chart;
- Cobbleverse's best-spawner-config.json bucket weights (common 88.5, uncommon 10, rare 1.2, ultra-rare 0.3);
- the placement on the gym sequence measured HERE from the compiled boxes by the document's rule (section 1: a
  sub-region whose spawn boxes come within 128 blocks of a route's is on that route's leg, the earliest one; over
  128 from every route_01..08 is off the path; victory_road places nothing, as in tools/availability.py). route_0N
  is leg N; the victory_road corridor and the vrc_* pools are tier 9. derived/availability.json is
  checked to agree with it (that test SKIPS without the file; a skip is not a pass);
- data/encounter_design.json, ONLY for authored constants: a table's `tier` (used for off-path tables, and checked
  against the measured leg), `themes`, `water_body`, and `rules.themes` (checked equal to the document's section 7).

How a chance is computed (this file's own rule): within a context (land = grounded; water = surface, submerged,
seafloor) a bucket is drawn by its Cobbleverse weight renormalised over the buckets present in that context, then a
spawn within the bucket by its weight. A table is the union of its entries over all its boxes; an entry with a
timeRange counts as present at all times. Base-stat means are spawn-chance weighted within a table's land context,
then averaged over tables with equal weight per table.

Hearts (section 10, 2026-10-02): a sub-region file holds its base table and, for 28 places, a heart's added rows.
split_heart() tells them apart from the compiled condition alone (a `minY`, or a box set other than the base's).
Targets 1, 4 (strength) and 5 read the BASE rows, the table a player meets across the place; the other targets
read the file's union, as before. Section 10's own limits on the heart are in tests/test_encounter_hearts.py.

Not covered, and it needs a running server or a world: real spawn rates (Cobblemon's per-position weights, the
spawn caps, the biome and block conditions, day and night), whether a player actually meets a table on the leg
the geometry puts it on, whether a wild Pokemon over the cap really breaks free, the client's rendering (target 8
reads only the manifest's list of substitute dolls), the marine bands, waterways and unrelated habitat pools, and the
upstream pools the suppression leaves live.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import battle_sim as BS  # noqa: E402  shared infrastructure: the jar's species and type chart
import compile_spawns as CS  # noqa: E402  the compiler, run only to produce the pack under test

DOC = (ROOT / "docs" / "mechanics" / "ENCOUNTER_DESIGN.md").read_text(encoding="utf-8")
DESIGN = json.loads((ROOT / "data" / "encounter_design.json").read_text(encoding="utf-8"))
SPAWNER = json.loads((ROOT / "base-pack" / "cobbleverse" / "config" / "cobblemon" / "spawning"
                      / "best-spawner-config.json").read_text(encoding="utf-8"))
BUCKET_WEIGHT = {b["name"]: float(b["weight"]) for b in SPAWNER["buckets"]}
ATM_SUBSET = ROOT / "modpack" / "manifest" / "client-pack-atm-subset.json"
AVAILABILITY = ROOT / "derived" / "availability.json"

LAND = ("grounded",)
WATER = ("surface", "submerged", "seafloor")
CONTEXTS = {"land": LAND, "water": WATER}


def section(n):
    """The text of section `n` of the design document, whitespace collapsed."""
    m = re.search(r"^## %s\. .*?(?=^## |\Z)" % re.escape(n), DOC, re.S | re.M)
    assert m, "section %s of ENCOUNTER_DESIGN.md is gone" % n
    return m.group(0)


def flat(text):
    return re.sub(r"\s+", " ", text)


S8 = flat(section("8"))

# Section 2: tier -> (cap, band low, band high), parsed from the document's table.
TIER_CAP = {int(t): int(c) for t, c, _lo, _hi in re.findall(r"\|\s*(\d)\s*\|\s*(\d+)\s*\|\s*(\d+)-(\d+)\s*\|",
                                                             section("2"))}

# Section 7: theme name -> type set, parsed from the document's table ("meadow, plains, heath" share one set).
DOC_THEMES = {}
for _names, _types in re.findall(r"^\|\s*([a-z][^|]*?)\s*\|\s*([a-z][^|]*?)\s*\|\s*$", section("7"), re.M):
    for _n in _names.split(","):
        DOC_THEMES[re.sub(r"\s*\(.*\)", "", _n).strip()] = {t.strip() for t in _types.split(",")}

# Section 8, target 1: the evolved-share floors, parsed from the document.
_m = re.search(r"evolved share of those tables is at least ([\d., ]+?) on tiers 1-8 and ([\d.]+) at tier 9", S8)
assert _m, "target 1's evolved-share floors are no longer stated in section 8"
EVOLVED_FLOOR = dict(enumerate([float(x) for x in _m.group(1).split(",")], start=1))
EVOLVED_FLOOR[9] = float(_m.group(2))

# Section 8, target 7: the gyms' types in leg order.
_m = re.search(r"super-effective against that leg's gym \(([^)]*)\)", S8)
assert _m, "target 7's gym types are no longer stated in section 8"
GYM_TYPE = {i: t.strip().lower() for i, t in enumerate(_m.group(1).split(","), start=1)}

# Numbers this file hardcodes; test_the_thresholds_here_are_the_documents checks each against section 8's text.
VR_BST_MIN = 480            # target 1
VR_FINAL_SHARE = 0.85       # target 2
VR_SPECIES_MAX = 0.30       # target 2
VR_STAPLE_MAX = 1 / 3       # target 2 ("at most a third")
WATER_TABLES_MAX = 2        # target 3
WATER_OVERLAP_MAX = 0.35    # target 3
FIND_BST_MIN = 480          # target 4
THEME_SHARE_MIN = 0.70      # target 6
GYM_ANSWERS_MIN = 2         # target 7 ("at least two families")
MARGIN = 128                # section 1: "within 128 blocks of one"
MISFITS = ("excadrill", "quagsire", "whiscash", "boldore", "graveler")   # section 7a / target 2
STAPLE = ("crobat", "steelix", "golem")                                   # section 7a
# Section 7a's themed zones (Drowned Gallery, Slagworks, Bloom, Raw Tear, Abandoned Cut) and their core tiles;
# vrc_cave is the unthemed cave.
THEMED_ZONES = ("vrc_drowned", "vrc_slagworks", "vrc_bloom", "vrc_raw_tear", "vrc_abandoned_cut")


# ------------------------------------------------------------------ inputs

@pytest.fixture(scope="session")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("encounter_design_pack")
    CS.main(["--out", str(out)])
    base = out / "data" / "cobblers"
    assert (base / "spawn_pool_world" / "subregions").is_dir()
    return base


@pytest.fixture(scope="session")
def jar():
    try:
        species, _moves, chart = BS.load_pack(BS.find_jar())
    except BS.SimError as exc:
        pytest.skip("no Cobblemon 1.8 jar: stages, stats and types come from it (%s)" % exc)
    return Dex(species, chart)


class Dex:
    """Stages, families, stats and types from the jar."""

    def __init__(self, species, chart):
        self.sp = species
        self.chart = chart
        self.parent = {}
        self.children = {}
        for k, d in species.items():
            pre = BS.key((d.get("preEvolution") or "").split()[0]) if d.get("preEvolution") else None
            if pre in species:
                self.parent[k] = pre
            for ev in d.get("evolutions") or []:
                res = BS.key(str(ev.get("result") or "").split()[0])
                if res in species and res != k:
                    self.children.setdefault(k, set()).add(res)
                    self.parent.setdefault(res, k)

    def get(self, name):
        k = BS.key(str(name).split()[0])
        assert k in self.sp, "species %r is not in the Cobblemon jar" % name
        return k

    def root(self, name):
        k, seen = self.get(name), set()
        while k in self.parent and k not in seen:
            seen.add(k)
            k = self.parent[k]
        return k

    def members(self, root):
        out, todo = set(), [root]
        while todo:
            k = todo.pop()
            if k not in out:
                out.add(k)
                todo.extend(self.children.get(k, ()))
        return out

    def evolved(self, name):
        return self.get(name) in self.parent

    def final_or_single(self, name):
        return not self.children.get(self.get(name))

    def bst(self, name):
        return sum(self.sp[self.get(name)]["baseStats"].values())

    def final_bst(self, root):
        return max(self.bst(m) for m in self.members(root) if not self.children.get(m))

    def types(self, name):
        # a regional form ("sandshrew alolan") has its own types in the species' forms list: Alolan Sandshrew is
        # Ice/Steel, not Ground. Without this the snow theme read 0% at the Frostpeak strand (2026-10-02).
        d = self.sp[self.get(name)]
        parts = str(name).split()
        if len(parts) > 1 and parts[1] in REGIONAL:
            for f in d.get("forms") or []:
                if str(f.get("name") or "").lower() == REGIONAL[parts[1]] and f.get("primaryType"):
                    d = f
                    break
        return {t.lower() for t in (d.get("primaryType"), d.get("secondaryType")) if t}


REGIONAL = {"alolan": "alola", "galarian": "galar", "hisuian": "hisui", "paldean": "paldea"}


def species_of(entry):
    """The species key, keeping a regional aspect ("sandshrew alolan") so its form's types can be read."""
    parts = str(entry.get("pokemon") or entry.get("species") or "").lower().split()
    base = BS.key(parts[0]) if parts else ""
    return base + " " + parts[1] if len(parts) > 1 and parts[1] in REGIONAL else base


def level_range(s):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(s))
    if m:
        return int(m.group(1)), int(m.group(2))
    assert str(s).strip().isdigit(), "unreadable level %r" % s
    return int(s), int(s)


def details(path):
    return json.loads(path.read_text(encoding="utf-8")).get("spawns") or []


def rows_of(spawns):
    """Distinct spawns: (species, bucket, position type, weight, lo, hi, timeRange), union over their boxes."""
    rows = set()
    for e in spawns:
        lo, hi = level_range(e.get("level") or e.get("levelRange"))
        rows.add((species_of(e), e["bucket"], e.get("spawnablePositionType", "grounded"), float(e["weight"]), lo, hi,
                  json.dumps((e.get("condition") or {}).get("timeRange") or e.get("timeRange"))))
    return rows


def table_rows(path):
    """A pool's distinct spawns, union over its boxes (a sub-region's heart included)."""
    return rows_of(details(path))


BOX_KEYS = ("minX", "minZ", "maxX", "maxZ")


def box_of(e):
    c = e.get("condition") or {}
    return tuple(c.get(k) for k in BOX_KEYS)


def detail_signature(e):
    """Everything a compiled detail says except its id and its box: the spawn it is, wherever it is."""
    c = {k: v for k, v in (e.get("condition") or {}).items() if k not in BOX_KEYS}
    return json.dumps([{k: v for k, v in e.items() if k not in ("id", "condition")}, c], sort_keys=True)


def columns_of(box_set):
    """How many (x, z) columns a set of inclusive boxes covers, overlaps counted once."""
    bs = np.array(sorted(box_set), dtype=np.int64).reshape(-1, 4)
    if len(bs) == 0:
        return 0
    x0, z0 = bs[:, 0].min(), bs[:, 1].min()
    mask = np.zeros((int(bs[:, 3].max() - z0 + 1), int(bs[:, 2].max() - x0 + 1)), dtype=bool)
    for a, b, c, d in bs:
        mask[b - z0:d - z0 + 1, a - x0:c - x0 + 1] = True
    return int(mask.sum())


def mega_den_ranges():
    """[(anchor x, anchor z, leash, {line species})] of the Mega field's dens, from data/gulch_mine.json (farms field_*,
    mega_field.families.lines by the den's species). Read from the data, never from tools/compile_spawns.py."""
    gm = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))
    lines = ((gm.get("mega_field") or {}).get("families") or {}).get("lines") or {}
    return [(d["anchor"][0], d["anchor"][2], d["leash"], set(lines.get(d["species"]) or []))
            for fa in gm.get("farms") or [] if fa["id"].startswith("field_") for d in fa["dens"]]


def split_den_lines(spawns, dens=None):
    """(other details, den-line details) of one compiled file. The Mega field's dens carry their evolution lines as
    natural spawns over each den's range (the owner, 2026-10-05: "have some base mons of each version running around in
    the area as well as the megas"). They are not a heart (section 10's hearts are `<sub>_h<n>_` and add above-cap
    presences; these are the den's own line inside its range), so they are taken out before split_heart: a detail is a
    den line when its species is in a den's line and every corner column of its box is inside that den's range
    (hypot to the anchor <= leash). Nothing here reads the id; test_encounter_hearts checks the split against the ids."""
    dens = mega_den_ranges() if dens is None else dens
    rest, den = [], []
    for e in spawns:
        c = e.get("condition") or {}
        hit = False
        if all(k in c for k in ("minX", "maxX", "minZ", "maxZ")):
            corners = [(x, z) for x in (c["minX"], c["maxX"]) for z in (c["minZ"], c["maxZ"])]
            hit = any(e.get("pokemon") in line and all((x - ax) ** 2 + (z - az) ** 2 <= L * L for x, z in corners)
                      for ax, az, L, line in dens)
        (den if hit else rest).append(e)
    return rest, den


def split_heart(spawns):
    """(base details, heart details) of one compiled sub-region file, told apart by the compiled condition alone.

    Section 10: a table may carry one heart; its entries ADD to the base inside the heart, a summit heart's
    entries carry `minY` (section 9: the only entries that do), and a focus heart's cover a circle of the
    sub-region's cells. So in the compiled file every base spawn spans the same box set -- the whole place, the
    largest -- and a heart spawn either carries `minY` or spans a different (smaller) box set. Nothing here reads
    the id or the generator; test_the_condition_split_agrees_with_the_documented_heart_ids checks it against the
    id convention section 10 states.
    """
    spans = {}
    for e in spawns:
        spans.setdefault(detail_signature(e), set()).add(box_of(e))
    if not spans:
        return [], []
    base_set = max({frozenset(v) for v in spans.values()}, key=lambda s: (columns_of(s), len(s)))
    base, heart = [], []
    for e in spawns:
        in_base = frozenset(spans[detail_signature(e)]) == base_set and "minY" not in (e.get("condition") or {})
        (base if in_base else heart).append(e)
    return base, heart


def chances(rows, context):
    """species -> chance of being the spawn, within one context (this file's own rule, see the docstring)."""
    rs = [r for r in rows if r[2] in CONTEXTS[context] and r[3] > 0]
    by_bucket = {}
    for r in rs:
        by_bucket.setdefault(r[1], []).append(r)
    total_bw = sum(BUCKET_WEIGHT[b] for b in by_bucket)
    out = {}
    for b, members in by_bucket.items():
        w = sum(r[3] for r in members)
        for r in members:
            out[r[0]] = out.get(r[0], 0.0) + BUCKET_WEIGHT[b] / total_bw * r[3] / w
    return out


def boxes(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    bs = [(c["minX"], c["minZ"], c["maxX"], c["maxZ"]) for c in (e.get("condition") or {} for e in d["spawns"])
          if "minX" in c]
    return np.array(sorted(set(bs)), dtype=np.int64).reshape(-1, 4)


def box_gap(a, b):
    """Shortest Chebyshev gap between any box of a and any box of b (0 where they touch or overlap)."""
    if len(a) == 0 or len(b) == 0:
        return None
    dx = np.maximum(0, np.maximum(a[:, None, 0] - b[None, :, 2], b[None, :, 0] - a[:, None, 2]))
    dz = np.maximum(0, np.maximum(a[:, None, 1] - b[None, :, 3], b[None, :, 1] - a[:, None, 3]))
    return int(np.maximum(dx, dz).min())


@pytest.fixture(scope="session")
def world(pack):
    """Every table, its rows, and where it sits on the gym sequence."""
    pw = pack / "spawn_pool_world"
    route_leg = {}
    for p in sorted((pw / "routes").glob("*.json")):
        m = re.match(r"route_0(\d)_", p.stem)
        route_leg[p.stem] = int(m.group(1)) if m else (9 if p.stem == "victory_road" else None)
    assert None not in route_leg.values(), route_leg
    route_boxes = {r: boxes(pw / "routes" / ("%s.json" % r)) for r in route_leg}
    route_rows = {r: table_rows(pw / "routes" / ("%s.json" % r)) for r in route_leg}

    # Placement walks route_01..08 only, as tools/availability.py does (section 1 defers to it): victory_road is
    # not a leg a sub-region is placed on, so the Rift is off the path here and its tier is a raised one.
    legs = {r: rb for r, rb in route_boxes.items() if route_leg[r] <= 8}
    dens_of = mega_den_ranges()
    subs = {}
    for p in sorted((pw / "subregions").glob("*.json")):
        b = boxes(p)
        gaps = {r: box_gap(b, rb) for r, rb in legs.items()}
        near = [route_leg[r] for r, g in gaps.items() if g is not None and g <= MARGIN]
        nearest = min((g, route_leg[r], r) for r, g in gaps.items() if g is not None)
        authored = (DESIGN["tables"].get(p.stem) or {}).get("tier")
        spawns = details(p)
        rest, den = split_den_lines(spawns, dens_of)
        base, heart = split_heart(rest)
        subs[p.stem] = {"rows": rows_of(spawns), "base_rows": rows_of(base), "heart_rows": rows_of(heart),
                        "base": base, "heart": heart, "den": den,
                        "on_path": bool(near), "leg": min(near) if near else None,
                        "nearest": nearest, "authored_tier": authored,
                        "tier": min(near) if near else (authored if authored is not None else nearest[1])}
    vrc = {}
    for p in sorted((pack / "habitat_pools").glob("vrc_*.json")):
        rows = table_rows(p)
        vrc[p.stem] = {"rows": rows, "base_rows": rows, "heart_rows": set(), "on_path": True, "leg": 9, "tier": 9}
    assert len(subs) == 63, "section 1 counts 63 sub-region tables; the pack has %d" % len(subs)
    assert len(vrc) == 11, "section 1 counts 11 Victory Road pools; the pack has %d" % len(vrc)
    return {"subs": subs, "vrc": vrc, "route_leg": route_leg, "route_rows": route_rows, "route_boxes": route_boxes,
            "route_details": {r: details(pw / "routes" / ("%s.json" % r)) for r in route_leg}}


def all_tables(world):
    return {**world["subs"], **world["vrc"]}


def land_bst(dex, rows):
    ch = chances(rows, "land")
    return sum(p * dex.bst(s) for s, p in ch.items()) if ch else None


def evolved_share(dex, rows):
    ch = chances(rows, "land")
    return sum(p for s, p in ch.items() if dex.evolved(s)) if ch else None


def tier_means(dex, tables, measure, rows="rows"):
    by = {}
    for name, t in tables.items():
        v = measure(dex, t[rows])
        if v is not None:
            by.setdefault(t["tier"], []).append(v)
    return {k: sum(v) / len(v) for k, v in sorted(by.items())}


def on_path_tables(world):
    return {k: t for k, t in all_tables(world).items() if t["on_path"]}


def off_path_tables(world):
    return {k: t for k, t in world["subs"].items() if not t["on_path"]}


# ------------------------------------------------------------------ the test's own inputs agree with their sources

def test_the_thresholds_here_are_the_documents():
    # Without it a threshold could be edited here until the data passed, and nothing would say it left the doc.
    for phrase in ("Victory Road's is at least 480", "at least 85% of the spawns", "no one species is over 30% of a context",
                   "the staple is at most a third", "Excadrill, Quagsire, Whiscash, Boldore and Graveler",
                   "in more than two sub-region water tables", "share at most 35% of their probability",
                   "final-stage total of 480 or more", "at least 70% of the spawns", "at least two families",
                   "No spawn in a table is above its tier's cap"):
        assert phrase in S8, "section 8 no longer says %r" % phrase
    assert "within 128 blocks" in flat(section("1"))
    assert "(Crobat, Steelix, Golem)" in flat(section("7a"))
    for zone in ("Drowned Gallery", "Slagworks", "Bloom", "Raw Tear", "Abandoned Cut"):
        assert zone in flat(section("7a"))
    assert TIER_CAP == {1: 20, 2: 25, 3: 30, 4: 35, 5: 40, 6: 45, 7: 50, 8: 55, 9: 60}, TIER_CAP
    assert len(EVOLVED_FLOOR) == 9 and len(GYM_TYPE) == 8


def test_authored_theme_sets_are_the_documents():
    # Without it data/encounter_design.json could widen a theme's types and target 6 would pass on the widened set.
    authored = {k: set(v) for k, v in DESIGN["rules"]["themes"].items()}
    assert set(authored) <= set(DOC_THEMES), sorted(set(authored) - set(DOC_THEMES))
    wrong = {k: sorted(authored[k] ^ DOC_THEMES[k]) for k in authored if authored[k] != DOC_THEMES[k]}
    assert not wrong, wrong
    used = {th for t in list(DESIGN["tables"].values()) + [h for k, h in DESIGN["habitats"].items()
                                                              if isinstance(h, dict)] for th in t.get("themes", [])}
    assert used <= set(DOC_THEMES), sorted(used - set(DOC_THEMES))


def test_placement_measured_here_agrees_with_availability_json(world):
    # Without it this file's placement rule and tools/availability.py's could drift apart unnoticed, and the
    # targets would be measured on legs the rest of the project does not use.
    if not AVAILABILITY.is_file():
        pytest.skip("derived/availability.json is absent: run python tools/compile_spawns.py then "
                    "python tools/availability.py --write")
    av = json.loads(AVAILABILITY.read_text(encoding="utf-8"))
    listed = {}
    for g, rows in av["gyms"].items():
        for r in rows:
            if r["kind"] == "subregion":
                listed[r["pool"]] = min(listed.get(r["pool"], 99), int(g))
    subs = world["subs"]
    wrong = {k: (g, subs[k]["leg"]) for k, g in listed.items() if subs[k]["leg"] != g}
    assert not wrong, "pool: (availability.json's gym, measured leg) %s" % wrong
    # and every pool it calls off-route is off here, with the same nearest route
    off_here = {k: t["nearest"][2] for k, t in subs.items() if not t["on_path"]}
    assert off_here == {k: v["nearest_route"] for k, v in av["off_route"].items() if v["kind"] == "subregion"}


def test_on_path_tables_carry_the_tier_of_the_leg_they_are_met_on(world):
    # Without it an on-path table could be authored a tier late (higher levels, more evolved) and escalation,
    # caps and gym answers would all be judged against the wrong leg (section 1).
    wrong = {k: (t["authored_tier"], t["leg"]) for k, t in world["subs"].items()
             if t["on_path"] and t["authored_tier"] != t["leg"]}
    assert not wrong, "table: (authored tier, measured leg) %s" % wrong


def test_off_path_tables_are_never_a_tier_before_their_nearest_route(world):
    # Without it an off-path table could be authored early, which lowers its cap and its expected strength, or
    # raised without the written reason section 1 requires.
    tables = DESIGN["tables"]
    early, unexplained = {}, []
    for k, t in world["subs"].items():
        if t["on_path"]:
            continue
        gap, leg, route = t["nearest"]
        if t["authored_tier"] is None or t["authored_tier"] < leg:
            early[k] = (t["authored_tier"], route, leg)
        elif t["authored_tier"] > leg and not (tables[k].get("tier_why") or "").strip():
            unexplained.append(k)
    assert not early, "table: (authored tier, nearest route, its leg) %s" % early
    assert not unexplained, "raised above the nearest route's leg without tier_why: %s" % unexplained


# ------------------------------------------------------------------ target 1: escalation

def test_on_path_land_strength_never_falls_from_one_tier_to_the_next(world, jar):
    # Without it a later leg could again offer the same or weaker land Pokemon than an earlier one, the flat
    # roster the owner rejected on 2026-10-02 (target 1). Measured on the BASE tables: a heart covers at most a
    # ninth of its place (section 10), so its rows are not what a player meets across the leg; the hearts are
    # checked on their own in tests/test_encounter_hearts.py.
    means = tier_means(jar, on_path_tables(world), land_bst, rows="base_rows")
    tiers = sorted(means)
    falls = [(a, round(means[a]), b, round(means[b])) for a, b in zip(tiers, tiers[1:]) if means[b] < means[a]]
    assert not falls, "mean land BST falls (tier, mean, next tier, mean): %s; all: %s" % (
        falls, {k: round(v) for k, v in means.items()})


def test_victory_road_mean_strength_is_at_least_480(world, jar):
    # Without it Victory Road could again feel like the middle of the journey, not its end (target 1).
    vals = [land_bst(jar, t["rows"]) for t in world["vrc"].values()]
    vals = [v for v in vals if v is not None]
    mean = sum(vals) / len(vals)
    assert mean >= VR_BST_MIN, "Victory Road's mean land BST is %.0f" % mean


def test_on_path_evolved_share_meets_each_tiers_floor(world, jar):
    # Without it evolved stages could stay absent from late legs and the families would never move up (target 1).
    means = tier_means(jar, on_path_tables(world), evolved_share)
    short = {k: (round(v, 3), EVOLVED_FLOOR[k]) for k, v in means.items() if v < EVOLVED_FLOOR[k]}
    assert not short, "tier: (evolved share, floor) %s" % short


# ------------------------------------------------------------------ target 2: Victory Road

def test_victory_road_pools_are_final_or_single_stage(world, jar):
    # Without it Victory Road could again be full of middle stages (Boldore, Graveler) a player met legs ago.
    short = {}
    for name, t in world["vrc"].items():
        for ctx in CONTEXTS:
            ch = chances(t["rows"], ctx)
            if ch:
                share = sum(p for s, p in ch.items() if jar.final_or_single(s))
                if share < VR_FINAL_SHARE:
                    short["%s/%s" % (name, ctx)] = round(share, 3)
    assert not short, "final-or-single share under %.2f: %s" % (VR_FINAL_SHARE, short)


def test_no_victory_road_species_dominates_a_context(world):
    # Without it one species could again be most of what a Victory Road zone shows (target 2).
    over = {}
    for name, t in world["vrc"].items():
        for ctx in CONTEXTS:
            for s, p in chances(t["rows"], ctx).items():
                if p > VR_SPECIES_MAX:
                    over["%s/%s/%s" % (name, ctx, s)] = round(p, 3)
    assert not over, over


def test_the_cave_staple_is_at_most_a_third_of_a_themed_zone(world):
    # Without it Crobat, Steelix and Golem could swamp the zones whose themes are the point of them (target 2).
    zones = [k for k in world["vrc"] if any(k == z or k == z + "_core" for z in THEMED_ZONES)]
    assert len(zones) == 10, zones
    over = {}
    for name in zones:
        for ctx in CONTEXTS:
            ch = chances(world["vrc"][name]["rows"], ctx)
            share = sum(ch.get(s, 0.0) for s in STAPLE)
            if share > VR_STAPLE_MAX + 1e-9:
                over["%s/%s" % (name, ctx)] = round(share, 3)
    assert not over, over


def test_the_owners_named_misfits_are_out_of_victory_road(world):
    # Without it Excadrill, Quagsire, Whiscash, Boldore or Graveler could return to the end of the journey (target 2).
    found = {name: sorted({r[0] for r in t["rows"]} & set(MISFITS)) for name, t in world["vrc"].items()}
    found = {k: v for k, v in found.items() if v}
    assert not found, found


# ------------------------------------------------------------------ target 3: waters

def water_tables(world):
    return {k: t for k, t in world["subs"].items() if chances(t["rows"], "water")}


def test_no_water_species_is_in_more_than_two_water_tables(world):
    # Without it one water template could again be pasted into many lakes (target 3).
    where = {}
    for name, t in water_tables(world).items():
        for s in chances(t["rows"], "water"):
            where.setdefault(s, []).append(name)
    over = {s: len(v) for s, v in where.items() if len(v) > WATER_TABLES_MAX}
    assert not over, "species: water tables %s" % dict(sorted(over.items(), key=lambda kv: -kv[1]))


@pytest.mark.parametrize("species", ["magikarp", "goldeen"])
def test_magikarp_and_goldeen_are_each_in_at_most_two_water_tables(world, species):
    # Without it the two fish the audit found in most lakes could spread again (target 3, named).
    where = sorted(k for k, t in water_tables(world).items() if species in chances(t["rows"], "water"))
    assert len(where) <= WATER_TABLES_MAX, "%s in %d water tables: %s" % (species, len(where), where)


def test_a_water_family_in_two_tables_shows_a_new_stage_in_the_later(world, jar):
    # Without it the same family at the same stage could fill two waters; section 5 allows two tables only when
    # the later one shows a different stage.
    where = {}
    for name, t in water_tables(world).items():
        for s in chances(t["rows"], "water"):
            where.setdefault(jar.root(s), {}).setdefault(name, set()).add(s)
    over, same = {}, {}
    for fam, tabs in where.items():
        if len(tabs) > WATER_TABLES_MAX:
            over[fam] = sorted(tabs)
        elif len(tabs) == 2:
            (a, sa), (b, sb) = sorted(tabs.items(), key=lambda kv: world["subs"][kv[0]]["tier"])
            if not (sb - sa):
                same[fam] = (a, b, sorted(sb))
    assert not over, "families in more than two water tables: %s" % over
    assert not same, "family: (earlier, later, later's stages, none new) %s" % same


def test_waters_on_different_bodies_share_at_most_35_percent(world):
    # Without it two different lakes could again be one water template under two names (target 3).
    tabs = water_tables(world)
    body = {k: (DESIGN["tables"].get(k) or {}).get("water_body") or ("own:" + k) for k in tabs}
    dist = {k: chances(t["rows"], "water") for k, t in tabs.items()}
    names = sorted(tabs)
    over = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if body[a] == body[b]:
                continue
            shared = sum(min(p, dist[b].get(s, 0.0)) for s, p in dist[a].items())
            if shared > WATER_OVERLAP_MAX + 1e-9:
                over["%s~%s" % (a, b)] = round(shared, 3)
    assert not over, "%d pairs over %.2f, e.g. %s" % (len(over), WATER_OVERLAP_MAX,
                                                        dict(sorted(over.items(), key=lambda kv: -kv[1])[:8]))


# ------------------------------------------------------------------ target 4: off the path

def on_path_families(world, dex):
    return {dex.root(r[0]) for t in on_path_tables(world).values() for r in t["rows"]}


def finds_of(world, dex):
    """off-path table -> its families that qualify as a find under target 4."""
    on = on_path_families(world, dex)
    out = {}
    for name, t in off_path_tables(world).items():
        out[name] = sorted({dex.root(r[0]) for r in t["rows"] if r[1] in ("rare", "uncommon")
                            and dex.root(r[0]) not in on and dex.final_bst(dex.root(r[0])) >= FIND_BST_MIN})
    return out


def test_every_off_path_table_has_a_find(world, jar):
    # Without it there is again nothing off the path worth the detour (target 4).
    off = off_path_tables(world)
    assert off, "no off-path sub-region tables measured; the placement rule found none"
    missing = sorted(k for k, v in finds_of(world, jar).items() if not v)
    assert not missing, "%d of %d off-path tables have no find: %s" % (len(missing), len(off), missing)


def test_no_route_corridor_carries_a_find(world, jar):
    # Without it a route could hand a player passing through the reward that belongs to whoever leaves it
    # (target 4). Vacuous where no off-path table has a find; test_every_off_path_table_has_a_find says so then.
    finds = {f for v in finds_of(world, jar).values() for f in v}
    members = {m: f for f in finds for m in jar.members(f)}
    carried = {r: sorted({members[row[0]] for row in rows if row[0] in members})
               for r, rows in world["route_rows"].items()}
    carried = {k: v for k, v in carried.items() if v}
    assert not carried, carried


def test_off_path_tables_are_no_weaker_than_on_path_at_the_same_tier(world, jar):
    # Without it a detour could be rarer but weaker, which is no reward (target 4). Base tables on both sides:
    # a heart's above-cap presences would otherwise make a place look stronger than most of it is (section 10).
    on = tier_means(jar, {k: t for k, t in world["subs"].items() if t["on_path"]}, land_bst, rows="base_rows")
    off = tier_means(jar, off_path_tables(world), land_bst, rows="base_rows")
    weaker = {k: (round(off[k]), round(on[k])) for k in sorted(set(on) & set(off)) if off[k] < on[k]}
    assert not weaker, "tier: (off-path mean BST, on-path mean BST) %s" % weaker


# ------------------------------------------------------------------ target 5: catchable

def test_no_spawn_in_a_base_table_is_above_its_tiers_cap(world):
    # Without it wild Pokemon a player cannot catch on that leg (they break free over the cap) could spread across
    # a whole place (target 5). Section 10 lets a heart exceed the cap, so this reads the base tables (every
    # sub-region's base rows, every Victory Road pool); the heart's own limits are in test_encounter_hearts.py.
    over = {}
    for name, t in all_tables(world).items():
        cap = TIER_CAP[t["tier"]]
        high = max((r[5] for r in t["base_rows"]), default=0)
        if high > cap:
            over[name] = (t["tier"], cap, high)
    assert not over, "table: (tier, cap, highest level in the base table) %s" % over


def test_no_route_corridor_spawn_is_above_its_legs_cap(world):
    # Without it a route corridor, which takes its sub-regions' families, could carry levels its own leg cannot catch.
    over = {}
    for r, rows in world["route_rows"].items():
        cap = TIER_CAP[world["route_leg"][r]]
        high = max((row[5] for row in rows), default=0)
        if high > cap:
            over[r] = (cap, high)
    assert not over, "route: (cap, highest level) %s" % over


# ------------------------------------------------------------------ target 6: legible

def test_each_table_and_context_reads_as_its_themes(world, jar):
    # Without it a marsh could stop reading as a marsh (target 6, section 7).
    themes_of = {k: v.get("themes") for k, v in DESIGN["tables"].items()}
    themes_of.update({k: v.get("themes") for k, v in DESIGN["habitats"].items() if isinstance(v, dict)})
    unthemed, short = [], {}
    for name, t in all_tables(world).items():
        if not themes_of.get(name):
            unthemed.append(name)
            continue
        allowed = set().union(*(DOC_THEMES[th] for th in themes_of[name]))
        for ctx in CONTEXTS:
            ch = chances(t["rows"], ctx)
            if not ch:
                continue
            ok = allowed | DOC_THEMES["water"] if ctx == "water" else allowed   # "water (any water half)"
            share = sum(p for s, p in ch.items() if jar.types(s) & ok)
            if share < THEME_SHARE_MIN:
                short["%s/%s" % (name, ctx)] = round(share, 3)
    assert not unthemed, "tables with no themes: %s" % unthemed
    assert not short, "under %.2f on theme: %s" % (THEME_SHARE_MIN, short)


# ------------------------------------------------------------------ target 7: gym answers

def test_each_leg_offers_two_families_that_hit_its_gym_super_effectively(world, jar):
    # Without it a leg could leave a player with no wild answer to the gym at its end (target 7).
    short = {}
    for leg, gtype in GYM_TYPE.items():
        row = jar.chart[gtype]
        se = {t.lower() for t, x in row.items() if x > 1.0}
        fams = {jar.root(r[0]) for t in world["subs"].values() if t["on_path"] and t["leg"] == leg
                for r in t["rows"] if jar.types(r[0]) & se}
        if len(fams) < GYM_ANSWERS_MIN:
            short[leg] = (gtype, sorted(fams))
    assert not short, "leg: (gym type, answering families) %s" % short


# ------------------------------------------------------------------ target 8: renders

def test_no_spawned_species_is_drawn_as_the_substitute_doll(pack):
    # Without it a player could meet a Pokemon the client draws as the stand-in doll (target 8).
    # Scope: the design's tables (sub-regions, Victory Road's pools) and the route corridors built from them. The
    # elder nests, waterways, marine bands and other habitat pools are outside this design (section 9) and are
    # not checked here.
    dolls = {BS.key(s) for s in json.loads(ATM_SUBSET.read_text(encoding="utf-8"))["species"]}
    files = (sorted((pack / "spawn_pool_world" / "subregions").glob("*.json"))
             + sorted((pack / "spawn_pool_world" / "routes").glob("*.json"))
             + sorted((pack / "habitat_pools").glob("vrc_*.json")))
    hits = {}
    for p in files:
        d = json.loads(p.read_text(encoding="utf-8"))
        for e in d.get("spawns") or []:
            s = species_of(e)
            if s in dolls:
                hits.setdefault(p.relative_to(pack).as_posix(), set()).add(s)
    assert not hits, {k: sorted(v) for k, v in hits.items()}
