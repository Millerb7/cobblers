"""`data/adopted_legendary_sites.json` held against the heightmap, `data/structures.json` and the portal rule.

Written by the test author. Nothing in the repository read this file before: it is not in
`tests/test_pinned_ground_is_the_heightmap.py`'s `SWEPT` list (that sweep finds records carrying `x`, `z`
and `ground_y`; these carry `corner` and a `ground` block, so it never saw them), no generator emits it,
and no entry in `data/placements.json` names any of its four sites.

WHAT BREAKS WITHOUT IT. The record is four adopted Cobbleverse templates, each a measured coordinate plus
the exact raw `/place template` line a human will copy. Every y, every min/max/median/mode and every
cut/fill count in it was measured ONCE, by hand, off the canonical heightmap. That is the same closed
loop that put four world trees in open air over the ocean on 2026-10-01: `data/elder_trees.json`, its doc
table and its site file all agreed with each other, and none of them asked the terrain after the water
pass drowned the Jungle Isle. This file already carries one scar from that pass -- Mew's temple was
re-sited because its researched coordinate (5160, 7463) measures y61 against a sea level of y62 -- so the
heightmap has moved under this record's subject matter once already.

THE INDEPENDENT SIDES, none of them this record:

  the terrain    `tools/ground.py`, the canonical heightmap, ROUNDED (CLAUDE.md "Ground comes from the
                 heightmap, never from a world"). Every ground, cut and fill expectation here is
                 re-measured over the footprint the record's own `corner` and `size` imply. No
                 expectation is ever taken from the record's `ground` block.
  the templates  `data/structures.json` `footprint`, for each template's x/height/z.
  the ceilings   `data/world.json` `vertical.max_y` (310) and `sea_level` (62), and Minecraft 1.21.1's
                 build limit of 320.
  the rule       `data/portals.json` `rules.min_from_legendary_mouth`.

ON PROVING THESE BITE. The repository's standard is "mutate the GENERATOR, not the record", because a
record-side mutation normally moves the expectation and the output together and so proves nothing. THERE
IS NO GENERATOR HERE: the record IS the artifact, and the heightmap is the independent side. So a
mutation that perturbs a COPY of the record in memory and asserts the check goes red is the right proof,
and it is a real proof rather than a shared derivation precisely because the expectation comes from the
heightmap, which a mutated record cannot move. The file on disk is never written: every mutation test
works on `copy.deepcopy`.

TWO RECORDING INCONSISTENCIES, found by these tests and NOT fixed here (a test author does not edit
`data/`; see the report):

  `top_y`           three sites record the topmost OCCUPIED layer (`y + height - 1`: Mew 142+25-1=166,
                    Crown 109+24-1=132, Zapdos 74+66-1=139); `adopted_articuno_shrine` records
                    `y + height` (151+74=225, where the top occupied layer is y224). Both are safe --
                    Articuno's is the conservative direction -- so `test_top_y_is_the_templates_top`
                    accepts either and asserts the direction that matters: `top_y` may never UNDERSTATE
                    the occupied top, because an understated `top_y` is how a ceiling breach would hide.
                    The hard clearance check uses `y + height - 1` computed here and allows no slack.
  `ceiling_margin`  Mew, Crown and Zapdos measure it against `max_y` 310; Articuno measures it against
                    320 and adds `max_y_margin` for 310. So the field means two different things in one
                    file. `test_declared_margins_are_arithmetic` therefore asserts that each declared
                    margin resolves EXACTLY onto one of the two real, externally defined ceilings -- not
                    a tolerance, a disjunction over two constants that come from `data/world.json` and
                    the game. A margin computed from any third number, or left stale when `y` or
                    `max_y` moves, lands on neither and fails.

ALSO FIXED HERE, a cross-system hole the record asks for by name: `tools/portals.py` `clearances()` reads
`data/legendaries.json` `encounters` for its `min_from_legendary_mouth` check (tools/portals.py:345-348)
and CANNOT SEE this file, so a portal could be sited on top of an adopted site. The record says so and
says the 120 blocks is "measured here, not enforced anywhere". `test_every_site_clears_the_portal_rule`
enforces it, from the footprint EDGE (the conservative measure) rather than from the centre.

NOT COVERED, by any of it. Validity is not behaviour (`.claude/rules/testing.md`):

  * whether `/place template` puts these four templates down at all, or what they contain. No `.nbt` is
    read anywhere here and none is in the repository (COBBLEVERSE-DP-v31.zip is gitignored,
    no-redistribution). `size` is believed from `data/structures.json`; if that footprint string is
    wrong, every y, top and margin here is wrong with it and these tests agree with the error.
  * whether the `lumymon:*_altar` and the command chain inside a template do anything. That is
    EXP-LEG-ALTAR, an experiment, not pytest.
  * whether the terrain UNDER the paste is dressed. The tests re-derive how many blocks of cut and fill
    each site needs; nothing here places one.
  * the record's prose. Several of its distances are measured from the footprint CENTRE and read as if
    they were clearances: "395" to the `sky_far_reach` portal is 397 centre-to-centre and 378 from the
    footprint edge, and Zapdos' "63 blocks" to the nearest sub-sea-level column is 63.1 from the centre
    and 45.1 from the edge. The conclusions hold either way; the numbers are not interchangeable and no
    test asserts the prose.
  * the `ceiling` and `why_a_sibling_of_legendaries_json` blocks still say THREE sites and name Zapdos as
    the tallest top. Articuno joined later and is both the fourth and the tallest (y225 against y139).
    `test_record_ceiling_max_y_is_world_json` pins the one number in that block; the stale counts are a
    finding, not a thing to assert.
  * anything about `data/placements.json`. These sites are deliberately absent from it until a paste is
    approved, so no scheduling, demolition or audit tool sees them -- which is exactly why this file is
    the kind of record that can rot unnoticed.
"""
from __future__ import annotations

