"""`data/adopted_legendary_sites.json` held against the heightmap, `data/structures.json`, `data/placements.json`
and the portal rule.

Written by the test author; reshaped by a second test author on 2026-10-02 when three of the six sites were
SCHEDULED (commit dfad147). No generator emits this record.

TWO KINDS OF SITE, ONE POSITION EACH. The record's own rule is `placement_method.not_in_placements_json`: a
site has ONE author for its position.

  unscheduled   (Articuno, placed by its own step, tools/articuno_tower.py) carries a `placement` block here --
                corner, y, rotation, mirror and the raw `/place template` line -- and NO record in
                data/placements.json names its template. Mew and Zapdos were here until 2026-10-02.
  scheduled     (Crown Cemetery, Dawn tower, Dusk tower; Zapdos, Mew and Moltres since 2026-10-02, once
                EXP-048 passed) carry `scheduled_as: <placements id>` and NO
                `placement` block. Their corner is that record's `position` x/z, their bottom layer its
                `position` y, their rotation and mirror its own. The measurement and the reasoning stay here.

`where()` resolves either kind to one (corner, y, rotation, mirror) and EVERY terrain, seat, ceiling and portal
check below runs on all six against it. A scheduled site is therefore checked against the position the server
will actually be given, not against a copy of it -- which is the only way the check could still see the
terrain if someone moved the placements record and left this file alone.

WHAT BREAKS WITHOUT IT. Every y, every min/max/median/mode and every cut/fill count in the record was
measured ONCE, by hand, off the canonical heightmap. That is the same closed loop that put four world trees
in open air over the ocean on 2026-10-01: `data/elder_trees.json`, its doc table and its site file all agreed
with each other, and none of them asked the terrain after the water pass drowned the Jungle Isle. This file
already carries one scar from that pass -- Mew's temple was re-sited because its researched coordinate
(5160, 7463) measures y61 against a sea level of y62.

THE INDEPENDENT SIDES, none of them this record:

  the terrain    `tools/ground.py`, the canonical heightmap, ROUNDED (CLAUDE.md "Ground comes from the
                 heightmap, never from a world"). Every ground, cut and fill expectation here is re-measured
                 over the footprint the resolved corner, rotation and `size` imply. No expectation is ever
                 taken from the record's `ground` block.
  the templates  `data/structures.json` `footprint`, for each template's x/height/z.
  the ceiling    the RUNTIME's build top, read from the dimension type our pack ships
                 (`modpack/datapacks/cobblers_height/.../dimension_type/overworld.json`: min_y + height - 1,
                 y575), and `data/world.json` `sea_level` (62). `vertical.max_y` (310) is NOT a ceiling for
                 built blocks: it caps authored terrain only (world.json measured_ceiling_note), and a template
                 pasted on that terrain may rise above it.
  the cells      `data/cells.json` bounds, for the cell a scheduled record and a site name.
  the rule       `data/portals.json` `rules.min_from_legendary_mouth`.

ON PROVING THESE BITE. The repository's standard is "mutate the GENERATOR, not the record", because a
record-side mutation normally moves the expectation and the output together. THERE IS NO GENERATOR HERE: the
record and the placements entry ARE the artifact, and the heightmap is the independent side. So a mutation
that perturbs a COPY of the record -- or of the placements list -- in memory and asserts the check goes red
is the right proof, and a real one, because the expectation comes from the heightmap, which a mutated record
cannot move. No file on disk is ever written: every mutation works on `copy.deepcopy`.

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

A scheduled site has no `top_y`, `ceiling_margin`, `centre` or `command`: they went with the deleted block.
What it has instead is a one-line pointer (`placement_lives_in` on every scheduled site)
that QUOTES the corner, y, rotation and mirror, and on the towers the top layer and
its margin. A quoted position is a second copy of the position, so `pointer_problems` holds every number it
quotes to the placements record and the template height; it is to a scheduled site what `command_problems` is
to an unscheduled one.

ALSO CLOSED HERE, a cross-system hole: `tools/portals.py` `clearances()` reads `data/legendaries.json`
`encounters` for `min_from_legendary_mouth` and CANNOT SEE this file, so a portal could be sited on an adopted
site. `test_every_site_clears_the_portal_rule_that_nothing_enforces` enforces it from the footprint EDGE.

NOT COVERED, by any of it. Validity is not behaviour (`.claude/rules/testing.md`):

  * whether `/place template` puts these templates down at all, or what they contain. No `.nbt` is read and
    none is in the repository (COBBLEVERSE-DP-v31.zip is gitignored, no-redistribution). `size` is believed
    from `data/structures.json`; if that footprint string is wrong, every y, top and margin is wrong with it
    and these tests agree with the error.
  * the footprint under a rotation other than `none`. `footprint()` turns the template the way Minecraft's
    StructureTemplate.transform does about the placement corner (transcribed here, not imported), but every
    site today is `rotation: none`, so the rotated branch has never met a real record.
  * whether the altars, the towers' summit chain or the levitation lift do anything, and whether
    `enable-command-block` is on. The towers' rewritten chain is tested as TEXT in
    tests/test_donor_set_commands.py; that it gates anything is an experiment, not pytest.
  * whether the terrain UNDER the paste is dressed. The tests re-derive how many blocks of cut and fill each
    site needs; nothing here places one.
  * the record's distance prose ("395 to sky_far_reach", "482 to Whiteback"). Several are centre-to-centre
    and read as clearances; no test asserts them.
  * the top-level `ceiling` block's verdict prose. `test_record_ceiling_is_the_runtime_top` pins its numbers;
    the counts in its sentences are a finding, not a thing to assert.
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
SCHEDULED = tuple(i for i in IDS if "scheduled_as" in SITES[i])
UNSCHEDULED = tuple(i for i in IDS if "scheduled_as" not in SITES[i])

PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]

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

# A template offset (dx, dz) turned about the placement corner, as Minecraft's StructureTemplate.transform does
# with a zero pivot. Transcribed here, NOT imported from tools/place_town.py or tools/place_donor.py, so the
# footprint below is not the builder's own derivation.
TURN = {"none": lambda dx, dz: (dx, dz), "clockwise_90": lambda dx, dz: (-dz, dx),
        "180": lambda dx, dz: (-dx, -dz), "counterclockwise_90": lambda dx, dz: (dz, -dx)}

STRUCTURES = {s["id"]: s for s in
              json.loads((ROOT / "data" / "structures.json").read_text(encoding="utf-8"))["structures"]}
CELLS = json.loads((ROOT / "data" / "cells.json").read_text(encoding="utf-8"))["cells"]

# The pointer a scheduled site leaves where its `placement` block was. The Crown's is named one way and the
# towers' another; either is accepted, and a scheduled site with neither fails.
POINTER_KEYS = ("placement_lives_in",)


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


# ------------------------------------------------------------------------------------- where a site stands


def records_named(site, placements):
    """Every placements record whose id is the site's `scheduled_as`. Exactly one is the contract."""
    return [q for q in placements if q.get("id") == site.get("scheduled_as")]


