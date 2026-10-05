"""tools/desert_wreck_audit.py against tools/desert_wreck.py: the audit's derived numbers are the hand-computed ones, and
a broken GENERATOR fails a named check.

Written by an agent that built none of the Brass Petrel (CLAUDE.md principle 16). Every mutation below changes the
generator's CODE (a line of tools/desert_wreck.py, exec'd as a copy) and leaves data/desert_wreck.json and every other
data file alone: a record-side mutation moves the expectation and the output together and proves nothing (CLAUDE.md,
"How to prove an audit is independent"). The mutated copy also has its own self-check (problems()) switched off, since
a builder that refuses to write proves nothing about the audit; each mutation counts as caught only by an error the
unmutated build on the same ground does not have.

Most tests run on a synthetic beach, x-independent, so every number is by hand:
  z <= 6755: y75 (the dune over the bow)   6756-6790: y68   6791-6800: y66 (the transom row: D = 66 + 4 = 70, K = 63)
  6801-6827: y63 / y62 (the flats; the strand ward at y62 = 63 - 1; Castellan's spot (6448, 6826) on y62)
  6828-6829: y61 (awash)   z >= 6830: y58 (the sea)
The committed build on the canonical heightmap is audited last (skipped, and says so, when no heightmap is found).

NOT covered, and it needs a running server: that the fills land; the dune's real material over the bow; the wards
redirecting spawns (EXP-021/EXP-033); the keeper waking Castellan; the cache paying; whether anything spawns in the hold.
"""
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import desert_wreck_audit as A  # noqa: E402

DOC = json.loads((ROOT / "data" / "desert_wreck.json").read_text(encoding="utf-8"))
SRC = (ROOT / "tools" / "desert_wreck.py").read_text(encoding="utf-8")
SELF_CHECK = "    probs = problems(doc, pl, g)\n"


class Beach:
    """The synthetic beach above: ground depends on z only."""

    def __call__(self, x, z):
        if z <= 6755:
            return 75
        if z <= 6790:
            return 68
        if z <= 6800:
            return 66
        if z <= 6820:
            return 63
        if z <= 6827:
            return 62
        if z <= 6829:
            return 61
        return 58


class Flat:
    def __init__(self, y=100):
        self.y = y

    def __call__(self, x, z):
        return self.y


def generator(*subs):
    """tools/desert_wreck.py as a fresh module, each (old, new) applied once, its own refusal switched off."""
    src = SRC
    assert src.count(SELF_CHECK) == 1
    src = src.replace(SELF_CHECK, "    probs = []\n")
    for old, new in subs:
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    mod = types.ModuleType("desert_wreck_mutant")
    mod.__file__ = str(ROOT / "tools" / "desert_wreck.py")
    exec(compile(src, "desert_wreck_mutant", "exec"), mod.__dict__)
    return mod


def build(tmp_path, g, *subs, name="pack"):
    mod = generator(*subs)
    files, _pl = mod.files(DOC, g)
    out = tmp_path / name
    mod.write(files, out)
    return out


@pytest.fixture(scope="module")
def jar():
    p = A.find_jar()
    return A.Jar(p) if p else None


@pytest.fixture(scope="module")
def baseline(tmp_path_factory, jar):
    pack = build(tmp_path_factory.mktemp("base"), Beach())
    return A.audit(DOC, pack, Beach(), A.DATA, jar, tight_bounds=False)


def _caught(baseline, rep, check):
    new = [e for e in rep.failed(check) if e not in baseline.errors]
    return new


# ------------------------------------------------------------------------------------------- hand-computed numbers
# Without it the audit's hull could be derived wrongly (deck from the wrong row, a misread taper) and every shape check
# would hold the build to a wrong hull.
def test_the_hulls_deck_and_keel_are_the_hand_computed_ones():
    H = A.Hull(DOC, Beach())
    assert (H.D, H.K, H.F) == (70, 63, 64)
    # deck widths: bow 3,3,5,5,7,7,9,9,9 (57) + 27 rows of 11 (297) + stern 11,11,9,9 (40)
    assert sum(1 for (_x, y, _z) in H.cells if y == 70) == 394
    # keel (narrowed by 3): bow 0,0,0,0,1,1,3,3,3 (11) + 27 rows of 5 (135) + stern 5,5,3,3 (16)
    assert sum(1 for (_x, y, _z) in H.cells if y == 63) == 162