import copy
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

RECORD = json.loads((ROOT / "data" / "adopted_legendary_sites.json").read_text(encoding="utf-8"))
SITES = {s["id"]: s for s in RECORD["sites"]}
IDS = tuple(sorted(SITES))

WORLD = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
MAX_Y = WORLD["vertical"]["max_y"]
SEA_LEVEL = WORLD["vertical"]["sea_level"]

# Minecraft 1.21.1's overworld build limit. Not ours to configure and not in data/world.json: the world's
# own max_y (310) is the tighter, authored ceiling and this is the one the game enforces.
BUILD_CEILING = 320

# /place template's own argument vocabulary (the command form data/adopted_legendary_sites.json
# `placement_method.command` declares). A rotation outside this list is a command that will not run.
ROTATIONS = ("none", "clockwise_90", "180", "counterclockwise_90")
MIRRORS = ("none", "left_right", "front_back")

STRUCTURES = {s["id"]: s for s in
              json.loads((ROOT / "data" / "structures.json").read_text(encoding="utf-8"))["structures"]}


@pytest.fixture(scope="module")
def ground():
    import ground as G
    from terrain import TerrainUnavailable
    try:
        return G.load()
    except TerrainUnavailable as e:
        # The one error that means "this machine has no heightmap", raised by terrain.load for a missing
        # COBBLERS_SOURCE_ROOT or a root without the image. Never a bare except and never BaseException:
        # a bug inside G.load() must fail this module, not quietly skip every site in it
        # (tests/test_no_swallowed_crashes.py names this line).
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])


# ------------------------------------------------------------------------------------- the independent side


def footprint(site):
    """The inclusive (x0, z0, x1, z1) box the record's own `corner` and `size` imply."""
    x0, z0 = site["placement"]["corner"]
    sx, _, sz = site["size"]
    return x0, z0, x0 + sx - 1, z0 + sz - 1


def measure(g, x0, z0, x1, z1):
    """The ground stats of a box, from the heightmap alone. Never reads the record."""
    import numpy as np
    b = g.box(x0, z0, x1, z1).ravel()
    counts = Counter(int(v) for v in b.tolist())
    top = max(counts.values())
    mode = min(v for v, c in counts.items() if c == top)  # ties resolve low, so the answer is one number
    return {"min": int(b.min()), "max": int(b.max()), "median": float(np.median(b)), "mode": mode,
            "mode_columns": top, "columns": int(b.size), "spread": int(b.max() - b.min()),
            "heights": b}


