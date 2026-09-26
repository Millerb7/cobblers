"""The 52 elder sapling birds: habitats elder_* in data/spawns.json, their Habitat Blocks elder_* in
data/habitat_blocks.json, the elder trees they sit in (derived/sites/elder_trees.json regions[].sites[] and
derived/sites/tree_grove_foothill_woods.json elders[]) and the pools tools/compile_spawns.py compiles for them.

Written by the test author, not by the session that authored the habitats, the blocks or the prefabs.

Independent sources: docs/world-building/SAPLING_BIRDS.md, the owner-approved table (one row per tree: id, (x, z,
ground), band / pool, bird), whose status paragraph records the two changes to it (block at the first storey,
ground + 21; Long Isle levels 44-50 per LONG_ISLE.md D5); the elder prefabs' NBT and trunk_origin; vanilla
`place template` rotation (StructureTemplate.transform about the placement position: clockwise_90 (x, z) -> (-z, x),
180 -> (-x, -z), counterclockwise_90 -> (z, -x)), written here, not imported from the tools that place the trees; and
the Cobblemon 1.8.0 jar (EXP-000 runtime copy, tools/battle_sim.JAR_CANDIDATES) for species ids, implementation and
level-up evolutions.

What is asserted: the doc, the blocks and the habitats name the same 52 trees; every block stands at the doc's
(x, z) and ground + 21; every block is on the trunk centre of a tree the site files still place, and that cell is a
log in the prefab as seated there; ranges 19 standalone and 14 in the grove; no two ReplaceSpawns blocks anywhere in
the manifest overlap (horizontal distance under the sum of their ranges, EXP-021's measured edge); every habitat in
data/spawns.json compiles to a non-empty pool whose species are valid resource paths (the Farfetch'd bug) and
Cobblemon species that some loaded source implements; each elder pool's birds and levels are the doc's.

derived/ is gitignored and disposable: without the site files the tree tests SKIP (a skip is not a pass). Without
the Cobblemon jar the species tests SKIP.

Not covered, and it needs a running server: that a block placed at ground + 21 is inside the trunk in the world (the
tree might not be there), the vertical shape of the reach (EXP-033), whether a grounded bird spawns on the limbs,
whether the pools load (a species id that is valid but unknown to the server), and whether the block survives a
chunk reload (EXP-021).
"""
from __future__ import annotations

import json
import math
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_spawns as CS  # noqa: E402
import nbt  # noqa: E402

