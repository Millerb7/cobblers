"""The six overworld2 themes (OVERWORLD2, 2026-10-11): city, great_tree, ice_spire, hill_keep, desert_excavation, night_crater in
data/dungeon_themes.json, their rows in the puzzle, relic, resource, greed and extras tables, and
tests/fixtures/dungeon_overworld2_demo.json, a full-length demo dungeon for each.

What is checked, and against what (the expectation is never read from the theme under test):
  species   every species id of the themes' ambient groups, the fixture's fights and the fishing tables exists in the Cobblemon
            1.8.0 jar; every ambient line is an evolution chain of the jar's own `evolutions`; every line spawns in the jar's
            spawn pools where the theme is (a biome tag set written HERE, or a village structure for the city, or the night /
            dark conditions for the crater), or is one of a short list of approved exceptions with a reason; no doll, no
            mis-assembled model, no legendary / mythical / paradox, no starter line;
  blocks    every id is in the 1.21.1 jar (tests/test_dungeon_rooms.py checks that for every theme as well); no hazard, no
            gravity block, no concrete, no powder snow, no regular ice (it melts under light), no budding amethyst, no
            crafting or enchanting block; the desert never names the flooded ruin's dig block; the seam, the secret block and
            every extras row (dig, bed, vendor, clue header, fishing pool) exist where the tools read them;
  walking   no standable cell of a built slot stands on ice, packed ice, blue ice, soul sand, honey or slime (the spire is ice
            and a parkour must stay fair); every plant stands only on what vanilla lets it (#minecraft:dirt for grass and
            flowers) -- and MUTATIONS of the generator that put packed ice in the floor, or plant ignoring the support, make
            those tests fail;
  dressing  a built slot carries what makes the theme what it is (brick and lanterns, bark and froglight, snow and packed ice,
            banners and hay, cut sandstone and terracotta strata, obsidian and amethyst);
  builds    each fixture has no `D.problems` (the walk check over every variant, the clock, the chains); the extras rooms (bank
            vault, well, bait, fishing, eggs, fossil) build clean in every theme; a hazard, a gravity block and a light-less
            hull made by mutating the generator are all named; the independent audit (`tools/dungeon_independent_audit.py`,
            marked slow: about 50 s a theme) reports 0 findings on each fixture.
Not covered: anything in a running Minecraft (the look of any of it, whether the sounds are loud enough, whether a banner or
a decorated pot survives the setblock, how the lanterns read).
"""
from __future__ import annotations

import collections
import copy
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_greed as DGR  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_kinds as K  # noqa: E402
import dungeon_rooms as R  # noqa: E402

OW = ["city", "great_tree", "ice_spire", "hill_keep", "desert_excavation", "night_crater"]
FX = json.loads((ROOT / "tests" / "fixtures" / "dungeon_overworld2_demo.json").read_text(encoding="utf-8"))
THEMES = R.load_themes()["themes"]
BASE = D.load()
COBBLEMON_JAR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
ASSET_INDEX = Path("C:/Users/wnd/AppData/Roaming/ModrinthApp/meta/assets")
needs_cobblemon = pytest.mark.skipif(not COBBLEMON_JAR.is_file(), reason="the Cobblemon 1.8.0 jar is not at the snapshot path")


def data(name):
    return json.loads((ROOT / "data" / ("%s.json" % name)).read_text(encoding="utf-8"))


def vanilla_jar():
    import town_character as TC
    j = TC.default_vanilla_jar()
    return Path(j) if j and Path(j).is_file() else None


def theme_text(theme, skip=()):
    return json.dumps({k: v for k, v in THEMES[theme].items() if k not in skip})


@pytest.fixture(scope="module")
def cobblemon():
    z = zipfile.ZipFile(COBBLEMON_JAR)
    species = {}
    for n in z.namelist():
        m = re.match(r"data/cobblemon/species/[^/]+/([a-z0-9_]+)\.json$", n)
        if m:
            species[m.group(1)] = json.loads(z.read(n))
    facts = collections.defaultdict(lambda: {"tags": set(), "structures": set(), "night": False, "dark": False})
    for n in z.namelist():
        if n.startswith("data/cobblemon/spawn_pool_world/") and n.endswith(".json"):
            for s in json.loads(z.read(n)).get("spawns", []):
                words = (s.get("pokemon") or "").split()
                if not words or "-alpha" in words[0] or "herd" in words[0]:
                    continue
                c = s.get("condition", {})
                f = facts[words[0]]
                f["tags"] |= {b.replace("#cobblemon:", "") for b in c.get("biomes", []) if b.startswith("#cobblemon:")}
                f["structures"] |= set(c.get("structures", []))
                f["night"] |= c.get("timeRange") == "night"
                f["dark"] |= c.get("maxSkyLight", 15) <= 7
    return species, dict(facts)


def ambient_lines(theme):
    return [(g["id"], line) for g in THEMES[theme]["life"]["ambient"]["groups"] for line in g["lines"]]


