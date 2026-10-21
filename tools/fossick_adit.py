#!/usr/bin/env python
"""The Fossick adit: a built hill east of the mining town whose west face opens into the Fossick Deep Galleries.

The owner, 2026-10-20, of the galleries' free-standing timber frame over a stair shaft on the flat (tools/mining_caves.py's
own mouth, which R9OC built): "make fossick like route 1". The Route 1 old mine (tools/route1_old_mine.py) is not cut
into a natural slope: it builds a hill on flat ground and digs a timbered adit into it. This is that hill and that adit,
from the same code (tools/hill_adit.py), not a copy of it; the ground here is as flat (143-149 over 90 blocks), and the
hill is a little smaller than Route 1's so its west foot keeps five columns from the town's slag heap
(data/placements.json mining_town_works) and eleven from the town's footprint.

  the hill      Route 1's dome, mirrored so its long face is the west one the adit enters, 36 x 36 and 16 high, on the
                heightmap's ground (tools/ground.py, rounded, never a world's surface). Its skin is the Craters' ground,
                not Route 1's grass: basalt, blackstone and gravel (the paint here is data/regions.json east_cones,
                preset volcanic: BASALT), bare rock where it is steep. No trees: none is painted within the hill
  the adit      Route 1's: the notch open to the sky, the spruce portal, a level of two cells under a timber set, the
                old track's sleepers, then the incline: cobblestone stairs down eastward, the full width, a lantern
                every four stairs. The incline falls exactly from the level's feet to the galleries' hall floor
                (data/mining_caves.json cave_fossick: the hall's feet y124), so it is as long as that fall
  the foot      the incline's last stair stands in front of the hall's near end wall, where the guild's old incline
                came in; the row of the end wall itself is the opening (entry.host.opening), written here as air with
                its floor, its two sides and its roof (the cave's build writes the opening as air and grows no wall
                over it: tools/mining_caves.py, R9OC)
  outside       a short worn path of coarse dirt out of the notch toward the town (a street of the plan, graded as
                the town pass grades it, and laid by the earthwork too), the spoil heap of
                gravel and cobbled deepslate south of the portal, a lamp post in the notch, four boulders on the flanks

Built with the towns (R8) as the earthwork fossick_adit_hill of its own settlement, like the Route 1 old mine. In a
world that already has the galleries' old frame and shaft (the live world), step R9OCR (tools/mining_caves.py
reroute_files) first puts the old mouth back to the heightmap's terrain and then runs exactly these lines, gated on the
portal's beam (entry.host.probe), so a rerouted world matches a fresh export and a second run writes nothing.

No block here decides a spawn (the spawn-condition list tools/route1_old_mine.py and validate_data read): no ore, no
magma, no rail, no water.

  python tools/fossick_adit.py --source-root <root>     # writes the settlement and its earthwork
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ground as G
import hill_adit as HA
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

ROOT = Path(__file__).resolve().parent.parent
SID = "fossick_adit"
RID = "fossick_adit_hill"
CELL = "F7"
Z_AXIS = 5804                        # the adit's centre line: the galleries' hall's (data/mining_caves.json cave_fossick)
PORTAL_X = 6764                      # the portal's outer face; the notch runs west from it to the hill's foot
PEAK = (6778, 5804)                  # east of the portal, so the west face the adit enters is the long one
RX, RZ, HEIGHT = 18, 18, 16          # the dome's half-widths and its rise at the peak
CLEAR_MARGIN = 2                     # cleared round the hill (Route 1: 5); no painted tree stands within 4 of it
HILL = HA.Hill(PEAK, RX, RZ, HEIGHT, mirror=True)
# the worn path: out of the notch's mouth toward the town, one street of the settlement's plan, laid by this
# earthwork exactly as tools/town_plan.py grades a street (town_plan.graded_cells), so the live world's reroute (which
# runs no town pass) and a fresh export (whose prep paves it too) end the same. It runs along z5807, south of the
# slag heap (mining_town_works writes x6744..6752 z5795..5801), and stops where it would come within 12 of what the
# town authors at its edge (data/placements.json mining_town's anchor at x6742 z5802..5816, data/landmarks.json's
# mine portal at (6736, 5800)): the caves' authored_clearance, which the audit holds the hill to
PATH = ((6757, 5807), (6756, 5807))
STREET = {"id": "path", "polyline": [list(p) for p in PATH], "width": 3, "surface": "minecraft:coarse_dirt",
          "max_grade": 0.15, "why": "the carts' old way out of the notch toward the town's mine spur, worn into the ground: "
                                   "it says the notch is a way in (Route 1's old mine has its trail)"}
PATH_END = min(x for x, _ in PATH)
# the spoil heap south of the portal, the boulders on the flanks: Route 1's, mirrored and moved to this hill
SPOIL = ((6761, 5808), (6760, 5808), (6759, 5809), (6761, 5809), (6760, 5809), (6760, 5810), (6759, 5810))
BOULDERS = ((6789, 5799), (6767, 5793), (6771, 5817), (6786, 5816))


def skin(x, z, steep):
    """The Craters' ground on the hill: basalt, with blackstone and gravel where it steepens, now and then smooth
    basalt (Route 1's rule, tools/hill_adit.py route1_skin, with this ground's blocks)."""
    k = HA.h32(x, z, 3) % 14
    return ("minecraft:blackstone" if steep == 2 and k < 5 else "minecraft:gravel" if steep == 2 and k < 7
            else "minecraft:smooth_basalt" if k == 0 else "minecraft:basalt[axis=y]")


def steep_rock(x, y, z):
    k = HA.h32(x, y, z, 7) % 20
    return ("minecraft:blackstone" if k < 6 else "minecraft:tuff" if k < 8 else "minecraft:smooth_basalt" if k < 9
            else "minecraft:basalt[axis=y]")


PALETTE = {"skin": skin, "under": "minecraft:blackstone", "steep": steep_rock}


def opening():
    """(x0, y0, z0, x1, y1, z1, cave id): the hole in the galleries' near end wall the incline ends in, as
    data/mining_caves.json records it for the cave whose entry is a passage from this adit (entry.host.settlement)."""
    spec = json.loads((ROOT / "data" / "mining_caves.json").read_text(encoding="utf-8"))
    hosted = [c for c in spec["caves"] if ((c.get("entry") or {}).get("host") or {}).get("settlement") == SID]
    if len(hosted) != 1:
        raise SystemExit("data/mining_caves.json: %d caves are entered from %s, not one" % (len(hosted), SID))
    x0, y0, z0, x1, y1, z1 = hosted[0]["entry"]["host"]["opening"]
    return x0, y0, z0, x1, y1, z1, hosted[0]["id"]


def adit(g):
    """The adit's line: the level's feet over the ground outside the portal, and an incline exactly as long as the fall
    from there to the opening's feet, ending one row in front of the opening."""
    ox0, oy0, oz0, ox1, oy1, oz1, _cid = opening()
    if ox0 != ox1 or (oz0, oz1) != (Z_AXIS - 1, Z_AXIS + 1) or oy1 - oy0 != 3:
        raise SystemExit("the adit's opening %s is not one row deep in x, 3 wide about z%d and 4 high"
                         % ([ox0, oy0, oz0, ox1, oy1, oz1], Z_AXIS))
    feet = g(PORTAL_X - 1, Z_AXIS) + 1
    drop = feet - oy0
    if drop < 1:
        raise SystemExit("the opening's feet y%d are not under the adit's feet y%d" % (oy0, feet))
    return HA.Adit(PORTAL_X, ox0 - 1 - drop, Z_AXIS, drop, 1)


