#!/usr/bin/env python
"""An independent audit of the training grounds (data/training_grounds.json, docs/mechanics/LEVEL_CATCHUP.md section 7).

It checks what tools/training_grounds.py GENERATED -- the Habitat Block records in data/habitat_blocks.json, the
habitat and entries in data/spawns.json, the compiled habitat pools and the sign function -- against expectations
derived from sources the generator does not use for them:

  caps        data/trainers.json generation_contract gym_ace_levels (cross-checked with each leader's team top) and
              initialLevelCap / relativeLevelCap from modpack/config/rctmod-server.toml; never tools/legendaries_audit.py
              rct_caps, which the generator calls
  tiers       data/encounter_design.json rules.tiers (the tier whose cap is the cap held before the gym) and
              rules.non_level_evolution_min_tier
  species     the Cobblemon 1.8.0 jar's species files (evolution method into each stage, base experience)
  ground      tools/ground.py (the canonical heightmap, rounded) and data/world.json's sea level; build/paint water
              masks and terrain.png (the painted world), read directly, not through the generator's water_map
  paths       data/route_paths.json, distance to every SEGMENT (not just the vertices)
  buildings   derived/towns/*_placement.json building footprints and *_plan.json anchors, lots, lamps and waystones,
              for every town (not only the host)
  nests       every other block in data/habitat_blocks.json, with each block's own range field

The distances it holds them to are the ones data/training_grounds.json `rules` states (the design's claim); no
threshold here is tuned to the data. Nothing is imported from tools/training_grounds.py.

  python tools/training_grounds_audit.py [--pools DIR] [--signs FILE] [--out FILE]

Without --pools the habitat pools are compiled in memory by tools/compile_spawns.py compile_habitat (the compiler
under test) from data/spawns.json, and the report says so. Exit 0 all checks pass; 1 any FAIL; 2 a check could not
run (NOT_EXECUTED), which is never reported as a pass.

What it does NOT cover (needs a running server, docs/mechanics/LEVEL_CATCHUP.md section 7):
  - that rctmod actually clamps EXP at the cap in game, and the cobblecuisine overshoot (D1, D2);
  - that the block is in the world at its position with its PoolId (habitat_blocks.py verify on a stopped copy);
  - walkability from the town: it reports the steepest step and water on the straight line as NOTES only;
  - features outside data/ and derived/towns (other derived dressing, templates' own NPC spawners);
  - datapack overrides of the jar's species data.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

TG = ROOT / "data" / "training_grounds.json"
HABITATS = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
TRAINERS = ROOT / "data" / "trainers.json"
TOWNS = ROOT / "data" / "towns.json"
PATHS = ROOT / "data" / "route_paths.json"
ENCOUNTER = ROOT / "data" / "encounter_design.json"
WORLD = ROOT / "data" / "world.json"
RCT_TOML = ROOT / "modpack" / "config" / "rctmod-server.toml"
PAINT = ROOT / "build" / "paint"
TOWN_PLANS = ROOT / "derived" / "towns"
SIGNS = ROOT / "build" / "datapacks" / "cobblers_training_grounds" / "data" / "cobblers" / "function" / "training_grounds" / "build.mcfunction"
LOCAL_JARS = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods")
PREFIX = "training_ground_"


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


class Report:
    def __init__(self):
        self.rows = []

    def add(self, subject, check, status, detail=""):
        self.rows.append({"subject": subject, "check": check, "status": status, "detail": detail})

    def ok(self, subject, check, cond, detail):
        self.add(subject, check, "PASS" if cond else "FAIL", detail)
        return cond

    def failures(self, subject=None, check=None):
        return [r for r in self.rows if r["status"] == "FAIL" and (subject is None or r["subject"] == subject)
                and (check is None or r["check"] == check)]

    def count(self, status):
        return sum(1 for r in self.rows if r["status"] == status)


# ----------------------------------------------------------------------------------------------------------- caps
def toml_int(text, key):
    m = re.search(r"^\s*%s\s*=\s*(-?\d+)" % key, text, re.M)
    if not m:
        raise ValueError("%s not in the rctmod config" % key)
    return int(m.group(1))


def gym_caps(trainers, toml_text):
    """({gym N: the cap a player holds before gym N}, [problems]).

    rctmod's rule as its config states it: the cap is the next required trainer's strongest Pokemon plus
    relativeLevelCap, never below initialLevelCap. The next required trainer before gym N is gym leader N, whose
    strongest Pokemon is data/trainers.json generation_contract gym_ace_levels[N-1]; that number is cross-checked
    against the leader record's own team, and a disagreement is a problem, not silently resolved."""
    init, rel = toml_int(toml_text, "initialLevelCap"), toml_int(toml_text, "relativeLevelCap")
    gc = trainers["generation_contract"]
    aces = gc["gym_ace_levels"]
    problems = []
    if gc.get("relative_level_cap") is not None and gc["relative_level_cap"] != rel:
        problems.append("generation_contract relative_level_cap %s != rctmod relativeLevelCap %d" % (gc["relative_level_cap"], rel))
    leaders = {t.get("order"): t for t in trainers["trainers"] if t.get("class") == "gym_leader"}
    out = {}
    for n in range(1, len(aces) + 1):
        lead = leaders.get(n)
        top = max(m["level"] for m in lead["team"]) if lead and lead.get("team") else None
        if top != aces[n - 1]:
            problems.append("gym %d: gym_ace_levels says %s, the leader's team top is %s" % (n, aces[n - 1], top))
        out[n] = max(init, aces[n - 1] + rel)
    return out, problems