def cut_and_fill(heights, y):
    """(cut blocks, cut columns, fill blocks, fill columns) for a bottom layer at y."""
    import numpy as np
    return (int(np.clip(heights - y, 0, None).sum()), int((heights > y).sum()),
            int(np.clip(y - heights, 0, None).sum()), int((heights < y).sum()))


def template_size(site):
    """(x, height, z) from data/structures.json's footprint string -- the record's declared source."""
    s = STRUCTURES[site["template"]]
    return tuple(int(n) for n in re.match(r"^(\d+)x(\d+)x(\d+)", s["footprint"]).groups())


# ------------------------------------------------------------------- checks as functions, so they can be mutated


def ground_problems(site, g):
    """[problem] where the record's `ground` and `displaces` blocks disagree with the heightmap."""
    x0, z0, x1, z1 = footprint(site)
    m = measure(g, x0, z0, x1, z1)
    rec = site["ground"]
    bad = []
    for key in ("min", "max", "median", "mode", "mode_columns", "columns", "spread"):
        if key in rec and float(rec[key]) != float(m[key]):
            bad.append("ground.%s is %s, the heightmap says %s" % (key, rec[key], m[key]))
    if not {"min", "max", "columns"} <= set(rec):
        bad.append("ground declares no min/max/columns, so nothing about this footprint is pinned")
    cut, cut_cols, fill, fill_cols = cut_and_fill(m["heights"], site["placement"]["y"])
    d = site["displaces"]
    for key, got in (("cut_blocks", cut), ("cut_columns", cut_cols),
                     ("fill_blocks", fill), ("fill_columns", fill_cols)):
        if key in d and d[key] != got:
            bad.append("displaces.%s is %s, the heightmap says %s" % (key, d[key], got))
    for key in ("cut_blocks", "fill_blocks"):
        if key not in d:
            bad.append("displaces declares no %s" % key)
    return bad


def ceiling_problems(site):
    """[problem] in the vertical arithmetic: the occupied top, both ceilings, and every declared margin."""
    p = site["placement"]
    height = template_size(site)[1]
    occupied_top = p["y"] + height - 1
    bad = []
    if occupied_top > MAX_Y:
        bad.append("the top occupied layer is y%d, over the world's max_y %d" % (occupied_top, MAX_Y))
    if occupied_top > BUILD_CEILING:
        bad.append("the top occupied layer is y%d, over the %d build limit" % (occupied_top, BUILD_CEILING))
    if p["top_y"] < occupied_top:
        # The dangerous direction: a top_y below the real top is how a breach of the ceiling hides.
        bad.append("top_y %d understates the top occupied layer y%d" % (p["top_y"], occupied_top))
    if p["top_y"] > p["y"] + height:
        bad.append("top_y %d is above y + height (%d)" % (p["top_y"], p["y"] + height))
    for key in ("ceiling_margin", "max_y_margin"):
        if key in p and (p[key] + p["top_y"]) not in (MAX_Y, BUILD_CEILING):
            bad.append("%s %d implies a ceiling of y%d, which is neither max_y %d nor the %d limit"
                       % (key, p[key], p[key] + p["top_y"], MAX_Y, BUILD_CEILING))
    if "ceiling_margin" not in p:
        bad.append("placement declares no ceiling_margin")
    return bad


def command_problems(site):
    """[problem] where placement.command disagrees with the fields a reader would trust instead."""
    p = site["placement"]
    want = "/place template %s %d %d %d %s %s" % (
        site["template"], p["corner"][0], p["y"], p["corner"][1], p["rotation"], p["mirror"])
    bad = []
    if p["command"] != want:
        bad.append("command is %r; the fields say %r" % (p["command"], want))
    if p["rotation"] not in ROTATIONS:
        bad.append("rotation %r is not a /place template rotation" % (p["rotation"],))
    if p["mirror"] not in MIRRORS:
        bad.append("mirror %r is not a /place template mirror" % (p["mirror"],))
    if p.get("anchor_mode") != "corner":
        bad.append("anchor_mode is %r, but /place template takes the minimum corner" % (p.get("anchor_mode"),))
    if p.get("y_mode") != "absolute":
        bad.append("y_mode is %r, but the command's y is an absolute bottom layer" % (p.get("y_mode"),))
    return bad


