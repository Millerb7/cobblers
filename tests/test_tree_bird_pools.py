"""The species of the 66 bird trees, by height band, against the species designer's file (data/tree_bird_species.json).

Written by the test author, not by the session that built tools/tree_birds.py or the designer's file. The expected
species are READ FROM the designer's file; the pools under test are what the server is given: `compile_spawns.build`
over data/spawns.json (a weight-0 entry is not compiled, so an unplaced evolution stage is not a spawn).

Independent sources: data/tree_bird_species.json (line, bands, levels, crown_levels per tree), the owner's rules as
quoted there (one line per tree; "not like pidove or trumbeak"), the 10 route-bird lines named in the task (typed here
in full, not read from the designer's `basis.excluded_lines`), and the Cobblemon jar's species files for evolution
levels and families (SKIPPED without the jar: a skip is not a pass).

Pools: the tree's own id is its CROWN pool (the four old nests); `tbird_<tree>_low` and `_mid` are the storey nests.
The 4 Foothill grove elders have a crown pool only (no geometry for storey nests). The world tree's four pools
(`tbird_world_tree_foothill_woods_*`) come from data/world_tree_bird_species.json (the owner's set, an exception to the one-line rule) and are tested apart.

Not covered: that a bird spawns in the tree (nest placement, `tools/tree_birds_audit.py` and a staging count); that
the species fit their country (tools/spawn_habitat_audit.py); the compiled JSON's keys inside Cobblemon
(tests/test_habitat_blocks_activated.py).
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

DATA = ROOT / "data"
SPAWNS = json.loads((DATA / "spawns.json").read_text(encoding="utf-8"))
ROUTES = json.loads((DATA / "routes.json").read_text(encoding="utf-8"))
DESIGN = json.loads((DATA / "tree_bird_species.json").read_text(encoding="utf-8"))["trees"]
BLOCKS = json.loads((DATA / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
WORLD = "world_tree_foothill_woods"
GROVE = ("elder_foothill_grove_1", "elder_foothill_grove_2", "elder_foothill_grove_3", "elder_foothill_grove_4")
BANDS = ("low", "mid", "crown")
# The route birds the owner does not want on a tree, in full lines (base first), typed here from Pokemon's own
# evolutionary lines rather than read from the designer's file.
ROUTE_LINES = {
    "pidgey": ("pidgey", "pidgeotto", "pidgeot"), "spearow": ("spearow", "fearow"),
    "starly": ("starly", "staravia", "staraptor"), "pidove": ("pidove", "tranquill", "unfezant"),
    "pikipek": ("pikipek", "trumbeak", "toucannon"), "fletchling": ("fletchling", "fletchinder", "talonflame"),
    "taillow": ("taillow", "swellow"), "rookidee": ("rookidee", "corvisquire", "corviknight"),
    "wingull": ("wingull", "pelipper"), "hoothoot": ("hoothoot", "noctowl"),
}
ROUTE_SPECIES = {s for line in ROUTE_LINES.values() for s in line}


def pool_id(tid, band):
    return tid if band == "crown" else "tbird_%s_%s" % (tid, band)


def level_band(tid, band):
    v = DESIGN[tid]
    text = v.get("crown_levels") if band == "crown" and v.get("crown_levels") else v["levels"]
    lo, hi = (int(x) for x in text.split("-"))
    return lo, hi


@pytest.fixture(scope="module")
def compiled():
    files, _routes, _habitats = CS.build(SPAWNS, ROUTES)
    out = {}
    for h in SPAWNS["habitats"]:
        key = "data/cobblers/habitat_pools/%s.json" % h["id"]
        assert key in files, key
        out[h["id"]] = json.loads(files[key])["spawns"]
    return out


def _species(compiled, pool):
    return [s["species"] for s in compiled[pool]]


def _jar():
    import battle_sim
    for c in battle_sim.JAR_CANDIDATES:
        if c.is_file():
            return c
    pytest.skip("no Cobblemon jar outside the live server (EXP-000 runtime copy)")


@pytest.fixture(scope="module")
def jar():
    z = zipfile.ZipFile(_jar())
    files = {n.rsplit("/", 1)[1][:-5]: n for n in z.namelist()
             if n.startswith("data/cobblemon/species/") and n.endswith(".json")}
    cache = {}

    def get(sp):
        if sp not in cache:
            cache[sp] = json.loads(z.read(files[sp]))
        return cache[sp]
    return files, get


def _evolves_at(get, sp):
    """The lowest level at which `sp`'s pre-evolution evolves into it by level-up, or None."""
    pre = get(sp).get("preEvolution")
    if not pre:
        return None
    levels = []
    for ev in get(pre.split()[0]).get("evolutions") or []:
        if ev.get("result", "").split()[:1] == [sp]:
            levels += [int(q["minLevel"]) for q in ev.get("requirements") or [] if q.get("variant") == "level"]
    return min(levels) if levels else None


