"""The five nether themes (NETHER-THEMES, 2026-10-10): nether_wastes, crimson_forest, warped_forest, soul_sand_valley,
basalt_deltas in data/dungeon_themes.json, and tests/fixtures/dungeon_nether_demo.json, a full-length demo dungeon for each.

What is checked, and against what (the expectation is never read from the theme under test):
  species   every species id of the themes' ambient groups and of the fixture's fights exists in the Cobblemon 1.8.0 jar;
            every ambient line is an evolution chain of the jar's own `evolutions`; every line spawns in the jar's spawn
            pools under the nether biome tags a theme maps to (the mapping is written here, from the jar's
            data/cobblemon/tags/worldgen/biome/nether/*.json: is_wasteland, is_crimson, is_fungus, is_warped, ...);
  blocks    every id is in the 1.21.1 jar (tests/test_dungeon_rooms.py checks that for every theme as well), no hazard, no
            vine, no fire, no magma, no lava; the seam is the nether's quartz and gold ore and never ancient debris (the
            1.21.1 jar's `needs_diamond_tool` tag: the rift pick is an iron pickaxe), and every seam and secret block
            has a GREED row whose cp is its drops;
  dressing  a built slot of each fixture carries what makes the theme what it is (stems and wart for the forests, bone and
            soul torches for the valley, basalt and froglight for the delta, glowstone and nether brick for the wastes);
            ground cover stands only on what vanilla lets it (roots and sprouts on nylium or soul soil, a standing torch
            on a full top face) -- and a MUTATION of the generator that ignores the support makes that test fail;
  builds    each fixture has no `D.problems` (the walk check over every variant, the clock, the chains); the independent
            audit (`tools/dungeon_independent_audit.py`, marked slow: about 95 s a theme) reports 0 findings on it.
Not covered: anything in a running Minecraft (the look of any of it, whether the sounds are loud enough, whether a
nylium floor stays nylium under a trunk, soul sand's drag).
"""
from __future__ import annotations

import collections
import copy
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_greed as DGR  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_kinds as K  # noqa: E402
import dungeon_rooms as R  # noqa: E402

NETHER = ["nether_wastes", "crimson_forest", "warped_forest", "soul_sand_valley", "basalt_deltas"]
FX = json.loads((ROOT / "tests" / "fixtures" / "dungeon_nether_demo.json").read_text(encoding="utf-8"))
THEMES = R.load_themes()["themes"]
BASE = D.load()
COBBLEMON_JAR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
ASSET_INDEX = Path("C:/Users/wnd/AppData/Roaming/ModrinthApp/meta/assets")

# the jar's nether biome tags, per theme: the vanilla biome each tag holds (read from
# data/cobblemon/tags/worldgen/biome/nether/is_*.json): wastes = is_wasteland; crimson = is_crimson, is_fungus; warped =
# is_warped, is_fungus; soul sand valley = is_soul_sand, is_soul_fire, is_desert; basalt deltas = is_basalt, is_mountain
BIOME_TAGS = {
    "nether_wastes": {"is_wasteland"},
    "crimson_forest": {"is_crimson", "is_fungus"},
    "warped_forest": {"is_warped", "is_fungus"},
    "soul_sand_valley": {"is_soul_sand", "is_soul_fire", "is_desert"},
    "basalt_deltas": {"is_basalt", "is_mountain"},
}
GENERIC = "#minecraft:is_nether"


def vanilla_jar():
    import town_character as TC
    j = TC.default_vanilla_jar()
    return Path(j) if j and Path(j).is_file() else None


needs_cobblemon = pytest.mark.skipif(not COBBLEMON_JAR.is_file(), reason="the Cobblemon 1.8.0 jar is not at the snapshot path")


@pytest.fixture(scope="module")
def cobblemon():
    z = zipfile.ZipFile(COBBLEMON_JAR)
    species = {}
    for n in z.namelist():
        m = re.match(r"data/cobblemon/species/[^/]+/([a-z0-9_]+)\.json$", n)
        if m:
            species[m.group(1)] = json.loads(z.read(n))
    pools = collections.defaultdict(set)         # species -> the biome selectors its spawns name
    for n in z.namelist():
        if n.startswith("data/cobblemon/spawn_pool_world/") and n.endswith(".json"):
            for s in json.loads(z.read(n)).get("spawns", []):
                words = (s.get("pokemon") or "").split()
                name = words[0] if words else ""
                if not name or "-alpha" in name or "herd" in name:
                    continue
                for b in s.get("condition", {}).get("biomes", []):
                    pools[name].add(b)
    return species, pools


