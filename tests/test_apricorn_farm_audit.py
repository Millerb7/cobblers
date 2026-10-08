"""Tests for tools/apricorn_farm_audit.py, the independent audit of Hollin's Apricorn Farm.

Two kinds, neither touching the canonical heightmap or the Cobblemon jar:
  * the audit's primitives (the replay, the fruit rule, light, walking, the ground rule, distances, the economy, the
    step wiring) on tiny hand-built fixtures whose answers are worked out in the comments;
  * the whole farm built by the generator over a SYNTHETIC flat surface (every column y130), where the expectations are
    hand-computable (every terrace floor y130, every building floor y131), and the generator MUTATED in source with the
    data untouched, to prove each check bites on a change the builder could make (CLAUDE.md "How to prove an audit is
    independent").

What these do not cover: the real heightmap's terraces (the prepare job runs the audit there), the jar-backed checks
(exercised with a synthetic zip only), and anything in game: the farm has never been applied or seen.
"""
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import apricorn_farm_audit as A  # noqa: E402

FN = Path("data") / "cobblers" / "function" / "apricorn_farm"


def pack_with(tmp_path, functions):
    d = tmp_path / "pack"
    for name, lines in functions.items():
        f = d / FN / (name + ".mcfunction")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


def flat(y):
    return lambda x, z: y


# --------------------------------------------------------------------------------------------- the replay
# Protects: the replay follows `function` calls and expands fills; without it every later check reads an empty world.
def test_replay_follows_calls_and_expands_fills(tmp_path):
    p = pack_with(tmp_path, {"build": ["function cobblers:apricorn_farm/a", "setblock 9 9 9 minecraft:stone"],
                             "a": ["fill 0 0 0 2 0 1 minecraft:dirt"]})
    rep = A.Replay(p, "apricorn_farm/build", ground=flat(-10))
    assert len(rep.state) == 3 * 1 * 2 + 1 and rep.calls == ["apricorn_farm/build", "apricorn_farm/a"]


# Protects: `fill ... replace <tag>` only touches tag members; a replay that filled blindly would erase the farm it clears.
def test_conditional_fill_touches_only_tag_members(tmp_path):
    p = pack_with(tmp_path, {"build": [
        "setblock 0 0 0 cobblemon:apricorn_leaves[distance=1,persistent=true,waterlogged=false]",
        "setblock 1 0 0 minecraft:stone",
        "fill 0 0 0 1 0 0 minecraft:air replace #minecraft:leaves"]})
    rep = A.Replay(p, "apricorn_farm/build", A.JAR_TAG_FALLBACK, ground=flat(-10))
    assert A.base(rep.state[(0, 0, 0)]) == "minecraft:air" and rep.state[(1, 0, 0)] == "minecraft:stone"


# Protects: a fruit whose leaf a LATER write replaces breaks at that moment (ApricornBlock.updateShape), even if a leaf
# is put back afterwards; the final-world check alone would miss it.
def test_fruit_breaks_when_a_later_write_takes_its_leaf(tmp_path):
    leaf = "cobblemon:apricorn_leaves[distance=1,persistent=true,waterlogged=false]"
    p = pack_with(tmp_path, {"build": [
        "setblock 1 0 0 " + leaf,
        "setblock 0 0 0 cobblemon:red_apricorn[age=3,facing=east]",
        "setblock 1 0 0 " + leaf,                     # the same state again: no update, no break
        "setblock 1 0 0 minecraft:stone",             # the leaf gone: the fruit breaks
        "setblock 1 0 0 " + leaf]})
    rep = A.Replay(p, "apricorn_farm/build", ground=flat(-10))
    assert [(b[0], b[1]) for b in rep.breaks] == [((0, 0, 0), (1, 0, 0))]
    assert A.base(rep.state[(0, 0, 0)]) == "minecraft:air"