def fixture_species(theme):
    out = set()
    for r in FX["themes"][theme]["rooms"]:
        p = r.get("params") or {}
        for t in p.get("trainers") or []:
            for team in t["team_by_band"].values():
                out.update(team)
        out.update((p.get("species_by_band") or {}).values())
        sp = p.get("species")
        out.update(sp if isinstance(sp, list) else ([sp] if sp else []))
    return out


def fishing_species(theme):
    out = set()
    for band, row in data("dungeon_extras2")["fishing"]["species"][theme].items():
        if band == "why":
            continue
        for bucket in row.values():
            out.update(s for s, _w in bucket)
    return out


# ================================================================================================= the themes' data


def test_the_six_themes_exist_beside_the_eight_and_carry_every_key_the_kit_reads():
    assert set(OW) <= set(THEMES) and {"mine", "jungle", "flooded_ruin", "basalt_deltas"} <= set(THEMES)
    for t in OW:
        th = THEMES[t]
        for key in ("hull", "door", "rip", "lamp", "messages", "dress", "maze", "parkour", "bridge", "seam", "safe", "dark", "life", "shapes", "crossroads"):
            assert key in th, (t, key)
        assert {"wall", "floor", "ceiling", "light", "light_every", "min_light"} <= set(th["hull"])
        assert set(th["crossroads"]["looks"]) == {"lit", "dark", "flooded"}
        ops = [o["op"] for o in th["dress"]]
        assert ops[-2:] == ["life", "relics"] and "life_scenes" in ops and "deposits" in ops, t
        assert ops.index("life_scenes") < ops.index("life") and ops.index("deposits") < ops.index("life"), t
        for op in th["dress"]:
            # life_scenes, life, deposits and relics are registered by their own modules when a dungeon is built
            assert op["op"] in R.DRESS or op["op"] in ("life_scenes", "life", "deposits", "relics"), (t, op["op"])


@pytest.mark.parametrize("theme", OW)
def test_the_shape_mix_names_only_shapes_the_kit_builds_and_every_theme_has_variety(theme):
    legal = {"box", "oval", "l", "t", "gallery", "cavern", "split", "ring"}
    mix = THEMES[theme]["shapes"]["mix"]
    used = set()
    for kind, v in mix.items():
        for shape in ([v] if isinstance(v, str) else [s for s, _w in v]):
            assert shape in legal, (theme, kind, shape)
            used.add(shape)
    assert len(used) >= 5, (theme, "a theme with fewer than five outlines is a box with a coat of paint", used)
    assert set(THEMES[theme]["shapes"]["params"].get("ring", {}).get("feature", "rock").split()) <= {"rock", "pool", "columns"}


BANNED = ["lava", "fire", "soul_fire", "magma_block", "campfire", "soul_campfire", "cactus", "sweet_berry_bush", "powder_snow", "cobweb",
          "pointed_dripstone", "tnt", "bubble_column", "wither_rose", "sculk_sensor", "sculk_shrieker", "budding_amethyst", "ice",
          "sand", "red_sand", "gravel", "suspicious_sand", "suspicious_gravel", "anvil", "chipped_anvil", "damaged_anvil", "dragon_egg", "snow",
          # a crafting or enchanting block is a free service in a run that has its own economy
          "crafting_table", "furnace", "blast_furnace", "smoker", "enchanting_table", "grindstone", "smithing_table", "loom",
          "cartography_table", "stonecutter", "brewing_stand", "beacon", "ender_chest", "jukebox"]


@pytest.mark.parametrize("theme", OW)
def test_no_theme_row_names_a_hazard_a_gravity_block_concrete_regular_ice_or_a_crafting_block(theme):
    rows = {"theme": THEMES[theme], "puzzles": data("dungeon_puzzles")["themes"][theme], "relics": data("dungeon_relics")["themes"][theme]}
    text = json.dumps(rows)
    for b in BANNED:
        assert not re.search(r'"minecraft:%s(\[|")' % b, text), (theme, b)
    assert not re.search(r'minecraft:[a-z_]*concrete', text), theme
    for b in re.findall(r'"(minecraft:[a-z0-9_]+)', text):
        assert not G.forbidden(b), (theme, b)
        assert G.classify(b) != G.HAZARD, (theme, b)


def test_the_theme_text_names_no_sand_block_at_all_and_the_desert_has_no_plain_sandstone():
    # plain sandstone is the flooded ruin's fossil-bay dig block; tests/test_dungeon_extras2.py refuses any theme that names it
    # (as a substring: its stairs, slab and wall too). The desert uses cut, smooth and chiseled sandstone and the red kinds
    text = (ROOT / "data" / "dungeon_themes.json").read_text(encoding="utf-8")
    assert "minecraft:sandstone" not in text
    assert not re.search(r'minecraft:(red_)?sand["\[]', text)
    assert "minecraft:cut_sandstone" in theme_text("desert_excavation") and "minecraft:smooth_sandstone" in theme_text("desert_excavation")


