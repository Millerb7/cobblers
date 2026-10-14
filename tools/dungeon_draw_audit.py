#!/usr/bin/env python
"""INDEPENDENT audit of the dungeon draw (docs/mechanics/DUNGEON_DRAW.md sections 2-4) and of where the rips stand.

Independent means: the EXPECTATIONS here come from the spec (the design, the owner's answers D1-D5) and from
data/dungeon_prize_roster.json (first_band and gate per dungeon), never from the generator's own helpers.

  * The draw is checked by RUNNING the functions tools/dungeon.py emits, on the existing function simulator
    (tests/pocket_sim.py through tests/test_dungeon.py's DW), against scenarios built from the roster. No expectation
    is read from dungeon.py's `draw`, `candidates` or `eligible` code.
  * Rip siting is re-measured from tools/ground.py (the canonical heightmap, ROUNDED) and from data/*.json read here.
    tools/dungeon_rips.py is not imported for a single number: its siting rules are the thing being audited.
  * The owner's decisions of 2026-10-13 are read as: the 13 trail rips are RETIRED (data/dungeon_rips.json retired_rips; R16DR's
    rips/retire puts back each one's recorded plane and patch, an entity sweep kills their entities, nothing draws from their
    click); EVERY region with dry ground has a standing rip; a rip inside a badge-gated rift zone is ALLOWED and declares
    `reachable_after` as data/rift_zones.json has the zone. The expectations are the records, data/rift_zones.json,
    data/regions.json, data/dungeon_themes.json and the heightmap, read here.
  * Independence is proved by MUTATING THE GENERATOR (tools/dungeon.py source, with data/ untouched): `--mutate` rebuilds
    the pack from a mutated copy of the source and requires the audit to FAIL. A mutation that only edited data would
    move the expectation and the output together and prove nothing.

  python tools/dungeon_draw_audit.py --out <file>                 the whole audit; one verdict line on stdout
  python tools/dungeon_draw_audit.py --out <file> --only siting   the heightmap part only (seconds)
  python tools/dungeon_draw_audit.py --out <file> --only draw     the simulator part only (minutes)
  python tools/dungeon_draw_audit.py --mutate NAME --out <file>   rebuild from the mutation NAME and run the draw part

What this does NOT cover (CLAUDE.md "Our list is not the world"; testing.md): any of it in a running Minecraft. That
`random value 0..2^30-1` and `scoreboard players operation %=` behave in a function on a server as the simulator models
them, that a rip's click reaches its door through the advancement reward, that the oval stands where the siting says,
and that a tree or a mod structure is not in a plane. Nether rips are not sited (DUNGEON_DRAW.md section 5). The co-op
party draw (2.5) is deferred and unbuilt. The siting is checked against data/ and the heightmap, never against a world.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data"
OW = "minecraft:overworld"
OLD_TEST_RIPS_COMMIT = "6249332e"   # the 13 trail rips' positions, as the owner played them (git show 6249332e:data/dungeons.json)
MAP = 8192
RIPS_DIR = "data/cobblers/function/dungeons/rips/"     # where the pack's rip functions live (the path sc_rips_are_placed already reads)
FN = "cobblers:dungeons/"                              # the pack's function namespace and folder, as the reapply steps name them
DRY_SAMPLE_STEP = 8                                    # blocks between the columns sampled to decide whether a region has dry ground

# the spec's numbers (DUNGEON_DRAW.md 2.6), written here and not read from the tool under audit
CLEARANCE = 30          # blocks from every authored data/ coordinate
SPAWN_FREE_MARGIN = 0   # "No rip inside a spawn-free town precinct": the footprint must not touch one

BAND_CAPS = {1: (1, 25), 2: (26, 35), 3: (36, 45), 4: (46, 55), 5: (56, 62), 6: (63, 100)}   # DUNGEON_DRAW.md 1 / 2.2: the cap that makes each band
CAP_FOR_BAND = {1: 20, 2: 30, 3: 40, 4: 50, 5: 60, 6: 100}

# the dungeons the draw draws from, by roster id; the roster also lists three that are not built (cistern, temple_calendar,
# zero_dig): the audit only judges the ones in data/dungeons.json
ROSTER = DATA / "dungeon_prize_roster.json"


# ------------------------------------------------------------------------------------------------- the spec's expectations


def roster_expectations(roster=None, built_ids=None):
    """{dungeon id: (first_band, gate flag id or None)} from the roster's own fields. The roster's gate is prose such as
    'gym8_cleared (proposed, ...)': the flag is the leading token."""
    roster = roster if roster is not None else json.loads(ROSTER.read_text(encoding="utf-8"))
    out = {}
    for d in roster["dungeons"]:
        if built_ids is not None and d["id"] not in built_ids:
            continue
        g = d.get("gate")
        flag = None
        if g:
            m = re.match(r"([a-z0-9_]+_cleared)\b", g)
            if not m:
                raise ValueError("roster gate %r of %s does not start with a flag" % (g, d["id"]))
            flag = m.group(1)
        out[d["id"]] = (int(d["first_band"]), flag)
    return out


def eligible(band, held, expect):
    """The spec's rule (2.2): in the draw at band B when first_band <= B and the gate flag, if any, is held."""
    return {i for i, (fb, flag) in expect.items() if fb <= band and (flag is None or flag in held)}


# ------------------------------------------------------------------------------------------------- siting (heightmap, data)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _walk(obj, out, src):
    """Every authored coordinate: a dict with numeric x and z (or cx, cz); a list of two numbers read as (x, z); a list of three
    read as (x, y, z). A list of four is a BOX, an area and not a coordinate: boxes are held by the precinct and the gated-zone
    checks, where 'inside' is what matters. Over-inclusive otherwise on purpose: a stray list of small numbers is a false point
    near the map's corner, not a missed one."""
    if isinstance(obj, dict):
        for kx, kz in (("x", "z"), ("cx", "cz")):
            if _num(obj.get(kx)) and _num(obj.get(kz)):
                out.append((float(obj[kx]), float(obj[kz]), src))
        for v in obj.values():
            _walk(v, out, src)
    elif isinstance(obj, list):
        if obj and all(_num(v) for v in obj):
            if len(obj) == 2:
                out.append((float(obj[0]), float(obj[1]), src))
            elif len(obj) == 3:
                out.append((float(obj[0]), float(obj[2]), src))
            return
        for v in obj:
            _walk(v, out, src)


def authored_points(data_dir=DATA, skip_files=(), drop=None):
    """[(x, z, file)] for every coordinate in data/*.json and data/*/*.json. `drop(rel, doc)` may edit a document first (the
    rips' own probes are the rips' coordinates over again)."""
    out = []
    files = sorted(glob.glob(str(Path(data_dir) / "*.json"))) + sorted(glob.glob(str(Path(data_dir) / "*" / "*.json")))
    for f in files:
        rel = Path(f).relative_to(Path(data_dir).parent).as_posix()
        if rel in skip_files:
            continue
        doc = json.loads(Path(f).read_text(encoding="utf-8"))
        if drop:
            drop(rel, doc)
        pts = []
        _walk(doc, pts, rel)
        out += [p for p in pts if 0 <= p[0] < MAP and 0 <= p[1] < MAP]
    return out


def _drop_rip_probes(rel, doc):
    if rel == "data/world_probes.json":
        doc.get("places", {}).pop("dungeon_rips", None)


def ring_contains(ring, x, z):
    c, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, zi = ring[i][0], ring[i][1]
        xj, zj = ring[j][0], ring[j][1]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / float(zj - zi) + xi:
            c = not c
        j = i
    return c


def polys_contain(polys, x, z):
    return any(ring_contains(r, x, z) for r in polys)


def footprint(r):
    """(x0, z0, x1, z1) of what a rip occupies: its plane (x0..x1 at z), the click one in front and the exit point three in
    front. Read from the record's own frame/click/outside, not from the tool's window."""
    f = r["frame"]
    xs = [f["x0"], f["x1"], r["click"][0], math.floor(r["outside"][0])]
    zs = [f["z"], r["click"][2], math.floor(r["outside"][2])]
    return (min(xs), min(zs), max(xs), max(zs))


def box_gap(a, b):
    """Edge-to-edge distance between two boxes (x0, z0, x1, z1), 0 when they touch or overlap."""
    return math.hypot(max(a[0] - b[2], 0, b[0] - a[2]), max(a[1] - b[3], 0, b[1] - a[3]))


def point_gap(box, x, z):
    return math.hypot(max(box[0] - x, 0, x - box[2]), max(box[1] - z, 0, z - box[3]))


def water_world(data_dir=DATA):
    """(sea level, [(level_y, basin rings)]) read from data/world.json and data/landmarks.json."""
    w = json.loads((Path(data_dir) / "world.json").read_text(encoding="utf-8"))
    sea = int(w["vertical"]["sea_level"])
    lakes = []
    for l in json.loads((Path(data_dir) / "landmarks.json").read_text(encoding="utf-8"))["landmarks"]:
        wb = l.get("water_body") or {}
        if wb.get("level_y") is not None and wb.get("basin_polygons"):
            lakes.append((int(wb["level_y"]), [[tuple(q) for q in ring] for ring in wb["basin_polygons"]]))
    return sea, lakes


def precinct_boxes(data_dir=DATA):
    """[(x0, z0, x1, z1, label)]: the spawn-free zones and every town footprint, as data/ authors them."""
    out = []
    sup = json.loads((Path(data_dir) / "spawn_suppression.json").read_text(encoding="utf-8"))
    for z in sup.get("spawn_free_zones") or []:
        b = z["box"]
        out.append((b[0], b[1], b[2], b[3], "spawn_free_zone " + z["id"]))
    for t in json.loads((Path(data_dir) / "towns.json").read_text(encoding="utf-8"))["towns"]:
        f = t.get("footprint") or {}
        if all(k in f for k in ("min_x", "min_z", "max_x", "max_z")):
            out.append((f["min_x"], f["min_z"], f["max_x"], f["max_z"], "town " + t["id"]))
    return out


def region_polygons(data_dir=DATA):
    return {r["id"]: r["polygons"] for r in json.loads((Path(data_dir) / "regions.json").read_text(encoding="utf-8"))["regions"]}


def siting_problems(rips, ground, sea, lakes, points, boxes, regions, clearance=CLEARANCE):
    """[problem] for a list of STANDING rips: dry, `clearance` blocks from every point, outside every precinct, inside its own
    region. All inputs are values, so a fixture can hand it a synthetic world with hand-computable answers. Since the owner's
    2026-10-13 decision ("the rips near old mine have to go") no standing rip is exempt from anything: a rip of kind
    test_trail that is still in the standing list is itself a problem (the 13 live under retired_rips)."""
    bad = []
    for r in rips:
        rid = r["id"]
        fp = footprint(r)
        if r.get("kind") == "test_trail":
            bad.append("%s: a test_trail rip is standing; the owner retired them all on 2026-10-13" % rid)
        wet = None
        for x in range(fp[0], fp[2] + 1):
            for z in range(fp[1], fp[3] + 1):
                gy = ground(x, z)
                if gy < sea:
                    wet = (x, z, "sea", gy, sea)
                for level, basin in lakes:
                    if gy < level and polys_contain(basin, x, z):
                        wet = (x, z, "a lake", gy, level)
                if wet:
                    break
            if wet:
                break
        if wet:
            bad.append("%s: (%d, %d) is under %s: ground y%d, water y%d" % (rid, wet[0], wet[1], wet[2], wet[3], wet[4]))
        g = ground(r["click"][0], r["click"][2])
        if r["frame"]["y"] != g + 1:
            bad.append("%s: frame.y %d is not round(ground) + 1 = %d" % (rid, r["frame"]["y"], g + 1))
        near = min(((point_gap(fp, p[0], p[1]), p) for p in points), key=lambda t: t[0], default=(float("inf"), None))
        if near[0] < clearance:
            bad.append("%s: authored (%d, %d) in %s is %.1f blocks from the footprint; the rule is %d"
                       % (rid, near[1][0], near[1][1], near[1][2], near[0], clearance))
        for b in boxes:
            if box_gap(fp, b) <= SPAWN_FREE_MARGIN:
                bad.append("%s: the footprint touches %s" % (rid, b[4]))
        polys = regions.get(r.get("region"))
        if polys is None:
            bad.append("%s: region %r is not in data/regions.json" % (rid, r.get("region")))
        else:
            for x, z in ((fp[0], fp[1]), (fp[2], fp[1]), (fp[0], fp[3]), (fp[2], fp[3])):
                if not polys_contain(polys, x, z):
                    bad.append("%s: footprint corner (%d, %d) is outside region %s" % (rid, x, z, r["region"]))
                    break
    return bad


# ------------------------------------------------------------------------------------------------- a rip in every dry region


def _inside_any(rings, X, Z):
    """Boolean array: (X, Z) inside any ring (even-odd per ring, as ring_contains does for one point), vectorised."""
    import numpy as np
    inside = np.zeros(X.shape, bool)
    for ring in rings:
        c = np.zeros(X.shape, bool)
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, zi, xj, zj = float(ring[i][0]), float(ring[i][1]), float(ring[j][0]), float(ring[j][1])
            if zi != zj:
                c ^= ((zi > Z) != (zj > Z)) & (X < (xj - xi) * (Z - zi) / (zj - zi) + xi)
            j = i
        inside |= c
    return inside


