"""The 14 themed saplings of plan v2 (docs/world-building/SAPLING_BIRDS.md): their pinned sites
(data/themed_saplings.json), their pools (habitats sapling_* in data/spawns.json, compiled by tools/compile_spawns.py),
their nest blocks (sapling_* in data/habitat_blocks.json), their prefabs (kits/structures/prefabs/trees/themed/
sapling_<theme>.nbt), and the map-wide one-line rule over every sapling pool, elders and the Route 1 sapling included.

Written by the test author, not by the session that built the saplings, their pools or their blocks.

Independent sources: SAPLING_BIRDS.md "Plan v2": its status (the Long Isle desert tree is Vullaby, not Sigilyph; the
balance review set the Great Crater to 44-50 and the Sunset west palm to Wingull only at 16-20), its rules (1: one
species line per sapling; 2: a line repeats at least 1,000 blocks apart across the whole map; 3: 800 between themed
saplings and 400 from an elder; 4: every sapling keeps the elder's silhouette, tools/tree_grove.py big_tree at the
`elder` tier, two storeys of near-level limbs), "The skins" table (trunk and crown material per theme), the "Themed
saplings: 14 trees" table (id, bird line, levels) and the "Elders: 9 birds change" table (elder, becomes, levels); the
siting clearances in tools/themed_saplings.py's docstring (120 from a town centre, 100 from every data/placements.json
position); data/towns.json town centres; derived/sites/elder_trees.json and tree_grove_foothill_woods.json (the elders
as sited) and the elder blocks in data/habitat_blocks.json (the elders as nested); tools/tree_grove.py TIERS["elder"]
(storeys at floor 20 and floor + gap 38, each limb rising 0-2 at its root and 1-3 more to its tip: bands 20-24 and
38-42); the prefab NBT (tools/structure_nbt.py load) and its trunk_origin; vanilla `place template` rotation
(StructureTemplate.transform about the placement position, written here from Minecraft's formula and only
cross-checked against tools/place_town.py rotate); and the Cobblemon 1.8.0 jar (EXP-000 runtime copy,
tools/battle_sim.JAR_CANDIDATES) for species ids, implementation and evolution families.

What is asserted: 14 pins, the doc's 14 ids, 800 apart, 400 from every elder, 120 from every town centre, 100 from
every placement position; every sapling pool (elder_*, route_1_sapling_crown, sapling_*) is one evolution family and
no family sits on two saplings closer than 1,000 blocks (tree positions: the activated blocks that name the pool);
each themed pool holds the plan's bird line at the plan's levels, with the status's three changes; each of the 9 elder
swaps holds its new line at its levels; every species is a jar species implemented by the jar or a pack species
addition; each themed sapling has at least 3 activated nest blocks naming its own pool, holding at least 20 between
them, and, placed as `place template` seats the prefab, each sits in a cell of the theme's own trunk or crown block,
with all six face neighbours solid, and its mimic is that block; each prefab has a trunk column of its trunk material
from y 0 to at least 35, rings of trunk-material limbs at y 20-24 and 38-42 and none between, and a height of 60-90;
`tools/themed_saplings.py records` reproduces the sapling_ blocks exactly, statuses aside.

derived/ is gitignored and disposable: without the site files the derived-elder spacing test SKIPS (the committed
elder blocks are still checked). Without the Cobblemon jar the family and implementation tests SKIP. A skip is not a
pass.

Not covered, and it needs a running server or the heightmap: that the trees and blocks are in the world
(tools/habitat_blocks.py verify), that each tree is seen from a road (rule 6; tools/sightlines.py, not re-run here),
the ground_y pins against tools/ground.py, the settings (young trees, dressed ground), that birds stay near the tree,
that a block mimicking nether wart or bone hides as well as a log, and that 8 per block are held under real mob caps.
"""
from __future__ import annotations

import itertools
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
import structure_nbt  # noqa: E402

DATA = ROOT / "data"
SITES = ROOT / "derived" / "sites"
THEMED = ROOT / "kits" / "structures" / "prefabs" / "trees" / "themed"
ELDER_PREFABS = ROOT / "kits" / "structures" / "prefabs" / "trees" / "tree_town"

