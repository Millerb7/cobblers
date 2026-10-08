"""A placed structure's grounds with a roster of its own (data/spawns.json placement_sites), measured on the COMPILED pack.

Written by a test author, not by the session that built tools/compile_spawns.py placement_site_spawns (79f63ae). The
first sites are Poipole at the two pasted Necrozma towers (docs/mechanics/NETHER_ENCOUNTERS.md section 4).

Independent sources, none of them the generator's: a site's FOOTPRINT is its placement's corner (data/placements.json
position, corner anchor, rotation none) and its template's own footprint in data/structures.json ("46x90x45"), never
the placement's `size` the generator reads, nor the box list in a site's `why`; the containing sub-region is an
even-odd ray cast of this file's own over data/regions.json (not subregion_boxes.point_in_polygon), over the
footprint's four corners AND its centre; tier bands come from data/encounter_design.json rules.tiers and the caps from
ENCOUNTER_DESIGN.md section 2's table (test_encounter_design.TIER_CAP), with the sub-region's tier from
encounter_design.json tables (never spawns.json level_band, which the generator checks against); the species from the
Cobblemon 1.8.0 jar read with zipfile; the ground from tools/ground.py (the canonical heightmap) and the painted water
from tools/water_mask.py. The generator is imported only to be MUTATED (data untouched), to show each check bites.

What a site row is, without reading its id: a compiled detail whose species is one of a site's entries and whose box
lies inside the site's footprint widened by its margin (split_site_lines). The ids are then held against that split.

Not covered, and it needs a running server: that Cobblemon spawns a forced-canSeeSky grounded Poipole on the tower's
open grounds and its summit at the rate the rare bucket implies; that nothing spawns inside the shaft; whether a wild
Poipole's moveset already holds Dragon Pulse (so whether a wild one evolves at once); and whether the towers are
pasted at all -- both placements say "planned", and this file reads the plan, not the world. Rivers (data/rivers.json)
are not in tools/water_mask.py's painted water and are not checked here; the sub-region's base boxes, which the site
rows are clipped to, already leave out the compiled waterways.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))

import test_encounter_design as ED  # noqa: E402  the compiled pack and section 2's caps
from test_encounter_design import pack  # noqa: E402,F401  session fixture

DATA = ROOT / "data"
SITE_MECHANISM = "placement_coordinate_boxes"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def placement_sites():
    """[{id, placement, footprint (x0, x1, z0, z1) inclusive, margin, grounds (x0, x1, z0, z1), entries}] from the data:
    data/spawns.json placement_sites and their entries, data/placements.json for the corner, data/structures.json for
    the template's footprint. Fails on a placement this reading cannot translate (not corner-anchored, rotated)."""
    spawns = _load("spawns.json")
    placements = {p["id"]: p for p in _load("placements.json")["placements"] if isinstance(p, dict) and "id" in p}
    structures = {s["id"]: s for s in _load("structures.json")["structures"]}
    out = []
    for s in spawns.get("placement_sites") or []:
        p = placements[s["placement"]]
        assert p.get("anchor_mode") == "corner" and p.get("rotation") == "none", \
            "%s: %s is %s-anchored, rotation %s; this test reads corner and none only" % (
                s["id"], p["id"], p.get("anchor_mode"), p.get("rotation"))
        fx, _fy, fz = (int(v) for v in structures[p["template"]]["footprint"].split("x"))
        x0, z0 = int(p["position"]["x"]), int(p["position"]["z"])
        foot = (x0, x0 + fx - 1, z0, z0 + fz - 1)
        m = int(s["margin"])
        out.append({"id": s["id"], "placement": p["id"], "footprint": foot, "margin": m,
                    "grounds": (foot[0] - m, foot[1] + m, foot[2] - m, foot[3] + m),
                    "entries": [e for e in spawns["entries"]
                                if e.get("mechanism") == SITE_MECHANISM and e.get("scope") == s["id"]]})
    return out


def _box(e):
    c = e.get("condition") or {}
    if not all(k in c for k in ("minX", "maxX", "minZ", "maxZ")):
        return None
    return c["minX"], c["maxX"], c["minZ"], c["maxZ"]


def _inside(box, rect):
    return rect[0] <= box[0] and box[1] <= rect[1] and rect[2] <= box[2] and box[3] <= rect[3]