def ambient_lines(theme):
    out = []
    for g in THEMES[theme]["life"]["ambient"]["groups"]:
        for line in g["lines"]:
            out.append((g["id"], line))
    return out


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


# ================================================================================================= the themes' data


def test_the_five_nether_themes_exist_beside_the_three():
    assert set(NETHER) <= set(THEMES) and {"mine", "jungle", "flooded_ruin"} <= set(THEMES)
    for t in NETHER:
        th = THEMES[t]
        for key in ("hull", "door", "rip", "lamp", "messages", "dress", "maze", "parkour", "bridge", "seam", "safe", "dark", "life", "shapes", "crossroads"):
            assert key in th, (t, key)
        assert set(th["crossroads"]["looks"]) == {"lit", "dark", "flooded"}
        ops = [o["op"] for o in th["dress"]]
        assert ops[-2:] == ["life", "relics"] and "life_scenes" in ops, t
        assert ops.index("life_scenes") < ops.index("life"), t


@pytest.mark.parametrize("theme", NETHER)
def test_the_shape_mix_names_only_shapes_the_kit_builds(theme):
    legal = {"box", "oval", "l", "t", "gallery", "cavern", "split", "ring"}
    mix = THEMES[theme]["shapes"]["mix"]
    for kind, v in mix.items():
        for shape in ([v] if isinstance(v, str) else [s for s, _w in v]):
            assert shape in legal, (theme, kind, shape)
    assert set(THEMES[theme]["shapes"]["params"].get("ring", {}).get("feature", "rock").split()) <= {"rock", "pool", "columns"}


@pytest.mark.parametrize("theme", NETHER)
def test_no_nether_theme_uses_a_hazard_a_vine_fire_lava_or_magma(theme):
    banned = {"minecraft:lava", "minecraft:fire", "minecraft:soul_fire", "minecraft:magma_block", "minecraft:campfire",
              "minecraft:soul_campfire", "minecraft:vine", "minecraft:weeping_vines", "minecraft:twisting_vines",
              "minecraft:cave_vines", "minecraft:bubble_column", "minecraft:wither_rose", "minecraft:tnt"}
    text = json.dumps(THEMES[theme])
    for b in banned:
        assert '"%s' % b not in text, (theme, b)
    # and the kit's own walk check calls none of them walkable-safe either: the table the themes are held to
    assert all(G.classify(b) == G.HAZARD for b in ("minecraft:magma_block", "minecraft:soul_fire", "minecraft:lava", "minecraft:fire"))


def test_the_nethers_trunk_and_canopy_ops_never_ask_the_kit_for_a_vine():
    # the kit's trunks hang vanilla vines (vines_p) and its canopy curtains hang them beside the curtain (curtain_p default 0.03)
    for t in NETHER:
        for op in THEMES[t]["dress"]:
            if op["op"] == "trunks":
                assert op.get("vines_p", 0.5) == 0, (t, op["block"])
            if op["op"] == "canopy":
                assert op.get("curtain_p", 0.03) == 0, t
            assert op["op"] not in ("wall_vines", "glow_vines"), t


@pytest.mark.parametrize("theme", NETHER)
def test_the_notes_fit_a_waxed_sign(theme):
    notes = THEMES[theme]["life"]["notes"]
    assert len(notes) >= 5
    for n in notes:
        assert 1 <= len(n) <= 4
        for line in n:
            assert len(line) <= 15 and re.fullmatch(r"[ -~]*", line) and not re.search(r"['\"\\]", line), (theme, line)


