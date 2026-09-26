"""The 52 elder sapling nests: habitats elder_* in data/spawns.json, their four activated Habitat Blocks each
(elder_<tree>, elder_<tree>_mid, elder_<tree>_crown in the trunk, elder_<tree>_top in the crown's leaves) in
data/habitat_blocks.json, the elder trees they sit in, and the pools tools/compile_spawns.py compiles for them.

Written by the test author, not by the session that authored the habitats, the blocks or the prefabs.

Independent sources: docs/world-building/SAPLING_BIRDS.md, the owner-approved table (one row per tree: id, (x, z,
ground), tree species, band / pool, bird) and its status paragraph (one species per tree; Farfetch'd and Oricorio trees
without co-residents; owls and crows by day; "at least 20 ... spread vertically along the tree"); the owner's
2026-09-26 request to raise the spawns and put birds at the top of the tree, as recorded in docs/STATE.md and commit
ab3cf01 (four blocks per elder at ground + 12, + 35, + 58 in trunk log and + 74 in the crown's leaves, up to 8 alive
each within 16 blocks, refilling 2 at a time; the staging probe: leaves from + 63 to + 81 at every elder's centre);
data/elder_trees.json (the 48 pinned standalone elders: species, variant, rotation, ground);
derived/sites/tree_grove_foothill_woods.json (the 4 grove elders); the elder prefabs' NBT and trunk_origin; vanilla
`place template` rotation (StructureTemplate.transform about the placement position: clockwise_90 (x, z) -> (-z, x),
180 -> (-x, -z), counterclockwise_90 -> (z, -x)), written here, not imported from the tools that place the trees; and
the Cobblemon 1.8.0 jar (EXP-000 runtime copy, tools/battle_sim.JAR_CANDIDATES) for species ids, implementation,
evolution families and level-up evolutions.

What is asserted: the doc, the blocks and the habitats name the same 52 trees; each tree has exactly its four blocks,
activated, replace_spawns false, on the doc's trunk (x, z) at ground + 12, + 35, + 58, + 74, with the stated activated
settings (8 a block, except a per-tree cap stated in the doc's status and in each of the tree's blocks' why: the
Tropius elder's 5) and at least 20 max_spawns between them; each trunk block sits in solid trunk log of the prefab as seated
(the cell and its six face neighbours) and its mimic is that log; the top block sits in that wood's persistent leaves
(the cell and its six face neighbours) inside a centre column of leaves from + 63 to + 81, and its mimic is those
leaves; the doc's status paragraph states the layout the data holds; each pool is one evolution family, holds the
doc's bird at the doc's levels, and carries no time condition; species are valid resource paths and implemented.

derived/ is gitignored and disposable: without the site files the grove trees' seat test and the site-file test SKIP
(a skip is not a pass). Without the Cobblemon jar the species tests SKIP.

Not covered, and it needs a running server: that the blocks are in the world (tools/habitat_blocks.py verify), that
birds actually spread up the tree rather than drifting to the forest floor (docs/STATE.md: the + 58 and + 74 blocks
put no birds in the crown on staging, cause not found), that 8 per block are held under real player load and mob
caps, whether a spawn stands on leaves or limbs, whether a habitat block mimicking leaves counts as leaves for its
neighbours, and whether an activated block survives a chunk reload.
"""
from __future__ import annotations

import json
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
PINNED = {e["id"]: e for e in json.loads((ROOT / "data" / "elder_trees.json").read_text(encoding="utf-8"))["elders"]}
DOC = (ROOT / "docs" / "world-building" / "SAPLING_BIRDS.md").read_text(encoding="utf-8")
SITES = ROOT / "derived" / "sites"
PREFABS = ROOT / "kits" / "structures" / "prefabs" / "trees" / "tree_town"
# the owner, 2026-09-26 (docs/STATE.md, commit ab3cf01): four blocks per elder, suffix -> (height above ground, the
# block kind its mimic and its surroundings are), and what each keeps alive
NEST = {"": (12, "log"), "_mid": (35, "log"), "_crown": (58, "log"), "_top": (74, "leaves")}
ACTIVATED = {"spawn_range": 16, "max_spawns": 8, "max_spawns_per_activation": 2, "chance": 1.0, "trigger": "TICK",
             "cancel_range": -1}