# ------------------------------------------------------------------------------------------------------- species
def jar_path(jar_dir=None):
    d = Path(jar_dir or os.environ.get("COBBLERS_JAR_DIR") or LOCAL_JARS)
    hits = sorted(glob.glob(str(d / "Cobblemon-fabric-1.8*.jar"))) + sorted(glob.glob(str(d / "cobblemon-fabric-1.8*.jar")))
    return Path(hits[0]) if hits else None


def jar_species(jar):
    """{species name: species json} for every file under data/cobblemon/species/ in the jar."""
    out = {}
    with zipfile.ZipFile(jar) as z:
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                out[Path(n).stem] = json.loads(z.read(n))
    return out


def arrival(species, name):
    """How `name` is reached from its pre-evolution: (method, level) with method "base" (no pre-evolution), "level"
    (a minLevel requirement), "trade" or "other"; plus the arrival of the pre-evolution chain, worst first."""
    sp = species[name]
    pre = sp.get("preEvolution")
    if not pre:
        return [("base", None)]
    pre = pre.split()[0]
    evo = [e for e in species.get(pre, {}).get("evolutions", []) if str(e.get("result", "")).split()[0] == name]
    if not evo:
        return [("other", None)] + arrival(species, pre)
    e = evo[0]
    if e.get("variant") == "trade":
        here = ("trade", None)
    else:
        lv = [r.get("minLevel") for r in e.get("requirements", []) if r.get("variant") == "level"]
        here = ("level", lv[0]) if lv else ("other", None)
    return [here] + arrival(species, pre)


def next_level_evolution(species, name):
    lv = [r.get("minLevel") for e in species[name].get("evolutions", []) if e.get("variant") != "trade"
          for r in e.get("requirements", []) if r.get("variant") == "level"]
    return min(lv) if lv else None


