"""The Nether's encounter tables: data/encounter_design.json "nether" -> data/spawns.json (mechanism nether_ring_boxes,
nether_tables) -> tools/compile_spawns.py build_nether -> spawn_pool_world/nether/.

WRITTEN BY THE BUILDER of these tables, on the brief's instruction (2026-10-08), not by test-author: an independent
reviewer should re-derive the expectations below before trusting a green run.

Expectations come from outside the generated output:
  - the biome and structure of each table, typed here from docs/mechanics/NETHER_ENCOUNTERS.md sections 2.1-2.6 and 3.3
    (DESIGN_KEYS), and the fire rule's two biomes and its one written exception (the owner's Q7: Chi-Yu's ring);
  - types and implementation read straight from the Cobblemon 1.8.0 jar's species JSON here, with zipfile;
  - the caps from data/league_trainers.json (the Elite Four's top level is the cap after badge 8, the Champion's the
    next one) and the deep ring's 65-75 / 85 from the design's ring table;
  - the near ring from data/world.json's export border divided by the Nether's scale, 8.

The mutation tests change the GENERATOR (compile_spawns.open_sky_forced, build_encounters.nether_entry), never the data.

Not covered, and it needs a running server (NETHER_ENCOUNTERS.md section 6): that a grounded Nether spawn without
canSeeSky appears (N1), what radius neededNearbyBlocks really uses and whether a vine or shroomlight is ever that near
a standing spot (N2), that the structures condition matches inside a fortress, a bastion and a LegendaryMonuments shrine
(N4), and that /checkspawn in the Nether lists only these tables (N3).
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_spawns as CS  # noqa: E402

NETHER = "minecraft:the_nether"
MECH = "nether_ring_boxes"
SPAWNS = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
ENTRIES = [e for e in SPAWNS["entries"] if e["mechanism"] == MECH]
RECORDS = {r["id"]: r for r in SPAWNS.get("nether_tables") or []}

B = lambda *b: {"biomes": ["minecraft:" + x for x in b]}  # noqa: E731
S = lambda *s: {"structures": list(s)}  # noqa: E731
# NETHER_ENCOUNTERS.md: 2.1 nether wastes, 2.2 crimson forest, 2.3 warped forest, 2.4 soul sand valley, 2.5 basalt
# deltas, 2.6 the fortress (minecraft:fortress) and the bastion (minecraft:bastion_remnant), 3.3 the four Ruinous rings
DESIGN_KEYS = {
    "nether_wastes": B("nether_wastes"), "crimson_forest": B("crimson_forest"), "warped_forest": B("warped_forest"),
    "soul_sand_valley": B("soul_sand_valley"), "basalt_deltas": B("basalt_deltas"),
    "fortress_garrison": S("minecraft:fortress"), "bastion_hoard": S("minecraft:bastion_remnant"),
    "ruinous_grasswither": S("legendarymonuments:grasswither_shrine"),
    "ruinous_groundblight": S("legendarymonuments:groundblight_shrine"),
    "ruinous_icerend": S("legendarymonuments:icerend_shrine"),
    "ruinous_firescourge": S("legendarymonuments:firescourge_shrine"),
}
# the hearts (section 2): the block each stands beside, and the wastes' y line
DESIGN_HEARTS = {"nether_wastes": (["minecraft:lava"], 40),
                 "crimson_forest": (["minecraft:weeping_vines", "minecraft:weeping_vines_plant"], None),
                 "warped_forest": (["minecraft:shroomlight"], None), "soul_sand_valley": (["minecraft:bone_block"], None),
                 "basalt_deltas": (["minecraft:magma_block"], None)}
FIRE_BIOMES = {"minecraft:nether_wastes", "minecraft:crimson_forest"}
FIRE_EXCEPTION = "ruinous_firescourge"  # Q7, approved 2026-10-08: the one written exception
RINGS = ("near", "deep")
# mis-assembled 1.8 models (COBBLEVERSE_COMPATIBILITY.md:136-148), the design's UNCONFIRMED picks (Q9, not approved),
# its named dolls, and the soul sand valley's deliberately absent candle ghosts
NEVER = {"tyranitar", "cofagrigus", "turtonator", "talonflame", "capsakid", "scovillain", "stonjourner",
         "greavard", "houndstone", "mandibuzz", "litwick", "lampent", "chandelure"}


def _jar():
    import battle_sim
    try:
        return battle_sim.find_jar()
    except Exception as ex:  # noqa: BLE001
        pytest.skip("no Cobblemon 1.8.0 jar: %s" % ex)


_SPECIES = {}


def _jar_species():
    """{species id: (types, implemented)} read from the jar's species JSON, keyed the way the data writes them."""
    import re
    if _SPECIES:
        return _SPECIES
    out = _SPECIES
    with zipfile.ZipFile(_jar()) as z:
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                d = json.loads(z.read(n))
                k = re.sub(r"[^a-z0-9]", "", d["name"].lower())
                out[k] = ({t.lower() for t in (d.get("primaryType"), d.get("secondaryType")) if t},
                          d.get("implemented") is not False)
    return out


