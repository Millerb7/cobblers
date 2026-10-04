#!/usr/bin/env python
"""Audit the built Mega dens (cobblers_mega_dens) against data/mega_dens.json, data/gulch_mine.json and the ground.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/mega_dens.py's geometry.
It reads the records (data/mega_dens.json; the dens' anchors, the farms' grid, the gulch's block box and zone from
data/gulch_mine.json), the ground (tools/ground.py, the canonical heightmap, rounded), the spawn-condition contract
(data/spawn_blocks.json, data/spawn_block_policy.json), the footprints (data/towns.json, data/placements.json,
data/resident_encounters.json, data/route_paths.json, data/rift_zones.json, tools/water_mask.py) and the Rift skin's
palette (data/rift_skin.json), then REPLAYS the generated functions and checks the result. Only the re-application steps
are taken from the generator, as its OUTPUT, to check they hold the chunks they write.

  record     every open-air den in data/gulch_mine.json has exactly one record, keyed by the DEN's id (`den`), of the
             same species; a species may hold several dens (2026-10-04), so a lair, its function mega_dens/<den id>,
             its re-application step and every message are named by the den, never its species; its anchor is the
             gulch's; write_box holds the anchor, sits inside farms_grid and touches no other den's box; lighting is
             'dark'
  blocks     every written block is in blocks.ids; none is a spawn condition (data/spawn_blocks.json) unless a policy
             entry scoped to mega_dens allows it; no chest, no bed, no light source of any kind
  box        every written cell is inside its den's write_box
  anchor     the anchor is round(ground) + 1; after the build the anchor's ground block is solid and the cylinder of
             clear_radius by head_room over it is ALL air (written air, or natural air over the ground); within
             clear_radius nothing but air is written above the anchor's ground and nothing at all below it
  ground     below a column's own ground only the anchor pad's levelling block and a declared `dig` (within its radius
             of feature_at, no deeper than its depth under the ground there); above, never more than layout.max_rise
  support    nothing written above its ground floats: the cell under it is solid after the build; a gravity block always
             rests on something; a snow layer rests on a full block that is not ice; a path block has air over it
  visible    the scrape covers its disc (at least 70% of the columns within scrape_radius - scrape_ragged are rewritten at
             ground level), at least 80% of that ground is NOT the Rift skin's palette, the lair is 20 to 36 blocks
             across, and the sign stands at feature_at (or, for a dig, the ground there is opened to its floor)
  signature  each declared signature block is written at least its declared number of times
  footprint  no written column in a town's footprint, within 32 of a placement, within 4 of a resident anchor, in the
             gulch's block box or zone polygon, within 32 of a Rift zone wall or post, under painted water, or within
             128 of the critical path
  steps      every command is one the server accepts and this audit reads; the re-application runs each den's function
             inside a forceload of every column it writes and releases it after

  python tools/mega_dens_audit.py [--pack DIR] [--source-root R]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_mega_dens"
FUNCTIONS = "data/cobblers/function/mega_dens"
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*?)$")
FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$")
AIR = "minecraft:air"
# any block that gives light, by name: a lair is dark by design (data/mega_dens.json lighting)
LIGHT = re.compile(r"(lantern|torch|froglight|glowstone|glow_|shroomlight|candle|campfire|_lamp$|^minecraft:light$|"
                   r"end_rod|beacon|conduit|lava|(^|:|_)fire$|magma|crying_obsidian|sea_pickle|respawn_anchor|"
                   r"amethyst_cluster|_bud$|sculk_catalyst|brewing_stand|furnace|smoker|enchanting_table)")
GRAVITY = re.compile(r"(gravel|sand$|concrete_powder|anvil|scaffolding|pointed_dripstone|suspicious_)")
NOT_UNDER_SNOW = {"minecraft:ice", "minecraft:packed_ice", "minecraft:blue_ice", "minecraft:snow", AIR,
                  "minecraft:glass", "minecraft:iron_bars", "minecraft:chain", "minecraft:skeleton_skull"}
NOT_FULL = re.compile(r"(_stairs|_slab|anvil|skull|chain|iron_bars|^minecraft:snow$|glass_pane|_wall$|fence)")


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, check, msg):
        self.errors.append("%s: %s" % (check, msg))

    def note(self, msg):
        self.notes.append(msg)


def base(state):
    return state.split("[")[0].split("{")[0]


def load_json(name, root=DATA):
    return json.loads((root / name).read_text(encoding="utf-8"))


class Replay:
    """One den's function, run: final states, forceloads and lines this audit cannot read."""

    def __init__(self, lines):
        self.state, self.loads, self.bad = {}, [], []
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = FORCELOAD.match(line)
            if m:
                if m.group(1) == "add":
                    self.loads.append(tuple(int(v) for v in m.groups()[1:]))
                continue
            m = FILL.match(line)
            if m and not m.group(8):
                x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for y in range(min(y0, y1), max(y0, y1) + 1):
                        for z in range(min(z0, z1), max(z0, z1) + 1):
                            self.state[(x, y, z)] = m.group(7)
                continue
            m = SETBLOCK.match(line)
            if m:
                self.state[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = m.group(4)
                continue
            self.bad.append(line)


class World:
    """The replay over the natural ground: a cell not written is solid at or under round(ground), air over it."""

    def __init__(self, rep, g):
        self.rep, self.g, self._gc = rep, g, {}

    def ground(self, x, z):
        if (x, z) not in self._gc:
            self._gc[(x, z)] = int(round(self.g(x, z)))
        return self._gc[(x, z)]

    def at(self, x, y, z):
        if (x, y, z) in self.rep.state:
            return self.rep.state[(x, y, z)]
        return None if y <= self.ground(x, z) else AIR      # None: natural ground, solid

    def solid(self, x, y, z):
        s = self.at(x, y, z)
        return s is None or s != AIR


def _in_poly(x, z, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi:
            inside = not inside
        j = i
    return inside


def gulch_dens(gm):
    return {d["id"]: (f, d) for f in gm["farms"] for d in f["dens"]}


# --------------------------------------------------------------------------------------------- the checks
def check_record(rec, gm, R):
    dens = gulch_dens(gm)
    mine = {d["den"]: d for d in rec["dens"]}
    # two records for one den would build one file (mega_dens/<den id>) twice, the second over the first
    counts = {}
    for d in rec["dens"]:
        counts[d["den"]] = counts.get(d["den"], 0) + 1
    for did in sorted(k for k, n in counts.items() if n > 1):
        R.err("record", "%s has %d dressing records: one lair per den" % (did, counts[did]))
    if rec.get("lighting") != "dark":
        R.err("record", "lighting must be 'dark': these are wild lairs")
    for did, (_f, d) in sorted(dens.items()):
        if did not in mine:
            R.err("record", "the gulch's den %s (%s) has no dressing record" % (did, d["species"]))
        elif mine[did]["species"] != d["species"]:
            R.err("record", "%s is a %s in the gulch and a %s here" % (did, d["species"], mine[did]["species"]))
    for did in sorted(set(mine) - set(dens)):
        R.err("record", "%s is not a den in data/gulch_mine.json" % did)
    fg = gm["farms_grid"]
    boxes = []
    for d in rec["dens"]:
        b = d["write_box"]
        if did_anchor(d, dens) is None:
            continue
        ax, ay, az = did_anchor(d, dens)
        if not (b[0] <= ax <= b[3] and b[1] <= ay <= b[4] and b[2] <= az <= b[5]):
            R.err("record", "%s: write_box %s does not hold the anchor" % (d["den"], b))
        if not (fg["x"][0] <= b[0] and b[3] <= fg["x"][1] and fg["y"][0] <= b[1] and b[4] <= fg["y"][1]
                and fg["z"][0] <= b[2] and b[5] <= fg["z"][1]):
            R.err("record", "%s: write_box %s is not inside data/gulch_mine.json farms_grid" % (d["den"], b))
        for other, ob in boxes:
            if b[0] <= ob[3] and ob[0] <= b[3] and b[2] <= ob[5] and ob[2] <= b[5]:
                R.err("record", "%s's write_box overlaps %s's" % (d["den"], other))
        boxes.append((d["den"], b))


def did_anchor(d, dens):
    return tuple(dens[d["den"]][1]["anchor"]) if d["den"] in dens else None


def check_blocks(rep, d, rec, R):
    allowed = set(rec["blocks"]["ids"])
    spawn = set(load_json("spawn_blocks.json")["blocks"])
    policy = load_json("spawn_block_policy.json")
    white = {bk for w in policy.get("whitelist") or [] if "mega_dens" in (w.get("scope") or "") for bk in w["blocks"]}
    seen = {base(s) for s in rep.state.values()}
    sp = d["den"]
    for bk in sorted(seen - allowed):
        R.err("blocks", "%s writes %s, which is not in data/mega_dens.json blocks.ids" % (sp, bk))
    for bk in sorted((seen & spawn) - white):
        R.err("blocks", "%s writes %s, a spawn condition (data/spawn_blocks.json) no policy entry scoped to mega_dens "
                        "allows" % (sp, bk))
    for bk in sorted(seen):
        if "chest" in bk or bk.endswith("_bed"):
            R.err("blocks", "%s writes %s: no chests and no beds" % (sp, bk))
        if LIGHT.search(bk):
            R.err("blocks", "%s writes %s, a light source: the dens are dark by design" % (sp, bk))
    for s in rep.state.values():
        if "lit=true" in s:
            R.err("blocks", "%s writes a lit block %s" % (sp, s))
            break


def check_box(rep, d, R):
    b = d["write_box"]
    out = [k for k in rep.state if not (b[0] <= k[0] <= b[3] and b[1] <= k[1] <= b[4] and b[2] <= k[2] <= b[5])]
    if out:
        R.err("box", "%s writes %d cell(s) outside its write_box %s, e.g. %s" % (d["den"], len(out), b, out[0]))


def check_anchor(rep, W, d, anchor, rec, R):
    sp = d["den"]
    ax, ay, az = anchor
    if ay != W.ground(ax, az) + 1:
        R.err("anchor", "%s: the anchor y%d is not its ground + 1 (ground y%d)" % (sp, ay, W.ground(ax, az)))
    G0 = ay - 1
    pad = rec["anchor_pad"]
    cr, hr = pad["clear_radius"], pad["head_room"]
    if not W.solid(ax, G0, az):
        R.err("anchor", "%s: nothing to stand on at the anchor (%d, %d, %d)" % (sp, ax, G0, az))
    blocked = []
    for x in range(ax - cr, ax + cr + 1):
        for z in range(az - cr, az + cr + 1):
            if math.hypot(x - ax, z - az) > cr:
                continue
            for y in range(ay, ay + hr):
                if W.at(x, y, z) != AIR:
                    blocked.append((x, y, z, W.at(x, y, z) or "natural ground"))
    if blocked:
        R.err("anchor", "%s: %d cell(s) of the spawn cylinder (radius %d, %d high) are not air, e.g. %s"
              % (sp, len(blocked), cr, hr, blocked[0]))
    near = [(k, s) for k, s in rep.state.items() if math.hypot(k[0] - ax, k[2] - az) <= cr
            and (k[1] < G0 or (k[1] > G0 and s != AIR))]
    if near:
        R.err("anchor", "%s: %d block(s) written within %d of the anchor off its ground level, e.g. %s"
              % (sp, len(near), cr, near[0]))


def check_ground(rep, W, d, anchor, rec, R):
    sp = d["den"]
    ax, ay, az = anchor
    G0 = ay - 1
    cr = rec["anchor_pad"]["clear_radius"]
    dig = d.get("dig")
    fx, fz = d["feature_at"]
    floor = W.ground(fx, fz) - dig["depth"] if dig else None
    bad_low, bad_high = [], []
    for (x, y, z), s in rep.state.items():
        gr = W.ground(x, z)
        if y < gr:
            if math.hypot(x - ax, z - az) <= cr and y == G0:
                continue
            if dig and math.hypot(x - fx, z - fz) <= dig["radius"] and y >= floor:
                continue
            bad_low.append((x, y, z, s))
        elif s != AIR and y - gr > rec["layout"]["max_rise"]:
            bad_high.append((x, y, z, s))
    if bad_low:
        R.err("ground", "%s: %d cell(s) written below their ground outside the pad and any declared dig, e.g. %s"
              % (sp, len(bad_low), bad_low[0]))
    if bad_high:
        R.err("ground", "%s: %d block(s) stand more than max_rise %d over their ground, e.g. %s"
              % (sp, len(bad_high), rec["layout"]["max_rise"], bad_high[0]))


def check_support(rep, W, d, R):
    sp = d["den"]
    floating, falling, snow, path = [], [], [], []
    for (x, y, z), s in rep.state.items():
        if s == AIR:
            continue
        below = W.at(x, y - 1, z)
        below_solid = below is None or below != AIR
        if y > W.ground(x, z) and not below_solid:
            floating.append((x, y, z, s))
        if GRAVITY.search(base(s)) and not below_solid:
            falling.append((x, y, z, s))
        if base(s) == "minecraft:snow" and (below is not None and (base(below) in NOT_UNDER_SNOW
                                                                   or NOT_FULL.search(base(below)))):
            snow.append((x, y, z, below))
        if base(s) == "minecraft:dirt_path" and W.at(x, y + 1, z) != AIR:
            path.append((x, y, z, W.at(x, y + 1, z) or "natural ground"))
    for name, got, what in (("floating", floating, "stand on air"), ("falling", falling, "gravity block(s) over air"),
                            ("snow", snow, "snow layer(s) on a block that will not hold one"),
                            ("path", path, "path block(s) with something over them (they turn to dirt)")):
        if got:
            R.err("support", "%s: %d %s, e.g. %s" % (sp, len(got), what, got[0]))


def check_visible(rep, W, d, anchor, rec, R):
    sp = d["den"]
    ax, _ay, az = anchor
    L = rec["layout"]
    inner = L["scrape_radius"] - L["scrape_ragged"]
    skin = load_json("rift_skin.json")["palette"]
    skin_blocks = {base(b) for k in ("rock", "rock_fallbacks") for b in skin.get(k) or []}
    disc = [(x, z) for x in range(ax - inner, ax + inner + 1) for z in range(az - inner, az + inner + 1)
            if math.hypot(x - ax, z - az) <= inner]
    surf = {}
    for (x, y, z), s in rep.state.items():
        if s != AIR and y <= W.ground(x, z) and (x, z) in surf:
            surf[(x, z)] = max(surf[(x, z)], (y, s))
        elif s != AIR and y <= W.ground(x, z):
            surf[(x, z)] = (y, s)
    covered = [c for c in disc if c in surf]
    if len(covered) < 0.7 * len(disc):
        R.err("visible", "%s: the scrape rewrites %d of the %d columns within %d of the anchor (under 70%%)"
              % (sp, len(covered), len(disc), inner))
    skinned = [c for c in covered if base(surf[c][1]) in skin_blocks]
    if covered and len(skinned) > 0.2 * len(covered):
        R.err("visible", "%s: %d of the scrape's %d ground blocks are the Rift skin's own palette: it would not read "
                         "from the air" % (sp, len(skinned), len(covered)))
    reach = L["ring_radius"][1] + 3
    cols = {(x, z) for (x, _y, z), s in rep.state.items() if s != AIR and math.hypot(x - ax, z - az) <= reach}
    if cols:
        span = max(max(c[0] for c in cols) - min(c[0] for c in cols), max(c[1] for c in cols) - min(c[1] for c in cols))
        if not 20 <= span + 1 <= 36:
            R.err("visible", "%s: the lair is %d blocks across, not 20 to 36" % (sp, span + 1))
    fx, fz = d["feature_at"]
    if math.hypot(fx - ax, fz - az) <= rec["anchor_pad"]["clear_radius"] + 1:
        R.err("visible", "%s: feature_at is on the anchor's pad" % sp)
    if d.get("dig"):
        gf = W.ground(fx, fz)
        if W.at(fx, gf, fz) != AIR or not W.solid(fx, gf - d["dig"]["depth"], fz):
            R.err("visible", "%s: the ground at feature_at is not opened %d deep to a floor" % (sp, d["dig"]["depth"]))
    else:
        tall = [k for k, s in rep.state.items() if s != AIR and math.hypot(k[0] - fx, k[2] - fz) <= 4
                and k[1] > W.ground(k[0], k[2])]
        # or, laid flat, a ground the scrape round it is not made of (a strike fused to obsidian)
        plain = set(d.get("scrape") or {}) | {base(d.get("pad", "")), *(d.get("path") or {})}
        flat = [k for k, s in rep.state.items() if s != AIR and math.hypot(k[0] - fx, k[2] - fz) <= 2
                and base(s) not in plain]
        if len(tall) < 5 and len(flat) < 5:
            R.err("visible", "%s: nothing marks feature_at (%d, %d): %d block(s) stand within 4 of it"
                  % (sp, fx, fz, len(tall)))
    if d.get("feature") == "burrow":
        steps = [k for k, s in rep.state.items() if base(s).endswith("_stairs") and math.hypot(k[0] - fx, k[2] - fz) <= 1.5]
        if not steps:
            R.err("visible", "%s: the burrow has no step out of it" % sp)


def check_signature(rep, d, R):
    counts = {}
    for s in rep.state.values():
        counts[base(s)] = counts.get(base(s), 0) + 1
    for bk, n in sorted(d.get("signature", {}).items()):
        if counts.get(bk, 0) < n:
            R.err("signature", "%s writes %s %d time(s), under the %d its sign declares"
                  % (d["den"], bk, counts.get(bk, 0), n))


def check_footprint(cols, d, gm, W, R):
    sp = d["den"]
    if not cols:
        return
    for t in load_json("towns.json")["towns"]:
        fp = t.get("footprint") or {}
        if all(k in fp for k in ("min_x", "min_z", "max_x", "max_z")):
            inside = [c for c in cols if fp["min_x"] <= c[0] <= fp["max_x"] and fp["min_z"] <= c[1] <= fp["max_z"]]
            if inside:
                R.err("footprint", "%s writes inside %s's footprint, e.g. %s" % (sp, t["id"], inside[0]))
    xs, zs = [c[0] for c in cols], [c[1] for c in cols]
    box = (min(xs), min(zs), max(xs), max(zs))

    def near(px, pz, reach):
        if not (box[0] - reach <= px <= box[2] + reach and box[1] - reach <= pz <= box[3] + reach):
            return None
        dmin = min(math.hypot(px - c[0], pz - c[1]) for c in cols)
        return dmin if dmin < reach else None

    for p in load_json("placements.json")["placements"]:
        pos = p.get("position")
        if isinstance(pos, dict) and near(pos["x"], pos["z"], 32) is not None:
            R.err("footprint", "%s writes within 32 of placement %s" % (sp, p["id"]))
    for r in load_json("resident_encounters.json").get("encounters") or []:
        loc = r.get("location") or {}
        if "x" in loc and "z" in loc and near(loc["x"], loc["z"], 4.01) is not None:
            R.err("footprint", "%s writes within 4 of resident %s's anchor" % (sp, r["id"]))
    gg = gm["grid"]
    ing = [c for c in cols if gg["x"][0] <= c[0] <= gg["x"][1] and gg["z"][0] <= c[1] <= gg["z"][1]]
    if ing:
        R.err("footprint", "%s writes inside the gulch's block box (gulch_mine.json grid), e.g. %s" % (sp, ing[0]))
    poly = gm["zone"]["polygon"]
    inz = [c for c in cols if _in_poly(c[0] + 0.5, c[1] + 0.5, poly)]
    if inz:
        R.err("footprint", "%s writes inside the gulch's zone polygon, e.g. %s" % (sp, inz[0]))
    rz = load_json("rift_zones.json")
    built = []
    for cut in rz.get("cuts") or []:
        built += [(c[0], c[1], "wall " + cut["id"]) for c in cut.get("line") or []]
    for zid, zz in rz["zones"].items():
        for post in zz.get("posts") or []:
            if isinstance(post.get("at"), list):
                built.append((post["at"][0], post["at"][1], "post %s" % post.get("id")))
    for px, pz, what in built:
        if near(px, pz, 32) is not None:
            R.err("footprint", "%s writes within 32 of the Rift zones' %s" % (sp, what))
            break
    import water_mask
    bodies, sea = water_mask.bodies(), water_mask.sea_level()
    wet = [c for c in sorted(cols) if water_mask.level_at(c[0], c[1], W.ground, bodies, sea)[0] is not None]
    if wet:
        R.err("footprint", "%s: %d written column(s) under painted water, e.g. %s" % (sp, len(wet), wet[0]))
    route = [c for path in load_json("route_paths.json")["paths"].values() for c in path]
    dmin = min(math.hypot(rx - c[0], rz_ - c[1]) for c in sorted(cols)[::5] for rx, rz_ in route[::3])
    if dmin < 128:
        R.err("footprint", "%s writes %.0f blocks from the critical path (data/route_paths.json): under 128" % (sp, dmin))
    return dmin


def check_steps(reps, lines_by, rec, steps, R):
    import function_limits
    for sp, lines in sorted(lines_by.items()):
        bad = function_limits.check_lines(lines, sp)
        if bad:
            R.err("steps", "%s: %d command(s) the server would refuse: %s" % (sp, len(bad), bad[:2]))
        if reps[sp].bad:
            R.err("steps", "%s: %d line(s) this audit cannot read: %s" % (sp, len(reps[sp].bad), reps[sp].bad[:2]))
    if steps is None:
        return
    steps = [tuple(s) for s in steps]
    named = {d["den"] for d in rec["dens"]}
    for s in steps:
        if s[0] == "fn" and s[1].startswith("cobblers:mega_dens/") and s[1].rsplit("/", 1)[-1] not in named:
            R.err("steps", "the re-application runs %s, which is no den's lair" % s[1])
    for d in rec["dens"]:
        sp = d["den"]
        fn = ("fn", "cobblers:mega_dens/%s" % sp)
        if fn not in steps:
            R.err("steps", "the re-application does not run cobblers:mega_dens/%s" % sp)
            continue
        i = steps.index(fn)
        holds = []
        for s in steps[:i]:
            if s[0] == "cmd" and s[1].startswith("forceload add"):
                holds.append(tuple(int(v) for v in s[1].split()[2:]))
            if s[0] == "cmd" and s[1].startswith("forceload remove"):
                rem = tuple(int(v) for v in s[1].split()[2:])
                holds = [h for h in holds if h != rem]
        if not any(s[0] == "cmd" and s[1].startswith("forceload remove") for s in steps[i + 1:]):
            R.err("steps", "%s: the re-application never releases the chunks it held" % sp)
        if sp not in reps:
            continue
        for (x, _y, z) in reps[sp].state:
            if not any(min(h[0], h[2]) <= x <= max(h[0], h[2]) and min(h[1], h[3]) <= z <= max(h[1], h[3]) for h in holds):
                R.err("steps", "%s: (%d, %d) is written outside the re-application's forceload" % (sp, x, z))
                break


def audit(rec, g, pack, steps=None, gm=None):
    R = Report()
    gm = gm or load_json("gulch_mine.json")
    pack = Path(pack)
    check_record(rec, gm, R)
    dens = gulch_dens(gm)
    reps, lines_by = {}, {}
    for d in rec["dens"]:
        sp = d["den"]
        fn = pack / FUNCTIONS / ("%s.mcfunction" % sp)
        if not fn.exists():
            R.err("steps", "no %s in %s: build the pack first" % (fn.name, pack))
            continue
        lines = fn.read_text(encoding="utf-8").splitlines()
        rep = Replay(lines)
        reps[sp], lines_by[sp] = rep, lines
        anchor = did_anchor(d, dens)
        if anchor is None:
            continue
        W = World(rep, g)
        check_blocks(rep, d, rec, R)
        check_box(rep, d, R)
        check_anchor(rep, W, d, anchor, rec, R)
        check_ground(rep, W, d, anchor, rec, R)
        check_support(rep, W, d, R)
        check_visible(rep, W, d, anchor, rec, R)
        check_signature(rep, d, R)
        cols = {(x, z) for (x, _y, z) in rep.state}
        dmin = check_footprint(cols, d, gm, W, R)
        R.note("%s: %d cells written over %d columns; nearest critical path ~%.0f" % (sp, len(rep.state), len(cols),
                                                                                       dmin or -1))
    check_steps(reps, lines_by, rec, steps, R)
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rec = load_json("mega_dens.json")
    g = G.load(a.source_root)
    steps = None
    try:
        import mega_dens  # the re-application steps are the generator's OUTPUT, checked here, never its geometry
        steps = mega_dens.placement_steps(g=g)
    except ImportError:
        pass
    R = audit(rec, g, a.pack, steps)
    for n in R.notes:
        print("note: %s" % n)
    for e in R.errors:
        print("PROBLEM %s" % e)
    print("mega_dens_audit: %s (%d problem(s))" % ("clean" if not R.errors else "FAILED", len(R.errors)))
    return 1 if R.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