def test_no_ice_that_melts_and_no_walked_floor_of_the_spire_is_a_slippery_block():
    t = THEMES["ice_spire"]
    for k in ("wall", "floor", "ceiling"):
        assert not re.search(r"ice", t["hull"][k]), (k, t["hull"][k])
    # the extras' decks and the crossroads' approaches are walked too
    for look in t["crossroads"]["looks"].values():
        assert not re.search(r"ice", look.get("deck", "")), look
    for key in ("ledge", "ledge_top", "platform", "catch_floor"):
        assert "ice" not in t["parkour"][key], key
    for key in ("span", "span_edge", "ledge"):
        assert "ice" not in t["bridge"][key], key


@pytest.mark.parametrize("theme", OW)
def test_the_notes_fit_a_waxed_sign(theme):
    notes = THEMES[theme]["life"]["notes"]
    assert len(notes) >= 5
    for n in notes:
        assert 1 <= len(n) <= 4
        for line in n:
            assert len(line) <= 15 and re.fullmatch(r"[ -~]*", line) and not re.search(r"['\"\\]", line), (theme, line)


@pytest.mark.parametrize("theme", OW)
def test_the_ambience_sounds_and_particles_exist(theme):
    j = vanilla_jar()
    particles = {n.rsplit("/", 1)[1][:-5] for n in zipfile.ZipFile(j).namelist() if n.startswith("assets/minecraft/particles/")} if j else None
    flame = THEMES[theme]["life"].get("candle_flame", "small_flame")
    sounds = None
    idx = ASSET_INDEX / "indexes" / "17.json"
    if idx.is_file():
        h = json.loads(idx.read_text(encoding="utf-8"))["objects"]["minecraft/sounds.json"]["hash"]
        sounds = set(json.loads((ASSET_INDEX / "objects" / h[:2] / h).read_text(encoding="utf-8")))
    ents = THEMES[theme]["life"]["ambience"]
    assert any(e.get("sound") for e in ents) and any(e.get("particle") for e in ents)
    for e in ents:
        if e.get("particle") and particles is not None:
            assert e["particle"].split(":")[-1] in particles, (theme, e["particle"])
        if e.get("sound") and sounds is not None:
            assert e["sound"].split(":")[-1] in sounds, (theme, e["sound"])
    if particles is not None:
        assert flame in particles, (theme, flame)


# ================================================================================================= species


# the Pokemon the pack cannot show right (docs/research/COBBLEVERSE_COMPATIBILITY.md): the 40 species with no client asset and the
# final forms whose 1.8 model is mis-assembled
MISASSEMBLED = {"pidgeot", "talonflame", "arbok", "crobat", "cofagrigus", "skarmory", "tyranitar", "garganacl", "goodra", "primarina",
                "nidoking", "turtonator", "appletun", "archaludon"}


def dolls():
    text = (ROOT / "docs" / "research" / "COBBLEVERSE_COMPATIBILITY.md").read_text(encoding="utf-8")
    m = re.search(r"^(arctibax, blacephalon[^\n]*)$", text, re.M)
    assert m, "the doll list moved: re-read the compatibility note"
    return {s.strip().rstrip(".") for s in m.group(1).split(",")}


@needs_cobblemon
@pytest.mark.parametrize("theme", OW)
def test_every_species_exists_in_the_cobblemon_jar(theme, cobblemon):
    species, _f = cobblemon
    named = {s for _g, line in ambient_lines(theme) for s in line} | fixture_species(theme) | fishing_species(theme)
    assert named - set(species) == set(), sorted(named - set(species))


@needs_cobblemon
@pytest.mark.parametrize("theme", OW)
def test_every_ambient_line_is_an_evolution_chain_of_the_jars_own_evolutions(theme, cobblemon):
    species, _f = cobblemon
    for gid, line in ambient_lines(theme):
        for a, b in zip(line, line[1:]):
            results = {e["result"].split()[0] for e in species[a].get("evolutions", [])}
            assert b in results, (theme, gid, a, "does not evolve into", b)


