#!/usr/bin/env python3
"""Every placement with an absolute y, against the ground the heightmap and the plan say is under it.

WHY THIS EXISTS. On 2026-09-30 the six jungle ruins were found standing at y120..127 with the seabed
under them at y57..61 - sixty to sixty-seven blocks of open air, six stone ruins hanging over the
water - and nothing in the repository said so. `validate_data` checks that a placement's fields are
well formed; nothing checked that its y was anywhere near the ground. This does.

THE RULE IT HOLDS, and why it is a band and not a number. A placement written with `y_mode:
absolute` is stamped by `cobblers:structures/place_<id>` at exactly that y, so its bottom layer lands
there. The repository turns out to hold TWO conventions, and both were measured off the existing
placements rather than assumed:

  - on a levelled lot, `y == level - 1` (11 of the 15 placements that overlap a `plan.anchors` entry
    carrying a `level`: gyms 1, 3, 4, 5, 6, 7, 8, the observatory, the dojo, the department store,
    the tableland lookout). The lot's `level` is the surface a player stands on, so the top solid
    block is `level - 1` and the donor's own foundation course replaces it.
  - off a levelled lot, `y == max(ground over the footprint) + 1` (all eight Rift dig-camp tents,
    exactly). Here the structure sits ON the ground instead of replacing its top course.

Which of the two applies depends on the template, and this tool cannot tell templates apart. So it
does NOT demand a number. It demands that the base lie in the band the two conventions span:

    levelled lot:  level - 1  <=  y  <=  level
    otherwise:     min(ground) - 1  <=  y  <=  max(ground) + 1

- the base must be somewhere in the ground the structure covers, at most one course into it and at
most one course above its highest point. A building may be cut into a slope or set on it; it may not
hang over it. The six jungle ruins were sixty to sixty-seven blocks outside this band. No convention
is off by sixty.

GROUND COMES FROM THE HEIGHTMAP, NEVER FROM A WORLD (CLAUDE.md). This reads `tools/ground.py`
(rounded), through `ground.for_settlement` so a settlement with its own measured ground - the cavern
floor, the islet, the sea town's deck - is measured on that and not on the raw heightmap. It opens no
world save; `tests/test_ground_rule.py` enforces that for placement tools and this file keeps to it.

THE LEVELLED-LOT EXCEPTION, and why it is an exception and not a hole. A gym, the League and a few
other buildings stand on a lot the town pass CUTS FLAT before the donor is stamped. The heightmap
still holds the hillside, so the raw ground under them is meaningless and the comparison has to be
against the lot's declared `level` instead. Those lots are the `plan.anchors` entries that carry a
`level`, and this tool uses that number when a placement's footprint lies inside such an anchor. A
placement that sits inside NO levelled anchor is measured against the heightmap with no excuse
available, which is how the ruins would have been caught the day they were written.

FAIL-CLOSED. Exit 1 on any problem, and exit 1 as well when it cannot measure something rather than
passing it silently: a placement whose settlement has no record, or whose footprint falls outside the
heightmap, is a problem, not a skip.

    python tools/placement_ground_audit.py                 # every absolute placement
    python tools/placement_ground_audit.py --settlement jungle_ruins
    python tools/placement_ground_audit.py --verbose       # print every placement, not only problems
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ground as G  # noqa: E402

# This tool reads no world. The name is what tests/test_ground_rule.py looks for.
WORLD_READS: set = set()

DEFAULT_SIZE = [8, 4, 8]


def load_placements():
    return json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))


def placement_list(doc):
    ps = doc.get("placements")
    return ps if isinstance(ps, list) else list((ps or {}).values())


def levelled_anchors(doc):
    """Every plan anchor that declares a `level`, as (settlement, id, rect, level)."""
    out = []
    for sid, s in (doc.get("settlements") or {}).items():
        for a in ((s.get("plan") or {}).get("anchors") or []):
            if isinstance(a, dict) and a.get("level") is not None and a.get("rect"):
                out.append((sid, a.get("id"), tuple(a["rect"]), a["level"]))
    return out


def footprint(p):
    pos = p["position"]
    s = p.get("size") or DEFAULT_SIZE
    return pos["x"], pos["z"], pos["x"] + s[0] - 1, pos["z"] + s[2] - 1


def _area(r):
    return max(0, r[2] - r[0] + 1) * max(0, r[3] - r[1] + 1)


def best_anchor(anchors, sid, fp):
    """The levelled anchor this footprint sits on, by largest overlap, or None.

    Overlap and not containment: `size` is the TEMPLATE's bounding box and `position` its corner, so a
    donor routinely extends well past the lot that was cut for it - the gym lots match at 4% to 22%
    and are still plainly the right lot. Containment matched only three of fifteen and sent the rest
    to the raw heightmap, where a cut lot's ground is whatever hillside used to be there."""
    best = None
    for s, aid, r, lvl in anchors:
        if s != sid:
            continue
        ov = _area((max(fp[0], r[0]), max(fp[1], r[1]), min(fp[2], r[2]), min(fp[3], r[3])))
        if ov and (best is None or ov > best[0]):
            best = (ov, aid, lvl)
    return (best[1], best[2]) if best else None