def legal(species, name, tier, band, lo, hi, min_tier):
    """[problems] for `name` spawning at lo-hi in `tier` (band [b0, b1]) by the encounter rules
    (data/spawns.json evolution_policy): a stage evolved not by level only from min_tier['other'] (trade
    min_tier['trade']) and in the upper half of the band; a level stage not under its evolution level; never past
    four over its own next level evolution; no legendary or mythical."""
    if name not in species:
        return ["%s is not a Cobblemon 1.8.0 species" % name]
    bad = []
    labels = set(species[name].get("labels") or [])
    if labels & {"legendary", "mythical", "ultra_beast", "paradox"}:
        bad.append("%s is %s" % (name, sorted(labels & {"legendary", "mythical", "ultra_beast", "paradox"})))
    chain = arrival(species, name)
    mid = (band[0] + band[1]) / 2.0
    for method, lv in chain:
        if method in ("trade", "other"):
            need = min_tier[method]
            if tier < need:
                bad.append("%s is reached by a %s evolution, legal from tier %d, here tier %d" % (name, method, need, tier))
            if lo < mid:
                bad.append("%s (%s evolution) spawns from %d, under the band's midpoint %.1f" % (name, method, lo, mid))
    if chain[0][0] == "level" and lo < chain[0][1]:
        bad.append("%s spawns from %d, under its evolution level %d" % (name, lo, chain[0][1]))
    nxt = next_level_evolution(species, name)
    if nxt is not None and hi > nxt + 4:
        bad.append("%s spawns to %d, past its evolution level %d + 4" % (name, hi, nxt))
    return bad


# -------------------------------------------------------------------------------------------------------- geometry
def seg_distance(px, pz, pts):
    """Least distance from (px, pz) to the polyline through pts (an (n, 2) array), segment by segment."""
    a, b = pts[:-1], pts[1:]
    if len(pts) == 1:
        return float(np.hypot(pts[0, 0] - px, pts[0, 1] - pz))
    d = b - a
    L2 = (d ** 2).sum(1)
    t = np.where(L2 > 0, ((px - a[:, 0]) * d[:, 0] + (pz - a[:, 1]) * d[:, 1]) / np.where(L2 > 0, L2, 1), 0.0)
    t = np.clip(t, 0, 1)
    cx, cz = a[:, 0] + t * d[:, 0], a[:, 1] + t * d[:, 1]
    return float(np.min(np.hypot(cx - px, cz - pz)))


def rect_distance(px, pz, x0, z0, x1, z1):
    """Distance from a column to an inclusive block rectangle (0 inside it)."""
    x0, x1 = min(x0, x1), max(x0, x1)
    z0, z1 = min(z0, z1), max(z0, z1)
    dx = max(x0 - px, 0, px - x1)
    dz = max(z0 - pz, 0, pz - z1)
    return math.hypot(dx, dz)


def facing(rotation):
    """The unit (dx, dz) a standing sign's front faces: rotation 0 south (+z), 4 west, 8 north, 12 east
    (Minecraft standing-sign block state, 16 steps of 22.5 degrees clockwise seen from above)."""
    a = math.radians(rotation * 22.5)
    return -math.sin(a), math.cos(a)


def angle_between(u, v):
    nu, nv = math.hypot(*u), math.hypot(*v)
    c = (u[0] * v[0] + u[1] * v[1]) / (nu * nv)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def town_features(plans_dir):
    """[(kind, id, rect x0 z0 x1 z1)] for every building, anchor, lot, lamp and waystone in every derived town."""
    out = []
    for f in sorted(Path(plans_dir).glob("*_placement.json")):
        d = jload(f)
        for b in d.get("buildings", []):
            if b.get("footprint"):
                out.append(("building", b["id"], tuple(b["footprint"])))
        w = d.get("waystone")
        if w:
            out.append(("waystone", f.stem, (w[0], w[2], w[0], w[2])))
    for f in sorted(Path(plans_dir).glob("*_plan.json")):
        d = jload(f)
        for a in d.get("anchors", []):
            if a.get("rect"):
                out.append(("anchor:%s" % a.get("role"), a["id"], tuple(a["rect"])))
        for lot in d.get("lots", []):
            out.append(("lot", lot.get("id", f.stem), tuple(lot["rect"])))
        for lamp in d.get("lamps", []):
            at = lamp["at"]
            out.append(("lamp", "%s:%s" % (f.stem, lamp.get("street")), (at[0], at[2], at[0], at[2])))
    return out