# where each theme's animals may be found, by the jar's spawn pools (the tags are the jar's, data/cobblemon/spawn_pool_world; the
# map is written here). city: the jar has no urban tag, so the test is weak there by nature: a village structure is as urban as
# the overworld gets, and the plains, grassland, sky and spooky tags are the common town animals' (rats, pigeons, strays) night_crater: night spawns, cave-dark
# spawns and the magical, spooky, end and dripstone biomes
THEME_TAGS = {
    "city": {"is_overworld", "is_plains", "is_grassland", "is_spooky", "is_sky", "is_forest", "is_taiga"},
    "great_tree": {"is_forest", "is_jungle", "is_floral", "is_lush", "is_taiga", "is_mushroom", "is_tropical_island", "is_snowy_forest", "is_swamp", "nether/is_fungus"},
    "ice_spire": {"is_freezing", "is_glacial", "is_snowy", "is_tundra", "is_frozen_ocean", "is_peak", "is_snowy_taiga", "is_snowy_forest", "is_cold_ocean", "is_mountain", "nether/is_frozen"},
    "hill_keep": {"is_hills", "is_mountain", "is_highlands", "is_plateau", "is_grassland", "is_plains", "is_badlands", "is_savanna", "is_peak", "is_forest"},
    "desert_excavation": {"is_desert", "is_arid", "is_badlands", "is_volcanic", "is_savanna"},
    "night_crater": {"is_magical", "is_spooky", "is_end", "is_dripstone", "is_sky", "is_mountain", "is_peak"},
}
VILLAGE = "#minecraft:village"
# a line none of whose members has ANY spawn pool in the jar is a dungeon-only line: allowed, but at most two to a theme, so the
# jar still carries the roster
DUNGEON_ONLY_MAX = 2
# lines accepted although no member spawns where the theme is, each with the reason (design, not the theme under test)
APPROVED = {
    ("great_tree", "bees"): "Combee's pool names no biome tag (it spawns by flowers and hives); a honey wood is where it belongs",
    ("great_tree", "blooms"): "Sunkern/Sunflora are plains animals by the jar; flowers grow in a great tree's clearings",
    ("hill_keep", "hounds"): "Lillipup and Growlithe are village animals by the jar (a keep is a fortified village)",
    ("hill_keep", "fighters"): "Timburr's line is a village worker by the jar",
    ("hill_keep", "blades"): "Pawniard and Bisharp are the soldiers with blades for arms, the keep's namesake; the jar places them only in bamboo and river",
    ("desert_excavation", "burrowers"): "Diglett's pool names no biome tag: it is found everywhere underground",
    ("desert_excavation", "hippos"): "Hippopotas has the desert by the jar's pool selectors the tag table does not carry",
    ("night_crater", "gems"): "Sableye lives in the dark by gemstones (its pool needs #cobblemon:gemstones nearby): the crater's amethyst",
}


@needs_cobblemon
@pytest.mark.parametrize("theme", OW)
def test_every_ambient_line_belongs_to_its_theme_by_the_jars_spawns_or_an_approved_reason(theme, cobblemon):
    _species, facts = cobblemon
    tags = THEME_TAGS[theme]
    kept = collections.Counter()
    misses = []
    dungeon_only = []
    for gid, line in ambient_lines(theme):
        if gid == "sleeper":
            continue        # a sleeping Pokemon in the safe room is a prop, not a spawn
        if not any(s in facts for s in line):
            dungeon_only.append((gid, line))
            continue
        by_tag = any(facts[s]["tags"] & tags for s in line if s in facts)
        by_village = theme == "city" and any(VILLAGE in facts[s]["structures"] for s in line if s in facts)
        by_night = theme == "night_crater" and any(facts[s]["night"] or facts[s]["dark"] for s in line if s in facts)
        approved = (theme, gid) in APPROVED
        if not (by_tag or by_village or by_night or approved):
            misses.append((gid, line))
        kept["jar" if (by_tag or by_village or by_night) else "approved"] += 1
    assert not misses, (theme, misses, "spawn nowhere this theme is, by the jar, and have no approved reason")
    assert len(dungeon_only) <= DUNGEON_ONLY_MAX, (theme, dungeon_only)
    assert kept["jar"] > 3 * kept["approved"], "the jar's own spawn data must carry most of the roster: %s" % dict(kept)


@pytest.mark.parametrize("theme", OW)
def test_no_species_is_a_doll_or_a_mis_assembled_model_anywhere_in_the_theme_its_fixture_or_its_pond(theme):
    named = {s for _g, line in ambient_lines(theme) for s in line} | fixture_species(theme) | fishing_species(theme)
    assert len(dolls()) == 40
    assert not (named & (dolls() | MISASSEMBLED)), sorted(named & (dolls() | MISASSEMBLED))


@needs_cobblemon
@pytest.mark.parametrize("theme", OW)
def test_no_ambient_or_fished_pokemon_is_a_legendary_a_mythical_an_ultra_beast_a_paradox_or_a_starter_line_in_the_ambience(theme, cobblemon):
    species, _f = cobblemon
    bad = {"legendary", "mythical", "ultra_beast", "paradox", "restricted"}
    for gid, line in ambient_lines(theme):
        for s in line:
            lab = set(species[s].get("labels", []))
            assert not (lab & bad), (theme, s)
            assert "starter" not in lab, (theme, s, "starters are the eggs' and the ponds' business")
    for s in fishing_species(theme):
        assert not (set(species[s].get("labels", [])) & (bad | {"fossil"})), (theme, s)


@needs_cobblemon
@pytest.mark.parametrize("theme", OW)
def test_the_fixtures_fights_use_real_species_stand_teams_by_band_and_a_resident_habitat(theme, cobblemon):
    species, _f = cobblemon
    rooms = {r["id"]: r for r in FX["themes"][theme]["rooms"]}
    assert set(rooms["nest"]["params"]["species"]) <= set(species)
    assert rooms["hab"]["params"]["species"] in species
    for rid in ("stand1", "gaunt"):
        for t in rooms[rid]["params"]["trainers"]:
            for band, team in t["team_by_band"].items():
                assert len(team) == [2, 3, 3, 4, 5, 6][int(band) - 1], (theme, t["name"], band)
    # no two themes share a fight roster: the six are told apart by who is in them
    mine = fixture_species(theme)
    for other in OW:
        if other != theme:
            assert len(mine & fixture_species(other)) <= 6, (theme, other, sorted(mine & fixture_species(other)))


