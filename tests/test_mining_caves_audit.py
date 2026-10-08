"""The independent audit of the refillable mining caves (tools/mining_caves_audit.py), and its proof that it bites.

Written by test-author for unit CAVES (2026-10-10), who built none of the caves. The expectation comes from the
auditor's own reading of data/mining_caves.json's rules text (tools/mining_caves_audit.py expected()), never from
tools/mining_caves.py's geometry. The pack under test is produced by the builder itself, in process, on a synthetic
fixture: two caves on flat ground at y80, so every box below is hand-computable. The proofs of independence MUTATE THE
GENERATOR (tools/mining_caves.py's source text, one edit at a time, data untouched) and show the audit goes red.

Two tests read the canonical heightmap (the real caves' geometry and walkability) and skip, naming it, without one.
The keep-clear checks need a full checkout's derived/ and build/ and run from the CLI:
  python tools/mining_caves_audit.py --inputs-root <full checkout>

Not covered (validity is not behaviour, .claude/rules/testing.md): that Minecraft parses these commands and that the
vanilla selector/loaded/return semantics the command model states hold in 1.21.1; entities other than players and
cobblemon:pokemon (a tamed wolf, a Cobblemon NPC) are not guarded by the pack and can be buried; Pokemon AI walking
into a gallery between the guard and the fill (one function, one tick: not expected); the yields in play.
"""
from __future__ import annotations

import copy
import itertools
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import mining_caves_audit as A  # noqa: E402

BUILDER = ROOT / "tools" / "mining_caves.py"
FLAT = 80


def flat(x, z):
    return FLAT


def fixture_spec():
    """The real record's geometry, restore and yields; two synthetic caves on flat ground. Cave fx_east's first
    gallery straddles four chunks (x 88..98 crosses x=96, z 189..195 crosses z=192), so the loaded check is exercised."""
    spec = copy.deepcopy(A.load())
    mats = {"wall": "minecraft:stone", "shell": "minecraft:tuff", "floor": "minecraft:gravel",
            "stair": "minecraft:cobblestone_stairs", "timber": "minecraft:spruce_log"}
    deep = {"wall": "minecraft:deepslate", "shell": "minecraft:smooth_basalt", "floor": "minecraft:cobbled_deepslate",
            "stair": "minecraft:cobbled_deepslate_stairs", "timber": "minecraft:stripped_dark_oak_log"}
    spec["caves"] = [
        dict(mats, id="fx_east", name="Fixture east", place="fixture", host_anchor=[168, 196], ring={"min": 30, "max": 100},
             yield_="early", drop=10, entry={"anchor": [108, 196], "front": "east"},
             galleries=[{"id": "fx_g1", "side": "left", "slot": 0, "offset_ticks": 0},
                        {"id": "fx_g2", "side": "right", "slot": 0, "offset_ticks": 8000},
                        {"id": "fx_g3", "side": "left", "slot": 1, "offset_ticks": 16000}]),
        dict(deep, id="fx_west", name="Fixture west", place="fixture", host_anchor=[440, 300], ring={"min": 30, "max": 100},
             yield_="deep", drop=22, entry={"anchor": [500, 300], "front": "west"},
             galleries=[{"id": "fx_d1", "side": "left", "slot": 0, "offset_ticks": 0},
                        {"id": "fx_d2", "side": "right", "slot": 0, "offset_ticks": 12000}]),
    ]
    for c in spec["caves"]:
        c["yield"] = c.pop("yield_")
    return spec


class _NoClearance:
    """The keep-clear rules are not what these tests are about: every column is free."""

    def __init__(self, *a, **k):
        self.notes = []

    def why(self, x, z):
        return None

    def tree(self, x, z):
        return False


def builder(mutation=None):
    """tools/mining_caves.py as a fresh module, with one (old, new) source edit applied (it must match exactly once)."""
    src = BUILDER.read_text(encoding="utf-8")
    if mutation:
        old, new = mutation
        assert src.count(old) == 1, "the mutation %r no longer matches the generator once" % old[:60]
        src = src.replace(old, new)
    mod = types.ModuleType("mining_caves_under_audit")
    mod.__file__ = str(BUILDER)
    exec(compile(src, str(BUILDER), "exec"), mod.__dict__)
    return mod