def where(site, placements=None):
    """{corner, y, rotation, mirror, anchor_mode, y_mode}: the site's ONE position, from whichever file authors it.

    A scheduled site reads its data/placements.json record (position x/z = corner, position y = y) and never a
    copy of it here; an unscheduled one reads its `placement` block. Nothing is defaulted: a missing rotation is
    None, and the contract tests below fail on it rather than this function papering over it."""
    placements = PLACEMENTS if placements is None else placements
    if "scheduled_as" in site:
        hits = records_named(site, placements)
        assert len(hits) == 1, "%s: scheduled_as %r names %d records in data/placements.json" \
            % (site["id"], site["scheduled_as"], len(hits))
        q = hits[0]
        pos = q["position"]
        return {"corner": [pos["x"], pos["z"]], "y": pos["y"], "rotation": q.get("rotation"),
                "mirror": q.get("mirror"), "anchor_mode": q.get("anchor_mode"), "y_mode": q.get("y_mode")}
    p = site["placement"]
    return {"corner": list(p["corner"]), "y": p["y"], "rotation": p.get("rotation"), "mirror": p.get("mirror"),
            "anchor_mode": p.get("anchor_mode"), "y_mode": p.get("y_mode")}


# ------------------------------------------------------------------------------------- the independent side


def footprint(site, placements=None):
    """The inclusive (x0, z0, x1, z1) box the resolved corner, rotation and the record's `size` imply."""
    w = where(site, placements)
    x0, z0 = w["corner"]
    sx, _, sz = site["size"]
    turned = [TURN[w["rotation"]](dx, dz) for dx in (0, sx - 1) for dz in (0, sz - 1)]
    xs = [x0 + a for a, _ in turned]
    zs = [z0 + b for _, b in turned]
    return min(xs), min(zs), max(xs), max(zs)


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


def cell_of(x, z):
    """The data/cells.json id whose bounds hold (x, z), or None."""
    for c in CELLS:
        b = c["bounds"]
        if b["min_x"] <= x <= b["max_x"] and b["min_z"] <= z <= b["max_z"]:
            return c["id"]
    return None


# ------------------------------------------------------------------- checks as functions, so they can be mutated


def ground_problems(site, g, placements=None):
    """[problem] where the record's `ground` and `displaces` blocks disagree with the heightmap."""
    x0, z0, x1, z1 = footprint(site, placements)
    m = measure(g, x0, z0, x1, z1)
    rec = site["ground"]
    bad = []
    for key in ("min", "max", "median", "mode", "mode_columns", "columns", "spread"):
        if key in rec and float(rec[key]) != float(m[key]):
            bad.append("ground.%s is %s, the heightmap says %s" % (key, rec[key], m[key]))
    if not {"min", "max", "columns"} <= set(rec):
        bad.append("ground declares no min/max/columns, so nothing about this footprint is pinned")
    cut, cut_cols, fill, fill_cols = cut_and_fill(m["heights"], where(site, placements)["y"])
    d = site["displaces"]
    for key, got in (("cut_blocks", cut), ("cut_columns", cut_cols),
                     ("fill_blocks", fill), ("fill_columns", fill_cols)):
        if key in d and d[key] != got:
            bad.append("displaces.%s is %s, the heightmap says %s" % (key, d[key], got))
    for key in ("cut_blocks", "fill_blocks"):
        if key not in d:
            bad.append("displaces declares no %s" % key)
    return bad


