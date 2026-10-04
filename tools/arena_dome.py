#!/usr/bin/env python
"""Heaven's Arena as a dome on the Windward Deep's north floor (data/arena_dome.json).

The owner, 2026-10-03: "a small tower that becomes a large dome sort of place with several fighting venues inside the
main place". The site is data/arena_dome.json `site`: since the owner's "can we move the tower to the center, it's
very close to the spire" (2026-10-03) the middle of the Deep's north floor, (3586, 3164) r34, the floor at y0; site A
of docs/world-building/ARENA_SITE_NORTH.md ((3584, 3171) r40) is `superseded_site`. A gatehouse tower on the south
side, its door on the floor route from the lift-bank-3 stair, opens through the drum into the dome: a two-block drum to
y70 under a glass half-ellipsoid to y120 and a cupola to y126 (the HQ's y132 stays the tallest), four 15x15 rings and
a 19x19 grand stage in the middle. Each venue carries the contract the arena runtime reads (challenger_mark,
opponent_spot, post), and the build refuses if any of them is not a floor block with two air above it in what this
tool writes.

THE UNDO (STAGING ONLY). Staging was applied with site A on 2026-10-03 and nothing removes a build. `undo` regenerates
the old dome from `superseded_site` with this same geometry(), subtracts every cell the current dome writes, and lays
back what was there before: the city's own block (tools/deep_city.py build's canvas: the plaza paving at y0), the pit's
tread light (tools/rift_deep.py, its L1 grid) where the city writes nothing at y0, and air above the floor (the pit is
open to the sky and the city writes nothing above y0 on site A's columns; the build fails closed if that stops being
true). The old venue posts (tools/arena_runtime.py's interaction and label, tag cobblers_arena_post) are killed where
they stood. Written to build/staging/cobblers_arena_dome_undo, outside build/datapacks, so tools/reapply.py never sees
it and no fresh build's apply runs it; the live world never had site A.

Ground comes from the pit's ring model (tools/rift_deep.py model(), via tools/deep_city.py city_model()), never from a
world. The build runs the city's own build once (tools/deep_city.py build(), about 10 s, nothing emitted) and refuses
to write any column the city writes anything but floor paving on, anything nearer than `limits.min_street` to what the
city builds or to any lot's door, and anything inside the city's keep-clear and reserved boxes.

What this does NOT cover: the old arena drum at (3609, 3249), which tools/deep_city.py still builds, is not touched or
removed here; nothing is said about the trainers, the NPCs or the challenge posts, which the arena runtime places on
the contract's coordinates.

    python tools/arena_dome.py build [--source-root <root>]
    python tools/arena_dome.py undo [--out DIR] [--source-root <root>]     STAGING ONLY
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import function_limits as FL
import deep_city as DC
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "arena_dome.json"
CITY = ROOT / "data" / "deep_city.json"
FIGHTS = ROOT / "data" / "arena_fights.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_arena_dome"
FOLDER = "arena_dome"
TILE = 64
PART = 3000
AIR = "minecraft:air"
PAVE = {"plaza", "sidewalk", "fill_light"}       # what the city lays flush at y0 on open floor (ARENA_SITE_NORTH.md)
UNDO_OUT = ROOT / "build" / "staging" / "cobblers_arena_dome_undo"
UNDO_FOLDER = "arena_dome_undo"
POST_TAG = "cobblers_arena_post"                 # tools/arena_runtime.py POST: the venue posts' interaction and label
GEOMETRY_KEYS = ("site", "drum", "dome", "tower", "lighting", "entrance", "venues")


class DomeError(Exception):
    pass


def load():
    return json.loads(SPEC.read_text(encoding="utf-8"))


THIN = ("minecraft:lantern", "minecraft:chain", "minecraft:end_rod")


def solid(b):
    """A block a player stands on and cannot walk through. Not tools/deep_city.py's _solid, which counts every
    `*lantern` as thin and so a sea lantern flush in a floor as a hole."""
    if b is None:
        return False
    base = b.split("[")[0]
    return base != AIR and base not in THIN and not base.endswith(("_pane", "_trapdoor", "_door", "_sign", "_button"))


def _near(theta_deg, every):
    """Degrees from theta to the nearest multiple of `every`."""
    m = theta_deg % every
    return min(m, every - m)


# ------------------------------------------------------------------ the shape

def footprint(spec):
    """The columns the build may write: the site's disc, and the tower's box outside it."""
    cx, cz = spec["site"]["centre"]
    R = spec["site"]["radius"]
    cols = {(x, z) for x in range(cx - R, cx + R + 1) for z in range(cz - R, cz + R + 1)
            if math.hypot(x - cx, z - cz) <= R}
    x0, z0, x1, z1 = spec["tower"]["box"]
    cols |= {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    return cols


def geometry(spec, city_spec=None):
    """Every block the dome writes, on a tools/deep_city.py Canvas (a later write replaces an earlier one; phase 2 is
    what needs a block under it: the lanterns)."""
    cs = city_spec or json.loads(CITY.read_text(encoding="utf-8"))
    P = DC.Palette(cs)
    cv = DC.Canvas()
    cx, cz = spec["site"]["centre"]
    y0 = spec["site"]["floor_y"]
    dr, dm, tw, li = spec["drum"], spec["dome"], spec["tower"], spec["lighting"]
    Ri, Ro = dr["wall"]
    base = dm["base"]
    rise = dm["rise"]
    th = dm["thickness"]
    Hi = rise - th
    if dr["top"] != base:
        raise DomeError("the drum's top (%d) and the dome's base (%d) differ" % (dr["top"], base))
    dmat = {k: P(v) for k, v in dr["materials"].items()}
    gmat = {k: P(v) for k, v in dm["materials"].items()}

    def r_of(x, z):
        return math.hypot(x - cx, z - cz)

    def theta(x, z):
        return math.degrees(math.atan2(z - cz, x - cx)) % 360

    def h_out(r):
        return rise * math.sqrt(max(0.0, 1 - (r / Ro) ** 2)) if r <= Ro else -1

    def h_in(r):
        return Hi * math.sqrt(max(0.0, 1 - (r / Ri) ** 2)) if r < Ri else 0

    disc = [(x, z) for x in range(cx - Ro, cx + Ro + 1) for z in range(cz - Ro, cz + Ro + 1) if r_of(x, z) <= Ro]
    top_y = {}
    for x, z in disc:
        r = r_of(x, z)
        hi, ho = h_in(r), math.floor(h_out(r) + 0.5)
        top_y[(x, z)] = base + ho
        if r <= Ri:
            # the interior: air from the floor to under the shell, so a mark's headroom is this build's and not a hope
            cv.col(x, z, y0 + 1, base + int(math.floor(hi)), AIR)
            inlay = dr["inlay_r"][0] < r <= dr["inlay_r"][1]
            cv.put(x, y0, z, dmat["inlay"] if inlay else dmat["floor"])
        else:
            cv.put(x, y0, z, dmat["plinth"])
            t = theta(x, z)
            rib = _near(t, dr["rib_every_deg"]) < dr["rib_width_deg"] / 2
            for y in range(y0 + 1, dr["top"] + 1):
                if y <= dr["plinth_to"]:
                    b = dmat["plinth"]
                elif dr["cornice"][0] <= y <= dr["cornice"][1]:
                    b = dmat["cornice"]
                elif rib:
                    b = dmat["rib"]
                elif any(a <= y <= c for a, c in dr["windows"]):
                    b = dmat["window"]
                else:
                    b = dmat["wall"]
                cv.put(x, y, z, b, owner="drum")
        # the shell: above the inner half-ellipsoid, up to the outer one
        t = theta(x, z)
        mer = r >= 1 and r * math.radians(_near(t, dm["rib_every_deg"])) < 1.0
        for y in range(base + 1, base + ho + 1):
            if r < Ri and (y - base) <= hi:
                continue
            if y in dm["parallels"]:
                b = gmat["parallel"]
            elif mer:
                b = gmat["rib"]
            else:
                b = gmat["glass"]
            cv.put(x, y, z, b, owner="dome")

    # the cupola on the crown
    cu = dm["cupola"]
    crown = top_y[(cx, cz)]
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            cv.put(cx + dx, crown + 1, cz + dz, P(cu["frame"]), owner="cupola")
            if dx and dz:
                cv.put(cx + dx, crown + 2, cz + dz, P(cu["frame"]), owner="cupola")
            elif dx or dz:
                cv.put(cx + dx, crown + 2, cz + dz, P(cu["glass"]), owner="cupola")
            cv.put(cx + dx, crown + 3, cz + dz, P(cu["cap"]), owner="cupola")
    cv.put(cx, crown + 2, cz, P(cu["lamp"]), owner="cupola")
    for y in range(crown + 4, cu["top"] + 1):
        cv.put(cx, y, cz, P(cu["rod"]) + "[facing=up]", owner="cupola")

    # the chandelier: a chain from under the crown's shell to a ring of lamps over the grand stage
    ch = dm["chandelier"]
    under = base + int(math.floor(h_in(0)))
    for y in range(ch["ring_y"] + 1, under + 1):
        cv.put(cx, y, cz, P(ch["chain"]) + "[axis=y,waterlogged=false]", owner="chandelier")
    for dx in range(-4, 5):
        for dz in range(-4, 5):
            rr = math.hypot(dx, dz)
            if ch["ring"][0] <= rr <= ch["ring"][1] or (dx == 0 and dz == 0):
                cv.put(cx + dx, ch["ring_y"], cz + dz, P(ch["lamp"]), owner="chandelier")

    # ---- the tower: outside the drum (r > Ro) in its box; the drum's own wall closes its north side
    x0, z0, x1, z1 = tw["box"]
    tm = {k: P(v) for k, v in tw["materials"].items()}
    tcols = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if r_of(x, z) > Ro]
    perim = {(x, z) for x, z in tcols if x in (x0, x1) or z == z1}
    inner = [c for c in tcols if c not in perim]
    if not inner:
        raise DomeError("the tower's box leaves no lobby outside the drum")
    ix = sorted({x for x, _ in inner})
    iz = sorted({z for _, z in inner})
    tcx, tcz = (ix[0] + ix[-1]) // 2, (iz[0] + iz[-1]) // 2
    win_s = range(tcx - 2, tcx + 3)                    # windows on the south face
    win_ew = range(tcz - 1, tcz + 2)                   # and the east and west faces
    lobby = tw["lobby_to"]
    for x, z in tcols:
        cv.put(x, y0, z, tm["floor"], owner="tower")
        if (x, z) in perim:
            corner = x in (x0, x1) and (z == z1 or r_of(x, z - 1) <= Ro)
            for y in range(y0 + 1, tw["top"] + 1):
                window = any(a <= y <= c for a, c in tw["windows"]) and (
                    (z == z1 and x in win_s) or (x in (x0, x1) and z in win_ew))
                cv.put(x, y, z, tm["corner"] if corner else tm["window"] if window else tm["wall"], owner="tower")
            cv.put(x, tw["top"] + 1, z, tm["rim"], owner="tower")
        else:
            cv.col(x, z, y0 + 1, lobby, AIR, owner="tower")
            cv.put(x, lobby + 1, z, tm["ceiling"], owner="tower")
            for y in range(lobby + 2, tw["top"] + 1):
                # behind a window the block is a lamp, so the window reads lit and the tower holds no dark room
                lit = any(a <= y <= c for a, c in tw["windows"]) and (
                    (z == z1 - 1 and x in win_s) or (x in (x0 + 1, x1 - 1) and z in win_ew))
                cv.put(x, y, z, tm["lit"] if lit else tm["wall"], owner="tower")
            cv.put(x, tw["top"] + 1, z, tm["roof"], owner="tower")
    cv.put(tcx, y0, tcz, tm["floor_light"], owner="tower")
    cv.put(tcx, tw["top"] + 2, tcz, tm["lamp"], owner="tower")
    for y in (tw["top"] + 3, tw["top"] + 4):
        cv.put(tcx, y, tcz, tm["rod"] + "[facing=up]", owner="tower")
    # the door in the south face, and the passage through the drum into the dome
    d = tw["door"]
    for x in range(d["x"][0], d["x"][1] + 1):
        cv.col(x, d["z"], y0 + 1, d["to_y"], AIR, owner="door")
        cv.put(x, d["to_y"] + 1, d["z"], tm["lintel"], owner="tower")
    pa = tw["passage"]
    for x in range(pa["x"][0], pa["x"][1] + 1):
        for z in range(z0, z1 + 1):
            if Ri < r_of(x, z) <= Ro:
                cv.col(x, z, y0 + 1, pa["to_y"], AIR, owner="passage")
                cv.put(x, y0, z, tm["floor"], owner="passage")
                cv.put(x, pa["to_y"] + 1, z, tm["lintel"], owner="drum")

    # ---- the venues
    taken = set()
    for v in spec["venues"]:
        vx, vz = v["centre"]
        h, top, st = v["half"], v["top"], v["steps"]
        for dx in range(-h, h + 1):
            for dz in range(-h, h + 1):
                x, z = vx + dx, vz + dz
                taken.add((x, z))
                border = abs(dx) == h or abs(dz) == h
                for y in range(y0 + 1, top):
                    cv.put(x, y, z, dmat["floor"], owner=v["id"])
                cv.put(x, top, z, dmat["inlay"] if border else dmat["floor"], owner=v["id"])
                corner = abs(dx) == h and abs(dz) == h
                if corner:
                    cv.col(x, z, top + 1, top + 3, P(li["venue_post"]), owner=v["id"])
                    cv.put(x, top + 4, z, P(li["venue_lamp"]) + "[hanging=false,waterlogged=false]", phase=2, owner=v["id"])
                else:
                    cv.col(x, z, top + 1, top + 9, AIR, owner=v["id"])
        cv.put(vx, top, vz, P(li["venue_centre"]), owner=v["id"])
        if h >= 9:
            for dx in (-5, 5):
                for dz in (-5, 5):
                    cv.put(vx + dx, top, vz + dz, P(li["venue_centre"]), owner=v["id"])
        # steps up on the south side, the mark's side: row k (1 = against the ring) has its tread at top + 1 - k
        for k in range(1, st + 1):
            z = vz + h + k
            ty = top + 1 - k
            for x in range(vx - 3, vx + 4):
                taken.add((x, z))
                for y in range(y0 + 1, ty):
                    cv.put(x, y, z, dmat["floor"], owner=v["id"])
                cv.put(x, ty, z, DC.stair(spec["lighting"]["venue_stair"], "north"), owner=v["id"])
                cv.col(x, z, ty + 1, ty + 3, AIR, owner=v["id"])

    # ---- floor lights, flush, on a grid; none under a ring or its steps
    g, fr = li["floor_grid"], li["floor_r"]
    for x, z in disc:
        if (x - cx) % g == 0 and (z - cz) % g == 0 and r_of(x, z) <= fr and (x, z) not in taken:
            cv.put(x, y0, z, P(li["floor"]), owner="floor_light")
    return cv


# ------------------------------------------------------------------ the checks of our own output

def contract_problems(spec, cv):
    """The contract the arena runtime reads (do not rename): every venue's mark, spot and post on a floor block with
    two air above it in this build; the spot 8 across from the mark, the two facing each other; the ranks spread."""
    out = []
    ranks = [r["rank"] for r in json.loads(FIGHTS.read_text(encoding="utf-8"))["ranks"]]
    seen = []
    cx, cz = spec["site"]["centre"]

    def floor_ok(p, what):
        x, y, z = math.floor(p[0]), int(p[1]), math.floor(p[2])
        if p[0] != x + 0.5 or p[2] != z + 0.5:
            out.append("%s %s is not at a block centre" % (what, p[:3]))
        if not solid(cv.get(x, y - 1, z)):
            out.append("%s %s has no floor under it (%s)" % (what, p[:3], cv.get(x, y - 1, z)))
        for yy in (y, y + 1):
            if cv.get(x, yy, z) != AIR:
                out.append("%s %s is not clear at y%d (%s)" % (what, p[:3], yy, cv.get(x, yy, z)))

    for v in spec["venues"]:
        for k in ("id", "ranks", "challenger_mark", "opponent_spot", "post", "name"):
            if k not in v:
                out.append("%s has no %s" % (v.get("id"), k))
        m, s, p = v["challenger_mark"], v["opponent_spot"], v["post"]
        if len(m) != 4 or len(s) != 4 or len(p) != 3:
            out.append("%s: mark/spot need [x, y, z, yaw], post [x, y, z]" % v["id"])
            continue
        floor_ok(m, v["id"] + " challenger_mark")
        floor_ok(s, v["id"] + " opponent_spot")
        floor_ok(p, v["id"] + " post")
        if abs(math.hypot(m[0] - s[0], m[2] - s[2]) - 8) > 1e-6:
            out.append("%s: the spot is %.1f from the mark, not 8" % (v["id"], math.hypot(m[0] - s[0], m[2] - s[2])))
        # Minecraft yaw: 0 = +z, 90 = -x; the direction a yaw looks is (-sin, cos)
        for a, b, what in ((m, s, "mark"), (s, m, "spot")):
            fx, fz = -math.sin(math.radians(a[3])), math.cos(math.radians(a[3]))
            ux, uz = (b[0] - a[0]) / 8, (b[2] - a[2]) / 8
            if fx * ux + fz * uz < 0.99:
                out.append("%s: the %s's yaw %s does not face the other" % (v["id"], what, a[3]))
        if p[1] != m[1] or math.hypot(p[0] - m[0], p[2] - m[2]) > 3:
            out.append("%s: the post %s is not beside the mark" % (v["id"], p))
        # 13x13 clear floor with 8 of headroom, inside the border
        vx, vz = v["centre"]
        top = v["top"]
        for dx in range(-6, 7):
            for dz in range(-6, 7):
                if not solid(cv.get(vx + dx, top, vz + dz)):
                    out.append("%s: no ring floor at %s" % (v["id"], (vx + dx, top, vz + dz)))
                for y in range(top + 1, top + 9):
                    if cv.get(vx + dx, y, vz + dz) != AIR:
                        out.append("%s: %s over the ring at %s" % (v["id"], cv.get(vx + dx, y, vz + dz), (vx + dx, y, vz + dz)))
        seen += v["ranks"]
    if sorted(seen) != sorted(ranks):
        out.append("the venues carry ranks %s, data/arena_fights.json has %s" % (sorted(seen), sorted(ranks)))
    if len(spec["venues"]) < 4:
        out.append("only %d venues" % len(spec["venues"]))
    first = spec["venues"][0]
    if not {1, 2, 3} <= set(first["ranks"]):
        out.append("ranks 1-3 are not the first venue's")
    top9 = [v for v in spec["venues"] if max(ranks) in v["ranks"]]
    nearest = min(spec["venues"], key=lambda v: math.hypot(v["centre"][0] - cx, v["centre"][1] - cz))
    if not top9 or top9[0]["id"] != nearest["id"]:
        out.append("the streak rank is not the central venue's")
    e = spec["entrance"]
    door = e["door"]
    for y in (door[1], door[1] + 1):
        if cv.get(door[0], y, door[2]) != AIR:
            out.append("the door %s is not open at y%d" % (door, y))
    if not solid(cv.get(door[0], door[1] - 1, door[2])):
        out.append("the door %s has no floor" % (door,))
    return out


def shape_problems(spec, cv):
    out = []
    fp = footprint(spec)
    lim = spec["limits"]
    cols = {(x, z) for (x, _y, z) in cv.v}
    stray = cols - fp
    if stray:
        out.append("%d columns written outside the site and its tower, e.g. %s" % (len(stray), sorted(stray)[:3]))
    top = max(y for (_x, y, _z) in cv.v)
    if top > lim["crown_max"]:
        out.append("the crown reaches y%d, over y%d" % (top, lim["crown_max"]))
    if top <= lim["crown_must_clear"]:
        out.append("the crown (y%d) does not show above the lip (y%d)" % (top, lim["crown_must_clear"]))
    if min(y for (_x, y, _z) in cv.v) < spec["site"]["floor_y"]:
        out.append("something is written under the floor")
    for (x, y, z), (b, _ph) in cv.v.items():
        base = b.split("[")[0]
        if base in ("minecraft:light", "minecraft:water") or "iron" in base or "waterlogged=true" in b:
            out.append("%s at %s" % (b, (x, y, z)))
            break
    return out


def city_state(source_root):
    """The city's build in memory (nothing emitted, about 10 s) and the pit's ring model it stands on."""
    ccv, plan, _services, cspec = DC.build(source_root, None)
    return ccv, plan, DC.city_model(source_root, cspec)


def city_problems(spec, cv, source_root, city=None):
    """Run the city's build (nothing emitted) and the pit's model, and refuse what touches the city: a column the city
    writes anything but floor paving on, a column that is not the model's y0 floor, a keep-clear or reserved box, and
    anything nearer than limits.min_street to what the city builds or to a lot's door."""
    out = []
    ccv, plan, M = city or city_state(source_root)
    X0, Z0 = M["X0"], M["Z0"]
    NZ, NX = M["shape"]
    floor_y = spec["site"]["floor_y"]
    cols = {(x, z) for (x, _y, z) in cv.v}
    xs = [x for x, _ in cols]
    zs = [z for _, z in cols]
    pad = 30
    bx0, bx1, bz0, bz1 = min(xs) - pad, max(xs) + pad, min(zs) - pad, max(zs) + pad

    def floor_at(x, z):
        a, b = z - Z0, x - X0
        if not (0 <= a < NZ and 0 <= b < NX and M["mask"][a, b]):
            return None
        return int(M["T"][a, b])

    blocked = set()
    for (x, y, z), (_b, _ph) in ccv.v.items():
        if bx0 <= x <= bx1 and bz0 <= z <= bz1:
            if y > floor_y or ccv.owner.get((x, y, z)) not in PAVE:
                blocked.add((x, z))
    for x in range(bx0, bx1 + 1):
        for z in range(bz0, bz1 + 1):
            if floor_at(x, z) != floor_y:
                blocked.add((x, z))
    hit = cols & blocked
    if hit:
        out.append("%d written columns are not open y%d floor in the city's plan, e.g. %s"
                   % (len(hit), floor_y, sorted(hit)[:4]))
    boxes = list(plan["keep_clear"].items()) + [(r["id"], r["box"]) for r in plan["reserved"]]
    for name, bx in boxes:
        for (x, y, z) in cv.v:
            if bx[0] <= x <= bx[3] and bx[1] <= y <= bx[4] and bx[2] <= z <= bx[5]:
                out.append("a write at %s inside the city's keep-clear %s %s" % ((x, y, z), name, bx))
                break
    for _k, lo, up in M["lifts"]:
        for p in (lo, up):
            if (p[0], p[2]) in cols:
                out.append("a write on the lift at %s" % (p[:3],))
    # the street left round us: the edge of what we write to the nearest thing the city builds, and to every door
    edge = [(x, z) for x, z in cols if any((x + dx, z + dz) not in cols for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    near = min(((math.hypot(x - a, z - b), (x, z), (a, b)) for x, z in edge for a, b in blocked
                if abs(x - a) < 12 and abs(z - b) < 12), default=(99.0, None, None))
    doors = [(l_["id"], l_["door"]) for l_ in plan["lots"] if l_["door"]]
    dnear = min(((math.hypot(x - d[0], z - d[1]), lid, tuple(d)) for lid, d in doors for x, z in edge
                 if abs(x - d[0]) < 12 and abs(z - d[1]) < 12), default=(99.0, None, None))
    ms = spec["limits"]["min_street"]
    if near[0] < ms:
        out.append("the build comes %.1f from the city at %s (from %s), under min_street %s" % (near[0], near[2], near[1], ms))
    if dnear[0] < ms:
        out.append("the build comes %.1f from %s's door %s, under min_street %s" % (dnear[0], dnear[1], dnear[2], ms))
    outside = spec["entrance"]["outside"]
    if (outside[0], outside[2]) in blocked or (outside[0], outside[2]) in cols:
        out.append("the door's outside %s is not open floor the city leaves" % (outside,))
    stats = {"street": round(near[0], 1), "street_at": near[2], "door_street": round(dnear[0], 1), "door": dnear[1]}
    return out, stats


# ------------------------------------------------------------------ the undo of a superseded site (STAGING ONLY)

def superseded_spec(spec):
    """The spec as it was at the superseded site: every geometry key from `superseded_site`, the rest (limits,
    materials' names) from the current spec."""
    old = spec.get("superseded_site")
    if not old:
        raise DomeError("data/arena_dome.json has no superseded_site: there is nothing to undo")
    missing = [k for k in GEOMETRY_KEYS if k not in old]
    if missing:
        raise DomeError("superseded_site lacks %s: the old dome cannot be regenerated" % missing)
    s = dict(spec)
    for k in GEOMETRY_KEYS:
        s[k] = old[k]
    return s


def undo_box(old_cv):
    xs = [x for (x, _y, _z) in old_cv.v]
    ys = [y for (_x, y, _z) in old_cv.v]
    zs = [z for (_x, _y, z) in old_cv.v]
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


def undo_plan(spec, city):
    """-> (cells {(x, y, z): block}, first {(x, y, z)}, stats). Every cell the superseded dome wrote that the current
    dome does not, with what was there before it: the city's block, else the pit's tread light, else (above the floor)
    air. `first` are the cells cleared before the rest: the old lanterns, which would drop as items if what they stand
    on went first. Fails closed on a floor cell nothing accounts for, and on a city write above the floor in the old
    footprint (the undo would then have to know which of the two came last)."""
    import rift_deep as RD
    ccv, _plan, M = city
    olds = superseded_spec(spec)
    old, new = geometry(olds), geometry(spec)
    rd = M["rd"]["spec"]
    light = RD.pick(rd["light"]["block"], rd["light"]["fallback"], None)   # what prepare's build (no server dir) lays
    floor_y = olds["site"]["floor_y"]
    cols = {(x, z) for (x, _y, z) in old.v}
    over = sorted(c for c in ccv.v if c[1] > floor_y and (c[0], c[2]) in cols)
    if over:
        raise DomeError("the city writes %d cells above the floor in the old footprint, e.g. %s: not modelled"
                        % (len(over), over[:3]))
    cells, first = {}, set()
    st = {"old_cells": len(old.v), "kept_by_new": 0, "city": 0, "tread_light": 0, "air": 0}
    for c, (b, _ph) in old.v.items():
        if c in new.v:
            st["kept_by_new"] += 1
            continue
        if c in ccv.v:
            cells[c] = ccv.v[c][0]
            st["city"] += 1
        elif c in M["L1"]:
            cells[c] = light
            st["tread_light"] += 1
        elif c[1] > floor_y:
            cells[c] = AIR
            st["air"] += 1
        else:
            raise DomeError("the old dome's floor cell %s: neither the city nor the pit's tread lights say what was "
                            "there" % (c,))
        if b.startswith("minecraft:lantern"):
            first.add(c)
    st["box"] = undo_box(old)
    st["restored"] = len(cells)
    return cells, first, st


def undo_posts(spec):
    """[(x, y, z)] the superseded venues' posts, where tools/arena_runtime.py summoned them (the block's centre)."""
    old = superseded_spec(spec)
    now = [v["post"] for v in spec["venues"]]
    out = []
    for v in old["venues"]:
        px, py, pz = v["post"]
        p = (math.floor(px) + 0.5, py, math.floor(pz) + 0.5)
        if any(math.dist(p, (math.floor(q[0]) + 0.5, q[1], math.floor(q[2]) + 0.5)) < 1.0 for q in now):
            raise DomeError("the old post %s is within 1 of a current one: the undo, which kills within 0.5, would come too close to a live post" % (p,))
        out.append(p)
    return out


def undo_functions(spec, city):
    """-> ({name: lines}, order, stats). Each function holds the whole box force-loaded and never releases it; the
    last one kills the old posts and any dropped item in the box and then releases it, so by the time it runs the
    box's entities have had at least a tick to load."""
    cells, first, st = undo_plan(spec, city)
    x0, y0, z0, x1, y1, z1 = st["box"]
    hold = "forceload add %d %d %d %d" % (x0, z0, x1, z1)
    head = "# Generated by tools/arena_dome.py undo. STAGING ONLY: takes the superseded Heaven's Arena dome " \
           "(data/arena_dome.json superseded_site) off a world that has it; box x%d..%d y%d..%d z%d..%d" % (
               x0, x1, y0, y1, z0, z1)
    fns, order = {}, []
    for tag, part in (("a", {c: cells[c] for c in first}), ("b", {c: b for c, b in cells.items() if c not in first})):
        tiles = {}
        for (x, y, z), b in part.items():
            tiles.setdefault((x // TILE, z // TILE), {})[(x, y, z)] = b
        for t in sorted(tiles):
            body = DC._compress(tiles[t])
            for k in range(0, len(body), PART):
                name = "%s_%d_%d%s" % (tag, t[0], t[1], "" if k == 0 else "_%d" % (k // PART + 1))
                fns[name] = [head, hold] + body[k:k + PART]
                order.append(name)
    last = [head, hold]
    for px, py, pz in undo_posts(spec):
        last.append("kill @e[type=minecraft:interaction,tag=%s,x=%g,y=%g,z=%g,distance=..0.5]" % (POST_TAG, px, py, pz))
        last.append("kill @e[type=minecraft:text_display,tag=%s,x=%g,y=%g,z=%g,distance=..0.5]"
                    % (POST_TAG, px, py + 2.4, pz))
    last.append("kill @e[type=minecraft:item,x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d]" % (x0, y0, z0, x1 - x0, y1 - y0, z1 - z0))
    last.append("forceload remove %d %d %d %d" % (x0, z0, x1, z1))
    fns["z_entities_release"] = last
    order.append("z_entities_release")
    for name, lines in fns.items():
        probs = FL.check_lines(lines, name)
        if probs:
            raise DomeError("undo function %s would be refused: %s" % (name, probs[:3]))
    return fns, order, st


def write_undo(fns, order, out=UNDO_OUT):
    out = Path(out)
    if out.resolve().parent == (ROOT / "build" / "datapacks").resolve():
        raise DomeError("refusing to write the undo into build/datapacks: tools/reapply.py would demand a step for a "
                        "staging-only undo, and a fresh build's apply must never run it")
    if out.exists():
        shutil.rmtree(out)
    fn = out / "data" / "cobblers" / "function" / UNDO_FOLDER
    fn.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                                          "Cobblers: STAGING ONLY one-off removal of Heaven's Arena's "
                                                          "superseded site-A dome (tools/arena_dome.py undo)"}},
                                                indent=2) + "\n", encoding="utf-8")
    for name in order:
        (fn / (name + ".mcfunction")).write_text("\n".join(fns[name]) + "\n", encoding="utf-8", newline="\n")
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8", newline="\n")
    return fn


# ------------------------------------------------------------------ the pack

def emit(cv):
    if OUT.exists():
        shutil.rmtree(OUT)
    fn = OUT / "data" / "cobblers" / "function" / FOLDER
    fn.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                                          "Cobblers: Heaven's Arena, the dome on the Deep's north floor (tools/arena_dome.py)"}},
                                                indent=2) + "\n", encoding="utf-8")
    order, ncmd = [], 0
    for phase in (1, 2):
        tiles = {}
        for (x, y, z), (b, ph) in cv.v.items():
            if ph == phase:
                tiles.setdefault((x // TILE, z // TILE), {})[(x, y, z)] = b
        for t in sorted(tiles):
            body = DC._compress(tiles[t])
            for k in range(0, len(body), PART):
                name = "p%d_%d_%d%s" % (phase, t[0], t[1], "" if k == 0 else "_%d" % (k // PART + 1))
                out = FL.ensure_loaded(["# Generated by tools/arena_dome.py: phase %d, tile %d %d" % ((phase,) + t)]
                                       + body[k:k + PART])
                probs = FL.check_lines(out, name)
                if probs:
                    raise DomeError("function %s would be refused: %s" % (name, probs[:3]))
                (fn / (name + ".mcfunction")).write_text("\n".join(out) + "\n", encoding="utf-8")
                order.append(name)
                ncmd += len(body[k:k + PART])
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    return order, ncmd


def build(source_root):
    spec = load()
    cv = geometry(spec)
    probs = contract_problems(spec, cv) + shape_problems(spec, cv)
    cprobs, stats = city_problems(spec, cv, source_root)
    probs += cprobs
    if probs:
        for p in probs[:20]:
            print("PROBLEM: %s" % p)
        raise DomeError("%d problems; nothing emitted" % len(probs))
    order, ncmd = emit(cv)
    return cv, stats, order, ncmd


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "undo"))
    ap.add_argument("--source-root")
    ap.add_argument("--out", default=str(UNDO_OUT), help="undo only: where the staging-only pack goes")
    a = ap.parse_args(argv)
    src = a.source_root or env_source_root()
    if a.cmd == "undo":
        try:
            fns, order, st = undo_functions(load(), city_state(src))
            fn = write_undo(fns, order, a.out)
        except DomeError as e:
            print("arena_dome undo: REFUSED: %s" % e)
            return 1
        b = st["box"]
        print("  STAGING ONLY. box x%d..%d y%d..%d z%d..%d; old cells %d, left to the current dome %d, restored %d "
              "(city %d, tread lights %d, air %d)" % (b[0], b[3], b[1], b[4], b[2], b[5], st["old_cells"],
                                                      st["kept_by_new"], st["restored"], st["city"],
                                                      st["tread_light"], st["air"]))
        print("Heaven's Arena undo: %d functions in %s (run in index.txt order)" % (len(order), fn))
        return 0
    try:
        cv, stats, order, ncmd = build(src)
    except DomeError as e:
        print("arena_dome: REFUSED: %s" % e)
        return 1
    top = max(y for (_x, y, _z) in cv.v)
    print("  blocks written %d, crown y%d, street left %.1f (nearest %s), door street %.1f (%s)"
          % (len(cv.v), top, stats["street"], stats["street_at"], stats["door_street"], stats["door"]))
    print("Heaven's Arena dome: %d functions, %d commands" % (len(order), ncmd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