@pytest.mark.parametrize("theme", NETHER)
def test_the_ambience_sounds_and_particles_exist(theme):
    ids = {e.get("sound") or e.get("particle") for e in THEMES[theme]["life"]["ambience"]}
    j = vanilla_jar()
    particles = {n.rsplit("/", 1)[1][:-5] for n in zipfile.ZipFile(j).namelist() if n.startswith("assets/minecraft/particles/")} if j else None
    flame = THEMES[theme]["life"].get("candle_flame", "small_flame")
    sounds = None
    idx = ASSET_INDEX / "indexes" / "17.json"
    if idx.is_file():
        h = json.loads(idx.read_text(encoding="utf-8"))["objects"]["minecraft/sounds.json"]["hash"]
        sounds = set(json.loads((ASSET_INDEX / "objects" / h[:2] / h).read_text(encoding="utf-8")))
    for e in THEMES[theme]["life"]["ambience"]:
        if e.get("particle") and particles is not None:
            assert e["particle"].split(":")[-1] in particles, (theme, e["particle"])
        if e.get("sound") and sounds is not None:
            assert e["sound"].split(":")[-1] in sounds, (theme, e["sound"])
    if particles is not None:
        assert flame in particles, (theme, flame)
    assert ids


# ================================================================================================= species


@needs_cobblemon
@pytest.mark.parametrize("theme", NETHER)
def test_every_species_exists_in_the_cobblemon_jar(theme, cobblemon):
    species, _pools = cobblemon
    named = {s for _g, line in ambient_lines(theme) for s in line} | fixture_species(theme)
    named |= {s for t in THEMES[theme]["life"]["ambient"]["groups"] for line in t["lines"] for s in line}
    assert named - set(species) == set(), sorted(named - set(species))


@needs_cobblemon
@pytest.mark.parametrize("theme", NETHER)
def test_every_ambient_line_is_an_evolution_chain_of_the_jars_own_evolutions(theme, cobblemon):
    species, _pools = cobblemon
    for gid, line in ambient_lines(theme):
        for a, b in zip(line, line[1:]):
            results = {e["result"].split()[0] for e in species[a].get("evolutions", [])}
            assert b in results, (theme, gid, a, "does not evolve into", b)


DESIGN = ROOT / "docs" / "mechanics" / "NETHER_ENCOUNTERS.md"
DESIGN_SECTION = {"nether_wastes": "### 2.1", "crimson_forest": "### 2.2", "warped_forest": "### 2.3", "soul_sand_valley": "### 2.4",
                  "basalt_deltas": "### 2.5"}


def design_names(theme):
    """Every species name in the biome's table of the design draft (docs/mechanics/NETHER_ENCOUNTERS.md section 2, the owner's
    approved biome identities): the family column and the `Spawns as` column, lower-cased words."""
    text = DESIGN.read_text(encoding="utf-8")
    start = text.index(DESIGN_SECTION[theme])
    end = text.index("\n### ", start + 5)
    words = set()
    for row in text[start:end].splitlines():
        if row.startswith("|") and not row.startswith("| Family") and not row.startswith("|---"):
            cells = [c.strip() for c in row.strip("|").split("|")]
            words |= set(re.findall(r"[a-z]+", " ".join(cells[:3]).lower()))
    return words


@needs_cobblemon
@pytest.mark.parametrize("theme", NETHER)
def test_every_ambient_line_belongs_to_its_biome_by_the_jars_spawns_or_the_approved_design(theme, cobblemon):
    """A line stays when a member spawns under the theme's nether biome tags (or #minecraft:is_nether) in the Cobblemon
    1.8.0 jar, or is named in that biome's table of docs/mechanics/NETHER_ENCOUNTERS.md. Both sources are independent of
    the theme."""
    _species, pools = cobblemon
    mine = {"#cobblemon:nether/" + t for t in BIOME_TAGS[theme]} | {GENERIC}
    names = design_names(theme)
    kept_by = collections.Counter()
    for gid, line in ambient_lines(theme):
        if gid == "sleeper":
            continue          # a sleeping Pokemon in the safe room is a prop, not a spawn
        by_jar = any(pools.get(s, set()) & mine for s in line)
        by_design = any(s in names for s in line)
        assert by_jar or by_design, (theme, gid, line, "spawns nowhere in this biome by the jar and is not in the design's table")
        kept_by["jar" if by_jar else "design"] += 1
    assert kept_by["jar"] >= 3, "the jar's own spawn data must carry most of the roster: %s" % dict(kept_by)


# the Pokemon the pack cannot show right: the 40 species with no client asset and the final forms whose 1.8 model is
# mis-assembled (docs/research/COBBLEVERSE_COMPATIBILITY.md, "Every species ... except these 40" and Class A's table)
MISASSEMBLED = {"pidgeot", "talonflame", "arbok", "crobat", "cofagrigus", "skarmory", "tyranitar", "garganacl", "goodra", "primarina",
                "nidoking", "turtonator", "appletun", "archaludon"}