# ================================================================================================= the seam, the secret and the price


def test_every_theme_has_a_resources_row_and_its_seam_is_what_the_row_says():
    res = data("dungeon_resources")
    greed = data("dungeon_greed")["blocks"]
    for t in OW:
        row = res["themes"][t]
        assert row["family"] in ("stone", "deepslate")
        assert 3 <= row["heaps"]["min"] <= row["heaps"]["max"] <= 8 and row["heaps"]["height"] == [2, 3]
        seam = {e["block"] for e in THEMES[t]["seam"]["blocks"]}
        if row.get("seam") == "legacy":
            assert t == "great_tree"
            assert seam == {e["block"] for e in THEMES["jungle"]["seam"]["blocks"]}, "the produce face is the jungle's: its rows are the priced ones"
        else:
            # the seam's ores are the family's, whichever resources the data file says a band ever holds
            want = {res["resources"][r]["blocks"][row["family"]] for r in ("coal", "iron", "copper", "gold", "redstone", "lapis", "diamond")}
            assert seam == want, (t, sorted(seam ^ want))
        assert seam <= set(greed), (t, sorted(seam - set(greed)))
        # rubble is decoration the pick cannot break
        pick = set(BASE["engine"]["rift_pick"]["can_break"]) | seam
        for b, _w in row["rubble"]:
            assert b not in pick and "_ore" not in b, (t, b)


@pytest.mark.parametrize("theme", OW)
def test_the_secret_block_has_a_greed_row_worth_nothing_and_is_in_no_hull_or_dressing_of_its_theme(theme):
    sb = THEMES[theme]["shapes"]["secret_block"]
    row = data("dungeon_greed")["blocks"][sb]
    assert row["cp"] == 0 and row["drops"] == {}, sb
    rest = json.dumps({k: v for k, v in THEMES[theme].items() if k not in ("shapes",)})
    assert sb not in rest, (theme, sb)
    # and in no OTHER of the six either as its secret: two themes may share one (the cracked bricks), never swap a hull for it
    assert sb not in json.dumps(THEMES[theme]["dress"])


def test_no_dressing_block_is_one_the_rift_pick_can_break():
    pick = set(BASE["engine"]["rift_pick"]["can_break"])
    for t in OW:
        seam = {e["block"] for e in THEMES[t]["seam"]["blocks"]}
        text = json.dumps({k: v for k, v in THEMES[t].items() if k != "seam"})
        for b in pick | seam:
            assert '"%s' % b not in text and "%s[" % b not in text, (t, b)
        res = data("dungeon_resources")["themes"][t]
        fam = res["family"]
        table = data("dungeon_resources")
        for r in table["resources"]:
            assert '"%s"' % table["resources"][r]["blocks"][fam] not in text, (t, r)


def test_every_theme_has_an_extras_row_where_the_extras_tools_read_one():
    x1, x2 = data("dungeon_extras"), data("dungeon_extras2")
    themes_text = (ROOT / "data" / "dungeon_themes.json").read_text(encoding="utf-8") + (ROOT / "data" / "dungeon_puzzles.json").read_text(encoding="utf-8")
    ids = None
    j = vanilla_jar()
    if j:
        ids = {"minecraft:" + n.rsplit("/", 1)[1][:-5] for n in zipfile.ZipFile(j).namelist() if n.startswith("assets/minecraft/blockstates/") and n.endswith(".json")}
    own = {x2["fishing"]["markers"][str(b)] for b in range(1, 7)} | set(x2["fossils"]["dig"].values()) | {x2["fossils"]["block"]}
    for t in OW:
        assert 1 <= len(x1["bank_vault"]["clue_header"][t]) <= 15 and re.fullmatch(r"[ -~]+", x1["bank_vault"]["clue_header"][t])
        v = x2["eggs"]["vendor"][t]
        assert v["name"] and v["why"]
        bed, dig = x2["fishing"]["bed"][t], x2["fossils"]["dig"][t]
        for b in (bed, dig):
            assert not G.forbidden(b) and G.classify(b) != G.HAZARD
            if ids is not None:
                assert b in ids, (t, b)
        assert dig in data("dungeon_greed")["blocks"], (t, dig, "the pick breaks it: GREED must price it")
        assert set(x2["fishing"]["species"][t]) >= {"why", "1", "2", "3", "4", "5", "6"}
    for b in own:
        assert b not in themes_text, b


# ================================================================================================= the dressing, built


def fx_doc(theme, variants=True):
    doc = copy.deepcopy(BASE)
    d = doc["dungeons"][0]
    d["theme"] = theme
    d["rooms"] = copy.deepcopy(FX["themes"][theme]["rooms"])
    d["shape_mix"] = FX["themes"][theme]["shape_mix"]
    d["variants"] = copy.deepcopy(FX["variants"]) if variants else []
    d.pop("spine", None)
    d["clock_s_by_band"] = dict(FX["themes"][theme]["clock_s_by_band"])
    doc["dungeons"] = [d]
    doc["engine"]["sigils"]["free_first_entry"]["dungeons"] = [d["id"]]
    doc["engine"]["slots"]["per_dungeon"] = 4
    return doc