def regions_dry_columns(box, sea, regions, step=DRY_SAMPLE_STEP, size=MAP):
    """{region id: how many sampled columns of the region stand at or above the sea}. `box(x0, z0, x1, z1)` is a (z, x) array of
    ROUNDED ground (tools/ground.py Ground.box), sampled on the global grid of multiples of `step`. A region is dry when it has a
    sampled column. NOT covered: a lake basin counts as dry here (only the sea is subtracted), and a dry patch narrower than
    `step` can be missed; the margin is wide (the smallest real count is thousands), but it is a sample, not a proof."""
    import numpy as np
    out = {}
    for rid, polys in regions.items():
        xs = [p[0] for ring in polys for p in ring]
        zs = [p[1] for ring in polys for p in ring]
        x0, x1 = max(int(min(xs)), 0), min(int(max(xs)), size - 1)
        z0, z1 = max(int(min(zs)), 0), min(int(max(zs)), size - 1)
        fx, fz = -(-x0 // step) * step, -(-z0 // step) * step      # first multiple of step at or after the box's corner
        if fx > x1 or fz > z1:
            out[rid] = 0
            continue
        h = np.asarray(box(x0, z0, x1, z1))[fz - z0::step, fx - x0::step]
        X, Z = np.meshgrid(fx + step * np.arange(h.shape[1]), fz + step * np.arange(h.shape[0]))
        out[rid] = int((_inside_any(polys, X, Z) & (h >= sea)).sum())
    return out


def region_rip_problems(rips, dry_columns):
    """[problem]: the owner's 2026-10-13 decision, 'every area in game should be capable of spawning a rift': a region with dry
    ground has a standing rip (a region with none is the drowned Jungle Isle, a note and not a fault)."""
    have = {r.get("region") for r in rips}
    return ["region %s has %d dry sampled columns and no rip" % (rid, n) for rid, n in sorted(dry_columns.items()) if n > 0 and rid not in have]


# ------------------------------------------------------------------------------------------------- the retired trail rips


def old_test_rip_positions(old_doc, retired):
    """[problem]: the retired trail rips' frame, click and outside against the dungeon records of 6249332e (`old_doc`), matched by
    legacy_dungeon, not by order. The retire function puts back the plane the RECORD says; this is what says the record is the
    plane the owner played."""
    bad = []
    by_dungeon = {r.get("legacy_dungeon"): r for r in retired}
    for d in old_doc["dungeons"]:
        old = d["rip"]
        new = by_dungeon.get(d["id"])
        if new is None:
            bad.append("retired rip for %s: gone" % d["id"])
            continue
        for k in ("frame", "click", "outside"):
            if new[k] != old[k]:
                bad.append("retired rip for %s: %s was %r, is %r" % (d["id"], k, old[k], new[k]))
    if len(by_dungeon) != len(old_doc["dungeons"]):
        bad.append("%d retired rips, 6249332e had %d" % (len(by_dungeon), len(old_doc["dungeons"])))
    return bad


def retired_record_problems(rips, retired, dungeon_ids):
    """[problem]: the retired rips against the decision 'the rips near old mine have to go', read from the records alone:
    none of them stands (not in `rips`, no standing rip is test_trail or shares a click), they are exactly the rips the dungeons
    had (`dungeon_ids`, data/dungeons.json), and none sits where a standing rip's footprint is (retiring one must not take
    blocks out from under another)."""
    bad = []
    standing_ids = {r["id"] for r in rips}
    for r in retired:
        if r["id"] in standing_ids:
            bad.append("%s: retired and standing at once" % r["id"])
    for r in rips:
        if r.get("kind") == "test_trail" or r.get("legacy_dungeon"):
            bad.append("%s: a standing rip is a trail rip (kind %s, legacy_dungeon %s)" % (r["id"], r.get("kind"), r.get("legacy_dungeon")))
    stood = {tuple(r["click"]): r["id"] for r in rips}
    for r in retired:
        if tuple(r["click"]) in stood:
            bad.append("%s: its click %s is rip %s's click" % (r["id"], r["click"], stood[tuple(r["click"])]))
        for s in rips:
            if box_gap(footprint(r), footprint(s)) <= 0:
                bad.append("%s: its footprint touches standing %s: retiring it would take blocks out from under that rip" % (r["id"], s["id"]))
    legacy = sorted(r.get("legacy_dungeon") for r in retired)
    if legacy != sorted(dungeon_ids):
        bad.append("the retired rips stand for %s, the dungeons are %s" % (legacy, sorted(dungeon_ids)))
    return bad


def parse_block_writes(lines):
    """(unconditional {(x, y, z): block}, conditional [((x, y, z), if_block, new_block)], other [line]) from the setblock, fill and
    `execute if block .. run setblock ..` lines of a function. Comments, blanks and forceload lines are ignored; anything else is
    returned in `other` so the caller can refuse it."""
    unc, cond, other = {}, [], []
    n = r"(-?\d+)"
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#") or re.match(r"forceload (add|remove)\b", s):
            continue
        m = re.fullmatch(r"setblock %s %s %s (\S+)" % (n, n, n), s)
        if m:
            unc[tuple(int(v) for v in m.groups()[:3])] = m.group(4)
            continue
        m = re.fullmatch(r"fill %s %s %s %s %s %s (\S+)" % ((n,) * 6), s)
        if m:
            x1, y1, z1, x2, y2, z2 = (int(v) for v in m.groups()[:6])
            for x in range(min(x1, x2), max(x1, x2) + 1):
                for y in range(min(y1, y2), max(y1, y2) + 1):
                    for z in range(min(z1, z2), max(z1, z2) + 1):
                        unc[(x, y, z)] = m.group(7)
            continue
        m = re.fullmatch(r"execute if block %s %s %s (\S+) run setblock %s %s %s (\S+)" % ((n,) * 6), s)
        if m and m.groups()[:3] == m.groups()[4:7]:
            cond.append((tuple(int(v) for v in m.groups()[:3]), m.group(4), m.group(8)))
            continue
        other.append(s)
    return unc, cond, other


def _base(block):
    return block.split("[")[0]


def retire_pack_problems(files, retired, themes, standing=None):
    """[problem]: what R16DR's rips/retire does to the world, found by READING the emitted functions and expected from the
    retired RECORDS (frame, restore, retired.ground) and data/dungeon_themes.json, never from tools/dungeon.py's helpers.

    For each retired rip, exactly one function called by rips/retire writes its plane, and
      * the plane (x0..x1, y..y+height-1, at frame.z) ends as rip.restore says, cell by cell, and nothing else is written
        unconditionally (a stray setblock would overwrite what is there);
      * each cell of its themed patch (the keys of retired.ground, one block under the frame's y) is put back to the recorded
        block ONLY `if block` it still holds one of the theme's own blocks (hull.floor, hull.wall, rip.scorch), so a re-apply
        never overwrites what something else has put there since; a cell with no line is allowed only where the recorded block
        is already one of the theme's blocks (a patch of the block that was there has nothing to put back);
      * nothing it writes is a cell a STANDING rip's rips/blocks_* function writes, nor a cell of `standing` (since 2026-10-14
        no rip stands; the caller passes every candidate's plane, ground and exit point, read from the records).
    `themes` is data/dungeon_themes.json's 'themes' object."""
    bad = []
    top = files.get(RIPS_DIR + "retire.mcfunction")
    if top is None:
        return ["rips/retire is not in the pack: R16DR has nothing to run, so the retired rips stay in the world"]
    called = re.findall(r"function " + re.escape(FN) + r"(rips/retire_[a-z0-9_]+)", top)
    if len(called) != len(retired) or len(set(called)) != len(called):
        bad.append("rips/retire calls %d distinct functions (%d calls) for %d retired rips" % (len(set(called)), len(called), len(retired)))
    parsed = {}
    for c in called:
        text = files.get("data/cobblers/function/dungeons/%s.mcfunction" % c)
        if text is None:
            bad.append("%s is called by rips/retire and is not in the pack" % c)
            continue
        parsed[c] = parse_block_writes(text.splitlines())
        if parsed[c][2]:
            bad.append("%s holds a command this audit does not read: %r" % (c, parsed[c][2][0]))
    standing_cells = set(standing or ())
    for path, text in files.items():
        if path.startswith(RIPS_DIR + "blocks_") and path.endswith(".mcfunction"):
            unc, cond, _ = parse_block_writes(text.splitlines())
            standing_cells |= set(unc) | {c for c, _t, _n in cond}
    used = set()
    for r in retired:
        f, rid = r["frame"], r["id"]
        owners = [c for c, (unc, _c, _o) in parsed.items() if (f["x0"], f["y"], f["z"]) in unc]
        if len(owners) != 1:
            bad.append("%s: its plane's first cell is written by %d of rips/retire's functions (want 1)" % (rid, len(owners)))
            continue
        used.add(owners[0])
        unc, cond, _ = parsed[owners[0]]
        plane = {(x, f["y"] + i, f["z"]): r["restore"][str(x)][i] for x in range(f["x0"], f["x1"] + 1) for i in range(f["height"])}
        for cell, want in sorted(plane.items()):
            if unc.get(cell) != want:
                bad.append("%s: plane cell %s ends as %s, rip.restore says %s" % (rid, cell, unc.get(cell), want))
        stray = sorted(set(unc) - set(plane))
        if stray:
            bad.append("%s: %d unconditional writes outside its plane, first %s" % (rid, len(stray), stray[0]))
        y = f["y"] - 1
        theme = (themes.get(r.get("scorch_theme")) or {}).get("hull") or {}
        theme_blocks = {_base(b) for b in (theme.get("floor"), theme.get("wall"), *(r.get("scorch") or {}).values()) if b}
        patch = {}
        for key, back in r["retired"]["ground"].items():
            x, z = (int(v) for v in key.split(","))
            patch[(x, y, z)] = back
        by_cell = {}
        for cell, test, new in cond:
            by_cell.setdefault(cell, []).append((test, new))
        for cell, back in sorted(patch.items()):
            got = by_cell.get(cell, [])
            if not got:
                if _base(back) not in theme_blocks:
                    bad.append("%s: patch cell %s is never put back to %s" % (rid, cell, back))
            elif len(got) != 1 or got[0][1] != back:
                bad.append("%s: patch cell %s is put back to %s, retired.ground says %s" % (rid, cell, got, back))
            elif _base(got[0][0]) not in theme_blocks:
                bad.append("%s: patch cell %s is replaced where it holds %s, which is none of the theme's blocks %s" % (rid, cell, got[0][0], sorted(theme_blocks)))
        for cell in sorted(set(by_cell) - set(patch)):
            bad.append("%s: a conditional write at %s is outside the patch" % (rid, cell))
        touched = (set(unc) | set(by_cell)) & standing_cells
        if touched:
            bad.append("%s: its retire writes %d cells a standing rip's blocks function writes, first %s" % (rid, len(touched), sorted(touched)[0]))
    if len(used) != len(called):
        bad.append("rips/retire calls %d functions that write no retired rip's plane" % (len(called) - len(used)))
    return bad


def retire_sweep_problems(files, retired):
    """[problem]: the sweep that kills the retired rips' entities (rips/entities_retired*): a force-load box over each retired
    click, a kill of an interaction and of an item_display per retired rip, and none of those tags is one a standing rip's
    entity is summoned with (the sweep would kill a rip that stands)."""
    bad = []
    texts = [t for p, t in files.items() if p.startswith(RIPS_DIR + "entities_retired")]
    if not texts:
        return ["rips/entities_retired is not in the pack: a retired rip's interaction and oval would stay standing"]
    blob = "\n".join(texts)
    boxes = [tuple(int(v) for v in m) for m in re.findall(r"forceload add (-?\d+) (-?\d+) (-?\d+) (-?\d+)", blob)]
    for r in retired:
        x, _y, z = r["click"]
        if not any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for b in boxes):
            bad.append("%s: no force-loaded box of the sweep covers its click (%d, %d)" % (r["id"], x, z))
    kills = {"interaction": set(), "item_display": set()}
    for kind, tag in re.findall(r"kill @e\[type=minecraft:(interaction|item_display),tag=([A-Za-z0-9_.]+)\]", blob):
        kills[kind].add(tag)
    if len(kills["interaction"]) != len(retired) or kills["interaction"] != kills["item_display"]:
        bad.append("the sweep kills %d interaction tags and %d oval tags for %d retired rips" % (len(kills["interaction"]), len(kills["item_display"]), len(retired)))
    standing = set()
    for p, t in files.items():
        if p.startswith(RIPS_DIR) and p.endswith(".mcfunction") and not p.startswith(RIPS_DIR + "entities_retired"):
            for tags in re.findall(r"summon minecraft:(?:interaction|item_display) [^\n]*?Tags:\[([^\]]*)\]", t):
                standing |= set(re.findall(r'"([^"]+)"', tags))
    hit = (kills["interaction"] | kills["item_display"]) & standing
    if hit:
        bad.append("the sweep kills tags a standing rip's entity is summoned with: %s" % sorted(hit))
    return bad


def retired_click_problems(files, retired, click_fn):
    """[problem]: a retired rip has no click that draws. `click_fn` is rip_click_functions(files, retired): the function an
    interaction at the retired click reaches through an advancement. It must be empty, and no function of the pack may summon an
    interaction at a retired click at all."""
    bad = ["%s: a click still reaches %s" % (rid, fn) for rid, fn in sorted(click_fn.items())]
    spots = {(r["id"], r["click"][0] + 0.5, r["click"][1], r["click"][2] + 0.5) for r in retired}
    for path, text in files.items():
        if not path.endswith(".mcfunction"):
            continue
        for m in re.finditer(r"summon minecraft:interaction (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)", text):
            sx, sy, sz = (float(v) for v in m.groups())
            for rid, x, y, z in spots:
                if abs(sx - x) < 0.01 and abs(sy - y) < 0.01 and abs(sz - z) < 0.01:
                    bad.append("%s: %s summons an interaction at its click" % (rid, path))
    return bad


def retire_step_problems(steps, retired):
    """[problem]: tools/reapply.py's R16DR runs the retire. `steps` is dungeon.reapply_steps(): (id, text, actions). With retired
    rips, R16DR runs rips/retire and the entity sweep, and R16DG (the shells) runs neither."""
    if not retired:
        return []
    bad = []
    by_id = {s[0]: s[2] for s in steps}
    for want in ("rips/retire", "rips/entities_retired"):
        if ("fn", FN + want) not in by_id.get("R16DR", []):
            bad.append("R16DR does not run %s: the retired rips stay in the world" % want)
        if ("fn", FN + want) in by_id.get("R16DG", []):
            bad.append("R16DG runs %s; the retire belongs to R16DR" % want)
    return bad


def run_siting(out):
    import ground as G
    g = G.load()
    doc = json.loads((DATA / "dungeon_rips.json").read_text(encoding="utf-8"))
    rips, retired = doc["rips"], doc.get("retired_rips") or []
    sea, lakes = water_world()
    pts = authored_points(skip_files=("data/dungeon_rips.json",), drop=_drop_rip_probes)
    if not pts:
        raise RuntimeError("the walk over data/ found no authored coordinate: every clearance would pass vacuously")
    regs = region_polygons()
    bad = siting_problems(rips, g, sea, lakes, pts, precinct_boxes(), regs)
    out["siting"] = {"rips": len(rips), "region_rips": sum(r["kind"] == "region" for r in rips), "retired_rips": len(retired),
                     "points_read": len(pts), "regions": len(regs)}
    dry = regions_dry_columns(g.box, sea, regs)
    out["siting"]["regions_with_dry_ground"] = sum(n > 0 for n in dry.values())
    bad += region_rip_problems(rips, dry)
    zones = json.loads((DATA / "rift_zones.json").read_text(encoding="utf-8"))
    bad += gated_zone_problems(rips, zones)
    dungeons = json.loads((DATA / "dungeons.json").read_text(encoding="utf-8"))["dungeons"]
    bad += retired_record_problems(rips, retired, [d["id"] for d in dungeons])
    import subprocess
    old = subprocess.run(["git", "show", "%s:data/dungeons.json" % OLD_TEST_RIPS_COMMIT], cwd=str(ROOT), capture_output=True, text=True)
    if old.returncode != 0:
        out["siting"]["old_positions"] = "NOT_EXECUTED: git show %s failed: %s" % (OLD_TEST_RIPS_COMMIT, old.stderr.strip()[:200])
    else:
        bad += old_test_rip_positions(json.loads(old.stdout), retired)
        out["siting"]["old_positions"] = "checked"
    bad += ["siting tool: " + p for p in sc_siting_tool_rejects_sites_that_break_a_rule(load_rips_module(None), g)]
    # notes for the owner, not rules of the spec. The keep-out box says it binds "the far south's own places"; a rip is not one
    notes = ["region %s has no dry ground (%d sampled columns) and no rip: nothing can stand there" % (rid, n)
             for rid, n in sorted(dry.items()) if n == 0 and rid not in {r.get("region") for r in rips}]
    fs = json.loads((DATA / "far_south.json").read_text(encoding="utf-8"))["rules"]["keep_out_box"]["box"]
    notes += ["%s: stands inside data/far_south.json rules.keep_out_box %s" % (r["id"], fs) for r in rips if box_gap(footprint(r), tuple(fs)) == 0]
    notes += ["%s: reachable only after %s %s (zone %s), as its record says" % (r["id"], r["reachable_after"].get("kind"), r["reachable_after"].get("threshold", ""),
                                                                           r["reachable_after"].get("zone")) for r in rips if r.get("reachable_after")]
    out["siting_notes"] = notes
    return bad