def seat_problems(site, g, placements=None):
    """[problem] unless the bottom layer is the UNIQUE y in the measured range that moves the fewest blocks."""
    x0, z0, x1, z1 = footprint(site, placements)
    m = measure(g, x0, z0, x1, z1)
    y = where(site, placements)["y"]
    cost = {}
    for h in range(m["min"], m["max"] + 1):
        cut, _, fill, _ = cut_and_fill(m["heights"], h)
        cost[h] = cut + fill
    if not m["min"] <= y <= m["max"]:
        return ["y%d is outside the measured ground y%d..y%d: the paste floats or is buried whole"
                % (y, m["min"], m["max"])]
    best = min(cost.values())
    cheapest = [h for h, c in cost.items() if c == best]
    if cheapest != [y]:
        return ["y%d costs %d blocks of cut+fill; the cheapest seat is %s"
                % (y, cost[y], {h: cost[h] for h in cheapest})]
    return []


def ceiling_problems(site, placements=None, top=None):
    """[problem] in the vertical arithmetic: the occupied top against the runtime's build top, and the margin.

    The occupied top comes from the resolved y and the template's height for EVERY site. `top_y` and the margin
    exist only in an unscheduled site's `placement` block; a scheduled site's quoted top is held by
    pointer_problems instead. `top` defaults to RUNTIME_TOP; it is a parameter so a test can prove the check
    bites on the ceiling it is given (the old 320) rather than on anything the record says."""
    top = RUNTIME_TOP if top is None else top
    y = where(site, placements)["y"]
    height = template_size(site)[1]
    occupied_top = y + height - 1
    bad = []
    if occupied_top > top:
        bad.append("the top occupied layer is y%d, over the runtime build limit y%d" % (occupied_top, top))
    if "scheduled_as" in site:
        return bad
    p = site["placement"]
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
    """[problem] where an unscheduled site's placement.command disagrees with the fields beside it."""
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


def schedule_problems(site, placements=None):
    """[problem] in the contract between a scheduled site and its one data/placements.json record."""
    placements = PLACEMENTS if placements is None else placements
    bad = []
    if "placement" in site:
        bad.append("%s is scheduled but still carries a placement block: two authors for one position" % site["id"])
    for stale in ("corner", "centre", "command", "top_y", "ceiling_margin"):
        if stale in site:
            bad.append("%s is scheduled but carries a top-level %r, a copy of the deleted block" % (site["id"], stale))
    hits = records_named(site, placements)
    if len(hits) != 1:
        return bad + ["scheduled_as %r names %d records in data/placements.json, not one"
                      % (site.get("scheduled_as"), len(hits))]
    q = hits[0]
    for key in ("template", "pack_template"):
        if q.get(key) != site["template"]:
            bad.append("%s.%s is %r; the site's template is %r" % (q["id"], key, q.get(key), site["template"]))
    if list(q.get("size") or []) != list(site["size"]):
        bad.append("%s.size is %r; the site's size is %r" % (q["id"], q.get("size"), site["size"]))
    if q.get("anchor_mode") != "corner":
        bad.append("%s.anchor_mode is %r, but /place template takes the minimum corner" % (q["id"], q.get("anchor_mode")))
    if q.get("y_mode") != "absolute":
        bad.append("%s.y_mode is %r, but position y is an absolute bottom layer" % (q["id"], q.get("y_mode")))
    if q.get("rotation") not in ROTATIONS:
        bad.append("%s.rotation %r is not a /place template rotation" % (q["id"], q.get("rotation")))
    if q.get("mirror") not in MIRRORS:
        bad.append("%s.mirror %r is not a /place template mirror" % (q["id"], q.get("mirror")))
    if q.get("kind") != "donor":
        bad.append("%s.kind is %r; a pack template placed by resource id is a donor" % (q["id"], q.get("kind")))
    if not ((q.get("source") or {}).get("licence")):
        bad.append("%s carries no source.licence line" % q["id"])
    if q.get("adopted_site") != site["id"]:
        bad.append("%s.adopted_site is %r, not %r: the two files do not point at each other"
                   % (q["id"], q.get("adopted_site"), site["id"]))
    pos = q.get("position") or {}
    if "x" in pos and "z" in pos and q.get("cell") != cell_of(pos["x"], pos["z"]):
        bad.append("%s.cell is %r; data/cells.json puts (%d, %d) in %r"
                   % (q["id"], q.get("cell"), pos["x"], pos["z"], cell_of(pos["x"], pos["z"])))
    others = [o["id"] for o in placements if o is not q
              and site["template"] in (o.get("template"), o.get("pack_template"))]
    if others:
        bad.append("%s is also placed by %s: two positions for one template" % (site["template"], others))
    return bad