def problems(g, top, a, feet):
    """Where the hill would not hold its adit: a level or incline roof above the hill's surface (a stone strip on the
    slope, or daylight through it), or a portal face lower than the portal."""
    probs = []
    surf = lambda x, z: top.get((x, z), g(x, z))
    lo, hi = a.level()
    for x in range(lo, hi + 1):
        for z in range(Z_AXIS - 2, Z_AXIS + 3):
            if feet + 4 > surf(x, z):
                probs.append("the level's roof y%d stands over the hill's surface y%d at (%d, %d)" % (feet + 4, surf(x, z), x, z))
    for i in range(1, a.drop + 1):
        x, y = a.stair(i, feet)
        for z in range(Z_AXIS - 2, Z_AXIS + 3):
            if y + 5 > surf(x, z):
                probs.append("the incline's roof y%d stands over the hill's surface y%d at (%d, %d)" % (y + 5, surf(x, z), x, z))
    if surf(a.portal_x, Z_AXIS) < feet + 4:
        probs.append("the hill's face at the portal (y%d) is under the portal's beam (y%d)" % (surf(a.portal_x, Z_AXIS), feet + 4))
    return probs


def build(g):
    """The hill, the adit, the foot into the galleries and the outside, as commands (the earthwork's)."""
    a = adit(g)
    top, clear = HILL.plan(g, CLEAR_MARGIN)
    c = ["# the Fossick adit: a hill east of the mining town with a timbered adit in its west face and an incline down into "
         "the Fossick Deep Galleries (tools/fossick_adit.py, tools/hill_adit.py)"]
    HA.site(c, g, clear)
    HA.hill_body(c, g, top, PALETTE)
    feet = HA.adit(c, g, top, a)
    probs = problems(g, top, a, feet)
    if probs:
        raise SystemExit("the Fossick adit: %d problem(s), e.g. %s" % (len(probs), probs[0]))
    # ---- the foot: the opening row, the hall's near end wall, cut as the last row of the passage
    ox, oy, _oz, _x1, _y1, _z1, _cid = opening()
    Z = Z_AXIS
    c.append("fill %d %d %d %d %d %d minecraft:stone" % (ox, oy - 2, Z - 1, ox, oy - 1, Z + 1))
    for z in (Z - 2, Z + 2):
        c.append("fill %d %d %d %d %d %d %s" % (ox, oy - 1, z, ox, oy + 4, z, HA.rock(ox, oy, z)))
    c.append("fill %d %d %d %d %d %d minecraft:stone" % (ox, oy + 4, Z - 1, ox, oy + 4, Z + 1))
    c.append("fill %d %d %d %d %d %d minecraft:air" % (ox, oy, Z - 1, ox, oy + 3, Z + 1))
    # ---- outside: the worn path, the spoil heap, the lamp, boulders
    c += path_lines(g)
    HA.outside(c, g, top, a, feet, SPOIL, (), BOULDERS, boulder_blocks=("minecraft:blackstone", "minecraft:basalt[axis=y]"),
               spoil_blocks=("minecraft:gravel", "minecraft:cobbled_deepslate"))
    # the portal's lamp stands on a fence the site clear removes, and it would drop as an item on every rebuild
    c[1:1] = ["setblock %d %d %d minecraft:air" % HA.lamp_post(a, feet)]
    return c