# ------------------------------------------------------------------------------------------------- gated zones (data/rift_zones.json)


def gated_zones_of(rip, rift_zones):
    """[zone id]: the rift zones with a pass (badges, a flag, a catch count) whose boxes the rip's footprint touches. Those zones span
    the whole height (rift_zones.json `y` -64..575), so a player short of the pass is turned back from every column of them."""
    out = []
    fp = footprint(rip)
    for zid, z in sorted((rift_zones.get("zones") or {}).items()):
        if not isinstance(z, dict) or not z.get("pass") or not z.get("boxes"):
            continue
        if any(box_gap(fp, tuple(b[:4])) == 0 for b in z["boxes"]):
            out.append(zid)
    return out


def gated_zone_problems(rips, rift_zones):
    """[problem]: the owner's 2026-10-13 decision, 'every area in game should be capable of spawning a rift, so leave it even if
    its gated'. A rip inside a gated rift zone is ALLOWED, and must say so: `reachable_after` names the zone and repeats its pass
    (kind, threshold, advancements, name) exactly as data/rift_zones.json has it. A rip outside every gated zone must not claim
    one (a stale claim is a wrong promise to the player). Read from the zones file here, not from tools/dungeon_rips.py."""
    bad = []
    zones = rift_zones.get("zones") or {}
    for r in rips:
        inside = gated_zones_of(r, rift_zones)
        ra = r.get("reachable_after")
        if not inside:
            if ra:
                bad.append("%s: declares reachable_after zone %s but its footprint is in no gated rift zone" % (r["id"], ra.get("zone")))
            continue
        if not ra:
            bad.append("%s: the footprint stands inside gated rift zone(s) %s and declares no reachable_after" % (r["id"], inside))
            continue
        if ra.get("zone") not in inside:
            bad.append("%s: reachable_after names zone %s, the footprint is in %s" % (r["id"], ra.get("zone"), inside))
            continue
        z = zones[ra["zone"]]
        want = dict(z["pass"])
        if ra.get("zone_name") != z.get("name"):
            bad.append("%s: reachable_after.zone_name %r, data/rift_zones.json names it %r" % (r["id"], ra.get("zone_name"), z.get("name")))
        for k in ("kind", "threshold", "advancements"):
            if k in want and ra.get(k) != want[k]:
                bad.append("%s: reachable_after.%s is %r, zone %s's pass has %r" % (r["id"], k, ra.get(k), ra["zone"], want[k]))
    return bad


# ------------------------------------------------------------------------------------------------- the simulator part


SPEC_CAPS = {20: 1, 25: 1, 30: 2, 35: 2, 40: 3, 45: 3, 50: 4, 55: 4, 60: 5, 62: 5, 100: 6}   # DUNGEON_DRAW.md 1: band by RCT cap
ALL_FLAGS = ("gym6_cleared", "gym8_cleared", "champion_cleared")
PLAYTEST_TAG = "cobblers.dg_playtest"       # DUNGEON_DRAW.md 5 and STATE: staging only
# the names the scenarios read; each is checked to exist in the pack before a scenario runs, so a rename fails closed
CONTRACT = ("dg.st", "dg.dun", "dg.rip", "dg.band", "dg.ptdun", "dg.up", "dg.own")
# functions the draw path never calls: a room, a shell, a block placement. They are 99 per cent of the pack's bytes.
SKIP_FILES = re.compile(r"/(room|shells|place)(/|\.)|/place/|/lure|/reset\.")


def load_sim():
    """(DW, FAKES, PS): tests/test_dungeon.py's simulator subclass, without building a pack. That module builds the whole
    dungeon pack when imported (minutes), so it is imported with the build stubbed and removed from sys.modules again, which
    leaves a later real import (pytest's own) to build as it always did."""
    sys.path.insert(0, str(ROOT / "tests"))
    import dungeon as D
    import pocket_sim as PS
    if "test_dungeon" in sys.modules:
        TD = sys.modules["test_dungeon"]
    else:
        real = D.build
        D.build = lambda doc, **kw: {}
        try:
            import test_dungeon as TD
        finally:
            D.build = real
            sys.modules.pop("test_dungeon", None)
    return TD.DW, TD.FAKES, PS


def load_module(mutation=None):
    """The dungeon generator: the real tools/dungeon.py, or a MUTATED COPY of its source compiled as module `dungeon_mut`.
    data/ is untouched in both: a mutation of the generator is the only kind that tests independence."""
    import dungeon as D
    if not mutation:
        return D
    old, new = MUTATIONS[mutation]["edit"]
    src = (ROOT / "tools" / "dungeon.py").read_text(encoding="utf-8")
    if src.count(old) != 1:
        raise RuntimeError("mutation %s: its target text occurs %d times in tools/dungeon.py (want 1); the generator changed, "
                           "update the mutation, do not loosen it" % (mutation, src.count(old)))
    mod = type(sys)("dungeon_mut")
    mod.__file__ = str(ROOT / "tools" / "dungeon.py")
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


class Env:
    """One simulated world over one built pack, shared by the scenarios (a fresh player and fresh slots for each)."""

    def __init__(self, files, doc, tmp):
        DW, FAKES, PS = load_sim()
        self.PS, self.doc = PS, doc
        self.ds = [d["id"] for d in doc["dungeons"]]
        self.shorts = {d["id"]: d["short"] for d in doc["dungeons"]}
        self.rips = doc["rips"]
        self.sig = doc["engine"]["sigils"]["ladder"]
        self.lockout = doc["engine"]["lockout_ticks"]
        self.keeper = doc["engine"]["keeper"]["period_ticks"]
        self.files = files
        out = Path(tmp)
        n = 0
        for path, text in files.items():
            if SKIP_FILES.search("/" + path):
                continue
            f = out / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
            n += 1
        self.written = n
        fakes = dict(FAKES)
        fakes["cobblers:levelcap/battle_check"] = ["$scoreboard players operation @s cobblers.lc_cap = @s capwant$(x)"]
        for s in doc_slots(doc):
            fakes["cobblers:dungeons/slot/s%d/reset" % s] = ["# the slot's block reset, not under test here"]
        w = DW(out, fakes)
        w.objectives |= {"cobblers.lc_cap", "tailend", "stale", "capwant"}
        w.boot()
        self.w = w
        blob = "\n".join(t for p, t in files.items() if p.endswith(".mcfunction"))
        self.missing = [o for o in CONTRACT if o not in blob]
        self.rip_fn = rip_click_functions(files, self.rips)
        self.n_players = 0

    def lk(self, did):
        return "dg.lk_%s" % self.shorts[did]

    def fresh(self):
        """Free every slot, restart the uptime well above any lockout, drop every player."""
        w = self.w
        for (h, o) in list(w.scores):
            if o == "dg.own":
                w.scores[(h, o)] = 0
        w.set("#up", "dg.up", 1_000_000)
        for p in list(w.players()):
            w.ents.remove(p)
        w.random_values.clear()

    def player(self, band_cap=20, flags=(), tags=(), sigils=200, sigil_band=None, at=None):
        self.n_players += 1
        r = at or self.rips[0]
        sb = sigil_band or SPEC_CAPS[band_cap]
        p = self.w.player("A%d" % self.n_players, "minecraft:overworld", tuple(r["outside"][:3]),
                          advancements=["cobblers:flag/%s" % f for f in flags])
        p.tags.update(tags)
        if sigils:
            p.inventory.append([self.sig[sb - 1]["item"], {"cobblers_dg_sigil": sb}, sigils])
        self.w.set(p.name, "capwant", band_cap)
        return p

    def sigil_count(self, p):
        return sum(i[2] for i in p.inventory if i[0] in {s["item"] for s in self.sig})

    def click(self, p, rip=None):
        r = rip or self.rips[0]
        self.w.call(self.rip_fn[r["id"]], self.PS.Ctx(p, p.dim, p.pos))

    def entered(self, p):
        """The dungeon id the last click opened for p, else None (refused)."""
        if self.w.get(p.name, "dg.st") != 1:
            return None
        n = self.w.get(p.name, "dg.dun")
        return self.ds[n - 1] if n else None

    def backout(self, p):
        """What the player does after the draw, in the way the game offers: the back rip, once the arrival has put them in the
        entry room (dg.st 2). The slot is freed by the run's own end (m/end), the sigil refunded. Time passes a keeper pass."""
        w = self.w
        w.set(p.name, "dg.st", 2)
        w.call("cobblers:dungeons/back", self.PS.Ctx(p, p.dim, p.pos))
        w.set("#up", "dg.up", w.get("#up", "dg.up") + self.keeper)

    def draws(self, p, n, rip=None):
        out = []
        for _ in range(n):
            self.click(p, rip)
            d = self.entered(p)
            out.append(d)
            if d is None:
                break
            self.backout(p)
        return out

    def last_door(self):
        """The short whose own door the last click called, from the simulator's call log (a refusal is logged too)."""
        for name, _who in reversed(self.w.calls):
            m = re.fullmatch(r"cobblers:dungeons/door/([a-z0-9]+)", name)
            if m and not m.group(1).startswith(("rip_", "refuse_", "go_")):
                return m.group(1)
        return None


def doc_slots(doc):
    """Global slot numbers 1..N: engine.slots.per_dungeon for each dungeon, in file order (data/dungeons.json engine.slots.why)."""
    return list(range(1, doc["engine"]["slots"]["per_dungeon"] * len(doc["dungeons"]) + 1))


def rip_click_functions(files, rips):
    """{rip id: reward function id}: the function a right-click on the rip's interaction runs, found the way
    the game finds it and without the generator's naming: the interaction summoned at the rip's click (in a rips/ function),
    the tag it carries that an advancement's click criterion listens for, and that advancement's reward."""
    listens = {}
    for path, text in files.items():
        if path.startswith("data/cobblers/advancement/dungeons/") and path.endswith(".json"):
            j = json.loads(text)
            crit = (j.get("criteria") or {}).get("click")
            if crit:
                nbt = crit["conditions"]["entity"][0]["predicate"].get("nbt", "")
                for t in re.findall(r'"([^"]+)"', nbt):
                    listens[t] = j["rewards"]["function"]
    summons = []
    for path, text in files.items():
        if "/rips/" in path and path.endswith(".mcfunction"):
            for m in re.finditer(r"summon minecraft:interaction (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) \{[^\n]*?Tags:\[([^\]]*)\]", text):
                summons.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), re.findall(r'"([^"]+)"', m.group(4))))
    out = {}
    for r in rips:
        x, y, z = r["click"]
        for sx, sy, sz, tags in summons:
            if abs(sx - (x + 0.5)) < 0.01 and abs(sy - y) < 0.01 and abs(sz - (z + 0.5)) < 0.01:
                fns = {listens[t] for t in tags if t in listens}
                if len(fns) == 1:
                    out[r["id"]] = fns.pop()
    return out


# ------------------------------------------------------------------------------------------------- the scenarios
# Each returns [problem]. The expectation is derived from the spec and the roster in the scenario, never from the generator.


def _permutation_windows(seq, want):
    """[problem]: every run of len(want) consecutive draws must be each wanted dungeon exactly once (least recently entered
    wins: with n candidates and nothing else changing, the draw is a rotation through all n before any repeat)."""
    n = len(want)
    bad = []
    for i in range(0, len(seq) - n + 1):
        if sorted(seq[i:i + n]) != sorted(want):
            bad.append("draws %d..%d are %s, not each of %s once" % (i + 1, i + n, seq[i:i + n], sorted(want)))
            break
    return bad


def sc_band_from_cap(env, expect):
    bad = []
    for cap, band in SPEC_CAPS.items():
        env.fresh()
        p = env.player(cap, ALL_FLAGS)
        env.click(p)
        if env.entered(p) is None:
            bad.append("cap %d: a click with the right sigil and every flag was refused" % cap)
            continue
        got = env.w.get(p.name, "dg.band")
        if got != band:
            bad.append("cap %d: the band is %s, the spec's is %d" % (cap, got, band))
    return bad


def sc_reachable_sets(env, expect):
    """For every flag set and every band: the dungeons the draw can open are EXACTLY those the spec makes eligible (first_band
    at or under the band, the gate held), and each is reached within three rotations."""
    bad = []
    caps = (20, 30, 40, 50, 60, 100)
    flagsets = [()] + [(f,) for f in ALL_FLAGS] + [("gym6_cleared", "gym8_cleared"), ALL_FLAGS]
    for fl in flagsets:
        for cap in caps:
            band = SPEC_CAPS[cap]
            want = eligible(band, set(fl), expect)
            env.fresh()
            p = env.player(cap, fl)
            got = env.draws(p, 3 * len(want) + 2)
            if None in got:
                bad.append("band %d flags %s: a click was refused with a sigil and %d eligible dungeons" % (band, list(fl), len(want)))
                continue
            if set(got) != want:
                bad.append("band %d flags %s: drew %s; extra %s, never drawn %s"
                           % (band, list(fl), sorted(set(got)), sorted(set(got) - want), sorted(want - set(got))))
            bad += ["band %d flags %s: %s" % (band, list(fl), m) for m in _permutation_windows(got, want)]
    return bad


def sc_every_band_has_a_candidate(env, expect):
    bad = []
    for band in range(1, 7):
        if not eligible(band, set(ALL_FLAGS), expect):
            bad.append("band %d has no candidate in the roster" % band)
    return bad