def unscheduled_problems(site, placements=None):
    """[problem] unless an unscheduled site keeps its block and nothing in data/placements.json places it."""
    placements = PLACEMENTS if placements is None else placements
    bad = []
    if "placement" not in site:
        bad.append("%s is neither scheduled nor carries a placement block: it has no position at all" % site["id"])
    for q in placements:
        if site["template"] in (q.get("template"), q.get("pack_template")):
            bad.append("%s is also placed by data/placements.json %s, so two files carry a position for it"
                       % (site["template"], q.get("id")))
        if q.get("adopted_site") == site["id"] or q.get("id") == site["id"]:
            bad.append("data/placements.json %s claims %s, which is not scheduled" % (q.get("id"), site["id"]))
    return bad


def pointer_problems(site, placements=None):
    """[problem] where a scheduled site's pointer prose quotes a position its placements record does not hold."""
    keys = [k for k in POINTER_KEYS if k in site]
    if len(keys) != 1:
        return ["%s carries %d of %s; a scheduled site leaves exactly one pointer" % (site["id"], len(keys), POINTER_KEYS)]
    text = site[keys[0]]
    w = where(site, placements)
    bad = []
    if site["scheduled_as"] not in text:
        bad.append("%s does not name %s" % (keys[0], site["scheduled_as"]))
    m = re.search(r"corner \((\d+), (\d+)\)", text)
    if not m or [int(v) for v in m.groups()] != w["corner"]:
        bad.append("%s quotes corner %s; the record's is %s" % (keys[0], m and m.group(0), w["corner"]))
    m = re.search(r"\by(\d+),", text)
    if not m or int(m.group(1)) != w["y"]:
        bad.append("%s quotes %s; the record's y is %d" % (keys[0], m and m.group(0), w["y"]))
    for field in ("rotation", "mirror"):
        m = re.search(r"\b%s (\S+?)[,.]" % field, text)
        if not m or m.group(1) != w[field]:
            bad.append("%s quotes %s %s; the record's is %s" % (keys[0], field, m and m.group(1), w[field]))
    m = re.search(r"top occupied layer y(\d+) \((\d+) under the runtime ceiling y(\d+)", text)
    if "top occupied layer" in text and not m:
        bad.append("%s quotes a top occupied layer without its margin under the runtime ceiling" % keys[0])
    if m:
        top, margin, roof = (int(v) for v in m.groups())
        want = w["y"] + template_size(site)[1] - 1
        if top != want:
            bad.append("%s quotes the top occupied layer y%d; y + height - 1 is y%d" % (keys[0], top, want))
        if roof != RUNTIME_TOP or margin != RUNTIME_TOP - want:
            bad.append("%s quotes %d under y%d; the runtime top y%d gives %d"
                       % (keys[0], margin, roof, RUNTIME_TOP, RUNTIME_TOP - want))
    return bad


def intrusions(placements=None):
    """[(site, placements id)] for every authored placement whose position stands inside an adopted footprint.

    The ONE record excluded is the site's own scheduled record, whose position IS the footprint's corner."""
    placements = PLACEMENTS if placements is None else placements
    inside = []
    for sid in IDS:
        site = SITES[sid]
        x0, z0, x1, z1 = footprint(site, placements)
        for q in placements:
            if "scheduled_as" in site and q.get("id") == site["scheduled_as"]:
                continue
            pos = q.get("position") or {}
            if "x" in pos and x0 <= pos["x"] <= x1 and z0 <= pos["z"] <= z1:
                inside.append((sid, q["id"]))
    return inside


# ------------------------------------------------------------------------------------------- one author each


def test_both_kinds_of_site_are_present():
    # Without it a regression that turns every site into one kind would leave half of the parametrised
    # checks below running over nothing and still green.
    assert SCHEDULED and UNSCHEDULED, (SCHEDULED, UNSCHEDULED)


@pytest.mark.parametrize("sid", IDS)
def test_every_site_is_positioned_by_exactly_one_author(sid):
    # Without it a site can carry a placement block AND a scheduled_as, two positions in two files that git
    # will never say disagree (CLAUDE.md "A clean merge is not a clean union"), or neither, and no position.
    site = SITES[sid]
    assert ("placement" in site) != ("scheduled_as" in site), \
        "%s: placement block %s, scheduled_as %s" % (sid, "placement" in site, site.get("scheduled_as"))


@pytest.mark.parametrize("sid", SCHEDULED)
def test_a_scheduled_site_is_its_one_placements_record(sid):
    # Without it the scheduled record can drift from the site that measured it -- another template, another
    # size, a centre anchor, a relative y -- and every terrain check here would be measuring the wrong paste.
    assert schedule_problems(SITES[sid]) == []


@pytest.mark.parametrize("sid", SCHEDULED)
def test_a_scheduled_sites_pointer_quotes_the_records_position(sid):
    # Without it the one line a human reads here in place of the deleted block can quote a corner, y or top
    # the server is not given: a second, stale copy of the position.
    assert pointer_problems(SITES[sid]) == []


@pytest.mark.parametrize("sid", UNSCHEDULED)
def test_an_unscheduled_site_is_not_positioned_by_placements_json(sid):
    # Without it the day a site is copied into data/placements.json its `placement` block here can survive,
    # and one site has two positions in two files.
    assert unscheduled_problems(SITES[sid]) == []