def dolls():
    text = (ROOT / "docs" / "research" / "COBBLEVERSE_COMPATIBILITY.md").read_text(encoding="utf-8")
    m = re.search(r"^(arctibax, blacephalon[^\n]*)$", text, re.M)
    assert m, "the doll list moved: re-read the compatibility note"
    return {s.strip().rstrip(".") for s in m.group(1).split(",")}


@pytest.mark.parametrize("theme", NETHER)
def test_no_species_is_a_doll_or_a_mis_assembled_model_anywhere_in_the_theme_or_its_fixture(theme):
    named = {s for _g, line in ambient_lines(theme) for s in line} | fixture_species(theme)
    assert len(dolls()) == 40
    assert not (named & (dolls() | MISASSEMBLED)), sorted(named & (dolls() | MISASSEMBLED))


@needs_cobblemon
@pytest.mark.parametrize("theme", ["warped_forest", "soul_sand_valley", "basalt_deltas"])
def test_the_fire_rule_no_fire_type_outside_the_wastes_and_the_crimson_forest(theme, cobblemon):
    # NETHER_ENCOUNTERS.md section 2: "no species with Fire as either type is in any table except the nether wastes and the
    # crimson forest". The dungeons follow their themes, but the owner's 'NOT all fire' is kept by these three
    species, _pools = cobblemon
    for gid, line in ambient_lines(theme):
        for s in line:
            assert "fire" not in (species[s].get("primaryType"), species[s].get("secondaryType")), (theme, gid, s)


@needs_cobblemon
@pytest.mark.parametrize("theme", NETHER)
def test_no_ambient_pokemon_is_a_legendary_a_mythical_an_ultra_beast_or_a_starter_line(theme, cobblemon):
    # the ambient animals are catchable (the owner, 2026-10-10) and the rare prizes of a dungeon are chosen per dungeon:
    # the nether's rare spawns are the starters (cyndaquil, tepig, charmander, fuecoco lines) and are kept for those prizes
    species, _pools = cobblemon
    starters = {"cyndaquil", "quilava", "typhlosion", "tepig", "pignite", "emboar", "charmander", "charmeleon", "charizard",
                "fuecoco", "crocalor", "skeledirge", "chimchar", "monferno", "infernape"}
    for gid, line in ambient_lines(theme):
        for s in line:
            assert not (set(species[s].get("labels", [])) & {"legendary", "mythical", "ultra_beast", "paradox"}), (theme, s)
            assert s not in starters, (theme, s)


@needs_cobblemon
@pytest.mark.parametrize("theme", NETHER)
def test_the_fixtures_fights_use_the_themes_species_and_the_habitat_is_a_real_one(theme, cobblemon):
    species, _pools = cobblemon
    rooms = {r["id"]: r for r in FX["themes"][theme]["rooms"]}
    assert set(rooms["nest"]["params"]["species"]) <= set(species)
    assert rooms["hab"]["params"]["species"] in species
    for t in rooms["stand1"]["params"]["trainers"]:
        for band, team in t["team_by_band"].items():
            assert len(team) == [2, 3, 3, 4, 5, 6][int(band) - 1], (theme, t["name"], band)


# ================================================================================================= the seam and its price


@pytest.mark.parametrize("theme", NETHER)
def test_the_seam_is_the_nethers_quartz_and_gold_ore_and_never_ancient_debris(theme):
    blocks = {e["block"] for e in THEMES[theme]["seam"]["blocks"]}
    assert blocks == {"minecraft:nether_quartz_ore", "minecraft:nether_gold_ore"}
    assert all(e["min_band"] == 1 for e in THEMES[theme]["seam"]["blocks"])
    j = vanilla_jar()
    if j:
        tag = json.loads(zipfile.ZipFile(j).read("data/minecraft/tags/block/needs_diamond_tool.json"))["values"]
        assert "minecraft:ancient_debris" in tag, "the reason the seam has no debris: the 1.21.1 jar's own tag"
    assert BASE["engine"]["rift_pick"]["item"] == "minecraft:iron_pickaxe"
    # nothing else of the theme is a block the pick may break, ore or debris
    rest = json.dumps({k: v for k, v in THEMES[theme].items() if k != "seam"})
    for b in ("nether_quartz_ore", "nether_gold_ore", "ancient_debris"):
        assert '"minecraft:%s"' % b not in rest, (theme, b)