def sc_lockout_skips(env, expect):
    bad = []
    band1 = sorted(eligible(1, set(), expect))
    for locked in band1:
        env.fresh()
        p = env.player(20)
        up = env.w.get("#up", "dg.up")
        env.w.set(p.name, env.lk(locked), up - 1000)          # entered 1000 ticks ago, the lockout is an hour
        got = env.draws(p, 2 * len(band1))
        if None in got:
            bad.append("%s locked out: a click was refused although four others are open" % locked)
        elif locked in got:
            bad.append("%s locked out an hour and drawn anyway: %s" % (locked, got))
        elif set(got) != set(band1) - {locked}:
            bad.append("%s locked out: the others drawn were %s" % (locked, sorted(set(got))))
        env.w.set(p.name, env.lk(locked), env.w.get("#up", "dg.up") - 10 * env.lockout)   # long past
        if locked not in env.draws(p, 2 * len(band1)):
            bad.append("%s was never drawn again after its lockout ran out" % locked)
    # every open dungeon locked out: the click is refused, nothing is taken and it is not a draw
    env.fresh()
    p = env.player(20)
    up = env.w.get("#up", "dg.up")
    for d in band1:
        env.w.set(p.name, env.lk(d), up - 1000)
    before = env.sigil_count(p)
    env.click(p)
    if env.entered(p) is not None:
        bad.append("every band-1 dungeon locked out and a click still opened %s" % env.entered(p))
    if env.sigil_count(p) != before:
        bad.append("a click refused for the lockout took a sigil")
    return bad


def sc_full_falls_through(env, expect):
    bad = []
    band1 = sorted(eligible(1, set(), expect))
    per = env.doc["engine"]["slots"]["per_dungeon"]
    for full in band1:
        env.fresh()
        idx = env.ds.index(full) + 1
        for k in range(per):                                    # the playtest path names the dungeon: it fills the slots
            t = env.player(20, tags=(PLAYTEST_TAG,))
            env.w.set(t.name, "dg.ptdun", idx)
            env.click(t)
            if env.entered(t) != full:
                bad.append("could not seat occupant %d in %s through the playtest path: %s" % (k + 1, full, env.entered(t)))
                break
        p = env.player(20)
        got = env.draws(p, 2 * len(band1))
        if None in got or full in got or set(got) != set(band1) - {full}:
            bad.append("%s full: a regular player drew %s" % (full, got))
    env.fresh()
    idxs = [env.ds.index(d) + 1 for d in band1]
    for idx in idxs:
        for _ in range(per):
            t = env.player(20, tags=(PLAYTEST_TAG,))
            env.w.set(t.name, "dg.ptdun", idx)
            env.click(t)
    p = env.player(20)
    before = env.sigil_count(p)
    env.click(p)
    if env.entered(p) is not None:
        bad.append("every band-1 dungeon full and a click still opened %s" % env.entered(p))
    if env.sigil_count(p) != before:
        bad.append("a click refused for busy slots took a sigil")
    return bad


def sc_ties_are_random(env, expect, trials=400):
    """Five never-drawn band-1 dungeons tie. Over `trials` independent first clicks each must come up about trials/5 times.
    The bound is 5 standard deviations of a fair draw (sd = sqrt(400 * .2 * .8) = 8 around 80), not a number fitted to the data."""
    band1 = sorted(eligible(1, set(), expect))
    n = len(band1)
    env.fresh()
    counts = {d: 0 for d in band1}
    rolls0 = len(env.w.random_log)
    for _ in range(trials):
        p = env.player(20)
        env.click(p)
        d = env.entered(p)
        if d is not None:
            counts[d] += 1
            env.backout(p)
        env.w.ents.remove(p)
    bad = []
    mean = trials / float(n)
    sd = (trials * (1.0 / n) * (1 - 1.0 / n)) ** 0.5
    for d, c in counts.items():
        if abs(c - mean) > 5 * sd:
            bad.append("tie-break: %s was drawn %d of %d first clicks; a fair draw gives %.0f +- %.0f" % (d, c, trials, mean, 5 * sd))
    if len(env.w.random_log) - rolls0 < trials // 2:
        bad.append("tie-break: %d random rolls for %d tied draws" % (len(env.w.random_log) - rolls0, trials))
    return bad


def _door_dungeon(env, short):
    return next((d for d, s in env.shorts.items() if s == short), None)


def sc_refused_click_is_not_a_draw(env, expect):
    """A click that is refused takes nothing and does not count as a draw: with the same roll the next click that is let
    through opens the SAME dungeon the refused click would have, whatever the refusal was."""
    bad = []
    for label, weak in (("no sigil", False), ("a lower band's sigil", True)):
        env.fresh()
        cap = 30                                            # band 2
        p = env.player(cap, sigils=0)
        if weak:
            p.inventory.append([env.sig[0]["item"], {"cobblers_dg_sigil": 1}, 3])
        before = env.sigil_count(p)
        env.w.random_values[:] = [123456789]
        env.click(p)
        refused_to = _door_dungeon(env, env.last_door())
        if env.entered(p) is not None:
            bad.append("%s: the click was not refused" % label)
            continue
        if env.sigil_count(p) != before:
            bad.append("%s: a refused click changed the sigils from %d to %d" % (label, before, env.sigil_count(p)))
        if env.w.get(p.name, "dg.rip"):
            bad.append("%s: a refused click recorded a way out" % label)
        # one more refusal. Not more: with n candidates, n refusals that each stamped would stamp every one of them in turn and
        # bring the oldest stamp round to the first again, hiding the fault (the first draft of this check did exactly that)
        env.w.random_values[:] = [123456789]
        env.click(p)
        p.inventory[:] = [[env.sig[1]["item"], {"cobblers_dg_sigil": 2}, 5]]
        env.w.random_values[:] = [123456789]
        env.click(p)
        opened = env.entered(p)
        if opened is None:
            bad.append("%s: with the right sigil the click was still refused" % label)
        elif opened != refused_to:
            bad.append("%s: the refused click had drawn %s, the next click with the same roll opened %s: the refusal counted as a draw"
                       % (label, refused_to, opened))
    return bad


def sc_random_walk_matches_the_spec_model(env, expect, seeds=6, steps=160):
    """A reference model written from DUNGEON_DRAW.md 2.2-2.3 alone (eligible by band and gate; open = not locked out, a free
    slot; the oldest stamp among the open wins, never drawn oldest; nothing open falls back to the eligible ones, whose door
    refuses) is driven by random sequences of clicks, back-outs, lockouts, time and other players taking slots, beside the
    generated functions. At every click the dungeon the draw reached must be one the model allows, and the click must open
    exactly when the model says something is open. This reaches combinations no hand-written scenario names."""
    import random
    bad = []
    per = env.doc["engine"]["slots"]["per_dungeon"]
    for seed in range(seeds):
        rng = random.Random(seed)
        env.fresh()
        cap = rng.choice([20, 30, 40, 50, 60, 100])
        band = SPEC_CAPS[cap]
        flags = tuple(f for f in ALL_FLAGS if rng.random() < 0.6)
        elig = eligible(band, set(flags), expect)
        p = env.player(cap, flags)
        up = lambda: env.w.get("#up", "dg.up")                    # noqa: E731
        stamp, lock, occ, occupants, inrun = {}, {}, {d: 0 for d in env.ds}, [], None
        for step in range(steps):
            op = rng.choice(["click", "click", "click", "back", "time", "lock", "occupy", "release"])
            tag = "seed %d step %d (%s, band %d, flags %s)" % (seed, step, op, band, list(flags))
            if op == "time":
                env.w.set("#up", "dg.up", up() + rng.choice([20, 500, 40000, 80000]))
            elif op == "lock":
                d = rng.choice(sorted(elig))
                s = up() - rng.choice([0, 1000, 71000, 72000, 73000, 200000])
                env.w.set(p.name, env.lk(d), s)
                lock[d] = s
            elif op == "occupy":
                d = rng.choice(sorted(elig))
                if occ[d] + (1 if inrun == d else 0) < per:
                    t = env.player(20, tags=(PLAYTEST_TAG,))
                    env.w.set(t.name, "dg.ptdun", env.ds.index(d) + 1)
                    env.click(t)
                    if env.entered(t) != d:
                        bad.append("%s: the playtest occupant could not take a free slot of %s: %s" % (tag, d, env.entered(t)))
                        return bad
                    occ[d] += 1
                    occupants.append((d, t))
            elif op == "release" and occupants:
                d, t = occupants.pop(rng.randrange(len(occupants)))
                env.backout(t)
                occ[d] -= 1
            elif op == "back" and inrun:
                env.backout(p)
                inrun = None
            elif op == "click":
                before = [env.w.get(p.name, o) for o in ("dg.run", "dg.slot", "dg.dun", "dg.rip")] + [env.sigil_count(p)]
                env.click(p)
                got, door = env.entered(p), _door_dungeon(env, env.last_door())
                if inrun:
                    after = [env.w.get(p.name, o) for o in ("dg.run", "dg.slot", "dg.dun", "dg.rip")] + [env.sigil_count(p)]
                    if after != before:
                        bad.append("%s: a click by a player already in a run changed their run, slot, dungeon, rip or sigils: %s -> %s"
                                   % (tag, before, after))
                        return bad
                    continue
                locked = {d for d in elig if d in lock and 0 <= up() - lock[d] < env.lockout}
                free = {d for d in elig if occ[d] < per}
                openset = (elig - locked) & free
                pool = openset or elig
                oldest = min((stamp.get(d, -1) for d in pool))
                allowed = {d for d in pool if stamp.get(d, -1) == oldest}
                if door not in allowed:
                    bad.append("%s: the draw reached %s; the model allows %s (open %s, locked %s, full %s, stamps %s)"
                               % (tag, door, sorted(allowed), sorted(openset), sorted(locked), sorted(d for d in elig if occ[d] >= per),
                                  {d: stamp[d] for d in sorted(stamp)}))
                    return bad
                if bool(openset) != (got is not None):
                    bad.append("%s: the model has %d open dungeons, the click %s" % (tag, len(openset), "opened %s" % got if got else "was refused"))
                    return bad
                if got is not None:
                    stamp[got] = up()
                    inrun = got
    return bad


def sc_playtest_path(env, expect):
    bad = []
    ab = env.ds.index("ash_bell") + 1
    env.fresh()
    p = env.player(60, tags=(PLAYTEST_TAG,))
    env.w.set(p.name, "dg.ptdun", ab)
    env.click(p)
    if env.entered(p) != "ash_bell":
        bad.append("the playtest tag with dg.ptdun = ash_bell opened %s (gate bypass is the playtest path)" % env.entered(p))
    env.fresh()
    q = env.player(60)
    env.w.set(q.name, "dg.ptdun", ab)
    got = env.draws(q, 12)
    if "ash_bell" in got:
        bad.append("without the playtest tag, dg.ptdun forced or opened a gated dungeon: %s" % got)
    return bad


def sc_every_rip_draws_and_leaves_by_itself(env, expect):
    bad = []
    if len(env.rip_fn) != len(env.rips):
        bad.append("%d of %d rips have a click that reaches a function (an interaction at the click carrying a tag an advancement "
                   "listens for)" % (len(env.rip_fn), len(env.rips)))
    if len(set(env.rip_fn.values())) != len(env.rip_fn):
        bad.append("two rips share a click function")
    for k, r in enumerate(env.rips, 1):
        if r["id"] not in env.rip_fn:
            continue
        env.fresh()
        p = env.player(20)
        p.pos = [0.5, 200.0, 0.5]
        have = env.sigil_count(p)
        env.click(p, r)
        d = env.entered(p)
        if d is None:
            bad.append("%s: a click with a sigil at band 1 opened nothing" % r["id"])
            continue
        if env.w.get(p.name, "dg.rip") != k:
            bad.append("%s: dg.rip is %s, its place in data/dungeon_rips.json is %d" % (r["id"], env.w.get(p.name, "dg.rip"), k))
        if env.sigil_count(p) != have - 1:
            bad.append("%s: one entry took %d sigils" % (r["id"], have - env.sigil_count(p)))
        env.backout(p)
        want = [float(v) for v in r["outside"][:3]]
        if p.dim != OW or any(abs(a - b) > 0.01 for a, b in zip(p.pos, want)):
            bad.append("%s: the way out left the player at %s in %s, not at the rip's outside %s" % (r["id"], [round(v, 2) for v in p.pos], p.dim, want))
        if env.sigil_count(p) != have:
            bad.append("%s: the back rip did not refund the sigil (%d of %d)" % (r["id"], env.sigil_count(p), have))
    return bad


SCHED_DIR = "data/cobblers/function/rips/"      # the scheduler's pack (cobblers_rips), merged into env.files by run_draw


def window_box(r):
    """(x0, y0, z0, x1, y1, z1) round a rip, from its record: the plane's middle column +-4, one block behind the plane to five
    in front, the ground under it to six over it (DUNGEON_DRAW.md 2.6's 9 x 7 window, with the height a player stands in)."""
    f = r["frame"]
    mid = (f["x0"] + f["x1"]) // 2
    return (mid - 4, f["y"] - 2, f["z"] - 1, mid + 4, f["y"] + 6, f["z"] + 5)


def _in_box(b, x, y, z):
    return b[0] <= x < b[3] + 1 and b[1] <= y < b[4] + 1 and b[2] <= z < b[5] + 1


def sc_no_rip_stands(env, expect):
    """Since 2026-10-14 no rip STANDS (the owner: "placing possible spawn locations and then randomly having them appear"): the
    dungeon pack holds no one-shot placement (rips/place, rips/blocks_*), and no function outside the scheduler's pack summons a
    click or an oval in any candidate's window, so a rip is there only while the scheduler holds it open. The candidates and
    their windows are read from data/dungeon_rips.json here."""
    files, bad = env.files, []
    for path in sorted(files):
        if re.search(r"/function/dungeons/rips/(place|blocks_[a-z0-9_]+)\.mcfunction$", path):
            bad.append("the dungeon pack still holds %s: a one-shot placement of a rip" % path)
    _rips, cands, _s, _h = scheduler_inputs()
    boxes = [(r["id"], window_box(r)) for _i, r in cands]
    for path, text in files.items():
        if path.startswith(SCHED_DIR) or not path.endswith(".mcfunction"):
            continue
        for m in re.finditer(r"summon minecraft:(interaction|item_display) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)", text):
            x, y, z = (float(v) for v in m.groups()[1:])
            for rid, b in boxes:
                if _in_box(b, x, y, z):
                    bad.append("%s: %s summons a %s in its window, so it stands whether or not it is open" % (rid, path, m.group(1)))
    if not any(p.startswith(SCHED_DIR) for p in files):
        bad.append("the scheduler's pack is not in the files under audit: no rip can ever open")
    return bad


