"""tools/tree_birds_audit.py: the independent audit of the `tbird_*` nests, tested three ways.

Written by the test author, not by the session that built tools/tree_birds.py or the audit's subject.

  1. A deterministic SYNTHETIC tree with hand-computed zones: the audit's own zone rule is exercised on a pillar, a
     plate and a gap whose answers can be worked out on paper (the docstrings show the arithmetic), so the audit is
     not only ever run on one surface.
  2. The REAL data: the committed nests pass it (strict and lenient snow; the world tree too).
  3. MUTATION OF THE GENERATOR: tools/tree_birds.py is run with a defect planted in its CODE (a nest offset, a
     `hidden` that always says yes, a target window moved, a MAX_DROP changed, solid logs turned to air) with
     data/ untouched, and the audit must name each one. A record-side edit would move the expectation and the output
     together and prove nothing.

Not covered: that a bird stands in the tree (staging), that Minecraft re-centres a zone the way the audit's rule says
(the rule is the builder's reading of the Cobblemon 1.8.2 jar, relayed: neither the builder's code nor this file
re-reads the bytecode), the 4 Foothill grove elders (no geometry here: reported UNCOVERED), and the plant
mutation `centre_y down-first`, which this audit does NOT catch: for the trees tried, either search order reaches the same
air, so the generator's output is identical (an equivalent mutant, recorded below, not a pass).
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import tree_birds_audit as A  # noqa: E402

LOG = "minecraft:oak_log"
LEAVES = "minecraft:oak_leaves"
TREES = ["elder_viltri_plateau_1", "sapling_scorched_great_crater"]     # an elder (oak) and a themed sapling (basalt)


def make_tree(blocks, ground=100):
    names = dict(blocks)
    return A.Tree("synthetic", "elder", ground, (0, 0), names, {}, "strict")


# ---------------------------------------------------------------------------------------- 1. the synthetic fixture
def pillar(lo, hi, gaps=()):
    return {(0, y, 0): LOG for y in range(lo, hi + 1) if y not in gaps}


# Without it the re-centring rule (the heart of the fault: a buried block's zone is NOT round the block) is untested on
# anything whose answer a person can check. Hand-computed: a log pillar at (0, y, 0) for y 101..120 on ground 100.
# A nest at y 105: the start must be air with a passable block above; y 105..120 are logs, so up-first reaches
# y 121 (air, and 122 air) at k = 16; down, y 100 is the floor (solid). The centre is 121 whatever the nest's own y.
def test_a_buried_nests_zone_is_centred_on_the_air_above_the_pillar_not_on_the_nest():
    t = make_tree(pillar(101, 120))
    assert t.centre_y(0, 105, 0, 64) == 121
    assert t.centre_y(0, 101, 0, 64) == 121
    assert t.centre_y(0, 120, 0, 64) == 121
    # the area is dropped when the nearest air is farther than the correction allows (k = 16 > 15)
    assert t.centre_y(0, 105, 0, 15) is None


# Without it the zone's cells are not what Cobblemon's `grounded` position takes: a SOLID cell with a non-solid block above
# it, anywhere in the (2r+1)^3 box (limb tops, plates), not only the column top. Hand-computed: the pillar top (0, 120, 0)
# plus a 5x5 leaf plate at y 110 minus the pillar's own column = 24 standing cells; the box is y 105..137 (base 121 - 16),
# so the plate (110) and the top (120) are in it; the pillar's middle cells have solid above and are not.
def test_zone_cells_are_the_standing_surfaces_in_the_box_and_nothing_else():
    blocks = pillar(101, 120)
    blocks.update({(x, 110, z): LEAVES for x in range(-2, 3) for z in range(-2, 3) if (x, z) != (0, 0)})
    t = make_tree(blocks)
    cy, cells, floor = t.zone(0, 105, 0, 16, 64)
    assert cy == 121 and floor == 0
    assert len(cells) == 25 and (0, 120, 0) in cells and (0, 110, 0) not in cells
    assert sorted(c[1] for c in cells).count(110) == 24
    # the box is the point: a plate at y 104 (below base 105) is outside it
    blocks[(3, 104, 3)] = LEAVES
    assert (3, 104, 3) not in make_tree(blocks).zone(0, 105, 0, 16, 64)[1]


# Without it the search order (UP first at each distance) and "nearest wins" are unchecked. Hand-computed on a pillar with
# air gaps at y 108-109 and y 114-115 (a start needs air at y AND a passable block at y + 1, so a lone air cell at 109,
# with the log at 110 over it, is not one). Nest at y 111: down 108 is k = 3, up 114 is k = 3, a tie: up wins, 114.
# Nest at y 110: down 108 is k = 2 (air at 108, 109), up 114 is k = 4: down wins, 108.
def test_the_nearest_valid_start_wins_and_up_wins_a_tie():
    t = make_tree(pillar(101, 120, gaps=(108, 109, 114, 115)))
    assert t.centre_y(0, 111, 0, 64) == 114
    assert t.centre_y(0, 110, 0, 64) == 108
    assert t.centre_y(0, 111, 0, 2) is None


# Without it a zone that reaches the forest floor goes unreported (birds on the ground, which is what the low nests are for
# avoiding). Hand-computed: pillar y 101..110, nest at 105: centre 111, box base 95 <= ground 100, so every one of the
# 33 x 33 columns whose y 101 is not solid is a floor column: 1089 - 1 (the pillar's own) = 1088.
def test_a_zone_that_reaches_the_ground_counts_its_floor_columns():
    t = make_tree(pillar(101, 110))
    cy, cells, floor = t.zone(0, 105, 0, 16, 64)
    assert (cy, floor) == (111, 1088)
    assert make_tree(pillar(101, 150)).zone(0, 120, 0, 16, 64)[2] == 0


def _cube():
    return {(x, y, z): LOG for x in (-1, 0, 1) for y in (101, 102, 103) for z in (-1, 0, 1)}


def _rec(x, y, z, mimic=LOG):
    return {"id": "tbird_synthetic_low", "position": {"x": x, "y": y, "z": z}, "mimic": mimic}


# Without it the "in the tree's own wood, hidden" check cannot tell wood from air, a surface cell, or the wrong mimic:
# the 3 x 3 x 3 cube hides only its centre; (1, 102, 0) has air on one face; (5, 102, 5) is open air; a leaf mimic on a
# log cell would change what a player sees.
@pytest.mark.parametrize("pos,mimic,needle", [
    ((0, 102, 0), LOG, None),
    ((1, 102, 0), LOG, "not hidden"),
    ((5, 102, 5), LOG, "OPEN AIR"),
    ((0, 102, 0), LEAVES, "mimic"),
])
def test_the_wood_check_accepts_a_buried_log_and_names_air_a_surface_and_a_wrong_mimic(pos, mimic, needle):
    problems = []
    ok = A._wood_checks(make_tree(_cube()), _rec(*pos, mimic=mimic), problems)
    if needle is None:
        assert ok and not problems
    else:
        assert any(needle in p for p in problems), problems


# Without it snow's uncertain solidity (8 layers strict, 3 or more lenient) is silently one reading: a layer-5 snow block
# is air under strict and standable under lenient, and an unlisted block is refused, never guessed.
def test_snow_is_read_both_ways_and_an_unlisted_block_is_refused():
    assert not A.block_solid("minecraft:snow", {"layers": "5"}, "strict")
    assert A.block_solid("minecraft:snow", {"layers": "5"}, "lenient")
    assert A.block_solid("minecraft:snow", {"layers": "8"}, "strict")
    assert not A.block_solid("minecraft:cocoa", {}, "strict")
    with pytest.raises(ValueError):
        A.block_solid("minecraft:some_new_block", {}, "strict")


# Without it the audit quietly starts importing the builder's geometry and stops being independent of it (the 2026-09-30
# portals audit shared its builder's derivation and agreed with it about a 219,737-column hole).
def test_the_audit_imports_none_of_the_builders_modules():
    tree = ast.parse((ROOT / "tools" / "tree_birds_audit.py").read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add(n.module)
    assert not mods & {"tree_birds", "habitat_spawn_model", "tree_geometry"}, mods


# ----------------------------------------------------------------------------------------------- 2. the real data
# Without it a committed nest in open air, off its limb, in a structure's footprint, on a path, with a zone that reaches the
# floor or is empty, or a pool/record/designer disagreement goes live unnoticed: the 124 placed storey nests are audited
# against the templates and the designer's file.
@pytest.mark.parametrize("snow", ["strict", "lenient"])
def test_the_committed_storey_nests_pass_the_independent_audit(snow):
    res = A.audit(world_tree=False, snow=snow)
    assert not res["problems"], res["problems"][:5]
    assert len(res["stats"]["cells"]) == 124, len(res["stats"]["cells"])
    assert sorted(res["uncovered"]) == sorted(A.GROVE_ELDERS)


# Without it the world tree's 19 planned nests (hidden log cells on its limbs and leaf cells in the canopy) go unchecked:
# generated from tools/tree_grove (the tree itself), seated by tools/world_tree.CENTRE/GROUND, against the generator's own
# storey heights. Takes about 15 s (it builds 1.26 million blocks).
def test_the_world_trees_nests_pass_the_independent_audit():
    res = A.audit(trees={A.WORLD_TREE}, world_tree=True)
    assert not res["problems"], res["problems"][:5]
    assert len(res["stats"]["cells"]) == 19


# Without it an unplaced tree could pass by having no records at all: a requested tree with no tbird record is a problem.
def test_a_tree_with_no_storey_nests_is_a_problem_not_a_pass():
    doc = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))
    doc["blocks"] = [b for b in doc["blocks"] if not b["id"].startswith("tbird_" + TREES[0] + "_")]
    res = A.audit(habitats=doc, trees={TREES[0]}, world_tree=False)
    assert any("no tbird record" in p for p in res["problems"]), res["problems"]


# ------------------------------------------------------------------------------- 3. mutation of the GENERATOR
@pytest.fixture(scope="module")
def builder():
    import tree_birds as B
    import tree_geometry as TG
    import habitat_spawn_model as M
    return B, TG, M


def _generated(builder, tids):
    """The tbird records the builder's CODE produces for `tids`, as tools/tree_birds.py plan/merge would."""
    B, TG, _M = builder
    pools = B.trees_and_pools()
    recs = []
    for tid in tids:
        info = pools[tid]
        base = next(n for n in info["nests"] if n["id"] == tid or n["id"].endswith("_low"))
        t = TG.load(tid, (base["position"]["x"], base["position"]["z"]))
        new = B.plan_small(t, info)
        doc = {"trees": {tid: {"kind": t["kind"], "ground": t["ground"],
                               "per_activation": base["activated"]["max_spawns_per_activation"], "new": new}}}
        recs += B.records(doc)
    return recs