def pack(spec, ground=flat, mutation=None, real_ground=False):
    """(functions {name: lines}, tag values) the builder emits for `spec` on `ground` (no file written)."""
    mc = builder(mutation)
    if not real_ground:
        mc.G = types.SimpleNamespace(Ground=lambda source_root=None: ground)
    mc.Clearance = _NoClearance
    plan, _probs, _notes = mc.model(spec)
    fns = {"build_%s" % e["cave"]["id"]: mc.build_lines(spec, e) for e in plan}
    fns.update(mc.driver_files(spec, plan))
    return fns, mc.resettable(spec)


@pytest.fixture(scope="module")
def fx():
    spec = fixture_spec()
    fns, tag = pack(spec)
    return spec, fns, tag


# ------------------------------------------------------------------ the auditor's own model, by hand

# Without it the audit's expectation could drift from the rules text and every check below would compare the pack
# with a wrong box: fx_east's first gallery, by hand from the rules (mouth (108, 196) east, drop 10, flat y80): y0 80,
# hall y70, slot rows d 11..19 -> x 97..89, left u -2..-6 -> z 194..190, y 70..75; body d 12..18, u -2..-5, y 71..74.
def test_auditor_model_matches_the_hand_computed_gallery():
    spec = fixture_spec()
    ex = A.expected(spec, spec["caves"][0], flat)
    assert (ex["y0"], ex["yh"]) == (80, 70)
    g = ex["galleries"]["fx_g1"]
    assert g["box"] == (89, 70, 190, 97, 75, 194)
    assert len(g["body"]) == 7 * 4 * 4 and len(g["shell"]) == 9 * 5 * 6 - 7 * 4 * 4
    assert min(c[0] for c in g["body"]) == 90 and max(c[0] for c in g["body"]) == 96
    assert {c[2] for c in g["body"]} == {191, 192, 193, 194} and {c[1] for c in g["body"]} == {71, 72, 73, 74}
    assert A.grow(g["box"], 1) == (88, 69, 189, 98, 76, 195)
    # the west cave runs +x and its right side is +z
    w = A.expected(spec, spec["caves"][1], flat)["galleries"]["fx_d2"]
    assert w["box"] == (523, 58, 302, 531, 63, 306)


# Without it the command model could pass everything by matching nothing: the vanilla selector box is [x, x+dx+1),
# strict, so a player standing exactly against the box's face is out and one 0.01 into it is in.
def test_auditor_selector_semantics_are_the_vanilla_ones():
    s = A.Sim({}, [], lambda c: "minecraft:air")
    args = {"x": "10", "y": "0", "z": "10", "dx": "2", "dy": "1", "dz": "0"}
    s.entities = [A.player(13.3, 0, 10.5)]          # box 13.0..13.6: touches x = 13, the volume ends at 13
    assert not s.select("a", args)
    s.entities = [A.player(13.29, 0, 10.5)]
    assert s.select("a", args)
    s.entities = [A.player(11, 0, 10.5, kind="mob", typ="cobblemon:pokemon")]
    assert not s.select("a", args) and s.select("e", dict(args, type="cobblemon:pokemon"))


# ------------------------------------------------------------------ the pack the builder emits, audited

# Without it a restore could write outside its gallery, over a player's block, without the guard, or on a chunk that
# is not loaded, and nothing would say so: the static audit over the fixture's pack is clean.
def test_restore_writes_exactly_the_gallery_behind_a_full_guard(fx):
    spec, fns, tag = fx
    assert A.static_problems(spec, fns, tag, flat) == []


# Without it a restore could bury a player or a Pokemon, standing, sneaking, crawling or asleep, in a gallery, its
# shell or the hall beside it, or run with a chunk unloaded, or restore twice in a period across a restart or a walk
# out and back: the command model runs the fixture's pack and every case holds (each with a control that does restore).
def test_nobody_is_buried_and_the_clock_holds(fx):
    spec, fns, tag = fx
    assert A.run_problems(spec, fns, tag, flat) == []


# Without it a player's chest left in a mined-out gallery would be deleted by the refill (ECONOMY_OVERHAUL.md 3.1:
# "a player's chest survives"): the restore runs with a chest in a body cell and the chest is still there.
def test_a_chest_left_in_a_gallery_survives_the_restore(fx):
    spec, fns, tag = fx
    assert _chest_survives(spec, fns, tag)