def sc_closed_rips_show_nothing(env, expect):
    """A closed candidate shows nothing: every function outside the scheduler's pack that makes particles inside a candidate's
    window is run, on a world where the scheduler is armed and every rip closed and a player stands at every candidate's exit
    point, and no particle may appear in any candidate's window. (The motes belong to an OPEN rip; at a closed one they are a
    rip that is not there, and they give the whole pool away.)"""
    sys.path.insert(0, str(ROOT / "tests"))
    import mcfunction_sim as SIM
    _rips, cands, _s, _h = scheduler_inputs()
    boxes = [(r["id"], window_box(r)) for _i, r in cands]
    fns = {}
    for path, text in env.files.items():
        m = re.fullmatch(r"data/([^/]+)/function/(.+)\.mcfunction", path)
        if m:
            fns["%s:%s" % m.groups()] = text.splitlines()
    emitters = []
    for fid, lines in fns.items():
        if fid.startswith(SCHED_FN):
            continue
        for ln in lines:
            m = re.search(r"positioned (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) .*\bparticle ", ln)
            if m and any(_in_box(b, *(float(v) for v in m.groups())) for _rid, b in boxes):
                emitters.append(fid)
                break
    if not emitters:
        return []
    w = SIM.CellWorld(fns, terrain=terrain_block, loaded=lambda x, z: True)
    w.objectives |= {"dg.rip", "dg.st"}
    S = load_scheduler(None)
    _f, stags = scheduler_pack(S)
    for f in stags.get("load", []):
        w.function(f, w.server())
    for _i, r in cands:
        w.add_player([float(v) for v in r["outside"][:3]])
    for fid in emitters:
        w.function(fid, w.server())
    shown = {}
    for _t, (name, pos) in w.logged("particle"):
        for rid, b in boxes:
            if _in_box(b, *pos):
                shown.setdefault(rid, set()).add(name)
    return ["%d of %d candidates are closed and show particles (%s) from %s, first %s"
            % (len(shown), len(cands), sorted(set().union(*shown.values())), sorted(emitters), sorted(shown)[:3])] if shown else []


def sc_retired_rips_are_taken_out(env, expect):
    """The 13 trail rips retired by the owner (2026-10-13): R16DR's rips/retire puts back each one's recorded plane and patch,
    the entity sweep kills its interaction and oval, and nothing in the pack still draws from its click. The records are read from
    data/dungeon_rips.json and the theme blocks from data/dungeon_themes.json HERE, not from the generator's doc."""
    retired = json.loads((DATA / "dungeon_rips.json").read_text(encoding="utf-8")).get("retired_rips") or []
    themes = json.loads((DATA / "dungeon_themes.json").read_text(encoding="utf-8"))["themes"]
    if not retired:
        return ["data/dungeon_rips.json has no retired_rips: the owner's decision of 2026-10-13 is not in the record"]
    _rips, cands, _s, _h = scheduler_inputs()
    standing = set().union(*({exit_cell(r)} | allowed_cells(r) for _i, r in cands))
    bad = retire_pack_problems(env.files, retired, themes, standing)
    bad += retire_sweep_problems(env.files, retired)
    bad += retired_click_problems(env.files, retired, rip_click_functions(env.files, retired))
    return bad


def sc_reapply_wires_r16dr(env, expect, mod):
    bad = []
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    if "DG.reapply_steps()" not in src:
        bad.append("tools/reapply.py does not extend its step list with dungeon.reapply_steps()")
    steps = mod.reapply_steps(env.doc)
    r16dr = [s for s in steps if s[0] == "R16DR"]
    if len(r16dr) != 1:
        bad.append("%d R16DR steps" % len(r16dr))
    else:
        # since 2026-10-14 R16DR places no rip: it takes the retired ones out and ARMS the scheduler, i.e. runs the function the
        # scheduler's pack itself runs at load (its minecraft:load entry, or a function that entry calls)
        m = re.search(r"(\d+) (?:candidate )?rips", r16dr[0][1])
        if not m or int(m.group(1)) != len(env.rips):
            bad.append("R16DR says %s rips, data/dungeon_rips.json has %d" % (m and m.group(1), len(env.rips)))
        acts = r16dr[0][2]
        placing = [a for a in acts if a[0] == "fn" and re.search(r"rips/(place|blocks_)", a[1])]
        if placing:
            bad.append("R16DR still runs %s: a rip placed for good" % placing)
        _f, stags = scheduler_pack(load_scheduler(None))
        arming = set(stags.get("load", []))
        for f in list(arming):
            arming |= set(re.findall(r"^function (\S+)$", "\n".join(_f.get(f, [])), re.M))
        if not any(a[0] == "fn" and a[1] in arming for a in acts):
            bad.append("R16DR runs none of the functions the scheduler's own load entry runs %s: the scheduler is not armed by the "
                       "re-apply" % sorted(arming))
    retired = json.loads((DATA / "dungeon_rips.json").read_text(encoding="utf-8")).get("retired_rips") or []
    bad += retire_step_problems(steps, retired)
    return bad


def sc_record_matches_roster(env, expect):
    """data/dungeons.json carries, for each dungeon, the first_band and gate the roster proposes (the owner took them as written)."""
    bad = []
    for d in env.doc["dungeons"]:
        fb, flag = expect[d["id"]]
        if d.get("first_band") != fb:
            bad.append("%s: first_band %s, the roster's is %d" % (d["id"], d.get("first_band"), fb))
        want = "cobblers:flag/%s" % flag if flag else None
        if d.get("gate_flag") != want:
            bad.append("%s: gate_flag %s, the roster's is %s" % (d["id"], d.get("gate_flag"), want))
    if env.lockout != 72000:
        bad.append("engine.lockout_ticks is %d, the spec's one hour of uptime is 72000" % env.lockout)
    return bad


SCENARIOS = (
    ("record_matches_roster", sc_record_matches_roster),
    ("every_band_has_a_candidate", sc_every_band_has_a_candidate),
    ("band_from_cap", sc_band_from_cap),
    ("reachable_sets", sc_reachable_sets),
    ("lockout_skips", sc_lockout_skips),
    ("full_falls_through", sc_full_falls_through),
    ("ties_are_random", sc_ties_are_random),
    ("refused_click_is_not_a_draw", sc_refused_click_is_not_a_draw),
    ("random_walk_matches_the_spec_model", sc_random_walk_matches_the_spec_model),
    ("playtest_path", sc_playtest_path),
    ("every_rip_draws_and_leaves_by_itself", sc_every_rip_draws_and_leaves_by_itself),
    ("no_rip_stands", sc_no_rip_stands),
    ("closed_rips_show_nothing", sc_closed_rips_show_nothing),
    ("retired_rips_are_taken_out", sc_retired_rips_are_taken_out),
)


# ------------------------------------------------------------------------------------------------- mutations of the GENERATOR
# Each edits ONE spot of tools/dungeon.py's source (data/ untouched) and must make run_draw return problems.

_STAMP = '"scoreboard players operation @s %s = #up %s" % (dr_obj(d), O["up"]),'

MUTATIONS = {
    "floor_one_band_low": {
        "why": "a dungeon is drawn one band below its first_band (the < for <= slip)",
        "edit": ('fb, gf = d.get("first_band", 1), d.get("gate_flag")', 'fb, gf = d.get("first_band", 1) - 1, d.get("gate_flag")')},
    "floor_one_band_high": {
        "why": "a dungeon is not drawn at its own first_band (the <= for < slip)",
        "edit": ('fb, gf = d.get("first_band", 1), d.get("gate_flag")', 'fb, gf = d.get("first_band", 1) + 1, d.get("gate_flag")')},
    "lockout_dropped": {
        "why": "the draw no longer skips a dungeon the player is locked out of",
        "edit": ('matches 0..%d run "', 'matches -2147483648..-%d run "')},
    "full_dropped": {
        "why": "the draw no longer skips a dungeon with no free slot",
        "edit": ('if score #f%d %s matches 1 unless', 'if score #f%d %s matches 0..1 unless')},
    "gate_inverted": {
        "why": "a gated dungeon is drawn only WITHOUT its flag",
        "edit": ('if entity @s[advancements={%s=true}] run scoreboard players set #c', 'unless entity @s[advancements={%s=true}] run scoreboard players set #c')},
    "gate_open_to_all": {
        "why": "the playtest bypass opens every gate to everyone who is not a playtester",
        "edit": ('if entity @s[tag=%s] run scoreboard players set #c%d', 'if entity @s[tag=!%s] run scoreboard players set #c%d')},
    "never_drawn_is_youngest": {
        "why": "a dungeon never drawn counts as the most recent, so the one just drawn wins again",
        "edit": ('"scoreboard players set #a%d %s 2147483000" % (i, O["t"]),', '"scoreboard players set #a%d %s 0" % (i, O["t"]),')},
    "refusal_stamps": {
        "why": "a refused click stamps the dungeon it drew, so the refusal counts as a draw",
        "edit": ('"execute unless score #why %s matches 0 run return run function %s" % (O["t"], F("door/refuse_%s" % sh)),',
                 _STAMP + '\n               "execute unless score #why %s matches 0 run return run function %s" % (O["t"], F("door/refuse_%s" % sh)),')},
    "backout_not_counted": {
        "why": "the draw is not stamped at the go, so a backed-out dungeon can be drawn again at once (a free re-roll)",
        "edit": (_STAMP, '"# mutated: no stamp",')},
    "way_out_is_the_dungeons": {
        "why": "the run does not remember which rip it was entered by, so m/out falls back to one fixed rip per dungeon",
        "edit": ('"execute if score #rip %s matches 1.. run scoreboard players operation @s %s = #rip %s" % (O["t"], O["rip"], O["t"]),',
                 '"# mutated: dg.rip not recorded",')},
    "tie_is_not_random": {
        "why": "the tie-break roll is always 0, so the first tied dungeon always wins",
        "edit": ('random value 0..1073741823', 'random value 0..0')},
    "retire_skips_the_plane": {
        "why": "a retire function that does not put the rip's plane back (rips/retire_<name> holds the patch only)",
        "edit": ('    out = rip_plane_lines(r)\n    for x, y, z, blk in rip_scorch_cells(r):\n        back = ret["ground"]',
                 '    out = []\n    for x, y, z, blk in rip_scorch_cells(r):\n        back = ret["ground"]')},
    "retire_skips_the_patch": {
        "why": "a retire function that does not put the themed ground under the oval back (rips/retire_<name> holds the plane only)",
        "edit": ('    for x, y, z, blk in rip_scorch_cells(r):\n        back = ret["ground"]',
                 '    for x, y, z, blk in []:\n        back = ret["ground"]')},
    "retire_overwrites_the_patch": {
        "why": "a retire function that sets the patch back unconditionally, over whatever stands there now",
        "edit": ('out.append("execute if block %d %d %d %s run setblock %d %d %d %s" % (x, y, z, blk, x, y, z, back))',
                 'out.append("setblock %d %d %d %s" % (x, y, z, back))')},
}

# the mutations of the retire (rip_retire_lines): each is also run against the retire checker alone, on the functions the mutated
# module's own rip_retire_lines emits (tests/test_dungeon_draw_audit.py), because the full draw run that catches them takes minutes
RETIRE_MUTATIONS = ("retire_skips_the_plane", "retire_skips_the_patch", "retire_overwrites_the_patch")


# ------------------------------------------------------------------------------------------------- the siting TOOL, on sites of my own


RIPS_MUTATIONS = {
    "clearance_shrunk": {
        "why": "tools/dungeon_rips.py holds a site to 3 blocks from an authored coordinate instead of 30",
        "edit": ("CLEARANCE = 30\n", "CLEARANCE = 3\n")},
    "precinct_ignored": {
        "why": "tools/dungeon_rips.py no longer refuses a site beside a spawn-free zone or a town",
        "edit": ("        if box_distance(win, b) < CLEARANCE:", "        if False and box_distance(win, b) < CLEARANCE:")},
}


def load_rips_module(mutation=None):
    import dungeon_rips as R
    if not mutation:
        return R
    old, new = RIPS_MUTATIONS[mutation]["edit"]
    src = (ROOT / "tools" / "dungeon_rips.py").read_text(encoding="utf-8")
    if src.count(old) != 1:
        raise RuntimeError("mutation %s: its target text occurs %d times in tools/dungeon_rips.py (want 1)" % (mutation, src.count(old)))
    mod = type(sys)("dungeon_rips_mut")
    mod.__file__ = str(ROOT / "tools" / "dungeon_rips.py")
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


def sc_siting_tool_rejects_sites_that_break_a_rule(R, g=None):
    """tools/dungeon_rips.py is the tool that SITES the rips. Here it is handed sites made to break one rule each, with the
    ground from tools/ground.py, and must name each. The control is a real region rip with nothing near it. The distances are
    chosen from the spec's 30 and 300 (DUNGEON_DRAW.md 2.6), never from the tool's own constants."""
    import ground as G
    g = g or G.load()
    rips = json.loads((DATA / "dungeon_rips.json").read_text(encoding="utf-8"))["rips"]
    base = next(r for r in rips if r["id"] == "rip_pine_isles")
    f, rid, region = base["frame"], base["id"], base["region"]
    mx, z = (f["x0"] + f["x1"]) // 2, f["z"]
    polys = region_polygons()
    bad = []

    def run(frame=None, pts=(), boxes=(), polys_=None, others=(), reg=region):
        return R.site_problems(g, rid, reg, frame or f, list(pts), polys_ or polys, list(boxes), list(others))

    if run():
        bad.append("control: the real rip with no neighbours is refused: %s" % run()[:2])
    edge = mx + 4      # the footprint's east edge is x1 = mx + 2; the tool's own window runs to mx + 4: points beyond it are further from both
    if not any("authored" in p for p in run(pts=[(edge + 15.0, z + 2.0, "f")])):
        bad.append("an authored coordinate 15 blocks from the window is not refused (the spec's clearance is 30)")
    if run(pts=[(edge + 45.0, z + 2.0, "f")]):
        bad.append("an authored coordinate 45 blocks away is refused")
    if not run(boxes=[(edge + 1, z - 10, edge + 40, z + 10, "town x")]):
        bad.append("a town footprint one block from the window is not refused")
    if run(boxes=[(edge + 60, z - 10, edge + 90, z + 10, "town x")]):
        bad.append("a town footprint 60 blocks away is refused")
    if not run(polys_=polys, reg="the_rift"):
        bad.append("a rip outside the region it names is not refused")
    if not any("spread" in p for p in run(others=[("rip_other", mx + 100, z)])):
        bad.append("a region rip 100 blocks from another is not refused (the spread is 300)")
    if run(others=[("rip_other", mx + 400, z)]):
        bad.append("a region rip 400 blocks from another is refused")
    # wet ground: the first 9 x 7 window of flat sea floor found on a coarse walk of the heightmap, a column under the sea
    sea = water_world()[0]
    wet = None
    for zz in range(200, 8000, 64):
        for xx in range(200, 8000, 64):
            h = g.box(xx - 4, zz - 1, xx + 4, zz + 5)
            if int(h.max()) == int(h.min()) and int(h.min()) < sea - 10:
                wet = (xx, zz, int(h.min()))
                break
        if wet:
            break
    if wet is None:
        bad.append("NOT_EXECUTED: no flat sea-floor window found to test the dry rule")
    else:
        wf = {"x0": wet[0] - 2, "x1": wet[0] + 2, "z": wet[1], "y": wet[2] + 1, "height": 4}
        if not run(frame=wf):
            bad.append("a rip on the sea floor at (%d, %d), y%d, is not refused" % (wet[0], wet[1], wet[2]))
    return bad