def test_every_placements_record_claiming_an_adopted_site_is_that_sites_schedule():
    # Without it a placements record can name an adopted site that does not point back at it -- a third
    # author, or a schedule this file never agreed to.
    claims = {q["id"]: q["adopted_site"] for q in PLACEMENTS if q.get("adopted_site")}
    assert claims == {SITES[s]["scheduled_as"]: s for s in SCHEDULED}


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
    # Without it the prose can quote a box that is not the box the resolved corner + `size` describe, and the
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
    # Without it nothing connects `y` to the terrain at all. The record argues this site by site ("zero cut
    # and zero fill", "the unique cheapest seat", "the balance point of the whole column"); stated once and
    # derived from the heightmap, for a scheduled site from its placements record's position y.
    assert seat_problems(SITES[sid], ground) == []


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
        x0, z0 = where(site)["corner"]
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
def test_the_named_cell_holds_the_corner(sid):
    # Without it a site can say B5 while standing in C5, and a reader who looks for it by cell never finds it.
    site = SITES[sid]
    x, z = where(site)["corner"]
    assert site["site"]["cell"] == cell_of(x, z), \
        "%s says cell %s; data/cells.json puts (%d, %d) in %s" % (sid, site["site"]["cell"], x, z, cell_of(x, z))


@pytest.mark.parametrize("sid", UNSCHEDULED)
def test_centre_is_the_corner_plus_half_the_size(sid):
    # Without it the centre -- the point every distance in the record is measured from -- can drift off the
    # footprint it names. Only an unscheduled site has one; a scheduled site's went with its placement block,
    # and test_a_scheduled_site_is_its_one_placements_record fails if a stale copy is left at the top level.
    site = SITES[sid]
    x0, z0 = site["placement"]["corner"]
    sx, _, sz = site["size"]
    assert site["placement"]["centre"] == [x0 + sx // 2, z0 + sz // 2]


@pytest.mark.parametrize("sid", IDS)
def test_top_y_is_the_templates_top_and_clears_the_runtime_ceiling(sid):
    # Without it a 90-block tower seated high pokes through the build limit and the record still reads fine.
    # Every site: y + height - 1 from the resolved y. Unscheduled sites: top_y and the margin as well.
    assert ceiling_problems(SITES[sid]) == []


@pytest.mark.parametrize("sid", UNSCHEDULED)
def test_declared_margin_is_the_runtime_top_minus_the_occupied_top(sid):
    # Without it `ceiling_margin` is a number from the day it was typed. It is covered by
    # ceiling_problems(); this test names the property so a stale margin is not reported as "ceiling".
    site = SITES[sid]
    p = site["placement"]
    assert p["ceiling_margin"] == RUNTIME_TOP - (p["y"] + template_size(site)[1] - 1)
    assert "max_y_margin" not in p


@pytest.mark.parametrize("sid", UNSCHEDULED)
def test_command_text_is_the_fields_beside_it(sid):
    # Without it the one string a human will copy can disagree with the corner, y, rotation and mirror the
    # rest of the record reasons about, and the fields become decoration.
    assert command_problems(SITES[sid]) == []


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


def _portal_clearance(placements=None):
    """(rule, [(site id, portal id, distance from the footprint EDGE)]) for every site/portal pair."""
    doc = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))
    rule = doc["rules"]["min_from_legendary_mouth"]
    out = []
    for sid in IDS:
        x0, z0, x1, z1 = footprint(SITES[sid], placements)
        for q in doc["portals"]:
            px, pz = q["at"]
            d = math.hypot(max(x0 - px, 0, px - x1), max(z0 - pz, 0, pz - z1))
            out.append((sid, q["id"], d))
    return rule, out


def test_every_site_clears_the_portal_rule_that_nothing_enforces():
    # Without it nothing in the repository holds these sites to `min_from_legendary_mouth`:
    # tools/portals.py reads data/legendaries.json `encounters` for that check and cannot see this file,
    # so a portal could be sited on top of an adopted site and both tools would pass. Measured from the
    # footprint edge, which is stricter than portals.py's point-to-point.
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
    # Without it a site can be measured onto ground something of ours is already built on. A scheduled site's
    # own record is excluded -- its position IS the corner -- and nothing else is.
    assert intrusions() == []


# ------------------------------------------------------------------------------------------------ mutations
#
# A mutated COPY of the record, or of data/placements.json, must be caught. See the module docstring on why a
# record-side mutation is the right proof here: the expectations come out of the heightmap,
# data/structures.json, data/world.json, data/cells.json and data/portals.json, none of which a mutated dict
# can move. No file is written.


def _placements_with(record_id, **changes):
    """A deep copy of data/placements.json's list with one record's fields replaced (position keys merged)."""
    out = copy.deepcopy(PLACEMENTS)
    q = next(r for r in out if r.get("id") == record_id)
    for k, v in changes.items():
        if k == "position":
            q["position"].update(v)
        else:
            q[k] = v
    return out


@pytest.mark.slow
@pytest.mark.parametrize("field,delta", [("min", -1), ("max", 1), ("median", 1), ("mode", 1),
                                         ("columns", -1), ("mode_columns", 1), ("spread", 1)])