# ------------------------------------------------------------------------------------------------ the terrain


@pytest.mark.slow
@pytest.mark.parametrize("sid", IDS)
def test_ground_block_is_the_heightmap_over_the_named_footprint(sid, ground):
    # Without it the record's hand-measured ground is believed forever: this is the elder-tree check, the
    # one that would have said the Jungle Isle had drowned instead of agreeing with the file next door.
    assert ground_problems(SITES[sid], ground) == []


@pytest.mark.slow
@pytest.mark.parametrize("sid", IDS)
def test_measured_by_names_the_footprint_the_fields_imply(sid, ground):
    # Without it the prose can quote a box that is not the box `corner` + `size` describes, and the
    # numbers would be right about terrain nobody is pasting on.
    site = SITES[sid]
    m = re.search(r"x(\d+)\.\.(\d+),\s*z(\d+)\.\.(\d+)", site["ground"]["measured_by"])
    assert m, "ground.measured_by names no x..x, z..z box: %r" % site["ground"]["measured_by"]
    x0, z0, x1, z1 = footprint(site)
    assert tuple(int(v) for v in m.groups()) == (x0, x1, z0, z1), \
        "ground.measured_by quotes a box the corner and size do not describe"


@pytest.mark.slow
@pytest.mark.parametrize("sid", IDS)
def test_every_footprint_column_stands_above_sea_level(sid, ground):
    # Without it a site the next water pass drowns keeps its old y and the paste hangs over the ocean --
    # which is precisely what happened to the four jungle elders and to Mew's researched coordinate.
    x0, z0, x1, z1 = footprint(SITES[sid])
    m = measure(ground, x0, z0, x1, z1)
    assert m["min"] > SEA_LEVEL, "ground as low as y%d against sea level y%d" % (m["min"], SEA_LEVEL)


@pytest.mark.slow
@pytest.mark.parametrize("sid", IDS)
def test_y_is_the_least_disturbing_seat_in_the_measured_range(sid, ground):
    # Without it nothing connects `y` to the terrain at all. This is the rule the record argues for itself
    # site by site ("zero cut and zero fill", "a cut of one layer disappears under the template's own
    # floor", "the balance point of the whole column") stated once, and derived from the heightmap: the
    # bottom layer sits at the y that moves the fewest blocks of ground. All four sites are at that y, and
    # uniquely so -- a seat chosen for any other reason has to be argued for in the record, not assumed.
    site = SITES[sid]
    x0, z0, x1, z1 = footprint(site)
    m = measure(ground, x0, z0, x1, z1)
    cost = {}
    for y in range(m["min"], m["max"] + 1):
        cut, _, fill, _ = cut_and_fill(m["heights"], y)
        cost[y] = cut + fill
    best = min(cost.values())
    assert m["min"] <= site["placement"]["y"] <= m["max"], \
        "y%d is outside the measured ground y%d..y%d: the paste floats or is buried whole" \
        % (site["placement"]["y"], m["min"], m["max"])
    assert [y for y, c in cost.items() if c == best] == [site["placement"]["y"]], \
        "y%d costs %d blocks of cut+fill; the cheapest seat is %s" \
        % (site["placement"]["y"], cost[site["placement"]["y"]],
           {y: c for y, c in cost.items() if c == best})