# Without it the file the rest of this module is checked against could be emptied or half-parsed (a renamed key) and
# every per-tree test below would pass on nothing: 66 trees, a non-empty line, three bands, a level range each.
def test_the_designers_file_has_the_66_trees_each_with_a_line_three_bands_and_levels():
    assert len(DESIGN) == 66, len(DESIGN)
    for tid, v in DESIGN.items():
        assert v["line"] and set(v["bands"]) == set(BANDS), tid
        for band in BANDS:
            assert v["bands"][band], (tid, band)
            assert set(v["bands"][band]) <= set(v["line"]), (tid, band)
            lo, hi = level_band(tid, band)
            assert 1 <= lo <= hi <= 100, (tid, band, lo, hi)
    assert set(GROVE) <= set(DESIGN)


# Without it a tree spawns a bird of another tree's line (the old shared pools: a Pidgey under a Farfetch'd), which is
# exactly what "each tree its own species" forbids. Checked on EVERY band pool the server is given.
@pytest.mark.parametrize("tid", sorted(DESIGN))
def test_each_tree_spawns_only_its_own_line(tid, compiled):
    for band in BANDS:
        pid = pool_id(tid, band)
        if pid not in compiled:
            assert band != "crown", (tid, "no crown pool")
            continue
        extra = set(_species(compiled, pid)) - set(DESIGN[tid]["line"])
        assert not extra, (tid, band, "species outside the tree's line", sorted(extra))


# Without it a pool drifts from the designer's file in either direction: a band missing the stage the designer placed
# there, or holding one the designer did not (an evolved stage in the wrong height band). The expected species are the
# designer's `bands`, read from the file, never from the generator.
@pytest.mark.parametrize("tid", sorted(DESIGN))
def test_each_band_pool_holds_exactly_the_designers_band(tid, compiled):
    for band in BANDS:
        pid = pool_id(tid, band)
        if pid not in compiled:
            continue
        assert sorted(set(_species(compiled, pid))) == sorted(DESIGN[tid]["bands"][band]), (
            tid, band, _species(compiled, pid), DESIGN[tid]["bands"][band])
    # the 4 grove elders have the crown pool only; every other tree has all three
    have_storey = [b for b in ("low", "mid") if pool_id(tid, b) in compiled]
    assert have_storey == ([] if tid in GROVE else ["low", "mid"]), (tid, have_storey)


# Without it two trees share a line (the owner, 2026-10-21: a unique line each, "not like pidove or trumbeak"): checked
# on the designer's data, on every pool the server is given, and (with the jar) by evolution family, so a branch
# sibling (Wurmple's two lines) or a pre-evolution on another tree is caught as well as an identical species.
def test_no_line_is_on_two_trees(compiled):
    owner, clash = {}, []
    for tid, v in DESIGN.items():
        for sp in v["line"]:
            if owner.setdefault(sp, tid) != tid:
                clash.append((sp, owner[sp], tid))
    assert not clash, ("designer's file", clash)
    seen = {}
    for tid in DESIGN:
        for band in BANDS:
            pid = pool_id(tid, band)
            for sp in set(_species(compiled, pid)) if pid in compiled else ():
                if seen.setdefault(sp, tid) != tid:
                    clash.append((sp, seen[sp], tid))
    assert not clash, ("compiled pools", clash)


# Without it the evolution-family version of the rule goes untested: two different base species of one family on two
# trees (a branch evolution) would still be "no line twice" by species name.
def test_no_evolution_family_is_on_two_trees(jar):
    files, get = jar
    parent = {sp: sp for sp in files}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for sp in files:
        links = [e.get("result", "") for e in get(sp).get("evolutions") or []] + [get(sp).get("preEvolution") or ""]
        for o in links:
            o = o.split(" ")[0]
            if o in parent:
                parent[find(sp)] = find(o)
    # teeth: the jar's families tell the rule's cases apart
    assert find("pidgey") == find("pidgeot") and find("pidgey") != find("hoothoot")
    root = {}
    clash = []
    for tid, v in DESIGN.items():
        for sp in v["line"]:
            if sp in parent and root.setdefault(find(sp), tid) != tid:
                clash.append((sp, root[find(sp)], tid))
    assert not clash, clash


