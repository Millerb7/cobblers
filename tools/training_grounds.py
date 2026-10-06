#!/usr/bin/env python
"""The levelling catch-up: one training ground per gym town (data/training_grounds.json, docs/mechanics/LEVEL_CATCHUP.md).

A training ground is one ACTIVATED Habitat Block that keeps a few high-EXP-yield wild Pokemon alive round itself, at
levels just under the cap a player holds on reaching that town. Battle EXP is clamped at the cap by rctmod (its
EXPERIENCE_GAINED_EVENT_PRE handler, allowOverLeveling = false), so the ground fills a team to the cap and no further.

  site       choose each ground's site from the canonical heightmap (tools/ground.py) and a sweep of every coordinate
             in data/*.json; --write records it in data/training_grounds.json
  records    the shared records this tool owns: one block in data/habitat_blocks.json and one Habitat pool (habitat +
             entries) in data/spawns.json per ground; --write upserts them, without it the files are compared and any
             drift fails
  build      the sign pack: build/datapacks/cobblers_training_grounds, function cobblers:training_grounds/build
  estimate   the time-to-cap estimate (docs/mechanics/LEVEL_CATCHUP.md section 4)

  python tools/training_grounds.py site [--write]
  python tools/training_grounds.py records [--write]
  python tools/training_grounds.py build [--out DIR]
  python tools/training_grounds.py estimate

The block itself is placed with every other Habitat Block by tools/habitat_blocks.py (reapply R9E); the pool is
compiled by tools/compile_spawns.py. This tool places nothing in a world and never reads one.

What it does NOT cover: the ground's Pokemon are clamped by rctmod's handler only. Any EXP source that runs after it
(cobblecuisine's EXP-boost food, at NORMAL priority after rctmod's HIGHEST) or that sets a level directly (cobblecuisine's
Fancy Shake) is outside it: docs/mechanics/LEVEL_CATCHUP.md section 2.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "training_grounds.json"
HABITATS = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
TOWNS = ROOT / "data" / "towns.json"
PATHS = ROOT / "data" / "route_paths.json"
PAINT = ROOT / "build" / "paint"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_training_grounds"
NS, FN = "cobblers", "training_grounds"
PACK_FORMAT = 48
GRASS = 1           # build/paint/manifest.json terrain_codes: "1": "GRASS"

# The ground rule (tools/ground_rule.py): nothing here reads a world.
WORLD_READS = set()

# Cobblemon 1.8.0, read from the jar (docs/mechanics/LEVEL_CATCHUP.md section 3): species data baseExperienceYield,
# config/cobblemon/main.json experienceMultiplier 2.0, StandardExperienceCalculator (javap), experience groups.
BASE_EXP = {"audino": 390, "chansey": 395, "blissey": 635}
EXP_MULTIPLIER = 2.0


class SiteError(Exception):
    pass


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def caps():
    """{gym number: the cap a player holds before that gym}, the way rctmod computes it (tools/legendaries_audit.py)."""
    import legendaries_audit as L
    c = L.rct_caps()
    return {n: c[None] if n == 1 else c["gym%d_cleared" % (n - 1)] for n in range(1, 9)}


def roster(doc, gym):
    return doc["rosters"]["tiers_6_to_8" if gym >= 6 else "tiers_1_to_5"]


def band(doc, cap):
    lo, hi = doc["levels"]["below_cap"]
    return cap - lo, cap - hi


# ------------------------------------------------------------------------------------------------------------ siting
def swept_points(exclude_files=("training_grounds.json",), exclude_prefix="training_ground_"):
    """[(x, z, where)] for every coordinate any data/*.json carries: a dict with numeric x and z, or a two- or
    three-number list under a key that names a place (centre, site, at, position, anchor, location, origin)."""
    keys = {"centre", "center", "site", "at", "position", "anchor", "location", "origin", "pos"}
    out = []

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def walk(o, f, key):
        if isinstance(o, dict):
            if str(o.get("id", "")).startswith(exclude_prefix):
                return
            if num(o.get("x")) and num(o.get("z")):
                out.append((float(o["x"]), float(o["z"]), "%s:%s" % (f, key)))
            for k, v in o.items():
                if k in keys and isinstance(v, list) and len(v) in (2, 3) and all(num(a) for a in v):
                    x, z = (v[0], v[1]) if len(v) == 2 else (v[0], v[2])
                    if 0 <= x <= 8192 and 0 <= z <= 8192:
                        out.append((float(x), float(z), "%s:%s" % (f, k)))
                else:
                    walk(v, f, k)
        elif isinstance(o, list):
            for v in o:
                walk(v, f, key)

    for p in sorted((ROOT / "data").glob("*.json")):
        if p.name in exclude_files:
            continue
        try:
            walk(json.loads(p.read_text(encoding="utf-8")), p.name, "")
        except ValueError:
            continue
    return out


def path_points():
    return np.array([p for pl in json.loads(PATHS.read_text(encoding="utf-8"))["paths"].values() for p in pl], float)


def water_map(g, sea):
    """A whole-map (z, x) bool array: at or under the sea, or inside a painted lake or river (the masks
    tools/themed_saplings.py water_masks reads)."""
    from PIL import Image
    wet = np.round(g.heights) <= sea
    man = json.loads((PAINT / "manifest.json").read_text(encoding="utf-8"))
    for w in man["water"]:
        key = "levels" if "levels" in w else "mask"
        m = np.asarray(Image.open(PAINT / w[key])) > 0
        wx, wz = w["x"] - g.ox, w["z"] - g.oz
        wet[wz:wz + m.shape[0], wx:wx + m.shape[1]] |= m
    return wet


def footprints():
    """[(x0, z0, x1, z1, placement id)] for every building data/placements.json seats, as its placer seats it
    (tools/markets_audit.py building_footprints, tools/place_donor.py footprint; sizes read from the templates). Fails
    closed when a size cannot be read: an unknown footprint would be a building the ground could sit in."""
    import markets_audit as M
    import town_character as TC
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    templates = TC.Templates(TC.default_pack_dir(), TC.default_vanilla_jar())
    out, unknown = [], []
    for settlement in sorted({q.get("settlement") for q in placements["placements"] if q.get("settlement")}):
        fp, unk = M.building_footprints(settlement, placements, templates)
        out += [tuple(v) + (k,) for k, v in sorted(fp.items())]
        unknown += unk
        # and the town plan's lots and lamps (the independent audit, 2026-10-06: gym 8's first site stood 26-31 blocks
        # from Holdfast's lamps and a lot, under building_clear_blocks): a town's furniture is part of the town
        pp = ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)
        if pp.is_file():
            plan = json.loads(pp.read_text(encoding="utf-8"))
            for lot in plan.get("lots") or []:
                x0, z0, x1, z1 = lot["rect"]
                out.append((min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1), "%s lot %s" % (settlement, lot.get("id"))))
            for lamp in plan.get("lamps") or []:
                x, z = lamp["at"][0], lamp["at"][-1]
                out.append((x, z, x, z, "%s lamp" % settlement))
    if unknown:
        raise SiteError("building sizes could not be read for %s (kits hydrated? the COBBLEVERSE pack and the vanilla jar "
                        "present?)" % unknown[:5])
    return out


class Site:
    """Everything the siting needs, loaded once."""

    def __init__(self, doc, g=None):
        import ground as G
        import terrain as T
        from PIL import Image
        self.doc, self.g = doc, g or G.load()
        self.sea = T.sea_level(self.g.world)
        self.terrain = np.asarray(Image.open(PAINT / "terrain.png"))
        can = np.load(PAINT / "canopy.npz")
        self.canopy, self.canopy_grid = can["canopy"], int(can["grid_blocks"])
        self.paths = path_points()
        self.points = swept_points()
        self.pts = np.array([(px, pz) for px, pz, _w in self.points], float)
        self.wet = water_map(self.g, self.sea)
        hb = json.loads(HABITATS.read_text(encoding="utf-8"))["blocks"]
        self.nests = [b for b in hb if not str(b.get("id", "")).startswith("training_ground_")]
        self.towns = {t["id"]: t for t in json.loads(TOWNS.read_text(encoding="utf-8"))["towns"]}
        self.footprints = footprints()

    def measure(self, x, z, town, paths=None):
        """(problems, facts) for a block at column (x, z) serving `town`."""
        r = self.doc["rules"]
        act = self.doc["block"]["activated"]
        sr = act["spawn_range"]
        tx, tz = self.towns[town]["centre"]["x"], self.towns[town]["centre"]["z"]
        bad, f = [], {}
        f["town_distance"] = round(math.hypot(x - tx, z - tz), 1)
        lo, hi = r["ring_blocks"]
        if not lo <= f["town_distance"] <= hi:
            bad.append("%.0f blocks from the town centre, outside %d-%d" % (f["town_distance"], lo, hi))
        P = self.paths if paths is None else paths
        f["path_clearance"] = round(float(np.min(np.hypot(P[:, 0] - x, P[:, 1] - z))), 1)
        if f["path_clearance"] < r["path_clear_blocks"]:
            bad.append("%.0f blocks from a route path, under %d" % (f["path_clearance"], r["path_clear_blocks"]))
        dist = np.hypot(self.pts[:, 0] - x, self.pts[:, 1] - z)
        dist[(np.abs(self.pts[:, 0] - tx) < 0.5) & (np.abs(self.pts[:, 1] - tz) < 0.5)] = np.inf
        i = int(np.argmin(dist))
        d, w = float(dist[i]), self.points[i][2]
        f["feature_clearance"] = round(d, 1)
        f["nearest_feature"] = w
        if d < r["feature_clear_blocks"]:
            bad.append("%.0f blocks from a data coordinate (%s), under %d" % (d, w, r["feature_clear_blocks"]))
        for b in self.nests:
            dd = math.hypot(b["position"]["x"] - x, b["position"]["z"] - z)
            need = (b["activated"]["spawn_range"] + sr + r["nest_margin_blocks"] if b.get("style") == "activated"
                    else b.get("range_of_influence", 0) + sr)
            if dd < need:
                bad.append("%.0f blocks from Habitat Block %s, needs %d" % (dd, b["id"], need))
        fb = [(max(x0 - x, 0, x - x1) ** 2 + max(z0 - z, 0, z - z1) ** 2) ** 0.5 for x0, z0, x1, z1, _i in self.footprints]
        if fb:
            i = int(np.argmin(fb))
            f["building_clearance"] = round(fb[i], 1)
            f["nearest_building"] = self.footprints[i][4]
            if fb[i] < r["building_clear_blocks"]:
                bad.append("%.0f blocks from %s's footprint, under %d" % (fb[i], self.footprints[i][4], r["building_clear_blocks"]))
        rr = r["flat_radius_blocks"]
        box = self.g.box(x - rr, z - rr, x + rr, z + rr)
        yy, xx = np.mgrid[-rr:rr + 1, -rr:rr + 1]
        disk = xx * xx + yy * yy <= rr * rr
        f["relief"] = int(box[disk].max() - box[disk].min())
        if f["relief"] > r["max_relief_blocks"]:
            bad.append("relief %d within %d blocks, over %d" % (f["relief"], rr, r["max_relief_blocks"]))
        wr = sr + r["water_margin_blocks"]
        wet = self.wet[z - wr - self.g.oz:z + wr + 1 - self.g.oz, x - wr - self.g.ox:x + wr + 1 - self.g.ox]
        yy, xx = np.mgrid[-wr:wr + 1, -wr:wr + 1]
        f["wet_columns"] = int(wet[xx * xx + yy * yy <= wr * wr].sum())
        if f["wet_columns"]:
            bad.append("%d wet columns within %d blocks" % (f["wet_columns"], wr))
        f["terrain"] = int(self.terrain[z, x])
        if f["terrain"] != GRASS:
            bad.append("terrain code %d at the block, not GRASS" % f["terrain"])
        f["canopy"] = round(float(self.canopy[z // self.canopy_grid, x // self.canopy_grid]), 3)
        f["y"] = self.g(x, z)
        return bad, f

    def score(self, f):
        return f["town_distance"] + 8 * f["relief"] + 40 * f["canopy"]

    def choose(self, ground):
        r = self.doc["rules"]
        t = self.towns[ground["town"]]["centre"]
        tx, tz = int(t["x"]), int(t["z"])
        lo, hi = r["ring_blocks"]
        step = r["grid_blocks"]
        best = None
        # the paths within reach of the ring: exact for every candidate's test against path_clear_blocks; the winner
        # is measured again against every path below
        near = np.hypot(self.paths[:, 0] - tx, self.paths[:, 1] - tz) <= hi + 2 * r["path_clear_blocks"]
        local = self.paths[near] if near.any() else self.paths[:1]
        for dz in range(-hi, hi + 1, step):
            for dx in range(-hi, hi + 1, step):
                if not lo * lo <= dx * dx + dz * dz <= hi * hi:
                    continue
                x, z = tx + dx, tz + dz
                # cheap rejections first: the path and the sweep, then the terrain
                if float(np.min(np.hypot(local[:, 0] - x, local[:, 1] - z))) < r["path_clear_blocks"]:
                    continue
                if int(self.terrain[z, x]) != GRASS:
                    continue
                bad, f = self.measure(x, z, ground["town"], local)
                if bad:
                    continue
                key = (self.score(f), x, z)
                if best is None or key < best[0]:
                    best = (key, x, z, f)
        if best is None:
            raise SiteError("%s: no column within %d-%d blocks of %s passes the rules" % (ground["id"], lo, hi, ground["town"]))
        _key, x, z, _f = best
        bad, f = self.measure(x, z, ground["town"])
        if bad:
            raise SiteError("%s: the chosen column fails on the full path set: %s" % (ground["id"], bad))
        return dict({"x": x, "z": z}, **f)


def site_all(doc, g=None):
    s = Site(doc, g)
    out = {}
    for gr in doc["grounds"]:
        out[gr["id"]] = s.choose(gr)
    # two grounds must not share a nest (the towns are 600+ apart, so this only guards a future change)
    ids = list(out)
    sr = doc["block"]["activated"]["spawn_range"]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = math.hypot(out[a]["x"] - out[b]["x"], out[a]["z"] - out[b]["z"])
            if d < 2 * sr + doc["rules"]["nest_margin_blocks"]:
                raise SiteError("%s and %s are %.0f blocks apart" % (a, b, d))
    return out


# ----------------------------------------------------------------------------------------------------------- records
def records(doc, capmap=None):
    """(habitat block records, [(habitat record, entries)]) this tool owns in the shared files."""
    capmap = capmap or caps()
    rar = json.loads(SPAWNS.read_text(encoding="utf-8"))["rarity"]
    act = doc["block"]["activated"]
    blocks, pools = [], []
    for gr in doc["grounds"]:
        s = gr.get("site")
        if not s:
            raise SiteError("%s has no site: run tools/training_grounds.py site --write" % gr["id"])
        cap = capmap[gr["gym"]]
        lo, hi = band(doc, cap)
        level = "%d-%d" % (lo, hi)
        pid = gr["id"]
        blocks.append({
            "id": "%s_block" % pid,
            "place": "%s, %d blocks from %s's centre (data/training_grounds.json)" % (gr["name"], round(s["town_distance"]), gr["town"]),
            "pool": "cobblers:%s" % pid,
            "style": "activated",
            "replace_spawns": False,
            "position": {"x": s["x"], "y": s["y"], "z": s["z"]},
            "mimic": doc["block"]["mimic"],
            "activated": dict(act),
            "status": "planned",
            "why": "written by tools/training_grounds.py records --write: the levelling catch-up for gym %d (cap %d, "
                   "docs/mechanics/LEVEL_CATCHUP.md). In the grass at the heightmap's ground, keeping up to %d of its pool "
                   "alive within %d blocks; battle EXP from them stops at the cap (rctmod)." % (gr["gym"], cap, act["max_spawns"], act["spawn_range"])})
        hab_entries, entries = [], []
        for row in roster(doc, gr["gym"]):
            sp = row["species"]
            bucket = rar[row["role"]]["bucket"]
            hab_entries.append({"species": sp.capitalize(), "pokemon": sp, "family": "happiny" if sp in ("chansey", "blissey") else sp,
                                "family_priority": row["role"], "ambient": True, "eligibility_reason": row["why"],
                                "level": level, "bucket": bucket, "weight": row["weight"], "conditions": {}})
            entries.append({"id": "habitat.%s.%s" % (pid, sp), "species": sp, "bucket": bucket, "level": level,
                            "weight": row["weight"], "ambient": True, "scope": pid, "mechanism": "habitat_block",
                            "conditions": {}, "eligibility_reason": row["why"], "spawnable_position": "grounded"})
        habitat = {"id": pid, "display_name": gr["name"],
                   "intended_location": "%s: one activated Habitat Block, %s_block in data/habitat_blocks.json, at (%d, %d, %d), "
                                        "%d blocks from %s's centre and %d from the nearest route path"
                                        % (gr["name"], pid, s["x"], s["y"], s["z"], round(s["town_distance"]), gr["town"],
                                           round(s["path_clearance"])),
                   "mechanism": "habitat_block", "replace_spawns": False,
                   "level_band": {"minimum": lo, "maximum": hi},
                   "level_band_why": "cap %d (the cap before gym %d, rctmod's computation in tools/legendaries_audit.py rct_caps) "
                                     "less %s: %s" % (cap, gr["gym"], doc["levels"]["below_cap"], doc["levels"]["why"]),
                   "why": "the levelling catch-up (docs/mechanics/LEVEL_CATCHUP.md): " + doc["rosters"]["why"],
                   "entries": hab_entries,
                   "placement_status": "authored: data/habitat_blocks.json %s_block, status planned" % pid}
        pools.append((habitat, entries))
    return blocks, pools


def merged(doc, capmap=None):
    """(habitat_blocks doc, spawns doc) with this tool's records upserted in place."""
    blocks, pools = records(doc, capmap)
    hd = json.loads(HABITATS.read_text(encoding="utf-8"))
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    ids = {b["id"] for b in blocks}
    hd["blocks"] = [b for b in hd["blocks"] if b.get("id") not in ids] + blocks
    pids = {h["id"] for h, _e in pools}
    sd["habitats"] = [h for h in sd["habitats"] if h.get("id") not in pids] + [h for h, _e in pools]
    sd["entries"] = [e for e in sd["entries"] if e.get("scope") not in pids] + [e for _h, es in pools for e in es]
    return hd, sd


def dumps(d):
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------------------------------------- the sign
def sign_rotation(dx, dz):
    """A standing sign's rotation (0 = its front faces south, +z; 4 west; 8 north; 12 east) facing along (dx, dz)."""
    return int(round(math.degrees(math.atan2(-dx, dz)) / 22.5)) % 16


def sign_lines(doc, g=None):
    import ground as G
    g = g or G.load()
    towns = {t["id"]: t for t in json.loads(TOWNS.read_text(encoding="utf-8"))["towns"]}
    sg = doc["sign"]
    text = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(sg["lines"]) + ["", "", "", ""])[:4])
    out = ["# Generated by tools/training_grounds.py from data/training_grounds.json. Re-run to rebuild; do not edit.",
           "# One sign at each training ground (the Habitat Block itself is placed by tools/habitat_blocks.py, R9E)."]
    for gr in doc["grounds"]:
        s = gr["site"]
        x, z = s["x"] + sg["offset"][0], s["z"] + sg["offset"][1]
        y = g(x, z) + 1
        t = towns[gr["town"]]["centre"]
        rot = sign_rotation(t["x"] - x, t["z"] - z)
        out += ["# %s" % gr["name"], "forceload add %d %d" % (x, z),
                "setblock %d %d %d %s[rotation=%d]{front_text:{messages:[%s]}} replace" % (x, y, z, sg["block"], rot, text),
                "forceload remove %d %d" % (x, z)]
    return out


def build(doc, out=DEFAULT_OUT, g=None):
    import function_limits
    lines = sign_lines(doc, g)
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise SiteError("build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    fn = out / "data" / NS / "function" / FN / "build.mcfunction"
    fn.parent.mkdir(parents=True, exist_ok=True)
    fn.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                                 "Cobblers: training ground signs (tools/training_grounds.py)"}}, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    return fn, lines


# ------------------------------------------------------------------------------------------------------ the estimate
GROUPS = {
    # MediumSlow read from the jar (javap: max(0, 6n^3/5 - 15n^2 + 100n - 140)); the others the main series' formulas
    "medium_slow": lambda n: max(0, 6 * n ** 3 // 5 - 15 * n ** 2 + 100 * n - 140),
    "medium_fast": lambda n: n ** 3,
    "slow": lambda n: 5 * n ** 3 // 4,
}


def ko_exp(base, foe_level, own_level):
    """One knock-out's EXP for a participant: StandardExperienceCalculator, Cobblemon 1.8.0 (javap), wild foe, the
    Pokemon's own trainer, no Lucky Egg, no affection or evolution bonus, experienceMultiplier 2.0."""
    t1 = base * foe_level / 5.0
    t3 = ((2.0 * foe_level + 10) / (foe_level + own_level + 10)) ** 2.5
    return int(round((t1 * t3 + 1) * EXP_MULTIPLIER))


def estimate(doc, capmap=None, group="medium_slow", seconds_per_ko=60):
    """[(gym, cap, KOs to cap - 2, KOs to cap, minutes to cap - 2, minutes to cap)] for the documented arrival model:
    a party of six, four at the tier's band top (cap - 6) and two recent catches at its middle (cap - 11), each KO
    against the roster's weight-averaged yield at the band's middle level, one participant per KO, every gain clamped at
    the cap as rctmod clamps it."""
    capmap = capmap or caps()
    G = GROUPS[group]
    out = []
    for gr in doc["grounds"]:
        cap = capmap[gr["gym"]]
        lo, hi = band(doc, cap)
        rows = roster(doc, gr["gym"])
        base = sum(BASE_EXP[r["species"]] * r["weight"] for r in rows) / sum(r["weight"] for r in rows)
        foe = (lo + hi) / 2.0
        to2 = to0 = 0
        for start in [cap - 6] * 4 + [cap - 11] * 2:
            e, lv, n, n2 = G(start), start, 0, None
            while lv < cap:
                e += min(ko_exp(base, foe, lv), G(cap) - e)
                n += 1
                while G(lv + 1) <= e:
                    lv += 1
                if n2 is None and lv >= cap - 2:
                    n2 = n
            to2 += n2 or 0
            to0 += n
        out.append((gr["gym"], cap, to2, to0, round(to2 * seconds_per_ko / 60.0, 1), round(to0 * seconds_per_ko / 60.0, 1)))
    return out


# -------------------------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("site")
    s.add_argument("--write", action="store_true")
    r = sub.add_parser("records")
    r.add_argument("--write", action="store_true")
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(DEFAULT_OUT))
    sub.add_parser("estimate")
    a = ap.parse_args(argv)
    doc = load()
    if a.cmd == "site":
        try:
            sites = site_all(doc)
        except SiteError as exc:
            print("FAULT: %s" % exc)
            return 1
        for gid, f in sites.items():
            print("%s: (%d, %d, %d) %.0f from town, path %.0f, feature %.0f (%s), relief %d, canopy %.2f"
                  % (gid, f["x"], f["y"], f["z"], f["town_distance"], f["path_clearance"], f["feature_clearance"],
                     f["nearest_feature"], f["relief"], f["canopy"]))
        if a.write:
            for gr in doc["grounds"]:
                gr["site"] = sites[gr["id"]]
            DATA.write_text(dumps(doc), encoding="utf-8", newline="\n")
            print("wrote %d sites to %s" % (len(sites), DATA.relative_to(ROOT)))
        return 0
    if a.cmd == "records":
        hd, sd = merged(doc)
        if a.write:
            HABITATS.write_text(dumps(hd), encoding="utf-8", newline="\n")
            SPAWNS.write_text(dumps(sd), encoding="utf-8", newline="\n")
            print("wrote %d blocks and %d pools" % (len(doc["grounds"]), len(doc["grounds"])))
            return 0
        drift = [p.name for p, d in ((HABITATS, hd), (SPAWNS, sd)) if p.read_text(encoding="utf-8") != dumps(d)]
        if drift:
            print("DRIFT: %s differ from the generated records; run records --write" % ", ".join(drift))
            return 1
        print("records: %d grounds in step with data/habitat_blocks.json and data/spawns.json" % len(doc["grounds"]))
        return 0
    if a.cmd == "build":
        fn, lines = build(doc, a.out)
        print("training_grounds: %d signs -> %s" % (len(doc["grounds"]), fn))
        return 0
    if a.cmd == "estimate":
        for grp in ("medium_slow", "slow"):
            for gym, cap, k2, k0, m2, m0 in estimate(doc, group=grp):
                print("%s gym %d cap %d: %d KOs (%.0f min) to cap-2, %d KOs (%.0f min) to cap" % (grp, gym, cap, k2, m2, k0, m0))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