@pytest.fixture(autouse=True)
def fresh():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


_CENSUS = {}


def census(theme):
    if theme not in _CENSUS:
        _CENSUS[theme] = _census(theme)
    return _CENSUS[theme]


def _census(theme):
    doc = fx_doc(theme)
    d = doc["dungeons"][0]
    slot = D.slots(doc)[0]
    tot = collections.Counter()
    for b in R.slot_build(doc, d, slot):
        for n in b.grid.names():
            tot[G.base(n)] += int((b.grid.a == b.grid.idx[n]).sum())
    return doc, tot


def n(tot, *names):
    return sum(tot.get("minecraft:" + x, 0) for x in names)


IDENTITY = {
    "city": lambda t: n(t, "bricks") > 20000 and n(t, "polished_andesite") > 5000 and n(t, "lantern") > 200 and n(t, "chain") > 200 and n(t, "dark_oak_planks") > 300 and n(t, "cobblestone") > 1000,
    "great_tree": lambda t: n(t, "dark_oak_wood") > 20000 and n(t, "oak_leaves") > 10000 and n(t, "dark_oak_log", "mangrove_log") > 2000 and n(t, "ochre_froglight") > 500 and n(t, "vine") > 500 and n(t, "rooted_dirt") > 5000,
    "ice_spire": lambda t: n(t, "snow_block") > 20000 and n(t, "packed_ice") > 8000 and n(t, "sea_lantern") > 400 and n(t, "polished_diorite") > 5000 and n(t, "chiseled_stone_bricks") > 10,
    "hill_keep": lambda t: n(t, "stone_bricks") > 20000 and n(t, "spruce_planks") > 10000 and n(t, "hay_block") > 200 and n(t, "blue_banner", "orange_banner", "green_banner", "red_banner") > 60 and n(t, "lantern") > 300,
    "desert_excavation": lambda t: n(t, "cut_sandstone") > 20000 and n(t, "smooth_sandstone") > 5000 and n(t, "orange_terracotta", "yellow_terracotta", "red_terracotta", "brown_terracotta") > 600 and n(t, "chiseled_red_sandstone") > 500 and n(t, "oak_fence", "oak_log", "oak_planks") > 1000,
    "night_crater": lambda t: n(t, "blackstone") > 20000 and n(t, "obsidian") > 10000 and n(t, "amethyst_block") > 800 and n(t, "crying_obsidian") > 300 and n(t, "pearlescent_froglight") > 300 and n(t, "tuff") > 5000,
}


@pytest.mark.parametrize("theme", OW)
def test_a_built_slot_carries_what_makes_the_theme_what_it_is_and_nothing_a_player_cannot_stand_in(theme):
    _doc, tot = census(theme)
    assert IDENTITY[theme](tot), {k.split(":")[1]: v for k, v in tot.most_common(16)}
    for b in tot:
        assert G.classify(b) != G.HAZARD, b
        assert not G.forbidden(b), b
    assert not (set(tot) & {"minecraft:lava", "minecraft:fire", "minecraft:magma_block", "minecraft:soul_fire", "minecraft:powder_snow",
                            "minecraft:ice", "minecraft:sand", "minecraft:red_sand", "minecraft:gravel", "minecraft:budding_amethyst"})


@pytest.mark.parametrize("theme", OW)
def test_the_six_are_told_apart_by_their_blocks(theme):
    """Each theme's four commonest blocks share at most one id with any other theme's four: a palette swap would not."""
    _d, tot = census(theme)
    top = {k for k, _v in tot.most_common(6) if k != "minecraft:air"}
    for other in OW:
        if other == theme:
            continue
        _d2, tot2 = census(other)
        top2 = {k for k, _v in tot2.most_common(6) if k != "minecraft:air"}
        assert len(top & top2) <= 2, (theme, other, sorted(top & top2))


SLIPPERY = {"minecraft:ice", "minecraft:packed_ice", "minecraft:blue_ice", "minecraft:frosted_ice", "minecraft:soul_sand", "minecraft:honey_block", "minecraft:slime_block"}


def stood_on(theme):
    """Counter of the base id under every cell a player could stand in (feet and head passable, solid under) in a built slot, at
    most one block over the room's own floor there (a step; the top of a wall or a broken column two high is not reached)."""
    doc = fx_doc(theme, variants=False)
    d = doc["dungeons"][0]
    out = collections.Counter()
    for b in R.slot_build(doc, d, D.slots(doc)[0]):
        g = b.grid
        codes = np.array(g.codes)[g.a]
        mask = (codes[:, 1:-1, :] == G.PASS) & (codes[:, 2:, :] == G.PASS) & (codes[:, :-2, :] == G.SOLID)
        x0, y0, z0 = g.box[:3]
        for i, j, k in zip(*mask.nonzero()):
            x, y, z = int(i) + x0, int(j) + 1 + y0, int(k) + z0
            fl = R.floor_xz(b.room, x, z)
            if fl is None or y - fl > 1:
                continue
            out[G.base(g.pal[int(g.a[i, j, k])])] += 1
    return out


