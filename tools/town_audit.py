#!/usr/bin/env python
"""After a town is built: is there a block in it that decides what spawns there?

The policy check in tools/validate_data.py reads templates. This reads the world, which is the only
thing that catches what a template does not say: a jigsaw that resolved into a substituted block, a
donor placed by resource id whose substitution fills were refused, a path laid in the wrong material,
or anything a later hand-edit put there. Misty's gym kept 958 blocks of vanilla concrete through a
clean template check, because the fills that should have replaced them were over the /fill limit and
the server refused them in silence.

A block is a problem here when it is named by a Cobblemon spawn condition (data/spawn_blocks.json),
is not whitelisted in data/spawn_block_policy.json, and is the `from` side of a substitution that was
supposed to have removed it. Whitelisted blocks are reported as a count, not an error: a town is
allowed beds and flowers, and seeing how many is useful.

  python tools/town_audit.py gym1_town --world <stopped world copy>
  python tools/town_audit.py --all --world <stopped world copy>

Ownership: read-only. It never writes to the world and never touches the live save.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def policy_sets(policy, triggers):
    """(blocks that must not appear, blocks that are allowed on purpose)."""
    substituted_from = {s["from"] for s in policy.get("substitutions") or [] if isinstance(s, dict)}
    allowed = set()
    for w in policy.get("whitelist") or []:
        allowed |= set(w.get("blocks") or [])
    return substituted_from, allowed


def town_bounds(settlement, placements, margin=8):
    """The ground a town occupies: every placement, street and plaza it records."""
    s = placements["settlements"][settlement]
    plan = s.get("plan") or {}
    xs, zs = [], []
    for q in placements["placements"]:
        if q.get("settlement") != settlement:
            continue
        pos = q["position"]
        size = q.get("size") or [24, 0, 24]
        xs += [pos["x"], pos["x"] + size[0]]
        zs += [pos["z"], pos["z"] + size[2]]
    for street in plan.get("streets") or []:
        for x, z in street.get("polyline") or []:
            xs.append(x)
            zs.append(z)
    for r in s.get("roads") or []:
        for x, z in r.get("polyline") or []:
            xs.append(x)
            zs.append(z)
    pz = plan.get("plaza")
    if pz and (pz.get("rect") or pz.get("box")):
        rect = pz.get("rect") or pz["box"]
        xs += [rect[0], rect[2]]
        zs += [rect[1], rect[3]]
    if not xs:
        raise SystemExit("%s: nothing placed and no streets, so there is nothing to audit" % settlement)
    return min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin


def town_y_range(settlement, placements, pad_below=4, pad_above=8):
    """The vertical slice the town occupies.

    Scanning the whole column reads the ore and lava the world generated under the town, which is not
    the town's doing and drowns the finding that is. The slice runs from a little under the lowest
    floor to a little over the tallest roof.
    """
    floors, tops = [], []
    rep = ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)
    if rep.is_file():
        for b in json.loads(rep.read_text(encoding="utf-8")).get("buildings") or []:
            if b.get("floor_y") is not None:
                floors.append(b["floor_y"])
                tops.append(b["floor_y"] + 24)
    for q in placements["placements"]:
        if q.get("settlement") != settlement:
            continue
        y = (q.get("position") or {}).get("y")
        if y is not None:
            floors.append(y)
            tops.append(y + (q.get("size") or [0, 24, 0])[1])
    plan = (placements["settlements"][settlement].get("plan") or {})
    for a in plan.get("anchors") or []:
        for v in (a.get("ground_range") or []):
            floors.append(int(v))
            tops.append(int(v) + 24)
    if (plan.get("plaza") or {}).get("y") is not None:
        floors.append(plan["plaza"]["y"])
        tops.append(plan["plaza"]["y"] + 8)
    if not floors:
        return -64, 200
    return min(floors) - pad_below, max(tops) + pad_above


def audit(settlement, world, y_range=None):
    import structure_nbt as SN
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    blocks_doc = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))
    triggers = set(blocks_doc.get("blocks") or blocks_doc)
    must_not, allowed = policy_sets(policy, triggers)

    x0, z0, x1, z1 = town_bounds(settlement, placements)
    y_range = y_range or town_y_range(settlement, placements)
    cap = SN.capture(world, (x0, y_range[0], z0), (x1, y_range[1], z1))

    # A block inside a footprint we placed is ours and has to answer for itself. One outside is the
    # site: the coal and iron under a town are the world's, not the builder's, and reporting them as
    # findings buries the ones that matter.
    # the boxes are three-dimensional on purpose: a building's footprint in plan also covers the
    # ground under it, and the coal seam a town happens to stand on is not something the builder put
    # there. Each box runs from its floor to its roof, with a couple of blocks of foundation below.
    floors = {}
    rep = ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)
    if rep.is_file():
        for b in json.loads(rep.read_text(encoding="utf-8")).get("buildings") or []:
            if b.get("floor_y") is not None:
                floors[b["id"]] = b["floor_y"]
    ours = []
    for q in placements["placements"]:
        if q.get("settlement") != settlement:
            continue
        pos, size = q["position"], q.get("size") or [28, 24, 28]
        base = pos.get("y", floors.get(q["id"]))
        if base is None:
            base = y_range[0] + 4
        # from the floor up, not from the foundations down: the ore behind a foundation course is
        # the ground the town was built on, and the builder did not choose it
        ours.append((pos["x"], pos["x"] + size[0] - 1, base, base + size[1] - 1,
                     pos["z"], pos["z"] + size[2] - 1))

    def placed(x, y, z):
        return any(a <= x <= b and c <= y <= d and e <= z <= f for a, b, c, d, e, f in ours)

    inside, outside = Counter(), Counter()
    for (x, y, z), v in cap.blocks.items():
        name = v[0]
        if name in triggers:
            (inside if placed(x, y, z) else outside)[name] += 1
    unsubstituted = {b: n for b, n in inside.items() if b in must_not}
    unlisted = {b: n for b, n in inside.items() if b not in allowed and b not in must_not}
    listed = {b: n for b, n in inside.items() if b in allowed}
    return {"settlement": settlement, "bounds": [x0, z0, x1, z1], "y_range": list(y_range),
            "blocks_read": len(cap.blocks), "placed_footprints": len(ours),
            "unsubstituted": dict(sorted(unsubstituted.items())),
            "not_in_policy": dict(sorted(unlisted.items())),
            "whitelisted_present": dict(sorted(listed.items())),
            "in_the_ground_around_it": dict(sorted(outside.items()))}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("settlement", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--world", required=True, help="a STOPPED world copy; never the live save")
    p.add_argument("--json", action="store_true", dest="as_json")
    a = p.parse_args(argv)
    if "cobblers-10240" in Path(a.world).as_posix():
        raise SystemExit("refusing to read the live world")
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    names = sorted(placements["settlements"]) if a.all else [a.settlement]
    if not names or names == [None]:
        raise SystemExit("name a settlement or pass --all")
    bad = 0
    out = []
    for name in names:
        try:
            res = audit(name, a.world)
        except SystemExit as exc:
            print("%-12s skipped: %s" % (name, exc))
            continue
        out.append(res)
        problems = len(res["unsubstituted"]) + len(res["not_in_policy"])
        bad += problems
        if a.as_json:
            continue
        print("%-12s %s blocks read in %s, y %d to %d"
              % (name, format(res["blocks_read"], ","), res["bounds"], res["y_range"][0], res["y_range"][1]))
        for b, n in res["unsubstituted"].items():
            print("   UNSUBSTITUTED %-44s %d  (a substitution was supposed to remove this)" % (b, n))
        for b, n in res["not_in_policy"].items():
            print("   NOT IN POLICY %-44s %d  (decides spawns and nothing says it may)" % (b, n))
        if res["whitelisted_present"]:
            print("   allowed on purpose: %s"
                  % ", ".join("%s %d" % (b.split(":")[-1], n) for b, n in res["whitelisted_present"].items()))
        if res["in_the_ground_around_it"]:
            top = sorted(res["in_the_ground_around_it"].items(), key=lambda kv: -kv[1])[:5]
            print("   in the ground around it, not ours: %s"
                  % ", ".join("%s %d" % (b.split(":")[-1], n) for b, n in top))
        if not problems:
            print("   clean: nothing inside a footprint we placed decides a spawn without saying so")
    if a.as_json:
        print(json.dumps(out, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