def _table(scope):
    for t in DESIGN_KEYS:
        for r in RINGS:
            if scope == "%s_%s" % (t, r):
                return t, r
    raise AssertionError("scope %s is no designed table and ring" % scope)


def _caps():
    lt = json.loads((ROOT / "data" / "league_trainers.json").read_text(encoding="utf-8"))["trainers"]
    e4 = max(t["levels"][1] for t in lt if t["id"].startswith("elite_"))
    champ = max(t["levels"][1] for t in lt if t["id"].startswith("champion_"))
    # (cap, band, next cap) per ring: NETHER_ENCOUNTERS.md section 1
    return {"near": (e4, (54, 60), champ), "deep": (100, (65, 75), 85)}


def _lv(e):
    lo, hi = map(int, e["level"].split("-"))
    return lo, hi


# ----------------------------------------------------------------- checks, written as functions so mutations can feed them

def binding_problems(entries):
    out = []
    for e in entries:
        t, _ = _table(e["scope"])
        c = e.get("conditions") or {}
        key = DESIGN_KEYS[t]
        if c.get("dimensions") != [NETHER]:
            out.append((e["id"], "dimensions", c.get("dimensions")))
        if sorted(e.get("biomes") or []) != sorted(key.get("biomes") or []):
            out.append((e["id"], "biomes", e.get("biomes")))
        if (c.get("structures") or None) != key.get("structures"):
            out.append((e["id"], "structures", c.get("structures")))
    return out


def fire_problems(entries, species):
    out = []
    for e in entries:
        t, _ = _table(e["scope"])
        types = species[e["species"].split()[0]][0]
        if "fire" in types and not (set(DESIGN_KEYS[t].get("biomes") or []) and set(DESIGN_KEYS[t]["biomes"]) <= FIRE_BIOMES) \
                and t != FIRE_EXCEPTION:
            out.append((e["id"], sorted(types)))
    return out


def pool_problems(files):
    out = []
    for rel, text in files.items():
        for s in json.loads(text)["spawns"]:
            c = s["condition"]
            if c.get("dimensions") != [NETHER]:
                out.append((rel, s["id"], "dimensions"))
            if "canSeeSky" in c:
                out.append((rel, s["id"], "canSeeSky"))
    return out


# ----------------------------------------------------------------- the tables


def test_every_designed_table_and_ring_exists_and_nothing_else():
    assert set(RECORDS) == {"%s_%s" % (t, r) for t in DESIGN_KEYS for r in RINGS}
    assert {e["scope"] for e in ENTRIES} == set(RECORDS)


def test_every_entry_is_bound_to_the_nether_and_carries_its_tables_biome_or_structure():
    assert ENTRIES
    assert not binding_problems(ENTRIES)