@pytest.mark.slow
@pytest.mark.parametrize("sid", IDS)
def test_transposed_footprint_notes_are_the_heightmaps(sid, ground):
    # Without it the record's "rotation 90 or 270 is still free" notes are unchecked, and the first person
    # to rotate a paste trusts a min/max measured over a box the terrain no longer matches.
    site = SITES[sid]
    sx, _, sz = site["size"]
    found = 0
    for key, note in site["ground"].items():
        m = re.match(r"^transposed_(\d+)x(\d+)$", key)
        if not m:
            continue
        found += 1
        assert tuple(int(v) for v in m.groups()) == (sz, sx), "%s is not %dx%d transposed" % (key, sx, sz)
        x0, z0 = site["placement"]["corner"]
        t = measure(ground, x0, z0, x0 + sz - 1, z0 + sx - 1)
        assert (note["min"], note["max"]) == (t["min"], t["max"]), \
            "%s says %s..%s, the heightmap says %s..%s" % (key, note["min"], note["max"], t["min"], t["max"])
    assert found <= 1, "more than one transposed note: %s" % sorted(site["ground"])


@pytest.mark.slow
def test_the_records_own_ground_probe_is_still_true(ground):
    # Without it the file's self-declared probe ("ground(4528,4416) = 122") is decoration; it is the one
    # line that says WHICH heightmap every number in the record was measured against.
    m = re.search(r"ground\((\d+),\s*(\d+)\)\s*=\s*(\d+)", RECORD["ground_rule"])
    assert m, "ground_rule declares no probe: %r" % RECORD["ground_rule"]
    x, z, y = (int(v) for v in m.groups())
    assert ground(x, z) == y, "the record's probe says y%d at (%d, %d); the heightmap says y%d" \
        % (y, x, z, ground(x, z))


# -------------------------------------------------------------------------------------------- the arithmetic


@pytest.mark.parametrize("sid", IDS)
def test_template_is_a_structure_the_repository_knows(sid):
    # Without it a site can name a template no record describes, and nothing downstream could get its size.
    assert SITES[sid]["template"] in STRUCTURES


@pytest.mark.parametrize("sid", IDS)
def test_size_is_the_structures_file_footprint(sid):
    # Without it `size` drifts from data/structures.json and every top, margin and footprint box built on
    # it is wrong while still agreeing with itself.
    site = SITES[sid]
    assert tuple(site["size"]) == template_size(site)
    assert STRUCTURES[site["template"]]["footprint"].split()[0] in site["size_source"], \
        "size_source does not quote data/structures.json's footprint string"


@pytest.mark.parametrize("sid", IDS)
def test_centre_is_the_corner_plus_half_the_size(sid):
    # Without it the centre -- the point every distance in the record is measured from -- can drift off the
    # footprint it names.
    site = SITES[sid]
    x0, z0 = site["placement"]["corner"]
    sx, _, sz = site["size"]
    assert site["placement"]["centre"] == [x0 + sx // 2, z0 + sz // 2]


@pytest.mark.parametrize("sid", IDS)
def test_top_y_is_the_templates_top_and_clears_both_ceilings(sid):
    # Without it a 74-block template seated high pokes through the build limit and the record still reads
    # fine. See the module docstring: the file has two top_y conventions, so this asserts the direction
    # that matters and computes the hard clearance itself.
    assert ceiling_problems(SITES[sid]) == []


@pytest.mark.parametrize("sid", IDS)
def test_declared_margins_are_arithmetic_against_a_declared_ceiling(sid):
    # Without it `ceiling_margin` is a number from the day it was typed. It is covered by
    # ceiling_problems(); this test names the property so a stale margin is not reported as "ceiling".
    p = SITES[sid]["placement"]
    for key in ("ceiling_margin", "max_y_margin"):
        if key in p:
            assert p[key] + p["top_y"] in (MAX_Y, BUILD_CEILING)


@pytest.mark.parametrize("sid", IDS)
def test_command_text_is_the_fields_beside_it(sid):
    # Without it the one string a human will copy can disagree with the corner, y, rotation and mirror the
    # rest of the record reasons about, and the fields become decoration.
    assert command_problems(SITES[sid]) == []


@pytest.mark.parametrize("sid", IDS)
def test_no_site_is_also_positioned_by_placements_json(sid):
    # Without it the file's own id-authorship promise goes unchecked: the day a site is copied into
    # data/placements.json its `placement` block here must be deleted, or one site has two positions in
    # two files and git will never say so (CLAUDE.md "A clean merge is not a clean union").
    site = SITES[sid]
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
    ids = {q["id"] for q in placements}
    assert site["id"] not in ids
    assert not any(q.get("template") == site["template"] for q in placements), \
        "%s is also placed by data/placements.json, so two files carry a position for it" % site["template"]


def test_record_ceiling_max_y_is_world_json():
    # Without it the record's ceiling block can quote a max_y data/world.json no longer has, and every
    # margin computed from it is silently against the wrong roof.
    assert RECORD["ceiling"]["max_y"] == MAX_Y


# --------------------------------------------------------------------------------------- the cross-system hole


def _portal_clearance():
    """(rule, [(site id, portal id, distance from the footprint EDGE)]) for every site/portal pair."""
    doc = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))
    rule = doc["rules"]["min_from_legendary_mouth"]
    out = []
    for sid in IDS:
        x0, z0, x1, z1 = footprint(SITES[sid])
        for q in doc["portals"]:
            px, pz = q["at"]
            d = math.hypot(max(x0 - px, 0, px - x1), max(z0 - pz, 0, pz - z1))
            out.append((sid, q["id"], d))
    return rule, out