def test_a_perturbed_ground_stat_is_caught(field, delta, ground):
    # Proves test_ground_block_is_the_heightmap bites on each stat separately, on a SCHEDULED site whose
    # footprint is resolved through data/placements.json.
    site = copy.deepcopy(SITES["adopted_crown_cemetery"])
    assert "scheduled_as" in site, "the mutation target is meant to be a scheduled site"
    if field not in site["ground"]:
        pytest.skip("adopted_crown_cemetery declares no ground.%s" % field)
    site["ground"][field] += delta
    assert any(("ground.%s" % field) in p for p in ground_problems(site, ground))


@pytest.mark.slow
@pytest.mark.parametrize("sid", ["adopted_zapdos_tower", "adopted_dusk_tower", "adopted_articuno_shrine"])
@pytest.mark.parametrize("field", ["cut_blocks", "fill_blocks", "cut_columns", "fill_columns"])
def test_a_perturbed_cut_or_fill_count_is_caught(field, sid, ground):
    # Proves the displacement counts are re-derived rather than read back, for sites of both kinds (Articuno is
    # the one unscheduled site since 2026-10-02, and declares only the block counts).
    site = copy.deepcopy(SITES[sid])
    if field not in site["displaces"]:
        pytest.skip("%s declares no displaces.%s" % (sid, field))
    site["displaces"][field] += 1
    assert any(("displaces.%s" % field) in p for p in ground_problems(site, ground))


@pytest.mark.slow
@pytest.mark.parametrize("record_id,sid", [("legendary_dawn_tower", "adopted_dawn_tower"),
                                           ("legendary_dusk_tower", "adopted_dusk_tower"),
                                           ("legendary_crown_cemetery", "adopted_crown_cemetery"),
                                           ("legendary_zapdos_tower", "adopted_zapdos_tower"),
                                           ("legendary_mew_temple", "adopted_mew_temple"),
                                           ("legendary_moltres_tower", "adopted_moltres_tower")])
@pytest.mark.parametrize("dy", [1, -1])
def test_a_scheduled_record_reseated_by_one_block_is_caught(record_id, sid, dy, ground):
    # The input the scheduled checks read is the placements record, so THAT is what is moved: one block up
    # or down, the site file untouched. Both the seat and the cut/fill counts must go red.
    y = next(q for q in PLACEMENTS if q["id"] == record_id)["position"]["y"]
    moved = _placements_with(record_id, position={"y": y + dy})
    assert seat_problems(SITES[sid], ground, moved) != []
    assert any(p.startswith("displaces.") for p in ground_problems(SITES[sid], ground, moved))


@pytest.mark.slow
def test_a_scheduled_record_moved_onto_different_terrain_is_caught(ground):
    # The elder-tree failure in miniature, on the placements side: the site file stays perfect and only
    # the record's corner moves.
    q = next(r for r in PLACEMENTS if r["id"] == "legendary_crown_cemetery")
    moved = _placements_with("legendary_crown_cemetery",
                             position={"x": q["position"]["x"] + 60, "z": q["position"]["z"] + 60})
    assert ground_problems(SITES["adopted_crown_cemetery"], ground, moved) != []


@pytest.mark.slow
def test_a_site_moved_onto_different_terrain_is_caught(ground):
    # The same for an unscheduled site, whose corner lives in its own placement block.
    site = copy.deepcopy(SITES["adopted_articuno_shrine"])
    site["placement"]["corner"] = [site["placement"]["corner"][0] + 60, site["placement"]["corner"][1] + 60]
    assert ground_problems(site, ground) != []


@pytest.mark.slow
def test_a_drowned_site_is_caught(ground):
    # Mew's researched coordinate (5160, 7463) measures y61 against a sea level of y62: the site the water
    # pass removed. A record re-sited back onto it must fail the sea-level check.
    # Mew is scheduled, so the record moved is its placements record.
    moved = _placements_with("legendary_mew_temple", position={"x": 5160, "z": 7463})
    x0, z0, x1, z1 = footprint(SITES["adopted_mew_temple"], moved)
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
    site = copy.deepcopy(SITES["adopted_articuno_shrine"])
    site["placement"]["max_y_margin"] = MAX_Y - site["placement"]["top_y"]
    assert any("max_y_margin" in p for p in ceiling_problems(site))


def test_a_top_y_that_overstates_the_template_is_caught():
    # One convention now: y + height (Articuno's old form) is as wrong as an understatement.
    site = copy.deepcopy(SITES["adopted_articuno_shrine"])
    site["placement"]["top_y"] += 1
    site["placement"]["ceiling_margin"] -= 1
    assert any("not the top occupied layer" in p for p in ceiling_problems(site))