PINS = json.loads((DATA / "themed_saplings.json").read_text(encoding="utf-8"))["saplings"]
SPAWNS = json.loads((DATA / "spawns.json").read_text(encoding="utf-8"))
ROUTES = json.loads((DATA / "routes.json").read_text(encoding="utf-8"))
ALL_BLOCKS = json.loads((DATA / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
DOC = (ROOT / "docs" / "world-building" / "SAPLING_BIRDS.md").read_text(encoding="utf-8")
PLAN = DOC[DOC.index("## Plan v2"):DOC.index("\n## ", DOC.index("## Plan v2") + 1)]
PLAN_FLAT = " ".join(PLAN.split())

# the plan's rules and the tool's stated clearances
THEMED_SPACING, ELDER_SPACING, OFF_TOWN, OFF_PLACEMENT, LINE_SPACING = 800, 400, 120, 100, 1000
AT_LEAST_PER_TREE = 20          # the owner: "at least 20 ... spread vertically along the tree"
MIN_NESTS = 3
ACTIVATED = {"spawn_range": 16, "max_spawns": 8, "max_spawns_per_activation": 2, "chance": 1.0, "trigger": "TICK",
             "cancel_range": -1}  # "as in the elders' nests" (tools/themed_saplings.py records' why)
TRUNK_TO, HEIGHT = 35, (60, 90)
# blocks a nest must not touch: they do not close a face (a layer of snow, a pod, a bush, a rod, powder snow, roots
# with holes), so a block beside them shows
NON_FULL = {"minecraft:snow", "minecraft:cocoa", "minecraft:dead_bush", "minecraft:lightning_rod",
            "minecraft:powder_snow", "minecraft:mangrove_roots", "minecraft:air", None}
FACES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
RESOURCE_PATH = re.compile(r"[a-z0-9_./-]+")


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _section(heading):
    start = PLAN.index("\n### " + heading)
    end = PLAN.find("\n### ", start + 1)
    return PLAN[start:end if end > 0 else len(PLAN)]


def _table(heading, first_col_prefix):
    """The rows of the table under `### heading` in Plan v2 whose first cell starts with the prefix."""
    rows = []
    for line in _section(heading).splitlines():
        if line.startswith("| " + first_col_prefix):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


# ------------------------------------------------------------------ the plan, read from the doc

def _skins():
    """{theme: (trunk block, crown block or None)} from "The skins" table."""
    out = {}
    for cols in _table("The skins", ""):
        if len(cols) != 5 or cols[0] not in ("palm", "lakeshore", "scorched", "frost", "storm", "crag", "desert"):
            continue
        trunk = re.split(r",| with ", cols[1])[0].strip()
        trunk_id = "minecraft:" + trunk.replace(" ", "_")
        crown = cols[2].lower()
        if crown.startswith("no leaves"):
            crown_id = None
        elif "nether wart block" in crown:
            crown_id = "minecraft:nether_wart_block"
        else:
            m = re.search(r"\b(jungle|mangrove|spruce|oak|dark)\s+lea(?:ves|f)", crown)
            wood = {"dark": "dark_oak"}.get(m.group(1), m.group(1)) if m else trunk.split()[0]
            crown_id = "minecraft:%s_leaves" % wood        # "a weeping crown", "flat pads": the trunk wood's leaves
        out[cols[0]] = (trunk_id, crown_id)
    return out


SKINS = _skins()


def _themed_rows():
    """{id: (bird line [names], levels)} from the "Themed saplings: 14 trees" table."""
    return {c[0]: ([n.strip() for n in c[2].split(",")], c[3]) for c in _table("Themed saplings: 14 trees", "sapling_")}


ROWS = _themed_rows()
# Plan v2's status names three changes from the table; each is applied only while the status still says it
CHANGES = {
    "sapling_desert_long_isle_north": ({"line": ["Vullaby"]}, "the Long Isle desert tree is Vullaby, not Sigilyph"),
    "sapling_scorched_great_crater": ({"levels": "44-50"}, "set the Great Crater to 44-50"),
    "sapling_palm_sunset_west": ({"line": ["Wingull"], "levels": "16-20"},
                                 "the Sunset west palm to Wingull only at 16-20"),
}


def _plan(sid):
    line, levels = ROWS[sid]
    if sid in CHANGES:
        change, _ = CHANGES[sid]
        line, levels = change.get("line", line), change.get("levels", levels)
    return [_norm(n) for n in line], levels


def _swaps():
    """{elder: (becomes [names], levels)} from the "Elders: 9 birds change" table."""
    return {c[0].strip("`"): ([_norm(n) for n in c[2].split(",")], c[3]) for c in _table("Elders: 9 birds change", "`elder_")}


SWAPS = _swaps()

PIN = {p["id"]: p for p in PINS}
IDS = sorted(PIN)
SAPLING_BLOCKS = [b for b in ALL_BLOCKS if b["id"].startswith("sapling_")]


# Without it the doc's tables could stop parsing (a changed column, a renamed heading) and every per-tree check below
# would pass on nothing, or a status change the overrides below rely on could be reverted in the doc unnoticed.
def test_the_plan_tables_parse_and_the_status_states_its_changes():
    assert len(ROWS) == 14, sorted(ROWS)
    assert len(SWAPS) == 9, sorted(SWAPS)
    assert set(SKINS) == {"palm", "lakeshore", "scorched", "frost", "storm", "crag", "desert"}, SKINS
    assert SKINS["scorched"] == ("minecraft:polished_basalt", "minecraft:nether_wart_block"), SKINS["scorched"]
    assert SKINS["storm"] == ("minecraft:oak_log", "minecraft:dark_oak_leaves"), SKINS["storm"]
    assert SKINS["desert"] == ("minecraft:bone_block", None), SKINS["desert"]
    # teeth: the table as written still holds what the status changed, so the changes are changes
    assert ROWS["sapling_desert_long_isle_north"][0] == ["Sigilyph"]
    assert ROWS["sapling_scorched_great_crater"][1] == "44-52"
    for sid, (_change, phrase) in CHANGES.items():
        assert sid in ROWS and phrase in PLAN_FLAT, (sid, "Plan v2 status no longer says", phrase)


# ------------------------------------------------------------------ rule 1 and the siting clearances

# Without it a tree is added, dropped or renamed away from the plan's 14, and its pool, blocks and prefab drift apart.
def test_fourteen_pins_the_plans_ids_each_with_a_pool_and_a_known_theme():
    assert len(PINS) == 14 and len(PIN) == 14, [p["id"] for p in PINS]
    assert set(PIN) == set(ROWS), (sorted(set(PIN) ^ set(ROWS)))
    habitats = {h["id"]: h for h in SPAWNS["habitats"]}
    for sid, p in PIN.items():
        assert p["theme"] in SKINS and sid.startswith("sapling_%s_" % p["theme"]), (sid, p["theme"])
        assert sid in habitats and habitats[sid]["mechanism"] == "habitat_block", sid
    assert {h for h in habitats if h.startswith("sapling_")} == set(PIN)


# Without it two themed trees crowd one country (the first pass stood 250 apart; the owner: "we need to go back and
# really make sure we are dispersing the trees enough").
def test_themed_saplings_stand_at_least_800_apart():
    close = [(a["id"], b["id"], round(_dist((a["x"], a["z"]), (b["x"], b["z"]))))
             for a, b in itertools.combinations(PINS, 2)
             if _dist((a["x"], a["z"]), (b["x"], b["z"])) < THEMED_SPACING]
    assert not close, close


def _elder_points_from_blocks():
    pts = {}
    for b in ALL_BLOCKS:
        if b["id"].startswith("elder_") and b.get("style") == "activated":
            pts.setdefault(b["pool"].split(":", 1)[1], []).append((b["position"]["x"], b["position"]["z"]))
    return pts


# Without it a themed tree stands in an elder's wood, where the two nests share one reach and read as one place. The
# elders here are the nested ones (every elder_* activated block in data/habitat_blocks.json, committed data).
def test_themed_saplings_stand_at_least_400_from_every_nested_elder():
    elders = _elder_points_from_blocks()
    assert len(elders) == 52, len(elders)
    close = [(s["id"], e, round(_dist((s["x"], s["z"]), q))) for s in PINS for e, qs in elders.items() for q in qs
             if _dist((s["x"], s["z"]), q) < ELDER_SPACING]
    assert not close, close


# Without it the same rule is checked only against the nests: an elder the site files place with no nest (or a
# nest moved off its trunk) could stand inside 400 of a themed tree.
def test_themed_saplings_stand_at_least_400_from_every_sited_elder():
    et, gr = SITES / "elder_trees.json", SITES / "tree_grove_foothill_woods.json"
    if not (et.is_file() and gr.is_file()):
        pytest.skip("no derived/sites/elder_trees.json or tree_grove_foothill_woods.json (derived/ is gitignored)")
    pts = [(s["x"], s["z"]) for r in json.loads(et.read_text(encoding="utf-8"))["regions"] for s in r["sites"]]
    pts += [(e["x"], e["z"]) for e in json.loads(gr.read_text(encoding="utf-8"))["elders"]]
    assert len(pts) == 52, len(pts)
    close = [(s["id"], q, round(_dist((s["x"], s["z"]), q))) for s in PINS for q in pts
             if _dist((s["x"], s["z"]), q) < ELDER_SPACING]
    assert not close, close


# Without it a tree lands in a town or on a building: its prefab and setting are placed over whatever stands there.
def test_themed_saplings_clear_every_town_centre_by_120_and_every_placement_by_100():
    towns = [(t["id"], t["centre"]["x"], t["centre"]["z"])
             for t in json.loads((DATA / "towns.json").read_text(encoding="utf-8"))["towns"]
             if (t.get("centre") or {}).get("x") is not None]
    placed = [(p["id"], p["position"]["x"], p["position"]["z"])
              for p in json.loads((DATA / "placements.json").read_text(encoding="utf-8"))["placements"]
              if isinstance(p.get("position"), dict) and p["position"].get("x") is not None]
    assert len(towns) >= 20 and len(placed) >= 100, (len(towns), len(placed))
    bad = [(s["id"], "town", i, round(_dist((s["x"], s["z"]), (x, z)))) for s in PINS for i, x, z in towns
           if _dist((s["x"], s["z"]), (x, z)) < OFF_TOWN]
    bad += [(s["id"], "placement", i, round(_dist((s["x"], s["z"]), (x, z)))) for s in PINS for i, x, z in placed
            if _dist((s["x"], s["z"]), (x, z)) < OFF_PLACEMENT]
    assert not bad, bad


# ------------------------------------------------------------------ the pools

@pytest.fixture(scope="module")
def compiled():
    files, _routes, _habitats = CS.build(SPAWNS, ROUTES)
    out = {}
    for h in SPAWNS["habitats"]:
        key = "data/cobblers/habitat_pools/%s.json" % h["id"]
        assert key in files, key
        out[h["id"]] = json.loads(files[key])["spawns"]
    return out


SAPLING_POOLS = [h["id"] for h in SPAWNS["habitats"]
                 if h["id"].startswith(("elder_", "sapling_")) or h["id"] == "route_1_sapling_crown"]


def _tree_points():
    """{pool: [(x, z)]}: where each sapling pool's tree stands, read from the activated blocks that name it."""
    pts = {}
    for b in ALL_BLOCKS:
        if b.get("style") == "activated":
            pts.setdefault(b["pool"].split(":", 1)[1], []).append((b["position"]["x"], b["position"]["z"]))
    return pts


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


@pytest.fixture(scope="module")
def families(species_files):
    """{species: family root}, the union of the jar's evolutions results and preEvolution links."""
    z, files = species_files
    parent = {sp: sp for sp in files}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for sp, n in files.items():
        d = json.loads(z.read(n))
        links = [ev.get("result", "") for ev in d.get("evolutions") or []] + [d.get("preEvolution") or ""]
        for other in links:
            o = _norm(other.split(" ")[0])
            if o in parent:
                parent[find(sp)] = find(o)
    return {sp: find(sp) for sp in files}


# Without it a sapling (themed, elder or Route 1) mixes two lines and stops being one species' nest (rule 1): Fletchinder
# with Talonflame is one line, Wingull with a Pidgey is two.
def test_every_sapling_pool_is_one_evolution_line(compiled, families):
    fam = families
    # teeth: the pairs this rule must tell apart
    assert fam["fletchling"] == fam["talonflame"] and fam["wattrel"] == fam["kilowattrel"]
    assert fam["wingull"] != fam["pidgey"] and fam["vullaby"] != fam["sigilyph"] and fam["swablu"] != fam["delibird"]
    assert len(SAPLING_POOLS) == 52 + 1 + 14, len(SAPLING_POOLS)
    mixed = {}
    for hid in SAPLING_POOLS:
        roots = {fam.get(s["species"], "?" + s["species"]) for s in compiled[hid]}
        if len(roots) != 1:
            mixed[hid] = sorted(s["species"] for s in compiled[hid])
    assert not mixed, mixed


# Without it the same bird line comes back within a walk of itself (rule 2; the owner: "It's okay to repeat but they
# shouldn't be close"): the first pass put two Skarmory crags 250 apart. Distance is between the nearest blocks of the
# two trees, across the whole map, themed trees, elders and the Route 1 sapling alike.
def test_no_bird_line_sits_on_two_saplings_closer_than_1000(compiled, families):
    pts = _tree_points()
    unplaced = [h for h in SAPLING_POOLS if h not in pts]
    assert not unplaced, ("sapling pools no activated block names", unplaced)
    line = {h: {families.get(s["species"], "?" + s["species"]) for s in compiled[h]} for h in SAPLING_POOLS}
    close, repeats = [], 0
    for a, b in itertools.combinations(SAPLING_POOLS, 2):
        if line[a] & line[b]:
            repeats += 1
            d = min(_dist(p, q) for p in pts[a] for q in pts[b])
            if d < LINE_SPACING:
                close.append((sorted(line[a] & line[b]), a, b, round(d)))
    assert not close, close
    # teeth: lines do repeat on the map (Swablu, Starly, Noctowl ...), so the distance check has cases to judge
    assert repeats >= 10, repeats


# Without it a themed tree's bird drifts from the plan: the wrong line for its country, a stage the plan does not
# give (a Talonflame-only crater, Pelipper back on the level-cap-trap palm), or levels off the table (the crater's 51
# and 52 over Blaine's cap). The status's three changes apply: Vullaby on the Long Isle desert tree, the crater at
# 44-50, the Sunset west palm Wingull only at 16-20.
@pytest.mark.parametrize("sid", IDS)
def test_each_themed_pool_holds_the_plans_bird_line_at_the_plans_levels(sid, compiled):
    line, levels = _plan(sid)
    pool = compiled[sid]
    got = [s["species"] for s in pool]
    assert line[0] in got, (sid, "the plan's bird missing", line[0], got)
    base = next(s for s in pool if s["species"] == line[0])
    assert base["bucket"] == "common", (sid, base)
    assert set(got) <= set(line), (sid, "species the plan's line does not give", sorted(set(got) - set(line)))
    off = [(s["species"], s["levelRange"]) for s in pool if s["levelRange"] != levels]
    assert not off, (sid, "levels, plan", levels, off)
    if sid == "sapling_palm_sunset_west":
        assert got == ["wingull"], got


# Without it an elder swap is undone or half done: the old bird back (a line repeated inside 1,000 blocks again), the
# new line missing a stage the plan gives, or its levels off the table.
@pytest.mark.parametrize("eid", sorted(SWAPS))
def test_each_elder_swap_holds_its_new_line_at_its_levels(eid, compiled):
    line, levels = SWAPS[eid]
    pool = compiled[eid]
    assert {s["species"] for s in pool} == set(line), (eid, sorted(s["species"] for s in pool), line)
    off = [(s["species"], s["levelRange"]) for s in pool if s["levelRange"] != levels]
    assert not off, (eid, levels, off)


# Without it a sapling pool names a species the server has no data for, or one Cobblemon ships unimplemented (no model;
# it never spawns) that nothing in the pack implements: Emolga, Noibat, Gligar, Tropius and the rest were new to the
# pools in plan v2. Implementation is read from the jar and from species_additions in the EXP-000 runtime's datapacks
# and mods.
def test_every_sapling_species_is_a_jar_species_something_implements(compiled, species_files):
    z, files = species_files
    implemented = {sp for sp, n in files.items() if json.loads(z.read(n)).get("implemented") is True}
    server = _jar().parent.parent
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
    species = {s["species"] for h in SAPLING_POOLS for s in compiled[h]}
    assert {"emolga", "noibat", "gligar", "tropius", "vullaby", "flamigo"} <= species
    bad_path = sorted(s for s in species if not RESOURCE_PATH.fullmatch(s))
    assert not bad_path, bad_path
    unknown = sorted(species - set(files))
    assert not unknown, unknown
    unimplemented = sorted(species - implemented)
    assert not unimplemented, unimplemented


# ------------------------------------------------------------------ the nests

def _nests(sid):
    return [b for b in ALL_BLOCKS if b.get("pool") == "cobblers:%s" % sid]


# Without it a themed tree is a nest in name only: fewer than three blocks, a block pointing at another tree's pool, a
# natural block (a bird now and then), a ReplaceSpawns block, a block left `planned`, or fewer birds than the owner's 20.
@pytest.mark.parametrize("sid", IDS)
def test_each_themed_sapling_has_three_activated_nest_blocks_on_its_own_pool(sid):
    nests = _nests(sid)
    assert len(nests) >= MIN_NESTS, (sid, [b["id"] for b in nests])
    for b in nests:
        assert b["id"].startswith(sid + "_"), (sid, b["id"])
        assert b["style"] == "activated" and b["replace_spawns"] is False, (b["id"], b["style"], b["replace_spawns"])
        assert b["activated"] == ACTIVATED, (b["id"], b["activated"])
        assert b.get("status") in ("placed", "verified"), (b["id"], b.get("status"))
    assert sum(b["activated"]["max_spawns"] for b in nests) >= AT_LEAST_PER_TREE, sid
    # and no sapling_ block names a pool that is not its own tree's
    strays = [b["id"] for b in SAPLING_BLOCKS if not any(b["id"].startswith(i + "_") and b["pool"] == "cobblers:" + i
                                                          for i in IDS)]
    assert not strays, strays


def mc_rotate(x, z, rotation, pivot=(0, 0)):
    """Minecraft's StructureTemplate.transform for mirror NONE: with pivot (i, j) and a template cell (k, l),
    CLOCKWISE_90 -> (i + j - l, j - i + k), CLOCKWISE_180 -> (i + i - k, j + j - l),
    COUNTERCLOCKWISE_90 -> (i - j + l, i + j - k), NONE -> (k, l). `place template` uses pivot 0, 0."""
    i, j = pivot
    return {"none": (x, z), "clockwise_90": (i + j - z, j - i + x), "180": (i + i - x, j + j - z),
            "counterclockwise_90": (i - j + z, i + j - x)}[rotation]


UNROTATE = {"none": "none", "clockwise_90": "counterclockwise_90", "180": "180", "counterclockwise_90": "clockwise_90"}


# Without it the independent rotation above could be wrong the same way as the tool's and the seat test below would
# agree with a mirrored tree: clockwise seen from above turns north (-z) to east (+x), and the tool's rotate must agree.
def test_the_rotation_is_minecrafts_and_agrees_with_place_town():
    import place_town
    assert mc_rotate(0, -1, "clockwise_90") == (1, 0) and mc_rotate(1, 0, "clockwise_90") == (0, 1)
    assert mc_rotate(0, -1, "counterclockwise_90") == (-1, 0)
    for rot in UNROTATE:
        for x, z in ((3, 7), (-5, 2), (0, 0)):
            assert mc_rotate(*mc_rotate(x, z, rot), UNROTATE[rot]) == (x, z), (rot, x, z)
            assert mc_rotate(x, z, rot) == tuple(place_town.rotate(x, z, rot)), (rot, x, z)
    assert {p["rotation"] for p in PINS} == set(UNROTATE), "every rotation is exercised by some pin"


_PREFAB = {}


def _prefab(theme):
    """(sidecar, {(x, y, z): name}) of sapling_<theme>, from the NBT."""
    if theme not in _PREFAB:
        side = json.loads((THEMED / ("sapling_%s.json" % theme)).read_text(encoding="utf-8"))
        t = structure_nbt.load(THEMED / ("sapling_%s.nbt" % theme))
        blocks = {(x, y, z): t["palette"][s][0] for x, y, z, s in t["blocks"]}
        assert len(blocks) > 1000, theme
        _PREFAB[theme] = (side, blocks)
    return _PREFAB[theme]


def _template_cell(pin, side, pos):
    """The template cell a world position falls in when `place template` seats the prefab so its trunk centre's base
    (trunk_origin) lands on (x, ground + 1, z) with the pin's rotation."""
    ox, oy, oz = side["trunk_origin"]
    qx, qz = mc_rotate(ox, oz, pin["rotation"])
    px, py, pz = pin["x"] - qx, pin["ground_y"] + 1 - oy, pin["z"] - qz
    tx, tz = mc_rotate(pos[0] - px, pos[2] - pz, UNROTATE[pin["rotation"]])
    return tx, pos[1] - py, tz


def _buried_in(blocks, cell, materials):
    """None when the cell is one of `materials` and all six faces are closed; else what fails."""
    here = blocks.get(cell)
    if here not in materials:
        return ("cell", here)
    open_faces = [(f, blocks.get((cell[0] + f[0], cell[1] + f[1], cell[2] + f[2]))) for f in FACES
                  if blocks.get((cell[0] + f[0], cell[1] + f[1], cell[2] + f[2])) in NON_FULL]
    return ("open faces", open_faces) if open_faces else None


# Without it a nest block is set beside its tree (in the open, where a player sees and breaks it, or in air), in a
# snow layer or a leaf with an open face, or as a block the tree is not made of (a log patch in a bone tree): as
# `place template` seats the prefab, each block's cell must be the theme's own trunk or crown block (The skins), all six
# face neighbours solid, and its mimic that block, so the first setblock does not change the tree.
@pytest.mark.parametrize("sid", IDS)
def test_every_nest_block_is_buried_in_its_trees_own_trunk_or_crown(sid):
    pin = PIN[sid]
    side, blocks = _prefab(pin["theme"])
    own = {m for m in SKINS[pin["theme"]] if m}
    ox, oy, oz = side["trunk_origin"]
    # teeth: the trunk's surface at y 30 (bare trunk between the storeys) is trunk material with an open face, and
    # the trunk's centre cell there is buried
    edge = max(x for (x, y, z), n in blocks.items() if y == oy + 30 and z == oz and n in own)
    assert _buried_in(blocks, (edge, oy + 30, oz), own) is not None, (sid, "the check accepts an exposed cell")
    assert _buried_in(blocks, (ox, oy + 30, oz), own) is None, (sid, "the trunk centre at y 30 is not buried")
    for b in _nests(sid):
        p = b["position"]
        cell = _template_cell(pin, side, (p["x"], p["y"], p["z"]))
        fail = _buried_in(blocks, cell, own)
        assert fail is None, (b["id"], pin["rotation"], cell, fail, own)
        assert b["mimic"] == blocks[cell], (b["id"], b["mimic"], blocks[cell])
        # and it is the cell the prefab's sidecar names as a nest: a mirrored rotation that still lands in leaves
        # (a wide crown) is caught here, not only by the material
        recorded = {(n["at"][0] + ox, n["at"][1] + oy, n["at"][2] + oz) for n in side["nests"]}
        assert cell in recorded, (b["id"], pin["rotation"], cell, sorted(recorded))


# ------------------------------------------------------------------ the shape family

def _limb_sectors(blocks, centre, y0, y1, materials, r_min):
    """How many of 8 compass sectors hold a `materials` block r_min or more from centre (x, base y, z), y0..y1 above
    the base."""
    cx, by, cz = centre
    s = set()
    for (x, y, z), n in blocks.items():
        if y0 <= y - by <= y1 and n in materials and math.hypot(x - cx, z - cz) >= r_min:
            s.add(int((math.atan2(z - cz, x - cx) + math.pi) / (2 * math.pi) * 8) % 8)
    return len(s)


def _storey_bands():
    import tree_grove
    t = tree_grove.TIERS["elder"]
    # a limb's root rises 0-2 above its storey, its tip 1-3 more (tree_grove.big_tree)
    return [(t["floor"] + i * t["gap"], t["floor"] + i * t["gap"] + 4) for i in range(t["storeys"])]


RING_R, RING_SECTORS, BARE = 10, 6, (28, 34)


# Without it the ring measure below could pass on anything, or the elder's storeys could move while the saplings are
# still judged against the old heights: the measure must find the elder prefab's two storeys and nothing between them.
def test_the_storey_measure_finds_the_elders_own_storeys():
    assert _storey_bands() == [(20, 24), (38, 42)], _storey_bands()
    side = json.loads((ELDER_PREFABS / "elder_oak_a.json").read_text(encoding="utf-8"))
    t = structure_nbt.load(ELDER_PREFABS / "elder_oak_a.nbt")
    blocks = {(x, y, z): t["palette"][s][0] for x, y, z, s in t["blocks"]}
    ox, oy, oz = side["trunk_origin"]
    c = side["habitat"]["trunk"][0] // 2
    centre = (ox + c, oy, oz + c)
    logs = {"minecraft:oak_log"}
    for lo, hi in _storey_bands():
        assert _limb_sectors(blocks, centre, lo, hi, logs, RING_R) >= RING_SECTORS, (lo, hi)
    assert _limb_sectors(blocks, centre, BARE[0], BARE[1], logs, 6) == 0


# Without it a themed tree stops reading as the world tree's family on the horizon (rule 4; the owner: "a player should
# know what they see on a horizon"): a trunk that breaks or changes material low down, no storeys of near-level limbs
# at the elder's heights, limbs smeared up the bare trunk between them, or a tree much shorter or taller than an elder.
@pytest.mark.parametrize("theme", sorted(SKINS))
def test_each_sapling_prefab_keeps_the_elders_trunk_storeys_and_height(theme):
    side, blocks = _prefab(theme)
    trunk = SKINS[theme][0]
    ox, oy, oz = side["trunk_origin"]
    gaps = [y for y in range(0, TRUNK_TO + 1) if blocks.get((ox, oy + y, oz)) != trunk]
    assert not gaps, (theme, "trunk column not %s at y" % trunk, gaps)
    for lo, hi in _storey_bands():
        n = _limb_sectors(blocks, (ox, oy, oz), lo, hi, {trunk}, RING_R)
        assert n >= RING_SECTORS, (theme, "storey", lo, hi, "limbs in", n, "of 8 sectors")
    between = _limb_sectors(blocks, (ox, oy, oz), BARE[0], BARE[1], {trunk}, 6)
    assert between == 0, (theme, "trunk material 6 or more out between the storeys", between)
    top = max(y for (_x, y, _z) in blocks) - oy
    assert HEIGHT[0] <= top <= HEIGHT[1], (theme, top)


# ------------------------------------------------------------------ the pins round-trip

# Without it the nest blocks and the pins or prefabs drift apart: a pin moved, a prefab regenerated with its nests in
# other cells, a block hand-edited in data/habitat_blocks.json. `records` (without --write) is what the tool would
# write; statuses aside, it must be exactly the sapling_ blocks the data holds, in content and in number.
def test_the_records_the_tool_computes_are_exactly_the_sapling_blocks():
    import themed_saplings as TS
    recs = TS.records(TS.load_pins(), TS.sides())

    def strip(bs):
        return {b["id"]: {k: v for k, v in b.items() if k != "status"} for b in bs}

    got, have = strip(recs), strip(SAPLING_BLOCKS)
    assert len(recs) == len(got) == len(SAPLING_BLOCKS), (len(recs), len(got), len(SAPLING_BLOCKS))
    assert set(got) == set(have), (sorted(set(got) ^ set(have)))
    diff = {i: {k: (got[i].get(k), have[i].get(k)) for k in set(got[i]) | set(have[i]) if got[i].get(k) != have[i].get(k)}
            for i in got if got[i] != have[i]}
    assert not diff, diff