# Without it a route bird comes back to a tree: any stage of the ten lines the owner named (Pidgey, Spearow, Starly,
# Pidove, Pikipek, Fletchling, Taillow, Rookidee, Wingull, Hoothoot), in any band of any of the 66 trees. The lines are
# typed above in full, and with the jar their families are confirmed so the list cannot be short a stage.
def test_no_route_bird_on_any_of_the_66_trees(compiled):
    bad = [(tid, band, sp) for tid in DESIGN for band in BANDS
           for sp in (set(_species(compiled, pool_id(tid, band))) if pool_id(tid, band) in compiled else ())
           if sp in ROUTE_SPECIES]
    assert not bad, bad
    # the designer's own file: no tree LINE contains one either
    assert not [(t, sp) for t, v in DESIGN.items() for sp in v["line"] if sp in ROUTE_SPECIES]


def test_the_route_bird_lines_listed_here_are_the_jars_whole_lines(jar):
    files, get = jar
    for base, line in ROUTE_LINES.items():
        stages, todo = {base}, [base]
        while todo:
            for e in get(todo.pop()).get("evolutions") or []:
                nxt = e.get("result", "").split(" ")[0]
                if nxt and nxt not in stages:
                    stages.add(nxt)
                    todo.append(nxt)
        assert stages == set(line), (base, sorted(stages), line)


# Without it a species spawns outside the tree's level band (the band is the tree's country; over it is over the cap).
# Every compiled entry's range lies inside the designer's `levels` (`crown_levels` for the crown pool of the two trees
# that have one), for every band pool of every tree.
@pytest.mark.parametrize("tid", sorted(DESIGN))
def test_every_species_lies_within_its_trees_level_band(tid, compiled):
    for band in BANDS:
        pid = pool_id(tid, band)
        if pid not in compiled:
            continue
        lo, hi = level_band(tid, band)
        for s in compiled[pid]:
            a, b = (int(x) for x in s["levelRange"].split("-"))
            assert lo <= a <= b <= hi, (tid, band, s["species"], s["levelRange"], (lo, hi))


# Without it an evolved stage spawns below the level it evolves at (a wild Xatu at 21), or a stage no level-up reaches
# (an item or trade evolution) is put on a tree. Read from the jar's species files.
def test_an_evolved_stage_spawns_only_from_its_evolution_level_and_never_by_item(compiled, jar):
    files, get = jar
    bad, evolved = [], 0
    for tid in DESIGN:
        for band in BANDS:
            pid = pool_id(tid, band)
            for s in compiled.get(pid, []):
                if not get(s["species"]).get("preEvolution"):
                    continue
                evolved += 1
                at = _evolves_at(get, s["species"])
                a = int(s["levelRange"].split("-")[0])
                if at is None or a < at:
                    bad.append((tid, band, s["species"], s["levelRange"], "evolves at", at))
    assert evolved >= 20, evolved   # teeth: the rule has cases
    assert not bad, bad


# Without it a nest record names a pool that does not exist (a block that never holds a bird) or a pool has no nest
# (birds the owner approved that can never appear). Records <-> pools, both ways, and the covered trees are exactly
# the designer's trees less the grove elders, plus the world tree.
def test_every_tbird_record_has_its_pool_and_every_tbird_pool_a_record(compiled):
    recs = [b for b in BLOCKS if b["id"].startswith("tbird_")]
    assert len(recs) >= 100, len(recs)
    pools = {b["pool"].split(":", 1)[1] for b in recs}
    assert all(p in compiled for p in pools), sorted(p for p in pools if p not in compiled)
    pooled = {h for h in compiled if h.startswith("tbird_")}
    assert pooled == pools, (sorted(pooled - pools), sorted(pools - pooled))
    trees = {p[len("tbird_"):].rsplit("_", 1)[0] for p in pools}
    assert trees == (set(DESIGN) - set(GROVE)) | {WORLD}, sorted(trees ^ ((set(DESIGN) - set(GROVE)) | {WORLD}))


# ---------------------------------------------------------------------------------------- the world tree (PLACEHOLDER)
WORLD_POOLS = ["tbird_%s_%s" % (WORLD, b) for b in ("low", "mid", "high", "crown")]


# Without it the world tree drifts from the owner's set (2026-10-21: "the height of flying mons ... classics, like pidgeot
# and staraptor, or altaria, not a pidove or pikipek"), which is typed here from the owner's message, not read from
# data/world_tree_bird_species.json. The world tree is the owner's deliberate exception to the one-line-per-tree rule
# above (it shares Pidgey, Starly, Taillow, Hoothoot, Rookidee and Swablu lines with route birds and a grove elder), so
# what is asserted is the set itself, the levels climbing with height from the area's 21-23, and that the small birds the
# owner named as unwanted (Pidove, Pikipek) are absent.
def _full(s):
    """A compiled habitat spawn's species and its form: Cobblemon's HabitatSpawn takes the form as `modifiers`."""
    return s["species"] + (" " + s["modifiers"] if s.get("modifiers") else "")