def test_a_scheduled_tower_raised_through_the_ceiling_is_caught():
    # The same for a scheduled site, moving only its placements record: a y that puts the Dawn tower's top layer
    # exactly on the runtime top is clean, and one block higher breaches it. Derived from the template's height
    # and RUNTIME_TOP, so the check is held to the dimension type, not to a typed number.
    height = template_size(SITES["adopted_dawn_tower"])[1]
    at_limit_y = RUNTIME_TOP - height + 1
    at_limit = ceiling_problems(SITES["adopted_dawn_tower"],
                                _placements_with("legendary_dawn_tower", position={"y": at_limit_y}))
    assert not any("build limit" in p for p in at_limit), at_limit
    over = ceiling_problems(SITES["adopted_dawn_tower"],
                            _placements_with("legendary_dawn_tower", position={"y": at_limit_y + 1}))
    assert any("build limit" in p for p in over), over


def test_a_stale_ceiling_margin_is_caught():
    # The margin that was true when it was typed. One block off and it resolves onto no real ceiling.
    site = copy.deepcopy(SITES["adopted_articuno_shrine"])
    site["placement"]["ceiling_margin"] += 1
    assert any("ceiling_margin" in p for p in ceiling_problems(site))


def test_a_top_y_that_understates_the_template_is_caught():
    # The dangerous direction: a top_y below the real top would let a breach of the ceiling read as safe.
    site = copy.deepcopy(SITES["adopted_articuno_shrine"])
    site["placement"]["top_y"] -= 1
    assert any("understates" in p for p in ceiling_problems(site))


@pytest.mark.parametrize("field,value", [("corner", [1, 2]), ("y", 7), ("rotation", "clockwise_90"),
                                         ("mirror", "front_back"), ("anchor_mode", "centre"),
                                         ("y_mode", "relative")])
def test_a_command_that_no_longer_matches_its_fields_is_caught(field, value):
    # Proves the command is parsed against the fields rather than merely present. Each of these is a real
    # way for the two to part: a re-site, a re-seat, a rotation chosen once the .nbt has been looked at.
    site = copy.deepcopy(SITES["adopted_articuno_shrine"])
    site["placement"][field] = value
    assert command_problems(site) != []


@pytest.mark.parametrize("record_id,changes", [
    ("legendary_crown_cemetery", {"size": [45, 24, 46]}),
    ("legendary_crown_cemetery", {"template": "cobbleverse:dawn_tower"}),
    ("legendary_crown_cemetery", {"pack_template": "cobbleverse:dawn_tower"}),
    ("legendary_dawn_tower", {"anchor_mode": "centre"}),
    ("legendary_dawn_tower", {"y_mode": "relative"}),
    ("legendary_dawn_tower", {"rotation": "90"}),
    ("legendary_dusk_tower", {"mirror": "sideways"}),
    ("legendary_dusk_tower", {"kind": "town"}),
    ("legendary_dusk_tower", {"adopted_site": "adopted_dawn_tower"}),
    ("legendary_dusk_tower", {"cell": "H1"}),
    ("legendary_crown_cemetery", {"id": "legendary_crown_cemetery_renamed"}),
])
def test_a_scheduled_record_that_parts_from_its_site_is_caught(record_id, changes):
    # Proves schedule_problems reads each field of the contract, by breaking the PLACEMENTS side one field at
    # a time with the site file untouched.
    sid = next(q for q in PLACEMENTS if q["id"] == record_id)["adopted_site"]
    assert schedule_problems(SITES[sid], _placements_with(record_id, **changes)) != []


def test_a_second_record_placing_a_scheduled_template_is_caught():
    # Two placements records, one template: the second is a second position however its id reads.
    twin = copy.deepcopy(next(q for q in PLACEMENTS if q["id"] == "legendary_dusk_tower"))
    twin["id"] = "some_other_dusk"
    twin.pop("adopted_site")
    assert any("also placed by" in p for p in schedule_problems(SITES["adopted_dusk_tower"], PLACEMENTS + [twin]))


def test_a_duplicated_scheduled_id_is_caught():
    # Two records under the scheduled id: `scheduled_as` no longer names one position.
    twin = copy.deepcopy(next(q for q in PLACEMENTS if q["id"] == "legendary_dawn_tower"))
    assert schedule_problems(SITES["adopted_dawn_tower"], PLACEMENTS + [twin]) != []


def test_a_scheduled_site_that_keeps_its_placement_block_is_caught():
    # The deletion the record's own rule demands, undone.
    site = copy.deepcopy(SITES["adopted_crown_cemetery"])
    site["placement"] = {"corner": [4118, 1982], "y": 109}
    assert any("still carries a placement block" in p for p in schedule_problems(site))


def test_an_unscheduled_template_turning_up_in_placements_is_caught():
    # Articuno's tower copied into data/placements.json while its placement block stays here: tools/place_donor.py
    # and tools/articuno_tower.py (R18A) would then both paste it.
    rogue = {"id": "legendary_articuno_shrine", "template": SITES["adopted_articuno_shrine"]["template"],
             "position": {"x": 672, "y": 310, "z": 369}}
    assert unscheduled_problems(SITES["adopted_articuno_shrine"], PLACEMENTS + [rogue]) != []


def test_articuno_is_placed_by_its_own_step_and_never_scheduled():
    # Articuno's tower is pasted by tools/articuno_tower.py (reapply R18A) from its `placement` block. A
    # data/placements.json donor for it would paste it a second time in R9.
    assert "adopted_articuno_shrine" in UNSCHEDULED
    assert not [q["id"] for q in PLACEMENTS if SITES["adopted_articuno_shrine"]["template"]
                in (q.get("template"), q.get("pack_template"))]