def test_every_site_clears_the_portal_rule_that_nothing_enforces():
    # Without it nothing in the repository holds these sites to `min_from_legendary_mouth`:
    # tools/portals.py reads data/legendaries.json `encounters` for that check and cannot see this file,
    # so a portal moved east could be sited on top of an adopted site and both tools would pass. The
    # record asks for exactly this ("teaches portals.py about this file or declares the clearance in a
    # test"). Measured from the footprint edge, which is stricter than portals.py's point-to-point.
    rule, pairs = _portal_clearance()
    assert [(s, p, round(d)) for s, p, d in pairs if d < rule] == []


def test_no_adopted_site_shares_an_id_or_a_legendary_with_legendaries_json():
    # Without it the same legendary could be authored twice -- a parametric chamber in
    # data/legendaries.json and a pasted template here -- in two files that never conflict in git.
    legend = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))["encounters"]
    theirs = {e["id"] for e in legend} | {str(e.get("species", "")).lower() for e in legend}
    theirs.discard("")
    for sid, site in SITES.items():
        assert sid not in theirs
        mine = set(re.findall(r"[a-z]+", site["legendary"].lower()))
        assert mine & theirs == set(), "%s names a legendary data/legendaries.json also owns: %s" \
            % (sid, sorted(mine & theirs))


def test_no_authored_placement_stands_inside_an_adopted_footprint():
    # Without it a site can be measured onto ground something of ours is already built on, and because
    # these sites are deliberately absent from data/placements.json no placement audit would ever look.
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
    inside = []
    for sid in IDS:
        x0, z0, x1, z1 = footprint(SITES[sid])
        for q in placements:
            pos = q.get("position") or {}
            if "x" in pos and x0 <= pos["x"] <= x1 and z0 <= pos["z"] <= z1:
                inside.append((sid, q["id"]))
    assert inside == []


# ------------------------------------------------------------------------------------------------ mutations
#
# A mutated COPY of the record must be caught. See the module docstring on why a record-side mutation is
# the right proof here and not the usual one: the expectations above come out of the heightmap,
# data/structures.json, data/world.json and data/portals.json, none of which a mutated site dict can move.
# data/adopted_legendary_sites.json is never written.


@pytest.mark.slow
@pytest.mark.parametrize("field,delta", [("min", -1), ("max", 1), ("median", 1), ("mode", 1),
                                         ("columns", -1), ("mode_columns", 1), ("spread", 1)])
def test_a_perturbed_ground_stat_is_caught(field, delta, ground):
    # Proves test_ground_block_is_the_heightmap bites on each stat separately, not just on one of them.
    site = copy.deepcopy(SITES["adopted_crown_cemetery"])
    if field not in site["ground"]:
        pytest.skip("adopted_crown_cemetery declares no ground.%s" % field)
    site["ground"][field] += delta
    assert any(("ground.%s" % field) in p for p in ground_problems(site, ground))