def street_runs(plans_dir):
    """[(town, x0, z, x1)] every paved street run ([z, y, x0, x1] in the plan)."""
    out = []
    for f in sorted(Path(plans_dir).glob("*_plan.json")):
        for sid, s in (jload(f).get("streets") or {}).items():
            for z, _y, x0, x1 in s.get("cells", []):
                out.append((f.stem, x0, z, x1))
    return out


def painted_water(paint_dir, x0, z0, x1, z1):
    """A (z, x) bool array over the inclusive box: inside any painted water mask (build/paint/manifest.json water)."""
    from PIL import Image
    man = jload(Path(paint_dir) / "manifest.json")
    wet = np.zeros((z1 - z0 + 1, x1 - x0 + 1), bool)
    for w in man.get("water", []):
        img = np.asarray(Image.open(Path(paint_dir) / w.get("mask", w.get("levels")))) > 0
        if img.ndim == 3:
            img = img.any(2)
        mx0, mz0 = w["x"], w["z"]
        mx1, mz1 = mx0 + img.shape[1] - 1, mz0 + img.shape[0] - 1
        ix0, iz0, ix1, iz1 = max(x0, mx0), max(z0, mz0), min(x1, mx1), min(z1, mz1)
        if ix0 > ix1 or iz0 > iz1:
            continue
        wet[iz0 - z0:iz1 - z0 + 1, ix0 - x0:ix1 - x0 + 1] |= img[iz0 - mz0:iz1 - mz0 + 1, ix0 - mx0:ix1 - mx0 + 1]
    return wet


def terrain_code(paint_dir, x, z):
    from PIL import Image
    man = jload(Path(paint_dir) / "manifest.json")
    img = np.asarray(Image.open(Path(paint_dir) / man["terrain"]))
    codes = {v: int(k) for k, v in man["terrain_codes"].items()}
    return int(img[z, x]), codes.get("GRASS")


# ----------------------------------------------------------------------------------------------------------- signs
SIGN_RE = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) ([a-z0-9_:]+)\[rotation=(\d+)\]\{front_text:\{messages:\[(.*)\]\}\} replace$")


def parse_signs(lines):
    """[(x, y, z, block, rotation, [text lines], forceloaded)] from the sign function."""
    out = []
    loaded = set()
    for ln in lines:
        ln = ln.strip()
        m = re.match(r"^forceload add (-?\d+) (-?\d+)$", ln)
        if m:
            loaded.add((int(m.group(1)) >> 4, int(m.group(2)) >> 4))
            continue
        m = SIGN_RE.match(ln)
        if m:
            x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
            texts = [json.loads(t.replace("\\'", "'")) for t in re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(6))]
            out.append((x, y, z, m.group(4), int(m.group(5)), texts, (x >> 4, z >> 4) in loaded))
    return out


# ------------------------------------------------------------------------------------------------------------ pools
def compile_pools_in_memory(spawns):
    import compile_spawns as C
    out = {}
    for h in spawns.get("habitats", []):
        if not str(h.get("id", "")).startswith(PREFIX):
            continue
        ents = [e for e in spawns["entries"] if e.get("mechanism") == "habitat_block" and e.get("scope") == h["id"]]
        out[h["id"]], _s = C.compile_habitat(h, ents)
    return out


def pools_from_dir(d):
    out = {}
    for f in sorted(Path(d).glob(PREFIX + "*.json")):
        out[f.stem] = jload(f)
    return out


def parse_range(s):
    a, b = str(s).split("-")
    return int(a), int(b)