@pytest.mark.parametrize("sid", IDS)
def test_the_shared_resolver_agrees_with_this_files_own(sid):
    # tools/adopted_sites.py is what other systems (sea life, the research station) read a site's position
    # through. Its footprint must be this file's, for scheduled and unscheduled sites alike, or a consumer
    # keeps out of the wrong box.
    import adopted_sites
    assert adopted_sites.footprint(SITES[sid], PLACEMENTS) == footprint(SITES[sid])
    if "placement" in SITES[sid] and "centre" in SITES[sid]["placement"]:
        assert adopted_sites.centre(SITES[sid], PLACEMENTS) == SITES[sid]["placement"]["centre"]


def test_the_shared_resolver_fails_closed_on_a_site_with_no_position():
    # A silent None is how a scheduled site dropped out of the sea-life keep-out.
    import adopted_sites
    site = copy.deepcopy(SITES["adopted_zapdos_tower"])
    site["scheduled_as"] = "no_such_record"
    with pytest.raises(SystemExit):
        adopted_sites.where(site, PLACEMENTS)
    site.pop("scheduled_as")
    with pytest.raises(SystemExit):
        adopted_sites.where(site, PLACEMENTS)


@pytest.mark.parametrize("sid,mutate", [
    ("adopted_dawn_tower", lambda s: s.__setitem__("placement_lives_in", s["placement_lives_in"].replace("y99", "y98"))),
    ("adopted_dawn_tower", lambda s: s.__setitem__("placement_lives_in", s["placement_lives_in"].replace("y188", "y189"))),
    ("adopted_dawn_tower", lambda s: s.__setitem__("placement_lives_in", s["placement_lives_in"].replace("(387", "(386"))),
    ("adopted_dusk_tower", lambda s: s.__setitem__("placement_lives_in", s["placement_lives_in"].replace("7216", "7217"))),
    ("adopted_crown_cemetery", lambda s: s.__setitem__("placement_lives_in", s["placement_lives_in"].replace("rotation none", "rotation 180"))),
    ("adopted_crown_cemetery", lambda s: s.pop("placement_lives_in")),
])
def test_a_stale_pointer_is_caught(sid, mutate):
    # Proves pointer_problems reads every number it says it reads.
    site = copy.deepcopy(SITES[sid])
    mutate(site)
    assert pointer_problems(site) != []


def test_a_pointer_left_behind_by_a_moved_record_is_caught():
    # The direction that matters: the RECORD moves and the prose does not.
    moved = _placements_with("legendary_dusk_tower", position={"y": 147})
    assert pointer_problems(SITES["adopted_dusk_tower"], moved) != []


def test_a_placement_moved_into_an_adopted_footprint_is_caught():
    # Proves the intrusion check measures something, and that its one exclusion is the site's own record
    # and nothing else: the Dusk tower's record moved into the Crown's footprint, and a COPY of the Crown's
    # own record under another id, must both be reported.
    crown = next(q for q in PLACEMENTS if q["id"] == "legendary_crown_cemetery")
    moved = _placements_with("legendary_dusk_tower",
                             position={"x": crown["position"]["x"] + 5, "z": crown["position"]["z"] + 5})
    assert ("adopted_crown_cemetery", "legendary_dusk_tower") in intrusions(moved)
    twin = copy.deepcopy(crown)
    twin["id"] = "not_the_crowns_own_record"
    assert ("adopted_crown_cemetery", "not_the_crowns_own_record") in intrusions(PLACEMENTS + [twin])


def test_a_site_sited_on_a_portal_is_caught():
    # Proves the clearance check measures something: the hole it closes is a portal and a site in the same
    # place, which no other tool in the repository can see at once. Run through _portal_clearance itself,
    # with a scheduled site's placements record moved onto the portal.
    doc = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))
    px, pz = doc["portals"][0]["at"]
    moved = _placements_with("legendary_dawn_tower", position={"x": px - 5, "z": pz - 5})
    rule, pairs = _portal_clearance(moved)
    assert any(s == "adopted_dawn_tower" and p == doc["portals"][0]["id"] and d < rule for s, p, d in pairs)


def test_footprint_turns_with_the_rotation():
    # Proves the footprint is not hard-wired to rotation none. Worked by hand for the 46 (x) by 45 (z) tower
    # at (100, 200): clockwise_90 sends the x run along +z and the z run along -x, so x100-44..100 = 56..100
    # and z200..200+45 = 200..245; 180 sends both negative, x100-45..100 = 55..100, z200-44..200 = 156..200.
    site = copy.deepcopy(SITES["adopted_dawn_tower"])
    moved = _placements_with("legendary_dawn_tower", position={"x": 100, "z": 200}, rotation="clockwise_90")
    assert footprint(site, moved) == (56, 200, 100, 245)
    moved = _placements_with("legendary_dawn_tower", position={"x": 100, "z": 200}, rotation="180")
    assert footprint(site, moved) == (55, 156, 100, 200)