def run_draw(mod, tmp):
    """(problems by scenario, facts): build the pack with `mod`, run every scenario on the simulator."""
    t0 = time.time()
    doc = mod.load()
    # build() opens with problems(doc), the whole record's validator (about 130 s of the warm build: the rooms' walk checks).
    # It validates data, not the draw, and the builder's own tests run it; it is skipped here and the two validators that
    # concern the draw's and the rips' inputs are run instead (below). Restored in `finally`: the module is shared.
    real_problems = mod.problems
    mod.problems = lambda doc, **kw: []
    try:
        files = mod.build(doc)
    finally:
        mod.problems = real_problems
    # since 2026-10-14 a rip's click and oval are summoned by the scheduler's RUNTIME pack (cobblers_rips), which the server loads
    # beside the dungeon pack: its functions join the files under audit (not its load tag, which would replace the dungeon's), so
    # the click a draw starts from is the one the game will have. Built with the same dungeon module (a mutated one included).
    import dungeon as D0
    S = load_scheduler(None)
    if mod is not D0:
        S = _compiled("tools/rip_scheduler.py", "rip_scheduler_for_mut")
        S.D = mod
    for rel, text in S.pack_files(mod.load(), S.load()).items():
        if rel.endswith(".mcfunction"):
            if rel in files:
                raise RuntimeError("%s is in both the dungeon pack and the scheduler's" % rel)
            files[rel] = text
    built = time.time() - t0
    expect = roster_expectations(built_ids={d["id"] for d in doc["dungeons"]})
    env = Env(files, doc, tmp)
    out = {}
    if env.missing:
        out["contract_names"] = ["the pack never mentions %s: a name the scenarios read was renamed" % ", ".join(env.missing)]
    for name, fn in SCENARIOS:
        t = time.time()
        try:
            out[name] = fn(env, expect)
        except Exception as e:                      # a function the pack lacks, an unsupported command: a finding, not a pass
            out[name] = ["the scenario raised %s: %s" % (type(e).__name__, str(e)[:300])]
        out[name + "__seconds"] = round(time.time() - t, 1)
    out["input_validators"] = list(mod.draw_problems(doc)) + list(mod.rip_problems(doc))      # the builder's, cheap: not independent
    try:
        out["reapply_wires_r16dr"] = sc_reapply_wires_r16dr(env, expect, mod)
    except Exception as e:
        out["reapply_wires_r16dr"] = ["the scenario raised %s: %s" % (type(e).__name__, str(e)[:300])]
    facts = {"build_seconds": round(built, 1), "functions_written": env.written, "dungeons": len(env.ds), "rips": len(env.rips)}
    return out, facts


# ------------------------------------------------------------------------------------------------- the rip scheduler (cobblers_rips)
# Since 2026-10-14 no rip stands: tools/rip_scheduler.py emits a RUNTIME pack that keeps a few of data/dungeon_rips.json's
# candidates open at random and closes them again (the owner: "placing possible spawn locations and then randomly having them
# appear all over"). Audited here by RUNNING its emitted functions on tests/mcfunction_sim.py CellWorld (a world of real cells,
# clone/fill/setblock/schedule/random as vanilla runs them), against expectations read HERE from the records and the settings:
#
#   cap        a world-defined count (a candidate is open when a cell of its plane or ground differs from the world before)
#              never exceeds open_max, over a long walk in which EVERY 1-in-K roll succeeds, through a /reload and a restart
#              that lost the schedule; open_min and open_max are both reached (so the cap was tested, not vacuous)
#   exact      open then close gives back EVERY cell exactly (a world whose every cell is a distinct block with a state and a
#              block entity, so a lost state, a short box or a skipped clone shows), and the sky hold is air again
#   player     an open and a close both do nothing while a player stands in or on any cell the open writes, or at the exit point
#   way out    the exit point and the cell over it are written by nothing, and the ground under it is the world's after a close
#   return     an open does nothing while a player in a run has this rip's number in dg.rip; it opens for another rip's number
#   forceload  no chunk stays force-loaded longer than tools/chunk_look.py's own look window after a write
#   R16DR      (slow part, on the built dungeon pack) runs the retire and the scheduler's init, and no dungeon function places a rip
#
# The functions under test are found by what they DO (the open of rip i summons an interaction at rip i's click; its close
# clones back into rip i's footprint), never by tools/rip_scheduler.py's names or helpers. Independence is proved by
# SCHED_MUTATIONS: one edit to tools/rip_scheduler.py, tools/dungeon.py or tools/dungeon_rips.py, data/ untouched.
#
# NOT covered here (validity is not runtime behaviour): vanilla's block updates during a clone (a plant cloned to the hold with
# no block under it, a plant on a patch cell the open overwrites, sand in the hold: see the audit's report), a mob standing in
# the footprint, an entity that takes longer than the look window to load, a chunk another system force-loads (a `forceload
# remove` here would release it), dimensions (the sim has one), and anything a world holds that no record says.

SCHED_FN = "cobblers:rips/"
HEIGHT_TYPE = ROOT / "modpack" / "datapacks" / "cobblers_height" / "data" / "minecraft" / "dimension_type" / "overworld.json"
SKY = 400              # the synthetic world: every cell under this y is a distinct block, every cell at or over it air
FAR = (-3000.5, 300.0, -3000.5)     # a player who is online and nowhere near any candidate


def scheduler_inputs(data_dir=DATA):
    """(rips, candidates [(index, record)], settings {name: value}, (min_y, top_y)), read here from data/dungeon_rips.json,
    data/rip_scheduler.json and the dimension type the world runs; index is the record's 1-based place in 'rips' (dg.rip)."""
    rips = json.loads((Path(data_dir) / "dungeon_rips.json").read_text(encoding="utf-8"))["rips"]
    s = {k: v["value"] for k, v in json.loads((Path(data_dir) / "rip_scheduler.json").read_text(encoding="utf-8"))["settings"].items()}
    cands = [(i, r) for i, r in enumerate(rips, 1) if not (s["gated_sites"] == "exclude" and r.get("reachable_after"))]
    dim = json.loads(HEIGHT_TYPE.read_text(encoding="utf-8"))
    return rips, cands, s, (dim["min_y"], dim["min_y"] + dim["height"] - 1)


def plane_cells(r):
    f = r["frame"]
    return {(x, y, f["z"]) for x in range(f["x0"], f["x1"] + 1) for y in range(f["y"], f["y"] + f["height"])}


def allowed_cells(r):
    """The cells an open may write, from the record: the plane where the frame stood (x0..x1, y..y+height-1, at z) and the ground
    under the oval and in front of it (x0..x1, y-1, z+1..z+2: DUNGEON_DRAW.md's themed patch)."""
    f = r["frame"]
    return plane_cells(r) | {(x, f["y"] - 1, z) for x in range(f["x0"], f["x1"] + 1) for z in (f["z"] + 1, f["z"] + 2)}


def exit_cell(r):
    ox, oy, oz = r["outside"][:3]
    return (math.floor(ox), math.floor(oy), math.floor(oz))


def terrain_block(x, y, z):
    """The synthetic world: a distinct block in every cell, with a block state and block-entity data, so only an exact copy
    gives it back. Air from SKY up (where a sky hold may go)."""
    if y >= SKY:
        return "minecraft:air"
    return "test:b_%d_%d_%d[s=%d]{d:%d}" % (x, y, z, (x * 7 + y * 3 + z) % 5, x ^ z)


SCHED_MUTATIONS = {
    "cap_off_by_one": {
        "file": "tools/rip_scheduler.py", "why": "the pass stops opening only ABOVE open_max (>= for >)",
        "edit": ('"execute if score #open %s >= #max %s run return 0" % (V, V),', '"execute if score #open %s > #max %s run return 0" % (V, V),')},
    "cap_constant_one_high": {
        "file": "tools/rip_scheduler.py", "why": "init sets the cap one above data/rip_scheduler.json open_max",
        "edit": ('"scoreboard players set #max %s %d" % (V, v["open_max"])]', '"scoreboard players set #max %s %d" % (V, v["open_max"] + 1)]')},
    "open_skips_player_check": {
        "file": "tools/rip_scheduler.py", "why": "an open writes while a player stands on the rip",
        "edit": ('o += ["execute if entity @a[scores={%s=%d,%s=1..}] run return 0" % (D.OBJ["rip"], i, D.OBJ["st"]), guard,',
                 'o += ["execute if entity @a[scores={%s=%d,%s=1..}] run return 0" % (D.OBJ["rip"], i, D.OBJ["st"]),')},
    "return_point_skipped": {
        "file": "tools/rip_scheduler.py", "why": "a rip opens while a player in a run would come out at it",
        "edit": ('o += ["execute if entity @a[scores={%s=%d,%s=1..}] run return 0" % (D.OBJ["rip"], i, D.OBJ["st"]), guard,',
                 'o += [guard,')},
    "close_skips_player_check": {
        "file": "tools/rip_scheduler.py", "why": "a close gives the ground back under a player standing on the rip",
        "edit": ('"# a player on the rip: leave it open (the timer stays at 0, so the next pass asks again)",\n             guard,',
                 '"# a player on the rip: leave it open (the timer stays at 0, so the next pass asks again)",')},
    "guard_box_short_in_front": {
        "file": "tools/rip_scheduler.py", "why": "the player check stops short of the patch's front row and the exit point",
        "edit": ('"@a[dx=%d,dy=%d,dz=%d]" % (wx1 - wx0, CHECK_BELOW + CHECK_ABOVE, wz1 - wz0)',
                 '"@a[dx=%d,dy=%d,dz=%d]" % (wx1 - wx0, CHECK_BELOW + CHECK_ABOVE, wz1 - wz0 - 4)')},
    "open_never_releases_chunks": {
        "file": "tools/rip_scheduler.py", "why": "an open leaves its chunks force-loaded for good",
        "edit": ('"forceload remove %s" % fls]\n        out["o%d" % i] = o', '"# mutated: no release"]\n        out["o%d" % i] = o')},
    "close_never_releases_chunks": {
        "file": "tools/rip_scheduler.py", "why": "a close's last poll never releases the chunks",
        "edit": ('"execute if score %s %s matches ..0 run forceload remove %s" % (h, L, fls)]', '"# mutated: no release"]')},
    "close_polls_dropped": {
        "file": "tools/rip_scheduler.py", "why": "a close kills only in its own tick, before the chunk's saved entities arrive",
        "edit": ('"schedule function %s %dt replace" % (F("x%d" % i), chunk_look.LOAD_WAIT)]',
                 '"scoreboard players set %s %s 0" % (h, S), "forceload remove %s" % fls]')},
    "one_per_region_dropped": {
        "file": "tools/rip_scheduler.py", "why": "a second rip opens in a region that has one open",
        "edit": ('if j != i and q["region"] == r["region"]:', 'if False:')},
    "save_box_one_short": {
        "file": "tools/dungeon.py", "why": "the save (and the close) stop one block under the top of the plane the open clears",
        "edit": ('out = [(f["x0"], f["y"], f["z"], f["x1"], f["y"] + f["height"] - 1, f["z"])]',
                 'out = [(f["x0"], f["y"], f["z"], f["x1"], f["y"] + f["height"] - 2, f["z"])]')},
    "close_skips_hold_clear": {
        "file": "tools/dungeon.py", "why": "the close leaves the saved blocks standing in the sky",
        "edit": ('        out += ["fill %d %d %d %d %d %d minecraft:air" % h for h in holds]\n', '')},
    "close_skips_the_plane": {
        "file": "tools/dungeon.py", "why": "the close gives the ground back but not the plane",
        "edit": ('order = list(range(1, len(boxes))) + [0]', 'order = list(range(1, len(boxes)))')},
    "save_after_write": {
        "file": "tools/dungeon.py", "why": "the open writes the rip before it saves the ground, so the save holds the rip",
        "edit": ('return rip_save_lines(r, hold_y) + rip_lines(r)', 'return rip_lines(r) + rip_save_lines(r, hold_y)')},
    "window_short_in_front": {
        "file": "tools/dungeon_rips.py", "why": "the siting window (the scheduler's player box) ends one block in front of the plane",
        "edit": ('WIN = (-4, -1, 4, 5)\n', 'WIN = (-4, -1, 4, 1)\n')},
}


def _compiled(rel, name, edit=None):
    src = (ROOT / rel).read_text(encoding="utf-8")
    if edit:
        old, new = edit
        if src.count(old) != 1:
            raise RuntimeError("mutation of %s: its target text occurs %d times (want 1); the generator changed, update the "
                               "mutation, do not loosen it" % (rel, src.count(old)))
        src = src.replace(old, new)
    mod = type(sys)(name)
    mod.__file__ = str(ROOT / rel)
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    return mod


def load_scheduler(mutation=None):
    """tools/rip_scheduler.py as a module: the real one, or a fresh copy whose D (tools/dungeon.py) or DRP (tools/dungeon_rips.py)
    or own source carries ONE mutation from SCHED_MUTATIONS. data/ is untouched in every case."""
    import rip_scheduler as S0
    if not mutation:
        return S0
    m = SCHED_MUTATIONS[mutation]
    S = _compiled("tools/rip_scheduler.py", "rip_scheduler_mut", m["edit"] if m["file"] == "tools/rip_scheduler.py" else None)
    if m["file"] == "tools/dungeon.py":
        S.D = _compiled("tools/dungeon.py", "dungeon_mut", m["edit"])
    if m["file"] == "tools/dungeon_rips.py":
        S.DRP = _compiled("tools/dungeon_rips.py", "dungeon_rips_mut", m["edit"])
    return S


def scheduler_pack(S):
    """({function id: [lines]}, {tag: [function id]}): the pack module S emits (its pack_files: the OUTPUT under audit)."""
    files = S.pack_files(S.D.load(), S.load())
    fns, tags = {}, {}
    for rel, text in files.items():
        m = re.fullmatch(r"data/([^/]+)/function/(.+)\.mcfunction", rel)
        if m:
            fns["%s:%s" % m.groups()] = text.splitlines()
        m = re.fullmatch(r"data/minecraft/tags/function/([a-z_]+)\.json", rel)
        if m:
            tags[m.group(1)] = json.loads(text)["values"]
    return fns, tags


_N = r"(-?\d+)"


def command_boxes(line):
    """(kind, lo, hi, src_lo, src_hi) of a block-writing line (setblock, fill, clone; after any `execute ... run`), else None.
    For a clone, lo/hi is the DESTINATION box and src_* its source."""
    s = line.strip()
    if " run " in s and s.startswith("execute "):
        s = s[s.rindex(" run ") + 5:]
    m = re.match(r"setblock %s %s %s \S+" % ((_N,) * 3), s)
    if m:
        c = tuple(int(v) for v in m.groups())
        return ("setblock", c, c, None, None)
    m = re.match(r"fill %s %s %s %s %s %s \S+" % ((_N,) * 6), s)
    if m:
        v = [int(x) for x in m.groups()]
        lo, hi = tuple(min(v[i], v[i + 3]) for i in range(3)), tuple(max(v[i], v[i + 3]) for i in range(3))
        return ("fill", lo, hi, None, None)
    m = re.match(r"clone %s %s %s %s %s %s %s %s %s" % ((_N,) * 9), s)
    if m:
        v = [int(x) for x in m.groups()]
        slo, shi = tuple(min(v[i], v[i + 3]) for i in range(3)), tuple(max(v[i], v[i + 3]) for i in range(3))
        d = tuple(v[6:9])
        return ("clone", d, tuple(d[i] + shi[i] - slo[i] for i in range(3)), slo, shi)
    return None