# ------------------------------------------------------------------------------------------------------------ audit
class Inputs:
    """Every independent source, loaded once; tests pass their own."""

    def __init__(self, g=None, jar=None, plans_dir=TOWN_PLANS, paint_dir=PAINT):
        import ground as G
        self.g = g or G.load()
        self.sea = int(round(float((jload(WORLD).get("vertical") or {}).get("sea_level", 62))))
        self.caps, self.cap_problems = gym_caps(jload(TRAINERS), RCT_TOML.read_text(encoding="utf-8"))
        enc = jload(ENCOUNTER)["rules"]
        self.tiers = {int(k): v for k, v in enc["tiers"].items()}
        self.min_tier = enc["non_level_evolution_min_tier"]
        self.towns = {t["id"]: t for t in jload(TOWNS)["towns"]}
        self.paths = {k: np.array(v, float) for k, v in jload(PATHS)["paths"].items()}
        self.plans_dir, self.paint_dir = Path(plans_dir), Path(paint_dir)
        self.features = town_features(plans_dir) if Path(plans_dir).is_dir() else None
        self.streets = street_runs(plans_dir) if Path(plans_dir).is_dir() else None
        jp = jar if jar is not None else jar_path()
        self.species = jar_species(jp) if jp and Path(jp).is_file() else None
        self.jar = jp