def _audit_generated(builder, tids=TREES):
    doc = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))
    doc["blocks"] = [b for b in doc["blocks"] if not any(b["id"].startswith("tbird_%s_" % t) for t in tids)] \
        + _generated(builder, tids)
    return A.audit(habitats=doc, trees=set(tids), world_tree=False)


# Without it every mutation below could "fail" for a reason that is not the mutation (a generator that no longer
# reproduces the committed nests, or an audit that always objects): the unmutated generator's output passes the audit and
# is the committed data.
def test_control_the_unmutated_generator_passes_the_audit_and_is_the_committed_data(builder):
    assert not _audit_generated(builder)["problems"]
    committed = {b["id"]: b["position"] for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(
        encoding="utf-8"))["blocks"] if b["id"].startswith("tbird_")}
    for r in _generated(builder, TREES):
        assert committed[r["id"]] == r["position"], r["id"]


def _offset(B, M):
    real = B.nest_entry

    def nest_entry(t, band, pick):
        e = real(t, band, pick)
        e["position"] = dict(e["position"], x=e["position"]["x"] + 7)      # the nest lands 7 off its limb
        return e
    return B, "nest_entry", nest_entry


MUTATIONS = {
    # a nest offset bug: the record is 7 blocks from the cell the generator checked
    "offset_7": _offset,
    # `hidden` always says yes: nests on a limb's surface, visible, with air on a face
    "hidden_always_true": lambda B, M: (B, "hidden", lambda *a, **k: True),
    # both bands aimed at the second storey: the low nest is no longer low (and shares its cell with the mid nest)
    "low_aimed_at_second_storey": lambda B, M: (B, "SMALL_TARGETS", (("low", 41, 47), ("mid", 41, 47))),
    # the low band aimed into the crown's limbs: birds high, not low
    "low_aimed_into_the_crown": lambda B, M: (B, "SMALL_TARGETS", (("low", 56, 62), ("mid", 41, 47))),
    # MAX_DROP 40: a nest allowed deep in a thick trunk (one themed tree then loses its hiding)
    "max_drop_40": lambda B, M: (B, "MAX_DROP", 40),
    # MAX_DROP 0: no cell qualifies, so no nest is written at all
    "max_drop_0": lambda B, M: (B, "MAX_DROP", 0),
    # solid_name says logs are air: the generator finds no wood to seat a nest in
    "logs_are_air": lambda B, M: (M, "solid_name", lambda n, p=None: not n.endswith("_log")),
}


# Without it the audit has never been shown to bite: each plant a DEFECT IN THE GENERATOR'S CODE (data/ untouched) and the
# audit must object. A mutation that edited the records would move expectation and output together and prove nothing.
@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_defect_planted_in_the_generator_is_named_by_the_audit(name, builder, monkeypatch):
    B, _TG, M = builder
    mod, attr, value = MUTATIONS[name](B, M)
    monkeypatch.setattr(mod, attr, value)
    res = _audit_generated(builder)
    assert res["problems"], "mutation %s survived: the audit reported nothing" % name