def _box_cells(lo, hi):
    return {(x, y, z) for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1) for z in range(lo[2], hi[2] + 1)}


def scheduler_roles(fns, cands):
    """({index: (open id, close id)}, [problem]): found by what each function does. The open of rip i summons an interaction at
    rip i's click (x + 0.5, y, z + 0.5); its close is the one other function that clones INTO rip i's plane or ground."""
    bad, roles = [], {}
    summons = {}
    for fid, lines in fns.items():
        for ln in lines:
            m = re.search(r"summon minecraft:interaction (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)", ln)
            if m:
                summons.setdefault(tuple(round(float(v), 2) for v in m.groups()), set()).add(fid)
    clones_into = {}
    for fid, lines in fns.items():
        for ln in lines:
            b = command_boxes(ln)
            if b and b[0] == "clone":
                clones_into.setdefault(fid, set()).update(_box_cells(b[1], b[2]))
    for i, r in cands:
        x, y, z = r["click"]
        op = summons.get((round(x + 0.5, 2), round(float(y), 2), round(z + 0.5, 2)), set())
        if len(op) != 1:
            bad.append("%s (rip %d): %d functions summon an interaction at its click (want exactly one, its open)" % (r["id"], i, len(op)))
            continue
        op = op.pop()
        cl = [fid for fid, cells in clones_into.items() if fid != op and cells & allowed_cells(r)]
        if len(cl) != 1:
            bad.append("%s (rip %d): %d functions clone the ground back into its footprint (want exactly one, its close): %s" % (r["id"], i, len(cl), sorted(cl)[:3]))
            continue
        roles[i] = (op, cl[0])
    return roles, bad


def scheduler_static_problems(fns, tags, rips, cands, settings, height, roles, ground=None):
    """[problem] read from the emitted text: what each open writes stays in its record's plane and ground (plus a hold), it is
    saved before the first write, every hold is inside the world and clear of every footprint and exit point, no exit point or
    the cell over it is written by anything, no rip that is not a candidate (a retired one, a gated one under 'exclude') can open,
    the load tag arms the pack, and (with the heightmap) every exit point stands one block over round(ground)."""
    bad = []
    lo_y, top_y = height
    allowed = {i: allowed_cells(r) for i, r in cands}
    holds, writes_all = {}, set()
    for i, r in cands:
        if i not in roles:
            continue
        op, cl = roles[i]
        # a cell is SAVED when a clone copies it before anything has written it (a clone after a write saves the rip, not the world)
        saved, written, hold = set(), set(), set()
        for ln in fns[op]:
            b = command_boxes(ln)
            if not b:
                continue
            if b[0] == "clone":
                saved |= _box_cells(b[3], b[4]) - written
                hold |= _box_cells(b[1], b[2])
                continue
            cells = _box_cells(b[1], b[2])
            written |= cells
            outside = cells - allowed[i] - hold
            if outside:
                bad.append("%s: its open writes %d cell(s) outside its plane and ground, first %s" % (r["id"], len(outside), sorted(outside)[0]))
            unsaved = (cells & allowed[i]) - saved
            if unsaved:
                bad.append("%s: its open writes %d cell(s) it did not save first, first %s" % (r["id"], len(unsaved), sorted(unsaved)[0]))
            writes_all |= cells & allowed[i]
        if not hold:
            bad.append("%s: its open saves nothing (no clone)" % r["id"])
        holds[i] = hold
        for ln in fns[cl]:
            b = command_boxes(ln)
            if b:
                cells = _box_cells(b[1], b[2])
                writes_all |= cells & allowed[i]
                stray = cells - allowed[i] - hold
                if stray:
                    bad.append("%s: its close writes %d cell(s) outside its footprint and its hold, first %s" % (r["id"], len(stray), sorted(stray)[0]))
        ys = [c[1] for c in hold]
        if hold and (min(ys) < lo_y or max(ys) > top_y):
            bad.append("%s: its hold spans y%d..y%d, outside the world's y%d..y%d" % (r["id"], min(ys), max(ys), lo_y, top_y))
    every_fp = set().union(*allowed.values()) if allowed else set()
    exits = {}
    for i, r in cands:
        ex = exit_cell(r)
        exits[i] = {ex, (ex[0], ex[1] + 1, ex[2])}
    all_exit = set().union(*exits.values()) if exits else set()
    keys = sorted(holds)
    for a in keys:
        if holds[a] & (every_fp | all_exit):
            bad.append("rip %d: its hold overlaps a candidate's footprint or exit point" % a)
        for b in keys:
            if b > a and holds[a] & holds[b]:
                bad.append("rips %d and %d share hold cells" % (a, b))
    every_hold = set().union(*holds.values()) if holds else set()
    for i, r in cands:
        hit = exits[i] & (writes_all | every_hold)
        if hit:
            bad.append("%s: its exit point %s or the cell over it is written by a scheduler function" % (r["id"], sorted(hit)[0]))
        if ground is not None:
            ex = exit_cell(r)
            g = int(round(ground(ex[0], ex[2])))
            if ex[1] != g + 1:
                bad.append("%s: its exit point stands at y%d, round(ground) + 1 there is y%d: the way out is not on the ground" % (r["id"], ex[1], g + 1))
    cand_ids = {i for i, _r in cands}
    for i, r in enumerate(rips, 1):
        if i in cand_ids:
            continue
        x, y, z = r["click"]
        for fid, lines in fns.items():
            if any(re.search(r"summon minecraft:interaction %s %s %s" % (re.escape("%.1f" % (x + 0.5)), y, re.escape("%.1f" % (z + 0.5))), ln) for ln in lines):
                bad.append("%s: not a candidate (gated_sites %s) and %s still opens it" % (r["id"], settings["gated_sites"], fid))
    if not tags.get("load"):
        bad.append("the pack has no minecraft:load entry: nothing arms the scheduler after a boot or a /reload")
    return bad


def sched_world(fns, tags, seed=1, entity_delay=20):
    """A CellWorld over the scheduler pack: no chunk loaded but by `forceload` (so a write outside one fails), the dungeon pack's
    run objectives present (the contract names dg.rip and dg.st), entities in a newly force-loaded chunk arriving `entity_delay`
    ticks later."""
    sys.path.insert(0, str(ROOT / "tests"))
    import mcfunction_sim as SIM
    w = SIM.CellWorld(dict(fns), terrain=terrain_block, seed=seed, entity_delay=entity_delay, loaded=lambda x, z: False)
    w.tags = {"load": list(tags.get("load", [])), "tick": list(tags.get("tick", []))}
    w.objectives |= {"dg.rip", "dg.st"}
    return w


def changed_cells(w):
    return {c for c, b in w.cells.items() if b != terrain_block(*c)}


def rip_entities(w, r):
    """Live entities standing on rip r: the click (an interaction within a block of it) or anything in its plane's 3-block reach."""
    x, y, z = r["click"]
    return [e for e in w.entities if e.alive and e.type != "minecraft:player"
            and abs(e.pos[0] - (x + 0.5)) <= 3 and abs(e.pos[2] - (z + 0.5)) <= 3 and y - 1 <= e.pos[1] <= y + r["frame"]["height"] + 1]


def _run(w, fid):
    return w.function(fid, w.server())


def sc_sched_open_close_exact(fns, tags, cands, roles, cycles=2):
    """Open then close every candidate, twice, on a fresh world: after the close and its look window every cell any command
    wrote holds the world's block again (the hold air again), no chunk is force-loaded, nothing stands on the rip, and no write
    landed in an unloaded chunk. After the open the writes are inside the plane, the ground and a hold over them only."""
    import chunk_look
    window = chunk_look.LOAD_WAIT + chunk_look.POLLS * chunk_look.POLL_EVERY
    bad = []
    for i, r in cands:
        if i not in roles:
            continue
        op, cl = roles[i]
        w = sched_world(fns, tags)
        w.run_load()
        for k in range(cycles):
            _run(w, op)
            ch = changed_cells(w)
            fp = ch & allowed_cells(r)
            if not fp:
                bad.append("%s: its open changed none of its plane or ground (cycle %d)" % (r["id"], k + 1))
                break
            stray = {c for c in ch - allowed_cells(r) if c[1] < SKY}
            if stray:
                bad.append("%s: its open changed %d cell(s) outside its plane and ground, first %s" % (r["id"], len(stray), sorted(stray)[0]))
            if w.forced:
                bad.append("%s: %d chunk(s) still force-loaded after its open" % (r["id"], len(w.forced)))
            if not any(e.type == "minecraft:interaction" for e in rip_entities(w, r)):
                bad.append("%s: no click stands after its open" % r["id"])
            _run(w, cl)
            w.advance(window + 100)
            left = changed_cells(w)
            if left:
                hold = sorted(c for c in left if c[1] >= SKY)
                ground = sorted(c for c in left if c[1] < SKY)
                bad.append("%s: after open and close %d cell(s) differ from the world before (%d on the ground, first %s; %d in the sky hold, first %s)"
                           % (r["id"], len(left), len(ground), ground[0] if ground else None, len(hold), hold[0] if hold else None))
            if w.forced:
                bad.append("%s: %d chunk(s) still force-loaded after its close's look window" % (r["id"], len(w.forced)))
            if rip_entities(w, r):
                bad.append("%s: %d entit(ies) still stand on it after its close (a closed rip that can still be clicked)" % (r["id"], len(rip_entities(w, r))))
            if left or w.forced or rip_entities(w, r):
                break
        if w.errors:
            bad.append("%s: %d command(s) failed against an unloaded chunk or an overlap, first %s" % (r["id"], len(w.errors), w.errors[0][:160]))
    return bad


def probe_points(r):
    """Where a player can be that the open or close must not write over: feet in every cell the open may write, feet on top
    of every such cell, and the exit point."""
    pts = []
    for (x, y, z) in sorted(allowed_cells(r)):
        pts.append((x + 0.5, float(y), z + 0.5))
        pts.append((x + 0.5, float(y + 1), z + 0.5))
    ox, oy, oz = r["outside"][:3]
    pts.append((float(ox), float(oy), float(oz)))
    return pts


def sc_sched_player_guard(fns, tags, cands, roles):
    """An open with a player at any probe point writes nothing, summons nothing and holds no chunk; so does a close of an open
    rip. Without the player both go ahead (the control, so a function that never writes cannot pass)."""
    bad = []
    for i, r in cands:
        if i not in roles:
            continue
        op, cl = roles[i]
        w = sched_world(fns, tags)
        w.run_load()
        failed = False
        for pos in probe_points(r):
            p = w.add_player(pos)
            n_ents = len(w.entities)
            _run(w, op)
            p.alive = False
            if changed_cells(w) or len(w.entities) != n_ents or w.forced:
                bad.append("%s: its open went ahead with a player at %s" % (r["id"], tuple(round(v, 1) for v in pos)))
                failed = True
                break
        if failed:
            continue
        _run(w, op)
        if not changed_cells(w) & allowed_cells(r):
            bad.append("%s: control: with nobody on it, its open wrote nothing" % r["id"])
            continue
        before = dict(w.cells)
        for pos in probe_points(r):
            p = w.add_player(pos)
            _run(w, cl)
            p.alive = False
            if w.cells != before or w.forced:
                bad.append("%s: its close went ahead with a player at %s" % (r["id"], tuple(round(v, 1) for v in pos)))
                break
        else:
            _run(w, cl)
            if w.cells == before:
                bad.append("%s: control: with nobody on it, its close gave nothing back" % r["id"])
    return bad


def sc_sched_return_point(fns, tags, cands, roles):
    """An open does nothing while an online player in a run (dg.st >= 1) has the rip's number in dg.rip, the engine's way out
    to this rip's exit point; it opens for a player whose run is over, and for a run entered by another rip."""
    bad = []
    nums = [i for i, _r in cands]
    for i, r in cands:
        if i not in roles:
            continue
        op, cl = roles[i]
        w = sched_world(fns, tags)
        w.run_load()
        p = w.add_player(FAR)
        w.objectives |= {"dg.rip", "dg.st"}
        other = next((j for j in nums if j != i), i + 1)
        for rip_no, st, want_open in ((i, 1, False), (i, 2, False), (i, 0, True), (other, 1, True)):
            w.scores[("e%d" % p.uid, "dg.rip")] = rip_no
            w.scores[("e%d" % p.uid, "dg.st")] = st
            _run(w, op)
            opened = bool(changed_cells(w) & allowed_cells(r))
            if opened != want_open:
                bad.append("%s: with a player in a run (dg.rip %d, dg.st %d) its open %s" % (r["id"], rip_no, st, "went ahead" if opened else "did nothing"))
                break
            if opened:
                p.alive = False
                _run(w, cl)
                import chunk_look
                w.advance(chunk_look.LOAD_WAIT + chunk_look.POLLS * chunk_look.POLL_EVERY + 100)
                p.alive = True
    return bad