@pytest.mark.slow
@pytest.mark.parametrize("field", ["cut_blocks", "fill_blocks", "cut_columns", "fill_columns"])
def test_a_perturbed_cut_or_fill_count_is_caught(field, ground):
    # Proves the displacement counts are re-derived rather than read back out of the record.
    site = copy.deepcopy(SITES["adopted_zapdos_tower"])
    site["displaces"][field] += 1
    assert any(("displaces.%s" % field) in p for p in ground_problems(site, ground))


@pytest.mark.slow
def test_a_site_moved_onto_different_terrain_is_caught(ground):
    # The elder-tree failure in miniature: the record stays internally perfect and only the terrain under
    # it changes. A ground check that cannot see this is a check of the record against itself.
    site = copy.deepcopy(SITES["adopted_zapdos_tower"])
    site["placement"]["corner"] = [site["placement"]["corner"][0] + 60, site["placement"]["corner"][1] + 60]
    assert ground_problems(site, ground) != []


@pytest.mark.slow
def test_a_drowned_site_is_caught(ground):
    # Mew's researched coordinate (5160, 7463) measures y61 against a sea level of y62: the site the water
    # pass removed. A record re-sited back onto it must fail the sea-level check.
    site = copy.deepcopy(SITES["adopted_mew_temple"])
    site["placement"]["corner"] = [5160, 7463]
    x0, z0, x1, z1 = footprint(site)
    assert measure(ground, x0, z0, x1, z1)["min"] <= SEA_LEVEL


def test_a_structure_raised_through_the_build_limit_is_caught():
    # Proves the ceiling check is arithmetic over the template's real height and not a reading of
    # ceiling_margin. Articuno's template is 74 blocks tall, so y260 puts its top at y333.
    site = copy.deepcopy(SITES["adopted_articuno_shrine"])
    site["placement"]["y"] = 260
    site["placement"]["top_y"] = 260 + template_size(site)[1]
    site["placement"]["ceiling_margin"] = BUILD_CEILING - site["placement"]["top_y"]
    site["placement"]["max_y_margin"] = MAX_Y - site["placement"]["top_y"]
    problems = ceiling_problems(site)
    assert any("build limit" in p for p in problems), problems
    assert any("max_y" in p for p in problems), problems


def test_a_stale_ceiling_margin_is_caught():
    # The margin that was true when it was typed. One block off and it resolves onto no real ceiling.
    site = copy.deepcopy(SITES["adopted_mew_temple"])
    site["placement"]["ceiling_margin"] += 1
    assert any("ceiling_margin" in p for p in ceiling_problems(site))


def test_a_top_y_that_understates_the_template_is_caught():
    # The dangerous direction: a top_y below the real top would let a breach of the ceiling read as safe.
    site = copy.deepcopy(SITES["adopted_zapdos_tower"])
    site["placement"]["top_y"] -= 1
    assert any("understates" in p for p in ceiling_problems(site))


@pytest.mark.parametrize("field,value", [("corner", [1, 2]), ("y", 7), ("rotation", "clockwise_90"),
                                         ("mirror", "front_back"), ("anchor_mode", "centre"),
                                         ("y_mode", "relative")])
def test_a_command_that_no_longer_matches_its_fields_is_caught(field, value):
    # Proves the command is parsed against the fields rather than merely present. Each of these is a real
    # way for the two to part: a re-site, a re-seat, a rotation chosen once the .nbt has been looked at.
    site = copy.deepcopy(SITES["adopted_mew_temple"])
    site["placement"][field] = value
    assert command_problems(site) != []


def test_a_site_sited_on_a_portal_is_caught():
    # Proves the clearance check measures something: the hole it closes is a portal and a site in the same
    # place, which no other tool in the repository can see at once.
    doc = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))
    rule = doc["rules"]["min_from_legendary_mouth"]
    px, pz = doc["portals"][0]["at"]
    site = copy.deepcopy(SITES["adopted_mew_temple"])
    site["placement"]["corner"] = [px - 5, pz - 5]
    x0, z0, x1, z1 = footprint(site)
    d = math.hypot(max(x0 - px, 0, px - x1), max(z0 - pz, 0, pz - z1))
    assert d < rule