def run(only=None, verbose=False):
    doc = load_placements()
    anchors = levelled_anchors(doc)
    problems, rows = [], []
    grounds = {}
    for p in placement_list(doc):
        if p.get("y_mode") != "absolute":
            continue
        pos = p.get("position") or {}
        if pos.get("y") is None:
            problems.append("%s: y_mode is absolute but position has no y" % p.get("id"))
            continue
        sid = p.get("settlement")
        if only and sid != only:
            continue
        fp = footprint(p)
        hit = best_anchor(anchors, sid, fp)
        if hit:
            aid, level = hit
            lo, hi = level - 1, level
            basis = "lot %s levelled to y%d, so the base belongs at y%d or y%d" % (aid, level, lo, hi)
        else:
            if sid not in grounds:
                try:
                    grounds[sid] = G.for_settlement(sid, placements=doc) if sid else G.load()
                except SystemExit as e:
                    problems.append("%s (%s): ground could not be resolved: %s" % (p.get("id"), sid, e))
                    continue
            g = grounds[sid]
            try:
                hs = [round(g(x, z)) for x in range(fp[0], fp[2] + 1) for z in range(fp[1], fp[3] + 1)]
            except Exception as e:  # outside the heightmap, or a ground model that cannot answer
                problems.append("%s (%s): ground could not be measured over %s: %s" % (p.get("id"), sid, list(fp), e))
                continue
            if not hs:
                problems.append("%s (%s): empty footprint %s" % (p.get("id"), sid, list(fp)))
                continue
            g0, g1 = min(hs), max(hs)
            lo, hi = g0 - 1, g1 + 1
            basis = "heightmap %d..%d under its footprint, so the base belongs between y%d and y%d" % (g0, g1, lo, hi)
        y = pos["y"]
        d = 0 if lo <= y <= hi else (y - hi if y > hi else y - lo)
        rows.append((p.get("id"), sid, y, (lo, hi), d, basis))
        if d:
            problems.append("%s (%s): y%d, but %s - it is %s"
                            % (p.get("id"), sid, y, basis,
                               "%d block(s) clear of the ground, hanging in the air" % d if d > 0
                               else "buried %d block(s) into it" % -d))
    if verbose:
        print("%-26s %-18s %6s %-11s %6s" % ("id", "settlement", "y", "band", "out by"))
        for i, st, y, band, d, b in sorted(rows, key=lambda r: -abs(r[4])):
            print("%-26s %-18s %6d %-11s %+6d" % (i, st or "-", y, "%d..%d" % band, d))
    return problems, rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settlement")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)
    problems, rows = run(a.settlement, a.verbose)
    if problems:
        for p in problems:
            print(p)
        print("placement ground: %d problem(s) over %d absolute placement(s)" % (len(problems), len(rows)))
        return 1
    print("placement ground: clean over %d absolute placement(s)" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