OWNERS_SET = {
    "low": ({"pidgeotto", "staravia", "swablu", "noctowl"}, (22, 26)),
    "mid": ({"pidgeot", "staraptor", "altaria", "swellow"}, (26, 32)),
    "high": ({"pidgeot", "staraptor", "altaria", "togekiss", "corviknight"}, (32, 38)),
    "crown": ({"aerodactyl", "salamence", "dragonite", "articuno galarian", "zapdos galarian", "moltres galarian"}, (38, 45)),
}


def test_the_world_trees_pools_are_the_owners_classics_at_the_owners_levels(compiled):
    for band, (species, (lo, hi)) in OWNERS_SET.items():
        pool = compiled["tbird_%s_%s" % (WORLD, band)]
        assert {_full(s) for s in pool} == species, (band, sorted(_full(s) for s in pool))
        for s in pool:
            a, b = (int(x) for x in s["levelRange"].split("-"))
            want = (40, 45) if _full(s).endswith(" galarian") else (lo, hi)    # the owner: the Galarian birds 40-45
            assert (a, b) == want, (band, _full(s), s["levelRange"])
    got = {_full(s) for b in OWNERS_SET for s in compiled["tbird_%s_%s" % (WORLD, b)]}
    assert not got & {"pidove", "tranquill", "unfezant", "pikipek", "trumbeak", "toucannon"}, got
    # levels climb with height: each band's floor is at or above the one under it, starting at the area's 22
    floors = [OWNERS_SET[b][1][0] for b in ("low", "mid", "high", "crown")]
    assert floors == sorted(floors) and floors[0] >= 22


# Without it the owner's rarities drift (Togekiss and Corviknight rare, Dragonite ultra-rare, Aerodactyl rare, Swablu and
# Noctowl uncommon low). A bucket is Cobblemon's own word and the pools' weights are compiled from it. The high band's
# Pidgeot, Staraptor and Altaria are common (the owner's "(common)" read as covering the three).
def test_the_world_trees_rarities_are_the_owners(compiled):
    rows = {}
    for band in OWNERS_SET:
        for s in compiled["tbird_%s_%s" % (WORLD, band)]:
            rows[(band, _full(s))] = s["bucket"]
    want = {("low", "pidgeotto"): "common", ("low", "staravia"): "common", ("low", "swablu"): "uncommon",
            ("low", "noctowl"): "uncommon", ("mid", "swellow"): "common", ("mid", "pidgeot"): "uncommon",
            ("mid", "staraptor"): "uncommon", ("mid", "altaria"): "uncommon", ("high", "pidgeot"): "common",
            ("high", "staraptor"): "common", ("high", "altaria"): "common", ("high", "togekiss"): "rare",
            ("high", "corviknight"): "rare", ("crown", "aerodactyl"): "rare", ("crown", "salamence"): "rare",
            ("crown", "dragonite"): "ultra-rare", ("crown", "articuno galarian"): "ultra-rare",
            ("crown", "zapdos galarian"): "ultra-rare", ("crown", "moltres galarian"): "ultra-rare"}
    assert rows == want, rows


# Without it the owner's 2026-10-21 exemption widens: the three Galarian legendary birds are crown spawns of the world
# tree ONLY (the Dyna Tree's stand-in), and no other tree's pool, the world tree's other bands included, holds one. Their
# weight stays well under Dragonite's, which stays under Salamence's (the owner: "very rare", "rare").
def test_the_galarian_legendary_birds_are_the_world_trees_crown_and_nothing_else(compiled):
    trio = {"articuno galarian", "zapdos galarian", "moltres galarian"}
    for pid, spawns in compiled.items():
        if not (pid.startswith("tbird_") or pid in DESIGN):
            continue
        got = {_full(s) for s in spawns} & trio
        assert got == (trio if pid == "tbird_%s_crown" % WORLD else set()), (pid, sorted(got))
    w = {_full(s): s["weight"] for s in compiled["tbird_%s_crown" % WORLD]}
    assert max(w[t] for t in trio) * 2 <= w["dragonite"] < w["salamence"], w


# Without it the world tree's pools go unwatched on the properties that do not depend on the species chosen: its
# four pools exist and are non-empty, every entry is inside a sane level range.
def test_the_world_trees_four_pools_exist_and_are_non_empty(compiled):
    for p in WORLD_POOLS:
        assert compiled.get(p), p
        for s in compiled[p]:
            a, b = (int(x) for x in s["levelRange"].split("-"))
            assert 1 <= a <= b <= 100, (p, s)
    assert re.fullmatch(r"[a-z0-9_]+", WORLD)