def _chest_survives(spec, fns, tag):
    cave = spec["caves"][0]
    ex = A.expected(spec, cave, flat)
    e = ex["galleries"]["fx_g1"]
    s = A.due_only(A.Built(spec, fns, tag, flat).fresh(), spec, "fx_g1")
    A.mine_out(s, e["body"])
    chest = sorted(e["body"])[len(e["body"]) // 2]
    s.blocks[chest] = "minecraft:chest[facing=north]"
    s.entities.append(A.visitor_for(spec, ex, e))
    s.tick(spec["restore"]["every_ticks"])
    restored = {w[0] for w in s.writes} & (e["body"] | e["shell"])
    assert restored, "the control: no restore ran, so the chest proves nothing"
    return A.base(s.blocks[chest]) == "minecraft:chest"


# Without it the cave could be unwalkable (a step over one block, a stair missing, the hall shut): from outside the
# mouth, in 1-block steps either way, the hall beside every gallery of both fixture caves is reached.
def test_every_gallery_is_walkable_from_the_mouth(fx):
    spec, fns, tag = fx
    assert A.walk_problems(spec, fns, flat) == []


# Without it the bank's view of a reset could drift from the design (ECONOMY_OVERHAUL.md 3.3: $158 early, $231 deep
# per reset; 9 diamonds an hour server-wide from Fossick's 8 galleries), priced from data/bank.json.
def test_yield_per_reset_matches_the_design_table():
    eco = A.economy(A.load())
    assert eco["cave_old_mine"]["per_reset"] == 158 and eco["cave_fossick"]["per_reset"] == 231
    assert eco["cave_fossick"]["diamonds_per_hour_server"] == 9
    assert not eco["cave_old_mine"]["unpriced"] and not eco["cave_fossick"]["unpriced"]


# ------------------------------------------------------------------ mutations of the generator: the audit bites

GUARD = ('"guard": [bounds[0] - 1, bounds[1] - 1, bounds[2] - 1, bounds[3] + 1, bounds[4] + 1, bounds[5] + 1]')
MUTATIONS = {
    # the guard box shrunk by one: it is the writes themselves, not the writes grown by one
    "guard_shrunk_by_one": (GUARD, '"guard": [bounds[0], bounds[1], bounds[2], bounds[3], bounds[4], bounds[5]]'),
    # the guard box shrunk by two: it misses the shell, and a player in the shell is buried
    "guard_shrunk_by_two": (GUARD, '"guard": [bounds[0] + 1, bounds[1] + 1, bounds[2] + 1, bounds[3] - 1, bounds[4] - 1, bounds[5] - 1]'),
    # a container in the restore's tag
    "container_in_tag": ('out = list(M.load()["restore"]["resettable"])',
                         'out = list(M.load()["restore"]["resettable"]) + ["minecraft:chest"]'),
    # one loaded corner dropped (the far x, far z one)
    "loaded_corner_dropped": ('"execute unless loaded %d %d %d run return 0" % (gx1, gy0, gz1),', ''),
    # the Pokemon guard dropped
    "pokemon_guard_dropped": ('"execute if entity @e[type=cobblemon:pokemon,%s] run return 0" % vol,', ''),
    # the restore unfiltered (a plain fill over whatever stands there)
    "restore_unfiltered": ('M.column_runs(formation(spec, cave, g), tag)', 'M.column_runs(formation(spec, cave, g))'),
    # a restart re-arms every gallery (load sets the clock whether or not it is set)
    "load_rearms_the_clock": ('"execute unless score #%s %s matches -2147483648.. run scoreboard players set #%s %s %d"\n'
                              '                         % (gid, LAST, gid, LAST, -int(g["gallery"]["offset_ticks"])))',
                              '"execute if score #%s %s matches -2147483648.. run scoreboard players set #%s %s %d"\n'
                              '                         % (gid, LAST, gid, LAST, -int(g["gallery"]["offset_ticks"])))'),
    # the incline twice as steep: two-block steps
    "incline_two_block_steps": ("ft = y0 if d == 0 else y0 - d + 1", "ft = y0 if d == 0 else y0 - 2 * d + 2"),
}


def _red(name, spec):
    fns, tag = pack(spec, mutation=MUTATIONS[name])
    st = A.static_problems(spec, fns, tag, flat)
    return fns, tag, st


# Without it the static guard check could pass a guard that is only the writes: shrinking the generator's guard box by
# one (data untouched) turns it red, naming the gallery.
def test_mutation_guard_shrunk_by_one_is_caught():
    spec = fixture_spec()
    _f, _t, st = _red("guard_shrunk_by_one", spec)
    assert any("guard over the gallery grown by one" in p for p in st), st


# Without it the command model could miss a burial: a guard shrunk by two leaves the shell outside it, and a player
# in the shell is written over.
def test_mutation_guard_shrunk_by_two_buries_someone():
    spec = fixture_spec()
    fns, tag, st = _red("guard_shrunk_by_two", spec)
    rp = A.run_problems(spec, fns, tag, flat, only={"fx_g1"})
    assert any("written over (buried)" in p or "still got a restore" in p for p in rp), rp


# Without it a container could join the tag: the static check names it, and the chest left in a gallery is gone.
def test_mutation_container_in_tag_is_caught():
    spec = fixture_spec()
    fns, tag, st = _red("container_in_tag", spec)
    assert any("minecraft:chest" in p for p in st), st
    assert not _chest_survives(spec, fns, tag)


# Without it the loaded check could cover three corners of four: the static check names the untested chunk, and the
# command model restores with that chunk unloaded.
def test_mutation_loaded_corner_dropped_is_caught():
    spec = fixture_spec()
    fns, tag, st = _red("loaded_corner_dropped", spec)
    assert any("never tested `unless loaded`" in p for p in st), st
    rp = A.run_problems(spec, fns, tag, flat, only={"fx_g1"})
    assert any("unloaded" in p for p in rp), rp


@pytest.mark.parametrize("name,needle", [
    ("pokemon_guard_dropped", "[type=cobblemon:pokemon] guard"),
    ("restore_unfiltered", "an unfiltered or unexpected restore write"),
])
# Without it a dropped Pokemon guard or an unfiltered restore would pass: each, made in the generator, is named.
def test_mutation_guard_and_filter_edits_are_caught(name, needle):
    spec = fixture_spec()
    _f, _t, st = _red(name, spec)
    assert any(needle in p for p in st), st


# Without it the clock scenario could pass on a pack whose restart re-arms the gallery: the restart run restores
# again inside the period.
def test_mutation_load_rearming_the_clock_is_caught():
    spec = fixture_spec()
    fns, tag = pack(spec, mutation=MUTATIONS["load_rearms_the_clock"])
    with pytest.raises(AssertionError, match="under the period"):
        gallery_restart((fns, tag))


# Without it the walk could pass on any cave: an incline of two-block steps is not walked.
def test_mutation_two_block_steps_are_not_walkable():
    spec = fixture_spec()
    fns, tag = pack(spec, mutation=MUTATIONS["incline_two_block_steps"])
    assert A.walk_problems(spec, fns, flat), "a two-block incline was walked"


# ------------------------------------------------------------------ the gate-clock scenarios (contract C14)

def _clock(fns, action):
    spec = fixture_spec()
    fns, tag = fns if fns is not None else pack(spec)
    built = A.Built(spec, fns, tag, flat)
    cave = spec["caves"][0]
    ts = A.clock_run(spec, built, flat, cave, "fx_g1", action)
    period = spec["restore"]["period_ticks"]
    assert len(ts) >= 2, "%s: %d restores of fx_g1 in 2.6 periods: nothing ran" % (action, len(ts))
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    assert min(gaps) >= period, "%s: fx_g1 restored twice %d ticks apart, under the period %d" % (action, min(gaps), period)


def gallery_restart(fns=None):
    """A restart (minecraft:load) every pass never restores a mined-out gallery twice inside its period."""
    _clock(fns, "restart")


def gallery_reapproach(fns=None):
    """Walking out of the cave's approach box and back every pass never restores a gallery twice inside its period."""
    _clock(fns, "reapproach")


# ------------------------------------------------------------------ the real caves, on the canonical heightmap

@pytest.fixture(scope="module")
def real():
    try:
        import ground as G
        g = A.cached(G.Ground())
        g(1347, 4080)
    except Exception as exc:  # noqa: BLE001
        pytest.skip("NOT_EXECUTED: the canonical heightmap is not readable here (%s)" % exc)
    spec = A.load()
    fns, tag = pack(spec, real_ground=True)
    return spec, fns, tag, g


# Without it the real caves, sited on the heightmap, could restore outside their galleries or without the full guard:
# the static audit is clean on the pack the builder makes from data/mining_caves.json and the heightmap.
def test_real_caves_restore_exactly_their_galleries(real):
    spec, fns, tag, g = real
    assert A.static_problems(spec, fns, tag, g) == []


# Without it a real cave could be sited where its mouth cannot be climbed into or its incline breaks: from outside each
# mouth, on the heightmap, every gallery's hall is reached in 1-block steps (and so is the way back).
def test_real_caves_are_walkable_from_their_mouths(real):
    spec, fns, tag, g = real
    assert A.walk_problems(spec, fns, g) == []