# --------------------------------------------------------------------------------------------- light and walking
# Protects: the light model. A lantern at (0, 1, 0) over flat ground y0: (5, 1, 0) is 5 steps away, light 10; (0, 1, 7)
# is 7, light 8; the ground cell (0, 0, 1) stops light, 0. With a leaf at (3, 1, 0) the straight route costs one more
# (the leaf takes 2): (4, 1, 0) is 10 and (5, 1, 0) 9; every route round the leaf is 2 steps longer, so 9 stands.
def test_light_falls_one_a_block_and_two_through_leaves(tmp_path):
    p = pack_with(tmp_path, {"build": ["setblock 0 1 0 minecraft:lantern[hanging=false,waterlogged=false]"]})
    rep = A.Replay(p, "apricorn_farm/build", ground=flat(0))
    W = A.World(rep, flat(0))
    lvl = A.light_map(W, (-20, -20, 20, 20), 0, 20)
    assert lvl[(5, 1, 0)] == 10 and lvl[(0, 1, 7)] == 8 and lvl.get((0, 0, 1), 0) == 0   # ground stops light
    p2 = pack_with(tmp_path / "b", {"build": [
        "setblock 0 1 0 minecraft:lantern[hanging=false,waterlogged=false]",
        "setblock 3 1 0 cobblemon:apricorn_leaves[distance=1,persistent=true,waterlogged=false]"]})
    rep2 = A.Replay(p2, "apricorn_farm/build", ground=flat(0))
    lvl2 = A.light_map(A.World(rep2, flat(0)), (-20, -20, 20, 20), 0, 20)
    assert lvl2[(5, 1, 0)] == 9


# Protects: the walking rule. From flat ground y0 (feet y1): a one-block step up is a jump (reached); a two-block one
# is not; a stair on a block (low half 1.5 above the ground) is not -- the barn's step.
def test_walk_takes_one_block_rises_not_one_and_a_half(tmp_path):
    p = pack_with(tmp_path, {"build": [
        "setblock 2 1 0 minecraft:stone",                                   # +1: feet y2 at x2
        "fill 0 1 3 0 2 3 minecraft:stone",                                   # +2: feet y3 at x0 z3
        "setblock 2 1 6 minecraft:cobblestone",
        "setblock 2 2 6 minecraft:cobblestone_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]",
        "fill 3 0 6 3 2 6 minecraft:stone"]})
    rep = A.Replay(p, "apricorn_farm/build", ground=flat(0))
    W = A.World(rep, flat(0))
    # keep each case apart: only x0..2 on row z0, x-1..0 on z3, x1..2 on z6
    got = A.flood(W, (1, 1, 0), (0, 0, 2, 0))
    assert (2, 2, 0) in got
    assert (0, 3, 3) not in A.flood(W, (-1, 1, 3), (-1, 3, 0, 3))
    assert not any(k[0] == 2 for k in A.flood(W, (1, 1, 6), (1, 6, 2, 6)))


# --------------------------------------------------------------------------------------------- the ground rule
def _mini():
    D = types.SimpleNamespace(L={"alleys_z": [[0]]})
    g = lambda x, z: 10 if x <= 2 else 12        # 9 columns at y10, 6 at y12 in the 5x3 box x0-4, z0-2
    return D, g


# Protects: the terrace floor re-derivation. Earthwork over the box: F10 = 6*2 = 12, F11 = 9 + 6 = 15, F12 = 18.
# An east gate at (4, 1) looks out on (5, 1) ground 12, so only F11..13 keep it walkable: F11 (15) wins over F12 (18).
# A west gate looks out on (-1, 1) ground 10: F10 and F11 qualify and F10 (12) wins.
def test_expected_floor_is_least_earthwork_with_a_walkable_gate():
    D, g = _mini()
    east = {"box": (0, 0, 4, 2), "wc": (2, 1), "gate_side": "east"}
    west = dict(east, gate_side="west")
    assert A.expected_floor(D, g, east)[0] == 11
    assert A.expected_floor(D, g, west)[0] == 10


# --------------------------------------------------------------------------------------------- distances and water
# Protects: corridor boxes count as filled rectangles; a point inside is 0 away, a 3-4-5 offset from a corner is 5.
def test_rect_distance_is_filled():
    assert A.rect_dist((0, 0, 10, 10), 5, 5) == 0
    assert A.rect_dist((0, 0, 10, 10), 13, 14) == 5.0


# Protects: a river corridor is tested along its segments, not just at its vertices: a column halfway between two
# vertices 100 apart, 5 off the line, under a surface y20 with ground y10, is wet for a 32-wide river (half 17).
def test_river_wet_between_vertices():
    course = {"character": {"width": [32]}, "graded_polyline": [[0, 0, 20.0, 15.0], [100, 0, 20.0, 15.0]]}
    assert A.river_wet([course], flat(10), 50, 5)
    assert not A.river_wet([course], flat(10), 50, 30)
    assert not A.river_wet([course], flat(25), 50, 5)        # ground over the surface: dry


