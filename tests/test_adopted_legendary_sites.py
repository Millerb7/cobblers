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
  the ceiling    the RUNTIME's build top, read from the dimension type our pack ships
                 (`modpack/datapacks/cobblers_height/.../dimension_type/overworld.json`: min_y + height - 1,
                 y575), and `data/world.json` `sea_level` (62). `vertical.max_y` (310) is NOT a ceiling for
                 built blocks: it caps authored terrain only (world.json measured_ceiling_note), and a template
                 pasted on that terrain may rise above it.
  the rule       `data/portals.json` `rules.min_from_legendary_mouth`.

ON PROVING THESE BITE. The repository's standard is "mutate the GENERATOR, not the record", because a
record-side mutation normally moves the expectation and the output together and so proves nothing. THERE
IS NO GENERATOR HERE: the record IS the artifact, and the heightmap is the independent side. So a
mutation that perturbs a COPY of the record in memory and asserts the check goes red is the right proof,
and it is a real proof rather than a shared derivation precisely because the expectation comes from the
heightmap, which a mutated record cannot move. The file on disk is never written: every mutation test
works on `copy.deepcopy`.

CHANGED 2026-10-02, BY A DIFFERENT AUTHOR THAN THE ONE WHO WROTE THIS FILE (the agent that moved Articuno's
tower to the summit, disclosed here). This file used to hold every site under BOTH `vertical.max_y` 310 and
a hard-coded vanilla build limit of 320. Neither is this runtime's: `cobblers_height` ships an overworld
dimension type of min_y -64, height 640, so the highest buildable layer is y575 (docs/STATE.md "World
facts"), and max_y is a terrain line. The same wrong 320 is what refused the summit for Articuno on
2026-10-01. So the ceiling is now READ from that dimension type file, max_y no longer bounds built blocks,
and the two recording conventions this file used to tolerate are gone -- the record was rewritten to one:

  `top_y`           the top OCCUPIED layer, `y + height - 1`, exactly, for all four sites. Over- and
                    understating are both failures now: there is one convention, not a safe direction.
  `ceiling_margin`  `runtime_top - top_y`, exactly, for all four sites. `max_y_margin` is a second
                    convention and is refused wherever it appears.

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
  * the `why_a_sibling_of_legendaries_json` block still says THREE sites. Articuno joined later.
    `test_record_ceiling_is_the_runtime_top` pins the numbers in the `ceiling` block; the stale count is a
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
MAX_Y = WORLD["vertical"]["max_y"]          # authored TERRAIN only; never a ceiling for a built block
SEA_LEVEL = WORLD["vertical"]["sea_level"]

# The runtime's overworld build top, read from the dimension type our pack ships rather than typed in: the
# old hard-coded 320 was vanilla's, and it refused the summit for Articuno on 2026-10-01.
DIMENSION = ROOT / "modpack" / "datapacks" / "cobblers_height" / "data" / "minecraft" / "dimension_type" / "overworld.json"


def runtime_top(path=DIMENSION):
    dim = json.loads(Path(path).read_text(encoding="utf-8"))
    return dim["min_y"] + dim["height"] - 1


RUNTIME_TOP = runtime_top()

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


def ceiling_problems(site, top=None):
    """[problem] in the vertical arithmetic: the occupied top against the runtime's build top, and the margin.

    `top` defaults to RUNTIME_TOP; it is a parameter so a test can prove the check bites on the ceiling it is
    given (the old 320) rather than on anything the record says."""
    top = RUNTIME_TOP if top is None else top
    p = site["placement"]
    height = template_size(site)[1]
    occupied_top = p["y"] + height - 1
    bad = []
    if occupied_top > top:
        bad.append("the top occupied layer is y%d, over the runtime build limit y%d" % (occupied_top, top))
    if p["top_y"] < occupied_top:
        # the dangerous direction: a top_y below the real top is how a breach of the ceiling hides
        bad.append("top_y %d understates the top occupied layer y%d" % (p["top_y"], occupied_top))
    elif p["top_y"] != occupied_top:
        bad.append("top_y %d is not the top occupied layer y%d (one convention: y + height - 1)"
                   % (p["top_y"], occupied_top))
    if "ceiling_margin" not in p:
        bad.append("placement declares no ceiling_margin")
    elif p["ceiling_margin"] != top - occupied_top:
        bad.append("ceiling_margin %d is not runtime top y%d - top occupied layer y%d = %d"
                   % (p["ceiling_margin"], top, occupied_top, top - occupied_top))
    if "max_y_margin" in p:
        bad.append("max_y_margin is a second margin convention, against a terrain line that is not a ceiling")
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
def test_top_y_is_the_templates_top_and_clears_the_runtime_ceiling(sid):
    # Without it a 74-block template seated high pokes through the build limit and the record still reads
    # fine. The clearance is computed here from y and data/structures.json's height, never read from top_y.
    assert ceiling_problems(SITES[sid]) == []


@pytest.mark.parametrize("sid", IDS)
def test_declared_margin_is_the_runtime_top_minus_the_occupied_top(sid):
    # Without it `ceiling_margin` is a number from the day it was typed. It is covered by
    # ceiling_problems(); this test names the property so a stale margin is not reported as "ceiling".
    site = SITES[sid]
    p = site["placement"]
    assert p["ceiling_margin"] == RUNTIME_TOP - (p["y"] + template_size(site)[1] - 1)
    assert "max_y_margin" not in p


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


def test_record_ceiling_is_the_runtime_top():
    # Without it the record's ceiling block can quote a roof the runtime no longer has -- which it did, as
    # max_y 310 and the vanilla 320, until 2026-10-02 -- and every margin computed from it is silently
    # against the wrong one. The terrain line it also quotes must still be world.json's.
    assert RECORD["ceiling"]["runtime_top_y"] == RUNTIME_TOP
    assert RECORD["ceiling"]["terrain_max_y"] == MAX_Y


def test_the_runtime_top_is_read_from_the_shipped_dimension_type():
    # Without it a change to cobblers_height would silently move every margin. Pinned so that change is
    # loud: re-derive every ceiling_margin in the record when this fails.
    dim = json.loads(DIMENSION.read_text(encoding="utf-8"))
    assert (dim["min_y"], dim["height"]) == (-64, 640), "cobblers_height changed: re-derive every margin"
    assert RUNTIME_TOP == 575


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
    # ceiling_margin. Articuno's template is 74 blocks tall, so y520 puts its top occupied layer at y593.
    # The copy is kept internally consistent (top_y and margin re-derived) so only the ceiling can fail.
    site = copy.deepcopy(SITES["adopted_articuno_shrine"])
    site["placement"]["y"] = 520
    site["placement"]["top_y"] = 520 + template_size(site)[1] - 1
    site["placement"]["ceiling_margin"] = RUNTIME_TOP - site["placement"]["top_y"]
    problems = ceiling_problems(site)
    assert any("build limit" in p for p in problems), problems


def test_the_summit_tower_fails_against_the_vanilla_320_that_refused_it():
    # A mutation of the check's input, not of the record: hand ceiling_problems the old 320 and the summit
    # site (top y383) must go red, so the check is bounded by the ceiling it is given and the summit passes
    # only because this runtime's top is y575.
    problems = ceiling_problems(SITES["adopted_articuno_shrine"], top=320)
    assert any("build limit y320" in p for p in problems), problems


def test_terrain_max_y_is_not_treated_as_a_ceiling_for_built_blocks():
    # The summit tower stands on y310 terrain and rises to y383, over max_y 310. That must pass.
    site = SITES["adopted_articuno_shrine"]
    assert site["placement"]["y"] + template_size(site)[1] - 1 > MAX_Y
    assert ceiling_problems(site) == []


def test_a_second_margin_convention_is_caught():
    site = copy.deepcopy(SITES["adopted_mew_temple"])
    site["placement"]["max_y_margin"] = MAX_Y - site["placement"]["top_y"]
    assert any("max_y_margin" in p for p in ceiling_problems(site))


def test_a_top_y_that_overstates_the_template_is_caught():
    # One convention now: y + height (Articuno's old form) is as wrong as an understatement.
    site = copy.deepcopy(SITES["adopted_zapdos_tower"])
    site["placement"]["top_y"] += 1
    site["placement"]["ceiling_margin"] -= 1
    assert any("not the top occupied layer" in p for p in ceiling_problems(site))


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
