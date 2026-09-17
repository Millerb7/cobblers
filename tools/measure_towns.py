#!/usr/bin/env python
"""Re-measure the derived numbers on every town in data/towns.json.

Off-path places get distance_from_critical_path_blocks and nearest_leg measured on data/routes.json polylines. With a
source root, every town also gets centre.ground_y, footprint.ground_y and footprint.slope_degrees measured on the
canonical heightmap (plus any built_ground, e.g. Relic Island's islet). Positions, footprints, statuses and prose are
never touched: siting is an authored decision. The measurements are the same functions tools/validate_data.py checks
against, so a clean --write leaves those checks clean.

  python tools/measure_towns.py [--source-root <root>]            # report what would change
  python tools/measure_towns.py [--source-root <root>] --write    # rewrite data/towns.json in place
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_data as V  # noqa: E402


def refresh(towns_doc, routes_doc, heights=None, world=None):
    """Update towns_doc in place; return a list of (town id, field, old, new) for every value that changed."""
    changes = []
    for t in towns_doc["towns"]:
        tid = t["id"]
        if not t.get("critical_path"):
            m = V.measure_nearest_leg(routes_doc, t.get("centre"))
            if m is not None:
                dist, leg = m
                if t.get("distance_from_critical_path_blocks") != round(dist):
                    changes.append((tid, "distance_from_critical_path_blocks", t.get("distance_from_critical_path_blocks"), round(dist)))
                    t["distance_from_critical_path_blocks"] = round(dist)
                if "nearest_leg" in t and V._nearest_leg_problems(routes_doc, t["centre"], t["nearest_leg"]):
                    changes.append((tid, "nearest_leg", t["nearest_leg"], leg))
                    t["nearest_leg"] = leg
        if heights is None:
            continue
        m = V.measure_town_ground(heights, world, t)
        c, fp = t["centre"], t["footprint"]
        new_c = round(m["centre_ground_y"], 1)
        if c.get("ground_y") != new_c:
            changes.append((tid, "centre.ground_y", c.get("ground_y"), new_c))
            c["ground_y"] = new_c
        new_g = [round(v, 1) for v in m["footprint_ground_y"]]
        if fp.get("ground_y") != new_g:
            changes.append((tid, "footprint.ground_y", fp.get("ground_y"), new_g))
            fp["ground_y"] = new_g
        new_s = {"mean": round(m["slope_mean"], 1), "max": round(m["slope_max"], 1)}
        old_s = fp.get("slope_degrees") or {}
        if {k: old_s.get(k) for k in ("mean", "max")} != new_s:
            changes.append((tid, "footprint.slope_degrees", old_s, new_s))
            fp["slope_degrees"] = {**old_s, **new_s}
    return changes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default=str(ROOT / "data"))
    p.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"),
                   help="root of the out-of-repo source/ tree; without it heights are not measured")
    p.add_argument("--write", action="store_true", help="rewrite towns.json")
    a = p.parse_args(argv)
    data = Path(a.data)
    towns_path = data / "towns.json"
    towns = json.loads(towns_path.read_text(encoding="utf-8"))
    routes = json.loads((data / "routes.json").read_text(encoding="utf-8"))
    heights = world = None
    if a.source_root:
        import terrain as T
        heights, world = T.load(data / "world.json", a.source_root)
        if towns.get("computed_from_sha256") and towns["computed_from_sha256"] != world["heightmap"]["sha256"]:
            print("towns.json computed_from_sha256 %s -> %s" % (towns["computed_from_sha256"][:12], world["heightmap"]["sha256"][:12]))
            towns["computed_from_sha256"] = world["heightmap"]["sha256"]
    else:
        print("no source root: heights not measured, only route-derived fields")
    changes = refresh(towns, routes, heights, world)
    for tid, field, old, new in changes:
        print("%-22s %-34s %s -> %s" % (tid, field, json.dumps(old, ensure_ascii=False), json.dumps(new, ensure_ascii=False)))
    print("%d change(s)" % len(changes))
    if a.write and changes:
        towns_path.write_text(json.dumps(towns, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("wrote %s" % towns_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
