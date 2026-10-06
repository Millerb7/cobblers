#!/usr/bin/env python
"""Where an adopted legendary site stands, whichever file authors its position.

data/adopted_legendary_sites.json keeps the measurement and the reasoning for every site. A site that is NOT yet
scheduled carries its position in its own `placement` block. A SCHEDULED site has had that block deleted
(placement_method.not_in_placements_json): its position lives only in the data/placements.json `kind: donor` record
its `scheduled_as` names, so one site has one author.

A tool that reads `site["placement"]` directly therefore sees only the unscheduled sites and silently drops every
scheduled one (CLAUDE.md "Our list is not the world"). Read the position through `where()` instead.

  python tools/adopted_sites.py      every site, its author and its footprint
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "data" / "adopted_legendary_sites.json"
PLACEMENTS = ROOT / "data" / "placements.json"

# /place template's rotations about the minimum corner, as (dx, dz) -> world offset
TURN = {"none": lambda dx, dz: (dx, dz), "clockwise_90": lambda dx, dz: (-dz, dx),
        "180": lambda dx, dz: (-dx, -dz), "counterclockwise_90": lambda dx, dz: (dz, -dx)}


def sites(doc=None):
    """Every site with a position: the surface-seated `sites` AND the sweep's `sweep_sites` (sunk or floating,
    tools/legendary_sweep.py, 2026-10-06). A consumer that keeps clear of adopted sites (sea life, the hidden-site
    spread, the research station) must see both: reading only `sites` would drop the sweep's two from every exclusion
    built on this list (CLAUDE.md 'Our list is not the world')."""
    doc = doc if doc is not None else json.loads(SITES.read_text(encoding="utf-8"))
    return list(doc.get("sites") or []) + list(doc.get("sweep_sites") or [])


def site(site_id, doc=None):
    hits = [s for s in sites(doc) if s.get("id") == site_id]
    if len(hits) != 1:
        raise SystemExit("data/adopted_legendary_sites.json carries %d sites named %s" % (len(hits), site_id))
    return hits[0]


def where(s, placements=None):
    """{corner [x, z], y, rotation, mirror, size, author}: the site's ONE position.

    Scheduled: the data/placements.json record its `scheduled_as` names (position x/z = corner, y = bottom layer).
    Unscheduled: its own `placement` block. Fails closed on a site with neither, or a scheduled name that does not
    resolve to exactly one record: a silent None is how a site drops out of every exclusion built on it."""
    if "scheduled_as" in s:
        if placements is None:
            placements = json.loads(PLACEMENTS.read_text(encoding="utf-8"))["placements"]
        hits = [q for q in placements if q.get("id") == s["scheduled_as"]]
        if len(hits) != 1:
            raise SystemExit("%s: scheduled_as %r names %d records in data/placements.json"
                             % (s.get("id"), s["scheduled_as"], len(hits)))
        q = hits[0]
        pos = q["position"]
        return {"corner": [pos["x"], pos["z"]], "y": pos["y"], "rotation": q.get("rotation", "none"),
                "mirror": q.get("mirror", "none"), "size": list(s["size"]),
                "author": "data/placements.json %s" % q["id"]}
    p = s.get("placement")
    if not p:
        raise SystemExit("%s is neither scheduled nor carries a placement block" % s.get("id"))
    return {"corner": list(p["corner"]), "y": p["y"], "rotation": p.get("rotation", "none"),
            "mirror": p.get("mirror", "none"), "size": list(s["size"]),
            "author": "data/adopted_legendary_sites.json %s.placement" % s["id"]}


def footprint(s, placements=None):
    """Inclusive (x0, z0, x1, z1) the corner, rotation and size imply."""
    w = where(s, placements)
    x0, z0 = w["corner"]
    sx, _, sz = w["size"]
    turned = [TURN[w["rotation"]](dx, dz) for dx in (0, sx - 1) for dz in (0, sz - 1)]
    xs = [x0 + a for a, _ in turned]
    zs = [z0 + b for _, b in turned]
    return min(xs), min(zs), max(xs), max(zs)


def centre(s, placements=None):
    """[x, z] of the footprint's middle: min + width // 2, the record's own `centre` convention (corner + size // 2
    for rotation none; Articuno's 20-wide tower at corner 672 has its centre at 682)."""
    x0, z0, x1, z1 = footprint(s, placements)
    return [x0 + (x1 - x0 + 1) // 2, z0 + (z1 - z0 + 1) // 2]


def main(argv=None):
    placements = json.loads(PLACEMENTS.read_text(encoding="utf-8"))["placements"]
    for s in sites():
        w = where(s, placements)
        print("%-26s y%-4d footprint %s  (%s)" % (s["id"], w["y"], footprint(s, placements), w["author"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