# --------------------------------------------------------------------------------------------- economy
# Protects: the reported economy arithmetic. red 101 -> 25 crafts = 100 Poke Balls; Great = min(74//2, 101//2) = 37
# crafts = 148; Ultra = min(74//2, 63//2) = 31 crafts = 124 (the jar's recipes: 4 red; 2 blue + 2 red; 2 black + 2
# yellow; each makes 4).
def test_economy_counts_balls_from_fruit():
    doc = json.loads((ROOT / "data" / "apricorn_farm.json").read_text(encoding="utf-8"))
    R = A.Report()
    got = A.economy(R, A.Design(doc), {"red": 101, "blue": 74, "yellow": 63, "green": 98, "pink": 76, "white": 64,
                                       "black": 74}, None)
    assert (got["poke"], got["great"], got["ultra"]) == (100, 148, 124)
    assert 17.0 < got["cycle_min"] < 17.2           # 3 stages x 5 random ticks x 4096/3 game ticks / 20 / 60


# --------------------------------------------------------------------------------------------- the jar and the wiring
def _jar(tmp_path, cls_strings=(b"method_9558", b"method_9559", b"method_10093", b"APRICORN_LEAVES", b"method_9514")):
    f = tmp_path / "fake.jar"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("data/cobblemon/tags/block/apricorn_leaves.json", json.dumps({"values": ["cobblemon:apricorn_leaves"]}))
        z.writestr("com/cobblemon/mod/common/block/ApricornBlock.class", b"\xca\xfe" + b" ".join(cls_strings))
        var = {"age=%d,facing=%s" % (a, d): {} for a in range(4) for d in ("north", "south", "east", "west")}
        z.writestr("assets/cobblemon/blockstates/red_apricorn.json", json.dumps({"variants": var}))
        z.writestr("data/cobblemon/loot_table/blocks/red_apricorn.json", json.dumps({"pools": [{"entries": [{
            "name": "cobblemon:red_apricorn", "conditions": [{"properties": {"age": "3"}}]}]}]}))
    return A.Jar(f)


# Protects: the facing rule is re-read from the jar; a jar whose ApricornBlock no longer names APRICORN_LEAVES (a
# changed attachment rule) must fail, not be trusted.
def test_jar_rule_reads_the_class_and_the_tag(tmp_path):
    R = A.Report()
    A.jar_rule(R, _jar(tmp_path), ["red"])
    assert R.errors == []
    other = tmp_path / "changed"
    other.mkdir()
    R2 = A.Report()
    A.jar_rule(R2, _jar(other, cls_strings=(b"method_9558",)), ["red"])
    assert any("APRICORN_LEAVES" in e for e in R2.errors)


# Protects: the step order. R9AF before R9E, R18AF after R17N, the audit job after the build; swapping fails.
def test_reapply_wiring_is_checked_and_holds_in_the_real_file():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    R = A.Report()
    A.check_reapply(R, text)
    assert R.errors == []
    bad = text.replace('("R9AF"', '("R9XX"').replace('("R9E"', '("R9AF"').replace('("R9XX"', '("R9E"')
    R2 = A.Report()
    A.check_reapply(R2, bad)
    assert any("R9AF" in e for e in R2.errors)


# Protects: the KNOWN list is strict. A known fault that stops firing is stale and fails the run.
def test_known_list_goes_stale():
    real, hits, stale = A.classify(["walk: x"], [("walk", "x", ""), ("light", "y", "")])
    assert real == [] and hits == ["walk: x"] and [k[1] for k in stale] == ["y"]


# Protects: the audit fails closed on a pack with no build.
def test_missing_pack_fails(tmp_path):
    doc = json.loads((ROOT / "data" / "apricorn_farm.json").read_text(encoding="utf-8"))
    R = A.audit(doc, flat(130), tmp_path / "nothing", siting=False, dialogue=False)
    assert R.errors and R.errors[0].startswith("steps:")


