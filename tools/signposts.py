#!/usr/bin/env python
"""Route signposts: a post at every town exit, every sub-region transition along a route, and every junction where a
place's own path leaves a route, each naming where the road goes. Two-faced: the front faces the traveller going the
way it names, the back the traveller coming the other way.

  function   build/datapacks/cobblers_signs (cobblers:signs/place) and derived/signposts.json (every post)
  verify     read a STOPPED world: every post's sign stands where it should and says what it should

  python tools/signposts.py function --source-root <root>
  python tools/signposts.py verify --world <stopped world copy>

Where each goes, from committed data only (data/routes.json, data/towns.json, data/placements.json plans and
data/signposts.json): a town exit is the from-town's plan exit towards the leg's destination, else the first point of
the leg outside the town's footprint; the arrival end is the to-town's plan entry from the leg's origin, else the last
point before its footprint; transitions are the leg's own geography.transitions; junctions are every plan entry whose
`from` is a route, and data/signposts.json junctions. Each post stands `offset_blocks` to the traveller's right on
heightmap ground (tools/ground.py), never on painted water: a post that would stand in water moves along the road.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "build" / "datapacks" / "cobblers_signs"
REPORT = ROOT / "derived" / "signposts.json"
MIN_GAP = 150                 # blocks between transition posts on one route


# The ground rule (tools/ground_rule.py): the functions here that read a world, each only to check, never to
# decide a position: `verify` reads a stopped world to check every post; `function` never does.
WORLD_READS = {'main', 'verify'}


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def dense(poly, step=1.0):
    out = []
    for (ax, az), (bx, bz) in zip(poly, poly[1:]):
        L = math.hypot(bx - ax, bz - az)
        n = max(1, int(L / step))
        for i in range(n):
            out.append((ax + (bx - ax) * i / n, az + (bz - az) * i / n))
    out.append(tuple(poly[-1]))
    return out


def inside(fp, x, z, pad=0):
    return fp["min_x"] - pad <= x <= fp["max_x"] + pad and fp["min_z"] - pad <= z <= fp["max_z"] + pad


def rotation(fx, fz):
    """Standing-sign rotation (0 south, 4 west, 8 north, 12 east) whose front faces the direction (fx, fz)."""
    return int(round(math.degrees(math.atan2(-fx, fz)) / 22.5)) % 16


def lines(*texts):
    out = []
    for t in texts:
        while t and len(out) < 4:
            if len(t) <= 15:
                out.append(t)
                break
            cut = t.rfind(" ", 0, 16)
            cut = cut if cut > 0 else 15
            out.append(t[:cut])
            t = t[cut:].strip()
    return (out + [""] * 4)[:4]


def place_names():
    """{settlement id: the name a player reads}. A settlement's display name in data/towns.json once it has one,
    until then its working name in data/signposts.json `names`. Signposts and location titles
    (tools/location_titles.py) both read this, so a real name lands on both at once."""
    names = dict(load("signposts.json")["names"])
    for t in load("towns.json")["towns"]:
        if t.get("display_name"):
            names[t["id"]] = t["display_name"]
    return names


def posts(ground, wet):
    """[{id, x, y, z, rotation, front, back, why}] for every post."""
    cfg = load("signposts.json")
    names = place_names()
    label = cfg["route_labels"]
    towns = {t["id"]: t for t in load("towns.json")["towns"]}
    doc = load("placements.json")
    plans = {s: (v.get("plan") or {}) for s, v in doc["settlements"].items()}
    off = cfg.get("offset_blocks", 4)
    out = []

    def seat(pid, pts, i, front, back, why):
        """A post beside point i of a dense polyline, facing travellers moving towards increasing i."""
        for k in list(range(i, min(len(pts) - 1, i + 30))) + list(range(i - 1, max(0, i - 30), -1)):
            a, b = pts[max(0, k - 2)], pts[min(len(pts) - 1, k + 2)]
            dx, dz = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dz) or 1.0
            dx, dz = dx / L, dz / L
            x, z = int(round(pts[k][0] - dz * off)), int(round(pts[k][1] + dx * off))
            if wet[z - ground.oz, x - ground.ox]:
                continue
            out.append({"id": pid, "x": x, "y": ground(x, z) + 1, "z": z, "rotation": rotation(-dx, -dz),
                        "front": lines(*front), "back": lines(*back), "why": why})
            return
        print("  no dry ground for post %s" % pid)

    for r in load("routes.json")["routes"]:
        rl = label.get(r["id"], r["id"])
        ft, tt = r.get("from_town"), r.get("to_town")
        pts = dense([(p["x"], p["z"]) for p in r["corridor"]["polyline"]])
        fp_from = (towns.get(ft) or {}).get("footprint")
        fp_to = (towns.get(tt) or {}).get("footprint")
        # town exit, at the from-end
        ex = next((e for e in plans.get(ft, {}).get("exits") or [] if e.get("to") == tt), None)
        if ex:
            i = min(range(len(pts)), key=lambda k: (pts[k][0] - ex["at"][0]) ** 2 + (pts[k][1] - ex["at"][1]) ** 2)
        else:
            i = next((k for k, p in enumerate(pts) if not (fp_from and inside(fp_from, *p, pad=8))), 0)
        seat("%s_leaving_%s" % (r["id"], ft), pts, min(i + 6, len(pts) - 1), (rl, "to", names.get(tt, tt)),
             (names.get(ft, ft),), "the town exit: %s leaves %s" % (rl, names.get(ft, ft)))
        # arrival end: a post before the to-town, facing travellers leaving it the other way
        en = next((e for e in plans.get(tt, {}).get("entries") or [] if e.get("from") == ft), None)
        if en:
            j = min(range(len(pts)), key=lambda k: (pts[k][0] - en["at"][0]) ** 2 + (pts[k][1] - en["at"][1]) ** 2)
        else:
            j = next((k for k in range(len(pts) - 1, -1, -1) if not (fp_to and inside(fp_to, *pts[k], pad=8))), len(pts) - 1)
        rev = pts[::-1]
        seat("%s_leaving_%s" % (r["id"], tt), rev, min(len(pts) - 1 - j + 6, len(pts) - 1), (rl, "to", names.get(ft, ft)),
             (names.get(tt, tt),), "the town exit: %s leaves %s" % (rl, names.get(tt, tt)))
        # sub-region transitions along the leg
        # A boundary is recorded as a pair (into the overlap, out of it), and a wandering boundary is crossed several
        # times in a few blocks: only a settled change of sub-region gets a post, and never within MIN_GAP of the last
        nm = lambda sid: SUBNAMES.get(sid) or sid.replace("_", " ").title()
        current, last_d = None, -10 ** 6
        for n, t in enumerate(r.get("geography", {}).get("transitions") or []):
            subs_here = t.get("subregions") or []
            if len(subs_here) != 1:
                continue
            if current is None:
                current = subs_here[0]
                continue
            if subs_here[0] == current or t["at_distance_blocks"] - last_d < MIN_GAP:
                current = subs_here[0] if t["at_distance_blocks"] - last_d >= MIN_GAP else current
                continue
            k = min(range(len(pts)), key=lambda q: (pts[q][0] - t["at"]["x"]) ** 2 + (pts[q][1] - t["at"]["z"]) ** 2)
            seat("%s_transition_%d" % (r["id"], n), pts, k, (rl, nm(subs_here[0]), "to " + names.get(tt, tt)),
                 (rl, nm(current), "to " + names.get(ft, ft)), "the road crosses from %s into %s" % (nm(current), nm(subs_here[0])))
            current, last_d = subs_here[0], t["at_distance_blocks"]
    # junctions where a place's path leaves a route
    routes = {r["id"]: r for r in load("routes.json")["routes"]}
    junctions = [{"route": e["from"], "at": e["at"], "to": s} for s, p in plans.items() for e in p.get("entries") or []
                 if e.get("from") in routes and s not in cfg.get("no_sign", {})]
    junctions += cfg.get("junctions") or []
    for jn in junctions:
        r = routes[jn["route"]]
        pts = dense([(p["x"], p["z"]) for p in r["corridor"]["polyline"]])
        k = min(range(len(pts)), key=lambda q: (pts[q][0] - jn["at"][0]) ** 2 + (pts[q][1] - jn["at"][1]) ** 2)
        seat("junction_%s" % jn["to"], pts, k, (names.get(jn["to"], jn["to"]), "this way"),
             (names.get(jn["to"], jn["to"]), "this way"), "the path to %s leaves %s" % (names.get(jn["to"], jn["to"]), label.get(r["id"], r["id"])))
    return out


SUBNAMES = {}


def _subnames():
    reg = load("regions.json")
    found = {}

    def walk(o):
        if isinstance(o, dict):
            if "id" in o and "display_name" in o and "parent" in o:
                found[o["id"]] = o["display_name"]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(reg)
    return found


def sign_nbt(p, wood):
    q = lambda ls: ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in ls)
    return ("minecraft:%s_sign[rotation=%d]{front_text:{messages:[%s]},back_text:{messages:[%s]}}"
            % (wood, p["rotation"], q(p["front"]), q(p["back"])))


def function(a):
    import ground as G
    import function_limits
    from elder_trees import painted_water
    SUBNAMES.update(_subnames())
    g = G.Ground(a.source_root)
    wet = painted_water(g.heights, g.world)
    ps = posts(g, wet)
    wood = load("signposts.json").get("sign_wood", "spruce")
    cmds = ["# route signposts (tools/signposts.py): %d posts" % len(ps)]
    for p in ps:
        cmds += ["fill %d %d %d %d %d %d minecraft:air" % (p["x"], p["y"], p["z"], p["x"], p["y"] + 2, p["z"]),
                 "setblock %d %d %d minecraft:%s_fence" % (p["x"], p["y"], p["z"], wood),
                 "setblock %d %d %d %s" % (p["x"], p["y"] + 1, p["z"], sign_nbt(p, wood))]
    cmds = function_limits.ensure_loaded(cmds)
    refused = function_limits.check_lines(cmds, "signs/place")
    if refused:
        raise SystemExit("refused: %s" % refused[:2])
    fn = OUT / "data" / "cobblers" / "function" / "signs" / "place.mcfunction"
    fn.parent.mkdir(parents=True, exist_ok=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: route signposts (tools/signposts.py)"}}) + "\n", encoding="utf-8")
    fn.write_text("\n".join(cmds) + "\n", encoding="utf-8", newline="\n")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"wood": wood, "posts": ps}, indent=1), encoding="utf-8")
    print("wrote %d posts: %s" % (len(ps), fn))
    return 0


def verify(a):
    """Every post: the fence at y, the sign at y+1, and the sign's front and back text as written."""
    import nbt
    if "cobblers-10240" in Path(a.world).as_posix():
        raise SystemExit("refusing to read the live world")
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    if not rep.get("posts"):
        # fail closed: nothing to check is not "0 of 0 standing"
        print("no posts in %s: nothing to verify, which fails (run `signposts.py function` first)" % REPORT.name)
        return 1
    wood = rep["wood"]
    by_region = {}
    for p in rep["posts"]:
        by_region.setdefault((p["x"] >> 9, p["z"] >> 9), []).append(p)
    bad = []
    import build_audit as BA
    w = BA.World(a.world)
    for (rx, rz), ps in by_region.items():
        bes = {}
        path = Path(a.world) / "region" / ("r.%d.%d.mca" % (rx, rz))
        for _, _, ch in nbt.region_chunks(path):
            for be in ch.get("block_entities") or []:
                bes[(be.get("x"), be.get("y"), be.get("z"))] = be
        for p in ps:
            fence = w.block(p["x"], p["y"], p["z"])
            sign = w.block(p["x"], p["y"] + 1, p["z"])
            be = bes.get((p["x"], p["y"] + 1, p["z"]))
            text = lambda side: [json.loads(m) if m.startswith(("\"", "{")) else m for m in ((be or {}).get(side) or {}).get("messages") or []]
            flat = lambda ms: [m if isinstance(m, str) else m.get("text", "") for m in ms]
            if fence != "minecraft:%s_fence" % wood or sign != "minecraft:%s_sign" % wood:
                bad.append("%s: %s on %s at %s" % (p["id"], sign, fence, (p["x"], p["y"], p["z"])))
            elif flat(text("front_text")) != p["front"] or flat(text("back_text")) != p["back"]:
                bad.append("%s: says %s / %s" % (p["id"], flat(text("front_text")), flat(text("back_text"))))
    print("%d of %d posts standing and saying what they should" % (len(rep["posts"]) - len(bad), len(rep["posts"])))
    for b in bad[:20]:
        print("   ", b)
    return 1 if bad else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("function")
    f.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    v = sub.add_parser("verify")
    v.add_argument("--world", required=True)
    a = p.parse_args(argv)
    return {"function": function, "verify": verify}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