SPAWNS = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
ROUTES = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))
ALL_BLOCKS = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
BLOCKS = {b["id"]: b for b in ALL_BLOCKS if b["id"].startswith("elder_")}
HABITATS = {h["id"]: h for h in SPAWNS["habitats"] if h["id"].startswith("elder_")}
DOC = (ROOT / "docs" / "world-building" / "SAPLING_BIRDS.md").read_text(encoding="utf-8")
SITES = ROOT / "derived" / "sites"
PREFABS = ROOT / "kits" / "structures" / "prefabs" / "trees" / "tree_town"
STOREY = 21                     # SAPLING_BIRDS.md status: "the first storey, ground + 21" (the parent's decision)
LONG_ISLE_LEVELS = "44-50"      # SAPLING_BIRDS.md status: "Long Isle levels: 44-50" (LONG_ISLE.md D5)
RESOURCE_PATH = re.compile(r"[a-z0-9_./-]+")


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _doc_rows():
    """{tree id: {x, z, ground, pool, bird, rare}} from the elder tables of SAPLING_BIRDS.md."""
    rows = {}
    for line in DOC.splitlines():
        if not line.startswith("| elder_"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        tid = cols[0].replace("★", "").strip()
        x, z, g = (int(v) for v in re.findall(r"-?\d+", cols[1])[:3])
        pool = cols[4].split("/", 1)[1].strip()
        bird = cols[5]
        rare = {_norm(m) for m in re.findall(r"\*\*([^*]+)\*\*\s*\(rare\)", bird)}
        names = re.findall(r"[A-Z][A-Za-z']+", bird.replace("**", ""))
        rows[tid] = {"x": x, "z": z, "ground": g, "pool": pool, "bird": {_norm(n) for n in names}, "rare": rare}
    return rows


ROWS = _doc_rows()
IDS = sorted(ROWS)


# Without it the table could fail to parse (a changed column) and every per-tree check below would pass on nothing.
def test_the_doc_table_lists_the_52_elders_and_parses():
    assert len(ROWS) == 52, len(ROWS)
    assert sum(1 for i in ROWS if i.startswith("elder_foothill_grove_")) == 4
    assert all(r["bird"] for r in ROWS.values()), [i for i, r in ROWS.items() if not r["bird"]]
    assert {_norm("Farfetch'd")} <= ROWS["elder_viltris_path_valley_2"]["bird"]


# Without it a tree loses its bird (no block or no pool) or a stray block/pool is authored for a tree that is not
# in the owner-approved mapping.
def test_one_block_and_one_habitat_per_elder_none_missing_none_extra():
    assert set(BLOCKS) == set(ROWS), (sorted(set(ROWS) - set(BLOCKS)), sorted(set(BLOCKS) - set(ROWS)))
    assert set(HABITATS) == set(ROWS), (sorted(set(ROWS) - set(HABITATS)), sorted(set(HABITATS) - set(ROWS)))
    for tid, b in BLOCKS.items():
        assert b["pool"] == "cobblers:%s" % tid, (tid, b["pool"])
        assert HABITATS[tid]["mechanism"] == "habitat_block", tid
        assert b.get("replace_spawns") is True and b.get("style") == "natural", tid
    # one pool per tree (owner decision 9); Victory Road's tiles share one pool by design, so only elders are counted
    pools = [b["pool"] for b in BLOCKS.values()]
    assert len(pools) == len(set(pools)), "two elder blocks share a pool"


# Without it a block drifts off the tree the owner approved (wrong x, z) or back to the rejected crown height.
@pytest.mark.parametrize("tid", IDS)
def test_block_stands_at_the_docs_trunk_and_the_first_storey(tid):
    r, p = ROWS[tid], BLOCKS[tid]["position"]
    assert (p["x"], p["z"], p["y"]) == (r["x"], r["z"], r["ground"] + STOREY), (tid, p, r)


# Without it a grove block's reach is not held under the canopy giants' budget (14) or a standalone block's reach
# no longer matches the crown radius (19): the owner's decision 3.
@pytest.mark.parametrize("tid", IDS)
def test_ranges_are_19_standalone_and_14_in_the_grove(tid):
    want = 14 if tid.startswith("elder_foothill_grove_") else 19
    assert BLOCKS[tid]["range_of_influence"] == want, (tid, BLOCKS[tid]["range_of_influence"])


# Without it two ReplaceSpawns blocks overlap and the overlap spawns nothing at all (EXP-021). Measured horizontally
# (Euclidean), as EXP-021 measured the edge; the vertical shape is unverified (EXP-033). A square reach would make
# Victory Road's tiles overlap by design, so this is the only measure the manifest is built to.
def test_no_two_replace_spawns_blocks_overlap_anywhere_in_the_manifest():
    rs = [b for b in ALL_BLOCKS if b.get("replace_spawns")]
    assert len(rs) >= 100, len(rs)
    bad = []
    for i, a in enumerate(rs):
        for c in rs[i + 1:]:
            d = math.hypot(a["position"]["x"] - c["position"]["x"], a["position"]["z"] - c["position"]["z"])
            if d < a["range_of_influence"] + c["range_of_influence"]:
                bad.append((a["id"], c["id"], round(d, 1)))
    assert not bad, bad[:10]


# ------------------------------------------------------------------------------------------ the trees as seated

ROT = {"none": lambda x, z: (x, z), "clockwise_90": lambda x, z: (-z, x), "180": lambda x, z: (-x, -z),
       "counterclockwise_90": lambda x, z: (z, -x)}
INVERSE = {"none": "none", "clockwise_90": "counterclockwise_90", "180": "180", "counterclockwise_90": "clockwise_90"}


def _sites():
    """{(x, z): (source, region, site)} for every elder tree the site files place."""
    et, gr = SITES / "elder_trees.json", SITES / "tree_grove_foothill_woods.json"
    if not et.is_file() or not gr.is_file():
        pytest.skip("no derived/sites/elder_trees.json or tree_grove_foothill_woods.json: run tools/elder_trees.py "
                    "and tools/tree_grove.py (derived/ is gitignored)")
    out = {}
    for r in json.loads(et.read_text(encoding="utf-8"))["regions"]:
        for s in r["sites"]:
            out[(s["x"], s["z"])] = ("elder_trees", r["id"], s)
    for s in json.loads(gr.read_text(encoding="utf-8"))["elders"]:
        out[(s["x"], s["z"])] = ("grove", "foothill_grove", s)
    return out


_PREFAB = {}


def _prefab(template_id):
    name = template_id.rsplit("/", 1)[1]
    if name not in _PREFAB:
        side = json.loads((PREFABS / (name + ".json")).read_text(encoding="utf-8"))
        _, doc = nbt.load(PREFABS / (name + ".nbt"))
        pal = doc["palette"]
        blocks = {tuple(b["pos"]): pal[b["state"]]["Name"] for b in doc["blocks"]}
        assert len(blocks) > 1000, name
        _PREFAB[name] = (side, blocks)
    return _PREFAB[name]


# Without it the site files and the tree ids drift apart: an elder the doc and the blocks name is no longer placed by
# any site file (a re-apply builds no tree there, and its block is set into bare ground or air), or a new elder is
# placed with no bird.
def test_every_elder_tree_the_doc_names_is_still_placed_by_a_site_file():
    sites = _sites()
    assert len(sites) >= 40, len(sites)
    by_region = {}
    for src, region, _s in sites.values():
        by_region[region] = by_region.get(region, 0) + 1
    want = {}
    for tid in ROWS:
        region = re.sub(r"_\d+$", "", tid[len("elder_"):])
        want[region] = want.get(region, 0) + 1
    assert by_region == want, {k: (by_region.get(k), want.get(k)) for k in set(by_region) | set(want)
                               if by_region.get(k) != want.get(k)}


# Without it a block is set beside its tree (in the open, where a player breaks it, or in air) instead of hidden in
# the trunk: its x, z must be a placed tree's trunk centre, its y that tree's ground + 21, and the cell a log of the
# prefab as `place template` seats it (origin = centre - rotate(trunk_origin + half trunk), y = ground + 1 - origin y).
@pytest.mark.parametrize("tid", IDS)
def test_block_is_a_log_at_its_trees_trunk_centre_as_seated(tid):
    sites = _sites()
    p = BLOCKS[tid]["position"]
    hit = sites.get((p["x"], p["z"]))
    assert hit is not None, "%s at (%d, %d): no elder tree in derived/sites has its trunk centre there" % (
        tid, p["x"], p["z"])
    _src, _region, s = hit
    assert p["y"] == s["ground_y"] + STOREY, (tid, p["y"], s["ground_y"])
    side, blocks = _prefab(s["object"])
    ox, oy, oz = side["trunk_origin"]
    c = side["habitat"]["trunk"][0] // 2
    qx, qz = ROT[s["rotation"]](ox + c, oz + c)
    px, pz, py = s["x"] - qx, s["z"] - qz, s["ground_y"] + 1 - oy
    tx, tz = ROT[INVERSE[s["rotation"]]](p["x"] - px, p["z"] - pz)
    got = blocks.get((tx, p["y"] - py, tz))
    assert got is not None and got.endswith("_log"), (tid, s["object"], s["rotation"], (tx, p["y"] - py, tz), got)
    # the control that the seat is the trunk's centre and not merely some log: at h30, between the storeys, the trunk
    # is a disc of radius 3 with no limbs, so the centre is log and a cell 5 off it in each direction is not
    h30 = oy + 30
    assert (blocks.get((tx, h30, tz)) or "").endswith("_log"), (tid, "no trunk at h30 over the block")
    for dx, dz in ((5, 0), (-5, 0), (0, 5), (0, -5)):
        assert not (blocks.get((tx + dx, h30, tz + dz)) or "").endswith("_log"), (tid, "trunk wider than 5 at h30", dx, dz)


# ------------------------------------------------------------------------------------------------- the pools

@pytest.fixture(scope="module")
def compiled():
    files, _routes, _habitats = CS.build(SPAWNS, ROUTES)
    out = {}
    for h in SPAWNS["habitats"]:
        key = "data/cobblers/habitat_pools/%s.json" % h["id"]
        assert key in files, key
        out[h["id"]] = json.loads(files[key])["spawns"]
    return out


# Without it a habitat is authored with no top-level entries (mechanism habitat_block, scope = its id) and compiles to
# an empty pool: with ReplaceSpawns on, its block turns the tree into a place where nothing spawns.
def test_every_habitat_has_top_level_entries_and_a_non_empty_compiled_pool(compiled):
    assert len(SPAWNS["habitats"]) >= 52 + 2
    scoped = {}
    for e in SPAWNS["entries"]:
        if e["mechanism"] == "habitat_block":
            scoped.setdefault(e["scope"], []).append(e)
    empty = [h["id"] for h in SPAWNS["habitats"] if not compiled[h["id"]]]
    assert not empty, empty
    missing = [h["id"] for h in SPAWNS["habitats"] if not scoped.get(h["id"])]
    assert not missing, missing
    orphan = sorted(set(scoped) - {h["id"] for h in SPAWNS["habitats"]})
    assert not orphan, orphan


# Without it a display name reaches a pool file: "Farfetch'd" made the server read cobblemon:farfetch'd, an invalid
# resource location, and the whole data load stopped on staging (2026-09-26). Every compiled species must be a valid
# resource path.
def test_every_compiled_habitat_species_is_a_valid_resource_path(compiled):
    bad = [(hid, s["species"]) for hid, sp in compiled.items() for s in sp
           if not RESOURCE_PATH.fullmatch(s["species"])]
    assert not bad, bad
    # teeth: the display name that stopped the load is refused by the same pattern
    assert not RESOURCE_PATH.fullmatch("Farfetch'd") and not RESOURCE_PATH.fullmatch("farfetch'd")
    assert any(s["species"] == "farfetchd" for s in compiled["elder_viltris_path_valley_2"])


def _level_range(pool_col, species):
    """The doc's level range for a species: '12-15', or 'Rowlet 25-30, Decidueye 36-40' per species (the rest of the
    family at the first one's range)."""
    parts = re.findall(r"([A-Z][A-Za-z']+)\s+(\d+-\d+)", pool_col)
    if not parts:
        return pool_col.strip()
    per = {_norm(n): r for n, r in parts}
    return per.get(species, parts[0][1])


def _pool_min(tid):
    return int(LONG_ISLE_LEVELS.split("-")[0]) if tid.startswith("elder_long_isle_")         else int(re.findall(r"\d+", ROWS[tid]["pool"])[0])


# Without it a tree's pool drifts from the owner-approved mapping: a bird the doc does not name for that tree, a
# named bird or rare find dropped, or levels off the table. A stage the doc does not spell out in the bird column may
# appear only as the doc's "stages at pool" rule allows (checked against the jar in the next test). The Long Isle's
# trees were deliberately moved to 44-50 (LONG_ISLE.md D5, SAPLING_BIRDS.md status): every species there is at 44-50.
@pytest.mark.parametrize("tid", IDS)
def test_the_pool_holds_the_docs_birds_at_the_docs_levels(tid, compiled):
    row, pool = ROWS[tid], compiled[tid]
    got = {s["species"] for s in pool}
    assert row["bird"] <= got, (tid, "named in the doc, missing from the pool", sorted(row["bird"] - got))
    for s in pool:
        want = LONG_ISLE_LEVELS if tid.startswith("elder_long_isle_") else _level_range(row["pool"], s["species"])
        assert s["levelRange"] == want, (tid, s["species"], s["levelRange"], want)
        if s["species"] in row["rare"]:
            assert s["bucket"] == "rare", (tid, s)


def _jar():
    import battle_sim
    for c in battle_sim.JAR_CANDIDATES:
        if c.is_file():
            return c
    pytest.skip("no Cobblemon-fabric-1.8.0 jar outside the live server (EXP-000 runtime copy)")


def _species_files(jar):
    z = zipfile.ZipFile(jar)
    return z, {n.rsplit("/", 1)[1][:-5]: n for n in z.namelist()
               if n.startswith("data/cobblemon/species/") and n.endswith(".json")}


# Without it an unnamed species could slip into a tree's pool in the name of "now eligible": a bird of another family,
# or a stage that needs an item or is above the pool's floor. Every species the doc's bird column does not name must
# be a level-up evolution (a level requirement only) of a named bird, reachable by the pool's minimum level: the doc's
# "stages at pool" rule (Dartrix eligible at 17 in a 25-30 pool), and on the Long Isle the same rule at 44.
def test_unnamed_species_are_level_up_stages_of_the_docs_bird_reachable_by_the_pool_floor(compiled):
    z, files = _species_files(_jar())

    def evolves(sp, lo):
        d = json.loads(z.read(files[sp]))
        for ev in d.get("evolutions") or []:
            if ev.get("variant") != "level_up":
                continue
            lv = [q.get("minLevel") for q in ev.get("requirements") or [] if q.get("variant") == "level"]
            others = [q for q in ev.get("requirements") or [] if q.get("variant") != "level"]
            if lv and not others and lv[0] <= lo:
                yield ev["result"].split(" ")[0]

    extras = 0
    for tid in IDS:
        got = {s["species"] for s in compiled[tid]}
        reach, todo = set(ROWS[tid]["bird"]), list(ROWS[tid]["bird"])
        while todo:
            for nxt in evolves(todo.pop(), _pool_min(tid)):
                if nxt not in reach:
                    reach.add(nxt)
                    todo.append(nxt)
        assert got <= reach, (tid, sorted(got - reach))
        extras += len(got - ROWS[tid]["bird"])
    # the rule has cases: Dartrix, Trumbeak, Corvisquire at the rare-find trees, Corviknight and Unfezant on the Long Isle
    assert extras >= 3, extras


# Without it a pool names a species the server has no data for, or one Cobblemon ships unimplemented (no model; it
# never spawns) with nothing in the pack implementing it. Implementation is read from the jar and from any
# species_additions in the EXP-000 runtime's datapacks and mods (Cobbleverse's DP, Mega Showdown).
def test_every_habitat_species_is_a_cobblemon_species_something_implements(compiled):
    jar = _jar()
    z, files = _species_files(jar)
    implemented = {sp for sp, n in files.items() if json.loads(z.read(n)).get("implemented") is True}
    server = jar.parent.parent
    for f in sorted(server.glob("datapacks/*.zip")) + sorted(server.glob("mods/*.jar")):
        try:
            zz = zipfile.ZipFile(f)
        except zipfile.BadZipFile:
            continue
        for n in zz.namelist():
            if n.startswith("data/cobblemon/species") and n.endswith(".json"):
                try:
                    d = json.loads(zz.read(n))
                except ValueError:
                    continue
                if d.get("implemented") is True:
                    implemented.add((d.get("target") or n.rsplit("/", 1)[1][:-5]).split(":")[-1])
    species = {s["species"] for sp in compiled.values() for s in sp}
    assert len(species) > 100
    unknown = sorted(species - set(files))
    assert not unknown, unknown
    unimplemented = sorted(species - implemented)
    assert not unimplemented, unimplemented