# --------------------------------------------------------------------------------------------- the whole farm, synthetic
GEN = ROOT / "tools" / "apricorn_farm.py"
SURFACE = 130
STRICT = ("fruit", "terrace", "trees", "building", "blocks", "spots", "merchant", "steps", "paths")


def generator(old=None, new=None):
    """tools/apricorn_farm.py, optionally with exact source edits (one string, or a list of (old, new) pairs): the
    generator mutated, the data untouched."""
    src = GEN.read_text(encoding="utf-8")
    edits = [] if old is None else (old if isinstance(old, list) else [(old, new)])
    for o, n in edits:
        assert src.count(o) == 1, o
        src = src.replace(o, n)
    mod = types.ModuleType("apricorn_farm_mutant")
    mod.__file__ = str(GEN)
    exec(compile(src, str(GEN), "exec"), mod.__dict__)
    return mod


def build_and_audit(tmp_path, mod, check_rules=False):
    doc = json.loads((ROOT / "data" / "apricorn_farm.json").read_text(encoding="utf-8"))
    g = flat(SURFACE)
    out, res = mod.files(doc, g, wet=lambda x, z: False, check_rules=check_rules)
    mod.write(out, tmp_path / "pack")
    return doc, A.audit(doc, g, tmp_path / "pack", wet=lambda x, z: False, siting=False, dialogue=False)


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    return build_and_audit(tmp_path_factory.mktemp("clean"), generator(), check_rules=True)


def strict_errors(R):
    return [e for e in R.errors if e.split(":")[0] in STRICT]


# Protects: on a flat y130 surface the hand-computed farm: every terrace floor y130 (no earthwork), every building
# floor y131, the seven groves' fruit = 12 trees x their design's count, and none of the strict checks fire.
def test_flat_farm_is_hand_computable(clean):
    doc, R = clean
    assert strict_errors(R) == []
    terr = [n for n in R.notes if n.startswith("terraces:")][0]
    assert terr.count("(%d, 0)" % SURFACE) == 7
    assert "{'farmhouse': %d, 'barn': %d}" % (SURFACE + 1, SURFACE + 1) in " ".join(R.notes)
    D = A.Design(doc)
    by_place = [n for n in R.notes if n.startswith("fruit:")][0]
    for c in D.colours:
        assert "'grove_%s': %d" % (c, 12 * D.fruit_per_tree(c)) in by_place


MUTATIONS = [
    # (name, old source, new source, the check that must fire)
    ("fruit faces away from its leaf",
     "p.hang(bx, y, bz, fruit(colour, face, fruit_age(bx, y, bz)), who)",
     "p.hang(bx, y, bz, fruit(colour, {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}[face], "
     "fruit_age(bx, y, bz)), who)", "fruit"),
    ("terrace two blocks off its ground",
     "_k, F, (diff, _pref, gate, outside) = best",
     "_k, F, (diff, _pref, gate, outside) = best\n    F += 2", "terrace"),
    ("building floor without its +1",
     "F = max(p.g(x, z) for x, z in cols) + 1",
     "F = max(p.g(x, z) for x, z in cols) + 0", "building"),
    ("merchant inside the counter",
     'merchant = spot(p, m["at"][0], m["at"][1], "the stall keeper")',
     'merchant = spot(p, m["at"][0], m["at"][1], "the stall keeper")\n'
     '    merchant = (merchant[0] + 1, merchant[1], merchant[2])', "spots"),
    # the builder's own per-block guard refuses water, so the mutant also lets it past that guard: two code edits
    ("a water block in the groves' troughs",
     [('p.put(x, F + 1, z, "minecraft:water_cauldron[level=3]", who)', 'p.put(x, F + 1, z, "minecraft:water", who)'),
      ("if base(state) not in self.allowed:", "if base(state) not in self.allowed | {'minecraft:water'}:")],
     None, "blocks"),
]


# Protects: independence. Each mutation changes the GENERATOR's code with data/apricorn_farm.json untouched; an audit
# that shared the builder's derivation would move with it and pass. Each must fire its named check.
@pytest.mark.parametrize("name,old,new,check", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_generator_mutation_is_caught(tmp_path, name, old, new, check):
    _doc, R = build_and_audit(tmp_path, generator(old, new))
    fired = [e for e in R.errors if e.startswith(check + ":")]
    assert fired, (name, R.errors[:5])