def test_every_seam_and_secret_block_of_the_nether_themes_has_a_greed_row_whose_cp_is_its_drops():
    table = DGR.load()
    want = set()
    for t in NETHER:
        want |= {e["block"] for e in THEMES[t]["seam"]["blocks"]}
        want.add(THEMES[t]["shapes"]["secret_block"])
    assert want <= set(table["blocks"]), sorted(want - set(table["blocks"]))
    nug = table["items"]["minecraft:gold_nugget"]["cp"]
    assert table["blocks"]["minecraft:nether_gold_ore"]["drops"] == {"minecraft:gold_nugget": 4}
    assert table["blocks"]["minecraft:nether_gold_ore"]["cp"] == 4 * nug
    for b in ("minecraft:cracked_nether_bricks", "minecraft:cracked_polished_blackstone_bricks"):
        assert table["blocks"][b]["cp"] == 0 and table["blocks"][b]["drops"] == {}


def test_the_nether_gold_ore_row_is_what_the_1_21_1_loot_table_says():
    j = vanilla_jar()
    if not j:
        pytest.skip("no vanilla jar")
    lt = json.loads(zipfile.ZipFile(j).read("data/minecraft/loot_table/blocks/nether_gold_ore.json"))
    text = json.dumps(lt)
    assert '"minecraft:gold_nugget"' in text and '"min": 2.0' in text and '"max": 6.0' in text      # 2-6, mean 4


@pytest.mark.parametrize("theme", NETHER)
def test_the_secret_block_is_in_no_hull_or_dressing_of_its_theme(theme):
    sb = THEMES[theme]["shapes"]["secret_block"]
    rest = json.dumps({k: v for k, v in THEMES[theme].items() if k not in ("shapes",)})
    assert sb not in rest, (theme, sb)


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


def census(theme):
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
    "nether_wastes": lambda t: n(t, "netherrack") > 20000 and n(t, "glowstone") > 150 and n(t, "nether_bricks", "red_nether_bricks") > 500 and n(t, "blackstone") > 300,
    "crimson_forest": lambda t: n(t, "crimson_stem") > 3000 and n(t, "nether_wart_block") > 10000 and n(t, "crimson_roots") > 150 and n(t, "crimson_nylium") > 4000 and n(t, "shroomlight") > 400,
    "warped_forest": lambda t: n(t, "warped_stem") > 3000 and n(t, "warped_wart_block") > 10000 and n(t, "warped_roots") > 150 and n(t, "warped_nylium") > 4000 and n(t, "shroomlight") > 400,
    "soul_sand_valley": lambda t: n(t, "soul_soil") > 20000 and n(t, "bone_block") > 1000 and n(t, "soul_torch") > 80 and n(t, "soul_sand") > 300 and n(t, "soul_lantern") > 5,
    "basalt_deltas": lambda t: n(t, "basalt", "smooth_basalt", "polished_basalt") > 3000 and n(t, "blackstone") > 10000 and n(t, "ochre_froglight") > 150,
}


@pytest.mark.parametrize("theme", NETHER)
def test_a_built_slot_carries_what_makes_the_theme_what_it_is_and_nothing_a_player_cannot_stand_in(theme):
    _doc, tot = census(theme)
    assert IDENTITY[theme](tot), {k.split(":")[1]: v for k, v in tot.most_common(14)}
    for b in tot:
        assert G.classify(b) != G.HAZARD, b
        assert not G.forbidden(b), b
    assert not (set(tot) & {"minecraft:vine", "minecraft:lava", "minecraft:fire", "minecraft:magma_block", "minecraft:soul_fire",
                            "minecraft:weeping_vines", "minecraft:twisting_vines"})


def _tag(name):
    j = vanilla_jar()
    if not j:
        return None
    return set(json.loads(zipfile.ZipFile(j).read("data/minecraft/tags/block/%s.json" % name))["values"])