def path_lines(g):
    """The worn path's commands: per cell of STREET as tools/town_plan.py grades it, air from the paving up to the ground
    where it cuts, earth under it where it fills, the paving, and headroom over it (town_plan's prep, unfiltered)."""
    import town_plan as TP
    _pts, _gr, _target, cells = TP.graded_cells(STREET, lambda x, z: g(int(round(x)), int(round(z))))
    out = []
    for (x, z), y in sorted(cells.items()):
        gy = g(x, z)
        if gy > y:
            out.append("fill %d %d %d %d %d %d minecraft:air" % (x, y + 1, z, x, gy, z))
        if gy < y - 1:
            out.append("fill %d %d %d %d %d %d minecraft:dirt" % (x, gy + 1, z, x, y - 1, z))
        out.append("setblock %d %d %d %s" % (x, y, z, STREET["surface"]))
        out.append("fill %d %d %d %d %d %d minecraft:air" % (x, y + 1, z, x, y + TP.HEADROOM, z))
    return out


def probe(g):
    """(x, y, z, block): the portal beam's middle, which stands only once this has been built (entry.host.probe)."""
    a = adit(g)
    return [a.portal_x, a.feet(g) + 4, Z_AXIS, "minecraft:spruce_log"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=env_source_root())
    args = p.parse_args(argv)
    g = G.Ground(args.source_root)
    a = adit(g)
    top, clear = HILL.plan(g, CLEAR_MARGIN)
    cmds = build(g)
    feet = a.feet(g)
    path = ROOT / "data" / "placements.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    import town_plan as TP
    paved = TP.graded_cells(STREET, lambda x, z: g(int(round(x)), int(round(z))))[3]
    xs = [x for x, _ in clear] + [x for x, _ in paved]
    zs = [z for _, z in clear] + [z for _, z in paved]
    ox, oy, oz0, _x1, _y1, oz1, cid = opening()
    doc["settlements"][SID] = {
        "centre": list(PEAK), "status": "authored 2026-10-20; not built anywhere yet (staging or live)",
        "plan": {
            "reading": "East of the mining town, past the slag heap, a dark hill of basalt rises on its own out of the "
                       "flat. Its west face has been cut: a notch in the slope, a spruce portal, the old track's sleepers "
                       "running in under a timber set, and then the guild's incline, stair after stair down into the "
                       "deep seams, lanterns hanging every few steps, until it comes out at the end of the galleries' "
                       "hall, twenty-two blocks under the plain.",
            "entries": [{"from": "the mining town's mine spur, past the slag heap", "at": list(PATH[-1]),
                         "street": "path"}],
            "exits": [],
            "footprint": {"rect": [min(xs), min(zs), max(xs), max(zs)],
                          "why": "the hill, the ground cleared round it and the worn path out of the notch; the incline "
                                 "under it ends at the galleries' near end wall (data/mining_caves.json %s)" % cid},
            "streets": [STREET],
            "anchors": [{"id": "hill", "role": "landmark", "template": None,
                         "rect": [min(x for x, _ in top), min(z for _, z in top), max(x for x, _ in top), max(z for _, z in top)],
                         "facing": "west", "why": "the hill and its adit (earthwork fossick_adit_hill)"}],
            "house_lots": {"along": [], "why": "no houses"},
            "paving": {"main": "minecraft:coarse_dirt", "lamp": "none", "why": "a worn path, unlit; the portal has its lamp"},
            "no_services": "a mine entrance off the town, not a town",
            "prep_note": "the town pass grades and paves the path (tools/town_plan.py); the earthwork lays the same cells the "
                         "same way, so a live world rerouted by R9OCF (which runs no town pass) gets it too",
        },
    }
    rec = {"id": RID, "settlement": SID, "kind": "earthwork", "cell": CELL, "status": "planned",
           "chosen_because": "the owner, 2026-10-20: \"make fossick like route 1\": the Fossick Deep Galleries entered "
                             "by an adit in a built hill, as the Route 1 old mine is, not by a free-standing frame on "
                             "the flat; see tools/fossick_adit.py",
           "commands": cmds}
    at = next((i for i, q in enumerate(doc["placements"]) if q["id"] == RID), None)
    if at is None:
        doc["placements"].append(rec)
    else:
        doc["placements"][at] = rec
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote %s: %d commands; hill %d columns x%d..%d z%d..%d, peak y%d; portal x%d feet y%d, incline %d stairs "
          "to the opening (%d, %d, %d..%d); probe %s" % (
              SID, len(cmds), len(top), min(x for x, _ in top), max(x for x, _ in top), min(z for _, z in top),
              max(z for _, z in top), max(top.values()), a.portal_x, feet, a.drop, ox, oy, oz0, oz1, probe(g)))


if __name__ == "__main__":
    main()