def sc_sched_walk(fns, tags, cands, settings, passes=1500, seed=7):
    """A long walk of passes with players online, in which every 1-in-K roll succeeds (the adversary for the cap): each pass the
    world-defined open count is at most open_max, at most one per region (one_open_per_region), no write lands in an unloaded
    chunk, no chunk stays force-loaded past tools/chunk_look.py's look window; open_min and open_max are both reached. Through a
    /reload (pass 300) and a restart that lost the schedule (pass 600). Every 40 passes a player enters an open rip; when that rip
    has closed he comes out at its exit point, which must be on the world's own ground, and he stands there for three passes,
    in which that rip must not open. Every 25 passes a player stands on an open rip's ground for three passes, in which it must
    not close."""
    import chunk_look
    look = chunk_look.LOAD_WAIT + (chunk_look.POLLS - 1) * chunk_look.POLL_EVERY
    w = sched_world(fns, tags, seed=seed)
    M = len(cands)

    def adversary(lo, hi, fn):
        if hi - lo + 1 == M:
            return w.rng.randint(lo, hi)        # the pick: uniform, as the game draws it
        if lo == 1:
            return 1                            # a 1-in-K roll: always the opening value
        return w.rng.randint(lo, hi)
    w.random_hook = adversary
    by_i = dict(cands)
    region = {i: r["region"] for i, r in cands}
    w.run_load()
    online = [w.add_player(FAR, "a"), w.add_player((FAR[0] + 50, FAR[1], FAR[2]), "b")]
    walker, stander = online
    step = settings["pass_seconds"] * 20
    bad, peak, low_seen, entry, stand = [], 0, False, None, None

    def open_now():
        ch = changed_cells(w)
        return {i for i, r in cands if ch & allowed_cells(r)}
    for n in range(1, passes + 1):
        if n == 300:
            w.run_load()
        if n == 600:
            w.scheduled.clear()
            w.run_load()
        before = open_now()
        w.advance(step)
        now = open_now()
        if len(now) > settings["open_max"]:
            bad.append("pass %d: %d rips open, open_max is %d: %s" % (n, len(now), settings["open_max"], sorted(now)))
            break
        if settings["one_open_per_region"]:
            regs = [region[i] for i in now]
            dup = sorted({g for g in regs if regs.count(g) > 1})
            if dup:
                bad.append("pass %d: two rips open in region(s) %s" % (n, dup))
                break
        peak = max(peak, len(now))
        low_seen = low_seen or len(now) >= settings["open_min"]
        stale = [ch for ch, t in w.forced_since.items() if ch in w.forced and w.tick_no - t > look]
        if stale:
            bad.append("pass %d: chunk(s) %s force-loaded for more than %d ticks" % (n, stale[:2], look))
            break
        if w.errors:
            bad.append("pass %d: %s" % (n, w.errors[0][:200]))
            break
        # a player standing on an open rip: it must not close under him
        if stand is not None:
            i, until, snap = stand
            if {c: w.block_at(*c) for c in allowed_cells(by_i[i])} != snap:
                bad.append("pass %d: %s changed with a player standing on its ground" % (n, by_i[i]["id"]))
                break
            if n >= until:
                stander.pos = list(FAR)
                stand = None
        elif n % 25 == 0 and now:
            i = sorted(now)[n % len(now)]
            f = by_i[i]["frame"]
            stander.pos = [f["x0"] + 0.5, float(f["y"]), f["z"] + 1.5]
            stand = (i, n + 3, {c: w.block_at(*c) for c in allowed_cells(by_i[i])})
        # a run entered by an open rip; out at its exit point once it has closed
        if entry is None and n % 40 == 0 and now - ({stand[0]} if stand else set()):
            i = sorted(now - ({stand[0]} if stand else set()))[0]
            w.scores[("e%d" % walker.uid, "dg.rip")] = i
            w.scores[("e%d" % walker.uid, "dg.st")] = 1
            entry = [i, "in", n]
        elif entry is not None:
            i, state, since = entry
            r = by_i[i]
            if state == "in" and i not in now:
                ex = exit_cell(r)
                wrong = sorted(c for c in {ex, (ex[0], ex[1] + 1, ex[2]), (ex[0], ex[1] - 1, ex[2])} | allowed_cells(r)
                               if w.block_at(*c) != terrain_block(*c))
                if wrong:
                    bad.append("pass %d: %s closed, but %d cell(s) at its exit point or its ground are not the world's, first %s" % (n, r["id"], len(wrong), wrong[0]))
                    break
                walker.pos = [float(v) for v in r["outside"][:3]]
                w.scores[("e%d" % walker.uid, "dg.st")] = 0
                entry = [i, "out", n]
            elif state == "out":
                if i in now:
                    bad.append("pass %d: %s opened with a player standing at its exit point" % (n, r["id"]))
                    break
                if n - since >= 3:
                    walker.pos = list(FAR)
                    entry = None
    if not bad:
        if peak < settings["open_max"]:
            bad.append("vacuous: the walk never had open_max (%d) rips open (peak %d)" % (settings["open_max"], peak))
        if not low_seen:
            bad.append("the walk never reached open_min (%d)" % settings["open_min"])
    return bad, {"peak": peak, "passes": n}


def sc_sched_init_writes_nothing(fns, tags, cands):
    """The load entry (a boot, a /reload, R16DR's arming) opens and closes nothing: on a world with players and one rip open, it
    writes no block, summons nothing and tells no one anything."""
    bad = []
    w = sched_world(fns, tags)
    w.add_player(FAR)
    n_ents = len(w.entities)
    w.run_load()
    if w.writes or len(w.entities) != n_ents or any(p.messages for p in w.living("minecraft:player")):
        bad.append("the load entry wrote %d block command(s), summoned %d and told a player something" % (len(w.writes), len(w.entities) - n_ents))
    return bad


def sc_sched_pause_survives_reload(fns, tags, settings):
    """data/rip_scheduler.json enabled.origin documents the runtime pause, `scoreboard players set #on rp.v 0`. A pause must
    still hold after a /reload or a boot (and R16DR's arming): with it set, no rip opens over many passes with players online."""
    w = sched_world(fns, tags)
    w.run_load()
    w.add_player(FAR)
    w.command("scoreboard players set #on rp.v 0", w.server())
    w.run_load()                        # a /reload, a boot, or tools/reapply.py R16DR running the arming function
    w.advance(settings["pass_seconds"] * 20 * 60)
    if changed_cells(w):
        return ["a paused scheduler (#on rp.v 0, as data/rip_scheduler.json enabled says) opened a rip after a /reload: the load "
                "entry sets #on back to %s" % settings["enabled"]]
    return []


def run_scheduler(S=None, ground=None, quick=False):
    """({check: [problem]}, facts): the whole scheduler audit on the pack module S emits (the real tools/rip_scheduler.py by
    default). `quick` runs the per-rip checks on every fourth candidate (each region still met) and a shorter walk."""
    S = S or load_scheduler(None)
    rips, cands, settings, height = scheduler_inputs()
    t0 = time.time()
    try:
        fns, tags = scheduler_pack(S)
    except SystemExit as e:
        return {"build": ["the scheduler refused to build: %s" % str(e)[:300]]}, {}
    roles, bad_roles = scheduler_roles(fns, cands)
    sample = cands[::4] if quick else cands
    out = {"roles": bad_roles}
    checks = (
        ("static", lambda: scheduler_static_problems(fns, tags, rips, cands, settings, height, roles, ground)),
        ("init_writes_nothing", lambda: sc_sched_init_writes_nothing(fns, tags, cands)),
        ("open_close_exact", lambda: sc_sched_open_close_exact(fns, tags, sample, roles)),
        ("player_guard", lambda: sc_sched_player_guard(fns, tags, sample, roles)),
        ("return_point", lambda: sc_sched_return_point(fns, tags, sample, roles)),
        ("walk", lambda: sc_sched_walk(fns, tags, cands, settings, passes=700 if quick else 1500)[0]),
    )
    for name, fn in checks:
        t = time.time()
        try:
            out[name] = fn()
        except Exception as e:          # an unsupported command, a function the pack lacks: a finding, not a pass
            out[name] = ["the check raised %s: %s" % (type(e).__name__, str(e)[:300])]
        out[name + "__seconds"] = round(time.time() - t, 1)
    facts = {"candidates": len(cands), "functions": len(fns), "per_rip_checked": len(sample), "seconds": round(time.time() - t0, 1)}
    return out, facts


def sc_sched_pool_change_while_open(S, drop=0):
    """A pool rebuilt while rips are open (a record removed from data/dungeon_rips.json 'rips', as the 13 trail rips left it on
    2026-10-13; or gated_sites switched to 'exclude') must not damage the world: the state lives in holders numbered by the
    record's PLACE in the file, so after the rebuild the open rip's number names another place. Demonstration: the real pack
    opens every candidate it can; the pack is rebuilt in memory with record `drop` removed (data/ on disk untouched); the rebuilt
    pack's own timers run out. Every cell must end as the world before, and no click may stand at a closed place."""
    import chunk_look
    rips, cands, settings, _h = scheduler_inputs()
    fns, tags = scheduler_pack(S)
    roles, _ = scheduler_roles(fns, cands)
    w = sched_world(fns, tags)
    w.run_load()
    for i, _r in cands:
        if i in roles:
            _run(w, roles[i][0])
    ddoc = S.D.load()
    ddoc["rips"] = [r for k, r in enumerate(S.D.rips(ddoc)) if k != drop]
    files = S.pack_files(ddoc, S.load())
    w.functions = {}
    for rel, text in files.items():
        m = re.fullmatch(r"data/([^/]+)/function/(.+)\.mcfunction", rel)
        if m:
            w.functions["%s:%s" % m.groups()] = text.splitlines()
    w.scheduled.clear()
    w.run_load()
    for key in [k for k in w.scores if k[1] == "rp.t"]:
        w.scores[key] = 0
    w.add_player(FAR)
    w.advance(settings["pass_seconds"] * 20 * 3 + chunk_look.LOAD_WAIT + chunk_look.POLLS * chunk_look.POLL_EVERY)
    w.entities = [e for e in w.entities if e.type != "minecraft:player"]
    by_place = {}
    for c in changed_cells(w):
        if c[1] < SKY:
            hit = [r["id"] for r in rips if c in allowed_cells(r)]
            by_place.setdefault(hit[0] if hit else "elsewhere", []).append(c)
    gone = [r for r in rips if not (allowed_cells(r) & changed_cells(w))]
    standing = [r["id"] for r in gone if rip_entities(w, r)]
    bad = []
    if by_place:
        ground_y = {r["id"]: r["frame"]["y"] - 1 for r in rips}
        air = sorted({rid for rid, cs in by_place.items()
                      if any(c[1] == ground_y.get(rid) and w.block_at(*c) == "minecraft:air" for c in cs)})
        bad.append("after a rebuild that removed %s from the pool, %d place(s) are not the world's: %s; %d of them with ground "
                   "turned to air (an empty hold cloned back): %s" % (rips[drop]["id"], len(by_place), sorted(by_place)[:4], len(air), air[:4]))
    if standing:
        bad.append("clicks still stand at %d closed place(s): %s" % (len(standing), standing[:4]))
    return bad


# known defects of the scheduler, run apart so they report without failing every mutation's control (tests xfail them strictly)
SCHED_DEFECTS = (
    ("pause_survives_reload", lambda fns, tags, settings: sc_sched_pause_survives_reload(fns, tags, settings)),
)


# ------------------------------------------------------------------------------------------------- the CLI


def failures(result):
    return {k: v for k, v in result.items() if isinstance(v, list) and v and not k.endswith("__seconds")}


def novel(base, mutated):
    """{scenario: [problem]}: the problems a MUTATED generator's run has that the unmutated run did not. A mutation is caught
    only by a problem that is new, so a defect the real generator already has cannot make a mutation look caught."""
    seen = {(k, p) for k, v in failures(base).items() for p in v}
    out = {}
    for k, v in failures(mutated).items():
        fresh = [p for p in v if (k, p) not in seen]
        if fresh:
            out[k] = fresh
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out", required=True, help="where the full result is written (JSON)")
    ap.add_argument("--only", choices=("siting", "draw", "scheduler"), help="run one part")
    ap.add_argument("--mutate", help="comma list of mutation names, or 'all': rebuild from a mutated generator; the audit must FAIL")
    a = ap.parse_args(argv)
    result = {"audit": "dungeon draw", "spec": "docs/mechanics/DUNGEON_DRAW.md 2-4, data/dungeon_prize_roster.json"}
    verdict = []
    if a.mutate:
        names = list(MUTATIONS) + list(RIPS_MUTATIONS) + list(SCHED_MUTATIONS) if a.mutate == "all" else a.mutate.split(",")
        # the control first: the unmutated generator must pass, or a mutated failure proves nothing
        res = {}
        base = {}
        if any(n in MUTATIONS for n in names):
            with tempfile.TemporaryDirectory() as tmp:
                base, facts = run_draw(load_module(None), tmp)
        base["siting_tool"] = sc_siting_tool_rejects_sites_that_break_a_rule(load_rips_module(None))
        if any(n in SCHED_MUTATIONS for n in names):
            base.update({"scheduler_" + k: v for k, v in run_scheduler()[0].items()})
        res["control"] = {"problems": sum(len(v) for v in failures(base).values()), "scenarios_failing": sorted(failures(base))}
        for n in names:
            if n in SCHED_MUTATIONS:
                got = {"scheduler_" + k: v for k, v in run_scheduler(load_scheduler(n))[0].items()}
                why = SCHED_MUTATIONS[n]["why"]
            elif n in RIPS_MUTATIONS:
                got = {"siting_tool": sc_siting_tool_rejects_sites_that_break_a_rule(load_rips_module(n))}
                why = RIPS_MUTATIONS[n]["why"]
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    got, _ = run_draw(load_module(n), tmp)
                why = MUTATIONS[n]["why"]
            f = novel(base, got)
            res[n] = {"caught": bool(f), "why": why, "caught_by": sorted(f), "first_problem": next(iter(sum(f.values(), [])), None)}
        result["mutations"] = res
        missed = [n for n in names if not res[n]["caught"]]
        Path(a.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print("MUTATIONS: %d of %d caught%s; control %s" % (len(names) - len(missed), len(names), (" (MISSED: %s)" % ", ".join(missed)) if missed else "",
                                                         "clean" if not res["control"]["problems"] else "FAILS %s" % res["control"]["scenarios_failing"]))
        return 1 if missed or res["control"]["problems"] else 0
    if a.only in (None, "siting"):
        t = time.time()
        bad = run_siting(result)
        result["siting_problems"] = bad
        result["siting_seconds"] = round(time.time() - t, 1)
        verdict.append("siting %d problem(s)%s" % (len(bad), "" if result["siting"]["old_positions"] == "checked" else " [test-rip positions NOT_EXECUTED]"))
    if a.only in (None, "scheduler"):
        try:
            import ground as G
            g = G.load()
        except Exception as e:                  # the exit points' ground check needs the heightmap; the rest does not
            g, result["scheduler_ground"] = None, "NOT_EXECUTED: %s" % str(e)[:200]
        got, facts = run_scheduler(ground=g)
        S = load_scheduler(None)
        fns, tags = scheduler_pack(S)
        settings = scheduler_inputs()[2]
        result["scheduler"] = got
        result["scheduler_facts"] = facts
        result["scheduler_known_defects"] = {name: fn(fns, tags, settings) for name, fn in SCHED_DEFECTS}
        result["scheduler_known_defects"]["pool_change_while_open"] = sc_sched_pool_change_while_open(S)
        f = failures(got)
        verdict.append("scheduler %d problem(s) in %d checks%s; known defects %d" % (
            sum(len(v) for v in f.values()), len([k for k in got if not k.endswith("__seconds")]),
            "" if g is not None else " [exit ground NOT_EXECUTED]", sum(bool(v) for v in result["scheduler_known_defects"].values())))
    if a.only in (None, "draw"):
        with tempfile.TemporaryDirectory() as tmp:
            got, facts = run_draw(load_module(None), tmp)
        result["draw"] = got
        result["draw_facts"] = facts
        f = failures(got)
        verdict.append("draw %d problem(s) in %d of %d scenarios" % (sum(len(v) for v in f.values()), len(f), len(SCENARIOS) + 1))
    n = len(result.get("siting_problems", [])) + sum(len(v) for v in failures(result.get("draw", {})).values()) \
        + sum(len(v) for v in failures(result.get("scheduler", {})).values()) \
        + sum(len(v) for v in (result.get("scheduler_known_defects") or {}).values())
    Path(a.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("%s: %s -> %s" % ("PASS" if n == 0 else "FAIL", "; ".join(verdict), a.out))
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