def test_the_fire_rule_holds_with_only_the_written_chi_yu_exception():
    species = _jar_species()
    assert not fire_problems(ENTRIES, species)
    # the exception is written on Chi-Yu's ring and nowhere else, and it is used: Houndour's line is Fire
    design = json.loads((ROOT / "data" / "encounter_design.json").read_text(encoding="utf-8"))["nether"]["tables"]
    assert [t for t, v in design.items() if v.get("fire_exception")] == [FIRE_EXCEPTION]
    assert any("fire" in species[e["species"]][0] for e in ENTRIES if _table(e["scope"])[0] == FIRE_EXCEPTION)
    # and the two forests read apart: the warped forest, the valley and the deltas hold no Fire at all
    for t in ("warped_forest", "soul_sand_valley", "basalt_deltas", "fortress_garrison", "bastion_hoard"):
        assert not [e["species"] for e in ENTRIES if _table(e["scope"])[0] == t and "fire" in species[e["species"]][0]], t


def test_harness_the_fire_check_bites():
    species = _jar_species()
    fake = [{"id": "x", "scope": "warped_forest_near", "species": "magmar"}]
    assert fire_problems(fake, species)
    assert not fire_problems([dict(fake[0], scope="nether_wastes_near")], species)
    assert not fire_problems([dict(fake[0], scope="ruinous_firescourge_deep")], species)


def test_levels_sit_in_the_ring_band_and_only_presences_pass_the_cap():
    caps = _caps()
    assert caps["near"][0] == 60 and caps["near"][2] == 62, caps  # LEAGUE_LEVEL_CAP.md section 2, measured there
    bad = []
    for e in ENTRIES:
        _, ring = _table(e["scope"])
        cap, (blo, bhi), nxt = caps[ring]
        lo, hi = _lv(e)
        if not e.get("heart"):
            if lo < blo or hi > bhi:
                bad.append((e["id"], e["level"], "base outside %d-%d" % (blo, bhi)))
        elif hi > cap:
            # above the cap only as a presence: uncommon, from the band's top, no further than the next cap
            if e["bucket"] != "uncommon" or lo < bhi or hi > nxt:
                bad.append((e["id"], e["level"], e["bucket"]))
        elif lo < blo:
            bad.append((e["id"], e["level"], "heart below the band"))
    assert not bad, bad
    for rid, rec in RECORDS.items():
        cap, band, nxt = caps[_table(rid)[1]]
        assert (rec["level_band"]["minimum"], rec["level_band"]["maximum"], rec["level_band"]["cap"]) == (band[0], band[1], cap)


def test_every_species_is_implemented_in_the_jar_and_none_is_left_out_by_the_design():
    species = _jar_species()
    dolls = set(json.loads((ROOT / "modpack" / "manifest" / "client-pack-atm-subset.json").read_text(encoding="utf-8")).get("species") or [])
    names = {e["species"].split()[0] for e in ENTRIES}
    assert not [n for n in names if n not in species or not species[n][1]], "not implemented in the jar"
    assert not names & dolls, names & dolls
    assert not names & NEVER, names & NEVER


def test_hearts_key_on_the_designed_block_and_never_on_a_position():
    for t, (blocks, maxy) in DESIGN_HEARTS.items():
        for r in RINGS:
            hearts = [e for e in ENTRIES if e["scope"] == "%s_%s" % (t, r) and e.get("heart")]
            assert hearts, (t, r)
            for e in hearts:
                c = e["conditions"]
                assert c.get("neededNearbyBlocks") == blocks, (e["id"], c)
                assert c.get("maxY") == maxy, (e["id"], c)
                assert not set(c) & {"minX", "maxX", "minZ", "maxZ", "minY"}, e["id"]
                assert e.get("alpha") is True, e["id"]
    # no structure table has a heart
    assert not [e["id"] for e in ENTRIES if e.get("heart") and _table(e["scope"])[0] not in DESIGN_HEARTS]