# Without it the parser could drop fills, count a clearing as structure, or miss a write outside a force-load, and
# every check downstream would audit a different world from the one the server builds.
def test_the_parser_reads_fills_clearings_and_forceloads():
    text = "\n".join(["# c", "forceload add 0 0 15 15", "fill 0 1 0 1 1 1 minecraft:sand",
                      "fill 0 0 0 3 3 3 minecraft:air replace minecraft:dead_bush",
                      "setblock 2 5 2 minecraft:spruce_wall_sign[facing=east]{front_text:{messages:['\"a b\"']}}",
                      "forceload remove 0 0 15 15", "setblock 20 1 20 minecraft:sand"])
    blocks, _order, clears, unloaded, oversized = A.parse_build(text)
    assert len([c for c, s in blocks.items() if s == "minecraft:sand"]) == 5
    assert A.base(blocks[(2, 5, 2)]) == "minecraft:spruce_wall_sign"
    assert clears == [((0, 0, 0, 3, 3, 3), "minecraft:air", "minecraft:dead_bush")]
    assert [i for i, _l in unloaded] == [6] and not oversized


# Without it the walk could pass a two-block step or a one-high gap, so a hatch nobody can climb would still "reach".
def test_the_walk_takes_steps_of_one_and_climbs_ladders():
    g = Flat(100)
    stairs = {(1, 101, 0): "minecraft:stone", (2, 101, 0): "minecraft:stone", (2, 102, 0): "minecraft:stone"}
    W = A.World(stairs, g, 62)
    dom = (-2, 6, 95, 115, -2, 2)
    reach = A.walk(W, (0, 101, 0), dom)
    assert (1, 102, 0) in reach            # one up: walkable
    assert (2, 103, 0) in reach            # and one more
    cliff = {(1, y, 0): "minecraft:stone" for y in (101, 102)}
    reach = A.walk(A.World(cliff, g, 62), (0, 101, 0), (-1, 1, 95, 115, 0, 0))
    assert (1, 103, 0) not in reach        # two up in one step: not walkable
    lad = dict(cliff)
    lad.update({(0, 101, 0): "minecraft:ladder[facing=west]", (0, 102, 0): "minecraft:ladder[facing=west]"})
    reach = A.walk(A.World(lad, g, 62), (0, 101, 0), (-1, 1, 95, 115, 0, 0))
    assert (1, 103, 0) in reach            # the ladder climbs it


# Without it the light check could count light through planks or never fall off, and a dark hold would pass.
def test_block_light_falls_off_by_one_per_block_and_stops_at_planks():
    g = Flat(100)
    blocks = {(x, 101, 0): "minecraft:air" for x in range(1, 20)}
    blocks[(0, 101, 0)] = "minecraft:lantern[hanging=false]"
    for x in range(-1, 21):
        for dz in (-1, 1):
            blocks[(x, 101, dz)] = "minecraft:spruce_planks"
        blocks[(x, 102, 0)] = "minecraft:spruce_planks"
    blocks[(-1, 101, 0)] = "minecraft:spruce_planks"
    blocks[(20, 101, 0)] = "minecraft:spruce_planks"
    W = A.World(blocks, g, 62)
    H = A.Hull(DOC, Beach())
    rep = A.Report()
    level = A.check_light(W, H, DOC, [], rep)
    assert level[(14, 101, 0)] == 1 and level.get((15, 101, 0), 0) == 0
    assert (0, 103, 0) not in level        # nothing through the plank ceiling


# Without it a lantern hung from nothing, sand over air or a spar in mid-air would pass.
def test_support_finds_hung_blocks_falling_blocks_and_floating_ones():
    g = Flat(100)
    H = A.Hull(DOC, Beach())
    blocks = {(0, 105, 0): "minecraft:lantern[hanging=true]",
              (2, 101, 0): "minecraft:spruce_fence", (2, 102, 0): "minecraft:lantern[hanging=false]",
              (4, 103, 0): "minecraft:sand",
              (6, 104, 0): "minecraft:stripped_spruce_log[axis=x]"}
    rep = A.Report()
    A.check_support(A.World(blocks, g, 62), H, [], rep)
    text = "\n".join(rep.errors)
    assert "lantern at (0, 105, 0)" in text and "(2, 102, 0)" not in text
    assert "sand at (4, 103, 0)" in text
    assert "touch no ground" in text


# Without it a reef head in deep water, air dug below the sea or air beside it would pass.
def test_the_sea_check_bites_on_deep_and_flooding_writes():
    g = Beach()
    blocks = {(6488, 59, 6840): "minecraft:calcite", (6488, 62, 6828): "minecraft:air",
              (6400, 63, 6810): "minecraft:air"}
    rep = A.Report()
    A.check_sea(A.World(blocks, g, 62), rep)
    text = "\n".join(rep.errors)
    assert "(6488, 59, 6840)" in text and "(6488, 62, 6828) minecraft:air written in a sea column" in text
    assert "(6400, 63, 6810)" not in text