def audit(design, habitat_doc, spawns_doc, pools, sign_lines, inp, pool_source="?"):
    R = Report()
    rules = design["rules"]
    act = design["block"]["activated"]
    sr = act["spawn_range"]
    below_lo, below_hi = design["levels"]["below_cap"]
    rar = spawns_doc["rarity"]
    blocks = habitat_doc["blocks"]
    for p in inp.cap_problems:
        R.add("caps", "cap_sources_agree", "FAIL", p)
    if not inp.cap_problems:
        R.add("caps", "cap_sources_agree", "PASS", "gym_ace_levels == every leader's team top; caps %s" % inp.caps)

    ours = {b["id"]: b for b in blocks if str(b.get("id", "")).startswith(PREFIX)}
    expected_ids = {"%s_block" % gr["id"] for gr in design["grounds"]}
    R.ok("records", "blocks_one_per_ground", set(ours) == expected_ids,
         "manifest training-ground blocks %s, grounds %s" % (sorted(set(ours) - expected_ids) or "ok",
                                                              sorted(expected_ids - set(ours)) or "ok"))
    habs = {h["id"]: h for h in spawns_doc.get("habitats", []) if str(h.get("id", "")).startswith(PREFIX)}
    R.ok("records", "habitats_one_per_ground", set(habs) == {gr["id"] for gr in design["grounds"]},
         "spawns.json training-ground habitats %s" % sorted(habs))
    signs = parse_signs(sign_lines) if sign_lines is not None else None
    sign_doc = design["sign"]

    for gr in design["grounds"]:
        gid, n = gr["id"], gr["gym"]
        b = ours.get("%s_block" % gid)
        if b is None:
            R.add(gid, "block_present", "FAIL", "no %s_block in data/habitat_blocks.json" % gid)
            continue
        x, y, z = b["position"]["x"], b["position"]["y"], b["position"]["z"]
        where = "(%d, %d, %d)" % (x, y, z)
        cap = inp.caps.get(n)

        # 1. levels, from every artifact that carries them
        lvls = []
        pool = pools.get(gid)
        if pool is None:
            R.add(gid, "pool_present", "FAIL", "no compiled habitat pool %s (%s)" % (gid, pool_source))
        else:
            lvls += [("pool:%s" % s["species"], parse_range(s["levelRange"])) for s in pool.get("spawns", [])]
        ents = [e for e in spawns_doc["entries"] if e.get("scope") == gid]
        lvls += [("entry:%s" % e["species"], parse_range(e["level"])) for e in ents]
        h = habs.get(gid)
        if h:
            lvls.append(("level_band", (h["level_band"]["minimum"], h["level_band"]["maximum"])))
            lvls += [("habitat:%s" % e["pokemon"], parse_range(e["level"])) for e in h.get("entries", [])]
        over = [(k, v) for k, v in lvls if v[1] > cap]
        R.ok(gid, "levels_never_exceed_cap", not over and bool(lvls),
             "cap before gym %d is %d; %s" % (n, cap, "over: %s" % over if over else "%d level ranges, all <= cap" % len(lvls)))
        outside = [(k, v) for k, v in lvls if not (cap - 3 <= v[0] <= v[1] <= cap - 1)]
        R.ok(gid, "levels_within_cap_minus_3_to_1", not outside and bool(lvls),
             "expected within %d-%d; %s" % (cap - 3, cap - 1, "outside: %s" % outside if outside else "all inside"))
        exp_lo, exp_hi = cap - below_lo, cap - below_hi

        # 2. species legal at the tier
        tier = next((t for t, v in inp.tiers.items() if v["cap"] == cap), None)
        roster = [s["species"] for s in pool.get("spawns", [])] if pool else [e["species"] for e in ents]
        if inp.species is None:
            R.add(gid, "species_legal_at_tier", "NOT_EXECUTED", "no Cobblemon 1.8 jar (set COBBLERS_JAR_DIR)")
        elif tier is None:
            R.add(gid, "species_legal_at_tier", "FAIL", "no tier in data/encounter_design.json has cap %d" % cap)
        else:
            band = inp.tiers[tier]["band"]
            probs = []
            for sp in roster:
                probs += legal(inp.species, sp, tier, band, exp_lo, exp_hi, inp.min_tier)
            R.ok(gid, "species_legal_at_tier", not probs and bool(roster),
                 "tier %d band %s: %s" % (tier, band, probs or "%s legal" % sorted(set(roster))))
            # the design's base-experience claims, against the jar
            claims = []
            for row in (design["rosters"]["tiers_6_to_8" if n >= 6 else "tiers_1_to_5"]):
                m = re.search(r"yield (\d+)", row.get("why", ""))
                if m and inp.species.get(row["species"], {}).get("baseExperienceYield") != int(m.group(1)):
                    claims.append("%s claims %s, jar %s" % (row["species"], m.group(1),
                                                           inp.species.get(row["species"], {}).get("baseExperienceYield")))
            R.ok(gid, "base_experience_claims", not claims, claims or "the roster's yields match the jar")

        # 3. dry ground at the stated y
        gy = inp.g(x, z)
        R.ok(gid, "block_y_is_ground", y == gy, "%s: heightmap ground y%d" % (where, gy))
        wr = sr + rules["water_margin_blocks"]
        box = inp.g.box(x - wr, z - wr, x + wr, z + wr)
        yy, xx = np.mgrid[-wr:wr + 1, -wr:wr + 1]
        disk = xx * xx + yy * yy <= wr * wr
        low = int(((box <= inp.sea) & disk).sum())
        painted = int((painted_water(inp.paint_dir, x - wr, z - wr, x + wr, z + wr) & disk).sum()) if inp.paint_dir.is_dir() else None
        R.ok(gid, "dry_ground", gy > inp.sea and low == 0 and painted == 0,
             "%s: ground y%d vs sea %d; %d columns at/under sea and %s in painted water within %d" % (where, gy, inp.sea, low, painted, wr))
        if inp.paint_dir.is_dir():
            code, grass = terrain_code(inp.paint_dir, x, z)
            R.ok(gid, "grass_under_mimic", code == grass, "%s: terrain code %d, GRASS is %s (mimic %s)" % (where, code, grass, b.get("mimic")))

        # 4. nests: no overlap with any other block, and the stated margin from activated ones
        clash, margin = [], []
        for o in blocks:
            if o is b:
                continue
            ro = (o.get("activated") or {}).get("spawn_range") if o.get("style") == "activated" else o.get("range_of_influence")
            if ro is None:
                clash.append("%s has no range" % o["id"])
                continue
            op = o["position"]
            d2 = math.hypot(op["x"] - x, op["z"] - z)
            d3 = math.sqrt(d2 * d2 + (op["y"] - y) ** 2)
            if d3 < ro + sr:
                clash.append("%s %.1f < %d" % (o["id"], d3, ro + sr))
            if o.get("style") == "activated" and d2 < ro + sr + rules["nest_margin_blocks"]:
                margin.append("%s %.1f < %d" % (o["id"], d2, ro + sr + rules["nest_margin_blocks"]))
        R.ok(gid, "no_range_overlap", not clash, clash or "clear of %d other blocks" % (len(blocks) - 1))
        R.ok(gid, "nest_margin", not margin, margin or "every activated block >= its range + %d + %d" % (sr, rules["nest_margin_blocks"]))

        # 5. route paths (segments) and buildings
        pd = min((seg_distance(x, z, p), k) for k, p in inp.paths.items())
        R.ok(gid, "path_clearance", pd[0] >= rules["path_clear_blocks"],
             "%s: %.1f from route path %s, needs %d" % (where, pd[0], pd[1], rules["path_clear_blocks"]))
        if inp.features is None:
            R.add(gid, "building_clearance", "NOT_EXECUTED", "no derived/towns")
        else:
            near = sorted((rect_distance(x, z, *r), kind, fid) for kind, fid, r in inp.features)
            bad = [(round(d, 1), k, f) for d, k, f in near if d < rules["building_clear_blocks"]]
            R.ok(gid, "building_clearance", not bad,
                 "%s: %s" % (where, bad or "nearest %s %s at %.1f, needs %d" % (near[0][1], near[0][2], near[0][0], rules["building_clear_blocks"])))
            sd = min((rect_distance(x, z, x0, zz, x1, zz), t) for t, x0, zz, x1 in inp.streets) if inp.streets else None
            if sd:
                R.add(gid, "town_street_distance", "NOTE", "%.1f from a paved street of %s" % sd)

        # 6. distance from the town
        tc = inp.towns[gr["town"]]["centre"]
        td = math.hypot(x - tc["x"], z - tc["z"])
        lo_r, hi_r = rules["ring_blocks"]
        R.ok(gid, "town_distance", lo_r <= td <= hi_r, "%.1f from %s's centre, stated %d-%d" % (td, gr["town"], lo_r, hi_r))
        # reachability, as a note: the straight line from the town centre
        steps = int(td * 2) + 1
        xs = np.linspace(tc["x"], x, steps).round().astype(int)
        zs = np.linspace(tc["z"], z, steps).round().astype(int)
        hs = np.array([inp.g(a, c) for a, c in zip(xs, zs)])
        R.add(gid, "straight_walk", "NOTE", "steepest step %d between half-block samples, %d samples at/under sea, net %+d"
              % (int(np.abs(np.diff(hs)).max()), int((hs <= inp.sea).sum()), int(hs[-1] - hs[0])))

        # 7. the sign
        if signs is None:
            R.add(gid, "sign", "NOT_EXECUTED", "no sign function")
        else:
            ox, oz = sign_doc["offset"]
            mine = [s for s in signs if (s[0], s[2]) == (x + ox, z + oz)]
            if len(mine) != 1:
                R.add(gid, "sign_present", "FAIL", "%d signs at the stated offset (%d, %d) from %s" % (len(mine), ox, oz, where))
            else:
                sx, sy, sz, blk, rot, texts, loaded = mine[0]
                sg = inp.g(sx, sz)
                swet = painted_water(inp.paint_dir, sx, sz, sx, sz)[0, 0] if inp.paint_dir.is_dir() else False
                R.ok(gid, "sign_supported", sy == sg + 1 and sg > inp.sea and not swet and (sx, sz) != (x, z),
                     "sign (%d, %d, %d) over ground y%d (sea %d, painted water %s)" % (sx, sy, sz, sg, inp.sea, bool(swet)))
                ang = angle_between(facing(rot), (tc["x"] - sx, tc["z"] - sz))
                R.ok(gid, "sign_faces_town", ang <= 11.25 + 1e-6,
                     "rotation %d faces %.1f degrees off the town centre (max 11.25)" % (rot, ang))
                R.ok(gid, "sign_text_and_load", blk == sign_doc["block"] and texts == list(sign_doc["lines"]) and loaded,
                     "block %s, lines %s, forceloaded %s" % (blk, texts == list(sign_doc["lines"]), loaded))

        # 8. the compiled pool matches the record
        want = {r["species"]: r for r in design["rosters"]["tiers_6_to_8" if n >= 6 else "tiers_1_to_5"]}
        if pool is not None:
            got = {s["species"]: s for s in pool.get("spawns", [])}
            diff = []
            if set(got) != set(want):
                diff.append("species %s vs roster %s" % (sorted(got), sorted(want)))
            for sp, row in want.items():
                s = got.get(sp)
                if not s:
                    continue
                exp = {"levelRange": "%d-%d" % (exp_lo, exp_hi), "weight": row["weight"], "bucket": rar[row["role"]]["bucket"],
                       "spawnablePositionType": "grounded"}
                for k, v in exp.items():
                    if s.get(k) != v:
                        diff.append("%s %s %r != %r" % (sp, k, s.get(k), v))
            R.ok(gid, "pool_matches_record", not diff, diff or "%d spawns, %d-%d (%s)" % (len(got), exp_lo, exp_hi, pool_source))
        R.ok(gid, "block_record", b.get("pool") == "cobblers:%s" % gid and b.get("style") == "activated"
             and b.get("activated") == act and b.get("mimic") == design["block"]["mimic"],
             "pool %s, style %s, activated %s" % (b.get("pool"), b.get("style"), b.get("activated") == act))
        s = gr.get("site") or {}
        R.ok(gid, "site_matches_block", (s.get("x"), s.get("y"), s.get("z")) == (x, y, z),
             "data/training_grounds.json site (%s, %s, %s) vs block %s" % (s.get("x"), s.get("y"), s.get("z"), where))
    return R