def test_the_nethers_new_nearby_blocks_decide_nothing_outside_the_nether():
    """shroomlight, bone blocks and weeping vines are named by no overworld spawn condition (data/spawn_blocks.json, as
    scanned 2026-09-15); a condition that names one must also name the Nether, so a placed lamp or bone block in the
    overworld or the pocket decides no encounter (contract C4's concern)."""
    known = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    new = {b for blocks, _ in DESIGN_HEARTS.values() for b in blocks} - known
    assert new >= {"minecraft:shroomlight", "minecraft:bone_block"}, new
    for e in SPAWNS["entries"]:
        c = e.get("conditions") or {}
        if set(c.get("neededNearbyBlocks") or []) & new:
            assert c.get("dimensions") == [NETHER], e["id"]


def test_the_rings_are_the_overworld_border_over_eight_and_everything_else():
    border = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["export"]["border"]
    near = [border["min_x"] // 8, (border["max_x"] + 1) // 8 - 1, border["min_z"] // 8, (border["max_z"] + 1) // 8 - 1]
    assert near == [-128, 1151, -128, 1151], near
    boxes = {}
    for rid, rec in RECORDS.items():
        boxes.setdefault(_table(rid)[1], {tuple(b) for b in rec["boxes"]})
        assert {tuple(b) for b in rec["boxes"]} == boxes[_table(rid)[1]], rid
    assert boxes["near"] == {tuple(near)}
    allb = sorted(boxes["near"] | boxes["deep"])
    for i, a in enumerate(allb):
        for b in allb[i + 1:]:
            assert not (a[0] <= b[1] and b[0] <= a[1] and a[2] <= b[3] and b[2] <= a[3]), (a, b)
    # the deep ring reaches both border readings on record (data/dimension_overrides.json count_windows)
    win = json.loads((ROOT / "data" / "dimension_overrides.json").read_text(encoding="utf-8"))["count_windows"]
    lo = min(win["the_nether_unscaled"]["min"], win["the_nether_centre_over_8"]["min"])
    hi = max(win["the_nether_unscaled"]["max"], win["the_nether_centre_over_8"]["max"])
    area = sum((b[1] - b[0] + 1) * (b[3] - b[2] + 1) for b in allb)
    assert area == (hi - lo + 1) ** 2, "the rings do not tile the Nether between both border readings"


def test_the_compiled_pools_carry_the_nether_and_no_sky():
    files, summ = CS.build_nether(SPAWNS)
    assert len(files) == len(RECORDS) == len(summ)
    assert all(rel.startswith("data/cobblers/spawn_pool_world/nether/") for rel in files)
    assert not pool_problems(files)
    for rel, text in files.items():
        rid = rel.rsplit("/", 1)[1][:-5]
        boxes = {tuple(b) for b in RECORDS[rid]["boxes"]}
        for s in json.loads(text)["spawns"]:
            c = s["condition"]
            assert (c["minX"], c["maxX"], c["minZ"], c["maxZ"]) in boxes, s["id"]
            assert s["spawnablePositionType"] == "grounded", s["id"]
            assert ("alpha=true" in s["pokemon"]) == ("_h0" in s["id"]), s["id"]


# ----------------------------------------------------------------- the generator mutated


def test_mutation_a_forced_sky_in_the_compiler_is_caught(monkeypatch):
    monkeypatch.setattr(CS, "open_sky_forced", lambda entry: True)
    files, _ = CS.build_nether(SPAWNS)
    assert pool_problems(files), "the check no longer sees a forced canSeeSky on the Nether's pools (review N154)"


def test_mutation_an_entry_builder_that_drops_the_dimension_is_caught(monkeypatch):
    import build_encounters as BE
    jar = _jar()
    design = json.loads((ROOT / "data" / "encounter_design.json").read_text(encoding="utf-8"))
    real = BE.nether_entry

    def unbound(*a, **k):
        e = real(*a, **k)
        e["conditions"].pop("dimensions", None)
        e["biomes"] = []
        return e

    monkeypatch.setattr(BE, "nether_entry", unbound)
    gen, _, problems = BE.generate_nether(design, BE.Dex(jar), set())
    assert not problems
    entries = [e for es in gen.values() for e in es]
    assert binding_problems(entries), "the check no longer sees an entry that lost its dimension and biome"