LEAVES_RUN = (63, 81)           # the staging probe (docs/STATE.md): leaves at every elder's centre, ground + 63 to + 81
AT_LEAST_PER_TREE = 20          # the owner: "at least 20 ... spread vertically along the tree"
# Per-tree exceptions to the 8-a-block nest: tree -> max_spawns on each of its four blocks. An exception counts only
# when it is documented twice, in SAPLING_BIRDS.md and in every one of the tree's blocks' `why`, by the phrase
# CAP_PHRASE builds from the numbers, and it still holds at least AT_LEAST_PER_TREE in the tree. Plan v2's status:
# "the Tropius elder keeps 5 per block, 20 in the tree" (balance review: 32 of a Pokemon this large crowd one trunk).
CAP_EXCEPTIONS = {"elder_jungle_west_1": 5}
CAP_PHRASE = "keeps %d per block, %d in the tree"
# SAPLING_BIRDS.md status: these two lost their co-resident; the find is the tree's one bird
SINGLE = {"elder_viltris_path_valley_2": "farfetchd", "elder_long_isle_south_3": "oricorio"}
LONG_ISLE_LEVELS = "44-50"      # SAPLING_BIRDS.md earlier status: "Long Isle levels: 44-50" (LONG_ISLE.md D5)
RESOURCE_PATH = re.compile(r"[a-z0-9_./-]+")
WOODS = ("dark oak", "mangrove", "jungle", "cherry", "spruce", "birch", "oak")


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _doc_rows():
    """{tree id: {x, z, ground, wood, pool, bird, rare}} from the elder tables of SAPLING_BIRDS.md."""
    rows = {}
    for line in DOC.splitlines():
        if not line.startswith("| elder_"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        tid = cols[0].replace("★", "").strip()
        x, z, g = (int(v) for v in re.findall(r"-?\d+", cols[1])[:3])
        wood = next(w for w in WOODS if cols[3].startswith(w))
        pool = cols[4].split("/", 1)[1].strip()
        bird = cols[5]
        rare = {_norm(m) for m in re.findall(r"\*\*([^*]+)\*\*\s*\(rare\)", bird)}
        names = {_norm(n) for n in re.findall(r"[A-Z][A-Za-z']+", bird.replace("**", ""))}
        if tid in SINGLE:
            names, rare = {SINGLE[tid]}, set()
        rows[tid] = {"x": x, "z": z, "ground": g, "wood": wood.replace(" ", "_"), "pool": pool, "bird": names,
                     "rare": rare}
    return rows


ROWS = _doc_rows()
IDS = sorted(ROWS)


# Without it the table could fail to parse (a changed column) and every per-tree check below would pass on nothing,
# or the status's one-species exceptions could be removed from the doc while this file still assumes them.
def test_the_doc_table_lists_the_52_elders_and_the_one_species_status():
    assert len(ROWS) == 52, len(ROWS)
    assert sum(1 for i in ROWS if i.startswith("elder_foothill_grove_")) == 4
    assert all(r["bird"] for r in ROWS.values()), [i for i, r in ROWS.items() if not r["bird"]]
    assert "`elder_viltris_path_valley_2` Farfetch'd only" in DOC
    assert "`elder_long_isle_south_3` Oricorio only" in DOC
    assert {r["wood"] for r in ROWS.values()} >= {"oak", "birch", "spruce", "dark_oak", "jungle", "mangrove", "cherry"}


def _status_paragraph():
    start = DOC.index("Status:")
    return " ".join(DOC[start:DOC.index("\n\n", start)].split())


def _status_paragraphs():
    return [" ".join(DOC[m.start():DOC.find("\n\n", m.start())].split()) for m in re.finditer(r"(?m)^Status:", DOC)]


def _exception_phrase(tid):
    cap = CAP_EXCEPTIONS[tid]
    return CAP_PHRASE % (cap, cap * len(NEST))


# Without it the doc that maps the nests ("Pool and bird: docs/world-building/SAPLING_BIRDS.md" in every block's why)
# goes on stating a layout the data no longer holds, and the next session builds or balances from the stale numbers:
# its status paragraph must name every nest height and state no per-block cap other than the data's (8 an elder
# block, 12 a Route 1 block), and every per-tree exception's cap (5 for the Tropius elder) must be stated in a status
# paragraph of the doc; a cap in the data that neither the layout nor a documented exception gives fails.
def test_the_doc_status_states_the_nest_layout_the_data_holds():
    st = _status_paragraph()
    heights = [h for h, _ in NEST.values()]
    missing = [h for h in heights if "+ %d" % h not in st]
    caps = {int(n) for n in re.findall(r"up to (\d+)", st)}
    data_caps = {b["activated"]["max_spawns"] for b in ALL_BLOCKS
                 if b.get("style") == "activated" and (b["id"].startswith("elder_") or "sapling" in b["id"])}
    assert data_caps == {8, 12} | set(CAP_EXCEPTIONS.values()), data_caps
    assert not missing and caps and caps <= data_caps, (
        "SAPLING_BIRDS.md status paragraph", "heights not named", missing,
        "caps stated", sorted(caps), "caps in the data", sorted(data_caps), st)
    statuses = " ".join(_status_paragraphs())
    undocumented = [t for t in CAP_EXCEPTIONS if _exception_phrase(t) not in statuses]
    assert not undocumented, ("per-tree cap exceptions no SAPLING_BIRDS.md status states",
                              {t: _exception_phrase(t) for t in undocumented})


# Without it the doc and the pinned standalone elders drift apart: a block seated on the doc's ground or wood while
# the tree the tools place stands on another (a block in air or buried under the trunk base, a mimic of the wrong log).
def test_the_doc_agrees_with_the_pinned_elders_on_trunk_ground_and_wood():
    standalone = [t for t in IDS if not t.startswith("elder_foothill_grove_")]
    assert set(standalone) == set(PINNED), (sorted(set(standalone) ^ set(PINNED)))
    bad = [(t, ROWS[t], PINNED[t]) for t in standalone
           if (ROWS[t]["x"], ROWS[t]["z"], ROWS[t]["ground"], ROWS[t]["wood"])
           != (PINNED[t]["x"], PINNED[t]["z"], PINNED[t]["ground_y"], PINNED[t]["species"])]
    assert not bad, bad[:5]


# Without it a tree loses a nest block (the crown-top block in the leaves included), a stray elder block appears, or a
# block points at another tree's pool: the nest is the tree's one species, four blocks high.
def test_four_blocks_and_one_habitat_per_elder_none_missing_none_extra():
    want = {"%s%s" % (t, s) for t in ROWS for s in NEST}
    assert set(BLOCKS) == want, (sorted(want - set(BLOCKS))[:10], sorted(set(BLOCKS) - want)[:10])
    assert set(HABITATS) == set(ROWS), (sorted(set(ROWS) - set(HABITATS)), sorted(set(HABITATS) - set(ROWS)))
    for t in ROWS:
        assert HABITATS[t]["mechanism"] == "habitat_block", t
        for s in NEST:
            assert BLOCKS[t + s]["pool"] == "cobblers:%s" % t, (t + s, BLOCKS[t + s]["pool"])


# Without it an elder block goes back to the natural style (redirecting the forest's own spawns, a bird now and then)
# or turns ReplaceSpawns on (four stacked natural ReplaceSpawns blocks would cancel each other, EXP-021), or drops back
# to the smaller nest (7 alive, 1 per refill) the owner asked to raise. A tree may hold another per-block cap only as
# a documented exception (CAP_EXCEPTIONS): its every block's `why` and the doc state the cap and the tree's total.
@pytest.mark.parametrize("tid", IDS)
def test_every_elder_block_is_activated_with_the_nest_settings(tid):
    want = dict(ACTIVATED)
    if tid in CAP_EXCEPTIONS:
        want["max_spawns"] = CAP_EXCEPTIONS[tid]
        assert _exception_phrase(tid) in DOC, (tid, "exception not in SAPLING_BIRDS.md", _exception_phrase(tid))
    for s in NEST:
        b = BLOCKS[tid + s]
        assert b["style"] == "activated" and b["replace_spawns"] is False, (tid + s, b["style"], b["replace_spawns"])
        assert b["activated"] == want, (tid + s, b["activated"], want)
        assert b.get("status") in ("placed", "verified"), (tid + s, b.get("status"))
        if tid in CAP_EXCEPTIONS:
            assert _exception_phrase(tid) in b["why"], (tid + s, "why does not state the exception",
                                                        _exception_phrase(tid))


# Without it the exception list outgrows its purpose: an exception that would take a tree under the owner's 20, or one
# for a tree the doc does not map, is refused here, and the list must not be empty-handed (a name typo would exempt
# nothing while the Tropius tree failed elsewhere).
def test_every_cap_exception_is_a_mapped_elder_that_still_holds_at_least_20():
    assert set(CAP_EXCEPTIONS) <= set(ROWS), sorted(set(CAP_EXCEPTIONS) - set(ROWS))
    low = {t: c * len(NEST) for t, c in CAP_EXCEPTIONS.items() if c * len(NEST) < AT_LEAST_PER_TREE}
    assert not low, low
    # teeth: the phrase is built from the numbers, so a doc saying "keeps 5 per block, 32 in the tree" would not match
    assert _exception_phrase("elder_jungle_west_1") == "keeps 5 per block, 20 in the tree"


# Without it a tree holds fewer birds than the owner asked for (at least 20 in the tree; 32 as authored).
@pytest.mark.parametrize("tid", IDS)
def test_each_elder_keeps_at_least_20_birds(tid):
    total = sum(BLOCKS[tid + s]["activated"]["max_spawns"] for s in NEST)
    assert total >= AT_LEAST_PER_TREE, (tid, total)


# Without it a block drifts off the tree the owner approved (wrong x, z) or off the four heights that spread the
# birds up the tree (the retired ground + 21, a trunk height outside the solid trunk, or a top block below the crown).
@pytest.mark.parametrize("tid", IDS)
def test_blocks_stand_on_the_docs_trunk_at_ground_plus_12_35_58_74(tid):
    r = ROWS[tid]
    for s, (h, _kind) in NEST.items():
        p = BLOCKS[tid + s]["position"]
        assert (p["x"], p["z"], p["y"]) == (r["x"], r["z"], r["ground"] + h), (tid + s, p, r)


# Without it a block is placed as the wrong wood or the wrong kind: the mimic is what the first setblock puts in the
# tree (tools/habitat_blocks.py commands()), so a birch tree would carry an oak log patch, or the crown-top block a log
# cube in the leaves (or a trunk block a leaf in the trunk).
@pytest.mark.parametrize("tid", IDS)
def test_the_mimic_is_the_trees_own_log_or_leaves_by_block_kind(tid):
    for s, (_h, kind) in NEST.items():
        want = "minecraft:%s_%s" % (ROWS[tid]["wood"], kind)
        assert BLOCKS[tid + s]["mimic"] == want, (tid + s, BLOCKS[tid + s]["mimic"], want)


# ------------------------------------------------------------------------------------------ the trees as seated

ROT = {"none": lambda x, z: (x, z), "clockwise_90": lambda x, z: (-z, x), "180": lambda x, z: (-x, -z),
       "counterclockwise_90": lambda x, z: (z, -x)}
INVERSE = {"none": "none", "clockwise_90": "counterclockwise_90", "180": "180", "counterclockwise_90": "clockwise_90"}
FACES = ((0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def _grove_sites():
    gr = SITES / "tree_grove_foothill_woods.json"
    if not gr.is_file():
        pytest.skip("no derived/sites/tree_grove_foothill_woods.json: run tools/tree_grove.py (derived/ is gitignored)")
    return {(s["x"], s["z"]): s for s in json.loads(gr.read_text(encoding="utf-8"))["elders"]}


def _seat(tid):
    """(template id, rotation, ground_y) of the tree at tid: the pinned file for the 48, the grove file for the 4."""
    if tid in PINNED:
        e = PINNED[tid]
        return "cobblers:kits/trees/tree_town/elder_%s_%s" % (e["species"], e["variant"]), e["rotation"], e["ground_y"]
    r = ROWS[tid]
    s = _grove_sites().get((r["x"], r["z"]))
    assert s is not None, "%s: no grove elder at the doc's (%d, %d)" % (tid, r["x"], r["z"])
    return s["object"], s["rotation"], s["ground_y"]


_PREFAB = {}


def _prefab(template_id):
    name = template_id.rsplit("/", 1)[1]
    if name not in _PREFAB:
        side = json.loads((PREFABS / (name + ".json")).read_text(encoding="utf-8"))
        _, doc = nbt.load(PREFABS / (name + ".nbt"))
        pal = doc["palette"]
        blocks = {tuple(b["pos"]): pal[b["state"]]["Name"] for b in doc["blocks"]}
        props = {tuple(b["pos"]): pal[b["state"]].get("Properties") or {} for b in doc["blocks"]}
        assert len(blocks) > 1000, name
        _PREFAB[name] = (side, blocks, props)
    return _PREFAB[name]


# Without it the site files and the tree ids drift apart: an elder the doc and the blocks name is no longer placed by
# any site file (a re-apply builds no tree there, and its blocks are set into bare ground or air), or a new elder is
# placed with no bird.
def test_every_elder_tree_the_doc_names_is_still_placed_by_a_site_file():
    et = SITES / "elder_trees.json"
    if not et.is_file():
        pytest.skip("no derived/sites/elder_trees.json: run tools/elder_trees.py (derived/ is gitignored)")
    sites = {(s["x"], s["z"]): s for r in json.loads(et.read_text(encoding="utf-8"))["regions"] for s in r["sites"]}
    sites.update(_grove_sites())
    missing = [t for t in IDS if (ROWS[t]["x"], ROWS[t]["z"]) not in sites]
    assert not missing, missing
    wrong_ground = [(t, sites[(ROWS[t]["x"], ROWS[t]["z"])]["ground_y"], ROWS[t]["ground"]) for t in IDS
                    if sites[(ROWS[t]["x"], ROWS[t]["z"])]["ground_y"] != ROWS[t]["ground"]]
    assert not wrong_ground, wrong_ground
    assert len(sites) == len(IDS), (len(sites), len(IDS))


# Without it a block is set beside its tree (in the open, where a player sees and breaks it, or in air) instead of
# buried in it: each trunk block's cell and its six face neighbours must be log of the prefab as `place template`
# seats it (origin = centre - rotate(trunk_origin + half trunk), y = ground + 1 - origin y), and each top block's must
# be leaves (above the trunk's end, in the crown), and in both cases the mimic, so the first setblock does not change
# the tree's wood. The top block's leaves must be persistent: a non-log block in their midst must not let them decay.
# The centre column holds leaves from + 63 to + 81 as seated, the run the staging probe found (a control that the top
# block is inside the crown and not in a pocket of leaves).
@pytest.mark.parametrize("tid", IDS)
def test_every_block_is_buried_in_its_trees_trunk_log_or_crown_leaves_as_seated(tid):
    obj, rot, ground = _seat(tid)
    side, blocks, props = _prefab(obj)
    ox, oy, oz = side["trunk_origin"]
    c = side["habitat"]["trunk"][0] // 2
    r = ROWS[tid]
    qx, qz = ROT[rot](ox + c, oz + c)
    px, pz, py = r["x"] - qx, r["z"] - qz, ground + 1 - oy
    for s, (_h, kind) in NEST.items():
        b = BLOCKS[tid + s]
        p = b["position"]
        tx, tz = ROT[INVERSE[rot]](p["x"] - px, p["z"] - pz)
        ty = p["y"] - py
        cells = [(tx + dx, ty + dy, tz + dz) for dx, dy, dz in FACES]
        got = [blocks.get(q) for q in cells]
        assert all(g == b["mimic"] and g.endswith("_" + kind) for g in got), (tid + s, obj, rot, (tx, ty, tz), got,
                                                                              b["mimic"])
        if kind == "leaves":
            loose = [q for q in cells if props[q].get("persistent") != "true"]
            assert not loose, (tid + s, obj, "non-persistent leaves round the top block", loose)
            column = {k: blocks.get((tx, ground + k - py, tz)) for k in range(LEAVES_RUN[0], LEAVES_RUN[1] + 1)}
            gaps = sorted(k for k, n in column.items() if n != b["mimic"])
            assert not gaps, (tid, obj, "centre column not leaves at ground +", gaps)
            assert LEAVES_RUN[0] < p["y"] - ground < LEAVES_RUN[1], (tid + s, p["y"] - ground, LEAVES_RUN)
    # the control that the seat is the trunk's centre and not merely some log: at h30, between the storeys, the trunk
    # is a disc of radius 3 with no limbs, so the centre is log and a cell 5 off it in each direction is not
    p = BLOCKS[tid]["position"]
    tx, tz = ROT[INVERSE[rot]](p["x"] - px, p["z"] - pz)
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
# an empty pool: an activated block with an empty pool is a nest that never holds a bird.
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


# Without it an owl or crow tree goes back to night-only (the owner settled C6 / decision 10: by day too), and a nest
# stands empty for the whole day.
def test_no_elder_pool_or_entry_carries_a_time_condition(compiled):
    timed = [(t, s["species"]) for t in IDS for s in compiled[t] if "timeRange" in s]
    assert not timed, timed
    authored = [e["id"] for e in SPAWNS["entries"]
                if e.get("scope", "").startswith("elder_") and (e.get("conditions") or {}).get("timeRange")]
    assert not authored, authored


def _level_range(pool_col, species):
    """The doc's level range for a species: '12-15', or 'Rowlet 25-30, Decidueye 36-40' per species (the rest of the
    family at the first one's range)."""
    parts = re.findall(r"([A-Z][A-Za-z']+)\s+(\d+-\d+)", pool_col)
    if not parts:
        return pool_col.strip()
    per = {_norm(n): r for n, r in parts}
    return per.get(species, parts[0][1])


def _pool_min(tid):
    if tid.startswith("elder_long_isle_"):
        return int(LONG_ISLE_LEVELS.split("-")[0])
    return int(re.findall(r"\d+", ROWS[tid]["pool"])[0])


# Without it a tree's pool drifts from the owner-approved mapping: a bird the doc does not name for that tree, the
# named bird dropped, or levels off the table. The two trees the status made single-species hold their find alone, as
# a common spawn at the tree's full weight (a lone rare entry would still be the only thing the block can spawn, but
# the pool would no longer say what it is). The Long Isle's trees were moved to 44-50 (LONG_ISLE.md D5).
@pytest.mark.parametrize("tid", IDS)
def test_the_pool_holds_the_docs_bird_at_the_docs_levels(tid, compiled):
    row, pool = ROWS[tid], compiled[tid]
    got = {s["species"] for s in pool}
    assert row["bird"] <= got, (tid, "named in the doc, missing from the pool", sorted(row["bird"] - got))
    for s in pool:
        want = LONG_ISLE_LEVELS if tid.startswith("elder_long_isle_") else _level_range(row["pool"], s["species"])
        assert s["levelRange"] == want, (tid, s["species"], s["levelRange"], want)
        if s["species"] in row["rare"]:
            assert s["bucket"] == "rare", (tid, s)
    if tid in SINGLE:
        assert [(s["species"], s["bucket"], s["weight"]) for s in pool] == [(SINGLE[tid], "common", 24.0)], (tid, pool)


def _jar():
    import battle_sim
    for c in battle_sim.JAR_CANDIDATES:
        if c.is_file():
            return c
    pytest.skip("no Cobblemon-fabric-1.8.0 jar outside the live server (EXP-000 runtime copy)")


@pytest.fixture(scope="module")
def species_files():
    z = zipfile.ZipFile(_jar())
    files = {n.rsplit("/", 1)[1][:-5]: n for n in z.namelist()
             if n.startswith("data/cobblemon/species/") and n.endswith(".json")}
    return z, files


def _families(z, files):
    """{species: family root} from the jar's evolutions and preEvolution links (union-find)."""
    parent = {sp: sp for sp in files}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        if a in parent and b in parent:
            parent[find(a)] = find(b)

    for sp, n in files.items():
        d = json.loads(z.read(n))
        for ev in d.get("evolutions") or []:
            union(sp, _norm(ev.get("result", "").split(" ")[0]))
        if d.get("preEvolution"):
            union(sp, _norm(d["preEvolution"].split(" ")[0]))
    return {sp: find(sp) for sp in files}


# Without it a sapling stops being one species' nest: a co-resident of another family (Fletchling back under the
# Farfetch'd, Chatot under the Oricorio, Hoothoot in the Route 1 sapling) dilutes the tree. Stages of one family
# (Pidgey, Pidgeotto, Pidgeot) are one line and allowed. Families come from the jar's evolution links.
def test_every_sapling_pool_is_one_evolution_family(compiled, species_files):
    z, files = species_files
    fam = _families(z, files)
    # teeth: the pairs this rule must tell apart
    assert fam["pidgey"] == fam["pidgeot"] and fam["rowlet"] == fam["decidueye"]
    assert fam["pidgey"] != fam["hoothoot"] and fam["farfetchd"] != fam["fletchling"] and fam["oricorio"] != fam["chatot"]
    mixed = {}
    for hid in IDS + ["route_1_sapling_crown"]:
        roots = {fam.get(s["species"], "?" + s["species"]) for s in compiled[hid]}
        if len(roots) != 1:
            mixed[hid] = sorted(s["species"] for s in compiled[hid])
    assert not mixed, mixed


# Without it an unnamed species could slip into a tree's pool in the name of "now eligible": a stage that needs an
# item or is above the pool's floor. Every species the doc's bird column does not name must be a level-up evolution
# (a level requirement only) of a named bird, reachable by the pool's minimum level: the doc's "stages at pool" rule.
def test_unnamed_species_are_level_up_stages_of_the_docs_bird_reachable_by_the_pool_floor(compiled, species_files):
    z, files = species_files

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
def test_every_habitat_species_is_a_cobblemon_species_something_implements(compiled, species_files):
    z, files = species_files
    jar = _jar()
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