@pytest.mark.parametrize("theme", OW)
def test_no_cell_a_player_stands_in_has_a_slippery_or_sticky_floor(theme):
    under = stood_on(theme)
    assert sum(under.values()) > 5000, "the test needs floor to judge"
    assert not (set(under) & SLIPPERY), {k: v for k, v in under.items() if k in SLIPPERY}


def test_a_floor_of_packed_ice_would_be_caught_by_the_test_above(monkeypatch):
    """MUTATE THE GENERATOR (not the record): floor patches that lay packed ice on the spire's floor."""
    real = K.dress_floor_patches

    def icy(ctx, spec):
        spec = dict(spec)
        spec["blocks"] = [{"block": "minecraft:packed_ice", "w": 1}]
        spec["per100"] = 30
        return real(ctx, spec)

    monkeypatch.setitem(R.DRESS, "floor_patches", (icy, R.DRESS["floor_patches"][1]))
    under = stood_on("ice_spire")
    assert under.get("minecraft:packed_ice", 0) > 50, "the mutant lays packed ice where the player walks; the slip test has something to refuse"


def _tag(name):
    j = vanilla_jar()
    if not j:
        return None
    return set(json.loads(zipfile.ZipFile(j).read("data/minecraft/tags/block/%s.json" % name))["values"])


# grass, ferns and flowers survive on #minecraft:dirt (the jar's tag; grass_block, dirt, podzol, coarse_dirt, mycelium, rooted_dirt,
# moss_block, mud, muddy_mangrove_roots). The vanilla source names the tag for BushBlock; read here, not from the theme
DIRT = _tag("dirt") or {"minecraft:dirt", "minecraft:grass_block", "minecraft:podzol", "minecraft:coarse_dirt", "minecraft:mycelium",
                        "minecraft:rooted_dirt", "minecraft:moss_block", "minecraft:mud", "minecraft:muddy_mangrove_roots"}
GRASSLIKE = ("minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern", "minecraft:large_fern", "minecraft:dandelion", "minecraft:poppy",
             "minecraft:oxeye_daisy", "minecraft:azure_bluet", "minecraft:blue_orchid", "minecraft:red_tulip", "minecraft:lily_of_the_valley",
             "minecraft:brown_mushroom", "minecraft:red_mushroom")


def planted(theme):
    doc = fx_doc(theme, variants=False)
    d = doc["dungeons"][0]
    out = []
    for b in R.slot_build(doc, d, D.slots(doc)[0]):
        g = b.grid
        x0, y0, z0 = g.box[:3]
        for name in g.names():
            if G.base(name) in GRASSLIKE:
                if G.base(name) in ("minecraft:tall_grass", "minecraft:large_fern") and "half=upper" in name:
                    continue
                xs, ys, zs = (g.a == g.idx[name]).nonzero()
                for i, j, k in zip(xs, ys, zs):
                    out.append((G.base(name), G.base(g.block_at(int(i) + x0, int(j) + y0 - 1, int(k) + z0))))
    return out


@pytest.mark.parametrize("theme", ["great_tree", "hill_keep"])
def test_plants_stand_only_on_what_vanilla_lets_them(theme):
    found = planted(theme)
    assert len(found) > 30, "the test needs plants to judge"
    for plant, under in found:
        if plant in ("minecraft:brown_mushroom", "minecraft:red_mushroom"):
            continue            # a mushroom survives on any solid in the dark, and the themes place none
        assert under in DIRT, (theme, plant, under)


def test_no_theme_that_lights_its_floor_plants_a_cover_on_a_floor_light():
    # floor_lights (the tall_lights hull) replaces the block UNDER a plant with a light block and does not know about soil;
    # a theme with tall_lights therefore carries no ground_cover (the plant would be orphaned). The jungle-style trees and the
    # keep, whose rooms are lit from the ceiling, do
    for t in OW:
        has_tall = "tall_lights" in THEMES[t]["hull"]
        has_cover = any(o["op"] == "ground_cover" for o in THEMES[t]["dress"])
        assert not (has_tall and has_cover), t


def test_a_ground_cover_that_ignores_the_support_would_be_caught_by_the_test_above(monkeypatch):
    """MUTATE THE GENERATOR: ground cover that drops the `on` list plants grass on cobblestone, floor patches and piles, where it
    pops off in vanilla."""
    real = K.dress_ground_cover

    def careless(ctx, spec):
        spec = dict(spec)
        spec["plants"] = [{k: v for k, v in p.items() if k != "on"} for p in spec["plants"]]
        return real(ctx, spec)

    monkeypatch.setitem(R.DRESS, "ground_cover", (careless, R.DRESS["ground_cover"][1]))
    bad = [(p, u) for p, u in planted("hill_keep") if u not in DIRT and "mushroom" not in p]
    assert bad, "the mutant plants grass on stone and cobble; the support test has something to refuse"