def split_site_lines(spawns, sites=None):
    """(other details, {site id: [site-line details]}) of one compiled file, by species and range, never by id: a site
    line is a detail whose species is one of a site's entries and whose box lies inside that site's grounds."""
    sites = placement_sites() if sites is None else sites
    rest, lines = [], {}
    for e in spawns:
        b = _box(e)
        hit = None
        if b is not None:
            hit = next((s["id"] for s in sites
                        if e.get("pokemon") in {x["species"] for x in s["entries"]} and _inside(b, s["grounds"])), None)
        if hit is None:
            rest.append(e)
        else:
            lines.setdefault(hit, []).append(e)
    return rest, lines


def site_id_pattern(site_id):
    return re.compile(r"_%s_b\d+_" % re.escape(site_id))


def _in_ring(ring, x, z):
    c, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, zi = ring[i]
        xj, zj = ring[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / float(zj - zi) + xi:
            c = not c
        j = i
    return c


def containing_subregions(foot):
    """{sub-region id} of data/regions.json whose polygons hold every corner of the footprint and its centre."""
    pts = [(foot[0], foot[2]), (foot[1], foot[2]), (foot[0], foot[3]), (foot[1], foot[3]),
           ((foot[0] + foot[1]) / 2.0, (foot[2] + foot[3]) / 2.0)]
    return {s["id"] for s in _load("regions.json")["subregions"]
            if all(any(_in_ring(r, x, z) for r in s["polygons"]) for x, z in pts)}


def tier_band_cap(sub):
    """(tier, band low, band high, cap) for a sub-region: the tier from encounter_design.json tables, the band from its
    rules.tiers, the cap from ENCOUNTER_DESIGN.md section 2's table."""
    ed = _load("encounter_design.json")
    tier = int(ed["tables"][sub]["tier"])
    lo, hi = ed["rules"]["tiers"][str(tier)]["band"]
    return tier, int(lo), int(hi), ED.TIER_CAP[tier]


def site_faults(pack_base):
    """[problem] for the compiled site lines of a pack, and the number of site lines read."""
    sites = placement_sites()
    by_file = {}
    for p in sorted((pack_base / "spawn_pool_world").rglob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and isinstance(doc.get("spawns"), list):
            by_file[p.relative_to(pack_base).as_posix()] = doc["spawns"]
    faults, read = [], 0
    for s in sites:
        homes = containing_subregions(s["footprint"])
        if len(homes) != 1:
            faults.append("%s: the footprint %s lies wholly in %d sub-regions %s, not one"
                          % (s["id"], s["footprint"], len(homes), sorted(homes)))
            continue
        home = homes.pop()
        want = "spawn_pool_world/subregions/%s.json" % home
        species = {e["species"] for e in s["entries"]}
        pat = site_id_pattern(s["id"])
        found = {}
        for rel, spawns in by_file.items():
            _rest, lines = split_site_lines(spawns, sites)
            named = [e for e in spawns if pat.search(str(e.get("id", "")))]
            mine = lines.get(s["id"], [])
            mine_ids = {e["id"] for e in mine}
            for e in named:
                if e["id"] not in mine_ids:   # named for the site, but not a site species inside its grounds
                    faults.append("%s in %s: %s (%s, box %s) leaves the grounds %s or is not a site species"
                                  % (s["id"], rel, e["id"], e.get("pokemon"), _box(e), s["grounds"]))
            named_ids = {e["id"] for e in named}
            for e in mine:
                if e["id"] not in named_ids:
                    faults.append("%s in %s: %s is a site species inside the grounds whose id names no site"
                                  % (s["id"], rel, e["id"]))
            if mine:
                found[rel] = mine
        if set(found) != {want}:
            faults.append("%s: its lines are in %s; the sub-region holding the footprint is %s"
                          % (s["id"], sorted(found), home))
            continue
        rows = found[want]
        read += len(rows)
        # the grounds: every box inside footprint + margin, the footprint covered, every side of the margin reached
        boxes = [_box(e) for e in rows]
        g, f = s["grounds"], s["footprint"]
        for e, b in zip(rows, boxes):
            if not _inside(b, g):
                faults.append("%s: %s box %s leaves the grounds %s (footprint %s + margin %d)"
                              % (s["id"], e["id"], b, g, f, s["margin"]))
        for sp in species:
            sb = [b for e, b in zip(rows, boxes) if e["pokemon"] == sp]
            covered = {(x, z) for b in sb for x in range(max(b[0], f[0]), min(b[1], f[1]) + 1)
                       for z in range(max(b[2], f[2]), min(b[3], f[3]) + 1)}
            need = (f[1] - f[0] + 1) * (f[3] - f[2] + 1)
            if len(covered) != need:
                faults.append("%s: %s covers %d of the footprint's %d columns" % (s["id"], sp, len(covered), need))
            bbox = (min(b[0] for b in sb), max(b[1] for b in sb), min(b[2] for b in sb), max(b[3] for b in sb))
            if bbox != g:
                faults.append("%s: %s spans %s, not the grounds %s" % (s["id"], sp, bbox, g))
        # levels, bucket, weight and position against the authored entry and the tier
        tier, lo_b, hi_b, cap = tier_band_cap(home)
        auth = {e["species"]: e for e in s["entries"]}
        for e in rows:
            a = auth[e["pokemon"]]
            lo, hi = (int(v) for v in str(e["level"]).split("-"))
            if e["level"] != a["level"]:
                faults.append("%s: level %s, authored %s" % (e["id"], e["level"], a["level"]))
            if lo < lo_b or hi > hi_b or hi > cap:
                faults.append("%s: level %s outside %s's tier %d band %d-%d or over its cap %d"
                              % (e["id"], e["level"], home, tier, lo_b, hi_b, cap))
            if str(a.get("eligibility_reason", "")).startswith("find") and 2 * lo < lo_b + hi_b:
                faults.append("%s: a find from level %d, below the top half of %d-%d" % (e["id"], lo, lo_b, hi_b))
            if (e["bucket"], e["weight"], e["spawnablePositionType"]) != (a["bucket"], a["weight"],
                                                                          a["spawnable_position"]):
                faults.append("%s: %s/%s/%s, authored %s/%s/%s" % (e["id"], e["bucket"], e["weight"],
                              e["spawnablePositionType"], a["bucket"], a["weight"], a["spawnable_position"]))
            if a["spawnable_position"] == "grounded" and (e.get("condition") or {}).get("canSeeSky") is not True:
                faults.append("%s: a grounded row without canSeeSky true" % e["id"])
    return faults, read


# ------------------------------------------------------------------ the data and the compiled pack

def test_every_placement_site_has_entries_and_a_translatable_placement():
    # Without it a site could name no placement, or carry no entry, and every check below would read nothing.
    sites = placement_sites()
    assert sites, "data/spawns.json has no placement_sites; this file exercises nothing"
    assert all(s["entries"] for s in sites), [s["id"] for s in sites if not s["entries"]]
    scoped = {e["scope"] for e in _load("spawns.json")["entries"] if e.get("mechanism") == SITE_MECHANISM}
    assert scoped <= {s["id"] for s in sites}, sorted(scoped - {s["id"] for s in sites})


def test_compiled_site_lines_sit_on_their_grounds_in_their_subregion_and_band(pack):
    # Without it a site's rows could land in a sub-region that does not hold the structure, leave its grounds, miss
    # the footprint, or spawn outside the tier's band and over its cap, and nothing would say so.
    faults, read = site_faults(pack)
    assert not faults, faults[:5]
    assert read, "no site line was read; the check exercised nothing"


def test_the_site_species_exist_in_the_cobblemon_jar():
    # Without it a site could name a species the 1.8.0 jar does not ship (a typo, a doll), and the pool would hold a
    # row Cobblemon drops at load.
    try:
        jar = ED.BS.find_jar()
    except ED.BS.SimError as exc:
        pytest.skip("no Cobblemon 1.8 jar (%s): a skip is not a pass" % exc)
    with zipfile.ZipFile(jar) as z:
        names = {Path(n).stem: n for n in z.namelist() if n.startswith("data/cobblemon/species/") and n.endswith(".json")}
        missing, unimplemented = [], []
        for s in placement_sites():
            for e in s["entries"]:
                n = names.get(e["species"])
                if n is None:
                    missing.append(e["species"])
                elif json.loads(z.read(n)).get("implemented") is not True:
                    unimplemented.append(e["species"])
    assert not missing and not unimplemented, (missing, unimplemented)


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain
    try:
        return G.load()
    except terrain.TerrainUnavailable as exc:
        pytest.skip("no canonical heightmap (%s): the grounds' dryness needs it; a skip is not a pass" % exc)


def test_every_site_line_column_is_dry_land(pack, ground):
    # Without it a grounded, forced-canSeeSky site row could cover sea or a painted lake, where it can never spawn.
    import water_mask as W
    bodies, sea = W.bodies(), W.sea_level()
    wet, cols = [], 0
    for s in placement_sites():
        for rel_spawns in (json.loads(p.read_text(encoding="utf-8"))["spawns"]
                           for p in sorted((pack / "spawn_pool_world" / "subregions").glob("*.json"))):
            for e in split_site_lines(rel_spawns)[1].get(s["id"], []):
                if e.get("spawnablePositionType") != "grounded":
                    continue
                b = _box(e)
                for x in range(b[0], b[1] + 1):
                    for z in range(b[2], b[3] + 1):
                        cols += 1
                        body, _lvl = W.level_at(x, z, ground, bodies, sea)
                        if body is not None or ground(x, z) <= sea:
                            wet.append((s["id"], x, z, body, ground(x, z)))
    assert cols, "no grounded site column was read"
    assert not wet, (len(wet), wet[:5])


# ---- independence: the generator MUTATED, the data untouched; the site check must catch each mutation ----

from test_encounter_hearts import mutant, mutant_pack  # noqa: E402


@pytest.mark.parametrize("label, old, new, expect", [
    ("margin one wider on the east", "box = (x0 - m, x0 + sx - 1 + m, z0 - m, z0 + sz - 1 + m)",
     "box = (x0 - m, x0 + sx + m, z0 - m, z0 + sz - 1 + m)", "leaves the grounds"),
    ("margin one short on the south", "box = (x0 - m, x0 + sx - 1 + m, z0 - m, z0 + sz - 1 + m)",
     "box = (x0 - m, x0 + sx - 1 + m, z0 - m, z0 + sz - 2 + m)", "not the grounds"),
    ("rows filed in the wrong sub-region",
     "out.setdefault(sub, []).extend(rows)\n        summ.setdefault(sub, []).append({\"site\": sid",
     "out.setdefault(sorted(set(bands) - {sub})[0], []).extend(rows)\n        summ.setdefault(sub, []).append("
     "{\"site\": sid", "the sub-region holding the footprint"),
    ("a level written over the cap",
     "e[\"species\"].replace(\" \", \"_\")),\n                             \"pokemon\": e[\"species\"], \"type\": "
     "\"pokemon\", \"spawnablePositionType\": position_type(e),\n                             \"bucket\": e[\"bucket\"], "
     "\"level\": e[\"level\"],",
     "e[\"species\"].replace(\" \", \"_\")),\n                             \"pokemon\": e[\"species\"], \"type\": "
     "\"pokemon\", \"spawnablePositionType\": position_type(e),\n                             \"bucket\": e[\"bucket\"], "
     "\"level\": \"%d-%d\" % (lo, hi + 3),", "over its cap"),
    ("ids naming no site", "\"%s_%s_b%d_%s\" % (sub, sid, bi,", "\"%s_%s_b%d_%s\" % (sub, \"site\", bi,",
     "whose id names no site"),
])
def test_a_mutated_site_compiler_is_caught(tmp_path, label, old, new, expect):
    # Without it the site check could share the generator's derivation and pass whatever it emits.
    cs = mutant("compile_spawns", (old, new))
    faults, _read = site_faults(mutant_pack(cs, tmp_path / "p"))
    assert any(expect in f for f in faults), (label, faults[:3])


def test_build_encounters_copies_the_sites_through(tmp_path):
    # Without it regenerating data/spawns.json from the design could drop the hand-authored sites and their entries,
    # and Poipole would lose its only wild home with no failure anywhere.
    import shutil
    import build_encounters as BE
    try:
        jar = ED.BS.find_jar()
    except ED.BS.SimError as exc:
        pytest.skip("no Cobblemon 1.8 jar (%s): a skip is not a pass" % exc)
    scratch = tmp_path / "spawns.json"
    shutil.copyfile(DATA / "spawns.json", scratch)
    assert BE.main(["--spawns", str(scratch), "--jar", str(jar)]) == 0
    before, after = _load("spawns.json"), json.loads(scratch.read_text(encoding="utf-8"))
    assert after.get("placement_sites") == before["placement_sites"]
    pick = lambda d: [e for e in d["entries"] if e.get("mechanism") == SITE_MECHANISM]  # noqa: E731
    assert pick(after) == pick(before) and pick(before)