# Without it the jar lookups could accept a missing item or a made-up regional form.
def test_the_jar_reads_items_species_and_forms(tmp_path):
    p = tmp_path / "c.jar"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("assets/cobblemon/lang/en_us.json", json.dumps({"item.cobblemon.shell_bell": "Shell Bell"}))
        z.writestr("assets/cobblemon/models/item/shell_bell.json", "{}")
        z.writestr("assets/cobblemon/models/item/dive_ball.json", "{}")
        z.writestr("data/cobblemon/species/generation2/corsola.json", json.dumps({"forms": [{"aspects": ["galarian"]}]}))
    j = A.Jar(p)
    assert j.item("cobblemon:shell_bell") and not j.item("cobblemon:dive_ball")   # no lang entry
    assert j.species("corsola") and j.species("corsola", "galarian") and not j.species("corsola", "alolan")
    assert not j.species("sandygast")


# ------------------------------------------------------------------------------------------- the generator on the beach
# Without it the mutation tests below could be "catching" errors the unmutated build already has.
def test_the_unmutated_build_on_the_synthetic_beach_is_clean(baseline):
    assert not baseline.errors, baseline.errors


MUTATIONS = {
    # the hull two blocks down: the deck is no longer where the transom's ground puts it
    "hull_2_down": (("self.D = max(g(x, z) for x, z in transom) + w[\"stern_show\"]",
                     "self.D = max(g(x, z) for x, z in transom) + w[\"stern_show\"] - 2"), "shape"),
    # the hatch dropped: the deck over the ladder stays planks, and the hold has no way up
    "no_hatch": (("    p.hang(0, D, hz, \"minecraft:spruce_trapdoor",
                  "    0 and p.hang(0, D, hz, \"minecraft:spruce_trapdoor"), "walk"),
    # the hold's lanterns stood on the air under the deck instead of hanging from it
    "lantern_unhung": (("    p.hang(lx, D - 1, lz, \"minecraft:lantern[hanging=true",
                        "    p.hang(lx, D - 1, lz, \"minecraft:lantern[hanging=false"), "support"),
    # the hold's lanterns left out: the cargo hold goes dark
    "hold_dark": (("    p.hang(lx, D - 1, lz, \"minecraft:lantern[hanging=true,waterlogged=false]\")",
                   "    pass"), "light"),
    # the fallen topmast seated one block high: a log line in the air
    "spar_floats": (("        y = p.g(x, z) + 1\n        p.put_at(x, y, z, \"%s[axis=x]\"",
                     "        y = p.g(x, z) + 2\n        p.put_at(x, y, z, \"%s[axis=x]\""), "support"),
    # the clearing widened to #minecraft:replaceable, which holds water
    "clear_replaceable": (("PLANTS = (\"minecraft:dead_bush\",", "PLANTS = (\"#minecraft:replaceable\", \"minecraft:dead_bush\","),
                          "footprint"),
    # the reef laid into deep water
    "reef_deep": (("        if g < SEA - 1:\n            continue", "        if g < SEA - 9:\n            continue"), "sea"),
}


# Without it the audit could share the generator's derivation and pass whatever the generator writes (CLAUDE.md, "How
# to prove an audit is independent"): each mutation changes the generator's code only and must fail its named check.
@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_mutated_generator_fails_the_audit(name, tmp_path, baseline, jar):
    sub, check = MUTATIONS[name]
    pack = build(tmp_path, Beach(), sub)
    rep = A.audit(DOC, pack, Beach(), A.DATA, jar, tight_bounds=False)
    assert _caught(baseline, rep, check), (name, rep.errors[:5])


# ------------------------------------------------------------------------------------------- the canonical heightmap
def _canonical():
    try:
        import ground
        return ground.load()
    except (SystemExit, Exception) as e:   # noqa: BLE001
        pytest.skip("NOT_EXECUTED: no canonical heightmap (%s)" % e)


@pytest.fixture(scope="module")
def canonical_pack(tmp_path_factory):
    g = _canonical()
    import desert_wreck
    files, _pl = desert_wreck.files(DOC, g)
    out = tmp_path_factory.mktemp("canon") / "pack"
    desert_wreck.write(files, out)
    return g, out


# Without it the real build could break on the real beach (a hull cell left natural, a dark cell, a ward moved) with
# only the synthetic beach checked. This is the audit's verdict on tonight's build.
def test_the_committed_build_on_the_canonical_heightmap_passes_the_audit(canonical_pack, jar):
    g, pack = canonical_pack
    rep = A.audit(DOC, pack, g, A.DATA, jar)
    assert not rep.errors, rep.errors
    assert jar is not None, "NOT_EXECUTED in part: no Cobblemon 1.8.0 jar, species and items unchecked"


# Without it the mutation proof would only hold on the synthetic beach.
def test_on_the_canonical_heightmap_a_hull_two_down_fails(tmp_path, canonical_pack, jar):
    g, _pack = canonical_pack
    pack = build(tmp_path, g, MUTATIONS["hull_2_down"][0])
    rep = A.audit(DOC, pack, g, A.DATA, jar)
    assert rep.failed("shape"), rep.errors[:5]