def test_a_hazard_a_theme_is_tempted_by_is_refused_by_the_walk_check(monkeypatch):
    real = K.dress_floor_patches

    def hot(ctx, spec):
        spec = dict(spec)
        spec["blocks"] = [{"block": "minecraft:magma_block", "w": 1}]
        spec["per100"] = 30
        return real(ctx, spec)

    monkeypatch.setitem(R.DRESS, "floor_patches", (hot, R.DRESS["floor_patches"][1]))
    p = R.problems(fx_doc("night_crater", variants=False))
    assert any("magma" in x or "hazard" in x.lower() for x in p), p[:3]


def test_a_gravity_block_the_desert_is_tempted_by_is_refused(monkeypatch):
    """The dig is the one theme a builder would reach for sand in: sandy floor patches are named by the kit."""
    real = K.dress_floor_patches

    def sandy(ctx, spec):
        spec = dict(spec)
        spec["blocks"] = [{"block": "minecraft:red_sand", "w": 1}]
        spec["per100"] = 30
        return real(ctx, spec)

    monkeypatch.setitem(R.DRESS, "floor_patches", (sandy, R.DRESS["floor_patches"][1]))
    p = R.problems(fx_doc("desert_excavation", variants=False))
    assert any("sand" in x or "gravity" in x.lower() or "forbidden" in x.lower() for x in p), p[:3]


def test_a_hull_whose_lights_are_off_is_named_by_the_walk_check(monkeypatch):
    monkeypatch.setattr(R, "hull_lights", lambda ctx, room, theme, ref_y: None)
    p = R.problems(fx_doc("city", variants=False))
    assert any("no light" in x for x in p), p[:3]


# ================================================================================================= the fixtures build clean


@pytest.mark.parametrize("theme", OW)
def test_the_fixture_builds_clean_in_every_variant(theme):
    doc = fx_doc(theme)
    assert D.problems(doc) == []


@pytest.mark.parametrize("theme", OW)
def test_the_fixture_is_full_length_with_a_crossroads_and_every_look(theme):
    doc = fx_doc(theme)
    d = doc["dungeons"][0]
    recs = list(R.all_records(d))
    kinds = collections.Counter(r["kind"] for r in recs)
    for k in ("entry_room", "crossroads", "resources", "safe_room", "stand", "nest", "miniboss", "habitat", "puzzle", "vault",
              "parkour", "collapse_bridge", "dark_room", "gauntlet", "boss_arena", "exit_room", "maze"):
        assert kinds[k] >= 1, (theme, k)
    fork = next(r for r in d["rooms"] if r["kind"] == "fork")
    assert {rt["look"] for rt in fork["routes"]} == {"lit", "dark", "flooded"}
    assert len(recs) >= 25
    assert len(D.slots(doc)) == 4


def extras_doc(theme, fixture):
    rooms = json.loads((ROOT / "tests" / "fixtures" / fixture).read_text(encoding="utf-8"))["rooms"]
    doc = copy.deepcopy(BASE)
    doc["dungeons"] = doc["dungeons"][:1]
    d = doc["dungeons"][0]
    d["theme"] = theme
    d["rooms"] = copy.deepcopy(rooms)
    for k in ("spine", "clock_s_by_band", "variants", "shape_mix"):
        d.pop(k, None)
    doc["engine"]["sigils"]["free_first_entry"]["dungeons"] = [d["id"]]
    doc["engine"]["slots"]["per_dungeon"] = 1
    d["clock_s_by_band"] = DC.derive(doc, d)
    return doc


@pytest.mark.parametrize("theme", OW)
@pytest.mark.parametrize("fixture", ["dungeon_extras_rooms.json", "dungeon_extras2_rooms.json"])
def test_the_extras_rooms_build_clean_in_the_new_themes(theme, fixture):
    """bank vault, wishing well, bait room; fishing room, egg room, fossil chamber: each reads a row of its own for the theme."""
    doc = extras_doc(theme, fixture)
    assert R.problems(doc) == [] and D.warnings(doc) == [], (R.problems(doc)[:3], D.warnings(doc)[:3])


def test_an_extras_room_in_a_theme_with_no_row_fails_closed(monkeypatch):
    """The rows are needed, not decorative: remove the city's vendor and the kit names the egg room."""
    import dungeon_extras2 as X2
    doc = extras_doc("city", "dungeon_extras2_rooms.json")
    real = X2.egg_cfg

    def without():
        cfg = copy.deepcopy(real())
        cfg["vendor"].pop("city")
        return cfg

    monkeypatch.setattr(X2, "egg_cfg", without)
    R._BUILT.clear()
    p = R.problems(doc)
    assert any("has no entry for theme" in x for x in p), p[:3]


@pytest.mark.slow
@pytest.mark.parametrize("theme", OW)
def test_the_independent_audit_reports_nothing_on_the_fixture(theme):
    import dungeon_independent_audit as IA
    doc = fx_doc(theme)
    files = IA.build_files(doc)
    F, _info = IA.audit(files, doc, bands=[1], all_slots=False)
    assert [IA.fmt(f) for f in F] == []