# a root or a sprout survives on a block of the 1.21.1 jar's #minecraft:nylium tag, on soul soil (RootsBlock and
# NetherSproutsBlock name it in code, not in a tag: read from the vanilla source, not from the jar) and on the dirt tag
SUPPORT_FOR_ROOTS = (_tag("nylium") or {"minecraft:crimson_nylium", "minecraft:warped_nylium"}) | {"minecraft:soul_soil"} | (_tag("dirt") or set())
# a standing torch needs a full top face: a full cube. Not soul sand (14/16 high)
FULL_TOP = {"minecraft:soul_soil", "minecraft:blackstone", "minecraft:netherrack", "minecraft:crimson_nylium", "minecraft:warped_nylium",
            "minecraft:basalt", "minecraft:bone_block", "minecraft:polished_blackstone", "minecraft:polished_blackstone_bricks",
            "minecraft:glowstone", "minecraft:shroomlight", "minecraft:ochre_froglight"}


def planted(theme):
    """(plant, block under it) for every nether plant and torch in every room of a built slot."""
    doc = fx_doc(theme)
    d = doc["dungeons"][0]
    out = []
    for b in R.slot_build(doc, d, D.slots(doc)[0]):
        g = b.grid
        for name in g.names():
            if G.base(name) in ("minecraft:crimson_roots", "minecraft:warped_roots", "minecraft:nether_sprouts", "minecraft:soul_torch"):
                idx = g.idx[name]
                xs, ys, zs = (g.a == idx).nonzero()
                x0, y0, z0 = g.box[:3]
                for i, j, k in zip(xs, ys, zs):
                    out.append((G.base(name), G.base(g.block_at(int(i) + x0, int(j) + y0 - 1, int(k) + z0))))
    return out


@pytest.mark.parametrize("theme", ["crimson_forest", "warped_forest", "soul_sand_valley"])
def test_plants_and_torches_stand_only_on_what_vanilla_lets_them(theme):
    found = planted(theme)
    assert len(found) > 50, "the test needs plants to judge"
    for plant, under in found:
        if plant == "minecraft:soul_torch":
            assert under in FULL_TOP, (plant, under)
        else:
            assert under in SUPPORT_FOR_ROOTS, (plant, under)


def test_a_ground_cover_that_ignores_the_support_would_be_caught_by_the_test_above(monkeypatch):
    """MUTATE THE GENERATOR (not the record): ground cover that drops the `on` list plants roots on bare netherrack, where a
    root pops off in vanilla; the support test must fail on that build."""
    real = K.dress_ground_cover

    def careless(ctx, spec):
        spec = dict(spec)
        spec["plants"] = [{k: v for k, v in p.items() if k != "on"} for p in spec["plants"]]
        return real(ctx, spec)

    monkeypatch.setitem(R.DRESS, "ground_cover", (careless, R.DRESS["ground_cover"][1]))
    found = planted("crimson_forest")
    bad = [(p, u) for p, u in found if p != "minecraft:soul_torch" and u not in SUPPORT_FOR_ROOTS]
    assert bad, "the mutant plants roots on netherrack, floor patches and piles; the support test has something to refuse"


def test_a_hazard_a_theme_is_tempted_by_is_refused_by_the_walk_check(monkeypatch):
    """Magma in the soul valley's floor patches (or soul fire for its torches) would be a hazard a player walks on: the kit's
    problems() names it."""
    real = K.dress_floor_patches

    def hot(ctx, spec):
        spec = dict(spec)
        spec["blocks"] = [{"block": "minecraft:magma_block", "w": 1}]
        spec["per100"] = 30
        return real(ctx, spec)

    monkeypatch.setitem(R.DRESS, "floor_patches", (hot, R.DRESS["floor_patches"][1]))
    doc = fx_doc("soul_sand_valley", variants=False)
    p = R.problems(doc)
    assert any("magma" in x or "hazard" in x.lower() for x in p), p[:3]


# ================================================================================================= the fixtures build clean


@pytest.mark.parametrize("theme", NETHER)
def test_the_fixture_builds_clean_in_every_variant(theme):
    doc = fx_doc(theme)
    assert D.problems(doc) == []


@pytest.mark.parametrize("theme", NETHER)
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


@pytest.mark.slow
@pytest.mark.parametrize("theme", NETHER)
def test_the_independent_audit_reports_nothing_on_the_fixture(theme):
    import dungeon_independent_audit as IA
    doc = fx_doc(theme)
    files = IA.build_files(doc)
    F, _info = IA.audit(files, doc, bands=[1], all_slots=False)
    assert [IA.fmt(f) for f in F] == []