def load_sign_lines(path):
    p = Path(path)
    return p.read_text(encoding="utf-8").splitlines() if p.is_file() else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pools", help="a compiled habitat_pools directory (default: compile in memory from data/spawns.json)")
    ap.add_argument("--signs", default=str(SIGNS))
    ap.add_argument("--jar-dir")
    ap.add_argument("--out", help="write every row as JSON here")
    a = ap.parse_args(argv)
    design, hd, sd = jload(TG), jload(HABITATS), jload(SPAWNS)
    if a.pools:
        pools, src = pools_from_dir(a.pools), "compiled pools in %s" % a.pools
    else:
        pools, src = compile_pools_in_memory(sd), "compiled in memory from data/spawns.json; build/ not checked"
    inp = Inputs(jar=jar_path(a.jar_dir))
    R = audit(design, hd, sd, pools, load_sign_lines(a.signs), inp, src)
    if a.out:
        Path(a.out).write_text(json.dumps(R.rows, indent=1) + "\n", encoding="utf-8")
    for r in R.rows:
        if r["status"] in ("FAIL", "NOT_EXECUTED"):
            print("%s %s %s: %s" % (r["status"], r["subject"], r["check"], r["detail"]))
    print("training_grounds_audit: %d PASS, %d FAIL, %d NOT_EXECUTED, %d NOTE (pools: %s)"
          % (R.count("PASS"), R.count("FAIL"), R.count("NOT_EXECUTED"), R.count("NOTE"), src))
    return 1 if R.count("FAIL") else 2 if R.count("NOT_EXECUTED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
